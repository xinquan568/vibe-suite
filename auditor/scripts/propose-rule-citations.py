#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Propose exemplar citations for the rulebook, and optionally apply them.

    propose-rule-citations.py [--apply] --data-dir DIR --rules-path PATH
                              [--exemplar-url-prefix URL]

Each rule gains a generated block linking the exemplars that demonstrate it. Default is a dry
run printing the proposals; `--apply` rewrites the rules file between its markers.

LINKS MUST BE ABSOLUTE. The rulebook is read on github.com, in editors, in rendered docs and
inside issue bodies quoted elsewhere. A relative link resolves against whatever host is showing
the page, so it silently points at the wrong place — or nowhere — everywhere except the one
context it was authored in. The prefix is therefore validated rather than trusted: HTTPS, no
userinfo, no query, no fragment, and a path ending in `/blob/auditor-data/exemplars`.

The prefix names THIS repository — the one holding `skills/rules/SKILL.md` and the
`auditor-data` branch — not the audited repository the exemplar is about. Those are different
repositories and the exemplar's own frontmatter names the other one.

MARKERS ARE REPLACED, NEVER APPENDED TO. Appending stacks a fresh block under every previous
one on each run, and because each block is individually well-formed the file keeps looking
correct while growing without bound. A second apply over unchanged input must leave the file
byte-identical, and there is a test for exactly that.

`--apply` WITH NO EXEMPLARS REFUSES, and this is the explicit exception to "absent exemplars
are optional". A non-mutating run may model an absent corpus as empty; an applying run may not,
because "no exemplars found" and "the corpus failed to load" produce identical empty lists, and
one of them means every existing citation should be deleted. Refusing leaves the rules file
byte-identical.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

#: At most this many exemplars are cited per rule — strongest first. See collect().
MAX_PER_RULE = 3

#: The rulebook already carries one `:site <rule>` anchor per rule — 38 of them, hand-placed.
#: They are the insertion points, not something this helper invents: looking for begin/end
#: pairs that exist nowhere in the file meant every apply matched nothing and changed nothing,
#: while still exiting zero and reporting the rules it had "applied".
ANCHOR = "<!-- vibe-exemplar-citation:site {rule} -->"
#: The generated region this helper owns, written directly beneath the anchor. Delimited so a
#: second run REPLACES it rather than stacking another copy under the same anchor.
BEGIN = "<!-- vibe-exemplar-citation:begin {rule} -->"
END = "<!-- vibe-exemplar-citation:end {rule} -->"
REQUIRED_PATH_SUFFIX = "/blob/auditor-data/exemplars"
#: One URL path segment. `safe` keeps the unreserved set so ordinary names stay readable.
SAFE = "-._~"
UNSAFE_IN_FILENAME = ("/", "\\", "\x00", "\r", "\n")


def refuse(reason: str) -> None:
    print(f"REFUSE:propose-rule-citations:{reason}", file=sys.stderr)
    raise SystemExit(1)


def resolve_prefix(explicit):
    """`--exemplar-url-prefix`, then $VIBE_EXEMPLAR_URL_PREFIX, then the derived default."""
    prefix = explicit or os.environ.get("VIBE_EXEMPLAR_URL_PREFIX")
    if not prefix:
        repository = os.environ.get("GITHUB_REPOSITORY")
        if not repository:
            refuse("exemplar-url-prefix-unconfigured")
        server = os.environ.get("GITHUB_SERVER_URL") or "https://github.com"
        prefix = f"{server.rstrip('/')}/{repository}{REQUIRED_PATH_SUFFIX}"
    return validate_prefix(prefix)


def validate_prefix(prefix: str) -> str:
    prefix = prefix.rstrip("/") if prefix.endswith("/") else prefix
    parsed = urllib.parse.urlsplit(prefix)
    if parsed.scheme != "https" or not parsed.netloc:
        refuse("exemplar-url-prefix-invalid")
    if parsed.username or parsed.password or "@" in parsed.netloc:
        refuse("exemplar-url-prefix-invalid")
    if parsed.query or parsed.fragment:
        refuse("exemplar-url-prefix-invalid")
    if not parsed.path.endswith(REQUIRED_PATH_SUFFIX):
        refuse("exemplar-url-prefix-invalid")
    return prefix


def exemplar_url(prefix: str, filename: str) -> str:
    if any(ch in filename for ch in UNSAFE_IN_FILENAME) or not filename:
        refuse("unsafe-exemplar-filename")
    return f"{prefix}/{urllib.parse.quote(filename, safe=SAFE)}"


def markdown_label(text: str) -> str:
    """A safe Markdown link label: escape what would break the link, flatten newlines."""
    flattened = re.sub(r"[\r\n]+", " ", str(text))
    for ch in ("\\", "[", "]"):
        flattened = flattened.replace(ch, "\\" + ch)
    return flattened.strip()


