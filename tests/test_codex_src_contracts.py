#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""E7.1 (vibe-53): behavioral contracts of the seven reverse-delegation skill sources.

The sources are re-implemented at functional parity with cc-suite's originals (D7: consult,
never copy), so the contract each original defines — call flow, permission mechanism, argument
tables, verdict vocabularies, session handling — is frozen here as a table a test walks. An
artifact that reads plausibly but drops a leg of its original's contract fails this battery.

Two structural rules come from the served schema (`tests/fixtures/
claude-octopus-tools-1.2.0.json`, captured live from claude-octopus@1.2.0):

* every tool a call form names, and every argument key it passes, must exist in the schema,
  with each tool's `required` arguments present;
* `claude_code_reply` exposes no `permissionMode` argument, so a reply call form carrying one
  is a contract error, not a stylistic choice.

`permissionMode: plan` is the originals' read-only mechanism and is required on the initial
review/plan/audit dispatches and verify's fresh Option B — and must be absent from
claude-implement and claude-debug, whose originals grant write access.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "codex-src"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "claude-octopus-tools-1.2.0.json"

SERVER = "vibe-claude-mcp"
RETIRED_PREFIX = "mcp__claude-code__"

#: skill → (plan_required, plan_forbidden, required_substrings)
CONTRACTS = {
    "claude-review": dict(
        plan_required=True, plan_forbidden=False,
        substrings=[
            f"mcp__{SERVER}__claude_code:",
            f"mcp__{SERVER}__claude_code_reply:",
            "{review_session_id}",
            "Correctness", "Security", "Quality", "Architecture",
            "File:line", "Critical / High / Medium / Low",
            "Suggested fix", "recommended action",
            "PROVENANCE NOTE",
        ]),
    "claude-plan": dict(
        plan_required=True, plan_forbidden=False,
        substrings=[
            f"mcp__{SERVER}__claude_code:",
            f"mcp__{SERVER}__claude_code_reply:",
            "{plan_session_id}",
            "Do NOT write any code",
            "risk areas", "open questions", "test scenarios",
            "PROVENANCE NOTE",
        ]),
    "claude-implement": dict(
        plan_required=False, plan_forbidden=True,
        substrings=[
            f"mcp__{SERVER}__claude_code:",
            f"mcp__{SERVER}__claude_code_reply:",
            "{impl_session_id}",
            "Files changed", "Test results", "deferred",
            "maxBudgetUsd",
            "PROVENANCE NOTE",
        ]),
    "claude-debug": dict(
        plan_required=False, plan_forbidden=True,
        substrings=[
            f"mcp__{SERVER}__claude_code:",
            f"mcp__{SERVER}__claude_code_reply:",
            "{debug_session_id}",
            "SYMPTOM", "ERROR OUTPUT", "REPRODUCTION STEPS", "WHAT I TRIED",
            "root cause", "regressions",
            "PROVENANCE NOTE",
        ]),
    "audit": dict(
        plan_required=True, plan_forbidden=False,
        substrings=[
            f"mcp__{SERVER}__claude_code:",
            f"mcp__{SERVER}__claude_code_reply:",
            "{audit_session_id}",
            "Logic errors", "Code duplication", "Dead code",
            "Refactoring opportunities", "Shortcuts and tech debt",
            "Security", "Performance", "Compliance and documentation",
            "Dependencies",
            "--full", "--mini", "CLEAN",
            "PROVENANCE NOTE",
        ]),
    "audit-fix": dict(
        plan_required=True, plan_forbidden=False,
        substrings=[
            f"mcp__{SERVER}__claude_code:",
            f"mcp__{SERVER}__claude_code_reply:",
            "{cycle_session_id}",
            "--full", "--mini", "--rounds", "--severity", "--ask",
            "Critical+High (full) or High-only (mini)",
            "Fix all", "Stop here",
            "FIXED", "NOT FIXED", "PARTIAL", "REGRESSED",
            "git diff --stat",
            "PROVENANCE NOTE",
        ]),
    "verify": dict(
        plan_required=True, plan_forbidden=False,
        substrings=[
            f"mcp__{SERVER}__claude_code:",
            f"mcp__{SERVER}__claude_code_reply:",
            "{verify_session_id}",
            "Option A", "Option B",
            "FIXED", "NOT FIXED", "PARTIAL", "REGRESSED",
            "PROVENANCE NOTE",
        ]),
}

