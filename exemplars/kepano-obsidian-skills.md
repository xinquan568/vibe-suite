---
slug: kepano-obsidian-skills
repo: kepano/obsidian-skills
audited: 2026-05-13
commit_sha: fa1e131a014576ff8f8919f191a7ca8d8fded39b
score: 100
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: kepano/obsidian-skills

**Score**: 100/100  |  **Date**: 2026-05-13  |  **Commit**: `fa1e131a014576ff8f8919f191a7ca8d8fded39b`

Five-skill Claude Code plugin covering the Obsidian ecosystem; all five skills carry complete frontmatter, concrete worked examples, and explicit scope boundaries — with the most content-dense skill reaching 497 lines via deliberate reference offloading.

## Per-rule evidence

### R04 — Description as trigger

Each skill's `description` packs multiple action verbs and named feature keywords — not a one-sentence summary. `obsidian-markdown` is the densest: two sentences naming the artifact type, primary action verbs, and seven feature-level trigger words drawn directly from Obsidian's user vocabulary.

> `skills/obsidian-markdown/SKILL.md:3`:
>
> ```
> description: Create and edit Obsidian Flavored Markdown with wikilinks, embeds, callouts,
> properties, and other Obsidian-specific syntax. Use when working with .md files in Obsidian,
> or when the user mentions wikilinks, callouts, frontmatter, tags, embeds, or Obsidian notes.
> ```

Seven distinct trigger tokens ("wikilinks", "embeds", "callouts", "frontmatter", "tags", "Obsidian notes", ".md files") in 58 words. A user saying "I need to add a callout to my Obsidian note" matches three of them; a generic description like "Helpful Obsidian Markdown skill" would match zero.

### R05 — Body length under 500 lines

All five skills stay under 500 lines. The most content-dense, `obsidian-bases`, reaches 497 lines — three under the limit — because it offloads the complete function reference to `references/FUNCTIONS_REFERENCE.md` rather than inlining it. The offload is announced explicitly at the point where a reader would want it:

> `skills/obsidian-bases/SKILL.md:177`:
>
> ```
> Most commonly used functions. For the complete reference of all types (Date, String, Number,
> List, File, Link, Object, RegExp), see [FUNCTIONS_REFERENCE.md](references/FUNCTIONS_REFERENCE.md).
> ```

The skill provides 7 of the most-used functions inline, then defers the rest. This is active line-budget management: the author chose which content belongs in the hot path and which belongs in an on-demand reference, rather than either omitting the detail or blowing the budget.

### R06 — Code examples must be runnable

`json-canvas/SKILL.md` provides complete, copyable JSON for every node type (text, file, link, group), every edge configuration, and the base canvas structure. Each example uses plausible values — a real-looking 16-character hex ID, actual pixel coordinates, realistic content strings — not placeholder text.

> `skills/json-canvas/SKILL.md:81-93`:
>
> ```json
> {
>   "id": "6f0ad84f44ce9c17",
>   "type": "text",
>   "x": 0,
>   "y": 0,
>   "width": 400,
>   "height": 200,
>   "text": "# Hello World\n\nThis is **Markdown** content."
> }
> ```
>
> **Newline pitfall**: Use `\n` for line breaks in JSON strings. Do **not** use the literal `\\n`
> -- Obsidian renders that as the characters `\` and `n`.

Every required field is populated with a concrete value. An LLM reading this can generate a valid canvas node by pattern-matching against the example with no additional inference. The pitfall annotation immediately following (line 93) flags the single most common mistake at the exact point where it would be made.

### R07 — Scope note when related skills exist

`obsidian-markdown/SKILL.md` declares its scope boundary in the second sentence of the body, before any syntax:

> `skills/obsidian-markdown/SKILL.md:8`:
>
> ```
> This skill covers only Obsidian-specific extensions -- standard Markdown (headings, bold,
> italic, lists, quotes, code blocks, tables) is assumed knowledge.
> ```

Two boundaries in one sentence: what this skill covers, and what to rely on training data for instead. An LLM loading this skill won't look here for standard heading or list syntax; the scope note prevents misrouted queries before they waste attention.

### R08 — Patterns over theory

`obsidian-bases/SKILL.md` teaches three formula failure modes as WRONG/CORRECT code pairs, not as a type-system explanation. Each pair is self-contained: the broken expression, an inline comment naming the failure mode, the fix.

> `skills/obsidian-bases/SKILL.md:454-472`:
>
> ```yaml
> # WRONG - Duration is not a number
> "(now() - file.ctime).round(0)"
>
> # CORRECT - access .days first, then round
> "(now() - file.ctime).days.round(0)"
> ```
>
> ```yaml
> # WRONG - crashes if due_date is empty
> "(date(due_date) - today()).days"
>
> # CORRECT - guard with if()
> 'if(due_date, (date(due_date) - today()).days, "")'
> ```

No prose explains why Duration subtraction returns a non-number or why null properties crash — the WRONG/CORRECT pairs are the explanation. An LLM generating a formula either produces the correct pattern directly or recognizes its output matches the WRONG example and self-corrects.

## Worth adopting

**Pattern: inline pitfall annotation.** Evidence: `skills/json-canvas/SKILL.md:93`. A bold callout naming the most common mistake appears immediately after the relevant syntax example, not in a separate bottom-of-file troubleshooting section. Why it would be a useful rule: a pitfall co-located with the example is processed in the same attention window as the syntax; a pitfall deferred to a later section requires the LLM to connect a warning to the context where it applies, which is an unreliable inference hop.
