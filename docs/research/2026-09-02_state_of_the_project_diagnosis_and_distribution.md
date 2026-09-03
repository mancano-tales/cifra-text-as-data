# State of the project: diagnosis, distribution options, and trajectory risks

**Date**: 2026-09-02
**Context**: written the day the fifth MVP screen (Validation) landed. The
author asked for two things at once: an honest critical evaluation of what
was built against the product vision, and an orchestrator's view of what to
build next, judged by "what makes Cifra a reference tool in this field" rather
than engineering instinct.
**Method**: read every governance file (`AGENTS.md`, `README.md`,
`README.pt-BR.md`, `TODO.md`, `NEWS.md`), all 116 commits, every module in
`src/text_as_data/`, every component in `frontend/src/`, the four slice
specs/plans, and the research reports. Ran the test suite (238 passed in
2m36s, but only with `PYTHONPATH=src`; see "Dev environment" below).
**Companion document**: [`docs/ROADMAP.md`](../ROADMAP.md) turns this
diagnosis into self-contained task briefs for the next agents.

## Reframed product vision (author, 2026-09-02)

The author restated the vision in this session and it supersedes the
"academic tool" framing still present in the READMEs and the mini-site:

- Cifra is **general-purpose software** for anyone who must turn text into
  defensible, auditable, reproducible categorical data: social scientists,
  analysts inside organizations, data journalists, NGOs processing reports.
  Not a niche tool for one discipline.
- The differentiator is the **whole pipeline** (structured codebook ->
  traceable extraction -> agreement metrics -> disagreement analysis), not
  "LLM classification", which any script does.
- **Distribution to non-developers** is the most important open question.
  QualiLab's "download one file and open it" model is a real adoption
  advantage, not a cosmetic one.

One premise correction, already recorded in `AGENTS.md` on 2026-09-01 and
repeated here because the framing keeps resurfacing: QualiLab is **not**
"100% manual". It calls LLMs (five auto-coding assistants, an AI chat, a
blind evaluation). The real differences are architectural: a ~600k-character
ceiling per send, synchronous execution inside the open tab, and an
agreement count that explicitly disclaims statistical rigor.

## 1. What is right, and is the core of the product

The differentiating pipeline exists end to end and is honest about itself:

- `codebook.py` derives the Pydantic schema and the system prompt from the
  YAML at runtime; `validate_spec`/`spec_to_yaml_string` are shared by the
  file format and the editor, so they cannot drift.
- `providers.py` delivers both promised credential modes (API key via
  `instructor`, subscription CLI via subprocess) behind one contract.
- `extraction.py` caches by the codebook's **content hash**, not its id, so
  an edited codebook never silently reuses extractions made under the old
  definition. Retries per document; records an error row instead of killing
  the run; marks the run `error` on failures outside the loop.
- Every extraction persists `prompt_sent` and `raw_response`. This is what
  makes a result checkable by a third party.
- `validation.py` computes accuracy, Cohen's kappa, per-category
  precision/recall/F1, and the disagreement list. `disclosure.py` maps a
  run onto the GUIDE-LLM checklist. `reproducibility_report()` measures
  self-agreement across two runs.
- `db.py` runs an additive column migration on every startup, closing a
  recurring class of "shared SQLite has the old shape" bugs.
- Discipline: 238 tests verified passing; every slice has a spec and a plan;
  multiple red-team rounds with findings verified empirically before acting
  (including two reported bugs shown to be false).

**The most important scientific result already happened.** The V7 pilot
showed that non-discriminating outputs (both hypothesis sides scored
`muito_provavel`) were a codebook-specification gap, not a model problem:
enriching the codebook took non-discriminating cases from 6/16 to 0/16 with
the same model and CLI. That is the product's thesis demonstrated on real
data, and it is worth more than any feature.

## 2. Where the implementation drifted from a general-purpose tool

In descending order of future cost:

