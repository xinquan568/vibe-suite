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
import re
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
            # F2: gates holds no PAT, so the expected fork owner is a non-secret repo
            # variable here; the claim is PROVEN in submit against `gh api user` with the PAT.
            "AUDITOR_FORK_OWNER": "vibe-bot",
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


class TriggerBase(ContextBase):
    """Drive the derivation through the workflow's OWN `env:` mapping, not a supplied dict.

    Every other test in this file hands the block `REPO` directly. That is precisely the hole
    Step-8 finding 1 named: it means no test ever exercised what a real trigger actually
    delivers, and on an `issues` event -- the ordinary production trigger -- `INPUT_REPO` is
    empty, so `gates` refused `context-repo-unresolvable` before any gate ran. The graph could
    not complete on either trigger and the whole suite was green.

    So this harness reads the step's declared `env:` block out of the YAML, evaluates each
    `${{ ... }}` against a simulated event payload, and passes ONLY that. A value the workflow
    does not bind is a value the block does not get. Adding a test here cannot paper over a
    missing binding, because the binding is the thing under test.
    """

    #: The expressions the mapping is allowed to use. Anything else fails loudly rather than
    #: resolving to empty -- an unrecognised expression silently becoming "" would reproduce
    #: the exact defect this class exists to catch.
    def _eval(self, expr, event, inputs, variables):
        expr = expr.strip()
        if expr.startswith("${{") and expr.endswith("}}"):
            expr = expr[3:-2].strip()
        if expr.startswith("join(github.event.issue.labels.*.name"):
            sep = expr.rsplit(",", 1)[1].strip().rstrip(")").strip().strip("'\"")
            return sep.join(l for l in event.get("labels", []))
        if expr == "github.event.issue.number":
            n = event.get("number")
            return "" if n is None else str(n)
        if expr == "github.token":
            return "ghs_simulated_actions_token"
        if expr.startswith("inputs."):
            return str(inputs.get(expr.split(".", 1)[1], "") or "")
        if expr.startswith("vars."):
            return str(variables.get(expr.split(".", 1)[1], "") or "")
        raise AssertionError(
            f"the derive-context env: block uses an expression this harness does not model: "
            f"{expr!r}. Model it here rather than letting it resolve to empty -- an unmodelled "
            f"expression reading as '' is how finding 1 stayed invisible.")

    def step_env(self):
        """The `env:` mapping of the derive-context step, as declared in the YAML."""
        text = WF.read_text()
        m = re.search(r"^\s*# env-for:derive-context.*?^\s*env:\s*$(.*?)^\s*# /env-for\s*$",
                      text, re.M | re.S)
        self.assertIsNotNone(
            m, "no `# env-for:derive-context` ... `# /env-for` mapping in the workflow. The "
               "marker pair exists so the step's real trigger wiring is testable; the shell "
               "block's own `# /stage-logic` must close BEFORE it, or the YAML lands in the "
               "extracted script.")
        mapping = {}
        for line in m.group(1).split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition(":")
            mapping[k.strip()] = v.strip()
        return mapping

    def run_trigger(self, event_name, event=None, inputs=None, variables=None,
                    registry="registry-audited.json", extra=None, default_branch="main"):
        variables = {
            "AUDITOR_AUTHOR_NAME": "vibe-suite auditor bot",
            "AUDITOR_AUTHOR_EMAIL": "auditor@example.invalid",
            "AUDITOR_FORK_OWNER": "vibe-bot",
            "WEEKLY_CAP": "2",
            **(variables or {}),
        }
        sb = Sandbox(registry=registry)
        env = {k: self._eval(v, event or {}, inputs or {}, variables)
               for k, v in self.step_env().items()}
        # FIXTURE is a real cross-workflow channel (auditor-audit writes it), but it also
        # carries repo.full_name, so leaving it set would hand the block the answer and the
        # trigger path would never be exercised. Blank it for these tests only.
        env["FIXTURE"] = ""
        env.update(self.canned(sb, login=None, default_branch=default_branch))
        env.update(extra or {})
        r = sb.run(self.block(), env=env)
        return r, sb


