# TODO

## Pending

- Run + Results screens (Screens 3-4) and the Validation screen (Screen
  5) — each gets its own spec/plan, per `AGENTS.md` § "Build order for
  the MVP". The backend already has `POST /runs`, `GET /runs/{id}`, and
  `GET /runs/{id}/results` from Slice 1 — Slice 3 is mostly frontend
  work plus whatever the Results/Validation screens need that isn't
  there yet (e.g. Cohen's kappa computation).
- TXT/DOCX/PDF corpus import (Slice 2 covered CSV/XLSX/pasted text only).
- CI (lint + test on push) — not set up yet; add once the package has a
  real consumer.

## Prospective

- Support LLM providers beyond OpenAI in `examples/` (instructor supports
  multiple providers already; the core `extraction.py` is provider-agnostic
  since it only depends on the `instructor`-patched client interface).
- QualiLab interoperability: import a `.qualilab` project as a corpus
  source (its `documents`, optionally its existing `codes`/`doc_values` as
  context) and export Cifra's automated extractions back into the same
  format, as a coding layer clearly marked "AI, unattended" and distinct
  from QualiLab's human-authored layers — so a researcher can round-trip
  between automated coding here and manual review/reconciliation in
  QualiLab. The goal is interop through the open `.qualilab` file format,
  not a shared codebase: see `AGENTS.md` § "Why not a single-file HTML
  tool like QualiLab" (2026-09-01 correction) for why building Cifra's
  features inside QualiLab's own codebase was ruled out — the author's
  README explicitly rejects a plugin architecture as incompatible with its
  single-file design.

## Done

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
