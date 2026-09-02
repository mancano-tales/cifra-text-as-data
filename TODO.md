# TODO

## Pending

- Validation screen (Screen 5) — gold-label import, Cohen's kappa (the
  metric `agreement_report()` already computes) surfaced in the UI,
  category-level precision/recall/F1, and a disagreement-review list.
  Gets its own spec/plan per `AGENTS.md` § "Build order for the MVP".
  Note (2026-09-02): another session is designing a richer `human_labels`
  table shape as part of QualiLab interop (importing QualiLab doc_values
  as gold labels) — check what landed there before assuming AGENTS.md's
  original single-category/single-coder sketch is still the shape to
  build against.
- TXT/DOCX/PDF corpus import (Slice 2 covered CSV/XLSX/pasted text only).
- CI (lint + test on push) — not set up yet; add once the package has a
  real consumer.
- Enrich the V7 Bayesian pilot codebooks (`write_codebook_yaml` in
  `scripts/import_v7_pilot.py` and `scripts/run_v7_candidates_via_agy.py`)
  before treating any provider's output as validation-ready. They
  currently pass only `label`+`definition` per verbal-probability
  category — no `boundary_notes`, no positive/negative examples, no
  explicit instruction to weigh discriminating power (how much *less*
  likely under the rival hypothesis, not just "does this fit"). Running
  16 real candidate evaluations through `agy` (Google Antigravity CLI,
  Gemini) surfaced exactly the failure modes an under-specified codebook
  predicts: both sides of a pair scored `muito_provavel` in 6/16
  evaluations (~0 discriminating power, 4 of them in H3 alone); a scope
  condition ignored outright (H3a, "ideological preference for private
  provision," specifically theorizes right-wing/market-aligned parties —
  scored `muito_provavel` for a 2004 Lula/PT-government policy anyway);
  and inconsistent treatment of near-identical evidence (Fies
  retrenchment coded `muito_improvavel` for H1b in 2015/2016 but
  `muito_provavel` in 2017, no stable rule between the two readings).
  Per the author's explicit call (2026-09-01): treat this as a
  prompt/codebook specification gap to fix, not a signal to swap
  providers — see `AGENTS.md` § "Why the validation step is not
  optional" for why under-specified codebooks are expected to produce
  exactly this pattern regardless of which model runs them.

## Prospective

- Support LLM providers beyond OpenAI in `examples/` (instructor supports
  multiple providers already; the core `extraction.py` is provider-agnostic
  since it only depends on the `instructor`-patched client interface).
- **QualiLab interoperability — treat as a real priority, not a someday
  nice-to-have (author's emphasis, 2026-09-02).** Without it, Cifra and
  QualiLab stay two disconnected silos that both happen to call LLMs for
  coding, each rebuilding what the other already has (QualiLab: mature
  manual review, redaction, reconciliation, blind-evaluation UI; Cifra:
  unattended batch execution, cache, Cohen's kappa/precision/recall
  validation). Interop is what lets a researcher use both on the *same*
  project instead of picking one and losing the other's strengths — it is
  the concrete answer to "why build another tool" rather than a footnote.
  Any future slice that touches corpus import or the results/extractions
  data model should check whether it can be designed to also serve this,
  before that door closes by accident.
  Scope: import a `.qualilab` project as a corpus source (its
  `documents`, optionally its existing `codes`/`doc_values` as context)
  and export Cifra's automated extractions back into the same format, as
  a coding layer clearly marked "AI, unattended" and distinct from
  QualiLab's human-authored layers — so a researcher can round-trip
  between automated coding here and manual review/reconciliation in
  QualiLab. The goal is interop through the open `.qualilab` file format,
  not a shared codebase: see `AGENTS.md` § "Why not a single-file HTML
  tool like QualiLab" (2026-09-01 correction) for why building Cifra's
  features inside QualiLab's own codebase was ruled out — the author's
  README explicitly rejects a plugin architecture as incompatible with its
  single-file design.

## Done

- 2026-09-02 — Slice 3, Runs + Results screen: a "Runs" tab (list +
  detail: create a run in API-key or CLI mode, live progress polling,
  results table with category filter, inline categoria/justificativa
  edit, CSV/XLSX/JSON export). New backend: `GET /runs`,
  `PUT /runs/{id}/results/{id}`, `GET /runs/{id}/export`, and
  `GET /runs/{id}/results` now includes a `document_snippet`. Also fixed
  CORS to allow any localhost port instead of a single hardcoded
  `:5173` origin — hit as a real bug running two frontends against one
  backend during verification, not a hypothetical. Screen 5 (Validation)
  remains a separate, unstarted slice. Design:
  `docs/superpowers/specs/2026-09-01-slice-3-runs-results-screen-design.md`;
  plan: `docs/superpowers/plans/2026-09-01-slice-3-runs-results-screen.md`.
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
- 2026-09-01 — Slice 1, thin backend skeleton: FastAPI + SQLite backend
  verified end-to-end via `curl` against real V7 pilot data using CLI mode
  (`claude -p`, no API key available); both hypothesis sides ran
  successfully but disagreed with gold (`cinquenta_e_cinquenta` predicted
  vs. `provavel` gold on both, 0/2) — see `AGENTS.md` § "Build order for
  the MVP" for full outcome and two Windows-specific `CliProvider` bugs
  found along the way.
- 2026-08-30 — Initial scaffold (codebook/extraction/validation modules,
  toy example, tests). Agent: Claude Sonnet 5 (Claude Code).
