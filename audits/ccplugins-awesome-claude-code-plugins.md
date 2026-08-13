# NLPM Audit: ccplugins/awesome-claude-code-plugins
**Date**: 2026-04-12  |  **Artifacts**: 244  |  **Strategy**: progressive
**NL Score**: 78/100
**Security**: CLEAR
**Bugs**: 10  |  **Quality Issues**: 97  |  **Security Findings**: 3

---

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/desktop-app-dev/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Desktop App Dev subagent" — no semantic content |
| plugins/growth-hacker/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Growth Hacker subagent" — no semantic content |
| plugins/twitter-engager/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Twitter Engager subagent" — no semantic content |
| plugins/reddit-community-builder/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Reddit Community Builder subagent" — no semantic content |
| plugins/content-creator/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Content Creator subagent" — no semantic content |
| plugins/instagram-curator/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Instagram Curator subagent" — no semantic content |
| plugins/changelog-generator/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Changelog Generator subagent" — no semantic content |
| plugins/model-context-protocol-mcp-expert/.claude-plugin/plugin.json | plugin.json | 62 | Description is "Model Context Protocol Mcp Expert subagent" — no semantic content |
| plugins/problem-solver-specialist/agents/problem-solver-specialist.md | agent | 63 | frontmatter name "1-problem-solver-specialist" doesn't match plugin name; no examples in description; tools:"*" is overly broad |
| plugins/fix-issue/commands/fix-issue.md | command | 65 | Single-line body "Fix issue $ARGUMENTS" — no steps, no output format, no empty-input handling |
| plugins/fix-pr/commands/fix-pr.md | command | 65 | Single-line body — no steps, no allowed-tools, no output format |
| plugins/analytics-reporter/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated mid-sentence after "Context: Monthly performance review needed" |
| plugins/customer-success-manager/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after "Examples:" |
| plugins/support-responder/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated mid-sentence after "Context: Setting up support for a new app launch" |
| plugins/enterprise-onboarding-specialist/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/data-privacy-engineer/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/performance-benchmarker/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/infrastructure-maintainer/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/workflow-optimizer/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/test-results-analyzer/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/ux-researcher/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/pr-issue-resolve/.claude-plugin/plugin.json | plugin.json | 65 | Description is minimal ("this is to analyze the PRs and solve the requested changes in them") |
| plugins/brand-guardian/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/app-store-optimizer/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/ai-ethics-governance-specialist/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/tool-evaluator/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/product-sales-specialist/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/enterprise-security-reviewer/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/finance-tracker/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/database-performance-optimizer/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/api-integration-specialist/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/b2b-project-shipper/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/compliance-automation-specialist/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/api-tester/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/legal-compliance-checker/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/technical-sales-engineer/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/visual-storyteller/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/feedback-synthesizer/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/monitoring-observability-specialist/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/pricing-packaging-specialist/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/legal-advisor/.claude-plugin/plugin.json | plugin.json | 65 | Description ends with "Examples:" — truncated |
| plugins/ui-designer/.claude-plugin/plugin.json | plugin.json | 65 | Description truncated after first example context |
| plugins/data-scientist/agents/data-scientist.md | agent | 66 | No model declared; no examples; body is ~30 lines with no output format |
| plugins/desktop-app-dev/agents/desktop-app-dev.md | agent | 66 | No model declared; no examples; short body (~79 lines) with no output format |
| plugins/changelog-generator/agents/changelog-generator.md | agent | 66 | No model declared; no examples; no output format; body ~88 lines |
| plugins/project-curator/agents/project-curator.md | agent | 66 | No model declared; no examples in description; no output format |
| plugins/agent-sdk-dev/.claude-plugin/plugin.json | plugin.json | 68 | Description is "Claude Agent SDK Development Plugin" — no actionable context |
| plugins/pr-review/commands/pr-review.md | command | 69 | No allowed-tools; no numbered execution steps; no empty-input handling; vague prose |
| plugins/enterprise-onboarding-specialist/agents/enterprise-onboarding-specialist.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/data-privacy-engineer/agents/data-privacy-engineer.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/enterprise-integrator-architect/agents/enterprise-integrator-architect.md | agent | 71 | BUG: frontmatter name "enterprise-integration-architect" vs plugin name; no model; ~7 vague terms |
| plugins/legal-advisor/agents/legal-advisor.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/monitoring-observability-specialist/agents/monitoring-observability-specialist.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/pricing-packaging-specialist/agents/pricing-packaging-specialist.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/ai-ethics-governance-specialist/agents/ai-ethics-governance-specialist.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/enterprise-security-reviewer/agents/enterprise-security-reviewer.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/database-performance-optimizer/agents/database-performance-optimizer.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/api-integration-specialist/agents/api-integration-specialist.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/compliance-automation-specialist/agents/compliance-automation-specialist.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/technical-sales-engineer/agents/technical-sales-engineer.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/product-sales-specialist/agents/product-sales-specialist.md | agent | 71 | No model; ~7 vague quantifiers; no explicit output format |
| plugins/vision-specialist/agents/vision-specialist.md | agent | 71 | model: opus declared but no examples in description; no explicit output format |
| plugins/discuss/commands/discuss.md | command | 71 | No allowed-tools; no numbered steps; no empty-input handling |
| plugins/explore/commands/explore.md | command | 71 | No allowed-tools; no numbered steps; no empty-input handling; hardcoded file path placeholder |
| plugins/plan/commands/plan.md | command | 71 | No allowed-tools; no numbered steps; no empty-input handling; hardcoded "gh issue ###" |
| plugins/refractor/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/lyra/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/bug-detective/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/documentation-generator/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/optimize/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/generate-api-docs/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/code-review/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/analyze-codebase/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/audit/.claude-plugin/plugin.json | plugin.json | 72 | Description is one minimal sentence |
| plugins/customer-success-manager/agents/customer-success-manager.md | agent | 73 | No model; >7 vague quantifiers (capped at -20); no explicit output format |
| plugins/studio-producer/agents/studio-producer.md | agent | 73 | No model; >7 vague quantifiers; no explicit output format |
| plugins/brand-guardian/agents/brand-guardian.md | agent | 73 | No model; >7 vague quantifiers; no explicit output format |
| plugins/tiktok-strategist/agents/tiktok-strategist.md | agent | 73 | No model; >7 vague quantifiers; no explicit output format |
| plugins/whimsy-injector/agents/whimsy-injector.md | agent | 73 | No model; >7 vague quantifiers; no explicit output format |
| plugins/studio-coach/agents/studio-coach.md | agent | 73 | No model; >7 vague quantifiers; no explicit output format |
| plugins/b2b-project-shipper/agents/b2b-project-shipper.md | agent | 73 | No model; >7 vague quantifiers; no explicit output format |
| plugins/unit-test-generator/agents/unit-test-generator.md | agent | 74 | model: sonnet ✓; no examples in description; output format partially defined |
| plugins/lyra/commands/lyra.md | command | 74 | No allowed-tools; welcome message not a command; no empty-input handling |
| plugins/devops-automator/agents/devops-automator.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/analytics-reporter/agents/analytics-reporter.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/support-responder/agents/support-responder.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/mobile-app-builder/agents/mobile-app-builder.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/performance-benchmarker/agents/performance-benchmarker.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/infrastructure-maintainer/agents/infrastructure-maintainer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/workflow-optimizer/agents/workflow-optimizer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/test-results-analyzer/agents/test-results-analyzer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/ux-researcher/agents/ux-researcher.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/content-creator/agents/content-creator.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/app-store-optimizer/agents/app-store-optimizer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/frontend-developer/agents/frontend-developer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/tool-evaluator/agents/tool-evaluator.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/sprint-prioritizer/agents/sprint-prioritizer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/trend-researcher/agents/trend-researcher.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/rapid-prototyper/agents/rapid-prototyper.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/finance-tracker/agents/finance-tracker.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/feedback-synthesizer/agents/feedback-synthesizer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/visual-storyteller/agents/visual-storyteller.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/project-shipper/agents/project-shipper.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/ai-engineer/agents/ai-engineer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/twitter-engager/agents/twitter-engager.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/reddit-community-builder/agents/reddit-community-builder.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/instagram-curator/agents/instagram-curator.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/growth-hacker/agents/growth-hacker.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/joker/agents/joker.md | agent | 75 | No model; no explicit output format; very short body |
| plugins/ui-designer/agents/ui-designer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/mobile-ux-optimizer/agents/mobile-ux-optimizer.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/planning-prd-agent/agents/planning-prd-agent.md | agent | 75 | description wrapped in extra quotes; no examples in description; model: opus ✓ |
| plugins/prd-specialist/agents/prd-specialist.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/api-tester/agents/api-tester.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/legal-compliance-checker/agents/legal-compliance-checker.md | agent | 75 | No model; no explicit output format; ~5 vague quantifiers |
| plugins/agent-sdk-dev/agents/agent-sdk-verifier-ts.md | agent | 76 | No tools declared; body calls `npx tsc --noEmit` and WebFetch — missing Bash, Read, WebFetch |
| plugins/agent-sdk-dev/agents/agent-sdk-verifier-py.md | agent | 76 | No tools declared; body calls pip/python commands — missing Bash, Read tools |
| plugins/onomastophes/agents/onomastophes.md | agent | 76 | No model; no examples in description; has output format ✓ |
| plugins/code-reviewer/agents/code-reviewer.md | agent | 76 | No model; no examples in description (-15); checklist body only |
| plugins/code-architect/agents/code-architect.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/backend-architect/agents/backend-architect.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/web-dev/agents/web-dev.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/react-native-dev/agents/react-native-dev.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/python-expert/agents/python-expert.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/flutter-mobile-app-dev/agents/flutter-mobile-app-dev.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/n8n-workflow-builder/agents/n8n-workflow-builder.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/codebase-documenter/agents/codebase-documenter.md | agent | 77 | No model; no explicit output format; ~4 vague quantifiers |
| plugins/ceo-quality-controller-agent/agents/ceo-quality-controller-agent.md | agent | 78 | BUG: frontmatter name "1-ceo-quality-control-agent" mismatches plugin name; tools:"*" overly broad |
| plugins/bug-fix/commands/bug-fix.md | command | 78 | No allowed-tools; no numbered steps; $ARGUMENTS injection potential |
| plugins/context7-docs-fetcher/agents/context7-docs-fetcher.md | agent | 79 | BUG: uses `mcp__ide__*` tools not declared in tools list; no model |
| plugins/feature-dev/agents/code-explorer.md | agent | 79 | No examples in description; tools list includes KillShell and BashOutput (unusual) |
| plugins/feature-dev/agents/code-architect.md | agent | 79 | No examples in description; tools list includes KillShell and BashOutput (unusual) |
| plugins/feature-dev/agents/code-reviewer.md | agent | 79 | No examples in description; tools list includes KillShell and BashOutput (unusual) |
| plugins/github-issue-fix/commands/github-issue-fix.md | command | 79 | No allowed-tools; no empty-input handling for $ARGUMENTS |
| plugins/refractor/commands/refractor.md | command | 79 | No allowed-tools; no empty-input handling |
| plugins/deployment-engineer/agents/deployment-engineer.md | agent | 80 | model: sonnet ✓; no explicit output format; ~4 vague quantifiers |
| plugins/debugger/agents/debugger.md | agent | 80 | No model; no output format; short body ~30 lines |
| plugins/claude-desktop-extension/commands/claude-desktop-extension.md | command | 80 | No allowed-tools; uses WebFetch implicitly but not declared |
| plugins/discuss/.claude-plugin/plugin.json | plugin.json | 80 | Description is one adequate sentence |
| plugins/claude-desktop-extension/.claude-plugin/plugin.json | plugin.json | 80 | Description is one adequate sentence |
| plugins/update-claudemd/.claude-plugin/plugin.json | plugin.json | 80 | Description is one adequate sentence |
| plugins/github-issue-fix/.claude-plugin/plugin.json | plugin.json | 80 | Description is one adequate sentence |
| plugins/update-branch-name/commands/update-branch-name.md | command | 81 | No allowed-tools; no empty-input handling |
| plugins/commit/commands/commit.md | command | 81 | No allowed-tools; describes workflow but no executable steps |
| plugins/ultrathink/commands/ultrathink.md | command | 81 | No allowed-tools; no empty-input handling |
| plugins/code-review-assistant/commands/code-review-assistant.md | command | 81 | No allowed-tools; no empty-input handling |
| plugins/double-check/commands/double-check.md | command | 81 | No allowed-tools; partially handles empty input |
| plugins/create-worktrees/commands/create-worktrees.md | command | 81 | No allowed-tools; no empty-input handling |
| plugins/fix-github-issue/commands/fix-github-issue.md | command | 81 | No allowed-tools; no empty-input handling |
| plugins/create-pull-request/commands/create-pull-request.md | command | 81 | No allowed-tools; no numbered steps |
| plugins/pr-issue-resolve/commands/pr-issue-resolve.md | command | 81 | No allowed-tools; no empty-input handling |
| plugins/angelos-symbo/agents/angelos-symbo.md | agent | 81 | No model; no examples in description; has output format ✓ |
| plugins/debugger/.claude-plugin/plugin.json | plugin.json | 82 | Adequate single-sentence description |
| plugins/test-file/.claude-plugin/plugin.json | plugin.json | 82 | Adequate single-sentence description |
| plugins/analyze-issue/.claude-plugin/plugin.json | plugin.json | 82 | Adequate description |
| plugins/explore/.claude-plugin/plugin.json | plugin.json | 82 | Adequate description |
| plugins/onomastophes/.claude-plugin/plugin.json | plugin.json | 82 | Adequate description |
| plugins/code-reviewer/.claude-plugin/plugin.json | plugin.json | 82 | Adequate description |
| plugins/double-check/.claude-plugin/plugin.json | plugin.json | 82 | Adequate description |
| plugins/code-review-assistant/.claude-plugin/plugin.json | plugin.json | 82 | Adequate description |
| plugins/data-scientist/.claude-plugin/plugin.json | plugin.json | 82 | Adequate description |
| plugins/optimize/commands/optimize.md | command | 84 | has allowed-tools ✓; SECURITY: $ARGUMENTS interpolated into `du`/`wc` shell calls; no empty-input handling |
| plugins/experiment-tracker/agents/experiment-tracker.md | agent | 85 | No model; has documentation template (output format) ✓; ~4 vague quantifiers |
| plugins/unit-test-generator/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/pr-review-toolkit/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/planning-prd-agent/.claude-plugin/plugin.json | plugin.json | 85 | Good description; description value wrapped in extra quotes |
| plugins/update-branch-name/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/commit/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/fix-issue/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/vision-specialist/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/ultrathink/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/feature-dev/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/create-worktrees/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/project-curator/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/create-pr/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/fix-github-issue/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/husky/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/create-pull-request/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/problem-solver-specialist/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/bug-fix/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/pr-review/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/fix-pr/.claude-plugin/plugin.json | plugin.json | 85 | Good description |
| plugins/debug-session/.claude-plugin/plugin.json | plugin.json | 85 | Adequate description |
| plugins/code-review/commands/code-review.md | command | 86 | has allowed-tools ✓; no empty-input handling (no fallback if no changes) |
| plugins/feature-dev/commands/feature-dev.md | command | 86 | No allowed-tools; very detailed phases ✓; optional args handled ✓ |
| plugins/create-pr/commands/create-pr.md | command | 86 | No allowed-tools; good workflow description; no empty-input handling |
| plugins/generate-api-docs/commands/generate-api-docs.md | command | 86 | has allowed-tools ✓; no empty-input handling |
| plugins/agent-sdk-dev/commands/new-sdk-app.md | command | 87 | No allowed-tools; very detailed interactive flow ✓; uses WebFetch without declaring it |
| plugins/openapi-expert/.claude-plugin/plugin.json | plugin.json | 88 | Good description |
| plugins/security-guidance/.claude-plugin/plugin.json | plugin.json | 88 | Good description |
| plugins/enterprise-integrator-architect/.claude-plugin/plugin.json | plugin.json | 88 | Good description with examples |
| plugins/analyze-codebase/commands/analyze-codebase.md | command | 90 | has allowed-tools ✓; very detailed ✓; output file defined ✓; ~4 vague qualifiers |
| plugins/audit/commands/audit.md | command | 90 | has allowed-tools ✓; numbered steps ✓; handles empty $ARGUMENTS ✓ |
| plugins/pr-review-toolkit/commands/review-pr.md | command | 90 | has allowed-tools ✓; 7 numbered steps ✓; handles empty args ✓; ~4 vague qualifiers |
| plugins/pr-review-toolkit/agents/code-simplifier.md | agent | 91 | model: opus ✓; 1 example (-5); has output format ✓; no tools (appropriate for review) |
| plugins/pr-review-toolkit/agents/type-design-analyzer.md | agent | 91 | model: inherit ✓; 1 example (-5); has output format ✓; no tools (appropriate) |
| plugins/pr-review-toolkit/agents/code-reviewer.md | agent | 91 | model: opus ✓; 1 example (-5); has output format ✓; no tools (appropriate) |
| plugins/pr-review-toolkit/agents/comment-analyzer.md | agent | 91 | model: inherit ✓; 1 example (-5); has output format ✓; no tools (appropriate) |
| plugins/pr-review-toolkit/agents/pr-test-analyzer.md | agent | 91 | model: inherit ✓; 1 example (-5); has output format ✓; no tools (appropriate) |
| plugins/bug-detective/commands/bug-detective.md | command | 91 | No allowed-tools; well-structured framework; handles no-input gracefully |
| plugins/documentation-generator/commands/documentation-generator.md | command | 91 | No allowed-tools; well-structured; handles no-input gracefully |
| plugins/husky/commands/husky.md | command | 91 | No allowed-tools; numbered steps ✓; good error-handling protocol |
| plugins/update-claudemd/commands/update-claudemd.md | command | 92 | has allowed-tools ✓; very detailed sections ✓; no empty-input issue (reads CLAUDE.md) |
| plugins/commit-commands/commands/clean_gone.md | command | 93 | No allowed-tools; bash script with safe patterns; good fallback handling |
| plugins/debug-session/commands/debug-session.md | command | 93 | has allowed-tools ✓; 5 numbered steps ✓; handles empty $ARGUMENTS gracefully |
| plugins/pr-review-toolkit/agents/silent-failure-hunter.md | agent | 94 | model: inherit ✓; 2 examples ✓; output format ✓; no tools (appropriate); few vague words |
| plugins/joker/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/react-native-dev/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/mobile-app-builder/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/python-expert/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/experiment-tracker/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/studio-producer/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/deployment-engineer/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/backend-architect/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/sprint-prioritizer/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/trend-researcher/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/rapid-prototyper/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/whimsy-injector/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/project-shipper/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/test-writer-fixer/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 5 examples |
| plugins/angelos-symbo/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/context7-docs-fetcher/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/ceo-quality-controller-agent/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/tiktok-strategist/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/n8n-workflow-builder/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/ai-engineer/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/frontend-developer/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/flutter-mobile-app-dev/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/mobile-ux-optimizer/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/web-dev/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/code-architect/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/prd-specialist/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/codebase-documenter/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 2 examples |
| plugins/studio-coach/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 4 examples |
| plugins/devops-automator/.claude-plugin/plugin.json | plugin.json | 95 | Full description with 3 examples |
| plugins/commit-commands/commands/commit.md | command | 98 | has allowed-tools ✓; numbered steps ✓; clean single-purpose ✓ |
| plugins/commit-commands/commands/commit-push-pr.md | command | 98 | has allowed-tools ✓; numbered steps ✓; clean single-purpose ✓ |

