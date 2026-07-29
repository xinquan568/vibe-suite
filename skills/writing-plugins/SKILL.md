---
name: writing-plugins
description: How to plan, build, and review a plugin — deciding architecture, selecting components, laying out files, configuring the plugin.json manifest, versioning, and publishing to a marketplace, for Claude Code with mappings to Codex CLI and Antigravity.
---

# Writing Plugins

> Scope: this skill covers plugin design and construction end to end. All examples
> use the Claude Code layout — a `.claude-plugin/plugin.json` manifest plus
> auto-discovered `commands/`, `agents/`, `skills/`, and `hooks/` directories.
> The same architecture carries over to Codex CLI (manifest at
> `.codex-plugin/plugin.json`, marketplace file at `.agents/plugins/marketplace.json`,
> skills under `.agents/skills/` — see [conventions-codex](../conventions-codex/SKILL.md))
> and to Antigravity extensions (`gemini-extension.json`, currently transitioning to
> the "Antigravity plugins" naming; skills under `.agent/skills/` — see
> [conventions-antigravity](../conventions-antigravity/SKILL.md)).
> A bare collection of SKILL.md files needs no plugin wrapper at all and installs
> into any tool with `npx skills add` — see [writing-skills](../writing-skills/SKILL.md).
> For authoring the individual components, see
> [writing-skills](../writing-skills/SKILL.md),
> [writing-agents](../writing-agents/SKILL.md),
> [writing-hooks](../writing-hooks/SKILL.md), and
> [writing-rules](../writing-rules/SKILL.md).

## 1. Plugin = Commands + Agents + Skills + Hooks

### Component Selection Guide

Pick the component that matches the need — not the one that feels most powerful:

| You need... | Component | Example |
|---|---|---|
| A user-invoked entry point | Command (slash command) | A scoring command invoked as `/vibe-suite:score` |
| An autonomous AI task | Agent | A security scanner dispatched to sweep the repo |
| Domain knowledge the AI should load | Skill | A SKILL.md carrying pattern tables |
| Automatic behavior on tool events | Hook | Lint on save, block a force-push |
| Integration with an external service | MCP server via `.mcp.json` | GitHub API, Slack |

### Minimum Viable Plugin

A minimum viable plugin has exactly **one** component. The smallest working layout
is a `.claude-plugin/plugin.json` manifest plus a single `commands/*.md` file.
Hold back agents, skills, and hooks until you actually need them — every extra
component is another artifact you have to keep correct and in sync.

## 2. Architecture Patterns

Five patterns cover nearly every plugin:

### Pattern 1: Single Command

The command does everything itself. Use when the work is simple, deterministic,
and single-step — for example, a scan that flags files breaching a line-count
guard.

### Pattern 2: Command + Agent

The command parses arguments, dispatches one agent, and formats its output. Use
when the work needs AI judgment but has a clear user-facing entry point — for
example, a score command that hands analysis to a dedicated scorer agent.

### Pattern 3: Command + Multiple Agents (Parallel)

The command dispatches **2–6** agents in parallel, then synthesizes their
results. Use when several independent analyses run over the same input — for
example, six review agents each inspecting a different dimension.

### Pattern 4: Command + Agent Pipeline (Sequential)

Each stage feeds the next, and stages may warrant different model tiers — for
illustration, a haiku stage that parses, a sonnet stage that analyzes, then a
sonnet stage that quality-checks. Use when each phase depends on the previous
phase's output — for example, a four-phase reading pipeline.

### Pattern 5: Hooks Only

No commands at all: an event fires, a hook script runs, and the action is
allowed, denied, or annotated with advice. Use for enforcement that must happen
automatically rather than when a user asks — for example, a pre-commit quality
gate.

### Pattern Selection Matrix

Answer six yes/no questions:

| Question | Yes means... |
|---|---|
| Does the user explicitly trigger it? | Command (no → hooks-only) |
| Does it need AI judgment? | Agents (no → command-only or hooks) |
| Are there independent sub-analyses? | Parallel agents (Pattern 3) |
| Does each step depend on the previous one? | Sequential pipeline (Pattern 4) |
| Should it run automatically on events? | Add hooks |
| Does it need domain knowledge? | Add skills |

## 3. The plugin.json Manifest

### Required

Only one field is strictly required: `name`.

### Recommended

Ship `name`, `version`, `description`, `author` (an object with a `name` key),
`license`, `keywords` (an array), and `category`.

### Field Reference

| Field | Meaning |
|---|---|
| `name` | Unique identifier; appears in slash commands |
| `version` | Semver; drives marketplace listings and update checks |
| `description` | One-line text shown in the marketplace listing |
| `author.name` | Attribution |
| `license` | License identifier, e.g. `MIT` |
| `keywords` | Marketplace search terms |
| `category` | Marketplace category, e.g. `"developer-tools"` |

## 4. File Structure

### Full Layout

```
my-plugin/
├── .claude-plugin/
│   ├── plugin.json          # required manifest
│   └── marketplace.json     # publishing metadata
├── commands/
│   ├── do-thing.md          # invocable as /my-plugin:do-thing
│   └── shared/              # partials, user-invocable: false
├── agents/
├── skills/
│   └── my-plugin/
│       └── some-skill/
│           ├── SKILL.md
│           └── references/
├── hooks/
│   └── hooks.json
├── scripts/
├── CLAUDE.md                # for the AI
├── README.md                # for humans
└── LICENSE
```

