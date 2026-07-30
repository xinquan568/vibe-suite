---
artifact: agents/scanner.md
type: agent
min_score: 80
---

# scanner — suite spec (vibe-31 / E3.6)

Source: shipped agents/scanner.md (F4.1): read-only NL-artifact discovery for /vibe-suite:ls. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "inventory the NL artifacts in this repo"
- "list every prompt and agent file here"
- "discover the plugin components in this project"
- "what natural-language artifacts does this repo ship"
- "scan this directory for NL programming files"

## Does Not Trigger On
- "score these artifacts"                        (the scorer's lane)
- "scan the plugin for security risks"           (security-scanner)
- "delete unused artifacts"                      (mutation; scanner is read-only)

## Output Contains
- discovery categories A-E
- a grouped artifact listing

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
