# NLPM Audit: dontbesilent2025/dbskill
**Date**: 2026-04-13  |  **Artifacts**: 12  |  **Strategy**: single
**NL Score**: 90/100
**Security**: REVIEW
**Bugs**: 1  |  **Quality Issues**: 5  |  **Security Findings**: 7

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/dbskill-upgrade/SKILL.md | skill | 78 | Embedded destructive shell scripts; non-standard frontmatter; Chinese-only description |
| skills/dbs-ai-check/SKILL.md | skill | 86 | Broken `/文风分析` skill reference in next-step suggestions |
| skills/dbs-benchmark/SKILL.md | skill | 90 | Vague "合理时间内" (within a reasonable time) quantifier |
| skills/dbs-diagnosis/SKILL.md | skill | 90 | Vague "合适的时机" (appropriate timing) quantifier |
| skills/dbs-xhs-title/SKILL.md | skill | 90 | No issues beyond size (good: 75 inline formulas) |
| skills/dbs/SKILL.md | skill | 91 | Clean router; chatroom-austrian not in numbered menu |
| skills/dbs-deconstruct/SKILL.md | skill | 91 | No significant issues |
| skills/dbs-hook/SKILL.md | skill | 91 | No significant issues |
| skills/dbs-slowisfast/SKILL.md | skill | 91 | No significant issues |
| skills/dbs-action/SKILL.md | skill | 92 | No significant issues |
| skills/dbs-content/SKILL.md | skill | 92 | No significant issues |
| skills/chatroom-austrian/SKILL.md | skill | 93 | No significant issues |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 3 |
| Medium | 3 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts | `scripts/record-demo.sh` |
| MCP configs | 0 |
| Package manifests | 0 |
| Embedded scripts in skills | `skills/dbskill-upgrade/SKILL.md` (bash code blocks executed by Claude) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH | skills/dbskill-upgrade/SKILL.md | 78 | File deletion outside repo | `rm -rf "$HOME/.claude/skills"/dbs*` — deletes user's installed skills without granular confirmation |
| 2 | HIGH | skills/dbskill-upgrade/SKILL.md | 67 | Runtime code install from network | `git clone --depth 1 https://github.com/dontbesilent2025/dbskill.git` then copies downloaded code into `~/.claude/skills/` — supply chain risk if repo is compromised |
| 3 | HIGH | skills/dbskill-upgrade/SKILL.md | 79 | File writes outside repo | `cp -r "$TMP_DIR/dbskill/skills"/dbs* "$HOME/.claude/skills/"` — installs externally fetched code as Claude skills |
| 4 | MEDIUM | skills/dbskill-upgrade/SKILL.md | 40 | Network call | `curl -sL https://raw.githubusercontent.com/dontbesilent2025/dbskill/main/VERSION` — fetches content from external URL |
| 5 | MEDIUM | scripts/record-demo.sh | 41 | Network call with user-controlled variable | `gh api "repos/$upstream/..."` where `$upstream` derives from `git remote get-url` — passes unvalidated remote URL fragment to GitHub API |
| 6 | MEDIUM | scripts/record-demo.sh | 63 | Variable in sed substitution | `sed "s|MARKETPLACE_REPO|$MARKETPLACE_REPO|g"` — MARKETPLACE_REPO comes from git remote URL; a URL containing `|` could corrupt the sed command |
| 7 | LOW | scripts/record-demo.sh | 80 | Fragile output parsing | `ls -lh "$OUTPUT_GIF" \| awk '{print $5}'` — parsing `ls` output is brittle across locales/platforms |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/dbs-ai-check/SKILL.md:255 | References `/文风分析` skill in "下一步建议" (next-step suggestions); no such skill exists in the repo or dbs routing table | Users who follow this suggestion will get a "skill not found" error; dead end in the diagnostic flow |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/record-demo.sh:63 | `MARKETPLACE_REPO` variable in sed substitution without sanitization | Validate/sanitize the value before use: `MARKETPLACE_REPO=$(echo "$MARKETPLACE_REPO" \| tr -dc 'A-Za-z0-9/_-')` |
| 2 | scripts/record-demo.sh:80 | Parses `ls` output | Replace with `stat -c%s "$OUTPUT_GIF"` (Linux) or `wc -c < "$OUTPUT_GIF"` for portable byte count |

*Note: Findings #1–3 (HIGH) involve `skills/dbskill-upgrade/SKILL.md` and require private disclosure or careful architectural review rather than a public PR fix — see Recommendation.*

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/dbskill-upgrade/SKILL.md | Non-standard `trigger` frontmatter field — trigger info belongs inside `description` per Claude Code skill schema | -3 |
| 2 | skills/dbskill-upgrade/SKILL.md | Description is Chinese-only; all peer skills provide bilingual (Chinese + English) descriptions | -5 |
| 3 | skills/dbskill-upgrade/SKILL.md | Embedded destructive shell scripts (`rm -rf`, `git clone`, network fetch) in an NL skill file create an implicit auto-updater that runs without a dedicated security gate; flagged as HIGH in security | -10 |
| 4 | skills/dbs-benchmark/SKILL.md:71 | Vague quantifier: "合理时间内获取这些资源" (within a reasonable timeframe) — "reasonable" is undefined | -2 |
| 5 | skills/dbs-diagnosis/SKILL.md:413 | Vague quantifier: "在合适的时机指出" (point out at an appropriate time) — "appropriate" is undefined | -2 |

## Cross-Component
**Routing coverage**: `dbs/SKILL.md` routes all 9 diagnostic skills correctly. `chatroom-austrian` is intentionally not in the main menu (it's accessed via `/奥派` or `/chatroom-austrian` directly, and referenced conditionally from `dbs-diagnosis` and `dbs-deconstruct`) — acceptable design.

**Knowledge base**: All `知识库/Skill知识包/` references in deep-reference footnotes resolve to real files in the repo. No broken paths.

**Broken reference**: `dbs-ai-check/SKILL.md` references `/文风分析` in a conditional next-step suggestion. This skill does not exist anywhere in the repo. The routing table in `dbs/SKILL.md` has no entry for it. The atoms JSON files mention "文风分析" as a concept only. This is a dead reference that should either be removed or replaced with an existing skill (e.g., `/dbs-ai-check` already handles style analysis, so the suggestion could point back to it with a different framing, or be removed entirely).

**dbskill-upgrade isolation**: The upgrade skill is architecturally separate from the diagnostic skills and not listed in `dbs/SKILL.md`'s routing table — correct, as it's a maintenance tool, not a business diagnostic.

## Recommendation
REVIEW — submit NL fix PRs, flag security findings in issue.

The NL quality is high (90/100): all 12 skills have correct frontmatter, well-defined output formats, inline case libraries, and a coherent cross-referencing system. The one NL bug (broken `/文风分析` reference) is a safe, low-risk PR fix.

The HIGH security findings in `skills/dbskill-upgrade/SKILL.md` do not block NL fix PRs, but should be filed as a separate security issue before any PR that touches that skill. The core concern is that invoking `/dbskill-upgrade` causes Claude to run `rm -rf ~/.claude/skills/dbs*` followed by a `git clone` from GitHub and a copy into `~/.claude/skills/` — an implicit auto-updater with no integrity check on the downloaded code. If the upstream repo (`dontbesilent2025/dbskill`) is ever compromised, the skill becomes a supply chain vector. Recommended mitigations: add a checksum/hash verification step, display a diff of what will change before executing, and require explicit user confirmation before `rm -rf`.

The MEDIUM findings in `scripts/record-demo.sh` are developer tooling (GIF recording script) and are low operational risk, but the two easy fixes are noted above.
