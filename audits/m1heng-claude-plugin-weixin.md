# NLPM Audit: m1heng/claude-plugin-weixin
**Date**: 2026-04-06  |  **Artifacts**: 3  |  **Strategy**: single
**NL Score**: 97/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 4  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `skills/access/SKILL.md` | skill | 95 | Unused tool `Bash(ls *)` declared but never called (-3) |
| `skills/configure/SKILL.md` | skill | 95 | Unused tool `Bash(mkdir *)` declared but never called (-3) |
| `.claude-plugin/plugin.json` | plugin manifest | 100 | — |

### Score Detail

**`skills/access/SKILL.md`** — 95/100
- Frontmatter complete (name, description, user-invocable, allowed-tools) ✓
- Multi-step sub-commands all use numbered steps ✓
- Empty-argument handling present ("No args — status") ✓
- Output described inline for each sub-command ✓
- `Bash(ls *)` declared in allowed-tools but no `ls` call appears in any step: -3
- Vague quantifier "gracefully" (in "handle ENOENT gracefully"): -2

**`skills/configure/SKILL.md`** — 95/100
- Frontmatter complete ✓
- TWO-STEP login flow uses numbered steps ✓
- Empty-argument handling present ("No args — status and guidance") ✓
- `Bash(ls *)` is explicitly used (to resolve install-dir wildcard) ✓
- `Bash(mkdir *)` declared but no `mkdir` call appears in any step — the bun scripts handle directory creation: -3
- Vague quantifier "complete picture" (in "give the user a complete picture"): -2

**`.claude-plugin/plugin.json`** — 100/100
- All required fields present: name, description, version (valid semver 0.4.0), keywords ✓

---

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
| Hooks | 0 |
| Scripts (shell/py/js) | 0 |
| TypeScript executables | `server.ts`, `login-qr.ts`, `login-poll.ts` |
| MCP configs | `.mcp.json` |
| Package manifests | `package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | `package.json` | 8 | SEC-runtime-install | `start` script runs `bun install` on every server launch, pulling dependency resolution to runtime rather than install time — supply-chain risk |
| 2 | Medium | `login-qr.ts` | 14–16 | SEC-runtime-install | Auto-installs dependencies via `Bun.spawnSync(['bun','install',...])` if `node_modules/qrcode-terminal` is missing — same supply-chain risk |
| 3 | Low | `package.json` | 11–12 | SEC-unpinned-semver | Both dependencies use `^` ranges (`^1.0.0`, `^0.12.0`), allowing unreviewed minor/patch bumps |

**Note — `.mcp.json` `--shell=bun` (line 5)**: `--shell=bun` routes npm script execution through Bun's built-in cross-platform shell rather than `/bin/sh`. This is the *safer* option and does not match the `SEC-shell-true` pattern; marked false-positive in the sidecar.

---

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `.claude-plugin/plugin.json` vs `package.json` / `server.ts` | Version mismatch: plugin.json declares `0.4.0`; package.json and MCP server registration both declare `0.1.0` | Version reported to Claude Code differs from what the MCP server advertises; can confuse update checks |

---

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `package.json` | `bun install` in `start` script runs at MCP server launch | Move install step to a one-time `postinstall` script or require users to run `bun install` manually before first use |
| 2 | `login-qr.ts` | Runtime auto-install via `Bun.spawnSync` | Remove the auto-install block; add a preflight check that prints a clear error if deps are missing, pointing to `bun install` |
| 3 | `package.json` | Unpinned `^` semver ranges | Pin to exact versions (`1.x.y`, `0.12.x`) or use a lockfile-only install (`bun install --frozen-lockfile`) in the start script |

---

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `skills/access/SKILL.md` | `Bash(ls *)` declared in allowed-tools but no `ls` invocation appears in any documented step | -3 |
| 2 | `skills/access/SKILL.md` | "handle ENOENT gracefully" — "gracefully" is a vague quantifier; specify the fallback behavior (return default object) | -2 |
| 3 | `skills/configure/SKILL.md` | `Bash(mkdir *)` declared in allowed-tools but no `mkdir` invocation appears in any configure step — directory creation is delegated to bun scripts | -3 |
| 4 | `skills/configure/SKILL.md` | "give the user a complete picture" — "complete" is a vague quantifier; the subsequent numbered list already makes this concrete | -2 |

---

## Cross-Component

**Version drift** — `plugin.json` (`0.4.0`) vs `package.json` + `server.ts` (`0.1.0`): these appear to be tracking versions independently. The plugin metadata version should match the npm package version so tooling can correlate them. Filed as Bug #1 above.

**Script paths** — `skills/configure/SKILL.md` references `~/.claude/plugins/cache/m1heng-plugins/weixin/*/login-qr.ts`. The actual files (`login-qr.ts`, `login-poll.ts`) exist in the repo root, which is where the plugin cache would copy them. Reference is plausible given typical plugin install layout; no broken path detected.

**State contract** — `skills/access/SKILL.md`, `skills/configure/SKILL.md`, `server.ts`, and `login-poll.ts` all agree on `~/.claude/channels/weixin/` as the state directory, with consistent field names (`dmPolicy`, `allowFrom`, `pending`, `token`, `baseUrl`). No terminology drift.

**Security control cross-check** — `server.ts` includes `assertSendable` (path-traversal guard via `realpathSync`) and atomic writes (tmp → rename). These are not referenced in the skills, which is correct — implementation detail. No gap.

---

## Recommendation

CLEAR — submit PRs for all bugs and medium/low security fixes.

The plugin is well-structured with strong access-control logic and no critical or high security findings. Recommended PRs in priority order:
1. Fix version mismatch between `plugin.json` and `package.json`/`server.ts`
2. Replace runtime `bun install` in `start` script and `login-qr.ts` with an explicit preflight or lockfile-frozen install
3. Pin dependency semver ranges
4. Remove unused `Bash(ls *)` from `skills/access/SKILL.md` and `Bash(mkdir *)` from `skills/configure/SKILL.md`
