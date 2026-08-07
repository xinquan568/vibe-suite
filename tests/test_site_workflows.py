#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""T0 (E8.4 / vibe-61) — static contracts over the five site/release workflows.

These are the contracts a VitePress build cannot check: which events fire a workflow, what
each job is permitted to do, that the Pages deployment rides OIDC rather than a stored secret
(rule 6), and that **every** build path goes through the single entry point `site/build.sh`
(I2b) rather than invoking VitePress directly — a clean checkout has no `site/data/` or
`site/reports/` (D-D), so a path that bypasses the orchestrator builds a hollow site.

Stdlib only, so the YAML is read as raw indented text (no PyYAML in this project). The
parser below understands exactly the block/flow forms these workflows use.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

#: workflow file -> the EXACT trigger set. Exact, not "at least": an extra trigger on a
#: deploying workflow is a new way to publish, and must be a reviewed edit.
EXPECTED_TRIGGERS = {
    "deploy-site.yml": {"push", "workflow_dispatch"},
    "site-preview.yml": {"pull_request"},
    "site-preview-cleanup.yml": {"pull_request"},
    "site-validate.yml": {"pull_request"},
    "self-check.yml": {"schedule", "workflow_dispatch"},
}

#: The workflows that build the site, and therefore must invoke the orchestrator.
BUILD_PATHS = ("deploy-site.yml", "site-preview.yml", "site-validate.yml")


