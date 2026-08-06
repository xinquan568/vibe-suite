# SPDX-License-Identifier: ISC
"""RED-first tests for the E8.2 inventory-row split (vibe-59).

tools/inventory-report.py's single ("Auditor-unit workflows", 24, pending-S8) row must become two
rows whose targets sum to 24: pipeline (18, exact, auditor/**/*.yml full glob) and site/release
(6, pending-S8, counting the five outstanding E8.4 workflow names across BOTH .github/workflows/
and auditor/workflows/, with pre-release-quality-gate excluded as delivered early by E7.4).
Seeded temp trees prove the semantics before—and after—the tool edit.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("invrep", REPO / "tools" / "inventory-report.py")
invrep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(invrep)

PIPELINE_ROW = "Auditor pipeline workflows (E8.2)"
SITE_ROW = "Auditor site/release workflows (E8.4)"
OUTSTANDING = ["deploy-site", "self-check", "site-preview", "site-preview-cleanup",
               "site-validate"]


def verdict_for(root, label):
    rows = invrep.measure(Path(root))
    for (lab, ok, note) in invrep.verdicts(rows):
        if lab == label:
            return ok, note
    raise AssertionError(f"row '{label}' not found; rows: {[r[0] for r in rows]}")


def seed(root, n_auditor_yml=18, github_extra=(), auditor_extra=()):
    (root / "auditor" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows").mkdir(parents=True)
    for i in range(n_auditor_yml):
        (root / "auditor" / "workflows" / f"auditor-wf-{i}.yml").write_text("name: x\n")
    for name in github_extra:
        (root / ".github" / "workflows" / f"{name}.yml").write_text("name: x\n")
    for name in auditor_extra:
        (root / "auditor" / "workflows" / f"{name}.yml").write_text("name: x\n")


class TestRowSplit(unittest.TestCase):
    def test_targets_sum_to_24(self):
        rows = {r[0]: r[1] for r in invrep.ROWS}
        self.assertIn(PIPELINE_ROW, rows)
        self.assertIn(SITE_ROW, rows)
        self.assertEqual(rows[PIPELINE_ROW] + rows[SITE_ROW], 24)

    def test_18_files_pass_17_and_19_fail(self):
        for n, expect_ok in ((18, True), (17, False), (19, False)):
            with tempfile.TemporaryDirectory() as td:
                seed(Path(td), n_auditor_yml=n)
                ok, note = verdict_for(td, PIPELINE_ROW)
                with self.subTest(n=n):
                    self.assertEqual(ok, expect_ok, note)

    def test_site_row_green_today_red_on_deploy_site_either_location(self):
        with tempfile.TemporaryDirectory() as td:
            seed(Path(td))
            ok, _ = verdict_for(td, SITE_ROW)
            self.assertTrue(ok, "site row must be green with zero outstanding names")
        with tempfile.TemporaryDirectory() as td:
            seed(Path(td), github_extra=["deploy-site"])
            ok, _ = verdict_for(td, SITE_ROW)
            self.assertFalse(ok, "deploy-site under .github/workflows/ must self-expire the row")
        with tempfile.TemporaryDirectory() as td:
            seed(Path(td), auditor_extra=["deploy-site"])
            ok, _ = verdict_for(td, SITE_ROW)
            self.assertFalse(ok, "deploy-site under auditor/workflows/ must self-expire the row")

    def test_pre_release_is_excluded_as_early_delivered(self):
        with tempfile.TemporaryDirectory() as td:
            seed(Path(td), github_extra=["pre-release-quality-gate"])
            ok, _ = verdict_for(td, SITE_ROW)
            self.assertTrue(ok, "pre-release-quality-gate predates S8 (E7.4) and must not count")

    def test_helper_scripts_row_still_requires_zero_python(self):
        with tempfile.TemporaryDirectory() as td:
            seed(Path(td))
            ok, _ = verdict_for(td, "Auditor helper scripts")
            self.assertTrue(ok)
            (Path(td) / "auditor" / "sneaky.py").write_text("x = 1\n")
            ok2, _ = verdict_for(td, "Auditor helper scripts")
            self.assertFalse(ok2)


if __name__ == "__main__":
    unittest.main()
