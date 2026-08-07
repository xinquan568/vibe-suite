#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Compare an audit's findings against a re-audit's, and record what actually changed.

    diff-findings.py --repo OWNER/NAME
                     --original-sidecar PATH --reaudit-sidecar PATH
                     --registry PATH
                     --commit-sha-before SHA --commit-sha-after SHA
                     --events-out PATH --diff-report-out PATH --summary-out PATH

All nine are required. This is the helper that decides whether a rule was VALIDATED — a finding
we reported and the maintainer fixed — so its output feeds rule health, and a wrong answer here
argues for keeping bad rules or retiring good ones.

A LINE SHIFT IS NOT A FIX, and getting this wrong is the easy mistake. The fingerprint is
`sha256("<repo>|<file>|<rule_id>|<pattern>|<line>")` — the LINE IS IN THE DIGEST. So comparing
the two sidecars by fingerprint reports that every finding below an inserted paragraph
disappeared and an equal number of brand-new ones appeared. Add one line to the top of a file
and this helper would credit the maintainer with fixing forty findings while accusing them of
introducing forty more, and every number downstream would be wrong in the same direction.

Findings are therefore matched on the line-independent identity `(file, rule_id, pattern)`:

  * IDENTICAL   — present in both, same line. Still open.
  * SHIFTED     — present in both, different line. Still open; the file moved around it.
  * FIXED       — in the original, absent from the re-audit. This is the outcome that counts.
  * INTRODUCED  — in the re-audit only. New since the audit.

BOTH SHAS ARE VALIDATED BEFORE ANY OUTPUT EXISTS. The "before" sha comes only from the
registry's `commit_sha_at_audit` and the "after" only from the re-audit clone's HEAD. Neither
may be `"unknown"`, empty, a fallback, the workflow's own commit, or the data branch's — a diff
between two commits nobody can name is not evidence, and once it is written into the ledger it
is indistinguishable from a real one. Validation happens before anything is created, truncated
or appended, so a refusal leaves the previous state exactly as it was.

EVENTS ARE APPENDED LAST, after the report and summary are safely written. The ledger is
append-only and shared; events written first would survive a later failure and permanently
claim outcomes for a comparison whose report never existed. Reruns are idempotent — an event
already recorded for the same finding and the same pair of shas is not appended twice, so
re-running after a transient failure converges instead of accumulating.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")
#: Values that have been observed standing in for a real sha. Each would produce a diff
#: attributed to a commit that does not exist.
NOT_A_SHA = frozenset({"", "unknown", "none", "null", "head", "latest"})


def refuse(reason: str) -> None:
    print(f"REFUSE:diff-findings:{reason}", file=sys.stderr)
    raise SystemExit(1)


def validate_sha(value, side: str) -> str:
    if value is None or str(value).strip() == "":
        refuse(f"commit-sha-{side}-missing")
    text = str(value).strip()
    if text.lower() in NOT_A_SHA:
        refuse(f"commit-sha-{side}-invalid")
    lowered = text.lower()
    if not SHA.match(lowered):
        refuse(f"commit-sha-{side}-invalid")
    return lowered


def read_sidecar(path: Path, label: str):
    if not path.is_file():
        refuse(f"{label}-missing")
    findings, malformed = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            findings.append(json.loads(line))
        except json.JSONDecodeError:
            malformed += 1
    return findings, malformed


def fingerprint_of(repo, finding):
    """The finding's fingerprint, computed when the record does not carry one.

    SCHEMAS.md section 4 is explicit: a per-audit sidecar carries NO timestamp, run id, repo,
    commit sha or fingerprint — the aggregation post-step enriches each line before it reaches
    `ledgers/findings.jsonl`. This helper is handed those RAW sidecars by
    auditor-case-study.yml, so requiring a fingerprint meant skipping every row and emitting no
    events whatsoever on production input, while exiting zero.

    Same digest as compute-fingerprint.sh, trailing newline included.
    """
    existing = finding.get("fingerprint")
    if existing:
        return str(existing)
    line = finding.get("line")
    payload = "|".join((
        repo,
        str(finding.get("file") or ""),
        str(finding.get("rule_id") or ""),
        str(finding.get("pattern") or ""),
        "null" if line is None or line is False else str(line),
    )) + "\n"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identity(finding):
    """The line-INDEPENDENT identity of a finding.

    Line is excluded on purpose: it is in the fingerprint, so including it here would make
    every shifted finding look like one fixed and one introduced.
    """
    return (str(finding.get("file") or ""),
            str(finding.get("rule_id") or ""),
            str(finding.get("pattern") or ""))


