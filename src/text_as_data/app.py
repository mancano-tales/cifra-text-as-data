from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from .codebook import spec_from_yaml_string, spec_to_yaml_string
from .corpus_import import parse_csv_rows, parse_xlsx_rows
from .db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine
from .disclosure import build_disclosure
from .export import results_to_csv_bytes, results_to_json_bytes, results_to_xlsx_bytes
from .extraction import run_extraction
from .providers import CliProvider, Provider, make_api_key_provider

_EXPORT_CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "json": "application/json",
}
_EXPORT_BUILDERS = {
    "csv": results_to_csv_bytes,
    "xlsx": results_to_xlsx_bytes,
    "json": results_to_json_bytes,
}

app = FastAPI(title="Cifra backend (Slice 1)")

app.add_middleware(
    CORSMiddleware,
    # A fixed single origin (":5173") breaks the moment two dev frontends
    # run at once on different ports -- a real scenario, not hypothetical,
    # once multiple people/sessions work on this repo locally. Any
    # localhost/127.0.0.1 origin on any port is allowed instead; this is a
    # local dev backend, not a deployed one, so there's no production
    # origin to restrict against.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = get_engine()


def get_engine_dependency():
    return _engine


class CreateRunRequest(BaseModel):
    codebook_id: int
    corpus_id: str
    model: str
    provider_mode: Literal["api_key", "cli"] = "api_key"
    cli_command: list[str] | None = None
    cli_prompt_mode: Literal["stdin", "arg"] = "stdin"


def get_provider_dependency(request: CreateRunRequest) -> Provider:
    """Built from the request's own `model` (and, for CLI mode, its own
    `cli_command`/`cli_prompt_mode`) -- not a hardcoded constant. The model
    actually invoked must match what's persisted on the `RunRecord` and
    used as the cache key in `run_extraction`, or both become misleading.

    CLI mode is the agent-agnostic path documented in AGENTS.md's provider
    layer design: any already-installed CLI that accepts a prompt and
    returns text works here, not just `claude -p` -- e.g. Google
    Antigravity's `agy -p "<prompt>"`, which (unlike `claude -p`) requires
    the prompt as a trailing argument rather than reading stdin, hence
    `cli_prompt_mode`."""
    if request.provider_mode == "cli":
        if not request.cli_command:
            raise HTTPException(status_code=422, detail="cli_command is required when provider_mode is 'cli'")
        return CliProvider(command=request.cli_command, prompt_mode=request.cli_prompt_mode)
    return make_api_key_provider(vendor="anthropic", model=request.model)


@app.get("/runs")
def list_runs(engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        runs = session.exec(select(RunRecord).order_by(RunRecord.created_at.desc())).all()
        results = []
        for run in runs:
            codebook = session.get(CodebookRecord, run.codebook_id)
            total = len(
                session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == run.corpus_id)).all()
            )
            processed = len(session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run.id)).all())
            results.append(
                {
                    "id": run.id,
                    "corpus_id": run.corpus_id,
                    "codebook_id": run.codebook_id,
                    "codebook_name": codebook.name if codebook else None,
                    "model": run.model,
                    "status": run.status,
                    "processed": processed,
                    "total": total,
                    "created_at": run.created_at,
                }
            )
        return results


@app.post("/runs")
def create_run(
    request: CreateRunRequest,
    background_tasks: BackgroundTasks,
    engine=Depends(get_engine_dependency),
    provider: Provider = Depends(get_provider_dependency),
):
    with Session(engine) as session:
        codebook = session.get(CodebookRecord, request.codebook_id)
        if codebook is None:
            raise HTTPException(status_code=404, detail=f"codebook {request.codebook_id} not found")

        provider_detail = (
            " ".join(request.cli_command) if request.provider_mode == "cli" and request.cli_command else request.model
        )
        run = RunRecord(
            codebook_id=request.codebook_id,
            corpus_id=request.corpus_id,
            model=request.model,
            provider_mode=request.provider_mode,
            provider_detail=provider_detail,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    background_tasks.add_task(run_extraction, engine, run_id, provider)
    return {"run_id": run_id}


@app.get("/runs/{run_id}")
def get_run(run_id: int, engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        total = len(session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == run.corpus_id)).all())
        processed = len(session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all())
        return {"id": run.id, "status": run.status, "processed": processed, "total": total}


