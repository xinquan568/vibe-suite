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
    for name in ("discover", "classify", "scope-parse", "plugin-discover",
                 "model-selection", "fallback")
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
    """Glob -> excluded path prefix, from the dedicated `Excludes` column.

    A column, not prose. Scraping the word "excludes" out of a Notes cell made the executable rule
    depend on wording: a rephrase, a negation or a second prefix would silently change behaviour.
    """
    text = _read("discover") if text is None else text
    exclusions = {}
    for letter in "ABCDEF":
        rows = _table_after(text, f"## Category {letter} —", "discover.md")
        for row in rows:
            if len(row) < 3:
                raise PartialParseError(
                    f"discover.md category {letter}: expected Pattern|Excludes|Notes, got {row!r}"
                )
            cell = row[1].strip()
            if cell in ("", "—", "-"):
                continue
            prefixes = _ticked(cell)
            if len(prefixes) != 1:
                raise PartialParseError(
                    f"discover.md category {letter}: Excludes must hold exactly one backticked "
                    f"prefix, got {cell!r}"
                )
            for glob in _ticked(row[0]):
                exclusions[glob] = prefixes[0]
    return exclusions


def parse_content_qualified(text=None):
    """Globs whose Notes cell marks them content-qualified, from `discover.md`."""
    text = _read("discover") if text is None else text
    qualified = set()
    for letter in "ABCDEF":
        for row in _table_after(text, f"## Category {letter} —", "discover.md"):
            # Notes is the third column now that Excludes is structured (finding 7).
            if len(row) > 2 and "content-qualified" in row[2].lower():
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
    order = [p.strip() for p in match.group(1).split("→")]
    if order != list("ABCDEF"):
        raise PartialParseError(f"discover.md: precedence must be exactly A→B→C→D→E→F, got {order}")
    return order


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
    rules, _is_fallback = [], {}
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
        _is_fallback[number] = row[1].strip() == "fallback"
        rules.append((number, _parse_condition(row[1], number), types[0]))
    if not rules:
        raise PartialParseError("classify.md: empty rule set")
    if [n for n, _, _ in rules] != list(range(1, len(rules) + 1)):
        raise PartialParseError("classify.md: row numbers are not 1..N in order")
    fallbacks = [n for n, _, _ in rules if _is_fallback[n]]
    if fallbacks != [len(rules)]:
        raise PartialParseError(
            f"classify.md: expected exactly one fallback, as the last row; found rows {fallbacks}"
        )
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


def parse_inventory_classes(text=None):
    """Inventory class -> (glob, expected frontmatter), from `plugin-discover.md`."""
    text = _read("plugin-discover") if text is None else text
    classes = {}
    for row in _table_after(text, "## Artifact inventory", "plugin-discover.md"):
        globs = _ticked(row[1])
        if not globs:
            raise PartialParseError(f"plugin-discover.md: inventory row without a glob: {row!r}")
        classes[row[0].strip().lower()] = (globs[0], row[2].strip())
    if not classes:
        raise PartialParseError("plugin-discover.md: empty artifact inventory")
    return classes


def parse_crossref_edges(text=None):
    """Ordered edge names from `plugin-discover.md`'s cross-reference list."""
    text = _read("plugin-discover") if text is None else text
    idx = text.find("## Cross-reference map")
    if idx < 0:
        raise PartialParseError("plugin-discover.md: no '## Cross-reference map' section")
    edges = []
    for line in text[idx:].splitlines():
        if match := re.match(r"^\d+\.\s+\*\*(.+?)\*\*", line.strip()):
            edges.append(match.group(1).strip().lower())
        elif line.startswith("## ") and edges:
            break
    if not edges:
        raise PartialParseError("plugin-discover.md: no cross-reference edges listed")
    return edges


def parse_never_trivial(text=None):
    """The never-trivial guards from `scope-parse.md`."""
    text = _read("scope-parse") if text is None else text
    idx = text.find("**Never trivial when ANY")
    if idx < 0:
        raise PartialParseError("scope-parse.md: no never-trivial guard list")
    guards = []
    for line in text[idx:].splitlines()[1:]:
        stripped = line.strip()
        if stripped.startswith("- "):
            guards.append(stripped[2:].lower())
        elif stripped.startswith("**") and guards:
            break
    if not guards:
        raise PartialParseError("scope-parse.md: never-trivial list is empty")
    return guards


