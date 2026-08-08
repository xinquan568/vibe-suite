# SPDX-License-Identifier: ISC
"""E8.2b quota path and the read-only gate (vibe-164, plan W6).

Three things:

  * the quota facts are PRODUCED by the filtering path rather than passed in. They were
    `${QUOTA_EXHAUSTED:-false}` / `${REMAINING_COUNT:-0}` -- env vars nothing computed, so the
    umbrella backstop could never fire on a real run.
  * the umbrella issue moves OUT of gates. gates is specified read-only and holds no
    `issues: write`, yet it called `gh issue create`. finalize already holds that permission.
  * a non-empty PR number is validated BEFORE any registry write, ledger append or label
    transition.

finalize runs `always()`, so its trigger cannot be inherited from job success: the predicate
is stated positively and every non-qualifying terminal path is asserted.

Note on where quota lives: the plan said context.json, but that file is written once by
derive-context BEFORE any filtering and is contractually immutable. The quota facts are
computed by the filter, so they ride in proposal-manifest.json, which the same step writes.
"""
import json
import re
import unittest
from pathlib import Path

from tests.test_auditor_state_machine import Sandbox, extract, FIX

REPO_ROOT = Path(__file__).resolve().parent.parent
WF = REPO_ROOT / "auditor" / "workflows" / "auditor-contribute.yml"
TARGET = "acme/claude-toolkit"


class QuotaBase(unittest.TestCase):
    def block(self, name, marker="gate"):
        b = extract(WF, marker, name)
        self.assertIsNotNone(b, f"no {marker}:{name} block in {WF.name}")
        return b

    def emit(self, cap):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        r = sb.run(self.block("emit-manifest"), env={
            "REPO": TARGET, "OWNER": TARGET.split("/")[0],
            "SIDECAR": str(FIX / "findings-sidecar.jsonl"),
            "CODE_DIR": str(REPO_ROOT),
            "MANIFEST": str(sb.root / "proposal-manifest.json"),
            "PATCH_CAP": str(cap), "PLANNED_COUNT": "4"})
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)
        return json.loads((sb.root / "proposal-manifest.json").read_text())


class TestQuotaIsProducedByTheFilter(QuotaBase):
    def test_an_uncapped_run_reports_no_exhaustion(self):
        m = self.emit(cap=10)
        self.assertFalse(m["quota_exhausted"])
        self.assertEqual(0, m["remaining_count"])

    def test_a_capped_run_reports_exhaustion_and_the_remainder(self):
        # Two ordinary high-confidence findings survive the other filters; a cap of 1 leaves
        # exactly one behind.
        m = self.emit(cap=1)
        self.assertTrue(m["quota_exhausted"],
                        "the cap dropped a finding but quota_exhausted stayed false")
        self.assertEqual(1, m["remaining_count"])

    def test_the_remainder_counts_only_cap_drops(self):
        # A finding excluded for being on the disclosure path is not "remaining findings we
        # ran out of quota for" -- counting it would raise an umbrella issue about work that
        # is deliberately never going to be a PR.
        m = self.emit(cap=10)
        self.assertEqual(0, m["remaining_count"])


class TestGatesIsReadOnly(unittest.TestCase):
    def test_gates_creates_no_issue(self):
        text = WF.read_text(encoding="utf-8")
        gates = text[text.index("\n  gates:"):text.index("\n  reserve:")]
        code = "\n".join(l for l in gates.split("\n") if not l.lstrip().startswith("#"))
        self.assertNotIn(
            "gh issue create", code,
            "the gates job creates an issue. It is specified read-only and holds no "
            "issues: write, so this is a mutation from a job with no authority for it")

    def test_finalize_owns_the_umbrella_backstop(self):
        text = WF.read_text(encoding="utf-8")
        finalize = text[text.index("\n  finalize:"):]
        self.assertIn("gh issue create", finalize,
                      "nothing creates the umbrella issue; the backstop was removed rather "
                      "than relocated")


