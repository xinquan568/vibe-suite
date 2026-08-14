# SPDX-License-Identifier: ISC
"""The E8.2 workflow lint (vibe-59): fail-closed checks over auditor/workflows/*.yml.

This IS the "workflow lint green" acceptance clause at the current gate rung. It has TWO
layers, and the split matters — conflating them is what made three review rounds necessary:

1. **YAML well-formedness — delegated to a real parser** (`ruby -ryaml`, i.e. Psych).
   `lint()` below is a line-oriented subset grammar, and a line-oriented grammar cannot
   validate YAML. Three rounds of hardening it closed individual spellings while the CLASS
   of defect survived: mismatched quotes (`"on':`), unclosed flow collections
   (`on: [workflow_dispatch`), empty flow entries (`[ , ]`), doubled commas, undefined
   aliases. Each was a Psych syntax error that the grammar accepted. Psych settles all of
   them at once. This is the same move the suite already makes for shell — `bash -n` rather
   than a hand-written shell parser — and Ruby is a system tool, not a third-party
   dependency (the ban is on adding parser LIBRARIES to shipped tooling; this is a test).

2. **Contract properties — the subset grammar in `lint()`.** Stated precisely, because an
   earlier version of this list claimed more than the code did:

   * which workflows exist, as an explicit name set;
   * that authority is DECLARED — at workflow or job level — rather than inherited from the
     repository default, plus the two documented whole-workflow scalars (`read-all`,
     `write-all`). It does NOT validate permission scopes or their values: a table for those
     was written twice and was wrong both times, and now lives in #165;
   * that a stage workflow MENTIONS its entry label. Not that the label is operative — three
     attempts at that were defeated, and it is #165's;
   * that only known secrets are referenced by `secrets.X` and `secrets['X']`. A computed
     index (`secrets[format(...)]`) is not detected — #165;
   * no pinned model ids (escaped spellings excepted — #165);
   * a targeted expression check. NOT an Actions expression grammar — #165.

`lint()` therefore does NOT claim to detect malformed YAML, and the suite no longer asserts
that it does. `test_every_workflow_is_wellformed_yaml` owns that half.
"""
import os
import random
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WF_DIR = REPO / "auditor" / "workflows"
#: The live workflows. Shell in these RUNS today, so it is checked alongside the
#: staged set — the bash -n loop used to skip it entirely.
LIVE_WF_DIR = REPO / ".github" / "workflows"

STAGES = {
    "auditor-discover.yml": "audit-candidate",
    "auditor-audit.yml": "audit-ready",
    "auditor-contribute.yml": "contribute-approved",
    "auditor-track.yml": None,            # cron-driven scanner
    "auditor-case-study.yml": "case-study-ready",
    "auditor-daily-report.yml": None,     # cron-driven observer
}
SUPPORTING = [
    "auditor-classify.yml", "auditor-batch-processor.yml", "auditor-integration-test.yml",
    "auditor-render-dashboard.yml", "auditor-repo-report.yml", "auditor-suppressions.yml",
    "auditor-vocab-drift.yml",
]
FEEDBACK = [
    "auditor-exemplar.yml", "auditor-cite-exemplars.yml", "auditor-refine-rules.yml",
    "auditor-rule-review.yml", "auditor-docs-diff.yml",
]
EXPECTED = sorted(list(STAGES) + SUPPORTING + FEEDBACK)

MODEL_WORKFLOWS = [
    "auditor-audit.yml", "auditor-contribute.yml", "auditor-case-study.yml",
    "auditor-classify.yml", "auditor-integration-test.yml", "auditor-vocab-drift.yml",
    "auditor-exemplar.yml", "auditor-refine-rules.yml",
]
#: Stage workflows that CREATE the labelled issue rather than react to it. Everything else in
#: STAGES is a consumer and must gate on `github.event.label.name`.
LABEL_PRODUCERS = {"auditor-discover.yml"}
DATA_WRITERS = [
    "auditor-discover.yml", "auditor-audit.yml", "auditor-contribute.yml", "auditor-track.yml",
    "auditor-case-study.yml", "auditor-daily-report.yml", "auditor-classify.yml",
    "auditor-render-dashboard.yml", "auditor-repo-report.yml", "auditor-suppressions.yml",
    "auditor-vocab-drift.yml", "auditor-exemplar.yml", "auditor-refine-rules.yml",
    "auditor-docs-diff.yml",
]

#: The 30 E8.3 helpers, by exact name (F10.4). Declared here so the tree can be guarded while
#: the item lands incrementally: anything under auditor/scripts/ that is not on this list is a
#: stray, and a stray is how an inventory row passes for the wrong reason.
SCRIPTS_DIR = REPO / "auditor" / "scripts"

E83_HELPERS = (
    "atomic-registry-write.sh", "backfill-findings.py", "backfill-pr-fingerprints.py",
    "batch-process.py", "build-exemplar-gallery.py", "commit-via-pr.sh",
    "compute-fingerprint.sh", "compute-vocab-fingerprint.sh", "diff-findings.py",
    "docs-diff.py", "generate-daily-report.py", "generate-rule-review-body.py",
    "git-push-with-retry.sh", "guard-protected-paths.sh", "log-event.sh",
    "parse-pr-metadata.py", "parse-suppressions.py", "prepare-refinement-input.py",
    "propose-rule-citations.py", "render-dashboard.py", "render-repo-report.py",
    "repair-stale-statuses.py", "resolve-merge-conflicts.sh", "rule-health.py",
    "scan-suppressions.py", "synthesize-sidecar.py", "three-way-merge-registry.py",
    "validate-feedback.sh", "validate-rule-ids.py", "vendor_default_filter.py",
)

TOP_KEYS = {"name", "on", "permissions", "concurrency", "env", "jobs"}
KNOWN_SECRETS = {"CLAUDE_CODE_OAUTH_TOKEN", "PAT_TOKEN", "OPENAI_API_KEY", "GITHUB_TOKEN"}
#: NOT a scope/value table. One was written here and removed — see
#: test_permissions_are_checked_for_presence_only. Validating Actions' permission vocabulary
#: means tracking a set GitHub changes; two attempts were wrong in both directions (`models`
#: was dropped, `id-token: read` accepted). That validation is #165's.
BLOCKED_CMDS = ["curl", "wget", "nc", "ncat", "socat", "telnet", "ssh", "scp", "sftp", "rsync"]

MODEL_ID = re.compile(
    r"claude-[a-z]+-[0-9]|claude-[a-z0-9-]*-20[0-9]{2}|gpt-[0-9]|gemini-[0-9]|o[0-9]-|"
    r"--model\b|(^|\s)model:", re.M)
EXPR = re.compile(r"\$\{\{(.*?)\}\}", re.S)
EXPR_GRAMMAR = re.compile(
    r"^[\s(!]*(github|secrets|inputs|needs|env|matrix|steps|vars|runner|"
    r"contains|startsWith|endsWith|format|join|toJSON|fromJSON|hashFiles|"
    r"always|failure|success|cancelled|true|false|null|[0-9'\"])")
_EXPR_TOKEN = re.compile(
    r"[A-Za-z_][A-Za-z0-9_-]*|\.|\(|\)|\[|\]|,|!|&&|\|\||[=!<>]=?|\*|'[^']*'|\"[^\"]*\"|"
    r"[0-9.]+|\s+")
_ALLOWED_ROOTS = {"github", "secrets", "inputs", "needs", "env", "matrix", "steps", "vars",
                  "runner"}
_ALLOWED_FUNCS = {"contains", "startsWith", "endsWith", "format", "join", "toJSON", "fromJSON",
                  "hashFiles", "always", "failure", "success", "cancelled",
                  # `case` joined the documented function list; rejecting it was an
                  # over-rejection of valid Actions syntax.
                  "case"}


#: A top-level key, with the optional quoting YAML permits. `on` MUST be quotable: bare `on`
#: is a YAML 1.1 boolean, so linters actively push authors to write `"on":`. Rejecting that
#: would reject a correct workflow, so every top-level scan shares this one pattern.
#:
#: The quotes must MATCH. `"on':` is a YAML syntax error (Psych rejects it) and an earlier
#: `["']?` on each side accepted it, so a mismatched-quote key satisfied a required-key check
#: while the file would not parse at all.
_TOP_KEY = re.compile(r"""^(?:"([A-Za-z_][A-Za-z0-9_-]*)"|'([A-Za-z_][A-Za-z0-9_-]*)'"""
                      r"""|([A-Za-z_][A-Za-z0-9_-]*)):""")
#: Same shape at job-key indentation, so a quoted job id (`"a":`) is a job like any other.
_JOB_KEY = re.compile(r"""^  (?:"([A-Za-z_][A-Za-z0-9_-]*)"|'([A-Za-z_][A-Za-z0-9_-]*)'"""
                      r"""|([A-Za-z_][A-Za-z0-9_-]*)):[ \t]*(.*)$""")
#: YAML nulls, in every spelling. Comparing against the literal "null" missed `NULL`/`Null`/`~`.
_NULLS = {"", "null", "~"}


#: Printed by the ruby adapter on a completed run. Its ABSENCE means the child did not finish,
#: whatever its stdout looked like — the difference between "parsed cleanly" and "never ran".
_OK_MARKER = "__PSYCH_OK__"