def resolve_hook_edges(plugin_root, hooks_json):
    """Resolve Hook -> script edges, as `plugin-discover.md` specifies.

    Executable, unlike the rest of that partial: the edge is a path in a JSON `command` field and
    either resolves on disk or does not. A dangling hook script registers cleanly and fails only
    when the event fires, which is why it gets a real test rather than a prose check.
    """
    edges = []
    for hook in json.loads(hooks_json):
        command = hook.get("command", "")
        script = command.split()[-1] if command else ""
        edges.append((script, (Path(plugin_root) / script).exists() if script else False))
    return edges


def parse_manifest_outcomes(text=None):
    """Manifest condition -> outcome, from `plugin-discover.md`."""
    text = _read("plugin-discover") if text is None else text
    outcomes = {}
    for row in _table_after(text, "## Manifest validation", "plugin-discover.md"):
        outcomes[row[0].strip().lower()] = row[1].strip().lower()
    if not outcomes:
        raise PartialParseError("plugin-discover.md: empty manifest-validation table")
    return outcomes


# ------------------------------------------------------------------- E0.4 engine selection


ACTION_TOKENS = frozenset({"USE_VALUE", "DEFER"})


def parse_priority_ladder(text=None):
    """Ordered (source, present_when, action) rows from `model-selection.md`.

    The action column is a **closed** token set. An unrecognised token raises rather than being
    tolerated: a permissive parser would let a partial carry a model literal here, which is the
    pinned default P9 exists to forbid.
    """
    text = _read("model-selection") if text is None else text
    rows = []
    for row in _table_after(text, "## Priority ladder", "model-selection.md"):
        if len(row) < 3:
            raise PartialParseError(f"model-selection.md: ladder row needs 3 columns: {row!r}")
        action = row[2].strip().strip("`")
        if action not in ACTION_TOKENS:
            raise PartialParseError(
                f"model-selection.md: unknown action {action!r}; expected one of {sorted(ACTION_TOKENS)}"
            )
        rows.append((row[0].strip().strip("`"), row[1].strip(), action))
    if not rows:
        raise PartialParseError("model-selection.md: empty priority ladder")
    if rows[-1][2] != "DEFER":
        raise PartialParseError("model-selection.md: the terminal ladder action must be DEFER")
    return rows


def resolve(ladder, supplied):
    """Execute the parsed ladder over a mapping of source -> supplied value.

    Reads the **action column**, deliberately. A resolver keyed on row position would return the
    same answer for every well-formed table and so could not detect a wrong action.
    """
    for source, _present_when, action in ladder:
        value = supplied.get(source)
        if value is None:
            continue
        if action == "USE_VALUE":
            return value
        if action == "DEFER":
            return "DEFER"
    return "DEFER"


def parse_lifecycle(text=None):
    """The staged `cross_model_audit_engine` default, as three parsed fields."""
    text = _read("model-selection") if text is None else text
    fields = {}
    for row in _table_after(text, "## Staged cross-model default", "model-selection.md"):
        if len(row) < 2:
            raise PartialParseError(f"model-selection.md: lifecycle row needs 2 columns: {row!r}")
        fields[row[0].strip().lower()] = row[1].strip()
    for required in ("pre-gate default", "graduation condition", "post-gate default"):
        if required not in fields:
            raise PartialParseError(f"model-selection.md: lifecycle missing {required!r}")
    return fields


def parse_config_schema(text=None):
    """key -> (type, allowed, default) from `model-selection.md`'s schema table."""
    text = _read("model-selection") if text is None else text
    schema = {}
    for row in _table_after(text, "## `.vibe-suite.md` keys", "model-selection.md"):
        if len(row) < 4:
            raise PartialParseError(f"model-selection.md: schema row needs 4 columns: {row!r}")
        schema[row[0].strip().strip("`")] = (row[1].strip(), row[2].strip(), row[3].strip())
    if not schema:
        raise PartialParseError("model-selection.md: empty config schema")
    return schema


def parse_fallback_hops(text=None):
    """Ordered hops from `fallback.md`."""
    text = _read("fallback") if text is None else text
    hops = []
    for row in _table_after(text, "## Fallback chain", "fallback.md"):
        if len(row) < 3:
            raise PartialParseError(f"fallback.md: hop row needs 3 columns: {row!r}")
        hops.append(tuple(c.strip() for c in row[:3]))
    if not hops:
        raise PartialParseError("fallback.md: empty chain")
    return hops


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


