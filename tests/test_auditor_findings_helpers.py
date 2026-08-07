# SPDX-License-Identifier: ISC
"""Behavioural tests for the E8.3 findings helpers.

Fingerprints, backfills, diff, synthesizer and the rule-id validator. The mutation contract and
the shared primitives are in `auditor_helpers_support`.
"""
import json
import os
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



REPORT = """# Audit report — acme/widget
Score: 71/100
Security: CLEAR

## Skills

| Rule | File | Line | Issue | Penalty |
|---|---|---|---|---|
| R04 | skills/a/SKILL.md | 3 | description missing | -25 |
| -- | skills/b/SKILL.md | 12 | frontmatter name differs from parent dir | -15 |

## Agents

### R05 — body length over 500 lines
- **File**: agents/big.md
- **Line**: 501
- Penalty: -10
"""


class _FingerprintMixin:
    """Both helpers must agree with `compute-fingerprint.sh`, so both check against it."""

    def shell_fingerprint(self, record, repo="acme/widget"):
        helper = SCRIPTS / "compute-fingerprint.sh"
        snippet = (f". '{helper}'\n"
                   f"printf '%s' '{json.dumps(record)}' | compute_fingerprint '{repo}'")
        r = subprocess.run(["bash", "-c", snippet], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()


class Test_synthesize_sidecar(_FingerprintMixin, unittest.TestCase):
    """`synthesize-sidecar.py` — rebuilding a sidecar without re-keying the ledger."""

    HELPER = SCRIPTS / "synthesize-sidecar.py"
    SLUG_ANCHOR = '    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]'
    SLUG_MUTANT = '    words = list({w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS})'

    def _report(self, text=REPORT):
        d = Path(tempfile.mkdtemp())
        (d / "report.md").write_text(text, encoding="utf-8")
        return d / "report.md"

    def _run(self, report, script_text=None, extra=(), env=None):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "synthesize-sidecar.py"
            helper.write_text(script_text, encoding="utf-8")
        return subprocess.run([sys.executable, str(helper), "--repo", "acme/widget",
                               "--report", str(report), *extra],
                              capture_output=True, text=True, env=env)

    def _records(self, report, **kw):
        r = self._run(report, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [json.loads(x) for x in r.stdout.splitlines() if x.strip()]

    # --- oracle ---------------------------------------------------------------------------
    def test_both_legacy_shapes_are_parsed(self):
        """A per-section table and a per-finding subsection; both were produced."""
        records = self._records(self._report())
        self.assertEqual(len(records), 3)
        self.assertEqual([r["file"] for r in records],
                         ["skills/a/SKILL.md", "skills/b/SKILL.md", "agents/big.md"])
        self.assertEqual([r["category"] for r in records], ["skill", "skill", "agent"])
        self.assertEqual([r["line"] for r in records], [3, 12, 501])

    def test_the_fingerprint_matches_the_shell_helper(self):
        """The digest is a join key shared with the shell helper. Two implementations that
        disagree do not fail — they silently write records nothing joins to."""
        for record in self._records(self._report()):
            expected = self.shell_fingerprint({k: record[k] for k in
                                               ("file", "rule_id", "pattern", "line")})
            with self.subTest(file=record["file"]):
                self.assertEqual(record["fingerprint"], expected)

    def test_rerunning_is_byte_identical(self):
        report = self._report()
        self.assertEqual(self._run(report).stdout, self._run(report).stdout)

    def test_output_does_not_depend_on_the_hash_seed(self):
        """A set-derived slug varies with PYTHONHASHSEED, so the same report fingerprints
        differently on two machines — and re-running on one machine never reveals it."""
        report = self._report()
        seen = set()
        for seed in ("0", "1", "42"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            seen.add(self._run(report, env=env).stdout)
        self.assertEqual(len(seen), 1, "output varies with the hash seed")

    def test_no_field_in_the_digest_comes_from_the_clock(self):
        src = self.HELPER.read_text(encoding="utf-8")
        code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith(("#", "*")))
        for forbidden in ("datetime.now", "time.time", "utcnow"):
            self.assertNotIn(forbidden, code, f"{forbidden} would re-key every finding")

    def test_a_declared_rule_id_wins_over_inference(self):
        records = self._records(self._report())
        self.assertEqual(records[0]["rule_id"], "R04")
        self.assertEqual(records[2]["rule_id"], "R05")

    def test_an_unnumbered_row_keeps_a_stable_pattern_without_a_rule_id(self):
        records = self._records(self._report())
        self.assertIsNone(records[1]["rule_id"])
        self.assertEqual(records[1]["pattern"], "name-matches-parent-dir")

    # --- refusals -------------------------------------------------------------------------
    def test_a_missing_report_is_refused(self):
        r = self._run(Path("/nonexistent/report.md"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:synthesize-sidecar:report-missing", r.stderr)

    def test_a_slug_passed_as_the_repo_is_refused(self):
        r = subprocess.run([sys.executable, str(self.HELPER), "--repo", "acme-widget",
                            "--report", str(self._report())], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("repo-not-owner-name", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        r = self._run(self._report(), script_text=NOOP[".py"])
        self.assertEqual(r.stdout, "", "sanity: a no-op emits nothing")

    def test_the_unordered_token_mutant_varies_with_the_hash_seed(self):
        """The plausible wrong implementation: build the slug from a set of tokens.

        It looks tidier, it deduplicates words, and it silently re-keys findings between
        machines — the file still parses and every fingerprint still looks stable.
        """
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.SLUG_ANCHOR, src, "mutation anchor missing")
        mutant = src.replace(self.SLUG_ANCHOR, self.SLUG_MUTANT, 1)
        # A report whose finding falls through to the slug fallback, so the mutation is reached.
        report = self._report("## Skills\n\n| File | Issue |\n|---|---|\n"
                              "| skills/x/SKILL.md | inconsistent heading capitalisation "
                              "throughout the document body |\n")
        seen = {self._run(report, script_text=mutant,
                          env=dict(os.environ, PYTHONHASHSEED=s)).stdout
                for s in ("0", "1", "42")}
        self.assertGreater(len(seen), 1,
                           "mutation ineffective: the mutant should vary with the hash seed")


class Test_backfill_findings(_FingerprintMixin, unittest.TestCase):
    """`backfill-findings.py` — append what is missing, touch nothing else."""

    HELPER = SCRIPTS / "backfill-findings.py"
    NL_ANCHOR = '    )) + "\\n"'
    NL_MUTANT = '    ))'

    def _fixture(self, existing=None, trailing_newline=True):
        d = Path(tempfile.mkdtemp())
        (d / "report.md").write_text(REPORT, encoding="utf-8")
        sidecar = d / "acme-widget.findings.jsonl"
        if existing is not None:
            text = "".join(json.dumps(e, sort_keys=True) + "\n" for e in existing)
            if not trailing_newline and text:
                text = text[:-1]
            sidecar.write_text(text, encoding="utf-8")
        return d / "report.md", sidecar

    def _run(self, report, sidecar, apply=True, script_text=None, synth_text=None):
        helper = self.HELPER
        if script_text is not None or synth_text is not None:
            root = Path(tempfile.mkdtemp()) / "scripts"
            root.mkdir(parents=True)
            (root / "backfill-findings.py").write_text(
                script_text if script_text is not None else self.HELPER.read_text(),
                encoding="utf-8")
            (root / "synthesize-sidecar.py").write_text(
                synth_text if synth_text is not None
                else (SCRIPTS / "synthesize-sidecar.py").read_text(), encoding="utf-8")
            helper = root / "backfill-findings.py"
        argv = [sys.executable, str(helper), "--repo", "acme/widget",
                "--report", str(report), "--sidecar", str(sidecar)]
        if apply:
            argv.append("--apply")
        return subprocess.run(argv, capture_output=True, text=True)

    def _lines(self, sidecar):
        return [json.loads(x) for x in sidecar.read_text().splitlines() if x.strip()]

    # --- oracle ---------------------------------------------------------------------------
    def test_exactly_the_missing_finding_is_appended(self):
        report, sidecar = self._fixture(existing=[])
        first = self._run(report, sidecar)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(len(self._lines(sidecar)), 3)

        sidecar.write_text("\n".join(sidecar.read_text().splitlines()[:2]) + "\n")
        r = self._run(report, sidecar)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self._lines(sidecar)), 3, "exactly the one missing line")

    def test_existing_lines_are_preserved_byte_for_byte(self):
        """They are what other ledgers join to. Re-emitting one with different key order
        produces a diff on every run and invites someone to 'fix' the wrong copy."""
        report, sidecar = self._fixture(existing=[])
        self._run(report, sidecar)
        before = sidecar.read_text()
        kept = "\n".join(before.splitlines()[:1]) + "\n"
        sidecar.write_text(kept)
        self._run(report, sidecar)
        self.assertTrue(sidecar.read_text().startswith(kept), "an existing line was rewritten")

    def test_a_rerun_appends_nothing_and_is_byte_identical(self):
        report, sidecar = self._fixture(existing=[])
        self._run(report, sidecar)
        after_first = sidecar.read_text()
        r = self._run(report, sidecar)
        self.assertIn("0 to append", r.stdout)
        self.assertEqual(sidecar.read_text(), after_first)

    def test_a_sidecar_without_a_final_newline_is_not_corrupted(self):
        """Appending to a file whose last line has no newline yields `{...}{...}` on one
        physical line. JSONL has no framing to notice: two findings become one unparseable
        line and nothing reports an error."""
        report, sidecar = self._fixture(existing=[], trailing_newline=True)
        self._run(report, sidecar)
        text = sidecar.read_text()
        sidecar.write_text(text.splitlines()[0])          # one line, NO trailing newline
        r = self._run(report, sidecar)
        self.assertEqual(r.returncode, 0, r.stderr)
        for lineno, line in enumerate(sidecar.read_text().splitlines(), 1):
            with self.subTest(line=lineno):
                json.loads(line)
        self.assertEqual(len(self._lines(sidecar)), 3)

    def test_the_fingerprint_matches_the_shell_helper(self):
        report, sidecar = self._fixture(existing=[])
        self._run(report, sidecar)
        for record in self._lines(sidecar):
            expected = self.shell_fingerprint({k: record[k] for k in
                                               ("file", "rule_id", "pattern", "line")})
            with self.subTest(file=record["file"]):
                self.assertEqual(record["fingerprint"], expected)

    def test_a_report_describing_one_finding_twice_appends_it_once(self):
        report, sidecar = self._fixture(existing=[])
        report.write_text(report.read_text() + report.read_text(), encoding="utf-8")
        self._run(report, sidecar)
        keys = [r["fingerprint"] for r in self._lines(sidecar)]
        self.assertEqual(len(keys), len(set(keys)), "a repeated finding was appended twice")

    def test_the_default_is_a_dry_run(self):
        report, sidecar = self._fixture(existing=[])
        r = self._run(report, sidecar, apply=False)
        self.assertIn("dry run", r.stdout)
        self.assertEqual(sidecar.read_text(), "", "a dry run must write nothing")

    def test_a_malformed_existing_line_is_left_in_place(self):
        """Rewriting the file to drop it would be a silent repair of data this helper was not
        asked to touch."""
        report, sidecar = self._fixture(existing=[])
        sidecar.write_text("{TRUNCATED\n", encoding="utf-8")
        self._run(report, sidecar)
        self.assertTrue(sidecar.read_text().startswith("{TRUNCATED\n"))

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        report, sidecar = self._fixture(existing=[])
        self._run(report, sidecar, script_text=NOOP[".py"])
        self.assertEqual(sidecar.read_text(), "", "sanity: a no-op appends nothing")

    def test_the_missing_digest_newline_mutant_re_keys_every_finding(self):
        """The plausible wrong implementation: hash the joined fields without jq's trailing
        newline. Every fingerprint is still a stable-looking sha256 — and none of them matches
        the one the shell helper already wrote into the ledgers.
        """
        synth = (SCRIPTS / "synthesize-sidecar.py").read_text(encoding="utf-8")
        self.assertIn(self.NL_ANCHOR, synth, "mutation anchor missing")
        report, sidecar = self._fixture(existing=[])
        self._run(report, sidecar,
                  synth_text=synth.replace(self.NL_ANCHOR, self.NL_MUTANT, 1))
        for record in self._lines(sidecar):
            expected = self.shell_fingerprint({k: record[k] for k in
                                               ("file", "rule_id", "pattern", "line")})
            with self.subTest(file=record["file"]):
                self.assertNotEqual(record["fingerprint"], expected,
                                    "mutation ineffective: the digest should have changed")


if __name__ == "__main__":
    unittest.main()
