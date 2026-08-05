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
import os
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

#: vibe-132: the pinned trees' location is explicit-first. The old four-parent constant
#: resolved only from run worktrees — in CI it pointed above the runner workspace and from
#: the main checkout at a directory that does not exist, so the reproducibility check
#: green-skipped everywhere it mattered.
PINNED_TREES_ENV = "VIBE_SUITE_PINNED_TREES"
_CLONE_NAMES = ("cc-suite", "grill-for-claude", "nlpm")


def resolve_pinned_trees(env=None, repo_root=REPO_ROOT):
    """The pinned-tree root. An explicit VIBE_SUITE_PINNED_TREES always wins and is
    returned unchecked — with the variable set, absence is the caller's *failure*, never
    a skip (CI sets it, so CI can never green-skip). Unset, the documented layout
    defaults apply in order: the main checkout's sibling codes/ (repo_root.parent), then
    the run-worktree four-parent path; the first existing directory containing at least
    one known clone wins. None means no candidate resolved — the local-skip case."""
    env = os.environ if env is None else env
    explicit = env.get(PINNED_TREES_ENV)
    if explicit:
        return Path(explicit)
    for cand in (repo_root.parent,
                 repo_root.parent.parent.parent.parent / "codes"):
        if cand.is_dir() and any((cand / name).is_dir() for name in _CLONE_NAMES):
            return cand
    return None


def verify_manifest(tree, repo, pin, manifest_path):
    """(verdict, message) — vibe-132's blame split. 'checkout' when the clone cannot
    serve the pinned commit (the object is what regeneration needs; HEAD position is
    irrelevant), 'manifest' when read-only regeneration at the pin differs from the
    shipped bytes, 'ok' otherwise."""
    probe = subprocess.run(["git", "-C", str(tree), "cat-file", "-e", f"{pin}^{{commit}}"],
                           capture_output=True)
    if probe.returncode != 0:
        return ("checkout",
                f"checkout at {tree} cannot serve pinned commit {pin}; "
                f"run: git -C {tree} fetch origin {pin}")
    out = Path(tempfile.mkdtemp()) / f"{repo}.json"
    try:
        subprocess.run([sys.executable, str(GEN), str(tree), "--repo", repo,
                        "--ref", pin, "--out", str(out)], capture_output=True, check=True)
        regenerated = out.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(out.parent, ignore_errors=True)
    if regenerated != manifest_path.read_text(encoding="utf-8"):
        return ("manifest",
                f"{repo}.json is stale against pinned {pin}; regenerate with "
                f"gen-source-manifest.py --ref {pin}")
    return ("ok", "")


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
        self.assertIn("303 source artifacts", result.stdout)
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


def required_ids(home_cell):
    """The row's actual homes, as §6 states them.

    §6's home column opens with the destination and then qualifies it in prose. "F2.5, F9.1" names
    two homes and both are required — that is the case a subset rule let slip. "F6.1 reference
    (incl. ...); cross-linked from F6.3" names one home and mentions another in passing. When the
    cell does not open with IDs at all ("one truthful doc set; ... (F10.3)"), every ID it names is
    taken as required, since there is no leading list to prefer.
    """
    lead = re.match(r"\s*((?:F[0-9]+\.[0-9]+)"
                    r"(?:\s*[,/+\u2013\u2014-]\s*F?[0-9]*\.?[0-9]+)*)", home_cell)
    if lead:
        return expand_ids(lead.group(1))
    return expand_ids(home_cell)


def primary_id(home_cell):
    """The first function ID in §6's home cell — the row's primary destination."""
    match = re.search(r"F[0-9]+\.[0-9]+", home_cell)
    return match.group(0) if match else None


def universe_for(tree):
    """Every path the tree actually has, so §6 names that do not exist there are not read as
    omissions from the row."""
    universe, _ = cc.build_universe(MANIFESTS)
    return universe[tree]["all"]


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
            out[f"{tree}:{number:02d}"] = (cells[1], expand_ids(cells[2]), cells[0], cells[2])
    return out