class TestTheRealTriggersReachTheGraph(TriggerBase):
    """Both production triggers must produce a context. Neither did."""

    def test_the_issues_trigger_resolves_the_repository_from_the_registry(self):
        # No dispatch input exists on an `issues` event. The tracking issue is the only handle
        # the payload carries, and the registry maps it back to the repository (`audit_issue`).
        r, sb = self.run_trigger("issues", event={"number": 901, "labels": ["contribute-approved"]})
        self.assertNotIn("REFUSE:context-repo-unresolvable", r.stdout + r.stderr)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual("acme/claude-toolkit", self.context(sb)["repo"])

    def test_the_dispatch_trigger_still_resolves_from_its_input(self):
        r, sb = self.run_trigger(
            "workflow_dispatch",
            inputs={"repo": "acme/claude-toolkit", "issue_number": "901"})
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual("acme/claude-toolkit", self.context(sb)["repo"])

    def test_the_issues_trigger_reaches_a_complete_context(self):
        # The point of finding 1 is that the run must reach `reserve`, not merely resolve the
        # repo. Every derived value has to survive the real mapping.
        r, sb = self.run_trigger("issues", event={"number": 901, "labels": ["contribute-approved"]})
        ctx = self.context(sb)
        missing = [k for k in DERIVED if not str(ctx.get(k, "")).strip()]
        self.assertEqual([], missing,
                         f"the issues trigger reached a context missing {missing}; the run "
                         f"would refuse before reserve")

    def test_an_unknown_issue_still_refuses_by_name(self):
        r, _ = self.run_trigger("issues", event={"number": 4242, "labels": []})
        self.assertIn("REFUSE:context-repo-unresolvable", r.stdout + r.stderr)

    def test_an_ambiguous_issue_refuses_rather_than_picking_one(self):
        # Two repositories claiming the same tracking issue is a registry defect. Picking the
        # first would contribute to an arbitrary repository -- the failure mode is silent and
        # the blast radius is somebody else's codebase.
        sb = Sandbox(registry="registry-audited.json")
        reg = json.loads((sb.data / "registry" / "repos.json").read_text())
        reg["repos"]["other/toolkit"] = dict(reg["repos"]["acme/claude-toolkit"])
        (sb.data / "registry" / "repos.json").write_text(json.dumps(reg))
        env = {k: self._eval(v, {"number": 901, "labels": []}, {},
                             {"AUDITOR_AUTHOR_NAME": "n", "AUDITOR_AUTHOR_EMAIL": "e",
                              "AUDITOR_FORK_OWNER": "vibe-bot", "WEEKLY_CAP": "2"})
               for k, v in self.step_env().items()}
        env["FIXTURE"] = ""
        env.update(self.canned(sb, login=None, default_branch="main"))
        r = sb.run(self.block(), env=env)
        self.assertIn("REFUSE:context-repo-ambiguous", r.stdout + r.stderr)


class TestTheRealDerivationSatisfiesTheConsumers(TriggerBase):
    """F10's composition case: derive-context → the captured context.json → the consumers.

    Every consumer test in this file (and in the manifest, quota, submit and fork suites)
    hand-writes a context.json "shaped like the one gates emits". That is legitimate for the
    refusal cases -- proving a consumer refuses when the relay omits `audited_sha` needs a
    relay with `audited_sha` omitted, which only a crafted file can provide. But if every
    relay in the suite is hand-written, nothing ever checks that the shape the producer
    actually writes is the shape the consumers actually read. The two could drift apart key by
    key and the suite would stay green.

    So this runs the REAL derivation through the REAL trigger wiring and feeds its output,
    byte for byte, to the consumers -- with no derived value supplied anywhere.
    """

    def produced_context(self):
        r, sb = self.run_trigger("issues", event={"number": 901, "labels": ["contribute-approved"]})
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        p = sb.root / "context.json"
        self.assertTrue(p.is_file(), "derive-context produced no relay to compose over")
        return p, sb

    def test_the_produced_relay_carries_every_key_the_consumers_read(self):
        p, sb = self.produced_context()
        produced = json.loads(p.read_text())
        # The keys consumers actually `jq` out of the relay, read from the workflow rather
        # than from memory -- a list written by hand is a list that drifts.
        text = WF.read_text(encoding="utf-8")
        read = set(re.findall(r"jq -r '\.([a-z_]+) // empty' \"\$\{?CONTEXT_FILE", text))
        read |= set(re.findall(r"ctx ([a-z_]+)\)", text))
        self.assertTrue(read, "found no relay reads to check against; the pattern changed")
        missing = sorted(k for k in read if k not in produced)
        self.assertEqual(
            [], missing,
            f"the consumers read {missing} from the relay and derive-context does not write "
            f"them. Every hand-written context.json in the suite supplies them, so no other "
            f"test can see this.")

    def test_a_consumer_accepts_the_produced_relay_unchanged(self):
        p, sb = self.produced_context()
        # submit's entry validation, given ONLY the produced file and the API boundary stubs.
        # No AUDITED_SHA, no BASE_BRANCH, no FORK_SLUG, no author, no cap.
        u = sb.root / "canned-user"
        u.write_text("vibe-bot\n")
        block = extract(WF, "logic", "submit-entry") or extract(WF, "logic", "submit")
        if block is None:
            self.skipTest("submit's entry block is not separately extractable")
        r = sb.run(block, env={"CONTEXT_FILE": str(p), "PAT_SECRET": "stub-pat",
                               "GH_CANNED_API_USER": str(u),
                               "TARGET_DIR": str(sb.root / "_target")})
        for name in ("relay-missing", "audited-sha-unresolvable", "base-branch-unresolvable",
                     "author-identity-unresolvable", "patch-cap-unresolvable",
                     "issue-unresolvable", "fork-slug-unresolvable"):
            self.assertNotIn(
                f"REFUSE:context-{name}", r.stdout + r.stderr,
                f"the consumer refused '{name}' against a relay the real derivation produced. "
                f"The producer and the consumer disagree about the relay's shape, and every "
                f"hand-written context.json in the suite hides it.")


