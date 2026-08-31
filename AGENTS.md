# AGENTS.md — text-as-data

This repository has light-weight governance (no `0-meta/`, no shared
skills, no git hooks — see the parent ecosystem's `CLAUDE.md` for why: this
repo was scaffolded at "light" governance level, same tier as
`presentations` and `2026-workshop-agentes-dcp-usp`).

## Rules for AI agents working in this repo

- **Language**: everything in this repository — code, comments, docstrings,
  README/NEWS/TODO, commit messages — is in **English**. This is a
  deliberate deviation from the parent `MancanoSync` ecosystem, whose root
  governance files are in Portuguese.
- **Validation is not optional**: any change to `codebook.py`,
  `extraction.py`, or `validation.py` must keep `pytest` passing. If you
  add a new codebook for a real pilot domain, validate it against a
  human-coded sample before treating its output as usable data — that
  validation is the actual scientific contribution of this tool, not a
  formality.
- **Keep `codebook` separate from `extraction`/`validation`**: a codebook
  is domain-specific and expected to change often; the engine underneath it
  should not need to change to support a new codebook. If you find yourself
  editing `extraction.py` to support a specific codebook, that is a signal
  the abstraction needs rethinking, not a one-off fix.
- **`TODO.md`**: append new pending items instead of editing prose in place;
  move finished items to the "Done" section with a date.
