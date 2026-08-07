#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Compose the quarterly rule-review issue body.

    generate-rule-review-body.py --data-dir DIR --quarter YYYY-Qn [--as-of YYYY-MM-DD]

Two sections a reviewer cannot assemble by hand:

  * STALE CITATIONS — rules whose supporting exemplar has not been re-confirmed in 90 days. The
    rule may still be right; what has lapsed is the evidence we would cite if challenged.
  * RECENT REJECTIONS — findings maintainers declined this quarter, with their reasons.

BOTH DATES ARE PARAMETERS, NEVER `now()`. A review body regenerated next week must come out
identical, or the issue picks up an unreviewable diff every time anyone re-runs the workflow —
and "which of these changed because the data changed, and which because time passed?" is not a
question a reviewer should have to answer.

THE STALE COMPARISON IS `age > 90 days`, and the reversed form is the easy mistake. `age < 90`
selects the FRESHEST citations, which reads perfectly: a plausible list of rules under a
heading that says the opposite of what it contains. Every genuinely stale citation is then
omitted, and the review concludes the evidence base is sound.

PATHS POINT AT THIS SUITE'S SKILLS. Emitting `skills/nlpm/...` produces links that 404 for
every reviewer, and the retired namespace is exactly what the AC-6 sweep exists to catch — the
rule paths here are `skills/rules/SKILL.md` and its siblings.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

STALE_AFTER_DAYS = 90
#: This suite's rulebook. `skills/nlpm/...` is the retired upstream spelling.
RULES_PATH = "skills/rules/SKILL.md"
SCORING_PATH = "skills/scoring/SKILL.md"


def refuse(reason: str) -> None:
    print(f"REFUSE:generate-rule-review-body:{reason}", file=sys.stderr)
    raise SystemExit(1)


def read_jsonl(path: Path):
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def parse_day(value):
    if not value:
        return None
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def quarter_bounds(quarter: str):
    """`(first_day, last_day)` for `YYYY-Qn`."""
    try:
        year_text, q_text = quarter.split("-Q")
        year, number = int(year_text), int(q_text)
    except (ValueError, AttributeError):
        refuse(f"quarter-invalid {quarter}")
    if not 1 <= number <= 4:
        refuse(f"quarter-invalid {quarter}")
    first_month = 3 * (number - 1) + 1
    start = date(year, first_month, 1)
    end = date(year + (first_month + 3 > 12), (first_month + 3 - 1) % 12 + 1, 1) \
        - timedelta(days=1)
    return start, end


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compose the quarterly rule-review body.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--quarter", default=None, help="YYYY-Qn")
    parser.add_argument("--as-of", default=None,
                        help="YYYY-MM-DD; the staleness reference. Default today (UTC).")
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    if not args.data_dir:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        refuse("data-dir-missing")
    if not args.quarter:
        refuse("quarter-required")
    start, end = quarter_bounds(args.quarter)

    as_of = parse_day(args.as_of) or datetime.now(timezone.utc).date()
    if args.as_of and parse_day(args.as_of) is None:
        refuse(f"as-of-invalid {args.as_of}")
    cutoff = as_of - timedelta(days=STALE_AFTER_DAYS)

    citations = read_jsonl(data_dir / "ledgers" / "citations.jsonl")
    disagreements = read_jsonl(data_dir / "ledgers" / "disagreements.jsonl")

    stale = []
    latest_by_rule = {}
    for citation in citations:
        rule = citation.get("rule_id")
        confirmed = parse_day(citation.get("confirmed_at") or citation.get("timestamp"))
        if not rule or confirmed is None:
            continue
        if rule not in latest_by_rule or confirmed > latest_by_rule[rule][0]:
            latest_by_rule[rule] = (confirmed, citation)
    for rule, (confirmed, citation) in latest_by_rule.items():
        # `confirmed < cutoff` is `age > 90 days`. The reversed form selects the FRESHEST
        # citations and prints them under a heading claiming the opposite.
        if confirmed < cutoff:
            stale.append({"rule_id": rule, "confirmed_at": confirmed.isoformat(),
                          "age_days": (as_of - confirmed).days,
                          "exemplar": citation.get("exemplar")})
    stale.sort(key=lambda r: (-r["age_days"], str(r["rule_id"])))

    rejections = []
    for record in disagreements:
        when = parse_day(record.get("timestamp") or record.get("rejected_at"))
        if when is None or not (start <= when <= end):
            continue
        rejections.append({"rule_id": record.get("rule_id"), "repo": record.get("repo"),
                           "when": when.isoformat(),
                           "reason": (record.get("reason") or "").strip()})
    rejections.sort(key=lambda r: (str(r["when"]), str(r["rule_id"]), str(r["repo"])))

    lines = [
        f"# Rule review — {args.quarter}", "",
        f"Staleness measured as of `{as_of.isoformat()}`; a citation is stale after "
        f"{STALE_AFTER_DAYS} days.",
        f"Rejections cover `{start.isoformat()}` to `{end.isoformat()}`.", "",
        f"Rulebook: [`{RULES_PATH}`]({RULES_PATH}) · scoring: [`{SCORING_PATH}`]"
        f"({SCORING_PATH})", "",
        f"## Stale citations ({len(stale)})", "",
    ]
    if stale:
        lines += ["| Rule | Last confirmed | Age (days) | Exemplar |", "|---|---|---|---|"]
        lines += [f"| {r['rule_id']} | {r['confirmed_at']} | {r['age_days']} "
                  f"| {r['exemplar'] or '--'} |" for r in stale]
    else:
        lines.append("_Every cited exemplar was re-confirmed within the window._")
    lines += ["", f"## Rejections this quarter ({len(rejections)})", ""]
    if rejections:
        lines += ["| Date | Rule | Repository | Reason |", "|---|---|---|---|"]
        lines += [f"| {r['when']} | {r['rule_id']} | {r['repo']} "
                  f"| {(r['reason'] or '--')[:200]} |" for r in rejections]
    else:
        lines.append("_No findings were declined in this window._")
    lines.append("")

    text = "\n".join(lines)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"generate-rule-review-body: {len(stale)} stale, {len(rejections)} rejected "
              f"-> {out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
