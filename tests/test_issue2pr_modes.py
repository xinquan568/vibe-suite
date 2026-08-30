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

import ast
import contextlib
import io
import importlib.util
import json
import pathlib
import shutil
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

#: Every mode the core defines. This began as four with manifest deliberately absent — #130 was the
#: follow-up, and it arrived. The tests assert that each *named* mode carries its contract, never
#: that a particular number exists, which is why adding the fifth cost one entry here.
MODES = ("chain", "resume", "iterate", "list", "manifest")

#: Modes invoked by a flag rather than a subcommand, mapped to the flag that starts them. Manifest
#: mode replaces a run's *inputs* rather than selecting a different lifecycle, so it is a flag — and
#: the advertised-surface check has to know that, or it reads the flag as an undefined subcommand.
MODE_FLAGS = {"manifest": "--from-manifest"}

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
                if mode in MODE_FLAGS:
                    self.assertIn(MODE_FLAGS[mode], value,
                                  f"`{mode}` is flag-invoked; its invocation must show the flag")
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
        # vibe-135: each row is now a record — operator guidance plus a machine `effect`
        # the mode driver executes. The word checks bind the guidance; the driver's own
        # suite binds the effects.
        for code, record in sorted(self.mapping().items()):
            with self.subTest(exit=code):
                action = record["guidance"]
                self.assertTrue(any(w in action.lower() for w in CHAIN_EFFECTS),
                                f"exit {code} maps to {action!r}, which names no chain effect")
                self.assertIn("effect", record,
                              f"exit {code} declares no machine effect for the mode driver")

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
                guidance = mapping.get(code, {}).get("guidance", "")
                self.assertIn(needle, guidance.lower(),
                              f"exit {code}'s guidance does not state {needle!r}")

    def test_no_two_codes_share_an_action(self):
        actions = [record["guidance"] for record in self.mapping().values()]
        self.assertEqual(len(set(actions)), len(actions), "two exits map to the same action text")

    def test_exit_3_declares_the_author_gate_and_exit_4_opts_out(self):
        # vibe-188: the declaration — not the driver — says which authors may trigger a babysit round,
        # what happens otherwise (notify-only; auto-merge never re-armed; the decision recorded), and
        # that a failing check (exit 4) has no author to gate on.
        mapping = self.mapping()
        three = mapping[3]["effect"]
        self.assertEqual(three["requires"], ["classification", "babysit_round", "babysit_cap"], "the flag is required by the gate, for actionable activity")
        gate = three["author_gate"]
        self.assertEqual(gate["applies_to"], "actionable")
        self.assertEqual(gate["babysit_allowed"], ["OWNER", "MEMBER", "COLLABORATOR"])
        otherwise = gate["otherwise"]
        self.assertEqual(otherwise["report"], "notify-only")
        self.assertEqual(otherwise["link_flag"], {"auto_merge_rearm": False})
        self.assertIn("NOT re-armed", otherwise["timeline_note"])
        self.assertEqual(otherwise.get("cursor"), "advance")
        self.assertEqual(otherwise.get("result_events"), [], "the notify-only branch awaits no result event")
        self.assertIn("edge", three["by_classification"]["actionable_within_cap"], "the collaborator path is unchanged")
        four = mapping[4]["effect"]
        self.assertEqual(four["as"], "3")
        self.assertIsNone(four["author_gate"])
        self.assertNotIn("requires", four, "exit 4 inherits its requirements from exit 3 through the alias")
        for code, guidance in ((3, mapping[3]["guidance"]), (4, mapping[4]["guidance"])):
            self.assertIn("classify" if code == 3 else "check", guidance.lower())
        self.assertIn("never re-armed", mapping[3]["guidance"])


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
                # A flag-invoked mode does not belong in a list of subcommands — saying so would be
                # its own inaccuracy. It must still be stated in the prose, just not as one.
                where = text if mode in MODE_FLAGS else line.group(0)
                self.assertIn(mode, where, f"`{mode}` is missing from the command's prose")

    def test_the_command_advertises_no_subcommand_the_core_leaves_undefined(self):
        known = set(MODES) | {"profile"} | {f.lstrip("-") for f in MODE_FLAGS.values()}
        undefined = {s for s in self.advertised() if s.lstrip("-") not in known}
        self.assertEqual(undefined, set(),
                         f"advertised but undefined in the core: {sorted(undefined)}")

    def test_every_flag_invoked_mode_is_advertised_by_its_flag(self):
        """A flag-invoked mode is invisible to a subcommand check, so it gets its own.

        `--from-manifest` sat in `chain`'s Refuses list long before anything defined it; the point of
        advertising it is that the refusal now refers to something real.
        """
        text = read(COMMAND)
        for mode, flag in MODE_FLAGS.items():
            with self.subTest(mode=mode):
                self.assertIsNotNone(mode_section(read(MODES_REF), mode),
                                     f"`{mode}` is advertised by {flag} but not defined")
                self.assertIn(flag, text, f"{flag} starts `{mode}` and must be advertised")

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
        self.assertEqual(result.stdout, "", "a usage error writes no activity line — it exits "
                                            "before a Watcher exists (vibe-188)")


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
                cursor="2026-01-01T00:00:00Z", max_wait=21600, fail_probe=False,
                rollup_fails=False, activity_fails=(), rollup_sequence=None, max_polls=5,
                stderr=None):
        """vibe-206 adds the degradation seams: `rollup_fails` / `activity_fails` make those probes
        raise `GhError` (per-endpoint for activity, by argv fragment), `rollup_sequence` drives a
        failure/success pattern across polls, `max_polls` lets a run reach the tenth consecutive
        degradation, and `stderr` collects the watcher's own reports."""
        module = load_watcher()
        ticks = list(clock)
        rollup_ticks = iter(rollup_sequence) if rollup_sequence is not None else None

        def now():
            return ticks.pop(0) if len(ticks) > 1 else ticks[0]

        def gh(argv):
            if "--json" in argv and "state" in argv:
                if fail_probe:
                    raise module.GhError("probe failed")
                return json.dumps(state)
            if "--json" in argv and "statusCheckRollup" in argv:
                fails = next(rollup_ticks) if rollup_ticks is not None else rollup_fails
                if fails:
                    raise module.GhError("rollup boom")
                return json.dumps(rollup if rollup is not None else self.ROLLUP_EMPTY)
            for fragment in activity_fails:
                if any(fragment in part for part in argv):
                    raise module.GhError(f"activity boom: {fragment}")
            return "\n".join(activity)

        w = module.Watcher("owner/repo", 1, cursor, poll=0, max_wait=max_wait,
                           merge_when_green=merge_when_green, gh=gh, clock=now,
                           max_polls=max_polls)
        if stderr is not None:
            w.emit_stderr = stderr.append
        return module, w


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


