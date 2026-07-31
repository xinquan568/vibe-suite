#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Validate an issue2pr profile against the versioned profile contract (E5.3 / vibe-42).

    profile_lint.py --root <dir> <profile.md> [--structural-only]

The contract is `skills/issue2pr/references/profile-contract.md`. Where this program and that document
disagree, **this one is what runs** — so the document is the specification and this is the enforcement,
and a field added there without a rule here is an intention rather than a contract.

**Two validation contexts, and they are not interchangeable.** Structural validation — fields, types,
domains, regex compilability, contract version — needs only the file. Environmental validation — does
`repo_path` resolve — needs a checkout. A *shipped reference profile* can only be validated
structurally: `examples/profiles/roamex.md` names a repository nobody reading it has cloned, and a lint
that failed it would be demanding every reader check out someone else's project. A **run** validates
fully, because there the checkout exists by definition.

**Unknown fields are an error, not a warning.** An optional field is the only kind that can be
misspelled without consequence — `tdd_polcy` would never apply, and the profile would look complete
while silently doing nothing. Refusing an unknown key is what makes the optional fields real.

This program writes nothing.
"""

import argparse
import re
import sys
from pathlib import Path

CONTRACT_VERSION = 1

EXIT_OK, EXIT_INVALID, EXIT_UNREADABLE = 0, 1, 2

REQUIRED = {
    "contract_version": "int",
    "project_id": "str",
    "repo_id": "str",
    "repo_path": "str-or-list",
    "base_branch": "str",
    "source_driver": "enum",
    "id_pattern": "regex",
    "url_regex": "regex",
    "branch_template": "str",
    "gates": "list",
}

OPTIONAL = {
    "gate_mechanics": "str",
    "pr_body_template": "str",
    "tdd_policy": "str",
    "anti_patterns": "list",
    "mental_model_refs": "list",
    "category_extensions": "map",
    "scenario_overrides": "map",
    "reviewer_backend": "enum",
}

SOURCE_DRIVERS = ("github",)

#: The reviewer-backend domain is **not** restated here. It belongs to the configuration schema in
#: `skills/vibe-core/SKILL.md`, and two statements of one enum is how they diverge — which is exactly
#: what the shared reviewer contract was written to prevent. Read it from the schema instead.
VIBE_CORE_SKILL = ("skills", "vibe-core", "SKILL.md")

HERE = Path(__file__).resolve().parent


def reviewer_backend_domain():
    """The enum's members, read from the configuration schema rather than duplicated.

    Resolved from **this file's own installed location**, not from the target workspace. An earlier
    version looked under `--root`, which is the repository being worked on — a consumer repository has
    no `skills/vibe-core/SKILL.md`, so the lookup returned nothing and the check **failed open**. Any
    backend value passed outside this repository's own self-hosting tests.

    A domain that cannot be read is an error, not permission.
    """
    path = HERE.parent.joinpath(*VIBE_CORE_SKILL)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ()
    for line in text.splitlines():
        if line.strip().startswith("| `reviewer_backend`"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3:
                return tuple(m for m in re.findall(r"`?([a-z0-9-]+)`?", cells[2]) if m)
    return ()


def parse_frontmatter(text):
    """A **closed** grammar: scalars, block sequences, one level of mapping. Anything else is an error.

    Closed is the operative word. A profile carries gate commands — strings this pipeline will run — so
    an ambiguity here is not a formatting nicety. Every rule below rejects rather than guesses:

    - the document opens with `---` on its own line and the block ends with `---` on its own line;
    - indentation is exactly two spaces, and only under a key that introduced a collection;
    - a **duplicate key is an error**, at either level. Last-wins silently discards a value someone
      wrote deliberately, and there is no way to tell which they meant;
    - a quoted scalar's quotes must balance;
    - a key may introduce a sequence or a mapping, never both.
    """
    if not text.startswith("---\n"):
        raise ValueError("no frontmatter: a profile opens with --- on its own line")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("unterminated frontmatter: no closing --- on its own line")
    tail = text[end + 1:]
    if not (tail.startswith("---\n") or tail.rstrip() == "---"):
        raise ValueError("malformed closing delimiter")

    fields, key = {}, None
    for number, raw in enumerate(text[4:end].splitlines(), 2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indent = len(raw) - len(raw.lstrip(" "))
        if indent not in (0, 2):
            raise ValueError("line %d: indentation must be 0 or 2 spaces, got %d" % (number, indent))
        if raw.lstrip(" ") != raw.lstrip():
            raise ValueError("line %d: tabs are not accepted" % number)

        stripped = raw.strip()

        if stripped.startswith("- "):
            if key is None:
                raise ValueError("line %d: sequence item before any key" % number)
            existing = fields.get(key)
            if isinstance(existing, dict):
                raise ValueError("line %d: %s is a mapping and cannot also hold a sequence"
                                 % (number, key))
            if isinstance(existing, str):
                # `.append` on a string raised AttributeError out of the parser — an uncaught crash
                # where a refusal belongs. Reached by deleting a `gates:` line and orphaning its items.
                raise ValueError("line %d: %s already holds a scalar; a key is a scalar or a "
                                 "sequence, never both" % (number, key))
            fields.setdefault(key, [])
            fields[key].append(_scalar(stripped[2:], number))
            continue

        if ":" not in stripped:
            raise ValueError("line %d: not a key: %r" % (number, stripped))

        name, _, value = stripped.partition(":")
        name, value = name.strip(), value.strip()

        if indent == 2:
            if key is None:
                raise ValueError("line %d: indented key before any parent" % number)
            if not isinstance(fields.get(key), dict):
                if fields.get(key) not in ([], None):
                    raise ValueError("line %d: %s already holds a scalar or sequence" % (number, key))
                fields[key] = {}
            if name in fields[key]:
                raise ValueError("line %d: duplicate key %r under %s" % (number, name, key))
            fields[key][name] = _scalar(value, number)
            continue

        if name in fields:
            raise ValueError("line %d: duplicate key %r — last-wins would discard a value someone "
                             "wrote deliberately" % (number, name))
        key = name
        fields[name] = [] if value == "" else _scalar(value, number)
    return fields


def _scalar(raw, number):
    """A scalar, with its quotes checked rather than stripped hopefully."""
    if raw[:1] in ("'", '"'):
        quote = raw[0]
        if len(raw) < 2 or raw[-1] != quote:
            raise ValueError("line %d: unbalanced %s quote" % (number, quote))
        return raw[1:-1]
    if raw[-1:] in ("'", '"'):
        raise ValueError("line %d: closing quote with no opening quote" % number)
    return raw


def check_type(name, value, kind, errors, root, structural):
    if kind == "int":
        if not isinstance(value, str) or not re.fullmatch(r"-?\d+", value):
            errors.append("%s: expected an integer, got %r" % (name, value))
    elif kind == "list":
        if not isinstance(value, list):
            errors.append("%s: expected a list, got a %s"
                          % (name, "mapping" if isinstance(value, dict) else "scalar"))
    elif kind == "map":
        # `[]` is the empty parse of a key with no members yet; a scalar is a real type error.
        if not isinstance(value, (dict, list)):
            errors.append("%s: expected a map, got a scalar" % name)
    elif kind == "str":
        if not isinstance(value, str):
            errors.append("%s: expected a scalar, got a %s"
                          % (name, "mapping" if isinstance(value, dict) else "list"))
    elif kind == "str-or-list":
        if isinstance(value, dict):
            errors.append("%s: expected a scalar or a list, got a mapping" % name)
    elif kind == "regex":
        if not isinstance(value, str):
            errors.append("%s: expected a scalar regex, got a %s"
                          % (name, "mapping" if isinstance(value, dict) else "list"))
            return
        try:
            re.compile(value)
        except re.error as exc:
            errors.append("%s: does not compile (%s)" % (name, exc))
    elif kind == "enum":
        if name == "source_driver" and value not in SOURCE_DRIVERS:
            errors.append("%s: %r is not one of %s" % (name, value, ", ".join(SOURCE_DRIVERS)))
        if name == "reviewer_backend":
            domain = reviewer_backend_domain()
            if not domain:
                errors.append("%s: the configuration schema could not be read, so the backend "
                              "domain is unknown — that is an error, not permission" % name)
            elif value not in domain:
                errors.append("%s: %r is not one of %s (from the configuration schema)"
                              % (name, value, ", ".join(domain)))


def validate(path, root, structural):
    errors = []
    try:
        fields = parse_frontmatter(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ["%s: %s" % (path.name, exc)]

    for name in sorted(REQUIRED):
        if name not in fields:
            errors.append("%s: required field is missing" % name)

    known = set(REQUIRED) | set(OPTIONAL)
    for name in sorted(set(fields) - known):
        errors.append("%s: unknown field — an optional field misspelled would silently never apply"
                      % name)

    for name, value in sorted(fields.items()):
        kind = REQUIRED.get(name) or OPTIONAL.get(name)
        if kind:
            check_type(name, value, kind, errors, root, structural)

    version = fields.get("contract_version")
    if version is not None and str(version) != str(CONTRACT_VERSION):
        errors.append("contract_version: %r, but this lint enforces version %d"
                      % (version, CONTRACT_VERSION))

    if not structural:
        for candidate in _as_list(fields.get("repo_path")):
            errors.extend(_check_repo_path(candidate, root))

    return errors


def _check_repo_path(candidate, root):
    """`repo_path` names a checkout **inside the workspace**, and nothing else.

    Existence alone was the whole check, which accepted `..` and `/tmp` — a checked-in profile could
    have redirected every later branch, gate and source operation outside the workspace. Three
    properties now hold, and each fails on its own:

    - **relative**, so a profile cannot name an absolute location;
    - **contained** after resolution, so neither `..` nor a symlink escapes;
    - **a git checkout**, so an arbitrary existing directory is not mistaken for a repository.
    """
    errors = []
    path = Path(candidate)
    if path.is_absolute():
        return ["repo_path: %r is absolute; a profile names a checkout inside the workspace" % candidate]

    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return ["repo_path: %r escapes the workspace root" % candidate]

    if not resolved.is_dir():
        return ["repo_path: %r does not resolve to a directory under %s" % (candidate, root)]
    if not (resolved / ".git").exists() and not (resolved / "README.md").exists():
        errors.append("repo_path: %r resolves, but does not look like a checkout" % candidate)
    return errors


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate an issue2pr profile.")
    parser.add_argument("profile")
    parser.add_argument("--root", required=True)
    parser.add_argument("--structural-only", action="store_true",
                        help="skip checks that need a checkout; the only mode a shipped "
                             "reference profile can be validated in")
    args = parser.parse_args(argv)

    path = Path(args.profile)
    if not path.is_file():
        print("profile_lint: %s is not a readable file" % args.profile, file=sys.stderr)
        return EXIT_UNREADABLE

    errors = validate(path, Path(args.root).absolute(), args.structural_only)
    if errors:
        print("profile_lint: %s — %d problem(s)" % (path.name, len(errors)), file=sys.stderr)
        for error in errors:
            print("  - %s" % error, file=sys.stderr)
        return EXIT_INVALID

    scope = "structural" if args.structural_only else "full"
    print("profile_lint: %s conforms to contract version %d (%s)"
          % (path.name, CONTRACT_VERSION, scope))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
