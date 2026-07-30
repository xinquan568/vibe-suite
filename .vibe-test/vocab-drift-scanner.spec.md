---
artifact: agents/vocab-drift-scanner.md
type: agent
min_score: 80
---

# vocab-drift-scanner — suite spec (vibe-31 / E3.6)

Source: F4.6: registry-free advisory vocabulary-drift scan (judgment clustering, never penalizes). This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "scan this corpus for vocabulary drift"
- "are there synonyms competing for one concept here"
- "cluster likely-synonymous verbs across these files"
- "advisory vocab check before adopting R51"
- "is the registry missing any drift pairs"

## Does Not Trigger On
- "apply R51 penalties"                          (the scoring lane)
- "seed the vocabulary registry"                 (vocab init authoring)
- "rename the drifted terms"                     (mutation)

## Output Contains
- drift candidate clusters with dispositions
- an advisory-only statement (no penalty)

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
