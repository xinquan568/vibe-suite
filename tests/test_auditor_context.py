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


def _job_bodies(text):
    """{job name: its YAML body}. Shared by the relay-topology and job-binding checks."""
    names = [m.group(1) for m in re.finditer(r"^  ([a-z][a-z-]*):$", text, re.M)]
    out = {}
    for i, n in enumerate(names):
        start = text.index(f"\n  {n}:")
        end = text.index(f"\n  {names[i+1]}:") if i + 1 < len(names) else len(text)
        out[n] = text[start:end]
    return out

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

    def step_env(self, marker="derive-context"):
        """The `env:` mapping of the named step, as declared in the YAML."""
        text = WF.read_text()
        m = re.search(r"^\s*# env-for:%s.*?^\s*env:\s*$(.*?)^\s*# /env-for\s*$"
                      % re.escape(marker), text, re.M | re.S)
        self.assertIsNotNone(
            m, f"no `# env-for:{marker}` ... `# /env-for` mapping in the workflow. The "
               "marker pair exists so the step's real trigger wiring is testable; the shell "
               "block's own closing marker must come BEFORE it, or the YAML lands in the "
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
        env["DECISION"] = str(sb.root / "decision.json")
        env.update(self.canned(sb, login=None, default_branch="main"))
        r = sb.run(self.block(), env=env)
        self.assertIn("REFUSE:context-repo-ambiguous", r.stdout + r.stderr)
        # F1, round 4: stderr is not where the outcome publisher reads. Every other refusal
        # in this block routes through refuse(), which records the named reason in the
        # decision file; this branch exited inline, so the publisher reported status=error
        # with an EMPTY reason while the name sat only in the log. The refusal must land in
        # the decision file like the rest.
        decision_file = sb.root / "decision.json"
        self.assertTrue(decision_file.is_file(),
                        "the ambiguous refusal wrote no decision file, so the outcome "
                        "publisher has no named reason to report")
        decision = json.loads(decision_file.read_text())
        self.assertFalse(decision.get("proceed", True))
        self.assertIn("context-repo-ambiguous", decision.get("reason", ""),
                      f"the decision file carries reason {decision.get('reason')!r}; the "
                      f"publisher would report this refusal without its name")


class TestSecurityGateReadsLiveLabels(TriggerBase):
    """F10.a (round 2): the security hold is a fact about the tracking issue NOW.

    The gate used to read labels from the event payload, which `workflow_dispatch` does not
    carry — so a dispatch run compared an empty string and an existing `security-blocked`
    label never blocked. The gate now reads the issue's current labels through the API,
    authenticated by the step's token against the workflow's own repository (never $REPO,
    the audited target), and any failure refuses by name with `side_exit_label:
    pipeline-error` — outside the `security-*` reason namespace, so an infrastructure
    failure cannot route as a disclosure.

    The harness is production-shaped: derive-context runs first with the workflow's own
    trigger wiring, and the gate consumes its real `$GITHUB_ENV` exports — `ISSUE` is never
    injected (it is on the no-supplied-derivations DERIVED list).
    """

    WORKFLOW_REPO = "example/auditor-repo"

    def gate_block(self):
        b = extract(WF, "gate", "security-blocked")
        self.assertIsNotNone(b, "no gate:security-blocked block")
        return b

    def _derive_then_gate(self, event=None, inputs=None, labels=None, api_fails=False):
        variables = {
            "AUDITOR_AUTHOR_NAME": "vibe-suite auditor bot",
            "AUDITOR_AUTHOR_EMAIL": "auditor@example.invalid",
            "AUDITOR_FORK_OWNER": "vibe-bot",
            "WEEKLY_CAP": "2",
        }
        sb = Sandbox(registry="registry-audited.json")
        genv = sb.root / "github.env"
        env = {k: self._eval(v, event or {}, inputs or {}, variables)
               for k, v in self.step_env().items()}
        env["FIXTURE"] = ""
        env["GITHUB_ENV"] = str(genv)
        env.update(self.canned(sb, login=None, default_branch="main"))
        r1 = sb.run(self.block(), env=env)
        self.assertEqual(0, r1.returncode,
                         f"derive-context refused; the gate never runs on such a run:\n"
                         f"{r1.stdout}\n{r1.stderr}")
        exports = {}
        for line in genv.read_text().splitlines():
            k, _, v = line.partition("=")
            exports[k] = v
        self.assertIn("ISSUE", exports, "derive-context exported no ISSUE")
        gate_env = {k: self._eval(v, event or {}, inputs or {}, variables)
                    for k, v in self.step_env(marker="security-blocked").items()}
        endpoint = f"repos/{self.WORKFLOW_REPO}/issues/{exports['ISSUE']}"
        run_env = dict(exports)
        run_env.update(gate_env)
        run_env["GITHUB_REPOSITORY"] = self.WORKFLOW_REPO
        run_env["GITHUB_ENV"] = str(genv)
        if api_fails:
            run_env["GH_FAIL"] = f"api:{endpoint}"
            run_env.pop("GH_CANNED_MAP", None)
        else:
            # RAW issue JSON, as the API returns it: the stub applies the block's own --jq
            # expression, so these tests exercise the production extraction — a broken
            # expression that reads as empty must fail the bypass test, not pass on a
            # pre-joined fixture (Step-8 finding 2).
            f = sb.root / "canned-labels"
            f.write_text(json.dumps(
                {"labels": [{"name": l} for l in (labels or [])]}) + "\n")
            m = sb.root / "canned-labels-map"
            m.write_text(f"api {endpoint}\t{f}\n")
            run_env["GH_CANNED_MAP"] = str(m)
        r2 = sb.run(self.gate_block(), env=run_env)
        return r2, sb, exports

    def test_a_dispatch_run_cannot_bypass_a_security_hold(self):
        # The round-5 finding, verbatim: no github.event.issue on dispatch, so an env
        # binding is empty and the hold never blocks. The live read must block.
        r, sb, _ = self._derive_then_gate(
            inputs={"repo": "acme/claude-toolkit", "issue_number": "901"},
            labels=["contribute-approved", "security-blocked"])
        self.assertNotEqual(0, r.returncode,
                            "a dispatch run passed the security gate while the tracking "
                            "issue carries security-blocked — the bypass the round-5 verify "
                            "named" + f"\n{r.stdout}\n{r.stderr}")
        self.assertIn("REFUSE:security-blocked", r.stdout + r.stderr)

    def test_a_labeled_event_run_still_refuses(self):
        r, _, _ = self._derive_then_gate(
            event={"number": 901, "labels": ["contribute-approved", "security-blocked"]},
            labels=["contribute-approved", "security-blocked"])
        self.assertNotEqual(0, r.returncode)
        self.assertIn("REFUSE:security-blocked", r.stdout + r.stderr)

    def test_clean_labels_pass(self):
        r, _, _ = self._derive_then_gate(
            event={"number": 901, "labels": ["contribute-approved"]},
            labels=["contribute-approved"])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_an_unlabeled_issue_passes(self):
        # The production jq expression against a raw `labels: []` response: join yields the
        # empty string, which is a real "no hold" answer, distinct from a FAILED read (the
        # test above). Regression-pins the extraction on the empty case.
        r, _, _ = self._derive_then_gate(
            event={"number": 901, "labels": ["contribute-approved"]}, labels=[])
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertIn("PASS", r.stdout)

    def test_an_unreachable_label_read_refuses_by_name(self):
        # Fail closed: an unreadable label set must never read as "no labels" — that would
        # reopen the bypass through every transient API failure.
        r, sb, exports = self._derive_then_gate(
            event={"number": 901, "labels": ["contribute-approved"]}, api_fails=True)
        self.assertNotEqual(0, r.returncode,
                            "the gate passed while the label read failed; an unverified "
                            "hold was treated as no hold")
        self.assertIn("REFUSE:issue-labels-unresolvable", r.stdout + r.stderr)
        decision = json.loads(Path(exports["DECISION"]).read_text())
        self.assertFalse(decision.get("proceed", True))
        self.assertEqual("issue-labels-unresolvable", decision.get("reason"),
                         "the refusal must publish its name where the outcome publisher "
                         "reads it")
        self.assertEqual("pipeline-error", decision.get("side_exit_label"),
                         "an infrastructure failure must route as pipeline-error, never "
                         "into the security-*/disclosure branch")


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

    def job_env(self, job, needs=None):
        """A job's declared step `env:` bindings, evaluated against a simulated context.

        Same principle as `step_env` for derive-context: the values a consumer job receives are
        read out of the workflow and evaluated, never invented here. `REPO` reaching submit via
        `needs.reserve.outputs.repo` is JOB WIRING and modelling it is modelling production;
        writing `"REPO": "acme/claude-toolkit"` into a dict by hand is the injection the
        acceptance clause forbids. The difference is the whole point.
        """
        jobs = _job_bodies(WF.read_text(encoding="utf-8"))
        self.assertIn(job, jobs, f"no job named {job}")
        out = {}
        for m in re.finditer(r"^\s+([A-Z][A-Z0-9_]*):\s*(\S.*)$", jobs[job], re.M):
            name, expr = m.group(1), m.group(2).strip()
            if not expr.startswith("${{"):
                out[name] = expr
                continue
            inner = expr[3:-2].strip() if expr.endswith("}}") else expr[3:].strip()
            if inner.startswith("needs."):
                _, jb, _, key = inner.split(".", 3)
                out[name] = (needs or {}).get(jb, {}).get(key, "")
            elif inner.startswith("secrets."):
                out[name] = "stub-secret"
            elif inner.startswith("vars."):
                out[name] = ""
            elif inner == "github.token":
                out[name] = "ghs_simulated_actions_token"
            else:
                out[name] = ""
        return out

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
        """The version of this test in iteration 2 asserted nothing.

        It supplied no REPO and checked no return code, so `logic:submit` exited on its second
        line at `REPO="${REPO:?}"` and the test passed having exercised none of the relay. A
        test that passes because its subject quit immediately is worse than no test: it reports
        coverage that does not exist. The fix is a POSITIVE checkpoint — a marker only
        reachable after entry validation has consumed every value — not a longer list of
        strings that must be absent.
        """
        p, sb = self.produced_context()
        produced = json.loads(p.read_text())
        u = sb.root / "canned-user"
        u.write_text("vibe-bot\n")
        block = extract(WF, "logic", "submit")
        self.assertIsNotNone(block, "no logic:submit block to compose against")
        # REPO arrives the way the workflow declares it: needs.reserve.outputs.repo, which is
        # the repository gates derived. Job wiring, evaluated from the YAML — not a value
        # written into a dict here.
        env = self.job_env("submit", needs={"reserve": {"repo": produced["repo"]}})
        env.update({"CONTEXT_FILE": str(p), "PAT_SECRET": "stub-pat",
                    "GH_CANNED_API_USER": str(u),
                    "TARGET_DIR": str(sb.root / "_target"),
                    "PATCH_DIR": str(sb.root / "_patches")})
        r = sb.run(block, env=env)
        out = r.stdout + r.stderr

        for name in ("relay-missing", "audited-sha-unresolvable", "default-branch-unresolvable",
                     "author-identity-unresolvable", "patch-cap-unresolvable",
                     "issue-unresolvable", "fork-slug-unresolvable"):
            self.assertNotIn(
                f"REFUSE:context-{name}", out,
                f"the consumer refused '{name}' against a relay the real derivation produced. "
                f"The producer and the consumer disagree about the relay's shape, and every "
                f"hand-written context.json in the suite hides it.")
        self.assertNotIn("REFUSE:pat-identity-unresolvable", out)
        # The checkpoint. `manifest-missing` is raised AFTER the whole context has been read
        # and the PAT identity proven, so reaching it is proof the produced relay satisfied
        # entry validation end to end. Nothing in this sandbox supplies a manifest, so this is
        # exactly where a fully-consumed relay is expected to stop.
        self.assertIn(
            "REFUSE:manifest-missing", out,
            f"submit did not reach the manifest check, so it never finished consuming the "
            f"relay. If it exited earlier the entry validation rejected something the real "
            f"derivation produced.\n--- output ---\n{out[-600:]}")


class TestAnEarlyRefusalIsStillReported(TriggerBase):
    """F1's residue: the reporting path must not depend on the step that failed.

    `derive-context` wrote DECISION and OUTCOME_DIR to $GITHUB_ENV at its END, after every
    value that can refuse. So on exactly the runs that need reporting, the always-publisher
    found neither: it wrote `./outcome-gates.json` instead of into the outcome directory, read
    a `decision.json` that did not exist, and therefore reported `status=error` with an empty
    reason — while the block had printed a perfectly good named refusal to stderr. The upload
    step's `path: ${{ env.OUTCOME_DIR }}/...` resolved to `/outcome-gates.json` and found
    nothing to upload.

    The named refusal existed and reached nobody, which is the same shape as the finalize half
    closed in iteration 2: the job that reports the failure was disabled by the failure.
    """

    def refuse_then_publish(self, sb=None):
        """Refuse in derive-context, then run the publisher over the same sandbox."""
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        env = {k: self._eval(v, {"number": 4242, "labels": []}, {},
                             {"AUDITOR_AUTHOR_NAME": "n", "AUDITOR_AUTHOR_EMAIL": "e",
                              "AUDITOR_FORK_OWNER": "vibe-bot", "WEEKLY_CAP": "2"})
               for k, v in self.step_env().items()}
        env["FIXTURE"] = ""
        env["GITHUB_ENV"] = str(sb.root / "gh.env")
        env.update(self.canned(sb, login=None, default_branch="main"))
        first = sb.run(self.block(), env=env)
        self.assertNotEqual(0, first.returncode, "the setup did not actually refuse")

        # The publisher runs `if: always()` in the same job, so it sees what the refusing step
        # exported to $GITHUB_ENV and nothing else.
        exported = {}
        gh_env = sb.root / "gh.env"
        if gh_env.exists():
            for line in gh_env.read_text().splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    exported[k] = v
        pub = extract(WF, "logic", "publish-gates") or _publisher_block()
        self.assertIsNotNone(pub, "no gates publisher block to run")
        return first, sb.run(pub, env=exported), sb, exported

    def test_the_publisher_receives_the_paths_it_needs(self):
        _, _, _, exported = self.refuse_then_publish()
        for name in ("DECISION", "OUTCOME_DIR"):
            self.assertIn(
                name, exported,
                f"{name} was never exported, because the refusal happened first. The "
                f"publisher then writes to '.' and the upload path resolves to '/…', so the "
                f"named refusal reaches nobody.")

    def test_the_published_outcome_names_the_value_that_could_not_resolve(self):
        _, pub, sb, exported = self.refuse_then_publish()
        out = Path(exported["OUTCOME_DIR"]) / "outcome-gates.json"
        self.assertTrue(out.is_file(),
                        f"the publisher wrote no outcome file into {exported['OUTCOME_DIR']}")
        doc = json.loads(out.read_text())
        self.assertNotEqual(
            "", doc.get("reason", ""),
            "the outcome carries no reason, so the run reports that something broke without "
            "saying which value was unresolvable — the refusal was named and then discarded")
        self.assertIn("repo", doc["reason"],
                      f"the reason does not name the unresolvable value: {doc}")

    def test_the_upload_path_does_not_depend_on_the_step_that_can_refuse(self):
        gates = _job_bodies(WF.read_text(encoding="utf-8"))["gates"]
        # Comment lines may sit between the two keys; match past them rather than assuming
        # they are adjacent.
        m = re.search(r"name: outcome-gates\s*\n(?:\s*#[^\n]*\n)*\s*path:\s*(\S.*)$",
                      gates, re.M)
        self.assertIsNotNone(m, "no outcome-gates upload step")
        self.assertNotIn(
            "env.OUTCOME_DIR", m.group(1),
            "the upload path reads env.OUTCOME_DIR, which the refusing step is the one that "
            "sets — so on a refusal it resolves to '/outcome-gates.json' and uploads nothing. "
            "Use a literal workspace path.")


def _publisher_block():
    """The gates `publish the gates outcome` step body, dedented."""
    text = WF.read_text(encoding="utf-8")
    m = re.search(r"- name: publish the gates outcome\s*\n\s*if: always\(\)\s*\n\s*run: \|\s*\n"
                  r"((?:\s+[^\n]*\n)+?)(?=\s*- )", text)
    if not m:
        return None
    lines = m.group(1).split("\n")
    indent = min((len(l) - len(l.lstrip())) for l in lines if l.strip())
    return "\n".join(l[indent:] if len(l) >= indent else l for l in lines)


def _steps(job_body):
    """Split a job body into (text before/around the steps list, [one text per step]).

    Step items sit at the 6-space list indent under `steps:`. A 4-space key after the list
    ends it. Everything outside the list (the job's own `env:`, `needs:`, …) is job-level.
    """
    pre, steps, cur, in_steps = [], [], None, False
    for ln in job_body.split("\n"):
        if re.match(r"^    steps:\s*$", ln):
            in_steps = True
            pre.append(ln)
            continue
        if in_steps and re.match(r"^    \S", ln):
            in_steps = False
            if cur is not None:
                steps.append("\n".join(cur))
                cur = None
        if in_steps and re.match(r"^      - ", ln):
            if cur is not None:
                steps.append("\n".join(cur))
            cur = [ln]
            continue
        if cur is not None:
            cur.append(ln)
        else:
            pre.append(ln)
    if cur is not None:
        steps.append("\n".join(cur))
    return "\n".join(pre), steps


def _shell_views(code):
    """Two views of a step's code, honest about SHELL STRING semantics (#165 4-body).

    reads view  — what the shell EXPANDS: double-quoted content, command
                  substitutions, and unquoted-delimiter heredoc bodies
                  interpolate, so reads there are real; single-quoted content
                  and quoted-delimiter heredoc bodies are inert data and are
                  masked; an escaped `\\$` is not a read.
    assigns view — where an assignment can BIND this shell: only bare, top-level
                  code. Content of any string or heredoc body is masked
                  (`msg="X=1; Y=2"` credits nothing), and so is everything
                  inside `$( … )` — a subshell assignment never binds the
                  parent. Quote contexts NEST inside substitutions, tracked on
                  a stack, so `"$(cd "$(dirname "$X")" )"` stays one value.

    Masking uses `_` (never spaces) so token boundaries survive — the
    env-prefix judgement below skips a masked value as one word. Line count is
    preserved in both views.
    """
    reads, assigns = [], []
    stack = []            # enclosing modes; len(stack) > 0 means inside $( )
    mode = "normal"       # current: normal / single / double
    pending = []          # heredoc delimiters queued on this line: (delim, quoted)
    in_heredoc = None
    i, n = 0, len(code)

    def emit(r, a):
        reads.append(r)
        assigns.append(a)

    def depth():
        return sum(1 for m in stack if m == "$(")

    while i < n:
        ch = code[i]
        if in_heredoc is not None:
            j = code.find("\n", i)
            line = code[i:j if j >= 0 else n]
            if line.strip() == in_heredoc[0]:
                emit(line, line)
                in_heredoc = None
            else:
                masked = "".join("_" if c != "\n" else c for c in line)
                emit(masked if in_heredoc[1] else line, masked)
            if j < 0:
                break
            emit("\n", "\n")
            i = j + 1
            continue
        sub = depth() > 0
        if ch == "\n":
            emit("\n", "\n")
            if mode == "normal" and not stack and pending:
                in_heredoc = pending.pop(0)
            i += 1
            continue
        if mode == "single":
            if ch == "'":
                mode = "normal"          # single only ever opens from normal
                emit(ch, ch if not sub else "_")
            else:
                emit("_", "_")
            i += 1
            continue
        if mode == "double":
            if ch == "\\" and i + 1 < n:
                nxt = code[i + 1]
                emit("__" if nxt == "$" else "\\" + nxt, "__")
                i += 2
                continue
            if code[i:i + 2] == "$(":
                stack.append("double")
                stack.append("$(")
                mode = "normal"
                emit("$(", "__")
                i += 2
                continue
            if ch == '"':
                mode = "normal"
                emit(ch, ch if not sub else "_")
            else:
                emit(ch, ch if ch == "\n" else "_")
            i += 1
            continue
        # mode == "normal"
        if ch == "\\" and i + 1 < n:
            nxt = code[i + 1]
            emit("__" if nxt == "$" else "\\" + nxt,
                 ("\\" + nxt) if not sub else "__")
            i += 2
            continue
        if code[i:i + 2] == "$(":
            stack.append("normal")
            stack.append("$(")
            emit("$(", "__")
            i += 2
            continue
        if ch == ")" and stack:
            assert stack[-1] == "$(" or "$(" in stack
            # Pop back to the state that opened this substitution.
            while stack and stack[-1] != "$(":
                stack.pop()
            if stack:
                stack.pop()            # the "$(" marker
                mode = stack.pop() if stack and stack[-1] in ("normal",
                                                              "double") else "normal"
            emit(ch, ch if depth() == 0 and mode == "normal" else "_")
            i += 1
            continue
        if ch == "'":
            mode = "single"
            emit(ch, ch if not sub else "_")
            i += 1
            continue
        if ch == '"':
            mode = "double"
            emit(ch, ch if not sub else "_")
            i += 1
            continue
        if (not sub and ch == "<" and code[i:i + 2] == "<<"
                and code[i:i + 3] != "<<<"):
            j = i + 2
            if j < n and code[j] == "-":
                j += 1
            while j < n and code[j] in " \t":
                j += 1
            if j < n and code[j] in "'\"":
                quote = code[j]
                k = code.find(quote, j + 1)
                if k > j:
                    pending.append((code[j + 1:k], True))
                    emit(code[i:k + 1], code[i:k + 1])
                    i = k + 1
                    continue
            m = re.match(r"[A-Za-z0-9_]+", code[j:])
            if m:
                pending.append((m.group(0), False))
                emit(code[i:j + m.end()], code[i:j + m.end()])
                i = j + m.end()
                continue
            emit(ch, ch)
            i += 1
            continue
        emit(ch, ch if not sub else "_")
        i += 1
    return "".join(reads), "".join(assigns)


def _crediting_assignments(assign_line, assign_re):
    """Names a line's assignments bind FOR THE LINES BELOW.

    An env-prefix assignment (`X=1 cmd …`) scopes to its own command — the
    command's argv is expanded from the PRIOR environment, so the prefix
    credits nothing here: not later lines, not even the same line's reads.
    A plain assignment (nothing but assignments, separators, redirects or a
    comment after it) credits everything below, as before.
    """
    names = []
    for m in assign_re.finditer(assign_line):
        rest = assign_line[m.end():]
        # Skip this assignment's value (one word, ending at whitespace OR a
        # separator; masked strings are `_` runs), then any further NAME=value
        # words — a prefix can stack.
        rest = re.sub(r"^[^\s;|&<>#]*", "", rest)
        while True:
            nxt = re.match(r"\s+(?:export\s+|local\s+)?[A-Z][A-Z0-9_]*=[^\s;|&<>#]*",
                           rest)
            if not nxt:
                break
            rest = rest[nxt.end():]
        rest = rest.strip()
        if rest and not rest.startswith((";", "&&", "||", "|", "#", ">", "<", "&", ")")):
            continue          # env-prefix: credits only its own command
        names.append(m.group(1))
    return names


def _unbound_names(job_body, runtime=frozenset(), optional=frozenset()):
    """Names a job's steps read that nothing available AT THAT POINT binds.

    Availability is scoped per step, in order: the runtime set, the job-level `env:`, the
    step's own `env:`, names EXPORTED to $GITHUB_ENV by an EARLIER step, and names assigned
    inside the step's own block. A binding that only exists in a LATER step does not satisfy
    an earlier read — that is the ordering the round-3 scan aggregated away.

    A read needs a binding when it has no default (`$X`, `${X}`), an explicitly empty default
    (`${X:-}`), or is required (`${X:?}`). The bare unbraced form is a read like any other;
    the round-3 scan did not match it, so a name read only as `$X` escaped entirely. A read
    with a NON-EMPTY default (`${DATA_DIR:-_data}`) is self-sufficient and is not flagged.

    String semantics (#165 4-body): reads are taken from the view the shell would EXPAND —
    double-quoted content, command substitutions, and unquoted-delimiter heredoc bodies are
    real; single-quoted content and quoted-delimiter heredoc bodies are inert data.
    Assignments exist only in bare top-level code: string content never credits, a subshell
    assignment never binds the parent, and an env-prefix (`X=1 cmd`) credits only its own
    command — not later lines, and not its own line's reads, which the shell expands from
    the PRIOR environment.

    Two boundaries are DELIBERATE exclusions, recorded rather than half-modelled:
    (c) branch reachability — the scan is straight-line lexical, so an assignment inside an
    untaken branch credits; refusing conditionals would reject legitimate workflows the
    runtime executes correctly, and E8.7's live matrix is the reachability oracle.
    (d) lowercase names are outside the scanned space — uppercase-is-configuration is the
    house convention this scan enforces.
    """
    def code_of(text):
        return "\n".join(l for l in text.split("\n") if not l.lstrip().startswith("#"))

    def needs(code):
        return (set(re.findall(r"\$\{([A-Z][A-Z0-9_]*):\?[^}]*\}", code))
                | set(re.findall(r"\$\{([A-Z][A-Z0-9_]*):-\}", code))
                | set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)\}", code))
                | set(re.findall(r"\$(?!\{)([A-Z][A-Z0-9_]*)", code)))

    def env_bound(text, indent=8):
        return set(re.findall(r"^\s{%d,}([A-Z][A-Z0-9_]*):\s*\S" % indent, text, re.M))

    # An assignment is a command in command position — the start of a line, or right after a
    # separator (`;`, `&&`, `||`) or a control keyword (`then`, `else`, `do`), optionally
    # exported — never a NAME= token inside printf/echo arguments: `echo FOO=bar` binds
    # nothing. Its credit begins on the NEXT line, so an empty self-default (`X="${X:-}"`)
    # cannot excuse the read on its own right-hand side. Both over-credits were how LABELS
    # sat unbound in the security-blocked gate while the round-4 scan passed.
    assign_re = re.compile(
        r"(?:^\s*|;\s*|&&\s*|\|\|\s*|\b(?:then|else|do)\s+)"
        r"(?:export\s+|local\s+)?([A-Z][A-Z0-9_]*)=")

    pre, steps = _steps(job_body)
    # Job-level `env:` entries sit at the 6-space indent; step-level ones at 10.
    job_env = env_bound(pre, indent=6)
    offenders, exported_by_earlier = [], set()
    for step in steps:
        code = code_of(step)
        # #165 4-body: reads come from the view the shell would EXPAND;
        # assignments only from bare code (string content never credits), and
        # an env-prefix assignment credits nothing beyond its own command.
        reads_code, assigns_code = _shell_views(code)
        base = (set(runtime) | set(optional) | job_env | env_bound(step)
                | exported_by_earlier)
        assigned_above, flagged = set(), set()
        for read_line, assign_line in zip(reads_code.split("\n"),
                                          assigns_code.split("\n")):
            for name in sorted(needs(read_line) - base - assigned_above - flagged):
                offenders.append(name)
                flagged.add(name)
            assigned_above.update(_crediting_assignments(assign_line, assign_re))
        exported_by_earlier |= set(re.findall(r'echo "([A-Z][A-Z0-9_]*)=', code))
    return offenders


