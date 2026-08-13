# NLPM Audit: backnotprop/plannotator
**Date**: 2026-04-26  |  **Artifacts**: 23  |  **Strategy**: batched
**NL Score**: 93/100
**Security**: REVIEW
**Bugs**: 2  |  **Quality Issues**: 6  |  **Security Findings**: 12

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| apps/opencode-plugin/commands/plannotator-archive.md | command | 65 | Claude Code `!` bang syntax copied verbatim into OpenCode file — does not execute |
| apps/opencode-plugin/commands/plannotator-last.md | command | 65 | Empty body — agent receives no instructions when command is invoked |
| apps/marketing/src/content/docs/commands/annotate-last.md | documentation | 90 | Non-executable Astro docs artifact; lacks agent-instruction semantics |
| apps/marketing/src/content/docs/commands/plan-review.md | documentation | 90 | Non-executable Astro docs artifact; lacks agent-instruction semantics |
| apps/marketing/src/content/docs/commands/annotate.md | documentation | 90 | Non-executable Astro docs artifact; lacks agent-instruction semantics |
| apps/marketing/src/content/docs/commands/code-review.md | documentation | 90 | Non-executable Astro docs artifact; lacks agent-instruction semantics |
| apps/hook/hooks/hooks.json | config | 90 | EnterPlanMode/improve-context hook present here but absent from install script |
| apps/gemini/hooks/settings-snippet.json | config | 90 | Snippet-only; no validation of Gemini hook schema completeness |
| apps/opencode-plugin/commands/plannotator-annotate.md | command | 90 | Missing empty/approve/dismiss state handling compared to hook variant |
| apps/opencode-plugin/commands/plannotator-review.md | command | 90 | Missing empty/approve/dismiss state handling compared to hook variant |
| apps/hook/.claude-plugin/plugin.json | config | 95 | Plugin manifest; complete and valid |
| apps/copilot/commands/plannotator-annotate.md | command | 100 | — |
| apps/copilot/commands/plannotator-last.md | command | 100 | — |
| apps/copilot/commands/plannotator-review.md | command | 100 | — |
| apps/hook/commands/plannotator-archive.md | command | 100 | — |
| apps/hook/commands/plannotator-last.md | command | 100 | — |
| apps/hook/commands/plannotator-review.md | command | 100 | — |
| apps/hook/commands/plannotator-annotate.md | command | 100 | — |
| .agents/skills/pierre-guard/SKILL.md | skill | 100 | — |
| .agents/skills/release/SKILL.md | skill | 100 | — |
| .agents/skills/review-renovate/SKILL.md | skill | 100 | — |
| .agents/skills/update-deps/SKILL.md | skill | 100 | — |
| apps/skills/plannotator-compound/SKILL.md | skill | 100 | — |

