# Slice 4 — Validation Screen (Design)

> Decided 2026-09-02 via brainstorming with the author. Covers `AGENTS.md`
> Screen 5 (Validation) — the last unbuilt screen from the original MVP
> list. Coordinated with a peer Claude Code session (`text-as-data-8a`)
> working on QualiLab interoperability in parallel: they own
> `HumanLabelRecord` and the QualiLab import/export endpoints; this slice
> owns the Validation UI/report endpoints and a QualiLab-independent
> plain-CSV gold-label import path, both consuming `human_labels` rows
> regardless of which path wrote them.

## Why this scope, and the cross-session dependency

`AGENTS.md`'s Validation scope: "import a human-labeled subset (gold
standard), compare against the LLM output, compute accuracy, Cohen's
kappa, precision/recall/F1 per category, and list disagreements." Two
things are missing to build this today:

1. **No `human_labels` table exists yet.** A peer session's QualiLab
   interop design (`docs/superpowers/specs/2026-09-02-qualilab-interop-design.md`,
   revision 4, three red-team rounds) specifies one:
   `HumanLabelRecord(id, document_id, codebook_id, category, coder,
   source, created_at)`, deliberately allowing multiple rows per
   document (a QualiLab double-blind project has one row per coder). That
   spec is not yet implemented in `db.py` as of this design — the peer
   session owns landing it. This design is written against that spec'd
   shape and blocks on it for the DB-touching tasks; the report/UI logic
   can be designed and partly built (validation.py's pure functions)
   independent of exactly when it lands.
2. **`agreement_report()` only computes accuracy + Cohen's kappa.**
   Precision/recall/F1 per category, explicitly asked for in `AGENTS.md`,
   isn't implemented. `scikit-learn` (already a dependency, used for
   kappa) has `precision_recall_fscore_support` — cheap to add.

