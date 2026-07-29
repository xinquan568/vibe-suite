#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Init-level fixtures for `/vibe-suite:init` (E2.1 / vibe-18).

**These are composition tests, and that is the point.** `tests/test_migrate.py` proves the five §7A
helpers implement rows 1-8/10 — and it stays green whether or not `init.sh` ever calls four of them.
AC-5 is written against `/vibe:init`, so only a fixture that runs init can discharge it.

The decision protocol is tri-state per row: a flag absent means *not asked*, `--resolve-*` means
*accepted with this value*, `--decline-*` means *asked and declined*. `false` is a legitimate value
for `gate.stop_review_gate`, so a two-valued flag could not carry the third state — that conflation
is what round 3's review rejected.

Init is **re-entrant, not resumable**: every invocation re-runs from the start and relies on each
helper's own idempotence, so the accumulating decision flags are the whole resume state and nothing
about a decision is persisted between runs.
"""

import json
import stat
import base64
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INIT = REPO_ROOT / "scripts" / "init.sh"
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import bridge        # noqa: E402
import init_bridge   # noqa: E402

#: Everything an install may add while reporting a decision, and nothing more. `migrate-*` writes its
#: report into the state dir by contract (`common.sh:11`), and init writes provenance before its
#: first mutation, so a conflict run is never a no-op on the whole tree — only on the targets.
DECISION_ADDITIONS = {".vibe-suite-state"}


def run_init(workspace, *args, env=None):
    environ = dict(os.environ)
    environ.setdefault("VIBE_NONINTERACTIVE_OK", "1")
    if env:
        environ.update(env)
    return subprocess.run(
        ["bash", str(INIT), "--workspace", str(workspace), *args],
        capture_output=True, text=True, env=environ,
    )


def tree(root):
    """path -> (kind, mode, content-or-link-target). Compared for equality across runs."""
    root = Path(root)
    out = {}
    for path in sorted(root.rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            out[rel] = ("l", None, os.readlink(path))
        elif path.is_dir():
            out[rel] = ("d", oct(path.stat().st_mode & 0o7777), None)
        else:
            out[rel] = ("f", oct(path.stat().st_mode & 0o7777), path.read_bytes())
    return out


def mtimes(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.lstat().st_mtime_ns for p in sorted(root.rglob("*"))}


class InitCase(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-init-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    # -- fixture builders ---------------------------------------------------------------------

    def legacy_config(self):
        (self.ws / ".cc-suite.md").write_text("- **Default effort**: high\n", encoding="utf-8")

    def conflicting_config(self):
        """The shape `tests/test_migrate.py` establishes: the two sources disagree on `effort`."""
        self.legacy_config()
        (self.ws / ".claude").mkdir(exist_ok=True)
        (self.ws / ".claude" / "nlpm.local.md").write_text(
            "---\neffort: low\nscore_threshold: 90\n---\n", encoding="utf-8")

    def legacy_history(self):
        d = self.ws / ".claude"
        d.mkdir(exist_ok=True)
        (d / "nlpm-history.json").write_text(
            json.dumps({"snapshots": [{"score": 71}]}) + "\n", encoding="utf-8")

    def legacy_state(self, value, name="codex-toolkit"):
        d = self.ws / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "config.json").write_text(
            json.dumps({"config": {"stopReviewGate": value}}) + "\n", encoding="utf-8")

    def legacy_sentinels(self):
        (self.ws / ".mcp.json").write_text(
            json.dumps({"mcpServers": {"cc-suite-mcp": {"command": "x"}}}, indent=2) + "\n",
            encoding="utf-8")

    def answers(self):
        return ["--effort", "medium", "--audit-depth", "mini", "--strictness", "standard"]


# ---------------------------------------------------------------------------------------------
# Composition — the claim helper-level tests cannot make
# ---------------------------------------------------------------------------------------------

class TestComposition(InitCase):
    def test_all_five_helpers_run_and_legacy_survives_byte_identical(self):
        self.legacy_config()
        self.legacy_history()
        self.legacy_state(True)
        (self.ws / ".claude" / "nlpm-reports").mkdir(parents=True, exist_ok=True)
        before = {p: (self.ws / p).read_bytes()
                  for p in (".cc-suite.md", ".claude/nlpm-history.json",
                            "codex-toolkit/config.json")}
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertTrue((self.ws / ".vibe-suite.md").is_file(), "row 1-2 did not run")
        self.assertTrue((self.ws / ".claude/vibe-history.json").is_file(), "row 3 did not run")
        self.assertIn("row 5", result.stderr, "row 5 helper was not invoked")
        self.assertIn("row 6", result.stderr, "row 6 helper was not invoked")
        self.assertIn("row 4", result.stderr, "survey did not run")

        for path, content in before.items():
            self.assertEqual((self.ws / path).read_bytes(), content,
                             f"{path} was modified — §7A forbids touching a legacy store")

    def test_migration_runs_before_the_fresh_config_is_written(self):
        """The ordering guard. `migrate-config.sh` skips once `.vibe-suite.md` exists, so a
        fresh-write-first install loses the legacy content with only a note."""
        self.legacy_config()
        run_init(self.ws, *self.answers())
        text = (self.ws / ".vibe-suite.md").read_text(encoding="utf-8")
        self.assertIn("high", text,
                      "the legacy value is absent — config-fill ran before migration")

    def test_survey_warnings_reach_init_output(self):
        (self.ws / ".claude").mkdir(exist_ok=True)
        (self.ws / ".claude" / "nlpm-reports").mkdir()
        (self.ws / ".nlpm-test").mkdir()
        (self.ws / ".nlpm-test" / "a.spec.md").write_text("spec\n", encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertIn("row 4", result.stderr)
        self.assertIn("row 7", result.stderr)

    def test_rows_eight_and_ten_are_reported_and_change_nothing(self):
        """Row 8's paths are already identical and row 10 is a recommendation, so the only evidence
        either ran is init's output — and the only correct behaviour is to touch nothing."""
        (self.ws / "runs").mkdir()
        (self.ws / "runs" / "keep.json").write_text("{}\n", encoding="utf-8")
        (self.ws / ".claude").mkdir(exist_ok=True)
        (self.ws / ".claude" / "plugins").mkdir(parents=True)
        (self.ws / ".claude" / "plugins" / "nlpm").mkdir()
        before = tree(self.ws)
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)
        for rel, value in before.items():
            self.assertEqual(tree(self.ws)[rel], value, f"{rel} changed; rows 8/10 copy nothing")
        rows = {f["row"] for f in json.loads(result.stdout)["findings"]}
        self.assertIn(8, rows, "row 8's finding did not reach init's caller")

    def test_pre_existing_new_store_wins_over_legacy(self):
        self.legacy_config()
        (self.ws / ".vibe-suite.md").write_text("---\nengine: claude\n---\n", encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("claude", (self.ws / ".vibe-suite.md").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------------------------
# The tri-state decision protocol — accepted and declined, per row
# ---------------------------------------------------------------------------------------------

class TestDecisions(InitCase):
    def _added(self, before):
        return set(tree(self.ws)) - set(before)

    def test_config_conflict_exits_three_and_touches_no_target(self):
        self.conflicting_config()
        before = tree(self.ws)
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 3, result.stderr)
        for rel, value in before.items():
            self.assertEqual(tree(self.ws).get(rel), value, f"{rel} changed during a discovery run")
        added = {a.split("/")[0] for a in self._added(before)}
        self.assertTrue(added <= DECISION_ADDITIONS,
                        f"a discovery run added more than its report: {added}")

    def test_config_conflict_accepted_completes(self):
        self.conflicting_config()
        run_init(self.ws, *self.answers())
        result = run_init(self.ws, *self.answers(), "--resolve-config",
                          json.dumps({"effort": "cc-suite"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("high", (self.ws / ".vibe-suite.md").read_text(encoding="utf-8"))

    def test_config_conflict_declined_continues_the_install(self):
        self.conflicting_config()
        result = run_init(self.ws, *self.answers(), "--decline-config")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.ws / ".cc-suite.md").read_text(encoding="utf-8"),
                         "- **Default effort**: high\n")
        self.assertTrue((self.ws / "AGENTS.md").is_file(),
                        "a declined row must not abort the rest of the install")

    def test_state_disagreement_accepted_with_false_is_not_a_decline(self):
        """`false` is a legitimate chosen value — the conflation round 3 rejected."""
        self.legacy_state(True, "codex-toolkit")
        self.legacy_state(False, "cc-suite-state")
        result = run_init(self.ws, *self.answers(), "--resolve-state", "false")
        self.assertEqual(result.returncode, 0, result.stderr)
        store = json.loads((self.ws / ".vibe-suite-state" / "state.json").read_text())
        self.assertIs(store["config"]["gate"]["stop_review_gate"], False)

    def test_state_disagreement_declined_leaves_the_key_unset(self):
        self.legacy_state(True, "codex-toolkit")
        self.legacy_state(False, "cc-suite-state")
        result = run_init(self.ws, *self.answers(), "--decline-state")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.ws / ".vibe-suite-state" / "state.json"
        stored = json.loads(path.read_text()) if path.is_file() else {}
        self.assertNotIn("stop_review_gate", stored.get("config", {}).get("gate", {}))

    def test_sentinels_declined_leaves_legacy_registrations(self):
        self.legacy_sentinels()
        result = run_init(self.ws, *self.answers(), "--confirm-sentinels", "no")
        self.assertEqual(result.returncode, 0, result.stderr)
        servers = json.loads((self.ws / ".mcp.json").read_text())["mcpServers"]
        self.assertIn("cc-suite-mcp", servers, "a declined row 6 must leave legacy sentinels")

    def test_accept_and_decline_together_is_an_error(self):
        result = run_init(self.ws, *self.answers(), "--decline-state", "--resolve-state", "true")
        self.assertNotEqual(result.returncode, 0)

    def test_non_interactive_propagates_exit_three(self):
        self.conflicting_config()
        result = run_init(self.ws, *self.answers(), "--non-interactive")
        self.assertEqual(result.returncode, 3)
        self.assertIn("migration-conflicts.json", result.stderr)


# ---------------------------------------------------------------------------------------------
# Ownership, containment, idempotence
# ---------------------------------------------------------------------------------------------

class TestOwnershipAndIdempotence(InitCase):
    def test_user_authored_memory_files_keep_every_byte(self):
        original = "# My project\n\nNotes I wrote myself.\n"
        (self.ws / "CLAUDE.md").write_text(original, encoding="utf-8")
        (self.ws / "AGENTS.md").write_text(original, encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("CLAUDE.md", "AGENTS.md"):
            text = (self.ws / name).read_text(encoding="utf-8")
            self.assertIn(original.strip(), text, f"{name} lost user content")
            self.assertIn("vibe-suite:", text, f"{name} did not gain an owned block")

    def test_second_run_changes_nothing_at_all(self):
        """AC-2. mtimes are the discriminator: rewriting identical bytes is exactly what a
        non-idempotent upsert does, and content plus mode comparison cannot see it."""
        run_init(self.ws, *self.answers())
        before, before_mtimes = tree(self.ws), mtimes(self.ws)
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree(self.ws), before, "second run changed content, modes or paths")
        self.assertEqual(mtimes(self.ws), before_mtimes, "second run rewrote identical bytes")

    def test_a_symlinked_target_outside_the_workspace_is_refused(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (self.ws / ".claude").symlink_to(outside, target_is_directory=True)
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0, "an escaping write must be refused")
        self.assertEqual(list(outside.iterdir()), [], "init wrote outside the workspace")

    def test_a_directory_where_a_file_belongs_is_refused(self):
        (self.ws / "AGENTS.md").mkdir()
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0)

    def test_every_agent_sentinel_is_enumerated(self):
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "vibe-agent:auditor": {"command": "a"},
            "vibe-agent:reviewer": {"command": "b"},
            "unrelated": {"command": "c"},
        }}, indent=2) + "\n", encoding="utf-8")
        result = run_init(self.ws, *self.answers(), "--list-owned")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("vibe-agent:auditor", result.stdout)
        self.assertIn("vibe-agent:reviewer", result.stdout)
        self.assertNotIn("unrelated", result.stdout)


