# NLPM Audit: JimLiu/baoyu-skills
**Date**: 2026-04-29  |  **Artifacts**: 23  |  **Strategy**: batched
**NL Score**: 90/100
**Security**: CLEAR
**Bugs**: 2  |  **Quality Issues**: 11  |  **Security Findings**: 1

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/baoyu-image-gen/SKILL.md | skill | 82 | Deprecated; description embeds deprecation notice; no completion report |
| skills/baoyu-xhs-images/SKILL.md | skill | 82 | Deprecated; Step 0 EXTEND.md paths point to `baoyu-image-cards` config dir, not own |
| skills/baoyu-post-to-weibo/SKILL.md | skill | 87 | No formal completion/output summary step |
| skills/baoyu-post-to-x/SKILL.md | skill | 87 | No formal completion/output summary step |
| skills/baoyu-youtube-transcript/SKILL.md | skill | 87 | Duplicate step number 3 in Workflow section (steps read 1,2,3,3,4) |
| skills/baoyu-imagine/SKILL.md | skill | 88 | No completion/output summary step |
| skills/baoyu-url-to-markdown/SKILL.md | skill | 88 | No formal completion summary step |
| CLAUDE.md | project-config | 88 | Vague "short variable names" in code style guidance |
| skills/baoyu-danger-gemini-web/SKILL.md | skill | 90 | No numbered workflow steps (CLI backend; acceptable but reduces discoverability) |
| skills/baoyu-danger-x-to-markdown/SKILL.md | skill | 90 | Clean |
| skills/baoyu-diagram/SKILL.md | skill | 90 | Missing `version` and `metadata.openclaw` fields present in all other skills |
| skills/baoyu-format-markdown/SKILL.md | skill | 90 | Vague qualifier "obvious" (in "obvious typos") |
| skills/baoyu-markdown-to-html/SKILL.md | skill | 90 | Clean |
| skills/baoyu-article-illustrator/SKILL.md | skill | 92 | Clean |
| skills/baoyu-comic/SKILL.md | skill | 92 | Clean |
| skills/baoyu-cover-image/SKILL.md | skill | 92 | Clean |
| skills/baoyu-image-cards/SKILL.md | skill | 92 | Clean |
| skills/baoyu-infographic/SKILL.md | skill | 92 | Clean |
| skills/baoyu-post-to-wechat/SKILL.md | skill | 92 | Clean |
| skills/baoyu-slide-deck/SKILL.md | skill | 92 | Clean |
| skills/baoyu-translate/SKILL.md | skill | 92 | Clean |
| skills/baoyu-compress-image/SKILL.md | skill | 93 | Clean |
| .claude/skills/release-skills/SKILL.md | skill | 96 | Vague "meaningful description" (×2, lines ~284–291) |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts | `scripts/sync-clawhub.sh` (1 .sh file; .mjs files not executable-surface matches) |
| MCP configs | 0 |
| Package manifests | `package.json` |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Low | package.json | 1 | SEC-unpinned-semver | All `dependencies` and `devDependencies` use `^` semver ranges; a compromised patch release of `sharp`, `pdf-lib`, `pptxgenjs`, or any devDep could be silently picked up on next install |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/baoyu-youtube-transcript/SKILL.md | Duplicate step number in Workflow section — the list reads 1, 2, 3, 3, 4; the second item 3 ("The script auto-saves…") should be item 4, and the current item 4 ("For `--speakers` mode…") should be item 5 | Agents following the numbered workflow skip or misorder the save-and-path-report step |
| 2 | skills/baoyu-xhs-images/SKILL.md | Step 0 EXTEND.md search paths reference `.baoyu-skills/baoyu-image-cards/EXTEND.md` (and XDG/home equivalents) instead of `.baoyu-skills/baoyu-xhs-images/EXTEND.md`; the deprecated skill has no config isolation from its replacement | Users who install only `baoyu-xhs-images` cannot save skill-specific preferences; the skill silently uses or overwrites `baoyu-image-cards` configuration |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | package.json | Unpinned semver ranges (`^`) for runtime dependencies `sharp ^0.34.5`, `pdf-lib ^1.17.1`, `pptxgenjs ^4.0.1` and devDeps | Pin to exact versions (`"sharp": "0.34.5"`) or use a lockfile-only strategy with `npm ci`; consider `overrides` to lock transitive deps |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/baoyu-image-gen/SKILL.md | Deprecated skill: description opens with `"[Deprecated: use baoyu-imagine]"` — unusual frontmatter pattern; no completion/output summary step | -8 |
| 2 | skills/baoyu-xhs-images/SKILL.md | Deprecated skill: description opens with `"[Deprecated: use baoyu-image-cards]"` — unusual frontmatter pattern; bug #2 also applies | -8 |
| 3 | skills/baoyu-diagram/SKILL.md | Missing `version` and `metadata.openclaw` fields that every other skill carries; reduces marketplace discoverability | -5 |
| 4 | skills/baoyu-imagine/SKILL.md | No completion/output summary step; after generation the skill only prints "Using [provider] / [model]" — no structured post-generation report | -5 |
| 5 | skills/baoyu-post-to-weibo/SKILL.md | No formal completion/output summary; workflow ends after scripts run and browser opens with no structured feedback | -5 |
| 6 | skills/baoyu-post-to-x/SKILL.md | No formal completion/output summary; same pattern as baoyu-post-to-weibo | -5 |
| 7 | skills/baoyu-url-to-markdown/SKILL.md | Workflow section (4 prose items) lacks a completion summary step; agent has no standardized success signal | -5 |
| 8 | .claude/skills/release-skills/SKILL.md | Vague qualifier: "Clear, meaningful description" appears twice in commit message guidance (Step 6); "meaningful" is not actionable | -4 |
| 9 | skills/baoyu-format-markdown/SKILL.md | Vague qualifier: "obvious typos" in Step 2 — what counts as "obvious" is subjective and inconsistently applied | -2 |
| 10 | CLAUDE.md | Vague qualifier: "short variable names" in Code Style section — threshold is undefined | -2 |
| 11 | skills/baoyu-danger-gemini-web/SKILL.md | No numbered workflow steps; pure CLI-reference structure reduces discoverability of the consent-check gate for first-time users | -5 |

