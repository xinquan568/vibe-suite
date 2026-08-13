# NLPM Audit: peterfei/ai-agent-team
**Date**: 2026-04-06  |  **Artifacts**: 23  |  **Strategy**: batched
**NL Score**: 82/100
**Security**: BLOCKED
**Bugs**: 3  |  **Quality Issues**: 12  |  **Security Findings**: 9

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/README.md | Doc | 35 | Missing frontmatter (documentation file, not an invocable command) |
| .claude/skills/thread-manager/SKILL.md | Skill | 40 | Missing required frontmatter (name, description) — skill unregistered |
| .claude/agents/devops_engineer.md | Agent | 63 | Zero interaction examples (-15); no output-format section (-10); vague cap (-12) |
| .claude/agents/tech-leader.md | Agent | 65 | Zero interaction examples (-15); vague-quantifier cap reached (-20) |
| .claude/agents/product_manager.md | Agent | 80 | Vague-quantifier cap reached (-20) |
| .claude/skills/drawnote/SKILL.md | Skill | 80 | Vague-quantifier cap reached (-20) |
| .claude/skills/softcopyright/SKILL.md | Skill | 80 | Vague-quantifier cap reached (-20) |
| .claude/agents/backend_dev.md | Agent | 81 | Sparse interaction examples (-5); vague language (-14) |
| .claude/agents/qa_engineer.md | Agent | 82 | Vague quantifiers (-18): 全面 x4, 清晰 x2, 彻底 x1, 有效 x1 |
| .claude/agents/frontend_dev.md | Agent | 82 | Vague quantifiers (-18): 适当 x3, 清晰 x2, 合理 x2, 良好 x1 |
| .claude/CLAUDE.md | Config | 82 | Vague quantifiers (-18): 清晰 x4, 具体 x2, 完整 x2 |
| .claude/commands/pm-start.md | Command | 89 | No allowed-tools (-5); minor vague language (-6) |
| .claude/commands/start-task.md | Command | 90 | No allowed-tools (-5); broken agent file reference |
| .claude/commands/t.md | Command | 90 | No allowed-tools (-5); minimal body for alias command |
| .claude/skills/tidymydesktop/SKILL.md | Skill | 92 | Minor vague language (-8) |
| .claude/skills/changelog-generator/SKILL.md | Skill | 94 | Minor vague language (-6) |
| .claude/commands/threads.md | Command | 95 | No allowed-tools (-5) |
| .claude/commands/tl-start.md | Command | 95 | No allowed-tools (-5); broken file reference |
| .claude/commands/qa-start.md | Command | 95 | No allowed-tools (-5) |
| .claude/commands/ops-start.md | Command | 95 | No allowed-tools (-5) |
| .claude/commands/thread.md | Command | 95 | No allowed-tools (-5) |
| .claude/commands/fe-start.md | Command | 95 | No allowed-tools (-5) |
| .claude/commands/be-start.md | Command | 95 | No allowed-tools (-5) |

**Score computation**: simple average of 23 artifacts = 1890 / 23 = **82/100**. The `.claude/commands/README.md` is documentation with no YAML frontmatter; it would not be registered as a command. Excluded from threshold check but included in average.

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 3 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 4 (`.claude/hooks/record-user-message.sh`, `record-assistant-message.sh`, `record-message.js`, `test-hook.sh`) |
| Scripts | 77 (`scripts/`, `bin/`, `.claude/agents/cli.sh`, `.claude/skills/*/scripts/`, etc.) |
| MCP configs | 1 (`.mcp.json` — empty `mcpServers: {}`) |
| Package manifests | 1 (`package.json` with `preinstall` + `postinstall` lifecycle hooks) |

