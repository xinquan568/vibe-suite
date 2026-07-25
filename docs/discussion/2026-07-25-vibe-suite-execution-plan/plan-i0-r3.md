> **Historical record — superseded in part.**
> This is a planning artifact preserved for traceability, not a live specification. Where it
> disagrees with current configuration, current configuration wins. Known divergence: this document
> refers to the command namespace as `/vibe:`; the namespace is now **`/vibe-suite:`** (D1-revised,
> 2026-07-25), which follows from `.claude-plugin/plugin.json:name`. The bound issue2pr profile is
> authoritative on project facts.

# vibe-suite — Execution Plan

**Goal:** turn the converged merge proposal — `docs/discussion/2026-07-18-vibe-suite-merge/iter-1/round-1/plan-i1-r1.md` (57 functions, 10 categories, decisions D1–D10, acceptance criteria AC-1..AC-9) — into ordered, **issue-sized work items** across **nine implementation stages**, so an AI can generate GitHub issues from this document and the project can be completed step by step in `codes/vibe-suite` (github.com/xinquan568/vibe-suite).

This plan adds no design decisions. Where a work item summarizes behavior, the merge proposal's function spec (its `F<x>.<y>` ID) is the authoritative definition; every item links to its function IDs. Conflicts resolve in favor of the merge proposal.

---

## 0. Decisions in force

