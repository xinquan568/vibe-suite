#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Reconstruct a findings sidecar from a legacy audit report.

    synthesize-sidecar.py --repo OWNER/NAME --report PATH [--out PATH]

Early audits produced only a Markdown report. The pipeline joins on the finding fingerprint,
so those audits are invisible to every downstream stage — outcomes, rule health, disagreements
— until their findings exist as records. This reads the report back and emits the sidecar.

DETERMINISM IS THE ENTIRE CONTRACT. The fingerprint is
`sha256("<repo>|<file>|<rule_id>|<pattern>|<line>")`, so `pattern` is part of a join key that
already exists in committed ledgers. If synthesis is rerun and any pattern comes out different,
the finding gets a new fingerprint, its recorded outcome no longer joins to it, and both the
old and new rows sit in the ledger looking equally valid. Nothing downstream can tell which is
current.

That makes two ordinary conveniences unusable here:

  * A pattern derived from `set(tokens)` — Python's set order varies with PYTHONHASHSEED, so
    the same report yields different fingerprints on different machines, and re-running on the
    same machine hides it.
  * Anything derived from the clock. `datetime.now()` in a field that feeds the digest re-keys
    every finding on every run.

So token order is source order throughout, the inference table is an ordered tuple where the
first match wins, and no value in the digest comes from the environment. Rerunning over an
unchanged report must produce a byte-identical file, and there is a test that asserts it.

The inferred `pattern` is not the exact string the original auditor used — that string was
never recorded. It only has to be STABLE, since its role is to make the same finding hash to
the same value every time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

#: (regex, rule_id, pattern_slug) — an ORDERED tuple, first match wins, so specific entries
#: must precede general ones. Order is part of the output contract: reordering these rows
#: re-keys every finding they match.
RULE_INFERENCE = (
    (r"\bfrontmatter\b.*\bname\b|\bname\b.*\bparent dir", None, "name-matches-parent-dir"),
    (r"\bdescription\b.*\bmissing\b|\bmissing\b.*\bdescription\b", "R04", "description-missing"),
    (r"\btrigger\b|\bgeneric description\b", "R04", "generic-description"),
    (r"\bdescription\b.*\blength\b|\btoo long\b.*\bdescription\b", "R04", "description-length"),
    (r"\bbody\b.*\blength\b|\bover \d+ lines\b|\btoo long\b", "R05", "body-length"),
    (r"<example>|\bexample blocks?\b", "R06", "example-blocks-missing"),
    (r"\bcode examples?\b|\bno examples\b", "R06", "code-examples-missing"),
    (r"\bscope note\b|\bcross-references?\b", "R07", "scope-note-missing"),
    # R01, not R18: the shipped rulebook defines vague quantifiers as R01 (-2 each, cap
    # -20). A wrong id here is a wrong rule id in the FINGERPRINT, so the finding hashes
    # to a key nothing else joins to.
    (r"\bvague\b|\bquantifier", "R01", "vague-quantifier"),
    (r"\bvocab\w*\b.*\bdrift\b|\bterminology\b", "R51", "vocabulary-drift"),
    (r"\borphan\b|\bunreferenced\b", None, "orphan-artifact"),
)

#: Every id shape SCHEMAS.md allows — `rule_id` is "a namespaced rule identifier". Matching
#: only R## rewrote a legacy row declaring SEC-001 as UNCLASSIFIED, which CHANGES the
#: fingerprint: the digest is taken over the rule id, so the synthesized record would never
#: join the one the original audit recorded.
DECLARED_ID = re.compile(
    r"^(?:[a-z][a-z0-9]*:)?(?:R\d{1,2}|(?:SEC|BUG|CC)-[A-Za-z0-9_-]+|UNCLASSIFIED)$")

STOPWORDS = frozenset("""a an and are as at be but by for from has have in into is it its not
of on or that the their this to with without missing should must than then when which""".split())

