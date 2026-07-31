#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The shared reviewer contract and its conformance registry (E5.1 / vibe-40).

F6.3 asks for one reference every generator-critic loop cites, so that a `major` in one loop means what
it means in another. The reference lands at `skills/vibe-core/references/reviewer-contract.md`; this
module pins its contents and grades its consumers.

**The acceptance criterion has no subject yet, and that shaped the design.** It grades whether
`skills/refine-proposal/` (#41) and `skills/issue2pr/` (#42) cite the contract without restating it.
Neither exists — they ship at links 2 and 3 of this chain. A glob over `skills/*` would pass over an
empty set today and keep passing after they land uncited, which is the failure mode worth engineering
against.

So the consumers are a **declared registry pinned by exact equality**, not a glob. Each entry is either
absent (reported pending, against its issue number) or present (fully graded). The set of things to
check is fixed now; only their state is discovered. Deleting an entry to silence it fails the equality
test.

**Citation versus redefinition is lexical, and the exemption order is the whole game.** A consumer must
be able to write `--max-review-rounds` in its own usage text; what it must not do is define the term
twice. An earlier draft of this policy allowed definition markers inside "interface" contexts, which let
an options-table row carry a complete second definition — `| --max-review-rounds | integer 1..5,
default 3 |` satisfied both rules while being exactly what the check exists to stop. The order is
inverted here: a definition marker fails wherever it appears, and the single carve-out is a
deterministically located `## Round bounds` block whose values are then checked for equality.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "vibe-core" / "SKILL.md"
CONTRACT = REPO_ROOT / "skills" / "vibe-core" / "references" / "reviewer-contract.md"

#: Path → the issue that ships it. Pinned by equality: a removed, added or renumbered entry fails.
REQUIRED_CONSUMERS = {
    "skills/refine-proposal": 41,   # E5.2
    "skills/issue2pr": 42,          # E5.3
}

#: The per-loop round-cap domains D2 fixed. Divergence hides here: two loops can agree on the key and
#: disagree on what it accepts.
DOMAINS = {
    "skills/refine-proposal": {"floor": 1, "ceiling": 5, "default": 3},
    "skills/issue2pr": {"floor": 2, "ceiling": 5, "default": 2},
}

CAP_KEY = "max_review_rounds"
CAP_FLAG = "--max-review-rounds"

MATRIX_DIMENSIONS = ("dispatch", "read-only guard", "output capture",
                     "token accounting", "pre-flight", "quota signature")
CLOSURE_STATES = ("open", "fixed", "declined", "accepted_decline", "challenged_once", "final_decline")
REVIEW_MODES = ("none", "single", "full")

PINNED_TERMS = (CAP_KEY, CAP_FLAG) + MATRIX_DIMENSIONS + CLOSURE_STATES + REVIEW_MODES

#: A definition marker: a range, a definitional verb, or a gloss. Rejected everywhere but the domain
#: block — including inside interface contexts, which is the fix for the loophole above.
DEFINITION_MARKER = re.compile(
    r"\d+\s*\.\.\s*\d+|\d+\s*-\s*\d+|between\s+\d+\s+and\s+\d+"
    r"|\bdefaults?\b|\bmust be\b|\bvalid values\b|\bclamp(?:ed|s)?\b", re.I)

ROUND_BOUNDS_HEADING = re.compile(r"^##[ ]Round bounds[ ]*$")

CONTRACT_LINK = "references/reviewer-contract.md"

MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})", re.I)


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


