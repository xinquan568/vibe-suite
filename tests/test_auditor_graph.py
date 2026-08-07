# SPDX-License-Identifier: ISC
"""T1 (vibe-59 / E8.2): the auditor-contribute job graph, asserted as a complete topology.

Raw-text parsing only — the repo bans third-party YAML parsers in shipped tooling and PyYAML is
not installed (precedent: tests/test_auditor_workflows.py, tools/coverage-check.py). The
assertions are the plan's job table read literally: five jobs, their exact `needs:` sets, one
authority per job, the model held by exactly one authority-free job, every guard backed by an
output its named job actually writes, and artifact names that join.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WF_DIR = REPO / "auditor" / "workflows"
CONTRIBUTE = WF_DIR / "auditor-contribute.yml"

MODEL_ACTION = re.compile(r"uses:\s*\S*(?:claude-code-action|anthropics/claude-code)")
OUTPUT_REF = re.compile(r"needs\.([A-Za-z_][A-Za-z0-9_-]*)\.outputs\.([A-Za-z_][A-Za-z0-9_-]*)")

# The plan's job table (round 6, step 6, iter-2), read row by row.
EXPECTED_JOBS = ["gates", "reserve", "propose", "submit", "finalize"]
EXPECTED_NEEDS = {
    "gates": set(),
    "reserve": {"gates"},
    "propose": {"reserve"},
    "submit": {"reserve", "propose"},
    "finalize": {"gates", "reserve", "propose", "submit"},
}
SUBMIT_GUARD = "needs.propose.outputs.status == 'patches'"


def workflows():
    return sorted(WF_DIR.glob("*.yml"))


def jobs(text):
    """job name -> body lines (everything under `  <name>:` inside `jobs:`)."""
    out, cur, body, in_jobs = {}, None, [], False
    for ln in text.split("\n"):
        if re.match(r"^jobs:", ln):
            in_jobs = True
            continue
        if in_jobs and re.match(r"^[A-Za-z_]", ln):
            in_jobs = False
        if not in_jobs:
            continue
        m = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):\s*$", ln)
        if m:
            if cur:
                out[cur] = body
            cur, body = m.group(1), []
        elif cur is not None:
            body.append(ln)
    if cur:
        out[cur] = body
    return out


def _scalar_or_block(body, i, value, indent):
    """Collect a scalar value plus any continuation lines indented deeper than `indent`."""
    parts = [] if value in ("", ">", ">-", "|", "|-") else [value]
    for ln in body[i + 1:]:
        if not ln.strip():
            continue
        if len(ln) - len(ln.lstrip(" ")) <= indent:
            break
        parts.append(ln.strip())
    return " ".join(parts)


def job_needs(body):
    for i, ln in enumerate(body):
        m = re.match(r"^    needs:\s*(.*)$", ln)
        if not m:
            continue
        rest = m.group(1).strip()
        if rest.startswith("["):
            return {x.strip().strip("'\"") for x in rest.strip("[]").split(",") if x.strip()}
        if rest:
            return {rest.strip("'\"")}
        got = set()
        for ln2 in body[i + 1:]:
            m2 = re.match(r"^\s+-\s*(.+?)\s*$", ln2)
            if not m2:
                break
            got.add(m2.group(1).strip("'\""))
        return got
    return set()


def job_if(body):
    for i, ln in enumerate(body):
        m = re.match(r"^    if:\s*(.*)$", ln)
        if m:
            return _scalar_or_block(body, i, m.group(1).strip(), 4)
    return ""


def _perm_map(lines, key_indent):
    perms = {}
    pat = re.compile(r"^%s([a-z-]+):\s*(\S+)\s*$" % (" " * (key_indent + 2)))
    for i, ln in enumerate(lines):
        if re.match(r"^%spermissions:\s*(.*)$" % (" " * key_indent), ln):
            inline = re.match(r"^\s*permissions:\s*(\S.*)$", ln)
            if inline and inline.group(1).strip() not in ("", "{}"):
                return {"__inline__": inline.group(1).strip()}
            for ln2 in lines[i + 1:]:
                if not ln2.strip():
                    continue
                m = pat.match(ln2)
                if not m:
                    break
                perms[m.group(1)] = m.group(2)
            return perms
    return None


def top_permissions(text):
    return _perm_map(text.split("\n"), 0) or {}


def effective_permissions(text, body):
    own = _perm_map(body, 4)
    return own if own is not None else top_permissions(text)


#: `id-token: write` is NOT repository write authority — it mints a short-lived OIDC token so the
#: Claude action can authenticate without a long-lived secret, and the action fails immediately
#: without it (the reference recorded five consecutive silent daily failures from exactly that
#: omission). Counting it as write authority would forbid every model job from running at all, so
#: it is excluded here. Repository-mutating scopes (contents, issues, pull-requests, actions,
#: packages, deployments) are what this predicate is about.
_NOT_REPO_WRITE = {"id-token"}


def has_write(perms):
    return any(v == "write" for k, v in perms.items() if k not in _NOT_REPO_WRITE) or \
        perms.get("__inline__") in ("write-all",)


def body_text(body):
    return "\n".join(body)


def artifact_names(text, action):
    """Names passed to upload-artifact / download-artifact, in file order."""
    names, lines = [], text.split("\n")
    for i, ln in enumerate(lines):
        if action not in ln or "uses:" not in ln:
            continue
        base = len(ln) - len(ln.lstrip(" "))
        for ln2 in lines[i + 1:i + 12]:
            if ln2.strip().startswith("- ") or (ln2.strip() and
                                                len(ln2) - len(ln2.lstrip(" ")) < base):
                break
            m = re.match(r"^\s*name:\s*(\S+)\s*$", ln2)
            if m:
                names.append(m.group(1).strip("'\""))
                break
    return names


def github_outputs(body):
    """Output names the job's steps write to $GITHUB_OUTPUT, plus any declared `outputs:` keys."""
    txt = body_text(body)
    got = set(re.findall(r"([A-Za-z_][A-Za-z0-9_-]*)=[^\n]*>>\s*\"?\$\{?GITHUB_OUTPUT", txt))
    for i, ln in enumerate(body):
        if re.match(r"^    outputs:\s*$", ln):
            for ln2 in body[i + 1:]:
                m = re.match(r"^      ([A-Za-z_][A-Za-z0-9_-]*):\s*\S", ln2)
                if not m:
                    break
                got.add(m.group(1))
    return got


