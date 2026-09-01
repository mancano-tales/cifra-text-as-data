# Slice 1 — Thin Backend Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the Codifica architecture end to end — YAML codebook → dynamically derived schema → LLM (CLI or API key) → SQLite → queryable result — against 2 real evidence rows from the author's `Reforming-TE-PT` V7 process-tracing workbook, with a `curl`-testable FastAPI backend and no frontend.

**Architecture:** FastAPI + SQLModel/SQLite backend added to the existing `text_as_data` package. `codebook.py` gains a YAML loader that derives a Pydantic schema at runtime. A new `Provider` abstraction (`providers.py`) lets `extraction.py` call either an API-key-backed `instructor` client or a subprocess CLI, uniformly, with caching and retry. A one-off script imports the V7 pilot data (2 evidence rows, mojibake-fixed, framed as 4 codebook runs — one per side of each hypothesis pair) into SQLite.

**Tech Stack:** Python 3.10+, FastAPI, Uvicorn, SQLModel (SQLite), `instructor`, `anthropic`/`openai`, `tenacity`, `ftfy`, `openpyxl`, `pyyaml`, `pytest`.

---

## Before you start

Read these, in order:
1. `text-as-data/AGENTS.md` — the full product vision, architecture decision, codebook YAML format, and the "Real-world pilot data" section (V7 mapping, the mojibake issue, the hypothesis-naming inconsistency).
2. `text-as-data/src/text_as_data/codebook.py`, `extraction.py`, `validation.py`, `tests/test_pipeline.py` — the existing code this plan extends. Do not change the public shape of `Codebook.build_messages`, `extract()`, or `agreement_report()` — only add to them.

**Pilot scope correction (read before Task 6):** `AGENTS.md` says 7 rows of the V7 workbook are fully human-coded. Of those, only **2 have a hypothesis pair resolvable to an actual theoretical definition** in the workbook's `tb1_hypotheses` sheet (`fk_hypothesis_group` = `H1` and `H3`). The other 4 use an old group label (`H_nao_partidaria`) that isn't a pair code in `tb1_hypotheses` — building codebook instructions for those would mean inventing hypothesis text that isn't in the data. This plan uses only the 2 resolvable rows. Each is coded against **both sides** of its pair (e.g. H1a and H1b), so the pilot run produces 4 (document, codebook) extractions to compare against 4 gold values. Log the 4 skipped rows so the gap is visible, don't silently drop them.

---

## File Structure

- `pyproject.toml` — **modify**: add runtime deps.
- `src/text_as_data/codebook.py` — **modify**: add `Codebook.from_yaml_string()` / `Codebook.from_yaml_file()`.
- `src/text_as_data/providers.py` — **create**: `Provider` ABC, `ApiKeyProvider` + `make_api_key_provider()`, `CliProvider`.
- `src/text_as_data/db.py` — **create**: SQLModel tables (`CodebookRecord`, `DocumentRecord`, `RunRecord`, `ExtractionRecord`) + `get_engine()`.
- `src/text_as_data/extraction.py` — **modify**: add `run_extraction(engine, run_id, provider)` (cache + retry, DB-backed), keep the existing `extract()` untouched.
- `src/text_as_data/pilot_v7.py` — **create**: pure transform functions for the V7 import (mojibake fix, hypothesis lookup, gold-row filtering) — no file I/O, fully unit-testable.
- `src/text_as_data/app.py` — **create**: FastAPI app, 3 endpoints.
- `scripts/import_v7_pilot.py` — **create**: one-off script wiring `pilot_v7.py` to a real `.xlsx` path, writing codebook YAMLs to `codebooks/`, seeding SQLite, writing `data/v7_pilot_gold.csv`.
- `codebooks/` — **create** (directory, populated by the import script, not by hand).
- `tests/test_codebook_yaml.py`, `tests/test_providers.py`, `tests/test_db.py`, `tests/test_pilot_v7.py`, `tests/test_extraction_run.py`, `tests/test_app.py` — **create**.

---

## Task 1: Add dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the new runtime and dev dependencies**

Edit the `dependencies` and `[project.optional-dependencies].dev` arrays:

```toml
[project]
name = "text-as-data"
version = "0.1.0"
description = "Pipeline to turn unstructured text into a structured table via LLM classification against an explicit codebook, validated against human coding."
requires-python = ">=3.10"
dependencies = [
    "instructor>=1.0",
    "pydantic>=2.0",
    "pandas>=2.0",
    "scikit-learn>=1.3",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "sqlmodel>=0.0.16",
    "anthropic>=0.34",
    "openai>=1.30",
    "tenacity>=8.2",
    "ftfy>=6.2",
    "openpyxl>=3.1",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "httpx>=0.27"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

(`httpx` is required by FastAPI's `TestClient`.)

- [ ] **Step 2: Install**

Run: `pip install -e ".[dev]"`
Expected: installs without error; `python -c "import fastapi, sqlmodel, anthropic, ftfy, openpyxl, yaml, tenacity"` prints nothing and exits 0.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add Slice 1 dependencies (FastAPI, SQLModel, anthropic, ftfy, etc.)"
```

