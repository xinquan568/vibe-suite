#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Deterministic scoring engine for /vibe-suite:score (E3.3 / vibe-28).

The engine is the ONLY penalty authority; agents narrate its output. The hand-computed oracle
(tests/fixtures/nl-audit/defective-skill/expected.json + its README worksheet) pins the semantics:
the engine deducts ONLY on the rows the row ledger (scripts/score_engine_rows.md) classifies
`mechanical`, and reports every `advisory-zero` row of the scored type as an advisory with zero
penalty. Both the command at runtime and tests/test_score_goldens.py invoke THIS file, so the
penalty arithmetic exists exactly once.

CLI contract (pinned by tests/test_score_goldens.py):
  stdin  : records `<type-or-category>\\x1f<relative-path>\\x00` — the same lossless framing as
           ls_counts, whose parser and path resolution are imported rather than restated. The
           first field is either an artifact type (`skill`, `agent`, …) or a scanner discovery
           category letter `A`–`F`; given a category, the engine classifies the path itself with
           the same first-match rules as commands/shared/classify.md.
  args   : --root <dir> [--config <file>] [--history <file>] [--scope <tag>] [--run-id <tag>]
  stdout : JSON {"files":[{"path","tier","score","band","verdict",
           "findings":[{"rule","check","line","penalty"}],"advisories":[{"rule","note"}]}],
           "run":{"files","total_penalty","considered_rows","skipped"}}
  exit   : 0 scored; 1 history append failed; 2 contract refusal (bad record, bad root,
           a path that is absolute, escapes the root, or does not exist, or a config file
           that exists but cannot be parsed). A missing --config file is NOT a refusal:
           the engine scores with the suite defaults.

Scoring semantics (owning text: skills/scoring/SKILL.md; row classifications with their quoted
predicates: scripts/score_engine_rows.md):
  formula     : final = max(0, min(100, 100 + sum(penalties)))
  verdict     : pass/fail against the config `score_threshold` (default 70); bands stay fixed
  tier        : each files[] entry carries the artifact's tool tier, classified per file from
                its canonical path (the scoring skill's tier classifier + the conventions
                overlay table): `2-Claude` / `2-Codex` / `2-Antigravity` under a tool tree,
                else `1` (open-spec artifact; the Tier 1.5 open-spec-corpus distinction is a
                property of a collection, not decidable from one file's path, so per-file
                output never states it — instead every tier-`1` entry carries a zero-penalty
                tier-boundary advisory naming the 1.5 possibility, so the boundary is
                explicit rather than silent). Tool-specific rows are tier-conditioned: a row
                bound to one tool's tier never fires on another tier's artifacts.
  description : counted in CHARACTERS of the description value — 500-800 -> -5, over 800 -> -10
  body (R05)  : counted in lines of the MARKDOWN BODY — the frontmatter block (both `---`
                fences included) is excluded — 400..upper -> -5, over upper -> -10, where the
                upper boundary is 500 or the R05 `threshold` override; the 400 lower stays
  R01         : token-bounded occurrences of the 11 listed words, -2 each, capped at -20, minus
                the three carve-outs of skills/conventions/SKILL.md §4 (heading `relevant`,
                `relevant to <named-scope>`, term followed by a measurable-criterion clause —
                the owning text names no example form for that clause, so it is encoded as a
                quantity in the remainder of the term's own sentence on its line: a digit, or
                a spelled-out cardinal from the closed _NUMBER_WORDS list). A counted term is
                by definition one no carve-out form followed; because the clause wording is
                open-ended, every file with a kept R01 finding also carries one borderline
                advisory pointing at rule_overrides.R01 — the rubric's own escape hatch
  degenerate  : unparseable frontmatter/config -> one -25 parse finding, and every row that
                does not need the parsed structure is still scored; empty (0-byte) file ->
                score 0, band Rewrite; unreadable file -> absent from files[], listed in
                run.skipped, exit stays 0

Artifact frontmatter is parsed by the permissive stdlib parser below — every schema-conforming
SKILL.md/agent/command frontmatter parses (nested block mappings such as `metadata:`,
sequences, flow mappings `{a: b}` including multiline flow collections bracket-matched across
lines, hyphenated keys, quoted scalars, block scalars); the -25 `frontmatter parse` finding
fires ONLY on a true structural failure: no closing `---` fence, a non-mapping top level,
unbalanced quotes or brackets, tab-broken indentation, or trailing text after a closed flow
collection (`key: {a: b} garbage` has no reading under the schema space).

Config is read through scripts/lib/config.py — the one reader; no second parser:
  rule_overrides.<Rid>.suppress / enabled: false -> rule zeroed, findings moved to advisories
  rule_overrides.<Rid>.max_penalty               -> the rule's summed penalty floors at -abs(value)
  rule_overrides.<Rid>.threshold                 -> numeric trigger: R01 the cap, R05/R23 the
                                                    upper line boundary
  score_threshold                                -> the pass/fail verdict boundary

History (--history H --scope S [--run-id R]): one {"scope","score","band","total_penalty","file"}
(plus "run" when R is given; dedup is then per-run rather than global) entry per
scored file; an entry identical to an existing one is not appended (same-scope dedupe — a distinct
scope produces a distinct entry and appends). The write goes through bridge.write_atomic: a temp
file created IN the destination directory, then an atomic rename — so a failed append leaves the
history byte-identical, leaves no temp residue, and exits non-zero.