1. **One variable per codebook, with Portuguese field names hardcoded in
   the engine.** The schema is fixed to `categoria` / `justificativa` /
   `trecho_evidencia` (`codebook.py`, `db.py`, `extraction.py`,
   `ResultsTable.tsx` with 7 references, `api.ts` with 6). A real codebook
   in Halterman & Keith's format asks several questions per document.
   Every table, export, gold-label CSV format, validation report, and the
   QualiLab mapping encodes the single-variable shape. Each week of delay
   multiplies the migration cost.
2. **Credentials only via environment variable.** `make_api_key_provider`
   is called with `api_key=None` and falls through to `ANTHROPIC_API_KEY`
   / `OPENAI_API_KEY`. No settings screen, no persisted config. The
   "paste your credential once" UX promised in `AGENTS.md` does not exist.
   For a non-developer this blocker is equal to installation.
3. **No cost estimate before a run** (MVP scope item 3). `tokens_used` is
   never populated; a grep finds it only in the table definition.
4. **Job execution is in-process, sequential, uncancellable, and
   unrecoverable.** FastAPI `BackgroundTasks`, one document at a time. If
   the server dies mid-run, the run stays `running` forever: there is no
   startup routine that reconciles stuck runs. "Survives closing the tab"
   holds; "survives closing the app" does not, and in a desktop shell the
   sidecar dies when the app closes.
5. **No delete endpoints** for corpora, codebooks, or runs. `corpus_id` is
   a free string, not a table row. Users accumulate garbage they cannot
   remove.
6. **The backend does not serve the frontend.** No `StaticFiles` mount; the
   UI needs the Vite dev server. The SQLite file path is relative to the
   working directory. Both are trivial, both block packaging.
7. **Only Anthropic and OpenAI, inferred from the model-name prefix**
   (`_MODEL_PREFIX_TO_VENDOR`). No Gemini, no Ollama, no OpenAI-compatible
   local endpoint. Police reports, NGO testimony, and anything under LGPD
   will not be sent to a US API. `instructor` already supports the
   OpenAI-compatible route, so this is cheap and unlocks a whole class of
   users.
8. **A specific study lives inside the product package.** `pilot_v7.py`
   (hypothesis definitions for one thesis, codebooks in mixed
   Portuguese/English) is in `src/text_as_data/`, and `data/` carries its
   results CSV.

## 3. The READMEs describe software that does not exist

- `README.md` says the Run, Results, and Validation screens are not built
  and cites "70+ tests". All three screens exist; there are 238 tests.
- `README.pt-BR.md` describes Krippendorff's alpha, Gwet's AC1, Ollama,
  Gemini, a "trajectory audit log", and a "hard limit of 2 retries". None of
  that exists. It is an aspirational architecture diagram presented as
  current.

For a tool whose argument is auditability and honesty, the front door cannot
describe imaginary software. Fixing it costs hours; not fixing it costs
credibility with exactly the audience that would cite it.

## 4. Dev environment and process signals

- **Bare `pytest` fails on this machine** with `ModuleNotFoundError: No
  module named 'text_as_data'`: `pip show text-as-data` reports the editable
  location as `MancanoSync\text-as-data\.claude\worktrees\v7-pipeline-tuning`,
  a worktree that no longer exists. This is the global-editable-install
  problem `TODO.md` already describes, now in its worst form. Tests pass
  with `PYTHONPATH=src`.
- **The suite takes 2.5 minutes for 238 tests.** Likely real sleeps from
  `tenacity` retry tests. Not urgent, but it will slow every future agent.
- **`TODO.md`'s Pending section is empty.** A product with no credential
  screen, no cost estimate, and no delete does not have an empty backlog.
  The backlog has been fed by reading papers and frameworks, not by
  watching someone use the tool.
- **Process weight vs. product weight.** In three days: 116 commits, eight
  research reports, a multi-agent git incident with a 3-model red-team
  review, a PreToolUse guard with 45 tests. Meanwhile there is no settings
  screen. Not a criticism of any single item; a signal about where
  attention has gone.
- **Parallel sessions produce inconsistency.** The two divergent READMEs
  and the broken editable install are symptoms of several agents landing
  work with no single integration owner per day.

## 5. Distribution: what each path really costs