class TestCrashConvergence(InitCase):
    def test_interruption_at_each_checkpoint_converges_on_rerun(self):
        probe = run_init(self.ws, *self.answers(), "--list-checkpoints")
        self.assertEqual(probe.returncode, 0, probe.stderr)
        steps = [s for s in probe.stdout.split() if s]
        self.assertGreaterEqual(len(steps), 12, "checkpoint list shrank")

        # The shape an uninterrupted install produces, to compare every healed run against.
        clean = Path(tempfile.mkdtemp(prefix="vibe-clean-"))
        self.addCleanup(shutil.rmtree, clean, ignore_errors=True)
        self.assertEqual(run_init(clean, *self.answers()).returncode, 0)
        def normalise(root, snapshot):
            marker = str(root).encode()
            return {k: (kind, mode,
                        blob.replace(marker, b"<WS>") if isinstance(blob, bytes) else blob)
                    for k, (kind, mode, blob) in snapshot.items()}

        reference = normalise(clean, tree(clean))

        for step in steps:
            with self.subTest(step=step):
                ws = Path(tempfile.mkdtemp(prefix="vibe-crash-"))
                self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
                crashed = run_init(ws, "--effort", "medium", "--audit-depth", "mini",
                                   "--strictness", "standard", env={"VIBE_FAIL_AFTER": step})
                self.assertNotEqual(crashed.returncode, 0)
                healed = run_init(ws, "--effort", "medium", "--audit-depth", "mini",
                                  "--strictness", "standard")
                self.assertEqual(healed.returncode, 0,
                                 f"re-run after a crash at {step} did not converge: {healed.stderr}")
                # Converging is not enough: the healed workspace must be the workspace an
                # uninterrupted run produces, or a crash silently changes what gets installed.
                self.assertEqual(normalise(ws, tree(ws)), reference,
                                 f"a crash at {step} healed into a different workspace")
                again = run_init(ws, "--effort", "medium", "--audit-depth", "mini",
                                 "--strictness", "standard")
                self.assertEqual(again.returncode, 0)
                self.assertEqual(normalise(ws, tree(ws)), reference,
                                 f"the third run after {step} diverged")

    def test_history_baseline_is_appended_once_across_runs(self):
        run_init(self.ws, *self.answers())
        run_init(self.ws, *self.answers())
        history = json.loads((self.ws / ".claude" / "vibe-history.json").read_text())
        markers = [s for s in history.get("snapshots", []) if s.get("baseline")]
        self.assertEqual(len(markers), 1, "the baseline snapshot was appended twice")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------------------------
