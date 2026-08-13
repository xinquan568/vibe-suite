# NLPM Audit: affaan-m/everything-claude-code
**Date**: 2026-04-06  |  **Artifacts**: 934  |  **Strategy**: progressive
**NL Score**: 84/100
**Security**: BLOCKED
**Bugs**: 24  |  **Quality Issues**: 187  |  **Security Findings**: 7

---

## NL Score Summary

Scores computed from a progressive sample of ~320 unique artifacts; localized variants follow their source file's pattern. Files sorted ascending by score.

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/test-coverage.md | command | 23 | Missing name + description frontmatter |
| commands/gan-build.md | command | 25 | Missing name + description frontmatter; references undefined agents |
| commands/learn.md | command | 29 | Missing name + description frontmatter |
| commands/update-docs.md | command | 27 | Missing name + description frontmatter |
| commands/model-route.md | command | 27 | Missing name + description frontmatter |
| commands/multi-execute.md | command | 33 | Missing name + description frontmatter; undefined variables |
| docs/ko-KR/commands/learn.md | command | 50 | Missing name + description frontmatter |
| docs/ko-KR/commands/eval.md | command | 50 | Missing name + description frontmatter |
| docs/zh-TW/commands/learn.md | command | 50 | Missing name + description frontmatter |
| docs/zh-TW/commands/eval.md | command | 50 | Missing name + description frontmatter |
| docs/pt-BR/commands/learn.md | command | 50 | Missing name + description frontmatter |
| docs/pt-BR/commands/eval.md | command | 50 | Missing name + description frontmatter |
| docs/zh-CN/commands/eval.md | command | 55 | Missing name + description frontmatter |
| docs/tr/commands/eval.md | command | 55 | Missing name + description frontmatter |
| docs/ja-JP/commands/eval.md | command | 55 | Missing name + description frontmatter |
| skills/customs-trade-compliance/SKILL.md | skill | 55 | Vague quantifiers capped + missing output format |
| commands/review-pr.md | command | 44 | Missing name; no allowed-tools; missing output format |
| commands/tdd.md | command | 48 | Missing name; no allowed-tools; no empty input handling |
| commands/eval.md | command | 50 | Missing name; no allowed-tools; no output format |
| commands/docs.md | command | 50 | Missing name; no allowed-tools; no output format |
| commands/kotlin-test.md | command | 50 | Missing name; no allowed-tools; no empty input handling |
| commands/devfleet.md | command | 50 | Missing name; no allowed-tools; no output format |
| commands/setup-pm.md | command | 60 | Missing name; no allowed-tools |
| commands/aside.md | command | 60 | Missing name; no allowed-tools |
| commands/gan-design.md | command | 60 | Missing name + description; no allowed-tools |
| commands/loop-status.md | command | 60 | Missing name + description; minimal content |
| commands/orchestrate.md | command | 55 | Missing name; multi-step without numbering |
| commands/kotlin-build.md | command | 56 | Missing name; no allowed-tools; no empty input handling |
| docs/tr/commands/e2e.md | command | 60 | Missing frontmatter; no allowed-tools; vague quantifiers |
| docs/ja-JP/commands/e2e.md | command | 60 | Missing frontmatter; no allowed-tools; vague quantifiers |
| docs/zh-CN/commands/e2e.md | command | 58 | Missing frontmatter; no allowed-tools; vague quantifiers |
| docs/zh-CN/commands/orchestrate.md | command | 65 | Missing frontmatter; incomplete sections |
| docs/tr/commands/orchestrate.md | command | 68 | Missing frontmatter; vague quantifiers |
| docs/ja-JP/commands/orchestrate.md | command | 68 | Missing frontmatter; vague quantifiers |
| commands/multi-frontend.md | command | 65 | Missing frontmatter; no numbered steps |
| commands/multi-backend.md | command | 65 | Missing frontmatter; no numbered steps |
| commands/multi-workflow.md | command | 65 | Missing frontmatter; vague quantifiers |
| commands/santa-loop.md | command | 65 | Multi-step without numbering; vague quantifiers |
| docs/tr/commands/plan.md | command | 70 | Missing allowed-tools; no empty input handling |
| docs/tr/commands/tdd.md | command | 65 | Missing allowed-tools; no empty input handling |
| docs/ja-JP/commands/tdd.md | command | 65 | Missing allowed-tools; no empty input handling |
| docs/zh-CN/commands/tdd.md | command | 62 | Missing allowed-tools; markdown formatting issues |
| commands/loop-start.md | command | 70 | Missing name + description |
| commands/hookify-help.md | command | 70 | Missing name; minimal content |
| commands/hookify-list.md | command | 70 | Missing name; missing description; minimal content |
| commands/rust-build.md | command | 70 | Missing name; no output format; no empty input handling |
| docs/tr/commands/code-review.md | command | 70 | Missing frontmatter; no numbered steps |
| docs/ja-JP/commands/code-review.md | command | 70 | Missing frontmatter; no numbered steps |
| docs/zh-CN/commands/code-review.md | command | 70 | Missing frontmatter; no numbered steps |
| .kiro/agents/loop-operator.md | agent | 70 | Missing model; critically sparse content |
| docs/zh-CN/agents/loop-operator.md | agent | 70 | Underdocumented; no examples; vague |
| docs/tr/agents/harness-optimizer.md | agent | 70 | Missing description; no examples; no output format |
| commands/python-review.md | command | 75 | Missing name; no output format; no allowed-tools |
| commands/plan.md | command | 54 | Missing name; no allowed-tools; no empty input handling |
| commands/prune.md | command | 75 | Missing output format; no empty input handling |
| commands/context-budget.md | command | 75 | Legacy shim; missing allowed-tools |
| commands/prp-prd.md | command | 75 | Multi-step without numbering; 4 vague quantifiers |
| commands/sessions.md | command | 75 | Missing name; complex subcommand structure |
| commands/promote.md | command | 75 | Missing allowed-tools; no output format; brief |
| commands/feature-dev.md | command | 75 | Seven-phase workflow without numbering |
| commands/build-fix.md | command | 75 | Missing frontmatter; no output format |
| commands/go-build.md | command | 75 | Multi-step without numbering; missing output format |
| docs/ko-KR/commands/code-review.md | command | 75 | Missing name |
| docs/ko-KR/commands/refactor-clean.md | command | 75 | Missing allowed-tools; no empty input handling |
| docs/zh-TW/commands/code-review.md | command | 75 | Missing name |
| docs/pt-BR/commands/code-review.md | command | 75 | Missing name |
| .kiro/agents/harness-optimizer.md | agent | 75 | Weak description; insufficient guidance; missing model |
| docs/zh-CN/agents/chief-of-staff.md | agent | 75 | Complex workflow; vague quantifiers capped |
| docs/zh-CN/agents/harness-optimizer.md | agent | 75 | Incomplete framework guidance |
| docs/tr/agents/loop-operator.md | agent | 75 | Missing description; no examples |
| skills/dart-flutter-patterns/SKILL.md | skill | 84 | Excessive "appropriate" usage (8 instances) |
| skills/flutter-dart-code-review/SKILL.md | skill | 80 | Heavy vague quantifiers capped at -20 |
| skills/inventory-demand-planning/SKILL.md | skill | 85 | 8 vague quantifiers (reasonable, proper, suitable…) |
| agents/e2e-runner.md | agent | 67 | Missing output format; vague quantifiers capped |
| agents/security-reviewer.md | agent | 71 | Missing output format; vague quantifiers |
| agents/refactor-cleaner.md | agent | 73 | Missing output format; vague quantifiers |
| agents/opensource-sanitizer.md | agent | 75 | Vague quantifiers capped; one example only |
| skills/ralphinho-rfc-pipeline/SKILL.md | skill | 50 | Missing name + description frontmatter |
| skills/continuous-agent-loop/SKILL.md | skill | 70 | Missing name frontmatter; abbreviated documentation |
| agents/code-simplifier.md | agent | 75 | Missing examples; missing output format |
| agents/loop-operator.md | agent | 75 | Missing examples; missing output format |
| agents/gan-planner.md | agent | 77 | Zero examples |
| commands/skill-health.md | command | 77 | No empty input handling; 4 vague quantifiers |
| agents/silent-failure-hunter.md | agent | 79 | Zero examples; too brief |
| agents/java-reviewer.md | agent | 79 | One example; 8 vague quantifiers |
| agents/go-reviewer.md | agent | 79 | Zero examples; vague quantifiers |
| docs/ko-KR/agents/code-reviewer.md | agent | 75 | Missing model; no examples; minimal structure |
| docs/ko-KR/agents/architect.md | agent | 80 | Missing model; no examples |
| docs/ko-KR/agents/planner.md | agent | 80 | Missing model; minimal structure |
| docs/ko-KR/agents/go-reviewer.md | agent | 80 | Missing name + description; missing model |
| agents/opensource-forker.md | agent | 80 | Vague quantifiers; Write/Edit without read-only safeguards |
| agents/comment-analyzer.md | agent | 80 | Zero examples; vague output format |
| agents/gan-evaluator.md | agent | 80 | 10+ vague quantifiers; Playwright tool used but not declared |
| docs/zh-CN/agents/planner.md | agent | 80 | Weak examples; vague quantifiers |
| docs/zh-CN/agents/docs-lookup.md | agent | 80 | MCP integration complexity; missing examples |
| docs/zh-CN/agents/kotlin-reviewer.md | agent | 80 | 10 vague quantifiers capped |
| docs/tr/agents/chief-of-staff.md | agent | 80 | Vague quantifiers capped; vague workflow |
| docs/tr/agents/docs-lookup.md | agent | 80 | Vague quantifiers capped; missing output format |
| docs/tr/agents/flutter-reviewer.md | agent | 80 | Vague quantifiers capped |
| docs/zh-CN/agents/chief-of-staff.md | agent | 75 | Complex workflow; vague quantifiers |
| agents/csharp-reviewer.md | agent | 83 | Zero examples |
| agents/cpp-reviewer.md | agent | 83 | Zero examples |
| agents/opensource-packager.md | agent | 83 | 6 vague quantifiers; sparse examples |
| commands/evolve.md | command | 79 | No empty input handling; vague "high-confidence" |
| commands/prune.md | command | 75 | Missing output format; no empty input handling |
| commands/hookify-configure.md | command | 80 | Multi-step without numbering; missing output format |
| commands/learn-eval.md | command | 80 | Multi-step quality gate without numbering |
| commands/rust-test.md | command | 80 | Missing description; missing output format |
| commands/save-session.md | command | 80 | Output format scattered; no numbered steps |
| commands/hookify.md | command | 80 | No numbered steps; missing output format |
| commands/verify.md | command | 80 | Legacy shim; vague delegation |
| commands/update-codemaps.md | command | 80 | No frontmatter; 5-step process not numbered |
| commands/multi-plan.md | command | 80 | Missing allowed-tools; 3 vague quantifiers |
| commands/prp-plan.md | command | 80 | 5 vague quantifiers |
| commands/jira.md | command | 80 | Missing name; 3 vague quantifiers |
| commands/code-review.md | command | 80 | Missing name; 4 vague quantifiers |
| docs/.claude/commands/database-migration.md | command | 80 | Multi-step without numbering; 3 vague quantifiers |
| docs/.claude/commands/add-language-rules.md | command | 80 | Multi-step without numbering; 4 vague quantifiers |
| docs/.claude/commands/feature-development.md | command | 80 | Multi-step without numbering; 4 vague quantifiers |
| docs/ko-KR/commands/test-coverage.md | command | 80 | No empty input handling; missing output format |
| docs/ko-KR/commands/build-fix.md | command | 80 | No empty input handling; missing output format |
| docs/zh-TW/commands/test-coverage.md | command | 80 | No empty input handling; missing output format |
| docs/zh-TW/commands/build-fix.md | command | 80 | No empty input handling; missing output format |
| docs/pt-BR/commands/test-coverage.md | command | 80 | No empty input handling; missing output format |
| docs/pt-BR/commands/build-fix.md | command | 80 | No empty input handling; missing output format |
| .kiro/agents/chief-of-staff.md | agent | 85 | Missing model; complex without examples |
| .kiro/agents/code-reviewer.md | agent | 88 | Missing model; 2 vague quantifiers |
| .kiro/agents/tdd-guide.md | agent | 88 | Missing model; no code examples |
| .kiro/agents/architect.md | agent | 88 | Missing model; 1 vague quantifier |
| .kiro/agents/security-reviewer.md | agent | 88 | Non-standard "allowedTools" field; missing model |
| docs/ko-KR/agents/security-reviewer.md | agent | 88 | Missing model; Write/Edit on read-only agent |
| docs/ko-KR/agents/e2e-runner.md | agent | 88 | Missing model; no examples |
| docs/ko-KR/agents/refactor-cleaner.md | agent | 88 | Missing model |
| docs/ko-KR/agents/tdd-guide.md | agent | 88 | Missing model |
| docs/ko-KR/agents/build-error-resolver.md | agent | 88 | Missing model |
| docs/ko-KR/agents/database-reviewer.md | agent | 88 | Missing model |
| docs/ko-KR/agents/go-build-resolver.md | agent | 88 | Missing model |
| docs/pt-BR/agents/security-reviewer.md | agent | 88 | Missing model |
| docs/pt-BR/agents/e2e-runner.md | agent | 88 | Missing model |
| docs/pt-BR/agents/refactor-cleaner.md | agent | 88 | Missing model |
| docs/pt-BR/agents/go-reviewer.md | agent | 88 | Missing model |
| docs/pt-BR/agents/doc-updater.md | agent | 88 | Missing model |
| docs/pt-BR/agents/go-build-resolver.md | agent | 88 | Missing model |
| docs/pt-BR/agents/planner.md | agent | 88 | Missing model |
| docs/pt-BR/agents/tdd-guide.md | agent | 88 | Missing model |
| docs/pt-BR/agents/architect.md | agent | 88 | Missing model |
| docs/pt-BR/agents/build-error-resolver.md | agent | 88 | Missing model |
| docs/pt-BR/agents/code-reviewer.md | agent | 88 | Missing model |
| docs/pt-BR/agents/database-reviewer.md | agent | 88 | Missing model |
| docs/ja-JP/skills/continuous-learning-v2/agents/observer.md | agent | 80 | Missing description frontmatter; vague quantifiers capped |
| agents/harness-optimizer.md | agent | 81 | Zero examples; extremely brief |
| commands/projects.md | command | 85 | Missing allowed-tools; no empty input handling |
| commands/instinct-status.md | command | 85 | Missing allowed-tools; no empty input handling |
| commands/kotlin-review.md | command | 85 | Multi-step without numbering; missing allowed-tools |
| commands/checkpoint.md | command | 85 | Multi-step without numbering; missing allowed-tools |
| commands/refactor-clean.md | command | 85 | 6-step labeled but not numbered; missing allowed-tools |
| commands/instinct-export.md | command | 85 | Multi-step without numbering |
| commands/prp-commit.md | command | 85 | Missing allowed-tools; no output format |
| commands/gradle-build.md | command | 85 | Missing allowed-tools; 2 vague quantifiers |
| commands/go-review.md | command | 85 | Missing name; 3 vague quantifiers |
| commands/prp-pr.md | command | 85 | Missing name; 2 vague quantifiers |
| commands/rust-review.md | command | 85 | Missing name; 2 vague quantifiers |
| commands/flutter-review.md | command | 85 | Missing name; 3 vague quantifiers |
| commands/flutter-test.md | command | 85 | Missing name; 2 vague quantifiers |
| commands/prp-implement.md | command | 85 | Missing name; 2 vague quantifiers |
| commands/cpp-review.md | command | 85 | Missing name; 3 vague quantifiers |
| agents/doc-updater.md | agent | 85 | One example; 5 vague quantifiers |
| agents/python-reviewer.md | agent | 85 | One example; 5 vague quantifiers |
| agents/performance-optimizer.md | agent | 85 | Missing output format; Write/Edit without guidance |
| agents/seo-specialist.md | agent | 85 | Output format informal; missing model declared |
| agents/code-architect.md | agent | 85 | Output format template-only; no examples |
| agents/conversation-analyzer.md | agent | 85 | Missing output narrative; YAML template only |
| agents/pr-test-analyzer.md | agent | 85 | Sparse output format |
| agents/database-reviewer.md | agent | 85 | Write/Edit without clear policy; missing output format |
| agents/code-explorer.md | agent | 85 | Zero examples |
| agents/cpp-build-resolver.md | agent | 85 | Zero examples |
| agents/type-design-analyzer.md | agent | 85 | Zero examples; file appears truncated |
| docs/zh-CN/agents/go-build-resolver.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/cpp-build-resolver.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/pytorch-build-resolver.md | agent | 85 | 3 vague quantifiers; 1 example |
| docs/zh-CN/agents/kotlin-build-resolver.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/flutter-reviewer.md | agent | 85 | 3 vague quantifiers; heavy verbosity |
| docs/zh-CN/agents/architect.md | agent | 85 | 3 vague quantifiers; 1 example |
| docs/zh-CN/agents/build-error-resolver.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/code-reviewer.md | agent | 85 | 3 vague quantifiers; 1 example |
| docs/zh-CN/agents/rust-build-resolver.md | agent | 85 | 3 vague quantifiers; 1 example |
| docs/zh-CN/agents/java-build-resolver.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/security-reviewer.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/e2e-runner.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/refactor-cleaner.md | agent | 85 | 1 vague quantifier; no examples |
| docs/zh-CN/agents/java-reviewer.md | agent | 85 | 2 vague quantifiers; 1 example |
| docs/zh-CN/agents/go-reviewer.md | agent | 90 | 1 vague quantifier; no examples |
| docs/zh-CN/agents/doc-updater.md | agent | 85 | 3 vague quantifiers; 1 example |
| docs/tr/agents/java-build-resolver.md | agent | 85 | One example only; no output format |
| docs/tr/agents/security-reviewer.md | agent | 85 | Long; inconsistent structure; vague quantifiers |
| docs/tr/agents/e2e-runner.md | agent | 85 | One example; missing output format |
| docs/tr/agents/refactor-cleaner.md | agent | 85 | One example; missing output format |
| docs/tr/agents/java-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/go-reviewer.md | agent | 85 | One example; vague terms |
| docs/tr/agents/doc-updater.md | agent | 85 | One example; vague terms |
| docs/tr/agents/python-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/kotlin-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/cpp-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/go-build-resolver.md | agent | 85 | One example; missing output format |
| docs/tr/agents/cpp-build-resolver.md | agent | 85 | One example; missing output format |
| docs/tr/agents/planner.md | agent | 85 | One example; missing output format |
| docs/tr/agents/tdd-guide.md | agent | 85 | One example; missing output format |
| docs/tr/agents/pytorch-build-resolver.md | agent | 85 | One example; missing output format |
| docs/tr/agents/kotlin-build-resolver.md | agent | 85 | One example; missing output format |
| docs/tr/agents/typescript-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/architect.md | agent | 85 | One example; missing output format |
| docs/tr/agents/build-error-resolver.md | agent | 85 | One example; missing output format |
| docs/tr/agents/rust-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/code-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/database-reviewer.md | agent | 85 | One example; missing output format |
| docs/tr/agents/rust-build-resolver.md | agent | 85 | One example; missing output format |
| docs/ja-JP/agents/security-reviewer.md | agent | 85 | One detailed example; model opus; missing output format |
| docs/ja-JP/agents/e2e-runner.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/refactor-cleaner.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/go-reviewer.md | agent | 85 | One example; missing output format |
| docs/ja-JP/agents/doc-updater.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/python-reviewer.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/go-build-resolver.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/planner.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/tdd-guide.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/architect.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/build-error-resolver.md | agent | 85 | One detailed example; missing output format |
| docs/ja-JP/agents/code-reviewer.md | agent | 85 | One example; missing output format |
| docs/ja-JP/agents/database-reviewer.md | agent | 85 | One detailed example; missing output format |
| docs/ko-KR/agents/doc-updater.md | agent | 85 | Missing model; one example |
| skills/brand-voice/SKILL.md | skill | 88 | 6 vague quantifiers |
| skills/api-design/SKILL.md | skill | 88 | 6 vague quantifiers (appropriate, proper) |
| skills/social-graph-ranker/SKILL.md | skill | 90 | Missing explicit output format section |
| skills/agentic-engineering/SKILL.md | skill | 85 | Multiple vague quantifiers; missing output format |
| skills/enterprise-agent-ops/SKILL.md | skill | 85 | Multiple vague quantifiers; missing output format |
| skills/lead-intelligence/SKILL.md | skill | 90 | 6 vague quantifiers |
| agents/gan-generator.md | agent | 90 | 5 vague quantifiers |
| agents/architect.md | agent | 90 | Zero examples |
| agents/build-error-resolver.md | agent | 90 | Missing output format detail |
| agents/rust-build-resolver.md | agent | 90 | Write/Edit without read-only safeguards noted |
| docs/zh-CN/agents/tdd-guide.md | agent | 90 | 2 vague quantifiers |
| docs/zh-CN/agents/cpp-reviewer.md | agent | 90 | Missing output format section |
| docs/zh-CN/agents/typescript-reviewer.md | agent | 90 | 2 vague quantifiers |
| docs/zh-CN/agents/rust-reviewer.md | agent | 90 | 1 vague quantifier |
| docs/zh-CN/agents/database-reviewer.md | agent | 90 | 1 vague quantifier |
| docs/zh-CN/agents/go-reviewer.md | agent | 90 | 1 vague quantifier |
| docs/zh-TW/agents/security-reviewer.md | agent | 90 | Vague quantifiers; Chinese language |
| docs/zh-TW/agents/e2e-runner.md | agent | 90 | Vague quantifiers; Chinese language |
| docs/zh-TW/agents/refactor-cleaner.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/go-reviewer.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/doc-updater.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/go-build-resolver.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/planner.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/tdd-guide.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/architect.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/build-error-resolver.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/database-reviewer.md | agent | 90 | Vague quantifiers |
| docs/zh-TW/agents/code-reviewer.md | agent | 85 | Missing structured content |
| skills/continuous-learning-v2/agents/observer.md | agent | 90 | Zero examples; 1 vague quantifier |
| docs/zh-CN/skills/continuous-learning-v2/agents/observer.md | agent | 90 | Zero examples; 1 vague quantifier |
| .kiro/agents/e2e-runner.md | agent | 90 | Missing model; 1 vague quantifier |
| .kiro/agents/doc-updater.md | agent | 90 | Missing model; 1 vague quantifier |
| .kiro/agents/planner.md | agent | 90 | Missing model; 1 vague quantifier |
| .kiro/agents/database-reviewer.md | agent | 90 | Missing model; 1 vague quantifier |
| .kiro/agents/build-error-resolver.md | agent | 93 | Missing model; 1 vague quantifier |
| .kiro/agents/refactor-cleaner.md | agent | 93 | Missing model; 1 vague quantifier |
| .kiro/agents/go-reviewer.md | agent | 93 | Missing model; 1 vague quantifier |
| .kiro/agents/python-reviewer.md | agent | 93 | Missing model; 1 vague quantifier |
| commands/quality-gate.md | command | 85 | Missing allowed-tools; missing output format |
| commands/claw.md | command | 85 | Legacy shim; missing allowed-tools |
| commands/harness-audit.md | command | 90 | Missing allowed-tools |
| commands/pm2.md | command | 90 | Missing allowed-tools; no name field |
| commands/resume-session.md | command | 90 | Missing allowed-tools; excellent otherwise |
| commands/go-test.md | command | 90 | Missing allowed-tools; 2 vague quantifiers |
| commands/instinct-import.md | command | 90 | Missing output format |
| commands/prompt-optimize.md | command | 90 | Legacy shim; missing output format |
| commands/cpp-build.md | command | 90 | Missing allowed-tools |
| commands/harness-audit.md | command | 90 | Missing allowed-tools |
| agents/chief-of-staff.md | agent | 94 | 3 vague quantifiers |
| agents/typescript-reviewer.md | agent | 95 | Complete; minor model field inconsistency |
| agents/kotlin-reviewer.md | agent | 95 | 5 vague quantifiers |
| agents/go-build-resolver.md | agent | 95 | Sparse examples in table format |
| agents/planner.md | agent | 95 | 5 vague quantifiers |
| agents/tdd-guide.md | agent | 95 | 4 vague quantifiers |
| agents/flutter-reviewer.md | agent | 95 | Minor vague language |
| agents/rust-reviewer.md | agent | 95 | Comprehensive; minor vague |
| agents/pytorch-build-resolver.md | agent | 95 | Sparse examples |
| agents/kotlin-build-resolver.md | agent | 95 | Sparse examples |
| agents/kotlin-reviewer.md | agent | 95 | 5 vague quantifiers |
| skills/lead-intelligence/agents/outreach-drafter.md | agent | 95 | 1 vague quantifier |
| skills/lead-intelligence/agents/mutual-mapper.md | agent | 95 | 1 vague quantifier |
| commands/skill-create.md | command | 100 | Perfect |
| commands/cpp-test.md | command | 95 | Missing allowed-tools only |
| commands/rules-distill.md | command | 95 | Very minimal legacy shim |
| commands/agent-sort.md | command | 95 | Very minimal legacy shim |
| agents/docs-lookup.md | agent | 96 | 2 vague quantifiers |
| agents/java-build-resolver.md | agent | 95 | One example; minimal penalties |
| agents/dart-build-resolver.md | agent | 98 | 1 vague quantifier |
| skills/lead-intelligence/agents/signal-scorer.md | agent | 98 | 2 vague quantifiers |
| skills/lead-intelligence/agents/enrichment-agent.md | agent | 100 | Perfect |
| skills/everything-claude-code/SKILL.md | skill | 100 | Perfect |
| skills/ck/SKILL.md | skill | 100 | Perfect |
| skills/safety-guard/SKILL.md | skill | 100 | Perfect |
| skills/laravel-verification/SKILL.md | skill | 100 | Perfect |
| skills/codebase-onboarding/SKILL.md | skill | 100 | Perfect |
| skills/llm-trading-agent-security/SKILL.md | skill | 100 | Perfect |
| skills/repo-scan/SKILL.md | skill | 100 | Perfect |
| skills/ai-first-engineering/SKILL.md | skill | 100 | Perfect |
| skills/cpp-testing/SKILL.md | skill | 100 | Perfect |
| skills/clickhouse-io/SKILL.md | skill | 100 | Perfect |
| skills/swift-protocol-di-testing/SKILL.md | skill | 100 | Perfect |
| skills/database-migrations/SKILL.md | skill | 98 | 1 vague quantifier |
| skills/perl-testing/SKILL.md | skill | 98 | 1 vague quantifier |
| skills/search-first/SKILL.md | skill | 98 | 1 vague quantifier |
| skills/crosspost/SKILL.md | skill | 100 | Perfect |
| skills/content-hash-cache-pattern/SKILL.md | skill | 100 | Perfect |
| skills/docker-patterns/SKILL.md | skill | 100 | Perfect |
| skills/claude-api/SKILL.md | skill | 100 | Perfect |
| skills/investor-outreach/SKILL.md | skill | 100 | Perfect |
| skills/deployment-patterns/SKILL.md | skill | 100 | Perfect |
| skills/swiftui-patterns/SKILL.md | skill | 100 | Perfect |
| skills/regex-vs-llm-structured-text/SKILL.md | skill | 100 | Perfect |
| skills/google-workspace-ops/SKILL.md | skill | 100 | Perfect |
| skills/messages-ops/SKILL.md | skill | 100 | Perfect |
| skills/workspace-surface-audit/SKILL.md | skill | 100 | Perfect |
| skills/project-flow-ops/SKILL.md | skill | 100 | Perfect |
| skills/perl-patterns/SKILL.md | skill | 100 | Perfect |
| skills/video-editing/SKILL.md | skill | 100 | Perfect |
| skills/context-budget/SKILL.md | skill | 100 | Perfect |
| skills/logistics-exception-management/SKILL.md | skill | 100 | Perfect |
| skills/nestjs-patterns/SKILL.md | skill | 100 | Perfect |
| skills/eval-harness/SKILL.md | skill | 100 | Perfect |
| skills/agent-sort/SKILL.md | skill | 100 | Perfect |
| skills/opensource-pipeline/SKILL.md | skill | 100 | Perfect |
| skills/quality-nonconformance/SKILL.md | skill | 100 | Perfect |
| skills/swift-actor-persistence/SKILL.md | skill | 100 | Perfect |
| skills/defi-amm-security/SKILL.md | skill | 100 | Perfect |
| skills/csharp-testing/SKILL.md | skill | 100 | Perfect |
| skills/tdd-workflow/SKILL.md | skill | 100 | Perfect |
| skills/kotlin-ktor-patterns/SKILL.md | skill | 100 | Perfect |
| skills/healthcare-phi-compliance/SKILL.md | skill | 100 | Perfect |
| skills/nodejs-keccak256/SKILL.md | skill | 100 | Perfect |
| skills/investor-materials/SKILL.md | skill | 100 | Perfect |
| skills/springboot-verification/SKILL.md | skill | 100 | Perfect |
| skills/springboot-security/SKILL.md | skill | 100 | Perfect |
| skills/code-tour/SKILL.md | skill | 100 | Perfect |
| skills/hipaa-compliance/SKILL.md | skill | 100 | Perfect |
| skills/hexagonal-architecture/SKILL.md | skill | 100 | Perfect |
| skills/article-writing/SKILL.md | skill | 100 | Perfect |
| skills/golang-testing/SKILL.md | skill | 100 | Perfect |
| skills/jpa-patterns/SKILL.md | skill | 100 | Perfect |
| skills/nutrient-document-processing/SKILL.md | skill | 100 | Perfect |
| skills/cpp-coding-standards/SKILL.md | skill | 100 | Perfect |
| skills/golang-patterns/SKILL.md | skill | 100 | Perfect |
| skills/pytorch-patterns/SKILL.md | skill | 100 | Perfect |
| skills/evm-token-decimals/SKILL.md | skill | 100 | Perfect |
| skills/coding-standards/SKILL.md | skill | 100 | Perfect |
| skills/git-workflow/SKILL.md | skill | 100 | Perfect |
| skills/kotlin-patterns/SKILL.md | skill | 100 | Perfect |
| skills/gan-style-harness/SKILL.md | skill | 100 | Perfect |
| skills/e2e-testing/SKILL.md | skill | 100 | Perfect |
| skills/perl-security/SKILL.md | skill | 100 | Perfect |
| skills/frontend-design/SKILL.md | skill | 100 | Perfect |
| skills/continuous-learning/SKILL.md | skill | 100 | Perfect |
| skills/product-capability/SKILL.md | skill | 100 | Perfect |
| skills/java-coding-standards/SKILL.md | skill | 100 | Perfect |
| skills/council/SKILL.md | skill | 100 | Perfect |
| skills/laravel-security/SKILL.md | skill | 100 | Perfect |
| skills/verification-loop/SKILL.md | skill | 100 | Perfect |
| skills/rust-patterns/SKILL.md | skill | 100 | Perfect |
| skills/autonomous-loops/SKILL.md | skill | 100 | Perfect |
| skills/carrier-relationship-management/SKILL.md | skill | 100 | Perfect |
| skills/ecc-tools-cost-audit/SKILL.md | skill | 100 | Perfect |
| skills/laravel-tdd/SKILL.md | skill | 100 | Perfect |
| skills/django-patterns/SKILL.md | skill | 100 | Perfect |
| skills/agent-eval/SKILL.md | skill | 100 | Perfect |
| skills/django-tdd/SKILL.md | skill | 100 | Perfect |
| skills/laravel-patterns/SKILL.md | skill | 100 | Perfect |
| skills/springboot-patterns/SKILL.md | skill | 100 | Perfect |
| skills/documentation-lookup/SKILL.md | skill | 100 | Perfect |
| skills/mcp-server-patterns/SKILL.md | skill | 100 | Perfect |
| skills/claude-devfleet/SKILL.md | skill | 100 | Perfect |
| skills/blueprint/SKILL.md | skill | 100 | Perfect |
| skills/videodb/SKILL.md | skill | 100 | Perfect |
| skills/kotlin-exposed-patterns/SKILL.md | skill | 100 | Perfect |
| skills/agent-harness-construction/SKILL.md | skill | 100 | Perfect |
| skills/rust-testing/SKILL.md | skill | 100 | Perfect |
| skills/dotnet-patterns/SKILL.md | skill | 100 | Perfect |
| skills/knowledge-ops/SKILL.md | skill | 100 | Perfect |
| skills/laravel-plugin-discovery/SKILL.md | skill | 100 | Perfect |
| skills/bun-runtime/SKILL.md | skill | 100 | Perfect |
| skills/ui-demo/SKILL.md | skill | 100 | Perfect |
| skills/python-patterns/SKILL.md | skill | 100 | Perfect |
| skills/swift-concurrency-6-2/SKILL.md | skill | 100 | Perfect |
| skills/returns-reverse-logistics/SKILL.md | skill | 100 | Perfect |
| skills/security-review/SKILL.md | skill | 100 | Perfect |
| skills/django-security/SKILL.md | skill | 100 | Perfect |
| skills/frontend-patterns/SKILL.md | skill | 100 | Perfect |
| skills/architecture-decision-records/SKILL.md | skill | 100 | Perfect |
| skills/foundation-models-on-device/SKILL.md | skill | 100 | Perfect |
| skills/kotlin-testing/SKILL.md | skill | 100 | Perfect |
| skills/springboot-tdd/SKILL.md | skill | 100 | Perfect (minor) |
| skills/backend-patterns/SKILL.md | skill | 100 | Perfect |
| skills/healthcare-cdss-patterns/SKILL.md | skill | 100 | Perfect |
| examples/CLAUDE.md | claude.md | 88 | Placeholder format; 1 vague quantifier |
| CLAUDE.md | claude.md | 85 | Missing depth; 1 vague quantifier |
| .claude-plugin/plugin.json | manifest | 95 | Agent descriptions could reference domains |

