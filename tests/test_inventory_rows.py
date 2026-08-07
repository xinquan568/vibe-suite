#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""T3 (E8.4 / vibe-61) — the D-B re-partition of the two `bin/` inventory rows.

`tools/inventory-report.py`'s "Python bin tools (shipped subset)" row is EXACT 3 and counts
*every* file in `bin/` bar `README.md`, so five site builders take it to 8 and it fails. D-B
re-partitions the pair without relaxing anything:

  * shipped subset  — EXACT 3, counting files **not** matching `vibe-build-*`;
  * site builders   — graduates `pending-S8 → EXACT 5`, counting files matching
    `vibe-build-*` **and** asserting the exact expected filename SET, because five wrongly
    named files would satisfy a bare count.

Both counters are **file-only**: a directory named `vibe-build-x` is not a builder. The two
targets still sum to 8, so a stray non-builder addition to `bin/` still reddens the first row.
"""

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT = REPO_ROOT / "tools" / "inventory-report.py"

SHIPPED_ROW = "Python bin tools (shipped subset)"
BUILDERS_ROW = "Python bin tools (site builders)"

#: The three shipped non-builder executables.
SHIPPED = ("vibe-check", "vibe-report", "vibe-badge")

#: The five site builders of F10.3 — the exact expected filename set (D-B).
EXPECTED_BUILDERS = {
    "vibe-build-reference-md",
    "vibe-build-vocab-data",
    "vibe-build-site-report-pages",
    "vibe-build-case-studies-index",
    "vibe-build-docs",
}


def load_report():
    spec = importlib.util.spec_from_file_location("inventory_report", REPORT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = load_report()


def row(label):
    for entry in MOD.ROWS:
        if entry[0] == label:
            return entry
    raise AssertionError(f"tools/inventory-report.py has no row {label!r}")


class RowBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="inventory-rows-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "bin").mkdir()

    def seed_files(self, *names):
        for name in names:
            (self.tmp / "bin" / name).write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    def seed_dir(self, name):
        (self.tmp / "bin" / name).mkdir()

    def count(self, label):
        return row(label)[3](self.tmp)

    def ok(self, label):
        """The checker's own verdict for one row against the synthetic bin/ tree."""
        _, target, rule, counter = row(label)
        try:
            actual, err = counter(self.tmp), None
        except (OSError, ValueError, KeyError) as exc:
            actual, err = None, str(exc)
        for _label, verdict, _note in MOD.verdicts([(label, target, rule, actual, err)]):
            return verdict
        raise AssertionError("verdicts() yielded nothing")


class Partition(RowBase):
    def test_targets_still_sum_to_eight(self):
        self.assertEqual(row(SHIPPED_ROW)[1] + row(BUILDERS_ROW)[1], 8,
                         "the D-B re-partition must preserve §5.0's total of 8 bin tools")

    def test_both_rows_are_exact(self):
        self.assertEqual(row(SHIPPED_ROW)[2], MOD.EXACT)
        self.assertEqual(row(BUILDERS_ROW)[2], MOD.EXACT,
                         "the site-builders row must graduate pending-S8 -> EXACT")

    def test_expected_builder_filenames_are_declared(self):
        declared = set(getattr(MOD, "SITE_BUILDERS", ()) or ())
        self.assertEqual(declared, EXPECTED_BUILDERS,
                         "the site-builders row must assert an exact filename SET; five "
                         "wrongly-named files would satisfy a bare count")

    def test_expected_builders_are_on_disk(self):
        for name in sorted(EXPECTED_BUILDERS):
            with self.subTest(builder=name):
                self.assertTrue((REPO_ROOT / "bin" / name).is_file())


class ShippedSubsetRow(RowBase):
    def test_excludes_the_builders(self):
        self.seed_files(*SHIPPED, *sorted(EXPECTED_BUILDERS), "README.md")
        self.assertEqual(self.count(SHIPPED_ROW), 3,
                         "the shipped-subset counter must skip vibe-build-* files")

    def test_a_stray_non_builder_still_reddens_it(self):
        self.seed_files(*SHIPPED, *sorted(EXPECTED_BUILDERS), "README.md", "vibe-stray")
        self.assertEqual(self.count(SHIPPED_ROW), 4)
        self.assertFalse(self.ok(SHIPPED_ROW),
                         "a stray non-builder addition to bin/ must fail the row")

    def test_is_file_only(self):
        self.seed_files(*SHIPPED, "README.md")
        self.seed_dir("helpers")
        self.assertEqual(self.count(SHIPPED_ROW), 3,
                         "the shipped-subset counter must count files only")


