#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The shell the macOS smoke runs must stay portable to bash 3.2 (vibe-340).

`macos-latest` ships Bash 3.2.57 and nothing newer, and every developer Mac has Homebrew bash 5 first on PATH — so a
bash-4 construct in shipped shell passes every local run and fails only the weekly runner. Two such constructs kept
`macOS smoke (weekly)` red from its first scheduled run: `mapfile`, and `"${ARR[@]}"` on an empty array under
`set -u`, which bash < 4.4 reports as an unbound variable.

This test is a census over text, not a shell parser. It enumerates every shell file and workflow the macOS job's
Python suite can execute (`IN_SCOPE`, with every exclusion in `OUT_OF_SCOPE` named with its reason) and holds each
to three rules:

1. The words `mapfile` and `readarray` do not appear, in any role, on any line that is not a whole-line comment.
   This is deliberately not a command-position rule: a text census cannot parse bash (assignment prefixes,
   `command --`, quoted operators, `#` inside a word, a `;(` run together, an unbalanced quote in prose can each
   move a word into or out of command position), so the census refuses to guess. It bans the word. `echo "mapfile"`
   is a hit as much as `mapfile -t x` is, and the remedy for a harmless mention is another word or a whole-line
   comment. The scope contains no such mention today, so the rule costs nothing and can only over-report.
2. Every expansion `${NAME[@]}` or `${NAME[*]}`, quoted or not, of an array that the same text initialises empty
   (`NAME=()`, `NAME=( )`, or any name on a `declare`/`local`/`typeset -a` line — rule 3 says what such a line may
   carry) is written in the guarded form `${NAME[@]+"${NAME[@]}"}`, unless `ALLOWLIST[(file, NAME)]` names it with
   the reason the bare form is safe there. An allowlist entry that no longer matches anything fails as stale.
3. The only arguments a `declare`/`local`/`typeset -a` line may carry are plain names, followed by nothing but an
   optional `# comment`. Each such name is initialised empty. Anything else on the line is a form the census does
   not read, and the file fails naming the line rather than the census guessing: an initialiser of any kind
   (`A=()`, `A=(x)`, `D=($maybe_empty)`, `D='()'`, `A=word`), a `"$var"`, a glob, a `$(...)`, or a second command
   after the names (`; declare -a D`). The remedy is mechanical: the names alone on the `-a` line, and each
   initialisation on its own line as `NAME=(...)`, which rule 2 reads. Every `declare`/`local`/`typeset` on a line
   is inspected on its own, so a non-array declaration before it (`declare -i X; declare -a D`) hides nothing.

Declared limits of a text census — each is a false negative the behavioural gates (the `bash32` rung locally, the
macOS job weekly) exist to catch, and none occurs in the scope today: a builtin whose name is not written as one word
(`'map''file'`, `"${cmd}file"`, a string assembled for `eval`; `\\mapfile` IS seen, since `\\` is a word boundary);
an array whose emptiness a text scan cannot see (`declare -a` in one function, expansion in another, or a name built
dynamically). Declared sources of false positives, none present today: either construct inside a trailing `#`
comment on a code line (only whole-line comments are blanked, so a `#` inside quotes can never hide code); a
workflow's YAML data or a heredoc body, which are scanned as if they were shell; and, by design, a harmless mention
of the banned words.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Shell the macOS job executes. The Python suite extracts the auditor workflows' run blocks and runs them, runs
#: the helpers under `auditor/scripts/`, `tests/run-parallel.sh`, the three `tools/*.sh` gates, `site/build.sh`, the
#: plugin's `scripts/*.sh` and `scripts/migrate/*.sh`; the job's own steps are in self-check.yml. Globs are relative
#: to the repository root and do not recurse: `tests/fixtures/**` holds shell the security scanner reads as data
#: and never executes.
IN_SCOPE = (
    "auditor/workflows/*.yml",
    "auditor/scripts/*.sh",
    "tests/*.sh",
    "tools/*.sh",
    "site/*.sh",
    "scripts/*.sh",
    "scripts/migrate/*.sh",
    "hooks/*.sh",
    ".github/workflows/*.yml",
)
#: Shell that never runs on macOS, with the reason. A file here is matched by IN_SCOPE and then skipped, so removing
#: an entry puts that file under the rules (ci.yml uses mapfile on ubuntu, and would fail them).
OUT_OF_SCOPE = {
    ".github/workflows/ci.yml": "every job runs on ubuntu-latest (bash 5)",
    ".github/workflows/pre-release-quality-gate.yml": "runs on ubuntu-latest (bash 5)",
}
#: Bare expansions of an empty-initialised array that are safe, by exact (file, array), each with its reason.
ALLOWLIST = {
    ("tests/run-parallel.sh", "MODULES"): "the script exits before the expansion when the count is 0",
    ("scripts/migrate/migrate-state.sh", "legacy_dirs"): "defaulted to two paths before the expansion when the count is 0",
    ("tools/site-brand-check.sh", "files"): "the script exits before the expansion when the count is 0",
}
#: The files behind the failures this test exists for, and the job's own workflow: they must stay in the census.
MUST_COVER = (
    "auditor/workflows/auditor-contribute.yml",
    "tests/run-parallel.sh",
    ".github/workflows/self-check.yml",
    "tools/site-brand-check.sh",
    "tools/legacy-string-sweep.sh",
    "tools/migrate-auditor-data.sh",
    "site/build.sh",
)

