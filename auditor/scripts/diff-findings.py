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
    before = {}
    for finding in original:
        before.setdefault(identity(finding), finding)
    after = {}
    for finding in reaudit:
        after.setdefault(identity(finding), finding)

    identical, shifted, fixed, introduced = [], [], [], []
    for key, finding in before.items():
        match = after.get(key)
        if match is None:
            fixed.append(finding)
        elif line_of(match) == line_of(finding):
            identical.append(finding)
        else:
            shifted.append({**match, "line_before": line_of(finding),
                            "line_after": line_of(match)})
    for key, finding in after.items():
        if key not in before:
            introduced.append(finding)
    return identical, shifted, fixed, introduced


def envelope(event, data, sha_before, sha_after):
    return {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflow": "auditor-case-study",
        "event": event,
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_number": int(os.environ.get("GITHUB_RUN_NUMBER") or 0),
        "data": {**data, "commit_sha_before": sha_before, "commit_sha_after": sha_after},
    }


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
            seen.add((record["event"], data["fingerprint"],
                      data.get("commit_sha_before"), data.get("commit_sha_after")))
    return seen


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
        "fixed": sorted(f.get("fingerprint") for f in fixed if f.get("fingerprint")),
        "introduced": sorted(f.get("fingerprint") for f in introduced if f.get("fingerprint")),
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

    pending = []
    for finding in fixed:
        key = ("finding_verified", finding.get("fingerprint"), sha_before, sha_after)
        if finding.get("fingerprint") and key not in seen:
            seen.add(key)
            pending.append(envelope("finding_verified", {
                "repo": args.repo, "fingerprint": finding["fingerprint"],
                "rule_id": finding.get("rule_id"), "file": finding.get("file"),
            }, sha_before, sha_after))
    for finding in introduced:
        key = ("finding_introduced", finding.get("fingerprint"), sha_before, sha_after)
        if finding.get("fingerprint") and key not in seen:
            seen.add(key)
            pending.append(envelope("finding_introduced", {
                "repo": args.repo, "fingerprint": finding["fingerprint"],
                "rule_id": finding.get("rule_id"), "file": finding.get("file"),
            }, sha_before, sha_after))

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
