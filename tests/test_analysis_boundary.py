#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The analysis/planning boundary criterion, and the two pre-closure checks (vibe-70).

Step 1 requires the anti-patterns in play and forbids planning content. An anti-pattern is a
constraint on implementation, so naming one sits exactly on that line — and with no stated test for
which side a sentence falls on, "planning leakage" became the most expensive finding class in the
corpus: raised `major` six times across two runs, six iterations, each remedy scoped to the quoted
instance because there was nothing to sweep against.

**The oracle is the issue's contract, not the document under test.** Every required property below is
a module-level constant transcribed from #70's `Do`, its amendment and the maintainer comment;
`skills/issue2pr/SKILL.md` is the artifact graded against them. That separation is what makes deletion
detectable — a module that read the core and checked the core against itself could not notice the
criterion going missing. `tests/test_reviewer_contract.py` holds its `DOMAINS` the same way, and
`tests/test_issue2pr_core.py` derives its forbidden set from a different file.

**A heading-delimited interval scopes, it does not derive.** `section_span` exists so a section-scoped
property cannot be satisfied by text elsewhere in the file — the technique
`tests/test_reviewer_contract.py` uses for `## Round bounds`. Assertions are on properties rather than
verbatim strings, so a rewording that preserves the property does not fail spuriously.

**Why the rule alone is not enough, asserted rather than assumed.** A bare noun phrase has no subject
and no verb, so no query keyed on modals or grammatical subject selects it. The construction
`"branch, PR title (vibe-N), body Closes #N"` took five iterations to close in `vibe-4`, then
reappeared verbatim in `vibe-9` — inside the document diagnosing the pattern, after a modal sweep and
a subject sweep had both returned clean. The core has to say so, which is what test 6 checks.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"

#: The two sections the criterion and the procedures live in.
BOUNDARY_HEADING = "## The analysis and planning boundary"
CHECKS_HEADING = "## Two checks before every closure dispatch"

#: The headings each pre-closure check's output is pasted under. Verbatim by design: an iteration's
#: record is searched for these, so they are an interface rather than prose.
DIRECT_READ_HEADING = "## Direct read of enumerated lists"
SWEEP_HEADING = "## Decision↔consequence sweep"

#: The steps the two checks apply to — the three update+verify steps.
CLOSURE_STEPS = ("3", "6", "9")

#: The profile field the anti-pattern clause must be quantified over. The issue's own acceptance says
#: "all eight anti-patterns", but eight is the *vibe-suite profile's* count and the core is
#: project-neutral, so the core must name the field and no number.
ANTI_PATTERN_FIELD = "anti_patterns"

#: A count *quantifying* anti-patterns, which must not appear. Deliberately narrow: a bare `\d+`
#: would fire on "Phase 2", which is a phase reference and not a count of anything.
COUNT_OF_ANTI_PATTERNS = re.compile(
    r"(?:all\s+)?\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+anti-pattern", re.I)

HEADING = re.compile(r"^##[ ]\S")


def section_span(text, heading):
    """Locate a section as a **line interval**, plus how many times its heading occurs.

    Returns `(start, end, count)`, 0-based and half-open, where `end` is the next `## ` heading or the
    end of file. `count != 1` is returned rather than swallowed: zero means the section was never
    declared, two means there is no way to say which governs, and both are failures.
    """
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(starts) != 1:
        return (None, None, len(starts))
    start = starts[0]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if HEADING.match(lines[i]):
            end = i
            break
    return (start, end, 1)


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


class CoreCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CORE.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def section(self, heading):
        start, end, count = section_span(self.text, heading)
        self.assertEqual(count, 1,
                         f"the core must declare exactly one '{heading}' section; "
                         f"zero is undeclared, two is ambiguous (found {count})")
        return "\n".join(self.lines[start:end])


