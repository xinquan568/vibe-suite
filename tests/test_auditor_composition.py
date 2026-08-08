# SPDX-License-Identifier: ISC
"""E8.2 gate composition + finalize durability (vibe-59, plan task T2).

The nine `# gate:` blocks of auditor-contribute.yml are executed IN SEQUENCE over ONE shared
decision file ($DECISION = {proceed, reason, side_exit_label}). Once a gate prints `SKIP:`,
every later gate must be a no-op: it must not act and must not overwrite the decision, and the
file must end with proceed=false carrying the first gate's reason and side-exit label.

`finalize` is executed against a REAL disposable git repo standing in for the `auditor-data`
branch (a bare remote + a clone), so the refusal event is proved COMMITTED AND PUSHED via
`git log` in the BARE remote rather than merely appended to a working copy, and the event
append is proved to happen BEFORE the label call.

One test method per row of the plan's 13-row outcome table, selected by (job, status).

Every test drives the CURRENT production path. No reserve/finalize job exists yet, so the
terminal label+ledger writer under test is auditor-contribute.yml's own `stage-logic:contribute`
step. The resulting failures are behavioral -- gate bodies execute after a skip, the label is
applied before any ledger write, nothing is ever committed or pushed -- not scaffolding absence.
"""
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract, FIX

WF = Path(__file__).resolve().parent.parent / "auditor" / "workflows" / "auditor-contribute.yml"
HAS_GIT = shutil.which("git") is not None

# Declared execution order of the nine gates (tests/test_auditor_gates.py::GATES).
GATE_ORDER = ["security-blocked", "no-external-prs", "cla", "pushback", "confidence",
              "duplicate-pr", "pr-caps", "disclosure-routing", "umbrella-backstop"]

# A gate "acted" when it emitted a decision-bearing line or called gh.
ACTION_PREFIXES = ("KEEP:", "DROP:", "CAP:", "DISCLOSE:")

# gh stub that also snapshots the ledger at the instant of the first label call, so
# event-before-label ordering is observable.
ORDER_GH_STUB = """#!/usr/bin/env bash
echo "gh $*" >> "$GH_LOG"
case "$*" in
  *--add-label*|*"issue edit"*)
    if [ -n "${LABEL_SNAPSHOT:-}" ] && [ ! -e "$LABEL_SNAPSHOT" ]; then
      cp "$EVENT_LOG" "$LABEL_SNAPSHOT" 2>/dev/null || : > "$LABEL_SNAPSHOT"
    fi
    ;;
esac
exit 0
"""

GIT_ENV = {"GIT_AUTHOR_NAME": "auditor-test", "GIT_AUTHOR_EMAIL": "auditor@example.invalid",
           "GIT_COMMITTER_NAME": "auditor-test", "GIT_COMMITTER_EMAIL": "auditor@example.invalid",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check, text=True,
                          capture_output=True, env=dict(os.environ, **GIT_ENV))


def make_data_repo(sb):
    """Turn the sandbox DATA_DIR into a real clone of a real bare `auditor-data` remote."""
    bare = sb.root / "auditor-data.git"
    git("init", "--bare", "-b", "main", str(bare), cwd=sb.root)  # -b main: without it HEAD is an unborn "master", so pushes to main leave the
    # remote log empty and the rival clone has no local main to race with.
    git("init", cwd=sb.data)
    git("checkout", "-b", "main", cwd=sb.data, check=False)
    for c in ("reports", "audits", "ledgers", "articles", "exemplars", "registry"):
        (sb.data / c / ".gitkeep").write_text("")
    git("add", "-A", cwd=sb.data)
    git("commit", "-m", "seed auditor-data", cwd=sb.data)
    git("remote", "add", "origin", str(bare), cwd=sb.data)
    git("push", "-u", "origin", "main", cwd=sb.data)
    return bare


