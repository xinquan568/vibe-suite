#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The filesystem-safety kernel of the Python half (M9 / vibe-223) — carved out of `bridge.py`, byte-for-byte.

**What lives here and nothing else:** containment (`assert_root`, `assert_inside`, `classify`), the descriptor-relative
`O_NOFOLLOW` descent with its root pin (`pin_root`, `_open_dir_chain`/`open_dir_chain`, `_ROOT_PIN` — one dict, shared by
the two, so a workspace swapped mid-run is detected rather than followed), the mutation primitives that ride the descent
(`unlink_at`, `remove_tree_at`, `ensure_dir_at`, `rename_at`, `symlink_at`, `secure_dir`, `lstat_at`), the two write
primitives (`write_atomic` — replace; `publish_new` — create-only) and their scratch discipline (`_scratch`,
`_fsync_dir`), and the two refusal classes every caller catches (`BridgeError`, `AbsentPath`). The codecs, the sentinel
inventory, provenance, the anchored writes and the shell CLI stay in `bridge.py`, which imports this module; nothing here
imports `bridge`, so the dependency runs one way.

**What this refuses, stated once.** A root that is a symlink; a destination that resolves outside the root; a `..`
component; a symlink at any component of the descent (each step is `O_DIRECTORY|O_NOFOLLOW` relative to the descriptor
already proven to be a real directory) or at the destination (`lstat`, never `exists`, so a dangling link is a link);
a fixed-name scratch (names are unpredictable `O_EXCL|O_NOFOLLOW`, created at the requested mode). **What it does not
close:** a same-uid attacker is out of scope exactly as it is for `write.mjs`; a new file keeps the umask-filtered
creation mode by design (a replaced file gets its own mode back exactly) — the shared invariant list in
`tests/fixtures/write-invariants/` states what both kernels guarantee.

Stdlib only; no bootstrap, no `sys.path`, no imports from this repository — the module is a leaf.
"""

import binascii
import os
from pathlib import Path

#: `O_NOFOLLOW` where the platform has it; 0 elsewhere, so the flag composes unconditionally.
O_NOFOLLOW_FLAG = getattr(os, "O_NOFOLLOW", 0)


class BridgeError(Exception):
    """Refusal. The caller aborts; nothing has been written."""


class AbsentPath(BridgeError):
    """A component of the requested path does not exist (vibe-179).

    Raised by the audited descent when it is asked NOT to create and a directory on the way is
    missing — the only descent failure that means "nothing is there" rather than "something is
    there that must not be followed". Read and delete primitives translate it into their existing
    absent-leaf answers (`None` / `False`); every other descent failure stays a plain `BridgeError`.
    """


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


def _open_dir_chain(root, relative, create=False):
    """Open `root/relative` by walking one component at a time, each with `O_NOFOLLOW`.

    Opening the parent by path resolves every *ancestor* through the kernel, so containment checked
    beforehand says nothing about what those components are at the moment of the call — a swapped
    grandparent redirects the whole subtree. Descending component by component removes the ambiguity:
    each step is relative to a descriptor already proven to be a real directory, and a symlink
    anywhere along the way fails the step that would have followed it.

    `create` is opt-in (vibe-179 / grill M10). The descent used to `mkdir` every missing component
    as a side effect of opening it, for every caller — so a read (`lstat_at`) or a deletion
    (`unlink_at`) minted directories the user never had, and a teardown could leave behind a
    `.codex/` the user had removed. Only the primitives whose purpose is to bring a path into
    existence (`ensure_dir_at`, `write_atomic`, `publish_new`, `symlink_at`) pass `create=True`;
    everything else gets `AbsentPath` for a missing component and leaves the tree untouched.
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
    try:
        fd = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        # The root is the trust anchor, not a component: a workspace that is missing, a file, or
        # a symlink is a refusal (`BridgeError`, the `OSError` kept as `__cause__`) — never
        # `AbsentPath`, which would let a read answer "nothing there" for a mistyped root.
        raise BridgeError(f"{root} could not be opened safely as the workspace root ({exc})") from exc
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
            if create:
                try:
                    os.mkdir(part, 0o777, dir_fd=fd)
                except FileExistsError:
                    pass
            try:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError as exc:
                # ENOENT alone means "nothing is there". A symlink or a file where a directory should
                # be is still a refusal below — ENOTDIR on macOS, ELOOP for a symlink on Linux.
                raise AbsentPath(
                    f"{root}/{'/'.join(relative)}: {part} does not exist") from exc
            os.close(fd)
            fd = nxt
    except AbsentPath:
        os.close(fd)
        raise
    except OSError as exc:
        os.close(fd)
        raise BridgeError(f"{root}/{'/'.join(relative)} could not be opened safely ({exc})") from exc
    except BaseException:
        os.close(fd)
        raise
    return fd


