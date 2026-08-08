# SPDX-License-Identifier: ISC
"""E8.2 contribution-gate behavior (vibe-59): every scriptable gate, positive + negative.

Gates live in `# gate:<name>` ... `# /gate` blocks inside auditor-contribute.yml's propose job;
the harness extracts and executes each with fixture inputs. This IS the "gate logic unit-tested
where scriptable" acceptance clause (the exhaustive combination matrix stays with E8.7).
"""
import json
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
            base = {"REPO": "acme/claude-toolkit", "OWNER": "acme",
                    "SIDECAR": str(FIX / "findings-sidecar.jsonl")}
            base.update(env)
            r = sb.run(self.block(), env=base)
            return r, sb.gh_calls(), sb
        finally:
            pass  # caller cleans via sb


class TestSecurityBlocked(GateBase):
    name = "security-blocked"

    def test_blocked_label_hard_fails(self):
        r, _, sb = self.run_gate({"LABELS": "contribute-approved,security-blocked"})
        self.assertNotEqual(r.returncode, 0)
        sb.cleanup()

    def test_clean_labels_pass(self):
        r, _, sb = self.run_gate({"LABELS": "contribute-approved"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("PASS", r.stdout)
        sb.cleanup()


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

    def test_cla_org_without_attestation_skips_with_template(self):
        r, _, sb = self.run_gate({"OWNER": "google", "CLA_SIGNED": "", "AUTHOR_NAME": "",
                                  "AUTHOR_EMAIL": ""})
        self.assertEqual(r.returncode, 0)
        self.assertIn("SKIP:cla", r.stdout)
        self.assertIn("cla-gate-messages", r.stdout)
        sb.cleanup()

    def test_attested_cla_org_passes(self):
        r, _, sb = self.run_gate({"OWNER": "google", "CLA_SIGNED": "true",
                                  "AUTHOR_NAME": "Jane Dev", "AUTHOR_EMAIL": "jane@example.com"})
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

    def test_api_error_fails_open(self):
        r, _, sb = self.run_gate({"OPEN_PRS_FILE": "/nonexistent/prs.json"})
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("DROP:", r.stdout)
        self.assertIn("PASS", r.stdout)
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