## Cross-Component
**baoyu-xhs-images ↔ baoyu-image-cards config coupling**: The deprecated `baoyu-xhs-images` skill hardcodes `baoyu-image-cards` EXTEND.md paths in Step 0 (all three priority levels). While CLAUDE.md documents this as intentional migration scaffolding ("sync any cross-cutting changes with baoyu-image-cards"), it means any user who installs `baoyu-xhs-images` alone will silently create or read `baoyu-image-cards` config directories — polluting a skill they may not have installed. This is both a bug (filed above) and a cross-component coupling that violates the skill self-containment principle stated in CLAUDE.md.

**baoyu-image-gen version drift**: `baoyu-image-gen` is at version 1.56.4 while `baoyu-imagine` is at 1.58.0. CLAUDE.md requires these to stay in sync ("sync any cross-cutting changes with baoyu-imagine"). The DashScope `wan2.7-image-pro`/`wan2.7-image` `--ref` support documented in `baoyu-imagine` (line 94) is not reflected in `baoyu-image-gen` (line 90), indicating drift has already occurred.

**baoyu-youtube-transcript duplicate step**: The step-numbering bug (1,2,3,3,4) in the Workflow section is isolated to that file; no other skill references this workflow, so there is no cross-component impact beyond the single skill.

**CLAUDE.md docs/ references**: CLAUDE.md references several `docs/` files (`docs/user-input-tools.md`, `docs/image-generation-tools.md`, `docs/chrome-profile.md`, etc.) that are outside any individual skill. These are explicitly marked "repo-author guidance only" and correctly excluded from SKILL.md cross-references — no inconsistency found.

## Recommendation
CLEAR — submit PRs for all bugs and the low-severity security fix. Security posture is clean (no critical or high findings). Two bugs have direct agent-behavior impact: the duplicate step in `baoyu-youtube-transcript` causes workflow misordering, and the wrong EXTEND.md paths in `baoyu-xhs-images` cause silent config leakage. The unpinned semver issue in `package.json` is a standard supply-chain hygiene fix safe to PR directly.
