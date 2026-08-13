# Audit Report: github/awesome-copilot

**Slug**: github-awesome-copilot  
**Audit Date**: 2026-04-25  
**Auditor**: nlpm-auditor (sonnet)  
**Repo**: https://github.com/github/awesome-copilot  
**Artifacts Scanned**: 100 NL artifacts (1 `.github/agents/`, 84 `agents/`, 15 `plugins/` agent files)

---

## NL Score Summary

| Directory | Files | Avg Score | Min | Max | Notes |
|-----------|-------|-----------|-----|-----|-------|
| `.github/agents/` | 1 | 50 | 50 | 50 | Missing `name` field (BUG) |
| `agents/` | 84 | 78 | 55 | 93 | Majority lack model declarations |
| `plugins/` | 15 | 80 | 72 | 85 | Mostly mirrors `agents/` content |
| **Overall** | **100** | **77** | **50** | **93** | Threshold: 70 ✅ |

### Top-Scoring Artifacts (≥ 88)

| File | Score | Strengths |
|------|-------|-----------|
| `agents/expert-nextjs-developer.agent.md` | 93 | Model declared, 8+ code examples, async-params migration guidance |
| `agents/accessibility.agent.md` | 92 | Model declared, full tool list, framework adapters, CI examples |
| `agents/drupal-expert.agent.md` | 92 | Model declared, extensive PHP examples, testing commands |
| `agents/power-bi-dax-expert.agent.md` | 92 | Model declared, DAX before/after anti-pattern examples |
| `agents/winui3-expert.agent.md` | 92 | Model declared, ✓/❌ code comparison tables |
| `agents/azure-iac-generator.agent.md` | 90 | Model declared, example interactions, format-specific workflows |
| `agents/salesforce-expert.agent.md` | 90 | Model declared, LWC before/after migration example |
| `agents/markdown-accessibility-assistant.agent.md` | 88 | Model declared, workflow examples |
| `agents/terratest-module-testing.agent.md` | 88 | Model declared, trigger examples, CI preferences |
| `agents/salesforce-flow.agent.md` | 88 | Model declared, table examples, output format |

### Bottom-Scoring Artifacts (< 65)

| File | Score | Problems |
|------|-------|---------|
| `.github/agents/agentic-workflows.agent.md` | 50 | Missing `name` field (BUG), no examples, `disable-model-invocation: true` without explanation |
| `agents/task-researcher.agent.md` | 55 | 14 vague-word penalties, no examples, cap exceeded |
| `agents/research-technical-spike.agent.md` | 63 | 14 vague-word penalties, no examples, no model |
| `agents/kusto-assistant.agent.md` | 62 | No model, 12 pts unused-tool penalty (findTestFiles, runNotebooks, runTests, testFailure inappropriate for a Kusto query agent) |
| `agents/se-system-architecture-reviewer.agent.md` | 65 | `edit/editFiles` declared on review-only agent (-10), no examples (-15) |

---

## Security Scan

**Pre-scan risk level**: CRITICAL (triggered by pattern match in hooks)  
**Post-analysis risk level**: HIGH (critical trigger was false positive; real findings are high/medium)

### Executable Surfaces Scanned

| Surface | Count | Notes |
|---------|-------|-------|
| Hook scripts (`hooks/**/*.sh`) | 10 | Across 6 hook packages |
| Scripts (`scripts/*.sh`) | 2 | Utility scripts |
| MCP configs | 0 | No `.mcp.json` found at repo root |
| `package.json` | 1 | No postinstall scripts |
| `requirements.txt` | 0 | Not present |

### Critical Pattern Analysis

**SEC-CRIT-001 — False Positive: curl-pipe-sh in guard-tool.sh**  
The pre-scan flagged `hooks/tool-guardian/guard-tool.sh` at lines 116–117:
```
"network_exfiltration:::critical:::curl.*\|.*bash:::..."
"network_exfiltration:::critical:::wget.*\|.*sh:::..."
```
These strings are **detection patterns** inside a `PATTERNS=()` array used by the tool guardian to *block* dangerous operations. They are not executed. **Risk: NONE (false positive).**