class TestTheStepBindsEveryValueItReads(TriggerBase):
    """A value the block reads from the environment must be bound by the step's `env:`.

    This is the general form of finding 1. The block read AUDITOR_AUTHOR_NAME,
    AUDITOR_AUTHOR_EMAIL, WEEKLY_CAP and AUDITOR_FORK_OWNER, and the step bound none of them,
    so `workflow_dispatch` refused at `author-identity` even when the repo resolved. Enumerating
    the reads from the block text means a newly-added read cannot escape the check.
    """

    #: Set by the harness (Sandbox) or by an earlier step via $GITHUB_ENV, not by this step.
    HARNESS_OR_UPSTREAM = {
        "DATA_DIR", "REGISTRY", "EVENT_LOG", "DECISION", "OUTCOME_DIR", "SIDECAR",
        "CONTEXT_FILE", "GITHUB_WORKSPACE", "GITHUB_ENV", "FIXTURE", "PWD",
        "REPO", "OWNER", "ISSUE",
    }

    def test_every_configuration_value_the_block_reads_is_bound_by_the_step(self):
        block = self.block()
        read = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*):?[-:]?[^}]*\}", block))
        read |= set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)\}", block))
        candidates = {n for n in read if n not in self.HARNESS_OR_UPSTREAM}
        bound = set(self.step_env())
        unbound = sorted(candidates - bound)
        self.assertEqual(
            [], unbound,
            f"the derive-context block reads {unbound} but the step's env: binds none of them, "
            f"so on a real run they are empty and the job refuses. Bind them from vars/github "
            f"or stop reading them.")

    def test_the_step_can_authenticate_the_default_branch_read(self):
        # BASE_BRANCH comes from `gh api repos/<repo>`, which needs a token. Without one the
        # call fails and the job refuses `default-branch` on every real run.
        self.assertIn("GH_TOKEN", self.step_env(),
                      "the block calls `gh api` but the step binds no GH_TOKEN")


