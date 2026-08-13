# NLPM Audit: sangrokjung/claude-forge
**Date**: 2026-04-16  |  **Artifacts**: 98  |  **Strategy**: progressive
**NL Score**: 82/100
**Security**: REVIEW
**Bugs**: 14  |  **Quality Issues**: 18  |  **Security Findings**: 6

---

## NL Score Summary

Scores for 73 core NL artifacts (agents, commands, skills). 25 supplementary knowledge/reference files included in the 98 discovery count are noted at the end of this section.

| Score | Artifact | Type | Class |
|-------|----------|------|-------|
| 60 | commands/test-coverage.md | command | BUG |
| 60 | commands/update-codemaps.md | command | BUG |
| 60 | commands/update-docs.md | command | BUG |
| 72 | commands/agent-router.md | command | BUG |
| 72 | commands/build-fix.md | command | BUG |
| 72 | commands/code-review.md | command | BUG |
| 72 | commands/debugging-strategies/SKILL.md | skill-cmd | BUG |
| 75 | commands/eval.md | command | BUG |
| 75 | commands/refactor-clean.md | command | BUG |
| 75 | commands/tdd.md | command | BUG |
| 78 | commands/e2e.md | command | BUG |
| 78 | commands/extract-errors/SKILL.md | skill-cmd | quality |
| 78 | commands/plan.md | command | BUG |
| 80 | commands/pull.md | command | quality |
| 80 | skills/continuous-learning-v2/agents/observer.md | agent | BUG |
| 80 | skills/continuous-learning-v2/commands/evolve.md | command | quality |
| 80 | skills/continuous-learning-v2/commands/instinct-export.md | command | quality |
| 80 | skills/continuous-learning-v2/commands/instinct-import.md | command | quality |
| 80 | skills/continuous-learning-v2/commands/instinct-status.md | command | quality |
| 82 | agents/verify-agent.md | agent | BUG |
| 82 | commands/checkpoint.md | command | quality |
| 82 | commands/dependency-upgrade/SKILL.md | skill-cmd | quality |
| 82 | commands/evaluating-llms-harness/SKILL.md | skill-cmd | quality |
| 82 | commands/learn.md | command | quality |
| 82 | commands/show-setup.md | command | quality |
| 82 | commands/suggest-automation.md | command | - |
| 82 | commands/summarize/SKILL.md | skill-cmd | quality |
| 82 | commands/worktree-cleanup.md | command | - |
| 82 | commands/worktree-start.md | command | - |
| 82 | skills/build-system/SKILL.md | skill | quality |
| 82 | skills/manage-skills/SKILL.md | skill | quality |
| 82 | skills/prompts-chat/SKILL.md | skill | quality |
| 82 | skills/skill-factory/SKILL.md | skill | quality |
| 82 | skills/strategic-compact/SKILL.md | skill | - |
| 82 | skills/using-superpowers/SKILL.md | skill | quality |
| 82 | skills/verify-implementation/SKILL.md | skill | - |
| 85 | agents/database-reviewer.md | agent | quality |
| 85 | agents/doc-updater.md | agent | quality |
| 85 | agents/security-reviewer.md | agent | quality |
| 85 | commands/auto.md | command | - |
| 85 | commands/evaluating-code-models/SKILL.md | skill-cmd | - |
| 85 | commands/explore.md | command | - |
| 85 | commands/forge-update.md | command | - |
| 85 | commands/guide.md | command | - |
| 85 | commands/init-project.md | command | - |
| 85 | commands/next-task.md | command | - |
| 85 | commands/orchestrate.md | command | quality |
| 85 | commands/quick-commit.md | command | - |
| 85 | commands/security-compliance/SKILL.md | skill-cmd | - |
| 85 | commands/stride-analysis-patterns/SKILL.md | skill-cmd | - |
| 85 | commands/sync-docs.md | command | - |
| 85 | commands/sync.md | command | - |
| 85 | commands/verify-loop.md | command | - |
| 85 | commands/web-checklist.md | command | - |
| 85 | skills/cache-components/SKILL.md | skill | - |
| 85 | skills/cc-dev-agent/SKILL.md | skill | - |
| 85 | skills/eval-harness/SKILL.md | skill | - |
| 85 | skills/frontend-code-review/SKILL.md | skill | - |
| 85 | skills/session-wrap/SKILL.md | skill | - |
| 85 | skills/team-orchestrator/SKILL.md | skill | - |
| 88 | agents/architect.md | agent | - |
| 88 | agents/build-error-resolver.md | agent | - |
| 88 | agents/e2e-runner.md | agent | - |
| 88 | agents/planner.md | agent | - |
| 88 | agents/refactor-cleaner.md | agent | - |
| 88 | agents/tdd-guide.md | agent | - |
| 88 | commands/commit-push-pr.md | command | - |
| 88 | commands/handoff-verify.md | command | - |
| 88 | commands/security-review.md | command | - |
| 88 | skills/continuous-learning-v2/SKILL.md | skill | - |
| 88 | skills/security-pipeline/SKILL.md | skill | - |
| 88 | skills/verification-engine/SKILL.md | skill | - |
| 90 | agents/code-reviewer.md | agent | - |

