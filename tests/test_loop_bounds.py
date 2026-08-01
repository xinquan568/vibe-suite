#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""AC-4 — loop bounds and malformed verdicts (E5.6 / vibe-45).

> With a stub reviewer that never returns a clean verdict, every generator-critic loop stops at its
> configured cap with the correct terminal status recorded; a malformed verdict triggers exactly one
> re-ask then degrades and records, never aborts.

**Half of that is not reachable here, and saying so is part of the deliverable.** No process in this
repository executes a markdown loop. `scripts/codex-runner.mjs` dispatches and returns an event stream;
it does not parse a verdict and it does not decide to re-ask — those belong to the host session, from
the contract's verdict-parsing rules. A test that dispatched, found the output unparseable and
dispatched again would be exercising control flow **it wrote itself**, and counting invocations would
measure this file rather than any loop.

So: **the stimulus is executable, the response is specification.** An earlier draft of this issue's plan
claimed the re-ask count as executable, which was the same error two earlier links in this chain had
already made — that is why it is written down here rather than only fixed.

**The three loops do not share a vocabulary**, so one stimulus does not serve all three. A persistent
`blocker` stops `issue2pr` in its first round, before the update loop, so the cap is never reached and
the run merely *looks* bounded. `fix` has no severity at all. See `tests/loop-bounds/README.md`.

