# Preventing destructive git operations in a shared multi-agent working directory

**Date**: 2026-09-02
**Context**: A real incident during today's session — bootstrapping a `gh-pages`
branch, I ran `git checkout --orphan gh-pages-init` followed by
`git clean -fdx -e site -e .git` in `text-as-data`'s working directory, which
four separate Claude Code sessions share (not separate worktrees — one
physical folder, one `.git`). The branch switch changed `HEAD` for all four
sessions simultaneously; the clean then deleted an in-progress uncommitted
edit another session (`text-as-data-6d`) was making at that exact moment in
`app.py`/`test_app.py`, plus wiped `frontend/node_modules` as collateral
damage. Nothing already committed was lost — only uncommitted working-tree
state, which is real loss regardless of whether the session could
reconstruct it from its own conversation context.

This document records the investigation into preventing a repeat, the
red-team review of the resulting plan across three independent LLMs, and
the revised plan that came out of it. Implementation follows this
document, not before it — the author asked for the investigation and
critique to be written up in detail before any code changes landed.

## Prior art investigated

The author pointed at two existing repos rather than asking for a design
from scratch:

### `Mancano2026-MA-Thesis` (the author's dissertation repo)

Has a mature governance setup: `hooks/` (`pre-commit`, `commit-msg`,
`post-merge`), `tools/` (`git-wrapper.ps1`, `validate-governance.R`,
several others), `AGENTS.md`/`CLAUDE.md`/`GUIDANCE.md`.

- `hooks/pre-commit` and `hooks/commit-msg` validate governance-file
  consistency (via an R script) and enforce Conventional Commits with a
  thesis-specific type list (`thesis|lit|data|draft|...`) — not relevant
  to today's incident, specific to that repo's academic-writing workflow.
- `tools/git-wrapper.ps1` intercepts `git add .`/`-A`, `reset --hard`,
  `restore .`, `clean -fd` — **but only for whoever chooses to invoke `git`
  through this wrapper** (a PowerShell alias in an interactive shell). It
  does not intercept a command an agent runs directly via its own Bash
  tool, which spawns `git.exe` without going through any shell profile or
  alias. This mechanism would not have prevented today's incident.

### `agentic-workflow-template` (the author's public template repo, which
the thesis repo's own governance setup derives from)

Has the actual relevant mechanism: `tools/guard-git-command.py` +
`guard-git-command.sh`, wired via a committed `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Bash", "hooks": [{ "type": "command", "command": "bash tools/guard-git-command.sh" }] }
    ]
  }
}
```

This is a Claude Code **`PreToolUse` hook** — it runs before the agent's
own Bash tool call executes, reading the tool-call payload from stdin and
exiting with code 2 to block it. This is the correct interposition point:
it does not depend on the agent choosing to use a wrapper: it fires on
every Bash invocation regardless of what the agent typed. `guard-git-command.sh`
shells out to `guard-git-command.py`, with a deliberately blunt bash-only
regex fallback if Python isn't available (fails closed on anything
resembling a destructive git verb, accepting false positives over false
negatives).

The script's own comments document a strikingly similar near-miss during
its own development: *"During the implementation of this guard, on
2026-08-11, a `git clean -fdx` run to TEST the then-broken wrapper version
wiped the untracked files of the working repo — including an earlier
version of this same file. Test destructive commands in a throwaway
directory, never in the repository in use."* Today's incident is the same
mistake, in a different repo, five months later, made by an agent that had
not read this comment.

`guard-git-command.py`'s logic (see the previous conversation turn for the
full source as red-teamed): tokenizes the Bash command with `shlex`
(respecting quotes and a `punctuation_chars=True` split on shell
operators), walks past recognized global git options (`-C`, `-c`,
`--git-dir`, ...), finds the subcommand, and blocks:

- `git add .` / `-A` / `--all` / `-u` (mass staging)
- `git reset --hard`
- `git clean` with any flag cluster containing `-f`
- `git restore .` / `git checkout .` / `:/` (mass working-tree discard)
- `git push --force` / `-f`

## The plan first proposed (v1)

1. Port `guard-git-command.py`/`.sh` to `text-as-data`, adapted (drop the
   thesis/R-specific parts — none of that applies here).
2. Add `.claude/settings.json` wiring the `PreToolUse` hook.
3. **New addition, not in the source template**: also block/flag branch-
   switching commands (`checkout <branch>`, `checkout -b`, `checkout
   --orphan`, `switch`) — motivated directly by today's incident, since
   the branch switch (not the clean) was what disrupted the other
   session's live work, and the existing guard doesn't touch it at all.
