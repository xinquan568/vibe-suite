# NLPM Audit: zhukunpenglinyutong/jetbrains-cc-gui
**Date**: 2026-04-06  |  **Artifacts**: 1  |  **Strategy**: single
**NL Score**: 98/100
**Security**: BLOCKED
**Bugs**: 1  |  **Quality Issues**: 1  |  **Security Findings**: 8

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.agents/skills/vercel-react-best-practices/SKILL.md` | skill | 98 | Broken reference to `AGENTS.md` (file not present in repo) |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 2 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (JS/MJS) | 62 files in `ai-bridge/`, 3 files in `webview/scripts/` |
| MCP configs | 0 |
| Package manifests | `webview/package.json`, `ai-bridge/package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical (FP) | `src/main/resources/libs/react-dom.production.min.js` | 219 | exec-unsafe-local-function | `MSApp.execUnsafeLocalFunction` call in vendored React DOM production build — IE compatibility shim in minified library, not custom code; false positive |
| 2 | High | `ai-bridge/services/claude/mcp-status/stdio-tools-getter.js` | 95 | shell-true | `spawnOptions.shell = true` set for Windows when command is `npx`/`npm`/`pnpm`/`yarn`/`.cmd`/`.bat`; command originates from user MCP config, enabling shell injection if config is malicious |
| 3 | High | `ai-bridge/services/claude/mcp-status/stdio-verifier.js` | 87 | shell-true | Same `spawn` + `shell: true` pattern as finding #2; same risk surface via user-supplied MCP server command |
| 4 | Medium | `ai-bridge/config/api-config.js` | 293 | tls-reject-unauthorized | `NODE_TLS_REJECT_UNAUTHORIZED=0` can be injected into `process.env` from user's `settings.json`; disables all TLS verification and creates MITM exposure; code emits a warning but still applies the setting |
| 5 | Medium | `ai-bridge/utils/sdk-loader.js` | 178 | dynamic-import-user-path | `import(resolvedUrl)` where `resolvedUrl` is derived from `~/.codemoss/dependencies/` (user-writable); a tampered SDK installation could execute arbitrary code at import time |
| 6 | Medium | `ai-bridge/config/api-config.test.js` | 23 | eval-variable | `execFileSync(process.execPath, ['--input-type=module', '--eval', script], …)` where `script` is a dynamically constructed template string; content is currently derived from static paths but the pattern permits code injection if inputs change |
| 7 | Low | `webview/package.json` | 14 | unpinned-semver | All devDependencies and dependencies use `^` or `~` version ranges; supply-chain substitution attack possible on `npm install` |
| 8 | Low | `ai-bridge/package.json` | 6 | unpinned-semver | `sql.js: "^1.12.0"` uses unpinned semver; same supply-chain concern |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `.agents/skills/vercel-react-best-practices/SKILL.md` | Line 149 references `` `AGENTS.md` `` as "the complete guide with all rules expanded" but no `AGENTS.md` exists anywhere in the repository | Readers following the link get a dead reference; the compiled guide is unavailable |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `ai-bridge/config/api-config.js` | `NODE_TLS_REJECT_UNAUTHORIZED=0` is injected with only a `console.warn` | Refuse to inject the setting in non-local/non-CLI-login modes; require explicit user acknowledgement or document removal from supported env vars |
| 2 | `ai-bridge/utils/sdk-loader.js` | Dynamic ESM import from user-writable `~/.codemoss/dependencies/` with no integrity check | Verify a lockfile or package integrity hash before `import(resolvedUrl)`; at minimum, validate that `resolvedUrl` resolves inside the expected prefix |
| 3 | `webview/package.json` | All dependencies use `^`/`~` semver ranges | Pin all dependencies to exact versions and commit a lockfile (`package-lock.json` or `pnpm-lock.yaml`) |
| 4 | `ai-bridge/package.json` | `sql.js` uses `^1.12.0` | Pin to exact version to prevent silent upgrades |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `.agents/skills/vercel-react-best-practices/SKILL.md` | "Comprehensive" (line 12) is a vague quantifier that doesn't commit to any measurable scope | -2 |

## Cross-Component
**Rule count mismatch**: `metadata.json` (line 5) states "40+ rules across 8 categories" while `SKILL.md` (line 12) states "70 rules across 8 categories". Counting the Quick Reference section yields 70 rules, so `metadata.json` is stale. Both documents ship in the same skill directory and describe the same content; the discrepancy misleads readers about the guide's scope.

**False attribution**: `metadata.json` lists `organization: "Vercel Engineering"` and `SKILL.md` frontmatter lists `metadata.author: vercel`. The repository is owned by `zhukunpenglinyutong`, not Vercel. The content appears to be derived from Vercel's public blog posts, not an official Vercel Engineering release. This is not a scoring violation but is worth surfacing to maintainers.

## Recommendation
BLOCKED — do not submit PRs. File private security report.

Two genuine HIGH-severity findings exist in `ai-bridge/services/claude/mcp-status/`: `spawn` with `shell: true` is conditionally enabled on Windows when handling user-supplied MCP server commands. A malicious MCP configuration could trigger shell injection. The Critical finding (finding #1) is a false positive from a vendored React DOM library and should not be escalated.

After the HIGH findings are resolved (either by disabling `shell: true` and using `shell: false` with explicit argument arrays, or by applying rigorous command allowlisting before enabling the shell), re-run the audit. At that point the one NL bug (broken `AGENTS.md` reference) and medium/low security issues become PR-eligible.
