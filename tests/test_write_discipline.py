#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""No direct filesystem mutation outside the audited primitive (E?? / vibe-94).

**This is the deliverable that makes the issue an invariant instead of a snapshot.** Fourteen
implementation passes on #21 each fixed the writers they were shown and revealed more of the same
class; three separate passes guarded one writer of `.vibe-suite.md` while an *earlier* writer went
untouched. A guard a caller can forget will be forgotten, so the rule is enforced mechanically.

**AST, not grep.** A textual sweep flags `sys.stdout.write`, `str.replace`, read-only `open`, and
comments, and misses mutators reached through an alias. Matching call *shapes* on the parsed tree
avoids both, which is what keeps a lint like this switched on rather than disabled as noisy.

Scope: Python under `scripts/`, including the Python embedded in `scripts/migrate/*.sh` heredocs.
The Node surface (`lib/jobs.mjs`'s hard-link CAS, the hooks, the runners) has different primitives
and is re-homed to a follow-up rather than silently covered — see `EXEMPT` below.
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"

#: The primitive itself, and the module that owns the descriptor discipline it is built on.
PRIMITIVE = {"scripts/lib/bridge.py"}

#: Mutating call shapes. Method names are matched on the attribute, so `p.write_text(...)` is caught
#: whatever `p` is called; bare names are matched only when they resolve to the `os` module.
MUTATING_METHODS = {
    "write_text", "write_bytes", "unlink", "rmdir", "touch", "symlink_to", "hardlink_to",
    "chmod", "rename", "lchmod",
}

#: `mkdir` is deliberately absent. It creates or (with `exist_ok`) no-ops — it cannot overwrite a
#: file or destroy content, and this rule is about destroying or exposing what the user owns.
#: Including it produced fourteen findings that had no defect behind them, and a lint whose findings
#: are mostly noise is a lint that gets switched off.

#: `.replace()` is the one name shared by a path mutator and a string method, and the arity tells
#: them apart: `Path.replace(target)` takes exactly one argument, `str.replace(old, new)` takes two.
#: Without this, every `cell.replace("**", "")` in `config.py` was reported as a filesystem write.
def _is_path_replace(node):
    return len(node.args) == 1 and not node.keywords
MUTATING_OS = {
    "remove", "unlink", "rmdir", "removedirs", "rename", "renames", "replace", "mkdir",
    "makedirs", "symlink", "link", "chmod", "chown", "truncate", "mkfifo", "mknod",
}

#: `str.replace` and `list.remove` share names with mutators. A call is only interesting when its
#: receiver could be a path — so a call whose receiver is a literal string is skipped outright.
#: Anything else is reported; a false positive is fixed by routing the call, not by widening this.
SAFE_RECEIVER_TYPES = (ast.Constant, ast.JoinedStr)  # `ast.Str` was removed in 3.12

#: Sites deliberately not covered, each with a reason. A whole-file entry here is a claim that the
#: file has no mutation to audit; an entry with a reason is a scoping decision, not an oversight.
EXEMPT = {
    # The primitive and its descriptor plumbing — this is where the low-level calls belong.
    "scripts/lib/bridge.py": "the audited primitive itself",
}

#: **Empty, and it stays empty.** This began as a ratchet with 37 recorded sites so the sweep could
#: run in CI while they were routed one at a time. They are all routed now, so the exception list is
#: the strongest statement it can be: there are no exceptions.
#:
#: A new entry here is a claim that some mutation cannot go through the primitive. That claim needs
#: a reason next to it, and it should be rare enough to argue about.
KNOWN = set()


def _python_sources():
    """Every Python file under `scripts/`, plus the Python embedded in migrate heredocs."""
    for path in sorted(SCRIPTS.rglob("*.py")):
        yield str(path.relative_to(REPO_ROOT)), path.read_text(encoding="utf-8")
    for path in sorted(SCRIPTS.rglob("*.sh")):
        text = path.read_text(encoding="utf-8")
        # `python3 - ... <<'PY' ... PY` — the quoted delimiter means no shell expansion, so the
        # body is literal Python and parses as-is.
        for index, block in enumerate(re.findall(r"<<'PY'\n(.*?)\nPY\n", text, re.S)):
            yield f"{path.relative_to(REPO_ROOT)}#heredoc{index}", block


def _mutations(tree):
    """`(lineno, description)` for every mutating call shape in a parsed module."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            if func.attr in ("write", "writelines"):
                # `handle.write` on a file opened for writing is a mutation; on stdout/stderr it is
                # not. Only the stream case is structurally recognisable, so it is what gets skipped.
                receiver = func.value
                if isinstance(receiver, ast.Attribute) and receiver.attr in ("stdout", "stderr"):
                    continue
                if isinstance(receiver, ast.Name) and receiver.id in ("sys", "stdout", "stderr"):
                    continue
                found.append((node.lineno, f".{func.attr}()"))
                continue
            if func.attr == "replace":
                # `os.replace(src, dst)` takes two arguments and is a rename — it must be checked
                # before the arity rule below, which would otherwise read it as `str.replace`.
                if isinstance(func.value, ast.Name) and func.value.id == "os":
                    found.append((node.lineno, "os.replace()"))
                elif _is_path_replace(node) and not isinstance(func.value, SAFE_RECEIVER_TYPES):
                    found.append((node.lineno, ".replace()"))
                continue
            if func.attr in MUTATING_METHODS:
                if isinstance(func.value, SAFE_RECEIVER_TYPES):
                    continue   # a literal string's `.replace` is not a filesystem call
                if isinstance(func.value, ast.Name) and func.value.id == "os":
                    found.append((node.lineno, f"os.{func.attr}()"))
                    continue
                found.append((node.lineno, f".{func.attr}()"))
                continue
            if isinstance(func.value, ast.Name) and func.value.id == "os" and func.attr in MUTATING_OS:
                found.append((node.lineno, f"os.{func.attr}()"))
                continue
        if isinstance(func, ast.Name) and func.id == "open":
            mode = ""
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                    mode = str(keyword.value.value)
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                found.append((node.lineno, f"open(..., {mode!r})"))
    return found


#: Shell redirections and mutating shell commands. **A redirection follows a symlink**, so `> path`
#: writes through a link planted at a fixed path — and none of it is visible to an AST sweep, which
#: is how one survived the pass that routed every Python write.
_SHELL_WRITE = re.compile(
    r"(?<![0-9<>])>>?\s*[\"']?\$?[A-Za-z_./{]"     # > path / >> path, not 2>&1 or a heredoc
    r"|^\s*(mv|cp|rm|ln|install|truncate|chmod|chown|touch|mkfifo)\s",
    re.M)

#: Redirections to a throwaway destination mutate nothing the user owns.
_SHELL_SAFE = re.compile(r">\s*(&[0-9-]|/dev/null|\$?\{?tmp|\$\(mktemp)")


SHELL_KNOWN = set()


def _shell_writes(text):
    """`(lineno, line)` for shell lines that mutate the filesystem outside the primitive.

    Heredoc bodies are skipped: they are Python, and the AST sweep already covers them. Scanning
    them as shell reports every `re.compile(r"...>...")` as a redirection, and a lint that cries
    wolf gets switched off.
    """
    hits = []
    in_heredoc = False
    for number, line in enumerate(text.split("\n"), 1):
        if in_heredoc:
            if line.strip() == "PY":
                in_heredoc = False
            continue
        if "<<'PY'" in line:
            in_heredoc = True
            continue
        bare = line.split("#", 1)[0]
        if not bare.strip() or "bridge.py" in bare and "write" in bare:
            continue
        if _SHELL_WRITE.search(bare) and not _SHELL_SAFE.search(bare):
            hits.append((number, bare.strip()[:90]))
    return hits


class NoDirectFilesystemMutation(unittest.TestCase):
    def test_every_python_source_parses(self):
        """A heredoc that stopped parsing would silently drop out of the sweep — which is exactly
        how a write site goes unnoticed."""
        for name, source in _python_sources():
            with self.subTest(source=name):
                ast.parse(source)

    def test_the_sweep_actually_sees_the_scripts(self):
        """A lint that scans nothing passes trivially. Two earlier tests in this repo could not
        fail; this asserts the corpus is non-empty and includes the heredocs."""
        names = [name for name, _ in _python_sources()]
        self.assertGreater(len(names), 10, f"the sweep found only {names}")
        self.assertTrue(any("#heredoc" in name for name in names),
                        "no embedded Python was extracted from scripts/migrate/*.sh")

    def test_the_detector_recognises_a_mutation(self):
        """And that it does not fire on a string method or a stdout write."""
        self.assertTrue(_mutations(ast.parse("p.write_text('x')")))
        self.assertTrue(_mutations(ast.parse("os.replace(a, b)")))
        self.assertTrue(_mutations(ast.parse("open(p, 'w')")))
        self.assertFalse(_mutations(ast.parse("'a-b'.replace('-', '_')")))
        self.assertFalse(_mutations(ast.parse("s.strip().replace('a', 'b')")))   # str, two args
        self.assertTrue(_mutations(ast.parse("tmp.replace(target)")))            # Path, one arg
        self.assertFalse(_mutations(ast.parse("d.mkdir(parents=True, exist_ok=True)")))
        self.assertFalse(_mutations(ast.parse("sys.stderr.write('note\\n')")))
        self.assertFalse(_mutations(ast.parse("open(p)")))
        self.assertFalse(_mutations(ast.parse("open(p, 'r')")))

    def test_the_shell_detector_recognises_a_redirection(self):
        self.assertTrue(_shell_writes('printf x > "$target"'))
        self.assertTrue(_shell_writes('mv a b'))
        self.assertFalse(_shell_writes("printf x > /dev/null"))
        self.assertFalse(_shell_writes("cmd 2>&1"))
        # A quoted `"$tmp"` is *not* exempted: the name says scratch, the value may not be. With
        # no sites left to accommodate, strictness costs nothing.
        self.assertTrue(_shell_writes('printf x > "$tmp"'))

    def test_no_shell_redirection_writes_a_real_path(self):
        """The gap that let `init.sh` write `config-resolution.json` with `> path` survive the sweep
        that routed every Python write. A redirection follows a symlink; an AST lint cannot see it."""
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.sh")):
            rel = str(path.relative_to(REPO_ROOT))
            for number, line in _shell_writes(path.read_text(encoding="utf-8")):
                entry = f"{rel}:{number} {line}"
                if entry not in SHELL_KNOWN:
                    offenders.append(entry)
        self.assertEqual(offenders, [], "shell redirection writing a real path — pipe it through "
                                        "`bridge.py write` instead:\n"
                                        + "\n".join(f"  - {o}" for o in offenders))

    def test_no_direct_mutation_outside_the_primitive(self):
        offenders = []
        for name, source in _python_sources():
            base = name.split("#")[0]
            if base in EXEMPT or base in PRIMITIVE:
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue   # reported by test_every_python_source_parses
            for lineno, what in _mutations(tree):
                entry = f"{name}:{lineno} {what}"
                if entry not in KNOWN:
                    offenders.append(entry)
        self.assertEqual(offenders, [], "direct filesystem mutation outside the audited primitive "
                                        "— route it through bridge.write_atomic / publish_new / "
                                        "unlink_at / symlink_at / secure_dir:\n"
                                        + "\n".join(f"  - {o}" for o in offenders))

    def test_the_baseline_only_shrinks(self):
        """A routed site must leave `KNOWN`, or the ratchet quietly stops ratcheting."""
        live = set()
        for name, source in _python_sources():
            base = name.split("#")[0]
            if base in EXEMPT or base in PRIMITIVE:
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue
            for lineno, what in _mutations(tree):
                live.add(f"{name}:{lineno} {what}")
        stale = sorted(KNOWN - live)
        self.assertEqual(stale, [], "these baseline entries no longer exist — delete them from "
                                    "KNOWN so the ratchet keeps its grip:\n"
                                    + "\n".join(f"  - {s}" for s in stale))


if __name__ == "__main__":
    unittest.main()
