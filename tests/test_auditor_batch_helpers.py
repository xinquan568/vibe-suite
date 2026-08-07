# SPDX-License-Identifier: ISC
"""Behavioural tests for the E8.3 batch and citation helpers.

These are the helpers that act on OTHER PEOPLE'S repositories — labelling issues, dispatching
workflows, writing links into the rulebook. The mutation contract and shared primitives are in
`auditor_helpers_support`.
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


class Test_batch_process(unittest.TestCase):
    """`batch-process.py` — every call here touches a third party's repository."""

    HELPER = SCRIPTS / "batch-process.py"
    #: The ENTIRE validation block. Replacing only its first refusal is not the
    #: mutant it looks like: the read then fails on its own and a later refusal
    #: fires, so the test would pass while proving nothing about the guard.
    REG_ANCHOR = '    if not registry_path.is_file():\n        refuse("registry-missing")\n    try:\n        raw = registry_path.read_text(encoding="utf-8")\n    except OSError:\n        refuse("registry-unreadable")\n    try:\n        registry = json.loads(raw)\n    except json.JSONDecodeError:\n        refuse("registry-unreadable")\n    repos = registry.get("repos") if isinstance(registry, dict) else None\n    if not isinstance(repos, dict):\n        refuse("registry-malformed")'
    REG_MUTANT = '    repos = {}'

    def _gh(self):
        d = Path(tempfile.mkdtemp())
        script = d / "gh"
        script.write_text("#!/usr/bin/env bash\n"
                          'printf "%s\\n" "$*" >> "$(dirname "$0")/calls.log"\n'
                          "exit 0\n", encoding="utf-8")
        script.chmod(0o755)
        return d

    def _calls(self, ghdir):
        log = ghdir / "calls.log"
        return log.read_text().splitlines() if log.is_file() else []

    def _data_dir(self, repos=None, raw=None):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        if raw is not None:
            (d / "registry" / "repos.json").write_text(raw, encoding="utf-8")
        elif repos is not None:
            (d / "registry" / "repos.json").write_text(
                json.dumps({"repos": repos}), encoding="utf-8")
        return d

    DISCOVERED = {f"acme/r{i}": {"status": "discovered", "issue_number": 100 + i}
                  for i in range(8)}

    def _run(self, d, ghdir, extra=(), script_text=None):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "batch-process.py"
            helper.write_text(script_text, encoding="utf-8")
        env = dict(os.environ, PATH=f"{ghdir}:{os.environ['PATH']}")
        return subprocess.run([sys.executable, str(helper), "--data-dir", str(d),
                               "--stage", "audit", *extra],
                              capture_output=True, text=True, env=env)

    # --- oracle ---------------------------------------------------------------------------
    def test_only_eligible_repositories_are_dispatched(self):
        repos = dict(self.DISCOVERED)
        repos["acme/done"] = {"status": "complete", "issue_number": 999}
        gh = self._gh()
        r = self._run(self._data_dir(repos), gh, extra=("--apply", "--batch-size", "10"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("999", " ".join(self._calls(gh)),
                         "a completed repository was dispatched")

    def test_the_batch_size_is_never_exceeded(self):
        """This is a rate limit on other people's repositories, not a tuning knob."""
        gh = self._gh()
        self._run(self._data_dir(self.DISCOVERED), gh, extra=("--apply", "--batch-size", "3"))
        labelled = [c for c in self._calls(gh) if "issue edit" in c]
        self.assertEqual(len(labelled), 3, f"dispatched {len(labelled)} of a 3-repo batch")

    def test_a_dry_run_issues_no_mutating_call(self):
        gh = self._gh()
        r = self._run(self._data_dir(self.DISCOVERED), gh)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self._calls(gh), [], "a dry run reached gh")
        self.assertIn("would run:", r.stdout)

    def test_the_dry_run_plan_matches_what_apply_does(self):
        gh_dry = self._gh()
        planned = [ln.split("would run: ", 1)[1] for ln in
                   self._run(self._data_dir(self.DISCOVERED), gh_dry,
                             extra=("--batch-size", "2")).stdout.splitlines()
                   if "would run:" in ln]
        gh_apply = self._gh()
        self._run(self._data_dir(self.DISCOVERED), gh_apply,
                  extra=("--apply", "--batch-size", "2"))
        actual = ["gh " + c for c in self._calls(gh_apply)]
        self.assertEqual(planned, actual)

    def test_each_repository_is_labelled_then_dispatched(self):
        gh = self._gh()
        self._run(self._data_dir({"acme/r0": {"status": "discovered", "issue_number": 100}}),
                  gh, extra=("--apply",))
        calls = self._calls(gh)
        self.assertTrue(calls[0].startswith("issue edit 100 --add-label audit-ready"), calls)
        self.assertIn("workflow run auditor-audit.yml", calls[1])
        self.assertIn("repo=acme/r0", calls[1])

    # --- refusals -------------------------------------------------------------------------
    def test_a_missing_registry_refuses_before_any_call(self):
        gh = self._gh()
        r = self._run(self._data_dir(), gh, extra=("--apply",))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:batch-process:registry-missing", r.stderr)
        self.assertEqual(self._calls(gh), [])

    def test_an_unreadable_registry_refuses_before_any_call(self):
        gh = self._gh()
        r = self._run(self._data_dir(raw="{not json"), gh, extra=("--apply",))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("registry-unreadable", r.stderr)
        self.assertEqual(self._calls(gh), [])

    def test_a_zero_batch_size_is_refused(self):
        r = self._run(self._data_dir(self.DISCOVERED), self._gh(),
                      extra=("--batch-size", "0"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("batch-size-invalid", r.stderr)

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        gh = self._gh()
        self._run(self._data_dir(self.DISCOVERED), gh, extra=("--apply",),
                  script_text=NOOP[".py"])
        self.assertEqual(self._calls(gh), [], "sanity: a no-op calls nothing")

    def test_the_empty_registry_mutant_keeps_going_after_it_cannot_read(self):
        """The plausible wrong implementation: a missing registry becomes an empty one. The run
        exits zero having done nothing, while the registry that would have said otherwise sits
        unread — and 'nothing eligible' and 'I cannot tell' look identical afterwards."""
        src = self.HELPER.read_text(encoding="utf-8")
        self.assertIn(self.REG_ANCHOR, src, "mutation anchor missing")
        gh = self._gh()
        r = self._run(self._data_dir(), gh, extra=("--apply",),
                      script_text=src.replace(self.REG_ANCHOR, self.REG_MUTANT, 1))
        self.assertEqual(r.returncode, 0,
                         "mutation ineffective: the mutant should proceed with no registry")


if __name__ == "__main__":
    unittest.main()
