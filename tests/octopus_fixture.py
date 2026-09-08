#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Shared fixtures for the lockfile-verified `claude-octopus` install (S13 / vibe-214).

Every module that renders a registration needs an *installed, verified* backend to render against;
these helpers build one on disk without `npm`, `npx` or the network:

* `fixture_install()` writes the shipped-file pair (`package.json`, `package-lock.json`) for one
  lockfile version and, per requested version, one **generation** under
  `versions/<v>/<generation>/` with its marker and (by default) its `.verified` mark.
* `add_generation()` adds further generations with a chosen marker sha and a distinguishable
  `dist/index.js` payload, so a test can tell *which* bytes a launch path resolves to.
* `legacy_entry()` / `legacy_body()` / `legacy_server_body()` reproduce today's `npx -y` shapes for
  seeding pre-existing registrations literally.
* `write_fake_npm()` / `write_fake_server()` are the two process seams (`VIBE_SUITE_NPM_BIN`,
  `VIBE_SUITE_MCP_BIN`); both record what they were asked to do to a sidecar file.
"""

import hashlib
import json
import os
import textwrap
from pathlib import Path

PACKAGE = "claude-octopus"
FIXTURE_INTEGRITY = "sha512-" + "A" * 86 + "=="


def lockfile_text(version, integrity=FIXTURE_INTEGRITY, lockfile_version=3, drop_integrity=False,
                  root_dependency=None, entry_version=None):
    """A minimal lockfile v3 for one exact dependency. The knobs exist for the refusal tests."""
    entry = {"version": entry_version or version,
             "resolved": f"https://registry.npmjs.org/{PACKAGE}/-/{PACKAGE}-{version}.tgz",
             "license": "MIT", "bin": {PACKAGE: "dist/index.js"}}
    if not drop_integrity:
        entry["integrity"] = integrity
    doc = {"name": "vibe-suite-claude-octopus-install", "lockfileVersion": lockfile_version,
           "requires": True,
           "packages": {"": {"name": "vibe-suite-claude-octopus-install", "license": "ISC",
                             "dependencies": {PACKAGE: root_dependency or version}},
                        f"node_modules/{PACKAGE}": entry}}
    return json.dumps(doc, indent=2) + "\n"


def manifest_text(version):
    return json.dumps({"name": "vibe-suite-claude-octopus-install", "private": True,
                       "license": "ISC", "dependencies": {PACKAGE: version}}, indent=2) + "\n"


def lockfile_sha256(install_dir):
    return hashlib.sha256((Path(install_dir) / "package-lock.json").read_bytes()).hexdigest()


def fixture_install(install_dir, versions=(), lock_version="1.2.0", verified=True, payload="fixture"):
    """Shipped files for `lock_version`; one generation per entry of `versions` (verified by default)."""
    install_dir = Path(install_dir)
    install_dir.mkdir(parents=True, exist_ok=True)
    (install_dir / "package.json").write_text(manifest_text(lock_version), encoding="utf-8")
    (install_dir / "package-lock.json").write_text(lockfile_text(lock_version), encoding="utf-8")
    for v in versions:
        add_generation(install_dir, v, payload=payload, verified=verified)
    return install_dir


def add_generation(install_dir, version, sha=None, payload="fixture", verified=False, name=None,
                   installed_at="20260908T000000Z", pid=None, metadata_version=None, with_bin=True,
                   with_marker=True):
    """One immutable generation. Returns its name. `metadata_version`/`with_bin`/`with_marker` build
    deliberately *invalid* generations for the reuse-predicate tests."""
    install_dir = Path(install_dir)
    sha = sha or lockfile_sha256(install_dir)
    gen = name or f"{sha[:12]}-{installed_at}-{pid or os.getpid()}"
    pkg = install_dir / "versions" / version / gen / "node_modules" / PACKAGE
    (pkg / "dist").mkdir(parents=True, exist_ok=True)
    (pkg / "package.json").write_text(json.dumps(
        {"name": PACKAGE, "version": metadata_version or version, "bin": {PACKAGE: "dist/index.js"}},
        indent=2) + "\n", encoding="utf-8")
    if with_bin:
        (pkg / "dist" / "index.js").write_text(
            f"#!/usr/bin/env node\n// fixture payload: {payload}\nconsole.log({payload!r});\n",
            encoding="utf-8")
    if with_marker:
        (install_dir / "versions" / version / gen / ".vibe-suite-install.json").write_text(json.dumps(
            {"version": version, "lockfile_sha256": sha, "installed_at": installed_at,
             "generation": gen}, indent=2) + "\n", encoding="utf-8")
    if verified:
        mark_verified(install_dir, version, gen)
    return gen


def mark_verified(install_dir, version, gen, detail="fixture"):
    p = Path(install_dir) / "versions" / version / f"{gen}.verified"
    if not p.exists():
        p.write_text(json.dumps({"generation": gen, "verified_at": "2026-09-08T00:00:00Z",
                                 "probe_detail": detail}, indent=2) + "\n", encoding="utf-8")
    return p


def bin_path(install_dir, version, gen):
    return str(Path(install_dir) / "versions" / version / gen / "node_modules" / PACKAGE
               / "dist" / "index.js")


# ---- legacy (pre-S13) registration shapes -----------------------------------------------------

def legacy_entry(env, pin):
    return {"command": "npx", "args": ["-y", f"{PACKAGE}@{pin}"], "env": dict(env),
            "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}


def legacy_body(name, env, pin):
    lines = [f"[mcp_servers.{name}]", 'command = "npx"', f'args = ["-y", "{PACKAGE}@{pin}"]',
             "startup_timeout_sec = 60", "tool_timeout_sec = 900", f"[mcp_servers.{name}.env]"]
    for k, v in sorted(env.items()):
        lines.append(f"{k} = {json.dumps(str(v))}")
    return "\n".join(lines)


def legacy_server_body(pin):
    return "\n".join(("[mcp_servers.vibe-claude-mcp]", 'command = "npx"',
                      f'args = ["-y", "{PACKAGE}@{pin}"]', "startup_timeout_sec = 60",
                      "tool_timeout_sec = 900"))


# ---- process seams ------------------------------------------------------------------------------

def write_fake_npm(path, behaviour="ok"):
    """A stand-in for `npm`. Records argv and cwd to `FAKE_NPM_LOG` (one JSON line per call).

    `ok`                 materialises `node_modules/claude-octopus/{package.json,dist/index.js}` in its
                         cwd from the `package.json` dependency there; payload from `FAKE_NPM_PAYLOAD`;
                         omits the bin when `FAKE_NPM_NO_BIN=1`.
    `eintegrity`         the *same complete tree*, then exits 1 with `npm error code EINTEGRITY` — only
                         the exit status distinguishes it (mutation M1's isolation).
    `partial`            `package.json` only, exits 1 (the measured real EINTEGRITY leftover shape).
    `fail`               exits 1 writing nothing.
    `wrong-version`      a complete tree whose metadata says 9.9.9, exits 0.
    `ok-and-plant-winner` `ok`, plus a complete, valid, verified generation planted under
                         `<cwd>/../<version>/` before exiting — a concurrent installer that won.
    """
    path = Path(path)
    path.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import hashlib, json, os, sys
        from pathlib import Path
        behaviour = {behaviour!r}
        cwd = Path.cwd()
        log = os.environ.get("FAKE_NPM_LOG")
        if log:
            with open(log, "a") as fh:
                fh.write(json.dumps({{"argv": sys.argv[1:], "cwd": str(cwd)}}) + "\\n")
        if behaviour == "fail":
            print("npm error fixture failure", file=sys.stderr); sys.exit(1)
        version = json.loads((cwd / "package.json").read_text())["dependencies"]["claude-octopus"]
        payload = os.environ.get("FAKE_NPM_PAYLOAD", "fake-npm")
        def materialise(root, ver, with_bin=True):
            pkg = root / "node_modules" / "claude-octopus"
            (pkg / "dist").mkdir(parents=True, exist_ok=True)
            (pkg / "package.json").write_text(json.dumps(
                {{"name": "claude-octopus", "version": ver, "bin": {{"claude-octopus": "dist/index.js"}}}}) + "\\n")
            if with_bin:
                (pkg / "dist" / "index.js").write_text(
                    "#!/usr/bin/env node\\n// payload: " + payload + "\\nconsole.log(" + json.dumps(payload) + ");\\n")
        if behaviour == "partial":
            pkg = cwd / "node_modules" / "claude-octopus"; pkg.mkdir(parents=True, exist_ok=True)
            (pkg / "package.json").write_text(json.dumps({{"name": "claude-octopus", "version": version}}) + "\\n")
            print("npm error code EINTEGRITY", file=sys.stderr); sys.exit(1)
        if behaviour == "wrong-version":
            materialise(cwd, "9.9.9"); sys.exit(0)
        materialise(cwd, version, with_bin=os.environ.get("FAKE_NPM_NO_BIN") != "1")
        if behaviour == "eintegrity":
            print("npm error code EINTEGRITY", file=sys.stderr)
            print("npm error sha512-... integrity checksum failed", file=sys.stderr); sys.exit(1)
        if behaviour == "ok-and-plant-winner":
            sha = hashlib.sha256((cwd / "package-lock.json").read_bytes()).hexdigest()
            gen = sha[:12] + "-99991231T235959Z-99999"
            root = cwd.parent / version / gen
            materialise(root, version)
            (root / ".vibe-suite-install.json").write_text(json.dumps(
                {{"version": version, "lockfile_sha256": sha, "installed_at": "99991231T235959Z",
                  "generation": gen}}) + "\\n")
            (cwd.parent / version / (gen + ".verified")).write_text(json.dumps(
                {{"generation": gen, "verified_at": "9999-12-31T23:59:59Z", "probe_detail": "winner"}}) + "\\n")
        sys.exit(0)
        """), encoding="utf-8")
    path.chmod(0o755)
    return path