class TestUmbrellaPredicate(unittest.TestCase):
    """finalize runs always(), so the trigger is stated positively, not inherited."""

    def block(self):
        b = extract(WF, "stage-logic", "umbrella")
        self.assertIsNotNone(b, "no stage-logic:umbrella block in finalize")
        return b

    def run_umbrella(self, quota=True, remaining=2, submit_result="success",
                     status="submitted", existing=None):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        man = sb.root / "proposal-manifest.json"
        man.write_text(json.dumps({"version": 1, "repo": TARGET, "findings": [],
                                   "quota_exhausted": quota, "remaining_count": remaining}))
        env = {"REPO": TARGET, "MANIFEST": str(man),
               "SUBMIT_RESULT": submit_result, "TERMINAL_STATUS": status,
               "GITHUB_RUN_ID": "run-1"}
        if existing is not None:
            f = sb.root / "canned-issues"; f.write_text(json.dumps(existing))
            env["GH_CANNED_ISSUE_LIST"] = str(f)
        r = sb.run(self.block(), env=env)
        return r, sb

    def test_it_creates_when_every_condition_holds(self):
        r, sb = self.run_umbrella()
        self.assertIn("issue create", " ".join(sb.gh_calls()))

    def test_no_umbrella_when_quota_was_not_exhausted(self):
        r, sb = self.run_umbrella(quota=False)
        self.assertNotIn("issue create", " ".join(sb.gh_calls()))

    def test_no_umbrella_when_nothing_remains(self):
        r, sb = self.run_umbrella(remaining=0)
        self.assertNotIn("issue create", " ".join(sb.gh_calls()))

    def test_no_umbrella_when_submit_was_skipped(self):
        r, sb = self.run_umbrella(submit_result="skipped")
        self.assertNotIn("issue create", " ".join(sb.gh_calls()),
                         "an umbrella issue was raised on a run whose submit never executed")

    def test_no_umbrella_when_submit_failed(self):
        r, sb = self.run_umbrella(submit_result="failure")
        self.assertNotIn("issue create", " ".join(sb.gh_calls()))

    def test_no_umbrella_on_a_pre_pr_failure(self):
        # The run never reached a PR, so there is no exhausted quota to report.
        r, sb = self.run_umbrella(status="pre-pr-failure")
        self.assertNotIn("issue create", " ".join(sb.gh_calls()))

    def test_a_rerun_does_not_open_a_second_umbrella(self):
        r, sb = self.run_umbrella(existing=[{"number": 7, "title":
                                             f"Umbrella: 2 remaining findings for {TARGET} (run-1)"}])
        self.assertNotIn("issue create", " ".join(sb.gh_calls()),
                         "a rerun opened a duplicate umbrella issue")


class TestPrNumberGuard(unittest.TestCase):
    """W6.3 -- nothing durable is written keyed on an empty PR number.

    A behavioural test was written first and proved VACUOUS: removing the guard entirely broke
    nothing, because the extracted block exits earlier under fixture conditions and never
    reaches the durable region at all. A test that passes with and without the thing it
    guards is worse than no test, so the assertion is structural instead -- it is sensitive to
    the guard's presence AND to its position, which is the property that actually matters.
    """

    def block(self):
        b = extract(WF, "logic", "submit")
        self.assertIsNotNone(b, "no logic:submit block")
        return b

    def test_the_guard_precedes_every_durable_write(self):
        b = self.block()
        guard = b.find("REFUSE:pr-number-empty")
        self.assertNotEqual(-1, guard,
                            "no PR-number guard: the registry write, the append-only "
                            "contribution_submitted record and the label transition are all "
                            "keyed on a value nothing validates")
        for what, needle in (("registry write", 'status: "contributed"'),
                             ("ledger append", 'event: "contribution_submitted"'),
                             ("label transition", "--add-label")):
            at = b.find(needle)
            if at == -1:
                continue
            self.assertLess(
                guard, at,
                f"the PR-number guard sits AFTER the {what}. An append-only record written "
                f"with an empty key cannot be taken back.")

    def test_the_guard_refuses_rather_than_defaulting(self):
        b = self.block()
        seg = b[b.index("REFUSE:pr-number-empty") - 200:b.index("REFUSE:pr-number-empty") + 200]
        self.assertIn("exit 1", seg,
                      "the guard reports but does not stop; a warning does not prevent the "
                      "durable write that follows it")


class TestStrictMode(unittest.TestCase):
    """W7.3 -- `set -euo pipefail` throughout, the issue's fail-loudly clause.

    The file was written under `set -u` only: unset variables aborted, but a failing command
    did not, and a failing pipeline stage was invisible behind a successful last stage. That
    is why this wave is LAST -- it changes the exit behaviour of every block the earlier waves
    touched, so doing it earlier would have made every later failure ambiguous.

    Note `2>/dev/null` protects nothing here: it redirects stderr and leaves exit status
    untouched. Fifty-one of those in this file were mistaken for protection during planning.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = WF.read_text(encoding="utf-8")

    def _run_blocks(self):
        """Every run block, with its first non-comment shell line.

        Matches both `run: |` and the bare `- run: |` step form. An earlier version matched
        only the first, so two blocks were invisible to it -- and stayed invisible until the
        separate `set -u` assertion disagreed with it. Two checks over the same property,
        written independently, is what surfaced the gap.
        """
        import re
        out = []
        lines = self.text.split("\n")
        for i, ln in enumerate(lines):
            if re.match(r"\s*-?\s*run: \|\s*$", ln):
                indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                body = []
                for nxt in lines[i + 1:]:
                    if nxt.strip() and (len(nxt) - len(nxt.lstrip())) < indent:
                        break
                    body.append(nxt)
                first = next((b.strip() for b in body
                              if b.strip() and not b.strip().startswith("#")), "")
                out.append((i + 1, first, "\n".join(body)))
        return out

    def test_every_run_block_enables_strict_mode(self):
        offenders = [(ln, first[:60]) for ln, first, _ in self._run_blocks()
                     if "set -euo pipefail" not in _]
        self.assertEqual(
            [], offenders,
            f"{len(offenders)} run block(s) do not enable strict mode: {offenders[:5]}")

    def test_no_block_enables_only_set_u(self):
        weak = [ln for ln, _, body in self._run_blocks()
                if re.search(r"^\s*set -u\s*$", body, re.M)]
        self.assertEqual([], weak,
                         f"blocks still enabling only `set -u` (line numbers): {weak}")
