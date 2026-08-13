# Re-Audit: aaron-he-zhu/seo-geo-claude-skills

**Date**: 2026-04-24  |  **Before**: `unknown` (91/100)  |  **After**: `dc77e77` (95/100)

## Summary

| Outcome | Count |
|---------|------:|
| fixed — our PR merged | 1 |
| fixed — applied separately | 9 |
| fixed — upstream, not via our PR | 25 |
| newly introduced (regressions) | 32 |

## Original findings — verification

| # | File | Line | Rule | Pattern | Outcome | PR |
|---|------|------|------|---------|---------|----|
| 1 | `commands/contract-lint.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — our PR merged | #10 |
| 2 | `commands/wiki-lint.md` | — | BUG-missing-steps | `missing-step-ordering` | fixed — upstream, not via our PR | #11 |
| 3 | `.claude-plugin/plugin.json` | — | CC-version-drift | `version-drift` | fixed — upstream, not via our PR |  |
| 4 | `commands/audit-domain.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 5 | `commands/keyword-research.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 6 | `commands/optimize-meta.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 7 | `commands/p2-review.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 8 | `commands/report.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 9 | `commands/setup-alert.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 10 | `commands/write-content.md` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 11 | `SKILL.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 12 | `commands/audit-domain.md` | — | UNCLASSIFIED | `missing-argument-hint-field` | fixed — upstream, not via our PR |  |
| 13 | `commands/optimize-meta.md` | — | UNCLASSIFIED | `missing-argument-hint-field` | fixed — upstream, not via our PR |  |
| 14 | `commands/wiki-lint.md` | — | UNCLASSIFIED | `missing-argument-hint-field` | fixed — upstream, not via our PR | #11 |
| 15 | `commands/p2-review.md` | — | UNCLASSIFIED | `missing-argument-hint-field` | fixed — upstream, not via our PR |  |
| 16 | `hooks/hooks.json` | — | UNCLASSIFIED | `stop-hook-auto-appends-critical-veto-ite` | fixed — upstream, not via our PR |  |
| 17 | `commands/geo-drift-check.md` | — | UNCLASSIFIED | `experimental-v9-0-label-in-claude-md-but` | fixed — upstream, not via our PR |  |
| 18 | `CLAUDE.md` | — | BUG-broken-reference | `broken-reference` | fixed — upstream, not via our PR |  |
| 19 | `cross-cutting/content-quality-auditor/SKILL.md` | — | UNCLASSIFIED | `both-auditor-class-skills-carry-the-iden` | fixed — applied separately | #12 |
| 20 | `cross-cutting/domain-authority-auditor/SKILL.md` | — | UNCLASSIFIED | `both-auditor-class-skills-carry-the-iden` | fixed — applied separately | #12 |
| 21 | `SKILL.md` | — | UNCLASSIFIED | `metadata-geo-relevance-values-are-hardco` | fixed — upstream, not via our PR |  |
| 22 | `research/competitor-analysis/SKILL.md` | — | UNCLASSIFIED | `include-a-scraping-legality-note-verify` | fixed — applied separately | #12 |
| 23 | `optimize/internal-linking-optimizer/SKILL.md` | — | UNCLASSIFIED | `include-a-scraping-legality-note-verify` | fixed — applied separately | #12 |
| 24 | `hooks/hooks.json` | — | UNCLASSIFIED | `the-filechanged-hook-matcher-hot-cache-m` | fixed — upstream, not via our PR |  |
| 25 | `commands/report.md` | — | UNCLASSIFIED | `cross-project-mode-is-described-but-the` | fixed — upstream, not via our PR |  |
| 26 | `build/seo-content-writer/SKILL.md` | — | UNCLASSIFIED | `banned-vocabulary-list-crucial-robust-le` | fixed — applied separately | #12 |
| 27 | `monitor/performance-reporter/SKILL.md` | — | UNCLASSIFIED | `11-step-workflow-integrates-core-eeat-an` | fixed — applied separately | #12 |
| 28 | `cross-cutting/memory-management/SKILL.md` | — | UNCLASSIFIED | `gdpr-art-17-deletion-flow-is-documented` | fixed — applied separately | #12 |
| 29 | `All research skills` | — | UNCLASSIFIED | `the-next-best-skill-section-uses-markdow` | fixed — upstream, not via our PR |  |
| 30 | `commands/p2-review.md` | — | UNCLASSIFIED | `tombstone-rule-states-tombstone-review-2` | fixed — upstream, not via our PR |  |
| 31 | `commands/sync-versions.md` | — | UNCLASSIFIED | `step-5-says-to-verify-all-3-cross-agent` | fixed — upstream, not via our PR |  |
| 32 | `optimize/technical-seo-checker/SKILL.md` | — | UNCLASSIFIED | `llm-crawler-handling-section-names-speci` | fixed — applied separately | #12 |
| 33 | `build/schema-markup-generator/SKILL.md` | — | UNCLASSIFIED | `ftc-disclosure-note-for-aggregaterating` | fixed — applied separately | #12 |
| 34 | `SKILL.md` | — | UNCLASSIFIED | `save-results-section-is-identical-across` | fixed — upstream, not via our PR |  |
| 35 | `hooks/hooks.json` | 36 | UNCLASSIFIED | `userpromptsubmit-hook-line-36-fires-on-e` | fixed — upstream, not via our PR |  |