class TestWatcherCarriesTheAuthor(WatcherCase):
    """vibe-188 / grill H2 (part b): exit 3 says WHO — author_association and login of the activity
    that produced it, as one JSON line on stdout — so the chain can gate a babysit round on it."""

    def watcher_with_emit(self, **kw):
        module, w = self.watcher(**kw)
        lines = []
        w.emit = lines.append
        return module, w, lines

    def test_a_non_collaborator_comment_exits_3_carrying_author_association_none(self):
        module, w, lines = self.watcher_with_emit(
            state=self.OPEN, activity=["2026-06-01T00:00:00Z\tNONE\tstranger"])
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)
        self.assertEqual(w.last_activity,
                         {"at": "2026-06-01T00:00:00Z", "author_association": "NONE", "author": "stranger"})
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(json.loads(lines[0]),
                         {"exit": 3, "at": "2026-06-01T00:00:00Z", "author_association": "NONE", "author": "stranger"})

    def test_a_collaborator_comment_exits_3_carrying_its_association(self):
        module, w, lines = self.watcher_with_emit(
            state=self.OPEN, activity=["2026-06-01T00:00:00Z\tCOLLABORATOR\tmaintainer"])
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)
        self.assertEqual(w.last_activity["author_association"], "COLLABORATOR")
        self.assertEqual(json.loads(lines[0])["author"], "maintainer")

    def test_the_newest_activity_is_the_one_reported(self):
        module, w, lines = self.watcher_with_emit(
            state=self.OPEN, activity=["2026-06-01T00:00:00Z\tOWNER\tboss",
                                       "2026-06-02T00:00:00Z\tNONE\tstranger",
                                       "2026-05-30T00:00:00Z\tMEMBER\tteam"])
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)
        self.assertEqual(w.last_activity["author_association"], "NONE", "the newest stamp wins, whoever wrote it")

    def test_a_bare_stamp_is_accepted_and_reports_an_empty_association(self):
        # the pre-vibe-188 line shape (timestamps only) still produces exit 3; unknown is not a collaborator
        module, w, lines = self.watcher_with_emit(state=self.OPEN, activity=["2026-06-01T00:00:00Z"])
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)
        self.assertEqual(w.last_activity["author_association"], "")
        self.assertEqual(json.loads(lines[0])["author_association"], "")

    def test_no_activity_newer_than_the_cursor_reports_nothing(self):
        module, w, lines = self.watcher_with_emit(
            state=self.OPEN, activity=["2025-01-01T00:00:00Z\tNONE\tstranger"], clock=(0, 99999), max_wait=10)
        self.assertEqual(w.run(), module.EXIT_TIMEOUT)
        self.assertIsNone(w.last_activity)
        self.assertEqual(lines, [])

    def test_no_line_is_emitted_on_any_other_exit(self):
        # the line is tied to exit 3 alone — every other outcome, with tempting activity present,
        # emits nothing; the failing-check case matters most (exit 4 returns BEFORE the activity probe)
        newer = ["2026-06-01T00:00:00Z	NONE	stranger"]
        cases = {
            "merged": dict(state=self.MERGED, activity=newer),
            "closed": dict(state=self.CLOSED, activity=newer),
            "checks-failed": dict(state=self.OPEN, rollup=self.ROLLUP_FAIL, activity=newer),
            "green": dict(state=self.OPEN, rollup=self.ROLLUP_GREEN, activity=newer, clock=(0, 200), merge_when_green=True),
            "timeout": dict(state=self.OPEN, activity=newer, clock=(0, 99999), max_wait=10),
            "gh-errors": dict(state=self.OPEN, activity=newer, fail_probe=True),
        }
        expected = {"merged": "EXIT_MERGED", "closed": "EXIT_CLOSED", "checks-failed": "EXIT_CHECKS_FAILED",
                    "green": "EXIT_GREEN", "timeout": "EXIT_TIMEOUT", "gh-errors": "EXIT_GH_ERRORS"}
        for name, kw in cases.items():
            with self.subTest(outcome=name):
                module, w, lines = self.watcher_with_emit(**kw)
                if name == "gh-errors":
                    w.max_polls = 20
                self.assertEqual(w.run(), getattr(module, expected[name]))
                self.assertEqual(lines, [], f"{name} must emit no line")

    def test_the_activity_query_asks_for_the_association_and_login_as_tsv(self):
        module = load_watcher()
        seen = []

        def gh(argv):
            seen.append(argv)
            if "--json" in argv and "state" in argv:
                return json.dumps(self.OPEN)
            if "--json" in argv and "statusCheckRollup" in argv:
                return json.dumps(self.ROLLUP_EMPTY)
            return ""
        w = module.Watcher("owner/repo", 1, "-", poll=0, max_wait=1, gh=gh, clock=lambda: 0, max_polls=1)
        w.run()
        api_calls = [a for a in seen if a and a[0] == "api"]
        self.assertEqual(len(api_calls), 3, seen)
        for argv in api_calls:
            jq = argv[argv.index("--jq") + 1]
            self.assertIn("author_association", jq)
            self.assertIn("user.login", jq)
            self.assertIn("@tsv", jq)


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
                jq = argv[-1]
                if "@tsv" in jq:          # vibe-188: stamp, author_association, login per element
                    field = re.search(r"\[\.(\w+),", jq).group(1)
                    return self.module.reduce_activity(self.record(name)["body"], field)
                field = jq.split(".")[-1].split(" ")[0]
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
        def tsv(field):   # vibe-188: the activity query now carries the author with the stamp
            return (f'.[] | select(.{field} != null and .{field} != "") | '
                    f'[.{field}, (.author_association // ""), (.user.login // "")] | @tsv')
        self.assertEqual(apis, [
            ["api", "--paginate", "repos/owner/repo/issues/1/comments", "--jq", tsv("updated_at")],
            ["api", "--paginate", "repos/owner/repo/pulls/1/reviews", "--jq", tsv("submitted_at")],
            ["api", "--paginate", "repos/owner/repo/pulls/1/comments", "--jq", tsv("updated_at")],
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


class ManifestCase(unittest.TestCase):
    """vibe-130. The input contract, and the two checks a schema structurally cannot make."""

    SCHEMA_PATH = REPO_ROOT / "schemas" / "manifest.schema.json"
    EXAMPLE = REPO_ROOT / "skills" / "issue2pr" / "examples" / "manifests" / "example.json"

    @classmethod
    def setUpClass(cls):
        cls.entry = cls.load("manifest_entry", REPO_ROOT / "scripts" / "manifest_entry.py")
        cls.schema = json.loads(cls.SCHEMA_PATH.read_text(encoding="utf-8"))

    @staticmethod
    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def valid(self, **overrides):
        doc = json.loads(self.EXAMPLE.read_text(encoding="utf-8"))
        doc.update(overrides)
        return doc

    def rejects(self, doc):
        with self.assertRaises(self.entry.ManifestError) as caught:
            self.entry.validate_document(doc)
        self.assertEqual(caught.exception.stage, "schema")

    def accepts(self, doc):
        self.entry.validate_document(doc)


class TestManifestSchema(ManifestCase):
    def test_the_example_validates(self):
        self.accepts(self.valid())

    def test_the_examples_body_path_resolves_to_the_shipped_brief(self):
        """`body_path` is required, which is why the example is a pair. A manifest pointing at a
        file that does not exist would document the contract by violating it."""
        body = self.valid()["subtask"]["body_path"]
        self.assertTrue((REPO_ROOT / body).is_file(), f"{body} is missing")

    def test_each_required_key_rejects_independently(self):
        for key in self.schema["required"]:
            with self.subTest(missing=key):
                doc = self.valid()
                del doc[key]
                self.rejects(doc)

    def test_each_constraint_rejects_independently(self):
        cases = {
            "manifest_version const": {"manifest_version": 2},
            "unknown top-level key": {"unexpected": 1},
            "branch pattern": {"branch": "no-ai-segment"},
            "scope_override pattern": {"scope_override": "missing-number"},
            "subject_prefix pattern": {"subject_prefix": "no brackets"},
            "scenario enum": {"scenario": "refactor"},
            "round minimum": {"round": 0},
            "cap below minimum": {"max_review_iterations": 1},
            "cap above maximum": {"max_review_iterations": 6},
            "review_mode enum": {"review_mode": "partial"},
            "backend enum": {"reviewer_backend": "copilot-cli"},
            "empty repos": {"repos": []},
            "run_folder minLength": {"run_folder": ""},
        }
        for label, override in cases.items():
            with self.subTest(constraint=label):
                self.rejects(self.valid(**override))

    def test_every_constraint_in_the_schema_rejects_independently(self):
        """One isolated mutation per constraint, derived from the schema rather than listed by hand.

        A hand-written list only ever covers what its author remembered; walking the schema means a
        constraint added later is covered without editing this test.
        """
        def mutations(node, path=()):
            """(label, keys, value) for each constraint the walker can violate in isolation.

            Every applicable constraint yields a case — an earlier version used an `elif` chain, so a
            property with an `enum` never had its `type` mutated and a property with a `pattern` never
            had its `minLength` mutated. A constraint that cannot lose is a constraint nobody checked.
            """
            out = []
            for key, sub in (node.get("properties") or {}).items():
                here = path + (key,)
                label = ".".join(here)
                kind = sub.get("type")
                if sub.get("enum"):
                    out.append((f"{label} enum", here, "___not_a_member___"))
                if "const" in sub:
                    out.append((f"{label} const", here, "___not_the_const___"))
                if sub.get("pattern"):
                    out.append((f"{label} pattern", here, "!!!"))
                if sub.get("format"):
                    out.append((f"{label} format", here, "not a uri"))
                if sub.get("minLength"):
                    out.append((f"{label} minLength", here, ""))
                if "minimum" in sub:
                    out.append((f"{label} minimum", here, sub["minimum"] - 1))
                if "maximum" in sub:
                    out.append((f"{label} maximum", here, sub["maximum"] + 1))
                if kind == "string":
                    out.append((f"{label} type", here, 42))
                elif kind == "integer":
                    out.append((f"{label} type", here, "not-an-int"))
                elif kind == "array":
                    out.append((f"{label} type", here, "not-an-array"))
                    if "minItems" in sub:
                        out.append((f"{label} minItems", here, []))
                    if "maxItems" in sub:
                        out.append((f"{label} maxItems", here,
                                    [{}] * (sub["maxItems"] + 1)))
                elif kind == "object":
                    out.append((f"{label} type", here, "not-an-object"))
                    out.append((f"{label} additionalProperties", here + ("___extra___",), 1))
                    for required in sub.get("required", []):
                        out.append((f"{label}.{required} required", here + (required,), None))
                    out.extend(mutations(sub, here))
            return out

        def apply(doc, keys, value):
            node = doc
            for key in keys[:-1]:
                node = node[key]
            if value is None:
                node.pop(keys[-1], None)
            else:
                node[keys[-1]] = value
            return doc

        cases = mutations(self.schema)
        self.assertGreater(len(cases), 35, f"only {len(cases)} constraints derived; the walk is wrong")
        # Every property that declares a type must have had that type mutated, whatever else it
        # declares — at **every** depth. This is the assertion that would have caught the `elif`
        # chain, and enumerating only top-level properties would have let a nested one slip.
        def typed_properties(node, path=()):
            found = set()
            for key, sub in (node.get("properties") or {}).items():
                here = path + (key,)
                if "type" in sub:
                    found.add(".".join(here))
                found |= typed_properties(sub, here)
            return found

        typed = typed_properties(self.schema)
        self.assertGreater(len(typed), 15, "the type survey is not reaching nested properties")
        mutated_types = {label.rsplit(" ", 1)[0] for label, _, _ in cases if label.endswith(" type")}
        self.assertEqual(typed - mutated_types, set(),
                         "properties whose type is never independently mutated")

        # Per-kind coverage, because a total-count floor does not notice a missing *kind*. Deleting
        # every `enum` emission left 48 of 52 cases — enough to pass a floor of 35, the type
        # invariant and the `repos minItems` check all at once. Counting each kind against what the
        # schema actually declares is what makes the generator answerable for its description.
        def declared(node, kind):
            total = 0
            for sub in (node.get("properties") or {}).values():
                if kind in sub:
                    total += 1
                total += declared(sub, kind)
                if sub.get("type") == "array" and kind in (sub.get("items") or {}):
                    total += 1
            return total

        emitted = {}
        for label, _, _ in cases:
            emitted[label.rsplit(" ", 1)[-1]] = emitted.get(label.rsplit(" ", 1)[-1], 0) + 1
        for kind in ("enum", "const", "pattern", "format", "minLength", "minimum", "maximum",
                     "minItems", "required", "additionalProperties"):
            want = declared(self.schema, kind) if kind not in ("required", "additionalProperties") else None
            with self.subTest(kind=kind):
                if want:
                    self.assertGreaterEqual(
                        emitted.get(kind, 0), want,
                        f"schema declares {want} {kind} constraint(s); the walk emits "
                        f"{emitted.get(kind, 0)}")
                else:
                    self.assertGreater(emitted.get(kind, 0), 0, f"no {kind} case is derived")
        for label, keys, value in cases:
            with self.subTest(constraint=label):
                self.rejects(apply(self.valid(), keys, value))

    def test_the_root_object_rejects_a_non_object(self):
        for value in ("a string", 7, [], None):
            with self.subTest(instance=value):
                self.rejects(value)

    def test_repo_item_constraints_reject_independently(self):
        """Array items are not reached by the property walk above, so they get their own pass."""
        item = self.schema["properties"]["repos"]["items"]
        for field in item["properties"]:
            with self.subTest(wrong_type=f"repos[0].{field}"):
                doc = self.valid()
                doc["repos"][0][field] = 99
                self.rejects(doc)
        for required in item["required"]:
            with self.subTest(missing=f"repos[0].{required}"):
                doc = self.valid()
                del doc["repos"][0][required]
                self.rejects(doc)
        for label, repo in {
            "unknown key": {"id": "a", "path": "p", "base_branch": "b", "extra": 1},
            "id empty": {"id": "", "path": "p", "base_branch": "b"},
            "path empty": {"id": "a", "path": "", "base_branch": "b"},
            "base_branch empty": {"id": "a", "path": "p", "base_branch": ""},
            "item not an object": "a string",
        }.items():
            with self.subTest(case=label):
                self.rejects(self.valid(repos=[repo]))

    def test_booleans_are_not_numbers_for_the_bounds(self):
        """`bool` subclasses `int` in Python. A checker that forgot would accept `round: True`."""
        self.rejects(self.valid(round=True))
        self.rejects(self.valid(max_review_iterations=False))

    def test_nested_objects_reject_unknown_keys_and_bad_urls(self):
        for label, doc in {
            "parent_source extra": self.valid(parent_source={
                "type": "brief-file", "id": "x", "surprise": 1}),
            "parent_source enum": self.valid(parent_source={"type": "jira", "id": "x"}),
            "subtask missing body_path": self.valid(subtask={
                "id": "a", "slug": "b", "title": "c"}),
            "malformed url": self.valid(parent_source={
                "type": "brief-file", "id": "x", "url": "not a uri"}),
        }.items():
            with self.subTest(case=label):
                self.rejects(doc)

    def test_correction_1_an_arbitrary_repo_id_validates(self):
        """The source pinned `const: "vibe-suite"`. A project-neutral contract cannot."""
        self.accepts(self.valid(repos=[{
            "id": "anything-at-all", "path": "codes/x", "base_branch": "trunk"}]))

    def test_correction_2_an_arbitrary_base_branch_validates(self):
        self.accepts(self.valid(repos=[{
            "id": "example-repo", "path": "codes/x", "base_branch": "release/9"}]))

    def test_correction_3_a_two_element_repos_array_validates(self):
        """`boundary-inventory.md`: the core never assumes arity, so the schema must not impose it."""
        self.accepts(self.valid(repos=[
            {"id": "a", "path": "codes/a", "base_branch": "main"},
            {"id": "b", "path": "codes/b", "base_branch": "main"}]))


class TestManifestEntryPath(ManifestCase):
    PROFILE = {"repo_id": "example-repo", "base_branch": "trunk"}

    def test_a_conformant_manifest_is_accepted(self):
        self.assertEqual(
            self.entry.accept(self.valid(), self.PROFILE),
            {"max_review_rounds": 3, "review_mode": "full", "reviewer_backend": "codex"})

    def test_a_mismatched_repo_id_is_refused_here_not_by_the_schema(self):
        doc = self.valid(repos=[{"id": "other", "path": "p", "base_branch": "trunk"}])
        self.accepts(doc)                                   # the schema is content with it
        with self.assertRaises(self.entry.ManifestError) as caught:
            self.entry.check_against_profile(doc, self.PROFILE)
        self.assertEqual(caught.exception.stage, "profile")

    def test_a_mismatched_base_branch_is_refused_here_not_by_the_schema(self):
        doc = self.valid(repos=[{"id": "example-repo", "path": "p", "base_branch": "main"}])
        self.accepts(doc)
        with self.assertRaises(self.entry.ManifestError) as caught:
            self.entry.check_against_profile(doc, self.PROFILE)
        self.assertEqual(caught.exception.stage, "profile")

    def test_the_cap_property_is_mapped_to_the_cores_field(self):
        """The manifest keeps the source spelling; the core's field is what a run reads."""
        settings = self.entry.to_run_settings(self.valid(max_review_iterations=5))
        self.assertEqual(settings["max_review_rounds"], 5)
        self.assertNotIn("max_review_iterations", settings)

    def test_schema_failure_takes_precedence_over_a_profile_failure(self):
        """Order is contract. A profile complaint about a document that is not a manifest is noise."""
        doc = self.valid(round=0, repos=[{"id": "wrong", "path": "p", "base_branch": "wrong"}])
        with self.assertRaises(self.entry.ManifestError) as caught:
            self.entry.accept(doc, self.PROFILE)
        self.assertEqual(caught.exception.stage, "schema")

    def run_cli(self, document, profile_text):
        import tempfile
        directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, directory, True)
        manifest = directory / "m.json"
        manifest.write_text(json.dumps(document), encoding="utf-8")
        profile = directory / "p.md"
        profile.write_text(profile_text, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "manifest_entry.py"), str(manifest),
             "--profile", str(profile)], capture_output=True, text=True, timeout=60)

    GOOD_PROFILE = "repo_id: example-repo\nbase_branch: trunk\n"

    def test_the_cli_accepts_a_conformant_manifest_and_prints_run_settings(self):
        result = self.run_cli(self.valid(), self.GOOD_PROFILE)
        self.assertEqual(result.returncode, self.entry.EXIT_OK, result.stderr)
        self.assertEqual(json.loads(result.stdout)["max_review_rounds"], 3)

    def test_the_cli_reports_a_schema_failure_with_its_own_code(self):
        result = self.run_cli(self.valid(round=0), self.GOOD_PROFILE)
        self.assertEqual(result.returncode, self.entry.EXIT_SCHEMA, result.stderr)
        self.assertIn("schema", result.stderr)

    def test_the_cli_reports_a_profile_failure_with_its_own_code(self):
        result = self.run_cli(
            self.valid(repos=[{"id": "other", "path": "p", "base_branch": "trunk"}]),
            self.GOOD_PROFILE)
        self.assertEqual(result.returncode, self.entry.EXIT_PROFILE, result.stderr)

    def test_the_cli_reports_the_schema_failure_when_the_profile_is_also_unusable(self):
        """The regression that motivates the explicit sequencing in `main`.

        `accept(document, read_profile(path))` reads the profile first — Python evaluates arguments
        before the call — so an invalid manifest paired with an unreadable profile reported the
        *profile* failure for a document that was never a manifest.
        """
        result = self.run_cli(self.valid(round=0), "this profile declares nothing\n")
        self.assertEqual(result.returncode, self.entry.EXIT_SCHEMA, result.stderr)
        self.assertNotIn("declares no", result.stderr)


