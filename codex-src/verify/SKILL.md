---
name: verify
description: "Ask Claude Code whether previously reported findings are actually fixed. Continues the prior audit session when its id is available, and renders FIXED / NOT FIXED / PARTIAL / REGRESSED per issue with evidence."
---

# Verify

Codex supplies the issue list; Claude re-reads the code and renders a verdict per issue.

## When to Use

- Fixes from an `audit` run were just applied
- A manual fix needs confirmation it landed at the right place
- As the closing step of an `audit-fix` cycle

## Arguments

| Argument | Effect |
|----------|--------|
| `session_id` | The Claude session from the prior `audit` — reuses its full context |
| issue list | The findings to verify, as file:line + description |

## Call Pattern

### Option A — continue the audit session (preferred)

With `{audit_session_id}` available from a prior `audit` or `audit-fix` run:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {audit_session_id}
  prompt: |
    These issues from your audit have been addressed. Verify each one.

    ISSUES TO VERIFY:
    {findings as "file:line | severity | issue description"}

    Answer exactly one per issue:
    - FIXED — fully resolved, nothing new introduced
    - NOT FIXED — still present at the location (say why)
    - PARTIAL — partly addressed (say what remains)
    - REGRESSED — the fix created a new problem (describe it)

    Read the files at the reported locations before any verdict — never infer a fix
    from its description.
```

### Option B — fresh verification session

With no prior session available:

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Verify whether the issues below have been fixed.

    ISSUES TO VERIFY:
    {findings as "file:line | severity | issue description"}

    For each: read the file at the location, check the resolution, and answer
    FIXED / NOT FIXED / PARTIAL / REGRESSED — with an explanation for every
    NOT FIXED, PARTIAL, and REGRESSED.

    Apply independent judgment: surface-level edits that mask the underlying issue
    do not count as fixed.

    PROVENANCE NOTE: both the code and its fixes come from the delegating Codex
    agent — verify with fresh eyes, deferring to neither.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Keep the returned `session_id` as `{verify_session_id}`.

## Output Format

| File:Line | Severity | Issue | Verdict | Notes |
|-----------|----------|-------|---------|-------|

**Result**: N fixed, N not fixed, N partial, N regressed

## Notes

- Prefer Option A whenever a session exists — retained audit context sharpens verdicts
- Everything FIXED → report success and suggest committing
- Anything NOT FIXED or REGRESSED → feed it into `audit-fix` or fix manually