**Weighted average**: (2×65 + 8×90 + 1×95 + 12×100) / 23 = 2145/23 = **93/100**

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 3 |
| High | 1 |
| Medium | 4 |
| Low | 4 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | apps/hook/hooks/hooks.json, apps/gemini/hooks/settings-snippet.json |
| Scripts (shell) | scripts/install.sh, apps/marketing/public/install.sh, apps/pi-extension/vendor.sh, scripts/clear-opencode-cache.sh, tests/bench-startup.sh, tests/manual/local/*.sh (14 files), tests/manual/ssh/test-ssh.sh |
| Scripts (Python) | apps/skills/plannotator-compound/scripts/extract_exit_plan_mode_outcomes.py |
| MCP configs | None |
| Package manifests | package.json (root), apps/*/package.json (7), packages/*/package.json (6) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | scripts/install.sh | 57 | SEC-curl-pipe-sh | `curl … \| bash` in usage() heredoc — **FALSE POSITIVE**: appears only in documentation text printed to stdout, never executed |
| 2 | CRITICAL | scripts/install.sh | 58 | SEC-curl-pipe-sh | Second `curl … \| bash` example in same usage() heredoc — **FALSE POSITIVE** |
| 3 | CRITICAL | scripts/install.sh | 59 | SEC-curl-pipe-sh | Third `curl … \| bash` example in same usage() heredoc — **FALSE POSITIVE** |
| 4 | HIGH | scripts/install.sh | 508–514 | SEC-node-eval | `node -e "…"` block embeds unquoted shell variables `$GEMINI_SETTINGS` and `$PLANNOTATOR_HOOK`; if $HOME contains shell metacharacters the JavaScript is malformed. Both variables are OS-controlled ($HOME) or hardcoded, so actual exploit surface is negligible, but the pattern is architecturally unsafe. |
| 5 | MEDIUM | scripts/install.sh | 169 | network-call | `curl` to GitHub API to resolve latest release tag |
| 6 | MEDIUM | scripts/install.sh | 237–239 | network-call | `curl` downloads binary and SHA256 checksum from GitHub Releases |
| 7 | MEDIUM | scripts/install.sh | 349 | runtime-package-install | `pi install npm:@plannotator/pi-extension` — installs npm package at runtime during install |
| 8 | MEDIUM | scripts/install.sh | 465–466 | network-call | `git clone` from GitHub to sparse-checkout skills assets |
| 9 | LOW | package.json | 38 | SEC-unpinned-semver | `@anthropic-ai/claude-agent-sdk: ^0.2.92` — caret range permits minor/patch bumps without explicit review |
| 10 | LOW | package.json | 39 | SEC-unpinned-semver | `@openai/codex-sdk: ^0.118.0` — caret range |
| 11 | LOW | package.json | 40 | SEC-unpinned-semver | `@opencode-ai/sdk: ^1.3.0` — caret range |
| 12 | LOW | package.json | 41 | SEC-unpinned-semver | `@pierre/diffs: ^1.1.12` — caret range; Shadow DOM internals make surprise breaks high-impact (see pierre-guard skill) |

> **Note**: `apps/marketing/public/install.sh` is byte-for-byte identical to `scripts/install.sh`; findings #1–8 apply equally to that file at the same line numbers. Not duplicated in the table to avoid noise, but the sidecar records both.

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | apps/opencode-plugin/commands/plannotator-archive.md | File is an exact copy of the hook variant: contains Claude Code–specific `!` bang command (`!``plannotator archive```) and `allowed-tools: Bash(plannotator:*)` frontmatter that OpenCode does not process. The bang command is never executed in OpenCode; the archive subcommand is never invoked. | Archive command is silently broken in OpenCode |
| 2 | apps/opencode-plugin/commands/plannotator-last.md | Body is empty after the frontmatter. Other OpenCode commands (review, annotate, archive) have a brief instruction body; this file has none. Agent receives no guidance when the command is invoked. | Agent has no instructions; behavior is undefined |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/install.sh | `node -e` block interpolates `$GEMINI_SETTINGS` unquoted (lines 508–514); path could contain characters that break the JS literal | Write the settings path to a temp file and pass it as a CLI arg, or use `printf '%s' "$GEMINI_SETTINGS"` in the node invocation to avoid unquoted expansion inside a string literal |
| 2 | package.json | `@pierre/diffs: ^1.1.12` uses a caret range; the pierre-guard skill explicitly calls out that shadow DOM selectors and grid assumptions can break silently on minor upgrades | Pin to an exact version or use `~1.1.12` (patch-only) and gate upgrades through the pierre-guard verification checklist |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | apps/opencode-plugin/commands/plannotator-review.md | Missing empty-output and approval-state handling. Hook variant says "If no changes were requested, acknowledge and continue." OpenCode variant only says "wait for the user's feedback." Agent does not know what to do on empty output or approve. | −10 |
| 2 | apps/opencode-plugin/commands/plannotator-annotate.md | Same issue: no empty/approve/dismiss branching. Hook and copilot variants enumerate 3 explicit cases. | −10 |
| 3 | apps/marketing/src/content/docs/commands/*.md (4 files) | Astro content-collection docs pages included in NL artifact scan. They have valid title/description frontmatter but carry no agent-instruction semantics. Scored as documentation type; no penalty for missing allowed-tools or model. | −10 (per-file class deduction) |
| 4 | apps/hook/hooks/hooks.json | PreToolUse/EnterPlanMode hook (`plannotator improve-context`, timeout 5s) is present here but not installed by `scripts/install.sh`. Users who install via the marketplace get this hook; users who install via the install script do not. | informational |
| 5 | apps/opencode-plugin/commands/* | All four OpenCode commands are missing `allowed-tools`. This is correct for the OpenCode runtime (which does not use this field), but creates a visible parity gap with hook and copilot variants. No functional impact. | informational |
| 6 | apps/gemini/hooks/settings-snippet.json | Snippet-only config; does not include the `experimental.plan: true` block present in the auto-generated Gemini settings written by install.sh. A user who applies this snippet manually will miss the Gemini plan-mode enablement. | informational |

## Cross-Component
**EnterPlanMode hook gap**: `apps/hook/hooks/hooks.json` registers a `PreToolUse/EnterPlanMode` hook that calls `plannotator improve-context` (timeout: 5s). Neither `scripts/install.sh` nor the marketing docs mention this hook. The install script writes only the `PermissionRequest/ExitPlanMode` hook when updating an existing installation. Users who receive the plugin via marketplace get the EnterPlanMode hook; users who update via install.sh lose it on next reinstall.

**Harness tool-name parity**: Copilot commands declare `allowed-tools: shell(plannotator:*)` (lowercase `shell`) while hook commands declare `allowed-tools: Bash(plannotator:*)`. This is correct — the copilot harness exposes a `shell` tool, Claude Code exposes `Bash` — but any cross-harness copy must adjust this field. Bug #1 (archive OpenCode) demonstrates what happens when it is not.

**Version cross-check**: `apps/hook/.claude-plugin/plugin.json` declares version `0.19.1`. The release skill lists 7 files that must be bumped atomically; this audit cannot verify all 7 without reading the remaining manifests, but no stale version string was detected in the audited files.

**No broken relative-path references detected** in any audited skill or command file. All cross-references (e.g., `references/` paths in compound skill, `assets/report-template.html`) are intra-repo and consistent with the repo structure described in CLAUDE.md.

## Recommendation
The three Critical pre-scan matches are confirmed false positives — all three `curl … | bash` patterns appear exclusively inside a `cat <<'USAGE'` heredoc that is only printed to stdout as documentation text; they are never executed. The one confirmed HIGH finding (unquoted shell variables in a `node -e` block) has negligible actual exploit surface because both variables are OS-controlled or hardcoded, but the pattern is architecturally worth fixing.

**REVIEW** — submit NL fix PRs for bugs #1 and #2; flag the `node -e` interpolation (security finding #4) in a repo issue rather than a public PR.
