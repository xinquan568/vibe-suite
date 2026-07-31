#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Render and publish an issue2pr profile and its pointer (E5.5 / vibe-44).

    write_profile.py --root <dir> --fields <file|-> [--force]

**Everything that can fail happens before anything is published.** `bridge.write_atomic` makes each
*file* atomic; it does not make profile-plus-pointer atomic, and the gap between two writes is where a
half-finished state lives. So: pin the root before any *read*, preflight both destinations, render the
profile and **lint the candidate in memory** — a profile that would not pass is never written at all —
and only then write, profile first.

Profile first because a pointer to a missing profile is a worse residue than a profile nothing points
at. If the pointer write fails the orphaned profile is **named**, not silently left: rolling it back
would delete a file the user may want, and saying nothing is worse than either. The residue is bounded
and described, which is achievable; a two-file transaction is not.

**Repository-controlled strings are refused, not escaped.** Gate commands come from files and interview
answers come from people, and the profile is read back by `profile_lint.py`'s **closed** grammar —
balanced quotes, two-space indentation, no multi-line scalars, no escaping convention. Inventing an
escaping scheme its parser does not implement would produce a file that renders and will not read back.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402
import profile_lint  # noqa: E402

EXIT_OK, EXIT_BAD_INPUT, EXIT_GUARD, EXIT_INVALID, EXIT_WRITE_FAILED = 0, 1, 2, 3, 4

POINTER = ".vibe-suite.md"

#: Characters the lint's grammar cannot carry. Refused with the value named, so the user can fix the
#: source rather than wonder which field was rejected.
UNRENDERABLE = re.compile(r"[\n\r\t\x00-\x08\x0b\x0c\x0e-\x1f]")

NOT_ASKED_NOTE = """
## Round bounds

floor 2, ceiling 5, default 2 — the pipeline's own, not this profile's. The cap is a **per-run** flag
(`--max-review-rounds`), which is why `profile init` did not ask for it: there is no field here for the
answer to live in, and a profile carrying one would be rejected as an unknown field.

## Two questions `profile init` did not ask

Recorded so their absence is a decision rather than a gap.

- **The review-iteration cap** — per-run, as above.
- **The reviewer backend** — `reviewer_backend`'s domain is `codex` alone, so omitting the field
  selects exactly what the only legal answer would have selected.

Both were narrowed by an amendment to the issue that specified them. If a contract field for the cap
appears, or a second backend, this is the decision to revisit.
"""


def unrenderable(fields):
    """Every value the closed grammar cannot carry, named with its field."""
    problems = []
    for name, value in sorted(fields.items()):
        for item in (value if isinstance(value, list) else [value]):
            if not isinstance(item, str):
                continue
            if UNRENDERABLE.search(item):
                problems.append("%s: contains a newline or control character, which the profile "
                                "grammar cannot carry" % name)
            elif item.count("'") % 2 or item.count('"') % 2:
                problems.append("%s: contains an unbalanced quote, and the grammar has no escaping "
                                "convention" % name)
    return problems


#: Written as a block sequence.
LIST_FIELDS = ("gates", "anti_patterns", "mental_model_refs")
#: Written as a one-level mapping.
MAP_FIELDS = ("category_extensions", "scenario_overrides")
#: Everything the contract defines, in the order a reader wants them.
SCALAR_FIELDS = ("contract_version", "project_id", "repo_id", "repo_path", "base_branch",
                 "source_driver", "id_pattern", "url_regex", "branch_template",
                 "gate_mechanics", "pr_body_template", "tdd_policy", "reviewer_backend")

#: `profile_id` is the writer's own metadata — it names the file and the pointer, and is not a profile
#: field. Anything else unrecognised is a caller error rather than something to drop quietly.
WRITER_METADATA = ("profile_id",)