**`fix` does not satisfy AC-4's re-ask clause**, and the test below asserts that it does not. That is a
characterisation of a real gap — issue **#123** is filed to close it, and this test fails the day it
lands, which is when the assertion should be inverted.
"""

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOOPS = json.loads((REPO_ROOT / "tests" / "loop-bounds" / "loops.json").read_text(encoding="utf-8"))
README = REPO_ROOT / "tests" / "loop-bounds" / "README.md"
STUB = REPO_ROOT / "tests" / "fixtures" / "fake-codex" / "issue2pr-stub.mjs"
RUNNER = REPO_ROOT / "scripts" / "codex-runner.mjs"
CONTRACT = REPO_ROOT / "skills" / "vibe-core" / "references" / "reviewer-contract.md"

#: Read from the documents, never stored here. These are the expectations the extraction is checked
#: against — they live in the test because a *test* has to know what it expects, whereas `loops.json`
#: is consulted by the extractor and must not.
EXPECTED_DOMAIN = {
    "issue2pr": {"floor": 2, "ceiling": 5, "default": 2},
    "refine-proposal": {"floor": 1, "ceiling": 5, "default": 3},
    "fix": {"floor": 1, "ceiling": 5, "default": 3},
}

CITES_CONTRACT = {"issue2pr": True, "refine-proposal": True, "fix": False}

TERMINAL_STATUS = {"issue2pr": "EXIT_MAX_ROUNDS", "refine-proposal": None, "fix": None}


def document(name):
    return (REPO_ROOT / LOOPS[name]["document"]).read_text(encoding="utf-8")


def extract_domain(name):
    """Read a loop's cap domain from its own document, by the shape `loops.json` says it uses.

    Two shapes, because the loops declare differently and a single parser would have to guess which it
    was reading — which is the only thing `loops.json` exists to record.
    """
    text = document(name)
    shape = LOOPS[name]["cap_declaration"]

    if shape == "round-bounds-block":
        block = re.search(r"(?ms)^##[ ]Round bounds[ ]*$(.*?)(?=^#{1,2}[ ]|\Z)", text)
        if not block:
            return None
        body = block.group(1)
        found = {}
        for label in ("floor", "ceiling", "default"):
            match = re.search(r"\b%s\b\W{0,20}?(\d+)" % label, body, re.I)
            if match:
                found[label] = int(match.group(1))
        return found or None

    if shape == "prose-flag":
        match = re.search(r"--max-rounds\D{0,20}(\d+)\s*[-–]\s*(\d+)\D{0,30}default\s*(\d+)", text, re.I)
        if not match:
            return None
        return {"floor": int(match.group(1)), "ceiling": int(match.group(2)),
                "default": int(match.group(3))}

    raise AssertionError("unknown cap_declaration shape %r" % shape)


def cites_contract(name):
    return "reviewer-contract.md#" in document(name)


class StubCase(unittest.TestCase):
    """The executable half: the stub is a program, so its outputs are observable."""

    def dispatch(self, mode, cwd=None):
        import tempfile
        directory = cwd or tempfile.mkdtemp()
        env = dict(os.environ)
        env["VIBE_SUITE_CODEX_BIN"] = str(STUB)
        env["VIBE_TEST_STUB_VERDICT"] = mode
        result = subprocess.run(
            ["node", str(RUNNER), "--kind", "review", "--effort", "low", "--sandbox", "read-only",
             "--timeout-ms", "10000", "--", "review"],
            cwd=directory, env=env, capture_output=True, text=True, timeout=60)
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"expected one result line, got {lines!r}")
        return json.loads(lines[0])

    def answer(self, payload):
        for line in payload["rawOutput"].splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "item.completed":
                return event["text"]
        raise AssertionError("no item.completed event")

    def verdict_block(self, text):
        """The last fenced block — **`yaml`-tagged and ending the message**, as the contract requires.

        The first version accepted an untagged fence and allowed text after the closing one, so a
        wrapper that violated the contract still produced a block and every downstream assertion
        stayed green. The shape is part of what AC-4 is about, not scaffolding around it.
        """
        match = re.search(r"(?s)```yaml\s*(.*?)```\s*\Z", text)
        return match.group(1) if match else None


class TestNeverClean(StubCase):
    """AC-4's first stimulus. Its subject is the stub, which is a program."""

    def test_revise_never_returns_clean(self):
        """Ten times, because 'never' is not established by one.

        An unknown mode makes the stub fall back to `approve` — a **clean** verdict — which is exactly
        what would make a missing mode look like a passing one. So the assertion is that this mode
        never returns clean, not that it exists.
        """
        for attempt in range(10):
            with self.subTest(attempt=attempt):
                block = self.verdict_block(self.answer(self.dispatch("revise")))
                self.assertIsNotNone(block)
                self.assertNotIn("verdict: approve\n", block,
                                 "a clean verdict from the never-clean mode ends the loop early")
                self.assertIn("approve_with_revisions", block)
                self.assertIn("major", block, "an open finding is what keeps the loop going")

    def test_never_fixed_returns_the_continuing_verdict(self):
        """`fix` has no severity. `REGRESSED` *stops* its loop, which is the opposite of what AC-4
        wants observed, so the stimulus is the verdict that continues it.

        **Parsed, not string-matched.** Searching the raw answer for `NOT FIXED` passed a payload whose
        `verdict` was `approve` and which merely mentioned the phrase in an issue's state — a clean
        verdict that would end the loop rather than continue it.
        """
        for attempt in range(10):
            with self.subTest(attempt=attempt):
                payload = self.dispatch("never-fixed")
                self.assertEqual(payload["status"], "completed")
                parsed = _parse_verdict(self.verdict_block(self.answer(payload)))
                self.assertEqual(parsed["verdict"], "NOT FIXED",
                                 "the verdict field is what a loop reads; a mention is not a verdict")

    def test_a_clean_verdict_is_recognised_as_clean(self):
        """A positive control. Without it, a reader that called everything malformed would satisfy
        every negative assertion in this module."""
        parsed = _parse_verdict(self.verdict_block(self.answer(self.dispatch("approve"))))
        self.assertEqual(parsed["verdict"], "approve")


class TestMalformed(StubCase):
    """AC-4's second stimulus, and the check that it is genuinely malformed."""

    def test_the_malformed_mode_does_not_parse_as_yaml(self):
        """A 'malformed' output that happened to parse would make every downstream claim vacuous."""
        block = self.verdict_block(self.answer(self.dispatch("malformed")))
        self.assertIsNotNone(block, "there must still be a fenced block to fail on")
        with self.assertRaises(ValueError):
            _parse_verdict(block)

    def test_the_malformed_mode_still_completes_its_turn(self):
        """Unparseable is not unreachable. The contract distinguishes them, and a stub that crashed
        would be testing the wrong failure."""
        payload = self.dispatch("malformed")
        self.assertEqual(payload["status"], "completed")