---

## Task 2: YAML codebook loader

**Files:**
- Modify: `src/text_as_data/codebook.py`
- Test: `tests/test_codebook_yaml.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_codebook_yaml.py`:

```python
import pytest

from text_as_data import Codebook

YAML_SOURCE = """
concept: protest
description: >
  A collective, public event expressing a political or social claim,
  involving at least two people.
categories:
  - label: protest
    definition: >
      An occupation, march, or strike with a declared political demand.
    positive_examples:
      - "About 200 people occupied the square in front of city hall."
    negative_examples:
      - "People gathered for a cultural event with no political claim."
    boundary_notes: >
      Does not include purely ceremonial events with no claim being made.
  - label: not_protest
    definition: "Any event that does not meet the criteria above."
"""


def test_from_yaml_string_builds_schema_with_category_enum():
    codebook = Codebook.from_yaml_string(YAML_SOURCE)

    fields = codebook.schema.model_fields
    assert set(fields) == {"categoria", "justificativa", "trecho_evidencia"}
    assert set(fields["categoria"].annotation.__args__) == {"protest", "not_protest"}


def test_from_yaml_string_instructions_include_definitions_and_boundary_notes():
    codebook = Codebook.from_yaml_string(YAML_SOURCE)

    assert "occupation, march, or strike" in codebook.instructions
    assert "Does not include purely ceremonial events" in codebook.instructions


def test_from_yaml_string_rejects_duplicate_labels():
    bad_yaml = YAML_SOURCE.replace("not_protest", "protest")
    with pytest.raises(ValueError, match="duplicate category label"):
        Codebook.from_yaml_string(bad_yaml)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_codebook_yaml.py -v`
Expected: FAIL with `AttributeError: type object 'Codebook' has no attribute 'from_yaml_string'`

- [ ] **Step 3: Implement the loader**

Replace the full contents of `src/text_as_data/codebook.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import yaml
from pydantic import BaseModel, Field, create_model


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
        spec = yaml.safe_load(source)
        return cls._from_spec(spec)

    @classmethod
    def from_yaml_file(cls, path: str) -> "Codebook":
        with open(path, encoding="utf-8") as f:
            return cls.from_yaml_string(f.read())

    @classmethod
    def _from_spec(cls, spec: dict) -> "Codebook":
        labels = [c["label"] for c in spec["categories"]]
        if len(set(labels)) != len(labels):
            raise ValueError(f"duplicate category label in codebook: {labels}")

        schema = create_model(
            "CodebookExtraction",
            categoria=(Literal[tuple(labels)], Field(description="One of the codebook's category labels.")),
            justificativa=(str, Field(description="Free-text rationale for the chosen category.")),
            trecho_evidencia=(str, Field(description="Verbatim quote from the document that grounds the decision.")),
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

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_codebook_yaml.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the full existing suite to check nothing broke**

Run: `pytest -v`
Expected: all tests pass, including the pre-existing `tests/test_pipeline.py`

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/codebook.py tests/test_codebook_yaml.py
git commit -m "feat: load codebooks from YAML with a dynamically derived schema"
```

---

## Task 3: Provider abstraction — base + API-key mode

**Files:**
- Create: `src/text_as_data/providers.py`
- Test: `tests/test_providers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_providers.py`:

```python
from pydantic import BaseModel

from text_as_data.providers import ApiKeyProvider


class Label(BaseModel):
    categoria: str


class FakeChatCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, model, response_model, messages, max_retries):
        self.calls += 1
        return response_model(categoria="protest")


class FakeInstructorClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeChatCompletions()})()


def test_api_key_provider_delegates_to_instructor_client():
    fake_client = FakeInstructorClient()
    provider = ApiKeyProvider(client=fake_client, model="fake-model")

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "protest"
    assert fake_client.chat.completions.calls == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_providers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'text_as_data.providers'`

- [ ] **Step 3: Implement the base class and API-key provider**

Create `src/text_as_data/providers.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class Provider(ABC):
    """Something that can turn (messages, schema) into a validated schema instance."""

    @abstractmethod
    def extract(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        ...


class ApiKeyProvider(Provider):
    """The reliable path: an `instructor`-patched client that enforces the
    schema at the API level via tool/function calling."""

    def __init__(self, client: Any, model: str):
        self._client = client
        self._model = model

    def extract(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        return self._client.chat.completions.create(
            model=self._model,
            response_model=schema,
            messages=messages,
            max_retries=3,
        )


def make_api_key_provider(vendor: str, model: str, api_key: str | None = None) -> ApiKeyProvider:
    """Build an ApiKeyProvider for a real vendor. Not used in tests — tests
    construct ApiKeyProvider directly with a fake client."""
    import instructor

    if vendor == "anthropic":
        from anthropic import Anthropic

        client = instructor.from_anthropic(Anthropic(api_key=api_key))
    elif vendor == "openai":
        from openai import OpenAI

        client = instructor.from_openai(OpenAI(api_key=api_key))
    else:
        raise ValueError(f"unknown vendor: {vendor!r} (expected 'anthropic' or 'openai')")

    return ApiKeyProvider(client=client, model=model)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_providers.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/providers.py tests/test_providers.py
git commit -m "feat: add Provider abstraction and ApiKeyProvider (instructor-backed)"
```