# Regressions. Every case here is a defect review found in a diff whose 19 tests were green, so
# each names what it guards rather than what it exercises.
# ---------------------------------------------------------------------------------------------

class TestRegressions(InitCase):
    def test_a_symlink_at_the_temp_path_cannot_redirect_a_write(self):
        """The destination check was not enough: the temp path is predictable, so a symlink planted
        there was followed and the write landed outside the workspace."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import bridge

        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (self.ws / ".codex").mkdir()
        (self.ws / ".codex" / ".config.toml.vibe-tmp").symlink_to(outside / "pwned")
        with self.assertRaises(bridge.BridgeError):
            bridge.write_atomic(self.ws, self.ws / ".codex" / "config.toml", "owned")
        self.assertFalse((outside / "pwned").exists(), "the write escaped the workspace")

    def test_a_list_shaped_history_is_the_canonical_one(self):
        """nlpm's history is a top-level list (`tests/test_migrate.py:214`); an earlier revision
        assumed a mapping and raised on the exact fixture AC-5 row 3 specifies."""
        (self.ws / ".claude").mkdir()
        (self.ws / ".claude" / "vibe-history.json").write_text(
            json.dumps([{"run": 1, "score": 80}], indent=2) + "\n", encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)
        history = json.loads((self.ws / ".claude" / "vibe-history.json").read_text())
        self.assertIsInstance(history, list, "the existing shape was replaced, not appended to")
        self.assertEqual(len([s for s in history if s.get("baseline")]), 1)
        self.assertIn({"run": 1, "score": 80}, history, "existing entries were discarded")

    def test_an_empty_list_history_is_not_discarded(self):
        (self.ws / ".claude").mkdir()
        (self.ws / ".claude" / "vibe-history.json").write_text("[]\n", encoding="utf-8")
        run_init(self.ws, *self.answers())
        self.assertIsInstance(
            json.loads((self.ws / ".claude" / "vibe-history.json").read_text()), list)

    def test_the_written_config_parses_with_the_canonical_reader(self):
        """`--skip` produced a scalar where the schema wants a sequence, so the advertised answer
        yielded a config `config.py` rejects."""
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import config as config_mod

        result = run_init(self.ws, *self.answers(), "--skip", "vendor/**, build/**")
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = config_mod.parse_frontmatter(
            (self.ws / ".vibe-suite.md").read_text(encoding="utf-8"))
        self.assertIsInstance(parsed.get("skip_patterns"), list)
        self.assertIn("vendor/**", parsed["skip_patterns"])

    def test_a_resumed_run_carrying_decision_flags_is_also_a_no_op(self):
        """AC-2 was proven only on the conflict-free path. A resumed run rewrote its resolution file
        and re-set the store, changing mtimes both times."""
        self.legacy_state(True, "codex-toolkit")
        self.legacy_state(False, "cc-suite-state")
        flags = (*self.answers(), "--resolve-state", "false")
        run_init(self.ws, *flags)
        before, before_mtimes = tree(self.ws), mtimes(self.ws)
        result = run_init(self.ws, *flags)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree(self.ws), before)
        self.assertEqual(mtimes(self.ws), before_mtimes,
                         "a resumed run rewrote identical bytes")

    def test_duplicate_ownership_markers_are_refused_not_half_replaced(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import bridge

        doubled = (bridge.md_block_upsert("", "memory", "one")
                   + bridge.md_block_upsert("", "memory", "two"))
        with self.assertRaises(bridge.BridgeError):
            bridge.md_block_upsert(doubled, "memory", "three")

    def test_an_agent_registered_only_in_toml_is_still_enumerated(self):
        """`list-owned` read `.mcp.json` alone, so an agent living only in TOML was invisible to the
        inventory #21's teardown iterates."""
        (self.ws / ".codex").mkdir()
        (self.ws / ".codex" / "config.toml").write_text(
            '[mcp_servers."vibe-agent:auditor"]\ncommand = "x"\n'
            '[mcp_servers."vibe-agent:auditor".env]\nA = "1"\n'
            '[mcp_servers.unrelated]\ncommand = "y"\n', encoding="utf-8")
        result = run_init(self.ws, *self.answers(), "--list-owned")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("vibe-agent:auditor", result.stdout)
        self.assertNotIn("unrelated", result.stdout)

    def test_a_foreign_file_at_the_provenance_path_is_refused(self):
        (self.ws / ".vibe-suite-state").mkdir()
        (self.ws / ".vibe-suite-state" / "install-provenance.json").write_text(
            '{"schema": 99}\n', encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0,
                            "a non-provenance file at that path was trusted as a restore source")

    def test_provenance_records_a_hash_and_deduplicated_parents(self):
        (self.ws / "AGENTS.md").write_text("mine\n", encoding="utf-8")
        run_init(self.ws, *self.answers())
        record = json.loads(
            (self.ws / ".vibe-suite-state" / "install-provenance.json").read_text())
        agents = [t for t in record["targets"] if t["path"].endswith("AGENTS.md")][0]
        self.assertIn("sha256", agents)
        self.assertEqual(len(record["parents_created"]), len(set(record["parents_created"])))


