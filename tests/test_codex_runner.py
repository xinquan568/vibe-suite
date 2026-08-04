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
import signal
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
# The ISC-header rule covers test and fixture .mjs too (E1.2 / vibe-12, round-1 review finding 5) —
# a rule checked only where it was first applied is a rule that stops being followed.
CHECKED_MJS = SHIPPED_MJS + sorted((REPO_ROOT / "tests" / "node").glob("*.mjs")) \
    + sorted((REPO_ROOT / "tests" / "fixtures").rglob("*.mjs"))

STATE_DIRNAME = ".vibe-suite-state"
RESULT_KEYS = {"jobId", "status", "threadId", "rawOutput", "verdictState"}


class RunnerCase(unittest.TestCase):
    """Shared harness: a throwaway workspace and one way to invoke the runner."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.probe = self.ws / "probe.json"
        self.addCleanup(self._tmp.cleanup)
        # vibe-129: cleanups run LIFO, so registering the reaper AFTER the directory
        # cleanup makes it run FIRST — no process that can write under this workspace
        # survives into TemporaryDirectory teardown. Both the workspace and this
        # setUp's fixture ledger are bound as arguments: tests that call setUp() again
        # must pair each reaper with its own directory, not whatever self.ws holds later.
        self._spawned_fixtures = []
        self.addCleanup(self._reap_workspace_writers, self.ws, self._spawned_fixtures)

    def _group_members(self, groups):
        """pgid -> non-zombie member pids, via ps (portable to macOS and ubuntu CI).
        A zombie cannot write and counts as quiescent; per-pid kill(pid, 0) would both
        miss unrecorded descendants and wait on corpses."""
        out = subprocess.run(["ps", "-A", "-o", "pid=,pgid=,stat="],
                             capture_output=True, text=True)
        live = {}
        for line in out.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            try:
                pid_i, pgid_i = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            if pgid_i in groups and not parts[2].startswith("Z"):
                live.setdefault(pgid_i, []).append(pid_i)
        return live

    @staticmethod
    def _signal_groups(pgids, sig):
        for pgid in pgids:
            try:
                os.killpg(pgid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    def _reap_workspace_writers(self, ws, spawned_fixtures):
        """Drain, escalate, verify — the vibe-129 teardown invariant. Only validated
        live background handles are ever signalled: a *running* record whose
        workerPid/pgid are ints with pgid == workerPid (the worker leads its own group),
        pgid > 1, and not the harness's group. Terminal or historical records are never
        touched (PGID reuse). A group observed absent is dropped permanently. A hung
        worker whose fixture should terminate fails the test after the hygiene reap
        rather than vanishing into cleanup."""
        jobs_dir = ws / STATE_DIRNAME / "jobs"
        harness_pgid = os.getpgid(0)
        active = set()
        for rec in (jobs_dir.glob("job_*.json") if jobs_dir.is_dir() else []):
            try:
                data = json.loads(rec.read_text())
            except (ValueError, OSError):
                continue  # never convert a test failure into the reaper's own
            pid, pgid = data.get("workerPid"), data.get("pgid")
            if (data.get("status") == "running" and isinstance(pid, int)
                    and isinstance(pgid, int) and pgid == pid and pgid > 1
                    and pgid != harness_pgid):
                active.add(pgid)
        if not active:
            return
        deadline = time.monotonic() + 15.0

        def live_now():
            members = self._group_members(active)
            active.intersection_update(members)   # absent once -> dropped permanently
            return members

        # Phase 1 — drain: emitter workers finish on their own.
        drain_until = min(time.monotonic() + 2.0, deadline)
        while time.monotonic() < drain_until and live_now():
            time.sleep(0.05)
        survivors = live_now()
        hung_nonsleeper = False
        if survivors:
            expects_persistent = "sleeper.mjs" in spawned_fixtures
            if not expects_persistent:
                hung_nonsleeper = True
            # Phase 2 — escalate: TERM, brief grace, then KILL (sleeper ignores TERM;
            # the group covers the unrecorded grandchild).
            self._signal_groups(survivors, signal.SIGTERM)
            grace_until = min(time.monotonic() + 1.0, deadline)
            while time.monotonic() < grace_until and live_now():
                time.sleep(0.05)
            self._signal_groups(live_now(), signal.SIGKILL)
        # Phase 3 — verify: no non-zombie member of any collected group remains.
        while live_now():
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"workspace writers survived teardown: {sorted(live_now())}")
            time.sleep(0.05)
        if hung_nonsleeper:
            raise AssertionError(
                "a worker whose fixture should terminate was still alive after the "
                "drain window — reaped for hygiene, failing loudly (vibe-129)")

    def run_runner(self, *args, fixture="emitter.mjs", timeout=30, expect_ok=True):
        self._spawned_fixtures.append(fixture)
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

    def test_resume_forwards_thread_and_omits_sandbox_flag(self):
        """`codex exec resume` accepts no -s/--sandbox — verified against codex-cli 0.144.6.

        Round 1 passed `-s` here and the test still passed, because the fixture accepted any argv.
        Omitting the flag is also how "resume inherits the original sandbox" is genuinely achieved:
        the resumed session already carries it. The recorded sandbox is policy metadata, which
        `test_resume_into_danger_requires_confirmation` exercises.
        """
        first = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "workspace-write",
            "--timeout-ms", "10000", "--", "first"))
        self.assertEqual(first["status"], "completed")

        self.run_runner("--kind", "review", "--effort", "low", "--timeout-ms", "10000",
                        "--resume", first["jobId"], "--", "follow-up")
        argv = self.read_probe()["argv"]
        self.assertEqual(argv[:3], ["exec", "resume", "thread_fixture_0001"],
                         "resume must be the subcommand, with the captured thread id")
        self.assertNotIn("-s", argv, "codex exec resume rejects -s")
        self.assertNotIn("--sandbox", argv)

    def test_resume_records_the_inherited_sandbox(self):
        """The sandbox still governs policy even though it is not a CLI argument."""
        first = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "workspace-write",
            "--timeout-ms", "10000", "--", "first"))
        second = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--timeout-ms", "10000",
            "--resume", first["jobId"], "--", "follow-up"))
        self.assertEqual(self.job_record(second["jobId"])["sandbox"], "workspace-write")


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
        for path in CHECKED_MJS:
            head = path.read_text(encoding="utf-8").splitlines()[:3]
            self.assertTrue(any("SPDX-License-Identifier: ISC" in line for line in head),
                            f"{path.relative_to(REPO_ROOT)}: missing ISC SPDX header in first 3 lines")

    def test_no_top_level_await(self):
        """`node --check` accepts top-level await in .mjs, so it is not an oracle.

        The checker is sound in one direction: every ambiguity resolves to `top-level-await` or
        `refused`, never to `clean`. Its own probe suite (tests/node/no-top-level-await.test.mjs)
        pins both false negatives that round 1 shipped with.
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


