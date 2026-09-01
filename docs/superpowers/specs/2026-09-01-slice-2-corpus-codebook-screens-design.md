# Slice 2 — Corpus Import + Codebook Editor Screens (Design)

> Decided 2026-09-01 via brainstorming with the author. Covers `AGENTS.md`
> Screens 1 (Corpus) and 2 (Codebook), combined into one slice. Screens 3–5
> (Run, Results, Validation) are explicitly out of scope — running an
> extraction stays curl/API-only until Slice 3.

## Why this scope

Slice 1 proved the engine end-to-end (YAML codebook → LLM → SQLite) with no
frontend. The two things a researcher cannot yet do through any UI are: get
their own text into the tool, and author a codebook without hand-writing
YAML. Those are Screens 1 and 2. The author chose to build both together
rather than sequentially, since a demo where you can only do one half
("import your corpus, but the codebook is a hardcoded YAML file" or
"design a codebook, but seed data comes from a script") doesn't yet show
the product's actual shape. Run/Results/Validation build on the existing
`POST /runs` / `GET /runs/{id}` / `GET /runs/{id}/results` endpoints from
Slice 1 and are deferred to Slice 3.

Import scope for Screen 1 is narrowed to **CSV/XLSX + pasted text** (not
TXT/DOCX/PDF) — those two paths cover this project's actual pilot use case
(a spreadsheet of documents) and the simplest ad-hoc case (paste one piece
of text), without pulling in per-format parsers (`python-docx`, a PDF text
extractor) that are separable follow-up work.

## Frontend stack decision

**Vite + React + TypeScript**, chosen over the CDN-script Preact+htm
option `AGENTS.md` also allows. Reasoning: the codebook editor's form
(nested, repeatable category rows, each with two example lists) is
non-trivial state to hand-roll without a component model, and this is the
project's first and formative frontend decision — worth paying the modest
extra setup cost now for TypeScript + a real component ecosystem, rather
than migrating later once more screens exist. It remains a plain
webview-embeddable SPA (static build output), so it doesn't compromise the
Phase 2 Tauri plan.

New top-level directory: `frontend/` (sibling to `src/`), a standard Vite
scaffold (`npm create vite@latest -- --template react-ts`). Dev flow:
`uvicorn` on `:8000`, `npm run dev` (Vite) on `:5173`, frontend calls the
backend via `fetch` against `http://localhost:8000`. The backend gains
`CORSMiddleware` allowing `http://localhost:5173` for local dev only (no
production deploy target exists yet — Phase 2 packaging will revisit
origin handling when the Tauri shell serves both from one process).

Two screens, no router library needed yet — a simple two-tab layout
(`Corpus` / `Codebook`) in `App.tsx` is enough for 2 screens; React Router
gets added when Screen 3 (Run) makes "navigate to a specific run" a real
requirement.

## Data model change: `corpora` becomes a real table

Today `DocumentRecord.corpus_id` and `RunRecord.corpus_id` are bare
strings with no backing entity — Slice 1's V7 import script invents
strings like `"v7_pilot_H1"` ad hoc. Screen 1 is precisely the place that
creates corpora, and Screen 1's UI needs to list "your corpora" by a real
name, so this slice adds:

```python
class CorpusRecord(SQLModel, table=True):
    __tablename__ = "corpora"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    source: str  # "csv" | "xlsx" | "pasted"
    created_at: datetime = Field(default_factory=...)
```

`DocumentRecord.corpus_id` and `RunRecord.corpus_id` change from `str` to
`int` (`Field(foreign_key="corpora.id")`). This is a breaking schema
change, acceptable because `codifica.sqlite` is gitignored, generated,
local-only data — there is no migration to write, only regeneration.
Call sites that reference `corpus_id` as a string (`extraction.py`'s
document filter, `app.py`'s `CreateRunRequest`, `scripts/import_v7_pilot.py`,
and the tests seeding `corpus_id="test_corpus"`) all need updating to use
a real `CorpusRecord.id`. `scripts/import_v7_pilot.py` starts creating one
`CorpusRecord` per hypothesis pair instead of inventing a string.

## Backend: new modules and endpoints

**`src/text_as_data/corpus_import.py`** (new, mirrors `pilot_v7.py`'s
shape: pure transform functions, no file I/O, fully unit-testable):
- `parse_csv_rows(content: bytes) -> list[dict]`
- `parse_xlsx_rows(content: bytes) -> list[dict]` (via `openpyxl`, already
  a dependency)
- Both return row dicts keyed by the sheet/CSV's own header — column
  selection (which column is the text) happens one layer up, in `app.py`,
  from a `text_column` the client specifies, not hardcoded here.