Determinism: no timestamps, fixed evaluation order, json.dump(sort_keys=True) — byte-identical
output across runs on identical input.
"""

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

import bridge                  # noqa: E402
import config as config_mod    # noqa: E402
import ls_counts               # noqa: E402

#: R01's word list, verbatim from the scoring skill's "All types: vague quantifiers" row.
VAGUE_WORDS = (
    "appropriate", "relevant", "as needed", "sufficient", "adequate", "reasonable",
    "properly", "correctly", "some", "several", "various",
)
#: Token-bounded: `somewhere` never counts as `some`. Longest-first keeps phrases intact.
_VAGUE = re.compile(
    r"\b(?:" + "|".join(re.escape(word) for word in sorted(VAGUE_WORDS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE)
_HEADING = re.compile(r"#{1,6}\s")
_SENTENCE_END = re.compile(r"[.!?]")
#: The quantity lexemes of the measurable-criterion carve-out (conventions §4: "any listed
#: term followed by a measurable-criterion clause"). The owning text supplies no finer
#: definition, so the mechanical encoding is a closed one: a digit, or one of these
#: spelled-out cardinals ("appropriate timeout of one minute", "at most three retries").
_NUMBER_WORDS = frozenset((
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
))

#: Confirmed Claude hook events and hook types, verbatim from the scoring skill's
#: "Hooks (Claude Code, Tier 2-Claude)" table conditions.
CLAUDE_HOOK_EVENTS = (
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "PermissionRequest", "Stop", "StopFailure", "FileChanged",
)
CLAUDE_HOOK_TYPES = ("command", "http", "mcp_tool", "prompt", "agent")
#: Confirmed Codex hook events, verbatim from the scoring skill's
#: "Hooks (Codex CLI, Tier 2-Codex)" table condition.
CODEX_HOOK_EVENTS = (
    "SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest",
    "PreCompact", "PostCompact", "SubagentStart", "SubagentStop", "Stop",
)
#: Per-tool hook event tables, keyed by the tier whose artifacts they bind to. The
#: Antigravity table is deliberately absent: its owning text holds every Antigravity hook
#: finding advisory (confidence: low), so the engine never deducts on it.
HOOK_EVENTS_BY_TIER = {"2-Claude": CLAUDE_HOOK_EVENTS, "2-Codex": CODEX_HOOK_EVENTS}
#: Dangerous patterns, verbatim from the universal hooks table's command-safety condition.
DANGEROUS_PATTERNS = ("rm -rf", "git push --force", "DROP TABLE")
#: semver.org shape for the manifest's `version is semver` row.
_SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")
_MEMORY_TYPES = ("user", "feedback", "project", "reference")

BANDS = ((90, "Excellent"), (80, "Good"), (70, "Adequate"), (60, "Weak"))

#: advisory-zero ledger rows per artifact type, emitted unconditionally for every scored file
#: of that type. The rows have no objective predicate the engine can evaluate from the file's
#: own bytes and path (scripts/score_engine_rows.md quotes each justification), so their
#: presence cannot be decided mechanically either way — the engine reports the class and
#: deducts nothing; judgment about it belongs to the narrating agent.
TYPE_ADVISORIES = {
    "skill": (
        ("R04", "trigger quality"),
        ("R06", "code examples (complex concepts but no examples)"),
        ("R06", "code examples (no examples at all in a technical skill)"),
        ("R07", "scope note"),
        ("--", "broken references link"),
        ("--", "pseudocode example"),
        ("--", "domain mixing"),
        ("--", "redundant content"),
        ("--", "orphaned registration"),
    ),
    "agent": (
        ("R10", "model appropriate"),
        ("R11", "unused tools"),
        ("R11", "write on read-only"),
    ),
    "command": (
        ("R18", "argument-hint present"),
        ("R14", "steps numbered"),
        ("R15", "empty input handling"),
        ("R16", "output format"),
        ("R17", "error paths"),
    ),
    "shared-partial": (
        ("R20", "purpose clear"),
    ),
    "rule": (
        ("R21", "bold imperative"),
        ("R21", "rationale"),
        ("R22", "enforceability"),
        ("R26", "conflicts"),
        ("R24", "duplicates tooling"),
    ),
    "hook-config": (
        ("R29", "scripts exist"),
    ),
    "settings": (
        ("--", "no hardcoded secrets"),
        ("--", "permission mode sanity"),
        ("--", "recognized keys"),
    ),
    "claude-md": (
        ("R49", "file exists"),
        ("R38", "actionable content"),
        ("R33", "build/run command"),
        ("R34", "test command"),
        ("R35", "architecture overview"),
        ("R37", "no stale file refs"),
        ("R38", "actionability ratio"),
        ("--", "prerequisites section"),
        ("R39", "no rule conflicts"),
    ),
    "memory": (
        ("--", "content matches declared type"),
        ("--", "referenced in MEMORY.md index"),
        ("R37", "no stale content (refs to removed files/functions)"),
    ),
}
TYPE_ADVISORIES["user-command"] = TYPE_ADVISORIES["command"]

#: Tier-conditioned advisory-zero rows: rows of a per-tool table that bind only to that
#: tool's tier and stay advisory there by the owning text. Each value is (rule, full note).
TIER_ADVISORIES = {
    ("hook-config", "2-Claude"): (
        ("--", "advisory-zero: MCP matcher format; no objective predicate for the engine"),
    ),
    ("hook-config", "2-Codex"): (
        ("--", "advisory-zero: hooks config key (deprecated [features].codex_hooks); "
               "the owning text marks the row (advisory)"),
    ),
    ("hook-config", "2-Antigravity"): (
        ("R27", "advisory-zero: event names valid; the owning text holds every Antigravity "
                "hook finding advisory (confidence: low)"),
        ("R27", "advisory-zero: case correct; the owning text holds every Antigravity "
                "hook finding advisory (confidence: low)"),
    ),
}

#: Penalty-table rows one evaluation of the type consults (the type's own tables); every
#: evaluation additionally consults the two all-types R01 rows. hook-config is absent here:
#: its per-tool table is tier-conditioned, so `type_rows` computes it.
TYPE_TABLE_ROWS = {
    "skill": 12, "agent": 9, "command": 6, "user-command": 6, "shared-partial": 2,
    "rule": 7, "manifest": 3, "mcp-config": 2, "lsp-config": 1,
    "settings": 5, "claude-md": 11, "memory": 7,
}
#: The universal hooks table plus the per-tool hook table the artifact's tier binds to.
HOOK_TABLE_ROWS = {"2-Claude": 4, "2-Codex": 3, "2-Antigravity": 2}
GENERIC_ROWS = 2


def type_rows(artifact_type, tier):
    """Table rows one evaluation consults for a file of this type and tier (R01 excluded)."""
    if artifact_type == "hook-config":
        return 5 + HOOK_TABLE_ROWS.get(tier, 0)
    return TYPE_TABLE_ROWS.get(artifact_type, 0)


# ------------------------------------------------------------------- path classification

def _glob(path, pattern):
    """Match a POSIX-relative path against a `**`-aware glob (classify.md's grammar)."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?"); i += 3
        elif pattern.startswith("**", i):
            out.append(".*"); i += 2
        elif pattern[i] == "*":
            out.append("[^/]*"); i += 1
        elif pattern[i] == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(pattern[i])); i += 1
    return re.fullmatch("".join(out), path) is not None


