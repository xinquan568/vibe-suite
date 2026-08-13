---
slug: AgriciDaniel-claude-ads
repo: AgriciDaniel/claude-ads
audited: 2026-05-13
commit_sha: 402ba63b9af56c0573766fb0ae8d7b56dc13a674
score: 99
exemplifies:
  - R01
  - R04
  - R06
  - R07
  - R08
  - R10
  - R11
---

# Exemplar: AgriciDaniel/claude-ads

**Score**: 99/100  |  **Date**: 2026-05-13  |  **Commit**: `402ba63b9af56c0573766fb0ae8d7b56dc13a674`

A 19-skill, 10-agent paid advertising audit system that scores 99/100 by
combining quantified thresholds, explicit trigger phrases, paired fallback
examples, and on-demand reference loading — each a textbook application of
the rules it exemplifies.

## Per-rule evidence

### R01 — No vague quantifiers

Every metric in the skill bodies is expressed as a concrete threshold, not a
qualitative label. The Google sub-skill ships a seven-row key-thresholds table
that converts every vague concept ("good CTR", "acceptable quality score") into
three named bands with numeric boundaries.

> Real quote from `skills/ads-google/SKILL.md:146-157`:
>
> ```
> ## Key Thresholds
>
> | Metric | Pass | Warning | Fail |
> |--------|------|---------|------|
> | Quality Score (avg) | ≥7 | 5-6 | <5 |
> | CTR (Search) | ≥6.66% | 3-6.66% | <3% |
> | CVR (Search) | ≥7.52% | 3-7.52% | <3% |
> | CPC (Search) | ≤$5.26 | $5.26-8.00 | >$8.00 |
> | Wasted Spend | <10% | 10-20% | >20% |
> | Ad Strength | Good+ | Average | Poor |
> | Invalid Clicks | <5% | 5-10% | >10% |
> ```

What makes this strong rather than mediocre: each metric has three distinct
decision bands, not just a binary pass/fail — so the model can produce graded
output instead of a binary verdict that ignores borderline accounts.

### R04 — Description as trigger

Sub-skill descriptions function as routing contracts, not just summaries. They
list the exact phrases a user would type, so the orchestrator can delegate
accurately without guessing. The `ads-dna` description explicitly separates
structural description from trigger phrases with a labelled "Triggers on:" section.

> Real quote from `skills/ads-dna/SKILL.md:3-4`:
>
> ```
> description: "Brand DNA extractor for paid advertising. Scans a website URL to
> extract visual identity, tone of voice, color palette, typography, and imagery
> style. Outputs brand-profile.json to the current directory. Run before /ads create
> or /ads generate for brand-consistent creative. Triggers on: brand DNA, brand profile,
> extract brand, brand identity, brand colors, what is the brand voice, analyze brand,
> brand style guide."
> ```

> Real quote from `skills/ads-google/SKILL.md:3-5`:
>
> ```
> description: "Google Ads deep analysis covering Search, Performance Max, Display,
> YouTube, and Demand Gen campaigns. Evaluates 80 checks across conversion tracking,
> wasted spend, account structure, keywords, ads, and settings. Use when user says
> Google Ads, Google PPC, search ads, PMax, Performance Max, or Google campaign."
> ```

The `ads-google` description packs trigger phrases into the description field
itself using "Use when user says..." — a compact form that keeps the list
adjacent to the structural summary without needing a separate frontmatter key.

### R06 — Runnable examples

Both `creative-strategist.md` and `visual-designer.md` provide two `<example>`
blocks each: one for the happy path and one for the degraded/no-data path. The
tool-call sequence inside each example is concrete enough to replay without
modification.

