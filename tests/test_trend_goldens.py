#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Trend surface (E6.2 / vibe-48): the record contract, the scope vocabulary, and the trend
engine's golden output over fixture histories.

Every history fixture is copied into a temporary workspace before a trend run — the engine owns
the append, so running it against a checked-in fixture would mutate the corpus. Byte-level
assertions are deliberate: the acceptance is "sentinel-clean" style determinism, and a parsed
comparison would hide ordering and formatting drift that the golden exists to freeze.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "trend"
SCORE = REPO_ROOT / "scripts" / "score_engine.py"
TREND = REPO_ROOT / "scripts" / "trend_engine.py"
SCOPE_TAG = REPO_ROOT / "scripts" / "lib" / "scope_tag.py"


def run_py(script, *args, stdin=""):
    return subprocess.run([sys.executable, str(script), *args],
                          input=stdin, capture_output=True, text=True)


class TestRunScopedDedup(unittest.TestCase):
    """W1: --run-id semantics on score_engine's appender; flagless behavior byte-identical."""

    RECORD = "command\x1fcommands/advisor.md\x00"

    def _score(self, root, hist, *extra):
        return run_py(SCORE, "--root", str(root), "--history", str(hist),
                      "--scope", "full", *extra, stdin=self.RECORD)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="trend-w1-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.hist = self.tmp / "vibe-history.json"

    def test_flagless_append_and_dedup_bytes(self):
        r1 = self._score(REPO_ROOT, self.hist)
        self.assertEqual(r1.returncode, 0, r1.stderr)
        first = self.hist.read_bytes()
        entries = json.loads(first)
        self.assertEqual(len(entries), 1)
        self.assertNotIn("run", entries[0], "flagless entries carry no run field")
        r2 = self._score(REPO_ROOT, self.hist)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual(self.hist.read_bytes(), first,
                         "flagless identical re-score must dedupe to byte-identical history")
        self.assertEqual(r1.stdout, r2.stdout, "stdout is deterministic")

    def test_run_scoped_dedup(self):
        self._score(REPO_ROOT, self.hist, "--run-id", "r1")
        one = json.loads(self.hist.read_text())
        self.assertEqual([e.get("run") for e in one], ["r1"])
        self._score(REPO_ROOT, self.hist, "--run-id", "r1")
        self.assertEqual(len(json.loads(self.hist.read_text())), 1,
                         "same run + identical content drops")
        self._score(REPO_ROOT, self.hist, "--run-id", "r2")
        two = json.loads(self.hist.read_text())
        self.assertEqual(len(two), 2, "identical content under a new run appends")
        self.assertEqual([e.get("run") for e in two], ["r1", "r2"])


