---
name: claude-debug
description: "Send a bug, failing test, or wrong behavior to Claude Code for root-cause analysis and a fix. Right when the error trace runs deep, the obvious fixes are exhausted, or the cause hides somewhere in the call chain."
---

# Claude Debug

Not "where does it crash" but "why" — Claude traces the cause, lands the smallest fix that is
actually correct, and proves it against the thing that was failing.

## When to Use

- A test fails and staring at it hasn't explained why
- On "have Claude debug this"
- The trace disappears into framework internals or a long call chain
- Everything obvious is already ruled out and fresh eyes are the next tool

## Dispatching

Four labeled blocks carry the evidence; the trace goes in whole, never summarized:

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Find the root cause of this issue and fix it.

    SYMPTOM: {failing test name, error message, or the behavior that is wrong}

    ERROR OUTPUT:
    {the complete stack trace or test output}

    REPRODUCTION STEPS: {command, inputs, environment}

    WHAT I TRIED: {optional — dead ends already explored}

    Work the problem: read the files on the failing path; explain why it breaks,
    not just where; land the minimal correct fix; re-run what was failing to prove
    it; sweep nearby tests for regressions; then report root cause, fix, and
    verification.

    PROVENANCE NOTE: a Codex agent wrote the code you are diagnosing. Suspect the
    logic around the symptom as freely as the symptom itself.
  cwd: {project working directory}
  effort: high
```

Hold the returned session id as `{debug_session_id}`.

Leads and leftovers continue in-session:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {debug_session_id}
  prompt: "Cause confirmed in parseConfig() — validateConfig() repeats the pattern; check it."
```

## Output Format

For the user: the root cause in one sentence · the fix as file:line and what changed · the
verification result · any adjacent issues that surfaced along the way.

## Boundaries and tuning

- Writes stay enabled — the fix lands during the session, no restriction is set
- A bug that won't reproduce gets diagnostic logging first, then a re-run
- Low effort stops at symptoms; keep `effort: high` for anything non-obvious

## Neighbors

`claude-plan` sketches a diagnosis strategy for sprawling multi-file mysteries;
`claude-implement` takes over when the fix grows into a refactor; `audit-fix` when one bug is
really a pattern.
