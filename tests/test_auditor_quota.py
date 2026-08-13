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
        # Through the relay, not the environment -- see
        # tests/test_auditor_no_supplied_derivations.py for why this matters.
        ctx = sb.root / "context.json"
        ctx.write_text(json.dumps({
            "version": 1, "repo": TARGET, "issue": "42",
            "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
            "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
            "weekly_cap": 2, "patch_cap": cap}))
        # An API answer, not a derivation: emit-manifest now refuses without the open-PR list
        # (F9), because filter 3's input had been bound nowhere and the duplicate check was
        # skipped on every run. Empty is the honest value -- these cases exercise the cap.
        open_prs = sb.root / "open-prs.json"
        open_prs.write_text("[]")
        r = sb.run(self.block("emit-manifest"), env={
            "REPO": TARGET, "OWNER": TARGET.split("/")[0],
            "SIDECAR": str(FIX / "findings-sidecar.jsonl"),
            "CODE_DIR": str(REPO_ROOT), "CONTEXT_FILE": str(ctx),
            "MANIFEST": str(sb.root / "proposal-manifest.json"),
            "OPEN_PRS_FILE": str(open_prs),
            "PLANNED_COUNT": "4"})
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

    def test_every_run_block_enables_strict_mode_as_its_first_command(self):
        """F11: the helper computed `first` and the assertion then ignored it.

        The old check was `"set -euo pipefail" not in body` -- the marker anywhere in the
        block. A block that runs five commands and then enables strict mode passes that check
        while those five commands fail open, which is the whole failure this wave exists to
        remove. The helper had already computed the first executable command; the assertion
        just never used it.
        """
        offenders = [(ln, first[:60]) for ln, first, _ in self._run_blocks()
                     if first != "set -euo pipefail"]
        self.assertEqual(
            [], offenders,
            f"{len(offenders)} run block(s) do not enable strict mode as their FIRST "
            f"executable command: {offenders[:5]}")

    def test_the_block_scan_still_sees_the_whole_file(self):
        """A count, so a scan that quietly stopped matching cannot pass by finding nothing.

        The review measured 20 YAML run blocks against a claim of 22 -- the extra two were
        `set -euo pipefail` occurrences inside one block, not blocks. An unasserted count is
        how a shrinking scan stays invisible.
        """
        n = len(self._run_blocks())
        self.assertGreaterEqual(
            n, 20,
            f"the strict-mode scan found only {n} run blocks; if the step form changed it is "
            f"now checking almost nothing and will pass regardless")

    def test_no_block_enables_only_set_u(self):
        weak = [ln for ln, _, body in self._run_blocks()
                if re.search(r"^\s*set -u\s*$", body, re.M)]
        self.assertEqual([], weak,
                         f"blocks still enabling only `set -u` (line numbers): {weak}")


