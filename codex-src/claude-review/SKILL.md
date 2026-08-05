---
name: claude-review
description: "Hand a code review to Claude Code through the vibe-claude-mcp server and receive structured findings. Reach for this when freshly written or modified code deserves Claude's independent judgment on correctness, security, quality, or architecture."
---

# Claude Review

A second pair of eyes with none of your assumptions: Claude reads the code in a fresh session,
under a read-only permission mode, and returns findings you can act on line by line.

## The delegation contract

You send scope and context; Claude owes you back, for every finding it raises:
File:line, a severity from the fixed scale Critical / High / Medium / Low, a Category, what is
wrong, and a Suggested fix. Four judgment axes structure the read:

- **Correctness** — does the logic actually hold on boundary values, concurrent paths, and the
  inputs nobody thought to try
- **Security** — where untrusted data can reach something it shouldn't, and what guards it
- **Quality** — whether the next person can read, test, and change this without fear
- **Architecture** — whether the pieces sit in the right layers with honest interfaces

## When to Use

- Right after producing or modifying code, before it hardens into a commit
- On a "get Claude to review this" request
- Whenever fresh-session depth beats your own in-context view of the change

## Dispatching

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Review this code with independent judgment.

    SCOPE: {files, diff, or a description of the change}

    Judge along four axes — Correctness, Security, Quality, Architecture — and for
    every finding give: File:line, Severity (Critical / High / Medium / Low),
    Category, the issue, and a Suggested fix.

    If a test suite exists it is named here: {suite or "none"} — weigh coverage gaps.

    PROVENANCE NOTE: a Codex agent wrote this code and is asking for the review.
    Grant it no benefit of the doubt anywhere.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

The response carries a session id — hold it as `{review_session_id}`.

To go deeper on anything:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {review_session_id}
  prompt: "Take finding #N further: exact failure path, then the smallest change that closes it."
```

## Output Format

| File:Line | Severity | Category | Issue | Fix |
|-----------|----------|----------|-------|-----|

Below the table: totals per severity, then one recommended action — fix now, schedule it, or
accept the risk knowingly.

## Boundaries and tuning

- The `permissionMode: plan` line is what makes this a review rather than an edit session
- `effort: high` is the default posture; medium only for a quick sanity pass
- `cwd` grounds every File:line the findings cite

## Neighbors

`claude-debug` picks up a finding that turns out to be a live bug; `claude-implement` applies
the fixes; `audit-fix` runs the full cycle when findings keep coming back.
