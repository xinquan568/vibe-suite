# SPDX-License-Identifier: ISC
"""E8.2 schema contract tests (vibe-59, plan task T5) — emitters AND consumers.

`auditor/SCHEMAS.md` is the contract. This suite executes the *current* production paths —
the marked logic blocks and the readers' own extracted jq programs — against fixtures built
to the contract, so every failure is a behavioral disagreement between the tree and the
contract, never a missing-scaffolding artifact.

Emitter side: the finding fingerprint known vector (§3), the required finding fields (§2),
the event envelope on every appended record (§7), the vocab advisory fields and its sorted-
terms fingerprint (§6), and the canonical audited-SHA registry key shared by the audit
writer and the exemplar reader (§1/§10).

Consumer side: every ledger reader is driven by an *enveloped* fixture and asserted to find
the records it is contracted to join on (§7, §12). A reader that resolves flat fields sees
nothing under the envelope; a writer that appends a flat record into an enveloped ledger
mixes schemas in one file, which §13 forbids outright.
"""
import hashlib
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

TARGET_REPO = "acme/claude-toolkit"
ENVELOPE_KEYS = ("timestamp", "workflow", "event", "run_id", "run_number", "data")

# §2 — the required field set on every ledgers/findings.jsonl record.
FINDING_REQUIRED = (
    "event", "timestamp", "audit_run_id", "repo", "commit_sha", "fingerprint", "category",
    "rule_id", "file", "line", "severity", "confidence", "evidence", "penalty", "pattern",
    "description", "false_positive", "suggested_fix",
)
# §6 — the required field set on every ledgers/vocab-advisories.jsonl record.
VOCAB_REQUIRED = (
    "event", "timestamp", "audit_run_id", "repo", "commit_sha", "fingerprint", "disposition",
    "confidence", "terms", "rule_id",
)

GH_STUB = """#!/usr/bin/env bash
echo "gh $*" >> "$GH_LOG"
key="GH_CANNED_$(echo "$1_$2" | tr ' -' '__' | tr '[:lower:]' '[:upper:]')"
if [ -n "${!key:-}" ]; then cat "${!key}"; fi
exit 0
"""

VOCAB_SIDECAR = {
    "rule_id": "VOCAB-NOUN-DRIFT",
    "terms": ["directive", "command"],
    "disposition": "drift",
    "verdict": "drift",
    "confidence": "medium",
    "term_freq": {"command": 9, "directive": 4},
    "term_files": {"command": ["commands/a.md"], "directive": ["agents/b.md"]},
    "files_affected": 2,
    "suggested_canonical": "command",
    "evidence": "both terms head the same object position in adjacent files",
}


# --- fingerprint reference implementations (computed here, never imported) ------------

def finding_fingerprint(repo, file, rule_id, pattern, line):
    """§3: sha256 over repo|file|rule_id|pattern|line with a MANDATORY trailing newline."""
    joined = "|".join([repo, file, rule_id, pattern, str(line)]) + "\n"
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


def vocab_fingerprint(repo, terms, disposition):
    """§6: sha256 over repo|VOCAB|sorted-comma-joined-terms|disposition + trailing newline."""
    joined = "|".join([repo, "VOCAB", ",".join(sorted(terms)), disposition]) + "\n"
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()


# --- harness (mirrors tests/test_auditor_state_machine.py) ----------------------------

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
        lines.append(ln[indent:] if indent and ln.startswith(" " * indent) else ln)
    return "\n".join(lines)


def jq_program(workflow, needle):
    """Return the single-quoted jq program in `workflow` that contains `needle`.

    The reader is never retyped here: the production text is what runs.
    """
    text = (WF_DIR / workflow).read_text()
    m = re.search(r"'([^']*" + re.escape(needle) + r"[^']*)'", text, re.S)
    return m.group(1) if m else None


def run_jq(program, path, args=(), slurp=True, raw=True):
    cmd = ["jq"]
    if slurp:
        cmd.append("-s")
    if raw:
        cmd.append("-r")
    cmd.extend(args)
    cmd.extend([program, str(path)])
    return subprocess.run(cmd, capture_output=True, text=True)