4. Test in an isolated clone, not the shared working directory (learning
   directly from the guard's own documented near-miss).
5. Document in `AGENTS.md`/`TODO.md`/`NEWS.md`, referencing today's
   incident.

Before implementing, the author asked for this plan to be red-teamed by
independent models rather than accepted on the strength of it sounding
reasonable.

## Red-team methodology

Three models, same prompt, run in parallel via `agy` (Google Antigravity
CLI) from an isolated scratch directory (not the shared working tree):

- `claude-sonnet-4-6`
- `gemini-3.7-flash-high`
- `gemini-3.1-pro-high`

The prompt gave each model: the incident narrative, the full source of
`guard-git-command.py`, the proposed branch-switch addition, and six
explicit questions — does this prevent a repeat of the incident; what are
the bypass vectors (with specific classes suggested: quoting/subshells,
absolute paths, plumbing commands like `symbolic-ref`, non-shell
invocation, raw filesystem ops); is blocking all branch switches too
disruptive; does exit-code-2 fail closed; is there a fundamentally better
architecture than a command-blocklist hook at all; and are there bugs in
the tokenizer itself. Each model was told to be skeptical and to earn any
conclusion that the plan was fine, not default to agreement.

## Findings

### Unanimous verdict: the guard, even hardened, does not solve the actual problem

All three models, independently, walked through the literal incident
command against the literal guard source and reached the same conclusion
before being asked to recommend anything: **the original v1 guard would
not have prevented the incident.** `git checkout --orphan gh-pages-init`
matches none of the `checar()` cases (`analisar` returns subcommand
`checkout`, args `["--orphan", "gh-pages-init"]`; the check only looks for
`.`/`:/`/`*` as an argument, which `--orphan` and a branch name are not) —
it would have been **allowed**, corrupting `HEAD` for all four sessions
exactly as it did today. Only the `clean -fdx` step would have been
blocked, after the damage from the branch switch was already done.

All three then, independently and without prompting toward this specific
answer, named the same root cause and the same fix: **four independent
agents sharing one mutable `HEAD`/index/working tree is the actual defect
— not the absence of a big enough blocklist.** The fix that removes the
defect at the root is **`git worktree`**: give each session its own
physical directory (own `HEAD`, own index, own working tree) backed by the
same shared `.git` object database. In that architecture, `git clean -fdx`
or `git checkout --orphan` run inside one worktree cannot touch another
worktree's files or branch — not "is blocked by a check," but "has no
mechanism by which it could happen." Gemini 3.1 Pro's framing: *"You are
trying to solve a concurrency/architecture failure with a regex parser."*
Claude Sonnet's: *"Shipping [the guard] without worktrees is like putting
a better lock on a screen door."*

### Bypass vectors found, cross-checked across models

| Vector | Found by | Detail |
|---|---|---|
| `sh -c "git clean -fdx"` / `bash -c` / `eval` / PowerShell `Invoke-Expression` | Sonnet, Flash, Pro (all three) | `shlex` tokenizes the outer command; the inner `git ...` is a single quoted string argument to `sh`/`bash`/`eval`, never separately tokenized, so the walk for a token literally equal to `git` never finds it. Complete, unremarked bypass. |
| `git symbolic-ref HEAD refs/heads/X` / `git update-ref` | Sonnet, Flash | Moves `HEAD` without going through `checkout` or `switch` at all — the proposed branch-switch addition wouldn't have caught this class of command since it only pattern-matches on the subcommand names `checkout`/`switch`. |
| `subprocess.run(["git", "clean", "-fdx"])` from Python (or any non-Bash-tool execution path) | Sonnet, Flash, Pro (all three) | The hook's `matcher` is `"Bash"` — it fires only for Claude Code's Bash tool. Any other execution path (a Python tool, a committed script that itself shells out to git) is invisible to it. |
| Raw filesystem destruction (`rm -rf`, PowerShell `Remove-Item -Recurse -Force`) | Sonnet, Flash, Pro (all three) | Out of scope by construction — the guard only inspects commands containing the substring `"git"`. Today's actual `frontend/node_modules` collateral damage came from `git clean`, but the same working-tree destruction is reachable with no `git` in the command at all. |
| `git config alias.nuke "clean -fdx"` then `git nuke` | **Pro only** | The subcommand token literally becomes `"nuke"`; `checar()` never recognizes it as a `clean` invocation. Not found by the other two models — the single sharpest, most specific bypass across all three runs. |
| Unknown global flag that takes a value, not in `VALUE_OPTS` (e.g. `git -O myorderfile clean -f`) | Pro (concrete case) + Sonnet (general gap in `VALUE_OPTS`'s coverage) | `analisar()`'s walk treats `-O` as a bare flag (consumes 1 token, not 2, since `-O` isn't in `VALUE_OPTS`), then reads `myorderfile` as the subcommand. `checar("myorderfile", ["clean", "-f"])` matches nothing; the real `clean -f` after it is never inspected as part of the same command. |
| `&&` tokenizes to two adjacent `&` characters under `shlex(..., punctuation_chars=True)`, not one `&&` token | Sonnet | `SEPARATORS` contains the two-character string `"&&"`, which can never match either of the two single-character `"&"` tokens `shlex` actually produces. Verified by direct execution: `list(shlex.shlex("git add . && git push", ...))` → `['git', 'add', '.', '&', '&', 'git', 'push']`. The script still happens to segment correctly today only because `"&"` (the single character) is *also* in `SEPARATORS` — a coincidence of the specific set contents, not a designed behavior, and not guaranteed to hold for every shell operator the tokenizer might someday emit. |
| `git restore src/` or `git restore '*.py'` (a real subpath, not the literal string `.`/`*`/`:/`) | Pro | The check only matches the argument being exactly `.`, `:/`, or `*` — a directory or glob-quoted path still discards real working-tree content and is not caught. |
| `git stash drop` / `git stash clear` | Flash | Not covered by any `checar()` branch at all — stashed work (potentially another session's) can be discarded outright. |
| Windows/PowerShell tool-matcher gap | Sonnet, Pro | If a Claude Code session on this Windows machine executes a command via a PowerShell tool rather than the Bash tool, `matcher: "Bash"` never fires. Not confirmed as currently exploitable in this specific environment, but flagged as a real gap to verify, not dismiss. |
| `.claude/settings.json` "takes immediate effect for other sessions" claim | Sonnet | Only true if Claude Code re-reads settings from disk per tool call rather than caching them at session start — unverified against actual Claude Code hook-loading behavior. Flagged as an overstated claim in the original plan rather than a confirmed fact. |

### The branch-switch blocking question

Unanimous: hard-blocking every `checkout`/`switch` is too disruptive to
ship as-is — it would prevent checking out a PR branch to review it,
normal feature-branch workflows, and `git bisect`, and Gemini 3.1 Pro
points out the deeper bind directly: *"if you allow branch switching in a
shared directory, you guarantee future incidents... This dilemma is the
ultimate proof that the shared-directory architecture is unviable."*
Claude Sonnet's concrete alternative, adopted into the revised plan below:
make the check **context-aware** rather than a blanket block — before
restricting a branch switch, check whether the current directory is
already a dedicated `git worktree` (safe: the risk is confined to that
worktree) versus the shared main working directory (dangerous: block or
require an explicit, spelled-out confirmation phrase in the command
itself, e.g. an explicit flag the agent must add on purpose after being
told what it means).

### Exit-code / fail-closed behavior

The guard's own bash-only fallback (used when Python is unavailable) is
deliberately blunt by design — matches any git invocation that resembles a
destructive verb, accepting false positives to avoid a false negative when
the precise tokenizer can't run. All three models flagged the same
residual uncertainty rather than asserting it away: whether Claude Code's
`PreToolUse` hook mechanism treats a **hook script crash** (as opposed to
a deliberate `sys.exit(2)`) as fail-closed (block) or fail-open (proceed)
is not verified against Claude Code's actual documented behavior in this
investigation — flagged as something to check before relying on it, not
assumed.

## Revised plan (v2)

1. **Primary fix — `git worktree` per session.** Give each concurrent
   Claude Code session working on this repo its own physical directory
   (own `HEAD`, own index, own working tree), all backed by the same `.git`
   object database, so commits/branches/stashes are instantly visible
   across sessions without push/pull, but a destructive command in one
   session's directory has no path by which it can reach another's files.
   This is not something one session can force onto three already-running
   others unilaterally (each session's working directory is set by how it
   was launched, not by a setting one session can flip for the rest) — the
   concrete next step is documenting the `git worktree add` setup clearly
   enough that the author (or each session, told to do so) can adopt it,
   and flagging it to the other active sessions.
2. **Defense-in-depth — a hardened `guard-git-command.py`/`.sh`,
   scope honestly documented rather than oversold.** Port and fix the
   concrete bugs found: the `VALUE_OPTS`/parser-desync gap, the `&&`
   tokenizer fragility, add `git config alias.*` inspection (or at minimum
   block `git config alias.` writes outright, since there's no legitimate
   reason an agent needs to define a git alias in this repo), add
   `symbolic-ref`/`update-ref`/`stash drop`/`stash clear` to the blocked
   set, and broaden the `restore`/`checkout` path check beyond exact
   `.`/`:/`/`*` matches. Explicitly document in the script's own header
   and in `AGENTS.md` what this does **not** cover — `sh -c`/`eval`
   wrapping, non-Bash-tool execution paths, raw filesystem commands — so
   it is never mistaken for a complete guarantee the way the original v1
   framing implied.
3. **Branch-switch handling**: context-aware per Sonnet's proposal above,
   not a blanket block, once (1) is in place — worktree-aware allow, main-
   directory-requires-explicit-confirmation.
4. **Testing discipline**: exercise the guard's own logic (unit tests
   against the tokenizer, not manual dry runs) in an isolated location —
   both because that is simply correct test hygiene, and because the
   source guard's own comments record a prior real incident from testing
   a broken version of itself directly in a live repo.
5. **Verify, don't assume**: confirm Claude Code's actual `PreToolUse`
   fail-open/fail-closed behavior on a hook script crash, and confirm
   whether `.claude/settings.json` changes apply to already-running
   sessions without a restart, before stating either as fact in
   documentation aimed at other sessions.

## What this changes about how the original plan was presented

The v1 plan, as proposed to the author, claimed more than it delivered: it
was framed as "the fix" for the incident when a literal trace of the
incident's own first command shows it would not have been caught. That
framing gap is worth naming plainly rather than quietly correcting in the
implementation — the value of the red-team round was exactly to catch an
plan that sounded complete and wasn't.
