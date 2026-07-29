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
  args   : --root <dir> [--config <file>] [--history <file>] [--scope <tag>]
  stdout : JSON {"files":[{"path","score","band","verdict",
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
  description : counted in CHARACTERS of the description value — 500-800 -> -5, over 800 -> -10
  body (R05)  : counted in lines of the MARKDOWN BODY — the frontmatter block (both `---`
                fences included) is excluded — 400..upper -> -5, over upper -> -10, where the
                upper boundary is 500 or the R05 `threshold` override; the 400 lower stays
  R01         : token-bounded occurrences of the 11 listed words, -2 each, capped at -20, minus
                the three carve-outs of skills/conventions/SKILL.md §4 (heading `relevant`,
                `relevant to <named-scope>`, term followed by a measurable-criterion clause)
  degenerate  : unparseable frontmatter/config -> one -25 parse finding, and every row that
                does not need the parsed structure is still scored; empty (0-byte) file ->
                score 0, band Rewrite; unreadable file -> absent from files[], listed in
                run.skipped, exit stays 0

Config is read through scripts/lib/config.py — the one reader; no second parser:
  rule_overrides.<Rid>.suppress / enabled: false -> rule zeroed, findings moved to advisories
  rule_overrides.<Rid>.max_penalty               -> the rule's summed penalty floors at -abs(value)
  rule_overrides.<Rid>.threshold                 -> numeric trigger: R01 the cap, R05/R23 the
                                                    upper line boundary
  score_threshold                                -> the pass/fail verdict boundary

History (--history H --scope S): one {"scope","score","band","total_penalty","file"} entry per
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

#: Confirmed Claude hook events and hook types, verbatim from the scoring skill's
#: "Hooks (Claude Code, Tier 2-Claude)" table conditions.
CLAUDE_HOOK_EVENTS = (
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse", "PostToolUse",
    "PermissionRequest", "Stop", "StopFailure", "FileChanged",
)
CLAUDE_HOOK_TYPES = ("command", "http", "mcp_tool", "prompt", "agent")
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
        ("--", "MCP matcher format"),
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

#: Penalty-table rows one evaluation of the type consults (the type's own tables); every
#: evaluation additionally consults the two all-types R01 rows.
TYPE_TABLE_ROWS = {
    "skill": 12, "agent": 9, "command": 6, "user-command": 6, "shared-partial": 2,
    "rule": 7, "hook-config": 9, "manifest": 3, "mcp-config": 2, "lsp-config": 1,
    "settings": 5, "claude-md": 11, "memory": 7,
}
GENERIC_ROWS = 2


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


def parse_md_frontmatter(text, rel):
    """Returns (fields, parse_failed).

    A file whose first line is not a `---` fence has NO frontmatter — its keys are simply
    missing ({} — the presence rows fire), which is not the malformed-parse case. A file that
    opens a fence but fails the accepted YAML subset is malformed: (None, True), the -25
    file-level penalty. The parser is the config module's — one grammar — with the artifact
    key alphabet, so documented hyphenated keys (`allowed-tools`) parse instead of penalizing.
    """
    if text.split("\n", 1)[0].strip() != "---":
        return {}, False
    try:
        return config_mod.parse_frontmatter(
            text, source=rel, key_pattern=config_mod.ARTIFACT_KEY), False
    except config_mod.ConfigSyntaxError:
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


def count_r01(text):
    """R01 occurrences after the three conventions §4 carve-outs; returns (count, first_line).

    Carve-outs, exactly as skills/conventions/SKILL.md states them and no further contextual
    rules: `relevant` on a markdown heading line; `relevant to <named-scope>` (the term
    followed by `to` and a named scope); any listed term followed by a measurable-criterion
    clause — mechanically, a digit in the remainder of the term's own sentence on its line.
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
        if re.search(r"\d", sentence):
            continue
        count += 1
        if first_line is None:
            first_line = text.count("\n", 0, match.start()) + 1
    return count, first_line


# ---------------------------------------------------------------------- per-type checks
# One function per artifact type carrying mechanical rows. Every emit cites a ledger row
# classified `mechanical` (or the file-level parse semantics); nothing else may deduct.

def _load_json(text, emit, check):
    try:
        return json.loads(text)
    except ValueError:
        emit("--", check, -25)
        return None


def check_skill(text, rel, path, overrides, emit):
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


def check_agent(text, rel, path, overrides, emit):
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


def check_command(text, rel, path, overrides, emit):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None and frontmatter.get("description") is None:
        emit("--", "description present", -25)


def check_shared_partial(text, rel, path, overrides, emit):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None and frontmatter.get("user-invocable") is not False:
        emit("R19", "`user-invocable: false`", -25)


def check_rule(text, rel, path, overrides, emit):
    frontmatter, failed = parse_md_frontmatter(text, rel)
    if failed:
        emit("--", "frontmatter parse", -25)
    if frontmatter is not None and frontmatter.get("description") is None:
        emit("R21", "description present", -10)
    threshold = Controls(overrides, "R23").threshold
    limit = threshold if isinstance(threshold, int) else 500
    if len(text.splitlines()) > limit:
        emit("R23", "budget", -15)


def check_hook_config(text, rel, path, overrides, emit):
    # Text-level row first: the dangerous patterns are literal, parse or no parse.
    if any(pattern in text for pattern in DANGEROUS_PATTERNS):
        emit("--", "command safety", -15)
    data = _load_json(text, emit, "valid syntax")
    if data is None:
        return
    events, bad_matcher, bad_timeout, bad_type = [], False, False, False
    lowered = {event.lower() for event in CLAUDE_HOOK_EVENTS}
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
    if bad_matcher:
        emit("--", "matcher regex valid", -10)
    if bad_timeout:
        emit("--", "timeout reasonable", -5)
    unknown = [e for e in events if e not in CLAUDE_HOOK_EVENTS]
    if any(e.lower() not in lowered for e in unknown):
        emit("R27", "event names valid", -15)
    if any(e.lower() in lowered for e in unknown):
        emit("R27", "case correct", -10)
    if bad_type:
        emit("--", "hook type valid", -10)


def check_manifest(text, rel, path, overrides, emit):
    data = _load_json(text, emit, "valid JSON")
    if data is None:
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


def check_mcp_config(text, rel, path, overrides, emit):
    data = _load_json(text, emit, "valid JSON")
    if data is None:
        return
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    if isinstance(servers, dict) and any(
            not (isinstance(entry, dict) and entry.get("command"))
            for entry in servers.values()):
        emit("--", "server command present", -15)


def check_lsp_config(text, rel, path, overrides, emit):
    _load_json(text, emit, "valid JSON")


def check_settings(text, rel, path, overrides, emit):
    data = _load_json(text, emit, "valid JSON")
    if data is None:
        return
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if isinstance(hooks, dict):
        for event in hooks:                       # -10 per invalid, per the row
            if event not in CLAUDE_HOOK_EVENTS:
                emit("--", "hook definitions valid", -10)


def check_claude_md(text, rel, path, overrides, emit):
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


def check_memory(text, rel, path, overrides, emit):
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

def score_text(text, rel, path, artifact_type, overrides, pass_threshold):
    """Score one decoded file. Returns (files[] entry, summed penalty)."""
    findings = []

    def emit(rule, check, penalty, line=1):
        findings.append({"rule": rule, "check": check, "line": line, "penalty": penalty})

    checks = TYPE_CHECKS.get(artifact_type)
    if checks:
        checks(text, rel, path, overrides, emit)

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
    for rule, check in TYPE_ADVISORIES.get(artifact_type, ()):
        advisories.append({
            "rule": rule,
            "note": f"advisory-zero: {check}; no objective predicate for the engine"})
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
        "score": score,
        "band": band(score),
        "verdict": "pass" if score >= pass_threshold else "fail",
        "findings": kept,
        "advisories": advisories,
    }, total


def _append_history(history, scope, files, totals):
    """Append per-file snapshots; identical entries dedupe; the write is atomic or nothing."""
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
        if snapshot not in existing:
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
        try:
            data = path.read_bytes()
        except OSError:
            skipped.append(rel)          # unreadable: noted, never fatal
            continue
        if not data:
            files.append({"path": rel, "score": 0, "band": "Rewrite",
                          "verdict": "pass" if pass_threshold <= 0 else "fail",
                          "findings": [], "advisories": []})
            totals.append(0)
            continue
        considered += TYPE_TABLE_ROWS.get(artifact_type, 0) + GENERIC_ROWS
        entry, total = score_text(data.decode("utf-8", errors="replace"), rel, path,
                                  artifact_type, overrides, pass_threshold)
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

    if args.history:
        if not args.scope:
            print("score_engine: --history requires --scope", file=sys.stderr)
            return 2
        try:
            _append_history(Path(args.history), args.scope, files, totals)
        except (bridge.BridgeError, OSError, ValueError) as err:
            print(f"score_engine: history append failed: {err}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
