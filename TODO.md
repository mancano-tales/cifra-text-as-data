# TODO

## Pending

- Pick a first real pilot domain (candidates discussed: land-occupation
  news coding along the lines of DATALUTA, policy-stance statements,
  crime-event coding) and replace the toy example with a real codebook
  validated against an actual human-coded sample.
- Scraping/collection module — out of MVP scope on purpose (see
  `README.md`). Add once a real pilot domain is picked, since the source
  (newspaper archive, social platform API) determines the shape of the
  collector.
- CI (lint + test on push) — not set up yet; add once the package has a
  real consumer.

## Prospective

- Support LLM providers beyond OpenAI in `examples/` (instructor supports
  multiple providers already; the core `extraction.py` is provider-agnostic
  since it only depends on the `instructor`-patched client interface).

## Done

- 2026-08-30 — Initial scaffold (codebook/extraction/validation modules,
  toy example, tests). Agent: Claude Sonnet 5 (Claude Code).
