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

#: `O_NOFOLLOW` where the platform has it; 0 elsewhere, so the flag composes unconditionally.
O_NOFOLLOW_FLAG = getattr(os, "O_NOFOLLOW", 0)

#: Literal sentinel names, plus the prefix whose members are discovered at runtime.
SENTINEL_LITERALS = ("vibe-mcp", "vibe-claude-mcp")
SENTINEL_PREFIX = "vibe-agent:"

#: Advisor ownership is structural, not nominal (E6.1 / vibe-47): an advisor registers under its
#: bare name — the skill's `mcp__<name>__<tool_name>` callable identity requires the server key to
#: BE the name — so the claim of ownership travels inside the entry, exactly as owned hook entries
#: carry theirs. Only this exact marker value is a claim; anything else is a user's key.
ADVISOR_MARKER_KEY = f"_{MARKER}_owned"
ADVISOR_MARKER = {"kind": "advisor", "schema": SCHEMA}

OWNED_BLOCKS = (("AGENTS.md", "memory", "md"), ("CLAUDE.md", "import", "md"),
                ("GEMINI.md", "import", "md"), (".gitignore", "ignore", "text"),
                (".gitignore", "advisor-ignore", "text"),
                (".codex/config.toml", "server:vibe-mcp", "text"))


class BridgeError(Exception):
    """Refusal. The caller aborts; nothing has been written."""


# --------------------------------------------------------------------------------------------
# Containment and atomicity
# --------------------------------------------------------------------------------------------

def assert_root(root):
    """Refuse a root that is itself a symlink.

    Containment compares the destination against `root`, so when a caller passes the destination's
    own parent — and that parent is a symlink out of the workspace — the check compares the escape
    against itself and passes it. Refusing here makes the mistake impossible to make quietly rather
    than relying on every caller choosing the right anchor.
    """
    if Path(root).is_symlink():
        raise BridgeError(
            f"{root} is a symlink and cannot be the containment root; pass the workspace")


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


#: Identity of each workspace root this process has opened, so a mid-run replacement is detected
#: rather than silently followed. Keyed by the **caller-supplied** path — keying by the resolved path
#: would mint a fresh pin for a swapped-in directory and never notice the swap.
_ROOT_PIN = {}


