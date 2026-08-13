# SPDX-License-Identifier: ISC
"""E8.2 contribution-gate behavior (vibe-59): every scriptable gate, positive + negative.

Gates live in `# gate:<name>` ... `# /gate` blocks inside auditor-contribute.yml's propose job;
the harness extracts and executes each with fixture inputs. This IS the "gate logic unit-tested
where scriptable" acceptance clause (the exhaustive combination matrix stays with E8.7).
"""
import json
import shutil
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract, FIX

WF = Path(__file__).resolve().parent.parent / "auditor" / "workflows" / "auditor-contribute.yml"

GATES = ["security-blocked", "no-external-prs", "cla", "pushback", "confidence",
         "duplicate-pr", "pr-caps", "disclosure-routing", "umbrella-backstop"]


class GateBase(unittest.TestCase):
    name = None

    def block(self):
        self.assertTrue(WF.is_file(), f"{WF} missing")
        b = extract(WF, "gate", self.name)
        self.assertIsNotNone(b, f"no gate block '{self.name}'")
        return b

    def run_gate(self, env, registry="registry.json"):
        sb = Sandbox(registry=registry)
        try:
            # CODE_DIR is the code checkout root: gate:disclosure-routing sources
            # auditor/scripts/compute-fingerprint.sh from it to key each disclosed finding.
            # The sandbox's own `code` dir is empty, so it must point at the real tree. This
            # is a PATH, not a derived value -- the block still computes the fingerprints.
            base = {"REPO": "acme/claude-toolkit", "OWNER": "acme",
                    "CODE_DIR": str(WF.parent.parent.parent),
                    "SIDECAR": str(FIX / "findings-sidecar.jsonl")}
            base.update(env)
            r = sb.run(self.block(), env=base)
            return r, sb.gh_calls(), sb
        finally:
            pass  # caller cleans via sb


# The security-blocked gate's tests moved to
# tests/test_auditor_context.py::TestSecurityGateReadsLiveLabels (F10.a, round 2). The gate
# now derives LABELS from the tracking issue through the API, which needs derive-context's
# real $GITHUB_ENV exports — a production-shaped harness this file's direct-block runner
# does not provide, and supplying LABELS through the environment is an injected derivation
# the no-supplied-derivations scan forbids.


