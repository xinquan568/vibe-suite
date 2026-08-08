#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Three-way merge the registry when a push races another workflow.

    three-way-merge-registry.py BASE OURS THEIRS   > merged.json

WHY NOT A RECURSIVE OVERLAY. The obvious resolution — deep-merge OURS over THEIRS, ours wins —
is wrong whenever this workflow's checkout is stale. For every field this run did NOT touch,
OURS still holds the value read at checkout time, so overlaying it REVERTS whatever landed on
the remote since. The observable symptom is an entry oscillating between states run after run:
audit sets `audited`, the next unrelated workflow's stale view puts it back to `discovered`,
and nothing in the pipeline looks broken while the registry quietly loses updates.

A three-way merge asks a different question — not "what does each side say" but "what did each
side CHANGE" — which is the only way to tell a deliberate update from a stale copy:

    ours changed, theirs didn't   -> ours     (we made this change)
    theirs changed, ours didn't   -> theirs   (remote did; our value is just stale)
    both changed                  -> ours     (this run's intent wins, deterministically)
    neither changed               -> identical anyway

Keys present on only one side are unioned in. Recursion happens whenever OURS and THEIRS are
both mappings, even if BASE is absent or a scalar — otherwise two sides that independently added
the same key with different sub-fields would fall to the scalar branch and one side's fields
would be dropped.

Merged output is validated before printing: a result without a `repos` map is refused so the
caller fails loudly instead of writing a registry that parses but means nothing. Keys are
emitted sorted so concurrent resolutions produce identical bytes rather than diff noise.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MISSING = object()


def merge_value(base, ours, theirs):
    """Merge one cell. See the module docstring for the rules."""
    if isinstance(ours, dict) and isinstance(theirs, dict):
        return merge_dict(base if isinstance(base, dict) else {}, ours, theirs)
    ours_changed = ours != base
    theirs_changed = theirs != base
    if theirs_changed and not ours_changed:
        return theirs          # remote moved, our copy is stale
    return ours                # we moved, or both did: this run's intent


def merge_dict(base, ours, theirs):
    merged = {}
    for key in sorted(set(base) | set(ours) | set(theirs)):
        b = base.get(key, MISSING)
        o = ours.get(key, MISSING)
        t = theirs.get(key, MISSING)

        if o is MISSING and t is MISSING:
            continue                                    # deleted on both sides
        if o is MISSING:
            # Absent from ours: added by remote, or deleted by us. A deletion is only
            # honoured when the value remote holds is the one we deleted.
            if b is MISSING or t != b:
                merged[key] = t
            continue
        if t is MISSING:
            if b is MISSING or o != b:
                merged[key] = o
            continue
        merged[key] = merge_value(None if b is MISSING else b, o, t)
    return merged


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 3:
        print("usage: three-way-merge-registry.py BASE OURS THEIRS", file=sys.stderr)
        return 2

    documents = []
    for name in argv:
        try:
            documents.append(json.loads(Path(name).read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"REFUSE:three-way-merge:unreadable-input {name}: {exc}", file=sys.stderr)
            return 3

    if not all(isinstance(d, dict) for d in documents):
        print("REFUSE:three-way-merge:inputs-must-be-objects", file=sys.stderr)
        return 4

    base, ours, theirs = documents
    merged = merge_dict(base, ours, theirs)

    # A merge that loses the repos map is not a registry. Refusing here means the caller's
    # conflict resolution fails loudly rather than landing a well-formed, meaningless file.
    if not isinstance(merged.get("repos"), dict):
        print("REFUSE:three-way-merge:merged-has-no-repos-map", file=sys.stderr)
        return 5

    json.dump(merged, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
