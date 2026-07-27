#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Tests for the codex-runner job engine (E1.1 / vibe-11).

The runner is Node; these tests are Python and drive it as a subprocess, the same way
`test_migrate.py` drives the shell helpers. That is not a stylistic choice — CI's `test` job
discovers `test_*.py`, so this is the form that actually executes at the gate. Two narrow concerns
that need a timing oracle Python cannot give cleanly (event-stream parsing, heartbeat cadence) live
in `tests/node/` instead and run in the same job.

**No test invokes the real `codex` binary.** `VIBE_SUITE_CODEX_BIN` points at a fixture, so the suite
is hermetic: no network, no quota, no dependence on a CLI version. The fixtures reproduce the
behaviours that actually matter, including the one this engine exists to absorb — codex-cli 0.144.6
returning **exit 0** while emitting `turn.failed`.

The workspace is a fresh temp directory per test and the runner resolves its state directory from the
process CWD, so nothing here writes into the repository.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "scripts" / "codex-runner.mjs"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "fake-codex"
SHIPPED_MJS = sorted((REPO_ROOT / "scripts").rglob("*.mjs"))

STATE_DIRNAME = ".vibe-suite-state"
RESULT_KEYS = {"jobId", "status", "threadId", "rawOutput"}


class RunnerCase(unittest.TestCase):
    """Shared harness: a throwaway workspace and one way to invoke the runner."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.probe = self.ws / "probe.json"
        self.addCleanup(self._tmp.cleanup)

    def run_runner(self, *args, fixture="emitter.mjs", timeout=30, expect_ok=True):
        env = dict(os.environ)
        env["VIBE_SUITE_CODEX_BIN"] = str(FIXTURES / fixture)
        env["VIBE_TEST_PROBE"] = str(self.probe)
        result = subprocess.run(
            ["node", str(RUNNER), *args],
            cwd=self.ws, env=env, capture_output=True, text=True, timeout=timeout,
        )
        if expect_ok and result.returncode != 0:
            raise AssertionError(
                f"runner exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return result

    def result_line(self, completed):
        """The one-line JSON contract. Asserting 'exactly one line' is part of the contract."""
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"expected exactly one result line, got {lines!r}")
        return json.loads(lines[0])

    def read_probe(self):
        self.assertTrue(self.probe.exists(), "fixture never ran — nothing was spawned")
        return json.loads(self.probe.read_text())

    def job_record(self, job_id):
        path = self.ws / STATE_DIRNAME / "jobs" / f"{job_id}.json"
        self.assertTrue(path.exists(), f"no job record at {path}")
        return json.loads(path.read_text())

    def wait_for_terminal(self, job_id, timeout=20):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                record = self.job_record(job_id)
            except AssertionError:
                time.sleep(0.05)
                continue
            if record["status"] != "running":
                return record
            time.sleep(0.05)
        raise AssertionError(f"job {job_id} never reached a terminal status")

    def base_args(self, *extra):
        return ["--kind", "review", "--effort", "low", "--sandbox", "read-only",
                "--timeout-ms", "10000", *extra, "--", "fixture prompt"]


class ResultContract(RunnerCase):

    def test_result_contract_shape(self):
        parsed = self.result_line(self.run_runner(*self.base_args()))
        self.assertEqual(set(parsed), RESULT_KEYS)
        self.assertEqual(parsed["status"], "completed")
        self.assertIsInstance(parsed["jobId"], str)
        self.assertIsInstance(parsed["rawOutput"], str)

    def test_thread_id_captured(self):
        parsed = self.result_line(self.run_runner(*self.base_args()))
        self.assertEqual(parsed["threadId"], "thread_fixture_0001")

    def test_turn_failed_with_exit_zero_is_failed(self):
        """The engine's reason for existing: exit 0 must not mean success."""
        completed = self.run_runner(*self.base_args(), fixture="failer.mjs", expect_ok=False)
        parsed = self.result_line(completed)
        self.assertEqual(parsed["status"], "failed")
        self.assertNotEqual(completed.returncode, 0, "a failed job must not exit 0")

    def test_record_matches_result_line(self):
        parsed = self.result_line(self.run_runner(*self.base_args()))
        record = self.job_record(parsed["jobId"])
        for key in RESULT_KEYS:
            self.assertEqual(record[key], parsed[key], f"record disagrees with result line on {key}")


