# NLPM Audit: alirezarezvani/claude-skills
**Date**: 2026-04-06  |  **Artifacts**: 431  |  **Strategy**: progressive
**NL Score**: 92/100
**Security**: BLOCKED
**Bugs**: 16  |  **Quality Issues**: 87  |  **Security Findings**: 11

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| agents/product/cs-product-analyst.md | agent | 70 | Missing output format, insufficient examples |
| commands/seo-auditor.md | command | 70 | Multi-step without numbered steps, vague quantifiers capped |
| agents/engineering/cs-wiki-ingestor.md | agent | 74 | Write/Edit declared on read-only ingestion agent |
| agents/engineering/cs-wiki-librarian.md | agent | 76 | Write/Edit declared on read-only query agent |
| agents/engineering/cs-wiki-linter.md | agent | 78 | Write/Edit declared on read-only auditing agent |
| project-management/senior-pm/SKILL.md | skill | 80 | Vague quantifiers exceed cap (comprehensive, optimize, ensure, etc.) |
| commands/sprint-plan.md | command | 80 | Insufficient detail, missing input format specification |
| .claude/commands/review.md | command | 80 | Multi-step without numbered steps, vague terms |
| agents/marketing/cs-content-creator.md | agent | 83 | Vague quantifiers (ensure, optimize, appropriate, effective, proper) |
| commands/wiki-query.md | command | 81 | Missing allowed-tools, missing output format |
| engineering/llm-wiki/commands/wiki-query.md | command | 81 | Missing allowed-tools, missing output format |
| engineering/llm-wiki/commands/wiki-ingest.md | command | 83 | Missing allowed-tools, missing output format |
| agents/engineering-team/cs-engineering-lead.md | agent | 84 | Insufficient example blocks, vague language |
| agents/marketing/cs-demand-gen-specialist.md | agent | 85 | Vague quantifiers (ensure, optimize, appropriate, comprehensive, effective) |
| commands/prd.md | command | 85 | Insufficient detail |
| engineering-team/playwright-pro/skills/review/SKILL.md | skill | 85 | Missing name frontmatter (BUG) |
| engineering-team/playwright-pro/skills/testrail/SKILL.md | skill | 85 | Missing name + description frontmatter (BUG) |
| engineering-team/playwright-pro/skills/coverage/SKILL.md | skill | 85 | Missing name + description frontmatter (BUG) |
| engineering-team/self-improving-agent/agents/memory-analyst.md | agent | 85 | Missing name + description frontmatter (BUG) |
| engineering-team/self-improving-agent/agents/skill-extractor.md | agent | 85 | Missing name + description frontmatter (BUG) |
| engineering-team/playwright-pro/agents/test-architect.md | agent | 85 | Missing name + description frontmatter (BUG) |
| engineering-team/playwright-pro/agents/migration-planner.md | agent | 85 | Missing name + description frontmatter (BUG) |
| engineering-team/playwright-pro/agents/test-debugger.md | agent | 85 | Missing name + description frontmatter (BUG) |
| engineering-team/SKILL.md | skill | 85 | Vague quantifiers (comprehensive, appropriate) |
| product-team/saas-scaffolder/SKILL.md | skill | 85 | Multi-step workflow lacks numbered steps |
| engineering/secrets-vault-manager/SKILL.md | skill | 85 | Vague quantifiers, incomplete description |
| engineering/llm-cost-optimizer/SKILL.md | skill | 85 | Truncated description mid-word |
| ra-qm-team/soc2-compliance/SKILL.md | skill | 85 | Description field contains only usage prompt |
| finance/business-investment-advisor/SKILL.md | skill | 78 | Heavy vague quantifiers (appropriate, relevant, various, comprehensive, robust) |
| finance/saas-metrics-coach/SKILL.md | skill | 82 | Only one example on agents |
| .claude/commands/README.md | command | 75 | Multi-step without numbering, vague quantifiers |
| .claude/commands/seo-auditor.md | command | 75 | Multi-step without numbering, vague quantifiers |
| c-level-advisor/coo-advisor/SKILL.md | skill | 75 | Vague quantifiers exceed cap |
| c-level-advisor/cmo-advisor/SKILL.md | skill | 75 | Vague quantifiers exceed cap |
| commands/competitive-matrix.md | command | 65 | Missing output format, allowed-tools, no numbered steps, no empty input handling |
| agents/c-level/cs-ceo-advisor.md | agent | 86 | Excessive vague quantifiers (ensure, effective, strategic, robust, optimize, comprehensive) |
| agents/c-level/cs-cto-advisor.md | agent | 86 | Excessive vague quantifiers |
| agents/business-growth/cs-growth-strategist.md | agent | 87 | Vague quantifiers (ensure, appropriate, effective, comprehensive) |
| agents/engineering-team/cs-workspace-admin.md | agent | 87 | Vague quantifiers (ensure, proper, appropriate, effective) |
| agents/engineering/cs-senior-engineer.md | agent | 87 | Vague quantifiers |
| agents/personas/growth-marketer.md | persona | 87 | Vague quantifiers |
| agents/personas/product-manager.md | persona | 87 | Vague quantifiers |
| agents/product/cs-agile-product-owner.md | agent | 87 | Vague quantifiers |
| agents/product/cs-ux-researcher.md | agent | 87 | Vague quantifiers |
| agents/product/cs-product-strategist.md | agent | 85 | Vague quantifiers |
| product-team/roadmap-communicator/SKILL.md | skill | 88 | Missing description required field |
| product-team/product-discovery/SKILL.md | skill | 88 | Missing description field |
| product-team/apple-hig-expert/SKILL.md | skill | 88 | Missing name required field |
| marketing-skill/prompt-engineer-toolkit/SKILL.md | skill | 88 | Missing name/description, vague quantifiers |
| marketing-skill/content-creator/SKILL.md | skill | 88 | Missing description field, vague quantifiers |
| engineering-team/self-improving-agent/skills/review/SKILL.md | skill | 88 | Vague quantifiers (comprehensive x3, appropriate x2) |
| engineering-team/playwright-pro/skills/migrate/SKILL.md | skill | 88 | Missing name + description frontmatter (BUG) |
| engineering-team/playwright-pro/skills/generate/SKILL.md | skill | 88 | Missing name + description frontmatter (BUG) |
| engineering-team/playwright-pro/skills/report/SKILL.md | skill | 88 | Missing name + description frontmatter (BUG) |
| engineering-team/playwright-pro/skills/browserstack/SKILL.md | skill | 88 | Missing description frontmatter (BUG) |
| c-level-advisor/strategic-alignment/SKILL.md | skill | 88 | Vague quantifiers (relevant x3) |
| engineering-team/CLAUDE.md | config | 88 | Vague quantifiers (comprehensive, appropriate, ensure) |
| agents/finance/cs-financial-analyst.md | agent | 89 | Vague quantifiers (ensure, comprehensive, robust) |
| agents/ra-qm-team/cs-quality-regulatory.md | agent | 89 | Vague quantifiers |
| agents/personas/solo-founder.md | persona | 89 | Vague quantifiers |
| agents/personas/finance-lead.md | persona | 89 | Vague quantifiers |
| agents/product/cs-product-manager.md | agent | 85 | Vague quantifiers |
| commands/a11y-audit.md | command | 90 | Multi-step without numbered steps |
| commands/google-workspace.md | command | 90 | Multi-step without numbered steps |
| .claude/commands/git/clean.md | command | 90 | No output format specified |
| .claude/commands/git/cm.md | command | 90 | Multi-step without numbered steps |
| project-management/atlassian-admin/SKILL.md | skill | 90 | Vague quantifiers (appropriate, comprehensive, relevant, proper, effective) |
| finance/financial-analyst/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/context-engine/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/cs-onboard/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/board-deck-builder/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/org-health-diagnostic/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/internal-narrative/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/ceo-advisor/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/cpo-advisor/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/founder-coach/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/cto-advisor/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/company-os/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/competitive-intel/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/cfo-advisor/SKILL.md | skill | 90 | Minor vague quantifiers |
| c-level-advisor/executive-mentor/SKILL.md | skill | 90 | Minor vague quantifiers |
| ra-qm-team/information-security-manager-iso27001/SKILL.md | skill | 90 | Incomplete description, vague quantifiers |
| business-growth/contract-and-proposal-writer/SKILL.md | skill | 90 | Vague quantifiers |
| engineering/migration-architect/SKILL.md | skill | 90 | Vague quantifiers |
| engineering/SKILL.md | skill | 90 | Vague quantifiers (advanced, comprehensive) |
| engineering-team/self-improving-agent/CLAUDE.md | config | 90 | Vague quantifiers |
| engineering-team/incident-commander/SKILL.md | skill | 90 | Missing description detail |
| engineering-team/google-workspace-cli/SKILL.md | skill | 92 | Missing examples |
| engineering-team/email-template-builder/SKILL.md | skill | 92 | Vague quantifiers (appropriate, ensure, proper) |
| engineering-team/tech-stack-evaluator/SKILL.md | skill | 92 | Vague quantifiers (appropriate x2) |
| engineering-team/self-improving-agent/skills/status/SKILL.md | skill | 92 | Vague quantifiers (appropriate x2) |
| engineering-team/self-improving-agent/skills/extract/SKILL.md | skill | 92 | Vague quantifiers |
| engineering-team/senior-qa/SKILL.md | skill | 92 | Vague quantifiers (comprehensive, appropriate) |
| engineering-team/epic-design/SKILL.md | skill | 92 | Vague quantifiers (appropriate x3, ensure) |
| product-team/competitive-teardown/SKILL.md | skill | 92 | Vague quantifiers |
| product-team/ui-design-system/SKILL.md | skill | 92 | Vague quantifiers |
| project-management/atlassian-templates/SKILL.md | skill | 92 | Vague quantifiers |
| agents/personas/devops-engineer.md | persona | 92 | Clean |
| marketing-skill/copywriting/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/form-cro/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/content-production/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/app-store-optimization/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/free-tool-strategy/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/marketing-psychology/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/launch-strategy/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/site-architecture/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/video-content-strategist/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/onboarding-cro/SKILL.md | skill | 92 | Vague quantifiers |
| marketing-skill/pricing-strategy/SKILL.md | skill | 92 | Vague quantifiers |
| engineering-team/playwright-pro/SKILL.md | skill | 93 | Vague quantifiers (appropriate x2) |
| product-team/spec-to-repo/SKILL.md | skill | 93 | Vague quantifiers |
| product-team/ux-researcher-designer/SKILL.md | skill | 93 | Vague quantifiers |
| marketing-skill/referral-program/SKILL.md | skill | 93 | Vague quantifiers |
| marketing-skill/copy-editing/SKILL.md | skill | 93 | Clean |
| marketing-skill/marketing-ops/SKILL.md | skill | 93 | Clean |
| marketing-skill/paid-ads/SKILL.md | skill | 93 | Clean |
| marketing-skill/x-twitter-growth/SKILL.md | skill | 93 | Clean |
| marketing-skill/analytics-tracking/SKILL.md | skill | 93 | Clean |
| marketing-skill/social-content/SKILL.md | skill | 93 | Clean |
| marketing-skill/signup-flow-cro/SKILL.md | skill | 93 | Clean |
| marketing-skill/campaign-analytics/SKILL.md | skill | 93 | Clean |
| agents/personas/content-strategist.md | persona | 91 | Minor vague quantifiers |
| agents/personas/startup-cto.md | persona | 91 | Minor vague quantifiers |
| engineering/llm-wiki/commands/wiki-lint.md | command | 91 | Missing allowed-tools, vague quantifiers |
| .claude/commands/plugin-audit.md | command | 90 | Vague quantifiers |
| .claude/commands/security-scan.md | command | 85 | Multi-step without numbered steps |
| .claude/commands/git/cp.md | command | 85 | Multi-step without numbered steps |
| .claude/commands/git/pr.md | command | 85 | Multi-step without numbered steps |
| engineering/llm-wiki/commands/wiki-init.md | command | 85 | Missing allowed-tools |
| engineering/llm-wiki/commands/wiki-log.md | command | 85 | Missing allowed-tools |
| product-team/landing-page-generator/SKILL.md | skill | 95 | Missing output format field |
| product-team/product-manager-toolkit/SKILL.md | skill | 95 | Clean |
| product-team/research-summarizer/SKILL.md | skill | 95 | Clean |
| product-team/product-strategist/SKILL.md | skill | 95 | Clean |
| product-team/agile-product-owner/SKILL.md | skill | 95 | Minor vague quantifiers |
| marketing-skill/social-media-manager/SKILL.md | skill | 95 | Clean |
| marketing-skill/programmatic-seo/SKILL.md | skill | 95 | Clean |
| marketing-skill/content-strategy/SKILL.md | skill | 95 | Clean |
| marketing-skill/email-sequence/SKILL.md | skill | 95 | Clean |
| marketing-skill/schema-markup/SKILL.md | skill | 95 | Clean |
| marketing-skill/seo-audit/SKILL.md | skill | 95 | Clean |
| marketing-skill/ab-test-setup/SKILL.md | skill | 95 | Clean |
| marketing-skill/page-cro/SKILL.md | skill | 95 | Clean |
| marketing-skill/competitor-alternatives/SKILL.md | skill | 95 | Clean |
| marketing-skill/cold-email/SKILL.md | skill | 95 | Clean |
| marketing-skill/ai-seo/SKILL.md | skill | 95 | Clean |
| engineering-team/tdd-guide/SKILL.md | skill | 95 | Minor vague quantifiers |
| engineering-team/self-improving-agent/SKILL.md | skill | 95 | Vague quantifiers (appropriate x2) |
| engineering-team/self-improving-agent/skills/remember/SKILL.md | skill | 95 | Vague quantifiers |
| engineering-team/self-improving-agent/skills/promote/SKILL.md | skill | 95 | Vague quantifiers (appropriate x3) |
| engineering-team/ai-security/SKILL.md | skill | 95 | Minor vague quantifiers |
| engineering-team/senior-frontend/SKILL.md | skill | 95 | Minor vague quantifiers |
| engineering-team/red-team/SKILL.md | skill | 95 | Minor vague quantifiers |
| engineering-team/threat-detection/SKILL.md | skill | 95 | Minor vague quantifiers |
| engineering-team/a11y-audit/SKILL.md | skill | 95 | Minor vague quantifiers |
| engineering-team/cloud-security/SKILL.md | skill | 95 | Minor vague quantifiers |
| ra-qm-team/SKILL.md | skill | 95 | Vague quantifiers (appropriate, relevant, suitable) |
| ra-qm-team/regulatory-affairs-head/SKILL.md | skill | 95 | Vague quantifiers |
| ra-qm-team/quality-manager-qms-iso13485/SKILL.md | skill | 95 | Vague quantifiers |
| ra-qm-team/fda-consultant-specialist/SKILL.md | skill | 95 | Minor vague quantifiers |
| ra-qm-team/isms-audit-expert/SKILL.md | skill | 95 | Minor vague quantifiers |
| business-growth/SKILL.md | skill | 95 | Vague quantifiers |
| finance/SKILL.md | skill | 95 | Clean |
| c-level-advisor/intl-expansion/SKILL.md | skill | 95 | Clean |
| c-level-advisor/ma-playbook/SKILL.md | skill | 95 | Clean |
| c-level-advisor/SKILL.md | skill | 95 | Clean |
| c-level-advisor/board-meeting/SKILL.md | skill | 95 | Clean |
| c-level-advisor/scenario-war-room/SKILL.md | skill | 95 | Clean |
| c-level-advisor/decision-logger/SKILL.md | skill | 95 | Clean |
| c-level-advisor/executive-mentor/skills/board-prep/SKILL.md | skill | 95 | Clean |
| c-level-advisor/executive-mentor/skills/hard-call/SKILL.md | skill | 95 | Clean |
| c-level-advisor/executive-mentor/skills/challenge/SKILL.md | skill | 95 | Clean |
| c-level-advisor/executive-mentor/skills/postmortem/SKILL.md | skill | 95 | Clean |
| c-level-advisor/executive-mentor/skills/stress-test/SKILL.md | skill | 95 | Clean |
| c-level-advisor/executive-mentor/agents/devils-advocate.md | agent | 95 | Clean |
| engineering/mcp-server-builder/SKILL.md | skill | 95 | Minor vague quantifiers |
| agents/CLAUDE.md | config | 95 | Clean |
| agents/personas/TEMPLATE.md | template | 95 | Clean |
| .claude/commands/update-docs.md | command | 95 | Minor vague language |
| commands/wiki-init.md | command | 95 | Minor vague language |
| commands/tc.md | command | 95 | Minor vague language |
| commands/tdd.md | command | 95 | Unused tools declared |
| commands/wiki-ingest.md | command | 95 | Minor vague quantifiers |
| commands/wiki-lint.md | command | 95 | Vague language |
| commands/wiki-query.md | command | 95 | Minor vague terms |
| commands/focused-fix.md | command | 95 | Minor |
| commands/code-to-prd.md | command | 95 | Minor |
| engineering-team/playwright-pro/CLAUDE.md | config | 92 | Vague quantifiers |
| engineering-team/senior-data-scientist/SKILL.md | skill | 98 | Clean |
| engineering-team/ms365-tenant-manager/SKILL.md | skill | 98 | Clean |
| engineering-team/senior-computer-vision/SKILL.md | skill | 98 | Clean |
| engineering-team/senior-prompt-engineer/SKILL.md | skill | 98 | Clean |
| engineering-team/senior-secops/SKILL.md | skill | 98 | Clean |
| project-management/confluence-expert/SKILL.md | skill | 98 | Minor vague quantifiers |
| project-management/scrum-master/SKILL.md | skill | 98 | Minor vague quantifiers |
| project-management/team-communications/SKILL.md | skill | 98 | Minor vague quantifiers |
| engineering-team/senior-security/SKILL.md | skill | 100 | Clean |
| engineering-team/senior-devops/SKILL.md | skill | 100 | Clean |
| engineering-team/adversarial-reviewer/SKILL.md | skill | 100 | Clean |
| engineering-team/stripe-integration-expert/SKILL.md | skill | 100 | Clean |
| ra-qm-team/risk-management-specialist/SKILL.md | skill | 100 | Clean |
| ra-qm-team/gdpr-dsgvo-expert/SKILL.md | skill | 100 | Clean |
| ra-qm-team/quality-documentation-manager/SKILL.md | skill | 100 | Clean |
| ra-qm-team/capa-officer/SKILL.md | skill | 100 | Clean |
| ra-qm-team/mdr-745-specialist/SKILL.md | skill | 100 | Clean |
| ra-qm-team/qms-audit-expert/SKILL.md | skill | 100 | Clean |
| ra-qm-team/quality-manager-qmr/SKILL.md | skill | 100 | Clean |
| business-growth/revenue-operations/SKILL.md | skill | 100 | Clean |
| business-growth/sales-engineer/SKILL.md | skill | 100 | Clean |
| business-growth/customer-success-manager/SKILL.md | skill | 100 | Clean |
| engineering/terraform-patterns/SKILL.md | skill | 100 | Clean |
| engineering/helm-chart-builder/SKILL.md | skill | 100 | Clean |
| engineering/database-schema-designer/SKILL.md | skill | 100 | Clean |
| engineering/codebase-onboarding/SKILL.md | skill | 100 | Clean |
| engineering/behuman/SKILL.md | skill | 100 | Clean |
| engineering/focused-fix/SKILL.md | skill | 100 | Clean |
| engineering/skill-security-auditor/SKILL.md | skill | 100 | Clean |
| engineering/agent-designer/SKILL.md | skill | 100 | Clean |
| engineering/agent-workflow-designer/SKILL.md | skill | 100 | Clean |
| engineering/docker-development/SKILL.md | skill | 100 | Clean |
| engineering/changelog-generator/SKILL.md | skill | 100 | Clean |
| engineering/tech-debt-tracker/SKILL.md | skill | 100 | Clean |
| engineering/llm-wiki/SKILL.md | skill | 100 | Clean |
| engineering/env-secrets-manager/SKILL.md | skill | 100 | Clean |
| engineering/monorepo-navigator/SKILL.md | skill | 100 | Clean |
| engineering/release-manager/SKILL.md | skill | 100 | Clean |
| engineering/runbook-generator/SKILL.md | skill | 100 | Clean |
| engineering/statistical-analyst/SKILL.md | skill | 100 | Clean |
| engineering/api-design-reviewer/SKILL.md | skill | 100 | Clean |
| engineering/skill-tester/assets/sample-skill/SKILL.md | skill | 100 | Clean |
| engineering/skill-tester/SKILL.md | skill | 100 | Clean |
| engineering/self-eval/SKILL.md | skill | 100 | Clean |
| engineering/spec-driven-workflow/SKILL.md | skill | 100 | Clean |
| engineering/prompt-governance/SKILL.md | skill | 100 | Clean |
| engineering/tc-tracker/SKILL.md | skill | 100 | Clean |
| engineering/performance-profiler/SKILL.md | skill | 100 | Clean |
| engineering/demo-video/SKILL.md | skill | 100 | Clean |
| engineering/code-tour/SKILL.md | skill | 100 | Clean |
| engineering/database-designer/SKILL.md | skill | 100 | Clean |
| engineering/interview-system-designer/SKILL.md | skill | 100 | Clean |
| engineering/sql-database-assistant/SKILL.md | skill | 100 | Clean |
| engineering/rag-architect/SKILL.md | skill | 100 | Clean |
| engineering/dependency-auditor/SKILL.md | skill | 100 | Clean |
| engineering/browser-automation/SKILL.md | skill | 100 | Clean |
| engineering/api-test-suite-builder/SKILL.md | skill | 100 | Clean |
| engineering/git-worktree-manager/SKILL.md | skill | 100 | Clean |
| engineering/observability-designer/SKILL.md | skill | 100 | Clean |
| engineering/autoresearch-agent/SKILL.md | skill | 100 | Clean |
| engineering/autoresearch-agent/skills/setup/SKILL.md | skill | 100 | Clean |
| engineering/autoresearch-agent/skills/status/SKILL.md | skill | 100 | Clean |
| engineering/autoresearch-agent/skills/run/SKILL.md | skill | 100 | Clean |
| engineering/autoresearch-agent/skills/resume/SKILL.md | skill | 100 | Clean |
| engineering/autoresearch-agent/skills/loop/SKILL.md | skill | 100 | Clean |
| engineering/data-quality-auditor/SKILL.md | skill | 100 | Clean |
| engineering/ci-cd-pipeline-builder/SKILL.md | skill | 100 | Clean |
| engineering/pr-review-expert/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/skills/status/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/skills/run/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/skills/eval/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/skills/board/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/skills/merge/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/skills/spawn/SKILL.md | skill | 100 | Clean |
| engineering/agenthub/skills/init/SKILL.md | skill | 100 | Clean |
| project-management/meeting-analyzer/SKILL.md | skill | 96 | Minor vague quantifiers |
| project-management/jira-expert/SKILL.md | skill | 96 | Minor vague quantifiers |
| project-management/SKILL.md | config | 100 | Clean |
| CLAUDE.md | config | 100 | Clean |
| standards/CLAUDE.md | config | 100 | Clean |
| engineering-team/self-improving-agent/hooks/hooks.json | hook | 100 | Clean |
| engineering-team/playwright-pro/hooks/hooks.json | hook | 100 | Clean |
| marketing-skill/ad-creative/SKILL.md | skill | 100 | Clean |
| marketing-skill/SKILL.md | config | 100 | Clean |
| product-team/SKILL.md | config | 100 | Clean |
| commands/saas-health.md | command | 100 | Clean |
| commands/changelog.md | command | 100 | Clean |
| commands/rice.md | command | 100 | Clean |
| commands/project-health.md | command | 100 | Clean |
| commands/okr.md | command | 100 | Clean |
| commands/financial-health.md | command | 100 | Clean |
| commands/persona.md | command | 100 | Clean |
| commands/tech-debt.md | command | 100 | Clean |
| commands/pipeline.md | command | 100 | Clean |
| commands/retro.md | command | 100 | Clean |
| commands/user-story.md | command | 100 | Clean |
| commands/wiki-log.md | command | 100 | Clean |
| commands/sprint-health.md | command | 100 | Clean |
| .claude/commands/focused-fix.md | command | 100 | Clean |

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 5 |
| Medium | 2 |
| Low | 3 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | engineering-team/self-improving-agent/hooks/hooks.json, engineering-team/playwright-pro/hooks/hooks.json |
| Python scripts | engineering/autoresearch-agent/evaluators/benchmark_speed.py, benchmark_size.py, build_speed.py, test_pass_rate.py; engineering-team/google-workspace-cli/scripts/gws_recipe_runner.py; engineering/skill-security-auditor/scripts/skill_security_auditor.py |
| Shell scripts | 374 files (via scripts/ tree) |
| MCP configs | target-repo/.mcp.json |
| Package manifests | None found (no package.json / requirements.txt at root) |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | docs/plugins/index.md | 83 | curl pipe to shell | Installation instruction `curl -sL https://raw.githubusercontent.com/alirezarezvani/claude-skills/main/scripts/openclaw-install.sh \| bash` — downloads and executes arbitrary remote script; no integrity verification (no checksum, no pinned commit) |
| 2 | HIGH | engineering/autoresearch-agent/evaluators/benchmark_speed.py | 20,25 | subprocess shell=True | Dynamic command string executed with `shell=True`; if COMMAND config is attacker-influenced, enables arbitrary shell execution |
| 3 | HIGH | engineering/autoresearch-agent/evaluators/benchmark_size.py | 26,34,36 | subprocess shell=True + string interpolation | Line 36 interpolates Docker image name into shell string without quoting — direct command injection vector via image name |
| 4 | HIGH | engineering/autoresearch-agent/evaluators/build_speed.py | 20,23 | subprocess shell=True | BUILD_CMD and CLEAN_CMD executed with `shell=True`; configurable strings without sanitization |
| 5 | HIGH | engineering/autoresearch-agent/evaluators/test_pass_rate.py | 13 | subprocess shell=True | TEST_CMD executed with `shell=True`; configuration variable without validation |
| 6 | HIGH | engineering-team/google-workspace-cli/scripts/gws_recipe_runner.py | 321 | subprocess shell=True + dynamic cmd | `subprocess.run(cmd, shell=True, ...)` where `cmd` is constructed from recipe data — arbitrary shell injection via crafted recipe definitions |
| 7 | MEDIUM | .claude/commands/review.md | ~10 | Runtime package installs (unpinned) | Installs `yamllint`, `check-jsonschema`, `safety`, `markdown-link-check` at runtime without version pins; supply chain risk |
| 8 | MEDIUM | .claude/commands/security-scan.md | ~6 | Runtime privileged install | References `brew install gitleaks` at runtime — requires admin privileges; no version pin |
| 9 | LOW | engineering-team/self-improving-agent/hooks/hooks.json | — | Environment variable access | Reads `$CLAUDE_TOOL_OUTPUT`; standard Claude hook variable, no escalation risk |
| 10 | LOW | engineering-team/playwright-pro/hooks/hooks.json | — | Environment variable access | Reads tool output via stdin for path extraction; safe pattern |
| 11 | LOW | .mcp.json | — | MCP server config (stdio) | Configures tessl MCP server via stdio; no network exposure or credential storage detected |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | engineering-team/playwright-pro/skills/testrail/SKILL.md | Missing `name` and `description` frontmatter | Skill will not register correctly |
| 2 | engineering-team/playwright-pro/skills/coverage/SKILL.md | Missing `name` and `description` frontmatter | Skill will not register correctly |
| 3 | engineering-team/playwright-pro/skills/generate/SKILL.md | Missing `name` and `description` frontmatter | Skill will not register correctly |
| 4 | engineering-team/playwright-pro/skills/report/SKILL.md | Missing `name` and `description` frontmatter | Skill will not register correctly |
| 5 | engineering-team/playwright-pro/skills/migrate/SKILL.md | Missing `name` and `description` frontmatter | Skill will not register correctly |
| 6 | engineering-team/playwright-pro/skills/review/SKILL.md | Missing `name` frontmatter | Skill may not register correctly |
| 7 | engineering-team/playwright-pro/skills/browserstack/SKILL.md | Missing `description` frontmatter | Skill may not register correctly |
| 8 | engineering-team/self-improving-agent/agents/memory-analyst.md | Missing `name` and `description` frontmatter | Agent will not register correctly |
| 9 | engineering-team/self-improving-agent/agents/skill-extractor.md | Missing `name` and `description` frontmatter | Agent will not register correctly |
| 10 | engineering-team/playwright-pro/agents/test-architect.md | Missing `name` and `description` frontmatter | Agent will not register correctly |
| 11 | engineering-team/playwright-pro/agents/migration-planner.md | Missing `name` and `description` frontmatter | Agent will not register correctly |
| 12 | engineering-team/playwright-pro/agents/test-debugger.md | Missing `name` and `description` frontmatter | Agent will not register correctly |
| 13 | agents/engineering/cs-wiki-linter.md | Write/Edit tools declared on read-only auditing agent | Agent can modify files it should only read |
| 14 | agents/engineering/cs-wiki-librarian.md | Write/Edit tools declared on read-only query agent | Agent can modify files it should only read |
| 15 | agents/engineering/cs-wiki-ingestor.md | Write/Edit tools declared on read-only ingestion agent | Agent can modify files it should only read |
| 16 | commands/competitive-matrix.md | Missing `allowed-tools`, no output format, no empty input handling, no numbered steps | Command is underspecified; will produce inconsistent results |

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | .claude/commands/review.md | Runtime installs of unpinned packages (yamllint, check-jsonschema, safety, markdown-link-check) | Pin package versions or move to dev-dependency pre-install step; add `--require-hashes` for pip |
| 2 | .claude/commands/security-scan.md | Runtime `brew install gitleaks` requires admin and is unpinned | Pre-install gitleaks as dev dependency with version pin; document required version |
| 3 | engineering-team/playwright-pro/hooks/hooks.json | Environment variable reading without validation | Validate and sanitize stdin input before using as file path |
| 4 | .mcp.json | tessl MCP server registered globally | Scope MCP server to specific workspaces; audit tessl server permissions |