class TestDispositionsMatchSectionSix(CLICase):
    """Coverage proves the map is complete. This proves it says what §6 says."""

    def setUp(self):
        self.six = read_six()
        self.six_raw = {k: v[3] for k, v in self.six.items()}
        _, mappings = cc.parse_disposition(DISPOSITION.read_text(encoding="utf-8"))
        self.rows = {m["row"]: m for m in mappings}

    def test_the_proposal_yields_seventy_five_rows(self):
        self.assertEqual(len(self.six), 75)
        for tree, expected in (("cc-suite", 29), ("grill-for-claude", 7), ("nlpm", 25),
                               ("workspace", 14)):
            with self.subTest(tree=tree):
                self.assertEqual(sum(1 for k in self.six if k.startswith(tree + ":")), expected)

    def test_every_row_carries_sixs_disposition(self):
        for row, (disposition, _, _source, _home) in self.six.items():
            with self.subTest(row=row):
                self.assertEqual(self.rows[row]["disposition"], disposition,
                                 f"{row}: §6 says {disposition}")

    def test_every_function_target_is_one_six_names(self):
        """Where §6's home column names function IDs, the map must not invent different ones."""
        for row, (disposition, ids, _source, _home) in self.six.items():
            if not ids or disposition == "D":
                continue        # a D row's home cell is prose; it carries no function target
            with self.subTest(row=row):
                target = self.rows[row].get("target", [])
                mapped = frozenset(target if isinstance(target, list) else [target])
                required = required_ids(self.six_raw[row])
                self.assertTrue(mapped <= ids,
                                f"{row}: map invents {sorted(mapped - ids)}; §6 names {sorted(ids)}")
                self.assertEqual(mapped, required,
                                 f"{row}: §6 states {sorted(required)} outside parentheses; "
                                 f"the map names {sorted(mapped)}")

    def test_path_targets_match_the_path_six_names(self):
        """§6 gives three workspace rows a repository path as their home. Allowing a path there is
        not the same as checking it is the right one."""
        for row in sorted(cc.PATH_TARGET_ROWS):
            with self.subTest(row=row):
                target = self.rows[row]["target"]
                # Every target, not just the first: `[literal/path.md, bogus/path.md]` passed while
                # only target[0] was checked.
                targets = target if isinstance(target, list) else [target]
                cell = self.six_raw[row]
                literal = re.findall(r"`([^`]*/[^`]*)`", cell)
                for one in targets:
                    if literal:
                        self.assertIn(one, literal,
                                      f"{row}: §6 names {literal}; the map targets {one!r}")
                    else:
                        # Only where §6's home is prose (workspace:12) may a target be matched by
                        # its distinguishing stem.
                        stem = one.rsplit("/", 1)[-1].split(".")[0]
                        self.assertIn(stem, cell,
                                      f"{row}: §6's prose home does not mention {stem!r}")

    def test_the_only_row_without_a_six_source_is_the_recorded_divergence(self):
        self.assertEqual(set(self.rows) - set(self.six), DIVERGENCES)
        note = self.rows["cc-suite:30"].get("note", "")
        self.assertIn("DIVERGENCE", note)

    def test_each_rows_paths_answer_to_sixs_source_cell(self):
        """Dispositions and targets alone cannot catch an artifact swapped between two rows that
        share both. §6 names its artifacts in backticks; at least one of those names must appear in
        the paths the row claims."""
        checked = 0
        for row, (_, _ids, source, _home) in self.six.items():
            names = [n for n in re.findall(r"`([^`]+)`", source) if not n.startswith("-")]
            if not names:
                continue                      # prose-only source cells carry no checkable token
            mapping = self.rows[row]
            claimed = " ".join(mapping.get("paths", []) + mapping.get("corpus_roots", []))
            with self.subTest(row=row):
                # §6 writes some sources as globs (`bridge_*`, `mcp_*`) and names a few artifacts
                # that a given tree does not actually have (`doctor` alongside `diagnose`). A glob
                # is matched by its prefix; a name absent from the tree cannot be claimed by anyone
                # and is not evidence of an omission.
                present = universe_for(row.split(":")[0])
                stems = []
                for name in names:
                    cleaned = name.strip("$` ").rstrip("*/").rstrip(".")
                    if not cleaned:
                        continue
                    if "*" in name:
                        head = re.match(r"\.?[A-Za-z0-9_-]*", cleaned).group(0)
                        if head:
                            stems.append(("prefix", head))
                    elif "/" in cleaned:
                        # §6 sometimes names a path (`bin/nlpm-check`, `auditor/scripts/*`).
                        stems.append(("path", cleaned.rstrip("/")))
                    elif any(cleaned in path for path in present):
                        stems.append(("segment", cleaned if cleaned.startswith(".")
                                      else cleaned.split(".")[0]))
                # Boundary-aware: `audit` must not be satisfied by `audit-fix`. A name counts only
                # where it is a whole path segment or a whole basename stem.
                segments = set()
                for path in mapping.get("paths", []) + mapping.get("corpus_roots", []):
                    parts = path.split("/")
                    segments.update(parts)
                    segments.add(parts[-1].split(".")[0])
                paths = mapping.get("paths", []) + mapping.get("corpus_roots", [])
                missing = []
                for kind, stem in stems:
                    if kind == "prefix":
                        ok = any(s.startswith(stem) for s in segments)
                    elif kind == "path":
                        ok = any(p == stem or p.startswith(stem + "/") or p.endswith("/" + stem)
                                 for p in paths)
                    else:
                        ok = stem in segments
                    if not ok:
                        missing.append(stem)
                self.assertEqual(missing, [],
                                 f"{row}: §6 names {names}; the row does not claim {missing}")
            checked += 1
        self.assertGreater(checked, 40, "the source-cell check must cover most rows")

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

    def test_nlpm_badge_is_not_treated_as_a_generated_report(self):
        """§6 lists `nlpm-badge.json` as a source artifact with a disposition. Excluding it as a
        "generated report" made the map unable to claim something §6 requires it to claim — the
        strict source-cell oracle is what surfaced that."""
        self.assertFalse(cc.is_excluded("nlpm-badge.json"))

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
    """The manifests are the only record CI has of the trees, so drift must be a reviewable diff.

    vibe-132: the check executes wherever it can gate. Trees resolve per
    `resolve_pinned_trees` (env var strict, layout defaults lenient); regeneration reads
    the *pinned commit* read-only, so a checkout's HEAD position is irrelevant; and the
    two failure modes blame the artifact that actually diverged — an unservable pin names
    the checkout, a byte mismatch at the pin names the manifest.
    """

    def test_regenerating_a_pinned_manifest_reproduces_it(self):
        root = resolve_pinned_trees()
        strict = bool(os.environ.get(PINNED_TREES_ENV))
        if root is None:
            self.skipTest("no pinned-tree layout resolves and "
                          f"{PINNED_TREES_ENV} is unset (local machines only)")
        for repo, pin in cc.PINS.items():
            with self.subTest(repo=repo):
                tree = root / repo
                if not (tree / ".git").exists():
                    if strict:
                        self.fail(f"{PINNED_TREES_ENV} is set but {tree} is not a "
                                  "checkout — in CI this means the fetch step did not run")
                    self.skipTest(f"{tree} is not a checkout")
                verdict, message = verify_manifest(tree, repo, pin,
                                                   MANIFESTS / f"{repo}.json")
                self.assertEqual(verdict, "ok", message)


