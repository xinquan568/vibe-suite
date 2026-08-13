---
slug: tech-leads-club-agent-skills
repo: tech-leads-club/agent-skills
audited: 2026-05-13
commit_sha: HEAD
score: 93
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
  - R33
  - R34
  - R35
---

# Exemplar: tech-leads-club/agent-skills

**Score**: 93/100  |  **Date**: 2026-05-13  |  **Commit**: `HEAD`

78-skill monorepo (Claude Code, Cursor, Copilot, Windsurf, and 15 other agents) with a CLI installer and MCP server. Notable for corpus-wide description discipline and disciplined reference offloading that keeps skill bodies under budget.

## Per-rule evidence

### R04 — Description as trigger

Every skill in this corpus treats the `description` field as a routing key. Three examples from 100/100-scoring skills show the pattern at its tightest:

> `packages/skills-catalog/skills/(monitoring)/sentry/SKILL.md`, line 3:
>
> ```
> description: Inspect Sentry issues, summarize production errors, and pull health
> data via the Sentry API (read-only). Use when user says "check Sentry", "what
> errors in production?", "summarize Sentry issues", "recent crashes", or
> "production error report". Requires SENTRY_AUTH_TOKEN. Do NOT use for setting
> up Sentry SDK, configuring alerts, or non-Sentry error monitoring.
> ```

> `packages/skills-catalog/skills/(architecture)/domain-analysis/SKILL.md`, line 3:
>
> ```
> description: Maps business domains and suggests service boundaries in any
> codebase using DDD Strategic Design. Use when asking "what are the domains in
> this codebase?", "where should I draw service boundaries?", "identify bounded
> contexts", "classify subdomains", "DDD analysis", or analyzing domain cohesion.
> Do NOT use for grouping existing components into domains (use
> domain-identification-grouping) or dependency analysis (use coupling-analysis).
> ```

What elevates these past mediocre descriptions: "Use when" clauses quote actual user phrases verbatim ("check Sentry", "what are the domains in this codebase?"), not reformulations. "Do NOT use for" clauses name specific sibling skills, not abstract categories. With 78 skills in the corpus, ambiguous trigger overlap is a real routing hazard — these descriptions cut it off at the description field.

The pattern is codified in CLAUDE.md as a mandatory contributor requirement (see R33 section below), which explains the consistency.

### R05 — Under 500 lines

CLAUDE.md states the rule and wires it to a structural mechanism:

> `CLAUDE.md`, line 122:
>
> ```
> Keep `SKILL.md` under 500 lines; offload reference material to `references/`.
> ```

Skills above ~200 lines use explicit navigation pointers to named `references/` files rather than inlining content. From ai-pricing:

> `packages/skills-catalog/skills/(gtm)/ai-pricing/SKILL.md`, line 223:
>
> ```
> For hybrid pricing, BYOK, margin management, tier design, GTM impact, migration,
> competitive analysis, anti-patterns, and experimentation read
> `references/implementation-guide.md`.
> ```

And at line 240:

> ```
> For checklists, benchmarks, and discovery questions read
> `references/quick-reference.md` when you need detailed reference.
> ```

The pointer names the destination file and scopes what's in it. An agent can decide mid-task whether it needs the implementation guide or just the quick-reference — it doesn't have to load both.

### R06 — Code examples must be runnable

The `sentry` skill backs every workflow step with an actual shell command. From the list-issues section:

> `packages/skills-catalog/skills/(monitoring)/sentry/SKILL.md`, lines 43–52:
>
> ```bash
> python3 "$SENTRY_API" \
>   list-issues \
>   --org {your-org} \
>   --project {your-project} \
>   --environment prod \
>   --time-range 24h \
>   --limit 20 \
>   --query "is:unresolved"
> ```

`SENTRY_API` is defined earlier in the file so the variable is available before first use. The skill provides five numbered task sections (list-issues, resolve short ID, issue detail, issue events, event detail) each with its own runnable block. A golden test input block at lines 121–127 gives concrete fixture values. Nothing requires translation before execution.

### R07 — Scope note when related skills exist

Two complementary mechanisms carry scope. First, inline negative routing in the description (see R04 section above — `domain-analysis` names `domain-identification-grouping` and `coupling-analysis` by slug). Second, a structured "Related Skills" table closes skills with multiple adjacent neighbors:

> `packages/skills-catalog/skills/(gtm)/ai-pricing/SKILL.md`, lines 244–253:
>
> ```markdown
> ## Related Skills
>
> | Skill | Relationship to AI Pricing |
> |---|---|
> | positioning-icp | ICP determines willingness-to-pay and which charge metric resonates |
> | sales-motion-design | Pricing model dictates the sales motion, comp structure, and org design |
> | solo-founder-gtm | Solo founders need the simplest viable pricing; start with one tier and iterate |
> | gtm-metrics | Unit economics (CPT, CPR, CPAM) feed directly into pricing decisions |
> | expansion-retention | Pricing structure determines expansion levers (usage growth, tier upgrades, new products) |
> | gtm-engineering | Billing infrastructure must support the chosen pricing model (metering, credits, invoicing) |
> ```