| ID | Decision (settled — do not reopen in issues) |
|---|---|
| D1 | Namespace `/vibe:*`; renames: `implement`→`delegate`, `audit`→`roast --engine codex`, `status/cancel/result`→`jobs`, six auditors→`nl-audit --type` |
| D2 | No usable issue2pr profiles ship; Roamex = reference example; users generate profiles via `profile init` (F6.4) |
| D3 | Stop-review gate ships **opt-in** (disabled by default) |
| D4 | Auditor unit + site deploy in `github.com/xinquan568/vibe-suite`; site rebranded to vibe-suite |
| D5 | Division of labor: Claude works, Codex reviews, agy audits — **staged**: v1 audit default = codex until the F2.7 contract gate passes |
| D6 | No pinned model versions in shipped artifacts; tier aliases only; tool defaults otherwise (AC-9 lint) |
| D7 | Provenance: README-level acknowledgement of referenced repos; implementations are our own code; no per-part attribution |
| D8 | *(new, Q5)* agy CLI: binary **`agy`** (installer per https://antigravity.google/docs/getting-started); headless shape is **codex-exec-like** per the owner. Public docs confirm the binary, the TUI, and `settings.json` `toolPermission` modes (`request-review`, `proceed-in-sandbox`) but not the one-shot flags — so the F2.7 contract-gate **fixture verifies the exact flags empirically** before the default flips |
| D9 | *(new, Q6)* Ops data lives on the **`auditor-data` branch** of the same repo (A2 layout accepted) |
| D10 | *(new, Q7)* F6.4 scaffolder v1 keeps the full field set: identity, driver, gates, TDD, anti-patterns, mental-model refs (detect + interview) |

---

## 1. Stage overview

Stages match the merge proposal's phasing (§9). Each stage ends at a **stage gate** — a verifiable condition CI can hold. Suggested GitHub mapping: **one milestone per stage** (`S0`…`S8`), one issue per work item.

| Stage | Theme | Items | Depends on | Stage gate (definition of done) |
|---|---|---|---|---|
| S0 | Repo scaffold & shared core | 8 | — | CI runs on every PR: manifest valid, coverage-check + model-pin-lint wired (allowed to pass trivially until sources land) |
| S1 | Engines: codex runner, jobs, agy lane | 7 | S0 | `codex` lane green end-to-end on a smoke prompt; `/vibe:jobs` round-trips a background job; agy contract-gate fixture written (pass/fail recorded, default stays codex until pass) |
| S2 | Setup, bridge & lifecycle commands | 8 | S0, S1 | `/vibe:init` → `/vibe:doctor` clean on a fresh fixture project; §7A migration fixtures rows 1–8, 10 green |
| S3 | NL quality engine + security scan (deterministic/claude lanes only — cross-engine lanes land in S4) | 9 | S0 | `/vibe:score` deterministic on fixtures (AC-2); `bin/vibe-check` exit 0 on the suite itself |
| S4 | Cross-model auditor + code review + cross-engine lanes | 5 | S1, S3 | AC-3 nl-audit + roast fixtures green on the codex lane (agy-lane assertions run conditionally per the E1.7 gate) |
| S5 | Workflow loops (refine-proposal, issue2pr, scaffolder) | 7 | S1 (E5.6 additionally needs E4.4 from S4) | AC-4 loop bounds green; issue2pr mode/backend contract tests green; profile-lint + scaffolder fixture green; review-plan equivalence fixture green |
| S6 | Advisors, reporting, runs-stats | 6 | S2, S3, S5 | AC-3 runs-tree fixture green; report/trend/badge run on the suite's own history |
| S7 | Mirrors, docs, release gate | 5 | S0–S6 | AC-6 legacy-string sweep green; AC-7 quality gate green; `vibe-check --mirrors` green — **plugin releasable** |
| S8 | Auditor deployment, rulebook loop & site | 7 | S3, S4, S7 | AC-8 `auditor-integration-test` green in `xinquan568/vibe-suite`; site live under vibe-suite branding; data migrated to `auditor-data` |

Parallelism: S3 can run in parallel with S1–S2 (its cross-engine lanes were moved to S4 precisely so S3 has no S1 dependency). S5's items need only S1, except the AC-4 harness E5.6, which also needs E4.4 (S4) — the S5 stage gate therefore closes only after that one S4 item. S8 is independently deployable after S7.

---

## 2. Issue-generation conventions (for the AI that creates issues)

1. **One issue per work item.** Title: `[S<stage>] E<stage>.<n> — <item title>` (e.g. `[S1] E1.7 — agy-runner + contract-gate fixture`).
2. **Body** = the item's four blocks verbatim (Do / Deliverables / Acceptance / Depends), prefixed with one context line: "Implements F<ids> of the merge proposal (docs/discussion/2026-07-18-vibe-suite-merge/iter-1/round-1/plan-i1-r1.md); execution plan item E<id>." **Every item in §3 carries all four blocks** — if one appears to be missing, that is a defect in this plan, not license to improvise.
3. **Milestones:** `S0`…`S8`, one per stage. **Labels:** `stage:S<n>`, an area label (`area:engine|lifecycle|quality|review|workflow|reporting|mirror|auditor|docs`), and a size label (`size:S|M|L` from the item).
4. **Dependencies come in two kinds.** (a) *Item dependencies* — explicit item IDs, always a comma-separated list, never a range; rewrite each as an issue link ("Blocked by #<n>"). (b) *Stage-gate dependencies* — written `gate:S<n>`, meaning "milestone S<n> closed"; rewrite as a note linking the milestone. **Explicit dependency lists override numeric ordering** — an item may depend on a higher-numbered item in the same stage only when its Depends list says so (none currently do; ordering was normalized instead).
5. **Order within a stage** follows item numbering; cross-stage order follows §1's dependency column.
6. **Do not split or merge items** without updating this plan first — item boundaries were chosen to be one-PR-sized (S ≈ half a day, M ≈ 1–2 days, L ≈ 3–5 days of focused agent work).
7. Every issue inherits the suite-wide rules: D6 (no pinned model versions in code), D7 (no per-part source attribution), P2 (scripts for mutation, models for judgment), and the untrusted-input rule (F9.2).

---

## 3. Work items by stage

### Stage S0 — Repo scaffold & shared core *(milestone S0)*

**E0.1 — Repo scaffold, manifest pair, CI skeleton** · size M · F: §4 architecture
- **Do:** In `codes/vibe-suite`: create the plugin skeleton (`.claude-plugin/plugin.json` + `marketplace.json` with explicit commands/agents/skills arrays; `commands/ agents/ skills/ hooks/ scripts/ bin/ templates/ auditor/ codex/ tests/ tools/ docs/`). Bootstrap GitHub Actions CI (`.github/workflows/ci.yml`): jobs for manifest validation, Python/Node lint, and test execution; POSIX-only note in README (§8.1).
- **Deliverables:** manifest pair, directory skeleton, `.github/workflows/ci.yml`, README stub with the D7 acknowledgement section.
- **Acceptance:** CI green on the scaffold PR; manifest parses; plugin installs locally via the marketplace file.
- **Depends:** —

**E0.2 — vibe-core: finding contract + untrusted-input rules** · size M · F9.1, F9.2
- **Do:** Write the `vibe-core` knowledge skill: severity scale `[CRITICAL]..[GOOD]`, effort classes, six-field finding format (+Exploit scenario, +Risk Matrix variants), output-header contract, zero-findings `[GOOD]` rule, anti-padding rules, the severity mappings (nlpm penalties, cc-suite audit levels); untrusted-input + secret-handling rules stated once. Revive `audit-output.schema.json` as the machine-readable finding schema.
- **Deliverables:** `skills/vibe-core/SKILL.md`, `schemas/audit-output.schema.json`.
- **Acceptance:** schema validates a hand-written sample report; skill referenced by later agents compiles into their prompts (checked in S4).
- **Depends:** E0.1

**E0.3 — Discovery & classification partials** · size M · F9.3
- **Do:** Author the four shared partials: `discover.md` (categories A–F with skip-dirs), `classify.md` (17-row first-match-wins table + C/D/E types), `scope-parse.md` (scope grammar incl. trivial-change gate), `plugin-discover.md` (manifest validation + cross-reference map).
- **Deliverables:** `commands/shared/{discover,classify,scope-parse,plugin-discover}.md`.
- **Acceptance:** fixture repo classified correctly per category (table-driven test in `tests/`).
- **Depends:** E0.1

**E0.4 — Engine-selection + fallback partials (staged agy default)** · size S · F9.4, F9.5
- **Do:** `model-selection.md`: priority user > `.vibe-suite.md` > tool default; engine vocabulary (`engine`, `cross_model_audit_engine` — **codex in v1, flips to agy post-gate**, `reviewer backend/model`); no versioned model IDs anywhere. `fallback.md`: the two-hop chain agy → codex → manual, each hop emitting the diagnostic header.
- **Deliverables:** `commands/shared/{model-selection,fallback}.md`.
- **Acceptance:** table-driven unit test: (user choice, `.vibe-suite.md` value, tool default) triples resolve to the expected engine/model per the partial's rules, incl. the staged `cross_model_audit_engine` default; the user-visible rendering of these defaults is asserted downstream by E2.7's acceptance (AC-9c).
- **Depends:** E0.1

**E0.5 — `.vibe-suite.md` schema + config reader** · size M · F9.8, F1.8 (read side)
- **Do:** Document the config schema (engine defaults, skip patterns, score threshold, rule overrides incl. R51, `issue2pr_profile`, gate mirror) in vibe-core; implement one shared reader used by all commands (shell/python helpers under `scripts/lib/`), plus the job-state `state.json:config` runtime-toggle store.
- **Deliverables:** schema section in vibe-core; `scripts/lib/config.*`; store layout doc.
- **Acceptance:** round-trip test: write config → every consumer reads identical values; unknown keys warn, never crash.
- **Depends:** E0.1

**E0.6 — `docs/disposition.yaml` + coverage-check (AC-1)** · size M · §6, AC-1
- **Do:** Encode the merge proposal's §6 disposition map as `docs/disposition.yaml`; implement `tools/coverage-check.py` as the recursive allowlisted walk over the three pinned source trees + three workspace-skill trees (allowlist incl. `skills/**/SKILL.md`, `scripts/**/*`, manifests, top-level docs, `codex/**`, `site/**`; shared exclusion list; expected per-tree counts: cc-suite 13 skills, nlpm 17 skills). Wire into CI. Sources are consulted read-only at pinned commits (`bb605ec`, `938b1e8`, `4ef75d4a`) — vendor a file-manifest snapshot of each tree so CI needs no source checkout.
- **Deliverables:** `docs/disposition.yaml`, `tools/coverage-check.py`, vendored source-tree manifests under `tests/source-manifests/`, CI job.
- **Acceptance:** AC-1 — removing any row fails CI; expected counts assert; the exclusion list is the single shared definition.
- **Depends:** E0.1

**E0.7 — model-pin-lint (AC-9a)** · size S · P9
- **Do:** `tools/model-pin-lint.py`: grep shipped runtime-reachable artifacts for versioned model IDs (`gpt-<digit>`, `gemini-<digit>`, dated `claude-*-20*`, `o<digit>-` …); allowlist docs/CHANGELOG; tier aliases pass. Wire into CI.
- **Deliverables:** the lint, its CI job, and its own test cases (seeded violation + clean tree).
- **Acceptance:** seeded violation fails CI; clean tree passes.
- **Depends:** E0.1

**E0.8 — Migration engine + auditor-data migration script** · size M · §7A, AC-5 (row 9 part)
- **Do:** Implement the §7A migration helpers as idempotent scripts with sentinels/provenance (rows 1–8, 10 logic — invoked by init in E2.1), plus `tools/migrate-auditor-data.sh <dest-repo> [--branch auditor-data]` (copy + count/hash verification + idempotent re-run, per D9).
- **Deliverables:** `scripts/migrate/*.sh`, `tools/migrate-auditor-data.sh`.
- **Acceptance:** AC-5 row-9 fixture (local bare repo with `auditor-data` branch): complete copy, idempotent second run, originals byte-identical.
- **Depends:** E0.1, E0.5

### Stage S1 — Engines *(milestone S1)*

**E1.1 — codex-runner job engine** · size L · F2.1
- **Do:** Implement `scripts/codex-runner.mjs` + `scripts/lib/*`: foreground/background jobs, 30 s heartbeat, SIGTERM→SIGKILL deadlines, thread-id capture/resume, stdin `/dev/null`, sandboxes (`read-only` default / `workspace-write` / `danger-full-access` confirm-gated), one-line JSON result contract, job store at `<stateDir>/jobs/<jobId>.json`. `--model` optional (tool default per D6).
- **Deliverables:** the runner + lib modules + unit tests (deadline kill, resume, result contract).
- **Acceptance:** background smoke job completes and is queryable; kill honors deadline; no top-level await (cc-suite W7 class).
- **Depends:** E0.5

**E1.2 — `/vibe:jobs` command** · size S · F2.5
- **Do:** `status|result|cancel` subcommands over the E1.1 store using the resolver helpers + `render.mjs` renderers; document the real storage path.
- **Deliverables:** `commands/jobs.md` + renderer wiring.
- **Acceptance:** each subcommand exercised against live jobs in a test session; covers agy jobs after E1.7.
- **Depends:** E1.1

**E1.3 — `/vibe:preflight`** · size S · F1.5
- **Do:** codex probe (version, auth mode, exec smoke, model discovery from `~/.codex/models_cache.json` with TTL cache); agy probe slot (version, tiny read-only smoke, default-model report) landing codex-only first — the agy probe body is finalized inside E1.7 and slots in here. Zero hardcoded model names.
- **Deliverables:** `commands/preflight.md` + probe scripts (codex now; agy hook point).
- **Acceptance:** correct availability matrix for the codex lane with the CLI present/absent (fixture PATH manipulation); the agy column reports "probe pending" until E1.7 lands — the agy present/absent matrix is asserted by E1.7's acceptance.
- **Depends:** E1.1

**E1.4 — `/vibe:delegate`** · size M · F2.2
- **Do:** Plan/task → Codex implementation via E1.1; sandbox confirm gate for `danger-full-access`; post-run verify step; provenance disclosure line.
- **Deliverables:** `commands/delegate.md`.
- **Acceptance:** fixture plan delegated at `workspace-write` in a scratch repo; verify step runs; no `implement` naming anywhere (AC-6 class).
- **Depends:** E1.1

**E1.5 — `/vibe:bug-analyze` + `/vibe:continue`** · size S · F2.3, F2.4
- **Do:** RCA command (grep/glob recon → per-file Codex analysis → report) and thread-resume command (inherits original sandbox).
- **Deliverables:** `commands/bug-analyze.md`, `commands/continue.md`.
- **Acceptance:** RCA on a seeded-bug fixture names the defective file; continue resumes the E1.4 thread.
- **Depends:** E1.1

**E1.6 — Stop-review gate + lifecycle hooks (opt-in)** · size M · F2.6, D3
- **Do:** Port the Stop hook (900 s timeout; reviews the session **diff**; `ALLOW:`/`BLOCK:`; fail-open on infra failure) + SessionStart/SessionEnd hooks; **disabled by default**, toggled via the E0.5 runtime store; model from config (backend default).
- **Deliverables:** `hooks/` registrations + `scripts/stop-review-gate-hook.mjs`, `scripts/session-lifecycle-hook.mjs`.
- **Acceptance:** disabled by default on fresh install; enabled fixture blocks on a seeded bad diff and fails open when codex is absent.
- **Depends:** E1.1, E0.5

**E1.7 — agy-runner + contract-gate fixture (D8)** · size M · F2.7, AC-9(b)
- **Do:** Implement `scripts/agy-runner.mjs` mirroring E1.1's surface (stdin prompt, read-only execution, deadline, JSON result, shared job store; no resume/heartbeat in v1). Per D8: binary `agy`, codex-exec-like one-shot; enforce read-only via the CLI's sandbox/tool-permission mechanism (`settings.json` `toolPermission` per docs — resolve exact non-interactive flags empirically). Write the **contract-gate fixture** (headless one-shot call, read-only enforcement proof — an attempted write is denied, timeout kill, failure/quota signature parsing) and the **runner-level fallback fixtures**: agy selected but unavailable → codex hand-off with the F9.5 diagnostic header; agy and codex both unavailable → manual-fallback signal to the caller. Implement the **default-flip mechanism**: `cross_model_audit_engine` stays `codex` until the contract fixture passes in CI, then flips via a config-default change accompanied by a doctor notice; `--engine agy` errors with gate status before that. Finalize the E1.3 agy probe body.
- **Deliverables:** the runner, `tests/agy-contract/` fixtures (contract + both fallback paths), the flip PR checklist in `docs/`, the E1.3 probe body.
- **Acceptance:** contract-fixture outcome recorded either way; both fallback fixtures green (they run regardless of agy availability, via PATH manipulation); with `agy` installed and passing, the flip checklist executes; with it absent, everything still ships (D5 staging); the E1.3 preflight probe now reports the agy present/absent matrix correctly (closing the assertion E1.3 deferred).
- **Depends:** E1.1, E0.4

### Stage S2 — Setup, bridge & lifecycle *(milestone S2)*

**E2.1 — `/vibe:init`** · size L · F1.1, §7A rows 1–8/10
- **Do:** Interactive setup: AskUserQuestion flow (tier/default trust per D6, audit depth, score strictness, skip patterns); writes `.vibe-suite.md`, `AGENTS.md` + import lines, `.codex/config.toml`, `.codex/hooks.json`, `.mcp.json` entries, gitignore sentinel block, baseline history; invokes the E0.8 migration helpers for legacy cc-suite/nlpm stores; each bridge script runs exactly once.
- **Deliverables:** `commands/init.md` + `scripts/init.sh` orchestration.
- **Acceptance:** AC-5 rows 1–8 and 10 fixtures green (new store created, legacy byte-identical, precedence, doctor warnings); idempotent re-run is a no-op (AC-2).
- **Depends:** E0.5, E0.8

**E2.2 — `/vibe:doctor`** · size M · F1.2
- **Do:** Read-only diagnosis: sentinels/symlinks/pins, codex+agy connectivity, MCP registrations, hook wiring, manifest-vs-disk (E3.5 pointed at the project), version coherence, mirror staleness (hash manifest — full check live after E7.2), knowledge freshness, legacy-store detection; issues table with auto-fixable flags; offers repair.
- **Deliverables:** `commands/doctor.md`.
- **Acceptance:** each seeded breakage class detected on fixtures; clean project reports clean.
- **Depends:** E2.1

**E2.3 — `/vibe:repair`** · size S · F1.3
- **Do:** Non-interactive re-run of all bridge scripts: no prompts, idempotent, collect failures and continue, per-script outcome report; positioned as the escalation path from doctor.
- **Deliverables:** `commands/repair.md`.
- **Acceptance:** repairs every E2.2 auto-fixable fixture; re-run after repair is a byte-identical no-op.
- **Depends:** E2.1, E2.2

**E2.4 — `/vibe:unbridge`** · size M · F1.4
- **Do:** Confirm-gated teardown driven by the sentinel inventory (single source): all `vibe-*` sentinels, symlinks, MCP entries, gitignore block; provenance-backed CLAUDE.md restore; legacy `cc-suite-*` sentinel cleanup on confirm.
- **Deliverables:** `commands/unbridge.md` + `scripts/unbridge.sh`.
- **Acceptance:** after init→unbridge, the fixture project is byte-identical to pre-init (minus explicitly user-kept files); nothing user-owned touched.
- **Depends:** E2.1

**E2.5 — `/vibe:bridge`** · size M · F1.6
- **Do:** Subcommands `skills|hooks|mcp|mirrors|all`: skills symlinking; project-hook mirroring into `.codex/hooks.json` for the five shared event types (side-file fallback when user-owned); `.mcp.json`→`config.toml` sentinel mirroring, never copying secrets; `mirrors` = E7.2 regeneration (stub with a clear "lands in S7" message until then).
- **Deliverables:** `commands/bridge.md` + bridge scripts.
- **Acceptance:** each subcommand idempotent; a secret-bearing `.mcp.json` fixture never leaks values into `config.toml`.
- **Depends:** E2.1

**E2.6 — `/vibe:update`** · size S · F1.7
- **Do:** Post-plugin-update refresh: re-render bridges, npx pre-warm, `claude-octopus` pin boot-verify (real `initialize` handshake), mirror-regen hook; all output strings `/vibe:*`-only.
- **Deliverables:** `commands/update.md`.
- **Acceptance:** runs clean after a simulated plugin update; AC-6 grep finds no retired names in its output.
- **Depends:** E2.1, E2.5

**E2.7 — `/vibe:config`** · size S · F1.8
- **Do:** `--show` (merged `.vibe-suite.md` + runtime toggles, resolved engine defaults) and `--set key=value` (gate on/off, gate model, fail policy) over the E0.5 reader/store.
- **Deliverables:** `commands/config.md`.
- **Acceptance:** AC-9(c) — resolved engine defaults visible; gate toggle round-trips to the E1.6 hook.
- **Depends:** E0.5, E1.6

**E2.8 — Migration fixture suite (AC-5)** · size M · §7A
- **Do:** Build the ten §7A fixture projects and the assertion harness (new store created; legacy byte-identical; precedence honored; doctor warnings; row 8 no-op; row 9 already covered by E0.8's fixture).
- **Deliverables:** `tests/fixtures/migration/*` + harness in CI.
- **Acceptance:** AC-5 green across all rows.
- **Depends:** E2.1, E2.2, E2.3, E2.4

### Stage S3 — NL quality engine + security *(milestone S3)*

*(Deterministic and in-session lanes only — the `--engine codex|agy|both` cross-engine lanes for score land in E4.5, so this stage has no S1 dependency.)*

**E3.1 — Knowledge-skill library** · size L · F4.8
- **Do:** Author the 19 skills at functional parity (rules R01–R51, scoring tables + calibration + known-FP patterns, conventions floor + three overlays with the cc-suite/nlpm conventions-claude merge, patterns, testing, security, vocabulary, seven writing-*/orchestration references, agent-design, vibe-core from E0.2). Exemplar citations become build-time-generated placeholders (wired in S8 by E8.6).
- **Deliverables:** `skills/*/SKILL.md` ×19.
- **Acceptance:** self-contained at close: all 19 skill files parse with frontmatter present, the rules skill header count is correct, and a grep proves no hard link into ops data (nlpm S7 class); the full `bin/vibe-check` clean run over the tree is owned by E3.5's acceptance once that item lands.
- **Depends:** E0.2

**E3.2 — `/vibe:ls` + scanner agent** · size S · F4.1
- **Do:** Inventory command over the E0.3 discovery categories (A–F) with per-category file/line/token counts; haiku-class scanner agent (Read+Glob); no scoring.
- **Deliverables:** `commands/ls.md`, `agents/scanner.md`.
- **Acceptance:** fixture repo counts match golden values per category.
- **Depends:** E0.3

**E3.3 — `/vibe:score` (deterministic claude lane)** · size M · F4.2 (deterministic core)
- **Do:** Deterministic subtractive scoring: scorer agent (sonnet-class, loads scoring/conventions/vocabulary, full FP gauntlet + tier classifier) + vague-scanner (haiku-class, 11 words, −2 cap −20) in batches ≤5; config thresholds/rule overrides; malformed-YAML −25 / empty-file 0 / unreadable-skip paths; findings table + bands; scope-tagged atomic history appends. The `--engine` cross-model lanes are **out of scope here** — E4.5 adds them.
- **Deliverables:** `commands/score.md`, `agents/scorer.md`, `agents/vague-scanner.md`.
- **Acceptance:** AC-2 (same score ×3 runs) and the AC-3 golden penalty total on `defective-skill/`; the three degenerate-input paths fixture-tested.
- **Depends:** E3.1, E0.3

**E3.4 — `/vibe:check` + checker agent** · size M · F4.3
- **Do:** Cross-component consistency: reference integrity (command→partial, agent skills→SKILL.md, hook→script, CLAUDE.md listings), orphans, behavioral contradictions, terminology drift, R51 vocabulary drift when enabled; Verdict `CLEAN | N issues`; requires ≥2 artifacts.
- **Deliverables:** `commands/check.md`, `agents/checker.md`.
- **Acceptance:** seeded-breakage fixture caught per class; clean fixture verdicts CLEAN.
- **Depends:** E3.1, E0.3

**E3.5 — `bin/vibe-check` CI validator** · size M · F4.4
- **Do:** Stdlib-only Python: manifest-vs-disk, unregistered skills, frontmatter presence, name/dir match, hook event case, monorepo detection, version coherence, `--mirrors` staleness (live after E7.2); exit codes 0/1/2; ship pre-commit + GitHub-workflow templates.
- **Deliverables:** `bin/vibe-check`, `templates/pre-commit`, `templates/ci-vibe-check.yml`.
- **Acceptance:** exit 0 on the suite itself; each check class has a failing fixture.
- **Depends:** E0.1

**E3.6 — `/vibe:test` NL-TDD runner + suite specs** · size M · F4.5
- **Do:** Spec runner over `.vibe-test/` (+ legacy `.nlpm-test/` read-compat, new specs to the new dir); tester agent (frontmatter validity, trigger/non-trigger prediction with confidence, output-format expectations, rule compliance, score-vs-min_score); batches ≤3; missing artifact → RED. Author specs for **all 14 suite agents**.
- **Deliverables:** `commands/test.md`, `agents/tester.md`, `.vibe-test/*.spec.md` ×14.
- **Acceptance:** AC-7 spec-coverage clause (14/14); RED on a missing-artifact fixture; legacy-dir fixture runs.
- **Depends:** E3.1

**E3.7 — `/vibe:vocab` init+drift + suite registry** · size M · F4.6
- **Do:** `init`: layout detection, literary-warrant extractor (Python), vocabulary SKILL.md + `registry.yaml` stub, R51 opt-in instructions, overwrite refusal. `drift`: registry-free advisory scan (≥5 artifacts, cap 20, never penalizes, homonym FP suppression). Seed the suite's **own** registry with the merge-decided vocabulary (engine, cross_model_audit_engine, reviewer backend, delegate, …) and enable R51 (P7).
- **Deliverables:** `commands/vocab.md`, `agents/vocab-drift-scanner.md`, extractor script, `skills/vocabulary/` + suite `registry.yaml`.
- **Acceptance:** init refuses overwrite; drift on a seeded-synonym fixture clusters correctly; suite registry passes its own R51 check.
- **Depends:** E3.1

**E3.8 — `/vibe:spec-sync` + spec-researcher** · size M · F4.7
- **Do:** Per-overlay research agent (sonnet-class + WebFetch/WebSearch, first-party sources only, tagged gap report FIX/REMOVE/ADD/CONFIRM/RESOLVED with confidence guard); apply with inline correction notes + version bump; propagate via grep sweep; verify via E3.5; never commits.
- **Deliverables:** `commands/spec-sync.md`, `agents/spec-researcher.md`.
- **Acceptance:** dry-run on a seeded-stale overlay fixture produces a correctly tagged gap report; verify step invokes E3.5.
- **Depends:** E3.1, E3.5

**E3.9 — `/vibe:security-scan` + advisory hook** · size M · F5.1, F9.7
- **Do:** Security-scanner agent (sonnet-class, prompt-injection defense) over the shared security pattern skill: execution-surface discovery, Critical/High/Medium DB with context-aware capping (md-capped-Low, echo/heredoc drops, lockfile suppression, `.mcp.json` vs `package.json` pinning), gate banner `PASS | REVIEW | BLOCK`. Plus the PostToolUse advisory hook (5 s, fail-open, one-line stderr reminder on NL-artifact edits).
- **Deliverables:** `commands/security-scan.md`, `agents/security-scanner.md`, `hooks/` PostToolUse registration + `scripts/check-artifact.sh`.
- **Acceptance:** seeded plugin fixture hits each severity band and the capping rules; hook never blocks and stays under timeout.
- **Depends:** E3.1, E0.3

### Stage S4 — Cross-model auditor + code review + cross-engine lanes *(milestone S4)*

**E4.1 — `/vibe:nl-audit` (six types) + AC-3 fixtures** · size L · F4.9
- **Do:** One typed command preserving all six source auditors: per-type D0–D6 dimension sets with mini/full membership, `repo` mode's A–E discovery + 15 check sets, `plugin` type local-only; dispatch via E1.1 (v1 default) / E1.7 (post-gate) with knowledge-skill splice, scope grammar, provenance, and the **full F9.5 chain**: post-flip agy-absent → codex with diagnostic header; agy and codex both absent → manual in-session fallback. Build the six seeded-defect fixtures (`defective-skill/command/agent/rules/plugin`, `mixed-repo/`).
- **Deliverables:** `commands/nl-audit.md`, `tests/fixtures/nl-audit/*`, fallback-path fixtures.
- **Acceptance:** AC-3 per type (≥75 % of seeded classes, correct dimension attribution, mini-membership honored) on each CI-exercised engine lane (agy conditionally per the E1.7 gate); AC-9(b) command-level assertions: post-flip agy-absent run completes via codex with the diagnostic header, both-absent run completes via manual fallback — both exercised via PATH manipulation regardless of real agy availability.
- **Depends:** E1.1, E1.7, E3.1, E3.3

**E4.2 — Roast agents ×6 (recon + five specialists)** · size M · F3.2–F3.7, F5.2
- **Do:** recon (haiku-class, fixed survey template, ≤80 lines, secrets-file ban, prior-report exclusion) + architecture / error-handling / security / testing / edge-cases specialists with grill's ownership deconfliction, inlined untrusted-input rule, six-field findings, `[GOOD]` rule. **F5.2:** the security specialist loads the **same** `skills/security` pattern skill as E3.9's scanner — one pattern DB, two front-ends.
- **Deliverables:** `agents/{recon,architecture,error-handling,security,testing,edge-cases}.md`.
- **Acceptance:** agent specs pass `/vibe:test` (E3.6); deconfliction fixture (a config finding lands with error-handling, not architecture); F5.2 check — both the security agent and E3.9's scanner reference the identical security skill path, verified by a grep test so a pattern update lands in both.
- **Depends:** E0.2, E3.1, E3.6

**E4.3 — `/vibe:roast` orchestrator** · size L · F3.1
- **Do:** recon-first fan-out with styles ×6, add-ons ×8, select-all >500-file gate, engine lanes (`claude` in-session; `codex|agy` = the nine cc-suite dimensions via E1.1/E1.7 with >20-file batching; `both` = claude + configured cross-model engine with reconciliation labels); minute-granular report name + prior-report exclusion; manifest-read version stamp; agent-failure note-and-proceed.
- **Deliverables:** `commands/roast.md`.
- **Acceptance:** AC-3 sample-repo structural assertions (frontmatter keys, per-agent sections, traceable fixing plan, all nine dimensions represented) on the codex lane always, and on the agy lane when the E1.7 gate has passed (same fixture, engine-independent outcome contract).
- **Depends:** E4.2, E1.1

**E4.4 — `/vibe:fix` loop** · size M · F3.8
- **Do:** findings→fix→verify: `--fixer claude` in-session / `--fixer codex` at workspace-write via E1.1; verification always a fresh read-only call by a non-fixing engine (P4/P8); per-issue verdicts `FIXED | NOT FIXED | PARTIAL | REGRESSED`; NL reports re-score via E3.3 with deltas; nlpm's mechanical auto-fix table applied before model fixes.
- **Deliverables:** `commands/fix.md`.
- **Acceptance:** NL fixture improves score with verified closures; mechanical table applied first (order asserted); cap behavior covered by E5.6's harness.
- **Depends:** E1.1, E3.3, E4.1

**E4.5 — Score + security-scan cross-engine lanes (`--engine codex|agy|both`)** · size M · F4.2 (engine lanes), F5.1 (second-opinion lane)
- **Do:** Add the second-opinion lanes to E3.3's score (same rubric packaged into an engine prompt via E1.1/E1.7, same report format, provenance disclosed; `both` = claude + configured engine with explicit disagreement listing) **and to E3.9's security-scan** (a requested second opinion runs on the P8-resolved audit engine, same severity table + gate-banner structure, F9.5 fallback diagnostics). Staged default per D5 for both.
- **Deliverables:** the `--engine` sections of `commands/score.md` and `commands/security-scan.md` + lane tests for both.
- **Acceptance:** codex-lane fixtures for both commands produce the same report structure as their in-session lanes; score's disagreement listing appears on a seeded-disagreement fixture; security-scan's second-opinion lane emits the F9.5 diagnostic header when the resolved engine is absent; agy lanes exercised conditionally per the E1.7 gate.
- **Depends:** E3.3, E3.9, E1.1, E1.7

### Stage S5 — Workflow loops *(milestone S5)*

**E5.1 — Shared reviewer contract (vibe-core section)** · size S · F6.3
- **Do:** The one reference for all loops: backend enum + contract matrix, same-model-family refusal + `--allow-self-review` escape and recorded self-review fallback, review-mode semantics, bounded-round config names, fenced-YAML verdict parsing (last-block, one re-ask, degrade-and-record), closure state machine, D6 model-resolution rule.
- **Deliverables:** the reference section in `skills/vibe-core/` (cross-linked from F6.1/F6.2 ports).
- **Acceptance:** E5.2 and E5.3 both cite it and carry no divergent contract text (grep-checked).
- **Depends:** E0.2

**E5.2 — `/vibe:refine-proposal` port (updated skill)** · size M · F6.1
- **Do:** Port the current workspace skill (incl. `--stop-severity`, `--allow-self-review` fallback, `--second-language` bilingual finalize + one-pass translation review, schema v6, render metadata banner); dispatch refactored through E1.1 (artifact contract `review.md`/`review.json` unchanged); reviewer model = backend default (D6 — drop the `gpt-5.5` pin from script defaults).
- **Deliverables:** `skills/refine-proposal/` (SKILL.md + references + scripts).
- **Acceptance:** AC-3 flawed-plan fixture (`--review-mode single` surfaces ≥2/3 flaws — the review-plan equivalence); a `--dry-run` and a self-review-fallback round both exercise cleanly.
- **Depends:** E5.1, E1.1

**E5.3 — issue2pr core/profile split** · size L · F6.2, §11
- **Do:** Port the complete F6.2 pipeline core — the nine-step/three-phase state machine, review modes `none|single|full` with their severity rules, the bounded update+verify loop machinery, durable `runs/<run-id>/` state/timeline schemas, and source snapshots/deltas — and split it into the project-neutral core + the versioned **profile contract** (§11.3 field set per D10); parameterize every enumerated hardcoded surface (id/URL regexes, `--repo` values incl. the Step-9 PATCH endpoint, workspace expectation, branch template, PR-body template, gates + free-form gate-mechanics prose, category extensions, scenario overrides); profile resolution (`.vibe-suite.md` pointer or `--profile`; refusal with `profile init` pointer when absent per D2); `crates_confirmed`→`areas_confirmed` rename with manifest-schema version bump + read-compat; reviewer model = backend default (D6). Move Roamex to `examples/profiles/roamex.md`; genericize `roamex-manifest.py`→`profile-manifest.py` and the PR-body template; write the profile-lint.
- **Deliverables:** `skills/issue2pr/` (core SKILL.md, profile contract doc, profile-lint, `profile-manifest.py`, `watch-pr.sh`, generic `templates/pr-body.md`, `examples/profiles/roamex.md`, examples).
- **Acceptance:** core carries zero project literals (grep-enforced); golden runs on a tiny fixture repo with a fixture profile in **all three review modes** (stub reviewer for `single`/`full`) asserting run-folder layout, canonical step numbering, and mode-gated folder absences; old-manifest read-compat test; profile-lint rejects a contract-violating profile. (Chain/manifest/resume/iterate/list and the reviewer-backend contract matrix are covered by E5.7.)
- **Depends:** E5.1, E1.1

**E5.4 — Source-driver interface (github)** · size M · F6.2, §11.3(3)
- **Do:** Extract the source-system driver seam (fetch, snapshot/delta, closing links, chain/babysit PR semantics); implement the **github** driver; document the **jira** driver as an interface obligation only (deferred).
- **Deliverables:** the driver interface doc + github driver module inside `skills/issue2pr/`.
- **Acceptance:** driver conformance checklist; core calls no `gh` outside the driver (grep-enforced).
- **Depends:** E5.3

**E5.5 — `profile init` scaffolder** · size M · F6.4, D10
- **Do:** Precondition checks (finalized repo: git + origin on github.com + resolvable default branch); auto-detect (identity, default branch, owner/repo → regexes, login → branch template, gate candidates from package.json/Makefile/Cargo.toml/pom.xml/go.mod/CI, test hints); interview for the D10 judgment fields (TDD policy, anti-patterns, mental-model refs, scenario overrides, backend); write contract-valid `profiles/<id>.md` + `.vibe-suite.md` pointer; profile-lint + `gh issue list -L 1` smoke; `--force` overwrite guard.
- **Deliverables:** the `profile init` mode inside `skills/issue2pr/` + detection scripts.
- **Acceptance:** AC-3 scaffolder fixture (contract-valid profile from a fixture repo with detected fields filled; refusal on no-remote; overwrite guard honors `--force`).
- **Depends:** E5.3

**E5.6 — Loop-bounds test harness (AC-4)** · size S · AC-4
- **Do:** Stub reviewer that never returns a clean verdict; run each generator-critic loop against it: E4.4 fix, E5.2 refine-proposal, E5.3 issue2pr (update+verify loops). Assert cap stop + correct terminal status; malformed verdict → exactly one re-ask → degrade-and-record, never abort.
- **Deliverables:** `tests/loop-bounds/` harness + CI job.
- **Acceptance:** AC-4 green across all three loops.
- **Depends:** E4.4, E5.2, E5.3

**E5.7 — issue2pr operational modes + backend contracts** · size M · F6.2 (chain/manifest/resume/list, backends)
- **Do:** Exercise and fixture-test the pipeline's operational surface on the E5.3 core: chain mode (a 2-link chain on the fixture repo with a stubbed PR-merge event, watcher + babysit round trigger, the `--auto-merge` path), manifest mode (run from a fixture manifest, schema-validated), resume (mid-run checkpoint), iterate (terminal-run new round with source-delta), list; plus the reviewer-backend contract matrix for **both** backends — `codex` and `copilot-cli` — covering dispatch, read-only guard, output capture, token accounting, pre-flight, and quota signature (copilot-cli via a stub CLI when the real one is absent).
- **Deliverables:** `tests/issue2pr-modes/` fixtures + backend contract tests.
- **Acceptance:** every mode round-trips against its fixture with correct run-folder state; both backends pass the six-row contract matrix; backend re-resolution on unavailability prints the documented notice.
- **Depends:** E5.3, E5.4

### Stage S6 — Advisors, reporting, runs-stats *(milestone S6)*

**E6.1 — `/vibe:advisor` + persona pack** · size M · F7.1, F7.2
- **Do:** `add [preset|--custom] | list | remove` over dual MCP registration (`.mcp.json` + `.codex/config.toml`, sentinel-owned, timeline dirs); six persona templates with tier aliases, tool scopes, turn caps, budgets.
- **Deliverables:** `commands/advisor.md`, `templates/advisors/*` ×6.
- **Acceptance:** add→list→remove round-trip leaves both config files sentinel-clean; model-pin-lint (E0.7) passes over the templates.
- **Depends:** E2.5

**E6.2 — `/vibe:trend`** · size S · F8.1
- **Do:** Re-score via E3.3, scope-matched history filtering, per-file deltas, N-snapshot trajectory, snapshot append; missing-history → baseline run; malformed → warn + treat empty.
- **Deliverables:** `commands/trend.md`.
- **Acceptance:** golden trend output on a fixture history; both degenerate-history paths covered.
- **Depends:** E3.3

**E6.3 — `/vibe:report`** · size M · F8.2
- **Do:** Fresh score + check + vocab-drift (≥5 artifacts) + history → JSON blob (scratchpad/`mktemp`, never a fixed `/tmp` path) → Python renderer → `.claude/vibe-reports/index.html` + timestamped archive; vendored graph library, file://-openable, no network.
- **Deliverables:** `commands/report.md`, `bin/vibe-report`.
- **Acceptance:** report opens file:// with charts offline; concurrent-run fixture shows no blob collision.
- **Depends:** E3.3, E3.4, E3.7

**E6.4 — `vibe-badge`** · size S · F8.3
- **Do:** Badge endpoint JSON + optional attestation sidecar from the latest history snapshot.
- **Deliverables:** `bin/vibe-badge`.
- **Acceptance:** endpoint JSON validates against the shields.io schema; refresh path exercised (full wiring into self-check happens in E8.4).
- **Depends:** E3.3

**E6.5 — `/vibe:refresh-knowledge`** · size S · F8.4
- **Do:** context7-driven conventions refresh (`--check|--update`; stop-with-instructions when the MCP is absent); freshness date written where E2.2 doctor surfaces staleness.
- **Deliverables:** `commands/refresh-knowledge.md`.
- **Acceptance:** absent-MCP path prints install instructions and exits cleanly; update path bumps the freshness date doctor reads.
- **Depends:** E3.1, E2.2

**E6.6 — `/vibe:runs-stats` port + fixture** · size M · F8.5
- **Do:** Port the generator (stdlib-only; freeze/signature model; `config_key`; ad-hoc isolation) with the three port changes: profile-aware ticket patterns (from E5.3's contract), reviewer labels from run metadata (D6), vendored chart library; keep `--tz` default Asia/Shanghai.
- **Deliverables:** `skills/runs-stats/` (SKILL.md + generator).
- **Acceptance:** AC-3 runs-tree fixture (golden KPIs, UTC-boundary bucketing, freeze-refresh-once, ad-hoc isolation leaves history byte-identical); charts render offline.
- **Depends:** E5.3, E0.1

### Stage S7 — Mirrors, docs, release gate *(milestone S7)*

**E7.1 — Reverse-delegation skill set (Codex-side sources)** · size M · F9.6(d), A6
- **Do:** Author the seven Codex-side skills (`claude-review/plan/implement/debug`, `audit`, `audit-fix`, `verify`) that call Claude via the pinned `claude-octopus` MCP server; pin discipline + boot-verify integration with E2.6. These are **source artifacts** consumed by E7.2's generator.
- **Deliverables:** the seven skill sources + pin file.
- **Acceptance:** one end-to-end reverse call (Codex→Claude) succeeds against the pinned server; pin mismatch fails loudly via E2.6's boot-verify.
- **Depends:** E2.6

**E7.2 — Mirror-sync generator** · size L · F9.6
- **Do:** Generator over the four source sets (19 knowledge skills; roast as `$vibe-roast` sequential variant; 6 roast agents as `$vibe-*` skills; the seven E7.1 reverse-delegation skills) with the portability exclusion list → `codex/` + `MIRROR-MANIFEST.json` (a reason per exclusion); transformation rules (frontmatter map, header rewrites, `$vibe-x` refs, AGENTS untrusted-input, manifest-stamped version); content-hash manifest consumed by `vibe-check --mirrors`.
- **Deliverables:** `scripts/mirror-sync.*`, generated `codex/` tree, `codex/MIRROR-MANIFEST.json`.
- **Acceptance:** regeneration idempotent (byte-identical); hand-edit of a mirror fails the staleness check; every exclusion carries a reason; all four source sets appear (or are reason-excluded) in the manifest.
- **Depends:** E3.1, E4.2, E4.3, E7.1

**E7.3 — Doc set + AC-6 sweep** · size M · D7, AC-6
- **Do:** README (function catalog summary, old→new command migration table, POSIX + Python 3.11+ prereqs, the D7 acknowledgement section), CLAUDE.md, PRIVACY (every claim checked against disk); implement the AC-6 legacy-string grep (`/cc-suite:`, `/nlpm:`, `/grill:`, `/codex-toolkit:`, site templates included) as a CI job.
- **Deliverables:** README.md, CLAUDE.md, PRIVACY.md, `tools/legacy-string-sweep.sh` + CI job.
- **Acceptance:** AC-6 green; doc-accuracy spot checks (counts vs disk) pass.
- **Depends:** E0.6; gate:S1, gate:S2, gate:S3, gate:S4, gate:S5, gate:S6 *(content documents everything shipped — stage-gate dependencies per §2.4b)*

**E7.4 — Release gate wiring (AC-7)** · size M · F10.3 (gate part), P7
- **Do:** `pre-release-quality-gate` workflow: `/vibe:score` ≥ Strict on the suite itself, `/vibe:test` green (14 agent specs), `vibe-check --mirrors` green, §5.0-counts-vs-disk doc-accuracy check.
- **Deliverables:** `.github/workflows/pre-release-quality-gate.yml`.
- **Acceptance:** AC-7 green on the release branch; each sub-check has a seeded-failure test proving the gate actually gates.
- **Depends:** E3.3, E3.6, E7.2, E7.3

**E7.5 — Marketplace entry + install validation** · size S · §5.0
- **Do:** Final marketplace.json, install-from-marketplace smoke on a clean profile, README install section.
- **Deliverables:** finalized `marketplace.json` + install docs.
- **Acceptance:** clean-machine install → `/vibe:doctor` reports healthy.
- **Depends:** E7.3, E7.4

### Stage S8 — Auditor deployment, rulebook loop & site *(milestone S8)*

**E8.1 — Repo provisioning (D4/D9)** · size S · Category-10 prerequisites
- **Do:** On `xinquan568/vibe-suite`: create the seven lifecycle labels, enable issues/Actions/Pages, create the `auditor-data` orphan branch, install secrets (`CLAUDE_CODE_OAUTH_TOKEN`; `PAT_TOKEN` `public_repo` with rotation doc; optional `OPENAI_API_KEY`); document everything in the runbook.
- **Deliverables:** provisioned repo settings + `auditor/README.md` runbook section.
- **Acceptance:** the AC-8 preflight checklist items all present (verified by E8.7's preflight).
- **Depends:** E0.1

**E8.2 — Auditor pipeline workflows** · size L · F10.1
- **Do:** Port the 18 `auditor-*` workflows + prompts + `SCHEMAS.md` + runbook + `cla-gate-messages/`; all contribution safety gates normative (first-contact 3/5 PR caps, 2 repos/week, maintainer-pushback gate, duplicate-open-PR filter, CLA/no-external-PR skip with logged reason, security-finding disclosure path, umbrella-issue backstop); data paths target the `auditor-data` branch; injection-separation posture (audited content is data; patch-only surface; minimum-scope PAT).
- **Deliverables:** `auditor/workflows/*` ×18, `auditor/prompts/`, `auditor/SCHEMAS.md`, `auditor/cla-gate-messages/`.
- **Acceptance:** workflow lint green; each stage dry-runs against a fixture registry issue; gate logic unit-tested where scriptable (full matrix in E8.7).
- **Depends:** E8.1, E4.1, E3.9

**E8.3 — Auditor helper scripts (30)** · size L · F10.4
- **Do:** Implement the six script groups at functional parity under `auditor/scripts/` (registry/state ×6, findings ×6, contribution ×4, reporting ×5, rulebook ×5, suppressions/discovery/batch ×4).
- **Deliverables:** the 30 scripts, each with at least a smoke test.
- **Acceptance:** all smoke tests green; `atomic-registry-write.sh` + `three-way-merge-registry.py` exercised under a simulated push conflict.
- **Depends:** E8.2

**E8.4 — Site build + rebrand (D4)** · size M · F10.3
- **Do:** Five `vibe-build-*` tools + the six site/release workflows (deploy-site, site-preview ×2, site-validate, self-check with E6.4 badge refresh, release gate already in E7.4); VitePress site rebranded (title/theme/copy/badges/bylines/dashboards — no user-facing "nlpm"); AC-6 sweep covers site templates.
- **Deliverables:** `bin/vibe-build-*` ×5, site workflows, rebranded site source.
- **Acceptance:** site builds and deploys to Pages under vibe-suite branding; AC-6 site clause green.
- **Depends:** E8.1, E6.4, E0.6

**E8.5 — Data migration execution (D9)** · size S · §7A row 9
- **Do:** Run `tools/migrate-auditor-data.sh` against the real repo's `auditor-data` branch; verify count+hash manifest; confirm doctor's "migration pending" clears.
- **Deliverables:** migrated ops data on `auditor-data`; verification log committed to the runbook.
- **Acceptance:** AC-5 row 9 executed for real: complete copy, idempotent re-run, originals untouched.
- **Depends:** E8.1, E0.8, E8.2

**E8.6 — Rulebook feedback loop (F10.2)** · size M · F10.2
- **Do:** The self-evolution tooling: `exemplar` workflow + `cite-exemplars` (build-time citation blocks into the rules skill, against the migrated `auditor-data`), `refine-rules` + `rule-review` (propose → human-review), `docs-diff` (upstream-docs drift feeding E3.8), the ledgers (`disagreements.jsonl`, `vocab-advisories.jsonl`, suppressions), and `validate-rule-ids.py` wired into the audit stage.
- **Deliverables:** the feedback workflows + `auditor/scripts/` rulebook group wiring + regenerated exemplar citations in `skills/rules/`.
- **Acceptance:** cite-exemplars run against the migrated data produces valid citation blocks (E3.1's placeholders filled); `validate-rule-ids.py` blocks a seeded rule-ID drift; each ledger has a write+read round-trip test.
- **Depends:** E8.2, E8.3, E8.5, E3.1
- *(Note: E8.3's rulebook-group scripts are the mechanics; this item delivers the workflows + integration.)*

**E8.7 — `auditor-integration-test` green (AC-8)** · size M · AC-8
- **Do:** The full AC-8 matrix: required-secrets preflight (optional `OPENAI_API_KEY` absence must pass), cover-generation fallback path (templated SVG, article still publishes), one test per contribution gate (PR caps, weekly cap, pushback, duplicate filter, CLA skip, disclosure routing, umbrella backstop), security checklist sign-off before the first external audit.
- **Deliverables:** `auditor/workflows/auditor-integration-test.yml` + its test cases.
- **Acceptance:** AC-8 green in `xinquan568/vibe-suite`.
- **Depends:** E8.1, E8.2, E8.3, E8.4, E8.5, E8.6

---

## 4. Acceptance-criteria coverage map

| AC | Satisfied by |
|---|---|
| AC-1 coverage walk | E0.6 (tooling) — kept green by every later port item |
| AC-2 determinism | E2.1 (idempotent bridges), E3.3 (score ×3), E3.5 (exit 0 on suite) |
| AC-3 equivalence fixtures | E3.3 (score golden penalty total on `defective-skill/`), E4.1 (nl-audit types), E4.3 (roast sample-repo, codex + conditional agy lanes), E5.2 (flawed-plan), E5.5 (scaffolder), E6.6 (runs-tree) |
| AC-4 loop bounds | E5.6 (harness over E4.4, E5.2, E5.3) |
| AC-5 migration | E2.8 (rows 1–8, 10), E0.8 (row 9 fixture), E8.5 (row 9 execution) |
| AC-6 no legacy strings | E7.3 (sweep incl. site), E2.6 (update strings), E8.4 (site clause) |
| AC-7 quality gate | E7.4 |
| AC-8 auditor pipeline | E8.7 (full matrix), E8.1 (prereqs) |
| AC-9 division of labor / no pins | E0.7 (a: lint), E1.7 (b: contract gate + runner-level fallback fixtures), E4.1 (b: command-level post-flip fallback + both-absent manual fallback), E4.3/E4.5 (b: agy-lane coverage post-gate, incl. the security-scan second-opinion lane), E2.7 (c: config visibility), E0.4 (fallback chain definition) |

## 5. Sequencing summary

- **Critical path:** E0.1 → E0.5 → E1.1 → E5.3 → E5.4/E5.5, and E0.1 → E3.1 → E3.3 → E4.1 → E8.2 → E8.7.
- **Parallel tracks after S0:** (a) S1 engines, (b) S3 quality engine — fully independent (S3's cross-engine lanes were moved to E4.5).
- **Suggested first issue chain (issue2pr chain mode takes 2–10 issues):** E0.1 → E0.2 → E0.3 → E0.4 → E0.5 → E0.6 → E0.7 → E0.8 (all of S0, 8 links).
- **Totals:** 62 work items — S0:8 · S1:7 · S2:8 · S3:9 · S4:5 · S5:7 · S6:6 · S7:5 · S8:7. Sizes: 17 S · 36 M · 9 L.

---

## Assumptions & open questions

**Assumptions (proceeding on these unless corrected):**
- A1. `codes/vibe-suite` currently contains only README + LICENSE; everything is greenfield, and all work lands there via PRs (each issue → one PR, per the issue2pr workflow).
- A2. Milestones map 1:1 to stages S0–S8; the issue-generating AI follows §2 verbatim (including the two dependency kinds in §2.4).
- A3. The three source repos remain available read-only at their pinned commits for reference during implementation; per D7, code is written fresh in vibe-suite.
- A4. CI runs on GitHub Actions in the same repo; runners have Python 3.11+, Node (declared floor), bash — POSIX-only per §8 of the merge proposal.
- A5. Fixture-dependent items (AC-3/AC-4/AC-5) count their fixtures as part of the same work item — no separate fixture issues.

**Open questions for the owner:**
- OQ1. **Issue granularity:** 62 issues at the sizes listed — acceptable, or should S-sized neighbors be merged (e.g. E2.3 into E2.2, E6.4 into E6.2) to reduce issue count?
- OQ2. **Stage gates as PR gates:** should each stage's gate be enforced as a required CI check on `main` from that stage onward (recommended), or tracked manually per milestone?