def _significant(text):
    return [ln for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _indent(line):
    return len(line) - len(line.lstrip())


def _key_of(line):
    head = line.strip().split(":", 1)[0].strip()
    return head.strip("\"'")


def block_body(lines, key, indent=0):
    """The lines strictly more indented than `indent` that follow `<indent>key:`."""
    body, collecting = [], False
    for ln in lines:
        cur = _indent(ln)
        if not collecting:
            if cur == indent and ":" in ln and _key_of(ln) == key:
                collecting = True
            continue
        if cur <= indent:
            break
        body.append(ln)
    return body


def keys_at_top(body):
    """The mapping keys at the outermost indent of a block body."""
    if not body:
        return set()
    base = min(_indent(ln) for ln in body)
    return {_key_of(ln) for ln in body
            if _indent(ln) == base and ":" in ln and not ln.strip().startswith("-")}


def load(name):
    path = WORKFLOWS / name
    if not path.is_file():
        raise AssertionError(f".github/workflows/{name} does not exist")
    return path.read_text(encoding="utf-8")


def triggers(text):
    lines = _significant(text)
    for ln in lines:
        if _indent(ln) or ":" not in ln or _key_of(ln) != "on":
            continue
        rest = ln.split(":", 1)[1].strip()
        if rest:  # flow form: on: [push, workflow_dispatch]
            return {t.strip().strip("\"'") for t in rest.strip("[]").split(",") if t.strip()}
        return keys_at_top(block_body(lines, "on"))
    return set()


def jobs(text):
    """job id -> the raw text of that job's body."""
    body = block_body(_significant(text), "jobs")
    if not body:
        return {}
    base = min(_indent(ln) for ln in body)
    out, current = {}, None
    for ln in body:
        if _indent(ln) == base and ":" in ln and not ln.strip().startswith("-"):
            current = _key_of(ln)
            out[current] = []
        elif current is not None:
            out[current].append(ln)
    return {k: "\n".join(v) for k, v in out.items()}


class WorkflowsExist(unittest.TestCase):
    def test_all_five_are_present(self):
        for name in EXPECTED_TRIGGERS:
            with self.subTest(workflow=name):
                self.assertTrue((WORKFLOWS / name).is_file(),
                                f".github/workflows/{name} is missing")

    def test_each_declares_a_name(self):
        for name in EXPECTED_TRIGGERS:
            with self.subTest(workflow=name):
                self.assertRegex(load(name), r"(?m)^name:\s*\S")


class Triggers(unittest.TestCase):
    def test_exact_trigger_sets(self):
        for name, expected in EXPECTED_TRIGGERS.items():
            with self.subTest(workflow=name):
                self.assertEqual(triggers(load(name)), expected,
                                 f"{name}: trigger set must be exactly {sorted(expected)}")

    def test_deploy_site_pushes_only_from_main(self):
        push = block_body(block_body(_significant(load("deploy-site.yml")), "on"),
                          "push", indent=2)
        self.assertTrue(push, "deploy-site: push trigger declares no branch filter, so any "
                              "branch would publish to Pages")
        self.assertIn("main", "\n".join(push),
                      "deploy-site: push must be filtered to the main branch")

    def test_preview_cleanup_fires_on_closed(self):
        pr = block_body(block_body(_significant(load("site-preview-cleanup.yml")), "on"),
                        "pull_request", indent=2)
        self.assertIn("closed", "\n".join(pr),
                      "site-preview-cleanup must declare types: [closed]; without it the "
                      "cleanup runs on every PR event and tears down live previews")


class LeastPrivilege(unittest.TestCase):
    def test_every_job_declares_permissions(self):
        for name in EXPECTED_TRIGGERS:
            for job_id, body in jobs(load(name)).items():
                with self.subTest(workflow=name, job=job_id):
                    self.assertRegex(
                        body, r"(?m)^\s+permissions:",
                        f"{name}: job '{job_id}' declares no permissions block, so it "
                        f"inherits the repository default token scope")

    def test_no_workflow_grants_blanket_write_all(self):
        for name in EXPECTED_TRIGGERS:
            with self.subTest(workflow=name):
                self.assertNotIn("permissions: write-all", load(name))


class PagesDeployment(unittest.TestCase):
    """Rule 6: the Pages deployment rides Pages/OIDC scopes, never a stored secret."""

    def _deploy_job(self):
        found = {jid: body for jid, body in jobs(load("deploy-site.yml")).items()
                 if "pages" in body.lower()}
        self.assertTrue(found, "deploy-site declares no job that touches Pages")
        return found

    def test_deploy_job_carries_pages_write_and_id_token_write(self):
        for jid, body in self._deploy_job().items():
            with self.subTest(job=jid):
                self.assertRegex(body, r"pages:\s*write",
                                 f"deploy-site job '{jid}' lacks pages: write")
                self.assertRegex(body, r"id-token:\s*write",
                                 f"deploy-site job '{jid}' lacks id-token: write, so the "
                                 f"deployment cannot use OIDC")

    def test_deploy_site_references_no_stored_secret(self):
        text = load("deploy-site.yml")
        hits = re.findall(r"secrets\.[A-Za-z_][A-Za-z0-9_]*", text)
        self.assertEqual(hits, [],
                         f"deploy-site references stored secret(s) {hits}; the Pages "
                         f"deployment must authenticate via id-token/OIDC instead")


class SingleEntryPoint(unittest.TestCase):
    def test_every_build_path_invokes_the_orchestrator(self):
        for name in BUILD_PATHS:
            with self.subTest(workflow=name):
                self.assertIn("site/build.sh", load(name),
                              f"{name} builds the site without site/build.sh; a clean "
                              f"checkout has no site/data or site/reports (D-D), so this "
                              f"path would publish a hollow site")

    def test_no_workflow_invokes_vitepress_directly(self):
        for name in EXPECTED_TRIGGERS:
            with self.subTest(workflow=name):
                text = load(name)
                self.assertNotIn("npm run build", text,
                                 f"{name} invokes npm run build directly, bypassing the "
                                 f"orchestrator (I2b)")
                self.assertNotRegex(text, r"npx\s+vitepress\s+build",
                                    f"{name} invokes vitepress directly")

    def test_site_validate_runs_the_brand_check_over_the_built_output(self):
        text = load("site-validate.yml")
        self.assertIn("tools/site-brand-check.sh", text,
                      "site-validate must run the brand check (D-A) over the build output")


class SelfCheck(unittest.TestCase):
    def test_invokes_the_badge_and_check_tools(self):
        text = load("self-check.yml")
        for tool in ("bin/vibe-badge", "bin/vibe-check"):
            with self.subTest(tool=tool):
                self.assertIn(tool, text, f"self-check does not invoke {tool}")


if __name__ == "__main__":
    unittest.main()
