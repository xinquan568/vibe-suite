# SPDX-License-Identifier: ISC
"""E8.7 (vibe-64): the integration fixture's census is a pinned contract.

The smoke tier counts the fixture's artifacts and the full tier's oracle requires a floor
of the planted defects to be detected. Both bind to `census.json`; a fixture edit that
forgets the census silently weakens the oracle, so the census is held to disk here — the
same discipline `test_doc_accuracy` applies to documentation counts.
"""
import json
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import extract

REPO = Path(__file__).resolve().parent.parent
FIXTURE = REPO / "auditor" / "test-fixture"
CENSUS = FIXTURE / "census.json"


def run_block(block, env, cwd):
    """Execute an extracted workflow block the way its step would run it."""
    import os
    full = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", str(cwd))}
    full.update(env)
    return subprocess.run(["bash", "-c", "set -euo pipefail\n" + block],
                          env=full, cwd=cwd, capture_output=True, text=True)


class FixtureCensus(unittest.TestCase):
    def census(self):
        self.assertTrue(CENSUS.is_file(),
                        "auditor/test-fixture/census.json is missing — the smoke census "
                        "and the full-tier oracle have nothing to bind to")
        return json.loads(CENSUS.read_text())

    def test_the_md_count_matches_disk(self):
        c = self.census()
        actual = sorted(p.relative_to(FIXTURE).as_posix()
                        for p in FIXTURE.rglob("*.md"))
        self.assertEqual(c["files"], len(actual),
                         f"census says {c['files']} .md files; disk has {len(actual)}: "
                         f"{actual}")

    def test_every_planted_defect_names_a_real_file_and_rule(self):
        c = self.census()
        self.assertGreaterEqual(len(c["planted"]), 5,
                                "fewer than five planted defects makes the oracle floor "
                                "meaningless")
        for row in c["planted"]:
            self.assertTrue((FIXTURE / row["path"]).is_file(),
                            f"planted defect names a missing file: {row['path']}")
            self.assertRegex(row["rule_id"], r"^(R\d\d|--)$",
                             f"planted rule id is not rubric-shaped: {row['rule_id']}")

    def test_the_detection_floor_is_achievable_and_meaningful(self):
        c = self.census()
        # "--" rows are structural defects outside the numbered rubric; the oracle
        # skips them, so they must not count toward achievability — counting them
        # once hid a census whose floor was unreachable.
        distinct = {row["rule_id"] for row in c["planted"]} - {"--"}
        self.assertGreaterEqual(c["detection_floor"], 2,
                                "a floor below two proves nothing about detection")
        self.assertLessEqual(c["detection_floor"], len(distinct),
                             "the floor exceeds the distinct planted rubric ids the "
                             "oracle can count — it could never pass")

    def test_the_fixture_declares_itself(self):
        readme = FIXTURE / "README.md"
        self.assertTrue(readme.is_file())
        text = readme.read_text()
        for needle in ("deliberately", "planted"):
            self.assertIn(needle, text,
                          "the fixture README does not state that its defects are "
                          "intentional — a future reader would 'fix' the test bed")


class IntegrationLadderContract(unittest.TestCase):
    """E8.7: the ladder's tier contents are pinned — AC-8's green means THESE ran."""

    STAGED = REPO / "auditor" / "workflows" / "auditor-integration-test.yml"
    LIVE = REPO / ".github" / "workflows" / "auditor-integration-test.yml"

    #: The seven lifecycle labels of the F10.1 state machine (runbook), all asserted.
    LABELS = ("audit-candidate", "audit-ready", "audit-complete", "contribute-approved",
              "prs-submitted", "case-study-ready", "complete")
    #: The exact unit-tier suite list: six helper suites + the four modules carrying the
    #: seven contribution-gate scenarios (gates, composition, reservation's weekly cap,
    #: quota's umbrella predicate).
    UNIT_SUITES = (
        "tests.test_auditor_workflows", "tests.test_auditor_scripts",
        "tests.test_auditor_findings_helpers", "tests.test_auditor_reporting_helpers",
        "tests.test_auditor_rulebook_helpers", "tests.test_auditor_batch_helpers",
        "tests.test_auditor_gates", "tests.test_auditor_composition",
        "tests.test_auditor_reservation", "tests.test_auditor_quota",
    )

    def text(self):
        return self.STAGED.read_text(encoding="utf-8")

    def test_all_seven_lifecycle_labels_are_asserted(self):
        # Token-exact against the loop line itself: a \b regex matches `complete` INSIDE
        # `audit-complete`, which is precisely how the missing seventh label hid.
        text = self.text()
        loop = next((l for l in text.splitlines() if "for label in" in l), None)
        self.assertIsNotNone(loop, "the provisioning label loop is gone")
        tokens = set(loop.replace(";", " ").split())
        for label in self.LABELS:
            self.assertIn(label, tokens,
                          f"the provisioning checklist does not assert the '{label}' "
                          f"label — the F10.1 state machine defines seven and the check "
                          f"under-asserts: {loop.strip()}")

    def test_the_unit_tier_runs_the_gate_scenario_modules(self):
        text = self.text()
        for suite in self.UNIT_SUITES:
            self.assertIn(suite, text,
                          f"the unit tier does not run {suite} — a gate scenario AC-8 "
                          f"names is outside the ladder it declares green")

    def test_the_live_copy_exists_and_is_byte_identical(self):
        # Activation is a COPY plus this pin (the codex-mirror discipline): the staged
        # file stays the lint-covered source; the live copy is what GitHub dispatches;
        # drift between them fails here.
        self.assertTrue(self.LIVE.is_file(),
                        "no live copy under .github/workflows — GitHub cannot dispatch "
                        "the ladder and AC-8 can never run")
        self.assertEqual(self.STAGED.read_bytes(), self.LIVE.read_bytes(),
                         "the live workflow drifted from the staged source — edit the "
                         "staged file and re-copy")

    def test_the_smoke_census_binds_to_the_fixture_census(self):
        text = self.text()
        self.assertIn("census.json", text,
                      "the smoke tier does not read the fixture census — its count "
                      "asserts nothing")
        self.assertIn("auditor/test-fixture", text,
                      "the ladder does not point at the in-repo fixture tree")


