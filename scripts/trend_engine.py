#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Deterministic trend computation over the score history (E6.2 / vibe-48; F8.1).

CLI contract (pinned by tests/test_trend_goldens.py):
  stdin  : score_engine's stdout JSON — the current run's scores.
  args   : --root <dir> --history <file> --scope <tag> --run-id <tag> [--limit N]  (N default 10)
  stdout : deterministic JSON {"files": [{"path","current","previous","delta","flag"}],
           "trajectory": [{"run","mean_score","files"}], "status": {"history","scope_matches"}}
  stderr : exactly one warning line when the history is malformed; nothing otherwise.
  exit   : 0 computed (all three history states); 2 contract refusal (bad stdin, bad args,
           a history path outside the root).

**Read first, append last — inside one owner.** The engine reads and normalizes the history
once, computes deltas and the trajectory against that pre-append state, and only then appends
the current run through its own transaction. The ordering hazard the analysis fixed (a
post-append read self-compares) is closed structurally: no caller sequences two tools.

**The record contract** (frozen by the vibe-48 plan): entries carry
{scope, score, band, total_penalty, file} plus optional "run"; readers take the last entry per
(run, scope, file); entries lacking any of scope/score/file are markers and never enter
computation but are preserved byte-for-byte on append; legacy entries (no run) form the single
group "(pre-run-id)" ordered first; the delta baseline is the last pre-append entry per
(scope, file) excluding the current run; trajectory groups appear in append order with the
current run last, mean_score rounded to one decimal, and --limit keeping the last N points.

**Container shapes.** A top-level list and the fresh-init dict ({"vibe_suite_owned": true,
"snapshots": [...]}) both normalize; the append preserves whichever shape it read. A missing
file (and its parent, inside the root) is created; a malformed file is replaced by a fresh list
after the single warning — score_engine's own flagless malformed-input failure is deliberately
untouched, because F8.1's warn-and-continue rule belongs to the trend surface alone.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402

LEGACY_RUN = "(pre-run-id)"


def _is_score_entry(e):
    return isinstance(e, dict) and all(k in e for k in ("scope", "score", "file"))


def _normalize(raw):
    """(entries, shape) for a valid container; raises ValueError otherwise."""
    if isinstance(raw, list):
        return raw, "list"
    if isinstance(raw, dict) and isinstance(raw.get("snapshots"), list):
        return raw["snapshots"], "dict"
    raise ValueError("history is neither a list nor a snapshots container")


def _last_per(entries, key):
    out = {}
    for e in entries:
        out[key(e)] = e
    return out


def compute(history_entries, scope, current_files, run_id, limit):
    scoped = [e for e in history_entries if _is_score_entry(e) and e["scope"] == scope
              and e.get("run") != run_id]
    baseline = _last_per(scoped, lambda e: e["file"])
    files = []
    for f in sorted(current_files, key=lambda f: f["path"]):
        prev = baseline.get(f["path"])
        if prev is None:
            files.append({"path": f["path"], "current": f["score"], "previous": None,
                          "delta": None, "flag": "new"})
        else:
            delta = f["score"] - prev["score"]
            flag = "improved" if delta > 0 else "degraded" if delta < 0 else "unchanged"
            files.append({"path": f["path"], "current": f["score"], "previous": prev["score"],
                          "delta": delta, "flag": flag})
    groups, order = {}, []
    for e in scoped:
        run = e.get("run") or LEGACY_RUN
        if run not in groups:
            groups[run] = []
            order.append(run)
        groups[run].append(e)
    trajectory = []
    for run in order:
        last = _last_per(groups[run], lambda e: (e["scope"], e["file"]))
        scores = [e["score"] for e in last.values()]
        trajectory.append({"run": run, "mean_score": round(sum(scores) / len(scores), 1),
                           "files": len(scores)})
    cur_scores = [f["score"] for f in current_files]
    if cur_scores:
        trajectory.append({"run": run_id, "mean_score": round(sum(cur_scores) / len(cur_scores), 1),
                           "files": len(cur_scores)})
    return files, trajectory[-limit:], len(scoped)


def _append(root, history, raw_container, shape, scope, current_files, run_id):
    entries = []
    for f in current_files:
        penalty = sum(x.get("penalty", 0) for x in f.get("findings", []))
        entries.append({"scope": scope, "score": f["score"], "band": f["band"],
                        "total_penalty": penalty, "file": f["path"], "run": run_id})
    if shape == "list":
        container, target = raw_container, raw_container
    elif shape == "dict":
        container, target = raw_container, raw_container["snapshots"]
    else:  # fresh (missing or malformed)
        container = []
        target = container
    for entry in entries:
        if entry not in target:
            target.append(entry)
    rel = Path(history).resolve().relative_to(Path(root).resolve())
    bridge.ensure_dir_at(root, rel.parent)
    bridge.write_atomic(root, Path(root) / rel,
                        json.dumps(container, indent=2, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--root", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--run-id", dest="run_id", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    try:
        Path(args.history).resolve().relative_to(Path(args.root).resolve())
    except ValueError:
        print("trend_engine: --history must live inside --root", file=sys.stderr)
        return 2
    try:
        score = json.load(sys.stdin)
        current_files = score["files"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"trend_engine: stdin is not score_engine output ({exc})", file=sys.stderr)
        return 2

    hist_path = Path(args.history)
    status, raw, shape, entries = "present", None, "fresh", []
    if not hist_path.is_file():
        status = "missing"
    else:
        try:
            raw = json.loads(hist_path.read_text(encoding="utf-8"))
            entries, shape = _normalize(raw)
        except (json.JSONDecodeError, ValueError):
            print("trend_engine: history is malformed; treating as empty and starting fresh",
                  file=sys.stderr)
            status, raw, shape, entries = "malformed", None, "fresh", []

    files, trajectory, matches = compute(entries, args.scope, current_files,
                                         args.run_id, args.limit)
    out = {"files": files, "trajectory": trajectory,
           "status": {"history": status, "scope_matches": matches}}
    print(json.dumps(out, indent=2, sort_keys=True))
    _append(args.root, hist_path, raw, shape, args.scope, current_files, args.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