class TestRound5Regressions(InitCase):
    """Defects introduced or left open by the first fix pass. Each fails against `b2165fa`."""

    def _bridge(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import bridge
        return bridge

    def test_a_rewritten_user_file_keeps_its_mode(self):
        """The temp file was created 0600 and its mode never restored, so every rewritten user file
        silently became owner-only."""
        target = self.ws / "CLAUDE.md"
        target.write_text("mine\n", encoding="utf-8")
        target.chmod(0o644)
        run_init(self.ws, *self.answers())
        self.assertEqual(target.stat().st_mode & 0o777, 0o644,
                         "init changed the file's permissions")

    def test_crlf_line_endings_survive(self):
        """`Path.read_text()` normalises CRLF, so a read-modify-write rewrote every line."""
        target = self.ws / "CLAUDE.md"
        target.write_bytes(b"# Mine\r\n\r\nA CRLF file.\r\n")
        run_init(self.ws, *self.answers())
        self.assertIn(b"A CRLF file.\r\n", target.read_bytes(),
                      "the user's CRLF line endings were normalised to LF")

    def test_a_toml_subtable_is_not_a_registration(self):
        bridge = self._bridge()
        text = ('[mcp_servers."vibe-agent:auditor".env]\nA = "1"\n'
                '[mcp_servers.vibe-mcp.env]\nB = "2"\n')
        self.assertEqual(bridge.toml_owned_names(text), [],
                         "a subtable was read as evidence the server is registered")
        text += '[mcp_servers.vibe-mcp]\ncommand = "x"\n'
        self.assertEqual(bridge.toml_owned_names(text), ["vibe-mcp"])

    def test_an_invalid_effort_value_is_refused_not_written(self):
        """`parse_frontmatter` accepts any scalar; only the validating load rejects an off-enum
        value. An earlier revision wrote `effort: sonnet`, which nothing downstream could read."""
        result = run_init(self.ws, "--effort", "sonnet", "--audit-depth", "mini",
                          "--strictness", "standard")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ws / ".vibe-suite.md").is_file(),
                         "an invalid config was written to disk")

    def test_an_existing_skip_list_is_not_duplicated_on_rerun(self):
        run_init(self.ws, *self.answers(), "--skip", "vendor/**,build/**")
        first = (self.ws / ".vibe-suite.md").read_text(encoding="utf-8")
        run_init(self.ws, *self.answers(), "--skip", "vendor/**,build/**")
        self.assertEqual((self.ws / ".vibe-suite.md").read_text(encoding="utf-8"), first)
        self.assertEqual(first.count("vendor/**"), 1, "the pattern was appended twice")

    def test_a_json_document_of_the_wrong_shape_is_not_silently_replaced(self):
        (self.ws / ".claude").mkdir()
        (self.ws / ".claude" / "vibe-history.json").write_text('"a string"\n', encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.ws / ".claude" / "vibe-history.json").read_text(), '"a string"\n')

    def test_a_symlinked_provenance_path_is_refused(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "p.json").write_text('{"schema": 1, "targets": [], "parents_created": []}\n',
                                        encoding="utf-8")
        (self.ws / ".vibe-suite-state").mkdir()
        (self.ws / ".vibe-suite-state" / "install-provenance.json").symlink_to(outside / "p.json")
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0,
                            "a symlinked provenance path was trusted as a restore source")

    def test_a_provenance_record_missing_targets_is_refused(self):
        (self.ws / ".vibe-suite-state").mkdir()
        (self.ws / ".vibe-suite-state" / "install-provenance.json").write_text(
            '{"schema": 1, "targets": [], "parents_created": []}\n', encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0)


