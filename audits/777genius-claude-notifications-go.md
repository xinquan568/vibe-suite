# NLPM Audit: 777genius/claude-notifications-go
**Date**: 2026-04-17  |  **Artifacts**: 8  |  **Strategy**: single
**NL Score**: 63/100
**Security**: BLOCKED
**Bugs**: 8  |  **Quality Issues**: 13  |  **Security Findings**: 8

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/init.md | command | 53 | Missing `name` frontmatter (-25), no output format (-10), no empty-input handling (-10) |
| commands/notifications-settings.md | command/alias | 53 | Missing `name` (-25), 4 unused tools declared (-12), no output format (-10) |
| commands/sounds.md | command | 55 | Missing `name` (-25), not registered in plugin.json, no output format (-10), no empty-input handling (-10) |
| commands/settings.md | command | 60 | Missing `name` (-25), no empty-input handling (-10), no formal output format (-5) |
| commands/notifications-init.md | command/alias | 62 | Missing `name` (-25), Bash declared but unused (-3), no output format (-10) |
| commands/notifications-sounds.md | command/alias | 62 | Missing `name` (-25), not registered in plugin.json, Bash declared but unused (-3), no output format (-10) |
| .claude-plugin/plugin.json | manifest | 70 | `sounds.md` and `notifications-sounds.md` absent from commands array |
| hooks/hooks.json | hooks config | 90 | Well-formed; no structural issues |

