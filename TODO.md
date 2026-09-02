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
- No schema migration tooling — `SQLModel.metadata.create_all()` only
  creates missing tables, never alters an existing one. This has now bitten
  the shared local `codifica.sqlite` twice (`documents.created_at` in
  Slice 2, `extractions.prompt_sent`/`raw_response` on 2026-09-02, the
  second one discovered because it 500'd `GET /runs` for a live session)
  — both fixed by hand with an additive `ALTER TABLE ... ADD COLUMN`
  against the live file, not by regenerating it (see NEWS.md 2026-09-02
  (3) for the exact fix). Worth either a lightweight startup check
  (compare `PRAGMA table_info` against the SQLModel schema, auto-add
  missing nullable/defaulted columns) or adopting Alembic once the schema
  churns less — before every future column addition means hunting down
  and manually patching whichever `codifica.sqlite` files happen to be
  live at the time.

## Prospective

- Open items from the LLM-pipeline verification methodology (see
  `docs/research/2026-09-02_llm_pipeline_verification_methodology.md`,
  written after the author pushed on prompt provenance/reproducibility for
  the V7 pilot): (1) unify the enriched V7 codebooks to one language
  (Portuguese, matching the evidence corpus and the human-authored
  probability scale — currently mixed with the English mechanism/premises
  text) instead of the current inconsistent mix; (2) add an explicit
  structural delimiter between "instructions end" / "evidence begins" in
  the concatenated CLI prompt; (3) test whether scoring both hypothesis
  sides in one joint call (forcing direct comparison) discriminates better
  than the current two blind, separate calls — needs a schema/pipeline
  change, not just a prompt edit; (4) ablate the fixed "careful annotator"
  persona line in `Codebook.build_messages` (from the very first commit,
  never tested with/without); (5) once the Validation screen exists,
  consider running each evidence/hypothesis-pair evaluation more than once
  before treating a single categoria as final — a same-prompt repeat run
  on the 16 V7 candidates found only 21/32 (66%) exact agreement.
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

- 2026-09-02 — Full prompt/response audit trail, prompted by the author
  asking how to verify a shown prompt wasn't invented after the fact and
  whether the pipeline is reproducible. `providers.py` gained
  `ProviderResult(parsed, prompt, raw_response)`; both `ApiKeyProvider` and
  `CliProvider` return one instead of a bare parsed model.
  `ExtractionRecord` gained `prompt_sent`/`raw_response` columns, persisted
  by `run_extraction` on every row (copied from the cached record on a
  cache hit; best-effort `json.dumps(messages)` fallback if the provider
  itself fails after `build_messages` succeeded). Both fields now flow
  through `GET /runs/{id}/results` and every export format automatically,
  since `app.py` already builds those rows via `ExtractionRecord.model_dump()`.
  8 new tests, 95/95 passing. Full methodology and the reproducibility
  test that motivated it (a same-prompt repeat run on the V7 candidates:
  21/32 exact match, one real 3-step reversal inspected and found to
  reflect genuine evidence ambiguity, not model incoherence) written up in
  `docs/research/2026-09-02_llm_pipeline_verification_methodology.md`.
- 2026-09-02 — Enriched the V7 Bayesian pilot codebooks and confirmed the
  fix with real data: added `HYPOTHESIS_DEFINITIONS` (full mechanism +
  premises per side, not just the hypothesis name) and
  `PROBABILITY_BOUNDARY_NOTES` (scope-check / discriminating-power /
  consistency instructions per category) to `pilot_v7.py`
  (`build_enriched_hypothesis_codebook_spec`), then re-ran the identical
  16 evaluations through the identical `agy`/Gemini with nothing else
  changed. Non-discriminating cases (both sides of a pair scored
  `muito_provavel`) went from 6/16 to 0/16; the `muito_provavel` bias
  dropped from 66% to 28% of outputs; the flagged scope-condition failure
  (H3a scored `muito_provavel` for a left-wing government's policy)
  flipped to `quase_impossivel`, with the model's own justification now
  naming the governing party and calling it a "hoop test failure" in
  Fairfield & Charman's own terms. Confirms the author's diagnosis: this
  was a codebook-specification gap, not a model/provider reliability
  problem — see the project memory note on diagnosing prompt before model
  for the durable lesson. Every spreadsheet export from this pilot
  (`scripts/run_v7_candidates_via_agy.py`) now also carries the complete
  hypothesis definition and complete evidence text per row, not just a
  short justificativa, per the author's explicit requirement.
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