> Real quote from `agents/creative-strategist.md:15-37`:
>
> ```
> <example>
> Context: brand-profile.json exists in current directory. ADS-AUDIT-REPORT.md also present.
> user: Create campaign concepts for our SaaS product, targeting Meta and Google.
> assistant: I'll read the brand profile and audit findings first, then generate concepts
> grounded in both brand identity and the specific gaps the audit identified.
> [Reads brand-profile.json]
> [Reads ADS-AUDIT-REPORT.md, notes creative fatigue on Meta, low CTR on branded search]
> [Reads ~/.claude/skills/ads/references/brand-dna-template.md for schema]
> [Reads ~/.claude/skills/ads/references/benchmarks.md for platform copy guidance]
> [Generates 3 campaign concepts addressing the audit-identified weaknesses]
> [Writes strategic concepts section to campaign-brief.md]
> commentary: Always read brand profile before generating. Audit results are optional
> but strongly improve concept targeting. Concepts must address real weaknesses,
> not generic angles.
> </example>
>
> <example>
> Context: Only brand-profile.json exists. No audit data.
> user: Generate campaign concepts for our e-commerce brand.
> assistant: No audit data found. I'll create broadly applicable concepts from the brand profile alone.
> [Reads brand-profile.json]
> [Reads brand-dna-template.md]
> [Generates 3-5 concepts covering different messaging angles: pain point, social proof,
> offer, demo, education]
> [Notes: "For more targeted concepts, run /ads audit first to identify specific weaknesses"]
> commentary: Always inform the user when working without audit data. The concepts will be
> less targeted but still brand-accurate.
> </example>
> ```

The pairing matters: example 1 establishes the full-data path; example 2
defines what degrades (targeting) and what must stay constant (brand accuracy),
and mandates a user-visible disclosure. A single example would leave the
degraded path underdefined.

### R07 — Scope notes

Sub-skills that should not be invoked directly carry `user-invokable: false`
in their frontmatter. Reference files are kept out of cold-start context by
an explicit load policy in the orchestrator.

> Real quote from `skills/ads-dna/SKILL.md:4`:
>
> ```
> user-invokable: false
> ```

> Real quote from `ads/SKILL.md:152-153`:
>
> ```
> ## Reference Files
>
> Load these on-demand as needed; do NOT load all at startup.
> ```

The reference section then lists 22 files with one-line purpose annotations,
making the on-demand intent actionable: the model knows both that lazy loading
is required and what each file covers before deciding to load it.

### R08 — Patterns over theory

The `creative-strategist` agent replaces abstract advice about image prompts
("avoid text") with two-column DO/DO NOT tables that list concrete instances.
Annotated good/bad prompt blocks show the consequence of ignoring the rules,
not just the rules themselves.

