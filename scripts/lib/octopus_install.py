#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The lockfile-verified `claude-octopus` install (S13 / vibe-214).

`/vibe-suite:update` used to launch the reverse-MCP server as `npx -y claude-octopus@<pin>`: a
version pin, but no integrity — `npx` resolved 108 packages at launch time from whatever the
registry or its cache served. This module replaces that with an install the suite performs itself
from a **shipped lockfile** (`package.json` + `package-lock.json` beside this file's
`claude-octopus/` directory), so `npm ci --ignore-scripts` verifies every package's recorded
`integrity` once, and every later launch executes the verified bytes by `node <installed bin>`.

**Who proves what.** The lockfile plus a successful `npm ci` verify bytes, at install time. A
generation directory is *valid* when its marker names the shipped lockfile's sha256, its metadata
version equals the directory's version and the bin exists — the installer's reuse predicate. It is
*verified* when, in addition, its `.verified` mark exists; `update` writes that mark only after the
boot probe passed. Every render outside `update` requires a verified generation. Neither predicate
re-checks file contents: the local install is trusted the way the plugin's own files are.

**Generations are immutable.** Each install builds a fresh staging tree, binds the marker into it,
and publishes it with one atomic rename to a unique name — `versions/<v>/<sha12>-<utc>-<pid>/`.
Nothing is ever retired, replaced or deleted except this run's own staging directory on failure, so
a failing install cannot touch a backend some registration still launches, and two installers on one
machine publish two generations. Older generations are listed for manual cleanup.

Every mutation goes through `bridge`'s audited primitives (`ensure_dir_at`, `write_atomic`,
`rename_at`, `remove_tree_at`, `publish_new`); the containment root is the install directory and
`assert_root`/`pin_root` run before the first operation, so a symlinked root or `versions/` is refused.
`npm` itself writes only inside the staging directory (its cwd).
"""

import datetime
import hashlib
import json
import os
import secrets
import subprocess
from pathlib import Path
import fsafe
import mcp_pin

OK, FAIL = "ok", "fail"
PACKAGE = mcp_pin.PACKAGE
MARKER = ".vibe-suite-install.json"
STAGING_PREFIX = ".staging-"
NPM_ARGS = ["ci", "--ignore-scripts", "--no-audit", "--no-fund"]
NPM_BIN_ENV = "VIBE_SUITE_NPM_BIN"


def install_dir(env=None):
    return mcp_pin.install_dir(env)


def _env(env):
    return os.environ if env is None else env


def lockfile_sha256(env=None):
    return hashlib.sha256((install_dir(env) / "package-lock.json").read_bytes()).hexdigest()


def lockfile_check(pin, env=None):
    """Offline: the shipped pair describes exactly `pin`. Returns an error string, or None."""
    root = install_dir(env)
    manifest_p, lock_p = root / "package.json", root / "package-lock.json"
    if not manifest_p.is_file() or not lock_p.is_file():
        return f"shipped package.json/package-lock.json missing under {root}"
    manifest, lock = _json_object(manifest_p), _json_object(lock_p)
    if manifest is None or lock is None:
        return "shipped lockfile pair unreadable or not JSON objects"
    deps = manifest.get("dependencies")
    if not isinstance(deps, dict) or deps.get(PACKAGE) != pin:
        found = deps.get(PACKAGE) if isinstance(deps, dict) else None
        return f"package.json pins {PACKAGE}@{found!r}, the pin file says {pin}"
    if lock.get("lockfileVersion") != 3:
        return f"package-lock.json lockfileVersion is {lock.get('lockfileVersion')!r}, expected 3"
    packages = lock.get("packages")
    if not isinstance(packages, dict) or not isinstance(packages.get(""), dict):
        return "package-lock.json has no packages map with a root entry"
    root_deps = packages[""].get("dependencies")
    if not isinstance(root_deps, dict) or root_deps.get(PACKAGE) != pin:
        found = root_deps.get(PACKAGE) if isinstance(root_deps, dict) else None
        return f"package-lock.json root dependency {PACKAGE} is {found!r}, expected {pin}"
    entry = packages.get(f"node_modules/{PACKAGE}")
    if not isinstance(entry, dict) or entry.get("version") != pin:
        return f"package-lock.json entry for {PACKAGE} is at {entry.get('version') if isinstance(entry, dict) else None!r}, expected {pin}"
    if not str(entry.get("integrity", "")).startswith("sha512-"):
        return f"package-lock.json entry for {PACKAGE} has no sha512 integrity"
    missing = sorted(k for k, v in packages.items() if k and not (isinstance(v, dict) and v.get("integrity")))
    if missing:
        return f"package-lock.json entries without integrity: {', '.join(missing[:3])}{'…' if len(missing) > 3 else ''}"
    return None


# ---- generations -------------------------------------------------------------------------------

def _versions_root(env=None):
    return install_dir(env) / "versions"


def _json_object(path):
    """A JSON object from `path`, or None when the file is unreadable, not JSON, or not an object —
    every reader below treats None as "not a generation", never as an exception."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _audited_dir(root, parts):
    """Walk `root/parts` through bridge's `O_NOFOLLOW` descent: `"ok"` for a real directory chain,
    `"absent"` when a component does not exist, `"refused"` when a component is a symlink, a file,
    or otherwise not safely openable. Pathlib readers follow symlinks; this is what keeps a
    symlinked `versions/` (or generation) from being reused, rendered or probed."""
    try:
        fd = fsafe.open_dir_chain(root, tuple(parts))
    except fsafe.AbsentPath:
        return "absent"
    except (fsafe.BridgeError, OSError):
        return "refused"
    os.close(fd)
    return "ok"


