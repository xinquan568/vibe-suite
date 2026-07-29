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
import sys
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import bridge  # noqa: E402

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
                        # `bearer_token_env_var` names a *different* variable. Naming BILLING_API_KEY
                        # here would make it a value as well as a key, and values are poisoned — the
                        # fixture would then be asserting two incompatible things at once.
                        "env": {"BILLING_API_KEY": SECRET, "bearer_token_env_var": "OTHER_VAR"}},
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


class TestBlockerRegressions(BridgeCase):
    """Each reproduced against `3be00fd`."""

    def test_a_secret_repeated_in_args_does_not_cross(self):
        """Withholding `env` was not enough — the same value routinely appears in `args` too, and a
        leak through a second field is the same leak."""
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {"x": {
            "command": "run", "args": ["--key", SECRET], "env": {"K": SECRET}}}},
            indent=2) + "\n", encoding="utf-8")
        self.run_bridge("mcp")
        self.assertNotIn(SECRET, self.toml(), "the secret crossed through args")

    def test_a_secret_nested_in_env_is_collected(self):
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {"x": {
            "command": SECRET, "env": {"outer": {"inner": SECRET}}}}},
            indent=2) + "\n", encoding="utf-8")
        self.run_bridge("mcp")
        self.assertNotIn(SECRET, self.toml())

    def test_a_crafted_server_name_cannot_close_the_sentinel(self):
        hostile = 'evil"]\n# <<< vibe-suite:mcp-mirror <<<\nescaped = 1\n[mcp_servers.x'
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {hostile: {"command": "c"}}},
                                                      indent=2) + "\n", encoding="utf-8")
        self.run_bridge("mcp")
        text = self.toml()
        # The marker text may appear *inside* the quoted key — escaped, and therefore inert. What
        # must not happen is a second marker at the start of a line, which would end the block early
        # and leave the rest outside our ownership.
        closers = [ln for ln in text.splitlines() if ln.startswith("# <<< vibe-suite:mcp-mirror")]
        self.assertEqual(len(closers), 1, "a crafted name injected a real closing marker")
        self.assertNotIn("\nescaped = 1", text)

    def test_hooks_are_idempotent_and_do_not_fall_back_on_a_rerun(self):
        """Mirrored entries were unmarked, so the second run read its own output as user content."""
        self.seed_project_hooks() if hasattr(self, "seed_project_hooks") else None
        (self.ws / ".claude").mkdir(exist_ok=True)
        (self.ws / ".claude" / "settings.json").write_text(
            json.dumps({"hooks": {"PreToolUse": [{"cmd": "a"}]}}, indent=2) + "\n",
            encoding="utf-8")
        self.run_bridge("hooks")
        first = (self.ws / ".codex" / "hooks.json").read_bytes()
        self.run_bridge("hooks")
        self.assertFalse((self.ws / ".codex" / "hooks.vibe-suite.json").exists(),
                         "a second run fell back to a side file it did not need")
        self.assertEqual((self.ws / ".codex" / "hooks.json").read_bytes(), first)

    def test_a_wrong_skills_link_is_refused_not_deleted(self):
        (self.ws / ".agents").mkdir()
        (self.ws / "elsewhere").mkdir()
        (self.ws / ".agents" / "skills").symlink_to(self.ws / "elsewhere")
        result = self.run_bridge("skills")
        self.assertTrue((self.ws / ".agents" / "skills").is_symlink())
        self.assertEqual(os.readlink(self.ws / ".agents" / "skills"), str(self.ws / "elsewhere"),
                         "a link the user pointed elsewhere was replaced")
        self.assertIn("refused", result.stdout)

    def test_a_foreign_top_level_key_in_hooks_json_survives(self):
        (self.ws / ".codex").mkdir(exist_ok=True)
        (self.ws / ".codex" / "hooks.json").write_text(
            json.dumps({"hooks": {}, "somethingElse": {"keep": True}}, indent=2) + "\n",
            encoding="utf-8")
        (self.ws / ".claude").mkdir(exist_ok=True)
        (self.ws / ".claude" / "settings.json").write_text(
            json.dumps({"hooks": {"Stop": [{"cmd": "a"}]}}, indent=2) + "\n", encoding="utf-8")
        self.run_bridge("hooks")
        after = json.loads((self.ws / ".codex" / "hooks.json").read_text())
        self.assertEqual(after.get("somethingElse"), {"keep": True})


