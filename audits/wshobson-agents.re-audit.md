# NLPM Re-Audit: wshobson/agents

**Date**: 2026-04-24  |  **Artifacts**: 100  |  **Strategy**: progressive
**NL Score**: 84/100
**Bugs**: 2  |  **Quality Issues**: 202

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/developer-essentials/agents/monorepo-architect.md | agent | 15 | No YAML frontmatter (critical bug) |
| plugins/tdd-workflows/agents/tdd-orchestrator.md | agent | 83 | Missing tools; no output format; vague quantifier |
| plugins/tdd-workflows/agents/code-reviewer.md | agent | 83 | Missing tools; no output format; vague quantifier |
| plugins/seo-analysis-monitoring/agents/seo-cannibalization-detector.md | agent | 80 | Missing tools; no examples |
| plugins/seo-analysis-monitoring/agents/seo-authority-builder.md | agent | 80 | Missing tools; no examples |
| plugins/seo-analysis-monitoring/agents/seo-content-refresher.md | agent | 80 | Missing tools; no examples |
| plugins/functional-programming/agents/elixir-pro.md | agent | 80 | Missing tools; no examples |
| plugins/functional-programming/agents/haskell-pro.md | agent | 80 | Missing tools; no examples |
| plugins/content-marketing/agents/search-specialist.md | agent | 80 | Missing tools; no examples |
| plugins/hr-legal-compliance/agents/legal-advisor.md | agent | 80 | Missing tools; no examples |
| plugins/systems-programming/agents/c-pro.md | agent | 80 | Missing tools; no examples |
| plugins/systems-programming/agents/cpp-pro.md | agent | 80 | Missing tools; no examples |
| plugins/framework-migration/agents/legacy-modernizer.md | agent | 80 | Missing tools; no examples |
| plugins/payment-processing/agents/payment-integration.md | agent | 80 | Missing tools; no examples |
| plugins/javascript-typescript/agents/javascript-pro.md | agent | 80 | Missing tools; no examples |
| plugins/javascript-typescript/agents/typescript-pro.md | agent | 80 | Missing tools; no examples |
| plugins/error-diagnostics/agents/debugger.md | agent | 80 | Missing tools; no examples |
| plugins/error-diagnostics/agents/error-detective.md | agent | 80 | Missing tools; no examples |
| plugins/quantitative-trading/agents/risk-manager.md | agent | 80 | Missing tools; no examples |
| plugins/quantitative-trading/agents/quant-analyst.md | agent | 80 | Missing tools; no examples |
| plugins/web-scripting/agents/php-pro.md | agent | 80 | Missing tools; no examples |
| plugins/web-scripting/agents/ruby-pro.md | agent | 80 | Missing tools; no examples |
| plugins/seo-content-creation/agents/seo-content-planner.md | agent | 80 | Missing tools; no examples |
| plugins/seo-content-creation/agents/seo-content-writer.md | agent | 80 | Missing tools; no examples |
| plugins/seo-content-creation/agents/seo-content-auditor.md | agent | 80 | Missing tools; no examples |
| plugins/shell-scripting/agents/posix-shell-pro.md | agent | 80 | Missing tools; no examples |
| plugins/shell-scripting/agents/bash-pro.md | agent | 80 | Missing tools; no examples |
| plugins/documentation-generation/agents/reference-builder.md | agent | 80 | Missing tools; no examples |
| plugins/documentation-generation/agents/docs-architect.md | agent | 80 | Missing tools; no examples |
| plugins/documentation-generation/agents/mermaid-expert.md | agent | 80 | Missing tools; no examples |
| plugins/documentation-generation/agents/tutorial-engineer.md | agent | 80 | Missing tools; no examples |
| plugins/unit-testing/agents/debugger.md | agent | 80 | Missing tools; no examples |
| plugins/team-collaboration/agents/dx-optimizer.md | agent | 80 | Missing tools; no examples |
| plugins/seo-technical-optimization/agents/seo-snippet-hunter.md | agent | 80 | Missing tools; no examples |
| plugins/seo-technical-optimization/agents/seo-keyword-strategist.md | agent | 80 | Missing tools; no examples |
| plugins/seo-technical-optimization/agents/seo-structure-architect.md | agent | 80 | Missing tools; no examples |
| plugins/llm-application-dev/agents/vector-database-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/llm-application-dev/agents/ai-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/deployment-validation/agents/cloud-architect.md | agent | 85 | Missing tools; no output format |
| plugins/blockchain-web3/agents/blockchain-developer.md | agent | 85 | Missing tools; no output format |
| plugins/content-marketing/agents/content-marketer.md | agent | 85 | Missing tools; no output format |
| plugins/systems-programming/agents/rust-pro.md | agent | 85 | Missing tools; no output format |
| plugins/systems-programming/agents/golang-pro.md | agent | 85 | Missing tools; no output format |
| plugins/framework-migration/agents/architect-review.md | agent | 85 | Missing tools; no output format |
| plugins/database-migrations/agents/database-optimizer.md | agent | 85 | Missing tools; no output format |
| plugins/database-migrations/agents/database-admin.md | agent | 85 | Missing tools; no output format |
| plugins/codebase-cleanup/agents/code-reviewer.md | agent | 85 | Missing tools; no output format |
| plugins/codebase-cleanup/agents/test-automator.md | agent | 85 | Missing tools; no output format |
| plugins/full-stack-orchestration/agents/security-auditor.md | agent | 85 | Missing tools; no output format |
| plugins/full-stack-orchestration/agents/deployment-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/full-stack-orchestration/agents/performance-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/full-stack-orchestration/agents/test-automator.md | agent | 85 | Missing tools; no output format |
| plugins/database-cloud-optimization/agents/database-optimizer.md | agent | 85 | Missing tools; no output format |
| plugins/database-cloud-optimization/agents/cloud-architect.md | agent | 85 | Missing tools; no output format |
| plugins/business-analytics/agents/business-analyst.md | agent | 85 | Missing tools; no output format |
| plugins/backend-api-security/agents/backend-security-coder.md | agent | 85 | Missing tools; no output format |
| plugins/application-performance/agents/observability-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/application-performance/agents/frontend-developer.md | agent | 85 | Missing tools; no output format |
| plugins/application-performance/agents/performance-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/data-engineering/agents/data-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/agent-orchestration/agents/context-manager.md | agent | 85 | Missing tools; no output format |
| plugins/cicd-automation/agents/terraform-specialist.md | agent | 85 | Missing tools; no output format |
| plugins/cicd-automation/agents/cloud-architect.md | agent | 85 | Missing tools; no output format |
| plugins/cicd-automation/agents/deployment-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/cicd-automation/agents/kubernetes-architect.md | agent | 85 | Missing tools; no output format |
| plugins/cicd-automation/agents/devops-troubleshooter.md | agent | 85 | Missing tools; no output format |
| plugins/api-testing-observability/agents/api-documenter.md | agent | 85 | Missing tools; no output format |
| plugins/git-pr-workflows/agents/code-reviewer.md | agent | 85 | Missing tools; no output format |
| plugins/kubernetes-operations/agents/kubernetes-architect.md | agent | 85 | Missing tools; no output format |
| plugins/frontend-mobile-security/agents/frontend-developer.md | agent | 85 | Missing tools; no output format |
| plugins/frontend-mobile-security/agents/frontend-security-coder.md | agent | 85 | Missing tools; no output format |
| plugins/frontend-mobile-security/agents/mobile-security-coder.md | agent | 85 | Missing tools; no output format |
| plugins/julia-development/agents/julia-pro.md | agent | 85 | Missing tools; no output format |
| plugins/deployment-strategies/agents/terraform-specialist.md | agent | 85 | Missing tools; no output format |
| plugins/deployment-strategies/agents/deployment-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/api-scaffolding/agents/graphql-architect.md | agent | 85 | Missing tools; no output format |
| plugins/api-scaffolding/agents/fastapi-pro.md | agent | 85 | Missing tools; no output format |
| plugins/api-scaffolding/agents/django-pro.md | agent | 85 | Missing tools; no output format |
| plugins/documentation-generation/agents/api-documenter.md | agent | 85 | Missing tools; no output format |
| plugins/machine-learning-ops/agents/ml-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/machine-learning-ops/agents/data-scientist.md | agent | 85 | Missing tools; no output format |
| plugins/machine-learning-ops/agents/mlops-engineer.md | agent | 85 | Missing tools; no output format |
| plugins/unit-testing/agents/test-automator.md | agent | 85 | Missing tools; no output format |
| plugins/context-management/agents/context-manager.md | agent | 85 | Missing tools; no output format |
| plugins/llm-application-dev/agents/prompt-engineer.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/startup-business-analyst/agents/startup-analyst.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/c4-architecture/agents/c4-context.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/c4-architecture/agents/c4-code.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/c4-architecture/agents/c4-container.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/c4-architecture/agents/c4-component.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/hr-legal-compliance/agents/hr-pro.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/accessibility-compliance/agents/ui-visual-validator.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/database-cloud-optimization/agents/backend-architect.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/database-cloud-optimization/agents/database-architect.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/backend-api-security/agents/backend-architect.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/data-engineering/agents/backend-architect.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/api-scaffolding/agents/backend-architect.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/protect-mcp/agents/receipt-verifier.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/protect-mcp/agents/policy-enforcer.md | agent | 90 | Missing tools; single example (needs 2+) |
| plugins/conductor/agents/conductor-validator.md | agent | 100 | None |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | plugins/developer-essentials/agents/monorepo-architect.md | Missing `name` field — no YAML frontmatter block at all | Agent cannot be registered or invoked by the Claude Code plugin system |
| 2 | plugins/developer-essentials/agents/monorepo-architect.md | Missing `description` field — no YAML frontmatter block at all | Agent not discoverable; no trigger conditions defined |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | plugins/developer-essentials/agents/monorepo-architect.md | Missing `model` field (no frontmatter) | -5 |
| 2 | plugins/developer-essentials/agents/monorepo-architect.md | Missing `tools` field | -5 |
| 3 | plugins/developer-essentials/agents/monorepo-architect.md | No example blocks | -15 |
| 4 | plugins/developer-essentials/agents/monorepo-architect.md | No output format section | -10 |
| 5 | plugins/llm-application-dev/agents/vector-database-engineer.md | Missing `tools` field | -5 |
| 6 | plugins/llm-application-dev/agents/vector-database-engineer.md | No output format section | -10 |
| 7 | plugins/llm-application-dev/agents/prompt-engineer.md | Missing `tools` field | -5 |
| 8 | plugins/llm-application-dev/agents/prompt-engineer.md | Only one example block (needs 2+) | -5 |
| 9 | plugins/llm-application-dev/agents/ai-engineer.md | Missing `tools` field | -5 |
| 10 | plugins/llm-application-dev/agents/ai-engineer.md | No output format section | -10 |
| 11 | plugins/deployment-validation/agents/cloud-architect.md | Missing `tools` field | -5 |
| 12 | plugins/deployment-validation/agents/cloud-architect.md | No output format section | -10 |
| 13 | plugins/seo-analysis-monitoring/agents/seo-cannibalization-detector.md | Missing `tools` field | -5 |
| 14 | plugins/seo-analysis-monitoring/agents/seo-cannibalization-detector.md | No example blocks | -15 |
| 15 | plugins/seo-analysis-monitoring/agents/seo-authority-builder.md | Missing `tools` field | -5 |
| 16 | plugins/seo-analysis-monitoring/agents/seo-authority-builder.md | No example blocks | -15 |
| 17 | plugins/seo-analysis-monitoring/agents/seo-content-refresher.md | Missing `tools` field | -5 |
| 18 | plugins/seo-analysis-monitoring/agents/seo-content-refresher.md | No example blocks | -15 |
| 19 | plugins/c4-architecture/agents/c4-context.md | Missing `tools` field | -5 |
| 20 | plugins/c4-architecture/agents/c4-context.md | Only one example block (needs 2+) | -5 |
| 21 | plugins/c4-architecture/agents/c4-code.md | Missing `tools` field | -5 |
| 22 | plugins/c4-architecture/agents/c4-code.md | Only one example block (needs 2+) | -5 |
| 23 | plugins/c4-architecture/agents/c4-container.md | Missing `tools` field | -5 |
| 24 | plugins/c4-architecture/agents/c4-container.md | Only one example block (needs 2+) | -5 |
| 25 | plugins/c4-architecture/agents/c4-component.md | Missing `tools` field | -5 |
| 26 | plugins/c4-architecture/agents/c4-component.md | Only one example block (needs 2+) | -5 |
| 27 | plugins/functional-programming/agents/elixir-pro.md | Missing `tools` field | -5 |
| 28 | plugins/functional-programming/agents/elixir-pro.md | No example blocks | -15 |
| 29 | plugins/functional-programming/agents/haskell-pro.md | Missing `tools` field | -5 |
| 30 | plugins/functional-programming/agents/haskell-pro.md | No example blocks | -15 |
| 31 | plugins/blockchain-web3/agents/blockchain-developer.md | Missing `tools` field | -5 |
| 32 | plugins/blockchain-web3/agents/blockchain-developer.md | No output format section | -10 |
| 33 | plugins/content-marketing/agents/content-marketer.md | Missing `tools` field | -5 |
| 34 | plugins/content-marketing/agents/content-marketer.md | No output format section | -10 |
| 35 | plugins/content-marketing/agents/search-specialist.md | Missing `tools` field | -5 |
| 36 | plugins/content-marketing/agents/search-specialist.md | No example blocks | -15 |
| 37 | plugins/hr-legal-compliance/agents/hr-pro.md | Missing `tools` field | -5 |
| 38 | plugins/hr-legal-compliance/agents/hr-pro.md | Only one example block (needs 2+) | -5 |
| 39 | plugins/hr-legal-compliance/agents/legal-advisor.md | Missing `tools` field | -5 |
| 40 | plugins/hr-legal-compliance/agents/legal-advisor.md | No example blocks | -15 |
| 41 | plugins/systems-programming/agents/rust-pro.md | Missing `tools` field | -5 |
| 42 | plugins/systems-programming/agents/rust-pro.md | No output format section | -10 |
| 43 | plugins/systems-programming/agents/golang-pro.md | Missing `tools` field | -5 |
| 44 | plugins/systems-programming/agents/golang-pro.md | No output format section | -10 |
| 45 | plugins/systems-programming/agents/c-pro.md | Missing `tools` field | -5 |
| 46 | plugins/systems-programming/agents/c-pro.md | No example blocks | -15 |
| 47 | plugins/systems-programming/agents/cpp-pro.md | Missing `tools` field | -5 |
| 48 | plugins/systems-programming/agents/cpp-pro.md | No example blocks | -15 |
| 49 | plugins/framework-migration/agents/legacy-modernizer.md | Missing `tools` field | -5 |
| 50 | plugins/framework-migration/agents/legacy-modernizer.md | No example blocks | -15 |
| 51 | plugins/framework-migration/agents/architect-review.md | Missing `tools` field | -5 |
| 52 | plugins/framework-migration/agents/architect-review.md | No output format section | -10 |
| 53 | plugins/accessibility-compliance/agents/ui-visual-validator.md | Missing `tools` field | -5 |
| 54 | plugins/accessibility-compliance/agents/ui-visual-validator.md | Only one example block (needs 2+) | -5 |
| 55 | plugins/database-migrations/agents/database-optimizer.md | Missing `tools` field | -5 |
| 56 | plugins/database-migrations/agents/database-optimizer.md | No output format section | -10 |
| 57 | plugins/database-migrations/agents/database-admin.md | Missing `tools` field | -5 |
| 58 | plugins/database-migrations/agents/database-admin.md | No output format section | -10 |
| 59 | plugins/codebase-cleanup/agents/code-reviewer.md | Missing `tools` field | -5 |
| 60 | plugins/codebase-cleanup/agents/code-reviewer.md | No output format section | -10 |
| 61 | plugins/codebase-cleanup/agents/test-automator.md | Missing `tools` field | -5 |
| 62 | plugins/codebase-cleanup/agents/test-automator.md | No output format section | -10 |
| 63 | plugins/payment-processing/agents/payment-integration.md | Missing `tools` field | -5 |
| 64 | plugins/payment-processing/agents/payment-integration.md | No example blocks | -15 |
| 65 | plugins/full-stack-orchestration/agents/security-auditor.md | Missing `tools` field | -5 |
| 66 | plugins/full-stack-orchestration/agents/security-auditor.md | No output format section | -10 |
| 67 | plugins/full-stack-orchestration/agents/deployment-engineer.md | Missing `tools` field | -5 |
| 68 | plugins/full-stack-orchestration/agents/deployment-engineer.md | No output format section | -10 |
| 69 | plugins/full-stack-orchestration/agents/performance-engineer.md | Missing `tools` field | -5 |
| 70 | plugins/full-stack-orchestration/agents/performance-engineer.md | No output format section | -10 |
| 71 | plugins/full-stack-orchestration/agents/test-automator.md | Missing `tools` field | -5 |
| 72 | plugins/full-stack-orchestration/agents/test-automator.md | No output format section | -10 |
| 73 | plugins/database-cloud-optimization/agents/database-optimizer.md | Missing `tools` field | -5 |
| 74 | plugins/database-cloud-optimization/agents/database-optimizer.md | No output format section | -10 |
| 75 | plugins/database-cloud-optimization/agents/backend-architect.md | Missing `tools` field | -5 |
| 76 | plugins/database-cloud-optimization/agents/backend-architect.md | Only one example block (needs 2+) | -5 |
| 77 | plugins/database-cloud-optimization/agents/database-architect.md | Missing `tools` field | -5 |
| 78 | plugins/database-cloud-optimization/agents/database-architect.md | Only one example block (needs 2+) | -5 |
| 79 | plugins/database-cloud-optimization/agents/cloud-architect.md | Missing `tools` field | -5 |
| 80 | plugins/database-cloud-optimization/agents/cloud-architect.md | No output format section | -10 |
| 81 | plugins/javascript-typescript/agents/javascript-pro.md | Missing `tools` field | -5 |
| 82 | plugins/javascript-typescript/agents/javascript-pro.md | No example blocks | -15 |
| 83 | plugins/javascript-typescript/agents/typescript-pro.md | Missing `tools` field | -5 |
| 84 | plugins/javascript-typescript/agents/typescript-pro.md | No example blocks | -15 |
| 85 | plugins/business-analytics/agents/business-analyst.md | Missing `tools` field | -5 |
| 86 | plugins/business-analytics/agents/business-analyst.md | No output format section | -10 |
| 87 | plugins/tdd-workflows/agents/tdd-orchestrator.md | Missing `tools` field | -5 |
| 88 | plugins/tdd-workflows/agents/tdd-orchestrator.md | No output format section | -10 |
| 89 | plugins/tdd-workflows/agents/tdd-orchestrator.md | Vague quantifier: 'appropriate' (line 45) | -2 |
| 90 | plugins/tdd-workflows/agents/code-reviewer.md | Missing `tools` field | -5 |
| 91 | plugins/tdd-workflows/agents/code-reviewer.md | No output format section | -10 |
| 92 | plugins/tdd-workflows/agents/code-reviewer.md | Vague quantifier: 'appropriate' (line 22) | -2 |
| 93 | plugins/backend-api-security/agents/backend-architect.md | Missing `tools` field | -5 |
| 94 | plugins/backend-api-security/agents/backend-architect.md | Only one example block (needs 2+) | -5 |
| 95 | plugins/backend-api-security/agents/backend-security-coder.md | Missing `tools` field | -5 |
| 96 | plugins/backend-api-security/agents/backend-security-coder.md | No output format section | -10 |
| 97 | plugins/application-performance/agents/observability-engineer.md | Missing `tools` field | -5 |
| 98 | plugins/application-performance/agents/observability-engineer.md | No output format section | -10 |
| 99 | plugins/application-performance/agents/frontend-developer.md | Missing `tools` field | -5 |
| 100 | plugins/application-performance/agents/frontend-developer.md | No output format section | -10 |
| 101 | plugins/application-performance/agents/performance-engineer.md | Missing `tools` field | -5 |
| 102 | plugins/application-performance/agents/performance-engineer.md | No output format section | -10 |
| 103 | plugins/error-diagnostics/agents/debugger.md | Missing `tools` field | -5 |
| 104 | plugins/error-diagnostics/agents/debugger.md | No example blocks | -15 |
| 105 | plugins/error-diagnostics/agents/error-detective.md | Missing `tools` field | -5 |
| 106 | plugins/error-diagnostics/agents/error-detective.md | No example blocks | -15 |
| 107 | plugins/data-engineering/agents/backend-architect.md | Missing `tools` field | -5 |
| 108 | plugins/data-engineering/agents/backend-architect.md | Only one example block (needs 2+) | -5 |
| 109 | plugins/data-engineering/agents/data-engineer.md | Missing `tools` field | -5 |
| 110 | plugins/data-engineering/agents/data-engineer.md | No output format section | -10 |
| 111 | plugins/agent-orchestration/agents/context-manager.md | Missing `tools` field | -5 |
| 112 | plugins/agent-orchestration/agents/context-manager.md | No output format section | -10 |
| 113 | plugins/cicd-automation/agents/terraform-specialist.md | Missing `tools` field | -5 |
| 114 | plugins/cicd-automation/agents/terraform-specialist.md | No output format section | -10 |
| 115 | plugins/cicd-automation/agents/cloud-architect.md | Missing `tools` field | -5 |
| 116 | plugins/cicd-automation/agents/cloud-architect.md | No output format section | -10 |
| 117 | plugins/cicd-automation/agents/deployment-engineer.md | Missing `tools` field | -5 |
| 118 | plugins/cicd-automation/agents/deployment-engineer.md | No output format section | -10 |
| 119 | plugins/cicd-automation/agents/kubernetes-architect.md | Missing `tools` field | -5 |
| 120 | plugins/cicd-automation/agents/kubernetes-architect.md | No output format section | -10 |
| 121 | plugins/cicd-automation/agents/devops-troubleshooter.md | Missing `tools` field | -5 |
| 122 | plugins/cicd-automation/agents/devops-troubleshooter.md | No output format section | -10 |
| 123 | plugins/api-testing-observability/agents/api-documenter.md | Missing `tools` field | -5 |
| 124 | plugins/api-testing-observability/agents/api-documenter.md | No output format section | -10 |
| 125 | plugins/quantitative-trading/agents/risk-manager.md | Missing `tools` field | -5 |
| 126 | plugins/quantitative-trading/agents/risk-manager.md | No example blocks | -15 |
| 127 | plugins/quantitative-trading/agents/quant-analyst.md | Missing `tools` field | -5 |
| 128 | plugins/quantitative-trading/agents/quant-analyst.md | No example blocks | -15 |
| 129 | plugins/web-scripting/agents/php-pro.md | Missing `tools` field | -5 |
| 130 | plugins/web-scripting/agents/php-pro.md | No example blocks | -15 |
| 131 | plugins/web-scripting/agents/ruby-pro.md | Missing `tools` field | -5 |
| 132 | plugins/web-scripting/agents/ruby-pro.md | No example blocks | -15 |
| 133 | plugins/git-pr-workflows/agents/code-reviewer.md | Missing `tools` field | -5 |
| 134 | plugins/git-pr-workflows/agents/code-reviewer.md | No output format section | -10 |
| 135 | plugins/seo-content-creation/agents/seo-content-planner.md | Missing `tools` field | -5 |
| 136 | plugins/seo-content-creation/agents/seo-content-planner.md | No example blocks | -15 |
| 137 | plugins/seo-content-creation/agents/seo-content-writer.md | Missing `tools` field | -5 |
| 138 | plugins/seo-content-creation/agents/seo-content-writer.md | No example blocks | -15 |
| 139 | plugins/seo-content-creation/agents/seo-content-auditor.md | Missing `tools` field | -5 |
| 140 | plugins/seo-content-creation/agents/seo-content-auditor.md | No example blocks | -15 |
| 141 | plugins/kubernetes-operations/agents/kubernetes-architect.md | Missing `tools` field | -5 |
| 142 | plugins/kubernetes-operations/agents/kubernetes-architect.md | No output format section | -10 |
| 143 | plugins/frontend-mobile-security/agents/frontend-developer.md | Missing `tools` field | -5 |
| 144 | plugins/frontend-mobile-security/agents/frontend-developer.md | No output format section | -10 |
| 145 | plugins/frontend-mobile-security/agents/frontend-security-coder.md | Missing `tools` field | -5 |
| 146 | plugins/frontend-mobile-security/agents/frontend-security-coder.md | No output format section | -10 |
| 147 | plugins/frontend-mobile-security/agents/mobile-security-coder.md | Missing `tools` field | -5 |
| 148 | plugins/frontend-mobile-security/agents/mobile-security-coder.md | No output format section | -10 |
| 149 | plugins/julia-development/agents/julia-pro.md | Missing `tools` field | -5 |
| 150 | plugins/julia-development/agents/julia-pro.md | No output format section | -10 |
| 151 | plugins/deployment-strategies/agents/terraform-specialist.md | Missing `tools` field | -5 |
| 152 | plugins/deployment-strategies/agents/terraform-specialist.md | No output format section | -10 |
| 153 | plugins/deployment-strategies/agents/deployment-engineer.md | Missing `tools` field | -5 |
| 154 | plugins/deployment-strategies/agents/deployment-engineer.md | No output format section | -10 |
| 155 | plugins/api-scaffolding/agents/graphql-architect.md | Missing `tools` field | -5 |
| 156 | plugins/api-scaffolding/agents/graphql-architect.md | No output format section | -10 |
| 157 | plugins/api-scaffolding/agents/backend-architect.md | Missing `tools` field | -5 |
| 158 | plugins/api-scaffolding/agents/backend-architect.md | Only one example block (needs 2+) | -5 |
| 159 | plugins/api-scaffolding/agents/fastapi-pro.md | Missing `tools` field | -5 |
| 160 | plugins/api-scaffolding/agents/fastapi-pro.md | No output format section | -10 |
| 161 | plugins/api-scaffolding/agents/django-pro.md | Missing `tools` field | -5 |
| 162 | plugins/api-scaffolding/agents/django-pro.md | No output format section | -10 |
| 163 | plugins/startup-business-analyst/agents/startup-analyst.md | Missing `tools` field | -5 |
| 164 | plugins/startup-business-analyst/agents/startup-analyst.md | Only one example block (needs 2+) | -5 |
| 165 | plugins/shell-scripting/agents/posix-shell-pro.md | Missing `tools` field | -5 |
| 166 | plugins/shell-scripting/agents/posix-shell-pro.md | No example blocks | -15 |
| 167 | plugins/shell-scripting/agents/bash-pro.md | Missing `tools` field | -5 |
| 168 | plugins/shell-scripting/agents/bash-pro.md | No example blocks | -15 |
| 169 | plugins/documentation-generation/agents/reference-builder.md | Missing `tools` field | -5 |
| 170 | plugins/documentation-generation/agents/reference-builder.md | No example blocks | -15 |
| 171 | plugins/documentation-generation/agents/docs-architect.md | Missing `tools` field | -5 |
| 172 | plugins/documentation-generation/agents/docs-architect.md | No example blocks | -15 |
| 173 | plugins/documentation-generation/agents/mermaid-expert.md | Missing `tools` field | -5 |
| 174 | plugins/documentation-generation/agents/mermaid-expert.md | No example blocks | -15 |
| 175 | plugins/documentation-generation/agents/api-documenter.md | Missing `tools` field | -5 |
| 176 | plugins/documentation-generation/agents/api-documenter.md | No output format section | -10 |
| 177 | plugins/documentation-generation/agents/tutorial-engineer.md | Missing `tools` field | -5 |
| 178 | plugins/documentation-generation/agents/tutorial-engineer.md | No example blocks | -15 |
| 179 | plugins/protect-mcp/agents/receipt-verifier.md | Missing `tools` field (uses Bash but undeclared) | -5 |
| 180 | plugins/protect-mcp/agents/receipt-verifier.md | Only one example block (needs 2+) | -5 |
| 181 | plugins/protect-mcp/agents/policy-enforcer.md | Missing `tools` field | -5 |
| 182 | plugins/protect-mcp/agents/policy-enforcer.md | Only one example block (needs 2+) | -5 |
| 183 | plugins/machine-learning-ops/agents/ml-engineer.md | Missing `tools` field | -5 |
| 184 | plugins/machine-learning-ops/agents/ml-engineer.md | No output format section | -10 |
| 185 | plugins/machine-learning-ops/agents/data-scientist.md | Missing `tools` field | -5 |
| 186 | plugins/machine-learning-ops/agents/data-scientist.md | No output format section | -10 |
| 187 | plugins/machine-learning-ops/agents/mlops-engineer.md | Missing `tools` field | -5 |
| 188 | plugins/machine-learning-ops/agents/mlops-engineer.md | No output format section | -10 |
| 189 | plugins/unit-testing/agents/debugger.md | Missing `tools` field | -5 |
| 190 | plugins/unit-testing/agents/debugger.md | No example blocks | -15 |
| 191 | plugins/unit-testing/agents/test-automator.md | Missing `tools` field | -5 |
| 192 | plugins/unit-testing/agents/test-automator.md | No output format section | -10 |
| 193 | plugins/team-collaboration/agents/dx-optimizer.md | Missing `tools` field | -5 |
| 194 | plugins/team-collaboration/agents/dx-optimizer.md | No example blocks | -15 |
| 195 | plugins/context-management/agents/context-manager.md | Missing `tools` field | -5 |
| 196 | plugins/context-management/agents/context-manager.md | No output format section | -10 |
| 197 | plugins/seo-technical-optimization/agents/seo-snippet-hunter.md | Missing `tools` field | -5 |
| 198 | plugins/seo-technical-optimization/agents/seo-snippet-hunter.md | No example blocks | -15 |
| 199 | plugins/seo-technical-optimization/agents/seo-keyword-strategist.md | Missing `tools` field | -5 |
| 200 | plugins/seo-technical-optimization/agents/seo-keyword-strategist.md | No example blocks | -15 |
| 201 | plugins/seo-technical-optimization/agents/seo-structure-architect.md | Missing `tools` field | -5 |
| 202 | plugins/seo-technical-optimization/agents/seo-structure-architect.md | No example blocks | -15 |

## Cross-Component

- **Conductor plugin is the reference implementation**: `conductor-validator` is the only agent to declare `tools`, specify an output format, and include example commands. Its pattern (frontmatter + tools + output format + examples) is the target for all 99 remaining agents.
- **Backend-architect pattern reused across 5 plugins**: The `backend-architect` agent definition (database-cloud-optimization, backend-api-security, data-engineering, api-scaffolding) shares the single-example pattern. Adding one more example to each would lift all five from 90 to 95.
- **SEO cluster is internally consistent but example-poor**: All 9 SEO agents (3 in seo-analysis-monitoring, 3 in seo-content-creation, 3 in seo-technical-optimization) follow the same structure. Six have zero examples; three have output format. Fixing the six zero-example agents would raise the entire cluster from 80 to 85.
- **No broken cross-references or orphaned components detected** across the 47 audited plugins.

## Recommendation

The repo is structurally sound and internally consistent at 84/100, held back primarily by two mechanical omissions — missing `tools` declarations (99 of 100 agents) and missing output format sections (50 agents) — both of which can be fixed in bulk using the conductor-validator agent as the reference template.
