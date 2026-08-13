# NLPM Audit: tirth8205/code-review-graph
**Date**: 2026-04-29  |  **Artifacts**: 9  |  **Strategy**: single
**NL Score**: 95/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 11  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/debug-issue/SKILL.md | skill | 88/100 | Missing output format (-10), "related" vague (-2) |
| skills/explore-codebase/SKILL.md | skill | 88/100 | Missing output format (-10), "complex" vague (-2) |
| skills/refactor-safely/SKILL.md | skill | 88/100 | Missing output format (-10), "major" vague (-2) |
| skills/review-pr/SKILL.md | skill | 94/100 | "large", "related", "significant" vague (-6) |
| skills/build-graph/SKILL.md | skill | 98/100 | "rarely" vague (-2) |
| skills/review-delta/SKILL.md | skill | 98/100 | "many" vague (-2) |
| CLAUDE.md | project-config | 98/100 | "significant" vague (-2) |
| hooks/hooks.json | hook-config | 100/100 | — |
| skills/review-changes/SKILL.md | skill | 100/100 | — |

**Weighted average**: (88+88+88+94+98+98+98+100+100) / 9 = **95/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks (hooks.json) | hooks/hooks.json |
| Hook scripts | hooks/session-start.sh |
| MCP config | .mcp.json |
| VS Code extension manifest | code-review-graph-vscode/package.json |
| Python source (embeddings, subprocess) | code_review_graph/embeddings.py, code_review_graph/incremental.py, code_review_graph/tools/context.py |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | .mcp.json | 5 | unpinned-package-version | `uvx code-review-graph serve` runs without a version pin — always fetches the latest PyPI version, so a compromised or accidentally broken release would be auto-adopted |
| 2 | Medium | code_review_graph/embeddings.py | 195 | network-call-with-credentials | Makes HTTP requests to external APIs (MiniMax, Google Gemini, OpenAI-compatible) with API keys from env vars; code content is sent to third-party services when embeddings are enabled |
| 3 | Low | code-review-graph-vscode/package.json | 297–309 | unpinned-semver | npm dependencies use caret ranges (`better-sqlite3 ^12.4.1`, `d3 ^7.9.0`, `esbuild ^0.20.0`) without a committed lockfile, allowing unexpected minor/patch upgrades on install |

**Notes on clean surfaces:**
- `hooks/session-start.sh`: uses a single-quoted heredoc (`<<'INSTRUCTIONS'`) so no variable interpolation; DB_PATH is hardcoded; no user input reaches the shell. Clean.
- `hooks/hooks.json`: all three hook commands invoke the `code-review-graph` CLI with static arguments. No shell injection vector. The `PostToolUse(Write|Edit|Bash)` trigger is broad but safe.
- `code_review_graph/incremental.py`: all `subprocess.run` calls use list-form arguments (not `shell=True`). Clean.
- Cloud embeddings require explicit opt-in via `CRG_ACCEPT_CLOUD_EMBEDDINGS=1`; no ambient data exfiltration.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/build-graph/SKILL.md | Notes section lists 14 supported languages but CLAUDE.md documents 19 (missing Dart, R, Perl, Lua, Jupyter/Databricks notebooks) | Misleads contributors and users about the parser's actual language coverage |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | .mcp.json | No version pin on `uvx code-review-graph` | Change to `uvx code-review-graph==<current-version> serve`; update after each intentional release |
| 2 | code-review-graph-vscode/package.json | Caret semver ranges on npm deps | Pin to exact versions or commit `package-lock.json`; run `npm install --save-exact` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/debug-issue/SKILL.md | No output format — steps describe tool usage but don't specify what the debugging report should contain | -10 |
| 2 | skills/explore-codebase/SKILL.md | No output format — no guidance on what the exploration summary should look like | -10 |
| 3 | skills/refactor-safely/SKILL.md | No output format — no template for the refactoring plan or safety report | -10 |
| 4 | skills/debug-issue/SKILL.md | "related" is a vague quantifier (line 12): "find code related to the issue" | -2 |
| 5 | skills/explore-codebase/SKILL.md | "complex" is a vague quantifier (line 23): "identify complex code" | -2 |
| 6 | skills/refactor-safely/SKILL.md | "major" is a vague quantifier (line 21): "before major refactors" | -2 |
| 7 | skills/review-pr/SKILL.md | "large" is a vague quantifier (line 64): "For large PRs" | -2 |
| 8 | skills/review-pr/SKILL.md | "related" is a vague quantifier (line 65): "find related code the PR might have missed" | -2 |
| 9 | skills/review-pr/SKILL.md | "significant" is a vague quantifier (line 30): "files with significant changes" | -2 |
| 10 | skills/review-delta/SKILL.md | "many" is a vague quantifier (line 26): "Files with many dependents (high-risk changes)" | -2 |
| 11 | CLAUDE.md | "significant" is a vague quantifier (line 170): "This saves significant tokens by avoiding full codebase scans" | -2 |

## Cross-Component
**CC-1 — Terminology drift (MCP tool names):** `review-delta` and `review-pr` reference MCP tools with a `_tool` suffix (e.g. `get_review_context_tool`, `query_graph_tool`, `build_or_update_graph_tool`), while `debug-issue`, `explore-codebase`, and `review-changes` use bare tool names (`get_review_context`, `query_graph`). CLAUDE.md's Key Tools table uses bare names. The runtime tool names are authoritative; all skills should agree on them. Affects 5 of 7 skills.

**CC-2 — Stale language count in build-graph Notes:** `skills/build-graph/SKILL.md` line 38 lists 14 languages. `CLAUDE.md` architecture section explicitly lists 19, naming R, Perl, Lua, Dart, and Jupyter/Databricks notebooks as additions. This is the same issue as Bug #1 and also a cross-component consistency gap.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

Three skills (`debug-issue`, `explore-codebase`, `refactor-safely`) lack output format sections; adding them would bring each from 88 → 98. The MCP tool name suffix inconsistency across skills is the highest-priority cross-component fix because it is the one most likely to cause Claude to call non-existent tool variants.