def _parse_verdict(block):
    """The narrowest possible reader: a verdict is `key: value` lines.

    Deliberately not a YAML library — the point is to establish that the malformed fixture is malformed
    under the contract's own grammar, and pulling in a permissive parser could accept it.
    """
    result = {}
    for line in block.strip().splitlines():
        if not line.strip() or line.lstrip().startswith("-"):
            continue
        if ":" not in line:
            raise ValueError("not a key: %r" % line)
        key, _, value = line.partition(":")
        if not re.fullmatch(r"[a-z_]+", key.strip()):
            raise ValueError("not a verdict key: %r" % key)
        result[key.strip()] = value.strip()
    if "verdict" not in result:
        raise ValueError("no verdict key")
    return result


class TestExtraction(unittest.TestCase):
    """Each loop's cap, read from its own document by the shape `loops.json` names."""

    def test_loops_json_holds_no_loop_facts(self):
        """Anything a document could disagree with does not belong here."""
        for name, entry in LOOPS.items():
            with self.subTest(loop=name):
                self.assertEqual(set(entry), {"document", "cap_declaration"},
                                 "loops.json records where to look and how, never what is found")

    def test_every_document_exists(self):
        for name in LOOPS:
            with self.subTest(loop=name):
                self.assertTrue((REPO_ROOT / LOOPS[name]["document"]).is_file())

    def test_each_cap_domain_is_extractable_and_correct(self):
        for name, expected in EXPECTED_DOMAIN.items():
            with self.subTest(loop=name):
                self.assertEqual(extract_domain(name), expected,
                                 "the document's declaration and the expectation disagree; one of "
                                 "them is wrong and the diff says which")

    def test_the_two_registered_consumers_declare_a_round_bounds_block(self):
        for name in ("issue2pr", "refine-proposal"):
            with self.subTest(loop=name):
                self.assertEqual(LOOPS[name]["cap_declaration"], "round-bounds-block")

    def test_fix_declares_its_cap_in_prose(self):
        """A different shape, which is the only reason an extractor selector exists."""
        self.assertEqual(LOOPS["fix"]["cap_declaration"], "prose-flag")


class TestContractDelegation(unittest.TestCase):
    """Which loops delegate the re-ask rule, and which does not."""

    def test_the_contract_states_the_re_ask_rule_once(self):
        text = CONTRACT.read_text(encoding="utf-8")
        section = re.search(r"(?ms)^##[ ]Verdict parsing[ ]*$(.*?)(?=^##[ ])", text)
        self.assertIsNotNone(section)
        body = section.group(1).lower()
        self.assertIn("exactly once", body)
        self.assertIn("record", body)
        self.assertIn("never abort", body)

    def test_the_registered_consumers_cite_it(self):
        for name in ("issue2pr", "refine-proposal"):
            with self.subTest(loop=name):
                self.assertTrue(cites_contract(name))
                self.assertIn("reviewer-contract.md#verdict-parsing", document(name),
                              "delegating the rule means citing the section that states it")

    def test_fix_does_not_cite_the_contract(self):
        """**A characterisation, not an endorsement.**

        `fix` predates the contract and its unusable-verification path falls back and stops rather than
        re-asking once, so AC-4's re-ask clause does not hold for it. Issue **#123** is filed to close
        that.

        This test **fails the day #123 lands**, which is when it should be inverted. It starts green on
        purpose: it records a gap rather than driving work, and a gap nobody records is one nobody
        closes.
        """
        self.assertFalse(cites_contract("fix"),
                         "#123 has landed — invert this assertion and add `fix` to the registry")

    def test_the_gap_is_recorded_where_a_reader_will_find_it(self):
        self.assertIn("#123", README.read_text(encoding="utf-8"))


