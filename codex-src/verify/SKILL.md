---
name: verify
description: "Ask Claude Code whether previously reported findings are actually fixed. Continues the prior audit session when its id is available, and renders FIXED / NOT FIXED / PARTIAL / REGRESSED per issue with evidence."
---

# Verify

Claims meet code: for every finding on the list, Claude re-reads the cited location and rules
one of four ways — FIXED, NOT FIXED, PARTIAL, or REGRESSED — with reasons wherever the ruling
isn't clean.

## Inputs

| Argument | Effect |
|----------|--------|
| `session_id` | prior `audit` session — brings the full audit memory along |
| issue list | the findings under verification, as file:line + description |

## When to Use

- Fixes from an `audit` just landed and need adjudication
- A hand-made fix should be confirmed at its exact location
- Closing out an `audit-fix` cycle

## Option A — continue the audit session (the strong path)

When `{audit_session_id}` survives from the audit or cycle:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {audit_session_id}
  prompt: |
    The findings below have been addressed — rule on each.

    ISSUES TO VERIFY:
    {"file:line | severity | issue description" per line}

    One ruling each: FIXED (fully resolved, nothing new broken) · NOT FIXED (still
    there — say why) · PARTIAL (some of it remains — say what) · REGRESSED (the fix
    broke something else — describe it).

    Rule only after re-reading the file at each cited location.
```

## Option B — fresh session

No surviving session? Start clean, read-only:

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Rule on whether these issues are fixed.

    ISSUES TO VERIFY:
    {"file:line | severity | issue description" per line}

    Per issue: read the cited file, then rule FIXED / NOT FIXED / PARTIAL /
    REGRESSED, explaining every ruling that isn't FIXED. Cosmetic edits that bury
    the underlying problem do not count as fixes.

    PROVENANCE NOTE: code and fixes both come from a Codex agent — adjudicate with
    fresh eyes, deferring to neither.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Hold the returned session id as `{verify_session_id}`.

## Output Format

| File:Line | Severity | Issue | Verdict | Notes |
|-----------|----------|-------|---------|-------|

**Result**: N fixed, N not fixed, N partial, N regressed

## Afterwards

All FIXED clears the way to commit. Anything NOT FIXED or REGRESSED routes back into
`audit-fix` or a manual pass — with Option A preferred next time too, because retained audit
context is what makes the rulings precise.
