#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fixtures for `/vibe-suite:update` (E2.6 / vibe-23, F1.7).

**The acceptance clause is "runs clean after a simulated plugin update", so these fixtures simulate
one.** A stale managed pin, a new plugin pin, and unrelated user TOML are seeded, then the
orchestration is executed and the *transition* is asserted. Reading headings or matching strings
would prove none of it.

The MCP handshake runs against a **fake server that actually responds** — not against an absent
binary. #24 shipped a test that passed locally because `codex` was present and failed in CI because
it was not: it measured the environment rather than the code. `VIBE_SUITE_MCP_BIN` is therefore
proven load-bearing by pointing it at a path that does not exist and requiring failure.
"""

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UPDATE = REPO_ROOT / "scripts" / "update.py"
PROBE = REPO_ROOT / "scripts" / "lib" / "boot_probe.mjs"
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

import bridge          # noqa: E402
import mcp_pin         # noqa: E402
import retired_names   # noqa: E402

UNRELATED_TOML = textwrap.dedent("""\
    # a comment the user wrote
    [mcp_servers.something-of-theirs]
    command = "their-server"

    [tui]
    theme = "dark"
    """)


def write_fake_server(path, behaviour="respond"):
    """A stand-in for `npx`. It speaks newline-delimited JSON-RPC, so the probe has something real
    to hand-shake with. `hang` additionally spawns a descendant, so reaping the *group* is what the
    timeout test actually measures — killing the direct child alone would leave it running."""
    path.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import json, os, subprocess, sys, time
        behaviour = {behaviour!r}
        # Recorded to a sidecar rather than stderr: the probe deliberately does not echo third-party
        # output on success, so stderr is not observable there.
        record = os.environ.get("FAKE_ARGV_LOG")
        if record:
            with open(record, "a") as fh:
                fh.write(json.dumps(sys.argv[1:]) + "\\n")
        if "--version" in sys.argv:
            print("1.0.0"); sys.exit(0)
        if behaviour == "exit":
            sys.exit(3)
        if behaviour == "hang":
            subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
            time.sleep(300); sys.exit(0)
        line = sys.stdin.readline()
        req = json.loads(line)
        # The requested target rides in argv as ["-y", "<package>@<version>"]. Reporting it back
        # is the honest-server default (E7.1's mismatch contract compares self-report to the
        # request); the mismatch behaviours below are the liars the probe must now catch.
        target = sys.argv[-1]
        pkg, _, ver = target.rpartition("@")
        info = {{"name": pkg, "version": ver}}
        if behaviour == "wrong-name":
            info["name"] = "impostor-octopus"
        if behaviour == "wrong-version":
            info["version"] = "9.9.9"
        if behaviour == "no-version":
            del info["version"]
        if behaviour == "bad-version":
            info["version"] = {{"major": 9}}
        if behaviour == "no-name":
            del info["name"]
        if behaviour == "bad-name":
            info["name"] = 7
        if behaviour == "error":
            out = {{"jsonrpc": "2.0", "id": req["id"], "error": {{"code": -1, "message": "nope"}}}}
        else:
            out = {{"jsonrpc": "2.0", "id": req["id"], "result": {{"serverInfo": info}}}}
        print(json.dumps(out), flush=True)
        time.sleep(30)
        """), encoding="utf-8")
    path.chmod(0o755)
    return path


