#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Pinned reverse-MCP registration for `/vibe-suite:update` (E2.6 / vibe-23, F1.7).

**The reverse direction.** `bridge_cli.py mirrors` copies `.mcp.json` *into* `.codex/config.toml` so
Codex can reach the project's servers. This module writes the other way: the pinned `claude-octopus`
package through which Codex delegates *back* to Claude. Nothing else in the suite writes it.

**Ownership is the name.** The table is `[mcp_servers.vibe-claude-mcp]` — already in
`bridge.SENTINEL_LITERALS` — so `inventory_enumerate` and #21's teardown find it with no new codec.
The body goes through `bridge.toml_server_upsert`, whose `vibe-suite:server:… v1` fence is what
`toml_server_remove` matches; a hand-rolled fence would be discoverable but **not removable**.
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN_FILE = HERE / "claude-octopus-pin.txt"
PENDING_FILE = HERE / "claude-octopus-pin.pending"
SERVER_NAME = "vibe-claude-mcp"
PACKAGE = "claude-octopus"

#: Exact versions only. A pin that floats is not a pin, and boot-verifying `latest` proves nothing
#: about what installs tomorrow.
_EXACT = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")


class PinError(Exception):
    """The pin is unusable. Nothing is written."""


def resolve_pin(pin_file=None, pending_file=None):
    """Five states. Returns ``(status, value)`` where status is ``pending`` or ``shipped``.

    File absence alone cannot tell "E7.1 has not landed" from "E7.1 landed and the pin is missing",
    so the pending state is declared by an explicit marker rather than inferred.
    """
    pin_file = Path(pin_file) if pin_file else PIN_FILE
    pending_file = Path(pending_file) if pending_file else PENDING_FILE
    has_pin, has_marker = pin_file.is_file(), pending_file.is_file()

    if has_pin and has_marker:
        raise PinError(
            "both claude-octopus-pin.txt and claude-octopus-pin.pending are present; "
            "the shipped state is ambiguous — E7.1 must delete the marker when it adds the pin")
    if has_marker:
        return "pending", None
    if not has_pin:
        raise PinError(
            "no claude-octopus pin and no pending marker; this plugin installation is incomplete")
    raw = pin_file.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        raise PinError("claude-octopus-pin.txt is empty")
    if not _EXACT.match(raw):
        raise PinError(
            f"claude-octopus pin {raw!r} is not an exact version; ranges and tags "
            f"(latest, ^1.2.0, ~1.2, 1.x) cannot be boot-verified")
    return "shipped", raw


def target(pin):
    return f"{PACKAGE}@{pin}"


def render_body(pin):
    """The registration contract. Codex's default `tool_timeout_sec` would cut a multi-turn
    delegation off mid-run, and a cold `npx -y` download needs the startup allowance."""
    return "\n".join((
        f"[mcp_servers.{SERVER_NAME}]",
        'command = "npx"',
        f'args = ["-y", "{target(pin)}"]',
        "startup_timeout_sec = 60",
        "tool_timeout_sec = 900",
    ))


def collision(existing):
    """A reserved name that is not ours. Structural ownership means the name *is* the claim, so an
    unsentinelled `vibe-claude-mcp` is a collision to refuse — not a user preference to respect.

    cc-suite's `[mcp_servers.claude-code]` is a different name and is ignored entirely.
    """
    import bridge
    if bridge.toml_server_has(existing, SERVER_NAME):
        return None
    if re.search(r'^\s*\[mcp_servers\.(?:%s|"%s")\]\s*$' % (SERVER_NAME, SERVER_NAME),
                 existing, re.M):
        return (f"[mcp_servers.{SERVER_NAME}] exists without a vibe-suite fence — refusing to "
                f"adopt a reserved name this workspace did not get from us")
    return None


def plan(existing, pin):
    """`(action, new_text)` without writing. Validation is separable from application so a collision
    can be caught before anything else in the run has mutated the workspace."""
    import bridge
    conflict = collision(existing)
    if conflict:
        raise PinError(conflict)
    body = render_body(pin)
    updated = bridge.toml_server_upsert(existing, SERVER_NAME, body)
    if updated == existing:
        return "current", existing
    return ("refreshed" if bridge.toml_server_has(existing, SERVER_NAME) else "added"), updated