#: **Any** SHOUTING_SNAKE token. An earlier version matched only `EXIT_*` and `*_STATUS`, which left
#: `HALT_MAX_ROUNDS` and `MAX_ROUNDS_REACHED` free to appear — a longer list of known names is not the
#: same as detecting the shape.
TERMINAL_TOKEN = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

#: The one signal that separates a status from an environment variable, and it is **syntactic**.
#:
#: Three attempts got here. Excluding lines containing a backtick removed the real status, because a
#: status is written in backticks precisely because it is a term of art. Excluding lines mentioning
#: `environment` discarded any second status sharing such a line. Scoping that word-search to a window
#: around the token still excused `HALT_MAX_ROUNDS` in "The environment is noted; the run records
#: HALT_MAX_ROUNDS at the cap" — prose near a token says nothing reliable about the token.
#:
#: A variable is **interpolated** — `${NAME}` or `$NAME` — and a status never is. That is a fact about
#: the syntax rather than about the surrounding sentence, so no phrasing can talk its way past it.
INTERPOLATED = re.compile(r"\$\{?\Z")


def declared_terminal_statuses(name):
    """Every run-level terminal status a document names, not just the ones we thought of.

    Judged by whether the token is interpolated, which is a property of the token rather than of the
    prose around it — the three earlier attempts all judged by neighbourhood, and each let something
    through that the neighbourhood happened to excuse.
    """
    text = document(name)
    found = set()
    for match in TERMINAL_TOKEN.finditer(text):
        if INTERPOLATED.search(text[max(0, match.start() - 3):match.start()]):
            continue
        found.add(match.group(0))
    return found


