#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The opt-in real-codex contract probe (vibe-227 / grill M31).

Every other test in this suite drives a **fake** codex. That is what makes them fast and free, and it is also why the
real event vocabulary is unverified: `tests/fixtures/fake-codex/*` emits the shape by hand, so a field renamed upstream
leaves the suite green and breaks production at the next real call.

This module runs the installed binary **once**, opt in, and asserts that the stream still carries what
`scripts/lib/events.mjs` extracts from it. It asserts **through that module**, not through a second parser written
here: "the vocabulary still matches" has to mean "the code this repository ships still finds what it needs".

    VIBE_SUITE_REAL_CODEX=1 python3 -m unittest tests.test_codex_contract.RealCodexContract -v

Without that variable — so in every ordinary run of the suite, and in CI's shards — the live test skips at once and
spends nothing. The weekly job in `.github/workflows/self-check.yml` runs the command above.

**A failure means drift; only a named environmental cause skips.** An absent binary, a quota the repository's own
classifier recognises, an authentication refusal that says so, or a timeout are skips with their reason printed.
Unexplained output is a failure — a stream with no recognised events looks exactly like a renamed vocabulary, so it
cannot be waved through.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import textwrap
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmpdirs import TempDirMixin  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "self-check.yml"

HEALTHY = [
    {"type": "thread.started", "thread_id": "thread_probe_0001"},
    {"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}},
    {"type": "turn.completed", "usage": {"input_tokens": 12, "cached_input_tokens": 4, "output_tokens": 3}},
]


def stream(events, extra_lines=()):
    """A JSONL stream, plus any raw lines to interleave (codex prints diagnostics between events)."""
    lines = [json.dumps(event) for event in events]
    return "\n".join(list(lines) + list(extra_lines)) + "\n"


# ---- the probe ------------------------------------------------------------------------------------------------

EVENTS_MJS = REPO_ROOT / "scripts" / "lib" / "events.mjs"
DISCOVER_PY = REPO_ROOT / "scripts" / "runs_stats" / "discover.py"
SCRIPTS_LIB = REPO_ROOT / "scripts" / "lib"

PROMPT = "Reply with the single word: ok"
DEFAULT_TIMEOUT_MS = 120000
REAP_GRACE_S = 2.0
#: The optional tool vocabulary, checked per type and only when the stream carries it.
TOOL_EVENT_TYPES = ("item.started", "command_execution")

#: An authentication refusal says why. Advice ("codex login") is not a refusal, and `required` is ambiguous, so the
#: negation guard rides on that word alone — "not logged in" and "is not set" are refusals themselves.
AUTH_PATTERNS = (
    r"\bnot logged in\b",
    r"\bauthentication failed\b",
    r"\bunauthorized\b",
    r"\b401\b[^\n]{0,40}\b(unauthorized|forbidden|invalid)\b",
    r"\b(missing|invalid|no)\s+(openai[ _])?api[ _]key\b",
    r"\b(OPENAI_API_KEY|api[ _]key)\b[^\n]{0,24}\b(is\s+)?(missing|invalid|not set|unset)\b",
    r"\b(OPENAI_API_KEY|api[ _]key)\b[^\n]{0,24}\b(is\s+)?(?<!not )(?<!n't )(?<!no longer )required\b",
)


class Verdict:
    """What the probe concluded, and why. `kind` is one of pass, skip, fail."""

    def __init__(self, kind, reason, detail=None):
        self.kind, self.reason, self.detail = kind, reason, detail or {}

    def __repr__(self):
        return f"Verdict({self.kind!r}, {self.reason!r})"


def failure_text(raw):
    """Everything a failed turn said, from the RAW stream.

    `events.mjs` reads `error?.message ?? message ?? "turn.failed"`, so a **string** error — the shape
    `tests/fixtures/fake-codex/preflight-authless.mjs` emits — is discarded by the time the parser is done. The
    authentication decision needs those words, so it reads them here: the string itself, or the object's message,
    code and type, or the event's own top-level message.
    """
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.failed":
            continue
        # The FIRST terminal event decides, as it does in events.mjs ("a stream cannot un-fail"). Reading every
        # failure would let a later authentication refusal excuse an earlier unexplained one.
        said = []
        error = event.get("error")
        if isinstance(error, str):
            said.append(error)
        elif isinstance(error, dict):
            said.extend(str(error.get(key)) for key in ("message", "code", "type") if error.get(key))
        if event.get("message"):
            said.append(str(event["message"]))
        return "\n".join(said)
    return ""


def _reads_like_a_refusal(text):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in AUTH_PATTERNS)


class Expired(Exception):
    """The probe's single deadline ran out. Raised by whichever phase noticed."""


class CleanupUnconfirmed(Exception):
    """A helper overran and its process group could not be confirmed gone. Never a timeout: a timeout is weather,
    an unreaped group is a defect in the probe."""


def _remaining(deadline):
    """Seconds left on the probe's deadline. An exhausted deadline is exhausted — no phase gets a fresh grant."""
    left = deadline - time.monotonic()
    if left <= 0:
        raise Expired()
    return left


def _run_bounded(argv, deadline, group_alive, **kwargs):
    """Run a helper under the probe's deadline, in its own process group, and reap that group if it overruns."""
    _remaining(deadline)                       # nothing is launched on an exhausted budget
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               start_new_session=True, **kwargs)
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        pgid = process.pid
    try:
        out, err = process.communicate(timeout=_remaining(deadline))
    except (subprocess.TimeoutExpired, Expired):
        # Two different outcomes, and the first draft collapsed them: `raise X from A if c else B` raises X either
        # way and only picks its *cause*, so a group that survived was reported as an ordinary timeout.
        if _reap(process, pgid, group_alive):
            raise Expired() from None
        raise CleanupUnconfirmed(f"cleanup unconfirmed: {Path(argv[0]).name}'s process group outlived SIGKILL")
    return process.returncode, out, err


def read_stream(raw, deadline, group_alive, node_bin="node"):
    """Parse the stream with the module production uses, and report what it extracted.

    Nothing here knows the event vocabulary: `scripts/lib/events.mjs` does, and that is the point of the probe.
    """
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        (work / "stream.jsonl").write_text(raw, encoding="utf-8")
        reader = work / "read.mjs"
        reader.write_text(
            "import { readFileSync } from 'node:fs';\n"
            f"import {{ readEventStream, classifyFailure, billableTokens }} from {str(EVENTS_MJS.as_uri())!r};\n"
            "const raw = readFileSync(process.argv[2], 'utf8');\n"
            "const events = readEventStream(raw);\n"
            "const failure = events.terminal === 'failed' ? classifyFailure(events) : null;\n"
            "process.stdout.write(JSON.stringify({ ...events, failure, billable: billableTokens(events.usage) }));\n",
            encoding="utf-8")
        code, out, err = _run_bounded([node_bin, str(reader), str(work / "stream.jsonl")], deadline, group_alive)
        if code != 0:
            raise RuntimeError(f"the production parser could not be run: {err.strip()}")
        return json.loads(out)