### Real Security Findings

#### SEC-001 — HIGH: `--no-verify` Bypasses Security Hooks in auto-commit

**File**: `hooks/session-auto-commit/auto-commit.sh:33`  
**Pattern**: Hook-bypass (detection-evasion adjacent)

```bash
git commit -m "auto-commit: $TIMESTAMP" --no-verify 2>/dev/null
```

The session-auto-commit hook runs `git commit --no-verify`, which explicitly bypasses all pre-commit hooks — including `hooks/secrets-scanner/scan-secrets.sh`. This means any session that uses `session-auto-commit` will skip secret detection before committing. A developer using auto-commit could accidentally commit credentials that the secrets scanner would otherwise block.

**Recommended Fix**: Remove `--no-verify`. If commit hooks are slow, consider running the secrets scanner explicitly before `git commit` rather than bypassing all hooks.

#### SEC-002 — MEDIUM: `git add -A` Stages All Files Without Review

**File**: `hooks/session-auto-commit/auto-commit.sh:29`

```bash
git add -A
```

Staging all files including untracked ones could inadvertently stage `.env`, credential files, or large generated artifacts. This is compounded by SEC-001 (the secrets scanner is bypassed by `--no-verify`).

**Recommended Fix**: Stage only tracked modified files (`git add -u`) or add a filter step before staging.

#### SEC-003 — HIGH: Governance Audit Crashes on Threat Detection (Bug)

**File**: `hooks/governance-audit/audit-prompt.sh:87`

```bash
  for threat in "${THREATS_FOUND[@]}"; do
    ...
    local evidence          # ← line 87: 'local' outside a function
    evidence=$(printf ...)
```

The `local` keyword is only valid inside bash functions. Used in a `for` loop at global scope with `set -euo pipefail`, this causes the script to exit with error when threats are detected — the exact condition the governance audit is designed to handle. The hook **fails silently** (exits non-zero, which Copilot may ignore) precisely when a threat is present.

**Recommended Fix**: Wrap the threat-processing block in a function, or replace `local evidence` with a plain `evidence=` assignment.

#### SEC-004 — MEDIUM: GitHub Actions Template Syntax in MCP Server Config

**File**: `agents/elasticsearch-observability.agent.md` (mcp-servers env block)

```yaml
env:
  AUTH_HEADER: "ApiKey ${{ secrets.ELASTIC_API_KEY }}"
```

GitHub Actions `${{ secrets.* }}` syntax is not resolved in GitHub Copilot agent contexts. If a user deploys this agent, the MCP server will receive the literal string `ApiKey ${{ secrets.ELASTIC_API_KEY }}` as the auth header, causing authentication to fail. The intent (injecting a secret) is valid but the mechanism is wrong for this platform.

**Recommended Fix**: Document that users must substitute their actual API key, or use an environment variable reference appropriate for the deployment context (e.g., `$ELASTIC_API_KEY` from the shell environment).

---

## Bugs

### BUG-001 — Missing Required `name` Field

**File**: `.github/agents/agentic-workflows.agent.md`  
**Category**: BUG-missing-frontmatter  
**Severity**: high

The frontmatter lacks the `name` field, which is required for agent discovery and invocation. The file has `description` and `disable-model-invocation: true` but no `name`. Without a `name`, the agent cannot be listed or invoked by Copilot's agent picker.

```yaml
---
description: "..."
disable-model-invocation: true
# name: missing
---
```

**Fix**: Add `name: "Agentic Workflows"` (or appropriate name) to the frontmatter.

### BUG-002 — Non-Standard Pipe-Separated Model Format

**Files**: `agents/laravel-expert-agent.agent.md`, `agents/pimcore-expert.agent.md`  
**Category**: BUG-invalid-format  
**Severity**: medium

Both files declare:
```yaml
model: GPT-4.1 | 'gpt-5' | 'Claude Sonnet 4.5'
```

This is not a valid YAML value for a model field — it appears to be a human-readable "choose one" annotation left in as-is. Copilot agent parsers will likely read this as the literal string `GPT-4.1 | 'gpt-5' | 'Claude Sonnet 4.5'` which will fail model lookup or silently fall back to default.