**Supplementary knowledge files** (25 files; reference docs and rules with no YAML frontmatter; not scored as commands/agents/skills):

- `commands/evaluating-code-models/references/` (3 files) — benchmark reference docs
- `commands/evaluating-llms-harness/references/` (4 files) — eval reference docs
- `commands/security-compliance/reference/` (5 files) + `examples/` (2 files) — compliance reference material
- `skills/cache-components/PATTERNS.md`, `REFERENCE.md`, `TROUBLESHOOTING.md` — skill reference docs
- `rules/` (9 files: agents-v2, coding-style, date-calculation, git-workflow-v2, golden-principles, interaction, security, testing, verification) — `.claude/rules` plain-markdown convention; no YAML frontmatter is expected by that format

---

## Security Scan

| Severity | Count | Description |
|----------|-------|-------------|
| Critical | 0 | — |
| High     | 0 | — |
| Medium   | 4 | Unversioned package auto-install (MCP), unconditional network call on SessionStart, security hooks require env-var opt-in |
| Low      | 2 | Unpinned Python dependencies in scripts |

**Pre-scan flags resolved**: The automated pre-scan flagged 3 Critical and 2 High pattern matches (`base64.b64decode`, `eval` regex strings, subprocess calls). Manual code review confirmed all are false positives — defensive detection patterns in security hooks, not execution. See Security Findings below.

---

## Execution Surface Inventory

| File | Surface Type | Active Condition |
|------|-------------|-----------------|
| hooks/output-secret-filter.sh | PostToolUse hook (Python heredoc) | `OPENCLAW_SESSION_ID` set |
| hooks/remote-command-guard.sh | PreToolUse hook (Python heredoc) | `OPENCLAW_SESSION_ID` set |
| hooks/rate-limiter.sh | PreToolUse hook (shell + JSON) | `OPENCLAW_SESSION_ID` set |
| hooks/db-guard.sh | PreToolUse hook (Python heredoc) | `OPENCLAW_SESSION_ID` set |
| hooks/security-auto-trigger.sh | PostToolUse hook (shell) | `OPENCLAW_SESSION_ID` set |
| hooks/forge-update-check.sh | SessionStart hook (shell) | Always (4h cooldown) |
| scripts/md-to-docx/install.sh | Manual install script | On explicit run |
| scripts/md-to-docx/convert.py | Python CLI wrapper | On explicit run |
| scripts/pdf-enhance/enhance_pdf.py | Python post-processor | On explicit run |
| .mcp.json | MCP server config | Claude Code session start |
| mcp-servers.json | MCP server config (alternate) | Claude Code session start |
| .claude-plugin/plugin.json | Plugin manifest v2.2.0 | Plugin install |

---

## Security Findings

