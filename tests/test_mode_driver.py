#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The operator-tier mode driver (vibe-135): the five modes' bookkeeping — file and state
operations — driven deterministically against fixture run folders, with every behavior
read from `operational-modes.md`'s marker-tagged declaration blocks at runtime.

**This does not establish that a fresh reading of the markdown reproduces the goldens**
(`tests/test_loop_bounds.py:342` states why that guarantee is unreachable and this suite
inherits that scope honestly): the nine steps' content stays golden-recorded; what is
driven here is the mode wrapper around them.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DRIVER = REPO_ROOT / "scripts" / "issue2pr_mode_driver.py"
REFERENCE = REPO_ROOT / "skills" / "issue2pr" / "references" / "operational-modes.md"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "issue2pr" / "mode-driver"
ENTRY = REPO_ROOT / "scripts" / "manifest_entry.py"

MARKERS = ("run-status-enum", "loop-exit-to-status", "watcher-exit-actions",
           "chain-operations", "iterate-operations", "resume-operations",
           "list-operations", "manifest-operations")


def load_block(text, marker):
    m = re.search(rf"<!-- {re.escape(marker)} -->\n```json\n(.*?)\n```", text, re.S)
    return json.loads(m.group(1)) if m else None


def edit_reference(mutate):
    """A temp copy of the shipped reference with `mutate(blocks)` applied; returns its
    path. `blocks` is marker -> parsed JSON; a mutated block is re-serialized in place,
    a block set to None is removed entirely."""
    text = REFERENCE.read_text(encoding="utf-8")
    blocks = {m: load_block(text, m) for m in MARKERS}
    mutate(blocks)
    for marker in MARKERS:
        pattern = rf"<!-- {re.escape(marker)} -->\n```json\n.*?\n```"
        if blocks.get(marker) is None:
            text = re.sub(pattern, f"<!-- {marker} removed -->", text, flags=re.S)
        else:
            new = (f"<!-- {marker} -->\n```json\n"
                   + json.dumps(blocks[marker], indent=2, ensure_ascii=False) + "\n```")
            text = re.sub(pattern, lambda _m: new, text, flags=re.S)
    out = Path(tempfile.mkdtemp(prefix="modes-ref-")) / "operational-modes.md"
    out.write_text(text, encoding="utf-8")
    return out


def tree_hash(root):
    """Relative paths AND bytes: an empty file or a path-only write changes the hash."""
    h = hashlib.sha256()
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


