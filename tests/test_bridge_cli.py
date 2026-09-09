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
import re
import shutil
import subprocess
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path
from unittest import mock

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

    def seed_mirror_driver(self):
        """E7.2 fixture seam: the fixture's own copy of mirror-sync.py is a tiny driver —
        the production CLI surface stays un-overridable."""
        driver = self.plugin / "scripts" / "mirror-sync.py"
        driver.parent.mkdir(parents=True, exist_ok=True)
        driver.write_text(
            "#!/usr/bin/env python3\n# SPDX-License-Identifier: ISC\n"
            "import pathlib, sys\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('--root') + 1])\n"
            "d = root / 'codex'\n"
            "d.mkdir(exist_ok=True)\n"
            "(d / 'MIRROR-MANIFEST.json').write_text('{}')\n"
            "print('driver ok')\n")

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

    def test_the_command_does_not_claim_init_writes_the_owned_stop_entry(self):
        # grill S4 (vibe-191): no owned Stop hook is written until the binary ships; an older
        # init's bare `vibe-suite stop-gate` is dangling and repair removes it — the doc says so
        text = (REPO_ROOT / "commands" / "bridge.md").read_text(encoding="utf-8")
        self.assertNotIn("written by `/vibe-suite:init`", text)
        self.assertIn("none is written until the `vibe-suite` binary ships", text)
        self.assertIn("dangling", text)
        self.assertIn("/vibe-suite:repair", text)

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
    def test_mirrors_without_a_generator_fails_loudly(self):
        # E7.2 premise change: the mirrors leg is live. A plugin missing its generator is a
        # broken installation, and silence would read as success — the failure is loud.
        result = self.run_bridge("mirrors")
        self.assertEqual(result.returncode, 1)
        self.assertIn("generator not found", result.stdout + result.stderr)

    def test_all_runs_all_four_legs(self):
        self.seed_mcp()
        self.seed_mirror_driver()
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

    def seed_mcp_with_env_name(self, var):
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "billing": {"command": "node", "args": ["s.js"], "env": {var: SECRET, "OK_NAME": "x"}},
            "plain": {"command": "c"}}}, indent=2) + "\n", encoding="utf-8")

    def test_an_env_variable_name_that_is_not_a_name_is_refused_and_the_block_is_unchanged(self):
        # grill S5 (vibe-192): the placeholder is a `#` comment line — a "name" with a newline would
        # end the comment and put live TOML (a forged closing marker, a key) inside the owned block.
        # Such a name is refused BY NAME before anything is written; the file stays byte-identical.
        self.seed_mcp()
        self.assertEqual(self.run_bridge("mcp").returncode, 0)          # a clean mirror first
        before = (self.ws / ".codex" / "config.toml").read_bytes()
        for hostile in ('EVIL\n# <<< vibe-suite:mcp-mirror <<<\nescaped = 1\n[mcp_servers.x',
                        "A\nB", "WITH#HASH", "BRACKET[", "HAS SPACE", "DASH-NAME", "quote\"d", "",
                        "ünïcode", "TRAIL\r\n"):
            with self.subTest(name=hostile):
                self.seed_mcp_with_env_name(hostile)
                result = self.run_bridge("mcp")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("mcp: refused", result.stderr)
                self.assertIn("billing", result.stderr, "the refusal names the server")
                self.assertIn("[A-Za-z0-9_]", result.stderr, "the refusal names the rule")
                self.assertIn(repr(hostile), result.stderr, "the refusal names the variable, repr-escaped")
                self.assertEqual(result.stderr.strip().count("\n"), 0, "one refusal line on stderr: " + result.stderr)
                self.assertNotIn("\nescaped = 1", result.stderr, "the hostile text is shown escaped, never raw")
                text = (self.ws / ".codex" / "config.toml").read_bytes()
                self.assertEqual(text, before, "a refused mirror must leave config.toml byte-identical")
                closers = [ln for ln in text.decode("utf-8").splitlines() if ln.startswith("# <<< vibe-suite:mcp-mirror")]
                self.assertEqual(len(closers), 1)
                self.assertNotIn(SECRET, text.decode("utf-8"))

    def test_valid_env_variable_names_still_cross_after_the_rule(self):
        for good in ("BILLING_API_KEY", "lower_case", "_LEADING", "X9", "A"):
            with self.subTest(name=good):
                self.seed_mcp_with_env_name(good)
                result = self.run_bridge("mcp")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"# env: {good}", self.toml())
                self.assertNotIn(SECRET, self.toml())

    def test_an_advisor_owned_entry_with_a_non_name_env_key_does_not_refuse_the_foreign_mirror(self):
        # the advisor path has one writer (E6.1): the mirror never renders an advisor-owned entry,
        # so the preflight must not inspect it either — its env keys cannot refuse the leg
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "my_advisor": {"command": "npx", "args": ["-y", "claude-octopus@1.0.0"],
                           "env": {"BAD\nNAME": "x", "ALSO#BAD": "y"},
                           "_vibe-suite_owned": {"kind": "advisor", "schema": 1}},
            "plain": {"command": "c", "args": ["--flag"]}}}, indent=2) + "\n", encoding="utf-8")
        result = self.run_bridge("mcp")
        self.assertEqual(result.returncode, 0, result.stderr)
        toml = self.toml()
        self.assertNotIn("my_advisor", toml)
        self.assertNotIn("BAD", toml)
        self.assertIn("[mcp_servers.plain]", toml)

    def test_the_command_documents_the_name_rule(self):
        text = (REPO_ROOT / "commands" / "bridge.md").read_text(encoding="utf-8")
        self.assertIn("[A-Za-z0-9_]", text)
        self.assertIn("refused by name", text)
        self.assertIn("left exactly as it was", text)

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


