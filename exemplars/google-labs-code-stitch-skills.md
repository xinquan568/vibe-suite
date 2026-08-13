---
slug: google-labs-code-stitch-skills
repo: google-labs-code/stitch-skills
audited: 2026-05-13
commit_sha: 6c0cbdb909b7d256c8b9b3854c8c8f87aab2c140
score: 96
exemplifies:
  - R01
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: google-labs-code/stitch-skills

**Score**: 96/100  |  **Date**: 2026-05-13  |  **Commit**: `6c0cbdb909b7d256c8b9b3854c8c8f87aab2c140`

A collection of eight skills for Google's Stitch UI-generation platform, notable for action-phrase descriptions, complete runnable examples, explicit skill cross-references, and measurement-first anti-pattern catalogues.

## Per-rule evidence

### R04 — Description as trigger

Every skill in this collection writes its `description` field as a clause the user might actually type, not a summary of what the file contains. Each packs multiple specific action phrases in under 20 words, naming the tool, the artifact, and the transformation.

> `skills/enhance-prompt/SKILL.md:3-4`:
>
> ```
> description: Transforms vague UI ideas into polished, Stitch-optimized prompts. Enhances
>   specificity, adds UI/UX keywords, injects design system context, and structures output
>   for better generation results.
> ```

> `skills/remotion/SKILL.md:3-4`:
>
> ```
> description: Generate walkthrough videos from Stitch projects using Remotion with smooth
>   transitions, zooming, and text overlays
> ```

> `skills/taste-design/SKILL.md:3-4`:
>
> ```
> description: Semantic Design System Skill for Google Stitch. Generates agent-friendly
>   DESIGN.md files that enforce premium, anti-generic UI standards — strict typography,
>   calibrated color, asymmetric layouts, perpetual micro-motion, and hardware-accelerated
>   performance.
> ```

What separates these from mediocre descriptions: every one names a concrete input ("vague UI ideas", "Stitch projects"), a concrete output ("Stitch-optimized prompts", "walkthrough videos", "DESIGN.md files"), and the transformation between them. No skill uses a description like "Helpful Stitch skill."

---

### R05 — Body length

All eight skills stay well under the 500-line limit despite covering complex multi-step workflows. The three longest — `stitch-loop` (264 lines), `enhance-prompt` (205 lines), `taste-design` (192 lines) — achieve their depth through tables and code blocks rather than prose paragraphs.

> `skills/stitch-loop/SKILL.md` (entire file: 264 lines):
>
> ```
> ---
> name: stitch-loop
> ...
> ---
> # Stitch Build Loop
> ...
> ## Troubleshooting
> | Issue | Solution |
> |-------|----------|
> | Stitch generation fails | Check that the prompt includes the design system block |
> ...
> ```

The discipline is structural: the skill uses tables for lookup content (prerequisites, troubleshooting, orchestration options) and code blocks for schemas, rather than expanding into prose. Each section earns its lines by changing behavior; the Troubleshooting table alone saves an agent from four common failure modes without prose padding.

---

### R06 — Code examples must be runnable

`enhance-prompt` ships two end-to-end examples showing a real user input and the exact enhanced output the skill should produce. Both examples use realistic, runnable prompt text — not pseudocode or placeholders.