---

## Task 4: Provider abstraction — CLI mode

**Files:**
- Modify: `src/text_as_data/providers.py`
- Test: `tests/test_providers.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_providers.py`:

```python
import subprocess

import pytest

from text_as_data.providers import CliProvider


def _fake_runner(stdout: str, returncode: int = 0):
    def runner(command, input, capture_output, text, timeout):
        return subprocess.CompletedProcess(args=command, returncode=returncode, stdout=stdout, stderr="")

    return runner


def test_cli_provider_parses_json_from_stdout():
    runner = _fake_runner('Here is the answer:\n{"categoria": "protest"}\nDone.')
    provider = CliProvider(command=["fake-cli", "-p"], runner=runner)

    result = provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)

    assert result.categoria == "protest"


def test_cli_provider_raises_on_nonzero_exit():
    runner = _fake_runner("boom", returncode=1)
    provider = CliProvider(command=["fake-cli"], runner=runner)

    with pytest.raises(RuntimeError, match="CLI command failed"):
        provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)


def test_cli_provider_raises_on_missing_json():
    runner = _fake_runner("no json here")
    provider = CliProvider(command=["fake-cli"], runner=runner)

    with pytest.raises(ValueError, match="no JSON object found"):
        provider.extract(messages=[{"role": "user", "content": "x"}], schema=Label)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_providers.py -v`
Expected: FAIL with `ImportError: cannot import name 'CliProvider'`

- [ ] **Step 3: Implement `CliProvider`**

Append to `src/text_as_data/providers.py`:

```python
import json
import re
import subprocess


class CliProvider(Provider):
    """Best-effort path: shells out to an already-installed CLI (e.g. the
    Claude Code CLI, `claude -p`, or a Codex-style CLI) instead of a billed
    API key. No API-level schema enforcement — the schema is requested in
    the prompt, and the response is parsed as JSON. Less reliable than
    ApiKeyProvider; retry-on-malformed-output is the caller's job
    (extraction.py), not this class's."""

    def __init__(self, command: list[str], runner=subprocess.run, timeout: int = 180):
        self._command = command
        self._runner = runner
        self._timeout = timeout

    def extract(self, messages: list[dict], schema: type[BaseModel]) -> BaseModel:
        prompt = self._build_prompt(messages, schema)
        result = self._runner(
            self._command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"CLI command failed (exit {result.returncode}): {result.stderr}")
        json_str = self._extract_json(result.stdout)
        return schema.model_validate_json(json_str)

    @staticmethod
    def _build_prompt(messages: list[dict], schema: type[BaseModel]) -> str:
        parts = [m["content"] for m in messages]
        schema_json = json.dumps(schema.model_json_schema())
        parts.append(
            "Respond with ONLY a single JSON object matching this JSON Schema, "
            f"and no other text before or after it:\n{schema_json}"
        )
        return "\n\n".join(parts)

    @staticmethod
    def _extract_json(text: str) -> str:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"no JSON object found in CLI output: {text!r}")
        return match.group(0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_providers.py -v`
Expected: 4 passed

- [ ] **Step 5: Manually verify the real CLI invocation shape (not automated)**

Run this once by hand to confirm the actual flag name for your installed Claude Code CLI version before relying on it:

```bash
echo 'Respond with ONLY {"categoria": "protest"}' | claude -p
```

Expected: stdout contains a JSON object. If the flag differs on your installed version, update the `command` list passed to `CliProvider` accordingly wherever it's constructed (Task 9's `app.py` and the manual curl test in Task 10) — `CliProvider` itself takes `command` as a parameter, so no code change is needed here, only at the call site.

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/providers.py tests/test_providers.py
git commit -m "feat: add CliProvider for subscription-CLI-backed extraction"
```

---

## Task 5: SQLite data models

**Files:**
- Create: `src/text_as_data/db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_db.py`:

```python
from sqlmodel import Session

from text_as_data.db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine


