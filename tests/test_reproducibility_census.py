#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""`tests/reproducibility_census.py` — the skip census, and the weekly job that runs it (vibe-228).

The census exists because a gate that never executes is indistinguishable from one that passes, so
the tests here are mostly about the ways a census can go quietly wrong: counting a skip as a pass,
dropping the reason that says what to supply, exiting zero on a failure, writing nothing to the run
summary, or reporting on a gate list that has silently emptied.

The counting tests drive `main` with an **injected** result, so they never execute the real gates.
The injection is a convenience and never the only path: `test_the_entry_point_appends_to_the_real_
summary_variable` runs the real entry point with the real `GITHUB_STEP_SUMMARY`, because a suite
that only ever injects would stay green with the environment lookup deleted — and the run summary
is the thing the issue's acceptance asks for.
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reproducibility_census as rc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CENSUS = REPO_ROOT / "tests" / "reproducibility_census.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "self-check.yml"
#: The gate roots, scrubbed so a subprocess census reports the unset case whatever the developer's
#: shell happens to export.
SCRUBBED = {k: v for k, v in os.environ.items()
            if k not in ("VIBE_SUITE_PINNED_TREES", "VIBE_SUITE_WORKSPACE_SKILLS",
                         "GITHUB_STEP_SUMMARY")}


class FakeResult:
    """A `unittest` result with the shape `census()` reads, and nothing else."""

    def __init__(self, ran=0, skipped=(), failures=(), errors=()):
        self.testsRun = ran
        self.skipped = list(skipped)
        self.failures = list(failures)
        self.errors = list(errors)


def result_of(**kwargs):
    return lambda *a, **kw: FakeResult(**kwargs)


class TheGateRoster(unittest.TestCase):
    """A census over an empty or unresolvable roster reports "nothing skipped" and passes."""

    def test_the_gate_names_resolve_to_the_intended_classes(self):
        self.assertTrue(rc.GATES, "the census declares no gates")
        flat, stack = [], [rc.load_gates()]
        while stack:
            item = stack.pop()
            stack.extend(item) if isinstance(item, unittest.TestSuite) else flat.append(item)
        self.assertTrue(flat, "the gate roster loaded no tests")
        names = {type(t).__qualname__ for t in flat}
        self.assertNotIn("_FailedTest", names,
                         "a gate name did not resolve; the loader turned it into a placeholder "
                         "that would be counted as a gate")
        self.assertEqual(names, {"TestManifestsAreReproducible",
                                 "TestWorkspaceManifestIsReproducible"})


