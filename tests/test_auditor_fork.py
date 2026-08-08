# SPDX-License-Identifier: ISC
"""E8.2b fork lifecycle (vibe-164, plan W5): probe, verify, and never delete.

Three properties the issue states, none of which held:

  * `gates` probes fork existence WITHOUT creating anything. There was no probe at all; the
    only fork operation was `gh repo fork` in submit.
  * `submit` re-confirms the COMPLETE invariant after creation -- the fork resolves, it is a
    fork, its owner is the PAT's login, and its parent is the target. None was checked.
  * a failed post-creation check REFUSES and records an `orphaned_fork` ledger entry. The
    fork is never deleted: deleting a repository under a third-party account is not an action
    this pipeline takes on its own judgement (operator policy, 2026-08-07).

Wave 1 declared the orphaned_fork record in SCHEMAS.md. A declaration emits nothing -- that
was Step-5 finding 7 against the plan -- so these tests drive the emitter itself.
"""
import json
import subprocess
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract, FIX

REPO_ROOT = Path(__file__).resolve().parent.parent
WF = REPO_ROOT / "auditor" / "workflows" / "auditor-contribute.yml"
TARGET = "acme/claude-toolkit"
BOT = "vibe-bot"


def canned(sb, name, payload):
    p = sb.root / f"canned-{name}"
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    return p


class ForkBase(unittest.TestCase):
    def block(self, name, marker="gate"):
        b = extract(WF, marker, name)
        self.assertIsNotNone(b, f"no {marker}:{name} block in {WF.name}")
        return b

    def ctx(self, sb, fork_slug=f"{BOT}/claude-toolkit"):
        p = sb.root / "context.json"
        p.write_text(json.dumps({
            "version": 1, "repo": TARGET, "issue": "42",
            "expected_fork_slug": fork_slug, "audited_sha": "cafebabe",
            "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
            "weekly_cap": 2, "patch_cap": 3}))
        return p


class TestGatesProbeCreatesNothing(ForkBase):
    """W5.1 -- a read-only probe. gates holds contents:read and must stay read-only."""

    def run_probe(self, exists=True):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        env = {"REPO": TARGET, "OWNER": TARGET.split("/")[0],
               "CONTEXT_FILE": str(self.ctx(sb))}
        if exists:
            m = sb.root / "map"
            f = canned(sb, "fork", {"full_name": f"{BOT}/claude-toolkit", "fork": True})
            m.write_text(f"api repos/{BOT}/claude-toolkit\t{f}\n")
            env["GH_CANNED_MAP"] = str(m)
        return sb.run(self.block("fork-probe"), env=env), sb

    def test_the_probe_creates_nothing(self):
        r, sb = self.run_probe()
        calls = " ".join(sb.gh_calls())
        self.assertNotIn("repo fork", calls,
                         "the probe created a fork; gates is specified read-only")
        for verb in ("-X POST", "--method POST", "repo create"):
            self.assertNotIn(verb, calls, f"the probe issued a mutation ({verb})")

    def test_the_probe_addresses_the_bots_fork_not_the_target(self):
        r, sb = self.run_probe()
        calls = " ".join(sb.gh_calls())
        self.assertIn(f"{BOT}/claude-toolkit", calls,
                      "the probe never addressed the derived fork slug")
        self.assertNotIn(f"api repos/{TARGET}", calls,
                         "the probe addressed the TARGET repository -- a probe built from "
                         "$OWNER inspects the wrong repo entirely")

    def test_absence_is_reported_not_fatal(self):
        r, _ = self.run_probe(exists=False)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("FORK:absent", r.stdout)

    def test_presence_is_reported(self):
        r, _ = self.run_probe(exists=True)
        self.assertIn("FORK:present", r.stdout)