> **Pre-scan discrepancy**: Pre-scan reported "Hooks: 0 files" because it searched `hooks/` at repo root; actual hooks live at `.claude/hooks/` (4 files). Detailed scan scope expanded accordingly.

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Critical | `install.sh` | 4 | SEC-curl-pipe-sh | Comment documents `curl \| bash` installation pattern; script is explicitly designed to be fetched from a remote URL and piped directly into bash without integrity verification |
| 2 | High | `scripts/install-clt.sh` | 14 | SEC-sql-injection | Shell variable `$thread_prefix` is directly interpolated into SQLite query string with no sanitization; malicious argument could corrupt threads database (e.g., `' OR '1'='1'; DELETE FROM threads; --`) |
| 3 | High | `package.json` | 11 | SEC-postinstall-script | `postinstall` lifecycle script executes `scripts/postinstall.js` automatically on every `npm install`; actual content prints a banner (low actual risk) but the hook is unconditionally active |
| 4 | High | `bin/ai-agent-team.js` | 168 | SEC-shell-true | `spawnSync('npm', ...)` called with `shell: true` at lines 168, 176, and 188; args are currently hardcoded so injection is not immediately exploitable, but `shell: true` on an array invocation is unnecessary and should be removed |
| 5 | Medium | `scripts/install.sh` | 143 | SEC-file-write-outside-repo | Copies agent/command/CLAUDE.md files to `~/.claude/` and creates timestamped backup directories in the user's home directory |
| 6 | Medium | `scripts/install-clt.sh` | 40 | SEC-file-write-outside-repo | Appends shell function aliases to `~/.zshrc` without explicit per-session confirmation from the user |
| 7 | Medium | `.claude/hooks/record-user-message.sh` | 1 | SEC-env-access | `UserPromptSubmit` hook captures every user prompt and records it to local SQLite DB via `record-message.js`; expected thread-manager behavior but not disclosed prominently during install |
| 8 | Low | `package.json` | 125 | SEC-unpinned-semver | `@xenova/transformers: "^2.17.2"` and `puppeteer: "^24.31.0"` use caret ranges; automatic minor/patch upgrades can introduce vulnerabilities or breaking changes |
| 9 | Low | `package.json` | 126 | SEC-runtime-package-install | `puppeteer` downloads a ~300 MB Chromium browser binary on install; users may not expect this large implicit binary dependency |

