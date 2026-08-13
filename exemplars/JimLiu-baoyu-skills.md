---
slug: JimLiu-baoyu-skills
repo: JimLiu/baoyu-skills
audited: 2026-05-13
commit_sha: 505a7e10cea80f5da291114db19a4be0e40b9d7e
score: 90
exemplifies:
  - R04
  - R05
  - R06
  - R08
  - R35
  - R38
---

# Exemplar: JimLiu/baoyu-skills

**Score**: 90/100  |  **Date**: 2026-05-13  |  **Commit**: `505a7e10cea80f5da291114db19a4be0e40b9d7e`

A 23-skill Claude Code plugin for content generation and translation — notable for densely-packed bilingual description triggers, a references-offload pattern that keeps individual SKILL.md files compact, and a CLAUDE.md that reads like an instruction set rather than a project overview.

## Per-rule evidence

### R04 — Description as trigger

The `baoyu-translate` description packs 17 distinct trigger phrases across English and Chinese in a single `description:` field, covering both command forms ("translate"), natural-language forms ("这篇文章翻译一下"), and implicit intent ("when a URL or file is provided with translation intent"). The description also names all three workflow modes upfront so the skill loads only when the mode is relevant.

> Real quote from `skills/baoyu-translate/SKILL.md:3-3`:
>
> ```
> description: Translates articles and documents between languages with three modes - quick
>   (direct), normal (analyze then translate), and refined (analyze, translate, review, polish).
>   Supports custom glossaries and terminology consistency via EXTEND.md. Use when user asks
>   to "translate", "翻译", "精翻", "translate article", "translate to Chinese/English",
>   "改成中文", "改成英文", "convert to Chinese", "localize", "本地化", or needs any document
>   translation. Also triggers for "refined translation", "精细翻译", "proofread translation",
>   "快速翻译", "快翻", "这篇文章翻译一下", or when a URL or file is provided with
>   translation intent.
> ```

The description earns its length: every phrase covers a different user vocabulary cluster that would otherwise miss the skill. Compare to the mediocre `baoyu-article-illustrator` description which lists only 4 English phrases and no Chinese equivalents, yet this skill serves a predominantly Chinese-language audience.

### R05 — Body length

`baoyu-article-illustrator` describes a six-step image-generation workflow — pre-check, analyze, confirm, outline, generate, finalize — in 241 lines by consistently deferring procedural detail to `references/` sub-files. Each workflow section ends with a "Full procedures:" link rather than inlining the full specification. The SKILL.md stays navigable while the detail remains accessible.

> Real quote from `skills/baoyu-article-illustrator/SKILL.md:95-125`:
>
> ```
> ### Step 1: Pre-check
>
> **1.5 Load Preferences (EXTEND.md) ⛔ BLOCKING**
> ...
> Full procedures: [references/workflow.md](references/workflow.md#step-1-pre-check)
>
> ### Step 2: Analyze
>
> | Analysis | Output |
> |----------|--------|
> | Content type | Technical / Tutorial / Methodology / Narrative |
> | Purpose | information / visualization / imagination |
> | Core arguments | 2-5 main points |
> | Positions | Where illustrations add value |
>
> Full procedures: [references/workflow.md](references/workflow.md#step-2-setup--analyze)
> ```

The pattern — table-summary in SKILL.md, full spec in references/ — is applied consistently across all six steps, making the SKILL.md a navigable overview rather than an inline manual.

### R06 — Code examples must be runnable

`baoyu-compress-image` covers every major invocation pattern with real bash commands using the actual runtime variable (`${BUN_X}`), real flags from the options table, and an expected-output line showing concrete byte counts and reduction percentage. No pseudocode or placeholder arguments.

> Real quote from `skills/baoyu-compress-image/SKILL.md:58-78`:
>
> ```
> ## Examples
>
> ```bash
> # Single file → WebP (replaces original)
> ${BUN_X} {baseDir}/scripts/main.ts image.png
>
> # Keep PNG format
> ${BUN_X} {baseDir}/scripts/main.ts image.png -f png --keep
>
> # Directory recursive
> ${BUN_X} {baseDir}/scripts/main.ts ./images/ -r -q 75
>
> # JSON output
> ${BUN_X} {baseDir}/scripts/main.ts image.png --json
> ```
>
> **Output**:
> ```
> image.png → image.webp (245KB → 89KB, 64% reduction)
> ```
> ```

The output format example is what separates this from a typical examples block: Claude knows exactly what a success result looks like, making it possible to detect failure and surface it to the user.

### R08 — Patterns over theory

`baoyu-image-cards` teaches style selection as a lookup table: given observable signals in the source content, pick the named style, layout, and preset. No abstract advice about "choosing an appropriate visual style" — the rule is deterministic from the input.