## Findings introduced since audit

These findings appear in the re-audit but were not in the original audit. They may be true regressions (new commits introduced them) or artifacts of scoring drift.

| # | File | Line | Rule | Pattern | Description |
|---|------|------|------|---------|-------------|
| 1 | `commands/setup-alert.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration; tools used during execution are undeclared |
| 2 | `commands/setup-alert.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 3 | `commands/keyword-research.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration |
| 4 | `commands/keyword-research.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 5 | `commands/report.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration |
| 6 | `commands/report.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 7 | `commands/write-content.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration |
| 8 | `commands/write-content.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 9 | `commands/check-technical.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 10 | `commands/generate-schema.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 11 | `commands/generate-schema.md` | — | R01 | `vague-quantifier-appropriate` | Vague quantifier 'appropriate' used without specifying a concrete selection criterion |
| 12 | `commands/audit-domain.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration |
| 13 | `commands/audit-domain.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 14 | `commands/audit-page.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 15 | `commands/audit-page.md` | — | R01 | `vague-quantifier-some` | Vague quantifier 'Some' in 'Some EEAT items' without specifying which items or a threshold count |
| 16 | `commands/optimize-meta.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration |
| 17 | `commands/optimize-meta.md` | — | R15 | `no-empty-input-handling` | Command has required parameter(s) with no documented behavior for empty or missing input |
| 18 | `commands/p2-review.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration |
| 19 | `commands/p2-review.md` | — | R14 | `multi-step-no-numbered-steps` | Multi-step evaluation procedure uses bullet points (MET/PARTIAL/UNMET) instead of numbered steps |
| 20 | `commands/contract-lint.md` | — | R14 | `multi-step-no-numbered-steps` | Multi-step lint workflow uses labeled sections without sequential step numbering |
| 21 | `commands/wiki-lint.md` | — | R12 | `missing-allowed-tools` | Command has no allowed-tools declaration |
| 22 | `CLAUDE.md` | — | R34 | `missing-test-command` | CLAUDE.md has no test command entry; R34 requires a documented way to run the test suite |
| 23 | `cross-cutting/domain-authority-auditor/SKILL.md` | — | R01 | `vague-quantifier-some-relevant` | 3 vague quantifiers: 'Some items' (×2) and 'niche-relevant'; replace with explicit thresholds or criteria |
| 24 | `cross-cutting/content-quality-auditor/SKILL.md` | — | R01 | `vague-quantifier-sufficient-some` | 2 vague quantifiers: 'sufficient data' and 'Some EEAT items'; replace with concrete thresholds |
| 25 | `optimize/internal-linking-optimizer/SKILL.md` | — | R01 | `vague-quantifier-relevant` | 2 vague quantifiers: 'topic-relevant link opportunities' and 'Add relevant links' |
| 26 | `monitor/backlink-analyzer/SKILL.md` | — | R01 | `vague-quantifier-relevant` | 2 vague quantifiers including 'Relevant audience'; replace with concrete criteria |
| 27 | `cross-cutting/memory-management/SKILL.md` | — | R01 | `vague-quantifier-relevant` | Vague quantifier 'relevant' in 'locate relevant WARM files' |
| 28 | `monitor/alert-manager/SKILL.md` | — | R01 | `vague-quantifier-relevant` | Vague quantifier 'relevant' in 'For each relevant category' |
| 29 | `build/schema-markup-generator/SKILL.md` | — | R01 | `vague-quantifier-appropriate` | Vague quantifier 'appropriate' in 'Selects appropriate Schema.org types' |
| 30 | `optimize/on-page-seo-auditor/SKILL.md` | — | R01 | `vague-quantifier-relevant` | Vague quantifier 'relevant' in 'on-page-relevant items' |
| 31 | `optimize/technical-seo-checker/SKILL.md` | — | R01 | `vague-quantifier-properly` | Vague quantifier 'properly' in 'properly crawling' |
| 32 | `hooks/hooks.json` | — | CC-unrecognized-hook-event | `unrecognized-hook-event` | FileChanged hook event is not in the NLPM conventions hook-events list (SessionStart, UserPromptSubmit, PostToolUse, Stop) |

