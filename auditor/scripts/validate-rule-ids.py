#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Check audit findings against the scoring rubric.

    validate-rule-ids.py [--data-dir DIR] [--rubric PATH] [SIDECAR ...]

With sidecars named explicitly, every one must exist. With none, every
`<data-dir>/audits/*.findings.jsonl` is checked; an absent audits directory means there is
nothing to check, not a failure.

WHY THIS IS NOT A MEMBERSHIP TEST. The obvious implementation asks "is this rule id in the
catalog?", and that implementation would have passed the audit this helper exists because of.
The scoring skill records it: a 2026-05-13 audit applied "R07 / -15" fourteen times, wrong on
both counts — R07 is the Skills scope-note row worth -3, and -15 is a value from the Agents
table. R07 exists, so a membership test says the finding is fine. Fourteen wrong findings went
out to a maintainer under a rule id that had nothing to do with them.

A rule id is only meaningful together with the table it was read from and the check it names,
so three things are compared, not one:

  * ARTIFACT-TYPE DRIFT — the id is real but does not appear in the table for this finding's
    artifact type. The auditor read the right row number from the wrong table.
  * PENALTY DRIFT — the id and table are right but the penalty belongs to no row under them.
    This is the -15 half of the incident above, and it is what makes a score wrong rather than
    merely mislabelled.
  * SEMANTIC-TITLE DRIFT — the id, table and penalty are right but the finding describes a
    different check from the one that row is about. This is the half a maintainer notices,
    because the rule they are pointed at plainly does not say what the finding claims.

Findings marked `false_positive` are still checked. A false positive with a wrong rule id is
evidence about the rulebook — it is the case where an auditor reached for a rule that does not
fit — and skipping those would hide exactly the drift worth reading.

Rows whose Rule column is `--` are checks with no dedicated id. They are not loaded, so a
finding claiming one of their penalties under a real id is caught as penalty drift.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUBRIC = ROOT / "skills" / "scoring" / "SKILL.md"

#: Sidecar `category` -> the rubric section heading it must be scored against. Matched on the
#: heading PREFIX: the real headings carry long parentheticals ("Hooks (Codex CLI, Tier
#: 2-Codex)") that are editorial and change without the table changing.
SECTION_FOR = {
    "skill": "Skills", "skills": "Skills",
    "agent": "Agents", "agents": "Agents",
    "command": "Commands", "commands": "Commands",
    "shared-partial": "Shared Partials", "partial": "Shared Partials",
    "rule": "Rules", "rules": "Rules",
    "hook": "Hooks", "hooks": "Hooks",
    "memory": "Memory files", "claude.md": "CLAUDE.md",
    "plugin": "plugin.json", "settings": "Settings files",
}

RULE_ID = re.compile(r"^R\d{1,2}$")


def refuse(reason: str) -> None:
    print(f"REFUSE:validate-rule-ids:{reason}", file=sys.stderr)
    raise SystemExit(1)


def normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def load_rubric(path: Path):
    """`{section: {rule_id: [{check, condition, penalty}, ...]}}`.

    Section keys are the heading text up to the first parenthesis or dash, so a retitled
    parenthetical does not silently empty a table.
    """
    catalog: dict[str, dict[str, list[dict]]] = {}
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            section = re.split(r"\s*[(—-]", line[4:].strip(), 1)[0].strip()
            catalog.setdefault(section, {})
            continue
        if section is None or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not RULE_ID.match(cells[0]):
            continue
        penalty = re.search(r"-\d+", cells[3])
        catalog[section].setdefault(cells[0], []).append({
            "check": cells[1],
            "condition": cells[2],
            "penalty": int(penalty.group()) if penalty else None,
        })
    return catalog


def section_for(category, catalog):
    """The rubric section a finding's category maps to, or None if it names none."""
    wanted = SECTION_FOR.get(str(category or "").strip().lower())
    if wanted is None:
        return None
    for name in catalog:
        if name.lower().startswith(wanted.lower()):
            return name
    return None


def check_finding(finding, catalog, known_ids):
    """Every drift this finding shows, as a list of short reasons."""
    rule = str(finding.get("rule_id") or "").strip()
    if not rule or rule == "--":
        return []
    if rule not in known_ids:
        return [f"unknown-rule-id {rule}"]

    section = section_for(finding.get("category"), catalog)
    if section is None:
        # An unmapped category cannot be checked against a table. Say so rather than passing
        # it silently, which would make an unrecognised category a way to bypass this check.
        return [f"unmapped-category {finding.get('category')!r} for {rule}"]

    rows = catalog.get(section, {}).get(rule)
    if not rows:
        return [f"artifact-type-drift {rule} is not a '{section}' rule"]

    problems = []
    penalty = finding.get("penalty")
    if penalty is not None:
        allowed = {row["penalty"] for row in rows if row["penalty"] is not None}
        if allowed and int(penalty) not in allowed:
            problems.append(f"penalty-drift {rule} under '{section}' allows "
                            f"{sorted(allowed)}, finding says {int(penalty)}")

    haystack = normalise(f"{finding.get('check', '')} {finding.get('description', '')}")
    if haystack:
        # A shared word is enough. This is drift detection, not prose matching: the finding is
        # written for a maintainer and will not repeat the rubric's wording, so the bar is that
        # it is recognisably ABOUT the same check rather than phrased like it.
        vocabulary = {word for row in rows for word in normalise(row["check"]).split()
                      if len(word) > 3}
        if vocabulary and not (vocabulary & set(haystack.split())):
            problems.append(f"semantic-title-drift {rule} is "
                            f"{'/'.join(sorted({r['check'] for r in rows}))!r}, finding is "
                            f"{str(finding.get('check') or finding.get('description'))[:60]!r}")
    return problems


def read_findings(path: Path):
    findings, malformed = [], 0
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            findings.append((lineno, json.loads(line)))
        except json.JSONDecodeError:
            malformed += 1
    return findings, malformed


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check findings against the scoring rubric.")
    parser.add_argument("sidecars", nargs="*", help="explicit sidecars; default <data-dir>/audits")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--rubric", default=None)
    args = parser.parse_args(argv)

    rubric = Path(args.rubric) if args.rubric else DEFAULT_RUBRIC
    if not rubric.is_file():
        refuse("rubric-missing")
    catalog = load_rubric(rubric)
    known_ids = {rule for table in catalog.values() for rule in table}
    if not known_ids:
        refuse("rubric-empty")

    if args.sidecars:
        # Named explicitly means the caller asserts it exists. Silently skipping a missing one
        # would report "no drift" for a file that was never opened.
        targets = [Path(p) for p in args.sidecars]
        for path in targets:
            if not path.is_file():
                refuse("input-missing")
    else:
        if not args.data_dir:
            refuse("data-dir-required")
        audits = Path(args.data_dir) / "audits"
        targets = sorted(audits.glob("*.findings.jsonl")) if audits.is_dir() else []

    drifted = 0
    for path in targets:
        findings, malformed = read_findings(path)
        if malformed:
            print(f"WARN {path}: {malformed} malformed line(s) skipped", file=sys.stderr)
        for lineno, finding in findings:
            for problem in check_finding(finding, catalog, known_ids):
                drifted += 1
                print(f"{path}:{lineno}: {problem}")

    print(f"validate-rule-ids: {len(targets)} sidecar(s), {drifted} drift(s)")
    return 1 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
