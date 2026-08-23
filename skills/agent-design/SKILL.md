---
name: agent-design
description: Design advisor agents — file format, value-driven system prompts, model tier selection, tool and working-directory scoping, budget/turn caps, and choosing between a consultative advisor and a batch subagent. Use when creating, editing, or reviewing an advisor definition.
---

# Agent Design

An advisor agent is a project-scoped consultative persona: a markdown file that gives
one stable point of view its own system prompt, its own tool restrictions, and its own
model tier. Advisor files live at `.vibe-suite/agents/<name>.md`. The advisor engine
(`scripts/advisor_cli.py`) makes each advisor callable from either client as
`mcp__<name>__<tool_name>` by registering it as an MCP server twice over — in
`.mcp.json` for Claude and in `.codex/config.toml` for Codex.

Keep one sentence in mind the whole time you design one:

> **Advisors judge work. They do not do work.**

Every field in the format exists to hold that line — read-only tools, small turn caps,
tight budgets, narrow working directories. If your design keeps fighting those limits,
you are building the wrong thing (see the next section).

## Interaction models: batch fan-out specialists vs on-demand advisors

This is the first decision, before any file gets written. There are three mechanisms
that look similar and behave completely differently:

**Batch fan-out specialist (subagent via the Task tool).** A one-shot executor. You
hand it a focused chunk of work; it runs in an isolated context, returns its result,
and disappears. Nothing persists between invocations. Because each launch is
independent, you can fan out several at once — five files to survey, five parallel
subagents. This model fits *jobs*: research a question, refactor a file, run a probe,
sweep a directory. The output is the work itself.

**On-demand consultative advisor.** A persona that persists — one stable point of
view you come back to for consultation throughout a project's life. It keeps its own system prompt, its
own tool allowlist, its own model tier, and it remembers earlier consultations through
a per-agent timeline directory. You do not fan advisors out; you *return* to them. The
output is an opinion about work someone else did.

**Skill.** Static knowledge or convention, loaded into context on demand. No model
invocation at all. If the guidance never needs to look at your specific code — it is
just a rulebook — it should be a skill, not any kind of agent.

The rule of thumb:

- An *opinion you'd want from a person* → advisor.
- A *job you'd hand off* → subagent.
- A *rulebook* → skill.

When each fits, concretely:

| Situation | Mechanism | Why |
|---|---|---|
| "Survey these 8 modules for dead exports" | Fan-out subagents | Parallel, isolated, results merge; no memory needed |
| "Does this API design match our priorities?" | Advisor | Judgement against a held value system; asked again next month |
| "Rewrite this file to the new style" | Subagent | It is work, and it needs write access |
| "Is this doc honest about its limitations?" | Advisor | Stable critical perspective, consulted per doc |
| "What is our commit-message convention?" | Skill | Static; no code reading required |

The failure mode to avoid: building an advisor and then giving it `Edit`, twenty
turns, and a fat budget because "it needs to fix what it finds." That is a subagent
wearing an advisor's file format. Use the Task-tool path instead.

## The file format

An advisor file is YAML frontmatter plus a body. The body is the system prompt.

```yaml
---
description: |
  One-line summary of what this advisor judges and when to consult it.
  <example>
  Context: The caller just finished a first draft of a module.
  user: "Is this readable enough to merge?"
  assistant: "I'll consult the clarity reviewer for a readability verdict."
  </example>
  <example>
  Context: A refactor touched public naming.
  user: "Sanity-check these new names."
  assistant: "Consulting the clarity reviewer on the renamed surface."
  </example>
tool_name: clarity_review
model: sonnet
allowed_tools: [Read, Grep, Glob]
max_turns: 5
max_budget_usd: 0.50
cwd: .
---

(system prompt body goes here)
```

Field reference, with exact defaults:

| Field | Required | Default | Notes |
|---|---|---|---|
| `name` | Only if it differs from the filename | filename | kebab-case or snake_case |
| `description` | Yes | — | Must be a YAML literal block scalar (`\|`) so newlines and `<example>` tags survive |
| `tool_name` | No | `<name>_consult` | The MCP-visible tool name |
| `model` | No | caller's setting | `opus` \| `sonnet` \| `haiku` (tier aliases only) |
| `allowed_tools` | No | `[Read, Grep, Glob]` | Keep it read-only |
| `disallowed_tools` | No | `[]` | Subtractive filter |
| `permission_mode` | No | `default` | `default` \| `acceptEdits` \| `plan` \| `dontAsk` \| `auto` \| `bypassPermissions` |
| `max_turns` | No | `5` | Advisors answer in few turns |
| `max_budget_usd` | No | — | Per-consultation cap, e.g. `0.50` |
| `effort` | No | — | `low` \| `medium` \| `high` \| `max` |
| `cwd` | No | `.` | Relative to project root; restricts filesystem view |
| `additional_dirs` | No | `[]` | Extra readable directories outside `cwd` |
| `prompt_mode` | No | `append` | `append` \| `replace` |

