#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Nothing outside the source driver invokes `gh` (E5.4 / vibe-43).

    gh_boundary_lint.py --root <dir> [path ...]

E5.4's acceptance: *core calls no `gh` outside the driver*, grep-enforced. A bare substring match would
report the driver itself, every cross-reference to it, and every sentence containing the letters — so
the rule distinguishes an **invocation** from a **mention**.

**The rule is purely syntactic**, and that is a deliberate narrowing. An earlier formulation asked
whether a line was "an imperative" or "an instruction rather than a description", which is a judgement
no lint can make and a reviewer rightly refused. A command form is:

    gh <lowercase-subcommand>

and it fails in exactly three places:

1. inside a fenced code block;
2. inside an inline code span;
3. inside a string literal or subprocess argument in a script, found by **parsing** — the same reason
   `tests/test_write_discipline.py` gives for its own AST sweep: a textual sweep matches comments and
   misses what is reached through a name.

Everywhere else it passes, which is the prose case: `the gh CLI`, `see the github driver`. Bare `gh`
with no subcommand never fails.

**Exactly one false negative is accepted, and it is this**: an instruction written as unmarked prose —
"run gh pr create to open it", without backticks — passes. Two others found in review are *not*
accepted and are closed: tilde fences are recognised alongside backticks, and an unparseable Python file
**fails closed** rather than reporting nothing. That is unlikely under this repository's conventions,
where a command is written in a code span, and the alternative is a rule that guesses at intent. **A
lint that guesses gets switched off**, which is the failure this file exists to avoid rather than to
demonstrate.

This program writes nothing.
"""

import argparse
import ast
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_VIOLATION = 0, 1

#: The one place `gh` belongs *once a driver has been selected*.
DRIVER = Path("skills") / "issue2pr" / "drivers" / "github.md"

#: And the one place it belongs *before* that. `profile init` runs when no profile exists — and the
#: driver is chosen by `source_driver` **in a profile**, so routing this through a driver would require
#: the profile the command is being run to create. The circularity is real, not an excuse, which is why
#: this is a named second exemption rather than a widened first one.
#:
#: The exemption is narrow deliberately: this file, and only the probes named below.
PRE_PROFILE = Path("skills") / "issue2pr" / "references" / "profile-init.md"

#: **Exactly which invocations** the bootstrap file may carry. Skipping the file wholesale would have
#: exempted a mutating `gh pr create` sitting in it — the claim was "two read-only probes", and a
#: per-file skip cannot enforce a claim about which probes.
#:
#: Both are read-only and neither concerns a work item's content: one asks who is authenticated, the
#: other whether the repository answers at all.
PRE_PROFILE_ALLOWED = (
    re.compile(r"^gh\s+api\s+user\b"),
    re.compile(r"^gh\s+issue\s+list\b"),
)

#: Enumerated, not inferred. `tests/**` is excluded because a fixture must be able to contain the
#: thing being prohibited.
CORPUS = (
    "skills/issue2pr/**/*.md",
    "commands/issue2pr.md",
    "scripts/profile_*.py",
)

COMMAND_FORM = re.compile(r"\bgh\s+[a-z][a-z-]*\b")

SCRIPT_SUFFIXES = (".py", ".mjs", ".sh")


def markdown_hits(text):
    """`(line, snippet)` for command forms inside a fence or an inline code span."""
    hits = []
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        # CommonMark has two fence forms. Recognising only backticks let a tilde-fenced command
        # through a location the file claims to scan.
        if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
            fenced = not fenced
            continue
        if fenced:
            if COMMAND_FORM.search(line):
                hits.append((number, line.strip()))
            continue
        for span in re.findall(r"`([^`]+)`", line):
            if COMMAND_FORM.search(span):
                hits.append((number, span.strip()))
    return hits


def python_hits(text):
    """String literals containing a command form, plus `subprocess` argument lists.

    Parsed rather than matched: a comment mentioning `gh pr` is not an invocation, and a list built as
    `["gh", "pr", "view"]` contains no substring a text sweep would find.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        # Fail closed. Returning no hits meant an unparseable file containing `gh pr create` passed
        # silently — a check that treats "I could not look" as "there is nothing there".
        return [(0, "unparseable Python; the boundary cannot be checked here")]
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if COMMAND_FORM.search(node.value):
                hits.append((getattr(node, "lineno", 0), node.value.strip()))
        elif isinstance(node, (ast.List, ast.Tuple)):
            parts = [e.value for e in node.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if len(parts) >= 2 and parts[0] == "gh" and re.fullmatch(r"[a-z][a-z-]*", parts[1]):
                hits.append((getattr(node, "lineno", 0), " ".join(parts)))
    return hits


def shell_hits(text):
    """Shell and JS have no cheap AST here, so every line counts — they are executable throughout."""
    return [(number, line.strip()) for number, line in enumerate(text.splitlines(), 1)
            if COMMAND_FORM.search(line) and not line.lstrip().startswith("#")]


def scan(path, text):
    if path.suffix == ".md":
        return markdown_hits(text)
    if path.suffix == ".py":
        return python_hits(text)
    if path.suffix in SCRIPT_SUFFIXES:
        return shell_hits(text)
    return markdown_hits(text)


def _bootstrap_allowed(snippet):
    """Whether **every** `gh` invocation in the snippet is one of the named probes.

    Matching the *first* one and then exempting the whole snippet let
    `gh api user && gh pr create --fill` through: the prefix matched, and everything after it rode
    along. An exemption is a claim about a line, so it has to hold for all of it.
    """
    occurrences = list(COMMAND_FORM.finditer(snippet))
    if not occurrences:
        return False
    return all(any(pattern.match(snippet[match.start():]) for pattern in PRE_PROFILE_ALLOWED)
               for match in occurrences)


def targets(root, explicit):
    if explicit:
        return [Path(p) for p in explicit]
    found = []
    for pattern in CORPUS:
        found.extend(sorted(root.glob(pattern)))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description="Keep `gh` invocations inside the source driver.")
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)

    root = Path(args.root).absolute()
    violations = []

    for path in targets(root, args.paths):
        if not path.is_file():
            continue
        # Every target must resolve beneath --root, and only the ONE exact path is exempt. The
        # earlier basename fallback exempted any file called `drivers/github.md` anywhere — including
        # a nested one the recursive corpus finds, and an explicitly supplied path outside the root.
        # A boundary a caller can step around by naming a file is not a boundary.
        try:
            relative = path.resolve().relative_to(root.resolve())
        except ValueError:
            violations.append("%s  (outside --root; refusing to judge it)" % path)
            continue
        if relative == DRIVER:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, snippet in scan(path, text):
            if relative == PRE_PROFILE and _bootstrap_allowed(snippet):
                continue
            violations.append("%s:%d  %s" % (relative, number, snippet[:100]))

    if violations:
        print("gh_boundary_lint: %d invocation(s) outside %s (and the two bootstrap probes in %s)"
              % (len(violations), DRIVER, PRE_PROFILE), file=sys.stderr)
        for violation in violations:
            print("  - %s" % violation, file=sys.stderr)
        return EXIT_VIOLATION

    print("gh_boundary_lint: clean")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
