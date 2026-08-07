#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Render the cross-repository audit dashboard.

    render-dashboard.py --data-dir DIR [--out DIR] [--since YYYY-MM-DD] [--generated-at ISO]

Aggregates every repo's findings, vocabulary advisories and events into one page: an HTML
dashboard, a JSON sidecar carrying the same data, the assets and vendored graph bundle beside
them so it opens under `file://`, and the rule documentation the dashboard's rule badges link
into.

MALFORMED LINES ARE REPORTED, NOT SWALLOWED. A truncated write leaves a half-line in a `.jsonl`
ledger, which is normal under concurrent appends. Skipping it silently makes the dashboard
under-report — it shows a smaller number with the same confident styling as a correct one, and
nothing on the page says a line was dropped. So the parser returns `(records, malformed)` as a
pair and the count reaches the sidecar. The pair is the point: a count carried as an attribute
on a list subclass is erased by the first `[r for r in records if ...]`, which is exactly what
`--since` filtering does, so the telemetry would vanish precisely when records are being
dropped for a second reason.

DOCS ARE RENDERED HERE, NOT DELEGATED TO `bin/vibe-build-docs`. That builder requires
`--corpus` and emits VitePress Markdown for the public site; this needs standalone HTML the
report can open offline. Shelling out to it produces `docs/index.md` where the dashboard's
badges link to `docs/index.html`, so every rule badge silently 404s.

AGGREGATION IS TOTALLY ORDERED. `Counter.most_common` breaks ties by insertion order, so two
rules with equal counts swap places when the findings file is merely reordered — the dashboard
then differs between runs over identical data, and a reviewer diffing two artifacts sees noise.
Every ranking here breaks ties on the identifier.

Fail-closed on resources: a missing template or asset directory is a refusal, not a warning. The
alternative is publishing a dashboard that renders as unstyled text or literal braces.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = ROOT / "templates" / "report"
RULES_SKILL = ROOT / "skills" / "rules" / "SKILL.md"
SCORING_SKILL = ROOT / "skills" / "scoring" / "SKILL.md"
VOCAB_SKILL = ROOT / "skills" / "vocabulary" / "SKILL.md"

#: Ranking caps. Named because they are the difference between a dashboard and a data dump.
TOP_RULES = 25
TOP_TERMS = 60


def refuse(reason: str) -> None:
    print(f"REFUSE:render-dashboard:{reason}", file=sys.stderr)
    raise SystemExit(1)


def read_jsonl(path: Path):
    """`(records, malformed_count)`.

    A pair rather than a decorated list: see the module docstring. Callers that filter the
    records keep the count because it was never attached to them.
    """
    if not path.exists():
        return [], 0
    records, malformed = [], 0
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            malformed += 1
            print(f"WARN {path}:{lineno} malformed JSON: {exc}", file=sys.stderr)
    return records, malformed


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def filter_since(records, since, field="timestamp"):
    """Drop records older than `since`, and report how many were dropped.

    The drop count is returned rather than inferred by the caller: `len(before) - len(after)`
    conflates "filtered by date" with "unparseable", and those two need separate rows on the
    page — one is the user's own request, the other is data loss.
    """
    if not since:
        return records, 0
    kept = [r for r in records if str(r.get(field, "")) >= since]
    return kept, len(records) - len(kept)


def build_repo_table(findings, advisories, registry):
    """One row per repository: registry state plus its finding and drift counts."""
    by_repo_findings = defaultdict(list)
    for finding in findings:
        by_repo_findings[finding.get("repo", "?")].append(finding)
    by_repo_advisories = defaultdict(list)
    for advisory in advisories:
        by_repo_advisories[advisory.get("repo", "?")].append(advisory)

    repos = registry.get("repos", {}) if isinstance(registry, dict) else {}
    if not isinstance(repos, dict):
        repos = {}

    # Registry order first, then repos seen only in findings. A repo with findings but no
    # registry entry is a real state (discovery raced the audit) and must not vanish.
    ordered = list(repos)
    ordered += sorted(r for r in by_repo_findings if r not in repos)

    rows = []
    for repo in ordered:
        info = repos.get(repo) if isinstance(repos.get(repo), dict) else {}
        repo_findings = by_repo_findings.get(repo, [])
        repo_advisories = by_repo_advisories.get(repo, [])
        rows.append({
            "repo": repo,
            "status": info.get("status", "unknown"),
            "stars": info.get("stars"),
            "score": info.get("score"),
            "security": info.get("security"),
            "total_findings": len(repo_findings),
            "high_findings": sum(1 for f in repo_findings if f.get("confidence") == "high"),
            "medium_findings": sum(1 for f in repo_findings if f.get("confidence") == "medium"),
            "vocab_drift_count": len(repo_advisories),
            "vocab_drift_high": sum(1 for a in repo_advisories if a.get("confidence") == "high"),
        })
    rows.sort(key=lambda r: (-r["total_findings"], r["repo"]))
    return rows