> **Note:** Security findings #1–6 (Critical + High) require private disclosure, not public PRs. See Recommendation below.

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/product/cs-product-analyst.md | Missing output format, minimal examples, thin documentation | -30 |
| 2 | commands/competitive-matrix.md | No numbered steps, no empty input handling, no output format | -35 |
| 3 | project-management/senior-pm/SKILL.md | Vague quantifiers exceed cap (comprehensive, optimization, ensure, appropriate, etc.) | -20 |
| 4 | c-level-advisor/coo-advisor/SKILL.md | Vague quantifiers exceed cap (appropriate x3, ensure x2, relevant x2, comprehensive, proper, suitable x2, effective, optimal, necessary) | -20 |
| 5 | c-level-advisor/cmo-advisor/SKILL.md | Vague quantifiers exceed cap (appropriate x4, relevant x5, comprehensive, ensure, effective, suitable) | -20 |
| 6 | finance/business-investment-advisor/SKILL.md | Heavy vague quantifiers (appropriate x2, relevant x3, various, comprehensive, robust, ensure, proper, suitable, efficient) | -22 (capped -20) |
| 7 | agents/c-level/cs-ceo-advisor.md | Excessive vague quantifiers (ensure, effective, strategic, robust, optimize, comprehensive, well x2) | -14 |
| 8 | agents/c-level/cs-cto-advisor.md | Excessive vague quantifiers (ensure, optimize, effective, strategic, robust, comprehensive, sustainable) | -14 |
| 9 | engineering/llm-cost-optimizer/SKILL.md | Description truncated mid-word | -10 |
| 10 | ra-qm-team/soc2-compliance/SKILL.md | Description field contains only usage prompt, not actual description | -15 |
| 11 | agents/marketing/cs-content-creator.md | Vague quantifiers (ensure, optimize, appropriate, effective, proper, improve) | -12 |
| 12 | agents/marketing/cs-demand-gen-specialist.md | Vague quantifiers (ensure, optimize, appropriate, comprehensive, effective) | -10 |
| 13 | commands/.claude/seo-auditor.md | Multi-step without numbered steps, vague quantifiers capped | -25 |
| 14 | product-team/roadmap-communicator/SKILL.md | Missing description required field | -25 |
| 15 | product-team/product-discovery/SKILL.md | Missing description required field | -25 |
| 16 | product-team/apple-hig-expert/SKILL.md | Missing name required field | -25 |
| 17 | marketing-skill/prompt-engineer-toolkit/SKILL.md | Missing name/description, vague quantifiers | -30 |
| 18 | marketing-skill/content-creator/SKILL.md | Missing description, vague quantifiers | -27 |
| 19 | engineering-team/playwright-pro/skills/review/SKILL.md | Vague quantifiers (comprehensive x5) in addition to BUG | -10 |
| 20 | agents/engineering-team/cs-engineering-lead.md | Insufficient examples (one provided, needs 3+) | -5 (examples) |
| 21 | commands/sprint-plan.md | Insufficient procedural detail, missing input format | -20 |
| 22 | Multiple files (50+) | Vague quantifiers at 1-2 instances ("appropriate", "relevant", "ensure", "comprehensive") | -2 to -6 each |

