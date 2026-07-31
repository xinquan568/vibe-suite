#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Content contract for `/vibe-suite:roast` and the roasting skill (E4.3 / vibe-37).

F3.1 merges two source commands under one name — grill's `roast` and cc-suite's `audit`, the latter
surviving as `--engine codex|agy`. Most of what it fixes is a number, a threshold or an exact string,
so most of it is checkable.

Three things here exist because an earlier link of this chain shipped the defect they catch.

**The plain-scalar colon rule.** vibe-36's blocker was an agent whose unquoted `description` contained
a colon followed by whitespace — invalid inside a YAML plain scalar, and invisible to a frontmatter
reader that splits on the first colon. That check now covers `agents/`; this module carries it for
`commands/`.

**The dispatch branch.** vibe-35's plan review caught a command routing its default codex lane through
`scripts/agy-audit-cli.mjs`, which refuses before dispatching while the agy contract gate is shut.
Every cross-model run would have failed closed while appearing configured.

**The version stamp is asserted negatively.** F3.1 requires it read from the plugin manifest at run
time (fixing grill's W2). A positive check that the artifact *mentions* the manifest would pass an
artifact that also hardcodes a version, so the assertion is that no version literal appears at all.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND = REPO_ROOT / "commands" / "roast.md"
SKILL = REPO_ROOT / "skills" / "roasting" / "SKILL.md"
MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample-repo"

#: The nine, transcribed from cc-suite commands/audit.md:126-172 (v1.2.0). `docs/disposition.yaml`
#: row cc-suite:10's "nine dimensions preserved" is a claim about exactly this list.
NINE = (
    "Redundant & Low-Value Code",
    "Security & Risk Management",
    "Code Correctness & Reliability",
    "Compliance & Standards",
    "Maintainability & Readability",
    "Performance & Efficiency",
    "Testing & Validation",
    "Dependency & Environment Safety",
    "Documentation & Knowledge Transfer",
)

#: The mini set is a SEPARATE prompt, not a subset (commands/audit.md:97-120). Reading it as
#: five-of-nine changes what a mini run covers, so disjointness is asserted rather than assumed.
MINI_FIVE = (
    "Logic & Correctness",
    "Duplication",
    "Dead Code",
    "Refactoring Debt",
    "Shortcuts & Patches",
)

STYLES = (
    "Architecture Review",
    "Hard-Nosed Critique",
    "Multi-Perspective Panel",
    "ADR Style",
    "Paranoid Mode",
    "Select All",
)
ADDONS = (
    "scale stress", "hidden costs", "principle violations", "strangler fig",
    "success metrics", "before/after diagram", "assumptions audit", "compact & optimize",
)
RECONCILIATION = ("both-agree", "claude-only", "<engine>-only")

VERSION_LITERAL = re.compile(r"\b\d+\.\d+\.\d+\b")
MODEL_PIN = re.compile(
    r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})", re.I)


def read(path):
    return path.read_text(encoding="utf-8")


def norm(text):
    """Phrase-assertion view: emphasis stripped, whitespace collapsed, lowercased.

    Lowercased because the artifacts capitalise list items ("Scale stress") while the sources write
    them lowercase; asserting on the source's casing would be asserting a style the sources do not fix.
    """
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


class TestArtifactsExist(unittest.TestCase):
    def test_command_and_skill_are_present(self):
        self.assertTrue(COMMAND.is_file(), "commands/roast.md is the vibe-37 deliverable")
        self.assertTrue(SKILL.is_file(), "skills/roasting/SKILL.md carries the criteria")


class RoastTestCase(unittest.TestCase):
    def setUp(self):
        if not (COMMAND.is_file() and SKILL.is_file()):
            self.skipTest("artifacts do not exist yet")
        self.cmd = read(COMMAND)
        self.skill = read(SKILL)
        self.cmd_norm = norm(self.cmd)
        self.skill_norm = norm(self.skill)


