---
slug: krodak-clickup-cli
repo: krodak/clickup-cli
audited: 2026-05-13
commit_sha: 48aeedb5a998df0fb4f5b4502dc01b5b645d8915
score: 95
exemplifies:
  - R01
  - R02
  - R04
  - R05
  - R06
  - R08
---

# Exemplar: krodak/clickup-cli

**Score**: 95/100  |  **Date**: 2026-05-13  |  **Commit**: `48aeedb5a998df0fb4f5b4502dc01b5b645d8915`

A three-skill plugin for the `cup` ClickUp CLI tool — notable for a 30-phrase description trigger list, zero filler prose, and runnable workflow examples organized by agent task type rather than command category.

## Per-rule evidence

### R04 — Description as trigger

The main skill's description field is not a summary of contents — it is a dense list of 30 specific action phrases that match real user queries, prefixed with "Triggers:" to make the intent explicit.

> Real quote from `skills/clickup-cli/SKILL.md:3`:
>
> ```
> description: 'Use when managing ClickUp tasks, sprints, or comments via the `cup` CLI tool. Triggers: task queries, status updates, sprint tracking, creating subtasks, posting comments, threaded replies, standup summaries, searching tasks, checking overdue items, assigning tasks, listing spaces and lists, opening tasks in browser, checking auth or config, setting custom fields, deleting tasks, managing tags, managing checklists, editing comments, task links, time tracking, attachments, file uploads, listing members, listing fields, duplicating tasks, bulk operations, goals, key results, saved filters, favorites.'
> ```

The internal skills are equally specific. `releasing-clickup-cli` says "Use when releasing a new version, bumping version, or verifying a release" — three concrete use cases, not one generic label:

> Real quote from `.agents/skills/releasing-clickup-cli/SKILL.md:3`:
>
> ```
> description: Publishes a new version of clickup-cli to npm, updates Homebrew tap, writes release notes, and syncs the agent skill. Use when releasing a new version, bumping version, or verifying a release.
> ```

What makes these exemplary rather than merely adequate: the main skill's description enumerates 30 distinct trigger surfaces. A fuzzy-matched description like "ClickUp task management" would compete with any other ClickUp-adjacent skill in the agent's context; 30 specific trigger phrases remove that ambiguity.

### R05 — Under 500 lines

Rather than one monolithic skill, the plugin splits concerns across three files: `skills/clickup-cli/SKILL.md` (389 lines), `.agents/skills/testing-clickup-cli/SKILL.md` (132 lines), `.agents/skills/releasing-clickup-cli/SKILL.md` (132 lines). Each stays well under the 500-line ceiling.

> Real quote from `.agents/skills/testing-clickup-cli/SKILL.md:1-6`:
>
> ```
> ---
> name: testing-clickup-cli
> description: Run and manage tests for clickup-cli. Covers unit tests, e2e tests against a real ClickUp workspace, and the test data setup. Use when running tests, adding test coverage, debugging test failures, or setting up test fixtures.
> metadata:
>   internal: true
> ---
> ```

The split is domain-driven — use, test, release — not arbitrary line-count trimming. Each skill loads only when needed, not on every agent turn, keeping context overhead proportional to the task.

### R06 — Code examples must be runnable

Every code block in the skill is a real bash command or real TypeScript, not pseudocode. The testing skill provides an exact Vitest mock setup with a project-specific constraint explained inline:

> Real quote from `.agents/skills/testing-clickup-cli/SKILL.md:76-86`:
>
> ```typescript
> const mockGetTask = vi.fn().mockResolvedValue({ id: 't1', name: 'Task' })
>
> vi.mock('../../../src/api.js', () => ({
>   ClickUpClient: vi.fn().mockImplementation(function () {
>     return { getTask: mockGetTask }
>   }),
> }))
> ```
>
> The `function` keyword (not arrow) is required for Vitest 4's `new` semantics.

The comment on line 86 documents a non-obvious constraint that breaks silently when violated. A generic `vi.mock(() => ({...}))` pseudocode would leave this gap unaddressed.

### R08 — Patterns over theory

The `skills/clickup-cli/SKILL.md` "Agent Workflow Examples" section organizes commands by agent task type ("Investigate a task", "Find tasks", "Make changes") rather than by command category. Each subsection is a copy-paste-ready sequence for a concrete situation:

> Real quote from `skills/clickup-cli/SKILL.md:258-266`:
>
> ```bash
> ### Investigate a task
>
> cup task abc123def                   # markdown summary
> cup subtasks abc123def               # child tasks (open only)
> cup subtasks abc123def --include-closed  # all child tasks
> cup comments abc123def               # discussion
> cup activity abc123def               # task + comments combined
> ```

There is no explanation of what `cup task` does internally. The pattern — here is a situation, here are the commands in sequence — is the entire content. R08 says teach what to do in specific situations, and this section does exactly that across 9 subsections totaling 80 lines.

### R01 — No vague quantifiers

The Flags & Conventions table replaces vague behavior descriptions with exact matching semantics. Rather than "intelligent status matching", the skill specifies the algorithm:

> Real quote from `skills/clickup-cli/SKILL.md:232`:
>
> ```
> | `--status` | Fuzzy matching: exact > starts-with > contains. Prints match to stderr |
> ```

"Exact > starts-with > contains" tells Claude the priority order when a status string matches multiple candidates — no inference required.

### R02 — Every line earns its tokens

The Output Modes table occupies 8 lines and eliminates an entire class of agent errors (adding `--json` on every command when piped output is already Markdown):

> Real quote from `skills/clickup-cli/SKILL.md:96-102`:
>
> ```
> | Context         | Default output        | Override          |
> | --------------- | --------------------- | ----------------- |
> | Terminal (TTY)  | Interactive picker UI | `--json` for JSON |
> | Piped / non-TTY | Markdown tables       | `--json` for JSON |
>
> - Default piped output is **Markdown** - optimized for agent context windows
> - `cup task <id>` outputs a Markdown summary when piped; use `--json` for the full raw API object
> ```

No prose explanation: the table states exact behavior, the bullet clarifies the agent-specific implication. Compare to an equivalent prose paragraph — this table takes fewer tokens and is easier for an agent to parse.

## Worth adopting

**Pattern: Irreversibility sentinel block.** Evidence: `skills/clickup-cli/SKILL.md:386-388`. The skill closes with a `## DELETE SAFETY` block separate from the command table row: "Always confirm with the user before running `cup delete`. This is a destructive, irreversible operation. Even when using `--confirm` flag, verify the task ID is correct with the user first." A dedicated terminal block for destructive operations survives out-of-order reading in a way that a table row marked "(DESTRUCTIVE)" does not. Why it would be a useful rule: irreversible operations deserve a named safety block at the end of the skill; the command table row marks them syntactically, but the sentinel block reinforces the confirmation behavior when the agent is deep in a workflow.

**Pattern: Agent context window rationale on default filter scope.** Evidence: `skills/clickup-cli/SKILL.md:242`. The `--all` flag row reads: "Default: my tasks only (smaller output for agent context windows)." Documenting *why* the default is narrow — context budget — teaches the agent to respect it rather than reflexively adding `--all`. Why it would be a useful rule: when a CLI tool has defaults tuned for agent use, document the agent-specific rationale in the flag description so the agent does not override the narrow default unnecessarily.