**Fix**: Choose one model and use the standard identifier, e.g., `model: gpt-4.1` or `model: claude-sonnet-4-5`.

### BUG-003 — Non-Standard Tool Path Identifiers

**File**: `agents/wg-code-alchemist.agent.md`  
**Category**: BUG-invalid-format  
**Severity**: low

The tools list includes entries like `search/codebase` and `runCommands/terminalLastCommand` which use slash-separated sub-tool paths:
```yaml
tools: ['search/codebase', 'runCommands/terminalLastCommand', ...]
```

These paths are non-standard; the canonical tool identifiers are `codebase` and `terminalLastCommand`. Whether these parse correctly depends on the Copilot agent runtime version.

**Fix**: Use flat tool identifiers: replace `search/codebase` with `codebase`, `runCommands/terminalLastCommand` with `terminalLastCommand`, etc.

---

## Security Fixes

Ordered by priority:

1. **SEC-003 (HIGH)**: Fix `local` outside function in `audit-prompt.sh` — the governance audit is ineffective when threats are present.
2. **SEC-001 (HIGH)**: Remove `--no-verify` from auto-commit hook to allow secrets scanner to run.
3. **SEC-002 (MEDIUM)**: Replace `git add -A` with `git add -u` in auto-commit hook.
4. **SEC-004 (MEDIUM)**: Fix MCP server env template syntax in elasticsearch-observability agent.

---

## Quality Issues

### QI-001 — No Model Declaration (73/100 agents)

The majority of agents omit the `model` field. While Copilot agents may fall back to a default model, declaring a preferred model communicates intent and allows deployment-time validation.

**Most affected**: All agents without `model: ` in frontmatter, e.g., `agents/reepl-linkedin.agent.md`, `agents/task-researcher.agent.md`, and 71 others.

**Penalty**: −5 pts per artifact.

### QI-002 — Missing Concrete Examples (~40 agents)

Approximately 40% of agents describe their capabilities but provide no concrete input/output examples, sample interactions, or worked scenarios. The highest-scoring agents all include examples.

**Examples of well-exemplified agents**: `expert-nextjs-developer.agent.md` (8 code blocks), `accessibility.agent.md` (framework adapters + CI config), `power-bi-dax-expert.agent.md` (DAX before/after anti-patterns).

**Examples lacking examples**: `azure-principal-architect.agent.md`, `devops-expert.agent.md`, `mongodb-performance-advisor.agent.md`.

**Penalty**: −15 pts per artifact.

### QI-003 — Heavy Vague Language in Select Agents

**Files**: `agents/task-researcher.agent.md`, `agents/research-technical-spike.agent.md`

Both contain excessive use of "comprehensive", "appropriate", "relevant", "thorough", "obsessively" (research-technical-spike uses this term 3 times in a row) and similar vague qualifiers that reduce actionability.

**Worst offenders**:
- `task-researcher.agent.md`: "comprehensive research", "appropriate tools", "relevant context" — 14 vague-word hits (−14 pts, capped at −20)
- `research-technical-spike.agent.md`: "obsessively", "exhaustively", "recursively", "comprehensive" — 14 vague-word hits

**Fix**: Replace vague qualifiers with concrete constraints: "search with up to 5 queries", "use the top 3 results", "stop after finding 2 confirming sources".

### QI-004 — Unused Tools Declared

**File**: `agents/kusto-assistant.agent.md`

The Kusto assistant (Azure Data Explorer query helper) declares: `findTestFiles`, `runNotebooks`, `runTests`, `testFailure` — tools appropriate for test-running workflows, not Azure query assistance. These are likely copy-pasted from a template.

**Penalty**: −12 pts (inappropriate tools not aligned with agent purpose).

**Fix**: Remove the test-related tools; retain `search`, `codebase`, and azure-relevant tools.

### QI-005 — Review Agent Declares Write Tools

**File**: `agents/se-system-architecture-reviewer.agent.md`

