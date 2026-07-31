#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The AC-3 fixture oracle for `/vibe-suite:nl-audit` (E4.1 / vibe-35) -- the static half.

Merge-proposal line 627 enumerates the seeded defect classes per fixture and fixes the assertion
contract: `--full` reports >= 75 % of the seeded classes, each attributed to its correct source
dimension (D0-D6, or the A-E check set for `repo`); `--mini` reports only mini-member dimensions.
Those class lists are transcribed below as literals and are this module's authority. They are
**not** read from the fixtures, and not from the auditing skill: a corpus compared against itself
proves nothing, so the oracle is written down independently and the corpus is compared to it.

**This module is the static half only, and says so rather than implying more.** It checks that the
corpus and the oracle agree. Whether a real audit run *finds* the seeded classes is arithmetic over
two files that `tools/nl-audit-acceptance.py` performs and `test_nl_audit_acceptance.py` proves
correct; whether a live engine clears the floor is the operator's acceptance step. Three jobs, three
places, none claiming another's.

**`defective-skill/` is jointly owned by design.** Line 627 assigns it both the nl-audit duty and the
score-golden duty in one sentence, and `test_score_goldens.py` compares its `expected.json` for exact
equality against a hand-derived worksheet. The guard below asserts every pre-existing file in that
directory is byte-identical to its committed content, so an edit fails loudly here rather than
silently in the other suite.
"""

import json
import math
import re
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "nl-audit"
MANIFEST_NAME = "seeded-defects.json"

#: Per-type dimension membership, transcribed from F4.9 -- the same table `test_nl_audit.py` asserts
#: the skill against. Duplicated deliberately: this module must be able to fail when the skill and
#: the oracle disagree, which it could not do if it imported the skill's own view.
MINI_MEMBERS = {
    "skill": {"D0", "D1", "D2", "D3"},
    "command": {"D0", "D1", "D2", "D3"},
    "agent": {"D0", "D1", "D2", "D3"},
    "rules": {"D0", "D1", "D2", "D3"},
    "plugin": {"D0", "D1", "D3", "D6"},   # irregular: D2 is full-only, D6 is mini+full
}
ALL_DIMENSIONS = {"D0", "D1", "D2", "D3", "D4", "D5", "D6"}
REPO_CHECK_IDS = {
    "A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3",
    "D1", "D2", "D3", "E1", "E2", "E3",
}

#: The oracle. Every class literal is from line 627, in its order; every dimension is derived from
#: F4.9's dimension names for that type. Line 627 lists the four seven-class types in dimension
#: order, so those four are positional 1:1 -- which is itself evidence the source intended the
#: mapping, not a convenience.
ORACLE = {
    "defective-skill": {
        "type": "skill",
        "classes": {
            "missing name": "D0",
            "generic description": "D1",
            "redundant content": "D2",
            ">500-line body": "D3",
            "domain mixing": "D4",
            "missing scope note": "D4",
            "broken references link": "D5",
            "orphaned registration": "D5",
            "pseudocode example": "D6",
            "vague quantifiers": "D6",
        },
    },
    "defective-command": {
        "type": "command",
        "classes": {
            "bad frontmatter": "D0",
            "muddled workflow": "D1",
            "over-broad allowed-tools": "D2",
            "missing output spec": "D3",
            "unhandled empty input": "D4",
            "unsafe arguments interpolation": "D5",
            "duplicated partial logic": "D6",
        },
    },
    "defective-agent": {
        "type": "agent",
        "classes": {
            "schema errors": "D0",
            "mistriggering description": "D1",
            "weak system prompt": "D2",
            "tool over-provisioning": "D3",
            "scope bleed": "D4",
            "missing output format": "D5",
            "missing untrusted-input guard": "D6",
        },
    },
    "defective-rules": {
        "type": "rules",
        "classes": {
            "unparseable rule": "D0",
            "unenforceable vagueness": "D1",
            "token bloat": "D2",
            "two conflicting rules": "D3",
            "missing path scope": "D4",
            "rule duplicating a linter": "D5",
            "stale reference": "D6",
        },
    },
    "defective-plugin": {
        "type": "plugin",
        "classes": {
            "manifest disk mismatch": "D0",
            "spec gaps": "D1",
            "risky hook": "D2",
            "broken cross-refs": "D3",
            "contradictory commands": "D4",
            "missing error paths": "D5",
            "unmaintainable duplication": "D6",
        },
    },
    # Line 627 fixes mixed-repo's *span* ("artifacts across all discovery categories A-E incl. a
    # prompt file, a non-plugin agent framework, and a stale design doc"), not a class count -- so
    # its floor is derived from N rather than stated as a literal.
    "mixed-repo": {
        "type": "repo",
        "classes": {
            "invalid plugin manifest field": "A1",
            "command references a missing agent": "A2",
            "vague claude-md guidance": "B1",
            "unenforceable project rule": "B2",
            "weak system prompt file": "C1",
            "prompt without an untrusted-input guard": "C2",
            "malformed framework manifest": "D1",
            "stale design doc": "E3",
        },
    },
}

#: The three files `defective-skill/` shipped before this issue. `seeded-defects.json` is the only
#: permitted addition.
PREEXISTING_SKILL_FIXTURE_FILES = (
    "expected.json",
    "README.md",
    ".claude-plugin/plugin.json",
    "skills/defective/SKILL.md",
)


def floor_for(n):
    """>= 75 % of n, rounded up.

    `ceil`, not `round`: at n = 7, 0.75 * 7 = 5.25, and accepting 5 would be 71 % -- below the bar
    the acceptance criterion states. The floor rounds toward the stricter side by construction.
    """
    return math.ceil(0.75 * n)


def _load_manifest(name):
    path = FIXTURES / name / MANIFEST_NAME
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(text):
    """Class keys compare on their words, so a fixture may write '>500-line body' or
    'over 500 line body' and still match. Punctuation the oracle cannot canonicalise -- backticks,
    `$`, slashes -- is dropped rather than being a source of spurious mismatch."""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class TestFixtureCorpusExists(unittest.TestCase):
    def test_all_six_fixtures_are_present_with_a_manifest(self):
        missing = [name for name in ORACLE
                   if not (FIXTURES / name / MANIFEST_NAME).is_file()]
        self.assertEqual(missing, [],
                         "fixtures missing their %s: %s" % (MANIFEST_NAME, ", ".join(missing)))

    def test_no_undeclared_fixture_directory(self):
        if not FIXTURES.is_dir():
            self.skipTest("fixture root does not exist yet")
        on_disk = {d.name for d in FIXTURES.iterdir() if d.is_dir()}
        self.assertEqual(on_disk, set(ORACLE),
                         "the fixture set must be exactly line 627's six")


class TestSeededClassSets(unittest.TestCase):
    """The class inventories are fixed by line 627 -- no floor, no 'at least N'."""

    def test_each_fixture_declares_exactly_the_oracle_class_set(self):
        for name, spec in ORACLE.items():
            with self.subTest(fixture=name):
                if not (FIXTURES / name / MANIFEST_NAME).is_file():
                    self.skipTest("%s does not exist yet" % name)
                manifest = _load_manifest(name)
                declared = {_normalize(c["id"]) for c in manifest["classes"]}
                expected = {_normalize(c) for c in spec["classes"]}
                self.assertEqual(declared, expected,
                                 "%s declares a class set that is not line 627's" % name)

    def test_defective_skill_declares_ten_and_the_others_seven(self):
        """The counts line 627 states, asserted directly so a set that drifted in both directions
        at once could not cancel out."""
        expected_counts = {"defective-skill": 10, "defective-command": 7, "defective-agent": 7,
                           "defective-rules": 7, "defective-plugin": 7}
        for name, count in expected_counts.items():
            with self.subTest(fixture=name):
                if not (FIXTURES / name / MANIFEST_NAME).is_file():
                    self.skipTest("%s does not exist yet" % name)
                self.assertEqual(len(_load_manifest(name)["classes"]), count)

    def test_manifest_type_matches_the_oracle(self):
        for name, spec in ORACLE.items():
            with self.subTest(fixture=name):
                if not (FIXTURES / name / MANIFEST_NAME).is_file():
                    self.skipTest("%s does not exist yet" % name)
                self.assertEqual(_load_manifest(name)["type"], spec["type"])


class TestDimensionAttribution(unittest.TestCase):
    """AC-3's 'correct dimension attribution', checked against this module's own oracle rather than
    against the artifact under test."""

    def test_every_declared_dimension_matches_the_oracle(self):
        for name, spec in ORACLE.items():
            if not (FIXTURES / name / MANIFEST_NAME).is_file():
                continue
            oracle = {_normalize(k): v for k, v in spec["classes"].items()}
            for entry in _load_manifest(name)["classes"]:
                with self.subTest(fixture=name, cls=entry["id"]):
                    self.assertEqual(entry["dimension"], oracle[_normalize(entry["id"])],
                                     "%s: '%s' is attributed to the wrong dimension"
                                     % (name, entry["id"]))

    def test_attribution_domain_is_per_type(self):
        """D0-D6 for the five artifact types; A1-E3 for `repo`. A single shared id set would accept
        a `D0` attribution on mixed-repo, where no such check exists."""
        for name, spec in ORACLE.items():
            if not (FIXTURES / name / MANIFEST_NAME).is_file():
                continue
            domain = REPO_CHECK_IDS if spec["type"] == "repo" else ALL_DIMENSIONS
            for entry in _load_manifest(name)["classes"]:
                with self.subTest(fixture=name, cls=entry["id"]):
                    self.assertIn(entry["dimension"], domain,
                                  "%s: '%s' is not a valid id for type %s"
                                  % (name, entry["dimension"], spec["type"]))

    def test_every_dimension_of_each_artifact_type_is_exercised(self):
        """Zero dimension loss is only fixture-verified if every dimension has something to catch."""
        for name, spec in ORACLE.items():
            if spec["type"] == "repo" or not (FIXTURES / name / MANIFEST_NAME).is_file():
                continue
            with self.subTest(fixture=name):
                used = {e["dimension"] for e in _load_manifest(name)["classes"]}
                self.assertEqual(used, ALL_DIMENSIONS,
                                 "%s leaves %s unexercised"
                                 % (name, sorted(ALL_DIMENSIONS - used)))

    def test_mixed_repo_spans_every_discovery_category(self):
        if not (FIXTURES / "mixed-repo" / MANIFEST_NAME).is_file():
            self.skipTest("mixed-repo does not exist yet")
        letters = {e["dimension"][0] for e in _load_manifest("mixed-repo")["classes"]}
        self.assertEqual(letters, set("ABCDE"),
                         "mixed-repo must span discovery categories A-E")


class TestMiniMembershipSeeding(unittest.TestCase):
    """`--mini` reports only mini-member dimensions. Testing that exclusion needs both kinds of seed:
    with no full-only class in the fixture, a `--mini` run that wrongly emitted one would have
    nothing to emit, and the assertion would pass vacuously."""

    def test_each_artifact_type_fixture_seeds_both_mini_and_full_only_classes(self):
        for name, spec in ORACLE.items():
            if spec["type"] == "repo" or not (FIXTURES / name / MANIFEST_NAME).is_file():
                continue
            with self.subTest(fixture=name):
                used = {e["dimension"] for e in _load_manifest(name)["classes"]}
                mini = MINI_MEMBERS[spec["type"]]
                self.assertTrue(used & mini, "%s seeds no mini-member class" % name)
                self.assertTrue(used - mini, "%s seeds no full-only class" % name)


class TestDetectionFloor(unittest.TestCase):
    def test_declared_floor_equals_the_rule(self):
        """A hand-written floor that drifts from ceil(0.75 * N) silently lowers the bar."""
        for name in ORACLE:
            with self.subTest(fixture=name):
                if not (FIXTURES / name / MANIFEST_NAME).is_file():
                    self.skipTest("%s does not exist yet" % name)
                manifest = _load_manifest(name)
                self.assertEqual(manifest["floor"], floor_for(len(manifest["classes"])))

    def test_the_rule_reproduces_the_known_literals(self):
        """Pins the arithmetic itself, independent of any fixture on disk."""
        self.assertEqual(floor_for(10), 8)
        self.assertEqual(floor_for(7), 6)
        self.assertEqual(floor_for(8), 6)
        self.assertNotEqual(floor_for(7), 5, "round() would give 5, which is 71 % -- below the bar")


class TestJointOwnershipGuard(unittest.TestCase):
    """`defective-skill/` also serves `test_score_goldens.py`, whose oracle is hand-derived and
    compared for exact equality. Ordered first in the plan for that reason."""

    #: The reviewed baseline. **Not HEAD**: once a change is committed, the worktree and HEAD are
    #: identical by construction, so a HEAD comparison is vacuous on any clean checkout — it would
    #: pass for a commit that rewrote the oracle. The merge base against the integration branch is
    #: the last content a reviewer actually approved.
    BASELINE_REFS = ("origin/main", "main")

    def _baseline_ref(self):
        for ref in self.BASELINE_REFS:
            probe = subprocess.run(["git", "merge-base", "HEAD", ref],
                                   cwd=REPO_ROOT, capture_output=True, text=True)
            if probe.returncode == 0 and probe.stdout.strip():
                return probe.stdout.strip()
        return None

    def _committed(self, relpath):
        base = self._baseline_ref()
        if base is None:
            return subprocess.CompletedProcess([], 1, b"", b"")
        return subprocess.run(
            ["git", "show", "%s:tests/fixtures/nl-audit/defective-skill/%s" % (base, relpath)],
            cwd=REPO_ROOT, capture_output=True)

    def test_preexisting_files_are_byte_identical_to_their_committed_content(self):
        for relpath in PREEXISTING_SKILL_FIXTURE_FILES:
            with self.subTest(file=relpath):
                proc = self._committed(relpath)
                if proc.returncode != 0:
                    self.skipTest("%s is not in the baseline yet (or no baseline ref)" % relpath)
                on_disk = (FIXTURES / "defective-skill" / relpath).read_bytes()
                self.assertEqual(on_disk, proc.stdout,
                                 "tests/fixtures/nl-audit/defective-skill/%s was modified; the "
                                 "score-golden oracle depends on it byte for byte" % relpath)

    def test_seeded_defects_json_is_the_only_addition(self):
        root = FIXTURES / "defective-skill"
        if not root.is_dir():
            self.skipTest("defective-skill does not exist yet")
        on_disk = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        expected = sorted(list(PREEXISTING_SKILL_FIXTURE_FILES) + [MANIFEST_NAME])
        self.assertEqual(on_disk, expected,
                         "only %s may be added to the jointly-owned fixture" % MANIFEST_NAME)


if __name__ == "__main__":
    unittest.main()
