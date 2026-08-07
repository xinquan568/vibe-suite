#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Tests for the pinned-model-identifier lint (E0.7 / vibe-9).

These tests are the specification for `tools/model-pin-lint.py`, and they are written in three
layers because a detector fails in three independent ways.

**Matching.** A lint that matched nothing would pass a permitted-cases-only suite while enforcing
nothing — the exact defect this issue corrects, where the shipped inline pattern covered two of
AC-9's four families and reported success. So every family gets a case that must be *caught*. The
continuation cases (`gpt-5-mini`, `gpt-4o`, `gemini-2-pro`) guard a subtler version of the same
failure: a grammar narrow enough to satisfy every dotted sample while missing any id with a suffix.
Symmetrically the near-misses guard over-matching, and they matter more than usual — this lint runs
inside a required status check, so a false positive blocks every pull request in the repository.

**Scope.** `test_partition_is_total` is the structural one. `SCANNED`/`EXCLUDED` is an explicit
allowlist, whose characteristic weakness is a silent gap: add a directory, forget to list it, and it
is never scanned with nothing to say so. Asserting the partition covers every top-level entry
`git ls-files` reports converts that silence into a failing test. It must run against the real
repository via the production lister — driven by a temp-tree lister it could never see a newly
tracked entry, which is its whole purpose.

**Traversal.** One test per behaviour in the traversal contract. Enumeration failure and read failure
are tested separately because they are different branches: a broken lister and an unreadable file
fail at different points and must not be reported as one another.

`tests/` is outside the lint's own scan scope, but a dated id committed here is still a pinned id
sitting in the tree, so every dated fixture below is assembled from fragments at runtime and no
complete literal is stored. The cases stay readable — the assembly is a two-line constant, not
obfuscation — and `tests/test_auditor_workflows.py::TestNoCommittedModelIds` holds the property.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LINT_PATH = REPO_ROOT / "tools" / "model-pin-lint.py"


