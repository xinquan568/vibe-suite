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
#: Command specs delivered after the frozen stage — rung-5 NL-TDD REDs for later issues.
#: AC-7's "14/14" stays exactly the agent list above; these are additional, typed inventories.
COMMAND_SPECS = ["refresh-knowledge"]
#: Skill specs — same rung-5 mechanism for skills/<name>/SKILL.md artifacts.
SKILL_SPECS = ["runs-stats"]

SECTIONS = ["Triggers On", "Does Not Trigger On", "Output Contains", "Frontmatter Valid"]

#: Frozen per-spec provenance (frozen plan D8): each spec's Source line must carry its
#: normative token.
SOURCE_TOKENS = {
    "recon": "F3", "architecture": "F3", "error-handling": "F3", "security": "F3",
    "testing": "F3", "edge-cases": "F3",
    "scanner": "shipped", "scorer": "shipped", "vague-scanner": "shipped",
    "checker": "shipped",
    "tester": "F4.5", "vocab-drift-scanner": "F4.6",
    "security-scanner": "F5.1", "spec-researcher": "F4.7",
}

SKILL = REPO_ROOT / "skills" / "testing" / "SKILL.md"


def squash(text):
    """Whitespace-normalized text for whole-sentence, wrap-tolerant assertions."""
    return re.sub(r"\s+", " ", text)


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
        expected = [f"{n}.spec.md" for n in FOURTEEN + COMMAND_SPECS + SKILL_SPECS]
        self.assertEqual(on_disk, sorted(expected))

    def test_skill_spec_schema_and_depth(self):
        for name in SKILL_SPECS:
            with self.subTest(spec=name):
                text = (SPECS / f"{name}.spec.md").read_text(encoding="utf-8")
                fm = spec_frontmatter(text)
                self.assertEqual(sorted(fm), ["artifact", "min_score", "type"])
                self.assertEqual(fm["artifact"], f"skills/{name}/SKILL.md")
                self.assertEqual(fm["type"], "skill")
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

    def test_command_spec_schema_and_depth(self):
        for name in COMMAND_SPECS:
            with self.subTest(spec=name):
                text = (SPECS / f"{name}.spec.md").read_text(encoding="utf-8")
                fm = spec_frontmatter(text)
                self.assertEqual(sorted(fm), ["artifact", "min_score", "type"])
                self.assertEqual(fm["artifact"], f"commands/{name}.md")
                self.assertEqual(fm["type"], "command")
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
                source_line = next(l for l in text.splitlines()
                                   if l.startswith("Source:"))
                self.assertIn(SOURCE_TOKENS[name], source_line,
                              f"{name}: Source line lacks its frozen token")

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

    def test_skill_canonical_lines_verbatim(self):
        # The two ✗ example lines in skills/testing are the canonical instances; the
        # command must reproduce them character-for-character (D1/D3).
        skill = SKILL.read_text(encoding="utf-8")
        canonical = re.findall(r"`(✗ [^`]+)`", skill)
        self.assertEqual(len(canonical), 2, canonical)
        body = self._body()
        for line in canonical:
            self.assertIn(line, body, f"canonical line not verbatim: {line}")

    def test_failure_line_formats(self):
        body = self._body()
        self.assertIn('✗ "<query>" → predicted <YES|NO> trigger (expected <YES|NO>)',
                      body)
        self.assertIn("    confidence: high|medium|low", body)
        self.assertIn("✗ score <n>/100 (min: <m>)", body)
        self.assertIn('✗ output: format element "<item>" not stated', body)
        self.assertIn('✗ input: "<input>" behavior not stated', body)
        self.assertIn("✗ frontmatter: missing '<key>'", body)
        self.assertIn("✗ frontmatter: '<key>' not <requirement>", body)
        self.assertIn('✗ output: missing "<element>"', body)
        self.assertIn("✗ rule: violation sample not flagged", body)
        self.assertIn("✗ rule: compliant sample flagged", body)
        self.assertIn("✗ artifact missing (RED)", body)

    def test_discovery_and_batching(self):
        body = self._body()
        flat = squash(body)
        self.assertIn(".vibe-test/", body)
        self.assertIn(".nlpm-test/", body)
        self.assertRegex(body, r"(?i)never renamed|run as-is|no rename")
        self.assertRegex(body, r"(?i)new specs .*\.vibe-test")
        self.assertIn("the new directory wins and the legacy copy is reported as "
                      "skipped", flat)
        self.assertIn("run exactly that file", flat)
        self.assertRegex(body, r"(?i)batches of (up to )?3|≤3")
        self.assertIn("one tester dispatch per batch", flat)
        self.assertIn("the report aggregates in the same sorted order", flat)
        self.assertIn("skills/testing/SKILL.md", body)

    def test_registered(self):
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/test.md", manifest["commands"])
        self.assertIn("./agents/tester.md", manifest["agents"])
        # at least the E3.6 state; later items add more (membership above pins ours)
        self.assertGreaterEqual(len(manifest["commands"]), 16)
        self.assertGreaterEqual(len(manifest["agents"]), 5)


class TesterContract(unittest.TestCase):
    def _body(self):
        return TESTER.read_text(encoding="utf-8")

    def test_five_numbered_lanes_parsed(self):
        # The five lanes are parsed as NUMBERED bold headings, in F4.5's order —
        # deleting a lane, not just a keyword, fails this.
        body = self._body()
        lanes = re.findall(r"^\d+\. \*\*(.+?)\*\*", body, re.M)
        self.assertEqual(len(lanes), 5, lanes)
        for i, expected in enumerate(("Frontmatter validity", "Trigger prediction",
                                      "Output and input expectations",
                                      "Rule compliance", "Score vs min_score")):
            self.assertIn(expected.split()[0].lower(), lanes[i].lower(), lanes)
        self.assertRegex(body, r"(?i)predict")
        self.assertRegex(body, r"(?i)never executed or invoked")

    def test_output_and_input_lane_covers_all_three_sections(self):
        flat = squash(self._body())
        for section in ("Output Contains", "Output Format", "Handles Input"):
            self.assertIn(section, flat, f"lane 3 must cover {section}")

    def test_score_engine_invocation_contract(self):
        body = self._body()
        flat = squash(body)
        self.assertIn("printf 'agent\\x1f<relative-path>\\x00'", body)
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/score_engine.py" --root', flat)
        self.assertIn("files[0].score", body)
        self.assertIn("IGNORE `files[0].verdict`", body)
        self.assertIn("existence is checked BEFORE delegation", flat)
        self.assertIn("NO positional artifact form", flat)
        self.assertIn("If the engine exits 2, that spec alone fails with the "
                      "engine's message as its detail and the batch continues", flat)

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
