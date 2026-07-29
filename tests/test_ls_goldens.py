# SPDX-License-Identifier: ISC
"""E3.2 (vibe-27) acceptance: `/vibe-suite:ls` + the scanner agent.

The counting contract has ONE executable seam — scripts/ls_counts.py — invoked by the command
at runtime and by this test over a committed fixture. Discovery patterns are extracted live
from commands/shared/discover.md via tests/test_shared_partials' parser, so the goldens pin
the shipped discovery contract and the shipped counting code together, never a private oracle.

Counting semantics (normative, mirrored in scripts/ls_counts.py and commands/ls.md):
lines = newline count (POSIX `wc -l`; an unterminated final line is not counted);
tokens = per-file ceil(byte_length / 4), summed — never a ceiling over aggregated bytes;
category values = sums over member files; total = sums over category rows.
"""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests.test_shared_partials import (
    dedup,
    discover,
    parse_categories,
    parse_content_qualified,
    parse_exclusions,
    parse_precedence,
    parse_prompt_markers,
    parse_skip_dirs,
)
from tests.test_skill_library import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "ls-golden"
GOLDENS = FIXTURE / "expected.json"
HELPER = REPO_ROOT / "scripts" / "ls_counts.py"
COMMAND = REPO_ROOT / "commands" / "ls.md"
AGENT = REPO_ROOT / "agents" / "scanner.md"

RS = "\x00"  # record separator (NUL)
US = "\x1f"  # field separator between category and path


def fixture_records():
    """Categorize the fixture exactly as discover.md specifies (repo scan: no home, no F)."""
    records = dedup(
        discover(
            FIXTURE,
            parse_categories(),
            parse_skip_dirs(),
            parse_precedence(),
            home=None,
            qualified=parse_content_qualified(),
            markers=parse_prompt_markers(),
            exclusions=parse_exclusions(),
        )
    )
    return [(cat, path) for path, cat, _ in records if path != "expected.json"]


def run_helper(records, root, extra_args=()):
    payload = "".join(f"{cat}{US}{path}{RS}" for cat, path in records)
    return subprocess.run(
        [sys.executable, str(HELPER), "--root", str(root), *extra_args],
        input=payload.encode("utf-8"),
        capture_output=True,
    )


class DeliverablesShip(unittest.TestCase):
    def test_command_exists_with_frontmatter(self):
        fields = parse_frontmatter(
            COMMAND.read_text(encoding="utf-8"),
            required=("description", "argument-hint"),
        )
        self.assertIn("description", fields)
        self.assertIn("argument-hint", fields)

    def test_agent_exists_with_exact_contract(self):
        fields = parse_frontmatter(AGENT.read_text(encoding="utf-8"))
        self.assertEqual(fields["name"], "scanner")
        self.assertEqual(fields["model"], "haiku", "E3.2 fixes the tier: haiku")
        tools = [t.strip() for t in fields["tools"].split(",")]
        self.assertEqual(sorted(tools), ["Glob", "Read"], "tools are exactly Read, Glob")

    def test_agent_body_carries_examples_and_error_handling(self):
        body = AGENT.read_text(encoding="utf-8")
        self.assertGreaterEqual(body.count("<example>"), 2)
        self.assertRegex(body, r"(?im)^#+ .*error")

    def test_both_registered_in_manifest(self):
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertIn("./commands/ls.md", manifest["commands"])
        self.assertIn("./agents/scanner.md", manifest["agents"])

    def test_helper_ships_with_isc_header(self):
        head = HELPER.read_text(encoding="utf-8").splitlines()[:3]
        self.assertTrue(
            any("SPDX-License-Identifier: ISC" in line for line in head),
            "scripts/ls_counts.py must carry the ISC SPDX header in its first 3 lines",
        )

    def test_command_text_contract(self):
        body = COMMAND.read_text(encoding="utf-8")
        self.assertIn("scanner", body, "the command dispatches the scanner agent")
        self.assertIn("scripts/ls_counts.py", body, "the helper is the normative counter")
        self.assertIn(
            '"${CLAUDE_PLUGIN_ROOT}/scripts/ls_counts.py"', body,
            "the helper must be invoked by its plugin-root path — a relative invocation "
            "resolves inside the scanned repo and could execute a file the target controls",
        )
        self.assertRegex(body, r"(?i)default[s]? to the (current working directory|cwd)")
        self.assertRegex(body, r"(?i)categor(y|ies) F .*(omit|outside)")
        for scoring_word in ("penalty", "score band"):
            self.assertNotIn(scoring_word, body.lower(), "no scoring vocabulary (E3.3's lane)")


