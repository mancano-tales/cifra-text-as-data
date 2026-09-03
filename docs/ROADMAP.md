# ROADMAP — task briefs for the next agents

**Source**: the 2026-09-02 diagnosis in
[`docs/research/2026-09-02_state_of_the_project_diagnosis_and_distribution.md`](research/2026-09-02_state_of_the_project_diagnosis_and_distribution.md).
Read that first; it explains *why* this order. This file is the *what*.

**How to use this file.** Each brief below is written to be handed to a
fresh agent session with no other context. Pick the lowest-numbered brief
whose dependencies are done. For anything marked **spec first**, follow the
repo's existing workflow (a design spec under `docs/superpowers/specs/`,
then an implementation plan under `docs/superpowers/plans/`, then code)
before writing code. Everything else can go straight to a plan.

**Rules that apply to every brief** (from `AGENTS.md`, repeated so a fresh
session cannot miss them):

- Work in your own `git worktree` if another session may be active. Read
  `docs/MULTI_AGENT_WORKTREES.md`. Run tests with `PYTHONPATH=src pytest`
  if the editable install is stale.
- Everything in English: code, comments, docs, commit messages.
- `pytest` must stay green (238 tests at the time of writing). Add tests
  for every behavior you add. Run the frontend `npm run lint` and
  `npm run build` before claiming done.
- Do not add a feature that is not in your brief. If you find something
  worth doing, append it to `TODO.md` Pending instead.
- When done: `TODO.md` Done entry with date, `NEWS.md` entry, and a short
  learnings note (what was assumed, what was wrong, what to check next
  time), per the `LEARNINGS.md` convention in `AGENTS.md`.

Status legend: `[ ]` not started, `[~]` in progress (write the session id),
`[x]` done (write the date and commit).

---

## Phase 0 — Truth in the front door

### R0.1 `[ ]` Rewrite both READMEs to match what exists

**Depends on**: nothing. **Size**: hours. **Spec first**: no.

`README.md` still says the Run, Results, and Validation screens are not
built and cites "70+ tests"; all five screens exist and there are 238
tests. `README.pt-BR.md` describes Krippendorff's alpha, Gwet's AC1,
Ollama, Gemini, a "trajectory audit log", and a "hard limit of 2 retries";
none of that exists.

Do:
- Rewrite `README.md` "Status", "What's actually built", "Not built yet",
  and "Testing" sections from the real code (`src/text_as_data/app.py`
  endpoint list, `frontend/src/App.tsx` tabs, `pytest --co -q | tail -1`).
- Rewrite `README.pt-BR.md` as a faithful translation of the corrected
  English README, not an independent document. Remove every feature that
  does not exist. Keep the "story" tone if the author wants it, but every
  factual claim must be verifiable in the code.
- Add a one-paragraph "Who this is for" that reflects the general-purpose
  framing (researchers, organizational analysts, data journalists, NGOs),
  not only political science.
- Add the same corrections to `site/index.qmd` if it repeats the stale
  claims (check; do not rewrite the site otherwise).

Acceptance: a reader who follows README instructions gets exactly the
software the README describes. Every listed feature has an endpoint,
component, or function you can point to.

---

## Phase 1 — Generalize the contract before anyone has data files

### R1.1 `[ ]` Multi-variable codebooks with neutral field names

**Depends on**: nothing (do it before R2.x so nothing else has to migrate
twice). **Size**: the largest item on this list; multi-day.
**Spec first**: **yes**, and get the author's sign-off on the YAML shape
before writing code.

