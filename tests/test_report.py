#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The report surface (E6.3 / vibe-49): vendor integrity, the blob contract, the renderer's
offline single-file output, and the concurrency discipline.

The acceptance is "opens file:// with charts offline" and "no blob collision": CI proves the
structural halves — zero external references, the vendored bundle inlined, the blob embedded,
unique archives, atomic index — and the recorded in-session browser check proves the rendering
half (its evidence lives in the run folder and the PR test plan, not here).
"""

import base64
import hashlib
import json
import multiprocessing
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR = REPO_ROOT / "templates" / "report" / "vendor"
RENDERER = REPO_ROOT / "bin" / "vibe-report"
TEMPLATE = REPO_ROOT / "templates" / "report" / "single.html"


def full_blob():
    return {
        "schema": 1,
        "score": {"files": [{"path": "commands/a.md", "tier": "T2", "score": 90,
                             "band": "green", "verdict": "pass",
                             "findings": [{"rule": "R1", "check": "c", "line": 1, "penalty": -10}],
                             "advisories": [{"rule": "R18", "note": "n"}]}],
                  "run": {"files": 1, "total_penalty": -10, "considered_rows": 1, "skipped": []}},
        "check": {"mechanical": {"verdict": "clean", "issues": [
                      {"class": "orphan", "source": "scripts/x.py",
                       "detail": "zero inbound reference edges"}],
                  "checked": {"orphan": 1}},
                  "judgment": {"available": True, "status": "composed", "reason": None,
                               "data": {"verdict": "clean", "issues": [
                                   {"class": "orphan", "source": "scripts/x.py",
                                    "detail": "zero inbound reference edges"},
                                   {"class": "r51-drift", "detail": "verb drift",
                                    "sources": ["commands/a.md", "commands/b.md"]}],
                                        "checked": {"orphan": 1, "r51-drift": 1}}}},
        "vocab_drift": {"available": False, "reason": "corpus holds 3 artifacts (< 5)",
                        "candidates": [], "prose": None},
        "vocabulary": {"registry": {"scopes": [{"id": "operative", "description": "d",
                                                "paths": ["commands/**"]}],
                                    "verbs": {"operative": [{"canonical": "score",
                                                             "deprecated": [],
                                                             "output": "number",
                                                             "judgment": False,
                                                             "notes": "n"}]},
                                    "nouns": {"artifact_class": [{"canonical": "command",
                                                                  "deprecated": [],
                                                                  "definition": "d"}],
                                              "role_nouns": [{"canonical": "scorer",
                                                              "paired_verb": "score"}]}},
                       "extracted": {"terms": [{"term": "artifact", "count": 42}]}},
        "graph": {"nodes": [{"path": "commands/a.md", "kind": "command"},
                            {"path": "scripts/x.py", "kind": "script"}],
                  "edges": [{"source": "commands/a.md", "target": "scripts/x.py",
                             "kind": "command-script"}]},
        "history": {"status": "present",
                    "entries": [{"scope": "full", "score": 85, "band": "green",
                                 "total_penalty": -15, "file": "commands/a.md", "run": "r1"}],
                    "trajectory": [{"run": "r1", "mean_score": 85.0, "files": 1}]},
    }


def render(blob, out_dir, template=None):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(blob, fh)
        data = fh.name
    args = [sys.executable, str(RENDERER), "--data", data, "--out-dir", str(out_dir)]
    if template:
        args += ["--template", str(template)]
    r = subprocess.run(args, capture_output=True, text=True)
    os.unlink(data)
    return r


class TestVendorIntegrity(unittest.TestCase):
    def test_bundle_matches_vendored_record(self):
        recorded = re.search(r"sha256 \(this g6\.min\.js\)\*\*: `([0-9a-f]{64})`",
                             (VENDOR / "VENDORED.md").read_text())
        self.assertIsNotNone(recorded, "VENDORED.md records the sha256")
        actual = hashlib.sha256((VENDOR / "g6.min.js").read_bytes()).hexdigest()
        self.assertEqual(actual, recorded.group(1))
        self.assertIn("MIT", (VENDOR / "LICENSE").read_text()[:200])


class TestRendererDiscipline(unittest.TestCase):
    def test_isc_header_executable_stdlib(self):
        text = RENDERER.read_text(encoding="utf-8")
        self.assertIn("SPDX-License-Identifier: ISC", "\n".join(text.splitlines()[:3]))
        self.assertTrue(os.stat(RENDERER).st_mode & stat.S_IXUSR, "executable bit")
        for banned in ("import requests", "import yaml", "import numpy"):
            self.assertNotIn(banned, text)


class TestBlobValidation(unittest.TestCase):
    def _refused(self, blob, why):
        out = Path(tempfile.mkdtemp(prefix="report-refuse-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        r = render(blob, out)
        self.assertEqual(r.returncode, 2, why)
        self.assertEqual(list(out.iterdir()), [], "a refusal writes nothing")

    def test_valid_blob_renders(self):
        out = Path(tempfile.mkdtemp(prefix="report-ok-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        r = render(full_blob(), out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((out / "index.html").is_file())

    def test_refusals(self):
        b = full_blob(); b["schema"] = 2
        self._refused(b, "unknown schema")
        b = full_blob(); del b["graph"]
        self._refused(b, "missing key")
        b = full_blob(); b["score"]["files"][0]["score"] = "high"
        self._refused(b, "wrong type")
        b = full_blob()
        b["check"]["judgment"]["data"]["issues"][0]["sources"] = ["x"]
        self._refused(b, "mechanical issue carrying sources (cross-lane)")
        b = full_blob()
        b["check"]["judgment"]["data"]["issues"][1]["source"] = "y"
        self._refused(b, "judgment issue carrying source (cross-lane)")

    def test_honest_absences_render(self):
        out = Path(tempfile.mkdtemp(prefix="report-absent-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        b = full_blob()
        b["check"]["judgment"] = {"available": False, "status": "skipped",
                                  "reason": "no judgment input", "data": None}
        b["history"] = {"status": "missing", "entries": [], "trajectory": []}
        r = render(b, out)
        self.assertEqual(r.returncode, 0, r.stderr)
        html = (out / "index.html").read_text()
        self.assertIn("no judgment input", html)
        self.assertIn("missing", html)


class TestOfflineStructure(unittest.TestCase):
    def test_single_file_no_active_external_resource_attributes(self):
        """The structural gate: no ACTIVE external resource attributes (src/href to another
        origin). Inactive string constants inside the vendored minified bundle (icon-font URLs
        the report never dereferences) are outside this gate; the recorded browser evidence's
        zero-fetch observation covers the runtime half."""
        out = Path(tempfile.mkdtemp(prefix="report-offline-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        render(full_blob(), out)
        html = (out / "index.html").read_text()
        self.assertNotRegex(html, r'(?:src|href)\s*=\s*["\'](?:https?:)?//',
                            "no active external resource attributes")
        bundle_head = (VENDOR / "g6.min.js").read_text(encoding="utf-8")[:2000]
        self.assertIn(bundle_head, html, "the vendored bundle is inlined")
        self.assertIn('"schema": 1', html.replace("&quot;", '"'), "the blob is embedded")
        for view in ("vibe-score-view", "vibe-check-view", "vibe-vocab-view",
                     "vibe-graph-view", "vibe-history-view", "vibe-drift-view"):
            self.assertIn(view, html, view)

    def test_template_override(self):
        out = Path(tempfile.mkdtemp(prefix="report-tpl-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        alt = out / "alt.html"
        alt.write_text(TEMPLATE.read_text().replace("<title>", "<title>ALT "))
        r = render(full_blob(), out, template=alt)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ALT ", (out / "index.html").read_text())


def _surrogate(root, results, idx):
    scratch = tempfile.mkdtemp(prefix=f"report-scratch-{idx}-")
    fd, blob_path = tempfile.mkstemp(suffix=".json", dir=scratch)
    blob = full_blob()
    blob["score"]["files"][0]["score"] = 80 + idx
    with os.fdopen(fd, "w") as fh:
        json.dump(blob, fh)
    r = subprocess.run([sys.executable, str(RENDERER), "--data", blob_path,
                        "--out-dir", str(root)], capture_output=True, text=True)
    results[idx] = (r.returncode, blob_path)


class TestConcurrency(unittest.TestCase):
    def test_parallel_runs_no_collision(self):
        out = Path(tempfile.mkdtemp(prefix="report-conc-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        mgr = multiprocessing.Manager()
        results = mgr.dict()
        procs = [multiprocessing.Process(target=_surrogate, args=(out, results, i))
                 for i in (1, 2)]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        self.assertEqual({results[1][0], results[2][0]}, {0}, dict(results))
        self.assertNotEqual(results[1][1], results[2][1], "distinct mktemp blob paths")
        archives = sorted(out.glob("report-*.html"))
        self.assertEqual(len(archives), 2, "both archives exist")
        contents = [a.read_bytes() for a in archives]
        self.assertNotEqual(contents[0], contents[1], "distinct archive contents")
        index = (out / "index.html").read_bytes()
        self.assertIn(index, contents, "index byte-equals exactly one archive")
        residue = [p for p in out.iterdir()
                   if p.name not in {a.name for a in archives} and p.name != "index.html"]
        self.assertEqual(residue, [], "no staging residue")


class TestGraphLane(unittest.TestCase):
    """W2: --graph adds nodes/edges; flagless output byte-identical (goldens cover the repo)."""

    def test_synthetic_tree_all_kinds(self):
        root = Path(tempfile.mkdtemp(prefix="graph-kinds-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "commands" / "shared").mkdir(parents=True)
        (root / "agents").mkdir()
        (root / "skills" / "s").mkdir(parents=True)
        (root / "scripts").mkdir()
        (root / "hooks").mkdir()
        (root / "commands" / "go.md").write_text(
            '---\ndescription: "d"\n---\nUses shared/p.md and the helper agent.\n'
            '```bash\npython3 "${CLAUDE_PLUGIN_ROOT}/scripts/tool.py"\n```\n')
        (root / "commands" / "shared" / "p.md").write_text('---\ndescription: "d"\n---\nx\n')
        (root / "agents" / "helper.md").write_text(
            '---\ndescription: "d"\nskills:\n  - s\n---\nbody\n')
        (root / "skills" / "s" / "SKILL.md").write_text('---\nname: s\ndescription: d\n---\nx\n')
        (root / "scripts" / "tool.py").write_text("# SPDX-License-Identifier: ISC\n")
        (root / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"Stop": [
            {"type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/tool.py"}]}}))
        (root / "CLAUDE.md").write_text("- commands/go.md\n")
        r = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "check_engine.py"),
                            "--root", str(root), "--graph"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        kinds = {e["kind"] for e in out["graph"]["edges"]}
        self.assertEqual(kinds, {"command-script", "command-partial", "command-agent",
                                 "agent-skill", "hook-script", "claude-md-listing"})
        self.assertTrue(all(set(n) == {"path", "kind"} for n in out["graph"]["nodes"]))
        node_paths = {n["path"] for n in out["graph"]["nodes"]}
        for e in out["graph"]["edges"]:
            self.assertIn(e["source"], node_paths, "the emitted graph is closed")
            self.assertIn(e["target"], node_paths, "the emitted graph is closed")
        r2 = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "check_engine.py"),
                             "--root", str(root)], capture_output=True, text=True)
        self.assertNotIn("graph", json.loads(r2.stdout), "flagless output carries no graph key")
        # Deterministic order: a second --graph run is byte-identical.
        r3 = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "check_engine.py"),
                             "--root", str(root), "--graph"], capture_output=True, text=True)
        self.assertEqual(r.stdout, r3.stdout)


class TestReadOnlyTrajectory(unittest.TestCase):
    """W3: trajectory_from_entries == the CLI trajectory minus the current point; no append."""

    def test_equivalence_minus_current(self):
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import trend_engine
        entries = json.loads(
            (REPO_ROOT / "tests" / "fixtures" / "trend" / "history-list.json").read_text())
        stored = trend_engine.trajectory_from_entries(entries, "full", 10)
        score_json = json.loads(
            (REPO_ROOT / "tests" / "fixtures" / "trend" / "score-current.json").read_text())
        files, cli_traj, _ = trend_engine.compute(entries, "full", score_json["files"],
                                                  "r2", 10)
        self.assertEqual(stored, cli_traj[:-1],
                         "the stored trajectory is the CLI's minus the current-run point")

    def _history_blob_section(self, hist_path):
        """The command doc's deterministic history-assembly step, as a testable function."""
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import importlib, trend_engine
        importlib.reload(trend_engine)
        if not hist_path.is_file():
            return {"status": "missing", "entries": [], "trajectory": []}
        try:
            entries, _ = trend_engine._normalize(
                json.loads(hist_path.read_bytes().decode("utf-8")))
        except (json.JSONDecodeError, ValueError):
            return {"status": "malformed", "entries": [], "trajectory": []}
        score_entries = [e for e in entries if trend_engine._is_score_entry(e)]
        return {"status": "present", "entries": score_entries,
                "trajectory": trend_engine.trajectory_from_entries(entries, "full", 10)}

    def test_full_report_pass_leaves_history_bytes(self):
        cases = [("history-list.json", "present"), ("history-dict.json", "present"),
                 (None, "missing"), ("MALFORMED", "malformed")]
        for fixture, want_status in cases:
            ws = Path(tempfile.mkdtemp(prefix="report-hist-"))
            self.addCleanup(shutil.rmtree, ws, ignore_errors=True)
            hist = ws / "vibe-history.json"
            src = None
            if fixture == "MALFORMED":
                src = b"{not json"
                hist.write_bytes(src)
            elif fixture:
                src = (REPO_ROOT / "tests" / "fixtures" / "trend" / fixture).read_bytes()
                hist.write_bytes(src)
            blob = full_blob()
            blob["history"] = self._history_blob_section(hist)
            self.assertEqual(blob["history"]["status"], want_status, fixture)
            out = ws / "reports"
            r = render(blob, out)
            self.assertEqual(r.returncode, 0, (fixture, r.stderr))
            self.assertTrue((out / "index.html").is_file())
            if src is not None:
                self.assertEqual(hist.read_bytes(), src,
                                 f"{fixture}: the full assembly->render pass reads only")
            else:
                self.assertFalse(hist.exists(), "a missing history stays missing")


