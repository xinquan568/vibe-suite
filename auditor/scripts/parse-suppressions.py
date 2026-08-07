#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Emit a suite's `rule_overrides` as JSONL, one object per override.

Reads YAML frontmatter from the config file named as argv[1] and prints
`{"rule_id": ..., "override": ...}` per line. No config, no frontmatter, or no overrides is a
silent success — an absent config means "no suppressions", which is the normal state.

WHY THIS PARSES YAML ITSELF. The reference implementation imports PyYAML and, when the import
fails, prints a note and exits 0 — silently disabling every suppression. PyYAML is NOT
installed here and this repository ships stdlib only, so that path would be the permanent one:
suppressions configured by a maintainer would be ignored, quietly, forever. A gate that
silently stops enforcing is the failure mode this whole unit exists to avoid, so the frontmatter
subset is parsed directly.

The subset is deliberately narrow — the block mapping that `rule_overrides` actually uses:

    rule_overrides:
      nl:R1: false                  # scalar: bool / int / float / string
      nl:R2:
        max_penalty: 5              # one level of nesting
        threshold: 0.8

TYPES ARE PRESERVED, not stringified. `false` must reach the consumer as a JSON boolean and
`max_penalty: 5` as a number inside an object; emitting `"false"` or `"{'max_penalty': 5}"`
would produce well-formed JSONL that every downstream comparison then gets wrong.

Malformed frontmatter FAILS rather than yielding nothing, so a broken config surfaces instead
of reading as "no suppressions configured".
"""
import json
import os
import re
import sys

FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)
#: `key: value` where the key may be namespaced (`nl:R1`) — so the split is on the LAST colon
#: that is followed by whitespace or end of line, not the first.
ENTRY = re.compile(r"^(?P<indent>[ ]*)(?P<key>\S(?:.*\S)?)[ ]*:(?:[ ]+(?P<value>.*?))?[ ]*$")


def scalar(text):
    """A YAML scalar in the subset: bool, null, int, float, or string."""
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1]
    low = t.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", ""):
        return None
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def parse_overrides(front):
    """The `rule_overrides` mapping from frontmatter text. Raises ValueError if malformed."""
    lines = [ln for ln in front.split("\n") if ln.strip() and not ln.lstrip().startswith("#")]
    out, in_block, block_indent, pending, pending_indent = {}, False, 0, None, None

    for raw in lines:
        m = ENTRY.match(raw)
        if not m:
            raise ValueError(f"unparsable frontmatter line: {raw.strip()[:60]!r}")
        indent, key, value = len(m.group("indent")), m.group("key"), m.group("value")

        if not in_block:
            if key == "rule_overrides" and not (value or "").strip():
                in_block, block_indent = True, indent
            continue

        if indent <= block_indent:            # dedented out of the block
            break
        if pending is not None and indent > pending_indent:
            out[pending][key] = scalar(value or "")
            continue
        pending = None
        if (value or "").strip() == "":
            out[key], pending, pending_indent = {}, key, indent
        else:
            out[key] = scalar(value)
    return out


def main():
    if len(sys.argv) < 2:
        return 0
    path = sys.argv[1]
    try:
        content = open(path, encoding="utf-8").read()
    except OSError as exc:
        # An absent config is "no suppressions"; one that exists but cannot be read is a fault.
        if os.path.exists(path):
            print(f"parse-suppressions: {path} unreadable: {exc}", file=sys.stderr)
            return 1
        return 0

    m = FRONTMATTER.match(content)
    if not m:
        return 0
    try:
        overrides = parse_overrides(m.group(1))
    except ValueError as exc:
        print(f"parse-suppressions: malformed frontmatter in {path}: {exc}", file=sys.stderr)
        return 1

    for rule, override in overrides.items():
        print(json.dumps({"rule_id": str(rule), "override": override}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
