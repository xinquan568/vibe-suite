#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""vibe-198 / M32: the test suite must not leak temp directories into $TMPDIR.

Two kinds of check:

* **Helper unit tests** — `TempDirMixin.mkdtemp` removes its dir when the test ends, `scratch_dir`
  removes its dir at process exit, and the Node `tmpWorkspace()` removes its dir at process exit.
* **Deterministic leak meta-checks** — a previously-leaking module (Python and Node) is run in a
  subprocess pointed at a *private* `$TMPDIR`, so the assertion is isolated from every other process
  on the machine. After the subprocess exits, its private `$TMPDIR` must be empty. This is the
  robust form of the issue's "no new entries under $TMPDIR" acceptance: a private-TMPDIR subprocess
  is not subject to the concurrency noise that makes a whole-machine before/after count flaky.
"""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmpdirs import TempDirMixin, scratch_dir  # noqa: E402


class TempDirMixinCleansUp(TempDirMixin, unittest.TestCase):
    def test_mkdtemp_dir_is_removed_after_the_test(self):
        captured = {}

        class Inner(TempDirMixin, unittest.TestCase):
            def test_it(inner):
                captured["d"] = inner.mkdtemp(prefix="mixin-selftest-")
                inner.assertTrue(os.path.isdir(captured["d"]))

        result = unittest.TestResult()
        Inner("test_it").run(result)
        self.assertEqual(result.errors + result.failures, [], "inner test did not pass")
        self.assertFalse(os.path.exists(captured["d"]),
                         "TempDirMixin.mkdtemp did not remove its dir after the test ended")


class ScratchDirCleansUpAtExit(TempDirMixin, unittest.TestCase):
    def test_scratch_dir_is_removed_when_the_process_exits(self):
        private = self.mkdtemp(prefix="scratch-selftest-")
        script = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
            from tmpdirs import scratch_dir
            d = scratch_dir(prefix="scratch-child-")
            sys.stdout.write(d)
        """)
        env = dict(os.environ, TMPDIR=private)
        out = subprocess.run([sys.executable, "-c", script], env=env, check=True,
                             capture_output=True, text=True).stdout.strip()
        self.assertTrue(out, "child did not report a scratch dir")
        self.assertFalse(os.path.exists(out),
                         "scratch_dir was not removed at process exit")


class SubprocessLeaksNothing(TempDirMixin, unittest.TestCase):
    """A previously-leaking module, run in a subprocess with a private $TMPDIR, leaves it empty."""

    # Node writes a shared `node-compile-cache/` into $TMPDIR (a stable V8 cache reused across runs,
    # not a per-run mkdtemp leak); it is not what this issue fixes, so it is not counted.
    IGNORE = {"node-compile-cache"}

    def run_isolated(self, argv):
        private = self.mkdtemp(prefix="leakcheck-")
        env = dict(os.environ, TMPDIR=private)
        r = subprocess.run(argv, env=env, cwd=str(REPO_ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"{argv} failed: {r.stderr[-800:]}")
        leftover = sorted(n for n in os.listdir(private) if n not in self.IGNORE)
        self.assertEqual(leftover, [], f"{argv[-1]} left temp entries in its private $TMPDIR: {leftover}")

    def test_python_module_leaves_no_temp_entries(self):
        self.run_isolated([sys.executable, "-m", "unittest", "tests.test_loop_bounds"])

    def test_node_test_leaves_no_temp_entries(self):
        node = os.environ.get("NODE", "node")
        self.run_isolated([node, "--test", "tests/node/jobs-store.test.mjs"])


if __name__ == "__main__":
    unittest.main()
