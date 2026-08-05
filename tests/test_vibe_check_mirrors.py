#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""E7.2 (vibe-54): the vibe-check mirrors class — the reader half of the staleness contract.

Every case builds its tree through the GENERATOR and then breaks exactly one promise, so the
checker is validated against trees the writer really produces (and the hand-broken deltas are
the independent oracle). Cases: clean; hand-edited mirror; edited source; unaccounted file;
missing mirror; version drift; malformed manifest; duplicate record; bad generated
frontmatter; omitted sidecar (record+mirror both deleted); omitted copied dependency.
"""

import importlib.machinery
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "tests"))
from test_mirror_sync import FIXTURE_SETS, make_source_tree, mirror_sync  # noqa: E402


def _load_vibe_check():
    loader = importlib.machinery.SourceFileLoader(
        "vibe_check_mod", str(REPO_ROOT / "bin" / "vibe-check"))
    spec = importlib.util.spec_from_loader("vibe_check_mod", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


vibe_check = _load_vibe_check()

#: The fixture-world inventory for the API-only seam — the CLI stays production-bound; these
#: tests exercise the CHECK LOGIC against trees the fixture generator really produces.
FIXTURE_EXPECTED = {
    "knowledge": FIXTURE_SETS["knowledge"],
    "workflow": FIXTURE_SETS["workflow"],
    "roast_agents": FIXTURE_SETS["roast_agents"],
    "copied_deps": FIXTURE_SETS["copied_deps"],
    "generated_outputs": {
        "commands/roast.md": "codex/skills/vibe-roast/SKILL.md",
        ".claude-plugin/plugin.json": "codex/README.md",
    },
}


def run_check(root):
    """Findings from the mirrors class via the API seam, shaped like CLI output."""
    findings = vibe_check.check_mirrors(root, expected=FIXTURE_EXPECTED)
    class R:  # noqa: N801 — a tiny result shim keeping the assertion style uniform
        returncode = 1 if findings else 0
        stdout = "\n".join(f"mirrors: {f['path']}: {f['detail']}" for f in findings)
        stderr = ""
    return R


class MirrorsClass(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="vc-mirrors-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = make_source_tree(self.tmp)
        mirror_sync.generate(self.root, sets=FIXTURE_SETS)
        self.manifest_path = self.root / "codex" / "MIRROR-MANIFEST.json"

    def manifest(self):
        return json.loads(self.manifest_path.read_text())

    def write_manifest(self, doc):
        self.manifest_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")

    def assert_fail(self, needle):
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn(needle, proc.stdout + proc.stderr)

    def test_clean_tree_passes(self):
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_hand_edited_mirror_fails(self):
        p = self.root / "codex" / "skills" / "vibe-alpha" / "SKILL.md"
        p.write_text(p.read_text() + "\ntampered\n")
        self.assert_fail("vibe-alpha/SKILL.md")

    def test_edited_source_fails(self):
        p = self.root / "skills" / "alpha" / "SKILL.md"
        p.write_text(p.read_text() + "\nnew source line\n")
        self.assert_fail("skills/alpha/SKILL.md")

    def test_unaccounted_file_fails(self):
        (self.root / "codex" / "skills" / "stray.md").write_text("stray\n")
        self.assert_fail("stray.md")

    def test_missing_mirror_fails(self):
        (self.root / "codex" / "skills" / "vibe-beta" / "SKILL.md").unlink()
        self.assert_fail("vibe-beta/SKILL.md")

    def test_version_drift_fails(self):
        doc = self.manifest()
        doc["plugin_version"] = "0.0.0-stale"
        self.write_manifest(doc)
        self.assert_fail("version")

    def test_malformed_manifest_fails(self):
        self.manifest_path.write_text("{not json\n")
        self.assert_fail("manifest")

    def test_duplicate_record_fails(self):
        doc = self.manifest()
        doc["records"].append(dict(doc["records"][0]))
        self.write_manifest(doc)
        self.assert_fail("duplicate")

    def test_bad_generated_frontmatter_fails(self):
        p = self.root / "codex" / "skills" / "vibe-beta" / "SKILL.md"
        body = p.read_text().split("---", 2)[2]
        new = "---\nname: WRONG_NAME\ndescription: Beta knowledge.\n---" + body
        p.write_text(new)
        doc = self.manifest()
        for r in doc["records"]:
            if r["mirror"] == "codex/skills/vibe-beta/SKILL.md":
                r["mirror_sha256"] = mirror_sync.sha256_file(p)
        self.write_manifest(doc)
        self.assert_fail("frontmatter")

    def test_omitted_sidecar_fails(self):
        (self.root / "codex" / "skills" / "vibe-alpha" / "references" / "depth.md").unlink()
        doc = self.manifest()
        doc["records"] = [r for r in doc["records"]
                          if r["source"] != "skills/alpha/references/depth.md"]
        self.write_manifest(doc)
        self.assert_fail("depth.md")

    def test_omitted_copied_dependency_fails(self):
        (self.root / "codex" / "schemas" / "audit-output.schema.json").unlink()
        doc = self.manifest()
        doc["records"] = [r for r in doc["records"]
                          if r["source"] != "schemas/audit-output.schema.json"]
        self.write_manifest(doc)
        self.assert_fail("audit-output.schema.json")

    def test_absent_manifest_keeps_refusal(self):
        # The refusal precedes inventory logic, so the CLI path is exercised directly here.
        self.manifest_path.unlink()
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "bin" / "vibe-check"), str(self.root),
             "--mirrors"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_deleting_a_mandatory_generated_output_fails(self):
        # Round-4 F1: the variant, the partial copies and the README are anchored outputs —
        # removing any pair (record + mirror) is a finding, not a silent shrink.
        for gen_mirror in ("codex/skills/vibe-roast/SKILL.md", "codex/README.md"):
            with self.subTest(mirror=gen_mirror):
                mirror_sync.generate(self.root, sets=FIXTURE_SETS)
                (self.root / gen_mirror).unlink()
                doc = self.manifest()
                doc["records"] = [r for r in doc["records"] if r["mirror"] != gen_mirror]
                self.write_manifest(doc)
                proc = run_check(self.root)
                self.assertEqual(proc.returncode, 1)
                self.assertIn(gen_mirror.rsplit("/", 1)[-1], proc.stdout)

    def test_malformed_types_yield_findings_not_tracebacks(self):
        # Round-4 F5: scalar documents, non-object rows, non-string set members.
        cases = [
            "42\n",
            json.dumps({"schema": 1, "plugin_version": "x", "records": "nope",
                        "out_of_scope": [], "exclusions": [], "sets": {}}),
            json.dumps({"schema": 1, "plugin_version": "x", "records": [],
                        "out_of_scope": [17], "exclusions": [], "sets":
                        {"knowledge": [], "workflow": [], "roast_agents": [],
                         "copied_deps": {}}}),
            json.dumps({"schema": 1, "plugin_version": "x", "records": [],
                        "out_of_scope": [], "exclusions": [], "sets":
                        {"knowledge": [3], "workflow": [], "roast_agents": [],
                         "copied_deps": {}}}),
        ]
        for i, payload in enumerate(cases):
            with self.subTest(case=i):
                self.manifest_path.write_text(payload)
                proc = run_check(self.root)   # must not raise
                self.assertEqual(proc.returncode, 1)

    def test_symlink_escaping_source_is_a_finding(self):
        outdir = tempfile.mkdtemp(prefix="vc-outside-")
        self.addCleanup(shutil.rmtree, outdir, True)
        outside = Path(outdir) / "outside.md"
        outside.write_text("outside\n")
        link = self.root / "sneaky.md"
        link.symlink_to(outside)
        doc = self.manifest()
        doc["records"].append({"source": "sneaky.md",
                               "mirror": "codex/skills/vibe-alpha/SKILL.md",
                               "source_sha256": "0" * 64, "mirror_sha256": "0" * 64,
                               "transform": "verbatim", "dropped_keys": []})
        self.write_manifest(doc)
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("resolves outside", proc.stdout)

    def test_shrunken_declaration_is_itself_a_finding(self):
        # B1: a manifest that reclassifies or shrinks a set cannot pass — the declarations
        # are COMPARED to the expected inventory, never trusted.
        doc = self.manifest()
        doc["sets"]["knowledge"] = [k for k in doc["sets"]["knowledge"] if k != "alpha"]
        doc["sets"]["workflow"] = list(doc["sets"]["workflow"]) + ["alpha"]
        self.write_manifest(doc)
        proc = run_check(self.root)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("differs from the production inventory", proc.stdout)


if __name__ == "__main__":
    unittest.main()