> Real quote from `agents/creative-strategist.md:148-190`:
>
> ```
> **DO (include these):**
> - Composition type: split-screen, diagonal, centered, full-bleed, stacked
> - Abstract data shapes: rising curve, ascending bars, glowing line arc, pulse wave
> - Colors by hex: `#09090B background`, `#22C55E glow`, `#FFFFFF accent`
> - Mood atmosphere: dark technical precision, minimal authority, stark contrast
> - Visual metaphor (not literal): empty void vs. data richness, flat line vs. explosive growth
> - Imagery style from `brand-profile.json imagery.style`
>
> **DO NOT (these cause hallucinated text):**
> - Font names of any kind (`Noto Serif`, `Inter`, `Helvetica`, etc.)
> - Specific text labels, data values, column/row content
> - Phrases like "text reading X", "headline saying Y", "label showing Z"
> - "Dashboard with columns showing [data]": use "abstract dashboard silhouette" instead
> - More than 80 words total
>
> **BAD prompt (will hallucinate "KEYWORISNG" style garble):**
> sleek SEO dashboard UI with keyword ranking data, bold typographic hierarchy with
> Noto Serif heading font, SERP data visualizations labeled 'Traffic Analytics',
> brand color #22C55E glowing chart lines
>
> **GOOD prompt (clean generation, copy zone reserved):**
> #09090B dark background, #22C55E accent glow, dark split-screen digital illustration,
> left: solitary blinking cursor in empty void, right: abstract dashboard silhouette
> with anonymous rising data curve, stark contrast, lower 30% minimal for copy overlay,
> dark mode digital illustration style, no cheesy stock photos
> ```

The annotated bad/good pair names the failure mode ("KEYWORISNG style garble")
and links it to a specific cause (font names), so the model can apply the rule
to novel prompts rather than just pattern-matching to the given example.

### R10 — Model specified in agent frontmatter

Agents declare `model:` explicitly, enabling the orchestrator to make
deliberate cost/quality trade-offs. The four creative agents use three different
models matched to task complexity: Opus for strategy (most reasoning), Sonnet
for generation and formatting (mid-tier), and Haiku implied for the
lowest-complexity role via the `maxTurns: 15` budget signal.

> Real quote from `agents/creative-strategist.md:1-10`:
>
> ```
> ---
> name: creative-strategist
> description: >
>   Campaign concept strategist for paid advertising. Reads brand-profile.json
>   and optional audit results to generate structured campaign concepts, messaging
>   pillars, and creative direction for each platform. Produces the strategic
>   sections of campaign-brief.md.
> model: opus
> maxTurns: 25
> tools: Read, Write, Glob
> ---
> ```

> Real quote from `agents/visual-designer.md:1-10`:
>
> ```
> ---
> name: visual-designer
> description: >
>   Visual ad creative specialist. Reads campaign-brief.md and brand-profile.json
>   to construct 5-component image generation prompts via banana MCP, organizes
>   outputs into ad-assets/ directories, and writes generation-manifest.json
>   for the format-adapter agent.
> model: sonnet
> maxTurns: 30
> tools: Read, Write, Bash, Glob
> ---
> ```

The model assignment is not uniform: strategy gets Opus, visual generation
gets Sonnet, and the format-adapter (validation only) gets a 15-turn cap that
signals Haiku-class effort. Differentiation by task complexity is visible in
the frontmatter without reading the body.

### R11 — maxTurns declared in agent frontmatter

Every agent in the repo declares `maxTurns`, and the values are spread across
three tiers matched to the task's depth: 15 for format validation (bounded
enumeration), 20-25 for generation and strategy (open-ended but scoped), and
30 for image generation (network-intensive with retries).

> Real quote from `ads/SKILL.md:242-245` (subagent listing):
>
> ```
> - `creative-strategist`: Campaign concepts from brand profile + audit results (Opus, maxTurns: 25)
> - `visual-designer`: Image generation with brand injection via generate_image.py (Sonnet, maxTurns: 30)
> - `copy-writer`: Headlines, CTAs, primary text within platform limits (Sonnet, maxTurns: 20)
> - `format-adapter`: Asset dimension validation and spec compliance reporting (Haiku, maxTurns: 15)
> ```

The orchestrator's subagent listing repeats the model and maxTurns from each
agent's frontmatter, making the cost model visible at the call site — not just
inside the agent file.

## Worth adopting

**Pattern: Binary "when to show / when to skip" blocks for output appendages.**
Evidence: `ads/SKILL.md:115-149` — the community footer section enumerates
every command in two lists: one where the footer appears (major deliverables),
one where it does not (calculators, intermediate pipeline steps, error messages).
The enumeration is exhaustive; the model cannot drift into showing the footer
after a quick `/ads math` call because that case is named in the skip list.
Why it would be a useful rule: any skill that appends a footer, disclaimer,
or next-steps block needs an explicit binary contract for when to suppress it —
an ad hoc "show at the end of major outputs" instruction causes inconsistent
output that no downstream parser can rely on.

**Pattern: Hero-first generation with explicit consistency anchor.**
Evidence: `agents/visual-designer.md:142-148` — the image generation workflow
names the first generated asset the "consistency anchor" and passes it as a
reference to all subsequent generations in the campaign. The manifest records
`consistencyAnchor` as a first-class field so the format-adapter can trace
which image set a variation belongs to.
Why it would be a useful rule: multi-asset agent workflows that produce a
family of related outputs benefit from designating one output as the canonical
reference and propagating it explicitly — rather than relying on implicit
ordering or re-reading earlier outputs. The anchor field makes the dependency
machine-readable.
