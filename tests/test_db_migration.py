"""Regression tests for the additive column migration in db.py's
get_engine() -- the mechanism that fixes the recurring "existing shared
decifra.sqlite doesn't have a column the model now expects" bug (hit twice
already: prompt_sent/raw_response, then provider_mode/provider_detail)."""

import sqlite3
import uuid

from sqlmodel import Session, select

from text_as_data.db import CodebookRecord, RunRecord, get_engine


def _temp_sqlite_url(tmp_path) -> str:
    path = tmp_path / f"{uuid.uuid4().hex}.sqlite"
    return f"sqlite:///{path}"


def test_get_engine_adds_missing_columns_to_an_existing_table(tmp_path):
    url = _temp_sqlite_url(tmp_path)
    raw_path = url.removeprefix("sqlite:///")

    # Simulate a pre-existing DB file created by an older version of the
    # model -- a "runs" table with none of provider_mode/provider_detail.
    connection = sqlite3.connect(raw_path)
    connection.execute(
        "CREATE TABLE runs ("
        "id INTEGER PRIMARY KEY, codebook_id INTEGER, corpus_id TEXT, "
        "model TEXT, status TEXT, created_at TEXT)"
    )
    connection.execute(
        "INSERT INTO runs (codebook_id, corpus_id, model, status, created_at) "
        "VALUES (1, 'old_corpus', 'old-model', 'done', '2026-01-01T00:00:00')"
    )
    connection.commit()
    connection.close()

    # get_engine() must reconcile the old table shape without losing the
    # row already in it, and without requiring a fresh file.
    engine = get_engine(url)

    with Session(engine) as session:
        loaded = session.exec(select(RunRecord).where(RunRecord.corpus_id == "old_corpus")).first()
        assert loaded is not None
        assert loaded.model == "old-model"
        # New columns exist and fall back to their model-declared defaults
        # for a pre-existing row, rather than erroring or being NULL.
        assert loaded.provider_mode == "api_key"
        assert loaded.provider_detail == ""


def test_get_engine_is_idempotent_on_an_already_current_schema(tmp_path):
    url = _temp_sqlite_url(tmp_path)

    # First call creates the schema at its current (already up to date) shape.
    get_engine(url)
    # Second call against the same file must not error re-adding columns
    # that are already there.
    engine = get_engine(url)

    with Session(engine, expire_on_commit=False) as session:
        codebook = CodebookRecord(name="x", yaml_raw="concept: x")
        session.add(codebook)
        session.commit()
        session.refresh(codebook)

        session.add(RunRecord(codebook_id=codebook.id, corpus_id="c", model="m"))
        session.commit()
