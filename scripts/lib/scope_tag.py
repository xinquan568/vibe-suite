#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The one scope-tag derivation `/vibe-suite:score` and `/vibe-suite:trend` share (E6.2 / vibe-48).

Four canonical tags — `full` (no argument), `path:<posix-rel>` (a path argument), `changed`
(bare --changed), `changed:<posix-rel>` (path plus --changed). One executable derivation exists
so the two command docs can invoke it verbatim instead of restating the mapping: two restatements
of one rule is how the apples-to-apples filter would silently stop matching. A path outside the
root refuses (exit 2, nothing on stdout) — a tag for a foreign path would poison the history.
"""

import argparse
import os
import sys
from pathlib import Path


def derive(root, path=None, changed=False):
    if path is None:
        return "changed" if changed else "full"
    # Resolved on both sides: a lexical relpath admits a symlink inside the root pointing
    # outside it, and a tag for a foreign path would poison the history.
    root_r = Path(root).resolve()
    candidate = Path(path)
    candidate = candidate if candidate.is_absolute() else root_r / candidate
    try:
        rel = candidate.resolve().relative_to(root_r)
    except ValueError:
        raise ValueError(f"{path!r} resolves outside the root") from None
    posix = rel.as_posix()
    if posix == ".":
        return "changed" if changed else "full"
    prefix = "changed:" if changed else "path:"
    return prefix + posix


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--root", required=True)
    parser.add_argument("--path")
    parser.add_argument("--changed", action="store_true")
    args = parser.parse_args(argv)
    try:
        print(derive(args.root, args.path, args.changed))
    except ValueError as exc:
        print(f"scope_tag: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
