# SPDX-License-Identifier: ISC
"""E3.8 (vibe-33) acceptance: /vibe-suite:spec-sync + spec-researcher.

Rung 0/1 pins contracts, the freshness normalization, and the fixture oracle. The live
research step is the agent's judgment lane: CI performs no network fetch. What runs
mechanically here is the one-to-one comparison of a RECORDED manual dry run against the
hand-authored expectation — the recording's provenance header states when and how it
was produced.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMAND = REPO_ROOT / "commands" / "spec-sync.md"
AGENT = REPO_ROOT / "agents" / "spec-researcher.md"
SPEC = REPO_ROOT / ".vibe-test" / "spec-researcher.spec.md"
FIX = REPO_ROOT / "tests" / "fixtures" / "spec-sync"
EXPECTED = FIX / "expected-report.md"
RECORDED = FIX / "recorded-dry-run.md"
OVERLAYS = {
    "claude": REPO_ROOT / "skills" / "conventions-claude" / "SKILL.md",
    "codex": REPO_ROOT / "skills" / "conventions-codex" / "SKILL.md",
    "antigravity": REPO_ROOT / "skills" / "conventions-antigravity" / "SKILL.md",
}

#: D6's exact canonical post-state lines (verbatim, including the ≥ character in the
#: preserved Claude qualification).
CANONICAL = {
    "claude": "**Spec freshness:** verified 2026-06-07 against the official Claude Code "
              "docs map dated 2026-06-05 (code.claude.com/docs/en/)",
    "codex": "**Spec freshness:** verified 2026-06-07 against Codex CLI 0.137.0, "
             "released 2026-06-04 (developers.openai.com/codex)",
    "antigravity": "**Spec freshness:** UNVERIFIED — research written 2026-05-25, six "
                   "days after the Antigravity 2.0 announcement of 2026-05-19; the "
                   "verification pass described in §10 has not landed "
                   "(developers.googleblog.com)",
}
PRESERVED = {
    "claude": "That map tracks Claude Code ≥ v2.1.16x; where earlier notes conflicted "
              "with this refresh, the newer facts below are canonical.",
    "codex": "Pre-releases existed up to 0.138.0-alpha.6 at refresh time.",
    "antigravity": "the spec has not settled since Antigravity 2.0, so most "
                   "tool-specific checks stay advisory",
}
SUPERSEDED = ["Freshness: refreshed 2026-06-07", "Refresh state: verified 2026-06-07"]

TAGS = ["RESOLVED", "REMOVE", "FIX", "ADD", "CONFIRM"]


def squash(text):
    return re.sub(r"\s+", " ", text)


def report_rows(text):
    """Parse a gap-report table into (seed, section, tag, confidence) tuples."""
    rows = []
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| Seed") or set(
                line.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[0].isdigit():
            rows.append(tuple(cells[:4]))
    return rows


class Deliverables(unittest.TestCase):
    def test_artifacts_and_registration(self):
        self.assertTrue(COMMAND.is_file())
        self.assertTrue(AGENT.is_file())
        manifest = json.loads(
            (REPO_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./commands/spec-sync.md", manifest["commands"])
        self.assertIn("./agents/spec-researcher.md", manifest["agents"])
        # at least the E3.8 state; later items add more (membership above pins ours)
        self.assertGreaterEqual(len(manifest["commands"]), 18)
        self.assertGreaterEqual(len(manifest["agents"]), 7)

    def test_agent_frontmatter_matches_its_shipped_spec(self):
        body = AGENT.read_text(encoding="utf-8")
        self.assertRegex(body, r"(?m)^description: Use when")
        self.assertRegex(body, r"(?m)^model: (haiku|sonnet|opus)$")
        # exact allowlist — adding Write (or any tool) is a contract change
        self.assertRegex(body, r"(?m)^tools: WebFetch, WebSearch, Read$")
        spec = SPEC.read_text(encoding="utf-8")
        self.assertIn("FIX/REMOVE/ADD/CONFIRM/RESOLVED", spec)
        flat = squash(body)
        self.assertIn("first-party", flat.lower())
        self.assertRegex(flat, r"(?i)one dispatch per overlay|per-overlay dispatch")
        # the output-table contract, field by field
        self.assertIn("| Seed/claim | Section | Tag | Confidence or reason | "
                      "Source label | URL |", flat)
        for tag in TAGS:
            self.assertIn(tag, body, f"agent must state tag {tag}")
        for reason in ("source-silent", "source-conflict"):
            self.assertIn(reason, body)
        # D4/D5 evidence rules, each bound: per-row label AND URL; a quoted statement
        # with its URL for every graded row; deficient evidence routed to UNCLASSIFIED
        self.assertIn("and the full page URL", flat)
        self.assertIn("Every graded row (`high` or `medium`) must quote the source "
                      "statement it relied on together with that URL", flat)
        self.assertIn("a row without a quotable statement and URL is not graded "
                      "evidence and belongs in `UNCLASSIFIED`", flat)

    def test_no_deprecated_vocabulary(self):
        # R51 is enforced on commands/** and agents/** (E3.7).
        for path in (COMMAND, AGENT):
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)\bimplement\b")


class CommandContract(unittest.TestCase):
    def setUp(self):
        self.body = COMMAND.read_text(encoding="utf-8")
        self.flat = squash(self.body)

    def test_targets_field_complete(self):
        # D1: three tokens, `all` as default, floor excluded — each asserted by content
        for token in ("claude", "codex", "antigravity", "all"):
            self.assertIn(f"`{token}`", self.body, f"target token missing: {token}")
        self.assertIn("`all` (the default)", self.flat)
        self.assertIn("`skills/conventions/` floor is never a target", self.flat)

    def test_modes_and_change_predicate(self):
        self.assertIn("--dry-run", self.body)
        self.assertIn("--apply", self.body)
        self.assertIn("remains writable after the confidence threshold", self.flat)
        self.assertRegex(self.flat, r"(?i)no-change branch")
        self.assertRegex(self.flat, r"(?i)never commits")
        # D2: RESOLVED and a retiring CONFIRM are both actionable — deleting either
        # from the predicate fails here
        self.assertIn("FIX, REMOVE, ADD, or RESOLVED", self.flat)
        self.assertIn("CONFIRM that retires a correction note", self.flat)

    #: D3's five rows, EXACTLY and IN ORDER. A dict collapsed duplicates and hid
    #: reordering; an ordered list of full rows admits neither.
    D3_TABLE = [
        ["1", "`RESOLVED`", "carries an explicit hedge about X", "now settles X",
         "retire the hedge, state the settled fact"],
        ["2", "`REMOVE`", "states X", "X withdrawn/absent, no replacement",
         "delete the claim"],
        ["3", "`FIX`", "states X", "states not-X, with a replacement",
         "correct the claim in place"],
        ["4", "`ADD`", "silent on X, X in scope", "states X", "add the claim"],
        ["5", "`CONFIRM`", "states X definitely (no hedge)", "states X",
         "none, except note retirement (below)"],
    ]

    def test_tag_precedence_table_is_exact_and_ordered(self):
        rows = []
        for line in self.body.splitlines():
            if line.startswith("| ") and "`" in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells and cells[0].isdigit():
                    rows.append(cells)
        self.assertEqual(rows, self.D3_TABLE,
                         "the precedence table must match the frozen semantics exactly, "
                         "in order, with no extra or duplicate rows")

    def test_disjointness_rules_stated(self):
        self.assertIn("requires a replacement fact", self.flat)
        self.assertRegex(self.flat, r"(?i)CONFIRM requires .*un-hedged|no hedge")

    def test_confidence_and_threshold(self):
        self.assertIn("UNCLASSIFIED", self.body)
        self.assertIn("source-silent", self.body)
        self.assertIn("source-conflict", self.body)
        self.assertIn("--min-confidence", self.body)
        self.assertRegex(self.flat, r"(?i)default(s)? (to )?`?medium`?")
        self.assertIn("(withheld: below --min-confidence)", self.flat)
        # D4: both grade DEFINITIONS and the orthogonality statement
        self.assertIn("`high` is an explicit first-party statement", self.flat)
        self.assertIn("`medium` is first-party but indirect", self.flat)
        self.assertIn("grade the evidence, never the tag", self.flat)
        self.assertIn("Insufficient evidence is not a grade", self.flat)

    def test_evidence_contract_command_side(self):
        # the note carries BOTH label and URL, and the freshness line's label-only
        # convention is stated as a DISTINCTION, not a conflation
        self.assertIn("`<source label>` is the overlay-style bare domain path and "
                      "`<URL>` is the full first-party page URL", self.flat)
        self.assertIn("the note records BOTH", self.flat)
        self.assertIn("follows the overlays' existing label-only convention", self.flat)
        self.assertIn("not full URLs", self.flat)

    def test_correction_notes(self):
        self.assertIn(
            "<!-- spec-sync <run-date>: <tag> — <source label>, <URL> "
            "(confidence: high|medium) -->", self.body)
        self.assertIn("replaces its note rather than adding one", self.flat)
        self.assertIn("one note per claim, never accumulating", self.flat)
        self.assertIn("## Correction notes", self.body)
        self.assertRegex(self.flat, r"(?i)not valid YAML|conforming parser")
        # retirement is reachable: a note-retiring CONFIRM is writable
        self.assertRegex(self.flat,
                         r"(?i)CONFIRM .*retires .*(is writable|counts toward)")

    def test_overlay_root_semantics(self):
        self.assertIn("--overlay-root", self.body)
        self.assertRegex(self.flat, r"(?i)replaces the (selected )?overlay set")
        self.assertRegex(self.flat, r"(?i)requires an explicit target|refuses")

    #: The frozen 23-token sweep set — the command must SHIP it, not reference it.
    SWEEP_TOKENS = [
        ".claude/", ".codex/", ".agent/", ".gemini/", "AGENTS.md", "GEMINI.md",
        "CLAUDE.md", "hooks.json", "settings.json", "config.toml", ".mcp.json",
        "mcpServers", "marketplace.json", "plugin.json", "CLAUDE_PLUGIN_ROOT",
        "PreToolUse", "PostToolUse", "SessionStart", "SessionEnd", "SubagentStop",
        "PreCompact", "UserPromptSubmit", "gemini-extension",
    ]

    def _token_block(self):
        """The fenced token block itself — not the whole document, so a token that
        also appears elsewhere (CLAUDE_PLUGIN_ROOT is in the verify command) cannot
        satisfy the sweep definition by accident."""
        m = re.search(r"\*Tokens \((\d+) alternatives[^)]*\):\*\s*\n```\n(.*?)```",
                      self.body, re.S)
        self.assertIsNotNone(m, "the sweep's token block is missing")
        declared = int(m.group(1))
        tokens = m.group(2).split()
        return declared, tokens

    def test_sweep_token_block_is_exact(self):
        declared, tokens = self._token_block()
        # the declared count, the actual count, and the frozen set must all agree —
        # a removed token, an added token, or a stale count each fails
        self.assertEqual(declared, 23, "declared alternative count drifted")
        self.assertEqual(len(tokens), 23, f"token block holds {len(tokens)} tokens")
        self.assertEqual(sorted(tokens), sorted(self.SWEEP_TOKENS),
                         "token block differs from the frozen sweep set")

    def test_sweep_scope_is_exact(self):
        # the scope sentence, verbatim: EXCLUDING (not INCLUDING) those three trees
        self.assertIn(
            "every file in `git ls-files` EXCLUDING the `tests/`, `docs/`, and "
            "`.github/` trees", self.flat)

    def test_propagation_rules(self):
        for kind in ("SOURCE", "DOCUMENTARY", "ENCODED", "OPERATIONAL"):
            self.assertIn(f"**{kind}**", self.body, f"class missing: {kind}")
        self.assertIn("code-change-required", self.body)
        self.assertRegex(self.flat, r"(?i)never edited\*{0,2} by this command")
        # both citation forms (D7.4)
        self.assertIn("conventions-<tool> §N", self.body)
        self.assertIn("Markdown link to the overlay", self.flat)

    def test_verify_step_fully_pinned(self):
        self.assertIn(
            'python3 "${CLAUDE_PLUGIN_ROOT}/bin/vibe-check" "${CLAUDE_PLUGIN_ROOT}"',
            self.body)
        self.assertRegex(self.flat, r"(?i)exit status")


#: Every binding rule from the frozen plan, each pinned to an EXACT phrase in the
#: artifact that owns it. Adding a rule to the plan means adding a row here; deleting a
#: rule from an artifact fails the corresponding case. Phrases are matched against
#: whitespace-squashed text so line wrapping cannot mask a deletion.
REQUIRED_CLAUSES = [
    # (rule, file-key, exact phrase)
    ("D1 default", "command", "`all` (the default)"),
    ("D1 all selects three", "command", "selects those three"),
    ("D1 floor excluded", "command", "`skills/conventions/` floor is never a target"),
    ("D2 dry-run default", "command", "`--dry-run` (the default)"),
    ("D2 actionable set", "command", "FIX, REMOVE, ADD, or RESOLVED"),
    ("D2 retiring CONFIRM", "command", "CONFIRM that retires a correction note"),
    ("D4 high grade", "command", "`high` is an explicit first-party statement"),
    ("D4 medium grade", "command", "`medium` is first-party but indirect"),
    ("D4 orthogonality", "command", "grade the evidence, never the tag"),
    ("D4 not-a-grade", "command", "Insufficient evidence is not a grade"),
    ("D4 threshold default", "command", "**default `medium`**"),
    ("D5 every correction", "command", "Every applied correction carries a note"),
    ("D5 run-date semantics", "command",
     "is the ISO date of the run that writes it"),
    ("D5 body placement", "command",
     "the line immediately following the corrected or added claim"),
    ("D5 frontmatter placement", "command",
     "the note never goes inside the YAML block"),
    ("D5 retirement condition", "command",
     "`CONFIRM` at `high` confidence against a source dated at or after the note's own"),
    ("D5 one note per claim", "command", "one note per claim, never accumulating"),
    ("D6 label-only distinction", "command", "not full URLs"),
    ("D7 case sensitivity", "command", "case-sensitively"),
    ("D7 scope", "command",
     "every file in `git ls-files` EXCLUDING the `tests/`, `docs/`, and `.github/` trees"),
    ("D7 required targets", "command", "with the citing line quoted"),
    ("D7 never edited", "command", "**never edited** by this command"),
    ("D8 verify target", "command",
     'python3 "${CLAUDE_PLUGIN_ROOT}/bin/vibe-check" "${CLAUDE_PLUGIN_ROOT}"'),
    ("D9 first-party only", "agent", "**First-party only.**"),
    ("D9 page date", "agent", "plus the page's own date when it carries one"),
    ("D9 graded quote+URL", "agent",
     "Every graded row (`high` or `medium`) must quote the source statement it relied "
     "on together with that URL"),
    ("D9 unclassified routing", "agent",
     "a row without a quotable statement and URL is not graded evidence and belongs in "
     "`UNCLASSIFIED`"),
    ("D9 research not apply", "agent",
     "You research and report; applying corrections belongs to"),
    # --- rows added after the round-3 probe pass named them (each was deletable)
    ("D1 token->overlay mapping", "command",
     "`claude`, `codex`, and `antigravity` each select one overlay skill"),
    ("D3 RESOLVED action", "command", "retire the hedge, state the settled fact"),
    ("D5 REMOVE note placement", "command",
     "for REMOVE in place of the deleted claim"),
    ("D7 documentary changed-fact only", "command",
     "updated ONLY when the fact it restates is one this run changed"),
    ("D7 citation changed-section only", "command",
     "reported as REQUIRED targets ONLY when the cited section is one this run changed"),
    ("D2 withheld rows are not changes", "command",
     "Rows withheld by the threshold do not create changes"),
    ("D2 no-change reason is per overlay", "command",
     "with the reason stated per overlay"),
    ("D6 freshness rewritten atomically", "command",
     "rewrites that line's state, date, and source label together as one edit"),
    ("D7 every row states its basis", "command",
     "Every classified row states its basis so a reader can audit it"),
    ("D8 non-zero status surfaced", "command",
     "a non-zero status is surfaced, never swallowed"),
    ("D3 first-matching precedence", "command",
     "classified by the FIRST matching rule"),
    ("D4 withheld rows still reported", "command",
     "is reported as `(withheld: below --min-confidence)`"),
    ("D4 medium writes by default", "command",
     "both grades write unless you raise the bar"),
    ("D7 every occurrence classified", "command", "Classify every occurrence"),
    ("D7 owning tests named", "command", "with their owning tests named"),
    ("D7 anchor coverage still printed", "command",
     "The report still prints the anchor's coverage"),
    ("D7 coverage is not the bound", "command",
     "coverage is no longer the propagation bound; the sweep is"),
    ("D8 skip reason stated", "command", "Skipped, with the reason stated"),
    ("D9 non-first-party excluded before tagging", "agent",
     "are NOT evidence and are excluded before tagging"),
    ("D5 note names the frontmatter key", "command",
     "`## Correction notes` body section naming the frontmatter key"),
    ("D9 report every claim examined", "agent",
     "Report every claim you examined, including CONFIRM and UNCLASSIFIED rows"),
    ("D9 output row order", "agent", "ordered by tag precedence then section"),
    ("D9 quote beneath actionable rows", "agent",
     "Quote the source statement you relied on beneath any FIX, REMOVE, or RESOLVED row"),
]

#: T0 requires the worksheet to carry hand-derived expectations, not just the fixture's
#: seed table. Each row names a requirement the frozen plan states verbatim; the third
#: and fourth were absent from the shipped worksheet until round 6.
REQUIRED_WORKSHEET = [
    ("D3 worked example per tag", "## D3 tag precedence"),
    ("D4 UNCLASSIFIED reason examples", "## D4 confidence and UNCLASSIFIED"),
    ("D5 note format", "## D5 correction notes"),
    ("D5 replacement example", "**Replacement example**"),
    ("D6 pre/post for all four occurrences",
     "## D6 freshness normalization — pre/post for all four occurrences"),
    ("D7 anchor measurement",
     "## D7 anchor measurement and the four-kind classification"),
]

#: Frontmatter values the frozen plan fixes exactly (a tier alias, never a pinned id).
REQUIRED_FRONTMATTER = [("agent", "model", "sonnet")]


class RequiredClauses(unittest.TestCase):
    """One case per binding rule — the table above is the contract's inventory."""

    def test_every_rule_is_present(self):
        sources = {"command": squash(COMMAND.read_text(encoding="utf-8")),
                   "agent": squash(AGENT.read_text(encoding="utf-8"))}
        for rule, key, phrase in REQUIRED_CLAUSES:
            with self.subTest(rule=rule):
                self.assertIn(phrase, sources[key],
                              f"{rule}: required clause missing from {key}")

    def test_required_frontmatter_values(self):
        # D9 fixes the agent at sonnet-class; haiku or opus is a contract change
        sources = {"agent": AGENT.read_text(encoding="utf-8"),
                   "command": COMMAND.read_text(encoding="utf-8")}
        for key, field, value in REQUIRED_FRONTMATTER:
            with self.subTest(field=field):
                self.assertRegex(sources[key], rf"(?m)^{field}: {value}$",
                                 f"{key} {field} must be {value}")

    def test_worksheet_note_schema_matches_the_command(self):
        # the worksheet must not document a superseded schema (step-9 finding 2)
        worksheet = (FIX / "README.md").read_text(encoding="utf-8")
        self.assertIn("<source label>, <URL> (confidence: high|medium)", worksheet)
        self.assertNotIn("<tag> — <source label> (confidence", worksheet)


