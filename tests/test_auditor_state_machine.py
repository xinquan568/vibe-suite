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
# Forced failures FIRST: GH_FAIL holds space-separated "<verb>:<arg>" keys (e.g.
# "api:repos/o/r/issues/9"). A canned success must never shadow an explicitly forced
# failure -- the fail-closed tests are only authoritative if this wins. Same mechanism as
# the submit-suite stub; a caller that sets nothing behaves exactly as before.
case " ${GH_FAIL:-} " in *" ${1:-}:${2:-} "*) exit 1 ;; esac
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
  if [ -n "$best" ] && [ -f "$best" ]; then
    # A canned RAW payload (valid JSON) is served through the caller's own --jq expression,
    # so tests exercise the production extraction rather than a pre-processed answer -- a
    # broken expression must fail the test, not be papered over by the fixture. Legacy
    # pre-processed fixtures (non-JSON text like a bare branch name) are served verbatim.
    jqexpr=""; prev=""
    for a in "$@"; do
      if [ "$prev" = "--jq" ]; then jqexpr="$a"; fi
      prev="$a"
    done
    if [ -n "$jqexpr" ] && jq -e . < "$best" >/dev/null 2>&1; then
      jq -r "$jqexpr" < "$best"
    else
      cat "$best"
    fi
    exit 0
  fi
fi
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
        # vibe-167: rewired blocks invoke helpers at $CODE_DIR/auditor/scripts/;
        # a checkout always carries them, so the sandbox does too
        shutil.copytree(REPO / "auditor" / "scripts",
                        self.code / "auditor" / "scripts")
        # render-dashboard.py resolves ROOT two parents up from itself; its
        # templates and the rulebook ride along like a real checkout's would
        shutil.copytree(REPO / "templates" / "report",
                        self.code / "templates" / "report")
        shutil.copytree(REPO / "skills" / "rules",
                        self.code / "skills" / "rules")
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
            # Runner-provided, like GITHUB_WORKSPACE: the suppressions scan excludes the
            # host repository by name and refuses an unset value rather than ingesting its
            # own fixtures.
            "GITHUB_REPOSITORY": "example/host-repo",
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
                if name == "suppressions":
                    # The helper scan REFUSES a failed search (a partial corpus is worse
                    # than none), so the bare fixture-run cans a successful empty search.
                    # The cans live OUTSIDE the sandbox root: the confinement assertion
                    # below owns everything under it.
                    canned_dir = Path(tempfile.mkdtemp(prefix="supp-canned-"))
                    canned = canned_dir / "empty-search.json"
                    canned.write_text(json.dumps({"total_count": 0,
                                                  "incomplete_results": False,
                                                  "items": []}))
                    m = canned_dir / "canned-map"
                    m.write_text("api -X GET search/code\t" + str(canned) + "\n")
                    (sb.data / "feedback").mkdir(exist_ok=True)
                    extra_env = {"GH_CANNED_MAP": str(m), "CODE_DIR": str(REPO)}
                else:
                    canned_dir = None
                    extra_env = {}
                if name == "exemplar":
                    # vibe-59 round 6: exemplar REFUSES rather than publishing a fabricated stub
                    # when the model wrote nothing, so the happy path must supply model output.
                    (sb.data / "exemplars").mkdir(exist_ok=True)
                    (sb.data / "exemplars" / "acme-claude-toolkit.md").write_text(
                        "---\nslug: acme-claude-toolkit\nrepo: acme/claude-toolkit\n"
                        "audited: 2026-08-06\ncommit_sha: cafebabe\nscore: 92\n"
                        "exemplifies:\n  - R07\n---\n\nEvidence body.\n", encoding="utf-8")
                with self.subTest(workflow=name, case="fixture-run"):
                    r = sb.run(block, env={"SCORE": "92", "SECURITY": "CLEAR", **extra_env})
                    self.assertEqual(r.returncode, 0, f"{name}: {r.stdout} {r.stderr}")
                    self.assertEqual(sb.writes_outside_data(), [],
                                     f"{name} wrote outside DATA_DIR")
                sb2 = Sandbox(registry=None)
                (sb2.data / "registry" / "repos.json").unlink(missing_ok=True)
                with self.subTest(workflow=name, case="missing-input"):
                    r2 = sb2.run(block, env={"SCORE": "92", "SECURITY": "CLEAR", **extra_env})
                    out = r2.stdout + r2.stderr
                    self.assertTrue(
                        r2.returncode != 0 or "SKIP" in out or "REFUSE" in out,
                        f"{name} silently succeeded with no inputs")
                sb2.cleanup()
            finally:
                sb.cleanup()



