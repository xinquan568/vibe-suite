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
import re
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
        # E7.2: mirror-staleness is LIVE when the plugin ships its manifest — a clean live
        # check contributes neither a finding nor an unavailable row.
        self.assertNotIn("mirror-staleness", statuses)
        self.assertEqual(self.severities(report), ["[GOOD]"])

    def test_row_9_records_the_executed_migration_without_pending_semantics(self):
        """E8.5 (vibe-62): the migration EXECUTED, and the row must say so.

        The row stays in the capability table — a project-local, read-only command still has
        no readable receipt, because the receipt (.vibe-suite-migration/manifest.sha256 +
        provenance.json) lives on the auditor-data branch — but its reason must record the
        executed migration, not describe a pending one. The issue's acceptance clause
        ("doctor's 'migration pending' clears") is honored exactly here: no doctor surface
        may present §7A row 9 as outstanding. The user-facing contract in commands/doctor.md
        must present the same resolution, or the two surfaces drift.
        """
        self.install()
        report = self.report()
        rows = {c["check"]: c for c in report["capabilities"]}
        self.assertIn("legacy-auditor-data", rows,
                      "the row 9 capability disappeared; an omitted row is indistinguishable "
                      "from a passing one")
        row = rows["legacy-auditor-data"]
        self.assertEqual(row["status"], "unavailable",
                         "a project-local command still has no readable receipt; the row "
                         "must stay a capability, not become a finding or vanish")
        # Both surfaces must carry the SAME resolution — the same execution date and the
        # same receipt location — and neither may present the migration as pending or
        # outstanding in any wording. Substring checks alone let pending-semantics sneak
        # back beside the asserted date; the semantics are asserted directly.
        runtime_text = row["blocked_on"]
        doc = (Path(__file__).resolve().parent.parent / "commands" / "doctor.md").read_text()
        doc_row = re.search(r"§7A row 9 \(([^)]*)\)", doc)
        self.assertIsNotNone(doc_row,
                             "commands/doctor.md no longer carries a row-9 resolution "
                             "parenthetical — the two doctor surfaces have drifted")
        doc_text = doc_row.group(1)
        for surface, text in (("scripts/doctor.py", runtime_text),
                              ("commands/doctor.md", doc_text)):
            self.assertIn("executed 2026-08-13", text,
                          f"{surface} does not record the executed migration: {text!r}")
            self.assertIn("auditor-data", text,
                          f"{surface} does not name where the receipt lives: {text!r}")
            self.assertNotRegex(
                text, r"(?i)\b(pending|outstanding|not yet|awaiting)\b",
                f"{surface} reintroduced pending semantics beside the execution record: "
                f"{text!r}")

    def test_mirror_staleness_states(self):
        """E7.2 (round-4): absent manifest → capability row; stale mirror → HIGH with the
        plugin-root remediation; the check is read-only and runs from a workspace OUTSIDE
        the plugin root (CLAUDE_PLUGIN_ROOT resolution)."""
        import hashlib
        import shutil as _sh
        import sys
        import tempfile as _tf
        self.install()
        with _tf.TemporaryDirectory(prefix="doctor-plugin-") as tmp:
            plugin = Path(tmp) / "plugin"
            _sh.copytree(REPO_ROOT, plugin, symlinks=True,
                         ignore=_sh.ignore_patterns(".git", "node_modules", "__pycache__"))
            def tree_hash():
                h = hashlib.sha256()
                for f in sorted(plugin.rglob("*")):
                    if f.is_file():
                        h.update(f.relative_to(plugin).as_posix().encode())
                        h.update(f.read_bytes())
                return h.hexdigest()
            import json as _json
            import os as _os
            import subprocess as _sp

            def run_doctor():
                """The REAL entry — doctor subprocess from the OUTSIDE workspace with
                CLAUDE_PLUGIN_ROOT pointing at the temp plugin (round-4 F6)."""
                env = dict(_os.environ, CLAUDE_PLUGIN_ROOT=str(plugin))
                proc = _sp.run([sys.executable, str(plugin / "scripts" / "doctor.py"),
                                "--workspace", str(self.ws), "--json"],
                               capture_output=True, text=True, env=env, timeout=300)
                return _json.loads(proc.stdout)

            # absent
            _sh.rmtree(plugin / "codex")
            report = run_doctor()
            caps = {c["check"]: c for c in report["capabilities"]}
            self.assertEqual(caps["mirror-staleness"]["status"], "unavailable")
            self.assertNotIn("mirror-staleness",
                             {f["check"] for f in report["findings"]})
            # clean
            _sp.run([sys.executable, str(plugin / "scripts" / "mirror-sync.py"),
                     "generate", "--root", str(plugin)], check=True, capture_output=True)
            report = run_doctor()
            self.assertNotIn("mirror-staleness",
                             {f["check"] for f in report["findings"]})
            self.assertNotIn("mirror-staleness",
                             {c["check"] for c in report["capabilities"]})
            # stale, read-only
            victim = plugin / "codex" / "README.md"
            victim.write_text(victim.read_text() + "tamper\n")
            before = tree_hash()
            report = run_doctor()
            rows = [f for f in report["findings"] if f["check"] == "mirror-staleness"]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["severity"], "[HIGH]")
            self.assertIn("bridge mirrors", rows[0]["finding"])
            self.assertIn("CLAUDE_PLUGIN_ROOT", rows[0]["finding"])
            self.assertFalse(rows[0]["auto_fixable"])
            self.assertEqual(tree_hash(), before, "the doctor run wrote to the plugin")

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

    def test_floating_target_is_fixable_under_the_shipped_pin(self):
        # Pre-E7.1 this scenario was invalid-registration (a floating target with no default pin
        # to settle it — not auto-fixable). The shipped pin (vibe-53) settles the target, so the
        # same seed now classifies as a repairable divergence. The unsettleable-target refusal
        # remains covered by explicit pending-file cases in tests/test_advisors.py.
        self.install()
        self._declare()
        mcp = self.ws / ".mcp.json"
        doc = json.loads(mcp.read_text())
        entry = dict(self.ENTRY, args=["-y", "claude-octopus@latest"])
        doc.setdefault("mcpServers", {})["probe_advisor"] = entry
        mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        rows = [f for f in self.report()["findings"] if f["check"] == "advisor-state"]
        self.assertEqual(len(rows), 1, rows)
        self.assertNotIn("invalid-registration", rows[0]["finding"])
        self.assertTrue(rows[0]["auto_fixable"])


