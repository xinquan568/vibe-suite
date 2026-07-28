#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Structural and referential checks over the ADR series in `docs/adr/`.

**Scope, stated narrowly.** These tests cover three ways a numbered document series rots: a file
renamed out from under its number, an index row left behind, and a reference to a number that was
never allocated. They cover nothing else. In particular they cannot tell whether an implementation
honours the decision an ADR records — an ADR can be perfectly well-formed, perfectly indexed, and
perfectly referenced while the code contradicts it.

That limit is worth stating because ADR-0001 assigns a responsibility to `bin/vibe-check`, which does
not exist yet. Nothing here will notice if it lands ignoring the decision.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = REPO_ROOT / "docs" / "adr"
INDEX = ADR_DIR / "README.md"

#: `NNNN-slug.md`. Four digits so the series sorts lexicographically for as long as it will exist.
ADR_FILENAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")

#: How an ADR is referred to from anywhere else in the repository.
ADR_REFERENCE = re.compile(r"\bADR-(\d{4})\b")

#: Every ADR carries these, in this order. An ADR without a Decision is a note.
REQUIRED_HEADINGS = ("## Status", "## Context", "## Decision", "## Consequences")

#: A closed vocabulary. "Superseded by ADR-NNNN" carries its own reference and is checked like any
#: other, which is what keeps a superseded ADR from pointing into nothing.
STATUS_VALUES = ("Accepted", "Proposed", "Rejected", "Deprecated")

#: Directories that hold no repository prose. `.git` is excluded for size, not for principle.
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache"}

#: Suffixes searched for `ADR-NNNN` references. Binary and lockfile-ish paths are not prose.
PROSE_SUFFIXES = {".md", ".py", ".mjs", ".js", ".json", ".yml", ".yaml", ".sh", ".toml", ".txt"}


def adr_files():
    """Every file in `docs/adr/` that claims to be an ADR by its name."""
    if not ADR_DIR.is_dir():
        return []
    return sorted(p for p in ADR_DIR.iterdir() if ADR_FILENAME.match(p.name))


def allocated_numbers():
    return {ADR_FILENAME.match(p.name).group(1) for p in adr_files()}


def prose_files():
    """Repository files whose text can carry an `ADR-NNNN` reference.

    This test file is excluded: it names the pattern in order to search for it, and a checker that
    matched its own pattern definition would always find a reference to satisfy itself.
    """
    here = Path(__file__).resolve()
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in PROSE_SUFFIXES:
            continue
        if SKIP_DIRS & set(path.relative_to(REPO_ROOT).parts):
            continue
        if path.resolve() == here:
            continue
        yield path


class TestAdrStructure(unittest.TestCase):
    """Assertion 1 — every ADR is well-formed."""

    def test_adr_directory_exists(self):
        self.assertTrue(
            ADR_DIR.is_dir(),
            f"{ADR_DIR.relative_to(REPO_ROOT)} does not exist; the ADR series has no home.",
        )

    def test_index_exists(self):
        self.assertTrue(
            INDEX.is_file(),
            f"{INDEX.relative_to(REPO_ROOT)} does not exist; the series has no index.",
        )

    def test_directory_holds_only_adrs_and_the_index(self):
        if not ADR_DIR.is_dir():
            self.skipTest("docs/adr/ absent — test_adr_directory_exists owns that failure")
        stray = [
            p.name
            for p in ADR_DIR.iterdir()
            if p.is_file() and p.name != "README.md" and not ADR_FILENAME.match(p.name)
        ]
        self.assertEqual(
            stray, [], f"files in docs/adr/ matching neither NNNN-slug.md nor README.md: {stray}"
        )

    def test_every_adr_has_the_required_headings_in_order(self):
        for path in adr_files():
            with self.subTest(adr=path.name):
                text = path.read_text(encoding="utf-8")
                positions = []
                for heading in REQUIRED_HEADINGS:
                    index = text.find(f"\n{heading}\n")
                    self.assertNotEqual(
                        index, -1, f"{path.name} is missing the heading {heading!r}"
                    )
                    positions.append(index)
                self.assertEqual(
                    positions,
                    sorted(positions),
                    f"{path.name} has the required headings out of order; expected "
                    f"{' → '.join(REQUIRED_HEADINGS)}",
                )

    def test_every_adr_declares_a_known_status(self):
        for path in adr_files():
            with self.subTest(adr=path.name):
                text = path.read_text(encoding="utf-8")
                after = text.split("\n## Status\n", 1)
                self.assertEqual(len(after), 2, f"{path.name} has no Status section")
                first_line = next(
                    (line.strip() for line in after[1].splitlines() if line.strip()), ""
                )
                self.assertTrue(
                    any(first_line.startswith(value) for value in STATUS_VALUES),
                    f"{path.name} declares status {first_line!r}, which is outside "
                    f"{STATUS_VALUES}",
                )


class TestAdrReferences(unittest.TestCase):
    """Assertion 2 — every `ADR-NNNN` reference in the repository resolves to a file."""

    def test_every_reference_resolves(self):
        allocated = allocated_numbers()
        dangling = {}
        for path in prose_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for number in ADR_REFERENCE.findall(text):
                if number not in allocated:
                    dangling.setdefault(number, []).append(
                        str(path.relative_to(REPO_ROOT))
                    )
        self.assertEqual(
            dangling,
            {},
            "references to ADR numbers with no file in docs/adr/: "
            + "; ".join(f"ADR-{n} cited by {', '.join(f)}" for n, f in sorted(dangling.items())),
        )


class TestAdrIndex(unittest.TestCase):
    """Assertion 3 — the index and the directory agree, in both directions."""

    def _indexed_numbers(self):
        if not INDEX.is_file():
            return set()
        return set(ADR_REFERENCE.findall(INDEX.read_text(encoding="utf-8")))

    def test_every_adr_is_indexed(self):
        missing = sorted(allocated_numbers() - self._indexed_numbers())
        self.assertEqual(
            missing, [], f"ADRs present in docs/adr/ but absent from its README: {missing}"
        )

    def test_every_indexed_adr_exists(self):
        extra = sorted(self._indexed_numbers() - allocated_numbers())
        self.assertEqual(
            extra, [], f"ADRs listed in docs/adr/README.md with no matching file: {extra}"
        )


if __name__ == "__main__":
    unittest.main()
