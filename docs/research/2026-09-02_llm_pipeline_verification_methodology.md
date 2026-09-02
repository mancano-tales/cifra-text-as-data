# Verifying and reproducing an LLM-coding pipeline: methodology and findings

**Date**: 2026-09-02
**Context**: V7 Bayesian pilot, 16 evidence/hypothesis-pair evaluations run through
Cifra's real `extraction.py` engine via Google Antigravity's `agy` CLI (Gemini).
**Why this document exists**: the author pushed back, repeatedly, on taking any
claim about "what the LLM was actually asked" or "what the LLM actually did" at
face value — first asking for the literal prompt text, then asking how to know
it wasn't invented after the fact, then asking whether re-running with the
identical prompt would even reproduce. Those questions surfaced a real gap
(no audit trail existed) and produced a concrete fix. This document records
both the verification *procedure* — reusable for any future claim about this
pipeline's behavior — and what applying it found.

## Why this is a methodology question, not a bookkeeping one

Cifra's own stated thesis (`AGENTS.md` § "Why the validation step is not
optional") is that off-the-shelf LLMs frequently substitute their own generic
notion of a concept for a codebook's specific operationalization, and that
this is only catchable by treating LLM coding as a measurement instrument
subject to the same scrutiny any instrument in an empirical paper would get:
what exactly was the stimulus, is the response reproducible, and can a third
party check the claim without trusting the person who ran it. Everything
below is that scrutiny applied to Cifra's own pipeline, not a one-off
debugging exercise.

## The verification procedure

Four checks, each escalating in what it can prove:

1. **Reconstruct from the persisted artifact, not from memory or fresh
   source.** When asked to show "the prompt", pull the codebook YAML that was
   *actually stored* in the run's own SQLite database (`CodebookRecord.yaml_raw`
   in `data/v7_candidates_enriched.sqlite`), not a value recomputed from
   current `pilot_v7.py`. The DB record is what the run actually used, by
   construction — it can't have drifted.
2. **Prove determinism, don't just assert it.** Compare the DB-stored YAML
   against `build_enriched_hypothesis_codebook_spec()` called fresh, right
   now, from committed source. Byte-for-byte equality confirms two things at
   once: the function is pure (no hidden state, no randomness) and nothing
   was hand-edited between the run and the inspection. This is what makes
   "here is the prompt" a checkable claim instead of a report.
3. **Trace provenance through git, don't guess at authorship or intent.**
   When asked where a piece of prompt text came from (the fixed "careful
   annotator" persona in `Codebook.build_messages`), `git log -p --follow`
   and `git log -1 --format=... <commit>` answer it exactly: commit `b31b328`,
   2026-08-30, the project's very first commit, part of the generic scaffold
   — before any V7-specific work existed. Answering "I think it's from
   early on" is a guess; citing the commit hash and date is not.
4. **Test reproducibility empirically, don't assume determinism.** Re-run
   the identical 16 evaluations through the identical codebooks and the
   identical `agy` invocation, nothing else changed, and diff the two
   result sets. This is the only one of the four checks that can't be
   answered from static inspection — it requires actually spending the
   ~15 minutes of real `agy` calls twice.

Applying check 4 is what turned "the enrichment fixed it" from a plausible
story into a number: see the repeatability findings below.

## What each check found

### Determinism of codebook generation (checks 1–2)

Confirmed byte-for-byte identical. `build_enriched_hypothesis_codebook_spec`
and `spec_to_yaml_string` are pure functions over `HYPOTHESIS_DEFINITIONS`
and `PROBABILITY_BOUNDARY_NOTES` (`pilot_v7.py`) — no I/O, no randomness. This
is a genuine property to preserve: it is what lets anyone regenerate and
verify a prompt from source alone, without needing a stored log, for the
*instructions* portion specifically.

### The gap the checks exposed: no audit trail for the actual LLM call (check 1, extended)

The instructions portion is reproducible from source. The *final* prompt sent
to the CLI — instructions + the specific document's evidence text + the
JSON-schema request appended by `CliProvider._build_prompt` — was not
persisted anywhere. `CliProvider.extract()` built it, piped it to `agy` via
`subprocess.run`, and discarded it once the response was parsed. The same was
true of the raw response: only the already-parsed `categoria` /
`justificativa` / `trecho_evidencia` ever reached `ExtractionRecord`, never
the CLI's raw stdout (which can legitimately differ from the extracted JSON —
`_extract_json` exists specifically because CLI output often wraps the answer
in prose).