def remote_file(bare, path):
    r = subprocess.run(["git", f"--git-dir={bare}", "show", f"main:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def remote_log(bare):
    r = subprocess.run(["git", f"--git-dir={bare}", "log", "--oneline", "--name-only"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def extract_run_containing(needle):
    """Return the dedented body of the first `- run: |` step whose text contains `needle`."""
    text = WF.read_text()
    for m in re.finditer(r"^([ \t]*)- run: \|\n", text, re.M):
        base = len(m.group(1)) + 2
        lines = []
        for ln in text[m.end():].split("\n"):
            if ln.strip() and (len(ln) - len(ln.lstrip(" "))) <= base:
                break
            lines.append(ln)
        body = "\n".join(lines)
        if needle in body:
            ind = min((len(l) - len(l.lstrip(" ")) for l in lines if l.strip()), default=0)
            return "\n".join(l[ind:] if len(l) >= ind else l for l in lines)
    return None


def terminal_block():
    """`finalize`'s logic once it exists; today, production's only label+ledger writer."""
    return extract(WF, "logic", "finalize") or extract(WF, "stage-logic", "contribute")


def payload(rec):
    d = rec.get("data")
    return d if isinstance(d, dict) else rec


def stage_outcomes(job, status, reason, ids):
    order = ["gates", "reserve", "propose", "submit"]
    ok = {"gates": "pass", "reserve": "reserved", "propose": "patches", "submit": "submitted"}
    out = {}
    for s in order:
        if s == job:
            out[s] = {"schema_version": 1, "job": s, "status": status,
                      "reason": reason, "ids": ids}
            break
        out[s] = {"schema_version": 1, "job": s, "status": ok[s], "reason": "", "ids": {}}
    return out


class Res:
    """Observed effects of one terminal-stage run."""

    def __init__(self, r, sb, bare):
        self.r, self.sb, self.bare = r, sb, bare
        calls = sb.gh_calls()
        joined = "\n".join(calls)
        self.added = re.findall(r"--add-label\s+(\S+)", joined)
        self.removed = re.findall(r"--remove-label\s+(\S+)", joined)
        self.pr_creates = [c for c in calls if "pr create" in c]
        self.records = sb.events()
        self.out = r.stdout + r.stderr

    def names(self):
        return [x.get("event") or payload(x).get("event") for x in self.records]

    def rec(self, event):
        for x in self.records:
            if (x.get("event") or payload(x).get("event")) == event:
                return x
        return None

    def pushed_events(self):
        return remote_file(self.bare, "ledgers/events.jsonl")


@unittest.skipUnless(HAS_GIT, "git is required for the durability assertions")
class CompositionBase(unittest.TestCase):
    def sandbox(self, registry="registry.json"):
        sb = Sandbox(registry=registry)
        self.addCleanup(sb.cleanup)
        gh = sb.bin / "gh"
        gh.write_text(ORDER_GH_STUB)
        gh.chmod(0o755)
        sb.decision = sb.root / "decision.json"
        sb.decision.write_text(json.dumps(
            {"proceed": True, "reason": "", "side_exit_label": ""}) + "\n")
        sb.outcomes = sb.root / "outcomes"
        sb.outcomes.mkdir(exist_ok=True)
        sb.label_snapshot = sb.root / "eventlog-at-label.txt"
        sb.bare = make_data_repo(sb)
        return sb

    def base_env(self, sb, extra=None):
        e = {"REPO": "acme/claude-toolkit", "OWNER": "acme",
             "SIDECAR": str(FIX / "findings-sidecar.jsonl"),
             "DECISION": str(sb.decision), "OUTCOME_DIR": str(sb.outcomes),
             "DATA_REMOTE": str(sb.bare), "LABEL_SNAPSHOT": str(sb.label_snapshot),
             "ISSUE_NUMBER": "42", "LABELS": "contribute-approved"}
        e.update(GIT_ENV)
        e.update(extra or {})
        return e

    def gate(self, name):
        b = extract(WF, "gate", name)
        self.assertIsNotNone(b, f"no gate block '{name}' in {WF}")
        return b

    def run_sequence(self, sb, extra=None):
        """Run all nine gates in order against the one shared decision file."""
        results = []
        for name in GATE_ORDER:
            r = sb.run(self.gate(name), env=self.base_env(sb, extra))
            results.append((name, r))
        return results

    def decision(self, sb):
        return json.loads(sb.decision.read_text() or "{}")

    @staticmethod
    def acted(name, r, before_calls, after_calls):
        lines = r.stdout.splitlines()
        emitted = [l for l in lines if l.startswith(ACTION_PREFIXES)]
        return emitted or (len(after_calls) > len(before_calls))

    def drive_row(self, job, status, reason="", ids=None, extra=None, registry="registry.json"):
        sb = self.sandbox(registry=registry)
        for name, doc in stage_outcomes(job, status, reason, ids or {}).items():
            (sb.outcomes / f"outcome-{name}.json").write_text(json.dumps(doc) + "\n")
        sb.decision.write_text(json.dumps({
            "proceed": job == "submit" and status == "submitted",
            "reason": reason, "side_exit_label": ""}) + "\n")
        block = terminal_block()
        self.assertIsNotNone(block, "neither a finalize logic block nor stage-logic:contribute")
        env = self.base_env(sb, {"OUTCOME_JOB": job, "OUTCOME_STATUS": status,
                                 "OUTCOME_REASON": reason})
        env.update(extra or {})
        return Res(sb.run(block, env=env), sb, sb.bare)


class TestGateComposition(CompositionBase):
    """T2: the nine gates composed over one decision file."""

    def test_skip_stops_cascade(self):
        sb = self.sandbox()
        # Focused pair: `no-external-prs` skips, then `pr-caps` must not execute its body.
        before = len(sb.gh_calls())
        first = sb.run(self.gate("no-external-prs"), env=self.base_env(sb, {"OWNER": "anthropics"}))
        self.assertIn("SKIP:", first.stdout, "no-external-prs did not skip on a denied owner")
        second = sb.run(self.gate("pr-caps"), env=self.base_env(
            sb, {"OWNER": "anthropics", "FIRST_CONTACT": "true", "PLANNED_COUNT": "5"}))
        self.assertFalse(
            self.acted("pr-caps", second, [], sb.gh_calls()[before:]),
            "gate 2 (pr-caps) executed its body after gate 1 (no-external-prs) printed SKIP: "
            f"-- it emitted {second.stdout.strip()!r}; a skipped decision must make every later "
            "gate a no-op")

    def test_every_gate_after_the_first_skip_is_a_noop(self):
        sb = self.sandbox()
        results = self.run_sequence(sb, {"OWNER": "anthropics", "PLANNED_COUNT": "5",
                                         "QUOTA_EXHAUSTED": "true", "REMAINING_COUNT": "4"})
        skip_at = next((i for i, (_, r) in enumerate(results) if "SKIP:" in r.stdout), None)
        self.assertIsNotNone(skip_at, "no gate in the sequence printed SKIP:")
        offenders = [n for n, r in results[skip_at + 1:]
                     if [l for l in r.stdout.splitlines() if l.startswith(ACTION_PREFIXES)]]
        self.assertEqual(offenders, [],
                         f"gates {offenders} acted after '{results[skip_at][0]}' printed SKIP:; "
                         "the gates carry no decision-file guard, so the cascade never stops")

    def test_later_gates_do_not_overwrite_the_decision(self):
        sb = self.sandbox()
        self.run_sequence(sb, {"OWNER": "anthropics", "PLANNED_COUNT": "5"})
        dec = self.decision(sb)
        self.assertIn("no-external-prs", str(dec.get("reason", "")),
                      f"the decision file must retain the FIRST refusal reason; it holds {dec!r}")

    def test_decision_file_ends_with_proceed_false(self):
        sb = self.sandbox()
        self.run_sequence(sb, {"OWNER": "anthropics", "PLANNED_COUNT": "5"})
        dec = self.decision(sb)
        self.assertIs(dec.get("proceed"), False,
                      f"after a gate skip the decision file must end proceed=false; got {dec!r}")
        self.assertTrue(dec.get("side_exit_label"),
                        f"the skipping gate recorded no side_exit_label: {dec!r}")

    def test_skip_path_invokes_no_model(self):
        sb = self.sandbox()
        self.run_sequence(sb, {"OWNER": "anthropics"})
        guard = extract_run_containing("GATES_OK")
        self.assertIsNotNone(guard, "no step sets the model guard GATES_OK")
        genv = sb.root / "github_env"
        genv.write_text("")
        sb.run(guard, env=self.base_env(sb, {"GITHUB_ENV": str(genv)}))
        self.assertNotIn("GATES_OK=true", genv.read_text(),
                         "the model guard was armed on a skip path -- the model action would run "
                         "after a gate refused; GATES_OK is set unconditionally")

    def test_skip_path_makes_no_submit_call(self):
        sb = self.sandbox()
        self.run_sequence(sb, {"OWNER": "anthropics"})
        block = terminal_block()
        self.assertIsNotNone(block, "no terminal block to run")
        sb.run(block, env=self.base_env(sb))
        calls = "\n".join(sb.gh_calls())
        self.assertNotIn("prs-submitted", calls,
                         "a submit/label call happened on a skip path: " + calls)
        self.assertFalse([c for c in sb.gh_calls() if "pr create" in c],
                         "a PR was created on a skip path")


class TestFinalizeDurability(CompositionBase):
    """T2: the refusal event must be committed AND pushed, and must precede the label."""

    def _refusal_run(self):
        sb = self.sandbox()
        self.run_sequence(sb, {"OWNER": "anthropics"})
        for name, doc in stage_outcomes(
                "gates", "skip", "no-external-prs", {}).items():
            (sb.outcomes / f"outcome-{name}.json").write_text(json.dumps(doc) + "\n")
        block = terminal_block()
        self.assertIsNotNone(block, "no finalize/terminal block")
        r = sb.run(block, env=self.base_env(sb))
        return Res(r, sb, sb.bare)

    def test_refusal_event_is_committed_and_pushed_to_the_bare_remote(self):
        res = self._refusal_run()
        log = remote_log(res.bare)
        self.assertIn("ledgers/events.jsonl", log,
                      "no commit in the BARE auditor-data remote touches ledgers/events.jsonl; "
                      "the refusal event was only appended to the working copy and would be lost "
                      f"with the runner. Remote log:\n{log}")
        self.assertIn("contribution_refused", res.pushed_events(),
                      "the pushed ledger carries no contribution_refused record")

    def test_event_append_precedes_the_label_call(self):
        res = self._refusal_run()
        snap = res.sb.label_snapshot
        self.assertTrue(snap.exists(), "no label call was made at all")
        self.assertIn("contribution_refused", snap.read_text(),
                      "the label was applied BEFORE the ledger append: at the instant of the "
                      f"gh label call the ledger held {snap.read_text()!r}. The ledger is "
                      "authoritative and the label is a derived view, so the durable write and "
                      "push must precede any issue transition.")


class TestOutcomeTable(CompositionBase):
    """T2: one method per row of the 13-row (job, status) outcome table."""

    def test_row_gates_skip_nonsecurity(self):
        res = self.drive_row("gates", "skip", "no-external-prs")
        self.assertNotIn("prs-submitted", res.added,
                         "(gates,skip/non-security) applied prs-submitted; the row requires the "
                         "gate's side-exit label and no PR")
        self.assertIn("contribution_refused", res.names(),
                      f"(gates,skip/non-security) ledger must record contribution_refused{{reason}}; "
                      f"got {res.names()}")
        self.assertEqual(res.pr_creates, [], "(gates,skip/non-security) must open no PR")

    def test_row_gates_skip_security_disclosure(self):
        res = self.drive_row("gates", "skip", "security-disclosure",
                             extra={"LABELS": "contribute-approved,security-blocked"})
        self.assertNotIn("security-blocked", res.removed,
                         "(gates,skip/security) must RETAIN security-blocked")
        self.assertTrue({"disclosure_filed", "disclosure_pending"} & set(res.names()),
                        "(gates,skip/security) ledger must record disclosure_filed or "
                        f"disclosure_pending; got {res.names()}")
        self.assertEqual(res.pr_creates, [],
                         "(gates,skip/security) must NEVER open a public PR")

    def test_row_gates_error(self):
        res = self.drive_row("gates", "error", "unhandled")
        self.assertIn("pipeline-error", res.added,
                      f"(gates,error) must apply pipeline-error; applied {res.added}")
        rec = res.rec("contribution_error")
        self.assertIsNotNone(rec, f"(gates,error) needs contribution_error; got {res.names()}")
        self.assertEqual(payload(rec).get("stage"), "gates",
                         "(gates,error) contribution_error must carry stage=gates")
        self.assertNotEqual(res.r.returncode, 0, "(gates,error) must fail the run loudly")

    def test_row_reserve_capped(self):
        res = self.drive_row("reserve", "capped", "weekly-cap")
        self.assertIn("policy-weekly-cap", res.added,
                      f"(reserve,capped) must apply policy-weekly-cap; applied {res.added}")
        rec = res.rec("contribution_refused")
        self.assertIsNotNone(rec, f"(reserve,capped) needs contribution_refused; got {res.names()}")
        self.assertEqual(payload(rec).get("reason"), "weekly-cap",
                         "(reserve,capped) refusal reason must be weekly-cap")
        self.assertEqual(res.pr_creates, [], "(reserve,capped) must open no PR")

    def test_row_reserve_error(self):
        res = self.drive_row("reserve", "error", "data-branch-unreachable")
        self.assertIn("pipeline-error", res.added,
                      f"(reserve,error) must apply pipeline-error; applied {res.added}")
        rec = res.rec("contribution_error")
        self.assertIsNotNone(rec, f"(reserve,error) needs contribution_error; got {res.names()}")
        self.assertEqual(payload(rec).get("stage"), "reserve",
                         "(reserve,error) contribution_error must carry stage=reserve")

    def test_row_propose_no_patches(self):
        res = self.drive_row("propose", "no-patches", "no-patches")
        self.assertIn("no-actionable-patches", res.added,
                      f"(propose,no-patches) must apply no-actionable-patches; applied {res.added}")
        rec = res.rec("contribution_refused")
        self.assertIsNotNone(rec,
                             f"(propose,no-patches) needs contribution_refused; got {res.names()}")
        self.assertEqual(payload(rec).get("reason"), "no-patches",
                         "(propose,no-patches) refusal reason must be no-patches")
        self.assertEqual(res.pr_creates, [], "(propose,no-patches) must open no PR")

    def test_row_propose_refused(self):
        res = self.drive_row("propose", "refused", "discuss-first")
        self.assertIn("policy-discuss-first", res.added,
                      f"(propose,refused) must apply policy-discuss-first; applied {res.added}")
        self.assertIn("contribution_refused", res.names(),
                      f"(propose,refused) needs contribution_refused; got {res.names()}")
        self.assertEqual(res.pr_creates, [], "(propose,refused) must open no PR")

    def test_row_propose_error(self):
        res = self.drive_row("propose", "error", "model-action-failed")
        self.assertIn("pipeline-error", res.added,
                      f"(propose,error) must apply pipeline-error; applied {res.added}")
        rec = res.rec("contribution_error")
        self.assertIsNotNone(rec, f"(propose,error) needs contribution_error; got {res.names()}")
        self.assertEqual(payload(rec).get("stage"), "propose",
                         "(propose,error) contribution_error must carry stage=propose")

    def test_row_submit_conflict(self):
        res = self.drive_row("submit", "conflict", "conflict")
        self.assertIn("patch-conflict", res.added,
                      f"(submit,conflict) must apply patch-conflict; applied {res.added}")
        rec = res.rec("contribution_refused")
        self.assertIsNotNone(rec, f"(submit,conflict) needs contribution_refused; got {res.names()}")
        self.assertEqual(payload(rec).get("reason"), "conflict",
                         "(submit,conflict) refusal reason must be conflict")
        self.assertEqual(res.pr_creates, [], "(submit,conflict) must open no PR")

    def test_row_submit_pre_pr_failure(self):
        res = self.drive_row("submit", "pre-pr-failure", "fork-push-failed")
        self.assertIn("pipeline-error", res.added,
                      f"(submit,pre-pr-failure) must apply pipeline-error; applied {res.added}")
        rec = res.rec("contribution_error")
        self.assertIsNotNone(rec,
                             f"(submit,pre-pr-failure) needs contribution_error; got {res.names()}")
        self.assertEqual(payload(rec).get("phase"), "pre-pr",
                         "(submit,pre-pr-failure) contribution_error must carry phase=pre-pr")
        self.assertEqual(res.pr_creates, [],
                         "(submit,pre-pr-failure) leaves no external effect")

    def test_row_submit_partial_persisted(self):
        res = self.drive_row("submit", "partial-persisted", "ledger-write-failed",
                             ids={"pr_number": 77})
        self.assertNotIn("prs-submitted", res.added,
                         "(submit,partial-persisted) must NOT apply prs-submitted while the "
                         f"ledger write is unconfirmed; applied {res.added}")
        rec = res.rec("contribution_partial")
        self.assertIsNotNone(rec,
                             f"(submit,partial-persisted) needs a best-effort contribution_partial "
                             f"record; got {res.names()}")
        self.assertEqual(payload(rec).get("pr_number"), 77,
                         "(submit,partial-persisted) contribution_partial must carry pr_number")

    def test_row_submit_submitted(self):
        res = self.drive_row("submit", "submitted", "", ids={"pr_number": 77})
        rec = res.rec("contribution_submitted")
        self.assertIsNotNone(rec, f"(submit,submitted) needs contribution_submitted; got {res.names()}")
        self.assertEqual(payload(rec).get("pr_number"), 77,
                         "(submit,submitted) contribution_submitted must carry pr_number; the current "
                         "record carries only a `kept` count, so the label is a proxy oracle")
        self.assertIn("contribution_submitted", res.pushed_events(),
                      "(submit,submitted) contribution_submitted was never committed and pushed to the "
                      "bare auditor-data remote")
        self.assertIn("prs-submitted", res.added, "(submit,submitted) must apply prs-submitted")
        self.assertIn("contribute-approved", res.removed,
                      "(submit,submitted) must remove contribute-approved")

    def test_row_submit_error(self):
        res = self.drive_row("submit", "error", "label-step-failed", ids={"pr_number": 77})
        self.assertIn("contribution_submitted", res.pushed_events(),
                      "(submit,error) the ledger is authoritative and must ALREADY be persisted "
                      "in the bare remote when the label step fails")
        self.assertNotEqual(res.r.returncode, 0,
                            "(submit,error) must fail the run loudly so a rerun re-derives "
                            "the label")


if __name__ == "__main__":
    unittest.main()
