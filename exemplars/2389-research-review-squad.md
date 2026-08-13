---
slug: 2389-research-review-squad
repo: 2389-research/review-squad
audited: 2026-05-13
commit_sha: b32f196f410c917367bd51887b24336fe065915f
score: 96
exemplifies:
  - R04
  - R05
  - R07
  - R08
  - R43
---

# Exemplar: 2389-research/review-squad

**Score**: 96/100  |  **Date**: 2026-05-13  |  **Commit**: `b32f196f410c917367bd51887b24336fe065915f`

A four-skill plugin that dispatches reviewer panels (expert auditors, first-impression personas, task-completion testers, nitpick pedants); notable for tight scope carving between skills, concrete agent prompt templates with annotated rationale, and correct parallel/sequential dispatch reasoning throughout.

## Per-rule evidence

### R04 — Description as trigger

Every skill description opens with "Use when" and packs three or more distinct trigger scenarios into a single compact sentence. The descriptions match the exact phrases a user would type.

> From `skills/experts/SKILL.md:3`:
>
> ```
> Use when a project needs multi-perspective review — pre-launch audit, post-refactor check, inherited codebase assessment, or periodic health check. Dispatches parallel expert reviewer agents with persona framing.
> ```

> From `skills/well-actually/SKILL.md:3`:
>
> ```
> Use when you want pedantic, nitpicky, opinionated feedback on a site or project — the kind of feedback you'd get from Hacker News commenters, typography snobs, grammar pedants, and standards purists. Finds the things that professional reviewers skip because they're "too minor."
> ```

What makes these strong: each description fires on a different user query ("ready to launch?", "what will people roast me for?") without overlapping the other skills. They are trigger maps, not feature summaries.

### R05 — Under 500 lines

All four skills are tightly scoped: `experts` is 186 lines, `normies` is 153, `regulars` is 189, `well-actually` is 148. Each covers exactly one review modality and cross-references the others rather than absorbing their content.

> From `skills/regulars/SKILL.md:1-12`:
>
> ```
> ---
> name: regulars
> description: Use when you want to verify a site works by having agents act as
>   real users completing common tasks — browsing, subscribing, purchasing,
>   searching. Each agent has a goal and clicks through the real flow using
>   browser MCP tools.
> ---
>
> # Regulars
>
> ## Overview
>
> Dispatch a panel of subagents, each role-playing a real user with a specific
> task to complete on the site. ... The organizing principle is **task
> completion** — can users do what they came to do?
>
> **This is NOT a QA test suite or expert audit.**
> ```

189 lines for a skill this specific is the right call. The line budget is preserved by sending users to `review-squad:experts` for anything outside task-completion scope rather than expanding this file.

### R07 — Scope note when related skills exist

Every skill opens its Overview with an explicit boundary statement naming the sibling skill that handles the adjacent case. The scope notes are not footer disclaimers — they appear in the second paragraph of each Overview section.

> From `skills/normies/SKILL.md:13-14`:
>
> ```
> **This is NOT a technical review.** The review-squad:experts skill handles
> code quality, SEO, accessibility compliance, etc. This skill answers:
> "Do real people understand my site?"
> ```

> From `skills/well-actually/SKILL.md:11-12`:
>
> ```
> **This is NOT a professional audit.** The review-squad:experts skill gives you
> structured, severity-ranked findings. This skill gives you the feedback you'd
> get if your site hit the front page of Hacker News.
> ```

> From `skills/regulars/SKILL.md:43`:
>
> ```
> Unlike review-squad:experts (fixed default panel) or review-squad:normies
> (fixed sophistication spectrum), regulars tasks are **site-specific**.
> ```

Three sibling skills, three distinct scope carving statements — each tells Claude not just what this skill does but which neighbor handles the adjacent case, eliminating ambiguity when skills are loaded together.

### R08 — Patterns over theory

Each skill provides ready-to-fill agent prompt templates annotated with "Critical elements" sections that name *why* each element matters, not just what it is. The skills also include filled-in example output templates and typed default panels by project or site category.

