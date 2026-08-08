# SPDX-License-Identifier: ISC
"""E8.2b gate outputs (vibe-164, plan W4): filtering that is enforced, not printed.

The gates already decide which findings survive -- they print KEEP:/DROP:/DISCLOSE: lines --
but nothing downstream was bound by those decisions. `submit` applied whatever patches the
model produced. This suite covers the two artifacts that close that gap:

  proposal-manifest.json  the allowlist of what may become a patch, written after the
                          confidence, duplicate and cap filters
  disclosure.json         the security findings routed AWAY from the public-PR path

The security property is the sharp one: a finding that reaches disclosure.json must NOT be in
the manifest. If it were, submit would open a public PR carrying the very vulnerability the
disclosure path exists to keep private.
"""
import json
import subprocess
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract, FIX

REPO_ROOT = Path(__file__).resolve().parent.parent
WF = REPO_ROOT / "auditor" / "workflows" / "auditor-contribute.yml"
TARGET = "acme/claude-toolkit"


class ManifestBase(unittest.TestCase):
    def block(self, name, marker="gate"):
        b = extract(WF, marker, name)
        self.assertIsNotNone(b, f"no {marker}:{name} block in {WF.name}")
        return b

    def run_emit(self, name="emit-manifest", env=None, sidecar="findings-sidecar.jsonl"):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        base = {"REPO": TARGET, "OWNER": TARGET.split("/")[0],
                "SIDECAR": str(FIX / sidecar),
                "CODE_DIR": str(REPO_ROOT),
                "MANIFEST": str(sb.root / "proposal-manifest.json"),
                "DISCLOSURE": str(sb.root / "disclosure.json"),
                "PLANNED_COUNT": "4", "FIRST_CONTACT": "true"}
        base.update(env or {})
        r = sb.run(self.block(name), env=base)
        return r, sb

    def manifest(self, sb):
        p = sb.root / "proposal-manifest.json"
        self.assertTrue(p.is_file(), "gates wrote no proposal-manifest.json")
        return json.loads(p.read_text())


class TestManifestContents(ManifestBase):
    def test_manifest_is_versioned(self):
        r, sb = self.run_emit()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        self.assertEqual(1, self.manifest(sb)["version"])

    def test_only_high_confidence_findings_survive(self):
        r, sb = self.run_emit()
        rules = [f["rule_id"] for f in self.manifest(sb)["findings"]]
        self.assertNotIn("R07", rules, "a medium-confidence finding reached the allowlist")

    def test_the_disclosure_set_is_excluded_from_the_allowlist(self):
        # The security property. SEC-CURL-PIPE is high-confidence security/critical, so the
        # disclosure gate routes it away from the PR path. If it were also in the manifest,
        # submit would open a PUBLIC pull request carrying it.
        r, sb = self.run_emit()
        rules = [f["rule_id"] for f in self.manifest(sb)["findings"]]
        self.assertNotIn(
            "SEC-CURL-PIPE", rules,
            "a critical security finding is in the PR allowlist AND on the disclosure path; "
            "submit would publish it")

    def test_the_ordinary_high_confidence_findings_do_survive(self):
        r, sb = self.run_emit()
        rules = [f["rule_id"] for f in self.manifest(sb)["findings"]]
        self.assertIn("BUG-BROKEN-REF", rules)
        self.assertIn("BUG-DEAD-LINK", rules)

    def test_every_entry_carries_a_computed_fingerprint(self):
        # The sidecar carries no fingerprint (SCHEMAS section 4); the manifest must compute it
        # per section 3, or submit has nothing to validate a patch against.
        r, sb = self.run_emit()
        for f in self.manifest(sb)["findings"]:
            self.assertTrue(str(f.get("fingerprint", "")).startswith("sha256:"),
                            f"{f.get('rule_id')} has no section-3 fingerprint")

    def test_the_cap_bounds_the_allowlist(self):
        r, sb = self.run_emit(env={"PLANNED_COUNT": "1", "PATCH_CAP": "1"})
        self.assertLessEqual(len(self.manifest(sb)["findings"]), 1)


class TestDisclosureArtifact(ManifestBase):
    def test_disclosure_json_carries_the_routed_findings(self):
        r, sb = self.run_emit(name="disclosure-routing")
        p = sb.root / "disclosure.json"
        self.assertTrue(p.is_file(), "disclosure-routing wrote no disclosure.json")
        rules = [f["rule_id"] for f in json.loads(p.read_text())["findings"]]
        self.assertIn("SEC-CURL-PIPE", rules)

    def test_disclosure_json_holds_only_security_findings(self):
        r, sb = self.run_emit(name="disclosure-routing")
        rules = [f["rule_id"] for f in
                 json.loads((sb.root / "disclosure.json").read_text())["findings"]]
        self.assertNotIn("BUG-BROKEN-REF", rules)


