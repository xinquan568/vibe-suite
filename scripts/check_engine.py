#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Deterministic consistency engine for /vibe-suite:check.

The engine owns the mechanical classes and the composition; the checker agent owns the two
judgment classes and feeds them back via --judgment. Mechanical classes:

  reference-integrity, four reportable directions (F4.3):
    command-partial     a `(commands/)?shared/<name>.md` token in a command's body resolves
    agent-skills        an agent's frontmatter `skills:` entry (scalar or list form)
                        resolves to skills/<name>/SKILL.md
    hook-script         each ${CLAUDE_PLUGIN_ROOT}/ path in a parsed command-type hook's
                        command string resolves (quotes and arguments never leak in)
    claude-md-listing   a CLAUDE.md list item that is path-shaped resolves against the
                        root; a `plugin:component` token resolves to commands/<component>.md
  orphan                a non-root component (skill, agent, shared partial, script) with
                        zero inbound edges — per commands/shared/plugin-discover.md's map:
                        command→agent (path or whole-word name), command→partial,
                        agent→skill (frontmatter AND body path tokens), hook→script,
                        plus resolving CLAUDE.md listings. Command→agent and agent-body
                        skill references feed THIS computation only and are never a
                        reportable direction; manifest-claims are F4.4's, not checked here
  r51-drift             deprecated registry terms, only under the vocabulary skill's stated
                        preconditions: `.vibe-suite.md` (read fail-closed through
                        scripts/lib/config.py) has rule_overrides.R51.enabled true, not
                        suppressed, with a contained vocabulary_skill whose registry.yaml
                        exists. Verb terms flag only inside their scope's path globs;
                        noun-class terms are unscoped; deferred terms are never flagged.

