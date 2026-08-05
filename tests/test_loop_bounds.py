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

**All three loops satisfy AC-4's re-ask clause since #123** brought `fix` under the contract. The
test that once characterised the gap now asserts its closure — inverted the day #123 landed, exactly
as its docstring ordered when it recorded the gap.
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

#: The authoritative citing-consumer set, CONSUMED by the delegation tests below — flipping an
#: entry changes what is graded (vibe-123 made fix True when it joined the contract).
CITES_CONTRACT = {"issue2pr": True, "refine-proposal": True, "fix": True}

TERMINAL_STATUS = {"issue2pr": "EXIT_MAX_ROUNDS", "refine-proposal": None, "fix": None}


def document(name):
    return (REPO_ROOT / LOOPS[name]["document"]).read_text(encoding="utf-8")


def extract_section(text, heading):
    """A section's body, **fence-aware and uniqueness-asserting** (vibe-125).

    Generalised from the golden's extractor rather than deleted with it: the fence and uniqueness
    lessons (a fenced decoy heading beats a first-match extractor; two real headings make the
    subject ambiguous) apply to any section a test reads, so the discipline moved up a level when
    the golden died. Takes text, not a loop name, so grammar tests can feed constructed documents.

    No `.strip()` on the body — outer whitespace is part of the text (the ninth refutation: four
    spaces before the first line render it as a code block while a stripped comparison still
    matches).
    """
    def fence_scan(lines):
        """Yield (line, fenced) with real CommonMark-shaped fence tracking: a fence opens with
        three or more backticks OR tildes, and closes only on the same character at at least the
        opening length — so a ``` inside a ```` block is content, and ~~~ fences fence at all
        (the naive startswith("```") toggle missed both, and each miss admitted a decoy)."""
        open_fence = None
        for line in lines:
            match = re.match(r"(`{3,}|~{3,})", line.lstrip())
            if match:
                token = match.group(1)
                if open_fence is None:
                    open_fence = (token[0], len(token))
                    yield line, True
                    continue
                if token[0] == open_fence[0] and len(token) >= open_fence[1]:
                    open_fence = None
                    yield line, True
                    continue
                yield line, True
                continue
            yield line, open_fence is not None

    lines = text.splitlines()
    starts = [i for i, (line, fenced) in enumerate(fence_scan(lines))
              if not fenced and line.rstrip() == heading]
    if len(starts) != 1:
        raise AssertionError(
            "expected exactly one %r heading outside a code fence, found %d" % (heading, len(starts)))
    body = []
    for line, fenced in fence_scan(lines[starts[0] + 1:]):
        if not fenced and line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


#: The complete field set of a `## Round bounds` declaration, and the grammar's whole vocabulary.
ROUND_BOUNDS_FIELDS = ("flag", "floor", "ceiling", "default", "floor-reason",
                       "continue-verdicts", "stop-verdicts", "at-cap")


def parse_round_bounds(text):
    """The `## Round bounds` block as **data under a strict grammar** (vibe-125, issue #125).

    A parsed field has no neighbouring prose to contradict it, so the eight-attempt arms race over
    extraction and comparison ends here — provided the parser is strict. Every body line is a
    `- field: value` bullet; the field vocabulary is closed; duplicates and omissions are errors;
    verdict fields are exact sets of backticked literals with no trailing prose; the flag is exactly
    one backticked literal; the numeric fields are bare integers. A permissive reading anywhere on
    this list is a place prose could creep back in.
    """
    body = extract_section(text, "## Round bounds")
    fields = {}
    for raw in body.splitlines():
        if not raw.strip():
            continue
        match = re.fullmatch(r"- ([a-z-]+): (.+)", raw.rstrip())
        if not match:
            raise AssertionError(
                "not a top-level '- field: value' bullet (indentation included): %r" % raw)
        key, value = match.group(1), match.group(2).strip()
        if key not in ROUND_BOUNDS_FIELDS:
            raise AssertionError("unknown field %r" % key)
        if key in fields:
            raise AssertionError("duplicate field %r" % key)
        fields[key] = value
    missing = [f for f in ROUND_BOUNDS_FIELDS if f not in fields]
    if missing:
        raise AssertionError("missing field(s): %s" % ", ".join(missing))
    for key in ("floor", "ceiling", "default"):
        if not re.fullmatch(r"[0-9]+", fields[key]):
            raise AssertionError("%s must be a bare integer, got %r" % (key, fields[key]))
        fields[key] = int(fields[key])
    for key in ("flag", "continue-verdicts", "stop-verdicts"):
        literals = re.findall(r"`([^`]+)`", fields[key])
        residue = re.sub(r"`[^`]+`", "", fields[key]).replace(",", "").strip()
        if residue:
            raise AssertionError("%s carries prose outside backticked literals: %r" % (key, residue))
        if key == "flag":
            if len(literals) != 1:
                raise AssertionError("flag must be exactly one backticked literal, got %r" % literals)
            fields[key] = literals[0]
        else:
            if not literals:
                raise AssertionError("%s names no backticked literals" % key)
            fields[key] = frozenset(literals)
    return fields