class TestPostCreationInvariant(ForkBase):
    """W5.2 -- all four parts, each failing independently."""

    def run_verify(self, fork_json=None, resolves=True):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        env = {"REPO": TARGET, "OWNER": TARGET.split("/")[0],
               "CONTEXT_FILE": str(self.ctx(sb)),
               "EVENT_LOG": str(sb.data / "ledgers" / "events.jsonl"),
               "DATA_DIR": str(sb.data)}
        if resolves:
            m = sb.root / "map"
            f = canned(sb, "fork", fork_json if fork_json is not None else
                       {"full_name": f"{BOT}/claude-toolkit", "fork": True,
                        "parent": {"full_name": TARGET}})
            m.write_text(f"api repos/{BOT}/claude-toolkit\t{f}\n")
            env["GH_CANNED_MAP"] = str(m)
        return sb.run(self.block("verify-fork", marker="stage-logic"), env=env), sb

    def test_a_fork_that_does_not_resolve_refuses(self):
        r, _ = self.run_verify(resolves=False)
        self.assertIn("REFUSE:fork-invariant:resolves", r.stdout + r.stderr)

    def test_a_repo_that_is_not_a_fork_refuses(self):
        r, _ = self.run_verify({"full_name": f"{BOT}/claude-toolkit", "fork": False,
                                "parent": {"full_name": TARGET}})
        self.assertIn("REFUSE:fork-invariant:is_fork", r.stdout + r.stderr)

    def test_a_fork_owned_by_someone_else_refuses(self):
        r, _ = self.run_verify({"full_name": "someone-else/claude-toolkit", "fork": True,
                                "parent": {"full_name": TARGET}})
        self.assertIn("REFUSE:fork-invariant:owner_matches", r.stdout + r.stderr)

    def test_a_fork_of_a_different_parent_refuses(self):
        r, _ = self.run_verify({"full_name": f"{BOT}/claude-toolkit", "fork": True,
                                "parent": {"full_name": "someone/else"}})
        self.assertIn("REFUSE:fork-invariant:parent_matches", r.stdout + r.stderr)

    def test_a_complete_invariant_passes(self):
        r, _ = self.run_verify()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)


class TestOrphanedForkIsRecordedAndNeverDeleted(ForkBase):
    """W5.3 -- the durable emitter. Wave 1 declared the record; this writes it."""

    def run_failed_invariant(self):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        m = sb.root / "map"
        f = canned(sb, "fork", {"full_name": "someone-else/claude-toolkit", "fork": True,
                                "parent": {"full_name": TARGET}})
        m.write_text(f"api repos/{BOT}/claude-toolkit\t{f}\n")
        r = sb.run(self.block("verify-fork", marker="stage-logic"), env={
            "REPO": TARGET, "OWNER": TARGET.split("/")[0],
            "CONTEXT_FILE": str(self.ctx(sb)), "GH_CANNED_MAP": str(m),
            "EVENT_LOG": str(sb.data / "ledgers" / "events.jsonl"),
            "DATA_DIR": str(sb.data)})
        return r, sb

    def test_the_fork_is_never_deleted(self):
        r, sb = self.run_failed_invariant()
        calls = " ".join(sb.gh_calls())
        for destructive in ("repo delete", "-X DELETE", "--method DELETE"):
            self.assertNotIn(
                destructive, calls,
                "the pipeline deleted a repository under a third-party account. Operator "
                "policy 2026-08-07 is never delete: the record exists to hand it to a human.")

    def test_an_orphaned_fork_record_is_appended(self):
        r, sb = self.run_failed_invariant()
        events = [e for e in sb.events() if e.get("event") == "orphaned_fork"]
        self.assertTrue(events, "no orphaned_fork event was appended; the never-delete policy "
                                "leaves nothing behind for a human to clean up")

    def test_the_record_names_which_check_failed(self):
        r, sb = self.run_failed_invariant()
        ev = [e for e in sb.events() if e.get("event") == "orphaned_fork"][0]
        self.assertEqual("owner_matches", ev["data"]["invariant_failed"])
        self.assertEqual(f"{BOT}/claude-toolkit", ev["data"]["fork_slug"])


class TestForkSlugNeverFallsBackToTheTarget(unittest.TestCase):
    """W5.4 -- an empty slug must not resolve to the target repository."""

    def test_the_push_remote_has_no_target_fallback(self):
        # Comment lines are stripped first: the block carries a comment explaining why this
        # construct is forbidden, and matching that would be a prohibition test failing on
        # its own documentation.
        code = "\n".join(l for l in WF.read_text(encoding="utf-8").split("\n")
                         if not l.lstrip().startswith("#"))
        self.assertNotIn(
            '${FORK_SLUG:-$REPO}', code,
            "the fork remote falls back to $REPO when the slug is empty, so the submission "
            "branch would be pushed to the TARGET repository instead of the bot's fork")


class TestCleanupRunbook(unittest.TestCase):
    """W5.5 -- never-delete needs an operator-facing procedure, or it is just an orphan."""

    def test_the_runbook_documents_manual_fork_cleanup(self):
        readme = (REPO_ROOT / "auditor" / "README.md").read_text(encoding="utf-8")
        self.assertIn("orphaned_fork", readme,
                      "the runbook never mentions orphaned_fork, so an operator has no way to "
                      "find the forks the policy deliberately leaves behind")
