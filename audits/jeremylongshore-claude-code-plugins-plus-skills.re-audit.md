# NLPM Re-Audit: jeremylongshore/claude-code-plugins-plus-skills

**Date**: 2026-04-24  |  **Artifacts**: 100  |  **Strategy**: progressive
**NL Score**: 84/100
**Bugs**: 0  |  **Quality Issues**: 214

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `templates/full-plugin/agents/example.md` | agent | 65 | Zero examples (-15), no output format (-10) |
| `plugins/database/data-validation-engine/agents/validation-agent.md` | agent | 65 | Zero examples (-15), no output format (-10) |
| `plugins/ai-ml/jeremy-vertex-engine/agents/vertex-engine-inspector.md` | agent | 70 | Zero examples (-15), no output format (-10) |
| `plugins/productivity/travel-assistant/agents/travel-planner.md` | agent | 70 | Zero examples (-15), no output format (-10) |
| `workspace/lab/schema-optimization/agents/phase_5.md` | agent | 75 | Zero examples (-15) |
| `workspace/lab/schema-optimization/agents/phase_4.md` | agent | 75 | Zero examples (-15) |
| `workspace/lab/schema-optimization/agents/phase_3.md` | agent | 75 | Zero examples (-15) |
| `workspace/lab/schema-optimization/agents/phase_2.md` | agent | 75 | Zero examples (-15) |
| `workspace/lab/schema-optimization/agents/phase_1.md` | agent | 75 | Zero examples (-15) |
| `templates/agent-plugin/agents/example.md` | agent | 75 | Zero examples (-15) |
| `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | agent | 75 | One example (-5), no output format (-10) |
| `plugins/examples/security-agent/agents/security-reviewer.md` | agent | 75 | Zero examples (-15) |
| `plugins/crypto/mempool-analyzer/agents/mempool-agent.md` | agent | 75 | Zero examples (-15) |
| `plugins/crypto/cross-chain-bridge-monitor/agents/bridge-monitor-agent.md` | agent | 75 | Zero examples (-15) |
| `plugins/crypto/flash-loan-simulator/agents/flashloan-agent.md` | agent | 75 | Zero examples (-15) |
| `plugins/crypto/token-launch-tracker/agents/launch-tracker-agent.md` | agent | 75 | Zero examples (-15) |
| `plugins/crypto/crypto-derivatives-tracker/agents/derivatives-agent.md` | agent | 75 | Zero examples (-15) |
| `plugins/productivity/youtube-strategy/agents/idea-validator.md` | agent | 75 | Zero examples (-15) |
| `plugins/productivity/youtube-strategy/agents/yt-scraper.md` | agent | 75 | Zero examples (-15) |
| `plugins/productivity/youtube-strategy/agents/channel-analyzer.md` | agent | 75 | Zero examples (-15) |
| `plugins/database/freshie-inventory-manager/agents/discovery-scanner.md` | agent | 80 | Zero examples (-15) |
| `plugins/database/freshie-inventory-manager/agents/anomaly-detector.md` | agent | 80 | Zero examples (-15) |
| `plugins/database/freshie-inventory-manager/agents/compliance-validator.md` | agent | 80 | Zero examples (-15) |
| `plugins/business-tools/general-legal-assistant/agents/legal-clauses.md` | agent | 80 | Zero examples (-15) |
| `plugins/business-tools/general-legal-assistant/agents/legal-compliance.md` | agent | 80 | Zero examples (-15) |
| `plugins/business-tools/general-legal-assistant/agents/legal-recommendations.md` | agent | 80 | Zero examples (-15) |
| `plugins/business-tools/general-legal-assistant/agents/legal-risks.md` | agent | 80 | Zero examples (-15) |
| `plugins/business-tools/general-legal-assistant/agents/legal-obligations.md` | agent | 80 | Zero examples (-15) |
| `plugins/productivity/travel-assistant/agents/local-expert.md` | agent | 80 | Zero examples (-15) |
| `plugins/productivity/travel-assistant/agents/weather-analyst.md` | agent | 80 | Zero examples (-15) |
| `plugins/productivity/travel-assistant/agents/budget-calculator.md` | agent | 80 | Zero examples (-15) |
| `plugins/community/sprint/agents/nextjs-diagnostics-agent.md` | agent | 80 | Zero examples (-15) |
| `plugins/community/sprint/agents/allpurpose-agent.md` | agent | 80 | Zero examples (-15) |
| `plugins/community/sprint/agents/qa-test-agent.md` | agent | 80 | Zero examples (-15) |
| `plugins/community/sprint/agents/nextjs-dev.md` | agent | 80 | Zero examples (-15) |
| `plugins/community/sprint/agents/ui-test-agent.md` | agent | 80 | Zero examples (-15) |
| `.claude/agents/skill-auditor.md` | agent | 85 | One example (-5) |
| `plugins/database/query-performance-analyzer/agents/performance-agent.md` | agent | 85 | One example (-5) |
| `plugins/mcp/project-health-auditor/agents/reviewer.md` | agent | 85 | One example (-5) |
| `plugins/mcp/conversational-api-debugger/agents/api-expert.md` | agent | 85 | One example (-5) |
| `plugins/mcp/x-bug-triage/agents/bug-clusterer.md` | agent | 85 | Zero examples (-15) |
| `plugins/mcp/x-bug-triage/agents/owner-router.md` | agent | 85 | Zero examples (-15) |
| `plugins/mcp/x-bug-triage/agents/triage-summarizer.md` | agent | 85 | Zero examples (-15) |
| `plugins/mcp/x-bug-triage/agents/repo-scanner.md` | agent | 85 | Zero examples (-15) |
| `plugins/database/orm-code-generator/agents/orm-agent.md` | agent | 80 | No output format (-10) |
| `plugins/ai-ml/jeremy-genkit-pro/agents/genkit-flow-architect.md` | agent | 85 | No output format (-10) |
| `plugins/ai-ml/jeremy-gcp-starter-examples/agents/gcp-starter-kit-expert.md` | agent | 85 | No output format (-10) |
| `plugins/ai-ml/jeremy-adk-orchestrator/agents/a2a-protocol-manager.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/agents/deployment-specialist.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/agents/backend-architect.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/agents/api-builder.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/agents/database-designer.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/plugins/04-integration/agents/deployment-specialist.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/plugins/03-database/agents/database-designer.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/backend-architect.md` | agent | 85 | No output format (-10) |
| `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/api-builder.md` | agent | 85 | No output format (-10) |
| `plugins/packages/devops-automation-pack/plugins/03-docker/agents/docker-specialist.md` | agent | 85 | One example (-5) |
| `plugins/packages/devops-automation-pack/plugins/04-kubernetes/agents/kubernetes-expert.md` | agent | 85 | One example (-5) |
| `plugins/packages/devops-automation-pack/plugins/02-ci-cd/agents/ci-cd-expert.md` | agent | 85 | One example (-5) |
| `plugins/packages/devops-automation-pack/plugins/06-deployment/agents/deployment-specialist.md` | agent | 85 | One example (-5) |
| `plugins/packages/devops-automation-pack/plugins/05-terraform/agents/terraform-architect.md` | agent | 85 | One example (-5) |
| `plugins/ai-ml/ai-sdk-agents/agents/multi-agent-orchestrator.md` | agent | 90 | One example (-5) |
| `plugins/ai-agency/make-scenario-builder/agents/make-expert.md` | agent | 85 | One example (-5) |
| `plugins/ai-agency/n8n-workflow-designer/agents/n8n-expert.md` | agent | 85 | One example (-5) |
| `plugins/community/sprint/agents/project-architect.md` | agent | 85 | No output format (-10) |
| `plugins/business-tools/openbb-terminal/agents/crypto-analyst.md` | agent | 90 | One example (-5) |
| `plugins/business-tools/openbb-terminal/agents/portfolio-manager.md` | agent | 90 | One example (-5) |
| `plugins/business-tools/openbb-terminal/agents/macro-economist.md` | agent | 90 | One example (-5) |
| `plugins/business-tools/openbb-terminal/agents/equity-analyst.md` | agent | 90 | One example (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/prompt-injection-defender.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/ai-safety-expert.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/vector-db-expert.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/rag-architect.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-architect.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-optimizer.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/model-selector.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/llm-integration-expert.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/security-pro-pack/plugins/03-cryptography/agents/crypto-expert.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/security-pro-pack/plugins/01-core-security/agents/security-auditor-expert.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/security-pro-pack/plugins/01-core-security/agents/penetration-tester.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/security-pro-pack/plugins/04-infrastructure-security/agents/threat-modeler.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/security-pro-pack/plugins/02-compliance/agents/compliance-checker.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/creator-studio-pack/plugins/video-production/video-editor-ai/agents/video-editor.md` | agent | 90 | One example (-5) |
| `plugins/packages/creator-studio-pack/plugins/project-documentation/demo-video-generator/agents/demo-generator.md` | agent | 90 | One example (-5) |
| `plugins/packages/creator-studio-pack/plugins/project-documentation/code-explainer-video/agents/code-explainer.md` | agent | 90 | One example (-5) |
| `plugins/productivity/vibe-guide/agents/explainer.md` | agent | 90 | Missing model (-5) |
| `plugins/productivity/vibe-guide/agents/explorer.md` | agent | 90 | Missing model (-5) |
| `plugins/productivity/vibe-guide/agents/worker.md` | agent | 90 | Missing model (-5) |
| `plugins/productivity/overnight-dev/agents/overnight-dev-coach.md` | agent | 90 | Missing model (-5) |
| `plugins/packages/fullstack-starter-pack/agents/react-specialist.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/fullstack-starter-pack/agents/ui-ux-expert.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/fullstack-starter-pack/plugins/01-frontend/agents/react-specialist.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/fullstack-starter-pack/plugins/01-frontend/agents/ui-ux-expert.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/creator-studio-pack/plugins/content-strategy/distribution-automator/agents/distribution.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/creator-studio-pack/plugins/content-strategy/viral-idea-generator/agents/idea-generator.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/creator-studio-pack/plugins/workflow-optimization/collaboration-manager/agents/collaboration.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/creator-studio-pack/plugins/workflow-optimization/batch-recording-scheduler/agents/batch-scheduler.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/creator-studio-pack/plugins/workflow-optimization/content-calendar-ai/agents/calendar.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/creator-studio-pack/plugins/video-production/audio-mixer-assistant/agents/audio-mixer.md` | agent | 95 | Missing tools (-5) |
| `plugins/packages/creator-studio-pack/plugins/project-documentation/build-logger-agent/agents/build-logger.md` | agent | 95 | Missing tools (-5) |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|