def classify_path(rel):
    """Deterministic path -> artifact type, first match wins.

    The rules restate commands/shared/classify.md rows 1-23 for a scan-root-relative POSIX
    path (rows 13/14 collapse: both map CLAUDE.md to `claude-md`); the golden suite asserts
    agreement against the rules parsed out of that partial, so the two cannot drift apart
    silently. Paths here are already root-relative — ls_counts.resolve refused absolute ones.
    """
    p = rel[2:] if rel.startswith("./") else rel
    name = p.rsplit("/", 1)[-1]
    parts = p.split("/")
    parent = parts[-2] if len(parts) >= 2 else ""

    def g(*patterns):
        return any(_glob(p, pattern) for pattern in patterns)

    if g("commands/shared/**/*.md"):
        return "shared-partial"
    if g(".claude/commands/**/*.md"):
        return "user-command"
    if g("commands/**/*.md"):
        return "command"
    if g("agents/**/*.md"):
        return "agent"
    if name == "SKILL.md":
        return "skill"
    if g(".claude/rules/**/*.md"):
        return "rule"
    if g("hooks/**/*.json"):
        return "hook-config"
    if name == "plugin.json" and parent == ".claude-plugin":
        return "manifest"
    if name == "marketplace.json" and parent == ".claude-plugin":
        return "marketplace"
    if name == ".mcp.json":
        return "mcp-config"
    if name == ".lsp.json":
        return "lsp-config"
    if "/memory/" in p and g("**/*.md"):
        return "memory"
    if name == "CLAUDE.md":
        return "claude-md"
    if g(".claude/**/*.local.md"):
        return "plugin-config"
    if g(".claude/settings*.json"):
        return "settings"
    if g("prompts/**/*.md", "**/system-prompt*.md", "**/*-prompt.md", "**/*_prompt.md"):
        return "prompt"
    if g("**/agents/*.md", "**/agents/*.yaml"):
        return "framework-agent"
    if g("**/skills/*.md", "**/skills/**/*.md") and not p.startswith("skills/"):
        return "framework-skill"
    if g("**/manifest.yaml", "**/manifest.json"):
        return "framework-manifest"
    if g("**/frameworks/**/*.md"):
        return "framework-config"
    if g("docs/**/*.md", "dev-docs/**/*.md", "specs/**/*.md", "design/**/*.md",
         "plans/**/*.md", "decisions/**/*.md") or p in ("README.md", "CONTRIBUTING.md"):
        return "design-doc"
    return "document"


def classify_tier(rel):
    """Deterministic tool tier from the artifact's canonical path — first match wins.

    Owning texts: the scoring skill's tier classifier ("**Tier 1** — open-spec artifacts.
    **Tier 1.5** — open-spec corpora. **Tier 2** — overlays specific to each tool: 2-Claude,
    2-Codex, 2-Antigravity.") and the conventions overlay table ("classify its target tool
    from the canonical path it lives under"): conventions-claude governs `.claude/` and
    `plugin.json`; conventions-codex governs `.codex/`, `.agents/`, `AGENTS.md`;
    conventions-antigravity governs `.gemini/`, `.agent/`. The per-file markers beyond the
    trees come from the scoring skill's own table headings (`.mcp.json`/`.lsp.json`/
    `monitors/monitors.json` Claude; `agents/openai.yaml`/`.codex-plugin` 2-Codex;
    `gemini-extension.json` 2-Antigravity; `hooks/**/*.json` is the Claude plugin hooks
    config the Tier 2-Claude hook table binds to). Everything else is `1` — an open-spec
    artifact. Tier 1.5 ("open-spec corpora", the scoring skill's whole definition) is a
    property of a collection: a lone file shows the definition's "open-spec" marker but
    its "corpora" marker is collection-level, so no per-file predicate exists and this
    classifier never emits `1.5`; score_text surfaces the possibility as a zero-penalty
    tier-boundary advisory on every tier-`1` file instead.
    """
    p = rel[2:] if rel.startswith("./") else rel
    parts = p.split("/")
    name = parts[-1]
    dirs = parts[:-1]
    if ".claude" in dirs or ".claude-plugin" in dirs:
        return "2-Claude"
    if ".codex" in dirs or ".codex-plugin" in dirs or ".agents" in dirs:
        return "2-Codex"
    if ".gemini" in dirs or ".agent" in dirs:
        return "2-Antigravity"
    if name in ("CLAUDE.md", ".mcp.json", ".lsp.json") or p == "monitors/monitors.json" \
            or _glob(p, "hooks/**/*.json"):
        return "2-Claude"
    if name == "AGENTS.md" or (name == "openai.yaml" and dirs and dirs[-1] == "agents"):
        return "2-Codex"
    if name == "gemini-extension.json":
        return "2-Antigravity"
    return "1"


_CATEGORY = re.compile(r"[A-F]")


def resolve_type(field, rel):
    """A record's first field is a scanner category letter or an explicit artifact type."""
    if _CATEGORY.fullmatch(field):
        return classify_path(rel)
    return field


# ------------------------------------------------------------------------------- helpers

def band(score):
    for floor, name in BANDS:
        if score >= floor:
            return name
    return "Rewrite"


class Controls:
    """Effective per-rule knobs from `rule_overrides` (already validated by the config reader)."""

    def __init__(self, overrides, rule):
        row = overrides.get(rule) or {}
        self.suppressed = bool(row.get("suppress")) or row.get("enabled") is False
        self.max_penalty = row.get("max_penalty")
        self.threshold = row.get("threshold")


# ----------------------------------------------------- permissive artifact frontmatter parser
# `.vibe-suite.md` keeps the strict fail-closed config grammar (scripts/lib/config.py, the one
# reader). Artifact frontmatter is a different domain: its schema is the open SKILL.md spec,
# whose files the engine must SCORE rather than refuse, so the parser here is permissive —
# every schema-conforming shape parses (nested block mappings such as `metadata:`, sequences,
# flow mappings `{a: b}` — bracket-matched across lines when a flow collection spans them —
# hyphenated keys, quoted scalars, block scalars) and _FrontmatterError is raised ONLY on true
# structural failure: a non-mapping top level, unbalanced quotes or brackets, tab-broken
# indentation, or trailing text after a closed flow collection (the missing closing fence is
# caught before parsing).


class _FrontmatterError(Exception):
    """True structural failure of an artifact frontmatter block."""


_BLOCK_HEADER = re.compile(r"[|>][+-]?\d*")
_PLAIN_INT = re.compile(r"-?\d+")
_BARE_KEY = re.compile(r"([A-Za-z0-9_.-]+):(\S.*)")


def _fm_strip_comment(line):
    """Drop a ` #` comment that sits outside quotes and outside flow brackets."""
    inside, depth, index = None, 0, 0
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
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        elif char == "#" and depth == 0 and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
        index += 1
    return line


def _fm_scalar_convert(text):
    if text in ("", "null", "~"):
        return None
    if text in ("true", "True", "false", "False"):
        return text.lower() == "true"
    if _PLAIN_INT.fullmatch(text):
        return int(text)
    return text


