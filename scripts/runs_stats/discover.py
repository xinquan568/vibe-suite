# SPDX-License-Identifier: ISC
"""runs-stats — discovery: walk the runs/ tree and build one record per execution run (H12 / vibe-216).

Split out of the former single-file generator (`skills/runs-stats/scripts/generate_runs_stats.py`);
function bodies are unchanged. Everything here is a library: it imports the standard library only and
never touches `sys.path` — `main.py` is the program. Identity (`ID_RE`/`SEARCH_RE`) and the runs root
are module state set once by `configure()`; every parser below is a plain function of its arguments.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import bridge  # scripts/lib — the one JSON reader; main.py bootstraps the path before importing this module

# The work-item id pattern is profile-supplied (--id-pattern; the issue2pr profile's
# anchored `id_pattern`). ID_RE keeps the anchored form for whole-id matches; SEARCH_RE is
# its unanchored core, used only for the run-folder-name fallback when a run's metadata
# carries no id. main() sets both before discovery.
ID_RE = None


SEARCH_RE = None
RUNS_ROOT = None

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
        return bridge.load_json(path)          # the one reader (M6 / vibe-218); strict, so every failure raises
    except bridge.JsonUnreadable as exc:  # malformed / unreadable -> warning, never abort; the CAUSE is the public text
        warnings.append(f"parse-error: {os.path.relpath(path)} :: {exc.cause.__class__.__name__}: {exc.cause}")
        return None


def read_text(path, cap=20000, warnings=None):
    """A capped text read that never raises. A failure is reported into `warnings` (when given) as
    `timeline-read-error` and yields None — it used to be silent, which made a missing or unreadable
    timeline indistinguishable from an absent one (H12 / vibe-216)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            t = fh.read()
        return t[:cap] + ("\n…(truncated)…" if len(t) > cap else "")
    except Exception as exc:
        if warnings is not None:
            try:
                shown = os.path.relpath(path)
            except ValueError:
                shown = str(path)
            warnings.append(f"timeline-read-error: {shown} :: {exc.__class__.__name__}: {exc}")
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

    def field(key):
        # A non-numeric usage value is garbage in a data file: warn and count zero, never abort.
        try:
            return int(usage.get(key, 0) or 0)
        except (TypeError, ValueError):
            warnings.append(f"stream-error: {path} :: non-numeric usage field {key}")
            return 0
    nb = {
        "input_total": field("input_tokens"),
        "input_cached": field("cached_input_tokens"),
        "output": field("output_tokens"),
        "reasoning_output": field("reasoning_output_tokens"),
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


# ----------------------------------------------------------------------------- state.json shape


def coerce_state(state, name, warnings):
    """Normalise a *parsed* state.json into the shape the rest of discovery assumes.

    Unparseable files are already a `parse-error` warning in `load_json`; this covers the file that
    parses but carries the wrong shape — a dict where a list belongs, a number where a string belongs.
    Each defect is one `shape-error` warning and a safe default (H12 / vibe-216: "warn, never abort").
    Absent keys and `None` values are not defects. Applies only to a non-None parse result, after the
    legacy `state.yaml` fallback has had its chance at `None`."""
    def warn(msg):
        warnings.append(f"shape-error: {name}: {msg}")
    if not isinstance(state, dict):
        warn(f"state.json is not an object ({type(state).__name__}); ignored")
        return {}
    out = dict(state)
    status = out.get("status")
    if status is not None and not isinstance(status, str):
        warn(f"status is {type(status).__name__}, not a string; ignored")
        out["status"] = None
    rounds = out.get("rounds")
    if rounds is not None:
        if not isinstance(rounds, list):
            warn(f"rounds is {type(rounds).__name__}, not a list; ignored")
            out["rounds"] = []
        else:
            kept = []
            for i, rd in enumerate(rounds):
                if not isinstance(rd, dict):
                    warn(f"rounds[{i}] is {type(rd).__name__}, not an object; dropped")
                    continue
                rd = dict(rd)
                commits = rd.get("commits")
                if commits is not None and not isinstance(commits, list):
                    warn(f"rounds[{i}].commits is {type(commits).__name__}, not a list; ignored")
                    rd["commits"] = []
                pr_url = rd.get("pr_url")
                if pr_url is not None and not isinstance(pr_url, str):
                    warn(f"rounds[{i}].pr_url is {type(pr_url).__name__}, not a string; dropped")
                    del rd["pr_url"]
                kept.append(rd)
            out["rounds"] = kept
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
    elif state is not None:
        state = coerce_state(state, name, warnings)
    state = state or {}

    # metadata precedence: 00-meta -> manifest -> path-derived -> state
    sub = manifest.get("subtask") or {}
    parent_src = manifest.get("parent_source") or {}

    def profile_id(value):
        # An authoritative metadata id counts only when it matches the profile pattern
        # (D3/F8.5 — anchored whole-id match); a mismatch is warned and ignored so the
        # folder-name fallback, or "(unknown)", takes over. Legacy records are exempt:
        # their ids predate any profile.
        if not value:
            return None
        value = str(value)
        if ID_RE and not ID_RE.fullmatch(value):
            warnings.append(f"id-pattern-mismatch: {name}: metadata id {value!r} "
                            "does not match --id-pattern; ignored")
            return None
        return value

    source_id = (profile_id(meta.get("source_id")) or profile_id(sub.get("id"))
                 or (legacy or {}).get("ticket_key") or ticket_key_from(name))
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


def configure(runs_root, id_pattern):
    """Set the module state `main` used to write directly: the anchored profile pattern, its unanchored
    core for the folder-name fallback, and the resolved runs root. The only writer of these globals."""
    global ID_RE, SEARCH_RE, RUNS_ROOT
    ID_RE = re.compile(id_pattern, re.I)
    SEARCH_RE = re.compile(id_pattern.lstrip("^").rstrip("$"), re.I)
    RUNS_ROOT = Path(runs_root).resolve()
