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

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmpdirs import TempDirMixin  # noqa: E402

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
        """(ok, pgid -> non-zombie member pids), via ps (portable to macOS and ubuntu
        CI). A zombie cannot write and counts as quiescent; per-pid kill(pid, 0) would
        both miss unrecorded descendants and wait on corpses. A failed, timed-out, or
        empty ps is reported as ok=False — the caller must treat that snapshot as
        unknown, never as absence."""
        try:
            out = subprocess.run(["ps", "-A", "-o", "pid=,pgid=,stat="],
                                 capture_output=True, text=True, timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            return False, {}
        if out.returncode != 0 or not out.stdout.strip():
            return False, {}
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
        return True, live

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
        # Authoritative record per job: canonical <jobId>.json and CAS slots
        # <jobId>.v<N>.json both match the glob; the highest committed version wins,
        # so a stale running slot beneath a newer terminal record is never signalled.
        slot_re = re.compile(r"(job_[A-Za-z0-9_-]+?)(?:\.v(\d+))?\.json")
        by_job = {}
        for rec in (jobs_dir.glob("job_*.json") if jobs_dir.is_dir() else []):
            m = slot_re.fullmatch(rec.name)
            if not m:
                continue
            try:
                data = json.loads(rec.read_text())
            except (ValueError, OSError):
                continue  # never convert a test failure into the reaper's own
            if data.get("jobId") != m.group(1) or not isinstance(data.get("version"), int):
                continue
            best = by_job.get(m.group(1))
            if best is None or data["version"] > best["version"]:
                by_job[m.group(1)] = data
        active = set()
        for data in by_job.values():
            pid, pgid = data.get("workerPid"), data.get("pgid")
            if (data.get("status") == "running" and isinstance(pid, int)
                    and isinstance(pgid, int) and pgid == pid and pgid > 1
                    and pgid != harness_pgid):
                active.add(pgid)
        if not active:
            return
        deadline = time.monotonic() + 15.0

        def live_now():
            """A dict of live members, or None when no valid snapshot was obtained —
            unknown never mutates `active` and is never treated as absence."""
            ok, members = self._group_members(active)
            if not ok:
                return None
            active.intersection_update(members)   # absent once -> dropped permanently
            return members

        def settled_snapshot():
            """A valid snapshot, retried within the deadline; monitoring failure is loud."""
            while True:
                members = live_now()
                if members is not None:
                    return members
                if time.monotonic() >= deadline:
                    raise AssertionError(
                        "vibe-129 reaper: ps never produced a valid snapshot within "
                        "the teardown deadline — process liveness is unknown")
                time.sleep(0.1)

        # Phase 1 — drain: emitter workers finish on their own.
        drain_until = min(time.monotonic() + 2.0, deadline)
        while time.monotonic() < drain_until:
            members = live_now()
            if members == {}:
                break
            time.sleep(0.05)
        survivors = settled_snapshot()
        hung_nonsleeper = False
        if survivors:
            # The exemption is per-workspace-pure-sleeper, not any-sleeper-anywhere:
            # a hung emitter beside a sleeper invocation must still be reported.
            pure_sleeper = bool(spawned_fixtures) and set(spawned_fixtures) == {"sleeper.mjs"}
            hung_nonsleeper = not pure_sleeper
            # Phase 2 — escalate: TERM, brief grace, then KILL (sleeper ignores TERM;
            # the group covers the unrecorded grandchild).
            self._signal_groups(survivors, signal.SIGTERM)
            grace_until = min(time.monotonic() + 1.0, deadline)
            while time.monotonic() < grace_until:
                members = live_now()
                if members == {}:
                    break
                time.sleep(0.05)
            remaining = settled_snapshot()
            if remaining:
                self._signal_groups(remaining, signal.SIGKILL)
        # Phase 3 — verify: no non-zombie member of any collected group remains.
        while True:
            members = settled_snapshot()
            if members == {}:
                break
            if time.monotonic() >= deadline:
                raise AssertionError(
                    f"workspace writers survived teardown: {sorted(members)}")
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

    def test_skip_git_repo_check_only_for_read_only_on_exec_and_resume(self):
        """vibe-193 / grill S7: codex's own non-repository check stays armed for any sandbox that can
        write — on a fresh exec and on a resume, whose effective sandbox is the record's."""
        for sandbox in ("read-only", "workspace-write", "danger-full-access"):
            with self.subTest(sandbox=sandbox, mode="exec"):
                self.setUp()
                confirm = ["--confirm-danger"] if sandbox == "danger-full-access" else []
                first = self.result_line(self.run_runner(
                    "--kind", "review", "--effort", "low", "--sandbox", sandbox, *confirm,
                    "--timeout-ms", "10000", "--", "p"))
                argv = self.read_probe()["argv"]
                self.assertEqual("--skip-git-repo-check" in argv, sandbox == "read-only", argv)
            with self.subTest(sandbox=sandbox, mode="resume"):
                self.probe.unlink()
                self.run_runner("--kind", "review", "--effort", "low", *confirm,
                                "--timeout-ms", "10000", "--resume", first["jobId"], "--", "again")
                argv = self.read_probe()["argv"]
                self.assertIn("resume", argv)
                self.assertEqual("--skip-git-repo-check" in argv, sandbox == "read-only", argv)

    def test_the_prompt_follows_a_double_dash_for_exec_and_resume(self):
        """vibe-193: `--` ends codex's option parsing — a prompt that begins with `-` is a prompt."""
        first = self.result_line(self.run_runner(*self.base_args()))
        argv = self.read_probe()["argv"]
        self.assertEqual(argv[-2:], ["--", "fixture prompt"], argv)
        self.probe.unlink()                      # same workspace: the resume needs the first record
        self.run_runner("--kind", "review", "--effort", "low", "--timeout-ms", "10000",
                        "--resume", first["jobId"], "--", "follow-up")
        argv = self.read_probe()["argv"]
        self.assertIn("resume", argv)
        self.assertEqual(argv[-2:], ["--", "follow-up"], argv)

    def test_effort_outside_the_allow_list_is_refused_and_each_allowed_value_passes(self):
        """vibe-193: `-c reasoning.effort=` takes a free string; the runner allow-lists it."""
        completed = self.run_runner("--kind", "review", "--effort", "bogus", "--sandbox", "read-only",
                                    "--timeout-ms", "10000", "--", "p", expect_ok=False)
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        self.assertIn("--effort expects one of", completed.stderr)
        self.assertFalse(self.probe.exists(), "a refused effort must spawn nothing")
        for effort in ("low", "medium", "high"):
            with self.subTest(effort=effort):
                self.setUp()
                self.run_runner("--kind", "review", "--effort", effort, "--sandbox", "read-only",
                                "--timeout-ms", "10000", "--", "p")
                self.assertIn(f"reasoning.effort={effort}", self.read_probe()["argv"])

    def test_an_effort_from_project_config_outside_the_vocabulary_spawns_nothing(self):
        """A CONFIGURED effort is refused by config.py's own enum before the runner's gate; either
        door refusing means nothing is spawned (declared: config.py's refusal is the one observed)."""
        (self.ws / ".vibe-suite.md").write_text("---\neffort: bogus\n---\n")
        completed = self.run_runner("--kind", "review", "--sandbox", "read-only",
                                    "--timeout-ms", "10000", "--", "p", expect_ok=False)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("effort", completed.stderr)
        self.assertFalse(self.probe.exists(), "an unknown effort must spawn nothing")

    def test_a_resumed_record_carrying_an_out_of_vocabulary_effort_is_refused(self):
        """vibe-193: a record written by an earlier build carries whatever --effort it was given; the
        resume path inherits it, so the gate must read the EFFECTIVE effort, not just the flag."""
        jobs = self.ws / STATE_DIRNAME / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        prior = {
            "jobId": "job_prior0000000000000", "version": 1, "kind": "review", "status": "completed",
            "sandbox": "read-only", "effort": "xhigh", "model": None, "background": False,
            "threadId": "thread_fixture_0001", "workerPid": None, "pgid": None, "claimDigest": None,
            "createdAt": "2026-01-01T00:00:00Z", "startedAt": "2026-01-01T00:00:00Z",
            "endedAt": "2026-01-01T00:00:01Z", "updatedAt": "2026-01-01T00:00:01Z",
            "heartbeatAt": None, "timeoutMs": 5000, "exitCode": 0, "rawOutput": "", "error": None,
            "tokens": None, "verdictText": None, "verdictState": "absent", "errorClass": None,
        }
        (jobs / f"{prior['jobId']}.json").write_text(json.dumps(prior))
        before = sorted(p.name for p in jobs.iterdir())
        completed = self.run_runner("--kind", "review", "--timeout-ms", "10000",
                                    "--resume", prior["jobId"], "--", "again", expect_ok=False)
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        self.assertIn("resolved effort 'xhigh'", completed.stderr)
        self.assertFalse(self.probe.exists(), "a refused resume must spawn nothing")
        self.assertEqual(sorted(p.name for p in jobs.iterdir()), before,
                         "a refused resume must create no execution record")

    def test_the_runner_effort_vocabulary_equals_config_py_s_enum(self):
        """One vocabulary at both doors (vibe-193): the runner's allow-list is config.py's enum."""
        runner = RUNNER.read_text(encoding="utf-8")
        match = re.search(r'const EFFORTS = new Set\(\[([^\]]*)\]\);', runner)
        self.assertIsNotNone(match, "the runner must declare its EFFORTS allow-list")
        runner_values = sorted(v.strip().strip('"') for v in match.group(1).split(","))
        config_py = (REPO_ROOT / "scripts" / "lib" / "config.py").read_text(encoding="utf-8")
        enum = re.search(r'"effort":\s*Row\("enum",\s*"([^"]+)"', config_py)
        self.assertIsNotNone(enum, "config.py must declare the effort enum")
        self.assertEqual(runner_values, sorted(enum.group(1).split("|")))

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


class PreRecordFailures(RunnerCase):
    """vibe-180 / grill M7. `prepareRecord` — the step that shells out to `python3 config.py` and
    creates the job record — ran OUTSIDE the guard that promises the one-line JSON result, so a
    missing `python3`, an invalid `.vibe-suite.md` or an unwritable state directory produced a raw
    stack on stderr and NO result line. Consumers branch on the line's `status`; an absent line is
    an unspecified state for them. A failure before any record exists still owes them the line:
    `status: failed`, `jobId: null`, the reason on stderr."""

    def _assert_failed_line_without_a_record(self, completed):
        self.assertEqual(completed.returncode, 1,
                         "a contract failure exits 1 (a failed job's code) — not 0, and not the usage-error 2")
        parsed = self.result_line(completed)
        self.assertEqual(set(parsed), RESULT_KEYS)
        self.assertEqual(parsed["status"], "failed")
        self.assertIsNone(parsed["jobId"], "no record exists for a pre-record failure")
        self.assertNotIn("\n    at ", completed.stderr, "a raw stack reached stderr")
        self.assertIn("codex-runner:", completed.stderr, "the reason must reach stderr")
        return parsed

    def test_missing_python3_still_emits_the_failed_result_line(self):
        """PATH holds `node` and nothing else, so `config-bridge.loadConfig` cannot spawn `python3`."""
        bin_dir = self.ws / "only-node-bin"
        bin_dir.mkdir()
        node = shutil.which("node")
        self.assertIsNotNone(node, "node must be on PATH for the runner to exist at all")
        (bin_dir / "node").symlink_to(node)
        env = dict(os.environ)
        env["PATH"] = str(bin_dir)
        env["VIBE_SUITE_CODEX_BIN"] = str(FIXTURES / "emitter.mjs")
        env["VIBE_TEST_PROBE"] = str(self.probe)
        completed = subprocess.run(
            ["node", str(RUNNER), *self.base_args()],
            cwd=self.ws, env=env, capture_output=True, text=True, timeout=30,
        )
        self._assert_failed_line_without_a_record(completed)
        self.assertIn("python3", completed.stderr)
        self.assertFalse(self.probe.exists(), "the engine was spawned without a record")

    def test_broken_config_still_emits_the_failed_result_line(self):
        """An unterminated frontmatter makes `config.py` exit 1, which `loadConfig` raises as
        `ConfigBridgeError` — a contract-level failure, not a crash."""
        (self.ws / ".vibe-suite.md").write_text("---\nsandbox: read-only\n", encoding="utf-8")
        completed = self.run_runner(*self.base_args(), expect_ok=False)
        self._assert_failed_line_without_a_record(completed)
        self.assertIn("config", completed.stderr.lower())
        self.assertFalse(self.probe.exists(), "the engine was spawned without a record")

    def test_background_broken_config_still_emits_the_failed_result_line(self):
        """The background launcher calls `prepareRecord` too; its failure owes the same line."""
        (self.ws / ".vibe-suite.md").write_text("---\nsandbox: read-only\n", encoding="utf-8")
        completed = self.run_runner(*self.base_args("--background"), expect_ok=False)
        self._assert_failed_line_without_a_record(completed)

    def test_a_usage_error_raised_inside_prepare_record_still_exits_2_without_a_result_line(self):
        """The guard must not swallow usage errors into `failed` lines. This one is raised INSIDE
        `prepareRecord` — `assertSandboxAllowed` refuses a config that resolves to
        `danger-full-access` without `--confirm-danger` — so it crosses the new guard and must be
        rethrown: exit 2, nothing on stdout, the `codex-runner:` diagnostic on stderr."""
        (self.ws / ".vibe-suite.md").write_text("---\nsandbox: danger-full-access\n---\n\n# config\n")
        completed = self.run_runner("--kind", "review", "--effort", "low",
                                    "--timeout-ms", "5000", "--", "p", expect_ok=False)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual([l for l in completed.stdout.splitlines() if l.strip()], [])
        self.assertIn("codex-runner:", completed.stderr)
        self.assertFalse(self.probe.exists(), "nothing may be spawned when confirmation is missing")


class LeakedPipes(RunnerCase):
    """vibe-181 / grill H6. `runWithDeadline` settled on `close`, which Node fires only after the
    process exits AND every stdio pipe is released. A Codex child that leaked its pipes to a
    grandchild therefore never settled: the deadline's verdict was never recorded and — because the
    heartbeat interval was cleared only at settle — a background job kept heartbeating forever,
    so `isAbandoned` called it healthy and `--settle-abandoned` could not settle it. The leaker
    fixture spawns exactly that grandchild (pid in the probe, so the test reaps it) and dies on the
    deadline's SIGTERM; the job must end `timed_out` within `graceMs` of that, with the leak recorded.
    """

    def _reap_grandchild(self):
        """Test-owned cleanup with survivor verification. The vibe-129 reaper signals only
        `running` records' worker groups; once the job is terminal, a descendant that survives is
        invisible to it — so the test that planted the grandchild kills it and proves it gone."""
        pid = self.read_probe().get("grandchild")
        self.assertIsInstance(pid, int, "the leaker fixture must record its grandchild's pid")
        try:
            os.kill(pid, 9)
        except ProcessLookupError:
            pass
        self._assert_pid_gone(pid, "the grandchild")

    def _assert_pid_gone(self, pid, what, timeout=5.0):
        """Gone means ESRCH. A zombie is transient (its parent is exiting, or init reaps it); keep
        polling until the pid no longer exists, and fail — never shrug — if it still does."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            try:
                os.waitpid(pid, os.WNOHANG)   # reaps it if it is ours (it usually is not)
            except ChildProcessError:
                pass
            time.sleep(0.05)
        stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        self.fail(f"{what} {pid} still exists after {timeout}s (ps stat {stat!r})")

    def test_a_timed_out_background_job_whose_engine_leaked_a_pipe_ends_timed_out_and_stops_heartbeating(self):
        previous = os.environ.get("VIBE_SUITE_HEARTBEAT_MS")
        os.environ["VIBE_SUITE_HEARTBEAT_MS"] = "50"
        self.addCleanup(lambda: os.environ.pop("VIBE_SUITE_HEARTBEAT_MS", None)
                        if previous is None else os.environ.__setitem__("VIBE_SUITE_HEARTBEAT_MS", previous))
        started = time.monotonic()
        parsed = self.result_line(self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "read-only",
            "--timeout-ms", "600", "--background", "--", "p", fixture="leaker.mjs"))
        self.assertEqual(parsed["status"], "running", "the launcher acknowledges before the deadline")
        try:
            record = self.wait_for_terminal(parsed["jobId"], timeout=20)
            elapsed = time.monotonic() - started
            self.assertEqual(record["status"], "timed_out")
            self.assertIs(record.get("pipesLeaked"), True, "the leak must be recorded on the job")
            self.assertIsNotNone(record["endedAt"])
            # SIGTERM at 600 ms + the default 2 s drain; the grandchild holds for 10 s — settling
            # anywhere near that is the defect. A ceiling, not a window (deadline tests flake on lows).
            self.assertLess(elapsed, 8, f"the job settled only when the grandchild released the pipes ({elapsed:.1f}s)")
            # The heartbeat oracle that actually proves cessation: the detached worker must EXIT —
            # with the pipes still held by the grandchild, only a settled promise (interval cleared,
            # read ends destroyed) lets its event loop drain. An unchanged `heartbeatAt` alone would
            # not do: `transact` rejects late writes to a terminal record regardless.
            self.assertIsInstance(record["workerPid"], int)
            self._assert_pid_gone(record["workerPid"], "the background worker", timeout=10.0)
            first = record["heartbeatAt"]
            time.sleep(0.4)          # 8 intervals at 50 ms — belt and braces on top of the worker exit
            self.assertEqual(self.job_record(parsed["jobId"])["heartbeatAt"], first,
                             "the heartbeat kept beating after the job was finalised")
        finally:
            self._reap_grandchild()

    def test_a_foreground_job_records_released_pipes_when_nothing_leaks(self):
        parsed = self.result_line(self.run_runner(*self.base_args()))
        self.assertIs(self.job_record(parsed["jobId"]).get("pipesLeaked"), False)



class StderrDiagnostics(RunnerCase):
    """vibe-182 / grill H7: what the record keeps when the engine explains itself on stderr.

    A rejected flag, a login failure before any JSON, a crash — the only diagnostic is on stderr and
    there is no terminal event. Before vibe-182 the record said `error: "no terminal event"` and
    nothing else; the tail, the exit/signal, and the malformed-line count were discarded.
    """

    def test_stderr_and_exit_are_persisted_when_no_terminal_event_arrives(self):
        completed = self.run_runner(*self.base_args(), fixture="stderr-failer.mjs", expect_ok=False)
        parsed = self.result_line(completed)
        self.assertEqual(parsed["status"], "failed")
        record = self.job_record(parsed["jobId"])
        self.assertEqual(record["exitCode"], 2)
        self.assertIsNone(record["signal"], "a natural exit has no signal")
        self.assertEqual(record["malformedLines"], 1, "the non-JSON stdout line is counted, not lost")
        self.assertEqual(
            record["error"],
            "no terminal event (exit 2); stderr: codex: error: unexpected argument '--bogus'",
            "the error names how the engine ended and quotes the first stderr line")
        self.assertIn("codex: error: unexpected argument '--bogus'", record["stderrTail"])
        self.assertIn("tip: run with --help", record["stderrTail"])
        self.assertNotIn(chr(27), record["stderrTail"], "colour codes are stripped before persisting")
        self.assertNotIn("\r", record["stderrTail"], "carriage returns are control bytes: stripped")
        self.assertEqual(record["errorClass"], "failure")
        self.assertEqual(record["rawOutput"], "this line is not JSON\n", "stdout is still kept verbatim")

    def test_a_timed_out_job_records_the_signal_that_ended_the_engine(self):
        completed = self.run_runner(
            "--kind", "review", "--effort", "low", "--sandbox", "read-only",
            "--timeout-ms", "300", "--", "fixture prompt",
            fixture="sleeper.mjs", timeout=30, expect_ok=False)
        parsed = self.result_line(completed)
        record = self.job_record(parsed["jobId"])
        self.assertEqual(record["status"], "timed_out")
        self.assertIn(record["signal"], ("SIGTERM", "SIGKILL"), "the deadline's signal is recorded")
        self.assertIsInstance(record["stderrTail"], str,
                              "once the run settles the tail is a string (possibly empty), not null")

    def test_a_background_worker_gets_a_private_log_sink(self):
        parsed = self.result_line(self.run_runner(*self.base_args("--background")))
        record = self.wait_for_terminal(parsed["jobId"])
        log = self.ws / STATE_DIRNAME / "jobs" / f"{parsed['jobId']}.log"
        self.assertTrue(log.exists(), "the worker's stderr sink is created at launch")
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600,
                         "the worker log is private: stderr can carry credentials")
        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["stderrTail"], "", "the emitter prints nothing to stderr")
        self.assertEqual(record["malformedLines"], 1,
                         "the emitter fixture prints exactly one non-JSON line; the stream count reaches the record")


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

    def test_no_raw_fs_writes(self):
        """vibe-153: the Node write surface routes through scripts/lib/write.mjs.

        The checker is fail-closed by construction — a module is `clean` only if every
        construct it uses is in the accepted dialect — so a new evasion is a refusal, not a
        pass. This is the Node counterpart to tests/test_write_discipline.py.
        """
        checker = REPO_ROOT / "tests" / "node" / "no-raw-fs-writes.mjs"
        self.assertTrue(SHIPPED_MJS, "no shipped .mjs found — this check would pass vacuously")
        result = subprocess.run(["node", str(checker), *[str(p) for p in SHIPPED_MJS]],
                                capture_output=True, text=True, timeout=120, cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        inspected = len([p for p in SHIPPED_MJS
                         if p.relative_to(REPO_ROOT).as_posix() != "scripts/lib/write.mjs"])
        self.assertIn(f"{inspected} module(s) clean", result.stdout,
                      "the checker did not report the full inspected corpus — anti-vacuity")
        self.assertIn(f"({len(SHIPPED_MJS)} given)", result.stdout)

    def test_no_raw_fs_writes_probe_suite(self):
        """The checker's own DIRTY/CLEAN probes, run in CI's test job with everything else."""
        probes = REPO_ROOT / "tests" / "node" / "no-raw-fs-writes.test.mjs"
        result = subprocess.run(["node", "--test", str(probes)],
                                capture_output=True, text=True, timeout=180, cwd=REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_no_raw_fs_writes_catches_a_seeded_violation(self):
        """The gate must fail on a real import+call, not merely on a bare name.

        A seed of only `writeFile(...)` would be a ReferenceError at runtime and could be
        caught by a name grep; seeding the STATIC IMPORT as well is what proves the checker
        is import-aware.
        """
        checker = REPO_ROOT / "tests" / "node" / "no-raw-fs-writes.mjs"
        with tempfile.TemporaryDirectory(prefix="rawfs-seed-") as tmp:
            seeded = Path(tmp) / "seeded.mjs"
            seeded.write_text('import { writeFile } from "node:fs/promises";\n'
                              'await writeFile("p", "x");\n', encoding="utf-8")
            result = subprocess.run(["node", str(checker), str(seeded)],
                                    capture_output=True, text=True, timeout=60, cwd=REPO_ROOT)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("raw-fs-write", result.stdout)

    def test_no_raw_fs_writes_known_list_is_empty(self):
        """KNOWN is a claim surface, not a ratchet: an entry needs a reviewed reason."""
        source = (REPO_ROOT / "tests" / "node" / "no-raw-fs-writes.mjs").read_text(
            encoding="utf-8")
        self.assertIn("export const KNOWN = new Set();", source,
                      "KNOWN gained an entry — that is a new claim, not a ratchet step")

    def test_delegate_documents_the_non_git_fast_failure_as_intended(self):
        """vibe-193 acceptance: a workspace-write delegate outside a git repository fails fast with
        codex's own message — documented, so nobody reads it as a bug."""
        text = (REPO_ROOT / "commands" / "delegate.md").read_text(encoding="utf-8")
        self.assertIn("Not inside a trusted directory", text)
        self.assertIn("--skip-git-repo-check", text)
        self.assertIn("only for\n`read-only`", text.replace("only for `read-only`", "only for\n`read-only`"))

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

    def test_worker_without_a_handoff_flag_refuses_to_spawn_with_the_handoff_diagnostic(self):
        self.make_record(claimDigest="0" * 64)
        completed = self.run_runner("--__worker", "job_forged", expect_ok=False)
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("worker hand-off unreadable for job_forged", completed.stderr)
        self.assertFalse(self.probe.exists())

    def run_worker_with_handoff(self, job_id, payload, fixture="emitter.mjs", handoff_arg=None):
        """vibe-193: a worker takes the claim token and the prompt from an inherited fd (argv names
        the NUMBER); `payload` is the raw text the launcher would write — token, newline, prompt."""
        read_end, write_end = os.pipe()
        os.write(write_end, payload.encode("utf-8"))
        os.close(write_end)
        self._spawned_fixtures.append(fixture)
        env = dict(os.environ)
        env["VIBE_SUITE_CODEX_BIN"] = str(FIXTURES / fixture)
        env["VIBE_TEST_PROBE"] = str(self.probe)
        try:
            return subprocess.run(
                ["node", str(RUNNER), "--__worker", job_id, "--__handoff",
                 str(read_end) if handoff_arg is None else handoff_arg],
                cwd=self.ws, env=env, capture_output=True, text=True, timeout=30,
                pass_fds=(read_end,))
        finally:
            os.close(read_end)

    def test_worker_with_wrong_token_refuses_to_spawn(self):
        self.make_record(claimDigest="0" * 64)
        completed = self.run_worker_with_handoff("job_forged", "not-the-token\np")
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("worker claim refused for job_forged", completed.stderr)
        self.assertFalse(self.probe.exists())

    def test_worker_with_the_right_token_on_the_fd_claims_and_runs_the_piped_prompt(self):
        token = "t" * 64
        self.make_record(claimDigest=hashlib.sha256(token.encode("utf-8")).hexdigest(),
                         sandbox="read-only")
        completed = self.run_worker_with_handoff("job_forged", f"{token}\npiped prompt\nline two")
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        argv = self.read_probe()["argv"]
        self.assertEqual(argv[-2:], ["--", "piped prompt\nline two"],
                         "the prompt came down the pipe, whole, after `--`")
        record = self.wait_for_terminal("job_forged")
        self.assertEqual(record["status"], "completed")
        self.assertIsNone(record["claimDigest"], "consumed at claim")

    def test_a_handoff_fd_that_is_not_a_number_or_not_readable_refuses_to_spawn(self):
        token = "t" * 64
        for handoff_arg in ("not-a-number", "2", "999"):
            with self.subTest(handoff_arg=handoff_arg):
                self.setUp()
                self.make_record(claimDigest=hashlib.sha256(token.encode("utf-8")).hexdigest())
                completed = self.run_worker_with_handoff("job_forged", f"{token}\np",
                                                         handoff_arg=handoff_arg)
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertIn("worker hand-off unreadable for job_forged", completed.stderr)
                self.assertFalse(self.probe.exists(), "a broken hand-off must spawn nothing")

    def test_a_handoff_without_a_newline_or_with_an_empty_token_refuses_to_spawn(self):
        token = "t" * 64
        for payload in (token, "\np", ""):
            with self.subTest(payload=payload[:8]):
                self.setUp()
                self.make_record(claimDigest=hashlib.sha256(token.encode("utf-8")).hexdigest())
                completed = self.run_worker_with_handoff("job_forged", payload)
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertIn("worker hand-off unreadable for job_forged", completed.stderr)
                self.assertFalse(self.probe.exists(), "a malformed hand-off must spawn nothing")

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
                      "verdictText", "verdictState", "errorClass",
                      # vibe-181: null until the run settles; whether the engine's stdio pipes were
                      # still held open past its exit.
                      "pipesLeaked",
                      # vibe-182: the engine's stderr tail, the signal that ended it, and the
                      # malformed event-line count — null until the run settles.
                      "stderrTail", "signal", "malformedLines"):
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


