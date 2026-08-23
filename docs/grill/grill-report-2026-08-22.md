---
plugin: grill
version: 1.3.0
date: 2026-08-22
target: codes/vibe-suite
style: Hard-Nosed Critique + Roadmap
addons: [hidden-costs, principle-violations, assumptions-audit, compact-optimize]
agents: [recon, architecture, error-handling, security, testing]
---

# Grill Report — vibe-suite (v0.0.1, `main` @ `090b511`)

All paths below are relative to `codes/vibe-suite/`. Every finding carries the agent that produced it (`[arch]`, `[eh]`, `[sec]`, `[test]`); where several agents hit the same defect the version with the strongest evidence was kept and the others are credited. Severity tags follow grill-core: `[CRITICAL]` security/data-loss/correctness, `[HIGH]` significant reliability/maintainability/perf, `[MEDIUM]` noticeable, `[LOW]` minor, `[GOOD]` worth keeping.

**Run notes.** All five agents completed; none timed out. The security agent's fourth sub-audit (prompt-injection / secrets / least-privilege) did not report independently — that surface was covered by the security agent's own first-hand reading; `scripts/agy-runner.mjs`/`agy-fallback.mjs` prompt assembly and the `refine-proposal` prompt build were not read line-by-line and should be treated as unaudited. The testing agent ran both suites read-only: Python `2726 tests OK (skipped=1)` in **482.6 s** serial; Node 238 pass in 15.3 s. No `[CRITICAL]` was assigned by any agent.

---

## 1. Verdict in one paragraph

vibe-suite is a deliberately engineered plugin whose engine core — event-stream verdicts, hard-link CAS job store, confirmed group reaping, fail-closed config grammar, audited fd-relative write primitive, latch-synchronised race tests — is better than most production services. The problems are not in what the core does; they are in (a) **trust-boundary confusion**: repository-controlled files (`.vibe-suite/agents/*.md`, `.vibe-suite.md`) and third-party text (GitHub issues, PR comments, audited repos) are treated as operator intent at several points, one of which reaches `bypassPermissions` + Bash; (b) **seams the design does not reach**: a fail-closed gate neutralised by a YAML typo two files away, a deadline defeated by a leaked pipe, engine stderr thrown away, an unbounded state directory, a fixed scratch name that wedges every later write; and (c) **doctrinal debt**: the repo repeatedly states "one reader / one primitive / one table" and then ships eleven YAML-frontmatter parsers, two safety kernels, twelve hand-held cross-pinned pairs, and ~20k lines of an inert stage (`auditor/`) that the README says is "documentation only". The biggest single risk is H1 — a cloned repo can register an attacker-authored MCP advisor with `permission_mode: bypassPermissions` and `allowed_tools: [Bash]` during `/vibe-suite:init` with no confirmation.

---

## 2. Critical flaws (HIGH findings, deduplicated)

| ID | Flaw | Where | Agent | Effort |
|---|---|---|---|---|
| **H1** | Repo-shipped advisor definitions auto-registered as MCP servers with `bypassPermissions` + Bash during `init` | `scripts/lib/advisors.py:43,52,192-205,280-300,305-330`; `scripts/lib/init_bridge.py:316-325` | sec S1 | < 1 week |
| **H2** | issue2pr chain: any GitHub commenter triggers autonomous edits; no untrusted-input rule in the skill; `--auto-merge` re-arms | `scripts/watch_pr.py:129-140,172-174`; `skills/issue2pr/references/operational-modes.md:239,296-299`; `skills/issue2pr/SKILL.md` | sec S6 | < 1 week |
| **H3** | Stored XSS: finding rows built with `innerHTML`, `{{PROJECT}}` raw | `templates/report/assets/vibe-report.js:27-34`; `auditor/scripts/render-repo-report.py:178-183`; `templates/report/repo-audit.html:26,31` | sec S10 | < 1 day |
| **H4** | Staged auditor workflow: privileged `publish` job `source`s a file a Claude-with-Bash job could rewrite (RCE with write token once wired) | `auditor/workflows/auditor-exemplar.yml:103-120,169-170` | sec S16 | < 1 day |
| **H5** | `gate.fail_policy: closed` defeated by an unreadable `.vibe-suite.md` (or missing python3) → gate fails **open**; stderr of the store dropped | `scripts/stop-review-gate-hook.mjs:219-238,249-250`; `scripts/lib/store.py:141-180`; `scripts/lib/config.py:606-648` | eh A1 | < 1 day |
| **H6** | `runWithDeadline` resolves on `"close"`; a descendant holding the stdout pipe defeats the deadline; heartbeat keeps the job "healthy" forever | `scripts/lib/process.mjs:92,106-117,129-133,158-173`; `scripts/codex-runner.mjs:273-291` | eh B1 | < 1 day |
| **H7** | Engine stderr, `signal`, and `malformedLines` discarded; background worker `stdio` all `"ignore"` — crashes outside the try leave `running` records with no trace | `scripts/codex-runner.mjs:293-318,384-388`; `scripts/agy-runner.mjs:161-183`; `scripts/lib/jobs.mjs:114-145`; `scripts/lib/events.mjs:44,77` | eh B2 | < 1 day |
| **H8** | Job store unbounded: slots never pruned, each 30 s heartbeat = new slot + 4 fsyncs, `rawOutput` uncapped and stored twice, `readdir` per read, Stop gate `ENOBUFS` → fails open | `scripts/lib/jobs.mjs:65-69,159-171,243-277,411-476`; `scripts/lib/process.mjs:100-107`; `scripts/stop-review-gate-hook.mjs:65,296` | eh C1, arch §9 | < 1 week |
| **H9** | `bridge.write_atomic` uses a **fixed** scratch name; a crash between `os.open` and `os.replace` wedges every later write to that target (`.mcp.json`, `state.json`, `CLAUDE.md`, `chain.json`…); concurrent writers collide; no reaper | `scripts/lib/bridge.py:477-487` (vs random `_scratch` at 365-381) | eh C2, arch §3, sec S18 | < 1 day |
| **H10** | Eleven hand-rolled frontmatter/YAML parsers against a stated "one reader, no second parser" doctrine; `config.ARTIFACT_KEY` seam has no callers | `scripts/lib/config.py:263`; `scripts/score_engine.py:413-862`; `scripts/check_engine.py:301-620`; `scripts/lib/advisors.py:83-121`; `scripts/mirror-sync.py:103-120`; `scripts/mechanical_fix.py:53`; `scripts/profile_lint.py:91`; `scripts/write_profile.py:168`; `scripts/lib/init_bridge.py:143`; `bin/vibe-check:222`; `skills/runs-stats/scripts/generate_runs_stats.py:416` | arch §8 | < 1 month |
| **H11** | `auditor/` inert S8 stage (18 workflows, 30 scripts, 10.8k lines + ~10k lines of tests) in-tree and installed to every user; README says "documentation only" | `auditor/`, `tests/test_auditor_*.py`, `README.md:9-11` | arch §7 | < 1 week |
| **H12** | `generate_runs_stats.py`: 1,672-line god file under `skills/`, outside write discipline (`Path.write_text` at 1340, 1607, 1657-1658), ~1 test per 84 lines, zero unit tests on its seven parsers | `skills/runs-stats/scripts/generate_runs_stats.py`; `tests/test_runs_stats.py` | arch §8, test §1 | < 1 week |
| **H13** | CI acceptance gates `loop-bounds` (AC-4), `coverage` (AC-1), `legacy-strings` (AC-6) are advisory by `ci.yml`'s own comment (only three contexts required); no `timeout-minutes` on any job | `.github/workflows/ci.yml:136,142,243,262` | test §6 | < 1 day |

### Specific examples (the ones that should convince a sceptic)

- **H1 exploit chain.** `load_definitions` reads `<workspace>/.vibe-suite/agents/*.md`; `PERMISSION_MODES` includes `"bypassPermissions"` (`advisors.py:52`); `_advisor_env` exports `CLAUDE_PERMISSION_MODE`/`CLAUDE_ALLOWED_TOOLS`/`CLAUDE_ADDITIONAL_DIRS`/`CLAUDE_SYSTEM_PROMPT` (293-294); `init_bridge.install` calls `advisors.reconcile(ws)` unconditionally (322). A cloned repo with `helper.md` → `permission_mode: bypassPermissions`, `allowed_tools: [Bash]`, `additional_dirs: [~]` → `/vibe-suite:init` registers `npx -y claude-octopus@1.2.0` with that env into `.mcp.json` and `.codex/config.toml`. The codex lane requires `--confirm-danger` for `danger-full-access` (`codex-runner.mjs:190-203`); advisors have no equivalent.
- **H5.** `effectiveGate()` returns `null` on any non-zero exit (`:223`), `applyFailPolicy(null, …)` reads `gate?.fail_policy ?? "open"` (`:233`); `store.py:154` calls `config.load(workspace)` with no fallback, and `_cli` (175-179) catches only `Store*` errors — so a `ConfigSyntaxError` from the *user-edited* `.vibe-suite.md` is a traceback, exit 1, gate open. `tests/node/stop-gate.test.mjs:242-251` pins this as "unreadable config fails open by default" — but the stored *closed* policy is what gets ignored.
- **H6.** `process.mjs:158` resolves on `child.on("close")` with no `exit` handler; codex is spawned non-detached (`codex-runner.mjs:275-291`), so SIGTERM/SIGKILL reach only codex; a `workspace-write` delegate that starts `npm test --watch` inherits the pipe → promise never settles → heartbeat cleared only in `cleanup()` (129-133) → `isAbandoned` (jobs.mjs:391-404) says healthy.
- **H9.** `tmp_name = f".{dest.name}.vibe-tmp"` (477); `except FileExistsError → BridgeError("… already exists; refusing to write through it")` (482-484); cleanup is Python-exception-only (498-503). `publish_new` twenty lines above already uses the random `_scratch`.
- **H10.** `config.py:37-42` itself records that the scoring engine "now carries its own permissive artifact parser"; `score_engine._FrontmatterParser` is ~450 lines, `check_engine._reg_*` ~320 lines. The same SKILL.md frontmatter can parse differently in `score`, `check`, `fix`, `vibe-check`, `mirror-sync`, and `advisor`.
- **H13.** `ci.yml:136-142` says "a fourth job … could fail without blocking a merge — a gate that exists and does not gate", then defines three more standalone jobs. Branch protection was not readable from the checkout; the claim is the file's.

