#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""AC-1 — `tools/coverage-check.py` and `docs/disposition.yaml` (E0.6 / vibe-8).

AC-1 says "removing any row fails CI". That is quantified over every row, so the evidence has to be
too: `test_removing_any_row_fails` deletes **each of the 76 rows in turn** from a passing baseline
and requires a non-zero exit every time. A single hand-picked deletion would prove one row
load-bearing and say nothing about the other 75.

Everything runs the real CLI as a subprocess with the arguments the CI job uses. Testing the helper
functions would leave a broken entry point — or a broken CI invocation — perfectly green.

The row inventory in the checker is a constant rather than something read from the file under test.
That is what makes a `D` row's deletion detectable: a `D` row claims no allowlisted path, so pure
coverage cannot notice it going missing. AC-1 calls this out — "disk-driven, not self-referential".
"""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECK = REPO_ROOT / "tools" / "coverage-check.py"
GEN = REPO_ROOT / "tools" / "gen-source-manifest.py"
DISPOSITION = REPO_ROOT / "docs" / "disposition.yaml"
MANIFESTS = REPO_ROOT / "tests" / "source-manifests"
PINNED_TREES = REPO_ROOT.parent.parent.parent.parent / "codes"


def _load():
    spec = importlib.util.spec_from_file_location("coverage_check", CHECK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cc = _load()


class CLICase(unittest.TestCase):
    """Every assertion goes through the command line, as CI does."""

    def run_check(self, root=None, disposition=None, manifests=None):
        return subprocess.run(
            [sys.executable, str(CHECK),
             "--disposition", str(disposition or DISPOSITION),
             "--manifests", str(manifests or MANIFESTS),
             "--root", str(root or REPO_ROOT)],
            capture_output=True, text=True)

    def sandbox(self):
        """A copy of the real artifacts, so a mutation is isolated."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        shutil.copytree(MANIFESTS, tmp / "manifests")
        shutil.copy(DISPOSITION, tmp / "disposition.yaml")
        return tmp


