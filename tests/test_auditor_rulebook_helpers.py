# SPDX-License-Identifier: ISC
"""Behavioural tests for the E8.3 rulebook helpers.

Rule health, its validation gate, refinement input, rule review bodies and citations. These
helpers decide which rules get weakened, rewritten or retired, so every count they produce
eventually argues for changing the rulebook. The mutation contract and shared primitives are in
`auditor_helpers_support`.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditor_helpers_support import NOOP, REPO, SCRIPTS  # noqa: E402


def envelope(event, data, timestamp):
    return {"timestamp": timestamp, "workflow": "t", "event": event,
            "run_id": "1", "run_number": 1, "data": data}


class Test_rule_health(unittest.TestCase):
    """`rule-health.py` — the dataset that argues for changing the rulebook."""

    HELPER = SCRIPTS / "rule-health.py"
    HITS_ANCHOR = '    for fingerprint, rule in rule_of.items():'
    HITS_MUTANT = '    for fingerprint, rule in [((e.get("data") or {}).get("fingerprint"),\n                              str((e.get("data") or {}).get("rule_id")))\n                             for e in events\n                             if (e.get("data") or {}).get("fingerprint")\n                             and (e.get("data") or {}).get("rule_id")]:'

    #: One finding, reported three times — audit, re-audit, backfill — which is ordinary for an
    #: append-only ledger. And one outcome that CHANGED as the maintainer responded.
    EVENTS = [
        envelope("finding_recorded", {"fingerprint": "fp-a", "rule_id": "R04"},
                 "2026-01-01T00:00:00Z"),
        envelope("finding_recorded", {"fingerprint": "fp-a", "rule_id": "R04"},
                 "2026-02-01T00:00:00Z"),
        envelope("finding_recorded", {"fingerprint": "fp-a", "rule_id": "R04"},
                 "2026-03-01T00:00:00Z"),
        envelope("finding_recorded", {"fingerprint": "fp-b", "rule_id": "R04"},
                 "2026-01-05T00:00:00Z"),
        envelope("finding_recorded", {"fingerprint": "fp-c", "rule_id": "R05"},
                 "2026-01-06T00:00:00Z"),
        # fp-a: submitted, rejected, then the maintainer fixed it their own way.
        envelope("pr_outcome", {"fingerprint": "fp-a", "outcome": "submitted"},
                 "2026-04-01T00:00:00Z"),
        envelope("pr_outcome", {"fingerprint": "fp-a", "outcome": "rejected"},
                 "2026-05-01T00:00:00Z"),
        envelope("pr_outcome", {"fingerprint": "fp-a", "outcome": "applied_separately"},
                 "2026-06-01T00:00:00Z"),
        envelope("pr_outcome", {"fingerprint": "fp-b", "outcome": "merged"},
                 "2026-04-02T00:00:00Z"),
        envelope("pr_outcome", {"fingerprint": "fp-c", "outcome": "rejected"},
                 "2026-04-03T00:00:00Z"),
        envelope("finding_verified", {"fingerprint": "fp-b", "rule_id": "R04"},
                 "2026-07-01T00:00:00Z"),
        envelope("exemplar_published", {"rule_ids": ["R04"]}, "2026-07-02T00:00:00Z"),
    ]

    def _data_dir(self, events=None):
        d = Path(tempfile.mkdtemp())
        (d / "ledgers").mkdir()
        (d / "ledgers" / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in (self.EVENTS if events is None else events)),
            encoding="utf-8")
        return d

    def _run(self, d, script_text=None):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "rule-health.py"
            helper.write_text(script_text, encoding="utf-8")
        return subprocess.run([sys.executable, str(helper), "--data-dir", str(d),
                               "--generated-at", "2026-08-08T00:00:00Z"],
                              capture_output=True, text=True)

    def _rules(self, d):
        path = d / "feedback" / "log.json"
        if not path.is_file():
            return None
        return {r["rule_id"]: r for r in json.loads(path.read_text())["rules"]}

    # --- oracle ---------------------------------------------------------------------------
    def test_hits_count_unique_findings_not_events(self):
        """The ledger is append-only and the same finding is logged repeatedly as a matter of
        course. Counting events makes a rule look busier every time anything is re-run — and
        the rules re-run most are the ones already under suspicion, so the noisiest-looking
        rule becomes noisier the more it is investigated."""
        d = self._data_dir()
        r = self._run(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._rules(d)["R04"]["hits"], 2, "fp-a was logged three times")
        self.assertEqual(self._rules(d)["R05"]["hits"], 1)

    def test_only_the_latest_outcome_for_a_finding_counts(self):
        """fp-a went submitted -> rejected -> applied_separately. Summing them counts one
        finding three times and lets it be both rejected and accepted."""
        rules = self._rules_after()
        self.assertEqual(rules["R04"]["rejected"], 0, "a superseded rejection still counted")
        self.assertEqual(rules["R04"]["applied_separately"], 1)
        self.assertEqual(rules["R04"]["merged"], 1)
        self.assertEqual(rules["R04"]["resolved"], 2)

    def test_applied_separately_is_acceptance(self):
        """The maintainer fixed the problem and closed our PR. The finding was right."""
        rules = self._rules_after()
        self.assertEqual(rules["R04"]["acceptance_rate"], 1.0,
                         "merged + applied_separately of 2 resolved is 100%")
        self.assertEqual(rules["R05"]["acceptance_rate"], 0.0)

    def test_verified_and_exemplar_counts_are_carried(self):
        rules = self._rules_after()
        self.assertEqual(rules["R04"]["verified"], 1)
        self.assertEqual(rules["R04"]["exemplars"], 1)
        self.assertEqual(rules["R05"]["exemplars"], 0)

    def test_the_log_is_written_atomically(self):
        """Every consumer reads this file whole, so a partial write would be parsed as a
        smaller, entirely plausible dataset rather than failing."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn("os.replace", src)
        self.assertIn("dir=str(path.parent)", src, "a /tmp temp file makes rename non-atomic")

    def test_an_empty_ledger_produces_an_empty_but_valid_log(self):
        d = self._data_dir(events=[])
        r = self._run(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._rules(d), {})

    def test_a_missing_data_dir_is_refused(self):
        r = subprocess.run([sys.executable, str(self.HELPER), "--data-dir", "/nonexistent"],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:rule-health:data-dir-missing", r.stderr)

    def _rules_after(self):
        d = self._data_dir()
        self._run(d)
        return self._rules(d)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d = self._data_dir()
        self._run(d, script_text=NOOP[".py"])
        self.assertIsNone(self._rules(d), "sanity: a no-op writes no log")

    def test_the_per_event_mutant_inflates_the_rule_that_was_re_run(self):
        """The plausible wrong implementation: one hit per event. fp-a was logged three times,
        so R04 looks 50% noisier than it is — and looks noisier still after the next re-audit."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.HITS_ANCHOR, src, "mutation anchor missing")
        d = self._data_dir()
        r = self._run(d, script_text=src.replace(self.HITS_ANCHOR, self.HITS_MUTANT, 1))
        self.assertEqual(r.returncode, 0, r.stderr + "\nthe mutant should run clean")
        self.assertEqual(self._rules(d)["R04"]["hits"], 5,
                         "mutation ineffective: the mutant should count every event")

    def test_the_applied_separately_as_rejection_mutant_condemns_a_correct_rule(self):
        """The plausible wrong implementation: treat applied_separately as rejection. The rules
        most often fixed-then-closed are the simple, obviously-correct ones, so the mistake
        falls hardest on the best rules in the book."""
        src = self.HELPER.read_text(encoding="utf-8")
        mutant = (src.replace('ACCEPTED = ("merged", "applied_separately")',
                              'ACCEPTED = ("merged",)', 1)
                     .replace('REJECTED = ("rejected",)',
                              'REJECTED = ("rejected", "applied_separately")', 1))
        self.assertNotEqual(mutant, src, "mutation anchors missing")
        d = self._data_dir()
        self._run(d, script_text=mutant)
        self.assertEqual(self._rules(d)["R04"]["acceptance_rate"], 0.5,
                         "mutation ineffective: a correct rule should now look half wrong")


class Test_validate_feedback(unittest.TestCase):
    """`validate-feedback.sh` — the gate between a rebuild bug and a rulebook change."""

    HELPER = SCRIPTS / "validate-feedback.sh"
    VALID = {"schema_version": 1, "rules": [
        {"rule_id": "R04", "hits": 10, "submitted": 6, "merged": 3, "rejected": 2},
        {"rule_id": "nl:R7", "hits": 4, "submitted": 2, "merged": 1, "rejected": 0}]}

    def _log(self, payload, write=True):
        d = Path(tempfile.mkdtemp())
        (d / "feedback").mkdir()
        if write:
            text = payload if isinstance(payload, str) else json.dumps(payload)
            (d / "feedback" / "log.json").write_text(text, encoding="utf-8")
        return d

    def _run(self, d, extra=(), script_text=None):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "validate-feedback.sh"
            helper.write_text(script_text, encoding="utf-8")
        return subprocess.run(["bash", str(helper), "--data-dir", str(d), *extra],
                              capture_output=True, text=True)

    # --- oracle ---------------------------------------------------------------------------
    def test_a_valid_log_passes(self):
        r = self._run(self._log(self.VALID))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok (2 rule(s))", r.stdout)

    def test_malformed_json_fails(self):
        """A partial write parses as a smaller, entirely plausible dataset."""
        r = self._run(self._log("{not json", ))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("malformed-json", r.stderr)

    def test_an_invalid_rule_id_fails(self):
        """The aggregation keyed on something that is not a rule, so every count under it is
        attributed to nothing."""
        r = self._run(self._log({"rules": [{"rule_id": "BOGUS", "hits": 1}]}))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("invalid-rule-id: BOGUS", r.stderr)

    def test_a_negative_count_fails(self):
        r = self._run(self._log({"rules": [{"rule_id": "R04", "hits": -2}]}))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("negative-count", r.stderr)

    def test_more_resolved_than_submitted_fails(self):
        """Guarantees double-counting upstream, and it is the shape duplicate events produce."""
        r = self._run(self._log({"rules": [
            {"rule_id": "R04", "hits": 9, "submitted": 2, "merged": 5, "rejected": 3}]}))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("resolved-exceeds-submitted", r.stderr)

    def test_every_violation_is_reported_not_just_the_first(self):
        """A rebuild bug usually breaks many rows the same way; one row per run turns one fix
        into twenty runs."""
        r = self._run(self._log({"rules": [
            {"rule_id": "BAD1", "hits": 1}, {"rule_id": "BAD2", "hits": -1}]}))
        self.assertIn("invalid-rule-id: BAD1", r.stderr)
        self.assertIn("negative-count: BAD2", r.stderr)
        # The reported total must equal the number of lines reported. Pinning a literal here
        # would encode an implementation detail: a negative `hits` also drags `submitted`
        # negative, so one bad row can legitimately raise more than one violation.
        lines = [x for x in r.stderr.splitlines() if not x.startswith("REFUSE:")]
        self.assertRegex(r.stderr, rf"REFUSE:validate-feedback:invalid {len(lines)} violation")

    def test_a_missing_log_fails_after_bootstrap(self):
        """rule-health.py runs before this and always writes the file, so after bootstrap an
        absent log means the rebuild did not happen — not that there is no feedback."""
        r = self._run(self._log(None, write=False))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:validate-feedback:log-missing", r.stderr)

    def test_a_missing_log_is_allowed_only_when_asked_for(self):
        r = self._run(self._log(None, write=False), extra=("--allow-missing",))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("pre-bootstrap", r.stdout)

    def test_a_non_object_log_fails(self):
        r = self._run(self._log([{"rule_id": "R04"}]))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("schema-invalid", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        r = self._run(self._log({"rules": [{"rule_id": "BOGUS", "hits": -1}]}),
                      script_text=NOOP[".sh"])
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stderr, "", "sanity: a no-op reports nothing")

    def test_the_lenient_missing_log_mutant_turns_a_lost_rebuild_green(self):
        """The reference behaviour: a missing log is a warning and the check passes. The
        consumer downstream then reads a stale log, or none, and reports every rule healthy.
        """
        src = self.HELPER.read_text(encoding="utf-8")
        anchor = ("  echo \"REFUSE:validate-feedback:log-missing $LOG\" >&2\n"
                  "  exit 1")
        lenient = ("  echo \"validate-feedback: $LOG absent (warning)\"\n"
                   "  exit 0")
        self.assertIn(anchor, src, "mutation anchor missing")
        mutant = src.replace(anchor, lenient, 1)
        r = self._run(self._log(None, write=False), script_text=mutant)
        self.assertEqual(r.returncode, 0,
                         "mutation ineffective: the mutant should pass a missing log")


if __name__ == "__main__":
    unittest.main()
