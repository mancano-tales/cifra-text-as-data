from __future__ import annotations

from typing import Any

import pandas as pd

from .codebook import Codebook


def extract(
    texts: pd.DataFrame,
    codebook: Codebook,
    client: Any,
    model: str,
    id_col: str = "id",
    text_col: str = "text",
) -> pd.DataFrame:
    """Classify each row of `texts` against `codebook` using an instructor client.

    `client` is an `instructor`-patched LLM client (any provider instructor
    supports). One request is made per row; each response is validated
    against `codebook.schema` before being flattened into the output table.
    """
    rows = []
    for _, row in texts.iterrows():
        result = client.chat.completions.create(
            model=model,
            response_model=codebook.schema,
            messages=codebook.build_messages(row[text_col]),
        )
        rows.append({id_col: row[id_col], **result.model_dump()})
    return pd.DataFrame(rows)


from sqlmodel import Session, select
from tenacity import retry, stop_after_attempt, wait_exponential

from .db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord
from .providers import Provider


ERROR_CATEGORIA = "__error__"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), reraise=True)
def _extract_with_retry(provider: Provider, messages: list[dict], schema):
    return provider.extract(messages, schema)


def run_extraction(engine, run_id: int, provider: Provider) -> None:
    """Execute a run: for every document in the run's corpus, reuse a cached
    extraction if one exists for the same (document, codebook, model), else
    call the provider (with retry) and persist the result. A single
    document's failure is recorded as an error row, not a crash of the
    whole run."""
    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        run.status = "running"
        session.add(run)
        session.commit()

        codebook_record = session.get(CodebookRecord, run.codebook_id)
        codebook = Codebook.from_yaml_string(codebook_record.yaml_raw)
        documents = session.exec(
            select(DocumentRecord).where(DocumentRecord.corpus_id == run.corpus_id)
        ).all()

        for document in documents:
            cached = session.exec(
                select(ExtractionRecord)
                .join(RunRecord, ExtractionRecord.run_id == RunRecord.id)
                .where(
                    ExtractionRecord.document_id == document.id,
                    RunRecord.codebook_id == run.codebook_id,
                    RunRecord.model == run.model,
                    ExtractionRecord.categoria != ERROR_CATEGORIA,
                )
            ).first()

            if cached is not None:
                categoria, justificativa, trecho = cached.categoria, cached.justificativa, cached.trecho_evidencia
            else:
                messages = codebook.build_messages(document.text)
                try:
                    result = _extract_with_retry(provider, messages, codebook.schema)
                    categoria, justificativa, trecho = (
                        result.categoria,
                        result.justificativa,
                        result.trecho_evidencia,
                    )
                except Exception as exc:  # noqa: BLE001 -- one bad document must not kill the run
                    categoria, justificativa, trecho = ERROR_CATEGORIA, str(exc), ""

            session.add(
                ExtractionRecord(
                    run_id=run.id,
                    document_id=document.id,
                    categoria=categoria,
                    justificativa=justificativa,
                    trecho_evidencia=trecho,
                )
            )
            session.commit()

        run.status = "done"
        session.add(run)
        session.commit()
