#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Render the daily auditor report.

    generate-daily-report.py --data-dir DIR [--date YYYY-MM-DD] [--inputs DIR]

Reads cached stats, writes `<data-dir>/reports/<date>.md`. Every input is optional — a missing
file becomes empty — because the report is a status page and a missing section is information,
not a reason to fail the run.

TWO RATES, AND THE DIFFERENCE MATTERS. A finding can be accepted without our PR being merged:
a maintainer often applies the fix themselves and closes the PR, which is `applied_separately`.
That is the pipeline working — the code got fixed — so:

    acceptance rate = (merged + applied_separately) / resolved
    merge-only rate =  merged                       / resolved

Counting only merges undercounts the pipeline's actual effect and would push whoever reads this
report toward optimising for merges rather than for fixes. Both rates are shown side by side so
the gap between them is visible rather than a matter of which denominator someone picked.

`resolved` deliberately excludes still-open PRs: dividing by them would make the rate drift
downward simply because new PRs exist, which says nothing about whether findings are accepted.

The date is a parameter rather than "now" so a report can be regenerated for a past day and
come out identical.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

STAGES = ("discovered", "audited", "contributed", "tracked", "complete")
#: Outcomes that mean the finding was accepted, whatever happened to the PR itself.
ACCEPTED = ("merged", "applied_separately")
#: Outcomes that mean the PR reached an end state; `open` is deliberately absent.
RESOLVED = ACCEPTED + ("rejected",)


def load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def rates(outcomes):
    """`(acceptance, merge_only, resolved)` from a mapping of outcome -> count."""
    resolved = sum(int(outcomes.get(k, 0)) for k in RESOLVED)
    if not resolved:
        return None, None, 0
    accepted = sum(int(outcomes.get(k, 0)) for k in ACCEPTED)
    merged = int(outcomes.get("merged", 0))
    return accepted / resolved, merged / resolved, resolved


def render(date, registry, outcomes, rule_health, activity):
    pct = lambda v: "N/A" if v is None else f"{v * 100:.0f}%"
    acceptance, merge_only, resolved = rates(outcomes)

    lines = [f"# Daily report — {date}", "", "## Pipeline", "",
             "| Stage | Count |", "|---|---|"]
    by_status = registry.get("by_status") or {}
    for stage in STAGES:
        lines.append(f"| {stage} | {int(by_status.get(stage, 0))} |")
    # vibe-167 (F4): statuses outside the five stages — policy_denied,
    # policy_cla_required, orphaned, whatever the registry holds — are facts the
    # report existed to show; rendering only the known five silently hid them
    for status in sorted(set(by_status) - set(STAGES)):
        lines.append(f"| {status} | {int(by_status.get(status, 0))} |")
    lines += [f"| **total** | **{int(registry.get('total', 0))}** |", ""]

    lines += ["## Contribution outcomes", "", "| Metric | Value |", "|---|---|"]
    for name in RESOLVED:
        lines.append(f"| {name} | {int(outcomes.get(name, 0))} |")
    lines += [f"| open (not counted as resolved) | {int(outcomes.get('open', 0))} |",
              f"| resolved | {resolved} |",
              f"| **acceptance rate** (merged + applied separately) | **{pct(acceptance)}** |",
              f"| merge-only rate | {pct(merge_only)} |", ""]

    lines += ["## Rule health", ""]
    if rule_health:
        lines += ["| Rule | Findings | Accepted |", "|---|---|---|"]
        for rule in sorted(rule_health):
            row = rule_health[rule] or {}
            lines.append(f"| {rule} | {int(row.get('findings', 0))} "
                         f"| {int(row.get('accepted', 0))} |")
    else:
        lines.append("_No rule-health data for this period._")
    lines.append("")

    lines += ["## Activity", ""]
    if activity:
        lines += [f"- {item}" for item in activity]
    else:
        lines.append("_No notable events._")
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the daily auditor report.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR", "."))
    parser.add_argument("--inputs", default=None,
                        help="directory of cached stat files (default <data-dir>/report-cache)")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD; default today (UTC)")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    inputs = Path(args.inputs or data_dir / "report-cache")
    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    text = render(
        date,
        load(inputs / "registry-stats.json", {}),
        load(inputs / "pr-outcomes.json", {}),
        load(inputs / "rule-health.json", {}),
        load(inputs / "recent-activity.json", []),
    )

    out = Path(args.out or data_dir / "reports" / f"{date}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
