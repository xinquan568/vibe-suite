# NLPM Audit: santifer/career-ops
**Date**: 2026-04-06  |  **Artifacts**: 15  |  **Strategy**: single
**NL Score**: 91/100
**Security**: BLOCKED
**Bugs**: 0  |  **Quality Issues**: 15  |  **Security Findings**: 7

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .opencode/commands/career-ops-apply.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-batch.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-compare.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-contact.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-deep.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-evaluate.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-pdf.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-pipeline.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-project.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-scan.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-tracker.md | command | 90 | Missing output format |
| .opencode/commands/career-ops-training.md | command | 90 | Missing output format |
| .opencode/commands/career-ops.md | command | 90 | Missing output format |
| .claude/skills/career-ops/SKILL.md | skill | 95 | No example invocations showing expected mode output |
| CLAUDE.md | documentation | 96 | Vague quantifier "a few details" (×2) |

**Weighted average: 91/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 3 |
| Low | 3 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Shell scripts | batch/batch-runner.sh |
| MCP configs | 0 |
| Package manifests | package.json |
| Node scripts (root) | update-system.mjs, scan.mjs, generate-pdf.mjs, merge-tracker.mjs, verify-pipeline.mjs, dedup-tracker.mjs, normalize-statuses.mjs, analyze-patterns.mjs, followup-cadence.mjs, check-liveness.mjs, liveness-core.mjs, cv-sync-check.mjs, doctor.mjs, test-all.mjs |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | update-system.mjs | 244 | execSync + postinstall | `execSync('npm install --silent')` runs via shell and executes any postinstall scripts from newly added dependencies. During an auto-update that just fetched code from the upstream GitHub repo, a compromised package in the updated package.json could run arbitrary code on the user's machine via npm lifecycle scripts. |
| 2 | Medium | batch/batch-runner.sh | 356 | --dangerously-skip-permissions | `claude -p --dangerously-skip-permissions` processes external job URLs with no tool permission gates. A malicious job posting containing prompt injection instructions could trigger arbitrary file writes, command execution, or data exfiltration through Claude's tools with no human confirmation required. |
| 3 | Medium | batch/batch-runner.sh | 345–351 | sed metacharacter injection | URL content is substituted into `batch-prompt.md` via `sed -e "s|{{URL}}|${esc_url}|g"`. Escaping only handles `\` and `|` (lines 338–339); the `&` character in a URL expands as a sed backreference to the matched string, silently corrupting the resolved prompt. A URL like `https://example.com/jobs?ref=foo&bar` would produce malformed output. |
| 4 | Medium | update-system.mjs | 205 | remote code fetch + apply | `git fetch CANONICAL_REPO main` followed by `git checkout FETCH_HEAD -- [system paths]` overwrites `.claude/skills/`, `CLAUDE.md`, and all `modes/` files with content from `https://github.com/santifer/career-ops.git`. If the upstream repo is compromised (account hijack, malicious PR merge), all users receive tainted instructions on their next confirmed update. |
| 5 | Low | package.json | 34 | unpinned dependency | `"js-yaml": "^4.1.1"` — semver range allows silent minor/patch upgrades. |
| 6 | Low | package.json | 35 | unpinned dependency | `"playwright": "^1.58.1"` — large supply chain; semver range allows automatic Chromium runtime upgrades. |
| 7 | Low | scan.mjs | 115 | network calls from config | `fetchJson(url)` contacts Greenhouse/Ashby/Lever API endpoints derived from user-controlled `portals.yml`. Malicious or misconfigured portals.yml entries could direct the scanner to arbitrary URLs. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| — | — | No registration-breaking bugs found. | — |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | batch/batch-runner.sh | `&` not escaped in sed URL substitution (finding #3) | Add `esc_url="${esc_url//&/\\&}"` after the existing `esc_url` escaping block (lines 338–339) before passing to sed. |
| 2 | package.json | Unpinned `js-yaml` and `playwright` (findings #5–6) | Pin to exact versions: `"js-yaml": "4.1.1"`, `"playwright": "1.58.1"`. Run `npm install --save-exact` and commit the updated lockfile. |
| 3 | scan.mjs | Unvalidated URLs from portals.yml (finding #7) | Validate that each URL in portals.yml matches expected job portal hostnames (greenhouse.io, ashbyhq.com, lever.co) before fetching. |

> **Note:** Findings #1 (High) and #2 and #4 (Medium - --dangerously-skip-permissions, remote code fetch) require private disclosure, NOT public PRs. Contact the maintainer via the security email listed in SECURITY.md before any public discussion.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .opencode/commands/career-ops-apply.md | Missing output format: no description of what the command produces | −10 |
| 2 | .opencode/commands/career-ops-batch.md | Missing output format | −10 |
| 3 | .opencode/commands/career-ops-compare.md | Missing output format | −10 |
| 4 | .opencode/commands/career-ops-contact.md | Missing output format | −10 |
| 5 | .opencode/commands/career-ops-deep.md | Missing output format | −10 |
| 6 | .opencode/commands/career-ops-evaluate.md | Missing output format | −10 |
| 7 | .opencode/commands/career-ops-pdf.md | Missing output format | −10 |
| 8 | .opencode/commands/career-ops-pipeline.md | Missing output format | −10 |
| 9 | .opencode/commands/career-ops-project.md | Missing output format | −10 |
| 10 | .opencode/commands/career-ops-scan.md | Missing output format | −10 |
| 11 | .opencode/commands/career-ops-tracker.md | Missing output format | −10 |
| 12 | .opencode/commands/career-ops-training.md | Missing output format | −10 |
| 13 | .opencode/commands/career-ops.md | Missing output format | −10 |
| 14 | .claude/skills/career-ops/SKILL.md | No example invocations or sample output per mode; the routing table is clear but there is no illustration of what each dispatched mode produces | −5 |
| 15 | CLAUDE.md | Vague quantifier "a few details" appears in the onboarding dialog template (lines 119, 128) | −4 |

**Notes on OpenCode commands:** All 13 `.opencode/commands/` files are intentional thin shims that delegate entirely to the career-ops skill. The missing output format is by design, but documenting the expected output (even as a one-liner: "Produces an A–F evaluation report in `reports/`") would help users and tooling understand what each command yields. `name` frontmatter is omitted across all OpenCode commands; this is valid since OpenCode infers the command name from the filename — no penalty applied.

## Cross-Component
- **SKILL.md ↔ OpenCode commands**: All 13 commands correctly invoke `skill({ name: "career-ops" })`, which maps to `.claude/skills/career-ops/SKILL.md`. Reference is valid and consistent.
- **CLAUDE.md OpenCode table ↔ .opencode/commands/**: The 13 commands listed in CLAUDE.md lines 73–89 all have corresponding `.opencode/commands/*.md` files. No missing files.
- **Patterns and followup modes**: SKILL.md routing table (lines 61–62) lists `patterns` and `followup` modes that do not have dedicated OpenCode command wrappers. These modes are accessible via `/career-ops patterns` and `/career-ops followup` on Claude Code but have no equivalent `/career-ops-patterns` or `/career-ops-followup` commands in `.opencode/commands/`. This is a minor gap — not a broken reference, but an incomplete surface parity between Claude Code and OpenCode.
- **modes/*.md references**: SKILL.md and CLAUDE.md both reference `modes/_shared.md`, `modes/oferta.md`, `modes/pdf.md`, etc. These files are outside the audit scope but are critical dependencies. If they are absent, all command modes silently fail. No way to verify without reading those files; flagged for awareness.
- **update-system.mjs SYSTEM_PATHS**: `.claude/skills/` is listed as a system-layer path (auto-updatable). This means the auto-updater can overwrite the audited SKILL.md without user review of the diff. Combined with the remote code fetch risk (finding #4), this is architecturally significant.
- **No contradictions** found between SKILL.md mode routing table and CLAUDE.md Skill Modes table.

## Recommendation
**BLOCKED — do not submit PRs. File private security report.**

Finding #1 (High) is a supply chain risk in the auto-update mechanism: `execSync('npm install --silent')` after fetching remote code can execute malicious postinstall scripts. Findings #2 and #4 (Medium) amplify the attack surface via `--dangerously-skip-permissions` in batch mode and remote code overwrite of the Claude skill files.

Contact the maintainer at the security email listed in `SECURITY.md` (private vulnerability reporting) before any public discussion or PR submission. After the High finding is remediated, the NL quality PRs (output format documentation on OpenCode commands, example invocations in SKILL.md) and Low/Medium security fixes (sed escaping, pinned dependencies, URL allowlist in scanner) can be submitted publicly.

**NL quality**: 91/100 — strong, well-structured system. The core SKILL.md and CLAUDE.md are exemplary; the OpenCode shims are functional but bare. No registration-breaking bugs.
