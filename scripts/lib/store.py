#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The workspace runtime-toggle store (E0.5 / vibe-7).

`.vibe-suite.md` is human-edited project configuration; this is machine-managed runtime state,
resolved once per workspace. A user flipping a toggle must see it take effect without editing a
file, so the store wins for the session — but only over the three `gate.*` keys, and it never
writes project configuration.

**The on-disk layout is part of the contract**, not an implementation detail: settings live under a
top-level `config` member of `<workspace>/.vibe-suite-state/state.json`, an unset key is *absent*
rather than null, and a write preserves every sibling member of that file.

Job records are **not** members of this file. The codex-runner engine (E1.1) writes one file per job
at `<workspace>/.vibe-suite-state/jobs/<jobId>.json` — beside this store in the same state directory,
never inside it — so a toggle write and a job write cannot contend for the same file.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge  # noqa: E402

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


class StoreFormatError(Exception):
    """The state file exists but is not readable as the expected shape."""


def state_path(workspace):
    """The one state file for a workspace."""
    return Path(workspace) / STATE_DIRNAME / STATE_FILENAME


def _read(path):
    """Load the state file, refusing to proceed over damage.

    Swallowing a JSONDecodeError and returning `{}` looks defensive and is destructive: the next
    write would serialize that empty object over a file whose job records are still there but
    unparsed. A state file we cannot read is a state file we must not overwrite.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StoreFormatError(f"{path}: not valid JSON — refusing to overwrite") from error
    if not isinstance(raw, dict):
        raise StoreFormatError(f"{path}: expected a JSON object at the top level")
    config = raw.get("config", {})
    if not isinstance(config, dict):
        raise StoreFormatError(f"{path}: 'config' must be an object")
    return raw


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
        config = raw.setdefault("config", {})
        if not isinstance(config.setdefault(section, {}), dict):
            raise StoreFormatError(f"config.{section}: expected an object")
        config[section][leaf] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Through the audited primitive, not a hand-rolled tmp-and-rename. That version wrote a
        # **fixed** scratch name — `state.json.tmp`, a path the user may own — replaced a symlinked
        # `state.json` without noticing, and published an existing `0600` file at the default mode.
        #
        # State records can hold private content, so a *fresh* one is created `0600`; an existing
        # one keeps whatever mode the user gave it.
        fresh_mode = None if self.path.is_file() else 0o600
        # The workspace is the root, not the file's own parent. Anchoring on the parent lets a
        # symlinked `.vibe-suite-state` *be* the trusted root, so `assert_inside` can no longer
        # catch a write that escapes the workspace.
        bridge.write_atomic(self.workspace, self.path,
                            json.dumps(raw, indent=2, sort_keys=True) + "\n", mode=fresh_mode)

    def overrides(self):
        """The shadowed values actually stored, validated on the way out.

        A file edited by hand can hold keys `set()` would have rejected. Validating only on write
        would let those reach `effective_config()` unchecked, so the same rules apply on read.
        """
        stored = _read(self.path).get("config", {})
        for section, values in stored.items():
            if not isinstance(values, dict):
                raise StoreFormatError(f"config.{section}: expected an object")
            for leaf, value in values.items():
                _validate(f"{section}.{leaf}", value)
        return stored


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


def _cli(argv):
    """Read-only CLI so non-Python consumers reach the ONE resolver (E1.6 / vibe-16).

    `effective-config <workspace>` prints the resolved configuration as one JSON object. There is
    deliberately **no write subcommand**: runtime writes belong to `/vibe-suite:config` (E1.8), and
    a hook that could flip its own toggle would be a gate that disables itself. Exits: 0 success,
    1 a state file too damaged to read (never a silent `{}` — see `_read`), 2 usage.
    """
    if len(argv) != 2 or argv[0] != "effective-config":
        print("usage: store.py effective-config <workspace>", file=sys.stderr)
        return 2
    try:
        print(json.dumps(effective_config(argv[1]), indent=2, sort_keys=True))
    except (StoreFormatError, StoreKeyError, StoreValueError) as error:
        print(f"store: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
