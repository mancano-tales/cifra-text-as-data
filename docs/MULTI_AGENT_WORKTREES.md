# Running multiple Claude Code sessions against this repo: use `git worktree`

**Read this if you are (or are about to be) one of several Claude Code
sessions working on `text-as-data`/Cifra at the same time.** Full incident
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

There is no per-worktree Python virtual environment set up by default in
this repo. `pip install -e .` registers the *currently active* checkout's
`src/` as the editable install for the **entire** Python environment on
this machine — running it from one worktree silently repoints
`import text_as_data` for every other worktree and the main checkout too.
A session running tests right after another session ran `pip install -e .`
from a different worktree may see confusing, unrelated failures that have
nothing to do with its own changes.

**Correct fix, not yet set up as of this writing**: a dedicated virtual
environment per worktree (`python -m venv .venv` inside each worktree,
then `pip install -e ".[dev]"` inside that venv) fully isolates this.
Until that's standard practice here, at minimum: if tests fail in a way
that doesn't match what you changed, re-run `pip install -e ".[dev]"` from
your own directory before assuming your code is broken — you may just be
pointed at a different worktree's `src/`.

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
