#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""AC-3 acceptance gate for `/vibe-suite:roast` (E4.3 / vibe-37).

Validates one roast report against `tests/fixtures/sample-repo/seeded-issues.json`. Merge-proposal
line 628 fixes four structural assertions and scopes two of them by lane:

    always          the report carries its frontmatter keys
    always          every fixing-plan item cites a finding id that exists in the report
    --engine claude one `## [Agent: <name>] Findings` section per dispatched agent
    --engine codex  all nine cc-suite audit dimensions represented
    --engine agy    same as codex (conditional on the E1.7 gate, which is shut)

**Why a tool rather than assertions inside the test module.** Producing a report needs a live engine,
which CI has none of; *grading* one is arithmetic over two files. Separating them means the gate ships
and is itself tested — `tests/test_roast_acceptance.py` proves each assertion can fail — while the
live run stays the operator's, per `tests/fixtures/sample-repo/ACCEPTANCE.md`. A gate nobody has
watched fail is not a gate.

Usage:

    python3 tools/roast-acceptance.py <fixture-dir> --report <path> --lane claude|codex|agy [--json]

Exit codes are the contract:

    0  every applicable assertion passed
    1  an assertion failed
    2  the input was malformed -- distinct, because a gate that crashes into a pass is not a gate
"""

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_FAILED, EXIT_MALFORMED = 0, 1, 2

#: Frontmatter keys every roast report carries. `version` is read from the plugin manifest at run
#: time and never hardcoded (F3.1, fixing grill's W2), so its presence is checked and its value is
#: not compared to a literal.
REQUIRED_FRONTMATTER = ("target", "engine", "style", "generated", "version")

#: The in-session agents a roast dispatches. Styles 1-4 dispatch the first four; styles 5-6 add
#: edge-cases. recon runs first in every style but is a survey, not a findings section.
CLAUDE_AGENTS_BASE = ("architecture", "error-handling", "security", "testing")
CLAUDE_AGENTS_PARANOID = CLAUDE_AGENTS_BASE + ("edge-cases",)

AGENT_SECTION = re.compile(r"(?m)^##\s+\[Agent:\s*vibe-suite:([a-z-]+)\]\s+Findings\s*$")
DIMENSION_SECTION = re.compile(r"(?m)^##\s+Dimension:\s*(.+?)\s*$")
FINDING_ID = re.compile(r"\b([A-Z]{1,4}-\d+)\b")


class Malformed(Exception):
    """The report could not be graded. Never silently treated as a failing report: 'this did not meet
    the bar' and 'I could not read it' are different answers, and only one is about the roast."""


def split_frontmatter(text):
    if not text.startswith("---\n"):
        raise Malformed("report has no YAML frontmatter")
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise Malformed("report frontmatter is not terminated")
    keys = {}
    for line in parts[1].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            k, _, v = line.partition(":")
            keys[k.strip()] = v.strip()
    return keys, parts[2]


def split_plan(body):
    """(everything before the Fixing plan section, the Fixing plan section).

    The split matters for traceability: finding ids must be collected from the FINDINGS, not from the
    whole document. Scanning the whole body lets a plan item cite `SR-9`, and that citation is itself
    an occurrence of `SR-9` in the body -- so every item validates itself and the check passes
    vacuously. Found by its own seeded-failure test.
    """
    m = re.search(r"(?m)^##\s+Fixing plan\s*$", body, re.I)
    if not m:
        raise Malformed("report has no '## Fixing plan' section")
    rest = body[m.end():]
    nxt = re.search(r"(?m)^##\s+", rest)
    section = rest[: nxt.start()] if nxt else rest
    trailing = rest[nxt.start():] if nxt else ""
    return body[: m.start()] + trailing, section