class CoverFallbackWithoutKey(unittest.TestCase):
    """AC-8: no OPENAI_API_KEY → templated SVG cover, and the article still publishes.

    The case-study cover step is marker-extracted and EXECUTED with the key deliberately
    unbound — absence must pass, which inverts the usual preflight logic and is exactly
    the clause a presence-only check would leave untested.
    """

    CASE_STUDY = REPO / "auditor" / "workflows" / "auditor-case-study.yml"

    def setUp(self):
        self.block = extract(self.CASE_STUDY, "cover-logic", "case-study")
        self.assertIsNotNone(
            self.block, "no cover-logic:case-study marker in auditor-case-study.yml — "
                        "the fallback path has no test seam")
        self.root = Path(tempfile.mkdtemp(prefix="cover-fb-"))
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "data" / "articles").mkdir(parents=True)
        (self.root / "data" / "articles" / "fixture-slug.md").write_text(
            "# fixture article\n\nbody\n")
        self.env = {"DATA_DIR": str(self.root / "data"), "SLUG": "fixture-slug",
                    "TARGET_REPO": "acme/fixture", "CODE_DIR": str(self.root),
                    "GITHUB_OUTPUT": str(self.root / "out.env")}

    def test_absent_key_produces_the_svg_and_publishes(self):
        r = run_block(self.block, self.env, self.root)
        self.assertEqual(r.returncode, 0,
                         f"the cover step failed WITHOUT the optional key — absence "
                         f"must pass:\n{r.stdout}\n{r.stderr}")
        date = time.strftime("%Y-%m-%d", time.gmtime())
        articles = self.root / "data" / "articles"
        svg = articles / f"{date}-fixture-slug.svg"
        self.assertTrue(svg.is_file(), "no templated SVG cover was produced")
        self.assertIn("acme/fixture", svg.read_text(),
                      "the SVG template did not interpolate the target repo")
        article = articles / f"{date}-fixture-slug.md"
        self.assertTrue(article.is_file(), "the draft was not dated into place")
        self.assertIn(f"![cover]({date}-fixture-slug.svg)", article.read_text(),
                      "the article does not reference the fallback cover")
        self.assertIn(f"article_path=articles/{date}-fixture-slug.md",
                      (self.root / "out.env").read_text(),
                      "the article-publish path did not proceed")

    def test_a_missing_draft_still_refuses_by_name(self):
        (self.root / "data" / "articles" / "fixture-slug.md").unlink()
        r = run_block(self.block, self.env, self.root)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:article-draft-missing", r.stdout,
                      "the extraction must not have swallowed the draft guard")


