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
        self.assertIn("76 disposition rows", result.stdout)

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
        self.assertEqual(len(rows), 76, "§6's 75 rows plus cc-suite:30, the recorded divergence")

        blocks, current = [], None
        for line in text.splitlines(keepends=True):
            if line.startswith("  - row: "):
                current = [line]; blocks.append(current)
            elif current is not None and line.startswith("    "):
                current.append(line)
            else:
                current = None
        self.assertEqual(len(blocks), 76)

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
PROPOSAL = REPO_ROOT / "docs/discussion/2026-07-18-vibe-suite-merge/iter-1/round-1/plan-i1-r1.md"

#: §6's subsections, in the order the map numbers them.
SUBSECTIONS = (("cc-suite", "### cc-suite"), ("grill-for-claude", "### grill-for-claude"),
               ("nlpm", "### nlpm"), ("workspace", "### Workspace skills"))
#: cc-suite:30 has no §6 row — it is the recorded divergence (see the checker's ROW_INVENTORY note).
DIVERGENCES = {"cc-suite:30"}


def expand_ids(cell):
    """Function IDs named by a §6 home cell, expanding the ranges §6 writes.

    grill's agent row reads "F3.2-F3.7", meaning six functions. A plain findall sees two, so a map
    that correctly lists all six would look like it had invented four.
    """
    ids = set(re.findall(r"F[0-9]+\.[0-9]+", cell))
    for match in re.finditer(r"F([0-9]+)\.([0-9]+)\s*[-\u2013\u2014]\s*F?([0-9]+)?\.?([0-9]+)", cell):
        group, start = int(match.group(1)), int(match.group(2))
        end = int(match.group(4))
        if match.group(3) and int(match.group(3)) != group:
            continue
        ids.update(f"F{group}.{n}" for n in range(start, end + 1))
    return frozenset(ids)


def read_six():
    """Parse §6's tables out of the shipped proposal.

    The oracle is §6 itself, not a hand-copied sample of it. Three rounds of review found
    mistranscriptions in this map, and a 20-row sample missed them for the same reason every sample
    does: the rows I checked were right and the rows I did not check were wrong. Reading the source
    removes the sampling step entirely.
    """
    text = PROPOSAL.read_text(encoding="utf-8")
    bounds = [text.index(marker) for _, marker in SUBSECTIONS] + [text.index("\n## 7")]
    out = {}
    for index, (tree, _) in enumerate(SUBSECTIONS):
        body = text[bounds[index]:bounds[index + 1]]
        number = 0
        for line in body.splitlines():
            if not line.startswith("|") or line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 3 or cells[1] in ("Disp.",):
                continue
            number += 1
            out[f"{tree}:{number:02d}"] = (cells[1], expand_ids(cells[2]))
    return out


class TestDispositionsMatchSectionSix(CLICase):
    """Coverage proves the map is complete. This proves it says what §6 says."""

    def setUp(self):
        self.six = read_six()
        _, mappings = cc.parse_disposition(DISPOSITION.read_text(encoding="utf-8"))
        self.rows = {m["row"]: m for m in mappings}

    def test_the_proposal_yields_seventy_five_rows(self):
        self.assertEqual(len(self.six), 75)
        for tree, expected in (("cc-suite", 29), ("grill-for-claude", 7), ("nlpm", 25),
                               ("workspace", 14)):
            with self.subTest(tree=tree):
                self.assertEqual(sum(1 for k in self.six if k.startswith(tree + ":")), expected)

    def test_every_row_carries_sixs_disposition(self):
        for row, (disposition, _) in self.six.items():
            with self.subTest(row=row):
                self.assertEqual(self.rows[row]["disposition"], disposition,
                                 f"{row}: §6 says {disposition}")

    def test_every_function_target_is_one_six_names(self):
        """Where §6's home column names function IDs, the map must not invent different ones."""
        for row, (_, ids) in self.six.items():
            if not ids:
                continue
            with self.subTest(row=row):
                target = self.rows[row].get("target", [])
                mapped = frozenset(target if isinstance(target, list) else [target])
                self.assertTrue(mapped <= ids,
                                f"{row}: map has {sorted(mapped - ids)}, §6 names {sorted(ids)}")

    def test_the_only_row_without_a_six_source_is_the_recorded_divergence(self):
        self.assertEqual(set(self.rows) - set(self.six), DIVERGENCES)
        note = self.rows["cc-suite:30"].get("note", "")
        self.assertIn("DIVERGENCE", note)

    def test_retired_rows_name_their_replacement(self):
        """§6's legend: "R retired with replacement noted"."""
        for row, mapping in self.rows.items():
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