class TestRefineRulesPipeline(unittest.TestCase):
    """E8.6 (vibe-63): the refinement pipeline is the three helpers, in gate order.

    The block used to aggregate disagreements.jsonl inline — a reimplementation of what
    `rule-health.py` + `prepare-refinement-input.py` do, minus the gate between them. The
    wiring under test: `rule-health.py` rebuilds feedback/log.json from the event ledger,
    `validate-feedback.sh` gates the rebuilt log, and `prepare-refinement-input.py --out`
    writes the reviewer input the model step consumes. Order is load-bearing: the gate sits
    BETWEEN the rebuild and the consumer, and an invalid log must stop the pipeline before
    any refinement input exists.
    """

    def _events(self, rule_id="R04"):
        # A DISPUTED rule: three distinct fingerprints (the confidence floor), each
        # adjudicated, two rejected — acceptance below one half.
        def env_(event, data, ts):
            return {"timestamp": ts, "workflow": "t", "event": event, "run_id": "1",
                    "run_number": 1, "data": data}
        evs = []
        for i, fp in enumerate(("fp-a", "fp-b", "fp-c")):
            evs.append(env_("finding_recorded", {"fingerprint": fp, "rule_id": rule_id},
                            f"2026-01-0{i+1}T00:00:00Z"))
        return evs

    def _registry(self, rule_id="R04"):
        return {"repos": {"acme/w": {"prs": {
            "1": {"number": 1, "updatedAt": "2026-04-01T00:00:00Z", "outcome": "rejected",
                  "fingerprints": ["fp-a"], "rule_ids": [rule_id]},
            "2": {"number": 2, "updatedAt": "2026-04-02T00:00:00Z", "outcome": "rejected",
                  "fingerprints": ["fp-b"], "rule_ids": [rule_id]},
            "3": {"number": 3, "updatedAt": "2026-04-03T00:00:00Z", "outcome": "merged",
                  "fingerprints": ["fp-c"], "rule_ids": [rule_id]},
        }}}}

    def _sandbox(self, rule_id="R04"):
        sb = Sandbox()
        (sb.data / "ledgers" / "events.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in self._events(rule_id)), encoding="utf-8")
        (sb.data / "registry" / "repos.json").write_text(
            json.dumps(self._registry(rule_id)), encoding="utf-8")
        (sb.data / "exemplars").mkdir(exist_ok=True)
        return sb

    def _block(self):
        b = extract(WF_DIR / "auditor-refine-rules.yml", "logic", "refine-rules")
        assert b is not None
        return b

    def test_the_pipeline_rebuilds_gates_and_prepares(self):
        sb = self._sandbox()
        try:
            genv = sb.root / "out.env"
            r = sb.run(self._block(), env={"GITHUB_OUTPUT": str(genv), "CODE_DIR": str(REPO)})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue((sb.data / "feedback" / "log.json").is_file(),
                            "rule-health.py never rebuilt the feedback log")
            inp = sb.data / "ledgers" / "refinement-input.json"
            self.assertTrue(inp.is_file(), "prepare-refinement-input.py wrote no --out file")
            doc = json.loads(inp.read_text())
            self.assertIn("rules", doc, "the input does not carry the helper schema")
            self.assertGreaterEqual(doc.get("selected", 0), 1,
                                    "the disputed fixture selected nothing")
            self.assertIn("refine_proceed=true", genv.read_text() if genv.exists() else "",
                          "the proceed flag never published")
            events = [json.loads(l) for l in
                      (sb.data / "ledgers" / "events.jsonl").read_text().splitlines() if l]
            prepared = [e for e in events if e.get("event") == "proposals_prepared"]
            self.assertEqual(1, len(prepared))
            self.assertEqual(doc["selected"], prepared[0]["data"]["proposals"],
                             "the event count disagrees with the helper's selection")
        finally:
            sb.cleanup()

    def test_an_invalid_log_stops_at_the_gate(self):
        # A rule id outside the schema shape: the rebuilt log fails validate-feedback's
        # INVALID RULE IDS arithmetic, and the pipeline must stop with no refinement input.
        sb = self._sandbox(rule_id="not a rule id !!!")
        try:
            r = sb.run(self._block(), env={"GITHUB_OUTPUT": str(sb.root / "out.env"), "CODE_DIR": str(REPO)})
            self.assertNotEqual(0, r.returncode,
                                "an invalid feedback log passed the gate")
            self.assertFalse((sb.data / "ledgers" / "refinement-input.json").exists(),
                             "the consumer ran despite the gate's refusal — order is not "
                             "rebuild -> gate -> consume")
        finally:
            sb.cleanup()

    def test_zero_selected_skips_without_proceeding(self):
        # Healthy data: one accepted finding, hits below the confidence floor.
        sb = Sandbox()
        try:
            (sb.data / "ledgers" / "events.jsonl").write_text(
                json.dumps({"timestamp": "2026-01-01T00:00:00Z", "workflow": "t",
                            "event": "finding_recorded", "run_id": "1", "run_number": 1,
                            "data": {"fingerprint": "fp-z", "rule_id": "R07"}}) + "\n",
                encoding="utf-8")
            (sb.data / "registry" / "repos.json").write_text(
                json.dumps({"repos": {"acme/w": {"prs": {
                    "1": {"number": 1, "updatedAt": "2026-04-01T00:00:00Z",
                          "outcome": "merged", "fingerprints": ["fp-z"],
                          "rule_ids": ["R07"]}}}}}), encoding="utf-8")
            genv = sb.root / "out.env"
            r = sb.run(self._block(), env={"GITHUB_OUTPUT": str(genv), "CODE_DIR": str(REPO)})
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertIn("SKIP:no-proposals", r.stdout + r.stderr)
            self.assertNotIn("refine_proceed=true",
                             genv.read_text() if genv.exists() else "")
        finally:
            sb.cleanup()



class TestRuleReviewWiring(unittest.TestCase):
    """E8.6 (vibe-63): the quarterly review body is the helper's product, not a heredoc.

    The workflow used to print a static checklist; `generate-rule-review-body.py` composes
    the two sections a reviewer cannot assemble by hand (stale citations, quarterly
    rejections) from the data branch. The parser takes ONE `--quarter YYYY-Qn` value — the
    workflow holds year and quarter separately and must compose them — and `--out` names
    the body file the `gh issue create` call consumes.
    """

    def _block(self):
        b = extract(WF_DIR / "auditor-rule-review.yml", "logic", "rule-review")
        assert b is not None, "no logic:rule-review block — the body build is not extractable"
        return b

    def _sandbox(self):
        sb = Sandbox()
        for sub in ("ledgers", "exemplars"):
            (sb.data / sub).mkdir(exist_ok=True)
        return sb

    def test_the_issue_body_is_the_generated_review(self):
        sb = self._sandbox()
        try:
            r = sb.run(self._block(), env={"CODE_DIR": str(REPO),
                                           "RUNNER_TEMP": str(sb.root)})
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            create = [c for c in sb.gh_calls() if "issue create" in c]
            self.assertEqual(1, len(create), f"gh calls: {sb.gh_calls()}")
            self.assertIn("--body-file", create[0])
            body_path = create[0].split("--body-file", 1)[1].strip().split()[0]
            body = Path(body_path).read_text(encoding="utf-8")
            self.assertIn("## Stale citations", body,
                          "the filed body is not the helper's product — the stale-citations "
                          "section a hand-built checklist cannot compose is missing")
            self.assertIn("## Rejections this quarter", body)
            self.assertRegex(body, r"# Rule review — \d{4}-Q[1-4]",
                             "the composed YYYY-Qn quarter never reached the helper")
        finally:
            sb.cleanup()

    def test_an_open_review_this_quarter_skips(self):
        sb = self._sandbox()
        try:
            canned = sb.root / "canned-issues"
            canned.write_text("open issue 1\n")
            r = sb.run(self._block(), env={"CODE_DIR": str(REPO),
                                           "RUNNER_TEMP": str(sb.root),
                                           "GH_CANNED_ISSUE_LIST": str(canned)})
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertIn("SKIP:already-filed-this-quarter", r.stdout + r.stderr)
            self.assertEqual([], [c for c in sb.gh_calls() if "issue create" in c])
        finally:
            sb.cleanup()



class TestDocsDiffWiring(unittest.TestCase):
    """E8.6 (vibe-63): the drift scan is docs-diff.py's, and the issue duties survive.

    The block used to reimplement fetch/hash/compare inline with curl. The helper owns that
    surface (fetch-failure semantics included: an unreachable page keeps its stored hash and
    is NOT drift); what must survive the replacement are the workflow's externally visible
    duties — per-URL drift issues with dedup-by-comment, and the docs_diff event carrying
    the helper's own counts.
    """

    def _sandbox(self, citations, hashes=None):
        sb = Sandbox()
        (sb.data / "ledgers").mkdir(exist_ok=True)
        (sb.data / "ledgers" / "docs-citations.json").write_text(
            json.dumps(citations), encoding="utf-8")
        if hashes is not None:
            (sb.data / "ledgers" / "docs-hashes.json").write_text(
                json.dumps(hashes), encoding="utf-8")
        return sb

    def _block(self):
        b = extract(WF_DIR / "auditor-docs-diff.yml", "logic", "docs-diff")
        assert b is not None
        return b

    def _page(self, sb, name, text):
        f = sb.root / name
        f.write_text(text, encoding="utf-8")
        return f.as_uri()

    def _run(self, sb, env=None):
        e = {"CODE_DIR": str(REPO), "RUNNER_TEMP": str(sb.root)}
        e.update(env or {})
        return sb.run(self._block(), env=e)

    def _event(self, sb):
        events = [json.loads(l) for l in
                  (sb.data / "ledgers" / "events.jsonl").read_text().splitlines() if l]
        diffs = [e for e in events if e.get("event") == "docs_diff"]
        self.assertEqual(1, len(diffs))
        return diffs[0]["data"]

    def test_the_scan_is_the_helpers_not_a_reimplementation(self):
        # The duty tests above pass against any behaviorally equivalent implementation; this
        # pins the wiring itself. The helper owns fetch-failure semantics and the changed
        # list; an inline curl loop re-drifts from it silently.
        block = self._block()
        self.assertIn("auditor/scripts/docs-diff.py", block,
                      "the block does not call docs-diff.py — the scan is a reimplementation")
        self.assertIn("--changed-out", block,
                      "the changed list is not routed through the helper's contract")
        self.assertNotIn("curl", block,
                         "an inline fetch survives beside the helper call")

    def test_the_four_states_reach_the_event_with_the_helpers_counts(self):
        sb = Sandbox()
        try:
            (sb.data / "ledgers").mkdir(exist_ok=True)
            changed = self._page(sb, "changed.html", "new text")
            unchanged = self._page(sb, "same.html", "same text")
            boot = self._page(sb, "fresh.html", "first sight")
            dead = (sb.root / "absent.html").as_uri()
            import hashlib as _h
            (sb.data / "ledgers" / "docs-citations.json").write_text(json.dumps({
                changed: {"rules": ["R01"], "quote": "was"},
                unchanged: {"rules": ["R02"], "quote": "still"},
                boot: {"rules": ["R03"], "quote": "new"},
                dead: {"rules": ["R04"], "quote": "gone"}}), encoding="utf-8")
            def entry(body):
                return {"hash": _h.sha256(body).hexdigest(),
                        "last_seen": "2026-01-01T00:00:00Z"}
            (sb.data / "ledgers" / "docs-hashes.json").write_text(json.dumps({
                changed: entry(b"old text"),
                unchanged: entry(b"same text"),
                dead: entry(b"old body")}), encoding="utf-8")
            r = self._run(sb)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            data = self._event(sb)
            self.assertEqual({"changed": 1, "bootstrapped": 1, "unchanged": 1,
                              "fetch_failed": 1}, data)
            store = json.loads((sb.data / "ledgers" / "docs-hashes.json").read_text())
            self.assertEqual(_h.sha256(b"old body").hexdigest(), store[dead]["hash"],
                             "a fetch failure overwrote the stored hash — the baseline for "
                             "detecting the real change is gone")
            self.assertEqual(_h.sha256(b"new text").hexdigest(), store[changed]["hash"])
        finally:
            sb.cleanup()

    def test_a_drifted_url_files_its_issue_and_a_known_one_gets_a_comment(self):
        sb = Sandbox()
        try:
            (sb.data / "ledgers").mkdir(exist_ok=True)
            import hashlib as _h
            drift = self._page(sb, "drift.html", "after")
            (sb.data / "ledgers" / "docs-citations.json").write_text(json.dumps({
                drift: {"rules": ["R09"], "quote": "before"}}), encoding="utf-8")
            (sb.data / "ledgers" / "docs-hashes.json").write_text(json.dumps({
                drift: {"hash": _h.sha256(b"before").hexdigest(),
                        "last_seen": "2026-01-01T00:00:00Z"}}), encoding="utf-8")
            r = self._run(sb)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertTrue(any("issue create" in c and "docs-drift" in c
                                for c in sb.gh_calls()),
                            f"no drift issue was filed: {sb.gh_calls()}")
            sb2 = Sandbox()
            try:
                (sb2.data / "ledgers").mkdir(exist_ok=True)
                drift2 = self._page(sb2, "drift.html", "after")
                (sb2.data / "ledgers" / "docs-citations.json").write_text(json.dumps({
                    drift2: {"rules": ["R09"], "quote": "before"}}), encoding="utf-8")
                (sb2.data / "ledgers" / "docs-hashes.json").write_text(json.dumps({
                    drift2: {"hash": _h.sha256(b"before").hexdigest(),
                             "last_seen": "2026-01-01T00:00:00Z"}}), encoding="utf-8")
                canned = sb2.root / "canned-issue-num"
                canned.write_text("12\n")
                r2 = sb2.run(self._block(), env={
                    "CODE_DIR": str(REPO), "RUNNER_TEMP": str(sb2.root),
                    "GH_CANNED_ISSUE_LIST": str(canned)})
                self.assertEqual(0, r2.returncode, r2.stdout + r2.stderr)
                self.assertTrue(any("issue comment 12" in c for c in sb2.gh_calls()),
                                f"the open issue was not commented: {sb2.gh_calls()}")
                self.assertFalse(any("issue create" in c for c in sb2.gh_calls()),
                                 "a duplicate drift issue was filed past the dedupe gate")
            finally:
                sb2.cleanup()
        finally:
            sb.cleanup()



    def test_the_commit_path_is_executed_and_stages_the_store(self):
        # Step-8 finding 6: the commit path was pinned by a regex, which cannot prove it
        # runs. Executed here against a real data checkout with a bare remote.
        import hashlib as _h
        import subprocess as _sp
        sb = Sandbox()
        try:
            (sb.data / "ledgers").mkdir(exist_ok=True)
            drift = self._page(sb, "drift.html", "after")
            (sb.data / "ledgers" / "docs-citations.json").write_text(json.dumps({
                drift: {"rules": ["R09"], "quote": "before"}}), encoding="utf-8")
            (sb.data / "ledgers" / "docs-hashes.json").write_text(json.dumps({
                drift: {"hash": _h.sha256(b"before").hexdigest(),
                        "last_seen": "2026-01-01T00:00:00Z"}}), encoding="utf-8")
            genv = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
            bare = sb.root / "data-remote.git"
            _sp.run(["git", "init", "-q", "--bare", "-b", "auditor-data", str(bare)],
                    check=True)
            _sp.run(["git", "init", "-q", "-b", "auditor-data", str(sb.data)], check=True)
            _sp.run(["git", "-C", str(sb.data), "remote", "add", "origin", str(bare)],
                    check=True)
            _sp.run(["git", "-C", str(sb.data), "add", "-A"], check=True)
            _sp.run(["git", "-C", str(sb.data), "commit", "-q", "-m", "seed"],
                    env={**os.environ, **genv}, check=True)
            _sp.run(["git", "-C", str(sb.data), "push", "-q", "-u", "origin", "auditor-data"],
                    check=True)
            r = self._run(sb)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            commit_block = extract(WF_DIR / "auditor-docs-diff.yml", "commit-logic",
                                   "docs-diff")
            self.assertIsNotNone(commit_block,
                                 "no commit-logic:docs-diff marker — the commit path is "
                                 "not executable in tests")
            rc = sb.run(commit_block, env={"CODE_DIR": str(REPO), **genv})
            self.assertEqual(0, rc.returncode, rc.stdout + rc.stderr)
            shown = _sp.run(["git", "-C", str(sb.data), "show", "--name-only",
                             "--format=", "HEAD"], capture_output=True, text=True)
            self.assertIn("ledgers/docs-hashes.json", shown.stdout,
                          "the refreshed hash store never reached the commit")
        finally:
            sb.cleanup()


class TestSuppressionsWiring(unittest.TestCase):
    """E8.6 (vibe-63): the scan is scan-suppressions.py's, and the corpus reaches the branch.

    The block used to reimplement search, fetch, and the override grammar inline — and never
    produced feedback/suppressions.jsonl, the corpus rule-health's metrics consume. The
    helper owns the scan (pagination, incomplete-results refusal, blob-addressed fetch,
    (repo, sha, path) dedupe, the shared parse-suppressions grammar); the workflow keeps its
    ledger duties — downstream_suppression disagreements with the SCHEMAS enum, derived from
    the helper's structured records, and the summary event — and the commit step must carry
    the corpus file.
    """

    CONFIG = ("---\nrule_overrides:\n  R01:\n    suppress: true\n"
              "    reason: too noisy\n  R02:\n    max_penalty: 5\n"
              "  R03:\n    threshold: 2\n  R04:\n    override: reworded\n"
              "  nl:R1: suppress\n---\nbody\n")

    def _canned(self, sb):
        import base64 as _b
        search = sb.root / "canned-search.json"
        search.write_text(json.dumps({
            "total_count": 1, "incomplete_results": False,
            "items": [{"repository": {"full_name": "acme/lib"},
                       "path": ".vibe-suite-audit.yml", "sha": "blob123"}]}))
        blob = sb.root / "canned-blob.json"
        blob.write_text(json.dumps({
            "sha": "blob123", "encoding": "base64",
            "content": _b.b64encode(self.CONFIG.encode()).decode()}))
        commits = sb.root / "canned-commits.json"
        commits.write_text(json.dumps([{"sha": "deadbeef"}]))
        at_ref = sb.root / "canned-contents-at-ref.json"
        at_ref.write_text(json.dumps({"sha": "blob123"}))
        m = sb.root / "canned-map"
        m.write_text("api -X GET search/code\t" + str(search) + "\n"
                     "api repos/acme/lib/git/blobs/blob123\t" + str(blob) + "\n"
                     "api repos/acme/lib/contents/.vibe-suite-audit.yml\t" + str(at_ref) + "\n"
                     "api repos/acme/lib/commits\t" + str(commits) + "\n")
        return {"GH_CANNED_MAP": str(m), "GITHUB_REPOSITORY": "example/auditor-repo",
                "CODE_DIR": str(REPO)}

    def _block(self):
        b = extract(WF_DIR / "auditor-suppressions.yml", "logic", "suppressions")
        assert b is not None
        return b

    def test_the_scan_is_the_helpers_and_the_corpus_is_produced(self):
        block = self._block()
        self.assertIn("auditor/scripts/scan-suppressions.py", block,
                      "the block does not call scan-suppressions.py — the scan is a "
                      "reimplementation and the corpus is never produced")
        sb = Sandbox()
        try:
            (sb.data / "feedback").mkdir(exist_ok=True)
            r = sb.run(block, env=self._canned(sb))
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            corpus = sb.data / "feedback" / "suppressions.jsonl"
            self.assertTrue(corpus.is_file(), "no corpus was written")
            recs = [json.loads(l) for l in corpus.read_text().splitlines() if l]
            self.assertEqual(1, len(recs))
            self.assertEqual(["R01", "R02", "R03", "R04", "nl:R1"], recs[0]["rule_ids"])
            dis = [json.loads(l) for l in
                   (sb.data / "ledgers" / "disagreements.jsonl").read_text().splitlines()
                   if l]
            supp = [d for d in dis if d.get("event") == "downstream_suppression"]
            derived = {(d["data"]["rule_id"], d["data"]["suppression_type"])
                       for d in supp}
            # Every SCHEMAS section-5 enum, the namespaced id, and the inline scalar form
            # (Step-8 finding 2): is_rule_id rejecting nl:R1 or a scalar override producing
            # no event silently starves the disagreement ledger.
            self.assertEqual({("R01", "suppress"), ("R02", "max_penalty"),
                              ("R03", "threshold_adjustment"), ("R04", "rule_override"),
                              ("nl:R1", "suppress")}, derived,
                             f"the derivation lost enum kinds or ids: {sorted(derived)}")
            by_rule = {d["data"]["rule_id"]: d["data"] for d in supp}
            self.assertEqual("too noisy", by_rule["R01"].get("reason_given"))
            for d in supp:
                self.assertEqual("deadbeef", d["data"]["commit_sha"])
            events = [json.loads(l) for l in
                      (sb.data / "ledgers" / "events.jsonl").read_text().splitlines() if l]
            self.assertTrue(any(e.get("event") == "suppression_scan_complete"
                                for e in events))
        finally:
            sb.cleanup()


    def test_an_unverifiable_blob_at_the_commit_derives_nothing(self):
        # The commit_sha binds the observation only if the observed blob actually exists at
        # that path in that commit; otherwise the record would carry a false provenance.
        sb = Sandbox()
        try:
            (sb.data / "feedback").mkdir(exist_ok=True)
            env = self._canned(sb)
            at_ref = sb.root / "canned-contents-at-ref.json"
            at_ref.write_text(json.dumps({"sha": "a-different-blob"}))
            r = sb.run(self._block(), env=env)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            dis = [json.loads(l) for l in
                   (sb.data / "ledgers" / "disagreements.jsonl").read_text().splitlines()
                   if l]
            self.assertEqual([], [d for d in dis
                                  if d.get("event") == "downstream_suppression"],
                             "a disagreement was derived with an unverified commit_sha — "
                             "false provenance")
        finally:
            sb.cleanup()

    def test_a_rescan_of_the_same_blob_appends_nothing(self):
        sb = Sandbox()
        try:
            (sb.data / "feedback").mkdir(exist_ok=True)
            env = self._canned(sb)
            r1 = sb.run(self._block(), env=env)
            self.assertEqual(0, r1.returncode, r1.stdout + r1.stderr)
            corpus = sb.data / "feedback" / "suppressions.jsonl"
            dis = sb.data / "ledgers" / "disagreements.jsonl"
            n_corpus = len(corpus.read_text().splitlines())
            n_dis = len(dis.read_text().splitlines())
            r2 = sb.run(self._block(), env=env)
            self.assertEqual(0, r2.returncode, r2.stdout + r2.stderr)
            self.assertEqual(n_corpus, len(corpus.read_text().splitlines()),
                             "the (repo, sha, path) dedupe did not hold across runs")
            self.assertEqual(n_dis, len(dis.read_text().splitlines()),
                             "a duplicate disagreement was appended for an unchanged blob")
        finally:
            sb.cleanup()


    def _commit_block(self):
        b = extract(WF_DIR / "auditor-suppressions.yml", "commit-logic", "suppressions")
        assert b is not None, "no commit-logic:suppressions marker — the commit path is " \
                              "not extractable and its behavior rests on reading"
        return b

    GIT_IDENT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

    def _seed_git(self, sb):
        # Seed the checkout BEFORE the scan runs: the production data-branch checkout
        # predates the run's writes, and seeding afterwards swallows the scan's products
        # into the seed commit — the commit block then finds nothing to stage and every
        # assertion reads the seed (the vacuity the round-1 verify caught).
        import subprocess as _sp
        bare = sb.root / "data-remote.git"
        _sp.run(["git", "init", "-q", "--bare", "-b", "auditor-data", str(bare)], check=True)
        _sp.run(["git", "init", "-q", "-b", "auditor-data", str(sb.data)], check=True)
        _sp.run(["git", "-C", str(sb.data), "remote", "add", "origin", str(bare)], check=True)
        _sp.run(["git", "-C", str(sb.data), "add", "-A"], check=True)
        _sp.run(["git", "-C", str(sb.data), "commit", "-q", "-m", "seed"], env={
            **os.environ, **self.GIT_IDENT}, check=True)
        _sp.run(["git", "-C", str(sb.data), "push", "-q", "-u", "origin", "auditor-data"],
                check=True)

    def _run_commit(self, sb):
        return sb.run(self._commit_block(), env={"CODE_DIR": str(REPO), **self.GIT_IDENT})

    def test_the_first_clean_scan_still_commits(self):
        # Step-8 finding 4: a zero-hit scan wrote no corpus and the unconditional
        # `git add feedback/suppressions.jsonl` failed the first production run. The logic
        # block now materializes the empty corpus; the commit path is EXECUTED here, not
        # read.
        sb = Sandbox()
        try:
            (sb.data / "feedback").mkdir(exist_ok=True)
            canned_dir = Path(tempfile.mkdtemp(prefix="supp-canned-"))
            self.addCleanup(shutil.rmtree, canned_dir, True)
            canned = canned_dir / "empty-search.json"
            canned.write_text(json.dumps({"total_count": 0, "incomplete_results": False,
                                          "items": []}))
            m = canned_dir / "map"
            m.write_text("api -X GET search/code\t" + str(canned) + "\n")
            self._seed_git(sb)
            r = sb.run(self._block(), env={"GH_CANNED_MAP": str(m), "CODE_DIR": str(REPO),
                                           "GITHUB_REPOSITORY": "example/auditor-repo"})
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertTrue((sb.data / "feedback" / "suppressions.jsonl").is_file(),
                            "a clean scan left no corpus — the commit path fails on the "
                            "first real run")
            rc = self._run_commit(sb)
            self.assertEqual(0, rc.returncode,
                             f"the commit path failed after a clean scan: {rc.stdout} "
                             f"{rc.stderr}")
            import subprocess as _sp
            shown = _sp.run(["git", "-C", str(sb.data), "show", "--name-only",
                             "--format=", "HEAD"], capture_output=True, text=True)
            self.assertIn("feedback/suppressions.jsonl", shown.stdout,
                          "the first clean run's commit does not carry the materialized "
                          "corpus — HEAD is still the seed")
        finally:
            sb.cleanup()

    def test_the_commit_path_stages_the_corpus_with_new_records(self):
        sb = Sandbox()
        try:
            (sb.data / "feedback").mkdir(exist_ok=True)
            self._seed_git(sb)
            env = self._canned(sb)
            r = sb.run(self._block(), env=env)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            rc = self._run_commit(sb)
            self.assertEqual(0, rc.returncode, rc.stdout + rc.stderr)
            import subprocess as _sp
            shown = _sp.run(["git", "-C", str(sb.data), "show", "--name-only",
                             "--format=", "HEAD"], capture_output=True, text=True)
            for f in ("feedback/suppressions.jsonl", "ledgers/disagreements.jsonl"):
                self.assertIn(f, shown.stdout,
                              f"the scan produced {f} but the commit does not carry it — "
                              f"HEAD is still the seed")
            log = _sp.run(["git", "-C", str(sb.data), "log", "--oneline"],
                          capture_output=True, text=True)
            self.assertEqual(2, len(log.stdout.splitlines()),
                             "no commit landed on top of the seed")
        finally:
            sb.cleanup()

    def test_the_commit_step_carries_the_corpus(self):
        text = (WF_DIR / "auditor-suppressions.yml").read_text()
        self.assertRegex(
            text, r"git add[^\n]*feedback/suppressions\.jsonl",
            "the commit step does not stage feedback/suppressions.jsonl — the corpus is "
            "produced and then left behind on the runner")



class TestLedgerRoundTrips(unittest.TestCase):
    """E8.6 (vibe-63): a record written by the producing path is read by the consuming path.

    disagreements.jsonl and vocab-advisories.jsonl each had producer-side tests and
    consumer-side tests that never met — a drift in the shared record shape would pass both
    halves while the join silently broke. Each round-trip here writes through the workflow
    block that produces the ledger and reads through the helper that consumes it.
    (feedback/suppressions.jsonl already has its round-trip in the rulebook helpers suite.)
    """

    def test_a_self_false_positive_survives_from_sidecar_to_rule_health(self):
        sb = Sandbox()
        try:
            sidecar = sb.data / "audits" / "acme-claude-toolkit.findings.jsonl"
            rows = [
                {"rule_id": "R04", "file": "a.md", "severity": "medium", "line": 3,
                 "false_positive": True, "fp_reason": "fires on fixture text",
                 "evidence": "e1"},
                {"rule_id": "R04", "file": "b.md", "severity": "medium", "line": 7,
                 "evidence": "e2"},
            ]
            sidecar.write_text("".join(json.dumps(r) + "\n" for r in rows),
                               encoding="utf-8")
            block = extract(WF_DIR / "auditor-audit.yml", "stage-logic", "audit")
            self.assertIsNotNone(block)
            r = sb.run(block, env={"SCORE": "64", "SECURITY": "CLEAR"})
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            dis = [json.loads(l) for l in
                   (sb.data / "ledgers" / "disagreements.jsonl").read_text().splitlines()
                   if l]
            fps = [d for d in dis if d.get("event") == "self_false_positive"]
            self.assertEqual(1, len(fps), "the producing path wrote no disagreement")
            hr = subprocess.run(
                ["python3", str(REPO / "auditor" / "scripts" / "rule-health.py"),
                 "--data-dir", str(sb.data), "--generated-at", "2026-08-13T00:00:00Z"],
                capture_output=True, text=True)
            self.assertEqual(0, hr.returncode, hr.stdout + hr.stderr)
            log = json.loads((sb.data / "feedback" / "log.json").read_text())
            r04 = next((row for row in log.get("rules", [])
                        if row.get("rule_id") == "R04"), None)
            self.assertIsNotNone(r04, f"R04 never reached the feedback log: {log}")
            self.assertGreaterEqual(r04.get("false_positives", 0), 1,
                                    "the consumer did not count the produced "
                                    "self_false_positive — the round trip is broken")
        finally:
            sb.cleanup()

    def test_a_vocab_advisory_survives_from_sidecar_to_dashboard(self):
        sb = Sandbox()
        try:
            record = {"rule_id": "VOCAB-GENERAL-DRIFT",
                      "terms": ["invoke", "trigger"], "disposition": "drift",
                      "confidence": "high", "term_freq": {"invoke": 4, "trigger": 3},
                      "term_files": {"invoke": ["a.md"], "trigger": ["b.md"]},
                      "files_affected": 2, "suggested_canonical": "invoke",
                      "evidence": "same concept, two verbs"}
            (sb.data / "audits").mkdir(exist_ok=True)
            (sb.data / "audits" / "acme-claude-toolkit.vocab-advisories.jsonl").write_text(
                json.dumps(record) + "\n", encoding="utf-8")
            block = extract(WF_DIR / "auditor-vocab-drift.yml", "logic", "vocab-drift")
            self.assertIsNotNone(block)
            fixture = sb.root / "target.json"
            fixture.write_text(json.dumps({"repo": {"full_name": "acme/claude-toolkit",
                                                    "artifact_count": 12,
                                                    "head_sha": "cafebabe"}}))
            r = sb.run(block, env={"FIXTURE": str(fixture), "CODE_DIR": str(REPO)})
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            ledger = sb.data / "ledgers" / "vocab-advisories.jsonl"
            self.assertTrue(ledger.is_file(), "the producing path wrote no ledger")
            self.assertIn("VOCAB-GENERAL-DRIFT", ledger.read_text())
            dr = subprocess.run(
                ["python3", str(REPO / "auditor" / "scripts" / "render-dashboard.py"),
                 "--data-dir", str(sb.data),
                 "--generated-at", "2026-08-13T00:00:00Z"],
                capture_output=True, text=True)
            self.assertEqual(0, dr.returncode, dr.stdout + dr.stderr)
            reports = list((sb.data / "reports").rglob("*")) if (
                sb.data / "reports").is_dir() else []
            rendered = "".join(p.read_text(encoding="utf-8", errors="replace")
                               for p in reports if p.is_file())
            self.assertIn("invoke", rendered,
                          "the consumer never surfaced the produced advisory — the round "
                          "trip is broken")
        finally:
            sb.cleanup()



class TestMirrorBearingCommitPaths(unittest.TestCase):
    """E8.6 (vibe-63): a commit that edits skills/rules/SKILL.md carries its mirror.

    codex/MIRROR-MANIFEST.json maps the rules skill to codex/skills/vibe-rules/SKILL.md;
    the --mirrors gate fails a stale mirror. Two workflows commit edits to that source —
    cite-exemplars (the citation applier) and refine-rules (the model's reviewed patch) —
    and neither regenerated the mirror, so every real run would have landed main in a state
    the release gate refuses. The ordering pinned here: source edit, THEN mirror-sync
    generate, THEN the commit (whose -am form stages every tracked modification — source,
    mirror, and manifest together).
    """

    CASES = (
        ("auditor-cite-exemplars.yml", "propose-rule-citations.py"),
        ("auditor-refine-rules.yml", "git apply refine-out/rules.patch"),
    )


    def test_the_cite_exemplars_publish_path_executes_end_to_end(self):
        """Step-8 finding 6: index comparisons cannot prove the apply→regen→commit sequence
        runs. Executed here on a copy of the real repository: the applier writes citations,
        mirror-sync regenerates, and the commit carries source, mirror and manifest."""
        import shutil as _sh
        import subprocess as _sp
        import tempfile as _tf
        with _tf.TemporaryDirectory(prefix="cite-publish-") as tmp:
            code = Path(tmp) / "code"
            _sh.copytree(REPO, code, symlinks=True,
                         ignore=_sh.ignore_patterns(".git", "node_modules", "__pycache__"))
            genv = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}
            _sp.run(["git", "init", "-q", "-b", "main", str(code)], check=True)
            _sp.run(["git", "-C", str(code), "add", "-A"], check=True)
            _sp.run(["git", "-C", str(code), "commit", "-q", "-m", "seed"],
                    env={**os.environ, **genv}, check=True)
            data = Path(tmp) / "data"
            (data / "exemplars").mkdir(parents=True)
            (data / "exemplars" / "acme-widget.md").write_text(
                "---\nslug: acme-widget\nrepo: acme/widget\naudited: 2026-08-01\n"
                "commit_sha: abc\nscore: 95\nexemplifies: [R01]\n---\nbody\n",
                encoding="utf-8")
            block = extract(WF_DIR / "auditor-cite-exemplars.yml", "publish-logic",
                            "cite-exemplars")
            self.assertIsNotNone(block, "no publish-logic:cite-exemplars marker")
            script = "set -euo pipefail\ncd \"$CODE_DIR\"\n" + block
            r = _sp.run(["bash", "-c", script], capture_output=True, text=True,
                        env={**os.environ, **genv, "CODE_DIR": str(code),
                             "DATA_DIR": str(data), "DATE": "2026-08-13",
                             "VIBE_EXEMPLAR_URL_PREFIX":
                                 "https://github.com/xinquan568/vibe-suite/blob/"
                                 "auditor-data/exemplars"},
                        cwd=str(code))
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            shown = _sp.run(["git", "-C", str(code), "show", "--name-only", "--format=",
                             "HEAD"], capture_output=True, text=True)
            for expected in ("skills/rules/SKILL.md", "codex/skills/vibe-rules/SKILL.md",
                             "codex/MIRROR-MANIFEST.json"):
                self.assertIn(expected, shown.stdout,
                              f"the publish commit does not carry {expected} — the mirror "
                              f"pair would land stale")

    def test_mirror_regeneration_sits_between_the_edit_and_the_commit(self):
        for wf, edit_marker in self.CASES:
            with self.subTest(workflow=wf):
                text = (WF_DIR / wf).read_text(encoding="utf-8")
                edit = text.index(edit_marker)
                REGEN_CMD = 'scripts/mirror-sync.py" generate'
                self.assertIn(REGEN_CMD, text,
                              f"{wf} commits a mirrored source and never regenerates the "
                              f"mirror — a real run lands a stale mirror on main")
                regen = text.index(REGEN_CMD)
                commit = text.index("git commit", edit)
                self.assertLess(edit, regen,
                                f"{wf}: the mirror regenerates before the source edit — "
                                f"the mirror captures the OLD content")
                self.assertLess(regen, commit,
                                f"{wf}: the commit precedes mirror regeneration — the "
                                f"mirror change is left uncommitted")
                if wf == "auditor-refine-rules.yml":
                    # Step-8 finding 1: the refine patch is MODEL OUTPUT, so staging is
                    # EXPLICIT — exactly the guarded source, the mirror, and the manifest;
                    # -am would let anything the apply escaped ride into the commit.
                    self.assertIn('git add -- "$ALLOWED" codex/skills/vibe-rules/SKILL.md '
                                  "codex/MIRROR-MANIFEST.json", text,
                                  f"{wf}: staging is not the explicit guarded set")
                    self.assertIn('ALLOWED="skills/rules/SKILL.md"', text,
                                  f"{wf}: the allowlist variable does not pin the rulebook")
                else:
                    self.assertRegex(text[commit:commit + 120], r"git commit -am",
                                     f"{wf}: the commit does not stage all tracked "
                                     f"modifications, so the regenerated mirror and "
                                     f"manifest may be left behind")


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


