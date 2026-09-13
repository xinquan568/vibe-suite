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
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from itertools import product
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
SELF_CHECK = REPO_ROOT / ".github" / "workflows" / "self-check.yml"

# The values of the ONE matrix leg that measures coverage (the ceiling). Any other substitution
# makes the shard step take its plain `else` branch, which never reaches the setup under test.
CEILING_LEG = (("${{ matrix.shard }}", "0"), ("${{ matrix.python }}", "3.x"), ("${{ matrix.node }}", "lts/*"))


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
        # The cov dir is created INSIDE the guarded condition, as the Node step does. As a bare statement
        # in the then-block, `set -euo pipefail` lets a failing mkdir end the step before the plain
        # fallback is reached (vibe-280). This used to be a presence check, and presence cannot tell the
        # two shapes apart: the old unanchored regex matched the guarded form and the unguarded one alike.
        self.assertRegex(step, r'\n\s+&& mkdir -p "\$RUNNER_TEMP/cov"; then\n')
        self.assertNotRegex(step, r'(?m)^\s*mkdir -p "\$RUNNER_TEMP/cov"\s*$',
                            "mkdir must not be a bare statement in the then-block")
        # a coverage-run failure reruns PLAIN unittest, which is the authoritative verdict
        self.assertIn("rerunning PLAIN for the authoritative verdict", step)
        self.assertGreaterEqual(step.count('python3 -m unittest -v "${mods[@]}"'), 2,
                                "the shard step must keep a PLAIN unittest fallback (and the else branch)")

    def test_python_shard_step_survives_a_failing_coverage_setup(self):
        """BEHAVIOURAL, not textual (vibe-280): EXECUTE the shard step's own shell with its coverage
        setup failing, and require the authoritative plain run to still happen and the step to pass.

        The assertions above read the YAML; none of them runs a failure path, which is how an unguarded
        `mkdir` sat under an assertion that the `mkdir` exists. The script is extracted from ci.yml
        rather than carried as a copy, so this cannot drift from the real step.

        Each guard closes a way this test could pass while testing nothing:
          * the ceiling-leg values are substituted and any surviving `${{` fails the test — a blank
            substitution sends the step down its plain `else` branch, which never touches the setup;
          * `python3` is stubbed to succeed, so pip "installs" deterministically (a real install failure
            would also take the `else` branch) and the real suite is never re-entered;
          * `mkdir` is stubbed to FAIL, and the test asserts it was actually called — asserting only that
            the fallback ran would pass on every branch, including the ones that never reach mkdir.
        """
        bash = _bash_supporting_mapfile_d()
        if bash is None:
            self.skipTest("no bash supporting `mapfile -d` (bash 4.4+); the shard step uses it for "
                          "null-delimited discovery and cannot run under an older shell (macOS /bin/bash is 3.2)")
        script = _run_script(_step(self.text, "Run this shard's Python modules"))
        self.assertIn("set -euo pipefail", script, "the probe only means something under the step's own shell options")
        for expression, value in CEILING_LEG:
            self.assertIn(expression, script, f"{expression} no longer appears — substituting it would be vacuous")
            script = script.replace(expression, value)
        self.assertNotIn("${{", script, "an unresolved Actions expression would send the probe down a branch "
                                        "the ceiling leg never takes")

        sandbox = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, sandbox, ignore_errors=True)
        (sandbox / "tests").mkdir()
        (sandbox / "tests" / "test_probe_only.py").write_text("", encoding="utf-8")
        stubs = sandbox / "stubs"
        stubs.mkdir()
        for name, status in (("python3", 0), ("mkdir", 1)):
            stub = stubs / name
            stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "$PROBE_LOG"\nexit {status}\n',
                            encoding="utf-8")
            stub.chmod(0o755)
        log = sandbox / "calls.log"
        runner_temp = sandbox / "runner-temp"
        env = dict(os.environ, PATH=f"{stubs}{os.pathsep}{os.environ.get('PATH', '')}",
                   RUNNER_TEMP=str(runner_temp), PROBE_LOG=str(log))

        proc = subprocess.run([bash, "-c", script], cwd=sandbox, env=env,
                              capture_output=True, text=True, timeout=60)
        calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        detail = f"\ncalls: {calls}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"

        self.assertIn("python3 -m pip install --quiet coverage", calls,
                      "the ceiling branch was not taken, so the coverage setup was never exercised" + detail)
        self.assertIn(f"mkdir -p {runner_temp}/cov", calls,
                      "mkdir was never called, so this probe did not test the guard at all" + detail)
        self.assertEqual(proc.returncode, 0,
                         "a failing coverage setup turned a green suite red — the step ended before its "
                         "plain fallback" + detail)
        self.assertIn("python3 -m unittest -v tests.test_probe_only", calls,
                      "the authoritative plain run never happened" + detail)
        self.assertFalse(any(call.startswith("python3 -m coverage run") for call in calls),
                         "coverage ran even though its setup failed" + detail)

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


