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
import re
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

import fsafe          # noqa: E402
import mcp_pin         # noqa: E402
import retired_names   # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmpdirs import TempDirMixin  # noqa: E402
import shutil  # noqa: E402
from unittest import mock  # noqa: E402
from octopus_fixture import (  # noqa: E402
    add_generation, bin_path, fixture_install, generation_of, legacy_body, legacy_entry,
    legacy_server_body, lockfile_sha256, lockfile_text, manifest_text, mark_verified, module_install,
    seam_env, shipped_pin, start_module_seams, stop_module_seams, write_fake_npm, write_fake_server)

SHIPPED = shipped_pin()
LAUNCH_RE = re.compile(r"/versions/([^/]+)/[^/]+/node_modules/claude-octopus/dist/index\.js$")


def setUpModule():
    # S13 (vibe-214): every renderer needs an installed, verified backend; nothing here may reach
    # `npm`, `npx` or the network. One fixture install for the module, in the process environment.
    start_module_seams("update", versions=("1.0.0", "2.0.0", "1.2.3", SHIPPED), lock_version=SHIPPED)


def tearDownModule():
    stop_module_seams("update")

UNRELATED_TOML = textwrap.dedent("""\
    # a comment the user wrote
    [mcp_servers.something-of-theirs]
    command = "their-server"

    [tui]
    theme = "dark"
    """)


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
        # S13: the path is the version-bearing token; a pin bump changes the body.
        self.assertIn("/versions/2.0.0/", moved)
        self.assertNotIn("/versions/1.0.0/", moved)
        self.assertNotIn('"npx"', moved)
        self.assertEqual(moved.count(f"[mcp_servers.{mcp_pin.SERVER_NAME}]"), 1)

    def test_unrelated_toml_is_preserved(self):
        _, text = mcp_pin.plan(UNRELATED_TOML, "1.0.0")
        for line in UNRELATED_TOML.strip().splitlines():
            self.assertIn(line, text)

    def test_body_fields_are_a_contract(self):
        # S13: the registration executes the lockfile-verified install by `node <bin>`; the path
        # carries the version and the generation.
        body = mcp_pin.render_body("1.0.0")
        inst = module_install("update")
        expected = bin_path(inst, "1.0.0", generation_of(inst, "1.0.0"))
        self.assertIn('command = "node"', body)
        self.assertIn(f'args = ["{expected}"]', body)
        self.assertNotIn("npx", body)
        self.assertIn("startup_timeout_sec = 60", body)
        self.assertIn("tool_timeout_sec = 900", body)

    def test_launch_refuses_an_uninstalled_or_mismatched_version(self):
        with tempfile.TemporaryDirectory() as td:
            inst = fixture_install(Path(td) / "inst", versions=("1.0.0",), lock_version="1.0.0")
            env = dict(os.environ, VIBE_SUITE_OCTOPUS_INSTALL_DIR=str(inst))
            # a version with no generation at all
            with self.assertRaises(mcp_pin.PinError):
                mcp_pin.launch("claude-octopus@3.0.0", env=env)
            gen = generation_of(inst, "1.0.0")
            command, args = mcp_pin.launch("claude-octopus@1.0.0", env=env)
            self.assertEqual((command, args), ("node", [bin_path(inst, "1.0.0", gen)]))
            # an explicit generation that is not a valid generation of that version
            with self.assertRaises(mcp_pin.PinError):
                mcp_pin.launch("claude-octopus@1.0.0", env=env, generation="nope")
            # a valid but UNVERIFIED generation with no verified sibling → no current generation
            inst2 = fixture_install(Path(td) / "inst2", versions=(), lock_version="1.0.0")
            add_generation(inst2, "1.0.0", verified=False)
            with self.assertRaises(mcp_pin.PinError):
                mcp_pin.launch("claude-octopus@1.0.0", env=dict(env, VIBE_SUITE_OCTOPUS_INSTALL_DIR=str(inst2)))
            # metadata version ≠ directory version
            inst3 = fixture_install(Path(td) / "inst3", versions=(), lock_version="1.0.0")
            add_generation(inst3, "1.0.0", metadata_version="1.0.1", verified=True)
            with self.assertRaises(mcp_pin.PinError):
                mcp_pin.launch("claude-octopus@1.0.0", env=dict(env, VIBE_SUITE_OCTOPUS_INSTALL_DIR=str(inst3)))
            # the bin deleted
            Path(bin_path(inst, "1.0.0", gen)).unlink()
            with self.assertRaises(mcp_pin.PinError):
                mcp_pin.launch("claude-octopus@1.0.0", env=env)

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
        inst = module_install("update")
        launch_bin = bin_path(inst, "1.2.3", generation_of(inst, "1.2.3"))
        # S13: `<target> <command> [args…]` — the probe spawns exactly what the registration will.
        return subprocess.run([  # noqa: S603
            "node", str(PROBE), "claude-octopus@1.2.3", str(fake), launch_bin],
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

    def test_probe_spawns_the_launch_not_npx(self):
        self.run_probe("respond")
        inst = module_install("update")
        argv = json.loads(self.argv_log.read_text().splitlines()[0])
        self.assertEqual(argv, [bin_path(inst, "1.2.3", generation_of(inst, "1.2.3"))])
        self.assertNotIn("-y", argv)

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
        for rel in ("scripts/update.py", "scripts/bridge_cli.py", "scripts/_bootstrap.py"):  # vibe-215: the programs bootstrap
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

    @property
    def install_dir(self):
        return self.plugin / "scripts" / "lib" / "claude-octopus"

    def seed_stale_registration(self, pin="1.0.0"):
        # The pre-S13 shape, seeded literally: `render_body` now renders the node launch.
        stale = bridge.toml_server_upsert(UNRELATED_TOML, mcp_pin.SERVER_NAME,
                                          legacy_server_body(pin))
        (self.ws / ".codex" / "config.toml").write_text(stale)

    def ship_pin(self, version="2.0.0"):
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.txt").write_text(version + "\n")
        # The shipped file pair for that pin; nothing installed — the (fake) npm installs.
        fixture_install(self.install_dir, versions=(), lock_version=version)

    def run_update(self, extra_env=None, npm="ok", server="respond", timeout_ms="5000"):
        fake = write_fake_server(self.root / f"fake-server-{server}", server)
        fake_npm = write_fake_npm(self.root / f"fake-npm-{npm}", npm)
        self.argv_log = self.root / "server-argv.log"
        self.npm_log = self.root / "npm.log"
        env = dict(os.environ, VIBE_SUITE_MCP_BIN=str(fake), VIBE_SUITE_NPM_BIN=str(fake_npm),
                   VIBE_SUITE_OCTOPUS_INSTALL_DIR=str(self.install_dir),
                   FAKE_ARGV_LOG=str(self.argv_log), FAKE_NPM_LOG=str(self.npm_log),
                   FAKE_NPM_PAYLOAD="run-" + npm,
                   VIBE_SUITE_PROBE_TIMEOUT_MS=timeout_ms, **(extra_env or {}))
        return subprocess.run(
            [sys.executable, str(self.plugin / "scripts" / "update.py"),
             "--workspace", str(self.ws), "--plugin-root", str(self.plugin), "--json"],
            capture_output=True, text=True, timeout=180, env=env)

    def stages(self, proc):
        return {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}

    def stores(self):
        toml = (self.ws / ".codex" / "config.toml")
        mcp = self.ws / ".mcp.json"
        return (toml.read_bytes() if toml.exists() else None, mcp.read_bytes() if mcp.exists() else None)

    def pin_dependent_stores(self):
        """Both stores minus the bridge stage's own `mcp-mirror` block. Bridges and mirrors run in
        every pin state by design (they are pin-independent); the acceptance's "unchanged" is about
        the pin-dependent content — the reverse-server block and every advisor registration."""
        toml, mcp = self.stores()
        if toml is not None:
            toml = bridge.text_block_remove(toml.decode("utf-8"), "mcp-mirror").encode("utf-8")
        return toml, mcp

    def register_advisor(self, name, pin, install_dir=None):
        """A stamped, registered advisor in `self.ws`, rendered against `install_dir` (which must hold
        a valid, verified generation of `pin`)."""
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / f"{name}.md").write_text(
            "---\ndescription: |\n  Judges things.\nmodel: sonnet\n---\n\nValue truth.\n", encoding="utf-8")
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import advisors as advisors_mod
        with mock.patch.dict(os.environ, {"VIBE_SUITE_OCTOPUS_INSTALL_DIR": str(install_dir or self.install_dir)}):
            advisors_mod.add(self.ws, name, pin=pin)

    def test_stale_pin_transitions_to_the_new_one(self):
        self.seed_stale_registration("1.0.0")
        self.ship_pin("2.0.0")
        proc = self.run_update()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        toml = (self.ws / ".codex" / "config.toml").read_text()
        # S13: the new block launches the installed generation by node; the legacy line is gone.
        self.assertIn("/versions/2.0.0/", toml)
        self.assertNotIn('args = ["-y", "claude-octopus@1.0.0"]', toml)
        self.assertNotIn("npx", toml.split("[mcp_servers.vibe-claude-mcp]")[1].split("[")[0])
        self.assertEqual(toml.count(f"[mcp_servers.{mcp_pin.SERVER_NAME}]"), 1)
        # The user's own content survives the refresh untouched.
        self.assertIn("[mcp_servers.something-of-theirs]", toml)
        self.assertIn('theme = "dark"', toml)
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertEqual(stages["install"]["status"], "ok")
        self.assertEqual(stages["probe"]["status"], "ok")
        self.assertEqual(stages["registration"]["status"], "ok")
        self.assertNotIn("prewarm", stages)
        # the stage order is the contract: install and probe precede advisors and registration
        order = [s["stage"] for s in json.loads(proc.stdout)["stages"]]
        self.assertLess(order.index("install"), order.index("probe"))
        self.assertLess(order.index("probe"), order.index("advisors"))
        self.assertLess(order.index("advisors"), order.index("registration"))

    def test_second_run_is_a_clean_no_op(self):
        self.seed_stale_registration("1.0.0")
        self.ship_pin("2.0.0")
        self.run_update()
        first = (self.ws / ".codex" / "config.toml").read_text()
        npm_calls = len(self.npm_log.read_text().splitlines())
        self.assertEqual(npm_calls, 1)
        proc = self.run_update()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.ws / ".codex" / "config.toml").read_text(), first)
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertIn("current", stages["registration"]["detail"])
        # the valid, verified generation is reused: npm is not invoked again
        self.assertEqual(len(self.npm_log.read_text().splitlines()), npm_calls)
        self.assertIn("already installed", stages["install"]["detail"])

    def test_pending_state_still_refreshes_bridges(self):
        """The regression this ordering exists to prevent: S2 ships pending, so an early exit would
        make the command inert for the entire stage it ships in."""
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.pending").write_text("owner: E7.1")
        proc = self.run_update()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        stages = {s["stage"]: s for s in json.loads(proc.stdout)["stages"]}
        self.assertIn("bridges", stages)
        self.assertNotIn("probe", stages)
        self.assertNotIn("install", stages)
        self.assertIn("E7.1", stages["pin"]["detail"])
        self.assertFalse(self.argv_log.exists(), "no server spawned in the pending state")
        self.assertFalse(self.npm_log.exists(), "npm not invoked in the pending state")

    def test_pending_state_removes_orphans_without_spawning(self):
        (self.plugin / "scripts" / "lib" / "claude-octopus-pin.pending").write_text("owner: E7.1")
        orphan = {"command": "npx", "args": ["-y", "claude-octopus@9.9.9"], "env": {},
                  "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {"orphan_advisor": orphan}}, indent=2) + "\n")
        proc = self.run_update()
        stages = self.stages(proc)
        self.assertEqual(stages["advisors"]["status"], "ok", stages["advisors"])
        self.assertIn("registered-undeclared->removed", stages["advisors"]["detail"])
        self.assertNotIn("orphan_advisor", json.loads((self.ws / ".mcp.json").read_text()).get("mcpServers", {}))
        self.assertFalse(self.argv_log.exists())
        self.assertFalse(self.npm_log.exists())

    SKIPPED_TEXT = "not boot-verified this run"

    def _seed_stale_and_advisor(self):
        """A legacy stale reverse-server block plus a registered advisor on 1.0.0 — the two things a
        failing run must leave byte-identical."""
        self.seed_stale_registration("1.0.0")
        self.ship_pin("2.0.0")
        add_generation(self.install_dir, "1.0.0", verified=True)
        (self.ws / ".mcp.json").write_text('{"mcpServers": {}}\n')
        self.register_advisor("held_one", "1.0.0")
        return self.pin_dependent_stores()

    def test_a_tampered_lockfile_is_refused_before_any_server_starts(self):
        before = self._seed_stale_and_advisor()
        proc = self.run_update(npm="eintegrity")
        stages = self.stages(proc)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(stages["install"]["status"], "fail", stages["install"])
        self.assertIn("EINTEGRITY", stages["install"]["detail"])
        self.assertEqual(stages["advisors"]["status"], "warn")
        self.assertIn(self.SKIPPED_TEXT, stages["advisors"]["detail"])
        self.assertNotIn("probe", stages)
        self.assertNotIn("registration", stages)
        self.assertEqual(self.pin_dependent_stores(), before)
        self.assertFalse(self.argv_log.exists(), "no server was started")
        self.assertEqual([p.name for p in (self.install_dir / "versions" / "2.0.0").iterdir()] if (self.install_dir / "versions" / "2.0.0").exists() else [], [])

    def test_probe_failure_leaves_both_stores_unchanged(self):
        before = self._seed_stale_and_advisor()
        proc = self.run_update(server="wrong-version")
        stages = self.stages(proc)
        self.assertEqual(stages["install"]["status"], "ok", stages["install"])
        self.assertEqual(stages["probe"]["status"], "fail")
        self.assertEqual(stages["advisors"]["status"], "warn")
        self.assertIn(self.SKIPPED_TEXT, stages["advisors"]["detail"])
        self.assertNotIn("registration", stages)
        self.assertEqual(self.pin_dependent_stores(), before)
        # the new generation exists but is NOT verified
        gens = [p for p in (self.install_dir / "versions" / "2.0.0").iterdir() if p.is_dir()]
        self.assertEqual(len(gens), 1)
        self.assertEqual(list((self.install_dir / "versions" / "2.0.0").glob("*.verified")), [])

    def test_probe_timeout_is_the_same_skipped_contract(self):
        before = self._seed_stale_and_advisor()
        proc = self.run_update(server="hang", timeout_ms="1500")
        stages = self.stages(proc)
        self.assertEqual(stages["probe"]["status"], "fail")
        self.assertEqual(stages["advisors"]["status"], "warn")
        self.assertIn(self.SKIPPED_TEXT, stages["advisors"]["detail"])
        self.assertNotIn("registration", stages)
        self.assertEqual(self.pin_dependent_stores(), before)
        self.assertEqual(list((self.install_dir / "versions" / "2.0.0").glob("*.verified")), [])

    def test_an_older_install_is_retained_after_a_pin_bump(self):
        self._seed_stale_and_advisor()
        old_gen = generation_of(self.install_dir, "1.0.0")
        old_bin = Path(bin_path(self.install_dir, "1.0.0", old_gen))
        old_bytes = old_bin.read_bytes()
        held_before = json.loads((self.ws / ".mcp.json").read_text())["mcpServers"]["held_one"]
        # make the advisor HELD (edited after registration) so update leaves it on 1.0.0
        defn = self.ws / ".vibe-suite" / "agents" / "held_one.md"
        defn.write_text(defn.read_text().replace("Value truth.", "Value truth, edited."), encoding="utf-8")
        proc = self.run_update()
        stages = self.stages(proc)
        self.assertEqual(stages["registration"]["status"], "ok", stages)
        self.assertTrue(old_bin.is_file(), "the older generation is retained")
        self.assertEqual(old_bin.read_bytes(), old_bytes)
        self.assertEqual(json.loads((self.ws / ".mcp.json").read_text())["mcpServers"]["held_one"], held_before)
        self.assertIn("1.0.0", stages["install"]["detail"])
        self.assertNotIn("prune", stages)

    def test_a_same_version_lockfile_change_with_a_failed_probe_keeps_the_old_generation_launchable(self):
        self.ship_pin("2.0.0")
        h1 = add_generation(self.install_dir, "2.0.0", verified=True, payload="H1")
        h1_bin = Path(bin_path(self.install_dir, "2.0.0", h1))
        (self.ws / ".mcp.json").write_text('{"mcpServers": {}}\n')
        self.register_advisor("held_one", "2.0.0")
        # reverse-server block on H1 too
        with mock.patch.dict(os.environ, {"VIBE_SUITE_OCTOPUS_INSTALL_DIR": str(self.install_dir)}):
            _, text = mcp_pin.plan(UNRELATED_TOML, "2.0.0")
        (self.ws / ".codex" / "config.toml").write_text(text)
        before = self.pin_dependent_stores()
        # the shipped lockfile changes (H2) → a new generation is built; the probe fails
        (self.install_dir / "package-lock.json").write_text(
            lockfile_text("2.0.0", integrity="sha512-" + "B" * 86 + "=="), encoding="utf-8")
        proc = self.run_update(server="wrong-version")
        stages = self.stages(proc)
        self.assertEqual(stages["install"]["status"], "ok")
        self.assertEqual(stages["probe"]["status"], "fail")
        self.assertNotIn("registration", stages)
        self.assertEqual(self.pin_dependent_stores(), before)
        self.assertTrue(h1_bin.is_file())
        self.assertIn("payload: H1", h1_bin.read_text())
        gens = sorted(p.name for p in (self.install_dir / "versions" / "2.0.0").iterdir() if p.is_dir())
        self.assertEqual(len(gens), 2, gens)
        self.assertEqual(list((self.install_dir / "versions" / "2.0.0").glob("*.verified")),
                         [self.install_dir / "versions" / "2.0.0" / f"{h1}.verified"])

    def _crash_advisor_cli(self, *args, fail_after):
        return subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "advisor_cli.py"),
                               "--workspace", str(self.ws), *args], capture_output=True, text=True,
                              env=dict(os.environ, VIBE_ADVISOR_FAIL_AFTER=fail_after,
                                       VIBE_SUITE_OCTOPUS_INSTALL_DIR=str(self.install_dir)))

    def _declare(self, name):
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / f"{name}.md").write_text(
            "---\ndescription: |\n  Judges things.\nmodel: sonnet\n---\n\nValue truth.\n", encoding="utf-8")

    def test_a_pending_apply_journal_is_recovered_before_the_registration_is_written(self):
        self.seed_stale_registration("1.0.0")           # the legacy block is in the pre-image
        self.ship_pin("2.0.0")
        (self.ws / ".mcp.json").write_text('{"mcpServers": {}}\n')
        self._declare("journaled")
        crashed = self._crash_advisor_cli("add", "journaled", "--pin", "2.0.0", fail_after="json")
        # `add` rendered against an install that has no 2.0.0 yet: either it refused (no journal) or
        # it crashed with a journal — the recovery-before-registration property needs the journal.
        if not (self.ws / ".vibe-suite-state" / "advisor-txn.json").is_file():
            add_generation(self.install_dir, "2.0.0", verified=True)
            crashed = self._crash_advisor_cli("add", "journaled", "--pin", "2.0.0", fail_after="json")
        self.assertEqual(crashed.returncode, 9, crashed.stderr)
        self.assertTrue((self.ws / ".vibe-suite-state" / "advisor-txn.json").is_file())
        proc = self.run_update()
        stages = self.stages(proc)
        self.assertEqual(stages["registration"]["status"], "ok", stages)
        self.assertFalse((self.ws / ".vibe-suite-state" / "advisor-txn.json").exists(), "journal recovered")
        toml = (self.ws / ".codex" / "config.toml").read_text()
        block = toml.split("[mcp_servers.vibe-claude-mcp]")[1].split("# <<<")[0]
        self.assertIn("/versions/2.0.0/", block)
        self.assertNotIn("npx", block)

    def test_a_pending_remove_journal_is_rolled_forward_before_the_registration_is_written(self):
        self.seed_stale_registration("1.0.0")
        self.ship_pin("2.0.0")
        add_generation(self.install_dir, "2.0.0", verified=True)
        (self.ws / ".mcp.json").write_text('{"mcpServers": {}}\n')
        self.register_advisor("doomed", "2.0.0")
        crashed = self._crash_advisor_cli("remove", "doomed", fail_after="json")
        self.assertEqual(crashed.returncode, 9, crashed.stderr)
        self.assertTrue((self.ws / ".vibe-suite-state" / "advisor-txn.json").is_file())
        proc = self.run_update()
        stages = self.stages(proc)
        self.assertEqual(stages["registration"]["status"], "ok", stages)
        self.assertFalse((self.ws / ".vibe-suite-state" / "advisor-txn.json").exists())
        toml = (self.ws / ".codex" / "config.toml").read_text()
        block = toml.split("[mcp_servers.vibe-claude-mcp]")[1].split("# <<<")[0]
        self.assertIn("/versions/2.0.0/", block)
        self.assertNotIn("npx", block)
        self.assertNotIn("doomed", json.loads((self.ws / ".mcp.json").read_text()).get("mcpServers", {}))

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