_No bugs found. All agents have the required `name` and `description` frontmatter fields._

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `.claude/agents/skill-auditor.md` | Missing model (R10) | -5 |
| 2 | `.claude/agents/skill-auditor.md` | Missing tools (R11) | -5 |
| 3 | `.claude/agents/skill-auditor.md` | One example instead of two (R09) | -5 |
| 4 | `workspace/lab/schema-optimization/agents/phase_5.md` | Missing model (R10) | -5 |
| 5 | `workspace/lab/schema-optimization/agents/phase_5.md` | Missing tools (R11) | -5 |
| 6 | `workspace/lab/schema-optimization/agents/phase_5.md` | Zero examples (R09) | -15 |
| 7 | `workspace/lab/schema-optimization/agents/phase_4.md` | Missing model (R10) | -5 |
| 8 | `workspace/lab/schema-optimization/agents/phase_4.md` | Missing tools (R11) | -5 |
| 9 | `workspace/lab/schema-optimization/agents/phase_4.md` | Zero examples (R09) | -15 |
| 10 | `workspace/lab/schema-optimization/agents/phase_3.md` | Missing model (R10) | -5 |
| 11 | `workspace/lab/schema-optimization/agents/phase_3.md` | Missing tools (R11) | -5 |
| 12 | `workspace/lab/schema-optimization/agents/phase_3.md` | Zero examples (R09) | -15 |
| 13 | `workspace/lab/schema-optimization/agents/phase_2.md` | Missing model (R10) | -5 |
| 14 | `workspace/lab/schema-optimization/agents/phase_2.md` | Missing tools (R11) | -5 |
| 15 | `workspace/lab/schema-optimization/agents/phase_2.md` | Zero examples (R09) | -15 |
| 16 | `workspace/lab/schema-optimization/agents/phase_1.md` | Missing model (R10) | -5 |
| 17 | `workspace/lab/schema-optimization/agents/phase_1.md` | Missing tools (R11) | -5 |
| 18 | `workspace/lab/schema-optimization/agents/phase_1.md` | Zero examples (R09) | -15 |
| 19 | `templates/full-plugin/agents/example.md` | Missing model (R10) | -5 |
| 20 | `templates/full-plugin/agents/example.md` | Missing tools (R11) | -5 |
| 21 | `templates/full-plugin/agents/example.md` | Missing output format (R12) | -10 |
| 22 | `templates/full-plugin/agents/example.md` | Zero examples (R09) | -15 |
| 23 | `templates/agent-plugin/agents/example.md` | Missing model (R10) | -5 |
| 24 | `templates/agent-plugin/agents/example.md` | Missing tools (R11) | -5 |
| 25 | `templates/agent-plugin/agents/example.md` | Zero examples (R09) | -15 |
| 26 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | Missing model (R10) | -5 |
| 27 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | Missing tools (R11) | -5 |
| 28 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | One example (R09) | -5 |
| 29 | `plugins/database/nosql-data-modeler/agents/nosql-agent.md` | Missing output format (R12) | -10 |
| 30 | `plugins/database/data-validation-engine/agents/validation-agent.md` | Missing model (R10) | -5 |
| 31 | `plugins/database/data-validation-engine/agents/validation-agent.md` | Missing tools (R11) | -5 |
| 32 | `plugins/database/data-validation-engine/agents/validation-agent.md` | Missing output format (R12) | -10 |
| 33 | `plugins/database/data-validation-engine/agents/validation-agent.md` | Zero examples (R09) | -15 |
| 34 | `plugins/database/freshie-inventory-manager/agents/discovery-scanner.md` | Missing tools (R11) | -5 |
| 35 | `plugins/database/freshie-inventory-manager/agents/discovery-scanner.md` | Zero examples (R09) | -15 |
| 36 | `plugins/database/freshie-inventory-manager/agents/anomaly-detector.md` | Missing tools (R11) | -5 |
| 37 | `plugins/database/freshie-inventory-manager/agents/anomaly-detector.md` | Zero examples (R09) | -15 |
| 38 | `plugins/database/freshie-inventory-manager/agents/compliance-validator.md` | Missing tools (R11) | -5 |
| 39 | `plugins/database/freshie-inventory-manager/agents/compliance-validator.md` | Zero examples (R09) | -15 |
| 40 | `plugins/database/orm-code-generator/agents/orm-agent.md` | Missing model (R10) | -5 |
| 41 | `plugins/database/orm-code-generator/agents/orm-agent.md` | Missing tools (R11) | -5 |
| 42 | `plugins/database/orm-code-generator/agents/orm-agent.md` | Missing output format (R12) | -10 |
| 43 | `plugins/database/query-performance-analyzer/agents/performance-agent.md` | Missing model (R10) | -5 |
| 44 | `plugins/database/query-performance-analyzer/agents/performance-agent.md` | Missing tools (R11) | -5 |
| 45 | `plugins/database/query-performance-analyzer/agents/performance-agent.md` | One example (R09) | -5 |
| 46 | `plugins/mcp/project-health-auditor/agents/reviewer.md` | Missing model (R10) | -5 |
| 47 | `plugins/mcp/project-health-auditor/agents/reviewer.md` | Missing tools (R11) | -5 |
| 48 | `plugins/mcp/project-health-auditor/agents/reviewer.md` | One example (R09) | -5 |
| 49 | `plugins/mcp/conversational-api-debugger/agents/api-expert.md` | Missing model (R10) | -5 |
| 50 | `plugins/mcp/conversational-api-debugger/agents/api-expert.md` | Missing tools (R11) | -5 |
| 51 | `plugins/mcp/conversational-api-debugger/agents/api-expert.md` | One example (R09) | -5 |
| 52 | `plugins/mcp/x-bug-triage/agents/bug-clusterer.md` | Zero examples (R09) | -15 |
| 53 | `plugins/mcp/x-bug-triage/agents/owner-router.md` | Zero examples (R09) | -15 |
| 54 | `plugins/mcp/x-bug-triage/agents/triage-summarizer.md` | Zero examples (R09) | -15 |
| 55 | `plugins/mcp/x-bug-triage/agents/repo-scanner.md` | Zero examples (R09) | -15 |
| 56 | `plugins/business-tools/general-legal-assistant/agents/legal-clauses.md` | Missing tools (R11) | -5 |
| 57 | `plugins/business-tools/general-legal-assistant/agents/legal-clauses.md` | Zero examples (R09) | -15 |
| 58 | `plugins/business-tools/general-legal-assistant/agents/legal-compliance.md` | Missing tools (R11) | -5 |
| 59 | `plugins/business-tools/general-legal-assistant/agents/legal-compliance.md` | Zero examples (R09) | -15 |
| 60 | `plugins/business-tools/general-legal-assistant/agents/legal-recommendations.md` | Missing tools (R11) | -5 |
| 61 | `plugins/business-tools/general-legal-assistant/agents/legal-recommendations.md` | Zero examples (R09) | -15 |
| 62 | `plugins/business-tools/general-legal-assistant/agents/legal-risks.md` | Missing tools (R11) | -5 |
| 63 | `plugins/business-tools/general-legal-assistant/agents/legal-risks.md` | Zero examples (R09) | -15 |
| 64 | `plugins/business-tools/general-legal-assistant/agents/legal-obligations.md` | Missing tools (R11) | -5 |
| 65 | `plugins/business-tools/general-legal-assistant/agents/legal-obligations.md` | Zero examples (R09) | -15 |
| 66 | `plugins/business-tools/openbb-terminal/agents/crypto-analyst.md` | Missing tools (R11) | -5 |
| 67 | `plugins/business-tools/openbb-terminal/agents/crypto-analyst.md` | One example (R09) | -5 |
| 68 | `plugins/business-tools/openbb-terminal/agents/portfolio-manager.md` | Missing tools (R11) | -5 |
| 69 | `plugins/business-tools/openbb-terminal/agents/portfolio-manager.md` | One example (R09) | -5 |
| 70 | `plugins/business-tools/openbb-terminal/agents/macro-economist.md` | Missing tools (R11) | -5 |
| 71 | `plugins/business-tools/openbb-terminal/agents/macro-economist.md` | One example (R09) | -5 |
| 72 | `plugins/business-tools/openbb-terminal/agents/equity-analyst.md` | Missing tools (R11) | -5 |
| 73 | `plugins/business-tools/openbb-terminal/agents/equity-analyst.md` | One example (R09) | -5 |
| 74 | `plugins/examples/security-agent/agents/security-reviewer.md` | Missing model (R10) | -5 |
| 75 | `plugins/examples/security-agent/agents/security-reviewer.md` | Missing tools (R11) | -5 |
| 76 | `plugins/examples/security-agent/agents/security-reviewer.md` | Zero examples (R09) | -15 |
| 77 | `plugins/ai-ml/jeremy-genkit-pro/agents/genkit-flow-architect.md` | Missing tools (R11) | -5 |
| 78 | `plugins/ai-ml/jeremy-genkit-pro/agents/genkit-flow-architect.md` | Missing output format (R12) | -10 |
| 79 | `plugins/ai-ml/jeremy-gcp-starter-examples/agents/gcp-starter-kit-expert.md` | Missing tools (R11) | -5 |
| 80 | `plugins/ai-ml/jeremy-gcp-starter-examples/agents/gcp-starter-kit-expert.md` | Missing output format (R12) | -10 |
| 81 | `plugins/ai-ml/ai-sdk-agents/agents/multi-agent-orchestrator.md` | Missing tools (R11) | -5 |
| 82 | `plugins/ai-ml/ai-sdk-agents/agents/multi-agent-orchestrator.md` | One example (R09) | -5 |
| 83 | `plugins/ai-ml/jeremy-adk-orchestrator/agents/a2a-protocol-manager.md` | Missing tools (R11) | -5 |
| 84 | `plugins/ai-ml/jeremy-adk-orchestrator/agents/a2a-protocol-manager.md` | Missing output format (R12) | -10 |
| 85 | `plugins/ai-ml/jeremy-vertex-engine/agents/vertex-engine-inspector.md` | Missing tools (R11) | -5 |
| 86 | `plugins/ai-ml/jeremy-vertex-engine/agents/vertex-engine-inspector.md` | Zero examples (R09) | -15 |
| 87 | `plugins/ai-ml/jeremy-vertex-engine/agents/vertex-engine-inspector.md` | Missing output format (R12) | -10 |
| 88 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/prompt-injection-defender.md` | Missing model (R10) | -5 |
| 89 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/prompt-injection-defender.md` | Missing tools (R11) | -5 |
| 90 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/ai-safety-expert.md` | Missing model (R10) | -5 |
| 91 | `plugins/packages/ai-ml-engineering-pack/plugins/04-ai-safety/agents/ai-safety-expert.md` | Missing tools (R11) | -5 |
| 92 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/vector-db-expert.md` | Missing model (R10) | -5 |
| 93 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/vector-db-expert.md` | Missing tools (R11) | -5 |
| 94 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/rag-architect.md` | Missing model (R10) | -5 |
| 95 | `plugins/packages/ai-ml-engineering-pack/plugins/03-rag-systems/agents/rag-architect.md` | Missing tools (R11) | -5 |
| 96 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-architect.md` | Missing model (R10) | -5 |
| 97 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-architect.md` | Missing tools (R11) | -5 |
| 98 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-optimizer.md` | Missing model (R10) | -5 |
| 99 | `plugins/packages/ai-ml-engineering-pack/plugins/01-prompt-engineering/agents/prompt-optimizer.md` | Missing tools (R11) | -5 |
| 100 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/model-selector.md` | Missing model (R10) | -5 |
| 101 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/model-selector.md` | Missing tools (R11) | -5 |
| 102 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/llm-integration-expert.md` | Missing model (R10) | -5 |
| 103 | `plugins/packages/ai-ml-engineering-pack/plugins/02-llm-integration/agents/llm-integration-expert.md` | Missing tools (R11) | -5 |
| 104 | `plugins/packages/fullstack-starter-pack/agents/react-specialist.md` | Missing tools (R11) | -5 |
| 105 | `plugins/packages/fullstack-starter-pack/agents/ui-ux-expert.md` | Missing tools (R11) | -5 |
| 106 | `plugins/packages/fullstack-starter-pack/agents/deployment-specialist.md` | Missing tools (R11) | -5 |
| 107 | `plugins/packages/fullstack-starter-pack/agents/deployment-specialist.md` | Missing output format (R12) | -10 |
| 108 | `plugins/packages/fullstack-starter-pack/agents/backend-architect.md` | Missing tools (R11) | -5 |
| 109 | `plugins/packages/fullstack-starter-pack/agents/backend-architect.md` | Missing output format (R12) | -10 |
| 110 | `plugins/packages/fullstack-starter-pack/agents/api-builder.md` | Missing tools (R11) | -5 |
| 111 | `plugins/packages/fullstack-starter-pack/agents/api-builder.md` | Missing output format (R12) | -10 |
| 112 | `plugins/packages/fullstack-starter-pack/agents/database-designer.md` | Missing tools (R11) | -5 |
| 113 | `plugins/packages/fullstack-starter-pack/agents/database-designer.md` | Missing output format (R12) | -10 |
| 114 | `plugins/packages/fullstack-starter-pack/plugins/04-integration/agents/deployment-specialist.md` | Missing tools (R11) | -5 |
| 115 | `plugins/packages/fullstack-starter-pack/plugins/04-integration/agents/deployment-specialist.md` | Missing output format (R12) | -10 |
| 116 | `plugins/packages/fullstack-starter-pack/plugins/01-frontend/agents/react-specialist.md` | Missing tools (R11) | -5 |
| 117 | `plugins/packages/fullstack-starter-pack/plugins/01-frontend/agents/ui-ux-expert.md` | Missing tools (R11) | -5 |
| 118 | `plugins/packages/fullstack-starter-pack/plugins/03-database/agents/database-designer.md` | Missing tools (R11) | -5 |
| 119 | `plugins/packages/fullstack-starter-pack/plugins/03-database/agents/database-designer.md` | Missing output format (R12) | -10 |
| 120 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/backend-architect.md` | Missing tools (R11) | -5 |
| 121 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/backend-architect.md` | Missing output format (R12) | -10 |
| 122 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/api-builder.md` | Missing tools (R11) | -5 |
| 123 | `plugins/packages/fullstack-starter-pack/plugins/02-backend/agents/api-builder.md` | Missing output format (R12) | -10 |
| 124 | `plugins/packages/security-pro-pack/plugins/03-cryptography/agents/crypto-expert.md` | Missing model (R10) | -5 |
| 125 | `plugins/packages/security-pro-pack/plugins/03-cryptography/agents/crypto-expert.md` | Missing tools (R11) | -5 |
| 126 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/security-auditor-expert.md` | Missing model (R10) | -5 |
| 127 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/security-auditor-expert.md` | Missing tools (R11) | -5 |
| 128 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/penetration-tester.md` | Missing model (R10) | -5 |
| 129 | `plugins/packages/security-pro-pack/plugins/01-core-security/agents/penetration-tester.md` | Missing tools (R11) | -5 |
| 130 | `plugins/packages/security-pro-pack/plugins/04-infrastructure-security/agents/threat-modeler.md` | Missing model (R10) | -5 |
| 131 | `plugins/packages/security-pro-pack/plugins/04-infrastructure-security/agents/threat-modeler.md` | Missing tools (R11) | -5 |
| 132 | `plugins/packages/security-pro-pack/plugins/02-compliance/agents/compliance-checker.md` | Missing model (R10) | -5 |
| 133 | `plugins/packages/security-pro-pack/plugins/02-compliance/agents/compliance-checker.md` | Missing tools (R11) | -5 |
| 134 | `plugins/packages/devops-automation-pack/plugins/03-docker/agents/docker-specialist.md` | Missing model (R10) | -5 |
| 135 | `plugins/packages/devops-automation-pack/plugins/03-docker/agents/docker-specialist.md` | Missing tools (R11) | -5 |
| 136 | `plugins/packages/devops-automation-pack/plugins/03-docker/agents/docker-specialist.md` | One example (R09) | -5 |
| 137 | `plugins/packages/devops-automation-pack/plugins/04-kubernetes/agents/kubernetes-expert.md` | Missing model (R10) | -5 |
| 138 | `plugins/packages/devops-automation-pack/plugins/04-kubernetes/agents/kubernetes-expert.md` | Missing tools (R11) | -5 |
| 139 | `plugins/packages/devops-automation-pack/plugins/04-kubernetes/agents/kubernetes-expert.md` | One example (R09) | -5 |
| 140 | `plugins/packages/devops-automation-pack/plugins/02-ci-cd/agents/ci-cd-expert.md` | Missing model (R10) | -5 |
| 141 | `plugins/packages/devops-automation-pack/plugins/02-ci-cd/agents/ci-cd-expert.md` | Missing tools (R11) | -5 |
| 142 | `plugins/packages/devops-automation-pack/plugins/02-ci-cd/agents/ci-cd-expert.md` | One example (R09) | -5 |
| 143 | `plugins/packages/devops-automation-pack/plugins/06-deployment/agents/deployment-specialist.md` | Missing model (R10) | -5 |
| 144 | `plugins/packages/devops-automation-pack/plugins/06-deployment/agents/deployment-specialist.md` | Missing tools (R11) | -5 |
| 145 | `plugins/packages/devops-automation-pack/plugins/06-deployment/agents/deployment-specialist.md` | One example (R09) | -5 |
| 146 | `plugins/packages/devops-automation-pack/plugins/05-terraform/agents/terraform-architect.md` | Missing model (R10) | -5 |
| 147 | `plugins/packages/devops-automation-pack/plugins/05-terraform/agents/terraform-architect.md` | Missing tools (R11) | -5 |
| 148 | `plugins/packages/devops-automation-pack/plugins/05-terraform/agents/terraform-architect.md` | One example (R09) | -5 |
| 149 | `plugins/packages/creator-studio-pack/plugins/content-strategy/distribution-automator/agents/distribution.md` | Missing tools (R11) | -5 |
| 150 | `plugins/packages/creator-studio-pack/plugins/content-strategy/viral-idea-generator/agents/idea-generator.md` | Missing tools (R11) | -5 |
| 151 | `plugins/packages/creator-studio-pack/plugins/workflow-optimization/collaboration-manager/agents/collaboration.md` | Missing tools (R11) | -5 |
| 152 | `plugins/packages/creator-studio-pack/plugins/workflow-optimization/batch-recording-scheduler/agents/batch-scheduler.md` | Missing tools (R11) | -5 |
| 153 | `plugins/packages/creator-studio-pack/plugins/workflow-optimization/content-calendar-ai/agents/calendar.md` | Missing tools (R11) | -5 |
| 154 | `plugins/packages/creator-studio-pack/plugins/video-production/video-editor-ai/agents/video-editor.md` | Missing tools (R11) | -5 |
| 155 | `plugins/packages/creator-studio-pack/plugins/video-production/video-editor-ai/agents/video-editor.md` | One example (R09) | -5 |
| 156 | `plugins/packages/creator-studio-pack/plugins/video-production/audio-mixer-assistant/agents/audio-mixer.md` | Missing tools (R11) | -5 |
| 157 | `plugins/packages/creator-studio-pack/plugins/project-documentation/demo-video-generator/agents/demo-generator.md` | Missing tools (R11) | -5 |
| 158 | `plugins/packages/creator-studio-pack/plugins/project-documentation/demo-video-generator/agents/demo-generator.md` | One example (R09) | -5 |
| 159 | `plugins/packages/creator-studio-pack/plugins/project-documentation/code-explainer-video/agents/code-explainer.md` | Missing tools (R11) | -5 |
| 160 | `plugins/packages/creator-studio-pack/plugins/project-documentation/code-explainer-video/agents/code-explainer.md` | One example (R09) | -5 |
| 161 | `plugins/packages/creator-studio-pack/plugins/project-documentation/build-logger-agent/agents/build-logger.md` | Missing tools (R11) | -5 |
| 162 | `plugins/crypto/mempool-analyzer/agents/mempool-agent.md` | Missing model (R10) | -5 |
| 163 | `plugins/crypto/mempool-analyzer/agents/mempool-agent.md` | Missing tools (R11) | -5 |
| 164 | `plugins/crypto/mempool-analyzer/agents/mempool-agent.md` | Zero examples (R09) | -15 |
| 165 | `plugins/crypto/cross-chain-bridge-monitor/agents/bridge-monitor-agent.md` | Missing model (R10) | -5 |
| 166 | `plugins/crypto/cross-chain-bridge-monitor/agents/bridge-monitor-agent.md` | Missing tools (R11) | -5 |
| 167 | `plugins/crypto/cross-chain-bridge-monitor/agents/bridge-monitor-agent.md` | Zero examples (R09) | -15 |
| 168 | `plugins/crypto/flash-loan-simulator/agents/flashloan-agent.md` | Missing model (R10) | -5 |
| 169 | `plugins/crypto/flash-loan-simulator/agents/flashloan-agent.md` | Missing tools (R11) | -5 |
| 170 | `plugins/crypto/flash-loan-simulator/agents/flashloan-agent.md` | Zero examples (R09) | -15 |
| 171 | `plugins/crypto/token-launch-tracker/agents/launch-tracker-agent.md` | Missing model (R10) | -5 |
| 172 | `plugins/crypto/token-launch-tracker/agents/launch-tracker-agent.md` | Missing tools (R11) | -5 |
| 173 | `plugins/crypto/token-launch-tracker/agents/launch-tracker-agent.md` | Zero examples (R09) | -15 |
| 174 | `plugins/crypto/crypto-derivatives-tracker/agents/derivatives-agent.md` | Missing model (R10) | -5 |
| 175 | `plugins/crypto/crypto-derivatives-tracker/agents/derivatives-agent.md` | Missing tools (R11) | -5 |
| 176 | `plugins/crypto/crypto-derivatives-tracker/agents/derivatives-agent.md` | Zero examples (R09) | -15 |
| 177 | `plugins/productivity/vibe-guide/agents/explainer.md` | Missing model (R10) | -5 |
| 178 | `plugins/productivity/vibe-guide/agents/explainer.md` | Missing tools (R11) | -5 |
| 179 | `plugins/productivity/vibe-guide/agents/explorer.md` | Missing model (R10) | -5 |
| 180 | `plugins/productivity/vibe-guide/agents/explorer.md` | Missing tools (R11) | -5 |
| 181 | `plugins/productivity/vibe-guide/agents/worker.md` | Missing model (R10) | -5 |
| 182 | `plugins/productivity/vibe-guide/agents/worker.md` | Missing tools (R11) | -5 |
| 183 | `plugins/productivity/travel-assistant/agents/travel-planner.md` | Missing tools (R11) | -5 |
| 184 | `plugins/productivity/travel-assistant/agents/travel-planner.md` | Zero examples (R09) | -15 |
| 185 | `plugins/productivity/travel-assistant/agents/travel-planner.md` | Missing output format (R12) | -10 |
| 186 | `plugins/productivity/travel-assistant/agents/local-expert.md` | Missing tools (R11) | -5 |
| 187 | `plugins/productivity/travel-assistant/agents/local-expert.md` | Zero examples (R09) | -15 |
| 188 | `plugins/productivity/travel-assistant/agents/weather-analyst.md` | Missing tools (R11) | -5 |
| 189 | `plugins/productivity/travel-assistant/agents/weather-analyst.md` | Zero examples (R09) | -15 |
| 190 | `plugins/productivity/travel-assistant/agents/budget-calculator.md` | Missing tools (R11) | -5 |
| 191 | `plugins/productivity/travel-assistant/agents/budget-calculator.md` | Zero examples (R09) | -15 |
| 192 | `plugins/productivity/youtube-strategy/agents/idea-validator.md` | Zero examples (R09) | -15 |
| 193 | `plugins/productivity/youtube-strategy/agents/yt-scraper.md` | Zero examples (R09) | -15 |
| 194 | `plugins/productivity/youtube-strategy/agents/channel-analyzer.md` | Zero examples (R09) | -15 |
| 195 | `plugins/productivity/overnight-dev/agents/overnight-dev-coach.md` | Missing model (R10) | -5 |
| 196 | `plugins/productivity/overnight-dev/agents/overnight-dev-coach.md` | Missing tools (R11) | -5 |
| 197 | `plugins/ai-agency/make-scenario-builder/agents/make-expert.md` | Missing model (R10) | -5 |
| 198 | `plugins/ai-agency/make-scenario-builder/agents/make-expert.md` | Missing tools (R11) | -5 |
| 199 | `plugins/ai-agency/make-scenario-builder/agents/make-expert.md` | One example (R09) | -5 |
| 200 | `plugins/ai-agency/n8n-workflow-designer/agents/n8n-expert.md` | Missing model (R10) | -5 |
| 201 | `plugins/ai-agency/n8n-workflow-designer/agents/n8n-expert.md` | Missing tools (R11) | -5 |
| 202 | `plugins/ai-agency/n8n-workflow-designer/agents/n8n-expert.md` | One example (R09) | -5 |
| 203 | `plugins/community/sprint/agents/nextjs-diagnostics-agent.md` | Missing tools (R11) | -5 |
| 204 | `plugins/community/sprint/agents/nextjs-diagnostics-agent.md` | Zero examples (R09) | -15 |
| 205 | `plugins/community/sprint/agents/project-architect.md` | Missing tools (R11) | -5 |
| 206 | `plugins/community/sprint/agents/project-architect.md` | Missing output format (R12) | -10 |
| 207 | `plugins/community/sprint/agents/allpurpose-agent.md` | Missing tools (R11) | -5 |
| 208 | `plugins/community/sprint/agents/allpurpose-agent.md` | Zero examples (R09) | -15 |
| 209 | `plugins/community/sprint/agents/qa-test-agent.md` | Missing tools (R11) | -5 |
| 210 | `plugins/community/sprint/agents/qa-test-agent.md` | Zero examples (R09) | -15 |
| 211 | `plugins/community/sprint/agents/nextjs-dev.md` | Missing tools (R11) | -5 |
| 212 | `plugins/community/sprint/agents/nextjs-dev.md` | Zero examples (R09) | -15 |
| 213 | `plugins/community/sprint/agents/ui-test-agent.md` | Missing tools (R11) | -5 |
| 214 | `plugins/community/sprint/agents/ui-test-agent.md` | Zero examples (R09) | -15 |

## Cross-Component

No broken cross-component references detected. The repository uses a self-contained plugin structure where agents operate independently without shared partials or cross-plugin skill imports. The `workspace/lab/schema-optimization/` pipeline phases (phase_1 through phase_5) form an implicit chain but reference each other only by convention, not by path — no broken references.

## Recommendation

The repository scores 84/100 across 100 agents and is in good shape overall, with all required frontmatter present; the primary gaps are systemic — 88 agents lack `tools:` declarations and 42 lack worked examples — both addressable by a single sweep adding `tools: Read` and one representative interaction to each deficient file.