class SandboxGate(RunnerCase):
    """The gate must read the EFFECTIVE sandbox, not the raw flag."""

    def write_config(self, sandbox):
        (self.ws / ".vibe-suite.md").write_text(f"---\nsandbox: {sandbox}\n---\n\n# config\n")

    def test_config_default_danger_is_refused(self):
        """Round-1 blocker: a config default reached the spawn without confirmation."""
        self.write_config("danger-full-access")
        completed = self.run_runner("--kind", "review", "--effort", "low",
                                    "--timeout-ms", "5000", "--", "p", expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.probe.exists(), "nothing may be spawned when confirmation is missing")

    def test_config_default_danger_proceeds_with_confirmation(self):
        self.write_config("danger-full-access")
        self.run_runner("--kind", "review", "--effort", "low", "--confirm-danger",
                        "--timeout-ms", "5000", "--", "p")
        self.assertIn("danger-full-access", self.read_probe()["argv"])

    def test_confirm_danger_without_effective_danger_is_an_error(self):
        completed = self.run_runner(*self.base_args("--confirm-danger"), expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)


class ClaimToken(RunnerCase):
    """Authorisation is a one-time capability, never a field of the record."""

    def make_record(self, **overrides):
        jobs = self.ws / STATE_DIRNAME / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        record = {
            "jobId": "job_forged", "version": 1, "kind": "review", "status": "running",
            "sandbox": "danger-full-access", "effort": "low", "model": None, "background": True,
            "threadId": None, "workerPid": None, "pgid": None, "claimDigest": None,
            "createdAt": "2026-01-01T00:00:00Z", "startedAt": None, "endedAt": None,
            "updatedAt": "2026-01-01T00:00:00Z", "heartbeatAt": None, "timeoutMs": 5000,
            "exitCode": None, "rawOutput": None, "error": None, "tokens": None,
        }
        record.update(overrides)
        (jobs / f"{record['jobId']}.json").write_text(json.dumps(record))
        return record

    def test_worker_without_token_refuses_to_spawn(self):
        self.make_record()
        completed = self.run_runner("--__worker", "job_forged", "--", "p", expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.probe.exists(), "a worker without a valid token must spawn nothing")

    def test_worker_with_wrong_token_refuses_to_spawn(self):
        self.make_record(claimDigest="0" * 64)
        completed = self.run_runner("--__worker", "job_forged", "--__claim", "not-the-token",
                                    "--", "p", expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(self.probe.exists())

    def test_claim_token_is_single_use(self):
        """The digest is consumed at claim, so a replayed command line cannot re-claim."""
        parsed = self.result_line(self.run_runner(*self.base_args("--background")))
        record = self.wait_for_terminal(parsed["jobId"])
        self.assertIsNone(record["claimDigest"], "the digest must be consumed by the claim")


class ResumeGate(RunnerCase):

    def test_resume_into_danger_requires_confirmation(self):
        """Inheriting a confirmed sandbox is not inheriting the confirmation."""
        (self.ws / ".vibe-suite.md").write_text("---\nsandbox: danger-full-access\n---\n")
        first = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--confirm-danger",
            "--timeout-ms", "10000", "--", "first"))
        self.assertEqual(first["status"], "completed")

        completed = self.run_runner("--kind", "review", "--effort", "low", "--timeout-ms", "10000",
                                    "--resume", first["jobId"], "--", "follow-up", expect_ok=False)
        self.assertNotEqual(completed.returncode, 0,
                            "resuming into danger-full-access must re-require --confirm-danger")


