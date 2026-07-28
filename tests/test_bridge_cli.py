#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fixtures for `/vibe-suite:bridge` (E2.5 / vibe-22).

The named acceptance clause is the sharp one: *a secret-bearing `.mcp.json` fixture never leaks
values into `config.toml`*. Secrets cross by **allowlist** — every `env` value withheld, variable
names crossing as commented placeholders — rather than by redaction, which would still put the
secret's shape in a second file.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "scripts" / "bridge_cli.py"

SECRET = "sk-live-DO-NOT-COPY-8f3a91"


class BridgeCase(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-bridge-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.plugin = Path(tempfile.mkdtemp(prefix="vibe-plugin-"))
        self.addCleanup(shutil.rmtree, self.plugin, ignore_errors=True)
        (self.plugin / "skills").mkdir()

    def run_bridge(self, *args):
        return subprocess.run(
            ["python3", str(CLI), *args, "--workspace", str(self.ws),
             "--plugin-root", str(self.plugin)], capture_output=True, text=True)

    def toml(self):
        path = self.ws / ".codex" / "config.toml"
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def seed_mcp(self):
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "billing": {"command": "node", "args": ["s.js"],
                        "env": {"BILLING_API_KEY": SECRET, "bearer_token_env_var": "BILLING_API_KEY"}},
        }}, indent=2) + "\n", encoding="utf-8")


class TestSecretsNeverCross(BridgeCase):
    def test_no_env_value_appears_in_the_mirror(self):
        """The named acceptance clause."""
        self.seed_mcp()
        self.assertEqual(self.run_bridge("mcp").returncode, 0)
        self.assertNotIn(SECRET, self.toml(), "a secret value was mirrored into config.toml")
        self.assertNotIn(SECRET, "".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for p in (self.ws / ".codex").rglob("*") if p.is_file()),
            "a secret reached some other file under .codex/")

    def test_the_variable_name_does_cross(self):
        """A name is not a value — that is what makes an allowlist different from a redaction."""
        self.seed_mcp()
        self.run_bridge("mcp")
        self.assertIn("BILLING_API_KEY", self.toml(),
                      "the env variable's name should cross so the user knows to set it")

    def test_the_server_itself_is_mirrored(self):
        self.seed_mcp()
        self.run_bridge("mcp")
        self.assertIn("mcp_servers.billing", self.toml())

    def test_our_own_registration_is_not_mirrored_into_itself(self):
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "vibe-mcp": {"command": "vibe-suite"}}}, indent=2) + "\n", encoding="utf-8")
        self.run_bridge("mcp")
        self.assertNotIn("mcp_servers.vibe-mcp", self.toml(),
                         "the bridge mirrored its own registration")


class TestHooks(BridgeCase):
    def seed_project_hooks(self, extra=None):
        (self.ws / ".claude").mkdir(exist_ok=True)
        hooks = {"PreToolUse": [{"cmd": "a"}], "Stop": [{"cmd": "b"}]}
        hooks.update(extra or {})
        (self.ws / ".claude" / "settings.json").write_text(
            json.dumps({"hooks": hooks}, indent=2) + "\n", encoding="utf-8")

    def written(self):
        path = self.ws / ".codex" / "hooks.json"
        return json.loads(path.read_text()) if path.is_file() else {}

    def test_the_five_shared_events_are_mirrored(self):
        self.seed_project_hooks()
        self.run_bridge("hooks")
        self.assertIn("PreToolUse", self.written()["hooks"])

    def test_a_claude_only_event_is_skipped_and_reported(self):
        self.seed_project_hooks({"Notification": [{"cmd": "x"}]})
        result = self.run_bridge("hooks")
        self.assertNotIn("Notification", self.written().get("hooks", {}))
        self.assertIn("Notification", result.stdout)

    def test_an_owned_entry_is_preserved(self):
        """#18 writes an owned Stop entry into the same file. Mirroring must not drop it."""
        (self.ws / ".codex").mkdir(exist_ok=True)
        (self.ws / ".codex" / "hooks.json").write_text(json.dumps({"hooks": {"Stop": [
            {"type": "command", "command": "vibe-suite stop-gate", "_vibe-suite_owned": 1}]}},
            indent=2) + "\n", encoding="utf-8")
        self.seed_project_hooks()
        self.run_bridge("hooks")
        entries = self.written()["hooks"].get("Stop", [])
        self.assertTrue(any(e.get("_vibe-suite_owned") for e in entries),
                        "the owned Stop entry was dropped")

    def test_a_user_owned_target_gets_a_side_file(self):
        (self.ws / ".codex").mkdir(exist_ok=True)
        mine = {"hooks": {"Stop": [{"cmd": "mine, not yours"}]}}
        (self.ws / ".codex" / "hooks.json").write_text(json.dumps(mine, indent=2) + "\n",
                                                       encoding="utf-8")
        self.seed_project_hooks()
        self.run_bridge("hooks")
        self.assertEqual(json.loads((self.ws / ".codex" / "hooks.json").read_text()), mine,
                         "a user-owned hooks file was overwritten")
        self.assertTrue((self.ws / ".codex" / "hooks.vibe-suite.json").is_file())


