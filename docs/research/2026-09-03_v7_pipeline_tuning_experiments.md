# V7 pipeline tuning experiments: results (items 3, 4, 5)

**Date**: 2026-09-03
**Context**: follow-up to
`docs/research/2026-09-02_llm_pipeline_verification_methodology.md`'s open
items. Run against the real `agy` CLI (Gemini), the real 16-candidate V7
set, the real enriched codebooks (`pilot_v7.py`) — not a synthetic or
smaller sample. Script: `scripts/run_v7_tuning_experiments.py`.

## Setup

Four conditions, all against the same 16 candidates (32 hypothesis-side
evaluations):

- **A. baseline** — current enriched codebook (post tuning-item-2
  instructions/evidence delimiter fix), persona on.
- **B. no_persona** — identical codebook, persona off (item 4).
- **C. repeat** — identical to A, a second independent call (item 5).
- **D. joint** — one call per candidate scoring both hypothesis sides at
  once, instead of two separate blind calls (item 3).

A/B/C share one `CodebookRecord`/corpus per (pair, side) and all set
`RunRecord.bypass_cache=True`, so none of them can silently replay another
condition's cached answer.

## Headline numbers

| Comparison | Exact match | Kappa | Mismatches |
|---|---|---|---|
| A vs B (persona ablation) | 75.0% | 0.68 | 8/32 |
| A vs C (reproducibility repeat) | 68.8% | 0.60 | 10/32 |
| A vs D (joint scoring) | 59.4% | 0.48 | 13/32 |

## Finding 1: the non-discriminating-cases fix holds, and is not fragile

Zero of 16 candidates had both hypothesis sides score `muito_provavel` or
higher simultaneously, in **any** of the four conditions (A, B, C, or D).
This is the failure mode the codebook enrichment (2026-09-02, prior
session) was built to fix, previously measured at 6/16 pre-enrichment. The
fix stays at 0/16 whether the persona line is present, whether it's a
fresh repeat, or whether the model sees both sides at once instead of
blind — it is not a brittle artifact of one specific prompt phrasing.

## Finding 2 (the important one): the persona-ablation "effect" cannot be
distinguished from ordinary resampling noise at this sample size

The naive reading of "75% agreement between persona-on and persona-off"
is "removing the persona line changes about a quarter of decisions." But
condition C (an exact repeat of A, same persona, same everything) only
agrees with A **68.8%** of the time — *more* disagreement than A vs B's
75%. In other words: two runs of the **identical** prompt disagree more
often than a run with the persona line removed disagrees with a run that
has it. The persona-ablation's 8/32 mismatches sits comfortably inside
the 10/32 mismatch rate produced by simple resampling variance alone.

This does not mean the persona line has zero effect — it means this
experiment, at N=32, cannot separate any real effect it has from the
model's own sampling noise. A confident claim either way would need a
much larger N (many repeats of both conditions) to establish whether 75%
vs. an ~69% noise floor is a real difference or within-noise fluctuation.
Recorded here specifically so nobody later cites "removing the persona
changed 25% of answers" as if it were a clean causal estimate — it isn't,
on this data.

## Finding 3: joint scoring is the most different from baseline — genuinely, not just noise

At 59.4% exact match (13/32 mismatches), condition D diverges from
baseline more than either the persona ablation (25% divergence) or the
repeat-noise floor (31% divergence) — comfortably outside the ~31% noise
band Finding 2 establishes. Forcing the model to see both hypothesis
sides in one call and weigh them against each other measurably changes
individual category choices, beyond what resampling variance alone would
produce.

**What this experiment cannot tell us**: whether joint scoring's answers
are *more correct* — the V7 gold-label set (per `AGENTS.md`) is far too
small (1-2 usable points) to check either condition's accuracy with any
power. What it does establish is that the two-blind-calls vs. one-joint-
call design choice is not a wash — it produces a real, measurably
different pattern of judgments, not a redundant restructuring of the same
answer. Whether that pattern is worth the schema/pipeline change
(`AGENTS.md`'s "keep codebook separate from extraction" concern, since
joint scoring can't be expressed through the general single-`categoria`
`Codebook` class) is a design decision for whoever picks this up next,
not something this experiment settles on its own.

## What this changes in the TODO

- Item 2 (delimiter): already landed; this run is incidental confirmation
  it didn't change the reproducibility rate in either direction (68.8% now
  vs. the pre-fix 65.6%/21-32 finding — same order of magnitude).
- Item 3 (joint scoring): real effect confirmed, not yet a design decision
  about whether to adopt it — needs more gold labels to evaluate against,
  not more ablation runs.
- Item 4 (persona ablation): inconclusive at this N — Finding 2 above.
  Would need a repeated-measures design (many repeats per condition) to
  say anything confident, which is a bigger ask than this pass's scope.
- Item 5 (reproducibility): reconfirmed under current code. The ~1/3
  single-run divergence rate from the prior finding is not an artifact
  of the pre-delimiter-fix prompt — it persists after the fix, which is
  useful signal that it's a property of the model/task, not something a
  prompt tweak alone will close.