---

## 3. Red flags (patterns, not single defects)

1. **"Shipped disabled" is store-only.** `gate.stop_review_gate`, `gate.fail_policy`, `gate.model`, and `sandbox` are all admitted from the repo file `.vibe-suite.md` (`config.py:66-82,96-98`); `store.effective_config` layers the store *over* the file, so a clone can switch on a 900 s egress hook and make it fail closed (`tests/test_store.py:184-189` proves the file path). `[sec S2, MEDIUM]`
2. **Verify-after-delegate runs repo scripts unsandboxed.** `commands/delegate.md:63,81-90`: engine runs with `workspace-write`, then `./run-tests.sh` / `npm test` execute in the operator's shell. `[sec S3, MEDIUM]`
3. **A bare, non-existent `vibe-suite` command is registered in three trust-bearing files** (`.mcp.json`, `.codex/config.toml`, `.codex/hooks.json`) — `init_bridge.py:228-234,298-305` — and committed into the user's repo. Binary-planting slot until the binary exists. `[sec S4, MEDIUM]`
4. **Observability is "one stderr line at exit 0", visibility assumed.** Every hook report — abandoned job, unreadable job, fail-open notice, "run /vibe-suite:score" — is stderr + exit 0 (`session-lifecycle-hook.mjs:32-49`, `check-artifact.sh:46`, `stop-review-gate-hook.mjs:236,325`); no `systemMessage`, no durable log anywhere (zero `import logging`, zero log-level env). `[eh A2/G, MEDIUM]`
5. **The highest-volume external call bypasses the dispatcher.** issue2pr reviewer dispatch is specified as bare `codex exec … < /dev/null` in prose (`skills/vibe-core/references/reviewer-contract.md:32-40`); no deadline, no record, no quota classification — the runner's guarantees do not cover it. `[eh E2, MEDIUM]`
6. **Prompt and one-time claim token travel in argv** to the detached worker (`codex-runner.mjs:384-385`) — readable via `ps`/`/proc`, and re-introduces E2BIG. `[sec S7, MEDIUM]`
7. **Supply chain inside the Claude auth boundary is version-pinned, not integrity-pinned.** `npx -y claude-octopus@1.2.0` (`mcp_pin.py:66-75`), identity verified only via the package's self-reported `serverInfo` (`boot_probe.mjs:99-116`); TOML registration written before the probe and not rolled back on failure (`update.py:148-159`). `[sec S13, MEDIUM]`
8. **Two safety kernels, one invariant list nowhere.** `write.mjs` (path-based, weaker guarantees disclosed) vs `bridge.py` (fd-relative); random scratch names exist in `write.mjs:150-165` and `bridge.publish_new` but not `bridge.write_atomic`. Every lesson must be learned twice. `[arch §4, MEDIUM]`
9. **Shared partials are include-by-link.** Nothing inlines `commands/shared/*.md`; ten commands' engine resolution depends on the model choosing to Read a 125-line partial whose ladder already exists as six lines of code (`config-bridge.mjs:61-67`). `[arch §2, MEDIUM]`
10. **Tests that pin text of tests.** `tests/test_issue2pr_modes.py:489-497`, `tests/test_migration_fixtures.py:214-218`, `tests/test_mode_driver.py:830` assert on other test files' source. 19 modules / 530 tests (19 %) execute no code at all. `[test §2, MEDIUM]`
11. **Self-description drift.** `hooks/README.md:24` ("`/vibe-suite:config` … not yet built" — it ships), `write.mjs:35-36` ("AST lint … NOT delivered" — it is), `commands/check.md:10-11` ("`bin/vibe-check`, when it lands"), `init_bridge.py:10-12`, `README.md:10-11` (auditor "documentation only"). `[arch §10, eh K, LOW]`

---

## 4. The 80/20 rewrite plan

The 20 % of change that retires ~80 % of the risk, in execution order. None of it is a rewrite of the engine core — that should stay.

| # | Track | What changes | Retires |
|---|---|---|---|
| 1 | **Trust-boundary hardening** (< 1 week) | Advisors: refuse `bypassPermissions`/`dontAsk`/`auto` and out-of-workspace `cwd`/`additional_dirs` without a `--confirm-danger`-style flag; never auto-reconcile in `init`; hash-stamp definitions. Config: make `gate.*` store-only (drop from `CLOSED_MAPS`). issue2pr: inline the vibe-core untrusted-input rule into `skills/issue2pr/SKILL.md`, `refine-proposal`, `continue`, `advisor`; `watch_pr.py` emits `author_association`, chain babysits only on `OWNER|MEMBER|COLLABORATOR`, never re-arms `--auto-merge` after a non-collaborator round; slug rule for `{slug}`. Delegate: confirm before executing repo-resident scripts. | H1, H2, S2, S3 |
| 2 | **Engine-seam robustness** (4 × < 1 day) | `write_atomic` → random `_scratch`; `runWithDeadline` → resolve on `exit` + bounded drain + stop heartbeat after SIGKILL; persist `stderrTail`/`signal`/`malformedLines`, give the worker a 0600 log sink; `store.effective_config` degrades (store gate + `config_error`) so a stored `fail_policy: closed` still blocks, hook emits `systemMessage`; wrap `prepareRecord` so a result line is always emitted. | H5, H6, H7, H9, M7 |
| 3 | **Job-store lifecycle** (< 1 week) | `jobs prune [--older-than 7d]` (terminal jobs only — safe because `transact` refuses terminal records); compact slots on finalise; cap `rawOutput` at 16 MB with disclosed truncation; `highestSlot` via existence probes not `readdir`; document heartbeat fsync cost. | H8 |
| 4 | **One frontmatter grammar** (< 1 month) | `scripts/lib/frontmatter.py` with `split()` + `parse(mode="strict"|"artifact")`; route the eight small helpers through `split`; `check_engine` registry parser on the same block-mapping core; `config.py` stays the schema owner. Then split `score_engine`/`check_engine` into packages. Do the `scripts/lib/__init__.py` bootstrap first. | H10, M16, L12 |
| 5 | **Shed inert weight** (< 1 week, product decisions) | Move `auditor/` + its 13 test modules to a staging branch/sibling repo (carry H4/S17 fixes with it), fix the README sentence; decide the agy lane (demote to `ConfigValueError` or re-scope the gate — not both); move `tests/source-manifests/` and `docs/discussion/` off the install path. | H11, M14, M15 |
| 6 | **CI that gates** (< 1 day + < 1 day) | Register `loop-bounds`/`coverage`/`legacy-strings` as required contexts or fold into `test`/`lint`; `timeout-minutes` on every job; shard the Python suite 4-way (482 s → ~2-3 min); floor matrix py 3.11 / node 18 + weekly macOS leg; add `node --test` to CLAUDE.md's battery; stop the temp-dir leak. | H13, M32, M34 |
| 7 | **Render safely** (< 1 day) | `createElement`/`textContent` rows + CSP meta in `templates/report/`; HTML-escape `args.repo`; one `md_escape()` for the five site builders + `markdown.html=false`; never `source` artifact content in auditor workflows. | H3, H4, M23 |

---

## 5. Prioritized backlog (15 items, ranked by impact × risk ÷ effort)

| Rank | Item | Sev | Impact | Risk if left | Effort | Findings |
|---|---|---|---|---|---|---|
| 1 | Advisor definitions: refuse dangerous modes without confirmation; no auto-reconcile in `init` | HIGH | Closes repo→`bypassPermissions` chain | Exploitable on first `init` in a hostile clone | < 1 week | H1 |
| 2 | issue2pr: untrusted-input rule + `author_association` filter + no auto-merge re-arm | HIGH | Closes comment→merge pipeline | Public repos with `--auto-merge` | < 1 week | H2 |
| 3 | `write_atomic` random scratch name | HIGH | Un-wedges config writes after any crash | Opaque permanent failure of `init`/`config`/`score --history` | < 1 day | H9 |
| 4 | Honour stored `fail_policy: closed` on unreadable config; `systemMessage` | HIGH | Makes the one "when in doubt, block" setting reliable | Silent fail-open | < 1 day | H5 |
| 5 | Deadline on `exit` + drain; stop heartbeat after kill | HIGH | "Deadline-bounded" becomes true | Eternal `running` jobs | < 1 day | H6 |
| 6 | Persist `stderrTail`/`signal`; worker log sink | HIGH | Failed external calls become diagnosable | Every codex flag/auth failure is "no terminal event" | < 1 day | H7 |
| 7 | XSS: `textContent` rows + CSP; `md_escape` in site builders | HIGH/MED | Removes stored XSS from reports/site | Cross-origin once served from Pages | < 1 day | H3, M23 |
| 8 | `jobs prune` + finalise compaction + `rawOutput` cap + O(1) `highestSlot` | HIGH | Bounded state dir; gate cannot `ENOBUFS`-open | Linear growth per workspace | < 1 week | H8 |
| 9 | CI: required contexts + `timeout-minutes` + shard + floor matrix | HIGH/MED | Gates gate; 8-min suite → 3 | Advisory AC gates; 6 h hung jobs | < 1 day | H13, M34 |
| 10 | `gate.*` store-only; delegate verify confirmation; `vibe-suite` bare-command registration removed | MED | Repo content cannot flip hooks/sandbox or run scripts | Clone-time surprises | < 1 day each | S2, S3, S4 |
| 11 | `generate_runs_stats.py`: move under `scripts/runs_stats/`, templates out, route writes through bridge, unit-test parsers | HIGH | Largest file becomes testable and audited | Unaudited writes into `runs/_reports/`; next refactor is blind | < 1 week | H12 |
| 12 | Prompt/token off argv; `--` separator; `--skip-git-repo-check` only for read-only | MED | No `/proc` leak of diffs/tokens; E2BIG gone | Local disclosure; race on claim | < 1 day | S7, S15 |
| 13 | `auditor/` out of tree (with S16/S17 fixes); README corrected; agy-lane decision | HIGH/MED | −20k lines from battery and installs | CI time, onboarding load, misleading README | < 1 week | H11, M14, M15 |
| 14 | `frontmatter.py` consolidation → then `score`/`check` package splits | HIGH | One grammar, one edge-case suite, ~800 fewer lines | Divergent parses across six engines | < 1 month | H10, M16 |
| 15 | `claude-octopus` integrity pin (lockfile/tarball sha256, `--ignore-scripts`), roll back TOML on probe failure | MED | Closes registry/transitive compromise of the Claude-session driver | Auth-boundary supply chain | < 1 week | S13 |

