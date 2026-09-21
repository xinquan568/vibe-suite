#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The exit-code registry (vibe-231 / grill P4).

`docs/exit-codes.md` holds one table per shipped program; each program states the same codes in one
`Exit codes: 0 … · 1 …` marker line in its header. Nothing related the two before, and the codes had
drifted: `survey.sh` said "Always exits 0" and exits 1, and about twenty programs documented nothing.

**What this proves, and no more** (the page says the same): every candidate file is registered or
listed as not a program; each registered program's marker equals its table, code for code and meaning
for meaning; every module-level `EXIT_*` constant of a Python program has its value in the table; outside
the marker, no line of a program's header states an exit number (two named exceptions, below); and no
docstring line a program prints or hands to argparse is its marker.
It does NOT prove that a literal `return 3` matches the table — the per-program behaviour tests do that
where they exist.

The parsers are pure functions over text, so each is also driven here with the malformed inputs it must
refuse (the self-tests at the bottom).
"""
import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC = REPO_ROOT / "docs" / "exit-codes.md"
HOOKS = ("scripts/session-lifecycle-hook.mjs", "scripts/stop-review-gate-hook.mjs")

MARKER_RE = re.compile(r"^[ \t]*(?:(?:#|//|\*)[ \t]*)?Exit codes: (.+)$", re.M)
PIECE_RE = re.compile(r"(\d+) (\S.*)")
HEADING_RE = re.compile(r"### `([^`]+)`")
CODE_ROW_RE = re.compile(r"\| (\d+) \| (.+) \|")
FILE_ROW_RE = re.compile(r"\| `([^`]+)` \| (.+) \|")
#: an exit number stated in prose: a standalone integer within the three words after any word that begins with
#: "exit" ("exit 2", "(exit 4", "exit code 1", "the exit is 0", "exits with 1", "exit stays 0", '"exit": 3'). A
#: window, not a list of phrasings: vibe-231 round 2 showed a list is never complete ("stays" was missing). A
#: version string ("0.144.6") is not a standalone integer.
MENTION_RE = re.compile(r"\b[Ee]xit\w*(?:\W+\w+){0,3}?\W+(?<![\w.])\d+(?!\w|\.\d)")
DOC_SLICE_RE = re.compile(r"__doc__(\.strip\(\))?\.splitlines\(\)\[(-?\d+)\]")
#: header lines allowed to state an exit number, by exact stripped text, each with its reason
HEADER_MENTION_ALLOW = {
    ("scripts/codex-runner.mjs",
     "// **Success is decided by the event stream, never the exit code.** codex-cli 0.144.6 exits 0 on an"):
        "describes codex-cli's exit status, not this program's",
    ("scripts/watch_pr.py",
     '`{"at": "<iso>", "author": "<login>", "author_association": "<assoc>", "exit": 3}` — so the chain can'):
        "the stdout line this program prints; its value is the activity code",
}


class RegistryError(ValueError):
    pass


def parse_registry(text):
    """docs/exit-codes.md -> ({path: {code: meaning}}, {path: reason}). Refuses a duplicate program,
    a program without rows, a duplicate code, a malformed row under a program, and an empty section."""
    programs_part, sep, rest = text.partition("\n## Programs\n")
    if not sep:
        raise RegistryError("no '## Programs' section")
    programs_text, sep, not_text = rest.partition("\n## Not a program\n")
    if not sep:
        raise RegistryError("no '## Not a program' section")
    programs, current = {}, None
    for line in programs_text.splitlines():
        heading = HEADING_RE.fullmatch(line)
        if heading:
            current = heading.group(1)
            if current in programs:
                raise RegistryError(f"{current}: listed twice")
            programs[current] = {}
            continue
        if current is None or not line.startswith("|") or line.startswith("| Code |") or line.startswith("| ---"):
            continue
        row = CODE_ROW_RE.fullmatch(line)
        if not row:
            raise RegistryError(f"{current}: malformed row {line!r}")
        code, meaning = int(row.group(1)), row.group(2)
        if code in programs[current]:
            raise RegistryError(f"{current}: code {code} listed twice")
        programs[current][code] = meaning
    for path, codes in programs.items():
        if not codes:
            raise RegistryError(f"{path}: no codes")
    others = {}
    for line in not_text.splitlines():
        if not line.startswith("| `"):
            continue
        row = FILE_ROW_RE.fullmatch(line)
        if not row:
            raise RegistryError(f"not-a-program: malformed row {line!r}")
        if row.group(1) in others:
            raise RegistryError(f"{row.group(1)}: listed twice as not a program")
        others[row.group(1)] = row.group(2)
    if not programs or not others:
        raise RegistryError("an empty section")
    return programs, others


def parse_marker(text):
    """A file's text -> {code: meaning} from its ONE marker line. Refuses none, two, or a malformed piece."""
    found = MARKER_RE.findall(text)
    if len(found) != 1:
        raise RegistryError(f"{len(found)} 'Exit codes:' marker lines (exactly one required)")
    codes = {}
    for piece in found[0].split(" · "):
        m = PIECE_RE.fullmatch(piece.strip())
        if not m:
            raise RegistryError(f"malformed marker piece {piece!r}")
        if int(m.group(1)) in codes:
            raise RegistryError(f"code {m.group(1)} twice in the marker")
        codes[int(m.group(1))] = m.group(2)
    return codes


