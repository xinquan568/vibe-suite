# NLPM Audit: lijigang/ljg-skills
**Date**: 2026-05-13  |  **Artifacts**: 22  |  **Strategy**: batched
**NL Score**: 90/100
**Security**: REVIEW
**Bugs**: 2  |  **Quality Issues**: 16  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/ljg-paper/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-invest/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-plain/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-read/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-think/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-rank/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-paper-river/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-writes/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-skill-map/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-paper-flow/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-word-flow/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-travel/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-card/SKILL.md | skill | 85 | No example blocks |
| skills/ljg-present/SKILL.md | skill | 85 | No example blocks |
| CLAUDE.md | docs | 85 | Skill inventory lists only 7 of 21 skills |
| skills/ljg-push/SKILL.md | skill | 97 | Workflow reference to Workflows/Push.md unverified |
| skills/ljg-word/SKILL.md | skill | 97 | Stale example names obsolete skill "ljg-explain-words" |
| skills/ljg-learn/SKILL.md | skill | 100 | — |
| skills/ljg-roundtable/SKILL.md | skill | 100 | — |
| skills/ljg-relationship/SKILL.md | skill | 100 | — |
| skills/ljg-qa/SKILL.md | skill | 100 | — |
| .claude-plugin/plugin.json | manifest | 100 | — |

**Scoring notes**: Skills scored 100 if they have `name`+`description` frontmatter, at least one `<example>` block, and a clear output format. Skills without any example block received −15. The two 97-point skills each have a single minor cross-reference issue (−3). CLAUDE.md receives −15 for severely stale skill inventory. Weighted average: 1969/22 = **90/100**.

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 4 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts | scripts/install.sh, scripts/sync-push.sh, skills/ljg-push/Tools/Push.sh, skills/ljg-skill-map/scripts/scan.sh |
| Node.js scripts | skills/ljg-card/assets/capture.js |
| Package manifests | skills/ljg-card/package.json |
| Hooks | (none) |
| MCP configs | (none) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | skills/ljg-qa/SKILL.md | 44 | SEC-network-call | Skill instructs Claude to POST to `localhost:31337/notify` as a voice notification side-effect. Fixed payload, no user data exfiltrated, but any process can bind that port. |
| 2 | Medium | skills/ljg-push/SKILL.md | 74 | SEC-network-call | Same localhost:31337 voice notification pattern. Fixed payload, but assumes a trusted service at that port. |
| 3 | Medium | scripts/install.sh | 11 | SEC-postinstall-script | Runs `npm install` which executes any `postinstall` scripts in playwright's dependency tree — supply-chain risk on first install. |
| 4 | Medium | scripts/sync-push.sh | 9 | SEC-path-traversal | `SKILL="$1"` is used unsanitized to build `rsync` target path (`$REPO/skills/$SKILL`). A caller passing `../../outside-repo` and having a matching local directory would rsync files outside the skills subtree. |
| 5 | Low | skills/ljg-card/package.json | 3 | SEC-unpinned-semver | `playwright` pinned with caret range (`^1.58.2`) — allows automatic minor/patch upgrades, meaning future `npm install` pulls a newer, unreviewed version. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/ljg-word/SKILL.md | Example on line 11 says `[Calls ljg-explain-words with "Serendipity"]` — the skill's own name is `ljg-word`, not `ljg-explain-words`. Stale artifact from a rename. | Misleads users about how to invoke the skill; breaks copy-paste invocation patterns. |
| 2 | CLAUDE.md | Skill inventory table (lines 39–48) lists only 7 skills (ljg-card, ljg-paper, ljg-paper-flow, ljg-plain, ljg-skill-map, ljg-word, ljg-writes) while the repo contains 21 skills. 14 skills are completely absent from the inventory. | New contributors and automated tooling scanning CLAUDE.md for the skill list get a severely incomplete picture. |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | skills/ljg-qa/SKILL.md | curl to localhost:31337 runs as a side-effect whenever the skill executes | Wrap in an explicit opt-in env-var check: `[ "${LJG_NOTIFY:-0}" = "1" ] && curl ...` |
| 2 | skills/ljg-push/SKILL.md | Same localhost notification pattern | Same opt-in env-var guard |
| 3 | scripts/install.sh | `npm install` runs with no integrity check | Add `npm ci` (requires package-lock.json) or pin playwright via exact version + run `npm install --ignore-scripts` |
| 4 | scripts/sync-push.sh | Unsanitized `$1` in rsync target path | Validate that `SKILL` matches the pattern `^ljg-[a-z][a-z0-9-]*$` before use: `[[ "$SKILL" =~ ^ljg-[a-z][a-z0-9-]*$ ]] || exit 2` |
| 5 | skills/ljg-card/package.json | `^1.58.2` semver range | Pin to exact version: `"playwright": "1.58.2"` and commit a lock file |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/ljg-paper/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 2 | skills/ljg-invest/SKILL.md | No `<example>` block | −15 |
| 3 | skills/ljg-plain/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 4 | skills/ljg-read/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 5 | skills/ljg-think/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 6 | skills/ljg-rank/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 7 | skills/ljg-paper-river/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 8 | skills/ljg-writes/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 9 | skills/ljg-skill-map/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 10 | skills/ljg-paper-flow/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 11 | skills/ljg-word-flow/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 12 | skills/ljg-travel/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 13 | skills/ljg-card/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 14 | skills/ljg-present/SKILL.md | No `<example>` block despite `user_invocable: true` | −15 |
| 15 | skills/ljg-push/SKILL.md | References `Workflows/Push.md` in the workflow instructions; directory `Workflows/` is non-standard (repo convention uses `references/`). File existence unverified. | −3 |
| 16 | skills/ljg-qa/SKILL.md | References `Workflows/Extract.md` and `References/QuestionDesign.md` in workflow instructions; file existence unverified. | −3 (informational) |