class TestEveryJobBindsWhatItReads(unittest.TestCase):
    """The general form of finding 1, applied to every job rather than to one step.

    F1 was: a block reads a name, no step binds it, so on a real run it is empty and the job
    refuses — while a suite that supplies the name by hand stays green. That is not a property
    of `derive-context`; it is a property of every block in the file, and checking it in one
    place was how the same defect sat in four other jobs unnoticed.

    Reading it off the WORKFLOW rather than off the tests is what makes it load-bearing: it
    fails on the production defect directly, instead of inferring it from test hygiene. The
    lexical scan in test_auditor_no_supplied_derivations.py is the backstop, not the guarantee.

    F10, round 4: the scan itself is now `_unbound_names` above, and it is stricter in the
    two ways the review showed it could certify an unbound consumer — it matches the bare
    unbraced read (`$X`), which the round-3 regexes never saw, and it scopes availability by
    step and order, where round 3 pooled every binding and assignment in the job so a name
    assigned in step 5 excused a read in step 3. `TestTheBindingScanItselfCatches` below runs
    the scan against synthetic jobs that hold each defect, so a regression here fails a test
    rather than quietly narrowing the guarantee.
    """

    #: Provided by the Actions runner, or by the harness that executes a block.
    RUNTIME = {"GITHUB_WORKSPACE", "GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_RUN_ID",
               "GITHUB_RUN_NUMBER", "GITHUB_REPOSITORY", "PWD", "PATH", "HOME", "CI",
               "RUNNER_TEMP", "FIXTURE"}

    #: Names that are genuinely optional, each with the reason. Not a list of jobs -- the same
    #: discipline the derived-value scan's exemptions carry, for the same reason.
    OPTIONAL = {
        "GH_TOKEN_HTTPS": "an ALTERNATIVE inside ${PAT_SECRET:-${GH_TOKEN_HTTPS:-}}; the "
                          "primary is bound, so this being unset is the normal case",
        "GH_TOKEN": "the second rung of ${PAT_SECRET:-${GH_TOKEN:-}}, whose empty case is a "
                    "real branch: `reserve` checks out auditor-data WITHOUT "
                    "persist-credentials:false, so git already holds a credential and the "
                    "explicit helper is only needed when a PAT overrides it. Checked rather "
                    "than assumed -- gates passes persist-credentials:false and reserve does "
                    "not, and that difference is what makes this a fallback and not a gap.",
        "OUTCOME_JOB": "a harness seam: production reaches it only when no outcome artifact "
                       "carries a status, where empty is the correct reading. Production code "
                       "reading a test-only override is a wart worth filing, not silencing.",
        "OUTCOME_STATUS": "the status half of the same harness seam as OUTCOME_JOB; empty is "
                          "the correct production reading and the default covers it",
        "OUTCOME_REASON": "the reason half of the same harness seam as OUTCOME_JOB; empty is "
                          "the correct production reading and the default covers it",
        "GIT_AUTH_TOKEN": "expanded only inside git's single-quoted credential-helper string, "
                          "which runs in a subshell under an explicit GIT_AUTH_TOKEN=… env "
                          "prefix on the same git command — a deferred read the invoking "
                          "step never performs itself",
        "FORK_REMOTE": "a harness seam: tests point it at a local bare remote; production "
                       "leaves it empty and the submit block derives "
                       "https://github.com/$FORK_SLUG.git before first use",
        "PR_NUMBER": "a harness seam (test_auditor_state_machine drives outcome rows with "
                     "it); production takes pr_number from the create/recovery paths and "
                     "the empty env fallback is the correct no-PR reading",
        # DECISION needs no exemption since F10.b: finalize's route step binds it to the
        # decision document downloaded in the gate-context artifact, and gates steps get it
        # from derive-context's $GITHUB_ENV export. The old exemption claimed production
        # label routing survived without the document; the round-2 review showed it did not.
    }

    @classmethod
    def setUpClass(cls):
        cls.jobs = _job_bodies(WF.read_text(encoding="utf-8"))

    def test_every_job_binds_or_produces_every_name_its_blocks_require(self):
        offenders = []
        for job, body in self.jobs.items():
            if job == "issues":  # the `on:` trigger block, not a job
                continue
            for name in _unbound_names(body, self.RUNTIME, set(self.OPTIONAL)):
                offenders.append(f"{job}: {name}")
        self.assertEqual(
            [], offenders,
            "a step reads a name nothing available at that point binds, exports or assigns, "
            "so on a real run it is empty — the shape of finding 1, and of finding 9 before "
            "it:\n  " + "\n  ".join(offenders))

    def test_the_optional_list_stays_a_list_of_names_with_reasons(self):
        for name, reason in self.OPTIONAL.items():
            self.assertGreaterEqual(
                len(reason), 40,
                f"{name} is treated as optional without a reason anyone can check")

    def test_the_scan_still_sees_every_job(self):
        found = {j for j in self.jobs if j != "issues"}
        for expected in ("gates", "reserve", "propose", "submit", "finalize"):
            self.assertIn(expected, found,
                          f"the job scan lost {expected}; it is now checking less than the "
                          f"whole workflow and would pass regardless")


