#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Structural and referential checks over the ADR series in `docs/adr/`.

**Scope, stated narrowly.** These checks cover three ways a numbered document series rots: a file
renamed out from under its number, an index row left behind, and a reference to a number that was
never allocated. They cover nothing else. In particular they cannot tell whether an implementation
honours the decision an ADR records — an ADR can be perfectly well-formed, perfectly indexed and
perfectly referenced while the code contradicts it. ADR-0001 assigns a responsibility to
`bin/vibe-check`, which does not exist yet, and nothing here will notice if it lands ignoring the
decision.

**Every check takes a root**, and every check has a negative test that builds a broken tree in a
temporary directory and asserts the check rejects it. An earlier revision of this file checked the
repository only, and review found it passed against a renamed ADR whose index link had gone stale —
it compared *number* sets, which are equal on both sides of exactly that failure. A positive-only
suite cannot catch that; the negative tests below are the part that does the work.
"""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: `NNNN-slug.md`. Four digits, so the series sorts lexicographically for as long as it will exist.
ADR_FILENAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")

#: How an ADR is referred to from anywhere else in the repository. Written as a concatenation so
#: this module contains no literal four-digit reference of its own — otherwise the reference check
#: would have to exclude the file that defines it, and a checker that skips a file is a checker with
#: a blind spot exactly where its author was looking.
ADR_REFERENCE = re.compile(r"\bADR" + r"-(\d{4})\b")

#: An index row's link: the reference text and the file it points at.
INDEX_LINK = re.compile(r"\[ADR" + r"-(\d{4})\]\(([^)]+)\)")

#: Every ADR carries these, in this order. An ADR without a Decision is a note.
REQUIRED_HEADINGS = ("## Status", "## Context", "## Decision", "## Consequences")

#: A closed vocabulary, matched exactly. Supersession detail belongs in Consequences, not here.
STATUS_VALUES = frozenset({"Accepted", "Proposed", "Rejected", "Deprecated"})


def adr_dir(root):
    return Path(root) / "docs" / "adr"


def index_path(root):
    return adr_dir(root) / "README.md"


def adr_files(root):
    """Every file in `docs/adr/` whose name claims it is an ADR."""
    directory = adr_dir(root)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir() if p.is_file() and ADR_FILENAME.match(p.name))


def allocated(root):
    """number -> filename, for every ADR file present."""
    return {ADR_FILENAME.match(p.name).group(1): p.name for p in adr_files(root)}


def stray_children(root):
    """Anything in `docs/adr/` that is neither the index nor an ADR — directories included."""
    directory = adr_dir(root)
    if not directory.is_dir():
        return []
    return sorted(
        p.name
        for p in directory.iterdir()
        if not (p.is_file() and (p.name == "README.md" or ADR_FILENAME.match(p.name)))
    )


def index_links(root):
    """number -> link target, from the index's actual links.

    Reading links rather than bare numbers is what catches a renamed ADR: the number survives a
    rename and the target does not.
    """
    path = index_path(root)
    if not path.is_file():
        return {}
    return dict(INDEX_LINK.findall(path.read_text(encoding="utf-8")))


def text_files(root):
    """Every tracked file whose bytes decode as UTF-8.

    Tracked, so generated and ignored trees are out of scope; decodable, so binaries are skipped by
    what they are rather than by an extension allowlist that would miss `LICENSE` or a `.rst`.
    """
    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    for name in listing.split(b"\0"):
        if not name:
            continue
        path = Path(root) / name.decode("utf-8", "surrogateescape")
        if not path.is_file():
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def dangling_references(root):
    """number -> [files citing it], for every reference with no ADR file behind it."""
    known = set(allocated(root))
    found = {}
    for path, text in text_files(root):
        for number in ADR_REFERENCE.findall(text):
            if number not in known:
                found.setdefault(number, []).append(str(path.relative_to(root)))
    return found


def malformed_status(path):
    """The offending status line, or None."""
    parts = path.read_text(encoding="utf-8").split("\n## Status\n", 1)
    if len(parts) != 2:
        return "<no Status section>"
    line = next((s.strip() for s in parts[1].splitlines() if s.strip()), "")
    return None if line in STATUS_VALUES else line


def missing_or_misordered_headings(path):
    """A message describing the first heading problem, or None."""
    text = path.read_text(encoding="utf-8")
    positions = []
    for heading in REQUIRED_HEADINGS:
        index = text.find(f"\n{heading}\n")
        if index == -1:
            return f"missing {heading!r}"
        positions.append(index)
    if positions != sorted(positions):
        return f"headings out of order; expected {' -> '.join(REQUIRED_HEADINGS)}"
    return None


class TestRepositoryAdrs(unittest.TestCase):
    """The checks, applied to this repository."""

    def test_directory_and_index_exist(self):
        self.assertTrue(adr_dir(REPO_ROOT).is_dir(), "docs/adr/ does not exist")
        self.assertTrue(index_path(REPO_ROOT).is_file(), "docs/adr/README.md does not exist")

    def test_no_stray_children(self):
        self.assertEqual(stray_children(REPO_ROOT), [])

    def test_headings(self):
        for path in adr_files(REPO_ROOT):
            with self.subTest(adr=path.name):
                self.assertIsNone(missing_or_misordered_headings(path))

    def test_status(self):
        for path in adr_files(REPO_ROOT):
            with self.subTest(adr=path.name):
                self.assertIsNone(malformed_status(path))

    def test_every_reference_resolves(self):
        self.assertEqual(dangling_references(REPO_ROOT), {})

    def test_index_and_directory_agree_on_numbers(self):
        self.assertEqual(set(index_links(REPO_ROOT)), set(allocated(REPO_ROOT)))

    def test_every_index_link_points_at_the_file_it_names(self):
        allocated_files = allocated(REPO_ROOT)
        for number, target in sorted(index_links(REPO_ROOT).items()):
            with self.subTest(adr=number):
                self.assertEqual(
                    target,
                    allocated_files.get(number),
                    f"index links ADR-{number} to {target!r}, but the file is "
                    f"{allocated_files.get(number)!r}",
                )
                self.assertTrue((adr_dir(REPO_ROOT) / target).is_file())


class TestChecksRejectBrokenTrees(unittest.TestCase):
    """Negative cases. Each builds a tree broken one way and asserts the check notices."""

    GOOD_ADR = (
        "# ADR-0001 — A decision\n\n## Status\n\nAccepted\n\n## Context\n\nc\n\n"
        "## Decision\n\nd\n\n## Consequences\n\ne\n"
    )
    ADR_NAME = "0001-a-decision.md"

    def _tree(self, adr_name=ADR_NAME, adr_body=None, index=None, extra=None):
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", str(root)], check=False))
        directory = root / "docs" / "adr"
        directory.mkdir(parents=True)
        if adr_name:
            (directory / adr_name).write_text(
                self.GOOD_ADR if adr_body is None else adr_body, encoding="utf-8"
            )
        (directory / "README.md").write_text(
            f"| [ADR-0001]({adr_name or 'missing.md'}) | t | Accepted |\n"
            if index is None
            else index,
            encoding="utf-8",
        )
        for relative, content in (extra or {}).items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        return root

    def test_healthy_tree_passes_every_check(self):
        """Without this, a check that rejects everything would satisfy all the cases below."""
        root = self._tree()
        self.assertEqual(stray_children(root), [])
        self.assertEqual(dangling_references(root), {})
        self.assertEqual(set(index_links(root)), set(allocated(root)))
        self.assertEqual(index_links(root)["0001"], allocated(root)["0001"])
        adr = adr_dir(root) / self.ADR_NAME
        self.assertIsNone(malformed_status(adr))
        self.assertIsNone(missing_or_misordered_headings(adr))

    def test_renamed_adr_with_a_stale_index_link_is_caught(self):
        """The case review found the earlier revision passing.

        The number is still 0001 on both sides, so any check comparing number sets is satisfied.
        Only the link target reveals the rename.
        """
        root = self._tree(adr_name="0001-renamed-decision.md")
        (adr_dir(root) / "README.md").write_text(
            "| [ADR-0001](0001-a-decision.md) | t | Accepted |\n", encoding="utf-8"
        )
        self.assertEqual(set(index_links(root)), set(allocated(root)), "numbers agree — as expected")
        self.assertNotEqual(
            index_links(root)["0001"], allocated(root)["0001"], "the stale link must be visible"
        )
        self.assertFalse((adr_dir(root) / index_links(root)["0001"]).is_file())

    def test_reference_to_an_unallocated_number_is_caught(self):
        root = self._tree(extra={"docs/note.md": "see ADR" + "-0002 for the rest\n"})
        self.assertEqual(dangling_references(root), {"0002": ["docs/note.md"]})

    def test_a_dangling_reference_in_a_suffixless_file_is_caught(self):
        """An extension allowlist would have missed this one."""
        root = self._tree(extra={"LICENSE": "granted under ADR" + "-0003\n"})
        self.assertEqual(dangling_references(root), {"0003": ["LICENSE"]})

    def test_untracked_files_are_out_of_scope(self):
        root = self._tree()
        (root / "scratch.md").write_text("ADR" + "-0009\n", encoding="utf-8")
        self.assertEqual(dangling_references(root), {}, "untracked scratch must not fail the suite")

    def test_indexed_adr_with_no_file_is_caught(self):
        root = self._tree(adr_name=None)
        self.assertEqual(allocated(root), {})
        self.assertEqual(set(index_links(root)), {"0001"})

    def test_adr_missing_from_the_index_is_caught(self):
        root = self._tree(index="No table here.\n")
        self.assertEqual(index_links(root), {})
        self.assertEqual(set(allocated(root)), {"0001"})

    def test_stray_file_and_stray_directory_are_both_caught(self):
        root = self._tree()
        (adr_dir(root) / "scratch.txt").write_text("x", encoding="utf-8")
        (adr_dir(root) / "drafts").mkdir()
        self.assertEqual(stray_children(root), ["drafts", "scratch.txt"])

    def test_near_miss_status_is_rejected(self):
        """`startswith` matching accepted this; exact matching does not."""
        root = self._tree(adr_body=self.GOOD_ADR.replace("\nAccepted\n", "\nAcceptedly\n"))
        self.assertEqual(malformed_status(adr_dir(root) / self.ADR_NAME), "Acceptedly")

    def test_missing_and_misordered_headings_are_rejected(self):
        root = self._tree(adr_body=self.GOOD_ADR.replace("## Decision", "## Choice"))
        self.assertEqual(
            missing_or_misordered_headings(adr_dir(root) / self.ADR_NAME), "missing '## Decision'"
        )
        swapped = self._tree(
            adr_body="# t\n\n## Decision\n\nd\n\n## Status\n\nAccepted\n\n## Context\n\nc\n\n"
            "## Consequences\n\ne\n"
        )
        self.assertIn(
            "out of order", missing_or_misordered_headings(adr_dir(swapped) / self.ADR_NAME)
        )


if __name__ == "__main__":
    unittest.main()