def round_bounds_block(text):
    """The one legal home for definition-shaped text, located deterministically.

    Returns (block_text, heading_count). Zero headings means the domain was never declared; two means
    there is no way to say which governs. Both are failures, so the count is returned rather than
    swallowed.
    """
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if ROUND_BOUNDS_HEADING.match(line)]
    if len(starts) != 1:
        return "", len(starts)
    start = starts[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^#{1,2}[ ]", lines[i]):
            end = i
            break
    return "\n".join(lines[start + 1:end]), 1


class TestRegistry(unittest.TestCase):
    """The registry itself, before anything it points at."""

    def test_registry_is_pinned_by_equality(self):
        """Non-emptiness would not catch deletion — dropping one entry leaves the rest satisfiable."""
        self.assertEqual(
            REQUIRED_CONSUMERS,
            {"skills/refine-proposal": 41, "skills/issue2pr": 42},
            "the consumer registry changed; F6.3 names these two and the acceptance criterion "
            "grades exactly them")

    def test_every_consumer_has_a_domain(self):
        self.assertEqual(set(DOMAINS), set(REQUIRED_CONSUMERS),
                         "a consumer without a declared domain cannot be graded for divergence")


class TestContractContent(unittest.TestCase):
    """What the reference must say. Semantics where a heading alone would be hollow."""

    @classmethod
    def setUpClass(cls):
        cls.text = CONTRACT.read_text(encoding="utf-8")
        cls.norm = norm(cls.text)

    def test_the_six_matrix_dimensions_are_named(self):
        for dimension in MATRIX_DIMENSIONS:
            with self.subTest(dimension=dimension):
                self.assertIn(dimension, self.norm)

    def test_quota_signature_is_not_confused_with_failure_detection(self):
        """An earlier draft substituted 'failure signature'. They are different dimensions: one is an
        exhausted allowance, retryable later; the other is how a result is read."""
        self.assertIn("quota signature", self.norm)
        self.assertIn("exhaust", self.norm)

    def test_the_backend_enum_defers_to_the_config_schema(self):
        """The schema already fixes `reviewer_backend`. Two authorities for one rule is worse than one."""
        self.assertIn("reviewer_backend", self.text)
        self.assertRegex(self.norm, r"schema (governs|wins|is authoritative)")

    def test_the_enum_agrees_with_the_schema_rather_than_pinning_it_twice(self):
        skill = SKILL.read_text(encoding="utf-8")
        row = [l for l in skill.splitlines() if l.strip().startswith("| `reviewer_backend`")]
        self.assertEqual(len(row), 1, "expected exactly one reviewer_backend schema row")
        self.assertIn("codex", row[0])
        self.assertNotIn("copilot", row[0], "the schema's enum must not list a dropped backend")
        # The contract may *record* that copilot-cli was dropped — that history is worth keeping, and
        # a reader who finds the name in an old plan should find out here why it is not a backend.
        # What it must not do is present it as a member. So every mention must be an exclusion.
        for lineno, line in enumerate(self.text.splitlines(), 1):
            if "copilot" not in line.lower():
                continue
            with self.subTest(line=lineno):
                self.assertRegex(
                    line.lower(), r"dropped|never listed|not a backend",
                    "a copilot-cli mention must state its exclusion; the enum has one member")

    def test_review_modes_are_defined_not_merely_listed(self):
        """A heading with an empty body would pass a presence check. Each mode must state what it does
        about reviewer dispatch, the update pass, and the cap."""
        for mode in REVIEW_MODES:
            with self.subTest(mode=mode):
                self.assertIn(mode, self.norm)
        for prop in ("step numbering", "no backend", "never a silent"):
            with self.subTest(property=prop):
                self.assertIn(prop, self.norm)

    def test_the_closure_machine_carries_its_states_and_the_one_challenge_rule(self):
        for state in CLOSURE_STATES:
            with self.subTest(state=state):
                self.assertIn(state, self.text)
        self.assertIn("at most once", self.norm,
                      "without the one-challenge rule the machine has a cycle and the bounded rounds "
                      "stop bounding anything")

    def test_verdict_parsing_states_all_four_steps(self):
        for phrase in ("last", "re-ask", "record", "never abort"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.norm)

    def test_self_review_never_engages_implicitly(self):
        self.assertIn("--allow-self-review", self.text)
        self.assertIn("never", self.norm)
        self.assertIn('reviewer: "self"', self.text)

    def test_model_resolution_states_precedence_and_non_persistence(self):
        self.assertRegex(self.norm, r"user\s*>\s*project|user .{0,30}project .{0,30}tool default")
        self.assertIn("never persisted", self.norm)

    def test_provenance_names_its_shipped_precedents(self):
        self.assertIn("provenance", self.norm)
        self.assertIn("commands/score.md", self.text)
        self.assertIn("commands/security-scan.md", self.text)

    def test_the_clamp_rule_is_pinned(self):
        self.assertIn("nearest bound", self.norm)
        self.assertIn("not a clamp", self.norm,
                      "a non-integer must be an error; silently rounding a typo produces a cap "
                      "nobody chose")

    def test_no_pinned_model_id(self):
        hits = [l for l in self.text.splitlines() if MODEL_PIN.search(l) and "never" not in l.lower()]
        self.assertEqual(hits, [], f"P9: pinned model id in the contract: {hits}")

    def test_the_skill_points_at_the_reference(self):
        self.assertIn(CONTRACT_LINK, SKILL.read_text(encoding="utf-8"),
                      "an unreferenced reference is one nothing loads")


class TestConsumerConformance(unittest.TestCase):
    """The acceptance criterion. Absent consumers are reported, not skipped silently."""

    def consumer_files(self, rel):
        directory = REPO_ROOT / rel
        if not directory.is_dir():
            return None
        return sorted(directory.rglob("*.md"))

    def test_each_consumer_is_absent_or_conformant(self):
        for rel, issue in sorted(REQUIRED_CONSUMERS.items()):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    self.assertGreater(issue, 0, f"{rel} pending — ships at #{issue}")
                    continue
                self.assertTrue(files, f"{rel} exists but holds no markdown to grade")
                blob = "\n".join(f.read_text(encoding="utf-8") for f in files)
                self.assertIn(CONTRACT_LINK, blob,
                              f"{rel} must cite the reviewer contract, not restate it")
                self.assertRegex(blob, re.escape(CONTRACT_LINK) + r"#\S+",
                                 f"{rel}'s citation must name the subsection it relies on")

    def test_present_consumers_declare_exactly_one_round_bounds_block(self):
        for rel in sorted(REQUIRED_CONSUMERS):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    continue
                blob = "\n".join(f.read_text(encoding="utf-8") for f in files)
                _, count = round_bounds_block(blob)
                self.assertEqual(count, 1,
                                 f"{rel} must declare exactly one '## Round bounds' block "
                                 f"(found {count}); zero is undeclared, two is ambiguous")

    def test_present_consumers_match_their_domain_tuple(self):
        for rel, domain in sorted(DOMAINS.items()):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    continue
                blob = "\n".join(f.read_text(encoding="utf-8") for f in files)
                block, count = round_bounds_block(blob)
                if count != 1:
                    continue  # reported by the test above
                numbers = [int(n) for n in re.findall(r"\d+", block)]
                for name, value in domain.items():
                    self.assertIn(value, numbers,
                                  f"{rel}'s round-bounds block omits its {name} ({value})")
                self.assertRegex(norm(block), r"because|since|so that",
                                 f"{rel} must state a reason for its floor; D2 makes the rationale "
                                 f"part of the contract, not a courtesy")

    def test_definition_markers_appear_only_in_the_round_bounds_block(self):
        """The inverted exemption order: a marker fails wherever it appears but there."""
        for rel in sorted(REQUIRED_CONSUMERS):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    continue
                for path in files:
                    text = path.read_text(encoding="utf-8")
                    block, count = round_bounds_block(text)
                    block_lines = set(block.splitlines()) if count == 1 else set()
                    for lineno, line in enumerate(text.splitlines(), 1):
                        if line in block_lines or not DEFINITION_MARKER.search(line):
                            continue
                        if any(term in line for term in PINNED_TERMS):
                            self.fail(
                                f"{path.relative_to(REPO_ROOT)}:{lineno} redefines a contract term "
                                f"outside the '## Round bounds' block: {line.strip()!r}")


if __name__ == "__main__":
    unittest.main()
