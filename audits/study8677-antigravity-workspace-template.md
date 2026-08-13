# NLPM Audit: study8677/antigravity-workspace-template
**Date**: 2026-04-20  |  **Artifacts**: 7  |  **Strategy**: single
**NL Score**: 62/100
**Security**: CLEAR
**Bugs**: 4  |  **Quality Issues**: 5  |  **Security Findings**: 1

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| engine/antigravity_engine/skills/research/SKILL.md | SKILL | 38/100 | No frontmatter; no output format |
| engine/antigravity_engine/skills/agent-repo-init/SKILL.md | SKILL | 40/100 | No frontmatter; no output format |
| engine/antigravity_engine/skills/graph-retrieval/SKILL.md | SKILL | 50/100 | No frontmatter |
| engine/antigravity_engine/skills/knowledge-layer/SKILL.md | SKILL | 50/100 | No frontmatter |
| cli/src/ag_cli/templates/CLAUDE.md | CLAUDE.md | 75/100 | Sparse content, fully delegates to AGENTS.md |
| ./CLAUDE.md | CLAUDE.md | 88/100 | Well-structured; no penalties |
| skills/agent-repo-init/SKILL.md | SKILL | 95/100 | Minor: no formal return type |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts | 1 (`scripts/demo_tools.py`) |
| MCP configs | 0 |
| Package manifests | 2 (`engine/pyproject.toml`, `cli/pyproject.toml`) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Low | engine/pyproject.toml | 7-12 | Unpinned dependencies | `pydantic`, `pydantic-settings`, `python-dotenv`, `requests`, `openai-agents[litellm]` have no upper-bound version pins; `mcp[cli]>=1.0.0` only lower-bounded |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | engine/antigravity_engine/skills/agent-repo-init/SKILL.md | Missing `name` and `description` frontmatter | Skill cannot be registered by a standards-conformant loader; discoverability broken |
| 2 | engine/antigravity_engine/skills/graph-retrieval/SKILL.md | Missing `name` and `description` frontmatter | Same — unregisterable without frontmatter |
| 3 | engine/antigravity_engine/skills/knowledge-layer/SKILL.md | Missing `name` and `description` frontmatter | Same — unregisterable without frontmatter |
| 4 | engine/antigravity_engine/skills/research/SKILL.md | Missing `name` and `description` frontmatter | Same — unregisterable without frontmatter |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | engine/pyproject.toml | Unpinned deps (`pydantic`, `pydantic-settings`, `python-dotenv`, `requests`, `openai-agents[litellm]`) | Pin to compatible ranges, e.g. `pydantic>=2.0,<3`, `requests>=2.28,<3`, `openai-agents[litellm]>=0.0.3,<1` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | engine/antigravity_engine/skills/research/SKILL.md | Missing output format — `deep_research() -> str` declares return type but gives no description of what the string contains | -10 |
| 2 | engine/antigravity_engine/skills/research/SKILL.md | Vague quantifier: "comprehensive" ("a simulated comprehensive research task") | -2 |
| 3 | engine/antigravity_engine/skills/agent-repo-init/SKILL.md | Missing output format — tool signature shown but no return-value contract | -10 |
| 4 | cli/src/ag_cli/templates/CLAUDE.md | Sparse content: 5 lines, fully delegates to `AGENTS.md` and `.antigravity/`; provides no fallback guidance if those files are absent | — |
| 5 | skills/agent-repo-init/SKILL.md | Expected Output describes files created but no formal return type for the script exit/return value | — |

## Cross-Component
Two versions of the agent-repo-init skill exist at different paths:
- `skills/agent-repo-init/SKILL.md` — has full frontmatter, bash examples, and expected output. Well-formed.
- `engine/antigravity_engine/skills/agent-repo-init/SKILL.md` — no frontmatter, no examples, much thinner.

These describe the same capability (`init_agent_repo`) but diverge in structure and quality. The engine-side version is the one actually executed; the `skills/` version appears to be a Claude Code–facing reference copy. This split creates a maintenance burden: changes to the capability signature must be synced in two places. Consider making the `skills/` version the canonical source and symlinking or auto-generating the engine stub, or merging them with a clear authority comment.

`cli/src/ag_cli/templates/CLAUDE.md` delegates entirely to `AGENTS.md` (line 5). If the CLI bootstraps a project directory that does not include `AGENTS.md`, the resulting CLAUDE.md is effectively a broken pointer. No guard or fallback is documented.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

Priority order:
1. Add frontmatter (`name`, `description`) to all four engine-side SKILL.md files — this unblocks skill registration and is a 1-line fix per file.
2. Pin dependency versions in `engine/pyproject.toml` to avoid supply-chain drift.
3. Add output format contracts to `research/SKILL.md` and `engine/agent-repo-init/SKILL.md`.
4. Resolve the dual-source inconsistency between `skills/agent-repo-init/SKILL.md` and its engine counterpart.
