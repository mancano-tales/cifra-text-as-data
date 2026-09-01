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

---

## Product Vision — What This Is Becoming

> This section captures the author's brief for evolving the current
> library scaffold into a full application, agreed 2026-08-31. It is the
> source of truth for scope and architecture until superseded by a dated
> update to this section. Working product name: **"Codifica"** (placeholder
> — avoid colliding with existing tools like "Codebook LLMs", which is a
> paper name, not a product; final name TBD). The package/repo keeps the
> name `text-as-data`; renaming the repo is a cosmetic decision deferred to
> later.

### The problem

Social scientists (political science, sociology, geography) code
unstructured text (news articles, police reports, public statements) into
categorical variables that operationalize theoretical concepts — "is this a
protest?", "does this statement support or oppose policy X?". This has
historically been done by hand, with research assistants reading and
filling a spreadsheet. LLMs can now automate a lot of this, but every
researcher currently reinvents the pipeline from scratch, with no reusable
tool.

This is **not** a manual QDA tool (Taguette, QualCoder, QualiLab already
exist for that). It is the inverse: the researcher defines a codebook,
points at a corpus, and the software calls an LLM to fill the output table
automatically — with a validation step against human coding as a
first-class part of the pipeline, because LLMs do not follow codebooks with
perfect fidelity (see "Why validation is not optional" below).

**What "automated" does and does not mean**: automation applies only to the
mechanical coding step — text becomes a category without an RA reading
every row. It does not remove the researcher from the rest of the process.
The researcher is still solely responsible for: designing the codebook
(which categories exist, how each is defined, where the conceptual
boundaries are), deciding the pipeline's architecture (which corpus, which
model, which parameters), interpreting results, and deciding — via the
validation step — whether the automated coding is reliable enough to become
research data. The software automates mechanical execution, not the
theoretical decision of what is being measured. This should be explicit in
the UI too: the Codebook Editor (Screen 2) is the most important screen in
the software, not a secondary form before "the real part".

### MVP scope (v0.1) — build in this order

1. **Import corpus**: CSV/XLSX (one row = one document; user maps which
   column is the text), standalone TXT/DOCX/PDF, or pasted text. No
   automated web scraping in this version — this is local file ingestion.
2. **Codebook editor**: an interface to define a concept with categories.
   Each category has: name, definition, positive examples, negative
   examples, boundary notes ("do not confuse with Y"). See exact format
   below.
3. **Run extraction**: runs the LLM over each corpus document using the
   codebook as system instructions + structured output (JSON Schema).
   Needs: a queue with visible progress, automatic retry on
   network/rate-limit errors, caching (do not re-code a document already
   processed with the same codebook+model), estimated cost (tokens) before
   running.
4. **Results table**: view/edit output row by row, export CSV/XLSX/JSON.
5. **Validation**: import a human-labeled subset (gold standard), compare
   against the LLM output, compute accuracy, Cohen's kappa,
   precision/recall/F1 per category, and list disagreements for manual
   reading (error analysis).

**Explicitly out of MVP scope** (do not build yet, only keep the
architecture ready for it): automated scraping of sites/social media,
model fine-tuning, multi-user/auth, multi-language UI, image/scanned-PDF
extraction (OCR).

### Architecture (closed decision — do not reopen without a strong reason)

Why not a single-file HTML tool like QualiLab: QualiLab is 100% manual
coding — it makes no batched API calls. This project needs to run
hundreds/thousands of LLM calls reliably (retry, cache, cost tracking,
execution that survives closing the tab). That calls for a real backend
process, not just JS in the browser.

**Stack decision**: a lightweight local backend (Python), not a
single-file browser app. Batched LLM calls need retry/cache/cost control
and processing that survives closing the tab — uncomfortable and unsafe
(exposed API key) if done only in browser JS.

