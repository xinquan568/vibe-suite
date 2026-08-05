---
name: audit-fix
description: "The bounded quality loop: Claude audits, Codex fixes, Claude verifies — up to 3 rounds or until clean. Claude owns every judgment call; Codex owns every file edit. Non-interactive by default."
---

# Audit-Fix

Claude audits. Codex fixes. Claude verifies. Repeat until clean or the bound is reached.

The division of labor is the point: Claude supplies independent analysis and verification;
Codex applies targeted fixes without relitigating the findings.

## When to Use

- The user says "audit and fix this" — findings resolved, not just listed
- Automated quality enforcement after a feature lands
- Before a commit, when open findings should not survive

## Arguments

| Argument | Default | Effect |
|----------|---------|--------|
| `--full` | off | 9-dimension audit |
| `--mini` | on | 5-dimension audit (faster) |
| `--rounds N` | 3 | Maximum fix→verify iterations |
| `--severity=all\|high` | `all` | Which findings to fix: Critical+High (full) or High-only (mini) under `high` |
| `--ask` | off | Restore the interactive severity filter and continue/stop prompts |
| file/dir path | cwd | Scope |

Without `--ask` the loop runs non-interactively: every finding gets fixed, and the loop stops
after the first round if issues remain open.

## Workflow

### Step 1 — Claude audits

Dispatch the audit exactly as the `audit` skill does (5 or 9 dimensions by the flags):

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Audit the code below and report every issue with its exact file:line.

    SCOPE: {files or directory}

    {the 5- or 9-dimension list, exactly as in the audit skill}

    Each finding: file:line | severity | dimension | issue | suggested fix

    PROVENANCE NOTE: code produced by the delegating Codex agent — audit with full
    rigor and independent judgment.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Keep `session_id` as `{cycle_session_id}`.

No findings → report CLEAN and stop. Otherwise show the findings table.

### Step 2 — severity filter

With `--ask`: offer **Fix all** / Fix Critical+High only / **Stop here** (keep the audit, fix
manually — stops with the final report). Without it, apply the flag silently:
`--severity=all` fixes everything; `--severity=high` filters to Critical+High (full) or
High-only (mini).

### Step 3 — the loop (at most `--rounds` iterations)

**3a — Codex fixes.** For each remaining issue: read the file at the reported location and
apply the minimal correct fix — nothing beyond the reported location and its directly related
code, no opportunistic refactoring, no deletions the issue does not call for. Then detect and
run the project's test suite (`package.json` test script → `npm test` · `pytest.ini`/
`conftest.py` → `pytest` · `go.mod` → `go test ./...` · `Cargo.toml` → `cargo test`) and show
`git diff --stat` plus the test results.

**3b — Claude verifies, same session.**

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {cycle_session_id}
  prompt: |
    These issues from your audit have been addressed. Verify each one.

    ISSUES:
    {file:line | severity | description, one per line}

    For each, answer exactly one of: FIXED / NOT FIXED / PARTIAL / REGRESSED.
    Read the files at the reported locations first — never assume a fix from its diff.
```

**3c — evaluate.** All FIXED → final report. Issues remain and rounds are left: with `--ask`,
show them and ask fix-again-or-stop; without it, stop with the partial state. The round
counter hitting `--rounds` always ends the loop.

### Step 4 — final report

Scope, depth (mini/full), round count, then:

| Status | Count |
|--------|-------|
| Fixed | N |
| Not Fixed | N |
| Partial | N |
| Regressed | N |

A **Fixed** table (file:line, severity, issue), a **Remaining** table (adding verdict + notes),
the `git diff --stat`, and next steps: review the diff, run the tests, commit if satisfied,
re-run `audit-fix` on remaining files otherwise.

## Notes

- Claude's audit runs under `permissionMode: plan`; only Codex ever writes files
- Reusing `{cycle_session_id}` for verification keeps Claude's full audit context — verdicts
  come back sharper than from a fresh session
- A fix that breaks tests gets reverted and reported NOT FIXED, never left in
