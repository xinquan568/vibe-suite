# SPDX-License-Identifier: ISC
"""E3.5 (vibe-30) acceptance: `bin/vibe-check` — deterministic CI validator (F4.4 as
amended by ADR-0001). Oracles are hand-derived (tests/fixtures/vibe-check/README.md
predates the engine).

CLI: bin/vibe-check [dir] [--json] [--report PATH] [--mirrors]. Exit 0 clean / 1 findings
/ 2 error. Report-only mode when --report is given with neither dir nor --mirrors; the
report is validated against the installation's canonical schema only (no CLI override);
UnsupportedSchemaError is exercised at the importable module seam.
"""

import importlib.machinery
import importlib.util
import json
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN = REPO_ROOT / "bin" / "vibe-check"
FIX = REPO_ROOT / "tests" / "fixtures" / "vibe-check"
SAMPLE = REPO_ROOT / "tests" / "fixtures" / "sample-report.json"
GOLDEN = FIX / "expected-manifest-vs-disk.json"


def run_check(*args, cwd=REPO_ROOT):
    return subprocess.run([sys.executable, str(BIN), *args],
                          capture_output=True, cwd=cwd)


def load_module():
    """Import the extensionless executable as a module (the test seam)."""
    loader = importlib.machinery.SourceFileLoader("vibe_check", str(BIN))
    spec = importlib.util.spec_from_loader("vibe_check", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Deliverables(unittest.TestCase):
    def test_compiles_and_ships_isc(self):
        # CI's *.py find misses the suffix-less file; this compile IS its syntax gate.
        py_compile.compile(str(BIN), doraise=True)
        head = BIN.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in l for l in head))

    def test_templates_ship(self):
        pre = REPO_ROOT / "templates" / "pre-commit"
        yml = REPO_ROOT / "templates" / "ci-vibe-check.yml"
        self.assertTrue(pre.is_file())
        self.assertTrue(yml.is_file())
        self.assertIn("vibe-check", pre.read_text(encoding="utf-8"))
        self.assertIn("vibe-check", yml.read_text(encoding="utf-8"))
        # both pass the root explicitly rather than relying on incidental CWD
        self.assertIn("git rev-parse --show-toplevel", pre.read_text(encoding="utf-8"))


class PerClassFixtures(unittest.TestCase):
    """One failing case per check class (the hook class carries two fixtures)."""

    CASES = [
        ("manifest-vs-disk",
         ["manifest-vs-disk: agents/stray.md: on disk but not registered in plugin.json",
          "manifest-vs-disk: commands/ghost.md: registered in plugin.json but absent on disk"]),
        ("unregistered-skill",
         ["unregistered-skill: skills/orphan: SKILL.md present but not in plugin.json skills[]"]),
        ("frontmatter",
         ["frontmatter: agents/nodesc.md: missing required key 'description'",
          "frontmatter: commands/noblock.md: missing frontmatter block",
          "frontmatter: commands/shared/invocable-true.md: key 'user-invocable' must be false",
          "frontmatter: commands/shared/nodesc.md: missing required key 'description'"]),
        ("name-dir",
         ["name-dir: skills/alpha/SKILL.md: name 'beta' does not match directory 'alpha'"]),
        ("hook-case",
         ["hook-case: hooks/hooks.json: event 'postToolUse' should be 'PostToolUse'"]),
        ("hook-case-configured",
         ["hook-case: config/custom-hooks.json: event 'sessionstart' should be 'SessionStart'"]),
        ("monorepo",
         ["monorepo: sub-a: sub-plugin root (run vibe-check per sub-plugin)",
          "monorepo: sub-b: sub-plugin root (run vibe-check per sub-plugin)"]),
        ("version",
         ["version: .claude-plugin/marketplace.json: plugin 'fixture-version' version "
          "'9.9.9' != plugin.json version '0.0.1'"]),
    ]

    def test_structural_fixtures(self):
        for fixture, expected in self.CASES:
            with self.subTest(fixture=fixture):
                proc = run_check(str(FIX / fixture))
                out = proc.stdout.decode()
                self.assertEqual(proc.returncode, 1, out + proc.stderr.decode())
                lines = [l for l in out.splitlines() if ": " in l and not
                         l.startswith("vibe-check:")]
                self.assertEqual(lines, expected)

    def test_hook_open_world_anti_seed(self):
        # 'TotallyNewEvent' (exact unknown name) must NOT be a finding (§6 open world).
        out = run_check(str(FIX / "hook-case")).stdout.decode()
        self.assertNotIn("TotallyNewEvent", out)

    def test_mirrors_missing_refusal(self):
        # The deferred class's CURRENT failing case: refusal naming the dependency.
        proc = run_check(str(FIX / "mirrors-missing"), "--mirrors")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("mirror hash manifest not found; ships with E7.2/F9.6",
                      proc.stderr.decode())