class TestTheCriterion(CoreCase):
    """The rule itself: stated once, both halves, with a worked pair."""

    def test_the_boundary_criterion_is_declared_exactly_once(self):
        _, _, count = section_span(self.text, BOUNDARY_HEADING)
        self.assertEqual(count, 1,
                         "the analysis/planning criterion must be stated in exactly one section — "
                         "a second statement of a rule is the beginning of two rules")

    def test_the_criterion_states_both_halves(self):
        """One half alone is not a test. A reader given only 'the work is planning' cannot classify
        a sentence about a rule."""
        low = norm(self.section(BOUNDARY_HEADING))
        self.assertRegex(low, r"subject[^.]{0,80}(rule|current state)[^.]{0,80}analysis",
                         "the criterion must say that a rule-or-current-state subject is analysis")
        self.assertRegex(low, r"subject[^.]{0,60}the work[^.]{0,60}planning",
                         "the criterion must say that a work subject is planning")

    def test_a_contrasting_worked_pair_is_present(self):
        """The pair is what makes the rule usable: both sentences describe one rule, and only the
        second directs work. A rule with no example was what the corpus already had."""
        section = self.section(BOUNDARY_HEADING)
        rows = [ln for ln in section.splitlines()
                if ln.strip().startswith("|") and ln.count("|") >= 3]
        self.assertGreaterEqual(len(rows), 3,
                                "the criterion needs a two-column contrast table (header, separator, "
                                "and at least one worked row)")
        header = norm(rows[0])
        self.assertIn("analysis", header, "one column must be the analysis example")
        self.assertIn("planning", header, "the other column must be the planning example")


class TestTheAntiPatternClause(CoreCase):
    """Naming an anti-pattern is analysis; satisfying it is Phase 2. This is the clause that makes a
    Step-1 output listing the profile's anti-patterns correct rather than a scope finding."""

    def test_the_anti_pattern_clause_is_stated(self):
        """Sentence-scoped rather than order-sensitive.

        An earlier form of this assertion required the tokens in one fixed order and rejected
        "Naming an anti-pattern is analysis" — a rewording that preserves the property exactly. The
        property is that one sentence ties naming an anti-pattern to analysis, and another ties
        satisfying it to Phase 2; word order is not the property.
        """
        sentences = re.split(r"(?<=[.;])\s+", norm(self.section(BOUNDARY_HEADING)))
        naming = [s for s in sentences
                  if "anti-pattern" in s and re.search(r"\bnam(?:e|es|ing)\b", s)]
        self.assertTrue(naming, "the core must have a sentence about naming an anti-pattern")
        self.assertTrue(any("analysis" in s for s in naming),
                        "the core must say naming an anti-pattern is analysis")
        self.assertTrue(any(re.search(r"satisf\w+", s) and "phase 2" in s for s in sentences),
                        "the core must say their satisfaction belongs to Phase 2")

    def test_the_clause_is_quantified_over_the_profile_field_and_names_no_count(self):
        """The issue's acceptance says 'all eight anti-patterns'. Eight is the *vibe-suite profile's*
        count; `anti_patterns` is a profile-supplied list of unspecified length, and the core is
        project-neutral. A count baked into the core would be a project literal with extra steps."""
        section = self.section(BOUNDARY_HEADING)
        self.assertIn(ANTI_PATTERN_FIELD, section,
                      "the clause must be quantified over the profile's `anti_patterns` field")
        hit = COUNT_OF_ANTI_PATTERNS.search(norm(section))
        self.assertIsNone(
            hit,
            f"the core must not name a count of anti-patterns; the number is the bound profile's "
            f"fact, not the core's: {hit.group(0)!r}" if hit else "")


class TestTheStatedInsufficiency(CoreCase):
    """The rule alone is not sufficient, and the exception is specific."""

    def test_the_rule_is_declared_insufficient_and_names_the_construction(self):
        low = norm(self.section(BOUNDARY_HEADING))
        self.assertRegex(low, r"not (?:enough|sufficient)|insufficient",
                         "the core must state that the subject test alone is not sufficient")
        self.assertRegex(low, r"(?:bare )?noun phrase",
                         "the core must name the bare noun phrase as the evading construction")
        self.assertRegex(low, r"no subject and no verb|neither a subject nor a verb",
                         "the core must say why no subject-keyed query selects it")