class TestRound6Regressions(InitCase):
    """The ancestor race and the CRLF data-loss path. Each fails against `417f5e2`."""

    def _bridge(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import bridge
        return bridge

    def test_a_symlinked_ancestor_cannot_redirect_a_write(self):
        """`O_NOFOLLOW` on the final component left every ancestor resolved by path. The descent is
        now component-by-component, so a symlink anywhere along the way fails its own step."""
        bridge = self._bridge()
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (outside / "codex").mkdir()
        # `.config` is a symlink; `.config/codex/config.toml` would land outside.
        (self.ws / ".config").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(bridge.BridgeError):
            bridge.write_atomic(self.ws, self.ws / ".config" / "codex" / "config.toml", "owned")
        self.assertFalse((outside / "codex" / "config.toml").exists(),
                         "the write escaped through a symlinked ancestor")

    def test_a_crlf_config_keeps_its_settings(self):
        """`_split_front` recognised only LF, so a CRLF config's frontmatter was read as body and a
        second block was written above it — hiding every existing setting."""
        (self.ws / ".vibe-suite.md").write_bytes(
            b"---\r\nengine: codex\r\nscore_threshold: 90\r\n---\r\n")
        result = run_init(self.ws, *self.answers())
        self.assertEqual(result.returncode, 0, result.stderr)
        raw = (self.ws / ".vibe-suite.md").read_bytes()
        self.assertEqual(raw.count(b"---"), 2, "a second frontmatter block was written")
        import sys
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import config as config_mod
        parsed = config_mod.load(str(self.ws))
        self.assertEqual(parsed["engine"], "codex", "the existing setting was hidden")
        self.assertEqual(parsed["score_threshold"], 90, "an existing value was overwritten")

    def test_a_json_null_history_is_not_treated_as_absent(self):
        (self.ws / ".claude").mkdir()
        (self.ws / ".claude" / "vibe-history.json").write_text("null\n", encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.ws / ".claude" / "vibe-history.json").read_text(), "null\n")

    def test_a_provenance_record_with_duplicate_entries_is_refused(self):
        (self.ws / ".vibe-suite-state").mkdir()
        one = str(self.ws / ".gitignore")
        (self.ws / ".vibe-suite-state" / "install-provenance.json").write_text(
            json.dumps({"schema": 1, "parents_created": [],
                        "targets": [{"path": one, "kind": "absent"}] * 9}) + "\n",
            encoding="utf-8")
        result = run_init(self.ws, *self.answers())
        self.assertNotEqual(result.returncode, 0)

    def test_a_new_file_respects_the_umask(self):
        """A blanket chmod overrode the user's umask policy for files we create ourselves."""
        import subprocess
        script = (f'umask 077; bash {REPO_ROOT / "scripts" / "init.sh"} --workspace {self.ws} '
                  '--effort medium --audit-depth mini --strictness standard')
        subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        mode = (self.ws / ".gitignore").stat().st_mode & 0o777
        self.assertEqual(mode & 0o077, 0, f"umask 077 was overridden: got {oct(mode)}")


