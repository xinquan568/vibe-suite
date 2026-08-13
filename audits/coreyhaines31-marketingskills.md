# NLPM Audit: coreyhaines31/marketingskills
**Date**: 2026-04-13  |  **Artifacts**: 35  |  **Strategy**: batched
**NL Score**: 96/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 14  |  **Security Findings**: 3

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/ab-test-setup/SKILL.md | skill | 90 | Missing Output Format section |
| skills/ai-seo/SKILL.md | skill | 90 | Missing Output Format section |
| skills/churn-prevention/SKILL.md | skill | 90 | Missing Output Format section |
| skills/cold-email/SKILL.md | skill | 90 | Missing Output Format section |
| skills/copy-editing/SKILL.md | skill | 90 | Missing Output Format section |
| skills/free-tool-strategy/SKILL.md | skill | 90 | Missing Output Format section |
| skills/launch-strategy/SKILL.md | skill | 90 | Missing Output Format section |
| skills/marketing-psychology/SKILL.md | skill | 90 | Missing Output Format section |
| skills/paid-ads/SKILL.md | skill | 90 | Missing Output Format section |
| skills/paywall-upgrade-cro/SKILL.md | skill | 90 | Missing Output Format section |
| skills/pricing-strategy/SKILL.md | skill | 90 | Missing Output Format section |
| skills/referral-program/SKILL.md | skill | 90 | Missing Output Format section |
| skills/social-content/SKILL.md | skill | 90 | Missing Output Format section |
| skills/programmatic-seo/SKILL.md | skill | 98 | Vague quantifier: "CTAs appropriate to intent" |
| skills/ad-creative/SKILL.md | skill | 100 | — |
| skills/analytics-tracking/SKILL.md | skill | 100 | — |
| skills/community-marketing/SKILL.md | skill | 100 | — |
| skills/competitor-alternatives/SKILL.md | skill | 100 | — |
| skills/content-strategy/SKILL.md | skill | 100 | — |
| skills/copywriting/SKILL.md | skill | 100 | — |
| skills/customer-research/SKILL.md | skill | 100 | — |
| skills/email-sequence/SKILL.md | skill | 100 | — |
| skills/form-cro/SKILL.md | skill | 100 | — |
| skills/lead-magnets/SKILL.md | skill | 100 | — |
| skills/marketing-ideas/SKILL.md | skill | 100 | — |
| skills/onboarding-cro/SKILL.md | skill | 100 | — |
| skills/page-cro/SKILL.md | skill | 100 | — |
| skills/popup-cro/SKILL.md | skill | 100 | — |
| skills/product-marketing-context/SKILL.md | skill | 100 | — |
| skills/revops/SKILL.md | skill | 100 | — |
| skills/sales-enablement/SKILL.md | skill | 100 | — |
| skills/schema-markup/SKILL.md | skill | 100 | — |
| skills/seo-audit/SKILL.md | skill | 100 | — |
| skills/signup-flow-cro/SKILL.md | skill | 100 | — |
| skills/site-architecture/SKILL.md | skill | 100 | — |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 (none found) |
| CLI scripts (tools/clis/) | 61 Node.js files |
| MCP configs (.mcp.json) | 0 (none found) |
| Package manifests (package.json) | 0 (none found) |
| Python requirements (requirements.txt) | 0 (none found) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | tools/clis/*.js (all 61) | 3–10 | env var access | API credentials read from `process.env` — correct practice, not hardcoded; note for inventory |
| 2 | Medium | tools/clis/*.js (all 61) | ~17 | network calls | Outbound HTTPS calls to external marketing APIs — by design for this API wrapper library |
| 3 | Low | tools/clis/zapier.js | 34–45 | arbitrary URL | `hooks send --url <webhook_url>` POSTs to user-supplied URL; benign in CLI context but worth documenting |

## Bugs (PR-worthy)
No bugs found. All 35 skill files have valid `name` and `description` frontmatter. The `name` fields match their directory names. No broken cross-component references were detected within the audited SKILL.md files.

| # | File | Issue | Impact |
|---|------|-------|--------|
| — | — | No bugs found | — |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | tools/clis/zapier.js | `hooks send` accepts arbitrary user-supplied webhook URL with no validation | Add a comment documenting the intended use case; optionally validate URL scheme is `https://` |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/referral-program/SKILL.md | Missing `## Output Format` section — skill has a launch checklist and email templates but no section declaring structured output shape | -10 |
| 2 | skills/copy-editing/SKILL.md | Missing `## Output Format` section — the Seven Sweeps framework and Expert Panel Scoring are thorough, but the skill never declares what deliverable format to produce | -10 |
| 3 | skills/free-tool-strategy/SKILL.md | Missing `## Output Format` section — evaluation scorecard present but no output format declaration | -10 |
| 4 | skills/paid-ads/SKILL.md | Missing `## Output Format` section — reporting/analysis guidance present but no structured output spec | -10 |
| 5 | skills/ab-test-setup/SKILL.md | Missing `## Output Format` section — documentation template in references but no skill-level output format | -10 |
| 6 | skills/marketing-psychology/SKILL.md | Missing `## Output Format` section — knowledge/reference skill with no output format declaration | -10 |
| 7 | skills/churn-prevention/SKILL.md | Missing `## Output Format` section — cancel flow UI patterns and dunning templates present but output format not declared | -10 |
| 8 | skills/cold-email/SKILL.md | Missing `## Output Format` section — quality check present but no formal output format | -10 |
| 9 | skills/launch-strategy/SKILL.md | Missing `## Output Format` section — detailed launch checklist but no output format declaration | -10 |
| 10 | skills/ai-seo/SKILL.md | Missing `## Output Format` section — extensive audit tables and optimization strategy but no declared output structure | -10 |
| 11 | skills/social-content/SKILL.md | Missing `## Output Format` section — content calendar template present but no output format section | -10 |
| 12 | skills/pricing-strategy/SKILL.md | Missing `## Output Format` section — pricing checklist present but no output format declaration | -10 |
| 13 | skills/paywall-upgrade-cro/SKILL.md | Missing `## Output Format` section — specific paywall templates shown but no output format section | -10 |
| 14 | skills/programmatic-seo/SKILL.md | Vague quantifier: "CTAs appropriate to intent" (line 137) — "appropriate" is non-specific guidance | -2 |

## Cross-Component
- **Marketplace coverage**: `marketplace.json` lists all 35 audited skills — 100% match, no orphaned skills.
- **Internal references**: Multiple skills reference `references/` subdirectory files (e.g., `references/program-examples.md` in referral-program, `references/affiliate-programs.md`, `references/platform-specs.md` in ad-creative). These are valid optional on-demand reference files per the skill spec. Not audited here; if any are missing from the repo they would be silent failures when agents try to load them.
- **Related skills cross-references**: All `## Related Skills` cross-links point to skills that exist in the manifest. No orphaned cross-references detected.
- **product-marketing-context pattern**: All 35 skills consistently implement the "Check for product marketing context first" pattern — strong coherence across the collection.
- **Version inconsistency**: `customer-research` and `community-marketing` and `lead-magnets` are at version `1.0.0` while most other skills are at `1.1.0` or higher. This suggests they were added in a later batch but not bumped. Minor cosmetic issue.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

The collection is exceptionally high quality. All 35 skills have valid frontmatter, consistent structure, and follow a coherent cross-skill pattern (product-marketing-context integration, related skills linking, task-specific questions). The only actionable issues are: (1) 13 skills missing a formal `## Output Format` section — these skills have structured content but no dedicated section declaring deliverable shape, and (2) one minor vague quantifier in programmatic-seo.

The CLI tool suite (tools/clis/) is clean: zero-dependency Node.js, credentials from environment variables only, HTTPS-only calls to documented APIs, no shell execution, no eval. The sole low-severity note is the arbitrary webhook URL in zapier.js, which is intentional webhook sender functionality.

**Suggested PRs:**
1. Add `## Output Format` sections to the 13 affected skills (batch PR or individual)
2. Fix vague "CTAs appropriate to intent" → "CTAs matched to the page's conversion goal" in programmatic-seo
3. Add URL scheme validation comment to zapier.js `hooks send`
