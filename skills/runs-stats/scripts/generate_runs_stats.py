#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""
generate_runs_stats.py — build a static HTML statistics report over the issue2pr `runs/` tree
(F8.5 / E6.6, vibe-52 — ported from the workspace runs-stats skill).

Python standard library ONLY (json, pathlib, datetime, argparse, html, re, statistics, os).
Every generated page inlines the vendored Chart.js bundle (vendor/chart.umd.min.js), so
dashboards render from file:// with no network. Ticket identity comes from the resolved
issue2pr profile's anchored `id_pattern`, passed as --id-pattern; the run refuses without it.

Object model: ContainerRun / ExecutionRun / Ticket.
"""

import argparse
import hashlib
import html
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

# ----------------------------------------------------------------------------- helpers


_CHART_BUNDLE_CACHE = None


def chart_bundle():
    """The vendored Chart.js source, read once. Inlined into every page (F8.5(c)):
    a static report under a consumer's runs/_reports/ cannot portably reference a
    plugin-install path, and file:// rendering must need no network."""
    global _CHART_BUNDLE_CACHE
    if _CHART_BUNDLE_CACHE is None:
        vendor = Path(__file__).resolve().parent.parent / "vendor" / "chart.umd.min.js"
        _CHART_BUNDLE_CACHE = vendor.read_text(encoding="utf-8")
    return _CHART_BUNDLE_CACHE

# The work-item id pattern is profile-supplied (--id-pattern; the issue2pr profile's
# anchored `id_pattern`). ID_RE keeps the anchored form for whole-id matches; SEARCH_RE is
# its unanchored core, used only for the run-folder-name fallback when a run's metadata
# carries no id. main() sets both before discovery.
ID_RE = None
SEARCH_RE = None
TS_CLEAN_RE = re.compile(r"(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")

IGNORE_DIR_NAMES = {"worktrees", "source-snapshots", "subtasks", "tickets", ".git"}


def parse_iso(ts):
    """Tolerant ISO-8601 -> aware datetime (UTC). Returns None on failure."""
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    # normalise trailing Z and offset-without-colon
    s = s.replace("Z", "+00:00")
    m = re.match(r"^(.*[+-]\d{2})(\d{2})$", s)
    if m and ":" not in s[-3:]:
        s = m.group(1) + ":" + m.group(2)
    for cand in (s, s.split(".")[0]):
        try:
            dt = datetime.fromisoformat(cand)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def load_json(path, warnings):
    if not os.path.isfile(path):  # missing is expected (e.g. manifest-only runs) — not a warning
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # malformed / unreadable -> warning, never abort
        warnings.append(f"parse-error: {os.path.relpath(path)} :: {exc.__class__.__name__}: {exc}")
        return None


