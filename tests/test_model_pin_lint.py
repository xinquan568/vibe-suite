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

`tests/` is outside the lint's scan scope, which is what lets the cases below be written as plain
literals instead of obfuscated strings.
"""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
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


# (text, must_be_flagged, why)
MATCHING_CASES = [
    # One rejection per AC-9 family. The two dated-Claude forms are listed separately because
    # they fail differently under the pattern this lint replaces: the tier-named form is caught
    # by prefix, the tier-first form is missed entirely.
    ('model = "gpt-5.6-sol"', True, "AC-9 family: gpt-<digit>"),
    ('"gemini-3.1-pro"', True, "AC-9 family: gemini-<digit>"),
    ("o3-mini", True, "AC-9 family: o<digit>-"),
    ("claude-3-5-sonnet-20241022", True, "AC-9 family: dated claude, tier-first"),
    ("claude-sonnet-4-20250514", True, "AC-9 family: dated claude, tier-named"),
    # Dotted suffixes. `.` is a token separator, so these tokenize to a bare id and must still
    # be caught; treating `.` as a token character would silently miss both.
    ("models/claude-sonnet-4-20250514.json", True, "dotted suffix: path"),
    ("see claude-3-5-sonnet-20241022.md", True, "dotted suffix: prose reference"),
    # Continuation forms. A grammar of `gpt-[0-9]` alone passes every case above — the dotted
    # samples tokenize to `gpt-5` and `gemini-3` — while missing all of these.
    ("gpt-5-mini", True, "continuation: hyphenated suffix"),
    ("gpt-4o", True, "continuation: alphanumeric suffix"),
    ("gemini-2-pro", True, "continuation: hyphenated suffix"),
    ("o1-preview", True, "continuation: o-series"),
    # Permitted by AC-9: tier aliases carry no version or date.
    ("tier: sonnet", False, "permitted: bare tier alias"),
    ("opus-class", False, "permitted: tier alias"),
    ("claude-sonnet", False, "permitted: undated claude"),
    # Near-misses. Each is caught by an unanchored substring search and must not be flagged.
    ("photo3-processing", False, "near-miss: contains o3- mid-token"),
    ("my-gpt-5-wrapper", False, "near-miss: family at token interior, not start"),
    ("deploy-claude-x-20241022", False, "near-miss: dated claude with a prefix"),
    ("claude-x-20241022suffix", False, "near-miss: dated claude with trailing garbage"),
    ("claude-workflow-2025", False, "near-miss: 4-digit year, not an 8-digit date"),
    ("gpt-x", False, "near-miss: no digit after the hyphen"),
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
        # Guards the suite against silently shrinking. The plan fixes this at 20 cases: 5 family
        # rejections, 2 dotted-suffix, 4 continuation, 3 permitted, 6 near-miss.
        self.assertEqual(len(MATCHING_CASES), 20)
        self.assertEqual(sum(1 for _, flag, _ in MATCHING_CASES if flag), 11)

    def test_every_ac9_family_has_a_grammar(self):
        self.assertEqual(len(lint.GRAMMARS), 4)

    def test_dot_is_a_token_separator(self):
        # The load-bearing tokenizer property. If `.` were a token character,
        # `claude-sonnet-4-20250514.json` would be one token and the end anchor would reject it.
        self.assertEqual(lint.tokenize("a.b-c"), ["a", "b-c"])

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
                    _write(tmp, f"{area}/thing.md", "claude-sonnet-4-20250514\n")
                    self.assertEqual(lint.scan(tmp, lister=_tree_lister), [])

    def test_scanned_directories_are_scanned(self):
        for area in ("commands", "schemas", "templates"):
            with self.subTest(area=area):
                with tempfile.TemporaryDirectory() as tmp:
                    _write(tmp, f"{area}/thing.md", "claude-sonnet-4-20250514\n")
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

    def test_nested_changelog_inside_a_scanned_directory_is_scanned(self):
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
            _git_repo(tmp, {"skills/bad.md": "model: claude-sonnet-4-20250514\n"})
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

    def test_explicit_root_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            _git_repo(tmp, {"skills/bad.md": "o3-mini\n"})
            with tempfile.TemporaryDirectory() as elsewhere:
                result = self._run(elsewhere, tmp)
                self.assertEqual(result.returncode, 1)

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

    def test_required_lint_job_invokes_the_tool_exactly_once(self):
        # Positive half. A purely negative assertion would also pass if the step were deleted
        # outright, leaving P9 unenforced and the test still green.
        self.assertEqual(self.workflow.count("tools/model-pin-lint.py"), 1)

    def test_the_invocation_lives_in_the_required_job(self):
        # `lint (python + node)` is a required status context on main; a new job would not be,
        # so it could fail without blocking a merge.
        lint_job = self.workflow.split("name: lint (python + node)", 1)[1].split("\n  test:", 1)[0]
        self.assertIn("tools/model-pin-lint.py", lint_job)

    def test_no_inline_family_pattern_remains(self):
        # Negative half. Two copies of the pattern is how the shipped gap arose: the inline step
        # drifted from AC-9 with nothing comparing them.
        self.assertNotIn("gpt-[0-9]", self.workflow)
        self.assertNotIn("gemini-[0-9]", self.workflow)


if __name__ == "__main__":
    unittest.main()
