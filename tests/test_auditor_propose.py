# SPDX-License-Identifier: ISC
"""E8.2b propose-side target clone (vibe-164, plan W3.2).

The issue requires `propose` -- the job that runs the model -- to clone "the target at its
audited SHA". Before this suite it cloned neither: its two checkouts take this repository and
the `auditor-data` branch, so the job described as reading the audited tree did not have that
tree at all.

This is deliberately NOT tested through tests/test_auditor_submit.py. That module already has
a green `test_checkout_is_at_the_audited_sha`, but it exercises SUBMIT's checkout, which is a
different job with a different failure mode; reusing it would let an already-passing assertion
stand in for a path that was never built. Step-5 finding 4.
"""
import json
import subprocess
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract

WF = Path(__file__).resolve().parent.parent / "auditor" / "workflows" / "auditor-contribute.yml"

HAS_GIT = subprocess.run(["git", "--version"], capture_output=True).returncode == 0
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e.invalid"}


def git(*a, cwd, check=True):
    return subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True,
                          check=check, env={"PATH": "/usr/bin:/bin:/usr/local/bin", **GIT_ENV})


@unittest.skipUnless(HAS_GIT, "git is required")
class TestProposeClonesTheAuditedSha(unittest.TestCase):
    def block(self):
        b = extract(WF, "stage-logic", "propose-clone")
        self.assertIsNotNone(
            b, "no stage-logic:propose-clone block -- W3.2 must add the clone AND its marker; "
               "propose currently checks out only this repo and auditor-data")
        return b

    def setUp(self):
        self.sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(self.sb.cleanup)
        # A stand-in "target" with two commits, so an unpinned clone lands on the wrong one.
        self.target = self.sb.root / "target.git"
        self.target.mkdir()
        git("init", "-b", "main", cwd=self.target)
        (self.target / "a.txt").write_text("audited state\n")
        git("add", "-A", cwd=self.target); git("commit", "-m", "audited", cwd=self.target)
        self.audited = git("rev-parse", "HEAD", cwd=self.target).stdout.strip()
        (self.target / "a.txt").write_text("later drift\n")
        git("add", "-A", cwd=self.target); git("commit", "-m", "drift", cwd=self.target)
        self.head = git("rev-parse", "HEAD", cwd=self.target).stdout.strip()

    def run_clone(self, audited_sha=None):
        ctx = {"version": 1, "repo": "acme/claude-toolkit", "issue": "42",
               "expected_fork_slug": "vibe-bot/claude-toolkit",
               "audited_sha": self.audited if audited_sha is None else audited_sha,
               "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
               "weekly_cap": 2, "patch_cap": 3}
        p = self.sb.root / "context.json"; p.write_text(json.dumps(ctx))
        env = {"CONTEXT_FILE": str(p), "TARGET_DIR": str(self.sb.root / "_target"),
               "TARGET_REMOTE": str(self.target), "REPO": "acme/claude-toolkit", **GIT_ENV}
        return self.sb.run(self.block(), env=env), self.sb.root / "_target"

    def test_the_clone_lands_on_the_audited_sha_not_head(self):
        r, tgt = self.run_clone()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        at = git("rev-parse", "HEAD", cwd=tgt).stdout.strip()
        self.assertEqual(self.audited, at,
                         f"propose is at {at[:12]} (later drift) rather than the audited "
                         f"{self.audited[:12]}; the model would review code that was never audited")

    def test_the_audited_content_is_what_the_model_would_see(self):
        r, tgt = self.run_clone()
        self.assertEqual("audited state\n", (tgt / "a.txt").read_text())

    def test_an_unresolvable_sha_refuses_rather_than_taking_head(self):
        r, _ = self.run_clone(audited_sha="")
        self.assertIn("REFUSE:context-audited-sha-unresolvable", r.stdout + r.stderr)

    def test_a_sha_absent_from_the_target_refuses(self):
        r, _ = self.run_clone(audited_sha="0" * 40)
        out = r.stdout + r.stderr
        self.assertIn("REFUSE:", out)
        self.assertNotEqual(0, r.returncode,
                            "a SHA the target does not contain was tolerated; the clone would "
                            "silently fall back to HEAD")
