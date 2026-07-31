#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Seeded-failure tests for the AC-3 acceptance evaluator (E4.1 / vibe-35).

`tools/nl-audit-acceptance.py` is the gate that decides whether an `/vibe-suite:nl-audit` run met
AC-3 on a fixture. A gate nobody has watched fail is not a gate, so every clause it checks -- the
detection floor, dimension attribution, and mini-membership exclusion -- has a case here that
**passes** and a case that **fails**, plus the boundary case at exactly the floor.

The distinction that makes this possible: running a live judgment engine needs a model, but *grading*
a run is arithmetic over two files. The inputs below are synthetic records, so the whole module is
hermetic and runs in CI with no engine, no network and no credentials.

Exit codes are part of the contract:

    0  every applicable clause passed
    1  a clause failed -- the finding is on stdout
    2  the input was malformed -- distinct, because a gate that crashes into a pass is not a gate
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "nl-audit-acceptance.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "nl-audit"

EXIT_OK, EXIT_CLAUSE_FAILED, EXIT_MALFORMED = 0, 1, 2


def _classes(fixture):
    return json.loads((FIXTURES / fixture / "seeded-defects.json").read_text(encoding="utf-8"))


def record(fixture, depth, entries):
    """A synthetic audit record in the shape `ACCEPTANCE.md` documents."""
    spec = _classes(fixture)
    return {"run": {"type": spec["type"], "depth": depth, "engine": "codex"},
            "findings": [{"class": cid, "dimension": dim} for cid, dim in entries]}


def all_findings(fixture, limit=None):
    spec = _classes(fixture)
    entries = [(c["id"], c["dimension"]) for c in spec["classes"]]
    return entries if limit is None else entries[:limit]


def run_tool(fixture, depth, payload, use_stdin=True):
    args = [sys.executable, str(TOOL), str(FIXTURES / fixture), "--%s" % depth]
    text = json.dumps(payload) if not isinstance(payload, str) else payload
    if use_stdin:
        return subprocess.run(args, input=text, capture_output=True, text=True, cwd=REPO_ROOT)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        fh.write(text)
        path = fh.name
    try:
        return subprocess.run(args + ["--findings", path],
                              capture_output=True, text=True, cwd=REPO_ROOT)
    finally:
        Path(path).unlink(missing_ok=True)


class EvaluatorTestCase(unittest.TestCase):
    def setUp(self):
        if not TOOL.is_file():
            self.skipTest("tools/nl-audit-acceptance.py does not exist yet")
        if not (FIXTURES / "defective-skill" / "seeded-defects.json").is_file():
            self.skipTest("the fixture corpus does not exist yet")


class TestDetectionFloorClause(EvaluatorTestCase):
    def test_case_1_all_classes_detected_passes(self):
        proc = run_tool("defective-skill", "full",
                        record("defective-skill", "full", all_findings("defective-skill")))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)

    def test_case_2_exactly_at_the_floor_passes(self):
        """8 of 10 is the floor for a ten-class fixture; the boundary must be inclusive."""
        proc = run_tool("defective-skill", "full",
                        record("defective-skill", "full", all_findings("defective-skill", 8)))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)

    def test_case_3_one_below_the_floor_fails(self):
        """The seeded failure for the rate clause."""
        proc = run_tool("defective-skill", "full",
                        record("defective-skill", "full", all_findings("defective-skill", 7)))
        self.assertEqual(proc.returncode, EXIT_CLAUSE_FAILED)
        self.assertIn("detection", (proc.stdout + proc.stderr).lower())

    def test_case_11_mixed_repo_uses_its_derived_floor(self):
        """mixed-repo has no literal floor in the sources -- ceil(0.75 * N) must be applied, not
        skipped for want of a stated number."""
        spec = _classes("mixed-repo")
        proc = run_tool("mixed-repo", "full",
                        record("mixed-repo", "full", all_findings("mixed-repo", spec["floor"])))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)
        below = run_tool("mixed-repo", "full",
                         record("mixed-repo", "full",
                                all_findings("mixed-repo", spec["floor"] - 1)))
        self.assertEqual(below.returncode, EXIT_CLAUSE_FAILED)


