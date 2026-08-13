---
slug: softaworks-agent-toolkit
repo: softaworks/agent-toolkit
audited: 2026-05-13
commit_sha: 3027f20f3181758385a1bb8c022d4041dfb4de84
score: 90
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: softaworks/agent-toolkit

**Score**: 90/100  |  **Date**: 2026-05-13  |  **Commit**: `3027f20f3181758385a1bb8c022d4041dfb4de84`

A 43-skill, 6-agent collection where every skill file uses progressive disclosure (SKILL.md entry point + `references/` subdirectory) and nearly all include runnable code or concrete Before/After examples rather than abstract descriptions.

## Per-rule evidence

### R04 — Description as trigger

Skills in this collection write descriptions that enumerate explicit trigger phrases and usage conditions, so the agent can route without reading the full file. The `mermaid-diagrams` skill packs nine diagram-type keywords, five action verbs, and a fallback condition into a single description field:

> Real quote from `skills/mermaid-diagrams/SKILL.md:3-8`:
>
> ```
> description: Comprehensive guide for creating software diagrams using Mermaid syntax. Use when
>   users need to create, visualize, or document software through diagrams including class diagrams
>   (domain modeling, object-oriented design), sequence diagrams (application flows, API
>   interactions, code execution), flowcharts (processes, algorithms, user journeys), entity
>   relationship diagrams (database schemas), C4 architecture diagrams (system context, containers,
>   components), state diagrams, git graphs, pie charts, gantt charts, or any other diagram type.
>   Triggers include requests to "diagram", "visualize", "model", "map out", "show the flow", or
>   when explaining system architecture, database design, code structure, or user/application flows.
> ```

What makes this a strong example: the description names the retrieval condition ("Triggers include requests to…") explicitly rather than leaving the agent to infer it. A description that says only "Mermaid diagram creation" leaves ambiguous whether it should activate for "show me the flow" — this one does not.

The `ascii-ui-mockup-generator` agent raises the bar further by embedding full structured invocation examples with user utterance and commentary directly in the description field:

> Real quote from `agents/ascii-ui-mockup-generator.md:3`:
>
> ```
> description: Use this agent when you need to visualize UI concepts through ASCII mockups before
>   implementation. Examples: <example>Context: User has an idea for a dashboard layout with data
>   tables and charts. user: 'I want to create a dashboard that shows user analytics with a sidebar
>   navigation, main content area with charts, and a data table below' assistant: 'I'll use the
>   ascii-ui-mockup-generator agent to create multiple ASCII mockup variations for your dashboard
>   concept.' <commentary>The user wants to visualize a UI concept, so use the
>   ascii-ui-mockup-generator to create multiple ASCII representations they can choose
>   from.</commentary></example> ...
> ```

The `<example>` / `<commentary>` markup in the description is the Claude Code schema for subagent dispatch examples. Embedding two such examples means the dispatch model has concrete utterance–action pairs, not just a keyword list.

---

### R05 — Body length

The top-scoring skills keep SKILL.md compact by offloading deep content to `references/` files. `mermaid-diagrams/SKILL.md` runs 218 lines: one Quick Start block per major diagram type plus a selection guide, then a pointer section to seven reference files for depth:

> Real quote from `skills/mermaid-diagrams/SKILL.md:136-147`:
>
> ```
> ## Detailed References
>
> For in-depth guidance on specific diagram types, see:
>
> - **[references/class-diagrams.md](references/class-diagrams.md)** - Domain modeling, relationships
>   (association, composition, aggregation, inheritance), multiplicity, methods/properties
> - **[references/sequence-diagrams.md](references/sequence-diagrams.md)** - Actors, participants,
>   messages (sync/async), activations, loops, alt/opt/par blocks, notes
> - **[references/flowcharts.md](references/flowcharts.md)** - Node shapes, connections, decision
>   logic, subgraphs, styling
> - **[references/erd-diagrams.md](references/erd-diagrams.md)** - Entities, relationships,
>   cardinality, keys, attributes
> - **[references/c4-diagrams.md](references/c4-diagrams.md)** - System context, container,
>   component diagrams, boundaries
> - **[references/architecture-diagrams.md](references/architecture-diagrams.md)** - Cloud services,
>   infrastructure, CI/CD deployments
> - **[references/advanced-features.md](references/advanced-features.md)** - Themes, styling,
>   configuration, layout options
> ```

The split is disciplined: the 218-line SKILL.md covers the 90% case (pick diagram type, copy a working example); all syntax edge cases live in files that are read only when needed. Of the 43 skills, 28 use a `references/` subdirectory — this pattern is applied consistently across the collection, not just in one flagship skill.

---

### R06 — Runnable examples

The `humanizer` skill contains 24 numbered Before/After example pairs, each with an exact "Words to watch" list, a problem statement, and two verbatim text blocks. The examples are not illustrative paraphrases; they are real text lifted from Wikipedia edits that triggered the original pattern identification. Pattern 1:

