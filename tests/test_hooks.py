#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Hook registration and the store CLI (E1.6 / vibe-16).

The registration is the settings-shaped nested schema Claude Code actually loads — event ->
matcher-group list -> `hooks` list of `{type: "command", command, timeout?}` — not the flat array
an older helper used. A hook registered in the wrong shape is a hook that never runs, which is the
worst kind of gate: one that looks installed.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
PLUGIN_MANIFEST = REPO_ROOT / ".claude-plugin" / "plugin.json"
STORE = REPO_ROOT / "scripts" / "lib" / "store.py"

EVENTS = ["Stop", "SessionStart", "SessionEnd", "PostToolUse"]


class TestHookRegistration(unittest.TestCase):
    def setUp(self):
        self.assertTrue(HOOKS_JSON.is_file(), "hooks/hooks.json is missing")
        self.manifest = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))

    def test_plugin_manifest_points_at_the_hook_file(self):
        plugin = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(plugin.get("hooks"), "./hooks/hooks.json")

    def test_nested_settings_shape_with_exactly_the_four_events(self):
        hooks = self.manifest.get("hooks")
        self.assertIsInstance(hooks, dict, "the top level must be a nested `hooks` object")
        self.assertEqual(sorted(hooks), sorted(EVENTS))
        for event in EVENTS:
            groups = hooks[event]
            self.assertIsInstance(groups, list, f"{event}: expected a matcher-group list")
            self.assertTrue(groups, f"{event}: no groups")
            for group in groups:
                handlers = group.get("hooks")
                self.assertIsInstance(handlers, list, f"{event}: group has no hooks list")
                for handler in handlers:
                    self.assertEqual(handler.get("type"), "command", f"{event}: handler type")
                    self.assertIn("${CLAUDE_PLUGIN_ROOT}", handler.get("command", ""))

    def test_post_tool_use_maps_to_the_advisory_hook(self):
        # F9.7 fixes the matcher verbatim; conventions-claude records MultiEdit as removed,
        # but an alternation branch that never matches is inert and dropping it would
        # deviate from the governing spec
        groups = self.manifest["hooks"]["PostToolUse"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].get("matcher"), "Write|Edit|MultiEdit")
        handlers = groups[0]["hooks"]
        self.assertEqual(len(handlers), 1)
        self.assertIn("check-artifact.sh", handlers[0]["command"])
        self.assertEqual(handlers[0].get("timeout"), 5)

    def _commands(self, event):
        return [h["command"] for g in self.manifest["hooks"][event] for h in g["hooks"]]

    def test_stop_maps_to_the_gate_script_with_a_900_second_timeout(self):
        handlers = [h for g in self.manifest["hooks"]["Stop"] for h in g["hooks"]]
        self.assertEqual(len(handlers), 1)
        self.assertIn("stop-review-gate-hook.mjs", handlers[0]["command"])
        self.assertEqual(handlers[0].get("timeout"), 900)

    def test_lifecycle_events_map_to_their_own_event_argument(self):
        for event, expected in (("SessionStart", "--event start"), ("SessionEnd", "--event end")):
            commands = self._commands(event)
            self.assertEqual(len(commands), 1, event)
            self.assertIn("session-lifecycle-hook.mjs", commands[0], event)
            self.assertTrue(commands[0].strip().endswith(expected),
                            f"{event}: expected the command to end with `{expected}`, got {commands[0]}")

    def test_every_referenced_script_exists(self):
        for event in EVENTS:
            for command in self._commands(event):
                marker = "${CLAUDE_PLUGIN_ROOT}/"
                tail = command.split(marker, 1)[1]
                relative = tail.split('"', 1)[0].split()[0]
                self.assertTrue((REPO_ROOT / relative).is_file(),
                                f"{event}: {relative} does not exist")


class TestStoreCli(unittest.TestCase):
    def _run(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(STORE), *args],
                              capture_output=True, text=True, timeout=60, cwd=cwd)

    def test_effective_config_prints_json_and_exits_zero(self):
        import tempfile
        with tempfile.TemporaryDirectory() as workspace:
            result = self._run("effective-config", workspace)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIs(payload["gate"]["stop_review_gate"], False,
                          "the gate ships disabled (D3)")
            self.assertEqual(payload["gate"]["fail_policy"], "open")

    def test_damaged_state_refuses_with_exit_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as workspace:
            state = Path(workspace) / ".vibe-suite-state"
            state.mkdir()
            (state / "state.json").write_text("not json", encoding="utf-8")
            result = self._run("effective-config", workspace)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("refusing to overwrite", result.stderr)

    def test_usage_error_exits_two_and_there_is_no_write_subcommand(self):
        self.assertEqual(self._run("bogus").returncode, 2)
        self.assertEqual(self._run("set", "gate.stop_review_gate", "true").returncode, 2,
                         "writes belong to /vibe-suite:config (E1.8), not to this bridge")


if __name__ == "__main__":
    unittest.main()
