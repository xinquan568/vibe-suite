---
description: "Manage consultative advisor personas: add [preset|--custom] | list | remove <name>. Advisors register as MCP servers in both .mcp.json and .codex/config.toml (bare-name key, structurally owned), each with its own system prompt, tier alias, tool scope, turn cap, budget, and timeline directory. add resolves the claude-octopus backend from the shipped pin, or an explicit exact --pin before E7.1 ships one."
argument-hint: "[add <preset>|add --custom | list | remove <name>] [--pin <exact-version>]"
---

# /vibe-suite:advisor — consultative advisor personas

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/advisor_cli.py" --workspace . ${ARGUMENTS}
```

An advisor is an on-demand, value-over-rules persona — one stable point of view you *return* to,
reachable from Claude and Codex as `mcp__<name>__<tool_name>`. Definitions live at
`.vibe-suite/agents/<name>.md`; persistent memory at `.vibe-suite/agents/<name>/timeline/`
(gitignored). The [agent-design skill](../skills/agent-design/SKILL.md) is the authoritative file
format and design guide.

## `add <preset>` — six shipped personas

`north_star_advisor` · `security_skeptic` (opus) · `clarity_reviewer` · `simplicity_advocate` ·
`deletion_advocate` · `documentation_critic` (sonnet). The preset is copied to
`.vibe-suite/agents/<name>.md`; tell the user to tailor the system prompt to *this project's*
values — the preset is a starting point, not the product.

## `add --custom` — collect, then dispatch

Interview the user for the fields (name, one-line description, tier alias `opus|sonnet|haiku`,
turn cap, budget), write the system prompt to a temp file, then dispatch with explicit flags:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/advisor_cli.py" add <name> --custom \
  --description "<one line>" --model sonnet --max-turns 5 --max-budget-usd 0.50 \
  --body-file <path-to-system-prompt>
```

The CLI itself never prompts — every behavior is flag-driven and testable.

## Dangerous definitions need `--confirm-danger`

A definition is repository content. One that declares `permission_mode: dontAsk | auto |
bypassPermissions`, or a `cwd` / `additional_dirs` entry that resolves outside the workspace
(`~`, an absolute path outside it, `..` that escapes), is **refused** by `add` and by `reconcile` —
the refusal names the field and the flag, and nothing is written. Ask the user, and only after an
explicit yes re-run with `--confirm-danger`; the acceptance is recorded (journaled with the
transaction and kept in the advisor ledger, bound to that exact definition) so a later `init` /
`repair` / `update` converges the same definition without the flag, and a changed definition asks
again. `default` / `acceptEdits` / `plan` and in-workspace directories are unaffected; passing the
flag when nothing is dangerous is refused. `remove` never registers a dangerous definition on the
way out and never blocks on one.

## The backend pin

A registration executes the pinned `claude-octopus` package. Until **E7.1** ships the default pin,
a plain `add` refuses with the remedy text; pass `--pin <exact-version>` (e.g. `--pin 1.2.3`) to
register now — exact versions only, the same grammar the suite's pin machinery enforces. Never
suggest `latest` or a range.

## `remove <name>`

Ask the user about the timeline before dispatching (it holds prior consultation history):
keep (default; `--keep-timeline`) or delete (`--delete-timeline`). Removal cleans the definition
and **both** store registrations; the round trip leaves both config files sentinel-clean.

## Propagation

Claude reads `.mcp.json` at session startup — a new or removed advisor takes effect after a
restart. Codex re-reads `.codex/config.toml` per invocation — immediately.

Report the CLI's output lines as returned; on exit 2 relay the refusal verbatim (it names the
remedy: a collision to rename, or the pin to supply).
