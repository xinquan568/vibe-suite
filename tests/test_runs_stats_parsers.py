#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""In-process tests for the runs-stats parsers and the behaviours H12 (vibe-216) added.

`tests/test_runs_stats.py` drives `scripts/runs_stats/main.py` as a subprocess against the runs-tree
fixture and is the integration oracle (the golden). This module imports the package and exercises the
nine parsers the grill named with table-driven cases, plus the shape layer (`coerce_state`), the
template loader, the `warnings`-bearing `read_text`, and the in-process CLI entry `main(argv)`.
"""

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import runs_stats.discover as discover  # noqa: E402
import runs_stats.aggregate as aggregate  # noqa: E402
import runs_stats.render as render  # noqa: E402
import runs_stats.main as rs_main  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "runs-tree"
CORRUPT = REPO_ROOT / "tests" / "fixtures" / "runs-tree-corrupt"
STREAM = FIXTURE / "runs" / "vibe-90-alpha" / "round-1" / "phase-1-analyze" / "step-2-review" / "reviewer.json"
UTC = timezone.utc


def dt(*args):
    return datetime(*args, tzinfo=UTC)


class TestParseIso(unittest.TestCase):
    def test_table(self):
        cases = [
            ("2026-07-30T10:00:00Z", dt(2026, 7, 30, 10)),
            ("2026-07-30T18:00:00+0800", dt(2026, 7, 30, 10)),          # offset without colon
            ("2026-07-30T10:00:00.123456+00:00", dt(2026, 7, 30, 10, 0, 0, 123456)),
            ("2026-07-30T10:00:00", dt(2026, 7, 30, 10)),               # naive → UTC
            ("garbage", None), ("", None), (None, None), (12345, None),
        ]
        for raw, want in cases:
            with self.subTest(raw=raw):
                self.assertEqual(discover.parse_iso(raw), want)


class TestUnionSeconds(unittest.TestCase):
    def test_table(self):
        a, b, c, d = dt(2026, 1, 1, 0), dt(2026, 1, 1, 1), dt(2026, 1, 1, 2), dt(2026, 1, 1, 3)
        cases = [
            ([(a, c), (b, d)], 3 * 3600.0),      # overlapping → union
            ([(a, b), (c, d)], 2 * 3600.0),      # disjoint → sum
            ([(a, d), (b, c)], 3 * 3600.0),      # nested
            ([(b, a)], 0.0),                     # inverted dropped
            ([(a, None), (None, b)], 0.0),       # open intervals dropped
            ([], 0.0),
        ]
        for iv, want in cases:
            with self.subTest(iv=iv):
                self.assertEqual(discover.union_seconds(iv), want)


class TestNormalizeTokenBlock(unittest.TestCase):
    def test_three_shapes_and_accuracy(self):
        codex = {"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 200,
                 "reasoning_output_tokens": 50, "method": "codex-reported"}
        nb = discover.normalize_token_block(codex)
        self.assertEqual((nb["input_total"], nb["input_cached"], nb["input_uncached"], nb["output"],
                          nb["reasoning_output"], nb["accuracy"]), (1000, 400, 600, 200, 50, "accurate"))
        log = {"input_total": 10, "input_cached": 30, "output": 2, "method": "file-size-estimate"}
        nb = discover.normalize_token_block(log)
        self.assertEqual((nb["input_uncached"], nb["accuracy"]), (0, "estimate"))   # clamp at 0
        est = {"input_estimate": 5, "output_estimate": 1}
        self.assertEqual(discover.normalize_token_block(est)["accuracy"], "unknown")

    def test_rejects(self):
        self.assertIsNone(discover.normalize_token_block(None))
        self.assertIsNone(discover.normalize_token_block("tokens"))
        self.assertIsNone(discover.normalize_token_block({"method": "codex-reported"}))  # neither input nor output


class TestTokensFromLog(unittest.TestCase):
    def test_locations(self):
        blk = {"input_tokens": 1, "output_tokens": 2}
        self.assertEqual(discover.tokens_from_log({"tokens": blk})["output"], 2)
        self.assertEqual(discover.tokens_from_log({"verify_tokens": blk})["output"], 2)
        self.assertEqual(discover.tokens_from_log({"verify": {"tokens": blk}})["output"], 2)
        self.assertEqual(discover.tokens_from_log({"input_total": 7, "output": 3})["input_total"], 7)  # flat
        self.assertIsNone(discover.tokens_from_log({"verdict": "approve"}))
        self.assertIsNone(discover.tokens_from_log("nope"))


class TestUsageFromEventStream(unittest.TestCase):
    def test_fixture_stream(self):
        w = []
        nb, calls = discover.usage_from_event_stream(str(STREAM), w)
        self.assertEqual((nb["input_total"], nb["input_cached"], nb["input_uncached"], nb["output"],
                          nb["method"], nb["accuracy"], calls), (1000, 400, 600, 200, "codex-reported", "accurate", 2))
        self.assertEqual(w, [])

    def test_bad_lines_skipped_and_missing_file_warns(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.jsonl"
            p.write_text('{"type":"item.completed"}\nnot json\n{"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":1}}\n')
            w = []
            nb, calls = discover.usage_from_event_stream(str(p), w)
            self.assertEqual((nb["input_total"], calls, w), (3, 1, []))
            w = []
            self.assertEqual(discover.usage_from_event_stream(str(Path(td) / "absent"), w), (None, 0))
            self.assertEqual(len(w), 1)
            self.assertTrue(w[0].startswith("stream-error:"), w)

    def test_non_numeric_usage_warns_instead_of_raising(self):        # T13
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.jsonl"
            p.write_text('{"type":"turn.completed","usage":{"input_tokens":"abc","output_tokens":2}}\n')
            w = []
            nb, calls = discover.usage_from_event_stream(str(p), w)
            self.assertEqual((nb["input_total"], nb["output"], calls), (0, 2, 0))
            self.assertEqual(len(w), 1)
            self.assertIn("non-numeric usage field input_tokens", w[0])


def unit(**kw):
    base = {"round": 1, "step_base": "step-2", "iteration": None, "repo": None, "start": None, "end": None,
            "duration": None, "tokens": None}
    base.update(kw)
    return base


class TestComputeTiming(unittest.TestCase):
    def test_levels_and_ladder(self):
        a, b, c = dt(2026, 1, 1, 0), dt(2026, 1, 1, 1), dt(2026, 1, 1, 2)
        # per-repo units run in parallel → interval union (2h), not sum (3h)
        units = [unit(repo="r1", start=a, end=c), unit(repo="r2", start=b, end=c)]
        t = discover.compute_timing(units, {}, {})
        self.assertEqual((t["active_seconds"], t["time_method"], t["time_confidence"]), (7200, "step-sum", "high"))
        # iterations without timestamps → durations summed
        units = [unit(iteration=1, duration=10.0), unit(iteration=2, duration=5.0)]
        self.assertEqual(discover.compute_timing(units, {}, {})["active_seconds"], 15)
        # per-repo durations → max
        units = [unit(repo="r1", duration=10.0), unit(repo="r2", duration=5.0)]
        self.assertEqual(discover.compute_timing(units, {}, {})["active_seconds"], 10)
        # round span only → medium
        st = {"rounds": [{"started_at": a.isoformat(), "completed_at": b.isoformat()}]}
        t = discover.compute_timing([], st, {})
        self.assertEqual((t["elapsed_seconds"], t["time_method"], t["time_confidence"]), (3600, "round-span", "medium"))
        # lifecycle → low; nothing → unknown
        t = discover.compute_timing([], {"updated_at": b.isoformat()}, {"created_at": a.isoformat()})
        self.assertEqual((t["elapsed_seconds"], t["time_method"], t["time_confidence"]), (3600, "lifecycle", "low"))
        self.assertEqual(discover.compute_timing([], {}, {})["time_method"], "unknown")

    def test_run_started_precedence(self):
        a, b, c = dt(2026, 1, 1, 0), dt(2026, 1, 1, 1), dt(2026, 1, 1, 2)
        st = {"rounds": [{"started_at": b.isoformat()}]}
        self.assertEqual(discover.compute_timing([unit(start=c, end=c)], st, {"created_at": a.isoformat()})["run_started_at"], b.isoformat())
        self.assertEqual(discover.compute_timing([unit(start=c, end=c)], {}, {"created_at": a.isoformat()})["run_started_at"], a.isoformat())
        self.assertEqual(discover.compute_timing([unit(start=c, end=c)], {}, {})["run_started_at"], c.isoformat())


class TestNormalizeStatus(unittest.TestCase):
    def test_table(self):
        cases = [
            (("completed", "findings-only", None), ("success", "findings_only")),
            (("completed", "no PR opened", None), ("success", "completed_no_pr")),
            (("pr_opened", None, None), ("success", "pr_opened")),
            (("completed", "pr_opened", None), ("success", "pr_opened")),
            (("completed", None, None), ("success", "completed")),
            (("completed", {"pr": 1}, None), ("success", "pr_opened")),           # object outcome flattened
            (("stopped_by_review", None, "plan-blocker"), ("stopped", "plan-blocker")),
            (("running", None, "cap"), ("stopped", "cap")),                        # stop_reason wins
            (("failed", None, None), ("failed", "failed")),
            (("watchdog_timeout", None, None), ("failed", "watchdog_timeout")),
            (("running_step_4", None, None), ("in_progress", "running_step_4")),
            (("pending", None, None), ("pending", "pending")),
            ((None, None, None), ("unknown", "(none)")),
            (("weird", None, None), ("unknown", "weird")),
        ]
        for args, want in cases:
            with self.subTest(args=args):
                self.assertEqual(discover.normalize_status(*args), want)


class TestExtractTests(unittest.TestCase):
    def test_table(self):
        self.assertEqual(discover.extract_tests({"tests": {"run": 3, "failed": 1, "skipped": "x"}}), {"run": 3, "failed": 1})
        self.assertEqual(discover.extract_tests({"tests_run": 5, "tests_errors": 2}), {"run": 5, "errors": 2})
        self.assertEqual(discover.extract_tests({"tests": {"run": 1}, "tests_failed": 4}), {"run": 1, "failed": 4})
        self.assertIsNone(discover.extract_tests({"verdict": "approve"}))
        self.assertIsNone(discover.extract_tests(None))


def run_record(rid, tokens=1000, n_rounds=1, commits=(), started="2026-07-30T10:00:00+00:00"):
    return {"id": rid, "reviewer_tokens": {"input_total": tokens, "output": 0}, "n_rounds": n_rounds, "status_cat": "success",
            "timing": {"active_seconds": 900, "run_started_at": started}, "findings_caught": 0, "commits": list(commits)}


class TestBucketSignature(unittest.TestCase):
    def test_properties(self):
        r1, r2 = run_record("a"), run_record("b")
        sig = aggregate.bucket_signature([r1, r2])
        self.assertRegex(sig, r"^[0-9a-f]{16}$")
        self.assertEqual(sig, aggregate.bucket_signature([r2, r1]))                       # order-independent
        self.assertNotEqual(sig, aggregate.bucket_signature([run_record("a", tokens=1001), r2]))
        self.assertNotEqual(sig, aggregate.bucket_signature([run_record("a", n_rounds=2), r2]))
        self.assertNotEqual(sig, aggregate.bucket_signature([run_record("a", commits=("c1",)), r2]))


class TestConfigure(unittest.TestCase):
    def test_identity_and_root(self):
        with tempfile.TemporaryDirectory() as td:
            discover.configure(Path(td), r"^vibe-(\d+)$")
            self.assertEqual(str(discover.RUNS_ROOT), str(Path(td).resolve()))
            self.assertTrue(discover.ID_RE.fullmatch("vibe-12"))
            self.assertIsNone(discover.ID_RE.fullmatch("retry-vibe-12-x"))
            self.assertEqual(discover.ticket_key_from("retry-vibe-12-mystery"), "VIBE-12")   # unanchored core


class TestCoerceState(unittest.TestCase):                                   # T12
    def test_table(self):
        cases = [
            ([1], {}, 1), ("str", {}, 1), (5, {}, 1),
            ({"status": "completed", "rounds": {"a": 1}}, {"status": "completed", "rounds": []}, 1),
            ({"status": 5}, {"status": None}, 1),
            ({"rounds": [5, {"commits": "abc", "pr_url": 7}]}, {"rounds": [{"commits": []}]}, 3),
            ({"status": "completed", "rounds": [{"started_at": "x"}], "outcome": None}, {"status": "completed", "rounds": [{"started_at": "x"}], "outcome": None}, 0),
            ({"rounds": None, "status": None}, {"rounds": None, "status": None}, 0),   # None is absent
            ({}, {}, 0),
        ]
        for raw, want, n in cases:
            with self.subTest(raw=raw):
                w = []
                self.assertEqual(discover.coerce_state(raw, "run-x", w), want)
                self.assertEqual(len(w), n, w)
                self.assertTrue(all(x.startswith("shape-error: run-x:") for x in w), w)

    def test_build_execution_run_survives_the_corrupt_fixture(self):
        w = []
        discover.configure(CORRUPT / "runs", r"^vibe-(\d+)$")
        with tempfile.TemporaryDirectory() as td:
            shutil.copytree(CORRUPT / "runs", Path(td) / "runs")
            bad = Path(td) / "runs" / "vibe-96-notjson"
            (bad / "state.json.malformed").rename(bad / "state.json")
            discover.configure(Path(td) / "runs", r"^vibe-(\d+)$")
            statuses = {}
            for name in ("vibe-95-clean", "vibe-96-notjson", "vibe-97-shapes", "vibe-98-entries", "vibe-99-list"):
                r = discover.build_execution_run(str(Path(td) / "runs" / name), "direct", None, w)
                statuses[name] = r["status_cat"]
        self.assertEqual(statuses, {"vibe-95-clean": "success", "vibe-96-notjson": "unknown", "vibe-97-shapes": "unknown",
                                    "vibe-98-entries": "success", "vibe-99-list": "unknown"})
        self.assertEqual(len(w), 7, w)


class TestReadText(unittest.TestCase):                                      # T25a
    def test_directory_warns(self):
        with tempfile.TemporaryDirectory() as td:
            w = []
            self.assertIsNone(discover.read_text(td, warnings=w))
            self.assertEqual(len(w), 1)
            self.assertTrue(w[0].startswith("timeline-read-error:"), w)

    def test_file_reads_and_caps(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.md"; p.write_text("x" * 30)
            w = []
            self.assertEqual(discover.read_text(str(p), cap=10, warnings=w), "x" * 10 + "\n…(truncated)…")
            self.assertEqual(w, [])


class TestTemplates(unittest.TestCase):                                     # T11
    def test_sentinel_templates_are_what_renders(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "dashboard.html").write_text("<html>DASH-SENTINEL <script>__CHART_BUNDLE__</script><title>__TITLE__</title>__DATA__</html>")
            (Path(td) / "index.html").write_text("<html>INDEX-SENTINEL <script>__CHART_BUNDLE__</script><title>__TITLE__</title>__DATA__</html>")
            with mock.patch.object(render, "TEMPLATE_DIR", Path(td)):
                render.reset_caches()
                page = render.render_html({"runs": [], "note": "</script>"})
                index = render.render_index({"buckets": {}}, Path(td))
            render.reset_caches()
        self.assertIn("DASH-SENTINEL", page); self.assertNotIn("INDEX-SENTINEL", page)
        self.assertIn("INDEX-SENTINEL", index); self.assertNotIn("DASH-SENTINEL", index)
        for text in (page, index):
            for ph in ("__CHART_BUNDLE__", "__TITLE__", "__DATA__"):
                self.assertNotIn(ph, text)
        self.assertIn("<\\/script>", page)                                     # payload escape survives

    def test_shipped_templates_pinned(self):                                # T16
        for name in ("dashboard.html", "index.html"):
            text = (REPO_ROOT / "templates" / "runs-stats" / name).read_text(encoding="utf-8")
            self.assertGreater(len(text), 1000)
            for ph in ("__CHART_BUNDLE__", "__DATA__"):
                self.assertEqual(text.count(ph), 1, (name, ph))
            self.assertEqual(text.count("__TITLE__"), 2, name)   # <title> and the <h1>, as shipped


class TestMainInProcess(unittest.TestCase):                                 # T25b
    def test_timeline_read_failure_is_a_warning(self):
        with tempfile.TemporaryDirectory() as td:
            shutil.copytree(FIXTURE / "runs", Path(td) / "runs")
            adir = Path(td) / "not-a-file"; adir.mkdir()
            out = io.StringIO()
            with mock.patch.object(discover, "discover_timeline", return_value=str(adir)), contextlib.redirect_stdout(out):
                rc = rs_main.main(["--runs-root", str(Path(td) / "runs"), "--reports-dir", str(Path(td) / "runs" / "_reports"),
                                   "--tz", "Asia/Shanghai", "--id-pattern", r"^vibe-(\d+)$"])
            self.assertIn(rc, (None, 0))
            self.assertRegex(out.getvalue(), r"parse warnings: 3")   # three runs, each timeline read fails once


if __name__ == "__main__":
    unittest.main()
