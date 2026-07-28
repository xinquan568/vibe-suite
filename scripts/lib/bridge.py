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
import hashlib
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


def _open_dir_chain(root, relative):
    """Open `root/relative` by walking one component at a time, each with `O_NOFOLLOW`.

    Opening the parent by path resolves every *ancestor* through the kernel, so containment checked
    beforehand says nothing about what those components are at the moment of the call — a swapped
    grandparent redirects the whole subtree. Descending component by component removes the ambiguity:
    each step is relative to a descriptor already proven to be a real directory, and a symlink
    anywhere along the way fails the step that would have followed it.
    """
    for flag in ("O_DIRECTORY", "O_NOFOLLOW"):
        if not hasattr(os, flag):
            raise BridgeError(
                f"this platform lacks os.{flag}; the install refuses rather than write through a "
                "path it cannot resolve safely")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in relative:
            if part in ("", "."):
                continue
            if part == "..":
                raise BridgeError("'..' in a bridge target path; refusing")
            try:
                os.mkdir(part, 0o777, dir_fd=fd)
            except FileExistsError:
                pass
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
    except OSError as exc:
        os.close(fd)
        raise BridgeError(f"{root}/{'/'.join(relative)} could not be opened safely ({exc})") from exc
    except BaseException:
        os.close(fd)
        raise
    return fd