def candidates(root):
    """Every file under bin/, and every .py/.mjs/.sh under scripts/ (bytecode caches excluded)."""
    root = Path(root)
    found = {p for p in (root / "bin").rglob("*") if p.is_file()}
    for suffix in (".py", ".mjs", ".sh"):
        found |= set((root / "scripts").rglob(f"*{suffix}"))
    return {p.relative_to(root).as_posix() for p in found if "__pycache__" not in p.parts}


def exit_constants(source):
    """{name: int} for every module-level `EXIT_*` assignment, including tuple unpacking."""
    out = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            pairs = []
            if isinstance(target, ast.Name):
                pairs = [(target, node.value)]
            elif isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
                pairs = list(zip(target.elts, node.value.elts))
            for name, value in pairs:
                if (isinstance(name, ast.Name) and name.id.startswith("EXIT_")
                        and isinstance(value, ast.Constant) and type(value.value) is int):
                    out[name.id] = value.value
    return out


def is_python(rel, text):
    return rel.endswith(".py") or text.startswith("#!/usr/bin/env python3")


def header_spans(text, python):
    """1-based inclusive line spans of a program's header: for Python, the module docstring plus the docstring that
    holds the marker; otherwise the leading comment block plus the comment block that holds the marker."""
    lines = text.splitlines()
    marker_lines = {i for i, line in enumerate(lines, 1) if MARKER_RE.fullmatch(line)}
    if python:
        tree = ast.parse(text)
        spans = []
        for node in [tree] + [n for n in ast.walk(tree)
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]:
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                span = (body[0].lineno, body[0].end_lineno)
                if node is tree or any(span[0] <= m <= span[1] for m in marker_lines):
                    spans.append(span)
        return spans
    prefix = "//" if lines and lines[0].startswith("#!/usr/bin/env node") else "#"
    blocks, start = [], None
    for i, line in enumerate(lines, 1):
        comment = line.lstrip().startswith(prefix) and not line.startswith("#!")
        if comment and start is None:
            start = i
        elif not comment and start is not None:
            blocks.append((start, i - 1))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))
    return blocks[:1] + [b for b in blocks[1:] if any(b[0] <= m <= b[1] for m in marker_lines)]


def header_mentions(text, python):
    """[(line number, stripped line)] of header lines, other than the marker, that state an exit number."""
    lines = text.splitlines()
    out = []
    for a, b in header_spans(text, python):
        for n in range(a, b + 1):
            if not MARKER_RE.fullmatch(lines[n - 1]) and MENTION_RE.search(lines[n - 1]):
                out.append((n, lines[n - 1].strip()))
    return out


