---
artifact: agents/edge-cases.md
type: agent
min_score: 80
---

# edge-cases — suite spec (vibe-31 / E3.6)

Source: F3.x edge-cases (grill review engine): boundary-condition review dimension. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "what edge cases does this change miss"
- "review the boundary conditions in this diff"
- "check the empty-input behavior here"
- "what happens at the limits of this loop"
- "probe this parser for corner cases"

## Does Not Trigger On
- "review the error handling"                    (the error-handling dimension)
- "add boundary tests"                           (authoring)
- "benchmark this function"                      (performance ops)

## Output Contains
- "## [Agent: vibe-suite:edge-cases] Findings"
- a severity classification set

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
