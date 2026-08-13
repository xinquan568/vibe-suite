# Four bytes of quoting, approved by two OpenAI engineers

> **Disclosure**: Unlike the [wshobson/agents case study](2026-04-18-wshobson-agents.md) which was authored by an automated pipeline, this one was written by hand from the evidence. The audit data, PR diffs, and merge timestamps are GitHub records; the framing and commentary are editorial. The NLPM pipeline did not request comment from the maintainers before publication.

---

## The project

[openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) is OpenAI's official Claude Code plugin for integrating [Codex](https://openai.com/codex) into Claude workflows. A small, focused plugin — 13 artifacts total: 1 agent, 6 commands, 3 skills, 1 manifest, 1 hook config, and 1 main script suite. Not a marketplace; a single-purpose tool.

The repo is maintained by [Dominik Kundel](https://github.com/dkundel-openai) (OpenAI devrel) and reviewed by at least one other OpenAI contributor ([@traverswolf-png](https://github.com/traverswolf-png)).

## The audit

NLPM scored all 13 artifacts on 2026-04-06. Overall **93/100 — Gold tier**. The distribution shows what a mostly-clean codebase looks like:

| Score band | Files |
|---|---|
| 100/100 | 2 (status.md, plugin.json) |
| 98/100 | 3 skills (docked only for one vague quantifier each) |
| 90/100 | 6 commands (docked for multi-step flow phrasing + empty-input handling) |
| 80/100 | 1 agent (missing `model:` + zero example blocks) |

**Weighted average: 93/100.** This is what Gold tier looks like when it's earned — not by leaving low-scoring files unaudited, but by being consistently careful across a small surface area.

The security scan was more interesting than the quality score. **Zero Critical, zero High, five Medium, one Low.** The five Mediums clustered around shell-command hygiene in the plugin's own slash commands.

## What was submitted

Two PRs, opened 2026-04-07 06:11 UTC. Small by design — the codebase was small, so the fix surface was small too.

| PR | Title | Lines changed | Files |
|---|---|---|---|
| [#168](https://github.com/openai/codex-plugin-cc/pull/168) | fix: quote $ARGUMENTS in cancel, result, and status commands | +3 / −3 | 3 |
| [#169](https://github.com/openai/codex-plugin-cc/pull/169) | fix: declare model in codex-rescue agent frontmatter | +1 / −0 | 1 |

PR #168 is genuinely just four bytes of quoting, applied to three files. The change, per file:

```diff
-!`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" cancel $ARGUMENTS`
+!`node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" cancel "$ARGUMENTS"`
```

That's it. Wrap `$ARGUMENTS` in double quotes so shell metacharacters in a user-supplied job-id don't expand before Node receives them. Without the quotes, a crafted input like `task-123; malicious-cmd` would split on the semicolon and the trailing command would execute.

The telling detail: the plugin's **longer** commands, `review.md` and `adversarial-review.md`, already quoted `"$ARGUMENTS"` correctly. The three short `!`-prefix commands didn't. Same author, same repo, same week — different enough attention budget to slip. NLPM caught the inconsistency by pattern-matching within the repo.

PR #169 added one line: `model: sonnet`. The `codex-rescue` agent had no model declaration, which means it ran on whatever tier Claude Code assigned by default. For a "rescue" agent invoked when Claude is stuck, defaulting to an unspecified tier is a cost and capability question waiting to happen.

A tracking issue, [#170](https://github.com/openai/codex-plugin-cc/issues/170), was filed at the same time summarizing all four bugs with links to the two PRs.

## The response

This is the most interesting part, and the sharpest contrast with our other Gold-tier engagement ([wshobson/agents](2026-04-18-wshobson-agents.md)).

**Human review, not agentic sweep.** Both OpenAI contributors left explicit `APPROVED` review states on the repo — real GitHub Pull Request reviews, not just merges:

| PR | Reviews | Reviewers |
|---|---|---|
| #168 | 2 × APPROVED | dkundel-openai, traverswolf-png |
| #169 | 0 reviews, merged directly | dkundel-openai |

That two-review pattern on the security-relevant PR, single-merge on the trivial frontmatter PR, suggests differentiated review effort proportional to risk — the behavior of attentive humans, not a template loop.

**Response latency: ~39 hours.** PRs opened 2026-04-07 06:11 UTC; PR #169 merged 2026-04-08 21:28:45Z; PR #168 merged 2026-04-08 21:48:50Z. That's 1.6 days to evaluate, review, and merge a drive-by external PR from a stranger — fast for a company repo, and well inside a "normal business day" response window.

**Unusual ordering.** The tracking issue #170 was closed at 2026-04-08 04:49:39Z — about **17 hours before** the PRs were merged. The maintainer acknowledged the findings early, then held the PRs for separate review. Reading the timestamps:

1. Issue acknowledged and closed → triage signal ("we see this, thanks")
2. ~17 hours gap
3. PR #169 (trivial fix) reviewed and merged
4. 20 minutes later, PR #168 (security fix) gets its second approval and merges

This is roughly the inverse of wshobson's pattern: a single 13-second agentic burst vs. a 39-hour human workflow with intermediate signals.

**Selective acceptance.** NLPM flagged 4 bugs, 6 security findings, and 10 quality issues — 20 items total. The maintainer merged fixes for **4 of 4 bugs**, **3 of 6 security findings**, and **0 of 10 quality issues**.

| Category | Flagged | Addressed via PR | Acceptance shape |
|---|---|---|---|
| Bugs (functional) | 4 | 4 | 100% |
| Medium security (shell/IO hygiene) | 5 | 3 | 60% — only the $ARGUMENTS cluster |
| Low security (pinned deps) | 1 | 0 | 0% |
| Quality (numbering, empty-input, vague quantifiers) | 10 | 0 | 0% |

The 60%-on-security split is informative. The three fixes that landed were all small, mechanical, and came as a single bundled PR (`cancel`, `result`, `status` all share the same one-char change). The two security fixes that didn't land — Windows shell mode in `process.mjs`, env-file write bounds in `session-lifecycle-hook.mjs` — are genuinely more involved and require design judgment, not mechanical application. NLPM did not send PRs for those; the audit report flagged them as "suggest fix," not "trivially fixable."

The zero-out on quality issues is also consistent. Asking a maintainer to renumber every "steps described as bullets" complaint or replace every "better" with a more specific word is stylistic territory — below the threshold where an external PR feels welcome.

## What the audit revealed

**Consistency checking beats style checking.** The finding that produced 3 of 4 bugs was pattern-matching within the repo: the long commands quoted `"$ARGUMENTS"`, the short ones didn't. An NL linter that just checks "every `$ARGUMENTS` is quoted" would have flagged this too — but framing the finding as "this file is inconsistent with these peer files in the same plugin" is more persuasive than "here is a rule you violated." The diff tells the story.

**A Gold-tier score isn't a pass.** 93/100 still surfaced 4 real bugs and 3 mergeable security fixes. Scoring at 93 means there's no systemic rot, not that nothing is broken. The fixes here were small, but they closed a genuine shell-injection surface in a plugin that will be installed by developers trusting OpenAI's own distribution.

**Small audits accept more cleanly.** A 13-artifact plugin gets a 39-hour human review. A 509-artifact marketplace gets a 13-second agentic burst. The reviewer-type isn't a property of the maintainer's personality — it's a function of surface area. No one reviews 509 artifacts by hand, and no one needs to automate review on 13 artifacts.

**OpenAI's acceptance signals something structural for NLPM.** An external tool proposing security fixes to an OpenAI-official plugin, reviewed by two OpenAI contributors, landing in two business days, is a credibility data point. Not because OpenAI's stamp validates NLPM's rubric — it doesn't, and shouldn't — but because the workflow we converged on (small PRs, clear disclosure, evidence-grounded findings) passes the test at a major company's review bar. That's a useful baseline for what "good-faith automated contribution" looks like from their side.

## Timeline

| Time (UTC) | Event |
|---|---|
| 2026-04-06 | NLPM audit run (13 artifacts, score 93) |
| 2026-04-07 02:19 | Audit report committed; tracking issue #38 opened in NLPM |
| 2026-04-07 06:11 | Pipeline opens PR #168 (security) and #169 (agent model) |
| 2026-04-07 06:12 | Pipeline files tracking issue #170 upstream |
| 2026-04-08 04:49 | **OpenAI closes upstream issue #170** (acknowledgment signal) |
| 2026-04-08 21:28:45 | PR #169 merged (trivial fix, single approver) |
| 2026-04-08 21:48:50 | PR #168 merged (security fix, two approvers) |

~39 hours from PR open to merge. ~22 hours from issue-acknowledgment to PRs merged.

## Limitations

**Review reasoning not captured.** Both reviewers left `APPROVED` states without inline comments. We have the verdict, not the reasoning. The Gold-tier score and mechanical fix pattern made review low-effort, but we can't confirm what decision criteria the reviewers actually applied.

**The three unmerged Medium findings weren't PR'd.** The contribute workflow skipped `process.mjs` and `session-lifecycle-hook.mjs` because the suggested fixes required design judgment (Windows shell mode vs. explicit array spawning; env-file path validation). The audit report recommends manual follow-up. It's unclear whether OpenAI plans to address them independently; no comments to that effect are in the evidence.

**Audit was pre-cap-fix.** This audit ran on 2026-04-06, before the NLPM 100-file sample cap was introduced and before the [wshobson sampling-blind-spot debrief](2026-04-18-wshobson-agents-learnings.md) prompted the same-pattern full-scan proposal. The 13-artifact repo was small enough that the cap wouldn't have applied regardless, but the findings should be understood against that evolving baseline.

**No case study cover image.** The automated pipeline generates covers for its auto-written articles. This one was written by hand and no cover was generated. Not a methodology statement — just a constraint.

## Significance

NLPM's first Gold-tier acceptance from a major-organization repo. Not because the score was high (GSD scored higher); because the review process was human, thorough, and selective — the kind of review bar that makes approvals informative.

Four bytes of quoting sounds trivial. Shell injection in a Claude Code plugin reaches every user who installs it and passes arguments to the affected commands — the blast radius is not trivial. That's what makes a small, mechanical fix worth a 39-hour review cycle and two APPROVEDs from OpenAI engineers.

The broader pattern across our two Gold-tier engagements is worth naming: **different surface areas produce different review regimes, and NLPM's PR shape should reflect that.** Small repos merit patient, narrow PRs that earn human review. Large repos merit batched, pattern-grouped PRs that can pass a rubric at scale. The contribute workflow currently treats both the same. That's the next thing worth tuning.