### Directory Conventions

Auto-discovered: `.claude-plugin/` (manifest), `commands/`, `commands/shared/`
(discovered but NOT invocable), `agents/`, `skills/`, and `hooks/` via
`hooks.json`. NOT auto-discovered: `scripts/` — reference scripts explicitly,
and always through `${CLAUDE_PLUGIN_ROOT}` (for example
`${CLAUDE_PLUGIN_ROOT}/scripts/check.sh`) so the plugin works from wherever it
is installed. A command file named `commands/scan.md` in a plugin named
`vibe-suite` is invoked as `/vibe-suite:scan` — the general form is
`/plugin-name:command-name`.

### Naming Conventions

| Artifact | Convention |
|---|---|
| Commands | kebab-case descriptive verb |
| Agents | kebab-case role-noun |
| Skills | kebab-case directory; the file itself is always `SKILL.md` |
| Hook scripts | kebab-case descriptive name ending `.sh` |

## 5. Versioning

### Semver Rules

| Bump | Example | When |
|---|---|---|
| Patch | `0.1.0 -> 0.1.1` | Bug fixes, typos, penalty adjustments |
| Minor | `0.1.0 -> 0.2.0` | New commands, agents, or features |
| Major | `0.1.0 -> 1.0.0` | Breaking changes: renamed commands, removed features |

### Four-Place Update

A version bump touches four places — miss one and you have version drift:

1. `version` in `.claude-plugin/plugin.json`
2. The plugin's entry `version` in `.claude-plugin/marketplace.json`
3. The `marketplace.json` of the central marketplace clone, at
   `~/.claude/plugins/marketplaces/xiaolai/.claude-plugin/marketplace.json`
4. The central marketplace `README.md`, in its version table

Push the plugin repository BEFORE updating the central marketplace. The
marketplace points at the repo — if the repo is stale when the marketplace
updates, users pull old code.

## 6. CLAUDE.md for Plugins

The audience for CLAUDE.md is Claude itself, not the end user. Its job is to
explain how the components relate to each other.

**Include:** a short architecture blurb; a commands table (command → purpose);
an agents table (agent → model → role); a conventions list (for example a
shared output format, ordering dependencies, or a fail-open hooks policy).

**Exclude:** everything aimed at humans instead — installation steps and user
documentation belong in README.md, release history in CHANGELOG.md or the git
log, and contribution guidance in CONTRIBUTING.md.

## 7. Shared Partials

When several commands repeat the same logic, move it into
`commands/shared/*.md` with frontmatter setting `user-invocable: false` plus a
`description`.

### Extraction Candidates

| Logic | Extract when |
|---|---|
| Config loading | 3+ commands need it |
| File discovery | 3+ commands scan files |
| Prerequisite validation | 2+ commands share the same tools |
| Report formatting | 3+ commands emit reports |

### When NOT to Extract

- A single consumer — extraction is premature.
- Logic under **10 lines** — duplication is acceptable at that size.
- Slightly-divergent logic — forcing a generalization adds more complexity than
  the duplication cost.

## 8. Testing Your Plugin

### Pre-Publish Checklist

- `claude plugin validate /path/to/plugin` reports no errors.
- Each command run with no arguments prints helpful usage or a clear error.
- Each command with typical arguments produces correct output.
- Edge inputs degrade gracefully: an empty file, a huge file, a file that is
  missing.
- Agent trigger probes dispatch the correct agent.
- Hook scripts are executable (`chmod +x`) and emit valid JSON when fed test
  JSON input.
- Fail-open behavior holds: killing a hook script mid-run still allows the
  action.

### Testing Agent Triggers

Probe every agent with three query types:

1. A direct-match query — MUST trigger the agent.
2. An adjacent-topic query — either outcome is acceptable.
3. An unrelated query — must NOT trigger.

## 9. Marketplace Publishing

Five steps:

1. Push the plugin repository to GitHub.
2. In the central `marketplace.json`, add an entry with the same field set —
   name, description, source, version, license, author, category, keywords.
3. Append a row to the central README's version table.
4. Commit the central repository and push it.
5. Verify the install: `claude plugin install <name>@xiaolai --scope project`.

Before publishing, confirm: `claude plugin validate .` passes; no hardcoded
paths remain (check with `grep -r '/Users/' commands/ agents/ hooks/`); all
scripts are executable; the version string is identical in all 4 locations.

## 10. Common Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| Over-broad commands | One command tries to do everything | Split into focused commands |
| Agents without examples | Trigger accuracy drops to **40%** | Add 2-3 specific scenario examples |
| Skills over **500 lines** | Context bloat | Extract depth to `references/` |
| Hooks that block silently | User sees a denial with no reason | Always include `permissionDecisionReason` |
| Missing CLAUDE.md | The AI cannot grasp the architecture | Write one covering component relations |
| README exposing internals | Wrong audience | README = user guide; CLAUDE.md = internals |
| Hardcoded paths | Breaks on other machines | Use `${CLAUDE_PLUGIN_ROOT}` everywhere |
| No command error handling | Silent failures | Add explicit error cases to each command |
| Version drift | Marketplace serves stale metadata | Run the four-place checklist every bump |
| Premature `shared/` extraction | Needless indirection | Require 3+ consumers first |
