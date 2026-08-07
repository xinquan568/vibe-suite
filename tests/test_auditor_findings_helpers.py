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



class _GhFake:
    """A recording `gh` on PATH.

    These helpers are defined by what they do with GitHub's answers, so the answers are canned
    and the real binary is never reached. A test that hits the network is slow, flaky, and
    silently passes when the helper asks the wrong question.
    """

    def gh(self, responses):
        """A directory holding a `gh` that replays `responses`, keyed by a substring of argv."""
        d = Path(tempfile.mkdtemp())
        (d / "responses.json").write_text(json.dumps(responses), encoding="utf-8")
        script = d / "gh"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys, pathlib\n"
            "here = pathlib.Path(__file__).resolve().parent\n"
            "table = json.loads((here / 'responses.json').read_text())\n"
            "argv = ' '.join(sys.argv[1:])\n"
            "(here / 'calls.log').open('a').write(argv + '\\n')\n"
            "for key, value in table.items():\n"
            "    if key in argv:\n"
            "        if value is None:\n"
            "            sys.exit(1)\n"
            "        sys.stdout.write(json.dumps(value))\n"
            "        sys.exit(0)\n"
            "sys.exit(1)\n", encoding="utf-8")
        script.chmod(0o755)
        return d

    def calls(self, ghdir):
        log = ghdir / "calls.log"
        return log.read_text().splitlines() if log.is_file() else []

    def env(self, ghdir):
        return dict(os.environ, PATH=f"{ghdir}:{os.environ['PATH']}")