def normalise(path):
    """Normalise to the classifier's documented input contract.

    `classify.md` takes a scan-root-relative POSIX path, or a `~/`-prefixed home path for category F.
    An absolute filesystem path is a caller error: every anchored glob and every `not under` prefix
    would silently mismatch, so `/repo/agents/a.md` would classify `framework-agent` rather than
    `agent`. Rejecting is the fail-closed choice; guessing a scan root is not this partial's job.
    """
    if path.startswith("./"):
        path = path[2:]
    if path.startswith("/"):
        raise PartialParseError(
            f"absolute path {path!r}: classify takes scan-root-relative paths (or ~/ for memory)"
        )
    return path


def classify(path, rules):
    path = normalise(path)
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


# --------------------------------------------------------------------- independent oracle
#
# Written here, deliberately NOT derived from the partials. Every assertion above that iterates
# `parse_*()` output shares its oracle with the thing under test: delete the `.mcp.json` row and the
# coverage check simply stops requiring it. These tables are the second opinion. They are a copy of
# the *expectations*, not of the rules — the rules still live only in the partials.

REQUIRED_PATTERNS = {
    "A": [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "commands/**/*.md",
          "commands/shared/**/*.md", "agents/**/*.md", "skills/**/SKILL.md", "hooks/**/*.json",
          ".mcp.json", ".lsp.json", "settings.json"],
    "B": ["CLAUDE.md", ".claude/CLAUDE.md", "**/CLAUDE.md", ".claude/rules/**/*.md",
          ".claude/settings.json", ".claude/settings.local.json", ".claude/**/*.local.md",
          ".claude/commands/**/*.md"],
    "C": ["prompts/**/*.md", "templates/**/*.md", "**/system-prompt*.md", "**/*-prompt.md",
          "**/*_prompt.md"],
    "D": ["**/agents/*.md", "**/agents/*.yaml", "**/skills/*.md", "**/skills/**/*.md",
          "**/manifest.yaml", "**/manifest.json", "**/frameworks/**/*.md"],
    "E": ["docs/**/*.md", "dev-docs/**/*.md", "specs/**/*.md", "design/**/*.md", "plans/**/*.md",
          "decisions/**/*.md", "README.md", "CONTRIBUTING.md"],
    "F": ["~/.claude/projects/*/memory/*.md", "~/.claude/projects/*/memory/MEMORY.md"],
}

REQUIRED_SKIP_DIRS = ["node_modules/", ".git/", "target/", "dist/", "build/", "vendor/",
                      "__pycache__/", ".next/", ".venv/", ".cache/"]

REQUIRED_EXCLUSIONS = {"commands/**/*.md": "commands/shared/",
                       "**/skills/*.md": "skills/", "**/skills/**/*.md": "skills/"}

# fixture path -> (category, type). Independent of what the partials say.
EXPECTED = {
    ".claude-plugin/plugin.json": ("A", "manifest"),
    ".claude-plugin/marketplace.json": ("A", "marketplace"),
    "commands/x.md": ("A", "command"),
    "commands/shared/p.md": ("A", "shared-partial"),
    "agents/a.md": ("A", "agent"),
    "skills/s/SKILL.md": ("A", "skill"),
    "hooks/hooks.json": ("A", "hook-config"),
    ".mcp.json": ("A", "mcp-config"),
    ".lsp.json": ("A", "lsp-config"),
    "settings.json": ("A", "document"),
    "CLAUDE.md": ("B", "claude-md"),
    ".claude/CLAUDE.md": ("B", "claude-md"),
    "pkg/CLAUDE.md": ("B", "claude-md"),
    ".claude/rules/r.md": ("B", "rule"),
    ".claude/settings.json": ("B", "settings"),
    ".claude/settings.local.json": ("B", "settings"),
    ".claude/vibe.local.md": ("B", "plugin-config"),
    ".claude/commands/u.md": ("B", "user-command"),
    "prompts/p.md": ("C", "prompt"),
    "templates/prompt-ish.md": ("C", "document"),
    "lib/system-prompt.md": ("C", "prompt"),
    "x/review-prompt.md": ("C", "prompt"),
    "x/review_prompt.md": ("C", "prompt"),
    "fw/agents/y.md": ("D", "framework-agent"),
    "fw/agents/y.yaml": ("D", "framework-agent"),
    "fw/skills/z.md": ("D", "framework-skill"),
    "fw/skills/nested/z2.md": ("D", "framework-skill"),
    "fw/manifest.yaml": ("D", "framework-manifest"),
    "fw/manifest.json": ("D", "framework-manifest"),
    "frameworks/f.md": ("D", "framework-config"),
    "docs/d.md": ("E", "design-doc"),
    "dev-docs/d.md": ("E", "design-doc"),
    "specs/s.md": ("E", "design-doc"),
    "design/d.md": ("E", "design-doc"),
    "plans/p.md": ("E", "design-doc"),
    "decisions/d.md": ("E", "design-doc"),
    "README.md": ("E", "design-doc"),
    "CONTRIBUTING.md": ("E", "design-doc"),
}