The body's delivery depends on `prompt_mode`: `append` sends it via
`CLAUDE_APPEND_PROMPT` on top of the preset system prompt; `replace` sends it as
`CLAUDE_SYSTEM_PROMPT`, discarding the preset. Almost always use `append` — the
preset is useful plumbing, and your job is to add a perspective on top of it, not to
rebuild the base behavior. The bridge carries the multi-line description verbatim into
`CLAUDE_DESCRIPTION`.

### Why the `<example>` blocks matter

The description — examples included — becomes the MCP tool description the *caller*
reads when deciding whether to invoke the advisor. The examples are not decoration;
they teach the calling model when this advisor applies. Each one carries three lines:
a `Context:` line, a `user:` line, and an `assistant:` line. The assistant line shows
the *invocation framing* ("I'll consult X about Y"), never the advisor's answer.
Write two of them. Skip them and the caller will either consult the advisor for
everything or never think of it at all.

## Writing the prompt: values, not procedures

The system prompt must express a value system, not a checklist. A checklist makes a
linter; only values make an advisor.

Anti-pattern — a procedural prompt:

> Check the following: 1) names follow convention, 2) lines under 100 chars,
> 3) every function has a docstring, 4) no TODO comments remain.

Good pattern — a held value:

> You hold readability above cleverness. For every piece of code you read, ask:
> could a tired colleague follow this at 5pm on a Friday? When the answer is no,
> name the exact construct that causes the confusion.

The difference is behavioral, not stylistic. A procedure executes identically on every
input. A value *reweights* what the advisor notices per the actual code in front of
it — different code surfaces different concerns. That adaptivity is the entire reason
to pay for a model invocation instead of running a script.

Four phrasing rules:

1. **State the principle directly, with a strong stance.** Use the "you hold X above
   Y" form. A hedged stance produces hedged advice.
2. **Rank the values explicitly** so conflicts self-resolve — for example: simple
   beats clever, clever beats short.
3. **Name what to ignore.** Scoping things *out* is liberating; it is what keeps the
   advisor from padding every answer with noise about formatting or test coverage
   that some other advisor owns.
4. **Demand output specificity.** Require `file:line` citations, require naming which
   value was violated, and require proposing the smallest change that fixes it.

## Model choice

Only tier aliases are used — never a versioned model id.

- **`opus`** — for judgement-heavy value systems that require careful code reading
  plus reasoning about consequences. Personas like `north_star_advisor`,
  `security_skeptic`, or `architecture_critic`. Worth the cost when the judgement
  genuinely is the hard part.
- **`sonnet`** — the default tier; most advisors run here (`documentation_critic`,
  `clarity_reviewer`, `simplicity_advocate`).
- **`haiku`** — narrow, mechanical-but-restricted judgement of the "look for X,
  report instances" shape: `style_checker`, `link_validator`. Rarely the right call —
  if the task is that mechanical, a skill or a plain script is usually better.

Resist the default-to-opus urge. Before picking the top tier, check whether the value
system actually needs it. A big model driven by a vague prompt returns verbose,
hedged output; a small model driven by a sharp prompt returns sharp output. Prompt
sharpness buys more than tier upgrades do.

## Tool restrictions: default to read-only

Almost every advisor should keep the `allowed_tools` default of `[Read, Grep, Glob]`.
Advisors advise; they do not act.

- **`Bash`** — grant only when the check truly cannot be captured by reading files
  (a docs advisor verifying that documented CI commands actually run, say). Even
  then, prefer having the caller run the command and feed the results into the
  consultation.
- **`WebFetch` / `WebSearch`** — rare. Advisors are meant to argue from the code
  that is actually in the repo, and web access pulls their reasoning off it.
- **`Edit` / `Write`** — almost never. The moment an agent needs write access, it has
  become a subagent; move it to the Task-tool path.

The justification test: any tool whose presence you cannot defend in a single
sentence gets removed.

## Working directory scoping

`cwd` defaults to the project root. Override it to shrink the advisor's view of the
filesystem: the advisor subprocess sees `cwd` as its root and physically cannot read
outside it unless `additional_dirs` opens specific extra paths. Examples of the
pattern:

