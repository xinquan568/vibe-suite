#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The mechanical auto-fix table for `/vibe-suite:fix` (E4.4 / vibe-38).

F3.8 requires five transformations from nlpm's `fix` to run **before** any model-driven fix. Each has
exactly one correct output, so a model call would buy nothing and risk a rewrite.

**This is a script rather than prose in the command because "applied first" is an acceptance
criterion.** A markdown command has no callable seam, so a test that applied the rules itself would
prove the test rather than the command. The repository already draws this line: deterministic work
goes to a Python engine (`score_engine.py`, `model-pin-lint.py`), judgement goes to a model.

**Every rule is a no-op when its predicate is false**, so the table is idempotent: a second run over
the same tree changes nothing. That property is asserted for the table as a whole, so a future rule
that breaks it fails without anyone remembering to add a case.

**A conflict is a no-op and is reported, never a guess.** Where both the old and new form of a key are
present, dropping either would lose a value the author wrote.

**Every write goes through `bridge.write_atomic`**, the repository's audited primitive, rather than
`Path.write_text`. `tests/test_write_discipline.py` enforces that across `scripts/` for good reason,
and it is doubly right here: a fixer interrupted midway through a non-atomic write leaves a corrupted
artifact, which is the worst possible failure for a tool whose job is repair.

Usage:

    python3 scripts/mechanical_fix.py <root> [--dry-run] [--json]

Exit codes:

    0  ran; changes applied (or none needed)
    2  the root is unreadable
    3  a write was refused by the atomic primitive
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402

EXIT_OK, EXIT_BAD_ROOT, EXIT_WRITE_FAILED = 0, 2, 3

#: Files the table touches: markdown NL artifacts with YAML frontmatter.
GLOBS = ("commands/**/*.md", "agents/**/*.md", "skills/**/SKILL.md")


def split_frontmatter(text):
    """(lines of the frontmatter block, body) or (None, text) when there is no block."""
    if not text.startswith("---\n"):
        return None, text
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return None, text
    return parts[1].splitlines(), parts[2]


def join(fm_lines, body):
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def has_key(fm_lines, key):
    return any(re.match(r"^%s\s*:" % re.escape(key), line) for line in fm_lines)


def key_index(fm_lines, key):
    for i, line in enumerate(fm_lines):
        if re.match(r"^%s\s*:" % re.escape(key), line):
            return i
    return None


def derive_name(path):
    """SKILL.md takes its containing directory's name; everything else takes its filename stem.

    Derivation, not invention: both values are already on disk, and the conventions the corpus
    follows make each the name the artifact is addressed by.
    """
    return path.parent.name if path.name == "SKILL.md" else path.stem


# --- the five rules ------------------------------------------------------------------------------
# Each takes (path, fm_lines, body, rel) -- `rel` being the path RELATIVE to the target root -- and
# returns (fm_lines, body, note): None for a no-op, a string for an applied change, or a
# "conflict: ..." string for a reported refusal.

def rule_rename_tools(path, fm, body, rel):
    if not has_key(fm, "tools"):
        return fm, body, None
    if has_key(fm, "allowed-tools"):
        return fm, body, "conflict: both `tools` and `allowed-tools` present; neither touched"
    i = key_index(fm, "tools")
    fm = list(fm)
    fm[i] = re.sub(r"^tools\s*:", "allowed-tools:", fm[i])
    return fm, body, "renamed `tools` to `allowed-tools`"


def rule_shared_partial_not_user_invocable(path, fm, body, rel):
    """Keyed on the path RELATIVE to the target root.

    An earlier revision tested `"shared" in path.parts`, which examines the whole absolute path: a
    target whose own ancestor happened to be named `shared` gave every artifact under it
    `user-invocable: false`. Classification must depend on the artifact's place inside the target,
    never on where the target itself lives.
    """
    if rel.parts[:2] != ("commands", "shared") or has_key(fm, "user-invocable"):
        return fm, body, None
    return fm + ["user-invocable: false"], body, "added `user-invocable: false`"


#: `name` is required on skills and agents and is absent by convention on commands -- no shipped
#: command carries one, and all eight agents plus every skill do. A rule that added `name` to a
#: command would be introducing a key the corpus does not use, which is a rewrite rather than a fix.
NAMED_ARTIFACTS = ("SKILL.md",)


