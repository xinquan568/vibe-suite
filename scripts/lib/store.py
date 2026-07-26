#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The workspace runtime-toggle store (E0.5 / vibe-7).

`.vibe-suite.md` is human-edited project configuration; this is machine-managed runtime state,
resolved once per workspace. A user flipping a toggle must see it take effect without editing a
file, so the store wins for the session — but only over the three `gate.*` keys, and it never
writes project configuration.

**The on-disk layout is part of the contract**, not an implementation detail: settings live under a
top-level `config` member of `<workspace>/.vibe-suite-state/state.json`, an unset key is *absent*
rather than null, and a write preserves every sibling member so job records survive a toggle.
"""

import json
from pathlib import Path

STATE_DIRNAME = ".vibe-suite-state"
STATE_FILENAME = "state.json"

# Only these may be shadowed at runtime. Anything else belongs to the project file.
SHADOWABLE = {
    "gate.stop_review_gate": "bool",
    "gate.model": "string",
    "gate.fail_policy": "open|closed",
}
FRESH = {"gate.stop_review_gate": False, "gate.fail_policy": "open"}


class StoreKeyError(Exception):
    """A key outside the shadowable set."""


class StoreValueError(Exception):
    """A shadowable key with a value outside its domain."""


def state_path(workspace):
    """The one state file for a workspace."""
    return Path(workspace) / STATE_DIRNAME / STATE_FILENAME


def _read(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _validate(key, value):
    if key not in SHADOWABLE:
        raise StoreKeyError(f"{key}: not a runtime-shadowable setting")
    expected = SHADOWABLE[key]
    if expected == "bool" and not isinstance(value, bool):
        raise StoreValueError(f"{key}: expected true or false")
    if expected == "string" and not isinstance(value, str):
        raise StoreValueError(f"{key}: expected a string")
    if "|" in expected and value not in expected.split("|"):
        raise StoreValueError(f"{key}: expected one of {expected}")


class Store:
    """Runtime toggles for one workspace."""

    def __init__(self, workspace):
        self.workspace = Path(workspace)
        self.path = state_path(workspace)

    def get(self, key):
        if key not in SHADOWABLE:
            raise StoreKeyError(f"{key}: not a runtime-shadowable setting")
        section, _, leaf = key.partition(".")
        stored = _read(self.path).get("config", {}).get(section, {})
        if leaf in stored:
            return stored[leaf]
        return FRESH.get(key)          # absent, not null — see the module docstring

    def set(self, key, value):
        _validate(key, value)
        section, _, leaf = key.partition(".")
        raw = _read(self.path)         # read first, so sibling members survive
        raw.setdefault("config", {}).setdefault(section, {})[leaf] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def overrides(self):
        """The shadowed values actually stored, as a nested mapping."""
        return _read(self.path).get("config", {})


def effective_config(workspace):
    """Project configuration with runtime state layered over it.

    The store never writes `.vibe-suite.md`; the merge happens here, in memory, so a live toggle
    leaves the project file byte-identical.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "vibe_config", Path(__file__).resolve().parent / "config.py")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    resolved = config.load(workspace)
    gate = dict(resolved.get("gate") or {})
    for leaf, value in Store(workspace).overrides().get("gate", {}).items():
        gate[leaf] = value
    for key, value in FRESH.items():
        gate.setdefault(key.partition(".")[2], value)
    resolved["gate"] = gate
    return resolved
