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
        payload = {"root": str(FIXTURES / facts.pop("fixture", "node-gates")),
                   "is_git_repository": True}
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

    def test_a_non_git_directory_is_refused(self):
        """The first documented precondition, which nothing checked until the review found it."""
        result = self.detect(remote="git@github.com:acme/demo.git", default_branch="main",
                             is_git_repository=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git repository", (result.stdout + result.stderr).lower())

    def test_all_three_preconditions_are_reported_together(self):
        result = self.detect(fixture="no-remote", remote=None, default_branch=None,
                             is_git_repository=False)
        report = (result.stdout + result.stderr).lower()
        for phrase in ("git repository", "origin", "branch"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, report)

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

    def test_the_pointer_edit_preserves_every_other_byte(self):
        """Byte equality, not substring presence.

        Substring assertions pass while the file is rebuilt around them — line endings normalised,
        blank lines dropped, ordering changed. What the claim says is that untouched bytes are
        untouched, so that is what is compared.
        """
        config = self.ws / ".vibe-suite.md"
        before = "---\nscore_threshold: 80\neffort: high\n---\n\n# Notes\n\nkeep me\n"
        config.write_text(before, encoding="utf-8", newline="")
        self.assertEqual(self.write().returncode, 0)
        after = config.read_bytes().decode("utf-8")
        self.assertEqual(after.replace("issue2pr_profile: demo\n", ""), before,
                         "everything except the inserted entry must be byte-identical")

    def test_crlf_line_endings_survive(self):
        config = self.ws / ".vibe-suite.md"
        config.write_text("---\r\nscore_threshold: 80\r\n---\r\n\r\nbody\r\n",
                          encoding="utf-8", newline="")
        self.assertEqual(self.write().returncode, 0)
        after = config.read_bytes().decode("utf-8")
        self.assertIn("\r\n", after, "reading with translation would have destroyed these")
        self.assertNotIn("\n\n\n", after)

    def test_a_body_line_that_looks_like_the_pointer_is_not_configuration(self):
        """Searching the whole document made a sentence about configuration into configuration."""
        config = self.ws / ".vibe-suite.md"
        # At column 0, inside a fenced example — the shape a document explaining configuration
        # actually has. Indented or inline, `^` never matched it and the test proved nothing.
        config.write_text("---\n---\n\n# Notes\n\n```\nissue2pr_profile: other\n```\n",
                          encoding="utf-8")
        result = self.write()
        self.assertEqual(result.returncode, 0,
                         "a body line is prose, and must not demand --force: " + result.stderr)

    def test_force_repoints_from_a_different_existing_id(self):
        config = self.ws / ".vibe-suite.md"
        config.write_text("---\nissue2pr_profile: other\n---\n", encoding="utf-8")
        without = self.write()
        self.assertNotEqual(without.returncode, 0, "repointing needs --force")
        self.assertIn("other", without.stdout + without.stderr)
        with_force = self.write(None, "--force")
        self.assertEqual(with_force.returncode, 0, with_force.stderr)
        self.assertRegex(config.read_text(encoding="utf-8"), r"(?m)^issue2pr_profile: demo$")

    def test_a_symlinked_profile_destination_is_refused(self):
        """The actual containment boundary.

        The previous version declared an *empty* directory as the root and called the resulting failure
        a containment refusal — it failed because `./repo` was absent, which proves nothing about
        containment.
        """
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        (outside / "planted.md").write_text("planted\n", encoding="utf-8")
        (self.ws / "profiles" / "demo.md").symlink_to(outside / "planted.md")
        result = self.write()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", (result.stdout + result.stderr).lower())
        self.assertEqual((outside / "planted.md").read_text(encoding="utf-8"), "planted\n",
                         "the symlink target must not be written through")

    def test_a_symlinked_pointer_is_refused(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside, True)
        (outside / "config.md").write_text("planted\n", encoding="utf-8")
        (self.ws / ".vibe-suite.md").unlink(missing_ok=True)
        (self.ws / ".vibe-suite.md").symlink_to(outside / "config.md")
        result = self.write()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((outside / "config.md").read_text(encoding="utf-8"), "planted\n")


class TestOptionalFieldsSurvive(WriteCase):
    """The interview's whole output. An earlier writer rendered the required fields and dropped these."""

    def interview(self):
        return self.fields(
            tdd_policy="A behavioural change lands with a test that fails without it.",
            anti_patterns=["Editing generated files by hand.", "Shipping without a flag."],
            mental_model_refs=["docs/architecture.md"],
            scenario_overrides={"hotfix": "bug-fix"},
        )

    def parsed(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import profile_lint
        return profile_lint.parse_frontmatter(
            (self.ws / "profiles" / "demo.md").read_text(encoding="utf-8"))

    def test_every_interview_field_round_trips(self):
        result = self.write(self.interview())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        parsed = self.parsed()
        self.assertIn("A behavioural change", parsed["tdd_policy"])
        self.assertEqual(len(parsed["anti_patterns"]), 2)
        self.assertEqual(parsed["mental_model_refs"], ["docs/architecture.md"])
        self.assertEqual(parsed["scenario_overrides"], {"hotfix": "bug-fix"})

    def test_a_profile_with_interview_fields_still_passes_the_real_lint(self):
        self.assertEqual(self.write(self.interview()).returncode, 0)
        lint = self.lint(self.ws / "profiles" / "demo.md")
        self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_an_unknown_field_is_refused_rather_than_dropped(self):
        """Rendering only known fields would swallow a misspelling — which is what the contract's
        unknown-field rule exists to prevent, so the writer must not defeat the lint it then runs."""
        result = self.write(self.fields(tdd_polcy="strict"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tdd_polcy", result.stdout + result.stderr)
        self.assertFalse((self.ws / "profiles" / "demo.md").exists())


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


class TestInjection(WriteCase):
    """A check that does not reach everything it renders is not a check."""

    def test_a_newline_in_a_map_value_cannot_inject_a_field(self):
        """The regression this commit's predecessor introduced.

        Rendering gained map fields while the refusal still looked only at scalars and lists, so a
        `scenario_overrides` value carrying a newline wrote a **new top-level field** — and the
        in-memory lint then saw a syntactically fine document and reported nothing.
        """
        result = self.write(self.fields(
            scenario_overrides={"hotfix": "bug-fix'\nreviewer_backend: 'injected"}))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.ws / "profiles" / "demo.md").exists())
        # The *grammar* check must be what refuses. Asserting only that "inject" appeared passed even
        # with map inspection removed, because the injected field happened to be one the lint knows
        # and its own error message contained the word — a coincidence, not a check.
        report = result.stdout + result.stderr
        self.assertIn("cannot carry", report,
                      "the refusal must come from the renderability check, not from the lint "
                      "happening to dislike whatever got injected")
        self.assertIn("scenario_overrides", report, "and it must name the path that reaches it")

    def test_a_newline_in_a_map_key_cannot_inject_a_field(self):
        result = self.write(self.fields(
            scenario_overrides={"hotfix'\nreviewer_backend: 'x": "bug-fix"}))
        self.assertNotEqual(result.returncode, 0)

    def test_the_failure_names_the_path_that_reaches_the_value(self):
        result = self.write(self.fields(anti_patterns=["fine", "bad\nvalue"]))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("anti_patterns[1]", result.stdout + result.stderr)


class TestCrlfPointer(WriteCase):
    def test_an_existing_crlf_pointer_is_replaced_not_duplicated(self):
        """`[ \t]*$` cannot consume a carriage return, so a CRLF file matched nothing and the entry
        was appended — a duplicate key in a grammar that forbids them."""
        config = self.ws / ".vibe-suite.md"
        config.write_text("---\r\nissue2pr_profile: other\r\n---\r\n",
                          encoding="utf-8", newline="")
        result = self.write(None, "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        after = config.read_bytes().decode("utf-8")
        self.assertEqual(after.count("issue2pr_profile:"), 1, "the entry must be replaced, not added")
        self.assertIn("demo", after)
        # The pattern consumes the CR, so the replacement must restore it. Otherwise the one line it
        # touched becomes LF and the document is left with mixed endings.
        self.assertNotIn("\n", after.replace("\r\n", ""),
                         "every line ending must still be CRLF")


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

    def test_the_procedure_names_both_programs(self):
        """Without this the slash command could assemble a profile by hand and bypass every
        conversion, guard and in-memory lint the two programs exist to hold."""
        for program in ("scripts/detect_profile.py", "scripts/write_profile.py"):
            with self.subTest(program=program):
                self.assertIn(program, self.text)

    def test_the_procedure_defines_the_facts_handoff(self):
        for fact in ("is_git_repository", "remote", "default_branch", "login"):
            with self.subTest(fact=fact):
                self.assertIn(fact, self.text)

    def test_the_smoke_check_is_specified_including_its_skip(self):
        """A warning string is not a smoke check. The procedure must say what runs and when it does
        not, because an unrun check reported as passing is worse than either."""
        self.assertRegex(self.norm, r"gh issue list")
        self.assertIn("skipped", self.norm)
        self.assertRegex(self.norm, r"does not stop the write|not stop the write")

    def test_the_exit_codes_are_documented(self):
        for code in ("0", "1", "2", "3", "4"):
            with self.subTest(code=code):
                self.assertRegex(self.text, r"`?%s`?[ ]" % code)

    def test_the_precondition_reporting_rule_is_stated(self):
        self.assertRegex(self.norm, r"everything (that is )?missing|all .{0,20}missing|not the first")


if __name__ == "__main__":
    unittest.main()
