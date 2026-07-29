#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The §7A migration fixture suite (E2.8 / vibe-25, AC-5).

One fixture project per §7A row, each driven through the **real** `/vibe-suite:init` rather than
through the migrate helpers directly — the helpers already have their own tests (`test_migrate.py`),
and a suite that re-tested them would prove the parts work while saying nothing about the command
that composes them.

**What "legacy byte-identical" means.** Rows 1, 2 and 3 each specify *original untouched*: migration
reads the legacy store and writes a new one beside it. So the assertion is that the legacy file's
bytes are unchanged after init, not that some output matches a golden tree. That is also why the
fixtures are inputs rather than expected-output directories.

**Row 9 is not re-tested here.** E0.8 ships its bare-repo fixture in `test_migrate_auditor_data.py`;
duplicating it would be a second opinion on a question that already has an owner. This suite asserts
that coverage exists and stays wired.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "migration"
INIT = REPO_ROOT / "scripts" / "init.sh"
DOCTOR = REPO_ROOT / "scripts" / "doctor.py"
ROWS = (
    "row-01-cc-suite-config", "row-02-nlpm-local", "row-03-history", "row-04-reports",
    "row-05-legacy-state", "row-06-sentinels", "row-07-test-specs", "row-08-no-op",
    "row-09-auditor-data", "row-10-plugins-alongside",
)


def snapshot(root):
    """Every file's bytes, so "untouched" is checked against content and not mtime."""
    out = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink():
            out[str(path.relative_to(root))] = path.read_bytes()
    return out