class DriverCase(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="mode-driver-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def copy_fixture(self, name):
        dst = Path(tempfile.mkdtemp(dir=self.work, prefix="fx-")) / name
        shutil.copytree(FIXTURES / name, dst)
        return dst

    def runs_root_with(self, *names):
        root = Path(tempfile.mkdtemp(dir=self.work, prefix="runs-"))
        for name in names:
            shutil.copytree(FIXTURES / name, root / name)
        return root

    def drive(self, *args, reference=None):
        cmd = [sys.executable, str(DRIVER), *args]
        if reference is not None:
            cmd += ["--reference", str(reference)]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestIterate(DriverCase):
    def test_round_trip(self):
        root = self.runs_root_with("terminal-run")
        run = root / "terminal-run"
        meta_before = (run / "00-meta.json").read_bytes()
        r = self.drive("iterate", "terminal-run", "--runs-root", str(root),
                       "--max-review-rounds", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((run / "round-2").is_dir(), "round-<N+1> must be created")
        state = json.loads((run / "state.json").read_text())
        self.assertEqual(state["max_review_rounds_overrides"], {"2": 3})
        self.assertEqual(state["status"], "in_progress")
        self.assertEqual(state["current_round"], 2)
        self.assertEqual((run / "00-meta.json").read_bytes(), meta_before,
                         "00-meta.json is never rewritten")

    def test_refuses_non_terminal(self):
        root = self.runs_root_with("in-progress-run-full")
        r = self.drive("iterate", "in-progress-run-full", "--runs-root", str(root))
        self.assertEqual(r.returncode, 2)
        self.assertIn("resume", r.stderr, "the declared redirect names resume")

    def test_cap_flag_ignored_with_notice_under_none(self):
        root = self.runs_root_with("terminal-run")
        run = root / "terminal-run"
        state = json.loads((run / "state.json").read_text())
        state["review_mode"] = "none"
        (run / "state.json").write_text(json.dumps(state, indent=2) + "\n")
        r = self.drive("iterate", "terminal-run", "--runs-root", str(root),
                       "--max-review-rounds", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ignored", (r.stdout + r.stderr).lower())
        after = json.loads((run / "state.json").read_text())
        self.assertEqual(after["max_review_rounds_overrides"], {},
                         "an ignored flag writes no override")


class TestResume(DriverCase):
    CASES = {"in-progress-run-none": 4, "in-progress-run-single": 5,
             "in-progress-run-full": 5}

    def test_next_step_per_mode_and_writes_nothing(self):
        for name, expected in self.CASES.items():
            with self.subTest(run=name):
                root = self.runs_root_with(name)
                before = tree_hash(root)
                r = self.drive("resume", name, "--runs-root", str(root))
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(f"next step: {expected}", r.stdout)
                self.assertEqual(tree_hash(root), before, "resume writes nothing")

    def test_refuses_terminal(self):
        root = self.runs_root_with("terminal-run")
        r = self.drive("resume", "terminal-run", "--runs-root", str(root))
        self.assertEqual(r.returncode, 2)
        self.assertIn("iterate", r.stderr, "the declared redirect names iterate")


def set_touch_order(root, newest_to_oldest):
    """Deterministic last-touched times — git checkouts and copytree both reset dir
    mtimes, so ordering must be pinned by the test, never inherited (the CI lesson)."""
    base = 1754300000
    for offset, name in enumerate(newest_to_oldest):
        os.utime(Path(root) / name, (base - offset * 1000, base - offset * 1000))


class TestList(DriverCase):
    def test_columns_order_and_exclusion(self):
        root = self.runs_root_with("underscore-suite") / "underscore-suite"
        set_touch_order(root, ["run-a", "run-b"])
        before = tree_hash(root)
        r = self.drive("list", "--runs-root", str(root))
        self.assertEqual(r.returncode, 0, r.stderr)
        ref = load_block(REFERENCE.read_text(encoding="utf-8"), "list-operations")
        for column in ref["columns"]:
            self.assertIn(column, r.stdout, f"declared column {column!r} missing")
        lines = [l for l in r.stdout.splitlines()[1:] if l.startswith("run-")]
        self.assertEqual([l.split()[0] for l in lines], ["run-a", "run-b"],
                         "newest-first by last-touched")
        self.assertNotIn("_chains", r.stdout)
        self.assertNotIn("_archived", r.stdout)
        self.assertEqual(tree_hash(root), before, "list writes nothing")


class TestChain(DriverCase):
    def chain_file(self):
        d = self.copy_fixture("chain-two-link")
        return d / "chain.json", d / "timeline.md"

    def load(self, path):
        return json.loads(path.read_text())

    def drive_chain(self, chain, *args, reference=None):
        return self.drive("chain", "--chain-file", str(chain), *args,
                          reference=reference)

    def test_exit0_verified_merge_advances(self):
        chain, timeline = self.chain_file()
        r = self.drive_chain(chain, "--watcher-exit", "0",
                             "--merge-commit", "abc1234", "--ancestor-verified", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load(chain)
        self.assertEqual(data["links"][0]["status"], "merged")
        self.assertEqual(data["links"][1]["status"], "running")
        self.assertEqual(data["current_index"], 1)
        text = timeline.read_text()
        self.assertLess(text.index("merged"), text.index("running"),
                        "timeline entries are ordered")

    def test_exit0_unverified_refuses_and_writes_nothing(self):
        chain, _ = self.chain_file()
        before = tree_hash(chain.parent)
        r = self.drive_chain(chain, "--watcher-exit", "0",
                             "--merge-commit", "abc1234", "--ancestor-verified", "false")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(tree_hash(chain.parent), before)

    def test_exit0_on_final_link_completes_the_chain(self):
        chain, _ = self.chain_file()
        data = self.load(chain)
        data["links"] = [data["links"][0]]
        chain.write_text(json.dumps(data, indent=2) + "\n")
        r = self.drive_chain(chain, "--watcher-exit", "0",
                             "--merge-commit", "abc1234", "--ancestor-verified", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.load(chain)["status"], "complete")

    def test_exit2_closes_and_pauses(self):
        chain, _ = self.chain_file()
        r = self.drive_chain(chain, "--watcher-exit", "2")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load(chain)
        self.assertEqual(data["links"][0]["status"], "closed_unmerged")
        self.assertEqual(data["status"], "paused")
        self.assertEqual(data["links"][1]["status"], "pending", "no advance past a pause")

    def test_exit3_classifications(self):
        # The declared semantics: the 1-based ordinal about to run; it runs while
        # round <= cap. Boundary battery: cap-1, cap, cap+1, and the cap-1 chain.
        cases = {
            ("actionable", "2"): ("iterating", None, "babysit-start"),   # cap-1 < cap
            ("actionable", "3"): ("iterating", None, "babysit-start"),   # at cap: runs
            ("actionable", "4"): ("waiting_merge", "paused", None),      # past cap
            ("question", "1"): ("waiting_merge", None, "notify"),
        }
        for (classification, rnd), (link_status, chain_status, report) in cases.items():
            with self.subTest(classification=classification, round=rnd):
                chain, _ = self.chain_file()
                before = tree_hash(chain.parent)
                r = self.drive_chain(chain, "--watcher-exit", "3",
                                     "--classification", classification,
                                     "--babysit-round", rnd, "--babysit-cap", "3")
                self.assertEqual(r.returncode, 0, r.stderr)
                data = self.load(chain)
                self.assertEqual(data["links"][0]["status"], link_status)
                if chain_status:
                    self.assertEqual(data["status"], chain_status)
                if report:
                    self.assertIn(report, r.stdout)
                if classification == "question":
                    self.assertEqual(tree_hash(chain.parent), before,
                                     "a question is report-only")

    def test_exit3_cap_one_boundary(self):
        for rnd, link_status, chain_status in (("1", "iterating", None),
                                                ("2", "waiting_merge", "paused")):
            with self.subTest(round=rnd):
                chain, _ = self.chain_file()
                r = self.drive_chain(chain, "--watcher-exit", "3",
                                     "--classification", "actionable",
                                     "--babysit-round", rnd, "--babysit-cap", "1")
                self.assertEqual(r.returncode, 0, r.stderr)
                data = self.load(chain)
                self.assertEqual(data["links"][0]["status"], link_status)
                if chain_status:
                    self.assertEqual(data["status"], chain_status)

    def test_exit3_non_integer_inputs_refused(self):
        chain, _ = self.chain_file()
        r = self.drive_chain(chain, "--watcher-exit", "3",
                             "--classification", "actionable",
                             "--babysit-round", "soon", "--babysit-cap", "3")
        self.assertEqual(r.returncode, 2)

    def test_exit3_status_noise_advances_cursor_only(self):
        chain, _ = self.chain_file()
        r = self.drive_chain(chain, "--watcher-exit", "3",
                             "--classification", "status-noise",
                             "--babysit-round", "1", "--babysit-cap", "3",
                             "--cursor", "2026-08-02T00:00:00Z")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load(chain)
        self.assertEqual(data["links"][0]["status"], "waiting_merge")
        self.assertEqual(data["links"][0]["cursor"], "2026-08-02T00:00:00Z")

    def test_exit4_notes_failing_check_in_timeline(self):
        chain, timeline = self.chain_file()
        r = self.drive_chain(chain, "--watcher-exit", "4",
                             "--classification", "actionable",
                             "--babysit-round", "1", "--babysit-cap", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("failing-check", timeline.read_text())

    def test_babysit_finish_both_outcomes(self):
        for outcome, link_status, chain_status in (("pushed", "waiting_merge", None),
                                                    ("failed", "failed", "paused")):
            with self.subTest(outcome=outcome):
                chain, _ = self.chain_file()
                data = self.load(chain)
                data["links"][0]["status"] = "iterating"
                chain.write_text(json.dumps(data, indent=2) + "\n")
                r = self.drive_chain(chain, "--event", "babysit-finish",
                                     "--outcome", outcome)
                self.assertEqual(r.returncode, 0, r.stderr)
                data = self.load(chain)
                self.assertEqual(data["links"][0]["status"], link_status)
                if chain_status:
                    self.assertEqual(data["status"], chain_status)

    def test_link_lifecycle_events(self):
        chain, _ = self.chain_file()
        data = self.load(chain)
        data["links"][0]["status"] = "running"
        chain.write_text(json.dumps(data, indent=2) + "\n")
        r = self.drive_chain(chain, "--event", "link-run-outcome",
                             "--status", "pr_opened", "--pr", "12")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.load(chain)["links"][0]["status"], "waiting_merge")

        data = self.load(chain)
        data["links"][0]["status"] = "running"
        chain.write_text(json.dumps(data, indent=2) + "\n")
        r = self.drive_chain(chain, "--event", "link-run-outcome", "--status", "failed")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load(chain)
        self.assertEqual(data["links"][0]["status"], "failed")
        self.assertEqual(data["status"], "paused")

    def test_skip_advances_and_completes_on_final(self):
        chain, _ = self.chain_file()
        r = self.drive_chain(chain, "--event", "skip")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load(chain)
        self.assertEqual(data["links"][0]["status"], "skipped")
        self.assertEqual(data["links"][1]["status"], "running")
        r = self.drive_chain(chain, "--event", "link-run-outcome",
                             "--status", "pr_opened", "--pr", "13")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.drive_chain(chain, "--event", "skip")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.load(chain)["status"], "complete")

    def test_exit7_squash_report_then_merge_semantics(self):
        chain, _ = self.chain_file()
        r = self.drive_chain(chain, "--watcher-exit", "7",
                             "--merge-commit", "abc1234", "--ancestor-verified", "true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("squash", r.stdout, "the pre-report action is printed")
        data = self.load(chain)
        self.assertEqual(data["links"][0]["status"], "merged")
        self.assertEqual(data["links"][1]["status"], "running")

    def test_link_start_event(self):
        chain, _ = self.chain_file()
        data = self.load(chain)
        data["links"][0]["status"] = "pending"
        chain.write_text(json.dumps(data, indent=2) + "\n")
        r = self.drive_chain(chain, "--event", "link-start")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.load(chain)["links"][0]["status"], "running")

    def test_skip_from_running(self):
        chain, _ = self.chain_file()
        data = self.load(chain)
        data["links"][0]["status"] = "running"
        chain.write_text(json.dumps(data, indent=2) + "\n")
        r = self.drive_chain(chain, "--event", "skip")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.load(chain)
        self.assertEqual(data["links"][0]["status"], "skipped")
        self.assertEqual(data["links"][1]["status"], "running",
                         "skip is pause-exempt and advances")

    def test_report_only_exits(self):
        for code in ("5",):
            with self.subTest(code=code):
                chain, _ = self.chain_file()
                before = tree_hash(chain.parent)
                r = self.drive_chain(chain, "--watcher-exit", code)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(tree_hash(chain.parent), before)
                self.assertTrue(r.stdout.strip(), "a report-only exit still reports")

    def test_pausing_exits_and_unmapped(self):
        for code in ("6", "1", "42"):
            with self.subTest(code=code):
                chain, _ = self.chain_file()
                r = self.drive_chain(chain, "--watcher-exit", code)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(self.load(chain)["status"], "paused")

    def test_every_written_status_is_declared(self):
        ref = load_block(REFERENCE.read_text(encoding="utf-8"), "chain-operations")
        vocab = set(ref["link_statuses"])
        chain, _ = self.chain_file()
        self.drive_chain(chain, "--watcher-exit", "0",
                         "--merge-commit", "abc", "--ancestor-verified", "true")
        for link in self.load(chain)["links"]:
            self.assertIn(link["status"], vocab)


class TestManifest(DriverCase):
    def test_creates_the_named_run_folder_via_the_entry_executable(self):
        root = self.work / "runs"
        root.mkdir()
        r = self.drive("manifest", "--manifest",
                       str(FIXTURES / "manifest-mode.json"),
                       "--profile", str(REPO_ROOT / "tests" / "fixtures" / "issue2pr"
                                        / "profiles" / "fixture.md"),
                       "--runs-root", str(root))
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        run = root / "fx-9-manifest-mode-case"
        self.assertTrue(run.is_dir(), "the run folder the manifest names")
        state = json.loads((run / "state.json").read_text())
        self.assertEqual(state["status"], "in_progress")
        self.assertTrue((run / "00-meta.json").is_file())
        self.assertIn("manifest_entry", r.stdout,
                      "the declared validate_via executable ran")

    def test_escaping_run_folder_refused(self):
        root = self.work / "runs"
        root.mkdir()
        bad = json.loads((FIXTURES / "manifest-mode.json").read_text())
        bad["run_folder"] = "../outside-run"
        bad_path = self.work / "bad-manifest.json"
        bad_path.write_text(json.dumps(bad, indent=2) + "\n")
        r = self.drive("manifest", "--manifest", str(bad_path),
                       "--profile", str(REPO_ROOT / "tests" / "fixtures" / "issue2pr"
                                        / "profiles" / "fixture.md"),
                       "--runs-root", str(root))
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.work / "outside-run").exists())


class TestConsumption(DriverCase):
    """The driver derives behavior from the declarations — proven by removal (fail
    naming the gap, for EVERY key, probed by the mode that consumes it) and by mutation
    (behavior follows the change), parameterized from the blocks themselves so a future
    key joins the matrix without a test edit."""

    def keys_for(self, marker):
        block = load_block(REFERENCE.read_text(encoding="utf-8"), marker)
        return sorted(block.keys())

    def probe(self, marker, key, ref):
        """Drive the mode that consumes (marker, key); every probe must hit the gap."""
        if marker == "chain-operations":
            chain = self.copy_fixture("chain-two-link") / "chain.json"
            if key == "babysit_round_semantics":
                return self.drive("chain", "--chain-file", str(chain),
                                  "--watcher-exit", "3", "--classification",
                                  "actionable", "--babysit-round", "1",
                                  "--babysit-cap", "3", reference=ref)
            if key == "events":
                return self.drive("chain", "--chain-file", str(chain),
                                  "--event", "skip", reference=ref)
            return self.drive("chain", "--chain-file", str(chain),
                              "--watcher-exit", "2", reference=ref)
        if marker == "manifest-operations":
            root = Path(tempfile.mkdtemp(dir=self.work)) / "runs"
            root.mkdir()
            return self.drive("manifest", "--manifest",
                              str(FIXTURES / "manifest-mode.json"),
                              "--profile", str(REPO_ROOT / "tests" / "fixtures" /
                                               "issue2pr" / "profiles" / "fixture.md"),
                              "--runs-root", str(root), reference=ref)
        if marker == "iterate-operations":
            root = self.runs_root_with("terminal-run")
            return self.drive("iterate", "terminal-run", "--runs-root", str(root),
                              "--max-review-rounds", "3", reference=ref)
        if marker == "list-operations":
            root = self.runs_root_with("underscore-suite") / "underscore-suite"
            return self.drive("list", "--runs-root", str(root), reference=ref)
        root = self.runs_root_with("in-progress-run-none")
        return self.drive("resume", "in-progress-run-none", "--runs-root", str(root),
                          reference=ref)

    def test_removed_key_fails_naming_marker_and_key(self):
        markers = ("iterate-operations", "resume-operations", "list-operations",
                   "manifest-operations", "chain-operations", "run-status-enum")
        for marker in markers:
            for key in self.keys_for(marker):
                with self.subTest(marker=marker, key=key):
                    def mutate(blocks, marker=marker, key=key):
                        del blocks[marker][key]
                    ref = edit_reference(mutate)
                    r = self.probe(marker, key, ref)
                    self.assertEqual(r.returncode, 4,
                                     f"{marker}.{key} must be load-bearing for its "
                                     f"probe: exit {r.returncode}\n{r.stderr}")
                    self.assertIn(marker, r.stderr)
                    self.assertIn(key, r.stderr)

    def test_watcher_code_removal_is_declared_catch_all_behavior(self):
        """Removing a non-catch-all code falls to the declared catch-all (paused) —
        behavior, not a gap; removing the catch-all itself IS the gap."""
        def drop_two(blocks):
            del blocks["watcher-exit-actions"]["2"]
        chain = self.copy_fixture("chain-two-link") / "chain.json"
        r = self.drive("chain", "--chain-file", str(chain), "--watcher-exit", "2",
                       reference=edit_reference(drop_two))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(chain.read_text())["status"], "paused")

        def drop_catch_all(blocks):
            del blocks["watcher-exit-actions"]["1"]
        chain = self.copy_fixture("chain-two-link") / "chain.json"
        r = self.drive("chain", "--chain-file", str(chain), "--watcher-exit", "42",
                       reference=edit_reference(drop_catch_all))
        self.assertEqual(r.returncode, 4)
        self.assertIn("watcher-exit-actions", r.stderr)

    def test_behavior_follows_mutation(self):
        with self.subTest(mutation="iterate target status"):
            def mutate(blocks):
                blocks["iterate-operations"]["transition"]["to"] = "quota_paused"
            ref = edit_reference(mutate)
            root = self.runs_root_with("terminal-run")
            r = self.drive("iterate", "terminal-run", "--runs-root", str(root),
                           reference=ref)
            self.assertEqual(r.returncode, 0, r.stderr)
            state = json.loads((root / "terminal-run" / "state.json").read_text())
            self.assertEqual(state["status"], "quota_paused")

        with self.subTest(mutation="iterate override key"):
            def mutate(blocks):
                blocks["iterate-operations"]["override_records"]["max_review_rounds"] = \
                    "renamed_overrides"
            ref = edit_reference(mutate)
            root = self.runs_root_with("terminal-run")
            r = self.drive("iterate", "terminal-run", "--runs-root", str(root),
                           "--max-review-rounds", "4", reference=ref)
            self.assertEqual(r.returncode, 0, r.stderr)
            state = json.loads((root / "terminal-run" / "state.json").read_text())
            self.assertEqual(state["renamed_overrides"], {"2": 4})

        for mode in ("none", "single", "full"):
            with self.subTest(mutation=f"resume sequence ({mode})"):
                def mutate(blocks, mode=mode):
                    blocks["resume-operations"]["sequences"][mode] = [1, 8]
                ref = edit_reference(mutate)
                root = self.runs_root_with(f"in-progress-run-{mode}")
                r = self.drive("resume", f"in-progress-run-{mode}",
                               "--runs-root", str(root), reference=ref)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("next step: 8", r.stdout)

        with self.subTest(mutation="list order"):
            def mutate(blocks):
                blocks["list-operations"]["order"] = "last-touched, oldest first"
            ref = edit_reference(mutate)
            root = self.runs_root_with("underscore-suite") / "underscore-suite"
            set_touch_order(root, ["run-a", "run-b"])
            r = self.drive("list", "--runs-root", str(root), reference=ref)
            lines = [l for l in r.stdout.splitlines()[1:] if l.startswith("run-")]
            self.assertEqual([l.split()[0] for l in lines], ["run-b", "run-a"])

        with self.subTest(mutation="list exclude prefix"):
            def mutate(blocks):
                blocks["list-operations"]["exclude_prefix"] = "run-a"
            ref = edit_reference(mutate)
            root = self.runs_root_with("underscore-suite") / "underscore-suite"
            r = self.drive("list", "--runs-root", str(root), reference=ref)
            self.assertNotIn("run-a", r.stdout)

        with self.subTest(mutation="list columns subset"):
            def mutate(blocks):
                blocks["list-operations"]["columns"] = ["run-id", "status"]
            ref = edit_reference(mutate)
            root = self.runs_root_with("underscore-suite") / "underscore-suite"
            set_touch_order(root, ["run-a", "run-b"])
            r = self.drive("list", "--runs-root", str(root), reference=ref)
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = [l for l in r.stdout.splitlines()[1:] if l.strip()]
            for row in rows:
                self.assertEqual(len(row.split(" | ")), 2,
                                 "row cells follow the declared column set")

        with self.subTest(mutation="manifest creates without state.json"):
            def mutate(blocks):
                blocks["manifest-operations"]["creates"] = ["run_folder", "00-meta.json"]
            ref = edit_reference(mutate)
            root = Path(tempfile.mkdtemp(dir=self.work)) / "runs"
            root.mkdir()
            r = self.drive("manifest", "--manifest",
                           str(FIXTURES / "manifest-mode.json"),
                           "--profile", str(REPO_ROOT / "tests" / "fixtures" /
                                            "issue2pr" / "profiles" / "fixture.md"),
                           "--runs-root", str(root), reference=ref)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            run = root / "fx-9-manifest-mode-case"
            self.assertTrue((run / "00-meta.json").is_file())
            self.assertFalse((run / "state.json").exists(),
                             "an artifact absent from the declared creates is not written")

        with self.subTest(mutation="manifest initial_status"):
            def mutate(blocks):
                blocks["manifest-operations"]["initial_status"] = "quota_paused"
            ref = edit_reference(mutate)
            root = self.work / "runs3"
            root.mkdir()
            r = self.drive("manifest", "--manifest",
                           str(FIXTURES / "manifest-mode.json"),
                           "--profile", str(REPO_ROOT / "tests" / "fixtures" /
                                            "issue2pr" / "profiles" / "fixture.md"),
                           "--runs-root", str(root), reference=ref)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            state = json.loads((root / "fx-9-manifest-mode-case" / "state.json").read_text())
            self.assertEqual(state["status"], "quota_paused")

        ref_text = REFERENCE.read_text(encoding="utf-8")
        watcher = load_block(ref_text, "watcher-exit-actions")
        for code in sorted(watcher):
            if code in ("0", "3", "4", "7"):
                continue  # input-carrying effects; remapped via their own paths above
            with self.subTest(mutation=f"chain exit {code} remapped"):
                def mutate(blocks, code=code):
                    blocks["watcher-exit-actions"][code]["effect"] = {
                        "edge": {"from": "waiting_merge", "to": "skipped"}}
                ref = edit_reference(mutate)
                chain = self.copy_fixture("chain-two-link") / "chain.json"
                r = self.drive("chain", "--chain-file", str(chain),
                               "--watcher-exit", code, reference=ref)
                self.assertEqual(r.returncode, 0, r.stderr)
                data = json.loads(chain.read_text())
                self.assertEqual(data["links"][0]["status"], "skipped")

        with self.subTest(mutation="edge removed from the legal set"):
            def mutate(blocks):
                blocks["chain-operations"]["link_edges"]["waiting_merge"] = ["merged"]
            ref = edit_reference(mutate)
            chain = self.copy_fixture("chain-two-link") / "chain.json"
            before = tree_hash(chain.parent)
            r = self.drive("chain", "--chain-file", str(chain),
                           "--watcher-exit", "2", reference=ref)
            self.assertEqual(r.returncode, 2, "a formerly-legal transition now refuses")
            self.assertEqual(tree_hash(chain.parent), before)


