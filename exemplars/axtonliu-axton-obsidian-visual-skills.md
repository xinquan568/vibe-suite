---
slug: axtonliu-axton-obsidian-visual-skills
repo: axtonliu/axton-obsidian-visual-skills
audited: 2026-05-13
commit_sha: 1265976d9746a84858b4b7b42fb86a215aa93de9
score: 90
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: axtonliu/axton-obsidian-visual-skills

**Score**: 90/100  |  **Date**: 2026-05-13  |  **Commit**: `1265976d9746a84858b4b7b42fb86a215aa93de9`

Three Obsidian visualization skills (Excalidraw, Mermaid, Canvas) notable for bilingual trigger lists, complete JSON output templates with field-level constraints, and bad/good syntax pattern tables that prevent parser errors at generation time.

## Per-rule evidence

### R04 — Description as trigger

`excalidraw-diagram`'s description goes beyond action phrases: it ends with an explicit `Triggers on` list enumerating 11 trigger strings across Chinese and English, removing any ambiguity about when the skill fires.

> From `excalidraw-diagram/SKILL.md:3`:
>
> ```
> description: Generate Excalidraw diagrams from text content. Supports three output modes -
> Obsidian (.md), Standard (.excalidraw), and Animated (.excalidraw with animation order).
> Triggers on "Excalidraw", "画图", "流程图", "思维导图", "可视化", "diagram",
> "标准Excalidraw", "standard excalidraw", "Excalidraw动画", "动画图", "animate".
> ```

`mermaid-visualizer` and `obsidian-canvas-creator` both include "Use when..." clauses with concrete invocation scenarios ("users ask to visualize concepts, create flowcharts, or make diagrams from text"; "user mentions 'Obsidian Canvas' or similar visualization tools"), rather than summarizing what the skill is.

What separates this from a mediocre trigger description: the exhaustive explicit list means Claude matches the Chinese input "流程图" to this skill with the same confidence as the English "diagram", rather than relying on semantic inference.

### R05 — Body length

All three skills stay comfortably under the 500-line ceiling: `excalidraw-diagram` at 477 lines, `mermaid-visualizer` at 277, `obsidian-canvas-creator` at 212. The longer `excalidraw-diagram` stays under the cap by offloading the full element-type catalog to `references/excalidraw-schema.md` and pointing to it.

> From `excalidraw-diagram/SKILL.md:287`:
>
> ```
> See [references/excalidraw-schema.md](references/excalidraw-schema.md) for all element types.
> ```

Rather than embedding a complete schema reference inline (which would push the file well past 500 lines), the skill contains the required fields with hard constraints and defers the remainder. This demonstrates the intended split: behavioral rules stay in SKILL.md; reference data lives in a companion file.

### R06 — Code examples must be runnable

`excalidraw-diagram` shows all three output formats as complete, importable structures — not pseudocode. Each includes the exact fields required, the exact disallowed fields, and the exact defaults.

> From `excalidraw-diagram/SKILL.md:228-253`:
>
> ```json
> {
>   "id": "unique-id",
>   "type": "rectangle",
>   "x": 100, "y": 100,
>   "width": 200, "height": 50,
>   "angle": 0,
>   "strokeColor": "#1e1e1e",
>   "backgroundColor": "transparent",
>   "fillStyle": "solid",
>   "strokeWidth": 2,
>   "strokeStyle": "solid",
>   "roughness": 1,
>   "opacity": 100,
>   "groupIds": [],
>   "roundness": {"type": 3},
>   "seed": 123456789,
>   "version": 1,
>   "isDeleted": false,
>   "boundElements": null,
>   "updated": 1,
>   "link": null,
>   "locked": false
> }
> ```

The comment `(do NOT add extra fields like frameId, index, versionNonce, rawText -- they may cause issues on excalidraw.com. boundElements must be null not [], updated must be 1 not timestamps)` encodes failure modes that can only be known from operating the tool — exactly the kind of constraint that belongs in a skill, not a README.

`mermaid-visualizer` follows the same principle for its Common Patterns section: every pattern is a real `mermaid` code block that renders, not a description of what a block might look like.

### R07 — Scope note when related artifacts exist

All three skills carry explicit "load this reference when" notes for their companion reference documents, and the audit confirmed all four referenced paths exist on disk.

> From `obsidian-canvas-creator/SKILL.md:185-193`:
>
> ```
> ## Reference Documents
>
> - **Canvas Specification**: `references/canvas-spec.md` - Complete JSON Canvas format specification
> - **Layout Algorithms**: `references/layout-algorithms.md` - Detailed positioning algorithms for both layout types
>
> Load these references when:
> - Need specification details for edge cases
> - Implementing complex layout calculations
> - Troubleshooting validation errors
> ```

The "Load these references when:" phrasing is precise: it tells Claude the conditions under which the reference is worth loading, rather than a vague "see also." This matches the intent of R07 — help Claude decide which artifact to use without requiring it to guess.

### R08 — Patterns over theory

`mermaid-visualizer`'s "Critical Syntax Rules" section is pure pattern-over-theory: each rule is a named failure mode, a bad/good pair in actual syntax, and a one-line explanation of what goes wrong.

> From `mermaid-visualizer/SKILL.md:100-108`:
>
> ```
> ### Rule 1: Avoid List Syntax Conflicts
> ❌ WRONG: [1. Perception]       → Triggers "Unsupported markdown: list"
> ✅ RIGHT: [1.Perception]         → Remove space after period
> ✅ RIGHT: [① Perception]         → Use circled numbers (①②③④⑤⑥⑦⑧⑨⑩)
> ✅ RIGHT: [(1) Perception]       → Use parentheses
> ✅ RIGHT: [Step 1: Perception]   → Use "Step" prefix
>
> ### Rule 2: Subgraph Naming
> ❌ WRONG: subgraph AI Agent Core  → Space in name without quotes
> ✅ RIGHT: subgraph agent["AI Agent Core"]  → Use ID with display name
> ```

Rather than stating "subgraphs must be correctly named," the skill demonstrates the exact wrong input, the exact error it causes, and multiple valid alternatives. This is the pattern-over-theory ideal: Claude can apply Rule 1 mechanically — check for `[digit. space]` pattern, rewrite to one of four alternatives — without needing to understand the Mermaid parser's list-detection logic.

`excalidraw-diagram` applies the same discipline to font size: hard numeric floors per text role (title 20px min, body 16px min, absolute floor 14px) instead of abstract guidance about readability.

## Worth adopting

**Pattern: Trigger-word dispatch table.** Evidence: `excalidraw-diagram/SKILL.md:18-21`. The skill maps sets of trigger phrases to named output modes in a table with four columns (trigger words, output mode, file format, use case), then references that table throughout the workflow. Why it would be a useful rule: when a skill supports multiple distinct behaviors, a dispatch table makes the routing logic explicit in one place — a skill description listing 10+ triggers without a dispatch table leaves Claude to infer which phrases select which behavior, producing inconsistent mode selection.
