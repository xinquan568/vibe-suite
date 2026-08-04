#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The runs-stats port (E6.6 / vibe-52): AC-3's runs-tree fixture — golden KPIs,
UTC-boundary bucketing, freeze-refresh-once, byte-identical ad-hoc isolation — plus the
three port changes: profile-aware identity (--id-pattern, refusal without it), reviewer
labels from run metadata, and offline charts (the vendored bundle inlined in both shells).

The fixture holds four synthetic runs: vibe-90 (complete, model field present, one token
unit), vibe-91 (straddles the UTC/Shanghai day boundary, backend-only metadata), vibe-92
(no metadata id — the folder-name fallback — and no reviewer fields), and a legacy
runs/jira/ entry included only under --include-legacy. All timestamps are fixed; reviewer
metadata uses model-neutral sentinels because tests/ is excluded from model-pin-lint and
this suite carries the no-versioned-id check itself.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATOR = REPO_ROOT / "skills" / "runs-stats" / "scripts" / "generate_runs_stats.py"
VENDOR = REPO_ROOT / "skills" / "runs-stats" / "vendor"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "runs-tree"
GOLDEN = REPO_ROOT / "tests" / "fixtures" / "runs-tree-golden.json"
ID_PATTERN = r"^vibe-(\d+)$"


def run_gen(workdir, *args):
    return subprocess.run(
        [sys.executable, str(GENERATOR), "--runs-root", str(Path(workdir) / "runs"),
         "--reports-dir", str(Path(workdir) / "runs" / "_reports"), *args],
        capture_output=True, text=True)


class RunsTreeCase(unittest.TestCase):
    """Each test gets a throwaway copy of the fixture tree, so mutation tests never touch
    the checked-in fixture."""

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="runs-tree-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        shutil.copytree(FIXTURE / "runs", self.work / "runs")

    def canonical(self, *extra):
        return run_gen(self.work, "--tz", "Asia/Shanghai", "--id-pattern", ID_PATTERN, *extra)

    def history(self):
        return json.loads((self.work / "runs" / "_reports" / "history.json").read_text())


class TestRefusals(RunsTreeCase):
    def test_missing_id_pattern_refuses_with_profile_pointer(self):
        r = run_gen(self.work, "--tz", "Asia/Shanghai")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("id_pattern", r.stderr)
        self.assertIn("profile", r.stderr)
        self.assertFalse((self.work / "runs" / "_reports").exists(),
                         "a refused run writes nothing")

    def test_unknown_timezone_refusal_carried_from_source(self):
        r = run_gen(self.work, "--tz", "Not/AZone", "--id-pattern", ID_PATTERN)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown timezone", r.stderr)


class TestGoldenKpis(RunsTreeCase):
    def test_history_matches_golden(self):
        r = self.canonical()
        self.assertEqual(r.returncode, 0, r.stderr)
        got = self.history()
        golden = json.loads(GOLDEN.read_text())
        # as_of is generation-time and frozen is relative to "today"; kind, window, sig,
        # and every KPI are pinned.
        def stable(h):
            out = {"schema_version": h["schema_version"], "config_key": h["config_key"],
                   "buckets": {}}
            for bid, b in h["buckets"].items():
                out["buckets"][bid] = {k: v for k, v in b.items()
                                       if k not in ("as_of", "frozen")}
            return out
        self.assertEqual(stable(got), stable(golden))

    def test_config_key_records_the_id_pattern(self):
        self.canonical()
        self.assertEqual(self.history()["config_key"],
                         {"tz": "Asia/Shanghai", "include_archived": False,
                          "include_legacy": False, "id_pattern": ID_PATTERN})


