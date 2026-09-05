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
import sys  # noqa: E402
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import bridge  # noqa: E402


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
                text, r"(?i)\b(pending|outstanding|not[\s-]+yet|awaiting)\b",
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
    def test_a_dangling_bare_registration_is_detected_and_flagged_fixable_per_file(self):
        # grill S4 (vibe-191): the old `command = "vibe-suite"` registrations name a binary that
        # does not ship — each file carrying one is a fixable `sentinels` finding that names it
        self.install()
        plant_dangling_registrations(self.ws)
        findings = [f for f in self.report()["findings"] if f["check"] == "sentinels"]
        named = {f["finding"].split(" ")[0] for f in findings if "dangling" in f["finding"]}
        self.assertEqual(named, {".codex/config.toml", ".mcp.json", ".codex/hooks.json"}, findings)
        self.assertTrue(all(f["auto_fixable"] for f in findings if "dangling" in f["finding"]))

    def test_the_absence_of_a_vibe_mcp_registration_is_healthy(self):
        # nothing is registered until the binary ships; a fresh install must not be flagged
        self.install()
        self.assertEqual(self.severities(self.report()), ["[GOOD]"])

    def test_a_name_in_one_store_but_not_the_other_is_detected(self):
        """`inventory_enumerate` unions the two stores, so a half-registration is invisible unless
        both are asked. (A non-bare command — an absolute path — so this is the symmetry finding,
        not the dangling one.)"""
        self.install()
        (self.ws / ".mcp.json").write_text(json.dumps({"mcpServers": {
            "vibe-mcp": {"command": "/opt/vibe-suite/bin/vibe-suite", "args": []}}}, indent=2) + "\n",
            encoding="utf-8")
        report = self.report()
        self.assertIn("sentinels", self.checks(report))
        half = [f for f in report["findings"] if "registered only in .mcp.json" in f["finding"]]
        self.assertEqual(len(half), 1, report["findings"])
        self.assertFalse(half[0]["auto_fixable"], "repair registers nothing under vibe-mcp — not auto-fixable")

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
        # an OWNED Stop entry with an absolute command that does not exist (the shape a shipped
        # binary would register under, pointing nowhere) — init registers no hook today, so plant it
        self.install()
        (self.ws / ".codex").mkdir(exist_ok=True)
        doc = bridge.json_hook_entry_upsert({}, "Stop", {"type": "command", "command": "/nonexistent/vibe-suite-binary stop-gate"})
        (self.ws / ".codex" / "hooks.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
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

    def _add(self, name="probe_advisor"):
        r = subprocess.run(["python3", str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(self.ws),
                            "add", name], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_declared_unregistered_advisor_is_a_low_finding_that_names_add_and_is_not_fixable(self):
        # vibe-185: the expected state of a definition the operator never registered — repair must
        # not "fix" it; the remedy is the explicit add. Pre-vibe-185 this was a fixable finding.
        self.install()
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(ADVISOR_DEFN, encoding="utf-8")
        report = self.report()
        rows = [f for f in report["findings"] if f["check"] == "advisor-state"]
        self.assertEqual(len(rows), 1, report["findings"])
        self.assertFalse(rows[0]["auto_fixable"])
        self.assertEqual(rows[0]["severity"], "[LOW]")
        self.assertIn("not registered", rows[0]["finding"])
        self.assertIn("/vibe-suite:advisor add probe_advisor", rows[0]["finding"])

    def test_an_edited_registered_advisor_is_a_medium_finding_that_names_add_and_is_not_fixable(self):
        self.install()
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(ADVISOR_DEFN, encoding="utf-8")
        self._add()
        self.assertEqual([f for f in self.report()["findings"] if f["check"] == "advisor-state"], [])
        (agents / "probe_advisor.md").write_text(ADVISOR_DEFN.replace("model: sonnet", "model: opus"), encoding="utf-8")
        rows = [f for f in self.report()["findings"] if f["check"] == "advisor-state"]
        self.assertEqual(len(rows), 1, rows)
        self.assertFalse(rows[0]["auto_fixable"])
        self.assertEqual(rows[0]["severity"], "[MEDIUM]")
        self.assertIn("changed since it was registered", rows[0]["finding"])
        self.assertIn("/vibe-suite:advisor add probe_advisor", rows[0]["finding"])

    def test_a_registration_without_a_stamp_is_a_medium_finding_that_names_add_and_is_not_fixable(self):
        self.install()
        self._declare_and_register_unstamped()
        rows = [f for f in self.report()["findings"] if f["check"] == "advisor-state"]
        self.assertEqual(len(rows), 1, rows)
        self.assertFalse(rows[0]["auto_fixable"])
        self.assertIn("without a registration stamp", rows[0]["finding"])
        self.assertIn("/vibe-suite:advisor add probe_advisor", rows[0]["finding"])

    def _declare_and_register_unstamped(self):
        agents = self.ws / ".vibe-suite" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "probe_advisor.md").write_text(ADVISOR_DEFN, encoding="utf-8")
        self._add()
        ledger = self.ws / ".vibe-suite-state" / "advisor-preimages.json"
        data = json.loads(ledger.read_text()); data.pop("registered")
        ledger.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

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

    def _stamp(self):
        # vibe-185: drift is fixable only for a REGISTERED (stamped) advisor; register it first.
        r = subprocess.run(["python3", str(REPO_ROOT / "scripts" / "advisor_cli.py"), "--workspace", str(self.ws),
                            "add", "probe_advisor"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_stale_registered_is_fixable(self):
        self.install()
        self._declare()
        self._stamp()
        mcp = self.ws / ".mcp.json"
        doc = json.loads(mcp.read_text())
        doc.setdefault("mcpServers", {})["probe_advisor"] = dict(self.ENTRY)
        mcp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        # vibe-185: `add` already wrote the TOML block; the stale .mcp.json entry above is the drift.
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
        self._stamp()
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


# --- vibe-209 -------------------------------------------------------------------------------------
import ast as _v209_ast                                                              # noqa: E402
import pathlib as _v209_pathlib                                                      # noqa: E402
import sys as _v209_sys                                                              # noqa: E402
import os as _v209_os                                                                # noqa: E402
import tempfile as _v209_tempfile                                                    # noqa: E402
from unittest import mock as _v209_mock                                              # noqa: E402

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


class ConnectivityCapabilityStagedNoticeTest(DoctorCase):
    """vibe-210 / grill M14 — doctor states the agy lane's RELEASE status, not only its gate status.

    The freeze requires every surface to describe the lane in the same words. Doctor's single agy
    sentence lives in the `connectivity` capability's `blocked_on`, which is the field a user reads
    when they ask why the lane is not available. Asserting it through the real report — rather than
    grepping the source — is what makes this a statement about what the user is shown.
    """

    def connectivity(self, report):
        rows = {c["check"]: c for c in report["capabilities"]}
        self.assertIn("connectivity", rows, "doctor must still emit the connectivity capability")
        return rows["connectivity"]

    def test_connectivity_states_the_staged_release_status(self):
        cap = self.connectivity(self.report())
        self.assertIn("staged; unavailable in this release", cap["blocked_on"])

    def test_connectivity_still_defers_to_preflight_and_names_the_gate(self):
        # The notice ADDS a release statement; it must not replace the two facts already there —
        # who owns the normalised lane result, and that a gate is what holds agy pending.
        cap = self.connectivity(self.report())
        self.assertEqual(cap["status"], "see-preflight")
        self.assertIn("/vibe-suite:preflight", cap["blocked_on"])
        self.assertIn("gate", cap["blocked_on"])


class RuntimeCapabilityRowTest(unittest.TestCase):
    """R18/R19 — doctor's runtime capability row (vibe-209 / grill P4).

    The row uses the shape doctor's other capability rows use — `check` / `status` / `blocked_on` —
    and NOT a `detail` field, which does not exist. `doctor.py` already ships the precedent for a
    capability that defers to preflight: `{"check": "connectivity", "status": "see-preflight"}`.
    """

    def _row(self, probe):
        import doctor
        capabilities = []
        doctor.runtime_capability(capabilities, probe=probe)
        self.assertEqual(len(capabilities), 1, "one row, aggregated — not one per runtime")
        return capabilities[0]

    def test_all_runtimes_healthy_reports_ok(self):
        row = self._row({"python3": (3, 14), "node": (24, 0), "git": (2, 43)})
        self.assertEqual(row["check"], "runtimes")
        self.assertEqual(row["status"], "ok")

    def test_node_below_18_is_unavailable(self):
        # The plan's only floor case was python3; deleting the node floor would have survived it.
        row = self._row({"python3": (3, 14), "node": (16, 20), "git": (2, 43)})
        self.assertEqual(row["status"], "unavailable")
        self.assertIn("node", row["blocked_on"])

    def test_python_below_3_11_is_unavailable(self):
        row = self._row({"python3": (3, 9), "node": (24, 0), "git": (2, 43)})
        self.assertEqual(row["status"], "unavailable")
        self.assertIn("python3", row["blocked_on"])

    def test_the_floors_themselves_pass(self):
        # A `>` where `>=` belongs rejects exactly the version the docs tell people to install.
        row = self._row({"python3": (3, 11), "node": (18, 0), "git": (2, 43)})
        self.assertEqual(row["status"], "ok")

    def test_missing_node_and_missing_git_are_each_reported(self):
        for absent in ("node", "git"):
            probe = {"python3": (3, 14), "node": (24, 0), "git": (2, 43)}
            probe[absent] = None
            row = self._row(probe)
            self.assertEqual(row["status"], "unavailable", absent)
            self.assertIn(absent, row["blocked_on"], absent)

    def test_a_mixed_state_is_unavailable_not_ok(self):
        row = self._row({"python3": (3, 14), "node": None, "git": (2, 43)})
        self.assertEqual(row["status"], "unavailable",
                         "vibe-core makes [GOOD] exclusive: partly missing is not available")

    def test_the_row_discloses_that_an_absent_python3_yields_no_doctor_output(self):
        # The bootstrap limit, in `blocked_on` so it reaches BOTH the JSON and the text renderer.
        # commands/doctor.md launches `python3 .../doctor.py`, so an ABSENT python3 produces no rows
        # at all — including this one. Preflight, which is Node-hosted, is the diagnostic for that.
        row = self._row({"python3": None, "node": (24, 0), "git": (2, 43)})
        self.assertIn("preflight", row["blocked_on"].lower(),
                      "the row must point at the tool that CAN see an absent python3")


class RuntimeProbeAndWiringTest(unittest.TestCase):
    """The parts `runtime_capability(probe=...)` never reaches (vibe-209, Step-8 finding 3).

    Calling the pure function with a pre-parsed dict proves the AGGREGATION and leaves everything
    around it untested: the probe that produces the dict, and the call that puts the row in the
    report at all. Both are deletable without any of those tests noticing.
    """

    def _probe_with(self, script_by_name):
        """Run probe_runtimes against a PATH of fake binaries built from raw shell scripts."""
        import doctor
        binder = _v209_pathlib.Path(_v209_tempfile.mkdtemp())
        for name, script in script_by_name.items():
            p = binder / name
            p.write_text(script)
            p.chmod(0o755)
        env = dict(_v209_os.environ, PATH=str(binder))
        with _v209_mock.patch.dict(_v209_os.environ, env, clear=True):
            return doctor.probe_runtimes()

    def test_a_failing_version_call_is_not_a_version(self):
        found = self._probe_with({
            "python3": "#!/bin/sh\nprintf 'Python 3.11.9\\n'\nexit 1\n",
            "node": "#!/bin/sh\nprintf 'v24.0.0\\n'\n",
            "git": "#!/bin/sh\nprintf 'git version 2.43.0\\n'\n",
        })
        self.assertIsNone(found["python3"],
                          "a non-zero --version is a failed probe, whatever it printed")

    def test_a_wrapper_version_is_not_mistaken_for_the_runtime(self):
        # Measured before the fix: this parsed as 9.0 and cleared the 3.11 floor.
        found = self._probe_with({
            "python3": "#!/bin/sh\nprintf 'wrapper 9.0 warning; Python 3.9.18\\n'\n",
            "node": "#!/bin/sh\nprintf 'v24.0.0\\n'\n",
            "git": "#!/bin/sh\nprintf 'git version 2.43.0\\n'\n",
        })
        self.assertIsNone(found["python3"], "only the runtime's own anchored banner counts")

    def test_a_banner_below_wrapper_chatter_is_still_read(self):
        found = self._probe_with({
            "python3": "#!/bin/sh\nprintf 'wrapper: pyenv shim\\nPython 3.14.6\\n'\n",
            "node": "#!/bin/sh\nprintf 'v24.0.0\\n'\n",
            "git": "#!/bin/sh\nprintf 'git version 2.43.0\\n'\n",
        })
        self.assertEqual(found["python3"], (3, 14),
                         "the anchor is per LINE — a false red would be no better than a false green")

    def test_a_missing_binary_is_none_not_a_crash(self):
        found = self._probe_with({"node": "#!/bin/sh\nprintf 'v24.0.0\\n'\n"})
        self.assertIsNone(found["python3"])
        self.assertIsNone(found["git"])

    def test_the_REPORT_from_diagnose_contains_the_runtimes_row(self):
        """Through `diagnose`, not a source search.

        Deleting `runtime_capability(capabilities)` leaves a source search passing if the words
        appear anywhere, and leaves every unit test on the pure function green. The row has to be
        in what the command actually emits.
        """
        import doctor
        ws = _v209_pathlib.Path(_v209_tempfile.mkdtemp())
        report = doctor.diagnose(ws)
        rows = [row for row in report["capabilities"] if row["check"] == "runtimes"]
        self.assertEqual(len(rows), 1,
                         "exactly one runtimes row in the emitted report: %r"
                         % [r["check"] for r in report["capabilities"]])
        self.assertIn(rows[0]["status"], ("ok", "unavailable"))
        self.assertIn("preflight", rows[0]["blocked_on"].lower(),
                      "and it still carries the bootstrap disclosure")


class RuntimeVersionBoundsTest(unittest.TestCase):
    """An implausible component is not a version (vibe-209, Step-9 finding 4)."""

    def test_an_oversized_component_is_rejected_not_truncated(self):
        import doctor
        # `\d{1,4}` without a lookahead TRUNCATES: `Python 3.12345` matched as (3, 1234), a version
        # that was never printed, handed to the floor comparison as if it had been read.
        self.assertIsNone(doctor.RUNTIME_VERSION_PATTERNS["python3"].search("Python 3.12345"),
                          "an implausible component means the output is not the banner it resembles")
        self.assertIsNotNone(doctor.RUNTIME_VERSION_PATTERNS["python3"].search("Python 3.11.9"))
