#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""AC-3 acceptance gate for `/vibe-suite:nl-audit` (E4.1 / vibe-35).

Grades one audit run against one seeded-defect fixture. Merge-proposal line 627 states three
assertions and this tool computes all three:

    --full   >= 75 % of the seeded classes detected, each attributed to its correct dimension
    --mini   only mini-member dimensions reported

**Why a separate tool rather than more assertions in the test suite.** Running a live judgment engine
needs a model, which CI does not have. *Grading* a run does not: it is arithmetic over two files — the
fixture's `seeded-defects.json` and the run's findings. Separating them means the gate ships and is
itself tested (`tests/test_nl_audit_acceptance.py` proves each clause can fail), while the live run
stays the operator's input. A gate nobody has watched fail is not a gate.

**Deliberate duplication.** The mini-membership table below is transcribed from F4.9 for the third
time in this change — `tests/test_nl_audit.py` holds it to assert the skill, `tests/test_nl_audit_fixtures.py`
holds it to assert the corpus, and it is here to grade runs. A shared constant would be tidier and
would let one transcription error pass all three checks unnoticed. Three independent transcriptions
of a normative table is the point, not an oversight.

Usage:

    python3 tools/nl-audit-acceptance.py <fixture-dir> --full|--mini [--findings <path>] [--json]

The record is read from `--findings <path>` (the operator's interface — a Claude Code session writes
it with the Write tool, per `tests/fixtures/nl-audit/ACCEPTANCE.md`) or from stdin (the test
interface). Both reach the same evaluation.

Exit codes are the contract:

    0  every applicable clause passed
    1  a clause failed
    2  the input was malformed -- distinct, because a gate that crashes into a pass is not a gate
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_CLAUSE_FAILED, EXIT_MALFORMED = 0, 1, 2

#: Which dimensions a `--mini` run may report, per artifact type. Transcribed from F4.9. `plugin` is
#: irregular -- D2 is full-only and D6 is mini+full -- so the table is written out per type rather
#: than generated from the D0-D3 rule the other four happen to follow.
MINI_MEMBERS = {
    "skill": {"D0", "D1", "D2", "D3"},
    "command": {"D0", "D1", "D2", "D3"},
    "agent": {"D0", "D1", "D2", "D3"},
    "rules": {"D0", "D1", "D2", "D3"},
    "plugin": {"D0", "D1", "D3", "D6"},
}


def normalize(text):
    """Class ids compare on their words, so a run may render '>500-line body' or 'over 500 line
    body' and still match the seeded class."""
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def floor_for(n):
    """>= 75 % of n, rounded up.

    `ceil`, not `round`: at n = 7, 0.75 * 7 = 5.25, and accepting 5 would be 71 % -- under the bar.
    The five artifact-type fixtures have stated floors; `mixed-repo` has none in the sources (line
    627 fixes its category span, not a count), so every floor is derived here and the stated ones are
    checked against the derivation by `tests/test_nl_audit_fixtures.py`.
    """
    return math.ceil(0.75 * n)


class Malformed(Exception):
    """The record could not be graded. Never silently treated as a failing run: 'this did not meet
    the bar' and 'I could not tell' are different answers, and only one of them is about the audit."""


def load_record(path):
    raw = Path(path).read_text(encoding="utf-8") if path else sys.stdin.read()
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Malformed("findings record is not valid JSON: %s" % exc)
    if not isinstance(record, dict):
        raise Malformed("findings record must be a JSON object")
    findings = record.get("findings")
    if not isinstance(findings, list):
        raise Malformed("findings must be a list; got %s" % type(findings).__name__)
    for entry in findings:
        if not isinstance(entry, dict):
            raise Malformed("every finding must be an object")
        if "dimension" not in entry:
            raise Malformed("finding %r has no dimension; an unattributed finding cannot be graded"
                            % entry.get("class", "<unnamed>"))
        if "class" not in entry:
            raise Malformed("finding has no class: %r" % entry)
    return record


