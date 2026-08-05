#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""AC-1 merge-completeness check: every source artifact is claimed by `docs/disposition.yaml`.

§6 of the merge proposal maps every source function to where it landed in vibe-suite. This is the
disk-driven check that keeps that map honest — "so an artifact missing from this map fails the build
rather than passing silently".

Four things make it a real check rather than a self-referential one.

**Coverage is bidirectional.** Every allowlisted path must be claimed exactly once, *and* every
claimed path must exist and be allowlisted. A stale row naming a path that no longer exists is
exactly as damaging as a missing row, because either way the map has stopped describing the trees.

**The §6 row inventory is a constant here, not derived from the file being checked.** Otherwise
deleting a row would delete its own test, and a row claiming no allowlisted path — a `D` row — could
vanish unnoticed. AC-1 calls this out by name: "disk-driven, not self-referential".

**The pins are constants here too.** Comparing a manifest's commit to `disposition.yaml`'s commit
proves only that two editable files agree; both can be changed to the same wrong value. Re-pinning
must be a code change.

**The allowlist and exclusion list are transcribed from AC-1, and exist once.** They are applied
here and nowhere else — the manifests are unfiltered on purpose.
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- pins
# Full commits for the short forms the issue names. Constants, so re-pinning is reviewable.
PINS = {
    "cc-suite":         "bb605ec441862e1d35f182af5d9f0503c7d27d79",
    "grill-for-claude": "938b1e83b2135bc923b2d7312f82b654a76539c5",
    "nlpm":             "4ef75d4aa1626c0d06336f01227b6c07cfbf809f",
}

# --------------------------------------------------------------------------- AC-1's two lists
# Transcribed from §10 AC-1. This is the single definition; nothing else filters.
ALLOWLIST = (
    "commands/**/*.md",
    "agents/**/*.md",
    "skills/**/SKILL.md",          # source skills nest one level deeper in cc-suite and nlpm
    "hooks/**",
    "scripts/**/*",                # including nested libraries, e.g. scripts/lib/*.mjs
    "auditor/scripts/**/*",
    "auditor/prompts/**",          # §6 nlpm: "auditor pipeline workflows + prompts + SCHEMAS.md + registry"
    "auditor/registry/**",
    "auditor/SCHEMAS.md",
    ".nlpm-test/**",               # §6 nlpm: "test + tester + .nlpm-test specs" (K, F4.5)
    "analysis/scripts/**",         # §6 nlpm: extract-vocabulary.py ...
    "analysis/vocabulary-design-principles.md",   # ... + the vocabulary-design principles
    "bin/*",
    ".github/workflows/**",        # "workflows"
    "templates/**",
    "prompts/**",
    "schemas/**",
    ".claude-plugin/**",
    ".codex-plugin/**",
    "codex/**",                    # codex-mirror trees, incl. AGENTS files
    "site/**",
    "README.md", "CLAUDE.md", "AGENTS.md", "GEMINI.md", "PRIVACY.md", "package.json",
    "nlpm-badge.json",             # §6 gives it a disposition in two trees, so it must be claimable
)

#: Directory names excluded wherever they appear as a path component.
EXCLUDED_DIRS = (".git", "__pycache__", "node_modules")

#: ".DS_Store and other OS junk", pinned to exact basenames.
OS_JUNK = (".DS_Store", "Thumbs.db", "desktop.ini", ".Spotlight-V100", ".Trashes")

#: "generated reports" — the auditor's report corpus. NOT `nlpm-badge.json`: §6 lists that as a
#: source artifact with a disposition, so excluding it would make the map unable to claim something
#: §6 requires it to claim.
GENERATED_REPORTS = ("auditor/reports/**",)