def _load_lint():
    """Import `tools/model-pin-lint.py` by path.

    AC-9(a) names the artifact with a hyphen, which is not an importable module name, so the
    module is loaded from its file location rather than by `import`.
    """
    if not LINT_PATH.exists():
        raise AssertionError(f"lint not found: {LINT_PATH.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location("model_pin_lint", LINT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lint = _load_lint()


def _tree_lister(root):
    """A lister over every file in a temp tree, standing in for `git ls-files`.

    Injected by the unit layer so scanning logic can be exercised without a repository. The
    subprocess layer uses the production git lister instead — see `TestSubprocessLayer`.
    """
    root = Path(root)
    found = []
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_file():
            found.append(path.relative_to(root).as_posix())
    return sorted(found)


def _write(root, relpath, content):
    path = Path(root) / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# Dated model ids are ASSEMBLED AT RUNTIME. A complete literal here would itself be the pin
# AC-9/P9 bans — this file is a fixture corpus, not shipped tooling, but the id is just as
# real on disk; `tests/test_auditor_workflows.py::TestNoCommittedModelIds` scans for them.
_D1 = "2024" + "1022"
_D2 = "2025" + "0514"
DATED_TIER_FIRST = "-".join(["claude", "3", "5", "sonnet", _D1])
DATED_TIER_NAMED = "-".join(["claude", "sonnet", "4", _D2])

# (text, must_be_flagged, why)
MATCHING_CASES = [
    # One rejection per AC-9 family. The two dated-Claude forms are listed separately because
    # they fail differently under the pattern this lint replaces: the tier-named form is caught
    # by prefix, the tier-first form is missed entirely.
    ('model = "gpt-5.6-sol"', True, "AC-9 family: gpt-<digit>"),
    ('"gemini-3.1-pro"', True, "AC-9 family: gemini-<digit>"),
    ("o3-mini", True, "AC-9 family: o<digit>-"),
    (DATED_TIER_FIRST, True, "AC-9 family: dated claude, tier-first"),
    (DATED_TIER_NAMED, True, "AC-9 family: dated claude, tier-named"),
    # Dotted suffixes. `.` is a token separator, so these tokenize to a bare id and must still
    # be caught; treating `.` as a token character would silently miss both.
    (f"models/{DATED_TIER_NAMED}.json", True, "dotted suffix: path"),
    (f"see {DATED_TIER_FIRST}.md", True, "dotted suffix: prose reference"),
    # Continuation forms. A grammar of `gpt-[0-9]` alone passes every case above — the dotted
    # samples tokenize to `gpt-5` and `gemini-3` — while missing all of these.
    ("gpt-5-mini", True, "continuation: hyphenated suffix"),
    ("gpt-4o", True, "continuation: alphanumeric suffix"),
    ("gemini-2-pro", True, "continuation: hyphenated suffix"),
    ("o1-preview", True, "continuation: o-series"),
    # Vendor-qualified dated forms. Both are official and both evade a grammar that requires the
    # date to end the token: Bedrock keeps a `-v2` suffix after it, Vertex puts the date after `@`.
    (f"anthropic.{DATED_TIER_FIRST}-v2:0", True, "vendor form: Bedrock"),
    (f"claude-3-5-sonnet-v2@{_D1}", True, "vendor form: Vertex"),
    # Permitted by AC-9: tier aliases carry no version or date.
    ("tier: sonnet", False, "permitted: bare tier alias"),
    ("opus-class", False, "permitted: tier alias"),
    ("claude-sonnet", False, "permitted: undated claude"),
    # Near-misses. Each is caught by an unanchored substring search and must not be flagged.
    ("photo3-processing", False, "near-miss: contains o3- mid-token"),
    ("my-gpt-5-wrapper", False, "near-miss: family at token interior, not start"),
    (f"deploy-claude-x-{_D1}", False, "near-miss: dated claude with a prefix"),
    (f"claude-x-{_D1}suffix", False, "near-miss: dated claude with trailing garbage"),
    ("claude-workflow-2025", False, "near-miss: 4-digit year, not an 8-digit date"),
    ("gpt-x", False, "near-miss: no digit after the hyphen"),
    # `@` belongs to the token class, so this is one token rather than a bare `gpt-5`. With `@` as
    # a separator it would fail the build on an email address — on a required check, for everyone.
    ("support@gpt-5.com", False, "near-miss: address containing a family prefix"),
    ("release-2026-07-26", False, "near-miss: a plain date"),
]


class TestTokenMatching(unittest.TestCase):
    """The four AC-9 grammars, matched against whole tokens."""

    def test_cases(self):
        for text, should_flag, why in MATCHING_CASES:
            with self.subTest(text=text, why=why):
                hits = lint.find_pins(text)
                self.assertEqual(
                    bool(hits),
                    should_flag,
                    f"{why}: expected flagged={should_flag}, got {hits!r}",
                )

    def test_case_set_is_complete(self):
        # Guards the suite against silently shrinking. 24 cases: 5 family rejections, 2
        # dotted-suffix, 4 continuation, 2 vendor-qualified, 3 permitted, 8 near-miss.
        self.assertEqual(len(MATCHING_CASES), 24)
        self.assertEqual(sum(1 for _, flag, _ in MATCHING_CASES if flag), 13)

    def test_every_ac9_family_has_a_grammar(self):
        self.assertEqual(len(lint.GRAMMARS), 4)

    def test_dot_is_a_token_separator(self):
        # The load-bearing tokenizer property. If `.` were a token character,
        # the dated tier-named id with a `.json` suffix would be ONE token and the end anchor
        # would reject it.
        self.assertEqual(lint.tokenize("a.b-c"), ["a", "b-c"])

    def test_at_sign_is_a_token_character(self):
        # The converse property. Vertex writes the date after `@`; splitting there would hide it.
        self.assertEqual(lint.tokenize("a@b.c"), ["a@b", "c"])

    def test_reports_the_matched_token(self):
        self.assertEqual(lint.find_pins('model = "o3-mini"'), ["o3-mini"])


class TestScope(unittest.TestCase):
    """Which files the lint looks at."""

    def test_partition_is_total(self):
        # The test that makes an explicit allowlist safe: a new top-level entry fails here until
        # it is classified as scanned or excluded. Runs against the real repository through the
        # production lister, so it sees what actually ships.
        entries = {path.split("/")[0] for path in lint.git_lister(REPO_ROOT)}
        classified = lint.SCANNED | lint.EXCLUDED
        self.assertEqual(
            entries - classified,
            set(),
            "unclassified top-level entries: add each to SCANNED or EXCLUDED in "
            "tools/model-pin-lint.py",
        )

    def test_partition_is_disjoint(self):
        self.assertEqual(lint.SCANNED & lint.EXCLUDED, set())

    def test_excluded_directories_are_not_scanned(self):
        for area in ("tools", "tests", "docs", ".github"):
            with self.subTest(area=area):
                with tempfile.TemporaryDirectory() as tmp:
                    _write(tmp, f"{area}/thing.md", DATED_TIER_NAMED + "\n")
                    self.assertEqual(lint.scan(tmp, lister=_tree_lister), [])

    def test_scanned_directories_are_scanned(self):
        # codex-src (E7.1 / vibe-53): hand-authored Codex-side sources ship to another agent's
        # runtime, so they are inside AC-9's shipped-artifact scope like the codex/ mirror.
        for area in ("commands", "schemas", "templates", "codex-src"):
            with self.subTest(area=area):
                with tempfile.TemporaryDirectory() as tmp:
                    _write(tmp, f"{area}/thing.md", DATED_TIER_NAMED + "\n")
                    self.assertEqual(len(lint.scan(tmp, lister=_tree_lister)), 1)

    def test_root_readme_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "README.md", "gpt-5.6-sol\n")
            self.assertEqual(lint.scan(tmp, lister=_tree_lister), [])

    def test_nested_readme_inside_a_scanned_directory_is_scanned(self):
        # Exemption is positional, not by filename. A README under `templates/` is rendered into
        # every scaffolded project, so a pin there would propagate rather than stay put.
        for relpath in ("skills/README.md", "templates/README.md"):
            with self.subTest(relpath=relpath):
                with tempfile.TemporaryDirectory() as tmp:
                    _write(tmp, relpath, "gpt-5.6-sol\n")
                    self.assertEqual(len(lint.scan(tmp, lister=_tree_lister)), 1)

    def test_root_changelog_is_not_scanned(self):
        # AC-9 places `docs/CHANGELOG` outside enforcement. None exists yet, so the classification
        # is pre-declared: adding one should be an ordinary commit, not a build break.
        for name in ("CHANGELOG", "CHANGELOG.md", "CHANGELOG.rst"):
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as tmp:
                    _write(tmp, name, "gpt-5.6-sol\n")
                    self.assertEqual(lint.scan(tmp, lister=_tree_lister), [])

    def test_nested_changelog_inside_a_scanned_directory_is_scanned(self):
        # Exemption is positional, matching the README rule: a changelog shipped inside a skill is
        # a shipped artifact.
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "skills/CHANGELOG.md", "gpt-5.6-sol\n")
            self.assertEqual(len(lint.scan(tmp, lister=_tree_lister)), 1)

    def test_unclassified_top_level_entry_is_not_scanned_silently(self):
        # An entry in neither set is a configuration error, not a pass. `test_partition_is_total`
        # is what surfaces it in the real repository; here the behaviour itself is pinned.
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "brand-new-dir/thing.md", "gpt-5.6-sol\n")
            with self.assertRaises(lint.UnclassifiedEntryError):
                lint.scan(tmp, lister=_tree_lister)