class TheCensus(unittest.TestCase):

    def test_a_skip_is_counted_with_its_reason(self):
        counts = rc.census(FakeResult(ran=2, skipped=[("t1", "no root"), ("t2", "no skills")]))
        self.assertEqual((counts["ran"], counts["skipped"], counts["passed"]), (2, 2, 0))
        self.assertEqual(counts["skips"], [("t1", "no root"), ("t2", "no skills")])

    def test_subtest_failures_are_counted_per_test_not_per_subtest(self):
        """A REAL `unittest` result, not the fixture: `testsRun` counts the parent once while
        `result.failures` gains an entry per failing `subTest`. Mixing the two scales is how the
        census reported **-2 passed** for a broken pinned root — one test, three failing
        repositories, two tests run. The fixtures cannot reach this shape, so this builds it."""

        class Subtests(unittest.TestCase):
            def test_three_roots(self):
                for root in ("a", "b", "c"):
                    with self.subTest(root=root):
                        self.fail(f"{root} is not a checkout")

            def test_fine(self):
                pass

        suite = unittest.TestSuite([Subtests("test_three_roots"), Subtests("test_fine")])
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.failures), 3, "the fixture did not produce three subtests")
        counts = rc.census(result)
        self.assertEqual(counts["failed"], 1, "three subtests of one test are one failing test")
        self.assertEqual(counts["failure_events"], 3)
        self.assertEqual(counts["passed"], 1)
        self._assert_sums_to_ran(counts)

    def test_skipped_subtests_are_counted_per_test_not_per_subtest(self):
        """`subTest` records skips individually too — `testsRun=1, len(result.skipped)=3` for one
        test skipping three roots. Counting the entry list would put `skipped` on a different
        scale from `ran`; the pinned gate skips per repository, so this is the shape it reaches
        first."""

        class Subtests(unittest.TestCase):
            def test_three_roots(self):
                for root in ("a", "b", "c"):
                    with self.subTest(root=root):
                        self.skipTest(f"{root} has no checkout")

            def test_fine(self):
                pass

        result = unittest.TestResult()
        unittest.TestSuite([Subtests("test_three_roots"), Subtests("test_fine")]).run(result)
        self.assertEqual((result.testsRun, len(result.skipped)), (2, 3),
                         "the fixture did not produce three skipped subtests")
        counts = rc.census(result)
        self.assertEqual(counts["skipped"], 1, "three skipped subtests are one skipped test")
        self.assertEqual(counts["skip_events"], 3)
        self.assertEqual(counts["passed"], 1)
        self.assertEqual(len(counts["skips"]), 3, "every skip reason is kept for the table")
        self._assert_sums_to_ran(counts)

    def test_a_test_both_skipping_and_failing_is_counted_once(self):
        """One root skipped, another failed: without precedence the test lands in two buckets and
        the counts exceed `ran`. Failure wins — a gate that failed anywhere did not pass."""

        class Mixed(unittest.TestCase):
            def test_two_roots(self):
                with self.subTest(root="a"):
                    self.skipTest("a has no checkout")
                with self.subTest(root="b"):
                    self.fail("b is stale")

        result = unittest.TestResult()
        unittest.TestSuite([Mixed("test_two_roots")]).run(result)
        self.assertEqual((result.testsRun, len(result.skipped), len(result.failures)), (1, 1, 1))
        counts = rc.census(result)
        self.assertEqual((counts["failed"], counts["skipped"], counts["passed"]), (1, 0, 0))
        self._assert_sums_to_ran(counts)

    def _assert_sums_to_ran(self, counts):
        self.assertEqual(counts["passed"] + counts["skipped"] + counts["failed"]
                         + counts["errored"], counts["ran"],
                         f"the per-test counts must sum to `ran`: {counts}")
        self.assertGreaterEqual(counts["passed"], 0, f"negative passes: {counts}")

    def test_a_failure_is_counted_and_exits_non_zero(self):
        out = self._main(run=result_of(ran=1, failures=[("t1", "boom")]))
        self.assertEqual(out["code"], 1)
        self.assertIn("1 failed", out["text"])

    def test_an_error_only_result_exits_non_zero(self):
        """Errors are their own branch. With failures empty, only this case can show that an
        error is not silently treated as an absence of failures."""
        out = self._main(run=result_of(ran=1, errors=[("t1", "kaboom")]))
        self.assertEqual(out["code"], 1)
        self.assertIn("1 errored", out["text"])
        self.assertIn("0 failed", out["text"])

    def test_all_skipped_still_exits_zero(self):
        out = self._main(run=result_of(ran=2, skipped=[("t1", "a"), ("t2", "b")]))
        self.assertEqual(out["code"], 0)
        self.assertIn("2 skipped", out["text"])

    def test_the_count_sentence_is_derived_from_the_rows(self):
        """One pass, two skips, one failure: the sentence's numbers must equal what the table
        shows, or the census is reporting two different things at once."""
        out = self._main(run=result_of(ran=4, skipped=[("t1", "a"), ("t2", "b")],
                                       failures=[("t3", "boom")]))
        text = out["text"]
        stated = re.search(r"\*\*(\d+) test\(s\): (\d+) passed, (\d+) skipped, "
                           r"(\d+) failed, (\d+) errored\.\*\*", text)
        self.assertIsNotNone(stated, text)
        ran, passed, skipped, failed, errored = (int(g) for g in stated.groups())
        rows = text.count("\n| `t")
        self.assertEqual(skipped, rows, "the sentence disagrees with the table it sits above")
        self.assertEqual((ran, passed, failed, errored), (4, 1, 1, 0))

    def test_a_skip_reason_reaches_the_report(self):
        out = self._main(run=result_of(ran=1, skipped=[("t1", "VIBE_SUITE_PINNED_TREES is unset")]))
        self.assertIn("VIBE_SUITE_PINNED_TREES is unset", out["text"])

    def test_an_injected_summary_path_receives_the_same_markdown(self):
        target = Path(tempfile.mkdtemp()) / "summary.md"
        self.addCleanup(shutil.rmtree, target.parent, True)
        out = self._main(run=result_of(ran=1, skipped=[("t1", "a")]), summary_path=str(target))
        self.assertEqual(target.read_text(encoding="utf-8"), out["text"])

    def test_no_summary_variable_is_not_an_error(self):
        """Outside GitHub there is nowhere to append, and that is not a failure."""
        env = dict(os.environ)
        env.pop("GITHUB_STEP_SUMMARY", None)
        with mock.patch.dict(os.environ, env, clear=True):
            out = self._main(run=result_of(ran=1, skipped=[("t1", "a")]))
        self.assertEqual(out["code"], 0)

    def _main(self, **kwargs):
        buf = io.StringIO()
        code = rc.main(out=buf, **kwargs)
        return {"code": code, "text": buf.getvalue()}