A "reviewer" agent declares `edit/editFiles` as a tool. Architecture reviewers should produce written recommendations, not edit production files. This creates capability-intent mismatch and potential unintended file modifications.

**Penalty**: −10 pts.

**Fix**: Remove `edit/editFiles` or document explicitly that the agent may generate scaffold files as part of review output.

### QI-006 — Disable-Model-Invocation Without Explanation

**File**: `.github/agents/agentic-workflows.agent.md`

The agent sets `disable-model-invocation: true` without any comment or README explaining what this mode does or why it's appropriate. This is a non-standard field.

**Fix**: Add an inline comment or README section explaining the purpose.

---

## Cross-Component Analysis

### CC-001 — Duplicate Agent Definitions Between `agents/` and `plugins/`

Several agents are defined twice — once in `agents/` and once as plugin agents in `plugins/`:

| Agent | `agents/` path | `plugins/` path | Diff |
|-------|---------------|-----------------|------|
| Go MCP Expert | `agents/go-mcp-expert.agent.md` | `plugins/go-mcp-development/agents/go-mcp-expert.md` | Identical content |
| Azure Terraform IaC | `agents/terraform-azure-implement.agent.md` | `plugins/azure-cloud-development/agents/terraform-azure-implement.md` | Identical content |
| Technical Spike | `agents/research-technical-spike.agent.md` | `plugins/technical-spike/agents/research-technical-spike.md` | Identical content |

This creates maintenance risk: a fix applied to one location will not propagate to the other. Consumers of the plugin version and the standalone version may diverge.

**Fix**: Remove standalone `agents/` copies of plugin-owned agents, or add a comment indicating the canonical source.

### CC-002 — React 19 Plugin Has Richer Agents Than react18 Counterparts

The `plugins/react19-upgrade/` plugin contains a well-designed 4-agent pipeline (auditor → dep-surgeon → migrator → test-guardian) with memory protocol, gate conditions, and checklist tracking.

The standalone `agents/react18-*.agent.md` files (react18-commander, react18-dep-surgeon, react18-test-guardian) follow a similar pattern but are less rigorous: they lack the memory state-machine design and the explicit GO/NO-GO gate verification.

This inconsistency means users who discover the standalone agents get a weaker migration experience than those who use the plugin. Consider updating the standalone agents to reference or wrap the plugin.

### CC-003 — MCP Server References Without Discovery Docs

Several agents declare `mcp-servers` blocks (elasticsearch-observability, scientific-paper-research, neo4j-docker-client-generator, monday-bug-fixer, arm-migration) but there is no central MCP server catalog or discovery document to help users understand which servers are available, how to install them, or what authentication is required.

**Fix**: Add a `docs/mcp-servers.md` that catalogs all referenced MCP servers with install instructions, auth requirements, and tool lists.

---

## Recommendation

**Contribution verdict**: ✅ APPROVED (no critical security issues after false-positive analysis)

**Score**: 77/100 — above the 70-point threshold, with notable variance across artifacts.

**Priority fixes before next audit**:

1. **SEC-003** (HIGH): Fix `local`-outside-function bug in `audit-prompt.sh` — the governance hook fails silently when it matters most.
2. **SEC-001** (HIGH): Remove `--no-verify` from auto-commit hook.
3. **BUG-001**: Add `name` field to `.github/agents/agentic-workflows.agent.md`.
4. **BUG-002**: Fix pipe-separated model format in laravel and pimcore agents.
5. **QI-002**: Add examples to the ~40 agents that lack them — this is the single largest score improvement opportunity (potential +15 pts per artifact).
6. **CC-001**: Resolve agent duplication between `agents/` and `plugins/` directories.

**What's working well**:  
The React 19 migration plugin is an exemplary multi-agent orchestration pattern. The hooks directory contains genuinely useful security tooling (secrets scanner, license checker, governance audit, tool guardian). The top-tier agents (accessibility, Next.js, Drupal, Power BI DAX, WinUI3) demonstrate exactly how domain-expert agents should be written — with model declarations, concrete examples, anti-patterns, and framework-specific code.
