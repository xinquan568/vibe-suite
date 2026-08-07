# SPDX-License-Identifier: ISC
"""Behavioural tests for the E8.3 findings helpers.

Fingerprints, backfills, diff, synthesizer and the rule-id validator. The mutation contract and
the shared primitives are in `auditor_helpers_support`.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditor_helpers_support import NOOP, REPO, SCRIPTS  # noqa: E402


class Test_validate_rule_ids(unittest.TestCase):
    """`validate-rule-ids.py` — and the audit it exists because of.

    The scoring skill records the incident: a 2026-05-13 audit applied "R07 / -15" fourteen
    times, wrong on both counts. R07 is the Skills scope-note row worth -3; -15 is a value from
    the Agents table. Every test here is anchored to that, because a membership test — "is R07
    in the catalog?" — passes it, and a membership test is the obvious implementation.
    """

    HELPER = SCRIPTS / "validate-rule-ids.py"
    RUBRIC = REPO / "skills" / "scoring" / "SKILL.md"
    MEMBERSHIP_ANCHOR = '    section = section_for(finding.get("category"), catalog)'
    MEMBERSHIP_MUTANT = '    return []  # membership-only: the id exists, so accept it'

    #: The real finding from the real incident.
    INCIDENT = {"rule_id": "R07", "category": "skill", "penalty": -15,
                "check": "zero <example> blocks", "confidence": "high"}
    #: What that finding should have been.
    CORRECT = {"rule_id": "R07", "category": "skill", "penalty": -3,
               "check": "no scope note / cross-references", "confidence": "high"}

    def _sidecar(self, findings, name="acme-widget.findings.jsonl"):
        d = Path(tempfile.mkdtemp())
        (d / "audits").mkdir()
        path = d / "audits" / name
        path.write_text("\n".join(json.dumps(f) for f in findings) + "\n", encoding="utf-8")
        return d, path

    def _run(self, argv, script_text=None):
        helper = self.HELPER
        if script_text is not None:
            root = Path(tempfile.mkdtemp())
            (root / "auditor" / "scripts").mkdir(parents=True)
            (root / "skills").symlink_to(REPO / "skills")
            helper = root / "auditor" / "scripts" / "validate-rule-ids.py"
            helper.write_text(script_text, encoding="utf-8")
        return subprocess.run([sys.executable, str(helper), *argv],
                              capture_output=True, text=True)

    # --- oracle ---------------------------------------------------------------------------
    def test_the_documented_incident_is_caught_on_both_counts(self):
        """R07 / -15 on an example-blocks finding. The rule is real, so an id-membership check
        passes it; both the penalty and the check it names are wrong."""
        d, _ = self._sidecar([self.INCIDENT])
        r = self._run(["--data-dir", str(d)])
        self.assertEqual(r.returncode, 1, "drift must be reported")
        self.assertIn("penalty-drift R07", r.stdout)
        self.assertIn("semantic-title-drift R07", r.stdout)

    def test_a_correct_finding_passes(self):
        d, _ = self._sidecar([self.CORRECT])
        r = self._run(["--data-dir", str(d)])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 drift", r.stdout)

    def test_artifact_type_drift_is_caught(self):
        """The right row number read from the wrong table."""
        d, _ = self._sidecar([{"rule_id": "R04", "category": "hook", "penalty": -25,
                               "check": "description present"}])
        r = self._run(["--data-dir", str(d)])
        self.assertEqual(r.returncode, 1)
        self.assertIn("artifact-type-drift R04", r.stdout)

    def test_an_unknown_rule_id_is_caught(self):
        d, _ = self._sidecar([{"rule_id": "R99", "category": "skill", "penalty": -5}])
        r = self._run(["--data-dir", str(d)])
        self.assertIn("unknown-rule-id R99", r.stdout)

    def test_an_unmapped_category_is_reported_not_skipped(self):
        """Otherwise an unrecognised category is a way to bypass the check entirely."""
        d, _ = self._sidecar([{"rule_id": "R04", "category": "widget", "penalty": -25}])
        r = self._run(["--data-dir", str(d)])
        self.assertEqual(r.returncode, 1)
        self.assertIn("unmapped-category", r.stdout)

    def test_false_positives_are_still_checked(self):
        """A false positive with a wrong rule id is evidence ABOUT the rulebook — it is the
        case where an auditor reached for a rule that does not fit."""
        finding = dict(self.INCIDENT, false_positive=True, fp_reason="intentional")
        d, _ = self._sidecar([finding])
        r = self._run(["--data-dir", str(d)])
        self.assertEqual(r.returncode, 1, "a false positive's rule id must still be checked")

    def test_a_check_belonging_to_an_unnumbered_row_is_caught_under_a_real_id(self):
        """`--` rows are checks with no dedicated id, so they are not loaded. "name matches
        parent dir" is one of them; filed under R04 it must surface as drift rather than
        quietly matching the unnumbered row it really belongs to.

        Note the penalty is deliberately -15, which R04 DOES allow (its trigger-quality row).
        A finding can therefore carry a legitimate penalty and still be about the wrong check,
        which is why the check text is compared and not only the number."""
        d, _ = self._sidecar([{"rule_id": "R04", "category": "skill", "penalty": -15,
                               "check": "name matches parent dir"}])
        r = self._run(["--data-dir", str(d)])
        self.assertEqual(r.returncode, 1)
        self.assertIn("semantic-title-drift R04", r.stdout)

    def test_an_absent_audits_directory_is_not_a_failure(self):
        r = self._run(["--data-dir", tempfile.mkdtemp()])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 sidecar(s)", r.stdout)

    def test_a_malformed_line_is_skipped_and_announced(self):
        d, path = self._sidecar([self.CORRECT])
        path.write_text(path.read_text() + "{TRUNCATED\n", encoding="utf-8")
        r = self._run(["--data-dir", str(d)])
        self.assertEqual(r.returncode, 0)
        self.assertIn("malformed", r.stderr)

    # --- refusals -------------------------------------------------------------------------
    def test_an_explicitly_named_missing_sidecar_is_refused(self):
        """Naming it asserts it exists. Skipping it silently would report "no drift" for a file
        that was never opened."""
        d = Path(tempfile.mkdtemp())
        r = self._run(["--data-dir", str(d), "--rubric", str(self.RUBRIC),
                       str(d / "audits" / "missing.findings.jsonl")])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:validate-rule-ids:input-missing", r.stderr)

    def test_a_missing_rubric_is_refused(self):
        r = self._run(["--data-dir", tempfile.mkdtemp(), "--rubric", "/nonexistent.md"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:validate-rule-ids:rubric-missing", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d, _ = self._sidecar([self.INCIDENT])
        r = self._run(["--data-dir", str(d)], script_text=NOOP[".py"])
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout, "", "sanity: a no-op reports nothing")

    def test_the_membership_only_mutant_passes_the_incident(self):
        """The plausible wrong implementation, and the one that was actually in place: accept
        any finding whose rule id exists somewhere in the catalog.

        It runs clean, prints "0 drifts", and lets fourteen wrong findings go to a maintainer.
        """
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.MEMBERSHIP_ANCHOR, src, "mutation anchor missing")
        d, _ = self._sidecar([self.INCIDENT])
        r = self._run(["--data-dir", str(d)],
                      script_text=src.replace(self.MEMBERSHIP_ANCHOR, self.MEMBERSHIP_MUTANT, 1))
        self.assertEqual(r.returncode, 0,
                         "mutation ineffective: the mutant should wave the incident through")
        self.assertIn("0 drift", r.stdout)


if __name__ == "__main__":
    unittest.main()