---

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 2 |
| Medium | 3 |
| Low | 1 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks (hooks.json) | 1 |
| Shell scripts (.sh) | 7 |
| JavaScript scripts (.js) | 50+ |
| MCP config (.mcp.json) | 1 |
| Package manifest (package.json) | 1 |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | hooks/hooks.json | 10 | `npx block-no-verify@1.1.2` | External NPX package executed on every Bash tool invocation. Although version-pinned, each `npx` call re-fetches from the npm registry. A compromised `block-no-verify` package or registry poisoning would execute arbitrary code in every user session. |
| 2 | HIGH | scripts/hooks/post-edit-format.js | 56–68 | `spawnSync(resolved.bin, fileArgs, { shell: true })` | Windows .cmd execution with `shell: true`. Path is validated against `UNSAFE_PATH_CHARS` but character-set rejection (denylist) is weaker than an allowlist; Unicode tricks, newline injection, and parentheses are not blocked. |
| 3 | HIGH | scripts/hooks/stop-format-typecheck.js | 64–76 | `spawnSync(resolved.bin, fileArgs, { shell: true })` | Same pattern as finding #2. Shell execution on Windows with user-controlled file path. |
| 4 | MEDIUM | scripts/hooks/mcp-health-check.js | 254–297 | HTTP/HTTPS requests to MCP server URLs from config | Hook makes outbound network requests to arbitrary URLs loaded from user config. Could probe internal network services (127.0.0.1, RFC-1918 ranges). No host allowlist. |
| 5 | MEDIUM | scripts/hooks/auto-tmux-dev.js | 62–78 | `spawnSync` with controlled input | Command execution with session names derived from user-provided paths. Name sanitization (`replace(/[^a-zA-Z0-9_-]/g, '_')`) is correct, but pattern warrants monitoring. |
| 6 | MEDIUM | scripts/lib/utils.js | 403–428 | Command allowlist with `spawnSync` | Trusted-prefix allowlist gates command execution, but list maintenance is manual. Any addition to the allowlist that accepts user-controlled suffix could escalate. |
| 7 | LOW | package.json | ~122 | `"@iarna/toml": "^2.2.5"` | Caret range allows unreviewed minor/patch updates. Low risk but should be pinned for reproducible builds. |

