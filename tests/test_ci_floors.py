#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""vibe-200 / M34 (b): the CI `test-shard` job crosses the four shards with the DOCUMENTED
python/node floors and ceilings so the floors are actually exercised, publishes advisory
code-coverage artifacts (upload-first, gate-later), and a weekly macOS leg lives in self-check.yml.

The floors matrix is `shard × python × node` with node collapsed on the non-Node shards (only shard 0
runs the Node suite), so the expansion is a bounded 10 legs — this test replicates that expansion
from the emitted ci.yml and pins it. It also pins, PER STEP, that every coverage step is advisory:
measurement can never change the authoritative pass/fail (a `coverage run` / covered-node failure
falls back to a plain run), and the report/upload steps are `continue-on-error`. Fan-in, trigger,
and node-in-shard-0 invariants are pinned by test_ci_shards / test_site_workflows, not re-asserted here.
"""
import re
import unittest
from itertools import product
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SELF_CHECK = REPO_ROOT / ".github" / "workflows" / "self-check.yml"


def _list_values(text, key):
    m = re.search(rf"\b{re.escape(key)}:\s*\[([^\]]*)\]", text)
    return None if not m else [v.strip().strip("'\"") for v in m.group(1).split(",") if v.strip()]


def _step(text, name):
    """The YAML block of a single step (`- name: <name>` up to the next step or job)."""
    m = re.search(rf"(\n      - name: {re.escape(name)}\n(?:.*\n)*?)(?=\n      - |\n  [a-z])", text)
    return m.group(1) if m else ""


class FloorsMatrix(unittest.TestCase):
    def setUp(self):
        self.text = CI.read_text(encoding="utf-8")
        m = re.search(r"\n  test-shard:\n(?P<body>(?:.*\n)*?)    steps:\n", self.text)
        self.assertTrue(m, "test-shard job not found")
        self.shard_body = m.group("body")

    def test_matrix_declares_the_documented_floors(self):
        self.assertEqual(_list_values(self.shard_body, "shard"), ["0", "1", "2", "3"])
        self.assertEqual(_list_values(self.shard_body, "python"), ["3.11", "3.x"])
        self.assertEqual(_list_values(self.shard_body, "node"), ["18", "lts/*"])

    def test_setup_actions_consume_the_matrix(self):
        self.assertRegex(self.text, r"python-version:\s*\$\{\{\s*matrix\.python\s*\}\}")
        self.assertRegex(self.text, r"node-version:\s*\$\{\{\s*matrix\.node\s*\}\}")

    def test_expansion_is_exactly_ten_legs_bounded(self):
        shard = _list_values(self.shard_body, "shard")
        python = _list_values(self.shard_body, "python")
        node = _list_values(self.shard_body, "node")
        excl = {(s, n) for s, n in re.findall(
            r"-\s*\{\s*shard:\s*'([^']*)'\s*,\s*node:\s*'([^']*)'\s*\}", self.shard_body)}
        legs = [(s, p, n) for s, p, n in product(shard, python, node) if (s, n) not in excl]
        self.assertEqual(len(legs), 10, f"expected 10 bounded legs, got {len(legs)}")
        self.assertEqual(sum(1 for s, _, _ in legs if s == "0"), 4,
                         "shard 0 must run the full python*node 2x2")
        self.assertEqual({n for s, _, n in legs if s != "0"}, {"lts/*"},
                         "non-Node shards must not be duplicated across node versions")
        for s in shard:
            self.assertEqual({p for ss, p, _ in legs if ss == s}, {"3.11", "3.x"},
                             f"shard {s} must run python floor AND ceiling")


class AdvisoryCoverage(unittest.TestCase):
    """Each coverage step, isolated, must be unable to change the authoritative verdict."""

    def setUp(self):
        self.text = CI.read_text(encoding="utf-8")

    def test_python_shard_step_measures_but_falls_back_to_plain(self):
        step = _step(self.text, "Run this shard's Python modules")
        self.assertTrue(step, "shard python step not found")
        # measured only on the single ceiling leg per shard
        self.assertIn('[ "${{ matrix.python }}" = "3.x" ]', step)
        self.assertIn('[ "${{ matrix.node }}" = "lts/*" ]', step)
        self.assertIn("python3 -m coverage run --data-file", step)
        self.assertRegex(step, r'mkdir -p "\$RUNNER_TEMP/cov"')
        # a coverage-run failure reruns PLAIN unittest, which is the authoritative verdict
        self.assertIn("rerunning PLAIN for the authoritative verdict", step)
        self.assertGreaterEqual(step.count('python3 -m unittest -v "${mods[@]}"'), 2,
                                "the shard step must keep a PLAIN unittest fallback (and the else branch)")

    def test_python_coverage_report_step_is_advisory(self):
        step = _step(self.text, "Python coverage report (advisory)")
        self.assertTrue(step, "python coverage report step not found")
        self.assertIn("continue-on-error: true", step)
        self.assertRegex(step, r"if:\s*\$\{\{\s*always\(\)\s*&&\s*matrix\.python == '3\.x'\s*&&\s*matrix\.node == 'lts/\*'\s*\}\}")
        self.assertIn("python3 -m coverage xml", step)
        self.assertRegex(step, r'--data-file "\$RUNNER_TEMP/cov/\.coverage\.\$\{\{ matrix\.shard \}\}"')
        self.assertRegex(step, r'-o "\$RUNNER_TEMP/cov/coverage-shard-\$\{\{ matrix\.shard \}\}\.xml"')

    def test_python_coverage_upload_step_is_advisory_and_unique(self):
        step = _step(self.text, "Upload Python coverage (advisory)")
        self.assertTrue(step, "python coverage upload step not found")
        self.assertIn("continue-on-error: true", step)
        self.assertRegex(step, r"if:\s*\$\{\{\s*always\(\)\s*&&\s*matrix\.python == '3\.x'\s*&&\s*matrix\.node == 'lts/\*'\s*\}\}")
        self.assertRegex(step, r"name:\s*py-coverage-shard-\$\{\{ matrix\.shard \}\}")
        self.assertIn("if-no-files-found: ignore", step)

    def test_node_step_measures_but_falls_back_to_plain(self):
        step = _step(self.text, "Run the Node suite")
        self.assertTrue(step, "node suite step not found")
        self.assertIn("--experimental-test-coverage", step)
        self.assertRegex(step, r'tee "\$RUNNER_TEMP/cov/node-coverage\.txt"')
        # a covered-node failure reruns a PLAIN node --test (no coverage flag), the authoritative
        # verdict — the fallback line is distinct from the covered `... --experimental-test-coverage ...`
        self.assertIn("rerunning PLAIN for the authoritative verdict", step)
        self.assertGreaterEqual(step.count('node --test "${files[@]}"'), 1,
                                "the node step must keep a PLAIN node --test fallback")
        # the whole step runs under pipefail so the covered pipeline's node exit propagates
        self.assertRegex(step, r"set -euo pipefail")

    def test_node_coverage_upload_step_is_advisory_and_unique(self):
        step = _step(self.text, "Upload Node coverage (advisory)")
        self.assertTrue(step, "node coverage upload step not found")
        self.assertIn("continue-on-error: true", step)
        self.assertRegex(step, r"if:\s*\$\{\{\s*always\(\)\s*&&\s*matrix\.shard == '0'\s*&&\s*matrix\.python == '3\.x'\s*&&\s*matrix\.node == 'lts/\*'\s*\}\}")
        self.assertRegex(step, r"name:\s*node-coverage")


class MacOSWeeklyLeg(unittest.TestCase):
    def test_macos_job_runs_both_suites_and_declares_permissions(self):
        text = SELF_CHECK.read_text(encoding="utf-8")
        m = re.search(r"\n  macos:\n(?P<body>(?:.*\n)*?)(?=\n  \w|\Z)", text)
        self.assertTrue(m, "self-check.yml has no macos job")
        body = m.group("body")
        self.assertRegex(body, r"runs-on:\s*macos-latest")
        self.assertRegex(body, r"permissions:\n\s*contents:\s*read")
        self.assertIn("python3 -m unittest discover -s tests", body)
        self.assertIn("node --test", body)
        # Bash 3.2 (macOS default) lacks the bash-4 array-read builtins
        self.assertNotIn("mapfile", body)
        self.assertNotIn("readarray", body)


if __name__ == "__main__":
    unittest.main()
