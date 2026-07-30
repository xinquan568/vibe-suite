# SPDX-License-Identifier: ISC
"""E3.8 (vibe-33) acceptance: /vibe-suite:spec-sync + spec-researcher.

Rung 0/1 pins contracts, the freshness normalization, and the fixture oracle. The live
research step is the agent's judgment lane: CI performs no network fetch. What runs
mechanically here is the one-to-one comparison of a RECORDED manual dry run against the
hand-authored expectation — the recording's provenance header states when and how it
was produced.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND = REPO_ROOT / "commands" / "spec-sync.md"
AGENT = REPO_ROOT / "agents" / "spec-researcher.md"
SPEC = REPO_ROOT / ".vibe-test" / "spec-researcher.spec.md"
FIX = REPO_ROOT / "tests" / "fixtures" / "spec-sync"
EXPECTED = FIX / "expected-report.md"
RECORDED = FIX / "recorded-dry-run.md"
OVERLAYS = {
    "claude": REPO_ROOT / "skills" / "conventions-claude" / "SKILL.md",
    "codex": REPO_ROOT / "skills" / "conventions-codex" / "SKILL.md",
    "antigravity": REPO_ROOT / "skills" / "conventions-antigravity" / "SKILL.md",
}

#: D6's exact canonical post-state lines (verbatim, including the ≥ character in the
#: preserved Claude qualification).
CANONICAL = {
    "claude": "**Spec freshness:** verified 2026-06-07 against the official Claude Code "
              "docs map dated 2026-06-05 (code.claude.com/docs/en/)",
    "codex": "**Spec freshness:** verified 2026-06-07 against Codex CLI 0.137.0, "
             "released 2026-06-04 (developers.openai.com/codex)",
    "antigravity": "**Spec freshness:** UNVERIFIED — research written 2026-05-25, six "
                   "days after the Antigravity 2.0 announcement of 2026-05-19; the "
                   "verification pass described in §10 has not landed "
                   "(developers.googleblog.com)",
}
PRESERVED = {
    "claude": "That map tracks Claude Code ≥ v2.1.16x; where earlier notes conflicted "
              "with this refresh, the newer facts below are canonical.",
    "codex": "Pre-releases existed up to 0.138.0-alpha.6 at refresh time.",
    "antigravity": "the spec has not settled since Antigravity 2.0, so most "
                   "tool-specific checks stay advisory",
}
SUPERSEDED = ["Freshness: refreshed 2026-06-07", "Refresh state: verified 2026-06-07"]

TAGS = ["RESOLVED", "REMOVE", "FIX", "ADD", "CONFIRM"]


def squash(text):
    return re.sub(r"\s+", " ", text)


def report_rows(text):
    """Parse a gap-report table into (seed, section, tag, confidence) tuples."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| Seed") or set(
                line.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[0].isdigit():
            rows.append(tuple(cells[:4]))
    return rows


class Deliverables(unittest.TestCase):
    def test_artifacts_and_registration(self):
        self.assertTrue(COMMAND.is_file())
        self.assertTrue(AGENT.is_file())
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/spec-sync.md", manifest["commands"])
        self.assertIn("./agents/spec-researcher.md", manifest["agents"])
        # at least the E3.8 state; later items add more (membership above pins ours)
        self.assertGreaterEqual(len(manifest["commands"]), 18)
        self.assertGreaterEqual(len(manifest["agents"]), 7)

    def test_agent_frontmatter_matches_its_shipped_spec(self):
        body = AGENT.read_text(encoding="utf-8")
        self.assertRegex(body, r"(?m)^description: Use when")
        self.assertRegex(body, r"(?m)^model: (haiku|sonnet|opus)$")
        self.assertRegex(body, r"(?m)^tools: .*WebFetch.*WebSearch")
        spec = SPEC.read_text(encoding="utf-8")
        self.assertIn("FIX/REMOVE/ADD/CONFIRM/RESOLVED", spec)
        flat = squash(body)
        self.assertIn("first-party", flat.lower())
        self.assertRegex(flat, r"(?i)one dispatch per overlay|per-overlay dispatch")

    def test_no_deprecated_vocabulary(self):
        # R51 is enforced on commands/** and agents/** (E3.7).
        for path in (COMMAND, AGENT):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)\bimplement\b")


