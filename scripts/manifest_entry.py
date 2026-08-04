#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Manifest mode's entry path: `--from-manifest <path>`.

Two checks in a fixed order, and the order is part of the contract.

**Schema first.** `schemas/manifest.schema.json` decides whether the document is a manifest at all —
shape, types, enums, patterns, bounds. It is project-neutral, so it cannot decide whether *this*
manifest belongs to *this* repository.

**Profile second.** `repos[].id` and `repos[].base_branch` are compared against the bound profile.
The schema deliberately carries no `const` for either: pinning them would put a project value in an
artifact E5.3 requires to be project-neutral, and **a schema has no profile to compare against**.
That is not a limitation worked around here — it is the reason this file exists.

A document failing both reports the **schema** failure. A profile mismatch on a document that is not
a manifest is not a useful thing to say.

    python3 scripts/manifest_entry.py <manifest.json> --profile <profile.md>
"""

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "schemas" / "manifest.schema.json"

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_SCHEMA = 2
EXIT_PROFILE = 3

#: The manifest property and the core's field it becomes. The manifest keeps the source spelling —
#: renaming a specified input property would be a port-time correction nobody authorised — so the
#: translation lives here, where a mapping is an ordinary thing for an entry path to do.
CAP_PROPERTY = "max_review_iterations"
CAP_FIELD = "max_review_rounds"


class ManifestError(RuntimeError):
    """A manifest that will not be run, with the stage that refused it."""

    def __init__(self, stage, message):
        super().__init__(message)
        self.stage = stage


def _load_validator():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "validate_audit_output", REPO_ROOT / "scripts" / "validate_audit_output.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_profile(path):
    """The two fields the profile-dependent checks compare against.

    Deliberately minimal: this reads what it needs and refuses what it cannot find, rather than
    parsing a profile fully — `scripts/profile_lint.py` owns the contract.
    """
    text = Path(path).read_text(encoding="utf-8")
    fields = {}
    for key in ("repo_id", "base_branch"):
        match = re.search(r"(?m)^\s*%s:\s*'?\"?([^'\"\n]+?)'?\"?\s*$" % key, text)
        if not match:
            raise ManifestError("profile", f"profile {path} declares no {key}")
        fields[key] = match.group(1).strip()
    return fields


def validate_document(manifest, schema=None):
    """Stage one. Raises `ManifestError('schema', …)` — never a profile complaint."""
    validator = _load_validator()
    schema = schema if schema is not None else json.loads(SCHEMA.read_text(encoding="utf-8"))
    try:
        validator.validate(manifest, schema)
    except validator.ValidationError as exc:
        raise ManifestError("schema", str(exc)) from exc


def check_against_profile(manifest, profile):
    """Stage two. Only the checks a schema structurally cannot make."""
    for index, repo in enumerate(manifest.get("repos", [])):
        where = f"repos[{index}]"
        if repo.get("id") != profile["repo_id"]:
            raise ManifestError(
                "profile",
                f"{where}.id is {repo.get('id')!r}; the bound profile is {profile['repo_id']!r}")
        if repo.get("base_branch") != profile["base_branch"]:
            raise ManifestError(
                "profile",
                f"{where}.base_branch is {repo.get('base_branch')!r}; "
                f"the bound profile is {profile['base_branch']!r}")


def to_run_settings(manifest):
    """The manifest's optional run flags, in the core's vocabulary."""
    settings = {}
    if CAP_PROPERTY in manifest:
        settings[CAP_FIELD] = manifest[CAP_PROPERTY]
    for key in ("review_mode", "reviewer_model", "reviewer_backend"):
        if key in manifest:
            settings[key] = manifest[key]
    return settings


def accept(manifest, profile):
    """Both stages, in the contractual order, returning the run settings."""
    validate_document(manifest)
    check_against_profile(manifest, profile)
    return to_run_settings(manifest)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="manifest_entry.py", description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        document = json.loads(args.manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"manifest_entry: cannot read {args.manifest}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    # Order matters here, and it is easy to lose. `accept(document, read_profile(path))` reads the
    # profile *first* — Python evaluates arguments before the call — so a malformed profile reported
    # its own failure for a document that was never a manifest. The stages are sequenced explicitly.
    try:
        validate_document(document)
        settings = to_run_settings(document)
        check_against_profile(document, read_profile(args.profile))
    except ManifestError as exc:
        print(f"manifest_entry: {exc.stage}: {exc}", file=sys.stderr)
        return EXIT_SCHEMA if exc.stage == "schema" else EXIT_PROFILE
    print(json.dumps(settings, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
