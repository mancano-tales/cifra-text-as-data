<!-- 🇺🇸 English — [🇧🇷 versão em português](README.pt-BR.md) -->

# cifra-text-as-data — Cifra

**Cifra** is a tool for analysts and researchers to code unstructured text (news articles, policy statements, police reports) into categorical variables using an LLM against an explicit, theoretical **codebook** — with a validation step against human-coded gold labels, because LLMs do not follow a codebook's specific definitions with perfect fidelity.

It is not a manual qualitative-coding tool (see [Taguette](https://www.taguette.org/), [QualCoder](https://github.com/ccbogel/QualCoder), or [QualiLab](https://github.com/LuizPF42/QualiLab) for that). The researcher defines a codebook and points it at a corpus; Cifra calls an LLM to fill the output table automatically.

**Status:** early — the corpus-import and codebook-editor screens exist; the run/results/validation screens are still API-only (see "What's actually built" below). Nothing here is packaged as an installable app yet.

---

## Why Cifra?

LLM text classification risks **construct validity**: does the model actually apply *your* specific operationalization of a concept, or does it fall back on a generic pre-trained notion of it (e.g. counting a labor strike as a "protest" even when your codebook excludes it)? See Halterman & Keith, *"Codebook LLMs: Evaluating LLMs as Measurement Tools for Political Science Concepts"* (*Political Analysis*, 2025). Cifra treats validating LLM output against human coding as a first-class part of the pipeline, not an afterthought.

---

## What's actually built

- **Codebook engine** (`text_as_data.codebook`): load a concept + categories (definitions, positive/negative examples, boundary notes) from YAML, and derive a Pydantic schema + system prompt from it at runtime. The same shared `validate_spec`/`spec_to_yaml_string` functions back both the YAML file format and the structured codebook editor, so the two can't drift apart.
- **Two LLM provider modes** (`text_as_data.providers`):
  - **API-key mode**: `instructor`-enforced structured output over the Anthropic or OpenAI SDKs — the reliable path.
  - **CLI mode**: shells out to an already-installed, already-authenticated CLI (`claude -p`, `agy -p`, or any similar tool) instead of a metered API key. Best-effort — the schema is requested in the prompt and the JSON response is parsed, with retry on malformed output. Supports both stdin- and argv-based prompt delivery, since not every CLI takes the prompt the same way.
- **FastAPI backend + SQLite** (`text_as_data.app`, `text_as_data.db`): caches an extraction per (document, codebook, model) so re-running a batch doesn't re-pay for documents already coded; retries a failing document up to 3 times and records a real error message instead of crashing the run.
- **Validation** (`text_as_data.validation`): `agreement_report()` computes per-category accuracy and Cohen's kappa against a human-coded gold set. That's the only agreement statistic implemented today.
- **Frontend** (`frontend/`, Vite + React + TypeScript): a Corpus screen (paste text, or upload CSV/XLSX and pick which column is the document text) and a Codebook screen (structured form + YAML preview), bilingual PT-BR/EN.

**Not built yet:** a Run screen, a Results table, or a Validation screen in the frontend — those exist only as `POST /runs` / `GET /runs/{id}` / `GET /runs/{id}/results`, callable via `curl` or the Python API directly. TXT/DOCX/PDF corpus import. Any packaged installer (see "Packaging" below). Krippendorff's alpha or Gwet's AC1 (only Cohen's kappa exists). A token-cost estimate before running a batch.

---

## Installation (development)

```bash
pip install -e ".[dev]"
cd frontend && npm install && cd ..
```

You'll also need either an `ANTHROPIC_API_KEY` environment variable (for API-key mode) or an already-installed, already-authenticated CLI like `claude` or `agy` (for CLI mode) — a run makes no LLM calls without one of the two.

---

## Running it (development)

There's no packaged app yet — running Cifra today means starting the FastAPI backend and the Vite frontend together. `scripts/dev.sh` (macOS/Linux/Git Bash) and `scripts/dev.ps1` (native PowerShell) do that with one command instead of two terminals:

```bash
scripts/dev.sh              # backend on :8000, frontend on :5173
scripts/dev.sh 8010 5183    # optional: override both ports
```

```powershell
powershell -File scripts/dev.ps1
powershell -File scripts/dev.ps1 -BackendPort 8010 -FrontendPort 5183
```

Then open `http://localhost:5173` (or whichever frontend port you chose). Ctrl+C stops both processes.

---

## Quickstart (Python API)

### 1. Define a YAML codebook

```yaml
concept: protest
description: A collective public event expressing a political or social claim.
categories:
  - label: protest
    definition: An occupation, march, or rally with a declared political demand.
    positive_examples:
      - "About 200 students marched to city hall square demanding lower fares."
    negative_examples:
      - "People gathered for a music festival."
    boundary_notes: Does not include purely ceremonial parades.
  - label: not_protest
    definition: Any event that does not meet the criteria above.
```

### 2. Load it and run an extraction

`extract()` takes a raw `instructor`-patched client (any provider `instructor` supports), a DataFrame of texts, and the codebook — one LLM call per row, each response validated against the codebook's schema:

```python
import instructor
import pandas as pd
from anthropic import Anthropic

from text_as_data import Codebook, extract

codebook = Codebook.from_yaml_file("codebook.yaml")
client = instructor.from_anthropic(Anthropic())
texts = pd.DataFrame({"id": [1], "text": ["About 200 people occupied the square..."]})

predicted = extract(texts, codebook, client, model="claude-sonnet-5")
```

Prefer the FastAPI backend (below) if you want caching, retry, and CLI-mode
support — `extract()` is the lower-level building block it's implemented
on top of, useful mainly for one-off scripts.

### 3. Or drive the same thing through the backend

```bash
scripts/dev.sh   # in one terminal

curl -X POST http://localhost:8000/codebooks -H "Content-Type: application/json" -d '{
  "concept": "protest",
  "description": "A collective public event expressing a political or social claim.",
  "categories": [
    {"label": "protest", "definition": "An occupation, march, or rally with a declared political demand."},
    {"label": "not_protest", "definition": "Any event that does not meet the criteria above."}
  ]
}'
curl -X POST http://localhost:8000/corpora/paste -H "Content-Type: application/json" \
  -d '{"name": "demo", "text": "About 200 people occupied the square..."}'
curl -X POST http://localhost:8000/runs -H "Content-Type: application/json" \
  -d '{"codebook_id": 1, "corpus_id": "demo", "model": "claude-sonnet-5"}'
curl http://localhost:8000/runs/1/results
```

See `src/text_as_data/app.py` for the full endpoint list (`/corpora/*`, `/codebooks/*`, `/runs/*`).

---

## Testing

```bash
pytest
```

Runs the full test suite (70+ tests) across the codebook YAML/spec engine, both provider modes, the SQLite models, the FastAPI endpoints, corpus import parsing, and the V7 pilot ingestion script.

---

## Packaging (not started)

The plan (see `AGENTS.md` § "Product trajectory") is a packaged desktop app: the Python backend compiled to a single binary (PyInstaller or Nuitka), run as a sidecar process inside a Tauri desktop shell, so installing Cifra is "download and open," not "clone a repo and run two dev servers." That work has not started — this machine doesn't even have a Rust toolchain installed yet, which Tauri requires. `AGENTS.md` gates it behind the pipeline being "validated with real use" first (i.e. after the Run/Results/Validation screens exist and have been run against a real human-coded gold set), which hasn't happened yet either.