| ID | Sev | File | Line | Pattern | Finding |
|----|-----|------|------|---------|---------|
| S1 | MED | .mcp.json | 3,7,11,15,19 | `npx -y @…/…@latest` | 4 MCP packages auto-installed at latest without version pins: `@upstash/context7-mcp`, `@modelcontextprotocol/server-memory`, `@modelcontextprotocol/server-github`, `jina-mcp-tools`. Supply chain risk on each session start. |
| S2 | MED | mcp-servers.json | 3,7,11,15 | `npx -y @…/…@latest` + external HTTP | Same npx -y unversioned pattern. Additionally configures `https://mcp.exa.ai/mcp` — external HTTP endpoint without authentication. Requests will egress to third-party server during sessions. |
| S3 | MED | hooks/forge-update-check.sh | ~45 | `git fetch origin` | Unconditional outbound network call on every `SessionStart` (4h cooldown). Validates repo path before executing, so no injection risk, but every session may silently exfiltrate environment presence to the remote. |
| S4 | MED | hooks/ (all 5 security hooks) | ~1 | `OPENCLAW_SESSION_ID` guard | All defensive hooks (secret filter, command guard, rate limiter, db-guard, security-auto-trigger) are gated behind `OPENCLAW_SESSION_ID` environment variable. Local development sessions receive zero hook protection. Documented design for remote sessions, but creates an unprotected gap for local users. |
| S5 | LOW | scripts/md-to-docx/requirements.txt | all | unpinned deps | Python packages (`python-docx`, `mammoth`, `markdown`) have no version pins. Reproducibility risk; upstream compromise could silently inject malicious code on next `install.sh` run. |
| S6 | LOW | scripts/pdf-enhance/enhance_pdf.py | imports | unpinned PyMuPDF | `import fitz` (PyMuPDF) loaded without version constraint. Same supply chain reproducibility risk. |

**False positives confirmed clear:**
- `hooks/output-secret-filter.sh`: `base64.b64decode` decodes suspected secrets for *detection* (masking), does not execute decoded content.
- `hooks/remote-command-guard.sh`: `eval\(` appears only inside Python regex strings being *blocked*, not executed.
- `hooks/forge-update-check.sh`: `subprocess.run` calls only `git` with a validated local repo path.

---

## Bugs

| # | File | Field | Issue |
|---|------|-------|-------|
| 1 | agents/verify-agent.md | `tools` | `Task` absent from frontmatter tools array. Agent body (Tool_Usage section + Configuration table) explicitly requires Task to spawn security-reviewer subagent; without it the spawn call will fail silently. |
| 2 | commands/update-docs.md | frontmatter | No YAML frontmatter at all — no `description`, no `allowed-tools`. File opens with a raw `#` heading. Not registerable as a command. |
| 3 | commands/test-coverage.md | frontmatter | No YAML frontmatter. File is raw markdown. Not registerable as a command. |
| 4 | commands/update-codemaps.md | frontmatter | No YAML frontmatter. File opens with `# Update Codemaps` heading. Not registerable as a command. |
| 5 | commands/debugging-strategies/SKILL.md | references | References 6 non-existent files: `references/debugging-tools-guide.md`, `references/performance-profiling.md`, `references/production-debugging.md`, `assets/debugging-checklist.md`, `assets/common-bugs.md`, `scripts/debug-helper.ts`. All are dead links. |
| 6 | skills/continuous-learning-v2/agents/observer.md | `tools` | `tools` array entirely absent from frontmatter. Background agent with model and run_mode declared but no tools declaration means the runtime cannot constrain or grant tool access. |
| 7 | commands/eval.md | `allowed-tools` | Missing `allowed-tools` key. Command description and body exist; frontmatter has only `description`. |
| 8 | commands/plan.md | `allowed-tools` | Missing `allowed-tools`. Frontmatter has `description` only. |
| 9 | commands/tdd.md | `allowed-tools` | Missing `allowed-tools`. Frontmatter has `description` only. |
| 10 | commands/build-fix.md | `allowed-tools` | Missing `allowed-tools`. Frontmatter has `description` only. |
| 11 | commands/e2e.md | `allowed-tools` | Missing `allowed-tools`. Frontmatter has `description` only. |
| 12 | commands/code-review.md | `allowed-tools` | Missing `allowed-tools`. Frontmatter has `description` only. |
| 13 | commands/agent-router.md | `allowed-tools` | Missing `allowed-tools`. Frontmatter has `name` + `description` only. The router dispatches 34 domains yet declares no tools. |
| 14 | commands/refactor-clean.md | `allowed-tools` | Missing `allowed-tools`. Frontmatter has `description` only, despite body listing multi-step tool usage (knip, depcheck, ts-prune). |

---

## Security Fixes