def extract_domain(name):
    """Read a loop's cap domain from its own document, by the shape `loops.json` records.

    One shape today — vibe-125 retired `prose-flag` when `fix` gained its block. The selector
    stays so a second shape must declare itself in `loops.json`, and add its own parser here,
    rather than be guessed from the text.
    """
    text = document(name)
    shape = LOOPS[name]["cap_declaration"]

    if shape == "round-bounds-block":
        body = extract_section(text, "## Round bounds")
        found = {}
        for label in ("floor", "ceiling", "default"):
            match = re.search(r"\b%s\b\W{0,20}?(\d+)" % label, body, re.I)
            if match:
                found[label] = int(match.group(1))
        return found or None

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

    def test_every_contract_consumer_declares_a_round_bounds_block(self):
        """All three since vibe-123; driven by the same authoritative set as the citation test."""
        for name in sorted(CITES_CONTRACT):
            with self.subTest(loop=name):
                self.assertEqual(LOOPS[name]["cap_declaration"], "round-bounds-block")

    def test_fix_declares_a_round_bounds_block(self):
        """Inverted by vibe-125: the third loop now declares structurally too."""
        self.assertEqual(LOOPS["fix"]["cap_declaration"], "round-bounds-block")
        parse_round_bounds(document("fix"))


class TestRoundBoundsAsData(unittest.TestCase):
    """vibe-125: `fix`'s declaration is read as values, not sentences."""

    def test_fix_verdict_routing_is_read_as_data(self):
        fields = parse_round_bounds(document("fix"))
        self.assertEqual(fields["continue-verdicts"], frozenset({"NOT FIXED", "PARTIAL"}))
        self.assertEqual(fields["stop-verdicts"], frozenset({"REGRESSED"}))
        self.assertEqual(fields["flag"], "--max-rounds")
        self.assertEqual(fields["at-cap"], "stop and report")
        self.assertEqual({"floor": fields["floor"], "ceiling": fields["ceiling"],
                          "default": fields["default"]}, EXPECTED_DOMAIN["fix"])

    def test_the_cli_hint_agrees_with_the_block(self):
        """The argument-hint is the one place a number may echo the block — machine-checked.

        The match is scoped to the frontmatter `argument-hint:` value: a document-wide search
        would let stray prose satisfy the assertion after the hint itself lost its range.
        """
        fields = parse_round_bounds(document("fix"))
        front = document("fix").split("---\n", 2)[1]
        hint_line = re.search(r"(?m)^argument-hint:\s*(.+)$", front)
        self.assertIsNotNone(hint_line, "fix.md declares no argument-hint")
        rng = re.search(r"--max-rounds (\d+)-(\d+)", hint_line.group(1))
        self.assertIsNotNone(rng, "the argument-hint no longer names the flag's range")
        self.assertEqual((int(rng.group(1)), int(rng.group(2))),
                         (fields["floor"], fields["ceiling"]),
                         "the CLI hint may echo the block, and must agree with it")

    #: A minimal well-formed document; every grammar cell below is one mutation of it.
    GOOD = "\n".join([
        "# doc", "",
        "## Round bounds", "",
        "- flag: `--max-rounds`",
        "- floor: 1",
        "- ceiling: 5",
        "- default: 3",
        "- floor-reason: since one round can suffice",
        "- continue-verdicts: `NOT FIXED`, `PARTIAL`",
        "- stop-verdicts: `REGRESSED`",
        "- at-cap: stop and report",
        "", "## Next", "", "prose"])

    def test_the_reference_document_parses(self):
        fields = parse_round_bounds(self.GOOD)
        self.assertEqual(fields["floor"], 1)

    def test_round_bounds_grammar_is_strict(self):
        """Table-driven adversarial cells: each is a document a permissive parser would accept."""
        good = self.GOOD
        cells = {
            "heading only inside a fence":
                "# doc\n\n```\n## Round bounds\n```\n\n## Next\n",
            "duplicate real heading":
                good + "\n\n## Round bounds\n\n- flag: `--max-rounds`\n",
            "duplicate field": good.replace("- floor: 1", "- floor: 1\n- floor: 1"),
            "unknown field": good.replace("- at-cap: stop and report",
                                          "- at-cap: stop and report\n- extra: `x`"),
            "missing field": good.replace("- default: 3\n", ""),
            "unbackticked verdict": good.replace("`REGRESSED`", "REGRESSED"),
            "non-bullet body line": good.replace("- floor: 1", "floor is one"),
            "two fields compounded on one bullet":
                good.replace("- floor: 1\n- ceiling: 5", "- floor: 1, ceiling: 5"),
            "flag not exactly one literal":
                good.replace("- flag: `--max-rounds`", "- flag: `--max-rounds` `-r`"),
            "non-integer numeric": good.replace("- default: 3", "- default: three"),
            "trailing prose after verdicts": good.replace("`PARTIAL`", "`PARTIAL` while open"),
            "declaration indented as a code block":
                good.replace("\n- ", "\n    - "),
            "declaration wholly inside a tilde fence":
                "# doc\n\n~~~\n" + good[good.index("## Round bounds"):]
                + "\n~~~\n",
            "long fence not closed by a shorter one":
                "# doc\n\n````\n```\n" + good[good.index("## Round bounds"):]
                + "\n````\n",
        }
        for name, text in cells.items():
            with self.subTest(cell=name):
                with self.assertRaises(AssertionError):
                    parse_round_bounds(text)


