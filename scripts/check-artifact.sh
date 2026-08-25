#!/bin/bash
# SPDX-License-Identifier: ISC
# PostToolUse hook: detect NL artifact edits and remind to score. Fail-open — if
# anything goes wrong, emit nothing and exit 0. Never blocks (F9.7).
set +e

input=$(cat 2>/dev/null)

# Extract file_path from the JSON on stdin. jq when available, else a lexical
# grep/sed fallback. Every process is silenced: a diagnostic on stderr would be
# indistinguishable from the advisory line this hook exists to emit.
if command -v jq &>/dev/null; then
  file_path=$(echo "$input" | jq -r '.tool_input.file_path // .toolInput.file_path // empty' 2>/dev/null)
else
  file_path=$(echo "$input" \
    | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' 2>/dev/null \
    | head -1 2>/dev/null \
    | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//' 2>/dev/null)
fi

if [ -z "$file_path" ]; then
  exit 0
fi

# In shell case-pattern matching `*` matches `/` (unlike pathname expansion), so
# `*/commands/*.md` already matches `foo/commands/bar.md` AND
# `foo/commands/sub/bar.md` — the `*/commands/**/*.md` alternatives (and the
# equivalents for skills/ and rules/) were unreachable and are not written.
is_artifact=false
case "$file_path" in
  */commands/*.md) is_artifact=true ;;
  */agents/*.md) is_artifact=true ;;
  */skills/*/SKILL.md) is_artifact=true ;;
  */.claude/rules/*.md) is_artifact=true ;;
  */hooks/*.json) is_artifact=true ;;
  */CLAUDE.md) is_artifact=true ;;
  */.claude-plugin/plugin.json) is_artifact=true ;;
  */.mcp.json) is_artifact=true ;;
esac

if [ "$is_artifact" = true ]; then
  # Parameter expansion rather than basename: no external process means no
  # failure branch, and no path reaching here can end in `/` (a trailing slash
  # satisfies none of the patterns above).
  base="${file_path##*/}"
  echo "NL artifact edited: ${base}. Run /vibe-suite:score ${file_path} to check quality." >&2
  # vibe-203 (observability): a non-2, non-zero exit makes the harness SHOW this stderr line to the
  # operator (exit 0 would keep it transcript-only). It is advisory, never blocking — only exit 2
  # blocks a PostToolUse; 1 does not. A JSON systemMessage was rejected: encoding a user-controlled
  # file_path safely needs jq/python, which the hook must not depend on.
  exit 1
fi

exit 0
