# SPDX-License-Identifier: ISC
"""E3.6 (vibe-31) acceptance: /vibe-suite:test — NL-TDD spec runner + suite specs.

Rung 0/1 pins contracts and fixtures (the judgment-lane precedent): the frozen 14-spec
coverage (AC-7), per-spec schema and depth (frozen plan D8), the command's report and
discovery contract (D1-D3, D6, D7), the tester agent's evaluation contract including
the exact score-engine invocation (D5), and both mandated fixtures. Runtime prediction
quality is the tester's judgment lane and is not simulated here.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS = REPO_ROOT / ".vibe-test"
COMMAND = REPO_ROOT / "commands" / "test.md"
TESTER = REPO_ROOT / "agents" / "tester.md"
FIX = REPO_ROOT / "tests" / "fixtures" / "vibe-test-runner"

#: §5.0's frozen agent inventory — AC-7's "14/14" is exactly this list.
FOURTEEN = [
    "recon", "architecture", "error-handling", "security", "testing", "edge-cases",
    "scanner", "scorer", "vague-scanner", "checker", "tester",
    "vocab-drift-scanner", "security-scanner", "spec-researcher",
]
#: The five artifacts this stage delivers (four shipped + tester from this item).
STAGE_DELIVERED = ["scanner", "scorer", "vague-scanner", "checker", "tester"]

SECTIONS = ["Triggers On", "Does Not Trigger On", "Output Contains", "Frontmatter Valid"]


def spec_frontmatter(text):
    lines = text.split("\n")
    assert lines[0] == "---"
    keys = {}
    for line in lines[1:]:
        if line == "---":
            return keys
        m = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if m:
            keys[m.group(1)] = m.group(2).strip()
    raise AssertionError("unterminated frontmatter")


def section_items(text, heading):
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text,
                  re.M | re.S)
    if m is None:
        return None
    return [l for l in m.group(1).splitlines() if l.strip().startswith("- ")]


class SpecCoverage(unittest.TestCase):
    def test_fourteen_of_fourteen_no_extras(self):
        on_disk = sorted(p.name for p in SPECS.glob("*.spec.md"))
        self.assertEqual(on_disk, sorted(f"{n}.spec.md" for n in FOURTEEN))

    def test_per_spec_schema_and_depth(self):
        for name in FOURTEEN:
            with self.subTest(spec=name):
                text = (SPECS / f"{name}.spec.md").read_text(encoding="utf-8")
                fm = spec_frontmatter(text)
                self.assertEqual(sorted(fm), ["artifact", "min_score", "type"])
                self.assertEqual(fm["artifact"], f"agents/{name}.md")
                self.assertEqual(fm["type"], "agent")
                self.assertEqual(fm["min_score"], "80")
                for heading, minimum in (("Triggers On", 5),
                                         ("Does Not Trigger On", 3),
                                         ("Output Contains", 2),
                                         ("Frontmatter Valid", 1)):
                    items = section_items(text, heading)
                    self.assertIsNotNone(items, f"{name}: missing section {heading}")
                    self.assertGreaterEqual(
                        len(items), minimum,
                        f"{name}: {heading} needs >={minimum} items")
                headings = re.findall(r"^## (.+)$", text, re.M)
                self.assertTrue(set(headings) <= set(SECTIONS),
                                f"{name}: headings outside the skill vocabulary")
                self.assertIn("Source:", text,
                              f"{name}: missing the source-spec provenance line")

    def test_stage_delivered_artifacts_resolve(self):
        for name in STAGE_DELIVERED:
            self.assertTrue((REPO_ROOT / "agents" / f"{name}.md").is_file(), name)


class CommandContract(unittest.TestCase):
    def _body(self):
        return COMMAND.read_text(encoding="utf-8")

    def test_report_format(self):
        body = self._body()
        self.assertIn("Vibe Suite Test Report", body)
        self.assertIn("| Spec | Artifact | Result | Details |", body)
        self.assertIn("N/M checks", body)
        self.assertIn("RED items (fix these):", body)
        self.assertIn("N passed, N failed (percent%)", body)

    def test_failure_line_formats(self):
        body = self._body()
        self.assertIn('✗ "<query>" → predicted <YES|NO> trigger (expected <YES|NO>)',
                      body)
        self.assertIn("confidence: high|medium|low", body)
        self.assertIn("✗ score <n>/100 (min: <m>)", body)
        self.assertIn("✗ frontmatter: missing '<key>'", body)
        self.assertIn("✗ frontmatter: '<key>' not <requirement>", body)
        self.assertIn('✗ output: missing "<element>"', body)
        self.assertIn("✗ rule: violation sample not flagged", body)
        self.assertIn("✗ rule: compliant sample flagged", body)
        self.assertIn("✗ artifact missing (RED)", body)

    def test_discovery_and_batching(self):
        body = self._body()
        self.assertIn(".vibe-test/", body)
        self.assertIn(".nlpm-test/", body)
        self.assertRegex(body, r"(?i)never renamed|run as-is|no rename")
        self.assertRegex(body, r"(?i)new specs .*\.vibe-test")
        self.assertRegex(body, r"(?i)collision.*new dir|new directory wins")
        self.assertRegex(body, r"(?i)batches of (up to )?3|≤3")
        self.assertRegex(body, r"(?i)sorted")
        self.assertIn("skills/testing/SKILL.md", body)

    def test_registered(self):
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/test.md", manifest["commands"])
        self.assertIn("./agents/tester.md", manifest["agents"])
        self.assertEqual(len(manifest["commands"]), 16)
        self.assertEqual(len(manifest["agents"]), 5)


class TesterContract(unittest.TestCase):
    def _body(self):
        return TESTER.read_text(encoding="utf-8")

    def test_five_lanes_and_prediction_rule(self):
        body = self._body().lower()
        for lane in ("frontmatter", "trigger", "output", "rule", "min_score"):
            self.assertIn(lane, body)
        self.assertRegex(body, r"predict")
        self.assertRegex(body, r"(?i)never (executed|invoked)|not executed")

    def test_score_engine_invocation_contract(self):
        body = self._body()
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/score_engine.py"', body)
        self.assertIn("--root", body)
        self.assertIn("\\x1f", body)
        self.assertIn("\\x00", body)
        self.assertIn("files[0].score", body)
        self.assertRegex(body, r"(?i)ignore.*files\[0\]\.verdict|verdict.*ignored")
        self.assertRegex(body, r"(?i)exist(ence|s) .*before|checked? first")
        self.assertRegex(body, r"(?i)no positional")
        self.assertRegex(body, r"(?is)exits? 2.*(that spec|alone)")
        self.assertRegex(body, r"(?i)batch continues")

    def test_missing_artifact_red(self):
        self.assertIn("artifact missing (RED)", self._body())


class Fixtures(unittest.TestCase):
    def test_ghost_fixture(self):
        text = (FIX / "missing-artifact" / ".vibe-test" / "ghost.spec.md").read_text(
            encoding="utf-8")
        fm = spec_frontmatter(text)
        self.assertEqual(fm["artifact"], "agents/ghost.md")
        self.assertFalse((REPO_ROOT / "agents" / "ghost.md").exists())
        self.assertFalse((FIX / "missing-artifact" / "agents" / "ghost.md").exists())

    def test_legacy_fixture_self_contained(self):
        root = FIX / "legacy"
        spec = root / ".nlpm-test" / "legacy-sample.spec.md"
        fm = spec_frontmatter(spec.read_text(encoding="utf-8"))
        self.assertEqual(fm["artifact"], "agents/local.md")
        self.assertTrue((root / "agents" / "local.md").is_file())
        local = (root / "agents" / "local.md").read_text(encoding="utf-8")
        self.assertIn("description: Use when", local)


if __name__ == "__main__":
    unittest.main()
