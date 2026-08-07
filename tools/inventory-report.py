#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""§5.0 inventory report and counts-vs-disk check (AC-7's fourth sub-check, E7.4 / vibe-56).

§5.0 of the merge proposal is "the counts everything else derives from". It was written on
2026-07-18 and disk has moved in BOTH directions since:

  * categories that GREW — later stages shipped more than the inventory froze;
  * categories that are EMPTY — their artifacts belong to stage S8, which has not run.

So a literal equality check over every row cannot pass today for reasons no release can fix,
and a check that cannot pass is not a gate. This module therefore reports every §5.0 category
against disk and **fails `--check` on any category whose §5.0 figure is reachable today**,
while categories whose figure describes unshipped S8 work are reported with their target and
their owning stage, and are asserted to be EMPTY (their honest current value) rather than
waved through. When S8 ships, those rows move to `EXACT` by editing this table — the same
"an entry is a reviewed claim" discipline the mirror and sweep tables use.

Growth rows are asserted as `>=` their §5.0 figure with the drift printed, because a suite
that shipped more commands than the 2026-07-18 plan predicted is not a release defect; a
suite that LOST one is.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

EXACT, ATLEAST, PENDING_S8, RECONCILED = ("exact", "at-least", "pending-S8", "reconciled")

#: SS5.0's 24 auditor-unit workflows as two EXPLICIT, DISJOINT name sets.
#:
#: Counting was not enough. Targets that merely SUM to 24 let a required workflow vanish and be
#: replaced: an unrelated `auditor/**/*.yml` kept the pipeline count at 18, and a site workflow
#: present in both accepted homes collapsed to one under an existential name test. Both rows now
#: assert membership of a named set, so identity — not arithmetic — is what is enforced.
#:
#: Cross-pinned to tests/test_auditor_workflows.py:EXPECTED (the lint's own required set), the
#: way MIRROR and RETIRED are pinned; tests/test_inventory_rows.py holds the two identical.
PIPELINE_WORKFLOWS = (
    "auditor-audit", "auditor-batch-processor", "auditor-case-study", "auditor-cite-exemplars",
    "auditor-classify", "auditor-contribute", "auditor-daily-report", "auditor-discover",
    "auditor-docs-diff", "auditor-exemplar", "auditor-integration-test", "auditor-refine-rules",
    "auditor-render-dashboard", "auditor-repo-report", "auditor-rule-review",
    "auditor-suppressions", "auditor-track", "auditor-vocab-drift",
)
#: The six site/release names (E8.4's five + E7.4's early release gate).
SITE_RELEASE_WORKFLOWS = ("deploy-site", "self-check", "site-preview", "site-preview-cleanup",
                          "site-validate", "pre-release-quality-gate")

# The partition claim, asserted at import rather than asserted in prose.
assert not set(PIPELINE_WORKFLOWS) & set(SITE_RELEASE_WORKFLOWS), "auditor row sets overlap"
assert len(set(PIPELINE_WORKFLOWS) | set(SITE_RELEASE_WORKFLOWS)) == 24, "union is not SS5.0's 24"


#: The five E8.4 site builders, by exact name. The row requires this SET, not a count, so a
#: renamed builder yields -1 rather than passing as "still five files".
SITE_BUILDERS = frozenset((
    "vibe-build-case-studies-index", "vibe-build-docs", "vibe-build-reference-md",
    "vibe-build-site-report-pages", "vibe-build-vocab-data",
))


def _workflow_entries(d):
    """Every path under `d` that LOOKS like a workflow, valid or not.

    Deliberately unfiltered: the previous version dropped directories and empty files BEFORE
    anomaly detection, so an extra `sneaky.yml/` or a zero-byte file simply vanished from the
    census instead of reddening a row. Junk has to be SEEN to be rejected.
    """
    if not d.is_dir():
        return []
    return [f for ext in ("*.yml", "*.yaml") for f in d.rglob(ext)]


def _bad_entry(f, homes):
    """True when a workflow-shaped path is not a real workflow in an accepted home.

    GitHub runs workflows only from a workflow directory, so a file parked in
    `auditor/not-workflows/` is not part of the unit however correctly it is named.
    """
    # is_file() and stat() FOLLOW symlinks, so a symlink to any real file counted as a
    # workflow — including a link pointing outside the repo entirely. The unit must be made
    # of real files, so the link itself is the thing to test.
    return (f.parent not in homes or f.is_symlink()
            or not f.is_file() or f.stat().st_size == 0)


