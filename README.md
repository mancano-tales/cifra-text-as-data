<!-- 🇺🇸 English — [🇧🇷 versão em português](README.pt-BR.md) -->

# cifra-text-as-data — Cifra

**Cifra** is a local-first tool for turning unstructured text (news articles, policy statements, police reports) into categorical data using an LLM against an explicit **codebook** you define — with a validation step against human-coded gold labels, because LLMs do not follow a codebook's specific operationalization with perfect fidelity.

It is not a manual qualitative-coding tool (see [Taguette](https://www.taguette.org/), [QualCoder](https://github.com/ccbogel/QualCoder), or [QualiLab](https://github.com/LuizPF42/QualiLab) for that). You define a codebook, point it at a corpus, and Cifra runs the LLM over every document and fills an output table automatically.

**Status:** MVP complete — all five screens exist (Corpus, Codebook, Runs, Results, Validation). No packaged installer yet; running Cifra today requires starting two dev servers from a terminal (see "Running it" below).

---

## Why Cifra?

LLM text classification risks **construct validity**: does the model actually apply *your* specific operationalization of a concept, or does it fall back on a generic pre-trained notion (e.g. counting a labor strike as a "protest" even when your codebook excludes it)? See Halterman & Keith, *"Codebook LLMs: Evaluating LLMs as Measurement Tools for Political Science Concepts"* (*Political Analysis*, 2025). Cifra treats validating LLM output against human coding as a first-class step in the pipeline, not an afterthought.

---

## What's actually built

- **Codebook engine** (`text_as_data.codebook`): load a concept and its categories (definitions, positive/negative examples, boundary notes) from YAML, and derive a Pydantic schema and system prompt from it at runtime.
- **Two LLM provider modes** (`text_as_data.providers`):
  - **API-key mode**: `instructor`-enforced structured output over the Anthropic or OpenAI SDKs — the reliable path.
  - **CLI mode**: shells out to an already-installed, already-authenticated CLI (`claude -p`, `agy -p`, or a similar tool) instead of a metered API key. Best-effort — the schema is requested in the prompt and the JSON response is parsed, with retry on malformed output.
- **FastAPI backend + SQLite** (`text_as_data.app`, `text_as_data.db`): caches an extraction per (document, codebook hash, model) so re-running a batch doesn't re-pay for documents already coded; retries a failing document up to 3 times and records the error instead of crashing the run. Every extraction persists the exact prompt sent and the raw LLM response for auditability.
- **Validation** (`text_as_data.validation`): `agreement_report()` computes per-category accuracy, Cohen's kappa, precision, recall, and F1 against a human-coded gold set, and returns the list of disagreements for manual inspection.
- **Frontend** (`frontend/`, Vite + React + TypeScript): five screens — Corpus (paste text, or upload CSV/XLSX), Codebook (structured form + YAML preview), Runs (start a run, watch progress), Results (browse the output table, export CSV), and Validation (upload gold labels, view agreement metrics and disagreements). Bilingual PT-BR/EN.
- **QualiLab interop** (`text_as_data.qualilab_interop`): import `.qualilab` packages as a gold-label source for the validation step.
- **Disclosure** (`text_as_data.disclosure`): generates a structured methods-section report for a completed run — what model, what codebook, what prompt, what reproducibility rate.

**Not built yet:** TXT/DOCX/PDF corpus import. Packaged installer. Token cost estimate before running a batch. Parallel document processing (currently one document at a time). Krippendorff's alpha or Gwet's AC1 (only Cohen's kappa today). Support for providers beyond Anthropic and OpenAI (no Gemini, no local/Ollama endpoints yet). Credential entry in the UI (today, API keys are read from environment variables).

---

## Installation (development)

```bash
pip install -e ".[dev]"
cd frontend && npm install && cd ..
```

You'll also need either an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` environment variable (for API-key mode), or an already-installed, already-authenticated CLI like `claude` or `agy` (for CLI mode).

> **Note (multi-worktree environments):** `pip install -e .` registers the editable install globally, pointing to whichever checkout ran it last. If you have multiple worktrees, run the suite as `PYTHONPATH=src pytest` to bypass the editable install and hit the right source. See [`docs/MULTI_AGENT_WORKTREES.md`](docs/MULTI_AGENT_WORKTREES.md) for details.

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

Then open `http://localhost:5173`. Ctrl+C stops both processes.

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

`extract()` is the lower-level building block the FastAPI backend is implemented on top of, useful mainly for one-off scripts. Use the backend if you want caching, retry, and CLI-mode support.

### 3. Or drive it through the backend

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

---

## Testing

```bash
PYTHONPATH=src pytest
```

Runs 238 tests across the codebook engine, both provider modes, the SQLite models, the FastAPI endpoints, corpus import parsing, QualiLab interop, validation metrics, and the disclosure module.

---

## Packaging (not started)

The plan (see `AGENTS.md` § "Product trajectory") is a packaged desktop app — the Python backend compiled to a single binary, run locally, so installing Cifra is "download and open" rather than "clone a repo and run two dev servers." That work has not started. `AGENTS.md` gates it behind the pipeline being validated with real use first.