def _run_script(step):
    """The shell a step actually runs: the literal block under its `run: |`, dedented."""
    m = re.search(r"\n        run: \|\n((?:(?:          .*)?\n)+)", step)
    return "" if not m else "".join(line[10:] + "\n" for line in m.group(1).splitlines())


def _bash_supporting_mapfile_d():
    """A bash that can run the shard step's null-delimited `mapfile -d ''`, or None."""
    candidates = (shutil.which("bash"), "/opt/homebrew/bin/bash", "/usr/local/bin/bash", "/bin/bash")
    for candidate in dict.fromkeys(c for c in candidates if c):
        if not os.access(candidate, os.X_OK):
            continue
        probe = subprocess.run([candidate, "-c", "mapfile -d '' -t probe < /dev/null"],
                               capture_output=True, timeout=10)
        if probe.returncode == 0:
            return candidate
    return None


# Loads a module in the covered interpreter from a directory removed before the report runs — the route
# the three producers take. It also executes one in-tree file, because a run that measured nothing would
# fail `coverage xml` with "No data to report": a failure for a different reason, proving nothing.
_VANISHING_MODULE_DRIVER = """\
import importlib.util, pathlib, runpy, shutil, sys, tempfile
repo = pathlib.Path(sys.argv[1])
runpy.run_path(str(repo / "scripts" / "lib" / "retired_names.py"))
d = pathlib.Path(tempfile.mkdtemp())
(d / "vanishing.py").write_text("def value():\\n    return 1\\n", encoding="utf-8")
spec = importlib.util.spec_from_file_location("vanishing", d / "vanishing.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.value() == 1
shutil.rmtree(d)
"""


class CoverageScope(unittest.TestCase):
    """vibe-280: coverage measures the workspace's own code, never a module loaded from a directory that is
    gone by report time. Three test modules do exactly that — test_release_gate, test_auditor_scripts and
    test_auditor_findings_helpers — and each recorded a vanished source, `coverage xml` failed on it, and
    three of four shards published no coverage artifact while CI stayed green."""

    def test_a_module_loaded_from_a_vanished_directory_is_not_measured(self):
        if importlib.util.find_spec("coverage") is None:
            self.skipTest("coverage is not installed — CI installs it only on the ceiling leg, and this "
                          "repository is stdlib-only")
        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        driver = work / "driver.py"
        driver.write_text(_VANISHING_MODULE_DRIVER, encoding="utf-8")
        data = work / ".coverage"
        # The repository's own configuration is what is under test, found the way CI finds it: from the
        # working directory, with nothing in the environment overriding it.
        env = {k: v for k, v in os.environ.items() if not k.startswith("COVERAGE_")}

        run = subprocess.run([sys.executable, "-m", "coverage", "run", "--data-file", str(data),
                              str(driver), str(REPO_ROOT)],
                             cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

        listing = subprocess.run(
            [sys.executable, "-c",
             "import coverage, sys; d = coverage.CoverageData(sys.argv[1]); d.read(); "
             "print('\\n'.join(sorted(d.measured_files())))", str(data)],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(listing.returncode, 0, listing.stderr)
        root = REPO_ROOT.resolve()
        outside = [p for p in listing.stdout.splitlines() if p and not Path(p).resolve().is_relative_to(root)]
        self.assertEqual(outside, [], "coverage measured sources outside the workspace; any of them that is "
                                      "gone by report time makes `coverage xml` fail")

        xml = subprocess.run([sys.executable, "-m", "coverage", "xml", "--data-file", str(data),
                              "-o", str(work / "coverage.xml")],
                             cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300)
        self.assertEqual(xml.returncode, 0, "the advisory report failed: " + xml.stdout + xml.stderr)


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