def write_atomic(root, dest, content, mode=None):
    """Replace a file atomically, without ever resolving its parent path twice.

    `O_NOFOLLOW` on the temp file guards only its final component. The parent is still resolved by
    the kernel on every path-based call, so a directory swapped for a symlink between the
    containment check and the write escapes anyway. Opening the parent **once** with
    `O_DIRECTORY|O_NOFOLLOW` and then working relative to that descriptor removes the window: every
    subsequent operation names the directory by handle, not by path.
    """
    assert_inside(root, dest)
    dest = Path(dest)
    kind = classify(dest)
    if kind == "dir":
        raise BridgeError(f"{dest} is a directory where a file belongs; its contents are not "
                          "restorable from the provenance record, so the install refuses")
    if kind == "other":
        raise BridgeError(f"{dest} is neither a file nor a symlink; the install refuses")

    # A file's existing mode is the user's, not ours. An earlier revision created the temp at 0600
    # and never restored it, so every rewritten file silently became owner-only.
    if mode is None:
        mode = (dest.lstat().st_mode & 0o7777) if kind == "file" else 0o644

    relative = Path(dest).parent.relative_to(Path(root)).parts
    dir_fd = _open_dir_chain(root, relative)

    data = content if isinstance(content, bytes) else content.encode("utf-8")
    tmp_name = f".{dest.name}.vibe-tmp"
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(tmp_name, flags, mode, dir_fd=dir_fd)
        except FileExistsError as exc:
            raise BridgeError(f"{dest.parent / tmp_name} already exists; refusing to write "
                              "through it") from exc
        except OSError as exc:
            raise BridgeError(f"{dest.parent / tmp_name} could not be created safely "
                              f"({exc})") from exc
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if kind == "file":
                # Restore the user's mode exactly. For a *new* file the open() mode already went
                # through umask, and re-chmod'ing would override the user's umask policy.
                os.chmod(tmp_name, mode, dir_fd=dir_fd, follow_symlinks=False)
            os.replace(tmp_name, dest.name, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
        except BaseException:
            try:
                os.unlink(tmp_name, dir_fd=dir_fd)
            except OSError:
                pass
            raise
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


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
        raw = p.read_bytes()
        entry["mode"] = oct(p.lstat().st_mode & 0o7777)
        entry["sha256"] = hashlib.sha256(raw).hexdigest()
        entry["content_b64"] = base64.b64encode(raw).decode("ascii")
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
    """Replace between markers, or append. Idempotent: identical input yields identical output.

    A second marker pair for the same name is refused rather than silently half-replaced: two owned
    regions means an earlier run or a hand edit left the file in a state this function cannot
    reconcile, and picking the first would strand the other forever.
    """
    block = _block(name, body, open_delim, close_delim)
    pattern = _block_re(name, open_delim, close_delim)
    found = pattern.findall(existing)
    opens = existing.count(f"{open_delim} >>> {MARKER}:{name} ")
    closes = existing.count(f"{open_delim} <<< {MARKER}:{name} ")
    if len(found) > 1 or opens != closes or opens > len(found):
        raise BridgeError(
            f"{name}: found {opens} opening and {closes} closing markers for "
            f"{len(found)} well-formed block(s); refusing to guess which region is owned")
    if found:
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


def text_block_has(existing, name, open_delim="#", close_delim=""):
    return bool(_block_re(name, open_delim, close_delim).search(existing))


def text_block_remove(existing, name, open_delim="#", close_delim=""):
    """The exact inverse of `text_block_upsert`, so a clean install→remove round trip is
    byte-identical.

    Upsert appends `"\n" + block` to a non-empty file. Removal takes that one separator back and
    nothing else. An earlier revision normalised `\n\n\n` to `\n\n` anywhere in the file, which
    silently rewrote blank lines a user had put between their *own* paragraphs.
    """
    pattern = _block_re(name, open_delim, close_delim)
    match = pattern.search(existing)
    if not match:
        return existing
    start, end = match.span()
    # Reclaim the single separator newline upsert inserted before the block, if it is there.
    if start >= 1 and existing[start - 1] == "\n" and (start == 1 or existing[start - 2] == "\n"):
        start -= 1
    return existing[:start] + existing[end:]


def md_block_has(existing, name):
    return text_block_has(existing, name, "<!--", " -->")


def md_block_remove(existing, name):
    return text_block_remove(existing, name, "<!--", " -->")


def toml_server_upsert(existing, name, body):
    """`[mcp_servers.<name>]` plus its subtables. A subtable alone is not a registration —
    `migrate-sentinels.sh:151-160` already encodes that distinction, and a codec that ignored it
    would treat `[mcp_servers.x.env]` as evidence that `x` is registered."""
    return text_block_upsert(existing, f"server:{name}", body)


def toml_server_remove(existing, name):
    return _block_re(f"server:{name}", "#", "").sub("", existing)


def toml_server_has(existing, name):
    return bool(_block_re(f"server:{name}", "#", "").search(existing))


def toml_owned_names(text):
    """Concrete owned servers declared in a TOML document, including `vibe-agent:` members.

    Enumeration has to span every codec: an agent registered only in `.codex/config.toml` is invisible
    to a JSON-only sweep, and #21's teardown iterates whatever this returns.
    """
    found = set()
    for header in re.findall(r"^\s*\[mcp_servers\.(.+?)\]\s*$", text, re.M):
        rest = header.strip()
        # Split on the first dot *outside* quotes: `"vibe-agent:auditor".env` is a subtable of
        # `vibe-agent:auditor`, and a name may itself contain dots only when quoted.
        if rest.startswith(('"', "'")):
            quote = rest[0]
            end = rest.find(quote, 1)
            if end == -1:
                continue
            name, trailer = rest[1:end], rest[end + 1:]
        else:
            name, _, trailer = rest.partition(".")
            trailer = "." + trailer if trailer else ""
        if trailer.strip():
            continue          # a subtable is not a registration
        if name in SENTINEL_LITERALS or name.startswith(SENTINEL_PREFIX):
            found.add(name)
    return sorted(found)


def json_server_has(doc, name):
    return name in (doc.get("mcpServers") or {})


def json_server_remove(doc, name):
    (doc.get("mcpServers") or {}).pop(name, None)
    return doc


def json_hook_entry_remove(doc, event):
    events = (doc.get("hooks") or {}).get(event) or []
    (doc.get("hooks") or {})[event] = [
        e for e in events
        if not (isinstance(e, dict) and e.get(f"_{MARKER}_owned") is not None)]
    return doc


def json_hook_entry_has(doc, event):
    return any(isinstance(e, dict) and e.get(f"_{MARKER}_owned") is not None
               for e in (doc.get("hooks") or {}).get(event) or [])


def inventory_enumerate(root):
    """Every suite-owned sentinel in a workspace, across every store that can hold one.

    This is the single source F1.4 requires teardown to iterate. Two independently-maintained lists
    is the cc-suite W4 defect itself.
    """
    root = Path(root)
    names = set(owned_names(load_json(root / ".mcp.json")))
    toml = root / ".codex" / "config.toml"
    if toml.is_file():
        names |= set(toml_owned_names(toml.read_text(encoding="utf-8", errors="replace")))
    return sorted(names)


def owned_names(doc):
    """Every suite-owned server name in a parsed `.mcp.json`: the literals plus every concrete
    member of the `vibe-agent:` family."""
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    found = [n for n in servers if n in SENTINEL_LITERALS or n.startswith(SENTINEL_PREFIX)]
    return sorted(found)


def read_text_verbatim(path):
    """Text with its line endings intact. `Path.read_text()` normalises CRLF to LF, so a
    read-modify-write silently rewrites every line of a CRLF file."""
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_bytes().decode("utf-8", errors="surrogateescape")


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
        for name in inventory_enumerate(argv[2]):
            print(name)
        return 0
    print("usage: bridge.py list-owned <workspace>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
