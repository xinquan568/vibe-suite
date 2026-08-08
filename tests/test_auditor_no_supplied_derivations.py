# SPDX-License-Identifier: ISC
"""E8.2b: no test supplies a value the graph must derive (vibe-164).

The issue's acceptance clause, verbatim:

    the contribution path runs from real workflow inputs with **no test supplying a value the
    graph must derive** (enforced by a suite-wide scan covering environment variables *and*
    artifacts)

Why this exists, concretely. During E8.2b the relay was built across three waves and never
transported between jobs -- gates wrote context.json into its own runner's workspace and every
consumer read CONTEXT_FILE, but each job runs on a fresh runner and nothing uploaded or
downloaded it. Fifty-six new tests passed anyway, because every one of them set CONTEXT_FILE
to a local path. A test that hands the graph its answer cannot observe the graph failing to
produce one.

THE DISTINCTION THIS SCAN DRAWS. Supplying a *source* is legitimate; supplying an *answer* is
not.

  legitimate   a repo variable the graph reads and validates (AUDITOR_AUTHOR_NAME)
               a canned API response the graph must still parse (gh api user)
               a registry fixture carrying commit_sha_at_audit -- the graph's actual source
  violation    AUDITED_SHA / BASE_BRANCH / PATCH_CAP handed to a consumer as a loose env var,
               bypassing the relay the consumer is contracted to read
  violation    a fixture artifact carrying a derived answer rather than the input it derives from

LIVENESS. This scan is itself the kind of check that passes vacuously when it matches
nothing, so its failing state was observed per channel before it was allowed to count -- one
mutation cannot prove two channels:

  env      planting AUDITED_SHA in a test's env dict ->
           "test_auditor_quota.py:55: AUDITED_SHA — ..."
  artifact planting audited_sha in registry-audited.json ->
           "registry-audited.json: carries derived key 'audited_sha'"

Both were reverted. The distinct messages matter: they show each channel reports independently
rather than one assertion covering for the other.

ON ITS FIRST RUN this scan found a real defect, not just untidy tests. It flagged two suites
setting PATCH_CAP in the environment; following that pointed at emit-manifest reading
`${PATCH_CAP:-${PLANNED_COUNT:-0}}` while derive-context never exported PATCH_CAP to
$GITHUB_ENV. In production the cap would have silently fallen back to PLANNED_COUNT -- a
different quantity -- and F10.1's first-contact rule (3 on first contact, 5 thereafter) would
have been bypassed entirely. The tests were hiding it by supplying the answer.
"""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "tests"
FIXTURES = TESTS / "fixtures" / "auditor"

# Values gates derives. A consumer must read these from the relay, never from the environment.
DERIVED = ["AUDITED_SHA", "BASE_BRANCH", "PATCH_CAP", "EXPECTED_FORK_SLUG"]

# Modules allowed to set a given name because they exercise its DERIVATION, not its use.
# derive-context legitimately supplies the repo variables and trigger inputs gates reads.
SOURCE_SUITES = {"test_auditor_context.py"}

# Keys that are answers when they appear in a fixture artifact. commit_sha_at_audit is
# deliberately absent: it is the registry key the audit stage writes and gates reads, i.e. the
# source, and a fixture carrying it is modelling the world rather than the answer.
DERIVED_FIXTURE_KEYS = ["audited_sha", "base_branch", "patch_cap", "expected_fork_slug"]

AUDITOR_TESTS = "test_auditor_"


def _auditor_test_files():
    return sorted(p for p in TESTS.glob(f"{AUDITOR_TESTS}*.py")
                  if p.name != Path(__file__).name)


class TestNoSuppliedDerivations(unittest.TestCase):

    def test_no_test_supplies_a_derived_value_through_the_environment(self):
        """Channel 1 of 2: environment variables."""
        offenders = []
        for f in _auditor_test_files():
            if f.name in SOURCE_SUITES:
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
                if line.lstrip().startswith("#"):
                    continue
                for name in DERIVED:
                    # a dict entry or kwarg assigning the name as an env var
                    if re.search(rf'["\']{name}["\']\s*:', line):
                        offenders.append(f"{f.name}:{i}: {name} — {line.strip()[:72]}")
        self.assertEqual(
            [], offenders,
            "a test hands the graph a value gates is contracted to derive, bypassing the "
            "relay. Deliver it through context.json the way production does:\n  " +
            "\n  ".join(offenders))

    def test_no_fixture_artifact_carries_a_derived_answer(self):
        """Channel 2 of 2: artifacts. Proved separately -- one mutation cannot cover both."""
        offenders = []
        for f in sorted(FIXTURES.glob("*.json")) + sorted(FIXTURES.glob("*.jsonl")):
            text = f.read_text(encoding="utf-8")
            for key in DERIVED_FIXTURE_KEYS:
                if f'"{key}"' in text:
                    offenders.append(f"{f.name}: carries derived key '{key}'")
        self.assertEqual(
            [], offenders,
            "a fixture artifact carries a value the graph must derive rather than the input "
            "it derives from:\n  " + "\n  ".join(offenders))

    def test_the_scan_covers_every_auditor_test_module(self):
        """A scan that quietly stopped matching files would pass forever."""
        files = _auditor_test_files()
        self.assertGreaterEqual(
            len(files), 8,
            f"the scan found only {len(files)} auditor test modules; if the naming convention "
            f"changed it is now scanning almost nothing and will pass regardless")
