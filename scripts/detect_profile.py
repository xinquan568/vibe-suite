#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Detect what a repository can tell us about its issue2pr profile (E5.5 / vibe-44).

    detect_profile.py --facts <file|-> [--id <profile-id>]

**Reads; never writes.** Rendering and writing are `write_profile.py`'s, and the split is what lets
this be tested against fixture repositories without anything being produced — the same line #43 drew
between a driver that observes and a core that decides.

**Git facts come in as input, not out of a subprocess.** Detection is then deterministic and testable
without constructing eight real repositories; reading git is one small function at the call site with
its own test. What this program owns is the *conversion*, which is where every mistake lives: an
`origin` URL is not a `url_regex`, and a repository name containing `.` produces a pattern that
compiles and matches the wrong thing.

**Preconditions report everything missing**, not the first thing. Learning one requirement per attempt
is three round trips for one answer.

**Authentication is not a precondition.** An earlier design derived `branch_template` — a *required*
field — from the authenticated login, which left an unauthenticated user with no valid output at all.
The template no longer needs a login; a login only makes it nicer. So a missing login is a warning and
a skipped smoke check, and the skip is reported.
"""

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_PRECONDITION, EXIT_BAD_INPUT = 0, 1, 2

CONTRACT_VERSION = 1

GITHUB_HOSTS = ("github.com",)

SSH_REMOTE = re.compile(r"^git@(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<name>.+?)(?:\.git)?$")
HTTPS_REMOTE = re.compile(r"^https://(?P<host>[^/]+)/(?P<owner>[^/]+)/(?P<name>.+?)(?:\.git)?/?$")


def parse_remote(remote):
    """`(host, owner, name)` from either spelling, or None."""
    for pattern in (SSH_REMOTE, HTTPS_REMOTE):
        match = pattern.match(remote)
        if match:
            return match.group("host"), match.group("owner"), match.group("name")
    return None


def preconditions(facts):
    """Every missing requirement, in one pass.

    Returning after the first would teach the user one thing per attempt — which is the failure this
    function's shape exists to prevent, and why a fixture missing only one requirement cannot tell the
    difference.
    """
    missing = []

    # The first of the three documented preconditions, and it was absent: the fixture that stands for
    # "a complete repository" is not a git repository at all and passed anyway. A precondition nothing
    # checks is a sentence.
    if not facts.get("is_git_repository", False):
        missing.append("not a git repository — issue2pr cuts a work branch, so it needs one")

    remote = facts.get("remote")
    if not remote:
        missing.append("no `origin` remote — issue2pr needs a source repository to work against")
    else:
        parsed = parse_remote(remote)
        if not parsed:
            missing.append("`origin` (%s) is not a recognisable git remote" % remote)
        elif parsed[0] not in GITHUB_HOSTS:
            missing.append("`origin` is on %s; the only implemented source driver is github"
                           % parsed[0])

    if not facts.get("default_branch"):
        missing.append("no resolvable default branch — the work branch has nothing to cut from")

    return missing


def profile_id_from(name):
    """A pointer id: `[a-z0-9][a-z0-9-]*`, derived rather than assumed.

    `project_id` is a human-readable name and this is not it — F6.4's `--id <project-id>` invites
    treating them as one string, and the failure would appear at the *next* run rather than here.
    """
    derived = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return derived or None


def url_regex_for(host, owner, name):
    """Anchored, escaped, capturing the number.

    `re.escape` on the name is the whole point: a repository called `a.b` produces a pattern that
    matches `axb` without it, and the lint only checks that a pattern *compiles*.
    """
    return r"^https://%s/%s/%s/issues/(\d+)/?$" % (
        re.escape(host), re.escape(owner), re.escape(name))


def id_pattern_for(shorthand):
    """`proj-N` → `^proj-(\\d+)$`; `N` → `^(\\d+)$`. Escaped and anchored.

    Unanchored, `proj-(\\d+)` matches inside `xproj-17`, which is a different item.
    """
    if not shorthand or shorthand.strip() == "N":
        return r"^(\d+)$"
    if "N" not in shorthand:
        return None
    prefix, _, suffix = shorthand.partition("N")
    return r"^%s(\d+)%s$" % (re.escape(prefix), re.escape(suffix))


def detect_gates(root):
    """Candidates a file actually declares. A guessed gate is a command the pipeline will run."""
    gates = []
    package = root / "package.json"
    if package.is_file():
        try:
            scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
        except ValueError:
            scripts = {}
        for name in ("lint", "test"):
            if name in scripts:
                gates.append("npm run %s" % name)

    makefile = root / "Makefile"
    if makefile.is_file():
        targets = set(re.findall(r"(?m)^([A-Za-z][\w-]*):", makefile.read_text(encoding="utf-8")))
        for name in ("lint", "test"):
            if name in targets:
                gates.append("make %s" % name)

    for marker, command in (("Cargo.toml", "cargo test"), ("go.mod", "go test ./..."),
                            ("pom.xml", "mvn -q test")):
        if (root / marker).is_file():
            gates.append(command)

    return gates


def detect(facts):
    root = Path(facts["root"])
    host, owner, name = parse_remote(facts["remote"])

    profile_id = facts.get("profile_id") or profile_id_from(name)
    if not profile_id:
        raise ValueError("cannot derive a profile id from the repository name %r; pass --id" % name)

    id_pattern = id_pattern_for(facts.get("id_shorthand"))
    if id_pattern is None:
        raise ValueError("the id shorthand %r contains no N to stand for the number"
                         % facts.get("id_shorthand"))

    login = facts.get("login")
    # Required, therefore independent of authentication. A login only makes it nicer.
    branch_template = ("%s/ai/{id}-{slug}" % login) if login else "ai/{id}-{slug}"

    return {
        "contract_version": CONTRACT_VERSION,
        "profile_id": profile_id,
        "project_id": name,
        "repo_id": "%s/%s" % (owner, name),
        "repo_path": "./%s" % root.name,
        "base_branch": facts["default_branch"],
        "source_driver": "github",
        "id_pattern": id_pattern,
        "url_regex": url_regex_for(host, owner, name),
        "branch_template": branch_template,
        "gates": detect_gates(root),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Detect issue2pr profile fields.")
    parser.add_argument("--facts", required=True, help="JSON of repository facts, or - for stdin")
    parser.add_argument("--id", dest="profile_id")
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.facts == "-" else Path(args.facts).read_text(encoding="utf-8")
    try:
        facts = json.loads(raw)
    except ValueError as exc:
        print("detect_profile: %s" % exc, file=sys.stderr)
        return EXIT_BAD_INPUT
    if args.profile_id:
        facts["profile_id"] = args.profile_id

    missing = preconditions(facts)
    if missing:
        print("detect_profile: this repository is not ready (%d):" % len(missing), file=sys.stderr)
        for item in missing:
            print("  - %s" % item, file=sys.stderr)
        return EXIT_PRECONDITION

    try:
        detected = detect(facts)
    except ValueError as exc:
        print("detect_profile: %s" % exc, file=sys.stderr)
        return EXIT_BAD_INPUT

    if not facts.get("login"):
        print("detect_profile: WARNING no authenticated login — the source smoke check will be "
              "skipped, and the branch template will not carry a user prefix", file=sys.stderr)

    print(json.dumps(detected, indent=2, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
