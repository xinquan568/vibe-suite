#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# Refuse to let a pipeline run touch the suite's own core artifacts.
#
# The auditor writes only to the data branch and to case-studies/. Everything else here — the
# skills, agents, commands, hooks and the plugin manifest — is human-authored, and a workflow
# that edits it has escaped its remit. Run this before any `git add` or `git commit` in an
# auditor workflow; a non-zero exit means stop.
#
# Three change kinds are checked, and the third is the one that matters:
#
#   * unstaged  — `git diff --name-only HEAD`
#   * staged    — `git diff --cached --name-only`
#   * UNTRACKED — `git ls-files --others --exclude-standard`
#
# `git diff` does not surface a file that has never been added, so a guard built on diff alone
# is silently blind to `mkdir skills/x && echo ... > skills/x/SKILL.md`: brand-new protected
# content, invisible, committed by the next `git add -A`. The untracked probe is the whole
# reason this guard is trustworthy.
#
# Usage:  bash auditor/scripts/guard-protected-paths.sh   [--data-dir DIR]
# `--data-dir` is accepted and ignored: the guard inspects the CODE checkout it runs in, and
# taking the flag keeps every helper's invocation uniform.

set -u

PROTECTED=(
  "skills/" "agents/" "commands/" "hooks/"
  "CLAUDE.md" "README.md" "RULES.md" "EXAMPLES.md"
  ".claude-plugin/" ".nlpm-test/"
)

violations=0

for path in "${PROTECTED[@]}"; do
  unstaged="$(git diff --name-only HEAD -- "$path" 2>/dev/null)"
  staged="$(git diff --cached --name-only -- "$path" 2>/dev/null)"
  untracked="$(git ls-files --others --exclude-standard -- "$path" 2>/dev/null)"

  if [ -n "$unstaged" ] || [ -n "$staged" ] || [ -n "$untracked" ]; then
    violations=$((violations + 1))
    echo "VIOLATION: protected path modified: $path"
    [ -n "$unstaged" ]  && echo "  unstaged:  $unstaged"
    [ -n "$staged" ]    && echo "  staged:    $staged"
    [ -n "$untracked" ] && echo "  untracked: $untracked"
  fi
done

if [ "$violations" -gt 0 ]; then
  echo
  echo "BLOCKED: $violations protected path(s) were modified."
  echo "Auditor workflows write only the data branch and case-studies/."
  echo "A deliberate rule change is a human commit, made outside the pipeline."
  exit 1
fi

echo "Guard passed: no protected paths modified."
exit 0
