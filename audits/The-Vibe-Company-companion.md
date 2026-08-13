# NLPM Audit: The-Vibe-Company/companion
**Date**: 2026-04-26  |  **Artifacts**: 19  |  **Strategy**: single
**NL Score**: 91/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 22  |  **Security Findings**: 7

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .agents/skills/adapt/SKILL.md | skill | 86 | Missing output format; 2 vague quantifiers ("where appropriate") |
| .agents/skills/animate/SKILL.md | skill | 88 | Missing output format; malformed MANDATORY PREPARATION template |
| .agents/skills/bolder/SKILL.md | skill | 88 | Missing output format; malformed MANDATORY PREPARATION template |
| .agents/skills/colorize/SKILL.md | skill | 88 | Missing output format; malformed MANDATORY PREPARATION template |
| .agents/skills/delight/SKILL.md | skill | 88 | Missing output format; malformed MANDATORY PREPARATION template |
| .agents/skills/distill/SKILL.md | skill | 88 | Missing output format; malformed MANDATORY PREPARATION template |
| .agents/skills/quieter/SKILL.md | skill | 88 | Missing output format; malformed MANDATORY PREPARATION template |
| .agents/skills/clarify/SKILL.md | skill | 90 | Missing output format |
| .agents/skills/extract/SKILL.md | skill | 90 | Missing output format |
| .agents/skills/frontend-design/SKILL.md | skill | 90 | Missing output format |
| .agents/skills/harden/SKILL.md | skill | 90 | Missing output format |
| .agents/skills/normalize/SKILL.md | skill | 90 | Missing output format |
| .agents/skills/onboard/SKILL.md | skill | 90 | Missing output format |
| .agents/skills/optimize/SKILL.md | skill | 90 | Missing output format |
| CLAUDE.md | config | 95 | Soft reference to non-standard `agent-browser` CLI |
| .agents/skills/polish/SKILL.md | skill | 98 | Borderline vague word ("appropriate motion") |
| .agents/skills/audit/SKILL.md | skill | 100 | None |
| .agents/skills/critique/SKILL.md | skill | 100 | None |
| .agents/skills/teach-impeccable/SKILL.md | skill | 100 | None |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 6 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts (sh) | scripts/sync-codex-protocol.sh, scripts/landing-start.sh, scripts/check-claude-streaming.sh, scripts/dev-start.sh, scripts/build-push-companion-server.sh |
| Scripts (ts/js) | scripts/audit-recordings.ts |
| Package manifests | package.json, web/package.json |
| Hooks | none |
| MCP configs | none |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | scripts/check-claude-streaming.sh | 14 | SEC-path-traversal | CLI arg `$session_id` used unvalidated in glob path — `"$recordings_dir"/"${session_id}"*` — a crafted value containing `../` could reference files outside the recordings directory |
| 2 | Low | scripts/build-push-companion-server.sh | 31 | SEC-credential-env | DOCKERHUB_TOKEN sourced from env file and piped directly to `docker login`; credentials visible in process environment |
| 3 | Low | scripts/sync-codex-protocol.sh | 9 | SEC-network-call | `git clone --depth 1 https://github.com/openai/codex.git` fetches code from an external URL into a temp dir at runtime; no hash pinning |
| 4 | Low | scripts/landing-start.sh | 41 | SEC-network-call | `curl` health check to `http://localhost:$port` — false positive: localhost-only, no data exfiltration possible |
| 5 | Low | scripts/dev-start.sh | 44 | SEC-network-call | `curl` health check to `http://localhost:$port` — false positive: localhost-only, no data exfiltration possible |
| 6 | Low | package.json | 16 | SEC-unpinned-semver | Dependency `"the-companion": "^0.2.2"` uses caret range; patch/minor updates apply automatically |
| 7 | Low | package.json | 19 | SEC-unpinned-semver | DevDependency `"husky": "^9.1.7"` uses caret range |

