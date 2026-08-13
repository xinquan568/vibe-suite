# NLPM Audit: 888wing/codetape
**Date**: 2026-04-06  |  **Artifacts**: 17  |  **Strategy**: single
**NL Score**: 88/100
**Security**: CLEAR
**Bugs**: 4  |  **Quality Issues**: 22  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skill/SKILL.md | skill | 50 | Missing name + description frontmatter |
| skills/codetape/SKILL.md | skill | 50 | Missing name + description frontmatter |
| commands/trace-log.md | command | 85 | No empty input handling; missing allowed-tools |
| skill/commands/trace-log.md | command | 85 | No empty input handling; missing allowed-tools |
| commands/trace-commit.md | command | 91 | Vague terms ("well-structured", "concise"); missing allowed-tools |
| skill/commands/trace-commit.md | command | 91 | Vague terms ("well-structured", "concise"); missing allowed-tools |
| commands/trace-init.md | command | 93 | Vague "likely component roots"; missing allowed-tools |
| skill/commands/trace-init.md | command | 93 | Vague "likely component roots"; missing allowed-tools |
| commands/trace-sync.md | command | 93 | Vague "appropriate template"; missing allowed-tools |
| skill/commands/trace-sync.md | command | 93 | Vague "appropriate template"; missing allowed-tools |
| commands/trace-map.md | command | 95 | Missing allowed-tools |
| skill/commands/trace-map.md | command | 95 | Missing allowed-tools |
| commands/trace-review.md | command | 95 | Missing allowed-tools |
| skill/commands/trace-review.md | command | 95 | Missing allowed-tools |
| commands/trace.md | command | 95 | Missing allowed-tools |
| skill/commands/trace.md | command | 95 | Missing allowed-tools |
| .claude-plugin/plugin.json | config | 100 | Clean |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts | scripts/drift-check.sh, scripts/init-codetape.sh, scripts/stats.sh |
| CLI binaries | bin/codetape.js, src/cli/doctor.js, src/cli/init.js, src/cli/install.js, src/cli/serve.js, src/cli/status.js, src/cli/uninstall.js |
| Utilities | src/dashboard.js, src/utils/copy-skill.js, src/utils/detect-project.js, src/utils/inject-claude-md.js, src/utils/load-codetape-data.js, src/utils/scaffold.js |
| Package manifest | package.json |
| MCP configs | none |
| Hooks | none |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | src/cli/serve.js | 51, 62 | SEC-permissive-cors | `Access-Control-Allow-Origin: *` on the /api/data and /events SSE endpoints; any browser tab can cross-origin-fetch local trace data from the running dashboard |
| 2 | Low | src/cli/serve.js | 102 | SEC-shell-exec | `child_process.exec()` used with a template literal (`${openCmd} ${url}`); both variables are controlled (platform-derived constant + parseInt'd port) so risk is negligible, but exec() spawns a shell unnecessarily — prefer `execFile` or `spawn` |
| 3 | Low | src/dashboard.js | 45 | SEC-unpinned-semver | External CDN script loaded without Subresource Integrity (SRI) hash: `cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js`; CDN compromise could inject malicious JavaScript into the local dashboard |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skill/SKILL.md | Missing `name` frontmatter field | Claude Code skill discovery and display may fail without `name`; registration incomplete |
| 2 | skill/SKILL.md | Missing `description` frontmatter field | Skill cannot surface a one-line summary in plugin registries or `@` autocomplete |
| 3 | skills/codetape/SKILL.md | Missing `name` frontmatter field | Same as #1 — this is the npm-distributed copy; installed users are affected |
| 4 | skills/codetape/SKILL.md | Missing `description` frontmatter field | Same as #2 — affects all users who install via `npx codetape install` |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | src/cli/serve.js | CORS `*` exposes local trace data to any origin | Replace `'Access-Control-Allow-Origin': '*'` with `'Access-Control-Allow-Origin': 'http://localhost'` or restrict to same-origin only |
| 2 | src/cli/serve.js | `exec()` used for browser-open | Replace `exec(\`${openCmd} ${url}\`)` with `execFile(openCmd, [url])` to avoid shell invocation |
| 3 | src/dashboard.js | CDN script without SRI | Add `integrity="sha384-..."` and `crossorigin="anonymous"` to the mermaid `<script>` tag |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/trace.md | Missing `allowed-tools` frontmatter (needs Read, Bash, Write) | -5 |
| 2 | commands/trace-sync.md | Missing `allowed-tools` frontmatter (needs Read, Write) | -5 |
| 3 | commands/trace-map.md | Missing `allowed-tools` frontmatter (needs Read, Write) | -5 |
| 4 | commands/trace-review.md | Missing `allowed-tools` frontmatter (needs Read, Write) | -5 |
| 5 | commands/trace-init.md | Missing `allowed-tools` frontmatter (needs Read, Write, Bash) | -5 |
| 6 | commands/trace-log.md | Missing `allowed-tools` frontmatter (needs Read) | -5 |
| 7 | commands/trace-commit.md | Missing `allowed-tools` frontmatter (needs Read, Bash) | -5 |
| 8 | skill/commands/trace.md | Missing `allowed-tools` frontmatter (same as commands/trace.md) | -5 |
| 9 | skill/commands/trace-sync.md | Missing `allowed-tools` frontmatter | -5 |
| 10 | skill/commands/trace-map.md | Missing `allowed-tools` frontmatter | -5 |
| 11 | skill/commands/trace-review.md | Missing `allowed-tools` frontmatter | -5 |
| 12 | skill/commands/trace-init.md | Missing `allowed-tools` frontmatter | -5 |
| 13 | skill/commands/trace-log.md | Missing `allowed-tools` frontmatter | -5 |
| 14 | skill/commands/trace-commit.md | Missing `allowed-tools` frontmatter | -5 |
| 15 | commands/trace-commit.md | Vague term "well-structured" in opening sentence | -2 |
| 16 | commands/trace-commit.md | Vague term "concise summary" in step 3 | -2 |
| 17 | skill/commands/trace-commit.md | Vague term "well-structured" in opening sentence | -2 |
| 18 | skill/commands/trace-commit.md | Vague term "concise summary" in step 3 | -2 |
| 19 | commands/trace-init.md | Vague term "likely component roots" in step 2 | -2 |
| 20 | skill/commands/trace-init.md | Vague term "likely component roots" in step 2 | -2 |
| 21 | commands/trace-sync.md | Vague term "appropriate template" in step 4c | -2 |
| 22 | skill/commands/trace-sync.md | Vague term "appropriate template" in step 4c | -2 |
| 23 | commands/trace-log.md | No empty input handling — no fallback described when invoked without arguments | -10 |
| 24 | skill/commands/trace-log.md | No empty input handling — no fallback described when invoked without arguments | -10 |

## Cross-Component
**CC-1 — Commands directory not wired in plugin.json**: `.claude-plugin/plugin.json` has no `commands` array. The `commands/` directory is present in the repo and referenced from `package.json` `files`, but if Claude Code's plugin system requires an explicit declaration to discover command files, users who install via `claude plugin install` (rather than `npx codetape init`) will not get the commands registered. The npm path (`copy-skill.js`) correctly copies `skill/commands/` to `.claude/commands/`, but the plugin manifest path is silent on commands.

**CC-2 — Duplicate command trees risk content drift**: Both `commands/` and `skill/commands/` contain identical copies of all seven command files. `copy-skill.js` copies from `skill/commands/` only, making `commands/` an orphan copy that can silently drift if one path is updated without the other. No automation enforces their equivalence.

**CC-3 — Commands embed unresolved `@references/` and `@templates/` paths**: Every command file references skill-internal documents (`@references/trace_schema.md`, `@templates/session_summary.md`, etc.) that only exist after the skill is installed. If a user copies a command file manually without the full skill, these references will fail silently with no error message from the command itself.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

Priority order:
1. **Bug PR**: Add frontmatter (`name`, `description`) to `skill/SKILL.md` and `skills/codetape/SKILL.md` — affects all installed users.
2. **Security PR**: Fix CORS headers in `src/cli/serve.js` (Medium) and optionally add SRI to the mermaid CDN script.
3. **Quality PR**: Add `allowed-tools` frontmatter to all 14 command files and tighten vague terms.
4. **Cross-component PR**: Clarify the `commands/` vs `skill/commands/` duplication — either remove `commands/` or add a `commands` declaration to `plugin.json`.