def pin_root(root):
    """Establish the root's identity **before** anything reads or writes through it.

    The pin used to be created lazily, on the first descriptor operation — which happens after
    provenance validation and after path-based reads. A workspace swapped before that point simply
    became the pinned one, and the record was then applied to it. A command that will delete calls
    this at entry, so every later step is checked against the directory the decisions were made
    about.
    """
    fd = os.open(os.path.realpath(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
    finally:
        os.close(fd)
    _ROOT_PIN[str(root)] = (st.st_dev, st.st_ino)
    return _ROOT_PIN[str(root)]


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
    # The root is the trust anchor, so it is resolved **once** and then opened `O_NOFOLLOW`.
    # Opening it by the caller's path re-resolved every ancestor on every call, which let a swap of
    # the root itself (or any component above it) redirect the entire descent — including deletions —
    # outside the workspace. `realpath` has no symlink final component by construction, so
    # `O_NOFOLLOW` here rejects exactly the case where that component became one after we looked.
    anchor = os.path.realpath(root)
    fd = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        # Keyed by the path the caller handed us, not by what it resolved to: keying by the resolved
        # path would mint a fresh pin for the swapped-in directory and never notice the swap.
        key = str(root)
        if _ROOT_PIN.get(key) is None:
            _ROOT_PIN[key] = (st.st_dev, st.st_ino)
        elif _ROOT_PIN[key] != (st.st_dev, st.st_ino):
            raise BridgeError(
                f"{root} is not the directory this operation started against; refusing")
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


def open_dir_chain(root, relative):
    """Public name for the component-wise `O_NOFOLLOW` descent.

    `bridge_cli` carried its own copy of this, which is the pattern this module exists to end: a
    second implementation of a safety rule drifts from the first, and the copy had none of the
    refusals added here since. One descent, one place.
    """
    return _open_dir_chain(root, relative)


def unlink_at(root, rel):
    """Remove a workspace-relative entry, never following a symlink in its path.

    Deleting by path re-resolves every component at call time, so a symlink planted anywhere along it
    redirects the removal — which is how a teardown deletes a user's file. Resolving the parent once
    and unlinking relative to that descriptor removes the window.
    """
    import stat as _stat
    rel = Path(rel)
    assert_inside(root, Path(root) / rel)
    fd = _open_dir_chain(root, rel.parent.parts)
    try:
        try:
            info = os.lstat(rel.name, dir_fd=fd)
        except FileNotFoundError:
            return False
        # A directory needs rmdir, and which error unlink raises on one is platform-dependent —
        # macOS says PermissionError where Linux says IsADirectoryError. The node type is not.
        if _stat.S_ISDIR(info.st_mode):
            os.rmdir(rel.name, dir_fd=fd)
        else:
            os.unlink(rel.name, dir_fd=fd)
        return True
    finally:
        os.close(fd)


def remove_tree_at(root, rel):
    """Recursively remove the directory at `root/rel` through the audited descent.

    Every destructive step is descriptor-relative with `O_NOFOLLOW`: a symlink inside the tree is
    unlinked as a link — its target is never opened, so a link pointing outward cannot export the
    deletion. A `rel` that is itself a symlink is refused rather than followed, and a `rel` with
    dot/dotdot components never reaches the walk. Returns False when nothing exists at `rel`.
    """
    import stat as _stat
    rel = Path(rel)
    assert_root(root)
    assert_inside(root, Path(root) / rel)
    if not rel.parts or any(p in ("", ".", "..") for p in rel.parts):
        raise BridgeError(f"{rel} is not a plain workspace-relative directory path; refusing")
    # Read-only existence probe by path: the destructive walk below is fd-relative regardless, and
    # probing first keeps `_open_dir_chain` from creating parents for a tree that is not there.
    if not os.path.lexists(os.path.join(str(root), str(rel))):
        return False
    fd = _open_dir_chain(root, rel.parent.parts)
    try:
        info = os.lstat(rel.name, dir_fd=fd)
        if _stat.S_ISLNK(info.st_mode):
            raise BridgeError(f"{Path(root) / rel} is a symlink; refusing to remove a tree "
                              "through it")
        if not _stat.S_ISDIR(info.st_mode):
            raise BridgeError(f"{Path(root) / rel} is not a directory; unlink_at removes files")
        _remove_tree_fd(fd, rel.name)
    except FileNotFoundError:
        return False
    finally:
        os.close(fd)
    return True


def ensure_dir_at(root, rel):
    """Create the directory chain `root/rel` through the audited `O_NOFOLLOW` descent.

    `Path.mkdir(parents=True)` resolves every ancestor by path, so a symlink planted at any
    component redirects the creation outside the workspace. The descent creates each component
    relative to a proven directory descriptor and fails on the component that is a symlink.
    """
    rel = Path(rel)
    assert_inside(root, Path(root) / rel)
    if any(p == ".." for p in rel.parts):
        raise BridgeError(f"{rel}: '..' in a directory-creation path; refusing")
    fd = _open_dir_chain(root, rel.parts)
    os.close(fd)


def _remove_tree_fd(parent_fd, name):
    """Depth-first removal relative to an already-proven directory descriptor."""
    import stat as _stat
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | O_NOFOLLOW_FLAG, dir_fd=parent_fd)
    try:
        for entry in os.listdir(fd):
            info = os.lstat(entry, dir_fd=fd)
            if _stat.S_ISDIR(info.st_mode):
                _remove_tree_fd(fd, entry)
            else:
                os.unlink(entry, dir_fd=fd)
    finally:
        os.close(fd)
    os.rmdir(name, dir_fd=parent_fd)


#: Identity of each workspace root this process has opened, so a mid-run replacement is detected
#: rather than silently followed. Keyed by the **caller-supplied** path — keying by the resolved path
#: would mint a fresh pin for a swapped-in directory and never notice the swap.
_ROOT_PIN = {}


def rename_at(root, src_rel, dst_rel):
    """Atomically rename SRC to DST inside the root, both parents opened descriptor-relative
    (E7.2 / vibe-54 - the mirror swap's exchange step). DST must not exist; the caller owns
    collision policy. Descriptor-relative on both ends, so neither parent is resolved twice."""
    assert_root(root)
    src, dst = Path(src_rel), Path(dst_rel)
    assert_inside(root, Path(root) / src)
    assert_inside(root, Path(root) / dst)
    src_fd = open_dir_chain(root, src.parent.parts)
    try:
        dst_fd = open_dir_chain(root, dst.parent.parts)
        try:
            os.rename(src.name, dst.name, src_dir_fd=src_fd, dst_dir_fd=dst_fd)
        finally:
            os.close(dst_fd)
    finally:
        os.close(src_fd)


def symlink_at(root, rel, target):
    """Create `root/rel` -> `target`, relative to the audited descent.

    Returns True when the link was created, False when something was already there — a caller must
    never learn "it exists" by having clobbered it.
    """
    rel = Path(rel)
    assert_inside(root, Path(root) / rel)
    fd = _open_dir_chain(root, rel.parent.parts)
    try:
        os.symlink(str(target), rel.name, dir_fd=fd)
        return True
    except FileExistsError:
        return False
    finally:
        os.close(fd)


def publish_new(root, dest, content, mode=0o644):
    """Create `dest` with `content`, or report that something is already there. Never overwrites.

    The other half of the write surface. `write_atomic` *replaces*; this one *publishes*, and the
    distinction is the whole safety argument for row 3's history migration: a store that appeared
    while the migration ran must win, so the publication step has to fail rather than clobber.

    Returns True when it created the file, False when the destination already existed. The link is
    made from a fully written inode, so a reader never sees a partial file.
    """
    dest = Path(dest)
    assert_root(root)
    assert_inside(root, dest)
    if dest.is_symlink():
        # `lstat`, never `exists`: a dangling symlink reports False from `exists()`, and publishing
        # through it would write to wherever it points.
        raise BridgeError(f"{dest} is a symlink; refusing to publish through it")
    rel = dest.relative_to(Path(root))
    fd = _open_dir_chain(root, rel.parent.parts)
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    tmp_name = None
    try:
        handle, tmp_name = _scratch(fd, dest.name, mode)
        with os.fdopen(handle, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(tmp_name, dest.name, src_dir_fd=fd, dst_dir_fd=fd)
        except FileExistsError:
            return False
        _fsync_dir(fd)
        return True
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name, dir_fd=fd)
            except FileNotFoundError:
                pass
        os.close(fd)


def _scratch(dir_fd, name, mode):
    """An `O_EXCL` scratch file with an unpredictable name, created at `mode` from the start.

    Both properties matter: a fixed name is a path the user may own, and creating at the default and
    chmod-ing afterwards leaves a window in which a private file is readable — the window *is* the
    leak.
    """
    import binascii
    for _ in range(64):
        suffix = binascii.hexlify(os.urandom(6)).decode("ascii")
        candidate = f".{name}.{suffix}.vibe-tmp"
        try:
            return os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | O_NOFOLLOW_FLAG,
                           mode, dir_fd=dir_fd), candidate
        except FileExistsError:
            continue
    raise BridgeError("could not create a scratch file after 64 attempts")