Today a codebook is one concept with one set of categories, and the output
schema is fixed to three Portuguese-named fields: `categoria`,
`justificativa`, `trecho_evidencia`. These names are hardcoded in
`src/text_as_data/codebook.py`, `db.py` (`ExtractionRecord`),
`extraction.py`, `app.py` (results, gold-label CSV, validation,
QualiLab export), `export.py`, `frontend/src/ResultsTable.tsx`,
`frontend/src/api.ts`, `ValidationPanel.tsx`, and the gold-label CSV
column `gold_categoria`. A general-purpose tool must ask several questions
per document (Halterman & Keith's codebooks do), and an English codebase
should not leak Portuguese identifiers into its data contract.

Design questions the spec must answer:
- YAML shape for N variables per codebook. Suggested: keep today's
  single-variable YAML valid as a shorthand, and add a `variables:` list
  where each variable has `name`, `description`, `categories` (same
  category shape as today). Backwards compatibility with existing YAML
  files matters; backwards compatibility of the *database* matters less
  (there are no external users yet), but write a one-shot migration for
  the author's own `codifica.sqlite` anyway.
- Output field names. Suggested: `category`, `rationale`, `evidence_span`
  (the names `AGENTS.md` itself uses in the codebook-format section). One
  row per (document, variable) in `extractions`, or one row per document
  with a JSON column per variable; the spec must argue for one. Filtering
  and the validation report must work per variable.
- Prompt strategy: one LLM call per document returning all variables
  (cheaper, allows cross-variable consistency) vs. one call per variable
  (simpler caching). The spec must pick one and justify the cache key
  change in `extraction.py` (currently `(document, codebook_hash, model)`).
- Gold-label CSV: one `gold_<variable>` column per variable.
- Validation report keyed by variable.
- `pilot_v7.py` and `scripts/run_v7_candidates_via_agy.py`: either move
  out of `src/text_as_data/` into `scripts/` or `examples/`, or delete
  with a note. The product package must not contain one study's
  hypothesis definitions.

Acceptance: a codebook with two variables runs end to end in the UI
(import, edit, run, results filtered per variable, gold upload, validation
per variable, CSV/XLSX/JSON export). All existing single-variable tests
still pass, possibly with renamed fields. No Portuguese identifier remains
in any Python or TypeScript symbol (grep `categoria|justificativa|trecho`
returns only the i18n locale files and historical docs).

---

## Phase 2 — Usable by a second person (without packaging yet)

All R2.x items are independent of each other and can be parallelized across
sessions *after* R1.1 lands, since several touch the same tables. If R1.1 is
not done yet, only R2.4, R2.5, and R2.7 are safe to start.

### R2.1 `[ ]` Settings screen and persisted credentials

**Depends on**: nothing hard, but R1.1 first avoids a second frontend pass.
**Size**: 1-2 days. **Spec first**: yes (short).

Today the API key is read only from `ANTHROPIC_API_KEY` /
`OPENAI_API_KEY` at process start (`make_api_key_provider(api_key=None)` in
`app.py`). There is no settings UI.

Do:
- A `config.py` that reads/writes a config file in the platform user
  config dir (`platformdirs`; e.g. `%APPDATA%/Cifra/config.toml`,
  `~/Library/Application Support/Cifra/`, `~/.config/cifra/`). Keys stored
  with `keyring` when available, plain file with a warning otherwise.
  Environment variables still override, for scripting.
- `GET/PUT /settings` endpoints (never return the full key; return a
  masked suffix and a `configured: true/false` flag).
- A "Settings" tab in `App.tsx`: per-vendor key fields, default model,
  default provider mode, default CLI command. Bilingual via the existing
  i18n setup.
- `RunForm.tsx` pre-fills from settings and shows a clear message when no
  credential is configured for the chosen vendor instead of letting the
  run fail in the background.

Acceptance: a user with no environment variables set can paste a key in the
UI, restart the backend, and run. The key never appears in any API
response, log line, export, or disclosure report.

### R2.2 `[ ]` Cost estimate before a run, and tokens actually recorded

**Depends on**: R1.1 (prompt shape changes). **Size**: 1 day.
**Spec first**: no.

MVP scope item 3 in `AGENTS.md` requires an estimated cost before running.
`ExtractionRecord.tokens_used` exists but is never written.

Do:
- `POST /runs/estimate` (or `GET /runs/estimate?codebook_id&corpus_id&model`):
  build the real prompt per document via `Codebook.build_messages`, count
  tokens (Anthropic `count_tokens` endpoint when a key is present,
  `tiktoken` for OpenAI, a chars/4 fallback labeled as approximate), sum,
  and multiply by a price table in a versioned `pricing.py` with a
  `last_updated` date shown in the UI. Report input tokens, an assumed
  output-token budget per document, and the cache hit count (documents
  that will not be re-billed).
- Populate `tokens_used` from the provider response in `ApiKeyProvider`
  (instructor exposes the raw completion; read usage from it). CLI mode
  records `None` honestly.
- Show the estimate in `RunForm.tsx` before the Start button with a
  confirm step when the estimate exceeds a configurable threshold.

Acceptance: estimate shown for a 100-document corpus within a few seconds;
actual `tokens_used` summed over a finished API-key run is within the
stated approximation of the estimate; the pricing table has a test that
fails if a listed model is missing a price.

### R2.3 `[ ]` Delete corpora, codebooks, and runs

**Depends on**: R1.1 preferred. **Size**: half a day. **Spec first**: no.

There are no delete endpoints. `corpus_id` is a free string on
`DocumentRecord`, not a table.

Do:
- `DELETE /runs/{id}` (cascade extractions and that run's gold labels).
- `DELETE /codebooks/{id}`: refuse with 409 and the list of dependent runs
  if any run references it (FK already blocks it; return a useful message
  instead of a 500).
- `DELETE /corpora/{corpus_id}`: same 409 rule for runs.
- Delete buttons with confirm dialogs in `CorpusPage.tsx`,
  `CodebookEditor.tsx`, `RunsPage.tsx`.
- Decide in the plan whether to introduce a `corpora` table now
  (name, created_at, source type) since R1.1 already forces a DB
  migration; recommended yes.

Acceptance: deleting a run removes its extractions and labels; deleting a
codebook in use is refused with a message naming the runs; tests cover
cascade and refusal.

### R2.4 `[ ]` Backend serves the built frontend; `cifra` entry point; DB in the user data dir

**Depends on**: nothing. **Size**: 1 day. **Spec first**: no.

Today the UI only runs under the Vite dev server, and the SQLite file is
created relative to the current working directory
(`get_engine("sqlite:///codifica.sqlite")`).

Do:
- `vite build` output copied into the Python package (e.g.
  `src/text_as_data/static/`) via a build step documented in
  `pyproject.toml`/a `scripts/build_frontend.*`; mount it with
  `StaticFiles` at `/` with SPA fallback, and move the API under `/api/`
  (update `frontend/src/api.ts` `API_BASE` default accordingly, keep the
  `VITE_API_BASE` override for dev).
- A console script `cifra` in `pyproject.toml` (`[project.scripts]`) with
  subcommands `serve` (default: pick a free port, start uvicorn, open the
  default browser) and `--no-browser`, `--port`, `--db` overrides.
- DB default path in the platform data dir via `platformdirs`, created on
  first run; `--db` and `CIFRA_DB` env override. Print the path at startup.
- Verify `pipx install .` and `uv tool install .` produce a working
  `cifra` on a clean machine (or a clean venv) with no Node installed.

Acceptance: from a clean virtualenv, `pip install .` then `cifra` opens the
browser at a working UI with no second process. `curl` against `/api/`
still works with no frontend open (the Phase 1 acceptance criterion in
`AGENTS.md`).

### R2.5 `[ ]` Cancel a run, and recover stuck runs on startup

**Depends on**: nothing. **Size**: 1 day. **Spec first**: no.

`run_extraction` runs as a FastAPI `BackgroundTask`; there is no cancel,
and a run whose process died stays `running` forever.

Do:
- `POST /runs/{id}/cancel`: set a `cancel_requested` flag on `RunRecord`;
  `run_extraction` checks it between documents and exits with status
  `cancelled`. Cached/finished rows stay.
- On engine startup (in `get_engine` or an app lifespan hook), mark every
  run in `running`/`pending` as `interrupted` with a timestamp. Add
  `POST /runs/{id}/resume` that continues from the documents with no
  extraction row (the cache already makes re-running cheap, but resume
  should not require a new run id).
- Cancel and Resume buttons in `RunsPage.tsx`; show the new statuses.

Acceptance: killing uvicorn mid-run and restarting shows the run as
interrupted; resume finishes only the remaining documents; tests simulate
both.

### R2.6 `[ ]` Local and OpenAI-compatible providers

**Depends on**: R2.1 (settings hold the base URL). **Size**: 1 day.
**Spec first**: no.

`_vendor_for_model` in `app.py` only knows `claude*`, `gpt*`, `o1*`, `o3*`.
Sensitive corpora (police reports, testimony, anything under LGPD) cannot
go to a US API.

Do:
- Replace prefix inference with an explicit `vendor` field on the run
  request and in settings: `anthropic`, `openai`, `openai_compatible`
  (base URL + optional key; covers Ollama, LM Studio, vLLM, Groq, and
  similar), `gemini` if `instructor` supports it cleanly at the time.
- Persist `vendor` on `RunRecord`; include it in the disclosure report.
- Test with a fake OpenAI-compatible server (httpx mock) and, manually,
  with Ollama on the author's machine.

Acceptance: a run against a local Ollama model completes and the
disclosure report names the local endpoint; a model name with no vendor
gives a 422 with a helpful message.

### R2.7 `[ ]` Dev environment hygiene

**Depends on**: nothing. **Size**: hours. **Spec first**: no.

- Document and script a per-worktree virtualenv (`scripts/setup_env.*`)
  so `pip install -e .` never repoints a global install; update
  `docs/MULTI_AGENT_WORKTREES.md` and remove the TODO entry.
- Find why the suite takes ~2.5 minutes (likely real sleeps in `tenacity`
  retry paths under test); patch `wait` to zero in tests. Target under
  30 seconds.
- A `pytest` conftest that adds `src/` to `sys.path` so a stale editable
  install cannot make the suite fail with `ModuleNotFoundError`.

---

## Phase 3 — Hand it to real people

### R3.1 `[ ]` Two or three external pilot users, observed

**Depends on**: R0.1, R1.1, R2.1, R2.3, R2.4. **Size**: calendar time,
not code. **Spec first**: no. This is the author's task, not an agent's,
but an agent should prepare it.

Prepare: a 10-minute onboarding guide (install with `pipx`/`uv`, paste
key, import a CSV, write a two-category codebook, run 20 documents, upload
a gold CSV, read the report). A feedback template with the questions that
matter: where did you get stuck, what did you expect the tool to do that it
did not, what would you need before using the output in real work.

Output: a `docs/research/<date>_pilot_user_feedback.md` and new
`TODO.md` Pending items derived from it. **Everything in Phases 4-5 should
be re-prioritized against this feedback.**

---

## Phase 4 — Packaging

### R4.1 `[ ]` Single-binary build with PyInstaller (or Nuitka) + pywebview window

**Depends on**: R2.4 (static frontend, entry point, data dir). **Size**:
about a week for Windows + macOS. **Spec first**: yes (short; record the
binary size and startup time you measure, and the decision pywebview vs.
Tauri).

Do:
- `cifra` compiled onefile; a `cifra-app` variant that opens a `pywebview`
  window on the system webview instead of the browser. Verify pandas,
  scikit-learn, anthropic, openai, and `instructor` all import from the
  bundle (hidden imports are the usual failure).
- CI workflow building artifacts for Windows and macOS on tags (Linux as a
  bonus). Publish as GitHub Release assets.
- Installers: Inno Setup on Windows, a `.dmg` on macOS.
- A `docs/PACKAGING.md` with the signing situation stated honestly
  (unsigned builds trigger SmartScreen and Gatekeeper; what the author
  must buy to fix it).

Acceptance: a non-developer downloads one file, opens it, and reaches the
Settings screen without a terminal. Measured size and cold-start time are
recorded in the spec.

### R4.2 `[ ]` Code signing (author's task; agent prepares)

**Depends on**: R4.1. Apple Developer ID + notarization; a Windows
code-signing certificate. Agent prepares the CI steps and secrets layout;
the author buys and provisions.

### R4.3 `[ ]` Tauri shell — only if R4.1 proves insufficient

Reasons that would justify it: auto-update, system tray, pywebview
rendering bugs on a target OS, or bundle size. Otherwise skip.

---

## Phase 5 — Robustness for real corpora

### R5.1 `[ ]` Bounded parallelism and rate-limit handling

**Depends on**: R2.5. **Size**: 1-2 days. **Spec first**: yes (short).

`run_extraction` is strictly sequential. Do: a configurable worker pool
(default 4) inside the run, per-document retry that distinguishes 429/5xx
(back off, retry) from 4xx (record error, move on), a global pause when
rate-limited, progress that reflects concurrent completion. Keep CLI mode
sequential by default (subprocess CLIs usually serialize anyway).

### R5.2 `[ ]` Large-corpus tests

A 1,000-document synthetic corpus against a fake provider: memory stays
flat, results endpoint paginates or streams, exports do not load everything
twice, the UI table virtualizes or paginates.

---

## Phase 6 — Scientific depth (what "reference tool" is earned with)

Re-prioritize this whole phase against R3.1 feedback.

### R6.1 `[ ]` Krippendorff's alpha and Gwet's AC1

Kappa collapses under class imbalance (the 2026-08-31 audit document
already flags the Feinstein-Cicchetti paradox). Add both, with a one-line
plain-language explanation of when each is preferable in
`ValidationPanel.tsx`. Test against published worked examples, not against
your own implementation.

### R6.2 `[ ]` Repeated runs and majority vote

Measured self-agreement on the V7 pilot was 21/32. Add `n_repeats` on a
run, store every repeat, expose a per-document agreement rate and a
majority category, and let validation run against the majority.

### R6.3 `[ ]` Label-free codebook diagnostics (Halterman & Keith)

`POST /codebooks/{id}/diagnose`: category-order invariance (shuffle the
category order, re-run a sample, measure flips) and definition recovery
(ask the model to restate each category's definition and diff it against
the codebook). Report before the researcher spends money on the full run.

### R6.4 `[ ]` Gold-sample helper

Given a run, draw a stratified sample (by predicted category, with a
configurable size and a note on what agreement precision that size buys)
and export it as the gold-label CSV template with empty gold columns, so
the researcher hand-codes a defensible sample rather than an arbitrary one.

### R6.5 `[ ]` Benchmark datasets

Optional: wire one public codebook-LLM benchmark (e.g. from Halterman &
Keith's released materials, license permitting) as an example project, so
a new user can see a real validation report before importing their own
data.

---

## Phase 7 — Release

### R7.1 `[ ]` License decision (author's task)

`LICENSE` is "all rights reserved, provisional". Decide (the author has
signaled GPL-3.0 or AGPL-3.0) before any public announcement; a reference
tool spreads by citation and forks. Agent: prepare a `CITATION.cff`.

### R7.2 `[ ]` Public release checklist

Versioned release on GitHub with binaries (R4.1), corrected READMEs
(R0.1), a changelog cut from `NEWS.md`, the mini-site updated, and a
short screencast.