class TestSkills(BridgeCase):
    def test_both_links_are_created(self):
        self.run_bridge("skills")
        plugin_link = self.ws / ".claude" / "skills" / "vibe-suite"
        agents_link = self.ws / ".agents" / "skills"
        self.assertTrue(plugin_link.is_symlink())
        self.assertEqual(os.readlink(agents_link), "../.claude/skills")

    def test_the_plugin_link_leaves_the_project_by_design(self):
        self.run_bridge("skills")
        target = os.readlink(self.ws / ".claude" / "skills" / "vibe-suite")
        self.assertTrue(target.startswith(str(self.plugin)),
                        "the plugin-skills link must point into the installed plugin")

    def test_a_real_directory_is_left_alone(self):
        (self.ws / ".agents").mkdir()
        (self.ws / ".agents" / "skills").mkdir()
        (self.ws / ".agents" / "skills" / "mine.md").write_text("x\n", encoding="utf-8")
        self.run_bridge("skills")
        self.assertTrue((self.ws / ".agents" / "skills" / "mine.md").is_file())

    def test_a_correct_link_that_already_exists_is_accepted(self):
        self.run_bridge("skills")
        result = self.run_bridge("skills")
        self.assertEqual(result.returncode, 0)
        self.assertIn("already correct", result.stdout)


class TestSubcommands(BridgeCase):
    def test_mirrors_says_it_is_not_available(self):
        result = self.run_bridge("mirrors")
        self.assertEqual(result.returncode, 0)
        self.assertIn("S7", result.stdout, "a silent no-op would read as success")

    def test_all_runs_the_three_implementable_ones(self):
        self.seed_mcp()
        out = self.run_bridge("all").stdout
        for prefix in ("skills:", "hooks:", "mcp:", "mirrors:"):
            self.assertIn(prefix, out)

    def test_each_subcommand_is_idempotent(self):
        self.seed_mcp()
        for sub in ("skills", "hooks", "mcp"):
            with self.subTest(sub=sub):
                self.run_bridge(sub)
                before = {p: p.read_bytes() for p in self.ws.rglob("*") if p.is_file()}
                self.assertEqual(self.run_bridge(sub).returncode, 0)
                after = {p: p.read_bytes() for p in self.ws.rglob("*") if p.is_file()}
                self.assertEqual(after, before, f"{sub} was not idempotent")


class TestNamespace(BridgeCase):
    def test_no_retired_name_in_output_or_command(self):
        out = self.run_bridge("all").stdout
        text = (REPO_ROOT / "commands" / "bridge.md").read_text(encoding="utf-8")
        for body in (out, text):
            self.assertNotIn("/vibe:", body.replace("/vibe-suite:", ""))
        self.assertIn("scripts/bridge_cli.py", text)


if __name__ == "__main__":
    unittest.main()