## Cross-Component

**Stale CLAUDE.md inventory (CC-stale-count):** The `Skill Inventory` table in `CLAUDE.md` covers only 7 skills. The actual repo ships 21 skills across `skills/ljg-*/SKILL.md`. Missing from the inventory: ljg-learn, ljg-invest, ljg-think, ljg-word, ljg-roundtable, ljg-relationship, ljg-qa, ljg-push, ljg-rank, ljg-paper-river, ljg-read, ljg-skill-map, ljg-word-flow, ljg-travel, ljg-present, ljg-paper-river, ljg-paper-flow, ljg-writes (and others). This is the same issue as Bug #2 above.

**Template references (potential CC-broken-relative-path):** Both `skills/ljg-paper/SKILL.md` (line 35) and `skills/ljg-paper-river/SKILL.md` (line 30) reference `references/template.org` as the authoritative output template. The file was not found in the audited file set; if it is absent from those skill directories, the output format instructions are broken.

**Voice notification port coupling (informational):** `skills/ljg-qa/SKILL.md` and `skills/ljg-push/SKILL.md` both hard-code `localhost:31337` as a notification endpoint. This creates an implicit runtime dependency on a service the skill collection does not provision. No cross-skill documentation describes what should be running on that port.

**ljg-word-flow → ljg-card dependency:** `skills/ljg-word-flow/SKILL.md` depends on `ljg-card -i` and `skills/ljg-paper-flow/SKILL.md` depends on `ljg-card` in both modes. These composition dependencies are undocumented in `CLAUDE.md` and untested as a group.

## Recommendation

REVIEW — submit NL fix PRs for Bug #1 (stale example in ljg-word) and Bug #2 (CLAUDE.md inventory). Add `<example>` blocks to user-invocable skills that lack them (14 skills). For security findings, pin playwright, guard the localhost curl calls behind an opt-in env var, and sanitize the SKILL parameter in sync-push.sh — these are suitable for public PRs. No Critical or High security findings; no private disclosure required.
