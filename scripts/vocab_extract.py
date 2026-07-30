#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Literary-warrant extractor for the vocabulary discipline (E3.7 / vibe-32).

Emits a deterministic term-frequency table over a plugin's NL artifacts — the
extraction tooling the vocabulary skill names: it verifies literary warrant (a term
already appears in the corpus) and feeds `/vibe-suite:vocab init`. It emits
frequencies ONLY, never the canonical/deprecated split (the registry is
hand-maintained).

Discovery walks the same five artifact classes the R51 checker scans — commands
(incl. shared partials), agents, skills' SKILL.md files, and CLAUDE.md — with
`scripts/check_engine.py` as the owning statement of that class list (cited, not
restated: the glob patterns below mirror its scan set).

Usage:
    vocab_extract.py --root <dir> [--min-count N]

Output (stdout JSON, byte-identical across runs):
    {"root": "<as given>", "terms": [{"term", "count", "files"}, ...]}
sorted by (-count, term); files sorted; tokens are lowercased matches of
`[a-z][a-z0-9_-]+` at word boundaries.
"""

import argparse
import json
import re
import sys
from pathlib import Path

#: The R51 scan classes (check_engine.py is the owning statement of this list).
PATTERNS = ["commands/*.md", "commands/shared/*.md", "agents/*.md",
            "skills/*/SKILL.md", "CLAUDE.md"]

_TOKEN = re.compile(r"\b[a-z][a-z0-9_-]+\b")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True)
    parser.add_argument("--min-count", type=int, default=1)
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print(f"vocab-extract: {args.root!r} is not a directory", file=sys.stderr)
        return 2

    counts, files = {}, {}
    for pattern in PATTERNS:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            seen_here = set()
            for token in _TOKEN.findall(text):
                counts[token] = counts.get(token, 0) + 1
                if token not in seen_here:
                    files.setdefault(token, []).append(rel)
                    seen_here.add(token)

    terms = [{"term": term, "count": counts[term], "files": sorted(files[term])}
             for term in counts if counts[term] >= args.min_count]
    terms.sort(key=lambda t: (-t["count"], t["term"]))
    json.dump({"root": args.root, "terms": terms}, sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
