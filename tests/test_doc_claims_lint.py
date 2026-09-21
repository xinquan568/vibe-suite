# SPDX-License-Identifier: ISC
"""Specification for `tools/doc-claims-lint.py` (vibe-230): shipped text must not describe the codebase as it used to be.

The lint is driven through its own `scan` over temporary trees (a list-based lister stands in for `git ls-files`), and
once over the real repository, where it must be clean.
"""
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
LINT_PATH = REPO_ROOT / "tools" / "doc-claims-lint.py"


def _load():
    spec = importlib.util.spec_from_file_location("doc_claims_lint_under_test", LINT_PATH)
    mod = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


lint = _load()


class Tree(unittest.TestCase):
    def tree(self, files):
        root = Path(tempfile.mkdtemp(prefix="doc-claims-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        return root, (lambda _root: sorted(files))

    def scan(self, files, allowlist=()):
        root, lister = self.tree(files)
        return lint.scan(root, lister=lister, allowlist=allowlist)


class ThePhrases(Tree):

    def test_each_phrase_fails_in_shipped_text(self):
        for phrase in lint.PHRASES:
            with self.subTest(phrase=phrase):
                violations, stale = self.scan({"commands/x.md": f"The thing is {phrase.upper()} today.\n"})
                self.assertEqual([(v[0], v[1], v[2]) for v in violations], [("commands/x.md", 1, phrase)])
                self.assertEqual(stale, [])

    def test_a_phrase_split_across_a_line_break_is_one_claim(self):
        violations, _ = self.scan({"commands/check.md": "the validator (`bin/vibe-check`, when it\nlands) is not run.\n"})
        self.assertEqual([(v[1], v[2]) for v in violations], [(1, "when it lands")])

    def test_a_phrase_wrapped_behind_a_comment_leader_is_one_claim(self):
        for leader in ("#", "//", " *", ">"):
            with self.subTest(leader=leader):
                violations, _ = self.scan({"scripts/x.py": f"{leader} the lint is NOT delivered here and remains\n"
                                                           f"{leader} open until the next release.\n"})
                self.assertEqual([(v[1], v[2]) for v in violations], [(1, "remains open")])

    def test_a_no_break_space_between_words_still_matches(self):
        violations, _ = self.scan({"commands/x.md": "This is not\u00a0yet built.\n"})
        self.assertEqual([(v[1], v[2]) for v in violations], [(1, "not yet built")])

    def test_unrelated_words_across_a_line_break_do_not_match(self):
        violations, _ = self.scan({"commands/x.md": "the loop remains\n\nopen questions are listed below\n"})
        self.assertEqual(violations, [], "a blank line ends the sentence: two paragraphs are not one claim")

    def test_unreadable_entries_are_skipped_not_fatal(self):
        """Binary content, a directory where a file was listed, and a listed path that has vanished: none is prose."""
        root, _ = self.tree({"commands/ok.md": "fine\n"})
        (root / "commands" / "blob.bin").write_bytes(b"\xff\xfe not yet built \x80")
        (root / "commands" / "adir").mkdir()
        listed = ["commands/ok.md", "commands/blob.bin", "commands/adir", "commands/gone.md"]
        try:
            got = lint.scan(root, lister=lambda _r: listed, allowlist=())
        except Exception as exc:  # noqa: BLE001 — an escape is exactly the failure this test exists to catch
            self.fail(f"scan raised {exc!r}")
        self.assertEqual(got, ([], []))

    def test_text_outside_the_shipped_scope_is_not_scanned(self):
        violations, _ = self.scan({"docs/x.md": "not yet built\n", "tests/x.py": "# when it lands\n",
                                   "tools/x.py": "# remains open\n"})
        self.assertEqual(violations, [])


class TheAllowlist(Tree):

    def test_an_allowlisted_sentence_passes(self):
        entry = ("commands/fix.md", "stops when nothing remains open", 230, "a stop condition")
        violations, stale = self.scan({"commands/fix.md": "The loop stops when nothing remains open.\n"}, (entry,))
        self.assertEqual((violations, stale), ([], []))

    def test_an_allowlist_entry_covers_only_its_own_sentence(self):
        entry = ("commands/fix.md", "stops when nothing remains open", 230, "a stop condition")
        violations, _ = self.scan({"commands/fix.md": "The loop stops when nothing remains open.\n"
                                                      "This feature is not yet built.\n"}, (entry,))
        self.assertEqual([(v[1], v[2]) for v in violations], [(2, "not yet built")])

    def test_an_allowlist_entry_covers_only_its_own_path(self):
        entry = ("commands/fix.md", "stops when nothing remains open", 230, "a stop condition")
        same = "The loop stops when nothing remains open.\n"
        violations, _ = self.scan({"commands/fix.md": same, "commands/other.md": same}, (entry,))
        self.assertEqual([(v[0], v[2]) for v in violations], [("commands/other.md", "remains open")])

    def test_an_allowlist_entry_that_allows_nothing_is_stale(self):
        entry = ("commands/fix.md", "stops when nothing remains open", 230, "a stop condition")
        violations, stale = self.scan({"commands/fix.md": "The loop stops when it is done.\n"}, (entry,))
        self.assertEqual((violations, stale), ([], [entry]))

    def test_every_real_allowlist_entry_names_an_issue_and_a_reason(self):
        for path, sub, issue, why in lint.ALLOWLIST:
            with self.subTest(path=path):
                self.assertIsInstance(issue, int)
                self.assertTrue(sub and why)


class TheLoader(unittest.TestCase):
    """The tool loads `model-pin-lint.py` with bytecode off, so no `__pycache__` lands in `tools/`, and restores the
    caller's flag afterwards, even when loading fails. Driven with the flag ON, since this module's own loader and every
    subprocess here run with it off and would hide a missing suppression."""

    def load_with(self, exec_module):
        spec = importlib.util.spec_from_file_location("x", lint.ROOT / "tools" / "model-pin-lint.py")
        spec.loader.exec_module = exec_module
        with mock.patch.object(importlib.util, "spec_from_file_location", return_value=spec):
            return lint._load_pin_lint()

    def test_bytecode_is_off_while_loading_and_restored_after(self):
        seen = []
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = False
        try:
            self.load_with(lambda mod: seen.append(sys.dont_write_bytecode))
            self.assertEqual(seen, [True], "bytecode must be off while model-pin-lint is executed")
            self.assertIs(sys.dont_write_bytecode, False, "the caller's flag must be restored")
        finally:
            sys.dont_write_bytecode = previous

    def test_the_flag_is_restored_when_loading_fails(self):
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = False
        try:
            def boom(mod):
                raise RuntimeError("load failed")
            with self.assertRaises(RuntimeError):
                self.load_with(boom)
            self.assertIs(sys.dont_write_bytecode, False)
        finally:
            sys.dont_write_bytecode = previous


class TheScope(Tree):

    def test_an_unclassified_top_level_entry_is_an_error(self):
        root, lister = self.tree({"newdir/x.md": "fine\n"})
        with self.assertRaises(lint.PIN_LINT.UnclassifiedEntryError):
            lint.scan(root, lister=lister)

    def test_the_scope_is_model_pin_lints(self):
        self.assertEqual(Path(lint.PIN_LINT.__file__).name, "model-pin-lint.py", "one home for the shipped scope")
        for rel, shipped in (("commands/x.md", True), ("docs/x.md", False), ("README.md", False)):
            with self.subTest(path=rel):
                self.assertEqual(lint.PIN_LINT.in_scope(rel), shipped)


class TheCommandLine(unittest.TestCase):
    """`main`'s exit mapping, with `scan` stubbed: the real tree is clean, so only a stub reaches the failing paths."""

    def run_main(self, outcome):
        with mock.patch.object(lint, "scan", side_effect=outcome if isinstance(outcome, Exception) else None,
                               return_value=None if isinstance(outcome, Exception) else outcome):
            with mock.patch("sys.stdout", new_callable=io.StringIO), \
                    mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                code = lint.main([])
        self.stderr = err.getvalue()
        return code

    def test_a_claim_is_exit_1(self):
        self.assertEqual(self.run_main(([("commands/x.md", 1, "not yet built", "x")], [])), 1)

    def test_a_stale_allowlist_entry_is_exit_1(self):
        self.assertEqual(self.run_main(([], [("commands/x.md", "y", 230, "z")])), 1)

    def test_a_scope_error_is_exit_1_like_model_pin_lint(self):
        for exc in (lint.PIN_LINT.UnclassifiedEntryError("newdir is unclassified"), lint.PIN_LINT.EnumerationError("no git")):
            with self.subTest(error=type(exc).__name__):
                self.assertEqual(self.run_main(exc), 1)
                self.assertIn(f"doc-claims-lint: {exc}", self.stderr, "the error must be named on stderr")

    def test_clean_is_exit_0(self):
        self.assertEqual(self.run_main(([], [])), 0)


class ThePhraseSet(unittest.TestCase):

    def test_the_phrases_are_exactly_the_issues_three(self):
        """Pinned, because the per-phrase test iterates `PHRASES` itself and would silently test fewer."""
        self.assertEqual(set(lint.PHRASES), {"not yet built", "when it lands", "remains open"})


class TheWiring(unittest.TestCase):

    def test_ci_runs_the_lint_in_the_required_lint_job(self):
        """In `lint (python + node)`, the required status context, like the P9 step: a job of its own would not gate."""
        sys.path.insert(0, str(REPO_ROOT / "tests"))
        from test_auditor_workflows import _map_get, _scalar, resolved_document
        doc = resolved_document((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
        jobs = _map_get(doc, "jobs")
        lint_job = next(v for k, v in jobs["c"] if _scalar(_map_get(v, "name")) == "lint (python + node)")
        steps = [st for st in _map_get(lint_job, "steps")["c"]
                 if "python3 tools/doc-claims-lint.py" in (_scalar(_map_get(st, "run")) or "")]
        self.assertEqual(len(steps), 1)
        step = steps[0]
        self.assertIsNone(_map_get(step, "if"), "the step must run unconditionally")
        self.assertIsNone(_map_get(step, "continue-on-error"), "the step's failure must fail the job")
        self.assertIsNone(_map_get(lint_job, "continue-on-error"))
        self.assertTrue((_scalar(_map_get(step, "run")) or "").lstrip().startswith("set -euo pipefail"))


class TheRepository(unittest.TestCase):

    def test_the_shipped_tree_is_clean(self):
        r = subprocess.run([sys.executable, "-B", str(LINT_PATH)], capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_usage_error_is_exit_2(self):
        r = subprocess.run([sys.executable, "-B", str(LINT_PATH), "--extra"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