class Invocation(RunnerCase):

    def test_stdin_is_devnull(self):
        self.run_runner(*self.base_args())
        self.assertEqual(self.read_probe()["stdin"], "eof",
                         "stdin must be bound to /dev/null — an open stdin hangs codex")

    def test_sandbox_default_and_forwarding(self):
        self.run_runner("--kind", "review", "--effort", "low", "--timeout-ms", "10000",
                        "--", "p")
        self.assertIn("read-only", self.read_probe()["argv"])

        self.setUp()
        self.run_runner(*self.base_args()[:4], "--sandbox", "workspace-write",
                        "--timeout-ms", "10000", "--", "p")
        self.assertIn("workspace-write", self.read_probe()["argv"])

    def test_model_omitted_by_default(self):
        """P9: no model id unless the caller explicitly pinned one."""
        self.run_runner(*self.base_args())
        argv = self.read_probe()["argv"]
        self.assertNotIn("-m", argv)
        self.assertNotIn("--model", argv)

    def test_model_forwarded_when_explicit(self):
        self.run_runner(*self.base_args("--model", "some-model-id"))
        argv = self.read_probe()["argv"]
        self.assertIn("some-model-id", argv)

    def test_resume_passes_thread_and_inherits_sandbox(self):
        first = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "workspace-write",
            "--timeout-ms", "10000", "--", "first"))
        self.assertEqual(first["status"], "completed")

        self.run_runner("--kind", "review", "--effort", "low", "--timeout-ms", "10000",
                        "--resume", first["jobId"], "--", "follow-up")
        argv = self.read_probe()["argv"]
        self.assertIn("thread_fixture_0001", argv, "resume must forward the captured thread id")
        self.assertIn("workspace-write", argv, "resume must inherit the original sandbox")
        self.assertNotIn("read-only", argv, "resume must not fall back to the default sandbox")


class Deadlines(RunnerCase):

    def test_deadline_kills_and_reports_timed_out(self):
        started = time.monotonic()
        completed = self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "read-only",
            "--timeout-ms", "300", "--", "p",
            fixture="sleeper.mjs", timeout=30, expect_ok=False)
        elapsed = time.monotonic() - started
        parsed = self.result_line(completed)
        self.assertEqual(parsed["status"], "timed_out")
        # A ceiling, not a window: asserting a tight lower bound is how deadline tests flake.
        self.assertLess(elapsed, 20, "deadline was not enforced promptly")

    def test_sigkill_escalation(self):
        """The sleeper ignores SIGTERM; only escalation reaps it."""
        completed = self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "read-only",
            "--timeout-ms", "300", "--", "p",
            fixture="sleeper.mjs", timeout=30, expect_ok=False)
        parsed = self.result_line(completed)
        record = self.job_record(parsed["jobId"])
        self.assertEqual(record["status"], "timed_out")
        self.assertIsNotNone(record["endedAt"], "a killed job must still be finalised")


class Background(RunnerCase):

    def test_background_ack_exact_shape(self):
        parsed = self.result_line(self.run_runner(*self.base_args("--background")))
        self.assertEqual(set(parsed), RESULT_KEYS)
        self.assertEqual(parsed["status"], "running")
        self.assertIsNone(parsed["threadId"], "no thread id can exist at acknowledgement time")
        self.assertIsNone(parsed["rawOutput"], "no output can exist before the process exits")

    def test_launcher_exits_before_job_finishes(self):
        """The launcher must not supervise. It hands off and leaves."""
        started = time.monotonic()
        parsed = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "read-only",
            "--timeout-ms", "10000", "--background", "--", "p",
            fixture="sleeper.mjs", timeout=30))
        launcher_elapsed = time.monotonic() - started
        self.assertEqual(parsed["status"], "running")
        self.assertLess(launcher_elapsed, 15, "launcher blocked on the job instead of detaching")
        record = self.job_record(parsed["jobId"])
        self.assertEqual(record["status"], "running")

    def test_background_launch_is_queryable(self):
        parsed = self.result_line(self.run_runner(*self.base_args("--background")))
        record = self.wait_for_terminal(parsed["jobId"])
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["threadId"], "thread_fixture_0001")
        self.assertIsNotNone(record["rawOutput"])

    def test_record_carries_worker_handle(self):
        """#12 cannot cancel what it cannot signal — the handle is part of this contract."""
        parsed = self.result_line(self.run_runner(*self.base_args("--background")))
        record = self.job_record(parsed["jobId"])
        self.assertIsInstance(record["workerPid"], int)
        self.assertIsInstance(record["pgid"], int)
        terminal = self.wait_for_terminal(parsed["jobId"])
        self.assertIsNotNone(terminal["workerPid"], "the handle is retained after termination")