class GoldenCounts(unittest.TestCase):
    def test_fixture_counts_match_goldens_per_category(self):
        expected = json.loads(GOLDENS.read_text(encoding="utf-8"))
        proc = run_helper(fixture_records(), FIXTURE)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode())
        actual = json.loads(proc.stdout.decode())
        self.assertEqual(actual, expected)

    def test_category_f_absent_from_goldens(self):
        expected = json.loads(GOLDENS.read_text(encoding="utf-8"))
        self.assertNotIn("F", expected, "repo scans omit category F rather than report it empty")

    def test_ceiling_is_per_file_not_aggregate(self):
        # The fixture's category E is exactly two 5-byte files: per-file ceil gives 2+2=4;
        # a ceiling over aggregated bytes would give ceil(10/4)=3. The golden pins 4.
        expected = json.loads(GOLDENS.read_text(encoding="utf-8"))
        self.assertEqual(expected["E"]["tokens"], 4)

    def test_total_row_is_sum_of_category_rows(self):
        expected = json.loads(GOLDENS.read_text(encoding="utf-8"))
        for key in ("files", "lines", "tokens"):
            self.assertEqual(
                expected["total"][key],
                sum(v[key] for c, v in expected.items() if c != "total"),
            )


class HelperContract(unittest.TestCase):
    def test_refuses_absolute_path(self):
        proc = run_helper([("A", str(FIXTURE / "CLAUDE.md"))], FIXTURE)
        self.assertEqual(proc.returncode, 2)

    def test_refuses_root_escape(self):
        proc = run_helper([("A", "../outside.md")], FIXTURE)
        self.assertEqual(proc.returncode, 2)

    def test_refuses_missing_file(self):
        proc = run_helper([("A", "no-such-file.md")], FIXTURE)
        self.assertEqual(proc.returncode, 2)

    def test_skip_directory_decoy_is_committed_and_excluded(self):
        decoy = FIXTURE / "node_modules" / "skip.md"
        self.assertTrue(
            decoy.is_file(),
            "the skip-dir decoy must exist in the working tree (it is force-added past "
            ".gitignore's node_modules/ rule); without it the exclusion assertion is vacuous",
        )
        self.assertNotIn(
            "node_modules/skip.md", [p for _, p in fixture_records()],
            "skip directories must never be discovered",
        )

    def test_hostile_names_counted_exactly_without_side_effects(self):
        import tempfile

        hostile = sorted(
            (cat, path)
            for cat, path in fixture_records()
            if any(ch in path for ch in (" ", ";", "$", "'")) or "/-" in path
        )
        self.assertGreaterEqual(len(hostile), 5, "fixture must carry hostile-name files")
        self.assertTrue(
            any(";touch pwned;" in path for _, path in hostile),
            "an exploit-shaped filename must be part of the hostile set — it is what makes "
            "the canary causal: shell interpretation of it WOULD create ./pwned",
        )
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run(
                [sys.executable, str(HELPER), "--root", str(FIXTURE)],
                input="".join(f"{c}{US}{p}{RS}" for c, p in hostile).encode("utf-8"),
                capture_output=True,
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr.decode())
            actual = json.loads(proc.stdout.decode())
            expected = {"files": 0, "lines": 0, "tokens": 0}
            for _, path in hostile:
                data = (FIXTURE / path).read_bytes()
                expected["files"] += 1
                expected["lines"] += data.count(b"\n")
                expected["tokens"] += -(-len(data) // 4)
            self.assertEqual(actual["A"], expected, "hostile-only counts must be exact")
            self.assertFalse(
                (Path(tmp) / "pwned").exists(), "a hostile filename caused execution"
            )
        self.assertFalse((FIXTURE / "pwned").exists())
        self.assertFalse((Path.cwd() / "pwned").exists())


if __name__ == "__main__":
    unittest.main()