#: The COMPLETE word set of each artifact, frozen. Every other vocabulary check pins a
#: token SHAPE — all-caps, hyphenated, inside code spans — and a shape is a syntax, so
#: `Archival`, `evidence missing`, and a bare `critical` in prose slip past all of them.
#: A lexicon has no shape: any word not already in the contract fails, in any case,
#: spacing, or emphasis.
#:
#: This lives in test code, NOT in a fixture, and that is the point. The golden closes
#: the set at byte level but a deliberate re-bless updates it; the lexicon must be
#: updated here, in the same diff a reviewer reads, so a vocabulary change to a frozen
#: contract is never invisible. It is a drift detector, not a semantic check — the
#: equality tables above are what bind meaning.
LEXICON = {
    "command": {
        'a', 'able', 'about', 'absence', 'absent', 'accumulating', 'action', 'add',
        'added', 'adding', 'after', 'against', 'agent', "agent's", 'agents', 'all',
        'all-medium', 'alone', 'alternatives', 'an', "anchor's", 'and', 'antigravity',
        'any', 'application', 'applied', 'applies', 'apply', 'are', 'argument-hint',
        'arguments', 'artifacts', 'as', 'at', 'audit', 'bar', 'bare', 'basis', 'be',
        'because', 'becomes', 'been', 'below', 'bin', 'block', 'body', 'both', 'bound',
        'boundaries', 'branch', 'bridge', 'bump', 'bumps', 'but', 'by', 'caller', 'can',
        'candidate', 'canonical', 'carries', 'carry', 'carrying', 'case-sensitively',
        'change', 'changed', 'changes', 'check', 'citation', 'cited', 'citing', 'claim',
        'classified', 'classify', 'claude', 'code', 'code-change-required', 'codex',
        'com', 'command', "command's", 'comment', 'commit', 'commits', 'committed',
        'confidence', 'config', 'confirm', 'conforming', 'consumers', 'convention',
        'conventions', 'conventions-', 'correct', 'corrected', 'correcting',
        'correction', 'corrections', 'count', 'counts', 'coverage', 'create', 'data',
        'date', 'dated', 'declares', 'default', 'defaulting', 'defined', 'definitely',
        'delete', 'deleted', 'dependency', 'description', 'developers', 'disagree',
        'disjoint', 'dispatch', 'dispatches', 'do', 'docs', 'doctor', 'documentary',
        'documentation', 'documented', 'does', 'domain', 'dry-run', 'each', 'edit',
        'edited', 'either', 'encoded', 'engine', 'entry', 'events', 'every', 'evidence',
        'exactly', 'except', 'excluding', 'existing', 'exit', 'explicit', 'explicitly',
        'fact', 'family', 'fault', 'fetched', 'file', 'files', 'first', 'first-party',
        'fix', 'flags', 'floor', 'follow', 'following', 'follows', 'for', 'freshness',
        'frontmatter', 'full', 'function', 'gap', 'gemini', 'gemini-extension', 'git',
        'github', 'goes', 'grade', 'grades', 'h', 'has', 'hedge', 'hedged', 'here',
        'high', 'hook', 'hook-config', 'hooks', 'how', 'html', 'immediately', 'in',
        'independently', 'indirect', 'inline', 'input', 'inside', 'instructions',
        'insufficient', 'into', 'invocation', 'is', 'iso', 'it', 'its', 'json', 'keeps',
        'key', 'known', 'label', 'label-only', 'labels', 'later', 'least', 'left',
        'line', "line's", 'link', 'longer', 'ls-files', 'machine-readable', 'many',
        'markdown', 'marketplace', 'matched', 'matching', 'mcp', 'mcpservers', 'md',
        'medium', 'meets', 'migration', 'min-confidence', 'mode', 'modes', 'much',
        'must', 'n', 'named', 'naming', 'never', 'no', 'no-change', 'no-op', 'non-zero',
        'none', 'not', 'not-x', 'note', "note's", 'notes', 'nothing', 'now', 'number',
        'observation', 'occurrence', 'occurrences', 'occurs', 'of', 'on', 'one', 'only',
        'openai', 'operational', 'optional', 'or', 'order', 'other', 'overlay',
        'overlay-root', 'overlay-style', "overlays'", 'own', 'owning', 'page', 'pages',
        'parser', 'path', 'paths', 'per', 'per-row', 'per-tool', 'place', 'placement',
        'plugin', 'plus', 'posttooluse', 'precedence', 'precompact', 'predicate',
        'pretooluse', 'printing', 'prints', 'propagate', 'propagates', 'propagation',
        'prose', 'provenance', 'py', 'python', 'quoted', 'raise', 'rather',
        're-touches', 're-verified', 'reader', 'reading', 'reason', 'records',
        'reference', 'refuses', 'regardless', 'remain', 'remains', 'remove', 'renders',
        'replacement', 'replaces', 'report', "report's", 'reported', 'reports',
        'reproduce', 'required', 'requires', 'research', 'researcher', 'researches',
        'resolved', 'restates', 'restating', 'retire', 'retirement', 'retires',
        'returns', 'review', 'rewrites', 'root', 'rooted', 'row', 'rows', 'rule',
        'rules', 'run', 'run-date', 's', 'same', 'scanned', 'schema', 'scope', 'score',
        'scripts', 'section', 'select', 'selected', 'selects', 'sessionend',
        'sessionstart', 'set', 'settings', 'settled', 'settles', 'silent', 'single',
        'single-overlay', 'skill', 'skills', 'skipped', 'so', 'source',
        'source-conflict', 'source-silent', 'sources', 'spec', 'spec-researcher',
        'spec-sync', 'staged', 'state', 'stated', 'statement', 'states', 'status',
        'step', 'step-', 'still', 'stops', 'subagentstop', 'such', 'summarises',
        'surfaced', 'swallowed', 'sweep', 'sync', 'table', 'tag', 'tagged', 'tags',
        'takes', 'target', 'targets', 'tests', 'than', 'that', 'the', 'their', 'them',
        'themselves', 'these', 'this', 'those', 'three', 'threshold', 'to', 'together',
        'token', 'tokens', 'toml', 'tool', "tool's", 'tool-agnostic', 'tool-convention',
        'toward', 'transcription', 'tree', 'trees', 'two', 'un-hedged', 'unclassified',
        'under', 'unless', 'untouched', 'untrusted', 'unverified', 'update', 'updated',
        'url', 'urls', 'userpromptsubmit', 'uses', 'valid', 'value', 'verified',
        'verifies', 'verify', 'vibe-check', 'vibe-suite', 'visible', 'when', 'where',
        'whereas', 'which', 'whole', 'whose', 'with', 'withdrawal', 'withdrawn',
        'withheld', 'without', 'working', 'would', 'writable', 'write', 'writes',
        'writing', 'written', 'x', 'yaml', 'you', 'yourself', 'zero',
    },
    "agent": {
        'a', 'about', 'absent', 'actionable', 'add', 'adjacent', 'advisory', 'against',
        'aggregators', 'an', 'and', 'answers', 'any', 'applying', 'are', 'as', 'assign',
        'at', 'bare', 'because', 'before', 'belongs', 'beneath', 'blog', 'both', 'but',
        'by', 'carries', 'caveat', 'changelog', 'changelogs', 'citations', 'cite',
        'claim', 'classifiable', 'codex', 'com', 'command', 'confidence', 'confirm',
        'corrections', 'data', 'date', 'decides', 'declared', 'definitely',
        'definitively', 'description', 'developers', 'disagree', 'disjoint', 'dispatch',
        'documentation', 'documented', 'documents', 'domain', 'each', 'emit', 'every',
        'evidence', 'examined', 'example', 'excluded', 'explicit', 'fact', 'fetched',
        'first', 'first-party', 'fix', 'for', 'form', 'format', 'from', 'full', 'gap',
        'grade', 'graded', 'grades', 'hedge', 'hedged', 'high', 'hooks', 'in',
        'including', 'indirect', 'inference', 'input', 'inside', 'instructions',
        'insufficient', 'is', 'it', 'its', 'label', 'line', 'low', 'matching', 'md',
        'medium', 'model', 'must', 'name', 'never', 'no', 'not', 'not-x', 'notes',
        'now', 'observation', 'on', 'one', 'only', 'openai', 'or', 'order', 'ordered',
        'output', 'overflow', 'overlay', "overlay's", 'overlays', 'own', 'page',
        "page's", 'pages', 'path', 'per', 'per-row', 'plus', 'precedence', 'produces',
        'quotable', 'quote', 'quoted', 'read', 'reason', 'recollection', 'release',
        'relied', 'remove', 'replacement', 'report', 'repository', 'requires',
        'research', 'researching', 'resolved', 'return', 'row', "row's", 'rows', 'rule',
        'rules', 'scope', 'section', 'seed', 'sends', 'settled', 'settles', 'silent',
        'skill', 'skills', 'sonnet', 'source', 'source-conflict', 'source-silent',
        'sources', 'spec-researcher', 'spec-sync', 'stabilizes', 'stack', 'state',
        'statement', 'states', 'stops', 'such', 'table', 'tag', 'tagged', 'tagging',
        'text', 'that', 'the', 'then', 'to', 'together', 'tool-convention', 'tools',
        'tutorials', 'two', 'un-hedged', 'unclassified', 'unsettled', 'until',
        'untrusted', 'url', 'use', 'vendor', "vendor's", 'vibe-core', 'vibe-suite',
        'webfetch', 'websearch', 'what', 'when', 'with', 'withdrawal', 'withdrawn',
        'without', 'write', 'x', 'you',
    },
}