BUILTIN_RE = re.compile(r"\b(mapfile|readarray)\b")   # the word, in any role: the census refuses to parse bash
NAME = r"[A-Za-z_][A-Za-z_0-9]*"
EMPTY_ASSIGN_RE = re.compile(r"\b(" + NAME + r")=\(\s*\)")
# a declaration: the builtin word wherever it starts (a word boundary, so `x)declare -a D` after a case pattern and
# `(declare -a D)` count, and no list of allowed prefixes can be incomplete), its flags, and the arguments (the rest
# of the line) as a LOOKAHEAD: the match ends after the flags, so a later `declare` on the same line is found on its
# own and a non-array declaration before it (`declare -i X; declare -a D`) cannot swallow it. The flags are
# blank-separated, never newline-separated, so a bare `declare -a` never reads the next line as its arguments.
DECL_LINE_RE = re.compile(r"\b(?:declare|local|typeset)[ \t]+((?:-[a-zA-Z]+[ \t]+)+)(?=([^\n]*))")
# the arguments a declaration line may carry: plain names, then at most a `# comment`. No initialiser of any kind,
# no expansion, no second command: a text census cannot decide what those leave in the array, so it refuses them
DECL_ARGS_RE = re.compile(r"(?:" + NAME + r"\s+)*" + NAME + r"\s*(?:#.*)?")
EXPANSION_RE = re.compile(r"\$\{(" + NAME + r")\[[@*]\]\}")
GUARDED_RE = re.compile(r'\$\{(' + NAME + r')\[[@*]\]\+"\$\{\1\[[@*]\]\}"\}')


def strip_comments(text):
    """Blank whole-line comments (keeping the line count, so reported line numbers are the file's). Trailing
    comments are left alone: a `#` inside quotes is not a comment, and a text scan cannot tell the two apart."""
    return "\n".join("" if line.lstrip().startswith("#") else line for line in text.splitlines())


class UnsupportedDeclaration(ValueError):
    """A `-a` declaration line in a form the census does not read; it refuses rather than guesses."""


def declared_arrays(args):
    """The names on one `-a` declaration line, every one of them (round-2 F1), each initialised empty — the only
    arguments the census accepts are plain names. Raises UnsupportedDeclaration for anything else (rule 3)."""
    if not DECL_ARGS_RE.fullmatch(args):
        raise UnsupportedDeclaration(args.strip())
    return set(args.split("#", 1)[0].split())