class TestDisclosureNeverReachesPropose(unittest.TestCase):
    """W4.2's prohibited half, made live.

    A test that only asserts disclosure REACHES finalize is green while disclosure reaches
    nobody at all. This asserts the prohibition directly against the workflow text, so
    wiring a disclosure download into propose turns it red -- which is the mutation the plan
    requires (Step-5 finding 6).
    """

    def test_the_propose_job_downloads_no_disclosure_artifact(self):
        text = WF.read_text(encoding="utf-8")
        start = text.index("\n  propose:")
        end = text.index("\n  submit:")
        propose = text[start:end]
        # The prohibition is on the ARTIFACT reaching propose, not on the word appearing:
        # propose's model prompt legitimately tells the model that security findings take the
        # disclosure path. A bare substring match on "disclosure" flagged that prose, which
        # would have been a false positive standing guard over a real constraint.
        self.assertNotIn(
            "disclosure.json", propose,
            "the propose job references disclosure.json. propose runs the MODEL; a model job "
            "able to read undisclosed security findings can leak them into a public patch body "
            "(SCHEMAS section 14 routing constraint)")
        # Check what the download steps NAME, not what text follows them. An earlier version
        # scanned everything after the first download-artifact, which meant that simply
        # giving propose a legitimate download (gate-context) made it trip over the model
        # prompt's prose further down. That is the second time this assertion caught its own
        # documentation rather than a violation.
        import re
        names = re.findall(r"name:\s*(\S+)", propose)
        for n in names:
            self.assertNotIn(
                "disclosure", n.lower(),
                f"propose downloads or references an artifact named '{n}'. propose runs the "
                f"MODEL; the disclosure set must never reach it.")

    def test_the_finalize_job_does_receive_it(self):
        text = WF.read_text(encoding="utf-8")
        finalize = text[text.index("\n  finalize:"):]
        self.assertIn("disclosure", finalize,
                      "finalize does not consume disclosure.json, so the routing constraint "
                      "is satisfied only because nothing routes anywhere")


class TestSubmitValidatesAgainstTheAllowlist(unittest.TestCase):
    """W4.3 -- a patch whose fingerprint no gate admitted never reaches a PR.

    This is the enforcement half. Without it the manifest is a document nobody consults, and
    a patch could reach a public PR without any gate having admitted the finding behind it --
    including one the disclosure gate deliberately routed away.
    """

    def block(self):
        b = extract(WF, "logic", "submit")
        self.assertIsNotNone(b, "no logic:submit block")
        return b

    def run_submit(self, manifest_fps, patch_fps):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        man = sb.root / "proposal-manifest.json"
        man.write_text(json.dumps({
            "version": 1, "repo": TARGET,
            "findings": [{"rule_id": "R", "fingerprint": f, "file": "a.md",
                          "confidence": "high"} for f in manifest_fps]}))
        patches = sb.root / "_patches"; patches.mkdir()
        (patches / "findings.json").write_text(json.dumps(
            [{"rule_id": "R", "fingerprint": f} for f in patch_fps]))
        ctx = sb.root / "context.json"
        ctx.write_text(json.dumps({
            "version": 1, "repo": TARGET, "issue": "42",
            "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
            "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
            "weekly_cap": 2, "patch_cap": 3}))
        env = {"REPO": TARGET, "CONTEXT_FILE": str(ctx), "MANIFEST": str(man),
               "PATCH_DIR": str(patches), "PATCH_META": str(patches / "findings.json"),
               "TARGET_DIR": str(sb.root / "_target")}
        return sb.run(self.block(), env=env)

    def test_a_fingerprint_outside_the_allowlist_refuses(self):
        r = self.run_submit(manifest_fps=["sha256:aaa"], patch_fps=["sha256:aaa", "sha256:zzz"])
        out = r.stdout + r.stderr
        self.assertIn("REFUSE:patch-not-in-manifest", out,
                      "submit applied a patch no gate admitted")

    def test_an_allowlisted_fingerprint_is_not_refused_for_that_reason(self):
        r = self.run_submit(manifest_fps=["sha256:aaa"], patch_fps=["sha256:aaa"])
        self.assertNotIn("REFUSE:patch-not-in-manifest", r.stdout + r.stderr)

    def test_a_missing_manifest_refuses_rather_than_allowing_everything(self):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        patches = sb.root / "_patches"; patches.mkdir()
        (patches / "findings.json").write_text(json.dumps(
            [{"rule_id": "R", "fingerprint": "sha256:aaa"}]))
        ctx = sb.root / "context.json"
        ctx.write_text(json.dumps({
            "version": 1, "repo": TARGET, "issue": "42",
            "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
            "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
            "weekly_cap": 2, "patch_cap": 3}))
        r = sb.run(self.block(), env={
            "REPO": TARGET, "CONTEXT_FILE": str(ctx),
            "MANIFEST": str(sb.root / "absent.json"),
            "PATCH_DIR": str(patches), "PATCH_META": str(patches / "findings.json"),
            "TARGET_DIR": str(sb.root / "_target")})
        self.assertIn("REFUSE:manifest-missing", r.stdout + r.stderr,
                      "an absent manifest was treated as 'allow everything'; fail-open here "
                      "defeats the entire allowlist")