class TestTerminalVocabulary(unittest.TestCase):
    """Only one of the three names a run-level terminal status — and that is checked as a set."""

    def test_issue2pr_names_exactly_its_own_terminal_status(self):
        """Asserting the expected token is *present* left a second one free to appear beside it."""
        self.assertEqual(declared_terminal_statuses("issue2pr"), {TERMINAL_STATUS["issue2pr"]})

    def test_the_status_is_a_terminal_state_not_a_failure(self):
        """This chain's own runs have hit it, and the core says what it means. A harness asserting it
        as an error would encode the opposite."""
        text = document("issue2pr")
        window = text[text.index("EXIT_MAX_ROUNDS"):][:400].lower()
        self.assertIn("terminal", window)
        self.assertIn("not a failure", window)

    def test_the_other_two_name_none_at_all(self):
        """Not "none of the one we thought of". A different status introduced in either document is a
        new shared vocabulary invented without saying so, which is the thing this asserts against."""
        for name in ("refine-proposal", "fix"):
            with self.subTest(loop=name):
                self.assertIsNone(TERMINAL_STATUS[name])
                self.assertEqual(declared_terminal_statuses(name), set(),
                                 "a run-level terminal status here would mean the three loops now "
                                 "share a vocabulary — which is a change, not a detail")

    def test_fix_verdicts_carry_their_continue_or_stop_meaning(self):
        """Reading `NOT FIXED` as terminal would invert what it means.

        Checking only that the four tokens *occur* left the semantics free to flip — a document saying
        `NOT FIXED` stops the loop would have passed the test named for the opposite.
        """
        text = document("fix")
        low = norm(text)
        for verdict in ("FIXED", "NOT FIXED", "PARTIAL", "REGRESSED"):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, text)

        # The two that continue and the one that stops — searched on **both sides** of the verdict.
        # Looking only after it let "stop while any remain NOT FIXED" through, because the word that
        # inverts the meaning sits in front.
        self.assertRegex(low, r"(regressed[^.]{0,120}(stop|halt|abort)|(stop|halt|abort)[^.]{0,120}regressed)",
                         "REGRESSED is the verdict that ends the loop")
        # Matched as the **uppercase verdict token**, not as an English word. Lowercasing first made
        # "that partial's message" — an ordinary adjective about something else entirely — look like a
        # claim about the verdict, and the test failed on prose it had no business reading.
        # Load-bearing half: **the exact declaration**, whitespace-normalised. Not an inference about
        # meaning — three attempts at inferring meaning from English each passed on inverted text, and
        # the third *claimed* to be closed:
        #
        #   1. "no stopping phrase after the verdict"  — beaten by putting the phrase in front
        #   2. "no stopping verb stem in the sentence" — beaten by "causes the loop to exit"
        #   3. "a continuing word near the verdict"    — beaten by "continue to reporting; any
        #      NOT FIXED or PARTIAL prevents another round", which satisfies the proximity check while
        #      inverting the meaning, and uses a verb no stop-list contains
        #
        # Each fix matched **lexical proximity rather than the relation** between verdict and verb, so
        # each was evaded by a sentence with the right words in the wrong relation. A string equality
        # has no relation to get wrong. This is the golden-fixture approach the rest of the repository
        # already uses, applied to one load-bearing sentence.
        #
        # The cost is real and is the point: rewording this clause **fails the test**, so the semantics
        # of the loop cannot be changed as a side effect of an edit. Whoever rewords it updates the
        # constant deliberately.
        with self.subTest(half="declared-continuing"):
            self.assertIn(
                REQUIRED_CONTINUE_DECLARATION, low,
                "commands/fix.md must declare the round loop in exactly these words; any rewording "
                "is a deliberate change to loop semantics and updates this constant with it")

        # Backstop half, and **it is not a proof**. The exact-text anchor above fixes what the document
        # *declares*; it cannot stop a contradiction being added somewhere else in the file. Catching
        # that needs meaning-detection, which is the thing three iterations established cannot be done
        # reliably here — the set of English words meaning "stops" is open, so any list is evadable by
        # a word not on it. `prevents another round`, the phrasing that beat attempt 3, is still not
        # caught and deliberately so: adding it would restart the enumeration this test just abandoned.
        # Kept because the common phrasings are worth catching. The README states its strength exactly.
        for verdict in ("NOT FIXED", "PARTIAL"):
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if verdict not in sentence:
                    continue
                with self.subTest(verdict=verdict, half="backstop", sentence=sentence[:60]):
                    self.assertNotRegex(
                        sentence.lower(),
                        r"\b(stop|stops|stopping|halt|halts|halting|end|ends|ending|exit|exits|"
                        r"exiting|cease|ceases|ceasing|conclude|concludes|concluding|quit|quits|"
                        r"terminate|terminates|terminating|abort|aborts|aborting|final)\b",
                        "%s continues the loop; a sentence pairing it with a stopping verb "
                        "inverts AC-4's stimulus, whatever the phrasing" % verdict)


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


#: The round-loop declaration in `commands/fix.md`, verbatim after `norm()`. Held as a constant so the
#: assertion is a string equality rather than a judgement about English — see the three failed
#: judgement-based attempts recorded at the call site.
#:
#: Normalisation is deliberately minimal: it collapses whitespace so the clause can wrap across lines,
#: strips `**`/backticks so emphasis can move, and lowercases. It does **not** touch word order,
#: punctuation, or vocabulary, which is where an inversion has to live.
REQUIRED_CONTINUE_DECLARATION = (
    "a round is: fix the issues still open → verify → keep going while "
    "any remain not fixed or partial."
)


class TestReadmeStatesTheLimit(unittest.TestCase):
    """The honest half of the deliverable."""

    def test_it_says_which_clauses_are_unreachable(self):
        text = README.read_text(encoding="utf-8").lower()
        self.assertIn("no process in this repository executes a markdown loop", text)
        self.assertIn("executable is the stimulus, not the response", text.replace("**", ""))

    def test_it_does_not_claim_the_re_ask_is_observed(self):
        text = README.read_text(encoding="utf-8")
        section = text[text.index("| AC-4 clause"):]
        row = [line for line in section.splitlines() if "one re-ask" in line]
        self.assertTrue(row, "the re-ask clause must appear in the tier table")
        self.assertIn("Contract", row[0],
                      "claiming it Executable is the error this file exists to stop repeating")


if __name__ == "__main__":
    unittest.main()