The second column ("Relationship to AI Pricing") explains *why* each neighbor is adjacent. This prevents an agent from loading all GTM skills when the task only touches one edge of the graph.

### R08 — Patterns over theory

The GTM skills teach decision logic via flowchart and table, not prose. The charge-metric selection section in ai-pricing is the sharpest example:

> `packages/skills-catalog/skills/(gtm)/ai-pricing/SKILL.md`, lines 39–61:
>
> ```
> START HERE
>     |
>     v
> Can the customer measure a specific business outcome
> from your product? (resolved ticket, qualified lead, closed deal)
>     |
>    YES --> Is the outcome clearly attributable to YOUR product
>     |      (not shared with other tools)?
>     |          |
>     |         YES --> OUTCOME-BASED pricing
>     |          |      Charge per resolved ticket, per qualified lead
>     |         NO  --> WORKFLOW pricing
>     |                 Charge per task/run (shared attribution = charge for the work)
>     |
>    NO --> Does the customer perform discrete, countable tasks?
>     |      (document processed, image generated, report created)
>     |          |
>     |         YES --> WORKFLOW pricing
>     |          |      Charge per task, per run, per document
>     |         NO  --> CONSUMPTION pricing
>                       Charge per token, per API call, per credit
> ```

Three binary questions reach a leaf. The same skill's troubleshooting section (lines 233–236) follows: symptom → cause → fix, one row each. No preamble — every row is independently actionable.

### R33 — Include build/run command

> `CLAUDE.md`, lines 56–79:
>
> ```bash
> # Setup
> npm ci && npm run build
>
> # Development
> npm run start:dev:cli          # Run CLI interactively (tsx, no build needed)
> npm run start:dev:mcp          # Build MCP and open Inspector
> SKILLS_CDN_REF=main npm run dev -- install  # Test CLI against local registry
>
> # Build & Test
> npm run build                  # Build all packages (Nx)
> npm run test                   # Run all tests (requires Node --experimental-vm-modules)
>
> # Skills
> npm run generate:data          # Regenerate skills-registry.json + marketplace data
> npm run scan                   # Security scan (snyk-agent-scan, incremental; requires SNYK_TOKEN)
> nx g @tech-leads-club/skill-plugin:skill {name} --category={cat}  # Create new skill
> ```

Commands are grouped by phase (setup, dev, build+test, skills), each annotated. The `SKILLS_CDN_REF=main` override for testing against a local registry is the kind of non-obvious detail that prevents a debugging cycle — naming it inline means an agent finds it without searching.

### R34 — Include test command

> `CLAUDE.md`, line 67:
>
> ```bash
> npm run test                   # Run all tests (requires Node --experimental-vm-modules)
> ```

The inline comment is load-bearing: Jest 30 + ts-jest with ESM-only modules fails without `NODE_OPTIONS='--experimental-vm-modules'`. Documenting the requirement on the same line as the command means the flag cannot be missed by an agent quoting the command.

### R35 — Include architecture overview

> `CLAUDE.md`, lines 83–98 (excerpt):
>
> ```
> **Nx monorepo** with independent versioning and conventional commits.
>
> ### Packages
>
> - **`packages/cli`** — `@tech-leads-club/agent-skills`. The user-facing installer.
>   Dual-mode: interactive TUI (React + Ink) and non-interactive CLI (Commander.js).
>   Entry: `src/index.ts`. Business logic in `src/services/` (registry fetching,
>   skill installation, lockfile management, agent configs).
> - **`packages/skills-catalog`** — Skill definitions in
>   `skills/{(category)}/{skill-name}/SKILL.md` with YAML frontmatter.
>   `src/generate-registry.ts` produces `skills-registry.json` (committed, published
>   to npm, served via jsDelivr CDN).
>
> ### Key Flows
>
> **Skill installation**: CLI fetches `skills-registry.json` from CDN → downloads
> skill files (batched, 10 concurrent) to `~/.cache/agent-skillsls/` → installs
> via copy or symlink to agent-specific directory → records in
> `.agents/.skill-lock.json` (v2, Zod-validated, atomic writes).
> ```

Each package entry names its entry point file and primary services directory. "Key Flows" traces data movement end-to-end. An agent modifying skill installation knows to look at `src/services/` in the cli package; an agent modifying the registry knows `generate-registry.ts` in skills-catalog.

## Worth adopting

**Pattern: Encode NL quality constraints in CLAUDE.md so they govern agent-generated artifacts.** Evidence: `CLAUDE.md:124–132`. The "Skill Quality Standards" section requires any agent creating or modifying a skill to load the `skill-architect` skill first, with a verbatim description schema as fallback when that skill isn't installed. Why it would be a useful rule: the 50 Rules govern human-authored NL artifacts; a project that generates skills via AI agents needs those constraints at generation time. Encoding them in CLAUDE.md is the only surface that reaches the agent mid-task, before a bad description is committed. Proposed rule form: **Document NL quality constraints in CLAUDE.md for any project that generates NL artifacts programmatically.** Without it, automated skill generation bypasses the same quality gates that hand-authored skills must pass.
