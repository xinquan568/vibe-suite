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
     `write-all`); scopes and values validate against the VENDORED github/docs vocabulary
     (#165 — two hand tables were wrong both times; see tests/fixtures/*.provenance);
   * that a stage workflow's entry label is OPERATIVE — trigger-relative AST judgement of
     the entry jobs' if: expressions plus the producer's real argv (#165,
     TestStageLabelOperative; three line-matcher attempts were defeated before it);
   * that only known secrets are referenced by `secrets.X` and `secrets['X']`, and a
     COMPUTED index (`secrets[format(...)]`) is refused outright (#165);
   * no pinned model ids — escaped spellings included, via tools/model-pin-lint.py's
     per-language decoded layer (#165);
   * a recursive-descent Actions expression grammar (`_ExprParser`, #165) with the
     documented function arities;
   * a PARSED-document family (#165): value shapes, flow forms validated equal to block,
     steps/runs enumerated from the Psych AST (bare-dash and quoted spellings), aliases
     resolved bounded, explicit tags refused, `bash -n` over decoded run text.

`lint()` therefore does NOT claim to detect malformed YAML, and the suite no longer asserts
that it does. `test_every_workflow_is_wellformed_yaml` owns that half.
"""
import os
import random
import re
import json
import subprocess
import tempfile
import unittest
import unittest.mock
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
#: test_permissions_declaration_and_vocabulary. Validating Actions' permission vocabulary
#: means tracking a set GitHub changes; two hand tables were wrong in both directions
#: (`models` was dropped, `id-token: read` accepted). That validation now runs in the
#: parsed stage against the VENDORED github/docs vocabulary (#165) — see
#: permissions_vocabulary() and tests/fixtures/*.provenance.
BLOCKED_CMDS = ["curl", "wget", "nc", "ncat", "socat", "telnet", "ssh", "scp", "sftp", "rsync"]

MODEL_ID = re.compile(
    r"claude-[a-z]+-[0-9]|claude-[a-z0-9-]*-20[0-9]{2}|gpt-[0-9]|gemini-[0-9]|o[0-9]-|"
    r"--model\b|(^|\s)model:", re.M)
EXPR = re.compile(r"\$\{\{(.*?)\}\}", re.S)
_EXPR_TOKEN = re.compile(
    r"[A-Za-z_][A-Za-z0-9_-]*|\.|\(|\)|\[|\]|,|!|&&|\|\||[=!<>]=?|\*|'[^']*'|\"[^\"]*\"|"
    r"[0-9.]+|\s+")
#: The DOCUMENTED context roots (vibe-165 D2: job, jobs, strategy were valid and
#: rejected — an over-rejection of real Actions syntax).
_ALLOWED_ROOTS = {"github", "secrets", "inputs", "needs", "env", "matrix", "steps", "vars",
                  "runner", "job", "jobs", "strategy"}
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


#: vibe-165 W1 — the parsed-document bridge. Psych's NODE TREE (not a loaded
#: document): scalar keys keep their written-then-DECODED text (`"o\x6e"` is the
#: key `on`; bare `on` and bare `true` stay distinct strings — no YAML-1.1
#: boolean coercion happens at node level), styles distinguish flow from block
#: and quoted from plain, anchors carry identity, aliases are explicit leaf
#: nodes resolved in Python under stated semantics (below), and explicit tags
#: are surfaced for refusal. The emitter also computes its OWN census (jobs,
#: steps, run entries) in ruby — the independent recount the coverage tests
#: compare against the Python enumerator.
_AST_SCRIPT = """
require 'yaml'
require 'json'
def emit(n)
  case n
  when Psych::Nodes::Scalar
    {'t' => 's', 'tag' => n.tag, 'style' => n.style, 'anchor' => n.anchor,
     'v' => n.value, 'line' => n.start_line + 1}
  when Psych::Nodes::Mapping
    {'t' => 'm', 'tag' => n.tag, 'style' => n.style, 'anchor' => n.anchor,
     'line' => n.start_line + 1,
     'c' => n.children.each_slice(2).map { |k, v| [emit(k), emit(v)] }}
  when Psych::Nodes::Sequence
    {'t' => 'q', 'tag' => n.tag, 'style' => n.style, 'anchor' => n.anchor,
     'line' => n.start_line + 1, 'c' => n.children.map { |x| emit(x) }}
  when Psych::Nodes::Alias
    {'t' => 'a', 'anchor' => n.anchor, 'line' => n.start_line + 1}
  else
    {'t' => 'other', 'klass' => n.class.to_s}
  end
end
def scalar_value(n)
  n.is_a?(Psych::Nodes::Scalar) ? n.value : nil
end
def census(root)
  jobs = 0; steps = 0; runs = 0
  if root.is_a?(Psych::Nodes::Mapping)
    root.children.each_slice(2) do |k, v|
      next unless scalar_value(k) == 'jobs' && v.is_a?(Psych::Nodes::Mapping)
      v.children.each_slice(2) do |_jk, jv|
        jobs += 1
        next unless jv.is_a?(Psych::Nodes::Mapping)
        jv.children.each_slice(2) do |sk, sv|
          next unless scalar_value(sk) == 'steps' && sv.is_a?(Psych::Nodes::Sequence)
          sv.children.each do |item|
            steps += 1
            next unless item.is_a?(Psych::Nodes::Mapping)
            item.children.each_slice(2) do |ik, _iv|
              runs += 1 if scalar_value(ik) == 'run'
            end
          end
        end
      end
    end
  end
  {'jobs' => jobs, 'steps' => steps, 'runs' => runs}
end
begin
  doc = Psych.parse(STDIN.read)
rescue => e
  puts JSON.generate({'error' => e.class.to_s + ': ' + e.message.to_s[0, 200]})
  exit 0
end
if doc.nil? || doc.root.nil?
  puts JSON.generate({'error' => 'empty-document'})
  exit 0
end
puts JSON.generate({'root' => emit(doc.root), 'census' => census(doc.root)})
"""

#: Alias-resolution semantics (vibe-165 D1): anchors register in document order
#: as their nodes are entered; an alias naming an anchor not yet registered is a
#: violation (forward or unknown — Psych itself accepts both spellings of
#: brokenness); resolving revisits are cycles and refuse; total resolved nodes
#: are bounded so anchor-reuse bombs refuse rather than expand.
_ALIAS_EXPANSION_BOUND = 10_000


def parsed_workflow(text):
    """`(root, census, error)` via the Psych AST, or `(None, None, None)` when
    ruby is unavailable — unavailable stays distinguishable from invalid."""
    rb = _ruby()
    if rb is None:
        return None, None, None
    proc = subprocess.run([rb, "-e", _AST_SCRIPT], input=text.encode("utf-8"),
                          capture_output=True, timeout=60)
    payload = json.loads(proc.stdout.decode("utf-8", "replace"))
    if "error" in payload:
        return None, None, payload["error"]
    return payload["root"], payload["census"], None


def resolve_aliases(root):
    """`(resolved_root, violations)` under the stated semantics."""
    anchors, violations = {}, []
    budget = [_ALIAS_EXPANSION_BOUND]

    def copy(node, in_progress):
        if budget[0] <= 0:
            raise _ExpansionBound()
        budget[0] -= 1
        kind = node.get("t")
        if kind == "a":
            name = node.get("anchor")
            if name not in anchors:
                violations.append(f"alias to unregistered anchor '&{name}' "
                                  f"(forward or unknown) at line {node.get('line')}")
                return {"t": "s", "v": None, "line": node.get("line"),
                        "tag": None, "style": None, "anchor": None}
            if name in in_progress:
                violations.append(f"cyclic alias '&{name}' at line "
                                  f"{node.get('line')}")
                return {"t": "s", "v": None, "line": node.get("line"),
                        "tag": None, "style": None, "anchor": None}
            return copy(anchors[name], in_progress | {name})
        out = dict(node)
        name = node.get("anchor")
        if name:
            anchors[name] = node
            in_progress = in_progress | {name}
        if kind == "m":
            out["c"] = [[copy(k, in_progress), copy(v, in_progress)]
                        for k, v in node.get("c", [])]
        elif kind == "q":
            out["c"] = [copy(x, in_progress) for x in node.get("c", [])]
        return out

    class _ExpansionBound(Exception):
        pass
    try:
        resolved = copy(root, frozenset())
    except _ExpansionBound:
        violations.append(f"alias expansion exceeds {_ALIAS_EXPANSION_BOUND} "
                          f"nodes; refusing")
        resolved = None
    return resolved, violations


def tag_violations(node, out=None):
    """Explicit tags are refused by name — the lint validates workflows, not
    general YAML; timestamps, binary, sets and custom tags are all surprises."""
    if out is None:
        out = []
    if isinstance(node, dict):
        tag = node.get("tag")
        if tag:
            out.append(f"explicit tag '{tag}' at line {node.get('line')} — "
                       f"workflows use untagged YAML only")
        if node.get("t") == "m":
            for k, v in node.get("c", []):
                tag_violations(k, out)
                tag_violations(v, out)
        elif node.get("t") == "q":
            for child in node.get("c", []):
                tag_violations(child, out)
    return out


def _scalar(node):
    return node.get("v") if isinstance(node, dict) and node.get("t") == "s" else None


def _map_get(node, key):
    if isinstance(node, dict) and node.get("t") == "m":
        for k, v in node.get("c", []):
            if _scalar(k) == key:
                return v
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
                    # LIMIT: this recognises a mapping ENTRY by line shape, not by the
                    # parsed value. A quoted scalar containing a colon — `"not: a mapping"` —
                    # still passes HERE, because the colon inside the quotes reads as a
                    # key/value separator; the parsed stage (`_perm_shape`, #165) judges the
                    # real node type and refuses it.
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
            # Legal YAML this line-oriented grammar cannot walk. With ruby available the
            # parsed stage below validates flow forms for real (#165 item 2, validate
            # endpoint); without ruby the honest refusal stands so nothing passes
            # unvalidated silently.
            if _ruby() is None:
                v.append("jobs: uses an inline flow mapping, which this lint cannot "
                         "validate; use block style")
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
    # LIMIT: `_steps()` splits on `- ` and does not see a BARE dash, so a step written
    # `-` on its own line with `name:`/`id:` beneath it is not enumerated HERE; the parsed
    # stage (#165) enumerates steps from the AST, bare-dash and quoted spellings included.
    for jname, body in jobs.items():
        for step in _steps(body):
            # Quoted spellings ("run":, 'uses':) are the same key to YAML (#165 item 10);
            # matching only the bare form made this check falsely reject legal steps.
            if not any(re.match(r"""\s*(?:["']?(?:uses|run)["']?):""", ln) for ln in step):
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
    # The RAW pass holds only the declaration contract — "authority is declared rather than
    # inherited from the repository default", checked above at workflow or job level. What
    # the declared scopes and values MEAN is GitHub's vocabulary, which two hand tables got
    # wrong in both directions; the parsed stage (#165) validates them against the VENDORED
    # github/docs source instead — see permissions_vocabulary().
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
    # Parsed-path family (#165 W3). Deduped by exact string: where the parsed stage
    # re-detects a violation the line grammar already reported (block spellings), the
    # message appears once — so a flow workflow and its block twin yield EQUAL lists.
    for x in _parsed_checks(text):
        if x not in v:
            v.append(x)
    return v


_PERMISSIONS_VOCAB_CACHE = []


def permissions_vocabulary():
    """#165 item 5 (D9): scope names and value enums EXTRACTED from the vendored
    github/docs reusable — no hand-typed table anywhere. Pin, conformance gate,
    and refresh story: tests/fixtures/github-token-available-permissions.provenance."""
    if not _PERMISSIONS_VOCAB_CACHE:
        text = (Path(__file__).parent / "fixtures"
                / "github-token-available-permissions.md").read_text()
        _PERMISSIONS_VOCAB_CACHE.append(_extract_permissions_vocab(text))
    return _PERMISSIONS_VOCAB_CACHE[0]


def _extract_permissions_vocab(text):
    fenced = re.search(r"```yaml\n(.*?)```", text, re.S)
    if fenced is None:
        raise AssertionError("vendored permissions source has no yaml fence — "
                             "re-vendor per the .provenance note")
    fence = re.sub(r"\{%.*?%\}", "", fenced.group(1))
    vocab = {}
    for m in re.finditer(r"^\s*([a-z][a-z-]*):[ \t]*([a-z]+(?:\|[a-z]+)+)\s*$",
                         fence, re.M):
        vocab[m.group(1)] = frozenset(m.group(2).split("|"))
    if len(vocab) < 15:
        raise AssertionError(
            f"vendored permissions source yielded only {len(vocab)} scopes — "
            f"the fixture's shape changed; re-vendor per the .provenance note")
    return vocab


def _perm_shape(node, where):
    """vibe-165 items 9 + 5: a permissions declaration is judged by its PARSED
    value - a mapping (each scope and value checked against the vendored
    vocabulary), or the two documented whole-workflow scalars. A quoted scalar
    containing a colon is a string however key-like it reads."""
    if node.get("t") == "m":
        vocab = permissions_vocabulary()
        out = []
        for k, val in node.get("c", []):
            scope = _scalar(k)
            if scope not in vocab:
                out.append(f"{where}: unknown permission scope '{scope}'")
                continue
            if val.get("t") != "s":
                out.append(f"{where}: permission '{scope}' value is not a scalar")
                continue
            if val.get("v") not in vocab[scope]:
                out.append(f"{where}: permission '{scope}: {val.get('v')}' is "
                           f"outside the documented values "
                           f"({'|'.join(sorted(vocab[scope]))})")
        return out
    if node.get("t") == "s" and node.get("v") in ("read-all", "write-all"):
        return []
    shape = {"s": "scalar", "q": "sequence", "a": "alias"}.get(node.get("t"),
                                                               node.get("t"))
    return [f"{where}: permissions parses to a {shape}, not a mapping or "
            f"read-all/write-all"]


def _secret_index_checks(node, out=None):
    """vibe-165 item 6: a secrets[...] index must be a single literal - computed
    keys (format(), concatenation, context reads) are refused, so expression
    composition cannot evade the allowlist."""
    if out is None:
        out = []
    if isinstance(node, dict):
        if node.get("t") == "s" and node.get("v"):
            for m in re.finditer(r"\$\{\{(.*?)\}\}", str(node["v"]), re.S):
                try:
                    toks = _ExprParser(m.group(1)).toks
                except _ExprError:
                    continue
                for i, tok in enumerate(toks):
                    if tok != "secrets" or i + 1 >= len(toks) \
                            or toks[i + 1] != "[":
                        continue
                    j, depth, body = i + 2, 1, []
                    while j < len(toks) and depth:
                        if toks[j] == "[":
                            depth += 1
                        elif toks[j] == "]":
                            depth -= 1
                            if depth == 0:
                                break
                        body.append(toks[j])
                        j += 1
                    if len(body) != 1 or not body[0].startswith("'"):
                        out.append(f"line {node.get('line')}: computed secret "
                                   f"index - secrets[{' '.join(body)[:40]}] is "
                                   f"not a literal key; resolve or refuse")
        elif node.get("t") == "m":
            for k, v2 in node.get("c", []):
                _secret_index_checks(k, out)
                _secret_index_checks(v2, out)
        elif node.get("t") == "q":
            for child in node.get("c", []):
                _secret_index_checks(child, out)
    return out


def _parsed_checks(text):
    """vibe-165 W3 - the parsed-document family: value shapes, flow forms,
    steps/runs, computed secrets, aliases, tags. Runs only when ruby is
    available; the line-grammar's flow refusal stays for the no-ruby case so
    nothing passes unvalidated silently."""
    root, census, err = parsed_workflow(text)
    if root is None and err is None:
        return []
    if err is not None:
        return []      # psych_error already reports unparseable YAML by name
    out = []
    resolved, alias_violations = resolve_aliases(root)
    out.extend(alias_violations)
    out.extend(tag_violations(root))
    if resolved is None or resolved.get("t") != "m":
        return out
    perm = _map_get(resolved, "permissions")
    if perm is not None:
        out.extend(_perm_shape(perm, "workflow"))
    jobs = _map_get(resolved, "jobs")
    if jobs is not None:
        if jobs.get("t") != "m":
            shape = {"s": "scalar", "q": "sequence"}.get(jobs.get("t"),
                                                         jobs.get("t"))
            out.append(f"jobs parses to a {shape}, not a mapping")
        else:
            for jk, jv in jobs.get("c", []):
                jname = _scalar(jk)
                if jv.get("t") != "m":
                    shape = {"s": "scalar", "q": "sequence"}.get(jv.get("t"),
                                                                 jv.get("t"))
                    out.append(f"job '{jname}': parses to a {shape}, not a "
                               f"mapping - a block scalar cannot impersonate "
                               f"a job")
                    continue
                jperm = _map_get(jv, "permissions")
                if jperm is not None:
                    out.extend(_perm_shape(jperm, f"job '{jname}'"))
                # Structural parity with the line grammar (same strings, deduped at the
                # call site) so flow and block spellings report identically.
                if _map_get(jv, "runs-on") is None:
                    out.append(f"job '{jname}' missing runs-on")
                steps = _map_get(jv, "steps")
                if steps is None:
                    out.append(f"job '{jname}' missing steps")
                    continue
                if steps.get("t") != "q":
                    out.append(f"job '{jname}': steps parses to a non-sequence")
                    continue
                for idx, item in enumerate(steps.get("c", []), 1):
                    if not isinstance(item, dict) or item.get("t") != "m":
                        out.append(f"job '{jname}' step {idx}: not a mapping")
                        continue
                    keys = {_scalar(k) for k, _ in item.get("c", [])}
                    if "run" not in keys and "uses" not in keys:
                        out.append(f"job '{jname}' step {idx}: neither 'run' "
                                   f"nor 'uses' (parsed - bare-dash and quoted "
                                   f"spellings included)")
    out.extend(_secret_index_checks(resolved))
    return out


def _if_disjuncts(inner):
    """Top-level || disjuncts of a parsed if: expression, as token lists — None
    when the expression is outside the judged gating shape (parens, functions,
    or not in the grammar): the judge FAILS CLOSED rather than guessing."""
    if not _expr_ok(inner):
        return None
    toks = _ExprParser(inner).toks
    if "(" in toks or ")" in toks:
        return None
    disjuncts, cur = [], []
    for t in toks:
        if t == "||":
            disjuncts.append(cur)
            cur = []
        else:
            cur.append(t)
    disjuncts.append(cur)
    return disjuncts if all(disjuncts) else None


def _gates_on_label(inner, label):
    """#165 4-comment (D8): TRIGGER-RELATIVE gating. The recognized
    workflow_dispatch escape disjuncts are stripped; every REMAINING disjunct
    must carry the label equality as a top-level conjunct. `true || equality`
    fails (the true disjunct escapes on every trigger); the reordered
    `equality || dispatch` passes. Returns (gated, reason)."""
    disjuncts = _if_disjuncts(inner)
    if disjuncts is None:
        return False, "if: expression outside the judged gating shape"
    escapes = (["github", ".", "event_name", "==", "'workflow_dispatch'"],
               ["'workflow_dispatch'", "==", "github", ".", "event_name"])
    chain = ["github", ".", "event", ".", "label", ".", "name"]
    lit = "'" + label + "'"
    equalities = (chain + ["==", lit], [lit, "=="] + chain)
    remainder = [d for d in disjuncts if d not in escapes]
    if not remainder:
        return False, "only the dispatch escape remains — the label never gates"
    for d in remainder:
        conjuncts, cur = [], []
        for t in d:
            if t == "&&":
                conjuncts.append(cur)
                cur = []
            else:
                cur.append(t)
        conjuncts.append(cur)
        if not any(c in equalities for c in conjuncts):
            return False, ("a non-escape disjunct does not carry the label "
                           "equality: " + " ".join(d))
    return True, ""


def label_gate_violations(text, label):
    """Every ENTRY job (no needs:) of a consumer stage workflow must carry an
    if: whose expression gates on the stage label, judged from the AST — a
    comment, an echoed string, or a fake if: inside a block scalar never
    reaches this check because none of them is the job's if: node."""
    root, _census, err = parsed_workflow(text)
    if root is None or err is not None:
        return ["workflow does not parse: %s" % err]
    resolved, _ = resolve_aliases(root)
    if resolved is None or resolved.get("t") != "m":
        return ["workflow root is not a mapping"]
    jobs = _map_get(resolved, "jobs")
    if jobs is None or jobs.get("t") != "m":
        return ["no jobs mapping"]
    out = []
    for jk, jv in jobs.get("c", []):
        jname = _scalar(jk)
        if jv.get("t") != "m" or _map_get(jv, "needs") is not None:
            continue
        cond = _map_get(jv, "if")
        if cond is None or cond.get("t") != "s":
            out.append(f"entry job '{jname}': no if: gate")
            continue
        raw = str(cond.get("v") or "")
        m = re.fullmatch(r"\s*\$\{\{(.*)\}\}\s*", raw, re.S)
        inner = m.group(1) if m else raw
        gated, reason = _gates_on_label(inner, label)
        if not gated:
            out.append(f"entry job '{jname}': {reason}")
    return out


def producer_label_violations(text, label):
    """#165 4-comment, producer branch: the REAL `gh issue create` argv must
    carry `--label <label>` — command position via _split_commands (the house
    scanner; a deliberate in-module reuse), so an echoed string containing the
    full command line never satisfies this."""
    import shlex
    entries = parsed_run_steps(text)
    if entries is None:
        return ["run entries unavailable"]
    for _job, _idx, run_text, _line in entries:
        joined = run_text.replace("\\\n", " ")
        for line in joined.splitlines():
            if "gh issue create" not in line:
                continue
            raw_segments, scan_ok = _split_commands(line)
            if not scan_ok:
                continue
            for _sep, body, _stdin in raw_segments:
                try:
                    toks = shlex.split(body, comments=True)
                except ValueError:
                    continue
                while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
                    toks = toks[1:]
                if toks[:3] != ["gh", "issue", "create"]:
                    continue
                for i in range(3, len(toks) - 1):
                    if toks[i] == "--label" and toks[i + 1] == label:
                        return []
    return [f"no real `gh issue create --label {label}` invocation found"]


def parsed_run_steps(text):
    """#165 D6: run blocks enumerated from the PARSED document — bare-dash items
    and quoted key spellings included; values arrive DECODED by the parser (D7
    feeds `bash -n` from here). Returns [(job, step_index, run_text, line)], or
    None when ruby is unavailable or the document does not parse."""
    root, _census, err = parsed_workflow(text)
    if root is None or err is not None:
        return None
    resolved, _ = resolve_aliases(root)
    if resolved is None or resolved.get("t") != "m":
        return []
    out = []
    jobs = _map_get(resolved, "jobs")
    if jobs is None or jobs.get("t") != "m":
        return []
    for jk, jv in jobs.get("c", []):
        if jv.get("t") != "m":
            continue
        steps = _map_get(jv, "steps")
        if steps is None or steps.get("t") != "q":
            continue
        for idx, item in enumerate(steps.get("c", []), 1):
            if not isinstance(item, dict) or item.get("t") != "m":
                continue
            for k, val in item.get("c", []):
                if _scalar(k) == "run" and val.get("t") == "s":
                    out.append((_scalar(jk), idx, val.get("v"), val.get("line")))
    return out


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


#: vibe-165 D2″ — the EXACT documented arity per function; ("odd", n) means an
#: odd count of at least n.
_FUNC_ARITY = {
    "contains": (2, 2), "startsWith": (2, 2), "endsWith": (2, 2),
    "format": (1, None), "join": (1, 2), "toJSON": (1, 1), "fromJSON": (1, 1),
    "hashFiles": (1, None), "always": (0, 0), "success": (0, 0),
    "failure": (0, 0), "cancelled": (0, 0), "case": ("odd", 3),
}

_EXPR_LEX = re.compile(
    r"\s+"
    r"|'(?:[^']|'')*'"                                  # single-quoted, '' escape
    r"|0x[0-9A-Fa-f]+"
    r"|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    r"|[A-Za-z_][A-Za-z0-9_-]*"
    r"|&&|\|\||[=!<>]=|[<>]|!"
    r"|[()\[\],.*-]")


class _ExprError(Exception):
    pass


class _ExprParser:
    """A real recursive-descent parser for the documented Actions expression
    language (vibe-165 D2/D2″). It accepts the documented grammar — every
    context root, single-quoted strings with '' escapes, negative/hex/exponent
    numbers, repeatable postfix (.ident | .* | [expr]), the documented function
    set at its EXACT arities, unary !, comparisons, &&/|| with precedence —
    and consumes its FULL input. It rejects the demonstrated bad classes by
    construction: unbalanced parens, `..`, malformed or empty index access,
    unknown roots and functions, operator runs, double-quoted literals,
    trailing garbage. It does not claim bug-for-bug equivalence with Actions'
    evaluator; E8.7's live matrix is the real oracle."""

    def __init__(self, text):
        self.toks = []
        pos = 0
        while pos < len(text):
            m = _EXPR_LEX.match(text, pos)
            if not m:
                raise _ExprError(f"bad character at {pos}: {text[pos]!r}")
            if not m.group(0).isspace():
                self.toks.append(m.group(0))
            pos = m.end()
        self.i = 0

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else None

    def take(self, want=None):
        tok = self.peek()
        if tok is None or (want is not None and tok != want):
            raise _ExprError(f"expected {want!r}, got {tok!r}")
        self.i += 1
        return tok

    def parse(self):
        self.expr()
        if self.peek() is not None:
            raise _ExprError(f"trailing input at {self.peek()!r}")

    def expr(self):
        self.and_expr()
        while self.peek() == "||":
            self.take()
            self.and_expr()

    def and_expr(self):
        self.cmp_expr()
        while self.peek() == "&&":
            self.take()
            self.cmp_expr()

    def cmp_expr(self):
        self.unary()
        while self.peek() in ("==", "!=", "<", "<=", ">", ">="):
            self.take()
            self.unary()

    def unary(self):
        if self.peek() == "!":
            self.take()
            self.unary()
            return
        if self.peek() == "-":
            self.take()
            tok = self.peek()
            if tok is None or not re.fullmatch(
                    r"0x[0-9A-Fa-f]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", tok):
                raise _ExprError("unary minus takes a numeric literal")
            self.take()
            self.postfix()
            return
        self.primary()
        self.postfix()

    def primary(self):
        tok = self.peek()
        if tok is None:
            raise _ExprError("unexpected end of expression")
        if tok == "(":
            self.take()
            self.expr()
            self.take(")")
            return
        if tok.startswith("'") or re.fullmatch(
                r"0x[0-9A-Fa-f]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", tok):
            self.take()
            return
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", tok):
            self.take()
            if self.peek() == "(":
                if tok not in _ALLOWED_FUNCS:
                    raise _ExprError(f"unknown function {tok!r}")
                self.take("(")
                count = 0
                if self.peek() != ")":
                    self.expr()
                    count = 1
                    while self.peek() == ",":
                        self.take()
                        self.expr()
                        count += 1
                self.take(")")
                lo, hi = _FUNC_ARITY[tok]
                if lo == "odd":
                    if count < hi or count % 2 == 0:
                        raise _ExprError(f"{tok} takes an odd count >= {hi}, "
                                         f"got {count}")
                elif count < lo or (hi is not None and count > hi):
                    raise _ExprError(f"{tok} arity {lo}..{hi}, got {count}")
                return
            if tok in ("true", "false", "null"):
                return
            if tok not in _ALLOWED_ROOTS:
                raise _ExprError(f"unknown context root {tok!r}")
            return
        raise _ExprError(f"unexpected token {tok!r}")

    def postfix(self):
        while True:
            tok = self.peek()
            if tok == ".":
                self.take()
                nxt = self.peek()
                if nxt == "*":
                    self.take()
                elif nxt is not None and re.fullmatch(
                        r"[A-Za-z_][A-Za-z0-9_-]*", nxt):
                    self.take()
                else:
                    raise _ExprError(f"bad property access before {nxt!r}")
            elif tok == "[":
                self.take()
                if self.peek() == "]":
                    raise _ExprError("empty index access")
                self.expr()
                self.take("]")
            else:
                return


def _expr_ok(inner):
    try:
        _ExprParser(inner).parse()
        return True
    except _ExprError:
        return False


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


class TestParsedLint(unittest.TestCase):
    """#165 W3 — the parsed-document lint family. Each fixture is the issue's own
    spoof: the quoted-colon permissions (9), the block-scalar job (7), the
    bare-dash step and quoted "run": key (10), the computed secret index (6),
    and the inline-flow jobs mapping (2, validate endpoint)."""

    BASE = (
        "name: t\n"
        "on:\n"
        "  push: {}\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  a:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo ok\n"
    )

    def setUp(self):
        if _ruby() is None:
            self.skipTest("ruby unavailable")

    def test_the_scaffold_itself_is_clean(self):
        self.assertEqual(lint(self.BASE), [])

    def test_permissions_scalar_rejected_at_workflow_level(self):
        text = self.BASE.replace("permissions:\n  contents: read",
                                 'permissions: "not: a mapping"')
        self.assertIn("workflow: permissions parses to a scalar, not a mapping "
                      "or read-all/write-all", lint(text))

    def test_permissions_scalar_rejected_at_job_level(self):
        text = self.BASE.replace(
            "    runs-on: ubuntu-latest",
            '    runs-on: ubuntu-latest\n    permissions: "not: a mapping"')
        self.assertIn("job 'a': permissions parses to a scalar, not a mapping "
                      "or read-all/write-all", lint(text))

    def test_read_all_scalar_is_accepted(self):
        text = self.BASE.replace("permissions:\n  contents: read",
                                 "permissions: read-all")
        self.assertEqual([x for x in lint(text) if "parses to a" in x], [])

    def test_block_scalar_job_rejected(self):
        text = ("name: t\non:\n  push: {}\npermissions:\n  contents: read\n"
                "jobs:\n  a: |2\n    runs-on: ubuntu-latest\n")
        self.assertIn("job 'a': parses to a scalar, not a mapping - a block "
                      "scalar cannot impersonate a job", lint(text))

    def test_jobs_scalar_rejected(self):
        text = self.BASE.split("jobs:\n")[0] + "jobs: hello\n"
        self.assertIn("jobs parses to a scalar, not a mapping", lint(text))

    def test_bare_dash_step_without_run_rejected(self):
        text = self.BASE.replace("      - run: echo ok",
                                 "      -\n        name: no action")
        self.assertIn("job 'a' step 1: neither 'run' nor 'uses' (parsed - "
                      "bare-dash and quoted spellings included)", lint(text))

    def test_quoted_run_key_is_recognised(self):
        # Before #165 the line grammar falsely rejected this legal step.
        text = self.BASE.replace('      - run: echo ok', '      - "run": echo ok')
        self.assertEqual(lint(text), [])

    def test_flow_workflow_validates_equal_to_block_twin(self):
        # FULLY flow — permissions included, per D4's oracle (step-8 F4): the
        # twin differs from the block spelling in nothing but syntax, and the
        # violation lists must be EQUAL.
        block = self.BASE.replace("      - run: echo ok",
                                  "      -\n        name: no action")
        flow = ("name: t\non:\n  push: {}\npermissions: {contents: read}\n"
                "jobs: {a: {runs-on: ubuntu-latest, "
                "steps: [{name: no action}]}}\n")
        self.assertEqual(lint(flow), lint(block))
        self.assertIn("job 'a' step 1: neither 'run' nor 'uses' (parsed - "
                      "bare-dash and quoted spellings included)", lint(flow))
        self.assertFalse(any("cannot validate" in x for x in lint(flow)),
                         "the flow refusal must be dead when ruby is available")
        # and the flow permissions spelling is genuinely VALIDATED, not skipped
        bad = flow.replace("{contents: read}", "{id-token: read}")
        self.assertIn("workflow: permission 'id-token: read' is outside the "
                      "documented values (none|write)", lint(bad))

    def test_flow_refusal_stands_without_ruby(self):
        flow = (self.BASE.split("jobs:\n")[0] +
                "jobs: {a: {runs-on: ubuntu-latest, steps: [{run: echo ok}]}}\n")
        with unittest.mock.patch(f"{__name__}._ruby", return_value=None):
            self.assertIn("jobs: uses an inline flow mapping, which this lint "
                          "cannot validate; use block style", lint(flow))

    def test_computed_secret_index_refused(self):
        text = self.BASE.replace(
            "echo ok", "echo ${{ secrets[format('SNEAKY_{0}', 'TOKEN')] }}")
        self.assertTrue(any(x.startswith("line 10: computed secret index")
                            for x in lint(text)), lint(text))

    def test_literal_secret_index_is_not_computed(self):
        text = self.BASE.replace("echo ok",
                                 "echo ${{ secrets['GITHUB_TOKEN'] }}")
        self.assertEqual([x for x in lint(text) if "computed secret" in x], [])

    def test_explicit_tag_refused_via_lint(self):
        text = self.BASE.replace("echo ok", "!!str echo ok")
        self.assertTrue(any(x.startswith("explicit tag") for x in lint(text)),
                        lint(text))

    def test_live_workflows_pass_the_full_lint(self):
        """#165 item 10: live workflows now receive the lint. The FULL lint is
        empirically clean on all 8 live files today; the binding contract for
        live files is the structural family (well-formedness, expressions,
        permissions, value shapes, steps/runs) — if a future live workflow
        legitimately needs a secret or helper outside the auditor contract
        sets, the recorded remedy is scoping those families, not skipping the
        file."""
        live = sorted(LIVE_WF_DIR.glob("*.yml"))
        self.assertEqual(len(live), 8, [p.name for p in live])
        for p in live:
            with self.subTest(workflow=p.name):
                self.assertEqual(lint(p.read_text(), p.name), [])

    @staticmethod
    def _py_census(root):
        # An INDEPENDENT recount, in Python, over the emitted tree — mirroring
        # census()'s walk so equality proves the bridge dropped no nodes.
        jobs = steps = runs = 0
        if root.get("t") == "m":
            for k, v in root["c"]:
                if k.get("t") == "s" and k.get("v") == "jobs" \
                        and v.get("t") == "m":
                    for _jk, jv in v["c"]:
                        jobs += 1
                        if jv.get("t") != "m":
                            continue
                        for sk, sv in jv["c"]:
                            if sk.get("t") == "s" and sk.get("v") == "steps" \
                                    and sv.get("t") == "q":
                                for item in sv["c"]:
                                    steps += 1
                                    if item.get("t") != "m":
                                        continue
                                    for ik, _iv in item["c"]:
                                        if ik.get("t") == "s" \
                                                and ik.get("v") == "run":
                                            runs += 1
        return {"jobs": jobs, "steps": steps, "runs": runs}

    def test_census_recount_over_all_26_workflows(self):
        """The ruby-side census (counted during emission) must equal a Python
        recount of the emitted tree, per workflow; the totals pin the corpus:
        26 workflows, 48 jobs, 278 steps, 132 run entries."""
        total = {"jobs": 0, "steps": 0, "runs": 0}
        count = 0
        for d in (WF_DIR, LIVE_WF_DIR):
            for p in sorted(d.glob("*.yml")):
                root, census, err = parsed_workflow(p.read_text())
                self.assertIsNone(err, (p.name, err))
                count += 1
                with self.subTest(workflow=p.name):
                    self.assertEqual(census, self._py_census(root))
                for key in total:
                    total[key] += census[key]
        self.assertEqual(count, 26)
        self.assertEqual(total, {"jobs": 48, "steps": 278, "runs": 132})

    def test_decoding_changes_the_bash_n_verdict(self):
        """#165 item 8: the raw spelling of a double-quoted run scalar is a
        single shell WORD — `bash -n` accepts it — while its DECODED value is
        broken shell. Only the decoded path can see that."""
        raw = '"echo \\"hi\\" && ("'
        decoded_entries = parsed_run_steps(
            self.BASE.replace("- run: echo ok", f"- run: {raw}"))
        (job, idx, decoded, _line) = decoded_entries[0]
        self.assertEqual(decoded, 'echo "hi" && (')
        r_raw = subprocess.run(["bash", "-n"], input=raw,
                               capture_output=True, text=True)
        r_dec = subprocess.run(["bash", "-n"], input=decoded,
                               capture_output=True, text=True)
        self.assertEqual(r_raw.returncode, 0, "raw text is one quoted word")
        self.assertNotEqual(r_dec.returncode, 0, "decoded shell is broken")

    def test_every_run_entry_passes_bash_n_decoded(self):
        """#165 item 8 (D7): `bash -n` over the PARSER-DECODED value of every
        run entry Psych finds — all spellings, both directories, exactly 132.
        The raw-text sibling in TestLintClean keeps its own count; this one is
        independent by enumerator AND by text handed to the shell."""
        live = sorted(set(LIVE_WF_DIR.glob("*.yml"))
                      | set(LIVE_WF_DIR.glob("*.yaml")))
        paths = [WF_DIR / n for n in EXPECTED] + live
        checked = 0
        for path in paths:
            entries = parsed_run_steps(path.read_text())
            self.assertIsNotNone(entries, path.name)
            for job, idx, run_text, _line in entries:
                checked += 1
                shell = re.sub(r"\$\{\{.*?\}\}", "EXPR", run_text, flags=re.S)
                r = subprocess.run(["bash", "-n"], input=shell,
                                   capture_output=True, text=True)
                with self.subTest(workflow=path.name, job=job, step=idx):
                    self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(checked, 132)

    def test_run_steps_enumerated_from_the_parsed_document(self):
        """extract_run_blocks() misses a quoted "run": key (the recorded item-10
        gap); parsed_run_steps() sees it, decoded."""
        text = self.BASE.replace(
            "      - run: echo ok",
            '      - "run": |\n          echo "hi"\n          set -e')
        self.assertEqual(list(extract_run_blocks(text)), [],
                         "the raw extractor still misses the quoted spelling")
        got = parsed_run_steps(text)
        self.assertEqual(got, [("a", 1, 'echo "hi"\nset -e\n', 10)])


class TestPermissionsVocabulary(unittest.TestCase):
    """#165 item 5 (D9): the permissions vocabulary comes from a VENDORED
    upstream source — github/docs' own reusable at a recorded commit — with
    scope names and value enums extracted at test time. Two hand-maintained
    tables were each wrong in both directions; the .provenance note records
    the pin, the refresh command, and the two probed-and-refused sources
    (SchemaStore, github/docs HEAD post-Models-retirement)."""

    def setUp(self):
        if _ruby() is None:
            self.skipTest("ruby unavailable")

    def test_conformance_gate(self):
        """The three anchors the E8.2a rounds distilled. A source failing any
        of them repeats a recorded mistake: `models` was dropped once,
        `id-token: read` was accepted once, `vulnerability-alerts` postdates
        both hand tables."""
        vocab = permissions_vocabulary()
        self.assertIn("read", vocab["models"])
        self.assertNotIn("read", vocab["id-token"])
        self.assertIn("write", vocab["id-token"])
        self.assertIn("vulnerability-alerts", vocab)
        self.assertNotIn("write", vocab["vulnerability-alerts"])

    def test_extraction_fails_loudly_on_a_reshaped_fixture(self):
        with self.assertRaises(AssertionError):
            _extract_permissions_vocab("no fence here")
        with self.assertRaises(AssertionError):
            _extract_permissions_vocab("```yaml\ncontents: read|write|none\n```")

    def test_staleness_guard_every_used_scope_is_admitted(self):
        """A schema too old for our own tree must fail loudly: every
        (scope, value) any of the 26 workflows declares — workflow and job
        level, flow spellings included — must be admitted. (The `models`
        anchor is SOURCE-side, in test_conformance_gate: no workflow declares
        it today; a hand table dropping it was wrong about GitHub's
        vocabulary, not about this tree.)"""
        vocab = permissions_vocabulary()
        used = set()

        def collect(node, wf):
            if node.get("t") != "m":
                return
            for k, v in node.get("c", []):
                if _scalar(k) == "permissions" and v.get("t") == "m":
                    for pk, pv in v.get("c", []):
                        used.add((wf, _scalar(pk), _scalar(pv)))
                collect(v, wf)

        for d in (WF_DIR, LIVE_WF_DIR):
            for p in sorted(d.glob("*.yml")):
                root, _c, err = parsed_workflow(p.read_text())
                self.assertIsNone(err, (p.name, err))
                resolved, _ = resolve_aliases(root)
                collect(resolved, p.name)
        self.assertGreater(len(used), 10)
        for wf, scope, val in sorted(used):
            with self.subTest(workflow=wf, scope=scope):
                self.assertIn(scope, vocab)
                self.assertIn(val, vocab[scope])

    BASE = TestParsedLint.BASE

    def test_id_token_read_rejected(self):
        text = self.BASE.replace("  contents: read", "  id-token: read")
        self.assertIn("workflow: permission 'id-token: read' is outside the "
                      "documented values (none|write)", lint(text))

    def test_unknown_scope_rejected(self):
        text = self.BASE.replace("  contents: read", "  frobnicate: read")
        self.assertIn("workflow: unknown permission scope 'frobnicate'",
                      lint(text))

    def test_flow_spelling_at_job_level_is_validated(self):
        text = self.BASE.replace(
            "    runs-on: ubuntu-latest",
            "    runs-on: ubuntu-latest\n"
            "    permissions: {id-token: read}")
        self.assertIn("job 'a': permission 'id-token: read' is outside the "
                      "documented values (none|write)", lint(text))

    def test_empty_mapping_and_valid_scopes_accepted(self):
        text = self.BASE.replace("permissions:\n  contents: read",
                                 "permissions: {}")
        self.assertEqual(lint(text), [])
        text = self.BASE.replace("  contents: read",
                                 "  contents: read\n  models: read\n"
                                 "  vulnerability-alerts: read")
        self.assertEqual(lint(text), [])


class TestStageLabelOperative(unittest.TestCase):
    """#165 4-comment (D8): the stage entry label proven OPERATIVE, judged
    trigger-relatively from the AST — never from raw text, which is how three
    line-matcher attempts were each defeated (comment, echo, block-scalar
    fake if:). The recognized workflow_dispatch escape is the operator's
    documented manual entry; everything else must gate."""

    CONSUMERS = {name: label for name, label in STAGES.items()
                 if label and name not in LABEL_PRODUCERS}

    def setUp(self):
        if _ruby() is None:
            self.skipTest("ruby unavailable")

    def test_consumer_entry_jobs_gate_on_their_labels(self):
        self.assertEqual(set(self.CONSUMERS), {"auditor-audit.yml",
                                               "auditor-contribute.yml",
                                               "auditor-case-study.yml"})
        for name, label in self.CONSUMERS.items():
            with self.subTest(workflow=name):
                text = (WF_DIR / name).read_text()
                self.assertEqual(label_gate_violations(text, label), [])

    def test_producer_invocation_carries_the_label(self):
        text = (WF_DIR / "auditor-discover.yml").read_text()
        self.assertEqual(
            producer_label_violations(text, STAGES["auditor-discover.yml"]
                                      or "audit-candidate"), [])

    # -- the two algorithm-pinning fixtures ---------------------------------

    def test_true_disjunct_defeats_the_gate(self):
        for expr in (
                "github.event_name == 'workflow_dispatch' || true "
                "|| github.event.label.name == 'audit-ready'",
                "true || github.event.label.name == 'audit-ready'"):
            gated, reason = _gates_on_label(expr, "audit-ready")
            self.assertFalse(gated, expr)
            self.assertIn("does not carry the label equality", reason)

    def test_reordered_equality_still_gates(self):
        gated, _ = _gates_on_label(
            "github.event.label.name == 'audit-ready' "
            "|| github.event_name == 'workflow_dispatch'", "audit-ready")
        self.assertTrue(gated)
        gated, _ = _gates_on_label(
            "'audit-ready' == github.event.label.name", "audit-ready")
        self.assertTrue(gated)

    def test_an_unrecognized_escape_disjunct_does_not_gate(self):
        # D8″'s fixture (step-8 F5): only the DOCUMENTED workflow_dispatch
        # equality is a recognized escape — any other ungated disjunct defeats
        # the label however legitimate it looks.
        gated, reason = _gates_on_label(
            "github.actor == 'x' || github.event.label.name == 'audit-ready'",
            "audit-ready")
        self.assertFalse(gated)
        self.assertIn("does not carry the label equality", reason)

    def test_a_negated_equality_does_not_gate(self):
        # D8″'s fixture (step-8 F5): the equality under `!` gates on the
        # label's ABSENCE. The parenthesized form falls to the judged-shape
        # refusal; the bare form is a non-gating disjunct.
        for expr in ("!(github.event.label.name == 'audit-ready')",
                     "!github.event.label.name == 'audit-ready'"):
            gated, _reason = _gates_on_label(expr, "audit-ready")
            self.assertFalse(gated, expr)

    def test_dispatch_escape_alone_never_gates(self):
        gated, reason = _gates_on_label(
            "github.event_name == 'workflow_dispatch'", "audit-ready")
        self.assertFalse(gated)
        self.assertIn("only the dispatch escape remains", reason)

    def test_unjudgeable_shape_fails_closed(self):
        gated, reason = _gates_on_label(
            "contains(github.event.label.name, 'audit-ready')", "audit-ready")
        self.assertFalse(gated)
        self.assertIn("outside the judged gating shape", reason)

    # -- the smuggling shapes that defeated three line-matcher attempts -----

    _SMUGGLE_BASE = (
        "name: t\n"
        "on:\n"
        "  issues: {}\n"
        "permissions:\n"
        "  contents: read\n"
        "jobs:\n"
        "  a:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: echo ok\n"
    )

    def test_comment_label_is_not_a_gate(self):
        text = self._SMUGGLE_BASE.replace(
            "  a:\n", "  # gate: audit-ready\n  a:\n")
        self.assertEqual(label_gate_violations(text, "audit-ready"),
                         ["entry job 'a': no if: gate"])

    def test_echoed_equality_is_not_a_gate(self):
        text = self._SMUGGLE_BASE.replace(
            "echo ok",
            "echo \"github.event.label.name == 'audit-ready'\"")
        self.assertEqual(label_gate_violations(text, "audit-ready"),
                         ["entry job 'a': no if: gate"])

    def test_block_scalar_fake_if_is_not_a_gate(self):
        text = self._SMUGGLE_BASE.replace(
            "      - run: echo ok",
            "      - run: |  # note\n"
            "          if: ${{ github.event.label.name == 'audit-ready' }}\n"
            "          echo ok")
        self.assertEqual(label_gate_violations(text, "audit-ready"),
                         ["entry job 'a': no if: gate"])

    def test_echoed_producer_command_is_not_an_invocation(self):
        text = self._SMUGGLE_BASE.replace(
            "echo ok", 'echo "gh issue create --label audit-candidate"')
        self.assertEqual(
            producer_label_violations(text, "audit-candidate"),
            ["no real `gh issue create --label audit-candidate` invocation "
             "found"])

    def test_real_file_mutation_comment_smuggle_is_caught(self):
        """The first defeated matcher accepted a header comment. Remove the
        real if: from auditor-audit.yml and leave the label in a comment —
        the AST judge must flag the ungated entry job."""
        real = (WF_DIR / "auditor-audit.yml").read_text()
        needle = ("    if: ${{ github.event_name == 'workflow_dispatch' || "
                  "github.event.label.name == 'audit-ready' }}\n")
        self.assertIn(needle, real, "the real gate moved — update this mutation")
        mutated = real.replace(needle, "    # gate: audit-ready\n")
        self.assertNotEqual(mutated, real)
        self.assertTrue(any("no if: gate" in x
                            for x in label_gate_violations(mutated,
                                                           "audit-ready")))


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
        (then-116) blocks were unprotected by this regression. That is the same defect as the
        extractor skipping dash form: a true-sounding name over a narrower set.

        The loop now covers both directories and both extensions. It does NOT cover quoted
        `"run":` keys, which the extractor does not recognise — the Psych enumerator
        (`parsed_run_steps`, #165) does; it finds 132 run entries today, all block-scalar
        unquoted spellings, so the two counts match in fact, not by construction. The
        decoded-text twin of this check lives in TestParsedLint.
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
        # LIMIT: this recount uses the SAME extractor, so it detects a shrinking FILE
        # LIST but cannot reveal a spelling the extractor never recognised — a quoted `"run":`
        # key yields zero blocks in both counts. The genuinely independent enumerator
        # (`parsed_run_steps`, #165) finds 132 run entries today, matching this count exactly
        # — TestParsedLint pins that equality and bash-checks the DECODED text.
        expected = sum(1 for pth in paths for _ in extract_run_blocks(pth.read_text()))
        self.assertEqual(checked, expected,
                         f"checked {checked} run blocks but the corpus holds {expected}")
        self.assertGreater(expected, 100,
                           f"the corpus should hold ~132 run blocks, found {expected} — the "
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
        it can actually establish — the label appears in the file. The OPERATIVE proof lives
        in TestStageLabelOperative (#165): trigger-relative AST judgement of the entry jobs'
        if: expressions plus the producer's real argv. E8.7's live matrix exercises the real
        state machine against GitHub's own evaluator.
        """
        for name, label in STAGES.items():
            if label:
                with self.subTest(workflow=name):
                    self.assertIn(label, self._text(name),
                                  f"{name} must mention its entry label {label!r} "
                                  f"(presence only; the operative proof is "
                                  f"TestStageLabelOperative)")

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

    def test_permissions_declaration_and_vocabulary(self):
        """Authority must be DECLARED, and declared vocabulary must be VALID.

        A hand scope/value table lived here briefly and was wrong in both directions across
        two attempts — recalled from memory it omitted `artifact-metadata`, `code-quality`
        and `vulnerability-alerts` and accepted the invalid `id-token: read`; corrected from
        a documentation summary it then dropped the valid `models: read|none`. Encoding a
        vocabulary GitHub revises kept producing over-rejections of real workflows.

        #165 replaced the hand table with extraction from the VENDORED github/docs source
        (see permissions_vocabulary and TestPermissionsVocabulary); the spellings below are
        exactly the ones the old tables got wrong, now passing against the real vocabulary.
        """
        # an undeclared workflow is still a violation — that is the least-privilege contract
        self._assert_flagged(self.GOOD.replace("permissions:\n  contents: read\n", ""))
        # and every VALID declared spelling passes — the parsed stage judges them all now
        for spelling in ("permissions:\n  contents: read\n",
                         "permissions:\n  models: read\n",
                         "permissions:\n  artifact-metadata: read\n",
                         "permissions: read-all\n",
                         "permissions: {}\n"):
            with self.subTest(spelling=spelling.strip()):
                self.assertEqual(
                    lint(self.GOOD.replace("permissions:\n  contents: read\n", spelling)), [],
                    "valid vocabulary must pass — over-rejection is the recorded failure mode")

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


def _split_commands(line):
    """Quote-aware command segmentation for `check_call_sites`.

    Returns (prev_separator, text, has_stdin_redirect) triples. Built character-wise
    because token-level splitting after shlex cannot tell a PIPE from a quoted "|"
    argument — the difference between a command position and a spoof. Unquoted
    `$( … )` contents recurse as their own lines (each inner command is validated
    with its own argv — nesting cannot hide a flag), leaving a placeholder token as
    the outer value. An unquoted redirect ends the command's argv: the redirect's
    target belongs to the redirect, never to a flag."""
    segments = []
    state = {"ok": True}

    def scan(text):
        cur, sep, stdin_in = [], "", False
        i, n, quote = 0, len(text), None

        def flush(new_sep):
            nonlocal cur, sep, stdin_in
            body = "".join(cur).strip()
            if body:
                segments.append((sep, body, stdin_in))
            cur, sep, stdin_in = [], new_sep, False

        while i < n:
            c = text[i]
            if quote == '"' and text[i:i + 2] == "$(":
                # the shell substitutes inside double quotes; recurse there too,
                # leaving the placeholder inside the quoted value
                depth, j, q2 = 1, i + 2, None
                while j < n and depth:
                    d = text[j]
                    if q2:
                        if d == q2:
                            q2 = None
                    elif d in "'\"":
                        q2 = d
                    elif text[j:j + 2] == "$(":
                        depth += 1
                        j += 1
                    elif d == "(":
                        depth += 1
                    elif d == ")":
                        depth -= 1
                    j += 1
                if depth:
                    # an unclosed $( reached EOF: slicing would silently truncate
                    # the argv and validate a corrupted rendering — poison instead
                    state["ok"] = False
                    return
                scan(text[i + 2:j - 1])
                cur.append("__SUBST__")
                i = j
                continue
            if quote:
                cur.append(c)
                if c == quote:
                    quote = None
                i += 1
                continue
            if c in "'\"":
                quote = c
                cur.append(c)
                i += 1
                continue
            if text[i:i + 2] == "$(":
                depth, j, q2 = 1, i + 2, None
                while j < n and depth:
                    d = text[j]
                    if q2:
                        if d == q2:
                            q2 = None
                    elif d in "'\"":
                        q2 = d
                    elif text[j:j + 2] == "$(":
                        depth += 1
                        j += 1
                    elif d == "(":
                        depth += 1
                    elif d == ")":
                        depth -= 1
                    j += 1
                if depth:
                    # an unclosed $( reached EOF: slicing would silently truncate
                    # the argv and validate a corrupted rendering — poison instead
                    state["ok"] = False
                    return
                scan(text[i + 2:j - 1])
                cur.append(" __SUBST__ ")
                i = j
                continue
            if c in ";&|":
                two = text[i:i + 2]
                if two in ("&&", "||"):
                    flush(two)
                    i += 2
                else:
                    flush(c)
                    i += 1
                continue
            if c in "<>":
                if c == "<":
                    stdin_in = True
                # a digit prefix (2>>) is part of the redirect, not an argument
                while cur and cur[-1].isdigit():
                    cur.pop()
                # consume the operator and its target INLINE — the shell keeps
                # collecting arguments after a redirect, so ending argv here let
                # `… 2>>err.log --wrong x` smuggle flags past validation
                while i < n and text[i] in "<>&":
                    i += 1
                while i < n and text[i] == " ":
                    i += 1
                while i < n and text[i] not in " ;&|":
                    i += 1
                cur.append(" ")
                continue
            cur.append(c)
            i += 1
        flush("")

    scan(line)
    return segments, state["ok"]


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
            raw_segments, scan_ok = _split_commands(line)
            segments, bad_parse = [], not scan_ok
            for sep, body, stdin_in in raw_segments:
                try:
                    seg_tokens = shlex.split(body, comments=True)
                except ValueError:
                    bad_parse = True
                    continue
                if seg_tokens:
                    segments.append((sep, seg_tokens, stdin_in))
            if bad_parse:
                for helper in hits:
                    if (wf_name, helper) not in roster:
                        violations.append(f"{wf_name}:{line_no} {helper}: unparseable "
                                          f"call site and not on the extracted-run roster")
            for helper in hits:
                needle = f"auditor/scripts/{helper}"
                contract = contracts[helper]
                where = f"{wf_name}:{line_no} {helper}"
                found = False
                for sep, segment, stdin_in in segments:
                    indices = [i for i, t in enumerate(segment) if needle in t]
                    if not indices:
                        continue
                    found = True
                    if len(indices) > 1:
                        violations.append(f"{where}: {len(indices)} occurrences in "
                                          f"one command segment — only one can be "
                                          f"the invocation")
                    index = indices[0]
                    if contract.get("sourced"):
                        if index == 0 or segment[index - 1] not in (".", "source"):
                            violations.append(
                                f"{where}: function library referenced without "
                                f"sourcing (expected `. .../{helper}`)")
                        continue
                    interpreter = segment[index - 1] if index > 0 else ""
                    prefix_ok = all(
                        t in ("if", "!", "then", "else", "elif", "do", "while",
                              "until", "time")
                        or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t)
                        for t in segment[:max(index - 1, 0)])
                    if interpreter not in ("python3", "bash") or not prefix_ok:
                        violations.append(f"{where}: referenced without an "
                                          f"interpreter invocation in command "
                                          f"position (a mention is not a call)")
                        continue
                    if contract.get("stdin") and sep != "|" and not stdin_in:
                        violations.append(f"{where}: stdin helper invoked without "
                                          f"piped or redirected input")
                    args = segment[index + 1:]
                    flags, positionals, i = set(), 0, 0
                    boolean = contract.get("boolean", set())
                    redirect = re.compile(r"^(\d*>>?|<|&>>?)$")
                    while i < len(args):
                        token = args[i]
                        if redirect.match(token) or token in ("then", "do"):
                            break
                        if token.startswith("--"):
                            flag, eq, value = token.partition("=")
                            flags.add(flag)
                            if flag in boolean:
                                if eq:
                                    violations.append(f"{where}: boolean {flag} "
                                                      f"takes no value")
                                i += 1
                                continue
                            if eq:
                                if not value:
                                    violations.append(f"{where}: {flag} is missing "
                                                      f"its value")
                                i += 1
                                continue
                            if i + 1 >= len(args) or args[i + 1].startswith("--") \
                                    or redirect.match(args[i + 1]) \
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
    "diff-findings.py": {"required": {"--repo", "--original-sidecar",
                                      "--reaudit-sidecar", "--registry",
                                      "--commit-sha-before", "--commit-sha-after",
                                      "--events-out", "--diff-report-out",
                                      "--summary-out"},
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
    "propose-rule-citations.py": {"required": {"--data-dir", "--rules-path"},
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
    "vendor_default_filter.py": {"required": set(), "allowed": {"--report"},
                                 "boolean": {"--report"}},
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

    def test_mutation_empty_equals_value(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir=')
        self.assertTrue(any("missing its value" in s for s in v), v)

    def test_mutation_redirection_is_not_a_value(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir > out.txt')
        self.assertTrue(any("missing its value" in s for s in v), v)

    def test_mutation_a_mention_is_not_a_call(self):
        v = self._check('echo "see $CODE_DIR/auditor/scripts/fake-helper.py"')
        self.assertTrue(any("not a call" in s for s in v), v)

    def test_mutation_two_occurrences_in_one_segment(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir "$CODE_DIR/auditor/scripts/fake-helper.py"')
        self.assertTrue(any("occurrences in one command segment" in s for s in v), v)

    def test_mutation_assignment_substitution_form_is_validated(self):
        # OUT="$(python3 helper …)" is a real production shape; the unwrap must
        # expose the invocation to the same checks
        good = self._check('OUT="$(python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                           '--data-dir d)"')
        self.assertEqual(good, [], good)
        bad = self._check('OUT="$(python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                          '--wrong x)"')
        self.assertTrue(any("unknown flags" in s for s in bad), bad)

    def test_mutation_interpreter_adjacency_cannot_be_spoofed(self):
        v = self._check('echo python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir d')
        self.assertTrue(any("command position" in s for s in v), v)

    def test_mutation_stdin_contract_requires_piped_input(self):
        contracts = {"fake-helper.py": {"required": set(), "allowed": set(),
                                        "stdin": True}}
        bad = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py"',
                          contracts)
        self.assertTrue(any("without piped" in s for s in bad), bad)
        good = self._check('cat body.txt | python3 '
                           '"$CODE_DIR/auditor/scripts/fake-helper.py"', contracts)
        self.assertEqual(good, [], good)

    def test_mutation_numbered_redirection_is_not_a_value(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir 2>> err.log')
        self.assertTrue(any("missing its value" in s for s in v), v)

    def test_mutation_nested_substitution_keeps_flag_extraction_honest(self):
        # a nested substitution that still tokenizes must be validated on its REAL
        # flags — a planted unknown flag inside the same site must still be caught
        v = self._check('OUT="$(python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--wrong "$(dirname "$X")")"')
        self.assertTrue(any("unknown flags" in s for s in v), v)

    def test_mutation_parity_breaking_unwrap_fails_closed(self):
        # when the rewrite would lose quote parity, the original line is kept and
        # shlex fails CLOSED — never a validated corrupted rendering
        v = self._check('OUT="$(python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir "unclosed)')
        self.assertTrue(v, "a parity-breaking site produced zero violations — the "
                           "corrupted rendering was validated")

    def test_mutation_quoted_pipe_cannot_spoof_command_position(self):
        # iteration 4: a quoted "|" is an argument, not a separator — the segment's
        # command is still echo, and a mention is not a call
        v = self._check('echo "|" python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir d')
        self.assertTrue(any("command position" in s for s in v), v)

    def test_mutation_quoted_stdin_char_does_not_satisfy_the_contract(self):
        contracts = {"fake-helper.py": {"required": set(), "allowed": set(),
                                        "stdin": True, "positionals": (0, 5)}}
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" "<"',
                        contracts)
        self.assertTrue(any("without piped" in s for s in v), v)

    def test_mutation_attached_redirect_is_not_a_value(self):
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir 2>>err.log')
        self.assertTrue(any("missing its value" in s for s in v), v)

    def test_mutation_two_substitutions_cannot_hide_a_flag(self):
        v = self._check('A="$(python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--wrong "$(dirname "$X")")" B="$(date -u)"')
        self.assertTrue(any("unknown flags" in s for s in v), v)

    def test_mutation_flags_after_a_redirect_are_still_validated(self):
        # iteration 5: the shell keeps collecting argv after a redirect — ending
        # the segment there let a bad flag escape validation entirely
        v = self._check('python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir d 2>>err.log --wrong x')
        self.assertTrue(any("unknown flags" in s for s in v), v)

    def test_mutation_unclosed_UNQUOTED_substitution_fails_closed(self):
        # round 2: the ORIGINAL fail-open lived on the unquoted branch — no quote
        # before $(, no closing ) — where the pre-fix scanner sliced at EOF and
        # validated a silently truncated argv; the double-quoted fixture below
        # never exercised it
        v = self._check('OUT=$(python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir dx')
        self.assertTrue(any("unparseable" in s for s in v),
                        f"an unclosed UNQUOTED substitution must poison the parse: {v}")

    def test_mutation_unclosed_substitution_fails_closed(self):
        v = self._check('OUT="$(python3 "$CODE_DIR/auditor/scripts/fake-helper.py" '
                        '--data-dir dx')
        self.assertTrue(any("unparseable" in s for s in v),
                        f"an unclosed substitution must poison the parse, not "
                        f"validate a truncated argv: {v}")

    def test_mutation_sourced_library_must_be_sourced(self):
        contracts = {"fake-lib.sh": {"sourced": True}}
        bad = self._check('bash "$CODE_DIR/auditor/scripts/fake-lib.sh"', contracts)
        self.assertTrue(any("without sourcing" in s for s in bad), bad)
        good = self._check('. "$CODE_DIR/auditor/scripts/fake-lib.sh"', contracts)
        self.assertEqual(good, [], good)


class TestSingleDefinitionGuard(unittest.TestCase):
    """N1 (step-9): a shadowing duplicate silently splits edits between a live
    copy and a dead one. This guard lives in its OWN class and checks ITSELF —
    hosting it inside a guarded class let a duplicate of that class disable the
    guard along with everything else it shadowed."""

    def test_the_call_site_machinery_is_defined_exactly_once(self):
        source = (REPO / "tests" / "test_auditor_workflows.py").read_text()
        for name in ("HELPER_OBLIGATIONS", "CALL_CONTRACTS",
                     "EXTRACTED_RUN_ROSTER", "def check_call_sites",
                     "class TestHelperCallSites", "class TestCallSiteArguments",
                     "class TestSingleDefinitionGuard"):
            definitions = re.findall(rf"^{re.escape(name)}[ (=:]", source, re.M)
            self.assertEqual(len(definitions), 1,
                             f"{name!r} is defined more than once — the later copy "
                             f"shadows the earlier and edits split between them")


if __name__ == "__main__":
    unittest.main()


class TestParsedBridge(unittest.TestCase):
    """vibe-165 W1: the checklist IS the bridge's specification — every clause of
    D1 has its fixture here, refusals by name included."""

    def setUp(self):
        if _ruby() is None:
            self.skipTest("ruby unavailable")

    def parse(self, text):
        root, census, err = parsed_workflow(text)
        self.assertIsNone(err, err)
        return root, census

    def test_on_and_true_stay_distinct_keys(self):
        root, _ = self.parse("on: {push: null}\n\"true\": x\njobs: {}\n")
        keys = [_scalar(k) for k, _ in root["c"]]
        self.assertIn("on", keys)
        self.assertIn("true", keys)

    def test_an_escaped_quoted_key_decodes_to_its_key(self):
        root, _ = self.parse('"o\\x6e": {push: null}\n')
        self.assertEqual(_scalar(root["c"][0][0]), "on",
                         "YAML's own semantics: an escaped spelling IS the key")

    def test_flow_and_block_styles_are_visible(self):
        flow, _ = self.parse("jobs: {a: {runs-on: x}}\n")
        block, _ = self.parse("jobs:\n  a:\n    runs-on: x\n")
        self.assertNotEqual(_map_get(flow, "jobs")["style"],
                            _map_get(block, "jobs")["style"])

    def test_a_quoted_run_key_is_the_run_key(self):
        root, _ = self.parse('jobs:\n  a:\n    steps:\n      - "run": echo hi\n')
        step = _map_get(_map_get(_map_get(root, "jobs"), "a"), "steps")["c"][0]
        self.assertEqual(_scalar(step["c"][0][0]), "run")

    def test_a_bare_dash_step_is_a_step(self):
        root, census = self.parse(
            "jobs:\n  a:\n    steps:\n      -\n        name: x\n        id: n\n")
        self.assertEqual(census["steps"], 1)

    def test_a_block_scalar_job_value_is_a_scalar_node(self):
        root, _ = self.parse("jobs:\n  a: |2\n    not a job\n")
        self.assertEqual(_map_get(_map_get(root, "jobs"), "a")["t"], "s")

    def test_forward_and_unknown_aliases_are_violations(self):
        root, _ = self.parse("a: *later\nb: &later 1\n")
        _, violations = resolve_aliases(root)
        self.assertTrue(any("unregistered anchor" in v for v in violations))

    def test_anchor_reuse_resolves(self):
        root, _ = self.parse("a: &x {k: 1}\nb: *x\nc: *x\n")
        resolved, violations = resolve_aliases(root)
        self.assertEqual(violations, [])
        self.assertEqual(_scalar(_map_get(_map_get(resolved, "c"), "k")), "1")

    def test_a_self_cycle_is_refused_by_name(self):
        root, _ = self.parse("a: &x {self: *x}\n")
        _, violations = resolve_aliases(root)
        self.assertTrue(any("cyclic alias" in v for v in violations), violations)

    def test_an_expansion_bomb_is_refused_by_the_bound(self):
        text = "a0: &a0 [x, x, x, x, x, x, x, x, x, x]\n"
        for i in range(1, 5):
            text += (f"a{i}: &a{i} [*a{i-1}, *a{i-1}, *a{i-1}, *a{i-1}, *a{i-1}, "
                     f"*a{i-1}, *a{i-1}, *a{i-1}, *a{i-1}, *a{i-1}]\n")
        root, _ = self.parse(text)
        _, violations = resolve_aliases(root)
        self.assertTrue(any("expansion exceeds" in v for v in violations), violations)

    def test_explicit_tags_are_refused_by_name(self):
        for snippet in ("a: !!timestamp 2026-01-01\n",
                        "a: !!binary aGk=\n",
                        "a: !custom x\n",
                        "a: !custom {k: v}\n",
                        "a: !!str plain\n",
                        "a: !!set {x: null}\n"):
            with self.subTest(snippet=snippet):
                root, _ = self.parse(snippet)
                self.assertTrue(tag_violations(root),
                                f"an explicit tag passed silently: {snippet!r}")

    def test_double_quoted_run_text_arrives_decoded(self):
        root, _ = self.parse('jobs:\n  a:\n    steps:\n'
                             '      - run: "echo \\"hi\\"\\nset -e"\n')
        step = _map_get(_map_get(_map_get(root, "jobs"), "a"), "steps")["c"][0]
        self.assertEqual(_scalar(step["c"][0][1]), 'echo "hi"\nset -e')

    def test_the_ruby_census_is_the_independent_recount(self):
        text = ("jobs:\n  a:\n    steps:\n      - run: echo 1\n      - uses: x\n"
                "  b:\n    steps:\n      - \"run\": echo 2\n")
        root, census = self.parse(text)
        self.assertEqual(census, {"jobs": 2, "steps": 3, "runs": 2})
        # the Python side counts through the resolved tree — two implementations
        resolved, _ = resolve_aliases(root)
        runs = 0
        jobs_node = _map_get(resolved, "jobs")
        for _name, job in jobs_node["c"]:
            steps = _map_get(job, "steps")
            for step in (steps or {"c": []}).get("c", []):
                if isinstance(step, dict) and step.get("t") == "m" \
                        and any(_scalar(k) == "run" for k, _ in step["c"]):
                    runs += 1
        self.assertEqual(runs, census["runs"])


class TestExpressionGrammar(unittest.TestCase):
    """vibe-165 D2/D2″: positive conformance for the documented language and one
    red case per class the retired token walk admitted."""

    POSITIVE = [
        # every documented root
        *[f"{root}.x" for root in sorted(_ALLOWED_ROOTS)],
        "github.event.label.name == 'audit-ready'",
        "github.event.*.name",                       # object filter
        "needs.build-job.outputs.value",             # hyphenated property
        "steps['generate']['outputs']['x']",         # chained indices
        "fromJSON(env.LIST)[0]",
        "-1 == matrix.index", "0xff != env.N", "1e3 < 2.5",
        "'it''s fine' == github.ref",                # escaped single quote
        "!cancelled() && (success() || failure())",  # precedence + zero-arity
        "contains(github.ref, 'release')",
        "join(matrix.os)", "join(matrix.os, ', ')",
        "format('{0}-{1}', github.ref, github.sha)",
        "hashFiles('**/lock', '**/sum')",
        "toJSON(github)", "case(env.A == '1', 'x', 'default')",
        "case(env.A == '1', 'x', env.A == '2', 'y', 'default')",
    ]

    NEGATIVE = [
        "((github.ref)",                 # unbalanced parens
        "github..ref",                   # empty path segment
        "env[]",                         # empty index
        "env[else",                      # malformed index
        "unknownroot.x",                 # unknown context root
        "mystery(1)",                    # unknown function
        "env.A && && env.B",             # operator run
        '"double" == env.A',             # double-quoted literal
        "env.A) trailing",               # trailing garbage
        "contains('a', 'b', 'c')",       # arity: contains is exactly 2
        "join(env.A, ',', 'x')",         # arity: join is 1..2
        "toJSON(env.A, env.B)",          # arity: toJSON is exactly 1
        "fromJSON(env.A, env.B)",        # arity: fromJSON is exactly 1
        "hashFiles()",                   # arity: hashFiles is >= 1
        "case(env.A == '1', 'x')",       # arity: case is odd >= 3
        "case(env.A, 'x', env.B, 'y')",  # arity: case even count
        "contains(, 'x')",               # leading comma
        "contains('x',)",                # trailing comma
        "contains('x',, 'y')",           # doubled comma
        "contains('x' 'y')",             # missing separator
        "contains('x', 'y'",             # unclosed call
    ]

    def test_the_documented_language_is_accepted(self):
        for expr in self.POSITIVE:
            with self.subTest(expr=expr):
                self.assertTrue(_expr_ok(expr), f"over-rejection: {expr!r}")

    def test_each_admitted_bad_class_is_now_rejected(self):
        for expr in self.NEGATIVE:
            with self.subTest(expr=expr):
                self.assertFalse(_expr_ok(expr), f"still admitted: {expr!r}")

    def test_the_dead_grammar_symbol_is_gone(self):
        source = (REPO / "tests" / "test_auditor_workflows.py").read_text()
        self.assertEqual(len(re.findall(r"^EXPR_GRAMMAR", source, re.M)), 0,
                         "the dead EXPR_GRAMMAR constant came back")

    def test_every_expression_in_all_26_workflows_still_passes(self):
        # the no-over-rejection rail, at expression granularity
        bad = []
        for path in sorted((REPO / "auditor" / "workflows").glob("*.yml")) + \
                sorted((REPO / ".github" / "workflows").glob("*.yml")):
            for m in re.finditer(r"\$\{\{(.*?)\}\}", path.read_text(), re.S):
                if not _expr_ok(m.group(1).strip()):
                    bad.append(f"{path.name}: {m.group(1).strip()[:80]}")
        self.assertEqual(bad, [], f"the new grammar over-rejects: {bad}")