class TestFrontmatter(RoastTestCase):
    def test_description_and_argument_hint_present(self):
        block = self.cmd.split("---\n", 2)[1]
        self.assertRegex(block, r"^description:")
        self.assertRegex(block, r"(?m)^argument-hint:")

    def test_argument_hint_covers_the_f31_surface(self):
        block = self.cmd.split("---\n", 2)[1]
        hint = re.search(r"(?m)^argument-hint:\s*(.+)$", block).group(1)
        for token in ("--engine", "--style", "--addons", "--output"):
            self.assertIn(token, hint, "argument-hint omits %s" % token)

    def test_no_plain_scalar_carries_a_colon_space(self):
        """vibe-36's blocker, guarded for commands/. A YAML plain scalar may not contain ': ' -- the
        parser reads it as a key separator. Quoted values may contain anything."""
        for path in sorted((REPO_ROOT / "commands").glob("*.md")):
            text = read(path)
            if not text.startswith("---\n"):
                continue
            for lineno, line in enumerate(text.split("---\n", 2)[1].splitlines(), start=2):
                if not line.strip() or line.startswith((" ", "\t", "#")) or ":" not in line:
                    continue
                _, _, value = line.partition(":")
                value = value.strip()
                if value.startswith(('"', "'")):
                    continue
                with self.subTest(command=path.name, line=lineno):
                    self.assertIsNone(
                        re.search(r":\s", value),
                        "%s:%d has ': ' in an unquoted frontmatter value; quote it"
                        % (path.name, lineno))


class TestEngineLanes(RoastTestCase):
    def test_claude_is_the_default_and_runs_in_session(self):
        self.assertRegex(self.cmd_norm, r"claude[^|]*default")

    def test_the_codex_lane_dispatches_the_runner_directly(self):
        """Not through agy-audit-cli.mjs, which refuses before dispatching while the gate is shut."""
        self.assertIn("scripts/codex-runner.mjs", self.cmd)
        self.assertRegex(self.cmd_norm,
                         r"codex-runner\.mjs[^.]*(directly|never through)"
                         r"|(directly|never through)[^.]*codex-runner\.mjs")

    def test_a_pre_gate_agy_request_is_refused_not_degraded(self):
        self.assertRegex(self.cmd_norm, r"refus\w+[^.]*(not degraded|rather than degraded)"
                                        r"|agy[^.]*refus\w+")
        self.assertIn("agy-flip-checklist", self.cmd)

    def test_both_runs_two_lanes_and_labels_the_result(self):
        for label in RECONCILIATION:
            self.assertIn(label, self.cmd + self.skill,
                          "reconciliation label %r is not defined" % label)

    def test_no_model_flag_on_any_dispatch(self):
        for line in self.cmd.splitlines():
            if "codex-runner.mjs" in line or "agy-audit-cli.mjs" in line:
                self.assertNotRegex(line, r"(?<![\w-])-m\s|\B--model\b",
                                    "dispatch names a model (P9): %s" % line.strip())

    def test_no_versioned_model_id_in_either_artifact(self):
        for name, text in (("command", self.cmd), ("skill", self.skill)):
            with self.subTest(artifact=name):
                self.assertIsNone(MODEL_PIN.search(text))


class TestReconFirst(RoastTestCase):
    def test_recon_is_dispatched_before_any_specialist(self):
        self.assertIn("vibe-suite:recon", self.cmd)
        self.assertRegex(self.cmd_norm, r"recon[^.]*(first|before)")

    def test_the_survey_is_injected_with_a_do_not_rediscover_instruction(self):
        self.assertRegex(self.cmd_norm, r"do not re-?discover")

    def test_prior_reports_are_excluded(self):
        self.assertIn("vibe-report-", self.cmd)


class TestDimensionsAndDepth(RoastTestCase):
    def test_all_nine_dimensions_are_named_in_the_skill(self):
        for dim in NINE:
            with self.subTest(dimension=dim):
                self.assertIn(dim, self.skill)

    def test_all_five_mini_dimensions_are_named(self):
        for dim in MINI_FIVE:
            with self.subTest(dimension=dim):
                self.assertIn(dim, self.skill)

    def test_the_two_sets_are_disjoint(self):
        """The source calls them non-overlapping. Asserted on the NAME sets, which is the only form
        that is decidable -- 'Dead Code' and 'Redundant & Low-Value Code' are related in subject and
        distinct as names."""
        self.assertEqual(set(NINE) & set(MINI_FIVE), set())

    def test_the_skill_states_mini_is_not_a_subset(self):
        self.assertRegex(self.skill_norm, r"mini is a separate list|not a subset")

    def test_depth_changes_the_file_set_not_only_the_prompt(self):
        """A --full audit includes test files (dimension 7 is about them); --mini skips them."""
        self.assertRegex(self.cmd_norm + self.skill_norm,
                         r"full[^.]*includes? test files|test files[^.]*full")
        self.assertRegex(self.cmd_norm + self.skill_norm, r"mini[^.]*skips?")

    def test_the_dimension_provenance_is_recorded(self):
        """Transcribed, not invented: the source, its line range and its version are cited so the
        claim is checkable."""
        self.assertIn("commands/audit.md:126-172", self.skill)
        self.assertRegex(self.skill_norm, r"cc-suite 1\.2\.0")

    def test_the_sources_own_inconsistency_is_recorded(self):
        self.assertIn("skills/cc-suite/audit/SKILL.md", self.skill)