#: "the §7A row-9 migrated ops data" — the corpora the migration tool publishes.
ROW9_OPS_DATA = (
    "auditor/reports/**", "auditor/exemplars/**", "auditor/audits/**", "auditor/logs/**",
    "auditor/findings.jsonl", "auditor/disagreements.jsonl", "auditor/vocab-advisories.jsonl",
    "case-studies/**",
)
# auditor/reports/** is excluded by two routes deliberately: removing either must not un-exclude it.

# --------------------------------------------------------------------------- expected counts
SKILL_COUNTS = {"cc-suite": 13, "nlpm": 17}
NESTED_SCRIPT_LIB_COUNTS = {("cc-suite", "scripts/lib/**"): 7, ("nlpm", "auditor/scripts/**"): 32}

#: §5 counts 12 workspace-skill resources, all roamex-era. The live trees hold 14: `issue2pr` gained
#: `profiles/vibe-suite.md` and `templates/vibe-suite-pr-body.md` for this project after the proposal
#: was written. 12 = 14 - 2. Asserted because AC-1 wants a count that fails loudly, and honest
#: because the difference is accounted for rather than absorbed.
WORKSPACE_RESOURCE_COUNT = 14

#: §6's five letters, plus the two compound forms it actually writes: row 19's "K/M" (partials,
#: some kept and some merged) and row 22's "M/K" (conventions merged, agent-design kept). A
#: single-letter rule would force a choice §6 declines to make.
DISPOSITIONS = frozenset(("K", "M", "R", "G", "D", "K/M", "M/K"))
_TARGET = re.compile(r"F[0-9]+\.[0-9]+$")
#: §6's "vibe-suite home" column is a function ID, several IDs, or — for three workspace rows — a
#: repository path. Encoding only the first would have forced those rows to name a function that
#: §6 does not give them.
#: Only these rows have a §6 home that is a repository path rather than a function. Allowing a path
#: anywhere else weakened the check everywhere to accommodate three rows.
PATH_TARGET_ROWS = frozenset(("workspace:09", "workspace:10", "workspace:12"))

#: A path target must actually look like a repository path — it needs a directory separator and a
#: file extension. Accepting any bare word would have let `target: nonsense` through, which is the
#: weakening that admitting path targets introduced.
_TARGET_PATH = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)+\.[A-Za-z0-9]+$")

#: vibe-128: the rows whose promised capability is scheduled rather than delivered — frozen HERE,
#: stage and expected anchors included, for the same reason the pins are constants: two editable
#: files agreeing proves nothing, so adding, renaming, re-staging, or re-anchoring a scheduled row
#: must be a change to this file, not a data edit. The live `scheduled:` rows must be a SUBSET of
#: these keys with stage and anchors matching exactly; a row graduating to `delivered:` is a
#: data-only change. Every anchor must be ABSENT from the tree — an anchor that exists means the
#: capability landed and the gate stays red until the row flips (self-expiry).
#: All five are Stage-S8 (F10.x build/auditor) capabilities; anchors are the artifacts S8 delivers.
SCHEDULED = {
    "nlpm:12": ("S8", ("bin/vibe-build-docs",)),
    "nlpm:13": ("S8", ("bin/vibe-build-case-studies-index", "bin/vibe-build-reference-md",
                       "bin/vibe-build-site-report-pages", "bin/vibe-build-vocab-data")),
    "nlpm:20": ("S8", ("auditor/SCHEMAS.md", "auditor/workflows", "auditor/prompts")),
    "nlpm:21": ("S8", ("auditor/scripts",)),
    "nlpm:23": ("S8", ("site",)),
}

#: The dispositions that promise a reimplementation and therefore must say where it landed.
#: G/R/D rows promise none, so the target columns are forbidden there outright.
PROMISING_DISPOSITIONS = frozenset(("K", "M", "K/M", "M/K"))


class CoverageError(Exception):
    """A failure that must fail CI."""


