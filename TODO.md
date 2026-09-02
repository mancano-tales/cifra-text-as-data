# TODO

## Pending

- Validation screen (Screen 5) — gold-label import, Cohen's kappa (the
  metric `agreement_report()` already computes) surfaced in the UI,
  category-level precision/recall/F1, and a disagreement-review list.
  Gets its own spec/plan per `AGENTS.md` § "Build order for the MVP".
  Note (2026-09-02, updated): `HumanLabelRecord` has landed (QualiLab
  interop, below) — multiple rows allowed per `(document_id,
  codebook_id)`, distinguished by `coder`/`source`. `agreement_report()`
  needs exactly one gold row per document; the safe default is filtering
  to `source="qualilab_import"` rows imported with `layer="final"` (import
  already rejects a file with >1 "final" row per document, so that subset
  is guaranteed unique per document) or `source="manual"` rows from a
  plain-CSV gold import, not blindly passing every row for a codebook
  straight into the merge.
## Prospective

- DAAF-style **Reproducibility Verification** as its own validation mode
  (2026-09-02, from studying `DAAF-Contribution-Community/daaf`): beyond
  comparing a run's output to human gold labels (kappa/precision/recall),
  verify the *pipeline itself* is reproducible — same codebook + same
  model + same corpus should (within whatever tolerance non-deterministic
  LLM output allows) produce the same categoria. There's already a real
  data point for this: the V7 pilot's same-prompt repeat run found only
  21/32 (66%) exact agreement (see
  `docs/research/2026-09-02_llm_pipeline_verification_methodology.md`).
  DAAF has a dedicated engagement mode for exactly this — point it at a
  finished analysis and it reruns everything, reporting discrepancies.
  Bigger than the disclosure/provenance work above (needs its own design:
  what tolerance counts as "reproduced," N repeats, cost), not attempted
  in this pass — logged here instead of silently dropped.

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
## Done

- 2026-09-02 — TXT/MD/DOCX/PDF corpus import (Slice 2 covered
  CSV/XLSX/pasted text only): `POST /corpora/documents`, a multi-file
  upload where each file is one document (unlike CSV/XLSX's one-row-is-
  one-document) — a mixed batch of file types in one request is fine,
  dispatched per file by extension. New `corpus_import.py` parsers:
  `parse_txt_bytes` (also runs `ftfy.fix_text()`, already a dependency
  for exactly the mojibake class of bug AGENTS.md's V7 pilot notes
  describe), `parse_docx_bytes` (paragraphs, then table cells --
  `python-docx`), `parse_pdf_bytes` (page by page, no OCR — scanned/
  image-only PDFs are explicitly out of scope per AGENTS.md). All-or-
  nothing on a bad file in a batch, matching the CSV/XLSX endpoints'
  existing convention. `python-docx`/`pypdf` added to `pyproject.toml`
  (were already present in the dev environment but undeclared). 12 new
  tests, including a hand-built minimal-but-valid PDF (correct xref
  table and all) so PDF extraction is tested for real rather than mocked.