# Scope forms and never-trivial guards the gate must carry, written independently.
# Scope form -> the exact resolution it must specify. Independent of the partial: a token-presence
# check let `staged` resolve to `git diff HEAD` and stayed green.
REQUIRED_SCOPE_RESOLUTIONS = {
    "(empty)": "git diff HEAD --name-only",
    "staged": "git diff --cached --name-only",
    "commit -1": "git diff HEAD~1 --name-only",
    "commit -N": "git diff HEAD~N --name-only",
}
REQUIRED_SCOPE_FORMS = list(REQUIRED_SCOPE_RESOLUTIONS) + ["path"]
REQUIRED_NEVER_TRIVIAL = ["logic", "security", "dependen", "runtime", "error handling"]
REQUIRED_INVENTORY_CLASSES = ["commands", "shared partials", "agents", "skills", "hooks",
                              "mcp config", "marketplace"]
REQUIRED_CROSSREF_EDGES = ["command → agent", "command → shared partial", "agent → skill",
                           "hook → script"]


class TestIndependentOracle(FixtureCase):
    """The partials must satisfy expectations written without reference to them."""

    def test_every_required_pattern_is_present(self):
        for letter, required in REQUIRED_PATTERNS.items():
            for pattern in required:
                with self.subTest(category=letter, pattern=pattern):
                    self.assertIn(pattern, self.categories[letter],
                                  f"{letter} lost a required pattern — deleting a row must fail here")

    def test_no_extra_patterns_smuggled_in(self):
        for letter, required in REQUIRED_PATTERNS.items():
            with self.subTest(category=letter):
                self.assertEqual(self.categories[letter], required,
                                 "pattern set or order diverged from the specification")

    def test_every_required_skip_dir_is_present(self):
        self.assertEqual(self.skip_dirs, REQUIRED_SKIP_DIRS)

    def test_required_exclusions_are_declared(self):
        self.assertEqual(self.exclusions, REQUIRED_EXCLUSIONS)

    def test_expected_category_and_type_for_every_fixture(self):
        actual = {path: cat for path, cat, _ in self.deduped}
        for path, (want_cat, want_type) in EXPECTED.items():
            with self.subTest(path=path):
                self.assertEqual(actual.get(path), want_cat, "wrong category")
                self.assertEqual(classify(path, self.rules), want_type, "wrong type")

    def test_plain_template_is_not_discovered(self):
        self.assertNotIn("templates/plain.md", [p for p, _, _ in self.deduped])


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

    def test_dedup_keeps_the_first_complete_record_not_merely_one_path(self):
        # Comparing paths (or paths and categories) proves only that a collapse happened. First-match
        # -wins says *which* record survives, so the whole tuple must be compared: a mutant keeping
        # the later `**/CLAUDE.md` match passes a path-only assertion.
        first = next(r for r in self.raw if r[0] == "CLAUDE.md")
        kept = [r for r in self.deduped if r[0] == "CLAUDE.md"]
        self.assertEqual(kept, [first])
        self.assertEqual(first[2], "CLAUDE.md", "the root pattern should win, not `**/CLAUDE.md`")

    def test_dedup_keeps_the_first_complete_record_for_every_path(self):
        firsts = {}
        for record in self.raw:
            firsts.setdefault(record[0], record)
        self.assertEqual(self.deduped, [firsts[path] for path in dict.fromkeys(p for p, _, _ in self.raw)])

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
        # Category F paths arrive `~/`-prefixed, which is the documented contract.
        self.assertEqual(self._type("~/.claude/projects/p/memory/note.md"), "memory")

    def test_dot_relative_paths_are_normalised(self):
        # `./agents/a.md` must not fall through to the framework rules.
        self.assertEqual(self._type("./agents/a.md"), "agent")
        self.assertEqual(self._type("./commands/x.md"), "command")

    def test_absolute_paths_are_rejected_not_misclassified(self):
        # An anchored glob silently mismatches an absolute path: `/repo/agents/a.md` would have
        # classified `framework-agent`, and `/repo/skills/s/references/ref.md` would have bypassed
        # the `not under skills/` guard entirely. Failing loudly is the fail-closed choice.
        for path in ("/repo/agents/a.md", "/repo/commands/x.md",
                     "/repo/skills/s/references/ref.md", "/repo/docs/d.md"):
            with self.subTest(path=path):
                with self.assertRaises(PartialParseError):
                    self._type(path)

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