def _fsync_dir(dir_fd):
    try:
        os.fsync(dir_fd)
    except OSError:
        pass


def secure_dir(root, rel, mode=0o700):
    """Tighten a directory we own, through the audited descent.

    A directory mode is not a file write, so it needs its own entry point rather than being inlined
    at the one call site that wanted it — the same reasoning that gave `unlink_at` and `symlink_at`
    a home. `fchmod` on the descriptor, never `chmod` on the path: a path-based call after the
    descent can be redirected by swapping the name.
    """
    rel = Path(rel)
    assert_inside(root, Path(root) / rel)
    fd = _open_dir_chain(root, rel.parts)
    try:
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def lstat_at(root, rel):
    """`lstat` a workspace-relative path without resolving any component by path."""
    rel = Path(rel)
    fd = _open_dir_chain(root, rel.parent.parts)
    try:
        return os.lstat(rel.name, dir_fd=fd)
    except FileNotFoundError:
        return None
    finally:
        os.close(fd)


def pin_root(root):
    """Establish the root's identity **before** anything reads or writes through it.

    The pin used to be created lazily, on the first descriptor operation — which happens after
    provenance validation and after path-based reads. A workspace swapped before that point simply
    became the pinned one, and the record was then applied to it. A command that will delete calls
    this at entry, so every later step is checked against the directory the decisions were made
    about.
    """
    fd = os.open(os.path.realpath(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
    finally:
        os.close(fd)
    _ROOT_PIN[str(root)] = (st.st_dev, st.st_ino)
    return _ROOT_PIN[str(root)]


def write_atomic(root, dest, content, mode=None):
    """Replace a file atomically, without ever resolving its parent path twice.

    `O_NOFOLLOW` on the temp file guards only its final component. The parent is still resolved by
    the kernel on every path-based call, so a directory swapped for a symlink between the
    containment check and the write escapes anyway. Opening the parent **once** with
    `O_DIRECTORY|O_NOFOLLOW` and then working relative to that descriptor removes the window: every
    subsequent operation names the directory by handle, not by path.
    """
    assert_root(root)
    assert_inside(root, dest)
    dest = Path(dest)
    kind = classify(dest)
    if kind == "dir":
        raise BridgeError(f"{dest} is a directory where a file belongs; its contents are not "
                          "restorable from the provenance record, so the install refuses")
    if kind == "other":
        raise BridgeError(f"{dest} is neither a file nor a symlink; the install refuses")
    if kind == "symlink":
        # `classify()` has always returned "symlink"; nothing acted on it, so `os.replace` below
        # converted the user's link into a regular file. The bytes at the far end survive, but the
        # link does not — and teardown records `kind: symlink` while never restoring one, so the
        # conversion is permanent.
        #
        # Refusing is the fix rather than restoring later: the destructive step is the conversion,
        # and a step never taken needs no undo.
        raise BridgeError(
            f"{dest} is a symlink; replacing it would convert the user's link into a regular file "
            f"and could not be undone by /vibe-suite:unbridge. Remove or re-point it and re-run")

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


def _marker_open(name, open_delim, close_delim):
    """The opening marker, anchored to a whole line."""
    return (rf"^{re.escape(open_delim)} >>> {re.escape(MARKER)}:{re.escape(name)} v\d+ >>>"
            rf"{re.escape(close_delim)}$")


def _marker_close(name, open_delim, close_delim):
    """The closing marker, anchored to a whole line."""
    return (rf"^{re.escape(open_delim)} <<< {re.escape(MARKER)}:{re.escape(name)} <<<"
            rf"{re.escape(close_delim)}$")


def _block_re(name, open_delim, close_delim):
    """Detection and removal, built from the **same** anchored markers the validator uses.

    This was two regexes: an unanchored one here and an anchored one in `markers_wellformed`. A line
    like `prefix # >>> vibe-suite:x v1 >>>` therefore counted as zero markers to the validator — so
    the document passed as well-formed — while still matching here, and removal deleted through the
    user's content between it and the next close. Two parsers for one grammar is the defect; the
    parity is now structural rather than a thing to keep in step by hand.
    """
    return re.compile(
        _marker_open(name, open_delim, close_delim) + r"\n.*?"
        + _marker_close(name, open_delim, close_delim) + r"\n",
        re.S | re.M)


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


def markers_wellformed(existing, name, open_delim="#", close_delim=""):
    """Whether this document's markers for `name` are clean, non-overlapping, full-line pairs.

    `_block_re` matches non-greedily from an opening marker to the *next* close, so a stray or
    duplicated opening marker makes the match start early and swallow everything up to the real
    block's close — user content included. Validation therefore has to live **here**, beside the
    removal it guards: a check in one caller left every other caller (`toml_server_remove` among
    them) removing unvalidated.

    The grammar is not merely *like* `_block_re`'s — it is built from the same two functions, so the
    two cannot drift. A validator that recognised a marker the remover did not (or the reverse) would
    pass a document whose removal still spans user data.
    """
    opens = [m.start() for m in re.finditer(
        _marker_open(name, open_delim, close_delim), existing, re.M)]
    closes = [m.start() for m in re.finditer(
        _marker_close(name, open_delim, close_delim), existing, re.M)]
    if len(opens) != len(closes):
        return False
    expect = "o"
    for _, kind in sorted([(p, "o") for p in opens] + [(p, "c") for p in closes]):
        if kind != expect:
            return False
        expect = "c" if expect == "o" else "o"
    return True


def text_block_remove(existing, name, open_delim="#", close_delim=""):
    """The exact inverse of `text_block_upsert`, so a clean install→remove round trip is
    byte-identical.

    Upsert appends `"\n" + block` to a non-empty file. Removal takes that one separator back and
    nothing else. An earlier revision normalised `\n\n\n` to `\n\n` anywhere in the file, which
    silently rewrote blank lines a user had put between their *own* paragraphs.

    Refuses a document whose markers are malformed rather than removing across them.
    """
    if not markers_wellformed(existing, name, open_delim, close_delim):
        raise BridgeError(
            f"owned markers for {name!r} are malformed; refusing to remove across them")
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
    return text_block_remove(existing, f"server:{name}")


def toml_server_has(existing, name):
    return bool(_block_re(f"server:{name}", "#", "").search(existing))


def toml_table_names(text):
    """Every top-level `[mcp_servers.<name>]` table name in a TOML document.

    One parser for every consumer — enumeration and collision detection alike — because two
    parsers for one grammar is how `[mcp_servers.'probe']` collided invisibly: the collision
    check recognized bare and double-quoted keys while this function's grammar also knew single
    quotes. TOML permits whitespace around the dots and either quote kind; a subtable is not a
    registration.
    """
    names = []
    for header in re.findall(r"^\s*\[\s*mcp_servers\s*\.\s*(.+?)\s*\]\s*$", text, re.M):
        rest = header.strip()
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
        names.append(name)
    return names


def toml_owned_names(text):
    """Concrete owned servers declared in a TOML document, including `vibe-agent:` members.

    Enumeration has to span every codec: an agent registered only in `.codex/config.toml` is invisible
    to a JSON-only sweep, and #21's teardown iterates whatever this returns.
    """
    found = set()
    for name in toml_table_names(text):
        if name in SENTINEL_LITERALS or name.startswith(SENTINEL_PREFIX):
            found.add(name)
    # A bare-name advisor block is owned by its fence, not its name: the `server:<name>` markers
    # `toml_server_upsert` writes are the TOML-side twin of the JSON entry's advisor marker.
    for fenced in re.findall(
            rf"^# >>> {re.escape(MARKER)}:server:(.+?) v\d+ >>>$", text, re.M):
        if re.search(r"^\s*\[mcp_servers\.(?:%s|\"%s\")(?:\.[^]]+)?\]\s*$"
                     % (re.escape(fenced), re.escape(fenced)), text, re.M):
            found.add(fenced)
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


def advisor_owned_entry(entry):
    """Whether a server entry carries the exact advisor ownership marker.

    Exact-match on purpose — including *types*: Python's `==` treats `True`, `1` and `1.0` as
    equal, so a plain dict comparison would claim `{"schema": true}` and make teardown delete an
    entry the suite never wrote. A malformed or coerced marker is a user's key, not our claim.
    """
    if not isinstance(entry, dict):
        return False
    marker = entry.get(ADVISOR_MARKER_KEY)
    if not isinstance(marker, dict) or set(marker) != set(ADVISOR_MARKER):
        return False
    kind, schema = marker.get("kind"), marker.get("schema")
    return (type(kind) is str and kind == ADVISOR_MARKER["kind"]
            and type(schema) is int and not isinstance(schema, bool)
            and schema == ADVISOR_MARKER["schema"])


def owned_names(doc):
    """Every suite-owned server name in a parsed `.mcp.json`: the literals, every concrete member
    of the `vibe-agent:` family, and every bare-name entry carrying the advisor marker."""
    servers = doc.get("mcpServers", {}) if isinstance(doc, dict) else {}
    found = [n for n in servers if n in SENTINEL_LITERALS or n.startswith(SENTINEL_PREFIX)
             or advisor_owned_entry(servers[n])]
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
    if len(argv) >= 4 and argv[1] == "write":
        # For shell callers. A native redirection (`printf ... > path`) **follows a symlink**, so a
        # link planted at a fixed path redirects the write onto whatever it points at — and
        # redirections are invisible to the AST lint, which is how one survived the sweep that
        # routed every Python write. Content arrives on stdin so no argv limit applies.
        root, dest = Path(argv[2]), Path(argv[3])
        mode = int(argv[4], 8) if len(argv) >= 5 else None
        write_atomic(root, dest, sys.stdin.read(), mode=mode)
        return 0
    if len(argv) >= 4 and argv[1] == "publish":
        # Create-only, for shell callers. `mv -f` clobbers; this refuses, which is what "a store
        # that appeared while we ran still wins" requires.
        root, dest = Path(argv[2]), Path(argv[3])
        return 0 if publish_new(root, dest, sys.stdin.read()) else 0
    if len(argv) >= 3 and argv[1] == "list-owned":
        for name in inventory_enumerate(argv[2]):
            print(name)
        return 0
    print("usage: bridge.py list-owned <workspace>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