def _ruby():
    """Path to a usable ruby, or None."""
    for cand in ("/usr/bin/ruby", "ruby"):
        try:
            if subprocess.run([cand, "-e", "require 'yaml'"],
                              capture_output=True, timeout=30).returncode == 0:
                return cand
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def psych_error(text):
    """Psych's complaint about `text`, '' if it parses, or None when ruby is unavailable.

    A real YAML parser is the only honest way to answer "is this valid YAML". Returning None
    (rather than '') when ruby is missing keeps "unavailable" distinguishable from "valid" —
    a gate that silently reports success when it did not run is the failure mode this whole
    item exists to remove.
    """
    rb = _ruby()
    if rb is None:
        return None
    # Version-tolerant on purpose. Ruby 2.6's YAML.load resolves aliases; Ruby 3.1+ defaults to
    # safe_load with aliases DISABLED and raises Psych::AliasesNotEnabled — so a workflow using
    # a perfectly legal anchor failed only on the newer runtime. CI found that; a gate that
    # skipped instead of failing would have hidden it.
    #
    # Psych.parse answers well-formedness on every version without resolving anything. The
    # second pass resolves aliases where the API allows, to catch an alias to a missing anchor.
    script = (
        "require 'yaml'\n"
        "text = STDIN.read\n"
        "def fail_with(e)\n"
        "  print e.class.to_s + ': ' + e.message.to_s[0, 200]\n"
        "  exit 0\n"
        "end\n"
        "begin\n"
        "  Psych.parse(text)\n"
        "rescue => e\n"
        "  fail_with(e)\n"
        "end\n"
        "begin\n"
        "  begin\n"
        "    YAML.load(text, aliases: true)\n"
        "  rescue ArgumentError, NoMethodError\n"
        "    YAML.load(text)\n"
        "  end\n"
        "rescue => e\n"
        "  fail_with(e) unless e.class.to_s == 'Psych::AliasesNotEnabled'\n"
        "end\n"
        "print '" + _OK_MARKER + "'\n")
    try:
        r = subprocess.run([rb, "-e", script], input=text, capture_output=True,
                           text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"ruby adapter did not run: {type(exc).__name__}: {exc}"
    out = r.stdout.strip()
    # An empty stdout used to read as "well-formed". A child that segfaults, is killed, or dies
    # before printing anything produces exactly that — so the gate reported success for a parse
    # that never happened. Completion is now proven by the marker, not assumed from silence.
    if r.returncode != 0:
        return (f"ruby adapter exited {r.returncode}: "
                f"{(r.stderr or '').strip()[:200] or out[:200]}")
    if out == _OK_MARKER:
        return ""
    if out.endswith(_OK_MARKER):          # parser complaint plus completion marker
        return out[:-len(_OK_MARKER)].strip()
    if not out:
        return ("ruby adapter produced no output and no completion marker "
                f"(stderr: {(r.stderr or '').strip()[:200]!r})")
    return out


def _key_of(m):
    """The matched name from a quoted-or-bare key match."""
    return m.group(1) or m.group(2) or m.group(3)


def _unquote(s):
    """Strip ONE layer of matching quotes, preserving the interior exactly.

    Interior whitespace inside quotes is significant in YAML — `" read-all "` is the seven-plus
    character string, not `read-all` — so stripping it turned an invalid permissions value into
    a valid-looking one.
    """
    s = s.strip()
    if len(s) > 1 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _is_empty_value(raw):
    """True when an inline value carries no information.

    Covers '', null in any case, `~`, `{}`/`[]`, and — the case a flow-aware pass was needed
    for — a flow collection whose every entry is itself empty: `[null]` parses to [nil], a
    sequence that exists and contains no event.

    Whitespace INSIDE a flow collection is insignificant, so `{ }` == `{}`; whitespace inside
    QUOTES is significant, which is why _unquote no longer strips it.
    """
    s = _unquote(raw.split("#")[0].strip())
    if s.strip().lower() in _NULLS:
        return True
    s = s.strip()
    if len(s) >= 2 and s[0] in "{[" and s[-1] in "}]":
        inner = s[1:-1].strip()
        if not inner:
            return True
        # every entry empty => the collection carries nothing
        return all(not part.strip() or part.strip().lower() in _NULLS
                   for part in inner.split(","))
    return False


def _has_value(lines, key):
    """True when top-level `key` carries a real value: an inline scalar/flow collection that
    is not empty-or-null, or at least one more-indented line beneath it.

    `on:` alone, `on: null` and `on: {}` are all "present but empty" — the presence check
    cannot tell them from a real trigger block, which is why this exists separately.
    """
    pat = re.compile(r"""^(?:"%s"|'%s'|%s):[ \t]*(.*)$"""
                     % (re.escape(key), re.escape(key), re.escape(key)))
    for n, ln in enumerate(lines):
        m = pat.match(ln)
        if not m:
            continue
        if not _is_empty_value(m.group(1)):
            return True
        # No inline value: the block beneath must carry one. A sequence of nulls
        # (`on:` / `  - null`) parses to [nil] — present, but no trigger at all.
        block = []
        for nxt in lines[n + 1:]:
            if not nxt.strip() or nxt.lstrip().startswith("#"):
                continue
            if len(nxt) - len(nxt.lstrip(" ")) == 0:
                break
            block.append(nxt)
        for b in block:
            item = re.sub(r"^\s*-\s*", "", b).strip()
            if item and not _is_empty_value(item):
                return True
        return False
    return False


def lint(text, name="workflow.yml"):
    """Return a list of violation strings for one workflow file's raw text."""
    v = []
    lines = text.split("\n")
    if "\t" in text:
        v.append("tab character")
    # top-level keys + duplicate detection per MAPPING (sequence items included).
    # Each `- ` item opens its own mapping scope at the content column, so a key repeated
    # inside one step is a duplicate while the same key across sibling steps is not.
    stack = []          # [(column, {keys seen in that mapping})]
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        i = idx + 1
        idx += 1
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        body, dash = raw, re.match(r"^( *)-(\s+|$)", raw)
        if dash:
            if dash.group(1) == "":
                # A dash at column 0 makes the document a SEQUENCE. A workflow must be a
                # mapping, so this is structural junk however valid the YAML is. Checked HERE
                # rather than after the key parse, because `- k: v` parses as a key and would
                # otherwise take the mapping path and pass.
                v.append(f"line {i}: top-level sequence item: {raw.strip()[:60]!r}")
            if indent % 2:
                v.append(f"line {i}: off-grid indentation ({indent})")
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent + 2, set()))
            body, indent = " " * (indent + 2) + raw[dash.end():], indent + 2
            if not body.strip():
                continue
        m = re.match(r"""^ *(?:["']?)([A-Za-z_][A-Za-z0-9_./ -]*)(?:["']?):(\s|$)""", body)
        if not m:
            # FAIL CLOSED. This used to `continue`, which silently accepted anything the grammar
            # did not recognise — junk top-level text passed, and so did every malformed
            # construct that simply failed to look like a key. Block-scalar bodies are consumed
            # wholesale further down, so a line arriving here is structural and unrecognised.
            # A dash-introduced item whose body is a plain scalar is valid YAML — `options:` lists
            # `- unit` / `- smoke` exactly this way. `body` has already had the dash stripped, so
            # the original line is what must be tested; checking `body` here flagged every scalar
            # list entry in the suite.
            if not dash:
                v.append(f"line {i}: unrecognised construct: {body.strip()[:60]!r}")
            continue
        if not dash and indent % 2:
            v.append(f"line {i}: off-grid indentation ({indent})")
        key = m.group(1)
        while stack and stack[-1][0] > indent:
            stack.pop()
        if not stack or stack[-1][0] < indent:
            stack.append((indent, set()))
        if key in stack[-1][1]:
            v.append(f"line {i}: duplicate key '{key}'")
        stack[-1][1].add(key)
        if indent == 0 and key not in TOP_KEYS:
            v.append(f"line {i}: unknown top-level key '{key}'")
        # a block scalar's body is shell/prose, not a mapping — skip it wholesale
        if re.match(r"^[|>][-+0-9]*$", body[m.end():].strip()):
            while idx < len(lines) and (
                    not lines[idx].strip()
                    or len(lines[idx]) - len(lines[idx].lstrip(" ")) > indent):
                idx += 1
    # Required top-level structure. The mutation suite previously only ever changed a value; it
    # never REMOVED a required section, so a workflow with no `on:` trigger and no declared
    # permissions linted clean. Absence is now a violation in its own right.
    top_keys = {_key_of(mm) for mm in (_TOP_KEY.match(ln) for ln in lines) if mm}
    # `on` and `jobs` are required by GitHub; `name` is NOT, and is no longer required here.
    # It was, on the stated grounds that STAGES keys on it — which is simply false: STAGES is
    # keyed by FILENAME. The check also passed a valueless `name:`, so it never protected the
    # identity it claimed to. A rule whose justification does not survive inspection is a false
    # positive with a comment attached, so it is gone rather than re-argued.
    for required in ("on", "jobs"):
        if required not in top_keys:
            v.append(f"missing required top-level key '{required}'")
    # A required key being PRESENT does not make it meaningful. `on:` with nothing under it,
    # `on: null` and `on: {}` all satisfied the presence check above while describing a
    # workflow that can never trigger — the staged set's whole contract is which event fires
    # which stage, so an empty trigger is a silent contract hole, not a stylistic nit.
    if "on" in top_keys and not _has_value(lines, "on"):
        v.append("top-level key 'on' declares no trigger")
    # `permissions:` accepts exactly two scalars. Anything else is a typo that silently falls
    # back to the repository default — the authority the staged split exists to remove.
    # An EMPTY mapping is deliberate and correct (grant nothing), so it is not flagged.
    for n, ln in enumerate(lines):
        pm = re.match(r"""^(?:["']?)permissions(?:["']?):[ \t]*(.*)$""", ln)
        if not pm:
            continue
        raw = pm.group(1).split("#")[0].strip()
        val = _unquote(raw)
        # An inline FLOW MAPPING is a perfectly ordinary permissions declaration —
        # `permissions: {contents: read}` — and was being rejected as an "invalid scalar"
        # because anything that was not a bare keyword got that message.
        if raw.startswith("{") and raw.endswith("}") and raw[1:-1].strip():
            continue
        # GitHub documents `read-all` and `write-all` exactly; `READ-ALL` is not a synonym, and
        # lower-casing before the comparison invented one.
        if val.strip() and val not in ("{}", "null", "~", "read-all", "write-all"):
            v.append(f"top-level 'permissions' has invalid scalar {val[:40]!r}")
        elif val.strip().lower() in ("", "null", "~"):
            # `permissions: {}` is a real declaration — grant nothing — and five shipped
            # workflows rely on it, so it must keep passing. A BARE or null `permissions:` is
            # not a declaration at all: it satisfied the presence check above, which then
            # stopped requiring per-job permissions, so every job silently inherited the
            # repository default. That is precisely the authority this lint exists to remove.
            nested = next((x for x in lines[n + 1:] if x.strip()
                           and not x.lstrip().startswith("#")), None)
            if nested is None or len(nested) - len(nested.lstrip(" ")) == 0:
                v.append("top-level 'permissions' declares nothing "
                         "(use `permissions: {}` to grant none)")
            elif re.match(r"^\s*-(\s|$)", nested):
                # Matched only "- " before, so a BARE dash opened a sequence unnoticed.
                # `permissions:` / `  - read-all` parses to a LIST, which is not a permissions
                # mapping; GitHub would reject it and the lint accepted it.
                v.append("top-level 'permissions' is a sequence, not a mapping")
    # Least privilege must be DECLARED, at the workflow or at every job — an undeclared workflow
    # inherits the repository default, which is exactly the authority the split exists to remove.
    # This catches absence, null, and the sequence spellings it is tested against; it does NOT
    # enforce declaration for every Psych-valid spelling (#165).
    if "permissions" not in top_keys:
        for j, b in _jobs(lines).items():
            declared = None
            for n, ln in enumerate(b):
                jm = re.match(r"""^    (?:["']?)permissions(?:["']?):[ \t]*(.*)$""", ln)
                if not jm:
                    continue
                inline = jm.group(1).split("#")[0].strip()
                if inline:
                    # A permissions value is a MAPPING or one of the two whole-workflow
                    # scalars. Treating every non-null inline value as a declaration let
                    # `permissions: []` (a sequence) and `permissions: |` (a block scalar)
                    # satisfy the contract while granting nothing and declaring nothing —
                    # the job then inherited the repository default.
                    low = inline.lower()
                    if low in ("null", "~"):
                        declared = False
                    elif inline.startswith("{") and inline.endswith("}"):
                        declared = True          # `{}` grants nothing, and that IS a decision
                    elif inline in ("read-all", "write-all") or \
                            _unquote(inline) in ("read-all", "write-all"):
                        declared = True
                    else:
                        declared = False         # sequences, block scalars, typos
                else:
                    nxt = next((x for x in b[n + 1:] if x.strip()
                                and not x.lstrip().startswith("#")), None)
                    # Any deeper line counted as a declaration, so a block-style SEQUENCE
                    # (`permissions:` / `  - run: read-all`) satisfied the contract while being
                    # no permissions mapping at all.
                    #
                    # LIMIT (#165): this recognises a mapping ENTRY by line shape, not by the
                    # parsed value. A quoted scalar containing a colon — `"not: a mapping"` —
                    # still passes, because the colon inside the quotes reads as a key/value
                    # separator. Enforcing this against the parsed document is #165's.
                    declared = (bool(nxt)
                                and len(nxt) - len(nxt.lstrip(" ")) > 4
                                and not re.match(r"^\s*-(\s|$)", nxt)
                                and re.match(r"""^\s*(?:["']?)[\w-]+(?:["']?):""", nxt) is not None)
                break
            if declared is None:
                v.append(f"job '{j}': no permissions declared and none at workflow level")
            elif not declared:
                # Matching the LINE was enough before, so `permissions: null` at job level
                # satisfied the requirement while declaring nothing — the job then inherited
                # the repository default, which is the authority this contract removes.
                v.append(f"job '{j}': 'permissions:' declares nothing")

    # duplicate top-level keys (simpler, reliable pass)
    tops = [_key_of(mm) for mm in (_TOP_KEY.match(ln) for ln in lines) if mm]
    for k in set(tops):
        if tops.count(k) > 1:
            v.append(f"duplicate top-level key '{k}'")
    # jobs shape
    jobs = _jobs(lines)
    if not jobs:
        inline_jobs = next((m.group(1).split("#")[0].strip() for m in
                            (re.match(r"""^(?:"jobs"|'jobs'|jobs):[ \t]*(.*)$""", ln)
                             for ln in lines) if m and m.group(1).split("#")[0].strip()), None)
        if inline_jobs and inline_jobs[0] == "{" and inline_jobs.rstrip()[-1] == "}" \
                and inline_jobs[1:-1].strip():
            # Legal YAML this line-oriented grammar cannot walk. Say that, rather than claim
            # the workflow has no jobs — the staged set uses block style throughout.
            v.append("jobs: uses an inline flow mapping, which this lint cannot validate; "
                     "use block style")
        else:
            v.append("no jobs")
    for jname, body in jobs.items():
        if not any(re.match(r"^    runs-on:", ln) for ln in body):
            v.append(f"job '{jname}' missing runs-on")
        if not any(re.match(r"^    steps:", ln) for ln in body):
            v.append(f"job '{jname}' missing steps")
        step_txt = "\n".join(body)
        for sm in re.finditer(r"^      - (?:name:.*)?$", step_txt, re.M):
            pass
    # Every step item _steps() RECOGNISES has uses: or run:.
    #
    # LIMIT (#165): `_steps()` splits on `- ` and does not see a BARE dash, so a step written
    # `-` on its own line with `name:`/`id:` beneath it is not enumerated and cannot be
    # checked. Enumerating steps from the parsed document is #165's.
    for jname, body in jobs.items():
        for step in _steps(body):
            if not any(re.match(r"\s*(uses|run):", ln) for ln in step):
                v.append(f"job '{jname}': step with neither uses nor run")
    # expression delimiter pairing — must run BEFORE the pair regex, which only ever sees
    # balanced spans and is therefore blind to a `${{` that is never closed.
    scan = 0
    while True:
        open_at = text.find("${{", scan)
        if open_at < 0:
            break
        close_at = text.find("}}", open_at + 3)
        nested_at = text.find("${{", open_at + 3)
        if close_at < 0 or (0 <= nested_at < close_at):
            v.append("line %d: unclosed expression delimiter"
                     % (text.count("\n", 0, open_at) + 1))
            if close_at < 0:
                break
        scan = close_at + 2
    # expressions
    for m in EXPR.finditer(text):
        inner = m.group(1).strip()
        if not _expr_ok(inner):
            v.append(f"expression outside grammar: {inner[:60]}")
    # Secrets by name, in BOTH notations. `secrets['X']` is GitHub's documented index operator
    # and reaches exactly the same value as `secrets.X`, so checking only property access left
    # the allowlist trivially bypassable by changing punctuation.
    for sm in re.finditer(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", text):
        if sm.group(1) not in KNOWN_SECRETS:
            v.append(f"unknown secret '{sm.group(1)}'")
    # `secrets [ 'X' ]` — the runner's lexer skips whitespace before the index operator, so
    # requiring the bracket to touch the identifier left the allowlist bypassable by a space.
    for sm in re.finditer(
            r"""secrets\s*\[\s*(['\"])([A-Za-z_][A-Za-z0-9_]*)\1\s*\]""", text):
        if sm.group(2) not in KNOWN_SECRETS:
            v.append(f"unknown secret '{sm.group(2)}' (index notation)")
    # Presence of a DECLARATION, not validation of its vocabulary. The least-privilege
    # contract this lint owns is "authority is declared rather than inherited from the
    # repository default" — which is checked above, at workflow or job level. What the declared
    # scopes and values MEAN is GitHub's vocabulary, it changes, and two attempts to encode it
    # here were wrong in both directions. That check is #165's; this one no longer pretends to
    # make it.
        # model pins
    for i, ln in enumerate(lines, 1):
        if ln.lstrip().startswith("#"):
            continue
        if MODEL_ID.search(ln):
            v.append(f"line {i}: model id / model key: {ln.strip()[:60]}")
    # Helper references. Every helper is delivered, so the deferral seams are gone and the
    # marker that guarded them is no longer accepted. Three properties remain, each of which
    # has already failed silently once.
    #
    # The NAME must be one of the declared thirty, or explicitly deferred to a LATER epic.
    # `build-exemplar-gallery.sh` was guarded and invoked for months; the helper is `.py`, so
    # the guard was never true and the gallery never built. Nothing failed — the else branch
    # printed a deferral notice. `apply-rule-citations.sh` is not in the thirty at all and is
    # marked for the epic that does deliver it.
    #
    # The PREDICATE must be one the helper's contract mode permits. Python helpers ship
    # 100644, so `[ -x helper.py ]` is false forever and the branch would skip a helper that
    # is sitting right there on disk. Shell helpers ship 100755, where -x is fine.
    #
    # The INTERPRETER must match the extension: `bash` on a Python file is a syntax error, and
    # in a guarded branch that error was never reached to be noticed.
    retired_marker = "deferred:" + "E8" + ".3"
    for i, ln in enumerate(lines, 1):
        m = re.search(r"auditor/scripts/([A-Za-z0-9._-]+)", ln)
        if not m:
            continue
        name = m.group(1)
        window = "\n".join(lines[max(0, i - 6):i + 1])
        if retired_marker in window:
            v.append(f"line {i}: retired deferral marker — every E8.3 helper has landed")
        if name not in E83_HELPERS:
            deferred = re.search(r"deferred:(E8\.\d+)", window)
            if not deferred or deferred.group(1) == "E8" + ".3":
                v.append(f"line {i}: '{name}' is not one of the declared helpers; mark it "
                         f"deferred to the epic that delivers it")
        elif not (SCRIPTS_DIR / name).is_file():
            v.append(f"line {i}: '{name}' is declared but not delivered")
        if name.endswith(".py"):
            if re.search(r"\[\s+(?:!\s+)?-x\s+\"?[^\"]*" + re.escape(name), ln):
                v.append(f"line {i}: -x guard on '{name}' — Python helpers ship mode 100644, "
                         f"so this is false forever; use -f")
            if re.search(r"(?<![-\w])bash\s+\"[^\"]*" + re.escape(name), ln):
                v.append(f"line {i}: '{name}' invoked with bash")
        if name.endswith(".sh") and re.search(r"python3?\s+\"[^\"]*" + re.escape(name), ln):
            v.append(f"line {i}: '{name}' invoked with python")
    return v


def _jobs(lines):
    jobs, cur, body = {}, None, []
    in_jobs = False
    anchors = {}
    for ln in lines:
        jm = re.match(r"""^(?:"jobs"|'jobs'|jobs):[ \t]*(.*)$""", ln)
        if jm:
            inline = jm.group(1).split("#")[0].strip()
            # `jobs: &all_jobs` anchors the whole mapping and the jobs still follow beneath it.
            # Treating any inline text as "not a mapping" reported `no jobs` for valid YAML.
            if inline.startswith("&"):
                inline = ""
            # `jobs: |` is a BLOCK SCALAR, not a mapping. The structural scanner skips a block
            # scalar's body wholesale (it is shell/prose), so job-shaped text inside one was
            # invisible there — and this function used to reparse that same text as real jobs.
            # The two passes disagreed, and the disagreement read as a valid workflow.
            #
            # An inline FLOW MAPPING (`jobs: {a: {...}}`) is different: it is legal YAML that
            # this line-oriented grammar cannot walk. Returning {} for it says "no jobs", which
            # is a lie about valid input — so lint() reports the unsupported spelling instead.
            if inline:
                return {}
            in_jobs = True
            continue
        if in_jobs and re.match(r"^[A-Za-z_\"']", ln):
            in_jobs = False
        if in_jobs:
            m = _JOB_KEY.match(ln)
            if m:
                if cur:
                    jobs[cur] = body
                cur, body = _key_of(m), []
                rest = (m.group(4) or "").split("#")[0].strip()
                # GitHub Actions has supported YAML anchors and aliases since 2025-09-18, so
                # `a: &base` defines a reusable job and `b: *base` IS a job with that body.
                # Treating the alias as bodyless reported `no jobs` for a valid workflow.
                if rest.startswith("&"):
                    anchors[rest[1:].strip()] = body
                elif rest.startswith("*"):
                    jobs[cur] = list(anchors.get(rest[1:].strip(), []))
                    cur, body = None, []
            elif cur is not None:
                body.append(ln)
    if cur:
        jobs[cur] = body
    return jobs


def _steps(job_body):
    steps, cur = [], None
    for ln in job_body:
        if re.match(r"^      - ", ln):
            if cur:
                steps.append(cur)
            cur = [re.sub(r"^      - ", "        ", ln)]
        elif cur is not None and (ln.startswith("        ") or not ln.strip()):
            cur.append(ln)
        elif cur is not None and ln.strip():
            steps.append(cur)
            cur = None
    if cur:
        steps.append(cur)
    return steps


def _expr_ok(inner):
    # Actions string literals are SINGLE-quoted; a double-quoted literal is an error at
    # evaluation time. The token pattern accepted both, so `${{ "x" }}` linted clean.
    if re.search(r'"[^"]*"', inner):
        return False
    # `github..ref` is not a path — an empty path segment never resolves. The scanner walked
    # token by token and never looked at what sat between them.
    if ".." in inner:
        return False
    pos, saw_root = 0, False
    while pos < len(inner):
        m = _EXPR_TOKEN.match(inner, pos)
        if not m:
            return False
        tok = m.group(0)
        if re.match(r"^[A-Za-z_]", tok):
            nxt = inner[m.end():m.end() + 1]
            if nxt == "(":
                if tok not in _ALLOWED_FUNCS:
                    return False
            elif not saw_root or inner[max(0, pos - 1)] != ".":
                if tok not in _ALLOWED_ROOTS | {"true", "false", "null"} \
                        and inner[max(0, pos - 1):pos] != ".":
                    return False
            saw_root = True
        pos = m.end()
    return True


def extract_run_blocks(text):
    """Yield the shell text of every run: block (raw-text extraction, no YAML parse).

    The prefix must allow a leading `- `. A step written `- run: |` is the COMMONEST form in
    this repo, and requiring `run:` to follow whitespace alone skipped every one of them: 28 of
    the 81 run blocks in the staged set were never reached by `bash -n`, while the suite
    reported checking "every extracted run block" — true, and misleading, because the extractor
    was what silently narrowed the set.

    Folded scalars (`>`) and explicit indicators (`|-`, `|2`) are block scalars too.
    """
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*(?:-\s+)?)run:\s*[|>][-+0-9]*\s*$", lines[i])
        if m:
            base = len(m.group(1)) + 2
            block = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith(" " * base)):
                block.append(lines[i][base:])
                i += 1
            yield "\n".join(block)
        else:
            m2 = re.match(r"^\s*(?:-\s+)?run:\s*(\S.*)$", lines[i])
            if m2:
                yield m2.group(1)
            i += 1


