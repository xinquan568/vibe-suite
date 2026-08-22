#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Tests for the workspace runtime-toggle store (E0.5 / vibe-7).

The store's **on-disk representation is the contract**, not merely its API. An earlier draft asserted
only through getters, which an in-memory registry — or one writing a differently named file —
satisfies completely. Every assertion below that matters opens `state.json` and reads it as JSON.

`.vibe-suite.md` is human-edited project configuration; this store is machine-managed runtime state,
resolved once per workspace. Where both name a setting the store wins for the session, and only the
three `gate.*` keys may be shadowed at all.
"""

import importlib.util
import json
import stat
import shutil
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import bridge  # noqa: E402
STORE_PY = REPO_ROOT / "scripts" / "lib" / "store.py"


def _load(path, name):
    if not path.exists():
        raise AssertionError(f"not found: {path.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


store = _load(STORE_PY, "vibe_store")

FRESH_DEFAULTS = {"stop_review_gate": False, "fail_policy": "open"}
SHADOWABLE = ("gate.stop_review_gate", "gate.model", "gate.fail_policy")


class TestOnDiskLayout(unittest.TestCase):
    """The layout is the contract. These assertions are what an in-memory store cannot pass."""

    def test_settings_live_under_a_top_level_config_member_of_state_json(self):
        with tempfile.TemporaryDirectory() as ws:
            store.Store(ws).set("gate.stop_review_gate", True)
            raw = json.loads(store.state_path(ws).read_text(encoding="utf-8"))
            self.assertIn("config", raw, "settings must sit under state.json's `config` member")
            self.assertIs(raw["config"]["gate"]["stop_review_gate"], True)

    def test_the_state_file_is_at_the_documented_path(self):
        # Constructed here, not taken from store.state_path — trusting the module's own answer
        # would let any workspace-relative file named state.json satisfy this.
        with tempfile.TemporaryDirectory() as ws:
            store.Store(ws).set("gate.fail_policy", "closed")
            expected = Path(ws) / ".vibe-suite-state" / "state.json"
            self.assertTrue(expected.exists(), f"expected state at {expected}")

    def test_every_unset_shadowable_key_is_absent(self):
        # Each key is written in turn and the *other two* asserted absent, so no key's absence goes
        # untested. Writing only stop_review_gate would never exercise its own absence.
        keys = {"stop_review_gate": True, "model": "some-model", "fail_policy": "closed"}
        for written, value in keys.items():
            with self.subTest(written=written):
                with tempfile.TemporaryDirectory() as ws:
                    store.Store(ws).set(f"gate.{written}", value)
                    gate = json.loads(
                        store.state_path(ws).read_text(encoding="utf-8"))["config"]["gate"]
                    self.assertIn(written, gate)
                    for other in keys:
                        if other != written:
                            self.assertNotIn(other, gate, f"{other} must be absent, not null")

    def test_an_unset_key_is_absent_from_the_json_not_null(self):
        with tempfile.TemporaryDirectory() as ws:
            store.Store(ws).set("gate.stop_review_gate", True)
            gate = json.loads(store.state_path(ws).read_text(encoding="utf-8"))["config"]["gate"]
            self.assertNotIn("model", gate, "an unset dynamic model must be absent, never null")

    def test_a_write_preserves_unrelated_sibling_members(self):
        with tempfile.TemporaryDirectory() as ws:
            path = store.state_path(ws)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                "jobs": {"j1": {"status": "done"}},
                "config": {"other_section": {"keep": 1}, "gate": {"model": "preset"}},
            }), encoding="utf-8")
            store.Store(ws).set("gate.stop_review_gate", True)
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["jobs"], {"j1": {"status": "done"}}, "top-level sibling clobbered")
            self.assertEqual(raw["config"]["other_section"], {"keep": 1}, "config sibling clobbered")
            self.assertEqual(raw["config"]["gate"]["model"], "preset", "gate sibling clobbered")

    def test_values_survive_a_fresh_process(self):
        with tempfile.TemporaryDirectory() as ws:
            store.Store(ws).set("gate.fail_policy", "closed")
            code = (f"import importlib.util,sys;"
                    f"s=importlib.util.spec_from_file_location('s',r'{STORE_PY}');"
                    f"m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
                    f"print(m.Store(r'{ws}').get('gate.fail_policy'))")
            result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
            self.assertEqual(result.stdout.strip(), "closed", result.stderr)


class TestDamagedState(unittest.TestCase):
    """A state file we cannot read is a state file we must not overwrite."""

    def test_malformed_json_raises_rather_than_being_overwritten(self):
        with tempfile.TemporaryDirectory() as ws:
            path = store.state_path(ws)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"jobs": {"j1": "important"}, TRUNCATED', encoding="utf-8")
            with self.assertRaises(store.StoreFormatError):
                store.Store(ws).set("gate.stop_review_gate", True)
            self.assertIn("important", path.read_text(encoding="utf-8"),
                          "job records must survive a refused write")

    def test_a_hand_edited_invalid_override_is_rejected_on_read(self):
        # set() validates; a file edited by hand does not go through set().
        with tempfile.TemporaryDirectory() as ws:
            path = store.state_path(ws)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"config": {"gate": {"fail_policy": "sideways"}}}),
                            encoding="utf-8")
            with self.assertRaises(store.StoreValueError):
                store.Store(ws).overrides()

    def test_an_unknown_persisted_key_is_rejected_on_read(self):
        with tempfile.TemporaryDirectory() as ws:
            path = store.state_path(ws)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"config": {"gate": {"nonsense": True}}}), encoding="utf-8")
            with self.assertRaises(store.StoreKeyError):
                store.Store(ws).overrides()


class TestDefaultsAndIsolation(unittest.TestCase):
    def test_fresh_defaults(self):
        with tempfile.TemporaryDirectory() as ws:
            fresh = store.Store(ws)
            self.assertIs(fresh.get("gate.stop_review_gate"), False, "the gate ships OFF")
            self.assertEqual(fresh.get("gate.fail_policy"), "open", "fail-open by default")
            self.assertIsNone(fresh.get("gate.model"), "the gate model is dynamic, never pinned")

    def test_workspaces_are_isolated(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            store.Store(a).set("gate.stop_review_gate", True)
            self.assertIs(store.Store(b).get("gate.stop_review_gate"), False)


class TestValidationAndShadowing(unittest.TestCase):
    def test_only_the_three_gate_keys_are_shadowable(self):
        with tempfile.TemporaryDirectory() as ws:
            valid = {"gate.stop_review_gate": True, "gate.model": "some-model",
                     "gate.fail_policy": "open"}
            for key in SHADOWABLE:
                with self.subTest(key=key):
                    store.Store(ws).set(key, valid[key])

    def test_every_other_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as ws:
            for key in ("engine", "score_threshold", "skip_patterns", "gate.nonsense"):
                with self.subTest(key=key):
                    with self.assertRaises(store.StoreKeyError):
                        store.Store(ws).set(key, "x")

    def test_values_are_validated(self):
        with tempfile.TemporaryDirectory() as ws:
            with self.assertRaises(store.StoreValueError):
                store.Store(ws).set("gate.fail_policy", "sideways")


class TestEffectiveConfig(unittest.TestCase):
    """Runtime state wins for the session; the file is never rewritten."""

    def _project(self, root, frontmatter):
        (Path(root) / ".vibe-suite.md").write_text(f"---\n{frontmatter}---\n", encoding="utf-8")

    def test_runtime_state_overrides_the_file(self):
        with tempfile.TemporaryDirectory() as ws:
            self._project(ws, "gate:\n  fail_policy: closed\n")
            self.assertEqual(store.effective_config(ws)["gate"]["fail_policy"], "closed")
            store.Store(ws).set("gate.fail_policy", "open")
            self.assertEqual(store.effective_config(ws)["gate"]["fail_policy"], "open")

    def test_the_file_supplies_values_the_store_has_not_set(self):
        with tempfile.TemporaryDirectory() as ws:
            self._project(ws, "engine: codex\nscore_threshold: 55\n")
            effective = store.effective_config(ws)
            self.assertEqual(effective["engine"], "codex")
            self.assertEqual(effective["score_threshold"], 55)

    def test_a_live_gate_write_leaves_the_config_file_byte_identical(self):
        # The gate block in `.vibe-suite.md` is defaults-and-display only; the store owns live
        # values. This replaces an earlier unfalsifiable "read but never written".
        with tempfile.TemporaryDirectory() as ws:
            self._project(ws, "gate:\n  fail_policy: closed\n")
            path = Path(ws) / ".vibe-suite.md"
            before = path.read_bytes()
            store.Store(ws).set("gate.fail_policy", "open")
            self.assertEqual(path.read_bytes(), before, "the store must not write project config")

    # vibe-183 / grill H5: the project file is not the store. A broken `.vibe-suite.md` must not erase
    # the stored gate — the setting the issue calls "when in doubt, block". The store is read FIRST; a
    # project-file failure of any of config.py's three classes degrades to `{gate, config_error}`.
    BROKEN_PROJECT_FILES = {
        "syntax":      ("---\ngate:\n  fail_policy: open\n", "frontmatter"),                 # never closes
        "value":       ("---\nengine: bogus\n---\n", "engine: expected one of"),               # ConfigValueError
        "containment": ("---\nrule_overrides:\n  R51:\n    vocabulary_skill: ../../outside\n---\n",
                        "resolves outside the project root"),                                  # ConfigContainmentError
    }

    def test_a_broken_project_file_of_every_class_still_yields_the_stored_gate_and_names_the_error(self):
        for kind, (text, expected) in self.BROKEN_PROJECT_FILES.items():
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as ws:
                (Path(ws) / ".vibe-suite.md").write_text(text, encoding="utf-8")
                store.Store(ws).set("gate.fail_policy", "closed")
                effective = store.effective_config(ws)
                self.assertEqual(effective["gate"]["fail_policy"], "closed", "the stored policy survives the typo")
                self.assertEqual(effective["gate"]["stop_review_gate"], False, "FRESH defaults still apply")
                self.assertTrue(effective["config_error"].startswith("config: "), effective["config_error"])
                self.assertIn(expected, effective["config_error"], "the real cause is named")
                self.assertNotIn("engine", effective, "nothing but the gate can be resolved without the file")

    def test_a_valid_project_file_carries_no_config_error(self):
        with tempfile.TemporaryDirectory() as ws:
            self._project(ws, "engine: codex\n")
            self.assertNotIn("config_error", store.effective_config(ws))

    def test_effective_config_cli_exits_zero_on_a_broken_project_file_and_warns(self):
        with tempfile.TemporaryDirectory() as ws:
            (Path(ws) / ".vibe-suite.md").write_text("---\ngate:\n  fail_policy: open\n", encoding="utf-8")
            store.Store(ws).set("gate.fail_policy", "closed")
            result = subprocess.run([sys.executable, str(STORE_PY), "effective-config", ws],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            document = json.loads(result.stdout)
            self.assertEqual(document["gate"]["fail_policy"], "closed")
            self.assertIn("config_error", document)
            self.assertIn("store: config:", result.stderr, "the cause goes to stderr in the store's voice")
            self.assertIn("gate resolved from runtime state and defaults", result.stderr)

    def test_a_damaged_state_file_is_refused_first_even_when_the_project_file_is_also_broken(self):
        # The store is read BEFORE the project file (the issue's ordering): damage to the STATE file keeps
        # its exit-1 precedence — it is never masked by, or degraded alongside, a project-file error.
        with tempfile.TemporaryDirectory() as ws:
            (Path(ws) / ".vibe-suite.md").write_text("---\ngate:\n  fail_policy: open\n", encoding="utf-8")
            state_dir = Path(ws) / ".vibe-suite-state"
            state_dir.mkdir()
            (state_dir / "state.json").write_text("not json at all", encoding="utf-8")
            with self.assertRaises(store.StoreFormatError):
                store.effective_config(ws)
            result = subprocess.run([sys.executable, str(STORE_PY), "effective-config", ws],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, "a damaged STORE is still refused — that contract is unchanged")
            self.assertIn("store:", result.stderr)
            self.assertIn("refusing to overwrite", result.stderr)
            self.assertNotIn("config:", result.stderr, "the project-file error never gets a turn when the store is damaged")
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()


class SetGoesThroughTheAuditedPrimitive(unittest.TestCase):
    """`Store.set` hand-rolled tmp-and-rename: a **fixed** scratch name the user may own, no symlink
    check on the destination, and an existing `0600` file republished at the default mode."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-store-write-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.state_dir = self.ws / ".vibe-suite-state"
        self.state_dir.mkdir(parents=True)
        self.path = self.state_dir / "state.json"

    def store(self):
        return store.Store(self.ws)

    def test_a_symlinked_state_file_is_refused_not_replaced(self):
        target = self.ws / "theirs.json"
        target.write_text("{}")
        self.path.symlink_to(target)
        with self.assertRaises(bridge.BridgeError):
            self.store().set("gate.stop_review_gate", True)
        self.assertTrue(self.path.is_symlink(), "the user's link was replaced by a regular file")

    def test_a_users_file_at_the_scratch_path_survives(self):
        """The old code wrote `state.json.tmp` unconditionally."""
        scratch = self.state_dir / "state.json.tmp"
        scratch.write_text("something of mine")
        self.store().set("gate.stop_review_gate", True)
        self.assertTrue(scratch.is_file(), "a user's file at the scratch path was destroyed")
        self.assertEqual(scratch.read_text(), "something of mine")

    def test_a_fresh_state_file_is_not_world_readable(self):
        """State records can hold private content, so a fresh one is created 0600."""
        self.store().set("gate.stop_review_gate", True)
        mode = stat.S_IMODE(self.path.lstat().st_mode)
        self.assertEqual(mode & 0o077, 0, f"fresh state file is group/world readable at {oct(mode)}")

    def test_an_existing_files_mode_is_preserved(self):
        self.path.write_text("{}")
        os.chmod(self.path, 0o600)
        self.store().set("gate.stop_review_gate", True)
        self.assertEqual(stat.S_IMODE(self.path.lstat().st_mode), 0o600)
