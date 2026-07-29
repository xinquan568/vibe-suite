#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Bridge sub-operations for `/vibe-suite:bridge` (E2.5 / vibe-22, F1.6).

**Secrets cross by allowlist, not by redaction.** Every `.mcp.json` server `env` *value* is withheld;
variable *names* cross as commented placeholders, which is why `bearer_token_env_var` appears — it
names a variable rather than holding one. A redacted value would still put the secret's shape in a
second file the user did not choose.

**Three hook namespaces, and this mirrors the third**: not the plugin's own `hooks/hooks.json`, not
the owned `Stop` entry `init` writes, but the *project's* hooks in `.claude/settings.json`.
"""

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402

#: The events both tools have. Claude-only events are skipped rather than mirrored into a runtime
#: that would never fire them.
SHARED_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop")

SIDE_FILE = ".codex/hooks.vibe-suite.json"


def _toml_key(name):
    """A TOML key. Bare only for ASCII alphanumerics, `-` and `_`; anything else is a quoted basic
    string escaped by `json.dumps`, whose escaping is a superset of TOML's — so a quote, backslash,
    newline or control character cannot close the key and inject content outside our block."""
    if name and all(c.isascii() and (c.isalnum() or c in "-_") for c in name):
        return name
    return json.dumps(name)


def _toml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        # TOML has no nan/inf literal; such a value is not mirrored as a number.
        return json.dumps(str(value))
    return json.dumps(str(value))


def _name_repeats_a_value(name, env):
    """Whether a server's name carries one of its own env values.

    The name is the one field that must cross for the mirror to mean anything, so it is the one place
    a value comparison is still needed. It is bounded to that server's own env — a small closed set —
    rather than poisoning the whole document, which is what made the general rule unworkable.
    """
    def leaves(node):
        if isinstance(node, dict):
            for v in node.values():
                yield from leaves(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                yield from leaves(v)
        elif node is not None and not isinstance(node, bool):
            yield str(node)

    return any(v and v in name for v in leaves(env))


def mirror_mcp(ws, report):
    """`.mcp.json` → a `config.toml` sentinel block.

    **A server that declares `env` contributes only names.** Its own name and its variable names
    cross; `command` and `args` do not.

    That rule is structural, and it replaces three iterations of trying to *recognise* a secret.
    Recognition cannot work: poisoning every value means a two-character `env` entry like `on`
    withholds every occurrence of those characters and the mirror renders nothing, while any length
    floor lets a genuinely short credential through. Nothing in the input distinguishes a short
    credential from a short flag, so no threshold satisfies both — and case folding, Unicode
    normalisation and encoding variants each add an unbounded space to compare against.

    Declaring `env` is the one signal the file actually gives about which servers handle secrets. A
    server without it is mirrored in full; a server with it is named, and the user is told where the
    rest lives. The guarantee then holds without anyone having to identify a credential.
    """
    doc = bridge.load_json(ws / ".mcp.json")
    servers = doc.get("mcpServers") or {}
    lines, reduced = [], 0
    for name, spec in sorted(servers.items()):
        if name.startswith("cc-suite-") or not isinstance(spec, dict):
            continue
        if spec.get("command") == "vibe-suite":
            continue                      # mirroring our own registration would recurse
        env = spec.get("env")
        declares_env = bool(env)
        if declares_env and _name_repeats_a_value(name, env):
            lines.append("# a server was not mirrored: its name repeats one of its own env values")
            lines.append("")
            reduced += 1
            continue
        lines.append(f"[mcp_servers.{_toml_key(name)}]")
        if declares_env:
            reduced += 1
            lines.append("# this server declares env, so only names are mirrored — see .mcp.json")
        else:
            command = spec.get("command")
            if isinstance(command, str) and command:
                lines.append(f"command = {_toml_scalar(command)}")
            args = spec.get("args")
            if isinstance(args, list):
                scalars = [a for a in args if isinstance(a, (str, int, float, bool))]
                lines.append("args = [" + ", ".join(_toml_scalar(a) for a in scalars) + "]")
                if len(scalars) != len(args):
                    lines.append("# some args were not scalars and were not mirrored")
        names = sorted(k for k in env if isinstance(k, str)) if isinstance(env, dict) else []
        for var in names:
            # The variable's name crosses so the user knows what to set. Its value never does.
            lines.append(f"# env: {var} (value not mirrored — set it in your own environment)")
        lines.append("")
    body = "\n".join(lines).rstrip() or "# no project MCP servers to mirror"
    dest = ws / ".codex" / "config.toml"
    existing = bridge.read_text_verbatim(dest)
    updated = bridge.text_block_upsert(existing, "mcp-mirror", body)
    if updated != existing:
        bridge.write_atomic(ws, dest, updated)
    report.append(f"mcp: mirrored {len(servers)} server(s)"
                  + (f"; {reduced} declare env, so only names crossed" if reduced else ""))


def _side_file_is_ours(side):
    """Whether the hook side file is one we wrote.

    It was treated as owned on its *name*: a pre-existing file there was overwritten, and — worse —
    unlinked outright when the mirror was no longer needed. A symlink is never ours, and neither is
    a document without our stamp.
    """
    if side.is_symlink():
        return False
    if not side.exists():
        return True   # nothing there; we may create it
    doc = bridge.load_json(side)
    return isinstance(doc, dict) and doc.get("vibe_suite_owned") is True


def mirror_hooks(ws, report):
    """The *project's* Claude hooks → `.codex/hooks.json`, preserving the owned entry."""
    settings = bridge.load_json(ws / ".claude" / "settings.json")
    project = settings.get("hooks") or {}
    shared = {e: project[e] for e in SHARED_EVENTS if e in project}
    skipped = sorted(set(project) - set(SHARED_EVENTS))

    dest = ws / ".codex" / "hooks.json"
    doc = bridge.load_json(dest)
    hooks = doc.get("hooks") or {}
    owned = [e for e in hooks.values() for e in (e or [])
             if isinstance(e, dict) and e.get(f"_{bridge.MARKER}_owned") is not None]
    def ours(entry):
        return isinstance(entry, dict) and (
            entry.get(f"_{bridge.MARKER}_owned") is not None
            or entry.get(f"_{bridge.MARKER}_mirrored") is not None)

    # Mirrored entries are marked, so a second run recognises its own work instead of mistaking it
    # for the user's and falling back to a side file it does not need.
    user_content = any(not ours(entry)
                       for entries in hooks.values() for entry in (entries or []))

    marked = {e: [dict(x, **{f"_{bridge.MARKER}_mirrored": 1}) for x in v if isinstance(x, dict)]
              for e, v in shared.items()}
    if user_content:
        # The target is the user's. A side file mirrors without touching what they wrote.
        payload = json.dumps({"hooks": marked, "vibe_suite_owned": True},
                             indent=2, sort_keys=True) + "\n"
        side = ws / SIDE_FILE
        if not _side_file_is_ours(side):
            report.append(f"hooks: {SIDE_FILE} exists and is not ours — left alone, not mirrored")
            return
        if not side.is_file() or side.read_text(encoding="utf-8") != payload:
            bridge.write_atomic(ws, side, payload)
        report.append(f"hooks: {len(shared)} event(s) mirrored to {SIDE_FILE} "
                      "(the target holds your own entries)")
    else:
        side = ws / SIDE_FILE
        if side.is_file() and _side_file_is_ours(side):
            # The fallback existed because the target was the user's; it no longer is. Leaving it
            # behind would let two mirrors drift apart with nothing saying which one is live.
            bridge.unlink_at(ws, SIDE_FILE)
            report.append(f"hooks: removed {SIDE_FILE} — the target is no longer user-owned")
        merged = dict(marked)
        for entries in hooks.values():
            for entry in entries or []:
                if isinstance(entry, dict) and entry.get(f"_{bridge.MARKER}_owned") is not None:
                    merged.setdefault("Stop", []).append(entry)
        # Preserve any top-level key that is not `hooks` — the file is not ours alone.
        out = {k: v for k, v in doc.items() if k != "hooks"}
        out["hooks"] = merged
        updated = json.dumps(out, indent=2, sort_keys=True) + "\n"
        if updated != (dest.read_text(encoding="utf-8") if dest.is_file() else ""):
            bridge.write_atomic(ws, dest, updated)
        report.append(f"hooks: {len(shared)} event(s) mirrored, "
                      f"{len(owned)} owned entr(y/ies) preserved")
    if skipped:
        report.append(f"hooks: skipped Claude-only event(s): {', '.join(skipped)}")