def doc_slices(text):
    """[(expression, value)] for every `__doc__….splitlines()[i]` the program evaluates."""
    doc = ast.get_docstring(ast.parse(text), clean=False) or ""
    out = []
    for m in DOC_SLICE_RE.finditer(text):
        lines = (doc.strip() if m.group(1) else doc).splitlines()
        out.append((m.group(0), lines[int(m.group(2))]))
    return out


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.assertTrue(DOC.is_file(), "docs/exit-codes.md, the registry, is missing")
        self.programs, self.others = parse_registry(DOC.read_text(encoding="utf-8"))

    def text(self, rel):
        return (REPO_ROOT / rel).read_text(encoding="utf-8")

    def test_every_candidate_is_a_program_or_listed_as_not_one(self):
        found = candidates(REPO_ROOT)
        self.assertEqual(set(self.programs) & set(self.others), set(), "a file cannot be both")
        classified = set(self.programs) | set(self.others)
        self.assertEqual(sorted(found - classified), [],
                         "unclassified: add a table to docs/exit-codes.md, or list it under Not a program")
        self.assertEqual(sorted(classified - found), [], "the registry names files that do not exist")

    def test_both_hooks_are_programs(self):
        """Neither hook calls runMain; both set their exit inside callbacks, which is why candidates
        are enumerated by file kind and never by an entry-point pattern."""
        for hook in HOOKS:
            self.assertIn(hook, self.programs)

    def test_each_header_marker_equals_its_table(self):
        for rel, codes in self.programs.items():
            with self.subTest(program=rel):
                try:
                    marker = parse_marker(self.text(rel))
                except RegistryError as exc:
                    self.fail(f"{rel}: {exc}")
                self.assertEqual(marker, codes)

    def test_every_exit_constant_is_in_the_table(self):
        checked = 0
        for rel, codes in self.programs.items():
            text = self.text(rel)
            if not is_python(rel, text):
                continue
            for name, value in exit_constants(text).items():
                checked += 1
                with self.subTest(program=rel, constant=name):
                    self.assertIn(value, codes, f"{name} = {value} is not in {rel}'s table")
        self.assertGreater(checked, 0, "no EXIT_* constant was found: the scan is broken")

    def test_no_header_states_an_exit_number_outside_its_marker(self):
        """The marker is the one checked statement (frozen R2): prose beside it that restated a code could drift."""
        found = set()
        for rel in self.programs:
            text = self.text(rel)
            for n, line in header_mentions(text, is_python(rel, text)):
                found.add((rel, line))
                with self.subTest(program=rel, line=n):
                    self.assertIn((rel, line), HEADER_MENTION_ALLOW, f"{rel}:{n} states an exit number: {line}")
        self.assertEqual(sorted(set(HEADER_MENTION_ALLOW) - found), [], "stale HEADER_MENTION_ALLOW entries")

    def test_no_program_prints_or_describes_itself_with_its_marker(self):
        """A marker placed where a program slices its own docstring would replace its usage text or argparse
        description (validate_audit_output prints its docstring's last line as usage)."""
        sites = 0
        for rel in self.programs:
            text = self.text(rel)
            if not is_python(rel, text):
                continue
            for expr, value in doc_slices(text):
                sites += 1
                with self.subTest(program=rel, site=expr):
                    self.assertNotIn("Exit codes:", value)
        self.assertGreater(sites, 0, "no __doc__ slice was found: the scan is broken")

    def test_the_validator_still_prints_its_usage_line(self):
        result = subprocess.run([sys.executable, "-B", str(REPO_ROOT / "scripts" / "validate_audit_output.py")],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr.strip(),
                         "python3 scripts/validate_audit_output.py <report.json> [schema.json]")