class FrozenLexicon(unittest.TestCase):
    """The last vocabulary hole: a word in a shape no other check scans for."""

    def test_no_word_enters_the_contract_unnoticed(self):
        for key, path in (("command", COMMAND), ("agent", AGENT)):
            with self.subTest(artifact=key):
                words = {w.lower() for w in
                         re.findall(r"[A-Za-z][A-Za-z'-]*",
                                    path.read_text(encoding="utf-8"))}
                added = words - LEXICON[key]
                removed = LEXICON[key] - words
                self.assertEqual(
                    words, LEXICON[key],
                    f"{key}: vocabulary changed — added {sorted(added)}, "
                    f"removed {sorted(removed)}. If intended, update LEXICON in the "
                    "same commit so the change is visible in review.")

CONTRACT = FIX / "contract"


def list_terms(region):
    """Lead term of every list item, whatever the marker or emphasis.

    `- X`, `* X`, `1. X`, `- **X**`, and ``- `X` `` all yield X, so a vocabulary added
    as a numbered or bolded item is as visible as one added in the frozen style.
    """
    terms = []
    for line in region.splitlines():
        item = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.*)$", line)
        if item:
            lead = re.match(r"^[`*_]*([A-Za-z][A-Za-z0-9_-]*)", item.group(1))
            if lead:
                terms.append(lead.group(1))
    return terms