- A docs advisor scoped to `docs/`.
- A test-coverage advisor given `tests/` plus `src/` (one as `cwd`, the other via
  `additional_dirs`).
- A frontend reviewer scoped to `web/`.

One thing scoping never moves: the timeline directory. Persistent per-agent state
lives at `.vibe-suite/agents/<name>/timeline/` regardless of `cwd`, exposed to the
advisor through the `CLAUDE_TIMELINE_DIR` environment variable. Working scope and
memory location are deliberately separate concerns.

## Budget and turn caps

`max_turns` defaults to 5, and that is not stingy — a real advisor answers in a few
turns. An agent that needs on the order of 20 turns is doing work, not advising;
redesign it as a subagent.

`max_budget_usd` is the per-call runaway stop. Sensible defaults: `0.20` for a
sonnet advisor, `0.50` for opus. Set it tighter than you think you need.

The rationale is economic, not technical: caps are a cheapness contract with the
caller. If consulting an advisor is expensive, the caller stops consulting it, and an
advisor nobody consults is worthless. Cheap consultations keep the advisor in the
loop.

## Tool naming

`tool_name` controls the MCP-visible tool. Left at the default `<name>_consult`,
the name doubles into clunky results like
`mcp__north_star_advisor__north_star_advisor_consult`.
Override it: `tool_name: north_star_consult` yields
`mcp__north_star_advisor__north_star_consult`. Pick a name so the full callable reads
as an English action. Good verbs: consult, check, review, audit.

## Common mistakes

1. **A procedure disguised as a value.** Wrapping a checklist in "you value" wording
   does not make it a value system. "You value running the linter before approving"
   is still a procedure; "you hold confidence above speed" is a value.
2. **Duplicate advisors.** When the same code would draw the same review from two
   advisors, what you actually have is one advisor plus a copy. A *different* name
   is not enough — each advisor must hold its own value system.
3. **Asking for everything.** A prompt that requests review across security and
   performance and style and architecture produces noise on every axis. One value
   system per advisor.
4. **"Follow these steps:" prompts.** Handing the model a procedure gets you a
   checklist runner. Values produce judgement; procedures produce checklists.
5. **Forgetting the timeline.** Advisors remember prior consultations, and their
   `_followup` tools continue earlier conversations. Design the persona to build on
   its own history — do not write it as if every consultation starts from zero.

## Concrete starting points

Ready-made presets ship in `templates/advisors/` — add one with
`/vibe-suite:advisor add <preset>` and edit, rather than starting
from a blank file:

- `north_star_advisor` — holds work to the project's overarching priorities
- `clarity_reviewer` — puts readability ahead of correctness
- `simplicity_advocate` — argues for the smallest solution that is still complete
- `security_skeptic` — the adversarial read
- `deletion_advocate` — hunts for code that could be removed
- `documentation_critic` — doc honesty and audience fit

Every preset is well-formed yet generic; the project-specific value lives in what
you change — the values you edit, the `cwd` you narrow, the tool list you tighten.

## After editing an advisor

Edits to an advisor file do not take effect on their own — re-register it, which
stamps the edited content in the advisor ledger and converges both stores:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/advisor_cli.py" --workspace . add <name>
```

A flag-less reconcile — what `/vibe-suite:repair` and `/vibe-suite:update` run as part
of their normal flow, and what init runs after **listing** the declared definitions —
converges only definitions the operator registered (`/vibe-suite:advisor add <name>`)
and whose content is unchanged since: an edited advisor is held at its registered
content until you re-run `advisor add <name>`; a never-registered one is listed and
left alone. `/vibe-suite:advisor add` and `/vibe-suite:advisor remove` run the same
reconcile inside them.

Propagation differs by client: Claude reads `.mcp.json` at session startup, so a new
or renamed advisor appears only after a session restart; Codex re-reads
`.codex/config.toml` on each invocation, so it picks up changes immediately.

## Scope note

This skill covers advisor agents only. It does not cover:

- **Claude Code native subagents** (`.claude/agents/`, dispatched via the Task
  tool) — a different mechanism: one-shot, isolated, no timeline. See
  [writing-agents](../writing-agents/SKILL.md) for authoring them.
- **Skill authoring** — a separate discipline with its own conventions.
- **Writing an MCP server from scratch** — the advisor backend *is* the server; this
  skill only configures it per advisor.
- **Bridge mechanics** — deferred to `scripts/advisor_cli.py` (and
  `scripts/lib/advisors.py`) and the init, repair, and update flows that invoke
  the same reconcile.
