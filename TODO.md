# TODO

## Pending

- **Slice 1 — thin backend skeleton**: FastAPI + SQLite, YAML codebook
  loader deriving the Pydantic schema dynamically, provider layer with
  both CLI mode (Claude Code CLI / Codex CLI / generic) and API-key mode
  (`instructor`), corpus import + mojibake fix for the `Reforming-TE-PT`
  V7 evidence text, run against the 7 fully human-coded rows for
  validation, `curl`-testable, no frontend yet. See `AGENTS.md` § "Build
  order for the MVP" and § "Real-world pilot data". Ready to move into an
  implementation plan (`writing-plans`).
- Codebook editor UI (Screen 2) and arbitrary corpus import (Screen 1,
  CSV/XLSX/TXT/DOCX/PDF) — each gets its own spec/plan after Slice 1, per
  `AGENTS.md` § "Build order for the MVP".
- CI (lint + test on push) — not set up yet; add once the package has a
  real consumer.

## Prospective

- Support LLM providers beyond OpenAI in `examples/` (instructor supports
  multiple providers already; the core `extraction.py` is provider-agnostic
  since it only depends on the `instructor`-patched client interface).

## Done

- 2026-08-30 — Initial scaffold (codebook/extraction/validation modules,
  toy example, tests). Agent: Claude Sonnet 5 (Claude Code).
