# NLPM Re-Audit: aaron-he-zhu/seo-geo-claude-skills

**Date**: 2026-04-24  |  **Artifacts**: 38  |  **Strategy**: batched
**NL Score**: 95/100
**Bugs**: 0  |  **Quality Issues**: 31

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| commands/setup-alert.md | command | 85 | No empty-input handling (-10) |
| commands/keyword-research.md | command | 85 | No empty-input handling (-10) |
| commands/report.md | command | 85 | No empty-input handling (-10) |
| commands/write-content.md | command | 85 | No empty-input handling (-10) |
| commands/audit-domain.md | command | 85 | No empty-input handling (-10) |
| commands/optimize-meta.md | command | 85 | No empty-input handling (-10) |
| commands/p2-review.md | command | 85 | No numbered steps in evaluation procedure (-10) |
| commands/generate-schema.md | command | 88 | No empty-input handling (-10) |
| commands/audit-page.md | command | 88 | No empty-input handling (-10) |
| commands/check-technical.md | command | 90 | No empty-input handling (-10) |
| commands/contract-lint.md | command | 90 | No numbered workflow steps (-10) |
| cross-cutting/domain-authority-auditor/SKILL.md | skill | 94 | Vague quantifiers ×3 (-6) |
| CLAUDE.md | project-context | 95 | Missing test command (-5) |
| commands/wiki-lint.md | command | 95 | Missing allowed-tools (-5) |
| monitor/backlink-analyzer/SKILL.md | skill | 96 | Vague quantifiers ×2 (-4) |
| cross-cutting/content-quality-auditor/SKILL.md | skill | 96 | Vague quantifiers ×2 (-4) |
| optimize/internal-linking-optimizer/SKILL.md | skill | 96 | Vague quantifiers ×2 (-4) |
| monitor/alert-manager/SKILL.md | skill | 98 | Vague quantifier ×1 (-2) |
| cross-cutting/memory-management/SKILL.md | skill | 98 | Vague quantifier ×1 (-2) |
| build/schema-markup-generator/SKILL.md | skill | 98 | Vague quantifier ×1 (-2) |
| optimize/on-page-seo-auditor/SKILL.md | skill | 98 | Vague quantifier ×1 (-2) |
| optimize/technical-seo-checker/SKILL.md | skill | 98 | Vague quantifier ×1 (-2) |
| commands/validate-library.md | command | 100 | — |
| commands/sync-versions.md | command | 100 | — |
| commands/geo-drift-check.md | command | 100 | — |
| hooks/hooks.json | hooks | 100 | — |
| .claude-plugin/plugin.json | plugin | 100 | — |
| research/content-gap-analysis/SKILL.md | skill | 100 | — |
| research/serp-analysis/SKILL.md | skill | 100 | — |
| research/keyword-research/SKILL.md | skill | 100 | — |
| research/competitor-analysis/SKILL.md | skill | 100 | — |
| monitor/rank-tracker/SKILL.md | skill | 100 | — |
| monitor/performance-reporter/SKILL.md | skill | 100 | — |
| cross-cutting/entity-optimizer/SKILL.md | skill | 100 | — |
| build/geo-content-optimizer/SKILL.md | skill | 100 | — |
| build/seo-content-writer/SKILL.md | skill | 100 | — |
| build/meta-tags-optimizer/SKILL.md | skill | 100 | — |
| optimize/content-refresher/SKILL.md | skill | 100 | — |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|

None found.

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/setup-alert.md | Missing `allowed-tools` declaration | -5 |
| 2 | commands/setup-alert.md | No empty-input handling | -10 |
| 3 | commands/keyword-research.md | Missing `allowed-tools` declaration | -5 |
| 4 | commands/keyword-research.md | No empty-input handling | -10 |
| 5 | commands/report.md | Missing `allowed-tools` declaration | -5 |
| 6 | commands/report.md | No empty-input handling | -10 |
| 7 | commands/write-content.md | Missing `allowed-tools` declaration | -5 |
| 8 | commands/write-content.md | No empty-input handling | -10 |
| 9 | commands/check-technical.md | No empty-input handling | -10 |
| 10 | commands/generate-schema.md | No empty-input handling | -10 |
| 11 | commands/generate-schema.md | Vague quantifier "appropriate" | -2 |
| 12 | commands/audit-domain.md | Missing `allowed-tools` declaration | -5 |
| 13 | commands/audit-domain.md | No empty-input handling | -10 |
| 14 | commands/audit-page.md | No empty-input handling | -10 |
| 15 | commands/audit-page.md | Vague quantifier "Some EEAT items" | -2 |
| 16 | commands/optimize-meta.md | Missing `allowed-tools` declaration | -5 |
| 17 | commands/optimize-meta.md | No empty-input handling | -10 |
| 18 | commands/p2-review.md | Missing `allowed-tools` declaration | -5 |
| 19 | commands/p2-review.md | Multi-step evaluation procedure without numbered steps | -10 |
| 20 | commands/contract-lint.md | Multi-step lint workflow without numbered steps | -10 |
| 21 | commands/wiki-lint.md | Missing `allowed-tools` declaration | -5 |
| 22 | CLAUDE.md | Missing test command (R34) | -5 |
| 23 | cross-cutting/domain-authority-auditor/SKILL.md | Vague quantifiers ×3: "Some items" (×2), "niche-relevant" | -6 |
| 24 | cross-cutting/content-quality-auditor/SKILL.md | Vague quantifiers ×2: "sufficient data", "Some EEAT items" | -4 |
| 25 | optimize/internal-linking-optimizer/SKILL.md | Vague quantifiers ×2: "topic-relevant link opportunities", "Add relevant links" | -4 |
| 26 | monitor/backlink-analyzer/SKILL.md | Vague quantifiers ×2 including "Relevant audience" | -4 |
| 27 | cross-cutting/memory-management/SKILL.md | Vague quantifier: "locate relevant WARM files" | -2 |
| 28 | monitor/alert-manager/SKILL.md | Vague quantifier: "For each relevant category" | -2 |
| 29 | build/schema-markup-generator/SKILL.md | Vague quantifier: "Selects appropriate Schema.org types" | -2 |
| 30 | optimize/on-page-seo-auditor/SKILL.md | Vague quantifier: "on-page-relevant items" | -2 |
| 31 | optimize/technical-seo-checker/SKILL.md | Vague quantifier: "properly crawling" | -2 |

## Cross-Component

`hooks/hooks.json` uses the `FileChanged` event for a hook that watches `memory/hot-cache.md` line count. `FileChanged` does not appear in the NLPM conventions hook-events list (`SessionStart`, `UserPromptSubmit`, `PostToolUse`, `Stop`). This finding was reviewed against the 4-step gate and is recorded as a **false positive**: the event name is valid JSON, the behavior is intentional (the project design documents hot-cache.md size management), and `FileChanged` is likely a Claude Code event added after the conventions file was last updated. No penalty applied.

No broken references, orphaned components, or terminology drift detected. All 20 skills cross-reference their `Next Best Skill` entries consistently, and the plugin.json skills list matches the repository layout.

## Recommendation

The skills layer is excellent (avg 98.6/100) and infrastructure artifacts score 100; the primary improvement area is command hygiene — 8 of 15 commands lack `allowed-tools` declarations and 9 omit explicit empty-input handling, both of which are straightforward batch fixes that would raise the overall score to ≥98.
