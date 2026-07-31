#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Seeded-failure tests for the roast acceptance gate (E4.3 / vibe-37).

`tools/roast-acceptance.py` decides whether a roast report met AC-3's structural assertions. A gate
nobody has watched fail is not a gate, so every assertion it makes has a case here that **passes** and
a case that **fails**.

The reports below are synthetic, so the whole module is hermetic: no engine, no network, no
credentials. That is the same split link 1 (vibe-35) landed on — producing a report needs a live
model, grading one is arithmetic over two files.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "roast-acceptance.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample-repo"

EXIT_OK, EXIT_FAILED, EXIT_MALFORMED = 0, 1, 2

FRONTMATTER = """---
target: tests/fixtures/sample-repo
engine: {engine}
style: {style}
generated: 2026-07-31-0930
version: 0.0.1
---
"""


def dimensions():
    spec = json.loads((FIXTURE / "seeded-issues.json").read_text(encoding="utf-8"))
    return [i["dimension"] for i in spec["issues"]]


def report(engine="codex", style=6, *, frontmatter=True, summary=True, sections=None,
           findings=("SR-1",), plan=(("Phase 1 — now", "SR-1"),), plan_present=True):
    """A synthetic roast report. Every knob corresponds to one assertion the gate makes."""
    out = FRONTMATTER.format(engine=engine, style=style) if frontmatter else ""
    if summary:
        out += "\n## Executive summary\n\nOne [HIGH] finding; act on SR-1 first.\n"
    for section in (sections if sections is not None else
                    ["## Dimension: %s" % d for d in dimensions()]):
        out += "\n%s\n\n- %s: something is wrong here.\n" % (section, findings[0])
    for fid in findings[1:]:
        out += "\n- %s: another finding.\n" % fid
    if plan_present:
        out += "\n## Fixing plan\n"
        for phase, item in plan:
            if phase is not None:
                out += "\n### %s\n" % phase
            out += "\n- Fix %s in the named file.\n" % item
    return out


def run(text, lane="codex", style=6, fixture=None):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(text)
        path = fh.name
    try:
        return subprocess.run(
            [sys.executable, str(TOOL), str(fixture or FIXTURE), "--report", path,
             "--lane", lane, "--style", str(style)],
            capture_output=True, text=True, cwd=REPO_ROOT)
    finally:
        Path(path).unlink(missing_ok=True)


class GateTestCase(unittest.TestCase):
    def setUp(self):
        if not TOOL.is_file():
            self.skipTest("tools/roast-acceptance.py does not exist yet")
        if not (FIXTURE / "seeded-issues.json").is_file():
            self.skipTest("the sample-repo fixture does not exist yet")


class TestCodexLane(GateTestCase):
    def test_a_complete_report_passes(self):
        proc = run(report())
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)

    def test_a_missing_dimension_fails(self):
        """The seeded failure for AC-3's 'all nine dimensions represented'."""
        sections = ["## Dimension: %s" % d for d in dimensions()[:-1]]
        proc = run(report(sections=sections))
        self.assertEqual(proc.returncode, EXIT_FAILED)
        self.assertIn("absent", proc.stdout + proc.stderr)

    def test_all_nine_dimensions_are_required_not_a_majority(self):
        for drop in range(len(dimensions())):
            keep = [d for i, d in enumerate(dimensions()) if i != drop]
            with self.subTest(dropped=dimensions()[drop]):
                proc = run(report(sections=["## Dimension: %s" % d for d in keep]))
                self.assertEqual(proc.returncode, EXIT_FAILED)


class TestClaudeLane(GateTestCase):
    def _agent_sections(self, names):
        return ["## [Agent: vibe-suite:%s] Findings" % n for n in names]

    def test_styles_1_to_4_expect_four_agents(self):
        proc = run(report(engine="claude",
                          sections=self._agent_sections(
                              ("architecture", "error-handling", "security", "testing"))),
                   lane="claude", style=2)
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)

    def test_styles_5_and_6_expect_five_agents(self):
        four = ("architecture", "error-handling", "security", "testing")
        proc = run(report(engine="claude", sections=self._agent_sections(four)),
                   lane="claude", style=6)
        self.assertEqual(proc.returncode, EXIT_FAILED,
                         "styles 5-6 add edge-cases; four sections must not pass")
        proc = run(report(engine="claude", sections=self._agent_sections(four + ("edge-cases",))),
                   lane="claude", style=6)
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)

    def test_an_unqualified_agent_name_is_not_recognised(self):
        """The schema's enum requires the qualified form; a bare name would bypass its variant rules."""
        proc = run(report(engine="claude",
                          sections=["## [Agent: architecture] Findings",
                                    "## [Agent: vibe-suite:error-handling] Findings",
                                    "## [Agent: vibe-suite:security] Findings",
                                    "## [Agent: vibe-suite:testing] Findings"]),
                   lane="claude", style=2)
        self.assertEqual(proc.returncode, EXIT_FAILED)


