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

    #: One finding, reported three times — audit, re-audit, backfill — which is ordinary for
    #: an append-only ledger.
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
        # SCHEMAS.md: singular fingerprint, and an `outcome` from the fixed_*/persists_* enum.
        envelope("finding_verified",
                 {"repo": "acme/w", "fingerprint": "fp-b", "rule_id": "R04",
                  "outcome": "fixed_and_merged"}, "2026-07-01T00:00:00Z"),
        # A finding that still persists is recorded through the SAME event and must not count.
        envelope("finding_verified",
                 {"repo": "acme/w", "fingerprint": "fp-c", "rule_id": "R05",
                  "outcome": "persists_line_shifted"}, "2026-07-01T00:00:00Z"),
    ]

    #: The registry is where adjudications live. fp-a was attempted twice: an earlier PR closed
    #: unmerged, then a later one the maintainer fixed their own way.
    REGISTRY = {"repos": {"acme/w": {"prs": {
        "1": {"number": 1, "updatedAt": "2026-04-01T00:00:00Z", "outcome": "rejected",
              "fingerprints": ["fp-a"], "rule_ids": ["R04"]},
        "2": {"number": 2, "updatedAt": "2026-06-01T00:00:00Z",
              "outcome": "applied_separately", "fingerprints": ["fp-a"], "rule_ids": ["R04"]},
        "3": {"number": 3, "updatedAt": "2026-04-02T00:00:00Z", "outcome": "merged",
              "fingerprints": ["fp-b"], "rule_ids": ["R04"]},
        "4": {"number": 4, "updatedAt": "2026-04-03T00:00:00Z", "outcome": "rejected",
              "fingerprints": ["fp-c"], "rule_ids": ["R05"]},
    }}}}

    #: `exemplifies` is the join key, read from the exemplar files themselves.
    EXEMPLARS = {"acme-w.md": "---\nslug: acme-w\nrepo: acme/w\naudited: 2026-07-02\n"
                              "commit_sha: x\nscore: 95\nexemplifies: [R04]\n---\nbody\n"}

    def _data_dir(self, events=None, registry=None, exemplars=None):
        d = Path(tempfile.mkdtemp())
        (d / "ledgers").mkdir()
        (d / "registry").mkdir()
        (d / "exemplars").mkdir()
        (d / "ledgers" / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in (self.EVENTS if events is None else events)),
            encoding="utf-8")
        (d / "registry" / "repos.json").write_text(
            json.dumps(self.REGISTRY if registry is None else registry), encoding="utf-8")
        for name, text in (self.EXEMPLARS if exemplars is None else exemplars).items():
            (d / "exemplars" / name).write_text(text, encoding="utf-8")
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

    def test_applied_separately_is_acceptance(self):
        """The maintainer fixed the problem and closed our PR. The finding was right."""
        rules = self._rules_after()
        self.assertEqual(rules["R04"]["acceptance_rate"], 1.0,
                         "merged + applied_separately of 2 resolved is 100%")
        self.assertEqual(rules["R05"]["acceptance_rate"], 0.0)

    def test_the_log_is_written_atomically(self):
        """Every consumer reads this file whole, so a partial write would be parsed as a
        smaller, entirely plausible dataset rather than failing."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn("os.replace", src)
        self.assertIn("dir=str(path.parent)", src, "a /tmp temp file makes rename non-atomic")

    def test_an_empty_corpus_produces_an_empty_but_valid_log(self):
        """A registry with no PRs and no findings is a fresh install, not a failure."""
        d = self._data_dir(events=[], registry={"repos": {}}, exemplars={})
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


    def test_outcomes_come_from_the_registry_not_the_event_stream(self):
        """SCHEMAS.md puts the pipeline outcome enum on the REGISTRY's PR record.
        `finding_outcome` events carry `pr_state` — a different enum — and `fingerprints[]` /
        `rule_ids[]` as parallel ARRAYS. Reading a singular `outcome` off those events matches
        nothing, so every rule reports zero resolutions, which reads as "no maintainer has
        responded yet" rather than as a broken join.
        """
        d = self._data_dir(events=[
            envelope("finding_recorded", {"fingerprint": "fp-a", "rule_id": "R04"},
                     "2026-01-01T00:00:00Z"),
            # The real event shape. A helper keying on a singular `outcome` sees nothing here.
            envelope("finding_outcome",
                     {"pr": 2, "pr_state": "merged", "fingerprints": ["fp-a"],
                      "rule_ids": ["R04"]}, "2026-06-01T00:00:00Z"),
        ])
        self._run(d)
        self.assertEqual(self._rules(d)["R04"]["applied_separately"], 1,
                         "the registry's adjudication was not used")

    def test_the_latest_pr_wins_when_a_finding_was_attempted_twice(self):
        """fp-a was rejected on PR 1 and applied separately on PR 2. The maintainer's latest
        word is the answer; summing both counts one finding twice."""
        rules = self._rules_after()
        self.assertEqual(rules["R04"]["rejected"], 0)
        self.assertEqual(rules["R04"]["applied_separately"], 1)

    def test_parallel_rule_ids_join_by_position(self):
        """`rule_ids` is parallel to `fingerprints`. Keying a dict on the rule id instead would
        drop a PR that fixed two findings under one rule."""
        d = self._data_dir(events=[], registry={"repos": {"acme/w": {"prs": {
            "9": {"number": 9, "updatedAt": "2026-06-01T00:00:00Z", "outcome": "merged",
                  "fingerprints": ["fp-x", "fp-y"], "rule_ids": ["R07", "R07"]}}}}})
        self._run(d)
        self.assertEqual(self._rules(d)["R07"]["hits"], 2,
                         "two findings under one rule collapsed to one")

    def test_only_fixed_outcomes_count_as_verified(self):
        """`finding_verified` records persistence too, through the same event name. Counting
        every one of them would report a still-open finding as confirmation the rule works."""
        rules = self._rules_after()
        self.assertEqual(rules["R04"]["verified"], 1, "fp-b was fixed_and_merged")
        self.assertEqual(rules["R05"]["verified"], 0, "fp-c persists_line_shifted")

    def test_exemplar_counts_come_from_exemplifies(self):
        rules = self._rules_after()
        self.assertEqual(rules["R04"]["exemplars"], 1)
        self.assertEqual(rules["R05"]["exemplars"], 0)

    def test_a_missing_registry_is_refused(self):
        """Without it every finding looks unresolved — the most reassuring way to be wrong."""
        d = self._data_dir()
        (d / "registry" / "repos.json").unlink()
        r = self._run(d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:rule-health:registry-missing", r.stderr)


    def test_enveloped_finding_rows_are_read(self):
        """auditor-audit.yml appends findings through its `envelope` helper, so what is on disk
        is `{timestamp, workflow, event, run_id, run_number, data: {...}}` — while SCHEMAS.md
        section 2 documents a flat record. Reading only the flat shape sees no repo, no rule_id
        and no false_positive flag, so every rule reports a 0% false-positive rate: the most
        flattering possible answer, and the one that argues for changing nothing.
        """
        d = self._data_dir(events=[], registry={"repos": {"acme/w": {"prs": {
            "1": {"number": 1, "updatedAt": "2026-06-01T00:00:00Z", "outcome": "merged",
                  "fingerprints": ["fp-env"], "rule_ids": ["R42"]}}}}}, exemplars={})
        (d / "ledgers" / "findings.jsonl").write_text(json.dumps({
            "timestamp": "2026-01-01T00:00:00Z", "workflow": "auditor-audit",
            "event": "finding", "run_id": "1", "run_number": 1,
            "data": {"repo": "acme/w", "fingerprint": "fp-env", "rule_id": "R42",
                     "false_positive": True}}) + "\n", encoding="utf-8")
        r = self._run(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self._rules(d)["R42"]
        self.assertEqual(row["false_positives"], 1, "the enveloped payload was not unwrapped")
        self.assertEqual(row["merged"], 1)
        self.assertEqual(row["false_positive_rate"], 1.0)


    def test_self_false_positives_come_from_the_disagreements_ledger(self):
        """SCHEMAS.md section 5: a self-invalidated finding is emitted as a
        `self_false_positive` DISAGREEMENT event, not as a flag on a finding — and raw sidecars
        have no `false_positive` field at all. Reading one produced a 0% false-positive rate for
        every rule: the most flattering possible number, and the one that argues for changing
        nothing. A rule that fires on non-problems was therefore invisible to the dataset whose
        entire job is to surface it.
        """
        d = self._data_dir(events=[], exemplars={}, registry={"repos": {"a/b": {"prs": {
            "1": {"number": 1, "updatedAt": "2026-06-01T00:00:00Z", "outcome": "rejected",
                  "fingerprints": ["fp1"], "rule_ids": ["R09"]}}}}})
        (d / "ledgers" / "disagreements.jsonl").write_text(json.dumps(
            envelope("self_false_positive",
                     {"repo": "a/b", "fingerprint": "fp1", "rule_id": "R09",
                      "reason": "intentional pattern", "rule_gap": "needs an exemption"},
                     "2026-05-01T00:00:00Z")) + "\n", encoding="utf-8")
        r = self._run(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self._rules(d)["R09"]
        self.assertEqual(row["false_positives"], 1, "the disagreement event was not counted")
        self.assertEqual(row["false_positive_rate"], 1.0)


    def test_an_ambiguous_slug_is_refused(self):
        """`a/b-c` and `a-b/c` both slug to `a-b-c`. Resolving by iteration order attributes one
        repository's sidecar to the other and computes every fingerprint under the wrong repo —
        records that look valid and join to nothing. render-repo-report already refuses this."""
        d = self._data_dir(events=[], exemplars={}, registry={"repos": {
            "acme/w-x": {"prs": {}}, "acme-w/x": {"prs": {}}}})
        (d / "audits").mkdir(exist_ok=True)
        r = self._run(d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:rule-health:slug-collision", r.stderr)

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


    def test_schema_valid_rule_ids_are_accepted(self):
        """`rule_id` is "a namespaced rule identifier" (SCHEMAS.md section 2), not one rubric's
        R-numbers. UNCLASSIFIED is what the renderers themselves emit for a finding with no id.
        Rejecting a real pipeline's own output as corrupt trains whoever sees it to ignore this
        gate — the one failure mode a gate cannot recover from."""
        r = self._run(self._log({"rules": [
            {"rule_id": "SEC-001", "hits": 3, "submitted": 2, "merged": 1, "rejected": 0},
            {"rule_id": "BUG-x_9", "hits": 1, "submitted": 1, "merged": 1, "rejected": 0},
            {"rule_id": "nl:CC-7", "hits": 2, "submitted": 2, "merged": 1,
             "applied_separately": 1, "rejected": 0},
            {"rule_id": "UNCLASSIFIED", "hits": 1, "submitted": 1, "merged": 0, "rejected": 1},
        ]}))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_applied_separately_counts_toward_the_resolved_invariant(self):
        """It IS a resolution — the maintainer fixed it and closed our PR. Leaving it out of the
        sum let a genuine over-count hide behind the one arm most likely to grow, and
        contradicted rule-health, which counts it as acceptance."""
        r = self._run(self._log({"rules": [
            {"rule_id": "R04", "hits": 9, "submitted": 2,
             "merged": 1, "applied_separately": 1, "rejected": 1}]}))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("resolved-exceeds-submitted", r.stderr)
        self.assertIn("applied_separately=1", r.stderr)

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



class Test_prepare_refinement_input(unittest.TestCase):
    """`prepare-refinement-input.py` — the filter IS the value."""

    HELPER = SCRIPTS / "prepare-refinement-input.py"
    FLOOR_ANCHOR = '    if hits < min_hits:'
    FLOOR_MUTANT = '    if hits < 0:'

    RULES = [
        # healthy and busy: must never be selected, however often it fired
        {"rule_id": "R01", "hits": 200, "resolved": 100, "acceptance_rate": 0.95,
         "false_positive_rate": 0.01},
        # disputed, enough hits to mean something
        {"rule_id": "R02", "hits": 10, "resolved": 8, "acceptance_rate": 0.10,
         "false_positive_rate": 0.05},
        # noisy, enough hits
        {"rule_id": "R03", "hits": 20, "resolved": 5, "acceptance_rate": 0.80,
         "false_positive_rate": 0.60},
        # disputed on ONE hit: a single maintainer having a bad day
        {"rule_id": "R04", "hits": 1, "resolved": 1, "acceptance_rate": 0.0,
         "false_positive_rate": 1.0},
        # two hits: still below the confidence floor
        {"rule_id": "R05", "hits": 2, "resolved": 2, "acceptance_rate": 0.0,
         "false_positive_rate": 1.0},
        # more disputed than R02 but fewer hits, to pin the sort
        {"rule_id": "R06", "hits": 4, "resolved": 4, "acceptance_rate": 0.0,
         "false_positive_rate": 0.0},
    ]

    def _data_dir(self, rules=None, findings=None):
        d = Path(tempfile.mkdtemp())
        (d / "feedback").mkdir()
        (d / "audits").mkdir()
        (d / "feedback" / "log.json").write_text(
            json.dumps({"rules": self.RULES if rules is None else rules}), encoding="utf-8")
        if findings:
            (d / "audits" / "x.findings.jsonl").write_text(
                "".join(json.dumps(f) + "\n" for f in findings), encoding="utf-8")
        return d

    def _run(self, d, script_text=None):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "prepare-refinement-input.py"
            helper.write_text(script_text, encoding="utf-8")
        r = subprocess.run([sys.executable, str(helper), "--data-dir", str(d)],
                           capture_output=True, text=True)
        return r, (json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None)

    # --- oracle ---------------------------------------------------------------------------
    def test_a_healthy_rule_is_never_selected_however_often_it_fired(self):
        """A rule that fires 200 times and is accepted every time is the rulebook working.
        Putting it in front of a reviewer invites a change that breaks something correct."""
        _, out = self._run(self._data_dir())
        self.assertNotIn("R01", [r["rule_id"] for r in out["rules"]])

    def test_noisy_and_disputed_rules_are_selected(self):
        _, out = self._run(self._data_dir())
        selected = {r["rule_id"]: r["reasons"] for r in out["rules"]}
        self.assertIn("disputed", selected["R02"])
        self.assertIn("noisy", selected["R03"])

    def test_the_three_hit_floor_keeps_out_single_anecdotes(self):
        """One rejection of one hit is a 0% acceptance rate and means nothing. Acting on it
        rewrites rules from anecdotes — worse than not reviewing them, because the change
        carries the authority of a review."""
        _, out = self._run(self._data_dir())
        picked = [r["rule_id"] for r in out["rules"]]
        self.assertNotIn("R04", picked, "a one-hit rule was selected")
        self.assertNotIn("R05", picked, "a two-hit rule was selected")

    def test_disputed_sorts_above_noisy_then_hits_descending(self):
        """A noisy rule wastes our time; a disputed one wasted a maintainer's."""
        _, out = self._run(self._data_dir())
        self.assertEqual([r["rule_id"] for r in out["rules"]], ["R02", "R06", "R03"])

    def test_evidence_is_capped_at_five_and_says_so(self):
        """Forty examples of one failure is one fact presented forty times."""
        findings = [{"rule_id": "R02", "fingerprint": f"fp{i}", "file": f"f{i}.md", "line": i}
                    for i in range(12)]
        _, out = self._run(self._data_dir(findings=findings))
        row = next(r for r in out["rules"] if r["rule_id"] == "R02")
        self.assertEqual(len(row["evidence"]), 5)
        self.assertTrue(row["evidence_truncated"])

    def test_a_zero_acceptance_rate_is_not_treated_as_absent(self):
        """0.0 is the strongest possible dispute, and it is what truthiness throws away."""
        _, out = self._run(self._data_dir())
        self.assertIn("R06", [r["rule_id"] for r in out["rules"]])

    def test_a_missing_feedback_log_is_refused(self):
        """Selecting from nothing reports 'no rules need review' — the most reassuring possible
        way to be wrong."""
        d = Path(tempfile.mkdtemp())
        (d / "feedback").mkdir()
        r, _ = self._run(d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:prepare-refinement-input:feedback-missing", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        r, _ = self._run(self._data_dir(), script_text=NOOP[".py"])
        self.assertEqual(r.stdout, "", "sanity: a no-op emits nothing")

    def test_the_dropped_floor_mutant_admits_single_anecdotes(self):
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.FLOOR_ANCHOR, src, "mutation anchor missing")
        _, out = self._run(self._data_dir(),
                           script_text=src.replace(self.FLOOR_ANCHOR, self.FLOOR_MUTANT, 1))
        picked = [r["rule_id"] for r in out["rules"]]
        self.assertIn("R04", picked,
                      "mutation ineffective: the mutant should admit the one-hit rule")


