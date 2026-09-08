#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""`/vibe-suite:update` — post-plugin-update refresh (E2.6 / vibe-23, F1.7; S13 / vibe-214).

Run after the plugin itself is upgraded: re-render the bridges, install the pinned reverse-MCP
server from the shipped lockfile, prove that install boots, and only then refresh every
registration that launches it.

**Order is a correctness property, not a preference.**

    resolve pin -> bridges + mirrors -> install -> boot-verify -> advisors -> registration

* The pin resolves *first*; bridges and mirrors run **even in the pending state** (the plugin shipped
  with the pending marker for the whole of S2), and so do the advisors — removals and consistency
  need no backend.
* `install` (`octopus_install.ensure_installed`) runs `npm ci --ignore-scripts` from the shipped
  `package-lock.json` into an immutable, uniquely named generation directory — or reuses a valid one.
  `boot-verify` probes exactly that generation's `node <bin>`; on success it records the `.verified`
  mark every standalone render path requires. **Nothing pin-dependent is written before that**: a
  tampered lockfile (`EINTEGRITY`) or a failed probe ends the run with both stores byte-identical,
  and the advisors stage is reported as skipped rather than moved to an unverified backend.
* `advisors` runs before `registration` because `advisors.reconcile` begins by replaying its journal,
  which restores whole store images; the registration is planned on a re-read of the TOML after it.
* One generation is selected per run (the value `install` returned) and threaded through the probe,
  the advisors and the registration — a generation another installer publishes mid-run is not
  consulted by this run's writes.

**Validation precedes mutation.** A reserved-name collision in `.codex/config.toml` is detected
before any stage writes, so a refusal really does leave the workspace untouched.

Stages report independently and a later failure does not roll back an earlier success — the
per-step isolation `repair.py` established. The exit status is the worst stage.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge            # noqa: E402
import mcp_pin           # noqa: E402
import octopus_install   # noqa: E402
import retired_names     # noqa: E402

PROBE = HERE / "lib" / "boot_probe.mjs"
BRIDGE_CLI = HERE / "bridge_cli.py"
TOML_REL = Path(".codex") / "config.toml"

OK, WARN, FAIL = "ok", "warn", "fail"
_RANK = {OK: 0, WARN: 1, FAIL: 2}


class Report:
    def __init__(self):
        self.stages = []

    def add(self, stage, status, detail):
        self.stages.append({"stage": stage, "status": status, "detail": detail})

    @property
    def status(self):
        return max((s["status"] for s in self.stages), key=lambda s: _RANK[s], default=OK)

    def exit_code(self):
        return 1 if self.status == FAIL else 0


def _probe(target, launch, env, timeout):
    """`node boot_probe.mjs <target> <command> [args…]` — the probe spawns exactly the launch the
    registration will carry (S13), never a fresh `npx` resolution."""
    command, args = launch
    try:
        proc = subprocess.run(["node", str(PROBE), target, command, *args],
                              capture_output=True, text=True, timeout=timeout + 10, env=env)
    except subprocess.TimeoutExpired:
        return FAIL, f"boot probe did not return within {timeout + 10}s"
    except OSError as exc:
        return FAIL, f"boot probe could not run: {exc}"
    line = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = line[0] if line else "no output"
    return (OK, detail) if proc.returncode == 0 else (FAIL, detail)


def _skipped(pin, stage):
    return (f"skipped — claude-octopus@{pin} is not boot-verified this run ({stage} failed); "
            "advisor removals and convergence run on the next successful update")


def _advisors_stage(report, ws, generation=None):
    # Advisors reconcile in every pin state (E6.1) — removal and consistency need no backend, and
    # the engine resolves one lazily only when a registered advisor's registration must be
    # rewritten. vibe-185: update registers nothing the operator has not added; a never-registered
    # or edited definition is held and reported. S13: with a pin, `generation` is the one this run
    # installed and probed — the renderers never re-select.
    try:
        import advisors
        rep = advisors.reconcile(ws, generation=generation)
        detail = "; ".join(f"{k}: {v}" for k, v in sorted(rep.items())) or "no advisors"
        report.add("advisors", OK, detail)
    except Exception as exc:
        report.add("advisors", FAIL, str(exc))