class TestProducerFeedsConsumerUnchanged(ManifestBase):
    """W4.4 -- the manifest gates actually wrote, consumed by submit without editing.

    Both halves passing in isolation does not establish that they agree: the producer could
    emit a fingerprint shape the consumer never matches, and each suite would still be green
    against its own hand-built fixture. This runs the real producer, takes the file it
    actually wrote, and hands it to the real consumer.
    """

    def submit_block(self):
        b = extract(WF, "logic", "submit")
        self.assertIsNotNone(b, "no logic:submit block")
        return b

    def test_a_patch_for_an_admitted_finding_passes_the_real_manifest(self):
        r, sb = self.run_emit()
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        produced = self.manifest(sb)
        self.assertTrue(produced["findings"], "producer admitted nothing; nothing to integrate")
        fp = produced["findings"][0]["fingerprint"]

        patches = sb.root / "_patches"; patches.mkdir(exist_ok=True)
        (patches / "findings.json").write_text(json.dumps([{"rule_id": "R", "fingerprint": fp}]))
        ctx = sb.root / "context.json"
        ctx.write_text(json.dumps({
            "version": 1, "repo": TARGET, "issue": "42",
            "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
            "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
            "weekly_cap": 2, "patch_cap": 3}))
        r2 = sb.run(self.submit_block(), env={
            "REPO": TARGET, "CONTEXT_FILE": str(ctx),
            "MANIFEST": str(sb.root / "proposal-manifest.json"),
            "PATCH_DIR": str(patches), "PATCH_META": str(patches / "findings.json"),
            "TARGET_DIR": str(sb.root / "_target")})
        self.assertNotIn(
            "REFUSE:patch-not-in-manifest", r2.stdout + r2.stderr,
            "the consumer rejected a fingerprint the producer itself admitted -- the two "
            "halves disagree on fingerprint shape despite each passing in isolation")

    def test_a_disclosed_finding_cannot_be_patched_end_to_end(self):
        # The security property, end to end: SEC-CURL-PIPE is routed to disclosure, so it is
        # absent from the manifest, so a patch claiming it is refused by submit.
        # Both gates run in ONE sandbox -- running only emit-manifest would leave no
        # disclosure.json and the test would fail for the wrong reason.
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        env = {"REPO": TARGET, "OWNER": TARGET.split("/")[0],
               "SIDECAR": str(FIX / "findings-sidecar.jsonl"),
               "CODE_DIR": str(REPO_ROOT),
               "MANIFEST": str(sb.root / "proposal-manifest.json"),
               "DISCLOSURE": str(sb.root / "disclosure.json"),
               "PLANNED_COUNT": "4", "FIRST_CONTACT": "true"}
        rd = sb.run(self.block("disclosure-routing"), env=env)
        self.assertEqual(0, rd.returncode, rd.stdout + rd.stderr)
        rm = sb.run(self.block("emit-manifest"), env=env)
        self.assertEqual(0, rm.returncode, rm.stdout + rm.stderr)
        disclosed = json.loads((sb.root / "disclosure.json").read_text())["findings"]
        self.assertTrue(disclosed, "nothing was routed to disclosure; the test proves nothing")

        patches = sb.root / "_patches"; patches.mkdir(exist_ok=True)
        (patches / "findings.json").write_text(json.dumps(
            [{"rule_id": disclosed[0]["rule_id"], "fingerprint": "sha256:forged"}]))
        ctx = sb.root / "context.json"
        ctx.write_text(json.dumps({
            "version": 1, "repo": TARGET, "issue": "42",
            "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
            "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
            "weekly_cap": 2, "patch_cap": 3}))
        r2 = sb.run(self.submit_block(), env={
            "REPO": TARGET, "CONTEXT_FILE": str(ctx),
            "MANIFEST": str(sb.root / "proposal-manifest.json"),
            "PATCH_DIR": str(patches), "PATCH_META": str(patches / "findings.json"),
            "TARGET_DIR": str(sb.root / "_target")})
        self.assertIn("REFUSE:patch-not-in-manifest", r2.stdout + r2.stderr,
                      "a security finding on the disclosure path reached the patch surface")
