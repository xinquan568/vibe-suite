# SPDX-License-Identifier: ISC
"""Behavioural tests for the E8.3 registry, findings and contribution helpers.

The mutation contract every class here satisfies -- behavioural oracle, interpreter-correct
no-op mutant, plausible wrong-behaviour mutant -- is stated in `auditor_helpers_support`, which
also supplies the shared primitives. Reporting helpers live in
`test_auditor_reporting_helpers.py`.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from auditor_helpers_support import NOOP, REPO, SCRIPTS, source_and_call  # noqa: E402


class Test_compute_fingerprint(unittest.TestCase):
    """`compute-fingerprint.sh` — the join key across findings, outcomes and disagreements."""

    HELPER = SCRIPTS / "compute-fingerprint.sh"
    #: sha256 of "acme/widget|a.py|nl:R1|p|12\n" — the trailing newline is part of the contract.
    FINDING = '{"file":"a.py","rule_id":"nl:R1","pattern":"p","line":12}'
    EXPECTED = "sha256:19d43dcde3c64773e"          # prefix; full value asserted below

    def _fingerprint(self, script_text, finding=None):
        r = source_and_call(
            script_text,
            f"printf '%s' '{finding or self.FINDING}' | compute_fingerprint 'acme/widget'")
        return r.returncode, r.stdout.strip()

    # --- oracle -------------------------------------------------------------------------
    def test_the_digest_is_stable_and_covers_the_trailing_newline(self):
        rc, got = self._fingerprint(self.HELPER.read_text())
        self.assertEqual(rc, 0)
        self.assertTrue(got.startswith(self.EXPECTED), f"digest drifted: {got}")
        # The newline is contractual: stripping it yields a different, equally stable-looking
        # fingerprint that would silently re-key every historical finding.
        stripped = subprocess.run(
            "printf 'acme/widget|a.py|nl:R1|p|12' | shasum -a 256 | awk '{print \"sha256:\" $1}'",
            shell=True, capture_output=True, text=True).stdout.strip()
        self.assertNotEqual(got, stripped, "the digest must cover jq's trailing newline")

    def test_absent_and_null_line_agree_but_differ_from_a_real_line(self):
        """SCHEMAS §3: an absent OR null line contributes the literal "null"."""
        _, absent = self._fingerprint(self.HELPER.read_text(), "{}")
        _, null = self._fingerprint(self.HELPER.read_text(), '{"line":null}')
        _, zero = self._fingerprint(self.HELPER.read_text(), '{"line":0}')
        self.assertEqual(absent, null, "absent and null line must agree")
        self.assertNotEqual(absent, zero, "a file-level finding must not collide with line 0")

    def test_malformed_json_fails_rather_than_hashing_nothing(self):
        """Without pipefail the status is shasum's, so bad input would hash "|||null" to a
        valid-looking fingerprint and corrupt the join key with a value no schema check
        rejects."""
        rc, _ = self._fingerprint(self.HELPER.read_text(), '{"broken"')
        self.assertNotEqual(rc, 0, "a jq parse failure must propagate")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        rc, got = self._fingerprint(NOOP[".sh"])
        self.assertFalse(rc == 0 and got.startswith(self.EXPECTED),
                         "the oracle passed against a helper that does nothing")

    def test_the_newline_stripping_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: drop the newline before hashing.

        It produces a stable, correctly-shaped `sha256:` fingerprint, so any test asserting
        only the shape would accept it. The oracle must reject it.
        """
        mutant = self.HELPER.read_text().replace(
            "| shasum -a 256 \\", "| tr -d '\\n' | shasum -a 256 \\")
        self.assertIn("tr -d", mutant, "mutation did not apply")
        rc, got = self._fingerprint(mutant)
        self.assertFalse(rc == 0 and got.startswith(self.EXPECTED),
                         "the oracle accepted a digest computed without the trailing newline")


class Test_compute_vocab_fingerprint(unittest.TestCase):
    """`compute-vocab-fingerprint.sh` — the join key for term-cluster advisories.

    NOTE ON THE SPECIFICATION: E8.3's spec states an expected digest
    (`sha256:a442478…`) for terms `["helper","agent"]`, but the formula also consumes the repo
    and disposition and the spec names neither, so that digest cannot be reproduced — it was
    not derivable from any plausible fixture. The FORMULA and its properties are what is
    testable, and this class pins a fixture of its own alongside them.
    """

    HELPER = SCRIPTS / "compute-vocab-fingerprint.sh"
    ADVISORY = '{"terms":["helper","agent"],"disposition":"advise"}'
    EXPECTED = "sha256:1b21beb282540c68448"        # acme/widget + the fixture above

    def _fp(self, script_text, advisory=None):
        r = source_and_call(
            script_text,
            f"printf '%s' '{advisory or self.ADVISORY}' | compute_vocab_fingerprint 'acme/widget'")
        return r.returncode, r.stdout.strip()

    # --- oracle -------------------------------------------------------------------------
    def test_term_order_does_not_change_the_digest(self):
        """The contract's whole point: the scanner discovers terms in walk order, so hashing
        them unsorted would give the same advisory a new fingerprint every run and the join key
        would never match itself."""
        _, a = self._fp(self.HELPER.read_text(),
                        '{"terms":["helper","agent"],"disposition":"advise"}')
        _, b = self._fp(self.HELPER.read_text(),
                        '{"terms":["agent","helper"],"disposition":"advise"}')
        self.assertEqual(a, b, "term order must not affect the fingerprint")
        self.assertTrue(a.startswith(self.EXPECTED), f"digest drifted: {a}")

    def test_membership_changes_the_digest(self):
        """A different term set IS a different advisory, not the same one drifting."""
        _, two = self._fp(self.HELPER.read_text(), '{"terms":["helper","agent"]}')
        _, three = self._fp(self.HELPER.read_text(), '{"terms":["helper","agent","skill"]}')
        self.assertNotEqual(two, three)

    def test_absent_disposition_is_the_empty_string(self):
        _, absent = self._fp(self.HELPER.read_text(), '{"terms":["a"]}')
        _, empty = self._fp(self.HELPER.read_text(), '{"terms":["a"],"disposition":""}')
        self.assertEqual(absent, empty)

    def test_malformed_json_fails(self):
        rc, _ = self._fp(self.HELPER.read_text(), '{"terms"')
        self.assertNotEqual(rc, 0)

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        rc, got = self._fp(NOOP[".sh"])
        self.assertFalse(rc == 0 and got.startswith(self.EXPECTED))

    def test_the_source_order_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: hash terms in source order.

        It yields a stable, correctly-shaped digest, so a shape-only assertion would accept it.
        Only the order-independence oracle rejects it.
        """
        mutant = self.HELPER.read_text().replace("| sort | join(\",\")", "| join(\",\")")
        self.assertNotIn("| sort |", mutant, "mutation did not apply")
        _, a = self._fp(mutant, '{"terms":["helper","agent"],"disposition":"advise"}')
        _, b = self._fp(mutant, '{"terms":["agent","helper"],"disposition":"advise"}')
        self.assertNotEqual(a, b, "the mutant should be order-SENSITIVE; mutation ineffective")


class Test_guard_protected_paths(unittest.TestCase):
    """`guard-protected-paths.sh` — refuse a pipeline run that touches core artifacts."""

    HELPER = SCRIPTS / "guard-protected-paths.sh"

    def _repo(self):
        """A throwaway git repo with a committed data file and no protected changes."""
        td = tempfile.mkdtemp()
        root = Path(td)
        subprocess.run(["git", "init", "-q", "."], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "t@e"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
        (root / "auditor").mkdir()
        (root / "auditor" / "ok.txt").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
        return root

    def _run(self, root, script_text=None):
        path = root / "guard.sh"
        path.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        return subprocess.run(["bash", str(path)], cwd=root, capture_output=True, text=True)

    # --- oracle -------------------------------------------------------------------------
    def test_an_ordinary_data_change_passes(self):
        root = self._repo()
        (root / "auditor" / "ok.txt").write_text("x\ny\n", encoding="utf-8")
        self.assertEqual(self._run(root).returncode, 0)

    def test_every_protected_class_is_blocked_and_named(self):
        for rel in ("skills/x/SKILL.md", "agents/a.md", "commands/c.md", "hooks/h.json",
                    "CLAUDE.md", "README.md", ".claude-plugin/plugin.json"):
            with self.subTest(path=rel):
                root = self._repo()
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("x\n", encoding="utf-8")
                r = self._run(root)
                self.assertEqual(r.returncode, 1, f"{rel} was not blocked")
                self.assertIn("VIOLATION", r.stdout)
                self.assertIn(rel.split("/")[0], r.stdout, "the offending path must be named")

    def test_staged_unstaged_and_untracked_are_all_seen(self):
        """The untracked case is the one a diff-only guard misses entirely."""
        # untracked
        root = self._repo()
        (root / "skills").mkdir()
        (root / "skills" / "s.md").write_text("x\n", encoding="utf-8")
        self.assertEqual(self._run(root).returncode, 1, "untracked not blocked")
        # staged
        subprocess.run(["git", "add", "skills/s.md"], cwd=root, check=True)
        self.assertEqual(self._run(root).returncode, 1, "staged not blocked")
        # unstaged modification of a tracked protected file
        root2 = self._repo()
        (root2 / "README.md").write_text("a\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=root2, check=True)
        subprocess.run(["git", "commit", "-qm", "add readme"], cwd=root2, check=True)
        (root2 / "README.md").write_text("a\nb\n", encoding="utf-8")
        self.assertEqual(self._run(root2).returncode, 1, "unstaged not blocked")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        root = self._repo()
        (root / "skills").mkdir()
        (root / "skills" / "s.md").write_text("x\n", encoding="utf-8")
        self.assertNotEqual(self._run(root, NOOP[".sh"]).returncode, 1,
                            "sanity: a no-op cannot block")
        # the oracle above requires 1; a no-op returns 0, so the oracle rejects it
        self.assertEqual(self._run(root, NOOP[".sh"]).returncode, 0)

    def test_the_diff_only_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: inspect only `git diff`, skipping untracked.

        It blocks staged and unstaged edits, so a test that only covers those would pass it —
        while a workflow could create entirely new protected content unseen.
        """
        mutant = self.HELPER.read_text().replace(
            'untracked="$(git ls-files --others --exclude-standard -- "$path" 2>/dev/null)"',
            'untracked=""')
        self.assertIn('untracked=""', mutant, "mutation did not apply")
        root = self._repo()
        (root / "skills").mkdir()
        (root / "skills" / "s.md").write_text("x\n", encoding="utf-8")
        self.assertEqual(self._run(root, mutant).returncode, 0,
                         "mutation ineffective: the diff-only guard should miss this")
        # and the real helper must catch what the mutant misses
        self.assertEqual(self._run(root).returncode, 1)