---

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 2 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 1 — `plugins/security-guidance/hooks/hooks.json` |
| Scripts | 1 — `plugins/security-guidance/hooks/security_reminder_hook.py` |
| MCP configs | 0 |
| Package manifests | 0 (no root `package.json` or `requirements.txt`) |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | MEDIUM | `plugins/optimize/commands/optimize.md` | 6–7 | User args in shell commands | `!`du -h $ARGUMENTS`` and `!`wc -l $ARGUMENTS`` interpolate the raw argument string directly into shell commands. A user passing `"; rm -rf ~"` would execute the injected command via the `!` (pre-context shell execution) mechanism. Suggest: validate that $ARGUMENTS is a file path matching `[a-zA-Z0-9_./-]+` before use, or use `@$ARGUMENTS` for file inclusion instead of shell commands. |
| 2 | LOW | `plugins/security-guidance/hooks/security_reminder_hook.py` | 17–22 | Write to world-writable path | Debug log written unconditionally to `/tmp/security-warnings-log.txt`. On multi-user systems this file can be read or appended to by any local user. Suggest: use a user-specific temp file (`tempfile.mkstemp`) or disable debug logging by default. |
| 3 | LOW | `plugins/security-guidance/hooks/security_reminder_hook.py` | ~55 | Session state in home directory | Session state written to `~/.claude/security_warnings_state_<session_id>.json`. Accumulates over time with no cleanup. Suggest: add TTL-based pruning or store in a fixed single-file location. |