class TestStylesAndAddons(RoastTestCase):
    def test_all_six_styles_are_named(self):
        for style in STYLES:
            with self.subTest(style=style):
                self.assertIn(style, self.skill)

    def test_all_eight_addons_are_named(self):
        for addon in ADDONS:
            with self.subTest(addon=addon):
                self.assertIn(addon, self.skill_norm)

    def test_specialist_counts_by_style(self):
        combined = self.cmd_norm + " " + self.skill_norm
        self.assertRegex(combined, r"styles? 1[-–]4[^.]*four")
        self.assertRegex(combined, r"styles? 5[-–]6[^.]*(add|five)")

    def test_select_all_over_500_files_needs_confirmation(self):
        self.assertRegex(self.cmd_norm, r"500 files[^.]*(confirm|ask|stop)"
                                        r"|(confirm|ask|stop)[^.]*500 files")

    def test_batching_threshold_and_group_size(self):
        self.assertRegex(self.cmd_norm, r"more than 20 files[^.]*groups of 10")


class TestReportContract(RoastTestCase):
    def test_default_path_is_minute_granular(self):
        self.assertIn("vibe-report-<YYYY-MM-DD-HHMM>.md", self.cmd)
        self.assertRegex(self.cmd_norm, r"minute")

    def test_output_overrides_the_default(self):
        self.assertRegex(self.cmd_norm, r"--output overrides")

    def test_version_is_read_from_the_manifest_at_run_time(self):
        self.assertIn(".claude-plugin/plugin.json", self.cmd)
        self.assertRegex(self.cmd_norm, r"read from[^.]*plugin\.json|plugin\.json[^.]*run time")

    def test_no_version_literal_is_hardcoded(self):
        """Asserted negatively: a positive check that the artifact mentions the manifest would pass
        an artifact that also hardcodes a version. Fixes grill's W2."""
        hit = VERSION_LITERAL.search(self.cmd)
        self.assertIsNone(hit, "commands/roast.md hardcodes a version: %s"
                          % (hit.group(0) if hit else ""))

    def test_executive_summary_and_phased_plan_are_specified(self):
        self.assertIn("## Executive summary", self.cmd)
        self.assertIn("## Fixing plan", self.cmd)
        self.assertRegex(self.cmd_norm, r"phased")
        self.assertRegex(self.cmd_norm, r"every item cites")

    def test_agent_failure_is_note_and_proceed(self):
        self.assertRegex(self.cmd_norm, r"note-and-proceed|note and proceed")
        self.assertRegex(self.cmd_norm, r"continues?")


class TestFindingIdsAndHeadings(RoastTestCase):
    """The connective contracts the execution review found missing: without them a live report can be
    valid prose and ungradeable."""

    def test_the_command_defines_the_finding_id_scheme(self):
        """A schema finding has no id field, so the ids are a property of the report. Without an
        assigned scheme the fixing plan has nothing to cite and traceability is unenforceable."""
        self.assertRegex(self.cmd_norm, r"f-1[^.]*f-2|number the survivors")
        self.assertIn("F-", self.cmd)

    def test_the_command_and_the_grader_agree_on_the_id_format(self):
        """Bound explicitly: the grader's regex and the command's rendering are two halves of one
        contract, and nothing else would catch them drifting apart."""
        grader = (REPO_ROOT / "tools" / "roast-acceptance.py").read_text(encoding="utf-8")
        self.assertIn(r"F-\d+", grader, "the grader must recognise the F-<n> form")
        self.assertRegex(self.cmd, r"\bF-\d+\b")

    def test_the_cross_model_section_heading_is_exact(self):
        """The heading is the machine-readable part of the report. The skill numbers its own layout
        with `###`; the report's form is `## Dimension: <name>` and the command must say so."""
        self.assertIn("## Dimension: <name>", self.cmd)
        grader = (REPO_ROOT / "tools" / "roast-acceptance.py").read_text(encoding="utf-8")
        self.assertIn("Dimension:", grader)

    def test_the_prescribed_phase_names_appear_in_the_command(self):
        for phase in ("Phase 1 — now", "Phase 2 — next", "Phase 3 — later"):
            with self.subTest(phase=phase):
                self.assertIn(phase, self.cmd)

    def test_the_executive_summary_introduces_no_new_id(self):
        self.assertRegex(self.cmd_norm, r"cites ids but introduces none")


