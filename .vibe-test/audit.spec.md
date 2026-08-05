---
artifact: codex-src/audit/SKILL.md
type: skill
min_score: 80
---

# audit — codex-src source spec (vibe-53 / E7.1)

Source: F9.6(d) reverse-delegation source set — Codex requests a read-only 5- or 9-dimension audit from Claude. This spec states the contract before the
artifact exists (NL-TDD RED); the author inherits these expectations.

## Triggers On

- an independent quality check after writing a feature
- "have Claude audit this"
- a pre-commit or pre-PR findings pass
- the first step of a fix cycle
- choosing 5-dimension mini or 9-dimension full depth

## Does Not Trigger On

- fixing the findings (audit-fix's cycle or claude-implement)
- verifying earlier findings closed (verify's job)
- a free-form second opinion without dimensions (claude-review's job)

## Output Contains

- a findings table with file:line, severity, dimension, issue, and fix
- a severity summary and an explicit CLEAN statement when clean

## Frontmatter Valid

- name matches the directory name and description is non-empty
