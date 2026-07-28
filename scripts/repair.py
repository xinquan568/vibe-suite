#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Non-interactive bridge repair for `/vibe-suite:repair` (E2.3 / vibe-20, F1.3).

**No prompts, ever.** F1.3 forbids them, and repair is what runs when nobody is there to answer. A
§7A row needing a fresh decision is *reported*, not guessed — §7A forbids deciding silently.

**Per-step isolation, because idempotent is not resumable.** `init_bridge.install()` is idempotent
but fail-fast: an invalid config raises before memory and registrations are reached. F1.3 requires
collect-failures-and-continue with a per-step outcome, so each step runs in its own guard and one
failure cannot hide the rest.

**No `--strictness`.** `init.sh` needs the band; the band's only job was computing `score_threshold`,
which is what `.vibe-suite.md` actually stores. A stored 75 has no inverse to a band, so repair reads
the threshold and never reconstructs the question.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402
import config as config_mod  # noqa: E402
import init_bridge  # noqa: E402

STEPS = ("config", "memory", "codex", "mcp", "gitignore", "history")


def installed(ws):
    """Repair restores a bridge; it does not create one. Installing into a project nobody set up
    would make it a silent, answer-less `init`."""
    return (bool(bridge.inventory_enumerate(ws))
            or (ws / config_mod.CONFIG_FILENAME).is_file()
            or (ws / init_bridge.PROVENANCE).is_file())


def settings(ws):
    """Everything the bridge steps need, read from the config rather than asked for."""
    try:
        loaded = config_mod.load(str(ws))
    except Exception as exc:
        raise bridge.BridgeError(f"{config_mod.CONFIG_FILENAME} is invalid: {exc}") from exc
    return {"effort": loaded.get("effort") or "medium",
            "sandbox": loaded.get("sandbox") or "read-only",
            "depth": loaded.get("audit_depth") or "mini",
            "threshold": loaded.get("score_threshold"),
            "skip": loaded.get("skip_patterns") or []}


def repair(ws):
    ws = Path(ws).resolve()
    steps, values = [], None

    def record(name, outcome):
        steps.append({"step": name, "outcome": outcome})

    for name in STEPS:
        try:
            if name == "config":
                values = settings(ws)
                record(name, "ok")
                continue
            if values is None:
                # The config could not be read, so the steps that need its values cannot run — but
                # the ones that do not still must, which is the whole point of continuing.
                if name in ("memory", "history"):
                    record(name, "skipped: configuration is unreadable")
                    continue
                values = {"effort": "medium", "sandbox": "read-only", "depth": "mini",
                          "threshold": None, "skip": []}
            init_bridge.repair_step(ws, name, values)
            record(name, "ok")
        except Exception as exc:
            record(name, f"failed: {exc}")

    return {"steps": steps,
            "ok": all(s["outcome"] == "ok" or s["outcome"].startswith("skipped") for s in steps)}


def render(report):
    lines = ["# vibe-suite repair", "", "| Step | Outcome |", "|---|---|"]
    lines += [f"| {s['step']} | {s['outcome']} |" for s in report["steps"]]
    if not report["ok"]:
        lines += ["", "Some steps did not complete. Run `/vibe-suite:doctor` for the current state."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="non-interactive vibe-suite bridge repair")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ws = Path(args.workspace).resolve()

    if not installed(ws):
        print("error: vibe-suite is not installed here; run /vibe-suite:init "
              "(repair restores a bridge, it does not create one)", file=sys.stderr)
        return 2

    report = repair(ws)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