class SuiteSelf(unittest.TestCase):
    def test_exit_zero_on_the_suite_itself(self):
        # Rung 3's first truthful evaluation (issue #30 acceptance).
        proc = run_check(str(REPO_ROOT))
        self.assertEqual(proc.returncode, 0,
                         proc.stdout.decode() + proc.stderr.decode())
        self.assertIn("vibe-check: clean", proc.stdout.decode())


class ReportValidation(unittest.TestCase):
    def test_sample_report_passes(self):
        proc = run_check("--report", str(SAMPLE))
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_sample_report_passes_from_non_plugin_cwd(self):
        # Report-only mode requires no plugin root ("explicit, always available").
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_check("--report", str(SAMPLE), cwd=tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())

    def test_invalid_report_is_a_finding(self):
        proc = run_check("--report", str(FIX / "report-invalid.json"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("report:", proc.stdout.decode())

    def test_non_json_report_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "not-json.json"
            bad.write_text("not json at all", encoding="utf-8")
            proc = run_check("--report", str(bad))
        self.assertEqual(proc.returncode, 2)

    def test_unreadable_report_is_an_error(self):
        proc = run_check("--report", str(FIX / "no-such-report.json"))
        self.assertEqual(proc.returncode, 2)

    def test_unsupported_schema_raises_at_the_seam_and_maps_to_2(self):
        # No CLI override exists (ADR-0001 binds --report to the canonical schema);
        # the seam is the importable function, called with a synthetic 14-keyword schema.
        module = load_module()
        rc, findings = module.validate_report(
            SAMPLE, schema_path=FIX / "schema-unsupported.json")
        self.assertEqual(rc, 2)
        self.assertEqual(findings, [])

    def test_report_plus_mirrors_engages_directory_mode(self):
        # --mirrors always engages directory mode; pre-E7.2 ITS refusal governs the
        # outcome — not an unrelated non-plugin-root error.
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_check("--report", str(SAMPLE), "--mirrors", cwd=tmp)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("mirror hash manifest not found; ships with E7.2/F9.6",
                      proc.stderr.decode())


class ErrorTaxonomy(unittest.TestCase):
    def _tmp_plugin(self, tmp, manifest_text):
        root = Path(tmp)
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "plugin.json").write_text(manifest_text,
                                                             encoding="utf-8")
        return root

    def test_bad_dir(self):
        self.assertEqual(run_check(str(REPO_ROOT / "no-such-dir")).returncode, 2)

    def test_empty_non_plugin_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_check(tmp).returncode, 2)

    def test_malformed_plugin_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_check(str(self._tmp_plugin(tmp, "{not json"))).returncode, 2)

    def test_structurally_unusable_manifests(self):
        for manifest in ('["a", "list"]',
                         '{"name": "x", "commands": "not-a-list"}',
                         '{"name": "x", "hooks": 7}'):
            with self.subTest(manifest=manifest):
                with tempfile.TemporaryDirectory() as tmp:
                    proc = run_check(str(self._tmp_plugin(tmp, manifest)))
                self.assertEqual(proc.returncode, 2, manifest)

    def test_malformed_configured_hooks_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tmp_plugin(
                tmp, '{"name": "x", "hooks": "./hooks/hooks.json"}')
            (root / "hooks").mkdir()
            (root / "hooks" / "hooks.json").write_text("{broken", encoding="utf-8")
            self.assertEqual(run_check(str(root)).returncode, 2)

    def test_malformed_marketplace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tmp_plugin(tmp, '{"name": "x"}')
            (root / ".claude-plugin" / "marketplace.json").write_text(
                "{broken", encoding="utf-8")
            self.assertEqual(run_check(str(root)).returncode, 2)

    def test_missing_name_is_a_finding_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run_check(str(self._tmp_plugin(tmp, '{"version": "0.0.1"}')))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("required 'name'", proc.stdout.decode())

    def test_version_vacuous_pass(self):
        # A marketplace entry without a version field claims nothing.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tmp_plugin(tmp, '{"name": "x", "version": "1.0.0"}')
            (root / ".claude-plugin" / "marketplace.json").write_text(
                '{"name": "m", "plugins": [{"name": "x"}]}', encoding="utf-8")
            self.assertEqual(run_check(str(root)).returncode, 0)

    def test_registration_is_per_component_class(self):
        # A commands file listed only under agents[] is NOT registered as a command.
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tmp_plugin(
                tmp, '{"name": "x", "agents": ["./commands/x.md"], "commands": []}')
            (root / "commands").mkdir()
            (root / "commands" / "x.md").write_text(
                "---\ndescription: d.\n---\n# x\n", encoding="utf-8")
            proc = run_check(str(root))
        self.assertEqual(proc.returncode, 1)
        self.assertIn(
            "manifest-vs-disk: commands/x.md: on disk but not registered", 
            proc.stdout.decode())

    def test_skills_entry_may_name_the_skill_md_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._tmp_plugin(
                tmp, '{"name": "x", "skills": ["./skills/s/SKILL.md"]}')
            (root / "skills" / "s").mkdir(parents=True)
            (root / "skills" / "s" / "SKILL.md").write_text(
                "---\nname: s\ndescription: d.\n---\n# s\n", encoding="utf-8")
            proc = run_check(str(root))
        self.assertEqual(proc.returncode, 0,
                         proc.stdout.decode() + proc.stderr.decode())

    def test_manifest_paths_are_contained(self):
        # Absolute and traversal entries are findings and are never read/registered.
        for entry_json in ('{"name": "x", "commands": ["../outside.md"]}',
                           '{"name": "x", "commands": ["/etc/passwd"]}',
                           '{"name": "x", "hooks": "../../outside-hooks.json"}'):
            with self.subTest(manifest=entry_json):
                with tempfile.TemporaryDirectory() as tmp:
                    proc = run_check(str(self._tmp_plugin(tmp, entry_json)))
                self.assertEqual(proc.returncode, 1, entry_json)
                self.assertIn("escapes the plugin root", proc.stdout.decode())

    def test_invalid_utf8_manifest_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude-plugin").mkdir()
            (root / ".claude-plugin" / "plugin.json").write_bytes(
                b'{"name": "x\xff"}')
            proc = run_check(str(root))
        self.assertEqual(proc.returncode, 2)

    def test_invalid_utf8_report_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_bytes(b'{"agent": "\xff"}')
            proc = run_check("--report", str(bad))
        self.assertEqual(proc.returncode, 2)

    def test_inline_hooks_object_at_the_seam(self):
        # The inline branch of hook-config resolution shares the event-map reader.
        module = load_module()
        findings = module.check_hook_case(
            Path("."), {"name": "x", "hooks": {"hooks": {"postToolUse": []}}})
        self.assertEqual(len(findings), 1)
        self.assertIn("PostToolUse", findings[0]["detail"])


class JsonOutput(unittest.TestCase):
    def test_golden_and_determinism(self):
        outs = []
        for _ in range(3):
            proc = run_check("tests/fixtures/vibe-check/manifest-vs-disk", "--json")
            self.assertEqual(proc.returncode, 1)
            outs.append(proc.stdout)
        self.assertEqual(outs[0], outs[1])
        self.assertEqual(outs[1], outs[2])
        self.assertEqual(json.loads(outs[0].decode()),
                         json.loads(GOLDEN.read_text(encoding="utf-8")))

    def test_report_only_json_root_null(self):
        proc = run_check("--report", str(SAMPLE), "--json")
        got = json.loads(proc.stdout.decode())
        self.assertIsNone(got["root"])
        self.assertFalse(got["checked"]["manifest-vs-disk"])
        self.assertTrue(got["checked"]["report"])


if __name__ == "__main__":
    unittest.main()
