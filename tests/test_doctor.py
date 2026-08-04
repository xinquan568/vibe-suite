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


class TestMalformedInput(DoctorCase):
    """A diagnosis that dies on the input it exists to diagnose reports nothing about the rest."""

    def _corrupt(self, rel):
        self.install()
        (self.ws / rel).write_text("{not json\n", encoding="utf-8")
        result = self.doctor()
        self.assertNotIn("Traceback", result.stderr, f"{rel} produced a traceback")
        return json.loads(result.stdout)

    def test_malformed_provenance_is_a_finding(self):
        report = self._corrupt(".vibe-suite-state/install-provenance.json")
        self.assertEqual(report["state"], "partial")

    def test_malformed_mcp_json_is_a_finding(self):
        self.assertIn("sentinels", self.checks(self._corrupt(".mcp.json")))

    def test_malformed_hooks_json_is_a_finding(self):
        self.assertIn("hooks", self.checks(self._corrupt(".codex/hooks.json")))


class TestReadOnlyStrict(DoctorCase):
    def test_read_only_holds_and_the_run_succeeds(self):
        """The earlier read-only tests passed even if doctor crashed before touching anything."""
        self.install()
        before = {p: (Path(p).stat().st_mode & 0o777) for p in
                  (str(x) for x in self.ws.rglob("*") if x.is_file())}
        result = self.doctor()
        self.assertIn(result.returncode, (0, 1), result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        after = {p: (Path(p).stat().st_mode & 0o777) for p in
                 (str(x) for x in self.ws.rglob("*") if x.is_file())}
        self.assertEqual(after, before, "doctor changed a file mode")


ADVISOR_DEFN = """---
description: |
  Judges probe things.
model: sonnet
---

Value the smallest true answer.
"""


class TestAdvisorState(DoctorCase):
    """E6.1: a non-consistent advisor is a fixable finding — repair reconciles it."""

    def test_a_declared_unregistered_advisor_is_a_fixable_finding(self):
        self.install()
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(ADVISOR_DEFN, encoding="utf-8")
        report = self.report()
        rows = [f for f in report["findings"] if f["check"] == "advisor-state"]
        self.assertEqual(len(rows), 1, report["findings"])
        self.assertTrue(rows[0]["auto_fixable"])
        self.assertIn("declared-unregistered", rows[0]["finding"])

    def test_a_consistent_workspace_has_no_advisor_finding(self):
        self.install()
        report = self.report()
        self.assertEqual([f for f in report["findings"] if f["check"] == "advisor-state"], [])


class TestAdvisorStateVariants(DoctorCase):
    """E6.1 round 3: stale content is fixable; an invalid registration is not."""

    ENTRY = {"command": "npx", "args": ["-y", "claude-octopus@9.9.9"],
             "env": {"CLAUDE_SERVER_NAME": "probe_advisor"},
             "_vibe-suite_owned": {"kind": "advisor", "schema": 1}}

    def _declare(self):
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(ADVISOR_DEFN, encoding="utf-8")

    def test_stale_registered_is_fixable(self):
        self.install()
        self._declare()
        mcp = self.ws / ".mcp.json"
        doc = json.loads(mcp.read_text())
        doc.setdefault("mcpServers", {})["probe_advisor"] = dict(self.ENTRY)
        mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        toml = self.ws / ".codex" / "config.toml"
        block = ("# >>> vibe-suite:server:probe_advisor v1 >>>\n"
                 '[mcp_servers.probe_advisor]\ncommand = "npx"\n'
                 'args = ["-y", "claude-octopus@9.9.9"]\n'
                 "# <<< vibe-suite:server:probe_advisor <<<\n")
        toml.write_text(toml.read_text() + block)
        rows = [f for f in self.report()["findings"] if f["check"] == "advisor-state"]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("stale-registered", rows[0]["finding"])
        self.assertTrue(rows[0]["auto_fixable"])

    def test_invalid_registration_is_not_fixable(self):
        self.install()
        self._declare()
        mcp = self.ws / ".mcp.json"
        doc = json.loads(mcp.read_text())
        entry = dict(self.ENTRY, args=["-y", "claude-octopus@latest"])
        doc.setdefault("mcpServers", {})["probe_advisor"] = entry
        mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        rows = [f for f in self.report()["findings"] if f["check"] == "advisor-state"]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("invalid-registration", rows[0]["finding"])
        self.assertFalse(rows[0]["auto_fixable"])