class TestBucketing(RunsTreeCase):
    def test_utc_boundary_run_moves_across_the_dateline(self):
        self.canonical()
        shanghai_days = {b for b in self.history()["buckets"] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", b)}
        self.assertIn("2026-08-01", shanghai_days, "17:30Z is Aug 1 in Asia/Shanghai")
        work2 = Path(tempfile.mkdtemp(prefix="runs-tree-utc-"))
        self.addCleanup(shutil.rmtree, work2, ignore_errors=True)
        shutil.copytree(FIXTURE / "runs", work2 / "runs")
        r = run_gen(work2, "--tz", "UTC", "--id-pattern", ID_PATTERN)
        self.assertEqual(r.returncode, 0, r.stderr)
        utc_days = {b for b in json.loads((work2 / "runs" / "_reports" / "history.json")
                                          .read_text())["buckets"]
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", b)}
        self.assertIn("2026-07-31", utc_days)
        self.assertNotIn("2026-08-01", utc_days)

    def test_folder_name_fallback_buckets_vibe_92(self):
        self.canonical()
        alltime = (self.work / "runs" / "_reports" / "all-time.html").read_text()
        self.assertIn("vibe-92", alltime, "metadata-less run identified from its folder name")

    def test_legacy_dir_only_under_include_legacy(self):
        self.canonical()
        self.assertNotIn("QQ-1", (self.work / "runs" / "_reports" / "all-time.html").read_text())
        work2 = Path(tempfile.mkdtemp(prefix="runs-tree-leg-"))
        self.addCleanup(shutil.rmtree, work2, ignore_errors=True)
        shutil.copytree(FIXTURE / "runs", work2 / "runs")
        r = run_gen(work2, "--tz", "Asia/Shanghai", "--id-pattern", ID_PATTERN,
                    "--include-legacy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("QQ-1", (work2 / "runs" / "_reports" / "all-time.html").read_text())


class TestFreezeModel(RunsTreeCase):
    def day_page(self):
        matches = list((self.work / "runs" / "_reports" / "day").glob("2026-07-30*.html"))
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_refresh_once_then_freeze(self):
        self.canonical()
        first = self.day_page().read_bytes()
        state_path = self.work / "runs" / "vibe-90-alpha" / "state.json"
        state = json.loads(state_path.read_text())
        state["rounds"].append({"started_at": "2026-07-30T12:00:00+00:00",
                                "completed_at": "2026-07-30T12:30:00+00:00"})
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        self.canonical()
        second = self.day_page().read_bytes()
        self.assertNotEqual(first, second, "changed run-set signature refreshes the bucket once")
        self.canonical()
        third = self.day_page().read_bytes()
        self.assertEqual(second, third, "unchanged signature leaves the frozen page untouched")

    def test_force_regenerate_period_rebuilds(self):
        self.canonical()
        r = self.canonical("--force-regenerate", "--period", "2026-07-30")
        self.assertEqual(r.returncode, 0, r.stderr)


class TestAdhocIsolation(RunsTreeCase):
    def test_history_byte_identical(self):
        self.canonical()
        hpath = self.work / "runs" / "_reports" / "history.json"
        before = hpath.read_bytes()
        out = self.work / "adhoc.html"
        r = self.canonical("--ticket", "vibe-90", "--out", str(out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out.is_file())
        self.assertEqual(hpath.read_bytes(), before, "AC-3: the byte oracle")


class TestConfigKeyCompat(RunsTreeCase):
    def test_changed_id_pattern_refuses_without_reset(self):
        self.canonical()
        r = run_gen(self.work, "--tz", "Asia/Shanghai", "--id-pattern", r"^other-(\d+)$")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--reset-history", r.stderr)
        r2 = run_gen(self.work, "--tz", "Asia/Shanghai", "--id-pattern", r"^other-(\d+)$",
                     "--reset-history")
        self.assertEqual(r2.returncode, 0, r2.stderr)


class TestOfflineShells(RunsTreeCase):
    EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""", re.I)

    def test_both_shells_inline_the_bundle_with_no_external_refs(self):
        self.canonical()
        vendored = (VENDOR / "chart.umd.min.js").read_text(encoding="utf-8")
        probe = vendored[:400]
        for page in ("index.html", "all-time.html"):
            text = (self.work / "runs" / "_reports" / page).read_text(encoding="utf-8")
            with self.subTest(page=page):
                self.assertIsNone(self.EXTERNAL.search(text),
                                  f"{page} references an external resource")
                self.assertIn(probe, text, f"{page} does not inline the vendored bundle")

    def test_vendor_integrity_matches_vendored_md(self):
        recorded = re.search(r"File sha256:\s*([0-9a-f]{64})",
                             (VENDOR / "VENDORED.md").read_text())
        self.assertIsNotNone(recorded)
        actual = hashlib.sha256((VENDOR / "chart.umd.min.js").read_bytes()).hexdigest()
        self.assertEqual(recorded.group(1), actual)


class TestReviewerLabels(RunsTreeCase):
    def test_label_ladder(self):
        self.canonical()
        alltime = (self.work / "runs" / "_reports" / "all-time.html").read_text()
        self.assertIn("model-sentinel-1", alltime, "model field wins")
        self.assertIn("backend-x", alltime, "backend fallback appears for vibe-91")
        self.assertIn("(unrecorded)", alltime, "no metadata degrades honestly")

    def test_fixture_carries_no_versioned_model_id(self):
        pattern = re.compile(r"(claude|gpt|gemini)-[0-9]", re.I)
        for p in sorted(FIXTURE.rglob("*")):
            if p.is_file():
                with self.subTest(file=str(p.relative_to(FIXTURE))):
                    self.assertIsNone(pattern.search(p.read_text(encoding="utf-8",
                                                                 errors="replace")))


class TestArtifactPosture(unittest.TestCase):
    def test_isc_header_stdlib_generator(self):
        text = GENERATOR.read_text(encoding="utf-8")
        self.assertTrue(any("SPDX-License-Identifier: ISC" in line
                            for line in text.splitlines()[:3]))
        self.assertNotIn("cdn.jsdelivr.net", text, "no CDN reference survives the port")
        self.assertNotIn("QTAC", text)
        self.assertNotIn("QTDQ", text)
        self.assertNotIn("TAC workspace", text)


if __name__ == "__main__":
    unittest.main()


class TestProfileIdentityEnforcement(RunsTreeCase):
    """Step-8 finding: the anchored pattern must bind authoritative ids, not just the
    folder fallback. Metadata ids that mismatch are warned and ignored (data is
    warn-never-abort); ad-hoc --ticket tokens are operator input and refuse; legacy
    records keep their pre-profile ids."""

    def test_mismatched_metadata_ids_are_not_grouped(self):
        r = run_gen(self.work, "--tz", "Asia/Shanghai",
                    "--id-pattern", r"^other-(\d+)$", "--reset-history")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"parse warnings: 2",
                         "vibe-90 and vibe-91 metadata ids must be warned and ignored")

    def test_matching_pattern_produces_no_mismatch_warnings(self):
        r = self.canonical()
        self.assertRegex(r.stdout, r"parse warnings: 0")

    def test_adhoc_ticket_not_matching_pattern_refuses(self):
        self.canonical()
        r = self.canonical("--ticket", "OTHER-9", "--out", str(self.work / "x.html"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("--id-pattern", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_legacy_ids_stay_exempt(self):
        work2 = Path(tempfile.mkdtemp(prefix="runs-tree-lex-"))
        self.addCleanup(shutil.rmtree, work2, ignore_errors=True)
        shutil.copytree(FIXTURE / "runs", work2 / "runs")
        r = run_gen(work2, "--tz", "Asia/Shanghai", "--id-pattern", ID_PATTERN,
                    "--include-legacy")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("QQ-1", (work2 / "runs" / "_reports" / "all-time.html").read_text())
