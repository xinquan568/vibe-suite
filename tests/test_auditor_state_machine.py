# SPDX-License-Identifier: ISC
"""E8.2 stage dry-runs (vibe-59): execute every marked logic block against fixture state.

Each stage workflow carries `# stage-logic:<stage>` ... `# /stage-logic`; every other data-writing
workflow carries `# logic:<name>` ... `# /logic`. The harness extracts the block from the raw YAML
(no YAML parse), runs it under bash in a sandbox with a dual checkout (CODE_DIR + DATA_DIR), a
PATH-shimmed `gh` stub that records every call, and per-stage fixture variants. This IS the
"each stage dry-runs against a fixture registry issue" acceptance clause.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WF_DIR = REPO / "auditor" / "workflows"
FIX = Path(__file__).resolve().parent / "fixtures" / "auditor"

GH_STUB = """#!/usr/bin/env bash
# records every invocation; returns canned output when GH_CANNED_<verb> is set
echo "gh $*" >> "$GH_LOG"
key="GH_CANNED_$(echo "$1_$2" | tr ' -' '__' | tr '[:lower:]' '[:upper:]')"
if [ -n "${!key:-}" ]; then cat "${!key}"; exit 0; fi
# Path-shaped endpoints (gh api repos/<owner>/<name>) cannot form a legal variable name,
# so they are served from a map file instead: one "<prefix><TAB><file>" per line, longest
# prefix wins. Additive -- a caller that sets neither behaves exactly as before.
if [ -n "${GH_CANNED_MAP:-}" ] && [ -f "${GH_CANNED_MAP}" ]; then
  argv="$*"
  best=""; bestlen=0
  while IFS="$(printf '\t')" read -r prefix file; do
    [ -z "$prefix" ] && continue
    case "$argv" in
      "$prefix"*) if [ "${#prefix}" -gt "$bestlen" ]; then best="$file"; bestlen="${#prefix}"; fi ;;
    esac
  done < "$GH_CANNED_MAP"
  if [ -n "$best" ] && [ -f "$best" ]; then cat "$best"; exit 0; fi