---

## 6. Quick wins

### < 1 day (each independently shippable)
- H3 `templates/report/assets/vibe-report.js:27-34` → `createElement`/`textContent`; escape `args.repo`; CSP meta.
- H4 `auditor/workflows/auditor-exemplar.yml:169-170` → parse `KEY=VALUE` strictly or use job outputs; never `source`.
- H5 `store.py effective_config` degrade path + hook `systemMessage`; test: broken `.vibe-suite.md` + stored `closed` → BLOCK.
- H6 `process.mjs` resolve on `exit` + `graceMs` drain + `pipesLeaked` flag; stop heartbeat post-SIGKILL.
- H7 `stderrTail`/`signal` in `RECORD_SHAPE`; worker `stdio` → `.vibe-suite-state/jobs/<id>.log` (0600).
- H9 `bridge.write_atomic` → `_scratch`.
- H13 required contexts + `timeout-minutes: 25/10`.
- M7 wrap `prepareRecord` in the result-line guard (`codex-runner.mjs:350-370`).
- M10 `_open_dir_chain(create=False)` default; `create=True` only from `ensure_dir_at`/`write_atomic`/`publish_new`/`symlink_at` (`bridge.py:157-168`).
- M13 `_roast_variant` body → `codex-src/vibe-roast/SKILL.md.tmpl`, hashed (`mirror-sync.py:239-330`).
- S2 drop `gate.*` from `CLOSED_MAPS` (`config.py:96-98`) or require a stored `stop_review_gate: true` first.
- S3 `commands/delegate.md:81-90` confirm-before-run / refuse if `run-tests.sh`/`package.json` dirty.
- S4 remove bare `vibe-suite` registrations (`init_bridge.py:228-234`) until the binary ships; then absolute path.
- S5 validate env var names `[A-Za-z0-9_]` (`bridge_cli.py:124-127`).
- S7 prompt-file path + token via 0600 file/fd to the worker (`codex-runner.mjs:384-385`); `--` before prompt (219).
- M2 `timeout=60` on every `gh` call + degraded-probe counter (`watch_pr.py:77-81,122-140`).
- M3 let `ConfigBridgeError` propagate in `agy-runner.resolveModel` (`agy-runner.mjs:69-81`).
- M27 four `events.mjs` unit tests; fix `tests/fixtures/fake-codex/emitter.mjs:22` to the real `item.agent_message` shape.
- M29 three hook tests: garbage stdin, `sleeper.mjs` inside the Stop budget, `--event bogus` → exit 2.
- M32 temp-dir cleanup (`addCleanup` in five auditor modules; shared `tests/node/_tmp.mjs`).
- M30b delete the three meta-tests; dedupe the `watch_pr` existence tests.
- L-items: duplicate `pin_root`/`_ROOT_PIN` (`bridge.py:105-123,280-283,420-435`); stale self-docs (five sentences); `publish` exit code (`bridge.py:849`); config warnings forwarded on dispatch; preflight rows for `python3`/`git`; `awaitWorkerClaim` error names its budget; `-c core.fsmonitor= -c core.hooksPath=/dev/null` in the gate's git argv; `--skip-git-repo-check` only when `sandbox === "read-only"`.

### < 1 week
- H1 advisor gate + no auto-reconcile + hash stamps.
- H2 issue2pr untrusted rule + author filter + slug rule + no auto-merge re-arm.
- H8 `jobs prune` / compaction / cap / O(1) reads.
- H11 `auditor/` to staging (with S16/S17 fixes); README sentence.
- H12 `generate_runs_stats.py` relocation + parser unit tests + corrupt-run fixture.
- M4 route issue2pr reviewer dispatch through `codex-runner.mjs --kind review`.
- M5 append-only NDJSON `events.log` + `jobs log`.
- M6 `scripts/lib/cli.mjs` (`UsageError`, `runMain`, `parseLastJsonLine`, `readValue`); quota table into `events.mjs`; Stop hook uses `readEventStream`; one Python JSON loader.
- M8 `config_cli.py resolve-engine` seam; shrink `model-selection.md`.
- M9 split `bridge.py` → `fsafe.py` + `bridge.py`.
- M11 shared write-invariant fixture matrix run against both kernels.
- M12 pin the three comment-held pairs; derive `SLASH_LITERAL` and `TARGETS`; `mirror_tables.py`.
- M14 agy-lane decision; M15 install-weight trim; M17 extend AST lint to `bin/` + `skills/*/scripts` (after H12 and `vibe-report` routing).
- M24/S13 integrity pin for `claude-octopus`; M28 bridge primitive unit tests + fail-after-tmp-write; M35 specs for top commands/skills + scheduled judgment-lane run.

---

## 7. Add-on: Hidden costs (five, with evidence)

1. **Operational — the state directory grows forever and the gate can choke on it.** Slot files never deleted (`jobs.mjs:246-250`); every heartbeat a slot + four fsyncs; `rawOutput` unbounded and stored twice; `listRecords` is O(jobs × files) and runs on every SessionStart/End (`session-lifecycle-hook.mjs:34`) and every 25 ms in `awaitWorkerClaim` (`codex-runner.mjs:460-468`); a chatty review exceeds the gate's 8 MB `maxBuffer` → `ENOBUFS` → fail open. Plus a python3 interpreter spawn on **every** Stop even when the gate is disabled (`stop-review-gate-hook.mjs:276` before `:278`) and on every engine dispatch (`config-bridge.mjs:33`). `[eh C1, arch §1/§9]`
2. **Debugging — failures leave no trace.** Engine stderr discarded (`codex-runner.mjs:293-318`); worker stdio `/dev/null` (386); no log framework, no durable log, hook reports on stderr at exit 0 whose visibility is unverified; config warnings discarded on the dispatch path (`config.py:636-638`); `watch_pr` degrades silently for hours (`watch_pr.py:125-138`); "why did the gate fail open yesterday" is unanswerable. `[eh A2/B2/G/F2]`
3. **CI and developer time — an 8-minute serial suite that leaks.** 482.6 s serial for 81 modules (58 subprocess-heavy); ~600 temp dirs / 57 MB leaked per run (every `tests/node/*.test.mjs` `mkdtempSync` without cleanup; five auditor modules with 0 cleanup); 19 % of tests are prose pins; three meta-tests pin other tests' source; a byte-for-byte golden of a shipped reference doc (`tests/fixtures/issue2pr/goldens/operational-modes.md`); the `test` job fetches three upstream repos from github.com before running anything (`ci.yml:184-205`); no code-coverage measurement exists (the job called "coverage" checks `docs/disposition.yaml`). `[test §2/§5/§6]`
4. **Onboarding and install weight — a third of the repo is inert or dev-only, and it ships.** `auditor/` ~20k lines (code + tests) for an unshipped stage; agy lane ~800 lines behind an un-passable gate (`docs/agy-flip-checklist.md:16-45`); `tests/` is 441 files / 7.5 MB and the plugin installs by copying the repo root (~310 runtime-necessary files of 813); vendored `g6.min.js` 1.38 MB; eleven parsers and five JSON-load wrappers to learn; exit-code vocabularies that differ per CLI with no registry (`2` = usage / closed-without-merge / refusal / not-installed / gated-shut). `[arch §7, eh E]`
5. **Velocity — two-handed edits everywhere.** Two safety kernels with separate AST lints; twelve cross-pinned pairs (three held only by comments: Stop-hook budget `hooks.json:10` ↔ `stop-review-gate-hook.mjs:53-55`; `SLASH_LITERAL` ↔ `commands/` — currently contains `scan` which is not a command and omits 13 real ones; `init_bridge.TARGETS` (9) ↔ `bridge.OWNED_BLOCKS` (6)); a committed generated `codex/` tree (45 files) that must be regenerated on every knowledge-skill edit or `--mirrors` fails; prose-pinning tests that fail on wording changes; golden-pinned issue2pr steps that make routing the reviewer through the runner a large diff. `[arch §4/§5/§6, eh J]`

---

## 8. Add-on: Principle violations

