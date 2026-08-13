---
slug: Dammyjay93-interface-design
repo: Dammyjay93/interface-design
audited: 2026-05-13
commit_sha: 8c407c1c42890010a9eb403a9f419b1eeadcfdad
score: 94
exemplifies:
  - R04
  - R05
  - R07
  - R08
  - R16
---

# Exemplar: Dammyjay93/interface-design

**Score**: 94/100  |  **Date**: 2026-05-13  |  **Commit**: `8c407c1c42890010a9eb403a9f419b1eeadcfdad`

A single-skill plugin for UI craft (dashboards, apps, admin panels) that demonstrates how to pack deep domain knowledge into a tight, trigger-ready SKILL.md with output-templated commands.

## Per-rule evidence

### R04 — Description as trigger

The SKILL.md `description` field does three things in one sentence: names the domain, lists five specific artifact types, and negates the adjacent domain with three counter-examples. A model loading this skill knows immediately whether it applies to the current request.

> Real quote from `.claude/skills/interface-design/SKILL.md:3`:
>
> ```
> description: This skill is for interface design — dashboards, admin panels, apps, tools, and interactive products. NOT for marketing design (landing pages, marketing sites, campaigns).
> ```

What makes this stronger than a mediocre description: the negation clause ("NOT for marketing design") does disambiguation work that a positive-only description cannot. Without it, a model might load this skill for a landing page — both are "design." The parenthetical counter-examples (landing pages, marketing sites, campaigns) prevent borderline mis-triggers.

### R05 — Body length

The SKILL.md covers typography hierarchy, color theory, spacing systems, border progressions, animation, dark mode, interaction states, navigation context, a four-phase workflow, and four named self-check tests — all in 391 lines. It stays inside the 500-line budget while handling a domain with genuine depth.

> Real quote from `.claude/skills/interface-design/SKILL.md:229-298` (Design Principles section, condensed):
>
> ```
> ## Token Architecture
> ...
> ### Text Hierarchy
> Don't just have "text" and "gray text." Build four levels...
>
> ### Border Progression
> Borders aren't binary. Build a scale that matches intensity to importance...
>
> ### Control Tokens
> Form controls have specific needs. Don't reuse surface tokens...
>
> ## Spacing
> Pick a base unit and stick to multiples...
>
> ## Depth
> Choose ONE approach and commit:
> - **Borders-only** — Clean, technical. For dense tools.
> - **Subtle shadows** — Soft lift. For approachable products.
> - **Layered shadows** — Premium, dimensional. For cards that need presence.
> - **Surface color shifts** — Background tints establish hierarchy without shadows.
> ```

The constraint that forces this density: every principle is stated as a named pattern with a decision axis, not as a paragraph of reasoning. "Choose ONE approach and commit" is one line. A verbose author would write three paragraphs explaining why mixing depth strategies fails.

### R07 — Scope note when related skills exist

The scope boundary appears in two places: the frontmatter `description` (where it disambiguates at load time) and the body `Scope` section (where it redirects at runtime). Both point to the same redirect target.

> Real quote from `.claude/skills/interface-design/SKILL.md:12-14`:
>
> ```
> **Not for:** Landing pages, marketing sites, campaigns. Redirect those to `/frontend-design`.
> ```

The redirect target (`/frontend-design`) doesn't exist in this repo, which is a bug — but the pattern itself is correct. The scope note prevents the skill from silently handling requests it wasn't designed for, and it gives the model an explicit next step rather than leaving it to improvise.

### R08 — Patterns over theory

Instead of stating abstract principles like "check your design carefully," the SKILL.md defines four named diagnostic procedures that a model can execute mechanically. Each test has a specific question to answer and a specific implication if the answer is wrong.

> Real quote from `.claude/skills/interface-design/SKILL.md:138-148`:
>
> ```
> ## The Checks
>
> Run these against your output before presenting:
>
> - **The swap test:** If you swapped the typeface for your usual one, would anyone notice? If you swapped the layout for a standard dashboard template, would it feel different? The places where swapping wouldn't matter are the places you defaulted.
>
> - **The squint test:** Blur your eyes. Can you still perceive hierarchy? Is anything jumping out harshly? Craft whispers.
>
> - **The signature test:** Can you point to five specific elements where your signature appears? Not "the overall feel" — actual components. A signature you can't locate doesn't exist.
>
> - **The token test:** Read your CSS variables out loud. Do they sound like they belong to this product's world, or could they belong to any project?
> ```

Each check has a pass/fail condition (not "consider whether..."). The squint test operationalizes "good hierarchy" as a visual blur test — a model can follow that instruction. The token test turns a vague quality (intentional naming) into a specific affordance: read them aloud, hear whether they evoke a world. This is R08 at its clearest: the same advice rendered as procedure instead of principle.

### R16 — Output format defined

Three of the five commands define exact report templates with file-path + line-number + value citations. The templates leave no ambiguity about what the output should look like, making it easy to verify compliance at a glance.

> Real quote from `.claude/commands/audit.md:38-52`:
>
> ```
> **Report format:**
> ```
> Audit Results: src/components/
>
> Violations:
>   Button.tsx:12 - Height 38px (pattern: 36px)
>   Card.tsx:8 - Shadow used (system: borders-only)
>   Input.tsx:20 - Spacing 14px (grid: 4px, nearest: 12px or 16px)
>
> Suggestions:
>   - Update Button height to match pattern
>   - Replace shadow with border
>   - Adjust spacing to grid
> ```
> ```

The template encodes the violation format as `path:line - description (rule: expectation)` — a pattern the model can apply consistently across any codebase. The `extract.md` command uses the same approach, showing frequency counts in its template (`Found: 4px (12x), 8px (23x)...`), which makes the extraction output machine-readable for any downstream processing.

## Worth adopting

**Pattern: Mandatory intent-declaration block before each component.** Evidence: `.claude/skills/interface-design/SKILL.md:210-224` — a six-field template (Intent, Palette, Depth, Surfaces, Typography, Spacing) that the skill requires to be stated out loud before any UI code is written. Why it would be a useful rule: forcing the model to fill in a structured context block before generating output breaks the default-pattern path; it's a pre-generation QC gate that is more reliable than post-generation critique. Candidate rule: "**Require a structured intent declaration before generative output in design or creative skills.** List the fields as a fill-in template; a model that cannot fill in the template should stop and ask rather than generate from defaults."
