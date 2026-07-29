#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""§7A rows 1-8 and 10 — the migration helpers (E0.8 / vibe-10).

One rule governs every row: the suite never deletes or rewrites a legacy store. It copies or
derives, leaves the original untouched, and where both stores exist the new one wins.

**Legacy immutability is a harness property, not a per-row assertion.** `MigrationCase` snapshots
every legacy input before the run and compares it afterwards, in `tearDown`. Writing that assertion
row by row is how rows 3 and 5 came to be missing it in an earlier draft; here a new test cannot
forget it, because it does not have to remember it.

The snapshot covers path set, bytes and mode, so a helper that rewrote a legacy file with identical
content but different permissions is still caught.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATE = REPO_ROOT / "scripts" / "migrate"
EXIT_DECISION = 3


def snapshot(root):
    """Path, mode and bytes for everything beneath `root`. Absent roots snapshot as None."""
    if not Path(root).exists():
        return None
    out = {}
    for path in sorted(Path(root).rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            out[rel] = ("link", os.readlink(path))
        elif path.is_dir():
            out[rel] = ("dir", stat.S_IMODE(path.stat().st_mode))
        else:
            out[rel] = ("file", stat.S_IMODE(path.stat().st_mode), path.read_bytes())
    return out


class MigrationCase(unittest.TestCase):
    """A temp workspace, plus the immutability guarantee every row shares."""

    #: Legacy paths this row reads. Snapshotted before the run, compared after.
    LEGACY = (".cc-suite.md", ".claude/nlpm.local.md", ".claude/nlpm-history.json",
              ".claude/nlpm-reports", ".nlpm-test", ".cc-suite-state", ".codex-toolkit-state")

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self._guarded = False

    def guard_legacy(self):
        """Call once the fixture is written; the comparison runs at teardown."""
        self._before = {rel: snapshot(self.ws / rel) for rel in self.LEGACY}
        self._guarded = True
        self.addCleanup(self._assert_legacy_untouched)

    def _assert_legacy_untouched(self):
        for rel, before in self._before.items():
            self.assertEqual(snapshot(self.ws / rel), before,
                             f"legacy store {rel!r} was modified — the one rule §7A states")

    def write(self, rel, text, mode=None):
        path = self.ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if mode is not None:
            path.chmod(mode)
        return path

    def run_helper(self, name, *args, expect=0, env=None):
        environment = dict(os.environ)
        environment.update(env or {})
        result = subprocess.run(["bash", str(MIGRATE / name), "--workspace", str(self.ws), *args],
                                capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, expect,
                         f"{name}: expected exit {expect}, got {result.returncode}\n"
                         f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result


# --------------------------------------------------------------------------- rows 1 and 2

CC_SUITE = """# CC-Suite Configuration

## Defaults

- **Default effort**: high
- **Default audit type**: mini
- **Default sandbox**: workspace-write
"""

NLPM_LOCAL = """---
score_threshold: 90
strictness: strict
rule_overrides:
  R51:
    enabled: true
---
"""


class TestRowsOneAndTwo(MigrationCase):

    def test_cc_suite_fields_map_into_the_new_schema(self):
        self.write(".cc-suite.md", CC_SUITE)
        self.guard_legacy()
        self.run_helper("migrate-config.sh")
        text = (self.ws / ".vibe-suite.md").read_text(encoding="utf-8")
        self.assertIn("effort: high", text)
        self.assertIn("audit_depth: mini", text)
        self.assertIn("sandbox: workspace-write", text)

    def test_nlpm_quality_section_merges_in_the_same_run(self):
        self.write(".cc-suite.md", CC_SUITE)
        self.write(".claude/nlpm.local.md", NLPM_LOCAL)
        self.guard_legacy()
        self.run_helper("migrate-config.sh")
        text = (self.ws / ".vibe-suite.md").read_text(encoding="utf-8")
        self.assertIn("effort: high", text)          # from row 1
        self.assertIn("score_threshold: 90", text)   # from row 2
        self.assertIn("rule_overrides:", text)

    def test_a_key_with_no_new_equivalent_is_reported_not_invented(self):
        self.write(".claude/nlpm.local.md", NLPM_LOCAL)
        self.guard_legacy()
        result = self.run_helper("migrate-config.sh")
        self.assertIn("strictness", result.stderr)
        self.assertNotIn("strictness", (self.ws / ".vibe-suite.md").read_text(encoding="utf-8"))

    def test_an_existing_new_config_is_never_overwritten(self):
        self.write(".cc-suite.md", CC_SUITE)
        self.write(".vibe-suite.md", "---\nengine: codex\n---\n")
        self.guard_legacy()
        self.run_helper("migrate-config.sh")
        self.assertEqual((self.ws / ".vibe-suite.md").read_text(encoding="utf-8"),
                         "---\nengine: codex\n---\n")

    def test_nothing_to_migrate_is_not_an_error(self):
        self.guard_legacy()
        self.run_helper("migrate-config.sh")
        self.assertFalse((self.ws / ".vibe-suite.md").exists())

    # -- conflicts: asked once, resolved per key --------------------------------------------

    def _conflicting_workspace(self):
        self.write(".cc-suite.md", "- **Default effort**: high\n")
        self.write(".claude/nlpm.local.md", "---\neffort: low\nscore_threshold: 90\n---\n")

    def test_conflicts_exit_three_and_write_nothing(self):
        self._conflicting_workspace()
        self.guard_legacy()
        self.run_helper("migrate-config.sh", expect=EXIT_DECISION)
        self.assertFalse((self.ws / ".vibe-suite.md").exists(),
                         "a conflict must not write a partially-decided config")
        report = json.loads((self.ws / ".vibe-suite-state" /
                             "migration-conflicts.json").read_text(encoding="utf-8"))
        self.assertEqual(set(report["conflicts"]), {"effort"})
        self.assertEqual(report["conflicts"]["effort"], {"cc-suite": "high", "nlpm": "low"})

    def test_resolution_is_per_key_not_one_global_choice(self):
        """"Ask once" bounds how often the user is interrupted, not how many keys one answer
        covers. Three conflicts resolved three different ways must produce that mixture."""
        self.write(".cc-suite.md",
                   "- **Default effort**: high\n"
                   "- **Default audit type**: mini\n"
                   "- **Default sandbox**: workspace-write\n")
        self.write(".claude/nlpm.local.md",
                   "---\neffort: low\naudit_depth: full\nsandbox: read-only\n---\n")
        self.guard_legacy()
        self.run_helper("migrate-config.sh", expect=EXIT_DECISION)
        resolution = self.ws / "resolution.json"
        resolution.write_text(json.dumps({"effort": "cc-suite", "audit_depth": "nlpm",
                                          "sandbox": "cc-suite"}), encoding="utf-8")
        self.run_helper("migrate-config.sh", "--resolution", str(resolution))
        text = (self.ws / ".vibe-suite.md").read_text(encoding="utf-8")
        self.assertIn("effort: high", text)              # cc-suite side
        self.assertIn("audit_depth: full", text)         # nlpm side
        self.assertIn("sandbox: workspace-write", text)  # cc-suite side

    def test_a_resolution_missing_a_reported_key_is_an_error(self):
        self._conflicting_workspace()
        self.guard_legacy()
        self.run_helper("migrate-config.sh", expect=EXIT_DECISION)
        resolution = self.ws / "resolution.json"
        resolution.write_text("{}", encoding="utf-8")
        result = self.run_helper("migrate-config.sh", "--resolution", str(resolution), expect=1)
        self.assertIn("effort", result.stderr)
        self.assertFalse((self.ws / ".vibe-suite.md").exists())

    def test_precedence_beats_conflict(self):
        """A settled question is not a question: if the new store already holds the key, disagreeing
        legacy sources must not interrupt the user."""
        self._conflicting_workspace()
        self.write(".vibe-suite.md", "---\neffort: medium\n---\n")
        self.guard_legacy()
        self.run_helper("migrate-config.sh", expect=0)
        self.assertFalse((self.ws / ".vibe-suite-state" / "migration-conflicts.json").exists())
        self.assertEqual((self.ws / ".vibe-suite.md").read_text(encoding="utf-8"),
                         "---\neffort: medium\n---\n")


# --------------------------------------------------------------------------- row 3

class TestRowThree(MigrationCase):

    HISTORY = json.dumps([{"run": 1, "score": 80}, {"run": 2, "score": 85}], indent=2) + "\n"

    def test_history_copies_with_exactly_one_marker(self):
        self.write(".claude/nlpm-history.json", self.HISTORY)
        self.guard_legacy()
        self.run_helper("migrate-history.sh")
        data = json.loads((self.ws / ".claude" / "vibe-history.json").read_text(encoding="utf-8"))
        self.assertEqual([e for e in data if "run" in e], json.loads(self.HISTORY))
        markers = [e for e in data if "migrated_from" in e]
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]["migrated_from"]["path"], ".claude/nlpm-history.json")

    def test_second_run_adds_no_second_marker(self):
        self.write(".claude/nlpm-history.json", self.HISTORY)
        self.guard_legacy()
        self.run_helper("migrate-history.sh")
        first = (self.ws / ".claude" / "vibe-history.json").read_bytes()
        self.run_helper("migrate-history.sh")
        self.assertEqual((self.ws / ".claude" / "vibe-history.json").read_bytes(), first)

    def test_an_existing_new_history_is_left_alone(self):
        self.write(".claude/nlpm-history.json", self.HISTORY)
        self.write(".claude/vibe-history.json", "[]\n")
        self.guard_legacy()
        self.run_helper("migrate-history.sh")
        self.assertEqual((self.ws / ".claude" / "vibe-history.json").read_text(encoding="utf-8"),
                         "[]\n")

    def test_a_mapping_history_gets_one_marker_too(self):
        self.write(".claude/nlpm-history.json", '{"runs": []}\n')
        self.guard_legacy()
        self.run_helper("migrate-history.sh")
        data = json.loads((self.ws / ".claude" / "vibe-history.json").read_text(encoding="utf-8"))
        self.assertIn("migrated_from", data)
        self.assertEqual(data["runs"], [])


