# SPDX-License-Identifier: ISC
"""T3 (vibe-59 / E8.2): effectful submit tests — real git, stubbed `gh`.

The submit job's shell is extracted from auditor/workflows/auditor-contribute.yml (the
`# logic:submit` ... `# /logic` block; where that marker does not yet exist the CURRENT submit
job's `run:` block is extracted instead, so every failure recorded here is behavioural — no push
happened, no ledger was written — never "the marker is missing").

The block runs against a disposable tree:

    root/target/            working checkout of the audited repo (HEAD is a LATER commit than
                            $AUDITED_SHA, so "checked out the audited SHA" is observable)
    root/fork.git           bare fork remote                     -> $FORK_REMOTE
    root/auditor-data.git   bare data remote (branch auditor-data) -> $DATA_REMOTE
    root/data/              working clone of the data remote     -> $DATA_DIR
    root/_patches/          patch artifact + CAP + findings.json -> $PATCH_DIR
    root/bin/gh             PATH-shimmed stub logging every call

Ordering is observable because the data remote's post-receive hook appends `data-push` to the
same log the `gh` stub writes to.
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
CONTRIBUTE = REPO / "auditor" / "workflows" / "auditor-contribute.yml"

FINGERPRINTS = ["a1b2c3d4e5f60718", "0f1e2d3c4b5a6978"]
BRANCH = "auditor/vibe-59-fix"
AUTHOR_NAME = "vibe-suite auditor"
AUTHOR_EMAIL = "auditor@example.invalid"
TARGET_REPO = "acme/claude-toolkit"

GH_STUB = """#!/usr/bin/env bash
echo "gh $*" >> "$GH_LOG"
i=1
while [ -e "$GH_CALLS/call-$i" ]; do i=$((i+1)); done
: > "$GH_CALLS/call-$i"
for a in "$@"; do printf '%s\\0' "$a" >> "$GH_CALLS/call-$i"; done
key="GH_CANNED_$(printf '%s_%s' "${1:-}" "${2:-}" | tr 'a-z-' 'A-Z_')"
val="${!key:-}"
if [ -n "$val" ] && [ -f "$val" ]; then cat "$val"; fi
# Path-shaped endpoints (gh api repos/<owner>/<name>) cannot form a legal variable name, so
# they come from a map file: "<prefix><TAB><file>" per line, longest prefix wins. Same
# addition as tests/test_auditor_state_machine.py's stub; a caller setting neither is unaffected.
if [ -z "$val" ] && [ -n "${GH_CANNED_MAP:-}" ] && [ -f "${GH_CANNED_MAP}" ]; then
  argv="$*"; best=""; bestlen=0
  while IFS="$(printf '\t')" read -r prefix file; do
    [ -z "$prefix" ] && continue
    case "$argv" in
      "$prefix"*) if [ "${#prefix}" -gt "$bestlen" ]; then best="$file"; bestlen="${#prefix}"; fi ;;
    esac
  done < "$GH_CANNED_MAP"
  if [ -n "$best" ] && [ -f "$best" ]; then cat "$best"; fi
fi
case " ${GH_FAIL:-} " in *" ${1:-}:${2:-} "*) exit 1 ;; esac
exit 0
"""

POST_RECEIVE = """#!/usr/bin/env bash
if [ -n "${GH_LOG:-}" ]; then echo "data-push" >> "$GH_LOG"; fi
exit 0
"""
PRE_RECEIVE_DENY = """#!/usr/bin/env bash
echo "auditor-data is unavailable (forced)" >&2
exit 1
"""

README_V1 = "# demo\n\nold line\n"
GOOD_PATCH = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,3 @@
 # demo

-old line
+new line
"""
CONFLICT_PATCH = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,3 +1,3 @@
 # demo

-a line that is not in this file
+new line
"""


def extract(path, marker, name):
    """Mirror of tests/test_auditor_state_machine.py's extractor."""
    m = re.search(rf"^(\s*)# {marker}:{re.escape(name)}\s*$(.*?)^\s*# /{marker}\s*$",
                  path.read_text(), re.M | re.S)
    if not m:
        return None
    indent, lines = None, []
    for ln in m.group(2).split("\n"):
        if ln.strip() and indent is None:
            indent = len(ln) - len(ln.lstrip(" "))
        lines.append(ln[indent:] if indent and ln.startswith(" " * indent) else ln)
    return "\n".join(lines)