# --------------------------------------------------------------------------- glob
def _translate(pattern):
    """Anchored glob → regex.

    `fnmatch` is not usable here: its `*` crosses `/`, which would make `scripts/**/*` and
    `commands/**/*.md` mean something other than what AC-1's text says. The four tokens below are
    the whole language.
    """
    out, index = ["^"], 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out.append("(?:[^/]+/)*"); index += 3
        elif pattern.startswith("**", index):
            out.append(".*"); index += 2
        elif pattern[index] == "*":
            out.append("[^/]*"); index += 1
        elif pattern[index] == "?":
            out.append("[^/]"); index += 1
        else:
            out.append(re.escape(pattern[index])); index += 1
    out.append("$")
    return re.compile("".join(out))


_CACHE = {}


def matches(path, pattern):
    if pattern not in _CACHE:
        _CACHE[pattern] = _translate(pattern)
    return _CACHE[pattern].match(path) is not None


def matches_any(path, patterns):
    return any(matches(path, pattern) for pattern in patterns)


def is_excluded(path):
    parts = path.split("/")
    if any(part in EXCLUDED_DIRS for part in parts):
        return True
    base = parts[-1]
    if base in OS_JUNK or base.startswith("._"):
        return True
    return matches_any(path, GENERATED_REPORTS) or matches_any(path, ROW9_OPS_DATA)


def is_allowlisted(path):
    return matches_any(path, ALLOWLIST) and not is_excluded(path)


# --------------------------------------------------------------------------- §6 row inventory
# The 76 rows of §6, as stable IDs. A CONSTANT here rather than derived from disposition.yaml: if it
# were derived, deleting a row would delete its own test, and a row claiming no allowlisted path
# could vanish silently. This is what makes "removing any row fails CI" true for every row.
ROW_INVENTORY = tuple(
    [f"cc-suite:{n:02d}" for n in range(1, 31)] +          # 29 from §6 + one divergence (30)
    [f"grill-for-claude:{n:02d}" for n in range(1, 8)] +   # 7
    [f"nlpm:{n:02d}" for n in range(1, 26)] +              # 25
    [f"workspace:{n:02d}" for n in range(1, 15)]           # 14
)
#: §6 has 75 rows. `cc-suite:30` is a deliberate 76th: §6's cc-suite subsection has no row for that
#: tree's manifests and top-level docs, although grill and nlpm both do and AC-1 allowlists those
#: files. The divergence is carried here rather than papered over by absorbing §6's real rows into
#: neighbours — which is what produced three rounds of mistranscription.
assert len(ROW_INVENTORY) == 76, "§6's 75 rows plus cc-suite:30, the recorded divergence"

TREES = ("cc-suite", "grill-for-claude", "nlpm", "workspace")


