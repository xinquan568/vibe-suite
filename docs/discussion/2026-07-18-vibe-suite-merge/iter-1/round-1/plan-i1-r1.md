> **Historical record — superseded in part.**
> This is a planning artifact preserved for traceability, not a live specification. Where it
> disagrees with current configuration, current configuration wins. Known divergence: this document
> refers to the command namespace as `/vibe:`; the namespace is now **`/vibe-suite:`** (D1-revised,
> 2026-07-25), which follows from `.claude-plugin/plugin.json:name`. The bound issue2pr profile is
> authoritative on project facts.

# vibe-suite — Unified Function Catalog & Merge Proposal

**Goal:** merge every function of **cc-suite** (v0.8.1, commit `bb605ec`), **grill-for-claude** (v1.3.0, commit `938b1e8`), and **nlpm** (v1.1.2, commit `4ef75d4a`) — plus the three workspace skills **issue2pr**, **refine-proposal** (its **updated** version, with bilingual finalize), and **runs-stats** — into one Claude Code plugin, **vibe-suite**, importable into any new project. Where functions overlap, this proposal picks one canonical implementation and merges the duplicates, with rationale.

The plugin's home repository is **`codes/vibe-suite`** (github.com/xinquan568/vibe-suite), which also hosts the deployed auditor unit and the public site (owner decision D4, §5 Category 10).

*Iteration 1 — revised per the owner's answers to Q1–Q4 and suggestions 1–5 (see `iter-1/input.md`); the resolved decisions are recorded in "Resolved decisions" before the Assumptions block.*

This document is the reviewable deliverable: it lists (1) the function categories, (2) what each function does, and (3) a detailed specification for each function, followed by a full source-artifact disposition map proving that every source function is accounted for, and (§11) the requested fact-based analysis of issue2pr standardization.

---

## 1. Summary

vibe-suite is organized as **ten function categories** containing **57 functions** (see the deliverable inventory in §5.0 for the exact shipped-artifact counts, from which every number in this document is derived), built on a three-layer architecture inherited from the sources: **commands orchestrate, agents execute, skills know**, with all deterministic file mutation done by idempotent scripts (cc-suite's discipline) and all quality judgments backed by a deterministic rubric (nlpm's discipline).

The headline merge decisions:

1. **NL-artifact quality → two complementary engines, one contract.** nlpm's deterministic rubric engine (`/vibe:score`, R01–R51, penalties, history) is canonical for *lint-class* scoring of plugin/config/memory artifacts. cc-suite's cross-model auditor family survives intact as **one typed command**, `/vibe:nl-audit` (F4.9), preserving each source auditor's discovery rules (including prompts, non-plugin agent frameworks, specs, plans, and design docs — categories nlpm never covered), per-type dimension sets, `--full/--mini` depth, and output contract. The two engines share discovery partials and the suite finding contract; neither's behavior is lost.
2. **Code review → grill engine wins.** cc-suite's 9-dimension `/audit` is retired as a separate command; grill's recon-first multi-agent `roast` becomes the one code-review orchestrator, with cc-suite's Codex delegation available as `--engine codex|both`.
3. **Generator-critic loops → one shared reviewer contract.** refine-proposal (documents), issue2pr (issue→PR), and the fix loop (findings→fixes) all run on one shared reviewer-backend contract (Codex dispatch, `none|single|full` review modes, bounded rounds, YAML verdict fences, closure state machine). cc-suite's `review-plan` is retired into `refine-proposal --review-mode single`.
4. **The nlpm auditor pipeline is merged, not dropped.** The self-evolving open-source audit-and-contribute pipeline (discover → audit → contribute → track → case-study → daily-report, plus its feedback loop and site tooling) becomes Category 10 — it is exactly the "browse mainstream open-source projects, identify issues, fix bugs, submit contributions" capability named in vibe-suite's founding notes. It deploys under **github.com/xinquan568/vibe-suite** (D4) with the public site rebranded to vibe-suite; its ~32 MB accumulated ops *data* migrates as data onto a dedicated data branch of that repo (§7A row 9); its *functions* are all specified here.
5. **Division of labor across AI tools (D5), with no pinned model versions (D6).** By default: **Claude Code does the work** (drafting, implementation, orchestration — the worker everywhere), **Codex does the reviews** (every generator-critic loop and verify pass), and **Gemini via the agy CLI audits** — the *target* cross-model engine for audit-class commands (nl-audit, and the second-opinion lanes of score/roast/security-scan). Because the agy CLI's headless contract is not yet confirmed (Q5), the rollout is **staged**: v1 ships with codex as the cross-model audit default, and the default flips to agy the moment the F2.7 adapter's contract is confirmed and its acceptance fixtures pass (AC-9). Every tool runs on **its own current default/best model** — the suite never pins a versioned model ID (today that resolves to Claude Fable 5 / GPT-5.6-sol / Gemini 3.1 Pro, but those names appear nowhere in shipped artifacts). Model-tier aliases (haiku/sonnet/opus-class) remain allowed for in-session agents; dated or versioned IDs are lint-banned (AC-9).

Namespace: all commands ship under **`/vibe:*`** (D1 — confirmed). One project config file, **`.vibe-suite.md`**, supersedes `.cc-suite.md` and `.claude/nlpm.local.md` (migration matrix in §7A).

---

## 2. Sources and scope

| Source | Version pinned | What it contributes |
|---|---|---|
| `codes/cc-suite` | 0.8.1 (`bb605ec`) | Cross-tool config bridge (Claude ⇄ Codex ⇄ Gemini), Codex delegation + job engine, cross-model NL auditor family, advisor personas, stop-review gate |
| `codes/grill-for-claude` | 1.3.0 (`938b1e8`) | Multi-angle code interrogation (recon + 5 specialists), severity/effort taxonomy, six-field finding contract, review styles & add-ons |
| `codes/nlpm` | 1.1.2 (`4ef75d4a`) | NL-artifact scoring (R01–R51, 100-point deterministic rubric), consistency checking, NL-TDD, vocabulary discipline, security pattern DB, trend/report, deterministic Python validators, and the open-source auditor pipeline + site tooling |
| `.claude/skills/issue2pr` | workspace copy | Nine-step three-phase AI-reviewing-AI issue→PR pipeline with chain/manifest/resume/iterate; reviewer backends `codex` and `copilot-cli` as specified in the source skill |
| `.claude/skills/refine-proposal` | workspace copy (**updated version**) | Generator-critic proposal refinement loop, now including `--stop-severity`, the self-review fallback (`--allow-self-review`), and the bilingual finalize path (`--second-language` + one-pass translation fidelity review, state schema v6) — this document was produced by it |
| `.claude/skills/runs-stats` | workspace copy (**new**) | Time-bucketed static-HTML statistics dashboards over issue2pr's `runs/` directory (day/week/month/all-time, freeze/signature history model, ad-hoc filtered reports) |

