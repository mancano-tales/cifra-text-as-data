from pydantic import BaseModel
from sqlmodel import Session, select

from text_as_data.db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine
from text_as_data.extraction import run_extraction
from text_as_data.providers import Provider

YAML_SOURCE = """
concept: test_concept
description: "A test codebook."
categories:
  - label: yes
    definition: "Positive case."
  - label: no
    definition: "Negative case."
"""


class CountingFakeProvider(Provider):
    def __init__(self):
        self.calls = 0

    def extract(self, messages, schema):
        self.calls += 1
        return schema(categoria="yes", justificativa="because", trecho_evidencia="quote")


def _seed(engine, n_documents: int = 2) -> tuple[int, str]:
    with Session(engine) as session:
        codebook = CodebookRecord(name="test", yaml_raw=YAML_SOURCE)
        session.add(codebook)
        session.commit()
        session.refresh(codebook)

        for i in range(n_documents):
            session.add(DocumentRecord(corpus_id="test_corpus", text=f"document {i}"))
        session.commit()

        run = RunRecord(codebook_id=codebook.id, corpus_id="test_corpus", model="fake-model")
        session.add(run)
        session.commit()
        session.refresh(run)
        return run.id, run.corpus_id


def test_run_extraction_creates_one_extraction_per_document_and_marks_run_done():
    engine = get_engine("sqlite://")
    run_id, _ = _seed(engine, n_documents=2)
    provider = CountingFakeProvider()

    run_extraction(engine, run_id, provider)

    with Session(engine) as session:
        extractions = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        run = session.get(RunRecord, run_id)
        assert len(extractions) == 2
        assert all(e.categoria == "yes" for e in extractions)
        assert run.status == "done"
    assert provider.calls == 2


def test_run_extraction_reuses_cached_extraction_for_same_document_codebook_model():
    engine = get_engine("sqlite://")
    run_id, corpus_id = _seed(engine, n_documents=1)
    provider = CountingFakeProvider()
    run_extraction(engine, run_id, provider)

    with Session(engine) as session:
        codebook_id = session.exec(select(RunRecord).where(RunRecord.id == run_id)).one().codebook_id
        second_run = RunRecord(codebook_id=codebook_id, corpus_id=corpus_id, model="fake-model")
        session.add(second_run)
        session.commit()
        session.refresh(second_run)
        second_run_id = second_run.id

    run_extraction(engine, second_run_id, provider)

    with Session(engine) as session:
        extractions = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == second_run_id)).all()
        assert len(extractions) == 1
    assert provider.calls == 1  # not called again for the second run — cache hit