class TestFallbackBeforeNoteAndProceed(RoastTestCase):
    """A failed batch must degrade through the manual lane before it is written off as a gap;
    recording a gap first would skip analysis the fallback contract still owes."""

    def test_a_failed_batch_falls_back_before_it_is_recorded_as_a_gap(self):
        self.assertRegex(self.cmd_norm,
                         r"falls back to the manual[^.]*lane|manual[^.]*lane for that batch")
        self.assertRegex(self.cmd_norm, r"note-and-proceed applies only after")

    def test_the_two_hop_conditions_are_distinguished(self):
        """fallback.md: a header when the engine was unreachable, none when it merely came back
        empty."""
        self.assertRegex(self.cmd_norm, r"unreachable[^.]*header")
        self.assertRegex(self.cmd_norm, r"without one when it merely came back empty|empty")


class TestWriteBoundaries(RoastTestCase):
    def test_the_report_is_the_only_mutation(self):
        self.assertRegex(self.cmd_norm, r"only thing this command creates|"
                                        r"only[^.]*mutation|except the report")

    def test_collision_refuses_rather_than_overwrites(self):
        self.assertRegex(self.cmd_norm, r"refuse[^.]*never overwrite"
                                        r"|already exists[^.]*stop")

    def test_the_report_is_written_once_at_the_end(self):
        self.assertRegex(self.cmd_norm, r"write once|single operation")
        self.assertRegex(self.cmd_norm, r"no partial file|partial")

    def test_never_commits(self):
        self.assertRegex(self.cmd_norm, r"never commits")

    def test_untrusted_input_rule_is_stated_and_sourced(self):
        self.assertRegex(self.cmd_norm, r"data,? never instructions")
        self.assertIn("skills/vibe-core/SKILL.md", self.cmd)


class TestSharedPartialBindings(RoastTestCase):
    def test_the_command_binds_the_partials_it_relies_on(self):
        for partial in ("commands/shared/model-selection.md", "commands/shared/fallback.md",
                        "commands/shared/scope-parse.md"):
            with self.subTest(partial=partial):
                self.assertIn(partial, self.cmd)

    def test_the_skill_is_referenced_rather_than_inlined(self):
        self.assertIn("skills/roasting/SKILL.md", self.cmd)

    def test_the_command_stays_lean(self):
        """Judgement criteria live in the skill; twenty siblings run 48-163 lines."""
        self.assertLessEqual(len(self.cmd.splitlines()), 200)


class TestNamespace(RoastTestCase):
    def test_the_command_is_referenced_under_the_prefix(self):
        self.assertIn("/vibe-suite:roast", self.cmd)

    def test_no_retired_source_name_survives_as_a_command_reference(self):
        for name in ("audit",):
            for pattern in (r"/vibe-suite:%s\b" % name, r"(?<![\w-]):%s\b" % name, r"`%s`" % name):
                with self.subTest(retired=name, pattern=pattern):
                    self.assertIsNone(re.search(pattern, self.cmd),
                                      "commands/roast.md references the retired name %r" % name)


class TestFixture(unittest.TestCase):
    def setUp(self):
        self.assertTrue((FIXTURE / "seeded-issues.json").is_file(),
                        "the sample-repo fixture is a required acceptance artifact")
        self.spec = json.loads(read(FIXTURE / "seeded-issues.json"))

    def test_one_seeded_issue_per_dimension(self):
        seeded = [i["dimension"] for i in self.spec["issues"]]
        self.assertEqual(sorted(seeded), sorted(NINE))

    def test_every_seeded_issue_resolves_to_a_nonblank_line(self):
        for issue in self.spec["issues"]:
            with self.subTest(issue=issue["id"]):
                path = FIXTURE / issue["file"]
                self.assertTrue(path.is_file(), "%s: %s is absent" % (issue["id"], issue["file"]))
                lines = read(path).splitlines()
                self.assertTrue(1 <= issue["line"] <= len(lines),
                                "%s: line %d is outside %s" % (issue["id"], issue["line"],
                                                               issue["file"]))
                self.assertTrue(lines[issue["line"] - 1].strip(),
                                "%s: line %d is blank" % (issue["id"], issue["line"]))

    def test_no_report_is_committed_into_the_fixture(self):
        """The fixture is an input. A committed report would drift from what the command produces."""
        stray = [p.name for p in FIXTURE.rglob("vibe-report-*.md")]
        self.assertEqual(stray, [], "reports must be written to a scratch path, not into the fixture")


class TestRegistration(unittest.TestCase):
    def test_command_and_skill_are_registered(self):
        manifest = json.loads(read(MANIFEST))
        self.assertIn("./commands/roast.md", manifest["commands"])
        self.assertIn("./skills/roasting", manifest["skills"])


if __name__ == "__main__":
    unittest.main()