def open_dir_chain(root, relative, create=False):
    """Public name for the component-wise `O_NOFOLLOW` descent.

    `bridge_cli` carried its own copy of this, which is the pattern this module exists to end: a
    second implementation of a safety rule drifts from the first, and the copy had none of the
    refusals added here since. One descent, one place. `create` as in `_open_dir_chain`.
    """
    return _open_dir_chain(root, relative, create=create)


def unlink_at(root, rel):
    """Remove a workspace-relative entry, never following a symlink in its path.

    Deleting by path re-resolves every component at call time, so a symlink planted anywhere along it
    redirects the removal — which is how a teardown deletes a user's file. Resolving the parent once
    and unlinking relative to that descriptor removes the window.
    """
    import stat as _stat
    rel = Path(rel)
    assert_inside(root, Path(root) / rel)
    try:
        fd = _open_dir_chain(root, rel.parent.parts)
    except AbsentPath:
        return False   # a missing parent is a missing entry; nothing to remove, nothing created
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
    try:
        fd = _open_dir_chain(root, rel.parent.parts)
    except AbsentPath:
        return False   # nothing at `rel` because its parent is not there; the descent created nothing
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
    fd = _open_dir_chain(root, rel.parts, create=True)
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
    fd = _open_dir_chain(root, rel.parent.parts, create=True)
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
    fd = _open_dir_chain(root, rel.parent.parts, create=True)
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
    for _ in range(64):
        suffix = binascii.hexlify(os.urandom(6)).decode("ascii")
        candidate = f".{name}.{suffix}.vibe-tmp"
        try:
            return os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL | O_NOFOLLOW_FLAG,
                           mode, dir_fd=dir_fd), candidate
        except FileExistsError:
            continue
    # The residual refusal: every candidate name was taken. With 48 random bits that means the
    # directory is full of this suite's own leftovers, so the message names the remedy (vibe-178).
    raise BridgeError(
        f"could not create a scratch file for {name} after 64 attempts; remove stale "
        f".{name}.*.vibe-tmp files from that directory if no other vibe-suite process is running")


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
    fd = _open_dir_chain(root, rel.parts)   # create=False: a mode change creates nothing
    try:
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def lstat_at(root, rel):
    """`lstat` a workspace-relative path without resolving any component by path."""
    rel = Path(rel)
    try:
        fd = _open_dir_chain(root, rel.parent.parts)
    except AbsentPath:
        return None   # a missing parent is a missing entry; the descent created nothing
    try:
        return os.lstat(rel.name, dir_fd=fd)
    except FileNotFoundError:
        return None
    finally:
        os.close(fd)


def write_atomic(root, dest, content, mode=None):
    """Replace a file atomically, without ever resolving its parent path twice.

    The scratch file has an unpredictable `O_EXCL|O_NOFOLLOW` name (`_scratch`), so a scratch left
    behind by a hard crash is an orphan, never a poison pill for the next write, and concurrent
    writers of one destination each stage through their own file — the last `os.replace` wins.

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
    dir_fd = _open_dir_chain(root, relative, create=True)

    data = content if isinstance(content, bytes) else content.encode("utf-8")
    try:
        # The scratch name is unpredictable, never the fixed `.{name}.vibe-tmp` (vibe-178 / grill
        # H9). A fixed name is a path the user may own; and a scratch that outlives a hard crash
        # (SIGKILL, power loss — the cleanup below never runs) under a fixed name refused every
        # later write to the same destination until someone found and deleted a dot-file nothing
        # had told them about. Two writers of one destination collided the same way. `_scratch` is
        # the primitive `publish_new` already uses: `O_EXCL|O_NOFOLLOW`, random name, bounded
        # retries, created at `mode` from the start.
        try:
            fd, tmp_name = _scratch(dir_fd, dest.name, mode)
        except OSError as exc:
            # `_scratch` retries EEXIST and nothing else. Any other failure (EACCES, EROFS,
            # ENOSPC) keeps the primitive's contract: callers catch BridgeError, not OSError.
            raise BridgeError(f"{dest.parent}: a scratch file for {dest.name} could not be "
                              f"created safely ({exc})") from exc
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
