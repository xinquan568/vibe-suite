#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Render one repository's audit report.

    render-repo-report.py --repo OWNER/NAME --data-dir DIR [--out DIR] [--generated-at ISO]

Writes `<out>/<slug>.html` beside the dashboard, sharing its assets, vendored bundle and rule
documentation.

THE REPOSITORY IS `owner/name`, NEVER THE SLUG. The slug is a filename, and it is lossy: the
`owner/name` -> `owner-name` scheme cannot be reversed when either half contains a hyphen. A
caller that passes a slug here gets a report whose contents belong to some other repository, or
to none, and the page still renders with a plausible title. So the identifier is checked
against the registry and a report is refused rather than guessed.

THAT LOSSINESS IS ALSO A COLLISION. `a/b-c` and `a-b/c` both slug to `a-b-c`, so whichever
renders second silently overwrites the first and one repository's audit is published under
another's name. Nothing downstream can detect it — the file exists, parses, and reads plausibly.
It is checked against the whole registry on every run, not just when a collision is expected.

FAIL-CLOSED, per the specification: a missing registry or missing report resource refuses. The
caller must not swallow that failure. Publishing an audit while silently omitting its report
means the finding was made, recorded as delivered, and never actually shown to anyone.

The docs page is rendered here too rather than assumed. A report links every rule badge into
`docs/index.html`; when only this renderer runs — a single-repo re-audit, say — nothing else
would have produced that file and every badge on the page would dangle.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
# Aliased on purpose: main() binds a local `html` (the rendered page text), so the bare
# module name is unusable there (vibe-195).
from html import escape as html_escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE_DIR = ROOT / "templates" / "report"


def refuse(reason: str) -> None:
    print(f"REFUSE:render-repo-report:{reason}", file=sys.stderr)
    raise SystemExit(1)


def dashboard_module():
    """The dashboard renderer, imported for the resource and docs routines it already owns.

    Imported rather than duplicated: the helper set is a closed inventory of thirty names, so a
    shared module cannot be added, and a second copy of the docs renderer would drift from the
    first without anything failing.
    """
    spec = importlib.util.spec_from_file_location("_render_dashboard",
                                                  HERE / "render-dashboard.py")
    if spec is None or spec.loader is None:
        refuse("dashboard-helper-missing")
    module = importlib.util.module_from_spec(spec)
    # Importing normally drops a __pycache__ beside the helpers. That directory's contents are
    # a closed, asserted inventory of thirty names, so the cache is an undeclared entry that
    # fails the inventory check on any machine that has run this helper once. It is also
    # writable state inside a checkout the auditor commits from.
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def slug_for(repo: str) -> str:
    return repo.replace("/", "-")


def assert_no_slug_collision(repo: str, repos) -> None:
    target = slug_for(repo)
    clashing = sorted(other for other in repos if other != repo and slug_for(other) == target)
    if clashing:
        print(f"REFUSE:render-repo-report:slug-collision {repo} and {', '.join(clashing)} "
              f"both produce '{target}'", file=sys.stderr)
        raise SystemExit(1)


def build_data(repo, findings, advisories, info, generated_at):
    rules = Counter(f.get("rule_id") or "UNCLASSIFIED" for f in findings)
    return {
        "schema_version": 1,
        "project": repo,
        "generated_at": generated_at,
        "registry": {
            "status": info.get("status", "unknown"),
            "score": info.get("score"),
            "security": info.get("security"),
            "stars": info.get("stars"),
        },
        "summary": {
            "total_findings": len(findings),
            "high_findings": sum(1 for f in findings if f.get("confidence") == "high"),
            "medium_findings": sum(1 for f in findings if f.get("confidence") == "medium"),
            "total_advisories": len(advisories),
            "rules_cited": len(rules),
        },
        # Sorted for a stable diff between two runs over the same data.
        "rule_counts": [{"rule_id": rule, "total": total}
                        for rule, total in sorted(rules.items(), key=lambda kv: (-kv[1], kv[0]))],
        "findings": sorted(findings, key=lambda f: (str(f.get("file", "")),
                                                    int(f.get("line") or 0),
                                                    str(f.get("rule_id", "")))),
        "advisories": sorted(advisories, key=lambda a: str(a.get("terms", ""))),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render one repository's audit report.")
    parser.add_argument("--repo", default=None, help="owner/name — NOT the slug")
    parser.add_argument("--data-dir", default=os.environ.get("AUDITOR_DATA_DIR"))
    parser.add_argument("--out", default=None, help="default <data-dir>/reports")
    parser.add_argument("--generated-at", default=None,
                        help="ISO-8601 stamp; default now (UTC). Set it for reproducible output.")
    args = parser.parse_args(argv)

    if not args.repo:
        refuse("repo-required")
    if "/" not in args.repo:
        refuse(f"repo-not-owner-name {args.repo}")
    if not args.data_dir:
        refuse("data-dir-required")
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        refuse("data-dir-missing")

    registry_path = data_dir / "registry" / "repos.json"
    if not registry_path.is_file():
        refuse("registry-missing")
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        refuse("registry-unreadable")
    repos = registry.get("repos") if isinstance(registry, dict) else None
    if not isinstance(repos, dict):
        refuse("registry-malformed")
    if args.repo not in repos:
        refuse(f"repo-not-in-registry {args.repo}")
    assert_no_slug_collision(args.repo, repos)

    dashboard = dashboard_module()
    # `ledgers/`, per SCHEMAS.md section 1 — see the note in render-dashboard.py. A wrong path
    # here publishes a report saying the repository has no findings.
    all_findings, _ = dashboard.read_jsonl(data_dir / "ledgers" / "findings.jsonl")
    all_advisories, _ = dashboard.read_jsonl(data_dir / "ledgers" / "vocab-advisories.jsonl")
    findings = [f for f in all_findings if f.get("repo") == args.repo]
    advisories = [a for a in all_advisories if a.get("repo") == args.repo]

    info = repos.get(args.repo) if isinstance(repos.get(args.repo), dict) else {}
    generated_at = args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = build_data(args.repo, findings, advisories, info, generated_at)

    template_path = TEMPLATE_DIR / "repo-audit.html"
    if not template_path.is_file():
        refuse("repo-template-missing")

    out_dir = Path(args.out) if args.out else data_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    dashboard.copy_resource("assets", out_dir / "assets")
    dashboard.copy_resource("vendor", out_dir / "vendor")
    dashboard.render_docs(out_dir, generated_at)

    slug = slug_for(args.repo)
    (out_dir / f"{slug}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # `</` is split so a rule id or path containing `</script>` cannot close the data block and
    # have the rest of the payload parsed as markup.
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).replace("</", "<\\/")
    # {{PROJECT}} lands in markup context (<title>, <h1>); the repo name is external input.
    html = (template_path.read_text(encoding="utf-8")
            .replace("{{PROJECT}}", html_escape(args.repo))
            .replace("{{GENERATED_AT}}", generated_at)
            .replace("{{DATA_JSON}}", payload))

    target = out_dir / f"{slug}.html"
    target.write_text(html, encoding="utf-8")
    print(f"Wrote {target}")
    print(f"  Findings: {data['summary']['total_findings']} "
          f"({data['summary']['high_findings']} high)")
    print(f"  Advisories: {data['summary']['total_advisories']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
