# NLPM Audit: czlonkowski/n8n-skills
**Date**: 2026-04-13  |  **Artifacts**: 9  |  **Strategy**: single
**NL Score**: 93/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 7  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| CLAUDE.md | Project context doc | 90/100 | Minor vague language ("effectively", "expert guidance") |
| skills/n8n-code-javascript/SKILL.md | Skill | 92/100 | "comprehensive" in link descriptions (×2), "many" in instructional line |
| skills/n8n-code-python/SKILL.md | Skill | 92/100 | "comprehensive"/"complete" in link descriptions (×3) |
| skills/n8n-mcp-tools-expert/SKILL.md | Skill | 92/100 | "effectively" in description field |
| skills/n8n-node-configuration/SKILL.md | Skill | 94/100 | "comprehensive" in guides reference section |
| skills/n8n-validation-expert/SKILL.md | Skill | 94/100 | "comprehensive" in guides reference section |
| skills/n8n-expression-syntax/SKILL.md | Skill | 95/100 | None significant |
| skills/n8n-workflow-patterns/SKILL.md | Skill | 95/100 | None significant |
| .claude-plugin/plugin.json | Plugin manifest | 95/100 | None significant |

**Weighted average: 93/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | None |
| Scripts | `build.sh` (root-level zip packaging script) |
| MCP configs | None |
| Package manifests | None (`package.json` absent, `requirements.txt` absent) |

### Security Findings
No security findings.

`build.sh` was read in full. It is a self-contained zip packaging script: creates `dist/` directory, loops over a hardcoded `SKILLS` array, runs `cd skills && zip ...` per entry, then creates a bundle zip. No network calls, no `eval`, no user-supplied input, no credential handling, no PATH modification, no `sudo`, no postinstall hooks. All file writes are within the repository. The script is safe.

## Bugs (PR-worthy)
No bugs found. All SKILL.md files carry valid `name` and `description` frontmatter. All internal cross-references (`DATA_ACCESS.md`, `COMMON_PATTERNS.md`, `ERROR_PATTERNS.md`, `BUILTIN_FUNCTIONS.md`, `STANDARD_LIBRARY.md`, `SEARCH_GUIDE.md`, `VALIDATION_GUIDE.md`, `WORKFLOW_GUIDE.md`, `DEPENDENCIES.md`, `OPERATION_PATTERNS.md`, `ERROR_CATALOG.md`, `FALSE_POSITIVES.md`, `COMMON_MISTAKES.md`, `EXAMPLES.md`, `webhook_processing.md`, etc.) resolve to actual files present in the repository. `plugin.json` version `1.4.0` matches `build.sh` `VERSION="1.4.0"`. Plugin manifest has all required fields (`name`, `version`, `description`, `author`, `license`).

## Security Fixes (PR-worthy, Medium/Low only)
No security fixes required.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | CLAUDE.md | "effectively" in section heading "Teaches how to use n8n-mcp MCP tools **effectively**" — imprecise in instructional context | -2 |
| 2 | CLAUDE.md | "expert guidance" in overview — vague descriptor for what the skills provide | -2 |
| 3 | skills/n8n-code-javascript/SKILL.md | "comprehensive" used twice in resource link descriptions ("Comprehensive data access patterns", "comprehensive guide") | -4 |
| 4 | skills/n8n-code-javascript/SKILL.md | "many" in instructional context: "Complex logic that would require chaining **many** simple nodes" (line 628) | -2 |
| 5 | skills/n8n-code-python/SKILL.md | "comprehensive"/"complete" in resource link descriptions (×3: "Comprehensive Python data access patterns", "Complete standard library reference") | -6 |
| 6 | skills/n8n-mcp-tools-expert/SKILL.md | "effectively" in `description` field: "Expert guide for using n8n-mcp MCP tools **effectively**" | -2 |
| 7 | skills/n8n-node-configuration/SKILL.md | "comprehensive" in reference section intro: "For comprehensive guides on specific topics" (line 784) | -2 |

Note: `n8n-validation-expert` and `n8n-workflow-patterns` have isolated occurrences of the same "comprehensive" pattern in their reference footers, contributing marginally to their score reductions.

## Cross-Component
**Consistent**: All 7 SKILL.md files have matching cross-skill integration sections that correctly name and describe each sibling skill. No orphaned or phantom skill references found. `CLAUDE.md` accurately lists all 7 skills with correct names and one-line descriptions.

**Version alignment**: `plugin.json` version `1.4.0` matches `build.sh` `VERSION="1.4.0"` and all distribution zip filenames in `dist/`. Consistent.

**Supplementary files verified**: Every linked auxiliary file from every SKILL.md exists on disk. No 404-equivalent broken internal links.

**Minor gap**: `n8n-mcp-tools-expert/SKILL.md` references `n8n_health_check()` as a self-help tool (lines 661–666), but this tool is not listed anywhere in `CLAUDE.md`'s "Key MCP Tools" inventory. Informational inconsistency — not a blocker.

**Minor gap**: `CLAUDE.md` describes the plugin as installable via `npm install @anthropic/claude-code-plugin-n8n-skills` (line 171) but no `package.json` exists in the repository. The primary install path is `claude plugin install` from the `.claude-plugin/` manifest. The npm reference may be aspirational or stale.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

No bugs were found and no security findings exist, so there are no PRs to file. The quality issues are all minor vague-quantifier occurrences (total penalty ≈ -7 to -10 across 9 files, averaging ≈93/100). The two informational cross-component gaps (missing `n8n_health_check` in CLAUDE.md, stale npm install reference) are worth noting in a GitHub issue but do not warrant a code PR. This is a high-quality, well-structured pure-skills plugin with no executable attack surface.