class Test_backfill_pr_fingerprints(_GhFake, unittest.TestCase):
    """`backfill-pr-fingerprints.py` — provenance for PRs older than the metadata block."""

    HELPER = SCRIPTS / "backfill-pr-fingerprints.py"
    ATTR_ANCHOR = '            attributed = [f for path in paths for f in by_file.get(path, [])]'
    ATTR_MUTANT = '            attributed = list(findings)'

    FINDINGS = [
        {"file": "skills/a/SKILL.md", "rule_id": "R04", "fingerprint": "sha256:aaa"},
        {"file": "skills/b/SKILL.md", "rule_id": "R05", "fingerprint": "sha256:bbb"},
        {"file": "agents/c.md", "rule_id": "R06", "fingerprint": "sha256:ccc"},
    ]

    def _data_dir(self, prs=None):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "audits").mkdir()
        (d / "registry" / "repos.json").write_text(json.dumps({"repos": {"acme/widget": {
            "status": "contributed",
            "prs": prs if prs is not None else {
                "7": {"number": 7, "outcome": None, "fingerprints": [], "rule_ids": []}},
        }}}), encoding="utf-8")
        (d / "audits" / "acme-widget.findings.jsonl").write_text(
            "".join(json.dumps(f) + "\n" for f in self.FINDINGS), encoding="utf-8")
        return d

    def _run(self, d, ghdir, apply=True, script_text=None):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "backfill-pr-fingerprints.py"
            helper.write_text(script_text, encoding="utf-8")
        argv = [sys.executable, str(helper), "--data-dir", str(d)]
        if apply:
            argv.append("--apply")
        return subprocess.run(argv, capture_output=True, text=True, env=self.env(ghdir))

    def _prs(self, d):
        return json.loads((d / "registry" / "repos.json").read_text())["repos"]["acme/widget"]["prs"]

    # --- oracle ---------------------------------------------------------------------------
    def test_only_findings_in_the_prs_own_files_are_attributed(self):
        """The whole point. Attributing every finding to every PR runs clean and produces a
        registry in which a one-typo PR is credited with validating every rule — and rule
        health is computed from exactly these fields."""
        d = self._data_dir()
        gh = self.gh({"pr view 7": {"files": [{"path": "skills/a/SKILL.md"}]}})
        r = self._run(d, gh)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._prs(d)["7"]["fingerprints"], ["sha256:aaa"])
        self.assertEqual(self._prs(d)["7"]["rule_ids"], ["R04"])

    def test_existing_provenance_is_unioned_not_replaced(self):
        """A PR may already carry first-hand provenance from its metadata block; overwriting it
        with a reconstruction discards the auditor's own record."""
        d = self._data_dir(prs={"7": {"number": 7, "fingerprints": ["sha256:zzz"],
                                      "rule_ids": ["R99"]}})
        gh = self.gh({"pr view 7": {"files": [{"path": "skills/a/SKILL.md"}]}})
        self._run(d, gh)
        self.assertEqual(self._prs(d)["7"]["fingerprints"], ["sha256:aaa", "sha256:zzz"])
        self.assertEqual(self._prs(d)["7"]["rule_ids"], ["R04", "R99"])

    def test_a_rerun_changes_nothing(self):
        d = self._data_dir()
        gh = self.gh({"pr view 7": {"files": [{"path": "skills/a/SKILL.md"}]}})
        self._run(d, gh)
        after = (d / "registry" / "repos.json").read_text()
        r = self._run(d, gh)
        self.assertIn("updated 0 PR(s)", r.stdout)
        self.assertEqual((d / "registry" / "repos.json").read_text(), after)

    def test_an_unreadable_pr_is_skipped_not_treated_as_touching_nothing(self):
        """A fetch failure and a PR that changed nothing are different. Collapsing them makes a
        network error read as 'no findings apply', recorded as though it had been checked."""
        d = self._data_dir()
        gh = self.gh({"pr view 7": None})
        r = self._run(d, gh)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 unreadable", r.stdout)
        self.assertEqual(self._prs(d)["7"]["fingerprints"], [])

    def test_the_default_is_a_dry_run(self):
        d = self._data_dir()
        gh = self.gh({"pr view 7": {"files": [{"path": "skills/a/SKILL.md"}]}})
        before = (d / "registry" / "repos.json").read_text()
        r = self._run(d, gh, apply=False)
        self.assertIn("dry run", r.stdout)
        self.assertEqual((d / "registry" / "repos.json").read_text(), before)

    def test_a_missing_registry_is_refused(self):
        d = Path(tempfile.mkdtemp())
        r = self._run(d, self.gh({}))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:backfill-pr-fingerprints:registry-missing", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d = self._data_dir()
        gh = self.gh({"pr view 7": {"files": [{"path": "skills/a/SKILL.md"}]}})
        self._run(d, gh, script_text=NOOP[".py"])
        self.assertEqual(self._prs(d)["7"]["fingerprints"], [], "sanity: a no-op writes nothing")

    def test_the_attribute_everything_mutant_credits_a_pr_with_every_rule(self):
        """The plausible wrong implementation: skip the file match. It fills every empty field,
        exits zero, and silently claims a PR validated rules it never touched."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.ATTR_ANCHOR, src, "mutation anchor missing")
        d = self._data_dir()
        gh = self.gh({"pr view 7": {"files": [{"path": "skills/a/SKILL.md"}]}})
        r = self._run(d, gh, script_text=src.replace(self.ATTR_ANCHOR, self.ATTR_MUTANT, 1))
        self.assertEqual(r.returncode, 0, "the mutant runs clean — that is the danger")
        self.assertEqual(len(self._prs(d)["7"]["fingerprints"]), 3,
                         "mutation ineffective: the mutant should attribute all three")


class Test_scan_suppressions(_GhFake, unittest.TestCase):
    """`scan-suppressions.py` — what maintainers turned off, and why that is evidence."""

    HELPER = SCRIPTS / "scan-suppressions.py"
    DEDUPE_ANCHOR = '            seen.add((record["repo"], record["sha"], record["path"]))'
    DEDUPE_MUTANT = '            seen.add((record["repo"], record["path"]))'
    HOST = "xinquan568/vibe-suite"
    CONFIG = "---\nrule_overrides:\n  nl:R1: false\n  nl:R2:\n    max_penalty: 5\n---\n"

    def _b64(self, text):
        import base64
        return {"encoding": "base64", "content": base64.b64encode(text.encode()).decode()}

    def _responses(self, items, contents=None):
        table = {"search/code": {"items": items} if items is not None else None}
        # `gh api search/code --jq .items` — the fake ignores --jq, so hand back the list.
        table["search/code"] = items
        for repo_path, text in (contents or {}).items():
            table[f"repos/{repo_path}"] = self._b64(text)
        return table

    def _data_dir(self, ledger=None):
        d = Path(tempfile.mkdtemp())
        (d / "feedback").mkdir()
        if ledger is not None:
            (d / "feedback" / "suppressions.jsonl").write_text(
                "".join(json.dumps(r, sort_keys=True) + "\n" for r in ledger), encoding="utf-8")
        return d

    def _run(self, d, ghdir, apply=True, script_text=None, host=None):
        helper = self.HELPER
        if script_text is not None:
            root = Path(tempfile.mkdtemp()) / "scripts"
            root.mkdir(parents=True)
            (root / "scan-suppressions.py").write_text(script_text, encoding="utf-8")
            (root / "parse-suppressions.py").write_text(
                (SCRIPTS / "parse-suppressions.py").read_text(), encoding="utf-8")
            helper = root / "scan-suppressions.py"
        argv = [sys.executable, str(helper), "--data-dir", str(d),
                "--host-repo", host or self.HOST, "--observed-at", "2026-08-08T00:00:00Z"]
        if apply:
            argv.append("--apply")
        return subprocess.run(argv, capture_output=True, text=True, env=self.env(ghdir))

    def _ledger(self, d):
        path = d / "feedback" / "suppressions.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] \
            if path.is_file() else []

    # --- oracle ---------------------------------------------------------------------------
    def test_self_duplicate_and_new_are_separated(self):
        """Three kinds of hit in one scan: our own fixtures, a config already recorded, and a
        genuinely new one. Only the last may append."""
        d = self._data_dir(ledger=[{"repo": "acme/old", "path": ".vibe-suppressions.yml",
                                    "sha": "dup", "overrides": []}])
        gh = self.gh(self._responses(
            [{"repository": {"full_name": self.HOST}, "path": "tests/fixture.yml", "sha": "s1"},
             {"repository": {"full_name": "acme/old"}, "path": ".vibe-suppressions.yml",
              "sha": "dup"},
             {"repository": {"full_name": "acme/new"}, "path": ".vibe-suppressions.yml",
              "sha": "n1"}],
            {"acme/new/contents/.vibe-suppressions.yml": self.CONFIG}))
        r = self._run(d, gh)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 self", r.stdout)
        self.assertIn("1 already recorded", r.stdout)
        self.assertIn("1 new", r.stdout)
        self.assertEqual([x["repo"] for x in self._ledger(d)], ["acme/old", "acme/new"])

    def test_the_host_repositorys_own_fixtures_are_never_ingested(self):
        """This repository's tests and templates CONTAIN suppression configs. Ingesting them
        records overrides nobody set, into the dataset used to decide which rules to retire —
        our own fixtures arguing for changing our own rules."""
        d = self._data_dir()
        gh = self.gh(self._responses(
            [{"repository": {"full_name": self.HOST}, "path": "tests/fixture.yml", "sha": "s1"}],
            {f"{self.HOST}/contents/tests/fixture.yml": self.CONFIG}))
        self._run(d, gh)
        self.assertEqual(self._ledger(d), [])

    def test_override_types_survive_the_round_trip(self):
        d = self._data_dir()
        gh = self.gh(self._responses(
            [{"repository": {"full_name": "acme/new"}, "path": ".vibe-suppressions.yml",
              "sha": "n1"}],
            {"acme/new/contents/.vibe-suppressions.yml": self.CONFIG}))
        self._run(d, gh)
        record = self._ledger(d)[0]
        by_rule = {o["rule_id"]: o["override"] for o in record["overrides"]}
        self.assertIs(by_rule["nl:R1"], False, "a bool must not arrive as a string")
        self.assertEqual(by_rule["nl:R2"], {"max_penalty": 5})
        self.assertEqual(record["rule_ids"], ["nl:R1", "nl:R2"])

    def test_an_edited_config_appends_a_new_record(self):
        """repo+path without sha means an edit never registers: the ledger keeps the first
        version forever and a maintainer who later suppressed six more rules reads as having
        suppressed none of them."""
        d = self._data_dir(ledger=[{"repo": "acme/new", "path": ".vibe-suppressions.yml",
                                    "sha": "old", "overrides": []}])
        gh = self.gh(self._responses(
            [{"repository": {"full_name": "acme/new"}, "path": ".vibe-suppressions.yml",
              "sha": "new"}],
            {"acme/new/contents/.vibe-suppressions.yml": self.CONFIG}))
        self._run(d, gh)
        self.assertEqual([x["sha"] for x in self._ledger(d)], ["old", "new"])

    def test_two_configs_in_one_repository_are_both_kept(self):
        d = self._data_dir()
        gh = self.gh(self._responses(
            [{"repository": {"full_name": "acme/new"}, "path": "a/.vibe-suppressions.yml",
              "sha": "s1"},
             {"repository": {"full_name": "acme/new"}, "path": "b/.vibe-suppressions.yml",
              "sha": "s2"}],
            {"acme/new/contents/a/.vibe-suppressions.yml": self.CONFIG,
             "acme/new/contents/b/.vibe-suppressions.yml": self.CONFIG}))
        self._run(d, gh)
        self.assertEqual(len(self._ledger(d)), 2, "dedupe on repo alone loses one")

    def test_a_malformed_remote_config_is_recorded_not_dropped(self):
        """One repository's broken config must not stop the other hundred, and must not read as
        'this maintainer suppressed nothing'."""
        d = self._data_dir()
        gh = self.gh(self._responses(
            [{"repository": {"full_name": "acme/bad"}, "path": ".vibe-suppressions.yml",
              "sha": "b1"}],
            {"acme/bad/contents/.vibe-suppressions.yml": "---\nrule_overrides:\n\tbad\n---\n"}))
        r = self._run(d, gh)
        self.assertEqual(r.returncode, 0, r.stderr)
        record = self._ledger(d)[0]
        self.assertIn("parse_error", record)

    def test_a_missing_host_repo_is_refused(self):
        d = self._data_dir()
        r = subprocess.run([sys.executable, str(self.HELPER), "--data-dir", str(d)],
                           capture_output=True, text=True,
                           env={k: v for k, v in self.env(self.gh({})).items()
                                if k != "GITHUB_REPOSITORY"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("host-repo-required", r.stderr)

    def test_a_failed_search_is_refused_not_read_as_no_results(self):
        d = self._data_dir()
        r = self._run(d, self.gh({}))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:scan-suppressions:search-failed", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d = self._data_dir()
        gh = self.gh(self._responses(
            [{"repository": {"full_name": "acme/new"}, "path": ".vibe-suppressions.yml",
              "sha": "n1"}], {"acme/new/contents/.vibe-suppressions.yml": self.CONFIG}))
        self._run(d, gh, script_text=NOOP[".py"])
        self.assertEqual(self._ledger(d), [], "sanity: a no-op appends nothing")

    def test_the_sha_less_dedupe_mutant_never_notices_an_edit(self):
        """The plausible wrong implementation: dedupe on (repo, path). Every rescan of an
        edited config is a no-op, so the ledger keeps the stale version indefinitely."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.DEDUPE_ANCHOR, src, "mutation anchor missing")
        mutant = src.replace(self.DEDUPE_ANCHOR, self.DEDUPE_MUTANT, 1).replace(
            'seen.add((item["repo"], item["sha"], item["path"]))',
            'seen.add((item["repo"], item["path"]))', 1).replace(
            'key = (item["repo"], item["sha"], item["path"])',
            'key = (item["repo"], item["path"])', 1)
        d = self._data_dir(ledger=[{"repo": "acme/new", "path": ".vibe-suppressions.yml",
                                    "sha": "old", "overrides": []}])
        gh = self.gh(self._responses(
            [{"repository": {"full_name": "acme/new"}, "path": ".vibe-suppressions.yml",
              "sha": "new"}],
            {"acme/new/contents/.vibe-suppressions.yml": self.CONFIG}))
        self._run(d, gh, script_text=mutant)
        self.assertEqual([x["sha"] for x in self._ledger(d)], ["old"],
                         "mutation ineffective: the mutant should miss the edit")



