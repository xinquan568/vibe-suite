#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Tests for the four shared discovery/classification partials (E0.3 / vibe-5).

The partials are markdown; the acceptance criterion is executable. This module is the seam between
them: it **parses the rule tables out of the partials** and runs them, so the markdown is the single
source of truth and no rule is restated in code. Restating them here would recreate the structure
that produced #67/#68 — a second copy of a rule set with nothing comparing the two.

Three properties make the suite able to fail, and each was added because an earlier draft of the plan
lacked it:

**Parsing fails closed.** A table this module cannot find or cannot tokenize raises. A parser that
returned an empty rule set would make every assertion below vacuously true — the failure
`scripts/validate_audit_output.py` exists to prevent, in a new place.

**Discovery runs against a real filesystem.** A fixture tree is built in a temp directory (with
`HOME` redirected for category F) and the extracted globs are executed over it. Checking that
`discover.md` merely *contains* six headings would pass a partial whose globs were all wrong.

**Every retained pattern branch has a positive fixture, and no fixture sits inside a skip
directory.** An earlier draft put the whole of category D under `vendor/` — a skip dir — so every D
rule could have been deleted and the suite stayed green.

Assertions on discovery use **ordered lists, never sets**, on both sides of deduplication: the raw
records prove the root `CLAUDE.md` matched two patterns, and the post-dedup list proves discovery
collapsed it to one. A set on either side hides half of that rule.
"""

import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED = REPO_ROOT / "commands" / "shared"
PARTIALS = {
    name: SHARED / f"{name}.md"
    for name in ("discover", "classify", "scope-parse", "plugin-discover")
}


class PartialParseError(Exception):
    """A partial could not be parsed. Never swallowed — see the module docstring."""


# --------------------------------------------------------------------------- parsing


def _read(name):
    path = PARTIALS[name]
    if not path.exists():
        raise PartialParseError(f"partial not found: {path.relative_to(REPO_ROOT)}")
    return path.read_text(encoding="utf-8")


def _table_after(text, heading, source):
    """Return the rows of the first markdown table following `heading`."""
    idx = text.find(heading)
    if idx < 0:
        raise PartialParseError(f"{source}: heading not found: {heading!r}")
    rows, seen_table = [], False
    for line in text[idx + len(heading):].splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            seen_table = True
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append(cells)
        elif seen_table and stripped and not stripped.startswith("|"):
            break
    if not rows:
        raise PartialParseError(f"{source}: no table under {heading!r}")
    return rows[1:]  # drop the header row


def _ticked(cell):
    return re.findall(r"`([^`]+)`", cell)


def parse_categories(text=None):
    """Category letter -> ordered list of globs, from `discover.md`."""
    text = _read("discover") if text is None else text
    categories = {}
    for letter in "ABCDEF":
        heading = f"## Category {letter} —"
        globs = []
        for row in _table_after(text, heading, "discover.md"):
            globs.extend(_ticked(row[0]))
        if not globs:
            raise PartialParseError(f"discover.md: category {letter} has no patterns")
        categories[letter] = globs
    return categories


def parse_skip_dirs(text=None):
    text = _read("discover") if text is None else text
    idx = text.find("## Skip directories")
    if idx < 0:
        raise PartialParseError("discover.md: no '## Skip directories' section")
    dirs = []
    for line in text[idx:].splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith("- "):
            dirs.extend(_ticked(stripped))
        elif stripped.startswith("#"):
            break
    if not dirs:
        raise PartialParseError("discover.md: skip-directory list is empty")
    return dirs


def parse_exclusions(text=None):
    """Glob -> excluded path prefix, from an "excludes <prefix>" marker in the Notes cell.

    Exclusions must be machine-readable, not prose: a note the consumer cannot apply is a rule that
    silently does not exist. Both of this partial's exclusions were prose in the first draft, and the
    suite caught both.
    """
    text = _read("discover") if text is None else text
    exclusions = {}
    for letter in "ABCDEF":
        for row in _table_after(text, f"## Category {letter} —", "discover.md"):
            if len(row) < 2 or "excludes" not in row[1].lower():
                continue
            after = row[1][row[1].lower().index("excludes"):]
            prefixes = _ticked(after)
            if not prefixes:
                raise PartialParseError(f"discover.md: 'excludes' with no backticked prefix: {row[1]!r}")
            for glob in _ticked(row[0]):
                exclusions[glob] = prefixes[0]
    return exclusions


def parse_content_qualified(text=None):
    """Globs whose Notes cell marks them content-qualified, from `discover.md`."""
    text = _read("discover") if text is None else text
    qualified = set()
    for letter in "ABCDEF":
        for row in _table_after(text, f"## Category {letter} —", "discover.md"):
            if len(row) > 1 and "content-qualified" in row[1].lower():
                qualified.update(_ticked(row[0]))
    return qualified


def parse_prompt_markers(text=None):
    """The prompt-content predicate's markers, from `discover.md` (D-n)."""
    text = _read("discover") if text is None else text
    idx = text.find("## Prompt-content predicate")
    if idx < 0:
        raise PartialParseError("discover.md: no '## Prompt-content predicate' section")
    markers = []
    for line in text[idx:].splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith("- "):
            markers.extend(_ticked(stripped))
        elif stripped.startswith("#"):
            break
    if not markers:
        raise PartialParseError("discover.md: prompt-content predicate has no markers")
    return markers