| # | File | Fix |
|---|------|-----|
| F1 | .mcp.json | Pin all `npx -y` packages to exact versions, e.g. `@upstash/context7-mcp@1.0.x`. Run `npx npm-check-updates` to find current stable versions. Review each package's permissions before installing. |
| F2 | mcp-servers.json | Same version pinning as F1. Additionally audit the `https://mcp.exa.ai/mcp` HTTP endpoint: verify it is a trusted service and document the trust decision in a comment. Consider whether HTTPS with no auth token is acceptable for the data that will transit it. |
| F3 | hooks/forge-update-check.sh | Document the `OPENCLAW_SESSION_ID` activation requirement in the repo's README/FIRST-STEPS.md so local users know the guard is inactive. Consider adding a non-blocking warning log when the variable is absent. |
| F4 | hooks/ (all security hooks) | Add a startup log line when `OPENCLAW_SESSION_ID` is absent: `echo "⚠ Security hooks inactive (OPENCLAW_SESSION_ID not set)" >&2`. This surfaces the gap without blocking local use. |
| F5 | scripts/md-to-docx/requirements.txt | Pin all dependencies to tested versions, e.g. `python-docx==1.1.2`. Generate with `pip freeze > requirements.txt` after a clean install. |
| F6 | scripts/pdf-enhance/enhance_pdf.py | Add `PyMuPDF==X.Y.Z` to a `requirements.txt` (or `pyproject.toml`) in the same directory. |

---

## Quality Issues

