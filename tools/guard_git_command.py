"""guard_git_command.py -- PreToolUse hook: block destructive git commands
before Claude Code's Bash tool executes them.

Wired via .claude/settings.json (hooks.PreToolUse, matcher "Bash"). Reads
the tool-call JSON payload from stdin, inspects the Bash `command` string,
and exits 2 (Claude Code's "block this tool call" contract) if it looks
like a command that would discard uncommitted work or move HEAD out from
under other sessions sharing this working directory.

Why this exists (2026-09-02): four Claude Code sessions share one physical
working directory for this repo (not separate worktrees -- one folder, one
.git). One session ran `git checkout --orphan gh-pages-init` followed by
`git clean -fdx`, which switched HEAD for all four sessions at once and
then deleted another session's uncommitted edit. See
docs/research/2026-09-02_git_safety_governance_for_shared_agent_working_directory.md
for the full incident and the 3-model red-team review this script's design
is a direct response to.

WHAT THIS DOES NOT COVER -- read before trusting it as a complete guarantee,
per the red-team's own top finding (a command-blocklist hook can only ever
be a second line of defense, never the fix for the actual defect, which is
the shared working directory itself -- see the doc above for why `git
worktree` per session is the real fix this is defense-in-depth for):

  - Any execution path other than Claude Code's own Bash tool -- a Python
    script that calls `subprocess.run(["git", "clean", "-fdx"])`, a
    PowerShell tool invocation (this hook's matcher is "Bash" only), or a
    committed script that itself shells out to git, are all invisible to
    this hook.
  - Destructive commands that never mention "git" at all -- `rm -rf`,
    PowerShell's `Remove-Item -Recurse -Force`, etc.
  - A sufficiently determined bypass, e.g. redefining what a token means to
    git itself (`git config alias.<name> ...` is blocked below specifically
    because of this) or wrapping the real command in another layer this
    tokenizer doesn't unwrap.

This is a safety net for an agent making an honest mistake -- the exact
failure mode that produced the 2026-09-02 incident -- not a sandbox.
"""

from __future__ import annotations

import json
import re
import shlex
import sys

# Global git options that consume the NEXT token as a value (so the
# subcommand search must skip both). Deliberately not the only mechanism
# for finding the subcommand -- see _find_subcommand_candidates below for
# why relying solely on "walk past every global option correctly" was the
# root of a real bug (an unrecognized value-taking global option like
# `-O myorderfile` caused the walk to misidentify the git subcommand
# entirely, letting the real `clean -f` after it through unchecked).
VALUE_OPTS = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace",
    "--exec-path", "--config-env", "--super-prefix",
}

# Shell operators that separate distinct commands on one logical line.
# Kept as single characters deliberately: shlex.shlex(..., punctuation_chars=True)
# tokenizes "&&" as two adjacent "&" tokens and "||" as two adjacent "|"
# tokens, never as one two-character token -- a real bug in the version of
# this script this was ported from, where "&&" only happened to segment
# correctly because "&" (the single character) was also in this set. Made
# explicit here instead of relying on that coincidence.
SEPARATORS = {";", "&", "|", "\n"}

# Commands that, when they appear as a token anywhere before the `-c`
# argument, mean "the real command is hidden inside a following quoted
# string, which shlex tokenized as one opaque argument, not as separate
# tokens" -- shell wrapping is the single most-agreed bypass across all
# three models in the red-team review. When found, the quoted argument is
# recursively re-tokenized and re-checked.
SHELL_WRAPPERS = {"sh", "bash", "dash", "zsh", "ksh"}

CONFIRM_ENV_VAR = "CIFRA_CONFIRM_SHARED_HEAD_SWITCH"