def _fm_quoted(text, index, line_no):
    """Parse the quoted scalar opening at text[index]; returns (value, end)."""
    quote = text[index]
    index += 1
    out = []
    while index < len(text):
        char = text[index]
        if quote == '"' and char == "\\":
            if index + 1 >= len(text):
                break
            out.append(text[index + 1])
            index += 2
            continue
        if char == quote:
            if quote == "'" and text[index + 1:index + 2] == "'":
                out.append("'")
                index += 2
                continue
            return "".join(out), index + 1
        out.append(char)
        index += 1
    raise _FrontmatterError(f"line {line_no}: unterminated quoted scalar")


def _fm_flow_value(text, index, line_no):
    while index < len(text) and text[index] == " ":
        index += 1
    if index >= len(text):
        return None, index
    char = text[index]
    if char == "{":
        return _fm_flow_map(text, index + 1, line_no)
    if char == "[":
        return _fm_flow_seq(text, index + 1, line_no)
    if char in "\"'":
        return _fm_quoted(text, index, line_no)
    end = index
    while end < len(text) and text[end] not in ",}]":
        end += 1
    return _fm_scalar_convert(text[index:end].strip()), end


def _fm_flow_map(text, index, line_no):
    out = {}
    while True:
        while index < len(text) and text[index] in " ,":
            index += 1
        if index >= len(text):
            raise _FrontmatterError(f"line {line_no}: unterminated flow mapping")
        if text[index] == "}":
            return out, index + 1
        if text[index] == "]":
            raise _FrontmatterError(f"line {line_no}: mismatched bracket in flow mapping")
        if text[index] in "\"'":
            key, index = _fm_quoted(text, index, line_no)
        else:
            end = index
            while end < len(text) and text[end] not in ":,}]":
                end += 1
            key, index = text[index:end].strip(), end
        while index < len(text) and text[index] == " ":
            index += 1
        if index < len(text) and text[index] == ":":
            value, index = _fm_flow_value(text, index + 1, line_no)
        else:
            value = None
        out[str(key)] = value


def _fm_flow_seq(text, index, line_no):
    out = []
    while True:
        while index < len(text) and text[index] in " ,":
            index += 1
        if index >= len(text):
            raise _FrontmatterError(f"line {line_no}: unterminated flow sequence")
        if text[index] == "]":
            return out, index + 1
        if text[index] == "}":
            raise _FrontmatterError(f"line {line_no}: mismatched bracket in flow sequence")
        value, index = _fm_flow_value(text, index, line_no)
        out.append(value)


def _flow_depth(text):
    """Net `{}`/`[]` bracket depth outside quotes — the primitive behind both the
    multiline flow join (depth > 0: the collection continues on later lines) and
    nothing else; escapes inside double quotes are honored."""
    depth, inside, index = 0, None, 0
    while index < len(text):
        char = text[index]
        if inside:
            if char == "\\" and inside == '"':
                index += 2
                continue
            if char == inside:
                inside = None
        elif char in "\"'":
            inside = char
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        index += 1
    return depth


def _fm_value(rest, line_no):
    """One already-stripped inline value. Trailing text after a closed QUOTED scalar or a
    closed FLOW COLLECTION is a structural failure — `name: "probe" garbage` and
    `key: {a: b} garbage` have no reading under the schema space. An unterminated quote
    or flow raises."""
    char = rest[0]
    if char in "{[":
        if char == "{":
            value, end = _fm_flow_map(rest, 1, line_no)
        else:
            value, end = _fm_flow_seq(rest, 1, line_no)
        if rest[end:].strip():
            raise _FrontmatterError(
                f"line {line_no}: trailing text after a closed flow collection")
        return value
    if char in "\"'":
        value, end = _fm_quoted(rest, 0, line_no)
        if rest[end:].strip():
            raise _FrontmatterError(
                f"line {line_no}: trailing text after a closed quoted scalar")
        return value
    return _fm_scalar_convert(rest)


#: A line whose VALUE position syntactically begins a quoted scalar — the only context in
#: which multiline quote merging may engage. Plain scalars (`description: Don't merge`),
#: block-scalar content, and comments never match, so their apostrophes stay inert.
#: DOTALL so a partially merged logical line (already containing newlines) re-matches.
_QUOTED_VALUE_START = re.compile(
    r"^\s*(?:-\s+)?(?:\"[^\"\n]*\"|'[^'\n]*'|[A-Za-z0-9_.-]+)\s*:\s*([\"'].*)\Z"
    r"|^\s*-\s+([\"'].*)\Z",
    re.DOTALL,
)


def _fm_quoted_value_rest(logical):
    """The value text from its opening quote onward, when this logical line's value
    position begins with a quote; None otherwise (no merging context)."""
    match = _QUOTED_VALUE_START.match(logical)
    if match is None:
        return None
    return match.group(1) if match.group(1) is not None else match.group(2)


#: `key: |` / `key: >` — the line that opens a block scalar; the indicator grammar mirrors
#: _BLOCK_HEADER exactly ([|>][+-]?\d* — chomping and indentation indicators in the shapes
#: the walker itself accepts), trailing comment allowed. Everything more-indented after it
#: is opaque content.
_BLOCK_SCALAR_OPEN = re.compile(
    r"^(\s*)(?:-\s+)?(?:\"[^\"\n]*\"|'[^'\n]*'|[A-Za-z0-9_.-]+)\s*:\s*[|>][+-]?\d*\s*(?:#.*)?$"
)


def _fm_block_content_lines(lines):
    """Indices of lines that are block-scalar CONTENT — opaque bytes the multiline quote
    merger must never evaluate, whatever key-and-quote shapes they resemble."""
    inside, block_indent = set(), None
    for index, raw in enumerate(lines):
        if block_indent is not None:
            if not raw.strip() or (len(raw) - len(raw.lstrip())) > block_indent:
                inside.add(index)
                continue
            block_indent = None
        match = _BLOCK_SCALAR_OPEN.match(raw)
        if match is not None:
            block_indent = len(match.group(1))
    return inside


def _fm_open_quote(text):
    """The quote character left open at the end of `text`, or None. Same scan discipline as
    the comment stripper — including the comment rule itself, so an apostrophe inside a
    ` #` comment (`# don't`) never reads as an opened quote and can never trigger a bogus
    line merge. Backslash escapes honored inside double quotes; `''` in a single-quoted
    scalar reads as close-then-reopen, which is equivalent for openness."""
    inside, depth, index = None, 0, 0
    while index < len(text):
        char = text[index]
        if inside:
            if char == "\\" and inside == '"':
                index += 2
                continue
            if char == inside:
                inside = None
        elif char in "\"'":
            inside = char
        elif char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        elif char == "#" and depth == 0 and (index == 0 or text[index - 1] in " \t"):
            return None
        index += 1
    return inside


