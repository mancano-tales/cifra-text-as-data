from __future__ import annotations

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine
from .extraction import run_extraction
from .providers import Provider, make_api_key_provider

app = FastAPI(title="Cifra backend (Slice 1)")

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