class TestTraversal(unittest.TestCase):
    """One test per behaviour in the traversal contract."""

    def test_only_tracked_files_are_read(self):
        # "Tracked" is a property of the injected lister, not of the scanning logic. A file the
        # lister does not report is never opened, which is what keeps `__pycache__/*.pyc` — written
        # by the py_compile step of the same CI job — out of the scan.
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "skills/tracked.md", "clean\n")
            _write(tmp, "skills/untracked.md", "gpt-5.6-sol\n")
            only_tracked = lambda root: ["skills/tracked.md"]  # noqa: E731
            self.assertEqual(lint.scan(tmp, lister=only_tracked), [])

    def test_results_are_in_sorted_path_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("c.md", "a.md", "b.md"):
                _write(tmp, f"skills/{name}", "o3-mini\n")
            paths = [v.path for v in lint.scan(tmp, lister=_tree_lister)]
            self.assertEqual(paths, sorted(paths))
            self.assertEqual(paths, ["skills/a.md", "skills/b.md", "skills/c.md"])

    def test_symlinks_are_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(tmp, "skills/real.md", "clean\n")
            # The target lives under an excluded directory so that following the link would be
            # the only way to reach its contents.
            target = _write(tmp, "docs/outside.md", "gpt-5.6-sol\n")
            link = Path(tmp) / "skills" / "link.md"
            os.symlink(target, link)
            self.assertEqual(lint.scan(tmp, lister=_tree_lister), [])

    def test_undecodable_file_is_skipped_with_a_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "skills").mkdir()
            (Path(tmp) / "skills" / "blob.bin").write_bytes(b"\xff\xfe\x00binary")
            notices = []
            self.assertEqual(lint.scan(tmp, lister=_tree_lister, notice=notices.append), [])
            self.assertEqual(len(notices), 1)
            self.assertIn("skills/blob.bin", notices[0])

    def test_read_error_fails_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = lambda root: ["skills/vanished.md"]  # noqa: E731
            with self.assertRaises(lint.ReadError):
                lint.scan(tmp, lister=missing)

    def test_enumeration_error_fails_the_run(self):
        # A distinct branch from a read failure: the lister itself did not produce a list, so
        # there is no file to blame and no partial result to report.
        def broken(root):
            raise lint.EnumerationError("git ls-files failed")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lint.EnumerationError):
                lint.scan(tmp, lister=broken)

    def test_read_and_enumeration_errors_are_distinct_types(self):
        self.assertFalse(issubclass(lint.ReadError, lint.EnumerationError))
        self.assertFalse(issubclass(lint.EnumerationError, lint.ReadError))

    def test_git_lister_raises_enumeration_error_outside_a_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(lint.EnumerationError):
                lint.git_lister(tmp)

    def test_git_lister_survives_an_undecodable_tracked_filename(self):
        # A POSIX filename is an arbitrary byte string, and decoding git's output strictly would
        # raise UnicodeDecodeError out of the lister rather than the documented EnumerationError.
        # The decode path is driven directly rather than through a fixture: APFS refuses to create
        # a file whose name is not valid UTF-8 (EILSEQ), so an end-to-end version of this test
        # would be impossible to run on macOS and would only ever execute on CI.
        class _Completed:
            returncode = 0
            stdout = b"skills/bad\xff\xfename.md\x00skills/ok.md\x00"
            stderr = b""

        with unittest.mock.patch.object(lint.subprocess, "run", return_value=_Completed()):
            listed = lint.git_lister(".")
        self.assertEqual(len(listed), 2)
        self.assertIn("skills/ok.md", listed)
        # Round-trips back to the original bytes, which is what lets the file actually be opened.
        recovered = [name.encode("utf-8", "surrogateescape") for name in listed]
        self.assertIn(b"skills/bad\xff\xfename.md", recovered)