class _FrontmatterParser:
    """Block-structure walker over the fenced lines (fences excluded)."""

    def __init__(self, lines):
        # A quoted scalar may close on a later physical line (YAML multiline quoted
        # scalar): merge such runs first, preserving the newline as content, so the
        # per-line walk below only ever sees quote-balanced logical lines. Merging is
        # CONTEXT-AWARE: it engages only when a value position syntactically begins with
        # a quote that the scan finds still open — a plain scalar's or block scalar's
        # apostrophe is never a merge trigger. EOF with a value quote still open is a
        # structural failure.
        block_content = _fm_block_content_lines(lines)
        merged, index = [], 0
        while index < len(lines):
            logical, first = lines[index], index
            while first not in block_content:
                rest = _fm_quoted_value_rest(logical)
                if rest is None or _fm_open_quote(rest) is None:
                    break
                index += 1
                if index >= len(lines):
                    raise _FrontmatterError(
                        f"line {first + 2}: unterminated quoted scalar")
                logical += "\n" + lines[index]
            merged.append((logical, first))
            index += 1

        self.lines = lines
        self.tokens = []          # (indent, comment-stripped content, source line index)
        for logical, line_index in merged:
            content = _fm_strip_comment(logical).strip()
            if not content:
                continue
            leading = logical[:len(logical) - len(logical.lstrip())]
            if "\t" in leading:
                raise _FrontmatterError(f"line {line_index + 2}: tab in indentation")
            self.tokens.append((len(leading), content, line_index))

    @staticmethod
    def _is_item(content):
        return content == "-" or content.startswith("- ")

    @staticmethod
    def _split_key(content, line_no):
        """Split `key: rest`; raises when the line is not a mapping entry."""
        if content[0] in "\"'":
            key, end = _fm_quoted(content, 0, line_no)
            rest = content[end:].lstrip()
            if rest.startswith(":"):
                return str(key), rest[1:].strip()
            raise _FrontmatterError(f"line {line_no}: expected 'key: value'")
        depth = 0
        for index, char in enumerate(content):
            if char in "{[":
                depth += 1
            elif char in "}]":
                depth -= 1
            elif char == ":" and depth == 0 \
                    and (index + 1 == len(content) or content[index + 1] == " "):
                return content[:index].strip(), content[index + 1:].strip()
        bare = _BARE_KEY.fullmatch(content)     # `key:value` — tolerated authoring shorthand
        if bare:
            return bare.group(1), bare.group(2).strip()
        raise _FrontmatterError(f"line {line_no}: expected 'key: value'")

    def parse(self):
        if not self.tokens:
            return {}
        if self._is_item(self.tokens[0][1]):
            raise _FrontmatterError("line 2: top level is a sequence, not a mapping")
        result, pos = self._map(0, self.tokens[0][0])
        if pos != len(self.tokens):
            line_no = self.tokens[pos][2] + 2
            raise _FrontmatterError(f"line {line_no}: content outside the top-level mapping")
        return result

    def _node(self, pos):
        indent = self.tokens[pos][0]
        if self._is_item(self.tokens[pos][1]):
            return self._seq(pos, indent)
        return self._map(pos, indent)

    @staticmethod
    def _opens_flow(rest):
        """True when the value opens a flow collection that this line leaves unbalanced."""
        return bool(rest) and rest[0] in "{[" and _flow_depth(rest) > 0

    def _join_flow(self, rest, pos):
        """Bracket-match a multiline flow collection: append following token lines
        (whatever their indent) until the net depth closes; the joined text is then
        parsed as one inline value. Running out of tokens leaves the text unbalanced,
        which _fm_value reports as the unterminated structural failure."""
        parts, depth = [rest], _flow_depth(rest)
        while pos < len(self.tokens) and depth > 0:
            content = self.tokens[pos][1]
            parts.append(content)
            depth += _flow_depth(content)
            pos += 1
        return " ".join(parts), pos

    def _map(self, pos, indent):
        out = {}
        while pos < len(self.tokens) and self.tokens[pos][0] == indent \
                and not self._is_item(self.tokens[pos][1]):
            ind, content, line_index = self.tokens[pos]
            key, rest = self._split_key(content, line_index + 2)
            pos += 1
            if rest and _BLOCK_HEADER.fullmatch(rest):
                value, pos = self._block_scalar(pos, ind, line_index)
            elif self._opens_flow(rest):
                rest, pos = self._join_flow(rest, pos)
                value = _fm_value(rest, line_index + 2)
            elif rest:
                value = _fm_value(rest, line_index + 2)
                while pos < len(self.tokens) and self.tokens[pos][0] > ind:
                    # deeper lines after an inline scalar: multi-line plain continuation
                    if isinstance(value, str):
                        value = f"{value} {self.tokens[pos][1]}"
                    pos += 1
            elif pos < len(self.tokens) and self.tokens[pos][0] > ind:
                value, pos = self._node(pos)
            elif pos < len(self.tokens) and self.tokens[pos][0] == ind \
                    and self._is_item(self.tokens[pos][1]):
                value, pos = self._seq(pos, ind)    # sequence at the parent key's indent
            else:
                value = None
            out[key] = value                        # duplicate keys: last wins (permissive)
        return out, pos

    def _seq(self, pos, indent):
        out = []
        while pos < len(self.tokens) and self.tokens[pos][0] == indent \
                and self._is_item(self.tokens[pos][1]):
            ind, content, line_index = self.tokens[pos]
            rest = content[1:].strip()
            pos += 1
            if not rest:
                if pos < len(self.tokens) and self.tokens[pos][0] > ind:
                    value, pos = self._node(pos)
                else:
                    value = None
            elif self._opens_flow(rest):            # `- {a: b,` continuing on later lines
                rest, pos = self._join_flow(rest, pos)
                value = _fm_value(rest, line_index + 2)
            else:
                try:
                    key, item_rest = self._split_key(rest, line_index + 2)
                except _FrontmatterError:
                    key = None
                if key is not None:                 # `- key: value` mapping item
                    if self._opens_flow(item_rest):
                        item_rest, pos = self._join_flow(item_rest, pos)
                    value = {key: _fm_value(item_rest, line_index + 2) if item_rest else None}
                    if pos < len(self.tokens) and self.tokens[pos][0] > ind:
                        nested, pos = self._node(pos)
                        if isinstance(nested, dict):
                            value.update(nested)
                else:
                    value = _fm_value(rest, line_index + 2)
            out.append(value)
        return out, pos

    def _block_scalar(self, pos, indent, header_line_index):
        body, stop = [], header_line_index + 1
        for line_index in range(header_line_index + 1, len(self.lines)):
            raw = self.lines[line_index]
            if raw.strip() and len(raw) - len(raw.lstrip()) <= indent:
                break
            body.append(raw)
            stop = line_index + 1
        while body and not body[-1].strip():
            body.pop()
        widths = [len(l) - len(l.lstrip()) for l in body if l.strip()]
        width = min(widths) if widths else 0
        text = "\n".join(l[width:] if l.strip() else "" for l in body)
        while pos < len(self.tokens) and self.tokens[pos][2] < stop:
            pos += 1
        return (text + "\n" if text else ""), pos


