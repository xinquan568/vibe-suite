# Re-Audit: jeremylongshore/claude-code-plugins-plus-skills

**Date**: 2026-04-24  |  **Before**: `unknown` (73/100)  |  **After**: `3076d78` (84/100)

## Summary

| Outcome | Count |
|---------|------:|
| fixed — our PR merged | 7 |
| fixed — upstream, not via our PR | 35 |
| newly introduced (regressions) | 214 |

## Original findings — verification

| # | File | Line | Rule | Pattern | Outcome | PR |
|---|------|------|------|---------|---------|----|
| 1 | `.claude/agents/skill-auditor.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #535 |
| 2 | `workspace/lab/schema-optimization/agents/phase_1.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #536 |
| 3 | `workspace/lab/schema-optimization/agents/phase_2.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #536 |
| 4 | `workspace/lab/schema-optimization/agents/phase_3.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #536 |
| 5 | `workspace/lab/schema-optimization/agents/phase_4.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #536 |
| 6 | `workspace/lab/schema-optimization/agents/phase_5.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — our PR merged | #536 |
| 7 | `backups/.../backup-strategy.md` | — | BUG-unclassified | `shell-command-substitution-in-yaml-descr` | fixed — upstream, not via our PR |  |
| 8 | `backups/.../sync-agent-context.md` | — | BUG-missing-frontmatter | `no-yaml-frontmatter` | fixed — upstream, not via our PR |  |
| 9 | `backups/.../overnight-setup.md` | — | BUG-unclassified | `missing-required-name-field-in-frontmatt` | fixed — upstream, not via our PR |  |
| 10 | `backups/.../discovery.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 11 | `backups/.../sow.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 12 | `backups/.../make-builder.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 13 | `backups/.../zap.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 14 | `backups/.../n8n-builder.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 15 | `backups/.../roi.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 16 | `backups/.../mobile-test.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 17 | `backups/.../fuzz-api.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 18 | `backups/.../commit-smart.md` | — | BUG-unclassified | `missing-required-name-field` | fixed — upstream, not via our PR |  |
| 19 | `backups/.../backup-strategy.md` | — | SEC-unknown | `shell-substitution-expressions-in-yaml-f` | fixed — upstream, not via our PR |  |
| 20 | `backups/.../incident-p0-disk-full.md` | — | SEC-unknown | `sudo-rm-rf-instructed-against-a-postgres` | fixed — upstream, not via our PR |  |
| 21 | `scripts/quick-test.sh` | — | SEC-unknown | `npm-install-g-pnpm-9-15-9-at-runtime-pin` | fixed — our PR merged | #538 |
| 22 | `backups/.../fairdb-onboard-customer.md` | — | SEC-unknown | `pgpassword-in-env-document-alternative-p` | fixed — upstream, not via our PR |  |
| 23 | `backups/.../fairdb-setup-backup.md` | — | SEC-unknown | `webhook-curl-with-env-var-url-add-a-n-fa` | fixed — upstream, not via our PR |  |
| 24 | `schema-optimization/agents/phase_*.md` | — | R09 | `no-examples` | fixed — upstream, not via our PR |  |
| 25 | `skill-auditor.md` | — | UNCLASSIFIED | `substantial-body-detailed-audit-methodol` | fixed — upstream, not via our PR |  |
| 26 | `nosql-agent.md` | — | BUG-missing-model | `missing-model` | fixed — upstream, not via our PR |  |
| 27 | `validation-agent.md` | — | BUG-missing-model | `missing-model` | fixed — upstream, not via our PR |  |
| 28 | `orm-agent.md` | — | BUG-missing-model | `missing-model` | fixed — upstream, not via our PR |  |
| 29 | `nosql-agent.md` | — | UNCLASSIFIED | `code-examples-in-body-but-no-agent-examp` | fixed — upstream, not via our PR |  |
| 30 | `validation-agent.md` | — | UNCLASSIFIED | `code-examples-in-body-but-no-agent-examp` | fixed — upstream, not via our PR |  |
| 31 | `data-validation-engine` | — | UNCLASSIFIED | `code-examples-in-body-but-no-agent-examp` | fixed — upstream, not via our PR |  |
| 32 | `templates/full-plugin/agents/example.md` | — | UNCLASSIFIED | `stub-body-agent-instructions-here-templa` | fixed — upstream, not via our PR |  |
| 33 | `templates/agent-plugin/agents/example.md` | — | UNCLASSIFIED | `model-field-commented-out-should-show-ac` | fixed — upstream, not via our PR |  |
| 34 | `backups/.../commit.md` | — | UNCLASSIFIED | `hardcoded-model-claude-sonnet-4-5-202509` | fixed — upstream, not via our PR |  |
| 35 | `backups/.../validate-consistency.md` | — | UNCLASSIFIED | `non-standard-temperature-0-0-frontmatter` | fixed — upstream, not via our PR |  |
| 36 | `geepers_orchestrator_web.md` | — | UNCLASSIFIED | `description-truncated-mid-sentence-build` | fixed — upstream, not via our PR |  |
| 37 | `geepers_dashboard.md` | — | UNCLASSIFIED | `only-2-example-blocks-minimum-viable-but` | fixed — upstream, not via our PR |  |
| 38 | `geepers_scalpel.md` | — | UNCLASSIFIED | `only-2-example-blocks-minimum-viable-but` | fixed — upstream, not via our PR |  |
| 39 | `geepers_a11y.md` | — | UNCLASSIFIED | `only-2-example-blocks-minimum-viable-but` | fixed — upstream, not via our PR |  |
| 40 | `geepers_links.md` | — | UNCLASSIFIED | `only-2-example-blocks-minimum-viable-but` | fixed — upstream, not via our PR |  |
| 41 | `All devops/testing backup commands (33 files)` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 42 | `name` | — | BUG-missing-model | `missing-model` | fixed — upstream, not via our PR |  |