def _pipeline_count(r):
    """Required pipeline workflows present, or -1 on any structural anomaly under `auditor/`.

    -1 is never a legal target, so an anomaly reddens the row instead of being averaged away:
    a stray, misplaced, duplicated, empty or directory-shaped entry cannot substitute for a
    deleted required workflow.
    """
    home = r / "auditor" / "workflows"
    entries = _workflow_entries(r / "auditor")
    if any(_bad_entry(f, {home}) for f in entries):
        return -1
    stems = [f.stem for f in entries]
    if set(stems) - set(PIPELINE_WORKFLOWS) - set(SITE_RELEASE_WORKFLOWS):
        return -1
    # A SET loses multiplicity, so the same workflow twice (nested, or under both extensions)
    # collapsed into one and the unit carried more files than it claimed.
    if len(stems) != len(set(stems)):
        return -1
    return len(set(stems) & set(PIPELINE_WORKFLOWS))


def _site_count(r):
    """Site/release workflows present exactly once in an accepted home, or -1 on an anomaly.

    The reference keeps these under `.github/workflows/` and this repo may stage them under
    `auditor/workflows/`, so both homes are accepted — but only those two, and only once each.
    """
    homes = {r / ".github" / "workflows", r / "auditor" / "workflows"}
    seen = []
    for d in (r / ".github", r / "auditor"):
        for f in _workflow_entries(d):
            if f.stem not in SITE_RELEASE_WORKFLOWS:
                continue          # ci.yml and friends are not this row's business
            if _bad_entry(f, homes):
                return -1
            seen.append(f.stem)
    if len(seen) != len(set(seen)):
        return -1
    return len(set(seen))


ROWS = [
    ("Slash commands", 26, ATLEAST,
     lambda r: len([p for p in (r / "commands").glob("*.md")])),
    # The exact SET, not merely "the three named ones exist": a fourth user-invocable skill
    # is an inventory change §5.0 does not describe, so it must fail rather than be ignored.
    ("Workflow skills (user-invocable)", 3, EXACT,
     lambda r: len(_workflow_skills(r)) if _workflow_skills(r) == WORKFLOW_SKILLS else -1),
    ("Agents", 14, EXACT,
     lambda r: len(list((r / "agents").glob("*.md")))),
    ("Knowledge skills", 19, ATLEAST,
     lambda r: len(KNOWLEDGE_SKILLS & {d.name for d in (r / "skills").iterdir()
                                       if d.is_dir() and (d / "SKILL.md").is_file()})),
    # 8 in §5.0, 6 on disk: `codex-call` was delivered as scripts/codex-runner.mjs and
    # `append-history` as scripts/trend_engine.py (docs/disposition.yaml rows cc-suite:19 and
    # nlpm:16). The row asserts the 6 partials PLUS both reconciliation targets existing, so
    # losing either is still a failure.
    ("Shared partials", 8, RECONCILED,
     lambda r: len(list((r / "commands" / "shared").glob("*.md")))
     + _reconciled_partials(r)),
    ("Plugin hook registrations", 4, EXACT,
     lambda r: len(json.loads((r / "hooks" / "hooks.json").read_text()).get("hooks", {}))),
    # 8 in §5.0, of which 5 are the site-build tools of F10.3 — stage S8. The 3 shipped ones
    # (vibe-check, vibe-report, vibe-badge) are asserted exactly; the rest are the S8 row.
    # E8.4 (vibe-61) split this pair. The shipped-subset row previously counted EVERY file in
    # bin/, so five builders would have taken it from 3 to 8 and broken an exact row that is
    # meant to guard the shipped tools. It now counts only NON-builder files and stays EXACT 3;
    # the site-builders row graduates to EXACT 5 and asserts the exact filename set, because a
    # bare count would accept five wrongly-named files. Targets still sum to 8, and both
    # counters are file-only so a directory named `vibe-build-x` cannot satisfy either.
    ("Python bin tools (shipped subset)", 3, EXACT,
     lambda r: len([p for p in (r / "bin").iterdir()
                    if p.is_file() and p.name != "README.md"
                    and not p.name.startswith("vibe-build-")])),
    # Counting only KNOWN names would let a sixth `vibe-build-*` file land uncounted by BOTH rows
    # (the shipped-subset row excludes the prefix; this row would ignore the unknown name), so a
    # stray builder would be invisible to the inventory. Count every `vibe-build-*` FILE and
    # require the set to equal SITE_BUILDERS exactly; anything else yields -1, which no target
    # matches — so an extra file, a missing one and a renamed one all fail.
    ("Python bin tools (site builders)", 5, EXACT,
     lambda r: (lambda found: len(found) if found == SITE_BUILDERS else -1)(
         {p.name for p in (r / "bin").iterdir()
          if p.is_file() and p.name.startswith("vibe-build-")})),
    ("Advisor templates", 6, EXACT,
     lambda r: len(list((r / "templates" / "advisors").glob("*.md")))),
    # SS5.0's 24 auditor-unit workflows, split by delivering item (vibe-59): E8.2 landed the 18
    # pipeline workflows (full glob, so a stray auditor YAML breaks the row); E8.4 owes the
    # site/release set. The site row counts the five outstanding names across BOTH possible homes
    # (the reference keeps site workflows under .github/workflows/); pre-release-quality-gate is
    # excluded because E7.4 delivered it before S8. Targets sum to 24 -- asserted by
    # tests/test_inventory_rows.py, which also proves 17/19 fail and the self-expiry fires.
    # The pipeline row counts auditor/**/*.yml MINUS the site/release names, and the site row
    # counts only those names. Without the exclusion the two sets overlap: deleting one pipeline
    # workflow while moving a site workflow into auditor/workflows/ left both rows green with 23
    # unique files. The sets are now disjoint and their union is the 24 SS5.0 names.
    ("Auditor pipeline workflows (E8.2)", 18, EXACT, _pipeline_count),
    # E8.4 (vibe-61) delivered its five; the sixth, pre-release-quality-gate, arrived early with
    # E7.4. All six now exist, so the row graduates from pending to EXACT and the two auditor rows
    # again sum to SS5.0's 24. Counting by NAME (not a glob) keeps a stray workflow from passing.
    ("Auditor site/release workflows (E8.4)", 6, EXACT, _site_count),
    ("Auditor helper scripts", 30, PENDING_S8,
     lambda r: len(list((r / "auditor").rglob("*.py")))),
]