class ReaperContract(TempDirMixin, RunnerCase):
    """Step-8 regressions for the vibe-129 reaper itself: authoritative-version
    resolution, and the pure-sleeper-only masking exemption. Each test fabricates a
    separate workspace and drives _reap_workspace_writers directly against a real
    detached process group."""

    def _spawn_group(self):
        proc = subprocess.Popen(["sleep", "30"], preexec_fn=os.setsid,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self._end_group, proc)
        return proc

    @staticmethod
    def _end_group(proc):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait(timeout=10)

    def _fab_ws(self, records):
        ws = Path(self.mkdtemp(prefix="reaper-fab-"))
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        jobs = ws / STATE_DIRNAME / "jobs"
        jobs.mkdir(parents=True)
        for name, data in records.items():
            (jobs / name).write_text(json.dumps(data))
        return ws

    def test_historical_running_slot_is_never_signalled(self):
        proc = self._spawn_group()
        base = {"jobId": "job_hist", "workerPid": proc.pid, "pgid": proc.pid}
        ws = self._fab_ws({
            "job_hist.v1.json": {**base, "version": 1, "status": "running"},
            "job_hist.json": {**base, "version": 2, "status": "completed"},
        })
        self._reap_workspace_writers(ws, ["emitter.mjs"])
        self.assertIsNone(proc.poll(),
                          "a stale running slot beneath a terminal record was signalled")

    def test_hung_nonsleeper_is_reported_after_reaping(self):
        proc = self._spawn_group()
        ws = self._fab_ws({"job_hung.json": {"jobId": "job_hung", "version": 1,
                                             "status": "running",
                                             "workerPid": proc.pid, "pgid": proc.pid}})
        with self.assertRaisesRegex(AssertionError, "fixture should terminate"):
            self._reap_workspace_writers(ws, ["emitter.mjs", "sleeper.mjs"])
        self.assertIsNotNone(proc.poll(), "the hygiene reap must still have run")

    def test_pure_sleeper_workspace_is_exempt(self):
        proc = self._spawn_group()
        ws = self._fab_ws({"job_slp.json": {"jobId": "job_slp", "version": 1,
                                            "status": "running",
                                            "workerPid": proc.pid, "pgid": proc.pid}})
        self._reap_workspace_writers(ws, ["sleeper.mjs"])
        self.assertIsNotNone(proc.poll(), "the sleeper group is still reaped for hygiene")