**Single responsibility**
- `scripts/lib/bridge.py` (859) is named for one feature but is the fs-safety kernel for the whole Python half — descent, atomic write/publish, provenance, five codecs, sentinel inventory, CLI; 18 importers including `score_engine`, `trend_engine`, `mirror-sync`, `issue2pr_mode_driver`. `[arch §3, MEDIUM]`
- `_open_dir_chain` creates directories as a side effect of *opening*, so `lstat_at`/`unlink_at` — read/delete primitives — mutate; `remove_tree_at` works around it with an `lexists` probe (`bridge.py:229-232`), other callers do not (`advisors.py:358-365,453-457`). `[arch §3, eh C, sec S19 — MEDIUM]`
- `generate_runs_stats.py` (1,672): discovery, normalisation, aggregation, two HTML shells with embedded JS, bucket/freeze/history, CLI — in one file under a skill dir. `[arch §8, HIGH]`
- `score_engine.py` (1,386) and `check_engine.py` (821) each mix a parser, classification, a dozen rule functions, history, and CLI. `[arch §8, MEDIUM]`
- `bin/vibe-check` carries a 220-line mirror checker inside a structural validator. `[arch §8, LOW]`

**Single source of truth / dependency inversion**
- Eleven frontmatter/YAML parsers vs `config.py:3-8` and `config-bridge.mjs:4-9` "one reader, no second parser". `[arch §8, HIGH]`
- The engine-resolution ladder exists in prose (`commands/shared/model-selection.md`, 125 lines, include-by-link) and in code (`config-bridge.mjs:61-67`); no test compares them. `[arch §2, MEDIUM]`
- `_roast_variant` (`mirror-sync.py:239-330`) restates `commands/roast.md` + `scope-parse.md` inside the generator; the manifest hashes the *unused* source. `[arch §6, MEDIUM]`
- Three views of "what is ours": `init_bridge.TARGETS`, `bridge.OWNED_BLOCKS`, `unbridge._is_suite_state`/`_is_recognisably_ours`; `bridge.py:14` still says "six targets". `[arch §9, LOW]`
- Stop hook re-implements agent-message extraction (`stop-review-gate-hook.mjs:197-217`) instead of `events.readEventStream`; quota phrase tables in three places with three lists; `DEFAULT_TIMEOUT_MS` twice; "poll until group gone" three times; `UsageError` declared in four files; five Python JSON loaders; duplicate `pin_root`. `[eh J, arch §4 — MEDIUM]`
- Exit-code contracts differ per CLI with no registry. `[eh E, LOW]`

**Least privilege**
- Repo file → `bypassPermissions` + Bash MCP server, auto-registered (`advisors.py`, `init_bridge.py:322`). `[sec S1, HIGH]`
- Any GitHub commenter → autonomous edits; worker has no untrusted-text rule; `--auto-merge` re-arms (`watch_pr.py:172-174`, `operational-modes.md:239,296`). `[sec S6, HIGH]`
- Repo `.vibe-suite.md` → Stop-hook activation, `fail_policy: closed`, sandbox default (`config.py:66-82,96-98`; `store.py:155-157`). `[sec S2, MEDIUM]`
- `delegate` verify executes repo scripts unsandboxed after a `workspace-write` engine (`commands/delegate.md:86-89`). `[sec S3, MEDIUM]`
- Claim token + full prompt in worker argv (`codex-runner.mjs:384-385`). `[sec S7, MEDIUM]`
- Staged auditor workflows: Claude with Bash under a denylist (`Bash(curl:*)`, `Bash(git:*)` — not `bash -c`, `python3`, `printf >`) with `GH_TOKEN` at workflow level (`auditor-exemplar.yml:9,120`, `auditor-refine-rules.yml:34,118`, `auditor-classify.yml:89`, `auditor-contribute.yml:468-471`); `${{ inputs.* }}` interpolated into `run:` (`auditor-audit.yml:61-62`, `auditor-case-study.yml:73-74`); privileged job sources model-writable file. `[sec S16/S17, HIGH/MEDIUM]`
- "All Python mutation through the audited primitive" is enforced for `scripts/` only; `bin/vibe-report:400-433` hand-rolls `mkstemp`+`os.replace` and follows a symlinked out-dir; five `bin/vibe-build-*` and `generate_runs_stats.py` `write_text` directly. `[arch §8, sec S12 — MEDIUM]`
- `--skip-git-repo-check` always passed, including `workspace-write` (`codex-runner.mjs:216`). `[sec S15, LOW]`
- `.claude/settings.json` hook `command` strings mirrored verbatim into `.codex/hooks.json` without confirmation (`bridge_cli.py:176`). `[sec S19, LOW]`

---

## 9. Add-on: Assumptions audit

| # | Implicit assumption | Where it lives | Status | Fast validation |
|---|---|---|---|---|
| A1 | Hook stderr at exit 0 is shown to the operator | all three hooks; `hooks/README.md:14` | Unverified; documented harness behaviour suggests transcript-only | One environment-specific test against the harness; then move reports to stdout (SessionStart) / `systemMessage` (Stop, PostToolUse). < 1 day |
| A2 | The author of `.vibe-suite/agents/*.md` and `.vibe-suite.md` is the operator | `advisors.load_definitions`; `config.CLOSED_MAPS["gate"]`; `store.effective_config` | False for any clone | Policy decision (H1, S2); tests: hostile definition refused; file-supplied gate ignored without store opt-in. < 1 week |
| A3 | A GitHub commenter is a collaborator | `watch_pr.py:172-174`; `operational-modes.md:239` | False on public repos | Emit `author_association`; babysit only for `OWNER/MEMBER/COLLABORATOR`. < 1 week |
| A4 | The codex `--json` event vocabulary (0.144.6) is stable | `tests/fixtures/fake-codex/*` (pinned in comments only); `events.mjs` | Unverified continuously | Opt-in `VIBE_SUITE_REAL_CODEX=1` contract probe in `self-check.yml` weekly. < 1 day |
| A5 | Both `python3` ≥ 3.11 and `node` ≥ 18 are present on every path | `config-bridge.mjs:33` (every Node dispatch), `update.py:79` (Python→Node), `stop-review-gate-hook.mjs:276` | Unchecked up front; fails mid-run as a stack trace or silent fail-open | `doctor` row + `preflight` rows for `python3`/`node`/`git`. < 1 day |
| A6 | The codex child closes its stdio pipes when it exits | `process.mjs:158` | False under `workspace-write` delegates that background processes | Resolve on `exit` + bounded drain (H6). < 1 day |
| A7 | agy will grow a tooling-level write-denial channel | `docs/agy-flip-checklist.md:16-45`; `config.py:67` | Undated, unverified | Decide: demote or re-scope the gate (M14). < 1 week |
| A8 | npm is immutable and `serverInfo` is honest | `mcp_pin.py:66-75`; `boot_probe.mjs:99-116` | Version pin only | Lockfile/tarball sha256 + `--ignore-scripts`; roll back TOML on probe failure (S13). < 1 week |
| A9 | PATH is clean for a bare `vibe-suite` command | `init_bridge.py:228-234` | No such binary ships | Remove registration until it exists; then absolute path (S4). < 1 day |
| A10 | `ubuntu-latest` + newest py/node stands in for py 3.11 / node 18 / macOS | `.github/workflows/*.yml`; README floors | Floors never exercised | 2×2 matrix + weekly macOS leg. < 1 day |
| A11 | `loop-bounds`/`coverage`/`legacy-strings` block merges | `ci.yml:136-142` says they do not | Per the file, advisory | Register as required contexts or fold (H13). < 1 day |
| A12 | Claude Code's project-MCP approval dialog (and Codex's, if any) is the last line of defence for advisor servers | `advisors.py` registration into `.mcp.json` and `.codex/config.toml` | Claude side plausible; Codex side unverified | Verify Codex prompts for project `config.toml` servers; until then treat as absent (H1). < 1 day |
| A13 | `tests/source-manifests/` reproducibility runs in CI | `tests/test_coverage_check.py:828-836` hard-codes `REPO_ROOT.parent×4/.claude/skills` | Always skips in CI (the one skip in the run) | Opt-in `VIBE_SUITE_WORKSPACE_SKILLS`; set-but-missing = fail. < 1 day |
| A14 | The claim-handshake budget (5 s) is generous | `codex-runner.mjs:416-426,460-468` | Cold Node start on a loaded box can exceed it; error names neither the budget nor the pid | Name the budget; expose as a documented env seam. < 1 day |
| A15 | The "independent implementations" rule (D7) applies within this repo | `write.mjs:3-5` vs `bridge.py`; seven copies of the Node `main()` tail | D7 is about ports from other plugins | Shared invariant matrix (M11) and `cli.mjs` (M6). < 1 week |

---

## 10. Add-on: Compact & optimize