class TestOneStatementTwoReaders(CoreCase):
    """A criterion only one side holds is not a criterion — that asymmetry is what made this finding
    class expensive. The core has no per-step prompt specifications, so both steps must reach the one
    statement rather than each carrying a copy."""

    def nine_steps(self):
        return self.section("## The nine steps")

    def step_entry(self, number):
        section = self.nine_steps()
        entries, current = {}, None
        for line in section.splitlines():
            match = re.match(r"^(\d)\.\s", line)
            if match:
                current = match.group(1)
                entries[current] = [line]
            elif current and line.startswith("   "):
                entries[current].append(line)
            elif current and not line.strip():
                current = None
        return "\n".join(entries.get(number, []))

    def test_both_steps_reach_the_one_statement(self):
        for step in ("1", "2"):
            with self.subTest(step=step):
                entry = self.step_entry(step)
                self.assertTrue(entry, f"step {step} must be an entry in the nine-step list")
                self.assertIn("boundary", entry.lower(),
                              f"step {step} must reach the one boundary statement, so the worker and "
                              f"the reviewer judge by one criterion rather than two impressions")


class TestTheTwoChecks(CoreCase):
    """Procedural, not advisory. Both were documented as techniques first and failed anyway — one of
    them inside the document that wrote it down. Documenting a technique does not cause it to run."""

    def test_both_closure_check_headings_are_declared(self):
        section = self.section(CHECKS_HEADING)
        for heading in (DIRECT_READ_HEADING, SWEEP_HEADING):
            with self.subTest(heading=heading):
                self.assertIn(heading, section,
                              f"the core must declare {heading!r} verbatim — an iteration's record is "
                              f"searched for it, so it is an interface rather than prose")

    def test_the_checks_are_scoped_to_the_three_update_steps(self):
        section = norm(self.section(CHECKS_HEADING))
        for step in CLOSURE_STEPS:
            with self.subTest(step=step):
                self.assertRegex(section, rf"\b{step}\b",
                                 f"the checks must be scoped to step {step}")

    def test_the_checks_are_procedural_not_advisory(self):
        """A missing heading is an unaddressed finding, not an assumed pass. Without that, an
        iteration can skip a check and look identical to one that ran it."""
        low = norm(self.section(CHECKS_HEADING))
        self.assertRegex(low, r"unaddressed finding",
                         "the core must say the reviewer treats a missing heading as an unaddressed "
                         "finding")
        self.assertRegex(low, r"paste|pasted",
                         "the core must require each check's output pasted into the record, so that "
                         "skipping one is visible")

    def test_the_direct_read_procedure_states_its_obligation(self):
        """Not merely that the heading exists — what it obliges. A section declaring two headings and
        obliging nothing would otherwise pass."""
        low = norm(self.section(CHECKS_HEADING))
        self.assertRegex(low, r"every (?:enumerated )?(?:entry|list)|entry by entry|each entry",
                         "the direct read must oblige reading every enumerated entry")
        self.assertRegex(low, r"not (?:a )?(?:grep|query)|rather than (?:grep|quer)|do not grep",
                         "the direct read must say it is a read rather than a query")
        self.assertRegex(low, r"artifacts? instead of|lists? artifacts|instead of stating a rule",
                         "the direct read must name the artifact-list-instead-of-a-rule failure mode")

    def test_the_sweep_procedure_states_its_obligation(self):
        low = norm(self.section(CHECKS_HEADING))
        self.assertRegex(low, r"every claim[^.]{0,40}chang",
                         "the sweep must cover every claim the iteration changed")
        self.assertRegex(low, r"subject",
                         "the sweep must search by the changed claim's subject")
        self.assertRegex(low, r"superseded|stale|no other section",
                         "the sweep must confirm no section retains the superseded reading")


if __name__ == "__main__":
    unittest.main()
