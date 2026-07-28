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


def _secret_values(spec):
    """Every leaf under `env`, at any depth.

    Withholding `env` was not enough: the same value routinely appears in `args` too (`--key
    sk-...`), and a leak through a second field is the same leak. So the values are collected first
    and then treated as poison wherever they appear.
    """
    out = set()

    def walk(node):
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)
        elif isinstance(node, str) and node:
            out.add(node)

    walk(spec.get("env") or {})
    return out


def _toml_key(name):
    """A quoted TOML key. Bare keys are ASCII alphanumerics, `-` and `_` — anything else is quoted,
    and quoting escapes, because an unescaped quote lets a crafted name close the sentinel block and
    write outside our ownership."""
    if name and all(c.isascii() and (c.isalnum() or c in "-_") for c in name):
        return name
    escaped = name.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _toml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return json.dumps(str(value))


def mirror_mcp(ws, report):
    """`.mcp.json` → a `config.toml` sentinel block. Values from `env` never cross."""
    doc = bridge.load_json(ws / ".mcp.json")
    servers = doc.get("mcpServers") or {}
    lines, withheld = [], 0
    for name, spec in sorted(servers.items()):
        if name.startswith("cc-suite-") or not isinstance(spec, dict):
            continue
        if spec.get("command") == "vibe-suite":
            continue                      # mirroring our own registration would recurse
        secrets = _secret_values(spec)
        lines.append(f"[mcp_servers.{_toml_key(name)}]")
        command = spec.get("command")
        if isinstance(command, str) and command:
            if command in secrets:
                lines.append("# command withheld — it repeats a value from env")
                withheld += 1
            else:
                lines.append(f"command = {_toml_scalar(command)}")
        args = spec.get("args")
        if isinstance(args, list):
            rendered, dropped = [], False
            for arg in args:
                if not isinstance(arg, (str, int, float, bool)):
                    dropped = True          # a dict or list is not a TOML array member
                    continue
                if isinstance(arg, str) and arg in secrets:
                    dropped = True
                    withheld += 1
                    continue
                rendered.append(_toml_scalar(arg))
            lines.append("args = [" + ", ".join(rendered) + "]")
            if dropped:
                lines.append("# some args were withheld — they repeated an env value or were not "
                             "scalars")
        for var in sorted(k for k in (spec.get("env") or {}) if isinstance(k, str)):
            # The name crosses; no value ever does, in this field or any other.
            lines.append(f"# env: {var} (value not mirrored — set it in your own environment)")
        lines.append("")
    body = "\n".join(lines).rstrip() or "# no project MCP servers to mirror"
    dest = ws / ".codex" / "config.toml"
    existing = bridge.read_text_verbatim(dest)
    updated = bridge.text_block_upsert(existing, "mcp-mirror", body)
    if updated != existing:
        bridge.write_atomic(ws, dest, updated)
    report.append(f"mcp: mirrored {len(servers)} server(s), no env values copied"
                  + (f" ({withheld} field(s) withheld for repeating one)" if withheld else ""))


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
        bridge.write_atomic(ws, ws / SIDE_FILE,
                            json.dumps({"hooks": marked}, indent=2, sort_keys=True) + "\n")
        report.append(f"hooks: {len(shared)} event(s) mirrored to {SIDE_FILE} "
                      "(the target holds your own entries)")
    else:
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


def link_skills(ws, report, plugin_root):
    """Two links. The plugin link leaves the project by design; `.agents/skills` does not."""
    for rel, target in ((".claude/skills/vibe-suite", Path(plugin_root) / "skills"),
                        (".agents/skills", Path("../.claude/skills"))):
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            bridge.assert_inside(ws, path.parent)
        except bridge.BridgeError as exc:
            report.append(f"skills: {rel} refused — {exc}")
            continue
        if path.is_symlink():
            if os.readlink(path) == str(target):
                report.append(f"skills: {rel} already correct")
                continue
            # A link pointing somewhere else is the user's decision, not ours to overwrite.
            report.append(f"skills: {rel} points at {os.readlink(path)} — refused, not replaced")
            continue
        elif path.exists():
            report.append(f"skills: {rel} is a real path — left alone")
            continue
        try:
            path.symlink_to(target)
            report.append(f"skills: {rel} → {target}")
        except OSError as exc:
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