def build_rule_distribution(findings):
    """Most-cited rules, with how many repositories each reaches.

    `repos_affected` is the interesting number: a rule firing 200 times in one repository is
    that repository's problem, whereas one firing 20 times across 20 repositories is the
    corpus's problem, and a count alone cannot tell those apart.
    """
    counts = Counter()
    repos_per_rule = defaultdict(set)
    for finding in findings:
        rule = finding.get("rule_id") or "UNCLASSIFIED"
        counts[rule] += 1
        repos_per_rule[rule].add(finding.get("repo", "?"))
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_RULES]
    return [{"rule_id": rule, "total": total, "repos_affected": len(repos_per_rule[rule])}
            for rule, total in ranked]


def build_drift_network(advisories):
    """Terms as nodes, co-occurrence within one advisory's cluster as edges.

    Edge weight is the number of DISTINCT repositories sharing the pair, not the number of
    advisories: one noisy repository re-reporting the same cluster nightly would otherwise
    dominate the graph and hide drift that genuinely spans the corpus.
    """
    term_freq = Counter()
    term_repos = defaultdict(set)
    pair_repos = defaultdict(set)

    for advisory in advisories:
        repo = advisory.get("repo", "?")
        raw = advisory.get("terms")
        terms = sorted({str(t) for t in raw}) if isinstance(raw, list) else []
        for term in terms:
            term_freq[term] += 1
            term_repos[term].add(repo)
        for i, left in enumerate(terms):
            for right in terms[i + 1:]:
                pair_repos[(left, right)].add(repo)

    ranked = sorted(term_freq.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_TERMS]
    nodes = [{"id": t, "label": t, "freq": c, "repos": sorted(term_repos[t])} for t, c in ranked]
    keep = {n["id"] for n in nodes}
    edges = [{"source": a, "target": b, "weight": len(repos), "repos": sorted(repos)}
             for (a, b), repos in pair_repos.items() if a in keep and b in keep]
    edges.sort(key=lambda e: (-e["weight"], e["source"], e["target"]))
    return {"nodes": nodes, "edges": edges}


def build_activity_timeline(events):
    """Per-day event counts. Days with no events are absent rather than zero-filled."""
    by_day = defaultdict(Counter)
    for event in events:
        timestamp = str(event.get("timestamp", ""))
        if len(timestamp) < 10:
            continue
        by_day[timestamp[:10]][event.get("event", "?")] += 1
    return [{"day": day, "counts": dict(sorted(by_day[day].items()))} for day in sorted(by_day)]


def build_summary(findings, advisories, rows):
    return {
        "total_repos": len(rows),
        "total_findings": len(findings),
        "high_findings": sum(1 for f in findings if f.get("confidence") == "high"),
        "total_advisories": len(advisories),
        "high_advisories": sum(1 for a in advisories if a.get("confidence") == "high"),
        "repos_with_drift": sum(1 for r in rows if r["vocab_drift_count"]),
        "repos_blocked": sum(1 for r in rows if str(r.get("security") or "").upper() == "BLOCKED"),
    }


def section(markdown: str, heading: str) -> str:
    """The body of one `## <heading>` section, up to the next `## `.

    Matched on the heading PREFIX, case-insensitively, so that "Vocabulary Discipline (opt-in)"
    survives a change to the parenthetical and "Score Bands" survives being retitled "Score
    bands". Capitalization and parentheticals are editorial; the section is the contract. An
    exact match would turn either edit into a silently blank section on the published page,
    which is the one outcome nobody reviewing that edit would think to check.
    """
    pattern = re.compile(r"^## " + re.escape(heading) + r".*?$(.*?)(?=^## |\Z)",
                         re.MULTILINE | re.DOTALL | re.IGNORECASE)
    found = pattern.search(markdown)
    return found.group(1).strip() if found else ""


def markdown_to_html(text: str) -> str:
    """Enough Markdown for the rule sections: escaping, inline code, bold, and list items.

    Deliberately not a general converter. The input is one known file in a known house style,
    and a partial converter that is honest about its scope beats a general one that silently
    mangles a construct nobody tested.
    """
    if not text:
        return '<p class="empty">Not available in this build.</p>'
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        escaped = [inline(ln) for ln in lines]
        if all(ln.startswith(("- ", "* ")) for ln in lines):
            items = "".join(f"<li>{ln[2:].strip()}</li>" for ln in escaped)
            out.append(f"<ul>{items}</ul>")
        elif lines[0].startswith("### "):
            out.append(f"<h3>{escaped[0][4:].strip()}</h3>")
            if escaped[1:]:
                out.append("<p>" + " ".join(escaped[1:]) + "</p>")
        else:
            out.append("<p>" + " ".join(escaped) + "</p>")
    return "\n".join(out)


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)