class TestForkSlugComesFromTheBotIdentity(ContextBase):
    """The fork owner is the PAT's own login -- never the target owner, never guessed."""

    def test_gates_does_not_pretend_to_prove_identity(self):
        # F2: gates holds no PAT. Calling `gh api user` here proved nothing -- unauthenticated
        # it fails, and with github.token it identifies the Actions installation. The claim is
        # verified in submit, where the PAT lives; gates only carries the expectation.
        r, sb = self.run_ctx()
        self.assertFalse(any("api user" in c for c in sb.gh_calls()),
                         "gates called `gh api user` with no PAT bound; the result cannot "
                         "establish who owns the fork")

    def test_fork_slug_is_built_from_the_identity_response(self):
        r, sb = self.run_ctx()
        self.assertEqual("vibe-bot/claude-toolkit", self.context(sb)["expected_fork_slug"])

    def test_fork_slug_is_not_the_target_owner(self):
        r, sb = self.run_ctx()
        self.assertNotEqual(
            "acme", self.context(sb)["expected_fork_slug"].split("/")[0],
            "the fork slug was built from OWNER (the TARGET owner). Probing that slug probes "
            "the target repository, not the bot's fork -- Step-5 finding 2.")

    def test_fork_owner_refuses_when_the_variable_is_unset(self):
        r, _ = self.run_ctx({"AUDITOR_FORK_OWNER": ""})
        self.assertIn("REFUSE:context-fork-owner-unresolvable", r.stdout + r.stderr)


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

    # Every (job, artifact) pair a job READS. Derived from the workflow's own consumption,
    # not from memory: the previous version listed only the pairs I recalled, which is exactly
    # how `submit` reading the manifest and `finalize` reading the disclosure both survived a
    # test written to catch reads-without-downloads (Step-8 F4 and F5).
    READS = [
        ("reserve", "gate-context"),
        ("propose", "gate-context"),
        ("submit", "gate-context"),
        ("submit", "proposal-manifest"),
        ("finalize", "gate-context"),
        ("finalize", "proposal-manifest"),
        ("finalize", "gate-disclosure"),
    ]

    def test_every_reader_downloads_what_it_reads(self):
        jobs = self._jobs()
        missing = [f"{job} reads {art} but never downloads it"
                   for job, art in self.READS if art not in self._downloads(jobs[job])]
        self.assertEqual([], missing, "\n  ".join([""] + missing))

    def test_finalize_can_route_a_refusal_that_happened_before_the_context_existed(self):
        """F1's last clause: the refusal path must not depend on the refused job's output.

        `gates` refusing in derive-context means no context.json is ever uploaded. finalize
        runs `always()` and is the only job that can label the tracking issue and write the
        ledger row -- but its gate-context download was mandatory, so it died on a missing
        artifact and the named refusal reached nobody. The one job whose purpose is to report
        the failure could not run precisely when there was a failure to report.
        """
        finalize = self._jobs()["finalize"]
        m = re.search(r"uses:\s*actions/download-artifact@[^\n]*\n((?:\s+[^\n]*\n)+?)"
                      r"(?=\s*- |\Z)", finalize)
        blocks = [b.group(1) for b in re.finditer(
            r"uses:\s*actions/download-artifact@[^\n]*\n((?:\s+[^\n]*\n)+?)(?=\s*- |\Z)", finalize)]
        ctx = [b for b in blocks if re.search(r"name:\s*gate-context\b", b)]
        self.assertTrue(ctx, "finalize no longer downloads gate-context at all")
        self.assertTrue(
            any("continue-on-error: true" in b for b in ctx),
            "finalize's gate-context download is mandatory, so a context refusal in gates "
            "takes finalize down with it and the refusal is never routed. Mark it "
            "continue-on-error: true -- finalize already tolerates a missing context.")

    def test_finalize_can_still_name_the_issue_when_gates_produced_no_outputs(self):
        # A gates job that refused in derive-context never reached the guard step, so
        # needs.gates.outputs.issue is empty. On the `issues` trigger the number is right
        # there in the event payload; without a fallback the refusal is silent.
        finalize = self._jobs()["finalize"]
        # Match the YAML mapping, not the shell line `ISSUE="${ISSUE_NUMBER:-...}"` that reads
        # it -- the binding and the read are different things and only one of them is wiring.
        m = re.search(r"^\s+ISSUE_NUMBER:\s*(\$\{\{.+)$", finalize, re.M)
        self.assertIsNotNone(m, "finalize's routing step binds no ISSUE_NUMBER expression")
        self.assertIn(
            "github.event.issue.number", m.group(1),
            "ISSUE_NUMBER comes only from needs.gates.outputs, which is empty exactly when "
            "gates refused early. Fall back to the event payload.")

    @staticmethod
    def _downloads(job_text):
        """Artifact names this job DOWNLOADS. Uploads are a different direction entirely.

        A bare `name: gate-disclosure` search flagged gates, which PRODUCES the artifact --
        the fourth time in this issue a prohibition assertion matched the wrong construct
        (the others: the word 'disclosure' in prose, a comment warning against a pattern, and
        text following an unrelated download step). Match the step, not the string.
        """
        import re
        out = []
        for m in re.finditer(r"uses:\s*actions/download-artifact@[^\n]*\n((?:\s+[^\n]*\n)+?)"
                             r"(?=\s*- |\Z)", job_text):
            for nm in re.finditer(r"name:\s*(\S+)", m.group(1)):
                out.append(nm.group(1))
        return out

    def test_only_finalize_downloads_the_disclosure(self):
        jobs = self._jobs()
        for job in ("gates", "reserve", "propose", "submit"):
            self.assertNotIn(
                "gate-disclosure", self._downloads(jobs[job]),
                f"{job} downloads the disclosure set; only finalize may. propose is the "
                f"sharpest case -- it runs the model.")
        self.assertIn("gate-disclosure", self._downloads(jobs["finalize"]),
                      "finalize never downloads the disclosure set, so critical findings can "
                      "vanish while an ordinary contribution proceeds")

    def test_propose_still_downloads_no_disclosure(self):
        # The transport must not accidentally hand the model job the disclosure artifact.
        self.assertNotIn("gate-disclosure", self._jobs()["propose"],
                         "wiring the relay handed propose the disclosure artifact")