class FullTierOracle(unittest.TestCase):
    """AC-8: the full tier's report oracle — a tier that can pass on ANY report is no
    oracle. Extracted from the workflow and executed against fixture reports."""

    STAGED = REPO / "auditor" / "workflows" / "auditor-integration-test.yml"

    def setUp(self):
        self.block = extract(self.STAGED, "oracle-logic", "integration")
        self.assertIsNotNone(
            self.block, "no oracle-logic:integration marker — the report validation "
                        "has no test seam")
        self.outer = Path(tempfile.mkdtemp(prefix="oracle-"))
        self.addCleanup(shutil.rmtree, self.outer)
        self.repo = self.outer / "checkout"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        clone_fixture = self.repo / "fixture-clone" / "auditor" / "test-fixture"
        clone_fixture.mkdir(parents=True)
        shutil.copy(CENSUS, clone_fixture / "census.json")
        (self.repo / "audit-out").mkdir()
        self.census = json.loads(CENSUS.read_text())
        # the step summary lives OUTSIDE the checkout — it must not dirty the tree
        self.env = {"GITHUB_STEP_SUMMARY": str(self.outer / "summary.md")}

    def good_report(self):
        ids = sorted({r["rule_id"] for r in self.census["planted"]} - {"--"})
        lines = ["# Audit report — fixture tree", ""]
        lines += [f"- Finding: violates {rid} — planted defect detected in the fixture "
                  f"corpus, with enough prose to clear the triviality floor." for rid in ids]
        return "\n".join(lines) + "\n"

    def write_report(self, text):
        (self.repo / "audit-out" / "fixture-report.md").write_text(text)

    def test_a_detecting_confined_report_passes(self):
        self.write_report(self.good_report())
        r = run_block(self.block, self.env, self.repo)
        self.assertEqual(r.returncode, 0,
                         f"the oracle rejected a report naming every planted rule id "
                         f"with a clean tree:\n{r.stdout}\n{r.stderr}")
        self.assertIn("full tier green", r.stdout)

    def test_a_missing_report_fails(self):
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("report missing", r.stdout)

    def test_a_trivial_report_fails(self):
        self.write_report("looks fine\n")
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("trivial", r.stdout)

    def test_a_report_below_the_detection_floor_fails(self):
        # long enough to clear the byte floor, but names no planted rule id
        self.write_report("# Audit report\n\n" + "The tree was reviewed and no issues "
                          "of note were identified anywhere in the corpus. " * 5)
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("census floor", r.stdout)

    def test_a_mutated_tree_outside_audit_out_fails(self):
        self.write_report(self.good_report())
        (self.repo / "stray.txt").write_text("the model step wrote outside audit-out\n")
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("outside audit-out", r.stdout)


class SecurityChecklistSignOff(unittest.TestCase):
    """D2: the sign-off is an operator act; the unit tier verifies its durable record.
    Both states are driven against fixture copies — the REAL file's state at any moment
    (unchecked before the pause, signed after) is the operator's, not this suite's."""

    STAGED = REPO / "auditor" / "workflows" / "auditor-integration-test.yml"
    CHECKLIST = REPO / "auditor" / "SECURITY-CHECKLIST.md"

    ROWS = ("PAT scope", "Rotation doc", "Injection separation", "Audit token scope",
            "No secret egress")

    def setUp(self):
        self.block = extract(self.STAGED, "checklist-logic", "integration")
        self.assertIsNotNone(
            self.block, "no checklist-logic:integration marker — the sign-off check "
                        "has no test seam")
        self.root = Path(tempfile.mkdtemp(prefix="checklist-"))
        self.addCleanup(shutil.rmtree, self.root)

    def run_check(self, path):
        return run_block(self.block, {"CHECKLIST": str(path)}, self.root)

    def test_the_scaffold_carries_the_named_rows(self):
        text = self.CHECKLIST.read_text()
        for row in self.ROWS:
            self.assertIn(f"**{row}**", text,
                          f"the checklist scaffold lost its '{row}' row — AC-8 names "
                          f"PAT scope, rotation doc and injection separation explicitly")
        self.assertEqual(len(re.findall(r"^- \[[ x]\]", text, re.M)), len(self.ROWS))
        self.assertRegex(text, r"(?m)^Signed-off-by: ", "the sign-off line is gone")

    def test_a_missing_record_refuses(self):
        r = self.run_check(self.root / "absent.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("missing", r.stdout)

    def test_the_unchecked_scaffold_refuses(self):
        copy = self.root / "unchecked.md"
        copy.write_text(self.CHECKLIST.read_text())
        r = self.run_check(copy)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unchecked", r.stdout)

    def test_checked_rows_without_a_dated_signature_refuse(self):
        copy = self.root / "undated.md"
        copy.write_text(self.CHECKLIST.read_text().replace("- [ ]", "- [x]"))
        r = self.run_check(copy)
        self.assertNotEqual(r.returncode, 0,
                            "all rows checked but the sign-off line still carries the "
                            "placeholder — the check must demand a name and an ISO date")
        self.assertIn("sign-off", r.stdout)

    def test_a_signed_record_passes(self):
        copy = self.root / "signed.md"
        signed = self.CHECKLIST.read_text().replace("- [ ]", "- [x]").replace(
            "Signed-off-by: <operator name> <YYYY-MM-DD>",
            "Signed-off-by: Eric Liu 2026-08-13")
        copy.write_text(signed)
        r = self.run_check(copy)
        self.assertEqual(r.returncode, 0,
                         f"a fully attested, dated sign-off was refused:\n"
                         f"{r.stdout}\n{r.stderr}")
        self.assertIn("signed off", r.stdout)