def read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def render_docs(out_dir: Path, generated_at: str) -> Path:
    """`docs/index.html` — the page the dashboard's rule badges link into.

    Sourced from the shipped skills rather than from a separate copy, so the documentation a
    report links to cannot drift from the rules the auditor actually applied. SCORING and DRIFT
    come from the scoring and vocabulary skills: the template needs seven sections and the rules
    skill holds five of them.
    """
    template_path = TEMPLATE_DIR / "docs" / "index.html"
    if not template_path.is_file():
        refuse("docs-template-missing")

    rules = read_optional(RULES_SKILL)
    artifact_types = "\n\n".join(
        f"### {name}\n\n{section(rules, name)}"
        for name in ("Skills", "Agents", "Commands", "Shared Partials", "Rules", "Hooks",
                     "Memory File", "Prompts", "Orchestration", "Plugins")
        if section(rules, name))

    values = {
        "GENERATED_AT": generated_at,
        "PRINCIPLES": markdown_to_html(section(rules, "Universal")),
        "RULES": markdown_to_html(rules.split("## ", 1)[0] if rules else ""),
        "ARTIFACT_TYPES": markdown_to_html(artifact_types),
        "VOCAB": markdown_to_html(section(rules, "Vocabulary Discipline")),
        "WARRANT": markdown_to_html(section(rules, "Warrant Tags")),
        "SCORING": markdown_to_html(section(read_optional(SCORING_SKILL), "Score Bands")),
        "DRIFT": markdown_to_html(section(read_optional(VOCAB_SKILL), "Drift detection")),
    }

    html = template_path.read_text(encoding="utf-8")
    for key, value in values.items():
        html = html.replace("{{" + key + "}}", value)

    target = out_dir / "docs" / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def copy_resource(name: str, destination: Path) -> None:
    source = TEMPLATE_DIR / name
    if not source.is_dir():
        refuse(f"{name}-missing")
    if destination.is_symlink() or destination.is_file():
        destination.unlink()
    elif destination.is_dir():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def render(data: dict, out_dir: Path) -> Path:
    template_path = TEMPLATE_DIR / "dashboard.html"
    if not template_path.is_file():
        refuse("dashboard-template-missing")

    out_dir.mkdir(parents=True, exist_ok=True)
    data.setdefault("schema_version", 1)

    (out_dir / "dashboard.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    copy_resource("assets", out_dir / "assets")
    copy_resource("vendor", out_dir / "vendor")

    # `</` is split so a repository or term literally containing `</script>` cannot close the
    # inline data block and have the remainder of the payload parsed as markup.
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).replace("</", "<\\/")
    html = (template_path.read_text(encoding="utf-8")
            .replace("{{GENERATED_AT}}", data["generated_at"])
            .replace("{{DATA_JSON}}", payload))

    target = out_dir / "dashboard.html"
    target.write_text(html, encoding="utf-8")
    render_docs(out_dir, data["generated_at"])
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the cross-repository audit dashboard.")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--out", default=None, help="default <data-dir>/reports")
    parser.add_argument("--since", default=None, help="ISO date; drop older records")
    parser.add_argument("--generated-at", default=None,
                        help="ISO-8601 stamp; default now (UTC). Set it to make output reproducible.")
    args = parser.parse_args(argv)

    if not args.data_dir:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        refuse("data-dir-missing")

    # SCHEMAS.md section 1: the canonical ledgers live under `ledgers/`, and every workflow
    # writes them there. Reading root-level or `logs/` finds nothing, and "nothing" renders as
    # a complete, well-formed dashboard reporting zero of everything — the failure this whole
    # helper is supposed to make visible.
    findings, bad_findings = read_jsonl(data_dir / "ledgers" / "findings.jsonl")
    advisories, bad_advisories = read_jsonl(data_dir / "ledgers" / "vocab-advisories.jsonl")
    events, bad_events = read_jsonl(data_dir / "ledgers" / "events.jsonl")
    registry = read_json(data_dir / "registry" / "repos.json", {})

    findings, aged_findings = filter_since(findings, args.since)
    advisories, aged_advisories = filter_since(advisories, args.since)
    events, aged_events = filter_since(events, args.since)

    rows = build_repo_table(findings, advisories, registry)
    data = {
        "generated_at": args.generated_at or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "since": args.since,
        "summary": build_summary(findings, advisories, rows),
        "repo_rows": rows,
        "rule_distribution": build_rule_distribution(findings),
        "drift_network": build_drift_network(advisories),
        "activity_timeline": build_activity_timeline(events),
        # Two separate reasons a record is absent. Collapsing them into one number would let
        # data loss hide behind the operator's own --since.
        "input_health": {
            "malformed_lines": {"findings": bad_findings, "vocab_advisories": bad_advisories,
                                "events": bad_events},
            "filtered_by_since": {"findings": aged_findings, "vocab_advisories": aged_advisories,
                                  "events": aged_events},
        },
    }

    target = render(data, Path(args.out) if args.out else data_dir / "reports")
    summary = data["summary"]
    print(f"Wrote {target}")
    print(f"  Repos: {summary['total_repos']}")
    print(f"  Findings: {summary['total_findings']} ({summary['high_findings']} high)")
    print(f"  Advisories: {summary['total_advisories']} ({summary['high_advisories']} high)")
    total_malformed = bad_findings + bad_advisories + bad_events
    if total_malformed:
        print(f"  Malformed input lines skipped: {total_malformed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