class Store(RunnerCase):

    def test_record_is_atomic(self):
        parsed = self.result_line(self.run_runner(*self.base_args()))
        jobs_dir = self.ws / STATE_DIRNAME / "jobs"
        leftovers = [p.name for p in jobs_dir.iterdir() if not p.name.endswith(".json")]
        self.assertEqual(leftovers, [], f"temp artifacts survived: {leftovers}")
        json.loads((jobs_dir / f"{parsed['jobId']}.json").read_text())

    def test_state_json_is_untouched(self):
        """Jobs live beside the toggle store, never inside it."""
        state = self.ws / STATE_DIRNAME / "state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"config": {"gate": {"fail_policy": "closed"}}}))
        before = state.read_text()
        self.run_runner(*self.base_args())
        self.assertEqual(state.read_text(), before, "the runner must not write the toggle store")


class Safety(RunnerCase):

    def test_danger_full_access_requires_confirmation(self):
        completed = self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "danger-full-access",
            "--timeout-ms", "10000", "--", "p", expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.probe.exists(),
                         "nothing may be spawned when confirmation is missing")

    def test_danger_full_access_proceeds_with_confirmation(self):
        self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "danger-full-access",
            "--confirm-danger", "--timeout-ms", "10000", "--", "p")
        self.assertIn("danger-full-access", self.read_probe()["argv"])

    def test_confirm_danger_without_danger_sandbox_is_an_error(self):
        """Refuse the flag where it does nothing, so it cannot be set once and forgotten."""
        completed = self.run_runner(*self.base_args("--confirm-danger"), expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)


class SourceConventions(unittest.TestCase):
    """Static checks over the shipped runtime artifacts."""

    def test_shipped_mjs_exist(self):
        self.assertTrue(SHIPPED_MJS, "no shipped .mjs found — the other checks would pass vacuously")

    def test_isc_headers(self):
        for path in SHIPPED_MJS:
            head = path.read_text(encoding="utf-8").splitlines()[:3]
            self.assertTrue(any("SPDX-License-Identifier: ISC" in line for line in head),
                            f"{path.relative_to(REPO_ROOT)}: missing ISC SPDX header in first 3 lines")

    def test_no_top_level_await(self):
        """`node --check` accepts top-level await in .mjs, so it is not an oracle. Node's parser is.

        The module is reduced to something `new Function` can parse — imports dropped, `export`
        prefixes removed — and a top-level `await` then raises "await is only valid in async
        functions", while awaits nested inside async functions parse cleanly.
        """
        checker = REPO_ROOT / "tests" / "node" / "no-top-level-await.mjs"
        result = subprocess.run(["node", str(checker), *[str(p) for p in SHIPPED_MJS]],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_config_bridge_invokes_python(self):
        """Narrow by design: assert the bridge shells to config.py, not that no parser exists."""
        bridge = REPO_ROOT / "scripts" / "lib" / "config-bridge.mjs"
        source = bridge.read_text(encoding="utf-8")
        self.assertIn("config.py", source,
                      "the one .vibe-suite.md reader is config.py; do not re-implement its grammar")

    def test_no_pinned_model_ids(self):
        """P9 belongs to the lint, but a violation here should fail with this issue's tests too."""
        result = subprocess.run([sys.executable, str(REPO_ROOT / "tools" / "model-pin-lint.py")],
                                cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