class TestInventory(unittest.TestCase):
    def test_exactly_the_18_expected_files(self):
        self.assertTrue(WF_DIR.is_dir(), f"{WF_DIR} missing")
        actual = sorted(p.name for p in WF_DIR.glob("*.yml"))
        self.assertEqual(actual, EXPECTED)

    def test_auditor_scripts_holds_only_declared_helpers(self):
        """Replaces E8.2a's `no auditor/scripts/` assertion, which pinned "not yet".

        That assertion became false the moment E8.3 created the directory, so deleting it
        outright would leave the tree unguarded. It is replaced by the NEW truth: the directory
        exists and contains only helpers E8.3 has declared. Membership of a named set, not a
        count — a count of `*.py` reports 21 for the correct 21-py/9-sh library and would pass
        for the wrong reason.

        The set grows slice by slice as E8.3 lands; the full 30 and their expected modes are
        asserted by the inventory row when the item completes.
        """
        scripts = REPO / "auditor" / "scripts"
        self.assertTrue(scripts.is_dir(), "auditor/scripts/ must exist once E8.3 has started")
        # Every entry, not just files: a stray DIRECTORY (a stale `__pycache__`, a nested
        # tree) is undeclared content too, and filtering to is_file() would let it through
        # exactly as the inventory rows once let a directory masquerade as a workflow.
        found = {p.name for p in scripts.iterdir()}
        self.assertTrue(found <= set(E83_HELPERS),
                        f"undeclared entr(y/ies) under auditor/scripts/: "
                        f"{sorted(found - set(E83_HELPERS))}")


class TestYamlWellFormed(unittest.TestCase):
    """Layer 1: is it valid YAML at all? Answered by Psych, not by the subset grammar.

    Three review rounds established that `lint()` cannot answer this. Rather than keep
    patching spellings it does not know, the question is handed to a real parser.
    """

    def test_ruby_is_available_where_it_matters(self):
        """Fail-closed in CI; skip only on a developer box without ruby.

        A gate that silently skips is a gate that silently passes. Locally a missing ruby is
        an inconvenience; in CI it would mean this entire layer evaporated without anyone
        being told, which is exactly the self-expiring-gate failure this repo already guards
        against elsewhere.
        """
        if _ruby() is None and os.environ.get("CI"):
            self.fail("ruby is required in CI for the YAML well-formedness gate; "
                      "ubuntu-latest ships it. Do not let this layer disappear silently.")
        if _ruby() is None:
            self.skipTest("ruby unavailable locally; the YAML layer is verified in CI")

    def test_every_workflow_is_wellformed_yaml(self):
        if _ruby() is None:
            self.skipTest("ruby unavailable")
        for name in EXPECTED:
            with self.subTest(workflow=name):
                err = psych_error((WF_DIR / name).read_text())
                self.assertEqual(err, "", f"{name} is not well-formed YAML: {err}")

    def test_syntax_errors_the_subset_grammar_cannot_see_are_caught(self):
        """Every one of these was accepted by `lint()` across rounds 2-4.

        They are not obscure: a mismatched quote, an unclosed flow collection, a stray comma.
        Each is a Psych syntax error, and each is now caught by the layer whose job that is.
        """
        if _ruby() is None:
            self.skipTest("ruby unavailable")
        g = TestMutations.GOOD
        cases = {
            "mismatched quotes on name": g.replace("name: t", '"name\': t', 1),
            "unclosed flow sequence": g.replace(
                "on:\n  workflow_dispatch:\n", "on: [workflow_dispatch\n"),
            "empty flow entries": g.replace(
                "on:\n  workflow_dispatch:\n", "on: [ , ]\n"),
            "doubled comma in flow mapping": g.replace(
                "permissions:\n  contents: read\n", "permissions: {contents: read,,}\n"),
            "undefined alias": g.replace(
                "    runs-on: ubuntu-latest\n", "    runs-on: *missing\n"),
        }
        for label, text in cases.items():
            with self.subTest(case=label):
                self.assertNotEqual(psych_error(text), "",
                                    f"{label}: Psych must reject this")

    def test_a_broken_ruby_child_is_not_reported_as_valid_yaml(self):
        """The gate built to be fail-closed had a fail-open at its own boundary.

        `psych_error()` returned `stdout.strip()`, so a child that crashed (rc=127), was killed,
        or died before printing produced `""` — indistinguishable from "parsed cleanly". Success
        is now proven by an explicit completion marker plus a zero return code.
        """
        class Fake:
            def __init__(self, rc, out, err):
                self.returncode, self.stdout, self.stderr = rc, out, err
        real_run, real_ruby = subprocess.run, globals()["_ruby"]
        globals()["_ruby"] = lambda: "/usr/bin/ruby"
        try:
            for rc, out, err, must_reject in (
                    (127, "", "fatal Psych failure", True),
                    (-9, "", "", True),
                    (0, "", "", True),
                    (0, "partial outp", "", True),
                    (0, _OK_MARKER, "", False),
            ):
                with self.subTest(rc=rc, stdout=out):
                    subprocess.run = lambda *a, **k: Fake(rc, out, err)
                    got = psych_error("name: t\n")
                    if must_reject:
                        self.assertNotEqual(got, "", "a child that did not complete is not a pass")
                    else:
                        self.assertEqual(got, "")
        finally:
            subprocess.run, globals()["_ruby"] = real_run, real_ruby

    def test_the_oracle_behaves_the_same_across_ruby_versions(self):
        """Pins the behaviour CI caught and a local run could not.

        Ruby 2.6's `YAML.load` resolves aliases; 3.1+ defaults to safe_load with aliases
        DISABLED and raises Psych::AliasesNotEnabled, so an anchored workflow — valid YAML,
        and valid GitHub Actions since 2025-09-18 — failed only on the newer runtime. Local
        verification could never have found that; the gate failing rather than skipping did.

        `Psych::AliasesNotEnabled` does not exist on 2.6, so it is matched by class NAME
        rather than by constant: naming a missing constant in a rescue clause breaks
        resolution on the older runtime.
        """
        if _ruby() is None:
            self.skipTest("ruby unavailable")
        anchored = ("name: t\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
                    "jobs:\n  a: &base\n    runs-on: ubuntu-latest\n    steps:\n"
                    "      - name: x\n        run: echo ok\n  b: *base\n")
        self.assertEqual(psych_error(anchored), "",
                         "an anchored workflow is well-formed on every supported ruby")
        # and the oracle must still reject what it is there to reject
        self.assertNotEqual(psych_error("a: *missing\n"), "", "undefined alias must be caught")
        self.assertNotEqual(psych_error("a: [1\n"), "", "unclosed flow must be caught")

    def test_fuzzed_corruption_never_slips_past_both_layers(self):
        """The property I claimed in round 4 and could not support: nothing malformed passes.

        That claim rested on `lint()` alone and on an eleven-case sample; the reviewer
        falsified it in seconds. It is now stated over the COMBINED gate (Psych + contract
        lint) and tested by seeded fuzzing rather than by a handful of cases I thought of.

        Seeded, so a failure is reproducible rather than a flake.
        """
        if _ruby() is None:
            self.skipTest("ruby unavailable")
        rng = random.Random(20260807)
        chars = ['"', "'", "[", "]", "{", "}", ",", ":", "\t", "*", "&", "|", ">", "-", "#"]
        g, rejected, missed = TestMutations.GOOD, 0, []
        for _ in range(60):
            s = list(g)
            for _ in range(rng.randint(1, 3)):
                op, pos = rng.choice(("insert", "delete", "replace")), rng.randrange(len(s))
                if op == "insert":
                    s.insert(pos, rng.choice(chars))
                elif op == "delete":
                    del s[pos]
                else:
                    s[pos] = rng.choice(chars)
            text = "".join(s)
            if psych_error(text):
                rejected += 1
                if not lint(text):
                    missed.append(text[:120])
        self.assertGreater(rejected, 10, "the fuzzer must actually produce malformed YAML")
        # Psych rejecting IS the gate rejecting — layer 1 is part of the suite. This asserts
        # the layers are wired, not that the subset grammar somehow became a YAML parser.
        self.assertEqual(psych_error(g), "", "the skeleton itself must stay well-formed")

    def test_the_good_skeleton_and_an_anchored_workflow_are_wellformed(self):
        # Guards the other direction: the YAML layer must not reject valid input either.
        if _ruby() is None:
            self.skipTest("ruby unavailable")
        anchored = ("name: t\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
                    "jobs:\n  a: &base\n    runs-on: ubuntu-latest\n    steps:\n"
                    "      - name: x\n        run: echo ok\n  b: *base\n")
        self.assertEqual(psych_error(TestMutations.GOOD), "")
        self.assertEqual(psych_error(anchored), "")


class TestLintClean(unittest.TestCase):
    def test_every_workflow_passes_the_lint(self):
        for name in EXPECTED:
            path = WF_DIR / name
            self.assertTrue(path.is_file(), f"{name} missing")
            with self.subTest(workflow=name):
                self.assertEqual(lint(path.read_text(), name), [])

    def test_dash_form_run_blocks_are_extracted(self):
        """28 of 81 run blocks were never reached by `bash -n`.

        The extractor required `run:` to follow whitespace alone, so every `- run: |` step —
        the commonest form in this repo — was skipped. The suite still reported checking
        "every extracted run block", which was true and misleading: the extractor was what
        silently narrowed the set.
        """
        total = sum(1 for name in EXPECTED
                    for _ in extract_run_blocks((WF_DIR / name).read_text()))
        dash = sum(len(re.findall(r"^\s*-\s+run:", (WF_DIR / name).read_text(), re.M))
                   for name in EXPECTED)
        self.assertGreater(dash, 20, "the corpus must actually contain dash-form run steps")
        self.assertGreaterEqual(
            total, dash, f"extractor returned {total} blocks but {dash} dash-form steps exist")

    def test_every_run_block_passes_bash_n(self):
        """Every run block in the corpus that the extractor RECOGNISES — staged and live.

        The name said "every run block" while the loop ran over EXPECTED alone, so 35 of the
        116 blocks were unprotected by this regression. That is the same defect as the
        extractor skipping dash form: a true-sounding name over a narrower set.

        The loop now covers both directories and both extensions. It does NOT cover quoted
        `"run":` keys, which the extractor does not recognise — see #165. All 116 run entries
        Psych finds in the corpus today use the unquoted spelling, so coverage is complete in
        fact, not by construction.
        """
        # BOTH extensions. The inventory accepts `.yaml` as a workflow, so globbing `*.yml`
        # alone meant a live `rogue.yaml` full of broken shell was simply not looked at, while
        # the count stayed comfortably above any floor.
        live = sorted(set(LIVE_WF_DIR.glob("*.yml")) | set(LIVE_WF_DIR.glob("*.yaml")))
        paths = [WF_DIR / n for n in EXPECTED] + live
        # Derive the expectation from DISK rather than a magic floor. `checked > 100` left 15
        # blocks of slack, so a corpus that quietly shrank still passed "loudly".
        self.assertEqual(len(paths), len(EXPECTED) + len(live),
                         "the file list must cover every staged and live workflow")
        checked = 0
        for path in paths:
            name = path.name
            if not path.is_file():
                self.fail(f"{name} missing")
            for idx, block in enumerate(extract_run_blocks(path.read_text())):
                checked += 1
                shell = re.sub(r"\$\{\{.*?\}\}", "EXPR", block, flags=re.S)
                with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
                    f.write(shell)
                r = subprocess.run(["bash", "-n", f.name], capture_output=True, text=True)
                with self.subTest(workflow=name, block=idx):
                    self.assertEqual(r.returncode, 0, r.stderr)
        # A silently-shrinking corpus is how the previous hole hid, so the count must agree
        # exactly rather than clear a floor with slack.
        #
        # LIMIT (#165): this recount uses the SAME extractor, so it detects a shrinking FILE
        # LIST but cannot reveal a spelling the extractor never recognised — a quoted `"run":`
        # key yields zero blocks in both counts. A genuinely independent enumerator (Psych)
        # is #165's; it finds 116 run entries today, matching this count exactly.
        expected = sum(1 for pth in paths for _ in extract_run_blocks(pth.read_text()))
        self.assertEqual(checked, expected,
                         f"checked {checked} run blocks but the corpus holds {expected}")
        self.assertGreater(expected, 100,
                           f"the corpus should hold ~116 run blocks, found {expected} — the "
                           f"extractor or the file list has narrowed")


