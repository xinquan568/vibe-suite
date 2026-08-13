# Re-Audit: wshobson/agents

**Date**: 2026-04-24  |  **Before**: `unknown` (—)  |  **After**: `27a7ed9` (84/100)

## Summary

| Outcome | Count |
|---------|------:|
| fixed — our PR merged | 13 |
| fixed — upstream, not via our PR | 24 |
| newly introduced (regressions) | 204 |

## Original findings — verification

| # | File | Line | Rule | Pattern | Outcome | PR |
|---|------|------|------|---------|---------|----|
| 1 | `plugins/security-scanning/agents/threat-modeling-expert.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #488 |
| 2 | `plugins/meigen-ai-design/agents/prompt-crafter.md` | — | BUG-missing-frontmatter | `missing-name` | fixed — our PR merged | #489 |
| 3 | `plugins/meigen-ai-design/agents/gallery-researcher.md` | — | BUG-missing-frontmatter | `missing-name` | fixed — our PR merged | #489 |
| 4 | `plugins/meigen-ai-design/agents/image-generator.md` | — | BUG-missing-frontmatter | `missing-name` | fixed — our PR merged | #489 |
| 5 | `plugins/deployment-validation/commands/config-validate.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 6 | `plugins/c4-architecture/commands/c4-architecture.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #492 |
| 7 | `plugins/systems-programming/commands/rust-project.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 8 | `plugins/framework-migration/commands/code-migrate.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #492 |
| 9 | `plugins/framework-migration/commands/deps-upgrade.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #492 |
| 10 | `plugins/accessibility-compliance/commands/accessibility-audit.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 11 | `plugins/codebase-cleanup/commands/tech-debt.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #490 |
| 12 | `plugins/codebase-cleanup/commands/deps-audit.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #490 |
| 13 | `plugins/codebase-cleanup/commands/refactor-clean.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #490 |
| 14 | `plugins/database-cloud-optimization/commands/cost-optimize.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 15 | `plugins/javascript-typescript/commands/typescript-scaffold.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 16 | `plugins/tdd-workflows/commands/tdd-refactor.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 17 | `plugins/error-diagnostics/commands/error-trace.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #491 |
| 18 | `plugins/error-diagnostics/commands/error-analysis.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #491 |
| 19 | `plugins/error-diagnostics/commands/smart-debug.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #491 |
| 20 | `plugins/security-scanning/agents/security-auditor.md` | — | CC-duplication | `duplicate-file` | fixed — upstream, not via our PR |  |
| 21 | `plugins/code-documentation/agents/code-reviewer.md` | — | CC-duplication | `duplicate-file` | fixed — upstream, not via our PR |  |
| 22 | `plugins/observability-monitoring/agents/performance-engineer.md` | — | CC-duplication | `duplicate-file` | fixed — upstream, not via our PR |  |
| 23 | `plugins/jvm-languages/agents/scala-pro.md` | — | R09 | `no-examples` | fixed — upstream, not via our PR |  |
| 24 | `plugins/database-migrations/commands/sql-migrations.md` | — | UNCLASSIFIED | `use-toolaccess-field-instead-of-standard` | fixed — upstream, not via our PR |  |
| 25 | `migration-observability.md` | — | UNCLASSIFIED | `use-toolaccess-field-instead-of-standard` | fixed — upstream, not via our PR |  |
| 26 | `30+ commands across all plugins` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 27 | `plugins/arm-cortex-microcontrollers/agents/arm-cortex-expert.md` | — | UNCLASSIFIED | `tools-empty-array-agent-has-no-tool-acce` | fixed — upstream, not via our PR |  |
| 28 | `plugins/full-stack-orchestration/commands/full-stack-feature.md` | — | UNCLASSIFIED | `critical-behavioral-rules-blocks-with-10` | fixed — upstream, not via our PR |  |
| 29 | `plugins/tdd-workflows/commands/tdd-cycle.md` | — | UNCLASSIFIED | `critical-behavioral-rules-blocks-with-10` | fixed — upstream, not via our PR |  |
| 30 | `plugins/application-performance/commands/performance-optimization.md` | — | UNCLASSIFIED | `critical-behavioral-rules-blocks-with-10` | fixed — upstream, not via our PR |  |
| 31 | `plugins/tdd-workflows/commands/tdd-red.md` | — | UNCLASSIFIED | `critical-behavioral-rules-blocks-with-10` | fixed — upstream, not via our PR |  |
| 32 | `plugins/tdd-workflows/commands/tdd-green.md` | — | UNCLASSIFIED | `critical-behavioral-rules-blocks-with-10` | fixed — upstream, not via our PR |  |
| 33 | `plugins/functional-programming/agents/elixir-pro.md` | — | UNCLASSIFIED | `no-formal-example-interactions-section-o` | fixed — upstream, not via our PR |  |
| 34 | `haskell-pro.md` | — | UNCLASSIFIED | `no-formal-example-interactions-section-o` | fixed — upstream, not via our PR |  |
| 35 | `plugins/jvm-languages/agents/csharp-pro.md` | — | UNCLASSIFIED | `no-formal-example-interactions-section-o` | fixed — upstream, not via our PR |  |
| 36 | `plugins/game-development/agents/minecraft-bukkit-pro.md` | — | UNCLASSIFIED | `no-formal-example-interactions-section-o` | fixed — upstream, not via our PR |  |
| 37 | `plugins/arm-cortex-microcontrollers/agents/arm-cortex-expert.md` | — | UNCLASSIFIED | `uses-model-inherit-for-deeply-technical` | fixed — upstream, not via our PR |  |