class TestBatchProcessorWiring(unittest.TestCase):
    """vibe-167: phase 3's batch selection is batch-process.py's duty.

    The workflow delegates selection + labeling + dispatch to the helper — the one
    helper whose every gh call touches a third party's repository — and keeps only
    the label-removal post-pass inline, because the helper adds labels and removes
    none. Dry run must issue NO mutating call end to end."""

    WF = REPO / "auditor" / "workflows" / "auditor-batch-processor.yml"

    def setUp(self):
        self.sb = Sandbox(registry=None)
        self.addCleanup(self.sb.cleanup)
        (self.sb.data / "registry" / "repos.json").write_text(json.dumps(
            {"repos": {"acme/w": {"status": "discovered", "issue": 12}}}))
        self.block = extract(self.WF, "logic", "batch-select")
        self.assertIsNotNone(self.block,
                             "no logic:batch-select marker in auditor-batch-processor.yml")
        canned = self.sb.root / "both-labels.json"
        # real gh newline-terminates its output; a fixture that does not makes the
        # consuming read-loop drop its only line
        canned.write_text(json.dumps([{"number": 12, "title": "Audit candidate: acme/w"}]) + "\n")
        self.env = {"CODE_DIR": str(REPO), "BATCH_SIZE": "5",
                    "GH_CANNED_ISSUE_LIST": str(canned)}

    def test_a_dry_run_issues_no_mutating_call(self):
        r = self.sb.run("set -euo pipefail\n" + self.block,
                        env={**self.env, "DRY_RUN": "true"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        mutating = [c for c in self.sb.gh_calls()
                    if "issue edit" in c or "workflow run" in c]
        self.assertEqual(mutating, [],
                         "a dry run reached a third-party repository")
        self.assertIn("would run", r.stdout, "the helper's dry-run preview is the log")

    def test_apply_labels_dispatches_and_removes_the_candidate_label(self):
        r = self.sb.run("set -euo pipefail\n" + self.block,
                        env={**self.env, "DRY_RUN": "false"})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        calls = self.sb.gh_calls()
        self.assertTrue(any("issue edit 12" in c and "--add-label audit-ready" in c
                            for c in calls),
                        f"the helper did not label the eligible issue: {calls}")
        self.assertTrue(any("workflow run auditor-audit.yml" in c for c in calls),
                        f"the helper did not dispatch the stage workflow: {calls}")
        self.assertTrue(any("--remove-label audit-candidate" in c for c in calls),
                        f"the inline post-pass did not retire the candidate label: {calls}")


class TestTrackRefreshWiring(unittest.TestCase):
    """vibe-167: the PR-body metadata parse is parse-pr-metadata.py's duty — the
    helper is the documented second implementation of the §9 block contract, and the
    workflow now feeds from it instead of carrying a third copy inline."""

    WF = REPO / "auditor" / "workflows" / "auditor-track.yml"

    def setUp(self):
        self.sb = Sandbox(registry=None)
        self.addCleanup(self.sb.cleanup)
        (self.sb.data / "registry" / "repos.json").write_text(json.dumps(
            {"repos": {"acme/w": {"status": "contributed", "pipeline_prs": [7]}}}))
        self.block = extract(self.WF, "logic", "track-refresh")
        self.assertIsNotNone(self.block,
                             "no logic:track-refresh marker in auditor-track.yml")

    def _snap(self, body):
        return {"state": "MERGED", "mergedAt": "2026-08-01T00:00:00Z",
                "closedAt": None, "updatedAt": "2026-08-01T00:00:00Z",
                "body": body, "comments": [], "statusCheckRollup": []}

    def _run_with_body(self, body):
        canned = self.sb.root / "pr-view.json"
        canned.write_text(json.dumps(self._snap(body)) + "\n")
        return self.sb.run("set -euo pipefail\n" + self.block,
                           env={"CODE_DIR": str(REPO),
                                "GH_CANNED_PR_VIEW": str(canned)})

    def test_the_block_delegates_to_the_helper(self):
        self.assertIn("parse-pr-metadata.py", self.block,
                      "the refresh still parses the metadata block inline — three "
                      "implementations of one contract instead of two")

    def test_metadata_fingerprints_reach_the_registry(self):
        body = ('done\n<!-- vibe-suite-auditor-meta-begin '
                '{"findings":[{"fingerprint":"sha256:ab","rule_id":"R04"}]} '
                'vibe-suite-auditor-meta-end -->')
        r = self._run_with_body(body)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        pr = self.sb.registry()["repos"]["acme/w"]["prs"]["7"]
        self.assertEqual(pr["fingerprints"], ["sha256:ab"])
        self.assertEqual(pr["rule_ids"], ["R04"])
        self.assertEqual(pr["state"], "MERGED")

    def test_a_body_without_a_block_keeps_prior_provenance(self):
        (self.sb.data / "registry" / "repos.json").write_text(json.dumps(
            {"repos": {"acme/w": {"status": "contributed", "pipeline_prs": [7],
                                  "prs": {"7": {"number": 7, "outcome": None,
                                                "fingerprints": ["sha256:old"],
                                                "rule_ids": ["R05"],
                                                "stale_90d_emitted": False}}}}}))
        r = self._run_with_body("no block here")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        pr = self.sb.registry()["repos"]["acme/w"]["prs"]["7"]
        self.assertEqual(pr["fingerprints"], ["sha256:old"],
                         "a snapshot refresh must never wipe backfilled provenance")


class TestDailyReportWiring(unittest.TestCase):
    """vibe-167: the report is generate-daily-report.py's duty — the block caches the
    live inputs into the helper's --inputs seam, and the report_generated event takes
    the HELPER'S printed output path (the filename contract is the helper's)."""

    WF = REPO / "auditor" / "workflows" / "auditor-daily-report.yml"

    def setUp(self):
        self.sb = Sandbox(registry=None)
        self.addCleanup(self.sb.cleanup)
        (self.sb.data / "registry" / "repos.json").write_text(json.dumps(
            {"repos": {"acme/w": {"status": "audited", "stars": 10,
                                  "prs": {"1": {"outcome": "merged"}}}}}))
        (self.sb.data / "feedback").mkdir(exist_ok=True)
        (self.sb.data / "feedback" / "log.json").write_text(json.dumps(
            {"rules": [{"rule_id": "R04", "hits": 3, "merged": 1,
                        "applied_separately": 0}]}))
        self.block = extract(self.WF, "stage-logic", "daily-report")
        self.assertIsNotNone(self.block)

    def test_the_helper_renders_and_the_event_carries_its_path(self):
        import time as _time
        r = self.sb.run("set -euo pipefail\n" + self.block,
                        env={"CODE_DIR": str(REPO)})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("generate-daily-report.py", self.block,
                      "the report is still rendered inline")
        day = _time.strftime("%Y-%m-%d", _time.gmtime())
        report = self.sb.data / "reports" / f"{day}.md"
        self.assertTrue(report.is_file(),
                        "the helper's output name (<date>.md) is the contract; the "
                        "inline daily-<date>.md name lost")
        text = report.read_text()
        self.assertIn("# Daily report —", text, "the helper's renderer owns the body")
        self.assertIn("audit-candidate", text,
                      "the label census must survive the delegation (activity items)")
        events = [e for e in self.sb.events() if e.get("event") == "report_generated"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"]["report"], f"reports/{day}.md",
                         "the event path must be the helper's, not a second spelling")


class TestVocabFingerprintWiring(unittest.TestCase):
    """vibe-167: the advisory digest is compute-vocab-fingerprint.sh's duty; the
    sourced function and the retired inline formula must agree to the byte."""

    WF = REPO / "auditor" / "workflows" / "auditor-vocab-drift.yml"
    HELPER = REPO / "auditor" / "scripts" / "compute-vocab-fingerprint.sh"

    def test_the_block_sources_the_helper_not_an_inline_digest(self):
        block = extract(self.WF, "logic", "vocab-drift")
        self.assertIsNotNone(block)
        self.assertIn("compute-vocab-fingerprint.sh", block)
        self.assertIn("compute_vocab_fingerprint", block)
        self.assertNotIn("shasum", block,
                         "an inline digest beside the sourced function is the two-"
                         "implementations defect this wiring retires")

    def test_the_function_matches_the_documented_formula_to_the_byte(self):
        import hashlib
        advisory = {"terms": ["beta", "alpha"], "disposition": "merge"}
        expected = "sha256:" + hashlib.sha256(
            "acme/w|VOCAB|alpha,beta|merge\n".encode()).hexdigest()
        script = (f'. "{self.HELPER}"\n'
                  f"printf '%s' '{json.dumps(advisory)}' "
                  f'| compute_vocab_fingerprint "acme/w"\n')
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), expected)


