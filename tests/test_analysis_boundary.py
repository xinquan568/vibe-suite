#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The analysis/planning boundary criterion, and the two pre-closure checks (vibe-70).

Step 1 requires the anti-patterns in play and forbids planning content. An anti-pattern is a
constraint on implementation, so naming one sits exactly on that line — and with no stated test for
which side a sentence falls on, "planning leakage" became the most expensive finding class in the
corpus: raised `major` six times across two runs, six iterations, each remedy scoped to the quoted
instance because there was nothing to sweep against.

**The oracle is the issue's contract, not the document under test.** Every required property is a
constant or a `check_*` function here, transcribed from #70's `Do`, its amendment and the maintainer
comment; `skills/issue2pr/SKILL.md` is the artifact graded against them. A module that read the core
and checked the core against itself could not notice the criterion going missing.

**Every property is checked against a document that must FAIL it.** An earlier version of this
module asserted twelve properties and passed — and
`tests/fixtures/analysis-boundary/adversarial-core.md`, which contains every required token while
instructing the exact opposite ("Naming an anti-pattern is NOT analysis", "do not paste anything"),
**also passed all twelve.** Token recognition is not property establishment, and the only way to tell
them apart is to show the suite something it must reject. That is what `TestTheNegativeFixture` does,
and it is why the checks below are written as functions returning a reason rather than as bare
`assertRegex` calls: one implementation, two directions.

**Negation is the specific hole that fixture exposed.** An affirmative obligation has to be asserted
*affirmatively* — `affirms()` requires the tokens to co-occur in a sentence that carries no negation
marker, so "must paste" passes and "do not paste" does not.

**A heading-delimited interval scopes, it does not derive.** `section_span` exists so a
section-scoped property cannot be satisfied by text elsewhere in the file — the technique
`tests/test_reviewer_contract.py` uses for `## Round bounds`.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"
NEGATIVE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "analysis-boundary" / "adversarial-core.md"

BOUNDARY_HEADING = "## The analysis and planning boundary"
CHECKS_HEADING = "## Two checks before every closure dispatch"
STEPS_HEADING = "## The nine steps"

#: Anchors the nine-step entries must carry. A step entry that merely says the word "boundary" does
#: not reach the one statement; a resolving link does.
BOUNDARY_ANCHOR = "#the-analysis-and-planning-boundary"
CHECKS_ANCHOR = "#two-checks-before-every-closure-dispatch"

#: The headings each check's output is pasted under — an interface, searched for in a record.
DIRECT_READ_HEADING = "## Direct read of enumerated lists"
SWEEP_HEADING = "## Decision↔consequence sweep"

CLOSURE_STEPS = ("3", "6", "9")
ANTI_PATTERN_FIELD = "anti_patterns"

#: A count *quantifying* anti-patterns. Deliberately narrow: a bare `\d+` would fire on "Phase 2".
COUNT_OF_ANTI_PATTERNS = re.compile(
    r"(?:all\s+)?\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+anti-pattern", re.I)

#: Negation markers. A sentence carrying one of these does not affirm what its tokens name.
NEGATION = re.compile(
    r"\b(?:not|never|no longer|don't|do not|does not|cannot|can't|skip|skips|ignore|ignores|"
    r"ignoring|without|neither|nor|refrain)\b", re.I)

HEADING = re.compile(r"^##[ ]\S")


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


def sentences(text):
    return [s for s in re.split(r"(?<=[.;:])\s+|\n", norm(text)) if s.strip()]


def affirms(text, *tokens):
    """True when one sentence carries every token **and no negation marker**.

    The negation clause is the whole point. "Naming an anti-pattern is NOT analysis" contains
    `anti-pattern`, `naming` and `analysis`, and an assertion keyed on token co-occurrence accepts
    it — which is how the adversarial fixture passed twelve assertions while inverting every one.
    """
    for sentence in sentences(text):
        if all(re.search(t, sentence) for t in tokens) and not NEGATION.search(sentence):
            return True
    return False


