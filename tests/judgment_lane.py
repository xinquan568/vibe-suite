#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The judgment lane's trusted half (vibe-229 / M35).

The weekly `judgment` jobs in `.github/workflows/self-check.yml` evaluate every `.vibe-test` spec with a Claude session.
That session follows the tester's *procedure* (`agents/tester.md`) in-session — the tester *subagent* cannot be shown to
be dispatchable on a CI runner — and it is **untrusted** from the moment its model step starts. Everything that decides
anything therefore lives here, and runs in a separate job, on a separate runner, from a clean checkout:

    plan       sort the corpus, drop specs whose artifact is missing, chunk into batches of three
    inventory  derive, per spec, the exact checks the model must answer (it cannot answer "zero checks, all passed")
    report     recompute the plan and lane 5, read each batch's archive IN MEMORY, validate it, render the report

Lane 5 — the deterministic score against `min_score` — is computed here with the tester's exact engine invocation and
is never asked of the model. The model judges lanes 1-4 only, in a schema this module owns and rejects any deviation
from. Archives are opened with `zipfile` and only the two expected members are read, capped, into memory: nothing is
ever extracted, because the pinned `actions/download-artifact` lets an interior-traversal member escape its target
directory (issue #339).

    python3 -I tests/judgment_lane.py plan      --root .
    python3 -I tests/judgment_lane.py inventory --root . --specs "a b c" --out judgment-in/inventory.json
    python3 -I tests/judgment_lane.py report    --root . --in DIR --plan-matrix JSON --out report.md
"""

import argparse
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

SPECS_DIR = ".vibe-test"
BATCH_SIZE = 3
#: The two members a batch archive may contribute. The workflow writes exactly these names; the reader reads nothing else.
BATCH_MEMBER = "batch.json"
MODEL_MEMBER = "model.txt"
MEMBER_CAP = 1 << 20

#: Section heading → (check-id prefix, lane, parser kind). Only these are evaluated (agents/tester.md:21-45).
EVALUATED = {
    "Frontmatter Valid": ("fm", 1, "bullets"),
    "Triggers On": ("trig+", 2, "bullets"),
    "Does Not Trigger On": ("trig-", 2, "bullets"),
    "Output Contains": ("out", 3, "bullets"),
    "Output Format": ("fmt", 3, "numbered"),
    "Handles Input": ("in", 3, "table"),
    "Follows Rules": ("rule", 4, "pairs"),
}
KNOWN_FRONTMATTER_KEYS = ("description", "argument-hint", "name", "model", "tools", "skills", "allowed-tools",
                          "disable-model-invocation", "license")
TOKEN_SHAPED = re.compile(r"(?:ghs_|ghp_|gho_|ghu_|ghr_|github_pat_)[A-Za-z0-9_]{8,}")
MODEL_ID = re.compile(r"^[A-Za-z0-9._:\[\]-]{1,80}$")
BOUNDED = 200

# --------------------------------------------------------------------------------------------------------------------
# the corpus
# --------------------------------------------------------------------------------------------------------------------


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    out = {}
    for line in (m.group(1).splitlines() if m else []):
        k, sep, v = line.partition(":")
        if sep:
            out[k.strip()] = v.strip().strip('"')
    return out


def spec_stems(root):
    """Every spec stem, **sorted** — discovery order is never trusted."""
    return sorted(p.name[:-len(".spec.md")] for p in (Path(root) / SPECS_DIR).glob("*.spec.md"))


def spec_meta(root, stem):
    text = (Path(root) / SPECS_DIR / f"{stem}.spec.md").read_text(encoding="utf-8")
    fm = frontmatter(text)
    artifact = fm.get("artifact", "")
    return {"stem": stem, "text": text, "artifact": artifact, "type": fm.get("type", ""),
            "min": int(fm.get("min_score", "80")), "missing": not (Path(root) / artifact).is_file()}


def plan(root):
    """The matrix payload: batch index and space-separated stems, nothing else."""
    stems = [s for s in spec_stems(root) if not spec_meta(root, s)["missing"]]
    chunks = [stems[i:i + BATCH_SIZE] for i in range(0, len(stems), BATCH_SIZE)]
    return {"include": [{"batch": k, "specs": " ".join(c)} for k, c in enumerate(chunks)]}


# --------------------------------------------------------------------------------------------------------------------
# inventory
# --------------------------------------------------------------------------------------------------------------------


def _sections(text):
    body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
    parts = re.split(r"^## (.+?)\s*$", body, flags=re.M)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


def _query(item):
    m = re.match(r'\s*"(.*?)"', item)
    return m.group(1) if m else item.strip()


def _candidate_keys(bullet):
    keys = []
    for k in re.findall(r"`([A-Za-z][A-Za-z0-9-]*)`", bullet):
        if k not in keys:
            keys.append(k)
    for k in KNOWN_FRONTMATTER_KEYS:
        if k not in keys and re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", bullet):
            keys.append(k)
    return keys


def inventory(text):
    """{"checks": [...], "unevaluated": [...]} — the exact set of checks a spec asks for."""
    checks, unevaluated = [], []
    for heading, body in _sections(text):
        if heading not in EVALUATED:
            unevaluated.append(heading)
            continue
        prefix, lane, how = EVALUATED[heading]
        if how == "bullets":
            items = [l.strip()[2:] for l in body.splitlines() if l.strip().startswith("- ")]
        elif how == "numbered":
            items = [re.sub(r"^\d+\.\s*", "", l.strip()) for l in body.splitlines() if re.match(r"\s*\d+\.\s", l)]
        elif how == "table":
            rows = [l.strip() for l in body.splitlines() if l.strip().startswith("|")]
            items = [r.strip("|").split("|")[0].strip() for r in rows[2:]]
        else:  # pairs: two fenced blocks per rule
            items = [f"pair {n + 1}" for n in range(body.count("```") // 4)]
        for n, item in enumerate(items, 1):
            check = {"id": f"{prefix}:{n}", "lane": lane, "section": heading}
            if prefix.startswith("trig"):
                check.update(kind="trig", text=_query(item), expected="YES" if prefix == "trig+" else "NO")
            elif prefix == "fm":
                check.update(kind="fm", text=item, keys=_candidate_keys(item))
            else:
                check.update(kind=prefix, text=item)
            checks.append(check)
    return {"checks": checks, "unevaluated": unevaluated}


# --------------------------------------------------------------------------------------------------------------------
# lane 5
# --------------------------------------------------------------------------------------------------------------------


def score(root, stems, engine=None):
    """Lane 5 with the tester's exact invocation (agents/tester.md:47-62): one record-framed stdin entry, `--root`,
    `files[0].score`. A missing artifact never reaches the engine; exit 2 and an empty result are that spec's error."""
    root = Path(root)
    engine = engine or [sys.executable, str(root / "scripts" / "score_engine.py")]
    out = {}
    for stem in stems:
        meta = spec_meta(root, stem)
        row = {"artifact": meta["artifact"], "min": meta["min"], "score": None, "error": None,
               "missing": meta["missing"]}
        if not meta["missing"]:
            record = f"{meta['type']}\x1f{meta['artifact']}\x00".encode("utf-8")
            r = subprocess.run([*engine, "--root", str(root)], input=record, capture_output=True)
            if r.returncode == 2:
                row["error"] = r.stderr.decode("utf-8", "replace").strip() or "score engine exited 2"
            elif r.returncode != 0:
                row["error"] = f"score engine exited {r.returncode}"
            else:
                try:
                    files = json.loads(r.stdout).get("files") or []
                except (ValueError, AttributeError):
                    files = None
                if not files:
                    row["error"] = "score engine returned no result"
                else:
                    row["score"] = files[0].get("score")
                    if not isinstance(row["score"], int):
                        row["score"], row["error"] = None, "score engine returned no numeric score"
        out[stem] = row
    return out


# --------------------------------------------------------------------------------------------------------------------
# reading archives — never extracting
# --------------------------------------------------------------------------------------------------------------------


def _read_member(zf, name):
    matches = [i for i in zf.infolist() if i.filename == name]
    if not matches:
        return None, None
    if len(matches) > 1:
        return None, f"duplicate member {name}"
    info = matches[0]
    if info.file_size > MEMBER_CAP:
        return None, f"{name} exceeds {MEMBER_CAP} bytes"
    with zf.open(info) as fh:
        data = fh.read(MEMBER_CAP + 1)
    if len(data) > MEMBER_CAP:
        return None, f"{name} exceeds {MEMBER_CAP} bytes"
    return data.decode("utf-8", "replace"), None


def read_batches(in_dir, batch_ids):
    """{k: {"present", "raw", "model", "error"}} — each `<k>.zip` opened and read in memory, two members at most."""
    out = {}
    for k in batch_ids:
        row = {"present": False, "raw": None, "model": None, "error": None}
        path = Path(in_dir) / f"{k}.zip"
        if path.is_file():
            row["present"] = True
            try:
                with zipfile.ZipFile(path) as zf:
                    raw, err = _read_member(zf, BATCH_MEMBER)
                    model, _ = _read_member(zf, MODEL_MEMBER)
            except (zipfile.BadZipFile, OSError, EOFError, NotImplementedError) as exc:
                raw, err, model = None, f"not a zip archive ({type(exc).__name__})", None
            if err:
                row["error"] = err
            elif raw is None:
                row["error"] = f"no {BATCH_MEMBER} in the archive"
            else:
                row["raw"] = raw
                try:
                    json.loads(raw)
                except ValueError:
                    row["error"] = f"{BATCH_MEMBER} is not valid JSON"
            if model is not None:
                model = model.strip()
                row["model"] = model if MODEL_ID.match(model) else None
        out[k] = row
    return out


# --------------------------------------------------------------------------------------------------------------------
# validate — one schema, unknown fields rejected
# --------------------------------------------------------------------------------------------------------------------

# The answer vocabulary. The workflow prompt states every one of these (tests/test_judgment_lane.py holds it to them).
PREDICTED = ("YES", "NO")
CONFIDENCE = ("high", "medium", "low")
RESULTS = ("pass", "fail")
FM_KINDS = ("missing", "style")
RULE_KINDS = ("violation_not_flagged", "compliant_flagged")

_FIELDS = {
    "trig": ({"id", "predicted", "confidence"}, set()),
    "fm": ({"id", "result"}, {"kind", "key", "note"}),
    "rule": ({"id", "result"}, {"kind", "note"}),
    "out": ({"id", "result"}, {"note"}),
    "fmt": ({"id", "result"}, {"note"}),
    "in": ({"id", "result"}, {"note"}),
}


def _bounded(value):
    return isinstance(value, str) and 0 < len(value) <= BOUNDED and "\n" not in value and "\r" not in value


def _check_one(check, spec_check, errors, where):
    kind = spec_check["kind"]
    required, optional = _FIELDS[kind]
    fields = set(check)
    for f in sorted(fields - required - optional):
        errors.append(f"{where}: unknown field {f}")
    for f in sorted(required - fields):
        errors.append(f"{where}: missing field {f}")
    if kind == "trig":
        if check.get("predicted") not in PREDICTED:
            errors.append(f"{where}: predicted must be YES or NO")
        if check.get("confidence") not in CONFIDENCE:
            errors.append(f"{where}: confidence must be high, medium or low")
        return check.get("predicted") == spec_check["expected"]
    result = check.get("result")
    if result not in RESULTS:
        errors.append(f"{where}: result must be pass or fail")
    if "note" in check and not _bounded(check["note"]):
        errors.append(f"{where}: note must be a single line of at most {BOUNDED} characters")
    if kind == "fm":
        if result == "fail":
            if check.get("kind") not in FM_KINDS:
                errors.append(f"{where}: a frontmatter failure needs kind missing or style")
            keys = spec_check["keys"]
            if keys:
                if check.get("key") not in keys:
                    errors.append(f"{where}: key {check.get('key')!r} is not one this bullet names ({', '.join(keys)})")
            elif "key" in check:
                errors.append(f"{where}: this bullet names no key, so the failure takes none")
        elif "kind" in check or "key" in check:
            errors.append(f"{where}: kind and key belong to a failure only")
    if kind == "rule":
        if result == "fail" and check.get("kind") not in RULE_KINDS:
            errors.append(f"{where}: a rule failure needs kind violation_not_flagged or compliant_flagged")
        elif result != "fail" and "kind" in check:
            errors.append(f"{where}: kind belongs to a failure only")
    return result == "pass"


def validate(raw, assigned, inventories):
    """{"errors": [...], "spec_errors": {stem: [...]}, "specs": {stem: [check result, ...]}} for one batch document.

    Two levels (D5). A document that is not the schema — a token-shaped string, not JSON, the wrong top level, a
    malformed entry, a spec it was not assigned — is untrustworthy as a whole: `errors`, and the batch is invalid. A
    problem confined to one assigned spec — a missing or duplicated entry, any check-level error — is that spec's:
    `spec_errors[stem]`, and its batch-mates are still rendered."""
    errors, spec_errors, specs = [], {}, {}
    if TOKEN_SHAPED.search(raw):
        return {"errors": ["the batch contains a token-shaped string"], "spec_errors": {}, "specs": {}}
    try:
        doc = json.loads(raw)
    except ValueError:
        return {"errors": ["the batch is not valid JSON"], "spec_errors": {}, "specs": {}}
    if not (isinstance(doc, dict) and set(doc) == {"specs"} and isinstance(doc["specs"], list)):
        return {"errors": ['the batch top level must be exactly {"specs": [...]}'], "spec_errors": {}, "specs": {}}
    seen = []
    for entry in doc["specs"]:
        if not (isinstance(entry, dict) and set(entry) == {"spec", "checks"} and isinstance(entry.get("checks"), list)):
            errors.append("a spec entry must be exactly {spec, checks}")
            continue
        stem = entry["spec"]
        if stem not in assigned:
            errors.append(f"unassigned spec {stem}")
            continue
        if stem in seen:
            spec_errors.setdefault(stem, []).append(f"duplicate spec {stem}")
            continue
        seen.append(stem)
        mine = []
        expected = {c["id"]: c for c in inventories[stem]["checks"]}
        got_ids, results = [], []
        for check in entry["checks"]:
            if not isinstance(check, dict) or not isinstance(check.get("id"), str):
                mine.append(f"{stem}: a check must be an object with an id")
                continue
            cid = check["id"]
            if cid == "score" or cid.startswith("score") or cid.startswith("lane5"):
                mine.append(f"{stem}: the model reported lane 5 ({cid}); scores are computed, not reported")
                continue
            if cid in got_ids:
                mine.append(f"{stem}: duplicate check {cid}")
                continue
            got_ids.append(cid)
            if cid not in expected:
                mine.append(f"{stem}: unexpected check {cid}")
                continue
            passed = _check_one(check, expected[cid], mine, f"{stem} {cid}")
            results.append({"id": cid, "passed": passed, "check": check, "spec_check": expected[cid]})
        for cid in expected:
            if cid not in got_ids:
                mine.append(f"{stem}: missing check {cid}")
        if mine:
            spec_errors.setdefault(stem, []).extend(mine)
        specs[stem] = results
    for stem in assigned:
        if stem not in seen:
            spec_errors.setdefault(stem, []).append(f"missing spec {stem}")
    return {"errors": errors, "spec_errors": spec_errors, "specs": specs}


# --------------------------------------------------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------------------------------------------------


def _fail_lines(result):
    sc, ch = result["spec_check"], result["check"]
    kind = sc["kind"]
    if kind == "trig":
        return [f'✗ "{sc["text"]}" → predicted {ch["predicted"]} trigger (expected {sc["expected"]})',
                f'    confidence: {ch["confidence"]}']
    if kind == "fm":
        key = ch.get("key") or "frontmatter"
        line = (f"✗ frontmatter: missing '{key}'" if ch.get("kind") == "missing"
                else f"✗ frontmatter: '{key}' not {sc['text']}")
    elif kind == "out":
        line = f'✗ output: missing "{sc["text"]}"'
    elif kind == "fmt":
        line = f'✗ output: format element "{sc["text"]}" not stated'
    elif kind == "in":
        line = f'✗ input: "{sc["text"]}" behavior not stated'
    else:
        line = ("✗ rule: violation sample not flagged" if ch.get("kind") == "violation_not_flagged"
                else "✗ rule: compliant sample flagged")
    lines = [line]
    if ch.get("note"):
        lines.append(f"    note: {ch['note']}")
    return lines


def report(root, in_dir, plan_matrix, out, commit="", date=""):
    """Render the Vibe Suite Test Report. Returns the process exit status; a forged matrix writes nothing."""
    root = Path(root)
    expected = plan(root)
    try:
        received = json.loads(plan_matrix)
    except ValueError:
        received = None
    if received != expected:
        sys.stderr.write("judgment_lane: the received matrix does not match the plan recomputed from this checkout\n")
        return 2
    stems = spec_stems(root)
    batch_of = {s: b["batch"] for b in expected["include"] for s in b["specs"].split()}
    assigned = {b["batch"]: b["specs"].split() for b in expected["include"]}
    scores = score(root, stems)
    inventories = {s: inventory(spec_meta(root, s)["text"]) for s in stems}
    batches = read_batches(in_dir, sorted(assigned))
    validated = {}
    for k, row in batches.items():
        if row["present"] and not row["error"]:
            validated[k] = validate(row["raw"], assigned[k], inventories)

    rows, blocks, red = [], [], []
    passed_specs = 0
    for stem in stems:
        s = scores[stem]
        name = f"{stem}.spec.md"
        if s["missing"]:
            rows.append(f"| {name} | {s['artifact']} | FAIL | RED |")
            blocks.append((name, [f"✗ artifact missing (RED): {s['artifact']}"]))
            red.append(f"{name} → {s['artifact']}: artifact missing")
            continue
        k = batch_of[stem]
        batch = batches[k]
        if not batch["present"]:
            rows.append(f"| {name} | {s['artifact']} | FAIL | no report |")
            red.append(f"{name} → {s['artifact']}: batch {k} produced no report")
            continue
        if batch["error"] or validated[k]["errors"]:
            detail = batch["error"] or "; ".join(validated[k]["errors"][:3])
            rows.append(f"| {name} | {s['artifact']} | FAIL | invalid batch |")
            blocks.append((name, [f"✗ batch {k} rejected: {detail}"]))
            red.append(f"{name} → {s['artifact']}: batch {k} rejected")
            continue
        if stem in validated[k]["spec_errors"]:
            detail = "; ".join(validated[k]["spec_errors"][stem][:3])
            rows.append(f"| {name} | {s['artifact']} | FAIL | invalid verdict |")
            blocks.append((name, [f"✗ verdict rejected: {detail}"]))
            red.append(f"{name} → {s['artifact']}: verdict rejected")
            continue
        results = validated[k]["specs"][stem]
        lines = [l for r in results if not r["passed"] for l in _fail_lines(r)]
        gaps = sum(1 for r in results if not r["passed"])
        if s["error"]:
            lines.append(f"✗ score: {s['error']}")
            lane5 = False
        else:
            lane5 = s["score"] >= s["min"]
            if not lane5:
                lines.append(f"✗ score {s['score']}/100 (min: {s['min']})")
        gaps += 0 if lane5 else 1
        total = len(results) + 1
        passes = total - gaps
        if gaps == 0:
            passed_specs += 1
            rows.append(f"| {name} | {s['artifact']} | PASS | {passes}/{total} checks |")
        else:
            rows.append(f"| {name} | {s['artifact']} | FAIL | {passes}/{total} checks |")
            blocks.append((name, lines))
            red.append(f"{name} → {s['artifact']}: {gaps} gap(s)")

    models = sorted({b["model"] for b in batches.values() if b["model"]})
    unevaluated = [f"{s}.spec.md → {', '.join(inv['unevaluated'])}"
                   for s, inv in inventories.items() if inv["unevaluated"]]
    missing_batches = [k for k in sorted(assigned) if not batches[k]["present"]]
    failed = len(stems) - passed_specs
    percent = round(100 * passed_specs / len(stems)) if stems else 0

    text = ["Vibe Suite Test Report", "",
            "Judgment lane — advisory. Lanes 1-4 were judged by the tester's procedure, run in-session by a Claude "
            "session; this is not the tester subagent. Lane 5 was computed by the score engine, not by the model.",
            f"Commit: {commit} · Date: {date} · Model: {', '.join(models) if models else 'not reported'}"]
    if missing_batches:
        text.append("Missing: " + "; ".join(f"batch {k} produced no report" for k in missing_batches))
    if unevaluated:
        text.append("Not evaluated (no lane reads these sections): " + "; ".join(unevaluated))
    text += ["", "| Spec | Artifact | Result | Details |", "|------|----------|--------|---------|", *rows, ""]
    for name, lines in blocks:
        text += [f"**{name}**", "", "```", *lines, "```", ""]
    text += [f"{passed_specs} passed, {failed} failed ({percent}%)", ""]
    if red:
        text += ["RED items (fix these):", *[f"{n}. {item}" for n, item in enumerate(red, 1)]]
    Path(out).write_text("\n".join(text) + "\n", encoding="utf-8")
    return 0


# --------------------------------------------------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------------------------------------------------


def main(argv=None):
    ap = argparse.ArgumentParser(prog="judgment_lane.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--root", required=True)
    i = sub.add_parser("inventory")
    i.add_argument("--root", required=True)
    i.add_argument("--specs", required=True)
    i.add_argument("--out", required=True)
    r = sub.add_parser("report")
    r.add_argument("--root", required=True)
    r.add_argument("--in", dest="in_dir", required=True)
    r.add_argument("--plan-matrix", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--commit", default="")
    r.add_argument("--date", default="")
    a = ap.parse_args(argv)
    if a.cmd == "plan":
        print(json.dumps(plan(a.root)))
        return 0
    if a.cmd == "inventory":
        payload = {s: inventory(spec_meta(a.root, s)["text"]) for s in a.specs.split()}
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        return 0
    return report(a.root, a.in_dir, a.plan_matrix, a.out, commit=a.commit, date=a.date)


if __name__ == "__main__":
    sys.exit(main())
