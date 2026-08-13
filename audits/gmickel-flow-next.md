# NLPM Audit: gmickel/flow-next
**Date**: 2026-04-16  |  **Artifacts**: 87  |  **Strategy**: progressive
**NL Score**: 93/100
**Security**: BLOCKED
**Bugs**: 2  |  **Quality Issues**: 18  |  **Security Findings**: 6

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/flow/.claude-plugin/plugin.json | manifest | 80 | JSON manifest, not an NL artifact |
| plugins/flow-next/.claude-plugin/plugin.json | manifest | 80 | JSON manifest, not an NL artifact |
| plugins/flow-next/hooks/hooks.json | hook config | 88 | No NL frontmatter (JSON config) |
| plugins/flow/agents/practice-scout.md | agent | 88 | Stale year ("2025") in rules; single output example |
| plugins/flow/agents/repo-scout.md | agent | 90 | Single output format example; no confidence tags |
| plugins/flow/agents/docs-scout.md | agent | 90 | Single output format example |
| plugins/flow/agents/quality-auditor.md | agent | 90 | Single output format example |
| plugins/flow/agents/flow-gap-analyst.md | agent | 90 | Single output format example |
| plugins/flow-next/agents/epic-scout.md | agent | 90 | Rules say "Use haiku" but model declared as sonnet |
| flow-next-tui/.claude/CLAUDE.md | docs | 90 | Documentation, not NL artifact |
| flow-next-tui/CLAUDE.md | docs | 90 | Documentation, not NL artifact |
| CLAUDE.md | docs | 90 | Documentation, not NL artifact |
| plugins/flow/agents/context-scout.md | agent | 93 | Lacks confidence tags feature from flow-next version |
| plugins/flow-next/codex/skills/flow-next-worktree-kit/SKILL.md | skill | 95 | Single output example (commands list) |
| plugins/flow-next/skills/flow-next-worktree-kit/SKILL.md | skill | 95 | Single output example (commands list) |
| plugins/flow-next/codex/skills/flow-next-setup/SKILL.md | skill | 95 | Brief content, single output example |
| plugins/flow-next/skills/flow-next-setup/SKILL.md | skill | 95 | Brief content, single output example |
| plugins/flow/skills/worktree-kit/SKILL.md | skill | 95 | Single output example |
| plugins/flow-next/commands/flow-next/work.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/plan.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/plan-review.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/epic-review.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/uninstall.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/setup.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/prime.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/impl-review.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/interview.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/ralph-init.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/commands/flow-next/sync.md | command | 95 | Missing allowed-tools |
| plugins/flow/commands/flow/work.md | command | 95 | Missing allowed-tools |
| plugins/flow/commands/flow/plan.md | command | 95 | Missing allowed-tools |
| plugins/flow/commands/flow/plan-review.md | command | 95 | Missing allowed-tools |
| plugins/flow/commands/flow/impl-review.md | command | 95 | Missing allowed-tools |
| plugins/flow/commands/flow/interview.md | command | 95 | Missing allowed-tools |
| plugins/flow-next/agents/repo-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/security-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/practice-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/docs-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/quality-auditor.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/flow-gap-analyst.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/testing-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/claude-md-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/env-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/tooling-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/workflow-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/build-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/agents/observability-scout.md | agent | 95 | Single output format example |
| plugins/flow-next/codex/skills/flow-next/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-work/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-ralph-init/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-prime/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-interview/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-plan/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-rp-explorer/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-sync/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-export-context/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-impl-review/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-epic-review/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-plan-review/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/flow-next-deps/SKILL.md | skill | 100 | None |
| plugins/flow-next/codex/skills/browser/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-work/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-ralph-init/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-prime/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-interview/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-plan/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-rp-explorer/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-sync/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-export-context/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-impl-review/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-epic-review/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-plan-review/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/flow-next-deps/SKILL.md | skill | 100 | None |
| plugins/flow-next/skills/browser/SKILL.md | skill | 100 | None |
| plugins/flow/skills/flow-plan/SKILL.md | skill | 100 | None |
| plugins/flow/skills/flow-work/SKILL.md | skill | 100 | None |
| plugins/flow/skills/flow-impl-review/SKILL.md | skill | 100 | None |
| plugins/flow/skills/flow-interview/SKILL.md | skill | 100 | None |
| plugins/flow/skills/rp-explorer/SKILL.md | skill | 100 | None |
| plugins/flow/skills/flow-plan-review/SKILL.md | skill | 100 | None |
| plugins/flow-next/agents/context-scout.md | agent | 100 | None — complete example section |
| plugins/flow-next/agents/plan-sync.md | agent | 100 | None — two output format examples |
| plugins/flow-next/agents/memory-scout.md | agent | 100 | None — two output format variants |
| plugins/flow-next/agents/docs-gap-scout.md | agent | 100 | None — two output format variants |
| plugins/flow-next/agents/github-scout.md | agent | 100 | None — output format + common patterns |
| plugins/flow-next/agents/worker.md | agent | 100 | None — phased workflow with examples |

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 0 |
| Medium | 4 |
| Low | 2 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks (hooks.json) | plugins/flow-next/hooks/hooks.json |
| Shell scripts | plugins/flow-next/scripts/ci_test.sh, smoke_test.sh, ralph_smoke_test.sh, ralph_e2e_test.sh, ralph_smoke_rp.sh, ralph_e2e_rp_test.sh, ralph_e2e_short_rp_test.sh, plan_review_prompt_smoke.sh |
| Shell scripts (hooks) | plugins/flow-next/scripts/hooks/ralph-guard.sh, ralph-receipt-guard.sh, ralph-verbose-log.sh |
| Python scripts | plugins/flow-next/scripts/flowctl.py, plugins/flow-next/scripts/hooks/ralph-guard.py |
| Shell wrapper | plugins/flow-next/scripts/flowctl |
| Template scripts | plugins/flow-next/skills/flow-next-ralph-init/templates/ralph.sh, ralph_once.sh |
| Codex template scripts | plugins/flow-next/codex/skills/flow-next-ralph-init/templates/ralph.sh, ralph_once.sh |
| Worktree scripts | plugins/flow-next/skills/flow-next-worktree-kit/scripts/worktree.sh, codex/..., flow/skills/worktree-kit/scripts/worktree.sh |
| Repo scripts | scripts/bump.sh, scripts/sync-codex.sh, scripts/install-codex.sh |
| MCP configs | None found |
| Package manifests | None found |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | plugins/flow-next/scripts/ralph_e2e_rp_test.sh | 323 | eval with variables | `eval "$(retry_cmd ... "$FLOWCTL" rp setup-review ... --summary "Smoke preflight")"` — eval of command substitution output in executed test script. $FLOWCTL and $REPO_ROOT are shell variables; any unexpected output from `retry_cmd` or `flowctl` would be directly eval'd. |
| 2 | Critical | plugins/flow-next/scripts/ralph_smoke_rp.sh | 289 | eval with variables | `eval "$(retry_cmd ... "$FLOWCTL" rp setup-review ... --summary "Smoke preflight")"` — same eval pattern in executed smoke-test script. |
| 3 | Medium | plugins/flow-next/skills/flow-next-impl-review/workflow.md | 126 | eval with user-influenced var | `eval "$($FLOWCTL rp setup-review ... --summary "$REVIEW_SUMMARY" --create)"` — $REVIEW_SUMMARY is derived from an epic spec (user-controlled text). If it contains shell metacharacters (e.g., `$(cmd)`), agents executing this instruction could run arbitrary commands. |
| 4 | Medium | plugins/flow-next/skills/flow-next-plan-review/workflow.md | 119 | eval with user-influenced var | Same pattern as #3 with $REVIEW_SUMMARY from user-controlled plan content. |
| 5 | Medium | plugins/flow-next/skills/flow-next-epic-review/workflow.md | 118 | eval with user-influenced var | Same pattern as #3 with $REVIEW_SUMMARY from user-controlled epic spec. |
| 6 | Medium | scripts/install-codex.sh | 30–60 | file writes outside repo | Script copies files to `$HOME/.codex/` (user home directory outside repo). Expected install behavior, but could silently overwrite existing Codex configuration including skills, agents, config.toml, and hooks. |

