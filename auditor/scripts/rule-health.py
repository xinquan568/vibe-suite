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
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

#: Outcomes meaning the finding was accepted, whatever became of our PR.
ACCEPTED = ("merged", "applied_separately")
REJECTED = ("rejected",)
#: Terminal outcomes. `open`/`submitted` are deliberately excluded from the denominator.
RESOLVED = ACCEPTED + REJECTED

#: SCHEMAS.md section 1, PR record: the pipeline outcome enum. This lives in the REGISTRY, not
#: in the event stream. `finding_outcome` events carry `pr_state`, a different enum
#: ({merged, closed_unmerged, open, stale_90d, cla_blocked}) describing the PR rather than the
#: adjudication, and they carry `fingerprints[]`/`rule_ids[]` as parallel ARRAYS. Reading a
#: singular `outcome` off those events matches nothing at all — every rule then reports zero
#: resolutions, which reads as "no maintainer has responded yet" rather than as a broken join.
PIPELINE_OUTCOMES = ("merged", "applied_separately", "rejected", "open", "cla_blocked")


def refuse(reason: str) -> None:
    print(f"REFUSE:rule-health:{reason}", file=sys.stderr)
    raise SystemExit(1)


def fingerprint_of(repo: str, finding: dict) -> str:
    """The finding's digest, computed — section 4 sidecars store none."""
    line = finding.get("line")
    payload = "|".join((
        repo,
        str(finding.get("file") or ""),
        str(finding.get("rule_id") or ""),
        str(finding.get("pattern") or ""),
        "null" if line is None or line is False else str(line),
    )) + "\n"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def read_jsonl(path: Path):
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Same shape tolerance as render-dashboard.unwrap: SCHEMAS.md section 2 documents a
        # flat finding record, auditor-audit.yml writes an enveloped one, and reading only one
        # shape silently drops every row of the other.
        if isinstance(record, dict) and isinstance(record.get("data"), dict) \
                and record.get("event") == "finding":
            merged = dict(record["data"])
            for key in ("timestamp", "run_id"):
                merged.setdefault(key, record.get(key))
            record = merged
        records.append(record)
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


def outcomes_from_registry(registry):
    """`{fingerprint: outcome}` from the registry's PR records.

    A finding can appear in several PRs — a first attempt closed, a second merged. The most
    recently updated PR wins, because that is the maintainer's latest word on it. Ties break on
    the PR number so two PRs updated in the same second still resolve deterministically rather
    than by dict order.
    """
    ranked = []
    repos = registry.get("repos") if isinstance(registry, dict) else {}
    for repo, entry in (repos or {}).items():
        prs = entry.get("prs") if isinstance(entry, dict) else None
        for key, record in (prs or {}).items():
            if not isinstance(record, dict):
                continue
            outcome = record.get("outcome")
            if outcome not in PIPELINE_OUTCOMES:
                continue
            try:
                number = int(record.get("number", key))
            except (TypeError, ValueError):
                number = 0
            ranked.append((str(record.get("updatedAt") or ""), number, record, outcome))

    outcomes, rules = {}, {}
    for _, _, record, outcome in sorted(ranked, key=lambda r: (r[0], r[1])):
        fingerprints = record.get("fingerprints") or []
        rule_ids = record.get("rule_ids") or []
        if not isinstance(fingerprints, list):
            continue
        for index, fingerprint in enumerate(fingerprints):
            outcomes[str(fingerprint)] = outcome
            # `rule_ids` is a PARALLEL array, so position is the join. A dict keyed on rule id
            # would silently drop a PR that fixed two findings under the same rule.
            if index < len(rule_ids) and rule_ids[index]:
                rules[str(fingerprint)] = str(rule_ids[index])
    return outcomes, rules