class ContributeTopology(unittest.TestCase):
    """The five-job graph of auditor-contribute.yml (plan job table)."""

    @classmethod
    def setUpClass(cls):
        cls.text = CONTRIBUTE.read_text()
        cls.jobs = jobs(cls.text)

    def body(self, name):
        self.assertIn(name, self.jobs,
                      f"auditor-contribute.yml has no '{name}' job; jobs are "
                      f"{sorted(self.jobs)}")
        return self.jobs[name]

    def test_contribute_declares_exactly_the_five_planned_jobs(self):
        self.assertEqual(sorted(self.jobs), sorted(EXPECTED_JOBS),
                         "the contribute graph is not the planned five jobs "
                         f"(gates/reserve/propose/submit/finalize); found {sorted(self.jobs)}")

    def test_needs_edges_are_exactly_the_planned_dependency_sets(self):
        for name, want in EXPECTED_NEEDS.items():
            with self.subTest(job=name):
                got = job_needs(self.body(name))
                self.assertEqual(got, want,
                                 f"job '{name}' needs {sorted(got)}; the plan's job table "
                                 f"requires {sorted(want)}")

    def test_gates_holds_no_write_authority(self):
        perms = effective_permissions(self.text, self.body("gates"))
        self.assertFalse(has_write(perms),
                         f"'gates' runs with write authority ({perms}); the gate job must be "
                         "read-only so a refused run consumes nothing")

    def test_reserve_holds_contents_write_and_never_calls_the_model(self):
        body = self.body("reserve")
        perms = effective_permissions(self.text, body)
        self.assertEqual(perms.get("contents"), "write",
                         f"'reserve' must declare `contents: write` to append the reservation; "
                         f"it declares {perms}")
        self.assertIsNone(MODEL_ACTION.search(body_text(body)),
                          "'reserve' holds contents: write AND a model action — the write "
                          "authority and the model must never share a job")

    def test_propose_is_the_only_model_job_and_holds_neither_issues_write_nor_the_pat(self):
        body = self.body("propose")
        txt = body_text(body)
        self.assertIsNotNone(MODEL_ACTION.search(txt),
                             "'propose' has no model action; the patch proposal is the model's "
                             "only job in this graph")
        perms = effective_permissions(self.text, body)
        self.assertNotEqual(perms.get("issues"), "write",
                            f"'propose' declares `issues: write` ({perms}); the model job must "
                            "not be able to transition the issue")
        self.assertFalse(has_write(perms),
                         f"'propose' holds write authority ({perms}); audited content is data "
                         "and the model job must be read-only")
        self.assertNotIn("PAT_TOKEN", txt,
                         "'propose' references PAT_TOKEN; the model job must never see the PAT")

    def test_submit_holds_the_pat_and_never_calls_the_model(self):
        txt = body_text(self.body("submit"))
        self.assertIn("PAT_TOKEN", txt,
                      "'submit' does not reference PAT_TOKEN; the fork/push/PR authority lives "
                      "in this job")
        self.assertIsNone(MODEL_ACTION.search(txt),
                          "'submit' contains a model action while holding the PAT — the "
                          "injection separation requires the PAT-bearing job to run no model")

    def test_finalize_runs_always_holds_no_pat_and_can_close_the_issue(self):
        body = self.body("finalize")
        guard = job_if(body)
        self.assertIn("always()", guard,
                      f"'finalize' guard is {guard!r}; it must contain always() so a refusal "
                      "from any upstream stage is still routed")
        txt = body_text(body)
        self.assertNotIn("PAT_TOKEN", txt,
                         "'finalize' references PAT_TOKEN; only 'submit' may hold it")
        perms = effective_permissions(self.text, body)
        self.assertEqual(perms.get("contents"), "write",
                         f"'finalize' must declare `contents: write` to commit the refusal "
                         f"event; it declares {perms}")
        self.assertEqual(perms.get("issues"), "write",
                         f"'finalize' must declare `issues: write` to apply the side-exit "
                         f"label; it declares {perms}")

    def test_submit_guard_tests_propose_status_not_bare_success(self):
        guard = job_if(self.body("submit"))
        norm = " ".join(guard.split()).replace('"', "'")
        self.assertIn(SUBMIT_GUARD, norm,
                      f"'submit' guard is {guard!r}; it must test "
                      f"{SUBMIT_GUARD!r} — a propose job that succeeds while producing "
                      "'no-patches' or 'refused' must not enter submission")
        self.assertNotEqual(norm.strip(), "success()",
                            "'submit' is guarded by a bare success(), which cannot distinguish "
                            "'patches' from 'no-patches' or 'refused'")

    def test_every_guard_output_reference_is_written_by_its_named_job(self):
        refs = set(OUTPUT_REF.findall(self.text))
        for edge in (("gates", "proceed"), ("reserve", "reserved"), ("propose", "status")):
            self.assertIn(edge, refs,
                          f"no guard references needs.{edge[0]}.outputs.{edge[1]}; the plan's "
                          "propagation edge is unwired")
        for job, out in sorted(refs):
            with self.subTest(ref=f"needs.{job}.outputs.{out}"):
                self.assertIn(job, self.jobs,
                              f"needs.{job}.outputs.{out} names a job that does not exist")
                written = github_outputs(self.jobs[job])
                self.assertIn(out, written,
                              f"needs.{job}.outputs.{out} is consumed but job '{job}' never "
                              f"writes '{out}' to $GITHUB_OUTPUT (it writes {sorted(written)})")

    def test_artifact_download_names_match_an_upload(self):
        ups = set(artifact_names(self.text, "upload-artifact"))
        for name in artifact_names(self.text, "download-artifact"):
            with self.subTest(artifact=name):
                self.assertIn(name, ups,
                              f"download-artifact pulls '{name}' but no job uploads that name "
                              f"(uploads: {sorted(ups)})")

    def test_each_stage_publishes_its_outcome_artifact(self):
        ups = set(artifact_names(self.text, "upload-artifact"))
        for job in EXPECTED_JOBS:
            with self.subTest(job=job):
                self.assertTrue(any(f"outcome-{job}" in u for u in ups),
                                f"job '{job}' publishes no outcome-{job} artifact; finalize "
                                "cannot select the outcome row without it")