**Low findings:**

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 7 | Low | plugins/flow-next/scripts/hooks/ralph-guard.py | 452–481 | debug log at /tmp/ | Appends tool command payloads to `/tmp/ralph-guard-debug.log` unconditionally (even when FLOW_RALPH=1). Long-running agents accumulate full command history in /tmp. |
| 8 | Low | plugins/flow-next/scripts/hooks/ralph-verbose-log.sh | 22–50 | full payload capture | When FLOW_RALPH_VERBOSE=1, captures complete tool payloads (including file contents) to a run log. No size limits; could accumulate sensitive data in log files. |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | plugins/flow-next/agents/epic-scout.md | Rules section says "Use haiku model - keep analysis fast and cheap" but frontmatter declares `model: claude-sonnet-4-6`. Contradictory model guidance. | Maintainers and consumers get conflicting information about the intended model tier for this agent. |
| 2 | plugins/flow/agents/practice-scout.md | Line 70: "Current year is 2025 - search for recent guidance" — stale year; project CLAUDE.md documents current year as 2026. | Agents guided by flow/practice-scout may search for 2025 guidance instead of 2026, returning slightly outdated results. |

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | plugins/flow-next/skills/flow-next-impl-review/workflow.md:126 | `eval "$($FLOWCTL ... --summary "$REVIEW_SUMMARY"...)"` — shell injection risk via user-controlled $REVIEW_SUMMARY | Quote-sanitize REVIEW_SUMMARY before passing to eval, or refactor to export variables directly (`W=$(flowctl rp setup-review ...)`) without eval. |
| 2 | plugins/flow-next/skills/flow-next-plan-review/workflow.md:119 | Same eval + $REVIEW_SUMMARY pattern | Same fix as #1 |
| 3 | plugins/flow-next/skills/flow-next-epic-review/workflow.md:118 | Same eval + $REVIEW_SUMMARY pattern | Same fix as #1 |
| 4 | scripts/install-codex.sh | Silently overwrites existing ~/.codex/ config, agents, hooks | Add `--dry-run` flag and a confirmation prompt before overwriting existing files; at minimum warn when overwriting config.toml or hooks.json. |

