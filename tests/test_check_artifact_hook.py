# SPDX-License-Identifier: ISC
"""E3.9 (vibe-34) acceptance: the PostToolUse advisory hook.

Unlike the scanner, this deliverable is fully mechanical — classification, exit code,
streams and runtime are all directly executable — so the acceptance clause "the hook never
blocks and stays under timeout" is tested by running the script, not by asserting prose.

Two tables drive everything: IO_CASES (8 rows) and CLASSIFICATION (24 rows). The
classification table is the plan's derived boundary between the source's eight kept patterns
and F9.3's A/B/F categories; the two sets OVERLAP, neither contains the other, and exactness
is claimed only over these representatives.
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "scripts" / "check-artifact.sh"
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"

#: F9.7 fixes the timeout at 5 s; the script must finish well inside it.
TIMEOUT_S = 5

#: (label, path, should_match, category). One representative per F9.3 A/B/F pattern class,
#: plus C and E controls and the source-only nested case.
CLASSIFICATION = [
    ("plugin manifest", "/r/.claude-plugin/plugin.json", True, "A"),
    ("command", "/r/commands/x.md", True, "A"),
    ("shared partial", "/r/commands/shared/x.md", True, "A"),
    ("agent", "/r/agents/a.md", True, "A"),
    ("skill", "/r/skills/s/SKILL.md", True, "A"),
    ("hooks registration", "/r/hooks/hooks.json", True, "A"),
    ("mcp config", "/r/.mcp.json", True, "A"),
    ("root CLAUDE.md", "/r/CLAUDE.md", True, "B"),
    ("config-dir CLAUDE.md", "/r/.claude/CLAUDE.md", True, "B"),
    ("nested CLAUDE.md", "/r/pkg/CLAUDE.md", True, "B"),
    ("rule file", "/r/.claude/rules/r.md", True, "B"),
    ("user-level command", "/r/.claude/commands/u.md", True, "B"),
    # `*` spans `/` in shell case patterns, so the source reaches trees a root-anchored
    # discovery would skip. Kept deliberately; asserted so it cannot regress silently.
    ("vendored command", "/r/vendor/thirdparty/commands/x.md", True, "source-only"),
    # Inside F9.3's A/B/F but omitted by the source — recorded decisions, not oversights.
    ("marketplace entry", "/r/.claude-plugin/marketplace.json", False, "A"),
    ("lsp config", "/r/.lsp.json", False, "A"),
    ("root settings", "/r/settings.json", False, "A"),
    ("project settings", "/r/.claude/settings.json", False, "B"),
    ("local settings", "/r/.claude/settings.local.json", False, "B"),
    ("local plugin config", "/r/.claude/x.local.md", False, "B"),
    ("memory file", "/home/u/.claude/projects/p/memory/topic.md", False, "F"),
    ("memory index", "/home/u/.claude/projects/p/memory/MEMORY.md", False, "F"),
    # Controls: an edit-time advisory is scoped to A/B, not to prompts or design docs.
    ("prompt template", "/r/prompts/x.md", False, "C"),
    ("design doc", "/r/docs/x.md", False, "E"),
    ("readme", "/r/README.md", False, "E"),
]

#: (label, stdin, jq_available, expect_reminder)
IO_CASES = [
    ("valid json, artifact", json.dumps({"tool_input": {"file_path": "/r/commands/x.md"}}),
     True, True),
    ("valid json, non-artifact", json.dumps({"tool_input": {"file_path": "/r/docs/x.md"}}),
     True, False),
    ("valid json, no file_path", json.dumps({"tool_input": {}}), True, False),
    ("malformed json", "{not json", True, False),
    ("valid json, artifact, no jq",
     json.dumps({"tool_input": {"file_path": "/r/commands/x.md"}}), False, True),
    # The lexical fallback extracts from text jq would reject. Preserved source behaviour,
    # and safe for an advisory hook: the worst case is a reminder nobody needed.
    ("malformed text with a file_path, no jq",
     'garbage "file_path": "/r/commands/x.md" more garbage', False, True),
    ("empty stdin", "", True, False),
]


def run_hook(stdin_text, jq_available=True, strip_fallback_utils=False):
    """Run the hook, optionally hiding jq and/or the fallback utilities from PATH."""
    env = dict(os.environ)
    if not jq_available or strip_fallback_utils:
        shim = Path(os.environ["PYTEST_SHIM_DIR"]) if "PYTEST_SHIM_DIR" in os.environ else None
        assert shim is not None
        env["PATH"] = str(shim)
    started = time.monotonic()
    proc = subprocess.run([str(HOOK)], input=stdin_text, capture_output=True, text=True,
                          timeout=TIMEOUT_S, env=env)
    return proc, time.monotonic() - started


class HookRegistration(unittest.TestCase):
    def test_script_exists_and_is_executable(self):
        # hooks.json invokes the script directly, so the mode is part of the contract
        self.assertTrue(HOOK.is_file(), "scripts/check-artifact.sh is missing")
        self.assertTrue(HOOK.stat().st_mode & stat.S_IXUSR, "hook script is not executable")

    def test_spdx_header_in_first_three_lines(self):
        head = HOOK.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in line for line in head),
                        f"scripts/README.md requires an ISC SPDX header; got {head}")

    def test_registration_matcher_command_and_timeout(self):
        entry = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]["PostToolUse"]
        self.assertEqual(len(entry), 1)
        # F9.7 fixes this matcher verbatim. conventions-claude records MultiEdit as removed;
        # an alternation branch that never matches is inert, and dropping it would deviate
        # from the governing spec.
        self.assertEqual(entry[0]["matcher"], "Write|Edit|MultiEdit")
        handlers = entry[0]["hooks"]
        self.assertEqual(len(handlers), 1)
        self.assertEqual(handlers[0]["type"], "command")
        self.assertIn("check-artifact.sh", handlers[0]["command"])
        self.assertEqual(handlers[0]["timeout"], 5)


class HookIO(unittest.TestCase):
    """Exit 0 on every path, never a byte on stdout, at most one line on stderr."""

    @classmethod
    def setUpClass(cls):
        # a PATH containing only the interpreters the script needs, so `command -v jq`
        # fails and the fallback runs
        cls.tmp = Path(__file__).resolve().parent / ".hookshim"
        cls.tmp.mkdir(exist_ok=True)
        for util in ("bash", "cat", "echo", "grep", "head", "sed"):
            src = shutil.which(util)
            if src:
                link = cls.tmp / util
                if not link.exists():
                    link.symlink_to(src)
        os.environ["PYTEST_SHIM_DIR"] = str(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        os.environ.pop("PYTEST_SHIM_DIR", None)

    def test_io_matrix(self):
        for label, stdin_text, jq, expect_reminder in IO_CASES:
            with self.subTest(case=label):
                proc, _ = run_hook(stdin_text, jq_available=jq)
                # vibe-203: the advisory now exits 1 (a non-2, non-zero exit) so the harness SHOWS the
                # stderr line to the operator; a silent run still exits 0. Non-2 never BLOCKS the tool.
                self.assertEqual(proc.returncode, 1 if expect_reminder else 0,
                                 f"{label}: advisory -> exit 1 (non-blocking, shown); silence -> exit 0")
                self.assertNotEqual(proc.returncode, 2, f"{label}: must never BLOCK (exit 2)")
                self.assertEqual(proc.stdout, "", f"{label}: stdout must stay empty")
                if expect_reminder:
                    # the EXACT line, not a substring: changing the fallback branch's
                    # message to a different one-line string containing the same substring
                    # previously passed every row
                    path = "/r/commands/x.md"
                    self.assertEqual(
                        proc.stderr,
                        f"NL artifact edited: x.md. Run /vibe-suite:score {path} "
                        "to check quality.\n",
                        f"{label}: reminder must be byte-identical across branches")
                else:
                    self.assertEqual(proc.stderr, "", f"{label}: expected silence")

    def test_no_diagnostics_when_fallback_utilities_are_missing(self):
        # the source suppressed jq's errors but not grep/head/sed's; a diagnostic on stderr
        # would be indistinguishable from the advisory line
        empty = Path(__file__).resolve().parent / ".emptyshim"
        empty.mkdir(exist_ok=True)
        for util in ("bash", "cat", "echo"):
            src = shutil.which(util)
            if src and not (empty / util).exists():
                (empty / util).symlink_to(src)
        try:
            env = dict(os.environ, PATH=str(empty))
            proc = subprocess.run(
                [str(HOOK)],
                input=json.dumps({"tool_input": {"file_path": "/r/commands/x.md"}}),
                capture_output=True, text=True, timeout=TIMEOUT_S, env=env)
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(proc.stdout, "")
            # with no extractor available no path can be found, so the correct result is
            # silence — asserting only "no diagnostic" would accept a spurious reminder
            self.assertEqual(proc.stderr, "")
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_stays_well_inside_the_timeout(self):
        _, elapsed = run_hook(
            json.dumps({"tool_input": {"file_path": "/r/commands/x.md"}}))
        self.assertLess(elapsed, TIMEOUT_S,
                        "the hook must finish inside its 5 s budget")


class HookClassification(unittest.TestCase):
    """The 24-row boundary, executed. Sealing the worksheet proves its text did not
    change; only running the script proves the patterns behave."""

    def test_every_row(self):
        for label, path, should_match, category in CLASSIFICATION:
            with self.subTest(case=label, category=category):
                proc, _ = run_hook(json.dumps({"tool_input": {"file_path": path}}))
                self.assertEqual(proc.returncode, 1 if should_match else 0)  # vibe-203: advisory -> exit 1
                self.assertEqual(proc.stdout, "")
                got = "Run /vibe-suite:score" in proc.stderr
                self.assertEqual(
                    got, should_match,
                    f"{label} ({path}) should {'match' if should_match else 'not match'}")

    def test_matrix_shape(self):
        # the counts the plan froze; a row added or removed without updating the split is
        # a silent change to the boundary this item deliberately chose
        matched = [row for row in CLASSIFICATION if row[2]]
        self.assertEqual(len(CLASSIFICATION), 24)
        self.assertEqual(len(matched), 13)
        self.assertEqual(len(CLASSIFICATION) - len(matched), 11)

    #: Two independent witnesses per source pattern. A single representative lets a
    #: pattern be narrowed to exactly that path — `*/skills/*/SKILL.md` shrunk to
    #: `*/skills/s/SKILL.md` passed every earlier test while breaking real trees.
    WITNESSES = [
        ("*/commands/*.md", ["/r/commands/one.md", "/other/commands/two.md"]),
        ("*/agents/*.md", ["/r/agents/alpha.md", "/other/agents/beta.md"]),
        ("*/skills/*/SKILL.md", ["/r/skills/alpha/SKILL.md", "/other/skills/beta/SKILL.md"]),
        ("*/.claude/rules/*.md", ["/r/.claude/rules/one.md", "/o/.claude/rules/two.md"]),
        ("*/hooks/*.json", ["/r/hooks/hooks.json", "/other/hooks/extra.json"]),
        ("*/CLAUDE.md", ["/r/CLAUDE.md", "/other/deep/CLAUDE.md"]),
        ("*/.claude-plugin/plugin.json",
         ["/r/.claude-plugin/plugin.json", "/other/.claude-plugin/plugin.json"]),
        ("*/.mcp.json", ["/r/.mcp.json", "/other/nested/.mcp.json"]),
    ]

    def test_each_pattern_matches_more_than_its_fixture_path(self):
        for pattern, paths in self.WITNESSES:
            for path in paths:
                with self.subTest(pattern=pattern, path=path):
                    proc, _ = run_hook(json.dumps({"tool_input": {"file_path": path}}))
                    self.assertIn("Run /vibe-suite:score", proc.stderr,
                                  f"{pattern} must match {path}, not just one fixture path")

    def test_reminder_line_is_exact(self):
        path = "/r/commands/deep/x.md"
        proc, _ = run_hook(json.dumps({"tool_input": {"file_path": path}}))
        self.assertEqual(
            proc.stderr,
            f"NL artifact edited: x.md. Run /vibe-suite:score {path} to check quality.\n")

    def test_reminder_names_the_file_and_the_suite_namespace(self):
        proc, _ = run_hook(
            json.dumps({"tool_input": {"file_path": "/r/commands/deep/x.md"}}))
        line = proc.stderr.strip()
        self.assertTrue(line.startswith("NL artifact edited: x.md."), line)
        self.assertIn("/vibe-suite:score /r/commands/deep/x.md", line)
        self.assertNotIn("/nlpm:", line)
        self.assertNotIn("/vibe:score", line)


if __name__ == "__main__":
    unittest.main()