def parse_precedence(text=None):
    text = _read("discover") if text is None else text
    match = re.search(r"\*\*Precedence:\*\*\s*([A-F](?:\s*→\s*[A-F])+)", text)
    if not match:
        raise PartialParseError("discover.md: no '**Precedence:** A → B → …' line")
    return [p.strip() for p in match.group(1).split("→")]


# Closed condition vocabulary for classify.md. Anything else raises (fail-closed).
_COND = re.compile(
    r"^(?:matches (?P<globs>(?:`[^`]+`(?:, )?)+)"
    r"|basename is (?P<base>`[^`]+`)"
    r"|contains (?P<contains>`[^`]+`)"
    r"|fallback)"
    r"(?P<rest>.*)$"
)


def _parse_condition(cond, row_no):
    """Parse one condition cell into a predicate. Raises on anything unrecognised."""
    match = _COND.match(cond.strip())
    if not match:
        raise PartialParseError(f"classify.md row {row_no}: unparseable condition {cond!r}")
    globs = _ticked(match.group("globs") or "")
    base = (_ticked(match.group("base") or "") or [None])[0]
    contains = (_ticked(match.group("contains") or "") or [None])[0]
    rest, parent, not_under, not_at_root, extra_globs = match.group("rest").strip(), None, None, False, []
    while rest:
        if m := re.match(r"^and parent is (`[^`]+`)", rest):
            parent = _ticked(m.group(1))[0]
        elif m := re.match(r"^and not under (`[^`]+`)", rest):
            not_under = _ticked(m.group(1))[0]
        elif m := re.match(r"^and not at root", rest):
            not_at_root, m = True, re.match(r"^and not at root", rest)
        elif m := re.match(r"^and matches ((?:`[^`]+`(?:, )?)+)", rest):
            extra_globs = _ticked(m.group(1))
        else:
            raise PartialParseError(f"classify.md row {row_no}: unparseable clause {rest!r}")
        rest = rest[m.end():].strip()

    def predicate(path):
        name = path.split("/")[-1]
        parts = path.split("/")
        if cond.strip() == "fallback":
            return True
        if globs and not any(glob_match(path, g) for g in globs):
            return False
        if base is not None and name != base:
            return False
        if contains is not None and contains not in path:
            return False
        if parent is not None and (len(parts) < 2 or parts[-2] != parent):
            return False
        if not_under is not None and path.startswith(not_under):
            return False
        if not_at_root and "/" not in path:
            return False
        if extra_globs and not any(glob_match(path, g) for g in extra_globs):
            return False
        return True

    return predicate


