<!-- 🇺🇸 English — [🇧🇷 versão em português](README.pt-BR.md) -->

# cifra-text-as-data — Cifra

**Cifra** is a local-first software application and library designed for social scientists (political science, sociology, geography) to code unstructured text (news articles, policy statements, police reports) into categorical variables using Large Language Models (LLMs) against an explicit, theoretical **codebook** — with a first-class validation pipeline against human gold-standard coding.

---

## Why Cifra?

Social science computational text classification often risks **construct validity**: does the LLM actually apply *your* specific operationalization of a concept (e.g. distinguishing a labor strike from a political protest), or does it default to generic pre-training definitions? (See Halterman & Keith, *"Codebook LLMs: Evaluating LLMs as Measurement Tools for Political Science Concepts"*, *Political Analysis*, 2025.)

Cifra treats validation (Cohen's $\kappa$, Krippendorff's $\alpha$, Gwet's AC1, category-level disagreement analysis) as an essential, non-optional scientific contribution rather than a formality.

---

## Architecture

Cifra follows a lightweight, local-first **sidecar backend architecture** (Python + FastAPI + SQLite with WAL mode):

```
                       ┌──────────────────────────────┐
                       │   Cifra FastAPI Sidecar API   │
                       └──────────────┬───────────────┘
                                      │
  ┌───────────────────┬───────────────┴───────────────┬───────────────────┐
  ▼                   ▼                               ▼                   ▼
┌───────────────┐   ┌───────────────┐               ┌───────────────┐   ┌───────────────┐
│   Provider    │   │   Ingestion   │               │  Validation   │   │    Storage    │
│    Engine     │   │    Engine     │               │    Engine     │   │    Engine     │
│ • Instructor  │   │ • CSV/XLSX    │               │ • Cohen's κ   │   │ • SQLite WAL  │
│ • Claude CLI  │   │ • Process-Trac│               │ • Kripp. α    │   │ • Trajectory  │
│ • Ollama      │   │ • UTF-8/ftfy  │               │ • Gwet's AC1  │   │   Audit Log   │
└───────────────┘   └───────────────┘               └───────────────┘   └───────────────┘
```

- **YAML Codebooks**: Domain experts declare concepts, category definitions, positive/negative examples, and boundary notes in human/LLM-readable YAML files.
- **Dual Provider Engine**:
  1. **API-Key Mode**: Guaranteed schema enforcement via `instructor` and Pydantic models over OpenAI, Anthropic, or Gemini APIs.
  2. **CLI Mode**: Best-effort JSON extraction using flat-rate CLI subscriptions (`claude -p` / `codex exec`) with regex markdown fencing repair and capped 2 retries.
- **Cost Planning (`plan()`)**: Calculates token count and projects execution cost before running batch extractions.
- **SQLite Trajectory Audit Log**: Persists raw responses, prompt templates, evidence spans, and timestamps in append-only SQLite tables for peer-review defensibility.

---

## Installation

```bash
pip install -e ".[dev]"
cd frontend && npm install && cd ..
```

---

## Running it (development)

There's no packaged app yet (see `AGENTS.md`'s Phase 2 plan for that) — running
Cifra today means starting the FastAPI backend and the Vite frontend
together. `scripts/dev.sh` (macOS/Linux/Git Bash) and `scripts/dev.ps1`
(native PowerShell) do that with one command instead of two terminals:

```bash
scripts/dev.sh              # backend on :8000, frontend on :5173
scripts/dev.sh 8010 5183    # optional: override both ports
```

```powershell
powershell -File scripts/dev.ps1
powershell -File scripts/dev.ps1 -BackendPort 8010 -FrontendPort 5183
```

Then open `http://localhost:5173` (or whichever frontend port you chose).
Ctrl+C stops both processes. You'll need either an `ANTHROPIC_API_KEY`
environment variable or an already-authenticated CLI (`claude`, `agy`, ...)
for the LLM calls a run actually makes.

---

## Quickstart

### 1. Define a YAML Codebook

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

### 2. Python API & Database Setup

```python
from text_as_data.codebook import load_codebook
from text_as_data.db import init_db

# 1. Load codebook from YAML
codebook = load_codebook("codebook.yaml")

# 2. Initialize SQLite database with WAL mode enabled
engine = init_db()
```

### 3. Run FastAPI Sidecar Server

```bash
uvicorn text_as_data.app:app --reload --port 8000
```

- **Health Check**: `GET http://localhost:8000/health`
- **Upload Codebook**: `POST http://localhost:8000/codebooks`
- **Upload Corpus**: `POST http://localhost:8000/documents`
- **Execute Run**: `POST http://localhost:8000/runs`
- **Fetch Results**: `GET http://localhost:8000/runs/{run_id}/results`

---

## Testing

```bash
pytest
```

Runs the full test suite (40+ tests) across DB models, YAML codebook parsing, CLI provider regex repair, FastAPI endpoints, V7 pilot ingestion, and agreement validation.