**Merge-completeness rule:** every *function* in these six sources is either kept, merged, or generated — §6 maps each one, and a disk-driven coverage check (§10, AC-1) enforces it. The only things not carried as functions are **data corpora** (nlpm's `auditor/` accumulated audit data, exemplar corpus, and `case-studies/` articles — migrated as data per §7A) and **platform constraints** (§8).

**Provenance posture (D7).** The three referenced repos (cc-suite, grill-for-claude, nlpm) are third-party projects vibe-suite *references for functionality*: their capabilities are **reimplemented in vibe-suite's own code at functional parity**, and the repository README acknowledges them collectively — no per-file or per-function source attribution ships in the repo. The three workspace skills are the owner's own work and port directly. The §6 disposition map and `docs/disposition.yaml` are **internal planning/coverage artifacts** (they prove merge completeness); they are not an attribution mechanism.

---

## 3. Merge principles

- **P1 — One implementation per job.** Every overlap resolves to a single canonical implementation; the loser is retired only when the winner demonstrably covers its use cases (proven by the equivalence fixtures in §10), otherwise both are kept on shared infrastructure.
- **P2 — Deterministic where possible, model-judged where necessary.** Scripts own config mutation (cc-suite); Python validators own schema checks (nlpm `bin/nlpm-check`); models own judgment. Never let an LLM do what a script can.
- **P3 — One finding language.** grill-core's severity scale (`[CRITICAL] [HIGH] [MEDIUM] [LOW] [GOOD]`), effort scale, and six-field finding format become the suite-wide finding contract. nlpm's numeric penalties remain the scoring engine's internals, with a fixed severity mapping (HIGH ≥ 10 pts, MEDIUM 5–9, LOW < 5) rendering into the shared format. cc-suite's Critical/High/Medium/Low audit severities map 1:1 (its `Critical` = `[CRITICAL]`).
- **P4 — One reviewer contract.** All generator-critic loops share: reviewer = non-worker model family (default: **Codex on its backend-default model**, same-model refusal), review modes `none|single|full`, bounded rounds, fenced YAML verdicts parsed last-block-only with one re-ask, and the open→fixed/declined→challenged closure machine.
- **P5 — Single-source, generated mirrors.** Dual-runtime (Codex CLI) artifact copies are *generated* from the canonical Claude artifacts by a sync script — never hand-maintained (full spec in F9.6). This kills the observed drift in both grill (stale versions across twins) and nlpm (15/17 mirrored skills diverged).
- **P6 — Fix inherited defects at merge time.** Known weaknesses of the sources (cc-suite W1–W13, grill W1–W12, nlpm S1–S12) are either fixed by design here or explicitly deferred (§7).
- **P7 — Dogfood.** vibe-suite scores itself with its own quality engine (`/vibe:score` ≥ threshold as a release gate) and maintains its own vocabulary registry (R51 enabled).
- **P8 — Division of labor: Claude works, Codex reviews, agy audits (D5) — staged.** The worker is always the Claude session. The critic in every generator-critic loop (refine-proposal, issue2pr, fix-verify, stop gate) defaults to the **codex** backend. For **audit-class** commands (nl-audit; the `--engine` second-opinion lanes of score, roast, and security-scan) the *target* cross-model engine is **agy** (Gemini CLI) via F2.7 — but a default execution path may not rest on an unconfirmed CLI contract, so the rollout is staged: **v1 ships `cross_model_audit_engine: codex`**, and the default flips to agy when the F2.7 adapter contract is confirmed (Q5) and its acceptance fixtures pass (AC-9). Once agy is the resolved engine, runtime unavailability falls back to codex (diagnostic header, per F9.5). All defaults are configurable in `.vibe-suite.md`.
- **P9 — No pinned model versions (D6).** Shipped artifacts never name a versioned model ID (`gpt-5.5`, `gemini-3.1-pro`, dated Claude IDs, …). External CLIs (codex, agy, copilot) run on **their own configured default model** unless the user overrides per run; in-session agents use **tier aliases** (haiku/sonnet/opus-class) that track each tier's latest. Model *discovery* (F1.5) is dynamic; model *choice* is user > project config > tool default. Enforced by AC-9's lint.

---

## 4. Architecture overview

```
vibe-suite/                          (single Claude Code plugin, /vibe:* namespace; repo: codes/vibe-suite)
├── .claude-plugin/plugin.json       manifest (explicit commands/agents/skills arrays)
├── .claude-plugin/marketplace.json  single-plugin marketplace entry (as both sources ship)
├── commands/          26 slash commands + shared/ (8 partials)
├── agents/            14 agents
├── skills/            22 skills (19 knowledge + 3 user-invocable workflow skills)
├── hooks/             4 plugin hook registrations (SessionStart, SessionEnd, Stop, PostToolUse)
├── scripts/           bridge scripts, codex-runner job engine, agy-runner, mirror-sync generator
├── bin/               8 deterministic Python tools (check, report, badge, 5 build tools)
├── templates/         advisor personas ×6, issue2pr profile contract + reference example, pre-commit + CI templates
├── auditor/           the open-source audit pipeline unit (24 workflows + scripts + prompts)
└── codex/             GENERATED Codex CLI mirror (never hand-edited)
```

Per-project state (all outside the plugin):

| Store | Path | Owner functions |
|---|---|---|
| Suite config | `.vibe-suite.md` (project root) | init, config; read by all |
| Quality history | `.claude/vibe-history.json` | score, trend, report |
| HTML reports | `.claude/vibe-reports/` | report |
| Codex job state | `$CLAUDE_PLUGIN_DATA/state/<workspace-slug>/` | jobs engine |
| Workflow runs | `runs/<run-id>/` | issue2pr |
| Run statistics | `runs/_reports/` | runs-stats |
| Discussions | `docs/discussion/<date>-<slug>/` | refine-proposal |

Runtime toggles that must survive outside markdown (stop-gate on/off, gate model) live in the job-state `state.json:config` block; `.vibe-suite.md` holds everything human-edited. `/vibe:config` (F1.8) is the single front-end to both, so the split is invisible to the user.

---

## 5. Function catalog

### 5.0 Deliverable inventory (the counts everything else derives from)

| Kind | Count | Names |
|---|---|---|
| Slash commands | 26 | init, doctor, repair, unbridge, preflight, bridge, update, config · delegate, bug-analyze, continue, jobs · roast, fix · ls, score, check, test, vocab, spec-sync, nl-audit · security-scan · advisor · trend, report, refresh-knowledge |
| Workflow skills (user-invocable) | 3 | refine-proposal, issue2pr (incl. its `profile init` mode), runs-stats |
| Agents | 14 | recon, architecture, error-handling, security, testing, edge-cases · scanner, scorer, vague-scanner, checker, tester, vocab-drift-scanner, security-scanner, spec-researcher |
| Knowledge skills | 19 | vibe-core, rules, scoring, conventions, conventions-claude, conventions-codex, conventions-antigravity, patterns, testing, security, vocabulary, writing-skills, writing-agents, writing-rules, writing-prompts, writing-hooks, writing-plugins, orchestration, agent-design |
| Shared partials | 8 | discover, classify, append-history, scope-parse, plugin-discover, model-selection, fallback, codex-call |
| Plugin hook registrations | 4 | SessionStart, SessionEnd, Stop (review gate), PostToolUse (quality advisory) |
| Python bin tools | 8 | vibe-check, vibe-report, vibe-badge, vibe-build-docs, vibe-build-reference-md, vibe-build-vocab-data, vibe-build-site-report-pages, vibe-build-case-studies-index |
| Auditor-unit workflows | 24 | 18 `auditor-*` pipeline workflows + deploy-site, site-preview, site-preview-cleanup, site-validate, self-check, pre-release-quality-gate |
| Auditor helper scripts | 30 | full sub-inventory in F10.4 |
| Advisor templates | 6 | north_star_advisor, security_skeptic, clarity_reviewer, simplicity_advocate, deletion_advocate, documentation_critic |
| Workspace-skill resources | 12 | counting rule: non-SKILL.md files only (the 3 SKILL.md files are the workflow skills above; exclusions per the shared AC-1 list — OS junk like .DS_Store ignored) — issue2pr ×8: manifest-schema.json, roamex-manifest.py, watch-pr.sh, profiles/roamex.md, templates/roamex-pr-body.md, examples ×2, ROAMEX.md · refine-proposal ×3: review-rubric.md, codex_review.sh, render_final.sh · runs-stats ×1: generate_runs_stats.py |

**Invocation note (workflow skills, F14 fix):** refine-proposal, issue2pr, and runs-stats ship as **user-invocable plugin skills** — registered in the manifest's `skills` array and invoked by name through the plugin-skill mechanism — **not** as command files, so they are deliberately outside the 26-command inventory. Catalog headings write them in slash form (`/vibe:issue2pr` …) because that is what the user types to invoke the skill; the manifest/count expectation is 26 command files and 22 skills, of which 3 are user-invocable.

Function IDs below: 57 total — Cat 1: 8 · Cat 2: 7 · Cat 3: 8 · Cat 4: 9 · Cat 5: 2 · Cat 6: 4 · Cat 7: 2 · Cat 8: 5 · Cat 9: 8 · Cat 10: 4.

Format per function: **ID · name — description**, then spec (inputs, behavior, outputs, dependencies) and merge notes.

### Category 1 — Setup, Bridge & Lifecycle *(source: cc-suite, merged with nlpm init)*

Synchronizes project configuration across Claude Code, Codex CLI, and Gemini CLI from single sources of truth, and manages the suite's own lifecycle.

#### F1.1 `/vibe:init` — interactive project setup
- **Does:** One command initializes everything: the cross-tool bridge (AGENTS.md as canonical memory, one-line imports into CLAUDE.md/GEMINI.md, `.codex/` config, skills symlink, MCP registrations, gitignore block) *and* the quality baseline (strictness question → score threshold, baseline score snapshot into history), *and* migration of any pre-existing cc-suite/nlpm stores per the §7A matrix.
- **Spec:** No arguments; interactive Q&A via AskUserQuestion: default Codex effort/sandbox and audit depth (`--full`/`--mini` default), score strictness (Relaxed 60 / Standard 70 / Strict 80), skip patterns. Per P9 the model question is **which tier/default to trust, never a version pick-list of pinned IDs** (discovery via F1.5 populates overrides only if the user insists). Writes `.vibe-suite.md`, `AGENTS.md`, import lines, `.codex/config.toml`, `.codex/hooks.json`, `.mcp.json` entries, `.gitignore` block (schema-versioned sentinel), baseline `.claude/vibe-history.json`. All mutation via idempotent scripts with ownership sentinels; provenance file enables restore. Runs each bridge script exactly once (fixes cc-suite's double `bridge_skills.sh` run).
- **Merged from:** cc-suite `init` + nlpm `init` (one setup instead of two).

#### F1.2 `/vibe:doctor` — health check and guided fix
- **Does:** Diagnoses the whole installation: bridge integrity (sentinels, symlinks, pins), Codex **and agy** connectivity, MCP registrations, hook wiring, manifest-vs-disk consistency (via F4.4 pointed at the project), version coherence, mirror staleness (F9.6 hash manifest), knowledge-skill freshness (F8.4 date), and leftover legacy stores (§7A detection rules).
- **Spec:** No arguments. Read-only checks; issues table with severity + auto-fixable flag; offers `/vibe:repair` for fixable items. Subsumes grill's `validate-plugin.sh` checks (frontmatter presence, reference resolution) and cc-suite's `status.sh` + deep checks A–E. Fixes cc-suite W11 (wrong manifest path in cache-freshness check).
- **Merged from:** cc-suite `diagnose`/`doctor` + `status.sh` + grill `validate-plugin.sh`.

#### F1.3 `/vibe:repair` — non-interactive re-run of all bridge scripts
- **Spec:** No arguments, no prompts; idempotent; collects failures and continues; reports per-script outcome. Escalation path from F1.2.
- **From:** cc-suite `repair` (unchanged in design).

#### F1.4 `/vibe:unbridge` — complete teardown
- **Spec:** AskUserQuestion confirm; removes **all** suite-owned artifacts: every sentinel block (`vibe-mcp`, `vibe-claude-mcp`, `vibe-agent:*`), the skills symlinks, `.mcp.json` advisor entries, gitignore block; restores the provenance-backed original CLAUDE.md. Also removes legacy `cc-suite-*` sentinels when the user confirms (migration cleanup, §7A). Leaves user content untouched. **Fixes cc-suite W4** (incomplete teardown) by making the sentinel inventory the single source the script iterates.
- **From:** cc-suite `unbridge`, completed.

#### F1.5 `/vibe:preflight` — engine readiness and model discovery
- **Spec:** No arguments. For **codex**: `codex --version`, auth-mode detection, tiny `codex exec` smoke, model discovery from `~/.codex/models_cache.json` with TTL cache. For **agy** (F2.7): version probe + tiny read-only smoke + default-model report. Zero hardcoded model names (P9). Output: per-engine availability + model list consumed by model-selection (F9.4).
- **From:** cc-suite `preflight` + `codex-preflight.sh`, extended to the agy lane.

#### F1.6 `/vibe:bridge` — bridge sub-operations and mirror generation
- **Spec:** `/vibe:bridge [skills|hooks|mcp|mirrors|all]` (default `all`). `skills`: symlink `.agents/skills` → `.claude/skills` + plugin skills. `hooks`: mirror the **project's** configured Claude hooks into `.codex/hooks.json` for the five event types both tools share, skipping Claude-only events (side-file fallback when the user owns the target) — note this concerns the *user project's* hooks, distinct from the four hook registrations the plugin itself ships (§5.0). `mcp`: mirror `.mcp.json` servers into `.codex/config.toml` sentinel block, never copying secrets. `mirrors`: regenerate the `codex/` mirror per F9.6. Absorbs cc-suite's three `bridge-*` commands into one.
- **From:** cc-suite `bridge-skills` + `bridge-hooks` + `bridge-mcp`, extended with mirror generation.

#### F1.7 `/vibe:update` — post-plugin-update refresh
- **Spec:** No arguments. Re-renders bridges, pre-warms npx cache, boot-verifies the pinned reverse-MCP server (`claude-octopus` pin file, real `initialize` handshake), regenerates mirrors. All user-facing strings reference `/vibe:*` names only (fixes cc-suite W2 legacy-name leakage as a suite-wide rule: **no retired command name may appear in any runtime string**; enforced by a doctor check and AC-6).
- **From:** cc-suite `update`.

#### F1.8 `/vibe:config` — view and set suite configuration
- **Spec:** `/vibe:config [--show | --set key=value]`. Surfaces `.vibe-suite.md` (schema documented in vibe-core F9.8, not only in init prose) plus the runtime toggles stored in job-state config: `stop_review_gate on|off` (**ships OFF — opt-in, D3**), gate model (**configurable, never a pinned version — P9;** fixes cc-suite W3), gate fail policy (**fail-open default** — fixes W3's blocked-session-end defect).
- **Merged from:** cc-suite `setup` (gate toggle) + new unified config viewer.

### Category 2 — Codex/agy Delegation & Job Engine *(source: cc-suite; shared infrastructure for Categories 3, 4, 6, 10)*

One dispatch layer through which every external-engine call in the suite flows.

#### F2.1 Codex dispatch engine (`codex-runner`) — infrastructure module
- **Does:** Runs Codex as a killable, deadline-bounded, job-tracked subprocess: foreground (`--wait`, default) or background jobs with 30 s heartbeat, SIGTERM→SIGKILL deadline enforcement, thread-id capture for resume, stdin bound to `/dev/null` (hang fix), one-line JSON result contract `{jobId, status, threadId, rawOutput}`.
- **Spec:** Canonical call: `node scripts/codex-runner.mjs --kind <k> [--model <m>] --effort <e> --sandbox <s> --timeout-ms <t> [--background|--resume <threadId>] -- "<prompt>"`. Per P9, `--model` is an *optional override*: omitted, the CLI runs its configured default model. Sandboxes: `read-only` (default for all reviews/audits) / `workspace-write` / `danger-full-access` (explicit confirmation required). Sandbox changes require a fresh call; resume inherits the original sandbox. The MCP `codex-cli` bridge is registered for interop but is **not** the delegation path. Failures route to the manual-analysis fallback partial (F9.5). **Suite rule:** refine-proposal and issue2pr keep their artifact contracts (`review.md`/`review.json`, `result.md`/`reviewer.json`) but dispatch through this engine's synchronous path rather than each shelling out ad hoc — one place for deadline, quota-signature, and token accounting.
- **From:** cc-suite `codex-runner.mjs` + `scripts/lib/*` (state, job-control, process, workspace, render). The orphaned `render.mjs` becomes the one renderer for F2.5 output (fixes cc-suite W5 in part).

#### F2.2 `/vibe:delegate` — send a plan or task to Codex for implementation
- **Spec:** `<plan-file-or-inline> [--background|--wait]`. Effort/sandbox via F9.4 selection (model = tool default unless overridden, P9); `danger-full-access` gated by confirmation; verify step after completion. Provenance disclosure (which AI authored the plan) prepended per the anti-sycophancy rule.
- **From:** cc-suite `implement` (renamed; "implement" collides with the reverse-delegation skill vocabulary — rename confirmed by D1).

#### F2.3 `/vibe:bug-analyze` — root-cause analysis via Codex
- **Spec:** `<bug description> [--background|--wait]`. Recon via Grep/Glob first (cheap, in-session), then per-file Codex analysis; RCA report output.
- **From:** cc-suite `bug-analyze`.

#### F2.4 `/vibe:continue` — continue a prior Codex thread
- **Spec:** `<threadId> <follow-up>`. Runner `--resume`; inherits original sandbox.
- **From:** cc-suite `continue`.

#### F2.5 `/vibe:jobs` — job management (status, result, cancel)
- **Spec:** `/vibe:jobs [status [<job-id>] [--all] [--json] | result <job-id> | cancel [<job-id>]]` (default `status`). Uses the existing-but-unwired `resolveResultJob`/`resolveCancelableJob` helpers and `render.mjs` renderers; documents the **real** storage path (`<stateDir>/jobs/<jobId>.json`) — fixes cc-suite W13 (nonexistent documented path) and W5 (orphaned helpers). Node snippets avoid top-level await under the declared Node floor (fixes W7). Covers agy jobs too (F2.7 registers into the same job store).
- **Merged from:** cc-suite `status` + `result` + `cancel` (rename to `jobs` confirmed by D1).

#### F2.6 Stop-review gate — opt-in hook
- **Spec:** Stop hook (900 s timeout), **shipped disabled — opt-in via `/vibe:config` (D3)**: before Claude may end its turn, an adversarial Codex review of the session's **diff** (not the assistant's self-summary — fixes cc-suite W10) answers `ALLOW:`/`BLOCK:`. Model comes from config with the backend default as the default (P9; fixes W3 hardcoded `codex-mini`); infra failure **fails open** with a warning (fixes W3 blocking). SessionStart/SessionEnd lifecycle hooks (env export, stale-registration migration, job cleanup) ship alongside.
- **From:** cc-suite `stop-review-gate-hook.mjs` + `session-lifecycle-hook.mjs`, repaired.

#### F2.7 agy dispatch runner (`agy-runner`) — the audit engine lane *(new, owner-directed D5)*
- **Does:** Gives the suite a third external-engine lane: headless, read-only dispatch to the **agy CLI (Gemini)**, so audit-class commands can run on a distinct model family (P8) — Claude works, Codex reviews, agy audits. Shipped as **planned work behind a contract gate**: the adapter becomes the audit default only after its CLI contract is confirmed.
- **Spec:** `scripts/agy-runner.mjs`, mirroring F2.1's contract surface: prompt over stdin, read-only execution, deadline enforcement, one-line JSON result `{jobId, status, rawOutput}`, jobs registered into the same F2.5 store. No model flag by default (the CLI's configured default model runs, P9); `--model` passthrough for explicit overrides. Pre-flight probe lives in F1.5. **Contract gate (the F11 fix):** no source repo contains an existing agy runner or headless dispatch contract (cc-suite only scaffolds `.gemini` config paths), so the adapter's **definition of done** is an explicit contract confirmation — the exact supported command and binary name, stdin/stdout transport, read-only enforcement mechanism, timeout/kill behavior, and failure/quota signatures (open question Q5) — verified by a dedicated fixture (AC-9). **Until the gate passes, no audit command defaults to agy** (`--engine agy` before then errors with a pointer to the gate status); after it passes, the P8 default flips. **Fallback chain once live (per F9.5):** agy unavailable/empty → codex with a diagnostic header; codex also unavailable → manual in-session analysis. v1 scope is deliberately minimal: no thread resume, no background heartbeat (audit calls are bounded one-shots); those remain codex-lane features.
- **From:** new module (the one net-new capability in this merge, §8 note); pattern copied from F2.1.

### Category 3 — Code Review & Interrogation *(source: grill, absorbing cc-suite `audit`)*

Whole-codebase, multi-angle review with a recon-first shared-context fan-out.

#### F3.1 `/vibe:roast` — code interrogation orchestrator
- **Does:** Runs the full interrogation: recon survey → style/add-on selection → parallel specialist fan-out → synthesis with dedup → executive summary → report + phased fixing plan.
- **Spec:** `[target-path] [--engine claude|codex|agy|both] [--style 1-6] [--addons ...] [--output <path>]`.
  - `--engine claude` (default): grill's in-session flow — recon agent first; its survey is injected into each specialist prompt ("do not re-discover"); 4 specialists (styles 1–4) or 5 (styles 5–6, adds edge-cases); merge by parsing `## [Agent: <name>] Findings` headers, dedup keeping strongest evidence.
  - `--engine codex`: the cc-suite path — the same nine audit dimensions cc-suite's `/audit` defines (its `--full` set; `--mini` = its 5-dimension fast set) dispatched to Codex via F2.1 (batching >20 files into groups of 10), rendered in the suite finding contract. (Rename `audit` → `roast --engine codex` confirmed by D1.)
  - `--engine agy`: the same nine dimensions dispatched via F2.7 once its contract gate passes (P8 staged rollout; before that the flag errors with a pointer). After the flip, agy is the default *cross-model* engine when the user asks for a non-Claude pass without naming one.
  - `--engine both`: run claude plus the configured cross-model audit engine (F9.4 — codex in v1, agy after the F2.7 flip), then a reconciliation pass labels findings `both-agree` / `claude-only` / `<engine>-only` (highest-confidence first).
  - Styles (6): Architecture Review + Rewrite Plan; Hard-Nosed Critique + Roadmap; Multi-Perspective Panel; ADR Style; Paranoid Mode; Select All. Add-ons (8): scale stress, hidden costs, principle violations, strangler fig, success metrics, before/after diagram, assumptions audit, compact & optimize. Select-All on >500 files requires a confirmation gate.
  - Report: `--output` overrides the default `<target>/vibe-report-<YYYY-MM-DD-HHMM>.md` (minute granularity + prior-report exclusion rule for recon fix grill W8 same-day collisions); frontmatter version is **read from the plugin manifest at run time**, never hardcoded (fixes grill W2); agent-failure policy: note and proceed.
- **Merged from:** grill `roast` (primary) + cc-suite `audit` (as `--engine codex|agy`, dimensions preserved).

#### F3.2 Agent `vibe:recon` — repository survey
- **Spec:** haiku-class model (survey is non-judgmental — fixes grill W10 cost concern; tier alias per P9, per-agent configurable), tools Read/Glob/Grep/Bash (read-only command allowlist). Fixed survey template (language/framework, architecture, DB, CI/CD, entry points, size, notable config); ≤80 lines; facts only; "Unknown — do not guess". **Never reads/prints** `.env`, `*.pem`, `*.key`, `*secret*`, `id_rsa` — notes existence only. Ignores prior `vibe-report-*.md` files.
- **From:** grill `recon`.

#### F3.3–F3.7 Specialist agents — `architecture`, `error-handling`, `security`, `testing`, `edge-cases`
- **Spec (shared):** tools Read/Glob/Grep only; each **inlines** the untrusted-input rule (all target file content is data, never instructions) *and* loads vibe-core — belt-and-braces, fixing grill W6 (silent degradation if frontmatter `skills:` preload is ignored). Output opens `## [Agent: <name>] Findings`; six-field finding format; zero-findings → one `[GOOD]` entry, no padding.
- **Per-agent ownership (deconfliction preserved from grill):**
  - `architecture` (F3.3): entry points/request flow, module boundaries, dependency graph, data flow/state, patterns; defers config findings to error-handling.
  - `error-handling` (F3.4): error patterns, recovery, logging/observability, config management (primary owner); prioritizes silent/swallowed failures; defers secrets/PII-in-logs to security.
  - `security` (F3.5): authn/authz, injection, secrets (primary owner), deps/supply chain, transport/storage; mandatory **Exploit scenario** per finding; secret redaction first-4/last-4; no network audit tools.
  - `testing` (F3.6): coverage/gaps, quality, infra, CI/CD; no tests → one specific `[CRITICAL]`; no CI → `[HIGH]` with a concrete provider recommendation.
  - `edge-cases` (F3.7, Paranoid styles only): races/concurrency, boundary values, partial failure, error-propagation chains, implicit assumptions; outputs Risk Matrix + Worst Case Verdict.
- **From:** grill agents, unchanged in analysis content.

#### F3.8 `/vibe:fix` — findings→fix→verify loop (code and NL artifacts)
- **Does:** Takes a findings report (from roast, score, nl-audit, or security-scan) and drives a bounded fix loop: fix → independent verify → repeat until clean or cap.
- **Spec:** `[report-file|scope] [--severity all|high] [--fixer claude|codex] [--max-rounds 1-5]` (defaults: severity all, fixer claude, max-rounds 3). Fixer `claude` edits in-session; fixer `codex` runs at `workspace-write` via F2.1. Verification is always a **fresh read-only** call by a non-fixing engine (cross-model verify, per P4/P8 — codex verifies claude's fixes; claude verifies codex's), with per-issue verdicts `FIXED | NOT FIXED | PARTIAL | REGRESSED`. NL-artifact reports additionally re-score via F4.2 and report deltas; the mechanical auto-fix table from nlpm `fix` (rename `tools`→`allowed-tools`, add `user-invocable: false`, insert headings, derive missing names, add `argument-hint`) applies before model-driven fixes.
- **Merged from:** cc-suite `audit-fix` + `verify` + nlpm `fix` — one loop, two target classes.

### Category 4 — NL-Artifact Quality *(sources: nlpm + cc-suite's auditor family, both preserved)*

Lints and audits the markdown "programs" that drive AI agents: skills, agents, commands, rules, hooks, prompts, manifests, memory files, specs, plans, and design docs.

#### F4.1 `/vibe:ls` — NL-artifact inventory
- **Spec:** `[repo-path]` (default cwd). Dispatches the scanner agent; discovery per the shared category patterns (F9.3: A plugin / B project-config / F memory, plus C prompts / D non-plugin agent frameworks / E design docs from cc-suite); per-category file/line/token counts. No scoring.
- **From:** nlpm `ls` + `scanner` agent (haiku-class, Read+Glob), discovery extended with cc-suite's C/D/E categories.

#### F4.2 `/vibe:score` — 100-point deterministic quality scoring
- **Does:** Deterministic subtractive scoring (start 100, fixed penalties per rule R01–R51, floor 0), per artifact type, with a false-positive gauntlet. This is the *lint*: same input → same score.
- **Spec:** `[path] [--changed] [--engine claude|codex|agy|both]`.
  - Default engine `claude`: dispatches `scorer` (sonnet-class; loads scoring/conventions/vocabulary skills) + `vague-scanner` (haiku-class; mechanically counts the 11 vague-quantifier words, −2 each cap −20) in parallel batches of ≤5; deterministic counts win conflicts.
  - `--engine codex|agy`: second opinion **on the same rubric** — the scoring skill + artifact set packaged into a prompt via F2.1/F2.7; same report format, provenance disclosed. Per P8's staged rollout the unnamed cross-model default is codex in v1, agy once F2.7 graduates. (Judgment-based auditing beyond the rubric is F4.9's job, not a score mode.)
  - `--engine both`: claude plus the configured cross-model engine; disagreements listed explicitly.
  - Config: threshold + rule overrides (`suppress`, `enabled`, `max_penalty`, per-rule `threshold`) from `.vibe-suite.md`. Malformed YAML → −25 and continue; empty file → 0; unreadable → skip.
  - Output: per-file findings table `| # | Sev | Rule | Line | Issue | Penalty | Fix |`, score bands (90+ Excellent … <60 Rewrite), snapshot appended to `.claude/vibe-history.json` (scope-tagged, atomic, deduped).
  - Scorer safeguards inherited verbatim: "Do Not Invent Findings" gauntlet (rubric → schema do-not-penalize list → path-scope/tier → intent → tool-catalog → confidence), tier classifier (open-spec Tier 1/1.5 vs Tier 2 Claude/Codex/Antigravity, per-artifact in multi-tool repos).