**False positive noted**: `package.json` line 10 (`preinstall: node scripts/preinstall.js`) matches the preinstall-script pattern. Actual content only reads `process.version` and `process.platform` with no system modification or network access — **false positive**.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `.claude/commands/start-task.md` | Role-mapping table references `.claude/agents/tech_leader.md` (underscore) but actual filename is `tech-leader.md` (hyphen) | `/start-task tl "..."` silently loads wrong or no agent; tech-lead role broken |
| 2 | `.claude/commands/tl-start.md` | Step 3 instructs reading `.claude/agents/tech_leader.md` (underscore) but actual filename is `tech-leader.md` (hyphen) | `/tl-start "..."` silently fails to load tech-leader persona |
| 3 | `.claude/skills/thread-manager/SKILL.md` | No YAML frontmatter at all — missing required `name` and `description` fields | Skill will not be registered; all thread-manager-dependent commands warn or fail silently at invocation |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `scripts/install-clt.sh` | `$thread_prefix` interpolated into SQLite query (finding #2 is HIGH — **private disclosure** first; listed here for completeness only) | Validate `$thread_prefix` is alphanumeric (`^[a-zA-Z0-9-]+$`) before passing to sqlite3; do not open a public PR before private report |
| 2 | `scripts/install-clt.sh` | Appends to `~/.zshrc` without user confirmation or content preview | Prompt user and show aliases before writing; add idempotency check on exact function body, not just header comment |
| 3 | `package.json` | Unpinned semver ranges for `@xenova/transformers` and `puppeteer` | Pin to exact versions or commit `package-lock.json`; add npm audit to CI |
| 4 | `.claude/hooks/record-user-message.sh` | Conversation capture behavior not documented in README or install flow | Add disclosure to README and print a notice during `npx ai-agent-team init` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | `.claude/agents/devops_engineer.md` | Zero interaction examples — no `## 示例交互` section showing user/agent request-response flow | -15 |
| 2 | `.claude/agents/tech-leader.md` | Zero interaction examples | -15 |
| 3 | `.claude/agents/devops_engineer.md` | No `## 输出格式` section defining expected response structure for deployment plans, CI/CD reports, etc. | -10 |
| 4 | `.claude/agents/backend_dev.md` | Has code templates but no dedicated user/agent interaction examples | -5 |
| 5 | All 6 agents | `model: inherit` declared but no concrete model tier specified; agents will inherit whatever model the parent uses, making behavior unpredictable across contexts | 0 (declared, no penalty) |
| 6 | All 10 command files | Missing `allowed-tools` declaration in frontmatter; commands invoke MCP tools (`mcp__thread-manager__*`) that are not listed | -5 each |
| 7 | `.claude/agents/tech-leader.md` | Vague-quantifier cap reached: 清晰 x4, 合理 x3, 详细 x3, 完整 x2, 及时 x1 | -20 |
| 8 | `.claude/agents/product_manager.md` | Vague-quantifier cap reached: 清晰 x3, 全面 x2, 直观 x1, 现实的 x1, 具体 x2 | -20 |
| 9 | `.claude/skills/drawnote/SKILL.md` | Vague-quantifier cap: 完整 x3, 清晰 x3, 合理 x2, 适当 x2, 专业 x2 | -20 |
| 10 | `.claude/skills/softcopyright/SKILL.md` | Vague-quantifier cap: 清晰 x3, 专业 x2, 完整 x2, 准确 x2 | -20 |
| 11 | `.claude/agents/qa_engineer.md` | Vague quantifiers: 全面 x4, 清晰 x2, 彻底 x1, 有效 x1 | -18 |
| 12 | `.claude/agents/frontend_dev.md` | Vague quantifiers: 适当 x3, 清晰 x2, 合理 x2, 良好 x1 | -18 |

## Cross-Component
1. **Broken agent name across two commands**: `commands/start-task.md` (role-mapping table) and `commands/tl-start.md` (Step 3 instruction) both reference `tech_leader.md` (underscore), while the actual file is `tech-leader.md` (hyphen). Any user invoking `/start-task tl` or `/tl-start` will silently get the wrong behavior.

2. **Unregistered thread-manager skill creates invisible dependency**: `skills/thread-manager/SKILL.md` has no frontmatter and is therefore not registered as a skill. All thread-based commands (`threads`, `thread`, `pm-start`, `be-start`, `fe-start`, `qa-start`, `ops-start`, `tl-start`, `start-task`, `t`) depend on `mcp__thread-manager__*` tools and document thread-manager in `CLAUDE.md`, yet the skill dependency is undeclared and invisible to the registry.

3. **Orphaned documentation links in README.md**: `.claude/commands/README.md` links to `../../docs/THREAD_AGENT_INTEGRATION.md` and `../../docs/THREAD_CONTEXT_ISOLATION_DESIGN.md`, but the `docs/` directory is not listed in `package.json`'s `files` field. Installed packages will have broken documentation links.

4. **Hook path vs. pre-scan expectation**: Pre-scan searched `hooks/**` (root level). Actual hooks at `.claude/hooks/**` went undetected by the scanner's path pattern. Future scans should include `.claude/hooks/**`.

## Recommendation
BLOCKED — do not submit PRs. File private security report.

**Critical finding** (finding #1): `install.sh` is explicitly designed for `curl | bash` installation. If the GitHub repository or CDN is compromised, all downstream installations receive arbitrary code execution with no integrity check. This is a supply-chain risk that requires coordinated disclosure or architectural change (e.g., package signature verification, SHA-pinned curl download).

**High finding** (finding #2): SQL injection in `scripts/install-clt.sh` line 14 via unsanitized `$thread_prefix`. While blast radius is the user's local SQLite database, the pattern permits arbitrary SQL execution including full table deletion. Fix privately before publishing a patch.

After Critical/High issues are resolved, the following NL fix PRs are ready:
- Fix `tech_leader.md` → `tech-leader.md` references in `start-task.md` and `tl-start.md`
- Add YAML frontmatter to `skills/thread-manager/SKILL.md`
- Add `allowed-tools` declarations to all command files
- Add interaction examples to `devops_engineer.md` and `tech-leader.md`
- Add output-format section to `devops_engineer.md`