# --------------------------------------------------------------------------- row 5

def legacy_state(value):
    return json.dumps({"config": {"stopReviewGate": value}}, indent=2) + "\n"


class TestRowFive(MigrationCase):

    def _stored(self):
        """The stored `gate` section, as `store.py` nests it — not a flat dotted key."""
        path = self.ws / ".vibe-suite-state" / "state.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8")).get("config", {}).get("gate", {})

    def test_absent_key_is_imported(self):
        self.write(".cc-suite-state/state.json", legacy_state(True))
        self.guard_legacy()
        self.run_helper("migrate-state.sh")
        self.assertEqual(self._stored().get("stop_review_gate"), True)

    def test_a_stored_false_is_not_mistaken_for_absence(self):
        """`Store.get()` returns the fresh default for an absent key, so a stored `false` and an
        unset key are indistinguishable through it. This is the test that fails if the helper
        checks `get()` instead of `overrides()`."""
        self.write(".vibe-suite-state/state.json",
                   json.dumps({"config": {"gate": {"stop_review_gate": False}}}) + "\n")
        self.write(".cc-suite-state/state.json", legacy_state(True))
        self.guard_legacy()
        self.run_helper("migrate-state.sh")
        self.assertEqual(self._stored().get("stop_review_gate"), False,
                         "the already-set value must win")

    def test_no_legacy_value_is_not_an_error(self):
        self.guard_legacy()
        self.run_helper("migrate-state.sh")

    def test_two_legacy_dirs_disagreeing_exit_three(self):
        self.write(".cc-suite-state/state.json", legacy_state(True))
        self.write(".codex-toolkit-state/state.json", legacy_state(False))
        self.guard_legacy()
        self.run_helper("migrate-state.sh", expect=EXIT_DECISION)
        self.assertEqual(self._stored(), {})
        self.assertTrue((self.ws / ".vibe-suite-state" / "migration-conflicts.txt").exists())

    def test_two_legacy_dirs_agreeing_import_cleanly(self):
        self.write(".cc-suite-state/state.json", legacy_state(True))
        self.write(".codex-toolkit-state/state.json", legacy_state(True))
        self.guard_legacy()
        self.run_helper("migrate-state.sh")
        self.assertEqual(self._stored().get("stop_review_gate"), True)

    def test_precedence_beats_conflict(self):
        """Disagreeing legacy dirs must not interrupt when the new store already decided."""
        self.write(".vibe-suite-state/state.json",
                   json.dumps({"config": {"gate": {"stop_review_gate": True}}}) + "\n")
        self.write(".cc-suite-state/state.json", legacy_state(True))
        self.write(".codex-toolkit-state/state.json", legacy_state(False))
        self.guard_legacy()
        self.run_helper("migrate-state.sh", expect=0)
        self.assertFalse((self.ws / ".vibe-suite-state" / "migration-conflicts.txt").exists())