def _bloquear(titulo: str, alternativa: str) -> None:
    print("=" * 70, file=sys.stderr)
    print(f" [BLOCKED - guard_git_command] {titulo}", file=sys.stderr)
    print("", file=sys.stderr)
    print(f" {alternativa}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    sys.exit(2)


def _flag_curta_com(letra: str, tok: str) -> bool:
    """-f, -fd, -fdx, -xdf... (a short-flag cluster containing `letra`)."""
    return bool(re.match(rf"^-[A-Za-z]*{letra}[A-Za-z]*$", tok))


def _looks_like_mass_or_glob_path(tok: str) -> bool:
    """A path argument that discards more than one specific, named file:
    the bare wildcard/root markers, any glob-looking pattern, or a
    directory (trailing slash). A single filename like `app.py` is NOT
    matched here -- narrowly reverting one specific file is a legitimate,
    common operation this guard should not block."""
    if tok in (".", "*", ":/", "./"):
        return True
    if tok.endswith("/"):
        return True
    if any(ch in tok for ch in ("*", "?", "[")):
        return True
    return False


def _find_subcommand_candidates(tokens: list[str]) -> list[tuple[int, str, list[str]]]:
    """Return every (index, subcommand, remaining_args) where `tokens[index]`
    is a plausible git subcommand -- i.e. every non-flag token, not just the
    first one found by walking past global options. Checking every
    candidate (not just "the" one a global-option walk lands on) is what
    closes the parser-desync bug: an unrecognized value-taking global
    option can make a naive single-pass walk land on the wrong token, but
    the real dangerous subcommand a few tokens later is still inspected
    here regardless."""
    candidates = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in VALUE_OPTS:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        candidates.append((i, tok, tokens[i + 1 :]))
        i += 1
    return candidates


def _checar_segmento(tokens: list[str], *, allow_shared_head_switch: bool) -> None:
    for _, sub, args in _find_subcommand_candidates(tokens):
        _checar(sub, args, allow_shared_head_switch=allow_shared_head_switch)


def _checar(sub: str, args: list[str], *, allow_shared_head_switch: bool) -> None:
    if sub == "add":
        for a in args:
            if a in (".", "*", ":/", "--all", "-u", "--update", "--renormalize"):
                _bloquear(
                    "Mass staging forbidden ('git add .'/-A/--all/-u).",
                    "Stage files one at a time: git add path/to/file.ext",
                )
            if re.match(r"^-[A-Za-z]*[Au][A-Za-z]*$", a):
                _bloquear(
                    "Mass staging forbidden ('git add .'/-A/--all/-u).",
                    "Stage files one at a time: git add path/to/file.ext",
                )

    elif sub == "reset":
        if "--hard" in args:
            _bloquear(
                "'git reset --hard' discards uncommitted work.",
                "Use 'git stash' or revert specific files instead.",
            )

    elif sub == "clean":
        for a in args:
            if a == "--force" or _flag_curta_com("f", a):
                _bloquear(
                    "'git clean' with -f deletes untracked files -- in this shared "
                    "working directory, that includes other sessions' untracked work.",
                    "Run 'git clean -n' first (dry run) to see what would be deleted.",
                )

    elif sub in ("restore", "checkout"):
        for a in args:
            if _looks_like_mass_or_glob_path(a):
                _bloquear(
                    "Mass or glob-pattern discard of working-tree changes.",
                    "Restore one specific file at a time: git restore path/to/file.ext",
                )
        if sub == "checkout":
            _checar_checkout_branch_switch(args, allow_shared_head_switch=allow_shared_head_switch)

    elif sub == "switch":
        _checar_checkout_branch_switch(args, allow_shared_head_switch=allow_shared_head_switch)

    elif sub == "push":
        for a in args:
            if a.startswith("--force") or _flag_curta_com("f", a):
                _bloquear(
                    "Force-push rewrites already-published history.",
                    "If this is genuinely needed, the human author must authorize "
                    "and run it manually.",
                )

    elif sub == "config":
        for a in args:
            if a.startswith("alias.") or a == "--global" and any(x.startswith("alias.") for x in args):
                _bloquear(
                    "Defining a git alias is not needed for anything in this repo, and "
                    "an alias can shadow a real subcommand's own safety checks "
                    "(e.g. 'git config alias.nuke \"clean -fdx\"' then 'git nuke' bypasses "
                    "the clean check above entirely).",
                    "Run the real git subcommand directly instead of defining an alias.",
                )

    elif sub in ("symbolic-ref", "update-ref"):
        # A read (no target argument, or only the ref name) is harmless;
        # writing a new target moves HEAD (or another ref) without ever
        # going through 'checkout'/'switch', bypassing the branch-switch
        # check below entirely if this weren't handled separately.
        non_flag_args = [a for a in args if not a.startswith("-")]
        if len(non_flag_args) >= 2:
            _bloquear(
                f"'git {sub}' with a target moves a ref (often HEAD) directly, "
                "the same shared-HEAD hazard as a branch switch, without going "
                "through 'checkout'/'switch' at all.",
                "If you genuinely need to repoint a ref, confirm with the user first.",
            )

    elif sub == "stash":
        if args and args[0] in ("drop", "clear"):
            _bloquear(
                "'git stash drop'/'clear' permanently discards stashed work -- "
                "possibly another session's, not just yours.",
                "Use 'git stash list' to check whose stash it is first.",
            )


def _checar_checkout_branch_switch(args: list[str], *, allow_shared_head_switch: bool) -> None:
    """Block a branch switch specifically (not a pathspec-restore use of
    'checkout', already handled above) in the shared main working
    directory. Not a blanket ban -- see the design doc for why hard-
    blocking every checkout breaks legitimate work (reviewing a PR branch,
    normal feature-branch workflows, git bisect). A dedicated `git
    worktree` has its own HEAD, so switching there cannot disrupt any
    other session -- only the shared main directory is restricted."""
    if allow_shared_head_switch:
        return
    non_flag_args = [a for a in args if not a.startswith("-")]
    is_branch_switch = "--orphan" in args or "-b" in args or "-B" in args or bool(non_flag_args)
    # A bare pathspec-restore checkout (e.g. `git checkout -- file.py`) is
    # not a branch switch -- only flag it if there's no `--` isolating a
    # pathspec, or the flags themselves indicate a new branch.
    if "--" in args and not ("--orphan" in args or "-b" in args or "-B" in args):
        return
    if is_branch_switch:
        _bloquear(
            "Branch switch in the SHARED main working directory moves HEAD for "
            "every session currently working here at once -- this is exactly "
            "what caused the 2026-09-02 incident (see docs/research/).",
            f"If this is a dedicated `git worktree`, this check should not have "
            f"fired -- report that as a bug. Otherwise: prefer `git worktree add` "
            f"for isolated branch work. If you have confirmed with the user that "
            f"switching HEAD here, for everyone, is genuinely intended right now, "
            f"re-run prefixed with {CONFIRM_ENV_VAR}=1 (e.g. "
            f"`{CONFIRM_ENV_VAR}=1 git checkout ...`).",
        )


def _is_worktree(cwd_git_path: str = ".git") -> bool:
    """A dedicated `git worktree` has a *file* named .git (containing
    'gitdir: <path to the real admin dir>'), not a directory -- the main
    repository (or a plain clone) has a directory. Branch switches are
    safe to allow unconditionally in a worktree; only the shared main
    directory needs the confirmation gate."""
    import os

    return os.path.isfile(cwd_git_path)


def _extract_command(raw_stdin: str) -> str | None:
    try:
        dados = json.loads(raw_stdin)
        comando = dados.get("tool_input", {}).get("command", "")
    except Exception:
        comando = raw_stdin
    if not isinstance(comando, str) or "git" not in comando:
        return None
    return comando


def _tokenize(comando: str) -> list[str]:
    lexer = shlex.shlex(comando, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _is_git_token(tok: str) -> bool:
    return tok == "git" or tok.endswith("/git") or tok.endswith("\\git.exe") or tok == "git.exe"


def _split_segments(tokens: list[str]) -> list[list[str]]:
    segmentos: list[list[str]] = []
    atual: list[str] = []
    for tok in tokens + [";"]:
        if tok in SEPARATORS:
            if atual:
                segmentos.append(atual)
            atual = []
        else:
            atual.append(tok)
    return segmentos


def check_command(comando: str, *, allow_shared_head_switch: bool | None = None) -> None:
    """Raises SystemExit(2) (via _bloquear) if `comando` looks destructive.
    Returns normally (no exception) if it looks safe. Exposed as a plain
    function, separate from stdin/JSON handling, specifically so it can be
    unit-tested directly without constructing a fake hook payload."""
    if allow_shared_head_switch is None:
        allow_shared_head_switch = _is_worktree()
    if f"{CONFIRM_ENV_VAR}=1" in comando or f"{CONFIRM_ENV_VAR}=true" in comando:
        allow_shared_head_switch = True

    try:
        tokens = _tokenize(comando)
    except ValueError:
        _bloquear(
            "Could not safely parse a command that invokes git (e.g. unbalanced quotes).",
            "Rewrite the command more simply (balanced quotes, one action per call).",
        )
        return

    for segmento in _split_segments(tokens):
        # Shell-wrapper unwrapping: if this segment invokes sh/bash/eval
        # with a quoted string argument, that argument is one opaque shlex
        # token containing the real command -- recursively check it.
        for idx, tok in enumerate(segmento):
            base = tok.rsplit("/", 1)[-1]
            if base in SHELL_WRAPPERS and "-c" in segmento[idx + 1 :]:
                c_idx = segmento.index("-c", idx + 1)
                if c_idx + 1 < len(segmento):
                    check_command(segmento[c_idx + 1], allow_shared_head_switch=allow_shared_head_switch)
            if tok == "eval" and idx + 1 < len(segmento):
                check_command(" ".join(segmento[idx + 1 :]), allow_shared_head_switch=allow_shared_head_switch)

        for idx, t in enumerate(segmento):
            if _is_git_token(t):
                _checar_segmento(segmento[idx + 1 :], allow_shared_head_switch=allow_shared_head_switch)
                break


def main() -> None:
    raw = sys.stdin.read()
    comando = _extract_command(raw)
    if comando is None:
        sys.exit(0)

    check_command(comando)
    sys.exit(0)


if __name__ == "__main__":
    main()
