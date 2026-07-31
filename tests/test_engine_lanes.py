#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Cross-engine lane contracts for score and security-scan (E4.5 / vibe-39).

F4.2 adds `--engine claude|codex|agy|both` to score; F5.1 adds a *requested* second opinion to
security-scan. Both lanes reuse machinery that already ships, so most of what this module asserts is
that the two commands bind to it rather than re-implement it.

**The check catalog is generated, not written down.** The two lanes can only be compared if they speak
one finding vocabulary, and the authority on what check identifiers exist is the engine itself. This
module extracts them from `scripts/score_engine.py` and asserts the command says the catalog comes from
there — a hand-kept list in the command would be a second source of truth that rots the first time a
rule is added.

**Extraction resolves helpers.** Three review passes established that a literal scan is not enough:
`_load_json(text, emit, check)` calls `emit("--", check, -25)` with the identifier as a *parameter*,
and five call sites pass `valid syntax` or `valid JSON`. Literal-only extraction finds 28; the engine
can emit 30.

**What a fake engine can prove, and what it cannot.** `TestLaneStimulus` spawns the real runner against
`fixtures/fake-codex/lane-responder.mjs`, so dispatch arguments, the packaged prompt, the
unusable-vs-unreachable split, and a divergent payload's trip back through the runner are all observed
rather than asserted about prose. It cannot prove a host session renders the disagreement list or the
F9.5 header — no process in this repository performs host rendering. Those two remain command-contract
coverage; the rendered result is the operator's to check.
"""

import ast
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCORE = REPO_ROOT / "commands" / "score.md"
SECURITY = REPO_ROOT / "commands" / "security-scan.md"
ENGINE = REPO_ROOT / "scripts" / "score_engine.py"
GATE_RECORD = REPO_ROOT / "tests" / "agy-contract" / "gate-status.json"

#: The three identifiers that went missing across three review passes -- `frontmatter parse` to a
#: rubric-only vocabulary, `valid syntax` and `valid JSON` to literal-only extraction. Redundant with
#: the union equality below, and kept because a silent count change says less than a named absence.
DEMONSTRATED_LOSSES = ("frontmatter parse", "valid syntax", "valid JSON")

MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})", re.I)


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


def emit_catalog(source):
    """Every check identifier `scripts/score_engine.py` can emit, in two passes.

    Pass 1 — literal: `emit(rule, "<check>", penalty)`.
    Pass 2 — propagated: a helper whose body calls `emit(..., <param>, ...)` takes the identifier as a
    parameter, so each of its call sites contributes the constant passed in that position.

    AST rather than a text scan, for the reason `tests/test_write_discipline.py` gives for its own
    lint: a textual sweep matches comments and misses what is reached through a name.
    """
    tree = ast.parse(source)
    literal = {n.args[1].value for n in ast.walk(tree)
               if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "emit"
               and len(n.args) >= 2 and isinstance(n.args[1], ast.Constant)
               and isinstance(n.args[1].value, str)}

    helpers = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        params = [a.arg for a in fn.args.args]
        for call in ast.walk(fn):
            if (isinstance(call, ast.Call) and getattr(call.func, "id", None) == "emit"
                    and len(call.args) >= 2 and isinstance(call.args[1], ast.Name)
                    and call.args[1].id in params):
                helpers[fn.name] = params.index(call.args[1].id)

    propagated = set()
    for call in ast.walk(tree):
        if isinstance(call, ast.Call) and getattr(call.func, "id", None) in helpers:
            idx = helpers[call.func.id]
            if len(call.args) > idx and isinstance(call.args[idx], ast.Constant) \
                    and isinstance(call.args[idx].value, str):
                propagated.add(call.args[idx].value)
    return literal, propagated


class TestCheckCatalog(unittest.TestCase):
    """The anti-rot layer: a rule added to the engine cannot silently desynchronise the lane."""

    def setUp(self):
        self.literal, self.propagated = emit_catalog(ENGINE.read_text(encoding="utf-8"))

    def test_the_propagated_set_is_not_empty(self):
        """A regression to literal-only extraction would otherwise pass while the catalog quietly
        shrank. This is the assertion that would have caught the third review pass."""
        self.assertTrue(self.propagated,
                        "no helper-propagated check identifiers found; extraction has regressed to "
                        "literal-only and the catalog is now short by however many helpers exist")

    def test_the_demonstrated_losses_are_all_present(self):
        catalog = self.literal | self.propagated
        for check in DEMONSTRATED_LOSSES:
            with self.subTest(check=check):
                self.assertIn(check, catalog,
                              "%r is an identifier the engine emits and three earlier approaches "
                              "lost" % check)

    def test_at_least_one_identifier_has_no_rubric_row(self):
        """Why the catalog exists at all: the rubric is not the set of identifiers the engine emits.

        Measured rather than assumed. Of the 30, exactly **one** -- `frontmatter parse` -- has no
        Check row in `skills/scoring/SKILL.md`; `valid syntax` and `valid JSON` do have rows and were
        lost to *extraction*, not to vocabulary. One is enough: a lane given only the rubric could
        never emit it, and every malformed-frontmatter file would then compare as a disagreement.

        Asserted as "at least one" rather than as a fixed set, because which identifiers lack a rubric
        row is a property of the rubric that a later issue may change, while the *reason* the catalog
        is generated does not depend on the count.
        """
        rubric = (REPO_ROOT / "skills" / "scoring" / "SKILL.md").read_text(encoding="utf-8")
        catalog = self.literal | self.propagated
        engine_only = sorted(c for c in catalog if ("| %s |" % c) not in rubric)
        self.assertTrue(engine_only,
                        "every engine identifier has a rubric row, so packaging the rubric alone "
                        "would suffice and this catalog would be unnecessary")
        self.assertIn("frontmatter parse", engine_only)

    def test_the_catalog_is_larger_than_the_literal_pass_alone(self):
        self.assertGreater(len(self.literal | self.propagated), len(self.literal))


class TestScoreLanes(unittest.TestCase):
    def setUp(self):
        self.text = SCORE.read_text(encoding="utf-8")
        self.norm = norm(self.text)

    def test_the_e45_disclaimer_is_gone(self):
        """E3.3 wrote it to prevent a premature addition and named E4.5 as entitled to remove it."""
        self.assertNotIn("No engine-selection flag exists here", self.text)

    def test_the_flag_is_in_the_argument_hint(self):
        block = self.text.split("---\n", 2)[1]
        hint = re.search(r"(?m)^argument-hint:\s*(.+)$", block).group(1)
        self.assertIn("--engine", hint)
        for mode in ("claude", "codex", "agy", "both"):
            self.assertIn(mode, hint)

    def test_the_deterministic_engine_runs_in_every_mode(self):
        """`--engine` selects what is ADDED, never what is replaced -- otherwise a score command
        could not always answer 'does this pass'."""
        self.assertRegex(self.norm, r"deterministic engine runs in every mode|"
                                    r"selects what is added, never what is replaced")

    def test_the_verdict_is_always_the_computed_score(self):
        self.assertRegex(self.norm, r"verdict[^.]*always the computed|"
                                    r"computed score's, because a threshold")

    def test_the_two_numbers_are_labelled_and_never_merged(self):
        self.assertIn("computed", self.norm)
        self.assertIn("opinion", self.norm)
        self.assertRegex(self.norm, r"never merged")

    def test_the_penalty_authority_sentence_survives(self):
        """The sentence that makes score *score*. A lane addition must not weaken it."""
        self.assertIn("the only penalty authority", self.text)

    def test_the_prompt_carries_the_generated_catalog(self):
        self.assertRegex(self.norm, r"generated from scripts/score_engine\.py|"
                                    r"catalog is generated")
        self.assertRegex(self.norm, r"never written out here|hand-kept list")

    def test_the_disagreement_key_is_the_engine_record(self):
        for component in ("rule", "check", "line", "penalty"):
            self.assertIn(component, self.norm)
        self.assertRegex(self.norm, r"multiset")
        self.assertRegex(self.norm, r"not the rendered table|structured record")

    def test_matching_totals_with_differing_findings_are_still_listed(self):
        self.assertRegex(self.norm, r"totals match[^.]*listed|matching totals is the interesting")

    def test_an_unusable_lane_is_not_a_disagreement(self):
        self.assertRegex(self.norm, r"unusable second opinion")
        self.assertRegex(self.norm, r"no diagnostic header|without a diagnostic header|"
                                    r"nothing is broken to restore")


class TestSecurityScanSecondOpinion(unittest.TestCase):
    def setUp(self):
        self.text = SECURITY.read_text(encoding="utf-8")
        self.norm = norm(self.text)

    def test_it_is_requested_not_default(self):
        self.assertIn("--second-opinion", self.text)
        self.assertRegex(self.norm, r"requested, never a default")

    def test_the_in_session_lane_gates(self):
        self.assertRegex(self.norm, r"in-session scan gates")
        self.assertRegex(self.norm, r"second opinion is advisory")

    def test_a_more_severe_second_opinion_declines_to_gate(self):
        self.assertRegex(self.norm, r"more severe[^|]*no banner|no banner")
        self.assertIn("Scan inconsistent", self.text)

    def test_the_severity_ordering_is_stated(self):
        self.assertRegex(self.norm, r"pass < review < block")

    def test_the_f95_header_opens_the_report_only_when_unreachable(self):
        self.assertRegex(self.norm, r"header opens the report")
        self.assertRegex(self.norm, r"reachable but returns nothing usable|"
                                    r"no header appears|nothing is broken to restore")

    def test_both_lanes_share_one_pattern_database(self):
        self.assertIn("skills/security/SKILL.md", self.text)
        self.assertRegex(self.norm, r"one severity table|both lanes")


class TestSharedLaneDiscipline(unittest.TestCase):
    """Applies to both commands."""

    def _both(self):
        return (("score", SCORE.read_text(encoding="utf-8")),
                ("security-scan", SECURITY.read_text(encoding="utf-8")))

    def test_engine_resolution_goes_through_the_shared_partial(self):
        for name, text in self._both():
            with self.subTest(command=name):
                self.assertIn("commands/shared/model-selection.md", text)
                # The negative must not match the sentence that asserts the CORRECT behaviour --
                # score.md says "never parses .vibe-suite.md itself", which a bare
                # `pars\w+ \.vibe-suite\.md` catches. Look for the affirmative form only.
                self.assertNotRegex(
                    norm(text), r"(?<!never )pars\w+ (its own )?\.vibe-suite\.md directly",
                    "%s must resolve through the shared partial, not parse the config itself" % name)

    def test_the_codex_lane_dispatches_the_runner_directly(self):
        for name, text in self._both():
            with self.subTest(command=name):
                self.assertIn("scripts/codex-runner.mjs", text)
                self.assertRegex(norm(text), r"never scripts/agy-audit-cli\.mjs|"
                                             r"agy-audit-cli\.mjs, which refuses")

    def test_a_pre_gate_agy_request_refuses(self):
        for name, text in self._both():
            with self.subTest(command=name):
                self.assertRegex(norm(text), r"refus\w+")

    def test_the_gate_is_still_shut_so_the_refusal_is_the_live_path(self):
        record = json.loads(GATE_RECORD.read_text(encoding="utf-8"))
        self.assertNotEqual(record["status"], "passed",
                            "the agy gate has flipped; the conditional acceptance clause now needs "
                            "the lane exercised rather than refused")

    def test_provenance_is_disclosed(self):
        for name, text in self._both():
            with self.subTest(command=name):
                self.assertRegex(norm(text), r"provenance")

    def test_no_model_is_named(self):
        for name, text in self._both():
            with self.subTest(command=name):
                hit = MODEL_PIN.search(text)
                self.assertIsNone(hit, "%s pins a model id: %s" % (name, hit.group(0) if hit else ""))
                for line in text.splitlines():
                    if "codex-runner.mjs" in line:
                        self.assertNotRegex(line, r"(?<![\w-])-m\s|\B--model\b")

    def test_read_only_is_the_sandbox_for_both_lanes(self):
        """Neither command fixes anything, so neither ever needs to write."""
        for name, text in self._both():
            with self.subTest(command=name):
                for line in text.splitlines():
                    if "codex-runner.mjs" in line:
                        self.assertIn("read-only", line)
                self.assertNotIn("workspace-write", text)


class TestLaneStimulus(unittest.TestCase):
    """Drive the real runner against a fake engine — the coverage the contract tests cannot give.

    Everything above reads Markdown and Python source. That proves the commands *say* the right
    thing; it cannot prove the lane *does* it, and a review pass caught exactly that gap. These four
    tests spawn `scripts/codex-runner.mjs` with `VIBE_SUITE_CODEX_BIN` pointed at
    `tests/fixtures/fake-codex/lane-responder.mjs`, which records the prompt it was handed and
    returns a payload chosen by `VIBE_TEST_LANE_MODE`.

    Still out of reach, and deliberately so: the *rendered* comparison. No process here runs a host
    session, so what the operator sees is checked by the command contract, not by this class.
    """

    RUNNER = REPO_ROOT / "scripts" / "codex-runner.mjs"
    FIXTURE = REPO_ROOT / "tests" / "fixtures" / "fake-codex" / "lane-responder.mjs"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.probe = self.ws / "probe.json"
        self.addCleanup(self._tmp.cleanup)

    def dispatch(self, prompt, mode="agree", bin_path=None):
        env = dict(os.environ)
        env["VIBE_SUITE_CODEX_BIN"] = str(bin_path or self.FIXTURE)
        env["VIBE_TEST_PROBE"] = str(self.probe)
        env["VIBE_TEST_LANE_MODE"] = mode
        completed = subprocess.run(
            ["node", str(self.RUNNER), "--kind", "review", "--effort", "low",
             "--sandbox", "read-only", "--timeout-ms", "10000", "--", prompt],
            cwd=self.ws, env=env, capture_output=True, text=True, timeout=60)
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"expected one result line, got {lines!r}")
        return completed, json.loads(lines[0])

    @staticmethod
    def catalog():
        literal, propagated = emit_catalog(ENGINE.read_text(encoding="utf-8"))
        return literal | propagated

    @staticmethod
    def lane_answer(result):
        """The engine's answer, dug out of the event stream the runner hands back verbatim.

        `rawOutput` is the whole JSONL stream, not the payload — reading it as JSON directly is the
        mistake this helper exists to stop anyone repeating.
        """
        for line in result["rawOutput"].splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("type") == "item.completed":
                return event["text"]
        raise AssertionError("no item.completed event in the stream")

    def lane_prompt(self):
        """What the command tells the lane to package: the rubric, plus the generated catalog."""
        catalog = sorted(self.catalog())
        return ("Score this artifact against the packaged rubric.\n"
                "Rules: R01-R51, or -- where the row has no rule id.\n"
                "Return findings as {rule, check, line, penalty} records.\n"
                "Valid check identifiers:\n" + "\n".join(catalog) + "\n")

    def test_prompt_carries_the_generated_catalog(self):
        """F4.2's 'same rubric' claim, observed on the wire rather than in prose."""
        prompt = self.lane_prompt()
        self.dispatch(prompt)
        argv = json.loads(self.probe.read_text())["argv"]
        sent = argv[-1]
        self.assertIn("valid syntax", sent)
        self.assertIn("valid JSON", sent)
        self.assertIn("frontmatter parse", sent)
        self.assertIn("{rule, check, line, penalty}", sent)
        for check in self.catalog():
            self.assertIn(check, sent, f"the lane prompt dropped check identifier {check!r}")

    def test_stdin_is_closed_for_the_lane(self):
        """An open stdin hangs codex forever — the one failure that looks like a slow review."""
        self.dispatch(self.lane_prompt())
        self.assertEqual(json.loads(self.probe.read_text())["stdin"], "eof")

    def test_divergent_payload_compares_as_a_record_multiset(self):
        """D3, exercised: a differing score AND an extra finding both surface as disagreements."""
        _, agreed = self.dispatch(self.lane_prompt(), mode="agree")
        _, diverged = self.dispatch(self.lane_prompt(), mode="diverge")

        def records(result):
            payload = json.loads(self.lane_answer(result))
            return payload["score"], [
                (f["rule"], f["check"], f["line"], f["penalty"]) for f in payload["findings"]]

        agreed_score, agreed_findings = records(agreed)
        diverged_score, diverged_findings = records(diverged)

        self.assertNotEqual(agreed_score, diverged_score, "the fixture must actually diverge")
        extra = [r for r in diverged_findings if r not in agreed_findings]
        self.assertEqual(len(extra), 1)
        self.assertEqual(extra[0][1], "scope note")
        for _rule, check, _line, _penalty in agreed_findings:
            self.assertIn(check, self.catalog(),
                          "an agreeing lane must speak the engine's vocabulary")

    def test_unusable_and_unreachable_are_different_states(self):
        """`fallback.md` gives them different hops — collapsing them is the defect to prevent."""
        _, unusable = self.dispatch(self.lane_prompt(), mode="unusable")
        self.assertEqual(unusable["status"], "completed",
                         "a reachable engine that answers uselessly still completed its turn")
        with self.assertRaises(json.JSONDecodeError):
            json.loads(self.lane_answer(unusable))

        completed, unreachable = self.dispatch(
            self.lane_prompt(), bin_path=self.ws / "no-such-engine")
        self.assertEqual(unreachable["status"], "failed")
        self.assertNotEqual(completed.returncode, 0)
        self.assertNotEqual(unusable["status"], unreachable["status"])


if __name__ == "__main__":
    unittest.main()
