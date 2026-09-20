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
    r"\b(OPENAI_API_KEY|api[ _]key)\b[^\n]{0,24}\b(is\s+)?(?<!not )(?<!n.t )(?<!no longer )required\b",
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
    said = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if not isinstance(event, dict) or event.get("type") != "turn.failed":
            continue
        error = event.get("error")
        if isinstance(error, str):
            said.append(error)
        elif isinstance(error, dict):
            said.extend(str(error.get(key)) for key in ("message", "code", "type") if error.get(key))
        if event.get("message"):
            said.append(str(event["message"]))
    return "\n".join(said)


def _reads_like_a_refusal(text):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in AUTH_PATTERNS)


def read_stream(raw):
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
        result = subprocess.run(["node", str(reader), str(work / "stream.jsonl")],
                                capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"the production parser could not be run: {result.stderr.strip()}")
        return json.loads(result.stdout)


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


def _group_is_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _reap(process, group_alive):
    """SIGTERM the group, then SIGKILL it, then say whether it is confirmed gone.

    Two details the first draft got wrong, both found by the tests: a group whose only member is a zombie cannot be
    signalled at all (macOS answers EPERM), and the child has to be waited on before the group can empty — otherwise
    the probe reports its own unreaped zombie as a group that survived SIGKILL.
    """
    try:
        pgid = os.getpgid(process.pid)
    except ProcessLookupError:
        return True
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            process.wait(timeout=REAP_GRACE_S)
        except Exception:
            pass
        deadline = time.monotonic() + REAP_GRACE_S
        while time.monotonic() < deadline:
            if not group_alive(pgid):
                return True
            time.sleep(0.05)
    return not group_alive(pgid)


def probe(binary=None, opted_in=None, timeout_ms=None, group_alive=None):
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

    argv = [str(binary), "exec", "--json", "-s", "read-only", "--skip-git-repo-check", PROMPT]
    with tempfile.TemporaryDirectory() as work:
        process = subprocess.Popen(argv, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            raw, err = process.communicate(timeout=timeout_ms / 1000)
        except subprocess.TimeoutExpired:
            reaped = _reap(process, group_alive)
            if not reaped:
                return Verdict("fail", f"cleanup unconfirmed: the process group outlived SIGKILL "
                                       f"after timing out at {timeout_ms} ms", {"group_reaped": False})
            return Verdict("skip", f"timed out after {timeout_ms} ms", {"group_reaped": True})

    parsed = read_stream(raw)
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
        detail, complaint = _check_optional(raw, usage)
        if complaint:
            return Verdict("fail", complaint)
        detail["billable"] = parsed.get("billable")
        version = subprocess.run([str(binary), "--version"], capture_output=True, text=True,
                                 timeout=30).stdout.strip()
        detail["version"] = version
        return Verdict("pass", f"the event vocabulary matches ({version or 'version unreported'})", detail)

    if parsed.get("failure") == "quota":
        return Verdict("skip", f"quota: the stream reported an exhausted allowance ({said.splitlines()[:1]})")
    if parsed.get("terminal") != "completed" and _reads_like_a_refusal(said):
        return Verdict("skip", f"not authenticated: {said.strip().splitlines()[0] if said.strip() else 'refused'}")
    return Verdict("fail", "the event contract no longer holds: " + "; ".join(missing))


class FakeBinary(TempDirMixin):
    """Writes an executable stand-in for `codex` and records the argv it was called with."""

    def fake(self, out="", err="", code=0, sleep=0.0, spawn_child=False, ignore_sigterm=False):
        root = Path(self.mkdtemp())
        argv_log = root / "argv.json"
        script = root / "fake-codex"
        script.write_text(textwrap.dedent(f"""
            #!/usr/bin/env python3
            import json, os, signal, sys, time
            if {ignore_sigterm!r}:
                # A child mid-write ignores SIGTERM; only the second signal ends it. This is what makes the
                # termination policy's SIGKILL load-bearing rather than decorative.
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
            with open({str(argv_log)!r}, "a") as log:
                log.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
            if sys.argv[1:2] == ["--version"]:
                sys.stdout.write("codex-cli 9.9.9-fake\\n")
                sys.exit(0)
            if {spawn_child!r}:
                # A descendant that holds the output pipe: killing only the parent would leave it running.
                if os.fork() > 0:
                    time.sleep({sleep!r} or 30)
                    sys.exit({code!r})
                os.setpgid(0, os.getpgid(os.getppid()))
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
        return script, argv_log


class ProbeVerdicts(FakeBinary, unittest.TestCase):
    """T1-T18 — the probe's own behaviour, driven by fakes. No real call is ever spent here."""

    def probe(self, script, **kwargs):
        from tests import test_codex_contract as module
        return module.probe(binary=str(script), opted_in=True, **kwargs)

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
        for value in ("many", None):
            with self.subTest(value=value):
                usage = dict(HEALTHY[2]["usage"], output_tokens=value)
                events = HEALTHY[:2] + [{"type": "turn.completed", "usage": usage}]
                verdict = self.probe(self.fake(out=stream(events))[0])
                self.assertEqual(verdict.kind, "fail")
                self.assertIn("output_tokens", verdict.reason)

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
        """T9 — a descendant holds the pipe; both must be gone when the probe returns."""
        script, _ = self.fake(out=stream(HEALTHY), spawn_child=True, sleep=30, ignore_sigterm=True)
        started = time.monotonic()
        verdict = self.probe(script, timeout_ms=1500)
        self.assertEqual(verdict.kind, "skip", verdict.reason)
        self.assertIn("timed out", verdict.reason)
        self.assertLess(time.monotonic() - started, 30, "the probe outlived its own deadline")
        self.assertTrue(verdict.detail["group_reaped"])

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
        """T12 — the verdict comes from scripts/lib/events.mjs, not a second implementation."""
        from tests import test_codex_contract as module
        source = Path(module.__file__).read_text(encoding="utf-8")
        self.assertIn("scripts/lib/events.mjs", source)
        self.assertNotIn('"thread.started"', source.split("HEALTHY")[-1].split("class ")[0],
                         "the probe re-implements the vocabulary instead of reading it through events.mjs")


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
        # Every step that does work must be guarded, not just one of them: the documented skip path is "a
        # repository without the secret sees a green, visibly-skipped job", and one unguarded step breaks it.
        steps = [chunk for chunk in re.split(r"\n      - ", body) if "run:" in chunk or "uses:" in chunk]
        self.assertGreaterEqual(len(steps), 2, body)
        working = [chunk for chunk in steps if "run:" in chunk]
        self.assertTrue(working, body)
        for chunk in working:
            with self.subTest(step=chunk.splitlines()[0].strip()):
                self.assertRegex(chunk, r"if:\s*\$\{\{\s*.*secrets\.",
                                 "a step that does work is not guarded by the secret")

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
