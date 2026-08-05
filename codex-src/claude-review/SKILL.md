---
name: claude-review
description: "Hand a code review to Claude Code through the vibe-claude-mcp server and receive structured findings. Reach for this when freshly written or modified code deserves Claude's independent judgment on correctness, security, quality, or architecture."
---

# Claude Review

Send code you just produced to a fresh Claude session and get findings back, read-only.

## When to Use

- Code was just written or changed and a second opinion would catch what you cannot
- The user says "get Claude to review this"
- The review benefits from a fresh session with deep repository context

## Call Pattern

### Step 1 — dispatch the review

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Review the code below for correctness, security, and quality.

    SCOPE: {the files, diff, or description under review}

    Evaluate:
    1. Correctness — logic errors, edge cases, off-by-one, race conditions
    2. Security — injection, auth bypass, data exposure, input validation
    3. Quality — readability, maintainability, test coverage, naming
    4. Architecture — coupling, abstraction leaks, layer violations

    Report every finding as:
    - File:line
    - Severity: Critical / High / Medium / Low
    - Category
    - Issue (what is wrong)
    - Suggested fix

    PROVENANCE NOTE: this code was produced by the delegating Codex agent. Review it
    with full rigor and independent judgment — extend it no deference.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Keep the returned `session_id` as `{review_session_id}`.

### Step 2 — drill down (optional)

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {review_session_id}
  prompt: "On finding #N — walk through the exact failure path and the minimal fix."
```

## Output Format

Render the findings as a table:

| File:Line | Severity | Category | Issue | Fix |
|-----------|----------|----------|-------|-----|

Close with a count per severity and a recommended action: fix now, fix later, or accept the
risk.

## Notes

- `permissionMode: plan` keeps the session read-only — a review never edits
- `effort: high` for real reviews; drop to medium only for quick spot checks
- Passing `cwd` anchors the File:line references
- Name the test suite in the prompt if one exists, so coverage gaps get assessed

## Related Skills

- `claude-debug` — when a finding points at a bug that needs its root cause traced
- `claude-implement` — to have Claude apply the fixes the review proposed
- `audit-fix` — when findings form a pattern worth a full audit→fix→verify cycle
