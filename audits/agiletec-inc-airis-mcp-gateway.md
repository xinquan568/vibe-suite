# NLPM Audit: agiletec-inc/airis-mcp-gateway
**Date**: 2026-04-26  |  **Artifacts**: 11  |  **Strategy**: single
**NL Score**: 90/100
**Security**: BLOCKED
**Bugs**: 0  |  **Quality Issues**: 14  |  **Security Findings**: 9

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `config/bootstrap/assets/claude/commands/airis-research-first.md` | command | 78 | No output format + unnumbered multi-step rules |
| `skills/skills/mcp-database/SKILL.md` | skill | 83 | No examples + vague "appropriate caution" |
| `skills/skills/mcp-debugging/SKILL.md` | skill | 85 | No examples |
| `skills/skills/mcp-implementation/SKILL.md` | skill | 85 | No examples |
| `skills/skills/mcp-research/SKILL.md` | skill | 85 | No examples |
| `.claude/commands/troubleshoot.md` | command | 90 | No empty $ARGUMENTS handling |
| `.claude/commands/test.md` | command | 96 | Vague "some servers" + "actionable" |
| `.claude/commands/status.md` | command | 97 | `Bash(curl*)` declared but not used in body |
| `config/bootstrap/assets/claude/commands/airis-capability-router.md` | command | 98 | Vague "briefly" |
| `CLAUDE.md` | project-instructions | 98 | Vague "significant tokens" |
| `skills/.claude-plugin/plugin.json` | plugin-manifest | 100 | — |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 1 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Shell scripts (scripts/) | `scripts/quick-install.sh`, `scripts/airis-gateway`, `scripts/demo-for-gif.sh`, `scripts/record-gif.sh`, `scripts/test-airis-gateway-smoke.sh` |
| Shell scripts (root) | `install.sh` |
| Shell scripts (apps/) | `apps/api/entrypoint.sh`, `apps/api/start.sh` |
| Shell scripts (ops/) | `ops/autostart/linux/install.sh`, `ops/autostart/linux/uninstall.sh`, `ops/autostart/macos/install.sh`, `ops/autostart/macos/uninstall.sh` |
| Python scripts (scripts/) | `scripts/airis_bootstrap.py` |
| App Python source (apps/api/src/) | ~55 files (application code, not direct execution surfaces) |
| Hooks | 0 |
| MCP configs (.mcp.json) | 0 |
| package.json | `skills/package.json`, `apps/gateway-control/package.json`, `apps/airis-commands/package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | `install.sh` | 6 | `SEC-curl-pipe-sh` | Usage comment documents `curl -fsSL .../install.sh \| bash` as the standard installation method — no integrity check or hash verification |
| 2 | Critical | `scripts/quick-install.sh` | 6 | `SEC-curl-pipe-sh` | Same `curl \| bash` pattern documented as standard installation — users who follow docs run arbitrary code from GitHub |
| 3 | Critical | `install.sh` | 119 | `SEC-curl-pipe-sh` | Downloads remote `airis-gateway` shell script then immediately executes it (`chmod +x` + execute at line 129) without hash verification — functionally equivalent to `curl \| bash` |
| 4 | High | `scripts/airis-gateway` | 123 | `SEC-curl-pipe-sh` | Downloads `airis_bootstrap.py` from GitHub raw URL without integrity check; script is executed at line 358 via `python3 "$DIR/scripts/airis_bootstrap.py"` |
| 5 | Medium | `install.sh` | 163 | `SEC-curl-pipe-sh` | `curl -fsSL "$url" \| tar -xz -C "$BIN_DIR"` downloads and unpacks binary from GitHub releases without checksum or signature verification |
| 6 | Medium | `scripts/quick-install.sh` | 153 | `SEC-curl-pipe-sh` | Same `curl \| tar` pattern for `airis-workspace` binary download — no checksum verification |
| 7 | Medium | `scripts/airis-gateway` | 262 | `SEC-shell-injection` | `server = '$server'` interpolates shell variable directly into Python heredoc; a server name containing `'` or `$(...)` can corrupt the Python code block in `cmd_enable` (line 310 has the same pattern in `cmd_disable`) |
| 8 | Low | `install.sh` | 11 | `SEC-unpinned-semver` | `VERSION="${AIRIS_VERSION:-latest}"` defaults to `latest` — no pinned version means any future push to main/latest tag automatically affects all new installs |
| 9 | Low | `scripts/airis-gateway` | 15 | `SEC-unpinned-semver` | `BASE_URL` constructed with `${AIRIS_VERSION:-latest}` — all remote file downloads resolve against the latest tag without a pinned version |

