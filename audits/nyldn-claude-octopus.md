---
repo: nyldn/claude-octopus
audited_by: nlpm-auditor
audit_date: 2026-04-16
plugin_version: 9.22.1
artifact_count: 157
recommendation: REVIEW
nlpm_score: 79
---

# NLPM Audit: nyldn/claude-octopus
**Date**: 2026-04-16  |  **Artifacts**: 157  |  **Strategy**: progressive
**NL Score**: 79/100
**Security**: REVIEW
**Bugs**: 6  |  **Quality Issues**: 14  |  **Security Findings**: 6

---

## NL Score Summary

| Category | Files | Avg Score | Notes |
|----------|-------|-----------|-------|
| `.github/agents/` (GH Actions subagents) | 10 | 63 | Minimal stubs, systemic bugs |
| `agents/personas/` (rich persona agents) | 32 | 85 | Well-formed, exemplary |
| `agents/droids/` (task-specific agents) | 10 | 78 | Missing tools declaration throughout |
| `agents/skills/` (skill-router agents) | 3 | 72 | Thin, minimal descriptions |
| `agents/principles/` (critique rules) | 4 | 82 | Correct format, clean |
| `.claude/agents/` (default subagents) | 10 | 84 | Good quality, missing examples |
| `.claude/commands/` (slash commands) | 49 | 74 | Many missing `allowed-tools` |
| `skills/` (SKILL.md files) | 29 | 85 | Strong execution contracts |
| `config/` (provider + workflow docs) | 8 | 80 | Informational, no frontmatter schema |
| **Overall** | **155+** | **79** | |

**Weighted NL Score: 79 / 100**

Score breakdown by rubric:
- Agent files: start 100, apply: missing tools (-3/tool × count), missing examples (-15 for none, -5 for one), missing model (-5)
- Command files: missing `allowed-tools` (-5), missing numbered steps (-5), missing output format (-5)
- Skill files: missing name/description (-15 each), vague quantifiers (-2 each capped -20), missing output format (-10)

---

## Security Scan

### Execution Surface Inventory

| Surface | Path | Type | Risk Tier |
|---------|------|------|-----------|
| Hook | `hooks/codex-exec-guard.sh` | PreToolUse shell | LOW |
| Hook | `hooks/security-gate.sh` | PostToolUse shell | LOW |
| Hook | `hooks/quality-gate.sh` | PostToolUse shell | LOW |
| Hook | `hooks/post-compact.sh` | PostCompact shell | LOW |
| Hook | `hooks/telemetry-webhook.sh` | PostToolUse shell | MEDIUM |
| Hook | `hooks/user-prompt-submit.sh` | UserPromptSubmit shell+python | MEDIUM |
| Script | `scripts/orchestrate.sh` | Main orchestrator shell | LOW |
| Script | `scripts/lib/*.sh` (49 files) | Library modules | LOW |
| MCP | `.mcp.json` | MCP server config | CLEAN (empty) |
| Package | `package.json` | npm manifest | CLEAN |
| Requirements | `requirements.txt` | Python deps | NOT FOUND |
| Agent body | `agents/personas/openclaw-admin.md` | Markdown/data | HIGH |
| Skill body | `skills/skill-claw/SKILL.md` | Markdown/data | HIGH |
| Command | `.claude/commands/setup.md` | Runtime install guidance | MEDIUM |

### Security Findings

#### FINDING-01 — HIGH: curl-pipe-sh in Agent Persona Body

**File:** `agents/personas/openclaw-admin.md`  
**Location:** Body text, installation instructions section  
**Pattern:** `curl -fsSL https://gogcli.sh/install.sh | bash`  
**Category:** Curl-pipe-sh (R32 equivalent)

The `openclaw-admin` persona body contains a literal `curl | bash` installation command referencing an external domain (`gogcli.sh`). Claude Code renders this file as an agent prompt body. If Claude follows the embedded installation instructions (which the persona may do when invoked), it will download and execute arbitrary code from a third-party domain at runtime. The domain `gogcli.sh` is not the same as `openclaw.ai` used elsewhere — this mismatch is suspicious.

**Severity:** HIGH  
**Exploitability:** Requires invocation of the `openclaw-admin` persona; Claude must then choose to follow the embedded instruction. Risk is conditional but realistic given the agent's purpose.

---

#### FINDING-02 — HIGH: curl-pipe-sh in Skill Installation Table