def _open_parent(ws, rel):
    """The audited descent, from the module that owns it.

    This was a second copy of `bridge._open_dir_chain` — and a copy of a safety rule drifts from the
    original, which is how this codebase kept guarding one writer while another went unguarded.
    """
    return bridge.open_dir_chain(ws, Path(rel).parent.parts)


def link_skills(ws, report, plugin_root):
    """Two links. The plugin link leaves the project by design; `.agents/skills` does not."""
    for rel, target in ((".claude/skills/vibe-suite", Path(plugin_root) / "skills"),
                        (".agents/skills", Path("../.claude/skills"))):
        path = ws / rel
        try:
            # Opened, not merely checked: a path validated and then used is validated at a different
            # moment than it is used. The descriptor is what the symlink is created against.
            parent_fd = _open_parent(ws, rel)
        except bridge.BridgeError as exc:
            report.append(f"skills: {rel} refused — {exc}")
            continue
        if path.is_symlink():
            if os.readlink(path) == str(target):
                report.append(f"skills: {rel} already correct")
                os.close(parent_fd)
                continue
            # A link pointing somewhere else is the user's decision, not ours to overwrite.
            report.append(f"skills: {rel} points at {os.readlink(path)} — refused, not replaced")
            os.close(parent_fd)
            continue
        elif path.exists():
            report.append(f"skills: {rel} is a real path — left alone")
            os.close(parent_fd)
            continue
        os.close(parent_fd)
        try:
            if bridge.symlink_at(ws, rel, target):
                report.append(f"skills: {rel} → {target}")
            else:
                report.append(f"skills: {rel} appeared concurrently — left as it is")
        except (OSError, bridge.BridgeError) as exc:
            report.append(f"skills: {rel} could not be linked ({exc})")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="/vibe-suite:bridge")
    parser.add_argument("subcommand", nargs="?", default="all",
                        choices=["skills", "hooks", "mcp", "mirrors", "all"])
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--plugin-root", default=os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ws = Path(args.workspace).resolve()

    report, wanted = [], args.subcommand
    try:
        if wanted in ("skills", "all"):
            link_skills(ws, report, args.plugin_root or HERE.parent)
        if wanted in ("hooks", "all"):
            mirror_hooks(ws, report)
        if wanted in ("mcp", "all"):
            mirror_mcp(ws, report)
        if wanted in ("mirrors", "all"):
            # Specified as a stub by E2.5. A silent no-op would read as success.
            report.append("mirrors: not yet available — the codex/ mirror generator lands in S7 "
                          "(E7.2). Nothing was regenerated.")
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"steps": report}, indent=2) if args.json else "\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