## Bugs (PR-worthy)
No registration-breaking bugs found. All commands have `allowed-tools`, no broken internal references, no tools invoked outside declared allowed-tools.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `scripts/airis-gateway` | Shell variable injection in Python heredoc (`cmd_enable`, `cmd_disable`) | Pass server name as a positional arg via `python3 -c "..." "$server"` and read from `sys.argv[1]` instead of shell interpolation |
| 2 | `install.sh` | `curl \| tar` binary download without integrity check | Add SHA-256 checksum verification after download; fetch `.sha256` sidecar from release and verify before executing |
| 3 | `scripts/quick-install.sh` | Same `curl \| tar` issue | Same fix: fetch and verify SHA-256 checksum |
| 4 | `install.sh` | `AIRIS_VERSION` defaults to `latest` | Pin to a specific tag in the distributed installer; allow override via env var but default to pinned |
| 5 | `scripts/airis-gateway` | `BASE_URL` defaults to `latest` | Same: pin default version to a release tag |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `config/bootstrap/assets/claude/commands/airis-research-first.md` | Rules listed as unordered bullets instead of numbered steps | -10 |
| 2 | `config/bootstrap/assets/claude/commands/airis-research-first.md` | No output format section | -10 |
| 3 | `config/bootstrap/assets/claude/commands/airis-research-first.md` | Vague directive: "prefer Playwright CLI guidance" | -2 |
| 4 | `skills/skills/mcp-database/SKILL.md` | No example blocks | -15 |
| 5 | `skills/skills/mcp-database/SKILL.md` | Vague quantifier: "appropriate caution" | -2 |
| 6 | `skills/skills/mcp-debugging/SKILL.md` | No example blocks | -15 |
| 7 | `skills/skills/mcp-implementation/SKILL.md` | No example blocks | -15 |
| 8 | `skills/skills/mcp-research/SKILL.md` | No example blocks | -15 |
| 9 | `.claude/commands/troubleshoot.md` | No empty $ARGUMENTS handling — "Issue Type: $ARGUMENTS" renders blank with no fallback branch | -10 |
| 10 | `.claude/commands/test.md` | Vague quantifier: "at least some servers are 'ready'" | -2 |
| 11 | `.claude/commands/test.md` | Vague quantifier: "actionable troubleshooting steps" | -2 |
| 12 | `.claude/commands/status.md` | `Bash(curl*)` declared in allowed-tools but no direct `curl` invocation in command body — potential unused tool | -3 |
| 13 | `config/bootstrap/assets/claude/commands/airis-capability-router.md` | Vague qualifier: "briefly" in output direction | -2 |
| 14 | `CLAUDE.md` | Vague quantifier: "Saves significant tokens per `initialize`" | -2 |

## Cross-Component
**Undeclared external dependency**: `skills/skills/mcp-debugging/SKILL.md` line 8 directs users to "invoke `superpowers:systematic-debugging` first." The `superpowers` plugin is not listed as a dependency in `skills/.claude-plugin/plugin.json`, and there is no install guard or graceful degradation if that plugin is absent. Users without `superpowers` installed receive broken guidance.

**External reference in command**: `config/bootstrap/assets/claude/commands/airis-research-first.md` references `playwright-cli` skill/guidance. This is also an undeclared external dependency, though the phrasing ("prefer Playwright CLI guidance") implies optional usage and is less severe.

**Internal consistency**: All internal `task *` command references in `.claude/commands/` are consistent with the `CLAUDE.md` task documentation. The MCP tool names referenced in `test.md` match the gateway's documented API surface. No broken internal references found.

## Recommendation
BLOCKED — do not submit PRs. File private security report.

Three critical findings: the distributed installers (`install.sh`, `scripts/quick-install.sh`) document and implement `curl | bash` and download-then-execute patterns without any integrity verification. Finding #3 (download remote shell script → execute) and Finding #4 (download remote Python script → execute) in actual code are the highest-severity issues and require private disclosure before any public contribution. Findings #5–#6 (binary downloads without checksum) and #7 (shell injection in CLI) are suitable for public PRs once the critical/high issues are privately addressed.

NL quality is high (90/100) with no registration-breaking bugs. All 14 quality issues are mechanical and fixable; the four skills lacking examples are the largest single improvement opportunity.
