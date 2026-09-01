import pytest
from pydantic import BaseModel
from sqlmodel import Session, select

from text_as_data.codebook import Codebook
from text_as_data.db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine
from text_as_data.extraction import ERROR_CATEGORIA, run_extraction
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


class AlwaysFailingProvider(Provider):
    def __init__(self, message: str = "rate limited: 429"):
        self.calls = 0
        self._message = message

    def extract(self, messages, schema):
        self.calls += 1
        raise ValueError(self._message)


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


def test_run_extraction_records_real_error_message_and_still_marks_run_done():
    engine = get_engine("sqlite://")
    run_id, _ = _seed(engine, n_documents=1)
    provider = AlwaysFailingProvider(message="rate limited: 429")

    run_extraction(engine, run_id, provider)

    with Session(engine) as session:
        extractions = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        run = session.get(RunRecord, run_id)
        assert len(extractions) == 1
        assert extractions[0].categoria == ERROR_CATEGORIA
        # The real error message must survive, not a tenacity RetryError wrapper.
        assert extractions[0].justificativa == "rate limited: 429"
        assert "RetryError" not in extractions[0].justificativa
        assert run.status == "done"
    assert provider.calls == 3  # retried up to the stop_after_attempt(3) limit


def test_run_extraction_does_not_treat_error_row_as_cached():
    engine = get_engine("sqlite://")
    run_id, corpus_id = _seed(engine, n_documents=1)
    failing_provider = AlwaysFailingProvider()
    run_extraction(engine, run_id, failing_provider)
    assert failing_provider.calls == 3

    with Session(engine) as session:
        codebook_id = session.exec(select(RunRecord).where(RunRecord.id == run_id)).one().codebook_id
        second_run = RunRecord(codebook_id=codebook_id, corpus_id=corpus_id, model="fake-model")
        session.add(second_run)
        session.commit()
        session.refresh(second_run)
        second_run_id = second_run.id

    succeeding_provider = CountingFakeProvider()
    run_extraction(engine, second_run_id, succeeding_provider)

    # The prior __error__ row must not be reused as a cache hit — the
    # provider must be called again for the second run.
    assert succeeding_provider.calls == 1
    with Session(engine) as session:
        extractions = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == second_run_id)).all()
        assert len(extractions) == 1
        assert extractions[0].categoria == "yes"


def test_run_extraction_records_build_messages_failure_as_error_row_without_crashing(monkeypatch):
    def _raise(self, text):
        raise ValueError("mojibake broke build_messages")

    monkeypatch.setattr(Codebook, "build_messages", _raise)

    engine = get_engine("sqlite://")
    run_id, _ = _seed(engine, n_documents=2)
    provider = CountingFakeProvider()

    run_extraction(engine, run_id, provider)

    with Session(engine) as session:
        extractions = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        run = session.get(RunRecord, run_id)
        # Both documents get an error row instead of crashing the run.
        assert len(extractions) == 2
        assert all(e.categoria == ERROR_CATEGORIA for e in extractions)
        assert all(e.justificativa == "mojibake broke build_messages" for e in extractions)
        assert run.status == "done"  # not stuck at "running"
    # build_messages fails before provider.extract is ever reached, and a
    # build_messages failure must not be pointlessly retried.
    assert provider.calls == 0


def test_run_extraction_raises_clear_error_for_unknown_run_id():
    engine = get_engine("sqlite://")

    with pytest.raises(ValueError, match="unknown run_id"):
        run_extraction(engine, 999, CountingFakeProvider())


def test_run_extraction_marks_run_as_error_on_setup_failure_instead_of_hanging():
    engine = get_engine("sqlite://")
    with Session(engine) as session:
        codebook = CodebookRecord(name="broken", yaml_raw="this is not: [valid, codebook, yaml: at all")
        session.add(codebook)
        session.commit()
        session.refresh(codebook)

        session.add(DocumentRecord(corpus_id="test_corpus", text="document 0"))
        session.commit()

        run = RunRecord(codebook_id=codebook.id, corpus_id="test_corpus", model="fake-model")
        session.add(run)
        session.commit()
        session.refresh(run)
        run_id = run.id

    with pytest.raises(Exception):  # noqa: B017 -- exact exception type is YAML-parser-dependent
        run_extraction(engine, run_id, CountingFakeProvider())

    with Session(engine) as session:
        run = session.get(RunRecord, run_id)
        # Not stuck at "running" forever, and not silently "done" either.
        assert run.status == "error"
