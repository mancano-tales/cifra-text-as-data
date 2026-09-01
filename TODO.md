# TODO

## Pending

- **Slice 1 — thin backend skeleton**: FastAPI + SQLite, YAML codebook
  loader deriving the Pydantic schema dynamically, run the existing
  `policy_stance` toy example end to end, `curl`-testable, no frontend
  yet. Blocked on the LLM-provider decision below. See `AGENTS.md` §
  "Build order for the MVP".
- **LLM provider — CLI vs. API key, agnostic**: design a provider
  abstraction that supports both shelling out to an already-installed CLI
  (the user's existing subscription, e.g. Claude Code CLI) and a direct
  API key (OpenAI/Anthropic) via `instructor`. Needed before Slice 1's
  extraction call can be written for real (the toy example currently
  hardcodes OpenAI + `instructor`).
- **Real pilot data from sibling repos**: bring in the author's master's
  thesis coding spreadsheet ("V7", in `Mancano2026-MA-Thesis`) and scraped
  Folha de São Paulo articles (`folha-scraper`) as real corpus/gold-label
  data instead of only the toy example. Needs a root-level plan in
  `MancanoSync/0-meta/plan/` mentioning both sibling repos before any file
  is read/copied from them — not yet done.
- Pick a first real pilot domain (candidates discussed: land-occupation
  news coding along the lines of DATALUTA, policy-stance statements,
  crime-event coding) and replace the toy example with a real codebook
  validated against an actual human-coded sample. Likely resolved by the
  item above (V7 spreadsheet / Folha corpus) once located.
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