class TestScopeTag(unittest.TestCase):
    """W2: the shared scope derivation CLI."""

    def test_four_canonical_tags(self):
        root = Path(tempfile.mkdtemp(prefix="scope-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "skills").mkdir()
        cases = [((), "full"),
                 (("--path", "skills"), "path:skills"),
                 (("--changed",), "changed"),
                 (("--path", "skills", "--changed"), "changed:skills"),
                 (("--path", "./skills/"), "path:skills")]
        for extra, want in cases:
            r = run_py(SCOPE_TAG, "--root", str(root), *extra)
            self.assertEqual(r.returncode, 0, (extra, r.stderr))
            self.assertEqual(r.stdout.strip(), want, extra)

    def test_outside_root_refused(self):
        root = Path(tempfile.mkdtemp(prefix="scope2-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        r = run_py(SCOPE_TAG, "--root", str(root), "--path", "../etc")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_inside_symlink_to_outside_target_refused(self):
        root = Path(tempfile.mkdtemp(prefix="scope3-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        outside = Path(tempfile.mkdtemp(prefix="scope3-out-"))
        self.addCleanup(shutil.rmtree, outside, ignore_errors=True)
        (root / "link").symlink_to(outside)
        r = run_py(SCOPE_TAG, "--root", str(root), "--path", "link")
        self.assertEqual(r.returncode, 2, "an in-root symlink to an outside target is a refusal")
        self.assertEqual(r.stdout, "")


def load_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class TrendCase(unittest.TestCase):
    SCORE_JSON = None   # set in setUpClass by subclasses reading a fixture

    def ws_with_history(self, text_or_none, parent=".claude"):
        ws = Path(tempfile.mkdtemp(prefix="trend-ws-"))
        self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
        hist = ws / parent / "vibe-history.json"
        if text_or_none is not None:
            hist.parent.mkdir(parents=True, exist_ok=True)
            hist.write_text(text_or_none, encoding="utf-8")
        return ws, hist

    def trend(self, ws, hist, *extra, stdin=None):
        return run_py(TREND, "--root", str(ws), "--history", str(hist),
                      "--scope", "full", "--run-id", "r2",
                      *extra, stdin=stdin if stdin is not None else self.SCORE_JSON)


class TestTrendGolden(TrendCase):
    """W3: the golden over the mixed fixture, run against BOTH container shapes."""

    @classmethod
    def setUpClass(cls):
        cls.SCORE_JSON = load_fixture("score-current.json")

    def _assert_golden(self, hist_fixture):
        ws, hist = self.ws_with_history(load_fixture(hist_fixture))
        r = self.trend(ws, hist)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, load_fixture("golden-trend.json"),
                         f"golden mismatch for {hist_fixture}")
        after = json.loads(hist.read_text())
        if "dict" in hist_fixture:
            self.assertIsInstance(after, dict, "the dict container round-trips as a dict")
            entries = after["snapshots"]
        else:
            self.assertIsInstance(after, list)
            entries = after
        self.assertEqual(sum(1 for e in entries if e.get("run") == "r2"), 4,
                         "the current run appends after compute")

    def test_golden_list_shape(self):
        self._assert_golden("history-list.json")

    def test_golden_dict_shape(self):
        self._assert_golden("history-dict.json")

    def test_pre_append_baseline_proof(self):
        ws, hist = self.ws_with_history(load_fixture("history-list.json"))
        r = self.trend(ws, hist)
        out = json.loads(r.stdout)
        by_path = {f["path"]: f for f in out["files"]}
        self.assertEqual(by_path["commands/a.md"]["previous"], 85,
                         "baseline is the pre-append last entry, excluding the current run")
        appended = [e for e in json.loads(hist.read_text()) if e.get("run") == "r2"]
        self.assertEqual({e["file"]: e["score"] for e in appended},
                         {"commands/a.md": 90, "commands/b.md": 85, "commands/c.md": 100,
                          "commands/d.md": 95})


class TestTrendDegenerates(TrendCase):
    """W3: missing (file and parent) and malformed histories."""

    @classmethod
    def setUpClass(cls):
        cls.SCORE_JSON = load_fixture("score-current.json")

    def test_missing_history_is_baseline(self):
        ws, hist = self.ws_with_history(None)
        r = self.trend(ws, hist)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["status"]["history"], "missing")
        self.assertTrue(all(f["flag"] == "new" for f in out["files"]))
        self.assertTrue(hist.is_file(), "missing parent + file are created inside the root")
        entries = json.loads(hist.read_text())
        self.assertEqual(len(entries), 4)

    def test_malformed_history_warns_once_and_starts_fresh(self):
        ws, hist = self.ws_with_history("{not json")
        r = self.trend(ws, hist)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len([l for l in r.stderr.splitlines() if l.strip()]), 1,
                         "exactly one warning line")
        out = json.loads(r.stdout)
        self.assertEqual(out["status"]["history"], "malformed")
        entries = json.loads(hist.read_text())
        self.assertIsInstance(entries, list)
        self.assertEqual(len(entries), 4, "the fresh history holds exactly the current run")

    def test_scope_filter_is_apples_to_apples(self):
        ws, hist = self.ws_with_history(load_fixture("history-list.json"))
        r = self.trend(ws, hist, stdin=self.SCORE_JSON)
        out = json.loads(r.stdout)
        self.assertNotIn("commands/other.md", [f["path"] for f in out["files"]],
                         "entries of other scopes never enter the comparison")
        self.assertEqual(out["status"]["scope_matches"], 4)


class TestRecordContractEdges(TrendCase):
    """W-F6: the remaining frozen-contract rules, each with its own oracle."""

    @classmethod
    def setUpClass(cls):
        cls.SCORE_JSON = load_fixture("score-current.json")

    def test_fixed_byte_oracle_and_keyed_then_flagless(self):
        """The oracle is a checked-in byte fixture, not a runtime derivation: the keyed append
        over the mini-root must produce exactly expected-append.json, and a flagless identical
        re-score must leave those bytes untouched (content-key dedup across keyed entries)."""
        tmp = Path(tempfile.mkdtemp(prefix="trend-oracle-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        hist = tmp / "vibe-history.json"
        record = "command\x1fcommands/go.md\x00"
        mini = FIXTURES / "mini-root"
        r = run_py(SCORE, "--root", str(mini), "--history", str(hist),
                   "--scope", "full", "--run-id", "r1", stdin=record)
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = (FIXTURES / "expected-append.json").read_bytes()
        self.assertEqual(hist.read_bytes(), expected, "the checked-in byte oracle")
        r2 = run_py(SCORE, "--root", str(mini), "--history", str(hist),
                    "--scope", "full", stdin=record)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertEqual(hist.read_bytes(), expected,
                         "flagless dedup matches content keys across keyed entries")

    def test_run_id_bounds_refused_by_both_clis(self):
        tmp = Path(tempfile.mkdtemp(prefix="trend-bounds-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        hist = tmp / "vibe-history.json"
        record = "command\x1fcommands/advisor.md\x00"
        for bad in ("", "x" * 65):
            r = run_py(SCORE, "--root", str(REPO_ROOT), "--history", str(hist),
                       "--scope", "full", "--run-id", bad, stdin=record)
            self.assertEqual(r.returncode, 2, (len(bad), r.stderr))
            r2 = run_py(TREND, "--root", str(tmp), "--history", str(hist),
                        "--scope", "full", "--run-id", bad, stdin=self.SCORE_JSON)
            self.assertEqual(r2.returncode, 2, (len(bad), r2.stderr))

    def test_same_run_conflict_reader_takes_last(self):
        ws, hist = self.ws_with_history(load_fixture("history-conflict.json"))
        r = self.trend(ws, hist)
        out = json.loads(r.stdout)
        r1 = [g for g in out["trajectory"] if g["run"] == "r1"][0]
        self.assertEqual(r1["mean_score"], 85.0, "last-wins per (run, scope, file)")
        self.assertEqual(r1["files"], 1)

    def test_legacy_bucket_orders_first_even_when_physically_last(self):
        ws, hist = self.ws_with_history(load_fixture("history-legacy-after.json"))
        r = self.trend(ws, hist)
        runs = [g["run"] for g in json.loads(r.stdout)["trajectory"]]
        self.assertEqual(runs[0], "(pre-run-id)")
        self.assertEqual(runs[-1], "r2")

    def test_existing_current_run_entries_merge_last_wins(self):
        ws, hist = self.ws_with_history(load_fixture("history-current-run.json"))
        r = self.trend(ws, hist)
        out = json.loads(r.stdout)
        r2 = [g for g in out["trajectory"] if g["run"] == "r2"][0]
        self.assertEqual(r2["files"], 5, "existing r2 entries merge with incoming (x survives)")
        # incoming a=90 wins over the existing r2 a=70: (90+85+100+95+70x)/5 = 88.0
        self.assertEqual(r2["mean_score"], 88.0)
        by_path = {f["path"]: f for f in out["files"]}
        self.assertEqual(by_path["commands/a.md"]["flag"], "new",
                         "the baseline excludes current-run entries entirely")

    def test_limit_keeps_last_n(self):
        ws, hist = self.ws_with_history(load_fixture("history-list.json"))
        r = self.trend(ws, hist, "--limit", "2")
        runs = [g["run"] for g in json.loads(r.stdout)["trajectory"]]
        self.assertEqual(runs, ["r1", "r2"], "--limit keeps the last N points, current included")

    def test_marker_bytes_preserved_list_dict_and_crlf(self):
        cases = {
            "noncanonical-list.json": b'{"note":   "marker entry",\n        "weird_spacing": true}',
            "noncanonical-dict.json": b'{"note":"marker",   "odd": 1}',
            "noncanonical-crlf-list.json": b'{"note":   "crlf marker"},\r\n',
        }
        for name, marker in cases.items():
            src = (FIXTURES / name).read_bytes()
            ws = Path(tempfile.mkdtemp(prefix="trend-marker-"))
            self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
            hist = ws / ".claude" / "vibe-history.json"
            hist.parent.mkdir(parents=True)
            hist.write_bytes(src)
            r = self.trend(ws, hist)
            self.assertEqual(r.returncode, 0, (name, r.stderr))
            after = hist.read_bytes()
            self.assertIn(marker, after,
                          f"{name}: the marker's exact bytes (line endings included) survive")
            self.assertTrue(after.startswith(src[:src.index(marker) + len(marker)]),
                            f"{name}: every byte up to and including the marker is unchanged")
            if b"dict" in name.encode():
                self.assertIn(b'"trailing_key": "kept"', after)
