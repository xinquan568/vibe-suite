#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Derive a work-branch slug from a work item's title, under the slug rule the issue2pr profile
contract declares (grill H2, part c).

The slug is the one title-derived token that reaches a `git` or `gh` argument — the work branch is
argv, the body is stdin — so its domain is a core rule, stated once in
`skills/issue2pr/references/profile-contract.md` (`<!-- slug-rule -->`) and read from there at
runtime. Every member of that block is executed or validated here; a missing, unsupported or
unexpected member is a declaration gap named on stderr (exit 4) — never a fallback of this module's.

    python3 scripts/issue2pr_slug.py -- "<title>"     # stdout: the slug; exit 2 if none can be made
    python3 scripts/issue2pr_slug.py --check=<slug>   # exit 0 if the slug conforms, else exit 2

The `--` keeps a `-`-led title out of the options. A title that leaves nothing after the declared
normalisation steps (only separators, symbols, or non-Latin text) has no conforming slug and is
refused with the reason — a run does not start on an empty slug.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = REPO_ROOT / "skills" / "issue2pr" / "references" / "profile-contract.md"
MARKER = "slug-rule"

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_GAP = 4

#: The normalisation steps the declaration may name, by identifier. The declared `normalise` list
#: selects and orders them; an identifier not in this registry is a declaration gap.
STEPS = {
    "nfkd-ascii-fold": lambda text, rule: unicodedata.normalize("NFKD", text)
    .encode("ascii", "ignore").decode("ascii"),
    "lowercase": lambda text, rule: text.lower(),
    "non-alnum-runs-to-hyphen": lambda text, rule: re.sub(r"[^a-z0-9]+", "-", text),
    "strip-hyphens": lambda text, rule: text.strip("-"),
    "truncate-then-strip-hyphens": lambda text, rule: text[: rule["max_length"]].rstrip("-"),
}
#: What may happen when normalisation leaves nothing. `refuse` is the one supported policy.
EMPTY_POLICIES = ("refuse",)
MEMBERS = ("pattern", "max_length", "normalise", "empty")


class Refusal(Exception):
    """A title or slug the rule does not admit, with the reason."""


class DeclarationGap(Exception):
    """The contract does not declare what this operation needs — named, never defaulted."""

    def __init__(self, key):
        super().__init__(f"declaration gap: {CONTRACT.name} <!-- {MARKER} --> lacks {key!r}")
        self.key = key


def load_rule(contract=None):
    """The `<!-- slug-rule -->` JSON block of the profile contract; every member validated."""
    path = Path(contract) if contract else CONTRACT
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise DeclarationGap(f"contract ({exc})") from exc
    match = re.search(r"(?s)<!--\s*%s\s*-->\s*```json\s*(.*?)```" % re.escape(MARKER), text)
    if not match:
        raise DeclarationGap("block")
    try:
        rule = json.loads(match.group(1))
    except ValueError as exc:
        raise DeclarationGap(f"block (not JSON: {exc})") from exc
    if not isinstance(rule, dict):
        raise DeclarationGap("block (not an object)")
    for member in MEMBERS:
        if member not in rule:
            raise DeclarationGap(member)
    for member in rule:
        if member not in MEMBERS:
            raise DeclarationGap(f"unexpected member {member!r}")
    pattern = rule["pattern"]
    if not isinstance(pattern, str) or not pattern:
        raise DeclarationGap("pattern")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise DeclarationGap(f"pattern ({exc})") from exc
    max_length = rule["max_length"]
    if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length < 1:
        raise DeclarationGap("max_length")
    steps = rule["normalise"]
    if not isinstance(steps, list) or not steps:
        raise DeclarationGap("normalise")
    for index, step in enumerate(steps):
        if not isinstance(step, str) or step not in STEPS:
            raise DeclarationGap(f"normalise[{index}] ({step!r} is not a known step)")
    if rule["empty"] not in EMPTY_POLICIES:
        raise DeclarationGap(f"empty ({rule['empty']!r} is not a supported policy)")
    return rule


def check(slug, rule):
    """Refuse a slug outside the declared pattern, naming both."""
    if not isinstance(slug, str) or not re.fullmatch(rule["pattern"], slug):
        raise Refusal(f"slug {slug!r} does not match the declared slug rule "
                      f"{rule['pattern']}")
    return slug


def slugify(title, rule):
    """The declared normalisation steps, in the declared order; the declared policy when nothing
    remains; then the declared pattern."""
    text = str(title)
    for step in rule["normalise"]:
        text = STEPS[step](text, rule)
    if not text:
        # rule["empty"] == "refuse" — the one policy load_rule admits
        raise Refusal(f"no slug can be made from title {title!r}: nothing remains after the "
                      "declared normalisation — choose a title with a Latin letter or digit")
    return check(text, rule)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="issue2pr_slug.py",
        description="Derive (or check) a work-branch slug under the contract's declared slug rule.")
    parser.add_argument("title", nargs="?", help="the work item's title (put -- before it)")
    parser.add_argument("--check", metavar="SLUG", help="validate a supplied slug instead")
    parser.add_argument("--contract", metavar="PATH", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if (args.title is None) == (args.check is None):
        parser.error("give exactly one of -- <title> or --check=<slug>")
    try:
        rule = load_rule(args.contract)
        slug = check(args.check, rule) if args.check is not None else slugify(args.title, rule)
    except DeclarationGap as exc:
        print(f"issue2pr_slug: {exc}", file=sys.stderr)
        return EXIT_GAP
    except Refusal as exc:
        print(f"issue2pr_slug: refused: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    print(slug)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
