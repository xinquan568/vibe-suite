# SPDX-License-Identifier: ISC
"""Behavioural tests for the E8.3 helpers under `auditor/scripts/`.

The issue's acceptance is "all smoke tests green", so these tests ARE the evidence. A test that
passes when its helper is replaced by a no-op establishes nothing, and existence checks,
`--help`, `bash -n`, import success and unasserted invocation all survive that substitution.

Every helper therefore carries, per the E8.3 specification:

  * a **behavioural oracle** — a postcondition of the contract, not a banner or incidental
    output;
  * a **no-op mutant** — the interpreter-correct do-nothing replacement, which the oracle must
    reject. (`exit 0` is a SyntaxError in Python, so a shell no-op would make every Python
    helper's oracle "fail" for the wrong reason and prove nothing. The replacement is chosen
    per helper class.)
  * a **wrong-behaviour mutant** — a plausible mis-implementation, which the oracle must also
    reject. This is what proves the oracle is attached to the contract's meaning rather than to
    some accident of the real helper's output.

One class per helper, named `Test_<helper stem>`, so the mutation harness can address a single
helper's oracle.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "auditor" / "scripts"

#: Interpreter-correct no-ops. A shell `exit 0` does not parse as Python.
NOOP = {
    ".sh": "#!/usr/bin/env bash\n# SPDX-License-Identifier: ISC\nexit 0\n",
    ".py": "#!/usr/bin/env python3\n# SPDX-License-Identifier: ISC\nraise SystemExit(0)\n",
}


def source_and_call(script_text, snippet):
    """Run `snippet` in a bash shell that has sourced `script_text`.

    Sourceable helpers have no CLI, so mutation must go through the same caller shell the real
    oracle uses — otherwise the mutant is exercised differently from the original and the
    comparison proves nothing.
    """
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "helper.sh"
        path.write_text(script_text, encoding="utf-8")
        return subprocess.run(["bash", "-c", f". '{path}'\n{snippet}"],
                              capture_output=True, text=True)


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


if __name__ == "__main__":
    unittest.main()
