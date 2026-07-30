---
artifact: agents/spec-researcher.md
type: agent
min_score: 80
---

# spec-researcher — suite spec (vibe-31 / E3.6)

Source: F4.7/E3.8: per-overlay tool-convention researcher (first-party sources, tagged gap report). This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "research the current claude hooks spec"
- "sync the codex overlay against first-party docs"
- "what changed in the antigravity conventions"
- "produce a FIX/REMOVE/ADD gap report for this overlay"
- "verify our conventions against the official docs"

## Does Not Trigger On
- "apply the overlay corrections"                (spec-sync's apply step)
- "write a new conventions skill"                (authoring)
- "check hook event casing in this repo"         (bin/vibe-check)

## Output Contains
- a tagged gap report (FIX/REMOVE/ADD/CONFIRM/RESOLVED)
- first-party source citations

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
