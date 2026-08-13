# NLPM Audit: hamelsmu/claude-review-loop
**Date**: 2026-04-06  |  **Artifacts**: 4  |  **Strategy**: single
**NL Score**: 89/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 5  |  **Security Findings**: 4

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/review-loop.md | Command | 64 | R14 unnumbered steps + R15 empty input unhandled + R16 no output format + R01 vague language |
| commands/cancel-review.md | Command | 90 | R14 multi-step body without numbered steps |
| plugins/review-loop/.claude-plugin/plugin.json | Plugin manifest | 100 | No issues |
| hooks/hooks.json | Hook config | 100 | No issues |

**Weighted average**: (64 + 90 + 100 + 100) / 4 = 89/100

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 2 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | hooks/stop-hook.sh |
| Scripts | scripts/setup-review-loop.sh |
| MCP configs | (none) |
| Package manifests | (none) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | hooks/stop-hook.sh | 294 | SEC-env-var-injection | `REVIEW_LOOP_CODEX_FLAGS` env var is read and expanded unquoted at line 350 into a generated shell script. If the variable contains shell metacharacters (`;`, `&&`, `|`), they are baked into `.claude/review-loop-run-codex.sh` and execute when Claude runs `bash .claude/review-loop-run-codex.sh`. |
| 2 | Medium | hooks/stop-hook.sh | 222 | SEC-unpinned-runtime-install | The UX agent section of `build_review_prompt()` instructs the Codex agent to run `npm install -g agent-browser` (unpinned) if UI testing is needed. If the `agent-browser` package name is ever squatted or typosquatted, the Codex agent will install a malicious package in the target environment. |
| 3 | Low | hooks/stop-hook.sh | 1 | SEC-missing-strictmode | Script uses `trap ERR` for error handling but omits `set -u` and `set -o pipefail`. The ERR trap partially compensates but unbound variables can silently produce empty strings. |
| 4 | Low | commands/review-loop.md | null | SEC-unpinned-semver | Install instruction `npm install -g @openai/codex` has no version pin. A breaking upgrade to the Codex CLI could silently alter the review workflow. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | commands/review-loop.md | Empty `$ARGUMENTS` not validated (R15): if the user runs `/review-loop` with no task description, the inline bash creates a state file with a blank body and the loop starts silently with no task. The standalone `scripts/setup-review-loop.sh` correctly exits with an error for empty input, but the command's inline bash omits this check. | Loop activates with no task description; Claude implements nothing and the review cycle runs on an empty diff. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | hooks/stop-hook.sh | `REVIEW_LOOP_CODEX_FLAGS` expanded unquoted into generated shell script (line 294 + 350) | Validate `REVIEW_LOOP_CODEX_FLAGS` against an allowlist of known-safe codex flags (e.g. `^[a-zA-Z0-9 _=-]*$`) before baking it into the runner script; or quote the expansion and pass flags as an array element instead of relying on word-splitting. |
| 2 | hooks/stop-hook.sh | Unpinned `npm install -g agent-browser` in AI-generated prompt (line 222) | Pin to a specific version (`npm install -g agent-browser@<version>`) or remove the auto-install suggestion and document agent-browser as a manual prerequisite. |
| 3 | hooks/stop-hook.sh | Missing `set -u` and `set -o pipefail` (line 1) | Add `set -euo pipefail` at the top; the existing ERR trap already handles cleanup, so the change is low-risk. |
| 4 | commands/review-loop.md | Unpinned `npm install -g @openai/codex` install suggestion | Pin to a specific version in the install instruction. |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/review-loop.md | R14: Multi-step body with no numbered steps. The workflow has at least four sequential steps (setup → implement → stop → run Codex → address feedback) but they are described in prose paragraphs rather than a numbered list. | -10 |
| 2 | commands/review-loop.md | R15: No handling for empty `$ARGUMENTS`. The command has `argument-hint: "<task description>"` but the body never defines what happens when the user omits the argument. (Also filed as Bug #1 above.) | -10 |
| 3 | commands/review-loop.md | R16: No output format defined. The command says "you may stop" after addressing feedback but specifies no report template or completion summary structure. | -10 |
| 4 | commands/review-loop.md | R01: Three vague quantifiers: "thoroughly and completely" (line 29), "well-structured" (line 29), "well-tested" (line 29). None has measurable criteria. | -6 (3 × -2) |
| 5 | commands/cancel-review.md | R14: Multi-step body with no numbered steps. The command has four distinct steps (test for active loop → conditionally read state → remove files → report) presented in unnumbered prose. | -10 |

## Cross-Component
- **CC-orphan-component — scripts/setup-review-loop.sh**: The `commands/review-loop.md` command embeds its own setup bash inline (the large `set -e && REVIEW_ID=...` block) and never calls `scripts/setup-review-loop.sh`. The script is fully implemented with proper dependency checks and empty-input validation, but has no callers and is undocumented as a standalone utility. If the inline bash and the script drift, users of the script get different behavior than users of the command. Either delete the script or replace the inline bash with a call to it.
- `hooks/hooks.json` → `hooks/stop-hook.sh`: reference resolves correctly via `${CLAUDE_PLUGIN_ROOT}`. ✓
- `commands/cancel-review.md` removes `.claude/review-loop-run-codex.sh` and `.claude/review-loop-codex-prompt.txt`; these filenames match what `hooks/stop-hook.sh` generates. ✓
- `commands/review-loop.md` references `bash .claude/review-loop-run-codex.sh`; this file is generated by `hooks/stop-hook.sh` line 334. ✓
- Review ID format `YYYYMMDD-HHMMSS-hexhex` used consistently across command, hook, and cancel-review. ✓

## Recommendation
CLEAR — submit PRs for Bug #1 (empty input validation in review-loop.md) and Security Fixes #1–4 (Medium/Low). The plugin's core stop-hook logic is well-structured with good fail-open behavior, path-traversal validation, and jq fallbacks. The main actionable improvements are the missing input guard in the command and the orphaned setup script.
