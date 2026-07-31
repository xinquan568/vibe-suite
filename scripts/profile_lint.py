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


def reviewer_backend_domain(root):
    """The enum's members, read from the configuration schema rather than duplicated."""
    path = root.joinpath(*VIBE_CORE_SKILL)
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
    """The closed YAML subset the suite accepts: scalars, block sequences, one nesting level.

    A full YAML parser would accept anchors, aliases and flow collections that no profile should use,
    and every one of those is a way for a profile to say something the contract cannot check.
    """
    if not text.startswith("---"):
        raise ValueError("no frontmatter: a profile opens with ---")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    fields, key = {}, None
    for raw in text[3:end].splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue

        indented = raw.startswith("  ") and not raw.startswith("  - ")
        if raw.startswith("  - ") or raw.startswith("- "):
            if key is None:
                raise ValueError("sequence item before any key")
            fields.setdefault(key, [])
            if not isinstance(fields[key], list):
                raise ValueError("%s: scalar then sequence" % key)
            fields[key].append(raw.split("- ", 1)[1].strip().strip("'\""))
            continue

        if ":" not in raw:
            raise ValueError("not a key: %r" % raw.strip())

        if indented:
            # A map's member. Without this branch an indented `step-2: overlay-discipline` under
            # `category_extensions:` was read as a *top-level* key — and then rejected as unknown,
            # which is how the Roamex reference failed its own structural validation.
            if key is None:
                raise ValueError("indented key before any parent")
            if not isinstance(fields.get(key), dict):
                if fields.get(key) not in ([], None):
                    raise ValueError("%s: scalar then map" % key)
                fields[key] = {}
            member, _, value = raw.partition(":")
            fields[key][member.strip()] = value.strip().strip("'\"")
            continue

        key, _, value = raw.partition(":")
        key, value = key.strip(), value.strip()
        if value == "":
            fields[key] = []            # a key introducing a sequence or a map
        else:
            fields[key] = value.strip("'\"")
    return fields


def check_type(name, value, kind, errors, root, structural):
    if kind == "int":
        if not re.fullmatch(r"-?\d+", str(value)):
            errors.append("%s: expected an integer, got %r" % (name, value))
    elif kind == "list":
        if not isinstance(value, list):
            errors.append("%s: expected a list, got a scalar" % name)
    elif kind == "map":
        # `[]` is the empty parse of a key with no members yet; a scalar is a real type error.
        if not isinstance(value, (dict, list)):
            errors.append("%s: expected a map, got a scalar" % name)
    elif kind == "str":
        if isinstance(value, list):
            errors.append("%s: expected a scalar, got a list" % name)
    elif kind == "str-or-list":
        pass                            # both arities are the same fact
    elif kind == "regex":
        if isinstance(value, list):
            errors.append("%s: expected a scalar regex, got a list" % name)
            return
        try:
            re.compile(value)
        except re.error as exc:
            errors.append("%s: does not compile (%s)" % (name, exc))
    elif kind == "enum":
        if name == "source_driver" and value not in SOURCE_DRIVERS:
            errors.append("%s: %r is not one of %s" % (name, value, ", ".join(SOURCE_DRIVERS)))
        if name == "reviewer_backend":
            domain = reviewer_backend_domain(root)
            if domain and value not in domain:
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
            if not (root / candidate).exists():
                errors.append("repo_path: %r does not resolve under %s" % (candidate, root))

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