def envelope(event, data, timestamp="2026-08-01T00:00:00Z", workflow="auditor-audit",
             run_id="4242", run_number=7):
    """A record in the §7 envelope shape — the shape every ledger record must carry."""
    return {"timestamp": timestamp, "workflow": workflow, "event": event,
            "run_id": run_id, "run_number": run_number, "data": data}


def envelope_violation(rec):
    """Return a human diagnostic if `rec` is not exactly the §7 envelope, else None."""
    if not isinstance(rec, dict):
        return f"record is {type(rec).__name__}, not an object"
    missing = [k for k in ENVELOPE_KEYS if k not in rec]
    extra = sorted(k for k in rec if k not in ENVELOPE_KEYS)
    if missing:
        return f"missing envelope key(s) {missing}; payload keys promoted to top level: {extra}"
    if extra:
        return f"extra top-level key(s) {extra} outside the envelope"
    if not isinstance(rec["data"], dict):
        return "'data' is not an object"
    return None


class Sandbox:
    def __init__(self, registry="registry.json", ledgers=None):
        self.root = Path(tempfile.mkdtemp(prefix="auditor-schema-"))
        self.code = self.root / "code"
        self.data = self.root / "data"
        self.code.mkdir()
        # vibe-167: rewired blocks invoke helpers at $CODE_DIR/auditor/scripts/,
        # and render-dashboard.py resolves its templates and the rulebook two
        # parents above itself — a checkout always carries all three
        shutil.copytree(REPO / "auditor" / "scripts",
                        self.code / "auditor" / "scripts")
        shutil.copytree(REPO / "templates" / "report",
                        self.code / "templates" / "report")
        shutil.copytree(REPO / "skills" / "rules",
                        self.code / "skills" / "rules")
        for c in ("reports", "audits", "ledgers", "articles", "exemplars", "registry"):
            (self.data / c).mkdir(parents=True)
        if registry:
            shutil.copy(FIX / registry, self.data / "registry" / "repos.json")
        for fname, recs in (ledgers or {}).items():
            (self.data / "ledgers" / fname).write_text(
                "".join(json.dumps(r) + "\n" for r in recs))
        self.bin = self.root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(GH_STUB)
        gh.chmod(0o755)
        self.gh_log = self.root / "gh.log"
        self.gh_log.touch()

    def run(self, script, env=None, fixture="registry-issue.json"):
        e = dict(os.environ)
        e.update({
            "PATH": f"{self.bin}:{e['PATH']}",
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
                              cwd=self.root, timeout=90)

    def ledger(self, fname):
        p = self.data / "ledgers" / fname
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

    def all_ledger_records(self):
        out = []
        for p in sorted((self.data / "ledgers").glob("*.jsonl")):
            for ln in p.read_text().splitlines():
                if ln.strip():
                    out.append((p.name, json.loads(ln)))
        return out

    def registry(self):
        return json.loads((self.data / "registry" / "repos.json").read_text())

    def gh_calls(self):
        return self.gh_log.read_text().splitlines()

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


def _copy_findings_sidecar(sb):
    shutil.copy(FIX / "findings-sidecar.jsonl",
                sb.data / "audits" / f"{TARGET_REPO.replace('/', '-')}.findings.jsonl")


def _write_vocab_sidecar(sb):
    (sb.data / "audits" / f"{TARGET_REPO.replace('/', '-')}.vocab-advisories.jsonl").write_text(
        json.dumps(VOCAB_SIDECAR) + "\n")



def _write_model_exemplar(sb):
    """vibe-211: the exemplar publisher REFUSES when the model wrote nothing (exemplar-not-written), so
    the emitter row must supply a valid model output or it appends no record and proves nothing."""
    (sb.data / "exemplars" / f"{TARGET_REPO.replace('/', '-')}.md").write_text(
        f"---\nslug: {TARGET_REPO.replace('/', '-')}\nrepo: {TARGET_REPO}\naudited: 2026-08-06\n"
        "commit_sha: cafebabe\nscore: 92\nexemplifies:\n  - R07\n---\n\nEvidence body.\n",
        encoding="utf-8")


BASE_ENV = {"SCORE": "92", "SECURITY": "CLEAR", "RUN_ID": "4242", "GITHUB_RUN_ID": "4242",
            "GITHUB_RUN_NUMBER": "7", "TARGET_SHA": "cafebabe"}

# (workflow name, marker, extra env, registry fixture, prep hook)
EMITTERS = [
    ("discover", "stage-logic", {"DRY_RUN": "false"}, "registry.json", None),
    ("audit", "stage-logic", {"SCORE": "64", "SECURITY": "REVIEW"}, "registry.json",
     _copy_findings_sidecar),
    ("contribute", "stage-logic",
     # No LABELS: the terminal-transition block never reads it (the security gate derives
     # labels from the API since F10.a, and no other reader exists).
     {"FIRST_CONTACT": "true", "WEEK_CONTACT_COUNT": "0"},
     "registry.json", _copy_findings_sidecar),
    ("track", "stage-logic", {}, "registry-tracked.json", None),
    ("case-study", "stage-logic",
     {"MERGED": "0", "APPLIED_SEP": "0", "RULE_ADOPTED": "false"}, "registry-tracked.json", None),
    ("daily-report", "stage-logic", {}, "registry.json", None),
    ("classify", "logic", {}, "registry.json", None),
    ("render-dashboard", "logic", {}, "registry.json", None),
    ("repo-report", "logic", {}, "registry.json", None),
    ("suppressions", "logic", {}, "registry.json", None),
    ("vocab-drift", "logic", {}, "registry.json", _write_vocab_sidecar),
    ("exemplar", "logic", {"TARGET_REPO": TARGET_REPO}, "registry.json", _write_model_exemplar),
    ("cite-exemplars", "logic", {}, "registry.json", None),
    ("refine-rules", "logic", {}, "registry.json", None),
    ("docs-diff", "logic", {}, "registry.json", None),
]


class BlockBase(unittest.TestCase):
    def block(self, name, marker="stage-logic"):
        path = WF_DIR / f"auditor-{name}.yml"
        self.assertTrue(path.is_file(), f"{path} missing")
        b = extract(path, marker, name)
        self.assertIsNotNone(b, f"no {marker}:{name} block in {path.name}")
        return b

    def run_emitter(self, name, marker, extra=None, registry="registry.json", prep=None,
                    ledgers=None):
        sb = Sandbox(registry=registry, ledgers=ledgers)
        if prep:
            prep(sb)
        env = dict(BASE_ENV)
        env.update(extra or {})
        r = sb.run(self.block(name, marker), env=env)
        return sb, r


# --- emitters -------------------------------------------------------------------------

class TestFingerprint(BlockBase):
    """§3 — the finding fingerprint known vector, computed independently in this test."""

    def test_fingerprint_known_vector(self):
        sb, r = self.run_emitter("audit", "stage-logic", {"SCORE": "64", "SECURITY": "REVIEW"},
                                 prep=_copy_findings_sidecar)
        try:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            recs = sb.ledger("findings.jsonl")
            self.assertTrue(recs, "audit appended no finding records")
            by_rule = {}
            for rec in recs:
                payload = rec["data"] if isinstance(rec.get("data"), dict) else rec
                by_rule[payload.get("rule_id")] = payload
            self.assertIn("BUG-BROKEN-REF", by_rule,
                          f"expected the sidecar's BUG-BROKEN-REF finding; saw {sorted(by_rule)}")
            got = by_rule["BUG-BROKEN-REF"].get("fingerprint")
            want = finding_fingerprint(TARGET_REPO, "commands/deploy.md", "BUG-BROKEN-REF",
                                       "missing-include", 12)
            self.assertEqual(
                got, want,
                "§3 fingerprint disagreement: the digest must fold repo|file|rule_id|pattern|"
                "line WITH a trailing newline and keep the full-width hex behind the 'sha256:' "
                f"prefix.\n  produced: {got}\n  contract: {want}")
        finally:
            sb.cleanup()

    def test_fingerprint_is_full_width_hex(self):
        """A truncated digest is a silent collision surface; §3 fixes the width at sha256's."""
        sb, r = self.run_emitter("audit", "stage-logic", {"SCORE": "64", "SECURITY": "REVIEW"},
                                 prep=_copy_findings_sidecar)
        try:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for rec in sb.ledger("findings.jsonl"):
                payload = rec["data"] if isinstance(rec.get("data"), dict) else rec
                fp = payload.get("fingerprint", "")
                self.assertRegex(
                    fp, r"^sha256:[0-9a-f]{64}$",
                    f"fingerprint {fp!r} is not 'sha256:' + 64 lowercase hex digits")
        finally:
            sb.cleanup()


class TestFindingRecordFields(BlockBase):
    """§2 — every finding record carries the required field set, including the join keys."""

    def test_finding_records_carry_required_fields(self):
        sb, r = self.run_emitter("audit", "stage-logic", {"SCORE": "64", "SECURITY": "REVIEW"},
                                 prep=_copy_findings_sidecar)
        try:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            recs = sb.ledger("findings.jsonl")
            self.assertEqual(len(recs), 4, "expected the 4 sidecar findings to be aggregated")
            for i, rec in enumerate(recs):
                payload = rec["data"] if isinstance(rec.get("data"), dict) else rec
                merged = dict(payload)
                for k in ENVELOPE_KEYS:
                    if k in rec and k != "data":
                        merged.setdefault(k, rec[k])
                missing = [f for f in FINDING_REQUIRED if f not in merged]
                with self.subTest(record=i):
                    self.assertEqual(
                        missing, [],
                        f"§2 required field(s) absent from the finding record: {missing} "
                        f"(present: {sorted(merged)})")
                    self.assertEqual(
                        merged.get("event"), "finding",
                        "§2: 'event' is the constant discriminator \"finding\" on every record")
        finally:
            sb.cleanup()

    def test_finding_run_id_key_is_audit_run_id(self):
        """§2 names the field `audit_run_id`; a bare `run_id` in the payload is a different key."""
        sb, r = self.run_emitter("audit", "stage-logic", {"SCORE": "64", "SECURITY": "REVIEW"},
                                 prep=_copy_findings_sidecar)
        try:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for rec in sb.ledger("findings.jsonl"):
                payload = rec["data"] if isinstance(rec.get("data"), dict) else rec
                self.assertIn(
                    "audit_run_id", payload,
                    f"finding payload keys {sorted(payload)} carry no 'audit_run_id' (§2)")
                self.assertEqual(payload["audit_run_id"], "4242")
        finally:
            sb.cleanup()



class TestExemplarEmitter(BlockBase):
    """vibe-211: the exemplar row of EMITTERS must actually publish, or TestEventEnvelope is vacuous for it.

    Measured before this test existed: with no prep hook the block refused `exemplar-not-written`, exit 1,
    zero records — and the envelope loop, which only requires a positive total across ALL emitters, passed.
    """

    def test_exemplar_emitter_publishes_one_enveloped_record(self):
        row = [e for e in EMITTERS if e[0] == "exemplar"]
        self.assertEqual(len(row), 1)
        name, marker, extra, registry, prep = row[0]
        sb, r = self.run_emitter(name, marker, extra, registry, prep)
        try:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("PASS", r.stdout)
            recs = [rec for _f, rec in sb.all_ledger_records()]
            self.assertEqual([rec.get("event") for rec in recs], ["exemplar_published"])
            self.assertIsNone(envelope_violation(recs[0]), envelope_violation(recs[0]))
        finally:
            sb.cleanup()


class TestEventEnvelope(BlockBase):
    """§7 — `{timestamp, workflow, event, run_id, run_number, data}` on every appended record."""

    def test_event_envelope(self):
        emitted = 0
        failures = []
        for name, marker, extra, registry, prep in EMITTERS:
            sb, r = self.run_emitter(name, marker, extra, registry, prep)
            try:
                records = sb.all_ledger_records()
                emitted += len(records)
                for fname, rec in records:
                    bad = envelope_violation(rec)
                    if bad:
                        failures.append(f"{name} -> ledgers/{fname}: {bad}")
            finally:
                sb.cleanup()
        self.assertGreater(emitted, 0, "no workflow appended any ledger record — harness fault")
        self.assertEqual(
            failures, [],
            "§7 envelope violated by " + str(len(failures)) + " appended record(s):\n  "
            + "\n  ".join(sorted(set(failures))))


class TestVocabAdvisory(BlockBase):
    """§6 — advisory fields and the sorted-terms fingerprint."""

    def _advisory(self):
        sb, r = self.run_emitter("vocab-drift", "logic", {}, prep=_write_vocab_sidecar)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        recs = sb.ledger("vocab-advisories.jsonl")
        self.assertTrue(recs, "vocab-drift appended no advisory record")
        rec = recs[0]
        payload = rec["data"] if isinstance(rec.get("data"), dict) else rec
        merged = dict(payload)
        for k in ENVELOPE_KEYS:
            if k in rec and k != "data":
                merged.setdefault(k, rec[k])
        return sb, merged

    def test_vocab_advisory_documented_fields(self):
        sb, adv = self._advisory()
        try:
            missing = [f for f in VOCAB_REQUIRED if f not in adv]
            self.assertEqual(
                missing, [],
                f"§6 field(s) absent from the advisory record: {missing}. The contract names "
                "`commit_sha` and `audit_run_id`; `commit`/`run_id` are different keys and do "
                f"not join. (present: {sorted(adv)})")
        finally:
            sb.cleanup()

    def test_vocab_advisory_fingerprint(self):
        sb, adv = self._advisory()
        try:
            want = vocab_fingerprint(TARGET_REPO, VOCAB_SIDECAR["terms"],
                                     VOCAB_SIDECAR["disposition"])
            self.assertEqual(
                adv.get("fingerprint"), want,
                "§6 vocab fingerprint disagreement: the digest folds repo|VOCAB|<sorted terms, "
                "comma-joined>|disposition with a trailing newline and carries the 'sha256:' "
                f"prefix.\n  produced: {adv.get('fingerprint')}\n  contract: {want}")
        finally:
            sb.cleanup()


class TestAuditedShaKey(BlockBase):
    """§1/§10 — one canonical registry key for the audited SHA, shared writer and reader."""

    def test_audited_sha_key_agreement(self):
        sb, r = self.run_emitter("audit", "stage-logic",
                                 {"SCORE": "64", "SECURITY": "REVIEW", "TARGET_SHA": "cafebabe"},
                                 prep=_copy_findings_sidecar)
        try:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            written = sb.registry()["repos"][TARGET_REPO]
            reader = jq_program("auditor-exemplar.yml", "commit_sha_at_audit")
            self.assertIsNotNone(reader, "auditor-exemplar.yml no longer reads a registry SHA key")
            out = run_jq(reader, sb.data / "registry" / "repos.json",
                         args=["--arg", "r", TARGET_REPO], slurp=False)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(
                out.stdout.strip(), "cafebabe",
                "the exemplar reader resolves a different registry key than the audit writer "
                f"populates; audit wrote {sorted(k for k in written if 'sha' in k)} and the "
                f"reader program is: {reader.strip()}")
        finally:
            sb.cleanup()


# --- consumers: readers driven by enveloped fixtures ----------------------------------

def enveloped_findings(n=20, rule_id="R09", contributed=5):
    recs = []
    for i in range(n):
        recs.append(envelope("finding", {
            "repo": TARGET_REPO, "rule_id": rule_id, "file": f"commands/c{i}.md",
            "pattern": "p", "line": i, "severity": "medium", "confidence": "high",
            "contributed": i < contributed, "outcome": "closed_unmerged",
            "fingerprint": finding_fingerprint(TARGET_REPO, f"commands/c{i}.md", rule_id, "p", i),
        }))
    return recs


class TestConsumerBatchProcessor(unittest.TestCase):
    """batch-processor joins the event log and the findings ledger on payload fields."""

    def test_batch_processor_weekly_cap_reads_envelope(self):
        sb = Sandbox(ledgers={"events.jsonl": [
            envelope("prs_submitted", {"repo": TARGET_REPO, "pr_number": 11},
                     timestamp="2099-01-01T00:00:00Z", workflow="auditor-contribute"),
            envelope("prs_submitted", {"repo": TARGET_REPO, "pr_number": 12},
                     timestamp="2099-01-02T00:00:00Z", workflow="auditor-contribute"),
        ]})
        try:
            prog = jq_program("auditor-batch-processor.yml", "prs_submitted")
            self.assertIsNotNone(prog, "batch-processor no longer reads prs_submitted events")
            out = run_jq(prog, sb.data / "ledgers" / "events.jsonl",
                         args=["--arg", "r", TARGET_REPO,
                               "--arg", "c", "2026-01-01T00:00:00Z"])
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(
                out.stdout.strip(), "2",
                "batch-processor's weekly-cap read finds 0 of 2 enveloped prs_submitted records: "
                "it selects on a top-level `.repo`, which under §7 lives at `.data.repo`. "
                f"program: {prog.strip()}")
        finally:
            sb.cleanup()

    def test_batch_processor_suppression_set_reads_envelope(self):
        sb = Sandbox(ledgers={"findings.jsonl": enveloped_findings()})
        try:
            prog = jq_program("auditor-batch-processor.yml", "group_by(.rule_id)[]")
            self.assertIsNotNone(prog, "batch-processor no longer computes a suppression set")
            out = run_jq(prog, sb.data / "ledgers" / "findings.jsonl", raw=False)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(
                json.loads(out.stdout), ["R09"],
                "batch-processor's low-landing-rate set groups on a top-level `.rule_id`; under "
                "§7 the rule id is at `.data.rule_id`, so every enveloped finding collapses into "
                f"one anonymous group. program: {prog.strip()}")
        finally:
            sb.cleanup()


class TestConsumerRenderDashboard(BlockBase):
    """render-dashboard counts the three ledgers and filters on the envelope timestamp."""

    def test_render_dashboard_counts_and_stays_homogeneous(self):
        ledgers = {
            "findings.jsonl": enveloped_findings(n=2),
            "vocab-advisories.jsonl": [envelope("vocab_advisory", {"repo": TARGET_REPO},
                                                workflow="auditor-vocab-drift")],
            "events.jsonl": [envelope("repo_discovered", {"repo": TARGET_REPO},
                                      workflow="auditor-discover")],
        }
        sb, r = self.run_emitter("render-dashboard", "logic", {}, ledgers=ledgers)
        try:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            html = (sb.data / "reports" / "dashboard.html").read_text()
            # vibe-167: the dashboard is render-dashboard.py's output now — the
            # counts live in its embedded data blob, not in inline prose
            self.assertIn('"total_findings":2', html.replace(" ", ""),
                          "the enveloped findings ledger was not counted")
            self.assertIn('"total_advisories":1', html.replace(" ", ""),
                          "the enveloped advisory was not counted")
            bad = [envelope_violation(rec) for rec in sb.ledger("events.jsonl")]
            self.assertEqual(
                [b for b in bad if b], [],
                "render-dashboard appended a flat `dashboard_rendered` record into an events "
                "ledger that already holds §7-enveloped records; §13 forbids mixed schemas in "
                "one file, so the dashboard's own record is unreadable to every other consumer")
        finally:
            sb.cleanup()


class TestConsumerContribute(BlockBase):
    """contribute's pushback gate joins the disagreements ledger on the record's repo."""

    def test_contribute_pushback_gate_reads_envelope(self):
        sb = Sandbox(ledgers={"disagreements.jsonl": [
            envelope("maintainer_rejected",
                     {"repo": "unrelated/other", "pr": 5, "rule_ids": ["R07"]},
                     workflow="auditor-classify"),
        ]})
        try:
            block = extract(WF_DIR / "auditor-contribute.yml", "gate", "pushback")
            self.assertIsNotNone(block, "contribute has no gate:pushback block")
            r = sb.run(block, env=dict(BASE_ENV, REPO=TARGET_REPO))
            out = r.stdout + r.stderr
            self.assertNotIn(
                "SKIP:pushback", out,
                "the pushback gate blocks the target repo on a rejection recorded for a "
                "DIFFERENT repo: it reads a top-level `.repo` which §7 places at `.data.repo`, "
                "so `(.repo // $repo)` defaults every enveloped record into a match and `.pr` "
                "resolves to null")
            self.assertIn("PASS", out, out)
        finally:
            sb.cleanup()


class TestConsumerClassify(BlockBase):
    """classify dedupes snapshots against prior classifications by comments_hash."""

    def test_classify_dedupe_reads_envelope(self):
        sb = Sandbox(ledgers={"disagreements.jsonl": [
            envelope("pr_comments_snapshot",
                     {"pr": 17, "pr_state": "CLOSED", "comments_hash": "abc123",
                      "fingerprints": [], "rule_ids": [], "comments": []},
                     workflow="auditor-track"),
            envelope("maintainer_rejected_classification",
                     {"pr": 17, "comments_hash": "abc123", "dissent_type": "out_of_scope"},
                     workflow="auditor-classify"),
        ]})
        try:
            prog = jq_program("auditor-classify.yml", "| length")
            self.assertIsNotNone(prog, "classify no longer counts unseen snapshots")
            out = run_jq(prog, sb.data / "ledgers" / "disagreements.jsonl")
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(
                out.stdout.strip(), "0",
                "classify re-classifies an already-classified snapshot: the dedupe compares a "
                "top-level `.comments_hash`, which §7 places at `.data.comments_hash`, so every "
                f"enveloped hash reads as null. program: {prog.strip()}")
        finally:
            sb.cleanup()


class TestConsumerRefineRules(unittest.TestCase):
    """refine-rules consumes the ledgers through the rulebook-group helpers (E8.6).

    The envelope-awareness property this class used to pin lived in an inline jq
    aggregation the workflow no longer carries: the pipeline is now rule-health.py →
    validate-feedback.sh → prepare-refinement-input.py, and the §7-envelope reading is
    those helpers' own tested behavior (the rule-health suite drives enveloped events and
    disagreements directly). What remains pinned HERE is that the workflow has not grown a
    second, envelope-blind inline reader beside the helpers.
    """

    def test_the_workflow_carries_no_inline_ledger_aggregation(self):
        text = (WF_DIR / "auditor-refine-rules.yml").read_text(encoding="utf-8")
        block = text[text.index("# logic:refine-rules"):text.index("# /logic")]
        self.assertIn("rule-health.py", block,
                      "the pipeline lost its rebuild step")
        self.assertIn("prepare-refinement-input.py", block,
                      "the pipeline lost its selection step")
        self.assertNotIn("group_by(.data.rule_id)", block,
                         "an inline disagreement aggregation reappeared beside the helpers "
                         "— two readers of one ledger drift apart silently")


class TestConsumerSuppressions(unittest.TestCase):
    """suppressions dedupes against prior downstream_suppression records by fingerprint."""

    def test_suppressions_reads_envelope(self):
        fp = finding_fingerprint(TARGET_REPO, "commands/a.md", "R07", "p", 3)
        sb = Sandbox(ledgers={"disagreements.jsonl": [
            envelope("downstream_suppression",
                     {"repo": TARGET_REPO, "fingerprint": fp, "rule_id": "R07",
                      "suppression_type": "suppress", "commit_sha": "cafebabe",
                      "path": ".nlpm.json"},
                     workflow="auditor-suppressions"),
        ]})
        try:
            prog = jq_program("auditor-suppressions.yml", ".fingerprint == $f")
            self.assertIsNotNone(prog, "suppressions no longer dedupes on fingerprint")
            out = run_jq(prog, sb.data / "ledgers" / "disagreements.jsonl",
                         args=["-e", "--arg", "f", fp], slurp=False)
            self.assertEqual(
                out.returncode, 0,
                "suppressions does not recognise its own already-recorded suppression in an "
                "enveloped ledger: it matches a top-level `.fingerprint`, which §7 places at "
                f"`.data.fingerprint`, so every re-scan re-appends. program: {prog.strip()}")
        finally:
            sb.cleanup()


class TestConsumerLedgerHomogeneity(BlockBase):
    """§13 — a writer that appends into an enveloped ledger must keep the file homogeneous."""

    def _seeded(self):
        return {"events.jsonl": [envelope("repo_discovered", {"repo": "seed/repo"},
                                          workflow="auditor-discover")]}

    def _assert_homogeneous(self, name, marker, extra, registry, prep, why):
        sb, r = self.run_emitter(name, marker, extra, registry, prep, ledgers=self._seeded())
        try:
            recs = sb.ledger("events.jsonl")
            self.assertGreater(len(recs), 1,
                               f"{name} appended nothing to the seeded events ledger")
            bad = [envelope_violation(rec) for rec in recs]
            self.assertEqual([b for b in bad if b], [], why)
        finally:
            sb.cleanup()

    def test_discover_keeps_the_events_ledger_homogeneous(self):
        self._assert_homogeneous(
            "discover", "stage-logic", {"DRY_RUN": "false"}, "registry.json", None,
            "discover appends a flat `repo_discovered` record into an events ledger that "
            "already holds §7-enveloped records; §13 forbids mixed schemas in one file")

    def test_daily_report_keeps_the_events_ledger_homogeneous(self):
        self._assert_homogeneous(
            "daily-report", "stage-logic", {}, "registry.json", None,
            "daily-report appends a flat `report_generated` record into an enveloped events "
            "ledger; §13 forbids mixed schemas in one file")

    def test_case_study_keeps_the_events_ledger_homogeneous(self):
        self._assert_homogeneous(
            "case-study", "stage-logic",
            {"MERGED": "0", "APPLIED_SEP": "0", "RULE_ADOPTED": "false"},
            "registry-tracked.json", None,
            "case-study appends a flat `case_study_skipped` record into an enveloped events "
            "ledger; §13 forbids mixed schemas in one file")

    def test_track_keeps_the_events_ledger_homogeneous(self):
        self._assert_homogeneous(
            "track", "stage-logic", {}, "registry-tracked.json", None,
            "track appends flat `finding_outcome` records into an enveloped events ledger; "
            "§13 forbids mixed schemas in one file, and §7 is what the fingerprint join reads")


if __name__ == "__main__":
    unittest.main()


# --- E8.2b (vibe-164) W1: contract declarations for the contribution engine ------------

class TestE82bContractDeclarations(unittest.TestCase):
    """W1.1/W1.2 — the records E8.2b's engine must emit are declared in the contract.

    These are contract-shape assertions, not scaffolding checks: each names a record the
    engine is required to write, and the behavioural proof that the engine writes it in
    this shape lives with its emitter (W5.3 for orphaned_fork, W4.1/W4.2 for the gate
    outputs). A declaration without an emitter is exactly the gap Step-5 finding 7 raised.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = (REPO / "auditor" / "SCHEMAS.md").read_text(encoding="utf-8")

    def test_orphaned_fork_is_a_declared_event(self):
        self.assertIn("`orphaned_fork`", self.text,
                      "SCHEMAS.md declares no orphaned_fork event; the never-delete policy "
                      "has no durable record to write")
        for field in ("fork_slug", "invariant_failed"):
            self.assertIn(field, self.text,
                          f"orphaned_fork declares no {field} field")

    def test_orphaned_repo_status_is_untouched(self):
        # orphaned (repo status, terminal for repos whose PRs became untrackable) and
        # orphaned_fork (a fork we created whose post-creation invariant failed) are
        # different concepts at different layers. Overloading one would lose the other.
        self.assertIn(
            "`policy_cla_required` / `orphaned`", self.text,
            "the orphaned repo-status enum entry was altered; orphaned_fork must be added "
            "as a section-7 event, not by overloading the section-1 status")

    def test_gate_outputs_are_declared_immutable(self):
        for artifact in ("proposal-manifest.json", "disclosure.json"):
            self.assertIn(artifact, self.text,
                          f"SCHEMAS.md declares no {artifact}; submit has no allowlist to "
                          f"validate against and disclosure has no routed artifact")

    def test_disclosure_routing_constraint_is_contractual(self):
        # The constraint is a property of the record, not an accident of one workflow.
        self.assertRegex(
            self.text, r"disclosure\.json[\s\S]{0,400}?never.{0,40}propose",
            "the disclosure-never-propose routing constraint is not stated in the contract")