class TestDeclarationCoherence(unittest.TestCase):
    def test_watcher_effects_name_only_declared_statuses(self):
        text = REFERENCE.read_text(encoding="utf-8")
        chain = load_block(text, "chain-operations")
        watcher = load_block(text, "watcher-exit-actions")
        link_vocab = set(chain["link_statuses"])
        chain_vocab = set(chain["chain_statuses"]["non_terminal"]
                          + chain["chain_statuses"]["terminal"])

        def walk(effect):
            if not isinstance(effect, dict):
                return
            if "edge" in effect:
                self.assertIn(effect["edge"]["from"], link_vocab)
                self.assertIn(effect["edge"]["to"], link_vocab)
                self.assertIn(effect["edge"]["to"],
                              set(chain["link_edges"].get(effect["edge"]["from"], [])),
                              f"undeclared edge {effect['edge']}")
            if "chain" in effect:
                self.assertIn(effect["chain"], chain_vocab)
            for v in effect.values():
                if isinstance(v, dict):
                    walk(v)
        for code, record in watcher.items():
            with self.subTest(exit=code):
                walk(record["effect"])

    def test_declared_edges_equal_event_produced_edges(self):
        """Closure: every declared link edge has a producer, and every produced edge is
        declared — the orphan-edge class the Step-8 review found cannot recur silently."""
        text = REFERENCE.read_text(encoding="utf-8")
        chain = load_block(text, "chain-operations")
        watcher = load_block(text, "watcher-exit-actions")
        produced = set()

        def collect(effect):
            if not isinstance(effect, dict):
                return
            if "edge" in effect:
                produced.add((effect["edge"]["from"], effect["edge"]["to"]))
            for value in effect.values():
                if isinstance(value, dict):
                    collect(value)

        for record in watcher.values():
            collect(record["effect"])
        for name, event in chain["events"].items():
            if "edge" in event:
                produced.add((event["edge"]["from"], event["edge"]["to"]))
            for sub in (event.get("effects") or {}).values():
                collect(sub)
            if name == "skip":
                for frm in event["from_any_of"]:
                    produced.add((frm, event["to"]))
            if name == "advance":
                produced.add((event["next_link"]["from"], event["next_link"]["to"]))
        declared = {(frm, to) for frm, tos in chain["link_edges"].items()
                    for to in tos}
        self.assertEqual(declared, produced,
                         "declared edges and event-produced edges must be one set")

    def test_docstrings_state_the_fresh_reading_limit(self):
        for path in (Path(__file__), DRIVER):
            with self.subTest(file=path.name):
                self.assertIn("does not establish that a fresh reading",
                              path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