def evaluate(spec, record, depth):
    """Return (passed, clauses). Each clause is {passed, detail}; a clause not applicable at this
    depth is omitted rather than recorded as passing."""
    seeded = {normalize(c["id"]): c["dimension"] for c in spec["classes"]}
    artifact_type = spec["type"]
    clauses = {}

    reported = {}
    for entry in record["findings"]:
        key = normalize(entry["class"])
        if key not in seeded:
            raise Malformed(
                "finding %r names a class this fixture never seeded; an invented finding would "
                "inflate the detection rate" % entry["class"])
        reported[key] = entry["dimension"]

    # --- attribution: applies at both depths -----------------------------------------------------
    wrong = {cls: (got, seeded[cls]) for cls, got in reported.items() if got != seeded[cls]}
    clauses["attribution"] = {
        "passed": not wrong,
        "detail": ("every reported class is attributed to its seeded dimension" if not wrong else
                   "; ".join("%s reported under %s, seeded as %s" % (c, g, e)
                             for c, (g, e) in sorted(wrong.items()))),
    }

    if depth == "full":
        # --- detection rate: full runs only ------------------------------------------------------
        total = len(seeded)
        floor = spec.get("floor", floor_for(total))
        found = len(reported)
        clauses["detection_rate"] = {
            "passed": found >= floor,
            "detail": "detection: %d of %d seeded classes (floor %d)" % (found, total, floor),
        }
    else:
        # --- mini exclusion: mini runs only ------------------------------------------------------
        allowed = MINI_MEMBERS.get(artifact_type)
        if allowed is None:
            clauses["mini_membership"] = {
                "passed": True,
                "detail": "mini membership is not defined for type '%s'; no exclusion applies"
                          % artifact_type,
            }
        else:
            leaked = sorted({d for d in reported.values() if d not in allowed})
            clauses["mini_membership"] = {
                "passed": not leaked,
                "detail": ("mini run reported only mini-member dimensions" if not leaked else
                           "mini run reported full-only dimensions: %s" % ", ".join(leaked)),
            }
        # The detection floor is deliberately NOT applied to a mini run: a mini audit covers fewer
        # dimensions by design, so grading it against the full-run floor would fail every correct
        # mini run. Line 627 states one assertion for mini, and it is the exclusion above.

    return all(c["passed"] for c in clauses.values()), clauses


def main(argv=None):
    parser = argparse.ArgumentParser(description="Grade an nl-audit run against a seeded fixture.")
    parser.add_argument("fixture", help="path to a tests/fixtures/nl-audit/<name> directory")
    depth = parser.add_mutually_exclusive_group(required=True)
    depth.add_argument("--full", action="store_true")
    depth.add_argument("--mini", action="store_true")
    parser.add_argument("--findings", help="path to the run's findings record (default: stdin)")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable verdict")
    args = parser.parse_args(argv)

    spec_path = Path(args.fixture) / "seeded-defects.json"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write("nl-audit-acceptance: cannot read %s: %s\n" % (spec_path, exc))
        return EXIT_MALFORMED

    depth_name = "full" if args.full else "mini"
    try:
        record = load_record(args.findings)
        passed, clauses = evaluate(spec, record, depth_name)
    except Malformed as exc:
        sys.stderr.write("nl-audit-acceptance: %s\n" % exc)
        return EXIT_MALFORMED

    if args.json:
        json.dump({"fixture": Path(args.fixture).name, "type": spec["type"], "depth": depth_name,
                   "passed": passed, "clauses": clauses}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("%s (%s, --%s)\n" % (Path(args.fixture).name, spec["type"], depth_name))
        for name, clause in clauses.items():
            sys.stdout.write("  [%s] %s: %s\n"
                             % ("PASS" if clause["passed"] else "FAIL", name, clause["detail"]))
        sys.stdout.write("  => %s\n" % ("PASS" if passed else "FAIL"))

    return EXIT_OK if passed else EXIT_CLAUSE_FAILED


if __name__ == "__main__":
    sys.exit(main())