# ---------------------------------------------------------------------------------------------
# S13 (vibe-214): the lockfile-verified install
# ---------------------------------------------------------------------------------------------

def _octopus_install():
    import octopus_install  # noqa: E402  (absent at the RED baseline — that is the point)
    return octopus_install


class Lockfile(unittest.TestCase):
    """The shipped manifest/lockfile pair is the recorded integrity; it must agree with the pin."""

    def test_shipped_lockfile_matches_the_pin(self):
        d = REPO_ROOT / "scripts" / "lib" / "claude-octopus"
        self.assertTrue((d / "package.json").is_file(), "shipped package.json absent")
        self.assertTrue((d / "package-lock.json").is_file(), "shipped package-lock.json absent")
        manifest = json.loads((d / "package.json").read_text())
        lock = json.loads((d / "package-lock.json").read_text())
        self.assertEqual(manifest["dependencies"], {"claude-octopus": SHIPPED})
        self.assertTrue(manifest.get("private") is True)
        self.assertEqual(lock["lockfileVersion"], 3)
        pk = lock["packages"]
        self.assertEqual(pk[""]["dependencies"]["claude-octopus"], SHIPPED)
        entry = pk["node_modules/claude-octopus"]
        self.assertEqual(entry["version"], SHIPPED)
        self.assertTrue(entry["integrity"].startswith("sha512-"), entry.get("integrity"))
        self.assertEqual(entry.get("bin"), {"claude-octopus": "dist/index.js"})
        missing = [k for k, v in pk.items() if k and "integrity" not in v]
        self.assertEqual(missing, [], "non-root entries without integrity")
        self.assertGreater(len(pk) - 1, 1, "a real resolved tree has more than one package")


