# NLPM Audit: ooiyeefei/ccc
**Date**: 2026-04-06  |  **Artifacts**: 27  |  **Strategy**: batched
**NL Score**: 96/100
**Security**: CLEAR
**Bugs**: 5  |  **Quality Issues**: 14  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/deckling/commands/deckling.md | command | 65 | Missing allowed-tools; no numbered steps, output format, or empty-input handling; broken skill reference |
| commands/streak-switch.md | command | 85 | Missing allowed-tools; no empty-input handling when argument omitted |
| plugins/product-management/commands/prd.md | command | 90 | No empty-input handling when $ARGUMENTS is empty |
| commands/streak-list.md | command | 95 | Missing allowed-tools |
| commands/streak.md | command | 95 | Missing allowed-tools |
| commands/streak-stats.md | command | 95 | Missing allowed-tools |
| commands/streak-insights.md | command | 95 | Missing allowed-tools |
| commands/streak-new.md | command | 95 | Missing allowed-tools |
| plugins/product-management/hooks/hooks.json | hook | 95 | 10s timeout may be tight for filesystem + JSON read |
| plugins/product-management/.claude-plugin/plugin.json | config | 95 | Version 0.1.0 does not match SKILL.md version 0.2.0 |
| plugins/mvp-launch/skills/mvp-launch/SKILL.md | skill | 96 | Vague: "appropriate" used twice without concrete spec |
| plugins/product-management/agents/research-agent.md | agent | 98 | Vague: "relevant" in quality standards section |
| plugins/mvp-launch/agents/mvp-gap-analyst.md | agent | 100 | — |
| plugins/product-management/agents/gap-analyst.md | agent | 100 | — |
| plugins/product-management/agents/prd-generator.md | agent | 100 | — |
| plugins/mvp-launch/commands/launch-check.md | command | 100 | — |
| plugins/product-management/commands/gaps.md | command | 100 | — |
| plugins/product-management/commands/landscape.md | command | 100 | — |
| plugins/product-management/commands/analyze.md | command | 100 | — |
| plugins/product-management/commands/file.md | command | 100 | — |
| plugins/product-management/commands/sync.md | command | 100 | — |
| plugins/mvp-launch/.claude-plugin/plugin.json | config | 100 | — |
| plugins/product-management/skills/product-management/SKILL.md | skill | 100 | — |
| skills/excalidraw/SKILL.md | skill | 100 | — |
| skills/landing-page-gtm/SKILL.md | skill | 100 | — |
| skills/streak/SKILL.md | skill | 100 | — |
| skills/uat-testing/SKILL.md | skill | 100 | — |

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
| Hooks | plugins/product-management/hooks/hooks.json |
| Scripts | plugins/deckling/scripts/deckling_worker.py, skills/streak/tools/streak-bot.py, skills/streak/tools/streak-notify.py |
| MCP configs | none |
| Package manifests | plugins/deckling/requirements.txt, skills/streak/tools/requirements.txt |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | plugins/deckling/scripts/deckling_worker.py | 135 | network-call | Outbound HTTPS to Anthropic API using ANTHROPIC_API_KEY from environment; key is never logged, standard practice |
| 2 | Medium | skills/streak/tools/streak-notify.py | 187 | network-call | Outbound HTTPS to Telegram Bot API using bot token read from `.streak/config.md`; token stored in plaintext markdown |
| 3 | Medium | skills/streak/tools/streak-bot.py | 106 | subprocess-external | subprocess.run for git pull/push with user-provided challenge name in commit message; safe (list invocation, no shell=True) |
| 4 | Low | plugins/deckling/requirements.txt | 1 | SEC-unpinned-semver | `anthropic>=0.39.0` uses `>=` — will pick up any future major version including breaking changes |
| 5 | Low | skills/streak/tools/requirements.txt | 2 | SEC-unpinned-semver | `pytz>=2024.1` uses `>=` — unpinned minor/major; pin to a tested version for reproducibility |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | plugins/deckling/commands/deckling.md | References `skills/deckling-pptx.md` (relative to plugin) which does not exist in the scanned artifact set | Command cannot function; the skill it delegates to is missing |
| 2 | plugins/product-management/.claude-plugin/plugin.json | Declares version `0.1.0` but `plugins/product-management/skills/product-management/SKILL.md` declares `version: 0.2.0` | Version skew; users installing the plugin receive misleading metadata |
| 3 | plugins/product-management/skills/product-management/SKILL.md | Documents `/pm:review` command (line 131) but no `review.md` command file exists | Users following the documented workflow hit a missing command |
| 4 | plugins/product-management/commands/prd.md | No empty-argument branch: `$ARGUMENTS` is used directly in `gh issue list --search "$ARGUMENTS"` with no guard | Invoked as `/pm:prd` (no argument) silently searches all issues; user gets confusing output |
| 5 | commands/streak-switch.md | No empty-argument branch: no handling when `/streak-switch` is invoked with no challenge name | Claude receives `[challenge-name]` as a literal or empty string; instructions say "check if it exists" which will silently fail |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | skills/streak/tools/streak-notify.py | Bot token stored in plaintext `.streak/config.md` | Move token to environment variable `TELEGRAM_BOT_TOKEN`; read via `os.getenv` instead of parsing markdown |
| 2 | plugins/deckling/requirements.txt | `anthropic>=0.39.0` unpinned | Pin to `anthropic==0.39.0` (or latest tested) and add `# update intentionally` comment when bumping |
| 3 | skills/streak/tools/requirements.txt | `pytz>=2024.1` unpinned | Pin to `pytz==2024.1` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/streak-list.md | No `allowed-tools` declared | -5 |
| 2 | commands/streak.md | No `allowed-tools` declared | -5 |
| 3 | commands/streak-stats.md | No `allowed-tools` declared | -5 |
| 4 | commands/streak-insights.md | No `allowed-tools` declared | -5 |
| 5 | commands/streak-switch.md | No `allowed-tools` declared | -5 |
| 6 | commands/streak-new.md | No `allowed-tools` declared | -5 |
| 7 | plugins/deckling/commands/deckling.md | No `allowed-tools` declared | -5 |
| 8 | plugins/deckling/commands/deckling.md | No output format section; user cannot know what file will be produced or where | -10 |
| 9 | plugins/deckling/commands/deckling.md | Two-step instruction prose not numbered; violates multi-step sequencing requirement | -10 |
| 10 | plugins/deckling/commands/deckling.md | No empty-input handling for topic argument | -10 |
| 11 | plugins/mvp-launch/skills/mvp-launch/SKILL.md | "appropriate" used twice without concrete spec (line 17: "appropriate period"; line 23: "appropriately sized" — though line 23 is immediately followed by the concrete spec 44×44px, making it borderline) | -4 |
| 12 | plugins/product-management/agents/research-agent.md | "relevant" in quality standards (line 135: "information relevant to competitive positioning") | -2 |
| 13 | plugins/product-management/hooks/hooks.json | `timeout: 10` seconds may be insufficient if `.pm/` directory has many cached issue files to read | informational |
| 14 | plugins/product-management/.claude-plugin/plugin.json | Version 0.1.0 vs SKILL.md 0.2.0 (also filed as Bug #2) | informational |

## Cross-Component
**WINNING formula inconsistency**: `plugins/product-management/skills/product-management/SKILL.md` (line 13) shows `WINNING = Pain × Timing × Execution Capability` (3 factors, multiplicative), but `gap-analyst.md`, `gaps.md`, and the SKILL.md's own scoring table all implement **6 additive factors** summing to 60. The top-level formula is a misleading tagline that contradicts the working implementation directly below it.

**Orphaned `/pm:review` reference**: `product-management/SKILL.md` lines 118, 131 document `/pm:review` as a standard workflow step (after `/pm:gaps`, before `/pm:file`), but no `review.md` command file exists. This is a complete workflow gap — the gap-filing flow is undocumented.

**Missing `skills/deckling-pptx.md`**: `plugins/deckling/commands/deckling.md` delegates to a skill that does not exist. The actual implementation (`deckling_worker.py`) exists, but the skill abstraction layer is absent.

**Version drift**: `product-management/.claude-plugin/plugin.json` is at 0.1.0 while the installed skill self-identifies as 0.2.0. These should be kept in sync on every release.

**`references/` subdirectory files not scanned**: Multiple artifacts reference `references/search-patterns.md`, `references/stripe-testing.md`, `references/winning-filter.md`, `references/copy-formulas.md`, `references/file-templates.md`, `references/agent-guide.md`, and others. These files were out of scope for this audit but their presence should be verified before shipping — broken reference chains silently degrade agent quality.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

Priority order:
1. Create `plugins/deckling/skills/deckling-pptx.md` (or fix the reference) — command is non-functional without it
2. Create `plugins/product-management/commands/review.md` — workflow gap
3. Sync `plugin.json` version to 0.2.0
4. Add empty-argument guards to `prd.md` and `streak-switch.md`
5. Add `allowed-tools` to all 6 streak commands and deckling
6. Move Telegram bot token to env var; pin unpinned dependencies