class SiteBuildersRow(RowBase):
    def full(self, *extra):
        self.seed_files(*SHIPPED, "README.md", *sorted(EXPECTED_BUILDERS), *extra)

    def test_the_exact_five_pass(self):
        self.full()
        self.assertEqual(self.count(BUILDERS_ROW), 5)
        self.assertTrue(self.ok(BUILDERS_ROW))

    def test_a_directory_named_like_a_builder_does_not_count(self):
        self.full()
        self.seed_dir("vibe-build-x")
        self.assertEqual(self.count(BUILDERS_ROW), 5,
                         "a DIRECTORY named vibe-build-x is not a builder; the counter "
                         "must be file-only")
        self.assertTrue(self.ok(BUILDERS_ROW))

    def test_a_missing_name_fails(self):
        self.seed_files(*SHIPPED, "README.md",
                        *sorted(EXPECTED_BUILDERS - {"vibe-build-docs"}))
        self.assertFalse(self.ok(BUILDERS_ROW),
                         "four builders must fail the graduated EXACT 5 row")

    def test_a_replacement_name_fails(self):
        self.seed_files(*SHIPPED, "README.md",
                        *sorted(EXPECTED_BUILDERS - {"vibe-build-docs"}),
                        "vibe-build-documentation")
        self.assertFalse(self.ok(BUILDERS_ROW),
                         "five files with one wrong NAME must fail; counting alone is too "
                         "weak (D-B)")

    def test_an_extra_file_fails(self):
        self.full("vibe-build-extra")
        self.assertFalse(self.ok(BUILDERS_ROW),
                         "six vibe-build-* files must fail the EXACT 5 row")


if __name__ == "__main__":
    unittest.main()

# ---------------------------------------------------------------------------------------------
# Auditor workflow rows (E8.2a / vibe-59). Merged in from the other branch of the E8.2 rescope:
# that side created this file for the auditor rows, this side for the bin/ rows, so the two test
# sets are unioned rather than one replacing the other. §5.0's single 24-row was split into a
# pipeline row (18) and a site/release row (6); both are asserted here so the total stays guarded.
# ---------------------------------------------------------------------------------------------
PIPELINE_ROW = "Auditor pipeline workflows (E8.2)"
SITE_ROW = "Auditor site/release workflows (E8.4)"
SITE_WORKFLOWS = ("deploy-site", "self-check", "site-preview", "site-preview-cleanup",
                  "site-validate", "pre-release-quality-gate")


class AuditorRowSplit(RowBase):
    """The two auditor rows partition §5.0's 24 and neither may drift silently."""

    def seed_workflows(self, rel, *names):
        d = self.tmp / rel
        d.mkdir(parents=True, exist_ok=True)
        for n in names:
            (d / f"{n}.yml").write_text("name: x\n", encoding="utf-8")

    def test_targets_still_sum_to_24(self):
        self.assertEqual(row(PIPELINE_ROW)[1] + row(SITE_ROW)[1], 24,
                         "the split must preserve §5.0's total, or the inventory silently shrinks")

    def test_eighteen_pipeline_workflows_pass_and_seventeen_or_nineteen_fail(self):
        for n, expect_ok in ((18, True), (17, False), (19, False)):
            with self.subTest(count=n):
                d = self.tmp / "auditor" / "workflows"
                if d.exists():
                    shutil.rmtree(d)
                self.seed_workflows("auditor/workflows",
                                    *[f"auditor-wf-{i}" for i in range(n)])
                self.assertEqual(self.ok(PIPELINE_ROW), expect_ok,
                                 f"{n} auditor workflows: expected ok={expect_ok}")

    def test_every_site_workflow_name_is_required(self):
        # Counting by NAME, not by glob: a stray workflow must not stand in for a missing one.
        self.seed_workflows(".github/workflows", *SITE_WORKFLOWS[:-1], "an-unrelated-workflow")
        self.assertFalse(self.ok(SITE_ROW),
                         "a stray workflow must not substitute for a named site/release one")

    def test_all_six_site_workflow_names_pass(self):
        self.seed_workflows(".github/workflows", *SITE_WORKFLOWS)
        self.assertTrue(self.ok(SITE_ROW), "all six named site/release workflows must satisfy the row")

    def test_delete_and_move_cannot_hide_a_missing_workflow(self):
        """The two auditor rows must be a strict PARTITION, not merely sum to 24.

        Before this, the pipeline row counted every `auditor/**/*.yml` while the site row also
        permitted its names there — so deleting one pipeline workflow and moving one site workflow
        into `auditor/workflows/` left both rows green with only 23 unique files. The site name is
        now excluded from the pipeline count, so the shortfall surfaces.
        """
        wf = self.tmp / "auditor" / "workflows"
        wf.mkdir(parents=True, exist_ok=True)
        for i in range(17):                                  # one pipeline workflow deleted
            (wf / f"auditor-wf-{i}.yml").write_text("x", encoding="utf-8")
        (wf / "deploy-site.yml").write_text("x", encoding="utf-8")   # a site workflow moved in
        gh = self.tmp / ".github" / "workflows"
        gh.mkdir(parents=True, exist_ok=True)
        for n in SITE_WORKFLOWS:
            if n != "deploy-site":
                (gh / f"{n}.yml").write_text("x", encoding="utf-8")
        self.assertFalse(self.ok(PIPELINE_ROW),
                         "a site workflow moved into auditor/workflows/ must not substitute for a "
                         "deleted pipeline workflow")
