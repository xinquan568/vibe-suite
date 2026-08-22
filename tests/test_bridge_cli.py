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
        message = str(caught.exception)
        self.assertIn("remove stale", message, "the residual refusal does not name the corrective action")
        self.assertIn("no other vibe-suite process is running", message,
                      "the residual refusal does not name the condition for the remedy")


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