**`src/text_as_data/codebook.py`** (extend, don't replace): refactor the
label-uniqueness / required-field validation currently inlined in
`_from_spec` into a standalone `validate_spec(spec: dict) -> None` (raises
`ValueError`), reused by both `from_yaml_string` and a new
`spec_to_yaml_string(spec: dict) -> str`. The structured editor's "create
codebook" request body *is* the same `spec` dict shape the YAML already
uses (`concept`, `description`, `categories: [...]`) — the endpoint layer
just round-trips JSON ⇄ YAML through this one shared validator, so the
codebook format itself doesn't fork into "the API's version" and "the
YAML version."

**`src/text_as_data/app.py`** new endpoints:
- `POST /corpora/csv` — multipart upload (file + `name` + `text_column`),
  creates one `CorpusRecord` + N `DocumentRecord`s from CSV rows
- `POST /corpora/xlsx` — same, for `.xlsx`
- `POST /corpora/paste` — JSON `{name, text}`, creates one `CorpusRecord`
  + 1 `DocumentRecord`
- `GET /corpora` — list, with a document count per corpus
- `GET /corpora/{id}/documents` — list documents in a corpus (paginated:
  `?limit=&offset=`, default limit 50 — the V7 corpus alone is 443 rows)
- `POST /codebooks` — JSON body = the spec dict; validates via
  `validate_spec`, stores `yaml_raw = spec_to_yaml_string(spec)`
- `GET /codebooks` — list (id, name/concept, created_at)
- `GET /codebooks/{id}` — returns both the parsed structured spec (for
  re-populating the edit form) and `yaml_raw` (for the read-only preview
  panel)
- `PUT /codebooks/{id}` — same body shape as POST, re-validates,
  overwrites `yaml_raw`

Upload size isn't bounded in this slice (no chunking, no background job for
import — CSV/XLSX parsing is fast enough to do inline in the request). If
a real corpus turns out large enough to make that a problem, that's a
Slice 3+ concern, not a reason to add complexity here.

## Frontend: two screens

**Corpus screen** (`frontend/src/CorpusPage.tsx`): a list of existing
corpora (name, source, document count) fetched from `GET /corpora`, plus
an import panel with three actions — CSV upload, XLSX upload (both: pick
file, then a column-name text input for which column is the text, since
we don't yet parse headers client-side before submit — the column name is
typed in, and a 422 from the backend if it doesn't match a real header is
surfaced as a form error), and a textarea for pasting ad-hoc text. No
per-document preview/edit in this slice — that's the Results screen's job
later; this screen only needs to prove the corpus landed with the right
row count.

**Codebook screen** (`frontend/src/CodebookEditor.tsx`): list of existing
codebooks on the left (name, created_at, click to load into the form),
and the structured form on the right — concept name, description
textarea, and a repeatable list of category rows (label, definition,
positive examples as a repeatable string list, negative examples same,
boundary notes textarea). A "Preview YAML" panel below the form calls
`spec_to_yaml_string` server-side (via a lightweight `POST /codebooks`
dry-run, or simply re-renders after a successful save — simplest: the YAML
preview only appears after Save, fetched from `GET /codebooks/{id}`, not
live-generated client-side. This avoids duplicating the YAML-formatting
logic in TypeScript). Save creates via `POST /codebooks` if new, or
`PUT /codebooks/{id}` if editing an existing one already loaded.

## Error handling

- Backend: a CSV/XLSX with the requested `text_column` missing → `422`
  with the actual header list in the message (same pattern already used in
  `scripts/import_v7_pilot.py`'s `required_tb1_columns` check). An
  unparseable file (corrupt XLSX, wrong encoding CSV) → `400`.
- `validate_spec` errors (duplicate label, missing category, missing
  concept/description) → `422` from both `POST` and `PUT /codebooks`,
  surfaced verbatim in the form as an inline error banner — no
  client-side re-implementation of these rules, so the two can't drift.
- Frontend: every fetch call handles a non-2xx response by showing the
  server's `detail` message; no silent failures.

## Testing

- Backend: `pytest` coverage for `corpus_import.py` (pure functions, same
  style as `test_pilot_v7.py`), the new `app.py` endpoints (via
  `TestClient`, same pattern as `test_app.py`), and `validate_spec` /
  `spec_to_yaml_string` (extends `test_codebook_yaml.py`). This keeps the
  `AGENTS.md` rule ("any change to `codebook.py`, `extraction.py`, or
  `validation.py` must keep `pytest` passing") satisfied — this slice
  touches `codebook.py`.
- Frontend: no automated test suite is being introduced in this slice
  (no Vitest/RTL setup) — kept lean, matching the project's "don't
  over-build" ethos. Verification is manual: run both dev servers, import
  a real CSV, build a codebook by hand in the form, confirm the YAML
  preview matches, per this project's own rule to actually exercise UI
  changes in a browser before calling them done.

## Explicitly out of scope for this slice

Corpus source types other than CSV/XLSX/paste (TXT/DOCX/PDF); deleting or
duplicating a codebook; editing/deleting a corpus or its documents;
triggering a run from the UI (Slice 3); YAML preview before the first
save; a shared component library or design system (2 screens don't
justify one yet); authentication (out of MVP scope per `AGENTS.md`).