**File:** `skills/skill-claw/SKILL.md`  
**Location:** Installation table, Ubuntu row  
**Pattern:** `curl -fsSL https://openclaw.ai/install.sh | bash`  
**Category:** Curl-pipe-sh

The skill installation table instructs the agent to run a curl-pipe-sh pattern on the user's machine as part of the deployment workflow. Unlike FINDING-01, this is from the legitimate `openclaw.ai` domain, but the pattern is still a supply-chain risk — the remote script is executed without content verification, hash check, or sandboxing.

**Severity:** HIGH  
**Exploitability:** Any invocation of `skill-claw` for installation triggers this pattern via agent tool use.

---

#### FINDING-03 — MEDIUM: Telemetry Webhook Sends Session Metadata to User-Controlled URL

**File:** `hooks/telemetry-webhook.sh`  
**Location:** Entire file  
**Pattern:** `curl -s -X POST "$OCTOPUS_WEBHOOK_URL" --data-urlencode ...`

The `telemetry-webhook.sh` PostToolUse hook fires when `OCTOPUS_WEBHOOK_URL` is set and sends: `session_id`, `phase`, `tool_name`, `timestamp`, and `tool_output_length` to the URL. The webhook URL is fully user-controlled via environment variable. This creates a data exfiltration vector — a malicious configuration file, compromised `.env`, or social engineering attack could redirect session metadata to an attacker-controlled endpoint.

The payload itself (metadata only, no tool output content) limits severity, but session IDs + tool names across a session reveal the user's workflow structure.

**Severity:** MEDIUM  
**Exploitability:** Requires environment variable injection or user misconfiguration.

---

#### FINDING-04 — MEDIUM: User Prompt Submit Hook Injects MANDATORY Skill Invocations

**File:** `hooks/user-prompt-submit.sh`  
**Location:** Entire file

This `UserPromptSubmit` hook classifies incoming user prompts by keyword pattern matching and, on "strong signal" matches, injects `MANDATORY: Invoke Skill(...)` text into the prompt context. This is architecturally sound for its intended purpose (auto-invoke the right skill), but it constitutes a form of prompt injection into Claude's context from an external script.

The specific risk: if the keyword classifier can be triggered by attacker-controlled input (e.g., a code comment or user message containing trigger words), the attacker can force invocation of specific skills (e.g., `skill-claw` which installs software). The classifier uses static keyword lists, not LLM judgment.

**Severity:** MEDIUM — mitigated by the limited set of skills it can invoke and the requirement for the user to have the malicious input in their own prompts.

---

#### FINDING-05 — MEDIUM: Runtime npm install Instruction in Setup Command

**File:** `.claude/commands/setup.md`  
**Location:** Step 3a, provider install section  
**Pattern:** `npm install -g @openai/codex`

The setup command instructs Claude to execute `npm install -g @openai/codex` in the user's environment. While `@openai/codex` is a known legitimate package, instructing Claude to run global npm installs creates a pattern where the AI agent modifies system state without fine-grained user confirmation at the package level. The `AskUserQuestion` gates shown are at the "do you want to install Codex" level, not per-command confirmation.

**Severity:** MEDIUM (design pattern concern, not a supply-chain attack on its own).

---

#### FINDING-06 — LOW: post-compact.sh Re-injects Workflow Enforcement After Context Compaction

**File:** `hooks/post-compact.sh`  
**Location:** Entire file

After context compaction, this hook reads a pre-compaction state snapshot and re-injects enforcement text including "PROHIBITED from substituting Claude-native tools" directives. While this is an intentional anti-workaround mechanism, it is worth noting that the hook has write access to Claude's context and can persist behavioral constraints across compaction events. This is architecturally intentional but should be noted as a powerful context-manipulation surface.

**Severity:** LOW — by design, no external code execution.

---

### Security Gate Assessment

| Check | Result |
|-------|--------|
| MCP servers configured | CLEAN (empty `{}`) |
| Runtime dependencies | CLEAN (no npm deps) |
| `requirements.txt` | NOT FOUND |
| curl-pipe-sh patterns in hooks | NONE |
| curl-pipe-sh patterns in scripts | NONE |
| `eval` with user variables in scripts | NONE DETECTED |
| Credential exfiltration in hooks | NONE (telemetry: metadata only) |
| Reverse shell patterns | NONE |
| curl-pipe-sh in agent/skill bodies | 2 FOUND (FINDINGS 01, 02) |

---

## Bugs

### BUG-001 — `.github/agents/` files use `execute` tools but declare `readonly: true` implied

