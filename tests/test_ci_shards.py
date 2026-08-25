#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""vibe-199 / M34: the CI test job is sharded four ways behind a fan-in `test` context, and the
gate-battery docs list the Node suite and the ruby prerequisite.

The sharding is only correct if the four shards partition every `tests/test_*.py` module exactly
once — no module dropped (silently untested in CI), none run twice. The shard assignment is a
runtime modulo of the sorted module list, so a new module is absorbed automatically; this test
replicates that modulo and asserts full, disjoint coverage. It also pins the workflow shape (the
required `test` context is a fan-in that `needs` the shards, so branch protection is unchanged) and
the documentation the issue asks for.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CI = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CLAUDE = REPO_ROOT / "CLAUDE.md"
TESTS_README = REPO_ROOT / "tests" / "README.md"
RUN_PARALLEL = REPO_ROOT / "tests" / "run-parallel.sh"

SHARDS = 4


class ShardPartition(unittest.TestCase):
    def modules(self):
        return sorted(p.name for p in (REPO_ROOT / "tests").glob("test_*.py"))

    def test_the_modulo_partition_covers_every_module_exactly_once(self):
        mods = self.modules()
        self.assertTrue(mods, "no test_*.py modules found")
        shards = {s: [] for s in range(SHARDS)}
        for i, m in enumerate(mods):
            shards[i % SHARDS].append(m)
        union = [m for ms in shards.values() for m in ms]
        self.assertEqual(sorted(union), mods, "the shards do not cover exactly the module set")
        self.assertEqual(len(union), len(set(union)), "a module lands in more than one shard")
        for s in range(SHARDS):
            self.assertTrue(shards[s], f"shard {s} is empty")

    def test_ci_shards_with_this_modulo(self):
        # The ci.yml shard step must use the same `i % 4 == <shard>` partition over a sorted
        # `find tests -maxdepth 1 -name 'test_*.py'`, so this test and CI agree.
        text = CI.read_text(encoding="utf-8")
        self.assertRegex(text, r"find tests -maxdepth 1 -name 'test_\*\.py'")
        self.assertRegex(text, r"i % 4\b")
        self.assertRegex(text, r'matrix:\s*\n\s*shard:\s*\[')


class WorkflowShape(unittest.TestCase):
    def test_matrix_has_exactly_four_shards(self):
        text = CI.read_text(encoding="utf-8")
        m = re.search(r"shard:\s*\[([^\]]*)\]", text)
        self.assertTrue(m, "no matrix shard list")
        values = [v.strip().strip("'\"") for v in m.group(1).split(",")]
        self.assertEqual(values, ["0", "1", "2", "3"], "the matrix must be exactly four shards 0-3")

    def test_test_is_a_fanin_over_the_shards(self):
        text = CI.read_text(encoding="utf-8")
        # a matrix shard job and a fan-in `test` job that needs it
        self.assertRegex(text, r"\n  test-shard:\n")
        self.assertRegex(text, r"\n  test:\n(?:.*\n)*?\s*needs:\s*\[test-shard\]")
        # the fan-in still carries the required context name `test`
        self.assertRegex(text, r"\n  test:\n\s*name:\s*test\b")
        # it runs even on shard failure (always) and then fails explicitly unless every shard passed
        fanin = re.search(r"\n  test:\n(?P<body>(?:.*\n)*?)\n  \w", text).group("body")
        self.assertRegex(fanin, r"if:\s*\$\{\{\s*always\(\)\s*\}\}", "the fan-in must run even when a shard fails")
        self.assertIn("needs.test-shard.result", fanin, "the fan-in must inspect the shards' result")
        self.assertIn('"success"', fanin, "the fan-in must require the shards to have succeeded")
        self.assertIn("exit 1", fanin, "the fan-in must fail (not skip) when a shard did not succeed")

    def test_node_suite_stays_in_the_test_lineage(self):
        text = CI.read_text(encoding="utf-8")
        # the Node suite runs under a shard (shard 0), not in the removed standalone test job
        self.assertRegex(text, r"node --test")
        self.assertRegex(text, r"matrix\.shard == '0'")

    def test_pinned_trees_is_a_single_writer_with_a_conditional_save(self):
        text = CI.read_text(encoding="utf-8")
        # a dedicated fetch job the shards depend on, so racing shard writers cannot poison the cache
        self.assertRegex(text, r"\n  pinned-trees:\n")
        self.assertRegex(text, r"\n  test-shard:\n(?:.*\n)*?\s*needs:\s*\[pinned-trees\]")
        # exactly one cache writer, saving only on a cold miss AND a proven-complete tree set
        self.assertEqual(text.count("actions/cache/save@v4"), 1, "there must be exactly one cache writer")
        self.assertRegex(text, r"steps\.fetch\.outputs\.complete == 'true'")
        self.assertRegex(text, r"cache-hit != 'true'")
        # the fetch hard-fails on an empty/broken pin list so an empty tree is never cached: the
        # extraction validates PINS in Python BEFORE printing (the `-s` guard alone is fooled by an
        # empty mapping, which prints one blank line) — PinExtractionHardFail exercises the behaviour.
        self.assertRegex(text, r"not isinstance\(pins, dict\) or not pins")
        self.assertRegex(text, r'\[ -s "\$RUNNER_TEMP/pins\.txt" \]')

    def test_fanin_grants_no_token(self):
        text = CI.read_text(encoding="utf-8")
        # the pure fan-in `test` job checks out nothing and needs no token
        m = re.search(r"\n  test:\n(?P<body>(?:.*\n)*?)\n  \w", text)
        self.assertTrue(m, "could not isolate the test fan-in job body")
        self.assertRegex(m.group("body"), r"permissions:\s*\{\}")


