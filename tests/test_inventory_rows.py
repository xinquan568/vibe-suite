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
PIPELINE_WORKFLOWS = MOD.PIPELINE_WORKFLOWS


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

    def test_the_declared_set_is_a_strict_partition_of_24(self):
        """Disjoint AND exhaustive — the property the row targets alone cannot express.

        Summing to 24 was never the claim worth enforcing: two rows can sum to 24 while
        describing 23 files. Intersection-empty plus union-of-24 is the real invariant, and it
        is asserted at import in the tool as well as here.
        """
        pipeline, site = set(PIPELINE_WORKFLOWS), set(SITE_WORKFLOWS)
        self.assertEqual(pipeline & site, set(), "the two auditor name sets overlap")
        self.assertEqual(len(pipeline | site), 24, "the union is not §5.0's 24")

    def test_the_name_set_is_cross_pinned_to_the_lint(self):
        """The tool and the lint must require the SAME 18 workflows.

        Two independent hand-maintained lists of the same thing drift; the repo's convention
        (MIRROR, RETIRED) is to pin such pairs with a test rather than trust discipline.
        """
        from tests import test_auditor_workflows as lint_mod
        self.assertEqual(sorted(PIPELINE_WORKFLOWS),
                         sorted(n[:-4] for n in lint_mod.EXPECTED),
                         "tools/inventory-report.py:PIPELINE_WORKFLOWS and "
                         "tests/test_auditor_workflows.py:EXPECTED disagree")

    def test_the_eighteen_named_workflows_pass_and_a_missing_one_fails(self):
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        self.assertTrue(self.ok(PIPELINE_ROW), "the declared 18 must satisfy the row")
        (self.tmp / "auditor" / "workflows" / f"{PIPELINE_WORKFLOWS[0]}.yml").unlink()
        self.assertFalse(self.ok(PIPELINE_ROW), "a deleted required workflow must redden the row")

    def test_an_unrelated_auditor_yaml_cannot_replace_a_required_one(self):
        """Attack B: delete a required workflow, add an unrelated one — count stays 18.

        The old counter measured how MANY auditor YAML files existed, so any file could stand in
        for any other. Membership of a named set is what makes substitution visible.
        """
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS[:-1],
                            "auditor-totally-unrelated")
        self.assertEqual(len(list((self.tmp / "auditor").rglob("*.yml"))), 18,
                         "the attack must keep the physical file count at 18")
        self.assertFalse(self.ok(PIPELINE_ROW),
                         "an unrelated auditor YAML must not substitute for a required workflow")

    def test_a_site_workflow_in_both_homes_is_a_duplicate_not_a_pass(self):
        """Attack C: the same site workflow in BOTH accepted homes.

        Both locations are legitimate, so the row accepted either — but it tested EXISTENCE per
        name, which silently collapsed a genuine duplicate into one satisfied name and let the
        unit carry 25 files while reporting 24.
        """
        self.seed_workflows(".github/workflows", *SITE_WORKFLOWS)
        self.seed_workflows("auditor/workflows", SITE_WORKFLOWS[0])
        self.assertFalse(self.ok(SITE_ROW),
                         "a site workflow present in both homes is a duplicate, not a pass")

    def test_workflows_parked_outside_the_workflow_home_do_not_count(self):
        """GitHub runs workflows from a workflow directory; elsewhere they are inert files.

        The census scanned all of `auditor/` and `.github/`, so a complete set filed under
        `auditor/not-workflows/` satisfied both rows while the unit had no live workflows.
        """
        self.seed_workflows("auditor/not-workflows", *PIPELINE_WORKFLOWS)
        self.assertFalse(self.ok(PIPELINE_ROW),
                         "workflows outside the workflow home are not the unit")

    def test_a_symlinked_workflow_is_not_a_real_workflow(self):
        """`is_file()` and `stat()` FOLLOW symlinks, so a link counted as a real workflow.

        A required name could therefore be satisfied by a link to any file at all — including
        one pointing outside the repository. The link itself is what has to be tested.
        """
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS[1:])
        target = self.tmp / "elsewhere.yml"
        target.write_text("name: x\n", encoding="utf-8")
        (self.tmp / "auditor" / "workflows"
         / f"{PIPELINE_WORKFLOWS[0]}.yml").symlink_to(target)
        self.assertFalse(self.ok(PIPELINE_ROW),
                         "a symlink must not satisfy a required workflow")

    def test_a_symlinked_site_workflow_is_rejected_too(self):
        self.seed_workflows(".github/workflows", *SITE_WORKFLOWS[1:])
        target = self.tmp / "elsewhere-site.yml"
        target.write_text("name: x\n", encoding="utf-8")
        (self.tmp / ".github" / "workflows"
         / f"{SITE_WORKFLOWS[0]}.yml").symlink_to(target)
        self.assertFalse(self.ok(SITE_ROW), "a symlink must not satisfy a site workflow")

    def test_an_extra_empty_file_in_the_home_reddens_the_row(self):
        """Junk has to be SEEN to be rejected.

        Empty files and directories were filtered out BEFORE anomaly detection, so an extra
        `sneaky.yml` simply vanished from the census rather than reddening anything.
        """
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        (self.tmp / "auditor" / "workflows" / "sneaky.yml").write_text("", encoding="utf-8")
        self.assertFalse(self.ok(PIPELINE_ROW), "an extra empty entry must redden the row")

    def test_an_extra_directory_in_the_home_reddens_the_row(self):
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        (self.tmp / "auditor" / "workflows" / "sneaky.yml").mkdir()
        self.assertFalse(self.ok(PIPELINE_ROW), "an extra directory must redden the row")

    def test_unrelated_workflows_in_the_github_home_are_not_this_rows_business(self):
        # Guards the other direction: ci.yml lives there legitimately.
        self.seed_workflows(".github/workflows", *SITE_WORKFLOWS, "ci")
        self.assertTrue(self.ok(SITE_ROW), "an unrelated .github workflow must not redden the row")

    def test_a_nested_duplicate_pipeline_workflow_is_caught(self):
        """Reducing paths to a SET of stems lost multiplicity.

        The same workflow in `auditor/workflows/` and `auditor/workflows/nested/` collapsed to
        one name, so the unit carried 25 files while both rows reported 24.
        """
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        self.seed_workflows("auditor/workflows/nested", PIPELINE_WORKFLOWS[0])
        self.assertFalse(self.ok(PIPELINE_ROW), "a nested duplicate must redden the row")

    def test_a_nested_duplicate_site_workflow_is_caught(self):
        # The site row checked two DIRECT paths, so a nested copy was simply unseen.
        self.seed_workflows(".github/workflows", *SITE_WORKFLOWS)
        self.seed_workflows("auditor/workflows/nested", SITE_WORKFLOWS[0])
        self.assertFalse(self.ok(SITE_ROW), "a nested duplicate site workflow must redden the row")

    def test_a_yaml_extension_duplicate_is_caught(self):
        # GitHub runs .yaml as readily as .yml, so a .yaml twin is a live duplicate.
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        (self.tmp / "auditor" / "workflows"
         / f"{PIPELINE_WORKFLOWS[0]}.yaml").write_text("name: x\n", encoding="utf-8")
        self.assertFalse(self.ok(PIPELINE_ROW), "a .yaml twin of a .yml workflow is a duplicate")

    def test_a_workflow_may_legitimately_use_the_yaml_extension(self):
        """Guards the other direction: .yaml alone is valid and must not be counted missing."""
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS[1:])
        (self.tmp / "auditor" / "workflows"
         / f"{PIPELINE_WORKFLOWS[0]}.yaml").write_text("name: x\n", encoding="utf-8")
        self.assertTrue(self.ok(PIPELINE_ROW), "a .yaml workflow is a workflow")

    def test_a_directory_named_like_a_workflow_does_not_count(self):
        """`rglob("*.yml")` matches DIRECTORIES, so `auditor-audit.yml/` read as present.

        The bin rows already guarded this (test_a_directory_named_like_a_builder_does_not_count);
        the auditor rows did not, so the same trick worked one directory over.
        """
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        target = self.tmp / "auditor" / "workflows" / f"{PIPELINE_WORKFLOWS[0]}.yml"
        target.unlink()
        target.mkdir()
        self.assertFalse(self.ok(PIPELINE_ROW),
                         "a directory named like a workflow is not a workflow")

    def test_an_empty_file_is_not_a_workflow(self):
        # Presence is not content: a zero-byte file satisfied the row while being no workflow.
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        (self.tmp / "auditor" / "workflows" / f"{PIPELINE_WORKFLOWS[0]}.yml").write_text(
            "", encoding="utf-8")
        self.assertFalse(self.ok(PIPELINE_ROW), "an empty file must not satisfy the row")

    def test_an_empty_site_workflow_is_not_a_workflow(self):
        self.seed_workflows(".github/workflows", *SITE_WORKFLOWS)
        (self.tmp / ".github" / "workflows" / f"{SITE_WORKFLOWS[0]}.yml").write_text(
            "", encoding="utf-8")
        self.assertFalse(self.ok(SITE_ROW), "an empty file must not satisfy the site row")

    def test_a_stray_yaml_in_a_nested_auditor_dir_is_caught(self):
        # The pipeline scan is recursive, so a nested stray must not hide from it.
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS)
        self.seed_workflows("auditor/workflows/nested", "sneaky")
        self.assertFalse(self.ok(PIPELINE_ROW), "a nested stray auditor YAML must redden the row")

    def test_delete_and_move_cannot_hide_a_missing_workflow(self):
        """The two auditor rows must be a strict PARTITION, not merely sum to 24.

        Before this, the pipeline row counted every `auditor/**/*.yml` while the site row also
        permitted its names there — so deleting one pipeline workflow and moving one site workflow
        into `auditor/workflows/` left both rows green with only 23 unique files. The site name is
        now excluded from the pipeline count, so the shortfall surfaces.
        """
        # one required pipeline workflow deleted, one site workflow moved in to replace it
        self.seed_workflows("auditor/workflows", *PIPELINE_WORKFLOWS[:-1], "deploy-site")
        gh = self.tmp / ".github" / "workflows"
        gh.mkdir(parents=True, exist_ok=True)
        for n in SITE_WORKFLOWS:
            if n != "deploy-site":
                (gh / f"{n}.yml").write_text("x", encoding="utf-8")
        self.assertFalse(self.ok(PIPELINE_ROW),
                         "a site workflow moved into auditor/workflows/ must not substitute for a "
                         "deleted pipeline workflow")