if __name__ == "__main__":
    unittest.main()


class LifecycleRaces(RunnerCase):
    """Forced with file latches, not elapsed time (F-C / F-E).

    Round 1's race coverage was hope-based. These tests release each phase explicitly, so the
    interleaving under test is a fact rather than a scheduling accident.
    """

    def setUp(self):
        super().setUp()
        # vibe-103: the runner writes a latch signal only into an *owned* temp root — an env-supplied
        # path is an operator input, not a licence to write anywhere. The root is obtained FROM the
        # primitive rather than hand-built here: duplicating the marker format in the harness would
        # make this file a second source of truth about what ownership means, and the two copies
        # would drift the first time the format changed.
        made = subprocess.run(
            ["node", "--input-type=module", "-e",
             'const { pathToFileURL } = await import("node:url");'
             ' const { makeOwnedTempDir } = await import(pathToFileURL(process.argv[1]).href);'
             ' process.stdout.write(await makeOwnedTempDir("vibe-latch"));',
             str(REPO_ROOT / "scripts" / "lib" / "write.mjs")],
            capture_output=True, text=True, check=True)
        self.latch = Path(made.stdout.strip())
        self.addCleanup(shutil.rmtree, self.latch, ignore_errors=True)

    def run_latched(self, *args, fixture="emitter.mjs", timeout=60, hold_pre_spawn=False):
        # vibe-182: the launcher pauses at `pre-spawn` (record exists, sink not yet opened) only for
        # the tests that ask; every other latched test has it released before the launch.
        if not hold_pre_spawn:
            self.release("pre-spawn")
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

    def test_the_worker_argv_carries_neither_the_prompt_nor_the_token_and_nothing_is_at_rest(self):
        """vibe-193 / grill S7+S15: `ps` is readable by every local user; the detached worker lives
        for the whole job. Its argv names only the hand-off FD; the prompt and the token travel down
        that pipe and are never written to disk — after the job, no file under the jobs directory
        carries the prompt."""
        marker = "SECRET-PROMPT-MARKER-vibe-193"
        proc = self.run_latched("--kind", "review", "--effort", "low", "--sandbox", "read-only",
                                "--timeout-ms", "10000", "--background", "--", marker)
        try:
            self.wait_signal("pre-claim")
            listing = subprocess.run(["ps", "-axwwo", "pid=,args="], capture_output=True,
                                     text=True, check=True).stdout
            workers = [line for line in listing.splitlines()
                       if "--__worker" in line and str(RUNNER) in line]
            self.assertEqual(len(workers), 1, listing)
            line = workers[0]
            self.assertNotIn(marker, line, "the prompt text must not be on the worker argv")
            self.assertIsNone(re.search(r"[0-9a-f]{64}", line),
                              "no 64-hex token on the worker argv: " + line)
            self.assertIn("--__handoff", line)
            self.assertNotIn("--prompt-file", line, "no prompt file: nothing at rest")
        finally:
            self.release("pre-claim")
            out, _err = proc.communicate(timeout=60)
        parsed = json.loads([line for line in out.splitlines() if line.strip()][-1])
        record = self.wait_for_terminal(parsed["jobId"])
        self.assertEqual(record["status"], "completed", record)
        self.assertIsNone(record["claimDigest"], "the token is consumed at claim")
        self.assertEqual(self.read_probe()["argv"][-2:], ["--", marker],
                         "the engine still receives the prompt, after `--`")
        jobs_dir = self.ws / STATE_DIRNAME / "jobs"
        at_rest = [p.name for p in jobs_dir.iterdir() if p.is_file()
                   and marker.encode("utf-8") in p.read_bytes()]
        self.assertEqual(at_rest, [], "no runner-owned file may carry the prompt after the job")

    def test_a_worker_crash_before_claim_leaves_its_stack_in_the_job_log(self):
        """vibe-182 / grill H7: the worker's stderr was /dev/null, so a pre-claim crash left nothing
        to read. The launcher opens a private per-job log before the spawn; the worker's terminal
        catch writes the stack there.

        The crash is injected through the store: held at `pre-claim`, the canonical record is made
        non-JSON, so the claim's read throws before `runWorker`'s try — exactly the uncaught path.
        The launcher's handshake then gives up, kills the group, and cannot finalise a record that
        does not parse; that is today's behaviour and not what this test is about.
        """
        proc = self.run_latched(*self.base_args("--background"))
        self.wait_signal("pre-claim")
        jobs = list((self.ws / STATE_DIRNAME / "jobs").glob("job_*.json"))
        self.assertEqual(len(jobs), 1)
        job_id = jobs[0].stem
        jobs[0].write_text("not json at all\n")
        self.release("pre-claim")
        self.release("pre-kill")
        self.release("pre-ack")
        proc.communicate(timeout=60)
        log = self.ws / STATE_DIRNAME / "jobs" / f"{job_id}.log"
        self.assertTrue(log.exists(), "the worker log must exist even though the worker died before claiming")
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600, "the worker log is private")
        text = log.read_text()
        self.assertIn("codex-runner:", text, f"the worker's terminal catch writes to the log:\n{text}")
        self.assertIn("    at ", text, f"a stack trace, not just a message:\n{text}")

    def test_a_sink_that_cannot_be_opened_degrades_to_the_old_behaviour_and_says_so(self):
        """vibe-182: a launch is not failed over its diagnostics. Held at `pre-spawn` (after the record
        exists, before the sink is opened), the log path is squatted by a symlink — the audited
        primitive refuses it — so the launcher must say so on stderr, spawn the worker with its stderr
        discarded, and the job must still run to completion under the unchanged result contract.
        """
        proc = self.run_latched(*self.base_args("--background"), hold_pre_spawn=True)
        self.wait_signal("pre-spawn")
        jobs = list((self.ws / STATE_DIRNAME / "jobs").glob("job_*.json"))
        self.assertEqual(len(jobs), 1, "the record exists before the sink is opened")
        job_id = jobs[0].stem
        log = self.ws / STATE_DIRNAME / "jobs" / f"{job_id}.log"
        os.symlink(str(self.ws / "nowhere.log"), log)          # dangling: exists() is false, lstat sees a link
        self.release("pre-spawn")
        self.release("pre-claim")
        self.release("pre-kill")
        self.release("pre-ack")
        stdout, stderr = proc.communicate(timeout=60)
        self.assertIn("worker log unavailable for " + job_id, stderr, f"the degradation is said out loud:\n{stderr}")
        self.assertIn("symlink", stderr, "the reason travels with the warning")
        self.assertIn("stderr is discarded", stderr)
        lines = [line for line in stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, "exactly one result line — the contract is unchanged")
        parsed = json.loads(lines[0])
        self.assertEqual(set(parsed), RESULT_KEYS)
        self.assertEqual(parsed["status"], "running", "the launch receipt is still a launch receipt")
        record = self.wait_for_terminal(parsed["jobId"])
        self.assertEqual(record["status"], "completed", "the worker ran without a log sink")
        self.assertTrue(log.is_symlink(), "the squatting symlink is untouched — never followed, never replaced")
        self.assertFalse(log.exists(), "no log was created behind the symlink")

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