## Bugs (PR-worthy)
No NL bugs found. All 18 skill files carry valid `name` and `description` frontmatter. All cross-referenced skills resolve. No broken relative paths detected.

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/check-claude-streaming.sh | Unvalidated `$session_id` used in glob path (line 14) | Validate that `$session_id` matches `[a-zA-Z0-9_-]+` before interpolation; e.g. `[[ "$session_id" =~ ^[a-zA-Z0-9_-]+$ ]] \|\| { echo "invalid session id"; exit 1; }` |
| 2 | scripts/build-push-companion-server.sh | DOCKERHUB_TOKEN piped to docker login (line 31) | Low risk — standard pattern; consider using a dedicated CI secret store rather than a plain `.env` file for the token |
| 3 | scripts/sync-codex-protocol.sh | External `git clone` with no commit hash pinning (line 9) | Pin to a specific commit SHA instead of cloning HEAD; verify SHA before use |
| 4 | package.json | Unpinned semver for `the-companion` and `husky` (lines 16, 19) | Use exact versions or lock via bun.lock/package-lock.json; consider `--frozen-lockfile` in CI |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | .agents/skills/adapt/SKILL.md | Missing output format — skill does not specify what it should produce for the invoking agent (R41) | -10 |
| 2 | .agents/skills/animate/SKILL.md | Missing output format (R41) | -10 |
| 3 | .agents/skills/bolder/SKILL.md | Missing output format (R41) | -10 |
| 4 | .agents/skills/clarify/SKILL.md | Missing output format (R41) | -10 |
| 5 | .agents/skills/colorize/SKILL.md | Missing output format (R41) | -10 |
| 6 | .agents/skills/delight/SKILL.md | Missing output format (R41) | -10 |
| 7 | .agents/skills/distill/SKILL.md | Missing output format (R41) | -10 |
| 8 | .agents/skills/extract/SKILL.md | Missing output format (R41) | -10 |
| 9 | .agents/skills/frontend-design/SKILL.md | Missing output format (R41) | -10 |
| 10 | .agents/skills/harden/SKILL.md | Missing output format (R41) | -10 |
| 11 | .agents/skills/normalize/SKILL.md | Missing output format (R41) | -10 |
| 12 | .agents/skills/onboard/SKILL.md | Missing output format (R41) | -10 |
| 13 | .agents/skills/optimize/SKILL.md | Missing output format (R41) | -10 |
| 14 | .agents/skills/quieter/SKILL.md | Missing output format (R41) | -10 |
| 15 | .agents/skills/adapt/SKILL.md | Vague quantifier "where appropriate" appears twice (lines 54, 83); replace with concrete criteria (R01) | -4 |
| 16 | .agents/skills/polish/SKILL.md | Borderline vague: "Appropriate motion" (line 94) without defining what makes motion appropriate (R01) | -2 |
| 17 | .agents/skills/animate/SKILL.md | MANDATORY PREPARATION block has copy-paste error: "MUST STOP and STOP" redundancy and mid-sentence period ("to clarify. whether you got it right") on line 21 (R02) | -2 |
| 18 | .agents/skills/bolder/SKILL.md | Same MANDATORY PREPARATION template error as animate, line 21 (R02) | -2 |
| 19 | .agents/skills/colorize/SKILL.md | Same MANDATORY PREPARATION template error, line 21 (R02) | -2 |
| 20 | .agents/skills/delight/SKILL.md | Same MANDATORY PREPARATION template error, line 21 (R02) | -2 |
| 21 | .agents/skills/distill/SKILL.md | Same MANDATORY PREPARATION template error, line 21 (R02) | -2 |
| 22 | .agents/skills/quieter/SKILL.md | Same MANDATORY PREPARATION template error, line 21 (R02) | -2 |

## Cross-Component
All inter-skill references resolve cleanly. The six skills referencing the `frontend-design` skill (animate, bolder, colorize, delight, distill, quieter) point to a real `.agents/skills/frontend-design/SKILL.md`. The audit and critique skills recommend slash-commands (`/normalize`, `/optimize`, etc.) that each correspond to an existing SKILL.md. The `frontend-design` skill's seven `reference/*.md` sub-documents all exist on disk.

**Observation**: Seven skills (animate, bolder, colorize, delight, distill, quieter, teach-impeccable) instruct the agent to "call the AskUserQuestionTool." This tool is not part of the standard Claude Code toolkit. If these skills are invoked via Claude Code, the instruction will silently fail or be ignored. Consider replacing with a standard clarifying prompt pattern or documenting a custom tool registration requirement.

**Observation**: `CLAUDE.md` references `agent-browser` as the required CLI for browser exploration ("Always use `agent-browser` CLI command"). This is not a standard Claude Code tool and is not defined in the repository. If this is a custom installation requirement, it should be documented in the repo's setup instructions.

## Recommendation
CLEAR — submit PRs for medium/low security fixes. No NL bugs found; quality issues are informational. The template error in six MANDATORY PREPARATION blocks (findings 17–22) is the highest-leverage single fix: one template correction propagates across six skills.
