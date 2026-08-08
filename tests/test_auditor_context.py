# SPDX-License-Identifier: ISC
"""E8.2b context derivation (vibe-164, plan W2/W3): derive it or refuse by name.

The issue requires the graph to "resolve and validate its own context from the trigger
(target repo, issue number, audited SHA from the registry, default branch, author identity,
cap)" with "named refusals for each unresolvable value". Before this suite, `submit` supplied
defaults for four of them -- AUDITED_SHA to empty, BASE_BRANCH to main, the author to a
literal `vibe-suite auditor`, and the patch cap to 3 -- so an unresolved value did not refuse,
it proceeded with a fabricated one. An audited SHA defaulting to empty is the sharpest case:
the checkout guard is `[ -n "$AUDITED_SHA" ]`, so an empty default silently skips the pin and
the engine proposes patches against whatever HEAD happens to be.

Each test names the value and asserts the refusal, not just the resolution. A derivation that
resolves correctly but fails open is the defect this issue exists to close.
"""
import json
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract, FIX

WF = Path(__file__).resolve().parent.parent / "auditor" / "workflows" / "auditor-contribute.yml"

# The eight values the graph must derive rather than be handed.
DERIVED = ["repo", "issue", "expected_fork_slug", "audited_sha",
           "base_branch", "author_name", "author_email", "weekly_cap", "patch_cap"]


class ContextBase(unittest.TestCase):
    """Stubs the API BOUNDARY, never the answer.

    `gh api user` and `gh api repos/<repo>` are served canned; the block still has to call
    them and build the value itself. Handing the block a ready-made `expected_fork_slug` or
    `base_branch` would be the very thing the acceptance clause forbids -- a test supplying a
    value the graph must derive -- and the W-scan would flag it. Repo variables
    (AUDITOR_AUTHOR_NAME/EMAIL, WEEKLY_CAP) are configuration inputs, not derivations, so
    setting them is legitimate in the same way a secret is.
    """

    def block(self, name="derive-context", marker="stage-logic"):
        self.assertTrue(WF.is_file(), f"{WF} missing")
        b = extract(WF, marker, name)
        self.assertIsNotNone(
            b, f"no {marker}:{name} block in {WF.name} -- W2.1 must add the marker so the "
               f"derivation is extractable and therefore testable")
        return b

    def canned(self, sb, login="vibe-bot", default_branch="main"):
        """Write canned API responses; return the env that points the stub at them."""
        env = {}
        if login is not None:
            f = sb.root / "canned-user"
            f.write_text(login + "\n")
            env["GH_CANNED_API_USER"] = str(f)
        if default_branch is not None:
            f = sb.root / "canned-repo"
            f.write_text(default_branch + "\n")
            m = sb.root / "canned-map"
            m.write_text("api repos/acme/claude-toolkit\t" + str(f) + "\n")
            env["GH_CANNED_MAP"] = str(m)
        return env

    def run_ctx(self, env=None, registry="registry-audited.json", login="vibe-bot",
                default_branch="main"):
        sb = Sandbox(registry=registry)
        base = {
            "REPO": "acme/claude-toolkit", "ISSUE_NUMBER": "42",
            "AUDITOR_AUTHOR_NAME": "vibe-suite auditor bot",
            "AUDITOR_AUTHOR_EMAIL": "auditor@example.invalid",
            "WEEKLY_CAP": "2",
        }
        base.update(self.canned(sb, login=login, default_branch=default_branch))
        base.update(env or {})
        r = sb.run(self.block(), env=base)
        return r, sb

    def context(self, sb):
        p = sb.root / "context.json"
        self.assertTrue(p.is_file(),
                        "gates wrote no context.json; the relay has nothing to carry")
        return json.loads(p.read_text())


class TestContextIsExtractable(ContextBase):
    def test_the_derivation_carries_a_marker(self):
        self.assertIsNotNone(extract(WF, "stage-logic", "derive-context"))


class TestContextRefusesByName(ContextBase):
    """Each unresolvable value refuses with its own name -- never a generic failure."""

    def test_audited_sha_refuses_when_the_registry_has_none(self):
        r, _ = self.run_ctx(registry="registry.json")  # base fixture carries no audited SHA
        self.assertIn("REFUSE:context-audited-sha-unresolvable", r.stdout + r.stderr)

    def test_default_branch_refuses_when_the_api_cannot_resolve_it(self):
        r, _ = self.run_ctx(default_branch="")
        self.assertIn("REFUSE:context-default-branch-unresolvable", r.stdout + r.stderr)

    def test_author_identity_refuses_rather_than_using_a_literal(self):
        r, _ = self.run_ctx({"AUDITOR_AUTHOR_NAME": "", "AUDITOR_AUTHOR_EMAIL": ""})
        out = r.stdout + r.stderr
        self.assertIn("REFUSE:context-author-identity-unresolvable", out)
        self.assertNotIn("vibe-suite auditor@", out)

    def test_weekly_cap_refuses_when_unset(self):
        r, _ = self.run_ctx({"WEEKLY_CAP": ""})
        self.assertIn("REFUSE:context-weekly-cap-unresolvable", r.stdout + r.stderr)

    def test_issue_number_refuses_when_the_trigger_carries_none(self):
        r, _ = self.run_ctx({"ISSUE_NUMBER": "", "INPUT_ISSUE_NUMBER": ""})
        self.assertIn("REFUSE:context-issue-unresolvable", r.stdout + r.stderr)

    def test_repo_refuses_when_the_trigger_carries_none(self):
        r, _ = self.run_ctx({"REPO": "", "INPUT_REPO": "", "FIXTURE": ""})
        self.assertIn("REFUSE:context-repo-unresolvable", r.stdout + r.stderr)


class TestForkSlugComesFromTheBotIdentity(ContextBase):
    """The fork owner is the PAT's own login -- never the target owner, never guessed."""

    def test_the_block_actually_asks_for_the_identity(self):
        r, sb = self.run_ctx()
        self.assertTrue(any("api user" in c for c in sb.gh_calls()),
                        "the block never called `gh api user`; the login was assumed")

    def test_fork_slug_is_built_from_the_identity_response(self):
        r, sb = self.run_ctx()
        self.assertEqual("vibe-bot/claude-toolkit", self.context(sb)["expected_fork_slug"])

    def test_fork_slug_is_not_the_target_owner(self):
        r, sb = self.run_ctx()
        self.assertNotEqual(
            "acme", self.context(sb)["expected_fork_slug"].split("/")[0],
            "the fork slug was built from OWNER (the TARGET owner). Probing that slug probes "
            "the target repository, not the bot's fork -- Step-5 finding 2.")

    def test_fork_slug_refuses_when_the_identity_call_returns_nothing(self):
        r, _ = self.run_ctx(login="")
        self.assertIn("REFUSE:context-fork-slug-unresolvable", r.stdout + r.stderr)


class TestContextIsAWrittenArtifact(ContextBase):
    """W2.2: one immutable document, not eight scalar job outputs."""

    def test_context_json_carries_every_derived_value(self):
        r, sb = self.run_ctx()
        ctx = self.context(sb)
        missing = [k for k in DERIVED if k not in ctx]
        self.assertEqual([], missing, f"context.json omits derived values: {missing}")

    def test_context_json_carries_a_version(self):
        r, sb = self.run_ctx()
        self.assertEqual(1, self.context(sb).get("version"))
