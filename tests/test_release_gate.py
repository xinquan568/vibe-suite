#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""AC-7 release-gate honesty (E7.4 / vibe-56).

The acceptance's demanding half: *each sub-check has a seeded-failure test proving the gate
actually gates*. A step that runs but cannot fail is worse than an absent one, so every
sub-check here is shown FAILING on a planted defect — each on a temporary COPY of the tree,
so the tracked corpus is never mutated.

The last class also pins the workflow's own contract: the five steps exist and each runs the
command the seeded case exercised, so a step renamed, dropped or rewired fails here rather
than silently ceasing to gate.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pre-release-quality-gate.yml"
IGNORE = shutil.ignore_patterns(".git", "node_modules", "__pycache__", "runs")


def copy_tree(dest):
    shutil.copytree(REPO_ROOT, dest, symlinks=True, ignore=IGNORE)
    return dest


class SeededFailures(unittest.TestCase):
    """One planted defect per sub-check; each must make its check fail."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="release-gate-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_tree(Path(self.tmp) / "repo")

    def run_in(self, *argv, **kw):
        return subprocess.run(argv, capture_output=True, text=True, cwd=self.root,
                              timeout=900, **kw)

    def test_score_fails_on_a_degraded_artifact(self):
        clean = self.run_in(sys.executable, "tools/release-score.py", "--threshold", "80")
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        victim = self.root / "agents" / "recon.md"
        head = victim.read_text(encoding="utf-8").split("---", 2)
        victim.write_text(f"---{head[1]}---\n\n# recon\n\nDo the thing.\n", encoding="utf-8")
        seeded = self.run_in(sys.executable, "tools/release-score.py", "--threshold", "80")
        self.assertEqual(seeded.returncode, 1, seeded.stdout + seeded.stderr)
        self.assertIn("agents/recon.md", seeded.stdout)

    def test_spec_contract_fails_on_a_missing_spec(self):
        (self.root / ".vibe-test" / "recon.spec.md").unlink()
        seeded = self.run_in(sys.executable, "-m", "unittest",
                             "tests.test_vibe_test_specs")
        self.assertNotEqual(seeded.returncode, 0, seeded.stdout + seeded.stderr)

    def test_mirrors_fails_on_a_hand_edited_mirror(self):
        clean = self.run_in(sys.executable, "bin/vibe-check", ".", "--mirrors")
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        victim = self.root / "codex" / "README.md"
        victim.write_text(victim.read_text(encoding="utf-8") + "\ntampered\n",
                          encoding="utf-8")
        seeded = self.run_in(sys.executable, "bin/vibe-check", ".", "--mirrors")
        self.assertEqual(seeded.returncode, 1, seeded.stdout + seeded.stderr)

    def test_doc_accuracy_fails_on_a_wrong_count(self):
        readme = self.root / "README.md"
        text = readme.read_text(encoding="utf-8")
        readme.write_text(
            re.sub(r"\*\*\d+ commands,", "**999 commands,", text, count=1), encoding="utf-8")
        seeded = self.run_in(sys.executable, "-m", "unittest", "tests.test_doc_accuracy")
        self.assertNotEqual(seeded.returncode, 0, seeded.stdout + seeded.stderr)

    def test_inventory_check_fails_on_a_lost_agent(self):
        clean = self.run_in(sys.executable, "tools/inventory-report.py", "--check")
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        (self.root / "agents" / "recon.md").unlink()
        seeded = self.run_in(sys.executable, "tools/inventory-report.py", "--check")
        self.assertEqual(seeded.returncode, 1, seeded.stdout + seeded.stderr)
        self.assertIn("Agents", seeded.stdout)

    def test_score_discovery_reaches_past_the_manifest_arrays(self):
        """The step-8 finding: shared partials, manifests, hooks and CLAUDE.md are scored.

        These classes cannot be demonstrated by degradation — their rubric tables are short
        enough that a stripped file still clears 80 — so coverage is asserted directly on the
        discovered record set, which is the claim that actually matters.
        """
        report = json.loads(self.run_in(
            sys.executable, "tools/release-score.py", "--threshold", "80", "--json").stdout)
        self.assertGreaterEqual(report["artifacts"], 70)
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rs", self.root / "tools" / "release-score.py")
        rs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rs)
        discovered = {rel: kind for kind, rel in rs.discover(self.root)}
        for rel, kind in ((".claude-plugin/plugin.json", "manifest"),
                          (".claude-plugin/marketplace.json", "manifest"),
                          ("commands/shared/fallback.md", "shared-partial"),
                          ("hooks/hooks.json", "settings"),
                          ("CLAUDE.md", "claude-md")):
            with self.subTest(artifact=rel):
                self.assertIn(rel, discovered, f"{rel} is not discovered")
                self.assertEqual(discovered[rel], kind,
                                 f"{rel} scored under the wrong rubric")

    def test_score_fails_closed_on_malformed_engine_output(self):
        """An engine that cannot be parsed must not read as a pass."""
        engine = self.root / "scripts" / "score_engine.py"
        engine.write_text("import sys\nsys.stdout.write('not json')\n", encoding="utf-8")
        seeded = self.run_in(sys.executable, "tools/release-score.py", "--threshold", "80")
        self.assertNotEqual(seeded.returncode, 0, seeded.stdout + seeded.stderr)

    def test_inventory_fails_on_an_unclassified_new_skill(self):
        """A skill in neither declared set is a reviewed claim owed, not a silent count."""
        new = self.root / "skills" / "brand-new-thing"
        new.mkdir()
        (new / "SKILL.md").write_text("---\nname: brand-new-thing\ndescription: x\n---\n\n# x\n",
                                      encoding="utf-8")
        manifest = self.root / ".claude-plugin" / "plugin.json"
        data = json.loads(manifest.read_text())
        data["skills"].append("./skills/brand-new-thing")
        manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        seeded = self.run_in(sys.executable, "tools/inventory-report.py", "--check")
        self.assertEqual(seeded.returncode, 1, seeded.stdout + seeded.stderr)
        self.assertIn("Workflow skills", seeded.stdout)

    def test_write_discipline_fails_on_a_seeded_mutator(self):
        """The acceptance's named case, planted in a TOP-LEVEL shipped module."""
        victim = self.root / "scripts" / "codex-runner.mjs"
        victim.write_text('import { writeFile } from "node:fs/promises";\n'
                          + victim.read_text(encoding="utf-8")
                          + '\nawait writeFile("seed", "x");\n', encoding="utf-8")
        # The copy is not a git repo, so the corpus is enumerated the same way the
        # workflow's git-tracked glob covers it: top-level AND nested scripts/**.mjs.
        files = sorted(p.relative_to(self.root).as_posix()
                       for p in (self.root / "scripts").rglob("*.mjs"))
        self.assertGreaterEqual(len(files), 15, "module discovery went vacuous")
        seeded = self.run_in("node", "tests/node/no-raw-fs-writes.mjs", *files)
        self.assertEqual(seeded.returncode, 1, seeded.stdout + seeded.stderr)
        self.assertIn("scripts/codex-runner.mjs", seeded.stdout)


