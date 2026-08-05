---
name: audit
description: "Ask Claude Code for a structured audit of files or a directory — read-only, with findings by dimension and severity. Mini depth covers 5 dimensions, full depth 9. Reporting only; the audit-fix skill owns the fix cycle."
---

# Audit

Claude inspects the scope with fresh eyes and returns a findings table. Nothing gets fixed
here — that is the `audit-fix` cycle's job.

## When to Use

- A feature just landed and deserves an independent quality pass
- Before a commit or pull request
- The user says "have Claude audit this"
- As the opening step of a manual fix cycle

## Arguments

| Argument | Default | Effect |
|----------|---------|--------|
| `--full` | off | 9-dimension audit (adds security, performance, compliance, deps, docs) |
| `--mini` | on | 5-dimension audit (logic, duplication, dead code, refactoring, shortcuts) |
| file/dir path | cwd | Scope — files or a directory |

## Call Pattern

### Step 1 — run the audit

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Audit the code below and report every issue with its exact file:line.

    SCOPE: {files or directory}

    {WITH --mini, or by default}
    Audit dimensions (5):
    1. Logic errors — wrong conditions, off-by-one, unhandled edge cases, races
    2. Code duplication — copy-paste and near-duplicates that belong extracted
    3. Dead code — unreachable branches, unused variables/imports/exports, stale flags
    4. Refactoring opportunities — overgrown functions, poor names, leaky abstractions
    5. Shortcuts and tech debt — TODO/FIXME/HACK, hardcoded values, missing validation

    {WITH --full}
    Audit dimensions (9): the five above, plus
    6. Security — injection, auth bypass, data exposure, missing validation, weak defaults
    7. Performance — N+1 queries, quadratic loops, blocking I/O, needless allocation
    8. Compliance and documentation — missing error handling, undocumented public APIs, licenses
    9. Dependencies — outdated, unnecessary, or known-vulnerable packages

    Report each finding as:
    - file:line
    - Severity: Critical / High / Medium / Low
    - Dimension
    - Issue, in one sentence
    - Fix, in one sentence

    State it explicitly when a file is clean on every dimension.

    PROVENANCE NOTE: the code was produced by the delegating Codex agent. Audit it with
    full rigor and independent judgment on every finding.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Keep the returned `session_id` as `{audit_session_id}`.

### Step 2 — expand a finding (optional)

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {audit_session_id}
  prompt: "Finding #N — the exact mechanism and the minimal fix."
```

## Output Format

| File:Line | Severity | Dimension | Issue | Fix |
|-----------|----------|-----------|-------|-----|

**Summary**: Critical: N | High: N | Medium: N | Low: N | Total: N

A clean scope reports CLEAN, naming what was audited.

## Notes

- `permissionMode: plan` — the audit reads, never writes
- Hand `{audit_session_id}` to the `verify` skill after fixes land, so Claude keeps its context
- For whole projects, pass the top-level source directory rather than single files
