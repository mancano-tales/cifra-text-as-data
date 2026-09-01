# Deep-Dive Codebase Analysis & Architectural Benchmarks for Cifra (`cifra-text-as-data`)

*Date: August 31, 2026*  
*Target Application: Cifra (`cifra-text-as-data`)*  
*Inspected Repositories*: `deepseek-ai/deepseek-harness`, `quallmer/quallmer`, `refuel-ai/autolabel`, `jxnl/instructor`, `LorcanMcLaren/codebook-lab`, `davidjurgens/potato`, `flowersteam/LLM4Humanities`.

---

## 1. Executive Summary

This report documents the findings from a line-by-line source code inspection of seven major open-source repositories cloned into scratch space. 

Key architectural takeaways for **Cifra** (`cifra-text-as-data`):
1. **Plugin-First Core (Inspired by DeepSeek Harness)**: Adopting DeepSeek Harness's **"Everything is a Plugin"** paradigm ensures that Provider Adapters (CLI vs. API vs. Ollama), Ingestion Parsers, and Validation Evaluators remain decoupled from core FastAPI routes and SQLite models.
2. **Schema Retry & Reask Handlers (Inspired by `instructor`)**: Reinjecting Pydantic `ValidationError` tracebacks back into subsequent prompt retries (`reask_handler`) guarantees robust structured extraction even when using subscription CLIs without native function-calling.
3. **Cost Planning & Asynchronous Queueing (Inspired by `autolabel`)**: Implementing a `plan()` method (token counting and cost estimation prior to execution) and async batch queueing prevents rate-limit failures and unexpected API charges.
4. **Native Inter-Coder Reliability (Inspired by `quallmer`)**: Porting native matrix implementations of Cohen's $\kappa$ (unweighted and weighted) and Fleiss' $\kappa$ into Python avoids external statistical dependencies while supporting multi-rater validation.
5. **Append-Only Trajectory Audit Trail (Inspired by DeepSeek Harness & `quallmer`)**: Logging raw responses, prompt templates, evidence spans, and timestamps in append-only SQLite tables guarantees 100% academic auditability.

---

## 2. Codebase Inspection Breakdown

### 2.1 DeepSeek Harness (`deepseek-ai/deepseek-harness`)
- **Core Seam**: Cordis Kernel (`docs/architecture.md`).
- **Key Pattern**: Every system component—model adapters, tool registries, storage drivers, and the agent loop—is implemented as a swappable plugin mounted on a shared context (`ctx`).
- **Turn Flow & Logging**: Implements a strict invariant: **"Model-visible means logged."** All model interactions append to a durable `SessionEvent` stream, creating a reproducible "Trajectory View".

```
                             ┌──────────────────────────────┐
                             │     Cifra FastAPI Kernel     │
                             └──────────────┬───────────────┘
                                            │
        ┌───────────────────┬───────────────┴───────────────┬───────────────────┐
        ▼                   ▼                               ▼                   ▼
┌───────────────┐   ┌───────────────┐               ┌───────────────┐   ┌───────────────┐
│   Provider    │   │   Ingestion   │               │  Validation   │   │    Storage    │
│    Plugin     │   │    Plugin     │               │    Plugin     │   │    Plugin     │
│ • Instructor  │   │ • CSV/XLSX    │               │ • Cohen's κ   │   │ • SQLite      │
│ • Claude CLI  │   │ • Process-Trac│               │ • Kripp. α    │   │ • Trajectory  │
│ • Ollama      │   │ • PDF/DOCX    │               │ • Gwet's AC1  │   │   Audit Log   │
└───────────────┘   └───────────────┘               └───────────────┘   └───────────────┘
```

---

### 2.2 `quallmer` (`quallmer/quallmer`)
- **Core Seam**: `R/qlm_codebook.R`, `R/qlm_code.R`, `R/reliability_kappa.R`.
- **Key Pattern**: Maps Posit's `ellmer::TypeObject` schemas directly to measurement levels (`nominal`, `ordinal`, `interval`, `ratio`).
- **Validation Engine**:
  - Implements native matrix math for Cohen's $\kappa$ (unweighted, linear, and quadratic) and Fleiss' $\kappa$.
  - Dichotomizes categories (`per_category_kappa_cohen`) to return per-class agreement metrics alongside macro statistics.
- **Audit Logging**: `qlm_trail()` records system prompts, parameters, raw outputs, and timestamps.

---

### 2.3 Refuel Autolabel (`refuel-ai/autolabel`)
- **Core Seam**: `src/autolabel/labeler.py`, `src/autolabel/confidence.py`.
- **Key Pattern**:
  - **`plan()` Method**: Iterates through dataset inputs, constructs prompts, calculates token lengths, and estimates execution cost prior to API calls.
  - **`arun()` Asynchronous Queue**: Handles batch labeling with progress tracking, token counting, latency logging, cost accumulation, and caching (`SQLAlchemyGenerationCache`).
  - **Confidence Calculator**: Calculates log-probability confidence scores per response (`ConfidenceCalculator`).

---

### 2.4 Instructor (`jxnl/instructor`)
- **Core Seam**: `instructor/v2/core/retry.py`, `instructor/v2/core/registry.py`.
- **Key Pattern**:
  - **Dynamic Schema Contracting**: Intercepts LLM calls and forces output validation against Pydantic models.
  - **Reask Mechanism**: When `ValidationError` or `JSONDecodeError` occurs, `handlers.reask_handler()` catches the exception and appends the error traceback to the prompt payload for the retry attempt, allowing the LLM to fix malformed outputs.

---

### 2.5 CodeBook Lab (`LorcanMcLaren/codebook-lab`)
- **Core Seam**: Streamlit parameter sweep runner.
- **Key Pattern**: Executes automated benchmark runs comparing model variations (OpenAI vs. Ollama), prompt structures, and temperature settings against a holdout gold-standard CSV (`ground-truth.csv`), calculating Cohen's $\kappa$ and F1 per configuration.

---

### 2.6 Potato (`davidjurgens/potato`) & LLM4Humanities (`flowersteam/LLM4Humanities`)
- **Core Seam**: Living YAML codebook parsers and active learning loops.
- **Key Pattern**: Combines human manual coding on a small initial sample with automated zero-shot/few-shot LLM classification, displaying real-time inter-rater agreement metrics before full dataset deployment.

---

## 3. Concrete Architectural Directives for Cifra (`cifra-text-as-data`)

1. **Adopt "Everything is a Plugin" Kernel**:
   Implement `ProviderPlugin` (CLI vs API vs Ollama), `IngestionPlugin` (CSV/XLSX vs `Reforming-TE-PT` process tracing workbook), and `ValidationPlugin` (Cohen's $\kappa$, Krippendorff's $\alpha$, Gwet's AC1, Egami's DSL) as pluggable classes.
2. **Re-Ask Error Feedback in CLI Mode**:
   When running under CLI mode (Claude Code CLI `claude -p` / Codex CLI), catch JSON parsing errors and pass the validation error message back into prompt retries (inspired by `instructor`).
3. **Token Cost Estimation (`plan()`)**:
   Expose an `/api/runs/plan` endpoint in FastAPI that calculates token count and cost estimates before launching background extraction jobs.
4. **Per-Category Disagreement Matrix**:
   Port `quallmer`'s dichotomized per-category $\kappa$ calculation into Python (`src/text_as_data/validation.py`) to highlight specific category confusion in the Validation UI.
5. **Append-Only Trajectory View**:
   Store every extraction run's execution steps (`codebook_hash`, `prompt_template`, `raw_response`, `evidence_span`, `timestamp`) in SQLite to guarantee peer-review defensibility.