> Real quote from `skills/humanizer/SKILL.md:74-85`:
>
> ```
> ### 1. Undue Emphasis on Significance, Legacy, and Broader Trends
>
> **Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/
> key role/moment, underscores/highlights its importance/significance, reflects broader,
> symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for,
> marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point,
> indelible mark, deeply rooted
>
> **Before:**
> > The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal
> > moment in the evolution of regional statistics in Spain. This initiative was part of a broader
> > movement across Spain to decentralize administrative functions and enhance regional governance.
>
> **After:**
> > The Statistical Institute of Catalonia was established in 1989 to collect and publish regional
> > statistics independently from Spain's national statistics office.
> ```

What makes this strong: the "Words to watch" list is a grep-ready token inventory, not a vague category label. An agent processing a Wikipedia draft can match "marking a pivotal moment" to pattern 1 without any interpretation. The full example (24 patterns × Before/After) means almost any AI-writing anti-pattern has a concrete reference point.

The `mermaid-diagrams` skill demonstrates the same principle for code: all four Quick Start examples are complete, renderable Mermaid blocks (class, sequence, flowchart, ERD), not skeleton stubs with `// ... your content here`:

> Real quote from `skills/mermaid-diagrams/SKILL.md:84-99`:
>
> ```mermaid
> sequenceDiagram
>     participant User
>     participant API
>     participant Database
>
>     User->>API: POST /login
>     API->>Database: Query credentials
>     Database-->>API: Return user data
>     alt Valid credentials
>         API-->>User: 200 OK + JWT token
>     else Invalid credentials
>         API-->>User: 401 Unauthorized
>     end
> ```

Copy-paste and render — no placeholders. A user who has never used Mermaid gets a working login flow on the first try.

---

### R07 — Scope notes

The `frontend-to-backend-requirements` skill draws a hard boundary between what the frontend developer owns and what backend owns, expressed as a two-column table rather than prose:

> Real quote from `skills/frontend-to-backend-requirements/SKILL.md:28-36`:
>
> ```
> | Frontend Owns | Backend Owns |
> |---------------|--------------|
> | What data is needed | How data is structured |
> | What actions exist | Endpoint design |
> | UI states to handle | Field names, types |
> | User-facing validation | API conventions |
> | Display requirements | Performance/caching |
> ```

This scope note prevents a common misuse: a developer pasting in a JSON schema or specifying REST endpoints when the skill is intended for describing data _needs_. The table works as a runtime guard — the skill body references it early, before the workflow steps, so an agent sees the constraint before it starts writing output.

---

### R08 — Patterns over theory

The `humanizer` skill is a pure pattern catalog. There is no introductory theory about "what AI writing is" or "why it occurs" — the skill opens with a numbered task list and immediately enters the pattern section. Each of the 24 patterns follows an identical tripartite shape: `Words to watch` (tokens), `Problem` (one sentence on the mechanism), `Before/After` (verbatim text pair). Pattern 7:

> Real quote from `skills/humanizer/SKILL.md:159-172`:
>
> ```
> ### 7. Overused "AI Vocabulary" Words
>
> **High-frequency AI words:** Additionally, align with, crucial, delve, emphasizing, enduring,
> enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective),
> landscape (abstract noun), pivotal, showcase, tapestry (abstract noun), testament, underscore
> (verb), valuable, vibrant
>
> **Problem:** These words appear far more frequently in post-2023 text. They often co-occur.
>
> **Before:**
> > Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An
> > enduring testament to Italian colonial influence is the widespread adoption of pasta in the
> > local culinary landscape, showcasing how these dishes have integrated into the traditional diet.
>
> **After:**
> > Somali cuisine also includes camel meat, which is considered a delicacy. Pasta dishes,
> > introduced during Italian colonization, remain common, especially in the south.
> ```

The `frontend-to-backend-requirements` skill uses the same logic for its anti-pattern section — three Bad/Good pairs with exact text, not abstract descriptions of the mistake:

> Real quote from `skills/frontend-to-backend-requirements/SKILL.md:140-152`:
>
> ```
> ### Bad (Dictating Implementation)
> > "I need a GET /api/contracts endpoint that returns an array with fields: id, title, status,
> > created_at"
>
> ### Good (Describing Needs)
> > "I need to show a list of contracts. Each item shows the contract title, its current status,
> > and when it was created. User should be able to filter by status."
>
> ### Bad (Assuming Structure)
> > "The provider object should be nested inside the contract response"
>
> ### Good (Describing Relationship)
> > "For each contract, I need to show who the provider is (their name and maybe logo)"
> ```

Both skills show the anti-pattern before the correct pattern. An agent reading this can recognize a bad invocation and self-correct without needing to understand the theory behind the distinction.

---

## Worth adopting

**Pattern: Invocation examples with `<example>` / `<commentary>` markup in agent descriptions.** Evidence: `agents/ascii-ui-mockup-generator.md:3` (two full `<example>` blocks with `Context:`, `user:`, `assistant:`, and `<commentary>` tags in the `description:` field). Why it would be a useful rule: embedding structured dispatch examples directly in the agent description gives the routing model two concrete utterance–action pairs rather than a keyword list, reducing false-negative dispatch; the `<commentary>` tag explains *why* the agent was chosen, not just *that* it was chosen — this context is visible to the sub-agent when it loads its own definition.
