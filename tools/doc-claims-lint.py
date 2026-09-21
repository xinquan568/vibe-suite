#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Doc-claims lint (vibe-230): shipped text must not describe the codebase as it used to be.

Three phrases have each outlived what they described: `not yet built`, `when it lands`, `remains open`. A shipped file
that uses one fails the lint unless an allowlist entry below names that file and that sentence, with the issue where the
use was judged. An allowlist entry that no longer allows anything also fails, as stale, so the list cannot rot.

**Scope** is the shipped surface as `tools/model-pin-lint.py` defines it: tracked files only, through its `git_lister`,
filtered by its `in_scope`, including its rule that an unclassified top-level entry is an error, not a pass. One home for
"what ships", not two.

**A phrase may span a line break**, as `commands/check.md` did ("when it" / "lands"). Words are matched with any run of
whitespace between them, and that run may also cross a comment leader (`#`, `//`, `*`, `>`) at the start of the next
line, so a claim wrapped inside a comment block is still one claim.

    python3 tools/doc-claims-lint.py        # exit 0 clean; 1 on a claim, a stale entry or a scope error; 2 on a usage error
"""
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_pin_lint():
    spec = importlib.util.spec_from_file_location("model_pin_lint_for_doc_claims", ROOT / "tools" / "model-pin-lint.py")
    mod = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # no __pycache__ in tools/
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
    return mod


PIN_LINT = _load_pin_lint()

PHRASES = ("not yet built", "when it lands", "remains open")

#: Between two words of a phrase: horizontal whitespace of any kind (`[^\S\n]`: spaces, tabs, a no-break space), or ONE
#: line break with indentation and an optional comment leader. Two line breaks, a blank line, end the match.
_GAP = r"(?:[^\S\n]*\n[^\S\n]*(?:#|//|\*|>)?[^\S\n]*|[^\S\n]+)"
PATTERNS = {p: re.compile(_GAP.join(re.escape(w) for w in p.split()), re.IGNORECASE) for p in PHRASES}

#: (path, a substring of the hit's first line, the issue where the use was judged, why it is not a stale claim)
ALLOWLIST = (
    ("commands/fix.md", "The loop also stops when nothing remains open", 230,
     "the fix loop's stop condition, not a statement about the codebase"),
    ("codex-src/audit-fix/SKILL.md", "if anything remains open", 230,
     "the skill's non-interactive posture, not a statement about the codebase"),
    ("codex/skills/audit-fix/SKILL.md", "if anything remains open", 230,
     "the generated mirror of codex-src/audit-fix/SKILL.md"),
    ("skills/issue2pr/SKILL.md", "It records what remains open", 230,
     "what a stopped round records, not a statement about the codebase"),
)


def find_claims(text):
    """[(line number, phrase, the hit's first line)] for every phrase occurrence in `text`."""
    lines = text.split("\n")
    hits = []
    for phrase, pattern in PATTERNS.items():
        for m in pattern.finditer(text):
            n = text.count("\n", 0, m.start())
            hits.append((n + 1, phrase, lines[n]))
    return sorted(hits)


def scan(root, lister=None, allowlist=ALLOWLIST):
    """(violations, stale entries). `lister` defaults to model-pin-lint's `git_lister`; tests pass their own."""
    root = Path(root)
    files = (lister or PIN_LINT.git_lister)(root)
    used = set()
    violations = []
    for rel in files:
        if not PIN_LINT.in_scope(rel):
            continue
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
            continue  # binary or vanished: no prose to judge
        for line_no, phrase, line in find_claims(text):
            allowed = [i for i, (p, sub, _issue, _why) in enumerate(allowlist) if p == rel and sub in line]
            if allowed:
                used.update(allowed)
            else:
                violations.append((rel, line_no, phrase, line.strip()))
    stale = [allowlist[i] for i in range(len(allowlist)) if i not in used]
    return violations, stale


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print(f"doc-claims-lint: unknown argument {argv[0]!r} (the lint takes none)", file=sys.stderr)
        return 2
    try:
        violations, stale = scan(ROOT)
    except (PIN_LINT.EnumerationError, PIN_LINT.UnclassifiedEntryError) as exc:
        # 1, as model-pin-lint returns for the same two errors; 2 is kept for a usage error
        print(f"doc-claims-lint: {exc}", file=sys.stderr)
        return 1
    for rel, line_no, phrase, line in violations:
        print(f"{rel}:{line_no}: \"{phrase}\" — a status claim that may no longer be true: {line}")
    for rel, sub, issue, _why in stale:
        print(f"stale allowlist entry (#{issue}): {rel} no longer holds a phrase on a line containing {sub!r}")
    if violations or stale:
        print(f"doc-claims-lint: {len(violations)} claim(s), {len(stale)} stale allowlist entr(y/ies). Fix the text, "
              "or allowlist the sentence in tools/doc-claims-lint.py with the issue that judged it.")
        return 1
    print("doc-claims-lint: clean — no stale status claims in shipped text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