class TestContractDelegation(unittest.TestCase):
    """Every registered consumer delegates the re-ask rule to the contract (fix joined at #123)."""

    def test_the_contract_states_the_re_ask_rule_once(self):
        text = CONTRACT.read_text(encoding="utf-8")
        section = re.search(r"(?ms)^##[ ]Verdict parsing[ ]*$(.*?)(?=^##[ ])", text)
        self.assertIsNotNone(section)
        body = section.group(1).lower()
        self.assertIn("exactly once", body)
        self.assertIn("record", body)
        self.assertIn("never abort", body)

    def test_the_registered_consumers_cite_it(self):
        """Driven by CITES_CONTRACT, so the mapping is consumed rather than decorative."""
        for name, cites in sorted(CITES_CONTRACT.items()):
            if not cites:
                continue
            with self.subTest(loop=name):
                self.assertTrue(cites_contract(name))
                self.assertIn("reviewer-contract.md#verdict-parsing", document(name),
                              "delegating the rule means citing the section that states it")

    def test_fix_cites_the_contract(self):
        """Inverted by vibe-123, exactly as the recording test's docstring ordered.

        `fix` predated the contract; #123 registered it as a consumer, added the floor-reason to
        its Round bounds block, and its unusable-verification path now re-asks exactly once before
        degrading. The gap this test once characterised is closed, so it asserts the closure.
        """
        self.assertTrue(cites_contract("fix"),
                        "#123 landed this citation; losing it reopens the AC-4 re-ask gap")
        self.assertIn("reviewer-contract.md#verdict-parsing", document("fix"))

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

    def test_the_verdict_literals_exist_as_uppercase_code_literals(self):
        """Each verdict appears **at least once** as an uppercase code literal. That is the whole claim.

        An earlier version of this docstring said a rename *anywhere* in the document was caught, and
        the README repeated it. Both were wrong: each verdict occurs several times, so lowercasing one
        occurrence outside the frozen section leaves this assertion satisfied. The reviewer found it by
        doing exactly that.

        Overstating an assertion is the specific mistake this link has now made three times, always in
        the same direction. What this catches is a verdict vocabulary removed or renamed **wholesale**.
        Narrower renames inside the declaration fail `parse_round_bounds`'s exact-set assertion;
        the document's remaining prose is not graded, and nothing here claims it is.
        """
        text = document("fix")
        for verdict in ("FIXED", "NOT FIXED", "PARTIAL", "REGRESSED"):
            with self.subTest(verdict=verdict):
                self.assertIn("`%s`" % verdict, text,
                              "the verdicts are code literals; a document that names none of them "
                              "in backticks has renamed the vocabulary")


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