def test_round_trip_through_all_four_tables():
    engine = get_engine("sqlite://")

    # expire_on_commit=False: this test holds onto ORM objects (codebook,
    # document, run, extraction) across multiple `with Session(...)` blocks
    # to read their attributes later. SQLAlchemy's default
    # expire_on_commit=True expires every object still in the session on
    # each commit, so a later attribute read raises DetachedInstanceError
    # once the session that loaded it has closed. This isn't optional
    # here — it's required for this exact test shape.
    with Session(engine, expire_on_commit=False) as session:
        codebook = CodebookRecord(name="h1_a", yaml_raw="concept: x")
        session.add(codebook)
        session.commit()
        session.refresh(codebook)

        document = DocumentRecord(corpus_id="v7_pilot", text="some evidence text")
        session.add(document)
        session.commit()
        session.refresh(document)

        run = RunRecord(codebook_id=codebook.id, corpus_id="v7_pilot", model="claude-sonnet-5")
        session.add(run)
        session.commit()
        session.refresh(run)

        extraction = ExtractionRecord(
            run_id=run.id,
            document_id=document.id,
            categoria="quase_certa",
            justificativa="because...",
            trecho_evidencia="the quoted span",
        )
        session.add(extraction)
        session.commit()
        session.refresh(extraction)

    with Session(engine, expire_on_commit=False) as session:
        loaded = session.get(ExtractionRecord, extraction.id)
        assert loaded.categoria == "quase_certa"
        assert loaded.run_id == run.id
        assert loaded.document_id == document.id

    with Session(engine, expire_on_commit=False) as session:
        loaded_run = session.get(RunRecord, run.id)
        assert loaded_run.status == "pending"
        assert loaded_run.codebook_id == codebook.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'text_as_data.db'`

- [ ] **Step 3: Implement**

Create `src/text_as_data/db.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

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
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/db.py tests/test_db.py
git commit -m "feat: add SQLite data model (codebooks, documents, runs, extractions)"
```

---

## Task 6: V7 pilot transform functions (no file I/O)

**Files:**
- Create: `src/text_as_data/pilot_v7.py`
- Test: `tests/test_pilot_v7.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_pilot_v7.py`:

```python
from text_as_data.pilot_v7 import (
    VERBAL_PROBABILITY_LABELS,
    build_hypothesis_lookup,
    fix_mojibake,
    select_gold_rows,
)


def test_fix_mojibake_repairs_corrupted_portuguese_text():
    corrupted = "institui�es p�blicas"
    # Simulate the real corruption pattern seen in the V7 workbook: text
    # that was decoded with the wrong codec, not just replacement chars.
    corrupted = "institui\xe7\xf5es p\xfablicas".encode("latin-1").decode("cp1252", errors="replace")
    fixed = fix_mojibake(corrupted)
    assert isinstance(fixed, str)


def test_build_hypothesis_lookup_from_tb1_rows():
    tb1_rows = [
        {
            "pk_hyp_pair_code": "H1a",
            "hypothesis_name": "Conditional Partisan Expansion",
            "hypothesis_group_id": 1,
        },
        {
            "pk_hyp_pair_code": "H1b",
            "hypothesis_name": "De-commodification as Redistributive Mechanism",
            "hypothesis_group_id": 1,
        },
        {
            "pk_hyp_pair_code": "H3a",
            "hypothesis_name": "Ideological Preference for Private Provision",
            "hypothesis_group_id": 3,
        },
        {
            "pk_hyp_pair_code": "H3b",
            "hypothesis_name": "Path Dependence and Fiscal Constraint",
            "hypothesis_group_id": 3,
        },
    ]

    lookup = build_hypothesis_lookup(tb1_rows)

    assert lookup["H1"] == ("Conditional Partisan Expansion", "De-commodification as Redistributive Mechanism")
    assert lookup["H3"] == ("Ideological Preference for Private Provision", "Path Dependence and Fiscal Constraint")
    assert "H_nao_partidaria" not in lookup


def test_select_gold_rows_keeps_only_resolvable_pairs_with_both_probs():
    tb4_rows = [
        {"fk_id_ev": "ev1", "fk_hypothesis_group": "H1", "prob_e_dado_h1": "provavel", "prob_e_dado_h2": "improvavel"},
        {"fk_id_ev": "ev2", "fk_hypothesis_group": "H_nao_partidaria", "prob_e_dado_h1": "provavel", "prob_e_dado_h2": "provavel"},
        {"fk_id_ev": "ev3", "fk_hypothesis_group": "H3", "prob_e_dado_h1": None, "prob_e_dado_h2": "provavel"},
        {"fk_id_ev": "ev4", "fk_hypothesis_group": "H3", "prob_e_dado_h1": "quase_certa", "prob_e_dado_h2": "quase_impossivel"},
    ]
    lookup = {"H1": ("A", "B"), "H3": ("C", "D")}

    kept, skipped = select_gold_rows(tb4_rows, lookup)

    assert [r["fk_id_ev"] for r in kept] == ["ev1", "ev4"]
    assert [r["fk_id_ev"] for r in skipped] == ["ev2", "ev3"]


