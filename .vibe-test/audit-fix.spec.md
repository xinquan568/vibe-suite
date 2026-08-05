---
artifact: codex-src/audit-fix/SKILL.md
type: skill
min_score: 80
---

# audit-fix — codex-src source spec (vibe-53 / E7.1)

Source: F9.6(d) reverse-delegation source set — the bounded Claude-audits, Codex-fixes, Claude-verifies loop. This spec states the contract before the
artifact exists (NL-TDD RED); the author inherits these expectations.

## Triggers On

- "audit and fix this" — findings resolved, not just reported
- automated quality enforcement after writing a feature
- a pre-commit cycle bounded by rounds
- recurring patterns needing audit, fix, and verification together
- driving remaining findings to closure with Claude verdicts

## Does Not Trigger On

- reporting findings without fixing (audit's job)
- a one-off fix with a known cause (claude-debug's job)
- verification alone of externally-made fixes (verify's job)

## Output Contains

- per-finding closure verdicts drawn from FIXED, NOT FIXED, PARTIAL, REGRESSED
- a final report with status counts, fixed and remaining tables, and git diff --stat

## Frontmatter Valid

- name matches the directory name and description is non-empty