def empty_initialised(code):
    """Names the text initialises empty: `NAME=()` anywhere, and every name of every `-a` declaration line."""
    empty = set(EMPTY_ASSIGN_RE.findall(code))
    for m in DECL_LINE_RE.finditer(code):
        flags, args = m.group(1), m.group(2)
        if "a" not in flags:            # `-i`, `-r`, `-A` (associative): not an indexed array declaration
            continue
        empty |= declared_arrays(args)
    return empty


def census(root, files):
    """The file-level census: (unsupported, bare). `unsupported` lists (file, declaration-arguments) for every `-a`
    declaration the census refuses (rule 3); `bare` is {(file, name)} for every empty-initialised array expanded
    unguarded (rule 2). A refused file contributes to `unsupported` only: its arrays cannot be judged."""
    unsupported, bare = [], set()
    for rel in files:
        text = (root / rel).read_text(encoding="utf-8")
        try:
            names = bare_expansions(text)
        except UnsupportedDeclaration as e:
            unsupported.append((rel, str(e)))
            continue
        bare |= {(rel, name) for name in names}
    return unsupported, bare


def bare_expansions(text):
    """{name} of arrays initialised empty and expanded unguarded somewhere in `text`."""
    code = strip_comments(text)
    guarded_spans = [m.span() for m in GUARDED_RE.finditer(code)]
    empty = empty_initialised(code)
    bare = set()
    for m in EXPANSION_RE.finditer(code):
        if any(a <= m.start() and m.end() <= b for a, b in guarded_spans):
            continue
        if m.group(1) in empty:
            bare.add(m.group(1))
    return bare


def mapfile_sites(text):
    """1-based line numbers of lines carrying the word `mapfile` or `readarray` in any role, whole-line comments
    blanked (rule 1: refuse to parse, ban the word)."""
    return [i for i, line in enumerate(strip_comments(text).splitlines(), 1) if BUILTIN_RE.search(line)]


def in_scope_files():
    files = []
    for pattern in IN_SCOPE:
        files += sorted(p for p in REPO_ROOT.glob(pattern) if p.is_file())
    rels = [p.relative_to(REPO_ROOT).as_posix() for p in files]
    return [r for r in rels if r not in OUT_OF_SCOPE]


class TestBash32Portability(unittest.TestCase):
    def setUp(self):
        self.files = in_scope_files()
        self.assertGreater(len(self.files), 10, "the scope glob found almost nothing: the census is broken")

    def test_no_mapfile_or_readarray(self):
        for rel in self.files:
            with self.subTest(file=rel):
                self.assertEqual(mapfile_sites((REPO_ROOT / rel).read_text(encoding="utf-8")), [],
                                 f"{rel} uses mapfile/readarray, a bash-4 builtin macOS's bash 3.2 lacks")

    def test_every_array_declaration_is_a_form_the_census_reads(self):
        """Rule 3: a `-a` declaration the census cannot read fails the file, naming the line, rather than being
        guessed at (round-2 F1). `census()` is the one scan both file tests use; `TestCensusParsers` plants a
        refused file through it, so this handler is exercised even while the scope has no declarations."""
        unsupported, _ = census(REPO_ROOT, self.files)
        self.assertEqual(unsupported, [], "an array declaration form the census does not read; put the plain names "
                                          "alone on the -a line and each initialisation on its own line as NAME=(...)")

    def test_empty_initialised_arrays_are_expanded_guarded(self):
        _, bare = census(REPO_ROOT, self.files)
        seen = set()
        for rel, name in sorted(bare):
            seen.add((rel, name))
            with self.subTest(file=rel, array=name):
                self.assertIn((rel, name), ALLOWLIST,
                              f'{rel}: ${{{name}[@]}} can be empty; bash 3.2 + set -u reports an unbound '
                              f'variable. Write ${{{name}[@]+"${{{name}[@]}}"}}, or allowlist it with a reason')
        self.assertEqual(sorted(set(ALLOWLIST) - seen), [], "stale ALLOWLIST entries")

    def test_scope_covers_the_files_that_the_suite_executes(self):
        for rel in MUST_COVER:
            with self.subTest(file=rel):
                self.assertIn(rel, self.files)

    def test_out_of_scope_files_exist(self):
        for rel in OUT_OF_SCOPE:
            with self.subTest(file=rel):
                self.assertTrue((REPO_ROOT / rel).is_file(), f"{rel} is excluded but does not exist")