class TestAttributionClause(EvaluatorTestCase):
    def test_case_4_a_wrong_dimension_fails(self):
        """The seeded failure for the attribution clause: every class is found, but one is filed
        under the wrong dimension. A rate-only gate would pass this."""
        entries = all_findings("defective-command")
        entries = [(cid, "D1" if "interpolation" in cid or "arguments" in cid else dim)
                   for cid, dim in entries]
        proc = run_tool("defective-command", "full",
                        record("defective-command", "full", entries))
        self.assertEqual(proc.returncode, EXIT_CLAUSE_FAILED)
        self.assertIn("attribution", (proc.stdout + proc.stderr).lower())

    def test_case_7_repo_attributions_across_a_to_e_pass(self):
        proc = run_tool("mixed-repo", "full",
                        record("mixed-repo", "full", all_findings("mixed-repo")))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)

    def test_case_8_a_per_artifact_dimension_id_is_invalid_for_repo(self):
        entries = all_findings("mixed-repo")
        entries = [(entries[0][0], "D0")] + entries[1:]
        proc = run_tool("mixed-repo", "full", record("mixed-repo", "full", entries))
        self.assertEqual(proc.returncode, EXIT_CLAUSE_FAILED)


class TestMiniMembershipClause(EvaluatorTestCase):
    def _mini_entries(self, fixture, mini_ids):
        return [(c, d) for c, d in all_findings(fixture) if d in mini_ids]

    def test_case_5_mini_output_with_only_mini_members_passes(self):
        entries = self._mini_entries("defective-agent", {"D0", "D1", "D2", "D3"})
        proc = run_tool("defective-agent", "mini",
                        record("defective-agent", "mini", entries))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)

    def test_case_6_mini_output_leaking_a_full_only_dimension_fails(self):
        """The seeded failure for the exclusion clause."""
        entries = self._mini_entries("defective-agent", {"D0", "D1", "D2", "D3"})
        entries.append(("missing untrusted-input guard", "D6"))
        proc = run_tool("defective-agent", "mini",
                        record("defective-agent", "mini", entries))
        self.assertEqual(proc.returncode, EXIT_CLAUSE_FAILED)
        self.assertIn("mini", (proc.stdout + proc.stderr).lower())

    def test_the_detection_floor_does_not_apply_to_a_mini_run(self):
        """`--mini` audits fewer dimensions by design, so grading it against the full-run floor would
        fail every correct mini run. Line 627 states one assertion for mini, and this is it."""
        entries = self._mini_entries("defective-rules", {"D0", "D1", "D2", "D3"})
        proc = run_tool("defective-rules", "mini", record("defective-rules", "mini", entries))
        self.assertEqual(proc.returncode, EXIT_OK, proc.stdout + proc.stderr)