fi
# Forced failures for fail-closed paths: GH_FAIL holds space-separated "<verb>:<arg>" keys
# (e.g. "api:repos/o/r/issues/9"). Same mechanism as the submit-suite stub; a caller that
# sets nothing behaves exactly as before.
case " ${GH_FAIL:-} " in *" ${1:-}:${2:-} "*) exit 1 ;; esac
exit 0
"""

MACHINE = {  # stage -> (entry label, exit label)
    "discover": (None, "audit-candidate"),
    "audit": ("audit-ready", "audit-complete"),
    "contribute": ("contribute-approved", "prs-submitted"),
    "track": (None, "case-study-ready"),
    "case-study": ("case-study-ready", "complete"),
    "daily-report": (None, None),
}
LOGIC_WORKFLOWS = [  # non-stage data-writers: # logic:<name> blocks
    "classify", "render-dashboard", "repo-report", "suppressions", "vocab-drift",
    "exemplar", "cite-exemplars", "refine-rules", "docs-diff",
]
CATEGORIES = ("reports", "audits", "ledgers", "articles", "exemplars", "registry")


def extract(path, marker, name):
    text = path.read_text()
    m = re.search(rf"^(\s*)# {marker}:{re.escape(name)}\s*$(.*?)^\s*# /{marker}\s*$",
                  text, re.M | re.S)
    if not m:
        return None
    indent = None
    lines = []
    for ln in m.group(2).split("\n"):
        if ln.strip() and indent is None:
            indent = len(ln) - len(ln.lstrip(" "))
        lines.append(ln[indent:] if indent and ln[:indent].isspace() or indent and ln.startswith(" " * indent) else ln)
    return "\n".join(lines)


class Sandbox:
    def __init__(self, registry="registry.json"):
        self.root = Path(tempfile.mkdtemp(prefix="auditor-sm-"))
        self.code = self.root / "code"
        self.data = self.root / "data"
        (self.code).mkdir()
        for c in ("reports", "audits", "ledgers", "articles", "exemplars", "registry"):
            (self.data / c).mkdir(parents=True)
        if registry:
            shutil.copy(FIX / registry, self.data / "registry" / "repos.json")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(GH_STUB)
        gh.chmod(0o755)
        self.gh_log = self.root / "gh.log"
        self.gh_log.touch()
        self.outside_before = self._snapshot_outside()

    def _snapshot_outside(self):
        return sorted(str(p) for p in self.root.rglob("*")
                      if p.is_file() and not str(p).startswith(str(self.data))
                      and p.name not in ("gh", "gh.log"))

    def run(self, script, env=None, fixture="registry-issue.json"):
        e = dict(os.environ)
        e.update({
            "PATH": f"{self.bin}:{e['PATH']}",
            # Actions sets GITHUB_WORKSPACE; a developer shell does not. Blocks resolve
            # ${GITHUB_WORKSPACE:-$PWD}, so without pinning it here a block wrote into the
            # runner's workspace under CI and into the sandbox locally -- four tests passed
            # on a laptop and failed on the PR. Pin it to the sandbox so both agree.
            "GITHUB_WORKSPACE": str(self.root),
            "CODE_DIR": str(self.code), "DATA_DIR": str(self.data),
            "FIXTURE": str(FIX / fixture),
            "REGISTRY": str(self.data / "registry" / "repos.json"),
            "EVENT_LOG": str(self.data / "ledgers" / "events.jsonl"),
            "GH_LOG": str(self.gh_log),
        })
        e.update(env or {})
        sh = self.root / "block.sh"
        sh.write_text(script)
        return subprocess.run(["bash", sh], capture_output=True, text=True, env=e,
                              cwd=self.root, timeout=60)

    def gh_calls(self):
        return self.gh_log.read_text().splitlines()

    def events(self):
        p = self.data / "ledgers" / "events.jsonl"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def registry(self):
        return json.loads((self.data / "registry" / "repos.json").read_text())

    def writes_outside_data(self):
        return [p for p in self._snapshot_outside() if p not in self.outside_before
                and "block.sh" not in p]

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class StageBase(unittest.TestCase):
    stage = None

    def block(self):
        path = WF_DIR / f"auditor-{self.stage}.yml"
        self.assertTrue(path.is_file(), f"{path} missing")
        b = extract(path, "stage-logic", self.stage)
        self.assertIsNotNone(b, f"no stage-logic block for {self.stage}")
        r = subprocess.run(["bash", "-n", "/dev/stdin"], input=b, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"stage block bash -n: {r.stderr}")
        return b


class TestDiscover(StageBase):
    stage = "discover"

    def test_worthy_candidate_creates_issue_registry_event(self):
        sb = Sandbox()
        try:
            r = sb.run(self.block(), env={"DRY_RUN": "false"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            calls = " ".join(sb.gh_calls())
            self.assertIn("issue create", calls)
            self.assertIn("audit-candidate", calls)
            self.assertIn("acme/claude-toolkit", json.dumps(sb.registry()))
            self.assertTrue(any(e.get("event") == "repo_discovered" for e in sb.events()))
        finally:
            sb.cleanup()

    def test_dry_run_makes_no_side_effects(self):
        sb = Sandbox()
        try:
            before = json.dumps(sb.registry())
            r = sb.run(self.block(), env={"DRY_RUN": "true"})
            self.assertEqual(r.returncode, 0)
            self.assertNotIn("issue create", " ".join(sb.gh_calls()))
            self.assertEqual(json.dumps(sb.registry()), before)
        finally:
            sb.cleanup()

    def test_below_star_floor_skips(self):
        sb = Sandbox()
        try:
            r = sb.run(self.block(), env={"DRY_RUN": "false", "MIN_STARS": "100000"})
            self.assertEqual(r.returncode, 0)
            self.assertIn("SKIP", r.stdout)
            self.assertNotIn("issue create", " ".join(sb.gh_calls()))
        finally:
            sb.cleanup()


class TestAudit(StageBase):
    stage = "audit"

    def test_aggregates_sidecar_updates_registry_swaps_labels(self):
        sb = Sandbox()
        try:
            (sb.data / "audits").mkdir(exist_ok=True)
            shutil.copy(FIX / "findings-sidecar.jsonl",
                        sb.data / "audits" / "acme-claude-toolkit.findings.jsonl")
            r = sb.run(self.block(), env={"SCORE": "64", "SECURITY": "REVIEW"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            ledger = (sb.data / "ledgers" / "findings.jsonl")
            self.assertTrue(ledger.exists())
            recs = [json.loads(x) for x in ledger.read_text().splitlines()]
            self.assertEqual(len(recs), 4)
            # vibe-59 round 6: findings are emitted in the SCHEMAS.md envelope
            # {timestamp, workflow, event, run_id, run_number, data:{...}}, so the payload
            # fields live under .data. This assertion predates that contract.
            for rec in recs:
                self.assertIn("timestamp", rec)
                self.assertIn("data", rec, f"record is not enveloped: {sorted(rec)}")
                for field in ("fingerprint", "repo", "rule_id", "confidence"):
                    self.assertIn(field, rec["data"])
            self.assertEqual(sb.registry()["repos"]["acme/claude-toolkit"]["status"], "audited")
            calls = " ".join(sb.gh_calls())
            self.assertIn("--add-label", calls)
            self.assertIn("audit-complete", calls)
            self.assertIn("--remove-label", calls)
        finally:
            sb.cleanup()

    def test_absent_registry_refuses_named(self):
        sb = Sandbox(registry=None)
        try:
            (sb.data / "registry" / "repos.json").unlink(missing_ok=True)
            r = sb.run(self.block())
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("REFUSE:registry-missing", r.stdout + r.stderr)
        finally:
            sb.cleanup()


class TestContribute(StageBase):
    stage = "contribute"

    def test_filters_to_high_confidence_and_transitions(self):
        sb = Sandbox()
        try:
            shutil.copy(FIX / "findings-sidecar.jsonl",
                        sb.data / "audits" / "acme-claude-toolkit.findings.jsonl")
            # E8.2b (vibe-164) F8: the durable transition now requires a numeric PR number,
            # and a run that opened no PR exits before it. In production `gh pr create`
            # returns the PR URL and the number is parsed from it; the stub returned nothing,
            # so this test was asserting a label transition on a run that had no PR. Model the
            # creation response rather than relaxing the contract.
            r = sb.run(self.block(), env={
                "FIRST_CONTACT": "true", "WEEK_CONTACT_COUNT": "0",
                # This block does not open the PR -- `gh pr create` lives in logic:submit and
                # hands the number down. Supplying it models "a PR was opened upstream", which
                # is what a run reaching the durable transition means. Not a derived value the
                # graph must compute, so the derived-value scan is unaffected.
                "PR_NUMBER": "7"})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # 3 high-confidence findings, one is critical security -> disclosure, one duplicated? none here
            # plan surface: kept findings echoed as KEEP:<fingerprint-ish> lines
            keeps = [l for l in r.stdout.splitlines() if l.startswith("KEEP:")]
            self.assertEqual(len(keeps), 2)  # 3 high minus 1 critical-security (disclosure-routed)
            self.assertTrue(any(l.startswith("DISCLOSE:") for l in r.stdout.splitlines()))
            calls = " ".join(sb.gh_calls())
            self.assertIn("prs-submitted", calls)
            self.assertIn("--remove-label", calls)
        finally:
            sb.cleanup()

    def test_absent_registry_refuses(self):
        sb = Sandbox(registry=None)
        try:
            (sb.data / "registry" / "repos.json").unlink(missing_ok=True)
            r = sb.run(self.block(), env={})
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("REFUSE:registry-missing", r.stdout + r.stderr)
        finally:
            sb.cleanup()


class TestTrack(StageBase):
    stage = "track"

    def test_records_outcomes_promotes_and_emits_once(self):
        sb = Sandbox(registry="registry-tracked.json")
        try:
            r = sb.run(self.block())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            reg = sb.registry()["repos"]["acme/claude-toolkit"]
            self.assertEqual(reg["prs"]["17"]["outcome"], "merged")
            self.assertEqual(reg["prs"]["18"]["outcome"], "applied_separately")
            self.assertEqual(reg["status"], "tracked")
            self.assertTrue(reg.get("case_study_candidate"))
            self.assertIn("case-study-ready", " ".join(sb.gh_calls()))
            n_outcome = sum(1 for e in sb.events() if e.get("event") == "finding_outcome")
            self.assertEqual(n_outcome, 2)
            # idempotence: second run emits nothing new
            r2 = sb.run(self.block())
            self.assertEqual(r2.returncode, 0)
            n2 = sum(1 for e in sb.events() if e.get("event") == "finding_outcome")
            self.assertEqual(n2, 2)
        finally:
            sb.cleanup()


class TestCaseStudy(StageBase):
    stage = "case-study"

    def test_worthy_passes_unworthy_skips_with_status_complete(self):
        sb = Sandbox(registry="registry-tracked.json")
        try:
            r = sb.run(self.block(), env={"MERGED": "1", "APPLIED_SEP": "1", "SCORE": "64",
                                          "SECURITY": "REVIEW", "RULE_ADOPTED": "false"})
            self.assertEqual(r.returncode, 0)
            self.assertIn("PASS", r.stdout)
            sb2 = Sandbox(registry="registry-tracked.json")
            r2 = sb2.run(self.block(), env={"MERGED": "0", "APPLIED_SEP": "0", "SCORE": "95",
                                            "SECURITY": "CLEAR", "RULE_ADOPTED": "false"})
            self.assertEqual(r2.returncode, 0)
            self.assertIn("SKIP:not-worthy", r2.stdout)
            self.assertEqual(sb2.registry()["repos"]["acme/claude-toolkit"]["status"], "complete")
            self.assertTrue(any(e.get("event") == "case_study_skipped" for e in sb2.events()))
            sb2.cleanup()
        finally:
            sb.cleanup()


class TestDailyReport(StageBase):
    stage = "daily-report"

    def test_writes_report_with_unbounded_label_counts(self):
        sb = Sandbox()
        try:
            r = sb.run(self.block())
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            reports = list((sb.data / "reports").rglob("*.md"))
            self.assertTrue(reports, "no report written under DATA_DIR/reports")
            listing = [c for c in sb.gh_calls() if "issue list" in c]
            self.assertTrue(listing)
            for call in listing:
                m = re.search(r"--limit (\d+)", call)
                self.assertIsNotNone(m, f"issue list without --limit: {call}")
                self.assertGreaterEqual(int(m.group(1)), 1000, call)
            self.assertTrue(any(e.get("event") == "report_generated" for e in sb.events()))
        finally:
            sb.cleanup()


class TestNonStageDataWriters(unittest.TestCase):
    def test_every_data_writer_block_runs_confined_and_refuses_bare(self):
        for name in LOGIC_WORKFLOWS:
            path = WF_DIR / f"auditor-{name}.yml"
            self.assertTrue(path.is_file(), f"{path} missing")
            block = extract(path, "logic", name)
            self.assertIsNotNone(block, f"no logic block for {name}")
            sb = Sandbox()
            try:
                if name == "exemplar":
                    # vibe-59 round 6: exemplar REFUSES rather than publishing a fabricated stub
                    # when the model wrote nothing, so the happy path must supply model output.
                    (sb.data / "exemplars").mkdir(exist_ok=True)
                    (sb.data / "exemplars" / "acme-claude-toolkit.md").write_text(
                        "---\nslug: acme-claude-toolkit\nrepo: acme/claude-toolkit\n"
                        "audited: 2026-08-06\ncommit_sha: cafebabe\nscore: 92\n"
                        "exemplifies:\n  - R07\n---\n\nEvidence body.\n", encoding="utf-8")
                with self.subTest(workflow=name, case="fixture-run"):
                    r = sb.run(block, env={"SCORE": "92", "SECURITY": "CLEAR"})
                    self.assertEqual(r.returncode, 0, f"{name}: {r.stdout} {r.stderr}")
                    self.assertEqual(sb.writes_outside_data(), [],
                                     f"{name} wrote outside DATA_DIR")
                sb2 = Sandbox(registry=None)
                (sb2.data / "registry" / "repos.json").unlink(missing_ok=True)
                with self.subTest(workflow=name, case="missing-input"):
                    r2 = sb2.run(block, env={"SCORE": "92", "SECURITY": "CLEAR"})
                    out = r2.stdout + r2.stderr
                    self.assertTrue(
                        r2.returncode != 0 or "SKIP" in out or "REFUSE" in out,
                        f"{name} silently succeeded with no inputs")
                sb2.cleanup()
            finally:
                sb.cleanup()


if __name__ == "__main__":
    unittest.main()


class TestRegistryBootstrap(unittest.TestCase):
    """W7c (vibe-59): the bootstrap shape and its documentation contract."""

    def test_bootstrap_shape_is_the_schema_empty_form(self):
        boot = json.loads('{\n  "repos": {}\n}\n')
        self.assertEqual(boot, {"repos": {}})
        fixture = json.loads((FIX / "registry.json").read_text())
        self.assertIn("repos", fixture)
        self.assertIsInstance(fixture["repos"], dict)

    def test_schemas_documents_bootstrap_and_refusal(self):
        p = REPO / "auditor" / "SCHEMAS.md"
        self.assertTrue(p.is_file(), "auditor/SCHEMAS.md missing")
        t = p.read_text()
        self.assertIn('{"repos": {}}', t.replace("'", '"'))
        self.assertIn("registry-missing", t)

    def test_runbook_records_the_performed_bootstrap(self):
        t = (REPO / "auditor" / "README.md").read_text()
        self.assertIn("Registry bootstrap (performed", t)
        self.assertIn("REFUSE:registry-missing", t)
