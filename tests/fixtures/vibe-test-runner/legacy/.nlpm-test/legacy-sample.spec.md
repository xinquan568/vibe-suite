---
artifact: agents/local.md
type: agent
min_score: 80
---

# legacy-sample — the legacy-directory read-compat fixture (vibe-31)

Lives in `.nlpm-test/` deliberately: the runner must DISCOVER it there and run it as-is
(F4.5 read-compat; never renamed, new specs go to `.vibe-test/`).

## Triggers On
- "the legacy fixture needs a resolvable local artifact"
- "run the legacy read-compat check"
- "invoke the local fixture agent"
- "confirm the legacy directory is discovered"
- "test the nlpm-test compatibility path"

## Does Not Trigger On
- "migrate legacy specs to the new directory"   (migration, not evaluation)
- "write a new spec"                            (authoring)
- "review this blog post"                       (unrelated domain)

## Output Contains
- "legacy"
- "local"

## Frontmatter Valid
- description present and trigger-style ("Use when...")