class Timeouts(RunnerCase):

    def test_timeout_zero_and_negative_rejected(self):
        for bad in ("0", "-1", "abc"):
            completed = self.run_runner("--kind", "review", "--effort", "low",
                                        "--sandbox", "read-only", "--timeout-ms", bad,
                                        "--", "p", expect_ok=False)
            self.assertNotEqual(completed.returncode, 0, f"--timeout-ms {bad} must be rejected")

    def test_timeout_omitted_uses_documented_default(self):
        parsed = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "read-only", "--", "p"))
        self.assertEqual(self.job_record(parsed["jobId"])["timeoutMs"], 600000)


class WaitFlag(RunnerCase):

    def test_wait_flag_accepted(self):
        parsed = self.result_line(self.run_runner(*self.base_args("--wait")))
        self.assertEqual(parsed["status"], "completed")

    def test_wait_with_background_rejected_with_conflict_diagnostic(self):
        """Round-1 code already exited non-zero here as `unknown option` — that proved nothing."""
        completed = self.run_runner(*self.base_args("--wait", "--background"), expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("mutually exclusive", completed.stderr)


class RecordSchema(RunnerCase):

    def test_foreground_pgid_is_null(self):
        """`pgid` non-null iff background: foreground would otherwise name the shell's group."""
        parsed = self.result_line(self.run_runner(*self.base_args()))
        self.assertIsNone(self.job_record(parsed["jobId"])["pgid"])

    def test_record_declares_every_field(self):
        parsed = self.result_line(self.run_runner(*self.base_args()))
        record = self.job_record(parsed["jobId"])
        for field in ("jobId", "version", "kind", "status", "sandbox", "effort", "model",
                      "background", "threadId", "workerPid", "pgid", "claimDigest", "createdAt",
                      "startedAt", "endedAt", "updatedAt", "heartbeatAt", "timeoutMs", "exitCode",
                      "rawOutput", "error", "tokens",
                      # vibe-46: declared at creation, so a running record and an early terminal
                      # failure satisfy the same schema as a completed one.
                      "verdictText", "verdictState", "errorClass"):
            self.assertIn(field, record, f"record must always declare {field}")

    def test_background_record_carries_worker_handle(self):
        parsed = self.result_line(self.run_runner(*self.base_args("--background")))
        record = self.wait_for_terminal(parsed["jobId"])
        self.assertIsInstance(record["workerPid"], int)
        self.assertIsInstance(record["pgid"], int)
        self.assertIsNotNone(record["heartbeatAt"], "heartbeatAt is set at claim, not first beat")


class ErrorBoundary(RunnerCase):

    def test_foreground_spawn_failure_finalises_and_emits(self):
        """A bad binary must still finalise the record AND print the five-key line."""
        env = dict(os.environ)
        env["VIBE_SUITE_CODEX_BIN"] = str(self.ws / "does-not-exist")
        completed = subprocess.run(
            ["node", str(RUNNER), *self.base_args()],
            cwd=self.ws, env=env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(completed.returncode, 0)
        parsed = self.result_line(completed)
        self.assertEqual(set(parsed), RESULT_KEYS)
        self.assertEqual(parsed["status"], "failed")
        self.assertEqual(self.job_record(parsed["jobId"])["status"], "failed")


class Namespace(unittest.TestCase):

    def test_commands_are_fully_qualified(self):
        source = (REPO_ROOT / "scripts" / "codex-runner.mjs").read_text(encoding="utf-8")
        for bare in (" :jobs", " :continue", " :bug-analyze", " :delegate"):
            self.assertNotIn(bare, source,
                             f"command names must be fully qualified (/vibe-suite{bare.strip()})")


if __name__ == "__main__":
    unittest.main()


class LifecycleRaces(RunnerCase):
    """Forced with file latches, not elapsed time (F-C / F-E).

    Round 1's race coverage was hope-based. These tests release each phase explicitly, so the
    interleaving under test is a fact rather than a scheduling accident.
    """

    def setUp(self):
        super().setUp()
        self.latch = self.ws / "latches"
        self.latch.mkdir()

    def run_latched(self, *args, fixture="emitter.mjs", timeout=60):
        self._spawned_fixtures.append(fixture)
        env = dict(os.environ)
        env["VIBE_SUITE_CODEX_BIN"] = str(FIXTURES / fixture)
        env["VIBE_TEST_PROBE"] = str(self.probe)
        env["VIBE_TEST_PID_FILE"] = str(self.ws / "grandchild.pid")
        env["VIBE_SUITE_TEST_LATCH_DIR"] = str(self.latch)
        return subprocess.Popen(
            ["node", str(RUNNER), *args], cwd=self.ws, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def wait_signal(self, name, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if (self.latch / f"{name}.signal").exists():
                return True
            time.sleep(0.02)
        raise AssertionError(f"latch '{name}' was never signalled")

    def release(self, name):
        (self.latch / f"{name}.release").write_text("1")

    def test_killed_worker_is_never_acknowledged_as_running(self):
        """A record we killed must not be reported live, whatever the digest says."""
        proc = self.run_latched(*self.base_args("--background"), fixture="sleeper.mjs")
        self.wait_signal("pre-claim")
        self.wait_signal("final-poll", timeout=40)
        self.release("pre-claim")
        self.wait_signal("post-claim")
        self.release("pre-kill")
        self.release("pre-ack")
        stdout, _ = proc.communicate(timeout=60)

        parsed = json.loads([l for l in stdout.splitlines() if l.strip()][0])
        record = self.job_record(parsed["jobId"])
        self.assertIn(record["status"], {"completed", "failed", "timed_out", "cancelled"})
        if parsed["status"] == "running":
            self.assertNotEqual(record["status"], "running",
                                "a running receipt is only legitimate once the record is settled")

    def test_worker_blocks_at_pre_claim_until_released(self):
        """The pre-claim latch is what makes every other race in this class deterministic."""
        proc = self.run_latched(*self.base_args("--background"))
        self.wait_signal("pre-claim")
        # The worker is parked before claiming; the record must still be unclaimed.
        jobs = list((self.ws / STATE_DIRNAME / "jobs").glob("job_*.json"))
        self.assertEqual(len(jobs), 1)
        self.assertIsNone(json.loads(jobs[0].read_text())["workerPid"],
                          "the worker must not claim before the latch is released")
        self.release("pre-claim")
        self.release("pre-kill")
        self.release("pre-ack")
        proc.communicate(timeout=60)

    def test_contested_claim_never_leaves_the_record_running(self):
        """Finding 1 of the round-4 review: a worker killed just after claiming must not strand it.

        The ordering is the whole point. The worker is held at `pre-claim` until the launcher's
        handshake has provably given up (`final-poll`), so the claim lands *inside* the contested
        window — between the last unclaimed observation and the kill — rather than wherever the
        scheduler happened to put it.
        """
        proc = self.run_latched(*self.base_args("--background"), fixture="sleeper.mjs")
        self.wait_signal("pre-claim")
        self.wait_signal("final-poll", timeout=40)   # the launcher gave up: record still unclaimed
        self.release("pre-claim")                    # NOW let the claim land — the contested window
        self.wait_signal("post-claim")               # rendezvous: the claim is provably committed
        self.release("pre-kill")                     # only now may the launcher kill
        self.release("pre-ack")
        stdout, _ = proc.communicate(timeout=60)

        lines = [line for line in stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, "exactly one result line in every outcome")
        parsed = json.loads(lines[0])
        self.assertEqual(set(parsed), RESULT_KEYS)

        record = self.job_record(parsed["jobId"])
        self.assertIn(record["status"], {"completed", "failed", "timed_out", "cancelled"},
                      "a killed worker must never leave the record running forever")

    def test_grandchild_does_not_outlive_a_failed_handshake(self):
        """The kill must reach the process group, or the spawned Codex process orphans."""
        proc = self.run_latched(*self.base_args("--background"), fixture="sleeper.mjs")
        self.wait_signal("pre-claim")
        self.wait_signal("final-poll", timeout=40)
        self.release("pre-claim")
        self.wait_signal("post-claim")
        self.wait_signal("post-child-spawn")
        # `post-child-spawn` fires at spawn; the fixture needs a moment to boot and announce its pid.
        # Waiting for that pid BEFORE releasing the kill is what makes "a grandchild provably existed
        # before the kill" true rather than hoped for.
        pid_file = self.ws / "grandchild.pid"
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not pid_file.exists():
            time.sleep(0.02)
        self.assertTrue(pid_file.exists(), "the fixture (grandchild) must have started")
        grandchild = int(pid_file.read_text())

        self.release("pre-kill")
        self.release("pre-ack")
        proc.communicate(timeout=60)

        job = json.loads(next((self.ws / STATE_DIRNAME / "jobs").glob("job_*.json")).read_text())
        self.assertIsNotNone(job["workerPid"], "the worker must have claimed before the kill")

        # Asserting only the worker would pass an implementation that kills the worker and leaves the
        # Codex process orphaned — the exact defect. The fixture announces its own pid the moment it
        # starts, so the grandchild is assertable independently.
        def gone(pid):
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                try:
                    os.kill(pid, 0)
                    time.sleep(0.05)
                except OSError:
                    return True
            return False

        self.assertTrue(gone(job["workerPid"]), "the worker must be reaped")
        self.assertTrue(gone(grandchild),
                        "the Codex grandchild must die with its group, not outlive the failed record")


class OutputCaptureAndQuota(RunnerCase):
    """vibe-46 — the two reviewer-contract rows that had no behavioural coverage.

    The other four were already exercised: `test_stdin_is_devnull` (Dispatch), the `read-only` argv
    assertion (Read-only guard), `turn.failed`-with-exit-0 plus `tests/node/events.test.mjs`
    (Token accounting), and `tests/node/preflight-probe.test.mjs` (Pre-flight). Nothing here restates
    them.
    """

    #: Everything the fixture reads. Cleared on every call, because two runs inside one test would
    #: otherwise inherit each other's mode — which is how the reject case first came back as `quota`.
    FIXTURE_ENV = ("VIBE_TEST_VERDICT_FILE", "VIBE_TEST_QUOTA", "VIBE_TEST_REJECT",
                   "VIBE_TEST_QUOTA_MESSAGE", "VIBE_TEST_QUOTA_CODE",
                   "VIBE_TEST_VERDICT_TEXT", "VIBE_TEST_BARRIER")

    def run_with(self, **env):
        for key in self.FIXTURE_ENV:
            os.environ.pop(key, None)
        os.environ.update({k: str(v) for k, v in env.items()})
        self.addCleanup(lambda: [os.environ.pop(k, None) for k in self.FIXTURE_ENV])
        return self.run_runner(*self.base_args(), fixture="verdict-writer.mjs",
                               expect_ok=not (env.get("VIBE_TEST_QUOTA") or env.get("VIBE_TEST_REJECT")))

    def test_the_runner_asks_for_no_result_file(self):
        """vibe-137: the verdict travels in the mandatory stream, so `-o` is not passed at all.

        A second channel for one field bought redundancy the stream already guards — without a
        completed-turn event you know not to trust it — and cost two sources of truth that nothing
        reconciled.
        """
        self.run_with()
        self.assertNotIn("-o", self.read_probe()["argv"])

    def test_a_verdict_in_the_stream_is_present(self):
        parsed = self.result_line(self.run_with())
        self.assertEqual(parsed["verdictState"], "present")
        self.assertEqual(self.job_record(parsed["jobId"])["verdictText"], "verdict: approve")

    def test_an_empty_message_is_distinguishable_from_no_message(self):
        """The obligation is unchanged by where the verdict comes from: 'a run that produced none is
        distinguishable from one that produced an empty one.'"""
        empty = self.result_line(self.run_with(VIBE_TEST_VERDICT_FILE="empty"))
        absent = self.result_line(self.run_with(VIBE_TEST_VERDICT_FILE="absent"))
        self.assertEqual(empty["verdictState"], "empty")
        self.assertEqual(absent["verdictState"], "absent")
        self.assertIsNotNone(self.job_record(empty["jobId"])["verdictText"])
        self.assertIsNone(self.job_record(absent["jobId"])["verdictText"])

    def test_the_verdict_text_is_on_the_record_not_the_result_line(self):
        """`verdictText` stays off the line because `rawOutput` already carries the event it came
        from — duplication, not size."""
        parsed = self.result_line(self.run_with())
        self.assertNotIn("verdictText", parsed)
        self.assertIn("verdictState", parsed)

    def test_no_result_file_is_written_anywhere_under_the_workspace(self):
        """The machinery is gone, not merely unused: no path to derive, no cleanup to own, and no two
        jobs able to collide over one file."""
        parsed = self.result_line(self.run_with())
        strays = list(self.ws.rglob("*.result"))
        self.assertEqual(strays, [], f"result files survive: {strays}")
        self.assertEqual(parsed["verdictState"], "present")

    QUOTA_VARIANTS = (
        "You have exceeded your usage limit.",
        "rate_limit_exceeded: slow down",
        "Resource exhausted, try later",
        "429 too many requests",
        "You are out of credits",
    )

    NOT_QUOTA = (
        "The model declined to produce a review.",
        "The review found the change unacceptable.",
        "invalid_request_error: prompt too long",
    )

    def test_quota_variants_are_all_classified_as_quota(self):
        """One handcrafted phrase is one phrase. The table is the point — a new wording is a data
        change, not a regex edit."""
        for message in self.QUOTA_VARIANTS:
            with self.subTest(message=message):
                self.setUp()
                parsed = self.result_line(
                    self.run_with(VIBE_TEST_QUOTA="1", VIBE_TEST_QUOTA_MESSAGE=message))
                self.assertEqual(self.job_record(parsed["jobId"])["errorClass"], "quota")

    def test_quota_adjacent_failures_are_not_quota(self):
        """The negative half. A classifier that says quota to everything separates nothing."""
        for message in self.NOT_QUOTA:
            with self.subTest(message=message):
                self.setUp()
                parsed = self.result_line(
                    self.run_with(VIBE_TEST_QUOTA="1", VIBE_TEST_QUOTA_MESSAGE=message))
                self.assertEqual(self.job_record(parsed["jobId"])["errorClass"], "failure")

    def test_a_structured_quota_code_classifies_without_the_message(self):
        """The structured path must be reachable, not decorative.

        It was: `readEventStream` discarded the error's `code`/`type`, so the code branch could never
        fire. The message here is deliberately *not* quota-shaped, so only the code can classify it.
        """
        parsed = self.result_line(self.run_with(
            VIBE_TEST_QUOTA="1", VIBE_TEST_QUOTA_CODE="insufficient_quota",
            VIBE_TEST_QUOTA_MESSAGE="the request could not be completed"))
        self.assertEqual(self.job_record(parsed["jobId"])["errorClass"], "quota")

    def test_a_structured_non_quota_code_stays_a_failure(self):
        parsed = self.result_line(self.run_with(
            VIBE_TEST_QUOTA="1", VIBE_TEST_QUOTA_CODE="invalid_request_error",
            VIBE_TEST_QUOTA_MESSAGE="the prompt was malformed"))
        self.assertEqual(self.job_record(parsed["jobId"])["errorClass"], "failure")
