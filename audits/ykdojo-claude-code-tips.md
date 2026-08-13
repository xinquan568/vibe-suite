# NLPM Audit: ykdojo/claude-code-tips
**Date**: 2026-04-17  |  **Artifacts**: 9  |  **Strategy**: single
**NL Score**: 93/100
**Security**: REVIEW
**Bugs**: 2  |  **Quality Issues**: 6  |  **Security Findings**: 9

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/upgrade-patches.md | command | 80/100 | Hardcoded machine-specific path `/Users/yk/Desktop/projects/safeclaw`; missing `allowed-tools` |
| CLAUDE.md | project-instructions | 85/100 | Machine-specific GCS URL and safeclaw container references limit reusability |
| skills/clone/SKILL.md | skill | 90/100 | No example blocks; output instruction implicit not explicit |
| skills/handoff/SKILL.md | skill | 95/100 | Minor: no examples |
| skills/half-clone/SKILL.md | skill | 95/100 | Minor: no examples |
| skills/reddit-fetch/SKILL.md | skill | 96/100 | "adjust as needed", "complex searches" — vague quantifiers (-4) |
| skills/gha/SKILL.md | skill | 96/100 | "relevant" ×2 — vague quantifiers (-4) |
| skills/review-claudemd/SKILL.md | skill | 98/100 | "recent" slightly vague (-2) |
| .claude-plugin/plugin.json | manifest | 100/100 | Clean |

**Weighted average**: (80+85+90+95+95+96+96+98+100) / 9 = 835 / 9 ≈ **93/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 5 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (.sh) | 6 (check-context.sh, clone-conversation.sh, color-preview.sh, context-bar.sh, half-clone-conversation.sh, setup.sh, test-half-clone.sh) |
| Scripts (.js) | 1 (generate-toc.js) |
| MCP configs | 0 |
| package.json | 0 |
| requirements.txt | 0 |

> **Pre-scan discrepancy**: Pre-scan reported 275 script files; actual executable files found: 7. The count likely includes all repo files (.md tips, etc.) which are not executable artifacts.

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH | scripts/setup.sh | 158–160 | curl-download + chmod+x | Downloads `context-bar.sh` from raw GitHub URL (`$REPO_URL/scripts/context-bar.sh`) directly to `~/.claude/scripts/` and marks it executable. If the upstream repo is compromised, the downloaded script will execute with user privileges on every Claude Code prompt via the statusLine hook. |
| 2 | HIGH | scripts/setup.sh | 137–143 | sudo + unpinned npm install | `sudo npm install -g cc-safe` installs an unpinned third-party package with root privileges. If `cc-safe` on npm is compromised or typosquatted, arbitrary code runs as root. |
| 3 | MEDIUM | scripts/setup.sh | 119–124 | runtime plugin install | `claude plugin install dx@ykdojo` and `claude plugin marketplace add` execute at setup time without version pinning or checksum verification. |
| 4 | MEDIUM | scripts/setup.sh | 162–163 | file write outside repo | Writes to `~/.claude/settings.json` via jq + mv, modifying the user's global Claude Code configuration. |
| 5 | MEDIUM | scripts/context-bar.sh | 35–64 | user-controlled path in shell | `cwd` extracted from stdin hook JSON is passed directly to `git -C "$cwd"`. While the hook input originates from Claude Code (trusted), an unexpected `cwd` value (e.g., a path with embedded flags) could alter git behavior. |
| 6 | MEDIUM | scripts/clone-conversation.sh | 334 | file write outside repo | Appends user-controlled `display_text` (extracted and escaped from conversation data) to `~/.claude/history.jsonl`. Escaping is applied but the output path is outside the project repo. |
| 7 | MEDIUM | scripts/half-clone-conversation.sh | 528 | file write outside repo | Same pattern as clone-conversation.sh — appends to `~/.claude/history.jsonl`. |
| 8 | LOW | scripts/setup.sh | 137 | unpinned dependency | `npm install -g cc-safe` has no version pin. Future breaking versions or a supply-chain compromise would silently affect all users who run setup. |
| 9 | LOW | scripts/check-context.sh | 26–42 | env var / file read from stdin | `transcript_path` is taken from hook stdin JSON and used to read a file. Claude Code controls this value (trusted), but validation is minimal (`-f` check only). |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/upgrade-patches.md | Hardcoded absolute path `/Users/yk/Desktop/projects/safeclaw` in step **Container** section | Command is non-functional for any user other than the author; `./scripts/run.sh` will not be found |
| 2 | .claude/commands/upgrade-patches.md | Missing `allowed-tools` frontmatter field for a command that invokes Bash (npm, tmux) | Claude Code may prompt for permission on every tool use or silently fail to execute the steps |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/setup.sh | `sudo npm install -g cc-safe` — escalates to root for unpinned package | Pin to a specific version: `sudo npm install -g cc-safe@<version>`; document the expected version; or use `npx cc-safe` to avoid global install |
| 2 | scripts/setup.sh | `curl ... context-bar.sh` then `chmod +x` downloads remote code silently | Add a SHA-256 checksum verification step after download: `echo "<expected-hash>  $CLAUDE_DIR/scripts/context-bar.sh" | sha256sum -c` before chmod |
| 3 | scripts/setup.sh | `npm install -g cc-safe` with no version pin | Pin to a specific known-good version in the script |