def _needs_name(path, rel):
    """Relative-path classification, for the same reason as rule 2: an ancestor named `agents`
    outside the target must not make the target's commands look like agents."""
    return path.name in NAMED_ARTIFACTS or rel.parts[:1] == ("agents",)


def rule_derive_name(path, fm, body, rel):
    if not _needs_name(path, rel) or has_key(fm, "name"):
        return fm, body, None
    return ["name: %s" % derive_name(path)] + fm, body, "derived `name` from the path"


def rule_insert_heading(path, fm, body, rel):
    """Uses the derived name, so `derive-name` runs before it -- the one ordering the table fixes."""
    if re.search(r"(?m)^#{1,6}\s+\S", body):
        return fm, body, None
    heading = "# %s\n" % derive_name(path)
    return fm, "\n" + heading + body.lstrip("\n"), "inserted a top-level heading"


#: Rule 5's predicate has TWO clauses: no `argument-hint` AND the body actually reads arguments. A
#: command that takes none is untouched, and the inserted value is a placeholder rather than a guess
#: at an argument list -- a mechanical rule inventing semantics would be doing the model stage's job
#: badly.
ARGS_IN_BODY = re.compile(r"\$ARGUMENTS\b|\$\d\b")


def rule_add_argument_hint(path, fm, body, rel):
    if has_key(fm, "argument-hint") or not ARGS_IN_BODY.search(body):
        return fm, body, None
    fm = list(fm)
    at = key_index(fm, "description")
    insert_at = (at + 1) if at is not None else len(fm)
    fm.insert(insert_at, 'argument-hint: "<describe the arguments>"')
    return fm, body, "added an `argument-hint` placeholder"


#: Order matters between two of them: the heading rule uses the derived name, so derivation runs
#: first. The rest are independent.
RULES = (
    ("rename-tools", rule_rename_tools),
    ("shared-partial-flag", rule_shared_partial_not_user_invocable),
    ("derive-name", rule_derive_name),
    ("insert-heading", rule_insert_heading),
    ("add-argument-hint", rule_add_argument_hint),
)


def fix_text(path, text, rel=None):
    """Apply the table to one artifact. Returns (new_text, [(rule, note), ...]).

    `rel` is the path relative to the target root and is what the classification rules key on.
    """
    rel = Path(rel) if rel is not None else Path(path.name)
    fm, body = split_frontmatter(text)
    if fm is None:
        return text, []
    notes = []
    for name, rule in RULES:
        fm, body, note = rule(path, fm, body, rel)
        if note:
            notes.append((name, note))
    return join(fm, body), notes


def discover(root):
    seen, out = set(), []
    for pattern in GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.add(path)
                out.append(path)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply the mechanical auto-fix table.")
    parser.add_argument("root")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        sys.stderr.write("mechanical_fix: not a directory: %s\n" % root)
        return EXIT_BAD_ROOT

    # Pin the root's identity BEFORE discovery and before any path-based read. `write_atomic` would
    # otherwise pin it at the first write -- after the reads that decide the mutations -- so a root
    # swapped in between would receive content derived from the original tree. `pin_root`'s own
    # docstring describes exactly this window.
    try:
        bridge.assert_root(root)
        bridge.pin_root(root)
    except bridge.BridgeError as exc:
        sys.stderr.write("mechanical_fix: %s\n" % exc)
        return EXIT_BAD_ROOT

    changed = []
    for path in discover(root):
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        new_text, notes = fix_text(path, text, rel)
        if notes:
            changed.append({"file": str(rel),
                            "changes": [{"rule": r, "note": n} for r, n in notes]})
        if new_text != text and not args.dry_run:
            try:
                bridge.write_atomic(root, path, new_text)
            except bridge.BridgeError as exc:
                sys.stderr.write("mechanical_fix: %s\n" % exc)
                return EXIT_WRITE_FAILED

    if args.json:
        json.dump({"root": str(root), "dry_run": args.dry_run, "files": changed},
                  sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not changed:
            sys.stdout.write("mechanical_fix: nothing to apply\n")
        for entry in changed:
            sys.stdout.write("%s\n" % entry["file"])
            for c in entry["changes"]:
                sys.stdout.write("  [%s] %s\n" % (c["rule"], c["note"]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