class TestReportStructure(GateTestCase):
    def test_missing_frontmatter_key_fails(self):
        text = report().replace("style: 6\n", "")
        proc = run(text)
        self.assertEqual(proc.returncode, EXIT_FAILED)
        self.assertIn("style", proc.stdout + proc.stderr)

    def test_missing_executive_summary_fails(self):
        proc = run(report(summary=False))
        self.assertEqual(proc.returncode, EXIT_FAILED)
        self.assertIn("executive_summary", proc.stdout + proc.stderr)

    def test_an_unphased_fixing_plan_item_fails(self):
        proc = run(report(plan=((None, "SR-1"),)))
        self.assertEqual(proc.returncode, EXIT_FAILED)
        self.assertIn("phase", proc.stdout + proc.stderr)

    def test_an_item_citing_a_finding_that_is_not_in_the_report_fails(self):
        """Traceability: an item may cite only a finding the report actually raised."""
        proc = run(report(findings=("SR-1",), plan=(("Phase 1 — now", "SR-9"),)))
        self.assertEqual(proc.returncode, EXIT_FAILED)
        self.assertIn("cite", proc.stdout + proc.stderr)

    def test_phasing_and_traceability_fail_independently(self):
        """Two different defects: an item outside a phase, and an item citing nothing real. One
        assertion cannot catch both, so each is checked on its own."""
        proc = subprocess.run(
            [sys.executable, str(TOOL), str(FIXTURE), "--lane", "codex", "--json", "--report",
             self._write(report(plan=((None, "SR-1"),)))],
            capture_output=True, text=True, cwd=REPO_ROOT)
        checks = json.loads(proc.stdout)["checks"]
        self.assertFalse(checks["fixing_plan_phased"]["passed"])
        self.assertTrue(checks["fixing_plan_traceable"]["passed"])

    def _write(self, text):
        fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False)
        fh.write(text)
        fh.close()
        self.addCleanup(lambda: Path(fh.name).unlink(missing_ok=True))
        return fh.name


class TestMalformedInput(GateTestCase):
    def test_a_report_without_frontmatter_is_malformed(self):
        proc = run("# just a heading\n\nno frontmatter at all\n")
        self.assertEqual(proc.returncode, EXIT_MALFORMED)

    def test_a_report_without_a_fixing_plan_is_malformed(self):
        proc = run(report(plan_present=False))
        self.assertEqual(proc.returncode, EXIT_MALFORMED)

    def test_an_unreadable_fixture_is_malformed(self):
        proc = run(report(), fixture=REPO_ROOT / "tests" / "fixtures" / "no-such-fixture")
        self.assertEqual(proc.returncode, EXIT_MALFORMED)


class TestToolDiscipline(unittest.TestCase):
    """`tools/` is in model-pin-lint.py's EXCLUDED set ("not shipped as plugin functionality"), so the
    repo-wide P9 scan does not reach this file. The check is placed here rather than assumed."""

    def test_no_pinned_model_id(self):
        if not TOOL.is_file():
            self.skipTest("tool does not exist yet")
        import re
        pattern = re.compile(
            r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})",
            re.I)
        self.assertIsNone(pattern.search(TOOL.read_text(encoding="utf-8")))

    def test_isc_spdx_header(self):
        if not TOOL.is_file():
            self.skipTest("tool does not exist yet")
        head = TOOL.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in line for line in head))

    def test_the_acceptance_runbook_exists(self):
        self.assertTrue((FIXTURE / "ACCEPTANCE.md").is_file(),
                        "the operator's runbook is what makes the live half of AC-3 performable")


if __name__ == "__main__":
    unittest.main()
