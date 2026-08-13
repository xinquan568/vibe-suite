# NLPM Audit: shinpr/claude-code-workflows
**Date**: 2026-04-06  |  **Artifacts**: 51  |  **Strategy**: batched
**NL Score**: 91/100
**Security**: CLEAR
**Bugs**: 3  |  **Quality Issues**: 32  |  **Security Findings**: 0

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| agents/work-planner.md | agent | 80 | No model declared; 5 vague quantifiers |
| agents/technical-designer.md | agent | 80 | No model declared; Grep called but not declared in tools; 5 vague quantifiers |
| agents/technical-designer-frontend.md | agent | 80 | No model declared; Grep called but not declared in tools; 5 vague quantifiers |
| agents/codebase-analyzer.md | agent | 82 | No model declared; 4 vague quantifiers ("appropriate"×3, "relevant"×1) |
| agents/document-reviewer.md | agent | 82 | No model declared; 4 vague quantifiers ("appropriate"×2, "relevant"×2) |
| agents/requirement-analyzer.md | agent | 82 | No model declared; TaskCreate/TaskUpdate declared but unused in body |
| agents/solver.md | agent | 84 | No model declared; 3 vague quantifiers |
| agents/task-executor.md | agent | 84 | No model declared; 3 vague quantifiers |
| agents/verifier.md | agent | 84 | No model declared; 3 vague quantifiers |
| agents/scope-discoverer.md | agent | 84 | No model declared; 3 vague quantifiers |
| agents/task-decomposer.md | agent | 84 | No model declared; 3 vague quantifiers |
| agents/security-reviewer.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/rule-advisor.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/ui-spec-designer.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/prd-creator.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/task-executor-frontend.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/code-reviewer.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/code-verifier.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/investigator.md | agent | 86 | No model declared; 2 vague quantifiers |
| agents/quality-fixer.md | agent | 88 | No model declared; minimal vague |
| agents/quality-fixer-frontend.md | agent | 88 | No model declared; minimal vague |
| agents/integration-test-reviewer.md | agent | 88 | No model declared; minimal vague |
| agents/acceptance-test-generator.md | agent | 91 | No model declared (offset by rich test skeleton examples) |
| agents/design-sync.md | agent | 93 | No model declared (offset by rich conflict examples) |
| skills/test-implement/SKILL.md | skill | 97 | Minimal — dispatches to references |
| skills/recipe-plan/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-build/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-fullstack-build/SKILL.md | skill | 97 | Cross-plugin dependency undocumented |
| skills/implementation-approach/SKILL.md | skill | 96 | 2 vague quantifiers |
| skills/testing-principles/SKILL.md | skill | 97 | Minimal vague |
| skills/integration-e2e-testing/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-front-review/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-fullstack-implement/SKILL.md | skill | 97 | Cross-plugin dependency undocumented |
| skills/recipe-diagnose/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-add-integration-tests/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-task/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-front-build/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-front-plan/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-review/SKILL.md | skill | 97 | Minimal vague |
| skills/task-analyzer/SKILL.md | skill | 97 | Minimal vague |
| skills/documentation-criteria/SKILL.md | skill | 97 | Minimal vague |
| skills/ai-development-guide/SKILL.md | skill | 97 | Minimal vague |
| skills/frontend-ai-guide/SKILL.md | skill | 97 | Minimal vague |
| skills/coding-principles/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-update-doc/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-implement/SKILL.md | skill | 97 | Minimal vague |
| skills/typescript-rules/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-front-design/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-design/SKILL.md | skill | 97 | Minimal vague |
| skills/subagents-orchestration-guide/SKILL.md | skill | 97 | Minimal vague |
| skills/recipe-reverse-engineer/SKILL.md | skill | 97 | Minimal vague |

**Score computation**: Agent average 85.1 (2042/24); Skill average 97.0 (2619/27); Weighted average (51 artifacts) = 4661/51 = **91/100**.

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 0 — no `hooks/` directory |
| Shell scripts | 0 — no `scripts/` directory |
| MCP configs | 0 — no `.mcp.json` |
| Package manifests | 0 — no `package.json` or `requirements.txt` |
| Plugin manifest | `.claude-plugin/marketplace.json` (metadata only, no executable content) |

### Security Findings

No security findings.

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | agents/technical-designer.md | `Grep` tool used in body ("identify target files using Grep") but not declared in `tools:` frontmatter. Other design-phase agents (document-reviewer, code-verifier, codebase-analyzer) all declare Grep. | Agent will be unable to call the Grep tool at runtime; grep-based file discovery silently degrades to Bash fallback or fails entirely |
| 2 | agents/technical-designer-frontend.md | Same as Bug #1 — body instructs "identify target files with `Grep: "function.*Component|export.*function use" --type tsx`" but `tools:` lists only Bash, not Grep | Same impact as Bug #1; frontend design discovery loses the dedicated Grep tool |
| 3 | agents/requirement-analyzer.md | `TaskCreate` and `TaskUpdate` are declared in `tools:` but the agent body has no "Task Registration" instruction, unlike every other agent in the repo. The `## Initial Mandatory Tasks` section only mentions date retrieval, not task tracking. Unused declared tools carry wasted capability weight. | Unused tools (-3 each per NLPM rules); inconsistent task-tracking behavior vs all other agents |

## Security Fixes (PR-worthy, Medium/Low only)