---

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | commands/learn.md | Missing required `name` AND `description` frontmatter fields | Agent/command registration will fail; not loadable as a named command |
| 2 | commands/eval.md | Missing required `name` frontmatter field | Registration failure |
| 3 | commands/update-docs.md | Missing required `name` AND `description` frontmatter | Registration failure |
| 4 | commands/model-route.md | Missing required `name` AND `description` frontmatter | Registration failure |
| 5 | commands/multi-execute.md | Missing required `name` AND `description` frontmatter; references undefined variables `$ARGUMENTS`, `{{LITE_MODE_FLAG}}` | Registration failure + runtime undefined references |
| 6 | commands/test-coverage.md | Missing required `name` AND `description` frontmatter | Registration failure |
| 7 | commands/gan-build.md | Missing required `name` AND `description` frontmatter; references agents gan-planner, gan-generator, gan-evaluator without declaring them as dependencies | Registration failure; agent dispatch will fail if agents not installed |
| 8 | docs/ko-KR/commands/learn.md | Missing `name` AND `description` frontmatter (localized copies inherit source file bug) | Same as #1 in Korean locale |
| 9 | docs/ko-KR/commands/eval.md | Missing `name` AND `description` frontmatter | Registration failure in Korean locale |
| 10 | docs/zh-TW/commands/learn.md | Missing `name` AND `description` frontmatter | Registration failure in zh-TW locale |
| 11 | docs/pt-BR/commands/learn.md | Missing `name` AND `description` frontmatter | Registration failure in pt-BR locale |
| 12 | docs/tr/commands/eval.md | Missing `name` AND `description` frontmatter | Registration failure in Turkish locale |
| 13 | docs/ja-JP/commands/eval.md | Missing `name` AND `description` frontmatter | Registration failure in Japanese locale |
| 14 | docs/zh-CN/commands/eval.md | Missing `name` AND `description` frontmatter | Registration failure in zh-CN locale |
| 15 | docs/ko-KR/agents/go-reviewer.md | Missing `description` field entirely | Agent registration incomplete |
| 16 | docs/ko-KR/agents/security-reviewer.md | Declares `Write`, `Edit` tools — this is a read-only review agent that should not modify files | Agent can inadvertently write/overwrite reviewed files |
| 17 | agents/gan-evaluator.md | Uses Playwright in workflow but `Playwright` is not declared in `tools` list | Tool call will fail at runtime |
| 18 | .kiro/agents/security-reviewer.md | Uses non-standard `allowedTools` field instead of `tools` — Kiro IDE may not recognize this and the agent's tool list would be ignored | Security agent has no tool restrictions enforced |
| 19 | skills/ralphinho-rfc-pipeline/SKILL.md | Missing required `name` AND `description` frontmatter | Skill not registerable |
| 20 | agents/type-design-analyzer.md | File appears truncated mid-section | Incomplete agent definition |
| 21 | commands/tdd.md | File contains full TDD example code inline that was not removed when skill shim was created — structural contamination | Confusing agent behavior; bloated context |
| 22 | commands/e2e.md | Contains unrelated Playwright test code mixed with command documentation | Contaminated artifact; misleads agent |
| 23 | skills/continuous-agent-loop/SKILL.md | Missing required `name` frontmatter field | Skill not registerable |
| 24 | .kiro/skills/tdd-workflow/SKILL.md | Uses `await page.waitForTimeout(600)` anti-pattern in E2E test example (line ~199); should use `waitForLoadState`/`waitForSelector` | Example teaches flaky test practice |