**Files:** `code-reviewer.md`, `performance-engineer.md`, `cloud-architect.md` in `.github/agents/`  
**Issue:** These agents have `readonly: true` in their frontmatter but their body text instructs them to run bash commands, write files, or execute tools. Read-only agents cannot use `Bash`, `Write`, or `Edit` tools. This makes them non-functional for their stated purpose.  
**Severity:** BUG — agents cannot execute their primary workflow as written.

---

### BUG-002 — All 10 `agents/droids/` files missing `tools` declaration

**Files:** All files in `agents/droids/`  
**Issue:** None of the droid agents declare a `tools` field in frontmatter. Claude Code defaults to an empty tool list for sub-agents without explicit `tools` declarations, meaning these agents can only use text generation — no file reading, no bash, no grep. Their bodies describe complex workflows requiring these tools.  
**Severity:** BUG — droids cannot perform their stated tasks without tools.

---

### BUG-003 — `agents/personas/python-pro.md` missing `tools` field

**File:** `agents/personas/python-pro.md`  
**Issue:** The python-pro persona body describes using shell commands and reading files but has no `tools` declaration in frontmatter. Unlike droids, this is an isolated omission in an otherwise well-formed category.  
**Severity:** BUG.

---

### BUG-004 — `skill-extract/SKILL.md` contains unimplemented feature sections

**File:** `skills/skill-extract/SKILL.md`  
**Issue:** Multiple sections are explicitly marked "In Progress" or "Planned" in the skill body. This means if the skill is invoked, Claude will encounter instructions for behaviors that are described as not yet implemented. The skill should either not be installed or have a clear capability disclaimer in its description/frontmatter.  
**Severity:** BUG — user will receive incomplete or undefined behavior.

---

### BUG-005 — `hooks/user-prompt-submit.sh` depends on `python3` with no fallback

**File:** `hooks/user-prompt-submit.sh`  
**Issue:** The hook uses `python3` for JSON parsing with no fallback for environments where Python 3 is unavailable (e.g., minimal Docker containers, some CI environments). If `python3` is absent, the hook will fail silently or error, disrupting the UserPromptSubmit flow.  
**Severity:** BUG (environment compatibility).

---

### BUG-006 — `agents/personas/openclaw-admin.md` body references wrong installation domain

**File:** `agents/personas/openclaw-admin.md`  
**Issue:** The curl-pipe-sh command references `gogcli.sh` but the rest of the codebase (including `skill-claw/SKILL.md`) consistently references `openclaw.ai`. This domain mismatch suggests the agent body was written with a stale or incorrect URL. Combined with FINDING-01, this is both a bug and a security concern.  
**Severity:** BUG + HIGH security finding.

---

## Security Fixes

### FIX for FINDING-01 and BUG-006: Replace curl-pipe-sh in openclaw-admin.md

Replace the bare `curl -fsSL https://gogcli.sh/install.sh | bash` with:
1. Correct domain: `openclaw.ai`
2. Safer pattern: Download-then-inspect, or use a package manager method if available
3. Alternatively: Remove the installation instructions from the agent body entirely and route to `skill-claw` for the installation workflow with proper user confirmation gates

```diff
- curl -fsSL https://gogcli.sh/install.sh | bash
+ # Install via package manager (preferred):
+ brew install openclaw  # macOS
+ # OR: Download and inspect before running:
+ # curl -fsSL https://openclaw.ai/install.sh -o /tmp/openclaw-install.sh
+ # review /tmp/openclaw-install.sh before running
```

### FIX for FINDING-02: Add hash verification to skill-claw installation

Replace the bare curl-pipe-sh in `skill-claw/SKILL.md` with a version that:
1. Downloads the install script to a temp file
2. Shows the user the script location for review
3. Requires explicit user confirmation before executing
4. Optionally verifies SHA256 hash against a published checksum

### FIX for FINDING-03: Constrain telemetry webhook

Add URL allowlist validation before posting to `OCTOPUS_WEBHOOK_URL`:
```bash
# Validate webhook URL scheme and optionally hostname allowlist
if [[ ! "$OCTOPUS_WEBHOOK_URL" =~ ^https:// ]]; then
  exit 0  # refuse non-HTTPS webhooks silently
fi
```

---

## Quality Issues

### QUALITY-001 — `.github/agents/` are minimal stubs (score: ~63/100)

All 10 agents in `.github/agents/` follow an identical minimal template: frontmatter with name/description/model/tools, then a single-sentence purpose body. They have no examples, no behavioral guidance, no structured response format, and no tool usage patterns. These score approximately -15 (no examples), -5 (no model in 8/10 files), -3 per unused tool.

