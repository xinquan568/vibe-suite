#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The `profile init` scaffolder (E5.5 / vibe-44).

**D2 ships no working profile**, so a fresh install refuses until this command runs — the refusal in
`skills/issue2pr/SKILL.md` points here. That makes one failure worse than all the others: a generated
profile that the suite's own lint rejects, because it would be the user's first experience of the tool
producing something the tool refuses.

**Detection and writing are separate programs.** Detection reads and answers; writing takes a complete
field set and produces files. That split is what lets detection be tested against fixtures without
anything being written — the same line #43 drew between a driver that observes and a core that decides.

**Two of F6.4's interview questions are not asked**, by operator decision recorded on #44: the
review-iteration cap has no contract field (`max_review_rounds` is a per-run flag, so a profile
carrying it fails lint as an unknown field), and `reviewer_backend`'s domain contains `codex` alone, so
omitting it selects what the only legal answer would have selected.

**What CI reaches here.** Detection, rendering, writing and the end-to-end gate are programs and are
driven as subprocesses. The interview is a conversation a session has: the tests assert that the skill
*enumerates* its prompts and their target fields, and nothing here claims that asking elicits a good
answer.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DETECT = REPO_ROOT / "scripts" / "detect_profile.py"
WRITE = REPO_ROOT / "scripts" / "write_profile.py"
LINT = REPO_ROOT / "scripts" / "profile_lint.py"
REFERENCE = REPO_ROOT / "skills" / "issue2pr" / "references" / "profile-init.md"
CORE = REPO_ROOT / "skills" / "issue2pr" / "SKILL.md"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "profile-init"

REQUIRED_FIELDS = frozenset({
    "contract_version", "project_id", "repo_id", "repo_path", "base_branch",
    "source_driver", "id_pattern", "url_regex", "branch_template", "gates",
})

#: The five that survive. The cap and the backend are recorded as deliberately not asked.
INTERVIEW_FIELDS = {
    "issue-id shorthand": "id_pattern",
    "TDD policy": "tdd_policy",
    "anti-patterns": "anti_patterns",
    "mental-model references": "mental_model_refs",
    "scenario overrides": "scenario_overrides",
}

NOT_ASKED = ("review", "backend")


def norm(text):
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


class DetectCase(unittest.TestCase):
    """Detection takes git facts as inputs, so it is deterministic without building real repositories.

    Reading git is one function with its own test; everything downstream of it is pure.
    """

    def detect(self, **facts):
        payload = {"root": str(FIXTURES / facts.pop("fixture", "node-gates"))}
        payload.update(facts)
        result = subprocess.run(
            [sys.executable, str(DETECT), "--facts", "-"],
            input=json.dumps(payload), capture_output=True, text=True, timeout=60)
        return result

    def detected(self, **facts):
        result = self.detect(**facts)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)


