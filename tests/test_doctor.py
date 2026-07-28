#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fixtures for `/vibe-suite:doctor` (E2.2 / vibe-19).

Two halves to the acceptance criterion, and the second is the one that is easy to lose: *"each
seeded breakage class detected on fixtures; **clean project reports clean**."* A checker that reports
something on a healthy project is a checker nobody reads.

**Capabilities are not findings.** A check that cannot run — F4.4, mirror staleness, row 9 — is a
fact about the installation, not a defect in the project. Reporting them as findings would make
`[GOOD]` unreachable on a clean project, and `vibe-core` makes `[GOOD]` exclusive, so the two go in
separate tables.

**Read-only is asserted, not promised**, and only over the workspace: preflight may touch
`CODEX_HOME`, which these fixtures redirect rather than pretend to control.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCTOR = REPO_ROOT / "scripts" / "doctor.py"
INIT = REPO_ROOT / "scripts" / "init.sh"


def tree(root):
    out = {}
    for path in sorted(Path(root).rglob("*")):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            out[rel] = ("l", os.readlink(path))
        elif path.is_dir():
            out[rel] = ("d", None)
        else:
            out[rel] = ("f", path.read_bytes())
    return out


class DoctorCase(unittest.TestCase):
    def setUp(self):
        self.ws = Path(tempfile.mkdtemp(prefix="vibe-doctor-"))
        self.addCleanup(shutil.rmtree, self.ws, ignore_errors=True)
        self.home = Path(tempfile.mkdtemp(prefix="vibe-codexhome-"))
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def doctor(self, *args):
        env = dict(os.environ, CODEX_HOME=str(self.home))
        return subprocess.run(["python3", str(DOCTOR), "--workspace", str(self.ws), "--json", *args],
                              capture_output=True, text=True, env=env)

    def report(self, *args):
        result = self.doctor(*args)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def install(self):
        r = subprocess.run(["bash", str(INIT), "--workspace", str(self.ws), "--effort", "medium",
                            "--audit-depth", "mini", "--strictness", "standard"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def severities(self, report):
        return [f["severity"] for f in report["findings"]]

    def checks(self, report):
        return {f["check"] for f in report["findings"]}


class TestCleanProject(DoctorCase):
    def test_a_clean_project_reports_exactly_one_good(self):
        self.install()
        report = self.report()
        self.assertEqual(self.severities(report), ["[GOOD]"],
                         f"a healthy project produced findings: {report['findings']}")

    def test_unavailable_capabilities_do_not_prevent_good(self):
        """F4.4, mirror staleness and row 9 cannot run at this commit. They belong in the capability
        table; in the findings table they would make `[GOOD]` unreachable forever."""
        self.install()
        report = self.report()
        statuses = {c["check"]: c["status"] for c in report["capabilities"]}
        self.assertEqual(statuses.get("manifest-vs-disk"), "unavailable")
        self.assertEqual(statuses.get("mirror-staleness"), "unavailable")
        self.assertEqual(self.severities(report), ["[GOOD]"])

    def test_every_capability_names_what_blocks_it(self):
        self.install()
        for capability in self.report()["capabilities"]:
            if capability["status"] == "unavailable":
                self.assertTrue(capability.get("blocked_on"),
                                f"{capability['check']} is unavailable with no blocking item named")


class TestInitialisationStates(DoctorCase):
    def test_uninitialised_suppresses_the_cascade(self):
        report = self.report()
        self.assertEqual(report["state"], "uninitialised")
        self.assertNotIn("sentinels", self.checks(report),
                         "component checks fired on a project that was never initialised")

    def test_uninitialised_still_reports_legacy_stores(self):
        """A project holding a legacy config needs that said precisely because it has not been
        migrated. Suppressing the cascade must not suppress this."""
        (self.ws / ".cc-suite.md").write_text("- **Default effort**: high\n", encoding="utf-8")
        report = self.report()
        self.assertEqual(report["state"], "uninitialised")
        self.assertIn("legacy-config", self.checks(report))

    def test_uninitialised_still_reports_capabilities(self):
        self.assertTrue(self.report()["capabilities"])

    def test_provenance_absent_is_partial_not_installed(self):
        self.install()
        (self.ws / ".vibe-suite-state" / "install-provenance.json").unlink()
        report = self.report()
        self.assertEqual(report["state"], "partial")
        self.assertIn("provenance", self.checks(report))

    def test_provenance_malformed_is_distinguished_from_absent(self):
        self.install()
        (self.ws / ".vibe-suite-state" / "install-provenance.json").write_text(
            '{"schema": 1, "targets": []}\n', encoding="utf-8")
        report = self.report()
        self.assertEqual(report["state"], "partial")
        finding = [f for f in report["findings"] if f["check"] == "provenance"][0]
        self.assertIn("malformed", finding["finding"].lower())


class TestBreakageClasses(DoctorCase):
    def test_a_removed_mcp_sentinel_is_detected_and_flagged_fixable(self):
        self.install()
        doc = json.loads((self.ws / ".mcp.json").read_text())
        doc["mcpServers"].pop("vibe-mcp")
        (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        finding = [f for f in self.report()["findings"] if f["check"] == "sentinels"][0]
        self.assertTrue(finding["auto_fixable"])

    def test_a_name_in_one_store_but_not_the_other_is_detected(self):
        """`inventory_enumerate` unions the two stores, so a half-registration is invisible unless
        both are asked."""
        self.install()
        text = (self.ws / ".codex" / "config.toml").read_text(encoding="utf-8")
        (self.ws / ".codex" / "config.toml").write_text(
            text.replace("[mcp_servers.vibe-mcp]", "[mcp_servers.other]"), encoding="utf-8")
        self.assertIn("sentinels", self.checks(self.report()))

    def test_a_deleted_memory_block_is_detected(self):
        self.install()
        (self.ws / "CLAUDE.md").write_text("nothing owned here\n", encoding="utf-8")
        self.assertIn("memory", self.checks(self.report()))

    def test_a_target_replaced_by_a_symlink_is_detected(self):
        self.install()
        target = self.ws / ".gitignore"
        target.unlink()
        target.symlink_to(self.ws / "elsewhere")
        self.assertIn("symlinks", self.checks(self.report()))

    def test_a_hook_entry_whose_command_does_not_resolve_is_detected(self):
        self.install()
        doc = json.loads((self.ws / ".codex" / "hooks.json").read_text())
        for entry in doc["hooks"]["Stop"]:
            if entry.get("_vibe-suite_owned"):
                entry["command"] = "/nonexistent/vibe-suite-binary"
        (self.ws / ".codex" / "hooks.json").write_text(json.dumps(doc, indent=2) + "\n",
                                                       encoding="utf-8")
        self.assertIn("hooks", self.checks(self.report()))

    def test_a_pin_mismatch_is_detected(self):
        self.install()
        record = json.loads((self.ws / ".vibe-suite-state" / "install-provenance.json").read_text())
        record["plugin_version"] = "0.0.0-stale"
        (self.ws / ".vibe-suite-state" / "install-provenance.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8")
        self.assertIn("pins", self.checks(self.report()))

    def test_an_invalid_config_is_a_finding_not_a_crash(self):
        self.install()
        (self.ws / ".vibe-suite.md").write_text("---\neffort: sonnet\n---\n", encoding="utf-8")
        report = self.report()
        self.assertIn("config", self.checks(report))

    def test_each_legacy_row_is_detected(self):
        self.install()
        (self.ws / ".cc-suite.md").write_text("- **Default effort**: high\n", encoding="utf-8")
        (self.ws / ".claude" / "nlpm.local.md").write_text("---\neffort: low\n---\n",
                                                           encoding="utf-8")
        (self.ws / ".claude" / "nlpm-reports").mkdir(exist_ok=True)
        (self.ws / ".codex-toolkit-state").mkdir()
        (self.ws / ".codex-toolkit-state" / "state.json").write_text(
            '{"config":{"gate":{"stop_review_gate":true}}}\n', encoding="utf-8")
        doc = json.loads((self.ws / ".mcp.json").read_text())
        doc["mcpServers"]["cc-suite-mcp"] = {"command": "x"}
        (self.ws / ".mcp.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        report = self.report()
        found = self.checks(report)
        for check in ("legacy-config", "legacy-state", "legacy-sentinels"):
            self.assertIn(check, found)
        # Row 4 comes from survey.sh, consumed rather than reimplemented.
        self.assertTrue(any(c.startswith("legacy-row-") for c in found),
                        f"survey's rows were not forwarded: {sorted(found)}")


class TestKnowledgeFreshness(DoctorCase):
    def test_absent_producer_is_a_capability_not_a_staleness_finding(self):
        self.install()
        report = self.report()
        self.assertNotIn("knowledge-freshness", self.checks(report))
        statuses = {c["check"]: c["status"] for c in report["capabilities"]}
        self.assertEqual(statuses.get("knowledge-freshness"), "unavailable")


class TestReadOnly(DoctorCase):
    def test_doctor_changes_nothing_in_the_workspace(self):
        self.install()
        before = tree(self.ws)
        self.doctor()
        self.assertEqual(tree(self.ws), before, "doctor mutated the workspace")

    def test_doctor_changes_nothing_on_an_uninitialised_project(self):
        (self.ws / "README.md").write_text("mine\n", encoding="utf-8")
        before = tree(self.ws)
        self.doctor()
        self.assertEqual(tree(self.ws), before)


class TestCommandWiring(DoctorCase):
    def test_the_command_file_invokes_the_helper_it_documents(self):
        text = (REPO_ROOT / "commands" / "doctor.md").read_text(encoding="utf-8")
        self.assertIn("scripts/doctor.py", text)
        self.assertIn("/vibe-suite:repair", text, "auto-fixable items must point at repair")
        self.assertNotIn("/vibe:", text.replace("/vibe-suite:", ""))


if __name__ == "__main__":
    unittest.main()