def _job_lines(text, want):
    cur, body, in_jobs = None, [], False
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
            if cur == want:
                return body
            cur, body = m.group(1), []
        elif cur is not None:
            body.append(ln)
    return body if cur == want else []


def _run_blocks(body):
    out, i = [], 0
    while i < len(body):
        if re.match(r"^\s*-\s+run:\s*\|", body[i]):
            j, lines, indent = i + 1, [], None
            while j < len(body):
                ln = body[j]
                if not ln.strip():
                    lines.append("")
                    j += 1
                    continue
                cur = len(ln) - len(ln.lstrip(" "))
                if indent is None:
                    indent = cur
                if cur < indent:
                    break
                lines.append(ln[indent:])
                j += 1
            out.append("\n".join(lines))
            i = j
            continue
        i += 1
    return out


def submit_script():
    """The submit logic under test: the marked block if it exists, else today's submit job."""
    block = extract(CONTRIBUTE, "logic", "submit")
    if block is not None:
        return block
    return "\n".join(_run_blocks(_job_lines(CONTRIBUTE.read_text(), "submit")))


def git(*args, cwd, env=None, check=True):
    e = dict(os.environ)
    e.update(env or {})
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=e)
    if check and r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} in {cwd}: {r.stderr.strip()}")
    return r