---

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `plugins/enterprise-integrator-architect/agents/enterprise-integrator-architect.md` | Frontmatter `name: enterprise-integration-architect` doesn't match plugin name `enterprise-integrator-architect` (missing "or" → "or"). | Agent won't register with correct identity; invocation via plugin name will fail or produce wrong agent name in logs. |
| 2 | `plugins/ceo-quality-controller-agent/agents/ceo-quality-controller-agent.md` | Frontmatter `name: 1-ceo-quality-control-agent` (prefixed `1-`, ends in `-agent` not `-controller-agent`) mismatches plugin name `ceo-quality-controller-agent`. | Same registration mismatch; agent routing breaks. |
| 3 | `plugins/problem-solver-specialist/agents/problem-solver-specialist.md` | Frontmatter `name: 1-problem-solver-specialist` mismatches plugin name `problem-solver-specialist`. | Agent registered as `1-problem-solver-specialist`; downstream sub-agent delegation will fail unless callers use the prefixed name. |
| 4 | `plugins/openapi-expert/commands/openapi-expert.md` | File is in `commands/` directory but has agent-style frontmatter (`name`, `description`, `color`) and no `allowed-tools`. Claude Code will try to register it as a command with an agent-format body. | Command registration likely silently fails or produces broken behavior; the tool never executes correctly. |
| 5 | `plugins/agent-sdk-dev/agents/agent-sdk-verifier-ts.md` | No tools declared. Body explicitly instructs running `npx tsc --noEmit` (requires Bash) and fetching documentation (requires WebFetch). | Agent cannot execute its verification steps; will silently produce incomplete output. |
| 6 | `plugins/agent-sdk-dev/agents/agent-sdk-verifier-py.md` | Same issue as above — no tools declared, body requires Bash and WebFetch. | Same impact as #5. |
| 7 | `plugins/context7-docs-fetcher/agents/context7-docs-fetcher.md` | Uses MCP tools `mcp__ide__getDiagnostics` and `mcp__ide__executeCode` which require an active IDE MCP connection. These are not declared in the `tools:` frontmatter. | Agent silently fails when IDE MCP is unavailable. Users get misleading errors. |
| 8 | Multiple `plugin.json` files (~30) | `description` field is truncated mid-sentence (e.g., ends with `"Context: Monthly performance review needed"` or `"Examples:"`). This is likely a JSON serialization bug where long strings were cut at a character limit. | Plugin descriptions shown in marketplace/install dialogs will be incomplete and confusing. |
| 9 | `plugins/planning-prd-agent/.claude-plugin/plugin.json` | The `description` value is wrapped in an extra layer of single-quote string syntax: `"'MUST BE USED PROACTIVELY...'"` — the outer string contains a raw single-quoted string. | Some parsers may include the literal quote characters in the rendered description, creating UI noise. |
| 10 | `plugins/pr-issue-resolve/.claude-plugin/plugin.json` | Description `"this is to analyze the PRs and solve the requested changes in them\n"` contains a trailing literal `\n` newline escape in the JSON value. | May render as literal backslash-n in some displays; minor formatting bug. |

