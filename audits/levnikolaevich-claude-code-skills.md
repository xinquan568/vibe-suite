# NLPM Audit: levnikolaevich/claude-code-skills
**Date**: 2026-04-06  |  **Artifacts**: 288  |  **Strategy**: progressive
**NL Score**: 77/100
**Security**: BLOCKED
**Bugs**: 13  |  **Quality Issues**: 22  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills-catalog/shared/agents/prompt_templates/general_analysis.md | prompt-template | 40 | Missing name/description frontmatter; missing output format spec |
| skills-catalog/shared/agents/prompt_templates/scope_analysis.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/scenario_validator.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/review_base.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/iterative_refinement.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/task_decomposition.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/traceability_validator.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/refinement_perspectives.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/modes/code.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/modes/story.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/modes/context.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/shared/agents/prompt_templates/modes/plan_review.md | prompt-template | 50 | Missing name/description frontmatter |
| skills-catalog/ln-774-healthcheck-setup/SKILL.md | skill | 75 | No model declared; no examples; missing Paths header |
| plugins/agile-workflow/skills/ln-402-task-reviewer/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-302-task-replanner/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-221-story-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-523-auto-test-planner/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-401-task-executor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-314-review-repair-worker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-522-manual-tester/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-521-test-researcher/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-513-regression-checker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-312-review-findings-worker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-403-task-rework/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-313-review-docs-worker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-301-task-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-310-multi-agent-validator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-404-test-executor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-520-test-planner/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-222-story-replanner/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-210-epic-coordinator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-230-story-prioritizer/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-1000-pipeline-orchestrator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-201-opportunity-discoverer/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-315-review-merge-worker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-510-quality-coordinator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-316-review-refinement-worker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-400-story-executor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-300-task-coordinator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-311-review-research-worker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-514-test-log-analyzer/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-511-code-quality-checker/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-220-story-coordinator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-500-story-quality-gate/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-200-scope-decomposer/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/agile-workflow/skills/ln-512-tech-debt-cleaner/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-120-reference-docs-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-114-frontend-docs-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-100-documents-pipeline/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-110-project-docs-coordinator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-162-skill-reviewer/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-130-tasks-docs-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-113-backend-docs-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-111-root-docs-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-161-skill-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-160-docs-skill-extractor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-140-test-docs-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-115-devops-docs-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/documentation-pipeline/skills/ln-112-project-core-creator/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-640-pattern-evolution-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-650-persistence-performance-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-628-concurrency-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-629-lifecycle-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-641-pattern-analyzer/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-653-runtime-performance-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-631-test-business-logic-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-627-observability-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-623-code-principles-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-654-resource-lifecycle-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-644-dependency-graph-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-646-project-structure-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-630-test-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-634-test-coverage-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-652-transaction-correctness-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-611-docs-structure-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-622-build-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-625-dependencies-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-643-api-contract-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-637-test-structure-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-610-docs-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| plugins/codebase-audit-suite/skills/ln-633-test-value-auditor/SKILL.md | skill (adapter) | 80 | No model declared; no examples |
| skills-catalog/ln-761-secret-scanner/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-812-optimization-researcher/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-651-query-efficiency-auditor/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-013-config-syncer/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-814-optimization-executor/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-636-manual-test-auditor/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-160-docs-skill-extractor/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-832-bundle-optimizer/SKILL.md | skill | 80 | No model declared; no examples |
| skills-catalog/ln-112-project-core-creator/SKILL.md | skill | 80 | No model declared; no examples |
| .claude/commands/cross-pollinate-mcp.md | command | 83 | No empty-input handling; vague "real transferable" |
| .claude/commands/publish-mcp.md | command | 83 | No empty-input handling |
| skills-catalog/ln-820-dependency-optimization-coordinator/SKILL.md | skill | 85 | No examples; disable-model-invocation present |
| skills-catalog/ln-140-test-docs-creator/SKILL.md | skill | 85 | No examples |
| skills-catalog/ln-115-devops-docs-creator/SKILL.md | skill | 85 | No examples |
| skills-catalog/ln-742-precommit-setup/SKILL.md | skill | 85 | No examples |
| skills-catalog/ln-910-community-engagement/SKILL.md | skill | 85 | No examples |
| skills-catalog/ln-914-community-responder/SKILL.md | skill | 85 | No examples |
| skills-catalog/ln-002-session-analyzer/SKILL.md | skill | 87 | No examples |
| .claude/commands/review-skills.md | command | 88 | Minor: no empty-input guard (N/A for repo-scoped command) |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 0 |
| Medium | 2 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts (.sh) | skills-catalog/ln-840-benchmark-compare/scripts/run-benchmark.sh, skills-catalog/ln-162-skill-reviewer/references/run_checks.sh, skills-catalog/ln-741-linter-configurator/references/lint_script_template.sh, skills-catalog/ln-742-precommit-setup/references/husky_precommit_template.sh, skills-catalog/ln-742-precommit-setup/references/husky_commitmsg_template.sh, skills-catalog/ln-522-manual-tester/references/templates/template-api-endpoint.sh, skills-catalog/ln-522-manual-tester/references/templates/template-document-format.sh |
| Scripts (.py) | skills-catalog/ln-743-test-infrastructure/references/conftest_template.py, skills-catalog/ln-743-test-infrastructure/references/pytest_test_template.py |
| Scripts (.mjs) | skills-catalog/ln-840-benchmark-compare/scripts/parse-results.mjs (benchmark results parser) |
| Package manifests | mcp/package.json, mcp/hex-line-mcp/package.json, mcp/hex-ssh-mcp/package.json, mcp/hex-graph-mcp/package.json, mcp/hex-common/package.json |
| MCP configs | None found |
| Hooks | None found |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | skills-catalog/ln-741-linter-configurator/references/lint_script_template.sh | 43 | eval-with-variable | `eval "$cmd"` executes the second argument of `run_check()` as a shell command. Any caller supplying a malicious second argument achieves arbitrary code execution. Template is designed for developer customization; all current callers are hardcoded, but the pattern is inherently unsafe. |
| 2 | Medium | skills-catalog/ln-840-benchmark-compare/scripts/run-benchmark.sh | 164 | dangerous-permission-bypass | `--dangerously-skip-permissions` passed to `claude` CLI bypasses Claude Code's permission model for the built-in session. Appropriate for CI benchmarks but unsafe if run against untrusted project trees. |
| 3 | Medium | skills-catalog/ln-840-benchmark-compare/scripts/run-benchmark.sh | 178 | dangerous-permission-bypass | Second `--dangerously-skip-permissions` in hex-line session (same risk as finding #2). |
| 4 | Low | skills-catalog/ln-840-benchmark-compare/scripts/run-benchmark.sh | 53 | hook-bypass | `git commit --no-gpg-sign --no-verify` in `checkpoint_worktree()` skips signing and pre-commit hooks on benchmark worktree commits. Low risk in isolated worktrees but sets a permissive pattern. |
| 5 | Low | mcp/package.json | 22 | unpinned-semver | All dependencies use `^` semver ranges (e.g. `"@modelcontextprotocol/sdk": "^1.29.0"`). Minor/patch upgrades are auto-pulled, which could introduce regressions in distributed MCP servers without a lockfile review. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills-catalog/shared/agents/prompt_templates/scope_analysis.md | Missing YAML frontmatter (`name:`, `description:`) — NL artifact scanner cannot discover or register this template | Template invisible to `/nlpm:ls`; cannot be scored or tracked automatically |
| 2 | skills-catalog/shared/agents/prompt_templates/scenario_validator.md | Missing YAML frontmatter | Same as #1 |
| 3 | skills-catalog/shared/agents/prompt_templates/review_base.md | Missing YAML frontmatter | Same as #1 |
| 4 | skills-catalog/shared/agents/prompt_templates/iterative_refinement.md | Missing YAML frontmatter | Same as #1 |
| 5 | skills-catalog/shared/agents/prompt_templates/task_decomposition.md | Missing YAML frontmatter | Same as #1 |
| 6 | skills-catalog/shared/agents/prompt_templates/traceability_validator.md | Missing YAML frontmatter | Same as #1 |
| 7 | skills-catalog/shared/agents/prompt_templates/refinement_perspectives.md | Missing YAML frontmatter | Same as #1 |
| 8 | skills-catalog/shared/agents/prompt_templates/modes/code.md | Missing YAML frontmatter | Same as #1 |
| 9 | skills-catalog/shared/agents/prompt_templates/modes/story.md | Missing YAML frontmatter | Same as #1 |
| 10 | skills-catalog/shared/agents/prompt_templates/modes/context.md | Missing YAML frontmatter | Same as #1 |
| 11 | skills-catalog/shared/agents/prompt_templates/modes/plan_review.md | Missing YAML frontmatter | Same as #1 |
| 12 | skills-catalog/shared/agents/prompt_templates/general_analysis.md | Missing YAML frontmatter AND missing output format specification (only a `{output_schema}` placeholder with no schema defined in-file) | Incomplete contract; callers cannot rely on a stable output shape |
| 13 | skills-catalog/ln-774-healthcheck-setup/SKILL.md | Missing `> **Paths:**` header present on all other skills-catalog SKILL.md files; violates the repo's skill_contract.md path-resolution rule | Agents loading this skill may fail to locate referenced files if CWD ≠ repo root |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | skills-catalog/ln-741-linter-configurator/references/lint_script_template.sh | `eval "$cmd"` in `run_check()` — eval with variable is CRITICAL pattern; marked as critical and requires private disclosure, not a public PR | N/A — see private disclosure note |
| 2 | skills-catalog/ln-840-benchmark-compare/scripts/run-benchmark.sh | `--dangerously-skip-permissions` used in CI benchmark runs | Add a guard: only allow when `BENCH_ALLOW_DANGEROUS=1` env var is explicitly set; document in script header |
| 3 | skills-catalog/ln-840-benchmark-compare/scripts/run-benchmark.sh | `git commit --no-gpg-sign --no-verify` in benchmark worktrees | Add a comment explaining isolation context; use `git commit -n` (short form of `--no-verify`) and keep it to isolated worktrees only |
| 4 | mcp/package.json | Unpinned `^` semver for published MCP packages | Pin exact versions or use `npm shrinkwrap`/lockfile review in CI; at minimum add `package-lock.json` to the mcp/ workspace |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | All 100 audited files | No example blocks (input→output usage demos) in any SKILL.md or prompt template | -15 per file |
| 2 | skills-catalog/ln-761-secret-scanner/SKILL.md | No `model:` declaration; NLPM cannot select appropriate tier for standalone invocations | -5 |
| 3 | skills-catalog/ln-812-optimization-researcher/SKILL.md | No `model:` declaration | -5 |
| 4 | skills-catalog/ln-651-query-efficiency-auditor/SKILL.md | No `model:` declaration | -5 |
| 5 | skills-catalog/ln-013-config-syncer/SKILL.md | No `model:` declaration | -5 |
| 6 | skills-catalog/ln-814-optimization-executor/SKILL.md | No `model:` declaration | -5 |
| 7 | skills-catalog/ln-636-manual-test-auditor/SKILL.md | No `model:` declaration | -5 |
| 8 | skills-catalog/ln-160-docs-skill-extractor/SKILL.md | No `model:` declaration | -5 |
| 9 | skills-catalog/ln-832-bundle-optimizer/SKILL.md | No `model:` declaration | -5 |
| 10 | skills-catalog/ln-112-project-core-creator/SKILL.md | No `model:` declaration | -5 |
| 11 | skills-catalog/ln-774-healthcheck-setup/SKILL.md | No `model:` declaration | -5 |
| 12 | All 68 Codex adapter SKILL.md files in plugins/ | No `model:` declaration in any adapter (thin adapters rely on canonical skill's model) | -5 per file |
| 13 | skills-catalog/shared/agents/prompt_templates/general_analysis.md | `{output_schema}` is an unresolved placeholder — callers must supply schema at render time, but no default or contract is documented | -10 |
| 14 | skills-catalog/shared/agents/prompt_templates/review_base.md | Uses 18+ template variables (`{mode_header}`, `{mode_constraints}`, `{mode_body}`, etc.) with no variable contract document; the composition contract is implicit | Informational |
| 15 | skills-catalog/shared/agents/prompt_templates/modes/*.md | Mode template files use `## header`, `## constraints`, `## body` section markers that are not standard YAML or Markdown headings — they act as assembly keys for review_base.md but this contract is undocumented | Informational |
| 16 | .claude/commands/cross-pollinate-mcp.md | No empty/null `$ARGUMENTS` handling defined; command always runs against current repo | -0 (repo-scoped command, N/A) |
| 17 | .claude/commands/publish-mcp.md | `Glob` declared in `allowed-tools` but not directly invoked (Bash covers file inspection); minor unused-tool signal | -3 |
| 18 | skills-catalog/ln-812-optimization-researcher/SKILL.md | Uses "appropriate" (Phase 2, bottleneck section) and "relevant" (Phase 3, local check) — vague quantifiers | -4 |
| 19 | skills-catalog/ln-651-query-efficiency-auditor/SKILL.md | "relevant" appears twice in Detection sections | -4 |
| 20 | skills-catalog/ln-013-config-syncer/SKILL.md | "appropriate" in Phase 3 merge strategy description | -2 |
| 21 | skills-catalog/ln-774-healthcheck-setup/SKILL.md | "appropriate" appears in Phase 4 timing section | -2 |
| 22 | skills-catalog/ln-636-manual-test-auditor/SKILL.md | "relevant" in Layer 2 context analysis steps | -2 |

## Cross-Component

**CC-1: Prompt templates are architecturally undiscoverable.** The 12 files under `skills-catalog/shared/agents/prompt_templates/` have no YAML frontmatter and therefore cannot be indexed by NL artifact scanners. They are referenced exclusively via `MANDATORY READ` directives from calling skills (e.g., `review_base.md` is assembled by review mode skills). The variable contract between `review_base.md` and its mode files (`modes/code.md`, `modes/story.md`, etc.) is implicit — no document defines the full set of `{template_variable}` slots or their valid values. If a calling skill omits a variable, the rendered prompt silently retains the `{placeholder}` literal. Recommendation: add a `variables_contract.md` or minimal frontmatter block to each template.

**CC-2: Codex adapter layer creates version divergence risk.** All 68 SKILL.md files in `plugins/agile-workflow/`, `plugins/documentation-pipeline/`, and `plugins/codebase-audit-suite/` are thin Codex adapters that load canonical skills from `skills-catalog/` via `MANDATORY READ`. This is a clean delegation pattern, but the adapters all carry `**Version:** 1.0.0` and `**Last Updated:** 2026-04-24` regardless of canonical skill version. When a canonical skill is updated (e.g., `skills-catalog/ln-140-test-docs-creator/SKILL.md` is at `7.2.0`), the adapter remains at `1.0.0` with no signal that the delegation target changed. The adapter `**Last Updated:**` date should track canonical changes, or the adapters should reference the canonical version number.

**CC-3: Skills duplicated across catalog and plugins.** `skills-catalog/ln-160-docs-skill-extractor/SKILL.md` and `plugins/documentation-pipeline/skills/ln-160-docs-skill-extractor/SKILL.md` are both present. The plugins/ version is a thin adapter; however, the description text in both files must stay in sync. Similarly for ln-140, ln-115, ln-112. Current state appears consistent; monitor on next canonical update.

**CC-4: `ln-820` uses mixed runtime path.** `skills-catalog/ln-820-dependency-optimization-coordinator/SKILL.md` (line 310) references `node shared/scripts/optimization-runtime/cli.mjs` inside a code block under `## Worker Invocation (MANDATORY)`, but the runtime contract section at the top of the file references `shared/scripts/dependency-runtime/cli.mjs`. Both paths are referenced in the same file. This is either a stale copy of the optimization runtime path or a legitimate secondary runtime. Verify which CLI path is correct for worker delegation.

## Recommendation
BLOCKED — do not submit PRs. File private security report for the `eval "$cmd"` CRITICAL finding in `skills-catalog/ln-741-linter-configurator/references/lint_script_template.sh:43`.

Once the critical finding is resolved and disclosed:
- Submit bug-fix PRs for the 13 NL artifact bugs (prompt template frontmatter + ln-774 Paths header).
- Submit medium/low security fix PRs for `--dangerously-skip-permissions` guard and semver pinning.
- Quality improvements (model declarations, example blocks) can follow in a separate PR batch.