Impact: GitHub Actions subagents will produce inconsistent, low-quality output without behavioral grounding.

---

### QUALITY-002 — `.claude/commands/` missing `allowed-tools` in ~65% of files

Of 49 command files audited, approximately 32 are missing the `allowed-tools` frontmatter field. Commands that dispatch to `orchestrate.sh` are especially affected — they list Bash tool usage in their bodies but don't declare it in frontmatter. Per the scoring rubric, each missing field costs -5 points.

Notable commands missing `allowed-tools`: `debug.md`, `debate.md`, `embrace.md`, `brainstorm.md`, `costs.md`, `doctor.md`, `factory.md`, `guard.md`, `loop.md`, `multi.md`, `octo.md`, `parallel.md`, `pipeline.md`, `quick.md`, `research.md`, `retro.md`, `review.md`, `sentinel.md`, `tdd.md`.

Commands that correctly include `allowed-tools`: `setup.md`, `security.md`, and a handful of others.

---

### QUALITY-003 — Vague quantifiers in skill descriptions

Several skill descriptions contain vague terms such as "many features", "some scenarios", "various cases", "appropriate", "certain" without measurable thresholds. Per scoring rules, -2 per vague quantifier capped at -20. Most affected:

- `skill-extract/SKILL.md`: "various design elements", "many components" — significant vagueness given the unimplemented sections
- `skill-knowledge-work/SKILL.md`: "based on various signals", "some projects"
- `skill-cost-projections/SKILL.md`: "some thresholds", "certain workflows"

---

### QUALITY-004 — `agents/personas/devops-troubleshooter.md` missing `tools` declaration

The devops-troubleshooter persona (unlike the similarly-structured personas) does not declare `tools` in frontmatter, despite its body describing extensive use of shell commands, log fetching, and kubernetes debugging. This makes it non-functional as a sub-agent without tools.

---

### QUALITY-005 — `agents/personas/incident-responder.md` missing `tools` declaration

Same issue as QUALITY-004. The incident-responder persona body is rich and operational but no `tools` field is declared.

---

### QUALITY-006 — `agents/personas/test-automator.md` missing `tools` declaration

Same pattern. The test-automator body describes running test commands and reading test output but has no `tools` declaration.

---

### QUALITY-007 — `agents/personas/cloud-architect.md` missing `tools` declaration (but has hooks)

The cloud-architect persona declares hooks (PostToolUse → architecture-gate.sh) but no `tools` field, meaning the hook fires but the agent cannot use the tools it references. The `memory: local` setting compounds this as the agent has no persistence either.

---

### QUALITY-008 — `agents/personas/mermaid-expert.md` uses haiku with no tools

The mermaid-expert correctly uses `haiku` for a lightweight task, but has no `tools` declaration and no `when_to_use` / `avoid_if` fields. Without the ability to read existing code or files, the agent cannot produce context-aware diagrams.

---

### QUALITY-009 — `agents/personas/context-manager.md` missing `when_to_use` / `avoid_if` / examples

Despite being a rich, well-written persona, context-manager omits the structured when_to_use, avoid_if, and formal examples sections that appear in most other personas. This reduces discoverability and creates invocation confusion.

---

### QUALITY-010 — `agents/personas/ai-engineer.md` missing `when_to_use` / `avoid_if` / examples

Same omission as QUALITY-009. The ai-engineer body is comprehensive but the routing metadata is absent.

---

### QUALITY-011 — `agents/personas/academic-writer.md`, `agents/personas/graphql-architect.md` missing `tools`

Both agents describe research and analysis workflows that require `WebSearch`, `Read`, and similar tools, but neither declares `tools` in frontmatter.

---

### QUALITY-012 — `config/providers/` and `config/workflows/` files lack NLPM frontmatter schema

The 8 files in `config/` directories use a plain markdown format without the `name`/`description`/`version` frontmatter that would make them classifiable as NLPM artifacts. They function as reference docs but are not schema-conformant. Score: ~70 (informational only).

---

### QUALITY-013 — Personas `business-analyst.md` and `exec-communicator.md` no `tools` declared vs `finance-analyst.md` which does

