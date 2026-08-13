# NLPM Audit: JuliusBrussee/caveman
**Date**: 2026-04-17  |  **Artifacts**: 14  |  **Strategy**: single
**NL Score**: 92/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 6  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| caveman-compress/SKILL.md | skill | 85 | Process step uses hardcoded relative `cd caveman-compress`; fails if CWD ≠ repo root |
| plugins/caveman/skills/compress/SKILL.md | skill | 88 | Placeholder `<directory_containing_this_SKILL.md>` requires model inference |
| skills/compress/SKILL.md | skill | 88 | Identical to plugins copy; name "compress" inconsistent with caveman-compress canonical |
| hooks/package.json | config | 90 | Infrastructure marker, not NL artifact; no name/description (appropriate for type) |
| CLAUDE.md | project-doc | 90 | No frontmatter (correct for type); comprehensive but no canonical artifact type header |
| skills/caveman-help/SKILL.md | skill | 90 | External URL reference without fallback; one-shot card has no output format spec |
| .claude-plugin/plugin.json | config | 92 | Config manifest; name+description present; no NL artifact penalties applicable |
| .cursor/skills/caveman/SKILL.md | skill | 95 | Auto-synced copy; content excellent |
| .windsurf/skills/caveman/SKILL.md | skill | 95 | Auto-synced copy; content excellent |
| caveman/SKILL.md | skill | 95 | Auto-synced copy; content excellent |
| plugins/caveman/skills/caveman/SKILL.md | skill | 95 | Auto-synced copy; content excellent |
| skills/caveman-commit/SKILL.md | skill | 95 | Well-structured; two-tier examples; clear boundaries |
| skills/caveman-review/SKILL.md | skill | 95 | Good ❌/✅ examples; severity prefix system clear |
| skills/caveman/SKILL.md | skill | 95 | Source of truth; rich multi-level examples; auto-clarity rule well-defined |

**Weighted average**: (85+88+88+90+90+90+92+95×7) / 14 = 1288 / 14 = **92/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks (JS) | hooks/caveman-activate.js, hooks/caveman-mode-tracker.js, hooks/caveman-config.js |
| Scripts (sh) | hooks/caveman-statusline.sh, hooks/install.sh, hooks/uninstall.sh |
| Scripts (ps1) | hooks/install.ps1, hooks/uninstall.ps1, hooks/caveman-statusline.ps1 |
| MCP configs | None |
| Package manifests | hooks/package.json (CJS marker only, no dependencies) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | hooks/install.sh | 112 | Network fetch + file write | `curl -fsSL "$REPO_URL/$hook" -o "$HOOKS_DIR/$hook"` downloads JS hook files to `~/.claude/hooks/` without SHA-256 or GPG integrity verification. Supply chain risk: a compromise of the GitHub repo's `main` branch silently changes what future users install. |
| 2 | Medium | hooks/install.sh | 5 | Curl-pipe-to-bash documented | Comment documents `bash <(curl -s https://...)` installation as a usage option with no integrity-check warning. Users who follow this pattern execute remote shell code without verification. |
| 3 | Medium | hooks/caveman-config.js | 41 | Environment variable access | Reads `CAVEMAN_DEFAULT_MODE` env var and selects execution mode from it. Mode is validated against a VALID_MODES whitelist before use, making injection benign; flagged for env-var attack surface. |
| 4 | Low | hooks/install.sh | 38 | Unpinned dependency | `REPO_URL` pins to `main` branch (`/JuliusBrussee/caveman/main/hooks`), not a tagged release. Any push to main changes hooks silently fetched by future installs. |
| 5 | Low | hooks/uninstall.sh | 5 | Curl-pipe-to-bash documented | Same curl-pipe-to-bash pattern documented without integrity warning as usage option. |

