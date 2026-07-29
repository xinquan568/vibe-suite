#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Deterministic scoring engine for /vibe-suite:score (E3.3 / vibe-28).

The engine is the ONLY penalty authority; agents narrate its output. The hand-computed oracle
(tests/fixtures/nl-audit/defective-skill/expected.json + its README worksheet) pins the semantics:
the engine deducts ONLY on the rows the row ledger (scripts/score_engine_rows.md) classifies
`mechanical`, and reports every `advisory-zero` row as an advisory with zero penalty. Both the
command at runtime and tests/test_score_goldens.py invoke THIS file, so the penalty arithmetic
exists exactly once.

CLI contract (pinned by tests/test_score_goldens.py):
  stdin  : records `<type>\\x1f<relative-path>\\x00` — the same lossless framing as ls_counts,
           whose parser and path resolution are imported rather than restated
  args   : --root <dir> [--config <file>] [--history <file>] [--scope <tag>]
  stdout : JSON {"files":[{"path","score","band","findings":[{"rule","check","line","penalty"}],
           "advisories":[{"rule","note"}]}],
           "run":{"files","total_penalty","considered_rows","skipped"}}
  exit   : 0 scored; 1 history append failed; 2 contract refusal (bad record, bad root/config,
           a path that is absolute, escapes the root, or does not exist)

Scoring semantics (owning text: skills/scoring/SKILL.md; row classifications with their quoted
predicates: scripts/score_engine_rows.md):
  formula     : final = max(0, min(100, 100 + sum(penalties)))
  description : counted in CHARACTERS of the description value — 500-800 -> -5, over 800 -> -10
  body        : counted in physical lines of the WHOLE file — 400-500 -> -5, over 500 -> -10
  R01         : token-bounded occurrences of the 11 listed words, -2 each, capped at -20
  degenerate  : unparseable frontmatter -> one -25 "frontmatter parse" finding, and every row
                that does not need frontmatter is still scored; empty (0-byte) file -> score 0,
                band Rewrite; unreadable file -> absent from files[], listed in run.skipped,
                exit stays 0

Config is read through scripts/lib/config.py — the one reader; no second parser:
  rule_overrides.<Rid>.suppress / enabled: false -> rule zeroed, findings moved to advisories
  rule_overrides.<Rid>.max_penalty               -> the rule's summed penalty floors at -abs(value)
  rule_overrides.<Rid>.threshold                 -> numeric trigger: R01 the cap, R05 the lower
                                                    line boundary (band width stays 100 lines)

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

#: A scope note is a heading naming scope, or a cross-reference out of the skill's own directory.
_SCOPE_HEADING = re.compile(r"^#{1,6}\s[^\n]*\bscope\b", re.IGNORECASE | re.MULTILINE)
_SIBLING_LINK = re.compile(r"\]\(\.\./")

BANDS = ((90, "Excellent"), (80, "Good"), (70, "Adequate"), (60, "Weak"))

#: One advisory per advisory-zero ledger row, emitted unconditionally for every scored skill.
#: The rows have no objective predicate (scripts/score_engine_rows.md quotes each justification),
#: so their presence cannot be decided mechanically either way — the engine reports the class and
#: deducts nothing; judgment about it belongs to the narrating agent.
ADVISORY_ROWS = (
    ("R04", "trigger quality"),
    ("R06", "code examples (complex concepts but no examples)"),
    ("R06", "code examples (no examples at all in a technical skill)"),
    ("--", "broken references link"),
    ("--", "pseudocode example"),
    ("--", "domain mixing"),
    ("--", "redundant content"),
    ("--", "orphaned registration"),
)

#: Ledger rows one evaluation consults: the 12 Skills-table rows plus the two R01 rows for a
#: skill; every other artifact type currently gets only the all-types R01 pair.
SKILL_ROWS = 14
GENERIC_ROWS = 2


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


def score_text(text, rel, overrides, is_skill):
    """Score one decoded file. Returns (files[] entry, summed penalty)."""
    findings = []

    def emit(rule, check, penalty, line=1):
        findings.append({"rule": rule, "check": check, "line": line, "penalty": penalty})

    if is_skill:
        frontmatter = None
        try:
            # The one frontmatter grammar this suite owns; a hand-rolled second parser would be
            # two statements of one schema. Anything outside the accepted subset is a parse
            # failure, which is exactly the -25 the rubric assigns.
            frontmatter = config_mod.parse_frontmatter(text, source=rel)
        except config_mod.ConfigSyntaxError:
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

        # Body rows need no frontmatter; they are scored even after a parse failure.
        threshold = Controls(overrides, "R05").threshold
        lower = threshold if isinstance(threshold, int) else 400
        lines = len(text.splitlines())
        if lines > lower + 100:
            emit("R05", "body length", -10)
        elif lines >= lower:
            emit("R05", "body length", -5)

        if not (_SCOPE_HEADING.search(text) or _SIBLING_LINK.search(text)):
            emit("R07", "scope note", -3)

    hits = list(_VAGUE.finditer(text))
    if hits:
        threshold = Controls(overrides, "R01").threshold
        cap = -abs(threshold) if isinstance(threshold, int) else -20
        emit("R01", "vague quantifier", max(-2 * len(hits), cap),
             line=text.count("\n", 0, hits[0].start()) + 1)

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
    if is_skill:
        for rule, check in ADVISORY_ROWS:
            advisories.append(
                {"rule": rule, "note": f"advisory-zero: {check} — no objective predicate"})

    total = sum(finding["penalty"] for finding in kept)
    score = max(0, min(100, 100 + total))
    return {
        "path": rel,
        "score": score,
        "band": band(score),
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
    if args.config:
        try:
            text = Path(args.config).read_text(encoding="utf-8")
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

    offenders = []
    resolved = []
    for artifact_type, rel in records:
        path, reason = ls_counts.resolve(root, rel)
        if path is None:
            offenders.append(f"{rel!r}: {reason}")
        else:
            resolved.append((artifact_type, rel, path))
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
                          "findings": [], "advisories": []})
            totals.append(0)
            continue
        is_skill = artifact_type == "skill"
        considered += SKILL_ROWS if is_skill else GENERIC_ROWS
        entry, total = score_text(data.decode("utf-8", errors="replace"), rel,
                                  overrides, is_skill)
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