class TheEntryPoint(unittest.TestCase):
    """The wired command, as a subprocess, so the exit status is the thing asserted."""

    def _run(self, env_extra=None):
        return subprocess.run([sys.executable, str(CENSUS)], cwd=REPO_ROOT,
                              capture_output=True, text=True,
                              env={**SCRUBBED, **(env_extra or {})})

    def test_the_real_entry_point_runs_and_reports(self):
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        for gate in rc.GATES:
            self.assertIn(gate, r.stdout)
        self.assertIn("2 skipped", r.stdout)

    def test_the_entry_point_appends_to_the_real_summary_variable(self):
        """The real `GITHUB_STEP_SUMMARY`, through the real entry point, into a file that
        already has content: the marker proves the census APPENDS rather than truncating a
        summary other steps wrote to, and the counts prove it is the same report as stdout."""
        target = Path(tempfile.mkdtemp()) / "summary.md"
        self.addCleanup(shutil.rmtree, target.parent, True)
        marker = "an-earlier-step-wrote-this\n"
        target.write_text(marker, encoding="utf-8")
        r = self._run({"GITHUB_STEP_SUMMARY": str(target)})
        self.assertEqual(r.returncode, 0, r.stderr)
        written = target.read_text(encoding="utf-8")
        self.assertTrue(written.startswith(marker), "the summary file was truncated, not appended")
        appended = written[len(marker):]
        # Assert the CONTENT before comparing with stdout. An entry point that produced nothing
        # whenever GITHUB_STEP_SUMMARY was set would make both sides the empty string and satisfy
        # an equality check — while the run summary, which is the whole acceptance, stayed blank.
        for gate in rc.GATES:
            self.assertIn(gate, appended, "the appended report does not name the gates")
        self.assertIn("2 skipped", appended, "the appended report carries no skip count")
        self.assertIn("DID NOT RUN", appended)
        self.assertEqual(appended, r.stdout, "the summary and stdout reports differ")


class TheWeeklyJob(unittest.TestCase):
    """Parsed from the workflow, not grepped from its prose."""

    def test_the_reproducibility_job_is_declared(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        job = re.search(r"\n  reproducibility:\n(?P<body>(?:.*\n)*?)(?=\n  \w|\Z)", text)
        self.assertTrue(job, "self-check.yml has no reproducibility job")
        body = job.group("body")
        self.assertRegex(body, r"(?m)^\s+permissions:",
                         "the job declares no permissions block, so it inherits the default "
                         "token scope")
        self.assertIn("tests/reproducibility_census.py", body,
                      "the job does not invoke the census")

    def test_the_job_sets_no_gate_root(self):
        """Deliberate, and worth pinning: no runner has either root, and SETTING one would make
        an unresolved root a failure — turning the weekly job red for an honest absence. The
        job's product is the census; `ci.yml` remains where the pinned-tree gate gates.

        Comment lines are stripped first. The job's own comment explains this decision and names
        both variables, so a raw substring search would read the explanation as the thing it
        forbids — and would keep passing if someone deleted the comment and added the `env:`.
        """
        text = WORKFLOW.read_text(encoding="utf-8")
        job = re.search(r"\n  reproducibility:\n(?P<body>(?:.*\n)*?)(?=\n  \w|\Z)", text)
        self.assertTrue(job)
        code = "\n".join(line for line in job.group("body").splitlines()
                         if not line.lstrip().startswith("#"))
        self.assertIn("reproducibility_census.py", code, "the comment strip ate the job body")
        for name, _ in rc.ROOTS:
            with self.subTest(variable=name):
                self.assertNotIn(name, code)


if __name__ == "__main__":
    unittest.main()
