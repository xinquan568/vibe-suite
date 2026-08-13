---
slug: ooiyeefei-ccc
repo: ooiyeefei/ccc
audited: 2026-05-13
commit_sha: 51ecc703ffbbf02ee83b3cd79e32652937109c4b
score: 96
exemplifies:
  - R04
  - R07
  - R08
  - R09
  - R12
  - R17
---

# Exemplar: ooiyeefei/ccc

**Score**: 96/100  |  **Date**: 2026-05-13  |  **Commit**: `51ecc703ffbbf02ee83b3cd79e32652937109c4b`

A multi-plugin skills collection (product management, UAT testing, Excalidraw diagram generation, landing page GTM) notable for description fields that pack 6–12 quoted trigger phrases and skill bodies built almost entirely from lookup tables rather than prose.

## Per-rule evidence

### R04 — Description is a trigger, not a summary

The `product-management` skill description strings together 12 quoted user phrases, ensuring the skill fires on every natural phrasing of the domain — not just the canonical "product management" invocation.

> Real quote from `plugins/product-management/skills/product-management/SKILL.md:2–3`:
>
> ```
> description: This skill should be used when the user asks to "analyze my product",
> "research competitors", "find feature gaps", "create feature request",
> "prioritize backlog", "generate PRD", "plan roadmap",
> "what should we build next", "competitive analysis", "gap analysis",
> "sync issues", or mentions product management workflows.
> ```

Twelve quoted phrases in 156 characters of description — not a one-liner summary but a trigger map. The `uat-testing` SKILL.md uses the same technique with 6 quoted phrases plus a paraphrase fallback, and `excalidraw` packs 8 triggers. Every skill in this repo treats the description field as a dispatch table, not a label.

---

### R07 — Scope note when related skills exist

The product-management SKILL.md includes a dedicated integration section that names the adjacent skill, describes the boundary, and shows the handoff mechanism — so Claude knows exactly where PM ends and implementation begins.

> Real quote from `plugins/product-management/skills/product-management/SKILL.md:163–174`:
>
> ```
> ## Integration with spec-kit
>
> This plugin handles **WHAT to build and WHY** (product discovery).
> For **HOW to build it**, use spec-kit:
>
> PM Plugin → GitHub Issue → spec-kit
> /pm:file     Creates issue   /speckit.specify
> /pm:prd      Creates issue   /speckit.plan → /speckit.implement
>
> The GitHub Issue IS the handoff—no separate command needed.
> ```

The scope note answers three questions at once: what this skill covers, what it does not cover, and which artifact carries the handoff. A bare "see spec-kit" would leave the mechanism ambiguous.

---

### R08 — Patterns over theory

The Excalidraw skill teaches arrow positioning as a four-row formula table rather than prose. Claude can look up the edge formula, apply it, and move on — no reading comprehension needed.

> Real quote from `skills/excalidraw/SKILL.md:79–87`:
>
> ```
> ### 4. Arrow Edge Calculations
>
> Arrows must start/end at shape edges, not centers:
>
> | Edge   | Formula                         |
> |--------|---------------------------------|
> | Top    | `(x + width/2, y)`             |
> | Bottom | `(x + width/2, y + height)`    |
> | Left   | `(x, y + height/2)`            |
> | Right  | `(x + width, y + height/2)`   |
> ```

The same table format recurs throughout the skill: element types → use cases, framework signals → start commands, component roles → color hex codes. The entire skill is a reference grid, not a tutorial. This is why the Excalidraw skill scored 100/100.

---

### R09 — `<example>` blocks are mandatory

The `gap-analyst` agent includes three `<example>` blocks. Each follows the full structure: `Context` (what the user is doing, not just a label), a real-sounding `user` utterance, a dispatch-style `assistant` response, and a `<commentary>` block explaining the trigger logic.

> Real quote from `plugins/product-management/agents/gap-analyst.md:4–13`:
>
> ```
> <example>
> Context: User wants to identify product opportunities
> user: "What gaps do we have compared to competitors?"
> assistant: "I'll use the gap-analyst agent to systematically identify and score product gaps."
> <commentary>
> User explicitly asks about gaps, trigger gap-analyst for comprehensive analysis.
> </commentary>
> </example>
> ```

The third example is the strongest: it handles a follow-up phrase ("Now that we know what Linear does, what are we missing?") that shares no vocabulary with the agent name or description — only the examples make that trigger possible.

---

### R12 — Output format defined in body

Step 7 of the `gap-analyst` body specifies not just the output filename pattern but a full markdown template with concrete headers, table columns, and placeholder syntax — so every invocation produces the same schema.

> Real quote from `plugins/product-management/agents/gap-analyst.md:120–141`:
>
> ```
> Save to `.pm/gaps/[YYYY-MM-DD]-analysis.md`:
>
> # Gap Analysis - [Date]
>
> ## Summary
> - **Gaps Identified**: [N]
> - **NEW (ready to file)**: [N]
> - **EXISTING (already tracked)**: [N]
> - **SIMILAR (needs review)**: [N]
>
> ### NEW Gaps
>
> | Gap | Pain | Timing | Exec | Fit | Rev | Moat | WINNING | Action |
> |-----|------|--------|------|-----|-----|------|---------|--------|
> | [Feature] | 8 | 7 | 9 | 8 | 7 | 6 | 45/60 | FILE |
> ```

The template includes a populated example row, not just placeholder columns. This anchors the expected data type and scale for every field without a separate prose explanation.

---

### R17 — Specify error paths

The `gap-analyst` body closes with a four-item `## Edge Cases` section. Each case names the absent precondition and specifies an exact response — no "handle gracefully" hedging.

> Real quote from `plugins/product-management/agents/gap-analyst.md:197–203`:
>
> ```
> ## Edge Cases
>
> - **No Product Inventory**: Prompt to run `/pm:analyze` first
> - **No Competitor Data**: Prompt to run `/pm:landscape` first
> - **GitHub CLI Unavailable**: Note dedup may be incomplete
> - **All Gaps Existing**: Celebrate good coverage, suggest `/pm:backlog`
> ```

The fourth case ("All Gaps Existing") shows that error paths cover success edge cases too, not just failure. Telling Claude to "celebrate good coverage" prevents a confused no-op response when the agent finds nothing to file.

---

## Worth adopting

**Pattern: `references/` subdirectory for depth-on-demand.** Evidence: `skills/excalidraw/SKILL.md:88,102,139,159,181` links to `references/arrows.md`, `references/json-format.md`, `references/colors.md`, `references/examples.md`, `references/export.md`; the same pattern appears in `skills/uat-testing/`, `skills/landing-page-gtm/`, and `plugins/product-management/`. The main SKILL.md stays under 300 lines (R05) while deeper reference material lives in named sub-files that agents can load on demand. Why it would be a useful rule: "**Partition deep reference material into `references/` sub-files.** Keep the main SKILL.md under 500 lines (R05) by moving lookup tables, templates, and algorithm details into named sibling files; link them with inline `references/` cross-references so an agent can navigate to the detail it needs without loading the entire body."