> From `skills/experts/SKILL.md:99-126` (agent prompt template with annotations):
>
> ```
> Every reviewer agent prompt MUST follow this structure:
>
> ```
> You are a [ROLE] reviewing a [PROJECT TYPE] [before launch / after refactor / etc.].
> Do NOT write any code — only research and report findings.
> ...
> Review the following and report issues ranked by severity
> (critical, important, minor):
>
> 1. [Area] — [What to check, where to look]
> ...
> ```
>
> **Critical elements:**
> - **Persona first** — "You are a [ROLE]" gives the agent expertise framing
> - **No-code guard** — "Do NOT write any code" prevents agents from fixing things
> - **Severity ranking** — Forces structured output (critical/important/minor)
> - **Numbered review areas** — 8-12 specific areas per reviewer, tailored to their expertise
> ```

> From `skills/experts/SKILL.md:44-53` (default panel, one of four project types):
>
> ```
> ### Web (static sites, SPAs, server-rendered apps)
>
> | # | Expert | Focus Areas |
> |---|--------|-------------|
> | 1 | **SEO Expert** | Meta tags, heading hierarchy, sitemap, robots.txt, URL structure, RSS, structured data |
> | 2 | **Accessibility Expert** | Semantic HTML, skip nav, ARIA, color contrast, keyboard nav, motion/animation |
> | 3 | **Mobile UX Expert** | Viewport, responsive CSS, touch targets (44x44px min), font sizes, overflow |
> ...
> ```

The pattern here is not "dispatch reviewer agents" (theory) but "here is the exact prompt structure, here is the default panel for your project type, here is the output template." Claude can execute this without interpretation.

### R43 — Parallel when independent, sequential when dependent

The dispatch decision is documented at two levels: each individual skill states its dispatch mode with the technical reason, and the CLAUDE.md overview table consolidates the full picture. The technical reason (browser MCP is a shared singleton) is stated every time the sequential constraint appears.

> From `skills/experts/SKILL.md:129-135`:
>
> ```
> Use the Agent tool with `run_in_background: true` for ALL reviewers. Dispatch
> all in a single message block for maximum parallelism.
>
> Agent(description="SEO expert site review", subagent_type="general-purpose",
>   run_in_background=true, prompt="...")
> Agent(description="Accessibility expert review", subagent_type="general-purpose",
>   run_in_background=true, prompt="...")
> ...all agents in one message block...
> ```

> From `skills/normies/SKILL.md:38`:
>
> ```
> **Sequential dispatch required.** Browser MCP tools share a single browser
> instance. Agents must run one at a time, not in parallel.
> ```

> From `skills/well-actually/SKILL.md:97`:
>
> ```
> **Sequential** if using browser MCP (shared browser instance). If a persona
> only needs code access (rare), it can run in parallel with a browser-using
> persona.
> ```

> From `CLAUDE.md:35-38`:
>
> ```
> ### Sequential vs Parallel Dispatch
> - **experts**: Parallel dispatch (agents read code independently)
> - **normies**: Sequential (shared browser instance)
> - **regulars**: Sequential (shared browser instance)
> - **well-actually**: Sequential for browser-using agents; code-only agents
>   can run in parallel
> ```

The constraint is stated in the individual skill *and* summarized in CLAUDE.md — so it is discoverable both when a single skill is loaded and when the overview is loaded. The reason (shared browser instance) is never omitted, which prevents "why not parallel?" questions from reopening the decision.

## Worth adopting

**Pattern: Annotated prompt template.** Each skill splits the agent prompt template into two parts: (1) the literal fill-in-the-blanks template, and (2) a "Critical elements" bulleted list explaining why each element is there. Evidence: `skills/experts/SKILL.md:119-126`, `skills/normies/SKILL.md:87-93`, `skills/regulars/SKILL.md:124-130`. Why it would be a useful rule: "Include a 'Critical elements' annotation block after any agent prompt template. Each bullet states one element and the failure mode it prevents." This converts a template into self-documenting guidance — an agent reading only the skill can understand both the what and the why without consulting external rules.

**Pattern: Dot-graph workflow encoding.** Workflows are encoded as `dot` language digraphs inside fenced code blocks (`\`\`\`dot`), not prose descriptions. Evidence: `skills/experts/SKILL.md:22-38`, `skills/normies/SKILL.md:23-35`. Why it would be a useful rule: "Encode multi-step workflows as `dot` digraphs instead of prose lists when the workflow has branching or loops. Prose lists can't represent 'if not done, loop back' clearly." The digraphs in this repo show the feedback loop (`"All done?" -> "As each completes, note key finding" [label="no"]`) unambiguously.