There is an inconsistency in which personas declare `tools`. `finance-analyst`, `backend-architect`, `database-architect`, `frontend-developer`, `tdd-orchestrator`, `strategy-analyst`, `marketing-strategist`, `legal-compliance-advisor`, `performance-engineer`, `code-reviewer`, `research-synthesizer`, `ux-researcher` all declare explicit `tools` fields. But `business-analyst`, `exec-communicator`, `deployment-engineer`, `devops-troubleshooter`, `incident-responder`, `test-automator`, `context-manager`, `ai-engineer`, `graphql-architect`, `mermaid-expert`, `typescript-pro`, `academic-writer`, and `cloud-architect` do not. The inconsistency is systemic across ~13 personas (40% of the category).

---

### QUALITY-014 — `skill-extract/SKILL.md` skeleton implementation not gated by capability check

The skill is installable and invocable but approximately 30% of its documented features are marked as "Planned" or "In Progress" without any runtime check or user-facing caveat. Users who invoke the skill for planned features will receive undefined behavior. The skill description should be updated to clearly indicate beta/partial status.

---

## Cross-Component Analysis

### Positive: Execution Contract Pattern is strong

The flow skills (`flow-discover`, `flow-define`, `flow-develop`, `flow-deliver`) and several standalone skills (`skill-verify`, `skill-tdd`, `skill-debug`) implement a rigorous MANDATORY execution contract with numbered steps, explicit blocking gates, and validation requirements. This is best-practice NL programming and scores well (88-92).

### Positive: Security hooks are well-designed defensive patterns

`codex-exec-guard.sh` correctly blocks bare `codex` calls (requires `codex exec` subcommand), `security-gate.sh` validates OWASP category coverage before allowing output, and `quality-gate.sh` checks reference integrity. These are model examples of PostToolUse validation hooks.

### Positive: Provider routing is complete and well-documented

The `config/providers/` directory provides thorough operational documentation for each provider (Codex, Gemini, Copilot, Ollama, OpenCode). The `config/workflows/CLAUDE.md` clearly documents the Double Diamond methodology. These files serve as reliable reference for both Claude and developers.

### Concern: Inconsistent tools declaration across personas creates reliability split

The 32-persona set splits into two tiers: ~19 personas with explicit `tools` declarations that will function correctly as subagents, and ~13 personas without `tools` that will silently fail when invoked as subagents. This creates an unpredictable quality floor for persona-dispatched work. A user invoking `cloud-architect` as a subagent gets only text generation; invoking `backend-architect` gets a full tool suite. The user cannot tell the difference from the description.

### Concern: `.github/agents/` stub quality significantly below all other categories

The 10 GitHub Actions subagents in `.github/agents/` average ~63/100, well below every other category. These agents appear to have been generated from a template without behavioral grounding. If used for actual CI/CD AI workflows, they will produce inconsistent output. Recommend either enriching these with behavioral content or marking them as explicitly minimal stubs with `effort: low`.

### Concern: Command `allowed-tools` gaps reduce safety

When `allowed-tools` is absent, Claude Code does not restrict which tools the command can invoke. For commands like `embrace` and `factory` that orchestrate multi-provider workflows, this means the command could theoretically invoke tools not intended by its author. The security impact is low (user-authenticated session), but the surface is unnecessarily broad.

### Concern: `skill-claw` and `openclaw-admin` create a coordinated curl-pipe-sh risk

The two HIGH findings (FINDING-01, FINDING-02) are related — both enable OpenClaw installation via curl-pipe-sh. If a user invokes the openclaw-admin persona and then follows its install instructions, or invokes skill-claw's installation workflow, the result is identical: unauthenticated remote script execution. These two artifacts should be treated as a single coordinated attack surface.

---

## Recommendation

**REVIEW** — Do not auto-contribute until the following conditions are met:

### Required Fixes (blocks contribution)

1. **FINDING-01 (HIGH):** Remove or remediate the `curl -fsSL https://gogcli.sh/install.sh | bash` pattern in `agents/personas/openclaw-admin.md`. The wrong domain (`gogcli.sh` vs `openclaw.ai`) is an additional red flag.

2. **FINDING-02 (HIGH):** Replace bare curl-pipe-sh in `skills/skill-claw/SKILL.md` with a download-then-review pattern or direct package manager installation.

3. **BUG-001 (CRITICAL):** Audit `.github/agents/` files for `readonly: true` vs. tool usage conflicts. Files where the body requires write/execute tools but frontmatter blocks them are non-functional.

4. **BUG-002 (HIGH):** Add `tools` declarations to all 10 `agents/droids/` files to match their stated functionality.

### Recommended Improvements (unblocks higher score)