class CommandContract(unittest.TestCase):
    def setUp(self):
        self.body = COMMAND.read_text(encoding="utf-8")
        self.flat = squash(self.body)

    def test_modes_and_change_predicate(self):
        self.assertIn("--dry-run", self.body)
        self.assertIn("--apply", self.body)
        self.assertIn("remains writable after the confidence threshold", self.flat)
        self.assertRegex(self.flat, r"(?i)no-change branch")
        self.assertRegex(self.flat, r"(?i)never commits")

    def test_tag_precedence_and_disjointness(self):
        for tag in TAGS:
            self.assertIn(tag, self.body)
        # the two disjointness rules the review demanded
        self.assertIn("requires a replacement fact", self.flat)
        self.assertRegex(self.flat, r"(?i)CONFIRM requires .*un-hedged|no hedge")

    def test_confidence_and_threshold(self):
        self.assertIn("UNCLASSIFIED", self.body)
        self.assertIn("source-silent", self.body)
        self.assertIn("source-conflict", self.body)
        self.assertIn("--min-confidence", self.body)
        self.assertRegex(self.flat, r"(?i)default(s)? (to )?`?medium`?")
        self.assertIn("(withheld: below --min-confidence)", self.flat)

    def test_correction_notes(self):
        self.assertIn("<!-- spec-sync <run-date>:", self.body)
        self.assertIn("## Correction notes", self.body)
        self.assertRegex(self.flat, r"(?i)not valid YAML|conforming parser")
        # retirement is reachable: a note-retiring CONFIRM is writable
        self.assertRegex(self.flat,
                         r"(?i)CONFIRM .*retires .*(is writable|counts toward)")

    def test_overlay_root_semantics(self):
        self.assertIn("--overlay-root", self.body)
        self.assertRegex(self.flat, r"(?i)replaces the (selected )?overlay set")
        self.assertRegex(self.flat, r"(?i)requires an explicit target|refuses")

    def test_propagation_rules(self):
        self.assertRegex(self.flat, r"(?i)documentary")
        self.assertRegex(self.flat, r"(?i)encoded")
        self.assertRegex(self.flat, r"(?i)operational")
        self.assertIn("code-change-required", self.body)
        self.assertRegex(self.flat, r"(?i)never edited\*{0,2} by this command")

    def test_verify_step_fully_pinned(self):
        self.assertIn(
            'python3 "${CLAUDE_PLUGIN_ROOT}/bin/vibe-check" "${CLAUDE_PLUGIN_ROOT}"',
            self.body)
        self.assertRegex(self.flat, r"(?i)exit status")


class FreshnessNormalization(unittest.TestCase):
    def test_exact_canonical_lines(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(CANONICAL[name], squash(text))
                self.assertEqual(text.count("**Spec freshness:**"), 1)
                self.assertIn(PRESERVED[name], squash(text))

    def test_no_superseded_marker_and_no_dated_description(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                text = path.read_text(encoding="utf-8")
                for old in SUPERSEDED:
                    self.assertNotIn(old, text)
                description = next(
                    (l for l in text.splitlines() if l.startswith("description:")), "")
                self.assertNotRegex(description, r"\d{4}-\d{2}-\d{2}")


class FixtureOracle(unittest.TestCase):
    def test_fixture_seeds_present(self):
        overlay = (FIX / "stale-overlay" / "SKILL.md").read_text(encoding="utf-8")
        for n in range(1, 8):
            self.assertIn(f"SEED {n}", overlay)
        self.assertTrue((FIX / "stale-overlay" / "consumer-linked.md").is_file())
        self.assertTrue((FIX / "stale-overlay" / "consumer-uncited.md").is_file())

    def test_recorded_dry_run_matches_the_oracle_one_to_one(self):
        self.assertTrue(RECORDED.is_file(),
                        "the recorded manual dry run is missing")
        recorded = RECORDED.read_text(encoding="utf-8")
        self.assertRegex(recorded.splitlines()[0] + recorded.splitlines()[1],
                         r"(?i)provenance|recorded")
        self.assertIn("--overlay-root", recorded)
        expected_rows = report_rows(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(len(expected_rows), 7, "the oracle must carry seven seeds")
        recorded_rows = report_rows(recorded)
        self.assertEqual(recorded_rows, expected_rows,
                         "recorded run drifted from the hand-authored oracle")

    def test_dry_run_wrote_nothing(self):
        recorded = squash(RECORDED.read_text(encoding="utf-8"))
        self.assertRegex(recorded, r"(?i)no file (was )?written|dry run: no write")
        self.assertRegex(recorded, r"(?i)no verify|verify skipped")


class ThresholdRegressions(unittest.TestCase):
    """The two cases the plan review required (step-6 finding 6)."""

    def test_default_is_medium(self):
        flat = squash(COMMAND.read_text(encoding="utf-8"))
        self.assertIn("(**default `medium`**", flat)

    def test_all_medium_under_high_takes_no_change_branch(self):
        flat = squash(COMMAND.read_text(encoding="utf-8"))
        self.assertRegex(
            flat,
            r"(?i)all-medium run under `--min-confidence high` applies nothing")
        self.assertRegex(flat, r"(?i)no write, no bump, no propagation, no verify")


if __name__ == "__main__":
    unittest.main()