class TestCensusParsers(unittest.TestCase):
    def test_every_empty_initialisation_spelling(self):
        code = "A=()\nB=( )\ndeclare -a C\nlocal -ra D\ntypeset -a E\nG=(x)\ndeclare -i H\n"
        self.assertEqual(empty_initialised(code), {"A", "B", "C", "D", "E"})

    def test_every_name_of_a_declaration_line_is_read(self):
        """Round-2 F1: `declare -a A B` initialises B empty too; the `-a` flag may come in any position; a trailing
        comment does not hide the names; `-A` (associative) and `-i` lines are not array declarations."""
        code = ("declare -a A B\n"
                "declare -r -a G H  # comment\n"
                "local -a I J\n"
                "declare -A K L\n"
                "declare -i M\n"
                "echo x; typeset -a N\n"
                "declare -i X; declare -a O\n"          # a non-array declaration before it hides nothing (A6)
                "local x=1; declare -a P\n"
                "declare -A Y; local -a Q R\n"
                "case x in x)declare -a S\n"           # right after a case-pattern delimiter (A7)
                "esac\n"
                "( declare -a T\n"
                ")\n"
                "\\declare -a U\n")                     # a backslash before the word is a word boundary too
        self.assertEqual(empty_initialised(code), {"A", "B", "G", "H", "I", "J", "N", "O", "P", "Q", "R", "S", "T", "U"})
        self.assertEqual(empty_initialised("my_declare -a V\nmydeclare -a W\n"), set())   # not the builtin word
        for line in ("declare -i X; declare -a D='()'", "declare -A Y; declare -a D=()", "declare -a A; declare -i X",
                     "case x in x)declare -a D;; esac", "case x in x)declare -a D='()';; esac", 'echo "declare -a D"',
                     "(declare -a D)", "$(declare -a D)"):
            with self.subTest(line=line), self.assertRaises(UnsupportedDeclaration):
                empty_initialised(line + "\n")
        self.assertEqual(bare_expansions('declare -a A B\nprintf "%s" "${B[@]}"\n'), {"B"})
        self.assertEqual(bare_expansions('declare -a A B\nprintf "%s" ${B[@]+"${B[@]}"}\n'), set())

    def test_a_declaration_form_the_census_cannot_read_is_refused(self):
        """Rule 3: refuse, don't guess. Only plain names are read. Every initialiser is refused — the census cannot
        decide what `D=($maybe_empty)`, `` D=(`:`) ``, `D='()'` (an empty compound assignment to bash) or `A=word`
        (a one-element array) leave in the array (round-2 A1, A3) — and so is a second command after the names,
        which would otherwise hide a later declaration (A4)."""
        refused = ('"$name"', "A $(names)", "A *", "A =B", "A=()", "A=(x)", "C=(x) D=($empty)", "D=(`:`)",
                   "A=('(')", "C=(x) D='()'", "A=word", 'A="x"', "A=()B", "A B; echo x", "A B && echo x",
                   "C; declare -a D", "C=(x); declare -a D='()'", "A B |", "")
        for args in refused:
            with self.subTest(args=args), self.assertRaises(UnsupportedDeclaration):
                empty_initialised(f"declare -a {args}\n")
        for args in ("A", "A B", "A B  # c", "A\t B"):
            with self.subTest(args=args):
                self.assertEqual(empty_initialised(f"declare -a {args}\n"), set(args.split("#")[0].split()))
        # a bare `declare -a` lists arrays and declares nothing; the next line is never read as its arguments
        self.assertEqual(empty_initialised("declare -a\nfoo bar\n"), set())

    def test_the_file_census_reports_a_refused_file_and_judges_the_rest(self):
        """The scope has no `-a` declaration today, so the file-level refusal is exercised on a planted tree: the
        refused file is reported with its declaration arguments and contributes no arrays; the other file's bare
        expansion is still found (round-2 P3)."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.sh").write_text("declare -a A='()'\nprintf '%s' \"${A[@]}\"\n", encoding="utf-8")
            (root / "ok.sh").write_text("B=()\nprintf '%s' \"${B[@]}\"\nC=()\nprintf '%s' ${C[@]+\"${C[@]}\"}\n",
                                        encoding="utf-8")
            unsupported, bare = census(root, ["bad.sh", "ok.sh"])
        self.assertEqual(unsupported, [("bad.sh", "A='()'")])
        self.assertEqual(bare, {("ok.sh", "B")})

    def test_every_expansion_spelling_is_seen_and_only_the_guard_is_exempt(self):
        text = ('A=()\nB=()\nC=()\nD=()\nE=()\nF=(x)\n'
                'quoted "${A[@]}"\nunquoted ${B[@]}\nstar "${C[*]}"\nembedded "x${D[@]}y"\n'
                'guarded ${E[@]+"${E[@]}"}\nnonempty "${F[@]}"\n'
                'count "${#A[@]}" keys "${!A[@]}"\n')
        self.assertEqual(bare_expansions(text), {"A", "B", "C", "D"})

    def test_a_guard_on_one_array_does_not_cover_another(self):
        self.assertEqual(bare_expansions('A=()\nB=()\nx ${A[@]+"${B[@]}"}\n'), {"B"})

    def test_a_new_empty_array_beside_its_own_bare_loop_is_caught(self):
        """The trap the fix itself nearly introduced: `FILES=()` then `for f in "${FILES[@]}"`."""
        self.assertEqual(bare_expansions('FILES=()\nwhile read -r f; do FILES+=("$f"); done\nfor f in "${FILES[@]}"; do :; done\n'),
                         {"FILES"})

    def test_comment_lines_are_blanked_and_line_numbers_kept(self):
        text = '# "${A[@]}" in a comment\nA=()\n# mapfile in prose\nmapfile -t x < f\nreadarray -d "" y\n'
        self.assertEqual(bare_expansions(text), set())
        self.assertEqual(mapfile_sites(text), [4, 5], "line numbers are the file's, comment lines included")

    def test_rule_1_bans_the_word_in_every_role(self):
        """Every spelling that puts the builtin in command position is a hit, and so is a harmless mention: the rule
        does not try to tell them apart. Only a different word, or a whole-line comment, is clear."""
        hits = {
            "mapfile -t x < f": True, "  readarray y": True, "x; mapfile -t y": True, "a && mapfile -t y": True,
            "if true; then mapfile -t y; fi": True, "( mapfile -t y )": True, "{ mapfile -t y; }": True,
            "! mapfile -t y": True, "x | mapfile -t y": True, "mapfile": True,
            "X=1 mapfile -t x": True, "command -- mapfile -t x": True, "time -p mapfile -t x": True,
            ":;(mapfile -t x)": True, "echo x#y; mapfile -t x": True,          # direct calls a lexer misread
            "\\mapfile -t y": True, "builtin readarray z": True,
            "mapfile -t x < f 'unbalanced": True, "it doesn't map files; mapfile": True,   # untokenisable lines
            'echo "mapfile"': True, "grep mapfile f": True, 'echo ";" mapfile': True,   # mentions: hits by design
            "foo_mapfile=1": False, "mapfile_count=1": False, "mapfiles": False, "readarrays": False,
            "it doesn't map files": False, "# mapfile in a whole-line comment": False,
        }
        for line, expected in hits.items():
            with self.subTest(line=line):
                self.assertEqual(mapfile_sites(line) == [1], expected)

    def test_declared_limits_are_limits(self):
        """What a text census cannot see, stated in the module docstring: a builtin whose name is never written as
        one word is NOT caught, by design, and the behavioural gates own it. If this starts passing, update the
        docstring."""
        self.assertEqual(mapfile_sites("'map''file' -t x < f\ncmd=map; \"${cmd}file\" -t y < f\neval \"$cmd\"file -t z\n"), [])


if __name__ == "__main__":
    unittest.main()