def read_exemplars(data_dir: Path):
    """`{rule_id: [(filename, label), ...]}` from the exemplar corpus, in a stable order."""
    directory = data_dir / "exemplars"
    if not directory.is_dir():
        return None
    by_rule: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        front = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", text, re.DOTALL)
        if not front:
            continue
        block = front.group(1)
        # `exemplifies`, not `rule_ids`: SCHEMAS.md section 8 names it as the join key, and the
        # exemplar workflow accepts either a bracketed inline sequence or a block list. Reading
        # the wrong key finds nothing in every real exemplar, so the citation blocks come out
        # empty and the rulebook loses every link it had.
        repo = re.search(r"^repo:[ \t]*(.+?)[ \t]*$", block, re.MULTILINE)
        inline = re.search(r"^exemplifies:[ \t]*\[(.*?)\][ \t]*$", block, re.MULTILINE)
        if inline:
            rules = re.findall(r"[A-Za-z0-9:_-]+", inline.group(1))
        else:
            listed = re.search(r"^exemplifies:[ \t]*\n((?:[ \t]*-[ \t]*\S+\n?)+)",
                               block, re.MULTILINE)
            rules = re.findall(r"-[ \t]*(\S+)", listed.group(1)) if listed else []
        if not rules:
            continue
        label = repo.group(1).strip().strip("\"'") if repo else path.stem
        score_m = re.search(r"^score:[ \t]*(\d+)[ \t]*$", block, re.MULTILINE)
        score = int(score_m.group(1)) if score_m else 0
        for rule in rules:
            by_rule.setdefault(rule, []).append((-score, path.name, label))
    # Strongest first (score descending), then filename for determinism, CAPPED per rule:
    # applied to the real migrated corpus, uncapped one-bullet-per-exemplar rendering pushed
    # the rulebook past its own R05 sub-500-line cap (973 lines) and under the release-score
    # floor. Three strong citations serve the reader; sixteen serve nobody (the same
    # judgment the refinement input applies to evidence). The cap keeps the decoration
    # inside the constitution it decorates.
    return {rule: [(name, label) for _neg, name, label in sorted(set(items))[:MAX_PER_RULE]]
            for rule, items in by_rule.items()}


def build_block(rule: str, items, prefix: str) -> str:
    # One line, not one bullet per exemplar: the block's size is what broke R05.
    links = " · ".join(f"[{markdown_label(label)}]({exemplar_url(prefix, filename)})"
                       for filename, label in items)
    return "\n".join([BEGIN.format(rule=rule),
                       f"- Real-world examples: {links}",
                       END.format(rule=rule)])


def apply_blocks(text: str, blocks: dict):
    """`(text, applied, missing)` — citations written beneath each rule's `:site` anchor.

    A rule with no anchor is REPORTED rather than skipped quietly. Silence there is how the
    original bug hid: the helper found none of its markers, changed nothing, and still exited
    zero having announced the rules it applied.
    """
    applied, missing, removed = [], [], []

    # A rule that lost its last exemplar keeps its generated region otherwise, still linking to
    # exemplars that are no longer published — the rulebook then cites evidence that does not
    # exist, which is worse than citing none. Regions are keyed by rule, so a region with no
    # corresponding block is stale by construction.
    for found in set(re.findall(re.escape(BEGIN.split("{")[0]) + r"([A-Za-z0-9:_-]+) -->", text)):
        if found in blocks:
            continue
        stale = re.compile(re.escape(BEGIN.format(rule=found)) + r".*?"
                           + re.escape(END.format(rule=found)) + r"\n?", re.DOTALL)
        if stale.search(text):
            text = stale.sub("", text, count=1)
            removed.append(found)

    for rule, block in sorted(blocks.items()):
        anchor = ANCHOR.format(rule=rule)
        if anchor not in text:
            missing.append(rule)
            continue
        existing = re.compile(
            re.escape(anchor) + r"\n" + re.escape(BEGIN.format(rule=rule))
            + r".*?" + re.escape(END.format(rule=rule)),
            re.DOTALL)
        replacement = f"{anchor}\n{block}"
        if existing.search(text):
            # Replacement, never append: appending stacks a new block under the anchor on every
            # run, and each block being well-formed keeps the file looking correct as it grows.
            text = existing.sub(lambda _m, r=replacement: r, text, count=1)
        else:
            text = text.replace(anchor, replacement, 1)
        applied.append(rule)
    return text, applied, missing, sorted(removed)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Propose exemplar citations for the rulebook.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--rules-path", default=None)
    parser.add_argument("--exemplar-url-prefix", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    if not args.data_dir:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir)
    if not args.rules_path:
        refuse("rules-file-missing")
    rules_path = Path(args.rules_path)
    if not rules_path.is_file():
        refuse("rules-file-missing")
    try:
        rules_text = rules_path.read_text(encoding="utf-8")
    except OSError:
        refuse("rules-file-missing")

    prefix = resolve_prefix(args.exemplar_url_prefix)
    by_rule = read_exemplars(data_dir)

    if args.apply and by_rule is None:
        refuse("exemplar-corpus-missing")
    if args.apply and not by_rule:
        refuse("exemplar-corpus-empty")

    blocks = {rule: build_block(rule, items, prefix)
              for rule, items in sorted((by_rule or {}).items())}

    if not args.apply:
        print(json.dumps({"prefix": prefix, "rules": sorted(blocks),
                          "blocks": blocks}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    updated, applied, missing, removed = apply_blocks(rules_text, blocks)
    for rule in missing:
        print(f"  no `:site {rule}` anchor in {rules_path.name}; citations not written",
              file=sys.stderr)
    target = Path(args.out) if args.out else rules_path
    if updated == rules_text and target == rules_path:
        print(f"propose-rule-citations: {len(applied)} rule(s); {rules_path} already current")
        return 0
    target.write_text(updated, encoding="utf-8")
    print(f"propose-rule-citations: applied {len(applied)} rule(s) to {target}"
          + (f"; {len(removed)} stale region(s) removed" if removed else "")
          + (f"; {len(missing)} without an anchor" if missing else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