class TestTheBindingScanItselfCatches(unittest.TestCase):
    """Mutation anchors for `_unbound_names` — each defect the round-4 rework exists to see.

    The round-3 scan passed both synthetic jobs below. If a later edit relaxes the scan, the
    guarantee narrows silently and every suite that leans on it keeps passing; these fail
    instead.
    """

    def _job(self, *steps, pre=""):
        body = "  job:\n" + (pre + "\n" if pre else "") + "    steps:\n"
        for s in steps:
            body += "      - run: |\n"
            for line in s.split("\n"):
                body += "          " + line + "\n"
        return body

    def test_a_bare_unbraced_read_is_a_read(self):
        job = self._job('echo "$MYSTERY_VALUE"')
        self.assertIn("MYSTERY_VALUE", _unbound_names(job),
                      "a name read only as bare $X escaped the scan; the round-3 regexes "
                      "matched braces only and this is the regression back to that")

    def test_a_later_assignment_does_not_excuse_an_earlier_read(self):
        job = self._job('echo "${LATE_VALUE}"', "LATE_VALUE=set-too-late")
        self.assertIn("LATE_VALUE", _unbound_names(job),
                      "a name assigned only in a LATER step excused a read in an earlier "
                      "one; the scan is pooling bindings across the job again")

    def test_an_earlier_export_satisfies_a_later_read(self):
        job = self._job('EARLY_VALUE=x\necho "EARLY_VALUE=$EARLY_VALUE" >> "$GITHUB_ENV"',
                        'echo "${EARLY_VALUE}"')
        self.assertEqual([], _unbound_names(job, runtime={"GITHUB_ENV"}),
                         "an export to $GITHUB_ENV from an earlier step is how jobs hand "
                         "values forward; flagging it makes the scan unusable")

    def test_a_same_step_assignment_satisfies_its_own_read(self):
        job = self._job('LOCAL_VALUE=1\necho "$LOCAL_VALUE"')
        self.assertEqual([], _unbound_names(job))

    def test_a_self_default_does_not_excuse_its_own_read(self):
        # X="${X:-}" ASSIGNS X and READS it on the same line, and the read is the step
        # expecting the name from outside. Whole-step assignment credit excused it — which is
        # how LABELS sat unbound in the security-blocked gate while the scan passed, and the
        # label could never block a real run.
        job = self._job('SELF_DEFAULTED="${SELF_DEFAULTED:-}"\necho "$SELF_DEFAULTED"')
        self.assertIn("SELF_DEFAULTED", _unbound_names(job),
                      "an empty self-default excused its own RHS read; the step still gets "
                      "the name from nobody and the scan certifies it anyway")

    def test_a_literal_name_equals_token_is_not_an_assignment(self):
        # `echo FOO=bar` prints a token; it binds nothing. The unanchored assignment regex
        # credited it and the read below stayed green unbound.
        job = self._job('echo FOO=bar\necho "$FOO"')
        self.assertIn("FOO", _unbound_names(job),
                      "a printed NAME= token was credited as an assignment")

    def test_an_assignment_still_credits_only_the_lines_below_it(self):
        # The line ABOVE a real assignment reads nothing yet.
        job = self._job('echo "$ORDERED_VALUE"\nORDERED_VALUE=now')
        self.assertIn("ORDERED_VALUE", _unbound_names(job))

    def test_an_assignment_in_command_position_after_a_keyword_credits(self):
        # `if …; then X=5; else X=3; fi` assigns on every path; anchoring assignments to the
        # line start alone would flag the read below — the PATCH_CAP shape.
        job = self._job('if true; then CTRL_VALUE=5; else CTRL_VALUE=3; fi\n'
                        'echo "$CTRL_VALUE"')
        self.assertEqual([], _unbound_names(job))

    def test_a_step_env_binding_satisfies_that_step(self):
        body = ("  job:\n    steps:\n      - env:\n          BOUND_VALUE: yes\n"
                "        run: |\n          echo \"$BOUND_VALUE\"\n")
        self.assertEqual([], _unbound_names(body))

    # -- #165 4-body: string semantics and env-prefix scoping ---------------

    def test_a_single_quoted_read_is_inert_data(self):
        job = self._job("echo '$QUOTED_NAME'")
        self.assertEqual([], _unbound_names(job),
                         "single-quoted content is data the shell never expands")

    def test_a_double_quoted_read_is_a_real_read(self):
        job = self._job('echo "prefix ${DQ_READ} suffix"')
        self.assertIn("DQ_READ", _unbound_names(job),
                      "the shell expands inside double quotes; masking them "
                      "would hide real reads")

    def test_a_string_content_assignment_never_credits(self):
        job = self._job('msg="INNER_VALUE=x; OTHER_VALUE=y"\n'
                        'echo "$INNER_VALUE"')
        self.assertIn("INNER_VALUE", _unbound_names(job),
                      "an assignment-shaped substring inside a string binds "
                      "nothing; crediting it certifies an unbound read")

    def test_an_unquoted_delimiter_heredoc_body_reads_for_real(self):
        job = self._job("cat <<EOF\n${HD_READ}\nEOF")
        self.assertIn("HD_READ", _unbound_names(job),
                      "an unquoted-delimiter heredoc interpolates; its reads "
                      "are real")

    def test_a_quoted_delimiter_heredoc_body_is_inert(self):
        job = self._job("cat <<'EOF'\n${HD_INERT}\nEOF")
        self.assertEqual([], _unbound_names(job),
                         "a quoted-delimiter heredoc body is literal data")

    def test_a_heredoc_body_assignment_never_credits(self):
        job = self._job('cat <<EOF\nHD_ASSIGN=x\nEOF\necho "$HD_ASSIGN"')
        self.assertIn("HD_ASSIGN", _unbound_names(job),
                      "text inside a heredoc body is written to stdin, not "
                      "executed")

    def test_an_env_prefix_assignment_credits_only_its_command(self):
        job = self._job('TMP_VALUE=1 mycmd\necho "$TMP_VALUE"')
        self.assertIn("TMP_VALUE", _unbound_names(job),
                      "X=1 cmd scopes the binding to cmd's environment; the "
                      "step-wide credit was how a temporary excused a later "
                      "unbound read")

    def test_an_env_prefix_does_not_excuse_its_own_line_read(self):
        # `X=1 cmd "$X"`: the argv is expanded from the PRIOR environment,
        # before the prefix applies — the read needs an earlier binding.
        job = self._job('PRE_VALUE=1 mycmd "$PRE_VALUE"')
        self.assertIn("PRE_VALUE", _unbound_names(job))

    def test_a_subshell_assignment_does_not_bind_the_parent(self):
        job = self._job('OUT="$(SUB_VALUE=1; echo x)"\necho "$SUB_VALUE"')
        self.assertIn("SUB_VALUE", _unbound_names(job),
                      "a $( ) assignment lives and dies in the subshell")

    def test_a_lowercase_name_is_outside_the_scanned_space(self):
        # RECORDED exclusion (d) — uppercase-is-configuration is the house
        # convention the scan enforces; see the _unbound_names docstring.
        job = self._job('echo "$lower_value"')
        self.assertEqual([], _unbound_names(job))


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