## Findings introduced since audit

These findings appear in the re-audit but were not in the original audit. They may be true regressions (new commits introduced them) or artifacts of scoring drift.

| # | File | Line | Rule | Pattern | Description |
|---|------|------|------|---------|-------------|
| 1 | `plugins/developer-essentials/agents/monorepo-architect.md` | 1 | BUG-missing-frontmatter | `missing-frontmatter-name` | Agent file has no YAML frontmatter block; name field is absent |
| 2 | `plugins/developer-essentials/agents/monorepo-architect.md` | 1 | BUG-missing-description | `missing-frontmatter-description` | Agent file has no YAML frontmatter block; description field is absent |
| 3 | `plugins/developer-essentials/agents/monorepo-architect.md` | 1 | R10 | `missing-model` | Agent file has no YAML frontmatter block; model field is absent |
| 4 | `plugins/developer-essentials/agents/monorepo-architect.md` | 1 | R11 | `missing-tools` | No tools field declared in frontmatter; agent inherits full tool surface |
| 5 | `plugins/developer-essentials/agents/monorepo-architect.md` | 1 | R09 | `missing-examples` | No example interactions provided; triggering accuracy will suffer |
| 6 | `plugins/developer-essentials/agents/monorepo-architect.md` | 1 | R12 | `missing-output-format` | No output format specification; callers cannot predict agent output structure |
| 7 | `plugins/llm-application-dev/agents/vector-database-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared; agent inherits full tool surface |
| 8 | `plugins/llm-application-dev/agents/vector-database-engineer.md` | 4 | R12 | `missing-output-format` | No output format section; agent has Example Tasks but no output specification |
| 9 | `plugins/llm-application-dev/agents/prompt-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared; agent inherits full tool surface |
| 10 | `plugins/llm-application-dev/agents/prompt-engineer.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 11 | `plugins/llm-application-dev/agents/ai-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared; agent inherits full tool surface |
| 12 | `plugins/llm-application-dev/agents/ai-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 13 | `plugins/deployment-validation/agents/cloud-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 14 | `plugins/deployment-validation/agents/cloud-architect.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 15 | `plugins/seo-analysis-monitoring/agents/seo-cannibalization-detector.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 16 | `plugins/seo-analysis-monitoring/agents/seo-cannibalization-detector.md` | 4 | R09 | `missing-examples` | No example interactions |
| 17 | `plugins/seo-analysis-monitoring/agents/seo-authority-builder.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 18 | `plugins/seo-analysis-monitoring/agents/seo-authority-builder.md` | 4 | R09 | `missing-examples` | No example interactions |
| 19 | `plugins/seo-analysis-monitoring/agents/seo-content-refresher.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 20 | `plugins/seo-analysis-monitoring/agents/seo-content-refresher.md` | 4 | R09 | `missing-examples` | No example interactions |
| 21 | `plugins/c4-architecture/agents/c4-context.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 22 | `plugins/c4-architecture/agents/c4-context.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 23 | `plugins/c4-architecture/agents/c4-code.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 24 | `plugins/c4-architecture/agents/c4-code.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 25 | `plugins/c4-architecture/agents/c4-container.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 26 | `plugins/c4-architecture/agents/c4-container.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 27 | `plugins/c4-architecture/agents/c4-component.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 28 | `plugins/c4-architecture/agents/c4-component.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 29 | `plugins/functional-programming/agents/elixir-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 30 | `plugins/functional-programming/agents/elixir-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 31 | `plugins/functional-programming/agents/haskell-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 32 | `plugins/functional-programming/agents/haskell-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 33 | `plugins/blockchain-web3/agents/blockchain-developer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 34 | `plugins/blockchain-web3/agents/blockchain-developer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 35 | `plugins/content-marketing/agents/content-marketer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 36 | `plugins/content-marketing/agents/content-marketer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 37 | `plugins/content-marketing/agents/search-specialist.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 38 | `plugins/content-marketing/agents/search-specialist.md` | 4 | R09 | `missing-examples` | No example interactions |
| 39 | `plugins/hr-legal-compliance/agents/hr-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 40 | `plugins/hr-legal-compliance/agents/hr-pro.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 41 | `plugins/hr-legal-compliance/agents/legal-advisor.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 42 | `plugins/hr-legal-compliance/agents/legal-advisor.md` | 4 | R09 | `missing-examples` | No example interactions |
| 43 | `plugins/systems-programming/agents/rust-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 44 | `plugins/systems-programming/agents/rust-pro.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 45 | `plugins/systems-programming/agents/golang-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 46 | `plugins/systems-programming/agents/golang-pro.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 47 | `plugins/systems-programming/agents/c-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 48 | `plugins/systems-programming/agents/c-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 49 | `plugins/systems-programming/agents/cpp-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 50 | `plugins/systems-programming/agents/cpp-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 51 | `plugins/framework-migration/agents/legacy-modernizer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 52 | `plugins/framework-migration/agents/legacy-modernizer.md` | 4 | R09 | `missing-examples` | No example interactions |
| 53 | `plugins/framework-migration/agents/architect-review.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 54 | `plugins/framework-migration/agents/architect-review.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 55 | `plugins/accessibility-compliance/agents/ui-visual-validator.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 56 | `plugins/accessibility-compliance/agents/ui-visual-validator.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 57 | `plugins/database-migrations/agents/database-optimizer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 58 | `plugins/database-migrations/agents/database-optimizer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 59 | `plugins/database-migrations/agents/database-admin.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 60 | `plugins/database-migrations/agents/database-admin.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 61 | `plugins/codebase-cleanup/agents/code-reviewer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 62 | `plugins/codebase-cleanup/agents/code-reviewer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 63 | `plugins/codebase-cleanup/agents/test-automator.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 64 | `plugins/codebase-cleanup/agents/test-automator.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 65 | `plugins/payment-processing/agents/payment-integration.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 66 | `plugins/payment-processing/agents/payment-integration.md` | 4 | R09 | `missing-examples` | No example interactions |
| 67 | `plugins/full-stack-orchestration/agents/security-auditor.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 68 | `plugins/full-stack-orchestration/agents/security-auditor.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 69 | `plugins/full-stack-orchestration/agents/deployment-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 70 | `plugins/full-stack-orchestration/agents/deployment-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 71 | `plugins/full-stack-orchestration/agents/performance-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 72 | `plugins/full-stack-orchestration/agents/performance-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 73 | `plugins/full-stack-orchestration/agents/test-automator.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 74 | `plugins/full-stack-orchestration/agents/test-automator.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 75 | `plugins/database-cloud-optimization/agents/database-optimizer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 76 | `plugins/database-cloud-optimization/agents/database-optimizer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 77 | `plugins/database-cloud-optimization/agents/backend-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 78 | `plugins/database-cloud-optimization/agents/backend-architect.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 79 | `plugins/database-cloud-optimization/agents/database-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 80 | `plugins/database-cloud-optimization/agents/database-architect.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 81 | `plugins/database-cloud-optimization/agents/cloud-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 82 | `plugins/database-cloud-optimization/agents/cloud-architect.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 83 | `plugins/javascript-typescript/agents/javascript-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 84 | `plugins/javascript-typescript/agents/javascript-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 85 | `plugins/javascript-typescript/agents/typescript-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 86 | `plugins/javascript-typescript/agents/typescript-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 87 | `plugins/business-analytics/agents/business-analyst.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 88 | `plugins/business-analytics/agents/business-analyst.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 89 | `plugins/tdd-workflows/agents/tdd-orchestrator.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 90 | `plugins/tdd-workflows/agents/tdd-orchestrator.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 91 | `plugins/tdd-workflows/agents/tdd-orchestrator.md` | 45 | R01 | `vague-quantifier` | Vague word: 'appropriate' — underspecifies behavior |
| 92 | `plugins/tdd-workflows/agents/code-reviewer.md` | 4 | R11 | `missing-tools` | No tools field declared; code-reviewer should restrict to read-only tools |
| 93 | `plugins/tdd-workflows/agents/code-reviewer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 94 | `plugins/tdd-workflows/agents/code-reviewer.md` | 22 | R01 | `vague-quantifier` | Vague word: 'appropriate' — underspecifies analysis scope |
| 95 | `plugins/backend-api-security/agents/backend-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 96 | `plugins/backend-api-security/agents/backend-architect.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 97 | `plugins/backend-api-security/agents/backend-security-coder.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 98 | `plugins/backend-api-security/agents/backend-security-coder.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 99 | `plugins/application-performance/agents/observability-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 100 | `plugins/application-performance/agents/observability-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 101 | `plugins/application-performance/agents/frontend-developer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 102 | `plugins/application-performance/agents/frontend-developer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 103 | `plugins/application-performance/agents/performance-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 104 | `plugins/application-performance/agents/performance-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 105 | `plugins/error-diagnostics/agents/debugger.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 106 | `plugins/error-diagnostics/agents/debugger.md` | 4 | R09 | `missing-examples` | No example interactions |
| 107 | `plugins/error-diagnostics/agents/error-detective.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 108 | `plugins/error-diagnostics/agents/error-detective.md` | 4 | R09 | `missing-examples` | No example interactions |
| 109 | `plugins/data-engineering/agents/backend-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 110 | `plugins/data-engineering/agents/backend-architect.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 111 | `plugins/data-engineering/agents/data-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 112 | `plugins/data-engineering/agents/data-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 113 | `plugins/agent-orchestration/agents/context-manager.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 114 | `plugins/agent-orchestration/agents/context-manager.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 115 | `plugins/cicd-automation/agents/terraform-specialist.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 116 | `plugins/cicd-automation/agents/terraform-specialist.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 117 | `plugins/cicd-automation/agents/cloud-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 118 | `plugins/cicd-automation/agents/cloud-architect.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 119 | `plugins/cicd-automation/agents/deployment-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 120 | `plugins/cicd-automation/agents/deployment-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 121 | `plugins/cicd-automation/agents/kubernetes-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 122 | `plugins/cicd-automation/agents/kubernetes-architect.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 123 | `plugins/cicd-automation/agents/devops-troubleshooter.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 124 | `plugins/cicd-automation/agents/devops-troubleshooter.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 125 | `plugins/api-testing-observability/agents/api-documenter.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 126 | `plugins/api-testing-observability/agents/api-documenter.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 127 | `plugins/quantitative-trading/agents/risk-manager.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 128 | `plugins/quantitative-trading/agents/risk-manager.md` | 4 | R09 | `missing-examples` | No example interactions |
| 129 | `plugins/quantitative-trading/agents/quant-analyst.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 130 | `plugins/quantitative-trading/agents/quant-analyst.md` | 4 | R09 | `missing-examples` | No example interactions |
| 131 | `plugins/web-scripting/agents/php-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 132 | `plugins/web-scripting/agents/php-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 133 | `plugins/web-scripting/agents/ruby-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 134 | `plugins/web-scripting/agents/ruby-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 135 | `plugins/git-pr-workflows/agents/code-reviewer.md` | 4 | R11 | `missing-tools` | No tools field declared; reviewer should be read-only |
| 136 | `plugins/git-pr-workflows/agents/code-reviewer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 137 | `plugins/seo-content-creation/agents/seo-content-planner.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 138 | `plugins/seo-content-creation/agents/seo-content-planner.md` | 4 | R09 | `missing-examples` | No example interactions |
| 139 | `plugins/seo-content-creation/agents/seo-content-writer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 140 | `plugins/seo-content-creation/agents/seo-content-writer.md` | 4 | R09 | `missing-examples` | No example interactions |
| 141 | `plugins/seo-content-creation/agents/seo-content-auditor.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 142 | `plugins/seo-content-creation/agents/seo-content-auditor.md` | 4 | R09 | `missing-examples` | No example interactions |
| 143 | `plugins/kubernetes-operations/agents/kubernetes-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 144 | `plugins/kubernetes-operations/agents/kubernetes-architect.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 145 | `plugins/frontend-mobile-security/agents/frontend-developer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 146 | `plugins/frontend-mobile-security/agents/frontend-developer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 147 | `plugins/frontend-mobile-security/agents/frontend-security-coder.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 148 | `plugins/frontend-mobile-security/agents/frontend-security-coder.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 149 | `plugins/frontend-mobile-security/agents/mobile-security-coder.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 150 | `plugins/frontend-mobile-security/agents/mobile-security-coder.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 151 | `plugins/julia-development/agents/julia-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 152 | `plugins/julia-development/agents/julia-pro.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 153 | `plugins/deployment-strategies/agents/terraform-specialist.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 154 | `plugins/deployment-strategies/agents/terraform-specialist.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 155 | `plugins/deployment-strategies/agents/deployment-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 156 | `plugins/deployment-strategies/agents/deployment-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 157 | `plugins/api-scaffolding/agents/graphql-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 158 | `plugins/api-scaffolding/agents/graphql-architect.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 159 | `plugins/api-scaffolding/agents/backend-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 160 | `plugins/api-scaffolding/agents/backend-architect.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 161 | `plugins/api-scaffolding/agents/fastapi-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 162 | `plugins/api-scaffolding/agents/fastapi-pro.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 163 | `plugins/api-scaffolding/agents/django-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 164 | `plugins/api-scaffolding/agents/django-pro.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 165 | `plugins/startup-business-analyst/agents/startup-analyst.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 166 | `plugins/startup-business-analyst/agents/startup-analyst.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 167 | `plugins/shell-scripting/agents/posix-shell-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 168 | `plugins/shell-scripting/agents/posix-shell-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 169 | `plugins/shell-scripting/agents/bash-pro.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 170 | `plugins/shell-scripting/agents/bash-pro.md` | 4 | R09 | `missing-examples` | No example interactions |
| 171 | `plugins/documentation-generation/agents/reference-builder.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 172 | `plugins/documentation-generation/agents/reference-builder.md` | 4 | R09 | `missing-examples` | No example interactions |
| 173 | `plugins/documentation-generation/agents/docs-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 174 | `plugins/documentation-generation/agents/docs-architect.md` | 4 | R09 | `missing-examples` | No example interactions |
| 175 | `plugins/documentation-generation/agents/mermaid-expert.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 176 | `plugins/documentation-generation/agents/mermaid-expert.md` | 4 | R09 | `missing-examples` | No example interactions |
| 177 | `plugins/documentation-generation/agents/api-documenter.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 178 | `plugins/documentation-generation/agents/api-documenter.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 179 | `plugins/documentation-generation/agents/tutorial-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 180 | `plugins/documentation-generation/agents/tutorial-engineer.md` | 4 | R09 | `missing-examples` | No example interactions |
| 181 | `plugins/protect-mcp/agents/receipt-verifier.md` | 4 | R11 | `missing-tools` | No tools field declared; agent references Bash tool in body but does not declare it |
| 182 | `plugins/protect-mcp/agents/receipt-verifier.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 183 | `plugins/protect-mcp/agents/policy-enforcer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 184 | `plugins/protect-mcp/agents/policy-enforcer.md` | — | R09 | `single-example` | Only one example block found; minimum two required for reliable triggering |
| 185 | `plugins/machine-learning-ops/agents/ml-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 186 | `plugins/machine-learning-ops/agents/ml-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 187 | `plugins/machine-learning-ops/agents/data-scientist.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 188 | `plugins/machine-learning-ops/agents/data-scientist.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 189 | `plugins/machine-learning-ops/agents/mlops-engineer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 190 | `plugins/machine-learning-ops/agents/mlops-engineer.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 191 | `plugins/unit-testing/agents/debugger.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 192 | `plugins/unit-testing/agents/debugger.md` | 4 | R09 | `missing-examples` | No example interactions |
| 193 | `plugins/unit-testing/agents/test-automator.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 194 | `plugins/unit-testing/agents/test-automator.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 195 | `plugins/team-collaboration/agents/dx-optimizer.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 196 | `plugins/team-collaboration/agents/dx-optimizer.md` | 4 | R09 | `missing-examples` | No example interactions |
| 197 | `plugins/context-management/agents/context-manager.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 198 | `plugins/context-management/agents/context-manager.md` | 4 | R12 | `missing-output-format` | No dedicated output format section |
| 199 | `plugins/seo-technical-optimization/agents/seo-snippet-hunter.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 200 | `plugins/seo-technical-optimization/agents/seo-snippet-hunter.md` | 4 | R09 | `missing-examples` | No example interactions |
| 201 | `plugins/seo-technical-optimization/agents/seo-keyword-strategist.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 202 | `plugins/seo-technical-optimization/agents/seo-keyword-strategist.md` | 4 | R09 | `missing-examples` | No example interactions |
| 203 | `plugins/seo-technical-optimization/agents/seo-structure-architect.md` | 4 | R11 | `missing-tools` | No tools field declared |
| 204 | `plugins/seo-technical-optimization/agents/seo-structure-architect.md` | 4 | R09 | `missing-examples` | No example interactions |