class Test_parse_pr_metadata(unittest.TestCase):
    """`parse-pr-metadata.py` — carry findings' fingerprints from a PR body to the registry."""

    HELPER = SCRIPTS / "parse-pr-metadata.py"
    BLOCK = ('<!-- vibe-suite-auditor-meta-begin {{"findings":[{{"fingerprint":"{fp}"}}]}} '
             'vibe-suite-auditor-meta-end -->')

    def _run(self, body, script_text=None):
        if script_text is None:
            argv = [sys.executable, str(self.HELPER)]
            return subprocess.run(argv, input=body, capture_output=True, text=True)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "helper.py"
            path.write_text(script_text, encoding="utf-8")
            return subprocess.run([sys.executable, str(path)], input=body,
                                  capture_output=True, text=True)

    # --- oracle -------------------------------------------------------------------------
    def test_no_block_is_empty_and_succeeds(self):
        r = self._run("a PR body with no metadata at all\n")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout), {})

    def test_the_tail_most_block_wins(self):
        """A PR body is editable, so the LAST block is the current one.

        Taking the first is what a non-greedy regex does by default and would pin attribution
        to a superseded edit forever.
        """
        body = f"intro\n{self.BLOCK.format(fp='first')}\nmid\n{self.BLOCK.format(fp='second')}\n"
        r = self._run(body)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(json.loads(r.stdout)["findings"][0]["fingerprint"], "second")

    def test_a_malformed_payload_warns_and_fails_but_still_prints_empty(self):
        r = self._run("<!-- vibe-suite-auditor-meta-begin {nope} vibe-suite-auditor-meta-end -->")
        self.assertEqual(r.returncode, 1, "a corrupted block must surface, not vanish")
        self.assertIn("WARN", r.stderr)
        self.assertEqual(json.loads(r.stdout), {}, "stdout stays {} so callers need no case")

    def test_it_agrees_with_the_workflow_jq_that_reads_the_same_block(self):
        """auditor-track.yml parses this block with jq `"g"` + `| last`.

        Two implementations of one contract must agree; a divergence would split finding
        attribution between the workflow and the helper, silently.
        """
        body = f"a\n{self.BLOCK.format(fp='first')}\nb\n{self.BLOCK.format(fp='second')}\nc\n"
        mine = json.loads(self._run(body).stdout)["findings"][0]["fingerprint"]

        # Extract the regex FROM auditor-track.yml rather than restating it. A copy here could
        # drift from the workflow and the test would then be comparing the helper against a
        # regex nobody runs — which is precisely the failure this test exists to prevent.
        track = (REPO / "auditor" / "workflows" / "auditor-track.yml").read_text()
        m = re.search(r'match\("(<!--.*?vibe-suite-auditor-meta-end[^"]*)"; "g"\)', track)
        self.assertIsNotNone(m, "auditor-track.yml no longer contains the metadata regex")
        pattern = m.group(1)

        jq = subprocess.run(
            ["jq", "-R", "-s", "-r",
             f'[match("{pattern}"; "g")] | last | .captures[0].string '
             f'| fromjson | .findings[0].fingerprint'],
            input=body, capture_output=True, text=True)
        self.assertEqual(jq.returncode, 0, jq.stderr)
        self.assertEqual(mine, jq.stdout.strip(), "helper and workflow jq disagree")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        r = self._run("x", NOOP[".py"])
        self.assertNotEqual(r.stdout.strip(), "{}", "sanity: a no-op prints nothing")

    def test_the_first_block_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: return the FIRST match.

        It produces well-formed JSON from a real block, so any test with a single block in its
        fixture would accept it.
        """
        mutant = self.HELPER.read_text().replace("raw = matches[-1]", "raw = matches[0]")
        self.assertIn("matches[0]", mutant, "mutation did not apply")
        body = f"a\n{self.BLOCK.format(fp='first')}\nb\n{self.BLOCK.format(fp='second')}\n"
        got = json.loads(self._run(body, mutant).stdout)["findings"][0]["fingerprint"]
        self.assertEqual(got, "first", "mutation ineffective")
        self.assertNotEqual(got, "second", "the oracle must reject first-block behaviour")


class Test_parse_suppressions(unittest.TestCase):
    """`parse-suppressions.py` — emit configured rule overrides as JSONL.

    The reference implementation imports PyYAML and, on ImportError, prints a note and exits 0,
    silently disabling every suppression. PyYAML is not installed here and this repo ships
    stdlib only, so that path would be the permanent one. This helper parses the frontmatter
    subset directly; `test_it_does_not_depend_on_pyyaml` holds it to that.
    """

    HELPER = SCRIPTS / "parse-suppressions.py"
    CONFIG = (
        "---\n"
        "name: example\n"
        "rule_overrides:\n"
        "  nl:R1: false\n"
        "  nl:R2:\n"
        "    max_penalty: 5\n"
        "    threshold: 0.8\n"
        "  nl:R3: 3\n"
        "other: keep\n"
        "---\n"
        "body\n"
    )

    def _run(self, config_text=None, script_text=None, path=None):
        td = tempfile.mkdtemp()
        cfg = Path(td) / "cfg.md"
        if config_text is not None:
            cfg.write_text(config_text, encoding="utf-8")
        helper = Path(td) / "helper.py"
        helper.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        return subprocess.run([sys.executable, str(helper), str(path or cfg)],
                              capture_output=True, text=True)

    def _rows(self, r):
        return {json.loads(ln)["rule_id"]: json.loads(ln)["override"]
                for ln in r.stdout.splitlines() if ln.strip()}

    # --- oracle -------------------------------------------------------------------------
    def test_types_are_preserved_not_stringified(self):
        """`false` must arrive as a JSON boolean and a nested mapping as an object.

        Stringifying either produces well-formed JSONL that every downstream comparison then
        gets wrong — `"false"` is truthy, and `"{'max_penalty': 5}"` has no fields.
        """
        rows = self._rows(self._run(self.CONFIG))
        self.assertIs(rows["nl:R1"], False, "boolean was stringified")
        self.assertEqual(rows["nl:R2"], {"max_penalty": 5, "threshold": 0.8})
        self.assertIsInstance(rows["nl:R2"]["max_penalty"], int)
        self.assertIsInstance(rows["nl:R2"]["threshold"], float)
        self.assertEqual(rows["nl:R3"], 3)
        self.assertNotIn("other", rows, "only rule_overrides is emitted")

    def test_an_absent_config_is_a_silent_success(self):
        r = self._run(None, path="/nonexistent/cfg.md")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "")

    def test_no_frontmatter_and_no_overrides_are_both_empty(self):
        for text in ("just a body\n", "---\nname: x\n---\nbody\n"):
            with self.subTest(config=text[:20]):
                r = self._run(text)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(r.stdout.strip(), "")

    def test_malformed_frontmatter_fails_rather_than_reading_as_empty(self):
        r = self._run("---\nrule_overrides:\n  @@@bad\n---\n")
        self.assertEqual(r.returncode, 1, "a broken config must surface")
        self.assertIn("malformed", r.stderr)

    def test_it_does_not_depend_on_pyyaml(self):
        self.assertNotIn("import yaml", self.HELPER.read_text(),
                         "suppressions must not silently disable when PyYAML is absent")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        rows = self._rows(self._run(self.CONFIG, NOOP[".py"]))
        self.assertEqual(rows, {}, "sanity: a no-op emits nothing")

    def test_the_stringifying_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: emit every value as a string.

        It produces valid JSONL with the right rule ids, so a test checking only shape or
        rule-id coverage would accept it.
        """
        mutant = self.HELPER.read_text().replace(
            '{"rule_id": str(rule), "override": override}',
            '{"rule_id": str(rule), "override": str(override)}')
        self.assertIn('"override": str(override)', mutant, "mutation did not apply")
        rows = self._rows(self._run(self.CONFIG, mutant))
        self.assertEqual(rows["nl:R1"], "False", "mutation ineffective")
        self.assertIsNot(rows["nl:R1"], False, "the oracle must reject stringified values")


