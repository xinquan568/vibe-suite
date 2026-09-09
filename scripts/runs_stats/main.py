#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""
runs-stats — build the time-bucketed static HTML statistics reports over the issue2pr `runs/` tree
(F8.5 / E6.6, vibe-52; restructured under scripts/ by H12 / vibe-216).

The program half of the package: the CLI, the freeze/history model, and every write. Discovery lives
in `discover.py`, aggregation and bucketing in `aggregate.py`, HTML rendering from
`templates/runs-stats/` in `render.py`. Python standard library plus the repository's audited write
primitive (`scripts/lib/bridge.py`). Ticket identity comes from the resolved issue2pr profile's
anchored `id_pattern`, passed as --id-pattern; the run refuses without it.

Object model: ContainerRun / ExecutionRun / Ticket.
"""

import argparse
import json
import os
import re
import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

runpy.run_path(str(Path(__file__).resolve().parents[1] / "_bootstrap.py"))

import runs_stats.discover as disc  # noqa: E402
from runs_stats.discover import configure, discover, read_text  # noqa: E402
from runs_stats.aggregate import (aggregate, bucket_ids_for_date, bucket_signature,  # noqa: E402
                                  bucket_window, current_bucket_ids, kpis_summary, local_date_of,
                                  parse_rate, rollup_tickets)
from runs_stats.render import render_html, render_index  # noqa: E402
import bridge  # noqa: E402  (scripts/lib — the audited write primitive)
import fsafe  # noqa: E402  (scripts/lib — the audited write primitive)


class HistoryUnreadable(Exception):
    """history.json exists but cannot be read or parsed; the caller decides (refuse or --reset-history)."""

    def __init__(self, path, cause):
        super().__init__(f"{path}: {cause}")
        self.path, self.cause = path, cause


# ----------------------------------------------------------------------------- audited writes (H12 / vibe-216)


def _write(anchor, dest, content):
    """`bridge.write_below`, with a refusal reported as `runs-stats: …` and exit 2 before anything
    else is written in that step (the anchor rule itself lives in `bridge.existing_anchor`)."""
    try:
        bridge.write_below(anchor, dest, content)
    except fsafe.BridgeError as exc:
        print(f"runs-stats: {exc}", file=sys.stderr)
        raise SystemExit(2)


def build_one_report(subset_runs, all_containers, bucket_meta, out_path, as_of, tz,
                     reviewer_rate, runs_root, warnings, period_page, anchor):
    """Render one HTML report for a set of runs (all-time, a bucket, or ad-hoc)."""
    if period_page:
        child_ids = {r["id"] for r in subset_runs}
        containers = [c for c in all_containers if set(c.get("child_run_ids", [])) & child_ids]
    else:
        containers = all_containers
    aggr = aggregate(subset_runs, tz)
    ticket_rows, _ = rollup_tickets(subset_runs)
    undated = sum(1 for r in subset_runs if not local_date_of(r, tz))
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "as_of": as_of,
        "tz": tz,
        "bucket": bucket_meta,
        "runs_root": str(runs_root),
        "filters": bucket_meta.get("filters", ""),
        "reviewer_rate": reviewer_rate,
        "containers": containers,
        "runs": subset_runs,
        "tickets": ticket_rows,
        "aggregates": aggr,
        "warnings": warnings if not period_page else
                    warnings + ([f"{undated} undated run(s) excluded from this period bucket"] if undated else []),
    }
    _write(anchor, out_path, render_html(report))
    return ticket_rows, aggr


# ----------------------------------------------------------------------------- history.json + index.html


def load_history(path):
    """None when there is no history; the parsed dict when there is; `HistoryUnreadable` when a file
    exists but cannot be read or parsed. It used to return None for that last case too, and `main`
    then rebuilt the history — silently regenerating every frozen bucket it could see (H12 / vibe-216)."""
    if path.is_file() or path.is_symlink():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise HistoryUnreadable(path, exc) from exc
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate time-bucketed issue2pr runs statistics HTML reports.")
    ap.add_argument("--runs-root", default="runs")
    ap.add_argument("--reports-dir", default="runs/_reports",
                    help="root for the bucketed tree + history.json + index.html (canonical store)")
    ap.add_argument("--out", default=None,
                    help="optional extra copy of all-time.html (canonical mode) / output path (ad-hoc mode). "
                         "No extra copy is written by default.")
    ap.add_argument("--tz", default="Asia/Shanghai", help="timezone for day/week/month bucketing")
    ap.add_argument("--id-pattern", dest="id_pattern",
                    help="anchored work-item id regex from the resolved issue2pr profile "
                         "(its `id_pattern` field), e.g. '^vibe-(\\d+)$'")
    ap.add_argument("--include-archived", action="store_true", help="include runs/_archived/** (part of config_key)")
    ap.add_argument("--include-legacy", action="store_true", help="include runs/jira/ legacy attempts (part of config_key)")
    ap.add_argument("--force-regenerate", action="store_true",
                    help="overwrite archived (frozen) period files too — for fixing mistakes")
    ap.add_argument("--period", help="restrict/force-regenerate a single bucket id (e.g. 2026-W24, 2026-06, 2026-06-13)")
    ap.add_argument("--reset-history", action="store_true", help="rebuild history.json under the current config_key")
    ap.add_argument("--days-only", action="store_true")
    ap.add_argument("--weeks-only", action="store_true")
    ap.add_argument("--months-only", action="store_true")
    ap.add_argument("--all-time-only", action="store_true")
    # ad-hoc (scope-narrowing) filters → single --out report, never touch canonical store
    ap.add_argument("--ticket")
    ap.add_argument("--scenario")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--include-unknown-date", action="store_true")
    ap.add_argument("--reviewer-rate")
    args = ap.parse_args(argv)

    if not args.id_pattern:
        print("runs-stats: no id_pattern supplied. Pass --id-pattern with the resolved "
              "issue2pr profile's `id_pattern` (see .vibe-suite.md `issue2pr_profile:` -> "
              "profiles/<name>.md). A generic guess would bucket runs wrongly, so this "
              "refuses instead.", file=sys.stderr)
        raise SystemExit(2)
    runs_root = Path(args.runs_root).resolve()
    try:
        configure(runs_root, args.id_pattern)
    except re.error as exc:
        print(f"runs-stats: --id-pattern is not a valid regex: {exc}", file=sys.stderr)
        raise SystemExit(2)
    if not runs_root.is_dir():
        raise SystemExit(f"runs-stats: runs root not found: {runs_root} "
                         "(run from the workspace root containing runs/)")

    tz = args.tz
    try:
        ZoneInfo(tz)
    except Exception:
        raise SystemExit(f"runs-stats: unknown timezone '{tz}'. Use an IANA name like Asia/Shanghai or UTC.")
    rate = parse_rate(args.reviewer_rate)
    warnings = []
    containers, runs = discover(str(runs_root), args.include_archived, args.include_legacy, warnings)

    # attach timeline text once (shared across all reports)
    for r in runs:
        tp = r.pop("timeline_path", None)
        r["timeline"] = read_text(os.path.join(str(runs_root.parent), tp), warnings=warnings) if tp else None

    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ----- ad-hoc filtered mode: single --out report, never touches the canonical store (G1)
    if args.ticket or args.scenario or args.since or args.until:
        if args.ticket:
            bad = [tok.strip() for tok in args.ticket.split(",")
                   if tok.strip() and not disc.ID_RE.fullmatch(tok.strip())]
            if bad:
                print("runs-stats: --ticket value(s) " + ", ".join(repr(b) for b in bad)
                      + f" do not match --id-pattern {args.id_pattern!r}", file=sys.stderr)
                raise SystemExit(2)
        tickets_filter = set(t.strip().upper() for t in args.ticket.split(",")) if args.ticket else None
        scen_filter = set(s.strip() for s in args.scenario.split(",")) if args.scenario else None

        def in_date(r):
            if not (args.since or args.until):
                return True
            ld = local_date_of(r, tz)
            if not ld:
                return args.include_unknown_date
            d = ld.isoformat()
            if args.since and d < args.since:
                return False
            if args.until and d > args.until:
                return False
            return True

        sub = [r for r in runs
               if (not tickets_filter or (r["source_id"] or "").upper() in tickets_filter)
               and (not scen_filter or r["scenario"] in scen_filter) and in_date(r)]
        flab = []
        if tickets_filter:
            flab.append("ticket=" + ",".join(sorted(tickets_filter)))
        if scen_filter:
            flab.append("scenario=" + ",".join(sorted(scen_filter)))
        if args.since:
            flab.append("since " + args.since)
        if args.until:
            flab.append("until " + args.until)
        out = Path(args.out or "runs/_reports/runs-stats-adhoc.html")
        build_one_report(sub, containers, {"kind": "adhoc", "label": "Ad-hoc", "id": "adhoc",
                                           "filters": ", ".join(flab)}, out, as_of, tz, rate,
                         runs_root, warnings, period_page=False, anchor=bridge.existing_anchor(out.absolute().parent))
        print(f"runs-stats: ad-hoc report → {out}  ({len(sub)} runs)")
        print("  NOTE: ad-hoc filtered runs do NOT update the canonical history/index/buckets (G1).")
        return

    # ----- canonical bucketed mode
    reports_dir = Path(args.reports_dir)
    # One containment anchor for every canonical write: the nearest existing directory at or above the
    # reports dir's PARENT, so the reports dir itself is always below the anchor — created through the
    # audited descent when absent, refused when it is a symlink.
    anchor = bridge.existing_anchor(reports_dir.absolute().parent)
    config_key = {"tz": tz, "include_archived": args.include_archived,
                  "include_legacy": args.include_legacy, "id_pattern": args.id_pattern}
    try:
        history = load_history(reports_dir / "history.json")
    except HistoryUnreadable as exc:
        if not args.reset_history:
            print(f"runs-stats: history.json at {exc.path} exists but is unreadable ({exc.cause}); "
                  "refusing to overwrite it. Pass --reset-history to rebuild deliberately, or remove the file.",
                  file=sys.stderr)
            raise SystemExit(2)
        print(f"  reset-history: replacing unreadable history.json ({exc.cause})")
        history = None
    if history and history.get("config_key") != config_key and not args.reset_history:
        raise SystemExit(
            "runs-stats: history.json was built with config "
            f"{history.get('config_key')}, but you ran {config_key}. "
            "Use a different --reports-dir for this view, or --reset-history to rebuild.")
    if args.reset_history or not history or history.get("config_key") != config_key:
        history = {"schema_version": 1, "config_key": config_key, "buckets": {}}
    history.setdefault("buckets", {})

    # assign runs to buckets (by local start date)
    buckets = {"day": {}, "week": {}, "month": {}}
    undated = 0
    for r in runs:
        ids = bucket_ids_for_date(local_date_of(r, tz))
        if not ids:
            undated += 1
            continue
        for kind in ("day", "week", "month"):
            buckets[kind].setdefault(ids[kind], []).append(r)
    cur = current_bucket_ids(tz)

    only = {"day": args.days_only, "week": args.weeks_only, "month": args.months_only}
    any_only = any(only.values()) or args.all_time_only
    surgical = bool(args.period)  # --period = regenerate exactly that one bucket, nothing else
    do_all_time = ((not any_only) or args.all_time_only) and not surgical
    do_kind = {k: ((not any_only) or only[k]) for k in ("day", "week", "month")}

    written, frozen_kept, refreshed_stale = [], 0, 0

    # all-time (always live)
    if do_all_time:
        atmeta = {"kind": "all-time", "label": "All-time", "id": "all-time", "filters": "canonical · no scope filters"}
        tr, ag = build_one_report(runs, containers, atmeta, reports_dir / "all-time.html",
                                  as_of, tz, rate, runs_root, warnings, period_page=False, anchor=anchor)
        history["buckets"]["all-time"] = {"kind": "all-time", "as_of": as_of, "frozen": False,
                                          "kpis": kpis_summary(tr, runs, ag)}
        written.append("all-time.html")
        # optional extra copy ONLY if --out is explicitly given (no default duplicate file)
        if args.out:
            compat = Path(args.out)
            _write(bridge.existing_anchor(compat.absolute().parent), compat,
                   (reports_dir / "all-time.html").read_text(encoding="utf-8"))

    # period buckets
    for kind in ("month", "week", "day"):
        if not do_kind[kind]:
            continue
        for bid, rs in sorted(buckets[kind].items()):
            out = reports_dir / kind / f"{bid}.html"
            is_current = (bid == cur[kind])
            exists = out.exists()
            sig = bucket_signature(rs)
            tag = ""
            if args.period:
                regen = (bid == args.period)
            elif is_current:
                regen = True            # current period — always live
            elif not exists:
                regen = True            # missing past bucket — backfill
            elif args.force_regenerate:
                regen = True            # explicit override
            elif history["buckets"].get(bid, {}).get("sig") != sig:
                # past bucket whose data changed since its snapshot (runs added after a mid-period
                # generation, or a later iterate) — refresh ONCE so the frozen snapshot is complete,
                # then it freezes again because the signature now matches.
                regen = True
                refreshed_stale += 1
                tag = " (refreshed: data changed)"
            else:
                regen = False           # past bucket, complete & unchanged — frozen
            if not regen:
                frozen_kept += 1
                continue
            ws, we, wlabel = bucket_window(bid, kind)
            label = {"day": "Day", "week": "Week", "month": "Month"}[kind] + " " + bid
            meta = {"kind": kind, "id": bid, "label": label, "window": wlabel,
                    "frozen": not is_current, "filters": "canonical · no scope filters"}
            tr, ag = build_one_report(rs, containers, meta, out, as_of, tz, rate,
                                      runs_root, warnings, period_page=True, anchor=anchor)
            history["buckets"][bid] = {"kind": kind, "as_of": as_of, "frozen": not is_current,
                                       "window": wlabel, "sig": sig, "kpis": kpis_summary(tr, rs, ag)}
            written.append(f"{kind}/{bid}.html{tag}")

    if surgical and not any(args.period in w for w in written):
        print(f"  note: --period {args.period} matched no bucket with runs (nothing regenerated)")

    # NOTE: a day/week/month file exists iff that period has >=1 run. Empty periods (including the
    # current one when it has no runs yet) are skipped entirely — no file, no history row, no index
    # entry. all-time.html + index.html always regenerate (they are the entry points).

    # history + index
    _write(anchor, reports_dir / "history.json", json.dumps(history, indent=2, ensure_ascii=False))
    _write(anchor, reports_dir / "index.html", render_index(history, reports_dir))

    print(f"runs-stats: canonical reports under {reports_dir}/  (tz={tz})")
    print(f"  wrote {len(written)} report(s): {', '.join(written[:6])}{' …' if len(written) > 6 else ''}")
    if refreshed_stale:
        print(f"  refreshed {refreshed_stale} past bucket(s) whose data changed since their snapshot")
    print(f"  frozen/archived kept untouched: {frozen_kept}"
          + ("  (complete & unchanged; use --force-regenerate or --period <id> to rebuild)" if frozen_kept else ""))
    print(f"  index: {reports_dir}/index.html   history: {reports_dir}/history.json")
    print(f"  buckets present — days:{len(buckets['day'])} weeks:{len(buckets['week'])} months:{len(buckets['month'])}"
          f"   undated runs (all-time only): {undated}   parse warnings: {len(warnings)}")


if __name__ == "__main__":
    main()