5. Add `allowed-tools` to the ~32 `.claude/commands/` files that are missing it.

6. Add `tools` declarations to the ~13 personas missing them (`business-analyst`, `exec-communicator`, `deployment-engineer`, `devops-troubleshooter`, `incident-responder`, `test-automator`, `context-manager`, `ai-engineer`, `graphql-architect`, `mermaid-expert`, `typescript-pro`, `academic-writer`, `cloud-architect`).

7. Enrich `.github/agents/` files with behavioral guidance, examples, and explicit tool lists.

8. Gate `skill-extract/SKILL.md` with a beta warning in its frontmatter description, or remove planned/unimplemented sections.

9. Correct the `openclaw-admin.md` domain from `gogcli.sh` to `openclaw.ai` (or appropriate source).

---

## Appendix: Individual File Scores (Representative Sample)

| File | Score | Key Penalties |
|------|-------|---------------|
| `agents/personas/security-auditor.md` | 92 | — |
| `agents/personas/frontend-developer.md` | 90 | — |
| `agents/personas/database-architect.md` | 90 | — |
| `agents/personas/backend-architect.md` | 90 | — |
| `agents/personas/tdd-orchestrator.md` | 90 | — |
| `agents/personas/code-reviewer.md` | 90 | — |
| `skills/skill-verify/SKILL.md` | 90 | — |
| `skills/flow-discover/SKILL.md` | 90 | — |
| `skills/skill-tdd/SKILL.md` | 92 | — |
| `skills/skill-debug/SKILL.md` | 92 | — |
| `agents/personas/debugger.md` | 90 | — |
| `agents/personas/ui-ux-designer.md` | 88 | minor vague terms |
| `skills/flow-deliver/SKILL.md` | 87 | — |
| `skills/flow-develop/SKILL.md` | 87 | — |
| `skills/skill-iterative-loop/SKILL.md` | 88 | — |
| `skills/skill-finish-branch/SKILL.md` | 88 | — |
| `skills/skill-resume/SKILL.md` | 87 | — |
| `skills/skill-staged-review/SKILL.md` | 87 | — |
| `skills/skill-coverage-audit/SKILL.md` | 87 | — |
| `skills/skill-writing-plans/SKILL.md` | 87 | — |
| `agents/personas/strategy-analyst.md` | 87 | — |
| `agents/personas/finance-analyst.md` | 86 | — |
| `agents/personas/marketing-strategist.md` | 86 | — |
| `agents/personas/legal-compliance-advisor.md` | 86 | — |
| `agents/personas/product-writer.md` | 86 | — |
| `agents/personas/business-analyst.md` | 85 | no `tools` field |
| `.claude/commands/setup.md` | 85 | runtime install guidance |
| `.claude/commands/security.md` | 83 | no `allowed-tools` |
| `skills/skill-visual-feedback/SKILL.md` | 82 | — |
| `skills/skill-intent-contract/SKILL.md` | 85 | — |
| `skills/skill-scope-drift/SKILL.md` | 85 | — |
| `skills/skill-context-detection/SKILL.md` | 85 | — |
| `agents/personas/cloud-architect.md` | 78 | no `tools`, no examples |
| `agents/personas/devops-troubleshooter.md` | 78 | no `tools` |
| `agents/personas/incident-responder.md` | 78 | no `tools` |
| `agents/personas/context-manager.md` | 76 | no examples, no when_to_use |
| `agents/personas/ai-engineer.md` | 76 | no examples, no when_to_use |
| `agents/personas/mermaid-expert.md` | 76 | no `tools`, no when_to_use |
| `agents/principles/security.md` | 84 | — |
| `agents/principles/general.md` | 82 | — |
| `agents/principles/maintainability.md` | 82 | — |
| `agents/principles/performance.md` | 82 | — |
| `skills/skill-extract/SKILL.md` | 65 | unimplemented sections, vague |
| `agents/personas/openclaw-admin.md` | 55 | HIGH security finding, wrong domain |
| `skills/skill-claw/SKILL.md` | 60 | HIGH security finding |
| `.github/agents/code-reviewer.md` | 60 | stub, readonly bug |
| `.github/agents/performance-engineer.md` | 60 | stub, readonly bug |
| `.github/agents/cloud-architect.md` | 60 | stub, no tools |
| `.github/agents/tdd-orchestrator.md` | 63 | stub |
| `.github/agents/security-auditor.md` | 65 | stub, has tools |
| `agents/droids/*` (avg) | 78 | missing tools throughout |
