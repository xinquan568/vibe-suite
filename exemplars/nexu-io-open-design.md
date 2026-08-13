---
slug: nexu-io-open-design
repo: nexu-io/open-design
audited: 2026-05-13
commit_sha: 653c506b105a2fd47ffca6f0805da7f70350b82c
score: 91
exemplifies:
  - R01
  - R04
  - R05
  - R06
  - R08
---

# Exemplar: nexu-io/open-design

**Score**: 91/100  |  **Date**: 2026-05-13  |  **Commit**: `653c506b105a2fd47ffca6f0805da7f70350b82c`

A 61-skill design-artifact library for Claude Code's Open Design daemon, notable for its trigger-rich descriptions, measurable output contracts, and concrete pattern tables that replace abstract instructions with closed-vocabulary lookup tables.

## Per-rule evidence

### R04 — Description as trigger

`critique/SKILL.md` packs the description with 5 user-query phrases *and* names the exact output shape in the same sentence, so a user mentioning "what's wrong with my design" or "5 维度评审" maps cleanly to this skill without an ambiguous multi-skill match.

> Real quote from `skills/critique/SKILL.md:2-10`:
>
> ```
> description: |
>   Run a 5-dimension expert design review on any HTML artifact in the
>   project — Philosophy / Visual hierarchy / Detail / Functionality /
>   Innovation, each scored 0–10. Outputs a single self-contained HTML
>   report with a radar chart, evidence-backed scores, and three lists:
>   Keep / Fix / Quick-wins. Use when the brief asks for a "design
>   review", "design critique", "5 维度评审", "design audit", or "what's
>   wrong with my design".
> ```

What separates this from a mediocre description: it names the output shape (radar chart, three lists) as part of the trigger context. An LLM reading it knows both *when* to invoke the skill and *what it will produce* — R04's trigger function and an implicit output preview in one block.

`wireframe-sketch/SKILL.md` applies the same pattern for a lo-fi use case:

> Real quote from `skills/wireframe-sketch/SKILL.md:2-9`:
>
> ```
> description: |
>   A hand-drawn wireframe exploration — graph-paper background, marker /
>   pencil tone, multiple tab labels for variants, sticky-note annotations,
>   scribbled chart placeholders, hatched fills. Reads like a designer's
>   whiteboard before any pixels are committed. Use when the brief asks for
>   "wireframe", "sketch wireframe", "hand-drawn", "lo-fi", "whiteboard",
>   "草稿", or "手绘原型".
> ```

Seven trigger phrases, 6 visual descriptors in 78 characters of description — every token in the description earns its keep.

---

### R01 — No vague quantifiers without criteria

`blog-post/SKILL.md` replaces every instance of "a good article" or "appropriate length" with concrete counts. Step 2 of the workflow says "at least 600 words across 4–6 H2 sections. No lorem ipsum." The related-posts section specifies "3 cards linking to other posts. Each card: tiny image block, title, 1-line excerpt, date." Zero vague sizing words.

> Real quote from `skills/blog-post/SKILL.md:37-53`:
>
> ```
> 2. **Pick the topic** from the brief and write a real article — at least 600
>    words across 4–6 H2 sections. No lorem ipsum.
> 3. **Sections**, in order:
>    - **Masthead** — small wordmark + 4–6 nav links, plain.
>    - **Article header** — category eyebrow, headline (display token, large),
>      deck (1–2 sentence subhead), author name + role + date.
>    - **Hero image** — a 16:9 placeholder block using a DS-tinted gradient or
>      solid fill (no external images). Add a 1-line caption underneath.
>    - **Body** — alternating prose paragraphs with at least:
>      - 1 pull quote (large display type, accent rule on the left).
>      - 1 figure (image placeholder + caption).
>      - 1 list (numbered or bulleted).
>      - 1 inline blockquote.
> ```

`critique/SKILL.md` does the same for the scoring discipline section: instead of "be critical", it defines what each numeric band means and requires named elements as evidence.

> Real quote from `skills/critique/SKILL.md:159-166`:
>
> ```
> - **Always cite evidence** — "scored 4 because hero page mixes
>   Playfair display with Inter sans on the same line" beats "feels
>   inconsistent". Numbers without evidence get rejected.
> - **Don't average up** — if Hierarchy is 5 because page 3 is broken,
>   don't bump to 7 because pages 1 and 2 are fine. The score is the
>   *worst sustained band*.
> - **Don't grade-inflate** — a 7 means *strong*, not *acceptable*. If
>   every score is 7+, you're not reviewing critically.
> ```

Each instruction is verifiable in a code review: "did you cite an element?" is binary; "was it appropriate?" is not.

---

### R05 — Body length discipline

The six 100-scoring skills range from 74 to 97 lines. `blog-post/SKILL.md` (79 lines) covers masthead, hero, body sections, self-check, and output contract. `web-prototype/SKILL.md` (97 lines) covers resource map, 5 workflow steps, 5 hard rules, and output contract. Both stay under 100 lines by trusting the agent to fill content details rather than enumerating every possible case.

