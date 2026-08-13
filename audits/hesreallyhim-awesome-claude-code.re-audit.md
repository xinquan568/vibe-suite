# NLPM Re-Audit: hesreallyhim/awesome-claude-code

**Date**: 2026-04-24  |  **Artifacts**: 24  |  **Strategy**: batched
**NL Score**: 97/100
**Bugs**: 4  |  **Quality Issues**: 9

## NL Score Summary

Artifacts consist of one custom Claude Code command and 23 CLAUDE.md project context files collected from external repositories. Command-specific penalties (frontmatter, allowed-tools) applied to the command; R01 vague-quantifier penalties applied to CLAUDE.md context files per the strict rubric word list.

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/evaluate-repository.md | command | 45 | Missing name + description frontmatter (-50), missing allowed-tools (-5) |
| resources/claude.md-files/Cursor-Tools/CLAUDE.md | context | 96 | Vague: `sufficient` ×1, `relevant` ×1; embedded Cursor Rules YAML fragments |
| resources/claude.md-files/AVS-Vibe-Developer-Guide/CLAUDE.md | context | 98 | Vague: `appropriately` ×1 |
| resources/claude.md-files/AWS-MCP-Server/CLAUDE.md | context | 98 | Vague: `appropriate` ×1 |
| resources/claude.md-files/Basic-Memory/CLAUDE.md | context | 98 | Vague: `relevant` ×1 |
| resources/claude.md-files/Lamoom-Python/CLAUDE.md | context | 98 | Vague: `appropriate` ×1 |
| resources/claude.md-files/Network-Chronicles/CLAUDE.md | context | 98 | Vague: `appropriate` ×1 |
| resources/claude.md-files/Pareto-Mac/CLAUDE.md | context | 98 | Vague: `appropriate` ×1 |
| resources/claude.md-files/SG-Cars-Trends-Backend/CLAUDE.md | context | 98 | Vague: `appropriate` ×1 |
| resources/claude.md-files/AI-IntelliJ-Plugin/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/Anthropic-Quickstarts/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/Comm/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/Course-Builder/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/DroidconKotlin/CLAUDE.md | context | 100 | None (ephemeral "Current Task" section noted in Cross-Component) |
| resources/claude.md-files/EDSL/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/Giselle/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/Guitar/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/JSBeeb/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/LangGraphJS/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/Note-Companion/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/Perplexity-MCP/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/SPy/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/TPL/CLAUDE.md | context | 100 | None |
| resources/claude.md-files/claude-code-mcp-enhanced/CLAUDE.md | context | 100 | None |

**Weighted average**: 2327 / 24 = **97/100**

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/evaluate-repository.md | Missing `name:` frontmatter field | Command not discoverable in /help or command picker |
| 2 | .claude/commands/evaluate-repository.md | Missing `description:` frontmatter field | No summary shown to users; IDE integration blind to command purpose |
| 3 | .claude/commands/evaluate-repository.md | Missing `allowed-tools:` declaration | Claude Code cannot scope tool access during evaluation; all tools implicitly permitted |
| 4 | resources/claude.md-files/Cursor-Tools/CLAUDE.md | Cursor Rules YAML frontmatter fragments embedded at lines 64–73 inside body prose | Malformed for both CLAUDE.md and Cursor Rules parsers; read as plain text by Claude Code, likely a syntax error for Cursor |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | resources/claude.md-files/Lamoom-Python/CLAUDE.md | Vague quantifier R01: `appropriate` — "Use the logging module with appropriate levels" | -2 |
| 2 | resources/claude.md-files/AVS-Vibe-Developer-Guide/CLAUDE.md | Vague quantifier R01: `appropriately` — "placed in appropriately named subdirectories" | -2 |
| 3 | resources/claude.md-files/Cursor-Tools/CLAUDE.md | Vague quantifier R01: `relevant` — "Identify relevant files in your codebase" | -2 |
| 4 | resources/claude.md-files/Cursor-Tools/CLAUDE.md | Vague quantifier R01: `sufficient` — "query must include sufficient information for vibe-tools to determine which server to use" | -2 |
| 5 | resources/claude.md-files/SG-Cars-Trends-Backend/CLAUDE.md | Vague quantifier R01: `appropriate` — "Use mock data where appropriate, avoid hitting real APIs in tests" | -2 |
| 6 | resources/claude.md-files/Network-Chronicles/CLAUDE.md | Vague quantifier R01: `appropriate` — "Generates appropriate XP rewards and notifications for discoveries" | -2 |
| 7 | resources/claude.md-files/AWS-MCP-Server/CLAUDE.md | Vague quantifier R01: `appropriate` — "Implement appropriate logging levels (debug, info, error)" | -2 |
| 8 | resources/claude.md-files/Pareto-Mac/CLAUDE.md | Vague quantifier R01: `appropriate` — "Use os_log for logging, with appropriate log levels" | -2 |
| 9 | resources/claude.md-files/Basic-Memory/CLAUDE.md | Vague quantifier R01: `relevant` — "Continue previous conversations with relevant historical context" | -2 |

## Cross-Component

The 24 files are independent samples from separate external repositories. No shared components or internal cross-references exist between them.

**Observations carried forward from original audit (unresolved):**

- **SG-Cars-Trends-Backend/CLAUDE.md** references `apps/api/CLAUDE.md`, `apps/web/CLAUDE.md`, `packages/database/CLAUDE.md`, and `infra/CLAUDE.md` as sub-guides. These referenced files were not included in the audit set; their existence in the target repository cannot be confirmed. Latent risk if sub-files are missing or renamed.

- **Cursor-Tools/CLAUDE.md** references `node_modules/vibe-tools/README.md` and `vibe-tools.config.json` as authoritative documentation sources. These are runtime artifacts absent from the repository root; they should not be cited as canonical references in a CLAUDE.md.

- **DroidconKotlin/CLAUDE.md** still contains the ephemeral section `## Current Task: Cleaning up the app and prepping for release` (line 44). This persists across every future AI session, injecting stale task context. No rubric penalty assessed (R02 heuristic), but the section remains PR-worthy to remove.

## Recommendation

The collection scores 97/100 — a significant improvement in the NLPM R01 vague-quantifier signal relative to the original audit's 89/100, reflecting the stricter application of the rubric's exact word list. The four bugs remain unresolved and are all mechanical single-file fixes; the highest-priority is adding YAML frontmatter and `allowed-tools` to `evaluate-repository.md`.
