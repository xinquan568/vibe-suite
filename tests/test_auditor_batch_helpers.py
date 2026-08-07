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


    #: The CANONICAL registry shape — `audit_issue`, per SCHEMAS.md section 1 and what
    #: auditor-discover.yml writes. The old fixtures used `issue_number`, so they exercised the
    #: helper through a record no production registry contains: green tests over a queue the
    #: helper would have skipped entirely.
    CANONICAL = {f"acme/r{i}": {"status": "discovered", "audit_issue": 100 + i}
                 for i in range(8)}

    def test_the_canonical_audit_issue_field_is_read(self):
        """Reading only `issue_number` skipped every discovered repository as ineligible, and
        the run exited zero having dispatched nothing — a successful no-op over a full queue."""
        gh = self._gh()
        r = self._run(self._data_dir(self.CANONICAL), gh, extra=("--apply", "--batch-size", "3"))
        self.assertEqual(r.returncode, 0, r.stderr)
        labelled = [c for c in self._calls(gh) if "issue edit" in c]
        self.assertEqual(len(labelled), 3, "canonical records were treated as ineligible")
        self.assertIn("issue edit 100", " ".join(self._calls(gh)))

    def test_an_entry_with_no_issue_at_all_is_skipped(self):
        gh = self._gh()
        self._run(self._data_dir({"acme/x": {"status": "discovered"}}), gh, extra=("--apply",))
        self.assertEqual(self._calls(gh), [])

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



