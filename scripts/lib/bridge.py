#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Ownership marking, containment, atomic writes and provenance for the bridge (E2.1 / vibe-18).

**This module owns the sentinel inventory**, and it is the only place that owns it. F1.4 requires the
teardown to iterate a single source — *"fixes cc-suite W4 (incomplete teardown) by making the sentinel
inventory the single source the script iterates"* — so `init`, `bridge`, `repair` and `unbridge` all
read from here. Two independently-maintained lists is the W4 defect itself.

`vibe-mcp` and `vibe-claude-mcp` are literal names. **`vibe-agent:` is a prefix**, not a name: the
concrete agents exist only at runtime, so the inventory exports a rule and an enumerator rather than
three strings.

**Five codecs, because the six targets share no syntax.** JSON has no comments, so ownership there is
structural — a named key under `mcpServers`, or an entry inside an event array carrying its own
marker. A single comment-delimited block cannot express either.
"""

import base64
import json
import os
import re
import sys
from pathlib import Path

SCHEMA = 1
MARKER = "vibe-suite"

#: Literal sentinel names, plus the prefix whose members are discovered at runtime.
SENTINEL_LITERALS = ("vibe-mcp", "vibe-claude-mcp")
SENTINEL_PREFIX = "vibe-agent:"


class BridgeError(Exception):
    """Refusal. The caller aborts; nothing has been written."""


# --------------------------------------------------------------------------------------------
# Containment and atomicity
# --------------------------------------------------------------------------------------------

def assert_inside(root, candidate):
    """Refuse a destination that escapes the workspace.

    `scripts/lib/config.py` enforces this for config paths; nothing enforced it for bridge writes,
    so a workspace whose `.claude/` is a symlink could direct an install anywhere.
    """
    root_real = Path(root).resolve()
    target = Path(candidate)
    probe = target if target.exists() or target.is_symlink() else target.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    resolved = probe.resolve()
    if resolved != root_real and root_real not in resolved.parents:
        raise BridgeError(f"{candidate} resolves outside the workspace ({resolved})")


def classify(path):
    """`lstat`-based node kind. A broken symlink is a symlink, not `other`."""
    p = Path(path)
    if not p.is_symlink() and not p.exists():
        return "absent"
    if p.is_symlink():
        return "symlink"
    mode = p.lstat().st_mode
    if os.path.stat.S_ISDIR(mode) if hasattr(os.path, "stat") else p.is_dir():
        return "dir"
    if p.is_file():
        return "file"
    return "other"


def write_atomic(root, dest, content):
    """Same-directory temp file, fsync, rename, directory fsync.

    Full-file replacement only — no truncating in-place edit, so an interrupted write leaves either
    the old file or the new one.
    """
    assert_inside(root, dest)
    dest = Path(dest)
    kind = classify(dest)
    if kind == "dir":
        raise BridgeError(f"{dest} is a directory where a file belongs; its contents are not "
                          "restorable from the provenance record, so the install refuses")
    if kind == "other":
        raise BridgeError(f"{dest} is neither a file nor a symlink; the install refuses")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.vibe-tmp"
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, dest)
    fd = os.open(dest.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


# --------------------------------------------------------------------------------------------
# Provenance
# --------------------------------------------------------------------------------------------

def record_pre_image(path):
    """Enough to restore, or an explicit refusal.

    `content_b64` because a JSON string cannot carry arbitrary non-UTF-8 bytes, and the installer
    does not get to assume a user's file is text.
    """
    p = Path(path)
    kind = classify(p)
    entry = {"path": str(p), "kind": kind}
    if kind == "symlink":
        entry["link_target"] = os.readlink(p)
    elif kind == "file":
        entry["mode"] = oct(p.lstat().st_mode & 0o7777)
        entry["content_b64"] = base64.b64encode(p.read_bytes()).decode("ascii")
    elif kind in ("dir", "other"):
        raise BridgeError(f"{p} is a {kind} where a file belongs; the install refuses")
    return entry


def parents_created(root, dest):
    """Directories this install would bring into existence, so #21 can remove them."""
    made, probe = [], Path(dest).parent
    root = Path(root).resolve()
    while probe != root and root in probe.resolve().parents or probe == root:
        if probe == root or probe.exists():
            break
        made.append(str(probe))
        probe = probe.parent
    return list(reversed(made))


# --------------------------------------------------------------------------------------------
# Codecs — has / upsert / remove over one inventory
# --------------------------------------------------------------------------------------------

def _block(name, body, open_delim, close_delim):
    return (f"{open_delim} >>> {MARKER}:{name} v{SCHEMA} >>>{close_delim}\n"
            f"{body.rstrip()}\n"
            f"{open_delim} <<< {MARKER}:{name} <<<{close_delim}\n")


def _block_re(name, open_delim, close_delim):
    return re.compile(
        rf"{re.escape(open_delim)} >>> {re.escape(MARKER)}:{re.escape(name)} v\d+ >>>"
        rf"{re.escape(close_delim)}\n.*?"
        rf"{re.escape(open_delim)} <<< {re.escape(MARKER)}:{re.escape(name)} <<<"
        rf"{re.escape(close_delim)}\n",
        re.S)


def text_block_upsert(existing, name, body, open_delim="#", close_delim=""):
    """Replace between markers, or append. Idempotent: identical input yields identical output."""
    block = _block(name, body, open_delim, close_delim)
    pattern = _block_re(name, open_delim, close_delim)
    if pattern.search(existing):
        return pattern.sub(lambda _: block, existing, count=1)
    prefix = existing if existing.endswith("\n") or not existing else existing + "\n"
    return (prefix + "\n" if prefix else "") + block


def md_block_upsert(existing, name, body):
    return text_block_upsert(existing, name, body, "<!--", " -->")


def json_server_upsert(doc, name, entry):
    doc.setdefault("mcpServers", {})[name] = entry
    return doc


def json_hook_entry_upsert(doc, event, entry):
    """Ownership inside an event array. The entry carries its own marker, because a list member has
    no key to be owned by, and a user's entries share the array."""
    entry = dict(entry, **{f"_{MARKER}_owned": SCHEMA})
    events = doc.setdefault("hooks", {}).setdefault(event, [])
    for index, existing in enumerate(events):
        if isinstance(existing, dict) and existing.get(f"_{MARKER}_owned") is not None:
            events[index] = entry
            return doc
    events.append(entry)
    return doc


def owned_names(doc):
    """Every suite-owned server name in a parsed `.mcp.json`: the literals plus every concrete
    member of the `vibe-agent:` family."""
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    found = [n for n in servers if n in SENTINEL_LITERALS or n.startswith(SENTINEL_PREFIX)]
    return sorted(found)


def load_json(path):
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise BridgeError(f"{p} is not valid JSON ({exc}); the install refuses rather than "
                          "overwrite a file it cannot read") from exc


def main(argv):
    if len(argv) >= 3 and argv[1] == "list-owned":
        for name in owned_names(load_json(Path(argv[2]) / ".mcp.json")):
            print(name)
        return 0
    print("usage: bridge.py list-owned <workspace>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