#: SCHEMAS.md section 2 fixes `category` to the DEFECT class. A section heading names the
#: ARTIFACT type, which is a different axis entirely — emitting "skill" as a category produced
#: schema-invalid findings that the aggregation post-step then made DURABLE in the ledger.
#: Legacy reports carry no defect class, so everything synthesized from prose is nl_quality
#: unless the text says otherwise.
CATEGORY_FOR = (
    (r"\bsecurit|\bvulnerab|\binjection\b|\bsecret\b", "security"),
    (r"\bcrash\b|\bbug\b|\bincorrect\b|\bbroken\b", "bug"),
    (r"\bcross-?component\b|\borphan\b|\bunreferenced\b", "cross_component"),
)
DEFAULT_CATEGORY = "nl_quality"

SEVERITY_BY_PENALTY = ((-20, "high"), (-10, "medium"))


def refuse(reason: str) -> None:
    print(f"REFUSE:synthesize-sidecar:{reason}", file=sys.stderr)
    raise SystemExit(1)


def fingerprint(repo: str, finding: dict) -> str:
    """The same digest `compute-fingerprint.sh` produces, including jq's trailing newline.

    The newline is contractual, not incidental: dropping it yields a different, equally
    stable-looking fingerprint that would silently re-key every historical finding.
    """
    line = finding.get("line")
    payload = "|".join((
        repo,
        str(finding.get("file") or ""),
        str(finding.get("rule_id") or ""),
        str(finding.get("pattern") or ""),
        "null" if line is None or line is False else str(line),
    )) + "\n"
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def slugify(text: str, limit: int = 5) -> str:
    """A stable slug from the first significant words, IN SOURCE ORDER.

    Source order, never `set()` order: a set-derived slug varies with PYTHONHASHSEED, so the
    same report would fingerprint differently on two machines and re-running on one machine
    would never reveal it.
    """
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]
    return "-".join(words[:limit]) or "unclassified"


def infer_rule_and_pattern(text: str, declared_rule=None):
    for regex, rule_id, pattern in RULE_INFERENCE:
        if re.search(regex, text, re.IGNORECASE):
            return (declared_rule or rule_id), pattern
    return declared_rule, slugify(text)


def classify_category(text: str) -> str:
    """The DEFECT class, from the finding's own words."""
    for regex, category in CATEGORY_FOR:
        if re.search(regex, text, re.IGNORECASE):
            return category
    return DEFAULT_CATEGORY


def parse_penalty(text: str):
    found = re.search(r"-\s*(\d+)", text)
    return -int(found.group(1)) if found else None


def severity_for(penalty):
    if penalty is None:
        return "low"
    for threshold, name in SEVERITY_BY_PENALTY:
        if penalty <= threshold:
            return name
    return "low"


def split_cells(row: str):
    return [c.strip() for c in row.strip().strip("|").split("|")]