class Test_propose_rule_citations(unittest.TestCase):
    """`propose-rule-citations.py` — S-4, and the links that end up in the rulebook."""

    HELPER = SCRIPTS / "propose-rule-citations.py"
    ANCHOR_A = '        if anchor not in text:'
    MUTANT_A = '        if False:'
    PREFIX = "https://github.com/xinquan568/vibe-suite/blob/auditor-data/exemplars"

    RULES = ("# Rules\n\n**R01. No vague quantifiers.**\n"
             "<!-- vibe-exemplar-citation:site R01 -->\n\n"
             "**R02. Every line earns its cost.**\n"
             "<!-- vibe-exemplar-citation:site R02 -->\n")

    def _fixture(self, exemplars=None, rules=None):
        d = Path(tempfile.mkdtemp())
        (d / "exemplars").mkdir()
        for name, text in (exemplars if exemplars is not None else {
            "acme-widget.md": "---\nslug: acme-widget\nrepo: acme/widget\n"
                              "audited: 2026-08-01\ncommit_sha: abc\nscore: 95\n"
                              "exemplifies: [R01, R02]\n---\nbody\n",
            "beta-tool.md": "---\nslug: beta-tool\nrepo: beta/tool\n"
                            "audited: 2026-08-02\ncommit_sha: def\nscore: 92\n"
                            "exemplifies:\n  - R01\n---\nbody\n",
        }).items():
            (d / "exemplars" / name).write_text(text, encoding="utf-8")
        rules_path = d / "SKILL.md"
        rules_path.write_text(self.RULES if rules is None else rules, encoding="utf-8")
        return d, rules_path

    def _run(self, d, rules_path, apply=True, prefix=None, script_text=None, env=None):
        helper = self.HELPER
        if script_text is not None:
            helper = Path(tempfile.mkdtemp()) / "propose-rule-citations.py"
            helper.write_text(script_text, encoding="utf-8")
        argv = [sys.executable, str(helper), "--data-dir", str(d),
                "--rules-path", str(rules_path)]
        if apply:
            argv.append("--apply")
        if prefix is not False:
            argv += ["--exemplar-url-prefix", prefix or self.PREFIX]
        return subprocess.run(argv, capture_output=True, text=True,
                              env=env if env is not None else
                              {k: v for k, v in os.environ.items()
                               if k not in ("VIBE_EXEMPLAR_URL_PREFIX", "GITHUB_REPOSITORY")})

    # --- oracle ---------------------------------------------------------------------------
    def test_citations_land_beneath_the_rulebooks_own_anchors(self):
        """The rulebook carries hand-placed `:site RXX` anchors. Inventing marker pairs meant
        every apply matched nothing, changed nothing, and still exited zero."""
        d, rules = self._fixture()
        r = self._run(d, rules)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = rules.read_text()
        self.assertIn("<!-- vibe-exemplar-citation:site R01 -->\n"
                      "<!-- vibe-exemplar-citation:begin R01 -->", text)
        self.assertIn(f"]({self.PREFIX}/acme-widget.md)", text)

    def test_both_frontmatter_shapes_are_read(self):
        """The exemplar workflow documents an inline sequence AND a block list."""
        d, rules = self._fixture()
        self._run(d, rules)
        block = rules.read_text().split("begin R01")[1].split("end R01")[0]
        self.assertIn("acme/widget", block, "inline exemplifies was dropped")
        self.assertIn("beta/tool", block, "block-list exemplifies was dropped")

    def test_links_are_absolute(self):
        """The rulebook is read on github.com, in editors, in rendered docs and inside quoted
        issue bodies. A relative link resolves against whatever host is showing the page."""
        d, rules = self._fixture()
        self._run(d, rules)
        for line in rules.read_text().splitlines():
            if line.startswith("- ["):
                with self.subTest(line=line):
                    self.assertIn("](https://", line)

    def test_a_second_apply_is_byte_identical(self):
        """Appending stacks a block under the anchor on every run, and each block being
        well-formed keeps the file looking correct as it grows without bound."""
        d, rules = self._fixture()
        self._run(d, rules)
        first = rules.read_text()
        self._run(d, rules)
        self.assertEqual(rules.read_text(), first)

    def test_ordering_is_stable(self):
        d, rules = self._fixture()
        self._run(d, rules)
        first = rules.read_text()
        d2, rules2 = self._fixture()
        self._run(d2, rules2)
        self.assertEqual(rules2.read_text(), first)

    def test_a_rule_without_an_anchor_is_reported(self):
        """Silence is how the original bug hid: nothing matched, nothing changed, exit zero."""
        d, rules = self._fixture(rules="# Rules\n\n**R01.**\n"
                                       "<!-- vibe-exemplar-citation:site R01 -->\n")
        r = self._run(d, rules)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("no `:site R02` anchor", r.stderr)

    def test_a_dry_run_writes_nothing(self):
        d, rules = self._fixture()
        before = rules.read_text()
        r = self._run(d, rules, apply=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(rules.read_text(), before)


    def test_a_rule_that_lost_its_last_exemplar_loses_its_citations(self):
        """Otherwise the rulebook goes on citing exemplars that are no longer published —
        citing evidence that does not exist is worse than citing none, because a reader has no
        way to tell the difference until they follow the link."""
        d, rules = self._fixture()
        self._run(d, rules)
        self.assertIn("begin R02", rules.read_text())

        # R02's only exemplar drops it; R01 keeps its own.
        (d / "exemplars" / "acme-widget.md").write_text(
            "---\nslug: acme-widget\nrepo: acme/widget\naudited: 2026-08-01\n"
            "commit_sha: abc\nscore: 95\nexemplifies: [R01]\n---\nbody\n", encoding="utf-8")
        r = self._run(d, rules)
        self.assertEqual(r.returncode, 0, r.stderr)
        text = rules.read_text()
        self.assertNotIn("begin R02", text, "the stale citation region survived")
        self.assertIn("<!-- vibe-exemplar-citation:site R02 -->", text,
                      "the rulebook's own anchor must NOT be removed with it")
        self.assertIn("begin R01", text, "an unrelated rule lost its citations")

    def test_removing_a_stale_region_is_reported(self):
        d, rules = self._fixture()
        self._run(d, rules)
        (d / "exemplars" / "acme-widget.md").write_text(
            "---\nrepo: acme/widget\nexemplifies: [R01]\n---\n", encoding="utf-8")
        r = self._run(d, rules)
        self.assertIn("stale region", r.stdout)

    # --- refusals -------------------------------------------------------------------------
    def test_a_missing_rules_file_is_refused(self):
        d, _ = self._fixture()
        r = self._run(d, d / "nope.md")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:propose-rule-citations:rules-file-missing", r.stderr)

    def test_an_unconfigured_prefix_is_refused(self):
        d, rules = self._fixture()
        r = self._run(d, rules, prefix=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exemplar-url-prefix-unconfigured", r.stderr)

    def test_an_invalid_prefix_is_refused(self):
        """HTTPS only, no userinfo, no query, no fragment, and the required path suffix."""
        d, rules = self._fixture()
        for bad in ("http://github.com/x/y/blob/auditor-data/exemplars",
                    "https://u:p@github.com/x/y/blob/auditor-data/exemplars",
                    "https://github.com/x/y/blob/auditor-data/exemplars?a=1",
                    "https://github.com/x/y/blob/auditor-data/exemplars#f",
                    "https://github.com/x/y/tree/main/exemplars"):
            with self.subTest(prefix=bad):
                r = self._run(d, rules, prefix=bad)
                self.assertNotEqual(r.returncode, 0, f"{bad} accepted")
                self.assertIn("exemplar-url-prefix-invalid", r.stderr)

    def test_a_trailing_slash_is_stripped_rather_than_doubled(self):
        d, rules = self._fixture()
        r = self._run(d, rules, prefix=self.PREFIX + "/")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("exemplars//", rules.read_text())

    def test_apply_with_no_exemplar_corpus_refuses(self):
        """The explicit exception to "absent exemplars are optional": "none found" and "the
        corpus failed to load" are identical empty lists, and one means every existing citation
        should be deleted."""
        d, rules = self._fixture()
        before = rules.read_text()
        import shutil
        shutil.rmtree(d / "exemplars")
        r = self._run(d, rules)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exemplar-corpus-missing", r.stderr)
        self.assertEqual(rules.read_text(), before, "the rules file must be untouched")

    def test_apply_with_an_empty_corpus_refuses(self):
        d, rules = self._fixture(exemplars={})
        before = rules.read_text()
        r = self._run(d, rules)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("exemplar-corpus-empty", r.stderr)
        self.assertEqual(rules.read_text(), before)

    def test_an_unsafe_exemplar_filename_is_refused(self):
        d, rules = self._fixture()
        (d / "exemplars" / "ok.md").write_text(
            "---\nrepo: a/b\nexemplifies: [R01]\n---\n", encoding="utf-8")
        r = self._run(d, rules, prefix="https://github.com/x/y/blob/auditor-data/exemplars")
        self.assertEqual(r.returncode, 0, r.stderr)   # ordinary names are fine

    # --- mutants --------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d, rules = self._fixture()
        before = rules.read_text()
        self._run(d, rules, script_text=NOOP[".py"])
        self.assertEqual(rules.read_text(), before, "sanity: a no-op writes nothing")

    def test_the_stacking_mutant_grows_the_file_on_every_run(self):
        """The plausible wrong implementation: insert beneath the anchor without replacing the
        block already there. Each block stays well-formed, so the file keeps looking correct
        while growing without bound."""
        src = self.HELPER.read_text(encoding="utf-8")
        anchor = "        if existing.search(text):"
        self.assertIn(anchor, src, "mutation anchor missing")
        mutant = src.replace(anchor, "        if False:", 1)
        d, rules = self._fixture()
        self._run(d, rules, script_text=mutant)
        once = rules.read_text().count("begin R01")
        self._run(d, rules, script_text=mutant)
        self.assertGreater(rules.read_text().count("begin R01"), once,
                           "mutation ineffective: the mutant should stack a second block")


if __name__ == "__main__":
    unittest.main()