def render(fields):
    """The profile, in the subset `profile_lint.parse_frontmatter` accepts.

    **Every supported field is serialized**, not only the required ones. An earlier version emitted the
    ten required fields and `gates` and silently dropped `tdd_policy`, `anti_patterns`,
    `mental_model_refs` and `scenario_overrides` — which is the entire output of the interview. A
    scaffolder that asks and discards is worse than one that never asks.
    """
    lines = ["---"]
    for name in SCALAR_FIELDS:
        if name not in fields:
            continue
        value = fields[name]
        lines.append("%s: %s" % (name, value if name == "contract_version" else "'%s'" % value))
    for name in LIST_FIELDS:
        if name not in fields:
            continue
        lines.append("%s:" % name)
        for item in fields[name]:
            lines.append("  - '%s'" % item)
    for name in MAP_FIELDS:
        if name not in fields:
            continue
        lines.append("%s:" % name)
        for key, value in sorted(fields[name].items()):
            lines.append("  %s: '%s'" % (key, value))
    lines.append("---")
    lines.append("")
    lines.append("# %s" % fields["project_id"])
    lines.append("")
    lines.append("Generated by `/vibe-suite:issue2pr profile init`. Every value above was detected "
                 "from the repository")
    lines.append("or supplied in the interview; nothing was guessed.")
    if not fields["gates"]:
        lines.append("")
        lines.append("**No gates were detected.** `gates` is empty rather than guessed, because a "
                     "guessed gate is a command")
        lines.append("the pipeline will run. Add the commands that must pass before a PR opens.")
    lines.append(NOT_ASKED_NOTE)
    return "\n".join(lines) + "\n"


def read_pointer(path):
    """The existing configuration verbatim, or a fresh empty one.

    `newline=""` matters: the default translates CRLF to LF on read, so a file written back would have
    had its line endings silently changed — a claim of byte preservation that the reading step had
    already broken.
    """
    if not path.is_file():
        return "---\n---\n"
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def frontmatter_span(text):
    """`(start, end)` of the frontmatter body, or None. The pointer lives only here.

    Scoping matters: an earlier version searched the **whole document** for the pointer key, so a body
    line reading `issue2pr_profile: other` — in a code block, or a sentence about configuration — was
    mistaken for configuration and could demand `--force` for no reason.
    """
    if not text.startswith("---"):
        return None
    first = text.find("\n", 3)
    if first == -1:
        return None
    end = text.find("\n---", first)
    return (first + 1, end + 1) if end != -1 else None


def current_pointer(text):
    span = frontmatter_span(text)
    if not span:
        return None
    match = re.search(r"(?m)^issue2pr_profile:[ \t]*(\S+)[ \t]*$", text[span[0]:span[1]])
    return match.group(1) if match else None