def table_lead_cells(region):
    """Lead term of each table row's first non-numeric cell — a vocabulary moved into
    table form is still that vocabulary."""
    terms = []
    for line in region.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        for cell in cells:
            if cell and not cell.isdigit() and not set(cell) <= set("-: "):
                lead = re.match(r"^[`*_]*([A-Za-z][A-Za-z0-9_-]*)", cell)
                if lead:
                    terms.append(lead.group(1))
                break
    return terms


class WorksheetCompleteness(unittest.TestCase):
    """T0's worksheet is a deliverable, and it was the third place a frozen requirement
    went missing without any test noticing (after D7.3 and D7.4). Headings alone are not
    evidence, so each check below asserts the SUBSTANCE the plan asked for."""

    def setUp(self):
        self.text = (FIX / "README.md").read_text(encoding="utf-8")

    def test_required_sections(self):
        for rule, anchor in REQUIRED_WORKSHEET:
            with self.subTest(rule=rule):
                self.assertIn(anchor, self.text, f"worksheet is missing: {rule}")

    def test_d6_covers_four_occurrences_with_pre_and_post(self):
        section = self.text[self.text.index("## D6 freshness"):]
        section = section[:section.index("## D7")]
        rows = [ln for ln in section.splitlines()
                if ln.startswith("| ") and re.match(r"\| \d+ \|", ln)]
        self.assertEqual(len(rows), 4,
                         "D6 requires pre/post for all FOUR freshness occurrences")
        for overlay in ("claude", "codex", "antigravity"):
            self.assertIn(overlay, section, f"D6 omits the {overlay} overlay")
        # two of the four are `description:` clauses, not body lines — the split that
        # makes the count four rather than three
        self.assertEqual(sum("`description:`" in r for r in rows), 2,
                         "two of the four occurrences are description clauses")

    def test_d7_states_the_anchor_measurement_and_every_class(self):
        section = self.text[self.text.index("## D7 anchor measurement"):]
        for path in ("bin/vibe-check", "skills/scoring/SKILL.md",
                     "skills/conventions-antigravity/SKILL.md"):
            self.assertIn(path, section, f"anchor measurement omits {path}")
        for kind in ("SOURCE", "DOCUMENTARY", "ENCODED", "OPERATIONAL"):
            self.assertIn(f"| {kind} |", section,
                          f"the four-kind classification omits an example for {kind}")
        self.assertIn("both citation forms", section.replace("\n", " "),
                      "the anchor must state that both citation forms are matched")