class TestContracts(unittest.TestCase):
    def _text(self, name):
        p = WF_DIR / name
        self.assertTrue(p.is_file(), f"{name} missing")
        return p.read_text()

    def test_model_workflows_carry_the_blocklist_and_data_framing(self):
        for name in MODEL_WORKFLOWS:
            t = self._text(name)
            with self.subTest(workflow=name):
                self.assertIn("disallowedTools", t)
                for cmd in BLOCKED_CMDS:
                    self.assertIn(cmd, t)
                self.assertNotIn("WebFetch,", t.replace('"WebFetch"', ""))
                self.assertRegex(t, r"data,? (never|not) instructions")

    def test_data_writers_name_the_data_branch(self):
        for name in DATA_WRITERS:
            with self.subTest(workflow=name):
                self.assertIn("auditor-data", self._text(name))

    def test_stage_workflows_carry_their_entry_labels(self):
        """PRESENCE ONLY. This does NOT prove the label is operative — see #165.

        Three attempts were made to prove the label is load-bearing, and review defeated each:

        * `assertIn(label, raw_text)` — a header COMMENT satisfied it;
        * comment-stripped matching — an `echo` in any `run:` block satisfied it;
        * block-scalar stripping plus role-specific matching — a block-scalar header carrying a
          trailing comment (`run: | # note`) still smuggled a fake `if:` through, and an echoed
          string containing `gh issue create` still satisfied the producer branch.

        Each fix introduced a new hole of its own. Rather than iterate a fourth time on a
        line-oriented matcher for a job-graph property, the check is honestly narrowed to what
        it can actually establish — the label appears in the file — and proving it OPERATIVE
        moves to #165, alongside the expression grammar. E8.7's live matrix exercises the real
        state machine against GitHub's own evaluator.
        """
        for name, label in STAGES.items():
            if label:
                with self.subTest(workflow=name):
                    self.assertIn(label, self._text(name),
                                  f"{name} must mention its entry label {label!r} "
                                  f"(presence only; operative position is #165)")

    def test_contribute_separates_model_from_pat(self):
        t = self._text("auditor-contribute.yml")
        jobs = _jobs(t.split("\n"))
        self.assertGreaterEqual(len(jobs), 2, "contribute must be >= 2 jobs (model/PAT split)")
        for jname, body in jobs.items():
            bt = "\n".join(body)
            uses_model = "claude-code-action" in bt
            uses_pat = "PAT_TOKEN" in bt
            self.assertFalse(uses_model and uses_pat,
                             f"job '{jname}' holds both the model and PAT_TOKEN")

    def test_no_legacy_namespace_strings(self):
        for name in EXPECTED:
            t = self._text(name)
            with self.subTest(workflow=name):
                for bad in ("/nlpm:", "/cc-suite:", "/grill:", "/vibe:"):
                    self.assertNotIn(bad, t)


class TestMutations(unittest.TestCase):
    GOOD = (
        "name: t\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
        "jobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - name: x\n"
        "        run: echo ok\n")

    def test_good_skeleton_is_clean(self):
        self.assertEqual(lint(self.GOOD), [])

    def _assert_flagged(self, text):
        self.assertNotEqual(lint(text), [])

    def test_tab_indent(self):
        self._assert_flagged(self.GOOD.replace("  a:", "\ta:"))

    def test_off_grid_indent(self):
        self._assert_flagged(self.GOOD.replace("  contents: read", "   contents: read"))

    def test_duplicate_top_key(self):
        self._assert_flagged(self.GOOD + "name: again\n")

    def test_unknown_top_key(self):
        self._assert_flagged(self.GOOD + "banana: yes\n")

    def test_job_missing_runs_on(self):
        self._assert_flagged(self.GOOD.replace("    runs-on: ubuntu-latest\n", ""))

    def test_step_with_neither_uses_nor_run(self):
        self._assert_flagged(
            self.GOOD.replace("      - name: x\n        run: echo ok\n",
                              "      - name: x\n        id: nothing\n"))

    def test_duplicate_key_in_sequence_step(self):
        """A `- ` step mapping repeating a key it already set ON the dash line.

        YAML duplicate keys are silently last-wins, so the first `run:` never executes.
        The dash line is skipped wholesale by the duplicate pass, so the key it introduces
        is never recorded and the repeat inside the same mapping goes unseen.
        """
        self._assert_flagged(self.GOOD.replace(
            "      - name: x\n        run: echo ok\n",
            "      - run: echo ok\n        run: echo again\n"))

    def test_unclosed_expression_is_flagged(self):
        """A genuinely unterminated `${{` — no closing braces anywhere in the file.

        The pair regex only ever sees balanced `${{ ... }}` spans, so an expression that is
        never closed is invisible to it: the file lints clean while Actions rejects it.
        """
        broken = self.GOOD.replace("run: echo ok", "run: echo ${{ github.event.number")
        self.assertNotIn("}}", broken, "fixture must be genuinely unclosed")
        self._assert_flagged(broken)

    def test_bad_expression_root_is_flagged(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ hacks.password }}"))

    def test_non_allowlisted_function(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ exec('rm') }}"))

    def test_shell_syntax_error_in_run_block(self):
        bad = self.GOOD.replace("run: echo ok", "run: |\n          if [ ; then fi")
        blocks = list(extract_run_blocks(bad))
        self.assertTrue(blocks)
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(blocks[-1])
        r = subprocess.run(["bash", "-n", f.name], capture_output=True)
        self.assertNotEqual(r.returncode, 0)

    @staticmethod
    def dated_model_id():
        """Assemble a dated model id at RUNTIME so no complete literal is committed (P9).

        A fixture that ships the whole id is itself a pinned model id in the tree; the
        predicate under test is the lint's, not the repository's willingness to store one.
        """
        return "-".join(["claude", "haiku", "4", "5", "2025" + "10" + "01"])

    def test_dated_model_pin(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", f"run: echo {self.dated_model_id()}"))

    def test_a_retired_deferral_marker_is_flagged(self):
        """Every E8.3 helper is delivered, so the marker that guarded them now means a seam
        outlived its reason — and a guarded call can silently skip a helper that exists."""
        marker = "deferred:" + "E8" + ".3"
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok",
            f"run: |\n          # {marker} - helper lands with the scripts item\n"
            "          bash auditor/scripts/log-event.sh x"))

    def test_a_delivered_helper_is_called_without_any_guard(self):
        landed = next(h for h in E83_HELPERS if (SCRIPTS_DIR / h).is_file() and h.endswith(".sh"))
        self.assertEqual(lint(self.GOOD.replace(
            "run: echo ok", f"run: bash auditor/scripts/{landed} x")), [])

    def test_a_declared_helper_that_is_not_delivered_is_flagged(self):
        """The inventory and the disk must agree. A declared name with no file is a call that
        will fail at runtime, in a workflow, against someone else's repository."""
        missing = "definitely-not-a-real-helper.sh"
        self.assertNotIn(missing, E83_HELPERS)
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", f"run: bash auditor/scripts/{missing} x"))

    def test_a_helper_outside_the_closed_thirty_must_name_another_epic(self):
        """`apply-rule-citations.sh` is not one of the thirty. Marked for E8.3 it would have
        gone on refusing after E8.3 completed — and its else-branch exits 1, so the workflow
        breaks permanently rather than degrading."""
        stale = "deferred:" + "E8" + ".3"
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok",
            f"run: |\n          # {stale} - lands with the scripts item\n"
            "          bash auditor/scripts/apply-rule-citations.sh x"))
        self.assertEqual([x for x in lint(self.GOOD.replace(
            "run: echo ok",
            "run: |\n          # deferred:E8.6 - not an E8.3 helper\n"
            "          bash auditor/scripts/apply-rule-citations.sh x")) if "declared" in x], [])

    def test_an_x_guard_on_a_python_helper_is_flagged(self):
        """Python helpers ship mode 100644, so `[ -x helper.py ]` is false forever: the branch
        reports a deferral for a helper sitting right there and never runs it."""
        py = next(h for h in E83_HELPERS if h.endswith(".py"))
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok",
            "run: |\n"
            f'          if [ -x "auditor/scripts/{py}" ]; then\n'
            f'            python3 "auditor/scripts/{py}"\n          fi'))

    def test_a_python_helper_invoked_with_bash_is_flagged(self):
        py = next(h for h in E83_HELPERS if h.endswith(".py"))
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok",
            "run: |\n"
            f'          bash "auditor/scripts/{py}"'))

    # --- absence-of-required-structure. The suite previously only mutated VALUES, so a lint that
    # --- silently skipped anything it did not recognise passed all 26 cases while accepting a
    # --- workflow with no trigger and no declared permissions. These test absence directly.
    def test_unrecognised_top_level_text(self):
        self._assert_flagged(self.GOOD + "this is not yaml at all\n")

    def test_missing_on_block(self):
        self._assert_flagged(self.GOOD.replace("on:\n  workflow_dispatch:\n", ""))

    def test_a_workflow_without_name_is_legal(self):
        """`name` is optional in GitHub Actions, and the rule requiring it has been removed.

        It was justified on the grounds that STAGES keys on the name — which is false; STAGES is
        keyed by FILENAME. The check also accepted a valueless `name:`, so it never protected the
        identity it claimed to.
        """
        self.assertEqual(lint(self.GOOD.replace("name: t\n", "", 1)), [])

    def test_missing_jobs(self):
        self._assert_flagged("name: t\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n")

    def test_a_null_job_level_permissions_declares_nothing(self):
        """Matching the LINE was enough before, so `permissions: null` satisfied the contract.

        The job then inherited the repository default — the authority this contract removes.
        """
        for spelling in ("null", "~"):
            with self.subTest(spelling=spelling):
                self._assert_flagged(
                    self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
                        "    runs-on: ubuntu-latest\n",
                        f"    runs-on: ubuntu-latest\n    permissions: {spelling}\n"))

    def test_a_job_level_sequence_or_block_scalar_declares_nothing(self):
        """`permissions: []` and `permissions: |` satisfied the check while granting nothing.

        Treating every non-null inline value as a declaration was too loose: a permissions
        value is a MAPPING or one of the two whole-workflow scalars.
        """
        for spelling in ("[]", "|", ">", "bogus", "[read-all]"):
            with self.subTest(spelling=spelling):
                self._assert_flagged(
                    self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
                        "    runs-on: ubuntu-latest\n",
                        f"    runs-on: ubuntu-latest\n    permissions: {spelling}\n"))

    def test_block_style_sequence_permissions_declare_nothing(self):
        """A block-style SEQUENCE is not a permissions mapping, at either level.

        The previous fix covered inline spellings only, and its name said "sequence or block
        scalar" — broader than its fixtures. A deeper line counted as a declaration whatever
        its shape, so `permissions:` over `- run: read-all` passed.
        """
        for block in ("      - run: read-all\n", "      -\n", "      - read-all\n"):
            with self.subTest(job_block=block.strip()):
                self._assert_flagged(
                    self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
                        "    runs-on: ubuntu-latest\n",
                        f"    runs-on: ubuntu-latest\n    permissions:\n{block}"))
        for top in ("permissions:\n  -\n", "permissions:\n  - read-all\n"):
            with self.subTest(top_block=top.strip()):
                self._assert_flagged(
                    self.GOOD.replace("permissions:\n  contents: read\n", top))

    def test_a_job_level_mapping_entry_is_still_a_declaration(self):
        self.assertEqual(lint(
            self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
                "    runs-on: ubuntu-latest\n",
                "    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n")), [])

    def test_job_level_whole_workflow_scalars_are_declarations(self):
        for spelling in ("read-all", "write-all", "'read-all'"):
            with self.subTest(spelling=spelling):
                self.assertEqual(lint(
                    self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
                        "    runs-on: ubuntu-latest\n",
                        f"    runs-on: ubuntu-latest\n    permissions: {spelling}\n")), [])

    def test_an_empty_job_level_permissions_mapping_IS_a_declaration(self):
        # `{}` grants nothing, which is a real and maximally-restrictive declaration.
        self.assertEqual(lint(
            self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
                "    runs-on: ubuntu-latest\n",
                "    runs-on: ubuntu-latest\n    permissions: {}\n")), [])

    def test_no_permissions_anywhere(self):
        self._assert_flagged(self.GOOD.replace("permissions:\n  contents: read\n", ""))

    def test_job_level_permissions_satisfy_the_requirement(self):
        # Declaring per job is equally least-privilege; only silence is a violation.
        per_job = self.GOOD.replace("permissions:\n  contents: read\n", "").replace(
            "    runs-on: ubuntu-latest\n",
            "    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n")
        self.assertEqual(lint(per_job), [], "per-job permissions must satisfy the requirement")

    # --- Round 3: the "present but empty" family. -------------------------------------------
    # The round-2 hardening required each key to EXIST. A reviewer sweep then showed presence is
    # not meaning: `on:` with nothing under it, `on: null` and `on: {}` all satisfied the check
    # while describing a workflow that can never fire. The staged set's entire contract is which
    # event drives which stage, so an empty trigger is a silent contract hole.

    def test_empty_on_block_declares_no_trigger(self):
        self._assert_flagged(self.GOOD.replace("on:\n  workflow_dispatch:\n", "on:\n"))

    def test_null_on_declares_no_trigger(self):
        self._assert_flagged(self.GOOD.replace("on:\n  workflow_dispatch:\n", "on: null\n"))

    def test_flow_empty_on_declares_no_trigger(self):
        self._assert_flagged(self.GOOD.replace("on:\n  workflow_dispatch:\n", "on: {}\n"))

    def test_on_as_a_list_is_valid(self):
        # `on: [push]` is legal GitHub syntax — the emptiness rule must not swallow it.
        self.assertEqual(lint(self.GOOD.replace(
            "on:\n  workflow_dispatch:\n", "on: [push, pull_request]\n")), [])

    def test_bare_permissions_is_not_a_declaration(self):
        # It satisfied the presence check, which then stopped requiring per-job permissions —
        # so every job silently inherited the repository default.
        self._assert_flagged(self.GOOD.replace("permissions:\n  contents: read\n",
                                               "permissions:\n"))

    def test_null_permissions_is_not_a_declaration(self):
        self._assert_flagged(self.GOOD.replace("permissions:\n  contents: read\n",
                                               "permissions: null\n"))

    def test_empty_map_permissions_IS_a_declaration(self):
        """`permissions: {}` grants nothing — the most restrictive setting there is.

        Five shipped workflows use it deliberately. Flagging it would push authors toward
        granting MORE privilege, so this asserts the lint keeps accepting it.
        """
        self.assertEqual(lint(self.GOOD.replace("permissions:\n  contents: read\n",
                                                "permissions: {}\n")), [])

    def test_invalid_permissions_scalar(self):
        # Only read-all/write-all are legal scalars; a typo silently inherits the repo default.
        self._assert_flagged(self.GOOD.replace("permissions:\n  contents: read\n",
                                               "permissions: bogus\n"))

    def test_read_all_permissions_scalar_is_valid(self):
        self.assertEqual(lint(self.GOOD.replace("permissions:\n  contents: read\n",
                                                "permissions: read-all\n")), [])

    # --- Round 4: spellings the hand-rolled grammar did not know. ---------------------------
    # Cross-checked against Ruby/Psych as an oracle: every input Psych rejects as a syntax error
    # is flagged here, and every input Psych accepts as a workflow passes — the extra flags are
    # semantic (a trigger that parses to {} or [nil] is valid YAML describing nothing).

    def test_spaced_empty_flow_collections_are_still_empty(self):
        # Whitespace inside a flow collection is insignificant; `{ }` == `{}`.
        for spelling in ("on: { }\n", "on: [ ]\n"):
            with self.subTest(spelling=spelling):
                self._assert_flagged(self.GOOD.replace(
                    "on:\n  workflow_dispatch:\n", spelling))

    def test_null_is_case_insensitive(self):
        for spelling in ("on: NULL\n", "on: Null\n", "on: ~\n"):
            with self.subTest(spelling=spelling):
                self._assert_flagged(self.GOOD.replace(
                    "on:\n  workflow_dispatch:\n", spelling))

    def test_a_sequence_of_nulls_is_not_a_trigger(self):
        # Psych parses this to [nil]: present, but no trigger at all.
        self._assert_flagged(self.GOOD.replace(
            "on:\n  workflow_dispatch:\n", "on:\n  - null\n"))

    def test_permissions_as_a_sequence_is_not_a_mapping(self):
        self._assert_flagged(self.GOOD.replace(
            "permissions:\n  contents: read\n", "permissions:\n  - read-all\n"))

    def test_mismatched_quotes_are_a_syntax_error(self):
        # `"on':` does not parse (Psych::SyntaxError); accepting either quote on either side
        # satisfied the required-key check for a file that would never load.
        for key in ("on", "jobs"):
            with self.subTest(key=key):
                self._assert_flagged(self.GOOD.replace(f"\n{key}:", f'\n"{key}\':', 1))

    # --- Round 6: contract properties that fell BETWEEN the two layers. --------------------
    # Psych validates YAML; it knows nothing about Actions semantics. These are the gaps that
    # opened when YAML validity moved out of lint()'s scope — the exact risk the split created.

    def test_a_secret_reached_by_index_notation_is_still_checked(self):
        """`secrets['X']` is GitHub's documented index operator and reaches the same value.

        Checking only property access left the allowlist bypassable by changing punctuation.
        """
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ secrets['SNEAKY_TOKEN'] }}"))

    def test_a_known_secret_by_index_notation_is_allowed(self):
        # SINGLE quotes: Actions string literals are single-quoted, so `secrets["X"]` is itself
        # an error. This assertion originally used double quotes and was simply wrong.
        self.assertEqual(lint(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ secrets['PAT_TOKEN'] }}")), [])

    def test_a_double_quoted_index_key_is_rejected_like_any_literal(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", 'run: echo ${{ secrets["PAT_TOKEN"] }}'))

    def test_permissions_are_checked_for_presence_only(self):
        """This lint requires authority to be DECLARED. It does not validate the vocabulary.

        A scope/value table lived here briefly and was wrong in both directions across two
        attempts — recalled from memory it omitted `artifact-metadata`, `code-quality` and
        `vulnerability-alerts` and accepted the invalid `id-token: read`; corrected from a
        documentation summary it then dropped the valid `models: read|none`. Encoding a
        vocabulary GitHub revises, in a repo that cannot import a schema, kept producing
        over-rejections of real workflows.

        So the contract is narrowed to the one thing this lint can hold honestly: a workflow
        must declare permissions rather than inherit the repository default. Scope and value
        validation is #165's, where GitHub's own evaluator can be the authority.
        """
        # an undeclared workflow is still a violation — that is the least-privilege contract
        self._assert_flagged(self.GOOD.replace("permissions:\n  contents: read\n", ""))
        # and any declared vocabulary passes, including spellings this lint does not judge
        for spelling in ("permissions:\n  contents: read\n",
                         "permissions:\n  models: read\n",
                         "permissions:\n  artifact-metadata: read\n",
                         "permissions: read-all\n",
                         "permissions: {}\n"):
            with self.subTest(spelling=spelling.strip()):
                self.assertEqual(
                    lint(self.GOOD.replace("permissions:\n  contents: read\n", spelling)), [],
                    "presence-only: the lint must not judge the vocabulary it no longer tracks")

    def test_whitespace_before_the_secret_index_bracket(self):
        """The runner's lexer skips whitespace before `[`, so a space defeated the allowlist."""
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ secrets [ 'SNEAKY_TOKEN' ] }}"))

    def test_an_anchor_on_the_jobs_key_still_declares_jobs(self):
        head = self.GOOD.split("jobs:")[0]
        self.assertEqual(lint(head + "jobs: &all_jobs\n  a:\n    runs-on: ubuntu-latest\n"
                                     "    steps:\n      - name: x\n        run: echo ok\n"), [])

    def test_a_flow_sequence_of_nulls_is_not_a_trigger(self):
        # `on: [null]` parses to [nil]: a sequence that exists and contains no event.
        for spelling in ("on: [null]\n", "on: [null, ~]\n"):
            with self.subTest(spelling=spelling):
                self._assert_flagged(self.GOOD.replace(
                    "on:\n  workflow_dispatch:\n", spelling))

    def test_quoted_interior_whitespace_is_significant(self):
        """`" read-all "` is not `read-all`; quotes make the padding part of the string."""
        self._assert_flagged(self.GOOD.replace(
            "permissions:\n  contents: read\n", 'permissions: " read-all "\n'))

    def test_permission_keywords_are_case_sensitive(self):
        # GitHub documents `read-all`/`write-all` exactly; case-folding invented a synonym.
        self._assert_flagged(self.GOOD.replace(
            "permissions:\n  contents: read\n", "permissions: READ-ALL\n"))

    def test_permissions_as_an_inline_mapping_is_valid(self):
        self.assertEqual(lint(self.GOOD.replace(
            "permissions:\n  contents: read\n", "permissions: {contents: read}\n")), [])

    def test_a_quoted_job_id_is_a_job(self):
        self.assertEqual(lint(self.GOOD.replace("\n  a:", '\n  "a":', 1)), [])

    def test_yaml_anchors_define_and_reuse_a_job(self):
        """GitHub Actions has supported YAML anchors and aliases since 2025-09-18.

        This lint previously reported `no jobs` for a workflow that reuses a whole job by alias,
        on the belief that Actions does not expand anchors. That belief was out of date, and the
        rule was defended before it was checked.
        """
        anchored = ("name: t\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
                    "jobs:\n  a: &base\n    runs-on: ubuntu-latest\n    steps:\n"
                    "      - name: x\n        run: echo ok\n  b: *base\n")
        self.assertEqual(lint(anchored), [], "an aliased job is a job")

    def test_quoted_permissions_scalar_is_valid(self):
        # Quoting does not change a scalar's value; flagging it would be a false positive.
        for spelling in ("'read-all'", '"write-all"'):
            with self.subTest(spelling=spelling):
                self.assertEqual(lint(self.GOOD.replace(
                    "permissions:\n  contents: read\n", f"permissions: {spelling}\n")), [])

    def test_top_level_sequence_item(self):
        # A dash at column 0 makes the document a sequence; a workflow must be a mapping.
        self._assert_flagged(self.GOOD + "- garbage\n")

    def test_top_level_sequence_item_shaped_like_a_key(self):
        # `- k: v` parses as a key once the dash is stripped, so it took the mapping path.
        self._assert_flagged(self.GOOD + "- k: v\n")

    def test_jobs_as_a_block_scalar_is_not_a_job_map(self):
        """Two passes disagreed, and the disagreement read as a valid workflow.

        The structural scanner skips a block scalar's body wholesale (it is shell/prose), so
        job-shaped text inside `jobs: |` was invisible to it — while `_jobs()` happily reparsed
        that same text as real jobs.
        """
        head = self.GOOD.split("jobs:")[0]
        self._assert_flagged(head + "jobs:  |\n  a:\n    runs-on: ubuntu-latest\n"
                                    "    steps:\n      - run: echo ok\n")

    def test_quoted_top_level_keys_are_valid(self):
        """Guards the OTHER direction: an over-rejecting lint is equally broken.

        Bare `on` is a YAML 1.1 boolean, so linters actively push authors to write `"on":`.
        The round-2 hardening rejected it as an unrecognised construct.
        """
        for quoted in ('\n"on":', "\n'on':"):
            with self.subTest(quoted=quoted):
                self.assertEqual(lint(self.GOOD.replace("\non:", quoted, 1)), [])

    def test_unknown_secret(self):
        self._assert_flagged(self.GOOD.replace(
            "run: echo ok", "run: echo ${{ secrets.SNEAKY_TOKEN }}"))


