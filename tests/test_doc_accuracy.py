#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""E7.3 (vibe-55): the doc set's counts-vs-disk acceptance.

Every count a document states is a claim this file holds true THREE ways — the README's prose
number, the manifest's registration list, and the files actually on disk must agree (A-4:
manifest-only comparison would be transitively right but the acceptance says disk). The
migration table's `new` side must resolve to a registered command or a user-invocable skill;
the old side is history no test can check, so it rests on review.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"
PRIVACY = REPO_ROOT / "PRIVACY.md"


def manifest():
    return json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())


class DocsExist(unittest.TestCase):
    def test_all_three_exist_and_are_substantial(self):
        for doc in (README, CLAUDE, PRIVACY):
            with self.subTest(doc=doc.name):
                self.assertTrue(doc.is_file(), f"{doc.name} missing")
                self.assertGreater(len(doc.read_text(encoding="utf-8")), 500)


class ReadmeCounts(unittest.TestCase):
    def test_readme_counts_equal_manifest_and_disk(self):
        # RAW disk inventories compared to the manifest inventories (F5): registration
        # filtering on the disk side would hide unregistered extras. User-facing commands
        # are commands/*.md outside shared/ (partials are user-invocable: false plumbing,
        # registered separately by convention); agents are agents/*.md; skills are
        # skills/*/SKILL.md directories.
        text = README.read_text(encoding="utf-8")
        m = manifest()
        stated = re.search(r"\*\*(\d+) commands, (\d+) agents, (\d+) skills\*\*", text)
        self.assertIsNotNone(stated, "README lacks the counts sentence")
        c, a, s = (int(stated.group(i)) for i in (1, 2, 3))
        self.assertEqual((c, a, s),
                         (len(m["commands"]), len(m["agents"]), len(m["skills"])),
                         "README counts != manifest")
        commands_disk = sorted(p.relative_to(REPO_ROOT).as_posix()
                               for p in (REPO_ROOT / "commands").glob("*.md"))
        agents_disk = sorted(p.relative_to(REPO_ROOT).as_posix()
                             for p in (REPO_ROOT / "agents").glob("*.md"))
        skills_disk = sorted(d.relative_to(REPO_ROOT).as_posix()
                             for d in (REPO_ROOT / "skills").iterdir()
                             if d.is_dir() and (d / "SKILL.md").is_file())
        self.assertEqual(sorted(c[2:] for c in m["commands"]), commands_disk,
                         "manifest commands != disk commands")
        self.assertEqual(sorted(a[2:] for a in m["agents"]), agents_disk,
                         "manifest agents != disk agents")
        self.assertEqual(sorted(s[2:] for s in m["skills"]), skills_disk,
                         "manifest skills != disk skills")
        self.assertEqual((c, a, s),
                         (len(commands_disk), len(agents_disk), len(skills_disk)))

    def test_python_floor_is_stated(self):
        self.assertIn("Python 3.11+", README.read_text(encoding="utf-8"))

    def test_migration_table_targets_resolve(self):
        text = README.read_text(encoding="utf-8")
        m = manifest()
        commands = {Path(c).stem for c in m["commands"]}
        skills = {Path(s).name for s in m["skills"]}
        rows_full = re.findall(
            r"^\| `(/(?:cc-suite|nlpm|grill):[a-z-]+)`[^|]*\| ([^|]+) \|", text, re.M)
        # Exact-set coverage (F5): every user-facing command path in disposition.yaml's
        # source rows appears as a table row, and nothing else does.
        disp = (REPO_ROOT / "docs" / "disposition.yaml").read_text(encoding="utf-8")
        expected = set()
        for block in re.split(r"\n  - row: ", disp)[1:]:
            tree = re.search(r"tree: (\S+)", block)
            paths = re.search(r"paths: \[(.*?)\]", block, re.S)
            if not tree or not paths:
                continue
            prefix = {"cc-suite": "cc-suite", "nlpm": "nlpm",
                      "grill-for-claude": "grill"}.get(tree.group(1))
            if prefix is None:
                continue
            for p2 in paths.group(1).split(","):
                p2 = p2.strip()
                if p2.startswith("commands/") and "shared/" not in p2 and p2.endswith(".md"):
                    expected.add(f"/{prefix}:{Path(p2).stem}")
        stated_old = {r[0] for r in rows_full}
        self.assertEqual(stated_old, expected,
                         "migration table rows != disposition's user-facing commands")
        rows = [r[1] for r in rows_full]
        for new in rows:
            new = new.strip()
            if "no successor" in new:
                continue
            m2 = re.search(r"/vibe-suite:([a-z-]+)|the `([a-z-]+)` skill", new)
            self.assertIsNotNone(m2, f"unparseable replacement cell: {new!r}")
            target = m2.group(1) or m2.group(2)
            self.assertIn(target, commands | skills,
                          f"migration target {target!r} is neither a registered command "
                          "nor a registered skill")


class ClaudeMdAnchors(unittest.TestCase):
    def test_battery_commands_resolve(self):
        text = CLAUDE.read_text(encoding="utf-8")
        for rel in ("tools/model-pin-lint.py", "bin/vibe-check",
                    "tools/legacy-string-sweep.sh"):
            self.assertIn(rel, text, f"CLAUDE.md does not name {rel}")
            self.assertTrue((REPO_ROOT / rel).exists(), f"{rel} named but absent")
        self.assertIn("codex-src", text)


