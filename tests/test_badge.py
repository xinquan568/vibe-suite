#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The badge surface (E6.4 / vibe-50): the pinned shields endpoint schema, latest-snapshot
selection over the stored record, the refresh path, the deterministic attestation sidecar,
and the fail-closed refusal matrix.

The acceptance is "endpoint JSON validates against the shields.io schema" and "refresh path
exercised". The badge writes nothing — refresh is re-invocation — so the refresh test is two
invocations over a history that changed between them, with no filesystem semantics involved.
"""

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BADGE = REPO_ROOT / "bin" / "vibe-badge"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import trend_engine  # noqa: E402

NAMED_COLORS = {"brightgreen", "green", "yellowgreen", "orange", "red", "lightgrey"}
BADGE_KEYS = {"schemaVersion", "label", "message", "color"}
ATTESTATION_KEYS = {"kind", "schema", "scope", "run", "mean_score", "band", "files",
                    "runs_observed", "history_sha256"}

# Entry shape per the record contract: {"scope","score","file"} required, "run" keys a run
# group, no "run" lands in the legacy "(pre-run-id)" bucket.
R1 = [
    {"scope": "full", "score": 100, "file": "commands/a.md", "run": "r1",
     "band": "Excellent", "total_penalty": 0},
    {"scope": "full", "score": 90, "file": "commands/b.md", "run": "r1",
     "band": "Excellent", "total_penalty": -10},
    {"scope": "path:commands/a.md", "score": 50, "file": "commands/a.md", "run": "r1",
     "band": "Rewrite", "total_penalty": -50},
]
R2 = [
    {"scope": "full", "score": 72, "file": "commands/a.md", "run": "r2",
     "band": "Adequate", "total_penalty": -28},
    {"scope": "full", "score": 78, "file": "commands/b.md", "run": "r2",
     "band": "Adequate", "total_penalty": -22},
]
LEGACY = [
    {"scope": "full", "score": 60, "file": "commands/a.md",
     "band": "Weak", "total_penalty": -40},
]


def run_badge(*args):
    return subprocess.run([sys.executable, str(BADGE), *args],
                          capture_output=True, text=True)


def write_history(dirpath, entries, name="history.json"):
    path = Path(dirpath) / name
    path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return path


class TestArtifactPosture(unittest.TestCase):
    def test_isc_header_executable_stdlib(self):
        text = BADGE.read_text(encoding="utf-8")
        head = text.splitlines()[:3]
        self.assertTrue(any("SPDX-License-Identifier: ISC" in line for line in head),
                        "ISC header within 3 lines")
        self.assertTrue(os.stat(BADGE).st_mode & stat.S_IXUSR, "executable bit")
        allowed = {"argparse", "hashlib", "json", "sys", "pathlib",
                   "trend_engine", "score_engine"}
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                module = stripped.split()[1].split(".")[0]
                self.assertIn(module, allowed, f"non-stdlib import: {stripped}")


class TestBadgeSchema(unittest.TestCase):
    def assert_shields_payload(self, payload):
        self.assertEqual(set(payload), BADGE_KEYS, "exactly the documented fields")
        self.assertIs(type(payload["schemaVersion"]), int, "int, bool rejected")
        self.assertEqual(payload["schemaVersion"], 1)
        for key in ("label", "message"):
            self.assertIsInstance(payload[key], str)
            self.assertTrue(payload[key])
        self.assertIn(payload["color"], NAMED_COLORS)

    def test_normal_payload_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1 + R2)
            r = run_badge("--history", str(hist))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assert_shields_payload(json.loads(r.stdout))

    def test_no_data_payload_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_badge("--history", str(Path(tmp) / "absent.json"))
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assert_shields_payload(payload)
            self.assertEqual(payload["message"], "no data")
            self.assertEqual(payload["color"], "lightgrey")


class TestLatestSnapshot(unittest.TestCase):
    def test_latest_run_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1 + R2)
            r = run_badge("--history", str(hist))
            payload = json.loads(r.stdout)
            self.assertEqual(payload["message"], "75.0 · Adequate")
            self.assertEqual(payload["color"], "yellowgreen")
            self.assertEqual(payload["label"], "vibe-suite")

    def test_scope_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1 + R2)
            r = run_badge("--history", str(hist), "--scope", "path:commands/a.md")
            payload = json.loads(r.stdout)
            self.assertEqual(payload["message"], "50.0 · Rewrite")
            self.assertEqual(payload["color"], "red")
            self.assertEqual(payload["label"], "vibe-suite · path:commands/a.md")

    def test_legacy_bucket_first_regardless_of_position(self):
        # Legacy entries physically AFTER the keyed run still form the FIRST trajectory
        # point, so the latest snapshot stays the last keyed run.
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R2 + LEGACY)
            r = run_badge("--history", str(hist))
            self.assertEqual(json.loads(r.stdout)["message"], "75.0 · Adequate")

    def test_legacy_only_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, LEGACY)
            r = run_badge("--history", str(hist), "--attestation")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["run"], trend_engine.LEGACY_RUN)


class TestRefreshPath(unittest.TestCase):
    def test_reinvocation_reflects_new_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1)
            first = json.loads(run_badge("--history", str(hist)).stdout)
            self.assertEqual(first["message"], "95.0 · Excellent")
            self.assertEqual(first["color"], "brightgreen")
            # The record grew (fixture surgery, not the trend engine); refresh is just
            # running the tool again.
            write_history(tmp, R1 + R2)
            second = json.loads(run_badge("--history", str(hist)).stdout)
            self.assertEqual(second["message"], "75.0 · Adequate")


class TestAttestation(unittest.TestCase):
    def test_every_field_pinned(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1 + R2)
            r = run_badge("--history", str(hist), "--attestation")
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout)
            self.assertEqual(set(payload), ATTESTATION_KEYS)
            self.assertEqual(payload["kind"], "vibe-badge-attestation")
            self.assertIs(type(payload["schema"]), int)
            self.assertEqual(payload["schema"], 1)
            self.assertEqual(payload["scope"], "full")
            self.assertEqual(payload["run"], "r2")
            self.assertEqual(payload["mean_score"], 75.0)
            self.assertEqual(payload["band"], "Adequate")
            self.assertEqual(payload["files"], 2)
            entries = R1 + R2
            expected_runs = len(trend_engine.trajectory_from_entries(
                entries, "full", len(entries) + 1))
            self.assertEqual(payload["runs_observed"], expected_runs)
            self.assertEqual(payload["runs_observed"], 2)
            self.assertEqual(payload["history_sha256"],
                             hashlib.sha256(hist.read_bytes()).hexdigest())

    def test_deterministic_across_invocations(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1 + R2)
            a = run_badge("--history", str(hist), "--attestation")
            b = run_badge("--history", str(hist), "--attestation")
            self.assertEqual(a.stdout, b.stdout)
            self.assertTrue(a.stdout)


class TestRefusals(unittest.TestCase):
    def assert_refusal(self, r):
        self.assertEqual(r.returncode, 2)
        self.assertTrue(r.stderr.startswith("vibe-badge:"), r.stderr)
        self.assertEqual(r.stdout, "")

    def test_scope_empty_is_no_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1)
            r = run_badge("--history", str(hist), "--scope", "changed")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(json.loads(r.stdout)["message"], "no data")

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            path.write_text("{nope", encoding="utf-8")
            self.assert_refusal(run_badge("--history", str(path)))

    def test_non_contract_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            path.write_text('{"entries": []}', encoding="utf-8")
            self.assert_refusal(run_badge("--history", str(path)))

    def test_unreadable_history_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assert_refusal(run_badge("--history", tmp))

    def test_attestation_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_badge("--history", str(Path(tmp) / "absent.json"), "--attestation")
            self.assert_refusal(r)

    def test_attestation_scope_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1)
            r = run_badge("--history", str(hist), "--scope", "changed", "--attestation")
            self.assert_refusal(r)

    def test_empty_scope_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            hist = write_history(tmp, R1)
            self.assert_refusal(run_badge("--history", str(hist), "--scope", ""))


class TestEntriesFromText(unittest.TestCase):
    def test_list_container(self):
        self.assertEqual(trend_engine.entries_from_text(json.dumps(R1)), R1)

    def test_snapshots_container(self):
        raw = json.dumps({"snapshots": R1})
        self.assertEqual(trend_engine.entries_from_text(raw), R1)

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            trend_engine.entries_from_text("nope")
        with self.assertRaises(ValueError):
            trend_engine.entries_from_text('{"entries": []}')


class TestCli(unittest.TestCase):
    def test_help(self):
        r = run_badge("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("--history", r.stdout)

    def test_unknown_flag(self):
        self.assertEqual(run_badge("--nope").returncode, 2)

    def test_missing_history(self):
        self.assertEqual(run_badge().returncode, 2)


if __name__ == "__main__":
    unittest.main()