**Weighted average**: (53 + 53 + 55 + 60 + 62 + 62 + 70 + 90) / 8 = **63/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 1 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks (hooks.json) | 1 — `hooks/hooks.json` |
| Shell scripts | 6 — `bin/install.sh`, `bin/hook-wrapper.sh`, `bin/bootstrap.sh`, `bin/install_e2e_test.sh`, `bin/install_test.sh`, `scripts/dev-local-plugin.sh`, `scripts/e2e-real-claude.sh`, `scripts/dev-real-plugin.sh`, `scripts/linux-focus-debug.sh` |
| Python scripts | 2 — `bin/mock_server.py`, `scripts/iterm2-select-tab.py` |
| MCP configs | 0 |
| Package manifests | 0 (no package.json, requirements.txt) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | commands/init.md | 38, 45 | curl-download-execute | Downloads `install.sh` from `raw.githubusercontent.com/main` and executes it with `bash` with no integrity check on the script itself. If the `main` branch is compromised, arbitrary code runs in the user's shell during `/init`. |
| 2 | CRITICAL | bin/bootstrap.sh | 756–769 | curl-download-execute | Downloads `INSTALL_SCRIPT_URL` (defaults to `raw.githubusercontent.com/main/bin/install.sh`) and executes it with `bash "$tmp_script"` without any checksum or signature verification of the script. Identical exposure to finding #1 from the one-liner install path. |
| 3 | HIGH | commands/settings.md | 250–265 | user-input-in-path | The `sound_name` variable is extracted from free-form user message text and interpolated directly into a shell file path: `SOUND_PATH="${PLUGIN_ROOT}/sounds/${sound_name}.mp3"`. A user can supply `../../etc/passwd` or other traversal sequences. The surrounding `if/elif` guards do not sanitize the value; they only match known constants for the exact built-in names, leaving the `elif -f /System/Library/Sounds/...` branch and fallback reachable with arbitrary input. |
| 4 | MEDIUM | bin/install.sh | 333–337, 583–598 | network-download-execute | Downloads Go binaries from GitHub Releases over HTTPS. Checksum verification is present for the binary itself (good), but the `install.sh` invoked to perform the download is itself fetched without integrity verification (see finding #1/#2). Also downloads `terminal-notifier` zip from a third-party repo (`julienXX/terminal-notifier`) with no checksum (line 1118). |
| 5 | MEDIUM | bin/hook-wrapper.sh | 141 | silent-background-install | On every hook invocation, if the binary version differs from plugin.json, `run_install --force` is called silently (`>/dev/null 2>&1 || true`). This triggers `install.sh` which in turn makes unauthenticated network requests, all without user awareness. |
| 6 | MEDIUM | bin/bootstrap.sh | 404–409, 497–500 | destructive-rm-rf | Uses `rm -rf "$CACHE_DIR"` and `rm -rf` on plugin version directories. If `CACHE_DIR` resolves incorrectly (e.g., empty string), this could delete unintended paths. A guard `[ -n "$CACHE_DIR" ] && [ "$CACHE_DIR" != "/" ]` is present for the cache dir but not consistently applied everywhere. |
| 7 | LOW | commands/init.md | 32 | unpinned-branch-url | `INSTALL_SCRIPT_URL` references the `main` branch rather than a pinned commit SHA or release tag. Supply-chain attacks or accidental breakage of `main` affect all users on next run. |
| 8 | LOW | bin/bootstrap.sh | 21 | unpinned-branch-url | `INSTALL_SCRIPT_URL` also defaults to `main` branch. Same risk as finding #7. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude-plugin/plugin.json | `commands/sounds.md` is absent from the `commands` array | The `/claude-notifications-go:sounds` command is never registered; users cannot invoke it |
| 2 | .claude-plugin/plugin.json | `commands/notifications-sounds.md` is absent from the `commands` array | The alias `notifications-sounds` is similarly unreachable |
| 3 | commands/init.md | Missing `name` field in YAML frontmatter | Command may display incorrectly or fail registration depending on Claude Code version |
| 4 | commands/notifications-init.md | Missing `name` field in YAML frontmatter | Same as above |
| 5 | commands/notifications-settings.md | Missing `name` field in YAML frontmatter | Same as above |
| 6 | commands/notifications-sounds.md | Missing `name` field in YAML frontmatter | Same as above |
| 7 | commands/settings.md | Missing `name` field in YAML frontmatter | Same as above |
| 8 | commands/sounds.md | Missing `name` field in YAML frontmatter | Same as above |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | commands/settings.md | `sound_name` from user input inserted into shell file path | Validate `sound_name` against an allowlist of known sound names (e.g., `[a-zA-Z0-9_-]+`) before constructing any path; reject or escape values that contain `/`, `..`, or shell metacharacters |
| 2 | commands/init.md | `INSTALL_SCRIPT_URL` points to `main` branch | Pin the URL to the specific release tag matching `plugin.json` version, e.g. `https://raw.githubusercontent.com/777genius/claude-notifications-go/v${VERSION}/bin/install.sh` |
| 3 | bin/bootstrap.sh | Same unpinned `INSTALL_SCRIPT_URL` default | Same fix: derive the download URL from the marketplace's pinned release tag |
| 4 | bin/install.sh | `terminal-notifier` downloaded from third-party repo without checksum | Add expected SHA-256 for the `terminal-notifier-2.0.0.zip` and verify before extraction |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/init.md | No output format specification | -10 |
| 2 | commands/init.md | No empty-input handling section | -10 |
| 3 | commands/notifications-init.md | `Bash` listed in allowed-tools but command body only tells user to run a different command; Bash is never invoked | -3 |
| 4 | commands/notifications-init.md | No output format specification | -10 |
| 5 | commands/notifications-settings.md | `Bash`, `AskUserQuestion`, `Write`, `Read` all declared but command body is a redirect stub; none are invoked | -12 (4 × -3) |
| 6 | commands/notifications-settings.md | No output format specification | -10 |
| 7 | commands/notifications-sounds.md | `Bash` declared but command body is a redirect stub | -3 |
| 8 | commands/notifications-sounds.md | No output format specification | -10 |
| 9 | commands/settings.md | No empty-input handling (what should Claude do if invoked with no context or in an unsupported environment?) | -10 |
| 10 | commands/settings.md | Output format described only informally in Step 8 prose; no formal `## Output Format` section | -5 |
| 11 | commands/sounds.md | No output format specification | -10 |
| 12 | commands/sounds.md | No empty-input handling | -10 |
| 13 | All 6 command files | Alias commands (`notifications-*`) duplicate functionality without adding value; the canonical short-name commands should be the only registered ones, with the `notifications-` prefix variants removed entirely | informational |

## Cross-Component
**Orphaned commands**: `commands/sounds.md` and `commands/notifications-sounds.md` exist on disk and are referenced by each other (`notifications-sounds.md` points users to `sounds.md`) but neither file appears in `.claude-plugin/plugin.json`'s `commands` array. Neither command is accessible to end users after installation. This is a clear registration gap.

**Alias pattern inconsistency**: Three `notifications-*` aliases are registered in `plugin.json` (`notifications-init`, `notifications-settings`) while `notifications-sounds` is absent. This makes the alias naming pattern incomplete — users who know the old `notifications-` prefix will find settings but not sounds.

**Allowed-tools vs. body mismatch**: The three alias stubs (`notifications-init.md`, `notifications-settings.md`, `notifications-sounds.md`) declare tools (`Bash`, `AskUserQuestion`, `Write`, `Read`) that they never invoke. The `settings.md` command correctly declares `Bash, AskUserQuestion, Write, Read` and uses all of them. The alias stubs should declare `allowed-tools: []` or omit the field.

**Hook-to-binary coupling**: `hooks/hooks.json` invokes `${CLAUDE_PLUGIN_ROOT}/bin/hook-wrapper.sh` for all five hook events (PreToolUse, Notification, Stop, SubagentStop, TeammateIdle). The wrapper silently auto-downloads and auto-updates the Go binary on every hook invocation when versions mismatch. This tight coupling means a broken GitHub release or network outage at hook-fire time will log silent errors but not surface them to the user — a debugging blind spot.

## Recommendation
**BLOCKED — do not submit PRs. File private security report.**

Findings #1 and #2 (CRITICAL) represent a `curl`-download-then-`bash`-execute pattern on the `main` branch of the repository. If the repository is compromised, renamed, or subject to a dependency-confusion attack, arbitrary code executes on every user who runs `/claude-notifications-go:init` or the bootstrap one-liner. This must be addressed privately before any public PR activity.

After the Critical findings are resolved (e.g., by pinning download URLs to release tags and/or adding script-level integrity checks), reopen the audit. The NL bugs (missing `name` fields, unregistered commands) are all safe to submit as a public PR at that point.