class FrozenContractText(unittest.TestCase):
    """The set-closure mechanism, and the only one that does not depend on a grammar.

    Every check below this one extracts with a PATTERN, and a pattern encodes a syntax:
    reading targets out of `argument-hint` cannot see a target named only in the body,
    a backtick-anchored flag scan cannot see an unbackticked `--audit`, and a
    ``- **CLASS** —`` scan cannot see ``- **CLASS**:``. Each such hole is closed by
    widening one pattern, and the next unanticipated syntax opens another. So the
    artifacts are ALSO pinned whole: any addition, anywhere, in any syntax, changes the
    text and fails here.

    This does not make the pattern checks redundant, and the division matters. The
    golden closes the SET (nothing may be added); REQUIRED_CLAUSES and the equality
    tables bind the CONTENT to the frozen plan (the golden cannot be re-blessed into
    something that no longer states D1–D9). Updating a golden is therefore a deliberate
    act that must still satisfy every semantic check.
    """

    GOLDENS = {"command": (COMMAND, CONTRACT / "commands-spec-sync.md.golden"),
               "agent": (AGENT, CONTRACT / "agents-spec-researcher.md.golden")}

    def test_artifacts_match_their_frozen_text(self):
        for key, (shipped, golden) in self.GOLDENS.items():
            with self.subTest(artifact=key):
                self.assertTrue(golden.is_file(), f"missing golden for {key}")
                self.assertEqual(
                    shipped.read_text(encoding="utf-8"),
                    golden.read_text(encoding="utf-8"),
                    f"{key} differs from its frozen contract text. If the change is "
                    "intended, re-verify it against the frozen plan and update "
                    f"{golden.relative_to(REPO_ROOT)} in the same commit.")


