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

    def test_a_removed_sentinel_is_repaired(self):
        def breaker():
            doc = json.loads((self.ws / ".mcp.json").read_text())
            doc["mcpServers"].pop("vibe-mcp")
            (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        self._break_and_repair(breaker, "sentinels")

    def test_a_deleted_memory_block_is_repaired(self):
        self._break_and_repair(
            lambda: (self.ws / "CLAUDE.md").write_text("mine only\n", encoding="utf-8"), "memory")

    def test_a_missing_memory_file_is_repaired(self):
        self._break_and_repair(lambda: (self.ws / "GEMINI.md").unlink(), "memory")

    def test_a_deleted_gitignore_block_is_repaired(self):
        self._break_and_repair(
            lambda: (self.ws / ".gitignore").write_text("mine\n", encoding="utf-8"), "gitignore")

    def test_a_removed_hook_entry_is_repaired(self):
        def breaker():
            doc = json.loads((self.ws / ".codex" / "hooks.json").read_text())
            doc["hooks"]["Stop"] = []
            (self.ws / ".codex" / "hooks.json").write_text(json.dumps(doc, indent=2) + "\n",
                                                           encoding="utf-8")
        self._break_and_repair(breaker, "hooks")

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
        doc = json.loads((self.ws / ".mcp.json").read_text())
        doc["mcpServers"].pop("vibe-mcp")
        (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

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
        report = self.diagnose()
        for check in ("legacy-config", "legacy-state"):
            entry = [f for f in report["findings"] if f["check"] == check]
            self.assertTrue(entry, f"{check} was not detected")
            self.assertFalse(entry[0]["auto_fixable"],
                             f"{check} claims repair can clear it; §7A preserves its source")

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
        # Break the codex block first, so the step has something to write; then remove write
        # permission. A step with nothing to do cannot fail, and the fixture would prove nothing.
        (self.ws / ".codex" / "config.toml").write_text("# mine\n", encoding="utf-8")
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
                         {"config", "memory", "codex", "mcp", "gitignore", "history"})

    def test_a_failing_step_makes_the_exit_non_zero(self):
        self.install()
        (self.ws / ".codex" / "config.toml").write_text("# mine\n", encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