class WriteAtomicScratchIsUnpredictable(unittest.TestCase):
    """vibe-178 / grill H9. `write_atomic` staged through the FIXED name `.{dest}.vibe-tmp`, opened
    `O_EXCL`, and refused when that entry existed. A scratch stranded by a hard crash (no cleanup
    runs) — or by a cleanup unlink that itself failed — then wedged every later write to the same
    destination behind an opaque "already exists" refusal, and two writers of one destination
    collided the same way. The scratch now has the unpredictable `O_EXCL|O_NOFOLLOW` name
    `publish_new` always used (`_scratch`), so a leftover is an orphan, never a poison pill."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-wa-scratch-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    @staticmethod
    def scratch_names(parent):
        return sorted(p.name for p in parent.iterdir() if p.name.endswith(".vibe-tmp"))

    def test_a_write_interrupted_after_scratch_creation_does_not_poison_the_destination(self):
        """The crash seam is a child process that dies at the moment it would publish: `os._exit`
        unwinds nothing, so — exactly as after SIGKILL or power loss — the cleanup never runs and the
        scratch is left behind. The next write to the same destination must still succeed."""
        dest = self.ws / "CLAUDE.md"
        dest.write_text("first\n")
        child = textwrap.dedent(f"""
            import os, sys
            sys.path.insert(0, {str(REPO_ROOT / "scripts" / "lib")!r})
            import bridge
            def die(*args, **kwargs):
                os._exit(137)
            bridge.os.replace = die
            bridge.write_atomic({str(self.ws)!r}, {str(dest)!r}, "second\\n")
        """)
        proc = subprocess.run([sys.executable, "-c", child], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 137, proc.stderr)
        self.assertEqual(dest.read_text(), "first\n", "the interrupted write published a partial result")
        orphans = self.scratch_names(self.ws)
        self.assertEqual(len(orphans), 1, f"the seam did not leave the scratch behind: {orphans}")
        bridge.write_atomic(self.ws, dest, "third\n")
        self.assertEqual(dest.read_bytes(), b"third\n", "the next write did not land intact")

    def test_a_stale_fixed_name_scratch_from_an_earlier_crash_no_longer_blocks(self):
        """A leftover at the legacy fixed name — what a crash before this fix left behind — is an
        unrelated entry now: the write succeeds and the file is neither consumed nor destroyed."""
        dest = self.ws / ".mcp.json"
        dest.write_text("{}\n")
        stale = self.ws / ".{}.vibe-tmp".format(dest.name)
        stale.write_text("left behind by a crash before the fix\n")
        bridge.write_atomic(self.ws, dest, '{"a": 1}\n')
        self.assertEqual(dest.read_text(), '{"a": 1}\n')
        self.assertEqual(stale.read_text(), "left behind by a crash before the fix\n",
                         "a file at the legacy scratch name was consumed or destroyed")

    def test_two_concurrent_writers_of_one_destination_both_complete(self):
        """Deterministic interleaving, not timing: writer-A (a thread) is held after its scratch is
        open while writer-B runs to completion; then A is released. Both complete and the last
        `os.replace` wins. Under the fixed name B's `O_EXCL` open collided with A's scratch."""
        dest = self.ws / "state.json"
        dest.write_text("0\n")
        first_open = threading.Event()
        release = threading.Event()
        self.addCleanup(release.set)
        real_fdopen = os.fdopen

        def pausing_fdopen(fd, *args, **kwargs):
            handle = real_fdopen(fd, *args, **kwargs)
            if threading.current_thread().name == "writer-A":
                first_open.set()
                if not release.wait(10):
                    raise AssertionError("writer-A was never released")
            return handle

        failures = []

        def writer_a():
            try:
                bridge.write_atomic(self.ws, dest, "A\n")
            except BaseException as exc:  # noqa: BLE001 — the test reports whatever A raised
                failures.append(exc)

        with mock.patch.object(os, "fdopen", pausing_fdopen):
            thread = threading.Thread(target=writer_a, name="writer-A")
            thread.start()
            self.assertTrue(first_open.wait(10), "writer-A never reached its scratch")
            bridge.write_atomic(self.ws, dest, "B\n")
            self.assertEqual(dest.read_text(), "B\n", "writer-B did not complete while A held its scratch")
            release.set()
            thread.join(10)
        self.assertFalse(thread.is_alive(), "writer-A did not terminate")
        self.assertEqual(failures, [], f"a concurrent writer failed: {failures}")
        self.assertEqual(dest.read_text(), "A\n", "the last os.replace did not win")
        self.assertEqual(self.scratch_names(self.ws), [], "a completed writer left its scratch behind")

    def test_a_symlink_planted_at_the_scratch_name_is_not_followed(self):
        """The scratch is `O_EXCL|O_NOFOLLOW`. With the name pinned (`os.urandom` stubbed), a link
        planted there is an EEXIST on every attempt, never a write through the link — and the
        residual refusal, every candidate taken, names its remedy."""
        outside = Path(tempfile.mkdtemp(prefix="vibe-outside-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        dest = self.ws / "config.toml"
        dest.write_text("before\n")
        planted = self.ws / ".config.toml.{}.vibe-tmp".format("00" * 6)
        planted.symlink_to(outside / "pwned")
        with mock.patch.object(os, "urandom", lambda n: b"\x00" * n):
            with self.assertRaises(bridge.BridgeError) as caught:
                bridge.write_atomic(self.ws, dest, "owned\n")
        self.assertFalse((outside / "pwned").exists(), "the write escaped through the planted link")
        self.assertEqual(dest.read_text(), "before\n")
        self.assertTrue(planted.is_symlink(), "the planted link was consumed")
        self.assertEqual(planted.readlink(), outside / "pwned", "the planted link was re-pointed")
        message = str(caught.exception)
        self.assertIn("remove stale", message, "the residual refusal does not name the corrective action")
        self.assertIn("no other vibe-suite process is running", message,
                      "the residual refusal does not name the condition for the remedy")


# --------------------------------------------------------------------------- write-invariant matrix
# M11 / vibe-222: ONE invariant list, as data, run against BOTH safety kernels. The rows live in
# tests/fixtures/write-invariants/*.json; tests/node/write-primitive.test.mjs interprets the same files
# against scripts/lib/write.mjs. This class is an interpreter of the rows, not a port of either kernel.

WRITE_INVARIANTS = REPO_ROOT / "tests" / "fixtures" / "write-invariants"
REQUIRED_KEYS = {"schema", "id", "invariant", "setup", "operation", "expect"}
ROW_KEYS = REQUIRED_KEYS | {"umask"}
SETUP_KEYS = {"dir": {"kind", "path"}, "file": {"kind", "path", "content", "mode"}, "symlink": {"kind", "path", "target"}}
SETUP_REQUIRED = {"dir": {"kind", "path"}, "file": {"kind", "path", "content"}, "symlink": {"kind", "path", "target"}}
OPERATIONS = {"write_atomic", "publish_new"}
OPERATION_KEYS = {"name", "dest", "content", "mode"}
OUTCOMES = {"refused", "written", "declined"}
EXPECT_KEYS = {"outcome", "content", "mode", "untouched", "kinds", "entries", "entries_of"}
MODE_RULES = {"exact", "preserved", "subset_of"}
KINDS = {"absent", "symlink", "dir", "file", "other"}   # bridge.classify's answers
OCTAL = re.compile(r"0[0-7]{3}")


def _octal(value, where):
    # `fullmatch`, not `match`: `$` would accept a trailing newline.
    if not isinstance(value, str) or not OCTAL.fullmatch(value):
        raise ValueError(f"{where}: mode/umask must be a four-digit octal string like '0644', got {value!r}")
    return int(value, 8)


def _mapping(value, where):
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected an object, got {type(value).__name__}")
    return value


def _text(value, where):
    if not isinstance(value, str):
        raise ValueError(f"{where}: expected a string, got {type(value).__name__}")
    return value                        # well-formedness is checked for every string by `_check_tree`


def _refuse_constant(token):
    # `json.loads` accepts NaN/Infinity/-Infinity by default; they are not JSON, and JSON.parse refuses them.
    raise ValueError(f"non-JSON constant {token}")


#: The document class both loaders accept — stated as numbers, not as whichever parser gives out first.
#: A row is 400–900 bytes and four levels deep (row → expect → entries_of → list); the caps leave room and sit
#: far below every interpreter's own limits, so the answer does not depend on the Python or Node version.
MAX_ROW_BYTES = 65536
MAX_DEPTH = 16
#: The admissible row filename, stated identically in both loaders: `id` is the name minus `.json`, nothing else.
ROW_FILENAME = re.compile(r"[a-z][a-z0-9-]*\.json")


def _well_formed(value, where):
    try:
        value.encode("utf-8")           # a lone surrogate (JSON `"\\ud800"`) is not a well-formed string
    except UnicodeEncodeError as exc:
        raise ValueError(f"{where}: ill-formed string") from exc


def _check_tree(doc, where):
    """Iterative walk over the parsed document: nesting deeper than MAX_DEPTH is refused, and EVERY string —
    object key or value, at any depth, read by the grammar or not — must be well-formed."""
    stack = [(doc, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise ValueError(f"{where}: nesting deeper than {MAX_DEPTH}")
        if isinstance(node, dict):
            for key, child in node.items():
                _well_formed(key, where)
                stack.append((child, depth + 1))
        elif isinstance(node, list):
            for child in node:
                stack.append((child, depth + 1))
        elif isinstance(node, str):
            _well_formed(node, where)


def _raw_depth(text, where):
    """Nesting depth of the raw JSON text, counted BEFORE parsing — a parser keeps only the last value of a
    duplicate key, so a post-parse walk never sees a discarded value's nesting, and an interpreter may run out of
    recursion before any walk runs. Strings are skipped (a bracket inside a string is not nesting)."""
    depth = in_string = escaped = 0
    for ch in text:
        if in_string:
            if escaped:
                escaped = 0
            elif ch == "\\":
                escaped = 1
            elif ch == '"':
                in_string = 0
        elif ch == '"':
            in_string = 1
        elif ch in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise ValueError(f"{where}: nesting deeper than {MAX_DEPTH}")
        elif ch in "]}":
            depth -= 1


def _read_row(path):
    """Read exactly the documents the Node loader reads. The filename must match ROW_FILENAME (so `id`
    is the name minus `.json` on both sides — `Path.stem` and `slice(0, -5)` disagree on a name like `.json`). Bytes over MAX_ROW_BYTES are refused before decoding;
    invalid UTF-8 is a refusal (UnicodeDecodeError is a ValueError); the non-JSON constants are refused;
    every number is a double (`parse_int=float`), as it is for JSON.parse — so a 4,301-digit integer is `inf`
    on both sides instead of Python's int-conversion limit deciding; an interpreter that runs out of recursion
    before our own nesting cap is checked answers with the same refusal class."""
    if not ROW_FILENAME.fullmatch(path.name):
        raise ValueError(f"{path.name}: unknown row filename — expected [a-z][a-z0-9-]*.json")
    data = path.read_bytes()
    if len(data) > MAX_ROW_BYTES:
        raise ValueError(f"{path.name}: {len(data)} bytes exceeds the {MAX_ROW_BYTES}-byte row limit")
    text = data.decode("utf-8")
    _raw_depth(text, path.name)          # before the parser: covers discarded duplicate values and every interpreter's limit
    try:
        doc = json.loads(text, parse_constant=_refuse_constant, parse_int=float)
    except RecursionError as exc:        # unreachable past the pre-scan; kept so the refusal class never changes
        raise ValueError(f"{path.name}: nesting deeper than {MAX_DEPTH}") from exc
    _check_tree(doc, path.name)
    return doc


def load_write_invariants(directory=WRITE_INVARIANTS):
    """Every `*.json` under the fixture directory, validated strictly: an unknown key, kind, operation,
    outcome or mode rule is a ValueError, never a skipped row — a row one interpreter cannot express must
    fail that interpreter, or the 'either kernel failing a row fails CI' property is lost."""
    rows = []
    for path in sorted(Path(directory).glob("*.json")):
        row = _mapping(_read_row(path), path.name)
        if set(row) - ROW_KEYS or REQUIRED_KEYS - set(row):
            raise ValueError(f"{path.name}: unknown or missing top-level keys")
        # `schema` is the JSON NUMBER 1. `1.0` is the same JSON number (every parser agrees; the Node loader cannot
        # tell them apart, so neither does this one); `true` is not a number (bool is refused explicitly — it is a
        # subclass of int); a string is not a number. Duplicate keys keep the last value, as both parsers do.
        schema = row["schema"]
        if isinstance(schema, bool) or not isinstance(schema, (int, float)) or schema != 1 or row["id"] != path.stem:
            raise ValueError(f"{path.name}: schema must be the JSON number 1 and id must equal the file stem")
        _text(row["invariant"], path.name)
        if not isinstance(row["setup"], list):
            raise ValueError(f"{path.name}: setup must be a list")
        for step in row["setup"]:
            step = _mapping(step, path.name)
            kind = _text(step.get("kind"), path.name)          # a string BEFORE the membership test
            if kind not in SETUP_KEYS or set(step) - SETUP_KEYS[kind] or SETUP_REQUIRED[kind] - set(step):
                raise ValueError(f"{path.name}: unknown setup kind or fields {step!r}")
            for key in ("path", "content", "target"):
                if key in step:
                    _text(step[key], path.name)
            if "mode" in step:
                _octal(step["mode"], path.name)
        op = _mapping(row["operation"], path.name)
        if set(op) - OPERATION_KEYS or {"name", "dest", "content"} - set(op) or _text(op["name"], path.name) not in OPERATIONS:
            raise ValueError(f"{path.name}: unknown operation or operation fields {op!r}")
        _text(op["dest"], path.name); _text(op["content"], path.name)
        if "mode" in op:
            _octal(op["mode"], path.name)
        if "umask" in row:
            _octal(row["umask"], path.name)
        expect = _mapping(row["expect"], path.name)
        if set(expect) - EXPECT_KEYS or _text(expect.get("outcome"), path.name) not in OUTCOMES:
            raise ValueError(f"{path.name}: unknown expect keys or outcome")
        for key in ("untouched", "entries"):
            if key in expect and (not isinstance(expect[key], list) or not all(isinstance(x, str) for x in expect[key])):
                raise ValueError(f"{path.name}: {key} must be a list of strings")
        if "kinds" in expect:
            for rel, kind in _mapping(expect["kinds"], path.name).items():
                if _text(kind, path.name) not in KINDS:                # a string BEFORE the membership test
                    raise ValueError(f"{path.name}: unknown kind {kind!r} for {rel}")
        if "entries_of" in expect:
            for rel, names in _mapping(expect["entries_of"], path.name).items():
                if not isinstance(names, list) or not all(isinstance(x, str) for x in names):
                    raise ValueError(f"{path.name}: entries_of[{rel!r}] must be a list of strings")
        if "content" in expect:
            _text(expect["content"], path.name)
        if "mode" in expect:
            mode = _mapping(expect["mode"], path.name)
            if len(mode) != 1 or set(mode) - MODE_RULES:
                raise ValueError(f"{path.name}: unknown mode rule")
            (rule, value), = mode.items()
            if rule == "preserved":
                if value is not True:
                    raise ValueError(f"{path.name}: preserved must be exactly true")
            else:
                _octal(value, path.name)
        rows.append(row)
    if not rows:
        raise ValueError(f"{directory}: no rows")
    return rows


class WriteInvariantMatrix(unittest.TestCase):
    """The shared matrix against bridge.py. One subTest per row; the Node twin is
    `tests/node/write-primitive.test.mjs` ("write-invariant matrix")."""

    def _apply_setup(self, root, setup):
        for step in setup:
            target = root / step["path"]
            if step["kind"] == "dir":
                target.mkdir(parents=True)
            elif step["kind"] == "file":
                target.write_text(step["content"], encoding="utf-8")
                if "mode" in step:
                    os.chmod(target, int(step["mode"], 8))
            else:
                target.symlink_to(step["target"])

    def _snapshot(self, root, rel):
        # Observation goes through the kernel's own `classify`; the interpreter decides nothing about kinds.
        p = root / rel
        kind = bridge.classify(p)
        return (kind, os.readlink(p) if kind == "symlink" else p.read_bytes() if kind == "file" else None)

    def _run(self, row):
        root = Path(tempfile.mkdtemp(prefix="vibe-wi-")).resolve()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        self._apply_setup(root, row["setup"])
        expect = row["expect"]
        before = {rel: self._snapshot(root, rel) for rel in expect.get("untouched", [])}
        op = row["operation"]
        dest_path = root / op["dest"]
        before_mode = (dest_path.stat().st_mode & 0o777) if bridge.classify(dest_path) == "file" else None
        kwargs = {"mode": int(op["mode"], 8)} if "mode" in op else {}   # omission is the API's own default
        fn = getattr(bridge, op["name"])
        previous = os.umask(int(row["umask"], 8)) if "umask" in row else None
        try:
            try:
                result = fn(root, root / op["dest"], op["content"], **kwargs)
                outcome = "declined" if result is False else "written"
            except bridge.BridgeError:
                outcome = "refused"
        finally:
            if previous is not None:
                os.umask(previous)
        self.assertEqual(outcome, expect["outcome"], row["invariant"])
        dest = root / op["dest"]
        if outcome == "written":
            self.assertEqual(dest.read_text(encoding="utf-8"), expect["content"])
            if "mode" in expect:
                (rule, value), = expect["mode"].items()
                actual = dest.stat().st_mode & 0o777
                if rule == "exact":
                    self.assertEqual(actual, int(value, 8), row["id"])
                elif rule == "subset_of":
                    self.assertEqual(actual & ~int(value, 8), 0, f"{row['id']}: {oct(actual)} exceeds {value}")
                else:
                    self.assertEqual(actual, before_mode, row["id"])
        for rel, snap in before.items():
            self.assertEqual(self._snapshot(root, rel), snap, f"{row['id']}: {rel} changed")
        for rel, kind in expect.get("kinds", {}).items():
            self.assertEqual(bridge.classify(root / rel), kind, f"{row['id']}: {rel}")
        if "entries" in expect:
            self.assertEqual(sorted(p.name for p in root.iterdir()), sorted(expect["entries"]), row["id"])
        for rel, names in expect.get("entries_of", {}).items():
            self.assertEqual(sorted(p.name for p in (root / rel).iterdir()), sorted(names), f"{row['id']}: {rel}")

    def test_every_row_holds_against_bridge_py(self):
        rows = load_write_invariants()
        for row in rows:
            with self.subTest(row=row["id"]):
                self._run(row)

    def test_the_issue_named_rows_are_present(self):
        ids = {row["id"] for row in load_write_invariants()}
        for required in ("symlink-at-dest-replace", "intermediate-symlink", "dotdot-component", "fixed-name-collision",
                         "mode-preserved-when-omitted", "crash-leftover"):
            with self.subTest(row=required):
                self.assertIn(required, ids)

    def test_a_malformed_row_fails_the_loader_instead_of_being_skipped(self):
        bad = Path(tempfile.mkdtemp(prefix="vibe-wi-bad-"))
        self.addCleanup(shutil.rmtree, bad, ignore_errors=True)
        good = json.loads((WRITE_INVARIANTS / "dotdot-component.json").read_text(encoding="utf-8"))
        mutations = {
            "unknown operation": lambda r: r["operation"].__setitem__("name", "write_anything"),
            "unknown outcome": lambda r: r["expect"].__setitem__("outcome", "ignored"),
            "unknown top-level key": lambda r: r.__setitem__("skip", True),
            "unknown setup kind": lambda r: r["setup"].append({"kind": "fifo", "path": "f"}),
            "unknown setup field": lambda r: r["setup"][0].__setitem__("mode_bits", "0644"),
            "unknown operation field": lambda r: r["operation"].__setitem__("force", True),
            "missing required key": lambda r: r.pop("invariant"),
            "wrong schema": lambda r: r.__setitem__("schema", 2),
            "malformed octal mode": lambda r: r["operation"].__setitem__("mode", "644x"),
            "decimal mode": lambda r: r["operation"].__setitem__("mode", 420),
            "malformed umask": lambda r: r.__setitem__("umask", "22"),
            "two mode rules": lambda r: r["expect"].__setitem__("mode", {"exact": "0644", "preserved": True}),
            "boolean schema": lambda r: r.__setitem__("schema", True),
            "setup not a list": lambda r: r.__setitem__("setup", {}),
            "setup step not an object": lambda r: r.__setitem__("setup", ["real"]),
            "mode with a trailing newline": lambda r: r["operation"].__setitem__("mode", "0644\n"),
            "inherited-property operation name": lambda r: r["operation"].__setitem__("name", "toString"),
            "preserved false": lambda r: r["expect"].__setitem__("mode", {"preserved": False}),
            "expect not an object": lambda r: r.__setitem__("expect", ["refused"]),
            "operation not an object": lambda r: r.__setitem__("operation", "write_atomic"),
            "untouched not a list of strings": lambda r: r["expect"].__setitem__("untouched", "real"),
            "operation name not a string": lambda r: r["operation"].__setitem__("name", ["write_atomic"]),
            "setup kind not a string": lambda r: r["setup"][0].__setitem__("kind", ["dir"]),
            "outcome not a string": lambda r: r["expect"].__setitem__("outcome", ["refused"]),
            "entries_of value not a list": lambda r: r["expect"].__setitem__("entries_of", {"real": None}),
            "unknown classify kind": lambda r: r["expect"].__setitem__("kinds", {"x.json": "bogus"}),
            "kinds value a list": lambda r: r["expect"].__setitem__("kinds", {"x.json": ["file"]}),
            "kinds value an object": lambda r: r["expect"].__setitem__("kinds", {"x.json": {}}),
            "schema as a string": lambda r: r.__setitem__("schema", "1"),
            "schema 2": lambda r: r.__setitem__("schema", 2),
        }
        for label, mutate in mutations.items():
            row = json.loads(json.dumps(good)); mutate(row)
            (bad / "dotdot-component.json").write_text(json.dumps(row), encoding="utf-8")
            with self.subTest(mutation=label):
                with self.assertRaises(ValueError):
                    load_write_invariants(bad)
        # Agreement cases the Node loader must answer identically (its test carries the same raw texts): `1.0` is the
        # JSON number 1; a duplicate key keeps its LAST value; an escaped key spells the same key.
        raw = json.dumps(good)
        for label, text, ok in (("schema 1.0", raw.replace('"schema": 1,', '"schema": 1.0,'), True),
                                ("duplicate schema, first NaN", raw.replace('"schema": 1,', '"schema": NaN, "schema": 1,'), False),
                                ("duplicate schema, first Infinity", raw.replace('"schema": 1,', '"schema": Infinity, "schema": 1,'), False),
                                ("lone surrogate in content", raw.replace('"content": "new"', '"content": "\\ud800"'), False),
                                ("schema 1e0", raw.replace('"schema": 1,', '"schema": 1e0,'), True),
                                ("discarded 4301-digit integer", raw.replace('"schema": 1,', '"schema": ' + "9" * 4301 + ', "schema": 1,'), True),
                                ("discarded 17-level nesting", raw.replace('"schema": 1,', '"schema": ' + "[" * 17 + "0" + "]" * 17 + ', "schema": 1,'), False),
                                ("discarded 12-level nesting", raw.replace('"schema": 1,', '"schema": ' + "[" * 12 + "0" + "]" * 12 + ', "schema": 1,'), True),
                                ("discarded 2000-level nesting", raw.replace('"schema": 1,', '"schema": ' + "[" * 2000 + "0" + "]" * 2000 + ', "schema": 1,'), False),
                                ("brackets inside a string are not nesting", raw.replace('"content": "new"', '"content": "' + "[" * 40 + '"'), True),
                                ("discarded 15-level nesting is level 16 exactly", raw.replace('"schema": 1,', '"schema": ' + "[" * 15 + "0" + "]" * 15 + ', "schema": 1,'), True),
                                ("discarded 16-level nesting is level 17", raw.replace('"schema": 1,', '"schema": ' + "[" * 16 + "0" + "]" * 16 + ', "schema": 1,'), False),
                                ("a bracket run after an escaped backslash inside a string", raw.replace('"content": "new"', '"content": "a\\\\' + "[" * 30 + '"'), True),
                                ("an escaped quote then brackets inside a string", raw.replace('"content": "new"', '"content": "a\\"' + "[" * 30 + '\\""'), True),
                                ("an unterminated string followed by brackets", raw.replace('"content": "new"', '"content": "' + "[" * 30), False),
                                ("lone surrogate in an entries item", raw.replace('"entries": [', '"entries": ["\\ud800", '), False),
                                ("lone surrogate as a kinds key", raw.replace('"expect": {', '"expect": {"kinds": {"\\ud800": "file"}, '), False),
                                ("exactly the byte cap", raw + " " * (65536 - len(raw.encode("utf-8"))), True),
                                ("one byte over the cap", raw + " " * (65537 - len(raw.encode("utf-8"))), False),):
            (bad / "dotdot-component.json").write_text(text, encoding="utf-8")
            with self.subTest(agreement=label):
                if ok:
                    self.assertEqual(len(load_write_invariants(bad)), 1)
                else:
                    with self.assertRaises(ValueError):
                        load_write_invariants(bad)
        (bad / "dotdot-component.json").unlink()
        for name, ok in ((".json", False), ("Dotdot-Component.json", False), ("dotdot component.json", False), ("dotdot.component.json", False), ("dotdot-component.json", True)):
            for stale in bad.glob("*.json"):
                stale.unlink()
            doc = dict(good); doc["id"] = name[:-5]
            (bad / name).write_text(json.dumps(doc), encoding="utf-8")
            with self.subTest(filename=name):
                if ok:
                    self.assertEqual(len(load_write_invariants(bad)), 1)
                else:
                    with self.assertRaises(ValueError):
                        load_write_invariants(bad)
        for label, text, ok in (("schema with extra spaces", raw.replace('"schema": 1,', '"schema":  1,'), True),
                                ("duplicate schema, last 1.0", raw.replace('"schema": 1,', '"schema": 1, "schema": 1.0,'), True),
                                ("duplicate schema, last 2", raw.replace('"schema": 1,', '"schema": 1, "schema": 2,'), False),
                                ("escaped key", raw.replace('"schema": 1,', '"\\u0073chema": 1,'), True)):
            (bad / "dotdot-component.json").write_text(text, encoding="utf-8")
            with self.subTest(agreement=label):
                if ok:
                    self.assertEqual(len(load_write_invariants(bad)), 1)
                else:
                    with self.assertRaises(ValueError):
                        load_write_invariants(bad)
        (bad / "dotdot-component.json").write_bytes(raw.encode("utf-8").replace(b'"content": "new"', b'"content": "n\xffw"'))
        with self.subTest(agreement="invalid UTF-8 byte"):
            with self.assertRaises(ValueError):
                load_write_invariants(bad)
        (bad / "dotdot-component.json").write_bytes(b"\xef\xbb\xbf" + raw.encode("utf-8"))
        with self.subTest(agreement="UTF-8 BOM prefix"):
            with self.assertRaises(ValueError):          # json.loads refuses a BOM; so does JSON.parse when the decoder keeps it
                load_write_invariants(bad)
        (bad / "dotdot-component.json").write_text(json.dumps(good), encoding="utf-8")
        (bad / "renamed.json").write_text(json.dumps(good), encoding="utf-8")   # id != file stem
        with self.assertRaises(ValueError):
            load_write_invariants(bad)
        for path in bad.glob("*.json"):
            path.unlink()
        with self.assertRaises(ValueError):                                   # an empty directory is not a matrix
            load_write_invariants(bad)


class TestAdvisorMirrorSkip(unittest.TestCase):
    """E6.1 (D-b): the generic mirror never touches advisor-owned entries — single writer."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-bridge-adv-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.plugin = Path(tempfile.mkdtemp(prefix="vibe-plugin-adv-"))
        self.addCleanup(shutil.rmtree, self.plugin, ignore_errors=True)
        (self.plugin / "skills").mkdir()

    def test_owned_advisor_entry_is_not_mirrored(self):
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "my_advisor": {"command": "npx", "args": ["-y", "claude-octopus@1.0.0"],
                           "env": {"CLAUDE_DESCRIPTION": "d"},
                           "_vibe-suite_owned": {"kind": "advisor", "schema": 1}},
            "foreign_env": {"command": "srv", "env": {"TOKEN": "secret-value"}},
        }}, indent=2) + "\n", encoding="utf-8")
        r = subprocess.run(["python3", str(CLI), "mcp", "--workspace", str(self.ws),
                            "--plugin-root", str(self.plugin)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        toml = (self.ws / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertNotIn("my_advisor", toml,
                         "the advisor path owns both stores; the mirror must skip its entries")
        self.assertIn("foreign_env", toml, "foreign env servers still mirror names-only")
        self.assertNotIn("secret-value", toml)


class TestMirrorWiring(BridgeCase):
    """E7.2 (vibe-54): per-skill mirror links in a real .agents/skills directory, the legacy
    migration, and the mirrors regeneration leg."""

    def seed_mirror(self):
        d = self.plugin / "codex" / "skills" / "vibe-alpha"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: vibe-alpha\ndescription: a\n---\nx\n")

    def test_fresh_install_creates_per_skill_links(self):
        self.seed_mirror()
        self.run_bridge("skills")
        entry = self.ws / ".agents" / "skills" / "vibe-alpha"
        self.assertTrue((self.ws / ".agents" / "skills").is_dir())
        self.assertFalse((self.ws / ".agents" / "skills").is_symlink())
        self.assertTrue(entry.is_symlink())
        self.assertTrue((entry / "SKILL.md").is_file())

    def test_no_mirror_keeps_the_legacy_link(self):
        self.run_bridge("skills")
        agents_link = self.ws / ".agents" / "skills"
        self.assertTrue(agents_link.is_symlink())
        self.assertEqual(os.readlink(agents_link), "../.claude/skills")

    def test_legacy_owned_link_is_migrated_and_prior_exposure_preserved(self):
        self.seed_mirror()
        (self.ws / ".claude" / "skills" / "mine").mkdir(parents=True)
        (self.ws / ".claude" / "skills" / "mine" / "SKILL.md").write_text("m\n")
        (self.ws / ".agents").mkdir()
        os.symlink("../.claude/skills", self.ws / ".agents" / "skills")
        self.run_bridge("skills")
        skills_dir = self.ws / ".agents" / "skills"
        self.assertTrue(skills_dir.is_dir() and not skills_dir.is_symlink())
        self.assertTrue((skills_dir / "vibe-alpha").is_symlink())
        self.assertTrue((skills_dir / "mine" / "SKILL.md").is_file(),
                        "previously exposed skill vanished in the migration")

    def test_user_owned_agents_link_is_refused_untouched(self):
        self.seed_mirror()
        (self.ws / "my-skills").mkdir()
        (self.ws / ".agents").mkdir()
        os.symlink("../my-skills", self.ws / ".agents" / "skills")
        result = self.run_bridge("skills")
        self.assertEqual(os.readlink(self.ws / ".agents" / "skills"), "../my-skills")
        self.assertIn("refused", result.stdout + result.stderr)

    def test_colliding_user_entry_is_refused_per_entry(self):
        self.seed_mirror()
        (self.ws / ".agents" / "skills" / "vibe-alpha").mkdir(parents=True)
        (self.ws / ".agents" / "skills" / "vibe-alpha" / "SKILL.md").write_text("user\n")
        result = self.run_bridge("skills")
        self.assertEqual((self.ws / ".agents" / "skills" / "vibe-alpha" / "SKILL.md")
                         .read_text(), "user\n")
        self.assertIn("vibe-alpha", result.stdout + result.stderr)

    def test_mirrors_leg_runs_the_generator_and_is_idempotent(self):
        self.seed_mirror_driver()
        first = self.run_bridge("mirrors")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertTrue((self.plugin / "codex" / "MIRROR-MANIFEST.json").is_file())
        import hashlib
        def tree_hash():
            h = hashlib.sha256()
            for f in sorted(self.plugin.rglob("*")):
                if f.is_file():
                    h.update(f.relative_to(self.plugin).as_posix().encode())
                    h.update(f.read_bytes())
            return h.hexdigest()
        before = tree_hash()
        second = self.run_bridge("mirrors")
        self.assertEqual(second.returncode, 0)
        self.assertEqual(tree_hash(), before,
                         "a second mirrors run changed the plugin tree")

    def test_missing_generator_fails_loudly(self):
        result = self.run_bridge("mirrors")
        self.assertEqual(result.returncode, 1)
        self.assertIn("mirror", (result.stdout + result.stderr).lower())


# --- vibe-209 -------------------------------------------------------------------------------------
import ast as _v209_ast                                                              # noqa: E402
import pathlib as _v209_pathlib                                                      # noqa: E402
import sys as _v209_sys                                                              # noqa: E402
from unittest import mock as _v209_mock                                              # noqa: E402
import io as _v209_io                                                               # noqa: E402
import contextlib as _v209_contextlib                                               # noqa: E402
import tempfile as _v209_tempfile                                                   # noqa: E402

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


class MirrorRegenTimeoutTest(unittest.TestCase):
    """R16 — the mirror-regeneration spawn is bounded at exactly 60 s (vibe-209 / grill P4).

    Two assertions for two different defects. The VALUE is what the issue specifies, and a test that
    only proved "some bound exists" would accept 1 s or 10 minutes equally. The CALL is that the
    bound reaches `subprocess.run` rather than sitting in an unused constant.
    """

    def test_the_constant_is_the_value_the_issue_names(self):
        import bridge_cli
        self.assertEqual(bridge_cli.MIRROR_REGEN_TIMEOUT_S, 60)

    def test_every_subprocess_run_in_bridge_cli_is_bounded(self):
        calls, unbounded = _v209_unbounded_runs(_V209_SCRIPTS / "bridge_cli.py")
        self.assertTrue(calls, "the mirror regeneration spawn must still be a subprocess.run call")
        self.assertEqual([c.lineno for c in unbounded], [],
                         "an unbounded subprocess.run can hang the command forever")


class MirrorRegenTimeoutValueTest(unittest.TestCase):
    """The value and the handler, not merely "a timeout keyword exists" (Step-8 finding 2).

    `timeout=1`, `timeout=None` or `timeout=some_other_constant` all satisfy an AST presence check.
    These read the call's OWN keyword back and force the exception the handler exists for.
    """

    def _timeout_arg(self, source_path, call_index=0):
        tree = _v209_ast.parse(_v209_pathlib.Path(source_path).read_text(encoding="utf-8"))
        calls = [n for n in _v209_ast.walk(tree)
                 if isinstance(n, _v209_ast.Call) and isinstance(n.func, _v209_ast.Attribute)
                 and n.func.attr == "run" and isinstance(n.func.value, _v209_ast.Name)
                 and n.func.value.id == "subprocess"]
        self.assertTrue(calls, "the spawn must still be a subprocess.run call")
        for call in calls:
            for kw in call.keywords:
                if kw.arg == "timeout":
                    return kw.value
        self.fail("no timeout= keyword on any subprocess.run call")

    def test_the_timeout_is_the_owning_constant_not_an_arbitrary_number(self):
        node = self._timeout_arg(_V209_SCRIPTS / "bridge_cli.py")
        self.assertIsInstance(node, _v209_ast.Name,
                              "the bound must be the named constant, so the value has one home")
        self.assertEqual(node.id, "MIRROR_REGEN_TIMEOUT_S")

    def test_a_timeout_is_reported_as_a_diagnostic_not_a_traceback(self):
        """FORCE the exception; a source search proves only that the words are in the file.

        A bound with no handler turns a hang into a crash, which is not an improvement — and the
        earlier version of this test would have passed with the `except` deleted, because it read
        for the string rather than running the path.
        """
        import bridge_cli
        ws = _v209_pathlib.Path(_v209_tempfile.mkdtemp())
        plugin_root = _v209_pathlib.Path(_v209_tempfile.mkdtemp())
        gen = plugin_root / "scripts" / "mirror-sync.py"
        gen.parent.mkdir(parents=True, exist_ok=True)
        gen.write_text("# stand-in for the generator; never actually run\n")

        def explode(argv, **kwargs):
            raise bridge_cli.subprocess.TimeoutExpired(argv, kwargs.get("timeout"))

        err = _v209_io.StringIO()
        with _v209_mock.patch.object(bridge_cli.subprocess, "run", explode), \
                _v209_contextlib.redirect_stderr(err):
            rc = bridge_cli.main(["mirrors", "--workspace", str(ws),
                                  "--plugin-root", str(plugin_root)])
        self.assertEqual(rc, 1, "a timed-out regeneration is a reported failure, not a crash")
        # The command's OWN sentence, not Python's. `TimeoutExpired.__str__` is
        # "Command '[...]' timed out after 60 seconds", so asserting "timed out after" or "60"
        # passes whether this handler ran or a generic outer one printed the raw exception —
        # which is exactly how the first version of this test certified nothing.
        self.assertIn("error: mirrors: regeneration timed out after 60s", err.getvalue(),
                      "the handler's own diagnostic must be what reaches the operator: %r"
                      % err.getvalue())
        self.assertNotIn("Command '[", err.getvalue(),
                         "and the raw exception must not be what they see")


class TestAnchoredWrites(unittest.TestCase):
    """M17 / vibe-217: the containment anchor for an arbitrary output path, shared by every program
    that writes where the user points it (`bin/vibe-report`, the site builders, runs-stats)."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-anchor-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def test_existing_anchor_walks_up_and_resolves(self):
        unresolved, real = bridge.existing_anchor(self.ws / "a" / "b" / "c")
        self.assertEqual(unresolved, self.ws.absolute())
        self.assertEqual(real, Path(os.path.realpath(self.ws)))
        target = self.ws / "real"; target.mkdir()
        link = self.ws / "link"; link.symlink_to(target)
        unresolved, real = bridge.existing_anchor(link / "deeper")
        self.assertEqual((unresolved, real), (link.absolute(), Path(os.path.realpath(target))))
        # a regular FILE on the way up is not an anchor: the nearest existing DIRECTORY is
        blocker = self.ws / "a-file"; blocker.write_text("x")
        unresolved, real = bridge.existing_anchor(blocker / "sub" / "deep")
        self.assertTrue(real.is_dir(), "the anchor must be a directory")
        self.assertEqual((unresolved, real), (self.ws.absolute(), Path(os.path.realpath(self.ws))))

    def test_write_below_creates_descendants_and_refuses_symlinks(self):
        anchor = bridge.existing_anchor(self.ws / "out" / "sub")
        bridge.write_below(anchor, self.ws / "out" / "sub" / "f.txt", "hello\n")
        self.assertEqual((self.ws / "out" / "sub" / "f.txt").read_text(), "hello\n")
        # a symlinked directory component below the anchor is refused
        elsewhere = self.ws / "elsewhere"; elsewhere.mkdir()
        (self.ws / "out" / "linkdir").symlink_to(elsewhere)
        with self.assertRaises(bridge.BridgeError):
            bridge.write_below(anchor, self.ws / "out" / "linkdir" / "g.txt", "x")
        self.assertEqual(list(elsewhere.iterdir()), [])
        # a symlinked destination file is refused and preserved
        theirs = self.ws / "theirs.txt"; theirs.write_text("user")
        (self.ws / "out" / "sub" / "h.txt").symlink_to(theirs)
        with self.assertRaises(bridge.BridgeError):
            bridge.write_below(anchor, self.ws / "out" / "sub" / "h.txt", "ours")
        self.assertTrue((self.ws / "out" / "sub" / "h.txt").is_symlink())
        self.assertEqual(theirs.read_text(), "user")
        # a symlinked ANCHOR (the user's existing directory) is followed via its realpath
        real = self.ws / "realdir"; real.mkdir()
        link = self.ws / "linkedparent"; link.symlink_to(real)
        anchor2 = bridge.existing_anchor(link / "nested")
        bridge.write_below(anchor2, link / "nested" / "i.txt", "via link")
        self.assertEqual((real / "nested" / "i.txt").read_text(), "via link")

    def test_publish_below_collision_and_symlink(self):
        anchor = bridge.existing_anchor(self.ws / "out")
        dest = self.ws / "out" / "a.html"
        self.assertTrue(bridge.publish_below(anchor, dest, b"first"))
        self.assertFalse(bridge.publish_below(anchor, dest, b"second"), "an existing regular file is a collision")
        self.assertEqual(dest.read_bytes(), b"first")
        theirs = self.ws / "theirs.html"; theirs.write_text("user")
        link = self.ws / "out" / "b.html"; link.symlink_to(theirs)
        with self.assertRaises(bridge.BridgeError):
            bridge.publish_below(anchor, link, b"ours")
        self.assertEqual(theirs.read_text(), "user")


class TestLoadJson(unittest.TestCase):
    """M6 / vibe-218: one JSON reader. The default is strict — every failure is a `JsonUnreadable` whose
    `.cause` is the underlying exception; `strict=False` is the lenient contract the pre-M6 callers rely on."""

    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-loadjson-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def write(self, name, data):
        p = self.ws / name
        p.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        return p

    def test_default_is_strict_and_names_the_cause(self):
        cases = [
            ("missing.json", None, OSError),
            ("adir.json", "DIR", OSError),
            ("empty.json", b"", ValueError),
            ("blank.json", b"  \n", ValueError),
            ("bad.json", b"{not json", ValueError),
            ("utf8.json", b"\xff\xfe\x00", UnicodeDecodeError),
        ]
        for name, data, cause in cases:
            with self.subTest(name=name):
                if data == "DIR":
                    (self.ws / name).mkdir()
                elif data is not None:
                    self.write(name, data)
                with self.assertRaises(bridge.JsonUnreadable) as ctx:
                    bridge.load_json(self.ws / name)
                self.assertIsInstance(ctx.exception, bridge.BridgeError)
                self.assertEqual(Path(ctx.exception.path), self.ws / name)
                self.assertIsInstance(ctx.exception.cause, cause, repr(ctx.exception.cause))
        p = self.write("unreadable.json", b"{}"); p.chmod(0)
        try:
            with self.assertRaises(bridge.JsonUnreadable) as ctx:
                bridge.load_json(p)
            self.assertIsInstance(ctx.exception.cause, OSError)
        finally:
            p.chmod(0o644)
        self.assertEqual(bridge.load_json(self.write("ok.json", b'{"a": 1}')), {"a": 1})

    def test_a_parser_recursion_error_is_unreadable_too(self):
        """Step 9 R1: `json.loads` raises RecursionError (not a ValueError) on a deeply nested document.
        Injected, because the depth that trips it is version-dependent (3.12/3.13 fail at 100,000 levels,
        3.14 parses them); the real document below is accepted either way but may never escape as anything
        other than a value or a JsonUnreadable."""
        p = self.write("deep.json", b"[" * 100_000 + b"]" * 100_000)
        with mock.patch.object(bridge.json, "loads", side_effect=RecursionError("maximum recursion depth exceeded")):
            with self.assertRaises(bridge.JsonUnreadable) as ctx:
                bridge.load_json(p)
        self.assertIsInstance(ctx.exception.cause, RecursionError)
        self.assertEqual(str(ctx.exception.cause), "maximum recursion depth exceeded")
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except RecursionError:
            with self.assertRaises(bridge.JsonUnreadable) as ctx:
                bridge.load_json(p)
            self.assertIsInstance(ctx.exception.cause, RecursionError)
        else:
            self.assertIsInstance(bridge.load_json(p), list)   # not assertEqual: comparing 100,000-deep lists recurses too

    def test_explicit_lenient_mode_is_the_pre_m6_contract(self):
        self.assertEqual(bridge.load_json(self.ws / "missing.json", strict=False), {})
        (self.ws / "adir").mkdir()
        self.assertEqual(bridge.load_json(self.ws / "adir", strict=False), {})
        self.assertEqual(bridge.load_json(self.write("empty.json", b""), strict=False), {})
        with self.assertRaises(bridge.BridgeError):
            bridge.load_json(self.write("bad.json", b"{not json"), strict=False)
        self.assertEqual(bridge.load_json(self.write("ok.json", b'{"b": 2}'), strict=False), {"b": 2})