class PinStates(unittest.TestCase):
    """All five, because file-absence alone cannot distinguish pre-E7.1 from a broken install."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.pin, self.marker = self.d / "pin.txt", self.d / "pin.pending"

    def resolve(self):
        return mcp_pin.resolve_pin(pin_file=self.pin, pending_file=self.marker)

    def test_marker_only_is_pending(self):
        self.marker.write_text("owner: E7.1")
        self.assertEqual(self.resolve(), ("pending", None))

    def test_exact_version_is_shipped(self):
        self.pin.write_text("1.2.3\n")
        self.assertEqual(self.resolve(), ("shipped", "1.2.3"))
        self.pin.write_text("1.2.3-rc.1\n")
        self.assertEqual(self.resolve(), ("shipped", "1.2.3-rc.1"))

    def test_floating_specs_are_refused(self):
        for bad in ("latest", "^1.2.0", "~1.2", "1.x", "1.2", "", "  "):
            self.pin.write_text(bad)
            with self.assertRaises(mcp_pin.PinError):
                self.resolve()

    def test_neither_is_a_broken_installation(self):
        with self.assertRaises(mcp_pin.PinError):
            self.resolve()

    def test_both_is_ambiguous_and_refused(self):
        self.pin.write_text("1.2.3")
        self.marker.write_text("owner: E7.1")
        with self.assertRaises(mcp_pin.PinError):
            self.resolve()


class Registration(unittest.TestCase):
    def test_append_refresh_and_idempotence(self):
        added, text = mcp_pin.plan(UNRELATED_TOML, "1.0.0")
        self.assertEqual(added, "added")
        # The whole reason for the codec: written here, findable by the inventory, removable by
        # teardown. A hand-rolled fence would satisfy only the first.
        self.assertIn(mcp_pin.SERVER_NAME, bridge.toml_owned_names(text))
        self.assertTrue(bridge.toml_server_has(text, mcp_pin.SERVER_NAME))
        self.assertNotIn(mcp_pin.SERVER_NAME,
                         bridge.toml_owned_names(bridge.toml_server_remove(text, mcp_pin.SERVER_NAME)))

        again, same = mcp_pin.plan(text, "1.0.0")
        self.assertEqual(again, "current")
        self.assertEqual(same, text)

        action, moved = mcp_pin.plan(text, "2.0.0")
        self.assertEqual(action, "refreshed")
        self.assertIn("claude-octopus@2.0.0", moved)
        self.assertNotIn("claude-octopus@1.0.0", moved)
        self.assertEqual(moved.count(f"[mcp_servers.{mcp_pin.SERVER_NAME}]"), 1)

    def test_unrelated_toml_is_preserved(self):
        _, text = mcp_pin.plan(UNRELATED_TOML, "1.0.0")
        for line in UNRELATED_TOML.strip().splitlines():
            self.assertIn(line, text)

    def test_body_fields_are_a_contract(self):
        body = mcp_pin.render_body("1.0.0")
        self.assertIn('command = "npx"', body)
        self.assertIn('args = ["-y", "claude-octopus@1.0.0"]', body)
        self.assertIn("startup_timeout_sec = 60", body)
        self.assertIn("tool_timeout_sec = 900", body)

    def test_unsentinelled_reserved_name_is_a_collision(self):
        hostile = f"[mcp_servers.{mcp_pin.SERVER_NAME}]\ncommand = \"theirs\"\n"
        self.assertIsNotNone(mcp_pin.collision(hostile))
        with self.assertRaises(mcp_pin.PinError):
            mcp_pin.plan(hostile, "1.0.0")

    def test_cc_suite_claude_code_table_is_not_ours(self):
        theirs = '[mcp_servers.claude-code]\ncommand = "npx"\n'
        self.assertIsNone(mcp_pin.collision(theirs))
        _, text = mcp_pin.plan(theirs, "1.0.0")
        self.assertIn("[mcp_servers.claude-code]", text)


class Probe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def run_probe(self, behaviour, timeout_ms=4000, binary=None):
        fake = binary or write_fake_server(self.d / "fake-npx", behaviour)
        self.argv_log = self.d / "argv.log"
        env = dict(os.environ, VIBE_SUITE_MCP_BIN=str(fake),
                   FAKE_ARGV_LOG=str(self.argv_log),
                   VIBE_SUITE_PROBE_TIMEOUT_MS=str(timeout_ms))
        return subprocess.run([  # noqa: S603
            "node", str(PROBE), "claude-octopus@1.2.3"],
            capture_output=True, text=True, timeout=90, env=env)

    def test_handshake_succeeds_against_a_responding_server(self):
        proc = self.run_probe("respond")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("claude-octopus", proc.stdout)

    # E7.1 (vibe-53) — the acceptance's mismatch contract: a self-report disagreeing with the
    # requested target on name or version, or lacking a usable version, fails loudly. Before
    # this contract the probe accepted any well-formed serverInfo.
    def test_name_mismatch_fails_loudly(self):
        proc = self.run_probe("wrong-name")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("mismatch", proc.stderr)
        self.assertIn("impostor-octopus", proc.stderr)
        self.assertIn("claude-octopus@1.2.3", proc.stderr)

    def test_version_mismatch_fails_loudly(self):
        proc = self.run_probe("wrong-version")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("mismatch", proc.stderr)
        self.assertIn("9.9.9", proc.stderr)
        self.assertIn("claude-octopus@1.2.3", proc.stderr)

    def test_missing_reported_version_fails(self):
        proc = self.run_probe("no-version")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("mismatch", proc.stderr)

    def test_malformed_reported_version_fails(self):
        proc = self.run_probe("bad-version")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("mismatch", proc.stderr)

    def test_missing_reported_name_fails_immediately(self):
        # An identity claim with no name must fail as a mismatch, not linger to the timeout.
        proc = self.run_probe("no-name")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("mismatch", proc.stderr)

    def test_malformed_reported_name_fails(self):
        proc = self.run_probe("bad-name")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("mismatch", proc.stderr)

    def test_spawn_argv_is_the_pinned_target(self):
        self.run_probe("respond")
        self.assertEqual(json.loads(self.argv_log.read_text().splitlines()[0]),
                         ["-y", "claude-octopus@1.2.3"])

    def test_mcp_error_is_a_failure(self):
        self.assertEqual(self.run_probe("error").returncode, 1)

    def test_early_exit_is_reported_not_hung(self):
        proc = self.run_probe("exit")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("exited before responding", proc.stderr)

    def test_timeout_reaps_the_process_group(self):
        before = self._descendants()
        proc = self.run_probe("hang", timeout_ms=1500)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("did not respond", proc.stderr)
        time.sleep(0.5)
        # The hanger spawns a child of its own. Killing only the direct child would leave it behind,
        # which is precisely what a process-group kill exists to prevent.
        self.assertLessEqual(self._descendants() - before, 0)

    def _descendants(self):
        out = subprocess.run(["ps", "-eo", "command"], capture_output=True, text=True).stdout
        return out.count("import time; time.sleep(300)")

    def test_seam_is_load_bearing(self):
        """If this passed with a nonexistent binary, the other probe tests would prove nothing."""
        proc = self.run_probe("respond", binary=self.d / "does-not-exist")
        self.assertEqual(proc.returncode, 1)


class RetiredNames(unittest.TestCase):
    def test_survivor_is_not_flagged(self):
        self.assertEqual(retired_names.scan_text("/vibe-suite:update refreshes bridges"), [])

    def test_retired_namespaces_are_flagged(self):
        self.assertEqual(retired_names.scan_text("run /cc-suite:init then /vibe:doctor"),
                         ["/cc-suite:", "/vibe:"])

    def test_shipped_update_surface_is_clean(self):
        self.assertEqual(retired_names.scan_update_surface(REPO_ROOT), [])

    def test_a_seeded_offender_in_that_surface_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "commands").mkdir()
            (root / "commands" / "update.md").write_text("see /grill:audit for details")
            self.assertEqual(retired_names.scan_update_surface(root),
                             [("commands/update.md", ["/grill:"])])

    def test_the_check_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "commands").mkdir()
            target = root / "commands" / "update.md"
            target.write_text("/nlpm:score")
            before = sorted(p.stat().st_mtime_ns for p in root.rglob("*"))
            retired_names.scan_update_surface(root)
            self.assertEqual(sorted(p.stat().st_mtime_ns for p in root.rglob("*")), before)


class SimulatedPluginUpdate(unittest.TestCase):
    """The acceptance clause, executed: an old managed pin and unrelated TOML meet a new plugin."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ws = self.root / "ws"
        (self.ws / ".codex").mkdir(parents=True)
        (self.ws / ".claude").mkdir(parents=True)
        self.plugin = self.root / "plugin-2.0.0"
        (self.plugin / "scripts" / "lib").mkdir(parents=True)
        (self.plugin / "skills").mkdir(parents=True)
        for rel in ("scripts/update.py", "scripts/bridge_cli.py"):
            (self.plugin / rel).write_bytes((REPO_ROOT / rel).read_bytes())
        for item in (REPO_ROOT / "scripts" / "lib").iterdir():
            if item.is_file():
                (self.plugin / "scripts" / "lib" / item.name).write_bytes(item.read_bytes())
        # The copied lib carries whatever pin state the real tree ships (pending before E7.1,
        # pin.txt after). Each test constructs its own premise via ship_pin()/explicit writes,
        # so the baseline plugin must carry neither file.
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.pending").unlink(missing_ok=True)
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.txt").unlink(missing_ok=True)
        # E7.2: bridge "all" now runs the mirrors leg. The fixture's mirror-sync.py is a tiny
        # driver (the documented fixture seam) — the production CLI stays un-overridable.
        # The driver IMPORTS the real generator and injects fixture sets through the
        # Python-API seam (the frozen A-5 design) — the production CLI stays un-overridable.
        (self.plugin / ".claude-plugin").mkdir(exist_ok=True)
        (self.plugin / ".claude-plugin" / "plugin.json").write_text(json.dumps(
            {"name": "vibe-suite", "version": "0.0.0-fixture", "description": "x",
             "commands": [], "agents": [], "skills": ["./skills/probe"]}) + "\n")
        probe = self.plugin / "skills" / "probe"
        probe.mkdir(parents=True, exist_ok=True)
        (probe / "SKILL.md").write_text(
            "---\nname: probe\ndescription: Probe knowledge.\n---\n\nprobe\n")
        (self.plugin / "scripts" / "mirror-sync.py").write_text(
            "#!/usr/bin/env python3\n# SPDX-License-Identifier: ISC\n"
            "import importlib.util, pathlib, sys\n"
            f"spec = importlib.util.spec_from_file_location('real_mirror_sync', "
            f"{str(REPO_ROOT / 'scripts' / 'mirror-sync.py')!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "root = pathlib.Path(sys.argv[sys.argv.index('--root') + 1])\n"
            "mod.generate(root, sets={'knowledge': ('probe',), 'workflow': (),\n"
            "                         'roast_agents': (), 'copied_deps': {},\n"
            "                         'auditing_partials': ()})\n"
            "print('fixture driver: generated via the API seam')\n", encoding="utf-8")

    def seed_stale_registration(self, pin="1.0.0"):
        stale = bridge.toml_server_upsert(UNRELATED_TOML, mcp_pin.SERVER_NAME,
                                          mcp_pin.render_body(pin))
        (self.ws / ".codex" / "config.toml").write_text(stale)

    def ship_pin(self, version="2.0.0"):
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.txt").write_text(version + "\n")

    def run_update(self, extra_env=None):
        fake = write_fake_server(self.root / "fake-npx", "respond")
        env = dict(os.environ, VIBE_SUITE_MCP_BIN=str(fake),
                   VIBE_SUITE_PROBE_TIMEOUT_MS="5000", **(extra_env or {}))
        return subprocess.run(
            [sys.executable, str(self.plugin / "scripts" / "update.py"),
             "--workspace", str(self.ws), "--plugin-root", str(self.plugin), "--json"],
            capture_output=True, text=True, timeout=180, env=env)

    def test_stale_pin_transitions_to_the_new_one(self):
        self.seed_stale_registration("1.0.0")
        self.ship_pin("2.0.0")
        proc = self.run_update()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        toml = (self.ws / ".codex" / "config.toml").read_text()
        self.assertIn("claude-octopus@2.0.0", toml)
        self.assertNotIn("claude-octopus@1.0.0", toml)
        self.assertEqual(toml.count(f"[mcp_servers.{mcp_pin.SERVER_NAME}]"), 1)
        # The user's own content survives the refresh untouched.
        self.assertIn("[mcp_servers.something-of-theirs]", toml)
        self.assertIn('theme = "dark"', toml)
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertEqual(stages["registration"]["status"], "ok")
        self.assertEqual(stages["probe"]["status"], "ok")

    def test_second_run_is_a_clean_no_op(self):
        self.seed_stale_registration("1.0.0")
        self.ship_pin("2.0.0")
        self.run_update()
        first = (self.ws / ".codex" / "config.toml").read_text()
        proc = self.run_update()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.ws / ".codex" / "config.toml").read_text(), first)
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertIn("current", stages["registration"]["detail"])

    def test_pending_state_still_refreshes_bridges(self):
        """The regression this ordering exists to prevent: S2 ships pending, so an early exit would
        make the command inert for the entire stage it ships in."""
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.pending").write_text("owner: E7.1")
        proc = self.run_update()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertIn("bridges", stages)
        self.assertNotIn("probe", stages)
        self.assertIn("E7.1", stages["pin"]["detail"])

    def test_collision_refuses_before_anything_is_written(self):
        (self.ws / ".codex" / "config.toml").write_text(
            f"[mcp_servers.{mcp_pin.SERVER_NAME}]\ncommand = \"theirs\"\n")
        before = (self.ws / ".codex" / "config.toml").read_text()
        self.ship_pin("2.0.0")
        proc = self.run_update()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual((self.ws / ".codex" / "config.toml").read_text(), before)
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertEqual(stages["registration"]["status"], "fail")
        self.assertNotIn("bridges", stages)

    def test_broken_installation_fails(self):
        proc = self.run_update()
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertEqual(stages["pin"]["status"], "fail")
        self.assertEqual(proc.returncode, 1)

    def test_no_retired_names_on_success_or_failure_paths(self):
        self.ship_pin("2.0.0")
        ok = self.run_update()
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.txt").write_text("latest\n")
        bad = self.run_update()
        for proc in (ok, bad):
            for stream in (proc.stdout, proc.stderr):
                self.assertEqual(retired_names.scan_text(stream), [], stream)