class TestPreconditions(DetectCase):
    """`refuse with what is missing` — not the first thing missing."""

    def test_a_complete_repository_passes(self):
        self.detected(remote="git@github.com:acme/demo.git", default_branch="main")

    def test_a_missing_remote_is_refused(self):
        result = self.detect(fixture="no-remote", remote=None, default_branch="main")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("origin", (result.stdout + result.stderr).lower())

    def test_a_non_github_remote_is_refused(self):
        result = self.detect(remote="git@gitlab.com:acme/demo.git", default_branch="main")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("github", (result.stdout + result.stderr).lower())

    def test_two_missing_preconditions_are_both_reported(self):
        """Reporting the first teaches one thing per attempt. This is the case a single-failure
        fixture cannot distinguish."""
        result = self.detect(fixture="no-remote", remote=None, default_branch=None)
        self.assertNotEqual(result.returncode, 0)
        report = (result.stdout + result.stderr).lower()
        self.assertIn("origin", report)
        self.assertIn("branch", report)

    def test_missing_auth_is_a_warning_not_a_refusal(self):
        """Auth decides whether the smoke check runs, not whether a valid profile can be written."""
        result = self.detect(remote="git@github.com:acme/demo.git", default_branch="main", login=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skip", (result.stdout + result.stderr).lower())


class TestConversions(DetectCase):
    """Detected facts are converted, not copied. An origin URL is not a `url_regex`."""

    def test_both_remote_forms_yield_one_repo_id(self):
        ssh = self.detected(fixture="ssh-remote", remote="git@github.com:acme/demo.git",
                            default_branch="main")
        https = self.detected(fixture="https-remote", remote="https://github.com/acme/demo.git",
                              default_branch="main")
        self.assertEqual(ssh["repo_id"], "acme/demo")
        self.assertEqual(https["repo_id"], ssh["repo_id"])

    def test_the_default_branch_is_not_assumed(self):
        detected = self.detected(fixture="odd-default-branch",
                                 remote="git@github.com:acme/demo.git", default_branch="trunk")
        self.assertEqual(detected["base_branch"], "trunk")

    def test_the_url_regex_compiles_matches_and_discriminates(self):
        """String equality would pass a pattern that compiles and matches nothing."""
        detected = self.detected(remote="git@github.com:acme/demo.git", default_branch="main")
        pattern = re.compile(detected["url_regex"])
        match = pattern.match("https://github.com/acme/demo/issues/42")
        self.assertIsNotNone(match, "the pattern must match this project's issue URL")
        self.assertEqual(match.group(1), "42", "the number must be captured")
        self.assertIsNone(pattern.match("https://github.com/acme/other/issues/42"),
                          "it must not match a neighbouring repository")

    def test_a_metacharacter_in_the_repository_name_is_escaped(self):
        """`a.b` unescaped matches `axb`. Compiling is all the lint checks, so this is the case it
        cannot catch."""
        detected = self.detected(fixture="metachar-name",
                                 remote="git@github.com:acme/a.b.git", default_branch="main")
        pattern = re.compile(detected["url_regex"])
        self.assertIsNotNone(pattern.match("https://github.com/acme/a.b/issues/7"))
        self.assertIsNone(pattern.match("https://github.com/acme/axb/issues/7"),
                          "an unescaped dot matches any character")

    def test_the_branch_template_does_not_require_a_login(self):
        """`branch_template` is required, so it cannot depend on authentication."""
        without = self.detected(remote="git@github.com:acme/demo.git",
                                default_branch="main", login=None)
        self.assertIn("{id}", without["branch_template"])
        self.assertNotIn("None", without["branch_template"])
        with_login = self.detected(remote="git@github.com:acme/demo.git",
                                   default_branch="main", login="alice")
        self.assertTrue(with_login["branch_template"].startswith("alice/"))

    def test_repo_path_is_relative(self):
        """The lint refuses an absolute one."""
        detected = self.detected(remote="git@github.com:acme/demo.git", default_branch="main")
        self.assertFalse(Path(detected["repo_path"]).is_absolute())


class TestIdPattern(DetectCase):
    """The interview's answer, converted. Omitted from the first draft's table."""

    def pattern_for(self, shorthand):
        detected = self.detected(remote="git@github.com:acme/demo.git",
                                 default_branch="main", id_shorthand=shorthand)
        return re.compile(detected["id_pattern"])

    def test_a_prefixed_shorthand_matches_and_captures(self):
        pattern = self.pattern_for("proj-N")
        match = pattern.match("proj-17")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "17")
        self.assertIsNone(pattern.match("other-17"))

    def test_bare_numbers_are_supported(self):
        pattern = self.pattern_for("N")
        self.assertIsNotNone(pattern.match("17"))
        self.assertIsNone(pattern.match("proj-17"))

    def test_a_metacharacter_in_the_shorthand_is_escaped(self):
        pattern = self.pattern_for("a.b-N")
        self.assertIsNotNone(pattern.match("a.b-3"))
        self.assertIsNone(pattern.match("axb-3"))

    def test_the_pattern_is_anchored_at_both_ends(self):
        """`re.match` anchors the start by itself, so testing a leading prefix proves nothing about
        the pattern — removing `^` left that assertion green. The end anchor is the one a `.match()`
        call cannot supply, and a trailing suffix is what exposes it.
        """
        pattern = self.pattern_for("proj-N")
        self.assertIsNone(pattern.match("proj-17-extra"),
                          "without a trailing anchor the pattern matches a different item")
        self.assertIsNone(pattern.search("xproj-17"),
                          "without a leading anchor it matches inside another id")


