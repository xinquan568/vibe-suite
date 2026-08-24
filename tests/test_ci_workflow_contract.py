#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Workflow-contract tests for `.github/workflows/ci.yml` (vibe-194).

Two mechanical properties of the CI workflow, pinned after grill finding H13:

* every job carries an agreed `timeout-minutes` (a hung `sleeper.mjs`/`hanger.mjs`
  tree must fail in minutes, not GitHub's 360-minute default), and
* no comment claims a job count for the required status contexts — the historical
  defect was the count ("three job names are required") drifting from the
  server-side branch-protection state, so any count adjacent to "job(s)" is
  rejected rather than corrected, and the canonical enumeration of the required
  contexts lives exactly once, in the file header, where there is a single site
  to keep accurate.

Text-based on purpose (the `TestCIWiring` precedent): the environment does not
guarantee a YAML parser, and the properties under test are textual.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# One row per job, deliberately exhaustive: a job added without a row here is a
# failure, so a new job lands only together with a conscious timeout choice.
EXPECTED_TIMEOUTS = {
    "manifest-validation": 10,
    "lint": 10,
    "loop-bounds": 10,
    "test": 25,
    "coverage": 10,
    "legacy-strings": 10,
}

# Digits, zero through nineteen, the tens, hundred/dozen, and hyphenated
# compounds (twenty-one) — any of them adjacent to "job(s)" is a count claim.
COUNT_ADJACENT_TO_JOBS = re.compile(
    r"(?i)\b(?:\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten"
    r"|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen"
    r"|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
    r"|hundred|dozen)(?:-\w+)?\s+jobs?\b"
)

REQUIRED_CONTEXTS_SENTENCE = (
    "the required status contexts on main are `manifest validation`, "
    "`lint (python + node)`, `test`, and `coverage (AC-1)`"
)


def job_blocks(text):
    """Split the top-level ``jobs:`` section into an ordered {job_key: block} dict."""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line == "jobs:")
    except StopIteration:
        raise AssertionError("no top-level jobs: line in ci.yml")
    blocks = {}
    key = None
    for line in lines[start + 1:]:
        if line and not line.startswith(" ") and not line.startswith("#"):
            break  # a later top-level key would end the jobs section
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            key = match.group(1)
            blocks[key] = []
        elif key is not None:
            blocks[key].append(line)
    return {k: "\n".join(v) for k, v in blocks.items()}


def header_region(text):
    """The file's leading comment block: every line before the first line that
    is neither empty nor a comment (currently ``name: ci``)."""
    kept = []
    for line in text.splitlines():
        if line and not line.lstrip().startswith("#"):
            break
        kept.append(line)
    return "\n".join(kept)


class TestCIWorkflowContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_every_job_carries_the_agreed_timeout(self):
        blocks = job_blocks(self.text)
        self.assertEqual(
            set(blocks),
            set(EXPECTED_TIMEOUTS),
            "job set drifted from the timeout table — a new or renamed job "
            "needs a row (and a conscious timeout choice) here",
        )
        for job, minutes in EXPECTED_TIMEOUTS.items():
            found = re.findall(r"^\s+timeout-minutes:\s*(\d+)\s*$", blocks[job], re.M)
            self.assertEqual(
                found,
                [str(minutes)],
                f"job {job!r} must carry exactly one timeout-minutes: {minutes}",
            )

    def test_no_comment_claims_a_job_count(self):
        self.assertNotRegex(self.text, COUNT_ADJACENT_TO_JOBS)

    def test_the_header_names_the_required_contexts_exactly_once(self):
        self.assertEqual(
            self.text.count(REQUIRED_CONTEXTS_SENTENCE),
            1,
            "the canonical required-contexts enumeration must appear exactly once",
        )
        self.assertIn(
            REQUIRED_CONTEXTS_SENTENCE,
            header_region(self.text),
            "the canonical enumeration must live in the header comment block",
        )


if __name__ == "__main__":
    unittest.main()