def parse_md_frontmatter(text, rel):
    """Returns (fields, parse_failed).

    A file whose first line is not a `---` fence has NO frontmatter — its keys are simply
    missing ({} — the presence rows fire), which is not the malformed-parse case. A file that
    opens a fence is parsed by the permissive parser above: (None, True) — the -25 file-level
    penalty — ONLY on true structural failure (no closing fence, non-mapping top level,
    unbalanced quotes/brackets, tab-broken indentation).
    """
    if text.split("\n", 1)[0].strip() != "---":
        return {}, False
    lines = text.split("\n")
    closing = None
    for index in range(1, len(lines)):
        if not lines[index].startswith((" ", "\t")) and lines[index].rstrip() == "---":
            closing = index
            break
    if closing is None:
        return None, True
    try:
        return _FrontmatterParser(lines[1:closing]).parse(), False
    except _FrontmatterError:
        return None, True


def body_line_count(text):
    """Lines of the markdown body: the frontmatter block, fences included, is excluded."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index] == "---":
                return len(lines) - (index + 1)
    return len(lines)


def _walk_json(node, key=None):
    """Yield (key, value) leaves plus ("hooks", dict) containers, depth-first."""
    if isinstance(node, dict):
        for sub_key, value in node.items():
            if sub_key == "hooks" and isinstance(value, dict):
                yield ("hooks-map", value)
            yield from _walk_json(value, sub_key)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_json(item, key)
    else:
        yield (key, node)


def _measurable_criterion(clause):
    """conventions §4's third carve-out: "any listed term followed by a measurable-criterion
    clause". The owning text supplies no finer definition or example, so the mechanical
    encoding is closed and exactly this: the clause carries a quantity — a digit, or a
    spelled-out cardinal from _NUMBER_WORDS ("appropriate timeout of one minute",
    "a reasonable number of times, at most three"). No other context is consulted."""
    if re.search(r"\d", clause):
        return True
    return any(word.lower() in _NUMBER_WORDS for word in re.findall(r"[A-Za-z]+", clause))


def count_r01(text):
    """R01 occurrences after the three conventions §4 carve-outs; returns (count, first_line).

    Carve-outs, exactly as skills/conventions/SKILL.md states them and no further contextual
    rules: `relevant` on a markdown heading line; `relevant to <named-scope>` (the term
    followed by `to` and a named scope); any listed term followed by a measurable-criterion
    clause — the remainder of the term's own sentence on its line carries a quantity
    (a digit or a spelled-out cardinal; see `_measurable_criterion`).
    """
    count, first_line = 0, None
    for match in _VAGUE.finditer(text):
        start = text.rfind("\n", 0, match.start()) + 1
        end = text.find("\n", match.end())
        end = len(text) if end < 0 else end
        if match.group(0).lower() == "relevant":
            if _HEADING.match(text, start):
                continue
            if re.match(r"\s+to\s+\S", text[match.end():end]):
                continue
        sentence = _SENTENCE_END.split(text[match.end():end], 1)[0]
        if _measurable_criterion(sentence):
            continue
        count += 1
        if first_line is None:
            first_line = text.count("\n", 0, match.start()) + 1
    return count, first_line


# ---------------------------------------------------------------------- per-type checks
# One function per artifact type carrying mechanical rows. Every emit cites a ledger row
# classified `mechanical` (or the file-level parse semantics); nothing else may deduct.
# Rows of a tool-specific table are tier-conditioned (the scorer gauntlet's do-not-penalize
# principle): they fire only on artifacts of that tool's tier, never across tiers.

def _load_json(text, emit, check):
    try:
        return json.loads(text)
    except ValueError:
        emit("--", check, -25)
        return None


def check_skill(text, rel, path, overrides, emit, tier):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None:
        name = frontmatter.get("name")
        if name is None:
            emit("--", "name present", -25)
        elif str(name) != Path(rel).parent.name:
            # Only diffable when a name exists — with no frontmatter name there is nothing
            # to diff, so the row cannot fire (worksheet #1: no double-count).
            emit("--", "name matches parent dir", -15)
        description = frontmatter.get("description")
        if description is None:
            emit("R04", "description present", -25)
        else:
            chars = len(str(description))
            if chars > 800:
                emit("R04", "description length", -10)
            elif chars >= 500:
                emit("R04", "description length", -5)
        if frontmatter.get("user_invocable") is True and "<example>" not in text:
            emit("R06", "example blocks", -10)

    # Body rows need no frontmatter; they are scored even after a parse failure. The override
    # `threshold` replaces the 500-line upper boundary only; the 400 lower boundary stays.
    threshold = Controls(overrides, "R05").threshold
    upper = threshold if isinstance(threshold, int) else 500
    lines = body_line_count(text)
    if lines > upper:
        emit("R05", "body length", -10)
    elif lines >= 400:
        emit("R05", "body length", -5)


def check_agent(text, rel, path, overrides, emit, tier):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None:
        if frontmatter.get("description") is None:
            emit("R09", "description present", -25)
        if frontmatter.get("model") is None:
            emit("R10", "model declared", -5)
        if frontmatter.get("tools") is None:
            emit("R11", "tools declared", -5)
    examples = text.count("<example>")
    if examples == 0:
        emit("R09", "example blocks", -15)
    elif examples == 1:
        emit("R09", "example blocks", -5)
    if not re.search(r"(?im)^#{1,6}\s[^\n]*output", text):
        emit("R12", "output format", -10)


def check_command(text, rel, path, overrides, emit, tier):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None and frontmatter.get("description") is None:
        emit("--", "description present", -25)


def check_shared_partial(text, rel, path, overrides, emit, tier):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None and frontmatter.get("user-invocable") is not False:
        emit("R19", "`user-invocable: false`", -25)


def check_rule(text, rel, path, overrides, emit, tier):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None and frontmatter.get("description") is None:
        emit("R21", "description present", -10)
    threshold = Controls(overrides, "R23").threshold
    limit = threshold if isinstance(threshold, int) else 500
    if len(text.splitlines()) > limit:
        emit("R23", "budget", -15)


def check_hook_config(text, rel, path, overrides, emit, tier):
    # Text-level row first: the dangerous patterns are literal, parse or no parse.
    if any(pattern in text for pattern in DANGEROUS_PATTERNS):
        emit("--", "command safety", -15)
    data = _load_json(text, emit, "valid syntax")
    if data is None:
        return
    events, bad_matcher, bad_timeout, bad_type = [], False, False, False
    for key, value in _walk_json(data):
        if key == "hooks-map":
            events.extend(k for k in value if isinstance(k, str))
        elif key == "event" and isinstance(value, str):
            events.append(value)
        elif key == "matcher" and isinstance(value, str):
            try:
                re.compile(value)
            except re.error:
                bad_matcher = True
        elif key == "timeout" and isinstance(value, (int, float)) \
                and not isinstance(value, bool) and value > 30:
            bad_timeout = True
        elif key == "type" and isinstance(value, str) and value not in CLAUDE_HOOK_TYPES:
            bad_type = True
    # Universal rows ("Hooks — universal (all tools)") fire on every tier.
    if bad_matcher:
        emit("--", "matcher regex valid", -10)
    if bad_timeout:
        emit("--", "timeout reasonable", -5)
    # Per-tool event tables are tier-conditioned: the Claude/Codex R27 rows fire only on
    # their own tier's artifacts; Antigravity stays advisory by its owning text.
    confirmed = HOOK_EVENTS_BY_TIER.get(tier)
    if confirmed is not None:
        lowered = {event.lower() for event in confirmed}
        unknown = [e for e in events if e not in confirmed]
        if any(e.lower() not in lowered for e in unknown):
            emit("R27", "event names valid", -15)
        if any(e.lower() in lowered for e in unknown):
            emit("R27", "case correct", -10)
    if tier == "2-Claude" and bad_type:
        emit("--", "hook type valid", -10)


def check_manifest(text, rel, path, overrides, emit, tier):
    data = _load_json(text, emit, "valid JSON")
    if data is None or tier != "2-Claude":
        # The content rows belong to the "plugin.json (Claude, `.claude-plugin/plugin.json`)"
        # table — 2-Claude tier only; the parse row above is the universal file-level -25.
        return
    if not isinstance(data, dict):
        data = {}
    if data.get("name") is None:
        emit("--", "name present", -25)
    version = data.get("version")
    if version is not None and not (isinstance(version, str) and _SEMVER.fullmatch(version)):
        emit("--", "version is semver", -10)
    if data.get("description") is None:
        emit("--", "description present", -5)


def check_mcp_config(text, rel, path, overrides, emit, tier):
    data = _load_json(text, emit, "valid JSON")
    if data is None or tier != "2-Claude":
        return                    # the server-command row is the Claude .mcp.json table's
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if isinstance(servers, dict) and any(
            not (isinstance(entry, dict) and entry.get("command"))
            for entry in servers.values()):
        emit("--", "server command present", -15)


def check_lsp_config(text, rel, path, overrides, emit, tier):
    _load_json(text, emit, "valid JSON")


def check_settings(text, rel, path, overrides, emit, tier):
    data = _load_json(text, emit, "valid JSON")
    if data is None or tier != "2-Claude":
        return          # the hook-definitions row checks Claude events — 2-Claude tier only
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if isinstance(hooks, dict):
        for event in hooks:                       # -10 per invalid, per the row
            if event not in CLAUDE_HOOK_EVENTS:
                emit("--", "hook definitions valid", -10)


def check_claude_md(text, rel, path, overrides, emit, tier):
    if len(text.splitlines()) > 200:
        emit("--", "under 200 lines", -5)
    broken = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = re.fullmatch(r"@(\S+)", line.strip())
        if match and not match.group(1).startswith(("/", "~")):
            if not (path.parent / match.group(1)).exists():
                broken = True
    if broken:
        emit("R36", "valid `@` imports", -10)


def check_memory(text, rel, path, overrides, emit, tier):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
        return
    if frontmatter == {}:
        emit("--", "has YAML frontmatter", -15)
        return
    if frontmatter.get("name") is None:
        emit("--", "name in frontmatter", -10)
    if frontmatter.get("description") is None:
        emit("--", "description in frontmatter", -10)
    if frontmatter.get("type") not in _MEMORY_TYPES:
        emit("--", "type in frontmatter (values: user/feedback/project/reference)", -5)


TYPE_CHECKS = {
    "skill": check_skill,
    "agent": check_agent,
    "command": check_command,
    "user-command": check_command,
    "shared-partial": check_shared_partial,
    "rule": check_rule,
    "hook-config": check_hook_config,
    "manifest": check_manifest,
    "mcp-config": check_mcp_config,
    "lsp-config": check_lsp_config,
    "settings": check_settings,
    "claude-md": check_claude_md,
    "memory": check_memory,
}


# ------------------------------------------------------------------------------- scoring

def score_text(text, rel, path, artifact_type, tier, overrides, pass_threshold):
    """Score one decoded file. Returns (files[] entry, summed penalty)."""
    findings = []

    def emit(rule, check, penalty, line=1):
        findings.append({"rule": rule, "check": check, "line": line, "penalty": penalty})

    checks = TYPE_CHECKS.get(artifact_type)
    if checks:
        checks(text, rel, path, overrides, emit, tier)

    hits, first_line = count_r01(text)
    if hits:
        threshold = Controls(overrides, "R01").threshold
        cap = -abs(threshold) if isinstance(threshold, int) else -20
        emit("R01", "vague quantifier", max(-2 * hits, cap), line=first_line)

    kept = []
    advisories = []
    for finding in findings:
        if Controls(overrides, finding["rule"]).suppressed:
            advisories.append({
                "rule": finding["rule"],
                "note": "suppressed by rule_overrides: "
                        f"{finding['check']} ({finding['penalty']}) zeroed",
            })
            continue
        kept.append(finding)
    for rule in sorted({finding["rule"] for finding in kept}):
        control = Controls(overrides, rule)
        if not isinstance(control.max_penalty, int):
            continue
        cap = -abs(control.max_penalty)
        members = [finding for finding in kept if finding["rule"] == rule]
        total = sum(finding["penalty"] for finding in members)
        if total < cap:
            members[-1]["penalty"] += cap - total
    if any(f["rule"] == "R01" and f["check"] == "vague quantifier" for f in kept):
        # conventions §4's third carve-out ("any listed term followed by a
        # measurable-criterion clause") is open-ended: the owning text names no example
        # form. A counted term is by definition one where no encoded carve-out form
        # followed, so the deduction stands and the residual ambiguity is surfaced —
        # resolvable through the rubric's own config override, never by widening the
        # engine's closed encoding.
        advisories.append({
            "rule": "R01",
            "note": "R01 counted; carve-out forms absent -- if this is "
                    "measurable-in-context, suppress via rule_overrides.R01"})
    for rule, check in TYPE_ADVISORIES.get(artifact_type, ()):
        advisories.append({
            "rule": rule,
            "note": f"advisory-zero: {check}; no objective predicate for the engine"})
    for rule, note in TIER_ADVISORIES.get((artifact_type, tier), ()):
        advisories.append({"rule": rule, "note": note})
    if tier == "1":
        # The scoring skill's whole Tier 1.5 definition is "open-spec corpora" — a
        # collection property. A tier-`1` file shows the definition's "open-spec"
        # marker; whether it belongs to a corpus is not decidable from one file's
        # bytes and path, so the boundary is stated explicitly instead of silently.
        advisories.append({
            "rule": "--",
            "note": "tier boundary: emitted 1 (open-spec artifact); Tier 1.5 "
                    "(open-spec corpora) is a collection property with no per-file "
                    "predicate, so whether this file belongs to an open-spec corpus "
                    "stays with the narrating agent"})
    if (overrides.get("R51") or {}).get("enabled") is True:
        # The R51 misconfigured row: enabled without engine registry support stays advisory.
        advisories.append({
            "rule": "R51",
            "note": "advisory-zero: misconfigured; R51 is enabled but the engine ships no "
                    "registry.yaml reader, so the penalty stays zero"})

    total = sum(finding["penalty"] for finding in kept)
    score = max(0, min(100, 100 + total))
    return {
        "path": rel,
        "tier": tier,
        "score": score,
        "band": band(score),
        "verdict": "pass" if score >= pass_threshold else "fail",
        "findings": kept,
        "advisories": advisories,
    }, total


def _content_key(e):
    return (e.get("scope"), e.get("file"), e.get("score"), e.get("band"),
            e.get("total_penalty"))


def _append_history(history, scope, files, totals, run_id=None):
    """Append per-file snapshots; identical entries dedupe; the write is atomic or nothing.

    Dedup compares the CONTENT KEY — (scope, file, score, band, total_penalty) — never whole
    dicts: flagless, a snapshot matching any existing entry's content key drops, whether or not
    that entry carries a run field; with `--run-id`, a snapshot drops only when content key AND
    run both match, so identical content in an earlier run still appends — which is what makes
    run membership and trajectories reconstructable (E6.2).
    """
    if history.exists():
        existing = json.loads(history.read_text(encoding="utf-8"))
        if not isinstance(existing, list):
            raise ValueError("history is not a JSON list")
    else:
        existing = []
    changed = False
    for entry, total in zip(files, totals):
        snapshot = {"scope": scope, "score": entry["score"], "band": entry["band"],
                    "total_penalty": total, "file": entry["path"]}
        key = _content_key(snapshot)
        if run_id is not None:
            snapshot["run"] = run_id
            dup = any(_content_key(e) == key and e.get("run") == run_id
                      for e in existing if isinstance(e, dict))
        else:
            dup = any(_content_key(e) == key for e in existing if isinstance(e, dict))
        if not dup:
            existing.append(snapshot)
            changed = True
    if changed:
        content = json.dumps(existing, indent=2, sort_keys=True) + "\n"
        # Temp file in the destination directory, then an atomic rename; on any failure the
        # primitive removes its temp and the original bytes are never touched.
        bridge.write_atomic(history.parent, history, content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True)
    parser.add_argument("--config")
    parser.add_argument("--history")
    parser.add_argument("--scope")
    parser.add_argument("--run-id", dest="run_id")  # opaque, 1-64 chars (validated below)
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        print(f"score_engine: root {args.root!r} is not a directory", file=sys.stderr)
        return 2

    try:
        records = ls_counts.parse_records(sys.stdin.buffer.read())
    except ValueError as err:
        print(f"score_engine: {err}", file=sys.stderr)
        return 2

    overrides = {}
    pass_threshold = config_mod.SCHEMA["score_threshold"].default
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            try:
                text = config_path.read_text(encoding="utf-8")
            except OSError as err:
                print(f"score_engine: config unreadable: {err}", file=sys.stderr)
                return 2
            try:
                resolved_config, _warnings = config_mod.resolve_text(text, args.root)
            except (config_mod.ConfigSyntaxError, config_mod.ConfigValueError,
                    config_mod.ConfigContainmentError) as err:
                print(f"score_engine: config: {err}", file=sys.stderr)
                return 2
            overrides = resolved_config.get("rule_overrides") or {}
            pass_threshold = resolved_config.get("score_threshold", pass_threshold)
        # A missing config file is the documented default state, never a refusal.

    offenders = []
    resolved = []
    for field, rel in records:
        path, reason = ls_counts.resolve(root, rel)
        if path is None:
            offenders.append(f"{rel!r}: {reason}")
        else:
            resolved.append((resolve_type(field, rel), rel, path))
    if offenders:
        for line in offenders:
            print(f"score_engine: refused {line}", file=sys.stderr)
        return 2

    files = []
    totals = []
    skipped = []
    considered = 0
    for artifact_type, rel, path in resolved:
        tier = classify_tier(rel)
        try:
            data = path.read_bytes()
        except OSError:
            skipped.append(rel)          # unreadable: noted, never fatal
            continue
        if not data:
            files.append({"path": rel, "tier": tier, "score": 0, "band": "Rewrite",
                          "verdict": "pass" if pass_threshold <= 0 else "fail",
                          "findings": [], "advisories": []})
            totals.append(0)
            continue
        considered += type_rows(artifact_type, tier) + GENERIC_ROWS
        entry, total = score_text(data.decode("utf-8", errors="replace"), rel, path,
                                  artifact_type, tier, overrides, pass_threshold)
        files.append(entry)
        totals.append(total)

    out = {
        "files": files,
        "run": {
            "files": len(files),
            "total_penalty": sum(totals),
            "considered_rows": considered,
            "skipped": skipped,
        },
    }
    json.dump(out, sys.stdout, indent=2, sort_keys=True)
    print()

    if args.run_id is not None and not 1 <= len(args.run_id) <= 64:
        print("score_engine: --run-id must be 1-64 characters", file=sys.stderr)
        return 2
    if args.history:
        if not args.scope:
            print("score_engine: --history requires --scope", file=sys.stderr)
            return 2
        try:
            _append_history(Path(args.history), args.scope, files, totals, run_id=args.run_id)
        except (bridge.BridgeError, OSError, ValueError) as err:
            print(f"score_engine: history append failed: {err}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