class TestDiscoverFilterWiring(unittest.TestCase):
    """vibe-167: vendor/CLA-owner filtering is vendor_default_filter.py's duty — the
    helper's deny knowledge replaces the four-owner inline list, before audit cost."""

    WF = REPO / "auditor" / "workflows" / "auditor-discover.yml"

    def setUp(self):
        self.sb = Sandbox(registry=None)
        self.addCleanup(self.sb.cleanup)
        (self.sb.data / "registry" / "repos.json").write_text(json.dumps({"repos": {}}))
        (self.sb.data / "articles").mkdir(exist_ok=True)
        self.block = extract(self.WF, "logic", "discover-search")
        self.assertIsNotNone(self.block,
                             "no logic:discover-search marker in auditor-discover.yml")
        search = [{"full_name": "anthropics/claude-code", "stargazers_count": 9000,
                   "archived": False, "pushed_at": "2026-08-01T00:00:00Z",
                   "description": "d", "default_branch": "main"},
                  {"full_name": "google/genai-toolbox", "stargazers_count": 5000,
                   "archived": False, "pushed_at": "2026-08-01T00:00:00Z",
                   "description": "d", "default_branch": "main"},
                  {"full_name": "indie/plugin", "stargazers_count": 900,
                   "archived": False, "pushed_at": "2026-08-01T00:00:00Z",
                   "description": "d", "default_branch": "main"}]
        searchfile = self.sb.root / "search.json"
        searchfile.write_text(json.dumps({"items": search}) + "\n")
        tree = self.sb.root / "tree.json"
        tree.write_text(json.dumps(
            {"tree": [{"type": "blob", "path": ".claude/commands/x.md"}]}) + "\n")
        mapfile = self.sb.root / "canned.map"
        mapfile.write_text(f"api -X GET search/repositories\t{searchfile}\n"
                           f"api repos/\t{tree}\n")
        self.env = {"CODE_DIR": str(REPO), "GH_CANNED_MAP": str(mapfile),
                    "CANDIDATE_DIR": str(self.sb.root / "cands")}

    def test_vendor_and_cla_owners_are_dropped_by_the_helper(self):
        r = self.sb.run("set -euo pipefail\n" + self.block, env=self.env)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("vendor_default_filter.py", self.block,
                      "discovery still filters with the inline owner list")
        staged = sorted((self.sb.root / "cands").glob("candidate-*.json"))
        names = [json.loads(p.read_text())["repo"]["full_name"] for p in staged]
        self.assertEqual(names, ["indie/plugin"],
                         f"the helper's deny knowledge must drop the vendor and "
                         f"CLA-gated owners at discovery: {names}")