# --------------------------------------------------------------------------- loading
def load_manifest(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    repo, commit, files = data.get("repo"), data.get("commit"), data.get("files")
    if repo not in PINS:
        raise CoverageError(f"{path}: unknown repo {repo!r}")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise CoverageError(f"{path}: commit must be 40 lowercase hex characters")
    if commit != PINS[repo]:
        raise CoverageError(
            f"{path}: commit {commit[:8]} is not the pinned {PINS[repo]} — re-pinning must be a "
            f"change to {Path(__file__).name}, not a data edit")
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise CoverageError(f"{path}: 'files' must be a list of strings")
    for entry in files:
        if entry.startswith("/") or ".." in entry.split("/") or "\\" in entry or entry != entry.strip():
            raise CoverageError(f"{path}: entry {entry!r} is not a clean relative POSIX path")
    if files != sorted(files):
        raise CoverageError(f"{path}: entries must be sorted")
    if len(files) != len(set(files)):
        raise CoverageError(f"{path}: entries must be unique")
    return repo, commit, files


def parse_disposition(text, source="docs/disposition.yaml"):
    """Parse the closed subset this file is written in.

    A dependency-free reader, for the same reason `config.py` has one: the repo ships no YAML
    library and CI must not need one. The subset is small and every departure from it is an error,
    so an unreadable line is a failure rather than a silent omission.
    """
    trees, mappings, current, section = {}, [], None, None
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #", 1)[0].rstrip() if " #" in raw else raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("trees:"):
            section = "trees"; continue
        if line.startswith("mappings:"):
            section = "mappings"; continue
        if line.startswith("version:"):
            if line.strip() != "version: 1":
                raise CoverageError(f"{source}:{number}: only 'version: 1' is supported")
            continue
        if section == "trees":
            match = re.fullmatch(r"  ([A-Za-z0-9._-]+): *\{commit: *([0-9a-f]{40}|null)\}", line)
            if not match:
                raise CoverageError(f"{source}:{number}: expected '  <tree>: {{commit: <sha|null>}}'")
            if match.group(1) in trees:
                raise CoverageError(f"{source}:{number}: duplicate tree key {match.group(1)!r}")
            trees[match.group(1)] = None if match.group(2) == "null" else match.group(2)
            continue
        if section != "mappings":
            raise CoverageError(f"{source}:{number}: content outside 'trees:' or 'mappings:'")
        if line.startswith("  - "):
            current = {"_line": number}
            mappings.append(current)
            line = "    " + line[4:]
        if current is None:
            raise CoverageError(f"{source}:{number}: mapping field before any '- ' item")
        match = re.fullmatch(r"    ([a-z_]+): *(.*)", line)
        if not match:
            raise CoverageError(f"{source}:{number}: expected '    <key>: <value>'")
        key, value = match.group(1), match.group(2).strip()
        if key in current:
            raise CoverageError(f"{source}:{number}: duplicate key {key!r} in one mapping")
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if inner:
                parts = [part.strip() for part in inner.split(",")]
                if any(not part for part in parts):
                    raise CoverageError(f"{source}:{number}: empty item in list for {key!r}")
                current[key] = parts
            else:
                current[key] = []
        else:
            current[key] = value
    return trees, mappings


# --------------------------------------------------------------------------- validation
def validate_schema(trees, mappings, function_ids):
    errors = []
    for tree in TREES:
        if tree not in trees:
            errors.append(f"trees: missing {tree!r}")
    for tree, commit in trees.items():
        if tree not in TREES:
            errors.append(f"trees.{tree}: not a declared tree")
        elif tree == "workspace":
            if commit is not None:
                errors.append("trees.workspace: must be null — it is walked live, not pinned")
        elif commit is None or not commit.startswith(PINS[tree]):
            errors.append(f"trees.{tree}: commit is not the pinned {PINS[tree]}")

    seen_rows = {}
    for mapping in mappings:
        where = f"docs/disposition.yaml:{mapping['_line']}"
        row = mapping.get("row")
        if not row:
            errors.append(f"{where}: missing 'row'"); continue
        if row in seen_rows:
            errors.append(f"{where}: duplicate row id {row!r} (also line {seen_rows[row]})")
        seen_rows[row] = mapping["_line"]
        if mapping.get("tree") not in TREES:
            errors.append(f"{where}: 'tree' must be one of {', '.join(TREES)}")
        disposition = mapping.get("disposition")
        if disposition not in DISPOSITIONS:
            errors.append(f"{where}: disposition {disposition!r} is not one of K M R G D")
        has_paths, has_roots = "paths" in mapping, "corpus_roots" in mapping
        if has_paths == has_roots:
            errors.append(f"{where}: exactly one of 'paths' or 'corpus_roots' is required")
        if has_paths and not mapping["paths"]:
            errors.append(f"{where}: 'paths' is empty — a row that claims nothing covers nothing")
        if has_roots and not mapping["corpus_roots"]:
            errors.append(f"{where}: 'corpus_roots' is empty")
        for key in mapping:
            if key not in ("row", "tree", "paths", "corpus_roots", "disposition", "target",
                           "note", "delivered", "scheduled", "expected", "_line"):
                errors.append(f"{where}: unknown key {key!r}")
        # vibe-128: the promise columns. Exactly one of the two forms on every promising row,
        # neither on G/R/D — a row that promises a capability must say where it landed or when.
        delivered, scheduled = mapping.get("delivered"), mapping.get("scheduled")
        expected = mapping.get("expected")
        if disposition in PROMISING_DISPOSITIONS:
            if (delivered is None) == (scheduled is None):
                errors.append(f"{where}: a promising row carries exactly one of 'delivered' or "
                              "'scheduled' — the promise either landed or has a stage")
            if (scheduled is None) != (expected is None):
                errors.append(f"{where}: 'scheduled' and 'expected' are required together")
            if delivered is not None and (not isinstance(delivered, list) or not delivered):
                errors.append(f"{where}: 'delivered' must be a non-empty list of artifact paths")
            if scheduled is not None and not isinstance(scheduled, str):
                errors.append(f"{where}: 'scheduled' must be a single stage id")
            if expected is not None and (not isinstance(expected, list) or not expected):
                errors.append(f"{where}: 'expected' must be a non-empty list of anchor paths")
            if isinstance(delivered, list) and delivered:
                source_paths = mapping.get("paths") if isinstance(mapping.get("paths"), list) else []
                # Where the artifact class is mechanically derivable, assert the semantic
                # correspondence, not bare existence: a kept command resurfaces as a command,
                # a kept skill as a skill, and a path-target row must deliver its §6 home.
                if disposition in ("K", "K/M") and source_paths:
                    if (all(matches(p, "commands/**/*.md") for p in source_paths)
                            and not any(matches(d, "commands/**/*.md") for d in delivered)):
                        errors.append(f"{where}: every source path is a command, but nothing in "
                                      "'delivered' is one — a kept command must resurface under "
                                      "commands/")
                    if (all(p.endswith("/SKILL.md") for p in source_paths)
                            and not any(d.endswith("/SKILL.md") for d in delivered)):
                        errors.append(f"{where}: every source path is a SKILL.md, but nothing in "
                                      "'delivered' is one")
                home = mapping.get("target")
                if row in PATH_TARGET_ROWS and isinstance(home, str):
                    if not any(d == home or d.endswith("/" + home) for d in delivered):
                        errors.append(f"{where}: the §6 home is the path {home!r} and "
                                      "'delivered' must include it")
        elif disposition in DISPOSITIONS:
            for key in ("delivered", "scheduled", "expected"):
                if key in mapping:
                    errors.append(f"{where}: {key!r} is forbidden on a {disposition} row — "
                                  "G/R/D rows promise no reimplementation")
        if disposition in ("K/M", "M/K") and not mapping.get("note"):
            errors.append(f"{where}: a compound disposition must carry a note saying which is which")
        if disposition == "D" and has_paths:
            errors.append(f"{where}: a D row describes data, so it uses 'corpus_roots'")
        if disposition and disposition != "D" and has_roots:
            errors.append(f"{where}: only a D row may use 'corpus_roots'")
        target = mapping.get("target")
        if isinstance(target, str) and " " in target:
            errors.append(f"{where}: target {target!r} must be a single value or a list")
        targets = target if isinstance(target, list) else ([target] if target else [])
        if disposition and disposition != "D":
            # §6's legend: "R retired with replacement noted" — the replacement is the point of an
            # R row, so a target is required for it too. Only D has no function ID.
            if not targets:
                errors.append(f"{where}: disposition {disposition} requires a 'target'")
            for one in targets:
                if _TARGET.fullmatch(one):
                    if one not in function_ids:
                        errors.append(f"{where}: target {one!r} is well-formed but is not one of "
                                      f"the {len(function_ids)} function IDs")
                elif row not in PATH_TARGET_ROWS:
                    errors.append(f"{where}: target {one!r} is not a function ID, and only "
                                  f"{', '.join(sorted(PATH_TARGET_ROWS))} may name a path")
                elif not _TARGET_PATH.fullmatch(one):
                    errors.append(f"{where}: target {one!r} is neither a function ID nor a path")
        elif targets:
            errors.append(f"{where}: a D row has no target")
        claimed_lists = [mapping.get("paths", []), mapping.get("corpus_roots", [])]
        claimed_lists += [value for value in (delivered, expected) if isinstance(value, list)]
        for path in (p for one in claimed_lists for p in one):
            if path.startswith("/") or ".." in path.split("/") or path != path.strip():
                errors.append(f"{where}: {path!r} is not a clean relative POSIX path")

    missing = [row for row in ROW_INVENTORY if row not in seen_rows]
    extra = [row for row in seen_rows if row not in ROW_INVENTORY]
    if missing:
        errors.append(f"§6 rows absent from the map: {', '.join(missing)} — §6 has "
                      f"{len(ROW_INVENTORY)} rows and every one must be encoded")
    if extra:
        errors.append(f"rows not in §6's inventory: {', '.join(sorted(extra))}")
    return errors


def load_workspace_manifest(path):
    """The workspace skills' snapshot — vendored, like the pinned trees, and for the same reason.

    They are the owner's own work and live in the *workspace*, not in this repository, in a
    directory that is not a git checkout. CI clones only vibe-suite, so it cannot reach them; a
    "walk the live filesystem" rule would silently walk nothing there. What does carry over from
    that idea, and is the part that mattered, is that **no allowlist is applied** to this tree:
    AC-1 asks for "the complete file trees ... (scripts, references, profiles, templates, examples,
    schemas — not just the SKILL.md)", and the source allowlist would drop precisely those classes.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("repo") != "workspace":
        raise CoverageError(f"{path}: expected repo 'workspace'")
    if data.get("commit") is not None:
        raise CoverageError(f"{path}: the workspace tree is unpinned; commit must be null")
    files = data.get("files")
    if not isinstance(files, list) or not all(isinstance(f, str) for f in files):
        raise CoverageError(f"{path}: 'files' must be a list of strings")
    # The same path rules the pinned manifests get. An unvalidated entry here would be the one
    # place a manifest could carry `..` or an absolute path into the coverage universe.
    for entry in files:
        if entry.startswith("/") or ".." in entry.split("/") or "\\" in entry or entry != entry.strip():
            raise CoverageError(f"{path}: entry {entry!r} is not a clean relative POSIX path")
    if files != sorted(files):
        raise CoverageError(f"{path}: entries must be sorted")
    if len(files) != len(set(files)):
        raise CoverageError(f"{path}: entries must be unique")
    return [f for f in files if not is_excluded(f)]


def check_coverage(universe, mappings):
    """Bidirectional. Unclaimed paths and unresolvable claims are both failures: a stale row is as
    damaging as a missing one, because either way the map has stopped describing the trees."""
    errors, claimed = [], {}
    for mapping in mappings:
        tree, where = mapping.get("tree"), f"docs/disposition.yaml:{mapping['_line']}"
        known = universe.get(tree, {})
        for path in mapping.get("paths", []):
            key = (tree, path)
            if key in claimed:
                errors.append(f"{where}: {tree}:{path} is already claimed at line {claimed[key]}")
            claimed[key] = mapping["_line"]
            if path not in known["all"]:
                errors.append(f"{where}: {tree}:{path} is not in the manifest")
            elif path not in known["allowlisted"]:
                errors.append(f"{where}: {tree}:{path} is excluded or not allowlisted — the map and "
                              "the allowlist disagree about what counts")
        for root in mapping.get("corpus_roots", []):
            prefix = root.rstrip("/") + "/"
            if not any(p == root.rstrip("/") or p.startswith(prefix) for p in known["all"]):
                errors.append(f"{where}: corpus root {tree}:{root} matches nothing in the manifest")
    for tree, sets in universe.items():
        unclaimed = sorted(p for p in sets["allowlisted"] if (tree, p) not in claimed)
        if unclaimed:
            shown = ", ".join(unclaimed[:12]) + (f" … and {len(unclaimed) - 12} more"
                                                 if len(unclaimed) > 12 else "")
            errors.append(f"{tree}: {len(unclaimed)} allowlisted path(s) claimed by no row: {shown}")
    return errors


def check_targets(root, mappings):
    """vibe-128's clause: a promising row's capability either landed or is scheduled.

    Delivered artifacts must exist in the vibe-suite tree as regular files — a missing one fails
    naming the row, its line, and the path, which is what makes "a row promises a capability
    nothing delivers" a red build instead of a footnote. Scheduled rows are held to the frozen
    SCHEDULED constant (subset semantics, exact stage and anchors) and self-expire: an anchor
    that exists in the tree keeps the gate red until the row flips to delivered."""
    errors = []
    for mapping in mappings:
        row, where = mapping.get("row"), f"docs/disposition.yaml:{mapping['_line']}"
        delivered = mapping.get("delivered")
        if isinstance(delivered, list):
            for path in delivered:
                full = root / path
                if not full.exists():
                    errors.append(f"{where}: {row}: delivered artifact {path!r} does not exist — "
                                  "the row promises a capability nothing delivers")
                elif not full.is_file():
                    errors.append(f"{where}: {row}: delivered artifact {path!r} is a directory, "
                                  "not a file — a promise resolves to artifacts, not areas")
        stage = mapping.get("scheduled")
        if stage is None:
            continue
        if row not in SCHEDULED:
            errors.append(f"{where}: {row}: not in the checker's frozen scheduled set "
                          f"({', '.join(sorted(SCHEDULED))}) — scheduling a row is a change to "
                          f"{Path(__file__).name}, not a data edit")
            continue
        frozen_stage, frozen_anchors = SCHEDULED[row]
        if stage != frozen_stage:
            errors.append(f"{where}: {row}: scheduled stage {stage!r} is not the frozen "
                          f"{frozen_stage!r} — re-staging is a code change, not a data edit")
        anchors = tuple(mapping.get("expected") or ())
        if anchors != frozen_anchors:
            errors.append(f"{where}: {row}: expected anchors {list(anchors)} do not match the "
                          f"frozen {list(frozen_anchors)} — re-anchoring is a code change, not a "
                          "data edit")
        for anchor in frozen_anchors:
            if (root / anchor).exists():
                errors.append(f"{where}: {row}: expected artifact {anchor!r} exists in the tree — "
                              "the capability landed; flip the row to delivered")
    return errors


def report_scheduled(mappings, out=sys.stdout):
    """Print the scheduled rows on every run with a parseable disposition, pass or fail — a
    scheduled promise that is visible on every gate run cannot quietly become permanent."""
    for mapping in sorted((m for m in mappings if "scheduled" in m),
                          key=lambda m: m.get("row") or ""):
        anchors = ", ".join(mapping.get("expected") or ())
        out.write(f"scheduled: {mapping.get('row')} stage {mapping.get('scheduled')} "
                  f"(awaits: {anchors})\n")


def check_counts(universe):
    """AC-1's enumerated counts, "so a silently-empty glob fails loudly"."""
    errors = []
    for tree, expected in SKILL_COUNTS.items():
        found = sum(1 for p in universe[tree]["all"] if matches(p, "skills/**/SKILL.md"))
        if found != expected:
            errors.append(f"{tree}: expected {expected} skills/**/SKILL.md, found {found}")
    for (tree, pattern), expected in NESTED_SCRIPT_LIB_COUNTS.items():
        found = sum(1 for p in universe[tree]["all"] if matches(p, pattern))
        if found != expected:
            errors.append(f"{tree}: expected {expected} files under {pattern}, found {found}")
    resources = sum(1 for p in universe["workspace"]["allowlisted"]
                    if not p.endswith("/SKILL.md"))
    if resources != WORKSPACE_RESOURCE_COUNT:
        errors.append(f"workspace: expected {WORKSPACE_RESOURCE_COUNT} non-SKILL.md resources, "
                      f"found {resources} (§5 records 12; the live trees hold 14 — see the constant)")
    return errors


# --------------------------------------------------------------------------- function IDs
PROPOSAL = Path("docs/discussion/2026-07-18-vibe-suite-merge/iter-1/round-1/plan-i1-r1.md")
FUNCTION_ID_COUNT = 57


def load_function_ids(root=REPO_ROOT):
    """The authoritative inventory, read from the shipped proposal.

    Derived rather than a constant because the proposal *is* the authority on which functions
    exist — a second copy here would be a second source of truth about §4. The count is asserted so
    that a parse that silently returns nothing cannot turn target validation into a no-op.
    """
    path = root / PROPOSAL
    if not path.is_file():
        raise CoverageError(f"{PROPOSAL}: not found — the function-ID inventory has no source")
    ids = frozenset(re.findall(r"F[0-9]+\.[0-9]+", path.read_text(encoding="utf-8")))
    if len(ids) != FUNCTION_ID_COUNT:
        raise CoverageError(f"{PROPOSAL}: expected {FUNCTION_ID_COUNT} function IDs, found "
                            f"{len(ids)} — §4 says 57 total")
    return ids


# --------------------------------------------------------------------------- entry point
def build_universe(manifest_dir, root=REPO_ROOT):
    universe, trees = {}, {}
    for repo in PINS:
        _, commit, files = load_manifest(Path(manifest_dir) / f"{repo}.json")
        trees[repo] = commit
        universe[repo] = {"all": set(files),
                          "allowlisted": {f for f in files if is_allowlisted(f)}}
    workspace = load_workspace_manifest(Path(manifest_dir) / "workspace.json")
    universe["workspace"] = {"all": set(workspace), "allowlisted": set(workspace)}
    return universe, trees


def run(disposition_path, manifest_dir, root=REPO_ROOT):
    # Parse first and report the scheduled rows immediately: the listing is a promise made for
    # every run with a parseable disposition, including runs that go on to fail.
    text = Path(disposition_path).read_text(encoding="utf-8")
    declared, mappings = parse_disposition(text, str(disposition_path))
    report_scheduled(mappings)
    universe, manifest_commits = build_universe(manifest_dir, root)

    errors = validate_schema(declared, mappings, load_function_ids(root))
    for repo, commit in manifest_commits.items():
        if declared.get(repo) != commit:
            errors.append(f"trees.{repo}: {declared.get(repo)} does not match the manifest's "
                          f"{commit}")
    errors += check_coverage(universe, mappings)
    errors += check_counts(universe)
    errors += check_targets(Path(root), mappings)
    return errors, universe, mappings


def main(argv=None):
    parser = argparse.ArgumentParser(description="AC-1 merge-completeness coverage check")
    parser.add_argument("--disposition", default="docs/disposition.yaml")
    parser.add_argument("--manifests", default="tests/source-manifests")
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    try:
        errors, universe, mappings = run(args.disposition, args.manifests, args.root)
    except CoverageError as exc:
        sys.stderr.write(f"coverage-check: {exc}\n")
        return 1

    for error in errors:
        sys.stderr.write(f"coverage-check: {error}\n")
    if errors:
        sys.stderr.write(f"\ncoverage-check: {len(errors)} problem(s) — AC-1 not satisfied\n")
        return 1

    covered = sum(len(sets["allowlisted"]) for sets in universe.values())
    print(f"ok: {covered} source artifacts across {len(universe)} trees, "
          f"claimed by {len(mappings)} disposition rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