> **Note**: HIGH findings #1 and #2 (curl-download+exec, sudo npm) require private disclosure before any public PR activity. See Recommendation.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude/commands/upgrade-patches.md | No formal output format section | -5 |
| 2 | CLAUDE.md | Private GCS URL with project-internal bucket ID embedded in public instructions | informational |
| 3 | CLAUDE.md | `safeclaw` container references are author-specific and opaque to other users | informational |
| 4 | skills/gha/SKILL.md | "relevant error messages or file names" (×2) — vague quantifiers | -4 |
| 5 | skills/reddit-fetch/SKILL.md | "adjust as needed" and "complex searches" — vague quantifiers | -4 |
| 6 | skills/review-claudemd/SKILL.md | "recent conversations" — "recent" is vague without a time bound | -2 |

## Cross-Component
- **Internal references intact**: `skills/clone` → `scripts/clone-conversation.sh` ✓; `skills/half-clone` → `scripts/half-clone-conversation.sh` ✓; `CLAUDE.md` → `scripts/generate-toc.js` ✓.
- **Broken external reference** (Bug #1): `upgrade-patches.md` → `system-prompt/UPGRADING.md` and `/Users/yk/Desktop/projects/safeclaw` are not part of the plugin and will not resolve for other users.
- **Marketplace file**: CLAUDE.md instructs version bumping in both `plugin.json` and `marketplace.json`. The `marketplace.json` file was not included in the audited artifact list but is referenced at `.claude-plugin/marketplace.json`.
- **No orphaned components**: all 6 skills referenced in plugin description (`gha`, `clone`, `half-clone`, `handoff`, `reddit-fetch`, `review-claudemd`) have corresponding SKILL.md files.
- **setup.sh ↔ context-bar.sh coupling**: setup.sh installs context-bar.sh via curl when running in remote mode, creating a dependency on the live GitHub branch rather than the installed plugin version. A plugin update and a setup re-run could get out of sync.

## Recommendation
**REVIEW — submit NL fix PRs, but file a private security report before contributing.**

The two HIGH security findings (curl-download-exec in setup.sh and sudo npm without a version pin) are in an opt-in user-run setup script, not in auto-executing hooks. They do not trigger automatically during normal Claude Code usage. However, per disclosure policy, file a private security issue with the repo author covering findings #1 and #2 before opening public PRs.

Once the HIGH findings are acknowledged, submit public PRs for:
1. Bug fix: remove or parameterize the hardcoded `/Users/yk/Desktop/projects/safeclaw` path in `upgrade-patches.md`
2. Bug fix: add `allowed-tools: [Bash]` to `upgrade-patches.md` frontmatter
3. Medium/Low security fixes: pin `cc-safe` version; add checksum verification to the curl download