class TestTheRefusalBranchesWork(QuotaBase):
    """The named refusals, executed. **This class is not strict-mode evidence.**

    It was called `TestStrictModeIsBehavioural` and claimed to be exactly that. The review
    refuted it: every case here reaches an explicit `|| { echo REFUSE...; exit 1; }`, so every
    one of them stays green with `set -euo pipefail` removed from the workflow entirely. They
    test the guards, which is worth doing; they say nothing whatever about strict mode.

    The claim is corrected rather than the tests deleted, and the cases that DO isolate strict
    mode live in TestStrictModeChangesBehaviour below, where each one is proved by running the
    same block twice -- once as written, once with the marker stripped -- and requiring the two
    to differ. A test that cannot tell the two apart is not evidence about the difference.
    """

    def _sb(self):
        sb = Sandbox(registry="registry-audited.json")
        self.addCleanup(sb.cleanup)
        return sb

    def _emit_env(self, sb, context_text=None, open_prs="[]"):
        ctx = sb.root / "context.json"
        ctx.write_text(context_text if context_text is not None else json.dumps({
            "version": 1, "repo": TARGET, "issue": "42",
            "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
            "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
            "weekly_cap": 2, "patch_cap": 3}))
        prs = sb.root / "open-prs.json"
        prs.write_text(open_prs)
        return {"REPO": TARGET, "OWNER": TARGET.split("/")[0],
                "SIDECAR": str(FIX / "findings-sidecar.jsonl"),
                "CODE_DIR": str(REPO_ROOT), "CONTEXT_FILE": str(ctx),
                "MANIFEST": str(sb.root / "proposal-manifest.json"),
                "OPEN_PRS_FILE": str(prs), "PLANNED_COUNT": "4"}

    def test_malformed_json_input_aborts_rather_than_reading_as_empty(self):
        # jq on a non-JSON file exits non-zero and prints nothing, so the cap reads as empty.
        # What stops the block is the explicit `[ -n "$cap" ] ||` guard below, NOT strict mode
        # -- this comment used to credit strict mode and that was the overclaim the review
        # caught. The guard is worth testing on its own terms.
        sb = self._sb()
        r = sb.run(self.block("emit-manifest"),
                   env=self._emit_env(sb, context_text="<html>502 Bad Gateway</html>"))
        self.assertNotEqual(0, r.returncode,
                            "a malformed relay was read as an absent value and the block "
                            "continued past the guard that exists to stop exactly that")
        self.assertIn("REFUSE:context-patch-cap-unresolvable", r.stdout + r.stderr)

    def test_a_missing_required_file_aborts(self):
        sb = self._sb()
        env = self._emit_env(sb)
        env["CONTEXT_FILE"] = str(sb.root / "does-not-exist.json")
        r = sb.run(self.block("emit-manifest"), env=env)
        self.assertNotEqual(0, r.returncode)
        self.assertIn("REFUSE:context-relay-missing-unresolvable", r.stdout + r.stderr)

    def test_an_api_failure_aborts_rather_than_yielding_an_empty_answer(self):
        # The open-PR fetch: `gh` exits non-zero. Before F9 this class of failure was
        # indistinguishable from "no open PRs", which is the strongest form of failing open.
        sb = self._sb()
        gh = sb.bin / "gh"
        gh.write_text("#!/usr/bin/env bash\necho 'HTTP 403' >&2\nexit 1\n")
        gh.chmod(0o755)
        r = sb.run(self.block("open-prs", marker="stage-logic"),
                   env={"REPO": TARGET, "GITHUB_ENV": str(sb.root / "gh.env")})
        self.assertNotEqual(0, r.returncode)
        self.assertIn("REFUSE:open-prs-unavailable", r.stdout + r.stderr)

    def test_a_failing_early_pipeline_stage_is_not_hidden_by_a_successful_last_one(self):
        # Kept for the property, but note it runs a SYNTHETIC script, not a workflow block --
        # so it establishes that bash honours pipefail, which was never in doubt. It is not
        # evidence about this workflow. See TestStrictModeChangesBehaviour.
        script = "set -euo pipefail\nfalse | cat\necho REACHED\n"
        r = self._sb().run(script)
        self.assertNotEqual(0, r.returncode,
                            "a failing first pipeline stage was masked by a successful last "
                            "stage; pipefail is not in effect")
        self.assertNotIn("REACHED", r.stdout)


def _without_strict_mode(block):
    """The same block with its strict-mode marker removed, and nothing else changed."""
    out = [l for l in block.split("\n") if l.strip() != "set -euo pipefail"]
    assert len(out) < len(block.split("\n")), "the block carried no strict-mode marker to strip"
    return "\n".join(out)


