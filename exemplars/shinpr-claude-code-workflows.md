---
slug: shinpr-claude-code-workflows
repo: shinpr/claude-code-workflows
audited: 2026-05-13
commit_sha: 905dbe85aae1ff8d359639a2b348f830ed2dbcd9
score: 91
exemplifies:
  - R04
  - R06
  - R07
  - R08
  - R12
---

# Exemplar: shinpr/claude-code-workflows

**Score**: 91/100  |  **Date**: 2026-05-13  |  **Commit**: `905dbe85aae1ff8d359639a2b348f830ed2dbcd9`

A 51-artifact plugin (24 agents, 27 skills) for orchestrated software development workflows; notable for trigger-exact skill descriptions, concrete conflict-detection examples, and tight scope fencing on every agent.

## Per-rule evidence

### R04 — Description as trigger

The skill files consistently pack 3+ action-phrase triggers in one sentence rather than naming what the skill "is about." Every description names the exact invocation context — what the user is doing, not what the skill contains.

> From `skills/subagents-orchestration-guide/SKILL.md` (frontmatter, line 3):
>
> ```
> description: Guides subagent coordination through implementation workflows. Use when
> orchestrating multiple agents, managing workflow phases, or determining autonomous
> execution mode.
> ```

> From `skills/task-analyzer/SKILL.md` (frontmatter, line 3):
>
> ```
> description: Performs metacognitive task analysis and skill selection. Use when
> determining task complexity, selecting appropriate skills, or estimating work scale.
> ```

What makes these exemplary rather than adequate: both descriptions end with three parallel "Use when" clauses that mirror the exact phrases a user or orchestrator would write ("determining task complexity", "managing workflow phases"). A mediocre description would read "Provides task analysis and skill selection guidance" — accurate but useless as a trigger.

---

### R06 — Code examples must be runnable

`agents/design-sync.md` dedicates lines 213–289 to detection pattern examples, each showing two real document snippets and the exact classifier output. These are not "for example, if a conflict exists, report it" — they are concrete before/after pairs a reader can mechanically match against real docs.

> From `agents/design-sync.md` (lines 251–259):
>
> ```
> ### High confidence: exact_string (numeric parameter)
> ```
> # Source Design Doc
> Max retry count: 3
>
> # Other Design Doc
> Max retry count: 5
> ```
>
> ### Medium confidence: same_endpoint_role
> ```
> # Source Design Doc
> POST /api/v2/orders → handler: OrderController.create
>
> # Other Design Doc
> POST /api/v1/orders → handler: OrderController.submit
> ```
> → confidence: medium, match_basis: same_endpoint_role, reason: "Same service
>   (OrderController), same HTTP method (POST), same resource path (/orders) with
>   differing version prefix and handler method."
> ```

The file also includes a "Not reported" counterexample (lines 281–289) that shows a case which looks like a conflict but lacks structural evidence and should be silently skipped. Including the negative example is what separates a precise spec from an ambiguous one.

---

### R07 — Scope note when related skills/agents exist

`agents/design-sync.md` carries two distinct scope sections: "Scope Distinction" (what this agent does vs. related single-document review) and "Out of Scope" (explicit list of things it refuses). Without both, an orchestrator would route single-document quality checks here and get wrong results.

> From `agents/design-sync.md` (lines 51–59):
>
> ```
> ## Scope Distinction
>
> - **This agent**: Cross-document consistency verification between Design Docs
> - **Single-document review**: Document quality, completeness, and rule compliance
>
> ## Out of Scope
>
> - Consistency checks with PRD/ADR
> - Quality checks for single documents (use single-document review)
> - Automatic conflict resolution
> ```

`agents/acceptance-test-generator.md` does the same for AC filtering (lines 63–76): explicit Include/Exclude tables with one-line rationale per excluded category ("Performance metrics → Non-deterministic in CI, defer to load testing"). The rationale matters because it tells the agent *why* to exclude, not just *what* to exclude.

---

### R08 — Patterns over theory