class Test_generate_rule_review_body(unittest.TestCase):
    """`generate-rule-review-body.py` — the quarterly review issue."""

    HELPER = SCRIPTS / "generate-rule-review-body.py"
    STALE_ANCHOR = '        if confirmed < cutoff:'
    STALE_MUTANT = '        if confirmed > cutoff:'
    AS_OF = "2026-08-08"

    #: Real exemplar files, not a ledger: `exemplifies` is the join key SCHEMAS.md names and
    #: `audited` is the confirmation date. Both frontmatter shapes the exemplar workflow
    #: accepts are covered — a bracketed inline sequence and a block list.
    EXEMPLARS = {
        "fresh.md": "---\nslug: a\nrepo: acme/a\naudited: 2026-08-01\n"
                    "commit_sha: x\nscore: 95\nexemplifies: [R01]\n---\nbody\n",
        "old.md": "---\nslug: b\nrepo: acme/b\naudited: 2026-01-01\n"
                  "commit_sha: y\nscore: 92\nexemplifies:\n  - R02\n---\nbody\n",
        "ancient.md": "---\nslug: c\nrepo: acme/c\naudited: 2025-06-01\n"
                      "commit_sha: z\nscore: 91\nexemplifies: [R03]\n---\nbody\n",
    }
    #: Canonical: FIVE event types share this ledger, all enveloped. Only maintainer_rejected
    #: is a rejection, and its fields are pr/fingerprints[]/rule_ids[]/quote — not
    #: repo/rule_id/reason. The old fixture used the singular flat names, so it exercised the
    #: helper through a record the pipeline never writes.
    DISAGREEMENTS = [
        envelope("maintainer_rejected",
                 {"pr": 12, "fingerprints": ["f1", "f2"], "rule_ids": ["R02", "R07"],
                  "dissent_type": "style_disagreement", "commenter_role": "maintainer",
                  "quote": "we prefer this"}, "2026-05-02T00:00:00Z"),
        # captured AT that rejection — the same dispute, not a second one
        envelope("pr_comments_snapshot",
                 {"pr": 12, "fingerprints": ["f1"], "rule_ids": ["R02"], "comments": []},
                 "2026-05-02T00:00:00Z"),
        # our own invalidation, not a maintainer's
        envelope("self_false_positive",
                 {"repo": "acme/w", "fingerprint": "f9", "rule_id": "R51", "reason": "x"},
                 "2026-05-03T00:00:00Z"),
        envelope("maintainer_rejected",
                 {"pr": 3, "fingerprints": ["f0"], "rule_ids": ["R01"],
                  "dissent_type": "out_of_scope", "commenter_role": "maintainer",
                  "quote": "old quarter"}, "2026-02-01T00:00:00Z"),
    ]

    def _data_dir(self):
        d = Path(tempfile.mkdtemp())
        (d / "ledgers").mkdir()
        (d / "exemplars").mkdir()
        for name, text in self.EXEMPLARS.items():
            (d / "exemplars" / name).write_text(text, encoding="utf-8")
        (d / "ledgers" / "disagreements.jsonl").write_text(
            "".join(json.dumps(c) + "\n" for c in self.DISAGREEMENTS), encoding="utf-8")
        return d

    def _run(self, d, script_text=None, quarter="2026-Q2"):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "generate-rule-review-body.py"
            helper.write_text(script_text, encoding="utf-8")
        return subprocess.run([sys.executable, str(helper), "--data-dir", str(d),
                               "--quarter", quarter, "--as-of", self.AS_OF],
                              capture_output=True, text=True)

    # --- oracle ---------------------------------------------------------------------------
    def test_stale_means_older_than_ninety_days(self):
        r = self._run(self._data_dir())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("## Stale citations (2)", r.stdout)
        self.assertIn("R02", r.stdout)
        self.assertIn("R03", r.stdout)
        stale_section = r.stdout.split("## Stale citations")[1].split("## Rejections")[0]
        self.assertNotIn("R01", stale_section, "a citation confirmed a week ago is not stale")

    def test_stale_citations_sort_oldest_first(self):
        r = self._run(self._data_dir())
        section = r.stdout.split("## Stale citations")[1]
        self.assertLess(section.index("R03"), section.index("R02"))

    def test_only_this_quarters_maintainer_rejections_appear(self):
        """Snapshots and self-false-positives share this ledger. Counting them inflates the
        section with duplicates of the same dispute and with findings no maintainer ever saw."""
        r = self._run(self._data_dir())
        section = r.stdout.split("## Rejections")[1]
        self.assertIn("## Rejections this quarter (2)", r.stdout,
                      "one bundled rejection over two rules, snapshot and self-FP excluded")
        self.assertIn("R02", section)
        self.assertIn("R07", section, "the bundled PR's second rule was dropped")
        self.assertNotIn("R51", section, "a self-false-positive was counted as a rejection")
        self.assertNotIn("out_of_scope", section, "a Q1 rejection leaked into Q2")

    def test_rejection_rows_carry_real_values(self):
        """Reading singular repo/rule_id/reason off an enveloped record yields null for every
        one — a table of empty rows that still looks like a populated report."""
        r = self._run(self._data_dir())
        section = r.stdout.split("## Rejections")[1]
        self.assertIn("style_disagreement", section)
        self.assertIn("maintainer", section)
        self.assertIn("we prefer this", section)
        self.assertNotIn("| None |", section)

    def test_paths_point_at_this_suites_skills(self):
        """`skills/nlpm/...` 404s for every reviewer and is what the AC-6 sweep exists to
        catch."""
        r = self._run(self._data_dir())
        self.assertIn("skills/rules/SKILL.md", r.stdout)
        self.assertNotIn("skills/nlpm", r.stdout)

    def test_the_body_is_reproducible(self):
        d = self._data_dir()
        self.assertEqual(self._run(d).stdout, self._run(d).stdout)

    def test_an_invalid_quarter_is_refused(self):
        r = self._run(self._data_dir(), quarter="2026-Q9")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("quarter-invalid", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        r = self._run(self._data_dir(), script_text=NOOP[".py"])
        self.assertEqual(r.stdout, "", "sanity: a no-op emits nothing")

    def test_the_reversed_comparison_lists_the_freshest_citations(self):
        """`age < 90` reads perfectly: a plausible list under a heading saying the opposite,
        with every genuinely stale citation omitted."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.STALE_ANCHOR, src, "mutation anchor missing")
        r = self._run(self._data_dir(),
                      script_text=src.replace(self.STALE_ANCHOR, self.STALE_MUTANT, 1))
        self.assertIn("## Stale citations (1)", r.stdout,
                      "mutation ineffective: the mutant should list only the fresh citation")
        self.assertIn("R01", r.stdout.split("## Stale citations")[1].split("## Rejections")[0])


if __name__ == "__main__":
    unittest.main()