| Target | Action | Saves |
|---|---|---|
| Eleven frontmatter/YAML parsers | One `scripts/lib/frontmatter.py` (`split`, `parse(mode)`), registry parser on the same core | ~800 lines; one edge-case suite |
| Node CLI boilerplate | `scripts/lib/cli.mjs`: `UsageError` (×4 → 1), `runMain` tail (×7 → 1), `parseLastJsonLine` (×2), `readValue` argv closure (×2); `pollGroupGone` (×3 → 1); `ARGV_PROMPT_CAP`/`DEFAULT_TIMEOUT_MS` (×2 → 1); quota classifier into `events.mjs` (×3 → 1); Stop hook calls `readEventStream` | ~150 lines; one place per rule |
| Python duplicates | Delete second `_ROOT_PIN`/`pin_root` (`bridge.py:280-283,420-435`); one `bridge.load_json(path, *, strict)` replacing five loaders; `scripts/lib/__init__.py` + one bootstrap replacing 23 `sys.path.insert` and the `importlib` double-load (`store.py:147-152`) | ~100 lines; no double module state |
| Owned-target inventories | One `OWNED_TARGETS` table in `bridge.py` from which `TARGETS`, `OWNED_BLOCKS`, and unbridge recognisers derive | Teardown cannot miss a target init learned to write |
| `SLASH_LITERAL` | Derive from `commands/*.md` at generation time | Removes a hand-list that is already wrong (`scan` present, 13 real commands absent) |
| `auditor/` | Out of tree until S8 is scheduled | ~20k lines from battery, CI, and every install |
| agy lane | Decide (demote or re-scope) | ~800 lines + five test files, or a usable lane |
| Install tree | `tests/source-manifests/`, `docs/discussion/` off the install path | ~60 % smaller installs |
| Test suite | Shard 4-way in CI (heavy anchors: `test_codex_runner` 41 s, `test_auditor_scripts` 36 s, `test_auditor_workflows` 23 s); tag contract-tier modules for an inner-loop subset; delete three meta-tests; dedupe `watch_pr` existence tests (`test_issue2pr_core.py:491-520` vs `test_issue2pr_modes.py:500-520`); freeze the parsed mode table instead of the whole `operational-modes.md`; temp-dir cleanup | 482 s → ~2-3 min critical path; −57 MB/run |
| Job store | `jobs prune`; compaction on finalise; `highestSlot` via existence probes; skip python spawn when the gate toggle is off (read the one boolean from `state.json` in Node) | O(1) reads; zero-cost disabled gate |
| Heartbeat | Document fsync cost; consider a sidecar `heartbeatAt` file instead of a full CAS slot per beat | −4 fsyncs / 30 s per background job |
| Mirror regeneration | `tools/regen.sh` in the gate battery / pre-commit | No forgotten `codex/` regeneration |

---

## 11. What is good (keep these — they are the reason the rest is fixable)

- `[GOOD]` **Event-stream verdicts, exit codes as data** — `scripts/lib/events.mjs:1-78`; `codex-runner.mjs:28-29,293-298`; `agy-runner.mjs:92-111`; `absent` vs `empty` distinguished; quota vs failure classified structured-first. `[eh K, arch]`
- `[GOOD]` **Lock-free CAS job store** — hard-link publication, roll-forward of uncommitted slots, refusal of malformed slots with repair text, terminal-is-final enforced in `transact` (`jobs.mjs:8-31,286-319`); cancel-claims-before-signal; SIGTERM→SIGKILL with *confirmed* group reap (`process.mjs:114-127,145-156`). `[eh K, arch]`
- `[GOOD]` **Audited write primitives with empty exemption lists** — `bridge.py:126-175` dir-fd `O_NOFOLLOW` walks with dev/ino pins; `write.mjs:90-141,150-192,241-260` lstat classify, literal-`..` refusal, stamp-proven ownership, TOCTOU limits disclosed; `tests/test_write_discipline.py` and `tests/node/no-raw-fs-writes.mjs` AST lints. `[sec G, arch, test §8]`
- `[GOOD]` **Injection-free process layer** — zero `shell=True`/`os.system`/`eval`/`shell: true`; one spawn primitive with argv arrays; `gh` bodies via `--body-file -`; constant jq filters with `--arg`; `set -euo pipefail` with the `set +e … status=$?` bracket in every migrate helper (`migrate/common.sh:18-31`). `[sec G, eh H]`
- `[GOOD]` **Stop-gate design** — reviews the diff not the summary, `--no-textconv --no-ext-diff` + env scrub, untracked files lstat-gated and realpath-contained, 0600 prompt in 0700 temp via the audited primitive, structural verdict parse, single absolute deadline, `stop_hook_active` recursion guard, git failure → `Indeterminate` routed to policy (tested with a fail-closed repo `stop-gate.test.mjs:282-291`). `[sec G, eh I, arch]`
- `[GOOD]` **Fail-closed config grammar, one reader** — hand-written closed YAML subset refuses what it cannot parse, typed schema, path containment, unknown keys warn; Node shells to the one reader and refuses non-zero/non-JSON (`config.py`, `config-bridge.mjs:32-53`). `[eh F]`
- `[GOOD]` **Danger gate on the effective sandbox** — `codex-runner.mjs:190-203,329,340`; explicit `read-only` in almost every command. `[sec G]`
- `[GOOD]` **Graceful degradation designed, not accidental** — per-step isolation with collected outcomes (`repair.py:60-101`, `update.py:95-160`); write-ahead journal with pre/post images and `os._exit` crash-point matrix (`advisors.py:629-724`; `test_advisors.py:735-805`); staged-then-exchanged mirror swap with rollback (`mirror-sync.py:485-514`); explicit agy fallback state machine. `[eh K, arch]`
- `[GOOD]` **No secrets, provenance on vendored JS, least-privilege `.github/` workflows** — `permissions: {}`/`contents: read`, OIDC Pages deploy, no `pull_request_target`, upstream trees pinned to full SHAs; `VENDORED.md` sha256 re-verified in tests; `bin/vibe-report` and `generate_runs_stats.py` escape and split `</` in their own HTML. `[sec G]`
- `[GOOD]` **Tests that test** — latch-synchronised lifecycle races and grandchild-reap proof (`test_codex_runner.py:744-890`); seeded-failure tests for every gate tool; hand-derived oracles predating the engine; `test_shared_partials.py` executes rule tables parsed from the partials; `test_loop_bounds.py` drives the real runner from `## Round bounds` blocks; issue2pr driver reads marker-tagged declaration blocks at runtime and refuses on a gap (exit 4); `auditor/` helpers each carry a behavioural oracle plus a no-op and a wrong-behaviour mutant. `[test §1/§7/§8, arch §2]`
- `[GOOD]` **Pin discipline and minimal agent grants** — `mcp_pin.py:26` rejects non-exact versions; `boot_probe.mjs:45-47,76` sanitises third-party output; 10 of 14 agents are Read/Glob/Grep only; the vibe-core untrusted-input rule is inlined into 13 commands. `[sec G]`
- `[GOOD]` **Honest pre-release gate** — `release-score.py --threshold 80`, spec-corpus contract, `--mirrors`, anti-vacuous discovery; the judgment lane is disclosed as operator-run, not claimed; `tests/loop-bounds/README.md` documents what it cannot establish. `[test §6/§8]`

---

## 12. Executive summary

**Verdict.** Health is high in the engine core and uneven at its edges. The single biggest risk is that repository-controlled content is treated as operator intent: a hostile clone can register a `bypassPermissions` + Bash MCP advisor on `/vibe-suite:init` (H1), flip on a 900 s egress hook and make it fail closed (S2), and — in issue2pr with `--auto-merge` — let any GitHub commenter steer autonomous edits to a squash-merge (H2). Behind that sit five one-day robustness fixes in the dispatch/gate/write path (H5–H7, H9, M7) that each turn a silent failure into a diagnosable one, a job store that grows without bound (H8), and a doctrinal debt (eleven parsers, two kernels, an inert 20k-line stage) that is expensive but not dangerous.

**Top 3 actions.**
1. **Close the trust boundary** (Track 1, < 1 week): advisor gate + no auto-reconcile; `gate.*` store-only; issue2pr untrusted-input rule + `author_association` filter + no auto-merge re-arm; confirm before running repo scripts in `delegate`. This is the only work that changes the threat model.
2. **Ship the five engine-seam fixes together** (Track 2, ~4 days): random scratch in `write_atomic`; deadline on `exit` + drain; `stderrTail`/worker log; stored `fail_policy: closed` honoured on unreadable config with `systemMessage`; result line guaranteed from `prepareRecord`. Each is < 1 day, all are correctness, none needs a design debate.
3. **Make CI gate and shrink the loop** (Track 6, ~2 days): required contexts + `timeout-minutes`; shard the suite; floor matrix; stop the temp leak; add `node --test` to the documented battery. Everything else in this report depends on a gate battery people actually run.

**Confidence.**
- H1/H2/S2/S3 (trust boundary): **High** — code paths read end-to-end, exploit chains traced to specific lines. Would rise to certainty with one reproduction in a scratch clone and verification of whether Codex prompts for project `config.toml` servers (A12).
- H5/H6/H7/H9 (engine seams): **High** — each is a specific line with a specific failing input; H6 and H9 would benefit from a fixture that leaks a pipe / SIGKILLs between open and replace to make the test permanent.
- H8 (job store growth → `ENOBUFS` fail-open): **Medium-High** — growth is certain from the code; the `ENOBUFS` endpoint was reasoned, not reproduced.
- H10/H11/H12 (structural debt): **High** on the facts (file counts, line refs), **Medium** on the proposed shapes (`frontmatter.py` modes, staging branch vs env-gated tests) — those are product calls.
- H13 (advisory CI gates): **Medium** — rests on `ci.yml`'s own comment; branch protection was not readable. One look at repository settings resolves it.
- H3/H4 (XSS, `source`d artifact): **High** — verified against source by a sub-audit and re-verified by the security agent.

---

## Fixing Plan

Every item traces to a finding above. Efforts are engineer-days; many items are independent and parallelisable.

### Phase 1: Critical fixes (do immediately)
No finding was rated `[CRITICAL]`. Treat H1, H2, H5, H9 as the de-facto Phase 1 — see Phase 2, items 1–4.

### Phase 2: High-priority fixes (this sprint)