class TestNoExternalPRs(GateBase):
    name = "no-external-prs"

    def test_denied_owner_skips_with_reason(self):
        r, _, sb = self.run_gate({"OWNER": "anthropics"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("SKIP:no-external-prs", r.stdout)
        sb.cleanup()

    def test_other_owner_passes(self):
        r, _, sb = self.run_gate({"OWNER": "acme"})
        self.assertIn("PASS", r.stdout)
        sb.cleanup()


class TestCla(GateBase):
    name = "cla"

    def relay(self, author=None):
        """A context.json, the way production delivers the author identity to this gate.

        These tests used to set AUTHOR_NAME/AUTHOR_EMAIL directly in the environment. F3 moved
        the gate to read them from the relay, so the env injection was handing the gate an
        answer it is contracted to look up -- and the derived-value scan could not see it,
        because the scan only watched the producer-side names (F10).
        """
        import tempfile
        d = tempfile.mkdtemp(prefix="auditor-cla-")
        self.addCleanup(shutil.rmtree, d, True)
        ctx = {"version": 1, "repo": "acme/claude-toolkit", "issue": "42",
               "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
               "base_branch": "main", "weekly_cap": 2, "patch_cap": 3}
        if author:
            ctx["author_name"], ctx["author_email"] = author
        p = Path(d) / "context.json"
        p.write_text(json.dumps(ctx))
        return str(p)

    def test_cla_org_without_attestation_skips_with_template(self):
        r, _, sb = self.run_gate({"OWNER": "google", "CLA_SIGNED": "",
                                  "CONTEXT_FILE": self.relay(author=None)})
        self.assertEqual(r.returncode, 0)
        self.assertIn("SKIP:cla", r.stdout)
        self.assertIn("cla-gate-messages", r.stdout)
        sb.cleanup()

    def test_attested_cla_org_passes(self):
        r, _, sb = self.run_gate({
            "OWNER": "google", "CLA_SIGNED": "true",
            "CONTEXT_FILE": self.relay(author=("Jane Dev", "jane@example.com"))})
        self.assertIn("PASS", r.stdout)
        sb.cleanup()

    def test_non_cla_org_passes(self):
        r, _, sb = self.run_gate({"OWNER": "acme"})
        self.assertIn("PASS", r.stdout)
        sb.cleanup()


class TestPushback(GateBase):
    name = "pushback"

    def _log_with(self, sb, event):
        p = sb.data / "ledgers" / "disagreements.jsonl"
        p.write_text(json.dumps(event) + "\n")

    def test_prior_rejection_gates(self):
        r, _, sb = self.run_gate({})
        sb.cleanup()
        sb2 = Sandbox()
        self._log_with(sb2, {"event": "maintainer_rejected", "repo": "acme/claude-toolkit",
                             "pr": 18, "dissent_type": "out_of_scope"})
        r = sb2.run(self.block(), env={"REPO": "acme/claude-toolkit"})
        self.assertEqual(r.returncode, 0)  # skip, not failure
        self.assertIn("SKIP:pushback", r.stdout)
        sb2.cleanup()

    def test_no_history_passes(self):
        r, _, sb = self.run_gate({})
        self.assertIn("PASS", r.stdout)
        sb.cleanup()

    def test_override_event_unlocks(self):
        sb = Sandbox()
        p = sb.data / "ledgers" / "disagreements.jsonl"
        p.write_text(
            json.dumps({"event": "maintainer_rejected", "repo": "acme/claude-toolkit",
                        "pr": 18}) + "\n" +
            json.dumps({"event": "gate_override", "repo": "acme/claude-toolkit", "pr": 18,
                        "justification": "maintainer invited us back"}) + "\n")
        r = sb.run(self.block(), env={"REPO": "acme/claude-toolkit"})
        self.assertIn("PASS", r.stdout)
        sb.cleanup()


class TestConfidence(GateBase):
    name = "confidence"

    def test_only_high_pass_and_missing_is_dropped(self):
        r, _, sb = self.run_gate({})
        self.assertEqual(r.returncode, 0)
        kept = [l for l in r.stdout.splitlines() if l.startswith("KEEP:")]
        self.assertEqual(len(kept), 3)  # 3 of 4 fixture findings are confidence high
        sb.cleanup()

    def test_zero_high_skips_before_any_model_cost(self):
        sb = Sandbox()
        low = sb.root / "low.jsonl"
        low.write_text('{"rule_id":"R07","confidence":"medium","file":"a.md","severity":"low","category":"nl_quality"}\n')
        r = sb.run(self.block(), env={"REPO": "acme/claude-toolkit", "SIDECAR": str(low)})
        self.assertEqual(r.returncode, 0)
        self.assertIn("SKIP:no-high-confidence", r.stdout)
        sb.cleanup()


class TestDuplicatePR(GateBase):
    name = "duplicate-pr"

    def test_file_overlap_drops_finding(self):
        r, _, sb = self.run_gate({"OPEN_PRS_FILE": str(FIX / "open-prs.json")})
        self.assertEqual(r.returncode, 0)
        self.assertIn("DROP:", r.stdout)  # commands/deploy.md overlaps open PR 44
        sb.cleanup()

    def test_an_unavailable_list_refuses_instead_of_failing_open(self):
        """This test previously asserted the opposite, and that was the defect.

        `OPEN_PRS_FILE` was bound nowhere in the workflow, so on every real run the gate took
        this branch and the duplicate filter did nothing at all -- while a test named
        `test_api_error_fails_open` certified the behaviour as intended. Fail-open here means
        opening a second pull request against a file an open PR already touches, on somebody
        else's repository. The list being unavailable is a reason to stop, not to proceed
        blind. Step-8 finding 9.
        """
        r, _, sb = self.run_gate({"OPEN_PRS_FILE": "/nonexistent/prs.json"})
        self.assertNotEqual(r.returncode, 0,
                            "an unreadable open-PR list passed the gate; duplicates ship")
        self.assertIn("REFUSE:open-prs-unavailable", r.stdout + r.stderr)
        sb.cleanup()

    def test_an_empty_list_is_a_real_answer_and_drops_nothing(self):
        # Distinct from unavailable: the target genuinely has no open PRs, so nothing is a
        # duplicate. Conflating the two is what made the failure mode invisible.
        sb0 = Sandbox()
        empty = sb0.root / "empty-prs.json"
        empty.write_text("[]")
        r, _, sb = self.run_gate({"OPEN_PRS_FILE": str(empty)})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("DROP:", r.stdout)
        self.assertIn("PASS", r.stdout)
        sb.cleanup()
        sb0.cleanup()


class TestTheOpenPrListIsActuallyProduced(unittest.TestCase):
    """F9's headline: the filter's input was never created.

    Both `gate:duplicate-pr` and `emit-manifest` read OPEN_PRS_FILE, and no step in the
    workflow ever set it. Both therefore took their documented fail-open branch on every
    single run, permanently. A filter whose input is never bound is not a lenient filter --
    it is an absent one, and the gate ladder counted it as present.
    """

    def block(self):
        b = extract(WF, "stage-logic", "open-prs")
        self.assertIsNotNone(
            b, "no `# stage-logic:open-prs` block. Something must FETCH the target's open "
               "pull requests and bind OPEN_PRS_FILE, or the duplicate filters are inert.")
        return b

    def _gh(self, sb, payload):
        f = sb.root / "canned-prs"
        f.write_text(payload)
        m = sb.root / "canned-map"
        m.write_text("pr list\t" + str(f) + "\n")
        return {"GH_CANNED_MAP": str(m)}

    def test_the_workflow_binds_open_prs_file(self):
        text = WF.read_text(encoding="utf-8")
        self.assertRegex(
            text, r"OPEN_PRS_FILE=\S",
            "OPEN_PRS_FILE is read but never assigned anywhere in the workflow")

    def test_a_successful_fetch_writes_the_list_and_exports_the_path(self):
        sb = Sandbox()
        env = {"REPO": "acme/claude-toolkit", "GITHUB_ENV": str(sb.root / "gh.env")}
        env.update(self._gh(sb, '[{"number":44,"files":[{"path":"commands/deploy.md"}]}]'))
        r = sb.run(self.block(), env=env)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        exported = (sb.root / "gh.env").read_text()
        self.assertIn("OPEN_PRS_FILE=", exported,
                      "the path was not exported to $GITHUB_ENV, so the later steps in this "
                      "job -- gate:duplicate-pr and emit-manifest -- still see nothing")
        path = [l.split("=", 1)[1] for l in exported.splitlines()
                if l.startswith("OPEN_PRS_FILE=")][0]
        self.assertEqual(44, json.loads(Path(path).read_text())[0]["number"])
        sb.cleanup()

    def test_an_empty_result_is_written_rather_than_treated_as_a_failure(self):
        sb = Sandbox()
        env = {"REPO": "acme/claude-toolkit", "GITHUB_ENV": str(sb.root / "gh.env")}
        env.update(self._gh(sb, "[]"))
        r = sb.run(self.block(), env=env)
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        path = [l.split("=", 1)[1] for l in (sb.root / "gh.env").read_text().splitlines()
                if l.startswith("OPEN_PRS_FILE=")][0]
        self.assertEqual([], json.loads(Path(path).read_text()))
        sb.cleanup()

    def test_a_transport_failure_refuses_rather_than_writing_an_empty_list(self):
        # The whole point of finding 9: a rate-limited or unauthenticated call must not read
        # as "this repo has no open PRs". Writing [] there is indistinguishable downstream
        # from a genuine empty answer, and every duplicate ships.
        sb = Sandbox()
        failing = sb.bin / "gh"
        failing.write_text("#!/usr/bin/env bash\necho 'HTTP 403: rate limit exceeded' >&2\nexit 1\n")
        failing.chmod(0o755)
        r = sb.run(self.block(), env={"REPO": "acme/claude-toolkit",
                                      "GITHUB_ENV": str(sb.root / "gh.env")})
        self.assertNotEqual(0, r.returncode,
                            "a failed API call was treated as success; the duplicate filter "
                            "would run against a fabricated empty list")
        self.assertIn("REFUSE:open-prs-unavailable", r.stdout + r.stderr)
        sb.cleanup()

    def test_unparseable_output_refuses_too(self):
        sb = Sandbox()
        env = {"REPO": "acme/claude-toolkit", "GITHUB_ENV": str(sb.root / "gh.env")}
        env.update(self._gh(sb, "<html>502 Bad Gateway</html>"))
        r = sb.run(self.block(), env=env)
        self.assertNotEqual(0, r.returncode)
        self.assertIn("REFUSE:open-prs-unavailable", r.stdout + r.stderr)
        sb.cleanup()


class TestPrCaps(GateBase):
    name = "pr-caps"

    def test_first_contact_caps_at_3(self):
        r, _, sb = self.run_gate({"FIRST_CONTACT": "true", "PLANNED_COUNT": "5",
                                  "WEEK_CONTACT_COUNT": "0"})
        self.assertIn("CAP:3", r.stdout)
        sb.cleanup()

    def test_repeat_contact_caps_at_5(self):
        r, _, sb = self.run_gate({"FIRST_CONTACT": "false", "PLANNED_COUNT": "9",
                                  "WEEK_CONTACT_COUNT": "0"})
        self.assertIn("CAP:5", r.stdout)
        sb.cleanup()

    def test_weekly_repo_cap_skips(self):
        r, _, sb = self.run_gate({"FIRST_CONTACT": "true", "PLANNED_COUNT": "2",
                                  "WEEK_CONTACT_COUNT": "2"})
        self.assertIn("SKIP:weekly-cap", r.stdout)
        sb.cleanup()


class TestDisclosureRouting(GateBase):
    name = "disclosure-routing"

    def test_critical_security_routes_to_disclosure_never_pr(self):
        r, calls, sb = self.run_gate({})
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.splitlines()
        self.assertTrue(any(l.startswith("DISCLOSE:") and "SEC-CURL-PIPE" in l for l in lines))
        self.assertFalse(any(l.startswith("KEEP:") and "SEC-CURL-PIPE" in l for l in lines))
        self.assertFalse(any("pr create" in c for c in calls))
        sb.cleanup()


class TestUmbrellaBackstop(GateBase):
    name = "umbrella-backstop"

    def test_the_gate_creates_no_issue_even_under_quota_pressure(self):
        """E8.2b (vibe-164) W6.2 relocated this behaviour, it was not deleted.

        This gate used to call `gh issue create` -- a mutation from a job holding only
        contents: read, with no issues: write. The umbrella backstop now lives in finalize,
        which does hold that permission, and fires on an explicit predicate rather than on
        `always()` having been reached. Its coverage is tests/test_auditor_quota.py
        TestUmbrellaPredicate; what belongs HERE is that gates stays read-only.
        """
        r, calls, sb = self.run_gate({"QUOTA_EXHAUSTED": "true", "REMAINING_COUNT": "4"})
        self.assertEqual(r.returncode, 0)
        self.assertFalse([c for c in calls if "issue create" in c],
                         "gates created an issue; it is specified read-only")
        sb.cleanup()

    def test_no_quota_pressure_is_a_noop(self):
        r, calls, sb = self.run_gate({"QUOTA_EXHAUSTED": "false", "REMAINING_COUNT": "0"})
        self.assertEqual(r.returncode, 0)
        self.assertFalse(any("issue create" in c for c in calls))
        sb.cleanup()


class TestGateInventory(unittest.TestCase):
    def test_all_nine_gates_present(self):
        text = WF.read_text() if WF.is_file() else ""
        for g in GATES:
            with self.subTest(gate=g):
                self.assertIn(f"# gate:{g}", text)


if __name__ == "__main__":
    unittest.main()
