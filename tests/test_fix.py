#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Content contract for `/vibe-suite:fix` (E4.4 / vibe-38).

F3.8 fixes a small number of things exactly, and the two that matter most are easy to get subtly
wrong.

**The verifier is never the fixer.** Asserted as a pair *and* as a negative: the artifact must bind
each lane to the other engine, and must not anywhere instruct the fixing engine to grade its own work.
A positive-only check would pass an artifact that said both.

**The verdict surface is closed at four.** F3.8 lists `FIXED`, `NOT FIXED`, `PARTIAL`, `REGRESSED`.
An earlier draft of this plan added a fifth for "no verifier was available"; the plan review rejected
it, because that is the *absence* of a verdict rather than a fifth outcome. Unavailability is recorded
at run level and the per-issue verdict is absent, so this module asserts the closed set and that
absence is described rather than encoded.

The plain-scalar colon rule that caught vibe-36's blocker already covers `commands/` via
`tests/test_roast.py`; it is not duplicated here.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND = REPO_ROOT / "commands" / "fix.md"
MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
SCRIPT_REL = "scripts/mechanical_fix.py"

VERDICTS = ("FIXED", "NOT FIXED", "PARTIAL", "REGRESSED")

#: The declared verdict list is extracted from the artifact and compared as a SET. An earlier
#: revision rejected three hand-picked sentinels, so an arbitrary fifth such as `DEFERRED` passed --
#: a test that enumerates what it forbids can only ever catch what someone thought of.
VERDICT_LINE = re.compile(r"^`FIXED`(.+)$", re.M)

#: The fixer/verifier table, parsed rather than regex-sniffed: a loose pattern matched any occurrence
#: of "in-session" anywhere in the artifact, which a mutation to the table itself would not disturb.
TABLE_ROW = re.compile(r"^\|\s*`(claude|codex)`\s*\|\s*(.+?)\s*\|\s*$", re.M)
MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})", re.I)


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


class TestArtifactExists(unittest.TestCase):
    def test_command_is_present(self):
        self.assertTrue(COMMAND.is_file(), "commands/fix.md is the vibe-38 deliverable")


class FixTestCase(unittest.TestCase):
    def setUp(self):
        if not COMMAND.is_file():
            self.skipTest("commands/fix.md does not exist yet")
        self.text = COMMAND.read_text(encoding="utf-8")
        self.norm = norm(self.text)


class TestArgumentSurface(FixTestCase):
    def test_argument_hint_covers_f38(self):
        block = self.text.split("---\n", 2)[1]
        hint = re.search(r"(?m)^argument-hint:\s*(.+)$", block).group(1)
        for token in ("--severity", "--fixer", "--max-rounds"):
            self.assertIn(token, hint, "argument-hint omits %s" % token)

    def test_the_three_defaults(self):
        self.assertRegex(self.norm, r"severity all[^.]*default|default[^.]*severity all|"
                                    r"--severity all \(the default\)")
        self.assertRegex(self.norm, r"claude \(default\)|default[^.]*claude")
        # vibe-125: the max-rounds default moved from prose ("default 3") into the structured
        # `## Round bounds` block ("- default: 3"); both forms declare it.
        self.assertRegex(self.norm, r"default:? 3|default of 3")

    def test_max_rounds_range(self):
        self.assertRegex(self.norm, r"1[-–]5")


class TestFixerLanes(FixTestCase):
    def test_claude_edits_in_session_and_codex_runs_at_workspace_write(self):
        self.assertRegex(self.norm, r"claude[^|]*in-session")
        self.assertIn("scripts/codex-runner.mjs", self.text)
        self.assertIn("workspace-write", self.text)

    def test_the_fixer_lane_does_not_use_the_verifier_sandbox(self):
        self.assertRegex(self.norm, r"workspace-write explicitly|never .?read-only")

    def test_the_fixer_does_not_route_through_the_gated_audit_cli(self):
        self.assertRegex(self.norm, r"does not route through[^.]*agy-audit-cli|"
                                    r"agy-audit-cli[^.]*refus")

    def test_danger_full_access_is_not_reachable(self):
        self.assertRegex(self.norm, r"danger-full-access is not reachable")


