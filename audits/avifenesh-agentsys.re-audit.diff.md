# Re-Audit: avifenesh/agentsys

**Date**: 2026-04-24  |  **Before**: `unknown` (97/100)  |  **After**: `fd7f8f6` (95/100)

## Summary

| Outcome | Count |
|---------|------:|
| fixed — our PR merged | 3 |
| fixed — upstream, not via our PR | 9 |
| newly introduced (regressions) | 2 |

## Original findings — verification

| # | File | Line | Rule | Pattern | Outcome | PR |
|---|------|------|------|---------|---------|----|
| 1 | `.kiro/skills/web-auth/SKILL.md` | — | BUG-broken-reference | `hardcoded-path` | fixed — upstream, not via our PR | #337 |
| 2 | `.kiro/skills/web-browse/SKILL.md` | — | BUG-unclassified | `same-hardcoded-users-avifen-agentsys-pat` | fixed — upstream, not via our PR | #338 |
| 3 | `package.json` | — | SEC-unknown | `prepare-script-installs-git-hooks-silent` | fixed — our PR merged | #339 |
| 4 | `scripts/dev-install.js` | — | SEC-unknown | `npm-install-production-with-no-registry` | fixed — upstream, not via our PR |  |
| 5 | `package.json` | — | SEC-unknown | `version-script-uses-git-add-a` | fixed — our PR merged | #339 |
| 6 | `package.json` | — | SEC-unknown | `unpinned-dependency-versions` | fixed — our PR merged | #339 |
| 7 | `.kiro/skills/web-auth/SKILL.md` | — | SEC-unknown | `hardcoded-users-avifen-home-path` | fixed — upstream, not via our PR | #337 |
| 8 | `.kiro/skills/web-browse/SKILL.md` | — | SEC-unknown | `hardcoded-users-avifen-home-path` | fixed — upstream, not via our PR | #338 |
| 9 | `meta/skills/maintain-cross-platform/SKILL.md` | — | UNCLASSIFIED | `skill-exceeds-500-lines-1000-lines-the-e` | fixed — upstream, not via our PR |  |
| 10 | `.kiro/skills/orchestrate-review/SKILL.md` | 63 | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 11 | `.kiro/skills/repo-intel/SKILL.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 12 | `.kiro/skills/sync-docs/SKILL.md` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |

## Findings introduced since audit

These findings appear in the re-audit but were not in the original audit. They may be true regressions (new commits introduced them) or artifacts of scoring drift.

| # | File | Line | Rule | Pattern | Description |
|---|------|------|------|---------|-------------|
| 1 | `.kiro/skills/orchestrate-review/SKILL.md` | — | R14 | `missing-output-format` | No dedicated Output Format section; the skill's outputs to orchestrating callers (phase completion state, AskUserQuestion interaction, Review Queue schema) are documented only implicitly inside code examples. |
| 2 | `meta/skills/maintain-cross-platform/SKILL.md` | 900 | R07 | `vague-quantifier-relevant` | Vague quantifier 'relevant' in instruction text: 'Add to relevant section (Validation Suite, Installation, etc.)' — leaves ambiguity about which section to update. |

