#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The analysis/planning boundary criterion, and the two pre-closure checks (vibe-70).

Step 1 requires the anti-patterns in play and forbids planning content. An anti-pattern is a
constraint on implementation, so naming one sits exactly on that line — and with no stated test for
which side a sentence falls on, "planning leakage" became the most expensive finding class in the
corpus: raised `major` six times across two runs, six iterations, each remedy scoped to the quoted
instance because there was nothing to sweep against.

**This is drift detection, not an adversarial guarantee**, and that distinction was paid for twice —
once in this repository already.

Three successive attempts here tried to establish that the core *means* the right thing, and a
reviewer refuted each:

| # | Check | Refuted by |
|---|---|---|
| 1 | token co-occurrence per property | a core carrying every token and negating every obligation passed all twelve |
| 2 | negation-aware `affirms()` over a fixed marker list | a fresh core using "Reject", "Bypass", "Discard", "Avoid", "Preserve" |
| 3 | semantic exemptions with targeted decoys | "Discard the profile's `anti_patterns`" satisfied the no-count check; "It is false that this rule is not sufficient" satisfied the insufficiency check; reversed worked-example cells passed a length-and-inequality test; "Scan less than the whole artifact" satisfied the whole-artifact assertion |

The fourth attempt is not a fourth vocabulary. `tests/test_loop_bounds.py:342` records the identical
race on `commands/fix.md` — **eight** checks, eight refutations — and its conclusion applies verbatim:
establishing what a prose document means, against a reader actively looking for a way through, is an
arms race over extraction and comparison surfaces with no natural end. The criterion #70 asks for is
Contract-tier: what is claimable is that the specification says so.

So the two sections are **frozen byte for byte** against goldens, and the rest of this module checks
only structure that cannot be argued about. What that catches is the realistic failure — an edit
altering the criterion as a side effect of touching something nearby, which cannot happen without a
reviewer seeing the golden change in the same commit. **It does not catch someone deliberately
constructing a document to defeat it, and nothing here claims it does.** Closing that needs a
structured declaration the core does not have; the boundary would have to become parsed data rather
than prose, which is a different issue.

Extraction is **fence-aware** and asserts **uniqueness**, because a fenced code block containing a
decoy copy of a heading satisfies a first-match extractor while the operative section is free to
change — the eighth refutation in the sibling race. There is **no `.strip()`**: four leading spaces
would be discarded while markdown renders the line as an indented code block, which was the ninth.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "analysis-boundary"

BOUNDARY_HEADING = "## The analysis and planning boundary"
CHECKS_HEADING = "## Two checks before every closure dispatch"
STEPS_HEADING = "## The nine steps"

#: Frozen sections, and the golden holding each one's text.
FROZEN = (
    (BOUNDARY_HEADING, FIXTURES / "boundary-section.md"),
    (CHECKS_HEADING, FIXTURES / "checks-section.md"),
)

#: Anchors the nine-step entries must carry. A step entry that merely says the word "boundary" does
#: not reach the one statement; a link that resolves to the section does.
BOUNDARY_ANCHOR = "#the-analysis-and-planning-boundary"
CHECKS_ANCHOR = "#two-checks-before-every-closure-dispatch"

#: The headings each check's output is pasted under — an interface, searched for in a run record.
DIRECT_READ_HEADING = "## Direct read of enumerated lists"
SWEEP_HEADING = "## Decision↔consequence sweep"

CLOSURE_STEPS = ("3", "6", "9")
ANTI_PATTERN_FIELD = "anti_patterns"

#: A count *quantifying* anti-patterns. Deliberately narrow: a bare `\d+` would fire on "Phase 2",
#: which is a phase reference rather than a count of anything.
COUNT_OF_ANTI_PATTERNS = re.compile(
    r"(?:all\s+)?\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+anti-pattern", re.I)


def core_text():
    return CORE.read_text(encoding="utf-8")


def section(heading, text=None):
    """A section's body, extracted fence-aware, with its heading required to be unique.

    Uniqueness is asserted rather than resolved by taking the first match: two real headings of the
    same name is a document problem, and picking one silently is how a decoy heading works.
    """
    lines = (text if text is not None else core_text()).splitlines()
    fenced, starts = False, []
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced and line.rstrip() == heading:
            starts.append(i)
    if len(starts) != 1:
        raise AssertionError(
            "expected exactly one %r heading outside a code fence, found %d — a second one makes the "
            "frozen section ambiguous" % (heading, len(starts)))
    fenced, body = False, []
    for line in lines[starts[0] + 1:]:
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("## "):
            break
        body.append(line)
    # No .strip(): outer whitespace is part of the frozen text like everything else.
    return "\n".join(body)