class TestRenderDashboardWiring(unittest.TestCase):
    """vibe-167: dashboard + rule docs are render-dashboard.py's duty; the block keeps
    counting for the event (observability) and the docs-clobber guard, and delegates
    every byte of HTML."""

    WF = REPO / "auditor" / "workflows" / "auditor-render-dashboard.yml"

    def setUp(self):
        self.sb = Sandbox(registry=None)
        self.addCleanup(self.sb.cleanup)
        (self.sb.data / "registry" / "repos.json").write_text(json.dumps(
            {"repos": {"acme/w": {"status": "audited"}}}))
        self.block = extract(self.WF, "logic", "render-dashboard")
        self.assertIsNotNone(self.block)

    def test_the_helper_renders_and_the_event_still_fires(self):
        r = self.sb.run("set -euo pipefail\n" + self.block,
                        env={"CODE_DIR": str(REPO)})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("render-dashboard.py", self.block,
                      "the dashboard is still rendered inline")
        self.assertTrue((self.sb.data / "reports" / "dashboard.html").is_file())
        self.assertTrue((self.sb.data / "reports" / "docs" / "index.html").is_file())
        events = [e for e in self.sb.events() if e.get("event") == "dashboard_rendered"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"]["report"], "reports/dashboard.html")

    def test_a_foreign_docs_build_is_not_clobbered(self):
        docs = self.sb.data / "reports" / "docs"
        docs.mkdir(parents=True)
        (docs / "index.html").write_text("<html>the real docs build</html>")
        r = self.sb.run("set -euo pipefail\n" + self.block,
                        env={"CODE_DIR": str(REPO)})
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assertIn("the real docs build", (docs / "index.html").read_text(),
                      "a docs build that is not ours was overwritten")