class TestStrictModeChangesBehaviour(QuotaBase):
    """F11, round 4: prove the difference by executing both sides of it.

    The structural assertion shows a string sits in a position. The refusal tests above show
    the guards fire. Neither can show what strict mode itself buys, because a block whose
    failure paths are all explicitly guarded behaves identically without it -- which is exactly
    what the review found, and why those four cases were withdrawn as evidence.

    So each case here runs the SAME block twice, once as written and once with `set -euo
    pipefail` stripped, and requires the two to differ. If a case cannot tell them apart it is
    not evidence about strict mode, and it fails rather than passing quietly.

    What strict mode demonstrably buys this workflow is TWO mechanisms, each proven by a
    differential. The first is a failed output redirection under `set -e`, shown below at two
    independent sites (the open-PR export and the manifest write) -- round 3 called those two
    classes, which overstated it; they abort by the same mechanism. The second is a failing
    early pipeline stage under `pipefail`: round 4 claimed this could not exist because the
    workflow's pipelines start from `printf` of in-memory values, and the review falsified
    that -- submit's allowlist read is `jq … "$MANIFEST" | sort -u`, where a manifest that
    exists but does not parse fails jq behind a successful sort. That differential lives with
    its sandbox in tests/test_auditor_submit.py::SubmitPipefailChangesBehaviour.

    `set -u` alone still has no workflow-level differential to show, and that is by
    construction rather than omission: it needs an unguarded read of an unset name, and every
    read is bound, defaulted or `:?`-guarded -- enforced structurally, per step and in order,
    by TestEveryJobBindsWhatItReads. `${SIDECAR:?}` was tried as a set-u candidate and
    REJECTED for exactly this reason: the explicit `:?` does the work and `set -u` adds
    nothing to it. The synthetic pipefail case in TestTheRefusalBranchesWork covers the
    primitive and says it is not workflow evidence.
    """

    def _both(self, block, env_builder):
        """Run `block` as written and stripped, in two fresh sandboxes. Returns both results."""
        results = []
        for script in (block, _without_strict_mode(block)):
            sb = Sandbox(registry="registry-audited.json")
            self.addCleanup(sb.cleanup)
            results.append((sb, sb.run(script, env=env_builder(sb))))
        return results

    def test_an_unwritable_relay_destination_aborts_instead_of_exporting_a_broken_path(self):
        def env(sb):
            canned = sb.root / "canned"; canned.write_text("[]")
            m = sb.root / "map"; m.write_text("pr list\t" + str(canned) + "\n")
            # A regular file where a directory would have to be: the redirect cannot succeed.
            blocker = sb.root / "blocker"; blocker.write_text("x")
            return {"REPO": TARGET, "GH_CANNED_MAP": str(m),
                    "GITHUB_ENV": str(sb.root / "gh.env"),
                    "OPEN_PRS_FILE": str(blocker / "prs.json")}

        (sb_real, real), (sb_weak, weak) = self._both(
            self.block("open-prs", marker="stage-logic"), env)

        self.assertNotEqual(0, real.returncode,
                            "the block reported success after failing to write the open-PR list")
        self.assertEqual(0, weak.returncode,
                         "stripping strict mode changed nothing here, so this case proves "
                         "nothing about strict mode -- replace it with one that does")
        weak_env = (sb_weak.root / "gh.env").read_text()
        self.assertIn(
            "OPEN_PRS_FILE=", weak_env,
            "without strict mode the block should export a path to a file it never wrote; if "
            "it does not, the two runs are indistinguishable and the case is vacuous")
        real_env_file = sb_real.root / "gh.env"
        self.assertNotIn(
            "OPEN_PRS_FILE=", real_env_file.read_text() if real_env_file.exists() else "",
            "the real block exported the path anyway, so the abort came too late to matter")

    def test_an_unwritable_manifest_aborts_instead_of_reporting_an_allowlist_it_never_wrote(self):
        # The sharpest one. Without strict mode this block prints `MANIFEST:n admitted` and
        # `PASS` while the file it describes does not exist -- gates reports the allowlist was
        # written, and submit then refuses `manifest-missing` for reasons the gate log denies.
        def env(sb):
            ctx = sb.root / "context.json"
            ctx.write_text(json.dumps({
                "version": 1, "repo": TARGET, "issue": "42",
                "expected_fork_slug": "vibe-bot/claude-toolkit", "audited_sha": "cafebabe",
                "base_branch": "main", "author_name": "n", "author_email": "e@x.invalid",
                "weekly_cap": 2, "patch_cap": 3}))
            prs = sb.root / "open-prs.json"; prs.write_text("[]")
            blocker = sb.root / "blocker"; blocker.write_text("x")
            return {"REPO": TARGET, "OWNER": TARGET.split("/")[0],
                    "SIDECAR": str(FIX / "findings-sidecar.jsonl"),
                    "CODE_DIR": str(REPO_ROOT), "CONTEXT_FILE": str(ctx),
                    "OPEN_PRS_FILE": str(prs), "PLANNED_COUNT": "4",
                    "MANIFEST": str(blocker / "m.json")}

        (_, real), (_, weak) = self._both(self.block("emit-manifest"), env)

        self.assertNotEqual(0, real.returncode,
                            "the gate passed without writing the allowlist submit validates "
                            "every patch against")
        self.assertEqual(0, weak.returncode,
                         "stripping strict mode changed nothing here, so this case proves "
                         "nothing about strict mode")
        self.assertIn("PASS", weak.stdout,
                      "without strict mode the gate should report PASS on a manifest it never "
                      "wrote; if it does not, the two runs are indistinguishable")
        self.assertNotIn("PASS", real.stdout)