class TestScopeParseBehaviour(unittest.TestCase):
    """The gate is an instruction to an agent, so the strongest available check is that every
    required rule is present — asserted against a list written independently in this module, not
    read back out of the partial."""

    def test_every_required_scope_form_is_present(self):
        forms = " ".join(parse_scope_forms())
        for token in REQUIRED_SCOPE_FORMS:
            with self.subTest(token=token):
                self.assertIn(token, forms)

    def test_each_scope_form_resolves_to_the_right_command(self):
        # The check that distinguishes a correct table from a plausible one.
        forms = parse_scope_forms()
        for token, want in REQUIRED_SCOPE_RESOLUTIONS.items():
            with self.subTest(token=token):
                row = next((v for k, v in forms.items() if token in k), None)
                self.assertIsNotNone(row, f"scope form {token!r} missing")
                self.assertIn(want, row, f"{token!r} must resolve via `{want}`")

    def test_a_path_scope_does_not_resolve_through_git(self):
        forms = parse_scope_forms()
        row = next(v for k, v in forms.items() if "path" in k)
        self.assertNotIn("git diff", row, "a path is read directly, not diffed")

    def test_every_never_trivial_guard_is_present(self):
        guards = " ".join(parse_never_trivial())
        for required in REQUIRED_NEVER_TRIVIAL:
            with self.subTest(guard=required):
                self.assertIn(required, guards, f"the gate lost its {required!r} guard")

    def test_dependency_churn_is_never_trivial(self):
        # The regression this guards: an earlier draft listed lockfile churn as *trivial*, so a
        # dependency change could be skipped silently. A lockfile is the most mechanical-looking
        # representation of exactly the change the gate must not skip.
        text = _read("scope-parse").lower()
        idx = text.find("**never trivial when any")
        self.assertGreater(idx, 0)
        self.assertIn("depend", text[idx:idx + 800])
        trivial_block = text[text.find("**trivial only when all"):idx]
        self.assertNotIn("lockfile", trivial_block)

    def test_the_gate_asks_before_skipping(self):
        text = _read("scope-parse")
        self.assertIn("AskUserQuestion", text)
        self.assertIn("Analyze anyway", text)

    def test_a_five_line_threshold_is_stated(self):
        self.assertRegex(_read("scope-parse"), r"≤\s*5\s+lines")


class TestPluginDiscoverBehaviour(unittest.TestCase):
    """Inventory globs and hook edges, executed against a fixture plugin."""

    @classmethod
    def setUpClass(cls):
        cls.classes = parse_inventory_classes()
        cls.edges = parse_crossref_edges()
        cls.tmp = tempfile.mkdtemp(prefix="vibe5-plugin-")
        cls.hooks = json.dumps([
            {"event": "PostToolUse", "command": "scripts/present.sh"},
            {"event": "Stop", "command": "scripts/missing.sh"},
        ])
        for rel, body in {
            ".claude-plugin/plugin.json": '{"name":"fixture"}',
            "commands/c.md": "---\ndescription: c\n---\n",
            "commands/shared/s.md": "---\nuser-invocable: false\n---\n",
            "agents/a.md": "---\ndescription: a\n---\n",
            "skills/k/SKILL.md": "# k\n",
            "hooks/hooks.json": cls.hooks,
            ".mcp.json": '{"mcpServers":{}}',
            ".claude-plugin/marketplace.json": '{"plugins":[]}',
            "scripts/present.sh": "#!/bin/sh\n",
        }.items():
            path = Path(cls.tmp) / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_required_inventory_class_is_declared(self):
        for required in REQUIRED_INVENTORY_CLASSES:
            with self.subTest(cls=required):
                self.assertIn(required, self.classes)

    def test_each_inventory_glob_finds_its_fixture(self):
        for name, (glob, _) in self.classes.items():
            with self.subTest(cls=name):
                found = [
                    path.relative_to(self.tmp).as_posix()
                    for path in Path(self.tmp).rglob("*")
                    if path.is_file() and glob_match(path.relative_to(self.tmp).as_posix(), glob)
                ]
                self.assertTrue(found, f"inventory glob {glob!r} for {name!r} matched nothing")

    def test_every_required_crossref_edge_is_declared(self):
        joined = " ".join(self.edges)
        for required in REQUIRED_CROSSREF_EDGES:
            with self.subTest(edge=required):
                self.assertIn(required, joined, f"cross-reference map lost the {required!r} edge")

    def test_hook_edges_resolve_and_dangle_correctly(self):
        resolved = resolve_hook_edges(self.tmp, self.hooks)
        self.assertEqual(resolved, [("scripts/present.sh", True), ("scripts/missing.sh", False)])

    def test_a_dangling_hook_script_is_detectable(self):
        dangling = [script for script, ok in resolve_hook_edges(self.tmp, self.hooks) if not ok]
        self.assertEqual(dangling, ["scripts/missing.sh"])


