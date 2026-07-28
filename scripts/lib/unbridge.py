#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Teardown for `/vibe-suite:unbridge` (E2.4 / vibe-21, F1.4).

**Strip, then compare.** Provenance's `sha256` is the *pre-image* hash, and init changed the target —
so comparing it against the current file detects "init ran", not "the user edited". Removing the
owned region first and comparing the remainder is the test that distinguishes them, and it is what
lets both halves of the acceptance criterion hold at once: byte-identical to pre-init where the user
changed nothing, and untouched user content where they did.

**The record is data, not authority.** `targets` and `parents_created` hold absolute paths and are
only shape-validated by the writer. Every one is re-contained, `lstat`-classified and refused if it
is not what the record claims, before anything is deleted.
"""

import base64
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bridge  # noqa: E402
import init_bridge  # noqa: E402

#: name -> (relative path, codec). The inventory drives which regions come out of which file.
BLOCKS = (("AGENTS.md", "memory", "md"), ("CLAUDE.md", "import", "md"),
          ("GEMINI.md", "import", "md"), (".gitignore", "ignore", "text"),
          (".codex/config.toml", "server:vibe-mcp", "text"))


def recorded_path(ws, raw):
    """A path from the record, re-anchored to the resolved workspace, or None if it escapes.

    Provenance stores the path `init` was given; this command resolves its workspace. On macOS
    `/var` and `/private/var` name one directory, so a literal comparison rejects legitimate entries
    and — worse — the re-anchoring is also what proves an entry is genuinely inside.
    """
    path = Path(raw)
    try:
        return ws / path.resolve().relative_to(ws)
    except (ValueError, OSError):
        return None


def strip_owned(ws, rel, name, codec):
    path = ws / rel
    if not path.is_file():
        return None
    text = bridge.read_text_verbatim(path)
    stripped = (bridge.md_block_remove(text, name) if codec == "md"
                else bridge.text_block_remove(text, name))
    return text, stripped


def restore(ws, entry, report):
    """One target, from its recorded pre-image. Refuses anything the record misdescribes."""
    path = recorded_path(ws, entry["path"])
    if path is None:
        raise bridge.BridgeError(
            f"provenance names a path outside the workspace: {entry['path']}")

    kind, actual = entry["kind"], bridge.classify(path)
    if actual == "absent":
        report.append(f"{path.name}: already gone")
        return

    rel = str(path.relative_to(ws))
    owned = next(((r, n, c) for r, n, c in BLOCKS if r == rel), None)
    stripped = None
    if owned:
        pair = strip_owned(ws, rel, owned[1], owned[2])
        if pair:
            _, stripped = pair

    if kind == "absent":
        # init created it. Deleting is correct only when nothing but ours was ever in it — and for
        # a JSON target that question is about its *contents*, not about a text block, so an
        # unrelated server or hook left behind keeps the file alive.
        if rel in (".mcp.json", ".codex/hooks.json"):
            doc = bridge.load_json(path)
            leftover = (doc.get("mcpServers") if rel == ".mcp.json"
                        else {k: v for k, v in (doc.get("hooks") or {}).items() if v})
            if leftover:
                report.append(f"{rel}: kept — it still holds entries that are not ours")
                return
            path.unlink()
            report.append(f"{rel}: removed")
            return
        if stripped is not None and stripped.strip():
            bridge.write_atomic(ws, path, stripped)
            report.append(f"{rel}: kept — it holds content beyond the owned block")
        else:
            path.unlink()
            report.append(f"{rel}: removed")
        return

    if kind == "file":
        pre = base64.b64decode(entry["content_b64"], validate=True)
        if stripped is not None:
            if stripped.encode("utf-8", "surrogateescape") == pre:
                bridge.write_atomic(ws, path, pre, mode=int(entry["mode"], 8))
                report.append(f"{rel}: restored")
            else:
                # The user edited outside our region. Their version, minus our block, is what
                # honours "nothing user-owned touched" — the pre-image would overwrite their work.
                bridge.write_atomic(ws, path, stripped)
                report.append(f"{rel}: owned block removed; your later edits kept")
        else:
            bridge.write_atomic(ws, path, pre, mode=int(entry["mode"], 8))
            report.append(f"{rel}: restored")
        return

    report.append(f"{rel}: left as it is ({kind})")


def json_targets(ws, report, dry):
    """`.mcp.json` and `.codex/hooks.json`: structural ownership, so user entries survive."""
    for name in sorted(bridge.inventory_enumerate(ws)) + ["cc-suite-mcp", "cc-suite-claude-mcp"]:
        doc = bridge.load_json(ws / ".mcp.json")
        if bridge.json_server_has(doc, name):
            report.append(f".mcp.json: {name}")
            if not dry:
                bridge.write_atomic(ws, ws / ".mcp.json",
                                    json.dumps(bridge.json_server_remove(doc, name),
                                               indent=2, sort_keys=True) + "\n")
    hooks = bridge.load_json(ws / ".codex" / "hooks.json")
    if bridge.json_hook_entry_has(hooks, "Stop"):
        report.append(".codex/hooks.json: owned Stop entry")
        if not dry:
            bridge.write_atomic(ws, ws / ".codex" / "hooks.json",
                                json.dumps(bridge.json_hook_entry_remove(hooks, "Stop"),
                                           indent=2, sort_keys=True) + "\n")


def prune(ws, record, report):
    """Directories init created — removed only when empty, since a user may have filled one."""
    for raw in sorted(record.get("parents_created") or [], key=len, reverse=True):
        path = recorded_path(ws, raw)
        if path is None:
            report.append(f"{raw}: outside the workspace, left alone")
            continue
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            report.append(f"{path.relative_to(ws)}/: removed")


def main(argv):
    ws = Path(argv[1]).resolve()
    confirm = argv[2] == "1"
    provenance = ws / init_bridge.PROVENANCE
    if not provenance.is_file() and not bridge.inventory_enumerate(ws):
        print("nothing to remove: no vibe-suite artefacts are registered here")
        return 0
    record = bridge.load_json(provenance)
    if not isinstance(record, dict) or not isinstance(record.get("targets"), list):
        print("error: no usable provenance record; unbridge restores from it and will not guess "
              "what to remove", file=sys.stderr)
        return 1

    report = []
    if not confirm:
        for entry in record["targets"]:
            candidate = recorded_path(ws, entry["path"])
            if candidate and bridge.classify(candidate) != "absent":
                report.append(f"{candidate.name}: would be restored or removed")
        json_targets(ws, report, dry=True)
        print("\n".join(report))
        print("\nThis removes every vibe-suite artefact above **and** any legacy cc-suite "
              "registrations. Re-run with --confirm.", file=sys.stderr)
        return 3

    json_targets(ws, report, dry=False)
    for entry in record["targets"]:
        restore(ws, entry, report)
    prune(ws, record, report)
    state = ws / ".vibe-suite-state"
    if state.is_dir():
        for child in sorted(state.rglob("*"), key=lambda p: len(str(p)), reverse=True):
            child.unlink() if child.is_file() else child.rmdir()
        state.rmdir()
        report.append(".vibe-suite-state/: removed")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except bridge.BridgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
