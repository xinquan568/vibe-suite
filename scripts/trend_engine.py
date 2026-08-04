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


def trajectory_from_entries(entries, scope, limit):
    """The STORED record's trajectory — read-only, no current-score point, no append.

    The report surface (vibe-49) consumes this: reporting is observation of the record, and the
    trend command owns the appending workflow. Group semantics match `compute` exactly — the
    legacy bucket first regardless of physical position, keyed runs in first-appearance order,
    last-wins per (run, scope, file) — minus the current-run merge, which only the trend flow
    performs.
    """
    scoped = [e for e in entries if _is_score_entry(e) and e["scope"] == scope]
    legacy = [e for e in scoped if not e.get("run")]
    keyed, keyed_order = {}, []
    for e in scoped:
        r = e.get("run")
        if not r:
            continue
        if r not in keyed:
            keyed[r] = []
            keyed_order.append(r)
        keyed[r].append(e)
    sequence = ([(LEGACY_RUN, legacy)] if legacy else []) \
        + [(r, keyed[r]) for r in keyed_order]
    trajectory = []
    for run, group in sequence:
        last = _last_per(group, lambda e: (e["scope"], e["file"]))
        scores = [e["score"] for e in last.values()]
        trajectory.append({"run": run, "mean_score": round(sum(scores) / len(scores), 1),
                           "files": len(scores)})
    return trajectory[-limit:]


def compute(history_entries, scope, current_files, run_id, limit):
    scoped_all = [e for e in history_entries if _is_score_entry(e) and e["scope"] == scope]
    baseline_input = [e for e in scoped_all if e.get("run") != run_id]
    baseline = _last_per(baseline_input, lambda e: e["file"])
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
    # Trajectory groups: the legacy bucket is ALWAYS first regardless of physical position;
    # keyed runs follow in first-appearance order; the current run — existing entries of the
    # same run id merged with the incoming files, last-wins per (scope, file) — is always last.
    legacy = [e for e in scoped_all if not e.get("run")]
    keyed, keyed_order = {}, []
    for e in scoped_all:
        r = e.get("run")
        if not r:
            continue
        if r not in keyed:
            keyed[r] = []
            keyed_order.append(r)
        keyed[r].append(e)
    current_group = keyed.pop(run_id, [])
    if run_id in keyed_order:
        keyed_order.remove(run_id)
    merged = _last_per(current_group, lambda e: (e["scope"], e["file"]))
    for f in current_files:
        merged[(scope, f["path"])] = {"scope": scope, "file": f["path"], "score": f["score"]}
    sequence = ([(LEGACY_RUN, legacy)] if legacy else []) \
        + [(r, keyed[r]) for r in keyed_order] \
        + ([(run_id, list(merged.values()))] if merged else [])
    trajectory = []
    for run, group in sequence:
        last = _last_per(group, lambda e: (e["scope"], e["file"]))
        scores = [e["score"] for e in last.values()]
        trajectory.append({"run": run, "mean_score": round(sum(scores) / len(scores), 1),
                           "files": len(scores)})
    return files, trajectory[-limit:], len(baseline_input)


def _array_close_index(text, open_index):
    """The index of the `]` matching the `[` at open_index — string-aware, so brackets inside
    JSON strings never count. Deterministic and tiny; a full parse would re-serialize and lose
    the marker bytes the contract preserves."""
    depth, i, in_str, esc = 0, open_index, False, False
    while i < len(text):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unbalanced array")


def _append(root, history, raw_text, shape, existing_entries, scope, current_files, run_id):
    """Byte-preserving append: existing bytes — markers included — are never re-serialized.

    New entries splice in before the entries array's closing bracket; everything before and
    after that point is the file's original text. A fresh history (missing or malformed) is a
    canonical new list.
    """
    new = []
    for f in current_files:
        penalty = sum(x.get("penalty", 0) for x in f.get("findings", []))
        entry = {"scope": scope, "score": f["score"], "band": f["band"],
                 "total_penalty": penalty, "file": f["path"], "run": run_id}
        if entry not in existing_entries and entry not in new:
            new.append(entry)
    if shape == "fresh":
        content = json.dumps(new, indent=2, sort_keys=True) + "\n"
    elif not new:
        content = raw_text
    else:
        if shape == "list":
            open_idx = raw_text.index("[")
        else:
            key_idx = raw_text.index('"snapshots"')
            open_idx = raw_text.index("[", key_idx)
        close_idx = _array_close_index(raw_text, open_idx)
        body = raw_text[open_idx + 1:close_idx]
        rendered = ",\n".join(json.dumps(e, sort_keys=True) for e in new)
        indent = "  " if shape == "list" else "    "
        rendered = "\n".join(indent + line for line in rendered.splitlines())
        if body.strip():
            insertion = body.rstrip() + ",\n" + rendered + "\n" + (" " * (0 if shape == "list" else 2))
        else:
            insertion = "\n" + rendered + "\n" + (" " * (0 if shape == "list" else 2))
        content = raw_text[:open_idx + 1] + insertion + raw_text[close_idx:]
    rel = Path(history).resolve().relative_to(Path(root).resolve())
    bridge.ensure_dir_at(root, rel.parent)
    bridge.write_atomic(root, Path(root) / rel, content.encode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--root", required=True)
    parser.add_argument("--history", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--run-id", dest="run_id", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)

    if not 1 <= len(args.run_id) <= 64:
        print("trend_engine: --run-id must be 1-64 characters", file=sys.stderr)
        return 2
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
    status, raw_text, shape, entries = "present", "", "fresh", []
    if not hist_path.is_file():
        status = "missing"
    else:
        # Bytes first: text mode would translate CRLF to LF and the append would silently
        # rewrite every line ending the byte-preservation contract protects.
        raw_text = hist_path.read_bytes().decode("utf-8")
        try:
            entries, shape = _normalize(json.loads(raw_text))
        except (json.JSONDecodeError, ValueError):
            print("trend_engine: history is malformed; treating as empty and starting fresh",
                  file=sys.stderr)
            status, raw_text, shape, entries = "malformed", "", "fresh", []

    files, trajectory, matches = compute(entries, args.scope, current_files,
                                         args.run_id, args.limit)
    out = {"files": files, "trajectory": trajectory,
           "status": {"history": status, "scope_matches": matches}}
    print(json.dumps(out, indent=2, sort_keys=True))
    _append(args.root, hist_path, raw_text, shape, entries, args.scope, current_files,
            args.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