class SuiteAuthority(unittest.TestCase):
    """Authority scoping across all 18 auditor workflows."""

    def test_no_job_holds_both_a_model_action_and_write_authority(self):
        offenders = []
        for path in workflows():
            text = path.read_text()
            for name, body in jobs(text).items():
                if not MODEL_ACTION.search(body_text(body)):
                    continue
                perms = effective_permissions(text, body)
                if has_write(perms):
                    offenders.append(f"{path.name}:{name} {perms}")
        self.assertEqual(offenders, [],
                         "these jobs run a model AND hold write authority, collapsing the "
                         "injection separation: " + "; ".join(offenders))

    def test_eighteen_workflows_are_present(self):
        self.assertEqual(len(workflows()), 18,
                         f"expected 18 auditor workflows, found {len(workflows())}")

    def test_integration_unit_and_smoke_tiers_declare_no_secrets(self):
        path = WF_DIR / "auditor-integration-test.yml"
        text = path.read_text()
        js = jobs(text)
        for name in ("unit", "smoke"):
            with self.subTest(job=name):
                self.assertIn(name, js, f"auditor-integration-test.yml has no '{name}' job")
                found = sorted(set(re.findall(r"secrets\.([A-Z_]+)", body_text(js[name]))))
                self.assertEqual(found, [],
                                 f"the '{name}' tier requires secrets {found}; the preflight "
                                 "posture is that the cheap tiers run without any secret")


if __name__ == "__main__":
    unittest.main()