def run(workspace, plugin_root, env=None, probe_timeout=30, install_timeout=600):
    env = dict(os.environ if env is None else env)
    ws = Path(workspace).resolve()
    report = Report()

    # ---- resolve the pin first; nothing pin-dependent has a target without it -----------------
    try:
        state, pin = mcp_pin.resolve_pin(
            pin_file=Path(plugin_root) / "scripts" / "lib" / "claude-octopus-pin.txt",
            pending_file=Path(plugin_root) / "scripts" / "lib" / "claude-octopus-pin.pending")
    except mcp_pin.PinError as exc:
        report.add("pin", FAIL, str(exc))
        state, pin = None, None
    else:
        report.add("pin", OK,
                   "pinned reverse-MCP server not shipped yet (owner: E7.1); "
                   "bridges still refresh" if state == "pending" else f"pin resolves to {pin}")

    # ---- validate before mutating -------------------------------------------------------------
    toml_path = ws / TOML_REL
    existing = bridge.read_text_verbatim(toml_path) if toml_path.is_file() else ""
    if pin:
        conflict = mcp_pin.collision(existing)
        if conflict:
            report.add("registration", FAIL, conflict)
            report.add("preflight", FAIL, "refused before any stage wrote; workspace unchanged")
            return report

    # ---- bridges and mirrors: always, including the pending state ------------------------------
    try:
        proc = subprocess.run([sys.executable, str(BRIDGE_CLI), "all",
                               "--workspace", str(ws), "--plugin-root", str(plugin_root)],
                              capture_output=True, text=True, timeout=120, env=env)
        detail = (proc.stdout or "").strip().replace("\n", "; ") or "no output"
        report.add("bridges", OK if proc.returncode == 0 else FAIL, detail)
    except (subprocess.TimeoutExpired, OSError) as exc:
        report.add("bridges", FAIL, f"bridge refresh did not complete: {exc}")

    if not pin:
        # Pending state: advisors as ever (removals need no backend; a render that needs one is held
        # as backend-unavailable). No install, no probe, no registration.
        _advisors_stage(report, ws)
        return report

    # ---- install the pinned backend from the shipped lockfile -------------------------------------
    status, detail, generation = octopus_install.ensure_installed(pin, env=env, timeout=install_timeout)
    report.add("install", status, detail)
    if status != OK:
        report.add("advisors", WARN, _skipped(pin, "install"))
        return report

    # ---- boot-verify exactly that generation; record the mark only on success -------------------
    target = mcp_pin.target(pin)
    try:
        launch = mcp_pin.launch(target, env=env, generation=generation)
    except mcp_pin.PinError as exc:
        report.add("probe", FAIL, str(exc))
        report.add("advisors", WARN, _skipped(pin, "probe"))
        return report
    pstatus, pdetail = _probe(target, launch, env, timeout=probe_timeout)
    if pstatus == OK:
        try:
            octopus_install.mark_verified(pin, generation, env=env, detail=pdetail)
            pdetail = f"{pdetail}; verified generation {generation}"
        except (bridge.BridgeError, OSError) as exc:
            pstatus, pdetail = FAIL, f"{pdetail}; could not record the verification: {exc}"
    report.add("probe", pstatus, pdetail)
    if pstatus != OK:
        report.add("advisors", WARN, _skipped(pin, "probe"))
        return report

    # ---- advisors, then the registration (recovery replays whole images; write after it) --------
    _advisors_stage(report, ws, generation=generation)

    # Re-read. `existing` was a pre-flight snapshot taken before the collision check, and the bridge
    # and advisors stages write to this same file — planning from the stale copy would silently
    # discard what they rendered.
    current = bridge.read_text_verbatim(toml_path) if toml_path.is_file() else ""
    try:
        action, updated = mcp_pin.plan(current, pin, generation=generation, env=env)
        if action != "current":  # `current` means the fence already holds this exact body
            toml_path.parent.mkdir(parents=True, exist_ok=True)
            bridge.write_atomic(ws, toml_path, updated)
        report.add("registration", OK,
                   f"[mcp_servers.{mcp_pin.SERVER_NAME}] {action} ({target}, generation {generation})")
    except (mcp_pin.PinError, bridge.BridgeError) as exc:
        report.add("registration", FAIL, str(exc))
    return report


def render(report):
    glyph = {OK: "[GOOD]", WARN: "[LOW]", FAIL: "[HIGH]"}
    lines = ["| stage | status | detail |", "| --- | --- | --- |"]
    for s in report.stages:
        lines.append(f"| {s['stage']} | {glyph[s['status']]} | {s['detail']} |")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="/vibe-suite:update")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--plugin-root", default=os.environ.get("CLAUDE_PLUGIN_ROOT", str(HERE.parent)))
    parser.add_argument("--probe-timeout", type=int, default=30)
    parser.add_argument("--install-timeout", type=int, default=600)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run(args.workspace, args.plugin_root, probe_timeout=args.probe_timeout,
                 install_timeout=args.install_timeout)
    text = json.dumps({"status": report.status, "stages": report.stages}, indent=2) \
        if args.json else render(report)

    # The rule this command exists to enforce applies to this command. Checking our own output is
    # cheap, and a third-party string reaching stdout is exactly how W2 happened.
    leaked = retired_names.scan_text(text)
    if leaked:
        print(f"[HIGH] retired namespaces in this command's own output: {', '.join(leaked)}",
              file=sys.stderr)
        print(text)
        return 1
    print(text)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