#: Cells of the audit-fix argument table that must survive verbatim (defaults are contract).
AUDIT_FIX_TABLE_ROWS = [
    re.compile(r"--rounds[^|\n]*\|\s*3\s*\|"),
    re.compile(r"--severity=all\\?\|high[^|\n]*\|\s*`?all`?\s*\|"),
    re.compile(r"file/dir path[^|\n]*\|\s*cwd\s*\|"),
]


def load_schema():
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {t["name"]: t for t in doc["tools"]}


def body(name):
    return (SRC / name / "SKILL.md").read_text(encoding="utf-8")


def fenced_blocks(text):
    return re.findall(r"^```[a-z]*\n(.*?)^```", text, re.M | re.S)


def call_blocks(text):
    """Fenced blocks that open with an mcp tool invocation line."""
    out = []
    for block in fenced_blocks(text):
        m = re.match(r"^mcp__([a-z-]+)__([a-z_]+):", block)
        if m:
            out.append((m.group(1), m.group(2), block))
    return out


def top_level_args(block):
    """Argument keys at two-space indentation directly under the tool line."""
    return re.findall(r"^  ([a-zA-Z_]+):", block, re.M)


class ContractTable(unittest.TestCase):
    def test_required_substrings(self):
        for name, contract in CONTRACTS.items():
            text = body(name)
            for token in contract["substrings"]:
                with self.subTest(skill=name, token=token):
                    self.assertIn(token, text)

    def test_permission_mode_per_row(self):
        for name, contract in CONTRACTS.items():
            text = body(name)
            with self.subTest(skill=name):
                if contract["plan_required"]:
                    self.assertIn("permissionMode: plan", text)
                if contract["plan_forbidden"]:
                    self.assertNotIn("permissionMode: plan", text)

    def test_reply_blocks_carry_no_permission_mode(self):
        for name in CONTRACTS:
            for server, tool, block in call_blocks(body(name)):
                if tool == "claude_code_reply":
                    with self.subTest(skill=name):
                        self.assertNotIn("permissionMode", block)

    def test_call_blocks_match_served_schema(self):
        schema = load_schema()
        for name in CONTRACTS:
            blocks = call_blocks(body(name))
            self.assertTrue(blocks, f"{name}: no call blocks found")
            for server, tool, block in blocks:
                with self.subTest(skill=name, tool=tool):
                    self.assertEqual(server, SERVER)
                    self.assertIn(tool, schema)
                    props = set(schema[tool]["inputSchema"]["properties"])
                    args = top_level_args(block)
                    self.assertTrue(args, f"{name}/{tool}: no arguments parsed")
                    for arg in args:
                        self.assertIn(arg, props, f"{name}/{tool}: unserved arg {arg!r}")
                    for required in schema[tool]["inputSchema"].get("required") or []:
                        self.assertIn(required, args,
                                      f"{name}/{tool}: missing required arg {required!r}")

    def test_model_is_never_assigned(self):
        for name in CONTRACTS:
            for _, tool, block in call_blocks(body(name)):
                with self.subTest(skill=name, tool=tool):
                    self.assertNotRegex(block, re.compile(r"^\s*model:", re.M))

    def test_retired_server_prefix_absent(self):
        for name in CONTRACTS:
            with self.subTest(skill=name):
                self.assertNotIn(RETIRED_PREFIX, body(name))

    def test_claude_code_dispatches_carry_cwd_and_high_effort(self):
        for name in CONTRACTS:
            for _, tool, block in call_blocks(body(name)):
                if tool == "claude_code":
                    with self.subTest(skill=name):
                        self.assertIn("cwd:", block)
                        self.assertIn("effort: high", block)

    def test_audit_fix_argument_defaults(self):
        text = body("audit-fix")
        for pattern in AUDIT_FIX_TABLE_ROWS:
            with self.subTest(pattern=pattern.pattern):
                self.assertRegex(text, pattern)

    def test_audit_fix_actor_boundary(self):
        text = body("audit-fix")
        self.assertIn("Codex", text)
        squashed = re.sub(r"\s+", " ", text)
        self.assertRegex(
            squashed,
            re.compile(r"Claude audits.*Codex (?:fixes|applies).*Claude verifies", re.I))

    def test_verify_option_b_saves_session(self):
        text = body("verify")
        b_idx = text.index("Option B")
        self.assertIn("{verify_session_id}", text[b_idx:])


if __name__ == "__main__":
    unittest.main()