class ClosedSets(unittest.TestCase):
    """Every closed set is EXTRACTED with a general pattern and compared by equality
    against the frozen expectation, in BOTH artifacts. A pattern that matches only the
    expected values cannot see an addition — `--min-confidence (high|medium)` is blind
    to `critical` — so every extraction below is deliberately permissive and the
    equality does the work.
    """

    D3_TAGS = ["RESOLVED", "REMOVE", "FIX", "ADD", "CONFIRM"]
    #: The agent restates D3 in its own words; its rows are pinned exactly too.
    AGENT_TABLE = [
        ["1", "`RESOLVED`",
         'carries an explicit hedge about X (caveat / "advisory" / "unsettled" / '
         '"until … stabilizes")', "now settles X definitively"],
        ["2", "`REMOVE`", "states X",
         "documents X as withdrawn or absent, with NO replacement fact"],
        ["3", "`FIX`", "states X", "states not-X, WITH a replacement fact"],
        ["4", "`ADD`", "silent on X, and X is inside the overlay's declared scope",
         "states X"],
        ["5", "`CONFIRM`", "states X definitely, with no hedge", "states X"],
    ]

    def setUp(self):
        self.command = COMMAND.read_text(encoding="utf-8")
        self.agent = AGENT.read_text(encoding="utf-8")
        self.both = {"command": self.command, "agent": self.agent}

    @staticmethod
    def _rows(text):
        rows = []
        for line in text.splitlines():
            if line.startswith("| ") and "`" in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                if cells and cells[0].isdigit():
                    rows.append(cells)
        return rows

    def test_targets_are_exactly_four(self):
        # extracted from the argument-hint, which enumerates the closed target set
        hint = re.search(r"^argument-hint: \"\[([^\]]+)\]", self.command, re.M)
        self.assertIsNotNone(hint, "argument-hint must enumerate the targets")
        self.assertEqual(hint.group(1).split("|"),
                         ["claude", "codex", "antigravity", "all"],
                         "the target set is closed and ordered")
        # ...and again from the Targets section itself, so a target introduced only in
        # the body is caught by this test rather than incidentally by a clause
        body = self._section("## Targets", "## Modes")
        named = {t for t in re.findall(r"`([^`]+)`", body)
                 if re.fullmatch(r"[a-z]+", t)}
        self.assertEqual(named, {"claude", "codex", "antigravity", "all"},
                         f"the Targets section names an unfrozen target: {sorted(named)}")

    #: Where each artifact defines its confidence vocabulary. Scoping the scan to the
    #: defining section is what lets it capture BARE words without drowning in prose.
    GRADE_REGION = {"command": ("## Step 3", "## Step 4"),
                    "agent": ("## Confidence,", "## Output format")}

    def _region(self, key):
        text = self.both[key]
        start, end = self.GRADE_REGION[key]
        self.assertIn(start, text, f"{key}: confidence section not found")
        i = text.index(start)
        return text[i:text.index(end, i)]

    def _section(self, start, end, key="command"):
        text = self.both[key]
        self.assertIn(start, text, f"{key}: section {start!r} not found")
        i = text.index(start)
        return text[i:text.index(end, i)]

    def test_mode_flags_are_exactly_the_frozen_set(self):
        # every flag ANYWHERE, backticked or not, long or short: a mode introduced in
        # plain prose or as `-a` is still a mode
        flags = set(re.findall(r"(?<![\w-])(--?[a-z][a-z-]*)", self.command))
        self.assertEqual(
            flags, {"--dry-run", "--apply", "--min-confidence", "--overlay-root"},
            f"an unfrozen flag appeared: {sorted(flags)}")

    def test_threshold_values_are_exactly_high_medium(self):
        # accept every separator the flag could be written with (space, `=`, backtick),
        # so `--min-confidence=critical` is captured as readily as the frozen form
        values = set(re.findall(r"--min-confidence[=\s`]+([a-zA-Z|<>-]+)", self.command))
        tokens = {v for value in values for v in re.split(r"[|<>]", value) if v}
        self.assertEqual(tokens, {"high", "medium"},
                         f"threshold vocabulary drifted: {sorted(tokens)}")

    def test_confidence_grades_in_both_artifacts(self):
        for key in self.both:
            with self.subTest(artifact=key):
                region = self._region(key)
                # three grade-defining shapes, none of which assumes backticks or a
                # fixed universe of words: a backticked term, a list item `- X — …`,
                # and a defining sentence `X is an/a/first-party …`
                tokens = set(re.findall(r"`([a-z]+)`", region))
                tokens |= {t for t in list_terms(region) if t.islower()}
                tokens |= {t for t in table_lead_cells(region) if t.islower()}
                tokens |= set(re.findall(
                    r"`?\b([a-z]+)\b`?\s+is\s+(?:an|a|first-party)\b", region))
                tokens -= self.GRADE_SECTION_PROSE
                self.assertEqual(tokens, {"high", "medium"},
                                 f"{key}: grade vocabulary drifted: {sorted(tokens)}")

    #: Lowercase words that legitimately appear in a grade-defining position in the
    #: confidence sections without being grades. Asserted by subtraction, so a NEW
    #: prose word in that position also fails — the exemption list cannot silently grow.
    GRADE_SECTION_PROSE = {"withheld", "row", "claim", "grade", "reason", "confidence"}

    def test_unclassified_reasons_in_both_artifacts(self):
        for key in self.both:
            with self.subTest(artifact=key):
                # every hyphenated lowercase term in the section, backticked or not —
                # a reason written plainly as evidence-missing is still a reason
                region = self._region(key)
                terms = set(re.findall(r"\b([a-z]+-[a-z]+)\b", region))
                self.assertEqual(
                    terms, {"source-silent", "source-conflict"} | self.REGION_PROSE[key],
                    f"{key}: a new hyphenated term appeared in the confidence "
                    f"section: {sorted(terms)}")

    #: The hyphenated NON-reason vocabulary each confidence section already contains.
    #: Equality against reasons ∪ this set means any new hyphenated term fails, however
    #: it is written, and the exemptions are enumerated rather than pattern-excused.
    REGION_PROSE = {
        "command": {"all-medium", "first-party", "min-confidence", "no-change"},
        "agent": {"first-party"},
    }

    def test_propagation_classes_are_exactly_four(self):
        # structural: the lead term of each list item in the classification section,
        # so `1. **ARCHIVAL**` and `- **ARCHIVAL**:` are as visible as the frozen form
        section = self._section("Classify every occurrence", "## Step 7")
        classes = [t for t in list_terms(section) if t.isupper()]
        self.assertEqual(classes,
                         ["SOURCE", "DOCUMENTARY", "ENCODED", "OPERATIONAL"],
                         "the propagation classes are a closed, ordered set of four")

    def test_agent_tag_vocabulary_is_closed_outside_the_table_too(self):
        # every all-caps word in the agent, backticked, bolded or plain, compared by
        # equality — a sixth tag cannot hide in prose, and because the emphasis words
        # are enumerated rather than pattern-excused, a new one fails here too
        caps = set(re.findall(r"\b([A-Z]{3,})\b", self.agent))
        self.assertEqual(
            caps, set(self.D3_TAGS) | {"UNCLASSIFIED"} | self.AGENT_EMPHASIS,
            f"agent all-caps vocabulary drifted: {sorted(caps)}")

    #: All-caps words the agent uses for prose emphasis or as proper nouns.
    AGENT_EMPHASIS = {"BOTH", "FIRST", "NOT", "ONE", "SKILL", "URL", "WITH"}

    #: The D7 classes' full DEFINITIONS, not just their names. Binding the name alone
    #: lets the meaning be inverted underneath it — DOCUMENTARY could be redefined to
    #: update untouched prose while the four names still compare equal.
    CLASS_DEFINITIONS = [
        "- **SOURCE** — the overlay skills themselves.",
        "- **DOCUMENTARY** — prose restating an overlay fact. On `--apply`, updated ONLY "
        "when the fact it restates is one this run changed (each with a Step-4 note); a "
        "documentary occurrence of an untouched fact is reported and left alone.",
        "- **ENCODED** — a machine-readable transcription (`bin/vibe-check`'s "
        "`KNOWN_EVENTS`, `scripts/score_engine.py`'s rows, `scripts/check_engine.py`'s "
        "hook-config schema).",
        "- **OPERATIONAL** — code reading or writing per-tool paths as its function (the "
        "bridge family, `doctor.py`, `update.py`, the migration scripts, the hook "
        "scripts).",
    ]

    def test_propagation_class_definitions_are_exact(self):
        section = self._section("Classify every occurrence", "## Step 7")
        found = [" ".join(m.group(0).split()) for m in
                 re.finditer(r"(?ms)^- \*\*[A-Z]+\*\*.*?(?=^- \*\*|^\Z|^[A-Z])", section)]
        self.assertEqual(found, self.CLASS_DEFINITIONS,
                         "a class definition changed while its name stayed the same")

    #: Every bare-lowercase inline code span in each artifact. These artifacts name
    #: their vocabulary in code spans, so pinning the whole set by equality catches a
    #: term added ANYWHERE — outside any section a region-scoped check would look at.
    CODE_SPANS = {
        "command": {"all", "antigravity", "claude", "code-change-required", "codex",
                    "high", "medium", "source-conflict", "source-silent"},
        "agent": {"high", "medium", "source-conflict", "source-silent"},
    }

    #: The command's whole-file all-caps and hyphenated vocabularies. Region-scoped
    #: checks cannot see a term added outside the region they scan; these can, and their
    #: expectations live in test code rather than in a fixture, so re-blessing a golden
    #: does not also re-bless them.
    COMMAND_CAPS = {
        "ADD", "AGENTS", "BOTH", "CHANGES", "CLAUDE", "CONFIRM", "DOCUMENTARY",
        "ENCODED", "EXCLUDING", "FIRST", "FIX", "GEMINI", "HTML", "ISO", "ONLY",
        "OPERATIONAL", "PATH", "REMOVE", "REQUIRED", "REQUIRES", "RESOLVED", "SOURCE",
        "UNCLASSIFIED", "UNVERIFIED", "URL", "YAML",
    }
    COMMAND_HYPHENATED = {
        "all-medium", "argument-hint", "case-sensitively", "code-change", "dry-run",
        "first-party", "gemini-extension", "hook-config", "label-only", "ls-files",
        "machine-readable", "min-confidence", "no-change", "no-op", "non-zero",
        "overlay-root", "overlay-style", "per-row", "per-tool", "re-touches",
        "re-verified", "run-date", "single-overlay", "source-conflict", "source-silent",
        "spec-researcher", "spec-sync", "tool-agnostic", "tool-convention", "un-hedged",
        "vibe-check", "vibe-suite",
    }

    def test_command_whole_file_vocabularies_are_closed(self):
        caps = set(re.findall(r"\b([A-Z]{3,})\b", self.command))
        self.assertEqual(caps, self.COMMAND_CAPS,
                         f"command all-caps vocabulary drifted: "
                         f"{sorted(caps ^ self.COMMAND_CAPS)}")
        hyphenated = set(re.findall(r"\b([a-z]+-[a-z]+)\b", self.command))
        self.assertEqual(hyphenated, self.COMMAND_HYPHENATED,
                         f"command hyphenated vocabulary drifted: "
                         f"{sorted(hyphenated ^ self.COMMAND_HYPHENATED)}")

    def test_code_span_vocabulary_is_closed(self):
        for key, text in self.both.items():
            with self.subTest(artifact=key):
                spans = {s for s in re.findall(r"`([^`\n]+)`", text)
                         if re.fullmatch(r"[a-z][a-z-]*", s)}
                self.assertEqual(spans, self.CODE_SPANS[key],
                                 f"{key}: inline-code vocabulary drifted: "
                                 f"{sorted(spans)}")

    def test_agent_table_rows_are_exact(self):
        self.assertEqual(self._rows(self.agent), self.AGENT_TABLE,
                         "the agent's tag table must match D3's semantics exactly")

    def test_agent_frontmatter_is_parsed_not_pattern_matched(self):
        # a duplicate key would let a second `tools:` line override the allowlist while
        # a line-regex still matched the first — so parse the block and reject dupes
        lines = self.agent.split("\n")
        self.assertEqual(lines[0], "---")
        keys, fields = [], {}
        for line in lines[1:]:
            if line == "---":
                break
            # a key at ANY indentation and in EITHER quoting style: YAML resolves
            # `"tools":` and an indented `tools:` to the same key, so a parser that
            # only recognises bare keys at column 0 lets a later duplicate silently
            # override the allowlist while the first line still reads correctly
            # `? tools` is YAML's explicit-key form and resolves to the same key as a
            # plain `tools:`, so it is a duplicate the parser must see
            m = re.match(
                r"""^\s*(?:\?\s+)?(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))\s*:?\s*(.*)$""",
                line)
            if m:
                key = m.group(1) or m.group(2) or m.group(3)
                keys.append(key)
                fields[key] = m.group(4).strip()
        self.assertEqual(len(keys), len(set(keys)),
                         f"duplicate frontmatter key: {keys}")
        self.assertEqual(set(keys), {"name", "description", "model", "tools"},
                         f"the frontmatter key set is closed: {sorted(keys)}")
        self.assertEqual([t.strip() for t in fields["tools"].split(",")],
                         ["WebFetch", "WebSearch", "Read"],
                         "the tool allowlist is closed")
        self.assertEqual(fields["model"], "sonnet")


