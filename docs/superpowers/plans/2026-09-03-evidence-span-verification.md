# Evidence Span Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that `trecho_evidencia` (the LLM's quoted evidence span) actually appears verbatim in the source document, instead of trusting it blindly, and record the verification result on every extraction for the researcher to see.

**Architecture:** A small pure function, `verify_evidence_span(span, document_text) -> (verified, tier)`, does a two-tier check — exact substring match, then a normalized (quotes/dashes/whitespace-folded, lowercased) substring match — and never falls back to fuzzy/similarity matching. `run_extraction()` in `extraction.py` calls it once per fresh extraction and persists the result on two new `ExtractionRecord` columns. A cache hit copies the prior verification result instead of recomputing it. This ports the design from [QualiHolo](https://github.com/LuizPF42/QualiHolo)'s `verifySpan()`, credited in [issue #2](https://github.com/mancano-tales/decifra-text-as-data/issues/2). Per that issue's resolved open question, a failed verification is *flagged* (recorded, visible on the row), not used to invalidate `categoria` — consistent with this repo's stance (`AGENTS.md`'s Product Vision) that the researcher's judgment, not the software, makes the call on whether output is usable.

**Tech Stack:** Python 3.10+, SQLModel/SQLite (existing `_ensure_columns` additive-migration mechanism in `db.py` — no new migration code needed), pytest.

---

## File Structure

- **Modify: `src/text_as_data/extraction.py`** — add `verify_evidence_span()` (and its private normalization helper) near the top of the file, call it from `run_extraction()`.
- **Modify: `src/text_as_data/db.py`** — add `evidence_verified: bool` and `evidence_match_tier: str` to `ExtractionRecord`.
- **Create: `tests/test_evidence_verification.py`** — unit tests for `verify_evidence_span()` in isolation (exact match, normalized match, no match, empty, too-short).
- **Modify: `tests/test_extraction_run.py`** — one integration test confirming `run_extraction()` persists the verification result, and that a cache hit copies it rather than recomputing.
- **Modify: `tests/test_db_migration.py`** — one migration test confirming the two new columns backfill cleanly on a pre-existing `extractions` table, mirroring the existing `runs`-table test in the same file.

No frontend changes in this plan — the Results table (`frontend/src/ResultsTable.tsx`) doesn't display `trecho_evidencia` at all today, so surfacing `evidence_verified` there is a separate, later concern, not bundled into this port.

---

### Task 1: `verify_evidence_span()` — exact and normalized matching

**Files:**
- Modify: `src/text_as_data/extraction.py` (add near the top, after the imports at line 8, before the existing `extract()` function at line 10)
- Test: `tests/test_evidence_verification.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_evidence_verification.py`:

```python
from text_as_data.extraction import verify_evidence_span


def test_exact_substring_match_is_verified_as_exact():
    verified, tier = verify_evidence_span("about 200 people occupied the square", "Yesterday, about 200 people occupied the square in front of city hall.")
    assert verified is True
    assert tier == "exact"


def test_curly_quotes_and_em_dash_still_verify_as_normalized():
    document = "The mayor said “this will not stand” — a clear escalation."
    span = "\"this will not stand\" - a clear escalation"
    verified, tier = verify_evidence_span(span, document)
    assert verified is True
    assert tier == "normalized"


def test_collapsed_whitespace_and_case_still_verify_as_normalized():
    document = "The   protest   spread   to    three   other   cities overnight."
    span = "the protest spread to three other cities"
    verified, tier = verify_evidence_span(span, document)
    assert verified is True
    assert tier == "normalized"


def test_fabricated_span_not_found_in_document_fails():
    verified, tier = verify_evidence_span("the union called for a general strike", "About 200 people occupied the square in front of city hall.")
    assert verified is False
    assert tier == "not_found"


def test_empty_span_fails_as_empty():
    verified, tier = verify_evidence_span("", "About 200 people occupied the square.")
    assert verified is False
    assert tier == "empty"


def test_whitespace_only_span_fails_as_empty():
    verified, tier = verify_evidence_span("   ", "About 200 people occupied the square.")
    assert verified is False
    assert tier == "empty"


def test_span_too_short_after_normalization_fails_as_too_short():
    # "The Cat" is not a literal substring of the document (so the exact
    # tier can't match), and its normalized form ("the cat", 7 characters)
    # is under the 8-character cutoff -- too short to trust as
    # distinguishing evidence even before attempting the normalized
    # substring search, mirroring QualiHolo's own short-span cutoff.
    verified, tier = verify_evidence_span("The Cat", "The mayor made a statement about the protest.")
    assert verified is False
    assert tier == "too_short"


def test_near_miss_paraphrase_is_not_verified_even_though_it_is_similar():
    # Never falls back to fuzzy/similarity matching -- a near-miss is a
    # failure, on purpose (this is the whole point of the check).
    document = "About 200 demonstrators occupied the square in front of city hall."
    span = "about 200 people occupied the square near city hall"
    verified, tier = verify_evidence_span(span, document)
    assert verified is False
    assert tier == "not_found"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_evidence_verification.py -v`
Expected: FAIL with `ImportError: cannot import name 'verify_evidence_span'`

- [ ] **Step 3: Write the implementation**

In `src/text_as_data/extraction.py`, insert this after line 8 (`from .codebook import Codebook`) and before line 10 (`def extract(`):

```python
_QUOTE_DASH_FOLD = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'",
        "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
        "–": "-", "—": "-",
    }
)


def _normalize_for_span_match(text: str) -> str:
    """Lowercase, collapse whitespace, and fold curly-quote/dash variants to
    a single canonical form, for the "normalized" tier of
    verify_evidence_span. Must accept a model's evidence quote back even
    when it re-typed smart quotes/em-dashes or spaced things differently
    than the source document, without accepting a genuinely different
    quote -- mirrors QualiHolo's normalizeMap() (see issue #2)."""
    return " ".join(text.translate(_QUOTE_DASH_FOLD).lower().split())


def verify_evidence_span(span: str, document_text: str) -> tuple[bool, str]:
    """Check whether `span` is a verbatim quote from `document_text`.

    Two tiers, in order, porting QualiHolo's verifySpan() design (credited
    in issue #2, ported here because the LLM's evidence_span field --
    `codebook.py` calls it a "Verbatim quote from the document that grounds
    the decision" -- was, until now, never actually checked against the
    source, so a hallucinated or paraphrased quote passed through as if it
    were verbatim):

    1. Exact substring match against `document_text`.
    2. If that fails, both strings are normalized (quotes/dashes folded,
       whitespace collapsed, lowercased) and the substring match is
       retried -- this accepts a model's cosmetic re-typing of the quote
       without accepting a genuinely different one.

    Never falls back to fuzzy/similarity matching: a near-miss quote is
    not verifiable and must not be recorded as if it were.

    Returns (verified, tier), where tier is one of "exact", "normalized",
    "empty", "too_short", or "not_found".
    """
    span = span.strip()
    if not span:
        return False, "empty"
    if span in document_text:
        return True, "exact"
    normalized_span = _normalize_for_span_match(span)
    if len(normalized_span) < 8:
        return False, "too_short"
    if normalized_span in _normalize_for_span_match(document_text):
        return True, "normalized"
    return False, "not_found"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_evidence_verification.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/extraction.py tests/test_evidence_verification.py
git commit -m "feat: add verify_evidence_span, ported from QualiHolo (see #2)"
```

---

### Task 2: Persist the verification result — `ExtractionRecord` columns

**Files:**
- Modify: `src/text_as_data/db.py:102-118` (`ExtractionRecord`)
- Test: `tests/test_db_migration.py` (append a new test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db_migration.py`:

```python
def test_get_engine_adds_evidence_verification_columns_to_an_existing_extractions_table(tmp_path):
    url = _temp_sqlite_url(tmp_path)
    raw_path = url.removeprefix("sqlite:///")

    # Simulate a pre-existing DB file created before evidence-span
    # verification existed -- an "extractions" table with none of
    # evidence_verified/evidence_match_tier (or tokens_used/prompt_sent/
    # raw_response, also added later, to keep the simulated old shape
    # realistic rather than just the two columns under test).
    connection = sqlite3.connect(raw_path)
    connection.execute(
        "CREATE TABLE extractions ("
        "id INTEGER PRIMARY KEY, run_id INTEGER, document_id INTEGER, "
        "categoria TEXT, justificativa TEXT, trecho_evidencia TEXT)"
    )
    connection.execute(
        "INSERT INTO extractions (run_id, document_id, categoria, justificativa, trecho_evidencia) "
        "VALUES (1, 1, 'yes', 'because', 'a literal quote')"
    )
    connection.commit()
    connection.close()

    engine = get_engine(url)

    with Session(engine) as session:
        loaded = session.exec(
            select(ExtractionRecord).where(ExtractionRecord.trecho_evidencia == "a literal quote")
        ).first()
        assert loaded is not None
        # New columns exist and fall back to their model-declared defaults
        # for a pre-existing row, rather than erroring or being NULL.
        assert loaded.evidence_verified is False
        assert loaded.evidence_match_tier == ""
```

This needs `ExtractionRecord` importable in the test file — add it to the existing import line.

- [ ] **Step 2: Update the import and run the test to verify it fails**

Change the import line near the top of `tests/test_db_migration.py`:

```python
from text_as_data.db import CodebookRecord, ExtractionRecord, RunRecord, get_engine
```

Run: `PYTHONPATH=src pytest tests/test_db_migration.py::test_get_engine_adds_evidence_verification_columns_to_an_existing_extractions_table -v`
Expected: FAIL with `AttributeError: 'ExtractionRecord' object has no attribute 'evidence_verified'`

- [ ] **Step 3: Add the columns to the model**

In `src/text_as_data/db.py`, replace lines 102-118 (the whole `ExtractionRecord` class) with:

```python
class ExtractionRecord(SQLModel, table=True):
    __tablename__ = "extractions"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="runs.id")
    document_id: int = Field(foreign_key="documents.id")
    categoria: str
    justificativa: str
    trecho_evidencia: str
    # Whether trecho_evidencia was found verbatim (or near-verbatim, modulo
    # quote/dash/whitespace normalization) in the source document -- see
    # extraction.py's verify_evidence_span(). Ported from QualiHolo (issue
    # #2): until this existed, a hallucinated or paraphrased quote passed
    # through unnoticed. Flagged for the researcher to see, not used to
    # invalidate categoria -- this repo's stance is that automated software
    # surfaces the signal, the researcher's judgment decides what to do
    # with it (see AGENTS.md's Product Vision).
    evidence_verified: bool = False
    # "exact" | "normalized" | "empty" | "too_short" | "not_found" | "" for
    # a pre-existing row migrated before this column existed.
    evidence_match_tier: str = ""
    tokens_used: int | None = None
    # Audit trail: the exact prompt sent and the raw (pre-parsing) response
    # received, so any result can be verified later without having to trust
    # a reconstruction from current source -- see ProviderResult in
    # providers.py. Empty string, not None, when a build_messages failure
    # happened before any prompt could be built.
    prompt_sent: str = ""
    raw_response: str = ""
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_db_migration.py -v`
Expected: PASS (3 passed — the 2 existing tests plus the new one)

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/db.py tests/test_db_migration.py
git commit -m "feat: add evidence_verified/evidence_match_tier columns to ExtractionRecord"
```

---

### Task 3: Wire verification into `run_extraction()`

**Files:**
- Modify: `src/text_as_data/extraction.py:125-170` (inside `run_extraction()`)
- Test: `tests/test_extraction_run.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_extraction_run.py`:

```python
class QuotingFakeProvider(Provider):
    """Returns a trecho_evidencia that is an exact substring of whatever
    document text it's asked to classify -- for testing the "verified"
    path of run_extraction's evidence-span check without hand-writing the
    document text to match a hardcoded quote."""

    def extract(self, messages, schema):
        document_text = messages[-1]["content"]
        quote = document_text[:12]  # long enough to clear the too_short cutoff
        parsed = schema(categoria="yes", justificativa="because", trecho_evidencia=quote)
        return ProviderResult(parsed=parsed, prompt="fake prompt", raw_response="fake raw response")


def test_run_extraction_records_verified_true_and_exact_tier_for_a_real_quote():
    engine = get_engine("sqlite://")
    run_id, _ = _seed(engine, n_documents=1)
    run_extraction(engine, run_id, QuotingFakeProvider())

    with Session(engine) as session:
        extraction = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).one()
        assert extraction.evidence_verified is True
        assert extraction.evidence_match_tier == "exact"


class FabricatingFakeProvider(Provider):
    """Always returns a trecho_evidencia that is long enough to clear the
    too_short cutoff but never actually appears in the document text -- the
    fabricated/paraphrased-quote case verify_evidence_span exists to
    catch, distinct from CountingFakeProvider's "quote" (which is too
    short to reach the not_found tier at all -- see the too_short test in
    tests/test_evidence_verification.py)."""

    def extract(self, messages, schema):
        parsed = schema(
            categoria="yes",
            justificativa="because",
            trecho_evidencia="this exact sentence never appears in the source document",
        )
        return ProviderResult(parsed=parsed, prompt="fake prompt", raw_response="fake raw response")


def test_run_extraction_records_verified_false_for_a_fabricated_quote():
    engine = get_engine("sqlite://")
    run_id, _ = _seed(engine, n_documents=1)
    run_extraction(engine, run_id, FabricatingFakeProvider())

    with Session(engine) as session:
        extraction = session.exec(select(ExtractionRecord).where(ExtractionRecord.run_id == run_id)).one()
        assert extraction.evidence_verified is False
        assert extraction.evidence_match_tier == "not_found"


def test_run_extraction_copies_verification_result_on_cache_hit_instead_of_recomputing():
    engine = get_engine("sqlite://")
    run_id, corpus_id = _seed(engine, n_documents=1)
    run_extraction(engine, run_id, QuotingFakeProvider())

    with Session(engine) as session:
        codebook_id = session.exec(select(RunRecord).where(RunRecord.id == run_id)).one().codebook_id
        second_run = RunRecord(codebook_id=codebook_id, corpus_id=corpus_id, model="fake-model")
        session.add(second_run)
        session.commit()
        session.refresh(second_run)
        second_run_id = second_run.id

    # A provider that would fail verification if it were actually called --
    # proves the cache hit path copies the prior result rather than
    # recomputing (or, worse, calling the provider again).
    run_extraction(engine, second_run_id, CountingFakeProvider())

    with Session(engine) as session:
        extraction = session.exec(
            select(ExtractionRecord).where(ExtractionRecord.run_id == second_run_id)
        ).one()
        assert extraction.evidence_verified is True
        assert extraction.evidence_match_tier == "exact"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_extraction_run.py -k "verif" -v`
Expected: FAIL — `AttributeError: 'ExtractionRecord' object has no attribute 'evidence_verified'` on the assertions (the column exists from Task 2, but `run_extraction` never sets it, so it's stuck at the model default `False`/`""` for every case, making the "verified true" tests fail).

- [ ] **Step 3: Implement**

In `src/text_as_data/extraction.py`, inside `run_extraction()`'s per-document loop (lines 125-170), make two changes:

First, in the cache-hit branch (currently lines 125-131):

```python
                if cached is not None:
                    categoria, justificativa, trecho = (
                        cached.categoria,
                        cached.justificativa,
                        cached.trecho_evidencia,
                    )
                    evidence_verified, evidence_match_tier = (
                        cached.evidence_verified,
                        cached.evidence_match_tier,
                    )
                    prompt_sent, raw_response = cached.prompt_sent, cached.raw_response
```

Second, right after the `try`/`except` block that sets `categoria, justificativa, trecho` (currently ending at line 158, still inside the `else` branch, before the `session.add(ExtractionRecord(...))` call at line 160), add the verification call so it runs uniformly for both the success and error outcomes (an error's `trecho` is `""`, which `verify_evidence_span` correctly reports as `("empty")`, so no separate error-path handling is needed):

```python
                    evidence_verified, evidence_match_tier = verify_evidence_span(trecho, document.text)
```

Finally, add the two fields to the `ExtractionRecord(...)` constructor call (currently lines 160-170):

```python
                session.add(
                    ExtractionRecord(
                        run_id=run.id,
                        document_id=document.id,
                        categoria=categoria,
                        justificativa=justificativa,
                        trecho_evidencia=trecho,
                        evidence_verified=evidence_verified,
                        evidence_match_tier=evidence_match_tier,
                        prompt_sent=prompt_sent,
                        raw_response=raw_response,
                    )
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_extraction_run.py -v`
Expected: PASS (all tests in the file, including the 3 new ones)

- [ ] **Step 5: Commit**

```bash
git add src/text_as_data/extraction.py tests/test_extraction_run.py
git commit -m "feat: verify evidence_span against source text in run_extraction (closes #2)"
```

---

### Task 4: Full regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `PYTHONPATH=src pytest -q`
Expected: all tests pass (245 existing + 8 from Task 1 + 1 from Task 2 + 3 from Task 3 = 257), no regressions in unrelated modules (`app.py`'s results/export endpoints use `ExtractionRecord.model_dump()` generically, so the two new columns flow through automatically with no endpoint changes needed — confirm this by eye in `tests/test_app_qualilab.py`'s and `tests/test_app.py`'s existing results/export tests still passing, not by re-deriving it).

- [ ] **Step 2: Close the loop on the GitHub issue**

Comment on [issue #2](https://github.com/mancano-tales/decifra-text-as-data/issues/2) noting it's implemented, which commits closed it, and that the "flag, don't invalidate" question was resolved in favor of flagging (matching this repo's existing philosophy). Then close it.

```bash
gh issue close 2 --repo mancano-tales/decifra-text-as-data --comment "Implemented in commits <hash1>, <hash2>, <hash3> (see docs/superpowers/plans/2026-09-03-evidence-span-verification.md). Resolved the open question in favor of flagging (evidence_verified/evidence_match_tier recorded, categoria left alone) rather than invalidating -- matches this repo's existing stance that the researcher's judgment decides what to do with a signal, not the software. QualiHolo's broader validation-gate idea is intentionally not part of this -- left for a future issue if there's appetite."
```

Replace `<hash1>, <hash2>, <hash3>` with the actual commit hashes from Tasks 1-3 (`git log --oneline -3`).

---

## Self-Review Notes

- **Spec coverage**: every item in issue #2's "Proposed approach" is covered — the helper function (Task 1), the new columns via the existing additive-migration mechanism with no new migration code (Task 2), wiring into `run_extraction` including the cache-hit copy behavior (Task 3), and the resolved open question (flag, not invalidate — stated in the Goal and implemented by never touching `categoria`). The "out of scope" item (QualiHolo's `gateStatus()` validation gate) is deliberately not a task here, matching the issue.
- **Placeholder scan**: no TBDs — the module location question from the issue ("module TBD") is resolved in this plan to `extraction.py`, with the reasoning in the File Structure section.
- **Type consistency**: `verify_evidence_span(span: str, document_text: str) -> tuple[bool, str]` is the same signature and tier-string vocabulary (`"exact"`, `"normalized"`, `"empty"`, `"too_short"`, `"not_found"`) used consistently across Task 1's tests, Task 2's model field docstring, and Task 3's integration tests.
