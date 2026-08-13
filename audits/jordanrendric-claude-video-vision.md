# NLPM Audit: jordanrendric/claude-video-vision
**Date**: 2026-04-06  |  **Artifacts**: 5  |  **Strategy**: single
**NL Score**: 79/100
**Security**: CLEAR
**Bugs**: 4  |  **Quality Issues**: 12  |  **Security Findings**: 2

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/watch-video.md | command | 56/100 | Missing `name` frontmatter (-25), no empty-input handling (-10), no allowed-tools (-5) |
| commands/setup-video-vision.md | command | 66/100 | Missing `name` frontmatter (-25), no allowed-tools (-5), vague language (-4) |
| agents/frame-describer.md | agent | 81/100 | Zero example blocks (-15), vague language (-4) |
| skills/video-perception/SKILL.md | skill | 92/100 | Four vague quantifiers (-8) |
| .claude-plugin/plugin.json | manifest | 100/100 | Version skew vs mcp-server/package.json (cross-component only) |

**Weighted average**: (100 + 81 + 66 + 56 + 92) / 5 = **79/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts | 0 |
| MCP configs | `.mcp.json` |
| Package manifests | `mcp-server/package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | .mcp.json | 4 | runtime-package-install | `npx -y claude-video-vision@latest` auto-installs the latest npm package on every invocation with no version pin — any future publish to the `latest` tag (including a compromised one) is immediately trusted and executed as the MCP server |
| 2 | Low | mcp-server/package.json | 28 | unpinned-semver | Production dependencies (`@modelcontextprotocol/sdk`, `zod`, `@google/genai`, `openai`) all use `^` semver ranges, allowing minor and patch updates without explicit review |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | commands/setup-video-vision.md | Missing `name` frontmatter field | Command will not register in the plugin's slash-command list; users cannot invoke `/setup-video-vision` |
| 2 | commands/watch-video.md | Missing `name` frontmatter field | Command will not register; users cannot invoke `/watch-video` |
| 3 | commands/setup-video-vision.md | Missing `allowed-tools` frontmatter — calls `video_configure`, `video_setup`, `video_watch` with no tool declarations | Tool calls may be blocked at runtime depending on session permission mode |
| 4 | commands/watch-video.md | Missing `allowed-tools` frontmatter — calls `video_info`, `video_analyze`, `video_watch`, `video_detail`, `video_setup` with no tool declarations | Same as above; entire command workflow is at risk |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | .mcp.json | `@latest` unpinned MCP server version with auto-install flag | Pin to a specific version: `"args": ["-y", "claude-video-vision@1.3.1"]` — update on intentional releases only |
| 2 | mcp-server/package.json | `^` semver ranges on production dependencies | Pin to exact versions (`"@modelcontextprotocol/sdk": "1.12.0"`) or use a lock-file-only strategy; at minimum document that `package-lock.json` must be committed |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/frame-describer.md | Zero example blocks — agent has no examples showing expected input/output | -15 |
| 2 | agents/frame-describer.md | Vague quantifier "concise" (line 11): "write a concise but detailed description" — no objective measure | -2 |
| 3 | agents/frame-describer.md | Vague quantifier "key" (line 15): "key objects" — reader cannot determine selection threshold | -2 |
| 4 | commands/setup-video-vision.md | Vague quantifier "brief" (line 124): "show a brief summary of the results" — no scope defined | -2 |
| 5 | commands/setup-video-vision.md | Vague quantifier "concise" (line 131): "keep it concise" — unenforceable | -2 |
| 6 | commands/watch-video.md | No empty-input handling: if the user invokes the command with no arguments the command requires a video path but provides no fallback or error instruction | -10 |
| 7 | commands/watch-video.md | Vague quantifier "smart" (line 23): "plan smart frame extraction" — undefined standard | -2 |
| 8 | commands/watch-video.md | Vague quantifier "comprehensive" (line 32): "give a comprehensive summary" — no coverage criteria | -2 |
| 9 | skills/video-perception/SKILL.md | Vague quantifier "smart" (line 30): "make smart extraction decisions" | -2 |
| 10 | skills/video-perception/SKILL.md | Vague quantifier "relevant" (line 31): "Select filters relevant to the user's question" — selection criteria are implicit | -2 |
| 11 | skills/video-perception/SKILL.md | Vague quantifier "insufficient" (line 62): "if the initial view is insufficient" — no objective threshold | -2 |
| 12 | skills/video-perception/SKILL.md | Vague quantifier "complete" (line 96): "form a complete understanding" — completeness is unverifiable | -2 |

## Cross-Component
**Version skew**: `plugin.json` declares version `1.2.0` but `mcp-server/package.json` is at `1.3.1`. The `.mcp.json` installs via `@latest`, so the runtime MCP server is likely at 1.3.1 or newer regardless of either declared version. Plugin marketplaces will surface 1.2.0 to users while they receive 1.3.1 code. Fix: synchronize `plugin.json` version with `mcp-server/package.json` as part of each release.

**Missing `name` in both commands** also means neither command will appear under the plugin's registered slash-command list, making the plugin's primary UX surface unreachable via the command palette without manual discovery.

**Skill/command consistency is good**: the `video-perception` skill and `watch-video` command describe the same workflow with consistent step ordering, tool names, and threshold values (30s analyze gate, short/long video split at 2 min). No contradictions found.

**Agent reference is intact**: `setup-video-vision.md` asks users to configure `frame_describer_model`, correctly presupposing the `frame-describer` agent exists and is configurable. The agent file is present and consistent with that expectation.

## Recommendation
CLEAR — submit PRs for all bugs (missing `name` frontmatter in both commands, missing `allowed-tools` in both commands) and medium/low security fixes (pin MCP server version in `.mcp.json`, document lock-file policy for npm dependencies). Quality issues are informational; address in a follow-up or alongside the bug fixes.