> `skills/enhance-prompt/SKILL.md:147-176`:
>
> ```markdown
> ### Example 1: Vague Input → Structured Prompt
>
> **User input:**
> > "make me a login page"
>
> **Enhanced output:**
> ```markdown
> A clean, trustworthy login page with a centered form and subtle branding.
>
> **DESIGN SYSTEM (REQUIRED):**
> - Platform: Web, Desktop-first
> - Theme: Light, minimal, professional
> - Background: Clean White (#ffffff)
> - Surface: Soft Gray (#f9fafb) for form card
> - Primary Accent: Deep Blue (#2563eb) for submit button and links
> - Text Primary: Near Black (#111827) for headings
> - Text Secondary: Medium Gray (#6b7280) for labels
> - Buttons: Subtly rounded (8px), full-width on form
> - Cards: Gently rounded (12px), soft shadow for elevation
>
> **Page Structure:**
> 1. **Header:** Minimal logo, centered
> 2. **Login Card:** Centered form with email, password fields, "Forgot password?" link
> 3. **Submit Button:** Primary blue "Sign In" button
> 4. **Footer:** "Don't have an account? Sign up" link
> ```
> ```

`stitch-loop` does the same for its baton-file schema: not a template with placeholders, but a real populated JSON object with actual Stitch project IDs and screen coordinates an agent can use as a reference.

> `skills/stitch-loop/SKILL.md:172-215`:
>
> ```json
> {
>   "name": "projects/6139132077804554844",
>   "projectId": "6139132077804554844",
>   "title": "My App",
>   "screens": {
>     "index": {
>       "id": "d7237c7d78f44befa4f60afb17c818c1",
>       "sourceScreen": "projects/6139132077804554844/screens/d7237c7d78f44befa4f60afb17c818c1",
>       "x": 0,
>       "y": 0,
>       "width": 390,
>       "height": 1249
>     }
>   }
> }
> ```

A real project ID and screen UUID give an agent a concrete mental model of the schema; a placeholder `"projectId": "<your-project-id>"` does not.

---

### R07 — Scope note when related skills exist

`enhance-prompt` names its sibling skills in two places: once inline in the output template, once in the Output Options section. An agent reading this skill knows exactly where to go next without guessing.

> `skills/enhance-prompt/SKILL.md:54-63`:
>
> ```markdown
> **If DESIGN.md does not exist:**
> 1. Add this note at the end of the enhanced prompt:
>
> ```
> 💡 **Tip:** For consistent designs across multiple screens, create a DESIGN.md
> file using the `design-md` skill. This ensures all generated pages share the
> same visual language.
> ```
> ```

> `skills/enhance-prompt/SKILL.md:139-142`:
>
> ```markdown
> **Optional file output:** If the user requests, write to a file:
> - `next-prompt.md` — for use with the `stitch-loop` skill
> - Custom filename specified by user
> ```

`stitch-loop` reciprocates with an explicit integration section:

> `skills/stitch-loop/SKILL.md:241-246`:
>
> ```markdown
> ## Design System Integration
>
> This skill works best with the `design-md` skill:
>
> 1. **First time setup**: Generate `.stitch/DESIGN.md` using the `design-md` skill from an existing Stitch screen
> 2. **Every iteration**: Copy Section 6 ("Design System Notes for Stitch Generation") into your baton prompt
> ```

The cross-references are bidirectional and specific: they name the target skill, the artifact it produces, and the exact moment to invoke it.

---

### R08 — Patterns over theory

`taste-design` replaces all aesthetic advice with decision tables and substitution lists. Instead of "choose a good density," it gives a three-point scale with named stops. Instead of "avoid AI clichés," it lists 18 specific banned patterns.

> `skills/taste-design/SKILL.md:35-39`:
>
> ```markdown
> - **Density:** "Art Gallery Airy" (1–3) → "Daily App Balanced" (4–7) → "Cockpit Dense" (8–10)
> - **Variance:** "Predictable Symmetric" (1–3) → "Offset Asymmetric" (4–7) → "Artsy Chaotic" (8–10)
> - **Motion:** "Static Restrained" (1–3) → "Fluid CSS" (4–7) → "Cinematic Choreography" (8–10)
>
> Default baseline: Creativity 9, Variance 8, Motion 6, Density 5.
> ```

`enhance-prompt` does the same for prompt vocabulary:

> `skills/enhance-prompt/SKILL.md:71-80`:
>
> ```markdown
> | Vague | Enhanced |
> |-------|----------|
> | "menu at the top" | "navigation bar with logo and menu items" |
> | "button" | "primary call-to-action button" |
> | "list of items" | "card grid layout" or "vertical list with thumbnails" |
> | "form" | "form with labeled input fields and submit button" |
> | "picture area" | "hero section with full-width image" |
> ```

Both tables convert a judgment call into a lookup. An agent following `taste-design` never needs to decide what "dense" means; following `enhance-prompt` it never needs to decide how to name a button.

---

### R01 — No vague quantifiers without criteria

`taste-design` replaces every design guideline that could be written vaguely with a specific, measurable value. The pattern appears throughout: every dimension is a number, every constraint names a threshold.

> `skills/taste-design/SKILL.md:87-98`:
>
> ```markdown
> - **Touch Targets:** All interactive elements minimum `44px` tap target
> - **Typography Scaling:** Headlines scale via `clamp()`. Body text minimum `1rem`/`14px`
> - **Spacing:** Vertical section gaps reduce proportionally (`clamp(3rem, 8vw, 6rem)`)
> ```

> `skills/taste-design/SKILL.md:95-98`:
>
> ```markdown
> - **Spring Physics default:** `stiffness: 100, damping: 20` — premium, weighty feel. No linear easing
> - **Body:** Relaxed leading, max 65 characters per line
> ```

> `skills/taste-design/SKILL.md:44-49`:
>
> ```markdown
> **Mandatory constraints:**
> - Maximum 1 accent color. Saturation below 80%
> - Never use pure black (`#000000`) — use Off-Black, Zinc-950, or Charcoal
> ```

None of these say "appropriate" or "sufficient." Every constraint names a number, a named color token, or a CSS function. The audit's two R01 deductions in `taste-design` came from a different section of the same file; the design-system encoding sections shown here are clean.

---

## Worth adopting

**Pattern: Baton-file inter-skill state passing.** Evidence: `skills/stitch-loop/SKILL.md:36-55`. A YAML-fronted markdown file (`.stitch/next-prompt.md`) acts as the shared state object between autonomous loop iterations. The skill mandates both reading from and writing to this file as part of its execution contract. Why it would be a useful rule: skills that drive multi-turn or multi-agent loops need an explicit persistence contract; a rule like "define a named state file and its schema when a skill drives an iterative loop" would prevent agents from losing context between calls.

**Pattern: Domain anti-pattern catalogue as a first-class skill section.** Evidence: `skills/taste-design/SKILL.md:100-120`. The skill ends with a section titled "List Anti-Patterns (AI Tells)" containing 18 explicit banned patterns, each phrased as a concrete prohibition ("No `Inter` font", "No fake round numbers (`99.99%`, `50%`)"). The list is part of the Output Format instruction set — agents are told to reproduce it in their generated `DESIGN.md`. Why it would be a useful rule: in creative or generative skills, cataloguing domain-specific failure modes (AI tells, generic outputs, known bad defaults) in a dedicated section improves output quality more reliably than positive framing alone, because generative models have strong priors toward the patterns being banned.