class SubmitSandbox:
    def __init__(self, patch=GOOD_PATCH):
        self.root = Path(tempfile.mkdtemp(prefix="auditor-submit-"))
        self.gitenv = {
            "HOME": str(self.root),
            "GIT_CONFIG_GLOBAL": str(self.root / ".gitconfig"),
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_AUTHOR_NAME": "seed", "GIT_AUTHOR_EMAIL": "seed@example.invalid",
            "GIT_COMMITTER_NAME": "seed", "GIT_COMMITTER_EMAIL": "seed@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        }
        self.target = self.root / "target"
        self.target.mkdir()
        git("init", "-q", "-b", "main", ".", cwd=self.target, env=self.gitenv)
        (self.target / "README.md").write_text(README_V1)
        git("add", "README.md", cwd=self.target, env=self.gitenv)
        git("commit", "-q", "-m", "audited state", cwd=self.target, env=self.gitenv)
        self.audited_sha = git("rev-parse", "HEAD", cwd=self.target,
                               env=self.gitenv).stdout.strip()
        (self.target / "README.md").write_text(README_V1 + "extra\n")
        git("commit", "-q", "-am", "later drift", cwd=self.target, env=self.gitenv)
        self.head_sha = git("rev-parse", "HEAD", cwd=self.target, env=self.gitenv).stdout.strip()

        self.fork = self.root / "fork.git"
        git("clone", "-q", "--bare", str(self.target), str(self.fork), cwd=self.root,
            env=self.gitenv)

        self.data_remote = self.root / "auditor-data.git"
        git("init", "-q", "--bare", "-b", "auditor-data", str(self.data_remote), cwd=self.root,
            env=self.gitenv)
        seed = self.root / "_seed"
        seed.mkdir()
        git("init", "-q", "-b", "auditor-data", ".", cwd=seed, env=self.gitenv)
        for sub in ("registry", "ledgers", "audits", "reports"):
            (seed / sub).mkdir()
        (seed / "registry" / "repos.json").write_text(
            json.dumps({"repos": {TARGET_REPO: {"status": "audited"}}}, indent=2) + "\n")
        (seed / "ledgers" / "events.jsonl").write_text("")
        (seed / "ledgers" / "contact-reservations.jsonl").write_text("")
        git("add", "-A", cwd=seed, env=self.gitenv)
        git("commit", "-q", "-m", "seed", cwd=seed, env=self.gitenv)
        git("push", "-q", str(self.data_remote), "auditor-data", cwd=seed, env=self.gitenv)
        self.base_data_sha = git("rev-parse", "HEAD", cwd=seed, env=self.gitenv).stdout.strip()
        self._hook(self.data_remote, "post-receive", POST_RECEIVE)
        self.data = self.root / "data"
        git("clone", "-q", "-b", "auditor-data", str(self.data_remote), str(self.data),
            cwd=self.root, env=self.gitenv)

        self.patches = self.root / "_patches"
        self.patches.mkdir()
        (self.patches / "0001-fix.patch").write_text(patch)
        (self.patches / "CAP").write_text("3\n")
        (self.patches / "findings.json").write_text(json.dumps(
            [{"rule_id": "R7", "fingerprint": FINGERPRINTS[0]},
             {"rule_id": "R12", "fingerprint": FINGERPRINTS[1]}]) + "\n")

        self.bin = self.root / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(GH_STUB)
        gh.chmod(0o755)
        self.log = self.root / "gh.log"
        self.log.touch()
        self.calls = self.root / "gh-calls"
        self.calls.mkdir()
        self.canned = self.root / "canned"
        self.canned.mkdir()

    def _hook(self, bare, name, body):
        p = bare / "hooks" / name
        p.write_text(body)
        p.chmod(0o755)

    def block_data_pushes(self):
        self._hook(self.data_remote, "pre-receive", PRE_RECEIVE_DENY)

    def allow_data_pushes(self):
        (self.data_remote / "hooks" / "pre-receive").unlink(missing_ok=True)

    def can(self, key, payload):
        p = self.canned / key.lower()
        p.write_text(payload if isinstance(payload, str) else json.dumps(payload))
        return str(p)

    def reset_log(self):
        self.log.write_text("")
        shutil.rmtree(self.calls)
        self.calls.mkdir()

    def _write_pat_identity(self):
        """`gh api user --jq .login` for the PAT, matching FORK_SLUG's owner."""
        p = self.root / "canned-pat-user"
        p.write_text("vibe-suite-bot\n")
        return p

    def _write_fork_response(self):
        """The fork as the four-part invariant expects to find it.

        E8.2b (vibe-164) W5.2: submit now re-confirms after creation that the fork resolves,
        is a fork, is owned by the PAT login, and has the target as parent. Without a canned
        response these tests fail at `fork-invariant:resolves` -- correct behaviour meeting a
        harness that never modelled the fork's existence.
        """
        import json as _json
        slug = "vibe-suite-bot/claude-toolkit"
        body = self.root / "canned-fork-api"
        body.write_text(_json.dumps({
            "full_name": slug, "fork": True, "parent": {"full_name": TARGET_REPO}}))
        m = self.root / "canned-map"
        m.write_text("api repos/%s\t%s\n" % (slug, body))
        return m

    def _write_manifest(self):
        """The gate allowlist, admitting exactly the fingerprints these patches carry.

        E8.2b (vibe-164) W4.3: submit now refuses any patch fingerprint no gate admitted, and
        refuses outright when the manifest is absent -- failing open there would defeat the
        allowlist. This harness therefore has to supply one. It mirrors PATCH_META rather than
        inventing fingerprints, so these tests keep exercising submit's own behaviour instead
        of the allowlist check.
        """
        import json as _json
        meta = self.patches / "findings.json"
        fps = []
        if meta.is_file():
            try:
                fps = [f.get("fingerprint") for f in _json.loads(meta.read_text())
                       if f.get("fingerprint")]
            except Exception:
                fps = []
        p = self.root / "proposal-manifest.json"
        p.write_text(_json.dumps({
            "version": 1, "repo": TARGET_REPO,
            "findings": [{"rule_id": "R", "fingerprint": f, "file": "a.md",
                          "confidence": "high"} for f in fps]}))
        return p

    def _write_context(self):
        """The relay gates emits, as submit now consumes it.

        E8.2b (vibe-164): AUDITED_SHA, BASE_BRANCH and the author identity used to arrive as
        loose environment variables, which is a test supplying values the graph must derive --
        the exact injection the acceptance clause forbids, and what the W-scan flags. They now
        arrive the way production delivers them. CLA_AUTHOR_* stays: it is a documented CLA
        override with precedence over the derived identity, not an injected derivation.
        """
        p = self.root / "context.json"
        p.write_text(json.dumps({
            "version": 1, "repo": TARGET_REPO, "issue": "42",
            "expected_fork_slug": "vibe-suite-bot/claude-toolkit",
            "audited_sha": self.audited_sha, "base_branch": "main",
            "author_name": AUTHOR_NAME, "author_email": AUTHOR_EMAIL,
            "weekly_cap": 2, "patch_cap": 3}))
        return p

    def run(self, env=None):
        e = dict(os.environ)
        e.update(self.gitenv)
        e.update({
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "GH_LOG": str(self.log), "GH_CALLS": str(self.calls),
            "GH_TOKEN": "stub-pat", "GH_TOKEN_OVERRIDE": "stub-pat", "PAT_SECRET": "stub-pat",
            "REPO": TARGET_REPO, "OWNER": TARGET_REPO.split("/")[0],
            "ISSUE_NUMBER": "42", "ISSUE": "42",
            "HEAD_SHA": self.head_sha,
            "TARGET_DIR": str(self.target), "BRANCH": BRANCH,
            "FORK_REMOTE": str(self.fork), "FORK_SLUG": "vibe-suite-bot/claude-toolkit",
            "DATA_REMOTE": str(self.data_remote), "DATA_DIR": str(self.data),
            "DATA_BRANCH": "auditor-data",
            "REGISTRY": str(self.data / "registry" / "repos.json"),
            "EVENT_LOG": str(self.data / "ledgers" / "events.jsonl"),
            "PATCH_DIR": str(self.patches), "PATCH_META": str(self.patches / "findings.json"),
            "CLA_AUTHOR_NAME": AUTHOR_NAME, "CLA_AUTHOR_EMAIL": AUTHOR_EMAIL,
            "CONTEXT_FILE": str(self._write_context()),
            "MANIFEST": str(self._write_manifest()),
            "GH_CANNED_MAP": str(self._write_fork_response()),
            # F2: submit proves the PAT's own login matches the expected fork owner before
            # creating anything. The stub must model that identity call, or every test stops
            # at REFUSE:pat-identity-unresolvable -- correct behaviour meeting a harness that
            # never modelled it.
            "GH_CANNED_API_USER": str(self._write_pat_identity()),
        })
        e.update(env or {})
        sh = self.root / "submit.sh"
        sh.write_text(submit_script())
        return subprocess.run(["bash", str(sh)], capture_output=True, text=True, env=e,
                              cwd=str(self.root), timeout=180)

    # --- observations -------------------------------------------------------
    def log_lines(self):
        return self.log.read_text().splitlines()

    def gh_argvs(self):
        return [p.read_bytes().decode().split("\0")[:-1]
                for p in sorted(self.calls.glob("call-*"), key=lambda q: int(q.name[5:]))]

    def gh_verbs(self, *words):
        return [a for a in self.gh_argvs() if all(w in a for w in words)]

    def fork_log(self):
        r = git("log", "--oneline", BRANCH, cwd=self.fork, env=self.gitenv, check=False)
        return r.stdout if r.returncode == 0 else ""

    def data_files_written(self):
        r = git("log", "--name-only", "--format=", f"{self.base_data_sha}..auditor-data",
                cwd=self.data_remote, env=self.gitenv, check=False)
        return sorted({x for x in r.stdout.split() if x})

    def data_blob(self, path):
        r = git("show", f"auditor-data:{path}", cwd=self.data_remote, env=self.gitenv,
                check=False)
        return r.stdout if r.returncode == 0 else ""

    def local_ledger_text(self):
        out = []
        for p in (self.data / "ledgers").rglob("*.jsonl"):
            out.append(p.read_text())
        for p in self.root.rglob("outcome-*.json"):
            out.append(p.read_text())
        return "\n".join(out)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class SubmitEffects(unittest.TestCase):
    """One method per defect the round-2 review named; each asserts an observable git effect."""

    patch = GOOD_PATCH

    def setUp(self):
        self.sb = SubmitSandbox(patch=self.patch)
        self.addCleanup(self.sb.cleanup)

    def diag(self, r):
        return f"\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"

    def test_checkout_is_at_the_audited_sha(self):
        r = self.sb.run()
        head = git("rev-parse", "HEAD", cwd=self.sb.target, env=self.sb.gitenv,
                   check=False).stdout.strip()
        self.assertEqual(head, self.sb.audited_sha,
                         "submit never checked out the audited SHA — the target tree is still "
                         f"at {head[:12]} (later drift) instead of {self.sb.audited_sha[:12]}, "
                         "so any patch would be applied to unaudited content." + self.diag(r))

    def test_submission_branch_is_created(self):
        r = self.sb.run()
        rc = git("rev-parse", "--verify", BRANCH, cwd=self.sb.target, env=self.sb.gitenv,
                 check=False).returncode
        self.assertEqual(rc, 0,
                         f"submit created no '{BRANCH}' branch in the target checkout; there is "
                         "nothing to push or open a PR from." + self.diag(r))

    def test_patch_application_changes_file_content(self):
        r = self.sb.run()
        content = (self.sb.target / "README.md").read_text()
        self.assertIn("new line", content,
                      "submit never applied the patch — README.md still reads "
                      f"{content!r}; the PR would carry an empty diff." + self.diag(r))

    def test_commit_author_is_the_cla_identity(self):
        r = self.sb.run()
        out = git("log", "-1", "--format=%an%n%ae", BRANCH, cwd=self.sb.target,
                  env=self.sb.gitenv, check=False)
        got = out.stdout.strip().splitlines()
        self.assertEqual(got, [AUTHOR_NAME, AUTHOR_EMAIL],
                         "the submission commit does not carry the CLA identity from "
                         f"AUTHOR_NAME/AUTHOR_EMAIL; git reports {got or 'no commit at all'}."
                         + self.diag(r))

    def test_push_lands_in_the_bare_fork(self):
        r = self.sb.run()
        self.assertTrue(self.sb.fork_log().strip(),
                        f"nothing was pushed: the bare fork has no '{BRANCH}' ref, so the PR "
                        "would reference a branch that does not exist." + self.diag(r))

    def test_pr_body_ends_with_the_sentinel_metadata_block(self):
        self.sb.run(env={"GH_CANNED_PR_CREATE": self.sb.can(
            "gh_canned_pr_create", "https://github.com/acme/claude-toolkit/pull/7\n")})
        creates = self.sb.gh_verbs("pr", "create")
        self.assertTrue(creates, "submit made zero `gh pr create` calls, so there is no PR body "
                                 "to carry the sentinel metadata block")
        argv = creates[-1]
        self.assertIn("--body", argv, f"`gh pr create` was called without --body: {argv}")
        body = argv[argv.index("--body") + 1]
        tail = body.rstrip()
        self.assertTrue(tail.endswith("-->"),
                        "the metadata block is not the LAST element of the PR body (the tail "
                        f"position protects the closing sentinel); body ends with {tail[-80:]!r}")
        m = re.search(r"<!--(?:(?!<!--).)*$", tail, re.S)
        self.assertIsNotNone(m, "the PR body's tail is not a sentinel-bounded HTML comment")
        blob = re.search(r"\{.*\}", m.group(0), re.S)
        self.assertIsNotNone(blob, f"the trailing block carries no JSON object: {m.group(0)!r}")
        meta = json.loads(blob.group(0))
        self.assertEqual(meta.get("version"), 1, f"metadata version is {meta.get('version')!r}")
        got = sorted(f.get("fingerprint") for f in meta.get("findings", []))
        self.assertEqual(got, sorted(FINGERPRINTS),
                         "the metadata block does not carry the finding fingerprints "
                         f"(got {got}); recovery mode keys on exactly these")

    def test_full_success_persists_registry_and_event_before_labelling(self):
        self.sb.run(env={"GH_CANNED_PR_CREATE": self.sb.can(
            "gh_canned_pr_create", "https://github.com/acme/claude-toolkit/pull/7\n")})
        written = self.sb.data_files_written()
        self.assertIn("registry/repos.json", written,
                      f"the registry write never reached the bare auditor-data remote; the "
                      f"remote gained {written or 'nothing'} beyond the seed commit")
        self.assertIn("ledgers/events.jsonl", written,
                      f"the contribution_submitted event was never committed and pushed to the bare "
                      f"auditor-data remote; the remote gained {written or 'nothing'}")
        self.assertIn("contribution_submitted", self.sb.data_blob("ledgers/events.jsonl"),
                      "the pushed events ledger contains no contribution_submitted record")
        lines = self.sb.log_lines()
        pushes = [i for i, l in enumerate(lines) if l == "data-push"]
        labels = [i for i, l in enumerate(lines)
                  if "--add-label" in l and "prs-submitted" in l]
        self.assertTrue(labels, "the prs-submitted label was never applied after a successful "
                                "submission")
        self.assertTrue(pushes and pushes[0] < labels[0],
                        "the prs-submitted label was applied before the ledger push landed; the "
                        "durable record must precede every issue transition "
                        f"(log order: {lines})")

    def test_partial_persistence_applies_no_label_and_records_contribution_partial(self):
        self.sb.block_data_pushes()
        r = self.sb.run(env={"GH_CANNED_PR_CREATE": self.sb.can(
            "gh_canned_pr_create", "https://github.com/acme/claude-toolkit/pull/7\n")})
        joined = " ".join(self.sb.log_lines())
        self.assertNotIn("prs-submitted", joined,
                         "the ledger write failed yet the prs-submitted label was still "
                         "applied; the label is a derived view of a record that does not exist")
        trace = self.sb.local_ledger_text() + r.stdout + r.stderr
        self.assertIn("contribution_partial", trace,
                      "a partial submission (PR open, ledger write refused) recorded no "
                      "contribution_partial outcome, so the run is indistinguishable from a "
                      "clean failure and recovery has nothing to key on." + self.diag(r))

    def test_rerun_reconciles_the_sentinel_pr_without_opening_a_second_one(self):
        self.sb.block_data_pushes()
        canned_create = self.sb.can("gh_canned_pr_create",
                                    "https://github.com/acme/claude-toolkit/pull/7\n")
        self.sb.run(env={"GH_CANNED_PR_CREATE": canned_create})
        self.sb.allow_data_pushes()
        self.sb.reset_log()
        sentinel = json.dumps({"version": 1,
                               "findings": [{"rule_id": "R7", "fingerprint": FINGERPRINTS[0]},
                                            {"rule_id": "R12", "fingerprint": FINGERPRINTS[1]}]})
        pr_list = self.sb.can("gh_canned_pr_list", json.dumps([{
            "number": 7, "state": "OPEN", "headRefName": BRANCH,
            "author": {"login": "vibe-suite-bot"},
            "url": "https://github.com/acme/claude-toolkit/pull/7",
            "body": f"Bug / Evidence / Fix\n\n<!-- auditor-metadata {sentinel} -->",
        }]))
        r = self.sb.run(env={"GH_CANNED_PR_CREATE": canned_create,
                             "GH_CANNED_PR_LIST": pr_list,
                             "RECOVERY_MODE": "true"})
        self.assertEqual(self.sb.gh_verbs("pr", "create"), [],
                         "the rerun opened a SECOND pull request instead of reconciling the "
                         "existing sentinel PR #7 for the same fingerprints" + self.diag(r))
        written = self.sb.data_files_written()
        self.assertIn("ledgers/events.jsonl", written,
                      "the rerun did not reconcile: no ledger record reached the bare "
                      f"auditor-data remote (it gained {written or 'nothing'})" + self.diag(r))
        self.assertIn("contribution_submitted", self.sb.data_blob("ledgers/events.jsonl"),
                      "the reconciling rerun wrote no contribution_submitted record for the recovered PR")
        self.assertTrue(any("--add-label" in l and "prs-submitted" in l
                            for l in self.sb.log_lines()),
                        "the reconciling rerun never applied the prs-submitted label, so the "
                        "issue stays stuck after recovery" + self.diag(r))


class SubmitConflict(unittest.TestCase):
    """The patch-conflict row of the outcome table."""

    def setUp(self):
        self.sb = SubmitSandbox(patch=CONFLICT_PATCH)
        self.addCleanup(self.sb.cleanup)

    def test_unappliable_patch_opens_no_pr_and_reports_conflict(self):
        r = self.sb.run(env={"GH_CANNED_PR_CREATE": self.sb.can(
            "gh_canned_pr_create", "https://github.com/acme/claude-toolkit/pull/7\n")})
        self.assertEqual(self.sb.gh_verbs("pr", "create"), [],
                         "a patch that does not apply still produced a `gh pr create` call")
        self.assertEqual(self.sb.fork_log().strip(), "",
                         "a patch that does not apply still pushed a branch to the fork")
        trace = self.sb.local_ledger_text() + r.stdout + r.stderr
        self.assertTrue(re.search(r"conflict", trace, re.I),
                        "a patch that does not apply produced no conflict outcome at all — the "
                        "run is silent, so finalize cannot select the patch-conflict row."
                        + self.diag_text(r))

    def diag_text(self, r):
        return f"\n--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"


if __name__ == "__main__":
    unittest.main()