Refusals (exit 2): bad root; fewer than two artifacts ("check: consistency needs >=2
artifacts; found <n>"); malformed or invalid config; a registry.yaml outside the documented
schema; a judgment file that is unreadable, unparsable, or carries an unknown class or a
malformed finding shape.

Output (stdout JSON, deterministic ordering, byte-identical across runs):
  {"verdict": "CLEAN" | "<N> issues", "issues": [...], "checked": {...}}
Composition: issues = mechanical + judgment (file order); CLEAN iff the composed list is
empty; N == len(issues) exactly.

The grammar's oracle is the hand-authored worksheet (tests/fixtures/check/broken/README.md);
the edge definitions come from commands/shared/plugin-discover.md, the R51 semantics from
skills/vocabulary/SKILL.md.
"""

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

import config   # noqa: E402  (scripts/lib — the one fail-closed .vibe-suite.md reader)

JUDGMENT_CLASSES = {"behavioral-contradiction", "terminology-drift"}
DIRECTION_ORDER = ["command-partial", "agent-skills", "hook-script", "claude-md-listing"]
CLASS_ORDER = {"reference-integrity": 0, "orphan": 1, "r51-drift": 2,
               "behavioral-contradiction": 3, "terminology-drift": 3}

PARTIAL_TOKEN = re.compile(r"(?<![A-Za-z0-9._/-])(?:commands/)?shared/[A-Za-z0-9._-]+\.md")
SKILL_TOKEN = re.compile(r"(?<![A-Za-z0-9._/-])skills/([A-Za-z0-9._-]+)")
HOOK_TARGET = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)")
PATH_SHAPED = re.compile(r".+/.+|.+\.(md|json|sh)$")
PLUGIN_TOKEN = re.compile(r"[a-z0-9-]+:([a-z0-9-]+)")
LIST_ITEM = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def fail(msg):
    print(f"check: {msg}", file=sys.stderr)
    return 2


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def body_of(text):
    """The document below its frontmatter block (the whole text when there is none)."""
    lines = text.split("\n")
    if lines and lines[0] == "---":
        for index in range(1, len(lines)):
            if lines[index] == "---":
                return "\n".join(lines[index + 1:])
    return text


def agent_skills(text):
    """Frontmatter `skills:` entries — comma-separated scalar or YAML list form."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return []
    names, in_skills = [], False
    for line in lines[1:]:
        if line == "---":
            break
        if in_skills:
            m = re.match(r"^\s+-\s+(\S+)\s*$", line)
            if m:
                names.append(m.group(1))
                continue
            in_skills = False
        m = re.match(r"^skills:\s*(.*)$", line)
        if m:
            value = m.group(1).strip()
            if value:
                names.extend(s.strip() for s in value.split(",") if s.strip())
            else:
                in_skills = True
    return names


def discover(root):
    """Inventory the artifact set (classify-consistent core rows)."""
    arts = {"command": [], "partial": [], "agent": [], "skill": [],
            "claude-md": [], "hook-config": [], "script": []}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or ".git" in p.parts or "node_modules" in p.parts:
            continue
        rel = p.relative_to(root).as_posix()
        if re.fullmatch(r"commands/shared/[^/]+\.md", rel):
            arts["partial"].append(rel)
        elif re.fullmatch(r"commands/[^/]+\.md", rel):
            arts["command"].append(rel)
        elif re.fullmatch(r"agents/[^/]+\.md", rel):
            arts["agent"].append(rel)
        elif re.fullmatch(r"skills/[^/]+/SKILL\.md", rel):
            arts["skill"].append(rel)
        elif rel == "CLAUDE.md" or rel.endswith("/CLAUDE.md"):
            arts["claude-md"].append(rel)
        elif rel == "hooks/hooks.json":
            arts["hook-config"].append(rel)
        elif re.fullmatch(r"scripts/[^/]+\.(sh|py|mjs)", rel):
            arts["script"].append(rel)
    return arts


def walk_hooks(node):
    """Every {"type": "command", "command": <str>} object in a parsed hooks.json."""
    if isinstance(node, dict):
        if node.get("type") == "command" and isinstance(node.get("command"), str):
            yield node["command"]
        for key in sorted(node):
            yield from walk_hooks(node[key])
    elif isinstance(node, list):
        for item in node:
            yield from walk_hooks(item)


def check_mechanical(root, arts, deprecated_terms):
    issues, edges = [], set()   # edges: target rels with at least one inbound reference
    seen = set()                # (direction, source, target) dedupe for reported issues

    def dangling(direction, source, target, detail):
        if (direction, source, target) not in seen:
            seen.add((direction, source, target))
            issues.append({"class": "reference-integrity", "direction": direction,
                           "source": source, "target": target, "detail": detail})

    agent_names = {rel: Path(rel).stem for rel in arts["agent"]}

    # command bodies: partial tokens (reportable) + agent references (orphan input only)
    for rel in arts["command"]:
        body = body_of(read_text(root / rel))
        for token in PARTIAL_TOKEN.findall(body):
            target = f"commands/shared/{Path(token).name}"
            if (root / target).is_file():
                edges.add(target)
            else:
                dangling("command-partial", rel, target,
                         "referenced shared partial does not exist")
        for agent_rel, name in agent_names.items():
            if agent_rel in body or re.search(rf"\b{re.escape(name)}\b", body):
                edges.add(agent_rel)

    # agents: frontmatter skills: (reportable) + body skill tokens (orphan input only)
    for rel in arts["agent"]:
        text = read_text(root / rel)
        for name in agent_skills(text):
            target = f"skills/{name}/SKILL.md"
            if (root / target).is_file():
                edges.add(target)
            else:
                dangling("agent-skills", rel, target,
                         "skills: entry resolves to no SKILL.md")
        for name in SKILL_TOKEN.findall(body_of(text)):
            target = f"skills/{name}/SKILL.md"
            if (root / target).is_file():
                edges.add(target)

    # hook commands, read out of the PARSED object (reportable)
    for rel in arts["hook-config"]:
        try:
            data = json.loads(read_text(root / rel))
        except ValueError:
            continue   # malformed hook config is F4.4/frontmatter territory, not ours
        for command in walk_hooks(data):
            for target in HOOK_TARGET.findall(command):
                if (root / target).is_file():
                    edges.add(target)
                else:
                    dangling("hook-script", rel, target,
                             "hook command names a script that does not exist")

    # CLAUDE.md listings: path-shaped items and plugin:component tokens (reportable)
    for rel in arts["claude-md"]:
        for line in read_text(root / rel).splitlines():
            m = LIST_ITEM.match(line)
            if not m:
                continue
            item = m.group(1).strip().strip("`")
            if PATH_SHAPED.fullmatch(item):
                if (root / item).exists():
                    edges.add(item)
                else:
                    dangling("claude-md-listing", rel, item,
                             "listed path does not resolve")
                continue
            token = PLUGIN_TOKEN.fullmatch(item)
            if token:
                target = f"commands/{token.group(1)}.md"
                if (root / target).is_file():
                    edges.add(target)
                else:
                    dangling("claude-md-listing", rel, item,
                             "listed plugin component token does not resolve")

    # orphans: non-root components with zero inbound edges
    for kind in ("skill", "agent", "partial", "script"):
        for rel in arts[kind]:
            if rel not in edges:
                issues.append({"class": "orphan", "source": rel,
                               "detail": "zero inbound reference edges"})

    # r51-drift: deprecated terms under scope, per the pre-validated registry table
    if deprecated_terms:
        scan = [r for k in ("command", "agent", "skill", "partial", "claude-md")
                for r in arts[k]]
        for rel in scan:
            lowered = read_text(root / rel).lower()
            for term, canonical, scope_paths in sorted(
                    deprecated_terms, key=lambda t: (t[0], t[1])):
                if scope_paths is not None and \
                        not any(fnmatch.fnmatch(rel, g) for g in scope_paths):
                    continue
                n = len(re.findall(rf"\b{re.escape(term)}\b", lowered))
                if n:
                    issues.append({"class": "r51-drift", "source": rel,
                                   "detail": f"deprecated term '{term}' (canonical: "
                                             f"'{canonical}'), {n} occurrence"
                                             + ("s" if n > 1 else "")})
    return issues


# ------------------------------------------------------------------ registry (R51 sidecar)


class RegistryError(Exception):
    """registry.yaml is outside the documented schema — a refusal, never a silent skip."""


_REG_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*$")
REGISTRY_KEYS = {"scopes", "cross_scope_homonyms", "verbs",
                 "deferred_pending_warrant", "rejected_by_higher_principle", "nouns"}


#: YAML's null/bool spelling family beyond the canonical lowercase forms decoded above —
#: including the YAML 1.1 single-letter boolean abbreviations y/Y/n/N.
_KEYWORD_LOOKALIKE = re.compile(r"(?i)(null|true|false|yes|no|on|off|y|n)")


def _reg_quoted(text, line_no, source):
    """Decode a quoted scalar syntax-aware: escapes honored, closure must be terminal."""
    if text[0] == '"':
        index, out = 1, []
        while index < len(text):
            char = text[index]
            if char == "\\":
                if index + 1 >= len(text):
                    raise RegistryError(f"{source}:{line_no}: trailing escape character")
                mapped = {"\\": "\\", '"': '"', "n": "\n", "t": "\t"}.get(text[index + 1])
                if mapped is None:
                    raise RegistryError(f"{source}:{line_no}: unsupported escape sequence")
                out.append(mapped)
                index += 2
                continue
            if char == '"':
                if index != len(text) - 1:
                    raise RegistryError(
                        f"{source}:{line_no}: trailing text after a quoted scalar")
                return "".join(out)
            out.append(char)
            index += 1
        raise RegistryError(f"{source}:{line_no}: unterminated quoted scalar")
    index, out = 1, []
    while index < len(text):
        if text[index] == "'":
            if text[index + 1:index + 2] == "'":
                out.append("'")
                index += 2
                continue
            if index != len(text) - 1:
                raise RegistryError(
                    f"{source}:{line_no}: trailing text after a quoted scalar")
            return "".join(out)
        out.append(text[index])
        index += 1
    raise RegistryError(f"{source}:{line_no}: unterminated quoted scalar")


def _reg_scalar(text, line_no, source):
    """Decode one scalar fail-closed. The canonical lowercase typed forms decode to their
    types (so a string-typed leaf refuses them by type); quoting is the one spelling for
    exotic strings; everything ambiguous — case-variant keywords, exponent/sign/dot/radix
    numeric forms, flow/tag/anchor/block constructs — refuses rather than passing as a
    silent string."""
    if text == "[]":
        return []
    if text in ("null", "~"):
        return None
    if text in ("true", "false"):
        return text == "true"
    if re.fullmatch(r"-?[0-9]+", text):
        return int(text)
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", text):
        return float(text)
    if text[:1] in ("\"", "'"):
        return _reg_quoted(text, line_no, source)
    if text[:1] in ("{", "[", "!", "&", "*", "|", ">", ",", "]", "}", "%", "@", "`") \
            or text.startswith("<<"):
        raise RegistryError(
            f"{source}:{line_no}: construct outside the accepted registry grammar")
    if text[:1] == "?" and (len(text) == 1 or text[1] in " \t"):
        # '?' + whitespace is YAML's complex-key indicator: the text is a mapping
        # ({key: null}), never a plain string. '?' followed by a non-space is a legal
        # plain scalar and passes through.
        raise RegistryError(f"{source}:{line_no}: complex-key indicator '?' is outside "
                            "the accepted registry grammar")
    if _KEYWORD_LOOKALIKE.fullmatch(text) or text[:1] in tuple("+-.0123456789") \
            or text == "=":
        # The '=' arm completes the YAML 1.1 special-resolution space: bare '=' is
        # tag:yaml.org,2002:value; every other non-string plain-scalar resolution is a
        # keyword variant, starts with a sign/digit/dot, or is indicator-led — all
        # refused above/below.
        raise RegistryError(f"{source}:{line_no}: ambiguous scalar {text!r}; "
                            "quote it if a string is meant")
    if re.search(r":(?=[ \t]|$)", text):
        # In YAML block context a plain scalar cannot contain ': ' or end with ':' —
        # that is mapping syntax. Refusing it HERE closes the class on every surface
        # (map values, list scalars, item-head values) at once.
        raise RegistryError(f"{source}:{line_no}: unquoted scalar {text!r} carries "
                            "mapping syntax; quote it if a string is meant")
    return text


def _reg_strip_comment(line):
    """Drop a YAML inline comment (whitespace-preceded `#` outside quotes) — a comment is
    never part of the value, so `y # note` must decode as `y`, not a longer string."""
    inside, index = None, 0
    while index < len(line):
        char = line[index]
        if inside:
            if char == "\\" and inside == '"':
                index += 2
                continue
            if char == inside:
                inside = None
        elif char in "\"'":
            inside = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
        index += 1
    return line


def _reg_key(key, line_no, source):
    """A mapping key under the same discipline as values: a quoted key decodes to an
    explicit string key; an unquoted key must be an identifier that is not a YAML keyword
    spelling — the key surface must not accept what the value surface refuses."""
    if key[:1] in ("\"", "'"):
        decoded = _reg_quoted(key, line_no, source)
        if not decoded:
            raise RegistryError(f"{source}:{line_no}: empty mapping key")
        return decoded
    if not _REG_KEY.match(key):
        raise RegistryError(f"{source}:{line_no}: expected 'key:' or 'key: value'")
    if _KEYWORD_LOOKALIKE.fullmatch(key):
        raise RegistryError(f"{source}:{line_no}: ambiguous mapping key {key!r}; "
                            "quote it if a string key is meant")
    return key


def _reg_quote_end(text, line_no, source):
    """Index of the terminating quote of a quoted scalar that starts `text`."""
    quote = text[0]
    index = 1
    while index < len(text):
        char = text[index]
        if quote == '"' and char == "\\":
            index += 2
            continue
        if char == quote:
            if quote == "'" and text[index + 1:index + 2] == "'":
                index += 2
                continue
            return index
        index += 1
    raise RegistryError(f"{source}:{line_no}: unterminated quoted scalar")


def _reg_item_head(rest, line_no, source):
    """(key, value_text) when a list item is a mapping head, (None, None) for a scalar.

    Any ':' followed by whitespace (or ending the item) is YAML mapping syntax and must be
    treated as a head — a tab-separated or phrase-keyed head is never a silent string. A
    quoted token followed by ':' is a quoted head key; a fully quoted item is a scalar;
    anything else after a quoted item is trailing junk. Colon-space STRING items take the
    quoted spelling.
    """
    if rest[:1] in ("\"", "'"):
        end = _reg_quote_end(rest, line_no, source)
        after = rest[end + 1:]
        if after == "":
            return None, None
        if after[:1] == ":" and (len(after) == 1 or after[1] in " \t"):
            return _reg_key(rest[:end + 1], line_no, source), after[2:].strip()
        raise RegistryError(f"{source}:{line_no}: trailing text after a quoted scalar")
    key, sep, value = rest.partition(":")
    if sep and (not value or value[0] in " \t"):
        return _reg_key(key.strip(), line_no, source), value.strip()
    return None, None


def _reg_block(lines, index, indent, source):
    """Parse a mapping or list block whose entries sit at exactly `indent` spaces."""
    entries_list, entries_map = None, None
    while index < len(lines):
        raw = _reg_strip_comment(lines[index])
        if not raw.strip():
            index += 1
            continue
        current = len(raw) - len(raw.lstrip(" "))
        if raw[current:current + 1] == "\t":
            raise RegistryError(f"{source}:{index + 1}: tab in indentation — spaces only")
        if current < indent:
            break
        if current > indent:
            raise RegistryError(f"{source}:{index + 1}: unexpected indentation")
        content = raw.strip()
        if content.startswith("- "):
            if entries_map is not None:
                raise RegistryError(f"{source}:{index + 1}: list item inside a mapping")
            entries_list = [] if entries_list is None else entries_list
            rest = content[2:].strip()
            head_key, head = _reg_item_head(rest, index + 1, source)
            if head_key is not None:
                item = {head_key:
                        _reg_scalar(head, index + 1, source) if head else None}
                sub, index = _reg_block(lines, index + 1, indent + 2, source)
                if isinstance(sub, dict):
                    for k, v in sub.items():
                        if k in item:
                            raise RegistryError(
                                f"{source}: duplicate key {k!r} in a list item")
                        item[k] = v
                elif sub is not None:
                    raise RegistryError(f"{source}: a list may not follow a list item head")
                entries_list.append(item)
            else:
                entries_list.append(_reg_scalar(rest, index + 1, source))
                index += 1
            continue
        if entries_list is not None:
            raise RegistryError(f"{source}:{index + 1}: mapping key inside a list")
        # The mapping separator is ':' followed by whitespace or line end — a colon
        # glued to the next character is plain-scalar content per YAML, and a map-level
        # line without a real separator is malformed, never a charitable {key: value}.
        separator = re.search(r":(?=[ \t]|$)", content)
        if not separator:
            raise RegistryError(f"{source}:{index + 1}: expected 'key:' or 'key: value'")
        key = _reg_key(content[:separator.start()].strip(), index + 1, source)
        value = content[separator.start() + 1:].strip()
        entries_map = {} if entries_map is None else entries_map
        if key in entries_map:
            raise RegistryError(f"{source}:{index + 1}: duplicate key {key!r}")
        if value:
            entries_map[key] = _reg_scalar(value, index + 1, source)
            index += 1
        else:
            entries_map[key], index = _reg_block(lines, index + 1, indent + 2, source)
    return entries_list if entries_list is not None else entries_map, index


def _reg_entry(entry, required, optional, label, source):
    """Shape-check one schema entry: exact keys, exact leaf types. Off-schema raises."""
    if not isinstance(entry, dict):
        raise RegistryError(f"{source}: {label} must be a mapping")
    unknown = set(entry) - set(required) - set(optional)
    if unknown:
        raise RegistryError(f"{source}: {label}: unknown key {sorted(unknown)[0]!r}")
    missing = set(required) - set(entry)
    if missing:
        raise RegistryError(f"{source}: {label}: missing key {sorted(missing)[0]!r}")
    for key, kind in {**required, **optional}.items():
        if key not in entry:
            continue
        value = entry[key]
        if kind == "str" and not isinstance(value, str):
            raise RegistryError(f"{source}: {label}.{key}: expected a string")
        if kind == "bool" and not isinstance(value, bool):
            raise RegistryError(f"{source}: {label}.{key}: expected true or false")
        if kind == "str-list" and (not isinstance(value, list)
                                   or any(not isinstance(item, str) for item in value)):
            raise RegistryError(f"{source}: {label}.{key}: expected a list of strings")


def _reg_list(value, label, source):
    if not isinstance(value, list):
        raise RegistryError(f"{source}: {label} must be a list")
    return value


def registry_terms(path):
    """[(deprecated_term, canonical, scope_paths|None)] per the documented six-key schema.

    All six top-level keys are required and every section is shape-checked — legitimate
    documented input parses, off-schema input refuses rather than half-parsing. Verb
    entries are scope-keyed lists and flag only inside their scope's path globs;
    noun-class entries are unscoped; deferred and rejected terms are never flagged (they
    are not synonyms); canonical terms are never flagged.
    """
    source = path.name
    tree, _ = _reg_block(read_text(path).split("\n"), 0, 0, source)
    if not isinstance(tree, dict):
        raise RegistryError(f"{source}: top level must be a mapping")
    unknown = set(tree) - REGISTRY_KEYS
    if unknown:
        raise RegistryError(f"{source}: unknown top-level key {sorted(unknown)[0]!r}")
    missing = REGISTRY_KEYS - set(tree)
    if missing:
        raise RegistryError(f"{source}: missing top-level key {sorted(missing)[0]!r}")

    scopes = {}
    for scope in _reg_list(tree["scopes"], "scopes", source):
        _reg_entry(scope, {"id": "str", "description": "str", "paths": "str-list"}, {},
                   "scopes entry", source)
        scopes[scope["id"]] = scope["paths"]

    _reg_entry(tree["cross_scope_homonyms"], {"verbs": "str-list"}, {},
               "cross_scope_homonyms", source)

    terms = []
    verbs = tree["verbs"]
    if not isinstance(verbs, dict):
        raise RegistryError(f"{source}: verbs must be a mapping keyed by scope id")
    for scope_id, entries in verbs.items():
        if scope_id not in scopes:
            raise RegistryError(f"{source}: verbs scope {scope_id!r} is not declared")
        for entry in _reg_list(entries, f"verbs.{scope_id}", source):
            _reg_entry(entry, {"canonical": "str", "deprecated": "str-list",
                               "output": "str", "judgment": "bool"},
                       {"notes": "str"}, f"verbs.{scope_id} entry", source)
            for term in entry["deprecated"]:
                terms.append((term, entry["canonical"], scopes[scope_id]))

    for entry in _reg_list(tree["deferred_pending_warrant"],
                           "deferred_pending_warrant", source):
        _reg_entry(entry, {"verb": "str", "proposed_for": "str",
                           "p2_p5_pass": "bool", "needed_warrant": "str"},
                   {"scope": "str"}, "deferred_pending_warrant entry", source)

    for entry in _reg_list(tree["rejected_by_higher_principle"],
                           "rejected_by_higher_principle", source):
        _reg_entry(entry, {"verb": "str", "scope": "str",
                           "blocker_principle": "str", "blocker": "str"}, {},
                   "rejected_by_higher_principle entry", source)

    nouns = tree["nouns"]
    if not isinstance(nouns, dict):
        raise RegistryError(f"{source}: nouns must be a mapping")
    noun_keys = {"artifact_class", "output_class", "role_nouns"}
    unknown = set(nouns) - noun_keys
    if unknown:
        raise RegistryError(f"{source}: nouns: unknown key {sorted(unknown)[0]!r}")
    missing = noun_keys - set(nouns)
    if missing:
        raise RegistryError(f"{source}: nouns: missing key {sorted(missing)[0]!r}")
    for klass in ("artifact_class", "output_class"):
        for entry in _reg_list(nouns[klass], f"nouns.{klass}", source):
            _reg_entry(entry, {"canonical": "str", "deprecated": "str-list",
                               "definition": "str"}, {}, f"nouns.{klass} entry", source)
            for term in entry["deprecated"]:
                terms.append((term, entry["canonical"], None))
    for entry in _reg_list(nouns["role_nouns"], "nouns.role_nouns", source):
        _reg_entry(entry, {"canonical": "str", "paired_verb": "str"}, {},
                   "role_nouns entry", source)
    return terms


def r51_deprecated_terms(root, resolved_config):
    """The term table when R51's preconditions hold (vocabulary skill), else []."""
    r51 = (resolved_config.get("rule_overrides") or {}).get("R51") or {}
    if r51.get("suppress") is True or r51.get("enabled") is not True:
        return []
    vocab = r51.get("vocabulary_skill")
    if not isinstance(vocab, str):
        return []
    registry = root / vocab / "registry.yaml"
    if not registry.is_file():
        return []
    return registry_terms(registry)


def load_config(root, config_arg):
    """Resolve the project config fail-closed through scripts/lib/config.py.

    No --config: the root's `.vibe-suite.md` (defaults when absent). --config <path>:
    that file's text validated against the root (defaults when the file is absent —
    the caller is pointing away from the root's config on purpose). Malformed or
    invalid config raises — the engine refuses rather than defaulting.
    """
    if config_arg:
        path = Path(config_arg)
        if not path.is_file():
            return config.resolve_text("---\n---\n", str(root))[0]
        return config.resolve_text(read_text(path), str(root))[0]
    return config.load_with_warnings(str(root))[0]


def sort_key(issue):
    return (CLASS_ORDER.get(issue["class"], 9),
            DIRECTION_ORDER.index(issue["direction"])
            if issue.get("direction") in DIRECTION_ORDER else 9,
            issue.get("source", ""), issue.get("target", ""), issue.get("detail", ""))


def load_judgment(path_arg):
    """(validated judgment list, None) or (None, error string) — errors are refusals."""
    path = Path(path_arg)
    if not path.is_file():
        return None, f"judgment file {path_arg!r} does not exist"
    try:
        judgment = json.loads(path.read_text(encoding="utf-8"))
    except OSError as err:
        return None, f"judgment file cannot be read: {err}"
    except ValueError as err:
        return None, f"judgment file does not parse: {err}"
    if not isinstance(judgment, list):
        return None, "judgment file must be a JSON list"
    for finding in judgment:
        if not isinstance(finding, dict):
            return None, "judgment entries must be objects"
        if finding.get("class") not in JUDGMENT_CLASSES:
            return None, f"unknown judgment class {finding.get('class')!r}"
        if not isinstance(finding.get("detail"), str) or not finding["detail"]:
            return None, "judgment entries need a non-empty string detail"
        sources = finding.get("sources")
        if not isinstance(sources, list) or \
                any(not isinstance(item, str) for item in sources):
            return None, "judgment entries need a sources list of strings"
    return judgment, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True)
    parser.add_argument("--config")
    parser.add_argument("--judgment")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        return fail(f"root {args.root!r} is not a directory")

    arts = discover(root)
    count = sum(len(v) for v in arts.values())
    if count < 2:
        return fail(f"consistency needs >=2 artifacts; found {count}")

    try:
        resolved_config = load_config(root, args.config)
        deprecated_terms = r51_deprecated_terms(root, resolved_config)
    except (config.ConfigSyntaxError, config.ConfigValueError,
            config.ConfigContainmentError) as err:
        return fail(f"config: {err}")
    except RegistryError as err:
        return fail(f"registry: {err}")

    issues = check_mechanical(root, arts, deprecated_terms)
    issues.sort(key=sort_key)

    if args.judgment:
        judgment, error = load_judgment(args.judgment)
        if error:
            return fail(error)
        issues.extend(judgment)   # file order, after the mechanical block

    verdict = "CLEAN" if not issues else f"{len(issues)} issues"
    json.dump({"verdict": verdict, "issues": issues,
               "checked": {k: len(v) for k, v in sorted(arts.items())}},
              sys.stdout, indent=2, sort_keys=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
