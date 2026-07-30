---
artifact: agents/scorer.md
type: agent
min_score: 80
---

# scorer — suite spec (vibe-31 / E3.6)

Source: shipped agents/scorer.md (F4.2): deterministic scoring narrator for /vibe-suite:score. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "score the NL artifacts in this repository"
- "what is the quality score of this skill"
- "run the scoring rubric over these agents"
- "which penalties apply to this command file"
- "give me per-file scores with fixes"

## Does Not Trigger On
- "count the vague words only"                   (vague-scanner's recount)
- "check cross-component consistency"            (the checker)
- "raise this file's score by editing it"       (mutation)

## Output Contains
- per-file scores
- findings localized to line numbers with Fix text

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
