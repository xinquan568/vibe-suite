#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fail the build when a shipped artifact names a versioned model identifier (E0.7 / vibe-9).

P9: shipped artifacts never name a versioned model ID. AC-9(a) scopes that to shipped
runtime-reachable artifacts and enumerates four families — `gpt-<digit>`, `gemini-<digit>`,
`o<digit>-`, and dated `claude-*-20*` — while explicitly permitting tier aliases (`sonnet`,
`opus-class`), documentation, and per-run overrides.

Two design choices carry most of the weight.

**Scope is an explicit allowlist, checked for totality.** `SCANNED` and `EXCLUDED` name every
top-level entry, and a path in neither raises `UnclassifiedEntryError` rather than being quietly
passed over. An allowlist alone fails silently — add a directory, forget to list it, and it is never
scanned with nothing to say so. Refusing to guess turns that silence into a loud error, and
`test_partition_is_total` turns it into a failing test the moment a new entry is tracked. The
alternative, scanning everything except a deny-list, would enforce a broader policy than AC-9
authorises.

**Matching is full-token, and `.` is a token separator.** Each line is split into tokens and each
whole token is matched with `fullmatch`. An unanchored search reports `photo3-processing` and
`my-gpt-5-wrapper`; anchoring only the front reports `claude-x-20241022suffix`. Both matter more
than they look, because this runs inside a required status check where a false positive blocks every
pull request in the repository. Treating `.` as a separator is what keeps
`claude-sonnet-4-20250514.json` in scope: as one token it would end in `.json` and the trailing
anchor would let it through. The cost is that the reported token can be a prefix of the id as
written — `gpt-5.6-sol` is reported via `gpt-5` — which is why the diagnostic prints the source line
as well as the token.

Usage:
    python3 tools/model-pin-lint.py [root]      # root defaults to the working directory

Exit codes: 0 clean, 1 violation found or the scan could not be completed.
"""

import re
import subprocess
import sys
from pathlib import Path

# Top-level entries whose contents ship and are reachable at runtime.
SCANNED = frozenset(
    {
        ".claude-plugin",  # the shipped manifest pair
        "agents",
        "auditor",  # "the deployable audit unit"
        "bin",  # "programs, not prompts — they ship with tests"
        "codex",  # generated Codex-CLI mirror of shipped artifacts
        "commands",
        "hooks",  # executed by the harness
        "schemas",
        "scripts",  # "used by commands, hooks and CI"
        "skills",
        "templates",  # "copied or rendered into a target project"
    }
)

# Top-level entries outside AC-9's scope. `docs/` is allowlisted by AC-9 itself; the rest are not
# shipped as plugin functionality. `.github/` is CI infrastructure — `ci.yml` is instead covered by
# assertions in tests/test_model_pin_lint.py, since nothing here scans it.
EXCLUDED = frozenset(
    {
        ".github",
        ".gitignore",
        "LICENSE",
        "README.md",  # root documentation; nested READMEs under a scanned directory ARE scanned
        "docs",
        "tests",  # a test asserting `o3-mini` is caught must contain `o3-mini`
        "tools",  # "not shipped as plugin functionality and not registered in the manifest"
    }
)

# AC-9(a)'s four families, matched against a whole token. The trailing `[A-Za-z0-9_-]*` on the
# first three is load-bearing: without it `gpt-5-mini` and `gpt-4o` pass while `gpt-5` is caught.
GRAMMARS = tuple(
    re.compile(pattern)
    for pattern in (
        r"gpt-[0-9][A-Za-z0-9_-]*",
        r"gemini-[0-9][A-Za-z0-9_-]*",
        r"o[0-9]-[A-Za-z0-9_-]*",
        r"claude-[A-Za-z0-9_-]*-20[0-9]{6}",
    )
)

# `.` is absent from the token class deliberately — see the module docstring.
_SEPARATOR = re.compile(r"[^A-Za-z0-9_-]+")


class EnumerationError(Exception):
    """The set of files to scan could not be determined."""


class ReadError(Exception):
    """A file that should have been scanned could not be read."""


class UnclassifiedEntryError(Exception):
    """A top-level entry is in neither SCANNED nor EXCLUDED."""


class Violation:
    __slots__ = ("path", "line", "token", "text")

    def __init__(self, path, line, token, text):
        self.path = path
        self.line = line
        self.token = token
        self.text = text

    def __repr__(self):
        return f"Violation({self.path}:{self.line}: {self.token})"

    def format(self):
        return f"{self.path}:{self.line}: {self.token}\n    {self.text.strip()}"


def tokenize(text):
    """Split a line into candidate tokens."""
    return [token for token in _SEPARATOR.split(text) if token]


def find_pins(text):
    """Return every token in `text` that is a versioned model identifier."""
    return [
        token
        for token in tokenize(text)
        if any(grammar.fullmatch(token) for grammar in GRAMMARS)
    ]


def git_lister(root):
    """List tracked files under `root`, relative and POSIX-separated.

    Tracked-only is what keeps build products out of the scan: `py_compile` runs earlier in the
    same CI job and leaves `__pycache__/*.pyc` behind.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:  # git missing
        raise EnumerationError(f"could not run git: {exc}") from exc
    if result.returncode != 0:
        raise EnumerationError(
            f"git ls-files failed in {root}: {result.stderr.strip() or 'not a git repository'}"
        )
    return sorted(part for part in result.stdout.split("\0") if part)


def in_scope(relpath):
    """Whether `relpath` is a shipped runtime-reachable artifact.

    Raises `UnclassifiedEntryError` when its top-level entry is in neither set — an unlisted
    directory is a configuration error, not a pass.
    """
    top = relpath.split("/", 1)[0]
    if top in EXCLUDED:
        return False
    if top in SCANNED:
        return True
    raise UnclassifiedEntryError(
        f"{top!r} is in neither SCANNED nor EXCLUDED; classify it in tools/model-pin-lint.py"
    )


def scan(root, lister=git_lister, notice=None):
    """Return every violation under `root`, in sorted path order.

    `lister` supplies the files to consider, which is what lets the unit tests drive real scanning
    logic over a temporary tree while production uses `git ls-files`.
    """
    if notice is None:
        notice = lambda message: print(message, file=sys.stderr)  # noqa: E731
    root = Path(root)
    violations = []
    for relpath in sorted(lister(root)):
        if not in_scope(relpath):
            continue
        path = root / relpath
        if path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            notice(f"model-pin-lint: skipped (not UTF-8 text): {relpath}")
            continue
        except OSError as exc:
            raise ReadError(f"could not read {relpath}: {exc}") from exc
        for number, line in enumerate(text.splitlines(), start=1):
            for token in find_pins(line):
                violations.append(Violation(relpath, number, token, line))
    return violations


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = argv[0] if argv else "."
    try:
        violations = scan(root)
    except EnumerationError as exc:
        print(f"model-pin-lint: enumeration failed: {exc}", file=sys.stderr)
        return 1
    except ReadError as exc:
        print(f"model-pin-lint: read failed: {exc}", file=sys.stderr)
        return 1
    except UnclassifiedEntryError as exc:
        print(f"model-pin-lint: {exc}", file=sys.stderr)
        return 1

    if violations:
        print(f"P9 violation: {len(violations)} pinned model identifier(s) in shipped artifacts")
        for violation in violations:
            print(violation.format())
        return 1
    print("ok: no pinned model identifiers in shipped artifacts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
