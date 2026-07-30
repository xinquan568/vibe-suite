---
artifact: agents/security-scanner.md
type: agent
min_score: 80
---

# security-scanner — suite spec (vibe-31 / E3.6)

Source: F5.1/E3.9: NL-plugin security scan over hooks, scripts, MCP configs, injection surfaces. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "scan this plugin for security risks"
- "is this plugin safe to install"
- "check the hooks and scripts for dangerous patterns"
- "audit the MCP configuration of this plugin"
- "find prompt-injection surfaces in this artifact set"

## Does Not Trigger On
- "review this code diff for security"           (the security review dimension)
- "fix the dangerous hook"                       (mutation)
- "scan for vocabulary drift"                    (different scanner)

## Output Contains
- an execution-surface inventory
- a risk-level classification

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
