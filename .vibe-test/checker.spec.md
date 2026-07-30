---
artifact: agents/checker.md
type: agent
min_score: 80
---

# checker — suite spec (vibe-31 / E3.6)

Source: shipped agents/checker.md (F4.3): cross-component consistency for /vibe-suite:check. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "check cross-component consistency of this plugin"
- "find broken references between commands and agents"
- "do these artifacts contradict each other"
- "detect terminology drift across this corpus"
- "which skills are orphaned in this plugin"

## Does Not Trigger On
- "score each artifact's quality"               (the scorer)
- "validate the manifest against disk in CI"     (bin/vibe-check)
- "rename the drifted terms"                     (mutation)

## Output Contains
- "Verdict: CLEAN |"
- the engine-composed issue report

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