def parse_classify_rules(text=None):
    """Ordered list of (row_number, predicate, type) from `classify.md`."""
    text = _read("classify") if text is None else text
    rules = []
    for row in _table_after(text, "## Classification rules", "classify.md"):
        if len(row) < 3:
            raise PartialParseError(f"classify.md: malformed row {row!r}")
        try:
            number = int(row[0])
        except ValueError as exc:
            raise PartialParseError(f"classify.md: non-numeric row id {row[0]!r}") from exc
        types = _ticked(row[2])
        if not types:
            raise PartialParseError(f"classify.md row {number}: no type in {row[2]!r}")
        rules.append((number, _parse_condition(row[1], number), types[0]))
    if [n for n, _, _ in rules] != list(range(1, len(rules) + 1)):
        raise PartialParseError("classify.md: row numbers are not 1..N in order")
    return rules


def parse_scope_forms(text=None):
    """Scope token -> resolution, from `scope-parse.md`."""
    text = _read("scope-parse") if text is None else text
    forms = {}
    for row in _table_after(text, "## Scope grammar", "scope-parse.md"):
        key = _ticked(row[0])
        forms[key[0] if key else row[0]] = row[1]
    if not forms:
        raise PartialParseError("scope-parse.md: empty scope grammar")
    return forms


def parse_manifest_outcomes(text=None):
    """Manifest condition -> outcome, from `plugin-discover.md`."""
    text = _read("plugin-discover") if text is None else text
    outcomes = {}
    for row in _table_after(text, "## Manifest validation", "plugin-discover.md"):
        outcomes[row[0].strip().lower()] = row[1].strip().lower()
    if not outcomes:
        raise PartialParseError("plugin-discover.md: empty manifest-validation table")
    return outcomes


# --------------------------------------------------------------------------- globbing


