#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Deterministic counting seam for /vibe-suite:ls.

The scanner agent discovers; this helper counts; the command orchestrates. Both the command at
runtime and tests/test_ls_goldens.py invoke THIS file, so the counting rule exists exactly once.

Input (stdin, binary): records of `<category>\\x1f<relative-path>\\x00` — the unit separator
splits the two fields and NUL terminates the record, so any byte a filesystem allows in a name
(spaces, quotes, dashes, even newlines) travels inertly. Nothing here invokes a shell, builds a
command string, or executes a discovered path; hostile names are data.

Arg: --root <dir>. Every path is resolved against the root and refused (exit 2, all offenders
listed on stderr) if it is absolute, escapes the root after normalization, or does not exist.

Output (stdout): JSON — per category {"files", "lines", "tokens"} plus "total".

Counting semantics (normative; commands/ls.md cites this file):
  lines  = newline count, POSIX `wc -l` semantics — an unterminated final line is not counted.
  tokens = per-file ceil(byte_length / 4), summed. Never a ceiling over aggregated bytes.
  Category values are sums over member files; "total" sums the category rows.
"""

import argparse
import json
import sys
from pathlib import Path

RS = b"\x00"
US = b"\x1f"


def parse_records(raw):
    records = []
    for chunk in raw.split(RS):
        if not chunk:
            continue
        category, sep, path = chunk.partition(US)
        if not sep or not category or not path:
            raise ValueError(f"malformed record {chunk!r}: expected <category>\\x1f<path>")
        records.append((category.decode("utf-8"), path.decode("utf-8")))
    return records


def resolve(root, rel):
    """Resolve `rel` inside `root`, returning the Path or a refusal reason."""
    if rel.startswith("/") or rel.startswith("~"):
        return None, "absolute or home-anchored path"
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, "escapes the scan root"
    if not candidate.is_file():
        return None, "not an existing regular file"
    return candidate, None


def count_file(path):
    data = path.read_bytes()
    lines = data.count(b"\n")
    tokens = -(-len(data) // 4)  # ceil without floats
    return len(data), lines, tokens


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"ls_counts: root {args.root!r} is not a directory", file=sys.stderr)
        return 2

    try:
        records = parse_records(sys.stdin.buffer.read())
    except ValueError as err:
        print(f"ls_counts: {err}", file=sys.stderr)
        return 2

    offenders = []
    resolved = []
    for category, rel in records:
        path, reason = resolve(root, rel)
        if path is None:
            offenders.append(f"{rel!r}: {reason}")
        else:
            resolved.append((category, path))
    if offenders:
        for line in offenders:
            print(f"ls_counts: refused {line}", file=sys.stderr)
        return 2

    out = {}
    for category, path in resolved:
        row = out.setdefault(category, {"files": 0, "lines": 0, "tokens": 0})
        _, lines, tokens = count_file(path)
        row["files"] += 1
        row["lines"] += lines
        row["tokens"] += tokens
    total = {"files": 0, "lines": 0, "tokens": 0}
    for row in out.values():
        for key in total:
            total[key] += row[key]
    ordered = {c: out[c] for c in sorted(out)}
    ordered["total"] = total
    json.dump(ordered, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
