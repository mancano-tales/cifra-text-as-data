"""Unit tests for tools/guard_git_command.py's check_command().

Per the 2026-09-02 red-team review (docs/research/2026-09-02_git_safety_
governance_for_shared_agent_working_directory.md), testing this guard's
logic directly (not just eyeballing it) is exactly the discipline that was
missing when an earlier version of a similar guard was tested by running a
real destructive command against a live repo. These tests exercise
check_command() as a plain function -- no subprocess, no live git state.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from guard_git_command import CONFIRM_ENV_VAR, check_command  # noqa: E402


def blocked(command: str, **kwargs) -> bool:
    try:
        check_command(command, **kwargs)
    except SystemExit as exc:
        assert exc.code == 2
        return True
    return False


# ---------------------------------------------------------------------------
# The actual incident, replayed
# ---------------------------------------------------------------------------


def test_blocks_the_actual_incident_clean_step():
    assert blocked("git clean -fdx -e site -e .git")


def test_blocks_the_actual_incident_orphan_checkout_step_in_shared_dir():
    # This is the step the ORIGINAL (unfixed) guard let through -- the
    # whole reason this test module exists.
    assert blocked("git checkout --orphan gh-pages-init", allow_shared_head_switch=False)


def test_allows_orphan_checkout_inside_a_dedicated_worktree():
    assert not blocked("git checkout --orphan gh-pages-init", allow_shared_head_switch=True)


# ---------------------------------------------------------------------------
# Baseline blocks (ported from the original guard, must still work)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git add .",
        "git add -A",
        "git add --all",
        "git reset --hard",
        "git reset --hard HEAD~1",
        "git clean -f",
        "git clean -fd",
        "git clean --force",
        "git restore .",
        "git checkout .",
        "git push --force",
        "git push -f",
        "git push origin main --force",
    ],
)
def test_baseline_destructive_commands_still_blocked(command):
    assert blocked(command)


@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git add src/app.py",
        "git commit -m 'a normal message'",
        "git restore src/app.py",
        "git checkout -- src/app.py",
        "git push origin main",
        "git log --oneline",
        "git diff",
    ],
)
def test_safe_commands_not_blocked(command):
    assert not blocked(command)


# ---------------------------------------------------------------------------
# Bugs the red-team found in the ORIGINAL script, now fixed
# ---------------------------------------------------------------------------


def test_unrecognized_global_flag_with_value_no_longer_hides_the_real_subcommand():
    # gemini-3.1-pro-high's finding: an unrecognized value-taking global
    # option (not in VALUE_OPTS) made the original single-pass walk
    # misidentify the subcommand as the option's own value, letting the
    # real 'clean -f' after it through unchecked.
    assert blocked("git -O myorderfile clean -f")


def test_double_ampersand_separator_is_handled_explicitly():
    # claude-sonnet-4-6's finding: shlex(..., punctuation_chars=True)
    # tokenizes "&&" as two adjacent single "&" tokens, never one "&&"
    # token -- the original SEPARATORS set containing the string "&&"
    # could never match either token. Verify the destructive half of a
    # compound command is still caught regardless.
    assert blocked("git add file.py && git clean -fdx")


def test_double_pipe_separator_is_handled_explicitly():
    assert blocked("git status || git reset --hard")


def test_alias_definition_is_blocked_outright():
    # gemini-3.1-pro-high's sharpest finding, found by no other model:
    # `git config alias.nuke "clean -fdx"` then `git nuke` bypasses a
    # subcommand-name blocklist entirely, since "nuke" is never recognized
    # as a destructive verb. Blocking the alias *definition* closes this
    # regardless of what name the alias is given.
    assert blocked('git config alias.nuke "clean -fdx"')
    assert blocked("git config --global alias.wipe reset")


def test_symbolic_ref_write_is_blocked():
    # Moves HEAD without ever calling checkout/switch.
    assert blocked("git symbolic-ref HEAD refs/heads/gh-pages-init")


def test_symbolic_ref_read_is_not_blocked():
    assert not blocked("git symbolic-ref HEAD")


def test_update_ref_write_is_blocked():
    assert blocked("git update-ref HEAD refs/heads/main")


def test_stash_drop_and_clear_are_blocked():
    assert blocked("git stash drop")
    assert blocked("git stash clear")


def test_stash_list_and_push_are_not_blocked():
    assert not blocked("git stash list")
    assert not blocked("git stash push -m wip")


def test_glob_pattern_restore_is_blocked_not_just_exact_star():
    # gemini-3.1-pro-high's finding: only exact "." / ":/" / "*" were
    # checked, so a real glob or directory argument discarded working-tree
    # content without tripping the guard.
    assert blocked("git restore '*.py'")
    assert blocked("git checkout src/")


def test_single_named_file_restore_is_still_allowed():
    # Must not over-block: reverting one specific file is legitimate and
    # common, not the mass-discard hazard this guard targets.
    assert not blocked("git restore src/app.py")


# ---------------------------------------------------------------------------
# Shell-wrapper bypass (found independently by all three red-team models)
# ---------------------------------------------------------------------------


def test_sh_dash_c_wrapper_no_longer_hides_the_command():
    assert blocked('sh -c "git clean -fdx"')


def test_bash_dash_c_wrapper_no_longer_hides_the_command():
    assert blocked('bash -c "git reset --hard"')


def test_eval_wrapper_no_longer_hides_the_command():
    assert blocked('eval "git clean -fdx"')


def test_sh_dash_c_with_safe_inner_command_is_not_blocked():
    assert not blocked('sh -c "git status"')


# ---------------------------------------------------------------------------
# Branch-switch context-awareness (the confirmation escape hatch)
# ---------------------------------------------------------------------------


def test_plain_branch_checkout_blocked_in_shared_dir_by_default():
    assert blocked("git checkout main", allow_shared_head_switch=False)


def test_plain_branch_checkout_allowed_with_explicit_confirmation_env_var():
    assert not blocked(f"{CONFIRM_ENV_VAR}=1 git checkout main", allow_shared_head_switch=False)


def test_new_branch_checkout_blocked_in_shared_dir():
    assert blocked("git checkout -b feature/x", allow_shared_head_switch=False)


def test_switch_command_also_gated():
    assert blocked("git switch main", allow_shared_head_switch=False)
    assert not blocked("git switch main", allow_shared_head_switch=True)


# ---------------------------------------------------------------------------
# Non-git and malformed input
# ---------------------------------------------------------------------------


def test_non_git_command_is_ignored():
    assert not blocked("npm install")
    assert not blocked("pytest -q")


def test_unbalanced_quotes_fail_closed():
    with pytest.raises(SystemExit) as exc_info:
        check_command('git commit -m "unbalanced')
    assert exc_info.value.code == 2