# --------------------------------------------------- E0.4 independent oracle (vibe-6)
#
# Written here, not read back from the partials — the vibe-5 lesson. Deleting a row from a partial
# must fail a test, not quietly remove the obligation.

REQUIRED_ENGINE_VALUES = ["claude", "codex", "agy", "both"]
REQUIRED_LADDER = [("user choice", "USE_VALUE"), (".vibe-suite.md", "USE_VALUE"),
                   ("tool default", "DEFER")]
REQUIRED_LIFECYCLE = {"pre-gate default": "codex", "post-gate default": "agy"}
REQUIRED_CONFIG_KEYS = ["engine", "cross_model_audit_engine", "reviewer_backend", "reviewer_model"]
REQUIRED_HOPS = [("agy", "codex"), ("codex", "manual")]


class TestPriorityLadder(unittest.TestCase):
    """The ladder is *executed*, not inspected — and three mutants separate the ways a test could
    pass without reading the action column."""

    @classmethod
    def setUpClass(cls):
        cls.ladder = parse_priority_ladder()

    def test_ladder_matches_the_independent_expectation(self):
        self.assertEqual([(s, a) for s, _, a in self.ladder], REQUIRED_LADDER)

    def test_no_row_carries_a_model_literal(self):
        # The pinned-default loophole: a literal in any action cell.
        for source, _, action in self.ladder:
            with self.subTest(source=source):
                self.assertIn(action, ACTION_TOKENS)

    def test_user_choice_wins(self):
        self.assertEqual(resolve(self.ladder, {"user choice": "codex",
                                               ".vibe-suite.md": "agy"}), "codex")

    def test_config_wins_when_no_user_choice(self):
        self.assertEqual(resolve(self.ladder, {".vibe-suite.md": "agy"}), "agy")

    def test_two_distinct_tool_default_canaries_propagate_by_identity(self):
        # Rules out a hard-coded echo: the terminal action must pass *the supplied* value through.
        for canary in ("CANARY-ALPHA", "CANARY-BETA"):
            with self.subTest(canary=canary):
                self.assertEqual(resolve(self.ladder, {"tool default": canary}), "DEFER")

    def test_no_input_at_all_yields_defer_not_a_value(self):
        self.assertEqual(resolve(self.ladder, {}), "DEFER")

    # ---- mutants: each defeats a different way of passing without reading the action ----

    def _mutate(self, old, new):
        """Apply a mutation and assert it actually changed the text.

        A `str.replace` that matches nothing returns the original silently, so an unapplied mutant
        would test the unmutated partial. Here that surfaces as a failure rather than a pass, but
        only because `assertRaises` gets nothing — assert the application directly instead.
        """
        text = _read("model-selection")
        mutated = text.replace(old, new)
        self.assertNotEqual(text, mutated, f"mutation did not apply: {old!r}")
        return mutated

    def test_mutant_literal_in_terminal_action_is_rejected(self):
        text = self._mutate("| `tool default` | always | `DEFER` |",
                            "| `tool default` | always | `sonnet` |")
        with self.assertRaises(PartialParseError):
            parse_priority_ladder(text)

    def test_mutant_unknown_action_token_is_rejected(self):
        text = self._mutate("| `tool default` | always | `DEFER` |",
                            "| `tool default` | always | `WHATEVER` |")
        with self.assertRaises(PartialParseError):
            parse_priority_ladder(text)

    def test_mutant_legal_action_flip_preserving_row_order_changes_the_result(self):
        # The discriminating one. Flipping the config row's action leaves shape and ordering
        # identical, so a resolver keyed on row position returns the config value either way. Only
        # a resolver that reads the action column sees the difference.
        text = self._mutate("| `.vibe-suite.md` | key is set | `USE_VALUE` |",
                            "| `.vibe-suite.md` | key is set | `DEFER` |")
        mutant = parse_priority_ladder(text)
        self.assertEqual([s for s, _, _ in mutant], [s for s, _, _ in self.ladder],
                         "the mutant must preserve row order, or it proves nothing")
        self.assertEqual(resolve(self.ladder, {".vibe-suite.md": "agy"}), "agy")
        self.assertEqual(resolve(mutant, {".vibe-suite.md": "agy"}), "DEFER")


