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


# --- W3: the consumers read the relay, or refuse ---------------------------------------

class ConsumerBase(ContextBase):
    """Runs a consumer block against a context.json the derivation actually produced.

    The consumer is never handed a loose AUDITED_SHA/BASE_BRANCH/author/cap in the
    environment -- that is the injection the acceptance clause forbids. It gets the file and
    has to read it.
    """

    marker = "logic"
    name = None

    def consumer_block(self):
        b = extract(WF, self.marker, self.name)
        self.assertIsNotNone(b, f"no {self.marker}:{self.name} block in {WF.name}")
        return b

    def with_context(self, sb, **overrides):
        """Write a context.json shaped like the one gates emits, minus any dropped keys."""
        ctx = {"version": 1, "repo": "acme/claude-toolkit", "issue": "42",
               "expected_fork_slug": "vibe-bot/claude-toolkit",
               "audited_sha": "cafebabecafebabecafebabecafebabecafebabe",
               "base_branch": "trunk", "author_name": "vibe-suite auditor bot",
               "author_email": "auditor@example.invalid", "weekly_cap": 2, "patch_cap": 3}
        for k, v in overrides.items():
            if v is None:
                ctx.pop(k, None)
            else:
                ctx[k] = v
        p = sb.root / "context.json"
        p.write_text(json.dumps(ctx))
        return p

    def run_consumer(self, ctx_overrides=None, env=None, registry="registry-audited.json"):
        sb = Sandbox(registry=registry)
        p = self.with_context(sb, **(ctx_overrides or {}))
        base = {"REPO": "acme/claude-toolkit", "CONTEXT_FILE": str(p),
                "PATCH_DIR": str(sb.root / "_patches"), "TARGET_DIR": str(sb.root / "_target")}
        base.update(env or {})
        r = sb.run(self.consumer_block(), env=base)
        return r, sb


class TestSubmitReadsTheRelay(ConsumerBase):
    """W3.1/W3.4 -- submit's four defaults are gone; absence refuses."""

    name = "submit"

    def test_audited_sha_absent_refuses_instead_of_defaulting_empty(self):
        r, _ = self.run_consumer({"audited_sha": None})
        out = r.stdout + r.stderr
        self.assertIn("REFUSE:context-audited-sha-unresolvable", out)
        self.assertNotEqual(0, r.returncode,
                            "submit continued without an audited SHA; the checkout guard "
                            "`[ -n \"$AUDITED_SHA\" ]` then silently skips the commit pin")

    def test_base_branch_absent_refuses_instead_of_defaulting_main(self):
        r, _ = self.run_consumer({"base_branch": None})
        self.assertIn("REFUSE:context-default-branch-unresolvable", r.stdout + r.stderr)

    def test_base_branch_reaches_pr_create_from_the_relay(self):
        # Observable, not a string-absence check: BASE_BRANCH is used at `gh pr create
        # --base "$BASE_BRANCH"`, so the gh call log shows which value actually won. An
        # assertNotIn on stdout passed vacuously here -- the block never echoes it.
        r, sb = self.run_consumer()
        calls = " ".join(sb.gh_calls())
        if "pr create" in calls:
            self.assertIn("--base trunk", calls,
                          "pr create used a base branch other than the relay's 'trunk'")
            self.assertNotIn("--base main", calls)
        else:
            self.skipTest("submit did not reach pr create under this fixture")

    def test_author_identity_absent_refuses_instead_of_a_literal(self):
        r, _ = self.run_consumer({"author_name": None, "author_email": None})
        out = r.stdout + r.stderr
        self.assertIn("REFUSE:context-author-identity-unresolvable", out)
        self.assertNotIn("auditor@users.noreply.github.com", out,
                         "the generic author literal is still reachable")

    def test_patch_cap_absent_refuses_instead_of_defaulting_three(self):
        r, _ = self.run_consumer({"patch_cap": None})
        self.assertIn("REFUSE:context-patch-cap-unresolvable", r.stdout + r.stderr)


class TestReserveReadsTheRelay(ConsumerBase):
    """W3.3 -- reserve's weekly cap comes from the relay, not the constant 2."""

    name = "reserve"

    def test_weekly_cap_absent_refuses_instead_of_defaulting_two(self):
        r, _ = self.run_consumer({"weekly_cap": None})
        self.assertIn("REFUSE:context-weekly-cap-unresolvable", r.stdout + r.stderr)

    # Behavioural governance of the cap (does a cap of 2 refuse where 7 admits?) needs a
    # real bare-remote + clone, which tests/test_auditor_reservation.py already builds via
    # ReservationBase.setup_data. Duplicating a weaker version here would have added a test
    # that passes because an earlier `data-branch-unreachable` refusal fires, never because
    # the cap governed anything. That suite now delivers the cap through context.json, so it
    # covers the relay end to end; this suite keeps the refusal contract only.


class TestTheRelayIsActuallyTransported(unittest.TestCase):
    """The relay must cross JOB boundaries, not just exist in gates' workspace.

    Every test above sets CONTEXT_FILE to a local path, so all of them pass whether or not
    the file is ever transported between jobs. It was not: gates wrote context.json into its
    own runner's workspace, every consumer runs on a fresh runner, and nothing uploaded or
    downloaded it -- so on a real run every consumer would have refused relay-missing while
    the entire suite stayed green. Only an existing topology test noticed, and only for the
    manifest, because finalize happened to download that one by name.

    A test that supplies the file location can never observe its absence. These assertions
    read the workflow's own artifact wiring instead.
    """

    PRODUCED = {
        "gate-context": "context.json",
        "proposal-manifest": "proposal-manifest.json",
        "gate-disclosure": "disclosure.json",
    }

    @classmethod
    def setUpClass(cls):
        cls.text = WF.read_text(encoding="utf-8")

    def _jobs(self):
        import re
        names = [m.group(1) for m in re.finditer(r"^  ([a-z][a-z-]*):$", self.text, re.M)]
        out = {}
        for i, n in enumerate(names):
            start = self.text.index(f"\n  {n}:")
            end = (self.text.index(f"\n  {names[i+1]}:") if i + 1 < len(names) else len(self.text))
            out[n] = self.text[start:end]
        return out

    def test_every_gate_output_is_uploaded_by_its_producer(self):
        gates = self._jobs()["gates"]
        for artifact in self.PRODUCED:
            self.assertIn(
                f"name: {artifact}", gates,
                f"gates writes {self.PRODUCED[artifact]} but never uploads it as "
                f"'{artifact}'. On a real run the file dies with the runner and every "
                f"consumer refuses relay-missing.")

    def test_every_consumer_of_the_context_downloads_it(self):
        jobs = self._jobs()
        for job in ("reserve", "propose", "submit", "finalize"):
            self.assertIn(
                "name: gate-context", jobs[job],
                f"the {job} job reads CONTEXT_FILE but never downloads gate-context")

    def test_finalize_downloads_the_manifest_it_reads(self):
        self.assertIn("name: proposal-manifest", self._jobs()["finalize"],
                      "finalize reads quota facts from the manifest but never downloads it")

    def test_propose_still_downloads_no_disclosure(self):
        # The transport must not accidentally hand the model job the disclosure artifact.
        self.assertNotIn("gate-disclosure", self._jobs()["propose"],
                         "wiring the relay handed propose the disclosure artifact")
