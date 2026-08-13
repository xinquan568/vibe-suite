# NLPM Audit: rohitg00/awesome-claude-code-toolkit
**Date**: 2026-04-17  |  **Artifacts**: 100 scanned (of 558 total)  |  **Strategy**: progressive
**NL Score**: 46/100
**Security**: CLEAR
**Bugs**: 164  |  **Quality Issues**: 156  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/helm-charts/commands/upgrade-chart.md | command | 25 | No frontmatter, no format section, no empty-input handling |
| plugins/technical-sales/commands/write-proposal.md | command | 35 | No frontmatter (name/description) |
| plugins/technical-sales/commands/create-demo.md | command | 35 | No frontmatter |
| plugins/devops-automator/commands/health-check.md | command | 35 | No frontmatter |
| plugins/devops-automator/commands/automate.md | command | 35 | No frontmatter |
| plugins/fix-pr/commands/fix-comments.md | command | 35 | No frontmatter |
| plugins/openapi-expert/commands/validate-spec.md | command | 35 | No frontmatter |
| plugins/readme-generator/commands/generate-readme.md | command | 35 | No frontmatter, no format section |
| plugins/visual-regression/commands/capture-baseline.md | command | 35 | No frontmatter, no format section |
| plugins/visual-regression/commands/compare.md | command | 35 | No frontmatter, no format section |
| plugins/bundle-analyzer/commands/tree-shake.md | command | 35 | No frontmatter, no format section |
| plugins/bundle-analyzer/commands/analyze-bundle.md | command | 35 | No frontmatter, no format section |
| plugins/license-checker/commands/generate-notice.md | command | 35 | No frontmatter, no format section |
| plugins/license-checker/commands/check-licenses.md | command | 35 | No frontmatter, no format section |
| plugins/security-guidance/commands/fix-vulnerability.md | command | 35 | No frontmatter, needs user input |
| plugins/performance-monitor/commands/profile-api.md | command | 35 | No frontmatter |
| plugins/performance-monitor/commands/benchmark.md | command | 35 | No frontmatter |
| plugins/flutter-mobile/commands/platform-channel.md | command | 35 | No frontmatter |
| plugins/flutter-mobile/commands/create-widget.md | command | 35 | No frontmatter |
| plugins/migrate-tool/commands/code-migrate.md | command | 35 | No frontmatter |
| plugins/migrate-tool/commands/db-migrate.md | command | 35 | No frontmatter |
| plugins/react-native-dev/commands/native-module.md | command | 35 | No frontmatter |
| plugins/react-native-dev/commands/create-screen.md | command | 35 | No frontmatter |
| plugins/helm-charts/commands/create-chart.md | command | 35 | No frontmatter, no format section |
| plugins/unit-test-generator/commands/generate-tests.md | command | 35 | No frontmatter |
| plugins/gcp-helper/commands/configure-gcs.md | command | 35 | No frontmatter, no format section |
| plugins/gcp-helper/commands/setup-cloud-run.md | command | 35 | No frontmatter, no format section |
| plugins/accessibility-checker/commands/aria-fix.md (accessibility) | command | 35 | No frontmatter |
| plugins/rag-builder/commands/index-docs.md | command | 35 | No frontmatter, no format section |
| plugins/rag-builder/commands/create-retriever.md | command | 35 | No frontmatter, no format section |
| plugins/python-expert/commands/refactor-py.md | command | 35 | No frontmatter |
| plugins/python-expert/commands/type-hints.md | command | 35 | No frontmatter |
| plugins/experiment-tracker/commands/track.md | command | 35 | No frontmatter |
| plugins/ci-debugger/commands/fix-pipeline.md | command | 35 | No frontmatter, no format section |
| plugins/ci-debugger/commands/analyze-ci-failure.md | command | 35 | No frontmatter, no format section |
| plugins/pr-reviewer/commands/review-pr.md | command | 35 | No frontmatter |
| plugins/pr-reviewer/commands/approve-pr.md | command | 35 | No frontmatter |
| plugins/github-issue-manager/commands/create-issue.md | command | 35 | No frontmatter, no format section |
| plugins/github-issue-manager/commands/triage-issues.md | command | 35 | No frontmatter, no format section |
| plugins/debug-session/commands/bisect.md | command | 35 | No frontmatter |
| plugins/debug-session/commands/debug.md | command | 35 | No frontmatter |
| plugins/model-context-protocol/commands/create-server.md | command | 35 | No frontmatter |
| plugins/model-context-protocol/commands/add-tool.md | command | 35 | No frontmatter |
| plugins/ai-prompt-lab/commands/test-prompt.md | command | 35 | No frontmatter |
| plugins/ai-prompt-lab/commands/improve-prompt.md | command | 35 | No frontmatter |
| plugins/mutation-tester/commands/mutate.md | command | 35 | No frontmatter, no format section |
| plugins/infrastructure-maintainer/commands/update-infra.md | command | 35 | No frontmatter |
| plugins/screen-reader-tester/commands/test-sr.md | command | 35 | No frontmatter, no format section |
| plugins/screen-reader-tester/commands/fix-aria.md | command | 35 | No frontmatter, no format section |
| plugins/workflow-optimizer/commands/suggest-improvements.md | command | 35 | No frontmatter |
| plugins/test-results-analyzer/commands/analyze-failures.md | command | 35 | No frontmatter |
| plugins/context7-docs/commands/fetch-docs.md | command | 35 | No frontmatter |
| plugins/commit-commands/commands/amend.md (wait — has format) | command | 35 | No frontmatter |
| plugins/test-writer/commands/unit-test.md | command | 35 | No frontmatter |
| plugins/test-writer/commands/integration-test.md | command | 35 | No frontmatter |
| plugins/slack-notifier/commands/send-update.md | command | 35 | No frontmatter, no format section |
| plugins/slack-notifier/commands/create-thread.md | command | 35 | No frontmatter, no format section |
| plugins/seed-generator/commands/generate-seeds.md | command | 35 | No frontmatter, no format section |
| plugins/azure-helper/commands/setup-functions.md | command | 35 | No frontmatter, no format section |
| plugins/azure-helper/commands/configure-blob.md | command | 35 | No frontmatter, no format section |
| plugins/workflow-optimizer/commands/analyze-workflow.md | command | 35 | No frontmatter |
| plugins/infrastructure-maintainer/commands/audit-infra.md | command | 35 | No frontmatter |
| plugins/update-branch/commands/rebase.md | command | 35 | No frontmatter |
| plugins/openapi-expert/commands/generate-spec.md | command | 45 | No frontmatter (has format, project-based) |
| plugins/dependency-manager/commands/update-deps.md | command | 45 | No frontmatter |
| plugins/dependency-manager/commands/audit-deps.md | command | 45 | No frontmatter |
| plugins/security-guidance/commands/security-check.md | command | 45 | No frontmatter |
| plugins/changelog-gen/commands/generate-changelog.md | command | 45 | No frontmatter |
| plugins/smart-commit/commands/commit.md | command | 45 | No frontmatter |
| plugins/smart-commit/commands/changelog.md | command | 45 | No frontmatter |
| plugins/analytics-reporter/commands/report.md | command | 45 | No frontmatter |
| plugins/analytics-reporter/commands/dashboard.md | command | 45 | No frontmatter |
| plugins/accessibility-checker/commands/a11y-scan.md | command | 45 | No frontmatter |
| plugins/experiment-tracker/commands/compare.md | command | 45 | No frontmatter |
| plugins/release-manager/commands/release.md | command | 45 | No frontmatter |
| plugins/release-manager/commands/bump-version.md | command | 45 | No frontmatter |
| plugins/docker-helper/commands/build-image.md | command | 45 | No frontmatter |
| plugins/docker-helper/commands/optimize-dockerfile.md | command | 45 | No frontmatter |
| plugins/code-guardian/commands/review.md | command | 45 | No frontmatter |
| plugins/code-guardian/commands/security-scan.md | command | 45 | No frontmatter |
| plugins/test-results-analyzer/commands/analyze-failures.md | command | 45 | No frontmatter |
| plugins/commit-commands/commands/amend.md | command | 45 | No frontmatter |
| plugins/commit-commands/commands/commit-push.md | command | 45 | No frontmatter |
| plugins/product-shipper/commands/ship.md | command | 45 | No frontmatter |
| agents/specialized-domains/embedded-systems.md | agent | 85 | No example blocks |
| agents/specialized-domains/geospatial-engineer.md | agent | 85 | No example blocks |
| agents/specialized-domains/blockchain-developer.md | agent | 85 | No example blocks |
| agents/specialized-domains/game-developer.md | agent | 85 | No example blocks |
| agents/specialized-domains/seo-specialist.md | agent | 85 | No example blocks |
| agents/specialized-domains/real-estate-tech.md | agent | 85 | No example blocks |
| agents/specialized-domains/e-commerce-engineer.md | agent | 85 | No example blocks |
| agents/specialized-domains/voice-assistant.md | agent | 85 | No example blocks |
| agents/specialized-domains/healthcare-engineer.md | agent | 85 | No example blocks |
| agents/specialized-domains/robotics-engineer.md | agent | 85 | No example blocks |
| agents/specialized-domains/education-tech.md | agent | 85 | No example blocks |
| agents/specialized-domains/media-streaming.md | agent | 85 | No example blocks |
| agents/specialized-domains/payment-integration.md | agent | 85 | No example blocks |
| agents/specialized-domains/fintech-engineer.md | agent | 85 | No example blocks |
| agents/specialized-domains/iot-engineer.md | agent | 85 | No example blocks |
| agents/developer-experience/api-documentation.md | agent | 85 | No example blocks |
| plugins/code-guardian/agents/reviewer.md | agent | 85 | No example blocks |
| plugins/api-architect/agents/api-expert.md | agent | 85 | No example blocks |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks config | hooks/hooks.json (25 hook entries) |
| Hook scripts (JS) | hooks/scripts/*.js (19 files) |
| Hook scripts (Python) | hooks/scripts/smart-approve.py (1 file) |
| MCP configs | None found |
| Package manifests | None found (no package.json at root) |
| Requirements | None found |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | hooks/scripts/auto-test.js, post-edit-check.js, lint-fix.js | 5 | Subprocess with file path from input | `file_path` from hook input is passed as an argument to `execFileSync`. Uses array args (no shell injection), but a crafted filename could influence test path discovery. Risk is low in practice since `execFileSync` does not invoke a shell. |
| 2 | Medium | hooks/scripts/session-start.js, session-end.js, learning-log.js, suggest-compact.js, notification-log.js, pre-compact.js | various | File writes outside repo | These scripts write to `~/.claude/` (session-context.json, compact-log.json, learnings/, notification-log.json). Writes are outside the project directory. Intentional by design, but any hook-input injection could influence log contents stored in the user's home directory. |
| 3 | Medium | Multiple command files (review-pr, approve-pr, fix-comments, bisect) | N/A | User args passed to Bash | Commands instruct Claude to run `gh pr view <number>` / `git bisect` with user-supplied arguments without explicit sanitization guidance. Since these pass through Claude's Bash tool (not raw shell), injection risk is low, but the commands provide no sanitization guidance for adversarial inputs. |
| 4 | Low | hooks/scripts/block-dev-server.js | 27–28 | Environment variable dependency | Security decision (allow/block dev server) based on `process.env.TMUX` and `process.env.STY`. Environment variables can be set by parent processes; a process running with TMUX set but not actually inside tmux would bypass the guard. |
| 5 | Low | hooks/hooks.json | 1–146 | Broad hook trigger surface | 25 hook entries fire on every Write, Edit, and Bash invocation. Each additional hook script is an additional attack surface. If any hook script is compromised or has a bug, it fires on every Claude tool use. Recommend auditing hook scripts after any contributor change. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | All 82 command files (see list below) | Missing YAML frontmatter `name:` field | Plugin registry cannot parse the canonical command name; falls back to filename inference which may differ from intended name |
| 2 | All 82 command files | Missing YAML frontmatter `description:` field | Plugin marketplace and `/help` output show no description; discoverability is broken |

**Affected command files (82):** plugins/readme-generator/commands/generate-readme.md, plugins/technical-sales/commands/write-proposal.md, plugins/technical-sales/commands/create-demo.md, plugins/devops-automator/commands/health-check.md, plugins/devops-automator/commands/automate.md, plugins/fix-pr/commands/fix-comments.md, plugins/openapi-expert/commands/validate-spec.md, plugins/openapi-expert/commands/generate-spec.md, plugins/visual-regression/commands/capture-baseline.md, plugins/visual-regression/commands/compare.md, plugins/dependency-manager/commands/update-deps.md, plugins/dependency-manager/commands/audit-deps.md, plugins/bundle-analyzer/commands/tree-shake.md, plugins/bundle-analyzer/commands/analyze-bundle.md, plugins/license-checker/commands/generate-notice.md, plugins/license-checker/commands/check-licenses.md, plugins/security-guidance/commands/security-check.md, plugins/security-guidance/commands/fix-vulnerability.md, plugins/performance-monitor/commands/profile-api.md, plugins/performance-monitor/commands/benchmark.md, plugins/flutter-mobile/commands/platform-channel.md, plugins/flutter-mobile/commands/create-widget.md, plugins/migrate-tool/commands/code-migrate.md, plugins/migrate-tool/commands/db-migrate.md, plugins/changelog-gen/commands/generate-changelog.md, plugins/smart-commit/commands/commit.md, plugins/smart-commit/commands/changelog.md, plugins/react-native-dev/commands/native-module.md, plugins/react-native-dev/commands/create-screen.md, plugins/helm-charts/commands/create-chart.md, plugins/helm-charts/commands/upgrade-chart.md, plugins/analytics-reporter/commands/report.md, plugins/analytics-reporter/commands/dashboard.md, plugins/unit-test-generator/commands/generate-tests.md, plugins/gcp-helper/commands/configure-gcs.md, plugins/gcp-helper/commands/setup-cloud-run.md, plugins/accessibility-checker/commands/a11y-scan.md, plugins/accessibility-checker/commands/aria-fix.md, plugins/rag-builder/commands/index-docs.md, plugins/rag-builder/commands/create-retriever.md, plugins/python-expert/commands/refactor-py.md, plugins/python-expert/commands/type-hints.md, plugins/experiment-tracker/commands/track.md, plugins/experiment-tracker/commands/compare.md, plugins/ci-debugger/commands/fix-pipeline.md, plugins/ci-debugger/commands/analyze-ci-failure.md, plugins/pr-reviewer/commands/review-pr.md, plugins/pr-reviewer/commands/approve-pr.md, plugins/release-manager/commands/release.md, plugins/release-manager/commands/bump-version.md, plugins/docker-helper/commands/build-image.md, plugins/docker-helper/commands/optimize-dockerfile.md, plugins/code-guardian/commands/review.md, plugins/code-guardian/commands/security-scan.md, plugins/github-issue-manager/commands/create-issue.md, plugins/github-issue-manager/commands/triage-issues.md, plugins/debug-session/commands/bisect.md, plugins/debug-session/commands/debug.md, plugins/model-context-protocol/commands/create-server.md, plugins/model-context-protocol/commands/add-tool.md, plugins/ai-prompt-lab/commands/test-prompt.md, plugins/ai-prompt-lab/commands/improve-prompt.md, plugins/mutation-tester/commands/mutate.md, plugins/infrastructure-maintainer/commands/audit-infra.md, plugins/infrastructure-maintainer/commands/update-infra.md, plugins/update-branch/commands/rebase.md, plugins/screen-reader-tester/commands/test-sr.md, plugins/screen-reader-tester/commands/fix-aria.md, plugins/workflow-optimizer/commands/suggest-improvements.md, plugins/workflow-optimizer/commands/analyze-workflow.md, plugins/test-results-analyzer/commands/analyze-failures.md, plugins/context7-docs/commands/fetch-docs.md, plugins/commit-commands/commands/amend.md, plugins/commit-commands/commands/commit-push.md, plugins/test-writer/commands/unit-test.md, plugins/test-writer/commands/integration-test.md, plugins/slack-notifier/commands/send-update.md, plugins/slack-notifier/commands/create-thread.md, plugins/seed-generator/commands/generate-seeds.md, plugins/azure-helper/commands/setup-functions.md, plugins/azure-helper/commands/configure-blob.md, plugins/product-shipper/commands/ship.md

**Suggested fix (applies to all 82):** Add YAML frontmatter block at the top of each command file. Example for `generate-readme.md`:
```yaml
---
name: generate-readme
description: Generate a comprehensive README.md from project analysis
---
```

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | hooks/scripts/auto-test.js, post-edit-check.js, lint-fix.js | file_path from input passed to subprocess | Add path validation: confirm filePath is within `process.cwd()` before using it. Example: `if (!path.resolve(filePath).startsWith(process.cwd())) process.exit(0);` |
| 2 | hooks/scripts/block-dev-server.js | TMUX env var check is spoofable | Add secondary check: verify tmux socket existence via `fs.existsSync(process.env.TMUX)` or run `tmux ls` via `execFileSync`. |
| 3 | Multiple command files | No sanitization guidance for user-supplied PR numbers | Add a Rules entry: "Validate that PR numbers are numeric before constructing shell commands." |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | All 18 agent files | Zero example blocks — agents must include at least one input/output example to show expected behavior | -15 each (18 agents × -15 = -270 total) |
| 2 | All 82 command files | No `allowed-tools` declared in frontmatter — commands should declare which Claude tools they use | -5 each (82 × -5 = -410 total) |
| 3 | plugins/helm-charts/commands/upgrade-chart.md | No output format section AND no empty-input handling for required `release-name` argument | -10 format, -10 empty = -20 |
| 4 | plugins/technical-sales/commands/write-proposal.md, create-demo.md; plugins/devops-automator/commands/health-check.md, automate.md; plugins/fix-pr/commands/fix-comments.md; plugins/openapi-expert/commands/validate-spec.md; plugins/security-guidance/commands/fix-vulnerability.md; plugins/performance-monitor/commands/profile-api.md, benchmark.md; plugins/flutter-mobile/commands/platform-channel.md, create-widget.md; plugins/migrate-tool/commands/code-migrate.md, db-migrate.md; plugins/react-native-dev/commands/native-module.md, create-screen.md; plugins/unit-test-generator/commands/generate-tests.md; plugins/python-expert/commands/refactor-py.md, type-hints.md; plugins/experiment-tracker/commands/track.md; plugins/pr-reviewer/commands/review-pr.md, approve-pr.md; plugins/debug-session/commands/bisect.md, debug.md; plugins/model-context-protocol/commands/create-server.md, add-tool.md; plugins/ai-prompt-lab/commands/test-prompt.md, improve-prompt.md; plugins/infrastructure-maintainer/commands/update-infra.md; plugins/workflow-optimizer/commands/suggest-improvements.md; plugins/context7-docs/commands/fetch-docs.md; plugins/test-writer/commands/unit-test.md, integration-test.md (32 commands) | Commands require user-supplied arguments but do not handle the empty-input case (no argument provided) | -10 each |
| 5 | plugins/readme-generator/commands/generate-readme.md; plugins/visual-regression/commands/capture-baseline.md, compare.md; plugins/bundle-analyzer/commands/tree-shake.md, analyze-bundle.md; plugins/license-checker/commands/generate-notice.md, check-licenses.md; plugins/helm-charts/commands/create-chart.md; plugins/seed-generator/commands/generate-seeds.md; plugins/gcp-helper/commands/configure-gcs.md, setup-cloud-run.md; plugins/rag-builder/commands/index-docs.md, create-retriever.md; plugins/ci-debugger/commands/fix-pipeline.md, analyze-ci-failure.md; plugins/github-issue-manager/commands/triage-issues.md; plugins/mutation-tester/commands/mutate.md; plugins/screen-reader-tester/commands/test-sr.md, fix-aria.md; plugins/github-issue-manager/commands/create-issue.md; plugins/slack-notifier/commands/send-update.md, create-thread.md; plugins/azure-helper/commands/setup-functions.md, configure-blob.md (24 commands) | Missing `## Format` output section — no canonical output structure defined | -10 each |
| 6 | plugins/technical-sales/commands/write-proposal.md, create-demo.md; plugins/devops-automator/commands/health-check.md, automate.md; plugins/fix-pr/commands/fix-comments.md; plugins/openapi-expert/commands/validate-spec.md; plugins/flutter-mobile/commands/platform-channel.md, create-widget.md; plugins/react-native-dev/commands/native-module.md, create-screen.md; plugins/model-context-protocol/commands/create-server.md, add-tool.md; plugins/experiment-tracker/commands/track.md, compare.md; plugins/infrastructure-maintainer/commands/audit-infra.md, update-infra.md; plugins/debug-session/commands/bisect.md, debug.md; plugins/release-manager/commands/release.md, bump-version.md; plugins/workflow-optimizer/commands/suggest-improvements.md, analyze-workflow.md; plugins/commit-commands/commands/amend.md; plugins/product-shipper/commands/ship.md (24 commands) | Step bodies are skeletal — numbered steps contain only a category label ending in `:` with no action content, making them non-executable instructions | Informational, no direct penalty in rubric but degrades runtime usefulness |

## Cross-Component

**Inconsistent command format style:** The 82 command files use three different opening conventions: (a) H1 heading `# /plugin:command - Title`, (b) H1 heading without plugin prefix `# /command - Title`, and (c) plain prose. No consistent convention is enforced.

**Agent examples gap:** All 18 agents follow the same high-quality structure (10-step Process, Technical Standards, Verification) but uniformly omit example blocks. Adding examples to one agent would serve as a template for the rest.

**Hook script vs command alignment:** The `code-guardian/commands/security-scan.md` command instructs a full OWASP scan, while `hooks/scripts/secret-scanner.js` already runs on every Write/Edit. The two are complementary but not cross-referenced; the command should note that the hook provides continuous scanning between explicit invocations.

**Plugin naming collision risk:** Two separate plugins define an `aria-fix` command: `plugins/accessibility-checker/commands/aria-fix.md` and `plugins/screen-reader-tester/commands/fix-aria.md`. Without frontmatter `name:` fields, the registry must infer from filenames. Different filenames avoid collision, but the descriptions overlap significantly — consider merging or clearly differentiating scope.

**No orphaned agents detected.** All plugin agents (reviewer.md, api-expert.md) are referenced by their respective plugin structures.

## Recommendation

CLEAR — submit PRs for all bugs and medium/low security fixes.

**Priority order:**

1. **High-value PR:** Add YAML frontmatter (`name`, `description`, `allowed-tools`) to all 82 command files. This is a single systemic fix that eliminates 164 bugs and 82 quality issues in one PR. Use a script to auto-generate frontmatter from H1 headings and first-paragraph descriptions where present.

2. **Medium PR:** Add at least one example block to each of the 18 agent files. The agents are otherwise high quality (10-step process, standards, verification) — examples are the only missing element.

3. **Low PR (security/medium):** Add path validation guard (`startsWith(cwd)`) to the three hook scripts that pass `file_path` to subprocesses. Two-line fix per file.

4. **Low PR:** Add `## Format` sections to the 24 commands missing them, and add empty-input handling guidance to the 32 commands requiring user-supplied arguments.

**NL Score breakdown:**
- 18 agents: avg 85/100 (well-structured, strong domain coverage, only flaw is no examples)
- 82 commands: avg 37/100 (dragged down entirely by missing frontmatter; content quality is generally good)
- Weighted average: **46/100** (below the default 70 threshold — frontmatter fix alone would raise this to ~62/100)