**Multi-coder documents are excluded from a validation report, not
resolved.** If a document has more than one `human_labels` row for the
run's codebook (e.g. a QualiLab "individual"-layer import with two
coders), `agreement_report()`'s one-row-per-document assumption breaks.
Rather than silently pick one or average, those documents are reported as
excluded with a count — picking or aggregating across coders is a
validation-methodology decision, not something this slice should decide
on the researcher's behalf. This mirrors the QualiLab interop spec's own
explicit stance on the same problem (its finding #14).

## UI: an action inside the Runs screen, not a separate tab

A validation report only makes sense in the context of one specific run
(its corpus + codebook + predictions) — a separate "Validation" tab would
just mean re-selecting the same run from scratch. Instead, `ResultsTable`
gains a "Validate" section below the existing filter/export controls,
visible once a run's results are loaded:

- **No gold labels yet for this codebook**: an upload form — pick a CSV
  file, submit. Below it, a short explanation: "Export this run's
  results, fill in `gold_categoria` for the rows you've hand-reviewed,
  and upload that file here" (see "Gold-label CSV format" below for why
  it's shaped this way).
- **Some gold labels exist**: the report — coverage line ("14 of 26
  documents have a gold label; 2 excluded, multiple coders"), a
  per-category table (accuracy, kappa, precision, recall, F1), and a
  disagreement list (document snippet, predicted category, gold
  category), reusing the same `document_snippet` pattern already
  established in `ResultsTable`. An "Upload more gold labels" control
  stays available — validation coverage is expected to grow over time as
  a researcher hand-codes more of the sample, not be a one-shot action.

## Gold-label CSV format: reuse the results export, don't invent a new one

The CSV a researcher uploads has the exact same columns
`GET /runs/{run_id}/export?format=csv` already produces, plus one more:
`gold_categoria`. The intended workflow: export a run's results, open it
in a spreadsheet, fill in `gold_categoria` by hand for whichever rows
were manually reviewed (leave the rest blank), upload that same file
back. This was chosen over a from-scratch minimal format (`document_id` +
`gold_categoria` only) because:

- It closes the loop with a screen this slice already ships (the export
  buttons from Slice 3) instead of asking the researcher to construct a
  file from nothing.
- Matching by `document_id` (already a real column in the export) avoids
  fragile text-matching — no ambiguity from near-duplicate documents,
  no dependency on an external id system the way QualiLab import needs
  one.
- A blank `gold_categoria` cell is a natural, low-friction way to
  represent "not yet reviewed" — matches this project's established
  acceptance of small/partial gold sets (the V7 pilot's own real
  validation data, per `AGENTS.md`, was 1-7 usable rows, not a complete
  set).

Rows with an empty/missing `gold_categoria` are skipped (not an error).
Rows with a non-empty `gold_categoria` that doesn't match one of the
codebook's real category labels reject the **entire** upload with a list
of every bad row — a typo silently accepted as if it were a real category
would corrupt the gold set for every future validation report against
this codebook, and it's better caught immediately than after the fact
(same reasoning the QualiLab interop spec uses for its own all-or-nothing
validity rule, applied to this simpler path). This differs from
*coverage* (how many rows are filled in), which is never blocking.

## Backend

**`src/text_as_data/validation.py`** (extend, don't replace):
`agreement_report()` gains precision/recall/F1 per category via
`sklearn.metrics.precision_recall_fscore_support` (`average=None`,
per-label), added to each column's existing `{"accuracy", "kappa"}` dict
as `{"precision", "recall", "f1"}` — one number per category label,
matching the codebook's own labels, not a single averaged score (a
per-category breakdown is what actually reveals a codebook that's fine on
the majority class and unreliable on a rare one, which is exactly the
failure mode `AGENTS.md`'s "why validation is not optional" section is
about).

**New endpoints in `src/text_as_data/app.py`** (blocked on `HumanLabelRecord`
landing in `db.py`; everything else in this slice can proceed first):

- `POST /runs/{run_id}/gold-labels` — multipart CSV upload. Parses via
  the existing `corpus_import.parse_csv_rows` (already handles UTF-8-sig
  BOM, already a dependency — no new CSV-parsing code needed). Validates
  every non-empty `gold_categoria` against the run's codebook labels
  (reusing the same `spec_from_yaml_string(...)["categories"]` pattern
  `PUT /runs/{id}/results/{id}` already uses); `422` with the full list of
  bad rows if any fail. On success, writes one `HumanLabelRecord` per
  non-empty row (`coder="manual"`, `source="manual"`, `codebook_id` from
  the run) and returns `{"imported": N, "skipped_blank": M}`.
- `GET /runs/{run_id}/validation` — loads the run's extractions and the
  codebook's `human_labels` (filtered to documents in the run's corpus),
  groups gold labels by `document_id`, excludes any document with more
  than one gold row (counted, not silently resolved), builds the
  matching `predicted`/`gold` DataFrames `agreement_report()` already
  expects, and returns `{"coverage": {"labeled": N, "total": N,
  "excluded_multi_coder": N}, "per_category": {...}, "disagreements":
  [...]}` — `disagreements` entries include `document_snippet` (same
  160-char convention as results) for context, not just the two labels.

## Error handling

Same pattern as every prior slice: `HTTPException` with a real `detail`
string, no new pattern. `404` for an unknown run; `422` for an invalid
`gold_categoria` value (whole-upload rejection, with every bad row
listed, not just the first) or a malformed CSV (missing `document_id` or
`gold_categoria` column — reuses `corpus_import`'s existing missing-column
error shape).

## Testing

- `tests/test_validation.py` (new or extended, matching whatever the
  existing validation tests file is named) — `precision_recall_fscore`
  addition to `agreement_report()`, using a small synthetic
  predicted/gold pair with a known confusion pattern (so precision/recall
  differ from a trivial 100%-agreement case, actually exercising the
  metric rather than just confirming it runs).
- `tests/test_app_validation.py` (new) — gold-label upload (valid file,
  invalid category rejected whole-upload, blank cells skipped not
  errored), the validation report endpoint (coverage numbers, a
  deliberately-injected multi-coder document excluded and counted,
  disagreements list content), following the existing `TestClient` +
  `FakeProvider` pattern from `test_app_runs.py`.
- Frontend: no automated suite, same decision as every prior slice —
  manual browser verification (upload a gold CSV via the actual export
  round-trip, confirm the report renders, confirm re-uploading with more
  filled rows increases coverage) before calling it done.

## Explicitly out of scope for this slice

Resolving/aggregating multi-coder gold labels into one value (excluded
and reported instead — a future methodology decision, not blocked on
here). A UI for browsing/editing individual `human_labels` rows outside
the CSV upload flow. Any QualiLab-specific import/export UI (the peer
session's slice, consumed here only through the shared `human_labels`
table). Re-validating automatically when new extractions are edited via
`PUT /runs/{id}/results/{id}` — the report is generated on demand via
`GET /runs/{run_id}/validation`, not cached or auto-recomputed.
