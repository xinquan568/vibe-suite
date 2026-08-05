---
name: audit-fix
description: "The bounded quality loop: Claude audits, Codex fixes, Claude verifies — up to 3 rounds or until clean. Claude owns every judgment call; Codex owns every file edit. Non-interactive by default."
---

# Audit-Fix

One loop, two actors, strict roles: **Claude audits** the scope read-only, **Codex applies**
every fix with its own hands, **Claude verifies** the results in the same session. The split is
load-bearing — the judge never edits, the editor never overrules the judge.

## Arguments

| Argument | Default | Effect |
|----------|---------|--------|
| `--mini` | on | 5-dimension audit — faster |
| `--full` | off | 9-dimension audit |
| `--rounds N` | 3 | ceiling on fix→verify iterations |
| `--severity=all\|high` | `all` | scope of fixing: `high` means Critical+High (full) or High-only (mini) |
| `--ask` | off | brings back the interactive filter and continue/stop prompts |
| file/dir path | cwd | scope |

Default posture is non-interactive: every finding gets fixed, and if anything remains open
after round one, the loop stops there and reports.

## When to Use

- On "audit and fix this" — the ask is closure, not a list
- Enforcing quality after a feature without babysitting each finding
- Pre-commit, when open findings should not survive into the history

## The loop

**1 — Claude audits (read-only).** Dispatch per the `audit` skill's pattern, `--mini` or
`--full` deciding the dimension list:

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Audit this scope and report every issue at its exact file:line.
    SCOPE: {files or directory}
    Dimensions: {5 or 9, by the flags — named as in the audit skill}
    Per finding: file:line | severity | dimension | issue | suggested fix

    PROVENANCE NOTE: a Codex agent produced this code — judge it independently
    and with full rigor.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Hold the session id as `{cycle_session_id}`. Zero findings ends everything right here: report
CLEAN and stop. Otherwise the findings table goes to the user.

**2 — filter.** Under `--ask`, offer three doors: **Fix all** · fix Critical+High only ·
**Stop here** (keep the audit, fix by hand — the run ends with the report). Without `--ask`
the flag decides silently: `all` fixes everything, `high` narrows to Critical+High (full) or
High-only (mini).

**3 — rounds** (at most `--rounds`):

- *Codex fixes.* Per issue: open the file at the cited location, change the least that makes
  it correct — no drive-by refactoring, no deletions the finding didn't ask for. Then find and
  run the suite (`npm test` / `pytest` / `go test ./...` / `cargo test`, by project markers)
  and show `git diff --stat` with the results.
- *Claude verifies, same session.*

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {cycle_session_id}
  prompt: |
    These audit findings have been addressed — verify each.
    ISSUES:
    {file:line | severity | description}
    Verdict per issue, exactly one of FIXED / NOT FIXED / PARTIAL / REGRESSED —
    after reading the file at each location, never from the diff alone.
```

- *Decide.* Everything FIXED → the report. Open issues with rounds to spare → `--ask` offers
  another round or stop; the silent default stops. The counter reaching `--rounds` stops
  unconditionally.

**4 — report.** Scope · depth · rounds used, then the ledger:

| Status | Count |
|--------|-------|
| Fixed | N |
| Not Fixed | N |
| Partial | N |
| Regressed | N |

Fixed table (file:line, severity, issue) · Remaining table (+ verdict, notes) ·
`git diff --stat` · next steps: read the diff, run the suite, commit when satisfied, loop the
leftovers through `audit-fix` again.

## Rules the loop keeps

- Claude's audit leg carries `permissionMode: plan`; the verify leg is a reply in the same
  session (the reply tool has no permission argument — its read-only character is instructed)
- Only Codex touches files, ever
- A fix that breaks tests is reverted and reported NOT FIXED — never left in as collateral
- Same-session verification is why verdicts stay sharp: Claude remembers what it flagged