def _extraction_with_snippet(session: Session, extraction: ExtractionRecord) -> dict:
    document = session.get(DocumentRecord, extraction.document_id)
    snippet = document.text[:160] if document else ""
    return {**extraction.model_dump(), "document_snippet": snippet}


def _extractions_with_snippets(session: Session, extractions: list[ExtractionRecord]) -> list[dict]:
    """Batch version of `_extraction_with_snippet` -- one query for every
    document a run's extractions reference, instead of one query per row.
    A single-row helper is fine for `update_extraction`, but the results
    and export endpoints list every row in a run, where a per-row lookup
    turns into N+1 queries as a run grows."""
    document_ids = {e.document_id for e in extractions}
    documents = (
        session.exec(select(DocumentRecord).where(DocumentRecord.id.in_(document_ids))).all()
        if document_ids
        else []
    )
    snippets = {d.id: d.text[:160] for d in documents}
    return [{**e.model_dump(), "document_snippet": snippets.get(e.document_id, "")} for e in extractions]


@app.get("/runs/{run_id}/results")
def get_run_results(run_id: int, engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        rows = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        return _extractions_with_snippets(session, rows)


class UpdateExtractionRequest(BaseModel):
    categoria: str
    justificativa: str


@app.put("/runs/{run_id}/results/{extraction_id}")
def update_extraction(
    run_id: int, extraction_id: int, request: UpdateExtractionRequest, engine=Depends(get_engine_dependency)
):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        extraction = session.get(ExtractionRecord, extraction_id)
        if extraction is None or extraction.run_id != run_id:
            raise HTTPException(status_code=404, detail=f"extraction {extraction_id} not found in run {run_id}")

        codebook = session.get(CodebookRecord, run.codebook_id)
        valid_labels = {c["label"] for c in spec_from_yaml_string(codebook.yaml_raw)["categories"]}
        if request.categoria not in valid_labels:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"categoria {request.categoria!r} is not a valid label for this codebook; "
                    f"expected one of {sorted(valid_labels)}"
                ),
            )

        extraction.categoria = request.categoria
        extraction.justificativa = request.justificativa
        session.add(extraction)
        session.commit()
        session.refresh(extraction)
        return _extraction_with_snippet(session, extraction)


@app.get("/runs/{run_id}/export")
def export_run_results(
    run_id: int, format: Literal["csv", "xlsx", "json"] = "csv", engine=Depends(get_engine_dependency)
):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        rows = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        result_rows = _extractions_with_snippets(session, rows)

    content = _EXPORT_BUILDERS[format](result_rows)
    return Response(
        content=content,
        media_type=_EXPORT_CONTENT_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="run_{run_id}_results.{format}"'},
    )


@app.get("/runs/{run_id}/disclosure")
def get_run_disclosure(run_id: int, engine=Depends(get_engine_dependency)):
    """GUIDE-LLM-shaped AI-use disclosure report for one run -- see
    disclosure.py's docstring for what this covers and why. Read-only,
    derived entirely from what's already persisted (RunRecord,
    ExtractionRecord, the codebook); nothing new to fill in by hand."""
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")
        return build_disclosure(session, run)


class PasteCorpusRequest(BaseModel):
    name: str
    text: str


def _create_documents_or_409(engine, name: str, texts: list[str]) -> dict:
    with Session(engine) as session:
        existing = session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == name)).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"corpus {name!r} already exists")

        inserted = 0
        for text in texts:
            if text:
                session.add(DocumentRecord(corpus_id=name, text=text))
                inserted += 1
        session.commit()

    return {"corpus_id": name, "document_count": inserted}


@app.post("/corpora/paste")
def create_corpus_from_paste(request: PasteCorpusRequest, engine=Depends(get_engine_dependency)):
    return _create_documents_or_409(engine, request.name, [request.text])


def _rows_to_texts(rows: list[dict], text_column: str) -> list[str]:
    if not rows:
        raise HTTPException(status_code=400, detail="file has no data rows")
    if text_column not in rows[0]:
        raise HTTPException(
            status_code=422,
            detail=f"column {text_column!r} not found; available columns: {sorted(rows[0].keys())}",
        )
    return [str(row[text_column]) for row in rows if row.get(text_column)]


