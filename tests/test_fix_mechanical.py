#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The mechanical auto-fix table, and the ordering AC-4 asserts (E4.4 / vibe-38).

F3.8 requires nlpm's five transformations to run **before** any model-driven fix, and the acceptance
makes that ordering a tested property rather than a stated intention.

**What this module executes, precisely.** It runs `scripts/mechanical_fix.py` over a copy of
`tests/fixtures/fix/fixable-skill/` and compares the results. It does **not** claim to exercise
`commands/fix.md`, which is markdown with no callable seam — the command's binding to this script is a
static assertion in `tests/test_fix.py`. Saying "the test runs the table" when the test *is* the table
was the plan-review finding that produced the script in the first place.

**The ordering claim has two halves and they are proved differently.** The static half is that the
command says the table runs first and names the script. The executable half is that the script alone
already raises the fixture's score — so the mechanical stage is independently effective, and a model
stage is not doing its work. A seeded failure covers the converse: a tree whose only defect is
non-mechanical must show no movement.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "mechanical_fix.py"
SCORE_ENGINE = REPO_ROOT / "scripts" / "score_engine.py"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "fix" / "fixable-skill"


def run_table(root, dry_run=False):
    args = [sys.executable, str(SCRIPT), str(root), "--json"]
    if dry_run:
        args.append("--dry-run")
    proc = subprocess.run(args, capture_output=True, text=True, cwd=REPO_ROOT)
    return proc, (json.loads(proc.stdout) if proc.stdout.strip() else None)


def score(root, records):
    """The fixture's score, computed rather than asserted by hand.

    E3.3's oracle was hand-derived because it was proving the engine; here the engine is trusted and
    the property under test is *movement*, so a hand-written number would be a second oracle to keep.
    """
    stream = "".join("%s\x1f%s\x00" % (kind, rel) for kind, rel in records)
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "tests") as tmp:
        proc = subprocess.run(
            [sys.executable, str(SCORE_ENGINE), "--root", str(root),
             "--history", str(Path(tmp) / "h.json"), "--scope", "vibe-38"],
            input=stream, capture_output=True, text=True, cwd=REPO_ROOT)
    if proc.returncode != 0:
        raise AssertionError("score_engine failed: %s" % (proc.stderr or proc.stdout))
    return json.loads(proc.stdout)


class MechanicalTestCase(unittest.TestCase):
    def setUp(self):
        if not SCRIPT.is_file():
            self.skipTest("scripts/mechanical_fix.py does not exist yet")
        self.assertTrue((FIXTURE / "expected-fixes.json").is_file(),
                        "the fixable fixture is a required acceptance artifact")
        self.spec = json.loads((FIXTURE / "expected-fixes.json").read_text(encoding="utf-8"))
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp) / "fixable-skill"
        shutil.copytree(FIXTURE, self.root)
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _text(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")


class TestScriptShips(unittest.TestCase):
    """Non-skippable: deleting the shipped engine must not turn this module green."""

    def test_the_engine_and_fixture_exist(self):
        self.assertTrue(SCRIPT.is_file(), "scripts/mechanical_fix.py is a shipped deliverable")
        self.assertTrue((FIXTURE / "expected-fixes.json").is_file())

    def test_the_engine_carries_the_isc_header(self):
        head = SCRIPT.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in line for line in head))


class TestEachTransformation(MechanicalTestCase):
    def test_rename_tools_to_allowed_tools(self):
        run_table(self.root)
        text = self._text("commands/build.md")
        self.assertIn("allowed-tools: Read, Glob, Bash", text)
        self.assertNotRegex(text, r"(?m)^tools:")

    def test_shared_partial_gains_user_invocable_false(self):
        run_table(self.root)
        self.assertIn("user-invocable: false", self._text("commands/shared/paths.md"))

    def test_missing_name_is_derived_from_the_directory(self):
        run_table(self.root)
        self.assertIn("name: needsname", self._text("skills/needsname/SKILL.md"))

    def test_missing_heading_is_inserted(self):
        run_table(self.root)
        self.assertRegex(self._text("skills/needsname/SKILL.md"), r"(?m)^# needsname$")

    def test_argument_hint_is_added_when_the_body_reads_arguments(self):
        run_table(self.root)
        self.assertIn("argument-hint:", self._text("commands/build.md"))

    def test_a_command_that_takes_no_arguments_gains_no_hint(self):
        """Rule 5's predicate has two clauses; a command reading no arguments is untouched."""
        (self.root / "commands/noargs.md").write_text(
            "---\ndescription: Report the plugin version and exit.\n---\n\n# noargs\n\nPrint it.\n",
            encoding="utf-8")
        run_table(self.root)
        self.assertNotIn("argument-hint", self._text("commands/noargs.md"))

    def test_commands_never_gain_a_name_key(self):
        """No shipped command carries `name`; adding one would introduce a key the corpus does not
        use, which is a rewrite rather than a fix."""
        run_table(self.root)
        for rel in ("commands/build.md", "commands/report.md", "commands/shared/paths.md"):
            with self.subTest(file=rel):
                self.assertNotRegex(self._text(rel), r"(?m)^name:")


