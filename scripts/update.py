#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""`/vibe-suite:update` — post-plugin-update refresh (E2.6 / vibe-23, F1.7).

Run after the plugin itself is upgraded: re-render the bridges, warm the npx cache, refresh the
pinned reverse-MCP registration, and prove the pin actually boots.

**Order is a correctness property, not a preference.**

    resolve pin -> bridges + mirrors -> pre-warm -> registration -> boot-verify

The pin resolves *first* because pre-warm has nothing to warm without it. Bridges and mirrors run
**even in the pending state** — the plugin ships with the pending marker for the whole of S2, so
stopping early there would make this command inert exactly when it is the only thing that refreshes
a stale bridge. Only the pin-dependent stages are skipped.

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

import bridge          # noqa: E402
import mcp_pin         # noqa: E402
import retired_names   # noqa: E402

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


def _prewarm(target, env, timeout):
    """`npx -y <pin> --version` under its own bound. A cold cache is not a broken package, so this
    is a warning at worst — the handshake that follows is the real verdict."""
    binary = env.get("VIBE_SUITE_MCP_BIN", "npx")
    try:
        proc = subprocess.run([binary, "-y", target, "--version"],
                              capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return WARN, f"pre-warm timed out after {timeout}s; the probe will decide"
    except OSError as exc:
        return WARN, f"pre-warm could not run {binary}: {exc}"
    if proc.returncode != 0:
        return WARN, f"pre-warm exited {proc.returncode}; the probe will decide"
    return OK, f"npx cache warmed for {target}"


def _probe(target, env, timeout):
    try:
        proc = subprocess.run(["node", str(PROBE), target],
                              capture_output=True, text=True, timeout=timeout + 10, env=env)
    except subprocess.TimeoutExpired:
        return FAIL, f"boot probe did not return within {timeout + 10}s"
    except OSError as exc:
        return FAIL, f"boot probe could not run: {exc}"
    line = (proc.stdout or proc.stderr or "").strip().splitlines()
    detail = line[0] if line else "no output"
    return (OK, detail) if proc.returncode == 0 else (FAIL, detail)


def run(workspace, plugin_root, env=None, probe_timeout=30):
    env = dict(os.environ if env is None else env)
    ws = Path(workspace).resolve()
    report = Report()

    # ---- resolve the pin first; pre-warm cannot build a target without it ----------------------
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

    # Advisors reconcile in every pin state (E6.1) — removal and consistency need no backend, and
    # the engine resolves one lazily only when a new registration must be written.
    try:
        import advisors
        rep = advisors.reconcile(ws)
        detail = "; ".join(f"{k}: {v}" for k, v in sorted(rep.items())) or "no advisors"
        report.add("advisors", OK, detail)
    except Exception as exc:
        report.add("advisors", FAIL, str(exc))

    if not pin:
        return report

    target = mcp_pin.target(pin)
    report.add("prewarm", *_prewarm(target, env, timeout=probe_timeout))

    # ---- registration --------------------------------------------------------------------------
    # Re-read. `existing` was a pre-flight snapshot taken before the collision check, and the bridge
    # stage writes to this same file — planning from the stale copy would silently discard the mirror
    # block that had just been rendered.
    current = bridge.read_text_verbatim(toml_path) if toml_path.is_file() else ""
    try:
        action, updated = mcp_pin.plan(current, pin)
        if action != "current":  # `current` means the fence already holds this exact body
            toml_path.parent.mkdir(parents=True, exist_ok=True)
            bridge.write_atomic(ws, toml_path, updated)
        report.add("registration", OK, f"[mcp_servers.{mcp_pin.SERVER_NAME}] {action} ({target})")
    except (mcp_pin.PinError, bridge.BridgeError) as exc:
        report.add("registration", FAIL, str(exc))
        return report

    report.add("probe", *_probe(target, env, timeout=probe_timeout))
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
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run(args.workspace, args.plugin_root, probe_timeout=args.probe_timeout)
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