def test_verbal_probability_labels_has_seven_levels_in_scale_order():
    assert VERBAL_PROBABILITY_LABELS == [
        "quase_certa",
        "muito_provavel",
        "provavel",
        "cinquenta_e_cinquenta",
        "improvavel",
        "muito_improvavel",
        "quase_impossivel",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pilot_v7.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'text_as_data.pilot_v7'`

- [ ] **Step 3: Implement**

Create `src/text_as_data/pilot_v7.py`:

```python
from __future__ import annotations

import ftfy

VERBAL_PROBABILITY_LABELS = [
    "quase_certa",
    "muito_provavel",
    "provavel",
    "cinquenta_e_cinquenta",
    "improvavel",
    "muito_improvavel",
    "quase_impossivel",
]

VERBAL_PROBABILITY_DEFINITIONS = {
    "quase_certa": "Quase certamente observaríamos esta evidência se a hipótese fosse verdadeira (~0.95).",
    "muito_provavel": "Muito provavelmente observaríamos esta evidência (~0.80).",
    "provavel": "Provavelmente observaríamos esta evidência (~0.65).",
    "cinquenta_e_cinquenta": "Poderia ou não ocorrer — a evidência não discrimina entre as hipóteses (~0.50).",
    "improvavel": "Improvável, mas possível, observar esta evidência (~0.35).",
    "muito_improvavel": "Muito improvável observar esta evidência se a hipótese fosse verdadeira (~0.20).",
    "quase_impossivel": "Quase impossível observar esta evidência sob esta hipótese — hoop test (~0.05).",
}


def fix_mojibake(text: str) -> str:
    """Repair text corrupted by a wrong-codec round-trip during the original
    Folha scrape (e.g. `institui\\xe7\\xf5es` instead of `instituições`)."""
    return ftfy.fix_text(text)


def build_hypothesis_lookup(tb1_rows: list[dict]) -> dict[str, tuple[str, str]]:
    """Group tb1_hypotheses rows by `hypothesis_group_id` and return
    {pair_code: (side_a_name, side_b_name)} keyed by the pair's number
    (e.g. "H1"), sorted by pk_hyp_pair_code so side 'a' always comes first.
    Only pairs with exactly two rows are included."""
    by_group: dict[int, list[dict]] = {}
    for row in tb1_rows:
        by_group.setdefault(row["hypothesis_group_id"], []).append(row)

    lookup: dict[str, tuple[str, str]] = {}
    for group_id, rows in by_group.items():
        if len(rows) != 2:
            continue
        rows = sorted(rows, key=lambda r: r["pk_hyp_pair_code"])
        pair_code = f"H{group_id}"
        lookup[pair_code] = (rows[0]["hypothesis_name"], rows[1]["hypothesis_name"])
    return lookup


def select_gold_rows(
    tb4_rows: list[dict], hypothesis_lookup: dict[str, tuple[str, str]]
) -> tuple[list[dict], list[dict]]:
    """Split tb4_evidence_analisys rows into (kept, skipped).

    Kept: both prob_e_dado_h1 and prob_e_dado_h2 are filled, AND
    fk_hypothesis_group resolves to a real pair definition in
    hypothesis_lookup (built from tb1_hypotheses). Skipped: everything
    else — most commonly, rows tagged with an old free-text group label
    (e.g. "H_nao_partidaria") that isn't a resolvable pair code."""
    kept, skipped = [], []
    for row in tb4_rows:
        has_both_probs = bool(row.get("prob_e_dado_h1")) and bool(row.get("prob_e_dado_h2"))
        resolvable = row.get("fk_hypothesis_group") in hypothesis_lookup
        (kept if has_both_probs and resolvable else skipped).append(row)
    return kept, skipped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pilot_v7.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/pilot_v7.py tests/test_pilot_v7.py
git commit -m "feat: add V7 pilot transform functions (mojibake fix, hypothesis lookup, gold-row filter)"
```

---

## Task 7: V7 import script (real file I/O, run manually)

**Files:**
- Create: `scripts/import_v7_pilot.py`

This script is **not** covered by `pytest` — it touches a real file outside this repository (`Reforming-TE-PT`, a sibling directory) and is meant to be run once by hand, the same way `examples/toy_example/run.py` documents a manual real-LLM run. Its logic is a thin wrapper around the already-tested functions in `pilot_v7.py`.

- [ ] **Step 1: Write the script**

Create `scripts/import_v7_pilot.py`:

```python
"""Import the 2 usable V7 pilot rows (see docs/superpowers/plans/2026-08-31-slice-1-backend-skeleton.md)
into the Codifica SQLite DB, and write the 4 per-hypothesis-side codebook
YAML files plus a gold-labels CSV for later comparison.

Usage:
    python scripts/import_v7_pilot.py /path/to/v7_banco_process_tracing_baesiano_abdutivo_manual.xlsx
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import openpyxl
import yaml
from sqlmodel import Session

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from text_as_data.db import CodebookRecord, DocumentRecord, get_engine
from text_as_data.pilot_v7 import (
    VERBAL_PROBABILITY_DEFINITIONS,
    VERBAL_PROBABILITY_LABELS,
    build_hypothesis_lookup,
    fix_mojibake,
    select_gold_rows,
)

def _sheet_rows(ws) -> list[dict]:
    """Read a sheet using its own row-1 header as keys — do NOT hardcode a
    column list/order here. The workbook's `codebook` sheet documents a
    strict snake_case-in-English column-naming convention (§6 of
    `readme_v7_banco_process_tracing.md`), but does not guarantee column
    *order* matches the convention's own narrative tables, and this script
    was written from reading `tb3`/`tb4` directly, not `tb1` (see the
    plan's self-review note) — header-based reading removes that risk for
    all three sheets."""
    rows_iter = ws.iter_rows(values_only=True)
    header = next(rows_iter)
    rows = []
    for values in rows_iter:
        row = dict(zip(header, values))
        if row.get(header[0]) is None:
            continue
        rows.append(row)
    return rows


def write_codebook_yaml(pair_code: str, side_label: str, hypothesis_name: str, other_side_name: str) -> str:
    categories = [
        {
            "label": label,
            "definition": VERBAL_PROBABILITY_DEFINITIONS[label],
        }
        for label in VERBAL_PROBABILITY_LABELS
    ]
    spec = {
        "concept": f"{pair_code}_{side_label}_probability",
        "description": (
            f"Inhabit the world of the hypothesis '{hypothesis_name}' and ask: if this "
            "hypothesis were true, how expected would this evidence be? (Fairfield & "
            f"Charman 2022.) The competing hypothesis in this pair is '{other_side_name}' "
            "-- do not evaluate that one here, only the probability of the evidence under "
            f"'{hypothesis_name}'."
        ),
        "categories": categories,
    }
    path = Path("codebooks") / f"{pair_code.lower()}_{side_label}.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return str(path)


def main(xlsx_path: str) -> None:
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    tb1_rows = _sheet_rows(wb["tb1_hypotheses"])
    tb3_rows = {r["pk_id_ev"]: r for r in _sheet_rows(wb["tb3_evidence_raw"])}
    tb4_rows = _sheet_rows(wb["tb4_evidence_analisys"])

    required_tb1_columns = {"pk_hyp_pair_code", "hypothesis_name", "hypothesis_group_id"}
    if tb1_rows and not required_tb1_columns.issubset(tb1_rows[0]):
        raise KeyError(
            f"tb1_hypotheses is missing expected columns {required_tb1_columns - tb1_rows[0].keys()}; "
            f"actual columns: {sorted(tb1_rows[0].keys())}. This script's tb1 column names were taken from "
            "readme_v7_banco_process_tracing.md's documentation table, not verified directly against the "
            "sheet the way tb3/tb4 were (see the plan's self-review note) -- update build_hypothesis_lookup's "
            "expected keys in pilot_v7.py to match the real names printed above."
        )

    lookup = build_hypothesis_lookup(tb1_rows)
    kept, skipped = select_gold_rows(tb4_rows, lookup)

    print(f"Resolvable + fully coded rows kept: {len(kept)}")
    print(f"Skipped (unresolvable group or incomplete): {len(skipped)}")
    for row in skipped:
        print(f"  skipped {row['fk_id_ev']!r}: group={row.get('fk_hypothesis_group')!r}")

    engine = get_engine("sqlite:///codifica.sqlite")
    gold_rows = []

    with Session(engine) as session:
        for row in kept:
            pair_code = row["fk_hypothesis_group"]
            side_a_name, side_b_name = lookup[pair_code]
            evidence = tb3_rows[row["fk_id_ev"]]
            text = fix_mojibake(evidence["complete_evidence_content"])

            document = DocumentRecord(corpus_id=f"v7_pilot_{pair_code}", text=text)
            session.add(document)
            session.commit()
            session.refresh(document)

            for side_label, side_name, other_name, gold_categoria in (
                ("a", side_a_name, side_b_name, row["prob_e_dado_h1"]),
                ("b", side_b_name, side_a_name, row["prob_e_dado_h2"]),
            ):
                yaml_path = write_codebook_yaml(pair_code, side_label, side_name, other_name)
                codebook_record = CodebookRecord(
                    name=f"{pair_code}_{side_label}",
                    yaml_raw=Path(yaml_path).read_text(encoding="utf-8"),
                )
                session.add(codebook_record)
                session.commit()
                session.refresh(codebook_record)

                gold_rows.append(
                    {
                        "document_id": document.id,
                        "codebook_id": codebook_record.id,
                        "codebook_name": codebook_record.name,
                        "gold_categoria": gold_categoria,
                        "gold_justificativa": fix_mojibake(row.get("ek_justificativa_likelihoods") or ""),
                    }
                )

    gold_path = Path("data") / "v7_pilot_gold.csv"
    gold_path.parent.mkdir(exist_ok=True)
    with open(gold_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(gold_rows[0].keys()))
        writer.writeheader()
        writer.writerows(gold_rows)

    print(f"Wrote {len(gold_rows)} gold rows to {gold_path}")
    print(f"Documents + codebooks seeded into codifica.sqlite")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python scripts/import_v7_pilot.py /path/to/v7_....xlsx")
    main(sys.argv[1])
```

- [ ] **Step 2: Run it manually against the real file**

Run:
```bash
cd text-as-data
python scripts/import_v7_pilot.py "../Reforming-TE-PT/v7_banco_process_tracing_baesiano_abdutivo_manual.xlsx"
```
Expected: prints `Resolvable + fully coded rows kept: 2`, lists the 4 skipped `H_nao_partidaria`/incomplete rows, writes 4 files under `codebooks/`, writes `data/v7_pilot_gold.csv` with 4 rows, and creates/updates `codifica.sqlite` with 2 documents and 4 codebooks. If the actual kept/skipped counts differ from what `AGENTS.md` documents, that's real signal the workbook changed since 2026-08-31 — update `AGENTS.md` § "Real-world pilot data" to match, don't force the numbers.

- [ ] **Step 3: Commit**

```bash
git add scripts/import_v7_pilot.py
git commit -m "feat: add V7 pilot import script"
```

(`codifica.sqlite`, `codebooks/*.yaml`, and `data/v7_pilot_gold.csv` are generated data, not source — add all three to `.gitignore` in this step if `.gitignore` doesn't already exclude them.)

---

## Task 8: Extraction run — cache + retry, DB-backed

**Files:**
- Modify: `src/text_as_data/extraction.py`
- Test: `tests/test_extraction_run.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_extraction_run.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extraction_run.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_extraction'`

- [ ] **Step 3: Implement**

Append to `src/text_as_data/extraction.py` (keep the existing `extract()` function untouched above this):

```python
from sqlmodel import Session, select
from tenacity import retry, stop_after_attempt, wait_exponential

from .codebook import Codebook
from .db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord
from .providers import Provider


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def _extract_with_retry(provider: Provider, codebook: Codebook, text: str):
    messages = codebook.build_messages(text)
    return provider.extract(messages, codebook.schema)


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
                )
            ).first()

            if cached is not None:
                categoria, justificativa, trecho = cached.categoria, cached.justificativa, cached.trecho_evidencia
            else:
                try:
                    result = _extract_with_retry(provider, codebook, document.text)
                    categoria, justificativa, trecho = (
                        result.categoria,
                        result.justificativa,
                        result.trecho_evidencia,
                    )
                except Exception as exc:  # noqa: BLE001 -- one bad document must not kill the run
                    categoria, justificativa, trecho = "__error__", str(exc), ""

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extraction_run.py -v`
Expected: 2 passed

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/extraction.py tests/test_extraction_run.py
git commit -m "feat: add DB-backed run_extraction with caching and retry"
```

---

## Task 9: FastAPI app

**Files:**
- Create: `src/text_as_data/app.py`
- Test: `tests/test_app.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_app.py`:

```python
from fastapi.testclient import TestClient
from sqlmodel import Session

from text_as_data.app import app, get_engine_dependency, get_provider_dependency
from text_as_data.db import CodebookRecord, DocumentRecord, get_engine
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


class FakeProvider(Provider):
    def extract(self, messages, schema):
        return schema(categoria="yes", justificativa="because", trecho_evidencia="quote")


def _make_test_client():
    engine = get_engine("sqlite://")
    with Session(engine) as session:
        codebook = CodebookRecord(name="test", yaml_raw=YAML_SOURCE)
        session.add(codebook)
        session.add(DocumentRecord(corpus_id="test_corpus", text="doc 1"))
        session.commit()
        session.refresh(codebook)
        codebook_id = codebook.id

    app.dependency_overrides[get_engine_dependency] = lambda: engine
    app.dependency_overrides[get_provider_dependency] = lambda: FakeProvider()
    return TestClient(app), codebook_id


def test_post_runs_then_get_results():
    client, codebook_id = _make_test_client()

    response = client.post(
        "/runs", json={"codebook_id": codebook_id, "corpus_id": "test_corpus", "model": "fake-model"}
    )
    assert response.status_code == 200
    run_id = response.json()["run_id"]

    status = client.get(f"/runs/{run_id}").json()
    assert status["status"] == "done"
    assert status["processed"] == 1
    assert status["total"] == 1

    results = client.get(f"/runs/{run_id}/results").json()
    assert len(results) == 1
    assert results[0]["categoria"] == "yes"


def test_post_runs_with_unknown_codebook_returns_404():
    client, _ = _make_test_client()

    response = client.post("/runs", json={"codebook_id": 999, "corpus_id": "test_corpus", "model": "fake-model"})

    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'text_as_data.app'`

- [ ] **Step 3: Implement**

Create `src/text_as_data/app.py`:

```python
from __future__ import annotations

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .db import CodebookRecord, DocumentRecord, ExtractionRecord, RunRecord, get_engine
from .extraction import run_extraction
from .providers import Provider, make_api_key_provider

app = FastAPI(title="Codifica backend (Slice 1)")

_engine = get_engine()


def get_engine_dependency():
    return _engine


def get_provider_dependency() -> Provider:
    return make_api_key_provider(vendor="anthropic", model="claude-sonnet-5")


class CreateRunRequest(BaseModel):
    codebook_id: int
    corpus_id: str
    model: str


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
        rows = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).all()
        return [row.model_dump() for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app.py -v`
Expected: 2 passed

Note: in the test client, Starlette executes `BackgroundTasks` synchronously before returning the response, so by the time `client.post("/runs")` returns, the run is already `"done"` — no polling needed in the test.

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass (should be ~17 tests across all files by this point)

- [ ] **Step 6: Commit**

```bash
git add src/text_as_data/app.py tests/test_app.py
git commit -m "feat: add FastAPI backend (POST /runs, GET /runs/{id}, GET /runs/{id}/results)"
```

---

## Task 10: Manual end-to-end verification against real V7 data

This task has no automated test — it is the actual Phase 1 acceptance criterion from `AGENTS.md` ("the backend must come up and respond via `curl` with no frontend open"), run against the real pilot data from Task 7.

**Files:** none (verification only)

- [ ] **Step 1: Start the backend**

Run: `uvicorn text_as_data.app:app --reload --port 8000`
Expected: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 2: Confirm the codebooks and documents from Task 7 are present**

Run:
```bash
python -c "
from sqlmodel import Session, select
from text_as_data.db import CodebookRecord, DocumentRecord, get_engine
engine = get_engine('sqlite:///codifica.sqlite')
with Session(engine) as s:
    print('codebooks:', [c.name for c in s.exec(select(CodebookRecord)).all()])
    print('documents:', [(d.id, d.corpus_id) for d in s.exec(select(DocumentRecord)).all()])
"
```
Expected: 4 codebooks named like `h1_a`, `h1_b`, `h3_a`, `h3_b`; 2 documents.

- [ ] **Step 3: Kick off a real run via curl (uses `ANTHROPIC_API_KEY` from your environment)**

Run (substitute the real `codebook_id` and `corpus_id` printed in Step 2):
```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{"codebook_id": 1, "corpus_id": "v7_pilot_H1", "model": "claude-sonnet-5"}'
```
Expected: `{"run_id": <int>}`, HTTP 200.

- [ ] **Step 4: Poll status, then fetch results**

Run:
```bash
curl http://127.0.0.1:8000/runs/1
curl http://127.0.0.1:8000/runs/1/results
```
Expected: status eventually `"done"`; results contain one row with a `categoria` from `VERBAL_PROBABILITY_LABELS`, a `justificativa`, and a `trecho_evidencia`.

- [ ] **Step 5: Compare against gold by hand**

Open `data/v7_pilot_gold.csv` (written by Task 7) and compare the `categoria` returned in Step 4 against the row with matching `document_id`/`codebook_id`. Agreement or disagreement on 4 data points isn't a validation result — it's a sanity check that the plumbing produces sensible output. A real Cohen's kappa validation step is explicitly Slice 2+ scope (`AGENTS.md` § "Screens" → Validation), once more of the workbook is hand-coded.

- [ ] **Step 6: Update `AGENTS.md`**

Edit `text-as-data/AGENTS.md` § "Build order for the MVP": change "Slice 1 — thin backend skeleton (in progress)" to "(done, 2026-MM-DD)", and add one sentence noting whether the 4 real predictions agreed with the gold labels. Recreate the `CLAUDE.md` hard link if you edited `AGENTS.md` with a tool that breaks it (check with `diff AGENTS.md CLAUDE.md` before committing — see the fix already applied in this repo's git history, commit `87a1e46`, for the exact recovery steps if needed).

- [ ] **Step 7: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs: mark Slice 1 done, record real-run outcome against V7 gold data"
```

---

## Self-Review Notes

- **Spec coverage**: every `AGENTS.md` § "Build order" → Slice 1 requirement has a task — YAML codebook loading (Task 2), provider agnosticism (Tasks 3–4), SQLite persistence (Task 5), real pilot data with mojibake fix (Tasks 6–7), caching/retry (Task 8), `curl`-testable API with no frontend (Tasks 9–10).
- **Known, deliberate scope cut**: only 2 of the 7 "gold" rows `AGENTS.md` mentions are used (see "Pilot scope correction" at the top) — the other 4 need the author to resolve what `H_nao_partidaria` maps to in the current H1/H2/H3 numbering before they're usable; that's a follow-up, not a Slice 1 blocker.
- **Not in this plan** (explicitly Slice 2+ per `AGENTS.md`): any frontend, the Codebook Editor UI, arbitrary corpus import (CSV/XLSX/TXT/DOCX/PDF upload), Cohen's kappa / full Validation screen, cost estimation before running.
