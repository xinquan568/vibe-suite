---
artifact: agents/vague-scanner.md
type: agent
min_score: 80
---

# vague-scanner — suite spec (vibe-31 / E3.6)

Source: shipped agents/vague-scanner.md (F4.2): mechanical R01 recount cross-check. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "recount the vague quantifiers in these files"
- "cross-check the engine's R01 counts"
- "how many vague words does this skill use"
- "verify the vague-quantifier penalty"
- "scan for vague quantifier words at token boundaries"

## Does Not Trigger On
- "run the full scoring rubric"                  (the scorer)
- "rewrite the vague sentences"                  (authoring)
- "scan for security issues"                     (different scanner)

## Output Contains
- per-file vague-word counts
- a zero-penalty advisory on any disagreement

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