class TestUriConformance(unittest.TestCase):
    """`format: uri`, evidenced against a **sourced** corpus.

    Four rounds fixed whichever cases a reviewer had just found, and a fifth round found more each
    time — including one nobody had thought to try (a trailing newline, which `$` accepts). Coverage
    drawn from "cases found so far" has no stopping condition by construction.

    Every case below carries its provenance. The RFC examples make the valid set answerable to a
    named authority rather than to this project's history; the historical cases are regression guards,
    because a rewrite's real risk is the cases the old version got right.

    **What this establishes**: conformance to the productions transcribed in
    `scripts/validate_audit_output.py`, evidenced against this corpus. Not a proof of RFC 3986
    conformance — a mistranscription stays latent until a reader compares the productions or a case
    reaches it. That limit is real and stated rather than implied.
    """

    #: (uri, valid, source)
    CORPUS = (
        # RFC 3986 §1.1.2, verbatim — the specification's own worked examples.
        ("ftp://ftp.is.co.za/rfc/rfc1808.txt", True, "RFC 3986 §1.1.2"),
        ("http://www.ietf.org/rfc/rfc2396.txt", True, "RFC 3986 §1.1.2"),
        ("ldap://[2001:db8::7]/c=GB?objectClass?one", True, "RFC 3986 §1.1.2"),
        ("mailto:John.Doe@example.com", True, "RFC 3986 §1.1.2"),
        ("news:comp.infosystems.www.servers.unix", True, "RFC 3986 §1.1.2"),
        ("tel:+1-816-555-1212", True, "RFC 3986 §1.1.2"),
        ("telnet://192.0.2.16:80/", True, "RFC 3986 §1.1.2"),
        ("urn:oasis:names:specification:docbook:dtd:xml:4.1.2", True, "RFC 3986 §1.1.2"),
        # Wrongly rejected before the ABNF transcription.
        ("http://[V1.a]/", True, "round 4 — IPvFuture prefix is case-insensitive"),
        ("http://[::1]:/", True, "round 4 — port = *DIGIT admits empty"),
        ("http://[::1]:80/", True, "round 3 — bracketed host with port"),
        ("http://[0:0:0:0:0:ffff:192.0.2.128]/", True, "round 3 — IPv4-mapped"),
        ("http://example.com?x", True, "round 2 — query with no path"),
        ("http://user:pass@example.com/", True, "round 2 — userinfo permits ':'"),
        ("http://[v1.a]/", True, "round 1 — IPvFuture"),
        # Wrongly accepted before it.
        ("http://x/\n", False, "round 5 — `$` matches before a terminal newline"),
        ("http://x/a\nb", False, "round 5 — embedded control character"),
        ("http://[::1:2:3:4:5:6:7:8]/", False, "round 3 — nine groups"),
        ("http://[::ffff:999.999.999.999]/", False, "round 3 — octets out of range"),
        ("http://[1:2:3]/", False, "round 2 — three groups without '::'"),
        ("http://[:]/", False, "round 2 — not an address"),
        ("https://[broken", False, "round 1 — unclosed bracket"),
        ("https://example.com/%zz", False, "round 1 — invalid percent-encoding"),
        ("https://example.com/#one#two", False, "round 1 — two fragments"),
        ("https://[::::]/", False, "round 1 — malformed IPv6"),
        ("not a uri", False, "round 1 — no scheme"),
        ("http://[fe80::1%eth0]/", False, "round 6 — RFC 3986 Appendix A has no zone-identifier"),
        ("http://[fe80::1%25eth0]/", False, "round 6 — RFC 6874 scoped form, not Appendix A"),
    )

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "validate_audit_output", REPO_ROOT / "scripts" / "validate_audit_output.py")
        cls.v = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.v)

    def test_the_corpus_classifies_correctly(self):
        for uri, valid, source in self.CORPUS:
            with self.subTest(uri=uri, source=source):
                self.assertEqual(self.v._is_uri(uri), valid, f"{uri!r} — {source}")

    def test_every_rfc_example_is_present(self):
        """The valid set answers to the specification, not to this project's findings."""
        rfc = [c for c in self.CORPUS if c[2].startswith("RFC 3986")]
        self.assertEqual(len(rfc), 8, "RFC 3986 §1.1.2 lists eight examples")
        self.assertTrue(all(valid for _, valid, _ in rfc))

    def test_every_case_carries_a_source(self):
        """A case with no provenance is one nobody can check."""
        for uri, _, source in self.CORPUS:
            with self.subTest(uri=uri):
                self.assertTrue(source.strip(), "every corpus entry states where it came from")

    def test_no_production_is_anchored_with_a_dollar(self):
        """The defect class, closed at its source.

        `re.match(r"...$", "x\n")` succeeds, so any production anchored with `$` re-admits a trailing
        newline. Asserting the *technique* means the class cannot return one production at a time.
        """
        source = (REPO_ROOT / "scripts" / "validate_audit_output.py").read_text(encoding="utf-8")

        # Every compiled production, and every method it is consumed through — read from the AST,
        # not from substrings. A previous version asserted `"fullmatch" in text` (satisfied by a
        # comment) and the absence of two literal strings (leaving `.search(` free to pass while
        # accepting `http://x:80evil/`).
        tree = ast.parse(source)
        productions = {
            node.targets[0].id
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "attr", None) == "compile"
        }
        self.assertGreaterEqual(len(productions), 6, f"expected the grammar's productions, got {productions}")

        used = {}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id in productions):
                used.setdefault(node.func.value.id, set()).add(node.func.attr)
        self.assertTrue(used, "no production is called anywhere")
        for name, methods in sorted(used.items()):
            with self.subTest(production=name):
                self.assertEqual(methods, {"fullmatch"},
                                 f"{name} is consumed through {sorted(methods)}; a production must "
                                 "consume its whole input, so only fullmatch is permitted")

        # And no compiled pattern may carry a terminal anchor, which would re-admit a trailing
        # newline even under fullmatch's sibling methods.
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id in productions):
                literals = [n.value for n in ast.walk(node.value)
                            if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                for literal in literals:
                    with self.subTest(production=node.targets[0].id, literal=literal):
                        self.assertFalse(literal.endswith("$"),
                                         "a production ends with a `$` anchor")


class TestWatcherGhTimeout(unittest.TestCase):
    """vibe-206 (M2): every `gh` call is bounded.

    `_run_gh` is the watcher's only shell-out, and it ran `subprocess.run` with no `timeout=`, so a
    network black hole or an interactive auth prompt blocked inside the call. `max_wait` is evaluated
    between polls, so the deadline that exists to bound the watcher was unreachable from exactly the
    state that needed it.

    These drive `_run_gh` directly with an injected runner, because `Watcher(..., gh=...)` REPLACES
    the shell-out: an injection at that seam never reaches the timeout inside `_run_gh` and a hanging
    one would simply hang the test.
    """

    def test_every_gh_call_carries_the_timeout(self):
        module = load_watcher()
        seen = {}

        def runner(argv, **kwargs):
            seen.update(kwargs)
            seen["argv"] = argv
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

        self.assertEqual(module._run_gh(["pr", "view", "1"], runner=runner), "ok")
        self.assertEqual(seen["timeout"], module.GH_TIMEOUT_SECONDS,
                         "the bound is passed to the runner, not left to the default")
        self.assertEqual(module.GH_TIMEOUT_SECONDS, 60,
                         "the issue specifies 60s; a drift in the value is a change of policy")
        self.assertEqual(seen["argv"][0], "gh")

    def test_a_hung_gh_call_raises_gherror_rather_than_hanging(self):
        module = load_watcher()

        def runner(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        with self.assertRaises(module.GhError):
            module._run_gh(["api", "--paginate", "x"], runner=runner)

    def test_a_timeout_says_so_and_does_not_read_like_a_rejection(self):
        """The issue maps a hung call to `GhError` so it joins the same accounting as a failing one.
        An operator still has to be able to tell the two apart, and the message is where."""
        module = load_watcher()

        def hangs(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

        def rejects(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="HTTP 403: Forbidden")

        with self.assertRaises(module.GhError) as hung:
            module._run_gh(["api", "x"], runner=hangs)
        with self.assertRaises(module.GhError) as refused:
            module._run_gh(["api", "x"], runner=rejects)

        self.assertIn("timed out", str(hung.exception).lower())
        self.assertIn(str(module.GH_TIMEOUT_SECONDS), str(hung.exception))
        self.assertNotIn("timed out", str(refused.exception).lower())
        self.assertIn("403", str(refused.exception))


class TestWatcherDegradationCounters(WatcherCase):
    """vibe-206 (M2): a blind watcher says so.

    `_rollup` returned `[]` on a `GhError` and `_latest_activity` skipped a failing endpoint, both
    silently, so a permanently failing `gh api` left the watcher unable to see a failing check or a
    comment while looking exactly like a quiet PR — polling to `max_wait` and exiting 5, an
    unobserved-state timeout the chain treats as a heartbeat.

    Exit codes are deliberately NOT changed: the state probe already counts toward exit 6, and
    routing rollup/activity degradation there too would be a separate contract change to the
    docstring, `operational-modes.md` and its golden.
    """

    def lines(self, **kwargs):
        out = []
        module, w = self.watcher(state=self.OPEN, stderr=out, **kwargs)
        w.run()
        return module, out

    # -- RED on the base: nothing reported degradation at all ------------------------------------

    def test_ten_consecutive_rollup_degradations_report_once_on_stderr(self):
        _, out = self.lines(rollup_fails=True, max_polls=10)
        self.assertEqual(len(out), 1, f"one line at the tenth, got {out}")
        self.assertIn("rollup", out[0])
        self.assertIn("10", out[0])
        self.assertIn("rollup boom", out[0], "the last error is named")

    def test_ten_consecutive_activity_degradations_report_once_on_stderr(self):
        _, out = self.lines(activity_fails=("comments", "reviews"), max_polls=10)
        self.assertEqual(len(out), 1, f"one line at the tenth, got {out}")
        self.assertIn("activity", out[0])
        self.assertIn("10", out[0])

    def test_reports_arrive_at_10_and_20_and_not_between(self):
        for polls, expected in ((10, 1), (19, 1), (20, 2)):
            with self.subTest(polls=polls):
                _, out = self.lines(rollup_fails=True, max_polls=polls)
                self.assertEqual(len(out), expected,
                                 f"{polls} degradations should report {expected} time(s), got {out}")

    def test_a_partial_activity_failure_counts_once_and_keeps_what_succeeded(self):
        """One dead endpoint out of three is exactly the case that must not go uncounted: the other
        two keep answering, so the probe still returns a result while blind to a source."""
        _, out = self.lines(activity_fails=("issues/1/comments",),
                            activity=("2020-01-01T00:00:00Z",), max_polls=10)
        self.assertEqual(len(out), 1, f"one dead endpoint out of three is counted, got {out}")
        self.assertIn("activity", out[0])

    def test_a_surviving_endpoint_still_ends_the_run(self):
        """The survivors' records are USED, not merely fetched: a newer stamp from an endpoint that
        answered still produces EXIT_ACTIVITY and populates last_activity."""
        stamp = "2027-01-01T00:00:00Z"
        module, w = self.watcher(state=self.OPEN, activity_fails=("issues/1/comments",),
                                 activity=(stamp,), max_polls=10)
        self.assertEqual(w.run(), module.EXIT_ACTIVITY)
        self.assertEqual(w.last_activity["at"], stamp)

    def test_a_clean_activity_poll_resets_the_run(self):
        """The discriminating shape: 9 failures, one wholly clean poll, 9 more failures.

        WITH the reset the count restarts, so nine post-clean failures never reach ten and nothing is
        reported. WITHOUT it the count would carry 9 across the clean poll and the very first
        post-clean failure would be the tenth — so a report here is exactly the signature of a
        missing reset. Asserting on the report's TEXT could not tell those apart; asserting on its
        absence can.
        """
        module = load_watcher()
        calls = {"n": 0}

        def gh(argv):
            if "--json" in argv and "state" in argv:
                return json.dumps(self.OPEN)
            if "--json" in argv and "statusCheckRollup" in argv:
                return json.dumps(self.ROLLUP_EMPTY)
            calls["n"] += 1
            poll = (calls["n"] - 1) // 3 + 1     # three endpoints per poll
            if poll == 10:
                return ""                        # the clean poll: every endpoint answers
            raise module.GhError("boom")

        out = []
        w = module.Watcher("owner/repo", 1, "2026-01-01T00:00:00Z", poll=0, max_wait=10**9,
                           gh=gh, clock=lambda: 0, max_polls=19)
        w.emit_stderr = out.append
        w.run()
        self.assertEqual(out, [],
                         "nine, a clean poll, then nine more must never reach ten in a row")

    def test_the_report_names_the_last_failing_endpoint(self):
        """`_latest_activity` walks comments, reviews, then pull-comments, keeping the most recent
        error. With two different endpoints failing differently, the report must carry the LATER
        one — which a same-error fixture could not distinguish."""
        module = load_watcher()

        def gh(argv):
            if "--json" in argv and "state" in argv:
                return json.dumps(self.OPEN)
            if "--json" in argv and "statusCheckRollup" in argv:
                return json.dumps(self.ROLLUP_EMPTY)
            if any("issues/1/comments" in part for part in argv):
                raise module.GhError("first-endpoint-error")
            if any("pulls/1/reviews" in part for part in argv):
                raise module.GhError("second-endpoint-error")
            return ""

        out = []
        w = module.Watcher("owner/repo", 1, "2026-01-01T00:00:00Z", poll=0, max_wait=10**9,
                           gh=gh, clock=lambda: 0, max_polls=10)
        w.emit_stderr = out.append
        w.run()
        self.assertEqual(len(out), 1, f"one line at the tenth, got {out}")
        self.assertIn("second-endpoint-error", out[0],
                      "the retained error is the last one the probe met, not the first")
        self.assertNotIn("first-endpoint-error", out[0])

    # -- characterization: these hold on the base too, and guard against a spurious report ---------

    def test_nine_consecutive_degradations_say_nothing(self):
        _, out = self.lines(rollup_fails=True, max_polls=9)
        self.assertEqual(out, [])

    def test_repeated_legitimate_empty_rollups_say_nothing(self):
        """A PR whose checks have not registered yet returns an empty rollup successfully. Only the
        GhError fallback is degradation — counting `[]` would report a failure that never happened."""
        _, out = self.lines(rollup=None, max_polls=25)
        self.assertEqual(out, [])

    def test_a_legitimate_empty_rollup_resets_the_degradation_run(self):
        _, out = self.lines(rollup_sequence=[True] * 9 + [False] * 9 + [True] * 9, max_polls=27)
        self.assertEqual(out, [], "9 + 9 successes + 9 never reaches ten in a row")

    def test_degradation_never_changes_an_exit_code(self):
        """The frozen decision: counting and reporting only. Rollup/activity degradation does not
        newly reach EXIT_GH_ERRORS, which stays ten consecutive STATE-probe failures."""
        module, w = self.watcher(state=self.OPEN, rollup_fails=True,
                                 activity_fails=("comments", "reviews", "pulls"),
                                 max_polls=25, stderr=[])
        self.assertEqual(w.run(), module.EXIT_TIMEOUT,
                         "a blind watcher still ends at the unobserved-state timeout, not exit 6")

    def test_the_report_actually_reaches_stderr(self):
        """The other tests replace `emit_stderr` to capture it; this one leaves production alone and
        proves the default emitter writes to stderr."""
        module, w = self.watcher(state=self.OPEN, rollup_fails=True, max_polls=10)
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            w.run()
        self.assertIn("rollup probe degraded 10 times", buffer.getvalue())


# --- vibe-209 -------------------------------------------------------------------------------------
import ast as _v209_ast                                                              # noqa: E402
import pathlib as _v209_pathlib                                                      # noqa: E402
import sys as _v209_sys                                                              # noqa: E402

_V209_ROOT = _v209_pathlib.Path(__file__).resolve().parent.parent
_V209_SCRIPTS = _V209_ROOT / "scripts"
if str(_V209_SCRIPTS) not in _v209_sys.path:
    _v209_sys.path.insert(0, str(_V209_SCRIPTS))


def _v209_unbounded_runs(source_path):
    """Every `subprocess.run(...)` call in a file that does NOT pass `timeout=`.

    Structural, by AST, which is this repo's own idiom for "the call site must look like this"
    (`tests/test_write_discipline.py`). Forcing a real spawn would need a whole command invocation
    and a 60-second wait; reading the call is exact, instant, and cannot pass by luck.
    """
    tree = _v209_ast.parse(_v209_pathlib.Path(source_path).read_text(encoding="utf-8"))
    calls = [n for n in _v209_ast.walk(tree)
             if isinstance(n, _v209_ast.Call) and isinstance(n.func, _v209_ast.Attribute)
             and n.func.attr == "run" and isinstance(n.func.value, _v209_ast.Name)
             and n.func.value.id == "subprocess"]
    return calls, [c for c in calls if "timeout" not in [kw.arg for kw in c.keywords]]


class ManifestValidatorTimeoutTest(unittest.TestCase):
    """R17 — the manifest-validator spawn is bounded at exactly 60 s (vibe-209 / grill P4)."""

    def test_the_constant_is_the_value_the_issue_names(self):
        import issue2pr_mode_driver
        self.assertEqual(issue2pr_mode_driver.MANIFEST_VALIDATE_TIMEOUT_S, 60)

    def test_every_subprocess_run_in_the_driver_is_bounded(self):
        calls, unbounded = _v209_unbounded_runs(_V209_SCRIPTS / "issue2pr_mode_driver.py")
        self.assertTrue(calls, "the validator spawn must still be a subprocess.run call")
        self.assertEqual([c.lineno for c in unbounded], [], "unbounded subprocess.run")


class ManifestValidatorTimeoutValueTest(unittest.TestCase):
    """The value and the handler at the validator site (Step-8 finding 2)."""

    def test_the_timeout_is_the_owning_constant(self):
        tree = _v209_ast.parse(
            (_V209_SCRIPTS / "issue2pr_mode_driver.py").read_text(encoding="utf-8"))
        found = None
        for n in _v209_ast.walk(tree):
            if (isinstance(n, _v209_ast.Call) and isinstance(n.func, _v209_ast.Attribute)
                    and n.func.attr == "run" and isinstance(n.func.value, _v209_ast.Name)
                    and n.func.value.id == "subprocess"):
                for kw in n.keywords:
                    if kw.arg == "timeout":
                        found = kw.value
        self.assertIsInstance(found, _v209_ast.Name, "the bound must be the named constant")
        self.assertEqual(found.id, "MANIFEST_VALIDATE_TIMEOUT_S")

    def test_a_timeout_becomes_a_refusal_not_a_traceback(self):
        source = (_V209_SCRIPTS / "issue2pr_mode_driver.py").read_text(encoding="utf-8")
        self.assertIn("except subprocess.TimeoutExpired:", source)
        self.assertIn("did not finish within", source,
                      "the refusal must name the bound it hit")
