# NLPM Audit: manaflow-ai/cmux
**Date**: 2026-04-29  |  **Artifacts**: 11  |  **Strategy**: single
**NL Score**: 74/100
**Security**: BLOCKED
**Bugs**: 7  |  **Quality Issues**: 10  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/release.md | command | 43 | No frontmatter + vague "relevant" |
| .claude/commands/pull.md | command | 45 | No frontmatter (name, description) |
| .claude/commands/release-local.md | command | 45 | No frontmatter (name, description) |
| .claude/commands/release-nightly.md | command | 45 | No frontmatter (name, description) |
| .claude/commands/sync-branch.md | command | 45 | No frontmatter (name, description) |
| CLAUDE.md | project-context | 98 | Vague "minimal" in socket telemetry policy |
| skills/cmux-debug-windows/SKILL.md | skill | 98 | Script section path inconsistent with examples |
| skills/cmux-browser/SKILL.md | skill | 98 | Vague "similar" in wait support note |
| skills/cmux-markdown/SKILL.md | skill | 98 | Vague "short" retry window |
| skills/release/SKILL.md | skill | 98 | Vague "concise" in PR step |
| skills/cmux/SKILL.md | skill | 99 | Clean |

**Scoring notes:** Commands each lose -25 (name) + -25 (description) + -5 (allowed-tools) = -55 from baseline. `release.md` loses an additional -2 for the vague quantifier "if relevant". Skills and CLAUDE.md lose only -2 per vague quantifier found. NL score is the simple average of all eleven artifact scores.

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 1 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Shell scripts (scripts/*.sh) | 24 |
| Python scripts (scripts/*.py) | 6 |
| JavaScript scripts (scripts/*.js) | 2 |
| Package manifests | 2 (package.json, web/package.json) |
| Hooks | 0 |
| MCP configs | 0 |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH | scripts/sparkle_generate_appcast.sh | 105 | shell-var-in-python-c | `python3 -c` block interpolates shell variables `$SIGNATURE`, `$DMG_LENGTH`, and `$generated_appcast_path` directly into Python source. Pattern matches eval-with-variables. **FALSE POSITIVE**: `$SIGNATURE` is an EdDSA base64 string (no injectable characters), `$DMG_LENGTH` is an integer from `stat -f%z`, and `$generated_appcast_path` is a controlled temp path — none can carry a Python injection payload. |
| 2 | HIGH | scripts/build-sign-upload.sh | 85 | credential-cli-arg | `SPARKLE_PRIVATE_KEY` is passed as a positional CLI argument to `swift scripts/derive_sparkle_public_key.swift "$SPARKLE_PRIVATE_KEY"`, exposing the private key in the system process list (`ps aux`) for the lifetime of the swift invocation. The key should be passed via a temp file or environment variable instead. |
| 3 | MEDIUM | scripts/sparkle_generate_appcast.sh | 29 | runtime-fetch-no-checksum | `git clone --depth 1 --branch "$SPARKLE_VERSION"` fetches and then **builds from source** the Sparkle signing toolchain (`generate_appcast`, `sign_update`) at release time. Git tags are mutable; a rewritten or hijacked Sparkle tag would silently substitute malicious build tooling into the release pipeline. |
| 4 | LOW | web/package.json | null | unpinned-semver | All npm/bun dependencies (Next.js, Effect, drizzle-orm, e2b, etc.) use `^` semver ranges, allowing minor/patch version drift on each install and enabling subtle supply-chain substitution. |
| 5 | LOW | package.json | null | unpinned-semver | Root-level `"vercel": "^50.9.5"` is an unpinned range. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/pull.md | No YAML frontmatter block — `name` and `description` fields absent | Slash command has no description for registration or agent auto-selection context |
| 2 | .claude/commands/release-local.md | No YAML frontmatter block — `name` and `description` fields absent | Slash command has no description for registration or agent auto-selection context |
| 3 | .claude/commands/release-nightly.md | No YAML frontmatter block — `name` and `description` fields absent | Slash command has no description for registration or agent auto-selection context |
| 4 | .claude/commands/release.md | No YAML frontmatter block — `name` and `description` fields absent | Slash command has no description for registration or agent auto-selection context |
| 5 | .claude/commands/sync-branch.md | No YAML frontmatter block — `name` and `description` fields absent | Slash command has no description for registration or agent auto-selection context |
| 6 | skills/cmux-debug-windows/SKILL.md | `## Script` section lists path as `scripts/debug_windows_snapshot.sh` but the workflow step and all examples use the full repo-relative path `skills/cmux-debug-windows/scripts/debug_windows_snapshot.sh` | An agent reading only the Script section will attempt to run the script from the wrong location and fail |
| 7 | Cross-component | `release.md`, `release-local.md`, and `release-nightly.md` each instruct the agent to also update `docs-site/content/docs/changelog.mdx`; `release/SKILL.md` (step 4) and `CLAUDE.md` (Release section) both explicitly state this secondary file must **not** be manually edited because `web/app/docs/changelog/page.tsx` renders directly from `CHANGELOG.md` | Agent following any release command will edit a file that the canonical skill and CLAUDE.md say is auto-generated, producing unnecessary diffs or stale content |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/sparkle_generate_appcast.sh | Sparkle build toolchain cloned from GitHub at release time with no digest verification | Pin the clone to a known commit SHA (not just a tag) and verify the built binaries against pre-computed checksums before use |
| 2 | web/package.json | All dependencies use `^` semver ranges | Pin to exact versions and commit a lockfile; enforce pinning in CI |
| 3 | package.json | `vercel: "^50.9.5"` is an unpinned range | Pin to the exact version used in CI |

**Note:** Finding #2 (HIGH — `SPARKLE_PRIVATE_KEY` as CLI argument in `build-sign-upload.sh:85`) requires private disclosure to the maintainers, not a public PR.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .claude/commands/pull.md | Missing `allowed-tools` declaration | -5 |
| 2 | .claude/commands/release-local.md | Missing `allowed-tools` declaration | -5 |
| 3 | .claude/commands/release-nightly.md | Missing `allowed-tools` declaration | -5 |
| 4 | .claude/commands/release.md | Missing `allowed-tools` declaration | -5 |
| 5 | .claude/commands/sync-branch.md | Missing `allowed-tools` declaration | -5 |
| 6 | .claude/commands/release.md | Vague quantifier: "Link to issues/PRs if relevant" — "relevant" is not defined | -2 |
| 7 | skills/release/SKILL.md | Vague quantifier: "Include a concise changelog summary in the PR body" — no length bound given | -2 |
| 8 | skills/cmux-browser/SKILL.md | Vague quantifier: "cmux supports wait patterns similar to agent-browser" — "similar" gives no actionable precision | -2 |
| 9 | skills/cmux-markdown/SKILL.md | Vague quantifier: "the panel attempts automatic reconnection within its short retry window" — "short" is undefined | -2 |
| 10 | CLAUDE.md | Vague quantifier: "Schedule minimal UI/model mutation with DispatchQueue.main.async only when needed" — "minimal" is undefined | -2 |

## Cross-Component

**Changelog dual-update contradiction (high impact):** Three slash commands (`release.md`, `release-local.md`, `release-nightly.md`) instruct the agent to also update `docs-site/content/docs/changelog.mdx`. Both `release/SKILL.md` step 4 and the `## Release` section of `CLAUDE.md` explicitly contradict this, stating the secondary file must not be manually edited because the changelog page renders directly from `CHANGELOG.md`. An agent following any of the three commands will edit a file the canonical skill says is auto-generated; an agent following the skill will skip an edit the commands demand. One of these two instruction sets is outdated.

**Unverified relative reference paths in skills:** `skills/cmux/SKILL.md` and `skills/cmux-browser/SKILL.md` reference sub-documents via relative paths (`references/handles-and-identify.md`, `references/commands.md`, `references/snapshot-refs.md`, etc.). These paths were not confirmed to resolve in the audited snapshot. If the `references/` subdirectories are absent or incomplete, agents will follow dead links during complex browser or topology tasks.

**No orphaned commands or skills detected** — all five commands and all five skills have clear purpose statements and no inbound reference gaps.

## Recommendation

BLOCKED — do not submit PRs. File a private security report for finding #2 (`SPARKLE_PRIVATE_KEY` exposed in the process list via CLI argument at `scripts/build-sign-upload.sh:85`). Finding #1 is a confirmed false positive and can be closed after maintainer review. Once the high-severity finding is resolved and the security status is downgraded to REVIEW or CLEAR, the following work is ready to submit:

- **NL bug PRs (bugs 1–7):** Add YAML frontmatter (`name` + `description`) to all five commands; fix the `cmux-debug-windows` script path in the Script section; reconcile the changelog dual-update contradiction across the three release commands and `release/SKILL.md`.
- **Security fix PRs (findings 3–5):** Pin the Sparkle clone to a commit SHA with binary checksum verification; pin npm/bun dependencies to exact versions.
