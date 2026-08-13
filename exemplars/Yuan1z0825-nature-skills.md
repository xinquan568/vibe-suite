---
slug: Yuan1z0825-nature-skills
repo: Yuan1z0825/nature-skills
audited: 2026-05-24
commit_sha: f37ec718af793a7160b36437d6bd9d8291836a52
score: 93
exemplifies:
  - R04
  - R05
  - R07
  - R08
---

# Exemplar: Yuan1z0825/nature-skills

**Score**: 93/100  |  **Date**: 2026-05-24  |  **Commit**: `f37ec718af793a7160b36437d6bd9d8291836a52`

A 9-skill plugin for Nature-family manuscript workflows (polishing, citation, figure, data, writing, reader, response, paper2ppt, academic search) that demonstrates multilingual trigger discipline, consistent conditional-loading tables, and a strong pattern-over-theory structure in each SKILL.md.

## Per-rule evidence

### R04 — Description as trigger

R04 requires the `description` field to contain 3+ specific action phrases matching real user queries. The strongest example in this repo is `nature-response`, which packs both English action verbs and Chinese native-language query phrases into a single YAML block, ensuring the skill fires for Chinese-speaking researchers who ask in their first language.

> Real quote from `skills/nature-response/SKILL.md:3-8`:
>
> ```yaml
> description: >-
>   Draft, audit, or revise point-by-point reviewer response letters for Nature-family
>   manuscript revisions. Use when the user provides reviewer comments, editor decision
>   letters, revision notes, response drafts, or asks how to respond to major/minor
>   revision requests, rebuttal letters, response to reviewers, peer-review reports,
>   审稿意见回复, 逐点回复, 修回信, 大修回复, 小修回复, or 如何回复 reviewer.
> ```

The description does more than name the task: it enumerates six document types the user might provide, five decision-type phrases they might ask about, and six Chinese query strings. A user typing "修回信怎么写" in chat hits the trigger; a user typing "rebuttal letter" also hits it. That coverage comes from actual query phrases, not category labels.

`nature-reader` applies the same pattern: the description lists five input formats (PDF, DOI, arXiv, publisher HTML, pasted text), three output verbs (translate, read, extract), and bilingual trigger idioms (`中英文对照/原文对照/全文翻译解读`), reaching that coverage in two sentences.

> Real quote from `skills/nature-reader/SKILL.md:2-3`:
>
> ```yaml
> description: Build full-paper Chinese-English side-by-side, figure/table-aware, source-grounded
>   Markdown readers for journal or conference papers from PDF, DOI, arXiv, publisher HTML, or
>   pasted text. Use whenever the user asks to translate or read a paper, make
>   中英文对照/原文对照/全文翻译解读, extract figures or tables into the right positions,
>   preserve figure/table placement near relevant prose, or keep exact source anchors for every block.
> ```

What separates these from mediocre descriptions: every clause describes a concrete user action or document type, not a capability claim.

### R05 — Body length

R05 caps each SKILL.md at 500 lines to avoid context bloat. Eight of the nine skills comply; measured line counts: `nature-response` 127 lines, `nature-data` 117 lines, `nature-writing` 159 lines, `nature-reader` 254 lines, `nature-polishing` 386 lines. (`nature-paper2ppt` at 696 lines is the one exception and is not cited here as a positive case.)

The pattern enabling compliance: every skill keeps its SKILL.md to workflow and stance, then pushes deep reference content to a `references/` subdirectory loaded on demand. `nature-response` (127 lines) links to nine reference files covering intake routing, comment taxonomy, action mapping, tone, difficult cases, and QA checklists — none of that content sits in the SKILL.md body.

> Real quote from `skills/nature-response/SKILL.md:104-116`:
>
> ```markdown
> | File | Open when |
> |---|---|
> | [references/intake-and-routing.md](references/intake-and-routing.md) | Before drafting, to identify task mode, minimum inputs, editor IDs, readiness state, and clarifying-question need |
> | [references/source-basis.md](references/source-basis.md) | You need source hierarchy, rule provenance, or policy-vs-advice boundaries |
> | [references/response-structure.md](references/response-structure.md) | You need the response package format or point-by-point letter anatomy |
> | [references/comment-taxonomy.md](references/comment-taxonomy.md) | You need to classify reviewer comments by category and severity |
> | [references/action-mapping.md](references/action-mapping.md) | You need action labels, tracker fields, and missing-input states |
> | [references/tone-and-stance.md](references/tone-and-stance.md) | You need recommended language, forbidden phrasing, or disagreement tone |
> | [references/chinese-author-alignment.md](references/chinese-author-alignment.md) | The user writes in Chinese or provides Chinese author notes |
> | [references/difficult-cases.md](references/difficult-cases.md) | The comments involve impossible experiments, factual errors, conflicting reviewers, citations, statistics, compliance, transfer, or appeal-like cases |
> | [references/qa-checklist.md](references/qa-checklist.md) | Before finalizing an output or auditing a draft response |
> ```