class TestGateDetection(DetectCase):
    """Proposes; never invents. A guessed gate is a command the pipeline will run."""

    def test_node_scripts_become_gates(self):
        detected = self.detected(fixture="node-gates", remote="git@github.com:acme/demo.git",
                                 default_branch="main")
        self.assertIn("npm run test", detected["gates"])

    def test_make_targets_become_gates(self):
        detected = self.detected(fixture="make-gates", remote="git@github.com:acme/demo.git",
                                 default_branch="main")
        self.assertTrue(any("make" in gate for gate in detected["gates"]))

    def test_nothing_detected_yields_no_gates(self):
        detected = self.detected(fixture="no-gates", remote="git@github.com:acme/demo.git",
                                 default_branch="main")
        self.assertEqual(detected["gates"], [])

    def test_a_script_that_does_not_exist_is_not_proposed(self):
        detected = self.detected(fixture="node-gates", remote="git@github.com:acme/demo.git",
                                 default_branch="main")
        for gate in detected["gates"]:
            with self.subTest(gate=gate):
                self.assertNotIn("build", gate, "the fixture declares no build script")


class TestIdentifiers(DetectCase):
    """`project_id` is a name; the profile id is an id. F6.4's `--id <project-id>` conflates them."""

    def test_the_profile_id_is_derived_and_legal(self):
        detected = self.detected(remote="git@github.com:acme/My_Repo.git", default_branch="main")
        self.assertRegex(detected["profile_id"], r"^[a-z0-9][a-z0-9-]*$")

    def test_the_human_name_is_not_mangled(self):
        detected = self.detected(remote="git@github.com:acme/My_Repo.git", default_branch="main")
        self.assertEqual(detected["project_id"], "My_Repo")
        self.assertNotEqual(detected["project_id"], detected["profile_id"])

    def test_a_name_that_derives_to_nothing_is_refused(self):
        result = self.detect(remote="git@github.com:acme/---.git", default_branch="main")
        self.assertNotEqual(result.returncode, 0)


class WriteCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        (self.ws / "profiles").mkdir()
        shutil.copytree(FIXTURES / "node-gates", self.ws / "repo")
        (self.ws / "repo" / ".vibe-suite.md").write_text("---\n---\n", encoding="utf-8")

    def fields(self, **overrides):
        base = {
            "contract_version": 1, "project_id": "Demo", "profile_id": "demo",
            "repo_id": "acme/demo", "repo_path": "./repo", "base_branch": "main",
            "source_driver": "github", "id_pattern": r"^demo-(\d+)$",
            "url_regex": r"^https://github\.com/acme/demo/issues/(\d+)/?$",
            "branch_template": "ai/{id}-{slug}", "gates": ["npm run test"],
        }
        base.update(overrides)
        return base

    def write(self, fields=None, *extra):
        return subprocess.run(
            [sys.executable, str(WRITE), "--root", str(self.ws), "--fields", "-", *extra],
            input=json.dumps(fields or self.fields()), capture_output=True, text=True, timeout=60)

    def lint(self, profile):
        return subprocess.run(
            [sys.executable, str(LINT), "--root", str(self.ws), str(profile)],
            capture_output=True, text=True, timeout=60)


class TestEndToEnd(WriteCase):
    """The gate: a generated profile that the suite's own lint accepts, in full mode."""

    def test_the_generated_profile_passes_the_real_lint(self):
        result = self.write()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        profile = self.ws / "profiles" / "demo.md"
        self.assertTrue(profile.is_file())
        lint = self.lint(profile)
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_the_pointer_names_the_profile_id(self):
        self.write()
        config = (self.ws / ".vibe-suite.md").read_text(encoding="utf-8")
        self.assertRegex(config, r"(?m)^issue2pr_profile:\s*demo\s*$")

    def test_every_required_field_is_present(self):
        self.write()
        body = (self.ws / "profiles" / "demo.md").read_text(encoding="utf-8")
        for field in sorted(REQUIRED_FIELDS):
            with self.subTest(field=field):
                self.assertRegex(body, r"(?m)^%s:" % re.escape(field))

    def test_the_not_asked_questions_are_recorded_with_reasons(self):
        """Recording the absence is the difference between a decision and an omission."""
        body = norm((self.ws / "profiles" / "demo.md").read_text(encoding="utf-8")
                    if (self.ws / "profiles" / "demo.md").exists() else "")
        self.write()
        body = norm((self.ws / "profiles" / "demo.md").read_text(encoding="utf-8"))
        self.assertIn("per-run", body)
        self.assertIn("codex", body)


