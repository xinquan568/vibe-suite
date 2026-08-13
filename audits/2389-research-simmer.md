# NLPM Audit: 2389-research/simmer
**Date**: 2026-04-06  |  **Artifacts**: 8  |  **Strategy**: single
**NL Score**: 93/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 9  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| CLAUDE.md | Documentation | 75 | R33/R34: no build/run or test commands; missing prerequisites section |
| skills/SKILL.md | Skill (Orchestrator) | 88 | R05: 550 lines (>500 limit); R01: "appropriate" line 185 |
| skills/simmer-judge-board/SKILL.md | Skill | 90 | R01: "relevant" ×5 instances (lines 53, 125, 267, 271, 275) |
| skills/simmer-judge/SKILL.md | Skill | 96 | R01: "relevant" ×2 instances (lines 56, 135) |
| skills/simmer-setup/SKILL.md | Skill | 98 | R01: "some" at line 138 |
| .claude-plugin/plugin.json | Plugin Manifest | 100 | None |
| skills/simmer-generator/SKILL.md | Skill | 100 | None |
| skills/simmer-reflect/SKILL.md | Skill | 100 | None |

Weighted average: (75 + 88 + 90 + 96 + 98 + 100 + 100 + 100) / 8 = **93/100**

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | None found |
| Scripts (.sh/.py/.js) | None found |
| MCP configs (.mcp.json) | None found |
| Package manifests (package.json / requirements.txt) | None found |

### Security Findings

No security findings. This is a pure-markdown plugin with zero executable surfaces.

## Bugs (PR-worthy)

No bugs found. All plugin.json manifest fields are present and valid (name, semver version 3.0.0, description). All six SKILL.md files have required frontmatter (name + description). No broken skill cross-references — every subskill name referenced in skills/SKILL.md (`simmer:simmer-setup`, `simmer:simmer-generator`, `simmer:simmer-judge`, `simmer:simmer-judge-board`, `simmer:simmer-reflect`) has a corresponding SKILL.md in the repo.

## Security Fixes (PR-worthy, Medium/Low only)

No security fixes needed.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | CLAUDE.md | R33: No build/run command — no install instructions (e.g., `claude plugin install simmer@2389-research`) | −10 |
| 2 | CLAUDE.md | R34: No test command — `tests/integration/simmer-scenario.md` exists but no instructions to run it | −5 |
| 3 | CLAUDE.md | R38: Actionability ratio — >60% of content is descriptive (overview, tables, diagrams) with minimal actionable instructions | −5 |
| 4 | CLAUDE.md | No prerequisites section — does not state "none required" or list required tools/versions | −5 |
| 5 | skills/SKILL.md | R05: 550 lines exceeds 500-line ceiling; single-agent mode section (~35 lines) could be extracted to a linked reference | −10 |
| 6 | skills/SKILL.md | R01: "appropriate" at line 185 — "(or appropriate extension matching artifact type)" gives no measurable guidance on extension choice | −2 |
| 7 | skills/simmer-judge-board/SKILL.md | R01: "relevant" ×5 at lines 53, 125, 267, 271, 275 — all lack measurable criteria; file accumulates −10 (cap applies) | −10 |
| 8 | skills/simmer-judge/SKILL.md | R01: "relevant" ×2 at lines 56, 135 — "Extract what's relevant to the criteria" and "search for relevant techniques" | −4 |
| 9 | skills/simmer-setup/SKILL.md | R01: "some" at line 138 — "If some fields are missing or ambiguous" — no specification of which fields trigger the conversational path | −2 |

## Cross-Component
| # | Issue | Files | Impact |
|---|-------|-------|--------|
| 1 | CLAUDE.md directory tree (lines 82–91) lists four subskills (simmer-setup, simmer-generator, simmer-judge, simmer-reflect) but omits `simmer-judge-board/`. The subskill IS referenced in the Subskills table at line 20 and IS present on disk, so this is a stale directory listing only — no broken functionality. | CLAUDE.md ↔ skills/simmer-judge-board/SKILL.md | Informational — misleads readers inspecting plugin structure |

No broken partial references, no orphaned components, no contradictions between files. All five subskills referenced in the orchestrator SKILL.md exist and are internally consistent with the descriptions in CLAUDE.md.

## Recommendation

CLEAR — submit PRs for all quality fixes.

Priority order:
1. **CLAUDE.md** (highest ROI): add installation, testing, and prerequisites sections — 3 separate quality penalties totaling −20 points, all fixable in < 10 lines.
2. **skills/SKILL.md** R05: Extract or trim the single-agent mode section to get under 500 lines.
3. **skills/simmer-judge-board/SKILL.md** R01: Replace 5 "relevant" instances with specific artifact names or conditions (−10 accumulated).
4. **skills/simmer-judge/SKILL.md** and **skills/simmer-setup/SKILL.md**: Minor R01 substitutions (2 and 1 occurrences respectively).
5. **CLAUDE.md directory structure**: Add `simmer-judge-board/` entry to the directory tree.