class Test_vendor_default_filter(unittest.TestCase):
    """`vendor_default_filter.py` — drop candidates no PR can ever land against."""

    HELPER = SCRIPTS / "vendor_default_filter.py"
    RECORDS = [
        '{"fullName":"Anthropics/claude-code"}',   # mixed case, deny owner
        '{"fullName":"OpenAI/Codex"}',             # mixed case, deny repo
        '{"repo_name":"GOOGLE/some-repo"}',        # upper case, CLA owner, other key
        '{"fullName":"acme/widget"}',              # ordinary
        '{"weird":"shape"}',                       # unrecognised shape
        '{"fullName":"beta/gadget"}',              # ordinary, order matters
    ]

    def _run(self, script_text=None, records=None):
        with tempfile.TemporaryDirectory() as td:
            helper = Path(td) / "helper.py"
            helper.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
            return subprocess.run([sys.executable, str(helper)],
                                  input="\n".join(records or self.RECORDS) + "\n",
                                  capture_output=True, text=True)

    def _kept(self, r):
        return [json.loads(ln) for ln in r.stdout.splitlines() if ln.strip()]

    # --- oracle -------------------------------------------------------------------------
    def test_mixed_case_denies_are_dropped_with_reasons(self):
        """GitHub owners are case-insensitive, so `Anthropics/x` IS `anthropics/x`."""
        r = self._run()
        kept = self._kept(r)
        names = [k.get("fullName") or k.get("repo_name") for k in kept]
        self.assertNotIn("Anthropics/claude-code", names, "deny owner not dropped")
        self.assertNotIn("OpenAI/Codex", names, "deny repo not dropped")
        self.assertNotIn("GOOGLE/some-repo", names, "CLA owner not dropped")
        self.assertIn("deny:anthropics", r.stderr)
        self.assertIn("deny-repo:openai/codex", r.stderr)
        self.assertIn("cla-required:google", r.stderr)

    def test_ordinary_records_pass_through_in_order(self):
        kept = self._kept(self._run())
        names = [k.get("fullName") for k in kept if k.get("fullName")]
        self.assertEqual(names, ["acme/widget", "beta/gadget"], "order must be preserved")

    def test_an_unrecognised_shape_passes_through(self):
        """Dropping unknown shapes would make a schema change look like an empty run —
        the pipeline going quiet rather than failing."""
        kept = self._kept(self._run())
        self.assertIn({"weird": "shape"}, kept)

    def test_a_bare_name_without_a_slash_is_kept(self):
        kept = self._kept(self._run(records=['{"fullName":"anthropics"}']))
        self.assertEqual(len(kept), 1, "a name with no owner/ is not a repo reference")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        self.assertEqual(self._kept(self._run(NOOP[".py"])), [], "sanity: a no-op emits nothing")

    def test_the_case_sensitive_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: compare owners as written.

        It still drops every lowercase fixture, so a test using only lowercase names would
        accept it — while the identical repo spelled `Anthropics/` sails through.
        """
        mutant = self.HELPER.read_text().replace("lowered = repo.lower()", "lowered = repo")
        self.assertIn("lowered = repo\n", mutant, "mutation did not apply")
        names = [k.get("fullName") or k.get("repo_name") for k in self._kept(self._run(mutant))]
        self.assertIn("Anthropics/claude-code", names, "mutation ineffective")

    def test_the_drop_unknown_shape_mutant_fails_the_oracle(self):
        """The other plausible error: drop records whose repo key is unrecognised."""
        mutant = self.HELPER.read_text().replace(
            "            kept.append(record)          # unknown shape: pass through, never silently drop\n            continue",
            "            continue")
        self.assertNotIn("unknown shape: pass through", mutant, "mutation did not apply")
        kept = self._kept(self._run(mutant))
        self.assertNotIn({"weird": "shape"}, kept, "mutation ineffective")



class Test_docs_diff(unittest.TestCase):
    """`docs-diff.py` — detect when a cited external doc has drifted."""

    HELPER = SCRIPTS / "docs-diff.py"
    FAIL_ANCHOR = 'counts["fetch_failed"] += 1\n            continue'
    FAIL_MUTANT = 'counts["fetch_failed"] += 1\n            body = ""'

    def _module(self, script_text=None):
        import importlib.util
        path = Path(tempfile.mkdtemp()) / "docs_diff.py"
        path.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        spec = importlib.util.spec_from_file_location("docs_diff_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    @staticmethod
    def _opener(bodies, fail):
        class Resp:
            def __init__(self, b):
                self.b = b.encode()

            def read(self):
                return self.b

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(request, timeout=None):
            url = request.full_url
            if url in fail:
                raise OSError("network down")
            return Resp(bodies[url])

        return opener

    def _fixture(self, mod):
        import hashlib
        steady = hashlib.sha256(b"steady").hexdigest()
        d = Path(tempfile.mkdtemp())
        (d / "ledgers").mkdir()
        (d / "ledgers" / "docs-citations.json").write_text(json.dumps(
            {"_meta": "skipped", "http://new": {}, "http://drift": {},
              "http://same": {}, "http://down": {}}), encoding="utf-8")
        (d / "ledgers" / "docs-hashes.json").write_text(json.dumps({
            "http://drift": {"hash": "stale-digest", "last_seen": "x"},
            "http://same": {"hash": steady, "last_seen": "x"},
            "http://down": {"hash": "must-survive", "last_seen": "x"}}), encoding="utf-8")
        opener = self._opener(
            {"http://new": "fresh", "http://drift": "moved", "http://same": "steady"},
            fail={"http://down"})
        counts = mod.run(d / "ledgers" / "docs-citations.json",
                         d / "ledgers" / "docs-hashes.json",
                         d / "ledgers" / "changed.txt", opener)
        return d, counts

    # --- oracle -------------------------------------------------------------------------
    def test_the_four_states_are_distinguished(self):
        d, counts = self._fixture(self._module())
        self.assertEqual(counts, {"bootstrapped": 1, "changed": 1,
                                   "unchanged": 1, "fetch_failed": 1})
        self.assertEqual((d / "ledgers" / "changed.txt").read_text().split(), ["http://drift"],
                         "only the drifted URL is listed")

    def test_a_failed_fetch_leaves_its_stored_hash_untouched(self):
        """Recording a failure as drift raises a false alarm on every network blip; recording
        it as a NEW hash is worse — it adopts unreachable as the baseline, so the real change
        is never detected afterwards."""
        d, _ = self._fixture(self._module())
        after = json.loads((d / "ledgers" / "docs-hashes.json").read_text())
        self.assertEqual(after["http://down"]["hash"], "must-survive")
        self.assertNotIn("http://down", (d / "ledgers" / "changed.txt").read_text())

    def test_metadata_keys_are_not_fetched(self):
        _, counts = self._fixture(self._module())
        self.assertEqual(sum(counts.values()), 4, "the _meta key must not be treated as a URL")

    def test_the_hash_store_is_written_atomically(self):
        d, _ = self._fixture(self._module())
        leftovers = [x.name for x in (d / "ledgers").iterdir() if x.name.startswith(".")]
        self.assertEqual(leftovers, [], f"temp files left behind: {leftovers}")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        """The Python no-op raises SystemExit at import, so it can never provide `run`.

        Asserted rather than assumed: if a future no-op form imported cleanly, the mutation
        would silently stop proving anything for every Python helper.
        """
        with self.assertRaises(SystemExit):
            self._module(NOOP[".py"])

    def test_the_overwrite_on_failure_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: treat a failed fetch as an empty body.

        It yields a valid-looking summary and a well-formed hash store, so a test checking only
        counts or file shape would accept it — while every unreachable doc silently re-baselines
        to the hash of nothing.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.FAIL_ANCHOR, src, "mutation anchor missing")
        mod = self._module(src.replace(self.FAIL_ANCHOR, self.FAIL_MUTANT))
        d, _ = self._fixture(mod)
        after = json.loads((d / "ledgers" / "docs-hashes.json").read_text())
        self.assertNotEqual(after["http://down"]["hash"], "must-survive",
                            "mutation ineffective")



class Test_commit_via_pr(unittest.TestCase):
    """`commit-via-pr.sh` — publish an already-committed data change as a PR.

    The workflow commits and this helper publishes; that split differs from the reference
    implementation deliberately, because auditor-track's registry rewrites race the other
    stages and so track composes its own commit rather than pushing at the data branch.

    Everything below the network boundary is exercised here. Whether GitHub accepts the push
    and the PR is E8.7's live matrix, and this class does not claim it.
    """

    HELPER = SCRIPTS / "commit-via-pr.sh"

    def _repo(self, origin="https://github.com/acme/widget"):
        d = Path(tempfile.mkdtemp()) / "work"
        d.mkdir()
        run = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True,
                                        capture_output=True)
        run("init", "-q", ".")
        run("config", "user.email", "t@e")
        run("config", "user.name", "t")
        (d / "registry").mkdir()
        (d / "registry" / "repos.json").write_text("{}\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        if origin:
            run("remote", "add", "origin", origin)
        # Make every network operation fail IMMEDIATELY. These tests exercise the helper below
        # the network boundary; without this they reach `git ls-remote https://github.com/...`
        # and hang until the transport times out — in CI as well as locally. An unroutable
        # proxy is refused on connect, so `remote-unreachable` arrives in milliseconds and the
        # tests stay hermetic.
        run("config", "http.proxy", "http://127.0.0.1:1")
        return d


    def _remote_sandbox(self):
        """A checkout whose network operations reach a local bare repo, with `origin` still
        recorded as the canonical GitHub URL.

        The reviewer's construction, and it is better than the two I abandoned. insteadOf fails
        because `git remote get-url` APPLIES it, so the identity check sees a file:// URL and
        refuses. Here `origin` is never rewritten in config — a shim replaces the literal
        `origin` OPERAND of ls-remote, fetch and push only, so identity verification passes
        unchanged and the base comparison is actually reached.
        """
        base = Path(tempfile.mkdtemp())
        bare = base / "remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True,
                       capture_output=True)
        subprocess.run(["git", "-C", str(bare), "symbolic-ref", "HEAD",
                        "refs/heads/auditor-data"], check=True, capture_output=True)
        d = base / "work"
        d.mkdir()
        run = lambda *a: subprocess.run(["git", "-C", str(d), *a], check=True,
                                        capture_output=True)
        run("init", "-q", ".")
        run("config", "user.email", "t@e")
        run("config", "user.name", "t")
        run("checkout", "-q", "-B", "auditor-data")
        (d / "registry").mkdir()
        (d / "registry" / "repos.json").write_text("{}\n", encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "base")
        run("remote", "add", "origin", "https://github.com/acme/widget")

        real_git = subprocess.run(["which", "git"], capture_output=True,
                                  text=True).stdout.strip()
        shims = base / "bin"
        shims.mkdir()
        (shims / "git").write_text(
            "#!/usr/bin/env python3\n"
            "import os, sys\n"
            f"BARE = {str(bare)!r}\n"
            f"REAL = {real_git!r}\n"
            "argv = sys.argv[1:]\n"
            "net = {'ls-remote', 'fetch', 'push'}\n"
            "if any(a in net for a in argv):\n"
            "    argv = [BARE if a == 'origin' else a for a in argv]\n"
            "os.execv(REAL, [REAL] + argv)\n", encoding="utf-8")
        (shims / "git").chmod(0o755)
        (shims / "gh").write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  *'pr list'*) echo 'https://github.com/acme/widget/pull/1' ;;\n"
            "  *'pr merge'*) : ;;\n"
            "  *) : ;;\n"
            "esac\n"
            "exit 0\n", encoding="utf-8")
        (shims / "gh").chmod(0o755)

        # publish the base, then commit ahead of it — the normal state this helper publishes
        subprocess.run(["git", "-C", str(d), "push", "-q", str(bare), "auditor-data"],
                       check=True, capture_output=True)
        (d / "registry" / "repos.json").write_text('{"repos": {}}\n', encoding="utf-8")
        run("add", "-A")
        run("commit", "-qm", "update")
        return d, {"PATH": f"{shims}:{os.environ['PATH']}",
                   "HOME": os.environ.get("HOME", "/tmp"), "PAT_TOKEN": "t"}

    def _run(self, checkout, script_text=None, env=None, **kw):
        args = {"--checkout": str(checkout), "--repo": "acme/widget",
                "--base": "auditor-data", "--branch": "auditor-track-1"}
        args.update(kw)
        # Drop the whole PAIR when a value is None. Filtering only the value left the
        # bare flag behind, so `--checkout` swallowed the next flag as its value and the
        # helper ran on garbage — which then reached the network and hung.
        argv = [x for k, v in args.items() if v is not None for x in (k, v)]
        path = Path(tempfile.mkdtemp()) / "helper.sh"
        path.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        environ = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/tmp"),
                   "PAT_TOKEN": "tok"}
        if env is not None:
            environ.update(env)
        return subprocess.run(["bash", str(path), *argv], capture_output=True, text=True,
                              env=environ)

    def _reason(self, result):
        for line in result.stderr.splitlines():
            if line.startswith("REFUSE:commit-via-pr:"):
                return line.split(":", 2)[2]
        return None

    # --- oracle -------------------------------------------------------------------------
    def test_every_missing_argument_is_named(self):
        d = self._repo()
        for drop, reason in (("--checkout", "checkout-required"), ("--repo", "repo-required"),
                             ("--base", "base-required"), ("--branch", "branch-required")):
            with self.subTest(missing=drop):
                kw = {drop: None}
                r = self._run(d, **kw)
                self.assertEqual(self._reason(r), reason)

    def test_repository_identity_is_verified_across_url_forms(self):
        """Pushing to the wrong repository is not a recoverable mistake."""
        for url in ("https://github.com/acme/widget.git", "https://github.com/acme/widget",
                    "git@github.com:acme/widget.git", "ssh://git@github.com/acme/widget.git",
                    "https://github.com/ACME/Widget"):
            with self.subTest(origin=url):
                r = self._run(self._repo(url))
                self.assertNotIn(self._reason(r), ("origin-unverifiable", "repository-mismatch"),
                                 f"{url} should verify against acme/widget")

    def test_a_different_origin_is_refused(self):
        r = self._run(self._repo("https://github.com/evil/other"))
        self.assertEqual(self._reason(r), "repository-mismatch")

    def test_a_disagreeing_github_repository_is_refused(self):
        r = self._run(self._repo(), env={"GITHUB_REPOSITORY": "other/repo"})
        self.assertEqual(self._reason(r), "repository-mismatch")

    def test_an_unparseable_origin_is_refused_not_assumed(self):
        r = self._run(self._repo("/some/local/path"))
        self.assertEqual(self._reason(r), "origin-unverifiable")

    def test_a_missing_token_is_refused_and_gh_token_warns(self):
        d = self._repo()
        r = self._run(d, env={"PAT_TOKEN": "", "GH_TOKEN": ""})
        self.assertEqual(self._reason(r), "token-missing")
        r = self._run(d, env={"PAT_TOKEN": "", "GH_TOKEN": "fallback"})
        self.assertIn("WARN:commit-via-pr:using-GH_TOKEN", r.stderr,
                      "a GITHUB_TOKEN-created PR does not trigger downstream workflows")

    def test_a_dirty_tree_is_refused_in_all_three_shapes(self):
        for make, reason in (
            (lambda d: (d / "registry" / "new.json").write_text("x", encoding="utf-8"),
             "untracked-files"),
            (lambda d: (d / "registry" / "repos.json").write_text("changed", encoding="utf-8"),
             "unstaged-changes"),
        ):
            with self.subTest(reason=reason):
                d = self._repo()
                make(d)
                self.assertEqual(self._reason(self._run(d)), reason)

    def test_branch_equal_to_base_is_refused(self):
        r = self._run(self._repo(), **{"--branch": "auditor-data"})
        self.assertEqual(self._reason(r), "branch-equals-base")

    def test_a_non_worktree_checkout_is_refused(self):
        r = self._run(Path(tempfile.mkdtemp()))
        self.assertEqual(self._reason(r), "not-a-git-worktree")


    def test_the_token_reaches_git_and_not_only_gh(self):
        """It was exported as GH_TOKEN alone, so fetch and push ran unauthenticated — and the
        workflows check out with `persist-credentials: false`, so nothing ambient covers for
        it. The push fails, the branch never appears, and the PR carrying the data is never
        opened."""
        src = self.HELPER.read_text()
        for op in ("fetch --no-tags origin", "push origin", "ls-remote --heads origin"):
            with self.subTest(op=op):
                self.assertIn(f"git_auth {op}", src,
                              f"`{op}` bypasses the authenticated wrapper")

    def test_the_token_never_reaches_argv_or_config(self):
        """S-1: ephemeral only. In argv it is visible in `ps`; written to config or a remote
        URL it outlives the run in a checkout the auditor commits from."""
        src = self.HELPER.read_text()
        self.assertIn('GIT_AUTH_TOKEN="$TOKEN" git', src,
                      "the token must be passed through the environment")
        self.assertIn("${GIT_AUTH_TOKEN}", src,
                      "the helper must expand the token itself, not the shell")
        self.assertNotIn('extraheader', src, "no header form: it puts the secret in argv")
        for forbidden in ('config credential', 'remote set-url', '@github.com'):
            with self.subTest(pattern=forbidden):
                self.assertNotIn(forbidden, src)

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        r = self._run(self._repo(), NOOP[".sh"])
        self.assertIsNone(self._reason(r), "sanity: a no-op refuses nothing")
        self.assertEqual(r.returncode, 0)

    def test_the_local_branch_base_mutant_fails_the_oracle(self):
        """The mutant the specification named: compare HEAD against the LOCAL base branch.

        After committing on a checked-out auditor-data, local HEAD IS the tip of local
        auditor-data — so this rejects every normal post-commit call as nothing-to-publish.
        It looks right and blocks the helper's entire purpose.
        """
        src = self.HELPER.read_text()
        anchor = 'refs/remotes/origin/$BASE^{commit}'
        self.assertIn(anchor, src, "mutation anchor missing")
        mutant = src.replace(anchor, 'refs/heads/$BASE^{commit}')
        self.assertNotEqual(mutant, src, "mutation anchor did not match")

        # THE MUTANT IS RUN AND KILLED. Two earlier attempts failed and I concluded no
        # hermetic demonstration existed; the reviewer showed one, and they were right.
        #
        # The real helper publishes: HEAD is ahead of the fetched remote base. The mutant
        # compares against the LOCAL branch, which after a commit on a checked-out
        # auditor-data IS HEAD — so it refuses a perfectly normal call as nothing-to-publish.
        d, env = self._remote_sandbox()
        real = self._run(d, env=env)
        mutated = self._run(d, mutant, env=env)

        self.assertEqual(self._reason(mutated), "nothing-to-publish",
                         "mutation ineffective: the mutant should reject a normal call")
        # Assert publication SUCCEEDED, not merely that it failed differently. "not this
        # refusal" is satisfied by any other refusal, which would leave the real side of the
        # comparison unverified.
        self.assertEqual(real.returncode, 0, real.stderr)
        self.assertIn("PR_URL=", real.stdout,
                      "the real helper must publish and report the PR")


class Test_atomic_registry_write(unittest.TestCase):
    """`atomic-registry-write.sh` — validate a staged registry write, then land it atomically.

    The registry is the join key for every finding, PR outcome and disagreement the pipeline
    has recorded, so the ordering is the contract: VALIDATE FIRST, THEN WRITE. A helper that
    copies to the destination and validates afterwards has already destroyed the good registry
    by the time it notices.
    """

    HELPER = SCRIPTS / "atomic-registry-write.sh"
    ORIGINAL = '{"repos":{"acme/widget":{"state":"audited"}}}'
    VALIDATE_ANCHOR = 'if ! python3 -c \'import json,sys; json.load(open(sys.argv[1]))\' "$REG_TMP" >/dev/null 2>&1; then'

    def _tree(self):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "registry" / "repos.json").write_text(self.ORIGINAL, encoding="utf-8")
        return d

    def _run(self, d, staged, script_text=None):
        stage = d / "stage.json"
        if staged is not None:
            stage.write_text(staged, encoding="utf-8")
        path = Path(tempfile.mkdtemp()) / "helper.sh"
        path.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        env = dict(os.environ)
        env["REG_TMP"] = str(stage)
        return subprocess.run(["bash", str(path), "--data-dir", str(d)],
                              capture_output=True, text=True, env=env)

    @staticmethod
    def _digest(path):
        import hashlib
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    # --- oracle -------------------------------------------------------------------------
    def test_a_valid_staged_write_lands_and_consumes_the_source(self):
        d = self._tree()
        nxt = '{"repos":{"acme/widget":{"state":"contributed"}}}'
        r = self._run(d, nxt)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads((d / "registry" / "repos.json").read_text()),
                         json.loads(nxt))
        self.assertFalse((d / "stage.json").exists(),
                         "the staging file must be consumed so a stale one cannot be re-landed")

    def test_invalid_staged_json_preserves_the_original_BYTES(self):
        d = self._tree()
        before = self._digest(d / "registry" / "repos.json")
        r = self._run(d, '{"repos": broken')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("staged-not-json", r.stderr)
        self.assertEqual(self._digest(d / "registry" / "repos.json"), before,
                         "the registry must be byte-identical after a refused write")

    def test_a_refused_write_leaves_no_temp_files_behind(self):
        d = self._tree()
        self._run(d, '{"repos": broken')
        strays = [p.name for p in (d / "registry").iterdir() if p.name.startswith(".")]
        self.assertEqual(strays, [], f"temp files left behind: {strays}")

    def test_nothing_staged_is_refused(self):
        r = self._run(self._tree(), None)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nothing-staged", r.stderr)


    def test_source_pointing_at_the_destination_is_refused(self):
        """Round-2 regression, introduced by the fix for round 1's registry-missing finding.

        The helper consumes the source once the rename lands, so `--source <the registry>`
        deleted the registry it had just "written" — exit 0, no diagnostic, file gone. Reported
        as a successful atomic write, which is the worst possible way to lose the file every
        other stage reads.
        """
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        registry = d / "registry" / "repos.json"
        registry.write_text('{"repos": {"a/b": {"status": "audited"}}}\n', encoding="utf-8")
        r = subprocess.run(["bash", str(self.HELPER), "--data-dir", str(d),
                            "--source", str(registry)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:atomic-registry-write:source-is-destination", r.stderr)
        self.assertTrue(registry.is_file(), "the registry was deleted")

    def test_the_same_file_reached_by_a_relative_path_is_also_refused(self):
        """Compared by resolved path: a string comparison misses `--source repos.json` run from
        inside the registry directory, which is the same inode."""
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        registry = d / "registry" / "repos.json"
        registry.write_text('{"repos": {}}\n', encoding="utf-8")
        r = subprocess.run(["bash", str(self.HELPER), "--data-dir", str(d),
                            "--source", "repos.json"], capture_output=True, text=True,
                           cwd=str(d / "registry"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("source-is-destination", r.stderr)
        self.assertTrue(registry.is_file(), "the registry was deleted")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d = self._tree()
        nxt = '{"repos":{"acme/widget":{"state":"contributed"}}}'
        self._run(d, nxt, NOOP[".sh"])
        self.assertEqual(json.loads((d / "registry" / "repos.json").read_text()),
                         json.loads(self.ORIGINAL), "sanity: a no-op writes nothing")

    def test_the_validate_after_write_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: copy first, validate afterwards.

        It behaves identically on every VALID input — which is most inputs — so a test that
        only exercises the happy path would accept it. On malformed input it has already
        destroyed the registry before it notices.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.VALIDATE_ANCHOR, src, "mutation anchor missing")
        mutant = src.replace(
            self.VALIDATE_ANCHOR,
            'cp "$REG_TMP" "$REG_DEST"\n' + self.VALIDATE_ANCHOR, 1)
        d = self._tree()
        before = self._digest(d / "registry" / "repos.json")
        self._run(d, '{"repos": broken', mutant)
        self.assertNotEqual(self._digest(d / "registry" / "repos.json"), before,
                            "mutation ineffective: the mutant should have clobbered the registry")



class Test_three_way_merge_registry(unittest.TestCase):
    """`three-way-merge-registry.py` — resolve a registry push race without losing updates.

    The bug this replaces is subtle and was observed in production: deep-merging OURS over
    THEIRS reverts every field this run did not touch, because OURS still holds the value read
    at checkout. Entries then oscillate between states run after run while nothing looks broken.
    """

    HELPER = SCRIPTS / "three-way-merge-registry.py"
    MERGE_ANCHOR = "    if theirs_changed and not ours_changed:\n        return theirs          # remote moved, our copy is stale\n    return ours                # we moved, or both did: this run's intent"
    MERGE_MUTANT = '    return ours                # MUTANT: ours always wins'

    BASE = {"repos": {"a/x": {"state": "discovered", "score": 1},
                        "b/y": {"state": "discovered"}}}
    OURS = {"repos": {"a/x": {"state": "audited", "score": 1},
                        "b/y": {"state": "discovered"}}}
    THEIRS = {"repos": {"a/x": {"state": "discovered", "score": 1},
                          "b/y": {"state": "contributed"},
                          "c/z": {"state": "new"}}}

    def _run(self, script_text=None, base=None, ours=None, theirs=None):
        d = Path(tempfile.mkdtemp())
        # `is None`, NOT `or`: an empty registry `{}` is falsy, so `base or self.BASE`
        # silently substituted the default fixture and the empty-input case never ran.
        for name, doc in (("base", self.BASE if base is None else base),
                          ("ours", self.OURS if ours is None else ours),
                          ("theirs", self.THEIRS if theirs is None else theirs)):
            (d / f"{name}.json").write_text(
                doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
        helper = d / "helper.py"
        helper.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(helper), str(d / "base.json"), str(d / "ours.json"),
             str(d / "theirs.json")], capture_output=True, text=True)

    # --- oracle -------------------------------------------------------------------------
    def test_disjoint_changes_from_both_sides_survive(self):
        """The acceptance property: neither side's work is lost."""
        r = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        repos = json.loads(r.stdout)["repos"]
        self.assertEqual(repos["a/x"]["state"], "audited", "our change was lost")
        self.assertEqual(repos["b/y"]["state"], "contributed",
                         "the remote's change was REVERTED by our stale copy")
        self.assertEqual(repos["c/z"]["state"], "new", "a remote-only addition was dropped")

    def test_when_both_sides_change_a_field_ours_wins_deterministically(self):
        ours = {"repos": {"a/x": {"state": "audited"}}}
        theirs = {"repos": {"a/x": {"state": "contributed"}}}
        base = {"repos": {"a/x": {"state": "discovered"}}}
        first = self._run(base=base, ours=ours, theirs=theirs).stdout
        second = self._run(base=base, ours=ours, theirs=theirs).stdout
        self.assertEqual(json.loads(first)["repos"]["a/x"]["state"], "audited")
        self.assertEqual(first, second, "resolution must be deterministic")

    def test_output_is_byte_stable_so_concurrent_resolutions_agree(self):
        self.assertEqual(self._run().stdout, self._run().stdout)

    def test_unreadable_input_is_refused(self):
        r = self._run(base="{not json")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unreadable-input", r.stderr)

    def test_a_merge_without_a_repos_map_is_refused(self):
        r = self._run(base={}, ours={}, theirs={})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("merged-has-no-repos-map", r.stderr,
                      "a well-formed but meaningless registry must not be written")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        r = self._run(NOOP[".py"])
        self.assertEqual(r.stdout.strip(), "", "sanity: a no-op emits nothing")

    def test_the_ours_always_wins_mutant_fails_the_oracle(self):
        """The plausible wrong implementation — and the one that was actually shipped upstream
        before this: overlay ours on theirs.

        It produces a valid registry containing all the right repos, so a test checking shape
        or repo coverage accepts it. Only asking what each side CHANGED exposes the reversion.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.MERGE_ANCHOR, src, "mutation anchor missing")
        r = self._run(src.replace(self.MERGE_ANCHOR, self.MERGE_MUTANT))
        self.assertEqual(r.returncode, 0, r.stderr)
        repos = json.loads(r.stdout)["repos"]
        self.assertEqual(repos["b/y"]["state"], "discovered",
                         "mutation ineffective: the mutant should revert the remote's update")



class Test_log_event(unittest.TestCase):
    """`log-event.sh` — append one canonical event record to the ledger.

    E8.2a already wired all 18 emitters and ten ledger readers to this envelope, so its shape
    is a contract rather than a convention.
    """

    HELPER = SCRIPTS / "log-event.sh"
    SPREAD_ANCHOR = "run_number:($rn|tonumber? // 0), data:.}'"
    SPREAD_MUTANT = "run_number:($rn|tonumber? // 0)} + .'"
    NUMBER_ANCHOR = "run_number:($rn|tonumber? // 0), data:.}'"
    NUMBER_MUTANT = "run_number:$rn, data:.}'"

    def _emit(self, payload, script_text=None, run_number="10", workflow="discover",
              event="search_complete"):
        d = Path(tempfile.mkdtemp())
        helper = d / "helper.sh"
        helper.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        env = dict(os.environ)
        env["AUDITOR_DATA_DIR"] = str(d)
        env["GITHUB_RUN_NUMBER"] = run_number
        subprocess.run(
            ["bash", "-c", f". '{helper}'\nlog_event {workflow} {event} '{payload}'"],
            capture_output=True, text=True, env=env)
        ledger = d / "ledgers" / "events.jsonl"
        if not ledger.exists():
            return []
        return [json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]

    # --- oracle -------------------------------------------------------------------------
    def test_the_envelope_shape_is_exact(self):
        rows = self._emit('{"candidates":42}')
        self.assertEqual(len(rows), 1)
        self.assertEqual(sorted(rows[0]),
                         ["data", "event", "run_id", "run_number", "timestamp", "workflow"])
        self.assertEqual(rows[0]["data"], {"candidates": 42})

    def test_run_number_is_a_number_not_a_string(self):
        """Strings sort wrongly: "10" < "9" lexically, so run ordering inverts."""
        rows = self._emit('{"a":1}', run_number="10")
        self.assertIsInstance(rows[0]["run_number"], int)
        self.assertEqual(rows[0]["run_number"], 10)

    def test_a_payload_field_cannot_overwrite_an_envelope_field(self):
        """The reason the payload is nested rather than spread."""
        rows = self._emit('{"event":"HIJACK"}', event="scored")
        self.assertEqual(rows[0]["event"], "scored", "the envelope was overwritten")
        self.assertEqual(rows[0]["data"]["event"], "HIJACK", "the payload was dropped")

    def test_a_non_json_payload_is_raw_wrapped_not_lost(self):
        rows = self._emit("not json at all")
        self.assertEqual(rows[0]["data"], {"raw": "not json at all"})

    def test_a_junk_run_number_degrades_to_zero_rather_than_failing(self):
        rows = self._emit('{"a":1}', run_number="not-a-number")
        self.assertEqual(rows[0]["run_number"], 0)

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        self.assertEqual(self._emit('{"a":1}', NOOP[".sh"]), [],
                         "sanity: a no-op writes no ledger")

    def test_the_spread_payload_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: merge the payload into the envelope.

        The record still parses and still carries every field, so a shape check passes — until
        a payload key collides with an envelope key and every reader mis-attributes it.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.SPREAD_ANCHOR, src, "mutation anchor missing")
        rows = self._emit('{"event":"HIJACK"}',
                          src.replace(self.SPREAD_ANCHOR, self.SPREAD_MUTANT, 1),
                          event="scored")
        self.assertEqual(rows[0]["event"], "HIJACK",
                         "mutation ineffective: the payload should have overwritten the envelope")

    def test_the_string_run_number_mutant_fails_the_oracle(self):
        src = self.HELPER.read_text()
        self.assertIn(self.NUMBER_ANCHOR, src, "mutation anchor missing")
        rows = self._emit('{"a":1}',
                          src.replace(self.NUMBER_ANCHOR, self.NUMBER_MUTANT, 1),
                          run_number="10")
        self.assertIsInstance(rows[0]["run_number"], str, "mutation ineffective")



class Test_repair_stale_statuses(unittest.TestCase):
    """`repair-stale-statuses.py` — restore statuses a two-way merge race reverted."""

    HELPER = SCRIPTS / "repair-stale-statuses.py"
    TRUTHY_ANCHOR = 'if entry.get("score") is None:'
    TRUTHY_MUTANT = 'if not entry.get("score"):'
    DOWNSTREAM_ANCHOR = '        if status in DOWNSTREAM:\n            continue                       # the track workflow owns these\n'
    DOWNSTREAM_MUTANT = ''

    REGISTRY = {"repos": {
        "a/reverted": {"status": "discovered", "commit_sha_at_audit": "abc"},
        "b/contributed": {"status": "audited", "pipeline_prs": [1]},
        "c/zero": {"status": "audited", "score": 0, "commit_sha_at_audit": "d"},
        "d/missing": {"status": "audited", "commit_sha_at_audit": "e"},
        "e/tracked": {"status": "tracked", "commit_sha_at_audit": "f", "pipeline_prs": [2]},
        "f/complete": {"status": "complete", "pipeline_prs": [3]},
    }}

    def _run(self, script_text=None, registry=None):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "audits").mkdir()
        (d / "registry" / "repos.json").write_text(
            json.dumps(self.REGISTRY if registry is None else registry), encoding="utf-8")
        (d / "audits" / "d-missing.md").write_text("**NL Score**: 77/100\n", encoding="utf-8")
        (d / "audits" / "c-zero.md").write_text("**NL Score**: 55/100\n", encoding="utf-8")
        (d / "audits" / "e-tracked.md").write_text("**NL Score**: 88/100\n", encoding="utf-8")
        helper = d / "helper.py"
        helper.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        r = subprocess.run([sys.executable, str(helper), "--data-dir", str(d)],
                           capture_output=True, text=True)
        after = json.loads((d / "registry" / "repos.json").read_text())["repos"]
        return r, after

    # --- oracle -------------------------------------------------------------------------
    def test_documented_reversions_are_repaired(self):
        r, after = self._run()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(after["a/reverted"]["status"], "audited",
                         "commit_sha_at_audit proves the audit ran")
        self.assertEqual(after["b/contributed"]["status"], "contributed",
                         "pipeline_prs proves contribute ran")

    def test_a_real_zero_score_is_preserved(self):
        """0/100 is a legitimate — catastrophic — audit outcome, and exactly the result worth
        keeping. Truthiness would treat it as missing and overwrite it from the report."""
        _, after = self._run()
        self.assertEqual(after["c/zero"]["score"], 0,
                         "a real 0 was overwritten from the audit report")

    def test_a_genuinely_missing_score_is_recovered(self):
        _, after = self._run()
        self.assertEqual(after["d/missing"]["score"], 77)

    def test_downstream_statuses_are_never_touched(self):
        """tracked/complete belong to the track workflow; repairing them fabricates progress."""
        _, after = self._run()
        self.assertEqual(after["e/tracked"]["status"], "tracked")
        self.assertEqual(after["f/complete"]["status"], "complete")

    def test_dry_run_writes_nothing(self):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "audits").mkdir()
        original = json.dumps(self.REGISTRY)
        (d / "registry" / "repos.json").write_text(original, encoding="utf-8")
        subprocess.run([sys.executable, str(self.HELPER), "--data-dir", str(d), "--dry-run"],
                       capture_output=True, text=True)
        self.assertEqual((d / "registry" / "repos.json").read_text(), original)

    def test_an_unreadable_registry_is_refused(self):
        d = Path(tempfile.mkdtemp())
        (d / "registry").mkdir()
        (d / "registry" / "repos.json").write_text("{not json", encoding="utf-8")
        r = subprocess.run([sys.executable, str(self.HELPER), "--data-dir", str(d)],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("registry-unreadable", r.stderr)

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        _, after = self._run(NOOP[".py"])
        self.assertEqual(after["a/reverted"]["status"], "discovered",
                         "sanity: a no-op repairs nothing")

    def test_the_truthiness_mutant_overwrites_a_real_zero(self):
        """The plausible wrong implementation: `if not entry.get("score")`.

        It recovers every genuinely missing score correctly, so a test without a 0 in its
        fixture passes — while silently destroying the worst real score in the corpus.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.TRUTHY_ANCHOR, src, "mutation anchor missing")
        _, after = self._run(src.replace(self.TRUTHY_ANCHOR, self.TRUTHY_MUTANT, 1))
        self.assertEqual(after["c/zero"]["score"], 55,
                         "mutation ineffective: the mutant should overwrite the real 0")

    def test_the_downstream_guard_prevents_score_recovery_on_tracked_repos(self):
        """What the guard ACTUALLY does — measured, not assumed.

        An earlier version of this test asserted the guard stops a `tracked` repo being
        downgraded to `contributed`. It does not: the inner conditions already exclude
        `tracked`, so removing the guard changes nothing about status. Its real effect is
        narrower — it keeps repair out of downstream entries entirely, including their scores.
        The test now asserts that, so it fails for the reason it claims.
        """
        registry = {"repos": {"e/tracked": {"status": "tracked", "commit_sha_at_audit": "f",
                                            "pipeline_prs": [2]}}}
        src = self.HELPER.read_text()
        self.assertIn(self.DOWNSTREAM_ANCHOR, src, "mutation anchor missing")

        _, guarded = self._run(registry=registry)
        self.assertNotIn("score", guarded["e/tracked"],
                         "a downstream entry must be left entirely alone")

        _, unguarded = self._run(src.replace(self.DOWNSTREAM_ANCHOR, self.DOWNSTREAM_MUTANT, 1),
                                 registry=registry)
        self.assertEqual(unguarded["e/tracked"].get("score"), 88,
                         "mutation ineffective: without the guard a tracked repo gains a score")