`skills/subagents-orchestration-guide/SKILL.md` teaches the What-vs-How boundary with a two-column Bad/Good table (lines 66–69) instead of a paragraph about "delegation principles." The table forces the reader to match a situation to the correct action.

> From `skills/subagents-orchestration-guide/SKILL.md` (lines 66–69):
>
> ```
> | | Bad (orchestrator prescribes how) | Good (orchestrator passes what) |
> |---|---|---|
> | quality-fixer | "Run these checks: 1. lint 2. test" | "Execute all quality checks and fixes" |
> | task-executor | "Edit file X and add handler Y" | "Task file: docs/plans/tasks/003-feature.md" |
> ```

`skills/task-analyzer/SKILL.md` applies the same approach to task-type identification (lines 43–49): one row per task type with Characteristics and Key Skills columns, making the skill selection algorithm mechanical rather than judgment-based. The entire skill is tables; there is no introductory paragraph explaining "why task analysis matters."

---

### R12 — Output format defined in body

`agents/design-sync.md` defines a complete output format (lines 139–211) using named delimited sections (`[METADATA]`, `[SUMMARY]`, `[CONFIRMED_CONFLICTS]`, `[CANDIDATE_CONFLICTS]`, `[RECOMMENDATIONS]`) with every field named, typed, and placed. The format handles the three distinct output states (conflicts found, candidates only, no conflicts) without ambiguity.

> From `agents/design-sync.md` (lines 141–172, abridged to show structure):
>
> ```
> [METADATA]
> review_type: design-sync
> source_design: [source Design Doc path]
> analyzed_docs: [number of Design Docs verified]
> analysis_date: [execution datetime]
> [/METADATA]
>
> [CONFIRMED_CONFLICTS]
> ## Conflict-001
> severity: critical
> confidence: high
> match_basis: exact_string
> type: Type definition mismatch
> source_file: [source file]
> source_location: [section/line]
> source_value: |
>   [content in source file]
> target_file: [file with conflict]
> target_location: [section/line]
> target_value: |
>   [conflicting content]
> recommendation: |
>   [Recommend unifying to source file's value]
> [/CONFIRMED_CONFLICTS]
> ```

`agents/acceptance-test-generator.md` extends this to machine-parseable JSON for the generation report (lines 209–247), including a field contract: "`generatedFiles.integration` and `generatedFiles.e2e` are always present as keys. Value is a file path string when generated, `null` when not generated." Callers can rely on the contract without inspecting the agent's reasoning.

---

## Worth adopting

**Pattern: Handoff Contract sections in orchestration skills.**
Evidence: `skills/subagents-orchestration-guide/SKILL.md:354–406` (HC-01 through HC-06).
Each HC names the producer, the consumer, the exact fields to pass, and any orchestrator verification steps required before calling the next agent. Current rules say to pass data between agents (R12 covers output format) but say nothing about how the *receiving* prompt should be constructed or verified. A rule of the form: **When a skill defines agent hand-offs, document each as a named contract: producer → consumer, required fields, and orchestrator verification steps.** would reduce "dropped field" bugs in orchestrated flows.

**Pattern: Early Termination Condition before main workflow.**
Evidence: `agents/design-sync.md:65–70`.
The agent declares a named termination condition — "When target Design Docs count is 0, skip investigation and immediately terminate with NO_CONFLICTS status" — before the workflow steps, not inside them. This prevents wasted work and avoids the agent reading 20 files before discovering there's nothing to compare. No current rule mandates early-exit declarations; a short rule like **Declare early termination conditions before the main workflow. Name the condition, the trigger, and the output state.** would generalize this.

**Pattern: Scope constraint suffix injected into every sub-agent prompt.**
Evidence: `skills/recipe-implement/SKILL.md:85–92`.
The skill mandates appending `[SYSTEM CONSTRAINT] This agent operates within implement skill scope.` to every sub-agent invocation. This prevents sub-agents from importing unrelated skills or drifting scope when running inside a long autonomous flow. Not currently codified in the 50 Rules.