class TestKnowledgeFreshnessStates(DoctorCase):
    """E6.5 (vibe-51): the four reconciled freshness states. A valid record surfaces its date
    as a capability; the no-record capability says never-refreshed and cites #51; every
    malformed shape is the LOW finding (and exit 1); the staler-recommendation compares the
    record date against the overlay's canonical prose line."""

    def plugin_root(self, refreshed_json=None, prose_date="2026-06-07"):
        root = Path(tempfile.mkdtemp(prefix="vibe-pluginroot-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        skill = root / "skills" / "conventions-claude"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: conventions-claude\n---\n\n# Overlay\n\n"
            f"**Spec freshness:** verified {prose_date} against code.claude.com/docs/en/\n",
            encoding="utf-8")
        if refreshed_json is not None:
            (skill / "refreshed.json").write_text(refreshed_json, encoding="utf-8")
        return root

    def doctor_with_root(self, root):
        env = dict(os.environ, CODEX_HOME=str(self.home), CLAUDE_PLUGIN_ROOT=str(root))
        return subprocess.run(["python3", str(DOCTOR), "--workspace", str(self.ws),
                               "--json"], capture_output=True, text=True, env=env)

    def freshness_capability(self, report):
        rows = [c for c in report["capabilities"] if c["check"] == "knowledge-freshness"]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_no_record_capability_is_never_refreshed_and_cites_51(self):
        self.install()
        r = self.doctor_with_root(self.plugin_root())
        self.assertEqual(r.returncode, 0, r.stdout)
        cap = self.freshness_capability(json.loads(r.stdout))
        self.assertEqual(cap["status"], "unavailable")
        self.assertIn("never refreshed", cap["blocked_on"])
        self.assertIn("#51", cap["blocked_on"])

    def test_valid_record_surfaces_the_date_without_a_finding(self):
        self.install()
        root = self.plugin_root('{"refreshed": "2026-06-07"}')
        r = self.doctor_with_root(root)
        self.assertEqual(r.returncode, 0, r.stdout)
        report = json.loads(r.stdout)
        cap = self.freshness_capability(report)
        self.assertEqual(cap["status"], "refreshed 2026-06-07")
        self.assertEqual(cap["blocked_on"], "—")
        self.assertNotIn("knowledge-freshness", {f["check"] for f in report["findings"]})

    def test_prose_older_recommends_spec_sync(self):
        self.install()
        root = self.plugin_root('{"refreshed": "2026-08-01"}', prose_date="2026-06-07")
        cap = self.freshness_capability(json.loads(self.doctor_with_root(root).stdout))
        self.assertIn("spec-sync", cap["blocked_on"])

    def test_record_older_recommends_refresh_knowledge(self):
        self.install()
        root = self.plugin_root('{"refreshed": "2026-05-01"}', prose_date="2026-06-07")
        cap = self.freshness_capability(json.loads(self.doctor_with_root(root).stdout))
        self.assertIn("refresh-knowledge", cap["blocked_on"])

    def test_every_malformed_shape_is_the_low_finding_and_exit_1(self):
        cases = ("{nope", '{"other": true}', '{"refreshed": ""}',
                 '{"refreshed": "yesterday"}', '{"refreshed": "2026-99-99"}',
                 '{"refreshed": "20260607"}')
        for raw in cases:
            with self.subTest(raw=raw):
                self.install()
                r = self.doctor_with_root(self.plugin_root(raw))
                self.assertEqual(r.returncode, 1, r.stdout)
                report = json.loads(r.stdout)
                lows = [f for f in report["findings"]
                        if f["check"] == "knowledge-freshness"]
                self.assertEqual(len(lows), 1)
                self.assertEqual(lows[0]["severity"], "[LOW]")