#: §5.0's two skill kinds. Nothing in a SKILL.md declares which kind it is, so these are
#: DECLARED sets — reviewed claims, the same discipline KNOWN and MIRROR_EXPECTED use. Their
#: union must be exactly the registered skills, so a NEW skill of either kind fails until it
#: is classified here rather than silently joining a count.
WORKFLOW_SKILLS = {"issue2pr", "refine-proposal", "runs-stats"}
KNOWLEDGE_SKILLS = {
    "agent-design", "auditing", "conventions", "conventions-antigravity",
    "conventions-claude", "conventions-codex", "orchestration", "patterns", "roasting",
    "rules", "scoring", "security", "testing", "vibe-core", "vocabulary", "writing-agents",
    "writing-hooks", "writing-plugins", "writing-prompts", "writing-rules", "writing-skills",
}


def _registered_skills(root):
    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text())
    return {Path(entry).name for entry in manifest.get("skills", [])}


def _workflow_skills(root):
    """The workflow set, but only if the DECLARED partition still covers every skill."""
    registered = _registered_skills(root)
    if registered != WORKFLOW_SKILLS | KNOWLEDGE_SKILLS:
        return {"<unclassified skills: "
                + ",".join(sorted(registered ^ (WORKFLOW_SKILLS | KNOWLEDGE_SKILLS))) + ">"}
    return WORKFLOW_SKILLS & {d.name for d in (root / "skills").iterdir()
                              if d.is_dir() and (d / "SKILL.md").is_file()}


def _reconciled_partials(root):
    """Count the partials §5.0 lists that shipped as scripts — VALIDATED against the ledger.

    A hard-coded pair would be an assumption; docs/disposition.yaml is the ledger of record,
    so the delivered target is read from it and must exist on disk.
    """
    ledger = (root / "docs" / "disposition.yaml").read_text(encoding="utf-8")
    count = 0
    for partial, delivered in (("commands/shared/codex-call.md", "scripts/codex-runner.mjs"),
                               ("commands/shared/append-history.md",
                                "scripts/trend_engine.py")):
        if partial in ledger and delivered in ledger and (root / delivered).is_file():
            count += 1
    return count


def measure(root):
    out = []
    for label, target, rule, counter in ROWS:
        try:
            actual = counter(root)
        except (OSError, ValueError, KeyError) as exc:
            out.append((label, target, rule, None, str(exc)))
            continue
        out.append((label, target, rule, actual, None))
    return out


def verdicts(rows):
    """(label, ok, note) per row — the check's whole judgment."""
    for label, target, rule, actual, err in rows:
        if err is not None:
            yield label, False, f"uncountable: {err}"
        elif rule == EXACT:
            yield label, actual == target, f"{actual} (§5.0: {target}, exact)"
        elif rule == ATLEAST:
            yield label, actual >= target, (f"{actual} (§5.0: {target}, at-least"
                                            f"{f'; +{actual - target} since' if actual > target else ''})")
        elif rule == RECONCILED:
            yield label, actual >= target, (f"{actual} incl. reconciliation targets "
                                            f"(§5.0: {target})")
        else:   # PENDING_S8 — the honest current value is zero until stage S8 ships
            yield label, actual == 0, f"{actual} (§5.0 target {target}; pending S8)"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(REPO_ROOT))
    parser.add_argument("--check", action="store_true",
                        help="exit nonzero on any row whose rule is violated")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    rows = measure(root)
    bad = 0
    print("§5.0 inventory vs disk")
    for label, ok, note in verdicts(rows):
        print(f"  {'ok ' if ok else 'FAIL'} {label}: {note}")
        if not ok:
            bad += 1
    if args.check:
        print(f"inventory-report: {bad} row(s) violate their rule")
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