---

## Security Fixes (PR-worthy, Medium/Low only)

> **Critical (#1) and High (#2, #3) findings require private disclosure — do NOT submit public PRs for these.**

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/hooks/mcp-health-check.js | Outbound HTTP to arbitrary MCP URLs — can probe RFC-1918 addresses | Add host validation: reject loopback/private IPs unless user has explicitly allowlisted them; document that MCP server URLs must be trusted |
| 2 | scripts/lib/utils.js | Manual command allowlist maintenance creates ongoing risk | Add automated test asserting allowlist entries match expected patterns; add code review checklist item for allowlist changes |
| 3 | package.json | `@iarna/toml: "^2.2.5"` uses caret range | Pin to exact version `"2.2.5"` for reproducible supply chain |

---

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/e2e-runner.md | Missing explicit output format specification | -10 |
| 2 | agents/e2e-runner.md | Vague quantifiers: critical (3), proper (2), reliable (2), comprehensive (1), stable (1) = 9× | -18 |
| 3 | agents/security-reviewer.md | Missing explicit output format; delegates to external skill | -10 |
| 4 | agents/refactor-cleaner.md | Missing output format specification; vague quantifiers × 6 | -12 |
| 5 | agents/go-reviewer.md | Zero examples — no Go anti-pattern code shown | -15 |
| 6 | agents/silent-failure-hunter.md | Zero examples; too brief to guide execution | -15 |
| 7 | agents/gan-planner.md | Zero examples despite rich product-spec workflow | -15 |
| 8 | agents/harness-optimizer.md | Zero examples; extremely brief; unclear optimization criteria | -15 |
| 9 | agents/java-reviewer.md | "proper" used 3×, "idiomatic" 2×, "best practices" 2× — all without specifics | -16 |
| 10 | agents/opensource-sanitizer.md | "critical" used 5× as vague severity label | -20 (cap) |
| 11 | agents/code-simplifier.md | No output format; no examples | -25 |
| 12 | agents/loop-operator.md | No output format; no examples; execution model unclear | -25 |
| 13 | agents/opensource-forker.md | 20 vague quantifier instances; regex patterns for secret detection lack false-positive warnings | -20 (cap) |
| 14 | agents/performance-optimizer.md | Write/Edit declared without guidance on when modification is permitted | -10 |
| 15 | agents/gan-evaluator.md | 10+ vague quantifiers; scoring criteria relies entirely on subjective language | -20 (cap) |
| 16 | All 40+ tr/ja-JP agents | All have exactly one example (threshold met) but universally lack explicit output format | -5 each |
| 17 | All 12 ko-KR agents | Missing `model` field in frontmatter | -5 each |
| 18 | All 12 pt-BR agents | Missing `model` field in frontmatter | -5 each |
| 19 | All 16 .kiro/agents/*.md | Missing `model` field in frontmatter | -5 each |
| 20 | docs/zh-TW/agents/*.md | Model declared as `opus` but English originals use `sonnet` — tier mismatch | Quality concern |
| 21 | commands/learn.md (all locales) | Zero numbered steps for 5-step extraction process | -10 |
| 22 | commands/multi-execute.md | Phases numbered 0, 1, 3, 4, 5 — skips phase 2 | -10 |
| 23 | commands/gan-build.md | "Plateau detection" not defined; loop exit condition vague | -10 |
| 24 | commands/multi-frontend.md | 6-phase workflow with zero numbered steps | -10 |
| 25 | commands/multi-backend.md | 6-phase workflow with zero numbered steps | -10 |
| 26 | commands/santa-loop.md | Complex conditional logic in prose without decision numbering | -10 |
| 27 | All main commands (59/72) | Missing `allowed-tools` declaration | -5 each |
| 28 | All localized commands (~170 files) | Missing `allowed-tools` declaration | -5 each |
| 29 | commands/review-pr.md | No specification of accepted PR identifier format | -5 |
| 30 | skills/inventory-demand-planning/SKILL.md | 8 vague quantifiers: reasonable, standard, suitable, proper, appropriate, healthy, significant, practical | -16 |
| 31 | skills/customs-trade-compliance/SKILL.md | 10+ vague quantifiers + missing output format | -30 |
| 32 | skills/dart-flutter-patterns/SKILL.md | "appropriate" used 8× throughout | -16 |
| 33 | skills/flutter-dart-code-review/SKILL.md | 19 vague quantifier instances (appropriate × 8, relevant × 3, proper × 3) | -20 (cap) |
| 34 | skills/openclaw-persona-forge/SKILL.md | "typically 9-13 steps" × 5 instances — range imprecision | -10 |

---

## Cross-Component

**Broken References:**
- `commands/gan-build.md` dispatches to agents `gan-planner`, `gan-generator`, `gan-evaluator` — these exist in `agents/` but are not declared as dependencies anywhere in the command frontmatter. If the agents plugin is not co-installed, dispatch silently fails.
- `agents/harness-optimizer.md` references `/harness-audit` command but this command is at `commands/harness-audit.md` — the path notation is inconsistent.
- `.kiro/agents/security-reviewer.md` uses `allowedTools` while all other agent files use `tools` — inconsistent schema across IDE variants.

**Model Tier Inconsistencies:**
- `docs/zh-TW/agents/*.md` declares `model: opus` for agents that their English originals define as `sonnet`. A full review fleet running `opus` in zh-TW will incur ~5× higher costs than intended.
- `docs/ja-JP/agents/*.md` also uses `model: opus` throughout — same concern.

**Orphaned Skill Namespace:**
- `skills/ck/SKILL.md` exists but `ck` is not referenced by any agent or command in the scanned corpus. Possibly an internal utility but appears unused.

**Localization Drift:**
- `commands/learn.md` and `commands/eval.md` both have missing frontmatter in the English source. All 7 localized copies (`ko-KR`, `zh-TW`, `pt-BR`, `tr`, `ja-JP`, `zh-CN`, `.opencode`) inherit this bug, multiplying the impact.

**Deprecated Shims Without Sunset Date:**
- `commands/claw.md`, `commands/verify.md`, `commands/prompt-optimize.md`, `commands/rules-distill.md`, `commands/agent-sort.md` are explicitly marked as legacy shims but carry no deprecation version or sunset guidance. Users have no indication these will be removed.

---

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

The `hooks/hooks.json` Critical finding (supply chain risk via unpinned `npx block-no-verify` execution on every Bash tool call) and the two High findings (shell injection vectors in Windows `.cmd` execution paths) require private disclosure to the maintainer before any public contribution.

**After security is resolved**, there are 24 PR-worthy bugs and 34+ quality issues worth contributing:

**Priority 1 — Fix source bugs, fixes propagate to all locales:**
1. Add missing `name`/`description` to `commands/learn.md` and `commands/eval.md` (fixes 14 localized copies)
2. Remove contaminating example code from `commands/tdd.md` and `commands/e2e.md`
3. Add `Playwright` to `agents/gan-evaluator.md` tools list
4. Fix `skills/ralphinho-rfc-pipeline/SKILL.md` and `skills/continuous-agent-loop/SKILL.md` missing frontmatter

**Priority 2 — Agent quality:**
5. Add `model: haiku` (or appropriate tier) to all `ko-KR`, `pt-BR`, `.kiro` agents missing the field
6. Add output format sections to `agents/e2e-runner.md`, `agents/refactor-cleaner.md`, `agents/security-reviewer.md`
7. Add 2–3 concrete examples to `agents/go-reviewer.md`, `agents/silent-failure-hunter.md`, `agents/gan-planner.md`

**Priority 3 — Command cleanup:**
8. Add `name` field to all commands missing it (58 files with `-25` penalty)
9. Add `allowed-tools` declaration to commands (consistent pattern — can template-copy from `skill-create.md` which scores 100)
