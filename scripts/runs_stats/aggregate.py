# SPDX-License-Identifier: ISC
"""runs-stats — aggregation and time bucketing over the run records `discover` builds (H12 / vibe-216).

Ticket rollup, the per-report aggregates, `--tz` bucketing (day / ISO week / month), the bucket content
signature the freeze model keys on, and the KPI summary written to history.json. Library module: stdlib
only, no `sys.path`, no I/O.
"""

import hashlib
import statistics
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .discover import parse_iso

# ----------------------------------------------------------------------------- ticket rollup


def rollup_tickets(runs):
    tickets = {}
    for r in runs:
        key = r["source_id"] or "(unknown)"
        tickets.setdefault(key, []).append(r)
    out = []
    for key, rs in sorted(tickets.items()):
        non_archived = [r for r in rs if not r.get("archived")]
        pool = non_archived or rs

        def started(r):
            return r["timing"].get("run_started_at") or ""
        headline = sorted(pool, key=lambda r: (started(r), r["id"]))[-1]
        pr_urls = sorted(set(u for r in pool for u in r["pr_urls"]))
        out.append({
            "key": key,
            "title": headline["title"] or next((r["title"] for r in rs if r["title"]), ""),
            "source_url": headline["source_url"],
            "headline_run_id": headline["id"],
            "headline_status_cat": headline["status_cat"],
            "headline_status_sub": headline["status_sub"],
            "scenario": headline["scenario"],
            "attempt_count": len(rs),
            "run_ids": [r["id"] for r in rs],
            "pr_urls": pr_urls,
        })
    return out, tickets


# ----------------------------------------------------------------------------- aggregates


def aggregate(runs, tz="UTC"):
    def bump(d, k):
        d[k] = d.get(k, 0) + 1

    status_dist, scenario_dist, repo_dist, backend_dist, mode_dist = {}, {}, {}, {}, {}
    priority_dist, fixver_dist = {}, {}
    rev_tot = {"input_total": 0, "input_cached": 0, "output": 0, "reasoning_output": 0}
    worker_tot = {"input_total": 0, "output": 0}
    tool_calls = 0
    findings = 0
    commits = 0
    prs = set()
    active_list, elapsed_list = [], []
    verdict_dist = {}
    approved_no_rework = rework_one_iter = multi_round = 0
    tests_tot = {"run": 0, "failed": 0, "skipped": 0, "errors": 0}
    tests_cov = 0
    stop_reasons = {}
    per_day = {}

    for r in runs:
        if r.get("archived") or r.get("legacy"):
            # still counted in totals but flagged; keep them in token/None where present
            pass
        bump(status_dist, r["status_cat"])
        bump(scenario_dist, r["scenario"])
        for rp in (r["repos"] or ["(none)"]):
            bump(repo_dist, rp or "(none)")
        bump(backend_dist, r["reviewer_backend"])
        bump(mode_dist, r["review_mode"])
        pr = (r["jira"] or {}).get("priority")
        if pr:
            bump(priority_dist, pr if isinstance(pr, str) else (pr.get("name") if isinstance(pr, dict) else str(pr)))
        for fv in (r["jira"] or {}).get("fixVersions", []):
            bump(fixver_dist, fv if isinstance(fv, str) else (fv.get("name") if isinstance(fv, dict) else str(fv)))
        for k in rev_tot:
            rev_tot[k] += r["reviewer_tokens"].get(k, 0)
        worker_tot["input_total"] += r["worker_tokens_est"].get("input_total", 0)
        worker_tot["output"] += r["worker_tokens_est"].get("output", 0)
        tool_calls += r["tool_calls"]
        findings += r["findings_caught"]
        commits += len(r["commits"])
        prs.update(r["pr_urls"])
        if r["timing"].get("active_seconds"):
            active_list.append(r["timing"]["active_seconds"])
        if r["timing"].get("elapsed_seconds"):
            elapsed_list.append(r["timing"]["elapsed_seconds"])
        for v in r["verdicts"]:
            bump(verdict_dist, v)
        for rm in r["rounds"]:
            if rm["approved_no_rework"]:
                approved_no_rework += 1
            elif rm["rework_present"]:
                rework_one_iter += 1
            if rm["stop_reason"]:
                bump(stop_reasons, rm["stop_reason"])
        if r["n_rounds"] > 1:
            multi_round += 1
        if r["tests"]:
            tests_cov += 1
            for k in tests_tot:
                tests_tot[k] += r["tests"].get(k, 0)
        ld = local_date_of(r, tz)
        day = ld.isoformat() if ld else None
        if day:
            d = per_day.setdefault(day, {"runs": 0, "reviewer_tokens": 0})
            d["runs"] += 1
            d["reviewer_tokens"] += r["reviewer_tokens"]["input_total"] + r["reviewer_tokens"]["output"]

    return {
        "status_dist": status_dist, "scenario_dist": scenario_dist, "repo_dist": repo_dist,
        "backend_dist": backend_dist, "mode_dist": mode_dist,
        "priority_dist": priority_dist, "fixver_dist": fixver_dist,
        "reviewer_tokens": rev_tot, "worker_tokens_est": worker_tot, "tool_calls": tool_calls,
        "findings": findings, "commits": commits, "prs": sorted(prs),
        "active_total": sum(active_list), "active_median": int(statistics.median(active_list)) if active_list else 0,
        "elapsed_total": sum(elapsed_list), "elapsed_median": int(statistics.median(elapsed_list)) if elapsed_list else 0,
        "verdict_dist": verdict_dist,
        "approved_no_rework": approved_no_rework, "rework_one_iter": rework_one_iter,
        "multi_round": multi_round,
        "tests": tests_tot, "tests_coverage_runs": tests_cov,
        "stop_reasons": stop_reasons, "per_day": per_day,
    }


