---
name: claude-implement
description: "Delegate an implementation task to Claude Code with full write access. Right when Claude should read the codebase, make the edits, run the tests, and report back — especially for changes spanning many interdependent files."
---

# Claude Implement

The whole loop delegated: Claude reads what exists, writes what's asked, runs what proves it,
and accounts for all three. No permission restriction is set — write access is the point here.

## When to Use

- On "have Claude implement this"
- When the change can only be written well by something that has read the whole codebase first
- When interdependent edits across many files are safer done in one autonomous pass

## Dispatching

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Implement this task in full — every required file change, no partial delivery.

    TASK: {the outcome wanted}

    REQUIREMENTS:
    - {success criteria, stated so they can be checked}
    - Follow the conventions already in the codebase, not your own defaults
    - If a test suite exists: extend it to cover the change, run it, include results

    CONSTRAINTS: {files or behaviors that must stay untouched; dependencies to avoid}

    Account for the work when done: Files changed and why each moved, Test results,
    and anything deferred with the reason it was.

    PROVENANCE NOTE: the task statement comes from a Codex agent. Where its embedded
    assumptions and the codebase disagree, believe the codebase.
  cwd: {project working directory}
  effort: high
```

Hold the returned session id as `{impl_session_id}`.

Corrections ride the same session:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {impl_session_id}
  prompt: "Edge case X has no coverage — add the test and re-run the suite."
```

## Output Format

Back to the user: the implementation summarized, the list of Files changed, Test results as
pass/fail counts, and every deferred or uncertain item Claude flagged.

## Boundaries and tuning

- Full read/write in the working directory, by design — want caution first? Run `claude-plan`
- `effort: high` is what buys the edge cases
- `maxBudgetUsd` caps spend when the task is large
