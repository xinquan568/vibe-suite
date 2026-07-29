---
name: writing-skills
description: Use when creating, improving, or reviewing SKILL.md files for any tool — descriptions that trigger reliably, body structure that teaches effectively, and progressive disclosure via references/.
---

# Writing Skills

> Scope: SKILL.md is a cross-tool open standard (agentskills.io). One and the
> same file runs unchanged under Claude Code (`.claude/skills/`), under Codex
> CLI (`.agents/skills/`), and under Antigravity (`.agent/skills/`). The spec
> requires exactly two frontmatter
> fields: `name` and `description`. Per-tool extras belong in overlay skills —
> Claude Code adds `model:` and `allowed-tools:`; Codex uses an
> `agents/openai.yaml` sidecar — see
> [conventions-claude](../conventions-claude/SKILL.md),
> [conventions-codex](../conventions-codex/SKILL.md), and
> [conventions-antigravity](../conventions-antigravity/SKILL.md).
> For writing agents see [writing-agents](../writing-agents/SKILL.md); for
> plugin architecture see [writing-plugins](../writing-plugins/SKILL.md).

## 1. The Description is Everything

The `description` field is the load-trigger mechanism — it is NOT a summary.
The model decides whether to load the skill by matching the user's words
against it.

A label-style description ("helpful for React") scores around **55**; a
trigger-phrase description enumerating real use cases — building components,
debugging re-renders, memoization hooks, dependency arrays — scores around
**95**.

### Description Checklist

| Criterion | Test |
|---|---|
| **3+** trigger phrases | Count the distinct comma-separated action phrases |
| Action-oriented | Opens with "Use when..." or "How to..." |
| Tool/framework named | The tool or framework name appears explicitly in the text |
| Matches real queries | A user's actual question would contain a trigger word |

### Trigger Phrase Construction

Work backward from how users actually phrase their questions:

| Real user query | Trigger phrase |
|---|---|
| "Why does this keep re-rendering?" | debugging re-renders |
| "Should I memoize this?" | memo/callback optimization |
| "My effect runs in a loop" | dependency arrays |
| "Help me build a new component" | building components |

Bright line: if you cannot list **3** real user queries that would match the
description, rewrite the description.

## 2. Body Structure

### Section Order

Six slots, in this order:

1. Scope note — only if related skills exist; it routes between this skill and
   that skill.
2. Most-commonly-needed patterns — the material behind 80% of asks goes first.
3. Decision matrices — grids resolving A-vs-B choices.
4. Worked examples — scored before/after pairs.
5. Common mistakes — the anti-pattern catalog.
6. References — links for deep dives.

### Heading Rules

- H1 = the skill title; exactly one per file.
- H2 = major sections, numbered as `## 1. Name`.
- H3 = subsections under an H2.
- Never skip levels — no H2 followed directly by an H4.
- Bad/good example headings carry a parenthetical reason, e.g.
  "Bad (breaks on concurrent requests)" for shared mutable global state versus
  the request-scoped local-state fix.

### Code Examples

Three rules:

1. Runnable — real code, not pseudocode.
2. Contextual — enough surrounding code to show where it goes.
3. Annotated — comment only the critical line, not every line.

Every code example shows the problem first, then the solution.

## 3. Progressive Disclosure

Keep SKILL.md under **500 lines**. Depth goes to the file system, not the main
file:

```
skills/<domain>/<skill>/
├── SKILL.md          # core patterns, < 500 lines
├── references/       # deep dives, edge cases, full API docs
├── examples/         # working code samples (basic + advanced configs)
└── scripts/          # utility scripts (e.g. a validation script)
```

### When to Extract to references/

| Content | Decision |
|---|---|
| The top-5 patterns everyone needs | Keep in SKILL.md |
| Full API reference (**50+** entries) | Move to references/ |
| Edge cases affecting < **5%** of users | Move to references/ |
| Configuration matrix (**20+** options) | Move to references/ |
| Quick decision table (< **10** rows) | Keep in SKILL.md |

## 4. Worked Example: Improving a Skill

A docker-helper skill scored **55/100** with five defects:

1. Description was a label with **0** trigger phrases.
2. Body restated training-known theory — what the tool is, a basic command
   list.
3. No problem/solution code examples.
4. No decision matrices.
5. No scope note.

The body amounted to a definition sentence, bare command bullets, and one-line
section stubs.

After the rewrite it scored **92/100**:

- The description gained **8** trigger phrases — Dockerfile writing,
  container-network debugging, image-size optimization via multi-stage builds,
  Compose service configuration — plus a trailing sentence listing covered
  topics (build cache, volume mounts, health checks, compose profiles).
  The frontmatter `name` and `version` stayed unchanged.
- A scope note declared CLI/Dockerfile/Compose coverage and delegated
  Kubernetes to a separate skill reference.
- The theory was replaced with a before/after Dockerfile pair — a bloated
  single-stage build versus a multi-stage slim build (~88% size reduction) —
  with a key-changes line, plus a base-image decision matrix listing an image
  and size per use case.

Score deltas, attributed:

| Change | Delta |
|---|---|
| Description: 0 → 8 trigger phrases | **+37** |
| Scope note added | **+5** |
| Theory replaced by problem/solution examples | **+25** |
| Decision matrix added | **+10** |
| Training-known content removed (−15 lines) | **+5** for conciseness |

## 5. Common Mistakes

| Mistake | Harm | Fix |
|---|---|---|
| Description is a feature list | Queries cannot match it | Rewrite as "Use when…" trigger phrases |
| Body teaches theory | Wastes tokens on training-known content | Show patterns and decisions, not definitions |
| Over **500 lines** | Context bloat plus linter penalty | Extract to references/; keep only the core |
| No scope note | Cannot route between related skills | Add a scope note with related-skill refs |
| Pseudocode examples | Not actionable or copy-pasteable | Runnable code with context |
| Equal-weight sections | Buries the top content | Lead with the 80% patterns; edge cases to references/ |

## 6. Quality Checklist

- [ ] At least **3** specific trigger phrases in the description
- [ ] The description opens with "Use when..." or "How to..."
- [ ] A scope note exists whenever related skills do
- [ ] Numbered H2 sections, with H3s nested under them
- [ ] Each code example pairs a problem with its solution
- [ ] A-vs-B choices get decision tables
- [ ] Fewer than **500** total lines
- [ ] Training-known content absent
- [ ] At least **1** worked example with a before/after
