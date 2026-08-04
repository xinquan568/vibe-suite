#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The issue2pr operational-mode surface (vibe-127).

E5.3 (#42) ported the nine-step pipeline and left the **operational modes** behind: `chain`, `resume`,
`iterate` and `list` were named by three shipped documents and defined by none. Two runs died on that
gap before it had an issue number.

**What this module can and cannot establish.** The watcher is a program and is exercised as one — its
exit codes, its precedence, its boundaries. The mode surface is prose, and `test_loop_bounds.py`
records what a test over prose is worth: proving what a document *means*, against a reader looking for
a way through, is an arms race with no natural terminus. So the mode assertions are **structure and
parsed blocks** — a mode must carry every field of the contract, a status word must be a member of a
declared enum, an exit code must map to a named chain effect. That is **drift detection, not an
adversarial guarantee**, and the distinction is stated here rather than implied.

**One assertion crosses artifacts and is worth more than the rest**: the exit→action map in
`operational-modes.md` must have exactly the exit codes `scripts/watch_pr.py` can produce. A
divergence in *either* artifact fails it, which is what a doc and a program agreeing actually means.
"""

import importlib.util
import json
import py_compile
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"
MODES_REF = REPO_ROOT / "skills" / "issue2pr" / "references" / "operational-modes.md"
DRIVER_CONTRACT = REPO_ROOT / "skills" / "issue2pr" / "references" / "driver-contract.md"
COMMAND = REPO_ROOT / "commands" / "issue2pr.md"
CORE_TEST = REPO_ROOT / "tests" / "test_issue2pr_core.py"
WATCH = REPO_ROOT / "scripts" / "watch_pr.py"

#: The four modes this issue owns. Manifest is #130's and is deliberately absent: the tests assert
#: that each *named* mode carries its contract, never that exactly four exist, so the follow-up adds
#: a fifth without touching this list's shape.
MODES = ("chain", "resume", "iterate", "list")

#: A mode is defined when it answers all eight. Round 1 proposed asserting that four names appear,
#: which four empty headings would have satisfied.
CONTRACT_FIELDS = (
    "Invocation", "Reads", "Writes", "Precondition",
    "Refuses", "Statuses read", "Transitions written", "Round bounds",
)

#: An exit→action row must name a real chain effect. Without this a map that answers "handle it"
#: eight times would satisfy set equality against the program.
CHAIN_EFFECTS = ("merged", "closed_unmerged", "pause", "babysit", "cursor",
                 "complete", "notify", "squash", "advance")


def read(path):
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def json_block(text, marker):
    """A named ```json block, parsed rather than grepped — the convention the core already uses."""
    match = re.search(r"(?s)<!--\s*%s\s*-->\s*```json\s*(.*?)```" % re.escape(marker), text)
    return json.loads(match.group(1)) if match else None


def mode_section(text, mode):
    """The body of `## <mode>` up to the next `## `."""
    match = re.search(r"(?sm)^##\s+`?%s`?\s*$(.*?)(?=^##\s|\Z)" % re.escape(mode), text)
    return match.group(1) if match else None


def load_watcher():
    """Loaded lazily so a missing file FAILS a test rather than ERRORing collection."""
    spec = importlib.util.spec_from_file_location("watch_pr", WATCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestModeSurfaceIsFrozen(unittest.TestCase):
    """The structural checks below are drift detection. This one is the guarantee.

    A verifier hollowed this reference twice — first by blanking every field, then, once substance
    was required, by filling the unpinned cells with `alpha beta gamma delta` and keeping only the
    words the regexes demand. The second construction passed all 22 structural tests, and it always
    will: proving a document *means* something, against a reader looking for a way through, is an
    arms race with no natural terminus.

    **That conclusion is this repository's, already paid for.** `test_loop_bounds.py:342` records
    eight successive checks on `commands/fix.md` that a reviewer refuted one after another; the
    resolution was a frozen golden plus an honest statement of scope, not a ninth check. This is the
    same shape, so it takes the same answer rather than re-running the experiment.

    A hollowing is now a golden diff. The cost is that editing the reference means updating the
    golden deliberately — which is the point: a specification should not erode quietly.
    """

    GOLDEN = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "goldens" / "operational-modes.md"

    def test_the_reference_matches_its_golden_byte_for_byte(self):
        self.assertTrue(self.GOLDEN.is_file(), "the golden is missing")
        self.assertEqual(
            read(MODES_REF), self.GOLDEN.read_text(encoding="utf-8"),
            "operational-modes.md differs from its golden. If the change is deliberate, copy it "
            "over the golden in the same commit so the diff is reviewed rather than absorbed.")


class TestModeSurfaceExists(unittest.TestCase):
    def test_the_reference_exists(self):
        self.assertTrue(MODES_REF.is_file(),
                        "skills/issue2pr/references/operational-modes.md is missing; the core names "
                        "modes in three documents and defines them nowhere")

    def test_the_core_cites_the_reference_in_its_established_table_shape(self):
        """`SKILL.md:34-42` already answers 'where is X stated' with a two-column citing table.
        A new surface joins that table rather than inventing a second convention."""
        self.assertIn("references/operational-modes.md", read(SKILL),
                      "the core must cite the mode surface it relies on")

    def test_each_mode_has_a_section(self):
        text = read(MODES_REF)
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertIsNotNone(mode_section(text, mode),
                                     f"`{mode}` has no section in the mode reference")


class TestModeContracts(unittest.TestCase):
    """The depth target. Eight fields per mode, because 'defined' is what the issue asks for."""

    def field(self, mode, name, text=None):
        """A contract field's value — everything up to the next bolded field label."""
        body = mode_section(text or read(MODES_REF), mode) or ""
        found = re.search(r"(?ms)^-\s+\*\*%s:?\*\*(.*?)(?=^-\s+\*\*|\Z)"
                          % re.escape(name), body)
        return found.group(1).strip() if found else None

    def test_every_mode_answers_every_contract_field(self):
        """Labels are not answers.

        A verifier hollowed this document — every field label retained, every value blanked — and it
        passed. The label check is kept because it locates the field; the substance check is what
        makes the field mean something.
        """
        for mode in MODES:
            for name in CONTRACT_FIELDS:
                with self.subTest(mode=mode, field=name):
                    value = self.field(mode, name)
                    self.assertIsNotNone(value, f"`{mode}` does not state its {name}")
                    # Two answers are complete while being short, and the word count is only a proxy
                    # for substance — so each is covered by the check that actually fits it:
                    #   "none"     — `list` writes nothing, and saying so *is* the contract;
                    #   Invocation — `/vibe-suite:issue2pr list` is two words and entirely correct,
                    #                and `test_every_invocation_uses_the_shipped_namespace` pins it
                    #                far harder than counting words would.
                    if name == "Invocation" or re.fullmatch(r"[*\s.]*(none|nothing)[*\s.]*",
                                                            value, re.I):
                        continue
                    self.assertGreaterEqual(
                        len(value.split()), 4,
                        f"`{mode}`'s {name} is {value!r} — a label with no answer behind it")

    def test_every_invocation_uses_the_shipped_namespace(self):
        """D1-revised. Every command in this suite ships under `/vibe-suite:`, and a mode reference
        written to stop the core advertising what it does not have must not itself advertise a
        command that does not exist."""
        for mode in MODES:
            with self.subTest(mode=mode):
                value = self.field(mode, "Invocation") or ""
                self.assertIn("/vibe-suite:issue2pr", value,
                              f"`{mode}`'s invocation omits the shipped namespace")
                self.assertNotRegex(value, r"(?<!vibe-suite:)(?<![\w:])/issue2pr\b",
                                    f"`{mode}` shows an unnamespaced invocation")

    def test_list_is_declared_read_only(self):
        """The one mode whose whole contract is that it writes nothing — and the property this
        repository now depends on, since `runs/_archive/` is skipped by the underscore rule."""
        body = mode_section(read(MODES_REF), "list") or ""
        self.assertRegex(body, r"(?i)read-only|writes\s+nothing|\*\*none\*\*",
                         "`list` must declare that it writes nothing")

    def test_iterate_states_the_inherit_and_override_rule_69_augments(self):
        """#69 adds `--max-review-rounds` to `iterate`. It is blocked until the *semantics* it
        augments are stated — not merely until the word `iterate` appears."""
        body = mode_section(read(MODES_REF), "iterate") or ""
        self.assertIn("max_review_rounds_overrides", body,
                      "`iterate`'s per-round override mechanism must be named")
        self.assertRegex(body, r"(?i)00-meta\.json.*(not|never)",
                         "`iterate` must state that `00-meta.json` is not rewritten")

    def test_the_refused_flags_are_exact_per_mode(self):
        """Checking one flag per mode leaves the rest of the list free to drift or vanish.

        All four modes are pinned, including the two that refuse nothing: "this mode refuses no
        flags" is a claim, and an unpinned empty set is indistinguishable from a list that was
        deleted.
        """
        expected = {
            "chain": {"--scenario", "--base-branch", "--force", "--from-manifest"},
            "resume": {"--max-review-rounds", "--review-mode"},
            "iterate": set(),
            "list": set(),
        }
        for mode, flags in expected.items():
            with self.subTest(mode=mode):
                value = self.field(mode, "Refuses")
                self.assertIsNotNone(value, f"`{mode}` states no Refuses field")
                self.assertEqual(set(re.findall(r"`(--[a-z-]+)`", value)), flags)
                if not flags:
                    self.assertRegex(value, r"(?i)nothing|none",
                                     f"`{mode}` must say so explicitly, not leave the field blank")

    def test_the_matrix_values_that_carry_rules_are_pinned(self):
        """The cells a hollowing would empty first, each asserted for the rule it states."""
        cases = [
            ("chain", "Precondition", r"non-terminal"),
            ("chain", "Writes", r"(?i)every"),          # after *every* transition, not eventually
            ("resume", "Writes", r"(?i)nothing new|continues"),
            ("resume", "Precondition", r"in_progress"),
            ("iterate", "Precondition", r"(?i)terminal"),
            ("iterate", "Writes", r"max_review_rounds_overrides"),
            ("list", "Reads", r"underscore"),           # the rule `runs/_archive/` depends on
            ("list", "Writes", r"(?i)none|nothing"),
        ]
        for mode, name, pattern in cases:
            with self.subTest(mode=mode, field=name):
                self.assertRegex(self.field(mode, name) or "", pattern)

    def test_resume_says_why_the_cap_is_frozen(self):
        """The reason is the load-bearing half: without it, refusing the flag reads as an omission
        someone will helpfully 'fix'."""
        body = mode_section(read(MODES_REF), "resume") or ""
        row = re.search(r"(?ms)^\s*[-|]?\s*\*\*Refuses:?\*\*(.*?)(?=^\s*[-|]?\s*\*\*|\Z)", body)
        self.assertIsNotNone(row)
        self.assertRegex(row.group(1), r"(?i)because|since",
                         "`resume` must say why the cap is frozen mid-round")


class TestIterateCapOverride(unittest.TestCase):
    """vibe-69. `iterate` is the only mode that may raise the cap, so it owns the surrounding rules."""

    def field(self, mode, name):
        body = mode_section(read(MODES_REF), mode) or ""
        found = re.search(r"(?ms)^-\s+\*\*%s:?\*\*(.*?)(?=^-\s+\*\*|\Z)"
                          % re.escape(name), body)
        return found.group(1).strip() if found else ""

    def test_the_run_start_persistence_is_stated_not_only_the_never_rewrite_rule(self):
        """Edit (4) has two halves. Only the second landed in #131.

        The run-start value is written **write-once** to `00-meta.json` and mirrored into
        `state.json` so resume honours it; a per-round override goes to `state.json` alone. Without
        the first half, "never rewritten" describes a file the core never says is written.
        """
        writes = self.field("iterate", "Writes")
        self.assertIn("00-meta.json", writes)
        self.assertRegex(writes, r"(?i)write-once|written once",
                         "the run-start write must be named as write-once")
        self.assertRegex(writes, r"(?i)mirror", "the mirror into state.json must be stated")

    def test_the_flag_is_ignored_with_a_notice_under_the_modes_that_have_no_loop(self):
        """Edit (5)'s missing half. `none` and `single` run no verify loop, so a cap has nothing to
        bound — and silently accepting the flag would imply it did something."""
        bounds = self.field("iterate", "Round bounds")
        self.assertRegex(bounds, r"(?i)ignored", "the flag's fate under none/single must be stated")
        self.assertRegex(bounds, r"(?i)notice", "ignoring silently is indistinguishable from acting")

    def test_the_command_surface_advertises_the_flag_on_iterate(self):
        """Edit (1)'s missing half. The core accepts it; the `argument-hint` a user reads does not."""
        hint = re.search(r"(?m)^argument-hint:\s*\"(.*)\"\s*$", read(COMMAND))
        self.assertIsNotNone(hint)
        iterate = re.search(r"iterate <run-id>([^|]*)", hint.group(1))
        self.assertIsNotNone(iterate, "`iterate <run-id>` is not in the argument hint")
        self.assertIn("--max-review-rounds", iterate.group(1),
                      "iterate accepts the cap flag; the hint must say so")


class TestRunStatusEnum(unittest.TestCase):
    """The hole found while filling the contract matrix: `status` occurs **once** in the core, as an
    example value. `resume` is defined by 'status is in_progress/quota_paused' and `iterate` by
    'status is terminal' — so both are unanchored until the enum exists."""

    def enum(self):
        return json_block(read(MODES_REF), "run-status-enum")

    def test_the_enum_is_declared_as_a_parsed_block(self):
        self.assertIsNotNone(self.enum(),
                             "the mode surface must declare a `run-status-enum` json block")

    def test_the_enum_members_are_exact(self):
        """`assertIn` would pass a list that had lost half its members. The lists are normative, so
        they are pinned exactly and a change to either is a deliberate edit to this test."""
        enum = self.enum() or {}
        self.assertEqual(set(enum), {"non_terminal", "terminal"},
                         "the enum must partition statuses, since `iterate` requires a terminal one")
        self.assertEqual(set(enum.get("non_terminal", [])), {"in_progress", "quota_paused"})
        self.assertEqual(set(enum.get("terminal", [])),
                         {"completed", "stopped_by_max_rounds", "stopped_by_review",
                          "stopped_by_analysis_invalid", "failed"})

    def test_exhausting_the_cap_yields_a_status_iterate_accepts(self):
        """The closure #69 depends on. `EXIT_MAX_ROUNDS` is the commonest reason a round needs
        iterating; if it mapped to a non-terminal status, `iterate` would refuse the very runs it
        exists to rescue."""
        mapping = json_block(read(MODES_REF), "loop-exit-to-status") or {}
        self.assertIn("EXIT_MAX_ROUNDS", mapping, "the loop's cap exit must map to a status")
        status = mapping["EXIT_MAX_ROUNDS"]
        self.assertIn(status, (self.enum() or {}).get("terminal", []),
                      f"{status!r} must be terminal for `iterate` to accept it")

    def test_every_mapped_exit_status_is_a_member(self):
        enum = self.enum() or {}
        members = set(enum.get("non_terminal", [])) | set(enum.get("terminal", []))
        mapping = json_block(read(MODES_REF), "loop-exit-to-status") or {}
        stray = set(mapping.values()) - members
        self.assertEqual(stray, set(), f"exit map names statuses the enum lacks: {sorted(stray)}")

    def test_no_status_is_in_both_halves(self):
        enum = self.enum() or {}
        overlap = set(enum.get("non_terminal", [])) & set(enum.get("terminal", []))
        self.assertEqual(overlap, set(), f"a status cannot be both: {sorted(overlap)}")

    def test_the_cores_own_state_schema_carries_a_member(self):
        """The example value and the enum are two statements about one field.

        The core shipped `"status": "running"` — a name used nowhere else in this pipeline, while
        real run folders and the golden fixtures both say `in_progress`. Declaring the enum without
        this assertion would have left the core's own schema illustrating a status the enum rejects.
        """
        enum = self.enum() or {}
        members = set(enum.get("non_terminal", [])) | set(enum.get("terminal", []))
        schema = json_block(read(SKILL), "state-schema") or {}
        self.assertIn(schema.get("status"), members,
                      "the state schema's example status must be a member of the declared enum")

    def test_every_status_a_mode_names_is_a_member_of_the_enum(self):
        """The assertion that makes the enum load-bearing rather than decorative."""
        enum = self.enum() or {}
        members = set(enum.get("non_terminal", [])) | set(enum.get("terminal", []))
        text = read(MODES_REF)
        cited = set()
        for mode in MODES:
            body = mode_section(text, mode) or ""
            for field in ("Precondition", "Statuses read", "Transitions written"):
                row = re.search(r"(?m)^\s*[-|]?\s*\*\*%s:?\*\*(.*)$" % re.escape(field), body)
                if row:
                    cited |= set(re.findall(r"`(in_progress|quota_paused|completed|failed|"
                                            r"stopped_by_[a-z_]+)`", row.group(1)))
        self.assertTrue(cited, "no mode cites a run status; the preconditions name nothing")
        self.assertEqual(cited - members, set(),
                         f"modes cite statuses the enum does not declare: {sorted(cited - members)}")


class TestWatcherExitActionMap(unittest.TestCase):
    """Set equality proves the two artifacts know the same codes. It does not bind a code to an
    action — a map answering 'handle it' eight times would pass. Both are asserted."""

    def mapping(self):
        block = json_block(read(MODES_REF), "watcher-exit-actions") or {}
        return {int(k): v for k, v in block.items()}

    def test_the_map_is_declared(self):
        self.assertTrue(self.mapping(),
                        "the mode surface must declare a `watcher-exit-actions` json block")

    def test_the_map_covers_exactly_the_codes_the_program_can_produce(self):
        watcher = load_watcher()
        produced = {v for k, v in vars(watcher).items()
                    if k.startswith("EXIT_") and isinstance(v, int)}
        self.assertEqual(set(self.mapping()), produced,
                         "the documented exit set and the program's exit set must be equal")

    def test_every_row_names_a_chain_effect(self):
        for code, action in sorted(self.mapping().items()):
            with self.subTest(exit=code):
                self.assertTrue(any(w in action.lower() for w in CHAIN_EFFECTS),
                                f"exit {code} maps to {action!r}, which names no chain effect")

    def test_each_row_is_specific_to_its_own_code(self):
        """A generic-effect check is satisfied by replacing all eight rows with `notify`.

        Each code owns a word no other code's action would sensibly carry, so a copy-paste map fails
        even though every row still names a chain effect.
        """
        required = {
            0: "ancestor",      # the merge must be verified against the base branch, not trusted
            1: "unmapped",      # exit 1 also governs codes this map does not list
            2: "closed_unmerged",
            3: "classify",      # activity is triaged before it is acted on
            4: "check",         # the feedback for this round is the failing check
            5: "not a pause",   # a timeout re-arms; it does not stop the chain
            6: "consecutive",   # ten in a row, not any failure
            7: "squash",
        }
        mapping = self.mapping()
        for code, needle in required.items():
            with self.subTest(exit=code):
                self.assertIn(needle, mapping.get(code, "").lower(),
                              f"exit {code}'s action does not state {needle!r}")

    def test_no_two_codes_share_an_action(self):
        actions = list(self.mapping().values())
        self.assertEqual(len(set(actions)), len(actions), "two exits map to the same action text")


class TestGuardsResolve(unittest.TestCase):
    def test_the_run_collision_guard_points_at_the_modes_it_names(self):
        """`SKILL.md` refuses an existing run folder 'unless `resume` or `iterate` was asked for' —
        two modes it did not define, so the refusal dangled."""
        text = read(SKILL)
        # The whole bullet, continuation lines included. Requiring the citation on the same physical
        # line would assert wrapping rather than content, and a wrapped bullet is one statement.
        guard = re.search(r"(?ms)^-\s+\*\*A run folder that already exists\*\*.*?(?=^-\s+\*\*|\n\n)",
                          text)
        self.assertIsNotNone(guard, "the run-collision guard is missing")
        self.assertIn("operational-modes", guard.group(0),
                      "the guard names `resume` and `iterate` and must resolve them")


class TestNoDocumentAssertsAnUndefinedCapability(unittest.TestCase):
    """The three false assertions #127 exists to correct — one of which the issue did not know about."""

    def advertised(self):
        text = read(COMMAND)
        hint = re.search(r"(?m)^argument-hint:\s*\"(.*)\"\s*$", text)
        tail = hint.group(1).split("]")[-1] if hint else ""
        from_hint = {s.strip().split(" ")[0].strip("`<>") for s in tail.split("|") if s.strip()}
        line = re.search(r"(?m)^Subcommands:.*$", text)
        from_prose = set(re.findall(r"`([a-z]+)(?:\s+<[^>]+>)?`", line.group(0))) if line else set()
        return {s for s in from_hint if s} | from_prose

    def test_the_argument_hint_and_the_prose_agree(self):
        """The hint is what Claude Code displays, so a divergence is a trigger-accuracy defect."""
        text = read(COMMAND)
        hint = re.search(r"(?m)^argument-hint:\s*\"(.*)\"\s*$", text)
        line = re.search(r"(?m)^Subcommands:.*$", text)
        self.assertIsNotNone(hint)
        self.assertIsNotNone(line)
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertIn(mode, hint.group(1), f"`{mode}` is missing from the argument hint")
                self.assertIn(mode, line.group(0), f"`{mode}` is missing from the subcommand prose")

    def test_the_command_advertises_no_subcommand_the_core_leaves_undefined(self):
        undefined = {s for s in self.advertised() if s not in MODES and s != "profile"}
        self.assertEqual(undefined, set(),
                         f"advertised but undefined in the core: {sorted(undefined)}")

    def test_the_driver_contract_cites_a_chain_definition_that_exists(self):
        """`driver-contract.md` assigns chain-advance decisions to the core, which defined no chain."""
        self.assertIn("operational-modes.md", read(DRIVER_CONTRACT),
                      "the driver contract's chain claims must cite the definition")

    def test_the_core_suite_drives_the_third_executable_it_names(self):
        """`test_issue2pr_core.py`'s docstring names three programs 'driven as subprocesses here'.
        Two were. The Executable tier is enforced only when the third actually runs."""
        text = read(CORE_TEST)
        self.assertIn("watch_pr", text, "the core suite names watch_pr.py but never drives it")
        # `WATCH` and `subprocess.run` both appearing somewhere in the file is not evidence: a
        # cross-file regex matched that pair the moment S0 added the constant, and passed while
        # nothing ran the program. The invocation itself must name it.
        self.assertRegex(text, r"subprocess\.run\(\s*\[[^\]]*\bWATCH\b",
                         "naming the watcher is not driving it — no subprocess call passes WATCH")


class TestWatcherIsAProgram(unittest.TestCase):
    def test_it_exists(self):
        self.assertTrue(WATCH.is_file(), "scripts/watch_pr.py is missing")

    def test_it_compiles(self):
        self.assertTrue(WATCH.is_file(), "scripts/watch_pr.py is missing")
        py_compile.compile(str(WATCH), doraise=True)

    def test_it_carries_the_projects_licence_header(self):
        head = "\n".join(read(WATCH).splitlines()[:3])
        self.assertIn("SPDX-License-Identifier: ISC", head,
                      "ISC within the first three lines; this project is never Apache-2.0")

    def test_it_answers_help_as_a_subprocess(self):
        self.assertTrue(WATCH.is_file(), "scripts/watch_pr.py is missing")
        result = subprocess.run([sys.executable, str(WATCH), "--help"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--merge-when-green", result.stdout)

    def test_it_refuses_a_missing_argument_with_the_usage_code(self):
        self.assertTrue(WATCH.is_file(), "scripts/watch_pr.py is missing")
        result = subprocess.run([sys.executable, str(WATCH), "owner/repo"],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 1, "a usage error exits 1, before the loop")


class WatcherCase(unittest.TestCase):
    """In-process driving. The clock is injected so the timeout and the 180 s floor are reachable
    without waiting, and the poll count is bounded so a non-terminating condition fails rather than
    hanging CI."""

    OPEN = {"state": "OPEN"}
    MERGED = {"state": "MERGED"}
    CLOSED = {"state": "CLOSED"}
    ROLLUP_FAIL = {"statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}]}
    ROLLUP_GREEN = {"statusCheckRollup": [{"conclusion": "SUCCESS"}, {"state": "SUCCESS"}]}
    ROLLUP_EMPTY = {"statusCheckRollup": []}

    def watcher(self, *, state, rollup=None, activity=(), clock=(0,), merge_when_green=False,
                cursor="2026-01-01T00:00:00Z", max_wait=21600, fail_probe=False):
        module = load_watcher()
        ticks = list(clock)

        def now():
            return ticks.pop(0) if len(ticks) > 1 else ticks[0]

        def gh(argv):
            if "--json" in argv and "state" in argv:
                if fail_probe:
                    raise module.GhError("probe failed")
                return json.dumps(state)
            if "--json" in argv and "statusCheckRollup" in argv:
                return json.dumps(rollup if rollup is not None else self.ROLLUP_EMPTY)
            return "\n".join(activity)

        return module, module.Watcher("owner/repo", 1, cursor, poll=0, max_wait=max_wait,
                                      merge_when_green=merge_when_green, gh=gh, clock=now,
                                      max_polls=5)


class TestWatcherExitCodes(WatcherCase):
    def test_merged(self):
        module, w = self.watcher(state=self.MERGED)
        self.assertEqual(w.run(), module.EXIT_MERGED)

    def test_closed_without_merge(self):
        module, w = self.watcher(state=self.CLOSED)
        self.assertEqual(w.run(), module.EXIT_CLOSED)

    def test_new_activity_after_the_cursor(self):
        module, w = self.watcher(state=self.OPEN, activity=["2026-06-01T00:00:00Z"])
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)

    def test_a_completed_check_failed(self):
        module, w = self.watcher(state=self.OPEN, rollup=self.ROLLUP_FAIL)
        self.assertEqual(w.run(), module.EXIT_CHECKS_FAILED)

    def test_timeout(self):
        module, w = self.watcher(state=self.OPEN, clock=(0, 99999), max_wait=10)
        self.assertEqual(w.run(), module.EXIT_TIMEOUT)

    def test_ten_consecutive_probe_failures(self):
        module, w = self.watcher(state=self.OPEN, fail_probe=True)
        w.max_polls = 20
        self.assertEqual(w.run(), module.EXIT_GH_ERRORS)

    def test_green_when_armed_and_past_the_floor(self):
        module, w = self.watcher(state=self.OPEN, rollup=self.ROLLUP_GREEN,
                                 clock=(0, 200), merge_when_green=True)
        self.assertEqual(w.run(), module.EXIT_GREEN)

    def test_a_cursor_of_dash_treats_any_activity_as_new(self):
        module, w = self.watcher(state=self.OPEN, cursor="-", activity=["2000-01-01T00:00:00Z"])
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)


class TestWatcherPrecedence(WatcherCase):
    """One case per edge of `timeout → merged → closed → checks-failed → green → activity`.

    Round 1 listed three cases and called them the chain; only merged-≻-checks-failed was a
    precedence collision at all.
    """

    def test_timeout_beats_merged(self):
        """The timeout is checked *before* the state probe, so the PR's state is unobserved. The
        source logs 'PR still open' at this point and cannot know it."""
        module, w = self.watcher(state=self.MERGED, clock=(0, 99999), max_wait=10)
        self.assertEqual(w.run(), module.EXIT_TIMEOUT)

    def test_timeout_beats_closed(self):
        module, w = self.watcher(state=self.CLOSED, clock=(0, 99999), max_wait=10)
        self.assertEqual(w.run(), module.EXIT_TIMEOUT)

    def test_merged_beats_a_failed_check(self):
        module, w = self.watcher(state=self.MERGED, rollup=self.ROLLUP_FAIL)
        self.assertEqual(w.run(), module.EXIT_MERGED)

    def test_closed_beats_a_failed_check(self):
        module, w = self.watcher(state=self.CLOSED, rollup=self.ROLLUP_FAIL)
        self.assertEqual(w.run(), module.EXIT_CLOSED)

    def test_a_failed_check_beats_new_activity(self):
        module, w = self.watcher(state=self.OPEN, rollup=self.ROLLUP_FAIL,
                                 activity=["2026-06-01T00:00:00Z"])
        self.assertEqual(w.run(), module.EXIT_CHECKS_FAILED)

    def test_green_beats_new_activity(self):
        module, w = self.watcher(state=self.OPEN, rollup=self.ROLLUP_GREEN, clock=(0, 200),
                                 merge_when_green=True, activity=["2026-06-01T00:00:00Z"])
        self.assertEqual(w.run(), module.EXIT_GREEN)


class TestWatcherBoundaries(WatcherCase):
    """Two independent rules, misfiled as precedence in round 1."""

    def test_green_below_the_floor_does_not_exit(self):
        module, w = self.watcher(state=self.OPEN, rollup=self.ROLLUP_GREEN,
                                 clock=(0, 179), merge_when_green=True)
        self.assertNotEqual(w.run(), module.EXIT_GREEN,
                            "180 s is a floor; slow-to-register checks must be allowed to appear")

    def test_green_with_no_registered_check_does_not_exit(self):
        module, w = self.watcher(state=self.OPEN, rollup=self.ROLLUP_EMPTY,
                                 clock=(0, 200), merge_when_green=True)
        self.assertNotEqual(w.run(), module.EXIT_GREEN,
                            "an empty check set is not a green check set")

    def test_a_success_resets_the_failure_counter(self):
        module = load_watcher()
        calls = {"n": 0}

        def gh(argv):
            if "--json" in argv and "state" in argv:
                calls["n"] += 1
                if calls["n"] in (10,):          # one success among nine failures
                    return json.dumps(self.OPEN)
                raise module.GhError("probe failed")
            return json.dumps(self.ROLLUP_EMPTY) if "statusCheckRollup" in argv else ""

        w = module.Watcher("owner/repo", 1, "-", poll=0, max_wait=21600, gh=gh,
                           clock=lambda: 0, max_polls=12)
        self.assertNotEqual(w.run(), module.EXIT_GH_ERRORS,
                            "nine failures then a success must not reach ten consecutive")


class RecordedGh:
    """An invocation-aware fake that answers from **recorded** bodies.

    `WatcherCase` above drives behaviour with inline payloads, which is legible but proves nothing
    about the shapes `gh` really returns. This one is the reconciliation: every answer comes from a
    file under `gh-responses/`, routed by the call's argv and reduced through the port's own adapter.
    It also records each argv so a test can assert the five calls are the ones the plan committed to.
    """

    #: Two corpora, deliberately. `gh-responses/` is E5.4's source-driver spike and is a **closed
    #: set** — `test_source_driver.TestSpikeFixtures` asserts its exact membership, so adding to it
    #: breaks that contract. The watcher's own recordings live separately; both are read here.
    SPIKE = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "gh-responses"
    FIXTURES = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "watch-pr"

    def __init__(self, module, *, state="state-open", rollup="rollup-empty", activity=()):
        self.module = module
        self.state = state
        self.rollup = rollup
        self.activity = list(activity)
        self.calls = []

    def record(self, name):
        for base in (self.FIXTURES, self.SPIKE):
            path = base / f"{name}.json"
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        raise AssertionError(f"no recorded fixture named {name!r} in either corpus")

    def __call__(self, argv):
        self.calls.append(argv)
        if argv[0] == "pr" and "state" in argv:
            record = self.record(self.state)
            if record["exit_code"] != 0:
                raise self.module.GhError(record.get("stderr", "gh failed"))
            return json.dumps(record["body"])
        if argv[0] == "pr" and "statusCheckRollup" in argv:
            return json.dumps(self.record(self.rollup)["body"])
        # Route by the endpoint the fixture *records*, not by its filename. `review-submitted.json`
        # answers `/pulls/{n}/reviews`, and matching names to paths silently answered nothing.
        endpoint = self.endpoint(argv[2])
        for name in self.activity:
            if self.endpoint(self.record(name)["_invocation"]) == endpoint:
                field = argv[-1].split(".")[-1].split(" ")[0]
                return self.module.reduce(self.record(name)["body"], field)
        if endpoint in self.EMPTY_OK:
            return ""          # a genuinely empty collection, declared rather than defaulted
        raise AssertionError(f"no recorded fixture answers {endpoint!r}; returning an invented "
                             f"empty string here is how a fake stops reconciling anything")

    #: The three collections the port actually pages, as **shapes** rather than basenames. Collapsing
    #: to the last segment made `issues/{n}/comments` and `pulls/{n}/comments` the same endpoint, and
    #: let `totally/unroutable/comments` resolve too — so the guard passed anything ending in a name
    #: it recognised.
    EMPTY_OK = frozenset({"issues/*/comments", "pulls/*/reviews", "pulls/*/comments"})

    @staticmethod
    def endpoint(text):
        """`repos/owner/repo/pulls/1/comments` → `pulls/*/comments`."""
        for token in text.split():
            if "/" in token and not token.startswith("-"):
                parts = [p for p in token.rstrip("/").split("/") if p]
                tail = parts[-3:]
                return "/".join("*" if re.fullmatch(r"\d+|\{n\}", p) else p for p in tail)
        return text


class TestRecordedFixturesDriveTheWatcher(unittest.TestCase):
    """Finding 4: the in-process fake alone dropped the reconciliation S1 promised."""

    def watcher(self, **kwargs):
        module = load_watcher()
        gh = RecordedGh(module, **kwargs)
        return module, gh, module.Watcher("owner/repo", 1, "2026-01-01T00:00:00Z", poll=0,
                                          max_wait=21600, gh=gh, clock=lambda: 0, max_polls=3)

    def test_a_recorded_merged_state_exits_merged(self):
        module, _, w = self.watcher(state="merged")
        self.assertEqual(w.run(), module.EXIT_MERGED)

    def test_a_recorded_closed_state_exits_closed(self):
        module, _, w = self.watcher(state="state-closed")
        self.assertEqual(w.run(), module.EXIT_CLOSED)

    def test_a_recorded_failing_rollup_exits_checks_failed(self):
        module, _, w = self.watcher(rollup="rollup-failure")
        self.assertEqual(w.run(), module.EXIT_CHECKS_FAILED)

    def test_a_recorded_activity_collection_exits_activity(self):
        module, _, w = self.watcher(activity=["review-submitted"])
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)

    def test_a_recorded_green_rollup_exits_green_when_armed(self):
        module = load_watcher()
        gh = RecordedGh(module, rollup="rollup-green")
        ticks = iter([0, 200, 200, 200])   # start, then past the 180 s floor
        w = module.Watcher("owner/repo", 1, "-", poll=0, max_wait=21600, merge_when_green=True,
                           gh=gh, clock=lambda: next(ticks, 200), max_polls=3)
        self.assertEqual(w.run(), module.EXIT_GREEN)

    def test_a_recorded_probe_failure_repeated_exits_gh_errors(self):
        """`failure-state-probe.json` is the only recorded failure envelope aimed at the call that
        actually counts. The seven `failure-*.json` files all record the activity call."""
        module = load_watcher()
        gh = RecordedGh(module, state="failure-state-probe")
        w = module.Watcher("owner/repo", 1, "-", poll=0, max_wait=21600, gh=gh,
                           clock=lambda: 0, max_polls=15)
        self.assertEqual(w.run(), module.EXIT_GH_ERRORS)

    def test_one_poll_makes_exactly_the_five_committed_calls(self):
        """argv *and* arity. A port that silently added `-f since`, or issued the rollup twice,
        would pass every behavioural test while diverging from the protocol the plan fixed."""
        module = load_watcher()
        gh = RecordedGh(module)
        module.Watcher("owner/repo", 1, "-", poll=0, max_wait=21600, gh=gh,
                       clock=lambda: 0, max_polls=1).run()
        self.assertEqual(len(gh.calls), 5, f"one poll must make five calls, made {len(gh.calls)}")

        state, rollup, *apis = gh.calls
        self.assertEqual(state, ["pr", "view", "1", "--repo", "owner/repo", "--json", "state"])
        self.assertEqual(rollup,
                         ["pr", "view", "1", "--repo", "owner/repo", "--json", "statusCheckRollup"])
        # By identity, not by class. A previous version checked "has --paginate, lacks -f" and
        # passed against wrong paths, an added `--method GET`, and bogus jq fields.
        self.assertEqual(apis, [
            ["api", "--paginate", "repos/owner/repo/issues/1/comments",
             "--jq", ".[].updated_at // empty"],
            ["api", "--paginate", "repos/owner/repo/pulls/1/reviews",
             "--jq", ".[].submitted_at // empty"],
            ["api", "--paginate", "repos/owner/repo/pulls/1/comments",
             "--jq", ".[].updated_at // empty"],
        ])
        for call in (state, rollup):
            self.assertNotIn("--jq", call, "pr view reduces in Python, not through gh's jq")

    def test_an_unrouted_endpoint_is_an_error_not_an_empty_answer(self):
        """The fake's own guard. Its first version answered "" for anything it could not route, so a
        mis-routed fixture read as a quiet PR — the failure mode this whole issue is about."""
        module = load_watcher()
        gh = RecordedGh(module, activity=["merged"])   # records `pr view`, answers no endpoint
        for path in ("repos/owner/repo/pulls/1/issues",       # not a collection the port pages
                     "totally/unroutable/comments",           # right basename, wrong shape
                     "repos/owner/repo/issues/1/reviews"):    # right names, wrong pairing
            with self.subTest(path=path):
                with self.assertRaises(AssertionError):
                    gh(["api", "--paginate", path, "--jq", ".[].updated_at"])

    def test_repeated_rollup_and_activity_failures_never_reach_the_error_exit(self):
        """The docstring claims only state-probe failures count toward exit 6. Claimed, now tested.

        Twenty consecutive failures of both non-probe calls, with the probe healthy throughout: if
        either contributed, this would exit 6 long before the poll bound.
        """
        module = load_watcher()

        def gh(argv):
            if argv[0] == "pr" and "state" in argv:
                return json.dumps({"state": "OPEN"})
            raise module.GhError("rollup or activity failed")

        w = module.Watcher("owner/repo", 1, "-", poll=0, max_wait=21600, gh=gh,
                           clock=lambda: 0, max_polls=20)
        self.assertNotEqual(w.run(), module.EXIT_GH_ERRORS)


class TestFixtureAdapter(WatcherCase):
    """No fixture on disk is invocation-accurate for this port: `merged.json` requests a superset of
    fields, two activity fixtures send `-f since`, and every activity body is an array while calls
    3-5 emit newline-delimited timestamps. The adapter reconciles that, so it is tested rather than
    assumed."""

    FIXTURES = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "gh-responses"

    def test_field_projection_narrows_a_superset_body(self):
        module = load_watcher()
        body = json.loads((self.FIXTURES / "merged.json").read_text())["body"]
        self.assertEqual(module.project(body, ["state"]), {"state": "MERGED"},
                         "`pr view --json state` against a richer object yields only `state`")

    def test_reduction_turns_a_collection_into_newline_delimited_values(self):
        module = load_watcher()
        body = json.loads((self.FIXTURES / "review-submitted.json").read_text())["body"]
        out = module.reduce(body, "submitted_at")
        self.assertNotIn("[", out, "the reduction emits values, not JSON")
        self.assertTrue(all(re.match(r"\d{4}-\d{2}-\d{2}T", line) for line in out.splitlines() if line))

    def test_reduction_drops_empty_values(self):
        """`--jq '.[].submitted_at // empty'` drops pending reviews rather than emitting blanks."""
        module = load_watcher()
        self.assertEqual(module.reduce([{"submitted_at": None}, {"submitted_at": "x"}],
                                       "submitted_at"), "x")

    def test_the_check_runs_fixture_is_not_a_rollup_response(self):
        """Recorded against `commits/{sha}/check-runs` — a different resource, not a reshaping of
        `pr view --json statusCheckRollup`. The harness must not consume it."""
        record = json.loads((self.FIXTURES / "check-failed.json").read_text())
        self.assertIn("check-runs", record["_invocation"])
        self.assertIsInstance(record["body"], list)


if __name__ == "__main__":
    unittest.main()
