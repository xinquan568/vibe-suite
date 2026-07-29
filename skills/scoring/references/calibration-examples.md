# Calibration Examples

Four worked examples anchor the score bands: an Excellent Agent, a Rewrite Agent, an Excellent Rule, and a Weak Rule. The scorer loads this file on demand for borderline cases — not on every call. These walk-throughs were extracted from the rubric on 2026-05-28 to keep it under the R05 500-line body budget; the formula, penalty tables, and bands remain in [../SKILL.md](../SKILL.md).

## Example 1: Excellent Agent (95/100)

```markdown
---
name: dependency-security-audit
description: Audit project dependency manifests for known-vulnerable versions,
  typosquatted package names, and unpinned transitive ranges. Use after any
  lockfile change, before a release cut, or when a CVE advisory lands.
model: sonnet
tools: Read, Glob, Bash
skills: security-baseline
---

<example>
user: "We just bumped the lockfile — anything risky in there?"
assistant: "I'll run the dependency-security-audit agent over the changed manifests."
</example>
<example>
user: "A CVE dropped for one of our transitive deps."
assistant: "Dispatching dependency-security-audit to trace which manifests pull it in."
</example>

Scan every dependency manifest with Glob, Read each one, and compare pinned
versions against the advisory baseline from the security-baseline skill.

## Output format
Summary line with counts (files scanned, advisories matched), then a findings
table: package | version | advisory | severity | manifest path.
```

Score breakdown:

| Deduction | Rule | Value |
|-----------|------|-------|
| Bash declared but the body never invokes it (1 unused tool) | R11 | -3 |

Everything else passes: rich description with 3+ specific trigger phrases, two example blocks, sonnet on an analysis-tier task, tools declared, a skills reference, a defined output format (summary counts plus findings table), and read-only tool access for an audit agent.

**Final: 100 - 3 = 97/100 — Excellent.**

(Calibration note: a true 95 would have zero unused tools plus a scope note. The exact number is irrelevant — anywhere in 90–100 is Excellent either way.)

Lesson: even a near-perfect artifact still loses points for declared-but-unused tools, and the band label matters more than the exact score.

## Example 2: Rewrite Agent (41/100)

```markdown
---
name: code-helper
description: Helps with code tasks.
model: opus
tools: Read, Write, Edit, Bash, Glob, WebSearch, WebFetch
---

Help the user with whatever code work is relevant. Use the appropriate tools
as needed to get things done.
```

Score breakdown:

| Deduction | Rule | Value |
|-----------|------|-------|
| Zero example blocks | R09 | -15 |
| Generic description (no specific trigger phrases) | R09 | -15 |
| Opus for a routine task (haiku/sonnet appropriate) | R10 | -5 |
| Too many unused tools — WebSearch/WebFetch/Glob never appear in the body; judged 3–4 unused, rounded | R11 | -10 |
| Vague quantifiers ("appropriate", "relevant", "as needed"; 2 counted instances at -2 each) | R01 | -4 |
| No output format | R12 | -10 |

**Total: -59; applying max(0, 100 - 59) yields 41/100 — Rewrite.**

Lesson: the unused-tool and vague-quantifier counts may vary a little between reviewers; what matters is that an artifact with multiple fundamental issues lands well below 60.

## Example 3: Excellent Rule (92/100)

```markdown
---
description: All intra-plugin paths must go through the plugin-root env var
paths: hooks/**, commands/**
---

**Always reference intra-plugin files via `${CLAUDE_PLUGIN_ROOT}`, never via an
absolute path.** Absolute paths break the moment the plugin is installed on
another machine or under a different user; the env var keeps every hook and
command portable.

Correct:
{"command": "${CLAUDE_PLUGIN_ROOT}/scripts/check.sh"}

Incorrect:
{"command": "/Users/alice/plugins/my-plugin/scripts/check.sh"}
```

Score breakdown:

| Deduction | Rule | Value |
|-----------|------|-------|
| No cross-reference to related portability rules (a judgment call, not a formal penalty row) | -- | -3 |

Everything else passes: frontmatter description, bold imperative opening, portability rationale, testability (a grep for hardcoded `/Users/` paths verifies it), paths scoping, length budget, no linter overlap, no vague quantifiers.

**Final: 92/100 — Excellent.**

(Calibration note: the listed deductions do not arithmetically produce 92 — the remaining roughly-5-point gap reflects scope-coverage judgment, not a rubric violation.)

Lesson: excellent-band scores can legitimately include small judgment deductions beyond the formal penalty rows.

## Example 4: Weak Rule (40/100)

```markdown
Don't write bad code. Keep everything clean and well-organized, handle errors
appropriately, and follow best practices.
```

Score breakdown:

| Deduction | Rule | Value |
|-----------|------|-------|
| Missing frontmatter / description | R21 | -10 |
| No bold imperative opening | R21 | -5 |
| No rationale | R21 | -10 |
| Not specific or testable (unmeasurable adjectives) | R22 | -10 |
| Vague quantifier "appropriately" | R01 | -2 |
| Vague "well-organized" | R01 | -2 |
| Duplicates linter/formatter territory | R24 | -10 |
| Not enforceable by this suite or any tool | R22 (enforceability) | -10 |

**The deductions sum to -59; max(0, 100 - 59) then gives 41/100 — Rewrite.**

Lesson: as specified, this example sits NEAR 40 rather than exactly on it; judgment moves the precise value — whether "well-organized" is a vague quantifier, for instance.