## Findings introduced since audit

These findings appear in the re-audit but were not in the original audit. They may be true regressions (new commits introduced them) or artifacts of scoring drift.

| # | File | Line | Rule | Pattern | Description |
|---|------|------|------|---------|-------------|
| 1 | `.claude/agents/skill-auditor.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 2 | `.claude/agents/skill-auditor.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 3 | `.claude/agents/skill-auditor.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 4 | `workspace/lab/schema-optimization/agents/phase_5.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 5 | `workspace/lab/schema-optimization/agents/phase_5.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 6 | `workspace/lab/schema-optimization/agents/phase_5.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 7 | `workspace/lab/schema-optimization/agents/phase_4.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 8 | `workspace/lab/schema-optimization/agents/phase_4.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 9 | `workspace/lab/schema-optimization/agents/phase_4.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 10 | `workspace/lab/schema-optimization/agents/phase_3.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 11 | `workspace/lab/schema-optimization/agents/phase_3.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 12 | `workspace/lab/schema-optimization/agents/phase_3.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 13 | `workspace/lab/schema-optimization/agents/phase_2.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 14 | `workspace/lab/schema-optimization/agents/phase_2.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 15 | `workspace/lab/schema-optimization/agents/phase_2.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 16 | `workspace/lab/schema-optimization/agents/phase_1.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 17 | `workspace/lab/schema-optimization/agents/phase_1.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 18 | `workspace/lab/schema-optimization/agents/phase_1.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 19 | `templates/full-plugin/agents/example.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 20 | `templates/full-plugin/agents/example.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 21 | `templates/full-plugin/agents/example.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 22 | `templates/full-plugin/agents/example.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 23 | `templates/agent-plugin/agents/example.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 24 | `templates/agent-plugin/agents/example.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 25 | `templates/agent-plugin/agents/example.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 26 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 27 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 28 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 29 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 30 | `plugins/database/data-validation-engine/agents/validation-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 31 | `plugins/database/data-validation-engine/agents/validation-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 32 | `plugins/database/data-validation-engine/agents/validation-agent.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 33 | `plugins/database/data-validation-engine/agents/validation-agent.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 34 | `plugins/database/freshie-inventory-manager/agents/discovery-scanner.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 35 | `plugins/database/freshie-inventory-manager/agents/discovery-scanner.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 36 | `plugins/database/freshie-inventory-manager/agents/anomaly-detector.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 37 | `plugins/database/freshie-inventory-manager/agents/anomaly-detector.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 38 | `plugins/database/freshie-inventory-manager/agents/compliance-validator.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 39 | `plugins/database/freshie-inventory-manager/agents/compliance-validator.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 40 | `plugins/database/orm-code-generator/agents/orm-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 41 | `plugins/database/orm-code-generator/agents/orm-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 42 | `plugins/database/orm-code-generator/agents/orm-agent.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 43 | `plugins/database/query-performance-analyzer/agents/performance-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 44 | `plugins/database/query-performance-analyzer/agents/performance-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 45 | `plugins/database/query-performance-analyzer/agents/performance-agent.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 46 | `plugins/mcp/project-health-auditor/agents/reviewer.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 47 | `plugins/mcp/project-health-auditor/agents/reviewer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 48 | `plugins/mcp/project-health-auditor/agents/reviewer.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 49 | `plugins/mcp/conversational-api-debugger/agents/api-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 50 | `plugins/mcp/conversational-api-debugger/agents/api-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 51 | `plugins/mcp/conversational-api-debugger/agents/api-expert.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 52 | `plugins/mcp/x-bug-triage/agents/bug-clusterer.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 53 | `plugins/mcp/x-bug-triage/agents/owner-router.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 54 | `plugins/mcp/x-bug-triage/agents/triage-summarizer.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 55 | `plugins/mcp/x-bug-triage/agents/repo-scanner.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 56 | `plugins/business-tools/general-legal-assistant/agents/legal-clauses.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 57 | `plugins/business-tools/general-legal-assistant/agents/legal-clauses.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 58 | `plugins/business-tools/general-legal-assistant/agents/legal-compliance.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 59 | `plugins/business-tools/general-legal-assistant/agents/legal-compliance.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 60 | `plugins/business-tools/general-legal-assistant/agents/legal-recommendations.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 61 | `plugins/business-tools/general-legal-assistant/agents/legal-recommendations.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 62 | `plugins/business-tools/general-legal-assistant/agents/legal-risks.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 63 | `plugins/business-tools/general-legal-assistant/agents/legal-risks.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 64 | `plugins/business-tools/general-legal-assistant/agents/legal-obligations.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 65 | `plugins/business-tools/general-legal-assistant/agents/legal-obligations.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 66 | `plugins/business-tools/openbb-terminal/agents/crypto-analyst.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 67 | `plugins/business-tools/openbb-terminal/agents/crypto-analyst.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 68 | `plugins/business-tools/openbb-terminal/agents/portfolio-manager.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 69 | `plugins/business-tools/openbb-terminal/agents/portfolio-manager.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 70 | `plugins/business-tools/openbb-terminal/agents/macro-economist.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 71 | `plugins/business-tools/openbb-terminal/agents/macro-economist.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 72 | `plugins/business-tools/openbb-terminal/agents/equity-analyst.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 73 | `plugins/business-tools/openbb-terminal/agents/equity-analyst.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 74 | `plugins/examples/security-agent/agents/security-reviewer.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 75 | `plugins/examples/security-agent/agents/security-reviewer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 76 | `plugins/examples/security-agent/agents/security-reviewer.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 77 | `plugins/ai-ml/jeremy-genkit-pro/agents/genkit-flow-architect.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 78 | `plugins/ai-ml/jeremy-genkit-pro/agents/genkit-flow-architect.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 79 | `plugins/ai-ml/jeremy-gcp-starter-examples/agents/gcp-starter-kit-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 80 | `plugins/ai-ml/jeremy-gcp-starter-examples/agents/gcp-starter-kit-expert.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 81 | `plugins/ai-ml/ai-sdk-agents/agents/multi-agent-orchestrator.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 82 | `plugins/ai-ml/ai-sdk-agents/agents/multi-agent-orchestrator.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 83 | `plugins/ai-ml/jeremy-adk-orchestrator/agents/a2a-protocol-manager.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 84 | `plugins/ai-ml/jeremy-adk-orchestrator/agents/a2a-protocol-manager.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 85 | `plugins/ai-ml/jeremy-vertex-engine/agents/vertex-engine-inspector.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 86 | `plugins/ai-ml/jeremy-vertex-engine/agents/vertex-engine-inspector.md` | — | R09 | `zero-examples` | Zero formal examples provided |
| 87 | `plugins/ai-ml/jeremy-vertex-engine/agents/vertex-engine-inspector.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 88 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/prompt-injection-defender.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 89 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/prompt-injection-defender.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 90 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/ai-safety-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 91 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/ai-safety-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 92 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/vector-db-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 93 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/vector-db-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 94 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/rag-architect.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 95 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/rag-architect.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 96 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-architect.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 97 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-architect.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 98 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-optimizer.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 99 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-optimizer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 100 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/model-selector.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 101 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/model-selector.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 102 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/llm-integration-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 103 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/llm-integration-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 104 | `plugins/packages/fullstack-starter-pack/agents/react-specialist.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 105 | `plugins/packages/fullstack-starter-pack/agents/ui-ux-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 106 | `plugins/packages/fullstack-starter-pack/agents/deployment-specialist.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 107 | `plugins/packages/fullstack-starter-pack/agents/deployment-specialist.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 108 | `plugins/packages/fullstack-starter-pack/agents/backend-architect.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 109 | `plugins/packages/fullstack-starter-pack/agents/backend-architect.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 110 | `plugins/packages/fullstack-starter-pack/agents/api-builder.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 111 | `plugins/packages/fullstack-starter-pack/agents/api-builder.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 112 | `plugins/packages/fullstack-starter-pack/agents/database-designer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 113 | `plugins/packages/fullstack-starter-pack/agents/database-designer.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 114 | `plugins/packages/fullstack-starter-pack/plugins/04-integration/agents/deployment-specialist.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 115 | `plugins/packages/fullstack-starter-pack/plugins/04-integration/agents/deployment-specialist.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 116 | `plugins/packages/fullstack-starter-pack/plugins/01-frontend/agents/react-specialist.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 117 | `plugins/packages/fullstack-starter-pack/plugins/01-frontend/agents/ui-ux-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 118 | `plugins/packages/fullstack-starter-pack/plugins/03-database/agents/database-designer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 119 | `plugins/packages/fullstack-starter-pack/plugins/03-database/agents/database-designer.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 120 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/backend-architect.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 121 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/backend-architect.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 122 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/api-builder.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 123 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/api-builder.md` | — | R12 | `missing-output-format` | No output format specified in agent body |
| 124 | `plugins/packages/security-pro-pack/plugins/03-cryptography/agents/crypto-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 125 | `plugins/packages/security-pro-pack/plugins/03-cryptography/agents/crypto-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 126 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/security-auditor-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 127 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/security-auditor-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 128 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/penetration-tester.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 129 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/penetration-tester.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 130 | `plugins/packages/security-pro-pack/plugins/04-infrastructure-security/agents/threat-modeler.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 131 | `plugins/packages/security-pro-pack/plugins/04-infrastructure-security/agents/threat-modeler.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 132 | `plugins/packages/security-pro-pack/plugins/02-compliance/agents/compliance-checker.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 133 | `plugins/packages/security-pro-pack/plugins/02-compliance/agents/compliance-checker.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 134 | `plugins/packages/devops-automation-pack/plugins/03-docker/agents/docker-specialist.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 135 | `plugins/packages/devops-automation-pack/plugins/03-docker/agents/docker-specialist.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 136 | `plugins/packages/devops-automation-pack/plugins/03-docker/agents/docker-specialist.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 137 | `plugins/packages/devops-automation-pack/plugins/04-kubernetes/agents/kubernetes-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 138 | `plugins/packages/devops-automation-pack/plugins/04-kubernetes/agents/kubernetes-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 139 | `plugins/packages/devops-automation-pack/plugins/04-kubernetes/agents/kubernetes-expert.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 140 | `plugins/packages/devops-automation-pack/plugins/02-ci-cd/agents/ci-cd-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 141 | `plugins/packages/devops-automation-pack/plugins/02-ci-cd/agents/ci-cd-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 142 | `plugins/packages/devops-automation-pack/plugins/02-ci-cd/agents/ci-cd-expert.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 143 | `plugins/packages/devops-automation-pack/plugins/06-deployment/agents/deployment-specialist.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 144 | `plugins/packages/devops-automation-pack/plugins/06-deployment/agents/deployment-specialist.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 145 | `plugins/packages/devops-automation-pack/plugins/06-deployment/agents/deployment-specialist.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 146 | `plugins/packages/devops-automation-pack/plugins/05-terraform/agents/terraform-architect.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 147 | `plugins/packages/devops-automation-pack/plugins/05-terraform/agents/terraform-architect.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 148 | `plugins/packages/devops-automation-pack/plugins/05-terraform/agents/terraform-architect.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 149 | `plugins/packages/creator-studio-pack/plugins/content-strategy/distribution-automator/agents/distribution.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 150 | `plugins/packages/creator-studio-pack/plugins/content-strategy/viral-idea-generator/agents/idea-generator.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 151 | `plugins/packages/creator-studio-pack/plugins/workflow-optimization/collaboration-manager/agents/collaboration.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 152 | `plugins/packages/creator-studio-pack/plugins/workflow-optimization/batch-recording-scheduler/agents/batch-scheduler.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 153 | `plugins/packages/creator-studio-pack/plugins/workflow-optimization/content-calendar-ai/agents/calendar.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 154 | `plugins/packages/creator-studio-pack/plugins/video-production/video-editor-ai/agents/video-editor.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 155 | `plugins/packages/creator-studio-pack/plugins/video-production/video-editor-ai/agents/video-editor.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 156 | `plugins/packages/creator-studio-pack/plugins/video-production/audio-mixer-assistant/agents/audio-mixer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 157 | `plugins/packages/creator-studio-pack/plugins/project-documentation/demo-video-generator/agents/demo-generator.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 158 | `plugins/packages/creator-studio-pack/plugins/project-documentation/demo-video-generator/agents/demo-generator.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 159 | `plugins/packages/creator-studio-pack/plugins/project-documentation/code-explainer-video/agents/code-explainer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 160 | `plugins/packages/creator-studio-pack/plugins/project-documentation/code-explainer-video/agents/code-explainer.md` | — | R09 | `one-example` | Exactly one formal example provided; minimum two required |
| 161 | `plugins/packages/creator-studio-pack/plugins/project-documentation/build-logger-agent/agents/build-logger.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 162 | `plugins/crypto/mempool-analyzer/agents/mempool-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 163 | `plugins/crypto/mempool-analyzer/agents/mempool-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 164 | `plugins/crypto/mempool-analyzer/agents/mempool-agent.md` | — | R09 | `zero-examples` | Zero formal examples; Example Queries lists question prompts only, no agent responses |
| 165 | `plugins/crypto/cross-chain-bridge-monitor/agents/bridge-monitor-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 166 | `plugins/crypto/cross-chain-bridge-monitor/agents/bridge-monitor-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 167 | `plugins/crypto/cross-chain-bridge-monitor/agents/bridge-monitor-agent.md` | — | R09 | `zero-examples` | Zero formal examples; Example Queries lists question prompts only, no agent responses |
| 168 | `plugins/crypto/flash-loan-simulator/agents/flashloan-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 169 | `plugins/crypto/flash-loan-simulator/agents/flashloan-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 170 | `plugins/crypto/flash-loan-simulator/agents/flashloan-agent.md` | — | R09 | `zero-examples` | Zero formal examples; Example Strategies are one-line pseudocode, not full interaction examples |
| 171 | `plugins/crypto/token-launch-tracker/agents/launch-tracker-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 172 | `plugins/crypto/token-launch-tracker/agents/launch-tracker-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 173 | `plugins/crypto/token-launch-tracker/agents/launch-tracker-agent.md` | — | R09 | `zero-examples` | Zero formal examples; Example Queries lists question prompts only, no agent responses |
| 174 | `plugins/crypto/crypto-derivatives-tracker/agents/derivatives-agent.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 175 | `plugins/crypto/crypto-derivatives-tracker/agents/derivatives-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 176 | `plugins/crypto/crypto-derivatives-tracker/agents/derivatives-agent.md` | — | R09 | `zero-examples` | Zero formal examples; Example Queries lists question prompts only, no agent responses |
| 177 | `plugins/productivity/vibe-guide/agents/explainer.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 178 | `plugins/productivity/vibe-guide/agents/explainer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 179 | `plugins/productivity/vibe-guide/agents/explorer.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 180 | `plugins/productivity/vibe-guide/agents/explorer.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 181 | `plugins/productivity/vibe-guide/agents/worker.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 182 | `plugins/productivity/vibe-guide/agents/worker.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 183 | `plugins/productivity/travel-assistant/agents/travel-planner.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 184 | `plugins/productivity/travel-assistant/agents/travel-planner.md` | — | R09 | `zero-examples` | Zero formal examples; body is brief with no worked interactions |
| 185 | `plugins/productivity/travel-assistant/agents/travel-planner.md` | — | R12 | `missing-output-format` | Output section says only 'comprehensive travel plan' without structural template |
| 186 | `plugins/productivity/travel-assistant/agents/local-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 187 | `plugins/productivity/travel-assistant/agents/local-expert.md` | — | R09 | `zero-examples` | Zero formal examples; body is a brief bullet list with no worked interactions |
| 188 | `plugins/productivity/travel-assistant/agents/weather-analyst.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 189 | `plugins/productivity/travel-assistant/agents/weather-analyst.md` | — | R09 | `zero-examples` | Zero formal examples; body is a brief bullet list with no worked interactions |
| 190 | `plugins/productivity/travel-assistant/agents/budget-calculator.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 191 | `plugins/productivity/travel-assistant/agents/budget-calculator.md` | — | R09 | `zero-examples` | Zero formal examples; body is a brief bullet list with no worked interactions |
| 192 | `plugins/productivity/youtube-strategy/agents/idea-validator.md` | — | R09 | `zero-examples` | Zero formal examples; output format defined but no concrete worked example with filled-in data |
| 193 | `plugins/productivity/youtube-strategy/agents/yt-scraper.md` | — | R09 | `zero-examples` | Zero formal examples; no worked interaction or sample output shown |
| 194 | `plugins/productivity/youtube-strategy/agents/channel-analyzer.md` | — | R09 | `zero-examples` | Zero formal examples; output format defined but no concrete worked example with filled-in data |
| 195 | `plugins/productivity/overnight-dev/agents/overnight-dev-coach.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 196 | `plugins/productivity/overnight-dev/agents/overnight-dev-coach.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 197 | `plugins/ai-agency/make-scenario-builder/agents/make-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 198 | `plugins/ai-agency/make-scenario-builder/agents/make-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 199 | `plugins/ai-agency/make-scenario-builder/agents/make-expert.md` | — | R09 | `one-example` | Exactly one formal example provided (AI-Powered Lead Qualification scenario) |
| 200 | `plugins/ai-agency/n8n-workflow-designer/agents/n8n-expert.md` | — | R10 | `missing-model` | No model declared in frontmatter |
| 201 | `plugins/ai-agency/n8n-workflow-designer/agents/n8n-expert.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 202 | `plugins/ai-agency/n8n-workflow-designer/agents/n8n-expert.md` | — | R09 | `one-example` | Exactly one formal example provided (AI Email Responder workflow) |
| 203 | `plugins/community/sprint/agents/nextjs-diagnostics-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter; uses MCP tools in body but not declared in frontmatter |
| 204 | `plugins/community/sprint/agents/nextjs-diagnostics-agent.md` | — | R09 | `zero-examples` | Zero formal examples; report format specified but no worked diagnostic session shown |
| 205 | `plugins/community/sprint/agents/project-architect.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 206 | `plugins/community/sprint/agents/project-architect.md` | — | R12 | `missing-output-format` | Output format described via SPAWN REQUEST blocks in body but lacks a dedicated Output Format section |
| 207 | `plugins/community/sprint/agents/allpurpose-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 208 | `plugins/community/sprint/agents/allpurpose-agent.md` | — | R09 | `zero-examples` | Zero formal usage examples; IMPLEMENTATION REPORT template defines output structure but no worked interaction shown |
| 209 | `plugins/community/sprint/agents/qa-test-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 210 | `plugins/community/sprint/agents/qa-test-agent.md` | — | R09 | `zero-examples` | Zero formal usage examples; QA REPORT template defines output structure but no worked interaction shown |
| 211 | `plugins/community/sprint/agents/nextjs-dev.md` | — | R11 | `missing-tools` | No tools declared in frontmatter |
| 212 | `plugins/community/sprint/agents/nextjs-dev.md` | — | R09 | `zero-examples` | Zero formal usage examples; FRONTEND IMPLEMENTATION REPORT template defines output structure but no worked interaction shown |
| 213 | `plugins/community/sprint/agents/ui-test-agent.md` | — | R11 | `missing-tools` | No tools declared in frontmatter; uses MCP Chrome tools in body but not declared in frontmatter |
| 214 | `plugins/community/sprint/agents/ui-test-agent.md` | — | R09 | `zero-examples` | Zero formal usage examples; UI TEST REPORT template defines output structure but no worked test session shown |