class TestParsersRefuseMalformedInput(unittest.TestCase):
    DOC_OK = ("# x\n\n## Programs\n\n### `bin/a`\n\n| Code | Meaning |\n| --- | --- |\n| 0 | ok |\n| 2 | refused |\n"
              "\n## Not a program\n\n| File | Why it is not a program |\n| --- | --- |\n| `scripts/lib/x.py` | library |\n")

    def test_a_well_formed_page_parses(self):
        self.assertEqual(parse_registry(self.DOC_OK), ({"bin/a": {0: "ok", 2: "refused"}},
                                                       {"scripts/lib/x.py": "library"}))

    def test_the_registry_parser_refuses_each_malformation(self):
        cases = {
            "no programs section": (self.DOC_OK.replace("## Programs", "## Tools"), "no '## Programs'"),
            "no not-a-program section": (self.DOC_OK.replace("## Not a program", "## Other"), "no '## Not a program'"),
            "program twice": (self.DOC_OK.replace("\n## Not", "\n### `bin/a`\n\n| 0 | ok |\n\n## Not"), "listed twice"),
            "code twice": (self.DOC_OK.replace("| 2 | refused |", "| 0 | refused |"), "code 0 listed twice"),
            "malformed row": (self.DOC_OK.replace("| 2 | refused |", "| two | refused |"), "malformed row"),
            "program without rows": (self.DOC_OK.replace("\n## Not", "\n### `bin/b`\n\n## Not"), "bin/b: no codes"),
            "not-a-program twice": (self.DOC_OK + "| `scripts/lib/x.py` | again |\n", "listed twice as not a program"),
        }
        for label, (text, reason) in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(RegistryError, re.escape(reason)):
                    parse_registry(text)

    def test_the_marker_parser_reads_every_comment_syntax(self):
        for line in ("Exit codes: 0 ok · 2 refused", "# Exit codes: 0 ok · 2 refused",
                     "// Exit codes: 0 ok · 2 refused", "  Exit codes: 0 ok · 2 refused",
                     "#   Exit codes: 0 ok · 2 refused"):
            with self.subTest(line):
                self.assertEqual(parse_marker(f"head\n{line}\ntail\n"), {0: "ok", 2: "refused"})

    def test_the_marker_parser_refuses_each_malformation(self):
        cases = {
            "none": ("no marker here\n", "0 'Exit codes:' marker lines"),
            "two": ("Exit codes: 0 ok\n# Exit codes: 0 ok\n", "2 'Exit codes:' marker lines"),
            "prose, not a marker": ("See the Exit codes: 0 ok\n", "0 'Exit codes:' marker lines"),
            "malformed piece": ("Exit codes: 0 ok · two refused\n", "malformed marker piece"),
            "code twice": ("Exit codes: 0 ok · 0 again\n", "code 0 twice"),
        }
        for label, (text, reason) in cases.items():
            with self.subTest(label):
                with self.assertRaisesRegex(RegistryError, re.escape(reason)):
                    parse_marker(text)

    def test_a_meaning_mismatch_is_visible_to_the_comparison(self):
        self.assertNotEqual(parse_marker("Exit codes: 0 ok · 2 refused\n"), {0: "ok", 2: "refusal"})
        self.assertNotEqual(parse_marker("Exit codes: 0 ok\n"), {0: "ok", 2: "refused"})

    def test_candidates_cover_bin_and_three_kinds_under_scripts_at_any_depth(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("bin/tool", "bin/README.md", "scripts/a.py", "scripts/deep/er/b.sh", "scripts/c.mjs",
                        "scripts/notes.md", "scripts/lib/__pycache__/a.cpython-312.py", "tests/t.py"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("x\n", encoding="utf-8")
            self.assertEqual(candidates(root), {"bin/tool", "bin/README.md", "scripts/a.py",
                                                "scripts/deep/er/b.sh", "scripts/c.mjs"})

    def test_header_mentions_read_the_header_only_and_every_numeric_form(self):
        py = "\n".join([
            "#!/usr/bin/env python3", '"""Tool.', "",
            "Refuses (exit 2) on bad input.",           # 4
            "Exit codes: 0 ok · 2 refused",             # 5: the marker itself is skipped
            "It exits 0 when done.",                    # 6
            "Exit 3 is never used.",                    # 7
            "exit code 1 too.",                         # 8
            '{"exit": 4}',                              # 9
            "the exit is 0 here.",                      # 10
            "it exits with 1.",                         # 11
            "exit non-zero is fine.",                   # 12: no number
            "the error exit is fine.",                  # 13: no number
            "run.skipped, exit stays 0",                # 14: any verb inside the window
            "the exit, as documented in section 4",     # 15: the number is four words away
            "codex-cli 0.144.6 is a version",           # 16: no exit word; a version is not an integer
            "the exit of codex-cli 0.144.6",            # 17: a version inside the window is not an integer
            '"""', "def f():", '    """exit 2 here is not the header."""', "    return 2  # exit 2", ""])
        self.assertEqual([n for n, _ in header_mentions(py, True)], [4, 6, 7, 8, 9, 10, 11, 14])
        sh = ("#!/bin/bash\n# header: exits 1 on error\n# Exit codes: 0 ok · 1 error\nset -e\n"
              "# later comment: exit 1\nexit 1\n")
        self.assertEqual(header_mentions(sh, False), [(2, "# header: exits 1 on error")])
        mjs = ("#!/usr/bin/env node\n// top: exit 2 on usage\n\n/** not a // block */\nfunction f() {}\n"
               "// Exit codes: 0 ok · 2 usage\n// beside the marker: exits 0 always\n")
        self.assertEqual([n for n, _ in header_mentions(mjs, False)], [2, 7])

    def test_doc_slices_evaluate_the_programs_own_expression(self):
        text = ('"""First.\nSecond.\n\n    usage line\n"""\nA = __doc__.splitlines()[1]\n'
                'B = __doc__.strip().splitlines()[-1]\n')
        self.assertEqual(doc_slices(text), [("__doc__.splitlines()[1]", "Second."),
                                            ("__doc__.strip().splitlines()[-1]", "    usage line")])

    def test_exit_constants_are_read_from_names_and_tuples_only_at_module_level(self):
        source = ("EXIT_OK = 0\nEXIT_A, EXIT_B = 1, 2\nNOT_EXIT = 9\nEXIT_S = 'x'\nEXIT_T = True\n"
                  "def f():\n    EXIT_INNER = 7\n")
        self.assertEqual(exit_constants(source), {"EXIT_OK": 0, "EXIT_A": 1, "EXIT_B": 2})


if __name__ == "__main__":
    unittest.main()