class TestVocabGraphMapping(unittest.TestCase):
    """F2 closure: the noun-verb map's nodes and edges are deterministic Python data."""

    def test_counts_and_paired_verb_edges(self):
        from importlib.machinery import SourceFileLoader
        mod = SourceFileLoader("vibe_report", str(REPO_ROOT / "bin" / "vibe-report")).load_module()
        vocab = full_blob()["vocabulary"]
        data = mod.vocab_graph_data(vocab)
        verb_nodes = [n for n in data["nodes"] if n["group"] == "verb"]
        noun_nodes = [n for n in data["nodes"] if n["group"] != "verb"]
        self.assertEqual(len(verb_nodes), 1)       # operative:score
        self.assertEqual(len(noun_nodes), 2)       # artifact_class:command + role_nouns:scorer
        self.assertEqual(data["edges"],
                         [{"source": "noun:role_nouns:scorer",
                           "target": "verb:operative:score"}],
                         "the role noun's paired_verb is the registry's one cross-reference")
        run2 = mod.vocab_graph_data(vocab)
        self.assertEqual(data, run2, "deterministic")


class TestValidatorRefusalMatrix(unittest.TestCase):
    """F1 closure: the per-field refusal matrix beyond the earlier cases."""

    def _refused(self, mutate, why):
        b = full_blob()
        mutate(b)
        out = Path(tempfile.mkdtemp(prefix="report-matrix-"))
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        r = render(b, out)
        self.assertEqual(r.returncode, 2, why)
        self.assertEqual(list(out.iterdir()), [], why)

    def test_matrix(self):
        cases = [
            (lambda b: b.update(schema=True), "bool schema"),
            (lambda b: b["score"]["run"]["skipped"].append(7), "non-str skipped"),
            (lambda b: b["check"]["judgment"].pop("reason"), "missing reason"),
            (lambda b: b["check"]["judgment"].pop("data"), "missing data"),
            (lambda b: b["check"]["judgment"].update(available=False),
             "composed but unavailable (invariant)"),
            (lambda b: b["check"]["judgment"].update(status="skipped"),
             "skipped with data present (invariant)"),
            (lambda b: b["vocab_drift"]["candidates"].append(
                {"terms": [1], "rationale": "r"}), "non-str drift term"),
            (lambda b: b["vocab_drift"].pop("reason"), "missing drift reason"),
            (lambda b: b["vocabulary"]["registry"]["scopes"][0]["paths"].append(3),
             "non-str scope path"),
            (lambda b: b["vocabulary"]["registry"]["verbs"]["operative"][0]
                ["deprecated"].append(9), "non-str deprecated"),
            (lambda b: b["history"]["trajectory"][0].update(mean_score=85),
             "int mean_score"),
            (lambda b: b["history"].update(status="missing"),
             "missing status with payload present"),
            (lambda b: b.update(check=[1, 2]), "container of the wrong type -> BlobError not TypeError"),
        ]
        for mutate, why in cases:
            self._refused(mutate, why)