| # | File | Issue |
|---|------|-------|
| Q1 | agents/database-reviewer.md | `Write` and `Edit` declared in tools for a reviewer agent. Reviewer role should be read-only (Read, Grep, Glob, Bash(git:*)). Write/Edit access contradicts stated purpose and creates unnecessary permission surface. |
| Q2 | agents/security-reviewer.md | Same Write/Edit on reviewer role issue. Additionally, MCP tools referenced in the agent body (e.g., `mcp__brave-search`) are not listed in the frontmatter `tools` array, creating an undeclared dependency. |
| Q3 | agents/doc-updater.md | Missing formal example interaction block (concrete before/after conversation). Agent describes behavior but provides no illustrative exchange for calibration. |
| Q4 | commands/extract-errors/SKILL.md | Minimal body (8 lines). Describes only `yarn extract-errors` without output format, error taxonomy, or edge-case handling. Under-specified for the implied complexity. |
| Q5 | commands/pull.md | Body is minimal (pull + sync-docs description). No empty-input handling documented, no error cases, no interaction example. |
| Q6 | skills/continuous-learning-v2/commands/ (4 files) | evolve.md, instinct-export.md, instinct-import.md, instinct-status.md all declare `implementation: python3 ~/.claude/…` but have no `allowed-tools` or `model` field. These commands delegate to a Python CLI yet don't declare what tools the Python process needs. |
| Q7 | commands/evaluating-llms-harness/SKILL.md | Missing `version` field present on sibling evaluating-code-models/SKILL.md. Inconsistent versioning across the evaluation skill pair. |
| Q8 | commands/dependency-upgrade/SKILL.md | Missing `version` field; no author or license. Compare evaluating-code-models/SKILL.md which has both. |
| Q9 | commands/summarize/SKILL.md | Depends on external CLI binary `summarize` (brew-installed). No graceful fallback documented if the binary is absent. The `metadata.install` block is helpful but the skill body has no guard. |
| Q10 | skills/using-superpowers/SKILL.md | Activation trigger is "Use when starting any conversation" — a global, unconditional trigger. Will fire on every session including subagent spawns (a `<SUBAGENT-STOP>` guard exists but it requires subagent self-awareness to respect). |
| Q11 | skills/manage-skills/SKILL.md | `disable-model-invocation: true` is a non-standard frontmatter field not in the Claude Code schema. Same for skills/skill-factory/SKILL.md and skills/verify-implementation/SKILL.md. Three skills use this undocumented flag. |
| Q12 | commands/orchestrate.md | Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` env var. This is noted in the skill body but is not in the command frontmatter or argument-hint. Users who run /orchestrate without the env var will hit silent failure. |
| Q13 | skills/team-orchestrator/SKILL.md | Same CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS dependency but no fallback behavior described. Agent Teams API is experimental; the skill should document degraded behavior when unavailable. |
| Q14 | agents/security-reviewer.md | The agent declares `Write` and `Edit` but the effort:max enforcement section says security verification must not be abbreviated — yet write capabilities could allow auto-patching, which conflicts with the stated reviewer-only mandate. |
| Q15 | commands/checkpoint.md | Multi-operation command (save/restore/list/diff/delete) handled via argument dispatch but the frontmatter `argument-hint` is absent. Users have no hint about which sub-operations exist. |
| Q16 | commands/debugging-strategies/SKILL.md | Even ignoring the broken references (Bug #5), the main body is very thin — it outsources all content to the missing reference files. Without those files the skill is near-empty. |
| Q17 | skills/build-system/SKILL.md | `last_updated: 2026-01-31` hardcoded date in frontmatter. Dates in static fields are maintenance liabilities; they will become stale and mislead consumers. |
| Q18 | commands/sync.md | Body says "v7 순차 실행" (v7 sequential execution) but the pull.md it references shows a simpler v6-era description. Version labels are inconsistent between command pairs. |

---

## Cross-Component

### verify-agent ↔ handoff-verify (Critical)

`commands/handoff-verify.md` dispatches to `agents/verify-agent.md` via Task. The command's `allowed-tools` includes `Task`. However, `agents/verify-agent.md`'s tools array omits `Task`. This means the verify-agent cannot complete its declared job of spawning the security-reviewer subagent (Bug #1). The handoff-verify command will reach Step 7 (security review) and silently fail to spawn the security subagent.

**Fix**: Add `Task` to `agents/verify-agent.md` tools array: `tools: ["Read", "Write", "Edit", "Bash", "Grep", "Glob", "Task"]`

### orchestrate ↔ team-orchestrator

`commands/orchestrate.md` declares the Agent Teams requirement inline but `skills/team-orchestrator/SKILL.md` (the skill it loads) only mentions the requirement in its Prerequisite section. Neither surfaces a runtime check or degraded-mode fallback. Any agent loading the skill in an environment without the experimental flag will have no warning.

### observer ↔ continuous-learning-v2

`skills/continuous-learning-v2/SKILL.md` describes a complete hook-based observation pipeline, but `skills/continuous-learning-v2/agents/observer.md` (the agent that processes observations) has no `tools` declaration (Bug #6). The observer cannot read `observations.jsonl` or write instincts without tools access. The parent skill is well-specified; the child agent is incomplete.

### security hooks ↔ local development

Five security hooks provide defense-in-depth but only under `OPENCLAW_SESSION_ID`. For a security-focused plugin (claude-forge positions itself as a DevSecOps platform), this creates a documentation gap: the README/FIRST-STEPS.md does not warn that local Claude Code sessions bypass all hook protections.

---

## Recommendation

**REVIEW — submit NL fix PRs, flag security findings in issue.**

### Priority order

1. **Bug #1** (verify-agent Task tool) — adds `Task` to tools array; one-line fix, restores core verification pipeline.
2. **Bugs #2–4** (missing frontmatter) — add minimal frontmatter to update-docs.md, test-coverage.md, update-codemaps.md.
3. **Bug #5** (debugging-strategies broken references) — either create the missing reference files or remove the dead links from the SKILL.md body.
4. **Bugs #7–14** (missing allowed-tools on 8 commands) — add `allowed-tools` to eval, plan, tdd, build-fix, e2e, code-review, agent-router, refactor-clean.
5. **S1–S2** (unversioned MCP packages) — pin npx package versions in .mcp.json and mcp-servers.json.
6. **S4** (hooks opt-in gap) — add warning log when `OPENCLAW_SESSION_ID` is absent.
7. **Bug #6** (observer missing tools) — add tools array to observer.md.

### Strengths worth preserving

- `agents/code-reviewer.md` (90), `commands/handoff-verify.md` (88), `commands/commit-push-pr.md` (88) — these are well-structured exemplars with full frontmatter, strong output format specs, and clear integration contracts.
- The Iron Law in `skills/verification-engine/SKILL.md` ("NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE") is a high-signal pattern worth adopting broadly.
- `skills/security-pipeline/SKILL.md` — CWE Top 25 + STRIDE + effort:max enforcement is a best-practice pattern.
- Security hooks are architecturally sound; the OPENCLAW gating is a deployment concern, not a design flaw.