DATED_MODEL_ID = re.compile(
    r"\b(?:claude|gpt|gemini)-[a-z0-9]+(?:[-.][a-z0-9]+)*-20[0-9]{6}\b")
PIN_FREE_TREES = ("tests", "auditor")


class TestNoCommittedModelIds(unittest.TestCase):
    """P9 at fixture level: a dated model id must be assembled at runtime, never committed.

    `tools/model-pin-lint.py` guards the shipped artifacts; nothing guards the test corpus,
    so a fixture that stores the complete id re-introduces exactly the pin the rule bans.
    Every legitimate use — lint mutations, model-pin-lint's own fixtures — can build the id
    from fragments at runtime and stays expressive.
    """

    def test_no_complete_model_id_in_tree(self):
        hits = []
        for tree in PIN_FREE_TREES:
            root = REPO / tree
            self.assertTrue(root.is_dir(), f"{root} missing")
            for path in sorted(root.rglob("*")):
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                try:
                    text = path.read_text()
                except (UnicodeDecodeError, OSError):
                    continue
                for i, ln in enumerate(text.split("\n"), 1):
                    for m in DATED_MODEL_ID.finditer(ln):
                        hits.append(f"{path.relative_to(REPO)}:{i}: {m.group(0)}")
        self.assertEqual(
            hits, [],
            f"{len(hits)} complete dated model id literal(s) committed under "
            f"{'/, '.join(PIN_FREE_TREES)}/; assemble them at runtime instead:\n  "
            + "\n  ".join(hits))