class TestWriteDiscipline(WriteCase):
    """D8: everything that can fail happens before anything is published."""

    def test_an_invalid_field_set_writes_nothing(self):
        result = self.write(self.fields(id_pattern="^demo-(\\d+$"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ws / "profiles" / "demo.md").exists(),
                         "a profile that would not lint is never written")

    def test_an_existing_profile_stops_the_command_without_force(self):
        self.write()
        second = self.write()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("force", (second.stdout + second.stderr).lower())

    def test_force_overwrites_both(self):
        self.write()
        second = self.write(self.fields(project_id="Renamed"), "--force")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("Renamed", (self.ws / "profiles" / "demo.md").read_text(encoding="utf-8"))

    def test_the_pointer_edit_preserves_every_other_key_and_the_body(self):
        config = self.ws / ".vibe-suite.md"
        config.write_text("---\nscore_threshold: 80\neffort: high\n---\n\n# Notes\n\nkeep me\n",
                          encoding="utf-8")
        self.write()
        after = config.read_text(encoding="utf-8")
        self.assertIn("score_threshold: 80", after)
        self.assertIn("effort: high", after)
        self.assertIn("keep me", after)
        self.assertRegex(after, r"(?m)^issue2pr_profile:\s*demo\s*$")

    def test_a_destination_outside_the_root_is_refused(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        result = subprocess.run(
            [sys.executable, str(WRITE), "--root", str(outside), "--fields", "-"],
            input=json.dumps(self.fields()), capture_output=True, text=True, timeout=60)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr, "it must refuse in words, not by traceback")


class TestSerialization(WriteCase):
    """Repository-controlled strings meet a closed grammar, so unsupported content is refused."""

    def test_a_newline_in_a_gate_is_refused(self):
        result = self.write(self.fields(gates=["npm run test\nrm -rf /"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ws / "profiles" / "demo.md").exists())

    def test_an_unbalanced_quote_is_refused(self):
        result = self.write(self.fields(project_id="Demo's"))
        self.assertNotEqual(result.returncode, 0, "the lint's grammar has no escaping convention")

    def test_a_punctuation_heavy_gate_round_trips(self):
        """Rendered, then re-parsed by the lint's own parser, and compared to what went in."""
        gate = "pytest -q -k 'not slow' --maxfail=1"
        result = self.write(self.fields(gates=[gate]))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import profile_lint
        parsed = profile_lint.parse_frontmatter(
            (self.ws / "profiles" / "demo.md").read_text(encoding="utf-8"))
        self.assertEqual(parsed["gates"], [gate])


class TestReferenceStatesTheInterview(unittest.TestCase):
    """Contract tier: the skill *enumerates* its prompts. Elicitation is the operator's."""

    @classmethod
    def setUpClass(cls):
        cls.text = REFERENCE.read_text(encoding="utf-8")
        cls.norm = norm(cls.text)

    def test_every_asked_question_names_its_target_field(self):
        for question, field in INTERVIEW_FIELDS.items():
            with self.subTest(question=question):
                self.assertIn(field, self.text,
                              f"the prompt for {question} must name the field it fills")

    def test_the_two_unasked_questions_have_their_own_section_with_reasons(self):
        """A section, not a mention. Asserting the words appeared anywhere passed with the section
        deleted, because `review` and `backend` occur throughout a document about reviews."""
        match = re.search(r"(?ms)^###\s+Two questions this command does not ask\s*$(.*?)(?=^#{2,3}\s|\Z)",
                          self.text)
        self.assertIsNotNone(match, "the deliberately-unasked questions need their own section")
        section = norm(match.group(1))
        self.assertIn("per-run", section)
        self.assertRegex(section, r"one legal answer|codex alone|only legal")
        for topic in NOT_ASKED:
            with self.subTest(topic=topic):
                self.assertIn(topic, section)

    def test_the_core_refusal_points_at_this_command(self):
        """If the invocation differs, the refusal is a dead end."""
        self.assertIn("profile init", CORE.read_text(encoding="utf-8"))
        self.assertIn("profile init", self.text)

    def test_the_precondition_reporting_rule_is_stated(self):
        self.assertRegex(self.norm, r"everything (that is )?missing|all .{0,20}missing|not the first")


if __name__ == "__main__":
    unittest.main()
