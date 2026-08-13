---
slug: numman-ali-n-skills
repo: numman-ali/n-skills
audited: 2026-05-13
commit_sha: a518c67eab71c9b24b08c20a4abf08b318368463
score: 96
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: numman-ali/n-skills

**Score**: 96/100  |  **Date**: 2026-05-13  |  **Commit**: `a518c67eab71c9b24b08c20a4abf08b318368463`

A curated five-skill collection covering multi-agent orchestration, open-source maintenance, browser automation, and CLI tooling — notable for trigger-saturated descriptions, explicit reference-routing tables with required-output columns, and mode tables that convert behavior into observable trigger → persona → signature patterns.

## Per-rule evidence

### R04 — Description as trigger

`gastown/SKILL.md` packs 18 distinct trigger terms into its `description` frontmatter, covering both domain-specific jargon (individual character names, CLI command names) and generic intent ("wants to run multiple AI agents"). This anticipates users who know the Gas Town vocabulary and users who do not.

> `skills/tools/gastown/skills/gastown/SKILL.md:3`:
>
> ```
> description: Multi-agent orchestrator for Claude Code. Use when user mentions gastown,
> gas town, gt commands, bd commands, convoys, polecats, crew, rigs, slinging work,
> multi-agent coordination, beads, hooks, molecules, workflows, the witness, the mayor,
> the refinery, the deacon, dogs, escalation, or wants to run multiple AI agents on
> projects simultaneously. Handles installation, workspace setup, work tracking, agent
> lifecycle, crash recovery, and all gt/bd CLI operations.
> ```

The description doesn't stop at one "use when" clause — it enumerates every alias a user might plausibly say. `open-source-maintainer/SKILL.md:3` applies the same pattern, explicitly labeling its list "Triggers include" and naming seven phrases a user would speak, not a developer would read.

---

### R05 — Body length

`open-source-maintainer/SKILL.md` is 179 lines. Rather than embedding full reference content inline, it declares a "Reference Router" table that delegates depth to eight focused reference files. The SKILL.md body carries only the workflow skeleton, interaction model, and gates.

> `skills/workflow/open-source-maintainer/skills/open-source-maintainer/SKILL.md:1-11`:
>
> ```
> ---
> name: open-source-maintainer
> description: End-to-end GitHub repository maintenance ...
> ---
>
> # Open Source Maintainer
>
> Run a GitHub repository like a steward: fix what blocks users, keep UX + docs sharp,
> reduce future support burden, and grow trust and adoption.
>
> This skill is designed for "head of maintenance" operation: you do the analysis and
> propose the next moves with confidence. The human should be able to mostly ask:
> "What's next?"
> ```

The full behavioral depth lives in eight reference files (workflow, intent-extraction, quality-checklist, decision-framework, communication-guide, config, repo-state-template, report-structure). The core SKILL.md stays lean by routing to them on demand rather than inlining their content.

---

### R06 — Runnable examples

`open-source-maintainer/SKILL.md` shows the triage script with real flags, not placeholder documentation. Each variant has a comment explaining the use case so Claude knows when to pick it.

> `skills/workflow/open-source-maintainer/skills/open-source-maintainer/SKILL.md:120-135`:
>
> ```bash
> # Standard run (creates reports/<datetime>/)
> npx tsx /path/to/open-source-maintainer/scripts/triage.ts
>
> # Compare with previous run
> npx tsx /path/to/open-source-maintainer/scripts/triage.ts --delta
>
> # Keep existing folder if same datetime
> npx tsx /path/to/open-source-maintainer/scripts/triage.ts --keep
>
> # Override report folder name
> npx tsx /path/to/open-source-maintainer/scripts/triage.ts --datetime 2026-01-17T12-30-00
>
> # Use a custom config path
> npx tsx /path/to/open-source-maintainer/scripts/triage.ts --config .github/maintainer/config.json
> ```

Every line is directly executable. The inline comments serve as decision criteria ("Compare with previous run" → when to use `--delta`), removing ambiguity about which variant to choose without requiring prose explanation.

---

### R07 — Scope note when related skills exist

`open-source-maintainer/SKILL.md` uses a three-column reference-routing table that goes beyond a passive `[[see-other]]` note: it specifies the task trigger, the file to load, and the output Claude must produce after loading it.

> `skills/workflow/open-source-maintainer/skills/open-source-maintainer/SKILL.md:49-61`:
>
> ```
> Do **not** read everything by default. Load the **minimum** reference needed.
>
> | When you are about to…                              | Load this reference                   | Output you must produce                           |
> |-----------------------------------------------------|---------------------------------------|---------------------------------------------------|
> | Analyze issues/PRs (intent, severity, actionability)| `references/intent-extraction.md`     | Clear intent + actionability + relationships      |
> | Assess PR approach quality/risk                     | `references/quality-checklist.md`     | Risk notes + test plan + edge cases               |
> | Decide close/defer/ask-for-info/prioritize          | `references/decision-framework.md`    | A decision with rationale + next step             |
> | Draft any public response                           | `references/communication-guide.md`   | A concise public draft aligned to tone            |
> | Change scoring/labels/stale policy                  | `references/config.md`                | Proposed config edits + impact                    |
> | Initialize/reshape `.github/maintainer/` state      | `references/repo-state-template.md`   | Correct state files created/updated               |
> ```

The required-output column closes the loop on whether the reference was used correctly — Claude can't just load `intent-extraction.md` and continue; it must produce a specific artifact. `gastown/SKILL.md` uses the same routing pattern at lines 501–507, mapping five situation types to five reference files with explicit when-to-load triggers.

---

### R08 — Patterns over theory

`gastown/SKILL.md` encodes response behavior as a three-mode pattern table instead of prose description. Each mode specifies observable trigger phrases, a defined persona, and a required output signature.

> `skills/tools/gastown/skills/gastown/SKILL.md:288-297`:
>
> ```
> **Learning** - User asks "what is", "explain", "how does", or is in tutorial
> → Welcoming guide voice → `━━ ⛽ Gas Town | Learning ━━`
>
> **Setup** - User says "install", "set up", "add rig"
> → Engineer building alongside → `━━ ⛽ Gas Town | Setup ━━`
>
> **Operating** - Commands, troubleshooting, quick answers
> → Fellow operator at gauges → `━━ ⛽ Gas Town ━━`
>
> **Every response ends with the appropriate signature.**
> ```

The format is: trigger phrase list → persona label → output signature. Claude doesn't infer when to switch modes — the trigger phrases are enumerated and the output is fixed. The same skill applies this pattern again for "First Contact" (lines 227–242), mapping specific user utterances to specific action branches with no ambiguity.

---

## Worth adopting

**Pattern: Required-output column in reference-routing tables.** Evidence: `skills/workflow/open-source-maintainer/skills/open-source-maintainer/SKILL.md:49-61`. R07 currently specifies a passive scope note ("For Y, see [[other-skill]]"). The `open-source-maintainer` table adds a third column — "Output you must produce" — that converts reference loading from optional context into a verifiable contract: Claude must produce a specific deliverable after reading the file. Candidate rule: **"Scope notes must declare expected output, not just the target file.** A 'load this' with no required output is unenforceable — Claude may read the reference but apply it inconsistently. Add: Output type (e.g., 'A decision with rationale + next step') so callers can verify the reference was applied."