class TestIteration2(BridgeCase):
    """The deeper instances iteration 1 named. Each fails against `fd6402b`."""

    def _mcp(self, spec):
        (self.ws / ".mcp.json").write_text(
            json.dumps({"mcpServers": spec}, indent=2) + "\n", encoding="utf-8")

    def test_a_secret_embedded_in_a_larger_arg_does_not_cross(self):
        """Equality is not enough: `--key=sk-...` is not equal to `sk-...` but is the same leak."""
        self._mcp({"x": {"command": "run", "args": ["--key=" + SECRET], "env": {"K": SECRET}}})
        self.run_bridge("mcp")
        self.assertNotIn(SECRET, self.toml())

    def test_a_numeric_env_value_is_poisoned_too(self):
        token = "9182736455647382"
        self._mcp({"x": {"command": "run", "args": [token], "env": {"PIN": int(token)}}})
        self.run_bridge("mcp")
        self.assertNotIn(token, self.toml())

    def test_a_server_whose_name_repeats_a_secret_is_skipped_entirely(self):
        """The name is the one field that cannot be omitted, so the server must be."""
        self._mcp({"srv-" + SECRET: {"command": "run", "env": {"K": SECRET}}})
        self.run_bridge("mcp")
        self.assertNotIn(SECRET, self.toml())

    def test_a_list_shaped_env_does_not_crash_and_does_not_leak(self):
        self._mcp({"x": {"command": "run", "args": [SECRET], "env": [SECRET]}})
        self.assertEqual(self.run_bridge("mcp").returncode, 0)
        self.assertNotIn(SECRET, self.toml())

    def test_declaring_env_reduces_a_server_to_names(self):
        """The structural rule that replaced value recognition: a server declaring env contributes
        its name and its variable names, and nothing else. No length threshold is involved, so a
        two-character credential is as safe as a long one."""
        self._mcp({"x": {"command": "run", "args": ["--flag"], "env": {"N": "on"}}})
        self.run_bridge("mcp")
        text = self.toml()
        self.assertIn("mcp_servers.x", text)
        self.assertIn("# env: N", text)
        self.assertNotIn("--flag", text, "a value crossed from a server that declares env")
        self.assertNotIn("command =", text)

    def test_a_server_without_env_is_mirrored_in_full(self):
        """The rule keys on declaring env, not on guessing — so a server with no secrets to hold is
        mirrored completely."""
        self._mcp({"plain": {"command": "node", "args": ["server.js"]}})
        self.run_bridge("mcp")
        text = self.toml()
        self.assertIn('command = "node"', text)
        self.assertIn("server.js", text)

    def test_an_env_name_still_crosses(self):
        """F1.6 specifies it: the user has to know what to set."""
        self._mcp({"x": {"command": "run", "env": {"BILLING_API_KEY": SECRET}}})
        self.run_bridge("mcp")
        self.assertIn("BILLING_API_KEY", self.toml())
        self.assertNotIn(SECRET, self.toml())

    def test_the_side_file_is_removed_when_the_fallback_ends(self):
        (self.ws / ".codex").mkdir(exist_ok=True)
        (self.ws / ".claude").mkdir(exist_ok=True)
        (self.ws / ".claude" / "settings.json").write_text(
            json.dumps({"hooks": {"Stop": [{"cmd": "a"}]}}, indent=2) + "\n", encoding="utf-8")
        (self.ws / ".codex" / "hooks.json").write_text(
            json.dumps({"hooks": {"Stop": [{"cmd": "mine"}]}}, indent=2) + "\n", encoding="utf-8")
        self.run_bridge("hooks")
        side = self.ws / ".codex" / "hooks.vibe-suite.json"
        self.assertTrue(side.is_file(), "no side file was written for a user-owned target")
        (self.ws / ".codex" / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
        self.run_bridge("hooks")
        self.assertFalse(side.exists(),
                         "a stale side file was left beside a live mirror, with nothing saying "
                         "which one is authoritative")

    def test_a_symlinked_ancestor_refuses_the_skills_link(self):
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (self.ws / ".claude").symlink_to(outside, target_is_directory=True)
        result = self.run_bridge("skills")
        self.assertFalse((outside / "skills").exists(),
                         "a link was created through a symlinked ancestor")
        self.assertIn("refused", result.stdout)


class WriteAtomicRefusesSymlinks(unittest.TestCase):
    """`classify()` has always returned "symlink"; `write_atomic` acted only on "dir" and "other",
    so `os.replace` converted a user's link into a regular file. The bytes at the far end survive,
    but the link does not — and teardown records `kind: symlink` while never restoring one, so the
    conversion is permanent."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-wa-symlink-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_a_symlinked_destination_is_refused(self):
        target = self.ws / "theirs.txt"
        target.write_text("user data")
        link = self.ws / "CLAUDE.md"
        link.symlink_to(target)
        with self.assertRaises(bridge.BridgeError):
            bridge.write_atomic(self.ws, link, "ours\n")
        self.assertTrue(link.is_symlink(), "the user's link was converted to a regular file")
        self.assertEqual(os.readlink(link), str(target))
        self.assertEqual(target.read_text(), "user data")

    def test_a_dangling_symlink_is_refused_too(self):
        """`exists()` follows the link, so a dangling one reports False — the case every
        "is it already there?" guard waves through."""
        link = self.ws / "GEMINI.md"
        link.symlink_to(self.ws / "never-existed.txt")
        with self.assertRaises(bridge.BridgeError):
            bridge.write_atomic(self.ws, link, "ours\n")
        self.assertTrue(link.is_symlink())

    def test_a_regular_destination_is_still_written(self):
        plain = self.ws / "AGENTS.md"
        plain.write_text("before")
        bridge.write_atomic(self.ws, plain, "after\n")
        self.assertEqual(plain.read_text(), "after\n")
        self.assertFalse(plain.is_symlink())

    def test_a_fresh_destination_is_still_created(self):
        fresh = self.ws / "new.md"
        bridge.write_atomic(self.ws, fresh, "made\n")
        self.assertEqual(fresh.read_text(), "made\n")