class TestVerifierIsNeverTheFixer(FixTestCase):
    def _verifier_table(self):
        """The `| fixer | verifier |` rows, parsed from the artifact.

        The verifier table and the fixer table both have a `claude`/`codex` first column, so rows are
        taken from the section that follows the verification heading.
        """
        start = re.search(r"(?m)^## Step 4 —", self.text)
        self.assertIsNotNone(start, "no verification step to parse")
        rest = self.text[start.end():]
        end = re.search(r"(?m)^### ", rest)
        section = rest[: end.start()] if end else rest
        return {m.group(1): m.group(2) for m in TABLE_ROW.finditer(section)}

    def test_both_pairings_map_to_the_other_engine(self):
        table = self._verifier_table()
        self.assertEqual(set(table), {"claude", "codex"},
                         "the verifier table must map both fixer lanes")
        self.assertRegex(table["claude"], r"codex-runner\.mjs.*read-only",
                         "a claude fix must be verified by codex, read-only")
        self.assertRegex(table["codex"], r"(?i)in-session",
                         "a codex fix must be verified in-session")
        self.assertRegex(table["codex"], r"(?i)\bclaude\b",
                         "the codex row must name Claude as the verifier; 'in-session' alone would "
                         "be satisfied by an in-session self-verifier")

    def test_the_two_mapped_engines_differ(self):
        """The invariant itself, independent of how either row is worded."""
        table = self._verifier_table()
        claude_row, codex_row = table["claude"].lower(), table["codex"].lower()
        self.assertNotIn("in-session", claude_row,
                         "a claude fix verified in-session would be self-verification")
        self.assertNotIn("codex-runner", codex_row,
                         "a codex fix verified by codex would be self-verification")

    def test_verification_is_fresh_and_read_only(self):
        self.assertRegex(self.norm, r"fresh[^.]*read-only")

    def test_the_artifact_never_instructs_self_verification(self):
        """The negative half. A positive-only check would pass an artifact that said both."""
        for pattern in (r"verif\w+ its own (fix|work)",
                        r"the fixer (verifies|grades) (its own|the)",
                        r"ask the fixer whether it (succeeded|worked) and (accept|use)"):
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.norm),
                                  "the artifact instructs self-verification")

    def test_the_reason_is_stated_not_just_the_rule(self):
        self.assertRegex(self.norm, r"self-report|not a verdict|independent")


class TestVerdictSurface(FixTestCase):
    def test_all_four_verdicts_are_named(self):
        for verdict in VERDICTS:
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, self.text)

    def test_the_declared_verdict_set_is_exactly_four(self):
        """Compared as a set, not against a list of forbidden names: enumerating what is banned only
        ever catches what someone thought to ban."""
        line = VERDICT_LINE.search(self.text)
        self.assertIsNotNone(line, "the artifact must declare its verdicts on one line")
        declared = set(re.findall(r"`([A-Z][A-Z ]+)`", "`FIXED`" + line.group(1)))
        self.assertEqual(declared, set(VERDICTS),
                         "the per-issue verdict surface must be exactly F3.8's four; %s is extra"
                         % sorted(declared - set(VERDICTS)))

    def test_regressed_is_distinguished_from_not_fixed(self):
        self.assertRegex(self.norm, r"regressed[^.]*distinct|distinct[^.]*not fixed|"
                                    r"regressed means the fix broke")


