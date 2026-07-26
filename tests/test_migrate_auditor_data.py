#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""AC-5 row 9 — `tools/migrate-auditor-data.sh` against a local bare repo (E0.8 / vibe-10).

The fixture is the one the acceptance criterion names: a **bare** destination repository with an
`auditor-data` branch. Bare is not incidental. `cp -r` into a bare repo *succeeds* and leaves files
that are in no tree and no commit, so a tool that copies and then inspects its own output directory
would report success over a branch that gained nothing. Every assertion here therefore reads
`git ls-tree` on the destination — the branch, not the filesystem.

Three properties this suite exists to hold:

**Completeness is containment, not equality.** Asserting that the five managed namespaces *equal*
the corpus would silently require deleting anything else found there — the tool would destroy
destination data to satisfy its own check. `corpus ⊆ branch` cannot be broken by an extra file.

**Idempotence is a property of the whole corpus.** A single already-present file does not make a
run a no-op; treating it that way would strand an interrupted first run forever.

**Ownership is proved, not named.** The tool rewrites `.vibe-suite-migration/`, so it first checks
a provenance record it wrote itself. A filename is not a provenance claim.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / "tools" / "migrate-auditor-data.sh"
PREFIX = ".vibe-suite-migration"
BRANCH = "auditor-data"

# One file per §7A category, plus decoys that must never be copied.
CORPUS = {
    "auditor/reports/alpha.json": '{"repo": "alpha"}\n',
    "auditor/reports/docs/nested.html": "<p>nested</p>\n",
    "auditor/exemplars/good-skill.md": "# exemplar\n",
    "auditor/audits/alpha.md": "# audit\n",
    "auditor/audits/alpha.findings.jsonl": '{"id": 1}\n',
    "auditor/findings.jsonl": '{"finding": 1}\n',
    "auditor/disagreements.jsonl": '{"disagreement": 1}\n',
    "auditor/vocab-advisories.jsonl": '{"advisory": 1}\n',
    "auditor/logs/events.jsonl": '{"event": 1}\n',
    "case-studies/2026-01-01-study.md": "# study\n",
    "case-studies/images/fig.txt": "figure\n",
}
DECOYS = {
    "auditor/scripts/run.sh": "#!/bin/sh\necho hi\n",
    "auditor/README.md": "# readme\n",
    "auditor/SCHEMAS.md": "# schemas\n",
    "auditor/registry/repos.json": "{}\n",
    "auditor/feedback/log.json": "{}\n",
    "auditor/prompts/p.md": "prompt\n",
    # Unpublished security disclosures. The destination branch is public; copying these would be
    # the "no secrets" rule broken against data rather than credentials.
    "auditor/disclosures-pending/CVE-pending.md": "unpublished disclosure\n",
}
EXPECTED = {
    "reports/alpha.json", "reports/docs/nested.html",
    "exemplars/good-skill.md",
    "audits/alpha.md", "audits/alpha.findings.jsonl",
    "ledgers/findings.jsonl", "ledgers/disagreements.jsonl",
    "ledgers/vocab-advisories.jsonl", "ledgers/events.jsonl",
    "articles/2026-01-01-study.md", "articles/images/fig.txt",
}


def git(*args, cwd, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=check)