| # | Finding | Fix | Effort | Files to modify |
|---|---|---|---|---|
| 1 | **H1** advisor defs → `bypassPermissions`+Bash auto-registered | Refuse `bypassPermissions`/`dontAsk`/`auto` and out-of-workspace `cwd`/`additional_dirs` unless `--confirm-danger`; drop `advisors.reconcile(ws)` from `install`; list and require `advisor add` per entry; hash-stamp definitions and re-confirm on change | 4 d | `scripts/lib/advisors.py`, `scripts/lib/init_bridge.py`, `scripts/advisor_cli.py`, `commands/advisor.md`, `commands/init.md`, `tests/test_advisors.py`, `tests/test_init.py` |
| 2 | **H2** issue2pr: any commenter → edits/auto-merge; no untrusted rule | Inline vibe-core untrusted-input rule in `skills/issue2pr/SKILL.md`, `refine-proposal`, `continue`, `advisor`; `watch_pr.py` emits `author_association`; chain babysits only for `OWNER/MEMBER/COLLABORATOR`, notifies otherwise; never re-arm `--auto-merge` after a non-collaborator round; `{slug}` rule `[a-z0-9-]{1,40}` | 4 d | `skills/issue2pr/SKILL.md`, `skills/issue2pr/references/operational-modes.md`, `skills/issue2pr/references/profile-contract.md`, `scripts/watch_pr.py`, `scripts/issue2pr_mode_driver.py`, `commands/issue2pr.md`, `commands/refine-proposal.md`, `commands/continue.md`, `commands/advisor.md`, `tests/test_issue2pr_modes.py`, goldens |
| 3 | **H9** fixed scratch name in `write_atomic` | Use `_scratch(dir_fd, dest.name, mode)`; keep `O_NOFOLLOW`; name the remedy in the residual refusal; optional age-gated reap of stamped `.vibe-tmp` in the state dir | 0.5 d | `scripts/lib/bridge.py:477-487`, `tests/test_bridge_cli.py`, `tests/test_init.py:361-373` |
| 4 | **H5** stored `fail_policy: closed` defeated by unreadable config | `store.effective_config` loads store first and degrades (`{gate: store+FRESH, config_error}` exit 0 + stderr); hook blocks when stored policy is closed and config unreadable; include `result.stderr` in `why`; emit `{"systemMessage": …}` on fail-open; test broken `.vibe-suite.md` + stored closed → BLOCK | 1 d | `scripts/lib/store.py:141-180`, `scripts/stop-review-gate-hook.mjs:219-238`, `tests/node/stop-gate.test.mjs`, `tests/test_store.py` |
| 5 | **H6** deadline defeated by leaked pipe; heartbeat forever | Resolve on `exit` + bounded `graceMs` drain for `close`; `pipesLeaked: true` in record; stop heartbeat after SIGKILL | 1 d | `scripts/lib/process.mjs:92-173`, `scripts/codex-runner.mjs:273-291`, `scripts/lib/jobs.mjs` (RECORD_SHAPE), `tests/node/process-detached.test.mjs`, `tests/node/heartbeat.test.mjs` |
| 6 | **H7** stderr/signal/malformedLines discarded; worker stdio ignored | Add `stderrTail` (4–8 KB, control-stripped), `signal`, `malformedLines` to `newRecord`/`RECORD_SHAPE`; `error` names exit+signal+first stderr line when no terminal event; worker `stdio: ["ignore","ignore",fd]` → `.vibe-suite-state/jobs/<id>.log` 0600 via `write.mjs`; render fenced in `jobs status` | 1 d | `scripts/codex-runner.mjs:293-318,384-388`, `scripts/agy-runner.mjs:161-183`, `scripts/lib/jobs.mjs:114-145,493-521`, `scripts/lib/render.mjs`, `scripts/jobs-cli.mjs`, `commands/jobs.md`, node tests |
| 7 | **H3** XSS in report template | `createElement`/`textContent` rows; HTML-escape `args.repo`; CSP meta `default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'` | 0.5 d | `templates/report/assets/vibe-report.js:27-34`, `templates/report/repo-audit.html`, `auditor/scripts/render-repo-report.py:178-183`, `tests/test_report.py` |
| 8 | **H4** auditor publish job `source`s model-writable file | Parse `KEY=VALUE` with a strict regex into validated vars, or pass as job `outputs`; never `source` | 0.5 d | `auditor/workflows/auditor-exemplar.yml:103-120,169-170`, `tests/test_auditor_workflows.py` |
| 9 | **H8** job store unbounded; gate `ENOBUFS` | `jobs prune [--older-than 7d]` (terminal jobs, canonical + slots); compaction on finalise; `rawOutput` cap 16 MB with disclosed marker; `highestSlot` via `v(canonical+1..)` probes; document heartbeat cost; rewrite "never delete a slot" prose to "of a non-terminal job" | 3 d | `scripts/lib/jobs.mjs`, `scripts/jobs-cli.mjs`, `scripts/lib/process.mjs:100-107`, `scripts/codex-runner.mjs`, `commands/jobs.md`, `tests/node/jobs-*.test.mjs` |
| 10 | **H13** advisory CI gates; no timeouts | Register `loop-bounds`/`coverage`/`legacy-strings` as required contexts (or fold into `test`/`lint`) and say so in the comment; `timeout-minutes: 25` on `test`, `10` elsewhere | 0.5 d | `.github/workflows/ci.yml`, repository branch-protection settings |
| 11 | **H12** `generate_runs_stats.py` god file, unaudited writes, untested parsers | Move to `scripts/runs_stats/{discover,aggregate,render,main}.py`; HTML shells → `templates/runs-stats/*.html`; writes via `bridge.write_atomic`/`publish_new`; `importlib` unit tests for `parse_iso`, `union_seconds`, `normalize_token_block`, `tokens_from_log`, `usage_from_event_stream`, `compute_timing`, `normalize_status`, `extract_tests`, `bucket_signature`; corrupt-`state.json` fixture asserting warnings and no crash; `load_history` refuses to overwrite an unreadable existing file | 4 d | `skills/runs-stats/scripts/generate_runs_stats.py` → `scripts/runs_stats/`, `skills/runs-stats/SKILL.md`, `templates/runs-stats/`, `tests/test_runs_stats.py`, `tests/test_write_discipline.py` |
| 12 | **H11** inert `auditor/` in-tree; README misstates | Move `auditor/` (with items 8 and Phase-3 S17 applied) + `tests/test_auditor_*.py`, `tests/auditor_helpers_support.py`, `tests/test_migrate_auditor_data.py` to a staging branch/sibling repo, keep `auditor/README.md`; or gate its tests behind `VIBE_TEST_AUDITOR=1`; fix `README.md:9-11` | 3 d | `auditor/`, `tests/test_auditor_*`, `README.md`, `tools/migrate-auditor-data.sh`, `.github/workflows/ci.yml` |
| 13 | **H10** eleven frontmatter/YAML parsers | `scripts/lib/frontmatter.py` (`split`, `parse(mode="strict"|"artifact")`); route 8 small helpers through `split`; `check_engine` registry parser on the same block-mapping core + schema validator; `config.py` stays schema owner calling `parse(mode="strict")`; re-baseline goldens with per-diff review. Precede with `scripts/lib/__init__.py` bootstrap (Phase 4) | 15 d | `scripts/lib/config.py`, `scripts/score_engine.py`, `scripts/check_engine.py`, `scripts/lib/advisors.py`, `scripts/mirror-sync.py`, `scripts/mechanical_fix.py`, `scripts/profile_lint.py`, `scripts/write_profile.py`, `scripts/lib/init_bridge.py`, `bin/vibe-check`, `generate_runs_stats.py`, golden fixtures, `tests/test_config.py`, `tests/test_score*.py`, `tests/test_check*.py` |

**Phase 2 subtotal: ~38 days.**

### Phase 3: Medium-priority improvements (next sprint)