def line_of(finding):
    value = finding.get("line")
    return None if value is None or value is False else value


def classify(original, reaudit):
    """`(identical, shifted, fixed, introduced)`, each a list of records."""
    # Lists, not single entries: one file can carry the same rule and pattern at several
    # lines, and collapsing them loses every occurrence but one — so a maintainer who fixed
    # four of five is recorded as having fixed all five.
    before, after = {}, {}
    for finding in original:
        before.setdefault(identity(finding), []).append(finding)
    for finding in reaudit:
        after.setdefault(identity(finding), []).append(finding)

    identical, shifted, fixed, introduced = [], [], [], []
    leftover = {}
    for key, originals in before.items():
        matches = list(after.get(key, []))

        # TWO PASSES, and the order matters. Assign every exact-line match FIRST, across all
        # occurrences, before pairing anything as a shift. Processing originals in one pass
        # lets an earlier occurrence claim a later one's exact match: with lines 10, 20, 30
        # becoming 10 and 30, original-20 takes line 30 as a "shift" and original-30 is then
        # reported FIXED — while line 30 is still sitting there and line 20 is the one that
        # went. Every count is right and both attributions are wrong.
        unmatched = []
        for finding in originals:
            exact = next((m for m in matches if line_of(m) == line_of(finding)), None)
            if exact is not None:
                matches.remove(exact)
                identical.append(finding)
            else:
                unmatched.append(finding)

        for finding in unmatched:
            if matches:
                moved = matches.pop(0)
                shifted.append({**moved, "line_before": line_of(finding),
                                "line_after": line_of(moved)})
            else:
                fixed.append(finding)

        # Whatever no original claimed is genuinely new. Recomputing this by COUNT instead
        # picks occurrences by position rather than by what actually went unmatched.
        leftover[key] = matches

    for key, remaining in after.items():
        introduced.extend(leftover.get(key, []) if key in before else remaining)
    return identical, shifted, fixed, introduced


def envelope(event, data, sha_before, sha_after):
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflow": "auditor-case-study",
        "event": event,
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_number": int(os.environ.get("GITHUB_RUN_NUMBER") or 0),
        # `finding_introduced` names a single commit; only the verified events carry the
        # pair. Adding both to everything would put a field on an event whose schema has no
        # slot for it, and schema drift in an append-only ledger is not retractable.
        "data": ({**data} if "commit_sha" in data
                 else {**data, "commit_sha_before": sha_before,
                       "commit_sha_after": sha_after}),
    }


def dedupe_key(event, data):
    """The identity of an already-recorded outcome.

    Derived from the data in ONE place because the two event shapes differ: the verified events
    carry `commit_sha_before`/`commit_sha_after`, `finding_introduced` carries a single
    `commit_sha`. Building the key differently when writing and when re-reading makes every
    rerun append a second copy of an event it just decided it already had.
    """
    single = data.get("commit_sha")
    return (event, data.get("fingerprint"),
            data.get("commit_sha_before") or single,
            data.get("commit_sha_after") or single)


def already_recorded(path: Path):
    """`{(event, fingerprint, sha_before, sha_after)}` already in the ledger.

    Read so a rerun after a transient failure converges rather than appending a second copy of
    every outcome.
    """
    seen = set()
    if not path.is_file():
        return seen
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        data = record.get("data") or {}
        if record.get("event") and data.get("fingerprint"):
            seen.add(dedupe_key(record["event"], data))
    return seen


#: Registry PR outcome -> the `finding_verified` outcome for a finding that PR fixed.
FIXED_OUTCOME = {
    "merged": "fixed_and_merged",
    "applied_separately": "fixed_applied_separately",
}


