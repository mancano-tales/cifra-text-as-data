# Slice 2 — Corpus Import + Codebook Editor Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Codifica backend its first frontend — a Vite+React SPA with two working screens (Corpus import via CSV/XLSX/pasted text, and a structured Codebook editor with a YAML preview) — while keeping every Slice 1 test passing.

**Architecture:** Backend gains `corpus_import.py` (pure CSV/XLSX row-parsing functions), an extended `codebook.py` (spec validation and YAML serialization split out of `_from_spec` so both the YAML loader and the new structured-editor API share one source of truth), and new FastAPI endpoints in `app.py` for `/corpora/*` and `/codebooks/*`, all under `PRAGMA foreign_keys=ON` SQLite with `corpus_id` staying a plain string (no new table — see the design spec's revision note). Frontend is a new `frontend/` Vite+React+TypeScript app talking to the backend via `fetch` against `http://localhost:8000`, enabled by a `CORSMiddleware` allow-listing the Vite dev origin.

**Tech Stack:** Python 3.10+ (existing: FastAPI, SQLModel, openpyxl, pyyaml, pytest), `python-multipart` (new, required by FastAPI file uploads), Node 18+/npm, Vite, React 18, TypeScript.

**Design spec:** `docs/superpowers/specs/2026-09-01-slice-2-corpus-codebook-screens-design.md` — read it first for the full rationale (why this scope, why Vite+React, why no new `corpora` table).

---

## Before you start

Read, in order:
1. `text-as-data/AGENTS.md` — product vision, architecture decisions, codebook YAML format.
2. `text-as-data/docs/superpowers/specs/2026-09-01-slice-2-corpus-codebook-screens-design.md` — this slice's design, including the "no new table" revision.
3. `text-as-data/src/text_as_data/db.py`, `codebook.py`, `app.py` — the exact current code this plan modifies. Do not change `Codebook.build_messages`, `extract()`, `run_extraction`, or the existing `/runs` endpoints' behavior — only add to the surrounding files.

---

## File Structure

- `pyproject.toml` — **modify**: add `python-multipart`.
- `src/text_as_data/db.py` — **modify**: add `created_at` to `DocumentRecord`.
- `src/text_as_data/corpus_import.py` — **create**: `parse_csv_rows`, `parse_xlsx_rows`.
- `src/text_as_data/codebook.py` — **modify**: extract `validate_spec`, add `spec_to_yaml_string`, `spec_from_yaml_string`.
- `src/text_as_data/app.py` — **modify**: CORS, `/corpora/*` endpoints, `/codebooks/*` endpoints.
- `tests/test_corpus_import.py` — **create**.
- `tests/test_codebook_yaml.py` — **modify**: add tests for the new spec functions.
- `tests/test_db.py` — **modify**: add a `created_at` regression test.
- `tests/test_app_corpora.py` — **create**.
- `tests/test_app_codebooks.py` — **create**.
- `frontend/` — **create**: Vite+React+TS scaffold, `src/api.ts`, `src/CorpusPage.tsx`, `src/CodebookEditor.tsx`, `src/App.tsx`.
- `.gitignore` — **modify**: add `frontend/node_modules/`, `frontend/dist/`.
- `TODO.md`, `NEWS.md` — **modify**: close out the Slice 2 pending item.

---

## Task 1: Add `python-multipart` dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add `"python-multipart>=0.0.9",` to the `dependencies` list (any position — alphabetical isn't currently enforced in this file).

- [ ] **Step 2: Install**

Run: `pip install -e ".[dev]"`
Expected: installs without error; `python -c "import multipart"` prints nothing and exits 0.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add python-multipart (required for FastAPI file uploads)"
```

---

## Task 2: `DocumentRecord.created_at`

**Files:**
- Modify: `src/text_as_data/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_db.py` (below the existing tests):

```python
from datetime import datetime


def test_document_created_at_defaults_to_a_real_timestamp():
    engine = get_engine("sqlite://")

    with Session(engine, expire_on_commit=False) as session:
        document = DocumentRecord(corpus_id="test_corpus", text="hello")
        session.add(document)
        session.commit()
        session.refresh(document)

    assert isinstance(document.created_at, datetime)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py::test_document_created_at_defaults_to_a_real_timestamp -v`
Expected: FAIL with `AttributeError: 'DocumentRecord' object has no attribute 'created_at'`

- [ ] **Step 3: Add the column**

In `src/text_as_data/db.py`, modify `DocumentRecord`:

```python
class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    corpus_id: str
    text: str
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

(`datetime`/`timezone` are already imported at the top of `db.py` for `CodebookRecord.created_at` — no new import needed.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: all pass (4 tests)

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all existing tests still pass — this is a purely additive column.

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/db.py tests/test_db.py
git commit -m "feat: add created_at to DocumentRecord"
```

---

## Task 3: `corpus_import.py` — pure CSV/XLSX row parsing

**Files:**
- Create: `src/text_as_data/corpus_import.py`
- Test: `tests/test_corpus_import.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_corpus_import.py`:

```python
import io

import openpyxl

from text_as_data.corpus_import import parse_csv_rows, parse_xlsx_rows


def test_parse_csv_rows_reads_header_and_rows():
    content = "title,body\nA,First doc\nB,Second doc\n".encode("utf-8")

    rows = parse_csv_rows(content)

    assert rows == [
        {"title": "A", "body": "First doc"},
        {"title": "B", "body": "Second doc"},
    ]


def test_parse_csv_rows_strips_utf8_bom_from_the_first_header():
    content = "﻿title,body\nA,First doc\n".encode("utf-8")

    rows = parse_csv_rows(content)

    assert rows == [{"title": "A", "body": "First doc"}]


def _make_xlsx_bytes(rows: list[list]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parse_xlsx_rows_reads_header_and_rows():
    content = _make_xlsx_bytes([["title", "body"], ["A", "First doc"], ["B", "Second doc"]])

    rows = parse_xlsx_rows(content)

    assert rows == [
        {"title": "A", "body": "First doc"},
        {"title": "B", "body": "Second doc"},
    ]


def test_parse_xlsx_rows_skips_blank_trailing_rows():
    content = _make_xlsx_bytes([["title", "body"], ["A", "First doc"], [None, None]])

    rows = parse_xlsx_rows(content)

    assert len(rows) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_corpus_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'text_as_data.corpus_import'`

- [ ] **Step 3: Implement**

Create `src/text_as_data/corpus_import.py`:

```python
from __future__ import annotations

import csv
import io

import openpyxl


def parse_csv_rows(content: bytes) -> list[dict]:
    """Parse CSV bytes into row dicts keyed by the file's own header row.

    Decodes with `utf-8-sig` so a file exported from Excel with a leading
    byte-order mark doesn't corrupt the first header name into
    `'\\ufefftitle'`.
    """
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def parse_xlsx_rows(content: bytes) -> list[dict]:
    """Parse XLSX bytes into row dicts keyed by the active sheet's header
    row (its first row). Skips rows whose first cell is empty -- the same
    trailing-blank-row guard `scripts/import_v7_pilot.py` uses.
    """
    workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    worksheet = workbook.active
    rows_iter = worksheet.iter_rows(values_only=True)
    header = next(rows_iter)
    rows = []
    for values in rows_iter:
        row = dict(zip(header, values))
        if row.get(header[0]) is None:
            continue
        rows.append(row)
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_corpus_import.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/corpus_import.py tests/test_corpus_import.py
git commit -m "feat: add CSV/XLSX row-parsing functions for corpus import"
```

---

## Task 4: `codebook.py` — shared spec validation + YAML round-trip

**Files:**
- Modify: `src/text_as_data/codebook.py`
- Test: `tests/test_codebook_yaml.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_codebook_yaml.py`:

```python
from text_as_data.codebook import spec_from_yaml_string, spec_to_yaml_string, validate_spec

VALID_SPEC = {
    "concept": "protest",
    "description": "A collective, public event.",
    "categories": [
        {"label": "protest", "definition": "An occupation, march, or strike."},
        {"label": "not_protest", "definition": "Any event that does not meet the criteria above."},
    ],
}


def test_validate_spec_accepts_a_valid_spec():
    validate_spec(VALID_SPEC)  # must not raise


def test_validate_spec_rejects_duplicate_labels():
    bad_spec = {**VALID_SPEC, "categories": [VALID_SPEC["categories"][0], VALID_SPEC["categories"][0]]}
    with pytest.raises(ValueError, match="duplicate category label"):
        validate_spec(bad_spec)


def test_validate_spec_rejects_missing_concept():
    bad_spec = {k: v for k, v in VALID_SPEC.items() if k != "concept"}
    with pytest.raises(ValueError, match="missing required field"):
        validate_spec(bad_spec)


def test_validate_spec_rejects_category_missing_definition():
    bad_spec = {**VALID_SPEC, "categories": [{"label": "protest"}]}
    with pytest.raises(ValueError, match="missing required field"):
        validate_spec(bad_spec)


def test_spec_to_yaml_string_then_spec_from_yaml_string_round_trips():
    yaml_text = spec_to_yaml_string(VALID_SPEC)

    round_tripped = spec_from_yaml_string(yaml_text)

    assert round_tripped == VALID_SPEC


def test_spec_to_yaml_string_rejects_invalid_spec():
    bad_spec = {**VALID_SPEC, "categories": []}
    with pytest.raises(ValueError, match="at least one category"):
        spec_to_yaml_string(bad_spec)


def test_codebook_from_yaml_string_works_on_output_of_spec_to_yaml_string():
    yaml_text = spec_to_yaml_string(VALID_SPEC)

    codebook = Codebook.from_yaml_string(yaml_text)

    assert set(codebook.schema.model_fields["categoria"].annotation.__args__) == {"protest", "not_protest"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_codebook_yaml.py -v`
Expected: FAIL with `ImportError: cannot import name 'spec_from_yaml_string'` (or similar for `spec_to_yaml_string`/`validate_spec`)

- [ ] **Step 3: Refactor `codebook.py`**

Replace the full contents of `src/text_as_data/codebook.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import yaml
from pydantic import BaseModel, Field, create_model


class _CodebookYamlLoader(yaml.SafeLoader):
    """SafeLoader with the YAML 1.1 implicit-bool resolver disabled.

    Without this, unquoted category labels like `yes`/`no`/`on`/`off` (in
    any case) are parsed by PyYAML as Python booleans instead of strings,
    which silently corrupts labels and only surfaces later as a confusing
    Pydantic error. Codebook authors shouldn't have to know to quote
    reserved words, so we strip the bool resolver here instead.
    """


_CodebookYamlLoader.yaml_implicit_resolvers = {
    key: [resolver for resolver in resolvers if resolver[0] != "tag:yaml.org,2002:bool"]
    for key, resolvers in _CodebookYamlLoader.yaml_implicit_resolvers.items()
}


def validate_spec(spec: dict) -> None:
    """Validate a codebook spec dict -- the shared shape used by both the
    YAML file format and the structured codebook-editor API. Raises
    `ValueError` with a human-readable message on the first problem found.
    Both `Codebook.from_yaml_string` and `spec_to_yaml_string` call this,
    so the YAML format and the editor's JSON body can never validate
    differently."""
    if not spec.get("concept"):
        raise ValueError("codebook spec missing required field: 'concept'")
    if not spec.get("description"):
        raise ValueError("codebook spec missing required field: 'description'")
    if not spec.get("categories"):
        raise ValueError("codebook must define at least one category")

    labels = []
    for category in spec["categories"]:
        if not category.get("label"):
            raise ValueError("codebook category missing required field: 'label'")
        if not category.get("definition"):
            raise ValueError(f"category {category.get('label')!r} missing required field: 'definition'")
        labels.append(category["label"])

    if len(set(labels)) != len(labels):
        raise ValueError(f"duplicate category label in codebook: {labels}")


def spec_from_yaml_string(source: str) -> dict:
    """Parse codebook YAML text into a spec dict, using the bool-safe
    loader. Used by both `Codebook.from_yaml_string` and by `app.py` to
    read a stored codebook's spec back for the editor's edit form."""
    return yaml.load(source, Loader=_CodebookYamlLoader)


def spec_to_yaml_string(spec: dict) -> str:
    """Serialize a codebook spec dict to YAML text in the same shape
    `spec_from_yaml_string` reads back. Validates first, so a caller never
    persists an invalid spec as if it were valid YAML."""
    validate_spec(spec)
    return yaml.safe_dump(spec, allow_unicode=True, sort_keys=False)


@dataclass
class Codebook:
    """A theoretical construct operationalized as an LLM-extractable schema.

    A codebook bundles three things that must travel together: the output
    schema (what columns end up in the structured table), the instructions
    (the theoretical definition of each category — the part a domain expert
    actually authors), and a handful of worked examples (few-shot) that pin
    down edge cases the instructions alone tend to leave ambiguous.
    """

    schema: type[BaseModel]
    instructions: str
    examples: list[dict] = field(default_factory=list)

    def build_messages(self, text: str) -> list[dict]:
        system = (
            "You are a careful annotator applying a fixed coding scheme. "
            "Follow the instructions below exactly as written, even when a "
            "case looks similar to a more common or generic concept. Do not "
            "substitute your own default definition for the one given.\n\n"
            f"{self.instructions}"
        )
        messages = [{"role": "system", "content": system}]
        for example in self.examples:
            messages.append({"role": "user", "content": example["text"]})
            messages.append(
                {"role": "assistant", "content": example["output"].model_dump_json()}
                if isinstance(example["output"], BaseModel)
                else {"role": "assistant", "content": str(example["output"])}
            )
        messages.append({"role": "user", "content": text})
        return messages

    @classmethod
    def from_yaml_string(cls, source: str) -> "Codebook":
        spec = spec_from_yaml_string(source)
        return cls._from_spec(spec)

    @classmethod
    def from_yaml_file(cls, path: str) -> "Codebook":
        with open(path, encoding="utf-8") as f:
            return cls.from_yaml_string(f.read())

    @classmethod
    def _from_spec(cls, spec: dict) -> "Codebook":
        validate_spec(spec)

        # Fixed contract: `categoria`/`justificativa`/`trecho_evidencia` are
        # relied on by exact field name elsewhere (e.g. db.py's
        # ExtractionRecord, run_extraction) — renaming here breaks those
        # call sites silently via AttributeError, not at this layer.
        labels = [c["label"] for c in spec["categories"]]
        schema = create_model(
            "CodebookExtraction",
            categoria=(Literal[tuple(labels)], Field(description="One of the codebook's category labels.")),
            justificativa=(str, Field(description="Free-text rationale for the chosen category.")),
            trecho_evidencia=(
                str,
                Field(description="Verbatim quote from the document that grounds the decision."),
            ),
        )

        lines = [f"Concept: {spec['concept']}", spec["description"].strip(), "", "Categories:"]
        for c in spec["categories"]:
            lines.append(f"- {c['label']}: {c['definition'].strip()}")
            for ex in c.get("positive_examples", []):
                lines.append(f'  Positive example: "{ex}"')
            for ex in c.get("negative_examples", []):
                lines.append(f'  Negative example: "{ex}"')
            if c.get("boundary_notes"):
                lines.append(f"  Boundary notes: {c['boundary_notes'].strip()}")
        instructions = "\n".join(lines)

        return cls(schema=schema, instructions=instructions)
```

Note: the previous `KeyError`-catching `try/except` in `_from_spec` is gone — `validate_spec` now checks every required field up front and raises `ValueError` directly, so there's no `KeyError` path left to catch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_codebook_yaml.py -v`
Expected: all pass (13 tests: 6 original + 7 new)

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass — `_from_spec`'s observable behavior (schema shape, instructions text, error messages) is unchanged, only its internals moved into `validate_spec`.

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/codebook.py tests/test_codebook_yaml.py
git commit -m "refactor: extract validate_spec/spec_to_yaml_string from Codebook._from_spec"
```

---

## Task 5: `app.py` — corpus import endpoints

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_corpora.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_corpora.py`:

```python
import io

import openpyxl
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from text_as_data.app import app, get_engine_dependency
from text_as_data.db import DocumentRecord, get_engine


def _make_test_client():
    engine = get_engine("sqlite://")
    app.dependency_overrides[get_engine_dependency] = lambda: engine
    return TestClient(app), engine


def _make_xlsx_bytes(rows: list[list]) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_paste_creates_one_document_corpus():
    client, engine = _make_test_client()

    response = client.post("/corpora/paste", json={"name": "my_notes", "text": "some pasted text"})

    assert response.status_code == 200
    assert response.json() == {"corpus_id": "my_notes", "document_count": 1}
    with Session(engine) as session:
        docs = session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == "my_notes")).all()
        assert len(docs) == 1
        assert docs[0].text == "some pasted text"


def test_paste_rejects_duplicate_corpus_name():
    client, _ = _make_test_client()
    client.post("/corpora/paste", json={"name": "dup", "text": "first"})

    response = client.post("/corpora/paste", json={"name": "dup", "text": "second"})

    assert response.status_code == 409


def test_csv_upload_creates_documents_from_text_column():
    client, engine = _make_test_client()
    csv_content = b"title,body\nA,First doc\nB,Second doc\n"

    response = client.post(
        "/corpora/csv",
        data={"name": "articles", "text_column": "body"},
        files={"file": ("articles.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    assert response.json() == {"corpus_id": "articles", "document_count": 2}
    with Session(engine) as session:
        docs = session.exec(select(DocumentRecord).where(DocumentRecord.corpus_id == "articles")).all()
        assert sorted(d.text for d in docs) == ["First doc", "Second doc"]


def test_csv_upload_rejects_unknown_text_column():
    client, _ = _make_test_client()
    csv_content = b"title,body\nA,First doc\n"

    response = client.post(
        "/corpora/csv",
        data={"name": "articles", "text_column": "nope"},
        files={"file": ("articles.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 422


def test_xlsx_upload_creates_documents_from_text_column():
    client, engine = _make_test_client()
    xlsx_content = _make_xlsx_bytes([["title", "body"], ["A", "First doc"], ["B", "Second doc"]])

    response = client.post(
        "/corpora/xlsx",
        data={"name": "spreadsheet_corpus", "text_column": "body"},
        files={
            "file": (
                "corpus.xlsx",
                xlsx_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {"corpus_id": "spreadsheet_corpus", "document_count": 2}


def test_xlsx_upload_rejects_corrupt_file():
    client, _ = _make_test_client()

    response = client.post(
        "/corpora/xlsx",
        data={"name": "broken", "text_column": "body"},
        files={"file": ("broken.xlsx", b"not a real xlsx file", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_list_corpora_returns_counts_ordered_by_creation():
    client, _ = _make_test_client()
    client.post("/corpora/paste", json={"name": "first", "text": "a"})
    client.post("/corpora/paste", json={"name": "second", "text": "b"})
    client.post(
        "/corpora/csv",
        data={"name": "third", "text_column": "body"},
        files={"file": ("f.csv", b"body\nx\ny\n", "text/csv")},
    )

    response = client.get("/corpora")

    assert response.status_code == 200
    assert response.json() == [
        {"corpus_id": "first", "document_count": 1},
        {"corpus_id": "second", "document_count": 1},
        {"corpus_id": "third", "document_count": 2},
    ]


def test_list_corpus_documents_paginates():
    client, _ = _make_test_client()
    csv_content = b"body\nrow0\nrow1\nrow2\n"
    client.post(
        "/corpora/csv",
        data={"name": "paged", "text_column": "body"},
        files={"file": ("f.csv", csv_content, "text/csv")},
    )

    response = client.get("/corpora/paged/documents?limit=2&offset=1")

    assert response.status_code == 200
    assert [d["text"] for d in response.json()] == ["row1", "row2"]


def test_list_corpus_documents_404_for_unknown_corpus():
    client, _ = _make_test_client()

    response = client.get("/corpora/does-not-exist/documents")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_corpora.py -v`
Expected: FAIL — `404` on all of them (routes don't exist yet), since a real 404 has a different response body shape than what the tests assert.

- [ ] **Step 3: Add CORS and the corpus endpoints to `app.py`**

Modify `src/text_as_data/app.py`. Add these imports at the top (alongside the existing ones):

```python
from datetime import datetime

from fastapi import File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .corpus_import import parse_csv_rows, parse_xlsx_rows
```

Right after `app = FastAPI(title="Codifica backend (Slice 1)")`, add:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Add these new request models near `CreateRunRequest`:

```python
class PasteCorpusRequest(BaseModel):
    name: str
    text: str
```

Add these endpoints (anywhere after the dependency functions, e.g. right before `@app.post("/runs")`):

```python
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
```

`first_created_at.setdefault(...)` relies on `documents` already being in `id` order (the query's `order_by(DocumentRecord.id)`), so the first document seen per `corpus_id` is genuinely its earliest one — this also makes the ordering deterministic even if two documents land on the exact same `created_at` timestamp.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_corpora.py -v`
Expected: 9 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_corpora.py
git commit -m "feat: add corpus import endpoints (paste, CSV, XLSX) and CORS"
```

---

## Task 6: `app.py` — codebook editor endpoints

**Files:**
- Modify: `src/text_as_data/app.py`
- Test: `tests/test_app_codebooks.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_codebooks.py`:

```python
import yaml
from fastapi.testclient import TestClient

from text_as_data.app import app, get_engine_dependency
from text_as_data.db import get_engine

VALID_SPEC = {
    "concept": "protest",
    "description": "A collective, public event.",
    "categories": [
        {
            "label": "protest",
            "definition": "An occupation, march, or strike.",
            "positive_examples": ["200 people occupied the square."],
        },
        {"label": "not_protest", "definition": "Any event that does not meet the criteria above."},
    ],
}


def _make_test_client():
    engine = get_engine("sqlite://")
    app.dependency_overrides[get_engine_dependency] = lambda: engine
    return TestClient(app)


def test_create_codebook_then_get_it_back():
    client = _make_test_client()

    create_response = client.post("/codebooks", json=VALID_SPEC)
    assert create_response.status_code == 200
    codebook_id = create_response.json()["id"]

    get_response = client.get(f"/codebooks/{codebook_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["name"] == "protest"
    assert body["spec"]["concept"] == "protest"
    assert [c["label"] for c in body["spec"]["categories"]] == ["protest", "not_protest"]
    assert yaml.safe_load(body["yaml_raw"])["concept"] == "protest"


def test_create_codebook_rejects_duplicate_labels():
    client = _make_test_client()
    bad_spec = {**VALID_SPEC, "categories": [VALID_SPEC["categories"][0], VALID_SPEC["categories"][0]]}

    response = client.post("/codebooks", json=bad_spec)

    assert response.status_code == 422


def test_list_codebooks_returns_created_ones():
    client = _make_test_client()
    client.post("/codebooks", json=VALID_SPEC)

    response = client.get("/codebooks")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "protest"


def test_get_unknown_codebook_returns_404():
    client = _make_test_client()

    response = client.get("/codebooks/999")

    assert response.status_code == 404


def test_update_codebook_overwrites_spec_and_yaml():
    client = _make_test_client()
    codebook_id = client.post("/codebooks", json=VALID_SPEC).json()["id"]
    updated_spec = {**VALID_SPEC, "description": "An updated description."}

    response = client.put(f"/codebooks/{codebook_id}", json=updated_spec)

    assert response.status_code == 200
    body = client.get(f"/codebooks/{codebook_id}").json()
    assert body["spec"]["description"] == "An updated description."


def test_update_unknown_codebook_returns_404():
    client = _make_test_client()

    response = client.put("/codebooks/999", json=VALID_SPEC)

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_codebooks.py -v`
Expected: FAIL (404s / KeyErrors — routes don't exist yet)

- [ ] **Step 3: Add the codebook endpoints to `app.py`**

Add this import at the top of `src/text_as_data/app.py`:

```python
from .codebook import spec_from_yaml_string, spec_to_yaml_string
```

Add these request/response models near `PasteCorpusRequest`:

```python
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
```

Add these endpoints (after the corpus endpoints from Task 5):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app_codebooks.py -v`
Expected: 6 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass (Slice 1 + Task 1-6 tests, ~40+ total)

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app_codebooks.py
git commit -m "feat: add codebook editor endpoints (create, list, get, update)"
```

---

## Task 7: Frontend scaffold

**Files:**
- Create: `frontend/` (Vite scaffold)
- Modify: `.gitignore`

- [ ] **Step 1: Scaffold the Vite+React+TypeScript app**

From the repo root (`text-as-data/`):

```bash
npm create vite@latest frontend -- --template react-ts
```

Expected: creates `frontend/` with `package.json`, `src/`, `index.html`, `vite.config.ts`, `tsconfig.json`, etc. (non-interactive because `--template` is passed).

- [ ] **Step 2: Install dependencies**

```bash
cd frontend && npm install
```

Expected: `frontend/node_modules/` and `frontend/package-lock.json` created, no errors.

- [ ] **Step 3: Ignore generated frontend files**

Add to `.gitignore` (repo root):

```
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 4: Verify the default scaffold runs**

From `frontend/`: `npm run dev`
Expected: prints a `Local: http://localhost:5173/` URL. Stop it (Ctrl+C) once confirmed — the next tasks replace the default page content before it's run again for real verification in Task 11.

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend .gitignore
git commit -m "build: scaffold frontend/ with Vite + React + TypeScript"
```

(`.gitignore` was already updated in Step 3 to exclude `frontend/node_modules/` and `frontend/dist/`, so `git add frontend` only picks up scaffold source files.)

(The default Vite scaffold has no test suite and no lint step wired to CI in this repo yet — matches the design spec's "no automated frontend tests this slice" decision. `npm run build` in Task 11's verification step is the closest thing to an automated check: it fails on any TypeScript error.)

---

## Task 8: `frontend/src/api.ts` — backend client

**Files:**
- Create: `frontend/src/api.ts`

- [ ] **Step 1: Write the API client**

Create `frontend/src/api.ts`:

```typescript
const API_BASE = "http://localhost:8000";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? `request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export interface CorpusSummary {
  corpus_id: string;
  document_count: number;
}

export async function listCorpora(): Promise<CorpusSummary[]> {
  const response = await fetch(`${API_BASE}/corpora`);
  return handleResponse(response);
}

export async function createCorpusFromPaste(name: string, text: string): Promise<CorpusSummary> {
  const response = await fetch(`${API_BASE}/corpora/paste`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, text }),
  });
  return handleResponse(response);
}

async function uploadCorpusFile(
  endpoint: "csv" | "xlsx",
  name: string,
  textColumn: string,
  file: File
): Promise<CorpusSummary> {
  const formData = new FormData();
  formData.append("name", name);
  formData.append("text_column", textColumn);
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/corpora/${endpoint}`, { method: "POST", body: formData });
  return handleResponse(response);
}

export const createCorpusFromCsv = (name: string, textColumn: string, file: File) =>
  uploadCorpusFile("csv", name, textColumn, file);

export const createCorpusFromXlsx = (name: string, textColumn: string, file: File) =>
  uploadCorpusFile("xlsx", name, textColumn, file);

export interface CategorySpec {
  label: string;
  definition: string;
  positive_examples: string[];
  negative_examples: string[];
  boundary_notes: string;
}

export interface CodebookSpec {
  concept: string;
  description: string;
  categories: CategorySpec[];
}

export interface CodebookSummary {
  id: number;
  name: string;
  created_at: string;
}

export interface CodebookDetail {
  id: number;
  name: string;
  spec: CodebookSpec;
  yaml_raw: string;
}

export async function listCodebooks(): Promise<CodebookSummary[]> {
  const response = await fetch(`${API_BASE}/codebooks`);
  return handleResponse(response);
}

export async function getCodebook(id: number): Promise<CodebookDetail> {
  const response = await fetch(`${API_BASE}/codebooks/${id}`);
  return handleResponse(response);
}

export async function createCodebook(spec: CodebookSpec): Promise<{ id: number; name: string }> {
  const response = await fetch(`${API_BASE}/codebooks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  return handleResponse(response);
}

export async function updateCodebook(id: number, spec: CodebookSpec): Promise<{ id: number; name: string }> {
  const response = await fetch(`${API_BASE}/codebooks/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(spec),
  });
  return handleResponse(response);
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc --noEmit`
Expected: no errors (the default scaffold's `App.tsx` still exists and type-checks fine at this point too).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "feat: add frontend API client for corpora and codebooks endpoints"
```

---

## Task 9: `frontend/src/CorpusPage.tsx`

**Files:**
- Create: `frontend/src/CorpusPage.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/CorpusPage.tsx`:

```tsx
import { FormEvent, useEffect, useState } from "react";
import { CorpusSummary, createCorpusFromCsv, createCorpusFromPaste, createCorpusFromXlsx, listCorpora } from "./api";

export function CorpusPage() {
  const [corpora, setCorpora] = useState<CorpusSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [pasteName, setPasteName] = useState("");
  const [pasteText, setPasteText] = useState("");

  const [csvName, setCsvName] = useState("");
  const [csvColumn, setCsvColumn] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);

  const [xlsxName, setXlsxName] = useState("");
  const [xlsxColumn, setXlsxColumn] = useState("");
  const [xlsxFile, setXlsxFile] = useState<File | null>(null);

  async function refresh() {
    try {
      setCorpora(await listCorpora());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handlePaste(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await createCorpusFromPaste(pasteName, pasteText);
      setPasteName("");
      setPasteText("");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleCsv(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!csvFile) return;
    try {
      await createCorpusFromCsv(csvName, csvColumn, csvFile);
      setCsvName("");
      setCsvColumn("");
      setCsvFile(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleXlsx(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!xlsxFile) return;
    try {
      await createCorpusFromXlsx(xlsxName, xlsxColumn, xlsxFile);
      setXlsxName("");
      setXlsxColumn("");
      setXlsxFile(null);
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div>
      <h2>Corpus</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <h3>Existing corpora</h3>
      <ul>
        {corpora.map((c) => (
          <li key={c.corpus_id}>
            {c.corpus_id} ({c.document_count} documents)
          </li>
        ))}
      </ul>

      <h3>Paste text</h3>
      <form onSubmit={handlePaste}>
        <input
          placeholder="corpus name"
          value={pasteName}
          onChange={(e) => setPasteName(e.target.value)}
          required
        />
        <br />
        <textarea placeholder="text" value={pasteText} onChange={(e) => setPasteText(e.target.value)} required />
        <br />
        <button type="submit">Add</button>
      </form>

      <h3>Upload CSV</h3>
      <form onSubmit={handleCsv}>
        <input placeholder="corpus name" value={csvName} onChange={(e) => setCsvName(e.target.value)} required />
        <input
          placeholder="text column name"
          value={csvColumn}
          onChange={(e) => setCsvColumn(e.target.value)}
          required
        />
        <input type="file" accept=".csv" onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)} required />
        <button type="submit">Upload</button>
      </form>

      <h3>Upload XLSX</h3>
      <form onSubmit={handleXlsx}>
        <input placeholder="corpus name" value={xlsxName} onChange={(e) => setXlsxName(e.target.value)} required />
        <input
          placeholder="text column name"
          value={xlsxColumn}
          onChange={(e) => setXlsxColumn(e.target.value)}
          required
        />
        <input type="file" accept=".xlsx" onChange={(e) => setXlsxFile(e.target.files?.[0] ?? null)} required />
        <button type="submit">Upload</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc --noEmit`
Expected: no errors (this file isn't imported by `App.tsx` yet, but `tsc --noEmit` checks every `.ts`/`.tsx` file in the project regardless).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/CorpusPage.tsx
git commit -m "feat: add Corpus screen (paste text, CSV upload, XLSX upload)"
```

---

## Task 10: `frontend/src/CodebookEditor.tsx`

**Files:**
- Create: `frontend/src/CodebookEditor.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/CodebookEditor.tsx`:

```tsx
import { FormEvent, useEffect, useState } from "react";
import {
  CategorySpec,
  CodebookSpec,
  CodebookSummary,
  createCodebook,
  getCodebook,
  listCodebooks,
  updateCodebook,
} from "./api";

const EMPTY_CATEGORY: CategorySpec = {
  label: "",
  definition: "",
  positive_examples: [],
  negative_examples: [],
  boundary_notes: "",
};

function emptySpec(): CodebookSpec {
  return { concept: "", description: "", categories: [{ ...EMPTY_CATEGORY }] };
}

export function CodebookEditor() {
  const [codebooks, setCodebooks] = useState<CodebookSummary[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [spec, setSpec] = useState<CodebookSpec>(emptySpec());
  const [yamlPreview, setYamlPreview] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refreshList() {
    try {
      setCodebooks(await listCodebooks());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  useEffect(() => {
    refreshList();
  }, []);

  async function loadCodebook(id: number) {
    setError(null);
    try {
      const detail = await getCodebook(id);
      setEditingId(detail.id);
      setSpec({
        concept: detail.spec.concept,
        description: detail.spec.description,
        categories: detail.spec.categories.map((c) => ({
          label: c.label,
          definition: c.definition,
          positive_examples: c.positive_examples ?? [],
          negative_examples: c.negative_examples ?? [],
          boundary_notes: c.boundary_notes ?? "",
        })),
      });
      setYamlPreview(detail.yaml_raw);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function startNew() {
    setEditingId(null);
    setSpec(emptySpec());
    setYamlPreview(null);
  }

  function updateCategoryField(index: number, patch: Partial<CategorySpec>) {
    setSpec((prev) => {
      const categories = [...prev.categories];
      categories[index] = { ...categories[index], ...patch };
      return { ...prev, categories };
    });
  }

  function addCategory() {
    setSpec((prev) => ({ ...prev, categories: [...prev.categories, { ...EMPTY_CATEGORY }] }));
  }

  function removeCategory(index: number) {
    setSpec((prev) => ({ ...prev, categories: prev.categories.filter((_, i) => i !== index) }));
  }

  function parseExampleList(raw: string): string[] {
    return raw.split("\n").filter((line) => line.trim() !== "");
  }

  async function handleSave(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const result = editingId ? await updateCodebook(editingId, spec) : await createCodebook(spec);
      const detail = await getCodebook(result.id);
      setEditingId(detail.id);
      setYamlPreview(detail.yaml_raw);
      await refreshList();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div>
      <h2>Codebook</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}

      <div style={{ display: "flex", gap: "2rem", alignItems: "flex-start" }}>
        <div>
          <h3>Existing codebooks</h3>
          <button type="button" onClick={startNew}>
            + New codebook
          </button>
          <ul>
            {codebooks.map((c) => (
              <li key={c.id}>
                <button type="button" onClick={() => loadCodebook(c.id)}>
                  {c.name}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <form onSubmit={handleSave} style={{ flex: 1 }}>
          <label>
            Concept
            <br />
            <input
              value={spec.concept}
              onChange={(e) => setSpec((prev) => ({ ...prev, concept: e.target.value }))}
              required
            />
          </label>
          <br />
          <label>
            Description
            <br />
            <textarea
              value={spec.description}
              onChange={(e) => setSpec((prev) => ({ ...prev, description: e.target.value }))}
              required
            />
          </label>

          <h3>Categories</h3>
          {spec.categories.map((category, index) => (
            <fieldset key={index}>
              <legend>Category {index + 1}</legend>
              <label>
                Label
                <br />
                <input
                  value={category.label}
                  onChange={(e) => updateCategoryField(index, { label: e.target.value })}
                  required
                />
              </label>
              <br />
              <label>
                Definition
                <br />
                <textarea
                  value={category.definition}
                  onChange={(e) => updateCategoryField(index, { definition: e.target.value })}
                  required
                />
              </label>
              <br />
              <label>
                Positive examples (one per line)
                <br />
                <textarea
                  value={category.positive_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { positive_examples: parseExampleList(e.target.value) })
                  }
                />
              </label>
              <br />
              <label>
                Negative examples (one per line)
                <br />
                <textarea
                  value={category.negative_examples.join("\n")}
                  onChange={(e) =>
                    updateCategoryField(index, { negative_examples: parseExampleList(e.target.value) })
                  }
                />
              </label>
              <br />
              <label>
                Boundary notes
                <br />
                <textarea
                  value={category.boundary_notes}
                  onChange={(e) => updateCategoryField(index, { boundary_notes: e.target.value })}
                />
              </label>
              <br />
              {spec.categories.length > 1 && (
                <button type="button" onClick={() => removeCategory(index)}>
                  Remove category
                </button>
              )}
            </fieldset>
          ))}
          <button type="button" onClick={addCategory}>
            + Add category
          </button>

          <div>
            <button type="submit">{editingId ? "Save changes" : "Create codebook"}</button>
          </div>
        </form>

        {yamlPreview && (
          <div>
            <h3>YAML preview</h3>
            <pre>{yamlPreview}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify it type-checks**

From `frontend/`: `npx tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/CodebookEditor.tsx
git commit -m "feat: add Codebook editor screen (structured form + YAML preview)"
```

---

## Task 11: Wire up `App.tsx` and verify end-to-end in the browser

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Replace the default scaffold's `App.tsx`**

Replace the full contents of `frontend/src/App.tsx` with:

```tsx
import { useState } from "react";
import { CodebookEditor } from "./CodebookEditor";
import { CorpusPage } from "./CorpusPage";

type Tab = "corpus" | "codebook";

function App() {
  const [tab, setTab] = useState<Tab>("corpus");

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto", padding: "1rem" }}>
      <h1>Codifica</h1>
      <nav>
        <button onClick={() => setTab("corpus")} disabled={tab === "corpus"}>
          Corpus
        </button>{" "}
        <button onClick={() => setTab("codebook")} disabled={tab === "codebook"}>
          Codebook
        </button>
      </nav>
      {tab === "corpus" ? <CorpusPage /> : <CodebookEditor />}
    </div>
  );
}

export default App;
```

- [ ] **Step 2: Verify the whole frontend builds**

From `frontend/`: `npm run build`
Expected: `tsc -b && vite build` (or similar, per the scaffold's `package.json` script) completes with no TypeScript errors and writes `frontend/dist/`.

- [ ] **Step 3: Start the backend**

From the repo root, in one terminal: `uvicorn text_as_data.app:app --reload --port 8000`
Expected: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 4: Start the frontend dev server**

From `frontend/`, in a second terminal: `npm run dev`
Expected: `Local: http://localhost:5173/`

- [ ] **Step 5: Manually verify the Corpus screen in a browser**

Open `http://localhost:5173`. On the Corpus tab:
1. Paste some text with a corpus name (e.g. `demo_paste`) and click Add.
2. Upload a small CSV (create one by hand, e.g. `title,body` header with 2-3 rows) with a corpus name and `text_column=body`.
3. Confirm both corpora appear in "Existing corpora" with the right document counts, and confirm the browser's network tab shows no CORS errors.

- [ ] **Step 6: Manually verify the Codebook screen in a browser**

On the Codebook tab:
1. Fill in a concept name, description, and one category (label + definition).
2. Click "+ Add category", fill in a second category with a different label, add a positive example and a boundary note.
3. Click "Create codebook". Confirm a YAML preview appears and looks like the codebook YAML format from `AGENTS.md`.
4. Click the codebook's name in "Existing codebooks" — confirm the form re-populates with what you entered.
5. Edit the description, click "Save changes", confirm the YAML preview updates.

- [ ] **Step 7: Confirm the backend test suite still passes**

Run (repo root): `pytest -v`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: wire up App.tsx with Corpus/Codebook tab navigation"
```

---

## Task 12: Close out the slice — `TODO.md`, `NEWS.md`

**Files:**
- Modify: `TODO.md`
- Modify: `NEWS.md`

- [ ] **Step 1: Update `TODO.md`**

In `TODO.md`, remove the "Codebook editor UI (Screen 2) and arbitrary corpus import..." line from `## Pending`, and add under `## Done`:

```markdown
- 2026-09-01 — Slice 2, Corpus import + Codebook editor screens: first
  frontend (Vite+React+TypeScript) talking to new `/corpora/*` and
  `/codebooks/*` FastAPI endpoints. Corpus import covers CSV/XLSX/pasted
  text (TXT/DOCX/PDF deferred). Codebook editor is a structured form
  (concept, categories with definitions/examples/boundary notes) with a
  YAML preview reusing `codebook.py`'s own format via a shared
  `validate_spec`/`spec_to_yaml_string`. Screens 3-5 (Run, Results,
  Validation) remain curl/API-only, deferred to Slice 3 per
  `AGENTS.md` § "Build order for the MVP". Design:
  `docs/superpowers/specs/2026-09-01-slice-2-corpus-codebook-screens-design.md`.
```

Also add to `## Pending`:

```markdown
- Run + Results screens (Screens 3-4) and the Validation screen (Screen
  5) — each gets its own spec/plan, per `AGENTS.md` § "Build order for
  the MVP". The backend already has `POST /runs`, `GET /runs/{id}`, and
  `GET /runs/{id}/results` from Slice 1 — Slice 3 is mostly frontend
  work plus whatever the Results/Validation screens need that isn't
  there yet (e.g. Cohen's kappa computation).
```

- [ ] **Step 2: Update `NEWS.md`**

Add a new `## 2026-09-01 (2)` section at the top of `NEWS.md` (above the existing `## 2026-09-01` section), summarizing this slice in the same style as the existing entries — one paragraph, in English, covering: the frontend now exists (Vite+React+TS), what the two screens do, the corpus-import scope decision (CSV/XLSX/paste, not TXT/DOCX/PDF), and the "no new `corpora` table" data-model decision made during planning.

- [ ] **Step 3: Commit**

```bash
git add TODO.md NEWS.md
git commit -m "docs: close out Slice 2 (corpus import + codebook editor screens)"
```

---

## Self-Review Notes

- **Spec coverage**: every section of the design spec has a task —
  Vite+React scaffold (Task 7), CSV/XLSX/paste import (Tasks 3, 5, 9),
  the "no new table" `GET /corpora` grouping (Task 5), the shared
  `validate_spec`/`spec_to_yaml_string` codebook engine (Task 4), the
  codebook CRUD endpoints (Task 6), the structured-form editor with YAML
  preview (Task 10), and manual (not automated) frontend verification
  (Task 11).
- **Known, deliberate scope cuts** (all explicit in the design spec,
  reiterated here so they're not mistaken for oversights): TXT/DOCX/PDF
  corpus import; deleting/duplicating a codebook or a corpus; triggering
  a run from the UI; a YAML preview before the first save; any frontend
  automated test suite.
- **Not in this plan** (explicitly Slice 3+ per `AGENTS.md` and the
  updated `TODO.md`): the Run screen, the Results table, the Validation
  screen (Cohen's kappa, disagreement review).
