#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Deterministic consistency engine for /vibe-suite:check (STAGED DRAFT — place as
scripts/check_engine.py after the plan verify clears).

The engine owns the mechanical classes and the composition; the checker agent owns the two
judgment classes and feeds them back via --judgment. Mechanical classes:

  reference-integrity, four reportable directions (F4.3):
    command-partial     a command's reference to a shared partial resolves
    agent-skills        an agent's `skills:` entry resolves to skills/<name>/SKILL.md
    hook-script         a hooks.json command's ${CLAUDE_PLUGIN_ROOT}/ path resolves
    claude-md-listing   a CLAUDE.md list item that is path-shaped resolves
  orphan                a non-root component (skill, agent, shared partial, script) with
                        zero inbound edges — per commands/shared/plugin-discover.md's map;
                        command→agent edges feed THIS computation only and are never a
                        reportable direction; manifest-claims are F4.4's, not checked here
  r51-drift             deprecated registry terms, only under the vocabulary skill's stated
                        preconditions (rule_overrides.R51.enabled + vocabulary_skill with a
                        registry.yaml)

Refusals (exit 2): bad root; fewer than two artifacts ("check: consistency needs >=2
artifacts; found <n>"); unreadable/unknown-class --judgment file.

Output (stdout JSON, deterministic ordering, byte-identical across runs):
  {"verdict": "CLEAN" | "<N> issues", "issues": [...], "checked": {...}}
Composition: issues = mechanical + judgment (file order); CLEAN iff the composed list is
empty; N == len(issues) exactly.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

JUDGMENT_CLASSES = {"behavioral-contradiction", "terminology-drift"}
DIRECTION_ORDER = ["command-partial", "agent-skills", "hook-script", "claude-md-listing"]
CLASS_ORDER = {"reference-integrity": 0, "orphan": 1, "r51-drift": 2,
               "behavioral-contradiction": 3, "terminology-drift": 3}

MD_LINK = re.compile(r"\]\(([^)\s]+)\)")
PATH_SHAPED = re.compile(r".+/.+|.+\.(md|json|sh|py|mjs|yaml|toml)$")
LIST_ITEM = re.compile(r"^\s*[-*]\s+(.+?)\s*$")


def fail(msg):
    print(f"check: {msg}", file=sys.stderr)
    return 2


def read_text(path):
    return path.read_text(encoding="utf-8", errors="replace")


def frontmatter_fields(text):
    """Minimal `key: value` frontmatter read (skills:/name: lines are all this needs)."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return {}
    fields = {}
    for line in lines[1:]:
        if line == "---":
            break
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    return fields


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


def check_mechanical(root, arts, config):
    issues, edges = [], []   # edges: (source_rel, target_rel) inbound map input

    # command-partial (reportable) + command-agent (orphan input only)
    for rel in arts["command"]:
        body = read_text(root / rel)
        base = (root / rel).parent
        for target in MD_LINK.findall(body):
            if target.startswith(("http:", "https:", "#")):
                continue
            resolved = (base / target).resolve()
            try:
                target_rel = resolved.relative_to(root.resolve()).as_posix()
            except ValueError:
                continue
            if re.fullmatch(r"commands/shared/[^/]+\.md", target_rel):
                if resolved.is_file():
                    edges.append((rel, target_rel))
                else:
                    issues.append({"class": "reference-integrity",
                                   "direction": "command-partial", "source": rel,
                                   "target": target_rel,
                                   "detail": "referenced shared partial does not exist"})
            elif re.fullmatch(r"agents/[^/]+\.md", target_rel) and resolved.is_file():
                edges.append((rel, target_rel))   # orphan input only, never reported

    # agent-skills (reportable) + agent→skill edges
    for rel in arts["agent"]:
        fields = frontmatter_fields(read_text(root / rel))
        for name in [s.strip() for s in fields.get("skills", "").split(",") if s.strip()]:
            target_rel = f"skills/{name}/SKILL.md"
            if (root / target_rel).is_file():
                edges.append((rel, target_rel))
            else:
                issues.append({"class": "reference-integrity",
                               "direction": "agent-skills", "source": rel,
                               "target": target_rel,
                               "detail": "skills: entry resolves to no SKILL.md"})

    # hook-script (reportable)
    for rel in arts["hook-config"]:
        try:
            data = json.loads(read_text(root / rel))
        except ValueError:
            continue   # malformed hook config is F4.4/frontmatter territory, not ours
        blob = json.dumps(data)
        for m in re.finditer(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"']+)", blob):
            target_rel = m.group(1)
            if (root / target_rel).is_file():
                edges.append((rel, target_rel))
            else:
                issues.append({"class": "reference-integrity",
                               "direction": "hook-script", "source": rel,
                               "target": target_rel,
                               "detail": "hook command names a script that does not exist"})

    # claude-md-listing (reportable; the partial's gap — grammar per the worksheet)
    for rel in arts["claude-md"]:
        for line in read_text(root / rel).splitlines():
            m = LIST_ITEM.match(line)
            if not m:
                continue
            item = m.group(1).strip().strip("`")
            if not PATH_SHAPED.fullmatch(item):
                continue
            if (root / item).exists():
                edges.append((rel, item))
            else:
                issues.append({"class": "reference-integrity",
                               "direction": "claude-md-listing", "source": rel,
                               "target": item, "detail": "listed path does not resolve"})

    # orphans: non-root components with zero inbound edges
    inbound = {t for _, t in edges}
    for kind in ("skill", "agent", "partial", "script"):
        for rel in arts[kind]:
            if rel not in inbound:
                issues.append({"class": "orphan", "source": rel,
                               "detail": "zero inbound reference edges"})

    # r51-drift under the stated preconditions
    deprecated = r51_deprecated_terms(root, config)
    if deprecated:
        scan = [r for k in ("command", "agent", "skill", "partial", "claude-md")
                for r in arts[k]]
        for rel in scan:
            body = read_text(root / rel).lower()
            for term, canonical in sorted(deprecated.items()):
                n = len(re.findall(rf"\b{re.escape(term)}\b", body))
                if n:
                    issues.append({"class": "r51-drift", "source": rel,
                                   "detail": f"deprecated term '{term}' (canonical: "
                                             f"'{canonical}'), {n} occurrence"
                                             + ("s" if n > 1 else "")})
    return issues


def r51_deprecated_terms(root, config_path):
    """{deprecated_term: canonical} when R51's preconditions hold, else {}."""
    cfg = config_path if config_path else root / ".vibe-suite.md"
    if not cfg.is_file():
        return {}
    text = read_text(cfg)
    if not re.search(r"R51:\s*$|R51:\s*\{", text, re.M):
        enabled = re.search(r"R51:(?:.|\n)*?enabled:\s*true", text)
    else:
        enabled = re.search(r"enabled:\s*true", text)
    vocab = re.search(r"vocabulary_skill:\s*(\S+)", text)
    if not (enabled and vocab):
        return {}
    registry = root / vocab.group(1) / "registry.yaml"
    if not registry.is_file():
        return {}
    terms, canonical = {}, None
    for line in read_text(registry).splitlines():
        m = re.match(r"^\s+canonical:\s*(\S+)", line)
        if m:
            canonical = m.group(1)
        m = re.match(r"^\s+-\s+(\S+)", line)
        if m and canonical:
            terms[m.group(1)] = canonical
    return terms


def sort_key(issue):
    return (CLASS_ORDER.get(issue["class"], 9),
            DIRECTION_ORDER.index(issue["direction"])
            if issue.get("direction") in DIRECTION_ORDER else 9,
            issue.get("source", ""), issue.get("target", ""))


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

    config = Path(args.config) if args.config else None
    issues = check_mechanical(root, arts, config)
    issues.sort(key=sort_key)

    if args.judgment:
        jpath = Path(args.judgment)
        if not jpath.is_file():
            return fail(f"judgment file {args.judgment!r} does not exist")
        try:
            judgment = json.loads(read_text(jpath))
        except ValueError as err:
            return fail(f"judgment file does not parse: {err}")
        if not isinstance(judgment, list):
            return fail("judgment file must be a JSON list")
        for finding in judgment:
            if finding.get("class") not in JUDGMENT_CLASSES:
                return fail(f"unknown judgment class {finding.get('class')!r}")
        issues.extend(judgment)   # file order, after the mechanical block

    verdict = "CLEAN" if not issues else f"{len(issues)} issues"
    json.dump({"verdict": verdict, "issues": issues,
               "checked": {k: len(v) for k, v in sorted(arts.items())}},
              sys.stdout, indent=2, sort_keys=False)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