---

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `plugins/optimize/commands/optimize.md` | `$ARGUMENTS` interpolated directly into `du` and `wc` shell commands — shell injection risk. | Replace `!`du -h $ARGUMENTS`` with `@$ARGUMENTS` file reference for size context, or add an explicit note that the argument must be a safe file path. Add a check: `[[ "$ARGUMENTS" =~ ^[a-zA-Z0-9_./-]+$ ]]` before use. |
| 2 | `plugins/security-guidance/hooks/security_reminder_hook.py` | Debug log at `/tmp/security-warnings-log.txt` is world-readable on shared systems. | Gate debug logging behind an env var (e.g., `SECURITY_HOOK_DEBUG=1`), disabled by default. |
| 3 | `plugins/security-guidance/hooks/security_reminder_hook.py` | Session state files in `~/.claude/` accumulate indefinitely. | Add age-based pruning: delete state files older than 24h at hook startup. |

---

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | 48 agent .md files | No `model` declared in frontmatter — Claude Code will use project default without an explicit tier choice. | −5 each |
| 2 | 52 agent .md files | No explicit output format section — agents describe what they do but not how their response is structured. | −10 each |
| 3 | 9 agents (B2B specialist series) | Body text uses >7 vague quantifiers ("appropriate", "comprehensive", "relevant", "proper", "robust", "strategic", "effective", "efficient") — cap applied. | −20 each |
| 4 | ~35 agents | Body text uses 3–6 vague quantifiers per file. | −6 to −12 each |
| 5 | `plugins/fix-issue/commands/fix-issue.md` | Entire command body is "Fix issue $ARGUMENTS" — no steps, no output format, no empty-input handling. | −35 total |
| 6 | `plugins/fix-pr/commands/fix-pr.md` | Single-line body; no steps, no allowed-tools, no output format. | −35 total |
| 7 | `plugins/pr-review/commands/pr-review.md` | No `allowed-tools`; command body is purely descriptive prose, not executable instructions. | −31 total |
| 8 | 25 command files | Missing `allowed-tools` declaration. | −5 each |
| 9 | 12 command files | No empty-input handling for `$ARGUMENTS`. | −10 each |
| 10 | `plugins/problem-solver-specialist/agents/problem-solver-specialist.md` | `tools: "*"` (wildcard) — grants all tools with no specificity; makes tool inventory unmaintainable. | Quality concern |
| 11 | `plugins/ceo-quality-controller-agent/agents/ceo-quality-controller-agent.md` | Same — `tools: "*"` with wildcard. | Quality concern |
| 12 | `plugins/feature-dev/agents/code-explorer.md` | `tools` list includes `KillShell` and `BashOutput` — these are non-standard tool names not in the Claude Code tool registry. Likely copy-paste errors. | May cause registration warnings. |
| 13 | `plugins/feature-dev/agents/code-architect.md` | Same non-standard tools: `KillShell`, `BashOutput`. | Same. |
| 14 | `plugins/feature-dev/agents/code-reviewer.md` | Same non-standard tools: `KillShell`, `BashOutput`. | Same. |
| 15 | `plugins/lyra/commands/lyra.md` | Command body is a persona definition with a hardcoded welcome message — this is an agent in a command slot. No `allowed-tools`. | Structural mismatch. |
| 16 | `plugins/openapi-expert/commands/openapi-expert.md` | Agent body in commands/ directory (also filed as Bug #4). | Structural mismatch. |
| 17 | `plugins/explore/commands/explore.md` | Hardcoded placeholder paths `claude-checklists/DESCRIPTION-OF-THIS-AREA-OF-YOUR-SYSTEM.md` and `claude-checklists/CURRENT-PROJECT.md` — users must know to replace these, but there's no instructional note. | Usability issue. |
| 18 | `plugins/plan/commands/plan.md` | Hardcoded `Read gh issue ###` — users must replace `###` manually; no $ARGUMENTS, no instructions. | Usability issue. |
| 19 | 8 `plugin.json` files | Description is "[Plugin Name] subagent" — completely uninformative. Marketplace users cannot determine purpose. | −30 quality |
| 20 | ~30 `plugin.json` files | Description truncated mid-sentence (also Bug #8). | −20 quality |
| 21 | `plugins/unit-test-generator/agents/unit-test-generator.md` | Body references specific company name "Aurigo" — this is a domain-specific agent accidentally published as a generic plugin. | Domain bleed. |
| 22 | `plugins/pr-review-toolkit` agents | `model: inherit` is used by 4 agents — valid when spawned via Task, but if invoked directly by a user the model falls back to project default, which may be inadequate for review tasks. | Consider `model: sonnet` minimum. |
| 23 | `plugins/code-reviewer/agents/code-reviewer.md` | No examples in description; no model; minimal body. Same name as two other agents in the collection (`feature-dev/code-reviewer`, `pr-review-toolkit/code-reviewer`). | Name collision risk. |

---

## Cross-Component

**Broken references:**
- `plugins/ultrathink/commands/ultrathink.md` delegates to four sub-agents (Architect, Research, Coder, Tester) that are **not defined** as agent files in the plugin. The command acts as if they exist but there is no corresponding `agents/` directory. Users will get no-op delegation.
- `plugins/explore/commands/explore.md` references `claude-checklists/DESCRIPTION-OF-THIS-AREA-OF-YOUR-SYSTEM.md` and `claude-checklists/CURRENT-PROJECT.md` which are placeholder paths not present in the repo.

**Name collisions across plugins:**
- Three separate plugins define an agent named `code-reviewer`: `plugins/code-reviewer/`, `plugins/feature-dev/`, and `plugins/pr-review-toolkit/`. If all three are installed simultaneously, only one will be reachable by name. The pr-review-toolkit version specifies `model: opus` and has a confidence-scoring output format — it is the most complete.

**Structural inconsistency:**
- `plugins/openapi-expert/commands/openapi-expert.md` is stored as a command but has agent-style frontmatter (`name`, `description`, `color`). The companion `plugin.json` correctly describes it as a command. The `.md` file needs its frontmatter corrected to command format (replace `name`/`color` with `description`/`allowed-tools`).
- `plugins/lyra/commands/lyra.md` is a character-persona definition placed in a commands/ slot. It functions more like an agent. No functional impact since commands can contain any instructions, but it's architecturally inconsistent with the rest of the collection.

**Orphaned components:**
- The `agent-sdk-dev` plugin's verifier agents (`agent-sdk-verifier-ts.md`, `agent-sdk-verifier-py.md`) are referenced from `new-sdk-app.md` via "launch the agent-sdk-verifier-ts agent" but have no tools declared and cannot execute their verification steps (see Bug #5/#6).

**Consistent pattern in Alysson Franklin plugins:**
- 13 B2B specialist agents share the same template structure — all lack model declarations and output format sections, and all have truncated plugin.json descriptions ending in `"Examples:"`. These appear to be generated from a common template that was cut short during publishing.

---

## Recommendation

Security is **CLEAR** — no critical or high findings. One medium (shell injection in `optimize.md`) and two low findings are suitable for public PRs.

**Submit PRs for:**

1. **Bug fixes (high priority):** Fix the three agent name mismatches (enterprise-integrator-architect, ceo-quality-controller-agent, problem-solver-specialist). Fix missing tools declarations on agent-sdk-verifier agents. Fix openapi-expert command frontmatter structure.

2. **Truncated plugin.json descriptions:** ~30 files have descriptions cut off mid-sentence. Restoring full descriptions is low-effort, high-visibility. Batch into one PR per plugin author (Michael Galpert, Alysson Franklin batches).

3. **Minimal "subagent" descriptions:** 8 plugin.json files have placeholder descriptions. Replace with 1–2 sentence summaries and 1 example each.

4. **Security fix (Medium):** `plugins/optimize/commands/optimize.md` — replace shell-interpolated `$ARGUMENTS` with safe file reference.

**Defer or author-specific:**
- Model declarations on 48 agents — best done by original authors who know intended model tier.
- Output format sections on 52 agents — substantial content additions, best done per-author.
- `ultrathink` missing sub-agents — requires creating 4 new agent files or removing the delegation claim.
