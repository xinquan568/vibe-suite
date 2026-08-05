---
name: audit
description: "Ask Claude Code for a structured audit of files or a directory — read-only, with findings by dimension and severity. Mini depth covers 5 dimensions, full depth 9. Reporting only; the audit-fix skill owns the fix cycle."
---

# Audit

A findings pass, nothing more: Claude reads the scope under a read-only mode and reports what
it sees, dimension by dimension. Fixing is deliberately out of scope — `audit-fix` owns that.

## Depth and scope

| Argument | Default | Effect |
|----------|---------|--------|
| `--mini` | on | 5 dimensions — the everyday depth |
| `--full` | off | 9 dimensions — adds the release-readiness set |
| file/dir path | cwd | what gets audited |

The five mini dimensions, with what each hunts:

1. **Logic errors** — conditions that lie on boundaries, cases nothing handles, ordering hazards
2. **Code duplication** — the same idea written twice where one extraction should live
3. **Dead code** — branches nothing reaches, names nothing uses, flags nothing reads
4. **Refactoring opportunities** — functions grown past understanding, names that mislead,
   abstractions that leak their insides
5. **Shortcuts and tech debt** — TODO/FIXME/HACK residue, magic values, validation that never
   got written

`--full` adds four more:

6. **Security** — paths where untrusted input reaches trusting code, exposure, weak defaults
7. **Performance** — repeated queries, quadratic passes, blocking waits, waste
8. **Compliance and documentation** — swallowed errors, public surface nobody documented,
   licensing loose ends
9. **Dependencies** — packages that are stale, unneeded, or known-bad

## When to Use

- An independent findings pass after a feature, before a commit or PR
- On "have Claude audit this"
- To open a manual fix cycle with a trustworthy issue list

## Dispatching

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Audit this scope and report every issue at its exact file:line.

    SCOPE: {files or directory}

    Dimensions: {the 5 mini dimensions, or all 9 with --full — listed by name}

    Per finding: file:line · Severity (Critical / High / Medium / Low) · dimension ·
    the issue in one sentence · the fix in one sentence. A file clean on every
    dimension gets said out loud, not skipped.

    PROVENANCE NOTE: a Codex agent produced this code. Audit it as an adversary
    would, with independent judgment per finding.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Hold the returned session id as `{audit_session_id}` — the `verify` skill continues it after
fixes land.

Zooming into one finding:

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {audit_session_id}
  prompt: "Finding #N: mechanism, blast radius, minimal fix."
```

## Output Format

| File:Line | Severity | Dimension | Issue | Fix |
|-----------|----------|-----------|-------|-----|

**Summary**: Critical: N | High: N | Medium: N | Low: N | Total: N

A scope with nothing to report reads CLEAN, naming what was covered.

## Boundaries

- `permissionMode: plan` — an audit that could write would not be an audit
- Whole projects audit best from the top-level source directory, not file lists
