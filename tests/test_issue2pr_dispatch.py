#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""issue2pr's reviewer dispatch goes through the runner (vibe-224 / grill M4).

The reviewer contract's Dispatch row used to spell the issue2pr review as a bare engine call, carried in
prose the host had to remember: no deadline, no job record, no failure classification. The suite already
had the engine that owns those guarantees, and every other generator-critic loop used it.

**These tests execute the skill's own blocks.** Each tagged block is extracted from
`skills/issue2pr/SKILL.md` and run under `bash` with `VIBE_SUITE_CODEX_BIN` pointing at a fake engine, the
same way `tests/test_commands.py` treats `delegate.md`'s block. A test that asserted a string in the
markdown would stay green through a block that could not run.
"""

import json
import os
import re
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tmpdirs import TempDirMixin  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"
OPERATIONAL_MODES = REPO_ROOT / "skills" / "issue2pr" / "references" / "operational-modes.md"
CONTRACT = REPO_ROOT / "skills" / "vibe-core" / "references" / "reviewer-contract.md"
JOBS = REPO_ROOT / "scripts" / "lib" / "jobs.mjs"
EVENTS = REPO_ROOT / "scripts" / "lib" / "events.mjs"
FAKE = REPO_ROOT / "tests" / "fixtures" / "fake-codex"
JOBS_CLI = REPO_ROOT / "scripts" / "jobs-cli.mjs"

#: The runner's result contract, in order (`jobs.mjs` `RESULT_KEYS`).
RESULT_KEYS = ["jobId", "status", "threadId", "rawOutput", "verdictState", "verdictLine"]
#: `render.mjs` `RAW_OUTPUT_BYTES`.
RAW_OUTPUT_BYTES = 128 * 1024


def tagged_block(text, tag):
    """The fenced block after `<!-- tag -->`, without its info string. Exactly one such tag."""
    marker = f"<!-- {tag} -->"
    if text.count(marker) != 1:
        return None
    body = text.split(marker, 1)[1].split("```", 2)[1]
    return body.split("\n", 1)[1]


def json_block(text, tag):
    body = tagged_block(text, tag)
    return None if body is None else json.loads(body)


def skill_text():
    return SKILL.read_text(encoding="utf-8")


class BlockCase(TempDirMixin, unittest.TestCase):
    """Runs a tagged block from the skill in a fresh workspace."""

    def setUp(self):
        self.workspace = Path(self.mkdtemp())
        self.prompt = self.workspace / "prompt.md"
        self.prompt.write_text("Review the change and answer with the YAML block.\n", encoding="utf-8")

    def run_block(self, tag, fixture=None, timeout=60, **env):
        block = tagged_block(skill_text(), tag)
        self.assertIsNotNone(block, f"the skill carries no single <!-- {tag} --> block")
        full = dict(os.environ)
        for key in ("VIBE_TEST_STUB_VERDICT", "VIBE_TEST_STUB_PAD_BYTES", "ISSUE2PR_REVIEW_TIMEOUT_MS"):
            full.pop(key, None)
        full.update({"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT), "ISSUE2PR_PROMPT_FILE": str(self.prompt)})
        if fixture:
            full["VIBE_SUITE_CODEX_BIN"] = str(FAKE / fixture)
        full.update({k: str(v) for k, v in env.items()})
        return subprocess.run(["bash", "-c", block], cwd=self.workspace, env=full,
                              capture_output=True, text=True, timeout=timeout)

    def result_line(self, completed):
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"expected one result line, got {lines!r}\n{completed.stderr}")
        return json.loads(lines[0])

    def status_payload(self, job_id):
        completed = subprocess.run(["node", str(JOBS_CLI), "status", job_id, "--json"], cwd=self.workspace,
                                   capture_output=True, text=True, timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)


class TestCanonicalDispatchShape(unittest.TestCase):
    """T1 — one statement of the dispatch, in the core."""

    def test_the_core_carries_one_canonical_dispatch(self):
        text = skill_text()
        self.assertEqual(text.count("## Reviewer dispatch"), 1)
        block = tagged_block(text, "canonical-dispatch")
        self.assertIsNotNone(block, "exactly one <!-- canonical-dispatch --> block")
        for token in ('node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-runner.mjs"', "--kind review",
                      "--sandbox read-only", "--wait", '--prompt-file "$ISSUE2PR_PROMPT_FILE"',
                      '--timeout-ms "${ISSUE2PR_REVIEW_TIMEOUT_MS:-1200000}"'):
            self.assertIn(token, block)
        # P9: the block names no model and no effort; the runner resolves both.
        for banned in ("--model", "--effort", "codex exec"):
            self.assertNotIn(banned, block)
        self.assertIsNone(re.search(r"(^|\s)-m(\s|$)", block))


class TestDispatchProducesARecord(BlockCase):
    """T2 — acceptance: every review dispatch produces a job record."""

    def test_a_dispatch_produces_a_job_record(self):
        parsed = self.result_line(self.run_block("canonical-dispatch", fixture="issue2pr-stub.mjs"))
        self.assertEqual(list(parsed), RESULT_KEYS)
        self.assertEqual(parsed["status"], "completed")
        payload = self.status_payload(parsed["jobId"])
        self.assertEqual(len(payload["records"]), 1)
        record = payload["records"][0]
        self.assertEqual((record["jobId"], record["kind"], record["sandbox"]),
                         (parsed["jobId"], "review", "read-only"))


class TestHungReviewer(BlockCase):
    """T3 — acceptance: a hung reviewer ends `timed_out` within the deadline."""

    def test_a_hung_reviewer_ends_timed_out_within_the_deadline(self):
        started = time.monotonic()
        completed = self.run_block("canonical-dispatch", fixture="sleeper.mjs",
                                   ISSUE2PR_REVIEW_TIMEOUT_MS=1500)
        elapsed = time.monotonic() - started
        parsed = self.result_line(completed)
        self.assertEqual(parsed["status"], "timed_out")
        self.assertEqual(self.status_payload(parsed["jobId"])["records"][0]["status"], "timed_out")
        # A ceiling, not a window — the runner's own deadline tests use the same bound.
        self.assertLess(elapsed, 20, "the deadline was not enforced promptly")


class TestVerdictFromTheRecord(BlockCase):
    """T4 — the verdict is read from the record, not from the bounded wire."""

    def test_the_verdict_is_read_from_the_record(self):
        parsed = self.result_line(self.run_block("canonical-dispatch", fixture="issue2pr-stub.mjs",
                                                 VIBE_TEST_STUB_PAD_BYTES=1024 * 1024))
        self.assertEqual(parsed["status"], "completed")
        self.assertLessEqual(len(parsed["rawOutput"].encode("utf-8")), RAW_OUTPUT_BYTES)
        self.assertIn("[vibe-274: ", parsed["rawOutput"],
                      "the pad must push the capture past the bound for this test to mean anything")
        step = self.workspace / "step"
        step.mkdir()
        completed = self.run_block("canonical-verdict", ISSUE2PR_JOB_ID=parsed["jobId"],
                                   ISSUE2PR_STEP_DIR=step)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads((step / "job.json").read_text(encoding="utf-8"))
        text = payload["records"][0]["verdictText"]
        self.assertTrue(text.rstrip().endswith("```"), text[-200:])
        self.assertIn("```yaml\nverdict: approve\nfindings: []\n```", text)


def runner_terminal_statuses():
    script = (f"import({json.dumps(JOBS.as_uri())}).then(m => "
              "process.stdout.write(JSON.stringify([...m.TERMINAL_STATUSES])))")
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return set(json.loads(out.stdout))


def failure_classes():
    """Every class `classifyFailure` can return, read from its source."""
    text = EVENTS.read_text(encoding="utf-8")
    body = text.split("export function classifyFailure", 1)[1].split("\n}\n", 1)[0]
    classes = set()
    for line in body.splitlines():
        if "return" in line:
            classes.update(re.findall(r'"([a-z_]+)"', line))
    return classes


class TestOutcomeBranch(unittest.TestCase):
    """T5, T5b — every runner outcome has a declared branch, and the policy is exactly D4's."""

    def setUp(self):
        self.outcomes = json_block(skill_text(), "dispatch-outcome")
        self.assertIsNotNone(self.outcomes, "the skill declares no <!-- dispatch-outcome --> block")
        self.enum = json_block(OPERATIONAL_MODES.read_text(encoding="utf-8"), "run-status-enum")

    def test_every_runner_outcome_has_a_declared_branch(self):
        statuses = runner_terminal_statuses()
        classes = failure_classes()
        self.assertEqual(classes, {"quota", "failure"}, "the classifier's vocabulary moved; re-derive")
        expected = ({"completed"} | {f"failed:{c}" for c in classes}
                    | (statuses - {"completed", "failed"}))
        self.assertEqual(set(self.outcomes), expected)
        declared = set(self.enum["non_terminal"]) | set(self.enum["terminal"])
        for outcome, action in self.outcomes.items():
            with self.subTest(outcome=outcome):
                if action != "verdict":
                    self.assertIn(action, declared)

    def test_the_outcome_policy_is_exactly_d4(self):
        """A reviewer that did not answer leaves the run resumable — not merely in some valid status."""
        expected = {key: ("verdict" if key == "completed" else "quota_paused") for key in self.outcomes}
        self.assertEqual(self.outcomes, expected)
        self.assertIn("quota_paused", self.enum["non_terminal"])


class TestContractDispatchCell(unittest.TestCase):
    """T6 — the contract's Dispatch row names the engine that owns the guarantees."""

    def test_the_contract_dispatch_cell_names_the_runner(self):
        text = CONTRACT.read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("| **Dispatch** |")]
        self.assertEqual(len(rows), 1)
        cells = [cell.strip() for cell in rows[0].strip("|").split("|")]
        codex_cell = cells[2]
        self.assertIn("scripts/codex-runner.mjs", codex_cell)
        self.assertIn("/dev/null", codex_cell, "the stdin property stays stated, as the runner's")
        self.assertNotIn("`codex exec … < /dev/null`", codex_cell,
                         "the bare invocation is no longer the instruction")


if __name__ == "__main__":
    unittest.main()