class RowNineFixture(unittest.TestCase):
    """A local bare destination with an `auditor-data` branch, exactly as AC-5 specifies."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.source = self.tmp / "source"
        for rel, text in {**CORPUS, **DECOYS}.items():
            path = self.source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

        self.dest = self.tmp / "dest.git"
        git("init", "--quiet", "--bare", str(self.dest), cwd=self.tmp)

        # Seed the branch so it exists, as the fixture describes.
        seed = self.tmp / "seed"
        git("clone", "--quiet", str(self.dest), str(seed), cwd=self.tmp)
        git("checkout", "--quiet", "--orphan", BRANCH, cwd=seed)
        (seed / ".keep").write_text("", encoding="utf-8")
        git("add", ".keep", cwd=seed)
        git("-c", "user.name=t", "-c", "user.email=t@t.invalid",
            "commit", "--quiet", "-m", "seed", cwd=seed)
        git("push", "--quiet", "origin", f"HEAD:{BRANCH}", cwd=seed)

    # ---------------------------------------------------------------- helpers

    def run_tool(self, *extra, expect=0, env=None):
        environment = dict(os.environ)
        environment.update(env or {})
        result = subprocess.run(
            ["bash", str(TOOL), str(self.dest), "--branch", BRANCH, "--source", str(self.source),
             *extra],
            capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, expect,
                         f"expected exit {expect}, got {result.returncode}\n"
                         f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}")
        return result

    def branch_paths(self):
        out = git("ls-tree", "-r", "--name-only", BRANCH, cwd=self.dest).stdout
        return {line for line in out.splitlines() if line}

    def branch_blob(self, path):
        return git("rev-parse", f"{BRANCH}:{path}", cwd=self.dest).stdout.strip()

    def tip(self):
        return git("rev-parse", BRANCH, cwd=self.dest).stdout.strip()

    def snapshot(self, root):
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()
        }

    def seed_branch_file(self, path, text):
        work = self.tmp / f"seed-{abs(hash(path))}"
        git("clone", "--quiet", "--branch", BRANCH, str(self.dest), str(work), cwd=self.tmp)
        target = work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        git("add", "--", path, cwd=work)
        git("-c", "user.name=t", "-c", "user.email=t@t.invalid",
            "commit", "--quiet", "-m", f"seed {path}", cwd=work)
        git("push", "--quiet", "origin", f"HEAD:{BRANCH}", cwd=work)


class TestCompleteCopy(RowNineFixture):

    def test_the_branch_tree_is_not_empty(self):
        """The bare-repo trap: a `cp`-based implementation passes its own checks and fails this."""
        self.run_tool()
        self.assertTrue(self.branch_paths() - {".keep"},
                        "nothing reached the branch — the tool wrote to a directory, not a tree")

    def test_every_corpus_file_is_on_the_branch_with_matching_content(self):
        self.run_tool()
        on_branch = self.branch_paths()
        for rel in sorted(EXPECTED):
            with self.subTest(path=rel):
                self.assertIn(rel, on_branch)
                # Blob ids are content addresses: this compares what was published, not its name.
                expected_blob = subprocess.run(
                    ["git", "hash-object", str(self.source / self._source_of(rel))],
                    capture_output=True, text=True, check=True).stdout.strip()
                self.assertEqual(self.branch_blob(rel), expected_blob)

    def test_managed_namespaces_contain_exactly_the_corpus(self):
        self.run_tool()
        managed = {p for p in self.branch_paths()
                   if p.split("/")[0] in {"reports", "exemplars", "audits", "ledgers", "articles"}}
        self.assertEqual(managed, EXPECTED)

    def test_no_decoy_is_copied(self):
        self.run_tool()
        blob = "\n".join(sorted(self.branch_paths()))
        for fragment in ("scripts/", "README.md", "SCHEMAS.md", "registry/", "feedback/",
                         "prompts/"):
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, blob)

    def test_unpublished_disclosures_never_reach_the_branch(self):
        """Named separately from the other decoys because the cost of getting it wrong is not
        a tidiness problem — the destination branch is public."""
        self.run_tool()
        self.assertNotIn("disclosures-pending", "\n".join(sorted(self.branch_paths())))
        self.assertNotIn("CVE-pending", "\n".join(sorted(self.branch_paths())))

    def _source_of(self, dest_rel):
        head, _, rest = dest_rel.partition("/")
        return {
            "reports": f"auditor/reports/{rest}",
            "exemplars": f"auditor/exemplars/{rest}",
            "audits": f"auditor/audits/{rest}",
            "articles": f"case-studies/{rest}",
            "ledgers": {"findings.jsonl": "auditor/findings.jsonl",
                        "disagreements.jsonl": "auditor/disagreements.jsonl",
                        "vocab-advisories.jsonl": "auditor/vocab-advisories.jsonl",
                        "events.jsonl": "auditor/logs/events.jsonl"}.get(rest),
        }[head]


class TestManifest(RowNineFixture):

    def test_manifest_lives_under_the_tool_prefix_and_verifies(self):
        self.run_tool()
        self.assertIn(f"{PREFIX}/manifest.sha256", self.branch_paths())
        body = git("show", f"{BRANCH}:{PREFIX}/manifest.sha256", cwd=self.dest).stdout
        listed = [line.split("  ", 1)[1] for line in body.splitlines() if line]
        self.assertEqual(set(listed), EXPECTED)
        self.assertEqual(listed, sorted(listed), "manifest must be sorted to be deterministic")
        self.assertNotIn("manifest.sha256", body, "the manifest must not list itself")

    def test_manifest_hashes_are_sha256_of_contents(self):
        import hashlib
        self.run_tool()
        body = git("show", f"{BRANCH}:{PREFIX}/manifest.sha256", cwd=self.dest).stdout
        for line in body.splitlines():
            digest, rel = line.split("  ", 1)
            with self.subTest(path=rel):
                raw = (self.source / TestCompleteCopy._source_of(self, rel)).read_bytes()
                self.assertEqual(digest, hashlib.sha256(raw).hexdigest())

    def test_provenance_records_the_tool(self):
        self.run_tool()
        record = json.loads(git("show", f"{BRANCH}:{PREFIX}/provenance.json",
                                cwd=self.dest).stdout)
        self.assertEqual(record["tool"], "vibe-suite/migrate-auditor-data")
        self.assertEqual(record["files"], len(EXPECTED))


class TestIdempotenceAndOriginals(RowNineFixture):

    def test_second_run_makes_no_commit(self):
        self.run_tool()
        first = self.tip()
        self.run_tool()
        self.assertEqual(self.tip(), first, "a complete second run must not commit")

    def test_originals_are_byte_identical(self):
        before = self.snapshot(self.source)
        self.run_tool()
        self.run_tool()
        self.assertEqual(self.snapshot(self.source), before)

    def test_partial_overlap_publishes_the_remainder(self):
        """An interrupted first run must be completable. Treating one already-present file as
        'already done' would strand it permanently — this is the case that proves it does not."""
        self.seed_branch_file("reports/alpha.json", CORPUS["auditor/reports/alpha.json"])
        before = self.tip()
        self.run_tool()
        self.assertNotEqual(self.tip(), before, "missing corpus files must still be published")
        self.assertTrue(EXPECTED <= self.branch_paths())


class TestDestinationIsNeverOverwritten(RowNineFixture):

    def test_a_differing_corpus_file_refuses(self):
        self.seed_branch_file("reports/alpha.json", "DIFFERENT CONTENT\n")
        before = self.tip()
        result = self.run_tool(expect=3)
        self.assertEqual(self.tip(), before, "a refusal must not commit")
        self.assertIn("reports/alpha.json", result.stderr)

    def test_an_extra_outside_the_namespaces_survives(self):
        self.seed_branch_file("unrelated/note.md", "mine\n")
        self.run_tool()
        self.assertIn("unrelated/note.md", self.branch_paths())
        self.assertEqual(git("show", f"{BRANCH}:unrelated/note.md", cwd=self.dest).stdout, "mine\n")

    def test_an_extra_inside_a_managed_namespace_survives(self):
        """The case an equality assertion would have deleted."""
        self.seed_branch_file("reports/user-note.md", "hand written\n")
        self.run_tool()
        self.assertIn("reports/user-note.md", self.branch_paths())
        self.assertEqual(git("show", f"{BRANCH}:reports/user-note.md", cwd=self.dest).stdout,
                         "hand written\n")


class TestPrefixOwnership(RowNineFixture):
    """The tool rewrites what is under its prefix, so it must prove the prefix is its own."""

    def test_stale_manifest_with_valid_provenance_is_regenerated(self):
        self.run_tool()
        self.seed_branch_file(f"{PREFIX}/manifest.sha256", "0  stale\n")
        self.run_tool()
        body = git("show", f"{BRANCH}:{PREFIX}/manifest.sha256", cwd=self.dest).stdout
        self.assertNotIn("stale", body)

    def test_prefix_without_provenance_refuses(self):
        self.seed_branch_file(f"{PREFIX}/manifest.sha256", "0  someone-elses\n")
        before = self.tip()
        self.run_tool(expect=3)
        self.assertEqual(self.tip(), before)
        self.assertEqual(git("show", f"{BRANCH}:{PREFIX}/manifest.sha256", cwd=self.dest).stdout,
                         "0  someone-elses\n")

    def test_prefix_with_foreign_provenance_refuses(self):
        self.seed_branch_file(f"{PREFIX}/provenance.json", '{"tool": "someone-else"}\n')
        before = self.tip()
        self.run_tool(expect=3)
        self.assertEqual(self.tip(), before)

    def test_prefix_with_unparseable_provenance_refuses(self):
        self.seed_branch_file(f"{PREFIX}/provenance.json", "{ this is not json\n")
        before = self.tip()
        self.run_tool(expect=3)
        self.assertEqual(self.tip(), before)


class TestOrphanBranchAndRedaction(RowNineFixture):

    def test_missing_branch_is_created_as_an_orphan(self):
        empty = self.tmp / "empty.git"
        git("init", "--quiet", "--bare", str(empty), cwd=self.tmp)
        result = subprocess.run(
            ["bash", str(TOOL), str(empty), "--branch", BRANCH, "--source", str(self.source)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        paths = {line for line in git("ls-tree", "-r", "--name-only", BRANCH,
                                      cwd=empty).stdout.splitlines() if line}
        self.assertTrue(EXPECTED <= paths)

    def test_a_token_in_the_destination_url_is_never_echoed(self):
        """A local-path fixture cannot catch a credential leak, because it has nothing to leak."""
        url = "https://x-access-token:SECRETVALUE@example.invalid/repo.git"
        result = subprocess.run(
            ["bash", str(TOOL), url, "--branch", BRANCH, "--source", str(self.source)],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, "the unreachable host should fail the run")
        combined = result.stdout + result.stderr
        self.assertNotIn("SECRETVALUE", combined)
        self.assertIn("***@example.invalid", combined)


class TestSymlinkAttack(RowNineFixture):
    """A destination branch is not trusted input. It can carry a symlink, and `write_bytes`
    follows one — verified: writing to a planted link reached a file outside the clone entirely.
    So the managed paths are checked against the tree, and writes use O_NOFOLLOW."""

    def seed_branch_symlink(self, path, target):
        work = self.tmp / "seed-link"
        git("clone", "--quiet", "--branch", BRANCH, str(self.dest), str(work), cwd=self.tmp)
        link = work / path
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        git("add", "--", path, cwd=work)
        git("-c", "user.name=t", "-c", "user.email=t@t.invalid",
            "commit", "--quiet", "-m", "seed link", cwd=work)
        git("push", "--quiet", "origin", f"HEAD:{BRANCH}", cwd=work)

    def test_a_symlink_at_a_corpus_path_refuses(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        victim = outside / "secret.txt"
        victim.write_text("ORIGINAL\n", encoding="utf-8")
        self.seed_branch_symlink("reports/alpha.json", str(victim))
        before = self.tip()
        result = self.run_tool(expect=3)
        # Assert the REASON, not just the code. Reading through the link would also produce a
        # content mismatch and exit 3, so a test that checked only the code would pass against a
        # tool with no symlink handling at all — which is exactly what a mutation run showed.
        self.assertIn("symlink", result.stderr.lower())
        self.assertEqual(victim.read_text(encoding="utf-8"), "ORIGINAL\n",
                         "the tool must not write through a destination-controlled symlink")
        self.assertEqual(self.tip(), before)

    def test_a_symlinked_ancestor_refuses(self):
        outside = self.tmp / "outside-dir"
        outside.mkdir()
        self.seed_branch_symlink("reports/docs", str(outside))
        before = self.tip()
        result = self.run_tool(expect=3)
        self.assertIn("symlink", result.stderr.lower())
        self.assertEqual(list(outside.iterdir()), [],
                         "nothing may be written beneath a symlinked directory")
        self.assertEqual(self.tip(), before)


class TestVerificationIsNotJustACount(RowNineFixture):

    def test_verification_compares_every_blob_not_merely_a_count(self):
        """A seeded `.keep` alone satisfies "the tree is non-empty". The verification must compare
        each manifest entry against the branch by content address."""
        self.run_tool()
        manifest = git("show", f"{BRANCH}:{PREFIX}/manifest.sha256", cwd=self.dest).stdout
        listed = {line.split("  ", 1)[1] for line in manifest.splitlines() if line}
        self.assertEqual(listed, EXPECTED)
        on_branch = self.branch_paths()
        for rel in listed:
            with self.subTest(path=rel):
                self.assertIn(rel, on_branch)


if __name__ == "__main__":
    unittest.main()