def parse_report(text: str):
    """Every finding the report describes, in document order.

    Two legacy shapes are supported because both were produced: a per-section table, and a
    per-finding `###` subsection. Document order is preserved so the output is stable.
    """
    findings = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            i += 1
            continue
        if line.startswith("### "):
            findings.append(parse_subsection(lines, i))
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[-:\s|]+\|$",
                                                                    lines[i + 1].strip()):
            header = [h.lower() for h in split_cells(line)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = dict(zip(header, split_cells(lines[i])))
                parsed = parse_row(row)
                if parsed:
                    findings.append(parsed)
                i += 1
            continue
        i += 1
    return [f for f in findings if f]


def first_of(row: dict, *names):
    for name in names:
        value = row.get(name)
        if value and value not in {"--", "-", "n/a"}:
            return value
    return None


def parse_row(row: dict):
    description = first_of(row, "issue", "description", "check", "finding", "detail")
    path = first_of(row, "file", "path", "artifact")
    if not description and not path:
        return None
    declared = first_of(row, "rule", "rule_id")
    declared = declared if declared and DECLARED_ID.match(declared) else None
    penalty = parse_penalty(first_of(row, "penalty", "score") or "")
    rule_id, pattern = infer_rule_and_pattern(description or path or "", declared)
    line_value = first_of(row, "line", "lineno")
    # ONE decision, used for both. Deciding the category from description+path and the
    # penalty-nulling from description alone let `security/README.md` come out
    # `category: security` WITH a penalty, which section 2 forbids.
    category = classify_category(f"{description or ''} {path or ''}")
    return {
        "category": category,
        # `rule_id` is required and non-null in section 4. An inference that found no rule is
        # UNCLASSIFIED — the value the renderers already use — not a null the schema forbids.
        "rule_id": rule_id or "UNCLASSIFIED",
        "file": path,
        "line": int(line_value) if line_value and str(line_value).isdigit() else None,
        "pattern": pattern,
        "description": description,
        # section 2: penalty is a negative int for nl_quality and NULL otherwise; and
        # `confidence: high` requires actively reproduced breakage, which synthesis from prose
        # never did — so these stay medium and carry no evidence, which is the reproduction
        # record a medium finding has not earned.
        "penalty": penalty if category == "nl_quality" else None,
        "severity": severity_for(penalty),
        "confidence": "medium",
        "evidence": None,
        "false_positive": False,
        "suggested_fix": None,
    }


def parse_subsection(lines, start):
    heading = lines[start][4:].strip()
    body = []
    for line in lines[start + 1:]:
        if line.startswith(("## ", "### ")):
            break
        body.append(line)
    blob = "\n".join(body)
    # The id is the leading TOKEN, however it is punctuated. Splitting on whitespace kept a
    # trailing colon, so `### R12: ...` stopped matching — a heading shape the previous parser
    # accepted, which means legacy findings were being re-keyed by my own fix.
    declared = DECLARED_ID.match(re.split(r"[\s:—–-]+$", heading.split()[0].rstrip(":—–"))[0]
                                 if heading.split() else "")
    path = re.search(r"\*\*(?:File|Path)\*\*:?\s*`?([^`\n]+?)`?\s*$", blob, re.MULTILINE)
    line_no = re.search(r"\*\*Line\*\*:?\s*(\d+)", blob)
    penalty = parse_penalty(blob)
    title = re.sub(r"^R\d{1,2}\s*[—:-]\s*", "", heading)
    category = classify_category(f"{title} {blob}")
    rule_id, pattern = infer_rule_and_pattern(f"{title} {blob}",
                                              declared.group(0) if declared else None)
    return {
        "category": category,
        # `rule_id` is required and non-null in section 4. An inference that found no rule is
        # UNCLASSIFIED — the value the renderers already use — not a null the schema forbids.
        "rule_id": rule_id or "UNCLASSIFIED",
        "file": path.group(1).strip() if path else None,
        "line": int(line_no.group(1)) if line_no else None,
        "pattern": pattern,
        "description": title,
        "penalty": penalty if category == "nl_quality" else None,
        "severity": severity_for(penalty),
        "confidence": "medium",
        "evidence": None,
        "false_positive": False,
        "suggested_fix": None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild a findings sidecar from a report.")
    parser.add_argument("--repo", required=False, default=None, help="owner/name")
    parser.add_argument("--report", required=False, default=None)
    parser.add_argument("--out", default=None, help="default <report stem>.findings.jsonl")
    args = parser.parse_args(argv)

    if not args.repo:
        refuse("repo-required")
    if "/" not in args.repo:
        refuse("repo-not-owner-name")
    if not args.report:
        refuse("report-required")
    report = Path(args.report)
    if not report.is_file():
        refuse("report-missing")

    findings = parse_report(report.read_text(encoding="utf-8"))
    # NO FINGERPRINT. Section 4 is explicit that the sidecar carries no timestamp, run id,
    # repo, commit sha or fingerprint — the aggregation post-step enriches each line before the
    # ledger append. Writing one here produces a record no real sidecar contains, and the
    # post-step then makes it durable.

    payload = "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n"
                      for f in findings)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"Wrote {out} ({len(findings)} finding(s))")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