def fixing_plan_items(body):
    """Every list item under the Fixing Plan heading, with the phase it sits in.

    Phases matter: an item outside any phase and an item citing nothing are different defects, so the
    caller needs to tell them apart.
    """
    _, section = split_plan(body)
    items, phase = [], None
    for line in section.splitlines():
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        if heading:
            phase = heading.group(1).strip()
            continue
        if re.match(r"^\s*[-*]\s+\S", line):
            items.append((phase, line.strip()))
    return items


def evaluate(spec, report, lane, style):
    keys, body = split_frontmatter(report)
    dimensions = [i["dimension"] for i in spec["issues"]]
    checks = {}

    missing = [k for k in REQUIRED_FRONTMATTER if k not in keys]
    checks["frontmatter"] = {
        "passed": not missing,
        "detail": "all required keys present" if not missing else "missing: %s" % ", ".join(missing),
    }

    if not re.search(r"(?m)^##\s+Executive summary\s*$", body, re.I):
        checks["executive_summary"] = {"passed": False, "detail": "no '## Executive summary' section"}
    else:
        checks["executive_summary"] = {"passed": True, "detail": "present"}

    findings_text, _ = split_plan(body)
    reported_ids = set(FINDING_ID.findall(findings_text))
    items = fixing_plan_items(body)
    unphased = [i for phase, i in items if phase is None]
    untraceable = [i for _, i in items if not (set(FINDING_ID.findall(i)) & reported_ids)]
    checks["fixing_plan_phased"] = {
        "passed": bool(items) and not unphased,
        "detail": "no fixing-plan items" if not items else
                  ("every item sits in a phase" if not unphased
                   else "%d item(s) outside any phase" % len(unphased)),
    }
    checks["fixing_plan_traceable"] = {
        "passed": bool(items) and not untraceable,
        "detail": "every item cites a finding present in the report" if items and not untraceable
                  else "%d item(s) cite no finding in the report" % len(untraceable),
    }

    if lane == "claude":
        expected = set(CLAUDE_AGENTS_PARANOID if style in (5, 6) else CLAUDE_AGENTS_BASE)
        found = set(AGENT_SECTION.findall(body))
        checks["agent_sections"] = {
            "passed": found == expected,
            "detail": "expected %s, found %s" % (sorted(expected), sorted(found)),
        }
    else:
        found = {d.strip() for d in DIMENSION_SECTION.findall(body)}
        absent = [d for d in dimensions if d not in found]
        checks["dimensions"] = {
            "passed": not absent,
            "detail": "all %d dimensions represented" % len(dimensions) if not absent
                      else "absent: %s" % ", ".join(absent),
        }

    return all(c["passed"] for c in checks.values()), checks


def main(argv=None):
    parser = argparse.ArgumentParser(description="Grade a roast report against a seeded fixture.")
    parser.add_argument("fixture")
    parser.add_argument("--report", required=True)
    parser.add_argument("--lane", required=True, choices=("claude", "codex", "agy"))
    parser.add_argument("--style", type=int, default=6)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        spec = json.loads((Path(args.fixture) / "seeded-issues.json").read_text(encoding="utf-8"))
        report = Path(args.report).read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc:
        sys.stderr.write("roast-acceptance: cannot read input: %s\n" % exc)
        return EXIT_MALFORMED

    try:
        passed, checks = evaluate(spec, report, args.lane, args.style)
    except Malformed as exc:
        sys.stderr.write("roast-acceptance: %s\n" % exc)
        return EXIT_MALFORMED

    if args.json:
        json.dump({"fixture": Path(args.fixture).name, "lane": args.lane, "style": args.style,
                   "passed": passed, "checks": checks}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("%s (--engine %s, --style %d)\n"
                         % (Path(args.fixture).name, args.lane, args.style))
        for name, c in checks.items():
            sys.stdout.write("  [%s] %s: %s\n"
                             % ("PASS" if c["passed"] else "FAIL", name, c["detail"]))
        sys.stdout.write("  => %s\n" % ("PASS" if passed else "FAIL"))
    return EXIT_OK if passed else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
