#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fixtures for `/vibe-suite:repair` (E2.3 / vibe-20).

**`auto_fixable` is a contract.** Acceptance is *"repairs every E2.2 auto-fixable fixture"*, so the
flag has to mean "a no-prompt re-run clears this". The coupling is asserted in the direction the
criterion names — for every finding doctor flags, repair clears it — because a flag promising what no
command delivers is worse than no flag at all.

**Idempotent is not resumable.** `init_bridge.install()` is fail-fast: an invalid config raises
before memory and registrations are reached. F1.3 requires collect-and-continue, so the per-step
isolation is what these tests actually exercise.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPAIR = REPO_ROOT / "scripts" / "repair.py"
DOCTOR = REPO_ROOT / "scripts" / "doctor.py"
INIT = REPO_ROOT / "scripts" / "init.sh"
import sys  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import bridge  # noqa: E402


def snapshot(root):
    out = {}
    for p in sorted(Path(root).rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            out[rel] = ("l", None, os.readlink(p))
        elif p.is_dir():
            out[rel] = ("d", None, None)
        else:
            st = p.lstat()
            out[rel] = ("f", oct(st.st_mode & 0o777), p.read_bytes())
    return out


def mtimes(root):
    return {str(p.relative_to(root)): p.lstat().st_mtime_ns for p in sorted(Path(root).rglob("*"))}


def plant_dangling_registrations(ws):
    """The three registrations an earlier revision of init wrote — a bare `vibe-suite` command in
    each host-read file — beside a user's own entries, which must survive their removal."""
    ws = Path(ws)
    (ws / ".codex").mkdir(exist_ok=True)
    toml = ws / ".codex" / "config.toml"
    existing = toml.read_text(encoding="utf-8") if toml.is_file() else ""
    toml.write_text(bridge.toml_server_upsert(existing, "vibe-mcp",
                                              '[mcp_servers.vibe-mcp]\ncommand = "vibe-suite"'),
                    encoding="utf-8")
    mcp = ws / ".mcp.json"
    doc = json.loads(mcp.read_text(encoding="utf-8")) if mcp.is_file() else {}
    doc.setdefault("mcpServers", {})["mine"] = {"command": "x"}
    doc["mcpServers"]["vibe-mcp"] = {"command": "vibe-suite", "args": []}
    mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hooks = ws / ".codex" / "hooks.json"
    hdoc = json.loads(hooks.read_text(encoding="utf-8")) if hooks.is_file() else {}
    hdoc.setdefault("hooks", {}).setdefault("Stop", []).append({"type": "command", "command": "my-hook"})
    hdoc = bridge.json_hook_entry_upsert(hdoc, "Stop", {"type": "command", "command": "vibe-suite stop-gate"})
    hooks.write_text(json.dumps(hdoc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bare_registrations(ws):
    """Which of the three files still reference `vibe-suite` as a command."""
    ws = Path(ws)
    out = []
    toml = ws / ".codex" / "config.toml"
    if toml.is_file() and 'command = "vibe-suite"' in toml.read_text(encoding="utf-8"):
        out.append(".codex/config.toml")   # the bare SHAPE, not the server name: a non-bare vibe-mcp is legitimate
    mcp = ws / ".mcp.json"
    if mcp.is_file():
        servers = json.loads(mcp.read_text(encoding="utf-8")).get("mcpServers") or {}
        if any(isinstance(s, dict) and s.get("command") == "vibe-suite" for s in servers.values()):
            out.append(".mcp.json")
    hooks = ws / ".codex" / "hooks.json"
    if hooks.is_file():
        for event in (json.loads(hooks.read_text(encoding="utf-8")).get("hooks") or {}).values():
            if any(isinstance(e, dict) and str(e.get("command") or "").startswith("vibe-suite") for e in event):
                out.append(".codex/hooks.json")
                break
    return out

NON_BARE = "/opt/vibe-suite/bin/vibe-suite"


def plant_non_bare_registrations(ws):
    """A legitimate `vibe-mcp` — an absolute command (the shape a shipped binary registers under,
    or what the row-6 migration keeps from a legacy install) — in BOTH stores, plus an owned Stop
    hook with an absolute command, beside the user's own entries. None of these is dangling."""
    ws = Path(ws)
    (ws / ".codex").mkdir(exist_ok=True)
    toml = ws / ".codex" / "config.toml"
    existing = toml.read_text(encoding="utf-8") if toml.is_file() else ""
    toml.write_text(bridge.toml_server_upsert(existing, "vibe-mcp",
                                              '[mcp_servers.vibe-mcp]\ncommand = "%s"' % NON_BARE),
                    encoding="utf-8")
    mcp = ws / ".mcp.json"
    doc = json.loads(mcp.read_text(encoding="utf-8")) if mcp.is_file() else {}
    doc.setdefault("mcpServers", {})["mine"] = {"command": "x"}
    doc["mcpServers"]["vibe-mcp"] = {"command": NON_BARE, "args": []}
    mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hooks = ws / ".codex" / "hooks.json"
    hdoc = json.loads(hooks.read_text(encoding="utf-8")) if hooks.is_file() else {}
    hdoc.setdefault("hooks", {}).setdefault("Stop", []).append({"type": "command", "command": "my-hook"})
    hdoc = bridge.json_hook_entry_upsert(hdoc, "Stop", {"type": "command", "command": NON_BARE + " stop-gate"})
    hooks.write_text(json.dumps(hdoc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def host_files_snapshot(ws):
    ws = Path(ws)
    out = {}
    for rel in (".codex/config.toml", ".mcp.json", ".codex/hooks.json"):
        p = ws / rel
        out[rel] = (p.read_bytes(), p.lstat().st_mtime_ns) if p.is_file() else None
    return out

def plant_bare_and_non_bare_owned_hooks(ws):
    """A user's hook, an OWNED non-bare hook (an absolute command) and an OWNED bare
    `vibe-suite stop-gate` side by side: only the bare one is dangling."""
    ws = Path(ws)
    (ws / ".codex").mkdir(exist_ok=True)
    owned = {"_%s_owned" % bridge.MARKER: bridge.SCHEMA}
    doc = {"hooks": {"Stop": [
        {"type": "command", "command": "my-hook"},
        dict({"type": "command", "command": "/opt/vibe-suite/bin/vibe-suite stop-gate"}, **owned),
        dict({"type": "command", "command": "vibe-suite stop-gate"}, **owned),
    ]}}
    (ws / ".codex" / "hooks.json").write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stop_commands(ws):
    return [e.get("command") for e in json.loads((Path(ws) / ".codex" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"]]


class RepairCase(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-repair-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)

    def install(self):
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def repair(self):
        """stdin is closed: F1.3 forbids prompting, and a prompt would hang rather than fail."""
        return subprocess.run(["python3", str(REPAIR), "--workspace", str(self.ws), "--json"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def diagnose(self):
        r = subprocess.run(["python3", str(DOCTOR), "--workspace", str(self.ws), "--json"],
                           capture_output=True, text=True)
        return json.loads(r.stdout)

    def findings(self, report=None):
        return {f["check"] for f in (report or self.diagnose())["findings"]}

    def fixable(self, report=None):
        return {f["check"] for f in (report or self.diagnose())["findings"] if f["auto_fixable"]}


class TestRepairsWhatDoctorFlags(RepairCase):
    def _break_and_repair(self, breaker, check):
        self.install()
        breaker()
        self.assertIn(check, self.findings(), f"doctor did not detect {check}")
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(check, self.findings(), f"repair did not clear {check}")

    def test_a_dangling_bare_registration_is_detected_removed_and_reported(self):
        # grill S4 (vibe-191): the old registration named a binary that does not ship; doctor flags
        # it (auto-fixable), repair removes it from all three files, keeps the user's entries, and
        # SAYS so in the step outcomes.
        self._break_and_repair(lambda: plant_dangling_registrations(self.ws), "sentinels")
        self.assertEqual(bare_registrations(self.ws), [], "repair must remove the dangling registrations")
        servers = json.loads((self.ws / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertIn("mine", servers, "a user's server survives the repair")
        stop = json.loads((self.ws / ".codex" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"]
        self.assertEqual([e.get("command") for e in stop], ["my-hook"])
        # reported: plant again, repair again, read the step outcomes
        plant_dangling_registrations(self.ws)
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        outcomes = {s["step"]: s["outcome"] for s in json.loads(result.stdout)["steps"]}
        self.assertIn("removed dangling", outcomes["codex"], outcomes)
        self.assertIn(".codex/config.toml", outcomes["codex"])
        self.assertIn("removed dangling", outcomes["mcp"], outcomes)
        self.assertIn(".mcp.json", outcomes["mcp"])
        self.assertIn(".codex/hooks.json", outcomes["mcp"])
        self.assertEqual(bare_registrations(self.ws), [])

    def test_a_non_bare_vibe_mcp_and_a_non_bare_owned_hook_survive_repair_verbatim(self):
        # repair's cleanup removes the exact bare shapes only: a legitimate registration in both
        # stores and a non-bare owned hook survive byte- and mtime-identical, doctor does not flag
        # them as dangling, and the report carries no removal note
        self.install()
        plant_non_bare_registrations(self.ws)
        before = host_files_snapshot(self.ws)
        self.assertFalse(any("dangling" in f["finding"] for f in self.diagnose()["findings"]),
                         "a non-bare registration is not dangling")
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(host_files_snapshot(self.ws), before, "repair must not touch a non-bare registration")
        outcomes = {s["step"]: s["outcome"] for s in json.loads(result.stdout)["steps"]}
        self.assertEqual(outcomes["codex"], "ok"); self.assertEqual(outcomes["mcp"], "ok")

    def test_a_bare_owned_hook_beside_a_non_bare_owned_hook_goes_alone_on_repair(self):
        self.install()
        plant_bare_and_non_bare_owned_hooks(self.ws)
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stop_commands(self.ws), ["my-hook", "/opt/vibe-suite/bin/vibe-suite stop-gate"])
        outcomes = {s["step"]: s["outcome"] for s in json.loads(result.stdout)["steps"]}
        self.assertIn("removed dangling", outcomes["mcp"]); self.assertIn(".codex/hooks.json", outcomes["mcp"])

    def test_a_non_bare_half_registration_is_reported_not_auto_fixed_and_left_alone(self):
        # doctor's auto_fixable flag promises a no-prompt repair clears it; repair registers nothing
        # under vibe-mcp, so a non-bare vibe-mcp present in only one store is reported, NOT flagged
        # fixable, and left byte-identical by repair
        self.install()
        mcp = self.ws / ".mcp.json"
        mcp.write_text(json.dumps({"mcpServers": {"mine": {"command": "x"},
                                                  "vibe-mcp": {"command": "/opt/vibe-suite/bin/vibe-suite", "args": []}}},
                                  indent=2, sort_keys=True) + "\n", encoding="utf-8")
        before = mcp.read_bytes()
        report = self.diagnose()
        half = [f for f in report["findings"] if "registered only in .mcp.json" in f["finding"]]
        self.assertEqual(len(half), 1, report["findings"])
        self.assertFalse(half[0]["auto_fixable"], "repair cannot clear it, so it must not promise to")
        self.assertNotIn("sentinels", self.fixable(report))
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(mcp.read_bytes(), before, "repair left the legitimate half-registration alone")
        self.assertTrue(any("registered only in .mcp.json" in f["finding"] for f in self.diagnose()["findings"]))

    def test_a_missing_registration_is_not_a_finding_and_repair_registers_none(self):
        # the absence of a `vibe-mcp` registration is the healthy state until the binary ships
        self.install()
        self.assertNotIn("sentinels", self.findings())
        self.assertNotIn("hooks", self.findings())
        self.repair()
        self.assertEqual(bare_registrations(self.ws), [], "repair must not re-register a bare command")

    def test_a_deleted_memory_block_is_repaired(self):
        self._break_and_repair(
            lambda: (self.ws / "CLAUDE.md").write_text("mine only\n", encoding="utf-8"), "memory")

    def test_a_missing_memory_file_is_repaired(self):
        self._break_and_repair(lambda: (self.ws / "GEMINI.md").unlink(), "memory")

    def test_a_deleted_gitignore_block_is_repaired(self):
        self._break_and_repair(
            lambda: (self.ws / ".gitignore").write_text("mine\n", encoding="utf-8"), "gitignore")

    def test_user_content_survives_a_repair(self):
        self.install()
        (self.ws / "CLAUDE.md").write_text("# Mine\n\nkeep this\n", encoding="utf-8")
        self.repair()
        self.assertIn("keep this", (self.ws / "CLAUDE.md").read_text(encoding="utf-8"))


class TestTheContract(RepairCase):
    def test_every_auto_fixable_finding_is_actually_repaired(self):
        """The acceptance criterion, asserted in its own direction. Five of #19's original eight
        flags promised a fix no no-prompt command could deliver."""
        self.install()
        for path in ("CLAUDE.md", ".gitignore"):
            (self.ws / path).write_text("mine\n", encoding="utf-8")
        plant_dangling_registrations(self.ws)   # grill S4: the dangling registration is the sentinel breakage

        flagged = self.fixable()
        self.assertTrue(flagged, "no auto-fixable findings to test the contract against")
        self.repair()
        remaining = self.fixable()
        self.assertEqual(remaining, set(),
                         f"repair left auto-fixable findings unrepaired: {remaining}")

    def test_flags_that_repair_cannot_clear_are_not_marked_fixable(self):
        """§7A preserves legacy sources, provenance is write-once, and row 6 needs confirmation —
        so these survive their own 'fix' and must not claim otherwise."""
        self.install()
        (self.ws / ".cc-suite.md").write_text("- **Default effort**: high\n", encoding="utf-8")
        (self.ws / ".cc-suite-state").mkdir()
        (self.ws / ".cc-suite-state" / "state.json").write_text('{"config":{}}\n', encoding="utf-8")
        doc = json.loads((self.ws / ".mcp.json").read_text())
        doc["mcpServers"]["cc-suite-mcp"] = {"command": "x"}
        (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        record = json.loads((self.ws / ".vibe-suite-state" / "install-provenance.json").read_text())
        record["plugin_version"] = "0.0.0-stale"
        (self.ws / ".vibe-suite-state" / "install-provenance.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
        report = self.diagnose()
        for check in ("legacy-config", "legacy-state", "legacy-sentinels", "pins"):
            entry = [f for f in report["findings"] if f["check"] == check]
            self.assertTrue(entry, f"{check} was not detected")
            self.assertFalse(entry[0]["auto_fixable"],
                             f"{check} claims repair can clear it; §7A preserves its source")

    def test_malformed_mcp_json_does_not_suppress_the_report(self):
        """`installed()` parsed .mcp.json outside step isolation, so a malformed file aborted with a
        traceback and no per-step outcome survived."""
        self.install()
        (self.ws / ".mcp.json").write_text("{not json\n", encoding="utf-8")
        result = self.repair()
        self.assertNotIn("Traceback", result.stderr)
        self.assertTrue(json.loads(result.stdout)["steps"])

    def test_an_unreadable_config_never_guesses_a_threshold(self):
        """The fallback leaked forward: once set for `codex`, `history` ran with a guessed 70."""
        self.install()
        (self.ws / ".claude" / "vibe-history.json").unlink()
        (self.ws / ".vibe-suite.md").write_text("---\neffort: sonnet\n---\n", encoding="utf-8")
        report = json.loads(self.repair().stdout)
        outcomes = {s["step"]: s["outcome"] for s in report["steps"]}
        self.assertTrue(outcomes["history"].startswith("skipped"),
                        "history ran with a guessed threshold")

    def test_uninitialised_is_not_flagged_fixable(self):
        entry = [f for f in self.diagnose()["findings"] if f["check"] == "not-initialised"]
        self.assertTrue(entry)
        self.assertFalse(entry[0]["auto_fixable"], "the fix is init, which prompts")


class TestCollectAndContinue(RepairCase):
    def test_one_failing_step_does_not_stop_the_others(self):
        """`install()` is fail-fast; F1.3 requires the opposite."""
        self.install()
        (self.ws / ".gitignore").write_text("mine\n", encoding="utf-8")
        (self.ws / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
        # Give the codex step something to REMOVE — a dangling bare registration (grill S4: the
        # step no longer writes one, it removes one) — then remove write permission. A step with
        # nothing to do cannot fail, and the fixture would prove nothing.
        (self.ws / ".codex" / "config.toml").write_text(
            bridge.toml_server_upsert("# mine\n", "vibe-mcp", '[mcp_servers.vibe-mcp]\ncommand = "vibe-suite"'),
            encoding="utf-8")
        (self.ws / ".codex").chmod(0o500)
        self.addCleanup(lambda: (self.ws / ".codex").chmod(0o700))
        result = self.repair()
        report = json.loads(result.stdout)
        outcomes = {s["step"]: s["outcome"] for s in report["steps"]}
        self.assertTrue(any(o.startswith("failed") for o in outcomes.values()),
                        "no step failed, so this fixture proves nothing")
        self.assertEqual(outcomes.get("gitignore"), "ok",
                         "a later step was skipped because an earlier one failed")

    def test_every_step_appears_in_the_report(self):
        self.install()
        report = json.loads(self.repair().stdout)
        self.assertEqual({s["step"] for s in report["steps"]},
                         {"config", "memory", "codex", "mcp", "gitignore", "history",
                          "advisors"})

    def test_a_failing_step_makes_the_exit_non_zero(self):
        self.install()
        # a dangling registration the codex step must remove, under a read-only directory
        (self.ws / ".codex" / "config.toml").write_text(
            bridge.toml_server_upsert("# mine\n", "vibe-mcp", '[mcp_servers.vibe-mcp]\ncommand = "vibe-suite"'),
            encoding="utf-8")
        (self.ws / ".codex").chmod(0o500)
        self.addCleanup(lambda: (self.ws / ".codex").chmod(0o700))
        self.assertNotEqual(self.repair().returncode, 0)


class TestIdempotence(RepairCase):
    def test_repair_after_repair_is_byte_identical(self):
        self.install()
        (self.ws / "CLAUDE.md").write_text("mine\n", encoding="utf-8")
        self.repair()
        before, before_m = snapshot(self.ws), mtimes(self.ws)
        self.assertEqual(self.repair().returncode, 0)
        self.assertEqual(snapshot(self.ws), before, "a second repair changed content or modes")
        self.assertEqual(mtimes(self.ws), before_m, "a second repair rewrote identical bytes")

    def test_repair_on_a_healthy_project_changes_nothing(self):
        self.install()
        before, before_m = snapshot(self.ws), mtimes(self.ws)
        self.repair()
        self.assertEqual(snapshot(self.ws), before)
        self.assertEqual(mtimes(self.ws), before_m)


class TestRefusals(RepairCase):
    def test_an_uninitialised_project_is_declined_not_half_installed(self):
        result = self.repair()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ws / "AGENTS.md").exists(),
                         "repair installed into a project that was never set up")

    def test_an_invalid_config_is_reported_and_other_steps_still_run(self):
        self.install()
        (self.ws / ".vibe-suite.md").write_text("---\neffort: sonnet\n---\n", encoding="utf-8")
        (self.ws / ".gitignore").write_text("mine\n", encoding="utf-8")
        report = json.loads(self.repair().stdout)
        outcomes = {s["step"]: s["outcome"] for s in report["steps"]}
        self.assertTrue(outcomes["config"].startswith("failed"))
        self.assertEqual(outcomes["gitignore"], "ok")


class TestCommandWiring(RepairCase):
    def test_the_command_documents_what_it_runs(self):
        text = (REPO_ROOT / "commands" / "repair.md").read_text(encoding="utf-8")
        self.assertIn("scripts/repair.py", text)
        self.assertIn("no prompts", text.lower())
        self.assertNotIn("/vibe:", text.replace("/vibe-suite:", ""))

    def test_the_command_names_the_auto_fixable_checks_as_they_are(self):
        # grill S4: `hooks` is no longer auto-fixable (no owned Stop hook is written until the
        # binary ships) and `sentinels` means a dangling bare registration that repair removes
        text = (REPO_ROOT / "commands" / "repair.md").read_text(encoding="utf-8")
        self.assertIn("Three checks qualify", text)
        self.assertNotIn("Four checks qualify", text)
        qualifying = text.split("Three checks qualify", 1)[1].split("\n\n", 1)[0]
        self.assertIn("`sentinels`", qualifying); self.assertIn("`memory`", qualifying); self.assertIn("`gitignore`", qualifying)
        self.assertNotIn("`hooks`", qualifying, "hooks is not auto-fixable any more")
        self.assertIn("dangling", qualifying)
        self.assertIn("| `hooks` |", text, "the not-repairable table names hooks")


if __name__ == "__main__":
    unittest.main()


class TestAdvisorReconcile(RepairCase):
    """E6.1: repair converges advisor registrations through the same engine add/remove use."""

    ORPHAN = {"command": "npx", "args": ["-y", "claude-octopus@9.9.9"], "env": {},
              "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}

    def test_an_orphaned_advisor_registration_is_removed(self):
        self.install()
        mcp = self.ws / ".mcp.json"
        doc = json.loads(mcp.read_text())
        doc.setdefault("mcpServers", {})["orphan_advisor"] = dict(self.ORPHAN)
        mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        result = self.repair()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        outcome = {s["step"]: s["outcome"] for s in report["steps"]}.get("advisors", "")
        self.assertTrue(outcome.startswith("ok"), outcome)
        self.assertIn("registered-undeclared->removed", outcome)
        after = json.loads(mcp.read_text())
        self.assertNotIn("orphan_advisor", after.get("mcpServers", {}))

    def _declare(self):
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(
            "---\ndescription: |\n  Judges probe things.\nmodel: sonnet\n---\n\nValue truth.\n",
            encoding="utf-8")

    def test_a_declared_but_never_registered_advisor_is_held_by_repair_not_registered(self):
        # vibe-185: registration is the operator's act (`advisor add <name>`); repair converges
        # only what was registered. Pre-vibe-185 this test asserted zero-flag registration here.
        self.install()
        self._declare()
        report = json.loads(self.repair().stdout)
        outcome = {s["step"]: s["outcome"] for s in report["steps"]}.get("advisors", "")
        self.assertTrue(outcome.startswith("ok"), outcome)
        self.assertIn("declared-unregistered (not registered; register with advisor add probe_advisor)", outcome)
        doc = json.loads((self.ws / ".mcp.json").read_text())
        self.assertNotIn("probe_advisor", doc.get("mcpServers", {}))

    def test_a_registered_advisor_whose_registration_drifted_is_converged_by_repair_at_the_shipped_default(self):
        self.install()
        self._declare()
        r = subprocess.run(["python3", str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(self.ws),
                            "add", "probe_advisor"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        toml = self.ws / ".codex" / "config.toml"
        text = toml.read_text()
        start, end = text.index("# >>> vibe-suite:server:probe_advisor"), text.index("# <<< vibe-suite:server:probe_advisor <<<")
        toml.write_text(text[:start] + text[end + len("# <<< vibe-suite:server:probe_advisor <<<\n"):])
        report = json.loads(self.repair().stdout)
        outcome = {s["step"]: s["outcome"] for s in report["steps"]}.get("advisors", "")
        self.assertTrue(outcome.startswith("ok"), outcome)
        self.assertIn("half-registered->registered", outcome)
        doc = json.loads((self.ws / ".mcp.json").read_text())
        args = doc["mcpServers"]["probe_advisor"]["args"]
        self.assertRegex(args[-1], r"^claude-octopus@\d+\.\d+\.\d+")
        self.assertIn("probe_advisor", toml.read_text())