Reconstructing the instructions and confirming byte-identity is a legitimate
substitute for a log *only* for the codebook-authored portion, which is
static per (pair, side). It is not a substitute for the full, per-document
prompt or the model's raw answer — those genuinely didn't exist anywhere
after the process exited.

**Fix implemented (this date, same session)**: `providers.py` now defines
`ProviderResult(parsed, prompt, raw_response)`; both `ApiKeyProvider.extract()`
and `CliProvider.extract()` return one instead of a bare parsed model.
`ExtractionRecord` gained `prompt_sent: str` and `raw_response: str` columns.
`run_extraction` persists them on every row — on a cache hit, copied from the
cached record (the same extraction is genuinely being reused); on a fresh
call, the provider's own precise values; on a provider failure *after*
`build_messages` succeeded, a best-effort `json.dumps(messages)` fallback
(the provider never returned a `ProviderResult` to pull the exact string
from, but the messages that were about to be sent are still known); empty
only when `build_messages` itself raised before any prompt could exist.
Because `GET /runs/{id}/results` and the CSV/XLSX/JSON export endpoints
already build their rows via `ExtractionRecord.model_dump()`
(`app.py`'s `_extraction_with_snippet`), both fields now flow through every
export format automatically — no separate change needed there. 8 new tests
across `test_providers.py` and `test_extraction_run.py` cover the success,
cache-copy, provider-failure-fallback, and build-messages-failure paths; full
suite (95 tests) green.

### Provenance of the fixed persona line (check 3)

`"You are a careful annotator applying a fixed coding scheme..."` — commit
`b31b328`, 2026-08-30, the initial scaffold, written for the generic toy
example before any codebook was V7-specific. It is not something authored
for, or tuned to, this pilot.

**Assessment, stated plainly as an open question rather than a settled
one**: this is a cheap, generically-reasonable nudge ("resist your prior,
follow the given definition") directly aimed at the exact failure mode
Halterman & Keith describe. There is no ablation run (with vs. without) to
show it has any measurable effect, positive or negative, in either
direction. The enrichment's specific instructions (scope check,
discriminating power, consistency) are far more actionable and are what the
before/after comparison actually demonstrates works — the persona line's
own contribution is, honestly, unmeasured.

### Language consistency of the prompt (raised in discussion, not yet fixed)

The enriched prompt mixes English (hypothesis mechanism/premises/critical
instructions, added this session) with Portuguese (the 7-point verbal
probability scale, present since Slice 1; the evidence text itself, always
Portuguese). Two separate origins, one compounding error:

- The English hypothesis names/mechanisms/premises are not invented — they
  are quoted from `tb1_hypotheses`'s own `hypothesis_name` /
  `implied_mechanism` / `mutually_exclusive_premises` columns in the source
  V7 workbook, i.e. the author's own thesis framework, already in English
  before this pilot touched it.
- Applying `AGENTS.md`'s "everything in this repository is in English" rule
  to this content was a misjudgment made this session: that rule is about
  repository artifacts (code, comments, docs, commit messages), not about
  the actual text of a research instrument whose evidence corpus and
  human-authored scale are Portuguese. Adding ~3,500 characters of English
  mechanism/premises/instruction text on top of an already-Portuguese
  scale and evidence corpus mid-enrichment measurably deepened a
  pre-existing inconsistency rather than resolving it.

**Not yet fixed.** Recommendation if/when addressed: pick one language for
the entire prompt. Portuguese is the better default here — it is where the
volume of fixed, hard-to-relocate text already lives (the evidence corpus,
one document at a time) and where the human coder's own scale was
originally authored, versus translating the comparatively short
mechanism/premises text once.

### Structural limitation: hypothesis sides are scored in separate, blind calls

Raised in discussion: "a" and "b" never appear together in one call. Each
side of a pair (`H3_a`, `H3_b`) is a separate `CodebookRecord`, run as a
separate `RunRecord`, invoking `agy` in a separate subprocess. The model
scoring side A has no visibility into, and produces no direct comparison
against, its own answer for side B — each call independently decides "how
strongly does this evidence support *this* hypothesis" without the forced
joint calibration a single side-by-side judgment would carry. This is a
pipeline design property (inherited from Fairfield & Charman's own
per-hypothesis coding convention, not something introduced by this session),
not a prompt-wording issue — fixing it, if it turns out to matter, means
changing the schema (`categoria_a` + `categoria_b` + two justificativas in
one response) and the run/extraction data model, not just editing
`description` text. **Not tested, not implemented** — flagged as an open
design question, not a decided direction.

### Reproducibility under an unchanged prompt (check 4)

Re-ran the identical 16 evaluations (32 categoria decisions) through the
identical enriched codebooks and the identical `agy` invocation a second
time, nothing else changed.

- **21/32 (66%) exact match** between the two runs.
- Of the 11 that differed: **9 were one step apart** on the 7-point verbal
  scale, **1 was two steps apart**, **1 was three steps apart** (a real
  reversal of conclusion, not adjacent-category noise).
- The flagged scope-condition case (2004-02-16, H3a) was stable in
  direction across both runs: `quase_impossivel` vs. `muito_improvavel` —
  both firmly "against H3a", one step apart. The finding that mattered
  (codebook enrichment fixes the scope-condition failure) did not depend on
  which of the two runs happened to be picked.
- The one 3-step reversal (2015-06-27, H2b — Fies rule consultation with
  UNE/ABMES) was inspected directly rather than dismissed as noise: both
  runs' full `justificativa` text were read side by side, and both are
  independently well-reasoned readings of the same evidence — one weighing
  that non-partisan actors merely "accepted" the government's terms
  (favoring strict partisan-primacy), the other weighing that the rules
  were built "after consultation" with a negotiated quid-pro-quo (favoring
  co-production). The evidence itself supports both readings; the model's
  sampling landed on a different one each time. `agy --help` exposes no
  temperature/determinism flag to control for this at the CLI level.

**Implication for the eventual Validation screen**: single-run LLM coding
carries real sampling variance even against a well-specified codebook —
roughly a third of categoria decisions changed on an unchanged-prompt
re-run in this sample. Treating one run's output as the definitive answer,
rather than running each evidence/hypothesis pair multiple times (or at
minimum surfacing the variance), understates how much of a "disagreement
with gold" finding is prompt-quality signal versus simple resampling noise.

## What changed as a direct result of this discussion

- `providers.py`: `ProviderResult` dataclass; both providers return it.
- `db.py`: `ExtractionRecord.prompt_sent` / `.raw_response`.
- `extraction.py`: persists both, with the cache-copy / best-effort-fallback
  / empty-on-setup-failure behavior described above.
- 8 new tests (`test_providers.py`, `test_extraction_run.py`); 95/95 passing.
- `scripts/run_v7_candidates_via_agy.py`'s output CSV carries `prompt_sent` /
  `raw_response` per row, consistent with the full-text/full-hypothesis-
  definition requirement already established for this pilot's exports.
- This document.

## What is still open, deliberately not acted on yet

- Language consistency (English mechanism/premises vs. Portuguese scale and
  evidence) — diagnosed, not fixed.
- Explicit structural delimiter between "instructions end" and "evidence
  begins" in the concatenated prompt — proposed, not implemented.
- Whether a single joint call scoring both hypothesis sides at once would
  produce more differentiated, better-calibrated results than two blind
  calls — a real design question requiring a schema/pipeline change and a
  controlled test, not a prompt edit.
- An ablation of the fixed persona line's actual marginal effect.
- Running each evidence/hypothesis-pair evaluation multiple times (given
  the measured ~34% single-run divergence rate) before treating any one
  run's categoria as final, once the Validation screen exists to consume
  that kind of repeated-run data.
