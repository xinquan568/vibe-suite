#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The one reader for `.vibe-suite.md` (E0.5 / vibe-7).

Every command in the suite reads project configuration through this module — as a Python API, or as
a `--json` CLI for shell callers. One reader, because a second parser in another language would be
two statements of one schema, and this repository has a documented history of what happens to a rule
stated twice.

**The grammar is a closed subset of YAML frontmatter**, documented in `vibe-core`'s schema section
and implemented below: scalars, flat scalar-only sequences, maps to three levels, and the two
block-scalar forms. Anything outside it raises `ConfigSyntaxError` rather than being half-parsed —
the same fail-closed posture as `scripts/validate_audit_output.py`, for the same reason: a parser
that silently tolerates what it does not understand accepts a file nobody has checked.

**Unknown keys are the one exception.** They warn and the load continues, because the file is
user-authored and a newer suite version will add keys an older reader has never seen. Everything
else — an invalid value, malformed syntax, a duplicate key, a path escaping the project — is fatal.
Treating "warn, never crash" as a general posture would turn a bad enum into a silent default.

**Diagnostics never echo a value.** An unrecognised key may be a typo whose value is a credential,
and so may a bad value under a *known* key; messages name the key and the expected domain.

**stdout belongs to the CLI's JSON.** The API returns warnings and never prints — a warning on
stdout would corrupt the document its caller is parsing.
"""

import json
import os
import re
import sys
from pathlib import Path

CONFIG_FILENAME = ".vibe-suite.md"
MAX_DEPTH = 3
_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9-]*")   # applied with fullmatch — `$` would admit "safe\n"
_INT = re.compile(r"-?[0-9]+$")


class ConfigSyntaxError(Exception):
    """The file is not in the accepted grammar."""


class ConfigValueError(Exception):
    """A known key carries a value outside its domain."""


class ConfigContainmentError(Exception):
    """A path-valued key resolves outside the project root."""


class Row:
    __slots__ = ("type", "domain", "default")

    def __init__(self, type_, domain, default):
        self.type, self.domain, self.default = type_, domain, default


SCHEMA = {
    "engine":                   Row("enum",   "claude|codex|agy|both", None),
    "cross_model_audit_engine": Row("enum",   "codex|agy",             "codex"),
    "reviewer_backend":         Row("enum",   "codex",                 "codex"),
    "reviewer_model":           Row("string", "open",                  None),
    "effort":                   Row("enum",   "low|medium|high",       "medium"),
    "sandbox":                  Row("enum",   "read-only|workspace-write|danger-full-access", "read-only"),
    "audit_depth":              Row("enum",   "mini|full",             None),
    "model_overrides":          Row("map",    "codex|agy",             {}),
    "skip_patterns":            Row("list",   "open",                  []),
    "focus_instructions":       Row("string", "open",                  ""),
    "project_instructions":     Row("string", "open",                  ""),
    "score_threshold":          Row("int",    "0-100",                 70),
    "rule_overrides":           Row("map",    "closed",                {}),
    "issue2pr_profile":         Row("string", "id",                    None),
    "gate":                     Row("map",    "closed",                None),
}

CLOSED_MAPS = {
    "rule_overrides": {"R51": {"enabled": "bool", "vocabulary_skill": "string"}},
    "gate": {"stop_review_gate": "bool", "model": "string", "fail_policy": "open|closed"},
}
OPEN_MAPS = {"model_overrides": ("codex", "agy")}
PATH_VALUED = {("rule_overrides", "R51", "vocabulary_skill")}


# ----------------------------------------------------------------------------- grammar


def _split_frontmatter(text, source):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ConfigSyntaxError(f"{source}: expected a leading '---' frontmatter marker")
    for index in range(1, len(lines)):
        # Only at document level. An indented `---` is block-scalar content; treating it as the
        # closing marker silently truncates the file and discards everything after it.
        if lines[index] == "---":
            return lines[1:index]
    raise ConfigSyntaxError(f"{source}: unterminated frontmatter — no closing '---'")


def _find_closing_quote(text, line_no, source):
    index = 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return index
        index += 1
    raise ConfigSyntaxError(f"{source}:{line_no}: unterminated double-quoted scalar")


def _unescape(text, line_no, source):
    out, index = [], 0
    while index < len(text):
        if text[index] != "\\":
            out.append(text[index]); index += 1; continue
        if index + 1 >= len(text):
            raise ConfigSyntaxError(f"{source}:{line_no}: trailing escape character")
        mapped = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}.get(text[index + 1])
        if mapped is None:
            raise ConfigSyntaxError(f"{source}:{line_no}: unsupported escape sequence")
        out.append(mapped); index += 2
    return "".join(out)


def _decode_scalar(raw, line_no, source):
    text = raw.strip()
    if text.startswith("'"):
        index, out = 1, []
        while index < len(text):
            if text[index] == "'":
                if text[index + 1:index + 2] == "'":
                    out.append("'"); index += 2; continue
                if index != len(text) - 1:
                    raise ConfigSyntaxError(
                        f"{source}:{line_no}: trailing text after a quoted scalar")
                return "".join(out)
            out.append(text[index]); index += 1
        raise ConfigSyntaxError(f"{source}:{line_no}: unterminated single-quoted scalar")
    if text.startswith('"'):
        closing = _find_closing_quote(text, line_no, source)
        if closing != len(text) - 1:
            raise ConfigSyntaxError(f"{source}:{line_no}: trailing text after a quoted scalar")
        return _unescape(text[1:closing], line_no, source)
    for marker, what in (("{", "flow mapping"), ("[", "flow sequence"), ("!", "tag"),
                         ("&", "anchor"), ("*", "alias"), ("<<", "merge key")):
        if text.startswith(marker):
            raise ConfigSyntaxError(f"{source}:{line_no}: {what} is outside the accepted grammar")
    if text in ("", "null"):
        return None
    if text in ("true", "false"):
        return text == "true"
    if _INT.match(text):
        return int(text)
    return text                      # plain scalar — `*`, `?`, `[` are ordinary characters here


def _indent_of(line, line_no, source):
    width = len(line) - len(line.lstrip(" "))
    if line[:width + 1].find("\t") >= 0:
        raise ConfigSyntaxError(f"{source}:{line_no}: tab in indentation — spaces only")
    if width % 2:
        raise ConfigSyntaxError(f"{source}:{line_no}: indentation must be two spaces per level")
    return width // 2


def _strip_comment(line):
    inside, index = None, 0
    while index < len(line):
        char = line[index]
        if inside:
            if char == "\\" and inside == '"':
                index += 2; continue
            if char == inside:
                inside = None
        elif char in "\"'":
            inside = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
        index += 1
    return line


def _block_scalar(lines, start, indent, style, chomp, source):
    body, index, blanks = [], start, 0
    while index < len(lines):
        line = lines[index]
        if line.strip() and _indent_of(line, index + 2, source) <= indent:
            break
        body.append(line[(indent + 1) * 2:] if line.strip() else "")
        index += 1
    while body and body[-1] == "":
        body.pop(); blanks += 1
    if style == ">":
        pieces, run = [], 0
        for piece in body:
            if piece == "":
                run += 1
                continue
            if pieces:
                pieces.append("\n" * run if run else " ")
            pieces.append(piece); run = 0
        text = "".join(pieces)
    else:
        text = "\n".join(body)
    if chomp == "-":
        return text, index
    if chomp == "+":
        return text + "\n" * max(1, blanks + 1), index
    return text + "\n", index


def _peek(lines, index):
    while index < len(lines):
        if lines[index].strip():
            return lines[index]
        index += 1
    return None


def _sequence(lines, start, indent, source):
    items, index = [], start
    while index < len(lines):
        raw = lines[index]
        if not raw.strip():
            index += 1; continue
        depth = _indent_of(raw, index + 2, source)
        if depth <= indent:
            break
        if depth != indent + 1:
            raise ConfigSyntaxError(f"{source}:{index + 2}: sequence item is over-indented")
        content = _strip_comment(raw).strip()
        if not content.startswith("- "):
            break
        item = content[2:].strip()
        if item.startswith("- "):
            raise ConfigSyntaxError(f"{source}:{index + 2}: nested sequence item")
        if ":" in item and item[:1] not in ("'", '"'):
            raise ConfigSyntaxError(f"{source}:{index + 2}: mapping inside a sequence")
        items.append(_decode_scalar(item, index + 2, source))
        index += 1
    return items, index


def parse_frontmatter(text, source=CONFIG_FILENAME):
    """Parse the accepted subset into nested dicts. Raises on anything outside it."""
    lines = _split_frontmatter(text, source)
    root = {}
    stack = [(0, root)]
    index = 0
    while index < len(lines):
        raw = lines[index]
        line_no = index + 2
        if not raw.strip() or not _strip_comment(raw).strip():
            index += 1; continue
        stripped = _strip_comment(raw)
        content = stripped.strip()
        if content == "..." or content.startswith("%") or content.startswith("? ") \
                or content.startswith("<<"):
            raise ConfigSyntaxError(f"{source}:{line_no}: construct outside the accepted grammar")
        depth = _indent_of(stripped, line_no, source)
        if depth + 1 > MAX_DEPTH:
            raise ConfigSyntaxError(f"{source}:{line_no}: nesting deeper than {MAX_DEPTH} levels")
        while len(stack) > 1 and stack[-1][0] > depth:
            stack.pop()
        if stack[-1][0] != depth:
            raise ConfigSyntaxError(f"{source}:{line_no}: unexpected indentation")
        container = stack[-1][1]
        if content.startswith("- "):
            raise ConfigSyntaxError(f"{source}:{line_no}: sequence item outside a key")
        if ":" not in content:
            raise ConfigSyntaxError(f"{source}:{line_no}: expected 'key: value'")
        key, _, rest = content.partition(":")
        key, rest = key.strip(), rest.strip()
        if not _KEY.match(key):
            raise ConfigSyntaxError(f"{source}:{line_no}: invalid key name")
        if key in container:
            raise ConfigSyntaxError(f"{source}:{line_no}: duplicate key {key!r}")
        if rest[:1] in ("|", ">"):
            if rest not in ("|", ">", "|-", "|+", ">-", ">+"):
                raise ConfigSyntaxError(
                    f"{source}:{line_no}: block header must be one of | > |- |+ >- >+")
            style, chomp = rest[0], rest[1:2]
            container[key], index = _block_scalar(lines, index + 1, depth, style, chomp, source)
            continue
        if rest == "":
            following = _peek(lines, index + 1)
            if following is not None and _strip_comment(following).strip().startswith("- "):
                container[key], index = _sequence(lines, index + 1, depth, source)
                continue
            if following is None or _indent_of(following, 0, source) <= depth:
                container[key] = None      # `key:` with no child is absent, per the schema
                index += 1
                continue
            child = {}
            container[key] = child
            stack.append((depth + 1, child))
            index += 1
            continue
        container[key] = _decode_scalar(rest, line_no, source)
        index += 1
    return root


# ----------------------------------------------------------------------------- validation


def _check_scalar(key, value, row):
    if row.type == "enum":
        if value not in row.domain.split("|"):
            raise ConfigValueError(f"{key}: expected one of {row.domain}")
    elif row.type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigValueError(f"{key}: expected an integer in {row.domain}")
        low, high = (int(part) for part in row.domain.split("-"))
        if not low <= value <= high:
            raise ConfigValueError(f"{key}: expected an integer in {row.domain}")
    elif row.type == "string":
        if not isinstance(value, str):
            raise ConfigValueError(f"{key}: expected a string")
        if row.domain == "id" and not _PROFILE_ID.fullmatch(value):
            raise ConfigValueError(f"{key}: expected an id matching [a-z0-9][a-z0-9-]*")
    elif row.type == "list":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ConfigValueError(f"{key}: expected a list of strings")


def _check_leaf(label, value, expected):
    if expected == "bool" and not isinstance(value, bool):
        raise ConfigValueError(f"{label}: expected true or false")
    if expected == "string" and not isinstance(value, str):
        raise ConfigValueError(f"{label}: expected a string")
    if "|" in expected and value not in expected.split("|"):
        raise ConfigValueError(f"{label}: expected one of {expected}")


def _check_map(key, value):
    if not isinstance(value, dict):
        raise ConfigValueError(f"{key}: expected a mapping")
    if key in OPEN_MAPS:
        for sub, sub_value in value.items():
            if sub not in OPEN_MAPS[key]:
                raise ConfigValueError(f"{key}.{sub}: expected one of {'|'.join(OPEN_MAPS[key])}")
            if not isinstance(sub_value, str):
                raise ConfigValueError(f"{key}.{sub}: expected a string")
        return
    allowed = CLOSED_MAPS[key]
    for sub, sub_value in value.items():
        if sub not in allowed:
            raise ConfigValueError(f"{key}.{sub}: not a known key of the closed map {key!r}")
        expected = allowed[sub]
        if isinstance(expected, dict):
            if not isinstance(sub_value, dict):
                raise ConfigValueError(f"{key}.{sub}: expected a mapping")
            for leaf, leaf_value in sub_value.items():
                if leaf not in expected:
                    raise ConfigValueError(f"{key}.{sub}.{leaf}: not a known key")
                _check_leaf(f"{key}.{sub}.{leaf}", leaf_value, expected[leaf])
        else:
            _check_leaf(f"{key}.{sub}", sub_value, expected)


def _assert_inside(real_root, candidate, label):
    resolved = Path(os.path.realpath(candidate))
    if resolved != real_root and real_root not in resolved.parents:
        raise ConfigContainmentError(f"{label}: resolves outside the project root")


def _check_containment(root, data):
    real_root = Path(os.path.realpath(root))
    for path_key in PATH_VALUED:
        node = data
        for part in path_key[:-1]:
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict):
            value = node.get(path_key[-1])
            if isinstance(value, str):
                _assert_inside(real_root, Path(real_root) / value, ".".join(path_key))
    profile = data.get("issue2pr_profile")
    if isinstance(profile, str):
        _assert_inside(real_root, Path(real_root) / "profiles" / f"{profile}.md",
                       "issue2pr_profile")


# ----------------------------------------------------------------------------- public API


def _normalise_domain(cell):
    ticked = re.findall(r"`([^`]+)`", cell)
    if ticked:
        return "|".join(ticked)
    return "open" if "open" in cell.lower() else cell.replace("**", "").strip()


def parse_schema_table(text):
    """Extract a `| key | type | domain | default |` table from a markdown document."""
    rows = {}
    for line in text.split("\n"):
        if not line.startswith("| `"):
            continue
        # Split on *unescaped* pipes: a domain cell writes alternatives as `a`\|`b`, and splitting
        # on every pipe would truncate the domain to its first alternative.
        cells = [cell.replace("\\|", "|").strip()
                 for cell in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 4:
            continue
        key = cells[0].strip("`")
        # Every cell is parsed from the document. Taking the default from SCHEMA would compare the
        # code against itself and pass however wrong the documentation was.
        rows[key] = (cells[1].replace("**", "").strip(),
                     _normalise_domain(cells[2]),
                     _normalise_default(cells[3]))
    return rows


def canonical_default(value):
    """Reduce a default — documented or coded — to one comparable token.

    Both sides of the schema comparison pass through here, so the test compares like with like
    rather than a prose cell against a Python object.
    """
    if isinstance(value, str) and value.strip().lower() in ("unset", "absent", "none"):
        return "unset"
    if value is None:
        return "unset"
    if value == {} or value == [] or value == "":
        return "empty"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value).strip().strip("`").strip()
    return "empty" if text.lower() == "empty" else text


def _normalise_default(cell):
    text = cell.replace("**", "").strip()
    # Documented cells may carry a clarifying clause; the value is the part before it.
    for separator in ("—", " until ", " -- "):
        if separator in text:
            text = text.split(separator)[0]
    return canonical_default(text.strip().strip("`").strip())


def _fresh(default):
    if isinstance(default, dict):
        return dict(default)
    if isinstance(default, list):
        return list(default)
    return default


def load_with_warnings(root="."):
    """Return `(config, warnings)`. Never writes to stdout."""
    warnings, data = [], {}
    path = Path(root) / CONFIG_FILENAME
    if path.exists():
        data = parse_frontmatter(path.read_text(encoding="utf-8"), CONFIG_FILENAME)
    resolved = {}
    for key, value in data.items():
        row = SCHEMA.get(key)
        if row is None:
            warnings.append(f"unknown key {key!r} in {CONFIG_FILENAME} — ignored")
            continue
        if value is None:
            continue                       # explicitly empty — the default applies
        if row.type == "map":
            _check_map(key, value)
        else:
            _check_scalar(key, value, row)
        resolved[key] = value
    _check_containment(root, resolved)
    for key, row in SCHEMA.items():
        resolved.setdefault(key, _fresh(row.default))
    return resolved, warnings


def load(root="."):
    """Return the resolved configuration, discarding warnings."""
    return load_with_warnings(root)[0]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    root = argv[-1] if argv and not argv[-1].startswith("-") else "."
    try:
        resolved, warnings = load_with_warnings(root)
    except (ConfigSyntaxError, ConfigValueError, ConfigContainmentError) as error:
        print(f"config: {error}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"config: {warning}", file=sys.stderr)
    print(json.dumps(resolved, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
