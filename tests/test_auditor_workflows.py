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
    # top-level keys + duplicate detection per MAPPING (sequence items included).
    # Each `- ` item opens its own mapping scope at the content column, so a key repeated
    # inside one step is a duplicate while the same key across sibling steps is not.
    stack = []          # [(column, {keys seen in that mapping})]
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        i = idx + 1
        idx += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        body, dash = raw, re.match(r"^( *)-(\s+|$)", raw)
        if dash:
            if indent % 2:
                v.append(f"line {i}: off-grid indentation ({indent})")
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent + 2, set()))
            body, indent = " " * (indent + 2) + raw[dash.end():], indent + 2
            if not body.strip():
                continue
        m = re.match(r"^ *([A-Za-z_][A-Za-z0-9_./ -]*):(\s|$)", body)
        if not m:
            # FAIL CLOSED. This used to `continue`, which silently accepted anything the grammar
            # did not recognise — junk top-level text passed, and so did every malformed
            # construct that simply failed to look like a key. Block-scalar bodies are consumed
            # wholesale further down, so a line arriving here is structural and unrecognised.
            # A dash-introduced item whose body is a plain scalar is valid YAML — `options:` lists
            # `- unit` / `- smoke` exactly this way. `body` has already had the dash stripped, so
            # the original line is what must be tested; checking `body` here flagged every scalar
            # list entry in the suite.
            if not dash:
                v.append(f"line {i}: unrecognised construct: {body.strip()[:60]!r}")
            continue
        if not dash and indent % 2:
            v.append(f"line {i}: off-grid indentation ({indent})")
        key = m.group(1)
        while stack and stack[-1][0] > indent:
            stack.pop()
        if not stack or stack[-1][0] < indent:
            stack.append((indent, set()))
        if key in stack[-1][1]:
            v.append(f"line {i}: duplicate key '{key}'")
        stack[-1][1].add(key)
        if indent == 0 and key not in TOP_KEYS:
            v.append(f"line {i}: unknown top-level key '{key}'")
        # a block scalar's body is shell/prose, not a mapping — skip it wholesale
        if re.match(r"^[|>][-+0-9]*$", body[m.end():].strip()):
            while idx < len(lines) and (
                    not lines[idx].strip()
                    or len(lines[idx]) - len(lines[idx].lstrip(" ")) > indent):
                idx += 1
    # Required top-level structure. The mutation suite previously only ever changed a value; it
    # never REMOVED a required section, so a workflow with no `on:` trigger and no declared
    # permissions linted clean. Absence is now a violation in its own right.
    top_keys = {mm.group(1) for mm in
                (re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):", ln) for ln in lines) if mm}
    for required in ("name", "on", "jobs"):
        if required not in top_keys:
            v.append(f"missing required top-level key '{required}'")
    # Least privilege must be DECLARED, at the workflow or at every job — an undeclared workflow
    # inherits the repository default, which is exactly the authority the split exists to remove.
    if "permissions" not in top_keys:
        jobs_missing = [j for j, b in _jobs(lines).items()
                        if not any(re.match(r"^    permissions:", ln) for ln in b)]
        for j in jobs_missing:
            v.append(f"job '{j}': no permissions declared and none at workflow level")

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
    # expression delimiter pairing — must run BEFORE the pair regex, which only ever sees
    # balanced spans and is therefore blind to a `${{` that is never closed.
    scan = 0
    while True:
        open_at = text.find("${{", scan)
        if open_at < 0:
            break
        close_at = text.find("}}", open_at + 3)
        nested_at = text.find("${{", open_at + 3)
        if close_at < 0 or (0 <= nested_at < close_at):
            v.append("line %d: unclosed expression delimiter"
                     % (text.count("\n", 0, open_at) + 1))
            if close_at < 0:
                break
        scan = close_at + 2
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

    def test_duplicate_key_in_sequence_step(self):
        """A `- ` step mapping repeating a key it already set ON the dash line.

        YAML duplicate keys are silently last-wins, so the first `run:` never executes.
        The dash line is skipped wholesale by the duplicate pass, so the key it introduces
        is never recorded and the repeat inside the same mapping goes unseen.
        """
        self._assert_flagged(self.GOOD.replace(
            "      - name: x\n        run: echo ok\n",
            "      - run: echo ok\n        run: echo again\n"))

    def test_unclosed_expression_is_flagged(self):
        """A genuinely unterminated `${{` — no closing braces anywhere in the file.

        The pair regex only ever sees balanced `${{ ... }}` spans, so an expression that is
        never closed is invisible to it: the file lints clean while Actions rejects it.
        """
        broken = self.GOOD.replace("run: echo ok", "run: echo ${{ github.event.number")
        self.assertNotIn("}}", broken, "fixture must be genuinely unclosed")
        self._assert_flagged(broken)

    def test_bad_expression_root_is_flagged(self):
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

    @staticmethod
    def dated_model_id():
        """Assemble a dated model id at RUNTIME so no complete literal is committed (P9).

        A fixture that ships the whole id is itself a pinned model id in the tree; the
        predicate under test is the lint's, not the repository's willingness to store one.
        """
        return "-".join(["claude", "haiku", "4", "5", "2025" + "10" + "01"])

    def test_dated_model_pin(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", f"run: echo {self.dated_model_id()}"))

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

    # --- absence-of-required-structure. The suite previously only mutated VALUES, so a lint that
    # --- silently skipped anything it did not recognise passed all 26 cases while accepting a
    # --- workflow with no trigger and no declared permissions. These test absence directly.
    def test_unrecognised_top_level_text(self):
        self._assert_flagged(self.GOOD + "this is not yaml at all\n")

    def test_missing_on_block(self):
        self._assert_flagged(self.GOOD.replace("on:\n  workflow_dispatch:\n", ""))

    def test_missing_name(self):
        self._assert_flagged(self.GOOD.replace("name: t\n", "", 1))

    def test_missing_jobs(self):
        self._assert_flagged("name: t\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n")

    def test_no_permissions_anywhere(self):
        self._assert_flagged(self.GOOD.replace("permissions:\n  contents: read\n", ""))

    def test_job_level_permissions_satisfy_the_requirement(self):
        # Declaring per job is equally least-privilege; only silence is a violation.
        per_job = self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n")
        self.assertEqual(lint(per_job), [], "per-job permissions must satisfy the requirement")

    def test_unknown_secret(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ secrets.SNEAKY_TOKEN }}"))


DATED_MODEL_ID = re.compile(
    r"\b(?:claude|gpt|gemini)-[a-z0-9]+(?:[-.][a-z0-9]+)*-20[0-9]{6}\b")
PIN_FREE_TREES = ("tests", "auditor")


class TestNoCommittedModelIds(unittest.TestCase):
    """P9 at fixture level: a dated model id must be assembled at runtime, never committed.

    `tools/model-pin-lint.py` guards the shipped artifacts; nothing guards the test corpus,
    so a fixture that stores the complete id re-introduces exactly the pin the rule bans.
    Every legitimate use — lint mutations, model-pin-lint's own fixtures — can build the id
    from fragments at runtime and stays expressive.
    """

    def test_no_complete_model_id_in_tree(self):
        hits = []
        for tree in PIN_FREE_TREES:
            root = REPO / tree
            self.assertTrue(root.is_dir(), f"{root} missing")
            for path in sorted(root.rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                try:
                    text = path.read_text()
                except (UnicodeDecodeError, OSError):
                    continue
                for i, ln in enumerate(text.split("\n"), 1):
                    for m in DATED_MODEL_ID.finditer(ln):
                        hits.append(f"{path.relative_to(REPO)}:{i}: {m.group(0)}")
        self.assertEqual(
            hits, [],
            f"{len(hits)} complete dated model id literal(s) committed under "
            f"{'/, '.join(PIN_FREE_TREES)}/; assemble them at runtime instead:\n  "
            + "\n  ".join(hits))


if __name__ == "__main__":
    unittest.main()
