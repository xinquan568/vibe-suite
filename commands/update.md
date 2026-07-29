---
description: "Post-plugin-update refresh: re-render bridges and mirrors, warm the npx cache, refresh the pinned reverse-MCP registration, and boot-verify that pin with a real MCP initialize handshake. Run it after upgrading the plugin."
argument-hint: ""
---

# /vibe-suite:update — post-plugin-update refresh

Upgrading the plugin moves files the workspace points at. This re-points them, then proves the
pinned reverse-MCP server still boots.

## What to do

No arguments. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update.py" --workspace . --plugin-root "${CLAUDE_PLUGIN_ROOT}"
```

Report the table it prints. A `[HIGH]` row means the refresh did not complete; `[LOW]` is advisory.

## Order, and why it is fixed

    resolve pin → bridges + mirrors → npx pre-warm → registration → boot-verify

The pin resolves **first** because the pre-warm has no target without it. Bridges and mirrors run
**even when the pin is not shipped yet** — otherwise this command would do nothing in exactly the
release where a stale bridge is most likely.

Validation happens before any write, so a refusal leaves the workspace untouched. After that, stages
are independent: a failed probe does not undo a completed bridge refresh.

## The pinned reverse server

`[mcp_servers.vibe-claude-mcp]` in `.codex/config.toml` is the direction Codex uses to delegate back
to Claude. Its name is also its ownership marker, so teardown finds it without a second list.

Five pin states, and only one of them is silence:

| Pin file | Marker | Meaning |
| --- | --- | --- |
| absent | present | not shipped yet — bridges refresh, the rest is skipped |
| exact version | absent | verified and registered |
| range or tag | absent | refused — a floating pin cannot be boot-verified |
| absent | absent | refused — the plugin installation is incomplete |
| present | present | refused — the shipped state is ambiguous |

A `[mcp_servers.vibe-claude-mcp]` table without a vibe-suite fence is a **collision**: the command
refuses rather than adopting a reserved name it did not write.

## Namespaces

Every string this command prints uses `/vibe-suite:` only. The check is enforced, not merely
intended — `/vibe-suite:doctor` scans this command's own surface, and the command checks its output
before printing it.
