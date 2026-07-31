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


def round_bounds_span(text):
    """Locate the one legal home for definition-shaped text, as a **line interval**.

    Returns `(start, end, count)` with `start`/`end` as 0-based line indices, half-open. An earlier
    version returned the block's *text* and the caller exempted lines by string equality — which meant
    an identical definition line copied anywhere else in the file was exempt too. An interval cannot be
    forged by repetition.

    `count != 1` is returned rather than swallowed: zero means the domain was never declared, two means
    there is no way to say which governs, and both are failures.
    """
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if ROUND_BOUNDS_HEADING.match(line)]
    if len(starts) != 1:
        return 0, 0, len(starts)
    start = starts[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^#{1,2}[ ]", lines[i]):
            end = i
            break
    return start + 1, end, 1


def domain_from_block(block):
    """Read `floor`, `ceiling` and `default` as **labelled** values.

    Membership testing was the bug the execution review found: asserting each expected number appears
    somewhere in the block let `floor 1, ceiling 5, default 2` satisfy a required floor of 2, because
    the 2 was supplied by the default. A label binds a number to the thing it is.

    Returns a dict of the labels found; a missing label is simply absent, so the caller's equality
    check reports it.
    """
    found = {}
    for label in ("floor", "ceiling", "default"):
        match = re.search(r"\b%s\b\W{0,20}?(\d+)" % label, block, re.I)
        if match:
            found[label] = int(match.group(1))
    return found


def paragraphs(text):
    """Blank-line-separated units as `(first, last, joined)`, line numbers 0-based and inclusive.

    Definition detection runs on a whole paragraph with its newlines collapsed, because a redefinition
    split across a line wrap — the marker on one line, the pinned term on the next — evades any rule
    that looks at one line at a time.
    """
    units, start = [], None
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip():
            if start is None:
                start = i
        elif start is not None:
            units.append((start, i - 1, " ".join(lines[start:i])))
            start = None
    if start is not None:
        units.append((start, len(lines) - 1, " ".join(lines[start:])))
    return units


def redefinitions(text):
    """Every paragraph that defines a pinned term outside the `## Round bounds` block.

    Three properties the execution review found missing from the first implementation:

    - exemption is by **line interval**, so an identical definition line copied elsewhere is not
      exempt by virtue of matching the block's text;
    - matching is **case-insensitive**;
    - the unit is a **paragraph**, so a wrapped definition cannot straddle the rule.
    """
    start, end, count = round_bounds_span(text)
    hits = []
    for first, last, unit in paragraphs(text):
        if count == 1 and first >= start and last < end:
            continue                      # wholly inside the one legal block
        low = unit.lower()
        if not DEFINITION_MARKER.search(low):
            continue
        if any(term.lower() in low for term in PINNED_TERMS):
            hits.append((first + 1, unit.strip()))
    return hits


def citation_target_ok(text, containing_dir):
    """A citation must **resolve** and its fragment must name a real contract heading.

    Substring matching accepted `bogus/references/reviewer-contract.md#does-not-exist`, which is a
    citation of nothing. Link targets are parsed, resolved relative to the file that wrote them, and
    checked against the contract's actual headings.
    """
    headings = {
        re.sub(r"[^a-z0-9]+", "-", h.lower()).strip("-")
        for h in re.findall(r"^#{1,6}[ ]+(.+?)[ ]*$", CONTRACT.read_text(encoding="utf-8"), re.M)
    }
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        path, _, fragment = target.partition("#")
        if not path:
            continue
        try:
            resolved = (containing_dir / path).resolve()
        except (OSError, ValueError):
            continue
        if resolved != CONTRACT.resolve():
            continue
        if fragment and fragment in headings:
            return True
    return False


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

    def test_the_verdict_block_is_required_to_be_yaml(self):
        """F6.3 says fenced-**YAML**. A contract that said only 'fenced block' would let each loop pick
        a format no other loop can read — a shared contract sharing nothing."""
        self.assertIn("```yaml", self.text)
        self.assertRegex(self.norm, r"fenced yaml block")

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


class TestPolicy(unittest.TestCase):
    """The lexical policy on literals — every counterexample the execution review produced.

    These are committed rather than demonstrated by hand, because a policy proven once in a terminal is
    a policy nobody can re-check.
    """

    REFINE = DOMAINS["skills/refine-proposal"]
    ISSUE2PR = DOMAINS["skills/issue2pr"]

    def block(self, body):
        return f"# c\n\nIntro.\n\n## Round bounds\n\n{body}\n\n## After\n\ntail\n"

    def domain_of(self, body):
        doc = self.block(body)
        start, end, count = round_bounds_span(doc)
        self.assertEqual(count, 1)
        return domain_from_block("\n".join(doc.splitlines()[start:end]))

    def test_labelled_values_bind_to_their_labels(self):
        self.assertEqual(
            self.domain_of("Floor 1, ceiling 5, default 3, because a round is a complete unit."),
            self.REFINE)

    def test_the_membership_counterexample_now_fails(self):
        """`floor 1, ceiling 5, default 2` satisfied a required floor of 2 under membership testing,
        because the 2 came from the default. Labels bind a number to the thing it is."""
        self.assertNotEqual(
            self.domain_of("Floor 1, ceiling 5, default 2, because reasons."),
            self.ISSUE2PR)

    def test_swapped_floor_and_default_fail(self):
        self.assertNotEqual(
            self.domain_of("Floor 3, ceiling 5, default 1, because reasons."),
            self.REFINE)

    def test_a_missing_label_is_absent_not_guessed(self):
        found = self.domain_of("Ceiling 5, default 3, because reasons.")
        self.assertNotIn("floor", found)
        self.assertNotEqual(found, self.REFINE)

    def test_unrelated_numbers_do_not_supply_a_label(self):
        self.assertEqual(
            self.domain_of("Floor 1, ceiling 5, default 3. See issue 42 and section 7, because reasons."),
            self.REFINE)

    def test_a_definition_copied_outside_the_block_is_not_exempt(self):
        """Exempting by line *text* made an identical line legal anywhere it was repeated.

        The line has to name a pinned term to be a redefinition at all — `floor`/`ceiling`/`default`
        are the labels the block itself uses, not contract vocabulary. So the realistic copy is one
        that carries the cap flag, which is what a consumer would actually duplicate into its overview.
        """
        body = "--max-review-rounds: floor 1, ceiling 5, default 3, because reasons."
        doc = self.block(body).replace("tail", body)
        hits = redefinitions(doc)
        self.assertTrue(hits, "a duplicated definition line outside the block must be caught")
        self.assertEqual(len(hits), 1, "only the copy outside the block is a violation")

    def test_a_wrapped_redefinition_cannot_straddle_the_rule(self):
        """The marker on one line and the pinned term on the next evades any per-line check."""
        doc = ("# c\n\nThe flag --max-review-rounds is an integer whose\n"
               "valid values are 1..5, default 3.\n\n"
               "## Round bounds\n\nFloor 1, ceiling 5, default 3, because reasons.\n")
        self.assertTrue(redefinitions(doc), "a wrapped redefinition must still be caught")

    def test_case_does_not_evade_the_rule(self):
        doc = ("# c\n\nThe flag --MAX-REVIEW-ROUNDS has VALID VALUES 1..5.\n\n"
               "## Round bounds\n\nFloor 1, ceiling 5, default 3, because reasons.\n")
        self.assertTrue(redefinitions(doc))

    def test_a_bare_usage_line_is_not_a_redefinition(self):
        """The policy must not fire on a consumer legitimately naming its own flag."""
        doc = ("# c\n\nRun with --max-review-rounds to bound the loop.\n\n"
               "## Round bounds\n\nFloor 1, ceiling 5, default 3, because reasons.\n")
        self.assertEqual(redefinitions(doc), [])

    def test_two_round_bounds_blocks_are_ambiguous(self):
        doc = self.block("Floor 1, ceiling 5, default 3, because reasons.") + "\n## Round bounds\n\nx\n"
        self.assertEqual(round_bounds_span(doc)[2], 2)

    def test_a_citation_must_resolve(self):
        """Substring matching accepted a path that points at nothing."""
        real = CONTRACT.parent
        self.assertFalse(
            citation_target_ok("[c](bogus/references/reviewer-contract.md#round-bounds)", real),
            "a citation whose target does not resolve to the contract is a citation of nothing")

    def test_a_citation_fragment_must_name_a_real_heading(self):
        self.assertFalse(
            citation_target_ok("[c](reviewer-contract.md#does-not-exist)", CONTRACT.parent))
        self.assertTrue(
            citation_target_ok("[c](reviewer-contract.md#round-bounds)", CONTRACT.parent))


class TestConsumerConformance(unittest.TestCase):
    """The acceptance criterion. Absent consumers are reported, not skipped silently."""

    def consumer_files(self, rel):
        directory = REPO_ROOT / rel
        if not directory.is_dir():
            return None
        return sorted(directory.rglob("*.md"))

    def test_each_consumer_is_absent_or_cites_a_resolvable_subsection(self):
        for rel, issue in sorted(REQUIRED_CONSUMERS.items()):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    self.assertGreater(issue, 0, f"{rel} pending — ships at #{issue}")
                    continue
                self.assertTrue(files, f"{rel} exists but holds no markdown to grade")
                cited = any(citation_target_ok(f.read_text(encoding="utf-8"), f.parent)
                            for f in files)
                self.assertTrue(cited,
                                f"{rel} must cite a real subsection of the reviewer contract by a "
                                f"link that resolves — not restate it, and not point at nothing")

    def test_present_consumers_declare_exactly_one_round_bounds_block(self):
        for rel in sorted(REQUIRED_CONSUMERS):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    continue
                blob = "\n".join(f.read_text(encoding="utf-8") for f in files)
                self.assertEqual(round_bounds_span(blob)[2], 1,
                                 f"{rel} must declare exactly one '## Round bounds' block; "
                                 f"zero is undeclared, two is ambiguous")

    def test_present_consumers_match_their_domain_exactly(self):
        for rel, domain in sorted(DOMAINS.items()):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    continue
                blob = "\n".join(f.read_text(encoding="utf-8") for f in files)
                start, end, count = round_bounds_span(blob)
                if count != 1:
                    continue                      # reported by the test above
                block = "\n".join(blob.splitlines()[start:end])
                self.assertEqual(domain_from_block(block), domain,
                                 f"{rel}'s round bounds must equal its declared domain exactly")
                self.assertRegex(norm(block), r"because|since|so that",
                                 f"{rel} must state a reason for its floor; D2 makes the rationale "
                                 f"part of the contract, not a courtesy")

    def test_no_consumer_redefines_a_contract_term(self):
        for rel in sorted(REQUIRED_CONSUMERS):
            with self.subTest(consumer=rel):
                files = self.consumer_files(rel)
                if files is None:
                    continue
                for path in files:
                    hits = redefinitions(path.read_text(encoding="utf-8"))
                    self.assertEqual(
                        hits, [],
                        f"{path.relative_to(REPO_ROOT)} redefines a contract term outside its "
                        f"'## Round bounds' block: {hits}")


if __name__ == "__main__":
    unittest.main()