**Product trajectory** (a roadmap, not a day-1 requirement): the long-term
goal is a packaged desktop app (Windows/Mac/Linux), not a script only the
author knows how to run. This does **not** mean building in Tauri/Electron
from day one — it means building the Python backend so that packaging is a
packaging step later, not a rewrite:

- **Phase 1 (now)**: standalone FastAPI backend, "sidecar-ready" from the
  first commit — a single process that comes up on a local port, with no
  dependency on browser/session state, all persistence in local SQLite.
  **Acceptance criterion**: the backend must come up and respond via
  `curl` with no frontend open. If that stops being true at any point
  during development, it is a sign of improper front/back coupling — fix
  it before continuing.
- **Phase 2 (packaging, only after the pipeline is validated with real
  use)**: compile the Python backend into a single binary via PyInstaller
  (or Nuitka), and use Tauri (preferred over Electron — uses the system
  webview, much lighter) as the desktop shell, auto-starting that binary as
  a sidecar when the app opens. The LLM/validation/cache logic is not
  rewritten — only packaged. This is the same pattern used by today's
  popular desktop AI apps (e.g. local-LLM apps running a Node/Python
  process behind an Electron/Tauri window) — it is the standard
  industry architecture for "desktop GUI + local AI engine", not a hack.
- **Why not jump straight to Tauri with native (Rust/TS) logic**:
  rewriting LLM orchestration, retry/cache, and kappa computation in
  Rust/TypeScript costs real engineering and throws away the advantage of
  the Python ecosystem (mature LLM SDKs, `scipy`/`scikit-learn` for
  validation metrics, scraping libraries if scope grows). Only consider
  that route if the Python sidecar proves genuinely problematic for
  cross-platform distribution in practice.
- **Backend**: Python + FastAPI, running locally (`uvicorn`). Responsible
  for: LLM calls (see "LLM provider" below), a background job queue
  (nothing heavier than needed — no Redis/Celery in the MVP), and a SQLite
  database (`sqlmodel`) holding codebooks, corpus, runs, and results.
- **Frontend**: a simple SPA talking to the backend over REST/fetch.
  Either in QualiLab's "no heavy build" spirit (Preact + htm via CDN) or a
  light Vite+React app — implementer's call at build time, as long as it
  does not add build complexity a project this size does not need.
  Important for Phase 2: pick something Tauri can embed as a webview
  without friction (both options qualify).
- **Local execution (Phase 1)**: `pip install -e .` + a `codifica serve`
  (or similar) command brings up backend+frontend on a local port; the
  user opens it in a browser. Credentials are entered once in the UI and
  saved to local config (see "LLM provider" below for the two supported
  credential modes) — nothing is ever sent anywhere except the chosen
  provider's own API/CLI. In Phase 2 this migrates to the OS's native
  secure storage (e.g. a Tauri keychain plugin), but the "paste your
  credential once" UX stays the same.
- No cloud/third-party server in the MVP. If a collaborative mode ever
  makes sense later (like QualiLab's Supabase mode), treat it as v3, after
  desktop packaging.

**LLM provider — OPEN QUESTION, not yet closed** (as of 2026-08-31): the
author wants the provider layer to be **agent-agnostic**, supporting two
credential modes side by side rather than API-key-only:
1. Shelling out to an already-installed CLI the user has a subscription
   for (e.g. Claude Code CLI, a Codex-style CLI) — no separate metered API
   key needed if the user already pays for a CLI subscription.
2. A direct API key (OpenAI and/or Anthropic) via the `instructor` SDK
   pattern already used in the current toy example.
This changes the shape of the provider abstraction (`extraction.py`
currently assumes an `instructor`-patched chat client; a CLI-subprocess
path needs a different call shape and a different way to enforce
structured JSON output) and is **not yet designed** — see the open
questions thread in this repo's session history before implementing it.
Do not implement Slice 1's provider layer as API-key-only without
re-confirming this is still open.

### Codebook format

Based on Halterman & Keith's "Stage 0: Codebook Preparation" (2025,
*Political Analysis*, "Codebook LLMs") — a format readable by both humans
and LLMs. Stored as YAML (editable outside the GUI too) and as rows in
SQLite:

