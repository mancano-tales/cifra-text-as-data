# Design: Cifra ↔ QualiLab interoperability

Status: draft, revision 4 — all three planned red-team rounds complete and
incorporated; ready for user review before commit. Round 1: one Claude
subagent + agy/gemini-3.1-pro-low, against a revision-1 draft not committed
to this repo. Round 2: three independent agy runs — gemini-3.7-flash-low/
medium/high — against the committed revision 2. Round 3: a Claude subagent
+ agy/gemini-3.7-flash-high + agy/claude-sonnet-4-6, all three independent,
against the committed revision 3.

## Context

Cifra (this repo) automates qualitative-coding research: a researcher
defines a codebook (a concept + categorical labels, each with a
definition/positive examples/negative examples/boundary notes), points it
at a text corpus, and the backend calls an LLM to categorize each
document — with a validation step (Cohen's kappa, precision/recall/F1 per
category against human-coded gold labels) as the project's stated
scientific differentiator (see `AGENTS.md` § "Why the validation step is
not optional").

QualiLab (`github.com/luizpf42/QualiLab`, MIT, single-maintainer personal
project, single-file browser app, no server of its own, no plugin
architecture by explicit author decision) is a manual QDA tool with
BYOK AI-assist features of its own — but capped at ~600k chars per send,
synchronous in the open browser tab, no persistent job queue, and a
validation feature that explicitly disclaims statistical rigor. See
`AGENTS.md` § "Why not a single-file HTML tool like QualiLab" (2026-09-01
correction) for the full comparison and why building Cifra's features
inside QualiLab's codebase was ruled out.

This spec is the alternative the project settled on: interoperate through
QualiLab's own open, documented `.qualilab` file format rather than a
shared codebase — logged as a priority item in `TODO.md` (not a someday
nice-to-have) at the author's explicit request (2026-09-02).

## Verified facts (checked against real QualiLab source, not assumed)

Checked by cloning `luizpf42/QualiLab` (v1.4.50) and reading
`README.en.md`, `docs/MANUAL.en.md`, and its own shipped example fixture
`examples/QualiLab_synthetic_realistic_legal_ai_3.qualilab` directly —
several claims below were only caught by parsing the real fixture, not by
trusting the README's prose.

- **Container format**: first 2 bytes `PK` = zip (containing `project.json`
  plus `pdfs/<docId>.pdf` and `pdfindex/<docId>.json`, neither of which
  Cifra needs — QualiLab already extracts plain text into
  `documents[].content` regardless of source format); otherwise the whole
  file is `project.json` as plain UTF-8 text. This is QualiLab's own
  documented read algorithm.
- **`documents[]` shape**: `{id, name, content}` (`id` is a string like
  `"doc-1"`, `content` is plain extracted text).
- **`doc_values[]` shape**: `{id, document_id, category_id, value,
  set_by, author_name, layer}`. Observed `layer` values: `"final"`
  (team-consolidated reference) and `"individual"` (per-researcher).
- **`codings[]` shape**: `{id, document_id, code_id, span_start,
  span_end, quote, layer, author_name}` — passage-level (highlight spans
  within a document), not document-level. Not used by this design:
  Cifra's `categoria` is one label per document, which maps onto a
  QualiLab **attribute value** (`doc_values`), not a passage code.
- **Schema drift is real and bigger than the README's own top-level-key
  list suggests.** The README documents 9 top-level `project.json` keys:
  `_meta, documents, attributes, doc_values, codes, codings, memos,
  ia_results, ia_memory`. The actual shipped fixture has:
  `_meta, documents, categories, doc_values, codes, codings, memos` —
  `attributes` is called `categories` on disk, and `ia_results`/
  `ia_memory` are **absent entirely**, not merely renamed. 3 of 9
  documented keys deviate from a real file the project ships as its own
  example. No `_meta` schema-version field exists to branch on.
- **Invariant**: `coding.quote == document.content[span_start:span_end]`
  for every coding — verified against all 288 codings in the fixture
  during the first review round, zero failures. Any code that writes into
  an existing `.qualilab` file must not disturb this for codings it
  doesn't touch.
- **Vocabulary mismatch**: QualiLab attribute `options` are natural-language
  strings a researcher typed into a UI dropdown (e.g. `"Ambivalente"`,
  `"Não informado"`); Cifra codebook `label`s are short machine-style enum
  strings (`codebook.py`'s own example: `protest`/`not_protest`). These
  will essentially never match by exact string comparison.
- **QualiLab's own extensibility stance** (README, quoted directly):
  "QualiLab has no plugin architecture, and does not intend to have one:
  it clashes head-on with the single-file design... What it offers
  instead are three open surfaces: the `.qualilab` format (lossless,
  documented), export to REFI-QDA and W3C Web Annotation, and a read-only
  MCP server." This design uses exactly that surface.
- **QualiLab's own threat model** (`SECURITY.md`) explicitly lists a
  "malformed or hostile file that hangs the browser, corrupts the
  project, or escapes intended processing" as in scope — a `.qualilab`
  routinely moves between researchers, it is not always self-generated.
  Relevant to this design's own file-handling, below.

## Round-1 red-team findings and how this revision addresses them

Two independent reviewers (a Claude subagent with file access to the real
QualiLab clone and this repo; `agy` running gemini-3.1-pro-low with the
same access) reviewed a revision-1 draft. Findings, deduplicated:

| # | Finding | Source | Resolution in this revision |
|---|---|---|---|
| 1 | Document identity does not survive import: `DocumentRecord` has no external-id column, and reusing the CSV import path discards any id QualiLab supplies — export cannot map extractions back to the right document. | Both | New `external_id` column on `DocumentRecord` (§ Data model), populated only by a dedicated QualiLab-import path, not the CSV path. |
| 2 | No table exists to persist a reference to the source `.qualilab` bytes for a later export, and even if one did, caching bytes at import time for a delayed export risks silently overwriting the researcher's manual work done in QualiLab in the meantime (no merge tool exists). | Claude (gap), agy (risk) | Export takes the researcher's **current** file as a fresh upload in the same request (§ Export), never a cached copy. No new table needed — the gap and the risk dissolve together. |
| 3 | Parsing an untrusted zip/JSON upload with no size guard risks a decompression-bomb-style memory exhaustion, which would crash the backend and kill in-flight LLM runs — explicitly in QualiLab's own stated threat model for the same file type. | Both | Size caps before any parse (§ Security). |
| 4 | Schema drift is wider than "categories vs. attributes" — `ia_results`/`ia_memory` are absent in the real fixture too. | Claude | Defensive `.get(key, default)` across all documented top-level keys, not a special case for one. |
| 5 | Exact-string label matching between QualiLab's natural-language options and Cifra's enum-style codebook labels will reject nearly everything in real use. | Claude | Explicit `value_mapping` required from the researcher (§ Gold-label import) rather than fuzzy/auto matching — this is scientific ground-truth data; a wrong silent match is worse than a blocked import. |
| 6 | Partial-success gold-label import (report mismatches, import the rest) can introduce a systematic — not random — bias into the human-coded gold set, undermining the kappa/precision/recall this project treats as non-optional. | agy | Gold-label import is all-or-nothing: any unmapped/invalid value blocks the entire request, with the full list of problems returned at once. |
| 7 (minor) | Re-importing an updated `.qualilab` to refresh an existing corpus has no design — it collides with the existing 409-on-duplicate-name convention. | Claude | Out of scope for this revision; a corpus import is a one-time snapshot. Logged as a follow-up in `TODO.md`, not solved here. |

## Round-2 red-team findings and how this revision addresses them

Three independent `agy` runs (gemini-3.7-flash-low/medium/high, each given
the same instructions and file access, told not to repeat round-1
findings) reviewed the committed revision-2 spec. All three independently
converged on the `doc_values.id`/export-validation gaps below — treated as
high-confidence given the agreement. The `gemini-3.7-flash-high` run went
as far as reading QualiLab's actual `docs/index.html` source (not just its
README/manual) for two of its findings, cited by line number.

| # | Finding | Source | Resolution in this revision |
|---|---|---|---|
| 8 | Injected `doc_values` entries have no `id`, which QualiLab's own code requires to be unique per entry (confirmed against `docs/index.html`); a hardcoded `set_by: "cifra"` string also risks a unique-constraint collision under `(document_id, category_id, set_by, layer)` in QualiLab's cloud-sync mode, where `set_by` is expected to be a real user id or `null`. | low, medium, high (all three) | Deterministic `id` per injected entry (formula finalized in round 3, finding #18, below). `set_by: null` (not a string), identity carried only in `author_name: "Cifra (<model>)"`. The deterministic id is intended to double as re-export idempotency — round 3 (finding #13) found this wasn't actually specified yet at this point in the design; see below for the fix. |
| 9 | Export injects raw Cifra category labels (e.g. `"protest"`) into `doc_values.value` with no check against the target QualiLab category's declared `options` — QualiLab's UI renders an unmatched value as blank/unselected, making the exported extraction invisible in its own tool. | medium, high (high cites `index.html`'s `CategoryValue` check by line) | Export requires an explicit `reverse_value_mapping: dict[str, str]` (Cifra label → QualiLab option string), symmetric to import's `value_mapping`. Reject up front if `category_id` isn't in the uploaded project's categories/attributes, or if any mapped value isn't one of that category's `options`. |
| 10 | Export can silently "succeed" with zero effect: a corpus with no `external_id`s (e.g. one imported via CSV, not QualiLab) or an unrelated/wrong `.qualilab` upload produces a `200` response with 0 documents matched and 0 values injected — indistinguishable from success to the caller. | high | Reject with `422` if either the corpus has zero documents with a non-null `external_id`, or zero of them match the uploaded file's `documents[].id`. On any non-zero result (full or partial match), the response body reports matched/skipped counts explicitly — partial mismatch (some documents edited/deleted since import) stays a reported skip, not silent. |
| 11 | Gold-label import's all-or-nothing rule validates *mapped values*, but says nothing about documents with no `doc_values` entry for the chosen category/layer at all (QualiLab leaves these absent or `""`) — these silently produce a smaller gold set with no signal to the researcher, which risks a non-random (not just smaller) sample if missingness correlates with anything about the document. | low, medium | Import response always reports coverage: how many of the corpus's documents had a usable value for the chosen category/layer vs. total. This is a report, not an additional block — the project's own V7 pilot work (`TODO.md`) already established that small, partial gold sets are a normal, expected state to work from, not an error condition; forcing 100% coverage before any import would contradict that. |
| 12 (documented limitation, not fixed) | Exporting more than one run against the same base `.qualilab` file requires sequential re-upload (export run A → researcher saves the result → re-upload that file to export run B); concurrent exports of two runs against the same original file diverge with no merge path. | high | Documented under Explicit non-goals, below — not solved in this revision. The deterministic-id design (finding #8) at least makes re-exporting the *same* run against a newer copy of the file idempotent (it replaces its own prior entries rather than duplicating them), which covers the common case of "re-export after the researcher pulled in edits." |

## Round-3 red-team findings and how this revision addresses them

A Claude subagent and `agy`/gemini-3.7-flash-high independently reviewed
the committed revision-3 spec (a third `agy` run, on `claude-sonnet-4-6`,
was still in progress at the time of this revision and will be folded in
separately if it adds anything new). Both converged on the same critical
bug in round-2's own fix.

| # | Finding | Source | Resolution in this revision |
|---|---|---|---|
| 13 | **Finding #8's "idempotent re-export" claim was asserted, not specified.** A deterministic `doc_values.id` does not by itself cause replacement — the design's own wording ("appends one new entry... deterministic, so re-exporting replaces its prior entry") describes an append with no upsert step. Re-exporting a file that already contains a prior Cifra entry would produce two `doc_values` rows sharing one id — reintroducing the exact non-uniqueness problem finding #8 existed to fix. The round-2 testing bullet was also ambiguous enough that a naive "upload the same original bytes twice" test would pass even with pure `.append()`, masking the bug. | Claude, high, and agy/claude-sonnet-4-6 (all three independently — the strongest convergence of any finding across all rounds) | `inject_extractions_into_qualilab` now explicitly specifies an upsert step (below) — filter out any existing `doc_values` entry whose `id` matches before appending the new one. The test is rewritten to chain export output back in as export input (below), not to reuse the original bytes twice. |
| 14 | `HumanLabelRecord`'s deliberate multi-row-per-document design (finding #6, kept from round 1) is incompatible with the only validation code that already exists: `validation.py`'s `agreement_report()` does a plain `predicted.merge(gold, on=id_col)`, which assumes one gold row per document. Feeding a multi-coder gold set into it fans out each predicted row across every coder's row for that document, silently inflating N and corrupting accuracy/kappa. | Claude | See § "Gold-standard reduction to one row per document," new below — resolved for the default path (`layer="final"`), explicitly deferred for the multi-coder case (`layer="individual"`), which is future work this design intentionally does not solve. |
| 15 | Missing parameters: the `export-qualilab` endpoint's field list never listed `category_id`, even though `inject_extractions_into_qualilab` requires it — unusable for any project with more than one category. `qualilab_doc_values_to_human_labels`'s signature had no way to resolve a QualiLab string document id to Cifra's integer `DocumentRecord.id` for the `human_labels.document_id` foreign key, nor to compute `coverage` against the total corpus. | high, and agy/claude-sonnet-4-6 (both independently) | Both signatures corrected below (`category_id` added to the endpoint; `documents: list[DocumentRecord]` added to the function). |
| 16 | Undefined transport: the export endpoint was specified to return both the binary `.qualilab` file and a JSON body of matched/skipped counts — not possible in one HTTP response without saying how. | high | Counts travel as response headers (`X-Cifra-Matched-Count`, `X-Cifra-Skipped-Count`) alongside the binary file body, specified below. |
| 17 (minor) | No error handling specified for malformed input in `open_qualilab_project` (bad JSON, corrupt zip) — existing CSV/XLSX endpoints catch decode/parse failures and return `400`; an unhandled `json.JSONDecodeError`/`zipfile.BadZipFile` here would fall through to a `500`, inconsistent with repo convention. | Claude | `open_qualilab_project` catches both and raises the same `HTTPException(400, ...)` pattern the CSV/XLSX endpoints already use. |
| 18 | The deterministic id formula used Cifra's internal integer `document_id`, not QualiLab's stable string `external_id`. It works for uniqueness today, but if the SQLite database is ever wiped and recreated, a new run against the "same" corpus gets new integer PKs — so a later re-export's generated ids would no longer match the ones already sitting in the file, and finding #13's upsert step would silently fail to find them (an append, not a replace, despite the fix). | agy/claude-sonnet-4-6 | Formula changed to `f"cifra-{run_id}-{doc.external_id}-{category_id}"` throughout this document — stable across database resets, and incidentally more human-readable inside an opened `.qualilab` file. |

**Independently verified, not just asserted**: `agy`/claude-sonnet-4-6 grepped QualiLab's actual `docs/index.html` (`addDocValue`, `setDocValue`, and the file-load path `JSON.parse(...)` at line 8386) and confirmed `doc_values[].id` values are preserved verbatim when QualiLab loads a `.qualilab` file from disk — i.e., this design's whole approach (read the raw JSON, mutate the `doc_values` array, re-serialize) is sound in principle; the bug was specifically in *how* the mutation was specified (finding #13), not in the underlying strategy.

### Gold-standard reduction to one row per document (finding #14)

`agreement_report()` requires exactly one gold value per document. QualiLab's
`"final"` layer is, by its own definition ("team-consolidated reference"),
expected to already be at most one entry per `(document_id, category_id)` —
so the default and recommended gold-label import path (`layer="final"`) is
safe by construction, *if* that expectation actually holds in the uploaded
file. `qualilab_doc_values_to_human_labels` now enforces this rather than
assuming it: importing with `layer="final"` and finding more than one
`doc_values` entry for the same `(document_id, category_id)` is treated as
malformed input and rejected (this would itself be a QualiLab data anomaly,
not a normal state).

Importing with `layer="individual"` (multiple coders/double-blind) still
produces multiple `human_labels` rows per document by design — this data is
useful for future inter-rater-reliability work, but **must not** be passed
directly to today's `agreement_report()`, which would silently corrupt its
merge. This design does not build that reduction step (picking or
aggregating across coders is a validation-methodology decision, not an
interop-plumbing one) — it is called out here explicitly as a constraint
the eventual Validation screen (Slice 4, unplanned, per coordination with
the peer session building Slice 3) must account for, not something this
revision silently leaves for someone to discover the hard way.

## Design

### Data model changes (`src/text_as_data/db.py`)

```python
class DocumentRecord(SQLModel, table=True):
    __tablename__ = "documents"
    id: int | None = Field(default=None, primary_key=True)
    corpus_id: str
    text: str
    metadata_json: str = "{}"
    external_id: str | None = None   # NEW — QualiLab's own doc id ("doc-1"), or
                                      # any future source's native id. None for
                                      # CSV/XLSX/paste-imported documents.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HumanLabelRecord(SQLModel, table=True):
    __tablename__ = "human_labels"
    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id")
    codebook_id: int = Field(foreign_key="codebooks.id")
    category: str
    coder: str            # QualiLab author_name/set_by, or "manual" for
                           # labels entered directly in Cifra (future).
    source: str = "manual" # "qualilab_import" | "manual"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`HumanLabelRecord` allows multiple rows per document deliberately — a
QualiLab double-blind project produces one `doc_values` row per coder per
category, and this table preserves that instead of assuming a single
ground truth per document. No `corpora` table is introduced: it is not
needed once export stops depending on a cached original file (finding #2).

### New module `src/text_as_data/qualilab_interop.py`

- `open_qualilab_project(content: bytes) -> dict` — enforces a raw-upload
  size cap (50 MB) before touching the bytes. Detects `PK` magic bytes;
  if zip, reads the `project.json` `ZipInfo` entry and checks its
  declared uncompressed `file_size` against the same cap **before**
  calling `.read()` (a bomb is caught without ever decompressing it);
  else parses the whole byte string as UTF-8 JSON. Reads every top-level
  key defensively (`project.get("documents", [])`,
  `project.get("categories") or project.get("attributes") or []`, etc.) —
  no key is assumed present per finding #4. Catches
  `json.JSONDecodeError` and `zipfile.BadZipFile` and raises the same
  `HTTPException(400, ...)` pattern the existing CSV/XLSX endpoints
  already use for malformed input (finding #17) — not left to fall
  through to an unhandled `500`.
- `qualilab_documents_to_records(project: dict, corpus_id: str) ->
  list[DocumentRecord]` — maps `documents[].{id, name, content}` directly
  to `DocumentRecord(text=content, external_id=id, ...)`. A dedicated
  function, not a reuse of the CSV row-import path (finding #1) — the
  row shapes are genuinely different (CSV rows have no stable id to
  preserve).
- `qualilab_doc_values_to_human_labels(project, category_id, codebook_id,
  documents: list[DocumentRecord], value_mapping: dict[str, str],
  layer="final") -> ImportResult` — `documents` is the corpus's own
  `DocumentRecord` rows (needed to resolve a `doc_values.document_id`
  string like `"doc-1"` to the matching row's integer `id` via
  `external_id`, for `human_labels.document_id`, and to compute
  `coverage` against the true corpus size — both missing from revision 3's
  signature, finding #15). Filters `doc_values` by `category_id` and
  `layer`; for each value, looks it up in `value_mapping` (QualiLab option
  text → codebook category label) and validates the result against the
  target codebook's actual category labels. **All-or-nothing on mapping
  validity** (finding #6): if any present value has no mapping entry, or
  maps to something that isn't a real codebook category, the function
  returns the full list of problems and writes nothing. With
  `layer="final"`, more than one `doc_values` entry for the same
  `(document_id, category_id)` is rejected as malformed input (finding
  #14 — this is what keeps the default gold-import path safe for
  `agreement_report()`'s one-row-per-document assumption). Separately,
  `ImportResult` always carries a `coverage` field —
  `documents_with_value / total_corpus_documents` — for documents with no
  `doc_values` entry at all for this category/layer (finding #11): this
  is reported, not blocking, matching the project's existing acceptance
  of small/partial gold sets (see `TODO.md`'s V7 pilot notes).
- `inject_extractions_into_qualilab(project: dict, extractions: list[...],
  documents: list[DocumentRecord], category_id: str,
  reverse_value_mapping: dict[str, str], run_id: int) -> bytes` — first
  validates `category_id` exists in the uploaded project's
  categories/attributes and that every extraction's `categoria`, mapped
  through `reverse_value_mapping`, is one of that category's declared
  `options` (finding #9); rejects the whole export otherwise, before
  writing anything. Matches each extraction's document to the uploaded
  project's `documents[].id` via `DocumentRecord.external_id`. **Rejects
  with 422 if zero documents match** — a corpus with no `external_id`s
  (e.g. CSV-imported) or an unrelated/wrong `.qualilab` upload must not
  return a silent no-op `200` (finding #10); documents that do have an
  `external_id` but aren't found in this particular upload (edited/deleted
  since import) are skipped and counted, not errored, as long as at least
  one document matched. For each matched document, computes the
  deterministic id `f"cifra-{run_id}-{doc.external_id}-{category_id}"`,
  then **first removes any existing entry in `project["doc_values"]`
  whose `id` equals that value, then appends the new entry** — an
  explicit remove-then-append (upsert) step, not a bare append (finding
  #13: earlier wording asserted idempotency without specifying this step,
  and three independent reviewers across two model families caught that
  the claim didn't match the implementation it described). The new
  entry: `layer: "individual"` (a value QualiLab's schema already
  expects), `author_name: "Cifra (<model>)"`, `set_by: null` (not a
  string — QualiLab's schema expects `set_by` to be a real user id or
  null, and a made-up string risks a unique-constraint collision under
  `(document_id, category_id, set_by, layer)` in cloud-sync mode, finding
  #8). Returns the updated project re-serialized in the same container
  shape it was read in (zip stays zip, with the original
  `pdfs/`/`pdfindex/` entries carried through untouched; plain JSON stays
  plain JSON).

### New API endpoints (`src/text_as_data/app.py`)

- `POST /corpora/import-qualilab` — multipart file upload. Uses
  `open_qualilab_project` + `qualilab_documents_to_records`. Same
  duplicate-corpus-name 409 convention as the existing CSV/XLSX
  endpoints. Response includes each created document's `id` and
  `external_id` pair, for the frontend to use in the next step.
- `POST /corpora/{corpus_id}/import-qualilab-labels` — multipart:
  the `.qualilab` file again, `codebook_id`, `category_id`, `layer`
  (default `"final"`), `value_mapping` (JSON object). All-or-nothing on
  mapping validity per finding #6: `422` with a rich error body listing
  every unmapped value on failure; `201` on success with the count of
  `human_labels` rows created plus the `coverage` report (finding #11).
- `POST /runs/{run_id}/export-qualilab` — **`POST`, not `GET`** (finding
  #2): multipart, requires the researcher's current `.qualilab` file in
  the request body, plus **`category_id: str = Form(...)`** (finding
  #15 — not just the target codebook, since a run can only ever inject
  into one category, and this must come from the caller rather than be
  inferred) and `reverse_value_mapping` (finding #9). No server-side
  caching of any prior upload. `422` if `category_id` is missing from the
  uploaded file's categories/attributes, any mapped value isn't a
  declared option (finding #9), or zero documents matched by
  `external_id` (finding #10). On success, returns the updated file
  (same container shape as the upload, `Content-Type:
  application/octet-stream` or the zip/JSON equivalent) as the response
  body, with matched/skipped document counts in response headers
  (`X-Cifra-Matched-Count`, `X-Cifra-Skipped-Count`, finding #16 — a
  single HTTP response can't carry both a binary attachment and a JSON
  body, so counts travel as headers instead).

### Security

- Raw upload size cap: 50 MB (generous for a text-only QDA project;
  QualiLab itself caps a single AI send at ~200 pages, so a real research
  corpus is well under this).
- Zip entries are size-checked via `ZipInfo.file_size` before any `read()`
  call — a crafted high-ratio entry is rejected without ever being
  decompressed.
- No other zip entries (`pdfs/`, `pdfindex/`) are ever parsed or loaded
  into memory — they are only carried through byte-for-byte on export, if
  present, so PDF-parsing is never in Cifra's attack surface at all.

### Testing

- Copy the real fixture `examples/QualiLab_synthetic_realistic_legal_ai_3.qualilab`
  (MIT, from QualiLab's own repo) into `tests/fixtures/`, with a short
  attribution note in the test file, and test against it directly — real
  data is what caught findings #1 and #4 in round 1; synthetic mocks
  would not have.
- Unit tests: zip vs. plain-JSON detection; zip-bomb rejection via a
  crafted `ZipInfo` with an inflated `file_size`; `external_id` round-trip
  from import through to export matching; all-or-nothing rejection with a
  deliberately incomplete `value_mapping`; export preserving the
  `quote == content[span_start:span_end]` invariant for codings the
  export path never touches; export against a file where a document was
  deleted since import (must skip + report, not crash); export rejects
  with 422 on zero matched documents (CSV-imported corpus, and an
  unrelated `.qualilab` upload); export rejects when a mapped value isn't
  a declared `option` for the target category; re-export idempotency
  tested as a **chain**, not a repeat — export run A against the original
  fixture, then export run A *again* using the first export's own output
  bytes as the second call's uploaded file, and assert the result still
  has exactly one `doc_values` entry per document (finding #13 — a test
  that instead uploads the original fixture bytes twice would pass even
  with a bare `.append()`, and must not be used); gold-label import's
  `coverage` report reflects a deliberately partial fixture correctly;
  `layer="final"` import rejects a fixture deliberately edited to contain
  two `doc_values` entries for the same `(document_id, category_id)`
  (finding #14's guard).

## Explicit non-goals (this revision)

- Re-importing an updated `.qualilab` into an existing corpus (finding
  #7) — a corpus import is a one-time snapshot today.
- Importing QualiLab `codings` (passage-level highlights) — only
  `doc_values` (document-level attribute answers) are in scope; codings
  don't aggregate to a single document label without an arbitrary rule.
- Anything involving the `pdfs/`/`pdfindex/` zip entries beyond carrying
  them through unmodified on export.
- Merging concurrent exports of two different runs against the same base
  file (finding #12) — exporting run B after run A requires re-uploading
  run A's output first; there is no automatic merge of two divergent
  files. The deterministic `doc_values.id` (finding #8) makes re-exporting
  the *same* run idempotent, which covers "pull in the researcher's edits
  and re-export," but not "combine two different runs' outputs."