| # | Finding | Fix | Effort | Files |
|---|---|---|---|---|
| 1 | S2 repo file flips gate/sandbox | Drop `gate.*` from `CLOSED_MAPS` or require stored `stop_review_gate: true`; notice when file raises `sandbox` | 0.5 d | `scripts/lib/config.py:96-98`, `scripts/lib/store.py:155-157`, `tests/test_store.py:184-189`, `tests/test_config.py` |
| 2 | S3 delegate verify runs repo scripts unsandboxed | Show diff + confirm; or run verify under `codex -s workspace-write`; refuse if `run-tests.sh`/`package.json` dirty | 0.5 d | `commands/delegate.md:63,81-90`, `tests/node/delegate-dispatch.test.mjs`, `tests/test_commands.py` |
| 3 | S4 bare `vibe-suite` registrations | Remove until binary ships; then absolute `${CLAUDE_PLUGIN_ROOT}` path | 0.5 d | `scripts/lib/init_bridge.py:228-234,298-305`, `tests/test_init.py` |
| 4 | S5 env var names unescaped into TOML | Validate `[A-Za-z0-9_]` | 0.25 d | `scripts/bridge_cli.py:124-127`, `tests/test_bridge_cli.py` |
| 5 | S7 prompt/token on worker argv | Pass prompt-file path + token via 0600 file/fd; `--` before prompt; allow-list `--effort` | 0.5 d | `scripts/codex-runner.mjs:163-170,206-220,384-387`, `scripts/agy-audit-cli.mjs:45,56-62`, `tests/test_codex_runner.py` |
| 6 | S11 site builders raw-interpolate corpus | One `md_escape()`; `markdown: { html: false }`; `<div v-pre>` for untrusted blocks | 0.5 d | `bin/vibe-build-site-report-pages`, `bin/vibe-build-case-studies-index`, `bin/vibe-build-reference-md`, `bin/vibe-build-docs`, `bin/vibe-build-vocab-data`, `site/.vitepress/config.ts`, `tests/test_site_*` |
| 7 | S13 claude-octopus version-not-integrity pin; TOML before probe | Lockfile-backed local install with recorded `integrity` (or `npx --ignore-scripts` + tarball sha256); roll back TOML on probe failure | 3 d | `scripts/lib/mcp_pin.py`, `scripts/lib/boot_probe.mjs`, `scripts/update.py:148-159`, `scripts/lib/advisors.py:305-330`, `tests/test_update.py`, `tests/test_mcp_pin.py` |
| 8 | S17 auditor workflow hygiene | `env:` indirection for `${{ inputs.* }}`; `--allowedTools "Read,Grep,Glob,Write,Edit"`; `git diff -- skills/rules/SKILL.md` | 1 d | `auditor/workflows/auditor-audit.yml:61-62`, `auditor-case-study.yml:73-74`, `auditor-exemplar.yml:9,120`, `auditor-refine-rules.yml:34,118,128`, `auditor-classify.yml:89`, `auditor-contribute.yml:468-471`, `tests/test_auditor_workflows.py` |
| 9 | M7 result-line hole when `prepareRecord` throws | Wrap in the same guard; emit `{jobId:null,status:"failed",errorClass:"failure"}`; treat `ConfigBridgeError` as contract failure | 0.5 d | `scripts/codex-runner.mjs:350-370,512-526`, `scripts/lib/config-bridge.mjs:35-40`, `tests/test_codex_runner.py` |
| 10 | M10 `_open_dir_chain` creates on read/delete | `create=False` default; `create=True` from `ensure_dir_at`/`write_atomic`/`publish_new`/`symlink_at` | 0.5 d | `scripts/lib/bridge.py:157-168`, `scripts/lib/advisors.py:358-365,453-457`, `scripts/lib/unbridge.py:147,239`, `tests/test_unbridge.py` |
| 11 | M1 hook observability visibility assumed | Harness-contract test; SessionStart report → stdout; Stop fail-open → `systemMessage`; PostToolUse advisory → `systemMessage` or non-2 exit | 0.5 d | `scripts/session-lifecycle-hook.mjs:32-49`, `scripts/check-artifact.sh:46`, `scripts/stop-review-gate-hook.mjs:236,325`, `hooks/README.md`, `tests/test_check_artifact_hook.py`, `tests/node/session-lifecycle.test.mjs` |
| 12 | M2 `gh` calls untimed; degraded probes silent | `timeout=60` → `GhError`; counter + stderr line per 10 consecutive degradations | 0.5 d | `scripts/watch_pr.py:77-81,122-140,177-197`, `tests/test_issue2pr_modes.py` |
| 13 | M3 agy `resolveModel` swallows config errors | Propagate `ConfigBridgeError` as exit 2 | 0.25 d | `scripts/agy-runner.mjs:69-81`, `tests/node/agy-*.test.mjs` |
| 14 | M4 issue2pr reviewer dispatch bypasses runner | Route through `codex-runner.mjs --kind review --prompt-file … --wait`; branch on five-key `status` | 3 d | `skills/issue2pr/SKILL.md`, `skills/vibe-core/references/reviewer-contract.md:32-40`, goldens, `tests/test_issue2pr_*.py` |
| 15 | M5 no durable log | Append-only NDJSON `.vibe-suite-state/events.log` (0600, `O_APPEND`) for dispatch/gate/hook/prune events; `jobs log [--tail N]`; size-cap + rename | 3 d | `scripts/lib/` (new `eventlog.mjs`), `scripts/codex-runner.mjs`, `scripts/stop-review-gate-hook.mjs`, `scripts/session-lifecycle-hook.mjs`, `scripts/jobs-cli.mjs`, `commands/jobs.md`, tests |
| 16 | M6 duplicated Node/Python helpers | `scripts/lib/cli.mjs` (`UsageError`, `runMain`, `parseLastJsonLine`, `readValue`); `pollGroupGone`, `ARGV_PROMPT_CAP` exported from `process.mjs`; quota table + `classifyFailure` in `events.mjs`; Stop hook uses `readEventStream`; `bridge.load_json(strict)` as the one Python loader; delete duplicate `pin_root` | 2 d | `scripts/codex-runner.mjs`, `scripts/agy-runner.mjs`, `scripts/jobs-cli.mjs`, `scripts/preflight-cli.mjs`, `scripts/agy-audit-cli.mjs`, `scripts/stop-review-gate-hook.mjs:197-217,304-310`, `scripts/lib/agy-fallback.mjs:60-65`, `scripts/lib/process.mjs`, `scripts/lib/events.mjs`, `scripts/lib/bridge.py`, `scripts/lib/store.py`, `scripts/issue2pr_mode_driver.py`, `scripts/doctor.py`, node/py tests |
| 17 | M8 partials include-by-link; ladder in prose + code | `config_cli.py resolve-engine` printing `{engine, cross_model_audit_engine, model}`; shrink `model-selection.md`; commands call the seam | 2 d | `scripts/config_cli.py`, `commands/shared/model-selection.md`, ten commands referencing it, `tests/test_shared_partials.py`, `tests/test_commands.py` |
| 18 | M9 `bridge.py` is the unnamed fs kernel | Split `scripts/lib/fsafe.py` (descent, write_atomic, publish_new, unlink/rename/symlink/lstat/remove_tree, classify, pin_root) from `bridge.py` (codecs, sentinels, provenance, CLI) | 3 d | `scripts/lib/bridge.py`, 18 importers, `tests/test_write_discipline.py:28` |
| 19 | M11 two safety kernels, drifting invariants | Shared `tests/fixtures/write-invariants/*.json` matrix run against both kernels | 2 d | `tests/test_bridge_cli.py`, `tests/node/write-primitive.test.mjs`, new fixtures |
| 20 | M12 cross-pinned pairs; `SLASH_LITERAL` drift | Test `hooks.json` Stop timeout ↔ `HOOK_BUDGET_MS`; derive `SLASH_LITERAL` from `commands/*.md`; derive `TARGETS` from one `OWNED_TARGETS` table; `scripts/lib/mirror_tables.py` shared by generator and checker | 2 d | `scripts/mirror-sync.py:31-67`, `bin/vibe-check:482-507`, `scripts/lib/init_bridge.py:33-37`, `scripts/lib/bridge.py:44-47`, `scripts/lib/unbridge.py:267-330`, `tests/test_mirror_sync.py`, `tests/node/stop-gate.test.mjs` |
| 21 | M13 `_roast_variant` embedded in generator | Move to `codex-src/vibe-roast/SKILL.md.tmpl`, hashed; test scope-grammar sentences equal `scope-parse.md` | 0.5 d | `scripts/mirror-sync.py:239-330`, `codex-src/`, `codex/MIRROR-MANIFEST.json`, `tests/test_mirror_sync.py` |
| 22 | M14 agy lane behind un-passable gate | Decide: (a) `engine: agy` → `ConfigValueError("not available")` + move lane to a branch; or (b) re-scope gate to verifiable checks, keep non-default | 3 d | `scripts/agy-*.mjs`, `scripts/lib/agy-gate.mjs`, `scripts/lib/agy-fallback.mjs`, `scripts/lib/config.py:67`, `docs/agy-flip-checklist.md`, `tests/agy-contract/`, `tests/node/agy-*.test.mjs` |
| 23 | M15 install weight | `tests/source-manifests/`, `docs/discussion/` off the install path (CI fetches manifests) | 1 d | `tests/source-manifests/`, `docs/discussion/`, `.github/workflows/ci.yml:182-204`, `tools/coverage-check.py` |
| 24 | M16 `score_engine`/`check_engine` god files (after H10) | `score/{classify,rules,history,cli}.py`; `check/{graph,directions,r51,cli}.py`; keep entry filenames | 3 d each | `scripts/score_engine.py`, `scripts/check_engine.py`, tests |
| 25 | M17 write-discipline scope excludes `bin/`, skill scripts | Extend AST lint source set; route `bin/vibe-report` through `bridge.write_atomic`/`publish_new` (after H12) | 2 d | `tests/test_write_discipline.py:14-16,74-77`, `bin/vibe-report:400-433`, five `bin/vibe-build-*` |
| 26 | M26 job-store races hand-staged | 32-way `Promise.all(transact…)` + 4-process CAS test; `VIBE_TEST_FAIL_AFTER=link` seam in `write.mjs` publish path | 1 d | `tests/node/jobs-store.test.mjs`, `scripts/lib/write.mjs` |
| 27 | M27 `events.mjs` unit gaps; wrong fixture shape | Four unit tests (agent_message last-wins, empty-vs-absent, `errorCode`, `turn.usage` fallback); fix `emitter.mjs:22` | 0.5 d | `tests/node/events.test.mjs`, `tests/fixtures/fake-codex/emitter.mjs` |
| 28 | M28 `bridge.py` 18/41 public fns untested; no crash-between-tmp-and-replace | `TestBridgePrimitives` (+/- per function); fail-after-tmp-write injection | 2 d | `tests/test_bridge_primitives.py` (new), `scripts/lib/bridge.py` (seam) |
| 29 | M29 hook test gaps | Garbage stdin → allow + stderr; `sleeper.mjs` within `VIBE_TEST_GATE_BUDGET_MS`; `--event bogus` → exit 2 (fix the silent map to `start`) | 0.5 d | `tests/node/stop-gate.test.mjs`, `tests/node/session-lifecycle.test.mjs`, `scripts/session-lifecycle-hook.mjs:22-24` |
| 30 | M30 prose-pin tests; meta-tests | Tag contract-tier modules (`tests/contract/` or header) for an inner-loop subset; convert highest-churn prose pins to parsed declaration blocks; delete the three meta-tests; dedupe `watch_pr` existence tests; freeze parsed mode table not whole `operational-modes.md` | 2 d | `tests/test_roast.py`, `tests/test_reviewer_contract.py`, `tests/test_spec_sync.py`, `tests/test_commands.py`, `tests/test_issue2pr_modes.py:107-114,489-497`, `tests/test_migration_fixtures.py:214-218`, `tests/test_mode_driver.py:830`, `tests/test_issue2pr_core.py:491-520` |
| 31 | M31 no real-codex contract probe | Opt-in `VIBE_SUITE_REAL_CODEX=1` probe asserting event vocabulary, skipped without binary, weekly in `self-check.yml` | 0.5 d | `tests/test_codex_contract.py` (new), `.github/workflows/self-check.yml` |
| 32 | M32 temp-dir leak (~600 dirs/run) | `self.addCleanup(shutil.rmtree…)` in five auditor modules + `test_mode_driver`, `test_loop_bounds`; shared `tests/node/_tmp.mjs` `workspace()` with exit-time removal | 0.5 d | `tests/test_auditor_findings_helpers.py`, `test_auditor_scripts.py`, `test_auditor_reporting_helpers.py`, `test_auditor_rulebook_helpers.py`, `test_auditor_batch_helpers.py`, `test_mode_driver.py`, `test_loop_bounds.py`, all `tests/node/*.test.mjs` |
| 33 | M33 coverage-check reads sibling checkouts; reproducibility test always skips in CI | `VIBE_SUITE_WORKSPACE_SKILLS` opt-in (set-but-missing = fail); drop `repo_root.parent` default | 0.5 d | `tests/test_coverage_check.py:50-58,828-836`, `tools/coverage-check.py` |
| 34 | M34 CI: no floors/macOS, no coverage measurement, serial suite, battery omits node | 2×2 matrix (py 3.11/3.x × node 18/lts) + weekly macOS leg; `coverage.py` dev-only + `node --test --experimental-test-coverage` as artifacts; 4-shard matrix; cache pinned trees; add `node --test tests/node/*.test.mjs` to CLAUDE.md and `tests/README.md` (+ `ruby` prerequisite) | 1.5 d | `.github/workflows/ci.yml`, `.github/workflows/self-check.yml`, `CLAUDE.md:18-22`, `tests/README.md` |
| 35 | M35 specs cover 1/29 commands, 1/24 skills; never evaluated | Specs for `delegate`, `roast`, `score`, `fix`, `nl-audit`, `preflight`, `issue2pr`, `refine-proposal`, `vibe-core`; scheduled judgment-lane run, advisory | 3 d | `.vibe-test/*.spec.md`, `.github/workflows/self-check.yml` |