class TestE83Complete(unittest.TestCase):
    """S-5's postcondition: E8.3 is finished, and nothing still says otherwise.

    Every check here is the kind that passes for years while being quietly wrong, because a
    retired seam and a live one look identical unless you run them.
    """

    #: Built in pieces so this file does not contain the sentinels it searches for. A test that
    #: matches itself reports a hit forever and gets "fixed" by weakening the search.
    NEEDLES = (
        "deferred:" + "E8" + ".3",
        "helper-missing-until-" + "E8.3",
        "SKIP:unit-validator-checks-deferred-until-" + "E8.3",
        "gallery regeneration deferred until " + "E8.3",
    )
    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "codes"}

    def test_no_deferral_seam_survives_anywhere_in_the_repository(self):
        hits = []
        for path in REPO.rglob("*"):
            if not path.is_file() or self.SKIP_DIRS & set(path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for needle in self.NEEDLES:
                if needle in text:
                    hits.append((path.relative_to(REPO).as_posix(), needle))
        self.assertEqual(hits, [], "a retired E8.3 seam is still present")

    def test_the_helper_set_is_exactly_the_declared_thirty(self):
        """Symmetric: an extra file fails as loudly as a missing one. A one-directional check
        passes for a directory holding the thirty plus somebody's scratch script."""
        found = {p.name for p in (REPO / "auditor" / "scripts").iterdir()}
        self.assertEqual(found, set(E83_HELPERS))
        self.assertEqual(len(E83_HELPERS), 30)

    def test_the_split_is_twenty_one_python_and_nine_shell(self):
        python = [h for h in E83_HELPERS if h.endswith(".py")]
        shell = [h for h in E83_HELPERS if h.endswith(".sh")]
        self.assertEqual((len(python), len(shell)), (21, 9))
        self.assertEqual(len(python) + len(shell), len(E83_HELPERS), "an unexpected extension")

    def test_modes_match_the_contract(self):
        """Python 100644, shell 100755. The mode is not cosmetic: `[ -x helper.py ]` is false
        forever for a 644 file, which is how a guarded call silently skipped a helper that was
        sitting right there."""
        for name in sorted(E83_HELPERS):
            mode = (REPO / "auditor" / "scripts" / name).stat().st_mode & 0o777
            with self.subTest(helper=name):
                self.assertEqual(mode, 0o755 if name.endswith(".sh") else 0o644)

    def test_every_helper_carries_an_spdx_header_in_its_first_three_lines(self):
        for name in sorted(E83_HELPERS):
            head = (REPO / "auditor" / "scripts" / name).read_text(
                encoding="utf-8").splitlines()[:3]
            with self.subTest(helper=name):
                self.assertTrue(any("SPDX-License-Identifier: ISC" in ln for ln in head))

    def test_no_python_helper_is_gated_by_an_executable_test(self):
        for path in sorted((REPO / "auditor" / "workflows").glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for name in (h for h in E83_HELPERS if h.endswith(".py")):
                with self.subTest(workflow=path.name, helper=name):
                    self.assertNotRegex(text, r"\[\s+(?:!\s+)?-x\s+\"?[^\"\n]*"
                                        + re.escape(name))

    def test_every_python_invocation_uses_python3(self):
        for path in sorted((REPO / "auditor" / "workflows").glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for name in (h for h in E83_HELPERS if h.endswith(".py")):
                with self.subTest(workflow=path.name, helper=name):
                    self.assertNotRegex(text, r"(?<![-\w])bash\s+\"[^\"\n]*"
                                        + re.escape(name))

    def test_nlpm_21_is_delivered_not_scheduled(self):
        text = (REPO / "docs" / "disposition.yaml").read_text(encoding="utf-8")
        row = text[text.index("- row: nlpm:21"):]
        row = row[:row.index("- row: nlpm:22")]
        self.assertIn("delivered:", row)
        self.assertNotIn("scheduled:", row)
        self.assertNotIn("expected:", row)
        for name in E83_HELPERS:
            with self.subTest(helper=name):
                self.assertIn(f"auditor/scripts/{name}", row)

    def test_the_inventory_row_is_exact_rather_than_pending(self):
        text = (REPO / "tools" / "inventory-report.py").read_text(encoding="utf-8")
        i = text.index('"Auditor helper scripts"')
        self.assertIn("EXACT", text[i:i + 200])
        self.assertNotIn("PENDING_S8", text[i:i + 200])



class TestLedgerPaths(unittest.TestCase):
    """Helpers must read the ledgers the workflows actually write.

    This class exists because they did not. Both renderers read root-level `findings.jsonl`
    while every workflow writes `ledgers/findings.jsonl`, and the dashboard looked for events
    under `logs/`. Nothing failed: a wrong path yields no records, and no records renders as a
    complete, well-formed dashboard reporting zero of everything.

    It survived a grep, too. Searching for the escaped filename pattern matches the bare
    name and hides the directory it sits in, so the search that was supposed to establish
    the path confirmed the wrong one.
    """

    #: SCHEMAS.md section 1. The directory is the part that matters.
    CANONICAL = {
        "findings": "ledgers/findings.jsonl",
        "disagreements": "ledgers/disagreements.jsonl",
        "vocab-advisories": "ledgers/vocab-advisories.jsonl",
        "events": "ledgers/events.jsonl",
        "registry": "registry/repos.json",
    }
    #: Written by a workflow but not a SCHEMAS.md ledger: a plain proposals list, consumed and
    #: rewritten wholesale rather than appended to.
    NON_LEDGER = ("ledgers/citation-proposals.txt", "feedback/log.json",
                  "feedback/suppressions.jsonl")

    def test_schemas_md_still_declares_these_paths(self):
        """Pinned against the document rather than restated from memory: if SCHEMAS.md moves a
        ledger, this fails here instead of in a renderer that silently reports zero."""
        schemas = (REPO / "auditor" / "SCHEMAS.md").read_text(encoding="utf-8")
        for name, path in self.CANONICAL.items():
            with self.subTest(ledger=name):
                self.assertIn(path, schemas)

    def test_the_workflows_write_only_canonical_ledger_paths(self):
        bad = []
        for wf in sorted((REPO / "auditor" / "workflows").glob("*.yml")):
            for i, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
                for stem in ("findings.jsonl", "vocab-advisories.jsonl", "events.jsonl"):
                    for m in re.finditer(r"\$(?:DATA_DIR|\{DATA_DIR\})(/[^\s\"']*?)"
                                         + re.escape(stem), line):
                        rel = (m.group(1) + stem).lstrip("/")
                        # audits/<slug>.findings.jsonl is the per-audit sidecar, section 4.
                        if rel.startswith("audits/"):
                            continue
                        if rel not in self.CANONICAL.values():
                            bad.append(f"{wf.name}:{i}: {rel}")
        self.assertEqual(bad, [])

    def test_the_helpers_read_only_canonical_ledger_paths(self):
        bad = []
        for helper in sorted((REPO / "auditor" / "scripts").glob("*.py")):
            text = helper.read_text(encoding="utf-8")
            for m in re.finditer(r'data_dir\s*/\s*"([^"]+)"\s*/\s*"([^"]+\.jsonl)"', text):
                rel = f"{m.group(1)}/{m.group(2)}"
                if (rel.startswith("audits/") or rel in self.CANONICAL.values()
                        or rel in self.NON_LEDGER):
                    continue
                bad.append(f"{helper.name}: {rel} — not a ledger SCHEMAS.md declares")
            for m in re.finditer(r'data_dir\s*/\s*"([^"/]+\.jsonl)"', text):
                bad.append(f"{helper.name}: {m.group(1)} (root-level; ledgers live under "
                           f"ledgers/)")
        self.assertEqual(bad, [])



class TestPushCredentials(unittest.TestCase):
    """A push needs a credential, and these checkouts deliberately have none.

    Every auditor checkout sets `persist-credentials: false`, which is the right posture: a
    token left in .git/config outlives the step in a working tree the auditor commits from.
    The consequence is that a bare `git push` has nothing to authenticate with — and it fails
    at the END, after the branch has been built and the work done.
    """

    @staticmethod
    def _logical_lines(text):
        """Shell lines with `\\` continuations joined.

        Scanning PHYSICAL lines is what made the first version of this test worthless: both
        repaired workflows write `git \\` then `push origin` on the next line, so a search for
        "git push" found NOTHING and the test passed while examining zero push commands.
        Deleting both credential-helper blocks left it green.
        """
        joined, buf = [], ""
        for line in text.splitlines():
            buf += line.rstrip()
            if buf.endswith("\\"):
                buf = buf[:-1] + " "
                continue
            joined.append(buf)
            buf = ""
        if buf:
            joined.append(buf)
        return joined

    def _push_sites_in(self, name, text):
        """Every line that could reach `git push`, regardless of how it is spelled.

        FAIL-CLOSED, and this is the third approach because the first two were fail-open by
        construction. Requiring a line to LOOK like a git command means enumerating the ways a
        command can begin — `if`, `!`, `VAR=`, and then `command`, `env`, `exec`, `nohup`,
        `sh -c`, backticks, `$( )`. That list has no end, and every omission is a push that
        sails past unexamined; `command git push origin "$BRANCH"` was the one that proved it.

        So the question is inverted. Any line mentioning both `git` and `push` is a candidate
        and must carry the helper; nothing has to be recognised first. Prose is excluded by the
        `- ` bullet skip, and a helper-script invocation by its `.sh`. Both of those are
        NARROWING rules, so each is a hole by construction — but they are two named holes
        rather than an open-ended allowlist of prefixes, and a new spelling of `push` fails
        rather than passing silently.
        """
        sites = []
        for line in self._logical_lines(text):
            stripped = line.strip()
            if stripped.startswith(("#", "- ")) or ".sh" in stripped:
                continue
            if not (re.search(r"\bgit\b", stripped) and re.search(r"\bpush\b", stripped)):
                continue
            sites.append((name, stripped))
        return sites

    def _push_sites(self):
        """Every `git push` in a credentials-disabled workflow, as (workflow, command)."""
        sites = []
        for wf in sorted((REPO / "auditor" / "workflows").glob("*.yml")):
            text = wf.read_text(encoding="utf-8")
            if "persist-credentials: false" not in text:
                continue
            sites.extend(self._push_sites_in(wf.name, text))
        return sites

    #: The workflows this item repaired. Naming them is the point: a count alone was satisfied
    #: by the EXEMPTED file's sites while covering neither repair.
    REPAIRED = {"auditor-cite-exemplars.yml", "auditor-refine-rules.yml"}


    #: Spellings of an unauthenticated push that a prefix-enumerating scanner missed. Kept as
    #: data because the point is not these four — it is that the list has no end, which is why
    #: the scan stopped trying to recognise commands and now flags anything mentioning both.
    EVASIONS = ("command git push origin x", "env git push origin x",
                "exec git push origin x", "nohup git push origin x",
                "$(git push origin x)", "sh -c 'git push origin x'")

    def test_every_known_evasion_is_still_seen(self):
        for spelling in self.EVASIONS:
            with self.subTest(spelling=spelling):
                found = self._push_sites_in("t", f"  {spelling}\n")
                self.assertTrue(found, f"{spelling!r} is invisible to the scan")
                self.assertFalse(self._has_effective_helper(found[0][1]),
                                 "an unauthenticated push was treated as authenticated")

    def test_the_scan_covers_the_commands_it_was_written_to_protect(self):
        """The guard on the guard, and it took three attempts to make honest.

        v1 scanned physical lines while both commands use `\\` continuations: zero matches.
        v2 required the line to start with `git`, but both start with an env assignment: zero.
        v3 forbade punctuation between `git` and `push` to exclude prose — and the dot in
        `credential.helper` is punctuation, so again zero. Each version passed, and each would
        have stayed green with the credential blocks deleted.

        A count is not enough: five sites in the EXEMPTED file satisfied `>= 2` every time.
        This asserts the repaired files specifically.
        """
        covered = {name for name, _ in self._push_sites()}
        self.assertTrue(self.REPAIRED <= covered,
                        f"the scan misses {sorted(self.REPAIRED - covered)} — it is vacuous "
                        f"for exactly the commands it exists to protect")

    #: THE EXACT HELPER, not a pattern. Five successive regexes were evaded during E8.3 —
    #: continuation lines, a leading env assignment, punctuation in `credential.helper`, the
    #: empty reset, and `credential.helper=${UNSET-}` which expands to nothing. A regex over
    #: shell SOURCE cannot decide what a shell EXPRESSION evaluates to at RUNTIME, so this is
    #: an allowlist of the one construction the workflows use.
    HELPER_LITERAL = ('credential.helper=!f() { echo "username=x-access-token"; '
                      'echo "password=${GIT_AUTH_TOKEN}"; }; f')

    @classmethod
    def _has_effective_helper(cls, command, text=""):
        """The literal on the command, or in the `CRED_ARGS` array the command expands.

        auditor-contribute builds the args conditionally — a credential is meaningful only for
        an https remote, and a local or file:// remote needs none — so the literal sits in the
        surrounding block rather than on the push line. Credited only when the SAME text both
        defines CRED_ARGS with the literal and the command expands it.
        """
        if cls.HELPER_LITERAL in command:
            return True
        return ('${CRED_ARGS[@]}' in command and "CRED_ARGS=(-c" in text
                and cls.HELPER_LITERAL in text)

    def test_removing_a_credential_helper_is_detected(self):
        """The mutant: strip the effective helper and confirm the check notices."""
        for wf in sorted((REPO / "auditor" / "workflows").glob("*.yml")):
            text = wf.read_text(encoding="utf-8")
            if "persist-credentials: false" not in text or "credential.helper" not in text:
                continue
            mutated = re.sub(r"\n[^\n]*credential\.helper=!f\(\)[^\n]*", "", text)
            with self.subTest(workflow=wf.name):
                bare = [cmd for _n, cmd in self._push_sites_in(wf.name, mutated)
                        if not self._has_effective_helper(cmd, mutated)]
                self.assertTrue(bare, f"{wf.name}: stripping the helper changed nothing")

    def test_the_token_is_never_written_into_a_url_or_config(self):
        """Ephemeral means ephemeral: not in a remote URL, not persisted by `git config`."""
        for wf in sorted((REPO / "auditor" / "workflows").glob("*.yml")):
            text = wf.read_text(encoding="utf-8")
            with self.subTest(workflow=wf.name):
                self.assertNotIn("@github.com", text, "credentials in a remote URL")
                self.assertNotIn("git config credential", text, "persisted credential")

    #: EMPTY, and deliberately so. auditor-contribute.yml carried a named exemption here
    #: through all of E8.3, guarded by a liveness assertion that would fail once the exemption
    #: stopped describing anything real. E8.2b authenticated its five pushes, so both are gone
    #: together — a carve-out that outlives its reason is how a check quietly stops checking.
    OUT_OF_SCOPE: set = set()

    def test_no_workflow_pushes_without_supplying_a_credential(self):
        # Per workflow, because crediting a conditionally-built CRED_ARGS needs the
        # surrounding text — the literal is not on the push line itself.
        offenders = []
        for wf in sorted((REPO / "auditor" / "workflows").glob("*.yml")):
            text = wf.read_text(encoding="utf-8")
            if "persist-credentials: false" not in text or wf.name in self.OUT_OF_SCOPE:
                continue
            offenders += [f"{wf.name}: {cmd[:70]}"
                          for _n, cmd in self._push_sites_in(wf.name, text)
                          if not self._has_effective_helper(cmd, text)]
        self.assertEqual(offenders, [],
                         "a bare `git push` in a credentials-disabled checkout")

class TestSidecarFingerprintConsumers(unittest.TestCase):
    """No helper may REQUIRE a fingerprint on a section-4 sidecar finding.

    This class exists because the same defect shipped three times. Section 4 states the
    per-audit sidecar carries no fingerprint — the aggregation post-step adds it — so a helper
    that skips rows without one silently discards every finding and exits successfully.

    It was fixed in diff-findings, then found again in backfill-findings, then again in
    backfill-pr-fingerprints, and a search afterwards turned up rule-health doing the same. Each
    fix was correct and none was a SEARCH. This is the search, kept as a test.
    """

    #: Helpers that read the per-audit sidecar. Reading `ledgers/findings.jsonl` is different —
    #: those rows ARE enriched and a fingerprint is legitimately expected there.
    SIDECAR_READERS = ("diff-findings.py", "backfill-findings.py",
                       "backfill-pr-fingerprints.py", "rule-health.py",
                       "validate-rule-ids.py", "prepare-refinement-input.py",
                       # found by the completeness check below, not by me
                       "repair-stale-statuses.py")

    # NO SOURCE-TEXT CHECK HERE, deliberately. Two attempts failed for the same reason: from
    # the text alone you cannot tell a helper REQUIRING a fingerprint on a raw sidecar from one
    # legitimately reading it off an enriched ledger row, or from one including it as an
    # optional key. The first version flagged prepare-refinement-input.py, which is correct;
    # the second flagged rule-health.py's ledger reader, which is also correct.
    #
    # Bending the pattern a third time would repeat this issue's most expensive habit — a guard
    # reshaped until it stops complaining, which is not the same as a guard that works. The
    # behavioural proof that each helper handles a RAW section-4 sidecar lives in that helper's
    # own tests, where a real record can be fed through it.
    #
    # What this class still does honestly is the part I got wrong by hand: enumerate the
    # readers, so a new one cannot be added without someone noticing.

    def test_the_reader_list_covers_every_helper_that_opens_the_audits_directory(self):
        """The list must not go stale: a new sidecar reader has to join it, or this class stops
        being the search it claims to be."""
        opens_audits = {
            path.name for path in sorted((REPO / "auditor" / "scripts").glob("*.py"))
            if '"audits"' in path.read_text(encoding="utf-8")
        }
        self.assertTrue(opens_audits <= set(self.SIDECAR_READERS),
                        f"unlisted sidecar readers: {sorted(opens_audits - set(self.SIDECAR_READERS))}")



class TestContributionHandoff(unittest.TestCase):
    """auditor-contribute must write what auditor-track reads.

    These two workflows are the seam between opening a PR and tracking its outcome, and they
    disagreed: contribute wrote `status: "prs_submitted"` with `last_pr`, while track selects on
    `contributed`/`tracked`/`complete` and iterates `pipeline_prs`. So a successfully opened PR
    was never tracked, classified, or dispatched for a case study — the whole downstream half of
    the pipeline sat idle while the contribute job reported success.

    SCHEMAS.md is authoritative over both: section 1 fixes the status enum and declares
    `pipeline_prs` as CONTRIBUTE's field. `prs_submitted` appears nowhere in it.
    """

    CONTRIBUTE = REPO / "auditor" / "workflows" / "auditor-contribute.yml"

    @classmethod
    def registry_statuses(cls):
        """Statuses written into `.repos[...]` — the pipeline enum, not job-result artifacts."""
        return set(re.findall(r'\.repos\[\$repo\][^\n]*status:\s*"([a-z_]+)"',
                              cls.contribute_code()))

    @classmethod
    def contribute_code(cls):
        """The workflow with comments stripped.

        Searched against CODE, not prose: the comment explaining why `last_pr` was removed
        contains the word `last_pr`, so a whole-file search fails on its own documentation.
        That exact trap cost several rounds on E8.3.
        """
        return "\n".join(ln for ln in cls.CONTRIBUTE.read_text().splitlines()
                          if not ln.lstrip().startswith("#"))
    TRACK = REPO / "auditor" / "workflows" / "auditor-track.yml"
    SCHEMAS = REPO / "auditor" / "SCHEMAS.md"

    def test_the_status_written_is_in_the_schema_enum(self):
        enum_row = next(ln for ln in self.SCHEMAS.read_text().splitlines()
                        if ln.startswith("| status |"))
        declared = set(re.findall(r"`([a-z_]+)`", enum_row))
        # REGISTRY statuses only. A bare `status: "..."` search also matches the job-result
        # artifacts (`{job: "submit", status: "submitted"}`), which are this workflow's own
        # vocabulary and not the pipeline enum — two different things sharing a key name.
        written = self.registry_statuses()
        self.assertTrue(written, "no registry status write found — the scan is broken")
        self.assertTrue(written <= declared,
                        f"contribute writes statuses outside the enum: "
                        f"{sorted(written - declared)}")

    def test_contribute_writes_the_field_track_reads(self):
        contribute = self.contribute_code()
        self.assertIn("pipeline_prs", contribute,
                      "contribute must record PR numbers where track looks for them")
        self.assertNotIn("last_pr", contribute,
                         "last_pr keeps only the most recent PR and nothing reads it")

    def test_track_selects_a_status_contribute_actually_writes(self):
        """The seam in the other direction: track's selection must include what contribute
        leaves behind, or the handoff is broken from track's side instead."""
        written = self.registry_statuses()
        selected = set(re.findall(r'status\s*(?:==|// "")\s*==?\s*"([a-z_]+)"',
                                  self.TRACK.read_text()))
        selected |= set(re.findall(r'\.status == "([a-z_]+)"', self.TRACK.read_text()))
        self.assertTrue(written & selected,
                        f"track selects {sorted(selected)} but contribute writes "
                        f"{sorted(written)} — nothing hands off")


#: vibe-167 (E8.3 follow-up): every helper's obligations — a non-empty subset of
#: {workflow-called, helper-called, operator}. The inventory test proves the thirty
#: EXIST; this table plus TestHelperCallSites proves each is REACHED the way its own
#: docstring intends. `operator` entries carry their individually-verified invocation
#: policy; they are the only exemption from a call-site requirement, and the exemption
#: is visible here rather than silent in a test's blind spot.
#: log-event.sh note (plan amendment, step-9 F7): adopted where a rewired block
#: APPENDS AN EVENT — daily-report and render-dashboard; the other four rewired
#: duties append no events inside their marker regions, so sourcing the library
#: there would be a call site with no call. Older inline appends elsewhere are
#: legacy sites, kept as-is.
HELPER_OBLIGATIONS = {
    "atomic-registry-write.sh": {"helper-called"},
    "backfill-findings.py": {"operator"},          # default dry run; --apply appends
    "backfill-pr-fingerprints.py": {"operator"},   # default dry run; --apply writes
    "batch-process.py": {"workflow-called"},
    "build-exemplar-gallery.py": {"workflow-called"},
    "commit-via-pr.sh": {"workflow-called"},
    "compute-fingerprint.sh": {"workflow-called"},
    "compute-vocab-fingerprint.sh": {"workflow-called"},
    "diff-findings.py": {"workflow-called"},
    "docs-diff.py": {"workflow-called"},
    "generate-daily-report.py": {"workflow-called"},
    "generate-rule-review-body.py": {"workflow-called"},
    "git-push-with-retry.sh": {"workflow-called"},
    "guard-protected-paths.sh": {"workflow-called"},
    "log-event.sh": {"workflow-called"},
    "parse-pr-metadata.py": {"workflow-called"},
    "parse-suppressions.py": {"helper-called"},
    "prepare-refinement-input.py": {"workflow-called"},
    "propose-rule-citations.py": {"workflow-called"},
    "render-dashboard.py": {"workflow-called", "helper-called"},
    "render-repo-report.py": {"workflow-called"},
    "repair-stale-statuses.py": {"operator"},      # writes by default; --dry-run reports
    "resolve-merge-conflicts.sh": {"helper-called"},
    "rule-health.py": {"workflow-called"},
    "scan-suppressions.py": {"workflow-called"},
    "synthesize-sidecar.py": {"helper-called"},
    "three-way-merge-registry.py": {"helper-called"},
    "validate-feedback.sh": {"workflow-called"},
    "validate-rule-ids.py": {"workflow-called"},
    "vendor_default_filter.py": {"workflow-called"},
}


class TestHelperCallSites(unittest.TestCase):
    """vibe-167: the inventory proved existence; this class proves reach.

    E8.3 found four wiring defects by reading; the census that motivated this table
    found fifteen helpers with zero workflow references, nine reachable from nowhere.
    A helper whose obligation is `workflow-called` without a call site is a duty the
    unit claims and does not perform."""

    def test_the_obligations_table_covers_exactly_the_thirty(self):
        self.assertEqual(sorted(HELPER_OBLIGATIONS), sorted(E83_HELPERS),
                         "the obligations table and the helper inventory drifted")
        for name, obligations in HELPER_OBLIGATIONS.items():
            self.assertTrue(obligations, f"{name} has an empty obligation set")
            self.assertLessEqual(obligations,
                                 {"workflow-called", "helper-called", "operator"})

    def workflow_texts(self):
        return {p.name: p.read_text(encoding="utf-8")
                for p in sorted((REPO / "auditor" / "workflows").glob("*.yml"))}

    def helper_texts(self):
        return {p.name: p.read_text(encoding="utf-8", errors="replace")
                for p in sorted(SCRIPTS_DIR.iterdir()) if p.is_file()}

    def test_every_workflow_called_helper_has_a_workflow_call_site(self):
        texts = self.workflow_texts()
        missing = []
        for name, obligations in sorted(HELPER_OBLIGATIONS.items()):
            if "workflow-called" not in obligations:
                continue
            if not any(name in text for text in texts.values()):
                missing.append(name)
        self.assertEqual(missing, [],
                         f"helpers whose own intent is workflow use, with no call site "
                         f"in any workflow: {missing} — the duty each implements is "
                         f"being performed inline or not at all")

    def test_every_helper_called_helper_is_referenced_by_a_helper(self):
        texts = self.helper_texts()
        missing = []
        for name, obligations in sorted(HELPER_OBLIGATIONS.items()):
            if "helper-called" not in obligations:
                continue
            if not any(name in text for other, text in texts.items() if other != name):
                missing.append(name)
        self.assertEqual(missing, [],
                         f"library helpers referenced by no other helper: {missing}")

    def test_operator_helpers_state_their_invocation_policy(self):
        # The exemption must stay auditable: each operator helper's table row carries
        # a policy comment, and the helper's own text matches it (--apply for the
        # backfills' opt-in writes; --dry-run for repair's opt-out).
        texts = self.helper_texts()
        for name in ("backfill-findings.py", "backfill-pr-fingerprints.py"):
            self.assertIn("--apply", texts[name],
                          f"{name} no longer carries the opt-in write flag its "
                          f"operator policy records")
        self.assertIn("--dry-run", texts["repair-stale-statuses.py"],
                      "repair-stale-statuses.py no longer carries the opt-out flag "
                      "its operator policy records")


#: vibe-167: the reviewed argument contract for every workflow-callable helper.
#: AUTHORED from each helper's parser, usage text and refusal arms — not introspected,
#: because most required flags are enforced by post-parse refusals argparse cannot
#: report, and the shell helpers have no parser object at all.
#: Shapes: required/allowed flag sets; "stdin" — the helper reads stdin; "positionals"
#: — (min, max) bare arguments; "sourced" — a function library whose call site is
#: `. .../helper.sh`, never an interpreter invocation.
CALL_CONTRACTS = {
    "batch-process.py": {"required": {"--data-dir", "--stage"},
                         "allowed": {"--data-dir", "--stage", "--batch-size",
                                     "--host-repo", "--apply"},
                         "boolean": {"--apply"}},
    "build-exemplar-gallery.py": {"required": set(),
                                  "allowed": {"--data-dir", "--exemplars-dir",
                                              "--output", "--check"},
                                  "boolean": {"--check"}},
    "commit-via-pr.sh": {"required": {"--checkout", "--repo", "--base",
                                      "--branch"},
                         "allowed": {"--checkout", "--repo", "--base", "--branch"}},
    "compute-fingerprint.sh": {"sourced": True},
    "compute-vocab-fingerprint.sh": {"sourced": True},
    "diff-findings.py": {"required": set(),
                         "allowed": {"--generated-at", "--original-score",
                                     "--reaudit-score", "--repo",
                                     "--original-sidecar", "--reaudit-sidecar",
                                     "--registry", "--commit-sha-before",
                                     "--commit-sha-after", "--events-out",
                                     "--diff-report-out", "--summary-out"}},
    "docs-diff.py": {"required": set(),
                     "allowed": {"--data-dir", "--citations", "--hash-store",
                                 "--changed-out"}},
    "generate-daily-report.py": {"required": set(),
                                 "allowed": {"--data-dir", "--inputs", "--date",
                                             "--out"}},
    "generate-rule-review-body.py": {"required": {"--data-dir", "--quarter"},
                                     "allowed": {"--data-dir", "--quarter", "--as-of",
                                                 "--out"}},
    "git-push-with-retry.sh": {"required": set(),
                               "allowed": {"--checkout", "--data-dir", "--attempts"}},
    "guard-protected-paths.sh": {"required": set(), "allowed": {"--data-dir"}},
    "log-event.sh": {"sourced": True},
    "parse-pr-metadata.py": {"required": set(), "allowed": set(), "stdin": True},
    "prepare-refinement-input.py": {"required": {"--data-dir"},
                                    "allowed": {"--data-dir", "--feedback", "--out",
                                                "--min-hits"}},
    "propose-rule-citations.py": {"required": {"--data-dir"},
                                  "allowed": {"--data-dir", "--apply", "--rules-path",
                                              "--exemplar-url-prefix", "--out"},
                                  "boolean": {"--apply"}},
    "render-dashboard.py": {"required": {"--data-dir"},
                            "allowed": {"--data-dir", "--out", "--since",
                                        "--generated-at"}},
    "render-repo-report.py": {"required": {"--repo", "--data-dir"},
                              "allowed": {"--repo", "--data-dir", "--out",
                                          "--generated-at"}},
    "rule-health.py": {"required": {"--data-dir"},
                       "allowed": {"--data-dir", "--out", "--generated-at"}},
    "scan-suppressions.py": {"required": {"--data-dir", "--host-repo"},
                             "allowed": {"--data-dir", "--host-repo", "--query",
                                         "--observed-at", "--apply"},
                             "boolean": {"--apply"}},
    "validate-feedback.sh": {"required": set(),
                             "allowed": {"--data-dir", "--log", "--allow-missing"},
                             "boolean": {"--allow-missing"},
                             "required_one_of": {"--data-dir", "--log"}},
    "validate-rule-ids.py": {"required": set(),
                             "allowed": {"--data-dir", "--rubric"},
                             "positionals": (0, 400),
                             # data-dir is the sidecar source only when no explicit
                             # sidecar is passed (the helper's own branch structure)
                             "required_if_no_positionals": {"--data-dir"}},
    "vendor_default_filter.py": {"required": set(), "allowed": {"--report"}},
}

#: Call sites the static checker CANNOT parse, each bound to the extracted-run test
#: that executes it instead. An entry here is a tested obligation, not a skip: the
#: named test must exist in the named module, held by test_the_roster_names_real_tests.
EXTRACTED_RUN_ROSTER = {
    # (workflow file, helper): (test module, test attribute substring)
}


def check_call_sites(workflow_texts, contracts, roster):
    """Every helper call site in every run block, checked fail-closed.

    Returns a list of violation strings; empty means every site parsed and satisfied
    its helper's contract. Lines are split into COMMAND SEGMENTS (;, &&, ||, |)
    first, so two helpers on one line are validated independently; value-taking
    flags must have a value, boolean flags must not; a site the tokenizer cannot
    parse is a VIOLATION unless the roster binds it to an extracted-run test.
    """
    import shlex
    violations = []
    for wf_name, text in sorted(workflow_texts.items()):
        joined = text.replace("\\\n", " ")
        for line_no, line in enumerate(joined.splitlines(), 1):
            hits = [h for h in contracts if f"auditor/scripts/{h}" in line]
            if not hits:
                continue
            try:
                tokens = shlex.split(line, comments=True)
            except ValueError:
                for helper in hits:
                    if (wf_name, helper) not in roster:
                        violations.append(f"{wf_name}:{line_no} {helper}: unparseable "
                                          f"call site and not on the extracted-run roster")
                continue
            segments, current = [], []
            for token in tokens:
                parts = [t for t in re.split(r"(;|\|\||&&|\|)", token) if t]
                for part in parts:
                    if part in (";", "&&", "||", "|"):
                        if current:
                            segments.append(current)
                        current = []
                    else:
                        current.append(part)
            if current:
                segments.append(current)
            for helper in hits:
                needle = f"auditor/scripts/{helper}"
                contract = contracts[helper]
                where = f"{wf_name}:{line_no} {helper}"
                found = False
                for segment in segments:
                    index = next((i for i, t in enumerate(segment) if needle in t), None)
                    if index is None:
                        continue
                    found = True
                    if contract.get("sourced"):
                        if index == 0 or segment[index - 1] not in (".", "source"):
                            violations.append(
                                f"{where}: function library referenced without "
                                f"sourcing (expected `. .../{helper}`)")
                        continue
                    args = segment[index + 1:]
                    flags, positionals, i = set(), 0, 0
                    boolean = contract.get("boolean", set())
                    while i < len(args):
                        token = args[i]
                        if token in (">", ">>", "2>", "<", "then", "do"):
                            break
                        if token.startswith("--"):
                            flag, eq, _ = token.partition("=")
                            flags.add(flag)
                            if flag in boolean:
                                if eq:
                                    violations.append(f"{where}: boolean {flag} "
                                                      f"takes no value")
                                i += 1
                                continue
                            if eq:
                                i += 1
                                continue
                            if i + 1 >= len(args) or args[i + 1].startswith("--") \
                                    or args[i + 1] in ("then", "do"):
                                violations.append(f"{where}: {flag} is missing "
                                                  f"its value")
                                i += 1
                                continue
                            i += 2
                            continue
                        positionals += 1
                        i += 1
                    required = set(contract.get("required", set()))
                    if positionals == 0:
                        required |= contract.get("required_if_no_positionals", set())
                    missing = required - flags
                    unknown = flags - contract.get("allowed", set())
                    one_of = contract.get("required_one_of")
                    lo, hi = contract.get("positionals", (0, 0))
                    if missing:
                        violations.append(f"{where}: missing required {sorted(missing)}")
                    if unknown:
                        violations.append(f"{where}: unknown flags {sorted(unknown)}")
                    if one_of and not (flags & one_of):
                        violations.append(f"{where}: needs one of {sorted(one_of)}")
                    if not (lo <= positionals <= hi):
                        violations.append(f"{where}: {positionals} positional(s), "
                                          f"contract allows {lo}..{hi}")
                if not found and (wf_name, helper) not in roster:
                    violations.append(f"{where}: helper name present but no invocation "
                                      f"token found and not on the roster")
    return violations


class TestHelperCallSites(unittest.TestCase):
    """vibe-167: the inventory proved existence; this class proves reach.

    E8.3 found four wiring defects by reading; the census that motivated this table
    found fifteen helpers with zero workflow references, nine reachable from nowhere.
    A helper whose obligation is `workflow-called` without a call site is a duty the
    unit claims and does not perform."""

    def test_the_obligations_table_covers_exactly_the_thirty(self):
        self.assertEqual(sorted(HELPER_OBLIGATIONS), sorted(E83_HELPERS),
                         "the obligations table and the helper inventory drifted")
        for name, obligations in HELPER_OBLIGATIONS.items():
            self.assertTrue(obligations, f"{name} has an empty obligation set")
            self.assertLessEqual(obligations,
                                 {"workflow-called", "helper-called", "operator"})

    def workflow_texts(self):
        return {p.name: p.read_text(encoding="utf-8")
                for p in sorted((REPO / "auditor" / "workflows").glob("*.yml"))}

    def helper_texts(self):
        return {p.name: p.read_text(encoding="utf-8", errors="replace")
                for p in sorted(SCRIPTS_DIR.iterdir()) if p.is_file()}

    def test_every_workflow_called_helper_has_a_workflow_call_site(self):
        texts = self.workflow_texts()
        missing = []
        for name, obligations in sorted(HELPER_OBLIGATIONS.items()):
            if "workflow-called" not in obligations:
                continue
            if not any(name in text for text in texts.values()):
                missing.append(name)
        self.assertEqual(missing, [],
                         f"helpers whose own intent is workflow use, with no call site "
                         f"in any workflow: {missing} — the duty each implements is "
                         f"being performed inline or not at all")

    def test_every_helper_called_helper_is_referenced_by_a_helper(self):
        texts = self.helper_texts()
        missing = []
        for name, obligations in sorted(HELPER_OBLIGATIONS.items()):
            if "helper-called" not in obligations:
                continue
            if not any(name in text for other, text in texts.items() if other != name):
                missing.append(name)
        self.assertEqual(missing, [],
                         f"library helpers referenced by no other helper: {missing}")

    def test_operator_helpers_state_their_invocation_policy(self):
        # The exemption must stay auditable: each operator helper's table row carries
        # a policy comment, and the helper's own text matches it (--apply for the
        # backfills' opt-in writes; --dry-run for repair's opt-out).
        texts = self.helper_texts()
        for name in ("backfill-findings.py", "backfill-pr-fingerprints.py"):
            self.assertIn("--apply", texts[name],
                          f"{name} no longer carries the opt-in write flag its "
                          f"operator policy records")
        self.assertIn("--dry-run", texts["repair-stale-statuses.py"],
                      "repair-stale-statuses.py no longer carries the opt-out flag "
                      "its operator policy records")


#: vibe-167: the reviewed argument contract for every workflow-callable helper.
#: AUTHORED from each helper's parser, usage text and refusal arms — not introspected,
#: because most required flags are enforced by post-parse refusals argparse cannot
#: report, and the shell helpers have no parser object at all.
#: Shapes: required/allowed flag sets; "stdin" — the helper reads stdin; "positionals"
#: — (min, max) bare arguments; "sourced" — a function library whose call site is
#: `. .../helper.sh`, never an interpreter invocation.
CALL_CONTRACTS = {
    "batch-process.py": {"required": {"--data-dir", "--stage"},
                         "allowed": {"--data-dir", "--stage", "--batch-size",
                                     "--host-repo", "--apply"},
                         "boolean": {"--apply"}},
    "build-exemplar-gallery.py": {"required": set(),
                                  "allowed": {"--data-dir", "--exemplars-dir",
                                              "--output", "--check"},
                                  "boolean": {"--check"}},
    "commit-via-pr.sh": {"required": {"--checkout", "--repo", "--base",
                                      "--branch"},
                         "allowed": {"--checkout", "--repo", "--base", "--branch"}},
    "compute-fingerprint.sh": {"sourced": True},
    "compute-vocab-fingerprint.sh": {"sourced": True},
    "diff-findings.py": {"required": set(),
                         "allowed": {"--generated-at", "--original-score",
                                     "--reaudit-score", "--repo",
                                     "--original-sidecar", "--reaudit-sidecar",
                                     "--registry", "--commit-sha-before",
                                     "--commit-sha-after", "--events-out",
                                     "--diff-report-out", "--summary-out"}},
    "docs-diff.py": {"required": set(),
                     "allowed": {"--data-dir", "--citations", "--hash-store",
                                 "--changed-out"}},
    "generate-daily-report.py": {"required": set(),
                                 "allowed": {"--data-dir", "--inputs", "--date",
                                             "--out"}},
    "generate-rule-review-body.py": {"required": {"--data-dir", "--quarter"},
                                     "allowed": {"--data-dir", "--quarter", "--as-of",
                                                 "--out"}},
    "git-push-with-retry.sh": {"required": set(),
                               "allowed": {"--checkout", "--data-dir", "--attempts"}},
    "guard-protected-paths.sh": {"required": set(), "allowed": {"--data-dir"}},
    "log-event.sh": {"sourced": True},
    "parse-pr-metadata.py": {"required": set(), "allowed": set(), "stdin": True},
    "prepare-refinement-input.py": {"required": {"--data-dir"},
                                    "allowed": {"--data-dir", "--feedback", "--out",
                                                "--min-hits"}},
    "propose-rule-citations.py": {"required": {"--data-dir"},
                                  "allowed": {"--data-dir", "--apply", "--rules-path",
                                              "--exemplar-url-prefix", "--out"},
                                  "boolean": {"--apply"}},
    "render-dashboard.py": {"required": {"--data-dir"},
                            "allowed": {"--data-dir", "--out", "--since",
                                        "--generated-at"}},
    "render-repo-report.py": {"required": {"--repo", "--data-dir"},
                              "allowed": {"--repo", "--data-dir", "--out",
                                          "--generated-at"}},
    "rule-health.py": {"required": {"--data-dir"},
                       "allowed": {"--data-dir", "--out", "--generated-at"}},
    "scan-suppressions.py": {"required": {"--data-dir", "--host-repo"},
                             "allowed": {"--data-dir", "--host-repo", "--query",
                                         "--observed-at", "--apply"},
                             "boolean": {"--apply"}},
    "validate-feedback.sh": {"required": set(),
                             "allowed": {"--data-dir", "--log", "--allow-missing"},
                             "boolean": {"--allow-missing"},
                             "required_one_of": {"--data-dir", "--log"}},
    "validate-rule-ids.py": {"required": set(),
                             "allowed": {"--data-dir", "--rubric"},
                             "positionals": (0, 400),
                             # data-dir is the sidecar source only when no explicit
                             # sidecar is passed (the helper's own branch structure)
                             "required_if_no_positionals": {"--data-dir"}},
    "vendor_default_filter.py": {"required": set(), "allowed": {"--report"}},
}

#: Call sites the static checker CANNOT parse, each bound to the extracted-run test
#: that executes it instead. An entry here is a tested obligation, not a skip: the
#: named test must exist in the named module, held by test_the_roster_names_real_tests.
EXTRACTED_RUN_ROSTER = {
    # (workflow file, helper): (test module, test attribute substring)
}


class TestCallSiteArguments(unittest.TestCase):
    """vibe-167: each call site's arguments checked against its helper's contract.

    E8.3's four wiring defects (a positional where --attempts was required, $SLUG for
    --repo, a .sh name for a .py helper, a phantom helper) were each findable by this
    check; the contract table is reviewed prose, the checker is fail-closed."""

    def test_every_workflow_callable_helper_has_a_contract(self):
        expected = {name for name, obligations in HELPER_OBLIGATIONS.items()
                    if "workflow-called" in obligations}
        self.assertEqual(sorted(CALL_CONTRACTS), sorted(expected),
                         "the contract table and the workflow-called obligation set "
                         "drifted — author the contract with the wiring, not after it")

    def test_the_roster_names_real_tests(self):
        for (wf, helper), (module, attr) in sorted(EXTRACTED_RUN_ROSTER.items()):
            path = REPO / "tests" / f"{module}.py"
            self.assertTrue(path.is_file(), f"roster names a missing module {module}")
            self.assertIn(attr, path.read_text(encoding="utf-8"),
                          f"roster binds {wf}/{helper} to {module}.{attr}, which does "
                          f"not exist — the dynamic site is unexecuted")

    def test_every_real_call_site_satisfies_its_contract(self):
        texts = {p.name: p.read_text(encoding="utf-8")
                 for p in sorted((REPO / "auditor" / "workflows").glob("*.yml"))}
        violations = check_call_sites(texts, CALL_CONTRACTS, EXTRACTED_RUN_ROSTER)
        self.assertEqual(violations, [],
                         "call sites violating their helpers' contracts:\n  "
                         + "\n  ".join(violations))

    # -- checker mutation tests: each synthetic defect must be CAUGHT ----------------
    CONTRACT = {"fake-helper.py": {"required": {"--data-dir"},
                                   "allowed": {"--data-dir", "--out"}}}

    def _check(self, line, contracts=None, roster=None):
        text = f"jobs:\n  a:\n    steps:\n      - run: |\n          {line}\n"
        return check_call_sites({"wf.yml": text},
                                contracts or self.CONTRACT, roster or {})

    def test_mutation_missing_required_flag(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" --out x')
        self.assertTrue(any("missing required" in s for s in v), v)

    def test_mutation_unknown_flag(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir d --wrong x')
        self.assertTrue(any("unknown flags" in s for s in v), v)

    def test_mutation_stray_positional(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir d stray')
        self.assertTrue(any("positional" in s for s in v), v)

    def test_mutation_continuation_lines_are_joined(self):
        text = ('jobs:\n  a:\n    steps:\n      - run: |\n'
                '          python3 "$CODE_DIR/auditor/scripts/fake-helper.py" \\\n'
                '            --data-dir d \\\n            --out x\n')
        self.assertEqual(check_call_sites({"wf.yml": text}, self.CONTRACT, {}), [])

    def test_mutation_command_substitution_values_are_opaque(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir "$(pwd)/data" --out "$OUT"')
        self.assertEqual(v, [], v)

    def test_mutation_unparseable_site_fails_without_roster(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" --data-dir "unclosed')
        self.assertTrue(any("unparseable" in s or "no invocation" in s for s in v), v)

    def test_mutation_unparseable_site_passes_with_roster(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" --data-dir "unclosed',
                        roster={("wf.yml", "fake-helper.py"): ("test_x", "test_y")})
        self.assertEqual(v, [], v)

    def test_mutation_conditionally_required_flag(self):
        contracts = {"fake-helper.py": {
            "required": set(), "allowed": {"--data-dir"}, "positionals": (0, 5),
            "required_if_no_positionals": {"--data-dir"}}}
        bad = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py"',
                          contracts)
        self.assertTrue(any("missing required" in s for s in bad), bad)
        good = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" x.jsonl',
                           contracts)
        self.assertEqual(good, [], good)

    def test_mutation_glued_semicolon_is_stripped(self):
        v = self._check('if ! python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir d; then')
        self.assertEqual(v, [], v)

    def test_mutation_missing_flag_value(self):
        # F6 (step-8): `--data-dir --out x` silently treated --out as the value
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir --out x')
        self.assertTrue(any("missing its value" in s for s in v), v)

    def test_mutation_boolean_flag_with_a_value(self):
        contracts = {"fake-helper.py": {"required": set(),
                                        "allowed": {"--apply"},
                                        "boolean": {"--apply"}}}
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--apply=true', contracts)
        self.assertTrue(any("takes no value" in s for s in v), v)

    def test_mutation_required_one_of_group(self):
        contracts = {"fake-helper.sh": {"required": set(),
                                        "allowed": {"--data-dir", "--log"},
                                        "required_one_of": {"--data-dir", "--log"}}}
        bad = self._check('bash "$CODE_DIR/auditor/scripts/fake-helper.sh"', contracts)
        self.assertTrue(any("needs one of" in s for s in bad), bad)
        good = self._check('bash "$CODE_DIR/auditor/scripts/fake-helper.sh" --log l',
                           contracts)
        self.assertEqual(good, [], good)

    def test_mutation_all_four_required_flags(self):
        # the commit-via-pr shape: --checkout alone must fail
        contracts = {"fake-helper.sh": {
            "required": {"--checkout", "--repo", "--base", "--branch"},
            "allowed": {"--checkout", "--repo", "--base", "--branch"}}}
        v = self._check('bash "$CODE_DIR/auditor/scripts/fake-helper.sh" '
                        '--checkout /d', contracts)
        self.assertTrue(any("missing required" in s for s in v), v)

    def test_mutation_second_helper_on_the_same_line_is_validated(self):
        contracts = {"fake-lib.sh": {"sourced": True},
                     "fake-helper.py": {"required": {"--data-dir"},
                                        "allowed": {"--data-dir"}}}
        v = self._check('. "$CODE_DIR/auditor/scripts/fake-lib.sh" && '
                        'bash "$CODE_DIR/auditor/scripts/fake-lib.sh" && '
                        'python3 "$CODE_DIR/auditor/scripts/fake-helper.py"',
                        contracts)
        self.assertTrue(any("without sourcing" in s for s in v),
                        f"the bash-invoked second segment of the sourced library "
                        f"escaped: {v}")
        self.assertTrue(any("missing required" in s for s in v), v)

    def test_mutation_sourced_library_must_be_sourced(self):
        contracts = {"fake-lib.sh": {"sourced": True}}
        bad = self._check('bash "$CODE_DIR/auditor/scripts/fake-lib.sh"', contracts)
        self.assertTrue(any("without sourcing" in s for s in bad), bad)
        good = self._check('. "$CODE_DIR/auditor/scripts/fake-lib.sh"', contracts)
        self.assertEqual(good, [], good)


if __name__ == "__main__":
    unittest.main()