*Note: Critical findings (#1, #2 in security findings table) require private disclosure before public PR — see recommendation below.*

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | plugins/flow-next/agents/repo-scout.md | Single output format block (no separate example with sample input) | -5 |
| 2 | plugins/flow-next/agents/security-scout.md | Single output format block | -5 |
| 3 | plugins/flow-next/agents/practice-scout.md | Single output format block | -5 |
| 4 | plugins/flow-next/agents/docs-scout.md | Single output format block | -5 |
| 5 | plugins/flow-next/agents/quality-auditor.md | Single output format block | -5 |
| 6 | plugins/flow-next/agents/flow-gap-analyst.md | Single output format block | -5 |
| 7 | plugins/flow-next/agents/testing-scout.md | Single output format block | -5 |
| 8 | plugins/flow-next/agents/claude-md-scout.md | Single output format block | -5 |
| 9 | plugins/flow-next/agents/env-scout.md | Single output format block | -5 |
| 10 | plugins/flow-next/agents/tooling-scout.md | Single output format block | -5 |
| 11 | plugins/flow-next/agents/workflow-scout.md | Single output format block | -5 |
| 12 | plugins/flow-next/agents/build-scout.md | Single output format block | -5 |
| 13 | plugins/flow-next/agents/observability-scout.md | Single output format block | -5 |
| 14 | plugins/flow-next/agents/epic-scout.md | Rules section says "Use haiku" contradicting `model: claude-sonnet-4-6` declaration | -5 (also filed as Bug #1) |
| 15 | plugins/flow/agents/repo-scout.md | Single output format example; lacks confidence tags (`[VERIFIED]`/`[INFERRED]`) present in flow-next version | -5 |
| 16 | plugins/flow/agents/practice-scout.md | Stale year (2025); single output format example | -7 |
| 17 | plugins/flow/agents/docs-scout.md | Single output format example | -5 |
| 18 | plugins/flow/agents/quality-auditor.md | Single output format example | -5 |

## Cross-Component

**Intentional duplication:** `plugins/flow-next/skills/` is the canonical source; `plugins/flow-next/codex/skills/` is generated by `scripts/sync-codex.sh` with Codex-specific path patches. This is correct by design (documented in CLAUDE.md). All 16 skill pairs are consistent.

**All cross-references verified:** Every `[phases.md](phases.md)`, `[steps.md](steps.md)`, `[workflow.md](workflow.md)`, `[questions.md](questions.md)`, and `[cli-reference.md](cli-reference.md)` referenced from skill SKILL.md files was confirmed to exist.

**Model mapping documented but partially inconsistent:** The Codex model mapping table (CLAUDE.md) assigns `claude-sonnet-4-6` (fast) to epic-scout, but the Rules section of epic-scout.md says "Use haiku model". Sync-codex.sh correctly maps claude-sonnet-4-6 to gpt-5.4-mini for this agent, so the runtime behavior is correct, but the in-file rules comment is misleading.

**Flow vs. flow-next version gap:** The `flow` plugin agents are older versions of their flow-next counterparts. They lack: confidence tags, DESIGN.md validation sections, year-aware guidance (2026), and the expanded GitHub source quality heuristics. This is expected for a v1/v2 split, not a consistency bug.

**hooks.json correctly conditionalizes on ralph-guard.py existence:** The guard pattern `[ ! -f scripts/ralph/hooks/ralph-guard.py ] || ...` ensures hooks are silently no-ops when Ralph isn't installed. This is correct and intentional.

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

The pre-scan and detailed review confirmed 2 Critical pattern matches (eval with shell variables in executed test scripts) and 3 Medium findings (eval with user-controlled `$REVIEW_SUMMARY` in agent-executed workflow instructions). The `$REVIEW_SUMMARY` variable is populated from user-supplied epic spec text; a maliciously crafted spec title/summary could inject shell commands that execute when agents run the review workflow.

**Steps before contributing:**

1. **File a private security report** with maintainer gordon@mickel.tech covering Findings #1–#5 (eval patterns).
2. **Await maintainer response** on the eval refactor before any public PRs.
3. **After security fix is confirmed**, submit separate PRs for:
   - Bug #1: epic-scout.md rules/model contradiction
   - Bug #2: flow/practice-scout.md stale year
   - Medium security fix: install-codex.sh overwrite warning
4. **Quality PRs** (single output example improvement for 13 flow-next agents) can be batched into one PR after security is cleared.