class TestStagedDefault(unittest.TestCase):
    def test_lifecycle_fields_match_the_independent_expectation(self):
        fields = parse_lifecycle()
        for key, want in REQUIRED_LIFECYCLE.items():
            with self.subTest(key=key):
                self.assertIn(want, fields[key])

    def test_graduation_condition_names_the_contract_gate(self):
        self.assertIn("contract", parse_lifecycle()["graduation condition"].lower())

    def test_lifecycle_is_parsed_independently_of_the_vocabulary(self):
        # A value set cannot distinguish a v1 default from a post-flip one, which is why this has
        # its own table and its own parser.
        self.assertNotEqual(parse_lifecycle()["pre-gate default"],
                            parse_lifecycle()["post-gate default"])


class TestEngineVocabulary(unittest.TestCase):
    def test_engine_values(self):
        schema = parse_config_schema()
        for value in REQUIRED_ENGINE_VALUES:
            with self.subTest(value=value):
                self.assertIn(value, schema["engine"][1])

    def test_every_required_key_is_declared(self):
        schema = parse_config_schema()
        for key in REQUIRED_CONFIG_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, schema)

    def test_reviewer_backend_and_model_are_separate_keys(self):
        schema = parse_config_schema()
        self.assertIn("reviewer_backend", schema)
        self.assertIn("reviewer_model", schema)

    def test_reviewer_model_has_an_open_domain(self):
        # A discovered model cannot have a closed set; asserting one would be a lie the schema
        # would then have to keep.
        allowed = parse_config_schema()["reviewer_model"][1].lower()
        self.assertTrue("open" in allowed or "dynamic" in allowed, allowed)

    def test_both_is_documented_as_having_no_model_of_its_own(self):
        text = _read("model-selection").lower()
        self.assertIn("no model of its own", text)
        self.assertIn("independently", text)


class TestFallbackChain(unittest.TestCase):
    def test_hops_are_ordered_as_expected(self):
        hops = parse_fallback_hops()
        self.assertEqual([(h[0].strip("`"), h[1].strip("`")) for h in hops], REQUIRED_HOPS)

    def test_every_hop_carries_actionable_restoration_guidance(self):
        # F9.5 requires the user be told how to restore. A pointer to an unbuilt command does not.
        for hop in parse_fallback_hops():
            with self.subTest(hop=hop[0]):
                guidance = hop[2].lower()
                self.assertTrue(any(k in guidance for k in ("path", "install", "auth")), guidance)

    def test_the_chain_declares_itself_post_gate_only(self):
        # Without this an unconditional chain would pass while contradicting AC-9(b).
        text = _read("fallback").lower()
        self.assertIn("post-gate", text)
        self.assertIn("graduation", text)

    def test_the_pre_gate_refusal_is_not_described_here(self):
        # It belongs to E1.7; describing it here would misrepresent a refusal as a degradation.
        self.assertNotIn("errors with a pointer", _read("fallback").lower())


class TestArtifactDiscipline(unittest.TestCase):
    def test_classify_documents_its_path_contract(self):
        # The rule has to live in the partial, not only in this module's normalise(). A test that
        # enforces a contract the shipped artifact does not state is checking its own invention.
        text = _read("classify")
        self.assertIn("relative to the scan root", text)
        self.assertIn("absolute filesystem path is a caller error", text)
        self.assertIn("`./`", text)

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