class Test_build_exemplar_gallery(unittest.TestCase):
    """`build-exemplar-gallery.py` — the exemplar index, regenerated and CI-checked."""

    HELPER = SCRIPTS / "build-exemplar-gallery.py"
    SORT_ANCHOR = 'for item in sorted(items, key=lambda i: (i["repo"], i["slug"])):'
    SORT_MUTANT = 'for item in items:'

    def _corpus(self):
        d = Path(tempfile.mkdtemp())
        (d / "exemplars").mkdir()
        # Deliberately created in NON-alphabetical order so a helper that preserves input
        # order produces different output from one that sorts.
        for slug, repo, score, rule in (("zeta", "acme/zeta", "90", "R02"),
                                        ("alpha", "acme/alpha", "90", "R01"),
                                        ("mid", "beta/mid", "40", "R02")):
            (d / "exemplars" / f"{slug}.md").write_text(
                f"---\nslug: {slug}\nrepo: {repo}\naudited: 2026-01-01\n"
                f"score: {score}\nexemplifies:\n  - {rule}\n---\nbody\n",
                encoding="utf-8")
        (d / "exemplars" / "broken.md").write_text("---\nslug: broken\n---\nno repo\n",
                                                   encoding="utf-8")
        return d

    def _run(self, d, script_text=None, check=False):
        helper = Path(tempfile.mkdtemp()) / "helper.py"
        helper.write_text(script_text or self.HELPER.read_text(), encoding="utf-8")
        argv = [sys.executable, str(helper), "--data-dir", str(d)]
        if check:
            argv.append("--check")
        return subprocess.run(argv, capture_output=True, text=True)

    # --- oracle -------------------------------------------------------------------------
    def test_output_is_byte_identical_across_runs(self):
        """The gallery is CI-checked, so output must depend on the corpus, not on the order
        the filesystem happened to return entries in."""
        d = self._corpus()
        self._run(d)
        first = (d / "exemplars" / "README.md").read_text()
        self._run(d)
        self.assertEqual(first, (d / "exemplars" / "README.md").read_text())

    def test_every_view_is_sorted(self):
        d = self._corpus()
        self._run(d)
        text = (d / "exemplars" / "README.md").read_text()
        by_repo = text.split("## By repo")[1]
        order = [ln for ln in by_repo.splitlines() if ln.startswith("- [")]
        self.assertEqual(order, sorted(order), "the by-repo view is not sorted")
        # equal scores must tie-break on repo, not on input order
        by_score = text.split("## By score")[1].split("## By repo")[0]
        nineties = [ln for ln in by_score.splitlines() if ln.startswith("- 90/100")]
        self.assertEqual(nineties, sorted(nineties), "equal scores did not tie-break")

    def test_an_unparseable_exemplar_is_skipped_and_counted(self):
        """The gallery is an index, not a validator — but a silent skip hides a broken corpus."""
        d = self._corpus()
        r = self._run(d)
        self.assertIn("skipped 1", r.stderr)
        self.assertNotIn("broken", (d / "exemplars" / "README.md").read_text())

    def test_check_detects_a_stale_gallery(self):
        d = self._corpus()
        self._run(d)
        self.assertEqual(self._run(d, check=True).returncode, 0, "fresh gallery reported stale")
        readme = d / "exemplars" / "README.md"
        readme.write_text(readme.read_text() + "drift\n", encoding="utf-8")
        self.assertEqual(self._run(d, check=True).returncode, 1, "stale gallery not detected")

    def test_check_on_a_missing_corpus_is_a_distinct_exit(self):
        r = self._run(Path(tempfile.mkdtemp()), check=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("corpus-missing", r.stderr)

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d = self._corpus()
        self._run(d, NOOP[".py"])
        self.assertFalse((d / "exemplars" / "README.md").exists(),
                         "sanity: a no-op writes no gallery")

    def test_the_input_order_mutant_fails_the_oracle(self):
        """The plausible wrong implementation: index in filesystem order.

        It produces a correct and complete gallery — every exemplar present, every link right —
        so a content check passes. Only ordering exposes it, and the cost is a freshness gate
        that reports drift on an unchanged corpus until people learn to ignore it.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.SORT_ANCHOR, src, "mutation anchor missing")
        d = self._corpus()
        self._run(d, src.replace(self.SORT_ANCHOR, self.SORT_MUTANT))
        by_repo = (d / "exemplars" / "README.md").read_text().split("## By repo")[1]
        order = [ln for ln in by_repo.splitlines() if ln.startswith("- [")]
        self.assertNotEqual(order, sorted(order),
                            "mutation ineffective: the mutant should emit unsorted output")



class Test_resolve_merge_conflicts(unittest.TestCase):
    """`resolve-merge-conflicts.sh` — per-file conflict strategy, against a REAL git conflict.

    Each strategy exists because a naive default lost data: two-way merges reverted disjoint
    remote registry updates, and `--ours` on append-only ledgers dropped the remote's appended
    lines entirely, making every metric derived from them wrong.
    """

    HELPER = SCRIPTS / "resolve-merge-conflicts.sh"
    REG_ANCHOR = '  if ! python3 "$HERE/three-way-merge-registry.py" \\\n        "$TMP/base.json" "$TMP/ours.json" "$TMP/theirs.json" > "$TMP/merged.json"; then\n    echo "REFUSE:resolve-merge-conflicts:registry-merge-failed" >&2\n    exit 1\n  fi'
    REG_MUTANT = '  cp "$TMP/ours.json" "$TMP/merged.json"'
    LEDGER_ANCHOR = '    cat "$TMP/theirs.jsonl" "$TMP/ours.jsonl" | awk \'!seen[$0]++\' > "$CHECKOUT/$ledger"'
    LEDGER_MUTANT = '    cp "$TMP/ours.jsonl" "$CHECKOUT/$ledger"'

    def _conflicted_repo(self):
        """A data checkout mid-conflict: ours changed a/x, theirs changed b/y, both appended."""
        d = Path(tempfile.mkdtemp()) / "data"
        d.mkdir()
        g = lambda *a: subprocess.run(["git", "-C", str(d), *a], capture_output=True, check=False)
        g("init", "-q", ".")
        g("config", "user.email", "t@e")
        g("config", "user.name", "t")
        (d / "registry").mkdir()
        (d / "ledgers").mkdir()
        (d / "registry" / "repos.json").write_text(
            '{"repos":{"a/x":{"state":"discovered"},"b/y":{"state":"discovered"}}}',
            encoding="utf-8")
        (d / "ledgers" / "events.jsonl").write_text('{"e":1}\n', encoding="utf-8")
        g("add", "-A"); g("commit", "-qm", "base")
        g("branch", "-q", "remote-side")

        (d / "registry" / "repos.json").write_text(
            '{"repos":{"a/x":{"state":"audited"},"b/y":{"state":"discovered"}}}',
            encoding="utf-8")
        (d / "ledgers" / "events.jsonl").write_text('{"e":1}\n{"e":"ours"}\n', encoding="utf-8")
        g("add", "-A"); g("commit", "-qm", "ours")
        ours_branch = subprocess.run(["git", "-C", str(d), "rev-parse", "--abbrev-ref", "HEAD"],
                                     capture_output=True, text=True).stdout.strip()

        g("checkout", "-q", "remote-side")
        (d / "registry" / "repos.json").write_text(
            '{"repos":{"a/x":{"state":"discovered"},"b/y":{"state":"contributed"}}}',
            encoding="utf-8")
        (d / "ledgers" / "events.jsonl").write_text('{"e":1}\n{"e":"theirs"}\n', encoding="utf-8")
        g("add", "-A"); g("commit", "-qm", "theirs")

        g("checkout", "-q", ours_branch)
        g("merge", "remote-side")          # conflicts
        return d

    def _resolve(self, d, script_text=None):
        helper = SCRIPTS / "resolve-merge-conflicts.sh"
        if script_text is None:
            path = helper
        else:
            path = Path(tempfile.mkdtemp()) / "resolve.sh"
            path.write_text(script_text, encoding="utf-8")
            # siblings resolve relative to the script, so link them next to the mutant
            for sib in ("three-way-merge-registry.py", "atomic-registry-write.sh",
                        "build-exemplar-gallery.py"):
                (path.parent / sib).write_text((SCRIPTS / sib).read_text(), encoding="utf-8")
        return subprocess.run(["bash", str(path), "--checkout", str(d)],
                              capture_output=True, text=True)

    # --- oracle -------------------------------------------------------------------------
    def test_both_sides_registry_changes_survive(self):
        """The acceptance property, against a real conflict."""
        d = self._conflicted_repo()
        r = self._resolve(d)
        self.assertEqual(r.returncode, 0, r.stderr)
        repos = json.loads((d / "registry" / "repos.json").read_text())["repos"]
        self.assertEqual(repos["a/x"]["state"], "audited", "our change was lost")
        self.assertEqual(repos["b/y"]["state"], "contributed", "the remote's change was reverted")

    def test_append_only_lines_are_neither_lost_nor_duplicated(self):
        d = self._conflicted_repo()
        self._resolve(d)
        lines = [x for x in (d / "ledgers" / "events.jsonl").read_text().splitlines() if x.strip()]
        self.assertIn('{"e":"ours"}', lines, "our appended line was lost")
        self.assertIn('{"e":"theirs"}', lines, "the remote's appended line was lost")
        self.assertEqual(len(lines), len(set(lines)), "a line was duplicated")
        self.assertEqual(lines.count('{"e":1}'), 1, "the shared base line was duplicated")

    def test_the_conflict_is_fully_staged_afterwards(self):
        d = self._conflicted_repo()
        self._resolve(d)
        remaining = subprocess.run(["git", "-C", str(d), "diff", "--name-only",
                                    "--diff-filter=U"], capture_output=True, text=True).stdout
        self.assertEqual(remaining.strip(), "", f"unresolved paths remain: {remaining}")

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        d = self._conflicted_repo()
        self._resolve(d, NOOP[".sh"])
        remaining = subprocess.run(["git", "-C", str(d), "diff", "--name-only",
                                    "--diff-filter=U"], capture_output=True, text=True).stdout
        self.assertNotEqual(remaining.strip(), "", "sanity: a no-op resolves nothing")

    def test_the_two_way_registry_mutant_reverts_the_remote(self):
        """The strategy this replaces: take ours wholesale."""
        src = self.HELPER.read_text()
        self.assertIn(self.REG_ANCHOR, src, "registry mutation anchor missing")
        d = self._conflicted_repo()
        self._resolve(d, src.replace(self.REG_ANCHOR, self.REG_MUTANT, 1))
        repos = json.loads((d / "registry" / "repos.json").read_text())["repos"]
        self.assertEqual(repos["b/y"]["state"], "discovered",
                         "mutation ineffective: the mutant should revert the remote's change")

    def test_the_ours_ledger_mutant_drops_the_remotes_lines(self):
        """The `--ours` default that made per-rule metrics undercount by several times."""
        src = self.HELPER.read_text()
        self.assertIn(self.LEDGER_ANCHOR, src, "ledger mutation anchor missing")
        d = self._conflicted_repo()
        self._resolve(d, src.replace(self.LEDGER_ANCHOR, self.LEDGER_MUTANT, 1))
        lines = (d / "ledgers" / "events.jsonl").read_text()
        self.assertNotIn('{"e":"theirs"}', lines,
                         "mutation ineffective: the mutant should drop the remote's line")



class Test_git_push_with_retry(unittest.TestCase):
    """`git-push-with-retry.sh` — the issue's named acceptance, against a REAL push race.

    Two clones of one bare remote. B commits and pushes first; A commits a DISJOINT change and
    pushes into the race. The traversal is retry -> rebase -> resolver -> three-way merger ->
    atomic writer, and the remote must end with both sides' work intact.
    """

    HELPER = SCRIPTS / "git-push-with-retry.sh"
    GITDIR_ANCHOR = 'if [ -d "$GIT_DIR_PATH/rebase-merge" ] || [ -d "$GIT_DIR_PATH/rebase-apply" ]; then'
    GITDIR_MUTANT = 'if [ -d ".git/rebase-merge" ] || [ -d ".git/rebase-apply" ]; then'

    def _race(self):
        """A bare remote, a losing clone `a` mid-race, and B's change already pushed."""
        t = Path(tempfile.mkdtemp())
        run = lambda *a, **k: subprocess.run(a, capture_output=True, text=True, **k)
        run("git", "init", "-q", "--bare", str(t / "remote.git"))
        run("git", "-C", str(t / "remote.git"), "symbolic-ref", "HEAD", "refs/heads/main")
        for name in ("a", "b"):
            run("git", "clone", "-q", str(t / "remote.git"), str(t / name))
            run("git", "-C", str(t / name), "config", "user.email", "t@e")
            run("git", "-C", str(t / name), "config", "user.name", "t")
            run("git", "-C", str(t / name), "checkout", "-q", "-B", "main")

        (t / "a" / "registry").mkdir(parents=True)
        (t / "a" / "ledgers").mkdir(parents=True)
        (t / "a" / "registry" / "repos.json").write_text(
            '{"repos":{"a/x":{"state":"discovered"},"b/y":{"state":"discovered"}}}',
            encoding="utf-8")
        (t / "a" / "ledgers" / "events.jsonl").write_text('{"e":1}\n', encoding="utf-8")
        run("git", "-C", str(t / "a"), "add", "-A")
        run("git", "-C", str(t / "a"), "commit", "-qm", "base")
        run("git", "-C", str(t / "a"), "push", "-q", "-u", "origin", "main")

        run("git", "-C", str(t / "b"), "pull", "-q", "origin", "main")
        run("git", "-C", str(t / "b"), "branch", "-q", "--set-upstream-to=origin/main", "main")
        (t / "b" / "registry" / "repos.json").write_text(
            '{"repos":{"a/x":{"state":"discovered"},"b/y":{"state":"contributed"}}}',
            encoding="utf-8")
        (t / "b" / "ledgers" / "events.jsonl").write_text('{"e":1}\n{"e":"theirs"}\n',
                                                      encoding="utf-8")
        run("git", "-C", str(t / "b"), "add", "-A")
        run("git", "-C", str(t / "b"), "commit", "-qm", "theirs")
        run("git", "-C", str(t / "b"), "push", "-q")

        (t / "a" / "registry" / "repos.json").write_text(
            '{"repos":{"a/x":{"state":"audited"},"b/y":{"state":"discovered"}}}',
            encoding="utf-8")
        (t / "a" / "ledgers" / "events.jsonl").write_text('{"e":1}\n{"e":"ours"}\n',
                                                      encoding="utf-8")
        run("git", "-C", str(t / "a"), "add", "-A")
        run("git", "-C", str(t / "a"), "commit", "-qm", "ours")
        return t

    def _push(self, t, script_text=None, attempts="3"):
        if script_text is None:
            path = self.HELPER
        else:
            path = Path(tempfile.mkdtemp()) / "push.sh"
            path.write_text(script_text, encoding="utf-8")
            for sib in ("resolve-merge-conflicts.sh", "three-way-merge-registry.py",
                        "atomic-registry-write.sh", "build-exemplar-gallery.py"):
                (path.parent / sib).write_text((SCRIPTS / sib).read_text(), encoding="utf-8")
        return subprocess.run(["bash", str(path), "--checkout", str(t / "a"),
                               "--attempts", attempts], capture_output=True, text=True)

    def _remote_state(self, t):
        verify = t / f"verify{tempfile.mkdtemp()[-6:]}"
        subprocess.run(["git", "clone", "-q", str(t / "remote.git"), str(verify)],
                       capture_output=True)
        repos = json.loads((verify / "registry" / "repos.json").read_text())["repos"]
        lines = [x for x in (verify / "ledgers" / "events.jsonl").read_text().splitlines()
                 if x.strip()]
        return repos, lines

    # --- oracle: the named acceptance ---------------------------------------------------
    def test_both_sides_work_reaches_the_remote(self):
        t = self._race()
        r = self._push(t)
        self.assertEqual(r.returncode, 0, r.stderr)
        repos, lines = self._remote_state(t)
        self.assertEqual(repos["a/x"]["state"], "audited", "our registry change was lost")
        self.assertEqual(repos["b/y"]["state"], "contributed", "the remote's change was reverted")
        self.assertIn('{"e":"ours"}', lines, "our appended line was lost")
        self.assertIn('{"e":"theirs"}', lines, "the remote's appended line was lost")

    def test_append_only_lines_are_not_duplicated(self):
        t = self._race()
        self._push(t)
        _, lines = self._remote_state(t)
        self.assertEqual(len(lines), len(set(lines)), f"duplicated lines: {lines}")

    def test_exhaustion_is_a_hard_failure(self):
        """A push that never landed must not look like success."""
        r = subprocess.run(["bash", str(self.HELPER), "--checkout", "/nonexistent",
                            "--attempts", "1"], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("REFUSE:git-push-with-retry:", r.stderr)

    def test_a_non_worktree_checkout_is_refused(self):
        r = subprocess.run(["bash", str(self.HELPER), "--checkout", tempfile.mkdtemp()],
                           capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not-a-git-worktree", r.stderr)

    # --- mutants ------------------------------------------------------------------------
    def test_a_no_op_helper_fails_the_oracle(self):
        t = self._race()
        self._push(t, NOOP[".sh"])
        repos, _ = self._remote_state(t)
        self.assertEqual(repos["a/x"]["state"], "discovered",
                         "sanity: a no-op pushes nothing")

    def test_the_relative_git_dir_mutant_strands_the_rebase(self):
        """The CI-only failure: probe `.git/rebase-merge` relative to the PROCESS cwd.

        It finds nothing whenever the helper runs from anywhere but the checkout, so the rebase
        is never continued, the loop spins to exhaustion, and the work is stranded mid-rebase —
        after the conflicts were already resolved correctly.
        """
        src = self.HELPER.read_text()
        self.assertIn(self.GITDIR_ANCHOR, src, "mutation anchor missing")
        t = self._race()
        r = self._push(t, src.replace(self.GITDIR_ANCHOR, self.GITDIR_MUTANT, 1))
        self.assertNotEqual(r.returncode, 0,
                            "mutation ineffective: the mutant should fail to complete the rebase")

if __name__ == "__main__":
    unittest.main()