No security fixes needed.

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | All 24 agents | No `model:` field declared in frontmatter. Default model is used (currently Sonnet 4.6), but pinning is best practice for stable agentic behavior | -5 each (−120 total across agents) |
| 2 | All 24 agents | Zero standalone invocation examples. All agents provide JSON output-format schemas but no example showing a concrete agent invocation and its response. design-sync and acceptance-test-generator partially offset this with concrete data examples | -5 each for one-example tier (−120 total) |
| 3 | agents/work-planner.md | Vague quantifiers: "appropriate" ×5 across Phase Division Criteria, task design principles, and diagram sections | −10 |
| 4 | agents/technical-designer.md | Vague quantifiers: "appropriate" ×5 in Grep instructions, ADR responsibility, and implementation guidelines | −10 |
| 5 | agents/technical-designer-frontend.md | Vague quantifiers: "appropriate" ×5 in Grep instructions, props patterns, and component guidelines | −10 |
| 6 | agents/codebase-analyzer.md | Vague quantifiers: "appropriate" ×3, "relevant" ×1 in category detection and pattern search steps | −8 |
| 7 | agents/document-reviewer.md | Vague quantifiers: "appropriate" ×2, "relevant" ×2 in review mode and scope descriptions | −8 |
| 8 | agents/solver.md | Vague quantifiers: "appropriate" ×3 in solution type table, recommendation strategy | −6 |
| 9 | agents/task-executor.md | Vague quantifiers: "appropriate" ×3 in judgment criteria and implementation flow | −6 |
| 10 | agents/verifier.md | Vague quantifiers: "appropriate" ×3 in triangulation and coverage assessment | −6 |
| 11 | agents/scope-discoverer.md | Vague quantifiers: "appropriate" ×3 in discovery sources and boundary validation | −6 |
| 12 | agents/task-decomposer.md | Vague quantifiers: "appropriate" ×3 in verification criteria and task structuring | −6 |
| 13 | agents/requirement-analyzer.md | `TaskCreate` and `TaskUpdate` declared in tools but never instructed in body; -3 each for unused declared tools | −6 |
| 14 | agents/security-reviewer.md | Vague quantifiers: "appropriate" ×2 in review area descriptions | −4 |
| 15 | agents/rule-advisor.md | Vague quantifiers: "appropriate" ×2 in section selection heuristics | −4 |
| 16 | agents/ui-spec-designer.md | Vague quantifiers: "relevant" ×1, "appropriate" ×1 in component search steps | −4 |
| 17 | agents/prd-creator.md | Vague quantifiers: "appropriate" ×2 in format and scope descriptions | −4 |
| 18 | agents/task-executor-frontend.md | Vague quantifiers: "appropriate" ×2 in escalation criteria | −4 |
| 19 | agents/code-reviewer.md | Vague quantifiers: "appropriate" ×2 in evidence collection | −4 |
| 20 | agents/code-verifier.md | Vague quantifiers: "appropriate" ×2 in claim extraction | −4 |
| 21 | agents/investigator.md | Vague quantifiers: "appropriate" ×2 in failure-check criteria | −4 |
| 22 | skills/implementation-approach/SKILL.md | Vague quantifiers: "appropriate" ×2 in strategy selection criteria | −4 |
| 23 | skills/recipe-fullstack-implement/SKILL.md | References task-executor-frontend and quality-fixer-frontend (dev-workflows-frontend plugin) in its execution flow but the dev-workflows plugin manifest does not document this cross-plugin dependency. Users installing only dev-workflows will get runtime failures on fullstack flows. | Informational |
| 24 | skills/recipe-fullstack-build/SKILL.md | Same cross-plugin dependency as #23 — routes \*-frontend-task-\* to task-executor-frontend and quality-fixer-frontend | Informational |

## Cross-Component

**Cross-plugin dependency gap**: `recipe-fullstack-implement` and `recipe-fullstack-build` are included in the `dev-workflows` plugin but their execution paths route `*-frontend-task-*` files to `task-executor-frontend` and `quality-fixer-frontend`, which belong to `dev-workflows-frontend`. The `dev-workflows` marketplace entry does not list `dev-workflows-frontend` as a peer dependency. A user installing only `dev-workflows` will encounter missing-agent errors when running fullstack recipes. **Recommended fix**: add a `peerDependencies` or `requiredPlugins` field to the `dev-workflows` marketplace entry noting that `dev-workflows-frontend` is required for fullstack workflows, or split fullstack recipes into a separate plugin.

**Grep tool omission pattern**: `technical-designer` and `technical-designer-frontend` both omit `Grep` from their tools while all other investigation/design agents (codebase-analyzer, document-reviewer, code-verifier, code-reviewer, scope-discoverer, etc.) include it. This asymmetry suggests an accidental omission in both files rather than an intentional design choice — the two files are likely based on the same template that predates Grep being added to the shared agent pattern.

**Reference file coverage**: All `references/*.md` and `references/*.yaml` files cited in skill bodies were confirmed present on disk (`references/security-checks.md`, `references/monorepo-flow.md`, `references/skills-index.yaml`, `references/e2e-design.md`, `references/frontend.md`, `references/e2e.md`, plus documentation templates). No broken reference paths found.

**Agent inventory vs marketplace.json**: `scope-discoverer` is listed in `dev-workflows` agents but absent from `dev-workflows-frontend` agents. This appears intentional — scope-discoverer is used by `recipe-reverse-engineer` which is also backend-only. No inconsistency.

## Recommendation

CLEAR — submit PRs for all 3 bugs. No security findings, no critical NL issues. The overall 91/100 score is strong. Primary improvements are mechanical: add `model:` declarations to all agents (one-line change per file) and add Grep to the tools lists of technical-designer and technical-designer-frontend. The cross-plugin dependency gap for fullstack recipes is worth addressing with a documentation or manifest fix to avoid user-facing failures.
