# Slice 3 — Runs + Results Screen (Design)

> Decided 2026-09-01 via brainstorming with the author. Covers `AGENTS.md`
> Screens 3 (Run) and 4 (Results), combined into one UI tab. Screen 5
> (Validation — Cohen's kappa, gold-label import, disagreement review) is
> explicitly out of scope, deferred to a Slice 4.

## Why this scope, and why one tab not two

`AGENTS.md`'s MVP order lists Run and Results as separate screens, but
they're tightly coupled — you can't usefully look at Results without
having picked a Run first. Two disconnected tabs would mean carrying a
run id from one tab to the other by hand. Instead: one **Runs** tab, list
of runs on the left, a detail panel on the right that shows whichever of
three things is relevant to the selected run — a "create new run" form
(nothing selected), a live progress bar (status `pending`/`running`), or
the full results table (status `done`). This mirrors the existing
list+detail layout already used by the Codebook screen (`codebook-layout`
grid), not a new pattern.

Cost estimation before running (part of `AGENTS.md`'s original Run
scope) is deferred — it needs a real per-provider tokenizer
(`tiktoken` for OpenAI, an Anthropic equivalent), which is separable work
that doesn't block being able to run and see results.

Results scope, per the author's explicit choice, is the *full* original
`AGENTS.md` ask: table + filter by category + inline edit
(categoria/justificativa) + export in all three formats
(CSV/XLSX/JSON) — not trimmed to just table+CSV.

## Backend additions

**`GET /runs`** (new) — list all runs, most recent first, each with
`processed`/`total` counts (same shape `GET /runs/{id}` already computes)
plus the codebook's name (joined, so the frontend list doesn't need a
second fetch per row) and `corpus_id`:

```
[{"id", "corpus_id", "codebook_id", "codebook_name", "model", "status",
  "processed", "total", "created_at"}]
```

**`GET /runs/{run_id}/results`** (extend, don't replace) — the existing
endpoint returns bare `ExtractionRecord` rows with no document context,
which makes the table useless for judging whether `trecho_evidencia`
actually came from the right place. Add `document_snippet` (first 160
characters of `DocumentRecord.text`, joined by `document_id`) to each row.
Existing fields (`id`, `run_id`, `document_id`, `categoria`,
`justificativa`, `trecho_evidencia`, `tokens_used`) unchanged.

**`PUT /runs/{run_id}/results/{extraction_id}`** (new) — body
`{categoria, justificativa}`. Re-loads the run's codebook via
`Codebook.from_yaml_string` and checks `categoria` is one of its actual
category labels (`422` if not) — the codebook stays the single source of
truth for valid labels, the same rule Slice 2's `validate_spec` already
enforces for codebook authoring, now also enforced for hand-edits.
`404` if the extraction doesn't belong to `run_id`. `trecho_evidencia` is
intentionally not editable here — it's meant to be a verbatim quote
grounding the model's decision; hand-editing it would defeat its purpose
as an audit trail.

**`GET /runs/{run_id}/export?format=csv|xlsx|json`** (new) — streams a
file download of the run's results (same joined shape as the results
endpoint, minus internal ids). Backed by a new `src/text_as_data/export.py`
module: three pure functions
(`results_to_csv_bytes`/`results_to_xlsx_bytes`/`results_to_json_bytes`,
each `list[dict] -> bytes`), matching the existing pattern of pure,
independently-testable transform functions (`corpus_import.py`,
`pilot_v7.py`). `xlsx` reuses `openpyxl`, already a dependency; no new
package needed for any of the three formats.

## Frontend: one new screen

**`frontend/src/RunsPage.tsx`** (new), added as a third tab
(`Corpus | Codebook | Runs`) in `App.tsx`. Three states in the detail
panel, driven by which run (if any) is selected in the left list:

- **Nothing selected / "+ New run"**: a form — corpus dropdown (from
  `GET /corpora`), codebook dropdown (from `GET /codebooks`), a free-text
  model field (providers vary too much for a fixed dropdown to be
  correct), and a provider-mode toggle (API key / CLI). CLI mode reveals
  two more fields: the command (space-separated, e.g. `claude -p`, split
  client-side into the `cli_command` array the API expects) and a
  stdin/arg radio for `cli_prompt_mode`. Submitting `POST /runs` adds the
  new run to the list and selects it.
- **Selected run, status `pending`/`running`**: a progress bar
  (`processed`/`total`) that polls `GET /runs/{id}` every 2 seconds until
  the status leaves that state, then stops polling and re-renders into
  the results view below.
- **Selected run, status `done`**: the results table — one row per
  extraction, showing `document_snippet`, a `categoria` badge, and
  `justificativa`/`trecho_evidencia` (truncated with a "show more"
  toggle, since these can be long). A category filter dropdown above the
  table (client-side filter over the already-fetched rows — no new
  endpoint). Clicking a row switches its categoria/justificativa cells to
  editable inputs; Save calls the new `PUT` endpoint and refreshes that
  row in place. Three export buttons (CSV/XLSX/JSON), each a plain
  `<a href="{API_BASE}/runs/{id}/export?format=...">` with a `download`
  attribute — no client-side blob handling needed, the browser handles a
  same-shape cross-origin file download via a normal navigation.
- **Selected run, status `error`**: a plain error banner (the run's own
  extraction rows already carry per-document error messages via the
  existing `__error__` categoria convention from `extraction.py` — this
  state is for the rarer case for `run_extraction`'s own setup failure,
  e.g. a codebook that fails to parse at all).

## Error handling

Same pattern as Slice 2: every new endpoint's failure path uses
`HTTPException` with a real `detail` string (`404` unknown run/extraction,
`422` invalid categoria on edit), and the frontend surfaces it through the
existing `describeApiError`/`ApiError` machinery already in
`errorMessages.ts` — no new error-handling pattern introduced.

## Testing

- Backend: `tests/test_export.py` for the three pure `export.py`
  functions (given a small `list[dict]`, assert the bytes round-trip back
  to the same rows via `csv`/`openpyxl`/`json`). Extend
  `tests/test_app_corpora.py`-style `TestClient` tests in a new
  `tests/test_app_runs.py` for `GET /runs`, the extended
  `GET /runs/{id}/results` (asserting `document_snippet` appears), the
  new `PUT` endpoint (valid edit, invalid categoria → 422, unknown
  extraction → 404), and the export endpoint (one assertion per format
  that the response parses back to the expected rows).
- Frontend: no automated test suite, same decision as Slice 2 — manual
  browser verification (create a run, watch it complete, edit a row,
  download all three export formats, confirm no console errors) before
  calling it done.

## Explicitly out of scope for this slice

Screen 5 (Validation: gold-label import, Cohen's kappa, disagreement
review) — Slice 4. Token-cost estimation before running. Deleting a run.
Re-running/duplicating a run from the UI. Editing `trecho_evidencia`.
Pausing/cancelling a run in progress.
