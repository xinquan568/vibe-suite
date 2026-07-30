---
artifact: agents/security.md
type: agent
min_score: 80
---

# security — suite spec (vibe-31 / E3.6)

Source: F3.x security (grill review engine): security review dimension. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "review this change for security issues"
- "check for injection risks in this diff"
- "is user input validated on this path"
- "audit the auth checks in this PR"
- "look for secrets committed in this change"

## Does Not Trigger On
- "scan the plugin for dangerous hooks"          (security-scanner, plugin surface)
- "harden the server configuration"              (ops action)
- "review the naming in this module"             (style, not security)

## Output Contains
- "## [Agent: vibe-suite:security] Findings"
- a severity classification set

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