def read_text(path, cap=20000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            t = fh.read()
        return t[:cap] + ("\n…(truncated)…" if len(t) > cap else "")
    except Exception:
        return None


def ticket_key_from(name):
    m = SEARCH_RE.search(name or "") if SEARCH_RE else None
    return m.group(0).upper() if m else None


def union_seconds(intervals):
    """Sum of the union of [start,end] datetime intervals, in seconds."""
    iv = sorted([(a, b) for a, b in intervals if a and b and b >= a])
    if not iv:
        return 0.0
    total = 0.0
    cur_s, cur_e = iv[0]
    for s, e in iv[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += (cur_e - cur_s).total_seconds()
            cur_s, cur_e = s, e
    total += (cur_e - cur_s).total_seconds()
    return total


# ----------------------------------------------------------------------------- token normalisation


def _toknum(d, *keys):
    for k in keys:
        if isinstance(d, dict) and isinstance(d.get(k), (int, float)):
            return int(d[k])
    return None


def normalize_token_block(tok):
    """Map any observed log token shape -> canonical dict, or None.
    Handles: tokens.{input_tokens,cached_input_tokens,output_tokens,reasoning_output_tokens},
             {input_total,input_cached,output,reasoning_output}, {input_estimate,output_estimate}."""
    if not isinstance(tok, dict):
        return None
    input_total = _toknum(tok, "input_tokens", "input_total", "input_estimate", "input")
    input_cached = _toknum(tok, "cached_input_tokens", "input_cached")
    output = _toknum(tok, "output_tokens", "output", "output_estimate")
    reasoning = _toknum(tok, "reasoning_output_tokens", "reasoning_output", "reasoning")
    if input_total is None and output is None:
        return None
    method = tok.get("method") or ""
    if "estimate" in method:
        accuracy = "estimate"
    elif "reported" in method:  # codex-reported / subagent-reported
        accuracy = "accurate"
    else:
        accuracy = "unknown"
    input_uncached = None
    if input_total is not None and input_cached is not None:
        input_uncached = max(input_total - input_cached, 0)
    return {
        "input_total": input_total or 0,
        "input_cached": input_cached or 0,
        "input_uncached": input_uncached if input_uncached is not None else (input_total or 0),
        "output": output or 0,
        "reasoning_output": reasoning or 0,
        "method": method,
        "accuracy": accuracy,
    }


def tokens_from_log(log):
    """Extract a token block from a log.json dict, probing all known locations."""
    if not isinstance(log, dict):
        return None
    for loc in (log.get("tokens"), log.get("verify_tokens"),
                (log.get("verify") or {}).get("tokens") if isinstance(log.get("verify"), dict) else None):
        nb = normalize_token_block(loc)
        if nb:
            return nb
    # flat estimate/verifier fields directly on the log
    flat = normalize_token_block(log)
    return flat


def usage_from_event_stream(path, warnings):
    """Parse a codex JSONL stream -> (token_block, tool_call_count). Accurate reviewer tokens."""
    usage = None
    tool_calls = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                t = ev.get("type")
                if t in ("command_execution", "item.completed", "item.started"):
                    tool_calls += 1
                elif t == "turn.completed" and isinstance(ev.get("usage"), dict):
                    usage = ev["usage"]
    except Exception as exc:
        warnings.append(f"stream-error: {path} :: {exc}")
        return None, 0
    if not usage:
        return None, tool_calls
    nb = {
        "input_total": int(usage.get("input_tokens", 0) or 0),
        "input_cached": int(usage.get("cached_input_tokens", 0) or 0),
        "output": int(usage.get("output_tokens", 0) or 0),
        "reasoning_output": int(usage.get("reasoning_output_tokens", 0) or 0),
        "method": "codex-reported",
        "accuracy": "accurate",
    }
    nb["input_uncached"] = max(nb["input_total"] - nb["input_cached"], 0)
    return nb, tool_calls


# ----------------------------------------------------------------------------- unit discovery


def parse_unit_path(rel_parts):
    """From path parts under a run dir, derive round/phase/step_base/iteration/repo."""
    info = {"round": None, "phase": None, "step_base": None, "iteration": None, "repo": None}
    for i, p in enumerate(rel_parts):
        if p.startswith("round-"):
            try:
                info["round"] = int(p.split("-", 1)[1])
            except ValueError:
                pass
        elif p.startswith("phase-"):
            info["phase"] = p
        elif p.startswith("step-"):
            info["step_base"] = p
        elif p.startswith("iter-"):
            try:
                info["iteration"] = int(p.split("-", 1)[1])
            except ValueError:
                info["iteration"] = p
        elif p == "per-repo" and i + 1 < len(rel_parts):
            info["repo"] = rel_parts[i + 1]
    return info


def collect_units(run_dir, warnings):
    """Walk <run_dir>/round-*/ recursively; build a unit per dir holding artifacts."""
    units = []
    for dirpath, dirnames, filenames in os.walk(run_dir):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIR_NAMES and not d.startswith(".")]
        rel = os.path.relpath(dirpath, run_dir)
        parts = [] if rel == "." else rel.split(os.sep)
        if not parts or not parts[0].startswith("round-"):
            continue
        has_log = "log.json" in filenames
        stream_name = next((f for f in ("codex.jsonl", "reviewer.json") if f in filenames), None)
        if not has_log and not stream_name:
            continue
        info = parse_unit_path(parts)
        unit = {"path": rel, **info, "tokens": None, "tool_calls": 0,
                "duration": None, "start": None, "end": None,
                "verdict": None, "severity": None, "findings_count": None,
                "outcome": None, "role": None, "tests": None, "is_summary": False}
        log = load_json(os.path.join(dirpath, "log.json"), warnings) if has_log else None
        if isinstance(log, dict):
            unit["verdict"] = log.get("verdict") or log.get("verify_verdict")
            unit["severity"] = log.get("highest_severity") or log.get("max_severity")
            fc = log.get("findings_count")
            if fc is None and isinstance(log.get("findings"), list):
                fc = len(log["findings"])
            unit["findings_count"] = fc
            unit["outcome"] = log.get("outcome")
            unit["role"] = log.get("ai") or log.get("worker_ai") or log.get("verifier_ai")
            unit["start"] = parse_iso(log.get("started_at"))
            unit["end"] = parse_iso(log.get("ended_at"))
            if isinstance(log.get("duration_seconds"), (int, float)):
                unit["duration"] = float(log["duration_seconds"])
            elif unit["start"] and unit["end"]:
                unit["duration"] = (unit["end"] - unit["start"]).total_seconds()
            tb = tokens_from_log(log)
            tests = extract_tests(log)
            if tests:
                unit["tests"] = tests
            if tb:
                unit["tokens"] = tb
        if stream_name:
            nb, tc = usage_from_event_stream(os.path.join(dirpath, stream_name), warnings)
            unit["tool_calls"] = tc
            if nb:  # event stream wins for tokens (accurate)
                unit["tokens"] = nb
        units.append(unit)
    return units


def extract_tests(log):
    if not isinstance(log, dict):
        return None
    t = log.get("tests")
    out = {}
    if isinstance(t, dict):
        out = {k: t.get(k) for k in ("run", "failed", "skipped", "errors") if isinstance(t.get(k), int)}
    for k_src, k_dst in (("tests_run", "run"), ("tests_failed", "failed"),
                         ("tests_skipped", "skipped"), ("tests_errors", "errors")):
        if isinstance(log.get(k_src), int):
            out[k_dst] = log[k_src]
    return out or None


# ----------------------------------------------------------------------------- timing


def compute_timing(units, state, meta):
    # active: one contribution per (round, step_base), most-granular level, interval-union
    groups = {}
    for u in units:
        groups.setdefault((u["round"], u["step_base"]), []).append(u)
    active = 0.0
    for us in groups.values():
        per_repo = [u for u in us if u["repo"]]
        iters = [u for u in us if u["iteration"] and not u["repo"]]
        steps = [u for u in us if not u["iteration"] and not u["repo"]]
        level = per_repo or iters or steps
        intervals = [(u["start"], u["end"]) for u in level if u["start"] and u["end"]]
        if intervals:
            active += union_seconds(intervals)
        else:
            durs = [u["duration"] for u in level if u["duration"]]
            if durs:
                # per-repo run in parallel -> max; iters are sequential -> sum
                active += (max(durs) if per_repo else sum(durs))
    # elapsed from rounds
    elapsed = 0.0
    have_round_span = False
    all_ts = []
    for rd in (state.get("rounds") or []):
        s, e = parse_iso(rd.get("started_at")), parse_iso(rd.get("completed_at"))
        if s:
            all_ts.append(s)
        if e:
            all_ts.append(e)
        if s and e:
            elapsed += (e - s).total_seconds()
            have_round_span = True
    created = parse_iso(meta.get("created_at"))
    updated = parse_iso(state.get("updated_at"))
    for u in units:
        if u["start"]:
            all_ts.append(u["start"])
        if u["end"]:
            all_ts.append(u["end"])
    if created:
        all_ts.append(created)
    if updated:
        all_ts.append(updated)
    # run_started_at precedence
    round_starts = [parse_iso(rd.get("started_at")) for rd in (state.get("rounds") or [])]
    round_starts = [x for x in round_starts if x]
    unit_starts = [u["start"] for u in units if u["start"]]
    run_started = (min(round_starts) if round_starts else
                   created if created else
                   (min(unit_starts) if unit_starts else None))
    if not have_round_span:
        if run_started and updated:
            elapsed = (updated - run_started).total_seconds()
    if active and not have_round_span:
        method, conf = "step-sum", "high"
    elif active:
        method, conf = "step-sum", "high"
    elif have_round_span:
        method, conf = "round-span", "medium"
    elif run_started and updated:
        method, conf = "lifecycle", "low"
    else:
        method, conf = "unknown", "low"
    cal_start = min(all_ts) if all_ts else None
    cal_end = max(all_ts) if all_ts else None
    return {
        "active_seconds": round(active) if active else None,
        "elapsed_seconds": round(elapsed) if elapsed else None,
        "calendar_start": cal_start.isoformat() if cal_start else None,
        "calendar_end": cal_end.isoformat() if cal_end else None,
        "run_started_at": run_started.isoformat() if run_started else None,
        "time_method": method,
        "time_confidence": conf,
    }


# ----------------------------------------------------------------------------- status


def normalize_status(raw, outcome, stop_reason):
    raw_l = (raw or "").lower()
    # Some runs store `outcome` as an object (e.g. {"pr": …, "result": …}); flatten it to its
    # JSON text so the substring checks below still see "pr"/"result" markers — the malformed-file
    # contract is warn-don't-abort, so any non-string shape must degrade gracefully here.
    if outcome is not None and not isinstance(outcome, str):
        try:
            outcome = json.dumps(outcome)
        except (TypeError, ValueError):
            outcome = str(outcome)
    out_l = (outcome or "").lower()
    if "findings-only" in out_l or "findings_only" in out_l:
        return "success", "findings_only"
    if raw_l in ("completed",) and ("no pr" in out_l or "no code pr" in out_l):
        return "success", "completed_no_pr"
    if raw_l in ("pr_opened",) or "pr_opened" in out_l:
        return "success", "pr_opened"
    if raw_l == "completed":
        return "success", ("pr_opened" if "pr" in out_l else "completed")
    if raw_l.startswith("stopped") or stop_reason:
        return "stopped", (stop_reason or raw_l or "stopped")
    if raw_l in ("failed",) or "timeout" in raw_l or raw_l == "watchdog_timeout":
        return "failed", (stop_reason or raw_l)
    if raw_l in ("in_progress",) or raw_l.startswith("running"):
        return "in_progress", raw_l
    if raw_l in ("pending", "draft"):
        return "pending", raw_l
    if not raw_l:
        return "unknown", "(none)"
    return "unknown", raw_l


# ----------------------------------------------------------------------------- legacy state.yaml (best-effort)


def parse_state_yaml(path, warnings):
    out = {"status": None, "ticket_key": None, "pr_urls": [], "transitions": []}
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        warnings.append(f"legacy-read-error: {path} :: {exc}")
        return out
    m = re.search(r"^\s*ticket_key:\s*(\S+)", text, re.M)
    if m:
        out["ticket_key"] = m.group(1)
    m = re.search(r"^\s*status:\s*(\S+)", text, re.M)
    if m:
        out["status"] = m.group(1)
    out["pr_urls"] = re.findall(r"url:\s*(https://github\.com/\S+/pull/\d+)", text)
    out["transitions"] = re.findall(r"at:\s*([0-9T:\-\.\+Z]+)", text)
    return out


# ----------------------------------------------------------------------------- build one ExecutionRun


def jira_enrichment(run_dir, warnings):
    snap = os.path.join(run_dir, "source-snapshots")
    if not os.path.isdir(snap):
        return {}
    best = None
    for rd in sorted(os.listdir(snap)):
        fj = os.path.join(snap, rd, "fields.json")
        if os.path.isfile(fj):
            best = fj
    if not best:
        return {}
    d = load_json(best, warnings) or {}
    return {
        "priority": d.get("priority"),
        "fixVersions": d.get("fixVersions") or [],
        "labels": d.get("labels") or [],
        "jira_status": d.get("status"),
    }


def discover_timeline(run_dir):
    root = os.path.join(run_dir, "timeline.md")
    if os.path.isfile(root):
        return root
    cands = []
    for d in sorted(os.listdir(run_dir)) if os.path.isdir(run_dir) else []:
        if d.startswith("round-"):
            tp = os.path.join(run_dir, d, "timeline.md")
            if os.path.isfile(tp):
                cands.append((d, tp))
    if cands:
        cands.sort()
        return cands[-1][1]
    return None


def build_execution_run(run_dir, rtype, parent_id, warnings):
    name = os.path.basename(run_dir.rstrip(os.sep))
    rel_id = os.path.relpath(run_dir, str(RUNS_ROOT))  # unique across containers
    meta = load_json(os.path.join(run_dir, "00-meta.json"), warnings) or {}
    manifest = load_json(os.path.join(run_dir, "manifest.json"), warnings) or {}
    state = load_json(os.path.join(run_dir, "state.json"), warnings)
    legacy = None
    if state is None and os.path.isfile(os.path.join(run_dir, "state.yaml")):
        legacy = parse_state_yaml(os.path.join(run_dir, "state.yaml"), warnings)
        state = {"status": legacy["status"], "rounds": [], "updated_at": None,
                 "pr_urls": {}, "outcome": None}
    state = state or {}

    # metadata precedence: 00-meta -> manifest -> path-derived -> state
    sub = manifest.get("subtask") or {}
    parent_src = manifest.get("parent_source") or {}
    source_id = (meta.get("source_id") or sub.get("id") or (legacy or {}).get("ticket_key")
                 or ticket_key_from(name))
    title = meta.get("source_title") or sub.get("title") or ""
    source_url = meta.get("source_url") or sub.get("url") or parent_src.get("url") or ""
    scenario = meta.get("scenario") or manifest.get("scenario") or "unknown"
    repos = [r.get("id") for r in (meta.get("repos_in_scope") or [])] or \
            [r.get("id") for r in (manifest.get("repos") or [])]
    reviewer_backend = meta.get("reviewer_backend") or "unknown"
    # F8.5(b)/P9: the label comes from recorded metadata, never a hardcoded model name.
    reviewer_label = (meta.get("reviewer_model") or meta.get("reviewer_model_target")
                      or meta.get("reviewer_backend") or "(unrecorded)")
    review_mode = meta.get("review_mode") or state.get("review_mode") or "unknown"

    # PR urls
    pr_urls = []
    for src in (state.get("pr_urls"), meta.get("pr_urls")):
        if isinstance(src, dict):
            pr_urls.extend(src.values())
    if state.get("pr_url"):
        pr_urls.append(state["pr_url"])
    for rd in (state.get("rounds") or []):
        if rd.get("pr_url"):
            pr_urls.append(rd["pr_url"])
    if legacy:
        pr_urls.extend(legacy.get("pr_urls", []))
    pr_urls = sorted(set(u for u in pr_urls if u))

    status_raw = state.get("status")
    stop_reason = state.get("stop_reason")
    status_cat, status_sub = normalize_status(status_raw, state.get("outcome"), stop_reason)

    units = collect_units(run_dir, warnings)
    timing = compute_timing(units, state, meta)

    # token totals (reviewer accurate = event streams; worker estimate = estimate logs w/o stream)
    rev = {"input_total": 0, "input_cached": 0, "output": 0, "reasoning_output": 0}
    worker_est = {"input_total": 0, "output": 0}
    tool_calls = 0
    # mark step-level summary units that have token-bearing children
    by_group = {}
    for u in units:
        by_group.setdefault((u["round"], u["step_base"]), []).append(u)
    for us in by_group.values():
        children = [u for u in us if (u["iteration"] or u["repo"]) and u["tokens"]]
        for u in us:
            if not u["iteration"] and not u["repo"] and children and u["tokens"]:
                u["is_summary"] = True
    for u in units:
        tb = u["tokens"]
        tool_calls += u["tool_calls"] or 0
        if not tb or u["is_summary"]:
            continue
        if tb["accuracy"] == "accurate":
            for k in rev:
                rev[k] += tb.get(k, 0)
        elif tb["accuracy"] == "estimate":
            worker_est["input_total"] += tb.get("input_total", 0)
            worker_est["output"] += tb.get("output", 0)

    findings_caught = sum((u["findings_count"] or 0) for u in units
                          if u["role"] in (None,) or True)  # count from reviewer logs below
    # findings from reviewer units only (verdict present)
    findings_caught = sum((u["findings_count"] or 0) for u in units if u["verdict"])
    verdicts = [u["verdict"] for u in units if u["verdict"]]
    # also pull verdicts from state rounds
    for rd in (state.get("rounds") or []):
        for k in ("step_2_verdict", "step_5_verdict", "step_8_verdict"):
            if rd.get(k):
                verdicts.append(rd[k])

    commits = []
    for rd in (state.get("rounds") or []):
        commits.extend(rd.get("commits") or [])
    commits = [c for c in commits if c]

    # tests aggregate
    tests_total = {"run": 0, "failed": 0, "skipped": 0, "errors": 0}
    tests_seen = False
    for u in units:
        if u["tests"]:
            tests_seen = True
            for k in tests_total:
                if isinstance(u["tests"].get(k), int):
                    tests_total[k] += u["tests"][k]

    # first-pass metrics (per round, from state step_*_noop)
    rounds_meta = []
    for rd in (state.get("rounds") or []):
        noops = {k: rd.get(k) for k in ("step_3_noop", "step_6_noop", "step_9_noop") if k in rd}
        applicable = [v for v in noops.values() if v is not None]
        approved_no_rework = bool(applicable) and all(applicable)
        rework_present = any(v is False for v in applicable)
        rounds_meta.append({
            "round": rd.get("round"),
            "status": rd.get("status"),
            "stop_reason": rd.get("stop_reason"),
            "approved_no_rework": approved_no_rework,
            "rework_present": rework_present,
            "commits": rd.get("commits") or [],
        })

    iters_max = 0
    for u in units:
        if isinstance(u["iteration"], int):
            iters_max = max(iters_max, u["iteration"])

    return {
        "id": rel_id,
        "label": name,
        "type": rtype,
        "parent_container_id": parent_id,
        "source_id": source_id,
        "title": title,
        "source_url": source_url,
        "scenario": scenario,
        "repos": repos,
        "reviewer_backend": reviewer_backend,
        "reviewer_label": reviewer_label,
        "review_mode": review_mode,
        "jira": jira_enrichment(run_dir, warnings),
        "status_cat": status_cat,
        "status_sub": status_sub,
        "status_raw": status_raw,
        "outcome": state.get("outcome"),
        "stop_reason": stop_reason,
        "rounds": rounds_meta,
        "n_rounds": len(rounds_meta) or (1 if units else 0),
        "max_iter": iters_max,
        "pr_urls": pr_urls,
        "timing": timing,
        "reviewer_tokens": rev,
        "worker_tokens_est": worker_est,
        "tool_calls": tool_calls,
        "findings_caught": findings_caught,
        "verdicts": verdicts,
        "commits": commits,
        "tests": tests_total if tests_seen else None,
        "n_units": len(units),
        "timeline_path": discover_timeline(run_dir),
        "run_dir": os.path.relpath(run_dir, RUNS_ROOT.parent),
    }


# ----------------------------------------------------------------------------- discovery


def discover(runs_root, include_archived, include_legacy, warnings):
    containers, runs = [], []
    seen = set()

    def add_run(path, rtype, parent):
        rp = os.path.realpath(path)
        if rp in seen:
            return None
        seen.add(rp)
        r = build_execution_run(path, rtype, parent, warnings)
        runs.append(r)
        return r

    top = sorted(os.listdir(runs_root))
    for entry in top:
        path = os.path.join(runs_root, entry)
        if not os.path.isdir(path) or entry.startswith("."):
            continue
        if entry == "_archived":
            if include_archived:
                _discover_archived(path, containers, add_run, warnings)
            continue
        if entry == "jira":
            if include_legacy:
                _discover_legacy(path, add_run)
            continue
        if entry.startswith("batch--"):
            containers.append(_container(path, "batch", warnings))
            tickets_dir = os.path.join(path, "tickets")
            if os.path.isdir(tickets_dir):
                for k in sorted(os.listdir(tickets_dir)):
                    kp = os.path.join(tickets_dir, k)
                    if os.path.isdir(kp) and not k.startswith("."):
                        r = add_run(kp, "batch-child", entry)
                        if r:
                            containers[-1]["child_run_ids"].append(r["id"])
            continue
        # direct vs epic
        if os.path.isfile(os.path.join(path, ".spawned-by-epic-planner")):
            containers.append(_container(path, "epic", warnings))
            subs = os.path.join(path, "subtasks")
            if os.path.isdir(subs):
                for k in sorted(os.listdir(subs)):
                    kp = os.path.join(subs, k)
                    if os.path.isdir(kp) and not k.startswith(".") and (
                        os.path.isfile(os.path.join(kp, "state.json")) or
                        os.path.isfile(os.path.join(kp, "manifest.json"))
                    ):
                        r = add_run(kp, "epic-subtask", entry)
                        if r:
                            containers[-1]["child_run_ids"].append(r["id"])
            continue
        # plain direct run
        if (os.path.isfile(os.path.join(path, "00-meta.json")) or
                os.path.isfile(os.path.join(path, "state.json"))):
            add_run(path, "direct", None)
    return containers, runs


def _container(path, ctype, warnings):
    name = os.path.basename(path.rstrip(os.sep))
    meta = load_json(os.path.join(path, "00-meta.json"), warnings) or {}
    state = load_json(os.path.join(path, "state.json"), warnings) or {}
    return {
        "id": name, "type": ctype, "status": state.get("status"),
        "child_run_ids": [],
        "created_at": meta.get("created_at"),
        "updated_at": state.get("updated_at"),
        "ticket_keys": meta.get("ticket_keys") or list((meta.get("scenarios") or {}).keys()),
        "pr_urls": list((state.get("pr_urls") or {}).values()),
    }


def _discover_archived(arch_root, containers, add_run, warnings):
    for entry in sorted(os.listdir(arch_root)):
        path = os.path.join(arch_root, entry)
        if not os.path.isdir(path) or entry.startswith("."):
            continue
        if entry.startswith("batch--"):
            containers.append(_container(path, "batch", warnings))
            containers[-1]["id"] = "_archived/" + containers[-1]["id"]
            tickets_dir = os.path.join(path, "tickets")
            if os.path.isdir(tickets_dir):
                for k in sorted(os.listdir(tickets_dir)):
                    kp = os.path.join(tickets_dir, k)
                    if os.path.isdir(kp) and not k.startswith("."):
                        r = add_run(kp, "archived", "_archived/" + entry)
                        if r:
                            r["archived"] = True


def _discover_legacy(jira_root, add_run):
    for key in sorted(os.listdir(jira_root)):
        kp = os.path.join(jira_root, key)
        if not os.path.isdir(kp) or key.startswith("."):
            continue
        for stamp in sorted(os.listdir(kp)):
            sp = os.path.join(kp, stamp)
            if os.path.isdir(sp) and not stamp.startswith("."):
                r = add_run(sp, "legacy-attempt", None)
                if r:
                    r["legacy"] = True
                    if not r["source_id"]:
                        r["source_id"] = ticket_key_from(key)


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


# ----------------------------------------------------------------------------- HTML


def render_html(report):
    data_json = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    title = "Issue2PR Runs — Statistics Report"
    return (HTML_SHELL.replace("__CHART_BUNDLE__", chart_bundle())
            .replace("__TITLE__", html.escape(title)).replace("__DATA__", data_json))


HTML_SHELL = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__TITLE__</title>
<script>__CHART_BUNDLE__</script>
<script>try{var _t=localStorage.getItem('runs-stats-theme');if(_t==='light'||_t==='dark')document.documentElement.setAttribute('data-theme',_t);}catch(e){}</script>
<style>
/* Dark is the default (also used when the OS expresses no preference). */
:root{
 --bg:#0f1419;--card:#1a2029;--ink:#e6edf3;--mut:#8b97a6;--line:#2a323d;
 --hover:#20262f;--input:#0d1117;--pre:#0b0e12;--drill:#11161d;--badge-ink:#0b0e12;--on-ink:#08111f;
 --green:#3fb950;--teal:#39c5cf;--amber:#d29922;--red:#f85149;--blue:#58a6ff;--grey:#6e7681;--slate:#7d8590;
 --frozen-bg:#3a2d12;--frozen-ink:#f0c674;}
/* Light theme — auto when the OS is light AND no manual override is active. */
@media (prefers-color-scheme: light){:root:not([data-theme]){
 --bg:#f6f8fa;--card:#ffffff;--ink:#1f2328;--mut:#656d76;--line:#d0d7de;
 --hover:#eef1f4;--input:#ffffff;--pre:#f6f8fa;--drill:#f7f9fb;--badge-ink:#ffffff;--on-ink:#ffffff;
 --green:#1a7f37;--teal:#0a7c86;--amber:#9a6700;--red:#cf222e;--blue:#0969da;--grey:#6e7781;--slate:#57606a;
 --frozen-bg:#fff8e6;--frozen-ink:#7a5c00;}}
/* Manual override via the toggle button — wins over the OS setting. (data-theme="dark" falls back to the :root dark defaults.) */
:root[data-theme="light"]{
 --bg:#f6f8fa;--card:#ffffff;--ink:#1f2328;--mut:#656d76;--line:#d0d7de;
 --hover:#eef1f4;--input:#ffffff;--pre:#f6f8fa;--drill:#f7f9fb;--badge-ink:#ffffff;--on-ink:#ffffff;
 --green:#1a7f37;--teal:#0a7c86;--amber:#9a6700;--red:#cf222e;--blue:#0969da;--grey:#6e7781;--slate:#57606a;
 --frozen-bg:#fff8e6;--frozen-ink:#7a5c00;}
.theme-btn{position:fixed;top:12px;right:14px;z-index:60;display:inline-flex;align-items:center;gap:6px;
 background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:18px;padding:5px 12px;
 font:inherit;font-size:12px;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.3)}
.theme-btn:hover{border-color:var(--blue)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
 font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
header{padding:22px 26px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,var(--card),var(--bg))}
h1{margin:0 0 4px;font-size:20px}.sub{color:var(--mut);font-size:12px}
.wrap{padding:18px 26px;max-width:1500px;margin:0 auto}
.kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin:6px 0 18px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi .n{font-size:22px;font-weight:700}.kpi .l{color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.kpi .x{color:var(--mut);font-size:11px;margin-top:2px}
.frozen-banner{background:var(--frozen-bg);border:1px solid var(--amber);border-radius:10px;padding:8px 12px;margin:8px 0;color:var(--frozen-ink)}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
section h2{margin:0 0 12px;font-size:15px}
.grid{display:grid;gap:16px}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:1000px){.g2,.g3,.g4{grid-template-columns:1fr}}
.chartbox{position:relative;min-height:230px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;cursor:pointer;user-select:none;position:sticky;top:0;background:var(--card)}
tbody tr:hover{background:var(--hover)}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;font-weight:600;color:var(--badge-ink)}
.b-success{background:var(--green)}.b-stopped{background:var(--amber)}.b-failed{background:var(--red)}
.b-in_progress{background:var(--blue)}.b-pending{background:var(--grey);color:#fff}.b-unknown{background:var(--slate);color:#fff}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.right{text-align:right}.mut{color:var(--mut)}.small{font-size:12px}
.drill{background:var(--drill);border:1px dashed var(--line);border-radius:8px;padding:10px;margin:6px 0}
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:10px;flex-wrap:wrap}
input[type=search]{background:var(--input);border:1px solid var(--line);color:var(--ink);border-radius:8px;padding:7px 10px;min-width:230px}
.chip{border:1px solid var(--line);background:var(--input);color:var(--mut);border-radius:16px;padding:3px 10px;font-size:12px;cursor:pointer}
.chip.on{background:var(--blue);color:var(--on-ink);border-color:var(--blue)}
pre.tl{white-space:pre-wrap;background:var(--pre);border:1px solid var(--line);border-radius:6px;padding:10px;max-height:380px;overflow:auto;font-size:12px}
.warn{color:var(--amber)}.expander{cursor:pointer;color:var(--blue)}
.flag{font-size:10px;padding:1px 6px;border:1px solid var(--line);border-radius:10px;color:var(--mut);margin-left:6px}
</style></head>
<body>
<button id="theme-btn" class="theme-btn" title="Theme — click to cycle Auto / Light / Dark"></button>
<header><h1>__TITLE__</h1><div class="sub" id="freshness"></div></header>
<div class="wrap" id="app"></div>
<script id="report-data" type="application/json">__DATA__</script>
<script>
const R = JSON.parse(document.getElementById('report-data').textContent);
const esc = s => (s==null?'':String(s)).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const PAL = {success:'#3fb950',stopped:'#d29922',failed:'#f85149',in_progress:'#58a6ff',pending:'#6e7681',unknown:'#7d8590'};
const fmtDur = s => { if(s==null) return '—'; s=Math.round(s); const h=Math.floor(s/3600),m=Math.floor(s%3600/60),x=s%60;
  return h?`${h}h ${m}m`:(m?`${m}m ${x}s`:`${x}s`); };
const fmtK = n => n==null?'—':(n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(1)+'k':String(n));
const sum = a => a.reduce((x,y)=>x+y,0);
// Charts read their text/grid colors from the active CSS theme (light or dark) so they match the page.
const cssVar = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function applyChartTheme(){ Chart.defaults.color = cssVar('--mut'); Chart.defaults.borderColor = cssVar('--line'); }
applyChartTheme();
// Manual theme override (top-right button), persisted; 'auto' follows the OS.
const THEME_KEY='runs-stats-theme', THEME_SEQ=['auto','light','dark'], THEME_LABEL={auto:'🖥 Auto',light:'☀ Light',dark:'🌙 Dark'};
function storedTheme(){try{const v=localStorage.getItem(THEME_KEY);return (v==='light'||v==='dark')?v:'auto';}catch(e){return 'auto';}}
function setTheme(mode){
  try{ mode==='auto'?localStorage.removeItem(THEME_KEY):localStorage.setItem(THEME_KEY,mode); }catch(e){}
  const root=document.documentElement;
  if(mode==='auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme',mode);
  const btn=document.getElementById('theme-btn'); if(btn) btn.textContent=THEME_LABEL[mode];
  applyChartTheme(); charts.forEach(c=>{try{c.update()}catch(e){}});
}

function kpi(n,l,x){return `<div class="kpi"><div class="n">${n}</div><div class="l">${esc(l)}</div>${x?`<div class="x">${esc(x)}</div>`:''}</div>`;}

function statusBadge(cat,sub){return `<span class="badge b-${cat}">${esc(cat)}</span>${sub&&sub!=cat?` <span class="mut small">${esc(sub)}</span>`:''}`;}

let charts=[];
function donut(id,obj){const ctx=document.getElementById(id);if(!ctx)return;
  const labels=Object.keys(obj),vals=labels.map(k=>obj[k]);
  charts.push(new Chart(ctx,{type:'doughnut',data:{labels,datasets:[{data:vals,
   backgroundColor:labels.map(l=>PAL[l]||'#58a6ff')}]},options:{plugins:{legend:{position:'right'}}}}));}
function bar(id,obj,color){const ctx=document.getElementById(id);if(!ctx)return;
  const labels=Object.keys(obj),vals=labels.map(k=>obj[k]);
  charts.push(new Chart(ctx,{type:'bar',data:{labels,datasets:[{data:vals,backgroundColor:color||'#58a6ff'}]},
   options:{plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}}}));}

function render(){
  const a=R.aggregates, runs=R.runs, tickets=R.tickets;
  const b=R.bucket||{};
  const scope = b.label ? `<b>${esc(b.label)}</b>${b.window?` (${esc(b.window)}, ${esc(R.tz||'UTC')})`:''} · ` : '';
  document.getElementById('freshness').innerHTML =
    scope + `generated ${esc(R.generated_at)}${R.as_of&&R.as_of!=R.generated_at?` · as_of ${esc(R.as_of)}`:''} · `+
    `runs root <span class="mono">${esc(R.runs_root)}</span> · filters: ${esc(R.filters)} · `+
    `<span class="${R.warnings.length?'warn':''}">${R.warnings.length} parse warning(s)</span>`;
  const app=document.getElementById('app');
  if(b.frozen){const fb=document.createElement('div');fb.className='frozen-banner';
    fb.innerHTML=`❄ <b>Archived snapshot</b> for ${esc(b.label)} — frozen as of ${esc(R.as_of||R.generated_at)}. `+
      `The source may have changed since; run <span class="mono">--force-regenerate --period ${esc(b.id)}</span> to refresh.`;
    app.appendChild(fb);}
  const nTickets=tickets.length, nRuns=runs.length;
  const rt=a.reviewer_tokens, wt=a.worker_tokens_est;
  let h='';
  h+=`<div class="kpis">
    ${kpi(nTickets,'Tasks (tickets)',`${nRuns} runs · ${(nRuns/Math.max(nTickets,1)).toFixed(1)}/ticket`)}
    ${kpi(a.status_dist.success||0,'Success')}
    ${kpi((a.status_dist.stopped||0),'Stopped')}
    ${kpi((a.status_dist.failed||0),'Failed')}
    ${kpi(fmtK(rt.input_total+rt.output),'Reviewer tokens',`accurate · ${(100*rt.input_cached/Math.max(rt.input_total,1)).toFixed(0)}% cached`)}
    ${kpi('≈'+fmtK(wt.input_total+wt.output),'Worker tokens','estimate')}
    ${kpi(fmtDur(a.active_total),'Active time',`median ${fmtDur(a.active_median)}`)}
    ${kpi(a.prs.length,'PRs opened')}
    ${kpi(a.commits,'Commits')}
    ${kpi(a.findings,'Findings caught')}
    ${kpi(a.tool_calls,'Reviewer tool calls')}
  </div>`;

  h+=`<section><h2>Status &amp; composition</h2><div class="grid g4">
    <div><div class="mut small">Status</div><div class="chartbox"><canvas id="c_status"></canvas></div></div>
    <div><div class="mut small">Scenario</div><div class="chartbox"><canvas id="c_scn"></canvas></div></div>
    <div><div class="mut small">Repo</div><div class="chartbox"><canvas id="c_repo"></canvas></div></div>
    <div><div class="mut small">Reviewer backend</div><div class="chartbox"><canvas id="c_bk"></canvas></div></div>
  </div></section>`;

  h+=`<section><h2>Throughput over time</h2><div class="chartbox"><canvas id="c_day"></canvas></div></section>`;

  // ticket table
  h+=`<section><h2>Tasks (${nTickets})</h2>
   <div class="toolbar"><input type="search" id="q" placeholder="filter tickets…"/>
     <span id="chips"></span></div>
   <div style="overflow:auto;max-height:640px"><table id="ttab"><thead><tr>
     <th data-k="key">Ticket</th><th data-k="title">Title</th><th data-k="scenario">Scenario</th>
     <th data-k="status">Status</th><th data-k="attempts" class="right">Att.</th>
     <th data-k="active" class="right">Active</th><th data-k="elapsed" class="right">Elapsed</th>
     <th data-k="revtok" class="right">Rev tok</th><th data-k="wtok" class="right">Wkr tok≈</th>
     <th data-k="findings" class="right">Find.</th><th data-k="tests">Tests</th>
     <th data-k="commits" class="right">Cmts</th><th>PR(s)</th></tr></thead><tbody id="tbody"></tbody></table></div>
   </section>`;

  // tokens & cost
  h+=`<section><h2>Tokens &amp; cost</h2>
    <div class="grid g2">
     <div><div class="mut small">Reviewer tokens per run (stacked)</div><div class="chartbox"><canvas id="c_tok"></canvas></div></div>
     <div><div class="mut small">Cost</div><div id="cost" class="small"></div></div>
    </div></section>`;

  // review quality
  h+=`<section><h2>Review quality</h2><div class="grid g2">
     <div><div class="mut small">Verdict distribution</div><div class="chartbox"><canvas id="c_verdict"></canvas></div></div>
     <div class="small">
      <p><b>Approved without rework:</b> ${a.approved_no_rework} round(s) — reviewer required no changes.</p>
      <p><b>Rework converged in one iteration:</b> ${a.rework_one_iter} round(s).</p>
      <p><b>Multi-round runs:</b> ${a.multi_round}.</p>
      <p class="mut">Findings caught total: ${a.findings}. Reviewer tokens / finding:
         ${a.findings?fmtK(Math.round((rt.input_total+rt.output)/a.findings)):'—'}.</p>
     </div></div></section>`;

  // reliability
  h+=`<section><h2>Reliability</h2><div class="grid g2">
     <div><div class="mut small">Stop reasons</div><div class="chartbox"><canvas id="c_stop"></canvas></div></div>
     <div class="small">
       <p><b>Tests</b> (coverage: ${a.tests_coverage_runs}/${nRuns} runs recorded test data):
        ${a.tests.run} run · ${a.tests.failed} failed · ${a.tests.errors} errors · ${a.tests.skipped} skipped.</p>
       <p class="mut">Metrics show data-coverage because many logs omit these fields; absent ≠ zero.</p>
     </div></div></section>`;

  // containers
  if(R.containers.length){
    h+=`<section><h2>Containers (batch / epic) — not counted as tasks</h2>
      <table><thead><tr><th>Container</th><th>Type</th><th>Status</th><th>Children</th><th>Tickets</th></tr></thead><tbody>`;
    R.containers.forEach(c=>{h+=`<tr><td class="mono small">${esc(c.id)}</td><td>${esc(c.type)}</td>
      <td>${esc(c.status||'—')}</td><td class="right">${c.child_run_ids.length}</td>
      <td class="small mut">${esc((c.ticket_keys||[]).join(', '))}</td></tr>`;});
    h+=`</tbody></table></section>`;
  }

  // data quality
  h+=`<section><h2>Data quality</h2><div class="small">
     <p>${R.warnings.length} parse warning(s). Manifest-only runs and legacy attempts are parsed via fallbacks.</p>
     ${R.warnings.length?`<details><summary class="expander">show warnings</summary><pre class="tl">${esc(R.warnings.join('\n'))}</pre></details>`:''}
     <p class="mut">Token provenance: reviewer = accurate (codex-reported event streams); worker = ≈ estimate (file-size). Active time de-duplicated across step/iter/per-repo so repeated durations are not multiplied.</p>
   </div></section>`;

  app.innerHTML=h;

  // charts
  donut('c_status',a.status_dist);
  bar('c_scn',a.scenario_dist,'#39c5cf');
  bar('c_repo',a.repo_dist,'#a371f7');
  bar('c_bk',a.backend_dist,'#58a6ff');
  // throughput
  const days=Object.keys(a.per_day).sort();
  const dctx=document.getElementById('c_day');
  charts.push(new Chart(dctx,{data:{labels:days,datasets:[
    {type:'bar',label:'runs',data:days.map(d=>a.per_day[d].runs),backgroundColor:'#3fb950',yAxisID:'y'},
    {type:'line',label:'reviewer tokens',data:days.map(d=>a.per_day[d].reviewer_tokens),borderColor:'#d29922',yAxisID:'y1',tension:.25}
  ]},options:{scales:{
    y:{position:'left',beginAtZero:true},
    y1:{position:'right',grid:{drawOnChartArea:false},beginAtZero:true}}}}));
  // tokens per run stacked
  const rr=runs.slice().sort((x,y)=>(y.reviewer_tokens.input_total+y.reviewer_tokens.output)-(x.reviewer_tokens.input_total+x.reviewer_tokens.output)).slice(0,18);
  charts.push(new Chart(document.getElementById('c_tok'),{type:'bar',data:{labels:rr.map(r=>r.source_id||r.id),datasets:[
    {label:'input (uncached)',data:rr.map(r=>r.reviewer_tokens.input_total-r.reviewer_tokens.input_cached),backgroundColor:'#1f6feb'},
    {label:'cached',data:rr.map(r=>r.reviewer_tokens.input_cached),backgroundColor:'#388bfd55'},
    {label:'output',data:rr.map(r=>r.reviewer_tokens.output),backgroundColor:'#3fb950'},
    {label:'reasoning',data:rr.map(r=>r.reviewer_tokens.reasoning_output),backgroundColor:'#d29922'}]},
   options:{scales:{x:{stacked:true},y:{stacked:true}}}}));
  bar('c_verdict',a.verdict_dist,'#39c5cf');
  bar('c_stop',a.stop_reasons,'#f85149');

  // cost
  const cost=document.getElementById('cost');
  if(R.reviewer_rate){const rate=R.reviewer_rate;
    const c=(rt.input_uncached||rt.input_total-rt.input_cached)/1e6*(rate.input||0)
      + rt.input_cached/1e6*(rate.cached_input!=null?rate.cached_input:(rate.input||0))
      + rt.output/1e6*(rate.output||0) + rt.reasoning_output/1e6*(rate.reasoning!=null?rate.reasoning:(rate.output||0));
    cost.innerHTML=`<div class="kpi"><div class="n">$${c.toFixed(2)}</div><div class="l">estimated reviewer cost</div>
      <div class="x">rate $/1M: in ${rate.input}, cached ${rate.cached_input??'~in'}, out ${rate.output}, reason ${rate.reasoning??'~out'}</div></div>`;
  } else {
    cost.innerHTML=`<p class="mut">Cost estimation is off. Pass <span class="mono">--reviewer-rate input=&lt;n&gt;,output=&lt;n&gt;[,cached_input=&lt;n&gt;,reasoning=&lt;n&gt;]</span> to enable a $ estimate. Reviewer tokens total: in ${fmtK(rt.input_total)} (${fmtK(rt.input_cached)} cached), out ${fmtK(rt.output)}, reasoning ${fmtK(rt.reasoning_output)}.</p>`;
  }

  // ticket table
  const runById={};runs.forEach(r=>runById[r.id]=r);
  const rows=tickets.map(t=>{
    const hr=runById[t.headline_run_id]||{};
    const tk=t.run_ids.map(id=>runById[id]).filter(Boolean);
    const revtok=sum(tk.map(r=>r.reviewer_tokens.input_total+r.reviewer_tokens.output));
    const wtok=sum(tk.map(r=>r.worker_tokens_est.input_total+r.worker_tokens_est.output));
    const active=sum(tk.map(r=>r.timing.active_seconds||0));
    const elapsed=sum(tk.map(r=>r.timing.elapsed_seconds||0));
    const findings=sum(tk.map(r=>r.findings_caught));
    const commits=sum(tk.map(r=>r.commits.length));
    const tests=tk.find(r=>r.tests)?tk.filter(r=>r.tests).reduce((o,r)=>({run:o.run+(r.tests.run||0),failed:o.failed+(r.tests.failed||0)}),{run:0,failed:0}):null;
    const rounds=sum(tk.map(r=>r.n_rounds));
    return {t,hr,tk,revtok,wtok,active,elapsed,findings,commits,tests,rounds};
  });

  let sortK='revtok',sortDir=-1,activeCats=new Set();
  const cats=[...new Set(tickets.map(t=>t.headline_status_cat))];
  document.getElementById('chips').innerHTML=cats.map(c=>`<span class="chip on" data-c="${c}">${c}</span>`).join('');
  cats.forEach(c=>activeCats.add(c));
  document.querySelectorAll('#chips .chip').forEach(ch=>ch.onclick=()=>{const c=ch.dataset.c;
    if(activeCats.has(c)){activeCats.delete(c);ch.classList.remove('on');}else{activeCats.add(c);ch.classList.add('on');}draw();});

  function val(row,k){switch(k){case 'key':return row.t.key;case 'title':return row.t.title;
    case 'scenario':return row.t.scenario;case 'status':return row.t.headline_status_cat;
    case 'attempts':return row.t.attempt_count;case 'active':return row.active;case 'elapsed':return row.elapsed;
    case 'revtok':return row.revtok;case 'wtok':return row.wtok;case 'findings':return row.findings;
    case 'tests':return row.tests?row.tests.run:-1;case 'commits':return row.commits;default:return '';}}

  function draw(){
    const q=(document.getElementById('q').value||'').toLowerCase();
    let rs=rows.filter(r=>activeCats.has(r.t.headline_status_cat) &&
      (!q || (r.t.key+' '+r.t.title+' '+r.t.scenario).toLowerCase().includes(q)));
    rs.sort((x,y)=>{const a=val(x,sortK),b=val(y,sortK);return (a>b?1:a<b?-1:0)*sortDir;});
    const tb=document.getElementById('tbody');
    tb.innerHTML=rs.map((r,i)=>{
      const t=r.t;
      const prs=t.pr_urls.map(u=>`<a href="${esc(u)}" target="_blank">#${esc((u.match(/\/pull\/(\d+)/)||[])[1]||'PR')}</a>`).join(' ');
      return `<tr class="trow" data-i="${i}">
        <td><a href="${esc(t.source_url||'#')}" target="_blank">${esc(t.key)}</a></td>
        <td class="small">${esc(t.title)}</td><td class="small">${esc(t.scenario)}</td>
        <td>${statusBadge(t.headline_status_cat,t.headline_status_sub)}</td>
        <td class="right">${t.attempt_count}</td>
        <td class="right small">${fmtDur(r.active)}</td><td class="right small">${fmtDur(r.elapsed)}</td>
        <td class="right">${fmtK(r.revtok)}</td><td class="right mut">≈${fmtK(r.wtok)}</td>
        <td class="right">${r.findings}</td>
        <td class="small">${r.tests?`${r.tests.run}/${r.tests.failed}f`:'<span class="mut">n/a</span>'}</td>
        <td class="right">${r.commits}</td><td class="small">${prs||'<span class="mut">—</span>'}</td></tr>
       <tr class="drillrow" data-i="${i}" style="display:none"><td colspan="13"><div class="drill" id="d${i}"></div></td></tr>`;
    }).join('');
    document.querySelectorAll('.trow').forEach(tr=>tr.onclick=()=>{
      const i=tr.dataset.i;const dr=document.querySelector(`.drillrow[data-i="${i}"]`);
      if(dr.style.display==='none'){dr.style.display='';buildDrill(rs[i],document.getElementById('d'+i));}
      else dr.style.display='none';});
  }
  document.getElementById('q').oninput=draw;
  document.querySelectorAll('#ttab th[data-k]').forEach(th=>th.onclick=()=>{
    const k=th.dataset.k;if(sortK===k)sortDir*=-1;else{sortK=k;sortDir=(k==='key'||k==='title'||k==='scenario'||k==='status')?1:-1;}draw();});
  draw();

  function buildDrill(row,el){
    let h=`<div class="small mut">${row.tk.length} run(s) for ${esc(row.t.key)}:</div>`;
    row.tk.forEach(r=>{
      h+=`<div style="margin:8px 0;padding:8px;border:1px solid var(--line);border-radius:6px">
        <b class="mono">${esc(r.id)}</b> ${statusBadge(r.status_cat,r.status_sub)}
        <span class="flag">${esc(r.type)}</span>${r.archived?'<span class="flag">archived</span>':''}${r.legacy?'<span class="flag">legacy</span>':''}
        <div class="small mut" style="margin-top:4px">
          rounds ${r.n_rounds} · active ${fmtDur(r.timing.active_seconds)} (${esc(r.timing.time_method)}/${esc(r.timing.time_confidence)}) ·
          elapsed ${fmtDur(r.timing.elapsed_seconds)} · reviewer ${fmtK(r.reviewer_tokens.input_total+r.reviewer_tokens.output)} tok ·
          worker ≈${fmtK(r.worker_tokens_est.input_total+r.worker_tokens_est.output)} · tool calls ${r.tool_calls} ·
          reviewer ${esc(r.reviewer_label)} · mode ${esc(r.review_mode)} ·
          findings ${r.findings_caught}${r.stop_reason?' · stop: '+esc(r.stop_reason):''}</div>
        ${r.verdicts.length?`<div class="small">verdicts: ${r.verdicts.map(esc).join(', ')}</div>`:''}
        ${(r.jira&&r.jira.priority)?`<div class="small mut">priority ${esc(r.jira.priority)} · fixVersions ${esc((r.jira.fixVersions||[]).join(', '))}</div>`:''}
        ${r.timeline?`<details><summary class="expander small">timeline</summary><pre class="tl">${esc(r.timeline)}</pre></details>`:'<div class="small mut">timeline unavailable</div>'}
      </div>`;
    });
    el.innerHTML=h;
  }
}
render();
// Follow live OS light/dark switches (only matters in Auto): CSS re-themes the page; re-tint charts too.
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{
  applyChartTheme(); charts.forEach(c=>{ try{ c.update() }catch(e){} });});
// Wire the top-right toggle: apply the saved mode, then cycle Auto → Light → Dark on click.
(function(){ const btn=document.getElementById('theme-btn'); setTheme(storedTheme());
  if(btn) btn.onclick=()=>setTheme(THEME_SEQ[(THEME_SEQ.indexOf(storedTheme())+1)%THEME_SEQ.length]); })();
</script>
</body></html>
"""


# ----------------------------------------------------------------------------- main

RUNS_ROOT = None


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


# ----------------------------------------------------------------------------- report builder


def build_one_report(subset_runs, all_containers, bucket_meta, out_path, as_of, tz,
                     reviewer_rate, runs_root, warnings, period_page):
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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(report), encoding="utf-8")
    return ticket_rows, aggr


# ----------------------------------------------------------------------------- history.json + index.html


def load_history(path):
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def render_index(history, reports_dir):
    title = "Issue2PR Runs — Report Index"
    data_json = json.dumps(history, ensure_ascii=False).replace("</", "<\\/")
    return (INDEX_SHELL.replace("__CHART_BUNDLE__", chart_bundle())
            .replace("__TITLE__", html.escape(title)).replace("__DATA__", data_json))


INDEX_SHELL = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__TITLE__</title>
<script>__CHART_BUNDLE__</script>
<script>try{var _t=localStorage.getItem('runs-stats-theme');if(_t==='light'||_t==='dark')document.documentElement.setAttribute('data-theme',_t);}catch(e){}</script>
<style>
:root{--bg:#0f1419;--card:#1a2029;--ink:#e6edf3;--mut:#8b97a6;--line:#2a323d;--green:#3fb950;--amber:#d29922;--red:#f85149;--blue:#58a6ff}
@media (prefers-color-scheme: light){:root:not([data-theme]){--bg:#f6f8fa;--card:#ffffff;--ink:#1f2328;--mut:#656d76;--line:#d0d7de;--green:#1a7f37;--amber:#9a6700;--red:#cf222e;--blue:#0969da}}
:root[data-theme="light"]{--bg:#f6f8fa;--card:#ffffff;--ink:#1f2328;--mut:#656d76;--line:#d0d7de;--green:#1a7f37;--amber:#9a6700;--red:#cf222e;--blue:#0969da}
.theme-btn{position:fixed;top:12px;right:14px;z-index:60;display:inline-flex;align-items:center;gap:6px;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:18px;padding:5px 12px;font:inherit;font-size:12px;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.3)}
.theme-btn:hover{border-color:var(--blue)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
header{padding:22px 26px;border-bottom:1px solid var(--line)}h1{margin:0 0 4px;font-size:20px}.sub{color:var(--mut);font-size:12px}
.wrap{padding:18px 26px;max-width:1300px;margin:0 auto}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
section h2{margin:0 0 12px;font-size:15px}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600}.right{text-align:right}.mut{color:var(--mut)}.mono{font-family:ui-monospace,Menlo,monospace}
.chartbox{position:relative;height:240px}.frozen{color:var(--amber)}.cur{color:var(--green)}
</style></head>
<body>
<button id="theme-btn" class="theme-btn" title="Theme — click to cycle Auto / Light / Dark"></button>
<header><h1>__TITLE__</h1><div class="sub" id="sub"></div></header>
<div class="wrap" id="app"></div>
<script id="hist" type="application/json">__DATA__</script>
<script>
const H=JSON.parse(document.getElementById('hist').textContent);
const cssVar=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function applyChartTheme(){Chart.defaults.color=cssVar('--mut');Chart.defaults.borderColor=cssVar('--line');}
applyChartTheme();
// Manual theme override (top-right button), persisted; 'auto' follows the OS.
const THEME_KEY='runs-stats-theme', THEME_SEQ=['auto','light','dark'], THEME_LABEL={auto:'🖥 Auto',light:'☀ Light',dark:'🌙 Dark'};
function storedTheme(){try{const v=localStorage.getItem(THEME_KEY);return (v==='light'||v==='dark')?v:'auto';}catch(e){return 'auto';}}
function setTheme(mode){
  try{ mode==='auto'?localStorage.removeItem(THEME_KEY):localStorage.setItem(THEME_KEY,mode); }catch(e){}
  const root=document.documentElement;
  if(mode==='auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme',mode);
  const btn=document.getElementById('theme-btn'); if(btn) btn.textContent=THEME_LABEL[mode];
  applyChartTheme(); if(typeof trendChart!=='undefined'){try{trendChart.update()}catch(e){}}
}
const esc=s=>(s==null?'':String(s)).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtK=n=>n==null?'—':(n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e3?(n/1e3).toFixed(1)+'k':String(n));
const fmtDur=s=>{if(s==null)return '—';s=Math.round(s);const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h}h ${m}m`:(m?`${m}m`:`${s}s`);};
const ck=H.config_key||{};
document.getElementById('sub').innerHTML=`tz <b>${esc(ck.tz||'UTC')}</b> · archived:${ck.include_archived} · legacy:${ck.include_legacy} · buckets: ${Object.keys(H.buckets||{}).length}`;
const B=H.buckets||{};
function rows(kind){return Object.entries(B).filter(([id,v])=>v.kind===kind).sort((a,b)=>a[0]<b[0]?1:-1);}
function path(id,kind){return kind==='all-time'?'all-time.html':`${kind}/${id}.html`;}
function tbl(title,kind){
  const rs=rows(kind);if(!rs.length)return '';
  let h=`<section><h2>${esc(title)} (${rs.length})</h2><table><thead><tr>
   <th>Period</th><th>State</th><th class="right">Tasks</th><th class="right">Runs</th>
   <th class="right">✓/⏸/✗</th><th class="right">Rev tok</th><th class="right">Wkr tok≈</th>
   <th class="right">Active</th><th class="right">PRs</th><th class="right">Find.</th><th>as_of</th></tr></thead><tbody>`;
  rs.forEach(([id,v])=>{const k=v.kpis||{};
    h+=`<tr><td><a href="${esc(path(id,kind))}">${esc(id)}</a></td>
     <td class="${v.frozen?'frozen':'cur'}">${v.frozen?'❄ archived':'live'}</td>
     <td class="right">${k.tasks??'—'}</td><td class="right">${k.runs??'—'}</td>
     <td class="right">${k.success||0}/${k.stopped||0}/${k.failed||0}</td>
     <td class="right">${fmtK(k.reviewer_tokens)}</td><td class="right mut">≈${fmtK(k.worker_tokens_est)}</td>
     <td class="right">${fmtDur(k.active_seconds)}</td><td class="right">${k.prs||0}</td><td class="right">${k.findings||0}</td>
     <td class="mut" style="font-size:11px">${esc(v.as_of||'')}</td></tr>`;});
  return h+'</tbody></table></section>';
}
let app=document.getElementById('app'),h='';
if(B['all-time']){const k=B['all-time'].kpis||{};
  h+=`<section><h2>All-time</h2><p><a href="all-time.html">Open the full all-time dashboard →</a></p>
   <div class="mut">${k.tasks} tasks · ${k.runs} runs · ${fmtK(k.reviewer_tokens)} reviewer tokens · ${fmtDur(k.active_seconds)} active · ${k.prs} PRs</div></section>`;}
h+=`<section><h2>Monthly trend</h2><div class="chartbox"><canvas id="trend"></canvas></div></section>`;
h+=tbl('Months','month')+tbl('Weeks','week')+tbl('Days','day');
app.innerHTML=h;
const mr=rows('month').slice().reverse();
const trendChart=new Chart(document.getElementById('trend'),{data:{labels:mr.map(x=>x[0]),datasets:[
  {type:'bar',label:'runs',data:mr.map(x=>(x[1].kpis||{}).runs||0),backgroundColor:'#3fb950',yAxisID:'y'},
  {type:'line',label:'reviewer tokens',data:mr.map(x=>(x[1].kpis||{}).reviewer_tokens||0),borderColor:'#d29922',yAxisID:'y1',tension:.25}]},
 options:{scales:{y:{position:'left',beginAtZero:true},y1:{position:'right',beginAtZero:true,grid:{drawOnChartArea:false}}}}});
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{applyChartTheme();try{trendChart.update()}catch(e){}});
(function(){ const btn=document.getElementById('theme-btn'); setTheme(storedTheme());
  if(btn) btn.onclick=()=>setTheme(THEME_SEQ[(THEME_SEQ.indexOf(storedTheme())+1)%THEME_SEQ.length]); })();
</script></body></html>
"""


def main():
    global RUNS_ROOT
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
    args = ap.parse_args()

    if not args.id_pattern:
        print("runs-stats: no id_pattern supplied. Pass --id-pattern with the resolved "
              "issue2pr profile's `id_pattern` (see .vibe-suite.md `issue2pr_profile:` -> "
              "profiles/<name>.md). A generic guess would bucket runs wrongly, so this "
              "refuses instead.", file=sys.stderr)
        raise SystemExit(2)
    global ID_RE, SEARCH_RE
    try:
        ID_RE = re.compile(args.id_pattern, re.I)
        SEARCH_RE = re.compile(args.id_pattern.lstrip("^").rstrip("$"), re.I)
    except re.error as exc:
        print(f"runs-stats: --id-pattern is not a valid regex: {exc}", file=sys.stderr)
        raise SystemExit(2)

    runs_root = Path(args.runs_root).resolve()
    RUNS_ROOT = runs_root
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
        r["timeline"] = read_text(os.path.join(str(runs_root.parent), tp)) if tp else None

    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ----- ad-hoc filtered mode: single --out report, never touches the canonical store (G1)
    if args.ticket or args.scenario or args.since or args.until:
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
                         runs_root, warnings, period_page=False)
        print(f"runs-stats: ad-hoc report → {out}  ({len(sub)} runs)")
        print("  NOTE: ad-hoc filtered runs do NOT update the canonical history/index/buckets (G1).")
        return

    # ----- canonical bucketed mode
    reports_dir = Path(args.reports_dir)
    config_key = {"tz": tz, "include_archived": args.include_archived,
                  "include_legacy": args.include_legacy, "id_pattern": args.id_pattern}
    history = load_history(reports_dir / "history.json")
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
                                  as_of, tz, rate, runs_root, warnings, period_page=False)
        history["buckets"]["all-time"] = {"kind": "all-time", "as_of": as_of, "frozen": False,
                                          "kpis": kpis_summary(tr, runs, ag)}
        written.append("all-time.html")
        # optional extra copy ONLY if --out is explicitly given (no default duplicate file)
        if args.out:
            compat = Path(args.out)
            compat.parent.mkdir(parents=True, exist_ok=True)
            compat.write_text((reports_dir / "all-time.html").read_text(encoding="utf-8"), encoding="utf-8")

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
                                      runs_root, warnings, period_page=True)
            history["buckets"][bid] = {"kind": kind, "as_of": as_of, "frozen": not is_current,
                                       "window": wlabel, "sig": sig, "kpis": kpis_summary(tr, rs, ag)}
            written.append(f"{kind}/{bid}.html{tag}")

    if surgical and not any(args.period in w for w in written):
        print(f"  note: --period {args.period} matched no bucket with runs (nothing regenerated)")

    # NOTE: a day/week/month file exists iff that period has >=1 run. Empty periods (including the
    # current one when it has no runs yet) are skipped entirely — no file, no history row, no index
    # entry. all-time.html + index.html always regenerate (they are the entry points).

    # history + index
    (reports_dir / "history.json").write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    (reports_dir / "index.html").write_text(render_index(history, reports_dir), encoding="utf-8")

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
