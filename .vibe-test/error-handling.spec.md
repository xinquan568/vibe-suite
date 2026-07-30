---
artifact: agents/error-handling.md
type: agent
min_score: 80
---

# error-handling — suite spec (vibe-31 / E3.6)

Source: F3.x error-handling (grill review engine): failure-path review dimension. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "review the error handling in this change"
- "what happens when this call fails"
- "check for swallowed exceptions"
- "are failures propagated or hidden here"
- "audit the retry and timeout behavior"

## Does Not Trigger On
- "review the security of this endpoint"         (the security dimension)
- "add a try/except to this function"            (authoring)
- "why did production error last night"          (incident ops)

## Output Contains
- "## [Agent: vibe-suite:error-handling] Findings"
- a severity classification set

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