def parse_rate(s):
    if not s:
        return None
    out = {}
    for part in s.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k.strip()] = float(v)
            except ValueError:
                pass
    return out or None


# ----------------------------------------------------------------------------- time bucketing


def local_date_of(r, tz):
    """The run's start date in the given timezone (or None if undated)."""
    dt = parse_iso(r["timing"].get("run_started_at"))
    if not dt:
        return None
    try:
        return dt.astimezone(ZoneInfo(tz)).date()
    except Exception:
        return dt.date()


def bucket_ids_for_date(d):
    if d is None:
        return None
    iso = d.isocalendar()
    return {"day": d.isoformat(), "week": f"{iso[0]}-W{iso[1]:02d}", "month": f"{d.year:04d}-{d.month:02d}"}


def current_bucket_ids(tz):
    today = datetime.now(ZoneInfo(tz)).date()
    return bucket_ids_for_date(today)


def bucket_window(bid, kind):
    """(start_iso, end_iso, 'start → end') human window for a bucket id."""
    if kind == "day":
        return bid, bid, bid
    if kind == "month":
        y, m = (int(x) for x in bid.split("-"))
        start = date(y, m, 1)
        end = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1) - timedelta(days=1)
        return start.isoformat(), end.isoformat(), f"{start.isoformat()} → {end.isoformat()}"
    if kind == "week":
        ys, ws = bid.split("-W")
        mon = date.fromisocalendar(int(ys), int(ws), 1)
        sun = date.fromisocalendar(int(ys), int(ws), 7)
        return mon.isoformat(), sun.isoformat(), f"{mon.isoformat()} → {sun.isoformat()}"
    return None, None, ""


def bucket_signature(runs_subset):
    """Deterministic content fingerprint of a bucket's run-set. Changes whenever a run is added or an
    existing run's data changes (new rounds/tokens/commits) — used to detect a stale frozen snapshot
    (e.g. runs added after a mid-period generation, or a later iterate). Independent of generation time."""
    parts = []
    for r in sorted(runs_subset, key=lambda x: x["id"]):
        rt = r["reviewer_tokens"]
        parts.append("|".join(str(x) for x in [
            r["id"], rt["input_total"] + rt["output"], r["n_rounds"], r["status_cat"],
            r["timing"].get("active_seconds"), r["findings_caught"], len(r["commits"]),
            r["timing"].get("run_started_at"),
        ]))
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def kpis_summary(ticket_rows, runs, aggr):
    rt = aggr["reviewer_tokens"]
    wt = aggr["worker_tokens_est"]
    sd = aggr["status_dist"]
    return {
        "tasks": len(ticket_rows), "runs": len(runs),
        "success": sd.get("success", 0), "stopped": sd.get("stopped", 0),
        "failed": sd.get("failed", 0),
        "reviewer_tokens": rt["input_total"] + rt["output"],
        "worker_tokens_est": wt["input_total"] + wt["output"],
        "active_seconds": aggr["active_total"], "prs": len(aggr["prs"]),
        "findings": aggr["findings"], "commits": aggr["commits"],
    }