def section_span(text, heading):
    """Locate a section as a line interval, plus how many times its heading occurs."""
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


def section(text, heading):
    start, end, count = section_span(text, heading)
    if count != 1:
        return None
    return "\n".join(text.splitlines()[start:end])


def step_entry(text, number):
    body = section(text, STEPS_HEADING)
    if body is None:
        return ""
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


# --- the properties. Each returns None when satisfied, or a reason when not. ------------------

def check_criterion_declared_once(text):
    _, _, count = section_span(text, BOUNDARY_HEADING)
    if count != 1:
        return f"the criterion must be stated in exactly one section (found {count})"
    return None


def check_both_halves(text):
    body = section(text, BOUNDARY_HEADING)
    if body is None:
        return "no boundary section"
    if not affirms(body, r"subject", r"rule|current state", r"analysis"):
        return "must affirm that a rule-or-current-state subject is analysis"
    if not affirms(body, r"subject", r"the work", r"planning"):
        return "must affirm that a work subject is planning"
    return None


def check_worked_pair(text):
    """The pair is the usable part. Both **data cells** must carry real content — a table with
    placeholder cells satisfied the earlier assertion, which only read the header."""
    body = section(text, BOUNDARY_HEADING)
    if body is None:
        return "no boundary section"
    rows = [ln for ln in body.splitlines() if ln.strip().startswith("|") and ln.count("|") >= 3]
    if len(rows) < 3:
        return "needs a two-column contrast table with at least one worked row"
    header = norm(rows[0])
    if "analysis" not in header or "planning" not in header:
        return "the two columns must be the analysis and planning examples"
    for row in rows[2:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        left, right = cells[0], cells[1]
        if len(left) >= 25 and len(right) >= 15 and left != right:
            return None
    return "the worked row's cells must both carry a real example, not a placeholder"


def check_anti_pattern_clause(text):
    body = section(text, BOUNDARY_HEADING)
    if body is None:
        return "no boundary section"
    if not affirms(body, r"anti-pattern", r"nam(?:e|es|ing)", r"analysis"):
        return "must affirm that naming an anti-pattern is analysis"
    if not affirms(body, r"satisf\w+", r"phase 2"):
        return "must affirm that satisfaction belongs to Phase 2"
    return None


def check_no_count(text):
    body = section(text, BOUNDARY_HEADING)
    if body is None:
        return "no boundary section"
    if ANTI_PATTERN_FIELD not in body:
        return f"must be quantified over the profile's `{ANTI_PATTERN_FIELD}` field"
    hit = COUNT_OF_ANTI_PATTERNS.search(norm(body))
    if hit:
        return f"must not name a count of anti-patterns: {hit.group(0)!r}"
    return None


def check_insufficiency(text):
    body = section(text, BOUNDARY_HEADING)
    if body is None:
        return "no boundary section"
    low = norm(body)
    if not re.search(r"not (?:enough|sufficient)|insufficient", low):
        return "must state that the subject test alone is not sufficient"
    if not re.search(r"(?:bare )?noun phrase", low):
        return "must name the bare noun phrase as the evading construction"
    if not re.search(r"no subject and no verb|neither a subject nor a verb", low):
        return "must say why no subject-keyed query selects it"
    return None


def _reaches(entry, anchor):
    """The anchor must be present, and **the clause carrying it** must not be negated.

    Scoped to that clause on purpose. Step 1 legitimately reads "Not planning: no work breakdown…",
    so a blanket negation scan over the whole entry rejects a correct core — it did, before this was
    narrowed. What must not be negated is the sentence that reaches the statement.
    """
    if anchor not in entry:
        return f"must link the statement ({anchor})"
    for sentence in re.split(r"(?<=[.;])\s+|\n", entry):
        if anchor not in sentence:
            continue
        # Negation is judged on the text **preceding** the anchor, because that is what governs the
        # reach. "…decided by [the boundary](#anchor), not by impression" is affirmative — the `not`
        # contrasts what follows. "Do not use [the boundary](#anchor)" is not, and is caught.
        governing = norm(sentence[:sentence.index(anchor)])
        if not NEGATION.search(governing):
            return None
    return f"the clause carrying {anchor} must reach it affirmatively"


def check_both_steps_reach_it(text):
    """A resolving anchor, not the word. The fixture's "Ignore the boundary entirely" contains
    `boundary` and reaches nothing."""
    for step in ("1", "2"):
        entry = step_entry(text, step)
        if not entry:
            return f"step {step} must be an entry in the nine-step list"
        reason = _reaches(entry, BOUNDARY_ANCHOR)
        if reason:
            return f"step {step} {reason}"
    return None


def check_closure_steps_reach_the_checks(text):
    for step in CLOSURE_STEPS:
        entry = step_entry(text, step)
        if not entry:
            return f"step {step} must be an entry in the nine-step list"
        reason = _reaches(entry, CHECKS_ANCHOR)
        if reason:
            return f"step {step} {reason}"
    return None


def check_headings_declared(text):
    body = section(text, CHECKS_HEADING)
    if body is None:
        return "no checks section"
    for heading in (DIRECT_READ_HEADING, SWEEP_HEADING):
        if heading not in body:
            return f"must declare {heading!r} verbatim"
    return None


def check_checks_are_procedural(text):
    body = section(text, CHECKS_HEADING)
    if body is None:
        return "no checks section"
    if not affirms(body, r"unaddressed finding"):
        return "must affirm that a missing heading is an unaddressed finding"
    if not affirms(body, r"paste"):
        return "must affirm that each check's output is pasted into the record"
    if not affirms(body, r"\b(?:3|6|9)\b"):
        return "must affirm the steps the checks apply to"
    return None


def check_direct_read_obligation(text):
    body = section(text, CHECKS_HEADING)
    if body is None:
        return "no checks section"
    if not affirms(body, r"every (?:enumerated )?(?:entry|list)|each entry|entry by entry"):
        return "must affirm reading every enumerated entry"
    if not affirms(body, r"artifacts? instead of|instead of stating a rule|lists? artifacts"):
        return "must affirm the artifact-list-instead-of-a-rule failure mode as what is sought"
    return None


def check_sweep_obligation(text):
    body = section(text, CHECKS_HEADING)
    if body is None:
        return "no checks section"
    if not affirms(body, r"every claim", r"chang"):
        return "must affirm covering every claim the iteration changed"
    if not affirms(body, r"subject"):
        return "must affirm searching by the changed claim's subject"
    if not affirms(body, r"whole"):
        return "must affirm that the search covers the whole artifact"
    if not affirms(body, r"superseded|stale"):
        return "must affirm confirming no section retains the superseded reading"
    return None


#: Properties the adversarial fixture cannot attack by negation, each with its reason and each
#: covered by its own targeted decoy in `TestTheNegativeFixture`. Named individually rather than
#: waived as a class, so a property that silently stopped rejecting the fixture is still caught.
NOT_NEGATION_ATTACKABLE = {
    # structural: the fixture does declare its sections and headings, and should — that is what
    # makes it a test of *meaning* rather than of layout
    "criterion declared exactly once",
    "both check headings declared",
    # violated by addition, not negation: see test_the_count_property_rejects_a_core_that_names_a_count
    "quantified over the field, no count",
    # violated by omission, not negation: see test_the_insufficiency_property_rejects_a_core_that_omits_it
    "the stated insufficiency",
}

#: The twelve properties, as (name, function). One implementation, checked in both directions.
PROPERTIES = (
    ("criterion declared exactly once", check_criterion_declared_once),
    ("both halves of the rule", check_both_halves),
    ("a contrasting worked pair", check_worked_pair),
    ("the anti-pattern clause", check_anti_pattern_clause),
    ("quantified over the field, no count", check_no_count),
    ("the stated insufficiency", check_insufficiency),
    ("steps 1 and 2 reach the criterion", check_both_steps_reach_it),
    ("steps 3, 6 and 9 reach the checks", check_closure_steps_reach_the_checks),
    ("both check headings declared", check_headings_declared),
    ("the checks are procedural", check_checks_are_procedural),
    ("the direct-read obligation", check_direct_read_obligation),
    ("the sweep obligation", check_sweep_obligation),
)


class TestTheCore(unittest.TestCase):
    """The shipped core must satisfy every property."""

    @classmethod
    def setUpClass(cls):
        cls.text = CORE.read_text(encoding="utf-8")

    def test_every_property_holds(self):
        for name, check in PROPERTIES:
            with self.subTest(property=name):
                reason = check(self.text)
                self.assertIsNone(reason, f"{name}: {reason}")


class TestTheNegativeFixture(unittest.TestCase):
    """**The suite must reject a document that carries every token and negates every obligation.**

    Without this, an assertion that merely recognises tokens is indistinguishable from one that
    establishes a property — and the earlier version of this module was the former for all twelve.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = NEGATIVE_FIXTURE.read_text(encoding="utf-8")

    def test_the_fixture_exists(self):
        self.assertTrue(NEGATIVE_FIXTURE.is_file(),
                        "the negative fixture is what keeps these checks honest; without it the "
                        "suite has only ever been shown a document that passes")

    def test_the_fixture_still_carries_the_tokens(self):
        """If the fixture stopped containing the vocabulary it would be rejected for the wrong
        reason, and would stop testing negation-awareness at all."""
        low = norm(self.text)
        for token in ("anti-pattern", "analysis", "planning", "paste", "unaddressed finding",
                      "noun phrase", ANTI_PATTERN_FIELD):
            with self.subTest(token=token):
                self.assertIn(token, low,
                              "the fixture must keep every required token, so that only negation "
                              "distinguishes it from a conformant core")

    def test_the_meaning_bearing_properties_reject_it(self):
        """Every property that asserts *meaning* must fail here.

        Two of the twelve are structural rather than semantic and legitimately hold: the fixture
        declares its two headings verbatim, and it declares the boundary section exactly once. Those
        are excluded by name rather than by a blanket allowance, so a property that silently stopped
        rejecting the fixture would be caught.
        """
        for name, check in PROPERTIES:
            if name in NOT_NEGATION_ATTACKABLE:
                continue
            with self.subTest(property=name):
                self.assertIsNotNone(
                    check(self.text),
                    f"{name}: the adversarial fixture negates this obligation, so the check must "
                    f"reject it — a check that passes here recognises tokens rather than meaning")

    def test_the_count_property_rejects_a_core_that_names_a_count(self):
        """`no count` cannot be attacked by negation — it is violated by *adding* a number, so it
        gets its own decoy rather than a blanket exemption."""
        decoy = self.text.replace("The profile supplies anti_patterns.",
                                  "The profile supplies all eight anti-patterns.")
        self.assertIsNotNone(check_no_count(decoy),
                             "a core naming a count of anti-patterns must be rejected; the number "
                             "is the bound profile's fact, not the project-neutral core's")

    def test_the_insufficiency_property_rejects_a_core_that_omits_it(self):
        """Likewise: the insufficiency is violated by *omission*, not by negation — a core that
        simply drops it still reads as a confident rule, which is the failure #70's amendment is
        about."""
        decoy = "\n".join(ln for ln in self.text.splitlines()
                          if "not sufficient" not in ln and "noun phrase" not in ln)
        self.assertIsNotNone(check_insufficiency(decoy),
                             "a core that omits the stated insufficiency must be rejected — the "
                             "rule alone provably missed real instances three times")


if __name__ == "__main__":
    unittest.main()
