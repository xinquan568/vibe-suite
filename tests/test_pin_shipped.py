#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""E7.1 (vibe-53): shipped pin-state invariants and the codex-src source set.

Every prior pin test drives `resolve_pin` through temp files, which is right for contract
coverage and useless for the one question E7.1 answers: what state does the tree itself ship?
These tests run against the real repository files, so the pending→shipped flip is an asserted
fact rather than a side effect nothing checks. The advisor default matters for the same reason:
shipping the pin is what activates zero-flag advisor registration (`resolve_backend(None)`),
and only a real-tree assertion notices if the two files ever disagree.

The codex-src assertions pin the source set's mechanical shape (presence, frontmatter, no
versioned model ids). The per-skill behavioral contracts live in
`tests/test_codex_src_contracts.py`.
"""

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))

import advisors  # noqa: E402
import mcp_pin  # noqa: E402

SEVEN = [
    "claude-review", "claude-plan", "claude-implement", "claude-debug",
    "audit", "audit-fix", "verify",
]
SRC = REPO_ROOT / "codex-src"

#: AC-9's four id families, plus the dated-claude form. codex-src ships to another agent's
#: runtime, so a pinned id there is exactly the defect P9 names. `tools/model-pin-lint.py`
#: remains the single production authority; this guard exists so the RED battery fails locally
#: before the lint ever runs in CI.
MODEL_ID_PATTERNS = [
    re.compile(r"claude-[a-z]+-[0-9]"),
    re.compile(r"claude-[a-z0-9-]*-20[0-9]{2}"),
    re.compile(r"gpt-[0-9]"),
    re.compile(r"gemini-[0-9]"),
    re.compile(r"\bo[0-9]-"),
]


def frontmatter(text):
    lines = text.split("\n")
    assert lines[0] == "---", "missing frontmatter fence"
    keys = {}
    for line in lines[1:]:
        if line == "---":
            return keys
        m = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if m:
            keys[m.group(1)] = m.group(2).strip()
    raise AssertionError("unterminated frontmatter")


class ShippedPinState(unittest.TestCase):
    """The tree's own pin state, through the production default paths."""

    def test_real_tree_resolves_shipped_exact(self):
        state, value = mcp_pin.resolve_pin()
        self.assertEqual(state, "shipped")
        self.assertRegex(value, mcp_pin._EXACT)

    def test_pending_marker_is_gone(self):
        self.assertFalse(
            mcp_pin.PENDING_FILE.exists(),
            "claude-octopus-pin.pending still present — E7.1 owns its deletion")

    def test_advisor_zero_flag_default_is_the_shipped_pin(self):
        pin = mcp_pin.PIN_FILE.read_text(encoding="utf-8").strip()
        self.assertEqual(advisors.resolve_backend(None), f"claude-octopus@{pin}")


class CodexSrcSourceSet(unittest.TestCase):
    """Mechanical shape of F9.6 source set (d)."""

    def test_readme_states_the_generator_contract(self):
        text = (SRC / "README.md").read_text(encoding="utf-8")
        self.assertIn("E7.2", text)
        self.assertIn("codex/", text)

    def test_seven_sources_present(self):
        for name in SEVEN:
            with self.subTest(skill=name):
                self.assertTrue((SRC / name / "SKILL.md").is_file(), name)

    def test_frontmatter_name_matches_directory(self):
        for name in SEVEN:
            with self.subTest(skill=name):
                fm = frontmatter((SRC / name / "SKILL.md").read_text(encoding="utf-8"))
                self.assertEqual(fm.get("name"), name)
                self.assertTrue(fm.get("description"), f"{name}: empty description")

    def test_no_versioned_model_id_anywhere_in_codex_src(self):
        for path in sorted(SRC.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in MODEL_ID_PATTERNS:
                self.assertIsNone(
                    pattern.search(text),
                    f"{path.relative_to(REPO_ROOT)}: matches {pattern.pattern}")


if __name__ == "__main__":
    unittest.main()