def glob_match(path, pattern):
    """Match a POSIX-relative path against a `**`-aware glob."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.fullmatch("".join(out), path) is not None


# --------------------------------------------------------------------------- discovery


def discover(root, categories, skip_dirs, precedence, home=None, qualified=None, markers=None,
             exclusions=None):
    """Walk `root`, returning raw ordered records: (path, category, pattern_matched).

    Raw means pre-deduplication: a file matching two patterns appears twice. That is what makes the
    exclusion and dedup rules testable — collapsing here would erase the evidence.
    """
    root = Path(root)
    skip = {d.strip("/") for d in skip_dirs}
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in skip for part in rel.split("/")[:-1]):
            continue
        if rel.split("/")[-1] == ".gitkeep":
            continue
        files.append(rel)

    records = []
    for letter in precedence:
        for pattern in categories[letter]:
            if pattern.startswith("~/"):
                if home is None:
                    continue
                for path in sorted(Path(home).rglob("*")):
                    if path.is_file() and glob_match(
                        path.relative_to(home).as_posix(), pattern[2:]
                    ):
                        records.append((f"~/{path.relative_to(home).as_posix()}", letter, pattern))
                continue
            for rel in files:
                if not glob_match(rel, pattern):
                    continue
                excluded = (exclusions or {}).get(pattern)
                if excluded and rel.startswith(excluded):
                    continue
                if qualified and pattern in qualified:
                    body = (root / rel).read_text(encoding="utf-8", errors="replace")
                    if not any(m in body for m in (markers or [])):
                        continue
                records.append((rel, letter, pattern))
    return records


def dedup(records):
    """Collapse to first-match-wins, preserving order."""
    seen, out = set(), []
    for record in records:
        if record[0] in seen:
            continue
        seen.add(record[0])
        out.append(record)
    return out


def classify(path, rules):
    for _, predicate, artifact_type in rules:
        if predicate(path):
            return artifact_type
    raise PartialParseError(f"no rule matched {path!r} — classify.md lacks a fallback")


# --------------------------------------------------------------------------- fixture


PROMPTY = "You are a reviewer.\n\n## Instructions\nDo the thing.\n"
PLAIN = "# Scaffold\n\nA plain template with no model instruction.\n"

FIXTURE = {
    # Category A — 10 branches
    ".claude-plugin/plugin.json": '{"name":"fixture","version":"0.0.1"}',
    ".claude-plugin/marketplace.json": '{"plugins":[]}',
    "commands/x.md": "# x\n",
    "commands/shared/p.md": "# partial\n",
    "agents/a.md": "# agent\n",
    "skills/s/SKILL.md": "# skill\n",
    "hooks/hooks.json": "[]",
    ".mcp.json": '{"mcpServers":{}}',
    ".lsp.json": "{}",
    "settings.json": "{}",
    # Category B — 8 branches
    "CLAUDE.md": "# root\n",
    ".claude/CLAUDE.md": "# claude dir\n",
    "pkg/CLAUDE.md": "# nested\n",
    ".claude/rules/r.md": "# rule\n",
    ".claude/settings.json": '{"hooks":{}}',
    ".claude/settings.local.json": "{}",
    ".claude/vibe.local.md": "# local\n",
    ".claude/commands/u.md": "# user command\n",
    # Category C — 5 branches (templates gets a positive and a negative)
    "prompts/p.md": PROMPTY,
    "templates/prompt-ish.md": PROMPTY,
    "templates/plain.md": PLAIN,
    "lib/system-prompt.md": PROMPTY,
    "x/review-prompt.md": PROMPTY,
    "x/review_prompt.md": PROMPTY,
    # Category D — 7 branches, none under a skip directory
    "fw/agents/y.md": "# fw agent\n",
    "fw/agents/y.yaml": "name: y\n",
    "fw/skills/z.md": "# fw skill\n",
    "fw/skills/nested/z2.md": "# fw nested skill\n",
    "fw/manifest.yaml": "name: fw\n",
    "fw/manifest.json": '{"name":"fw"}',
    "frameworks/f.md": "# framework config\n",
    # Category E — 8 branches
    "docs/d.md": "# docs\n",
    "dev-docs/d.md": "# dev docs\n",
    "specs/s.md": "# spec\n",
    "design/d.md": "# design\n",
    "plans/p.md": "# plan\n",
    "decisions/d.md": "# decision\n",
    "README.md": "# readme\n",
    "CONTRIBUTING.md": "# contributing\n",
    # Guards and negatives
    "skills/s/references/ref.md": "# first-party skill asset, NOT a framework skill\n",
    "docs/schema.json": "{}",
    "agents/.gitkeep": "",
    "commands/.gitkeep": "",
}

HOME_FIXTURE = {
    ".claude/projects/proj/memory/note.md": "# memory\n",
    ".claude/projects/proj/memory/MEMORY.md": "# index\n",
}


def build_fixture(root, skip_dirs):
    for rel, body in FIXTURE.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    # One baited file per skip directory: `**/CLAUDE.md` matches at any depth, so if a skip
    # directory is missing from the partial, these surface immediately.
    for skip in skip_dirs:
        path = Path(root) / skip.strip("/") / "pkg" / "CLAUDE.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# should be skipped\n", encoding="utf-8")


def build_home(root):
    for rel, body in HOME_FIXTURE.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


class FixtureCase(unittest.TestCase):
    """Base: a temp fixture tree plus a redirected HOME, torn down per class."""

    @classmethod
    def setUpClass(cls):
        cls.categories = parse_categories()
        cls.skip_dirs = parse_skip_dirs()
        cls.precedence = parse_precedence()
        cls.qualified = parse_content_qualified()
        cls.markers = parse_prompt_markers()
        cls.exclusions = parse_exclusions()
        cls.rules = parse_classify_rules()
        cls.tmp = tempfile.mkdtemp(prefix="vibe5-fixture-")
        cls.home = tempfile.mkdtemp(prefix="vibe5-home-")
        build_fixture(cls.tmp, cls.skip_dirs)
        build_home(cls.home)
        cls.raw = discover(cls.tmp, cls.categories, cls.skip_dirs, cls.precedence, home=cls.home,
                           qualified=cls.qualified, markers=cls.markers,
                           exclusions=cls.exclusions)
        cls.deduped = dedup(cls.raw)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)
        shutil.rmtree(cls.home, ignore_errors=True)


# --------------------------------------------------------------------------- tests


class TestParserFailsClosed(unittest.TestCase):
    """A parser that degrades quietly would make every other test vacuous."""

    def test_missing_heading_raises(self):
        with self.assertRaises(PartialParseError):
            parse_categories("# nothing here\n")

    def test_empty_table_raises(self):
        with self.assertRaises(PartialParseError):
            parse_skip_dirs("## Skip directories\n\nnone\n")

    def test_excludes_without_a_prefix_raises(self):
        text = ("## Category A —\n\n| Pattern | Notes |\n|---|---|\n| `a/**/*.md` | excludes nothing |\n"
                + "".join(f"## Category {l} —\n\n| Pattern | Notes |\n|---|---|\n| `x{l}` | n |\n" for l in "BCDEF"))
        with self.assertRaises(PartialParseError):
            parse_exclusions(text)

    def test_missing_prompt_predicate_raises(self):
        with self.assertRaises(PartialParseError):
            parse_prompt_markers("## Skip directories\n- `x/`\n")

    def test_unknown_condition_raises(self):
        text = (
            "## Classification rules\n\n| # | Condition | Type |\n|---|---|---|\n"
            "| 1 | whenever it feels right | `x` |\n"
        )
        with self.assertRaises(PartialParseError):
            parse_classify_rules(text)

    def test_non_sequential_rows_raise(self):
        text = (
            "## Classification rules\n\n| # | Condition | Type |\n|---|---|---|\n"
            "| 1 | fallback | `a` |\n| 3 | fallback | `b` |\n"
        )
        with self.assertRaises(PartialParseError):
            parse_classify_rules(text)


class TestGlobMatcher(unittest.TestCase):
    def test_double_star_spans_segments(self):
        self.assertTrue(glob_match("commands/a/b.md", "commands/**/*.md"))
        self.assertTrue(glob_match("commands/x.md", "commands/**/*.md"))

    def test_single_star_stops_at_separator(self):
        self.assertFalse(glob_match("a/b.md", "*.md"))
        self.assertTrue(glob_match("b.md", "*.md"))

    def test_leading_double_star_matches_at_root(self):
        self.assertTrue(glob_match("agents/a.md", "**/agents/*.md"))
        self.assertTrue(glob_match("fw/agents/a.md", "**/agents/*.md"))


class TestDiscovery(FixtureCase):
    """Discovery executed over a real tree — not a check that headings exist."""

    def test_every_category_discovers_something(self):
        found = {letter for _, letter, _ in self.raw}
        self.assertEqual(found, set("ABCDEF"), f"categories with no discovered file: {set('ABCDEF') - found}")

    def test_every_pattern_branch_has_a_fixture(self):
        # The coverage obligation: a pattern with no fixture is a pattern the suite cannot defend.
        used = {pattern for _, _, pattern in self.raw}
        for letter, patterns in self.categories.items():
            for pattern in patterns:
                with self.subTest(category=letter, pattern=pattern):
                    self.assertIn(pattern, used, f"no fixture exercises {letter}:{pattern}")

    def test_skip_directories_are_skipped(self):
        for skip in self.skip_dirs:
            with self.subTest(skip=skip):
                bait = f"{skip.strip('/')}/pkg/CLAUDE.md"
                self.assertNotIn(bait, [p for p, _, _ in self.raw])

    def test_gitkeep_is_never_discovered(self):
        self.assertEqual([p for p, _, _ in self.raw if p.endswith(".gitkeep")], [])

    def test_raw_records_show_the_root_claude_md_matching_twice(self):
        # Pre-dedup multiplicity is the evidence; a set here would erase it.
        matches = [(p, c, pat) for p, c, pat in self.raw if p == "CLAUDE.md"]
        self.assertGreaterEqual(len(matches), 2, f"expected CLAUDE.md to match >1 pattern, got {matches}")

    def test_dedup_collapses_the_root_claude_md_to_one_record(self):
        # And the post-dedup side must be an ordered list, or the collapse is unproven.
        matches = [r for r in self.deduped if r[0] == "CLAUDE.md"]
        self.assertEqual(len(matches), 1)

    def test_dedup_preserves_order_and_drops_only_duplicates(self):
        self.assertEqual([r[0] for r in self.deduped], list(dict.fromkeys(p for p, _, _ in self.raw)))

    def test_shared_partial_matches_the_shared_pattern_not_the_command_pattern(self):
        matched = [pat for p, _, pat in self.deduped if p == "commands/shared/p.md"]
        self.assertEqual(len(matched), 1)
        self.assertIn("shared", matched[0])

    def test_first_party_skill_asset_is_not_category_d(self):
        cats = [c for p, c, _ in self.deduped if p == "skills/s/references/ref.md"]
        self.assertNotIn("D", cats, "a first-party skill asset was filed as a non-plugin framework")

    def test_non_plugin_framework_skill_is_still_category_d(self):
        cats = [c for p, c, _ in self.deduped if p == "fw/skills/z.md"]
        self.assertEqual(cats, ["D"], "the guard is over-broad — genuine framework skills must stay D")

    def test_qualifying_template_is_discovered_and_plain_one_is_not(self):
        paths = [p for p, _, _ in self.deduped]
        self.assertIn("templates/prompt-ish.md", paths)
        self.assertNotIn("templates/plain.md", paths)

    def test_category_f_resolves_through_a_redirected_home(self):
        found = [p for p, c, _ in self.deduped if c == "F"]
        self.assertEqual(len(found), 2, f"category F should find both memory files, got {found}")


class TestClassifierDirect(unittest.TestCase):
    """Paths handed straight to classify — these are NOT discovery output.

    Asserting them through the composed test would be vacuous: `docs/schema.json` matches no
    `.md`-scoped category-E branch and `templates/plain.md` fails the content qualifier, so neither
    ever reaches classification that way.
    """

    @classmethod
    def setUpClass(cls):
        cls.rules = parse_classify_rules()

    def _type(self, path):
        return classify(path, self.rules)

    def test_json_under_docs_stays_document(self):
        self.assertEqual(self._type("docs/schema.json"), "document")

    def test_plain_template_stays_document(self):
        self.assertEqual(self._type("templates/plain.md"), "document")

    def test_framework_skill_md_is_a_skill(self):
        # Filename rule beats the framework rule; `framework-skill` is narrower than its name.
        self.assertEqual(self._type("other/skills/demo/SKILL.md"), "skill")

    def test_first_party_skill_asset_is_not_framework_skill(self):
        self.assertNotEqual(self._type("skills/s/references/ref.md"), "framework-skill")

    def test_shared_partial_precedes_command(self):
        self.assertEqual(self._type("commands/shared/discover.md"), "shared-partial")
        self.assertEqual(self._type("commands/score.md"), "command")

    def test_memory_path_classifies_by_segment(self):
        self.assertEqual(self._type("/Users/x/.claude/projects/p/memory/note.md"), "memory")

    def test_fallback_catches_the_unknown(self):
        self.assertEqual(self._type("random/thing.txt"), "document")


class TestComposed(FixtureCase):
    """Classification of discovery's output — the two partials tested as they compose."""

    def test_every_discovered_file_gets_exactly_one_type(self):
        for path, _, _ in self.deduped:
            with self.subTest(path=path):
                self.assertIsInstance(classify(path.replace("~/", ""), self.rules), str)

    def test_expected_types_for_representative_paths(self):
        expected = {
            "commands/shared/p.md": "shared-partial",
            "commands/x.md": "command",
            "agents/a.md": "agent",
            "skills/s/SKILL.md": "skill",
            ".claude-plugin/plugin.json": "manifest",
            ".claude-plugin/marketplace.json": "marketplace",
            "hooks/hooks.json": "hook-config",
            "CLAUDE.md": "claude-md",
            "pkg/CLAUDE.md": "claude-md",
            "docs/d.md": "design-doc",
            "README.md": "design-doc",
            "prompts/p.md": "prompt",
            "fw/agents/y.md": "framework-agent",
            "fw/skills/z.md": "framework-skill",
            "fw/manifest.json": "framework-manifest",
            "frameworks/f.md": "framework-config",
        }
        discovered = {p for p, _, _ in self.deduped}
        for path, want in expected.items():
            with self.subTest(path=path):
                self.assertIn(path, discovered, "fixture regressed out of discovery")
                self.assertEqual(classify(path, self.rules), want)


