---
description: "Post-plugin-update refresh: re-render bridges and mirrors, install the pinned reverse-MCP server from the shipped lockfile, boot-verify that install with a real MCP initialize handshake, and only then refresh the registrations that launch it. Run it after upgrading the plugin."
argument-hint: ""
---

# /vibe-suite:update — post-plugin-update refresh

Upgrading the plugin moves files the workspace points at. This re-points them, installs the pinned
reverse-MCP server from the plugin's shipped lockfile, proves that install boots, and only then
rewrites the registrations that launch it.

## What to do

No arguments. Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/update.py" --workspace . --plugin-root "${CLAUDE_PLUGIN_ROOT}"
```

Report the table it prints. A `[HIGH]` row means the refresh did not complete; `[LOW]` is advisory.

## Order, and why it is fixed

    resolve pin → bridges + mirrors → install → boot-verify → advisors → registration

The pin resolves **first**. Bridges and mirrors run **even when the pin is not shipped yet** —
otherwise this command would do nothing in exactly the release where a stale bridge is most likely —
and so do the advisors (removals and consistency need no backend).

**Nothing that depends on the pin is written before the install is boot-verified.** `install` runs
`npm ci --ignore-scripts` from the shipped `scripts/lib/claude-octopus/package-lock.json` into a fresh,
immutable *generation* directory (`scripts/lib/claude-octopus/versions/<version>/<generation>/`), or
reuses a valid one; `boot-verify` launches exactly that generation by `node <installed bin>` and, on a
clean handshake, records its `.verified` mark. Only then do `advisors` (before `registration`, because
reconciliation first replays its journal, which restores whole store images) and `registration`
rewrite `.mcp.json` and `.codex/config.toml` to launch that generation.

Consequences worth knowing:

- A tampered package (`npm` reports `EINTEGRITY`), a missing `npm`, or a failed or timed-out handshake
  ends the run with both stores **byte-identical** and an advisory `advisors` row reading
  *skipped — … not boot-verified this run*; advisor removals and convergence run on the next successful
  update. Nothing is rolled back because nothing was written.
- Every registration executes the verified install (`command = "node"`, `args = ["…/dist/index.js"]`),
  so the path is specific to this machine's plugin directory; run this command after moving the plugin.
- Older generations are never deleted automatically: a held advisor, a workspace that has not run
  `update`, or a concurrent install may still launch one. The `install` row lists them; remove one by
  hand (`rm -rf scripts/lib/claude-octopus/versions/<version>/<generation>`) once no workspace's stores
  reference it. Each generation is roughly 250 MB.
- The local install is trusted after `npm ci` verified it, the same way the plugin's own files are
  trusted; nothing re-hashes installed files at launch.

Validation happens before any write, so a refusal leaves the workspace untouched. After that, stages
are independent: a failed probe does not undo a completed bridge refresh.

## Bumping the pin

Edit `scripts/lib/claude-octopus-pin.txt` **and** the `dependencies.claude-octopus` value in
`scripts/lib/claude-octopus/package.json` to the same exact version, then regenerate the lockfile in
that directory:

```bash
cd scripts/lib/claude-octopus && npm install --package-lock-only --ignore-scripts --no-audit --no-fund --save-exact
```

`tests/test_pin_shipped.py` and `tests/test_update.py::Lockfile` refuse a pin file, manifest and
lockfile that disagree. Then run `/vibe-suite:update` in each workspace.

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