# --------------------------------------------------------------------------- row 6

MCP_JSON = json.dumps({
    "mcpServers": {
        "cc-suite-mcp": {"command": "cc-suite-server"},
        "cc-suite-agent:auditor": {"command": "cc-suite-auditor"},
        "unrelated": {"command": "keep-me"},
    }
}, indent=2) + "\n"

CODEX_TOML = """[general]
keep = true

[mcp_servers.cc-suite-mcp]
command = "cc-suite-server"

[mcp_servers.unrelated]
command = "keep-me"
"""


QUOTED_TOML = """[general]
keep = true

[mcp_servers.cc-suite-mcp]
command = "cc-suite-server"

[mcp_servers.cc-suite-mcp.env]
TOKEN = "keep-this"

[mcp_servers."cc-suite-agent:auditor"]
command = "cc-suite-auditor"
"""

SUBTABLE_ONLY_TOML = """[mcp_servers.cc-suite-mcp]
command = "cc-suite-server"

[mcp_servers.vibe-mcp.env]
TOKEN = "pre-existing"
"""

ODD_HEADER_TOML = """[mcp_servers.'cc-suite-agent:auditor']
command = "cc-suite-auditor"

[mcp_servers.cc-suite-mcp]  # the primary server
command = "cc-suite-server"
"""