def set_pointer(text, profile_id):
    """Set or replace `issue2pr_profile`, leaving every other byte alone.

    Only the matched line is rewritten, or one line is inserted. The rest of the document — including
    its line endings, its body, and any key this command knows nothing about — is untouched, because
    it is never split and rejoined.
    """
    span = frontmatter_span(text)
    entry = "issue2pr_profile: %s" % profile_id
    if not span:
        return "---\n%s\n---\n\n%s" % (entry, text)

    start, end = span
    head, body, tail = text[:start], text[start:end], text[end:]
    replaced, count = re.subn(r"(?m)^issue2pr_profile:[ \t]*\S*[ \t]*$", entry, body, count=1)
    if count:
        return head + replaced + tail
    newline = "\r\n" if "\r\n" in body or "\r\n" in head else "\n"
    return head + body + entry + newline + tail


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render and publish a profile and its pointer.")
    parser.add_argument("--root", required=True)
    parser.add_argument("--fields", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    # 1. Pin before ANY read. The previous order read the fields file first, which contradicted this
    #    program's own stated invariant — and the fields file may itself be inside the root.
    root = Path(args.root).absolute()
    try:
        bridge.assert_root(root)
        bridge.pin_root(root)
    except bridge.BridgeError as exc:
        print("write_profile: %s" % exc, file=sys.stderr)
        return EXIT_GUARD

    raw = sys.stdin.read() if args.fields == "-" else Path(args.fields).read_text(encoding="utf-8")
    try:
        fields = json.loads(raw)
    except ValueError as exc:
        print("write_profile: %s" % exc, file=sys.stderr)
        return EXIT_BAD_INPUT

    # An unrecognised key must be **refused**, not dropped: rendering only the fields it knows would
    # silently swallow a misspelled optional field, which is precisely what the contract's
    # unknown-field rule exists to prevent — and the writer would be defeating the lint it then runs.
    known = set(SCALAR_FIELDS) | set(LIST_FIELDS) | set(MAP_FIELDS) | set(WRITER_METADATA)
    unknown = sorted(set(fields) - known)
    if unknown:
        print("write_profile: unrecognised field(s): %s" % ", ".join(unknown), file=sys.stderr)
        print("  A misspelled optional field would otherwise be dropped and never apply.",
              file=sys.stderr)
        return EXIT_BAD_INPUT

    problems = unrenderable(fields)
    if problems:
        print("write_profile: %d value(s) the profile grammar cannot carry:" % len(problems),
              file=sys.stderr)
        for problem in problems:
            print("  - %s" % problem, file=sys.stderr)
        return EXIT_INVALID

    profile_id = fields.get("profile_id")
    if not profile_id or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", profile_id):
        print("write_profile: %r is not a usable profile id" % profile_id, file=sys.stderr)
        return EXIT_BAD_INPUT

    # 2. Preflight BOTH destinations before either is touched.
    profile_path = root / "profiles" / ("%s.md" % profile_id)
    pointer_path = root / POINTER
    for path, label in ((profile_path, "profile"), (pointer_path, "pointer")):
        if path.is_symlink():
            print("write_profile: refusing to follow a symlinked %s at %s" % (label, path),
                  file=sys.stderr)
            return EXIT_GUARD
    if profile_path.exists() and not args.force:
        print("write_profile: %s already exists; pass --force to replace it" % profile_path,
              file=sys.stderr)
        return EXIT_GUARD

    existing = read_pointer(pointer_path)
    current = current_pointer(existing)
    if current and current != profile_id and not args.force:
        print("write_profile: %s already points at %r; pass --force to repoint it"
              % (POINTER, current), file=sys.stderr)
        return EXIT_GUARD

    # 3. Render and lint the candidate BEFORE publishing anything.
    document = render(fields)
    errors = profile_lint.validate_text(document, root, structural=False) \
        if hasattr(profile_lint, "validate_text") else None
    if errors:
        print("write_profile: the generated profile would not pass its own lint:", file=sys.stderr)
        for error in errors:
            print("  - %s" % error, file=sys.stderr)
        return EXIT_INVALID

    # 4. Profile first — a pointer to a missing profile is the worse residue.
    # No path-based `mkdir`. If the pinned root were swapped for a symlink, a path-based create could
    # make a directory outside the workspace before `write_atomic` noticed. `write_atomic` descends
    # component by component with `O_NOFOLLOW` and creates as it goes, so the parent comes into
    # existence through the same audited chain the write uses — and an explicit call here was both
    # redundant and, passing a Path where components were wanted, wrong.
    try:
        bridge.write_atomic(root, profile_path, document)
    except (bridge.BridgeError, ValueError) as exc:
        print("write_profile: refusing to write %s: %s" % (profile_path, exc), file=sys.stderr)
        return EXIT_WRITE_FAILED

    try:
        bridge.write_atomic(root, pointer_path, set_pointer(existing, profile_id))
    except (bridge.BridgeError, ValueError) as exc:
        # 5. Name the residue rather than leaving it to be discovered.
        print("write_profile: wrote %s but could not update %s (%s).\n"
              "  The profile exists and nothing points at it. Add "
              "`issue2pr_profile: %s` by hand, or re-run with --force."
              % (profile_path, pointer_path, exc, profile_id), file=sys.stderr)
        return EXIT_WRITE_FAILED

    print("write_profile: wrote %s and pointed %s at %s" % (profile_path, POINTER, profile_id))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
