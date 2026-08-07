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
import re
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


def read_exemplar_citations(directory: Path):
    """One record per (rule, exemplar) from the exemplar corpus.

    `exemplifies` is the join key SCHEMAS.md names; `audited` is the confirmation date. A bare
    string in `exemplifies` is rejected by the exemplar workflow, so a non-list here is a
    malformed file rather than a single-rule shorthand.
    """
    if not directory.is_dir():
        return []
    out = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        front = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", text, re.DOTALL)
        if not front:
            continue
        block = front.group(1)
        audited = re.search(r"^audited:[ \t]*(\S+)", block, re.MULTILINE)
        inline = re.search(r"^exemplifies:[ \t]*\[(.*?)\][ \t]*$", block, re.MULTILINE)
        if inline:
            rules = re.findall(r"[A-Za-z0-9:_-]+", inline.group(1))
        else:
            listed = re.search(r"^exemplifies:[ \t]*\n((?:[ \t]*-[ \t]*\S+\n?)+)",
                               block, re.MULTILINE)
            rules = re.findall(r"-[ \t]*(\S+)", listed.group(1)) if listed else []
        for rule in rules:
            out.append({"rule_id": rule, "exemplar": path.name,
                        "confirmed_at": audited.group(1).strip("\"'") if audited else None})
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

    # Citations are not a ledger. The exemplar files ARE the citation record: each carries
    # `exemplifies` (the rules it evidences) and `audited` (when it was last confirmed), per
    # SCHEMAS.md section 8. Reading a separate ledger would be a second copy of the same fact,
    # free to disagree with the files it describes.
    citations = read_exemplar_citations(data_dir / "exemplars")
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

    # FIVE EVENT TYPES SHARE THIS FILE, all inside the section 7 envelope. Only
    # `maintainer_rejected` is a rejection: `pr_comments_snapshot` is the raw thread captured
    # AT that rejection, `self_false_positive` is our own invalidation, and
    # `downstream_suppression` is a config change. Counting them all inflated the section with
    # duplicates of the same dispute and with findings no maintainer ever saw.
    #
    # And its fields are `pr`, `fingerprints[]`, `rule_ids[]`, `quote` — not `repo`, `rule_id`,
    # `reason`. Reading the singular names off an enveloped record yields null for every one,
    # so production rendered a table of empty rows that still looked like a populated report.
    rejections = []
    for record in disagreements:
        data = record.get("data") if isinstance(record.get("data"), dict) else record
        if record.get("event") != "maintainer_rejected":
            continue
        when = parse_day(record.get("timestamp") or data.get("timestamp"))
        if when is None or not (start <= when <= end):
            continue
        rules = data.get("rule_ids")
        rules = [str(r) for r in rules] if isinstance(rules, list) and rules else ["--"]
        # One row per rule: a bundled PR disputes several findings at once, and collapsing them
        # would credit the dispute to whichever rule happened to sort first.
        for rule in rules:
            rejections.append({
                "rule_id": rule,
                "pr": data.get("pr"),
                "when": when.isoformat(),
                "dissent": (data.get("dissent_type") or "").strip(),
                "role": (data.get("commenter_role") or "").strip(),
                "reason": (data.get("quote") or "").strip(),
            })
    rejections.sort(key=lambda r: (str(r["when"]), str(r["rule_id"]), str(r["pr"])))

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
        lines += ["| Date | Rule | PR | Dissent | Role | Quote |",
                  "|---|---|---|---|---|---|"]
        lines += [f"| {r['when']} | {r['rule_id']} | {r['pr'] or '--'} "
                  f"| {r['dissent'] or '--'} | {r['role'] or '--'} "
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