`critique/SKILL.md` (258 lines) is the longest exemplary file and demonstrates that near-500 is justified only when the content is structured reference material (scoring bands, evidence criteria, dimension definitions) that Claude must consult mid-task — not narrative explanation.

> Real quote from `skills/web-prototype/SKILL.md:32-42`:
>
> ```
> ## Resource map
>
> ```
> web-prototype/
> ├── SKILL.md                ← you're reading this
> ├── assets/
> │   └── template.html       ← seed: tokens + class system + chrome (READ FIRST)
> └── references/
>     ├── layouts.md          ← 8 paste-ready section skeletons
>     └── checklist.md        ← P0/P1/P2 self-review
> ```
> ```

Off-loading 8 layout skeletons to `references/layouts.md` is why `web-prototype/SKILL.md` stays at 97 lines instead of 600.

---

### R06 — Runnable examples

`critique/SKILL.md` Step 3 includes a fully worked scoring example with class names, page numbers, and a specific finding — not a template stub with `[INSERT EXAMPLE HERE]`.

> Real quote from `skills/critique/SKILL.md:197-206`:
>
> ```
> Example:
> ```
> Dimension: Detail execution
> Score: 6 / 10
> Evidence: Stat-cards on page 3 align cleanly (grid-6, 3×2), but on
> page 8 the right column foot sits 2vh higher than the left because
> .callout has 3vh top margin while the figure doesn't. Image captions
> use mono on page 5 but sans on page 7 — pick one.
> ```
> ```

A model reading this learns what evidence granularity is expected: it names a CSS class (`.callout`), a property (`top margin`), a page number, and a cross-page inconsistency. A stub like "Score: X/10. Evidence: [describe why]" teaches nothing.

---

### R08 — Patterns over theory

`design-brief/SKILL.md` Section 1 gives a 25-row lookup table mapping natural language phrases to concrete I-Lang dimension values, eliminating any ambiguous "parse the intent" instruction.

> Real quote from `skills/design-brief/SKILL.md:76-99`:
>
> ```
> | Natural language phrase | Dimension | I-Lang value |
> |------------------------|-----------|-------------|
> | "dark mode", "dark theme" | palette | `monochrome_dark` |
> | "light", "white background" | palette | `light_clean` |
> | "earthy", "warm tones" | palette | `earth_tones` |
> | "pop of color", "vibrant" | accent | `electric_blue` (default) or `coral` |
> | "clean", "minimal", "simple" | mood | `professional_minimal` |
> | "playful", "fun", "friendly" | mood | `playful` |
> | "bold", "brutalist", "raw" | mood | `brutalist` |
> | "editorial", "magazine-like" | mood | `editorial` |
> | "spacious", "lots of whitespace" | density | `spacious` |
> | "compact", "dense", "information-rich" | density | `compact` |
> ```

When a phrase maps to multiple dimensions, a note resolves it: "resolve each dimension independently." When a phrase has two possible values, the note names the selection condition: "the first is the default; the agent may select the alternative only if surrounding context strongly favors it."

The same skill extends this in Section 2.2 with a default-resolution table: every unspecified dimension has a mood-conditional default, not a vague "pick something sensible."

> Real quote from `skills/design-brief/SKILL.md:152-163`:
>
> ```
> | Unspecified dimension | Default rule |
> |----------------------|-------------|
> | `palette` | If mood=editorial → `light_clean`. If mood=brutalist → `monochrome_dark`. Otherwise → `light_clean`. |
> | `accent` | If palette is dark → `coral`. If palette is light → `electric_blue`. |
> | `typography` | Always → `inter` (highest cross-platform legibility). |
> | `display` | If mood=editorial → `playfair`. If mood=brutalist → `space_grotesk`. Otherwise → `same_as_body`. |
> | `layout` | Always → `single_column` (safest responsive default). |
> | `mood` | Always → `professional_minimal` (least opinionated). |
> ```

Every conditional branch terminates in a concrete token string, not a description.

---

## Worth adopting

**Pattern: Bilingual trigger list.** Multiple skills include Chinese-language trigger phrases alongside English ones — both in the `triggers:` YAML list and in the description. Evidence: `skills/wireframe-sketch/SKILL.md:18-19` (`"手绘原型"`, `"草图"`, `"线框图"`), `skills/blog-post/SKILL.md:15-16` (`"博客"`, `"文章"`), `skills/critique/SKILL.md:20-21` (`"5 维度评审"`, `"评审"`, `"复盘"`). Why it would be a useful rule: skills deployed to multilingual user bases silently fail when the daemon's trigger-matching only matches the English form; adding the target-language trigger string costs 1–3 tokens and eliminates the miss entirely. A candidate rule: "**Include target-language trigger strings when the skill is designed for non-English users.** One additional line per language; missing it means users querying in their native language get no skill match."
