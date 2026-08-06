# SPDX-License-Identifier: ISC
"""The E8.2 workflow lint (vibe-59): fail-closed structural checks over auditor/workflows/*.yml.

This IS the "workflow lint green" acceptance clause at the current gate rung: a stdlib subset
grammar (the repo bans third-party YAML parsers in shipped tooling; precedent:
tools/coverage-check.py hand-parses disposition.yaml), plus `bash -n` on every extracted run
block, plus mutation cases proving each predicate actually fails when violated.
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WF_DIR = REPO / "auditor" / "workflows"

STAGES = {
    "auditor-discover.yml": "audit-candidate",
    "auditor-audit.yml": "audit-ready",
    "auditor-contribute.yml": "contribute-approved",
    "auditor-track.yml": None,            # cron-driven scanner
    "auditor-case-study.yml": "case-study-ready",
    "auditor-daily-report.yml": None,     # cron-driven observer
}
SUPPORTING = [
    "auditor-classify.yml", "auditor-batch-processor.yml", "auditor-integration-test.yml",
    "auditor-render-dashboard.yml", "auditor-repo-report.yml", "auditor-suppressions.yml",
    "auditor-vocab-drift.yml",
]
FEEDBACK = [
    "auditor-exemplar.yml", "auditor-cite-exemplars.yml", "auditor-refine-rules.yml",
    "auditor-rule-review.yml", "auditor-docs-diff.yml",
]
EXPECTED = sorted(list(STAGES) + SUPPORTING + FEEDBACK)

MODEL_WORKFLOWS = [
    "auditor-audit.yml", "auditor-contribute.yml", "auditor-case-study.yml",
    "auditor-classify.yml", "auditor-integration-test.yml", "auditor-vocab-drift.yml",
    "auditor-exemplar.yml", "auditor-refine-rules.yml",
]
DATA_WRITERS = [
    "auditor-discover.yml", "auditor-audit.yml", "auditor-contribute.yml", "auditor-track.yml",
    "auditor-case-study.yml", "auditor-daily-report.yml", "auditor-classify.yml",
    "auditor-render-dashboard.yml", "auditor-repo-report.yml", "auditor-suppressions.yml",
    "auditor-vocab-drift.yml", "auditor-exemplar.yml", "auditor-refine-rules.yml",
    "auditor-docs-diff.yml",
]

TOP_KEYS = {"name", "on", "permissions", "concurrency", "env", "jobs"}
KNOWN_SECRETS = {"CLAUDE_CODE_OAUTH_TOKEN", "PAT_TOKEN", "OPENAI_API_KEY", "GITHUB_TOKEN"}
BLOCKED_CMDS = ["curl", "wget", "nc", "ncat", "socat", "telnet", "ssh", "scp", "sftp", "rsync"]

MODEL_ID = re.compile(
    r"claude-[a-z]+-[0-9]|claude-[a-z0-9-]*-20[0-9]{2}|gpt-[0-9]|gemini-[0-9]|o[0-9]-|"
    r"--model\b|(^|\s)model:", re.M)
EXPR = re.compile(r"\$\{\{(.*?)\}\}", re.S)
EXPR_GRAMMAR = re.compile(
    r"^[\s(!]*(github|secrets|inputs|needs|env|matrix|steps|vars|runner|"
    r"contains|startsWith|endsWith|format|join|toJSON|fromJSON|hashFiles|"
    r"always|failure|success|cancelled|true|false|null|[0-9'\"])")
_EXPR_TOKEN = re.compile(
    r"[A-Za-z_][A-Za-z0-9_-]*|\.|\(|\)|\[|\]|,|!|&&|\|\||[=!<>]=?|\*|'[^']*'|\"[^\"]*\"|"
    r"[0-9.]+|\s+")
_ALLOWED_ROOTS = {"github", "secrets", "inputs", "needs", "env", "matrix", "steps", "vars",
                  "runner"}
_ALLOWED_FUNCS = {"contains", "startsWith", "endsWith", "format", "join", "toJSON", "fromJSON",
                  "hashFiles", "always", "failure", "success", "cancelled"}


def lint(text, name="workflow.yml"):
    """Return a list of violation strings for one workflow file's raw text."""
    v = []
    lines = text.split("\n")
    if "\t" in text:
        v.append("tab character")
    # top-level keys + duplicate detection per indent block
    seen_stack = [(-1, set())]
    for i, ln in enumerate(lines, 1):
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        if ln.strip().startswith("- "):
            continue  # sequence items may repeat
        m = re.match(r"^( *)([A-Za-z_][A-Za-z0-9_./ -]*):(\s|$)", ln)
        if not m:
            continue
        if indent % 2:
            v.append(f"line {i}: off-grid indentation ({indent})")
        key = m.group(2)
        while seen_stack and seen_stack[-1][0] >= indent:
            seen_stack.pop()
        parent = seen_stack[-1][1] if seen_stack else set()
        tag = (indent, key)
        if tag in parent:
            v.append(f"line {i}: duplicate key '{key}'")
        parent.add(tag)
        seen_stack.append((indent, {(indent, key)} if False else parent and set()))
        seen_stack[-1] = (indent, set())
        if indent == 0 and key not in TOP_KEYS:
            v.append(f"line {i}: unknown top-level key '{key}'")
    # duplicate top-level keys (simpler, reliable pass)
    tops = [re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", ln).group(1)
            for ln in lines if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:", ln)]
    for k in set(tops):
        if tops.count(k) > 1:
            v.append(f"duplicate top-level key '{k}'")
    # jobs shape
    jobs = _jobs(lines)
    if not jobs:
        v.append("no jobs")
    for jname, body in jobs.items():
        if not any(re.match(r"^    runs-on:", ln) for ln in body):
            v.append(f"job '{jname}' missing runs-on")
        if not any(re.match(r"^    steps:", ln) for ln in body):
            v.append(f"job '{jname}' missing steps")
        step_txt = "\n".join(body)
        for sm in re.finditer(r"^      - (?:name:.*)?$", step_txt, re.M):
            pass
    # every step item has uses: or run:
    for jname, body in jobs.items():
        for step in _steps(body):
            if not any(re.match(r"\s*(uses|run):", ln) for ln in step):
                v.append(f"job '{jname}': step with neither uses nor run")
    # expressions
    for m in EXPR.finditer(text):
        inner = m.group(1).strip()
        if not _expr_ok(inner):
            v.append(f"expression outside grammar: {inner[:60]}")
    # secrets by name
    for sm in re.finditer(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text):
        if sm.group(1) not in KNOWN_SECRETS:
            v.append(f"unknown secret '{sm.group(1)}'")
    # model pins
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("#"):
            continue
        if MODEL_ID.search(ln):
            v.append(f"line {i}: model id / model key: {ln.strip()[:60]}")
    # deferred scripts guard
    for i, ln in enumerate(lines, 1):
        if "auditor/scripts/" in ln:
            window = "\n".join(lines[max(0, i - 4):i + 1])
            if "deferred:E8.3" not in window:
                v.append(f"line {i}: unguarded auditor/scripts/ reference")
    return v


def _jobs(lines):
    jobs, cur, body = {}, None, []
    in_jobs = False
    for ln in lines:
        if re.match(r"^jobs:", ln):
            in_jobs = True
            continue
        if in_jobs and re.match(r"^[A-Za-z_]", ln):
            in_jobs = False
        if in_jobs:
            m = re.match(r"^  ([A-Za-z_][A-Za-z0-9_-]*):\s*$", ln)
            if m:
                if cur:
                    jobs[cur] = body
                cur, body = m.group(1), []
            elif cur:
                body.append(ln)
    if cur:
        jobs[cur] = body
    return jobs


def _steps(job_body):
    steps, cur = [], None
    for ln in job_body:
        if re.match(r"^      - ", ln):
            if cur:
                steps.append(cur)
            cur = [re.sub(r"^      - ", "        ", ln)]
        elif cur is not None and (ln.startswith("        ") or not ln.strip()):
            cur.append(ln)
        elif cur is not None and ln.strip():
            steps.append(cur)
            cur = None
    if cur:
        steps.append(cur)
    return steps


def _expr_ok(inner):
    pos, saw_root = 0, False
    while pos < len(inner):
        m = _EXPR_TOKEN.match(inner, pos)
        if not m:
            return False
        tok = m.group(0)
        if re.match(r"^[A-Za-z_]", tok):
            nxt = inner[m.end():m.end() + 1]
            if nxt == "(":
                if tok not in _ALLOWED_FUNCS:
                    return False
            elif not saw_root or inner[max(0, pos - 1)] != ".":
                if tok not in _ALLOWED_ROOTS | {"true", "false", "null"} \
                        and inner[max(0, pos - 1):pos] != ".":
                    return False
            saw_root = True
        pos = m.end()
    return True


def extract_run_blocks(text):
    """Yield the shell text of every run: block (raw-text extraction, no YAML parse)."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)run:\s*\|", lines[i])
        if m:
            base = len(m.group(1)) + 2
            block = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith(" " * base)):
                block.append(lines[i][base:])
                i += 1
            yield "\n".join(block)
        else:
            m2 = re.match(r"^\s*run:\s*(\S.*)$", lines[i])
            if m2:
                yield m2.group(1)
            i += 1


class TestInventory(unittest.TestCase):
    def test_exactly_the_18_expected_files(self):
        self.assertTrue(WF_DIR.is_dir(), f"{WF_DIR} missing")
        actual = sorted(p.name for p in WF_DIR.glob("*.yml"))
        self.assertEqual(actual, EXPECTED)

    def test_no_python_under_auditor_and_no_scripts_dir(self):
        self.assertEqual(list((REPO / "auditor").rglob("*.py")), [])
        self.assertFalse((REPO / "auditor" / "scripts").exists())


class TestLintClean(unittest.TestCase):
    def test_every_workflow_passes_the_lint(self):
        for name in EXPECTED:
            path = WF_DIR / name
            self.assertTrue(path.is_file(), f"{name} missing")
            with self.subTest(workflow=name):
                self.assertEqual(lint(path.read_text(), name), [])

    def test_every_run_block_passes_bash_n(self):
        for name in EXPECTED:
            path = WF_DIR / name
            if not path.is_file():
                self.fail(f"{name} missing")
            for idx, block in enumerate(extract_run_blocks(path.read_text())):
                shell = re.sub(r"\$\{\{.*?\}\}", "EXPR", block, flags=re.S)
                with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
                    f.write(shell)
                r = subprocess.run(["bash", "-n", f.name], capture_output=True, text=True)
                with self.subTest(workflow=name, block=idx):
                    self.assertEqual(r.returncode, 0, r.stderr)


class TestContracts(unittest.TestCase):
    def _text(self, name):
        p = WF_DIR / name
        self.assertTrue(p.is_file(), f"{name} missing")
        return p.read_text()

    def test_model_workflows_carry_the_blocklist_and_data_framing(self):
        for name in MODEL_WORKFLOWS:
            t = self._text(name)
            with self.subTest(workflow=name):
                self.assertIn("disallowedTools", t)
                for cmd in BLOCKED_CMDS:
                    self.assertIn(cmd, t)
                self.assertNotIn("WebFetch,", t.replace('"WebFetch"', ""))
                self.assertRegex(t, r"data,? (never|not) instructions")

    def test_data_writers_name_the_data_branch(self):
        for name in DATA_WRITERS:
            with self.subTest(workflow=name):
                self.assertIn("auditor-data", self._text(name))

    def test_stage_workflows_carry_their_entry_labels(self):
        for name, label in STAGES.items():
            if label:
                with self.subTest(workflow=name):
                    self.assertIn(label, self._text(name))

    def test_contribute_separates_model_from_pat(self):
        t = self._text("auditor-contribute.yml")
        jobs = _jobs(t.split("\n"))
        self.assertGreaterEqual(len(jobs), 2, "contribute must be >= 2 jobs (model/PAT split)")
        for jname, body in jobs.items():
            bt = "\n".join(body)
            uses_model = "claude-code-action" in bt
            uses_pat = "PAT_TOKEN" in bt
            self.assertFalse(uses_model and uses_pat,
                             f"job '{jname}' holds both the model and PAT_TOKEN")

    def test_no_legacy_namespace_strings(self):
        for name in EXPECTED:
            t = self._text(name)
            with self.subTest(workflow=name):
                for bad in ("/nlpm:", "/cc-suite:", "/grill:", "/vibe:"):
                    self.assertNotIn(bad, t)


class TestMutations(unittest.TestCase):
    GOOD = (
        "name: t\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
        "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - name: x\n"
        "        run: echo ok\n")

    def test_good_skeleton_is_clean(self):
        self.assertEqual(lint(self.GOOD), [])

    def _assert_flagged(self, text):
        self.assertNotEqual(lint(text), [])

    def test_tab_indent(self):
        self._assert_flagged(self.GOOD.replace("  a:", "\ta:"))

    def test_off_grid_indent(self):
        self._assert_flagged(self.GOOD.replace("  contents: read", "   contents: read"))

    def test_duplicate_top_key(self):
        self._assert_flagged(self.GOOD + "name: again\n")

    def test_unknown_top_key(self):
        self._assert_flagged(self.GOOD + "banana: yes\n")

    def test_job_missing_runs_on(self):
        self._assert_flagged(self.GOOD.replace("    runs-on: ubuntu-latest\n", ""))

    def test_step_with_neither_uses_nor_run(self):
        self._assert_flagged(
            self.GOOD.replace("      - name: x\n        run: echo ok\n",
                              "      - name: x\n        id: nothing\n"))

    def test_unclosed_expression_or_bad_root(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ hacks.password }}"))

    def test_non_allowlisted_function(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ exec('rm') }}"))

    def test_shell_syntax_error_in_run_block(self):
        bad = self.GOOD.replace("run: echo ok", "run: |\n          if [ ; then fi")
        blocks = list(extract_run_blocks(bad))
        self.assertTrue(blocks)
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(blocks[-1])
        r = subprocess.run(["bash", "-n", f.name], capture_output=True)
        self.assertNotEqual(r.returncode, 0)

    def test_dated_model_pin(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: tool --model claude-haiku-4-5-20251001"))

    def test_unguarded_scripts_reference(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: bash auditor/scripts/log-event.sh x"))

    def test_guarded_scripts_reference_is_allowed(self):
        guarded = self.GOOD.replace(
            "run: echo ok",
            "run: |\n          # deferred:E8.3 — helper lands with the scripts item\n"
            "          if [ -x auditor/scripts/log-event.sh ]; then\n"
            "            bash auditor/scripts/log-event.sh x\n"
            "          else\n            echo 'REFUSE:helper-missing-until-E8.3' >&2\n          fi")
        self.assertEqual([x for x in lint(guarded) if "unguarded" in x], [])

    def test_unknown_secret(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ secrets.SNEAKY_TOKEN }}"))


if __name__ == "__main__":
    unittest.main()