def exemplar_counts(directory: Path):
    """Per-rule exemplar counts from `exemplifies`, the join key SCHEMAS.md names.

    Read from the exemplar FILES, not from events: the files are the record, and an event
    stream would be a second copy free to disagree with them.
    """
    counts = {}
    if not directory.is_dir():
        return counts
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        front = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", text, re.DOTALL)
        if not front:
            continue
        block = front.group(1)
        inline = re.search(r"^exemplifies:[ \t]*\[(.*?)\][ \t]*$", block, re.MULTILINE)
        if inline:
            rules = re.findall(r"[A-Za-z0-9:_-]+", inline.group(1))
        else:
            listed = re.search(r"^exemplifies:[ \t]*\n((?:[ \t]*-[ \t]*\S+\n?)+)",
                               block, re.MULTILINE)
            rules = re.findall(r"-[ \t]*(\S+)", listed.group(1)) if listed else []
        for rule in rules:
            counts[rule] = counts.get(rule, 0) + 1
    return counts


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

    # The registry is REQUIRED, not optional. Without it every finding looks unresolved, which
    # reads as "no maintainer has responded yet" rather than as a missing input — the most
    # reassuring possible way for this dataset to be wrong.
    registry_path = data_dir / "registry" / "repos.json"
    if not registry_path.is_file():
        refuse("registry-missing")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        refuse("registry-unreadable")
    if not isinstance(registry, dict) or not isinstance(registry.get("repos"), dict):
        refuse("registry-malformed")

    outcomes, rule_of = outcomes_from_registry(registry)

    findings = {}
    audits = data_dir / "audits"
    # THE SIDECAR CARRIES NO FINGERPRINT (section 4) — skipping rows without one dropped every
    # per-audit finding, so only findings that had already reached a PR were ever counted. The
    # digest is computed, which needs the repo: recovered from the registry by slug rather than
    # by reversing the filename, because `owner-name` cannot be split back reliably when either
    # half contains a hyphen.
    # AMBIGUOUS SLUGS ARE REFUSED, not resolved by iteration order. `a/b-c` and `a-b/c` both
    # slug to `a-b-c`, so a dict comprehension silently attributes one repository's sidecar to
    # the other and computes every fingerprint under the wrong repo — records that look valid
    # and join to nothing. render-repo-report.py already refuses this; reintroducing the same
    # lossiness here would have made it a bug in one helper and a guard in another.
    slug_to_repo = {}
    for repo in registry["repos"]:
        slug = repo.replace("/", "-")
        if slug in slug_to_repo:
            print(f"REFUSE:rule-health:slug-collision {repo} and {slug_to_repo[slug]} "
                  f"both produce '{slug}'", file=sys.stderr)
            raise SystemExit(1)
        slug_to_repo[slug] = repo
    for path in sorted(audits.glob("*.findings.jsonl")) if audits.is_dir() else []:
        repo = slug_to_repo.get(path.name[:-len(".findings.jsonl")])
        if repo is None:
            print(f"WARN {path.name}: no registry repo for this slug; skipped",
                  file=sys.stderr)
            continue
        for finding in read_jsonl(path):
            key = finding.get("fingerprint") or fingerprint_of(repo, finding)
            findings.setdefault(key, finding)
            if finding.get("rule_id"):
                rule_of.setdefault(key, str(finding["rule_id"]))
    for finding in read_jsonl(data_dir / "ledgers" / "findings.jsonl"):
        if finding.get("fingerprint"):
            findings.setdefault(finding["fingerprint"], finding)
            if finding.get("rule_id"):
                rule_of.setdefault(finding["fingerprint"], str(finding["rule_id"]))

    # `finding_verified` is singular per SCHEMAS.md, unlike finding_outcome. Only the outcomes
    # that mean the finding was actually fixed count as verified; the two `persists_*` values
    # are the opposite result recorded through the same event.
    verified = {(event.get("data") or {}).get("fingerprint")
                for event in events
                if event.get("event") == "finding_verified"
                and str((event.get("data") or {}).get("outcome", "")).startswith("fixed_")}
    verified.discard(None)

    # SELF-FALSE-POSITIVES ARE A DISAGREEMENT EVENT, not a flag on a finding. SCHEMAS.md
    # section 5: the audit workflow routes a self-invalidated finding to
    # ledgers/disagreements.jsonl as `self_false_positive`, carrying fingerprint, rule_id,
    # reason and the rule_gap learning payload. Raw sidecars have no `false_positive` field at
    # all, so reading one produced a 0% false-positive rate for every rule — the most
    # flattering possible number, and the one that argues for changing nothing.
    self_fp = set()
    for record in read_jsonl(data_dir / "ledgers" / "disagreements.jsonl"):
        data = record.get("data") if isinstance(record.get("data"), dict) else record
        if record.get("event") == "self_false_positive" and data.get("fingerprint"):
            self_fp.add(str(data["fingerprint"]))
            if data.get("rule_id"):
                rule_of.setdefault(str(data["fingerprint"]), str(data["rule_id"]))

    exemplars = exemplar_counts(data_dir / "exemplars")

    rules = {}
    for fingerprint, rule in rule_of.items():
        row = rules.setdefault(rule, {"rule_id": rule, "hits": 0, "merged": 0,
                                      "applied_separately": 0, "rejected": 0, "open": 0,
                                      "cla_blocked": 0, "verified": 0, "exemplars": 0,
                                      "false_positives": 0})
        row["hits"] += 1                      # one per UNIQUE fingerprint, never per event
        outcome = outcomes.get(fingerprint)
        if outcome in PIPELINE_OUTCOMES:
            row[outcome] += 1
        if fingerprint in verified:
            row["verified"] += 1
        if fingerprint in self_fp or (findings.get(fingerprint) or {}).get("false_positive"):
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