```yaml
concept: protest
description: >
  A collective, public event expressing a political or social claim,
  involving at least two people.
categories:
  - label: protest
    definition: >
      An occupation, march, or strike with a declared political demand, or
      a road blockade with a stated claim.
    positive_examples:
      - "About 200 people occupied the square in front of city hall..."
    negative_examples:
      - "People gathered for a cultural event with no political claim"
    boundary_notes: >
      Does not include purely ceremonial/commemorative events with no
      claim being made. A labor strike with no political demand is a
      boundary case — decide explicitly whether to include or exclude it.
  - label: not_protest
    definition: "Any event that does not meet the criteria above."
```

The LLM's structured output must be forced via a JSON Schema derived
directly from this codebook (an `enum` of the category `label`s, plus a
free-text `rationale` field and an `evidence_span` field quoting the part
of the document that grounded the decision — this is what makes the
decision auditable later).

### Data model (SQLite tables, high level)

- `codebooks` (id, name, yaml_raw, created_at)
- `documents` (id, corpus_id, text, metadata_json)
- `runs` (id, codebook_id, corpus_id, model, status, created_at)
- `extractions` (id, run_id, document_id, category, rationale,
  evidence_span, tokens_used)
- `human_labels` (id, document_id, codebook_id, category, coder)

### Screens (main flow)

1. **Corpus** — import/list documents
2. **Codebook** — create/edit codebook (a structured form, not raw YAML)
3. **Run** — pick corpus + codebook + model, watch progress, estimated cost
4. **Results** — browsable table, filter by category, export
5. **Validation** — import human gold labels, view agreement metrics and
   the list of disagreements

### Why the validation step is not optional

Read before simplifying this part: Halterman & Keith (2025) and the same
group's 2026 follow-up ("What is a protest anyway?", ACL 2026) show that
off-the-shelf LLMs frequently ignore a codebook's specific
operationalization and fall back on their own generic notion of the
concept (e.g. including a labor strike under "protest" even when the
codebook explicitly excludes it). That is why the Validation screen with
Cohen's kappa and manual disagreement review is not a "nice to have" — it
is this tool's actual scientific differentiator over just calling the API
directly from a script.

### Build order for the MVP (agreed 2026-08-31, via brainstorming)

The 5-screen MVP is too large for one implementation plan. Build order:

1. **Slice 1 — thin backend skeleton** (in progress): FastAPI + SQLite,
   engine adapted to load the YAML codebook format above and derive the
   Pydantic schema dynamically, run against the existing toy corpus
   (`examples/toy_example/`, the `policy_stance` domain — reused as-is for
   this slice), with minimal caching/retry and a `curl`-testable API. No
   frontend yet — that is Slice 2's job, matching the Phase 1 acceptance
   criterion above ("backend responds via curl with no frontend open").
   Provider layer for this slice is blocked on the open LLM-provider
   question above.
2. **Slice 2+** — one spec/plan per screen (Corpus import, Codebook
   editor, Run + Results, Validation), each building on the skeleton.

### Real-world pilot data (proposed, not yet actioned)

The author wants to validate the concept against his own real-world data
rather than only the toy example, specifically:
- His master's thesis coding spreadsheet ("V7"), in the
  `Mancano2026-MA-Thesis` sibling repository.
- Scraped Folha de São Paulo articles from the `folha-scraper` sibling
  repository.

Both are **separate child repositories** of the `MancanoSync` root, not
part of `text-as-data`. Per the root `AGENTS.md`, reading from and copying
data out of another child repo into this one is a cross-repository,
architectural action that needs a root-level plan in `0-meta/plan/`
mentioning all three repositories by name before any file is touched in
`Mancano2026-MA-Thesis` or `folha-scraper` — this has not happened yet as
of 2026-08-31. Locate the exact files and confirm scope before acting.
