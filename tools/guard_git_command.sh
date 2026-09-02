#!/usr/bin/env bash
# guard_git_command.sh -- PreToolUse hook entry point (see guard_git_command.py
# for the full rationale and the incident this responds to).
#
# Claude Code invokes this with the tool-call JSON payload on stdin;
# exiting 2 blocks the tool call. Delegates the actual analysis to
# guard_git_command.py, which tokenizes properly (quotes, shell operators,
# global git options) instead of relying on regex alone.
#
# Bash-only fallback below (no Python found): deliberately blunt, matching
# any git invocation that resembles a destructive verb anywhere in the
# string. This trades false positives for never producing a false
# negative when the precise tokenizer can't run -- fail closed, not open.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$DIR/guard_git_command.py"

for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1; then
    exec "$cand" "$PY"
  fi
done

PAYLOAD=$(cat)

if echo "$PAYLOAD" | grep -q "git"; then
  if echo "$PAYLOAD" | grep -qE '(clean[^|;&]*(-[A-Za-z]*f|--force)|reset[^|;&]*--hard|push[^|;&]*(-[A-Za-z]*f|--force)|add[[:space:]]+[^|;&]*(-[A-Za-z]*[Au]|--all|--update|--renormalize|\.|\*|:/)|(restore|checkout)[[:space:]]+[^|;&]*(\.|:/|\*)([[:space:]]|"|$)|checkout[[:space:]]+(--orphan|-[bB])|config[[:space:]]+[^|;&]*alias\.|stash[[:space:]]+(drop|clear)|(symbolic-ref|update-ref)[[:space:]]+[A-Za-z])'; then
    echo "======================================================================" >&2
    echo " [BLOCKED - guard_git_command] Potentially destructive git command." >&2
    echo "" >&2
    echo " Python is unavailable, so the precise tokenizer can't run, and this" >&2
    echo " blunt fallback blocks by precaution (fail closed). Install Python 3" >&2
    echo " for the exact check, or run the action manually after confirming" >&2
    echo " what it affects." >&2
    echo "======================================================================" >&2
    exit 2
  fi
fi

exit 0