## Cross-Component

**Broken references detected:**
- `engineering/autoresearch-agent/evaluators/` — referenced by autoresearch-agent SKILL.md but the evaluator scripts contain HIGH severity `subprocess shell=True` patterns; NL quality (100) and security quality (HIGH risk) are misaligned.
- `engineering-team/playwright-pro/` — 7 sub-skill SKILL.md files missing frontmatter while parent playwright-pro/SKILL.md scores 93; sub-skills will fail to register.
- `agents/engineering/cs-wiki-*.md` — all three wiki agents (linter, librarian, ingestor) declare Write/Edit tools; contradicts their described read-only roles and the engineering/llm-wiki/ skill definitions.

**Orphaned components:**
- `docs/agents/` and `docs/commands/` — documentation mirrors of agent/command files; content is duplicated but appears to be auto-generated docs, not executable NL artifacts. No cross-component inconsistencies found within docs/ itself.

**Positive patterns:**
- All `plugin.json` files are well-formed and consistent with their parent skill/agent declarations.
- `engineering/` skill tree (autoresearch-agent, agenthub sub-skills) shows excellent NL quality (100/100) and consistent sub-skill structure.
- `ra-qm-team/` skills are unusually complete — 6 of 14 score perfect 100, indicating a high-quality authoring workflow.

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

