from __future__ import annotations

from datetime import datetime

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from .codebook import spec_from_yaml_string, spec_to_yaml_string
from .corpus_import import parse_csv_rows, parse_xlsx_rows
from .db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine
from .extraction import run_extraction
from .providers import Provider, make_api_key_provider

app = FastAPI(title="Cifra backend (Slice 1)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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


def get_provider_dependency(request: CreateRunRequest) -> Provider:
    """Built from the request's own `model`, not a hardcoded constant --
    Slice 1 only supports the Anthropic API-key vendor, but the model
    actually invoked must match what's persisted on the `RunRecord` and
    used as the cache key in `run_extraction`, or both become misleading."""
    return make_api_key_provider(vendor="anthropic", model=request.model)


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

        run = RunRecord(codebook_id=request.codebook_id, corpus_id=request.corpus_id, model=request.model)
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


@app.get("/runs/{run_id}/results")
def get_run_results(run_id: int, engine=Depends(get_engine_dependency)):
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail=f"run {run_id} not found")

        rows = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        return [row.model_dump() for row in rows]


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