Nine files of depth, zero bytes in the hot path — that is the mechanism that keeps the 127-line body honest.

### R07 — Scope note when related skills exist

R07 requires a scope note ("Covers X. For Y, see other-skill.") when related skills exist. This repo does something stronger: every skill uses a `| File | Open when |` table that makes the conditional load trigger explicit rather than advisory.

The `nature-polishing` skill separates its own scope (prose-level argument repair, polishing) from content in five reference files, and states the loading condition for each as a concrete task rather than a subject area.

> Real quote from `skills/nature-polishing/SKILL.md:30-39`:
>
> ```markdown
> | File | Open when |
> |---|---|
> | [references/published-article-patterns.md](references/published-article-patterns.md) | You need Nature/Nature Communications article-level writing patterns for abstracts, introductions, Results, Discussion, conclusions, or titles |
> | [references/writing-strategy.md](references/writing-strategy.md) | You need paragraph- or section-level argument repair before sentence polishing |
> | [references/section-moves.md](references/section-moves.md) | You need section-specific move orders or phrase patterns derived from Academic Phrasebank |
> | [references/phrasebank-playbook.md](references/phrasebank-playbook.md) | You need hedging, transition, evidence, limitation, or future-work phrase families |
> | [references/style-guardrails.md](references/style-guardrails.md) | You need academic-style checks, paragraph/sentence checks, article use, register, or mechanics |
> ```

The "Open when" column answers "what situation demands this file" rather than "what topic does this file cover." That distinction matters: a topic label invites loading the file on vague relevance; a situation trigger fires only when the agent is actually at that decision point.

### R08 — Patterns over theory

R08 says to teach what to do in specific situations, not abstract concepts. Two patterns in this repo demonstrate this concretely.

**Diagnostic ordering**: `nature-polishing` could say "fix the most important problems first." Instead it gives a typed evaluation chain that the agent can follow left-to-right:

> Real quote from `skills/nature-polishing/SKILL.md:127-129`:
>
> ```
> Prioritize in this order:
>
> `paper type -> section job -> paragraph logic -> claim/evidence/boundary -> sentence polish`
> ```

An agent applying this does not decide what "important" means — it runs the chain and stops at the leftmost failing step.

**Explicit permission tiers**: The AI-ethics section does not say "be careful with AI." It maps each use case to Green/Yellow/Red with one example per cell:

> Real quote from `skills/nature-polishing/SKILL.md:350-370`:
>
> ```markdown
> `Green`: generally acceptable with author verification
>
> - improve grammar, clarity, concision, or tone
> - generate outline options or paragraph structures
> - produce alternative titles or abstract phrasings
> - summarize literature for categorization, not as a substitute for reading
> - translate with terminology and hedging checks
>
> `Yellow`: allowed only with strong human control
>
> - explain methods or results for wording support
> - draft reviewer-response frameworks that are then checked line by line
> - help with code or statistics explanations only if outputs are reproduced and validated
>
> `Red`: generally inappropriate
>
> - ask AI to draft the paper's core argument from scratch
> - insert AI-generated references, data, or claims without checking them
> - upload unpublished manuscripts, sensitive data, or peer-review material to public models
> - use AI to fabricate, manipulate, or conceal substantive image creation
> ```

Each item is a specific action, not a principle. An agent (or user) can check any planned action against the list without interpretation.

## Worth adopting

**Pattern: Multilingual trigger phrases in `description` for audience-specific skills.**
Evidence: `skills/nature-response/SKILL.md:7`, `skills/nature-reader/SKILL.md:2-3`.
Chinese query idioms (`审稿意见回复`, `中英文对照`) appear directly in the `description` field alongside their English equivalents.
Why it would be a useful rule: skill auto-loading depends on matching user utterances; when a skill targets multilingual users, description fields containing only English phrases will miss triggers from users querying in their primary language, even when the skill body explicitly supports them.

**Pattern: `## Output format` with a literal template in every skill.**
Evidence: `skills/nature-response/SKILL.md:63-89`, `skills/nature-data/SKILL.md:76-91`.
Both skills define a copy-pasteable text block with every field name present as a label, not a description.
Why it would be a useful rule: scoring already penalizes missing output-format sections in skills (−10); a rule that requires a *literal template* (not just a section heading) would close the gap between "defined" and "machine-parseable output."
