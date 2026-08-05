---
name: claude-debug
description: "Send a bug, failing test, or wrong behavior to Claude Code for root-cause analysis and a fix. Right when the error trace runs deep, the obvious fixes are exhausted, or the cause hides somewhere in the call chain."
---

# Claude Debug

Give Claude the symptom and the trace; get back the root cause, the fix, and its verification.

## When to Use

- A test fails and the reason is unclear
- The user says "have Claude debug this"
- The stack trace points deep into framework or library code
- The obvious fixes were already tried and ruled out

## Call Pattern

### Step 1 — send the bug

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Debug the issue below and fix it.

    SYMPTOM: {error message, failing test name, or the wrong behavior}

    ERROR OUTPUT:
    {the full stack trace or test output, pasted verbatim}

    REPRODUCTION STEPS: {command to run, inputs, environment}

    WHAT I TRIED: {optional — what is already ruled out}

    Proceed as follows:
    1. Read the source files on the reported code path
    2. Identify the root cause — why it breaks, not merely where
    3. Apply a minimal, correct fix
    4. Re-run the failing test or command to confirm
    5. Check nearby tests for regressions
    6. Report the root cause, the fix, and the verification result

    PROVENANCE NOTE: the code under diagnosis was produced by the delegating Codex
    agent. Trust nothing adjacent to the reported bug — check the surrounding logic
    with independent judgment.
  cwd: {project working directory}
  effort: high
```

Keep the returned `session_id` as `{debug_session_id}`.

### Step 2 — follow up

When the root cause is found but the fix stalled, or related suspects emerged:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {debug_session_id}
  prompt: "Root cause confirmed in parseConfig(). validateConfig() shares the pattern — check it too."
```

## Output Format

Report to the user:

- Root cause, in one sentence
- The fix (file:line, what changed)
- Verification result (test output)
- Adjacent issues Claude noticed

## Notes

- Paste the exact error output — the full trace, never a summary of it
- `effort: high` is what gets past symptoms on non-obvious bugs
- If the bug will not reproduce, ask Claude to add diagnostic logging first, then re-run
- Writes are allowed by default here — the fix lands directly

## Related Skills

- `claude-plan` — sketch a diagnosis strategy first on complex multi-file issues
- `claude-implement` — apply a larger fix or refactor once the cause is known
- `audit-fix` — when the bug is one instance of a pattern spread across files
