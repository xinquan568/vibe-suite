# NLPM Audit: addyosmani/web-quality-skills
**Date**: 2026-04-29  |  **Artifacts**: 7  |  **Strategy**: single
**NL Score**: 97/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 9  |  **Security Findings**: 0

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/seo/SKILL.md | skill | 92 | 4 vague quantifiers ("relevant", "reasonable", "important", "naturally") |
| skills/best-practices/SKILL.md | skill | 96 | "modern" and "appropriate" vague quantifiers |
| skills/web-quality-audit/SKILL.md | skill | 96 | "comprehensive" and "meaningful" vague quantifiers |
| skills/accessibility/SKILL.md | skill | 98 | "comprehensive" vague quantifier in description |
| CLAUDE.md | project-instructions | 100 | None |
| skills/core-web-vitals/SKILL.md | skill | 100 | None |
| skills/performance/SKILL.md | skill | 100 | None |

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
| Hooks | 0 |
| Scripts | 1 (`skills/web-quality-audit/scripts/analyze.sh`) |
| MCP configs | 0 |
| Package manifests | 0 |

### Security Findings
No security findings.

## Bugs (PR-worthy)
No bugs found.

## Security Fixes (PR-worthy, Medium/Low only)
No security fixes needed.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/seo/SKILL.md | "relevant" at line 237: "Link to relevant internal pages" — vague, no criteria for relevance | -2 |
| 2 | skills/seo/SKILL.md | "reasonable" at line 239: "Reasonable number of links per page" — vague, no threshold given | -2 |
| 3 | skills/seo/SKILL.md | "important" at line 470: "No `noindex` on important pages" — vague, no definition of importance | -2 |
| 4 | skills/seo/SKILL.md | "naturally" at line 120: "Include target keywords naturally" — vague instruction with no measurable criterion | -2 |
| 5 | skills/best-practices/SKILL.md | "modern" at line 10 (description): "Modern web development standards" — undated/undefined, changes over time | -2 |
| 6 | skills/best-practices/SKILL.md | "appropriate" at line 567: "Appropriate image aspect ratios" — no threshold or definition provided | -2 |
| 7 | skills/web-quality-audit/SKILL.md | "comprehensive" at line 10: "Comprehensive quality review" — scope-claim without enumeration | -2 |
| 8 | skills/web-quality-audit/SKILL.md | "meaningful" at line 45: "Every `<img>` has meaningful `alt` text" — criterion is undefined; should specify that alt describes subject and context | -2 |
| 9 | skills/accessibility/SKILL.md | "comprehensive" at line 10: "Comprehensive accessibility guidelines" — same pattern as #7 | -2 |

## Cross-Component
- All relative cross-skill references (`../performance/SKILL.md`, `../core-web-vitals/SKILL.md`, `../accessibility/SKILL.md`, `../seo/SKILL.md`, `../best-practices/SKILL.md`, `../web-quality-audit/SKILL.md`) resolve correctly.
- `skills/accessibility/references/A11Y-PATTERNS.md` and `skills/accessibility/references/WCAG.md` both exist and are properly referenced from `skills/accessibility/SKILL.md`.
- **Orphan document**: `skills/core-web-vitals/references/LCP.md` exists on disk but is not referenced anywhere in `skills/core-web-vitals/SKILL.md`. The skill's References section links to external `web.dev` URLs instead. This file is unreachable from any skill navigation.
- `CLAUDE.md` skill table and all referenced directories are consistent with what exists on disk.

## Recommendation
CLEAR — No bugs found and security is clean. Quality issues are all informational vague-language findings (9 × -2 penalties). Consider opening a single polish PR replacing vague quantifiers with specific criteria (e.g., "relevant" → concrete selection rule, "reasonable" → a numeric guideline, "meaningful alt" → descriptive criterion). Also consider either referencing or removing the orphan `skills/core-web-vitals/references/LCP.md`.