class Manifest(unittest.TestCase):
    def test_every_command_is_registered(self):
        """`update.md` was written and *not* registered, which would have shipped a command that
        does not exist. The invariant is cheap; the omission is not."""
        manifest = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        on_disk = {f"./commands/{p.name}" for p in (REPO_ROOT / "commands").glob("*.md")}
        self.assertEqual(set(manifest["commands"]), on_disk)


if __name__ == "__main__":
    unittest.main()


class TestAdvisorReconcileStage(unittest.TestCase):
    """E6.1: update reconciles advisors in every pin state; removal needs no backend."""

    def test_orphan_removed_and_stage_reported(self):
        ws = Path(tempfile.mkdtemp(prefix="vibe-update-advisors-"))
        self.addCleanup(__import__("shutil").rmtree, ws, ignore_errors=True)
        orphan = {"command": "npx", "args": ["-y", "claude-octopus@9.9.9"], "env": {},
                  "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}
        (ws / ".mcp.json").write_text(json.dumps(
            {"mcpServers": {"orphan_advisor": orphan}}, indent=2, sort_keys=True) + "\n")
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import update as update_mod
        report = update_mod.run(ws, REPO_ROOT, probe_timeout=1)
        stages = {s["stage"]: s for s in report.stages}
        self.assertIn("advisors", stages)
        self.assertIn("registered-undeclared->removed", stages["advisors"]["detail"])
        after = json.loads((ws / ".mcp.json").read_text())
        self.assertNotIn("orphan_advisor", after.get("mcpServers", {}))

    def test_reconcile_failure_surfaces_as_advisors_fail_stage(self):
        # E7.1 (vibe-53) characterization: when reconciliation cannot complete, the advisors
        # stage reports FAIL in /vibe-suite:update's report instead of dying silently. The seed
        # is a name collision — an unowned server squatting on a declared advisor's name —
        # which reconcile refuses in every pin state.
        ws = Path(tempfile.mkdtemp(prefix="vibe-update-advisors-"))
        self.addCleanup(__import__("shutil").rmtree, ws, ignore_errors=True)
        (ws / ".vibe-suite" / "agents").mkdir(parents=True)
        (ws / ".vibe-suite" / "agents" / "floaty.md").write_text(
            "---\n"
            "description: |\n"
            "  Judges floaty things.\n"
            "  <example>\n"
            "  Context: draft done.\n"
            '  user: "Check this?"\n'
            '  assistant: "Consulting floaty."\n'
            "  </example>\n"
            "  <example>\n"
            "  Context: rename sweep.\n"
            '  user: "Names ok?"\n'
            '  assistant: "Consulting floaty."\n'
            "  </example>\n"
            "model: sonnet\n"
            "max_turns: 4\n"
            "max_budget_usd: 0.40\n"
            "---\n\nValue the smallest true answer.\n", encoding="utf-8")
        squatter = {"command": "their-server"}
        (ws / ".mcp.json").write_text(json.dumps(
            {"mcpServers": {"floaty": squatter}}, indent=2, sort_keys=True) + "\n")
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import update as update_mod
        report = update_mod.run(ws, REPO_ROOT, probe_timeout=1)
        stages = {s["stage"]: s for s in report.stages}
        self.assertIn("advisors", stages)
        self.assertEqual(stages["advisors"]["status"], "fail")
        self.assertIn("floaty", stages["advisors"]["detail"])
        self.assertIn("unowned", stages["advisors"]["detail"])