def _generation_names(version, env=None):
    d = _versions_root(env) / version
    try:
        if not d.is_dir():
            return []
        return sorted(p.name for p in d.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []


def _read_marker(version, gen, env=None):
    return _json_object(_versions_root(env) / version / gen / MARKER)


def bin_of(version, gen, env=None):
    return str(_versions_root(env) / version / gen / "node_modules" / PACKAGE / "dist" / "index.js")


def _metadata_version(version, gen, env=None):
    meta = _json_object(_versions_root(env) / version / gen / "node_modules" / PACKAGE / "package.json")
    return meta.get("version") if meta else None


def is_valid_generation(version, gen, env=None, sha=None):
    """Marker naming the shipped lockfile's sha + metadata version == directory version + bin."""
    if not gen or "/" in gen or gen.startswith("."):
        return False
    root = install_dir(env)
    if _audited_dir(root, ("versions", version, gen)) != "ok":
        return False
    marker = _read_marker(version, gen, env)
    if not isinstance(marker, dict):
        return False
    try:
        sha = sha or lockfile_sha256(env)
    except OSError:
        return False
    if marker.get("version") != version or marker.get("lockfile_sha256") != sha or marker.get("generation") != gen:
        return False
    if _metadata_version(version, gen, env) != version:
        return False
    try:
        return Path(bin_of(version, gen, env)).is_file()
    except OSError:
        return False


def is_verified(version, gen, env=None):
    return (_versions_root(env) / version / f"{gen}.verified").is_file()


def _selectable(version, env):
    """The (root, sha) a selector needs, or None when the install directory cannot be read safely
    (a symlinked root, a missing lockfile). A symlinked `versions/` or `versions/<v>` needs no check
    here: `is_valid_generation` walks every candidate through the audited `O_NOFOLLOW` descent and
    refuses it there (mutation M20b showed a second check here to be unreachable)."""
    root = install_dir(env)
    try:
        fsafe.assert_root(root)
        sha = lockfile_sha256(env)
    except (fsafe.BridgeError, OSError):
        return None
    return root, sha


def current_valid_generation(version, env=None):
    """The installer's reuse predicate: the last valid generation by name, or None."""
    selectable = _selectable(version, env)
    if selectable is None:
        return None
    _, sha = selectable
    for gen in reversed(_generation_names(version, env)):
        if is_valid_generation(version, gen, env, sha=sha):
            return gen
    return None


def current_verified_generation(version, env=None):
    """The render predicate for every standalone path: the last valid AND verified generation."""
    selectable = _selectable(version, env)
    if selectable is None:
        return None
    _, sha = selectable
    for gen in reversed(_generation_names(version, env)):
        try:
            verified = is_verified(version, gen, env)
        except OSError:
            verified = False
        if verified and is_valid_generation(version, gen, env, sha=sha):
            return gen
    return None


def mark_verified(version, gen, env=None, detail=""):
    """`publish_new`: create the mark, or report it already exists. Never overwrites, never touches
    the generation tree. Returns True when this call created it."""
    root = install_dir(env)
    fsafe.assert_root(root)
    dest = root / "versions" / version / f"{gen}.verified"
    payload = json.dumps({"generation": gen, "version": version,
                          "verified_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          "probe_detail": detail}, indent=2) + "\n"
    return fsafe.publish_new(root, dest, payload)


def retained_generations(version, env=None):
    """Read-only listing of every generation under `versions/` (all versions) and foreign staging
    directories, for the install row's detail and manual cleanup."""
    out = []
    root = _versions_root(env)
    if not root.is_dir():
        return out
    try:
        sha = lockfile_sha256(env)
    except OSError:
        sha = None
    for p in sorted(root.iterdir()):
        if p.name.startswith(STAGING_PREFIX) or p.name.startswith(".retired-"):
            out.append({"version": None, "generation": p.name, "kind": "staging"})
        elif p.is_dir():
            for gen in _generation_names(p.name, env):
                out.append({"version": p.name, "generation": gen, "kind": "generation",
                            "valid": bool(sha) and is_valid_generation(p.name, gen, env, sha=sha),
                            "verified": is_verified(p.name, gen, env)})
    return out


def _retained_summary(version, current, env=None):
    rows = retained_generations(version, env)
    others = [f"{r['version']}/{r['generation']}" for r in rows if r["kind"] == "generation"
              and not (r["version"] == version and r["generation"] == current)]
    staging = [r["generation"] for r in rows if r["kind"] == "staging"]
    parts = []
    if others:
        parts.append("retained: " + ", ".join(others))
    if staging:
        parts.append("foreign staging (remove by hand): " + ", ".join(staging))
    return ("; " + "; ".join(parts)) if parts else ""


# ---- the install -------------------------------------------------------------------------------

def _cleanup(root, rel):
    try:
        fsafe.remove_tree_at(root, rel)
    except (fsafe.BridgeError, OSError) as exc:
        return f"; cleanup of {rel} failed: {exc}"
    return ""


def _first_line(text):
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def ensure_installed(pin, env=None, timeout=600):
    """`(status, detail, generation | None)`. Reuses a valid generation, else builds a new one.

    Order: root refusal → offline lockfile↔pin check → reuse → stage (`npm ci --ignore-scripts` in a
    fresh staging dir) → gate (rc 0, metadata == pin, bin present) → bind the marker into the staged
    tree → one atomic rename to a unique generation name. A failure removes only this run's staging.

    Every filesystem failure anywhere in that sequence is a `FAIL` row, never an exception: the outer
    boundary below catches `OSError` and still removes this run's staging directory if one was made.
    """
    env = _env(env)
    root = install_dir(env)
    staging = [None]
    try:
        return _install(pin, env, timeout, root, staging)
    except OSError as exc:
        cleanup = _cleanup(root, staging[0]) if staging[0] is not None else ""
        return FAIL, f"install failed: {exc}" + cleanup, None


def _install(pin, env, timeout, root, staging):
    try:
        fsafe.assert_root(root)
    except fsafe.BridgeError as exc:
        return FAIL, f"install directory refused: {exc}", None
    if not root.is_dir():
        return FAIL, f"install directory {root} does not exist", None
    try:
        fsafe.pin_root(root)          # identity before ANY read through the tree
    except OSError as exc:
        return FAIL, f"install directory refused: {exc}", None
    err = lockfile_check(pin, env)
    if err:
        return FAIL, f"lockfile refused before install: {err}", None
    try:
        sha = lockfile_sha256(env)
    except OSError as exc:
        return FAIL, f"lockfile unreadable: {exc}", None
    # `versions/` and `versions/<pin>` must be real directories (or absent) BEFORE anything is reused:
    # pathlib readers follow symlinks; the audited descent does not.
    for parts in (("versions",), ("versions", pin)):
        if _audited_dir(root, parts) == "refused":
            return FAIL, f"install directory refused: {'/'.join(parts)} is not a real directory", None
    current = current_valid_generation(pin, env)
    if current:
        return OK, (f"already installed (generation {current}, lockfile {sha[:12]})"
                    + _retained_summary(pin, current, env)), current

    staging_rel = Path("versions") / f"{STAGING_PREFIX}{os.getpid()}-{secrets.token_hex(4)}"
    staging[0] = staging_rel
    try:
        fsafe.ensure_dir_at(root, staging_rel)
        fsafe.write_atomic(root, root / staging_rel / "package.json", (root / "package.json").read_bytes())
        fsafe.write_atomic(root, root / staging_rel / "package-lock.json", (root / "package-lock.json").read_bytes())
    except (fsafe.BridgeError, OSError) as exc:
        return FAIL, f"could not stage the install: {exc}" + _cleanup(root, staging_rel), None

    npm = env.get(NPM_BIN_ENV, "npm")
    try:
        proc = subprocess.run([npm, *NPM_ARGS], cwd=str(root / staging_rel), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeout, env=dict(env))
    except subprocess.TimeoutExpired:
        return FAIL, f"npm ci did not finish within {timeout}s" + _cleanup(root, staging_rel), None
    except OSError as exc:
        return FAIL, f"npm ci could not run ({npm}): {exc}" + _cleanup(root, staging_rel), None

    staged_pkg = root / staging_rel / "node_modules" / PACKAGE
    problem = None
    if proc.returncode != 0:
        problem = f"npm ci exited {proc.returncode}: {_first_line(proc.stderr) or _first_line(proc.stdout) or 'no output'}"
    else:
        staged_meta = _json_object(staged_pkg / "package.json")
        meta = staged_meta.get("version") if staged_meta else None
        if meta != pin:
            problem = f"installed metadata says {meta!r}, expected {pin}"
        elif not (staged_pkg / "dist" / "index.js").is_file():
            problem = f"installed package has no node_modules/{PACKAGE}/dist/index.js"
    if problem:
        return FAIL, problem + _cleanup(root, staging_rel), None

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    gen = f"{sha[:12]}-{stamp}-{os.getpid()}"
    marker = json.dumps({"version": pin, "lockfile_sha256": sha, "installed_at": stamp, "generation": gen},
                        indent=2) + "\n"
    dest_rel = Path("versions") / pin / gen
    try:
        fsafe.write_atomic(root, root / staging_rel / MARKER, marker)
        fsafe.ensure_dir_at(root, Path("versions") / pin)
        fsafe.rename_at(root, staging_rel, dest_rel)
    except (fsafe.BridgeError, OSError) as exc:
        return FAIL, f"could not publish generation {gen}: {exc}" + _cleanup(root, staging_rel), None
    return OK, f"installed generation {gen} (lockfile {sha[:12]})" + _retained_summary(pin, gen, env), gen
