# NEWS

## 2026-08-31 (2)

- Both open items from the first 2026-08-31 entry resolved: the LLM
  provider layer is agent-agnostic (CLI mode — Claude Code CLI, Codex CLI,
  or a generic command adapter, best-effort JSON — alongside the existing
  API-key/`instructor` mode as the reliable path); and the real pilot data
  is the `Reforming-TE-PT` Bayesian process-tracing workbook ("V7"),
  chosen over the simpler Folha relevance-triage pipeline in
  `Mancano2026-MA-Thesis`. Located, inspected read-only (with explicit
  root-plan authorization), and found to have only 7 fully human-coded
  rows (5 with justification) — small but real; proceeding with it for
  Slice 1 anyway, on the author's call. Also found: text mojibake in the
  evidence content (fix before use) and an old/new hypothesis-group naming
  inconsistency in the coded rows. Full detail in `AGENTS.md` §
  "Real-world pilot data".

## 2026-08-31

- `AGENTS.md` expanded with the full product vision for evolving this
  library scaffold into "Codifica", a local-first app for LLM-assisted
  text coding with a codebook editor, run queue, results table, and a
  validation screen (Cohen's kappa + disagreement review) against
  human-coded gold labels. Architecture closed: Python/FastAPI backend now
  ("sidecar-ready" from commit 1), Tauri+PyInstaller packaging later, no
  rewrite. Build order agreed via brainstorming: a thin backend-only
  skeleton (Slice 1, reusing the existing `policy_stance` toy example)
  before any of the 5 MVP screens are built individually. Two things
  still open: the LLM provider layer (must support both a CLI the user
  already has a subscription for, and a direct API key) and whether/how
  to bring in real pilot data from `Mancano2026-MA-Thesis` ("V7" coding
  spreadsheet) and `folha-scraper` — both live in sibling repositories and
  need a root-level plan before anything is touched there.

## 2026-08-30

- Initial scaffold: `codebook`, `extraction`, `validation` modules, a toy
  end-to-end example, and a test suite exercising the pipeline against a
  fake LLM client. No real domain codebook yet — see `TODO.md`.