class FreshnessNormalization(unittest.TestCase):
    def test_exact_canonical_lines(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(CANONICAL[name], squash(text))
                self.assertEqual(text.count("**Spec freshness:**"), 1)
                self.assertIn(PRESERVED[name], squash(text))

    def test_canonical_line_is_first_content_after_h1(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                lines = path.read_text(encoding="utf-8").splitlines()
                h1 = next(i for i, l in enumerate(lines) if l.startswith("# "))
                after = [l for l in lines[h1 + 1:] if l.strip()]
                self.assertTrue(after[0].startswith("**Spec freshness:**"),
                                f"{name}: first content after H1 is {after[0][:60]!r}")

    def test_no_superseded_marker_and_no_dated_description(self):
        for name, path in OVERLAYS.items():
            with self.subTest(overlay=name):
                text = path.read_text(encoding="utf-8")
                for old in SUPERSEDED:
                    self.assertNotIn(old, text)
                description = next(
                    (l for l in text.splitlines() if l.startswith("description:")), "")
                self.assertNotRegex(description, r"\d{4}-\d{2}-\d{2}")


class FixtureOracle(unittest.TestCase):
    def test_fixture_seeds_present(self):
        overlay = (FIX / "stale-overlay" / "SKILL.md").read_text(encoding="utf-8")
        for n in range(1, 8):
            self.assertIn(f"SEED {n}", overlay)
        self.assertTrue((FIX / "stale-overlay" / "consumer-linked.md").is_file())
        self.assertTrue((FIX / "stale-overlay" / "consumer-uncited.md").is_file())

    def test_recorded_dry_run_matches_the_oracle_one_to_one(self):
        self.assertTrue(RECORDED.is_file(),
                        "the recorded manual dry run is missing")
        recorded = RECORDED.read_text(encoding="utf-8")
        self.assertRegex(recorded.splitlines()[0] + recorded.splitlines()[1],
                         r"(?i)provenance|recorded")
        self.assertIn("--overlay-root", recorded)
        expected_rows = report_rows(EXPECTED.read_text(encoding="utf-8"))
        self.assertEqual(len(expected_rows), 7, "the oracle must carry seven seeds")
        recorded_rows = report_rows(recorded)
        self.assertEqual(recorded_rows, expected_rows,
                         "recorded run drifted from the hand-authored oracle")
        # every row well-formed: a known tag, and a confidence/reason from the
        # closed vocabulary — a malformed or invented row fails here
        allowed = set(TAGS) | {"UNCLASSIFIED"}
        vocab = {"high", "medium", "source-silent", "source-conflict"}
        for seed, section, tag, conf in recorded_rows:
            self.assertIn(tag, allowed, f"seed {seed}: unknown tag {tag!r}")
            self.assertIn(conf, vocab, f"seed {seed}: bad confidence/reason {conf!r}")
            self.assertTrue(section.startswith("§"), f"seed {seed}: section {section!r}")
        self.assertEqual(len({r[0] for r in recorded_rows}), 7, "seeds must be unique")

    def test_dry_run_wrote_nothing(self):
        recorded = squash(RECORDED.read_text(encoding="utf-8"))
        self.assertRegex(recorded, r"(?i)no file (was )?written|dry run: no write")
        self.assertRegex(recorded, r"(?i)no verify|verify skipped")


class ThresholdRegressions(unittest.TestCase):
    """The two cases the plan review required (step-6 finding 6)."""

    def test_default_is_medium(self):
        flat = squash(COMMAND.read_text(encoding="utf-8"))
        self.assertIn("(**default `medium`**", flat)

    def test_all_medium_under_high_takes_no_change_branch(self):
        flat = squash(COMMAND.read_text(encoding="utf-8"))
        self.assertRegex(
            flat,
            r"(?i)all-medium run under `--min-confidence high` applies nothing")
        self.assertRegex(flat, r"(?i)no write, no bump, no propagation, no verify")


if __name__ == "__main__":
    unittest.main()