> Real quote from `skills/baoyu-image-cards/SKILL.md:186-200`:
>
> ```
> ## Auto-Selection
>
> Match content signals to the best combo. First row whose keywords appear wins; fall back
> to `cute-share` if nothing matches.
>
> | Signals in source | Style | Layout | Recommended preset |
> |-------------------|-------|--------|--------------------|
> | beauty, fashion, cute, girl, pink | `cute` | sparse/balanced | `cute-share`, `girly` |
> | health, nature, fresh, organic | `fresh` | balanced/flow | `product-review`, `nature-flow` |
> | life, story, emotion, warm | `warm` | balanced | `cozy-story` |
> | warning, important, must, critical | `bold` | list/comparison | `warning`, `versus` |
> | professional, business, elegant | `minimal` | sparse/balanced | `clean-quote`, `pro-summary` |
> | knowledge, concept, productivity, SaaS | `notion` | dense/list | `knowledge-card`, `checklist` |
> | education, tutorial, learning, classroom | `chalkboard` | balanced/dense | `tutorial`, `classroom` |
> ```

`baoyu-translate` applies the same pattern for mode auto-detection (`"快翻"` → quick mode, `"精翻"` → refined mode, otherwise → normal), so any skill that requires the agent to make a classification decision expresses it as a keyed lookup rather than prose guidance.

### R35 — Architecture overview

CLAUDE.md opens with a two-level architecture description: the single plugin entry point (`marketplace.json`), the three logical skill groups, and the per-skill directory layout — all in a table-and-prose format that answers "what lives where" in under 10 lines.

> Real quote from `CLAUDE.md:1-15`:
>
> ```
> Claude Code marketplace plugin providing AI-powered content generation skills.
> Version: **1.107.0**.
>
> ## Architecture
>
> Skills are exposed through the single `baoyu-skills` plugin in
> `.claude-plugin/marketplace.json` (which defines plugin metadata, version, and skill paths).
> The repo docs still group them into three logical areas:
>
> | Group | Description |
> |-------|-------------|
> | Content Skills | Generate or publish content (images, slides, comics, posts) |
> | AI Generation Skills | AI generation backends |
> | Utility Skills | Content processing (conversion, compression, translation) |
>
> Each skill contains `SKILL.md` (YAML front matter + docs), optional `scripts/`,
> `references/`, `prompts/`.
> ```

The architecture section immediately answers the question Claude is most likely to ask before reading any skill file: "what kind of repo is this and how is it structured?" — which prevents Claude from scanning every directory before loading a skill.

### R38 — More instructive than descriptive

The longest sections of CLAUDE.md are imperative rule tables: Skill Self-Containment (what Claude must never link to and why), User Input Tools (exact tool-selection priority order), Image Generation Tools (backend resolution algorithm). The project description and feature list occupy fewer than 15 lines total.

> Real quote from `CLAUDE.md` (Skill Self-Containment section):
>
> ```
> ## Skill Self-Containment
>
> Each skill under `skills/` (and `.claude/skills/`) is distributed and consumed
> independently — the folder may be extracted, copied into another project, or loaded
> without the rest of this repo. Therefore:
>
> - **Never link from `SKILL.md` or its `references/` to files outside the skill's own
>   directory.** This includes `docs/`, sibling skills, and the repo root. Relative paths
>   like `../../docs/foo.md` break when the skill is used standalone.
> - **Inline any shared convention** (e.g., user-input rules, image-generation backend
>   selection) directly in the skill rather than referencing an out-of-skill doc.
> - Shared docs under `docs/` exist for **repo-author guidance only** — they may be
>   referenced from `CLAUDE.md` and `docs/creating-skills.md`, but NOT from any `SKILL.md`.
> ```

The constraint is stated as a behavioral rule with the consequence ("breaks when the skill is used standalone"), not as a description of the repo's design philosophy — which is the right register for a CLAUDE.md.

## Worth adopting

**Pattern: Three-tier EXTEND.md lookup.** Every skill declares user preferences using the same three-path priority table: project-local (`.baoyu-skills/<skill>/EXTEND.md`) → XDG config → home dir. Evidence: `skills/baoyu-compress-image/SKILL.md:28-36`, `skills/baoyu-translate/SKILL.md:40-47`, and every other skill with preferences. Why it would be a useful rule: skills that read user preferences without a documented override chain force users to choose between project-local and global settings at install time; a three-tier lookup lets the same skill serve both use cases without configuration flags.

**Pattern: Hard-gate annotation (⛔ BLOCKING).** Steps that must complete before the workflow can continue are annotated inline with `⛔ BLOCKING` in the step heading and a hard-gate note in the body. Evidence: `skills/baoyu-article-illustrator/SKILL.md:97` (`**1.5 Load Preferences (EXTEND.md) ⛔ BLOCKING**`), `skills/baoyu-image-cards/SKILL.md:285` (`### Step 0: Load EXTEND.md ⛔ BLOCKING`). Why it would be a useful rule: prose-only descriptions of prerequisite steps are routinely skipped by agents reasoning about "optional" setup; a visual sentinel in the heading makes the constraint legible in a table-of-contents scan.