**Reason:** 1 CRITICAL finding (curl pipe to shell in docs/plugins/index.md) and 5 HIGH findings (subprocess shell=True with dynamic inputs in evaluator scripts and gws_recipe_runner.py). These require private disclosure to the repo maintainer before any public PR activity.

**After security issues are resolved, the following PRs are safe to submit:**

1. **PR: Fix playwright-pro sub-skill frontmatter** — Add `name` and `description` to the 7 skills/agents under `engineering-team/playwright-pro/` missing registration metadata. (Bugs #1–7)
2. **PR: Fix self-improving-agent agent frontmatter** — Add `name` and `description` to memory-analyst.md and skill-extractor.md. (Bugs #8–9)
3. **PR: Remove Write/Edit from wiki agents** — cs-wiki-linter, cs-wiki-librarian, cs-wiki-ingestor should be read-only; remove Write/Edit from their tool declarations. (Bugs #13–15)
4. **PR: Fix competitive-matrix command** — Add `allowed-tools`, output format section, numbered steps, and empty input handler. (Bug #16)
5. **PR: Fix missing frontmatter in product/marketing skills** — roadmap-communicator, product-discovery, apple-hig-expert, prompt-engineer-toolkit, content-creator. (Quality #14–18)
6. **PR: Pin runtime package installs** — .claude/commands/review.md and security-scan.md. (Security Fix #1–2)
