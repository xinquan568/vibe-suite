#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fixtures for `/vibe-suite:config` (E2.7 / vibe-24).

**Two acceptance clauses, two fixtures.** AC-9(c) is `--show` displaying `cross_model_audit_engine`
and `reviewer_backend`; E2.7's own clause is the gate toggle reaching the E1.6 hook. One test each,
because a single fixture covering both would let either failure hide behind the other.

The three values F1.8 calls out are **corrections to inherited defects** — the gate ships OFF (D3),
the gate model is never a shipped pin (P9), and fail policy defaults open (fixing cc-suite W3's
blocked session end). Each is asserted as a default, not just as a readable value.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "scripts" / "config_cli.py"
HOOK = REPO_ROOT / "scripts" / "stop-review-gate-hook.mjs"


class ConfigCase(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-config-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def run_cli(self, *args):
        return subprocess.run(["python3", str(CLI), "--workspace", str(self.ws), *args],
                              capture_output=True, text=True)

    def show(self, *args):
        r = self.run_cli("--show", "--json", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def stored(self):
        path = self.ws / ".vibe-suite-state" / "state.json"
        return json.loads(path.read_text())["config"]["gate"] if path.is_file() else {}


class TestAC9c(ConfigCase):
    def test_show_displays_the_resolved_engine_defaults(self):
        """AC-9(c) names these two keys specifically."""
        view = self.show()
        self.assertEqual(view["config"]["cross_model_audit_engine"], "codex")
        self.assertEqual(view["config"]["reviewer_backend"], "codex")

    def test_a_configured_engine_overrides_the_default_in_the_view(self):
        (self.ws / ".vibe-suite.md").write_text(
            "---\ncross_model_audit_engine: agy\n---\n", encoding="utf-8")
        self.assertEqual(self.show()["config"]["cross_model_audit_engine"], "agy")


class TestGateRoundTrip(ConfigCase):
    """E2.7's own acceptance clause: the toggle must change what the hook does."""

    def _hook_decision(self):
        """The hook's **decision**, parsed from its stdout — not its combined output.

        Comparing stdout+stderr passed on unrelated diagnostic variation. The hook is a Stop hook
        over a git worktree, so the fixture supplies a real repository, a seeded change, and the
        harness's `hook_event_name`; without those it fails the same way with the gate on or off.
        """
        payload = json.dumps({"cwd": str(self.ws), "hook_event_name": "Stop"})
        env = dict(os.environ, VIBE_SUITE_CODEX_BIN=str(self._reviewer()))
        r = subprocess.run(["node", str(HOOK)], input=payload, capture_output=True, text=True,
                           cwd=str(self.ws), env=env)
        try:
            return json.loads(r.stdout).get("decision", "allow")
        except (json.JSONDecodeError, AttributeError):
            return "allow"

    def _reviewer(self):
        """A reviewer that always blocks, so the comparison is about the *toggle*.

        Without one the test is environment-dependent: where codex exists the gate reaches a verdict
        and blocks; where it does not the gate fails open and both runs allow — which is why this
        passed locally and failed in CI. `VIBE_SUITE_CODEX_BIN` is the seam `tests/node/` already
        uses for exactly this.
        """
        fake = self.ws / "fake-reviewer"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"agent_message\","
            "\"text\":\"BLOCK: seeded defect\"}}'\n"
            "printf '%s\\n' '{\"type\":\"turn.completed\",\"usage\":{}}'\n",
            encoding="utf-8")
        fake.chmod(0o755)
        return fake

    def _seed_repo(self):
        subprocess.run(["git", "init", "-q"], cwd=self.ws, check=True)
        subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=self.ws, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=self.ws, check=True)
        (self.ws / "seed.py").write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=self.ws, check=True)
        subprocess.run(["git", "commit", "-qm", "seed"], cwd=self.ws, check=True)
        (self.ws / "seed.py").write_text("x = 2\n", encoding="utf-8")

    def test_the_gate_ships_off(self):
        self.assertIs(self.show()["gate"]["stop_review_gate"], False)
        self.assertNotIn("stop_review_gate", self.stored(),
                         "shipping OFF must be a default, not a stored value")

    def test_setting_the_toggle_reaches_the_hook(self):
        self._seed_repo()
        before = self._hook_decision()
        self.assertEqual(before, "allow", "the gate should allow while it is off")
        r = self.run_cli("--set", "stop_review_gate=on")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(self.stored().get("stop_review_gate"), True)
        self.assertIs(self.show()["gate"]["stop_review_gate"], True)
        after = self._hook_decision()
        self.assertNotEqual(after, before,
                            f"the hook decided {after!r} both with the gate off and on")

    def test_the_fail_policy_defaults_open(self):
        self.assertEqual(self.show()["gate"]["fail_policy"], "open")
        self.assertNotIn("fail_policy", self.stored())


class TestP9(ConfigCase):
    def test_no_gate_model_ships(self):
        self.assertIsNone(self.show()["gate"].get("model"),
                          "a shipped model default would violate P9")
        self.assertNotIn("model", self.stored(),
                         "P9 is about what ships: the key must be absent, not merely falsy")

    def test_a_user_may_set_a_gate_model(self):
        r = self.run_cli("--set", "gate.model=some-model")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.stored().get("model"), "some-model")


class TestFreshAndInvalid(ConfigCase):
    def test_a_fresh_project_is_a_complete_answer(self):
        r = self.run_cli("--show")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("error", r.stderr.lower())

    def test_an_unknown_key_warning_reaches_the_output(self):
        (self.ws / ".vibe-suite.md").write_text("---\nnot_a_key: 1\n---\n", encoding="utf-8")
        view = self.show()
        self.assertTrue(view["warnings"], "the reader's warning was dropped")

    def test_an_invalid_config_is_reported_not_a_traceback(self):
        (self.ws / ".vibe-suite.md").write_text("---\neffort: sonnet\n---\n", encoding="utf-8")
        r = self.run_cli("--show")
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotEqual(r.returncode, 0)


class TestSetDiscipline(ConfigCase):
    def test_a_key_outside_the_shadowable_set_is_refused(self):
        r = self.run_cli("--set", "effort=high")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.ws / ".vibe-suite.md").exists(),
                         "--set wrote to the config file, which belongs to the user")

    def test_on_and_off_translate_to_the_store_domain(self):
        for word, expected in (("on", True), ("off", False), ("true", True), ("no", False)):
            with self.subTest(word=word):
                self.assertEqual(self.run_cli("--set", f"stop_review_gate={word}").returncode, 0)
                self.assertIs(self.stored()["stop_review_gate"], expected)

    def test_a_value_outside_the_domain_is_refused(self):
        self.assertNotEqual(self.run_cli("--set", "fail_policy=maybe").returncode, 0)

    def test_show_reflects_a_previous_set(self):
        self.run_cli("--set", "fail_policy=closed")
        self.assertEqual(self.show()["gate"]["fail_policy"], "closed")


class TestNamespace(ConfigCase):
    def test_no_retired_command_name_appears_in_output(self):
        combined = self.run_cli("--show").stdout + self.run_cli("--help").stdout
        self.assertNotIn("/vibe:", combined.replace("/vibe-suite:", ""))

    def test_the_command_file_wires_the_helper(self):
        text = (REPO_ROOT / "commands" / "config.md").read_text(encoding="utf-8")
        self.assertIn("scripts/config_cli.py", text)
        self.assertNotIn("/vibe:", text.replace("/vibe-suite:", ""))


if __name__ == "__main__":
    unittest.main()
