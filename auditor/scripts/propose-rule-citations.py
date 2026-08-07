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

BEGIN = "<!-- vibe-suite-auditor-citations-begin: {rule} -->"
END = "<!-- vibe-suite-auditor-citations-end: {rule} -->"
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
        rules = re.search(r"^rule_ids:[ \t]*\[(.*?)\][ \t]*$", block, re.MULTILINE)
        repo = re.search(r"^repo:[ \t]*(.+?)[ \t]*$", block, re.MULTILINE)
        if not rules:
            continue
        label = repo.group(1).strip().strip("\"'") if repo else path.stem
        for rule in re.findall(r"[A-Za-z0-9:_-]+", rules.group(1)):
            by_rule.setdefault(rule, []).append((path.name, label))
    # Sorted per rule so two runs over the same corpus emit identical blocks.
    return {rule: sorted(set(items)) for rule, items in by_rule.items()}


def build_block(rule: str, items, prefix: str) -> str:
    lines = [BEGIN.format(rule=rule)]
    for filename, label in items:
        lines.append(f"- [{markdown_label(label)}]({exemplar_url(prefix, filename)})")
    lines.append(END.format(rule=rule))
    return "\n".join(lines)


def apply_blocks(text: str, blocks: dict) -> str:
    """Replace each rule's existing marker pair, or leave the text alone if it has none."""
    for rule, block in blocks.items():
        pattern = re.compile(
            re.escape(BEGIN.format(rule=rule)) + r".*?" + re.escape(END.format(rule=rule)),
            re.DOTALL)
        if pattern.search(text):
            # Replacement, never append: appending stacks a new block under every previous one
            # on each run, and each block being well-formed keeps the file looking correct.
            text = pattern.sub(lambda _m, b=block: b, text, count=1)
    return text


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

    updated = apply_blocks(rules_text, blocks)
    target = Path(args.out) if args.out else rules_path
    if updated == rules_text and target == rules_path:
        print(f"propose-rule-citations: {len(blocks)} rule(s); {rules_path} already current")
        return 0
    target.write_text(updated, encoding="utf-8")
    print(f"propose-rule-citations: applied {len(blocks)} rule(s) to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
