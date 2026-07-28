#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""View and set suite configuration for `/vibe-suite:config` (E2.7 / vibe-24, F1.8).

Two stores, one view. `.vibe-suite.md` is the **user's file** and is read, never written; the three
runtime toggles live in the job-state store and are the only things `--set` touches — which is
exactly `store.SHADOWABLE`.

**Warnings are surfaced.** `config.load()` discards them; `load_with_warnings()` does not, and an
unknown-key warning is the single signal a user needs to fix their file.

**A fresh project is a complete answer**, not a failure: schema defaults plus the store's `FRESH`.
Three of those defaults are corrections to inherited defects, so they matter as defaults —
`stop_review_gate` ships **off** (D3), `fail_policy` defaults **open** (fixing cc-suite W3's blocked
session end), and **no `gate.model` ships at all** (P9 forbids a pinned default, not the capability).
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import config as config_mod  # noqa: E402
import store as store_mod  # noqa: E402

#: CLI vocabulary → the store's `bool` domain. F1.8 says `on|off`; `_validate` accepts only booleans,
#: so an untranslated word fails rather than setting anything.
WORDS = {"on": True, "true": True, "yes": True, "1": True,
         "off": False, "false": False, "no": False, "0": False}


def view(ws):
    resolved, warnings = config_mod.load_with_warnings(str(ws))
    gate = store_mod.effective_config(ws).get("gate", {})
    return {"config": resolved, "gate": gate, "warnings": list(warnings)}


def render(v):
    lines = ["# vibe-suite configuration", "", "## Project (`.vibe-suite.md`)", "",
             "| Key | Value |", "|---|---|"]
    lines += [f"| {k} | {json.dumps(val)} |" for k, val in sorted(v["config"].items())]
    lines += ["", "## Runtime toggles (`/vibe-suite:config --set`)", "",
              "| Key | Value |", "|---|---|"]
    for key in ("stop_review_gate", "model", "fail_policy"):
        shown = v["gate"].get(key)
        lines.append(f"| gate.{key} | {json.dumps(shown) if shown is not None else '(unset)'} |")
    if v["warnings"]:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in v["warnings"]]
    return "\n".join(lines) + "\n"


def apply_set(ws, assignment):
    if "=" not in assignment:
        raise ValueError(f"--set expects key=value, got '{assignment}'")
    key, _, raw = assignment.partition("=")
    key = key.strip()
    key = key if key.startswith("gate.") else f"gate.{key}"
    if key not in store_mod.SHADOWABLE:
        raise ValueError(
            f"'{key}' is not settable. `--set` writes the runtime toggles only "
            f"({', '.join(sorted(store_mod.SHADOWABLE))}); .vibe-suite.md is yours to edit.")
    value = raw.strip()
    if store_mod.SHADOWABLE[key] == "bool":
        if value.lower() not in WORDS:
            raise ValueError(f"{key} expects on|off (or true|false), got '{value}'")
        value = WORDS[value.lower()]
    store_mod.Store(ws).set(key, value)
    return key, value


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="/vibe-suite:config", description="view and set vibe-suite configuration")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--set", dest="assignment")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    ws = Path(args.workspace).resolve()

    try:
        if args.assignment:
            key, value = apply_set(ws, args.assignment)
            print(f"{key} = {json.dumps(value)}")
            return 0
        v = view(ws)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(v, indent=2, sort_keys=True) if args.json else render(v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