class PrivacyAnchors(unittest.TestCase):
    def test_named_surfaces_exist(self):
        text = PRIVACY.read_text(encoding="utf-8")
        self.assertIn("claude-octopus", text)
        self.assertTrue((REPO_ROOT / "scripts" / "lib" /
                         "claude-octopus-pin.txt").is_file())
        for secret in ("CLAUDE_CODE_OAUTH_TOKEN", "PAT_TOKEN", "OPENAI_API_KEY"):
            self.assertIn(secret, text)
        self.assertNotIn("local-only", text.lower())
        self.assertIn("future", text.lower())

    def test_dispatch_claims_anchor_to_implementation_artifacts(self):
        # F5 residue: every dispatch surface PRIVACY names must exist as the artifact that
        # implements it — the claim is checked against disk, not against itself.
        text = PRIVACY.read_text(encoding="utf-8")
        anchors = {
            "delegate": "commands/delegate.md",
            "continue": "commands/continue.md",
            "bug-analyze": "commands/bug-analyze.md",
            "roast": "commands/roast.md",
            "nl-audit": "commands/nl-audit.md",
            "preflight": "commands/preflight.md",
            "refresh-knowledge": "commands/refresh-knowledge.md",
            "refine-proposal": "skills/refine-proposal/SKILL.md",
            "issue2pr": "skills/issue2pr/SKILL.md",
        }
        for name, rel in anchors.items():
            with self.subTest(surface=name):
                self.assertIn(name, text, f"PRIVACY does not name {name}")
                self.assertTrue((REPO_ROOT / rel).is_file(),
                                f"named surface {name} lacks its artifact {rel}")
        # the Stop-time hook's implementation
        self.assertTrue((REPO_ROOT / "scripts" /
                         "stop-review-gate-hook.mjs").is_file())
        self.assertIn("Stop-time review hook", text)
        # the names-not-values bridge rule is implemented where PRIVACY says it is
        bridge_cli = (REPO_ROOT / "scripts" / "bridge_cli.py").read_text(encoding="utf-8")
        self.assertIn("value is withheld", bridge_cli.replace("*", ""))


if __name__ == "__main__":
    unittest.main()


class E85ExecutionRecord(unittest.TestCase):
    """E8.5 (vibe-62): the runbook's execution record is a set of factual claims.

    Every number in it — corpus total, category breakdown, tips, pre-existing blob ids, the
    source digest — is a claim about a real, completed ops action. Nothing else in the suite
    pins them, so a drifted edit (a "tidied" count, a truncated tip) would ship silently as
    a false record. The record is parsed, its internal arithmetic checked, and its required
    verification statements required verbatim.
    """

    RECORD_HEADER = "#### E8.5 execution record (2026-08-13)"

    def record(self):
        text = (REPO_ROOT / "auditor" / "README.md").read_text()
        self.assertIn(self.RECORD_HEADER, text,
                      "the E8.5 execution record vanished from the runbook")
        body = text.split(self.RECORD_HEADER, 1)[1]
        nxt = re.search(r"^#{2,4} ", body, re.M)
        return body[:nxt.start()] if nxt else body

    def test_the_corpus_arithmetic_holds(self):
        rec = self.record()
        m = re.search(r"corpus: (\d+) file\(s\) across (\d+) categories", rec)
        self.assertIsNotNone(m, "the record no longer quotes the tool's corpus line")
        total, cats = int(m.group(1)), int(m.group(2))
        self.assertEqual(cats, 5)
        parts = re.search(r"(\d+) `reports/`, (\d+) `exemplars/`,\s*(\d+) `audits/`, "
                          r"(\d+) `articles/`, (\d+) `ledgers/`", rec)
        self.assertIsNotNone(parts, "the category breakdown is gone or reworded")
        breakdown = [int(g) for g in parts.groups()]
        self.assertEqual(sum(breakdown), total,
                         f"the breakdown {breakdown} does not sum to the stated total {total}")
        self.assertEqual(breakdown, [642, 96, 496, 49, 4],
                         "the recorded category counts drifted from the executed migration")

    def test_the_verification_statements_are_verbatim(self):
        # Whitespace-normalized so the assertion covers the WHOLE statement regardless of
        # where the runbook wraps it — the first draft split on the newline and silently
        # asserted only the first physical line, so the load-bearing tail ("auditor-data by
        # content address") could vanish unnoticed.
        rec = " ".join(self.record().split())
        for needle in ("verified 1287 file(s) against auditor-data by content address",
                       "already complete — no commit",
                       "published 1287 new file(s)"):
            self.assertIn(needle, rec,
                          f"the record lost the tool's own evidence line: {needle!r}")

    def test_tips_blobs_and_digest_are_pinned(self):
        rec = self.record()
        for fact, why in (("8d8d85a", "the pre-migration tip (the rollback anchor)"),
                          ("72ab8f0", "the post-migration tip"),
                          ("68903f1", "the sentinel README's unchanged blob id"),
                          ("03be823", "registry/repos.json's unchanged blob id"),
                          ("f8631b5", "the whole-source digest prefix"),
                          ("1,531 files", "the whole-source file count")):
            self.assertIn(fact, rec, f"the record lost {why}")

    def test_the_rollback_discipline_names_all_three_outcomes_and_the_operator_stop(self):
        # Whitespace-normalized: the runbook wraps lines, and a claim must not pass or fail
        # on where the wrap falls.
        rec = " ".join(self.record().split())
        self.assertRegex(rec, r"stops? for (the )?operator",
                         "the record does not state the mandatory operator stop before "
                         "any recovery")
        self.assertRegex(rec, r"fetch(es)? and compares?", "fetch-and-compare is not recorded")
        for outcome in ("fix and re-?run", "--force-with-lease", "revert"):
            self.assertRegex(rec, outcome,
                             f"the rollback record lost the '{outcome}' branch — all three "
                             f"outcomes must be durable")