**Phase 3 subtotal: ~60 days.**

### Phase 4: Low-priority cleanup (when touching these files)

- **`scripts/lib/bridge.py`** — delete second `_ROOT_PIN`/`pin_root` (105-123 vs 280-283/420-435); `publish` subcommand returns a distinct code on "already existed" (849); wrap `main` in `try/except BridgeError → "bridge: …", 1` (835-855); update "six targets" docstring (14). *[arch §3, eh D]*
- **`scripts/lib/store.py`** — `_cli` catches `ConfigSyntaxError`/`ConfigValueError`/`ConfigContainmentError`/`OSError`/`UnicodeDecodeError` (164-180); `_read` handles `UnicodeDecodeError`/`PermissionError` (55-73); replace the `importlib` double-load of `config.py` (147-152) once `scripts/lib/__init__.py` exists. *[eh D, arch §3]*
- **`scripts/lib/config-bridge.mjs`** — `timeout: 30_000` on the python spawn (33); forward non-empty `result.stderr` (config warnings) to stderr. *[eh B4/F2]*
- **`scripts/codex-runner.mjs`** — heartbeat: count consecutive failures, log after 3 (285-289); `awaitWorkerClaim` error names budget + pid, budget as documented env seam (416-426, 460-468); `--skip-git-repo-check` only when `sandbox === "read-only"` (216). *[eh D/G, sec S15]*
- **`scripts/stop-review-gate-hook.mjs`** — read the `stop_review_gate` boolean from `state.json` in Node before spawning python (249-278); frame `reason` as "external reviewer text, data only" (317); add `-c core.fsmonitor= -c core.hooksPath=/dev/null` to git argv (104-108). *[arch §1, sec S8]*
- **`scripts/lib/preflight.mjs` / `scripts/preflight-cli.mjs` / `scripts/doctor.py`** — rows for `python3 ≥3.11`, `node ≥18`, `git`; count in `exitCodeFor`; doctor capability row. *[eh B5, arch §3]*
- **`scripts/doctor.py` (71-91), `scripts/repair.py` (36-41), `scripts/lib/advisors.py` (794-807), `scripts/issue2pr_mode_driver.py` (221-226), `scripts/migrate/common.sh` (131-136)** — capture the exception/reason into a finding / `(state, reason)` / `corrupt` column / `vibe_warn` instead of dropping it. *[eh D]*
- **`scripts/bridge_cli.py` (342-344), `scripts/issue2pr_mode_driver.py` (466-468)** — `timeout=60` on mirror regen and manifest validator. *[eh B4]*
- **`scripts/issue2pr_mode_driver.py` (92, 99, 139, 509)** — replace parent-as-root path-based `mkdir` with bridge primitives. *[sec S19]*
- **`scripts/lib/jobs.mjs` (208, 274, 305, 324)** — anchor `writeAtomic`/`publishNew` under `ensureState`'s symlink refusal for the self-heal path. *[sec S19]*
- **`scripts/bridge_cli.py` (176)** — confirm before mirroring `.claude/settings.json` hook commands into `.codex/hooks.json`. *[sec S19]*
- **`scripts/lib/agy-gate.mjs` (54-64) and all `VIBE_SUITE_*_BIN` readers** — one stderr notice when an override is active; require absolute path. *[sec S14]*
- **`commands/refresh-knowledge.md` (82-96)** — add the untrusted-input rule; write a review diff first; never modify the plugin checkout in place. *[sec S9]*
- **Stale self-docs** — `hooks/README.md:24`, `scripts/lib/write.mjs:35-36`, `commands/check.md:10-11`, `scripts/lib/init_bridge.py:10-12`, `README.md:10-11`; optional `tools/doc-claims-lint.py` for "not yet built|when it lands|remains open". *[arch §10, eh K]*
- **`docs/exit-codes.md`** (new) — one table per CLI + a test diffing each CLI's header comment against it. *[eh E]*
- **`skills/runs-stats/scripts/generate_runs_stats.py` (86-92, 1347-1353)** — warn on `read_text`/`load_history` failures (folds into Phase 2 #11). *[eh D]*
- **`templates/pre-commit` / `tools/regen.sh`** — run `mirror-sync.py generate` so `codex/` regeneration is mechanical. *[arch §6]*
- **`scripts/lib/advisors.py`** — split `advisors/{definitions,records,reconcile}.py` when next touched; **`bin/vibe-check`** — move `check_mirrors` to `scripts/lib/mirror_check.py`. *[arch §8]*
- **`.github/workflows/*.yml`, `auditor/workflows/*.yml`, `templates/ci-vibe-check.yml`** — pin actions to SHAs; add `permissions:` to the template; `auditor/scripts/guard-protected-paths.sh` inspect the code checkout not `$DATA_DIR`. *[sec S17]*
- **`tests/test_update.py` (264-266)** — tag the hanger with a per-test nonce instead of counting system-wide `ps`. *[test §5]*
- **`tests/test_doc_accuracy.py` (45, 126, 158)** — counts sentence behind a stable marker comment; drop fragment pins on PRIVACY/source strings. *[test §2]*
- **`scripts/lib/__init__.py` + `scripts/_bootstrap.py`** — replace 23 `sys.path.insert` sites (do before the Phase 3 package splits). *[arch §3]*

**Phase 4 subtotal: ~12 days (opportunistic).**

### Dependency graph
- Phase 2 #13 (`frontmatter.py`) **depends on** Phase 4 `scripts/lib/__init__.py` bootstrap; Phase 3 #24 (`score`/`check` splits) **depends on** Phase 2 #13.
- Phase 3 #25 (extend AST lint to `bin/`, skill scripts) **depends on** Phase 2 #11 (runs-stats writes routed) and the `bin/vibe-report` routing in the same item — otherwise the lint fails on day one.
- Phase 2 #4 (stored closed policy + `systemMessage`) **depends on** Phase 3 #11's harness-visibility check for the `systemMessage` half; the store-degrade half is independent.
- Phase 4 heartbeat-failure logging **depends on** Phase 2 #6 (worker log sink).
- Phase 2 #12 (`auditor/` out of tree) **should carry** Phase 2 #8 and Phase 3 #8 (S16/S17) — fix before moving so the staging copy is clean.
- Phase 3 #14 (route issue2pr reviewer through runner) **should follow** Phase 2 #2 — both touch the golden-pinned issue2pr skill; sequence to avoid double re-baselining.
- Phase 3 #16 (quota-table consolidation) **should follow** Phase 3 #22 (agy decision) — less to consolidate if the lane is demoted.
- Phase 3 #34 sharding **should precede** the floor matrix in the same item (3–4× CI minutes otherwise).
- Phase 3 #18 (`fsafe.py` split) **should follow** Phase 2 #3 and Phase 3 #10 (scratch name, `create=False`) so the kernel moves in its fixed form.
- Phase 3 #20 (`OWNED_TARGETS` table) **enables** Phase 4 unbridge recogniser cleanup.

### Estimated total effort
- Phase 1: 0 days (no `[CRITICAL]`; H1/H2/H5/H9 are the de-facto immediate set — ~10 days of Phase 2)
- Phase 2: ~38 days
- Phase 3: ~60 days
- Phase 4: ~12 days (opportunistic)
- **Total: ~110 engineer-days** (sequential estimate; Tracks 1, 2, 6, 7 of the 80/20 plan — ~12 days — retire the large majority of the risk and are parallelisable across two people)