class TestScopeParse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forms = parse_scope_forms()

    def test_documented_scope_forms(self):
        for token in ("(empty)", "staged", "commit -N", "path"):
            with self.subTest(token=token):
                self.assertTrue(
                    any(token in key for key in self.forms),
                    f"scope form {token!r} missing from the grammar",
                )

    def test_full_is_absent(self):
        # `--full` is an audit-depth flag stripped by the caller before scope parsing.
        self.assertNotIn("--full", " ".join(self.forms))

    def test_trivial_change_gate_is_documented(self):
        self.assertIn("trivial", _read("scope-parse").lower())


class TestPluginDiscover(unittest.TestCase):
    """Baseline manifest validation, exercised as behaviour rather than as words."""

    @classmethod
    def setUpClass(cls):
        cls.outcomes = parse_manifest_outcomes()

    def test_four_manifest_conditions_are_specified(self):
        for condition in ("valid", "missing", "malformed", "name"):
            with self.subTest(condition=condition):
                self.assertTrue(
                    any(condition in key for key in self.outcomes),
                    f"no documented outcome for a {condition} manifest",
                )

    def test_missing_and_malformed_stop(self):
        for key, outcome in self.outcomes.items():
            if "missing manifest" in key or "malformed" in key:
                with self.subTest(key=key):
                    self.assertIn("stop", outcome)

    def test_missing_name_reports_a_finding_without_stopping(self):
        row = next(v for k, v in self.outcomes.items() if "name" in k)
        self.assertIn("finding", row)
        self.assertNotIn("stop", row)

    def test_comprehensive_checks_are_deferred_to_the_validator(self):
        # The boundary: baseline here, manifest-vs-disk and frontmatter elsewhere.
        text = _read("plugin-discover").lower()
        self.assertIn("f4.4", text)


class TestArtifactDiscipline(unittest.TestCase):
    def test_all_four_partials_exist_with_frontmatter(self):
        for name, path in PARTIALS.items():
            with self.subTest(partial=name):
                self.assertTrue(path.exists(), f"missing {path.relative_to(REPO_ROOT)}")
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"), "no YAML frontmatter")
                self.assertIn("user-invocable: false", text, "partials are not commands")

    def test_each_partial_states_the_untrusted_input_rule(self):
        for name, path in PARTIALS.items():
            with self.subTest(partial=name):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("untrusted", text)
                self.assertIn("vibe-core", text)

    def test_gitkeep_exclusion_is_documented(self):
        # Document-conformance, not behaviour: no retained glob matches a `.gitkeep`, so no
        # behavioural test can distinguish a partial that states this rule from one that omits it.
        self.assertIn(".gitkeep", _read("discover"))

    def test_no_partial_names_a_versioned_model_id(self):
        for name, path in PARTIALS.items():
            with self.subTest(partial=name):
                text = path.read_text(encoding="utf-8")
                self.assertIsNone(re.search(r"\bgpt-[0-9]|\bgemini-[0-9]|\bo[0-9]-", text))


if __name__ == "__main__":
    unittest.main()
