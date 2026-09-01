from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Field, SQLModel, create_engine


class CodebookRecord(SQLModel, table=True):
    __tablename__ = "codebooks"

    id: int | None = Field(default=None, primary_key=True)
    name: str
    yaml_raw: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    corpus_id: str
    text: str
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RunRecord(SQLModel, table=True):
    __tablename__ = "runs"

    id: int | None = Field(default=None, primary_key=True)
    codebook_id: int = Field(foreign_key="codebooks.id")
    corpus_id: str
    model: str
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractionRecord(SQLModel, table=True):
    __tablename__ = "extractions"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    document_id: int = Field(foreign_key="documents.id")
    categoria: str
    justificativa: str
    trecho_evidencia: str
    tokens_used: int | None = None


def get_engine(db_url: str = "sqlite:///codifica.sqlite"):
    is_in_memory = db_url == "sqlite://" or ":memory:" in db_url
    kwargs = {"poolclass": StaticPool} if is_in_memory else {}
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        **kwargs,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    return engine