- **From:** nlpm `score` + `scorer` + `vague-scanner`.

#### F4.3 `/vibe:check` — cross-component consistency
- **Spec:** `[path]`; requires ≥2 artifacts. Checker agent (sonnet-class) verifies: reference integrity (command→partial, agent `skills:`→SKILL.md, hook→script, CLAUDE.md listings), orphans, behavioral contradictions, terminology drift, R51 vocabulary drift when enabled. Output: fixed report with Verdict `CLEAN | N issues`.
- **From:** nlpm `check` + `checker`.

#### F4.4 `vibe-check` — deterministic CI validator (Python, stdlib-only)
- **Spec:** `bin/vibe-check [dir] [--json]`; no Claude Code required. Manifest-vs-disk, unregistered skills, frontmatter presence, skill-name/dir match, hook event-name case, monorepo sub-plugin detection, plus new checks: cross-manifest version coherence and mirror-staleness (hash manifest from F9.6). Exit 0 clean / 1 findings / 2 error. Ships pre-commit + GitHub-workflow templates. Also used by F1.2 doctor and the release gate (P7).
- **From:** nlpm `bin/nlpm-check` (renamed), absorbing grill `validate-plugin.sh` (fixes grill W5 and the cc-suite W6 defect class).

#### F4.5 `/vibe:test` — NL-TDD spec runner
- **Spec:** `[spec-path]`. Spec directory: **`.vibe-test/`**; specs in legacy `.nlpm-test/` are also discovered and run (read-compat, no rename forced; new specs are written to `.vibe-test/`). Tester agent evaluates artifacts against specs: frontmatter validity, trigger/non-trigger prediction with confidence, output-format expectations, rule compliance, score-vs-`min_score`. Missing artifact → RED (TDD start state). Batches ≤3. vibe-suite ships its own specs for **all 14** of its agents (closing nlpm's 5-of-8 coverage gap).
- **From:** nlpm `test` + `tester` + testing skill.

#### F4.6 `/vibe:vocab` — vocabulary discipline (init + drift)
- **Spec:** `/vibe:vocab [init|drift] [path]`.
  - `init`: bootstrap a vocabulary skill for a target project — detect layout, run the literary-warrant extractor (Python), write `skills/<plugin>/vocabulary/SKILL.md` + `registry.yaml` stub, print R51 opt-in instructions; refuses overwrite.
  - `drift`: registry-free advisory scan (≥5 artifacts) via the drift-scanner agent (judgment-based clustering, dispositions drift/likely/co-occurrence/ambiguous, cap 20, never penalizes); reads existing registry homonyms to suppress FPs.
- **From:** nlpm `vocab-init` + `vocab-drift` + `vocab-drift-scanner` + vocabulary skill. vibe-suite maintains its **own** registry (P7) — merged vocabulary decisions in this proposal (e.g. "engine", "reviewer backend", "delegate") seed it.

#### F4.7 `/vibe:spec-sync` — tool-convention overlay sync
- **Spec:** `[claude|codex|antigravity|all]`. One spec-researcher agent per overlay (sonnet-class + WebFetch/WebSearch, first-party sources only, tagged gap report FIX/REMOVE/ADD/CONFIRM/RESOLVED with confidence guard); apply with inline correction notes + version bump; propagate via grep sweep; verify via F4.4. Never commits.
- **From:** nlpm `spec-sync` + `spec-researcher`.

#### F4.8 Knowledge-skill library — the rubric and reference corpus
- **Spec:** Carried into vibe-suite as its own skills at functional parity (D7): `rules` (R01–R51 single source of truth; header count corrected), `scoring` (per-type penalty tables + calibration examples + known-FP patterns), `conventions` + `conventions-claude` + `conventions-codex` + `conventions-antigravity` (tiered floor/overlays), `patterns`, `testing`, `security` (see F5), the seven `writing-*`/`orchestration` authoring references, and cc-suite's `agent-design`. **Dedup rule:** cc-suite's `claude-code-conventions` and nlpm's `conventions-claude` cover the same ground — merged into one skill, refreshed by F8.4. The exemplar-citation links from the rules skill into the auditor data directory become **generated at build time** by the citation tool (F10.2) against the migrated data branch, so the skill file itself carries no hard-coded relative links into ops data (addresses nlpm S7 while keeping the citations the auditor loop produces).
- **From:** nlpm skills (17) + cc-suite knowledge skills (2), minus one merged duplicate = 18, + vibe-core (F9.1–F9.5) = 19.

#### F4.9 `/vibe:nl-audit` — cross-model NL-artifact auditor (the cc-suite family, preserved)
- **Does:** Judgment-based, cross-model auditing of NL artifacts — the complement to F4.2's deterministic lint. One typed command preserves all six cc-suite auditors' behavior: their broader discovery, their per-type dimension sets, their `--full/--mini` depth split, and their findings-table output contract. The cross-model engine follows P8's staged rollout: **codex in v1**, **agy** once the F2.7 contract gate passes (`--engine` forces either).
- **Spec:** `/vibe:nl-audit [--type skill|command|agent|rules|plugin|repo] [path|scope] [--full|--mini] [--engine agy|codex] [--background|--wait]`. Every type carries its source auditor's **complete seven-dimension set** — the per-dimension check bullets and severity rules carry over at functional parity from the source command files; the lists below are the normative dimension names with their mini/full membership:
  - `--type skill` *(was audit-skill)*: D0 Frontmatter Schema (mini+full) · D1 Description Quality (mini+full) · D2 Content Structure (mini+full) · D3 Context Efficiency (mini+full) · D4 Scope Boundaries (full) · D5 Cross-References & Integration (full) · D6 Actionability (full).
  - `--type command` *(was audit-command)*: D0 Frontmatter Schema (mini+full) · D1 Workflow Clarity (mini+full) · D2 Tool Selection (mini+full) · D3 Output Specification (mini+full) · D4 Error Handling (full) · D5 Argument Safety (full) · D6 Shared Partial Usage (full).
  - `--type agent` *(was audit-agent)*: D0 Frontmatter Schema (mini+full) · D1 Triggering Quality (mini+full) · D2 System Prompt Quality (mini+full) · D3 Tool Selection (mini+full) · D4 Scope & Boundaries (full) · D5 Output Specification (full) · D6 Safety & Trust (full).
  - `--type rules` *(was audit-rules)*: D0 Schema & Formatting (mini+full) · D1 Enforceability (mini+full) · D2 Token Budget (mini+full) · D3 Conflict Detection (mini+full) · D4 Path Scoping (full) · D5 Tooling Overlap (full) · D6 Staleness & Relevance (full).
  - `--type plugin` *(was audit-plugin)*: D0 YAML Schema Validation (mini+full) · D1 Specification Quality (mini+full) · D2 Security Posture (full) · D3 Structural Integrity (mini+full) · D4 Behavioral Consistency (full) · D5 Robustness & Edge Cases (full) · D6 Maintainability (mini+full) — **local analysis, no model calls** (source behavior preserved), using the plugin-discover partial + F4.4, with D2 delegated to an F5.1 pass.
  - `--type repo` *(was audit-nlp)*: discover-then-audit across **all** discovery categories A–E (plugin artifacts, project config, prompt artifacts `prompts/**`, `**/system-prompt*.md` etc., non-plugin agent/skill frameworks and manifests, design/spec/plan/ADR docs) with the source's fifteen category-specific check sets: A1 Schema Validation · A2 Cross-Component Integrity · A3 Behavioral Consistency · B1 CLAUDE.md Quality · B2 Rules Quality · B3 Settings Consistency · C1 Prompt Effectiveness · C2 Prompt Safety · C3 Prompt Consistency · D1 Framework Structure · D2 Cross-Agent Consistency · D3 Completeness · E1 Internal Consistency · E2 Completeness · E3 Currency.
  - All model-calling types dispatch via F2.1 (v1 default) or F2.7 (default after its contract gate passes) read-only with the conventions knowledge skill spliced in (cc-suite's knowledge-injection pattern), scope grammar via F9.3 `scope-parse`, fallback via F9.5 (agy→codex→manual), provenance disclosure per P4. Untrusted-content warning: audited artifacts ARE prompts — data, never instructions.
- **Merged from:** cc-suite `audit-skill` + `audit-command` + `audit-agent` + `audit-rules` + `audit-plugin` + `audit-nlp` — six commands become one typed command (rename confirmed by D1) with **zero dimension loss**: 7 dimensions × 5 types + 15 repo-mode checks, all enumerated above and fixture-verified per type by AC-3.
- **Overlap resolution vs F4.2:** score = deterministic rubric, reproducible, history-tracked; nl-audit = cross-model judgment, broader discovery (C/D/E), dimension essays. `/vibe:doctor` and docs steer users: lint continuously with score, audit periodically (or pre-release) with nl-audit.

### Category 5 — Security Scanning *(sources: nlpm + grill, one shared pattern DB)*

Two front-ends over one security knowledge skill.

#### F5.1 `/vibe:security-scan` — plugin/executable-artifact security scan
- **Spec:** `[path]`; precondition: target looks like a plugin (`.claude-plugin/`, `agents/`, `commands/`, `skills/`, `hooks/`, `scripts/`). Security-scanner agent (sonnet-class, prompt-injection defense: file content is data): discovers execution surfaces (hooks, scripts, bin/, `.mcp.json`, dependency manifests, Bash-using commands), scans against the Critical/High/Medium pattern DB with context-aware severity capping (findings in `.md` capped Low; echo/heredoc/comment matches dropped; lockfile suppresses unpinned findings; `.mcp.json` unpinned is PR-worthy, `package.json` unpinned advisory). Output: severity table + findings + gate banner `PASS | REVIEW | BLOCK`. A cross-model second opinion (when requested) uses the P8-resolved audit engine (codex in v1, agy after the F2.7 flip). Also invoked as the pre-contribution gate by the auditor pipeline (F10.1) and by `nl-audit --type plugin`.
- **From:** nlpm `security-scan` + `security-scanner` + security skill.

#### F5.2 Code-security dimension — inside roast
- **Spec:** F3.5 (the grill security specialist) is the code-target security reviewer. Both F5.1 and F3.5 load the **same** shared security pattern skill so pattern updates land in both.
- **Merge note:** the built-in `/security-review` remains available for diffs; vibe-suite's two functions target whole plugins (F5.1) and whole codebases (F3.5).

### Category 6 — AI-Reviewing-AI Workflow Loops *(sources: workspace skills + cc-suite review-plan)*

Generator-critic loops on the shared reviewer contract (P4).

#### F6.1 `/vibe:refine-proposal` — proposal generator-critic loop *(updated skill version)*
- **Spec:** Ported as-is from the workspace skill's **current version** (it is already generic): free-text/`--file` requirement → frozen input → baseline plan → bounded Codex review rounds (`--review-mode none|single|full`, `--max-review-rounds 1..5` default 3, `--stop-severity blocker|major|minor` default major) → per-round revisions with stable finding IDs and the closure machine → rendered FINAL.html (self-contained, pandoc, metadata banner with UTC+8 timestamp + word/char counts; markdown-pointer fallback when pandoc is absent) + summary + changelog under `docs/discussion/<date>-<slug>/`. Supports `iterate` (config inheritance with per-flag override), `resume`, `list`, `--dry-run`, `--checkpoint`, and the **self-review fallback** (`--allow-self-review`: when codex is unavailable the worker plays reviewer; every such round records `reviewer:"self"` and summary.md flags it). **Bilingual output (the updated skill's addition):** `--second-language "<lang>"` makes finalize append a full translation after the English (English always first) into `final-bilingual.md`, which becomes the FINAL.html render source; one Codex fidelity pass over the translation runs by default (`--review-translation`/`--no-review-translation`; simpler contract — all findings applied as fixes, no closure machine; degrades to self-review or a recorded skip when codex is unavailable, never aborts finalize). State schema v6 (`second_language`, `review_translation`, `translation_review`, per-round `reviewer`, `carried_forward`). Reviewer model default = the backend's default model (P9); same-model-family refusal.
- **Merge note — absorbs cc-suite `review-plan`:** "send a plan to Codex for a one-shot architectural review" ≡ `/vibe:refine-proposal --file <plan> --review-mode single`. Retired as a separate command; the migration table documents the equivalence; AC-3 verifies it on a fixture.

#### F6.2 `/vibe:issue2pr` — GitHub issue → reviewed PR pipeline, **standardized** (§11)
- **Spec:** The nine-step three-phase pipeline (Analyze 1–3 → Plan 4–6 → Execute 7–9; each Worker → Reviewer → Update+Verify with bounded loop, default 2, configurable 2–5), review modes `none|single|full`, scenarios (auto/new-feature/bug-fix/iterate/spike/docs/no-go), chain mode (2–10 issues serial with auto-advance, PR watcher, babysit rounds, optional `--auto-merge`), manifest mode, resume/iterate/list, durable `runs/<run-id>/` state, reviewer backends **`codex` and `copilot-cli`** with the source skill's full backend contract matrix (dispatch, read-only guard, output capture, token accounting, pre-flight, quota signature) — both backends carried as specified in the source. Per P9, the reviewer model default becomes *the resolved backend's default model* (the source's pinned `gpt-5.5` default and its hardcoded fallback chain are replaced by backend model discovery); the worker≠reviewer family invariant stays.
- **Standardization (per the §11 analysis — the structural change):** the SKILL.md splits into a **project-neutral core** plus a **profile contract**. All project-bound facts move to `profiles/<project>.md` (schema in §11.3): repo id/path, base branch, source-system driver + issue-id pattern + URL regex, branch template, PR-body template, build/test gate commands *and* free-form gate mechanics, TDD policy, anti-patterns, reviewer mental-model references, per-step category extensions, scenario keyword overrides. A run resolves its profile from `.vibe-suite.md` (`issue2pr_profile:`) or `--profile <name>`; **no usable profile ships (D2)** — a run without a resolvable profile refuses with a pointer to `profile init` (F6.4). The Roamex profile is retained only as a **reference example** under `examples/profiles/roamex.md` (it doubles as the conformance case in AC-3). The source's leftover `crates_confirmed` field is renamed `areas_confirmed` with a schema-version bump and read-compat for old runs.
- **From:** workspace `issue2pr` skill.

#### F6.3 Shared reviewer contract — reference module (vibe-core section)
- **Spec:** One reference defines, for all loops (F6.1, F6.2, F3.8 verify, F2.6 gate, F10.1 audit/contribute gates): reviewer backend enum + contract matrix (from F6.2), same-model-family refusal (+ `--allow-self-review` escape and the recorded self-review fallback), review-mode semantics `none|single|full`, bounded-round configuration names (`max_review_rounds`), fenced-YAML verdict parsing (last block only, one re-ask, degrade-and-record never abort), the finding-closure state machine (open → fixed/declined → accepted_decline/challenged_once → final_decline), and the P9 model-resolution rule (backend default; overrides never persisted into shipped artifacts).
- **Merged from:** refine-proposal + issue2pr (their contracts are already near-identical) + cc-suite's provenance/anti-sycophancy rules.

#### F6.4 issue2pr profile scaffolder — `profile init` *(new, owner-directed D2)*
- **Does:** Helps a user create their **own** project profile once their GitHub repo is finalized — the shipped replacement for bundled profiles.
- **Spec:** `/vibe:issue2pr profile init [<repo-path>] [--id <project-id>]` (also offered interactively when a run finds no profile). **Precondition — "repo finalized":** the path exists, is a git repo with a resolvable default branch and an `origin` remote on github.com; otherwise refuse with what's missing (the helper is for finalized repos, matching the owner's intent). **Auto-detect (scripted, read-only):** repo id + path, default branch, GitHub owner/repo from `origin` → issue-URL regex + `gh --repo` value, authenticated login (`gh api user`) → branch template, candidate build/test gates probed from repo files (`package.json` scripts, `Makefile`, `Cargo.toml`, `pom.xml`, `go.mod`, CI workflow steps), test-framework hints. **Interview (AskUserQuestion, only what can't be detected):** issue-id shorthand (e.g. `roam-N`-style prefix or bare numbers), TDD policy, review-iteration cap, anti-pattern/house-rule sources (paths to ADRs, CONTRIBUTING, design docs → become reviewer mental-model references), scenario keyword overrides, reviewer backend. **Output:** `profiles/<id>.md` conforming to the §11.3 contract + `issue2pr_profile: <id>` written into `.vibe-suite.md`. **Validation:** profile-lint (required fields present, paths/refs resolve, regexes compile) + a `gh issue list -L 1` smoke against the repo; refuses to overwrite an existing profile without `--force`.
- **From:** new module (implements the owner's D2 answer); detection patterns reuse F1.1's probing discipline.

### Category 7 — Advisor Personas *(source: cc-suite)*

#### F7.1 `/vibe:advisor` — manage consultative advisor agents
- **Spec:** `/vibe:advisor [add [preset|--custom] | list | remove <name>]`. Advisors are value-over-rules personas registered as MCP servers in both `.mcp.json` and `.codex/config.toml` (dual registration via bridge script, sentinel-owned, timeline dirs). Each declares `tool_name`, `allowed_tools`, `max_turns`, `max_budget_usd`.
- **From:** cc-suite `add-agent` + `list-agents` + `remove-agent`.

#### F7.2 Persona template pack — six shipped advisors
- **Spec:** `north_star_advisor` (opus-class, priorities/scope-drift), `security_skeptic` (opus-class, adversarial security), `clarity_reviewer` (sonnet-class), `simplicity_advocate` (sonnet-class), `deletion_advocate` (sonnet-class), `documentation_critic` (sonnet-class) — carried with their tool scopes, turn caps, and budgets (tier aliases per P9).
- **Merge note:** grill's specialists and the advisors serve different interaction models (batch fan-out report vs on-demand consultation) — both kept; the agent-design skill (F4.8) documents when to use which.

### Category 8 — Reporting, Trend & Knowledge *(source: nlpm + cc-suite + workspace runs-stats)*

#### F8.1 `/vibe:trend` — score trends over time
- **Spec:** `[path]`. Re-scores via F4.2, filters history to the matching scope (apples-to-apples), per-file deltas (improved/degraded/unchanged/new), N-snapshot trajectory; appends snapshot. Missing history → baseline run; malformed → warn + treat empty. Reads `.claude/vibe-history.json` (migrated per §7A).
- **From:** nlpm `trend`.

#### F8.2 `/vibe:report` — self-contained HTML quality report
- **Spec:** `[path]`. Fresh score + check + vocab-drift (when ≥5 artifacts) + history → JSON blob → Python renderer → `.claude/vibe-reports/index.html` + timestamped archive; vendored graph library, file://-openable, no network. Data blob goes to the session scratchpad or `mktemp`, not a hardcoded `/tmp` path (fixes nlpm S12 concurrency collision).
- **From:** nlpm `report` + `bin/nlpm-report` (+ `vibe-build-docs` for the framework-reference pages).

#### F8.3 `vibe-badge` — shields.io badge generator
- **Spec:** `bin/vibe-badge`; endpoint JSON + optional attestation sidecar; refreshed by the self-check workflow (F10.3).
- **From:** nlpm `bin/nlpm-badge`.

#### F8.4 `/vibe:refresh-knowledge` — refresh the conventions skill from official docs
- **Spec:** `[--check|--update]`; requires the context7 MCP (stops with install instructions if absent); updates the merged conventions skill (F4.8) with a freshness date surfaced by F1.2 doctor (staleness becomes a visible doctor warning, fixing the silent-staleness gap).
- **From:** cc-suite `refresh-knowledge`. Complementary to F4.7 (spec-sync is research-agent-driven and covers all three tool overlays; refresh-knowledge is the fast context7 path for the Claude overlay — doctor recommends whichever is staler).

#### F8.5 `/vibe:runs-stats` — time-bucketed statistics over issue2pr runs *(new source: workspace skill)*
- **Does:** Static-HTML dashboards over everything under `runs/`, bucketed by **day / week / month / all-time**, so issue2pr activity, review quality, and token/cost usage are visible by just opening files. The measurement companion to F6.2.
- **Spec:** Ported from the workspace skill: one stdlib-only Python generator (`generate_runs_stats.py` — `zoneinfo`, no pip/venv) writes `runs/_reports/` (`index.html`, `all-time.html`, `history.json`, plus `day/ week/ month/` pages for periods that have runs). **Freeze/signature model carried intact:** current buckets + all-time regenerate live; a past bucket is refreshed once when its run-set signature changed, then freezes (❄ archived banner); `--force-regenerate` / `--period <id>` for surgical rebuilds; `history.json` records a `config_key` (`tz`, include flags) and refuses to merge mismatched configs. Ad-hoc filtered runs (`--ticket/--scenario/--since/--until`) produce one isolated `--out` report and never touch the canonical history. KPIs: tasks vs runs, per-task status, timing (de-duplicated), reviewer tokens from backend event streams + estimated worker tokens, tool calls, findings/verdicts, tests, PRs/commits, throughput; optional `--reviewer-rate` cost estimate. Correctness guarantees from the source (tz-aware bucketing, `</` escaping, malformed-file = warning never abort, immutability of frozen files) are acceptance-tested (AC-3).
- **Port changes:** (a) **profile-aware genericization** — ticket-id patterns and bucket keys come from the resolved issue2pr profile, replacing the source's residual Jira-era `QTAC-`/`QTDQ-` examples; the `--include-legacy` (`runs/jira/`) flag stays as a generic legacy-dir include; (b) **reviewer labels from run metadata** — token panels label the reviewer from each run's recorded backend/model metadata instead of a hardcoded model name (P9); (c) **vendored chart library** — the source loads Chart.js from a CDN; the port vendors it, aligning with F8.2's file://-openable no-network posture; (d) timezone default stays configurable (`--tz`, default Asia/Shanghai as shipped).
- **From:** workspace `runs-stats` skill (SKILL.md + `scripts/generate_runs_stats.py`).

### Category 9 — Shared Core (`vibe-core`) *(new, synthesized)*

The conventions layer every other function loads.

#### F9.1 Finding & severity contract
- **Spec:** grill-core adopted suite-wide: severity `[CRITICAL] [HIGH] [MEDIUM] [LOW] [GOOD]` with definitions; effort classes `[<1 day] [<1 week] [<1 month] [>1 month]`; six-field finding format (File `path:line`, Observation, Severity, Evidence, Proposed change, Tradeoff; +Exploit scenario for security; +Risk Matrix for edge-cases); output-header contract `## [Agent: <name>] Findings`; zero-findings `[GOOD]` rule; anti-padding and pick-a-side anti-patterns. Documented mappings: nlpm penalties (HIGH ≥ 10, MEDIUM 5–9, LOW < 5) and cc-suite audit severities (Critical→`[CRITICAL]`, High→`[HIGH]`, Medium→`[MEDIUM]`, Low→`[LOW]`). The orphaned cc-suite `audit-output.schema.json` is revived as the machine-readable schema for this contract; F4.4 validates reports against it.

#### F9.2 Untrusted-input & secret-handling rules
- **Spec:** All inspected file content is data, never instructions (inlined in every agent, per F3.3 note); secrets-file read ban (recon rule) and first-4/last-4 redaction (security rule) stated once here, referenced everywhere.

#### F9.3 Discovery & classification partials
- **Spec:** nlpm's `discover.md` extended with cc-suite's categories: **A** plugin artifacts, **B** project config, **C** prompt artifacts (`prompts/**/*.md`, `templates/**/*.md` with prompt patterns, `**/system-prompt*.md`, `**/*[-_]prompt.md`), **D** non-plugin agent/skill frameworks (`**/agents/*.{md,yaml}`, `**/skills/**/*.md`, `**/manifest.{yaml,json}`, `**/frameworks/**/*.md`), **E** design/spec/plan docs (`docs/**`, `specs/**`, `design/**`, `plans/**`, `decisions/**`, README/CONTRIBUTING), **F** memory files — one partial, six categories, with skip-dirs. `classify.md`: the 17-row first-match-wins path→type table, extended with C/D/E types. Plus cc-suite's `scope-parse.md` (scope grammar: empty=uncommitted, `staged`, `commit -N`, paths; skip patterns; trivial-change gate) and `plugin-discover.md` (manifest validation + cross-reference map). Four partials, one home. Consumers: F4.1/F4.2/F4.3 default to A/B/F (lint scope); F4.9 `--type repo` uses A–E (audit scope); flags can widen either.

#### F9.4 Model & engine selection partial
- **Spec:** cc-suite's `model-selection.md` generalized per P8/P9: priority = user choice > `.vibe-suite.md` > **tool default** (never a shipped pin); Codex/agy models discovered dynamically (F1.5), never hardcoded; suite-wide vocabulary fixed here: **engine** = who performs primary analysis (`claude|codex|agy|both`); **cross_model_audit_engine** = the default non-Claude engine for audit-class commands (`codex` in v1; flips to `agy` when F2.7's contract gate passes — configurable); **reviewer backend/model** = the critic in generator-critic loops (default backend `codex`, model = backend default).

#### F9.5 Fallback partial
- **Spec:** cc-suite's `fallback.md` extended to the two-step chain: when the selected engine is unavailable/empty, fall to the next (agy → codex → manual in-session analysis), each hop producing the same-format output with a diagnostic header telling the user what fell back and how to restore it. Referenced by every `--engine codex|agy` path.

#### F9.6 Mirror-sync generator — full specification
- **Source set:** (a) all 19 knowledge skills; (b) the roast orchestrator (as `$vibe-roast`, sequential-dispatch variant); (c) the 6 roast analysis agents (as `$vibe-<name>` skills); (d) the 7 cc-suite reverse-delegation skills (`claude-review`, `claude-plan`, `claude-implement`, `claude-debug`, `audit`, `audit-fix`, `verify` — Codex-side scripts that call Claude via the pinned MCP server).
- **Portability criteria (exclusion list):** an artifact is NOT mirrored if it requires any of: Task subagent dispatch (Codex has no subagents — its orchestrators inline sequential flow instead), AskUserQuestion interaction beyond simple prompts, Claude plugin hooks, or Claude-only MCP tooling. Excluded artifacts are listed in a generated `codex/MIRROR-MANIFEST.json` with a reason each — absence is documented, never silent.
- **Transformation rules:** frontmatter map (`globs` → `metadata.short-description`); header rewrite `## [Agent: X]` → `## [Skill: X]`; `Bash Scope` → `Shell Scope`; skill references `vibe:x` → `$vibe-x`; untrusted-input rule includes `AGENTS.md`; version stamped from the plugin manifest at generation time.
- **Validation:** the generator writes a content-hash manifest; `bin/vibe-check --mirrors` fails when canonical hash ≠ recorded source hash (stale mirror), and runs frontmatter checks on every generated file. F1.2 doctor surfaces staleness.
- **From:** revives cc-suite's orphaned `bridge_commands.sh` as the basis; kills grill W4 and nlpm S3 by construction.

#### F9.7 Advisory quality hook
- **Spec:** PostToolUse hook, matcher `Write|Edit|MultiEdit`, 5 s timeout, fail-open: when the edited path classifies as an NL artifact (F9.3 patterns), emit a one-line "consider `/vibe:score <file>`" reminder on stderr. Never blocks.
- **From:** nlpm `check-artifact.sh`.

#### F9.8 Suite config schema — `.vibe-suite.md`
- **Spec:** One documented schema: engine defaults (`cross_model_audit_engine`, reviewer backend, effort/sandbox/audit-depth — model overrides optional and empty by default, P9), skip patterns, focus instructions, score threshold, rule overrides (incl. R51 enablement + vocabulary skill path), issue2pr profile pointer, gate settings mirror. Supersedes `.cc-suite.md` and `.claude/nlpm.local.md`; `/vibe:init` migrates both per §7A.

### Category 10 — Open-Source Audit & Contribution Pipeline *(source: nlpm auditor unit)*

The self-evolving "health inspector for the Claude Code ecosystem": discovers NL-artifact repos on GitHub, audits them with the Category-4 engine, contributes fixes upstream, tracks outcomes, and feeds what it learns back into the rulebook. This is the capability vibe-suite's founding notes ask for ("browse mainstream open-source projects… identify issues, fix bugs, submit contributions, interact with their communities"). It ships as the `auditor/` unit inside the repo and **deploys in the same repository — `github.com/xinquan568/vibe-suite` (D4)**: the default branch carries the installable plugin + the auditor unit; accumulated **ops data lives on a dedicated `auditor-data` branch** of that repo so plugin installs stay lean (§7A row 9); GitHub Pages serves the public site, **rebranded from nlpm to vibe-suite** (D4). See the deployment prerequisites matrix below.

#### F10.1 Audit-and-contribute pipeline — the six-stage workflow set
- **Does:** Runs the labeled-issue state machine: `audit-candidate` → `audit-ready` → `audit-complete` → `contribute-approved` → `prs-submitted` → `case-study-ready` → `complete`, with a human approval gate between every automated stage.
- **Spec (per stage, from the source workflows, renamed `auditor-*`):**
  - `discover` (weekly cron / manual): trawls GitHub for Claude Code plugin/skill repos (≥500 stars, ≥5 NL artifacts), creates registry issues labeled `audit-candidate`.
  - `audit` (on `audit-ready`): clones the target, runs a **pre-audit security gate** (F5.1 engine), scores every artifact with the Category-4 engine (rules, scoring, conventions skills), writes the diagnosis report to the data branch and the issue.
  - `contribute` (on `contribute-approved`): forks, branches, and submits PRs for **verified bugs only**, each PR traceable to a scored finding; respects the suppressions ledger. **The source's contribution safety gates are normative and carry in full:** concrete contributions only (no drive-by nitpicks); high-confidence sidecar filtering (only findings whose evidence clears the confidence bar become PRs); **first-contact cap of 3 PRs per repo, 5 thereafter**; **max 2 repos contacted per week**; **maintainer-pushback gate** (a prior "no" from the maintainer blocks subsequent automated PRs to that repo — accept "no" gracefully); duplicate-open-PR filter (never re-open what is already proposed); policy/CLA gates with the required repo variables (repos with CLA requirements or no-external-PR policies are skipped with a logged reason, using the `cla-gate-messages` templates); **critical/high security findings take the non-PR responsible-disclosure path**, never a public PR; umbrella-issue backstop when PR quota is exhausted but findings remain.
  - `track` (weekly cron): checks PR outcomes (merged/closed/ignored), updates the registry, promotes fully-merged repos to `case-study-ready`.
  - `case-study` (on `case-study-ready`): gathers evidence, drafts the article, polishes prose, generates the cover, commits to the data branch.
  - `daily-report` (daily cron): pipeline state, PR scorecard, rule-frequency stats, rejection lessons, self-evolution signals.
  - Supporting workflows: `classify`, `batch-processor`, `integration-test`, `render-dashboard`, `repo-report`, `track`-adjacent `suppressions`, and `vocab-drift` (ecosystem-wide drift stats).
- **Security posture (carried as spec requirements, addressing nlpm S6):** minimum-scope PAT with documented rotation; prompt-injection separation for audited third-party content (audited files are data; patch-only contribution surface); the source's AUTH-LEAK mitigation list becomes this function's acceptance checklist rather than a queued TODO.
- **From:** nlpm `auditor/` workflows + registry + prompts + schemas.

#### F10.2 Rulebook feedback loop — self-evolution tooling
- **Does:** Turns audit outcomes into rulebook improvements: exemplar extraction from real findings, automatic citation insertion into the rules skill, rule-refinement proposals, disagreement and suppression ledgers.
- **Spec:** `exemplar` workflow + `cite-exemplars` (inserts/refreshes the exemplar-citation blocks into the rules skill **at build time**, per F4.8's decoupling), `refine-rules` + `rule-review` (propose → human-review rule changes), `docs-diff` (upstream Claude-docs drift detection feeding F4.7), ledgers `disagreements.jsonl`, `vocab-advisories.jsonl`, `suppressions`, and the `validate-rule-ids.py` guard (added after the source's recorded R07 mis-application incident).
- **From:** nlpm auditor feedback workflows + scripts.

#### F10.3 Site & release tooling — build and publish the public face
- **Does:** Renders the audit data into a public VitePress site — **branded vibe-suite (D4)** — and gates releases.
- **Spec (the five build tools + six workflows):** `bin/vibe-build-reference-md` (rules skill → reference pages), `bin/vibe-build-vocab-data` (registry.yaml → noun-verb map JSON), `bin/vibe-build-site-report-pages` (per-repo audit JSON → site pages), `bin/vibe-build-case-studies-index` (chronological index from case-study articles), `bin/vibe-build-docs` (framework-reference HTML, also used by F8.2). Workflows: `deploy-site`, `site-preview`, `site-preview-cleanup`, `site-validate`, `self-check` (badge refresh + `vibe-check` on the suite itself), `pre-release-quality-gate` (the P7 dogfood gate: score ≥ threshold, tests green, mirrors fresh, doc-accuracy checks). **Rebrand tasks (one-time, part of phase 8):** site title/theme/copy, badge endpoints, case-study bylines and index header, dashboard headers, and every user-facing "nlpm" string replaced with vibe-suite; the AC-6 legacy-string grep extends to the site templates.
- **From:** nlpm `bin/nlpm-build-*` + site/release workflows.

#### F10.4 Auditor operational helpers — the 30-script library
- **Does:** The deterministic mechanics the pipeline workflows call — registry integrity, finding fingerprints, contribution plumbing, analytics, and rulebook maintenance. Every script carries over at functional parity (renamed paths); each is listed here so the catalog and the coverage check account for it individually.
- **Spec (grouped by role; all under `auditor/scripts/`):**
  - *Registry & state integrity (6):* `atomic-registry-write.sh` (atomic JSON-validated registry writes) · `three-way-merge-registry.py` (push-conflict merge for `registry/repos.json`) · `resolve-merge-conflicts.sh` (per-file merge strategies for auditor-managed files) · `repair-stale-statuses.py` (repairs statuses corrupted by the pre-fix resolver) · `validate-feedback.sh` (feedback-log integrity gate before any decision) · `log-event.sh` (structured JSON events → `logs/events.jsonl`).
  - *Findings pipeline (6):* `compute-fingerprint.sh` + `compute-vocab-fingerprint.sh` (SCHEMAS-spec fingerprints for finding / vocab-advisory records) · `synthesize-sidecar.py` (legacy `.md` report → findings sidecar) · `backfill-findings.py` + `backfill-pr-fingerprints.py` (ledger backfills) · `diff-findings.py` (re-audit vs original diff).
  - *Contribution plumbing (4):* `commit-via-pr.sh` (auditor changes land via auto-merged PR) · `git-push-with-retry.sh` · `guard-protected-paths.sh` (blocks commits touching core artifacts) · `parse-pr-metadata.py` (metadata block from PR bodies).
  - *Reporting & analytics (5):* `generate-daily-report.py` · `generate-rule-review-body.py` (quarterly rule-review issue) · `rule-health.py` (per-rule health metrics from logs) · `render-dashboard.py` (cross-repo aggregate dashboard) · `render-repo-report.py` (single-repo HTML report).
  - *Rulebook feedback (5):* `propose-rule-citations.py` (real-world example lines for rules) · `prepare-refinement-input.py` (quarterly refinement input) · `validate-rule-ids.py` (scorer-drift guard) · `build-exemplar-gallery.py` (exemplars README) · `docs-diff.py` (cited-doc hash drift, feeds F4.7).
  - *Suppressions, discovery & batch (4):* `parse-suppressions.py` (rule_overrides from configs) · `scan-suppressions.py` (GitHub-wide suppression scan) · `vendor_default_filter.py` (vendor-default exclusion filter for discovery) · `batch-process.py` (the batch-processor phase engine: runs the phased batch state transitions the `auditor-batch-processor` workflow invokes).
  - The auditor's `prompts/` directory, `SCHEMAS.md`, the `README.md` runbook, and the `cla-gate-messages/` message templates carry alongside as the unit's specification documents and helper data (not counted as scripts).
- **From:** nlpm `auditor/scripts/` — all 30 scripts, dispositioned individually in §6.

#### Category-10 deployment prerequisites (required before first external run)

Deployment repo: **`github.com/xinquan568/vibe-suite`** (local clone `codes/vibe-suite`) — the same repo that ships the plugin (D4).

| Prerequisite | Used by | Required? | Fallback if absent |
|---|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` (claude-code-action) | audit, case-study, refine-rules — every model-judged stage | Required | Stages fail with a preflight error naming the secret; no silent skip |
| `PAT_TOKEN` (GitHub PAT, `public_repo` scope) | contribute (fork/branch/PR), track | Required for contribution | Audit-only mode: pipeline stops at `audit-complete`, doctor/README state why |
| `OPENAI_API_KEY` (image API) | case-study cover generation | Optional | Cover step degrades to a templated SVG cover; article still publishes |
| Repo settings on `xinquan568/vibe-suite`: Actions minutes, issues enabled, the seven lifecycle labels created, Pages (site), the `auditor-data` branch created | all workflows | Required | `auditor-integration-test` fails preflight with a checklist |

A preflight validation step (part of `auditor-integration-test`) checks the **required** rows (`CLAUDE_CODE_OAUTH_TOKEN`, `PAT_TOKEN` when contribution is enabled, repo settings incl. the data branch) and the F10.1 security checklist before the first external audit. `OPENAI_API_KEY` is **not** preflight-required — its absence engages the documented cover fallback; AC-8 tests that path separately.

---

## 6. Source-artifact disposition map

Every source function and where it landed. **K** kept (possibly renamed) · **M** merged into another function · **R** retired with replacement noted · **G** now generated · **D** migrated as data.

This section is the human-readable view; the repo ships it as machine-readable **`docs/disposition.yaml`** (source path → disposition → target function ID), which AC-1's coverage check validates against the pinned source trees on every CI run — so an artifact missing from this map fails the build rather than passing silently. Per D7, for the three referenced repos a K/M row means the *capability* is reimplemented at functional parity in vibe-suite's own code — the map is a coverage-planning artifact, not shipped attribution.

### cc-suite (30 commands, 5 partials, 13 skills, 3 hook events, scripts, 6 advisor templates)

| Source artifact | Disp. | vibe-suite home |
|---|---|---|
| `init` | M | F1.1 (merged with nlpm init) |
| `update` | K | F1.7 |
| `repair` | K | F1.3 |
| `diagnose`/`doctor` | M | F1.2 |
| `setup` (gate toggle) | M | F1.8 |
| `preflight` | K | F1.5 |
| `unbridge` | K | F1.4 (completed teardown) |
| `bridge-skills` / `bridge-hooks` / `bridge-mcp` | M | F1.6 subcommands |
| `add-agent` / `list-agents` / `remove-agent` | M | F7.1 |
| `audit` | R | F3.1 `--engine codex|agy` (nine dimensions preserved) |
| `audit-fix`, `verify` | M | F3.8 |
| `audit-skill` / `audit-command` / `audit-agent` / `audit-rules` / `audit-plugin` / `audit-nlp` | M | F4.9 `--type skill|command|agent|rules|plugin|repo` (dimensions, discovery A–E, depth flags, output contract preserved) |
| `implement` | K | F2.2 (renamed `delegate`) |
| `review-plan` | R | F6.1 `--review-mode single` |
| `bug-analyze` | K | F2.3 |
| `continue` | K | F2.4 |
| `status` / `cancel` / `result` | M | F2.5 |
| `refresh-knowledge` | K | F8.4 |
| partials: `codex-call`, `model-selection`, `scope-parse`, `fallback`, `plugin-discover` | K/M | F2.1, F9.4, F9.3, F9.5, F9.3 |
| skills: `claude-review`/`claude-plan`/`claude-implement`/`claude-debug`/`audit`/`audit-fix`/`verify` (Codex-side reverse delegation) | G | regenerated by F9.6 into `codex/` |
| skills: `init`/`diagnose`/`repair` (conversational counterparts) | M | folded into F1.1/F1.2/F1.3 skill descriptions |
| skills: `claude-code-conventions`, `agent-design` | M/K | F4.8 (conventions merged; agent-design kept) |
| skill: `vocabulary` + registry | M | F4.6 (suite registry seeded from both sources) |
| hooks: SessionStart/SessionEnd/Stop gate | K | F2.6 (gate ships opt-in, D3) |
| `codex-runner.mjs` + `lib/*` | K | F2.1 |
| bridge scripts (`init.sh`, `bridge_*.{sh,py}`, `mcp_*.sh`, `ensure_gitignore.sh`, `unbridge.sh`, `status.sh`, `codex-preflight.sh`) | K | F1.x scripts (renamed sentinels `vibe-*`) |
| `bridge_commands.sh` (orphan) | M | F9.6 basis |
| `render.mjs`, `audit-output.schema.json` (orphans) | M | F2.5, F9.1 |
| advisor templates ×6 | K | F7.2 |

### grill-for-claude

| Source artifact | Disp. | vibe-suite home |
|---|---|---|
| `roast` command | K | F3.1 |
| agents: recon, architecture, error-handling, security, testing, edge-cases | K | F3.2–F3.7 |
| `grill-core` skill | M | F9.1/F9.2 (suite-wide contract) |
| Codex mirror (8 skills incl. `$grill-core`, `$grill-roast`) | G | generated by F9.6 |
| `validate-plugin.sh` | M | F4.4 + F1.2 |
| manifests (`.claude-plugin/*`, `.codex-plugin/*`), `nlpm-badge.json` | M | single vibe-suite manifest pair + marketplace entry; badge via F8.3 |
| README/CLAUDE.md/PRIVACY.md | M | one truthful doc set; doc-accuracy checks in the release gate (F10.3) |

### nlpm

| Source artifact | Disp. | vibe-suite home |
|---|---|---|
| `ls` + `scanner` | K | F4.1 |
| `score` + `scorer` + `vague-scanner` | K | F4.2 |
| `fix` | M | F3.8 |
| `check` + `checker` | K | F4.3 |
| `bin/nlpm-check` (+ pre-commit/CI templates) | K | F4.4 |
| `test` + `tester` + `.nlpm-test` specs | K | F4.5 (spec coverage extended to all agents; legacy dir read-compat) |
| `vocab-init` / `vocab-drift` + `vocab-drift-scanner` + vocabulary skill | K | F4.6 |
| `security-scan` + `security-scanner` + security skill | K | F5.1 |
| `trend` | K | F8.1 |
| `report` + `bin/nlpm-report` | K | F8.2 |
| `bin/nlpm-badge` | K | F8.3 |
| `bin/nlpm-build-docs` | K | F10.3 (also serves F8.2) |
| `bin/nlpm-build-reference-md` / `nlpm-build-vocab-data` / `nlpm-build-site-report-pages` / `nlpm-build-case-studies-index` | K | F10.3 |
| `init` | M | F1.1 |
| `spec-sync` + `spec-researcher` | K | F4.7 |
| partials: `discover`, `classify`, `append-history` | K | F9.3, F9.3, F8.1/F4.2 internals |
| knowledge skills ×17 | K/M | F4.8 (conventions-claude merged with cc-suite's) |
| PostToolUse hook + `check-artifact.sh` | K | F9.7 |
| Codex skill mirror (17) | G | generated by F9.6 |
| auditor pipeline workflows (18 `auditor-*`) + prompts + `SCHEMAS.md` + registry | K | F10.1, F10.2 |
| auditor helper scripts ×30 (full list in F10.4: registry/state ×6, findings ×6, contribution ×4, reporting ×5, rulebook ×5, suppressions/discovery/batch ×4) | K | F10.4 (called by F10.1–F10.3) |
| `analysis/scripts/extract-vocabulary.py` + vocabulary-design principles | K | F4.6 |
| site + release workflows (deploy-site, site-preview ×2, site-validate, nlpm-self-check, pre-release-quality-gate) | K | F10.3 (site rebranded to vibe-suite, D4) |
| accumulated ops data: `auditor/reports`, `auditor/exemplars` (95), `auditor/audits`, ledgers, `case-studies/` articles | D | migrated to the `auditor-data` branch of `xinquan568/vibe-suite` (§7A row 9); citations regenerated by F10.2 |
| manifests / marketplace | M | single manifest pair + marketplace entry |

### Workspace skills (every file, not just the SKILL.md)

| Source | Disp. | vibe-suite home |
|---|---|---|
| `refine-proposal/SKILL.md` (**updated version**) | K | F6.1 (direct port incl. `--second-language`/translation pass, `--stop-severity`, self-review fallback, schema v6) |
| `refine-proposal/references/review-rubric.md` | K | F6.1 reference (incl. the translation-review contract); cross-linked from the F6.3 shared reviewer contract |
| `refine-proposal/scripts/codex_review.sh` | K | F6.1 dispatch wrapper, refactored to call F2.1 (artifact contract `review.md`/`review.json` unchanged; default-model dispatch per P9) |
| `refine-proposal/scripts/render_final.sh` | K | F6.1 FINAL.html renderer (pandoc; metadata banner; fallback contract unchanged) |
| `issue2pr/SKILL.md` | K | F6.2 (standardized core per §11; both reviewer backends carried) |
| `issue2pr/manifest-schema.json` | K | F6.2 manifest-mode input schema (`areas_confirmed` rename, versioned) |
| `issue2pr/scripts/roamex-manifest.py` | K | F6.2, genericized to `profile-manifest.py` (profile-parameterized manifest generator/validator) |
| `issue2pr/scripts/watch-pr.sh` | K | F6.2 chain-mode PR watcher |
| `issue2pr/profiles/roamex.md` | K | `examples/profiles/roamex.md` — reference example only, not an active profile (D2); AC-3 conformance case |
| `issue2pr/templates/roamex-pr-body.md` | K | genericized to `templates/pr-body.md` with per-profile override |
| `issue2pr/examples/roamex/` (brief-A-3.md, manifest-A-3.json) | K | F6.2 docs examples |
| `issue2pr/ROAMEX.md` | M | folded into the roamex reference example |
| `runs-stats/SKILL.md` (**new**) | K | F8.5 (profile-aware genericization; vendored chart lib) |
| `runs-stats/scripts/generate_runs_stats.py` | K | F8.5 generator (reviewer labels from run metadata, P9) |

---

## 7. Inherited defects fixed by design

| Defect (source) | Resolution here |
|---|---|
| cc-suite W2 — retired command names in runtime strings | Suite rule + doctor check + AC-6: no retired name in any user-facing string (F1.7) |
| cc-suite W3 — gate hardcodes model, blocks on infra failure | Config-driven model (backend default per P9), fail-open (F2.6, F1.8) |
| cc-suite W4 — incomplete unbridge | Sentinel-inventory-driven teardown (F1.4) |
| cc-suite W5 — orphaned `render.mjs`, `bridge_commands.sh`, schema | All three wired in (F2.5, F9.6, F9.1) |
| cc-suite W6 / grill W2 — version drift across manifests/templates | Version read from manifest at run time; F4.4 checks coherence |
| cc-suite W7 — top-level-await under Node floor | Snippet lint in tests; Node floor declared honestly |
| cc-suite W10 — gate reviews self-summary | Gate reviews the diff (F2.6) |
| cc-suite W13 — nonexistent documented result path | F2.5 documents the real path and uses the resolver helpers |
| grill W1 / nlpm S5 — PRIVACY/doc claims contradict behavior | Doc-accuracy items in the release gate (F10.3): every doc claim about counts, writes, and privacy checked against disk |
| grill W3 / nlpm S1 — stale counts in READMEs | Same release-gate class; §5.0 is the single count source |
| grill W4 / nlpm S3 — hand-maintained mirrors drift | Generated mirrors + staleness check (F9.6) |
| grill W6 — agents unguarded if `skills:` preload ignored | Untrusted-input rule inlined per agent (F3.3–F3.7) |
| grill W8 — same-day report collision; report read as input | Minute-granular filename + prior-report exclusion (F3.1, F3.2) |
| grill W10 — recon pinned to opus | haiku-class recon, per-agent model config (F3.2) |
| nlpm S2 — dangling tracked symlink | Not carried over; F1.2 checks for it in target projects |
| nlpm S4 — "no Python" claim vs python3 use | Prereqs stated honestly: Python 3.11+ required for F4.4/F8.2/F8.3/F8.5/F10.3 |
| nlpm S6 — auditor injection exposure queued-not-applied | Mitigations promoted to F10.1 spec requirements + acceptance checklist |
| nlpm S7 — rules skill hard-coupled to ops data dir | Citations generated at build time against the data branch (F4.8, F10.2) |
| nlpm S12 — hardcoded `/tmp` blob path | Scratchpad/`mktemp` (F8.2) |
| cc-suite W9 / nlpm POSIX assumptions | POSIX-only stated explicitly as a v1 constraint (§8) |
| runs-stats CDN dependency (charts blank offline) | Chart library vendored at port time (F8.5), aligning with F8.2's no-network rule |
| issue2pr / refine-proposal pinned `gpt-5.5` defaults | Replaced by backend-default model resolution (P9, F6.1/F6.2) |

Deferred (recorded, not fixed by this proposal): cc-suite's open questions on `codex exec --quiet` validity and the `models_cache.json` contract stability; the security posture of the external `claude-octopus` npm pin (kept pinned + boot-verified as today).

### 7A. Migration matrix (config, state, and data continuity)

Rules: **the suite never deletes or rewrites a legacy store** — it copies/derives, leaves the original untouched, and warns via doctor; precedence is always *new store wins when both exist*; rollback = delete the new store, originals were never touched. Each row is a fixture-backed acceptance test (AC-5).

| # | Legacy store | New store | Migration action (in `/vibe:init`) | Doctor behavior afterward |
|---|---|---|---|---|
| 1 | `.cc-suite.md` | `.vibe-suite.md` | Read; map fields into the new schema; write new file; original untouched | Warns "legacy config present, ignored" |
| 2 | `.claude/nlpm.local.md` | `.vibe-suite.md` (quality section) | Same-run merge with row 1; conflicting values → ask the user once | Same warning |
| 3 | `.claude/nlpm-history.json` | `.claude/vibe-history.json` | Copy verbatim (schema unchanged) + append a `migrated_from` marker snapshot; original untouched | Trend/report read only the new path |
| 4 | `.claude/nlpm-reports/` | `.claude/vibe-reports/` | No copy (reports are point-in-time artifacts); new reports to new dir | Notes old dir exists |
| 5 | Legacy job state (`codex-toolkit`/cc-suite state dirs) | vibe state dir | Import `config.stopReviewGate` only; jobs are ephemeral, not migrated | Notes stale state dir |
| 6 | cc-suite sentinels (`cc-suite-mcp`, `cc-suite-claude-mcp`, `cc-suite-agent:*`) in `.mcp.json`/`.codex/config.toml` | `vibe-*` sentinels | Detect; offer re-registration under vibe sentinels + removal of old blocks (explicit confirm; provenance-backed) | Warns if legacy sentinels remain |
| 7 | `.nlpm-test/*.spec.md` | `.vibe-test/` | No forced rename; F4.5 reads both, writes new specs to `.vibe-test/` | — |
| 8 | issue2pr `runs/` (+ `runs/_reports/`), refine-proposal `docs/discussion/` | unchanged | None — paths and schemas identical (runs-stats history carries a `config_key`, unaffected) | — |
| 9 | nlpm `auditor/` + `case-studies/` accumulated data | **`auditor-data` branch of `xinquan568/vibe-suite`** (D4 — destination resolved) | `tools/migrate-auditor-data.sh <dest-repo> [--branch auditor-data]`: copies reports, exemplars, audits, ledgers, and articles; verifies by file count + content-hash manifest; idempotent re-run; originals untouched (rollback = delete destination branch). AC-5 tests it against a local bare-repo fixture; execution is now unblocked | Doctor reports "auditor data migration pending" until executed; the default branch carries no ops data |
| 10 | Installed source plugins (cc-suite, nlpm, grill) | vibe-suite | Doctor detects them installed alongside and recommends uninstall (namespace collision table in README) | Warns while both installed |

---

## 8. Non-goals and platform constraints (v1)

1. **Windows:** POSIX-only (symlinks, bash/python3/node), stated in README — carried constraint from all three sources, now explicit.
2. **No new review capabilities beyond the sources, with one owner-directed exception:** the **agy audit lane (F2.7)** implements the owner's division-of-labor target (D5) — staged behind its contract gate — and is the single net-new capability. Everything else remains merge-only: the mirror generator (F9.6), the `--engine both` reconciliation (F3.1/F4.2), the unified config front-end (F1.8/F9.8), the profile scaffolder (F6.4 — a packaging consequence of D2), and the migration layer (§7A) each exist to make the merge coherent, not to add scope.
3. **Marketplace *publication*** (registering vibe-suite in public marketplaces) is a release activity, not a function; the marketplace manifest itself ships (§5.0).

---

## 9. Implementation phasing

| Phase | Delivers | Depends on |
|---|---|---|
| 0 | Repo scaffold in `codes/vibe-suite`, manifest pair, `vibe-core` (F9.1–F9.5, F9.8), config + migration layer (§7A) | — |
| 1 | Job engine + delegation (F2.1–F2.6), agy runner (F2.7), preflight (F1.5) | 0 |
| 2 | Setup/bridge/lifecycle (F1.1–F1.4, F1.6–F1.8) | 0–1 |
| 3 | NL quality engine (F4.1–F4.8), security scan (F5.1), advisory hook (F9.7) | 0 |
| 4 | Cross-model NL auditor (F4.9, staged engine default per P8); code review (F3.1–F3.8) incl. `--engine codex|agy` and unified fix loop | 1, 3 |
| 5 | Workflow loops (F6.1–F6.3), profile contract + scaffolder (F6.4) | 1 |
| 6 | Advisors (F7), reporting/trend/badge (F8.1–F8.3), knowledge refresh (F8.4), runs-stats (F8.5) | 2–3, 5 (F8.5 reads profiles) |
| 7 | Mirror generator (F9.6), generated `codex/`, doc set, release gate wiring | 0–6 |
| 8 | Auditor unit (F10.1–F10.4) live in `xinquan568/vibe-suite`: workflows + helper scripts adapted, site rebranded to vibe-suite, `auditor-data` branch created, data migration executed (§7A row 9) | 3, 4, 7 |

Phases 3 and 1–2 are parallelizable; phase 7 gates the plugin release; phase 8 is deployable independently after 7.

## 10. Acceptance criteria

- **AC-1 Coverage (disk-driven, not self-referential):** a CI script (`tools/coverage-check.py`) performs a **recursive, allowlisted walk** of the three pinned source trees — `commands/**/*.md`, `agents/**/*.md`, `skills/**/SKILL.md` (source skills nest one level deeper, e.g. `skills/cc-suite/agent-design/SKILL.md`, `skills/nlpm/rules/SKILL.md`), `hooks/**`, `scripts/**/*` **including nested libraries (`scripts/lib/*.mjs`) and `auditor/scripts/*`**, `bin/*`, workflows, templates, prompts, schemas, plugin/marketplace manifests (`.claude-plugin/**`, `.codex-plugin/**`), top-level project docs and package manifests (README, CLAUDE.md, PRIVACY.md, package.json), codex-mirror trees (`codex/**`, incl. AGENTS files), and site source files (`site/**`) — every artifact class the §6 disposition map covers — plus the **complete file trees** of the three workspace skills (scripts, references, profiles, templates, examples, schemas — not just the SKILL.md), and asserts each path has a row in `docs/disposition.yaml`. A shared **exclusion list** (`.git`, `__pycache__`, `.DS_Store` and other OS junk, `node_modules`, generated reports, and the §7A row-9 migrated ops data) is the single definition used by both this walk and the §5.0 counting rules. The walk also asserts **expected enumerated counts** per tree (cc-suite 13 skills, nlpm 17 skills, the nested script-library files) so a silently-empty glob fails loudly. An unmapped source artifact fails CI. (This validates against the *sources*, so an omission in §6 is caught, not grandfathered.)
- **AC-2 Determinism:** `bin/vibe-check` exits 0 on the suite itself; re-running any bridge script is a no-op (byte-identical outputs); `/vibe:score` on a fixture file yields the same score across three runs.
- **AC-3 Merge equivalences (fixture-backed, one per retired/absorbed surface):**
  - **One seeded-defect fixture per nl-audit type** under `tests/fixtures/nl-audit/`: `defective-skill/` (10 labeled defect classes: missing name, generic description, >500-line body, broken `references/` link, pseudocode example, domain mixing, redundant content, missing scope note, orphaned registration, vague quantifiers), `defective-command/` (bad frontmatter, muddled workflow, over-broad allowed-tools, missing output spec, unhandled empty input, unsafe `$ARGUMENTS` interpolation, duplicated partial logic), `defective-agent/` (schema errors, mistriggering description, weak system prompt, tool over-provisioning, scope bleed, missing output format, missing untrusted-input guard), `defective-rules/` (unparseable rule, unenforceable vagueness, token bloat, two conflicting rules, missing path scope, rule duplicating a linter, stale reference), `defective-plugin/` (manifest/disk mismatch, spec gaps, risky hook, broken cross-refs, contradictory commands, missing error paths, unmaintainable duplication), `mixed-repo/` (artifacts across all discovery categories A–E incl. a prompt file, a non-plugin agent framework, and a stale design doc). Assert per type: `--full` reports ≥ 75 % of the seeded classes, each attributed to its correct source dimension (D0–D6, or the A–E check set for `repo`); `--mini` reports only mini-member dimensions; the assertions hold on **each** engine lane exercised in CI (agy when available, codex otherwise — the fixture outcome contract is engine-independent). `/vibe:score` on `defective-skill/` additionally yields its exact golden penalty total.
  - `tests/fixtures/sample-repo/` — a small app with seeded issues per roast dimension. Assert (structural, not byte-golden): report contains the frontmatter keys, one `## [Agent: <name>] Findings` section per dispatched agent, a Fixing Plan whose every item traces to a finding, and — under `--engine codex|agy` — all nine cc-suite audit dimensions represented.
  - `tests/fixtures/flawed-plan.md` — a plan with 3 seeded design flaws. Assert: `/vibe:refine-proposal --file ... --review-mode single` produces a parseable verdict block surfacing ≥ 2 of the 3 flaws (the review-plan equivalence).
  - `tests/fixtures/runs-tree/` — a synthetic `runs/` directory (3 tasks, one multi-round, one stopped, one manifest-only undated). Assert: F8.5 produces the golden KPI rollups in `history.json` (task/run counts, status split, token totals), buckets by the fixture timezone correctly (incl. a UTC-boundary run), freezes a past bucket and refreshes it exactly once when a run is added, and an ad-hoc `--ticket` report leaves `history.json` byte-identical.
  - **Profile scaffolder fixture:** a minimal finalized fixture repo (git + `origin` remote stub + package.json scripts). Assert: `profile init` emits a contract-valid profile with the detected fields filled, writes the `.vibe-suite.md` pointer, refuses on a repo with no remote (not finalized), and refuses to overwrite without `--force`.
- **AC-4 Loop bounds:** with a stub reviewer that never returns a clean verdict, every generator-critic loop (F3.8, F6.1, F6.2) stops at its configured cap with the correct terminal status recorded; a malformed verdict triggers exactly one re-ask then degrades and records, never aborts.
- **AC-5 Migration (every §7A row accounted for):** rows 1–7 and 10 — one fixture project each; run `/vibe:init`; assert new store created, legacy store byte-identical to before, precedence honored, doctor emits the specified warning. Row 8 — assert-no-op test (paths and schemas untouched by init). Row 9 — run `tools/migrate-auditor-data.sh` against a local bare-repo fixture with an `auditor-data` branch; assert copy completeness by count + hash manifest, idempotent second run, originals byte-identical.
- **AC-6 No legacy strings:** grep over all shipped runtime-reachable text (commands, skills, agents, scripts, hook output, site templates) for `/cc-suite:`, `/nlpm:`, `/grill:`, `/codex-toolkit:` returns nothing; the site build contains no user-facing "nlpm" branding (D4).
- **AC-7 Quality gate (P7):** `/vibe:score` on the suite ≥ its Strict threshold; `/vibe:test` green with specs covering all 14 agents; `bin/vibe-check --mirrors` green; §5.0 counts match disk (doc-accuracy check).
- **AC-8 Auditor pipeline:** `auditor-integration-test` green **in `xinquan568/vibe-suite`**, including its preflight validation of the **required** prerequisites only (`CLAUDE_CODE_OAUTH_TOKEN` present and scoped; `PAT_TOKEN` present when contribution is enabled; labels created; Pages enabled; `auditor-data` branch present) — `OPENAI_API_KEY` absence must **not** fail preflight; the cover-generation fallback verified separately by running the case-study stage with the key absent (templated SVG cover, article still publishes); **the F10.1 contribution gates each covered by a test case** (first-contact PR cap, weekly repo cap, pushback gate blocks a repo with a prior "no", duplicate-open-PR filter, CLA/no-external-PR skip with logged reason, security finding routed to disclosure not PR, umbrella-issue backstop on quota exhaustion); the F10.1 security checklist (PAT scope, rotation doc, injection separation) fully checked before the first external audit runs.
- **AC-9 Division of labor & no pinned models (P8/P9):** (a) a lint (`tools/model-pin-lint.py`, run in CI) greps all shipped runtime-reachable artifacts for versioned model identifiers (patterns like `gpt-<digit>`, `gemini-<digit>`, `o<digit>-`, dated `claude-*-20*` IDs) and fails on any hit outside docs/CHANGELOG — tier aliases (haiku/sonnet/opus-class) are allowed; (b) the **agy graduation gate**: a contract fixture proves the adapter's headless one-shot call, read-only enforcement, timeout kill, and failure-signature parsing before the P8 default may flip to agy; until it passes, audit commands default to codex and `--engine agy` errors with a pointer. Once flipped: with agy absent at runtime, `/vibe:nl-audit` completes via codex with the F9.5 diagnostic header; with both agy and codex absent, it degrades to the manual fallback — all paths fixture-tested; (c) `/vibe:config --show` displays the resolved engine defaults (cross_model_audit_engine, reviewer backend) so the division of labor is inspectable.

---

## 11. issue2pr standardization analysis *(owner question 5 — fact-based)*

**Verdict: suitable for standardization** — with one structural caveat (source-system drivers) and one honesty caveat (profile quality bounds run quality). The evidence and the plan:

### 11.1 The facts (from the source skill as it exists today)

1. **The machinery is already project-neutral.** Of the source SKILL.md (~1,000 lines), the large majority specifies project-independent machinery: the nine-step/three-phase pipeline, review modes `none|single|full`, severity rules (blocker-stops-the-round), the bounded update+verify loop state machine with cycle detection and token budget, the run-folder/state/timeline schemas, source snapshots + identity-based iterate deltas, chain mode with babysit/auto-merge, manifest mode, resume/list, quota handling, worktree isolation, slug rules, and the reviewer-backend contract matrix. None of it mentions Roamex *by necessity*.
2. **A profile mechanism already half-exists.** `profiles/roamex.md` is explicitly "the authoritative field reference" that SKILL.md's "Roamex project facts" table only *summarises* — i.e., the source has already begun extracting project facts into a profile file with a de-facto field schema (~14 fields: project id, source system, repo set, mental model, build gates, TDD policy, anti-patterns, planning unit, backend, branch convention, PR target).
3. **The remaining project-specific matter is enumerable.** It is woven through the core but is a finite, listable set of surfaces: the issue-URL/id regexes (`roam-N`, `github.com/xinquan568/roamex`), `--repo` values on `gh` calls (including the Step-9 PR PATCH endpoint), the workspace-root expectation (`codes/roamex`), the branch template, the PR-body template, the build/test gate commands *and their free-form mechanics* (the Chromium checkout symlink hand-off), the TDD policy, the anti-pattern list, the reviewer mental-model references (execution plan §7.9/§12.2, ADRs), the per-step reviewer category vocabularies (e.g. `overlay-discipline`, `flag-gating`), and the scenario keyword table.
4. **The skill's own text shows copy-adapted lineage.** Two facts are directly observable on disk: the Step-1 analysis schema still uses the field name `crates_confirmed` ("kept as the field name") while describing Chromium *overlay areas* — a fossil of a Rust-project ancestor kept for schema stability — and the sibling runs-stats skill still carries Jira-era `QTAC-`/`QTDQ-` ticket examples and a `runs/jira/` legacy directory. The *inference* from these fossils (and from the owner's own description of per-project variations) is that the pipeline has previously been re-targeted **by editing copies** rather than by configuration; the older copies themselves are not in this workspace to cite. Observed or inferred, both point the same way: variation-by-fork is exactly what a profile contract eliminates.
5. **The abstraction pattern demonstrably works in this codebase.** The reviewer-backend contract matrix (`codex` | `copilot-cli`) already isolates *how the reviewer is reached* behind a small per-backend table while everything else stays backend-agnostic. Standardization applies the same move to *which project is being worked on*.

### 11.2 Why it is suitable (and where the honest limits are)

- **Suitable because** the variation across projects is (a) *facts*, not structure — repo names, regexes, commands, doc pointers — plus (b) exactly one structural axis: the **source system** (GitHub issues vs Jira tickets), which changes fetch/snapshot/delta mechanics, closing-link conventions, and re-introduces Jira-only steps (fixVersion, QA-handoff comments). Facts standardize as a profile schema; the one structural axis standardizes as a small driver interface.
- **Limits to state honestly:** (1) build-gate mechanics can be arbitrarily project-exotic (the Chromium symlink hand-off is a procedure, not a command list) — so the profile must allow *free-form gate-mechanics prose* the worker follows, and a profile's quality directly bounds run quality; (2) reviewer mental-model references are inherently per-project and cannot be generated — only pointed to; (3) chain mode's babysit/auto-merge semantics assume GitHub PRs; a Jira/other-forge driver would need its own adapter work (deferred, not blocking GitHub-first v1).

### 11.3 How to standardize (the plan F6.2/F6.4 implement)

1. **Core/profile split.** SKILL.md becomes the project-neutral core; a versioned **profile contract** defines the fields (required: project id, repo id/path, base branch, source driver + id pattern + URL regex, branch template, gate commands; optional: gate-mechanics prose, PR-body template, TDD policy, anti-patterns, mental-model refs, category extensions, scenario overrides, backend preference). A profile-lint validates contract conformance at run-start.
2. **Parameterize the enumerated surfaces** (§11.1 item 3) in core — every hardcoded regex, `--repo` value, path, and template resolves from the profile at run-start; core carries zero project literals (AC-6-style grep enforces it).
3. **Source-system driver interface.** v1 ships the **github** driver (fetch via `gh issue view`, PR closing links, chain/babysit). The **jira** driver (ticket fetch, fixVersion, QA-handoff) is specified as an interface obligation but deferred — the profile names its driver, so adding jira later changes no core logic.
4. **Category vocabularies = core set + profile extensions.** The per-step reviewer categories keep a stable core (correctness, security, test-coverage, plan-adherence, …); project-specific ones (`overlay-discipline`, `flag-gating`) come from the profile.
5. **Schema hygiene:** rename `crates_confirmed` → `areas_confirmed` with a manifest-schema version bump and read-compat for old runs (closing the fossil in §11.1 item 4).
6. **Ship no profiles; scaffold instead (D2).** The Roamex profile becomes a reference example under `examples/`; real profiles are generated per project by **F6.4 `profile init`** (auto-detect + interview) once the user's repo is finalized.
7. **Conformance fixtures (AC-3):** the scaffolder fixture plus the Roamex reference profile validated against the contract; a golden `--review-mode none` run on a tiny fixture repo proves the core runs with zero project literals.

---

## Resolved decisions (this iteration)

- **D1 (was Q1).** Namespace `/vibe:*` confirmed; all renames accepted (`implement`→`delegate`, `audit`→`roast --engine codex`, `status/cancel/result`→`jobs`, six auditors→`nl-audit --type`).
- **D2 (was Q2).** **No usable project profiles ship.** Roamex remains a reference example only. The suite instead helps users create their own profile once their GitHub repo is finalized — the F6.4 `profile init` scaffolder.
- **D3 (was Q3).** The stop-review gate ships **opt-in** (disabled by default), toggled via `/vibe:config`.
- **D4 (was Q4).** The auditor unit deploys under **`github.com/xinquan568/vibe-suite`** (local `codes/vibe-suite`) — the same repo as the plugin; the public site **rebrands to vibe-suite**. Ops data lives on the repo's dedicated `auditor-data` branch (A2).
- **D5.** Division of labor: **Claude Code works, Codex reviews, Gemini/agy audits** (P8) — implemented as a staged rollout: codex is the shipped cross-model audit default until the agy adapter (F2.7, the one net-new capability, owner-directed) passes its contract gate (Q5/AC-9), then the default flips to agy.
- **D6.** **No pinned model versions anywhere** — each tool runs its own current default/best model; tier aliases only for in-session agents (P9, AC-9). Today's defaults (Claude Fable 5, GPT-5.6-sol, Gemini 3.1 Pro) are documentation examples, never shipped strings.
- **D7.** Provenance: the repository README's collective acknowledgement of the referenced repos is the complete attribution; implementations are vibe-suite's own code at functional parity; no per-part source labels ship (§2).

## Assumptions & open questions

**Assumptions (proceeding on these unless corrected):**
- A1. vibe-suite is a **single plugin** under the `/vibe:*` namespace; source plugins are uninstalled after migration (no coexistence aliases; §7A row 10 covers detection; a README migration table maps every old command to its new home).
- A2. Per D4's single-repo decision, the plan reconciles "one repo" with "lean plugin installs" by placing accumulated ops data on a dedicated **`auditor-data` branch** of `xinquan568/vibe-suite`: the default branch (what a plugin install clones) carries functions and workflows only; pipeline workflows check out the data branch; Pages publishes from the site build. If the owner prefers ops data on the default branch instead, only §7A row 9 and the F10.1 data paths change (open question Q6).
- A3. "Merge all functions" means **feature parity at the function level**, verified by AC-1 coverage and AC-3 equivalence fixtures — not byte-level ports (consistent with D7).
- A4. The suite keeps **English** as its artifact language.
- A5. The reviewer backend default stays **codex**, running the **backend's default model** (P9 — no pinned reviewer model; today that resolves to GPT-5.6-sol). The worker is the Claude session; the same-model-family refusal applies suite-wide. issue2pr's `copilot-cli` backend ships as specified in its source skill.
- A6. cc-suite's reverse-delegation direction (Codex calling Claude via the pinned MCP server) is preserved as-is, including the npm pin discipline.
- A7. Gemini/Antigravity support = the source-parity bridge (instruction/skill bridging + the conventions-antigravity overlay) **plus the new agy audit lane (F2.7, per D5 — staged behind its contract gate)**. No agy thread-resume or background jobs in v1 — audit calls are bounded one-shots; parity with the codex lane's job features is future work if usage warrants it.

**Open questions for the owner:**
- Q5. **agy dispatch contract:** no source repo contains an agy runner today, so F2.7 is gated on confirming the CLI's headless contract — exact binary/flags for a one-shot invocation, stdin/stdout transport, read-only enforcement, timeout behavior, and failure/quota signatures (the shape assumed is `agy exec`-like, mirroring `codex exec`). Please confirm (or point at its docs). **This blocks only the default flip to agy, not v1 shipping** — audit commands default to codex until the gate passes (P8).
- Q6. **Ops-data location:** is the `auditor-data` branch layout (A2) acceptable, or should ops data live directly on the default branch of `xinquan568/vibe-suite` despite the install-size cost?
- Q7. **Scaffolder interview scope (F6.4):** is the v1 field set (identity, driver, gates, TDD, anti-patterns, mental-model refs) right, or should v1 detect-only (no interview) and leave the judgment fields as commented stubs the user fills by hand?