class TestRowSix(MigrationCase):

    LEGACY = MigrationCase.LEGACY  # .mcp.json is mutated by design; it is not a legacy *store*

    def _setup_sentinels(self):
        self.write(".mcp.json", MCP_JSON)
        self.write(".codex/config.toml", CODEX_TOML)
        self.guard_legacy()

    def _servers(self):
        return json.loads((self.ws / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]

    def _toml(self):
        return (self.ws / ".codex" / "config.toml").read_text(encoding="utf-8")

    def test_without_confirmation_only_the_decision_report_appears(self):
        """Exit 3 must write a machine-readable report — the caller cannot parse prose on stderr —
        and must change nothing else. An earlier version of this test asserted the whole workspace
        was byte-identical, which forbade the very report the exit contract requires."""
        self._setup_sentinels()
        before = snapshot(self.ws)
        self.run_helper("migrate-sentinels.sh", expect=EXIT_DECISION)
        report = self.ws / ".vibe-suite-state" / "row6-decision.json"
        self.assertTrue(report.exists(), "exit 3 must write a decision report")
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(set(payload["remove"][".mcp.json"]),
                         {"cc-suite-mcp", "cc-suite-agent:auditor"})
        self.assertEqual(payload["register"][".codex/config.toml"], ["vibe-mcp"])

        after = snapshot(self.ws)
        self.assertEqual(set(after) - set(before),
                         {".vibe-suite-state", ".vibe-suite-state/row6-decision.json"},
                         "nothing beyond the report may be created")
        for path in set(before):
            with self.subTest(path=path):
                self.assertEqual(after[path], before[path], "no existing path may change")

    def test_quoted_headers_and_subtables_migrate(self):
        """A sentinel whose name carries a colon is normally spelled
        [mcp_servers."cc-suite-agent:auditor"], and a sentinel may own subtables. A splitter that
        treats "." as an unconditional separator misses both."""
        self.write(".mcp.json", json.dumps({"mcpServers": {}}, indent=2) + "\n")
        self.write(".codex/config.toml", QUOTED_TOML)
        self.guard_legacy()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        toml = self._toml()
        self.assertIn("[mcp_servers.vibe-mcp]", toml)
        self.assertIn("[mcp_servers.vibe-mcp.env]", toml, "subtables must come across")
        self.assertIn('TOKEN = "keep-this"', toml)
        self.assertIn('[mcp_servers."vibe-agent:auditor"]', toml,
                      "a quoted sentinel name must be recognised and requoted")
        # The *headers* must be gone. The command values legitimately still name the
        # `cc-suite-server` executable: re-registration points the new sentinel at the same
        # server, so asserting the string "cc-suite" is absent would forbid a correct migration.
        headers = [line for line in toml.splitlines() if line.startswith("[")]
        self.assertEqual([h for h in headers if "cc-suite" in h], [],
                         "every legacy sentinel header must be pruned")
        self.assertIn("[general]", toml)
        self.assertIn('command = "cc-suite-server"', toml,
                      "the server the sentinel points at is unchanged by a rename")

    def test_a_subtable_alone_is_not_a_registration(self):
        """`[mcp_servers.vibe-mcp.env]` without `[mcp_servers.vibe-mcp]` describes the environment
        of a server that is not declared. Treating it as "already registered" skips installing the
        real table, lets verification pass, and then prunes the only functional legacy block — the
        forbidden neither state, reached by a route that looks like success."""
        self.write(".mcp.json", json.dumps({"mcpServers": {}}, indent=2) + "\n")
        self.write(".codex/config.toml", SUBTABLE_ONLY_TOML)
        self.guard_legacy()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        toml = self._toml()
        self.assertIn("[mcp_servers.vibe-mcp]", toml,
                      "the root table must be installed even when a subtable already exists")
        self.assertIn('command = "cc-suite-server"', toml,
                      "the working server definition must survive the transition")
        headers = [line for line in toml.splitlines() if line.startswith("[")]
        self.assertEqual([h for h in headers if "cc-suite" in h], [])

    def test_single_quoted_and_commented_headers_are_recognised(self):
        """Both quote styles are valid TOML, and a trailing comment is legal on a header line."""
        self.write(".mcp.json", json.dumps({"mcpServers": {}}, indent=2) + "\n")
        self.write(".codex/config.toml", ODD_HEADER_TOML)
        self.guard_legacy()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        toml = self._toml()
        headers = [line for line in toml.splitlines() if line.startswith("[")]
        self.assertEqual([h for h in headers if "cc-suite" in h], [],
                         "a single-quoted or commented legacy header must still be pruned")
        self.assertTrue(any("vibe-agent:auditor" in h for h in headers))
        self.assertTrue(any("vibe-mcp" in h for h in headers))

    def test_provenance_records_both_stores_in_restorable_form(self):
        """Recording only the JSON side would make the removal reversible in one file and
        irreversible in the other."""
        self._setup_sentinels()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        restore = self._provenance()["restore"]
        self.assertEqual(set(restore[".mcp.json"]), {"cc-suite-mcp", "cc-suite-agent:auditor"})
        self.assertIn('command = "cc-suite-server"', restore[".codex/config.toml"]["cc-suite-mcp"])

    def test_no_temporary_file_is_left_behind(self):
        """Atomic writes go through an mkstemp temporary in the same directory — an unpredictable
        name, so it cannot be pre-planted as a symlink. None may survive the run."""
        self._setup_sentinels()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        self.assertEqual([str(p) for p in self.ws.rglob("*.tmp")], [])

    def test_confirmed_run_registers_then_prunes(self):
        self._setup_sentinels()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        servers = self._servers()
        self.assertIn("vibe-mcp", servers)
        self.assertIn("vibe-agent:auditor", servers)
        self.assertNotIn("cc-suite-mcp", servers)
        self.assertNotIn("cc-suite-agent:auditor", servers)
        self.assertEqual(servers["unrelated"], {"command": "keep-me"},
                         "unrelated configuration must be preserved")
        self.assertIn("[mcp_servers.vibe-mcp]", self._toml())
        self.assertNotIn("[mcp_servers.cc-suite-mcp]", self._toml())
        self.assertIn("[general]", self._toml())
        self.assertIn("[mcp_servers.unrelated]", self._toml())

    def test_an_existing_vibe_sentinel_is_preserved_verbatim(self):
        data = json.loads(MCP_JSON)
        data["mcpServers"]["vibe-mcp"] = {"command": "customised-by-the-user"}
        self.write(".mcp.json", json.dumps(data, indent=2) + "\n")
        self.write(".codex/config.toml", CODEX_TOML)
        self.guard_legacy()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        self.assertEqual(self._servers()["vibe-mcp"], {"command": "customised-by-the-user"})

    def test_nothing_to_do_is_not_an_error(self):
        self.write(".mcp.json", json.dumps({"mcpServers": {"x": {}}}, indent=2) + "\n")
        self.guard_legacy()
        self.run_helper("migrate-sentinels.sh", "--confirm")

    # -- ordering, proved by injecting a failure at each step -------------------------------

    def _provenance(self):
        path = self.ws / ".vibe-suite-state" / "row6-provenance.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def test_failure_before_provenance_changes_nothing(self):
        self._setup_sentinels()
        before = snapshot(self.ws)
        self.run_helper("migrate-sentinels.sh", "--confirm", expect=1,
                        env={"VIBE_FAIL_AFTER": "start"})
        self.assertEqual(snapshot(self.ws), before)

    def test_failure_after_provenance_leaves_legacy_intact_and_no_vibe_sentinel(self):
        self._setup_sentinels()
        self.run_helper("migrate-sentinels.sh", "--confirm", expect=1,
                        env={"VIBE_FAIL_AFTER": "provenance"})
        self.assertIsNotNone(self._provenance(), "provenance must exist before any mutation")
        self.assertIn("cc-suite-mcp", self._servers())
        self.assertNotIn("vibe-mcp", self._servers())

    def test_failure_between_the_two_registrations_never_leaves_neither(self):
        self._setup_sentinels()
        self.run_helper("migrate-sentinels.sh", "--confirm", expect=1,
                        env={"VIBE_FAIL_AFTER": "register-json"})
        self.assertIn("vibe-mcp", self._servers())
        self.assertIn("cc-suite-mcp", self._servers(),
                      "the legacy block must survive until both registrations exist")

    def test_failure_before_pruning_leaves_both_registrations(self):
        self._setup_sentinels()
        self.run_helper("migrate-sentinels.sh", "--confirm", expect=1,
                        env={"VIBE_FAIL_AFTER": "verified"})
        self.assertIn("vibe-mcp", self._servers())
        self.assertIn("cc-suite-mcp", self._servers())
        self.assertIn("[mcp_servers.vibe-mcp]", self._toml())

    def test_a_rerun_after_each_failure_converges(self):
        for step in ("provenance", "register-json", "register-toml", "verified"):
            with self.subTest(failed_after=step):
                self.setUp()
                self._setup_sentinels()
                self.run_helper("migrate-sentinels.sh", "--confirm", expect=1,
                                env={"VIBE_FAIL_AFTER": step})
                self.run_helper("migrate-sentinels.sh", "--confirm")
                self.assertIn("vibe-mcp", self._servers())
                self.assertNotIn("cc-suite-mcp", self._servers())
                self.assertNotIn("[mcp_servers.cc-suite-mcp]", self._toml())

    def test_rerunning_a_complete_transition_changes_nothing(self):
        self._setup_sentinels()
        self.run_helper("migrate-sentinels.sh", "--confirm")
        after = snapshot(self.ws)
        self.run_helper("migrate-sentinels.sh", "--confirm")
        self.assertEqual(snapshot(self.ws), after)


# --------------------------------------------------------------------------- rows 4, 7, 8, 10

class TestSurvey(MigrationCase):

    def _run(self, **env):
        result = self.run_helper("survey.sh", env=env)
        return json.loads(result.stdout), result.stderr

    def test_row_four_reports_the_old_reports_dir_without_copying(self):
        self.write(".claude/nlpm-reports/r.json", "{}\n")
        self.guard_legacy()
        report, _ = self._run()
        self.assertEqual([f for f in report["findings"] if f["row"] == 4][0]["action"], "none")
        self.assertFalse((self.ws / ".claude" / "vibe-reports").exists())

    def test_row_seven_renames_nothing(self):
        self.write(".nlpm-test/a.spec.md", "spec\n")
        self.guard_legacy()
        report, _ = self._run()
        self.assertEqual([f for f in report["findings"] if f["row"] == 7][0]["files"], 1)
        self.assertTrue((self.ws / ".nlpm-test" / "a.spec.md").exists())
        self.assertFalse((self.ws / ".vibe-test").exists())

    def test_row_eight_is_a_no_op_across_the_whole_workspace(self):
        """Scoped to the entire workspace, not to the two directories row 8 names: a helper that
        left `runs/` alone while writing a provenance file elsewhere would pass the narrow form."""
        self.write("runs/r1/notes.md", "kept\n")
        self.write("docs/discussion/d1.md", "kept\n")
        self.write(".cc-suite.md", CC_SUITE)
        self.guard_legacy()
        before = snapshot(self.ws)
        self._run()
        self.assertEqual(snapshot(self.ws), before,
                         "survey.sh must not create, delete or modify anything at all")

    def test_row_ten_recommends_uninstall_for_each_detected_plugin(self):
        root = self.ws / "plugins"
        for name in ("cc-suite", "nlpm"):
            (root / name).mkdir(parents=True)
        self.guard_legacy()
        report, stderr = self._run(VIBE_PLUGIN_ROOT=str(root))
        row_ten = {f["plugin"]: f for f in report["findings"] if f["row"] == 10}
        self.assertEqual(set(row_ten), {"cc-suite", "nlpm"})
        for name, finding in row_ten.items():
            with self.subTest(plugin=name):
                self.assertEqual(finding["action"], "recommend-uninstall")
                self.assertIn(f"uninstall {name}", finding["recommendation"])
                self.assertIn(f"uninstall {name}", stderr)
        self.assertTrue((root / "cc-suite").exists(), "detection must not uninstall anything")


if __name__ == "__main__":
    unittest.main()


class FixedReportPathsAreNotTruncated(unittest.TestCase):
    """A fixed path is a path the user may own. Row 5's conflicts report truncated whatever sat
    there; row 6 replaced the live config through a symlink and forced it to 0644."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-fixedpath-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        (self.ws / ".vibe-suite-state").mkdir(parents=True)

    def _state_dirs_disagreeing(self):
        for name, value in ((".cc-suite-state", True), (".codex-toolkit-state", False)):
            d = self.ws / name
            d.mkdir()
            (d / "state.json").write_text(json.dumps({"config": {"stopReviewGate": value}}))

    def test_a_users_conflicts_report_is_not_overwritten(self):
        self._state_dirs_disagreeing()
        report = self.ws / ".vibe-suite-state" / "migration-conflicts.txt"
        report.write_text("notes I keep here")
        proc = subprocess.run(["bash", str(REPO_ROOT / "scripts/migrate/migrate-state.sh"),
                               "--workspace", str(self.ws)], capture_output=True, text=True)
        self.assertEqual(report.read_text(), "notes I keep here",
                         "a user's file at the report path was truncated")
        self.assertEqual(proc.returncode, 1)

    def test_row_six_preserves_the_live_configs_mode(self):
        mcp = self.ws / ".mcp.json"
        mcp.write_text(json.dumps({"mcpServers": {"cc-suite-mcp": {"command": "x"}}}))
        os.chmod(mcp, 0o600)
        subprocess.run(["bash", str(REPO_ROOT / "scripts/migrate/migrate-sentinels.sh"),
                        "--workspace", str(self.ws), "--confirm"], capture_output=True, text=True)
        mode = stat.S_IMODE(mcp.lstat().st_mode)
        self.assertEqual(mode & 0o077, 0,
                         f"a 0600 config was republished group/world readable at {oct(mode)}")

    def test_row_six_refuses_a_symlinked_live_config(self):
        real = self.ws / "elsewhere.json"
        real.write_text(json.dumps({"mcpServers": {"cc-suite-mcp": {"command": "x"}}}))
        (self.ws / ".mcp.json").symlink_to(real)
        subprocess.run(["bash", str(REPO_ROOT / "scripts/migrate/migrate-sentinels.sh"),
                        "--workspace", str(self.ws), "--confirm"], capture_output=True, text=True)
        self.assertTrue((self.ws / ".mcp.json").is_symlink(),
                        "the user's link was converted to a regular file")


class ProvenanceStepDoesNotLeakThroughScratch(unittest.TestCase):
    """`vibe_provenance_step` wrote a **fixed** `.tmp` sibling with `open(..., "w")`. The provenance
    record holds complete pre-images, so that scratch file was a world-readable copy of a `0600`
    `.mcp.json` — the leak `c2112ac` closed on the record itself, reopened one path over."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-provstep-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.prov = self.ws / "install-provenance.json"
        self.prov.write_text(json.dumps(
            {"steps": [], "targets": [{"path": "/x/.mcp.json", "content_b64": "czNjcmV0"}]}))
        os.chmod(self.prov, 0o600)

    def _step(self, name):
        script = (f'source "{REPO_ROOT}/scripts/migrate/common.sh"\n'
                  f'vibe_provenance_step "{self.prov}" "{name}"\n')
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    def test_the_record_keeps_its_mode_and_no_readable_copy_survives(self):
        proc = self._step("config")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("config", json.loads(self.prov.read_text())["steps"])
        mode = stat.S_IMODE(self.prov.lstat().st_mode)
        self.assertEqual(mode & 0o077, 0, f"the record ended up at {oct(mode)}")
        leftovers = [p for p in self.ws.iterdir() if p != self.prov]
        for leftover in leftovers:
            left_mode = stat.S_IMODE(leftover.lstat().st_mode)
            self.assertEqual(left_mode & 0o077, 0,
                             f"{leftover.name} is a readable copy at {oct(left_mode)}")

    def test_a_symlinked_record_is_refused(self):
        real = self.ws / "elsewhere.json"
        real.write_text(json.dumps({"steps": []}))
        link = self.ws / "linked-provenance.json"
        link.symlink_to(real)
        script = (f'source "{REPO_ROOT}/scripts/migrate/common.sh"\n'
                  f'vibe_provenance_step "{link}" "config"\n')
        subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertTrue(link.is_symlink(), "the user's link was converted to a regular file")