def _git_repo(root, files):
    """Build a temporary git repository with `files` staged.

    The production lister is `git ls-files`, which fails outside a repository and reports nothing
    for untracked files inside one. Without `git init` + `git add` a subprocess fixture would scan
    an empty list, and "clean tree passes" would be indistinguishable from "nothing was examined".
    """
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    subprocess.run(["git", "init", "-q"], cwd=root, check=True, env=env)
    for relpath, content in files.items():
        _write(root, relpath, content)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)


class TestSubprocessLayer(unittest.TestCase):
    """The real CLI, invoked as CI invokes it."""

    def _run(self, root, *args):
        return subprocess.run(
            [sys.executable, str(LINT_PATH), *args],
            cwd=root,
            capture_output=True,
            text=True,
        )

    def test_clean_tree_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _git_repo(tmp, {"skills/ok.md": "uses the sonnet tier\n"})
            result = self._run(tmp)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_violating_tree_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            _git_repo(tmp, {"skills/bad.md": f"model: {DATED_TIER_NAMED}\n"})
            result = self._run(tmp)
            self.assertEqual(result.returncode, 1)

    def test_diagnostic_names_path_line_and_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            _git_repo(tmp, {"skills/bad.md": "first\nmodel: o3-mini\n"})
            out = self._run(tmp).stdout
            self.assertIn("skills/bad.md:2:", out)
            self.assertIn("o3-mini", out)

    def test_diagnostic_includes_the_source_line(self):
        # Splitting on `.` means the matched token can be a prefix of the id as written, so the
        # token alone would under-report: `gpt-5.6-sol` is reported via the token `gpt-5`.
        with tempfile.TemporaryDirectory() as tmp:
            _git_repo(tmp, {"skills/bad.md": 'model = "gpt-5.6-sol"\n'})
            out = self._run(tmp).stdout
            self.assertIn("gpt-5.6-sol", out)

    def test_untracked_violation_is_not_reported(self):
        # The tracked-only rule through the production lister rather than an injected one. An
        # in-process test that hands `scan` a list omitting the file cannot catch `git_lister`
        # regressing to enumerate untracked paths, because it never calls it.
        with tempfile.TemporaryDirectory() as tmp:
            _git_repo(tmp, {"skills/ok.md": "the sonnet tier\n"})
            _write(tmp, "skills/untracked.md", "o3-mini\n")
            result = self._run(tmp)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_explicit_root_argument(self):
        # Run from a *clean repository* rather than a non-repository. Invoked from a bare temp dir
        # this would exit 1 whether or not the root argument was honoured — enumeration would fail
        # either way — so the assertion could not distinguish the two.
        with tempfile.TemporaryDirectory() as violating:
            _git_repo(violating, {"skills/bad.md": "o3-mini\n"})
            with tempfile.TemporaryDirectory() as clean:
                _git_repo(clean, {"skills/ok.md": "the sonnet tier\n"})
                self.assertEqual(self._run(clean).returncode, 0, "fixture must be clean")
                result = self._run(clean, violating)
                self.assertEqual(result.returncode, 1)
                self.assertIn("skills/bad.md", result.stdout)

    def test_non_repository_root_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(tmp)
            self.assertEqual(result.returncode, 1)
            self.assertIn("enumerat", (result.stdout + result.stderr).lower())

    def test_real_repository_is_clean(self):
        # The acceptance criterion's other half, against the tree that actually ships.
        result = self._run(REPO_ROOT, str(REPO_ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TestCIWiring(unittest.TestCase):
    """`ci.yml` is outside the lint's scan scope, so this is the only lasting check on it."""

    def setUp(self):
        self.workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    @staticmethod
    def _invocations(text):
        """Executable invocations of the lint — comments excluded.

        Counting the bare substring is not enough: a commented-out `# python3
        tools/model-pin-lint.py` satisfies a substring count and a region check while the gate no
        longer runs at all.
        """
        return [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("python3 tools/model-pin-lint.py")
        ]

    def test_required_lint_job_invokes_the_tool_exactly_once(self):
        # Positive half. A purely negative assertion would also pass if the step were deleted
        # outright, leaving P9 unenforced and the test still green.
        self.assertEqual(len(self._invocations(self.workflow)), 1)

    def test_the_invocation_lives_in_the_required_job(self):
        # `lint (python + node)` is a required status context on main; a new job would not be,
        # so it could fail without blocking a merge.
        lint_job = self.workflow.split("name: lint (python + node)", 1)[1].split("\n  test:", 1)[0]
        self.assertEqual(len(self._invocations(lint_job)), 1)

    def test_a_commented_out_invocation_does_not_count(self):
        # Pins the discriminating property itself, so the check cannot quietly weaken back into a
        # substring count.
        self.assertEqual(self._invocations("        # python3 tools/model-pin-lint.py"), [])

    def test_no_inline_family_pattern_remains(self):
        # Negative half. Two copies of the pattern is how the shipped gap arose: the inline step
        # drifted from AC-9 with nothing comparing them.
        self.assertNotIn("gpt-[0-9]", self.workflow)
        self.assertNotIn("gemini-[0-9]", self.workflow)



class EscapedPinsAreAKnownGap(unittest.TestCase):
    """Pins the DECISION, so the gap is visible and the reverted fix is not re-attempted blind.

    A pinned id spelled with string escapes is invisible to this scanner. Closing it by decoding
    escapes was tried and reverted: correct decoding needs the language and string context, so
    the attempt missed the eight-digit `\\U` form and reported a pin for a Python RAW string
    containing no escape at all. A repo-wide gate that fails honest code is worse than one with
    a known evasion, and P9's job is to catch accidental pinning, not deliberate encoding.
    """

    def test_an_escaped_pin_is_not_detected_and_that_is_recorded(self):
        line = 'model: "claude-opus-4-" "2025051\\u0034"'
        self.assertEqual(lint.find_pins(line), [],
                         "if this starts passing, the gap closed — update this test and the "
                         "note in tools/model-pin-lint.py")

    def test_a_python_raw_string_is_not_reported_as_a_pin(self):
        """The false positive the reverted fix introduced. This is the regression guard."""
        self.assertEqual(lint.find_pins(r'X = r"gpt-\x35"'), [],
                         "a raw string contains no escape; flagging it breaks honest builds")

    def test_a_plainly_written_pin_is_still_caught(self):
        self.assertTrue(lint.find_pins("model: gpt-5.6-sol"))
        self.assertTrue(lint.find_pins("model: claude-opus-4-" + "2025" + "0514"))


if __name__ == "__main__":
    unittest.main()