- 2026-09-02 — QualiLab interoperability: `POST /corpora/import-qualilab`
  (import a `.qualilab` project's documents as a corpus, preserving
  QualiLab's own doc id as the new `DocumentRecord.external_id`),
  `POST /corpora/{corpus_id}/import-qualilab-labels` (map `doc_values` to
  `HumanLabelRecord` gold labels via a required, explicit
  `value_mapping` — all-or-nothing on mapping validity, reports
  `coverage` for documents with no recorded value), and
  `POST /runs/{run_id}/export-qualilab` (inject a run's extractions back
  into a freshly re-uploaded `.qualilab` file as new `doc_values`, never
  a cached copy — matches by `external_id`, upserts by a deterministic id
  so re-exporting the same run doesn't duplicate). New
  `qualilab_interop.py` module (`open_qualilab_project`,
  `qualilab_documents_to_records`, `qualilab_doc_values_to_human_labels`,
  `inject_extractions_into_qualilab`, `serialize_qualilab_project`).
  New `HumanLabelRecord` table, deliberately multi-row per document (see
  the Validation screen note above for how that interacts with
  `agreement_report()`). Implements
  `docs/superpowers/specs/2026-09-02-qualilab-interop-design.md`
  (revision 4, 18 numbered findings across 3 red-team rounds) as written,
  including its two hardest-won details: the zip-bomb guard via
  `ZipInfo.file_size` checked before any `read()`, and the upsert-not-
  append fix for finding #13 (three independent reviewers across two
  model families caught that an earlier revision's "idempotent re-export"
  claim wasn't actually implemented). Tested against a copy of QualiLab's
  own shipped example fixture (`tests/fixtures/`, MIT), not synthetic
  mocks, for every behavior where the real file's shape matters — this is
  what caught the real "final" vs. "individual" layer counts used in the
  test assertions. 26 new tests, 126/126 passing (pilot_v7's CLI-dependent
  tests excluded from that count, unaffected).

- 2026-09-02 — CI: `.github/workflows/ci.yml`, two jobs on every push and
  every PR into main — `backend` (Python 3.12, `pip install -e ".[dev]"`,
  `pytest -q`) and `frontend` (Node 20, `npm ci`, `npm run lint`,
  `npm run build` — the latter runs `tsc -b` too, so a type error fails CI
  even though `oxlint` alone wouldn't catch it). Coordinated with the two
  other active sessions (`text-as-data-6d`, `text-as-data-8a`) before
  picking this up, to confirm it didn't collide with the Validation screen
  or QualiLab interop work in flight — this was the one item both agreed
  was fully unclaimed. Verified both jobs' exact commands pass locally
  before committing (109 tests green; frontend lint clean aside from 3
  pre-existing non-blocking `set-state-in-effect` warnings; build
  succeeds) rather than trusting the YAML would work once pushed.
- 2026-09-02 — GUIDE-LLM-shaped AI-use disclosure report per run
  (`GET /runs/{id}/disclosure`), adopted after studying the DAAF framework
  (`DAAF-Contribution-Community/daaf`) for lessons applicable to Cifra. New
  `disclosure.py` maps the real GUIDE-LLM checklist (13 items across
  sections A-G, fetched from the actual checklist page rather than
  guessed — llm-checklist.com/checklist) onto what Cifra already records
  per run: model/provider/access-mode (`RunRecord` gained `provider_mode`/
  `provider_detail`, persisted at creation instead of only living
  transiently on `CreateRunRequest`), the exact prompt sent per document
  (already-existing `prompt_sent`), whether output is validated against
  human gold labels (honestly reports "not yet" — no `human_labels` table
  exists yet), and reproducibility pointers (codebook id, run id, git
  commit). Doubles as the "citation propagation" idea from the same
  research: rather than a separate references subsystem, provenance and
  disclosure are the same report. Explicitly out of scope from that same
  research pass: DAAF's Reproducibility Verification mode (see Prospective
  below) and the rest of DAAF's much larger surface (9 engagement modes,
  benchmarking, etc.) — this took the 1-2 cheap, high-value ideas, not the
  whole framework. Also formalized the ad hoc "write down what surprised
  us" pattern this file was already doing as a named convention
  (`AGENTS.md` § `LEARNINGS.md`).
  Fell out of this work: closed the recurring schema-drift TODO below by
  building it instead of writing it up again — `db.py`'s `get_engine()`
  now runs an additive `_ensure_columns()` migration on every startup
  (diffs `PRAGMA table_info` against the SQLModel schema, `ALTER TABLE
  ADD COLUMN` for anything missing, defaulted and additive-only — never
  drops or renames), so a column added to a model doesn't require anyone
  to remember to patch whichever `codifica.sqlite` happens to be live.
  6 new tests (2 migration, 4 disclosure) plus coverage on the new
  endpoint; 99/99 passing (pilot_v7's CLI-dependent tests excluded from
  this count, unaffected by this change).
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