class TestMalformedInput(EvaluatorTestCase):
    def test_case_9a_non_json_input_fails_loudly(self):
        proc = run_tool("defective-skill", "full", "this is not json")
        self.assertEqual(proc.returncode, EXIT_MALFORMED)

    def test_case_9b_a_finding_without_a_dimension_fails_loudly(self):
        payload = {"run": {"type": "skill", "depth": "full", "engine": "codex"},
                   "findings": [{"class": "missing name"}]}
        proc = run_tool("defective-skill", "full", payload)
        self.assertEqual(proc.returncode, EXIT_MALFORMED)

    def test_a_findings_key_that_is_not_a_list_fails_loudly(self):
        payload = {"run": {"type": "skill", "depth": "full", "engine": "codex"}, "findings": {}}
        proc = run_tool("defective-skill", "full", payload)
        self.assertEqual(proc.returncode, EXIT_MALFORMED)

    def test_a_record_without_run_metadata_fails_loudly(self):
        """`ACCEPTANCE.md` requires provenance so a verdict can be attributed to an engine lane.
        Accepting a record without it would produce a verdict about an unidentified run."""
        payload = {"findings": [{"class": "missing name", "dimension": "D0"}]}
        self.assertEqual(run_tool("defective-skill", "full", payload).returncode, EXIT_MALFORMED)

    def test_each_run_field_is_required(self):
        for missing in ("type", "depth", "engine"):
            with self.subTest(field=missing):
                payload = record("defective-skill", "full", all_findings("defective-skill"))
                del payload["run"][missing]
                self.assertEqual(run_tool("defective-skill", "full", payload).returncode,
                                 EXIT_MALFORMED)

    def test_a_depth_mismatch_between_record_and_invocation_fails_loudly(self):
        """A mini record graded by the full clause set would be judged against a floor its run never
        aimed at -- a confident verdict about a run that did not happen."""
        payload = record("defective-skill", "full", all_findings("defective-skill"))
        payload["run"]["depth"] = "mini"
        self.assertEqual(run_tool("defective-skill", "full", payload).returncode, EXIT_MALFORMED)

    def test_a_type_mismatch_between_record_and_fixture_fails_loudly(self):
        payload = record("defective-skill", "full", all_findings("defective-skill"))
        payload["run"]["type"] = "agent"
        self.assertEqual(run_tool("defective-skill", "full", payload).returncode, EXIT_MALFORMED)

    def test_an_unknown_class_id_fails_loudly(self):
        """A class the fixture never seeded is not a detection -- silently ignoring it would let a
        run inflate its rate with invented findings."""
        payload = record("defective-skill", "full",
                         all_findings("defective-skill") + [("a class nobody seeded", "D0")])
        proc = run_tool("defective-skill", "full", payload)
        self.assertEqual(proc.returncode, EXIT_MALFORMED)


class TestOperatorInterface(EvaluatorTestCase):
    def test_findings_file_and_stdin_agree(self):
        """`--findings <path>` is the operator's interface (a session writes the file with the Write
        tool); stdin is the test interface. Both must reach the same verdict."""
        payload = record("defective-skill", "full", all_findings("defective-skill"))
        from_stdin = run_tool("defective-skill", "full", payload, use_stdin=True)
        from_file = run_tool("defective-skill", "full", payload, use_stdin=False)
        self.assertEqual(from_stdin.returncode, from_file.returncode)

    def test_json_mode_emits_a_parseable_verdict(self):
        payload = record("defective-skill", "full", all_findings("defective-skill", 7))
        proc = subprocess.run(
            [sys.executable, str(TOOL), str(FIXTURES / "defective-skill"), "--full", "--json"],
            input=json.dumps(payload), capture_output=True, text=True, cwd=REPO_ROOT)
        verdict = json.loads(proc.stdout)
        self.assertFalse(verdict["passed"])
        self.assertIn("detection_rate", verdict["clauses"])


class TestToolDiscipline(unittest.TestCase):
    """Case 12: `tools/` is in `model-pin-lint.py`'s EXCLUDED set ("not shipped as plugin
    functionality and not registered in the manifest"), so the repo-wide P9 scan does not reach this
    file. The check is placed here instead of assuming coverage that does not exist."""

    def test_the_evaluator_pins_no_model_id(self):
        if not TOOL.is_file():
            self.skipTest("tools/nl-audit-acceptance.py does not exist yet")
        import re
        pattern = re.compile(
            r"\b(?:gpt-\d|o\d-|gemini-\d|claude-(?:opus|sonnet|haiku|fable)-\d|claude-[a-z]+-20\d{2})",
            re.I)
        hit = pattern.search(TOOL.read_text(encoding="utf-8"))
        self.assertIsNone(hit, "the evaluator pins a model id: %s" % (hit.group(0) if hit else ""))

    def test_the_evaluator_carries_the_isc_spdx_header(self):
        if not TOOL.is_file():
            self.skipTest("tools/nl-audit-acceptance.py does not exist yet")
        head = TOOL.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in line for line in head),
                        "a new .py file needs the ISC SPDX header within its first 3 lines")

    def test_the_acceptance_runbook_exists(self):
        runbook = FIXTURES / "ACCEPTANCE.md"
        self.assertTrue(runbook.is_file(),
                        "tests/fixtures/nl-audit/ACCEPTANCE.md is the operator's runbook; without "
                        "it 'the operator runs the gate' has no addressee")


if __name__ == "__main__":
    unittest.main()
