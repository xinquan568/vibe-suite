#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""E7.3 (vibe-55): the AC-6 legacy-string sweep.

The sweep is the repository-wide widening `scripts/lib/retired_names.py`'s docstring assigns
to E7.3: no retired command namespace in any shipped runtime-reachable string. Its scope is a
total SWEPT/EXEMPT partition (the model-pin precedent), its patterns are the predicate's five
literals (cross-pinned here so the two copies cannot drift), and its one per-file exception is
the predicate module itself — enforcement data, not runtime text.
"""

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SWEEP = REPO_ROOT / "tools" / "legacy-string-sweep.sh"

sys.path.insert(0, str(REPO_ROOT / "scripts" / "lib"))
import retired_names  # noqa: E402


def run_sweep(cwd, *args):
    return subprocess.run(["bash", str(SWEEP), *args],
                          capture_output=True, text=True, cwd=cwd)


def script_text():
    if not SWEEP.is_file():
        raise AssertionError("tools/legacy-string-sweep.sh does not exist")
    return SWEEP.read_text(encoding="utf-8")


class SweepContract(unittest.TestCase):
    def test_script_exists_with_isc_header(self):
        text = script_text()
        self.assertIn("SPDX-License-Identifier: ISC",
                      "\n".join(text.splitlines()[:3]))

    def test_patterns_cross_pinned_to_the_predicate(self):
        text = script_text()
        for name in retired_names.RETIRED:
            self.assertIn(name, text, f"sweep lacks predicate pattern {name!r}")

    def test_partition_is_total_over_tracked_top_level(self):
        text = script_text()
        proc = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                              cwd=REPO_ROOT)
        tops = {line.split("/")[0] for line in proc.stdout.splitlines() if line}
        for top in sorted(tops):
            self.assertIn(top, text,
                          f"top-level entry {top!r} is unclassified in the sweep")

    def test_future_site_surface_is_preclassified(self):
        # A-1: disposition expects a separate site/ tree at S8; the classification exists
        # before the surface does.
        self.assertRegex(script_text(), re.compile(r'^\s*SWEPT=.*\bsite\b', re.M | re.S))

    def test_predicate_exception_is_stated_with_reason(self):
        text = script_text()
        self.assertIn("scripts/lib/retired_names.py", text)
        self.assertIn("enforcement data", text)

    def test_clean_tree_passes(self):
        proc = run_sweep(REPO_ROOT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_planted_name_fails_with_location(self):
        with tempfile.TemporaryDirectory(prefix="sweep-seed-") as tmp:
            root = Path(tmp)
            (root / "commands").mkdir()
            (root / "commands" / "evil.md").write_text(
                "---\ndescription: x\n---\nRun /nlpm:score now.\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            proc = run_sweep(root)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("commands/evil.md", proc.stdout + proc.stderr)
            self.assertIn("/nlpm:", proc.stdout + proc.stderr)

    def test_exempt_area_hit_does_not_fail(self):
        with tempfile.TemporaryDirectory(prefix="sweep-exempt-") as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs" / "history.md").write_text("The old /grill:roast is retired.\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            proc = run_sweep(root)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_unknown_flag_is_exit_2(self):
        proc = run_sweep(REPO_ROOT, "--definitely-not-a-flag")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)

    def test_ci_wires_the_job(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("bash tools/legacy-string-sweep.sh", ci)
        self.assertIn("AC-6", ci)


if __name__ == "__main__":
    unittest.main()