**Notes on mitigations found**: The hook files demonstrate strong security hygiene beyond most OSS plugins — `safeWriteFlag` uses O_NOFOLLOW, atomic temp+rename, 0600 permissions, and symlink checks at both file and parent directory levels. `readFlag` enforces a 64-byte size cap and VALID_MODES whitelist before injecting any content into model context. `caveman-statusline.sh` strips non-`[a-z0-9-]` characters from flag content before terminal output, blocking escape injection. No eval, no subprocess with unsanitized user input, no credential exfiltration.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | caveman-compress/SKILL.md:26 | Process step uses `cd caveman-compress && python3 -m scripts <absolute_filepath>` — hardcoded relative directory name. Fails if the agent's working directory is not the repo root when the skill is invoked. The sibling file `plugins/caveman/skills/compress/SKILL.md` uses the more robust `cd <directory_containing_this_SKILL.md>` pattern. | Skill fails silently or errors for any user whose CWD differs from repo root at invocation time. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | hooks/install.sh | Curl download of JS hooks has no integrity check (line 112) | Add sha256sum verification step: publish a `hooks/checksums.sha256` file in the repo and verify each downloaded file with `sha256sum --check` before writing to `~/.claude/hooks/`. |
| 2 | hooks/install.sh, hooks/uninstall.sh | Curl-pipe-to-bash pattern in comments (lines 5) lacks any integrity warning | Add a note alongside the one-liner: `# For added safety, download first and inspect: curl -o install.sh ...; less install.sh; bash install.sh`. Or document a `--verify` flag. |
| 3 | hooks/install.sh | REPO_URL pins to `main` branch (line 38) | Change to a tagged release URL (`/refs/tags/v<VERSION>/hooks`) and automate the tag bump in CI so standalone installs always get verified, versioned code. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | caveman-compress/SKILL.md | Process command not in a fenced code block — appears as plain text, which can cause formatting ambiguity in some renderers | -5 |
| 2 | plugins/caveman/skills/compress/SKILL.md, skills/compress/SKILL.md | `name: compress` diverges from canonical `name: caveman-compress` in the source-of-truth file. For skill loaders that deduplicate by name, this creates two distinct registrations with identical behavior. | -5 each |
| 3 | skills/caveman-help/SKILL.md | External URL `https://github.com/JuliusBrussee/caveman` at line 59 — no fallback if link is unavailable. One-shot reference card should be self-contained. | -5 |
| 4 | 5× auto-synced caveman SKILL.md | Five identical copies of `skills/caveman/SKILL.md` distributed across `.cursor/`, `.windsurf/`, `caveman/`, `plugins/caveman/skills/caveman/`, `skills/caveman/`. CI sync is documented and correct; minor drift risk if CI misses an edge case. | informational |
| 5 | plugins/caveman/skills/compress/SKILL.md | Process step placeholder `<directory_containing_this_SKILL.md>` is not resolved — the model must infer the path at runtime. Could silently fail on agents that don't infer file paths from context. | -3 |

## Cross-Component
- **Sync chain intact**: `CLAUDE.md` correctly documents CI sync from `skills/caveman/SKILL.md` to all five copies. Checked at audit time — content matches across `.cursor/skills/caveman/SKILL.md`, `.windsurf/skills/caveman/SKILL.md`, `caveman/SKILL.md`, `plugins/caveman/skills/caveman/SKILL.md`, `skills/caveman/SKILL.md`. No drift.
- **Hook references valid**: `plugin.json` declares hooks for `hooks/caveman-activate.js` and `hooks/caveman-mode-tracker.js` — both files exist and are correctly implemented.
- **Script dependency unverified**: `caveman-compress/SKILL.md` references `caveman-compress/scripts/__main__.py`. Those Python scripts were not in scope for this audit (33 scripts detected in pre-scan). If the scripts directory is present, the skill works; if absent, it silently fails step 2 with a Python `No module named scripts` error. Worth a reference check.
- **Name split for compress**: The compress skill ships as `name: caveman-compress` in the source (`caveman-compress/SKILL.md`) but as `name: compress` in the plugin distribution path (`plugins/caveman/skills/compress/SKILL.md`) and standalone path (`skills/compress/SKILL.md`). This appears intentional (shorter name for plugin context) but is undocumented in `CLAUDE.md` — a future editor could inadvertently normalize them.
- **No orphaned references found**: All hooks, skill files, and config references cross-check correctly.

## Recommendation
CLEAR — submit PRs for the one bug (caveman-compress/SKILL.md process step) and Medium/Low security fixes (integrity checks for curl downloads, REPO_URL version pinning). No private disclosure needed; all findings are about installation methodology, not hidden backdoors. The hook security posture (O_NOFOLLOW, symlink guards, whitelist validation, ANSI-stripping in statusline) is notably above average for a plugin of this type.
