# Running multiple Claude Code sessions against this repo: use `git worktree`

**Read this if you are (or are about to be) one of several Claude Code
sessions working on `text-as-data`/Decifra at the same time.** Full incident
history and the reasoning behind this recommendation:
[`docs/research/2026-09-02_git_safety_governance_for_shared_agent_working_directory.md`](research/2026-09-02_git_safety_governance_for_shared_agent_working_directory.md).

## The short version

Do not point two Claude Code sessions at the same physical checkout of
this repo. On 2026-09-02, four sessions shared one working directory; one
session's `git checkout --orphan` + `git clean -fdx` switched `HEAD` for
all four at once and permanently deleted another session's uncommitted
edit. A [3-model red-team review](research/2026-09-02_git_safety_governance_for_shared_agent_working_directory.md)
of the fallback fix (a command-blocking hook) unanimously concluded that a
blocklist is defense-in-depth at best — the actual fix is giving each
session its own working directory. This repo does ship that hook
(`.claude/settings.json` + `tools/guard_git_command.py`) and it *is*
active in any checkout of this repo, worktrees included, since it's
committed content — but treat it as a safety net for an honest mistake,
not a substitute for isolation.

## Setting up a worktree for a new session

From an existing checkout of this repo (the "main" one, or any other
worktree):

```bash
git worktree add ../text-as-data-<short-name> -b <short-name>/<what-you-are-doing>
```

Example:

```bash
git worktree add ../text-as-data-validation-ui -b agent/validation-ui
```

This creates a **new physical directory** at `../text-as-data-<short-name>`
with its own `HEAD`, its own index, and its own working tree — but backed
by the *same* `.git` object database as the checkout you ran the command
from. Commits, branches, and stashes made in one worktree are immediately
visible to `git log`/`git branch` in every other worktree of the same
repo, with no push/pull needed. A destructive command (`git clean -fdx`,
`git reset --hard`, `git checkout --orphan`) run inside one worktree
cannot reach any other worktree's files or branch — there is no shared
state left for it to corrupt.

Point the new Claude Code session at `../text-as-data-<short-name>` (open
it there, or `cd` there before starting work) rather than the original
directory.

## Migrating an already-running session

A session cannot move its own working directory mid-conversation — the
working directory a session operates in is fixed by how it was opened.
Two practical paths:

1. **Finish the current unit of work, commit it, then re-open the session
   in a new worktree** (per the setup steps above) for whatever comes
   next. This is the lowest-friction path and was how at least one session
   adopted this on 2026-09-02.
2. If work is genuinely blocked mid-flight and cannot be committed yet,
   coordinate explicitly with whichever other sessions share the current
   directory before either session runs anything that touches `HEAD` or
   discards working-tree state — this is exactly the coordination that
   was skipped on 2026-09-02.

## Known friction: `pip install -e .` is a global pointer, not per-directory

**This has already caused a real, confusing failure (2026-09-02) — not
just a theoretical risk.** A worktree isolates the filesystem and git
state, but not a shared global Python environment. One session ran
`pip install -e .` from its own worktree; another session's `pytest` run,
already in progress in a *different* worktree, silently started running
against the first worktree's `providers.py` instead of its own —
surfacing as an `AttributeError` on a class attribute that only existed in
the other worktree's version of the file. Nothing about that failure
pointed at "wrong environment" on its face; it read like a real code bug.

**Do this per worktree, not just when something looks broken**:

```bash
cd ../text-as-data-<short-name>
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -e ".[dev]"
```

Every subsequent `pytest`/`python` invocation in that worktree should go
through this venv (activate it per shell, or call
`.venv\Scripts\python.exe`/`.venv/bin/python` directly). This is not
optional hardening — treat "no venv yet" as leaving this exact bug latent,
not as a minor inconvenience. If a test failure doesn't match anything
you changed, suspect this before suspecting your own code — but the venv
is what actually prevents it, not vigilance after the fact.

## What the guard hook does and does not add on top of this

Once you're in a proper worktree, the `PreToolUse` guard
(`tools/guard_git_command.py`) allows branch switches freely — the
worktree already contains the blast radius. It still blocks the baseline
destructive set (`add -A`, `reset --hard`, `clean -f*`, mass/glob
`restore`/`checkout`, `push --force`, git-alias definitions, direct
`HEAD`-moving ref writes, `stash drop`/`clear`) inside that worktree too,
because those remain bad ideas even when they can't hurt anyone else — see
the guard's own module docstring for exactly what it does and does not
cover.