class TestReproducibilityMachinery(unittest.TestCase):
    """vibe-132's helpers, hermetically: layout resolution and the blame split.

    The mini-repos carry two commits with command-local identity; the expected manifest is
    generated from the FIRST commit while HEAD stays on the SECOND, so the central
    off-pin-HEAD behavior — position irrelevant once regeneration reads the pin — is the
    case actually proven.
    """

    def _root(self):
        root = Path(tempfile.mkdtemp(prefix="repro-132-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return root

    def _git(self, tree, *args):
        return subprocess.run(
            ["git", "-C", str(tree), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
             *args], capture_output=True, text=True, check=True).stdout.strip()

    def _mini_repo(self, root):
        """(tree, first_commit) — two commits, HEAD left on the second."""
        tree = root / "cc-suite"
        tree.mkdir(parents=True)
        (tree / "one.md").write_text("one\n")
        self._git(tree, "init", "-q")
        self._git(tree, "add", "-A")
        self._git(tree, "commit", "-q", "-m", "first")
        first = self._git(tree, "rev-parse", "HEAD")
        (tree / "two.md").write_text("two\n")
        self._git(tree, "add", "-A")
        self._git(tree, "commit", "-q", "-m", "second")
        return tree, first

    def _gen(self, tree, pin, out):
        subprocess.run([sys.executable, str(GEN), str(tree), "--repo", "cc-suite",
                        "--ref", pin, "--out", str(out)], capture_output=True, check=True)

    def test_resolver_env_wins(self):
        target = self._root()
        got = resolve_pinned_trees(env={PINNED_TREES_ENV: str(target)},
                                   repo_root=Path("/nonexistent"))
        self.assertEqual(got, target)

    def test_resolver_prefers_main_checkout_layout(self):
        root = self._root()
        (root / "codes" / "vibe-suite").mkdir(parents=True)
        (root / "codes" / "nlpm").mkdir()
        got = resolve_pinned_trees(env={}, repo_root=root / "codes" / "vibe-suite")
        self.assertEqual(got, root / "codes")

    def test_resolver_falls_back_to_four_parent_layout(self):
        root = self._root()
        (root / "codes" / "cc-suite").mkdir(parents=True)
        repo_root = root / "runs" / "r1" / "worktrees" / "vibe-suite"
        repo_root.mkdir(parents=True)
        got = resolve_pinned_trees(env={}, repo_root=repo_root)
        self.assertEqual(got, root / "codes")

    def test_resolver_none_when_no_candidate(self):
        root = self._root()
        repo_root = root / "alone" / "vibe-suite"
        repo_root.mkdir(parents=True)
        self.assertIsNone(resolve_pinned_trees(env={}, repo_root=repo_root))

    def test_off_pin_head_is_ok(self):
        root = self._root()
        tree, first = self._mini_repo(root)
        manifest = root / "cc-suite.json"
        self._gen(tree, first, manifest)
        verdict, message = verify_manifest(tree, "cc-suite", first, manifest)
        self.assertEqual(verdict, "ok", message)

    def test_unservable_pin_blames_checkout(self):
        root = self._root()
        tree, first = self._mini_repo(root)
        ghost = "deadbeef" * 5
        verdict, message = verify_manifest(tree, "cc-suite", ghost, root / "cc-suite.json")
        self.assertEqual(verdict, "checkout")
        self.assertIn(str(tree), message)
        self.assertIn(ghost, message)
        self.assertIn("fetch", message)

    def test_tampered_manifest_blames_manifest(self):
        root = self._root()
        tree, first = self._mini_repo(root)
        manifest = root / "cc-suite.json"
        self._gen(tree, first, manifest)
        data = json.loads(manifest.read_text())
        data["files"].append("phantom.md")
        manifest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        verdict, message = verify_manifest(tree, "cc-suite", first, manifest)
        self.assertEqual(verdict, "manifest")
        self.assertIn("cc-suite.json", message)
        self.assertIn(first, message)


class TestChecksAreWiredIntoTheCLI(CLICase):
    """The helper tests above prove each check is *correct*. These prove each is *called*.

    Removing an integration call — `check_counts` from `run()`, say — would leave every helper test
    and the passing baseline green, which is exactly the hole the review named. Each case here
    perturbs real input so that only a wired-in check can fail it.
    """

    def manifest_mutated(self, repo, mutate):
        tmp = self.sandbox()
        path = tmp / "manifests" / f"{repo}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return self.run_check(manifests=tmp / "manifests")

    def test_the_count_check_is_called(self):
        """Drop a SKILL.md from the manifest: only a wired-in count check notices."""
        def drop_a_skill(data):
            skill = next(f for f in data["files"] if f.endswith("/SKILL.md"))
            data["files"] = [f for f in data["files"] if f != skill]
        result = self.manifest_mutated("cc-suite", drop_a_skill)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("expected 13 skills", result.stderr)

    def test_the_nested_script_library_count_is_called(self):
        def drop_a_lib(data):
            lib = next(f for f in data["files"] if f.startswith("scripts/lib/"))
            data["files"] = [f for f in data["files"] if f != lib]
        result = self.manifest_mutated("cc-suite", drop_a_lib)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scripts/lib", result.stderr)

    def test_the_exclusion_list_is_called(self):
        """An OS-junk file added to a manifest must not become a coverage obligation."""
        def add_junk(data):
            # `scripts/**/*` matches any file, so this one IS allowlisted and only the exclusion
            # list keeps it out. `commands/.DS_Store` would have proved nothing: the commands
            # pattern is `commands/**/*.md`, so it was never in the universe to begin with.
            data["files"] = sorted(data["files"] + ["scripts/.DS_Store", "scripts/__pycache__/x.py"])
        self.assertEqual(self.manifest_mutated("cc-suite", add_junk).returncode, 0,
                         "an allowlisted-but-excluded file must not require a disposition row")

    def test_the_exclusion_list_is_load_bearing(self):
        """The converse: the same path with a normal name DOES require a row. Without this, a
        broken exclusion list and a broken allowlist look identical."""
        def add_real(data):
            data["files"] = sorted(data["files"] + ["scripts/genuinely-new.sh"])
        result = self.manifest_mutated("cc-suite", add_real)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scripts/genuinely-new.sh", result.stderr)

    def test_the_allowlist_is_called(self):
        """A newly allowlisted file with no row must fail — proving the walk reaches the manifest."""
        def add_command(data):
            data["files"] = sorted(data["files"] + ["commands/brand-new.md"])
        result = self.manifest_mutated("cc-suite", add_command)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commands/brand-new.md", result.stderr)

    def test_the_workspace_walk_is_called(self):
        def add_resource(data):
            data["files"] = sorted(data["files"] + ["issue2pr/brand-new.md"])
        result = self.manifest_mutated("workspace", add_resource)
        self.assertNotEqual(result.returncode, 0)

    def test_workspace_path_validation_is_called(self):
        def poison(data):
            data["files"] = sorted(data["files"] + ["../escape.md"])
        result = self.manifest_mutated("workspace", poison)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("clean relative POSIX path", result.stderr)


class TestWorkspaceManifestIsReproducible(unittest.TestCase):
    """The workspace tree is unpinned and lives outside this repository, so its snapshot is the one
    manifest that can drift without a commit to compare against."""

    WORKSPACE_ROOT = REPO_ROOT.parent.parent.parent.parent / ".claude" / "skills"

    def test_regenerating_workspace_json_reproduces_it(self):
        if not self.WORKSPACE_ROOT.is_dir():
            self.skipTest(f"workspace skills not present at {self.WORKSPACE_ROOT}")
        out = Path(tempfile.mkdtemp()) / "workspace.json"
        self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
        subprocess.run([sys.executable, str(GEN), str(self.WORKSPACE_ROOT), "--repo", "workspace",
                        "--out", str(out)], capture_output=True, check=True)
        self.assertEqual(out.read_text(encoding="utf-8"),
                         (MANIFESTS / "workspace.json").read_text(encoding="utf-8"),
                         "workspace.json is stale against the live workspace skills")


if __name__ == "__main__":
    unittest.main()
