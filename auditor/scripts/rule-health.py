#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Rebuild the rule-health feedback log from the event ledger.

    rule-health.py --data-dir DIR [--out PATH] [--rubric PATH]

Writes `<data-dir>/feedback/log.json` unless `--out` says otherwise. This is the dataset that
decides which rules get weakened, rewritten or retired, so every count here eventually argues
for changing the rulebook.

HITS ARE UNIQUE FINGERPRINTS, NOT EVENTS. The ledger is append-only and the same finding is
logged more than once as a matter of course — a re-audit re-reports it, a retry re-appends it,
a backfill adds provenance for it. Counting events makes a rule look busier every time anything
is re-run, and the rules that get re-run most are the ones already under suspicion. That is a
feedback loop pointing the wrong way: the noisiest-looking rule becomes noisier the more it is
investigated.

THE LATEST OUTCOME WINS. A fingerprint accumulates outcomes over time — submitted, then
rejected, then applied_separately when the maintainer fixed it their own way. Summing them
counts one finding several times and lets a single finding be both rejected and accepted.
Events are therefore ordered and only the last one per fingerprint counts.

APPLIED-SEPARATELY IS ACCEPTANCE. The maintainer fixed the problem and closed our PR. The
finding was right. Filing that under rejection makes correct rules look wrong, and the rules
most likely to be fixed-then-closed are the simple, obviously-correct ones — so the mistake
falls hardest on the best rules in the book.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

#: Outcomes meaning the finding was accepted, whatever became of our PR.
ACCEPTED = ("merged", "applied_separately")
REJECTED = ("rejected",)
#: Terminal outcomes. `open`/`submitted` are deliberately excluded from the denominator.
RESOLVED = ACCEPTED + REJECTED

OUTCOME_EVENTS = ("pr_outcome", "finding_outcome")


def refuse(reason: str) -> None:
    print(f"REFUSE:rule-health:{reason}", file=sys.stderr)
    raise SystemExit(1)


def read_jsonl(path: Path):
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def atomic_write(path: Path, text: str) -> None:
    """Same-directory temp file plus rename.

    Every consumer of this file reads it whole; a partial write would be parsed as a smaller,
    entirely plausible dataset rather than failing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent),
                                         prefix=path.name + ".", delete=False)
    try:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, path)
    except BaseException:
        os.unlink(handle.name)
        raise


def latest_outcomes(events):
    """`{fingerprint: outcome}` keeping only the LAST outcome recorded for each finding.

    Ordered by the event's own timestamp with the ledger position as tie-break, so two events
    sharing a second still resolve in append order rather than arbitrarily.
    """
    outcomes = {}
    ordered = sorted(enumerate(events),
                     key=lambda pair: (str(pair[1].get("timestamp") or ""), pair[0]))
    for _, event in ordered:
        if event.get("event") not in OUTCOME_EVENTS:
            continue
        data = event.get("data") or {}
        fingerprint = data.get("fingerprint")
        outcome = data.get("outcome")
        if fingerprint and outcome:
            outcomes[fingerprint] = str(outcome)
    return outcomes


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild the rule-health feedback log.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--out", default=None, help="default <data-dir>/feedback/log.json")
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args(argv)

    if not args.data_dir:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        refuse("data-dir-missing")

    events = read_jsonl(data_dir / "ledgers" / "events.jsonl")
    outcomes = latest_outcomes(events)

    # fingerprint -> rule_id, learned from whichever event carries both. Built first so a
    # fingerprint seen only in an outcome event still attributes to its rule.
    rule_of = {}
    for event in events:
        data = event.get("data") or {}
        if data.get("fingerprint") and data.get("rule_id"):
            rule_of.setdefault(data["fingerprint"], str(data["rule_id"]))

    findings = {}
    for path in sorted((data_dir / "audits").glob("*.findings.jsonl")) \
            if (data_dir / "audits").is_dir() else []:
        for finding in read_jsonl(path):
            if finding.get("fingerprint"):
                findings.setdefault(finding["fingerprint"], finding)
                if finding.get("rule_id"):
                    rule_of.setdefault(finding["fingerprint"], str(finding["rule_id"]))

    verified = {event.get("data", {}).get("fingerprint")
                for event in events if event.get("event") == "finding_verified"}
    verified.discard(None)

    exemplars = {}
    for event in events:
        if event.get("event") == "exemplar_published":
            rule_ids = (event.get("data") or {}).get("rule_ids") or []
            for rule in rule_ids:
                exemplars[str(rule)] = exemplars.get(str(rule), 0) + 1

    rules = {}
    for fingerprint, rule in rule_of.items():
        row = rules.setdefault(rule, {"rule_id": rule, "hits": 0, "merged": 0,
                                      "applied_separately": 0, "rejected": 0, "open": 0,
                                      "verified": 0, "exemplars": 0,
                                      "false_positives": 0})
        row["hits"] += 1                      # one per UNIQUE fingerprint, never per event
        outcome = outcomes.get(fingerprint)
        if outcome in ACCEPTED or outcome in REJECTED:
            row[outcome] = row.get(outcome, 0) + 1
        elif outcome:
            row["open"] += 1
        if fingerprint in verified:
            row["verified"] += 1
        if (findings.get(fingerprint) or {}).get("false_positive"):
            row["false_positives"] += 1

    for rule, row in rules.items():
        row["exemplars"] = exemplars.get(rule, 0)
        resolved = sum(row[k] for k in RESOLVED)
        accepted = sum(row[k] for k in ACCEPTED)
        row["resolved"] = resolved
        # applied_separately counts as acceptance: the maintainer fixed it and closed our PR,
        # which means the finding was right.
        row["acceptance_rate"] = round(accepted / resolved, 4) if resolved else None
        row["false_positive_rate"] = (round(row["false_positives"] / row["hits"], 4)
                                      if row["hits"] else None)

    payload = {
        "schema_version": 1,
        "generated_at": args.generated_at,
        "totals": {
            "rules": len(rules),
            "findings": len(rule_of),
            "resolved": sum(r["resolved"] for r in rules.values()),
            "verified": len(verified),
        },
        "rules": [rules[r] for r in sorted(rules)],
    }

    out = Path(args.out) if args.out else data_dir / "feedback" / "log.json"
    atomic_write(out, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"rule-health: {len(rules)} rule(s), {len(rule_of)} finding(s) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