@app.post("/corpora/csv")
async def create_corpus_from_csv(
    name: str = Form(...),
    text_column: str = Form(...),
    file: UploadFile = File(...),
    engine=Depends(get_engine_dependency),
):
    content = await file.read()
    try:
        rows = parse_csv_rows(content)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"could not decode file as UTF-8: {exc}") from exc
    texts = _rows_to_texts(rows, text_column)
    return _create_documents_or_409(engine, name, texts)


@app.post("/corpora/xlsx")
async def create_corpus_from_xlsx(
    name: str = Form(...),
    text_column: str = Form(...),
    file: UploadFile = File(...),
    engine=Depends(get_engine_dependency),
):
    content = await file.read()
    try:
        rows = parse_xlsx_rows(content)
    except Exception as exc:  # noqa: BLE001 -- any openpyxl parse failure means "not a valid xlsx"
        raise HTTPException(status_code=400, detail=f"could not parse file as XLSX: {exc}") from exc
    texts = _rows_to_texts(rows, text_column)
    return _create_documents_or_409(engine, name, texts)


@app.get("/corpora")
def list_corpora(engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        documents = session.exec(select(DocumentRecord).order_by(DocumentRecord.id)).all()

    counts: dict[str, int] = {}
    first_created_at: dict[str, datetime] = {}
    for doc in documents:
        counts[doc.corpus_id] = counts.get(doc.corpus_id, 0) + 1
        first_created_at.setdefault(doc.corpus_id, doc.created_at)

    ordered = sorted(counts, key=lambda corpus_id: first_created_at[corpus_id])
    return [{"corpus_id": cid, "document_count": counts[cid]} for cid in ordered]


@app.get("/corpora/{corpus_id}/documents")
def list_corpus_documents(
    corpus_id: str, limit: int = 50, offset: int = 0, engine=Depends(get_engine_dependency)
):
    with Session(engine) as session:
        total = len(session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == corpus_id)).all())
        if total == 0:
            raise HTTPException(status_code=404, detail=f"corpus {corpus_id!r} not found")

        documents = session.exec(
            select(DocumentRecord)
            .where(DocumentRecord.corpus_id == corpus_id)
            .order_by(DocumentRecord.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return [d.model_dump() for d in documents]


class CategorySpec(BaseModel):
    label: str
    definition: str
    positive_examples: list[str] = []
    negative_examples: list[str] = []
    boundary_notes: str = ""


class CodebookSpecRequest(BaseModel):
    concept: str
    description: str
    categories: list[CategorySpec]


@app.post("/codebooks")
def create_codebook(request: CodebookSpecRequest, engine=Depends(get_engine_dependency)):
    spec = request.model_dump()
    try:
        yaml_raw = spec_to_yaml_string(spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with Session(engine) as session:
        record = CodebookRecord(name=request.concept, yaml_raw=yaml_raw)
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"id": record.id, "name": record.name}


@app.get("/codebooks")
def list_codebooks(engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        records = session.exec(select(CodebookRecord).order_by(CodebookRecord.created_at)).all()
        return [{"id": r.id, "name": r.name, "created_at": r.created_at} for r in records]


@app.get("/codebooks/{codebook_id}")
def get_codebook(codebook_id: int, engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        record = session.get(CodebookRecord, codebook_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"codebook {codebook_id} not found")
        return {
            "id": record.id,
            "name": record.name,
            "spec": spec_from_yaml_string(record.yaml_raw),
            "yaml_raw": record.yaml_raw,
        }


@app.put("/codebooks/{codebook_id}")
def update_codebook(codebook_id: int, request: CodebookSpecRequest, engine=Depends(get_engine_dependency)):
    spec = request.model_dump()
    try:
        yaml_raw = spec_to_yaml_string(spec)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    with Session(engine) as session:
        record = session.get(CodebookRecord, codebook_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"codebook {codebook_id} not found")
        record.name = request.concept
        record.yaml_raw = yaml_raw
        session.add(record)
        session.commit()
        return {"id": record.id, "name": record.name}