QualiLab's model does not transfer because the use case differs: a run of
a thousand documents at a few seconds each takes over an hour, and the user
wants to close the laptop. That needs a process, so the backend decision
stands. But there is an intermediate path the current plan skips.

| Path | Real cost | Verdict |
|---|---|---|
| Static HTML like QualiLab | Rewrite the engine in TypeScript. Loses CLI mode and runs that outlive the tab. (A key in `localStorage` is acceptable for a *local* file; that is not the blocker.) | No: two products to maintain |
| Electron with a Node backend | Same rewrite, plus ~200 MB of Chromium | No |
| Browser extension | Hostile permission model, no long-lived process | No |
| `pipx install cifra` / `uv tool install cifra`, one command opens the browser | Backend serves the built frontend; a `cifra` entry point; DB in the platform data dir. About two days. `uv` installs Python itself. | Yes, first |
| PyInstaller onefile + pywebview + installers | A native window on the system webview, pip-only dependencies, no Rust. 150-300 MB binary because of pandas/scikit-learn. About a week for Windows and macOS. | Yes, second |
| Tauri + Python sidecar (current plan) | Everything above plus the Rust toolchain and the sidecar bridge. Gains auto-update and a smaller shell. | Only if pywebview proves insufficient |
| Hosted service | Lowest adoption barrier for journalists/NGOs, but multi-user, auth, server cost. | v3, but revisit the "no cloud" decision with usage data |

**The cost none of these remove is code signing.** An unsigned macOS binary
requires the user to go into System Settings to open it; Windows SmartScreen
warns. An Apple developer account and a Windows certificate are money and
bureaucracy, not code. QualiLab's "download and open" works because HTML
needs no signature. Budget this now; it is the same cost under Tauri or
pywebview.

The staged path wastes nothing: the PyInstaller binary is a prerequisite for
Tauri anyway.

## 6. Recommended order and why

1. Fix both READMEs (hours).
2. Generalize the codebook contract: several variables per codebook,
   neutral English field names, move V7 out of the package. Before any
   external user has a data file, because after that every schema change is
   a migration of someone else's data.
3. The "usable by a second person" package: settings screen with a
   persisted key, backend serving the frontend, `cifra` command, DB in the
   platform data dir, delete endpoints, cost estimate before a run, cancel,
   stuck-run recovery on startup, a local/OpenAI-compatible provider. Then
   hand it to two or three real people and watch.
4. Packaging: PyInstaller, pywebview, installers, signing.
5. Robustness for real corpora: bounded parallelism, rate-limit handling,
   resume.
6. Scientific depth: Krippendorff's alpha and Gwet's AC1 (the kappa paradox
   under class imbalance is real and the 2026-08-31 audit already flags it);
   repeated runs with majority vote (measured reproducibility was 66%);
   Halterman & Keith's label-free behavioral tests; a stratified-sampling
   helper for choosing what to hand-code, with size guidance. This is where
   "reference software" is earned, but only after people can run it.
7. License decision before any public release. "All rights reserved" blocks
   citation and forks; reference tools in this field spread by citation.

**Ordering constraints.** Packaging before schema generalization ships
installers whose database must then be migrated. Advanced metrics before a
second user are metrics built for the author. Tauri before PyInstaller is
inverted by dependency.

## 7. Trajectory risks

- **Process outweighs product.** The project becomes a showcase of agentic
  development rather than a tool someone uses.
- **Built for the author's V7 study.** Portuguese field names, bilingual
  codebooks, a gold set of one row. The tool's central thesis, validation,
  has never been exercised with statistical power. The first real
  validation with 100+ gold labels will find bugs and UX gaps no red-team
  found.
- **Feature accretion from interesting reading.** QualiLab interop,
  disclosure, reproducibility: all good, none requested by a user, each
  adding tables and endpoints that must cross the schema change in step 2.
- **Distribution paralysis.** Tauri + Rust + PyInstaller + signing on three
  OSes can eat a month with nothing shipped.
- **Parallel-session inconsistency.** One integration owner per day.
- **Provider lock-in.** Without a local model, Cifra is excluded from any
  sensitive-data use in Brazil.