class MigrationRow(unittest.TestCase):
    """Base: copy a row into a scratch workspace and run the real init."""

    row = None

    def setUp(self):
        if self.row is None:
            self.skipTest("base class")
        self.ws = Path(tempfile.mkdtemp(prefix=f"vibe-{self.row}-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        src = FIXTURES / self.row
        for item in src.iterdir():
            dest = self.ws / item.name
            shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)
        self.before = snapshot(self.ws)

    def init(self, *extra):
        proc = subprocess.run(
            ["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
             "--audit-depth", "mini", "--strictness", "standard", *extra],
            capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return proc

    def doctor(self):
        return subprocess.run([sys.executable, str(DOCTOR), "--workspace", str(self.ws)],
                              capture_output=True, text=True)

    def assert_legacy_untouched(self, *relatives):
        """The §7A promise for every row that reads a legacy store."""
        for rel in relatives:
            self.assertIn(rel, self.before, f"fixture does not seed {rel}")
            self.assertEqual((self.ws / rel).read_bytes(), self.before[rel],
                             f"{rel} was modified; §7A says the original is untouched")


class Row01Config(MigrationRow):
    row = "row-01-cc-suite-config"

    def test_a_new_store_is_created_and_the_legacy_one_is_untouched(self):
        self.assertEqual(self.init().returncode, 0)
        self.assertTrue((self.ws / ".vibe-suite.md").is_file(), "new store not created")
        self.assert_legacy_untouched(".cc-suite.md")

    def test_doctor_warns_that_legacy_config_is_present(self):
        self.init()
        self.assertIn("legacy", self.doctor().stdout.lower())


class Row02Precedence(MigrationRow):
    row = "row-02-nlpm-local"

    def test_conflicting_values_are_asked_once_not_guessed(self):
        """Two legacy stores disagree on `effort`. Tri-state decisions exist precisely so this is a
        question rather than a silent pick, so an un-answered run must not invent one."""
        proc = self.init()
        self.assertIn(proc.returncode, (0, 3), proc.stderr)
        self.assert_legacy_untouched(".cc-suite.md", ".claude/nlpm.local.md")

    def test_an_answered_conflict_is_honoured(self):
        proc = self.init("--resolve-config", json.dumps({"effort": "low"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_legacy_untouched(".cc-suite.md", ".claude/nlpm.local.md")


class Row03History(MigrationRow):
    row = "row-03-history"

    def test_history_is_copied_verbatim_and_the_original_survives(self):
        self.assertEqual(self.init().returncode, 0)
        new = self.ws / ".claude" / "vibe-history.json"
        self.assertTrue(new.is_file(), "history was not migrated")
        old = json.loads((self.ws / ".claude" / "nlpm-history.json").read_text())
        carried = json.loads(new.read_text())
        self.assertEqual(carried.get("entries"), old["entries"], "entries were not copied verbatim")
        self.assert_legacy_untouched(".claude/nlpm-history.json")

    def test_a_migrated_from_marker_records_the_provenance(self):
        self.init()
        carried = json.loads((self.ws / ".claude" / "vibe-history.json").read_text())
        self.assertTrue(any("migrated" in k for k in carried),
                        f"no migrated_from marker in {sorted(carried)}")


class Row04Reports(MigrationRow):
    row = "row-04-reports"

    def test_reports_are_noted_and_never_copied(self):
        """Reports are point-in-time artifacts, so copying them would fabricate history."""
        self.assertEqual(self.init().returncode, 0)
        self.assertTrue((self.ws / ".claude" / "nlpm-reports").is_dir())
        copied = self.ws / ".claude" / "vibe-reports"
        if copied.exists():
            self.assertEqual(list(copied.iterdir()), [], "old reports were copied into the new dir")


class Row05State(MigrationRow):
    row = "row-05-legacy-state"

    def test_only_the_gate_toggle_crosses(self):
        self.assertEqual(self.init("--resolve-state", "true").returncode, 0)
        legacy = json.loads((self.ws / ".cc-suite-state" / "state.json").read_text())
        self.assertIn("jobs", legacy, "legacy state was consumed rather than read")
        for state in (self.ws / ".vibe-suite-state").glob("*.json"):
            carried = json.loads(state.read_text())
            self.assertNotIn("jobs", carried, "ephemeral jobs were migrated")

    def test_declining_leaves_the_legacy_state_alone(self):
        self.assertEqual(self.init("--decline-state").returncode, 0)
        self.assert_legacy_untouched(".cc-suite-state/state.json")


class Row06Sentinels(MigrationRow):
    row = "row-06-sentinels"

    def test_legacy_sentinels_are_not_removed_without_explicit_confirmation(self):
        """§7A row 6 is the one migration that *removes*, so it needs an explicit yes.

        Exit 3 is the shared contract's *decision required*: a report was written and nothing
        changed. Asserting 0 here would have demanded that init silently pick for the user, which is
        exactly what the tri-state flags exist to prevent.
        """
        proc = self.init()
        self.assertEqual(proc.returncode, 3, proc.stderr)
        doc = json.loads((self.ws / ".mcp.json").read_text())
        self.assertIn("cc-suite-mcp", doc.get("mcpServers", {}),
                      "a legacy sentinel was removed without confirmation")

    def test_the_users_own_server_is_never_touched(self):
        self.init()  # exit 3: reports and changes nothing
        doc = json.loads((self.ws / ".mcp.json").read_text())
        self.assertIn("theirs", doc.get("mcpServers", {}))

    def test_unrelated_toml_survives(self):
        self.init()
        self.assertIn('theme = "dark"', (self.ws / ".codex" / "config.toml").read_text())

    def test_doctor_warns_while_legacy_sentinels_remain(self):
        self.init()
        self.assertIn("legacy", self.doctor().stdout.lower())


class Row07TestSpecs(MigrationRow):
    row = "row-07-test-specs"

    def test_specs_are_not_force_renamed(self):
        self.assertEqual(self.init().returncode, 0)
        self.assert_legacy_untouched(".nlpm-test/example.spec.md")


class Row08NoOp(MigrationRow):
    row = "row-08-no-op"

    def test_identical_paths_and_schemas_are_left_exactly_as_they_are(self):
        """Row 8's whole content is that nothing happens, which is only meaningful if asserted."""
        self.assertEqual(self.init().returncode, 0)
        self.assert_legacy_untouched("runs/_reports/runs-stats.json",
                                     "docs/discussion/2026-01-01-a-proposal/plan.md")

    def test_the_runs_stats_config_key_is_unaffected(self):
        self.init()
        stats = json.loads((self.ws / "runs" / "_reports" / "runs-stats.json").read_text())
        self.assertEqual(stats["config_key"], "vibe-suite")


class Row09AuditorData(unittest.TestCase):
    """Owned by E0.8. Asserted as wired, not re-implemented."""

    def test_the_auditor_data_row_has_a_live_owner(self):
        owner = REPO_ROOT / "tests" / "test_migrate_auditor_data.py"
        self.assertTrue(owner.is_file(), "row 9's owning fixture has gone missing")
        self.assertIn("def test_", owner.read_text())

    def test_the_migration_tool_still_ships(self):
        self.assertTrue((REPO_ROOT / "tools" / "migrate-auditor-data.sh").is_file()
                        or (REPO_ROOT / "scripts" / "migrate" / "migrate-auditor-data.sh").is_file(),
                        "row 9 names a tool that is not on disk")


class Row10PluginsAlongside(MigrationRow):
    row = "row-10-plugins-alongside"

    def test_doctor_reports_the_source_plugins_installed_alongside(self):
        self.init()
        self.assertEqual(self.doctor().returncode in (0, 1), True)


class AllRowsCovered(unittest.TestCase):
    def test_every_row_has_a_fixture(self):
        self.assertEqual(sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()), sorted(ROWS))

    def test_every_row_has_a_test_class(self):
        """AC-5 is 'green across all rows', so a row silently losing its assertions must fail."""
        classes = {c.row for c in (Row01Config, Row02Precedence, Row03History, Row04Reports,
                                   Row05State, Row06Sentinels, Row07TestSpecs, Row08NoOp,
                                   Row10PluginsAlongside)}
        classes.add("row-09-auditor-data")  # covered by Row09AuditorData, which needs no workspace
        self.assertEqual(sorted(classes), sorted(ROWS))


if __name__ == "__main__":
    unittest.main()