def _discover(raw, drop=()):
    """`(token block, tool-call count)` as scripts/runs_stats/discover.py reads them, over a filtered copy."""
    if str(SCRIPTS_LIB) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_LIB))
    import importlib.util
    spec = importlib.util.spec_from_file_location("vibe_discover", DISCOVER_PY)
    discover = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(discover)
    kept = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except Exception:
            kept.append(line)
            continue
        if isinstance(event, dict) and event.get("type") in drop:
            continue
        kept.append(line)
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "stream.jsonl"
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        warnings = []
        block, tool_calls = discover.usage_from_event_stream(str(path), warnings)
        return block, tool_calls, warnings


def _bounded_call(function, deadline):
    """Run pure work under the probe's deadline. It cannot be interrupted, so the thread is a daemon: if it never
    finishes, the probe still returns and the process still exits."""
    left = _remaining(deadline)
    outcome = {}

    def run():
        try:
            outcome["value"] = function()
        except BaseException as exc:
            outcome["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(left)
    if "error" in outcome:
        raise outcome["error"]
    if "value" not in outcome:
        raise Expired()
    return outcome["value"]


def _check_optional(raw, usage):
    """The optional rows of the contract: absence is never a failure, a present value is checked by its consumer."""
    detail = {}
    block, tool_calls, warnings = _discover(raw)
    if "reasoning_output_tokens" in (usage or {}):
        emitted = usage["reasoning_output_tokens"]
        if warnings or block is None or block.get("reasoning_output") != emitted:
            note = warnings[0] if warnings else f"read back {block and block.get('reasoning_output')!r}"
            return None, f"reasoning_output_tokens: the statistics reader disagrees with the stream ({note})"
        detail["reasoning"] = block["reasoning_output"]
    present = {}
    for event_type in TOOL_EVENT_TYPES:
        emitted = sum(1 for line in raw.splitlines()
                      if line.strip().startswith("{") and _type_of(line) == event_type)
        if not emitted:
            continue
        _, without, _ = _discover(raw, drop=(event_type,))
        if tool_calls - without != emitted:
            return None, (f"{event_type}: the statistics reader counted {tool_calls - without} of {emitted} "
                          f"— the event is no longer recognised")
        present[event_type] = emitted
    if present:
        detail["tool_events"] = present
    return detail, None


def _type_of(line):
    try:
        event = json.loads(line)
    except Exception:
        return None
    return event.get("type") if isinstance(event, dict) else None


def _group_is_alive(pgid, killpg=os.killpg):
    """True when the group still has a member we must not leave behind.

    `EPERM` means the group exists and we may not signal it — that is *not* proof of absence, and reading it as
    absence is how an unreaped descendant gets reported as a clean exit. `killpg` is a seam so a test can supply
    each error deterministically instead of hoping the platform produces one.
    """
    try:
        killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _reap(process, pgid, group_alive):
    """SIGTERM the group, then SIGKILL it, then say whether it is confirmed gone.

    `pgid` is captured when the child is launched, not looked up here: a process group outlives its leader, so a
    leader that has already exited says nothing about the descendants still holding the pipe. Two details the first
    draft also got wrong, both found by the tests: a group whose only member is a zombie cannot be signalled at all
    (macOS answers EPERM), and the child has to be waited on before the group can empty — otherwise the probe reports
    its own unreaped zombie as a group that survived SIGKILL.
    """
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            process.wait(timeout=REAP_GRACE_S)
        except Exception:
            pass
        until = time.monotonic() + REAP_GRACE_S
        while time.monotonic() < until:
            if not group_alive(pgid):
                return True
            time.sleep(0.05)
    return not group_alive(pgid)


def probe(binary=None, opted_in=None, timeout_ms=None, group_alive=None, node_bin="node",
          optional_check=None):
    """Run the installed binary once and report whether the event contract still holds.

    Skips carry a named environmental cause; anything unexplained is a failure, because a stream with no recognised
    events is indistinguishable from a renamed vocabulary.
    """
    if opted_in is None:
        opted_in = os.environ.get("VIBE_SUITE_REAL_CODEX") == "1"
    if not opted_in:
        return Verdict("skip", "opt-in not set (VIBE_SUITE_REAL_CODEX=1 runs it)")
    binary = binary or os.environ.get("VIBE_SUITE_CODEX_BIN") or shutil.which("codex")
    if not binary or not Path(binary).exists():
        return Verdict("skip", f"binary absent: {binary or 'codex'} not found")
    timeout_ms = timeout_ms or int(os.environ.get("VIBE_SUITE_PROBE_TIMEOUT_MS", DEFAULT_TIMEOUT_MS))
    group_alive = group_alive or _group_is_alive
    optional_check = optional_check or _check_optional

    argv = [str(binary), "exec", "--json", "-s", "read-only", "--skip-git-repo-check", PROMPT]
    deadline = time.monotonic() + timeout_ms / 1000          # one deadline for the whole probe, not per step
    with tempfile.TemporaryDirectory() as work:
        process = subprocess.Popen(argv, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            pgid = os.getpgid(process.pid)                   # captured now: a group outlives its leader
        except ProcessLookupError:
            pgid = process.pid
        try:
            raw, err = process.communicate(timeout=_remaining(deadline))
        except (subprocess.TimeoutExpired, Expired):
            reaped = _reap(process, pgid, group_alive)
            if not reaped:
                return Verdict("fail", f"cleanup unconfirmed: the process group outlived SIGKILL "
                                       f"after timing out at {timeout_ms} ms", {"group_reaped": False})
            return Verdict("skip", f"timed out after {timeout_ms} ms", {"group_reaped": True})

    try:
        parsed = read_stream(raw, deadline, group_alive, node_bin=node_bin)
    except Expired:
        return Verdict("skip", f"timed out after {timeout_ms} ms (parsing the stream)", {"group_reaped": True})
    except CleanupUnconfirmed as exc:
        return Verdict("fail", str(exc), {"group_reaped": False})
    except RuntimeError as exc:
        return Verdict("fail", str(exc), {"group_reaped": False})
    said = "\n".join(part for part in (failure_text(raw), err) if part)
    usage = parsed.get("usage") or {}

    missing = []
    if parsed.get("terminal") != "completed":
        missing.append("no terminal completion event")
    if not parsed.get("threadId"):
        missing.append("no thread id")
    if not parsed.get("agentMessage"):
        missing.append("no agent message")
    for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
        if field not in usage:
            missing.append(f"usage.{field} absent")
        elif not isinstance(usage[field], int) or isinstance(usage[field], bool):
            missing.append(f"usage.{field} is not an integer ({usage[field]!r})")

    if not missing:
        try:
            detail, complaint = _bounded_call(lambda: optional_check(raw, usage), deadline)
        except Expired:
            return Verdict("skip", f"timed out after {timeout_ms} ms (validating the stream)",
                           {"group_reaped": True})
        if complaint:
            return Verdict("fail", complaint)
        detail["billable"] = parsed.get("billable")
        try:
            version = _run_bounded([str(binary), "--version"], deadline, group_alive)[1].strip()
        except Expired:
            version = ""          # diagnostic only: a slow version read never decides the contract
        except CleanupUnconfirmed as exc:
            return Verdict("fail", str(exc), {"group_reaped": False})   # an unreaped group is not diagnostic
        detail["version"] = version
        return Verdict("pass", f"the event vocabulary matches ({version or 'version unreported'})", detail)

    if parsed.get("failure") == "quota":
        return Verdict("skip", f"quota: the stream reported an exhausted allowance ({said.splitlines()[:1]})")
    if parsed.get("terminal") != "completed" and _reads_like_a_refusal(said):
        return Verdict("skip", f"not authenticated: {said.strip().splitlines()[0] if said.strip() else 'refused'}")
    return Verdict("fail", "the event contract no longer holds: " + "; ".join(missing))


def _kill_all(pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _process_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _recorded_pids(path):
    try:
        return [int(pid) for pid in json.loads(path.read_text())]
    except Exception:
        return []


class FakeBinary(TempDirMixin):
    """Writes an executable stand-in for `codex` and records the argv it was called with."""

    def fake(self, out="", err="", code=0, sleep=0.0, spawn_child=False, ignore_sigterm=False, pids_file=None,
             leader_exits=False, version_sleep=0.0, version_child=False):
        root = Path(self.mkdtemp())
        argv_log = root / "argv.json"
        script = root / "fake-codex"
        script.write_text(textwrap.dedent(f"""
            #!/usr/bin/env python3
            import json, os, signal, sys, time
            if sys.argv[1:] == ["--warm"]:
                # the warm-up exec: the fixture itself leaves the marker; nothing logged, no child, no output
                open({str(root / "warmed")!r}, "w").close()
                sys.exit(0)
            if {ignore_sigterm!r}:
                # A child mid-write ignores SIGTERM; only the second signal ends it. This is what makes the
                # termination policy's SIGKILL load-bearing rather than decorative.
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
            with open({str(argv_log)!r}, "a") as log:
                log.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
            if sys.argv[1:2] == ["--version"]:
                if {version_child!r}:
                    kid = os.fork()
                    if kid > 0:
                        json.dump([os.getpid(), kid], open({str(pids_file)!r}, "w"))
                    else:
                        time.sleep(300)
                if {version_sleep!r}:
                    time.sleep({version_sleep!r})
                sys.stdout.write("codex-cli 9.9.9-fake\\n")
                sys.exit(0)
            if {spawn_child!r}:
                # A descendant that holds the output pipe: killing only the parent would leave it running.
                child = os.fork()
                if {str(pids_file)!r} != "None" and child > 0:
                    json.dump([os.getpid(), child], open({str(pids_file)!r}, "w"))
                if child > 0:
                    if {leader_exits!r}:
                        sys.exit(0)          # the leader goes at once; the descendant keeps the pipe open
                    time.sleep({sleep!r} or 30)
                    sys.exit({code!r})
                # The fork already inherits this group; looking it up through getppid() after the leader may
                # have exited is a race that can land the child in the adopter's group instead.
                time.sleep(120)
                sys.exit(0)
            sys.stderr.write({err!r})
            sys.stdout.write({out!r})
            sys.stdout.flush()
            if {sleep!r}:
                time.sleep({sleep!r})
            sys.exit({code!r})
        """).lstrip(), encoding="utf-8")
        script.chmod(0o755)
        warm(script, root)
        return script, argv_log


WARM_TIMEOUT_S = 60.0


def warm(script, root, group_alive=None, wait=None):
    """Exec a freshly written fixture once, with `--warm`, before any probe execs it.

    macOS charges the FIRST launch of a newly created executable an assessment — about half a second idle, up to
    several seconds when the process table is busy — whatever the file's interpreter; the interpreter itself starts
    in tens of milliseconds. Paid inside the probe's budget, that cost is what made the timing tests flaky
    (vibe-337): a 1500 ms budget was inside the fixture's own start-up distribution. Paid here, before the probe
    runs, the probe's exec is the file's second and costs the interpreter only.

    The fixture proves the exec by leaving a marker beside itself on `--warm`. The run is bounded, in its own process
    group whose id is captured at launch, and that group is reaped by the probe's own `_reap` on every path — a
    fixture that answered has exited and its group is empty; one that ignored `--warm`, forked and exited its leader
    is not left behind. Whether the group is gone is decided by `group_alive` (the probe's `_group_is_alive`, which
    reads a denied signal as presence); a group that outlives SIGKILL is reported as "cleanup unconfirmed", never
    as a warmed fixture. The check for that is inside the `finally`, right after the reap: an exception raised
    earlier (the group capture, the wait itself) is not allowed to carry the leftover process past it. `wait` is a
    seam for exactly that test; production waits on the leader under `WARM_TIMEOUT_S`.
    """
    group_alive = group_alive or _group_is_alive
    wait = wait or (lambda process: process.wait(timeout=WARM_TIMEOUT_S))
    marker = Path(root) / "warmed"
    process, pgid, timed_out, confirmed = None, None, False, False
    # A KeyboardInterrupt is raised by Python's SIGINT handler, which runs on the MAIN thread whichever thread the
    # signal reached — so a per-thread mask is not the mechanism. From before the launch until the verdict below is
    # delivered, the main thread's handler is replaced by one that only records the interrupt; the previous handler
    # is restored on every path, and a recorded interrupt is raised then — after the verdict, never inside the
    # region. The fixtures are written on the main thread (the probe's worker thread never calls this); off the
    # main thread no handler can be installed, and the region runs undeferred, which the docstring declares.
    deferred = []
    previous = None
    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGINT, lambda signum, frame: deferred.append(signum))
    try:
        try:
            process = subprocess.Popen([str(script), "--warm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       start_new_session=True)
            pgid = process.pid                              # the session leader's pid is its group id, until read
            try:
                pgid = os.getpgid(process.pid)              # captured at launch: a group outlives its leader
            except ProcessLookupError:
                pass
            try:
                wait(process)
            except subprocess.TimeoutExpired:
                timed_out = True
        finally:
            # every path — answered, hung, ignored `--warm` and forked, or an exception above — and the verdict on
            # the group is given HERE, so a pending exception cannot carry a leftover process past it. The cleanup's
            # own failure (the liveness seam raising) is the same verdict: a last SIGKILL is sent and the refusal
            # names it, with the cleanup's exception chained as its cause.
            if process is not None:
                try:
                    confirmed = _reap(process, pgid, group_alive)
                except BaseException as exc:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
                    raise AssertionError(f"cleanup unconfirmed: the reap of {Path(script).name}'s warm-up process "
                                         f"group raised {type(exc).__name__}: {exc}") from exc
                if not confirmed:
                    raise AssertionError(f"cleanup unconfirmed: {Path(script).name}'s warm-up process group outlived "
                                         f"SIGKILL")
    finally:
        if previous is not None:
            signal.signal(signal.SIGINT, previous)
    if deferred:
        raise KeyboardInterrupt("deferred until the warm-up's cleanup verdict was delivered")
    if timed_out:
        raise AssertionError(f"{Path(script).name} did not answer --warm within {WARM_TIMEOUT_S:.0f} s")
    if not marker.is_file():
        raise AssertionError(f"{Path(script).name} did not leave the warm marker: its --warm path did not run")


def wait_for_pids(pids_file, seconds=30.0):
    """The fixture's first observable write — both pids, valid — awaited on the TEST's deadline.

    Diagnostic, not a cure (vibe-337): the probe's own deadline runs on regardless, so what keeps the fixture from
    being reaped before it writes is the warm-up and the budget's headroom. This wait makes the failure, when there
    is one, say "the fixture did not start" by name instead of surfacing later as a missing pid.
    """
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        recorded = _recorded_pids(pids_file)
        if len(recorded) == 2 and all(isinstance(pid, int) and pid > 0 for pid in recorded):
            return
        time.sleep(0.01)
    raise AssertionError(f"the fixture did not start within {seconds:.0f} s: {pids_file} has no valid pid pair")


class ProbeVerdicts(FakeBinary, unittest.TestCase):
    """T1-T18 — the probe's own behaviour, driven by fakes. No real call is ever spent here."""

    def run_with_deadline(self, call, seconds, ready=None):
        """Run `call` on a worker thread and give up on it after `seconds`, so a hang fails this test rather than
        stalling the suite. The thread is a daemon: if it never returns, it cannot keep the runner alive.

        `ready`, when given, runs on THIS thread while the worker runs the probe: it waits for the fixture's first
        observable write on the test's own deadline (vibe-337) and raises, by name, if the fixture never starts."""
        outcome = {}
        started = time.monotonic()

        def run():
            try:
                outcome["verdict"] = call()
            except BaseException as exc:                     # reported, never swallowed
                outcome["error"] = exc
            finally:
                outcome["elapsed"] = time.monotonic() - started

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        if ready is not None:
            ready()
        worker.join(max(0.0, seconds - (time.monotonic() - started)))
        if "error" in outcome:
            raise outcome["error"]
        return outcome

    def probe(self, script, **kwargs):
        from tests import test_codex_contract as module
        return module.probe(binary=str(script), opted_in=True, **kwargs)

    def test_every_fixture_is_exec_d_once_before_the_probe(self):
        """vibe-337: the first launch of a newly created executable is charged by the OS, not by the interpreter;
        the fixture writers pay it before the probe runs and leave a marker. Without the marker, the probe's exec
        would be the file's first."""
        script, _ = self.fake(out=stream(HEALTHY))
        self.assertTrue((script.parent / "warmed").is_file(), "the fake binary was not exec'd before the probe")
        self.assertFalse((script.parent / "argv.json").exists(), "the warm-up exec must log nothing")
        slow = self.stalling_node(Path(self.mkdtemp()) / "pids.json")
        self.assertTrue((slow.parent / "warmed").is_file(), "the stand-in parser was not exec'd before the probe")
        for fixture in (script, slow):
            with self.subTest(fixture=fixture.name):
                self.assertEqual(subprocess.run([str(fixture), "--warm"], capture_output=True, timeout=60).returncode, 0)
        # the marker is the fixture's own act: a script that ignores --warm leaves none, and warm() says so by name
        from tests import test_codex_contract as module
        deaf = Path(self.mkdtemp()) / "deaf"
        deaf.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        deaf.chmod(0o755)
        with self.assertRaises(AssertionError) as caught:
            module.warm(deaf, deaf.parent)
        self.assertIn("did not leave the warm marker", str(caught.exception))
        # a fixture that ignores --warm, forks and exits its leader: the descendant must not outlive the warm-up,
        # and the refusal must come after the cleanup (A7)
        root = Path(self.mkdtemp())
        forker = root / "forker"
        forker.write_text("#!/bin/sh\nsleep 120 &\necho $! > " + str(root / "child.pid") + "\nexit 0\n", encoding="utf-8")
        forker.chmod(0o755)
        with self.assertRaises(AssertionError) as caught:
            module.warm(forker, root)
        self.assertIn("did not leave the warm marker", str(caught.exception))
        child = int((root / "child.pid").read_text().strip())
        try:
            self.assertFalse(_process_is_alive(child), "the warm-up's descendant outlived it")
        finally:
            _kill_all([child])
        # a group the seam reports alive after SIGKILL is "cleanup unconfirmed", even for a fixture that answered
        ok_script, _ = self.fake(out=stream(HEALTHY))
        with self.assertRaises(AssertionError) as caught:
            module.warm(ok_script, ok_script.parent, group_alive=lambda pgid: True)
        self.assertIn("cleanup unconfirmed", str(caught.exception))

        # an exception raised after launch (the wait itself, here) does not carry a leftover group past the check:
        # with the group reported alive the refusal is "cleanup unconfirmed"; with it gone, the exception propagates
        def failing_wait(process):
            raise OSError("the wait itself failed")

        try:
            module.warm(ok_script, ok_script.parent, group_alive=lambda pgid: True, wait=failing_wait)
        except AssertionError as exc:
            self.assertIn("cleanup unconfirmed", str(exc))
        except Exception as exc:                        # the wait's own exception must not carry the group past the verdict
            self.fail(f"a post-launch exception carried the leftover group past the cleanup verdict: {exc!r}")
        else:
            self.fail("warm() returned with its group reported alive")
        with self.assertRaises(OSError):
            module.warm(ok_script, ok_script.parent, wait=failing_wait)

        # the timeout verdict, through the seam: a wait that reports the bound expired is refused by name, after the
        # (confirmed) cleanup
        def expiring_wait(process):
            raise subprocess.TimeoutExpired(cmd="--warm", timeout=module.WARM_TIMEOUT_S)

        with self.assertRaises(AssertionError) as caught:
            module.warm(ok_script, ok_script.parent, wait=expiring_wait)
        self.assertIn("did not answer --warm within", str(caught.exception))

        # a SIGINT that reaches the process INSIDE the region — sent from this thread, and sent from another thread
        # (Python runs the handler on the main thread either way) — is deferred: the reap runs to its verdict, the
        # handler is restored, and only then is the KeyboardInterrupt raised
        original = signal.getsignal(signal.SIGINT)
        for sender in ("this thread", "another thread"):
            with self.subTest(sender=sender):
                seen = []

                def alive_interrupting(pgid, sender=sender):
                    seen.append("before")
                    if sender == "this thread":
                        os.kill(os.getpid(), signal.SIGINT)
                    else:
                        other = threading.Thread(target=lambda: os.kill(os.getpid(), signal.SIGINT))
                        other.start()
                        other.join()
                    time.sleep(0.05)                 # a bytecode boundary or two: an undeferred handler fires here
                    seen.append("after")             # reached only if the interrupt was deferred
                    return False

                script_i, _ = self.fake(out=stream(HEALTHY))
                with self.assertRaises(KeyboardInterrupt, msg="the deferred interrupt must be raised after the verdict"):
                    module.warm(script_i, script_i.parent, group_alive=alive_interrupting)
                self.assertEqual(seen, ["before", "after"], "the interrupt was not deferred past the reap")
                self.assertIs(signal.getsignal(signal.SIGINT), original, "the SIGINT handler was not restored")

        # the cleanup's own failure is the same verdict: a liveness seam that raises must not carry the group past it
        def raising_alive(pgid):
            raise RuntimeError("the liveness check itself failed")

        try:
            module.warm(ok_script, ok_script.parent, group_alive=raising_alive)
        except AssertionError as exc:
            self.assertIn("cleanup unconfirmed", str(exc))
            self.assertIsInstance(exc.__cause__, RuntimeError, "the cleanup's exception is chained as the cause")
        except Exception as exc:
            self.fail(f"the cleanup's own exception escaped the cleanup verdict: {exc!r}")
        else:
            self.fail("warm() returned although its cleanup could not confirm the group's absence")

    def test_a_fixture_that_never_starts_fails_by_name(self):
        """vibe-337: the readiness wait reports the fixture, not a missing pid later."""
        from tests import test_codex_contract as module
        never = Path(self.mkdtemp()) / "never.json"
        with self.assertRaises(AssertionError) as caught:
            module.wait_for_pids(never, seconds=0.2)
        self.assertIn("did not start", str(caught.exception))
        self.assertIn("never.json", str(caught.exception))
        half = Path(self.mkdtemp()) / "half.json"
        half.write_text("[1]", encoding="utf-8")            # one pid is not the fixture's write: both must be there
        with self.assertRaises(AssertionError):
            module.wait_for_pids(half, seconds=0.2)
        for bad in ("[0, 5]", "[-1, 2]", "[3, 0]"):          # a pid pair with a non-positive value is not valid
            invalid = Path(self.mkdtemp()) / "invalid.json"
            invalid.write_text(bad, encoding="utf-8")
            with self.subTest(pids=bad), self.assertRaises(AssertionError):
                module.wait_for_pids(invalid, seconds=0.2)
        written = Path(self.mkdtemp()) / "pids.json"
        written.write_text("[1, 2]", encoding="utf-8")
        module.wait_for_pids(written, seconds=0.2)          # returns at once when the write is there
        # and the wait runs on the test's thread while the probe runs on its worker: its failure is the test's
        with self.assertRaises(AssertionError):
            self.run_with_deadline(lambda: time.sleep(0.05), seconds=5,
                                   ready=lambda: module.wait_for_pids(never, seconds=0.1))

    def test_the_probe_is_opt_in(self):
        """T1 — without the variable the probe does not even look for a binary."""
        from tests import test_codex_contract as module
        script, argv_log = self.fake(out=stream(HEALTHY))
        verdict = module.probe(binary=str(script), opted_in=False)
        self.assertEqual(verdict.kind, "skip")
        self.assertIn("opt-in", verdict.reason)
        self.assertFalse(argv_log.exists(), "the binary was spawned despite the opt-in being unset")

    def test_an_absent_binary_skips(self):
        """T2 — the issue's own skip path."""
        verdict = self.probe(Path(self.mkdtemp()) / "not-here")
        self.assertEqual(verdict.kind, "skip")
        self.assertIn("not-here", verdict.reason)

    def test_a_healthy_stream_passes(self):
        """T3 — the vocabulary as production reads it."""
        script, _ = self.fake(out=stream(HEALTHY))
        verdict = self.probe(script)
        self.assertEqual(verdict.kind, "pass", verdict.reason)
        self.assertEqual(verdict.detail["billable"], 12 - 4 + 3)

    def test_each_missing_mandatory_observation_fails(self):
        """T4 — one case per mandatory row, each naming the field it lost."""
        cases = {
            "thread.started": ([HEALTHY[1], HEALTHY[2]], "thread"),
            "agent_message": ([HEALTHY[0], HEALTHY[2]], "agent message"),
            "turn.completed": (HEALTHY[:2], "terminal"),
        }
        for name, (events, expected) in cases.items():
            with self.subTest(missing=name):
                script, _ = self.fake(out=stream(events))
                verdict = self.probe(script)
                self.assertEqual(verdict.kind, "fail", verdict.reason)
                self.assertIn(expected, verdict.reason.lower())

    def test_a_missing_usage_field_fails(self):
        """T4 — the three fields billableTokens actually needs."""
        for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
            with self.subTest(missing=field):
                usage = {k: v for k, v in HEALTHY[2]["usage"].items() if k != field}
                events = HEALTHY[:2] + [{"type": "turn.completed", "usage": usage}]
                verdict = self.probe(self.fake(out=stream(events))[0])
                self.assertEqual(verdict.kind, "fail")
                self.assertIn(field, verdict.reason)

    def test_a_non_integral_usage_value_fails(self):
        """T18 — present but not a number is drift too."""
        for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
            for value in ("many", None, True):
                with self.subTest(field=field, value=value):
                    usage = dict(HEALTHY[2]["usage"], **{field: value})
                    events = HEALTHY[:2] + [{"type": "turn.completed", "usage": usage}]
                    verdict = self.probe(self.fake(out=stream(events))[0])
                    self.assertEqual(verdict.kind, "fail", verdict.reason)
                    self.assertIn(field, verdict.reason)

    def test_a_quota_failure_skips(self):
        """T5 — the repository's own classifier decides this one."""
        events = [HEALTHY[0], {"type": "turn.failed", "error": {"code": "insufficient_quota", "message": "no"}}]
        verdict = self.probe(self.fake(out=stream(events))[0])
        self.assertEqual(verdict.kind, "skip")
        self.assertIn("quota", verdict.reason)

    def test_an_unrecognised_failure_fails(self):
        """T6 — weather that cannot be named is not weather."""
        events = [HEALTHY[0], {"type": "turn.failed", "error": {"code": "teapot", "message": "short and stout"}}]
        verdict = self.probe(self.fake(out=stream(events))[0])
        self.assertEqual(verdict.kind, "fail", verdict.reason)

    def test_a_renamed_vocabulary_fails(self):
        """T7 — the drift this module exists to catch."""
        renamed = [
            {"type": "thread_started", "thread_id": "t"},
            {"type": "item_completed", "item": {"type": "agent_message", "text": "ok"}},
            {"type": "turn_completed", "usage": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}},
        ]
        verdict = self.probe(self.fake(out=stream(renamed))[0])
        self.assertEqual(verdict.kind, "fail", verdict.reason)

    def test_an_empty_stream_fails(self):
        """T8 — exit 0 with nothing said: the failer.mjs shape, which must not read as 'never started'."""
        verdict = self.probe(self.fake(out="")[0])
        self.assertEqual(verdict.kind, "fail", verdict.reason)

    def test_a_diagnostic_line_does_not_fail_a_healthy_stream(self):
        """T16 — codex interleaves prose; events.mjs tolerates it and so must the probe."""
        script, _ = self.fake(out=stream(HEALTHY, extra_lines=["", "not json at all"]))
        self.assertEqual(self.probe(script).kind, "pass")

    def test_an_authentication_refusal_skips(self):
        """T10 — every declared pattern, including the shapes the parser's own fallbacks allow."""
        cases = {
            "authless fixture (string error)": ([HEALTHY[0], {"type": "turn.failed", "error": "401 unauthorized"}], ""),
            "top-level message only": ([HEALTHY[0], {"type": "turn.failed", "message": "401 unauthorized"}], ""),
            "not logged in": ([], "Not logged in. Run `codex login`.\n"),
            "authentication failed": ([], "authentication failed\n"),
            "key is not set": ([], "OPENAI_API_KEY is not set\n"),
            "key is required": ([], "OPENAI_API_KEY is required\n"),
            "api key required": ([], "API key required. Please authenticate.\n"),
            "missing api key": ([], "missing API key\n"),
            # Exclusive to the 401 pattern: no other declared pattern matches this text.
            "401 forbidden": ([], "HTTP 401 forbidden by the gateway\n"),
        }
        for name, (events, err) in cases.items():
            with self.subTest(refusal=name):
                verdict = self.probe(self.fake(out=stream(events) if events else "", err=err)[0])
                self.assertEqual(verdict.kind, "skip", f"{name}: {verdict.reason}")
                self.assertIn("authenticat", verdict.reason.lower())

    def test_an_auth_marker_cannot_excuse_drift(self):
        """T10b — the near misses, in both directions."""
        drifted = stream([{"type": "thread_started", "thread_id": "t"}])
        for name, err in {
            "incidental 401": "401 items processed\n",
            "negated requirement": "OPENAI_API_KEY is not required here\n",
            "bare login advice": "run `codex login` for help\n",
        }.items():
            with self.subTest(near_miss=name):
                verdict = self.probe(self.fake(out=drifted, err=err)[0])
                self.assertEqual(verdict.kind, "fail", f"{name}: {verdict.reason}")

        with self.subTest(case="a refusal sentence beside a healthy stream"):
            script, _ = self.fake(out=stream(HEALTHY), err="Not logged in. Run `codex login`.\n")
            self.assertEqual(self.probe(script).kind, "pass")

        with self.subTest(case="a completed turn missing a mandatory observation, beside a refusal"):
            events = [HEALTHY[0], HEALTHY[2]]          # completed, but no agent message
            script, _ = self.fake(out=stream(events), err="Not logged in.\n")
            self.assertEqual(self.probe(script).kind, "fail")

    def test_a_later_refusal_cannot_excuse_the_first_failure(self):
        """F5's regression — the first terminal event decides, as it does in events.mjs."""
        events = [HEALTHY[0],
                  {"type": "turn.failed", "error": {"code": "teapot", "message": "short and stout"}},
                  {"type": "turn.failed", "error": "401 unauthorized"}]
        verdict = self.probe(self.fake(out=stream(events))[0])
        self.assertEqual(verdict.kind, "fail", verdict.reason)

    def test_optional_observations_are_checked_only_when_present(self):
        """T11 — absence is never a failure; a present value is checked through the consumer that reads it."""
        with self.subTest(case="absent"):
            self.assertEqual(self.probe(self.fake(out=stream(HEALTHY))[0]).kind, "pass")

        with self.subTest(case="present and valid"):
            usage = dict(HEALTHY[2]["usage"], reasoning_output_tokens=7)
            events = HEALTHY[:2] + [{"type": "turn.completed", "usage": usage}]
            verdict = self.probe(self.fake(out=stream(events))[0])
            self.assertEqual(verdict.kind, "pass", verdict.reason)
            self.assertEqual(verdict.detail["reasoning"], 7)

        with self.subTest(case="present and invalid"):
            usage = dict(HEALTHY[2]["usage"], reasoning_output_tokens="lots")
            events = HEALTHY[:2] + [{"type": "turn.completed", "usage": usage}]
            verdict = self.probe(self.fake(out=stream(events))[0])
            self.assertEqual(verdict.kind, "fail", verdict.reason)
            self.assertIn("reasoning_output_tokens", verdict.reason)

    def test_the_tool_event_differential_is_per_type(self):
        """T11b — item.completed is mandatory and also counted, so only a per-type differential has teeth."""
        events = [HEALTHY[0], {"type": "item.started", "item": {"type": "command_execution"}},
                  {"type": "command_execution", "command": "ls"}, HEALTHY[1], HEALTHY[2]]
        verdict = self.probe(self.fake(out=stream(events))[0])
        self.assertEqual(verdict.kind, "pass", verdict.reason)
        self.assertEqual(verdict.detail["tool_events"], {"item.started": 1, "command_execution": 1})

    def test_a_timeout_skips_and_reaps_the_group(self):
        """T9 — a descendant holds the pipe; both must be gone when the probe returns.

        The probe's own `group_reaped` flag is not evidence: this test records the pids the fake reports and checks
        them itself, under a watchdog that fires whatever the probe does, and kills whatever is left in `finally`.
        """
        pids_file = Path(self.mkdtemp()) / "pids.json"
        script, _ = self.fake(out=stream(HEALTHY), spawn_child=True, sleep=30, ignore_sigterm=True,
                              pids_file=pids_file)
        try:
            outcome = self.run_with_deadline(lambda: self.probe(script, timeout_ms=4000), seconds=60,
                                             ready=lambda: wait_for_pids(pids_file))
            self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
            verdict = outcome["verdict"]
            self.assertEqual(verdict.kind, "skip", verdict.reason)
            self.assertIn("timed out", verdict.reason)
            self.assertLess(outcome["elapsed"], 30, "the probe outlived its own deadline")
            recorded = _recorded_pids(pids_file)
            self.assertEqual(len(recorded), 2, f"the fake did not report both processes: {recorded}")
            # Checked BEFORE the fallback cleanup below, or the test would be grading its own kill.
            for pid in recorded:
                with self.subTest(pid=pid):
                    self.assertFalse(_process_is_alive(pid), "a process the probe launched is still running")
        finally:
            _kill_all(_recorded_pids(pids_file))

    def test_group_liveness_treats_permission_denial_as_presence(self):
        """A group we may not signal still exists — reading EPERM as absence is how a survivor gets reported clean.

        Both errors are injected, so the case does not depend on what this machine happens to have running.
        """
        from tests import test_codex_contract as module

        def denied(pgid, sig):
            raise PermissionError(1, "Operation not permitted")

        def absent(pgid, sig):
            raise ProcessLookupError(3, "No such process")

        self.assertTrue(module._group_is_alive(4242, killpg=denied), "a group we may not signal was reported gone")
        self.assertFalse(module._group_is_alive(4242, killpg=absent), "a vanished group was reported alive")
        self.assertTrue(module._group_is_alive(4242, killpg=lambda pgid, sig: None))

    def test_a_descendant_outliving_its_leader_is_still_reaped(self):
        """A process group outlives its leader, so the group id must be captured at launch, not looked up during
        cleanup — by then there may be nothing to look it up from."""
        pids_file = Path(self.mkdtemp()) / "pids.json"
        script, _ = self.fake(out=stream(HEALTHY), spawn_child=True, leader_exits=True, pids_file=pids_file)
        try:
            outcome = self.run_with_deadline(lambda: self.probe(script, timeout_ms=4000), seconds=60,
                                             ready=lambda: wait_for_pids(pids_file))
            self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
            self.assertEqual(outcome["verdict"].kind, "skip", outcome["verdict"].reason)
            recorded = _recorded_pids(pids_file)
            self.assertEqual(len(recorded), 2, f"the fake did not report both processes: {recorded}")
            self.assertFalse(_process_is_alive(recorded[1]), "the descendant outlived the probe")
        finally:
            _kill_all(_recorded_pids(pids_file))

    def stalling_node(self, pids_file):
        """A stand-in for `node` that never finishes and leaves a descendant holding the pipe.

        The descendant is the point: killing the helper alone would leave it running, so this is what shows the
        helper's whole process GROUP is reaped rather than just its leader.
        """
        script = Path(self.mkdtemp()) / "slow-node"
        script.write_text(textwrap.dedent(f"""
            #!/usr/bin/env python3
            import json, os, sys, time
            if sys.argv[1:] == ["--warm"]:
                open({str(script.parent / "warmed")!r}, "w").close()
                sys.exit(0)
            child = os.fork()
            if child > 0:
                json.dump([os.getpid(), child], open({str(pids_file)!r}, "w"))
                time.sleep(300)
            time.sleep(300)
        """).lstrip(), encoding="utf-8")
        script.chmod(0o755)
        warm(script, script.parent)
        return script

    def test_a_stalled_parse_times_out_and_reaps(self):
        """The parse runs inside the probe's one deadline, and its process group is reaped when it overruns."""
        pids_file = Path(self.mkdtemp()) / "node-pid.json"
        script, _ = self.fake(out=stream(HEALTHY))
        slow = self.stalling_node(pids_file)
        try:
            outcome = self.run_with_deadline(
                lambda: self.probe(script, timeout_ms=4000, node_bin=str(slow)), seconds=60,
                ready=lambda: wait_for_pids(pids_file))
            self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
            verdict = outcome["verdict"]
            self.assertEqual(verdict.kind, "skip", verdict.reason)
            self.assertIn("parsing", verdict.reason)
            recorded = _recorded_pids(pids_file)
            self.assertEqual(len(recorded), 2, "the stand-in parser did not record both processes")
            for pid in recorded:
                with self.subTest(pid=pid):
                    self.assertFalse(_process_is_alive(pid), "a parser process outlived the probe")
        finally:
            _kill_all(_recorded_pids(pids_file))

    def test_a_stalled_version_read_never_decides_the_contract(self):
        """The version is diagnostic: a slow read leaves it empty, and the contract's verdict stands."""
        script, _ = self.fake(out=stream(HEALTHY), version_sleep=30)
        outcome = self.run_with_deadline(lambda: self.probe(script, timeout_ms=4000), seconds=60)
        self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
        verdict = outcome["verdict"]
        self.assertEqual(verdict.kind, "pass", verdict.reason)
        self.assertEqual(verdict.detail.get("version"), "")

    def test_a_stalled_optional_check_times_out(self):
        """The optional phase is pure computation, so it is bounded by a joined worker rather than left to run."""
        script, _ = self.fake(out=stream(HEALTHY))

        def slow(raw, usage):
            time.sleep(60)
            return {}, None

        outcome = self.run_with_deadline(
            lambda: self.probe(script, timeout_ms=4000, optional_check=slow), seconds=60)
        self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
        verdict = outcome["verdict"]
        self.assertEqual(verdict.kind, "skip", verdict.reason)
        self.assertIn("validating", verdict.reason)

    def test_a_parser_group_that_survives_fails_rather_than_skipping(self):
        """D4's distinction, for the helper: a timeout is weather, an unreaped group is a defect."""
        pids_file = Path(self.mkdtemp()) / "node-pid.json"
        script, _ = self.fake(out=stream(HEALTHY))
        slow = self.stalling_node(pids_file)
        try:
            outcome = self.run_with_deadline(
                lambda: self.probe(script, timeout_ms=1500, node_bin=str(slow), group_alive=lambda pgid: True),
                seconds=60)
            self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
            verdict = outcome["verdict"]
            self.assertEqual(verdict.kind, "fail", verdict.reason)
            self.assertIn("cleanup unconfirmed", verdict.reason)
            self.assertFalse(verdict.detail.get("group_reaped", True))
        finally:
            _kill_all(_recorded_pids(pids_file))

    def test_a_version_group_that_survives_fails_rather_than_passing(self):
        """A slow version read is diagnostic; a version group that outlives SIGKILL is not."""
        script, _ = self.fake(out=stream(HEALTHY), version_sleep=30)
        outcome = self.run_with_deadline(
            lambda: self.probe(script, timeout_ms=3000, group_alive=lambda pgid: True), seconds=60)
        self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
        verdict = outcome["verdict"]
        self.assertEqual(verdict.kind, "fail", verdict.reason)
        self.assertIn("cleanup unconfirmed", verdict.reason)

    def test_a_version_descendant_is_reaped(self):
        """The version helper's whole group goes, not just the process the probe launched."""
        pids_file = Path(self.mkdtemp()) / "version-pids.json"
        script, _ = self.fake(out=stream(HEALTHY), version_sleep=30, version_child=True, pids_file=pids_file)
        try:
            outcome = self.run_with_deadline(lambda: self.probe(script, timeout_ms=4000), seconds=60,
                                             ready=lambda: wait_for_pids(pids_file))
            self.assertIn("verdict", outcome, "the probe did not return within the test's own deadline")
            self.assertEqual(outcome["verdict"].kind, "pass", outcome["verdict"].reason)
            recorded = _recorded_pids(pids_file)
            self.assertEqual(len(recorded), 2, f"the fake did not report both version processes: {recorded}")
            for pid in recorded:
                with self.subTest(pid=pid):
                    self.assertFalse(_process_is_alive(pid), "a version-helper process outlived the probe")
        finally:
            _kill_all(_recorded_pids(pids_file))

    def test_no_helper_is_launched_on_an_exhausted_budget(self):
        """An exhausted deadline stops work rather than starting another process.

        The binary does not exist, which is what makes this deterministic: if the deadline is checked first that
        never matters and `Expired` is raised, and if a process is launched anyway the launch itself fails with
        `FileNotFoundError`. Watching for a log file instead raced — a helper can be reaped before it writes one,
        so the assertion passed either way.
        """
        from tests import test_codex_contract as module
        missing = str(Path(self.mkdtemp()) / "not-a-real-binary")
        with self.assertRaises(module.Expired):
            module._run_bounded([missing, "--version"], time.monotonic() - 1, lambda pgid: False)

    def test_an_unreapable_group_fails(self):
        """T9b — SIGKILL cannot be ignored, so the seam is how this branch is reachable."""
        script, _ = self.fake(out=stream(HEALTHY), sleep=30)
        verdict = self.probe(script, timeout_ms=800, group_alive=lambda pgid: True)
        self.assertEqual(verdict.kind, "fail", verdict.reason)
        self.assertIn("cleanup unconfirmed", verdict.reason)

    def test_the_invocation_is_read_only_and_unpinned(self):
        """T17 — the argv, recorded by the fake itself."""
        script, argv_log = self.fake(out=stream(HEALTHY))
        self.assertEqual(self.probe(script).kind, "pass")
        recorded = json.loads(argv_log.read_text().splitlines()[0])   # the exec call, not the --version that follows
        argv = recorded["argv"]
        self.assertEqual(argv[0], "exec")
        for flag in ("--json", "--skip-git-repo-check"):
            self.assertIn(flag, argv)
        self.assertIn("read-only", argv[argv.index("-s") + 1])
        self.assertNotIn("-m", argv, "the probe must not pin a model")
        self.assertNotIn("--model", argv)
        self.assertTrue(argv[-1].strip(), "the prompt is empty")
        self.assertFalse(str(REPO_ROOT) in recorded["cwd"], "the probe ran inside this checkout")

    def test_the_parser_is_the_production_one(self):
        """T12 — behaviour, not source-grepping: only `events.mjs` knows these fallback spellings.

        `readEventStream` accepts `threadId` beside `thread_id` and `turn.usage` beside `usage`. A second parser
        written for this test would not, so a stream spelled that way passes here and fails anything else — which is
        what makes M1 (the Node evaluation replaced by a Python re-parse) detectable.
        """
        fallbacks = [
            {"type": "thread.started", "threadId": "camel_case_thread"},
            {"type": "item.completed", "item": {"type": "agent_message", "text": "ok"}},
            {"type": "turn.completed", "turn": {"usage": {"input_tokens": 5, "cached_input_tokens": 1,
                                                          "output_tokens": 2}}},
        ]
        verdict = self.probe(self.fake(out=stream(fallbacks))[0])
        self.assertEqual(verdict.kind, "pass", verdict.reason)
        self.assertEqual(verdict.detail["billable"], 5 - 1 + 2)


class TheWeeklyJob(unittest.TestCase):
    """T13 — parsed from the workflow, not grepped from its prose."""

    def test_the_weekly_job_is_declared(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        job = re.search(r"\n  codex-contract:\n(?P<body>(?:.*\n)*?)(?=\n  \w|\Z)", text)
        self.assertTrue(job, "self-check.yml has no codex-contract job")
        body = job.group("body")
        self.assertRegex(body, r"permissions:")
        self.assertIn("VIBE_SUITE_REAL_CODEX", body)
        self.assertIn("tests.test_codex_contract.RealCodexContract", body)
        # The credential's presence reaches the steps through job-level env, because `secrets` is not a context a
        # step-level `if:` may read. The job must therefore declare it once...
        self.assertRegex(body, r"env:\n(?:\s*#[^\n]*\n)*\s*HAS_CREDENTIAL:\s*\$\{\{[^\n]*secrets\.OPENAI_API_KEY",
                         "the job does not derive the credential's presence into env")
        self.assertNotRegex(body, r"if:[^\n]*secrets\.",
                            "a step-level `if:` reads `secrets`, which GitHub does not evaluate there")
        # ...and EVERY step must test it: the documented skip path is "a repository without the secret sees a
        # green, visibly-skipped job", and one unguarded step breaks it.
        steps = [chunk for chunk in re.split(r"\n      - ", body)[1:] if chunk.strip()]
        self.assertGreaterEqual(len(steps), 5, body)
        for chunk in steps:
            with self.subTest(step=chunk.splitlines()[0].strip()[:40]):
                self.assertRegex(chunk, r"if:\s*env\.HAS_CREDENTIAL == 'yes'",
                                 "a step of the weekly job is not guarded by the credential")

    def test_the_workflow_adds_no_trigger(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        header = text.split("\njobs:", 1)[0]
        self.assertIn("schedule:", header)
        self.assertIn("workflow_dispatch:", header)
        self.assertNotIn("pull_request:", header)
        self.assertNotIn("\n  push:", header)


class TheEntryPoint(FakeBinary, unittest.TestCase):
    """T14, T15 — the command the job runs, as a subprocess, so the exit status is the thing asserted."""

    def run_entry_point(self, env_extra):
        env = dict(os.environ, **env_extra)
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        return subprocess.run([sys.executable, "-B", "-m", "unittest",
                               "tests.test_codex_contract.RealCodexContract", "-v"],
                              cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180, env=env)

    def test_the_default_suite_spends_nothing(self):
        """T14 — no opt-in, no call: the live test skips."""
        env = {k: v for k, v in os.environ.items() if k != "VIBE_SUITE_REAL_CODEX"}
        result = subprocess.run([sys.executable, "-B", "-m", "unittest",
                                 "tests.test_codex_contract.RealCodexContract", "-v"],
                                cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped", result.stderr.lower())

    def test_the_entry_point_propagates_the_verdict(self):
        """T15 — pass, drift and skip must each reach the exit status the job sees."""
        healthy, _ = self.fake(out=stream(HEALTHY))
        drifted, _ = self.fake(out=stream([{"type": "thread_started", "thread_id": "t"}]))
        absent = Path(self.mkdtemp()) / "not-here"

        with self.subTest(outcome="pass"):
            result = self.run_entry_point({"VIBE_SUITE_REAL_CODEX": "1", "VIBE_SUITE_CODEX_BIN": str(healthy)})
            self.assertEqual(result.returncode, 0, result.stderr)

        with self.subTest(outcome="fail"):
            result = self.run_entry_point({"VIBE_SUITE_REAL_CODEX": "1", "VIBE_SUITE_CODEX_BIN": str(drifted)})
            self.assertNotEqual(result.returncode, 0, "drift did not reach the exit status")

        with self.subTest(outcome="skip"):
            result = self.run_entry_point({"VIBE_SUITE_REAL_CODEX": "1", "VIBE_SUITE_CODEX_BIN": str(absent)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("skipped", result.stderr.lower())


class RealCodexContract(unittest.TestCase):
    """The live run. Opt in with VIBE_SUITE_REAL_CODEX=1; otherwise this skips and spends nothing."""

    def test_the_event_vocabulary_still_matches(self):
        from tests import test_codex_contract as module
        verdict = module.probe()
        if verdict.kind == "skip":
            self.skipTest(verdict.reason)
        if verdict.kind == "fail":
            self.fail(verdict.reason)
        print(f"\ncodex contract: {verdict.reason}")


if __name__ == "__main__":
    unittest.main()
