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
    """Execute an extracted workflow block EXACTLY as production does: plain bash, no
    prepended strictness — every marker pair carries its own `set -euo pipefail`, so a
    block that lost it fails these tests rather than borrowing rigor from the harness."""
    import os
    full = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", str(cwd))}
    full.update(env)
    return subprocess.run(["bash", "-c", block],
                          env=full, cwd=cwd, capture_output=True, text=True)


#: The exact planted inventory (path, rule_id) — a multiset, matched exactly. A bare
#: count or shape check accepts a reassigned census; this pin does not.
EXPECTED_PLANTED = (
    ("agents/broken-front.md", "--"),
    ("agents/watcher.md", "R01"),
    ("agents/watcher.md", "R09"),
    ("commands/cleanup.md", "--"),
    ("commands/deploy.md", "R01"),
    ("commands/deploy.md", "R18"),
    ("skills/helper-skill/SKILL.md", "--"),
    ("skills/helper-skill/SKILL.md", "R01"),
    ("skills/helper-skill/SKILL.md", "R04"),
)


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

    def test_the_planted_inventory_matches_exactly(self):
        c = self.census()
        actual = sorted((row["path"], row["rule_id"]) for row in c["planted"])
        self.assertEqual(actual, sorted(EXPECTED_PLANTED),
                         "the census's planted inventory drifted from the pinned "
                         "multiset — fixture and census must change together")
        for path, _ in EXPECTED_PLANTED:
            self.assertTrue((FIXTURE / path).is_file(),
                            f"planted defect names a missing file: {path}")

    def test_each_planted_defect_is_still_planted(self):
        """Semantic predicates: a well-meaning 'fix' to a fixture file must fail here,
        not silently weaken the oracle. One mechanical check per planted row."""
        deploy = (FIXTURE / "commands" / "deploy.md").read_text()
        self.assertIn("$ARGUMENTS", deploy, "deploy.md no longer takes input — R18 gone")
        self.assertNotIn("argument-hint", deploy,
                         "deploy.md declares argument-hint — the R18 defect was fixed")
        for needle in ("as needed", "appropriate"):
            self.assertIn(needle, deploy, f"deploy.md lost its R01 vague term {needle!r}")

        watcher = (FIXTURE / "agents" / "watcher.md").read_text()
        self.assertNotIn("<example>", watcher,
                         "watcher.md gained <example> blocks — the R09 defect was fixed")
        self.assertIn("appropriate", watcher, "watcher.md lost its R01 vague term")

        skill = (FIXTURE / "skills" / "helper-skill" / "SKILL.md").read_text()
        self.assertIn("name: mismatched-name", skill,
                      "the skill's name↔directory mismatch (a '--' row) was fixed")
        for needle in ("various", "reasonable"):
            self.assertIn(needle, skill,
                          f"the skill body lost its R01 vague term {needle!r}")
        # R04's planted form is pinned VERBATIM: any rewording is a conscious
        # re-census, not a judgment call about what still counts as a summary
        desc = next(l for l in skill.splitlines() if l.startswith("description:"))
        self.assertEqual(
            desc,
            "description: A skill whose declared name does not match its directory.",
            "the skill description changed — the R04 summary-not-trigger defect is "
            "pinned verbatim; edit fixture and census together")

        cleanup = (FIXTURE / "commands" / "cleanup.md").read_text()
        self.assertNotIn("description:", cleanup,
                         "cleanup.md gained a description — its '--' defect was fixed")

        front = (FIXTURE / "agents" / "broken-front.md").read_text()
        frontmatter = front.split("---")[1]
        self.assertEqual(frontmatter.count('"') % 2, 1,
                         "broken-front.md's quote is balanced — its '--' defect "
                         "(unparseable frontmatter) was fixed")

    def test_fixture_bytes_are_pinned(self):
        """The census names WHAT is planted; this pins the bytes it is planted in.
        Any fixture edit — repair, rewording, addition — must arrive together with a
        recomputed pin, making silent oracle weakening impossible."""
        import hashlib
        expected = {
            "README.md": "7177b617d9d0d4627d274eed0ece1b97a89557b7a88e5cd726dc8d607323eb45",
            "agents/broken-front.md": "290256e6a604ff8c85bcc26e8fc15b1c31c71bebccda91da810efda5f54bda24",
            "agents/watcher.md": "f196a85f5e215c13476f6b6789e14714eccec064310f216a03d53eb29735a912",
            "commands/cleanup.md": "12571962fc5773dbdb42a105d264423a9d5275d1f1a6aa58ed62b6b7b1e74c92",
            "commands/deploy.md": "8e3d37cfe0357f41262a6ed83306e03e5eff5e0f6491be72dfbdf46e1efd57d5",
            "skills/helper-skill/SKILL.md": "2312d82af936e9e7802b64c9c901517c9570a81299cfe91fb27ecf586b130db9",
        }
        actual = {p.relative_to(FIXTURE).as_posix():
                  hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in FIXTURE.rglob("*.md")}
        self.assertEqual(actual, expected,
                         "fixture bytes drifted from the pin — re-plant deliberately "
                         "and update census + pin together")

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
    #: quota's umbrella predicate) + this module itself, so the dispatched tier runs the
    #: ladder's own contract pins (census, equality pin, extracted-block contracts).
    UNIT_SUITES = (
        "tests.test_auditor_workflows", "tests.test_auditor_scripts",
        "tests.test_auditor_findings_helpers", "tests.test_auditor_reporting_helpers",
        "tests.test_auditor_rulebook_helpers", "tests.test_auditor_batch_helpers",
        "tests.test_auditor_gates", "tests.test_auditor_composition",
        "tests.test_auditor_reservation", "tests.test_auditor_quota",
        "tests.test_auditor_fixture",
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

    def test_the_block_carries_its_own_strict_mode(self):
        # run_block deliberately prepends nothing, so strictness must travel INSIDE
        # the marker pair — this pin is what makes that claim executable
        first = next(l for l in self.block.splitlines()
                     if l.strip() and not l.lstrip().startswith("#"))
        self.assertEqual(first.strip(), "set -euo pipefail",
                         "the extracted cover block lost its own strict mode")

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

    GIT_ID = ("-c", "user.name=oracle-test", "-c", "user.email=oracle@test")

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
        # the TRUSTED census lives in the checked-out tree — the oracle must never
        # read it from the clone the model step touched
        trusted = self.repo / "auditor" / "test-fixture"
        trusted.mkdir(parents=True)
        shutil.copy(CENSUS, trusted / "census.json")
        # the subtree-equality check compares clone vs checkout, so the sandbox's
        # two trees must start identical, as a real self-clone's do
        (trusted / "artifact.md").write_text("# audited artifact\n")
        # the checkout's own content is committed, as actions/checkout leaves it —
        # only what the MODEL step adds may appear in the outer status
        subprocess.run(["git", *self.GIT_ID, "add", "-A"], cwd=self.repo, check=True)
        subprocess.run(["git", *self.GIT_ID, "commit", "-q", "-m", "checkout state"],
                       cwd=self.repo, check=True)
        # the clone is a real git checkout in a CLEAN state, as a fresh
        # `git clone --depth 1` leaves it — its own status is part of the oracle
        self.clone = self.repo / "fixture-clone"
        clone_fixture = self.clone / "auditor" / "test-fixture"
        clone_fixture.mkdir(parents=True)
        shutil.copy(CENSUS, clone_fixture / "census.json")
        (clone_fixture / "artifact.md").write_text("# audited artifact\n")
        # the real self-clone carries the repo's .gitignore; the ignored-addition
        # test depends on an ignore rule existing, exactly as in production
        (self.clone / ".gitignore").write_text("__pycache__/\n")
        subprocess.run(["git", "init", "-q"], cwd=self.clone, check=True)
        subprocess.run(["git", *self.GIT_ID, "add", "-A"], cwd=self.clone, check=True)
        subprocess.run(["git", *self.GIT_ID, "commit", "-q", "-m", "clone state"],
                       cwd=self.clone, check=True)
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

    def test_a_tracked_mutation_inside_the_clone_fails(self):
        """The outer status collapses the clone to one '?? fixture-clone/' line, so a
        model edit to an audited file — including the clone's own census — was
        invisible to the outer check. The oracle must inspect the clone's own git."""
        self.write_report(self.good_report())
        clone_census = self.clone / "auditor" / "test-fixture" / "census.json"
        clone_census.write_text(clone_census.read_text().replace(
            '"detection_floor": 2', '"detection_floor": 0'))
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0,
                            "the model lowered the clone census's floor and the oracle "
                            "did not notice — clone mutations must fail")
        self.assertIn("mutated the audited fixture clone", r.stdout)

    def test_an_untracked_file_inside_the_clone_fails(self):
        self.write_report(self.good_report())
        (self.clone / "auditor" / "test-fixture" / "planted-by-model.md").write_text(
            "a file the model step added inside the audited tree\n")
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("mutated the audited fixture clone", r.stdout)

    def test_a_clone_without_git_metadata_fails(self):
        shutil.rmtree(self.clone / ".git")
        self.write_report(self.good_report())
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not a git checkout", r.stdout)

    def test_a_committed_tamper_inside_the_clone_fails(self):
        """git status cannot see a tamper the model COMMITTED — the clone reads
        clean. Only byte-equality of the audited subtree against the checked-out
        tree catches it."""
        self.write_report(self.good_report())
        clone_census = self.clone / "auditor" / "test-fixture" / "census.json"
        clone_census.write_text(clone_census.read_text().replace(
            '"detection_floor": 2', '"detection_floor": 0'))
        subprocess.run(["git", *self.GIT_ID, "commit", "-aqm", "hide the tamper"],
                       cwd=self.clone, check=True)
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0,
                            "a committed tamper left git status clean and the oracle "
                            "passed — the subtree must be compared to the checkout")
        self.assertIn("diverged from the checkout", r.stdout)

    def test_an_ignored_addition_inside_the_clone_fails(self):
        """`--untracked-files=all` alone leaves IGNORED paths invisible — a
        `__pycache__/` dropped inside the audited tree stayed status-clean. The
        oracle must ask for ignored entries too."""
        self.write_report(self.good_report())
        cache = self.clone / "auditor" / "test-fixture" / "__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"\x00planted\x00")
        r = run_block(self.block, self.env, self.repo)
        self.assertNotEqual(r.returncode, 0,
                            "an ignored-path addition inside the clone passed the "
                            "oracle — ignored entries must count as mutations")
        self.assertIn("mutated the audited fixture clone", r.stdout)

    def test_the_block_carries_its_own_strict_mode(self):
        first = next(l for l in self.block.splitlines()
                     if l.strip() and not l.lstrip().startswith("#"))
        self.assertEqual(first.strip(), "set -euo pipefail",
                         "the extracted oracle block lost its own strict mode")

    def test_the_census_is_read_from_the_checkout_not_the_clone(self):
        """The floor's authority must be the checked-out tree. Subtree equality
        happens to subsume this while both stand, but this pin holds the mechanism
        in place on its own — a clone-sourced census is the tamper-your-own-floor
        vector regardless of what other checks exist that day."""
        census_lines = [l for l in self.block.splitlines() if "CENSUS=" in l]
        self.assertEqual(len(census_lines), 1, "the oracle must bind CENSUS once")
        self.assertIn('CENSUS="${FIXTURE_PATH:-auditor/test-fixture}/census.json"',
                      census_lines[0],
                      "the oracle reads the census from the clone the model step "
                      "touched — the floor can be tampered from inside the clone")
        self.assertNotIn("fixture-clone", census_lines[0])


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

    def signed_text(self):
        return self.CHECKLIST.read_text().replace("- [ ]", "- [x]").replace(
            "Signed-off-by: <operator name> <YYYY-MM-DD>",
            "Signed-off-by: Eric Liu 2026-08-13")

    def test_a_signed_record_passes(self):
        copy = self.root / "signed.md"
        copy.write_text(self.signed_text())
        r = self.run_check(copy)
        self.assertEqual(r.returncode, 0,
                         f"a fully attested, dated sign-off was refused:\n"
                         f"{r.stdout}\n{r.stderr}")
        self.assertIn("signed off", r.stdout)

    def test_a_signature_without_the_rows_refuses(self):
        """The bypass the step-8 review named: a file containing ONLY a well-formed
        signature line must not pass — every named row has to be attested."""
        copy = self.root / "bare-signature.md"
        copy.write_text("Signed-off-by: Eric Liu 2026-08-13\n")
        r = self.run_check(copy)
        self.assertNotEqual(r.returncode, 0,
                            "a signature with zero attestation rows passed — the "
                            "verifier checks the signature but not the attestations")
        self.assertIn("not attested", r.stdout)

    def test_a_deleted_row_refuses_by_name(self):
        copy = self.root / "row-deleted.md"
        lines = [l for l in self.signed_text().splitlines(keepends=True)
                 if "**PAT scope**" not in l]
        copy.write_text("".join(lines))
        r = self.run_check(copy)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("'PAT scope' is not attested", r.stdout)

    def test_a_malformed_row_refuses(self):
        copy = self.root / "row-malformed.md"
        copy.write_text(self.signed_text().replace("- [x] **Rotation doc**",
                                                   "* [x] **Rotation doc**"))
        r = self.run_check(copy)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("'Rotation doc' is not attested", r.stdout)

    def test_a_duplicate_token_on_the_attested_line_refuses(self):
        """The iteration-2 verify's bypass: line-count sees one valid PAT line even
        when a second `- [x] **PAT scope**` token rides on it. Occurrences are
        counted too, and more than one refuses."""
        copy = self.root / "dup-token.md"
        copy.write_text(self.signed_text().replace(
            "- [x] **PAT scope** — the contribution",
            "- [x] **PAT scope** and again - [x] **PAT scope** — the contribution"))
        r = self.run_check(copy)
        self.assertNotEqual(r.returncode, 0,
                            "a duplicated attestation token on one valid line passed "
                            "— tokens must be counted, not lines")
        self.assertIn("'PAT scope' is not attested", r.stdout)

    def test_prose_mentions_of_the_rows_do_not_attest(self):
        """The verify pass's bypass: with an UNANCHORED count, five prose lines each
        containing a row's checked text mid-line (plus a valid signature) passed.
        Attestation rows must be matched at line start."""
        copy = self.root / "prose.md"
        rows = ("PAT scope", "Rotation doc", "Injection separation",
                "Audit token scope", "No secret egress")
        body = "".join(f"we discussed whether - [x] **{r}** applies here\n"
                       for r in rows)
        copy.write_text(body + "Signed-off-by: Eric Liu 2026-08-13\n")
        r = self.run_check(copy)
        self.assertNotEqual(r.returncode, 0,
                            "prose mentions of the checked rows were counted as "
                            "attestations — the row match is not anchored")
        self.assertIn("not attested", r.stdout)

    def test_the_block_carries_its_own_strict_mode(self):
        first = next(l for l in self.block.splitlines()
                     if l.strip() and not l.lstrip().startswith("#"))
        self.assertEqual(first.strip(), "set -euo pipefail",
                         "the extracted checklist block lost its own strict mode")