class TestClassificationIsRelativeToTheRoot(MechanicalTestCase):
    """The defect this guards recurred once already: classification read the ABSOLUTE path, so a
    target whose own ancestor was named `shared` or `agents` misclassified every artifact under it.
    Where the target lives must not change what its artifacts are."""

    def _root_under(self, ancestor):
        base = Path(self.tmp) / ancestor / "project"
        shutil.copytree(FIXTURE, base)
        return base

    def test_an_ancestor_named_shared_does_not_flag_every_artifact(self):
        root = self._root_under("shared")
        run_table(root)
        for rel in ("commands/build.md", "commands/report.md"):
            with self.subTest(file=rel):
                self.assertNotIn("user-invocable", (root / rel).read_text(encoding="utf-8"),
                                 "only commands/shared/ partials may gain the flag")
        self.assertIn("user-invocable: false",
                      (root / "commands/shared/paths.md").read_text(encoding="utf-8"),
                      "the genuine shared partial must still be flagged")

    def test_an_ancestor_named_agents_does_not_give_commands_a_name(self):
        root = self._root_under("agents")
        run_table(root)
        for rel in ("commands/build.md", "commands/report.md", "commands/shared/paths.md"):
            with self.subTest(file=rel):
                self.assertNotRegex((root / rel).read_text(encoding="utf-8"), r"(?m)^name:")

    def test_a_real_agent_inside_the_target_does_gain_a_name(self):
        """The positive half: relative classification must still recognise a genuine agent."""
        (self.root / "agents").mkdir(exist_ok=True)
        (self.root / "agents/helper.md").write_text(
            "---\ndescription: Use when a helper is needed for the build step.\nmodel: haiku\n"
            "tools: Read\n---\n\n# helper\n\nHelp.\n", encoding="utf-8")
        run_table(self.root)
        self.assertIn("name: helper", (self.root / "agents/helper.md").read_text(encoding="utf-8"))


class TestConflictsAndIdempotence(MechanicalTestCase):
    def test_both_key_forms_present_is_a_reported_no_op(self):
        """Dropping either would lose a value the author wrote, so neither is touched."""
        (self.root / "commands/both.md").write_text(
            "---\ndescription: Do the thing.\ntools: Read\nallowed-tools: Glob\n---\n\n# both\n\nx\n",
            encoding="utf-8")
        before = self._text("commands/both.md")
        _, out = run_table(self.root)
        self.assertEqual(self._text("commands/both.md"), before, "a conflict must not mutate")
        notes = [c["note"] for f in out["files"] if f["file"] == "commands/both.md"
                 for c in f["changes"]]
        self.assertTrue(any("conflict" in n for n in notes), "a conflict must be reported")

    def test_the_table_is_idempotent(self):
        """Asserted for the table as a whole, so a future rule that breaks it fails without anyone
        remembering to add a case."""
        run_table(self.root)
        after_first = {p: p.read_text(encoding="utf-8")
                       for p in sorted(self.root.rglob("*.md")) if p.is_file()}
        _, out = run_table(self.root)
        after_second = {p: p.read_text(encoding="utf-8")
                        for p in sorted(self.root.rglob("*.md")) if p.is_file()}
        self.assertEqual(after_first, after_second, "a second run must change nothing")
        self.assertEqual(out["files"], [], "a second run must report no changes")

    def test_a_file_without_frontmatter_is_untouched(self):
        (self.root / "commands/plain.md").write_text("# plain\n\nno frontmatter\n", encoding="utf-8")
        before = self._text("commands/plain.md")
        run_table(self.root)
        self.assertEqual(self._text("commands/plain.md"), before)

    def test_a_missing_root_is_an_error_not_a_silent_pass(self):
        proc, _ = run_table(Path(self.tmp) / "no-such-tree")
        self.assertEqual(proc.returncode, 2)


class TestNonMechanicalDefectIsUntouched(MechanicalTestCase):
    def test_the_vague_description_survives_the_table(self):
        """FX-6 exists to prove the table stops where it should rather than rewriting what it meets."""
        before = self._text("commands/report.md")
        run_table(self.root)
        self.assertEqual(self._text("commands/report.md"), before)

    def test_the_fixture_declares_exactly_one_non_mechanical_defect(self):
        non_mech = [d for d in self.spec["defects"] if not d["mechanical"]]
        self.assertEqual(len(non_mech), 1)

    def test_every_declared_mechanical_defect_names_a_rule_the_engine_has(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mf", SCRIPT)
        mf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mf)
        engine_rules = {name for name, _ in mf.RULES}
        for defect in self.spec["defects"]:
            if defect["mechanical"]:
                with self.subTest(defect=defect["id"]):
                    self.assertIn(defect["rule"], engine_rules)


class TestOrderingIsEffective(MechanicalTestCase):
    """The executable half of AC-4's ordering claim."""

    RECORDS = (("command", "commands/build.md"),
               ("command", "commands/report.md"),
               ("skill", "skills/needsname/SKILL.md"))

    def test_the_table_alone_raises_the_score(self):
        before = score(self.root, self.RECORDS)
        run_table(self.root)
        after = score(self.root, self.RECORDS)
        before_total = sum(f["score"] for f in before["files"])
        after_total = sum(f["score"] for f in after["files"])
        self.assertGreater(after_total, before_total,
                           "the mechanical stage must be independently effective; if it is not, a "
                           "model stage is doing its work and 'applied first' means nothing")

    def test_a_tree_whose_only_defect_is_non_mechanical_does_not_move(self):
        """The seeded failure for the ordering claim: movement must come from the table, not from
        anything the harness happens to do."""
        only = Path(self.tmp) / "non-mechanical-only"
        (only / "commands").mkdir(parents=True)
        shutil.copy(FIXTURE / "commands/report.md", only / "commands/report.md")
        records = (("command", "commands/report.md"),)
        before = score(only, records)
        run_table(only)
        after = score(only, records)
        self.assertEqual([f["score"] for f in after["files"]],
                         [f["score"] for f in before["files"]])


if __name__ == "__main__":
    unittest.main()
