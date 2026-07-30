---
artifact: agents/testing.md
type: agent
min_score: 80
---

# testing — suite spec (vibe-31 / E3.6)

Source: F3.x testing (grill review engine): test-coverage review dimension. This spec restates the proposal's expectations as a test; a later
author of the artifact inherits these, not inventions.

## Triggers On
- "review the tests in this change"
- "is this diff adequately covered by tests"
- "what edge cases are untested here"
- "check whether the new code path has a test"
- "assess the assertion quality in these tests"

## Does Not Trigger On
- "run the test suite"                           (execution, not review)
- "evaluate NL artifacts against their specs"    (the tester agent)
- "write tests for this module"                  (authoring)

## Output Contains
- "## [Agent: vibe-suite:testing] Findings"
- a severity classification set

## Frontmatter Valid
- description present and trigger-style ("Use when...")
- a model tier alias (never a pinned model id)
- a tools list