class WorkflowContract(unittest.TestCase):
    """The workflow must actually run the commands the seeded cases exercised."""

    def setUp(self):
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_all_five_steps_are_declared(self):
        for name in ("score (Strict 80)", "test — spec-corpus contract",
                     "mirrors", "doc accuracy and §5.0 inventory",
                     "write discipline (Node)"):
            self.assertIn(f"name: {name}", self.text, name)

    def test_each_step_runs_the_checked_command(self):
        for command in ("python3 tools/release-score.py --threshold 80",
                        "python3 -m unittest tests.test_vibe_test_specs",
                        "bin/vibe-check . --mirrors",
                        "python3 -m unittest tests.test_doc_accuracy",
                        "python3 tools/inventory-report.py --check",
                        "node tests/node/no-raw-fs-writes.mjs"):
            self.assertIn(command, self.text, command)

    def test_the_gate_is_observable_on_pull_requests(self):
        """A release-branch-only trigger could not be demonstrated before merging."""
        self.assertIn("pull_request:", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn('branches: ["release/**"]', self.text)

    def test_paths_filter_covers_every_judged_input(self):
        """A PR touching a gate input must not bypass the gate (the step-8 finding)."""
        for path in ('"auditor/**"', '"docs/disposition.yaml"', '"schemas/**"',
                     '"templates/**"', '"PRIVACY.md"', '".vibe-suite.md"',
                     '".mcp.json"', '".lsp.json"', '"settings.json"'):
            self.assertIn(path, self.text, path)

    def test_module_discovery_is_anti_vacuous(self):
        self.assertIn("would pass vacuously", self.text)
        self.assertIn("scripts/*.mjs", self.text)

    def test_the_judgment_lane_is_disclosed_not_claimed(self):
        self.assertIn("no Claude session", self.text)
        self.assertIn("DETERMINISTIC", self.text)


if __name__ == "__main__":
    unittest.main()
