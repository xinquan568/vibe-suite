---
artifact: agents/architecture.md
type: agent
min_score: 80
---

# architecture — suite spec (vibe-31 / E3.6)

Source: F3.x architecture (grill review engine): structural/design review dimension. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "review the architecture of this change"
- "does this design fit the existing structure"
- "check for layering violations in this diff"
- "assess coupling introduced by this PR"
- "is this abstraction in the right place"

## Does Not Trigger On
- "format this file"                             (mechanical, not design)
- "review the test coverage"                     (the testing dimension)
- "draw me an architecture diagram"              (authoring, not review)

## Output Contains
- "## [Agent: vibe-suite:architecture] Findings"
- a severity classification set

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
