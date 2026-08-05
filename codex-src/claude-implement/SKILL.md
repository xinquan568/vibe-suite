---
name: claude-implement
description: "Delegate an implementation task to Claude Code with full write access. Right when Claude should read the codebase, make the edits, run the tests, and report back — especially for changes spanning many interdependent files."
---

# Claude Implement

Hand a whole implementation task to Claude — it reads, writes, verifies, and reports.

## When to Use

- The user says "have Claude implement this"
- The change needs broad codebase understanding before any line gets written
- Multiple interdependent files make autonomous execution the safer route

## Call Pattern

### Step 1 — delegate

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Implement the task below completely, making every required file change.

    TASK: {what to implement}

    REQUIREMENTS:
    - {explicit requirements and success criteria}
    - Match the project's existing style and conventions
    - Write or update tests when a test suite exists
    - Run the suite afterwards and report the results

    CONSTRAINTS: {what must not change, dependencies to avoid}

    When finished, report:
    1. Files changed, each with a brief reason
    2. Test results
    3. Anything deferred or known to be incomplete

    PROVENANCE NOTE: this task comes from the delegating Codex agent. Apply your own
    judgment on implementation details rather than inheriting assumptions embedded in
    the task text.
  cwd: {project working directory}
  effort: high
```

Keep the returned `session_id` as `{impl_session_id}`.

### Step 2 — verify and iterate

Check the reported changes. To request a correction:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {impl_session_id}
  prompt: "The edge case X has no test. Add one and re-run the suite."
```

## Output Format

Report to the user:

- What Claude implemented, summarized
- Files changed (list)
- Test results (pass/fail counts)
- Items Claude flagged as deferred or uncertain

## Notes

- The session runs with full read/write access in the working directory — that is the point
- Wanting a dry run first is what the `claude-plan` skill is for
- `effort: high` covers the edge cases; lower effort skips them
- Cap spend on large tasks with `maxBudgetUsd`