def pr_attribution(entry):
    """`(fingerprint -> pr number, fingerprint -> registry outcome)`.

    The most recently updated PR wins, so a finding attempted twice is attributed to the
    maintainer's latest word rather than to whichever record happened to be read first.
    """
    pr_for, outcome_for = {}, {}
    prs = entry.get("prs") if isinstance(entry, dict) else None
    ranked = []
    for key, record in (prs or {}).items():
        if not isinstance(record, dict):
            continue
        try:
            number = int(record.get("number", key))
        except (TypeError, ValueError):
            continue
        ranked.append((str(record.get("updatedAt") or ""), number, record))
    for _, number, record in sorted(ranked, key=lambda r: (r[0], r[1])):
        for fingerprint in record.get("fingerprints") or []:
            pr_for[str(fingerprint)] = number
            outcome_for[str(fingerprint)] = record.get("outcome")
    return pr_for, outcome_for


def render_report(repo, sha_before, sha_after, identical, shifted, fixed, introduced):
    lines = [f"# Re-audit diff — {repo}", "",
             f"- before: `{sha_before}`", f"- after: `{sha_after}`", "",
             "| Outcome | Count |", "|---|---|",
             f"| fixed | {len(fixed)} |",
             f"| still open (identical) | {len(identical)} |",
             f"| still open (shifted) | {len(shifted)} |",
             f"| introduced | {len(introduced)} |", ""]
    for title, rows in (("Fixed", fixed), ("Introduced", introduced)):
        lines += [f"## {title}", ""]
        if not rows:
            lines += [f"_None._", ""]
            continue
        lines += ["| Rule | File | Line |", "|---|---|---|"]
        lines += [f"| {r.get('rule_id') or '--'} | {r.get('file') or '--'} "
                  f"| {line_of(r) if line_of(r) is not None else '--'} |" for r in rows]
        lines.append("")
    if shifted:
        lines += ["## Still open, moved", "",
                  "These are the SAME findings at new line numbers. They are not fixes.", "",
                  "| Rule | File | Before | After |", "|---|---|---|---|"]
        lines += [f"| {r.get('rule_id') or '--'} | {r.get('file') or '--'} "
                  f"| {r.get('line_before')} | {r.get('line_after')} |" for r in shifted]
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diff an audit against its re-audit.")
    for flag in ("--repo", "--original-sidecar", "--reaudit-sidecar", "--registry",
                 "--commit-sha-before", "--commit-sha-after", "--events-out",
                 "--diff-report-out", "--summary-out"):
        parser.add_argument(flag, default=None)
    args = parser.parse_args(argv)

    # --- validate everything BEFORE creating, truncating or appending any output ---------
    for flag in ("repo", "original_sidecar", "reaudit_sidecar", "registry", "events_out",
                 "diff_report_out", "summary_out"):
        if not getattr(args, flag):
            refuse(f"{flag.replace('_', '-')}-required")
    if "/" not in args.repo:
        refuse("repo-not-owner-name")

    registry_path = Path(args.registry)
    if not registry_path.is_file():
        refuse("registry-missing")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        refuse("registry-unreadable")
    repos = registry.get("repos") if isinstance(registry, dict) else None
    if not isinstance(repos, dict) or args.repo not in repos:
        refuse(f"repo-not-in-registry {args.repo}")

    sha_before = validate_sha(args.commit_sha_before, "before")
    sha_after = validate_sha(args.commit_sha_after, "after")

    original, bad_original = read_sidecar(Path(args.original_sidecar), "original-sidecar")
    reaudit, bad_reaudit = read_sidecar(Path(args.reaudit_sidecar), "reaudit-sidecar")

    identical, shifted, fixed, introduced = classify(original, reaudit)
    summary = {
        "repo": args.repo,
        "commit_sha_before": sha_before,
        "commit_sha_after": sha_after,
        "counts": {"fixed": len(fixed), "identical": len(identical),
                   "shifted": len(shifted), "introduced": len(introduced),
                   "original_total": len(original), "reaudit_total": len(reaudit)},
        "malformed_lines": {"original": bad_original, "reaudit": bad_reaudit},
        "fixed": sorted(fingerprint_of(args.repo, f) for f in fixed),
        "introduced": sorted(fingerprint_of(args.repo, f) for f in introduced),
    }

    # --- report and summary first; the ledger is append-only and cannot be taken back ----
    report_path = Path(args.diff_report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(args.repo, sha_before, sha_after, identical, shifted, fixed, introduced),
        encoding="utf-8")

    summary_path = Path(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
                            + "\n", encoding="utf-8")

    # --- then the events -----------------------------------------------------------------
    events_path = Path(args.events_out)
    events_path.parent.mkdir(parents=True, exist_ok=True)
    seen = already_recorded(events_path)

    # SCHEMAS.md: `finding_verified` records BOTH results through one event name, with the
    # outcome saying which. Emitting it only for fixes loses the other half of the evidence —
    # a rule whose findings persist looks merely unreported rather than unheeded.
    #
    # A fix is attributed to the PR that carried it, and the PR's registry outcome decides
    # which `fixed_*` value applies. Without that attribution every fix reads the same, and a
    # fix the maintainer made themselves is indistinguishable from one we merged.
    pr_for, outcome_for = pr_attribution(repos.get(args.repo))

    pending = []
    for finding in fixed:
        fingerprint = fingerprint_of(args.repo, finding)
        pr_number = pr_for.get(fingerprint)
        pending.append(("finding_verified", fingerprint, {
            "repo": args.repo,
            "fingerprint": fingerprint,
            "rule_id": finding.get("rule_id"),
            "file": finding.get("file"),
            "pattern": finding.get("pattern"),
            "outcome": FIXED_OUTCOME.get(outcome_for.get(fingerprint),
                                         "fixed_upstream_not_merged"),
            "pr_number": pr_number,
        }))
    for finding in identical:
        fingerprint = fingerprint_of(args.repo, finding)
        if fingerprint:
            pending.append(("finding_verified", fingerprint, {
                "repo": args.repo, "fingerprint": fingerprint,
                "rule_id": finding.get("rule_id"), "file": finding.get("file"),
                "pattern": finding.get("pattern"), "outcome": "persists_identically",
                "pr_number": pr_for.get(fingerprint),
            }))
    for finding in shifted:
        fingerprint = fingerprint_of(args.repo, finding)
        if fingerprint:
            pending.append(("finding_verified", fingerprint, {
                "repo": args.repo, "fingerprint": fingerprint,
                "rule_id": finding.get("rule_id"), "file": finding.get("file"),
                "pattern": finding.get("pattern"), "outcome": "persists_line_shifted",
                "pr_number": pr_for.get(fingerprint),
            }))
    for finding in introduced:
        fingerprint = fingerprint_of(args.repo, finding)
        if fingerprint:
            pending.append(("finding_introduced", fingerprint, {
                "repo": args.repo, "fingerprint": fingerprint,
                "rule_id": finding.get("rule_id"), "file": finding.get("file"),
                "pattern": finding.get("pattern"), "severity": finding.get("severity"),
                # `finding_introduced` takes a single `commit_sha` — the commit it appeared in.
                "commit_sha": sha_after,
            }))

    envelopes = []
    for event, _fingerprint, data in pending:
        # Key off the envelope's data, i.e. the record as it will be STORED. Keying off `data`
        # first is subtly wrong: envelope() is what adds the sha pair to the verified events,
        # so the key computed here would carry no shas while the key computed when re-reading
        # carries both — and every rerun appends a second copy of an event it had just decided
        # it already held.
        wrapped = envelope(event, data, sha_before, sha_after)
        key = dedupe_key(event, wrapped["data"])
        if key in seen:
            continue
        seen.add(key)
        envelopes.append(wrapped)
    pending = envelopes

    if pending:
        existing = events_path.read_text(encoding="utf-8") if events_path.is_file() else ""
        with events_path.open("a", encoding="utf-8") as handle:
            if existing and not existing.endswith("\n"):
                handle.write("\n")
            for event in pending:
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"diff-findings: {len(fixed)} fixed, {len(identical)} identical, "
          f"{len(shifted)} shifted, {len(introduced)} introduced; "
          f"{len(pending)} event(s) appended")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