def step_entry(number):
    body = section(STEPS_HEADING)
    entries, current = {}, None
    for line in body.splitlines():
        match = re.match(r"^(\d)\.\s", line)
        if match:
            current = match.group(1)
            entries[current] = [line]
        elif current and line.startswith("   "):
            entries[current].append(line)
        elif current and not line.strip():
            current = None
    return "\n".join(entries.get(number, []))


class TestTheFrozenSections(unittest.TestCase):
    """The whole semantic claim, reduced to the one thing that is actually establishable."""

    def test_each_section_matches_its_golden_byte_for_byte(self):
        for heading, golden in FROZEN:
            with self.subTest(section=heading):
                self.assertTrue(golden.is_file(), f"missing golden: {golden}")
                self.assertEqual(
                    section(heading), golden.read_text(encoding="utf-8"),
                    f"{heading!r} changed in skills/issue2pr/SKILL.md. If that was deliberate, update "
                    f"{golden.relative_to(REPO_ROOT)} in the same commit — the point is that the "
                    f"criterion cannot move without a reviewer seeing it")

    def test_the_goldens_are_not_empty(self):
        """An empty golden would make the freeze vacuous, and would match an empty section."""
        for _, golden in FROZEN:
            with self.subTest(golden=golden.name):
                self.assertGreater(len(golden.read_text(encoding="utf-8").strip()), 400,
                                   "a golden this short cannot be holding a stated criterion")


class TestTheStructure(unittest.TestCase):
    """Structural facts, which a decoy cannot argue with. Nothing here reads meaning."""

    def test_both_sections_are_declared_exactly_once(self):
        for heading, _ in FROZEN:
            with self.subTest(section=heading):
                section(heading)  # raises if the heading is absent or duplicated

    def test_steps_1_and_2_link_the_criterion(self):
        """One statement, two readers — a criterion only one side holds is not a criterion, and that
        asymmetry is what made this finding class expensive. A resolving anchor is checkable; whether
        the surrounding sentence endorses it is not, and is the golden's job."""
        for step in ("1", "2"):
            with self.subTest(step=step):
                entry = step_entry(step)
                self.assertTrue(entry, f"step {step} must be an entry in the nine-step list")
                self.assertIn(BOUNDARY_ANCHOR, entry,
                              f"step {step} must link the one boundary statement")

    def test_the_closure_steps_link_the_checks(self):
        for step in CLOSURE_STEPS:
            with self.subTest(step=step):
                entry = step_entry(step)
                self.assertTrue(entry, f"step {step} must be an entry in the nine-step list")
                self.assertIn(CHECKS_ANCHOR, entry, f"step {step} must link the two checks")

    def test_both_check_headings_are_declared_verbatim(self):
        """These are an interface: a run record is searched for them, so the spelling is load-bearing
        in a way ordinary prose is not."""
        body = section(CHECKS_HEADING)
        for heading in (DIRECT_READ_HEADING, SWEEP_HEADING):
            with self.subTest(heading=heading):
                self.assertIn(heading, body, f"the core must declare {heading!r} verbatim")

    def test_the_criterion_is_quantified_over_the_profile_field(self):
        """`anti_patterns` is a profile-supplied list of unspecified length and the core is
        project-neutral, so a count baked in here is a project literal with extra steps."""
        body = section(BOUNDARY_HEADING)
        self.assertIn(ANTI_PATTERN_FIELD, body,
                      f"the clause must be quantified over the profile's `{ANTI_PATTERN_FIELD}`")
        hit = COUNT_OF_ANTI_PATTERNS.search(body)
        self.assertIsNone(hit, "the core must not name a count of anti-patterns; how many there are "
                               "is the bound profile's fact")


class TestWhatIsNotClaimed(unittest.TestCase):
    """The limit, asserted rather than left to a docstring nobody re-reads.

    Overstating an assertion is the mistake the sibling race made three times, always in the same
    direction. So the module says in its own text what it does not establish.
    """

    def test_the_module_states_that_this_is_drift_detection(self):
        text = Path(__file__).read_text(encoding="utf-8")
        self.assertIn("drift detection, not an adversarial guarantee", text)
        self.assertIn("nothing here claims it does", text,
                      "the module must say plainly that a deliberately constructed document is not "
                      "caught — a reader trusts this file to know what to distrust")


if __name__ == "__main__":
    unittest.main()