class ProvenanceDoesNotPublishSecrets(unittest.TestCase):
    """The record holds complete pre-images — every byte of every file it replaced. A `0600`
    `.mcp.json` with credentials therefore lives inside it, so writing it at the usual `0644`
    published exactly what the user had protected."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-prov-mode-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_the_record_is_no_looser_than_what_it_records(self):
        secrets = self.ws / ".mcp.json"
        secrets.write_text(json.dumps(
            {"mcpServers": {"s": {"command": "x", "env": {"TOKEN": "s3cret-value"}}}}))
        os.chmod(secrets, 0o600)
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

        record_path = self.ws / ".vibe-suite-state" / "install-provenance.json"
        record = json.loads(record_path.read_text())
        carried = [t for t in record["targets"]
                   if t["path"].endswith(".mcp.json") and t.get("content_b64")]
        self.assertTrue(carried, "the fixture does not exercise the leak: no pre-image was recorded")
        self.assertIn("s3cret-value",
                      base64.b64decode(carried[0]["content_b64"]).decode("utf-8"),
                      "the fixture does not exercise the leak: the secret is not in the record")

        mode = stat.S_IMODE(record_path.lstat().st_mode)
        self.assertEqual(mode & 0o077, 0, f"the record is group/world readable at {oct(mode)}")
        dir_mode = stat.S_IMODE((self.ws / ".vibe-suite-state").lstat().st_mode)
        self.assertEqual(dir_mode & 0o077, 0,
                         f"the directory holding it is traversable at {oct(dir_mode)}")


class ConfigValidationDoesNotWidenTheWindow(unittest.TestCase):
    """`_verify_config` swaps a candidate over the real config while the canonical loader validates
    it. Writing that candidate at the default mode and correcting it afterwards leaves a window in
    which a `0600` config is world-readable — and the window *is* the leak."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-cfgwindow-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_a_private_config_keeps_its_mode_through_init(self):
        cfg = self.ws / ".vibe-suite.md"
        cfg.write_text("---\neffort: high\n---\nsomething private\n")
        os.chmod(cfg, 0o600)
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        mode = stat.S_IMODE(cfg.lstat().st_mode)
        self.assertEqual(mode & 0o077, 0, f"a 0600 config ended up at {oct(mode)}")

    def test_validation_writes_nothing_at_all(self):
        """Stronger than the mode check this replaces. `_verify_config` used to stage a candidate
        over the live config and put the original back — every defect it accumulated (a `0600`
        config readable through the window, a mode lost on restore, a fixed scratch path) came from
        that swap. With nothing written there is no window to get wrong."""
        cfg = self.ws / ".vibe-suite.md"
        cfg.write_text("---\neffort: high\n---\nprivate\n")
        os.chmod(cfg, 0o600)
        before = {p.name: (p.read_bytes(), stat.S_IMODE(p.lstat().st_mode))
                  for p in self.ws.iterdir() if p.is_file()}
        init_bridge._verify_config(self.ws, "---\neffort: low\n---\nprivate\n")
        after = {p.name: (p.read_bytes(), stat.S_IMODE(p.lstat().st_mode))
                 for p in self.ws.iterdir() if p.is_file()}
        self.assertEqual(after, before, "validation touched the workspace")

    def test_an_invalid_candidate_is_still_rejected(self):
        """Removing the swap must not remove the validation."""
        with self.assertRaises(bridge.BridgeError):
            init_bridge._verify_config(self.ws, "---\neffort: sonnet\n---\n")