class PinExtractionHardFail(unittest.TestCase):
    """The pinned-trees fetch step extracts PINS from tools/coverage-check.py with an embedded
    Python snippet. That snippet must HARD-fail (nonzero, so `set -e` aborts the job) on an empty
    or malformed PINS — an empty mapping otherwise prints one blank line, passes the `[ -s ]`
    guard, and lets the job "succeed" with nothing cached. This lifts the ACTUAL snippet out of
    ci.yml and runs it against a fake tools/coverage-check.py, so it regresses shipped behaviour."""

    def _snippet(self):
        text = CI.read_text(encoding="utf-8")
        m = re.search(r"python3 - <<'PY'[^\n]*\n(.*?)\n\s*PY(?:\n|$)", text, re.S)
        self.assertTrue(m, "pin-extraction heredoc not found in ci.yml")
        return textwrap.dedent(m.group(1))

    def _run(self, pins_literal):
        root = Path(tempfile.mkdtemp(prefix="pins-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "tools").mkdir()
        (root / "tools" / "coverage-check.py").write_text(
            f"PINS = {pins_literal}\n", encoding="utf-8")
        return subprocess.run([sys.executable, "-"], input=self._snippet(),
                              cwd=root, capture_output=True, text=True)

    def test_empty_pins_hard_fails(self):
        r = self._run("{}")
        self.assertNotEqual(r.returncode, 0,
                            "empty PINS must hard-fail extraction (nonzero):\n" + r.stdout + r.stderr)

    def test_malformed_pin_hard_fails(self):
        r = self._run("{'repoA': ''}")
        self.assertNotEqual(r.returncode, 0,
                            "a blank pin must hard-fail extraction:\n" + r.stdout + r.stderr)

    def test_valid_pins_extract_and_print(self):
        r = self._run("{'repoA': 'abc123', 'repoB': 'def456'}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("repoA abc123", r.stdout)
        self.assertIn("repoB def456", r.stdout)


class BatteryDocs(unittest.TestCase):
    def test_claude_md_battery_lists_the_node_suite(self):
        text = CLAUDE.read_text(encoding="utf-8")
        self.assertRegex(text, r"node --test tests/node/\*\.test\.mjs")

    def test_ruby_prerequisite_is_documented(self):
        for doc in (CLAUDE, TESTS_README):
            with self.subTest(doc=doc.name):
                self.assertRegex(doc.read_text(encoding="utf-8"), r"\bruby\b")

    def test_run_parallel_exists_with_isc_header(self):
        self.assertTrue(RUN_PARALLEL.is_file(), "tests/run-parallel.sh is missing")
        head = "\n".join(RUN_PARALLEL.read_text(encoding="utf-8").splitlines()[:3])
        self.assertIn("SPDX-License-Identifier: ISC", head)


class RunParallelBehaviour(unittest.TestCase):
    """The local runner runs every top-level module once and fails if any module fails."""

    def _tree(self, modules):
        root = Path(tempfile.mkdtemp(prefix="rp-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "tests").mkdir()
        shutil.copy(RUN_PARALLEL, root / "tests" / "run-parallel.sh")
        (root / "tests" / "run-parallel.sh").chmod(0o755)
        for name, body in modules.items():
            (root / "tests" / name).write_text(body, encoding="utf-8")
        return root

    def _passing(self):
        return ("import os, unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        open(os.path.join(os.environ['RP_MARKERS'], os.environ['RP_SELF']), 'w').close()\n")

    def test_runs_every_module_once(self):
        names = ["test_alpha.py", "test_beta.py", "test_gamma.py"]
        root = self._tree({n: self._passing() for n in names})
        markers = root / "markers"
        markers.mkdir()
        # RP_SELF must differ per module; write it into each module rather than the env.
        for n in names:
            body = self._passing().replace("os.environ['RP_SELF']", repr(n))
            (root / "tests" / n).write_text(body, encoding="utf-8")
        r = subprocess.run(["bash", str(root / "tests" / "run-parallel.sh")],
                           env=dict(os.environ, RP_MARKERS=str(markers)),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(sorted(p.name for p in markers.iterdir()), sorted(names),
                         "run-parallel did not run each module exactly once")

    def test_exits_nonzero_when_a_module_fails(self):
        root = self._tree({
            "test_ok.py": "import unittest\nclass T(unittest.TestCase):\n"
                          "    def test_a(self): self.assertTrue(True)\n",
            "test_bad.py": "import unittest\nclass T(unittest.TestCase):\n"
                           "    def test_a(self): self.assertTrue(False)\n",
        })
        r = subprocess.run(["bash", str(root / "tests" / "run-parallel.sh")],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0, "run-parallel exited 0 despite a failing module")


if __name__ == "__main__":
    unittest.main()
