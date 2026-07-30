---
artifact: agents/recon.md
type: agent
min_score: 80
---

# recon — suite spec (vibe-31 / E3.6)

Source: F3.x recon (grill review engine): repository reconnaissance before dimension reviews. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "survey this repository before the deep review"
- "map the codebase for the review agents"
- "what areas should the reviewers focus on"
- "run recon on this project"
- "build the review context for this repo"

## Does Not Trigger On
- "review the error handling in this file"      (a dimension review, not recon)
- "write a new module"                           (creation)
- "deploy the reviewed branch"                   (ops action)

## Output Contains
- "## [Agent: vibe-suite:recon] Findings"
- a severity classification set

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
