#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Suite-level release score for the AC-7 pre-release quality gate (E7.4 / vibe-56).

`scripts/score_engine.py` is the deterministic scorer, and it is deliberately not a gate: it
consumes a record stream, reports PER-FILE scores, and exits 0 whatever those scores are (its
nonzero exits are contract refusals). `/vibe-suite:score` narrates it with agent-mediated
discovery, which a session-less runner cannot do. This module is the missing middle — it
discovers the corpus, frames the records, aggregates a SUITE verdict, and exits nonzero when
any artifact falls below the threshold.

Discovery follows `commands/shared/discover.md`'s Category A/B patterns rather than the
manifest's registration arrays, so shared partials, hook registrations, the manifest pair and
`CLAUDE.md` are scored too — an artifact class the manifest does not list is exactly where a
regression would otherwise hide.

The threshold is passed EXPLICITLY (default 80 = Strict). `.vibe-suite.md` declares no
`score_threshold`, so inheriting config would silently resolve to Standard 70 and the gate
would claim Strict while enforcing less. The config is still passed to the engine for its
other settings; the comparison here is this module's own.

Fails closed: an engine refusal, a skipped record, a missing or duplicated result, or an empty
corpus each exit nonzero rather than reporting success.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
ENGINE = REPO_ROOT / "scripts" / "score_engine.py"

#: (glob, engine type, exclude-prefix) per discover.md's Category A + the Category B root file.
PATTERNS = [
    ("commands/*.md", "command", None),
    ("commands/shared/*.md", "command", None),
    ("agents/*.md", "agent", None),
    ("skills/*/SKILL.md", "skill", None),
    ("CLAUDE.md", "memory", None),
]


def discover(root):
    """Every scored artifact, as (type, relative-path), sorted and deduplicated."""
    found = {}
    for pattern, kind, _ in PATTERNS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            found[rel] = kind
    return sorted((kind, rel) for rel, kind in found.items())


def score(root, records, config=None):
    payload = b"".join(f"{kind}\x1f{rel}".encode() + b"\x00" for kind, rel in records)
    argv = [sys.executable, str(ENGINE), "--root", str(root)]
    if config is not None:
        argv += ["--config", str(config)]
    proc = subprocess.run(argv, input=payload, capture_output=True, timeout=600)
    if proc.returncode != 0:
        raise SystemExit(f"release-score: engine refused (exit {proc.returncode}): "
                         f"{proc.stderr.decode(errors='replace').strip()}")
    try:
        return json.loads(proc.stdout.decode())
    except ValueError as exc:
        raise SystemExit(f"release-score: engine output is not JSON: {exc}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--threshold", type=int, default=80,
                        help="Strict is 80; passed explicitly, never inherited")
    parser.add_argument("--config", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    records = discover(root)
    if not records:
        print("release-score: no artifacts discovered — the gate would pass vacuously",
              file=sys.stderr)
        return 2

    report = score(root, records, args.config)
    files = report.get("files")
    if not isinstance(files, list) or not files:
        print("release-score: engine returned no per-file results", file=sys.stderr)
        return 2
    skipped = (report.get("run") or {}).get("skipped") or []
    if skipped:
        print(f"release-score: engine skipped {len(skipped)} record(s): {skipped[:5]}",
              file=sys.stderr)
        return 2

    scored = {}
    for entry in files:
        rel = entry.get("path") or entry.get("file")
        if rel in scored:
            print(f"release-score: duplicate result for {rel}", file=sys.stderr)
            return 2
        scored[rel] = entry.get("score")
    missing = [rel for _, rel in records if rel not in scored]
    if missing:
        print(f"release-score: {len(missing)} artifact(s) had no result: {missing[:5]}",
              file=sys.stderr)
        return 2

    below = sorted((s, rel) for rel, s in scored.items()
                   if not isinstance(s, int) or s < args.threshold)
    lowest = min(scored.values(), key=lambda v: (v is None, v))
    if args.json:
        json.dump({"threshold": args.threshold, "artifacts": len(scored),
                   "lowest": lowest, "below": [{"path": r, "score": s} for s, r in below]},
                  sys.stdout, indent=2, sort_keys=True)
        print()
    else:
        for s, rel in below:
            print(f"{rel}: {s} < {args.threshold}")
        print(f"release-score: {len(scored)} artifact(s), lowest {lowest}, "
              f"threshold {args.threshold} — {'FAIL' if below else 'pass'}")
    return 1 if below else 0


if __name__ == "__main__":
    sys.exit(main())