def write_fake_server(path, behaviour="respond"):
    """A stand-in for the launched backend. Speaks newline-delimited JSON-RPC so the probe has
    something real to hand-shake with. `hang` additionally spawns a descendant, so reaping the
    *group* is what the timeout test measures. The requested target is derived from `argv[-1]`:
    a `/versions/<v>/<gen>/…/dist/index.js` path (the S13 launch) or the legacy `<pkg>@<v>`."""
    path = Path(path)
    path.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import json, os, re, subprocess, sys, time
        behaviour = {behaviour!r}
        record = os.environ.get("FAKE_ARGV_LOG")
        if record:
            with open(record, "a") as fh:
                fh.write(json.dumps(sys.argv[1:]) + "\\n")
        if "--version" in sys.argv:
            print("1.0.0"); sys.exit(0)
        if behaviour == "exit":
            sys.exit(3)
        if behaviour == "hang":
            subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
            time.sleep(300); sys.exit(0)
        line = sys.stdin.readline()
        req = json.loads(line)
        last = sys.argv[-1] if len(sys.argv) > 1 else ""
        m = re.search(r"/versions/([^/]+)/[^/]+/node_modules/claude-octopus/dist/index\\.js$", last)
        if m:
            pkg, ver = "claude-octopus", m.group(1)
        else:
            pkg, _, ver = last.rpartition("@")
        info = {{"name": pkg, "version": ver}}
        if behaviour == "wrong-name":
            info["name"] = "impostor-octopus"
        if behaviour == "wrong-version":
            info["version"] = "9.9.9"
        if behaviour == "no-version":
            del info["version"]
        if behaviour == "bad-version":
            info["version"] = {{"major": 9}}
        if behaviour == "no-name":
            del info["name"]
        if behaviour == "bad-name":
            info["name"] = 7
        if behaviour == "error":
            out = {{"jsonrpc": "2.0", "id": req["id"], "error": {{"code": -1, "message": "nope"}}}}
        else:
            out = {{"jsonrpc": "2.0", "id": req["id"], "result": {{"serverInfo": info}}}}
        print(json.dumps(out), flush=True)
        time.sleep(30)
        """), encoding="utf-8")
    path.chmod(0o755)
    return path


def seam_env(install_dir, fake_npm, fake_server):
    return {"VIBE_SUITE_OCTOPUS_INSTALL_DIR": str(install_dir),
            "VIBE_SUITE_NPM_BIN": str(fake_npm),
            "VIBE_SUITE_MCP_BIN": str(fake_server)}


# ---- module-level seams (one install per test module) -------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE = {}


def shipped_pin():
    return (REPO_ROOT / "scripts" / "lib" / "claude-octopus-pin.txt").read_text(encoding="utf-8").strip()


def start_module_seams(key, versions=None, lock_version=None, server="respond", npm="ok"):
    """Create one fixture install (+ fake npm, fake server) and patch the process environment for
    the module's lifetime. Subprocesses inherit it through their `dict(os.environ, …)` copies;
    in-process renders read it directly. Returns the install dir. By default one verified
    generation of `lock_version` (the shipped pin) is installed — what `advisor_cli add` renders."""
    import shutil
    import tempfile
    from unittest import mock
    lock_version = lock_version or shipped_pin()
    if versions is None:
        versions = (lock_version,)
    tmp = Path(tempfile.mkdtemp(prefix=f"octopus-{key}-"))
    inst = fixture_install(tmp / "install", versions=versions, lock_version=lock_version)
    fake_npm = write_fake_npm(tmp / "fake-npm", npm)
    fake_server = write_fake_server(tmp / "fake-server", server)
    patcher = mock.patch.dict(os.environ, seam_env(inst, fake_npm, fake_server))
    patcher.start()
    _MODULE[key] = (tmp, patcher, inst, shutil)
    return inst


def stop_module_seams(key):
    tmp, patcher, _, shutil = _MODULE.pop(key)
    patcher.stop()
    shutil.rmtree(tmp, ignore_errors=True)


def generation_of(install_dir, version):
    """The (single) generation name a fixture created for `version`."""
    gens = sorted(p.name for p in (Path(install_dir) / "versions" / version).iterdir() if p.is_dir())
    assert len(gens) == 1, gens
    return gens[0]


def module_install(key):
    return _MODULE[key][2]