class TestBaseline(CLICase):

    def test_the_shipped_artifacts_pass(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("300 source artifacts", result.stdout)
        self.assertIn("75 disposition rows", result.stdout)

    def test_every_tree_contributes(self):
        universe, _ = cc.build_universe(MANIFESTS)
        for tree in ("cc-suite", "grill-for-claude", "nlpm", "workspace"):
            with self.subTest(tree=tree):
                self.assertGreater(len(universe[tree]["allowlisted"]), 0)


class TestAcceptanceCriterion(CLICase):
    """AC-1, quantified over every row."""

    def test_removing_any_row_fails(self):
        tmp = self.sandbox()
        text = (tmp / "disposition.yaml").read_text(encoding="utf-8")
        rows = re.findall(r"^  - row: (\S+)$", text, re.M)
        self.assertEqual(len(rows), 75, "the map must encode all 75 §6 rows")

        blocks, current = [], None
        for line in text.splitlines(keepends=True):
            if line.startswith("  - row: "):
                current = [line]; blocks.append(current)
            elif current is not None and line.startswith("    "):
                current.append(line)
            else:
                current = None
        self.assertEqual(len(blocks), 75)

        for row, block in zip(rows, blocks):
            with self.subTest(row=row):
                mutated = text.replace("".join(block), "", 1)
                target = tmp / f"d-{row.replace(':', '-')}.yaml"
                target.write_text(mutated, encoding="utf-8")
                result = self.run_check(disposition=target, manifests=tmp / "manifests")
                self.assertNotEqual(result.returncode, 0,
                                    f"removing row {row} left the check passing")

    def test_a_data_row_removal_is_caught_by_the_inventory_not_by_coverage(self):
        """A D row claims no allowlisted path, so coverage alone cannot see it go. The constant
        inventory is what catches it — this is the self-referential gap AC-1 names."""
        tmp = self.sandbox()
        text = (tmp / "disposition.yaml").read_text(encoding="utf-8")
        match = re.search(r"^  - row: (nlpm:\d+)\n(?:    .*\n)*?    disposition: D\n(?:    .*\n)*",
                          text, re.M)
        self.assertIsNotNone(match, "the map must contain a D row")
        target = tmp / "no-d.yaml"
        target.write_text(text.replace(match.group(0), "", 1), encoding="utf-8")
        result = self.run_check(disposition=target, manifests=tmp / "manifests")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("§6 rows absent from the map", result.stderr)


# --------------------------------------------------------------------------- the semantic oracle
#: §6's disposition and target for a sample of rows, transcribed BY HAND from the proposal rather
#: than read from the artifact under test. Coverage proves the map is *complete*; nothing else
#: proves it is *correct*, and a green run told me nothing about a batch of wrong-but-well-formed
#: targets that review caught. Every entry below was a defect at some point in this issue.
SIX_ORACLE = {
    # grill-for-claude — every one of these was wrong in the first draft
    "grill-for-claude:01": ("K", ["F3.1"]),              # `roast` command — was M
    "grill-for-claude:02": ("K", ["F3.2", "F3.3", "F3.4", "F3.5", "F3.6", "F3.7"]),
    "grill-for-claude:03": ("M", ["F9.1", "F9.2"]),      # grill-core skill — was K/F3.2
    "grill-for-claude:04": ("G", ["F9.6"]),
    "grill-for-claude:05": ("M", ["F4.4", "F1.2"]),      # validate-plugin.sh
    # nlpm
    "nlpm:01": ("K", ["F4.1"]),                          # ls + scanner
    "nlpm:02": ("K", ["F4.2"]),                          # score + scorer
    "nlpm:03": ("M", ["F3.8"]),                          # `fix` — was K/F4.3
    "nlpm:04": ("K", ["F4.3"]),                          # check + checker
    "nlpm:06": ("K", ["F4.5"]),                          # test + tester + .nlpm-test specs
    "nlpm:14": ("M", ["F1.1"]),                          # init
    "nlpm:25": ("D", []),                                # accumulated ops data
    # cc-suite
    "cc-suite:10": ("R", ["F3.1"]),                      # `audit` retired with replacement
    "cc-suite:14": ("R", ["F6.1"]),                      # `review-plan` retired with replacement
    # workspace — three §6 homes are paths, not function IDs
    "workspace:01": ("K", ["F6.1"]),                     # refine-proposal/SKILL.md
    "workspace:05": ("K", ["F6.2"]),                     # issue2pr/SKILL.md
    "workspace:09": ("K", ["examples/profiles/roamex.md"]),
    "workspace:10": ("K", ["templates/pr-body.md"]),
    "workspace:12": ("M", ["examples/profiles/roamex.md"]),
    "workspace:13": ("K", ["F8.5"]),
}


class TestDispositionsMatchSectionSix(CLICase):
    """Coverage proves completeness. This proves the map says what §6 says."""

    def parsed(self):
        text = DISPOSITION.read_text(encoding="utf-8")
        _, mappings = cc.parse_disposition(text)
        return {m["row"]: m for m in mappings}

    def test_sampled_rows_carry_sixs_disposition_and_target(self):
        rows = self.parsed()
        for row, (disposition, target) in SIX_ORACLE.items():
            with self.subTest(row=row):
                self.assertIn(row, rows)
                self.assertEqual(rows[row]["disposition"], disposition)
                actual = rows[row].get("target", [])
                actual = actual if isinstance(actual, list) else [actual]
                self.assertEqual(actual, target)

    def test_a_permuted_disposition_is_caught_by_the_oracle(self):
        """The check itself accepts any legal disposition, so this fixture is the only thing
        standing between a permuted map and a green run."""
        rows = self.parsed()
        self.assertNotEqual(rows["nlpm:03"]["disposition"], "K",
                            "nlpm `fix` is M into F3.8, not K — the first draft had this wrong")
        self.assertNotEqual(rows["grill-for-claude:03"]["disposition"], "K",
                            "grill-core is merged into the suite contract, not kept")

    def test_every_row_id_in_the_oracle_exists(self):
        rows = self.parsed()
        self.assertEqual(sorted(set(SIX_ORACLE) - set(rows)), [])

    def test_retired_rows_name_their_replacement(self):
        """§6's legend: "R retired with replacement noted"."""
        for row, mapping in self.parsed().items():
            if mapping.get("disposition") == "R":
                with self.subTest(row=row):
                    self.assertTrue(mapping.get("target"))


class TestCoverageIsBidirectional(CLICase):

    def _mutate(self, replace, with_):
        tmp = self.sandbox()
        text = (tmp / "disposition.yaml").read_text(encoding="utf-8")
        self.assertIn(replace, text)
        target = tmp / "m.yaml"
        target.write_text(text.replace(replace, with_, 1), encoding="utf-8")
        return self.run_check(disposition=target, manifests=tmp / "manifests")

    def test_a_path_absent_from_the_manifest_fails(self):
        result = self._mutate("    paths: [commands/init.md]",
                              "    paths: [commands/init.md, commands/nonesuch.md]")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not in the manifest", result.stderr)

    def test_claiming_an_excluded_path_fails(self):
        result = self._mutate("    paths: [commands/init.md]",
                              "    paths: [commands/init.md, case-studies/x.md]")
        self.assertNotEqual(result.returncode, 0)

    def test_claiming_one_path_twice_fails(self):
        result = self._mutate("    paths: [commands/update.md]",
                              "    paths: [commands/update.md, commands/init.md]")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already claimed", result.stderr)

    def test_an_unclaimed_allowlisted_path_fails_and_is_named(self):
        result = self._mutate("    paths: [commands/update.md]", "    paths: []")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commands/update.md", result.stderr)

    def test_a_corpus_root_matching_nothing_fails(self):
        result = self._mutate("auditor/reports, auditor/exemplars", "nonesuch-corpus, auditor/exemplars")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matches nothing", result.stderr)


class TestSchema(CLICase):

    def _mutate(self, replace, with_):
        tmp = self.sandbox()
        text = (tmp / "disposition.yaml").read_text(encoding="utf-8")
        self.assertIn(replace, text)
        target = tmp / "m.yaml"
        target.write_text(text.replace(replace, with_, 1), encoding="utf-8")
        return self.run_check(disposition=target, manifests=tmp / "manifests")

    def test_an_unknown_disposition_fails(self):
        self.assertNotEqual(self._mutate("    disposition: K\n", "    disposition: X\n").returncode, 0)

    def test_a_wellformed_but_nonexistent_target_fails(self):
        result = self._mutate("    target: F1.7\n", "    target: F99.9\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not one of the", result.stderr)

    def test_a_malformed_target_fails(self):
        self.assertNotEqual(self._mutate("    target: F1.7\n", "    target: nonsense\n").returncode, 0)

    def test_a_k_row_without_a_target_fails(self):
        result = self._mutate("    disposition: K\n    target: F1.7\n", "    disposition: K\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a 'target'", result.stderr)

    def test_a_pin_that_is_not_the_constant_fails(self):
        tmp = self.sandbox()
        path = tmp / "manifests" / "cc-suite.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["commit"] = "0" * 40
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = self.run_check(manifests=tmp / "manifests")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("re-pinning must be a change", result.stderr)

    def test_an_unsorted_manifest_fails(self):
        tmp = self.sandbox()
        path = tmp / "manifests" / "cc-suite.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["files"] = list(reversed(data["files"]))
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result = self.run_check(manifests=tmp / "manifests")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sorted", result.stderr)


class TestGlobSemantics(unittest.TestCase):
    """`fnmatch` cannot express these: its `*` crosses `/`."""

    CASES = [
        ("scripts/x.sh", "scripts/**/*", True),
        ("scripts/lib/y.mjs", "scripts/**/*", True),
        ("scripts/lib/deep/z.mjs", "scripts/**/*", True),
        ("scriptsX/x.sh", "scripts/**/*", False),
        ("skills/grill-core/SKILL.md", "skills/**/SKILL.md", True),
        ("skills/cc-suite/agent-design/SKILL.md", "skills/**/SKILL.md", True),
        ("codex/skills/grill-core/SKILL.md", "skills/**/SKILL.md", False),
        ("commands/a.md", "commands/**/*.md", True),
        ("commands/shared/a.md", "commands/**/*.md", True),
        ("commands/a.txt", "commands/**/*.md", False),
        ("bin/nlpm-check", "bin/*", True),
        ("bin/sub/x", "bin/*", False),
    ]

    def test_each_family_matches_direct_nested_and_near_miss(self):
        for path, pattern, expected in self.CASES:
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(cc.matches(path, pattern), expected)

    def test_codex_skills_do_not_count_toward_the_skills_expectation(self):
        universe, _ = cc.build_universe(MANIFESTS)
        for tree, expected in cc.SKILL_COUNTS.items():
            with self.subTest(tree=tree):
                counted = sum(1 for p in universe[tree]["all"]
                              if cc.matches(p, "skills/**/SKILL.md"))
                total = sum(1 for p in universe[tree]["all"] if p.endswith("SKILL.md"))
                self.assertEqual(counted, expected)
                if tree == "nlpm":
                    self.assertGreater(total, counted, "nlpm mirrors its skills under codex/")


class TestExclusions(CLICase):
    """One case per predicate. A predicate with no test can be deleted while the suite is green."""

    def _rejects(self, path):
        universe, _ = cc.build_universe(MANIFESTS)
        self.assertTrue(cc.is_excluded(path), f"{path} should be excluded")

    def test_directory_components(self):
        for name in cc.EXCLUDED_DIRS:
            with self.subTest(directory=name):
                self._rejects(f"a/{name}/b.md")

    def test_every_os_junk_basename(self):
        for name in cc.OS_JUNK:
            with self.subTest(basename=name):
                self._rejects(f"commands/{name}")
        self._rejects("commands/._resource")

    def test_every_generated_report_artifact(self):
        self._rejects("auditor/reports/x.json")
        self._rejects("nlpm-badge.json")

    def test_every_row9_corpus_family(self):
        for path in ("auditor/reports/a.json", "auditor/exemplars/a.md", "auditor/audits/a.md",
                     "auditor/logs/events.jsonl", "auditor/findings.jsonl",
                     "auditor/disagreements.jsonl", "auditor/vocab-advisories.jsonl",
                     "case-studies/a.md"):
            with self.subTest(path=path):
                self._rejects(path)

    def test_auditor_scripts_are_not_excluded(self):
        """AC-1 allowlists `auditor/scripts/*` explicitly. Excluding all of `auditor/` — which an
        earlier draft did — would have dropped 32 real script files."""
        self.assertFalse(cc.is_excluded("auditor/scripts/run.sh"))
        self.assertTrue(cc.is_allowlisted("auditor/scripts/run.sh"))

    def test_auditor_reports_stays_excluded_when_either_route_is_removed(self):
        """It is excluded as a generated report and as row-9 ops data. Neither alone may un-exclude
        it; both together are what make it required to be absent."""
        original_reports, original_row9 = cc.GENERATED_REPORTS, cc.ROW9_OPS_DATA
        try:
            cc.GENERATED_REPORTS = tuple(p for p in original_reports if "auditor" not in p)
            self.assertTrue(cc.is_excluded("auditor/reports/x.json"))
            cc.GENERATED_REPORTS = original_reports
            cc.ROW9_OPS_DATA = tuple(p for p in original_row9 if not p.startswith("auditor/reports"))
            self.assertTrue(cc.is_excluded("auditor/reports/x.json"))
        finally:
            cc.GENERATED_REPORTS, cc.ROW9_OPS_DATA = original_reports, original_row9


class TestCounts(CLICase):

    def test_the_enumerated_counts_hold(self):
        universe, _ = cc.build_universe(MANIFESTS)
        self.assertEqual(cc.check_counts(universe), [])

    def test_perturbing_a_skill_count_fails(self):
        universe, _ = cc.build_universe(MANIFESTS)
        original = dict(cc.SKILL_COUNTS)
        try:
            cc.SKILL_COUNTS["cc-suite"] = 12
            self.assertTrue(cc.check_counts(universe))
        finally:
            cc.SKILL_COUNTS.clear(); cc.SKILL_COUNTS.update(original)

    def test_the_workspace_resource_count_is_asserted_and_reconciled(self):
        """§5 records 12; the live trees hold 14. The difference is `profiles/vibe-suite.md` and
        `templates/vibe-suite-pr-body.md`, added to issue2pr for this project after the proposal was
        written. Asserted at 14 rather than waived, because AC-1 wants a count that fails loudly."""
        universe, _ = cc.build_universe(MANIFESTS)
        resources = [p for p in universe["workspace"]["allowlisted"] if not p.endswith("/SKILL.md")]
        self.assertEqual(len(resources), 14)
        self.assertEqual(cc.WORKSPACE_RESOURCE_COUNT, 14)
        for added in ("issue2pr/profiles/vibe-suite.md",
                      "issue2pr/templates/vibe-suite-pr-body.md"):
            self.assertIn(added, resources)

    def test_function_id_inventory_is_57(self):
        self.assertEqual(len(cc.load_function_ids()), cc.FUNCTION_ID_COUNT)


class TestManifestsAreReproducible(unittest.TestCase):
    """The manifests are the only record CI has of the trees, so drift must be a reviewable diff."""

    def test_regenerating_a_pinned_manifest_reproduces_it(self):
        if not PINNED_TREES.is_dir():
            self.skipTest(f"pinned source trees not present at {PINNED_TREES}")
        for repo in cc.PINS:
            tree = PINNED_TREES / repo
            if not (tree / ".git").exists():
                self.skipTest(f"{tree} is not a checkout")
            with self.subTest(repo=repo):
                out = Path(tempfile.mkdtemp()) / f"{repo}.json"
                self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
                subprocess.run([sys.executable, str(GEN), str(tree), "--repo", repo,
                                "--out", str(out)], capture_output=True, check=True)
                self.assertEqual(out.read_text(encoding="utf-8"),
                                 (MANIFESTS / f"{repo}.json").read_text(encoding="utf-8"),
                                 f"{repo}.json is stale against its pinned commit")


if __name__ == "__main__":
    unittest.main()
