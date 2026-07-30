---
artifact: agents/ghost.md
type: agent
min_score: 80
---

# ghost — the durable missing-artifact fixture (vibe-31)

The artifact is absent BY CONSTRUCTION and is never to be created: this spec pins the
runner's missing-artifact RED behavior (F4.5: "Missing artifact → RED").

## Triggers On
- "haunt the test suite"
- "verify the runner reports RED for me"
- "check the missing artifact path"
- "exercise the TDD start state"
- "run the ghost agent"

## Does Not Trigger On
- "run the real test suite"        (adjacent: the runner itself, not this fixture)
- "create a ghost agent"           (creation, not evaluation)
- "delete failing specs"           (ops action)

## Output Contains
- "artifact missing (RED)"
- "agents/ghost.md"

## Frontmatter Valid
- description present and trigger-style ("Use when...")