class TestVerifierOutage(FixTestCase):
    def test_only_the_claude_lane_can_reach_it(self):
        self.assertRegex(self.norm, r"only the claude fixer lane|codex fix is verified in-session")

    def test_both_no_usable_verification_conditions_are_covered(self):
        """fallback.md fires the hop for an unreachable engine AND for one that returned nothing
        usable. Scoping the exception to the first would let an empty verification count as a pass."""
        self.assertRegex(self.norm, r"nothing usable|no usable result")
        self.assertRegex(self.norm, r"unreachable")
        self.assertRegex(self.norm, r"header accompanies only the first|"
                                    r"nothing is broken to restore")

    def test_the_manual_hop_still_runs_and_is_disclosed(self):
        self.assertIn("commands/shared/fallback.md", self.text)
        self.assertRegex(self.norm, r"still runs|hop still runs")
        self.assertRegex(self.norm, r"three-field diagnostic header|diagnostic header")

    def test_the_assessment_is_labelled_not_verification(self):
        self.assertRegex(self.norm, r"not verification")

    def test_unavailability_is_recorded_at_run_level(self):
        self.assertIn("verification: unavailable", self.text)

    def test_per_issue_verdicts_are_absent_rather_than_sentinel_valued(self):
        self.assertRegex(self.norm, r"verdicts are absent|absent [-—] not a fifth value|"
                                    r"absent, not a fifth")

    def test_the_loop_stops_and_the_edits_are_kept(self):
        self.assertRegex(self.norm, r"stops after this round")

    def test_unusable_verdict_is_reasked_exactly_once(self):
        """vibe-123: the contract's verdict-parsing rule adopted in place of fall-back-and-stop —
        an unusable answer is re-asked once for only the block; an unreachable engine is not."""
        self.assertRegex(self.norm, r"re-ask(?:ed)? exactly once")
        self.assertIn("reviewer-contract.md#verdict-parsing", self.text)
        self.assertRegex(self.norm, r"edits already made are kept|stopping is not rolling back")

    def test_the_exception_states_its_reason(self):
        """An unexplained exception to a shared partial invites a future edit to 'restore
        consistency', which would reopen self-verification."""
        self.assertRegex(self.norm, r"deliberate exception")
        self.assertRegex(self.norm, r"do not .?restore consistency")


class TestMechanicalStage(FixTestCase):
    def test_the_command_names_the_shipped_engine(self):
        self.assertIn(SCRIPT_REL, self.text)
        self.assertTrue((REPO_ROOT / SCRIPT_REL).is_file(),
                        "the command names an engine that must exist")

    def test_the_table_runs_before_any_model(self):
        """The static half of the ordering claim; the executable half is in
        tests/test_fix_mechanical.py."""
        self.assertRegex(self.norm, r"before any model|mechanical table, before")

    def test_all_five_transformations_are_described(self):
        for phrase in ("allowed-tools", "user-invocable: false", "derive it from the directory",
                       "insert", "argument-hint"):
            with self.subTest(transformation=phrase):
                self.assertIn(phrase.lower(), self.norm)

    def test_conflicts_and_idempotence_are_stated(self):
        self.assertRegex(self.norm, r"conflicts are no-ops|neither is touched")
        self.assertRegex(self.norm, r"idempotent")


class TestCapAndScoring(FixTestCase):
    def test_the_cap_harness_is_attributed_to_e56(self):
        """The acceptance assigns cap coverage elsewhere; claiming it here would be a false gate."""
        self.assertRegex(self.norm, r"e5\.6|#45")
        self.assertRegex(self.norm, r"does not claim that coverage|assigns cap coverage")

    def test_nl_targets_re_score_and_report_deltas(self):
        self.assertIn("scripts/score_engine.py", self.text)
        self.assertRegex(self.norm, r"delta")

    def test_code_targets_have_no_score_oracle(self):
        self.assertRegex(self.norm, r"no such oracle")


class TestDisciplines(FixTestCase):
    def test_no_versioned_model_id(self):
        hit = MODEL_PIN.search(self.text)
        self.assertIsNone(hit, "commands/fix.md pins a model id: %s" % (hit.group(0) if hit else ""))

    def test_no_model_flag_on_any_dispatch(self):
        for line in self.text.splitlines():
            if "codex-runner.mjs" in line:
                self.assertNotRegex(line, r"(?<![\w-])-m\s|\B--model\b")

    def test_untrusted_input_is_stated_for_the_report_itself(self):
        self.assertRegex(self.norm, r"report is data|reports and target files are data")
        self.assertIn("skills/vibe-core/SKILL.md", self.text)

    def test_never_commits(self):
        self.assertRegex(self.norm, r"never commits")

    def test_namespace_and_no_retired_names(self):
        self.assertIn("/vibe-suite:fix", self.text)
        for name in ("audit-fix", "verify"):
            for pattern in (r"/vibe-suite:%s\b" % name, r"(?<![\w-]):%s\b" % name, r"`%s`" % name):
                with self.subTest(retired=name):
                    self.assertIsNone(re.search(pattern, self.text))

    def test_the_command_stays_lean(self):
        self.assertLessEqual(len(self.text.splitlines()), 200)


class TestRegistration(unittest.TestCase):
    def test_the_command_is_registered(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("./commands/fix.md", manifest["commands"])


if __name__ == "__main__":
    unittest.main()
