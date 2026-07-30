---
artifact: agents/tester.md
type: agent
min_score: 80
---

# tester — suite spec (vibe-31 / E3.6)

Source: F4.5 (this item, spec-before-artifact): the NL-TDD spec evaluator for /vibe-suite:test. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "evaluate these artifacts against their specs"
- "run the NL test specs in .vibe-test"
- "does this agent satisfy its spec"
- "predict whether these queries trigger the skill"
- "check the spec's min_score against the actual score"

## Does Not Trigger On
- "review the test coverage of this diff"        (the testing review dimension)
- "write a spec for this agent"                  (authoring)
- "run the Python unit tests"                    (code tests, not NL specs)

## Output Contains
- "N/M checks" per-spec results
- "artifact missing (RED)" for absent artifacts

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