class Install(unittest.TestCase):
    """`octopus_install.ensure_installed` — the install stage, against a fake npm."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = Path(self.tmp.name)
        self.pin = "2.0.0"
        self.inst = fixture_install(self.d / "inst", versions=(), lock_version=self.pin)
        self.log = self.d / "npm.log"
        self.oi = _octopus_install()

    def env(self, npm="ok", payload="P", **extra):
        fake = write_fake_npm(self.d / f"npm-{npm}", npm)
        e = dict(os.environ, VIBE_SUITE_OCTOPUS_INSTALL_DIR=str(self.inst), VIBE_SUITE_NPM_BIN=str(fake),
                 FAKE_NPM_LOG=str(self.log), FAKE_NPM_PAYLOAD=payload, **extra)
        return e

    def gens(self, version=None):
        v = self.inst / "versions" / (version or self.pin)
        return sorted(p.name for p in v.iterdir() if p.is_dir()) if v.exists() else []

    def staging(self):
        v = self.inst / "versions"
        return sorted(p.name for p in v.iterdir() if p.name.startswith(".staging-")) if v.exists() else []

    def npm_calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def snapshot(self, version, gen):
        root = self.inst / "versions" / version / gen
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    # 1
    def test_ok_installs_and_publishes_the_version_dir(self):
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertEqual(self.gens(), [gen])
        self.assertTrue(Path(bin_path(self.inst, self.pin, gen)).is_file())
        marker = json.loads((self.inst / "versions" / self.pin / gen / ".vibe-suite-install.json").read_text())
        self.assertEqual(marker["version"], self.pin)
        self.assertEqual(marker["lockfile_sha256"], lockfile_sha256(self.inst))
        self.assertEqual(marker["generation"], gen)
        self.assertEqual(self.staging(), [])

    # 2
    def test_npm_is_invoked_as_ci_ignore_scripts_in_the_staging_dir(self):
        self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        calls = self.npm_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["argv"], ["ci", "--ignore-scripts", "--no-audit", "--no-fund"])
        self.assertIn("/versions/.staging-", calls[0]["cwd"])
        self.assertTrue(Path(calls[0]["cwd"]).resolve().is_relative_to(self.inst.resolve()))

    # 3
    def test_eintegrity_exit_status_alone_is_a_failure(self):
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env("eintegrity"), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("EINTEGRITY", detail)
        self.assertIsNone(gen)
        self.assertEqual(self.gens(), [])
        self.assertEqual(self.staging(), [])

    # 4
    def test_partial_tree_is_removed_on_failure(self):
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env("partial"), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertEqual(self.staging(), [])
        self.assertEqual(self.gens(), [])

    # 5
    def test_wrong_installed_version_is_a_failure(self):
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env("wrong-version"), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("9.9.9", detail)
        self.assertEqual(self.gens(), [])
        self.assertEqual(self.staging(), [])

    # 6
    def test_missing_bin_is_a_failure(self):
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(FAKE_NPM_NO_BIN="1"), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("dist/index.js", detail)
        self.assertEqual(self.gens(), [])

    # 7
    @unittest.skipIf(os.geteuid() == 0, "root ignores directory modes")
    def test_unwritable_install_dir_fails_closed(self):
        (self.inst / "versions").mkdir()
        os.chmod(self.inst / "versions", 0o500)
        self.addCleanup(os.chmod, self.inst / "versions", 0o700)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertEqual(self.npm_calls(), [], "nothing was installed")

    # 8
    def test_matching_marker_skips_npm(self):
        g = add_generation(self.inst, self.pin, verified=False)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual((status, gen), (self.oi.OK, g))
        self.assertIn("already installed", detail)
        self.assertEqual(self.npm_calls(), [])

    # 9
    def test_a_corrupted_generation_is_left_alone_and_a_new_one_is_built(self):
        g1 = add_generation(self.inst, self.pin, payload="old", verified=True)
        Path(bin_path(self.inst, self.pin, g1)).unlink()
        before = self.snapshot(self.pin, g1)
        status, detail, g2 = self.oi.ensure_installed(self.pin, env=self.env(payload="new"), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertNotEqual(g2, g1)
        self.assertEqual(sorted(self.gens()), sorted([g1, g2]))
        self.assertEqual(self.snapshot(self.pin, g1), before, "the corrupted generation is untouched")
        self.assertIn("payload: new", Path(bin_path(self.inst, self.pin, g2)).read_text())
        self.assertEqual(self.oi.current_valid_generation(self.pin, env=self.env()), g2)

    # 10
    def test_a_metadata_mismatched_generation_is_not_current(self):
        g1 = add_generation(self.inst, self.pin, metadata_version="2.0.1", verified=True)
        before = self.snapshot(self.pin, g1)
        self.assertIsNone(self.oi.current_valid_generation(self.pin, env=self.env()))
        status, detail, g2 = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertNotEqual(g2, g1)
        self.assertEqual(self.snapshot(self.pin, g1), before)

    # 11
    def test_a_changed_lockfile_builds_a_new_generation_and_keeps_the_old(self):
        h1 = add_generation(self.inst, self.pin, payload="H1", verified=True)
        h1_bytes = Path(bin_path(self.inst, self.pin, h1)).read_bytes()
        (self.inst / "package-lock.json").write_text(
            lockfile_text(self.pin, integrity="sha512-" + "B" * 86 + "=="), encoding="utf-8")
        status, detail, h2 = self.oi.ensure_installed(self.pin, env=self.env(payload="H2"), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertNotEqual(h2, h1)
        marker = json.loads((self.inst / "versions" / self.pin / h2 / ".vibe-suite-install.json").read_text())
        self.assertEqual(marker["lockfile_sha256"], lockfile_sha256(self.inst))
        h2_bin = Path(bin_path(self.inst, self.pin, h2))
        self.assertIn("payload: H2", h2_bin.read_text())
        self.assertEqual(Path(bin_path(self.inst, self.pin, h1)).read_bytes(), h1_bytes)
        self.assertEqual(self.oi.current_valid_generation(self.pin, env=self.env()), h2)

    # 12
    def test_a_marker_less_directory_is_not_a_generation(self):
        stray = add_generation(self.inst, self.pin, name="x-stray", with_marker=False)
        before = self.snapshot(self.pin, stray)
        self.assertIsNone(self.oi.current_valid_generation(self.pin, env=self.env()))
        status, detail, g = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertNotEqual(g, stray)
        self.assertEqual(self.snapshot(self.pin, stray), before, "never stamped")

    # 13
    def test_lockfile_pin_mismatch_is_refused_before_npm_runs(self):
        good_lock = lockfile_text(self.pin)
        cases = {
            "entry version": ("package-lock.json", lockfile_text(self.pin, entry_version="1.0.0")),
            "lockfileVersion 2": ("package-lock.json", lockfile_text(self.pin, lockfile_version=2)),
            "entry without integrity": ("package-lock.json", lockfile_text(self.pin, drop_integrity=True)),
            "root dependency": ("package-lock.json", lockfile_text(self.pin, root_dependency="1.0.0")),
            "manifest dependency": ("package.json", manifest_text("1.0.0")),
        }
        for label, (fname, text) in cases.items():
            with self.subTest(case=label):
                (self.inst / "package-lock.json").write_text(good_lock, encoding="utf-8")
                (self.inst / "package.json").write_text(manifest_text(self.pin), encoding="utf-8")
                (self.inst / fname).write_text(text, encoding="utf-8")
                status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
                self.assertEqual(status, self.oi.FAIL, label)
                self.assertIn("lockfile refused", detail)
                self.assertIsNone(gen)
                self.assertEqual(self.npm_calls(), [], "npm must not run on a refused lockfile")

    # 14
    def test_a_previous_generation_survives_a_failed_install(self):
        old = add_generation(self.inst, "1.0.0", payload="old", verified=True)
        before = self.snapshot("1.0.0", old)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env("fail"), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertEqual(self.snapshot("1.0.0", old), before)
        self.assertEqual(self.gens("1.0.0"), [old])
        self.assertEqual(self.staging(), [])

    # 15
    def test_a_failed_publish_rename_removes_only_the_staging(self):
        import errno
        old = add_generation(self.inst, "1.0.0", verified=True)
        before = self.snapshot("1.0.0", old)
        for label, exc in (("BridgeError", fsafe.BridgeError("x")), ("OSError", OSError(errno.EXDEV, "x"))):
            with self.subTest(case=label):
                with mock.patch.object(fsafe, "rename_at", side_effect=exc):
                    status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
                self.assertEqual(status, self.oi.FAIL, detail)
                self.assertIsNone(gen)
                self.assertEqual(self.gens(), [])
                self.assertEqual(self.staging(), [])
                self.assertEqual(self.snapshot("1.0.0", old), before)

    # 16
    def test_two_concurrent_installs_publish_two_generations(self):
        status, detail, ours = self.oi.ensure_installed(self.pin, env=self.env("ok-and-plant-winner"), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        gens = self.gens()
        self.assertEqual(len(gens), 2, gens)
        self.assertIn(ours, gens)
        winner = [g for g in gens if g != ours][0]
        for g in gens:
            self.assertTrue((self.inst / "versions" / self.pin / g / ".vibe-suite-install.json").is_file())
        self.assertTrue((self.inst / "versions" / self.pin / f"{winner}.verified").is_file(), "winner's mark untouched")
        self.assertEqual(self.oi.current_valid_generation(self.pin, env=self.env()), max(gens))
        self.assertEqual(self.staging(), [])

    # 17
    def test_only_our_own_staging_is_removed(self):
        foreign = self.inst / "versions" / ".staging-99999-x"
        foreign.mkdir(parents=True)
        (foreign / "keep").write_text("x")
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertTrue((foreign / "keep").is_file(), "a foreign staging directory is never removed")
        self.assertIn(".staging-99999-x", detail)
        self.assertEqual(self.staging(), [".staging-99999-x"])

    # 18
    def test_a_symlinked_install_dir_is_refused(self):
        real = self.d / "elsewhere"
        real.mkdir()
        link = self.d / "link"
        link.symlink_to(real, target_is_directory=True)
        env = self.env()
        env["VIBE_SUITE_OCTOPUS_INSTALL_DIR"] = str(link)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=env, timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("symlink", detail)
        self.assertEqual(sorted(p.name for p in real.iterdir()), [], "nothing created behind the link")
        self.assertEqual(self.npm_calls(), [])

    # 19
    def test_a_symlinked_versions_dir_is_refused(self):
        elsewhere = self.d / "elsewhere-versions"
        elsewhere.mkdir()
        (self.inst / "versions").symlink_to(elsewhere, target_is_directory=True)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertEqual(sorted(p.name for p in elsewhere.iterdir()), [], "no staging created through the link")
        self.assertEqual(self.npm_calls(), [])

    # 20
    def test_cleanup_error_is_reported_and_the_status_stays_fail(self):
        with mock.patch.object(fsafe, "remove_tree_at", side_effect=fsafe.BridgeError("cleanup boom")):
            status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env("partial"), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("EINTEGRITY", detail)
        self.assertIn("cleanup boom", detail)

    # 21
    def test_retained_generations_are_listed_in_the_detail(self):
        old = add_generation(self.inst, "1.0.0", verified=True)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertIn(f"1.0.0/{old}", detail)
        retained = self.oi.retained_generations(self.pin, env=self.env())
        self.assertIn(("1.0.0", old), [(r["version"], r["generation"]) for r in retained])

    # 22
    def test_the_marker_is_inside_the_staged_tree_before_the_rename(self):
        seen = {}
        real = fsafe.rename_at

        def spy(root, src_rel, dst_rel):
            seen["marker_in_source"] = (Path(root) / src_rel / ".vibe-suite-install.json").is_file()
            return real(root, src_rel, dst_rel)
        with mock.patch.object(fsafe, "rename_at", side_effect=spy):
            status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertTrue(seen.get("marker_in_source"), "the marker must be written into the staged tree first")

    # 23
    def test_a_fresh_generation_is_valid_but_not_verified(self):
        older = add_generation(self.inst, self.pin, name="a-older", verified=True)
        (self.inst / "package-lock.json").write_text(
            lockfile_text(self.pin, integrity="sha512-" + "C" * 86 + "=="), encoding="utf-8")
        env = self.env()
        status, detail, gen = self.oi.ensure_installed(self.pin, env=env, timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertEqual(self.oi.current_valid_generation(self.pin, env=env), gen)
        self.assertIsNone(self.oi.current_verified_generation(self.pin, env=env),
                          "the older generation's lockfile sha no longer matches; the new one is unverified")
        self.oi.mark_verified(self.pin, gen, env=env)
        self.assertEqual(self.oi.current_verified_generation(self.pin, env=env), gen)
        mark = self.inst / "versions" / self.pin / f"{gen}.verified"
        first = mark.read_bytes()
        self.oi.mark_verified(self.pin, gen, env=env)          # idempotent: publish_new reports, never overwrites
        self.assertEqual(mark.read_bytes(), first)

    # 25 (Step-8 R1)
    def test_corrupt_metadata_is_an_invalid_generation_not_a_crash(self):
        g = add_generation(self.inst, self.pin, verified=True)
        meta = self.inst / "versions" / self.pin / g / "node_modules" / "claude-octopus" / "package.json"
        for junk in ("[]", "null", "not json", '"str"'):
            with self.subTest(junk=junk):
                meta.write_text(junk, encoding="utf-8")
                env = self.env()
                self.assertIsNone(self.oi.current_valid_generation(self.pin, env=env))
                self.assertIsNone(self.oi.current_verified_generation(self.pin, env=env))
                self.assertFalse(self.oi.is_valid_generation(self.pin, g, env))
        status, detail, g2 = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.OK, detail)
        self.assertNotEqual(g2, g)

    # 26 (Step-8 R1)
    def test_a_missing_lockfile_is_a_pin_error_not_a_file_not_found(self):
        g = add_generation(self.inst, self.pin, verified=True)
        (self.inst / "package-lock.json").unlink()
        env = self.env()
        self.assertIsNone(self.oi.current_verified_generation(self.pin, env=env))
        self.assertIsNone(self.oi.current_valid_generation(self.pin, env=env))
        with self.assertRaises(mcp_pin.PinError):
            mcp_pin.launch(f"claude-octopus@{self.pin}", env=env, generation=g)
        with self.assertRaises(mcp_pin.PinError):
            mcp_pin.launch(f"claude-octopus@{self.pin}", env=env)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=env, timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertEqual(self.npm_calls(), [])

    # 27 (Step-8 R1)
    @unittest.skipIf(os.geteuid() == 0, "root ignores directory modes")
    def test_an_unreadable_versions_dir_is_no_generation_and_a_failed_install(self):
        add_generation(self.inst, self.pin, verified=True)
        os.chmod(self.inst / "versions", 0o000)
        self.addCleanup(os.chmod, self.inst / "versions", 0o700)
        env = self.env()
        self.assertIsNone(self.oi.current_verified_generation(self.pin, env=env))
        with self.assertRaises(mcp_pin.PinError):
            mcp_pin.launch(f"claude-octopus@{self.pin}", env=env)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=env, timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertEqual(self.npm_calls(), [])

    # 28 (Step-8 R3)
    def test_a_symlinked_versions_dir_with_a_valid_generation_is_refused(self):
        real = fixture_install(self.d / "real", versions=(self.pin,), lock_version=self.pin)
        # the linked target holds a complete, valid, verified generation whose marker names OUR lockfile sha
        (self.inst / "versions").symlink_to(real / "versions", target_is_directory=True)
        env = self.env()
        self.assertIsNone(self.oi.current_valid_generation(self.pin, env=env))
        self.assertIsNone(self.oi.current_verified_generation(self.pin, env=env))
        with self.assertRaises(mcp_pin.PinError):
            mcp_pin.launch(f"claude-octopus@{self.pin}", env=env)
        status, detail, gen = self.oi.ensure_installed(self.pin, env=env, timeout=60)
        self.assertEqual(status, self.oi.FAIL, detail)
        self.assertIn("not a real directory", detail)
        self.assertEqual(self.npm_calls(), [], "nothing reused or built through the link")

    # 29 (Step-8 R4)
    def test_a_second_dependency_without_integrity_is_refused(self):
        (self.inst / "package-lock.json").write_text(lockfile_text(
            self.pin, extra_packages={"leftpad": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/leftpad/-/leftpad-1.0.0.tgz"}}),
            encoding="utf-8")
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("leftpad", detail)
        self.assertEqual(self.npm_calls(), [])

    # 30 (Step-8 R4)
    def test_npm_timeout_is_a_failure_with_staging_removed(self):
        status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env("hang"), timeout=1)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("did not finish", detail)
        self.assertEqual(self.staging(), [])
        self.assertEqual(self.gens(), [])

    # 31 (Step-8 R4)
    def test_a_missing_npm_executable_is_a_failure_with_staging_removed(self):
        env = self.env()
        env["VIBE_SUITE_NPM_BIN"] = str(self.d / "no-such-npm")
        status, detail, gen = self.oi.ensure_installed(self.pin, env=env, timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("could not run", detail)
        self.assertEqual(self.staging(), [])

    # 32 (Step-9 R1 residue)
    def test_malformed_manifest_dependencies_are_refused_before_npm(self):
        for junk in ('["bad"]', '"bad"', '1', 'null'):
            with self.subTest(junk=junk):
                (self.inst / "package.json").write_text(
                    '{"name": "x", "private": true, "dependencies": ' + junk + '}', encoding="utf-8")
                status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
                self.assertEqual(status, self.oi.FAIL)
                self.assertIn("lockfile refused", detail)
                self.assertEqual(self.npm_calls(), [])
        (self.inst / "package.json").write_text('{"dependencies": ["bad"]}', encoding="utf-8")
        self.assertIn("package.json pins", self.oi.lockfile_check(self.pin, env=self.env()) or "")

    # 33 (Step-9 R1 residue)
    def test_an_oserror_inspecting_the_staged_tree_is_a_failure_with_cleanup(self):
        real = Path.is_file

        def denied(self_):
            if self_.name == "index.js" and "/versions/.staging-" in str(self_):
                raise PermissionError("denied")
            return real(self_)
        with mock.patch.object(Path, "is_file", denied):
            status, detail, gen = self.oi.ensure_installed(self.pin, env=self.env(), timeout=60)
        self.assertEqual(status, self.oi.FAIL)
        self.assertIn("denied", detail)
        self.assertIsNone(gen)
        self.assertEqual(self.staging(), [], "the run's staging is removed even when the gate itself failed")
        self.assertEqual(self.gens(), [])

    # 24
    def test_the_verification_mark_lives_beside_the_generation_not_inside_it(self):
        env = self.env()
        status, detail, gen = self.oi.ensure_installed(self.pin, env=env, timeout=60)
        before = self.snapshot(self.pin, gen)
        self.oi.mark_verified(self.pin, gen, env=env)
        self.assertEqual(self.snapshot(self.pin, gen), before, "the generation tree is immutable")
        self.assertTrue((self.inst / "versions" / self.pin / f"{gen}.verified").is_file())


class _InProcessBase(TempDirMixin, unittest.TestCase):
    """Shared harness: `update.run` in-process with the seams pointed at a per-test install."""

    def setUp(self):
        self.d = Path(self.mkdtemp(prefix="vibe-inproc-"))
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import update as update_mod
        import advisors as advisors_mod
        self.update_mod, self.advisors = update_mod, advisors_mod
        self.oi = _octopus_install()

    def workspace(self, name):
        ws = self.d / name
        (ws / ".codex").mkdir(parents=True)
        (ws / ".claude").mkdir(parents=True)
        (ws / ".mcp.json").write_text('{"mcpServers": {}}\n')
        return ws

    def declare(self, ws, name):
        agents = ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / f"{name}.md").write_text(
            "---\ndescription: |\n  Judges things.\nmodel: sonnet\n---\n\nValue truth.\n", encoding="utf-8")

    def seams(self, inst, npm="ok", server="respond"):
        fake_npm = write_fake_npm(self.d / f"npm-{npm}", npm)
        fake_server = write_fake_server(self.d / f"server-{server}", server)
        return dict(seam_env(inst, fake_npm, fake_server), FAKE_NPM_LOG=str(self.d / "npm.log"),
                    FAKE_ARGV_LOG=str(self.d / "argv.log"), VIBE_SUITE_PROBE_TIMEOUT_MS="1500")

    def launch_paths(self, ws):
        doc = json.loads((ws / ".mcp.json").read_text())
        toml = (ws / ".codex" / "config.toml").read_text()
        json_paths = {n: e["args"][-1] for n, e in doc["mcpServers"].items() if self.advisors.is_owned_entry(e)}
        toml_paths = re.findall(r'args = \["([^"]+)"\]', toml)
        return json_paths, toml_paths



class InProcessUpdate(_InProcessBase):
    """The selection freeze and the production mark write."""

    def test_a_generation_published_after_the_probe_is_not_registered_this_run(self):
        inst = fixture_install(self.d / "inst", versions=(), lock_version=SHIPPED)
        ws = self.workspace("ws")
        # a stamped advisor registered against the module fixture's generation (stale here), and a
        # stamped definition whose entries are then removed from both stores (the presence-only path)
        for name in ("moves", "presence"):
            self.declare(ws, name)
            self.advisors.add(ws, name)
        doc = json.loads((ws / ".mcp.json").read_text())
        del doc["mcpServers"]["presence"]
        (ws / ".mcp.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        toml_p = ws / ".codex" / "config.toml"
        toml_p.write_text(bridge.toml_server_remove(toml_p.read_text(), "presence"))
        env = self.seams(inst)
        planted = {}

        def probe_then_plant(target, launch, env_, timeout):
            planted["gen"] = add_generation(inst, SHIPPED, name="zzzz-later-99999", verified=True, payload="later")
            return self.update_mod.OK, "ok (planted a later generation)"
        with mock.patch.dict(os.environ, env), mock.patch.object(self.update_mod, "_probe", side_effect=probe_then_plant):
            report = self.update_mod.run(ws, REPO_ROOT, env=dict(os.environ, **env), probe_timeout=1)
        stages = {s["stage"]: s for s in report.stages}
        self.assertEqual(stages["install"]["status"], "ok", stages)
        self.assertEqual(stages["registration"]["status"], "ok", stages)
        probed = [g for g in (p.name for p in (inst / "versions" / SHIPPED).iterdir() if p.is_dir()) if g != planted["gen"]]
        self.assertEqual(len(probed), 1, probed)
        probed = probed[0]
        json_paths, toml_paths = self.launch_paths(ws)
        self.assertEqual(set(json_paths), {"moves", "presence"})
        for path in list(json_paths.values()) + toml_paths:
            self.assertIn(f"/{probed}/", path, f"a launch names an unprobed generation: {path}")
            self.assertNotIn(planted["gen"], path)
        self.assertEqual(len(toml_paths), 3, toml_paths)   # two advisors + the reverse server

    def test_update_marks_the_probed_generation_and_a_second_workspace_converges_to_it(self):
        inst = fixture_install(self.d / "inst", versions=(), lock_version=SHIPPED)
        h1 = add_generation(inst, SHIPPED, payload="H1", verified=True)
        ws2, ws3 = self.workspace("ws2"), self.workspace("ws3")
        with mock.patch.dict(os.environ, {"VIBE_SUITE_OCTOPUS_INSTALL_DIR": str(inst)}):
            for ws in (ws2, ws3):
                self.declare(ws, "steady")
                self.advisors.add(ws, "steady")
        for ws in (ws2, ws3):
            self.assertIn(f"/{h1}/", self.launch_paths(ws)[0]["steady"])
        # the shipped lockfile changes → H1 no longer valid; H2 is built but UNVERIFIED
        (inst / "package-lock.json").write_text(lockfile_text(SHIPPED, integrity="sha512-" + "D" * 86 + "=="), encoding="utf-8")
        h2 = add_generation(inst, SHIPPED, payload="H2", verified=False)
        env = self.seams(inst)
        with mock.patch.dict(os.environ, env):
            self.assertIsNone(self.oi.current_verified_generation(SHIPPED, env=dict(os.environ)))
            self.assertTrue(self.advisors.reconcile(ws2)["steady"].startswith("backend-unavailable"))
            self.assertIn(f"/{h1}/", self.launch_paths(ws2)[0]["steady"], "held on H1 while H2 is unverified")
            # a real update in another workspace verifies H2 — PRODUCTION writes the mark
            ws1 = self.workspace("ws1")
            report = self.update_mod.run(ws1, REPO_ROOT, env=dict(os.environ, **env), probe_timeout=1)
            stages = {s["stage"]: s for s in report.stages}
            self.assertEqual(stages["probe"]["status"], "ok", stages)
            self.assertTrue((inst / "versions" / SHIPPED / f"{h2}.verified").is_file(), "production created the mark")
            self.assertEqual(self.oi.current_verified_generation(SHIPPED, env=dict(os.environ)), h2)
            # the second workspace converges through STANDALONE reconcile, no hand-written mark
            rep = self.advisors.reconcile(ws2)
            self.assertEqual(rep["steady"], "stale-registered->registered")
            self.assertIn(f"/{h2}/", self.launch_paths(ws2)[0]["steady"])
            # and a third through repair
            r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "repair.py"), "--workspace", str(ws3), "--json"],
                               capture_output=True, text=True, env=dict(os.environ, **env))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(f"/{h2}/", self.launch_paths(ws3)[0]["steady"])

    def test_failed_and_timed_out_probes_leave_the_generation_unmarked(self):
        for server in ("wrong-version", "hang"):
            with self.subTest(server=server):
                inst = fixture_install(self.d / f"inst-{server}", versions=(), lock_version=SHIPPED)
                h2 = add_generation(inst, SHIPPED, verified=False)
                ws = self.workspace(f"ws-{server}")
                env = self.seams(inst, server=server)
                with mock.patch.dict(os.environ, env):
                    report = self.update_mod.run(ws, REPO_ROOT, env=dict(os.environ, **env), probe_timeout=1)
                stages = {s["stage"]: s for s in report.stages}
                self.assertEqual(stages["probe"]["status"], "fail", stages)
                self.assertFalse((inst / "versions" / SHIPPED / f"{h2}.verified").exists())
                self.assertNotIn("registration", stages)


class InProcessUpdateContracts(_InProcessBase):
    """Step-8 R4: the install timeout is forwarded; a failed mark publication skips the writes."""

    def test_install_timeout_is_forwarded_from_run_and_from_the_cli(self):
        inst = fixture_install(self.d / "inst", versions=(SHIPPED,), lock_version=SHIPPED)
        ws = self.workspace("ws")
        env = self.seams(inst)
        seen = []
        real = self.update_mod.octopus_install.ensure_installed

        def spy(pin, env=None, timeout=600):
            seen.append(timeout)
            return real(pin, env=env, timeout=timeout)
        with mock.patch.dict(os.environ, env), mock.patch.object(self.update_mod.octopus_install, "ensure_installed", side_effect=spy):
            self.update_mod.run(ws, REPO_ROOT, env=dict(os.environ, **env), probe_timeout=1, install_timeout=7)
            with mock.patch("sys.stdout"):
                self.update_mod.main(["--workspace", str(ws), "--plugin-root", str(REPO_ROOT), "--probe-timeout", "1",
                                      "--install-timeout", "9", "--json"])
        self.assertEqual(seen, [7, 9])

    def test_a_failed_mark_publication_skips_advisors_and_registration(self):
        inst = fixture_install(self.d / "inst", versions=(), lock_version=SHIPPED)
        h = add_generation(inst, SHIPPED, verified=False)
        ws = self.workspace("ws")
        self.declare(ws, "steady")
        with mock.patch.dict(os.environ, {"VIBE_SUITE_OCTOPUS_INSTALL_DIR": str(module_install("update"))}):
            self.advisors.add(ws, "steady")
        before = ((ws / ".mcp.json").read_bytes(), bridge.text_block_remove((ws / ".codex" / "config.toml").read_text(), "mcp-mirror"))
        env = self.seams(inst)
        with mock.patch.dict(os.environ, env), mock.patch.object(self.update_mod.octopus_install, "mark_verified",
                                                                    side_effect=fsafe.BridgeError("disk says no")):
            report = self.update_mod.run(ws, REPO_ROOT, env=dict(os.environ, **env), probe_timeout=1)
        stages = {s["stage"]: s for s in report.stages}
        self.assertEqual(stages["probe"]["status"], "fail", stages)
        self.assertIn("could not record the verification", stages["probe"]["detail"])
        self.assertEqual(stages["advisors"]["status"], "warn")
        self.assertNotIn("registration", stages)
        self.assertEqual(((ws / ".mcp.json").read_bytes(), bridge.text_block_remove((ws / ".codex" / "config.toml").read_text(), "mcp-mirror")), before)
        self.assertFalse((inst / "versions" / SHIPPED / f"{h}.verified").exists())


class NetworkOptIn(unittest.TestCase):
    """Evidence, not a gate: the real npm's integrity check. Opt in with VIBE_SUITE_NETWORK_TESTS=1."""

    @unittest.skipUnless(os.environ.get("VIBE_SUITE_NETWORK_TESTS") == "1", "network test — opt in")
    def test_real_npm_ci_refuses_a_tampered_lockfile(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            src = REPO_ROOT / "scripts" / "lib" / "claude-octopus"
            (d / "package.json").write_bytes((src / "package.json").read_bytes())
            lock = json.loads((src / "package-lock.json").read_text())
            lock["packages"]["node_modules/claude-octopus"]["integrity"] = "sha512-" + "A" * 86 + "=="
            (d / "package-lock.json").write_text(json.dumps(lock, indent=2) + "\n")
            proc = subprocess.run(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=d,
                                  capture_output=True, text=True, timeout=600)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("EINTEGRITY", proc.stderr)

if __name__ == "__main__":
    unittest.main()


class TestAdvisorReconcileStage(TempDirMixin, unittest.TestCase):
    """E6.1: update reconciles advisors in every pin state; removal needs no backend."""

    def test_orphan_removed_and_stage_reported(self):
        ws = Path(self.mkdtemp(prefix="vibe-update-advisors-"))
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
        ws = Path(self.mkdtemp(prefix="vibe-update-advisors-"))
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
        # vibe-185: only a REGISTERED advisor takes part in the collision preflight — register it
        # first (the stamp), then let an unowned server squat on its name.
        (ws / ".mcp.json").write_text('{"mcpServers": {}}\n')
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
        import advisors as advisors_mod
        advisors_mod.add(ws, "floaty")
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

    def test_a_declared_but_never_registered_advisor_is_held_by_update(self):
        # vibe-185: update converges only what the operator registered.
        ws = Path(self.mkdtemp(prefix="vibe-update-advisors-"))
        self.addCleanup(__import__("shutil").rmtree, ws, ignore_errors=True)
        (ws / ".vibe-suite" / "agents").mkdir(parents=True)
        (ws / ".vibe-suite" / "agents" / "quiet.md").write_text(
            "---\ndescription: |\n  Judges quiet things.\nmodel: sonnet\n---\n\nValue truth.\n", encoding="utf-8")
        (ws / ".mcp.json").write_text('{"mcpServers": {}}\n')
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import update as update_mod
        report = update_mod.run(ws, REPO_ROOT, probe_timeout=1)
        stages = {s["stage"]: s for s in report.stages}
        self.assertEqual(stages["advisors"]["status"], "ok")
        self.assertIn("quiet: declared-unregistered (not registered; register with advisor add quiet)", stages["advisors"]["detail"])
        self.assertNotIn("quiet", json.loads((ws / ".mcp.json").read_text()).get("mcpServers", {}))
