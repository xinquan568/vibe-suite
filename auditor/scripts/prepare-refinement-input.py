#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Select the rules worth a human's attention, with the evidence for each.

    prepare-refinement-input.py --data-dir DIR [--out PATH] [--min-hits N]

Reads `<data-dir>/feedback/log.json` and writes the refinement input a reviewer works from.

THIS IS A FILTER, AND THE FILTER IS THE VALUE. Handing over every rule is the same as handing
over nothing: the reviewer skims, the genuinely broken rules sit in the middle of a long list,
and the exercise produces no changes. Two conditions get a rule onto the list:

  * NOISY — a high false-positive rate. The rule fires on things that are not problems.
  * DISPUTED — a low acceptance rate. Maintainers were told and disagreed.

A healthy rule is never included, however many times it fired. A rule that fires two hundred
times and is accepted every time is the rulebook working, and putting it in front of a reviewer
invites a change that would break something correct.

THE THREE-HIT FLOOR IS A CONFIDENCE FLOOR, not a tidiness one. One rejection out of one hit is
a 0% acceptance rate and means nothing — a single maintainer having a bad day produces it. Act
on that and rules get rewritten from single anecdotes, which is worse than not reviewing them,
because the change carries the authority of a review.

DISPUTED SORTS ABOVE NOISY. A noisy rule wastes our time; a disputed rule wasted a maintainer's,
and it is the one that costs us the standing to file the next finding.

EVIDENCE IS CAPPED AT FIVE PER RULE. Not for file size — so the reviewer reads them. Forty
examples of the same failure is one fact presented forty times, and the cap keeps the input
something a person finishes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

#: A rule must have at least this many distinct findings before its rates mean anything.
MIN_HITS = 3
#: Above this share of false positives, the rule fires on things that are not problems.
NOISY_FP_RATE = 0.30
#: Below this acceptance rate, maintainers were told and disagreed.
DISPUTED_ACCEPTANCE = 0.50
#: Evidence items kept per rule.
EVIDENCE_CAP = 5


def refuse(reason: str) -> None:
    print(f"REFUSE:prepare-refinement-input:{reason}", file=sys.stderr)
    raise SystemExit(1)


def read_findings(data_dir: Path):
    """`{rule_id: [finding, ...]}` from every audit sidecar, in a stable order."""
    audits = data_dir / "audits"
    by_rule: dict[str, list[dict]] = {}
    if not audits.is_dir():
        return by_rule
    for path in sorted(audits.glob("*.findings.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                finding = json.loads(line)
            except json.JSONDecodeError:
                continue
            if finding.get("rule_id"):
                by_rule.setdefault(str(finding["rule_id"]), []).append(finding)
    return by_rule


def classify(row, min_hits):
    """`(include, reasons)` for one rule-health row."""
    hits = int(row.get("hits") or 0)
    if hits < min_hits:
        return False, []
    reasons = []
    fp_rate = row.get("false_positive_rate")
    if fp_rate is not None and float(fp_rate) > NOISY_FP_RATE:
        reasons.append("noisy")
    acceptance = row.get("acceptance_rate")
    # `is not None` and not truthiness: an acceptance rate of exactly 0.0 is the strongest
    # possible dispute, and it is the value truthiness throws away.
    if acceptance is not None and float(acceptance) < DISPUTED_ACCEPTANCE \
            and int(row.get("resolved") or 0) > 0:
        reasons.append("disputed")
    return bool(reasons), reasons


def main(argv=None):
    parser = argparse.ArgumentParser(description="Select rules needing human review.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--feedback", default=None, help="default <data-dir>/feedback/log.json")
    parser.add_argument("--out", default=None, help="default stdout")
    parser.add_argument("--min-hits", type=int, default=MIN_HITS)
    args = parser.parse_args(argv)

    if not args.data_dir and not args.feedback:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir) if args.data_dir else None
    feedback = Path(args.feedback) if args.feedback else data_dir / "feedback" / "log.json"
    if not feedback.is_file():
        # rule-health.py always writes this file, so its absence means the rebuild was lost —
        # not that there is no feedback. Selecting from nothing would report "no rules need
        # review", which is the most reassuring possible way to be wrong.
        refuse("feedback-missing")
    try:
        payload = json.loads(feedback.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        refuse("feedback-unreadable")
    rows = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        refuse("feedback-malformed")

    by_rule = read_findings(data_dir) if data_dir else {}

    selected = []
    for row in rows:
        include, reasons = classify(row, args.min_hits)
        if not include:
            continue
        # `fingerprint` is absent from section-4 sidecars; the reviewer reads file+line, so
        # it is reported when enriched and simply omitted otherwise rather than shown null.
        evidence = [{"fingerprint": f.get("fingerprint"), "file": f.get("file"),
                     "line": f.get("line"), "description": f.get("description"),
                     "false_positive": bool(f.get("false_positive"))}
                    for f in by_rule.get(str(row.get("rule_id")), [])[:EVIDENCE_CAP]]
        selected.append({
            "rule_id": row.get("rule_id"),
            "reasons": reasons,
            "disputed": "disputed" in reasons,
            "hits": int(row.get("hits") or 0),
            "acceptance_rate": row.get("acceptance_rate"),
            "false_positive_rate": row.get("false_positive_rate"),
            "resolved": int(row.get("resolved") or 0),
            "evidence": evidence,
            "evidence_truncated": len(by_rule.get(str(row.get("rule_id")), [])) > EVIDENCE_CAP,
        })

    # Disputed first, then hits descending, then rule id so the order is total and two runs
    # over the same data produce the same document.
    selected.sort(key=lambda r: (not r["disputed"], -r["hits"], str(r["rule_id"])))

    out_payload = {
        "schema_version": 1,
        "criteria": {"min_hits": args.min_hits, "noisy_above": NOISY_FP_RATE,
                     "disputed_below": DISPUTED_ACCEPTANCE, "evidence_cap": EVIDENCE_CAP},
        "considered": len(rows),
        "selected": len(selected),
        "rules": selected,
    }
    text = json.dumps(out_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"prepare-refinement-input: {len(selected)} of {len(rows)} rule(s) -> {out}")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
