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
# Usage:  CODE_DIR=<code checkout> bash auditor/scripts/guard-protected-paths.sh   [--data-dir DIR]
# The guard inspects the CODE checkout named by $CODE_DIR — every auditor workflow binds it at
# workflow level and calls this script after `cd "$DATA_DIR"` (vibe-213 / S17) — and falls back to
# the current directory when CODE_DIR is unset (standalone use, the unit tests). A target that is
# not a git work tree is refused (exit 2), never reported clean. `--data-dir` is accepted and
# ignored; taking the flag keeps every helper's invocation uniform.

set -u

# Inspect the CODE checkout. Every auditor workflow binds CODE_DIR at workflow level and calls this
# guard after `cd "$DATA_DIR"`, so the target is $CODE_DIR when set; standalone use (the unit tests)
# falls back to the current directory. A target that is not a git work tree is a refusal, not a pass:
# with no repository the three probes below would print nothing and the guard would report clean.
target="${CODE_DIR:-$PWD}"
# `rev-parse --is-inside-work-tree` exits 0 and prints `false` inside a .git directory or a bare
# repository, so BOTH are required: the command must succeed and its answer must be exactly `true`.
answer="$(git -C "$target" rev-parse --is-inside-work-tree 2>/dev/null)" || answer=""
if [ "$answer" != "true" ]; then
  echo "REFUSE: guard target is not a git work tree: $target"
  exit 2
fi
# the protected paths are ROOT-relative, so the probes run at the work tree's top level even when the
# target names a subdirectory of it
top="$(git -C "$target" rev-parse --show-toplevel 2>/dev/null)" || top=""
if [ -z "$top" ] || ! cd "$top"; then
  echo "REFUSE: cannot enter the work tree top level of: $target"
  exit 2
fi

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