class Test_diff_findings(unittest.TestCase):
    """`diff-findings.py` — did the maintainer actually fix it?

    This helper decides whether a rule was VALIDATED, so its output feeds rule health. A wrong
    answer argues for keeping bad rules or retiring good ones.
    """

    HELPER = SCRIPTS / "diff-findings.py"
    SHIFT_ANCHOR = '    return (str(finding.get("file") or ""),\n            str(finding.get("rule_id") or ""),\n            str(finding.get("pattern") or ""))'
    SHIFT_MUTANT = '    return (str(finding.get("file") or ""),\n            str(finding.get("rule_id") or ""),\n            str(finding.get("pattern") or ""),\n            finding.get("line"))'
    SHA_BEFORE = "a" * 40
    SHA_AFTER = "b" * 40

    #: One of each outcome, which is what the specification's fixture calls for.
    ORIGINAL = [
        {"file": "a.md", "rule_id": "R04", "pattern": "p1", "line": 3, "fingerprint": "fp-same"},
        {"file": "b.md", "rule_id": "R05", "pattern": "p2", "line": 10, "fingerprint": "fp-old"},
        {"file": "c.md", "rule_id": "R06", "pattern": "p3", "line": 7, "fingerprint": "fp-fixed"},
    ]
    REAUDIT = [
        {"file": "a.md", "rule_id": "R04", "pattern": "p1", "line": 3, "fingerprint": "fp-same"},
        # same finding, file grew above it — NOT a fix
        {"file": "b.md", "rule_id": "R05", "pattern": "p2", "line": 42, "fingerprint": "fp-new"},
        {"file": "d.md", "rule_id": "R07", "pattern": "p4", "line": 1, "fingerprint": "fp-intro"},
    ]

    def _fixture(self, original=None, reaudit=None, events=None):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "audits").mkdir()
        (d / "ledgers").mkdir()
        (d / "registry" / "repos.json").write_text(
            json.dumps({"repos": {"acme/widget": {"commit_sha_at_audit": self.SHA_BEFORE}}}),
            encoding="utf-8")
        (d / "audits" / "orig.jsonl").write_text(
            "".join(json.dumps(f) + "\n" for f in
                    (self.ORIGINAL if original is None else original)), encoding="utf-8")
        (d / "audits" / "re.jsonl").write_text(
            "".join(json.dumps(f) + "\n" for f in
                    (self.REAUDIT if reaudit is None else reaudit)), encoding="utf-8")
        if events is not None:
            (d / "ledgers" / "events.jsonl").write_text(events, encoding="utf-8")
        return d

    def _argv(self, d, **over):
        values = {
            "--repo": "acme/widget",
            "--original-sidecar": str(d / "audits" / "orig.jsonl"),
            "--reaudit-sidecar": str(d / "audits" / "re.jsonl"),
            "--registry": str(d / "registry" / "repos.json"),
            "--commit-sha-before": self.SHA_BEFORE,
            "--commit-sha-after": self.SHA_AFTER,
            "--events-out": str(d / "ledgers" / "events.jsonl"),
            "--diff-report-out": str(d / "audits" / "diff.md"),
            "--summary-out": str(d / "audits" / "summary.json"),
        }
        values.update(over)
        argv = []
        for flag, value in values.items():
            if value is not None:
                argv += [flag, value]
        return argv

    def _run(self, d, script_text=None, **over):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "diff-findings.py"
            helper.write_text(script_text, encoding="utf-8")
        return subprocess.run([sys.executable, str(helper), *self._argv(d, **over)],
                              capture_output=True, text=True)

    def _summary(self, d):
        return json.loads((d / "audits" / "summary.json").read_text())

    def _events(self, d):
        path = d / "ledgers" / "events.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] \
            if path.is_file() else []

    # --- oracle ---------------------------------------------------------------------------
    def test_the_four_outcomes_are_each_counted_once(self):
        d = self._fixture()
        r = self._run(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        counts = self._summary(d)["counts"]
        self.assertEqual(counts["identical"], 1)
        self.assertEqual(counts["shifted"], 1)
        self.assertEqual(counts["fixed"], 1)
        self.assertEqual(counts["introduced"], 1)

    def test_a_line_shift_is_not_a_fix(self):
        """The line is IN the fingerprint, so a fingerprint comparison reports every finding
        below an inserted paragraph as fixed and an equal number as introduced. Add one line to
        the top of a file and the maintainer is credited with fixing forty findings and blamed
        for introducing forty more."""
        d = self._fixture()
        self._run(d)
        summary = self._summary(d)
        self.assertEqual(summary["fixed"], ["fp-fixed"], "the shifted finding was called fixed")
        self.assertEqual(summary["introduced"], ["fp-intro"])

    def test_a_whole_file_shifting_produces_no_fixes(self):
        """The realistic case: a paragraph added at the top moves everything down."""
        original = [{"file": "a.md", "rule_id": f"R{i:02d}", "pattern": f"p{i}", "line": i,
                     "fingerprint": f"fp-{i}"} for i in range(1, 21)]
        reaudit = [dict(f, line=f["line"] + 1, fingerprint=f"fp-shift-{i}")
                   for i, f in enumerate(original, 1)]
        d = self._fixture(original=original, reaudit=reaudit)
        self._run(d)
        counts = self._summary(d)["counts"]
        self.assertEqual((counts["fixed"], counts["introduced"], counts["shifted"]), (0, 0, 20))

    def test_events_go_to_the_events_ledger_with_the_right_names(self):
        d = self._fixture()
        self._run(d)
        events = self._events(d)
        self.assertEqual({e["event"] for e in events},
                         {"finding_verified", "finding_introduced"})
        self.assertEqual([e["data"]["fingerprint"] for e in events
                          if e["event"] == "finding_verified"], ["fp-fixed"])
        for event in events:
            self.assertEqual(event["data"]["commit_sha_before"], self.SHA_BEFORE)
            self.assertEqual(event["data"]["commit_sha_after"], self.SHA_AFTER)

    def test_a_rerun_keeps_event_multiplicity_at_one_to_one(self):
        d = self._fixture()
        self._run(d)
        first = len(self._events(d))
        self._run(d)
        self.assertEqual(len(self._events(d)), first, "the rerun duplicated events")

    def test_the_report_names_shifted_findings_as_still_open(self):
        d = self._fixture()
        self._run(d)
        report = (d / "audits" / "diff.md").read_text()
        self.assertIn("They are not fixes.", report)
        self.assertIn("| fixed | 1 |", report)

    # --- refusals -------------------------------------------------------------------------
    def test_every_one_of_the_nine_arguments_is_required(self):
        d = self._fixture()
        for flag in ("--repo", "--original-sidecar", "--reaudit-sidecar", "--registry",
                     "--commit-sha-before", "--commit-sha-after", "--events-out",
                     "--diff-report-out", "--summary-out"):
            with self.subTest(missing=flag):
                r = self._run(d, **{flag: None})
                self.assertNotEqual(r.returncode, 0, f"{flag} was not required")
                self.assertIn("REFUSE:diff-findings:", r.stderr)

    def test_placeholder_shas_are_refused(self):
        """A diff between two commits nobody can name is not evidence, and once it is in the
        ledger it is indistinguishable from a real one."""
        d = self._fixture()
        for bad in ("unknown", "", "HEAD", "none", "null", "latest", "abc123", "z" * 40):
            for side in ("--commit-sha-before", "--commit-sha-after"):
                with self.subTest(value=bad, side=side):
                    r = self._run(d, **{side: bad})
                    self.assertNotEqual(r.returncode, 0, f"{bad!r} accepted for {side}")
                    self.assertRegex(r.stderr, r"REFUSE:diff-findings:commit-sha-\w+-(missing|invalid)")

    def test_an_uppercase_sha_is_normalised_rather_than_refused(self):
        d = self._fixture()
        r = self._run(d, **{"--commit-sha-after": self.SHA_AFTER.upper()})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._summary(d)["commit_sha_after"], self.SHA_AFTER)

    def test_a_sha256_length_sha_is_accepted(self):
        d = self._fixture()
        r = self._run(d, **{"--commit-sha-after": "c" * 64})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_nothing_is_written_when_validation_fails(self):
        """Validation happens before anything is created, truncated or appended, so a refusal
        leaves the previous state exactly as it was."""
        d = self._fixture(events='{"event":"pre-existing"}\n')
        r = self._run(d, **{"--commit-sha-after": "unknown"})
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((d / "audits" / "diff.md").exists(), "a report was written anyway")
        self.assertFalse((d / "audits" / "summary.json").exists())
        self.assertEqual((d / "ledgers" / "events.jsonl").read_text(),
                         '{"event":"pre-existing"}\n', "the ledger was touched")

    def test_a_missing_sidecar_is_refused(self):
        d = self._fixture()
        (d / "audits" / "re.jsonl").unlink()
        r = self._run(d)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("reaudit-sidecar-missing", r.stderr)

    def test_a_repo_absent_from_the_registry_is_refused(self):
        d = self._fixture()
        r = self._run(d, **{"--repo": "ghost/repo"})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("repo-not-in-registry", r.stderr)


    def test_the_call_site_supplies_all_nine_arguments(self):
        """S-2's invocation, read from the workflow. The call site previously passed two
        positional paths to a helper that requires nine named flags."""
        text = (REPO / "auditor" / "workflows" / "auditor-case-study.yml").read_text()
        start = text.index("diff-findings.py")
        block = text[start:start + 900]
        for flag in ("--repo", "--original-sidecar", "--reaudit-sidecar", "--registry",
                     "--commit-sha-before", "--commit-sha-after", "--events-out",
                     "--diff-report-out", "--summary-out"):
            with self.subTest(flag=flag):
                self.assertIn(flag, block)
        self.assertNotIn("$SLUG\" \\\n", block.split("--repo")[1][:40])

    def test_the_call_site_derives_each_sha_from_exactly_one_source(self):
        """The before sha only from the registry's commit_sha_at_audit, the after sha only from
        the re-audit clone's HEAD. No fallback and no `|| echo unknown`."""
        text = (REPO / "auditor" / "workflows" / "auditor-case-study.yml").read_text()
        i = text.index("COMMIT_SHA_BEFORE=")
        block = text[i:text.index("diff-findings.py", i)]
        self.assertIn("commit_sha_at_audit", block)
        self.assertIn("rev-parse --verify HEAD^{commit}", block)
        self.assertNotIn("unknown", block)
        self.assertIn("REFUSE:diff-findings:commit-sha-before-missing", block)

    def test_events_go_to_the_events_ledger_not_findings(self):
        """The specification is explicit: finding_verified and finding_introduced belong in
        ledgers/events.jsonl."""
        text = (REPO / "auditor" / "workflows" / "auditor-case-study.yml").read_text()
        i = text.index("diff-findings.py")
        block = text[i:i + 900]
        self.assertIn('--events-out "$DATA_DIR/ledgers/events.jsonl"', block)
        self.assertNotIn("ledgers/findings.jsonl", block)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d = self._fixture()
        self._run(d, script_text=NOOP[".py"])
        self.assertFalse((d / "audits" / "summary.json").exists(),
                         "sanity: a no-op writes no summary")

    def test_the_line_sensitive_mutant_calls_every_shift_a_fix(self):
        """The plausible wrong implementation: include the line in the identity, which is what
        comparing fingerprints does. It runs clean and inverts the meaning of the output."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.SHIFT_ANCHOR, src, "mutation anchor missing")
        d = self._fixture()
        r = self._run(d, script_text=src.replace(self.SHIFT_ANCHOR, self.SHIFT_MUTANT, 1))
        self.assertEqual(r.returncode, 0, "the mutant runs clean — that is the danger")
        counts = self._summary(d)["counts"]
        self.assertEqual(counts["fixed"], 2,
                         "mutation ineffective: the mutant should count the shift as a fix")
        self.assertEqual(counts["shifted"], 0)


if __name__ == "__main__":
    unittest.main()
