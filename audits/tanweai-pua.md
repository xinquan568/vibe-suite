# Audit: tanweai/pua

**Repo**: https://github.com/tanweai/pua  
**Plugin**: pua v3.2.3 by 探微安全实验室  
**Audited**: 2026-04-25  
**NL Score**: 90/100  
**Security**: CLEAR  
**Artifacts scored**: 45  
**Findings**: 3 Medium security, 5 Low security, 9 quality issues

---

## NL Score Breakdown

Weighted average across all 45 NL artifacts (agents, commands, skills, hooks config, plugin manifest).

| Score | File | Type | Key Penalties |
|-------|------|------|--------------|
| 70 | agents/tech-lead-p9.md | agent | R09 no examples −15, R10 no model −5, R12 no output format −10 |
| 75 | agents/cto-p10.md | agent | R09 no examples −15, R12 no output format −10 |
| 75 | commands/survey.md | command | R14 no numbered steps −10, R16 no output format −10, R17 no error paths −5 |
| 80 | agents/senior-engineer-p7.md | agent | R09 no examples −15, R10 no model −5 |
| 80 | skills/p7/SKILL.md | skill | R06 no code examples −10, R12 no output format −10 |
| 80 | skills/p9/SKILL.md | skill | R06 no code examples −10, R12 no output format −10 |
| 80 | skills/p10/SKILL.md | skill | R06 no code examples −10, R12 no output format −10 |
| 85 | commands/flavor.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/kpi.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/mama.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/p10.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/p7.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/p9.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/pro.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/pua-loop.md | command | R16 no output format −10, R17 no error paths −5 |
| 85 | commands/yes.md | command | R16 no output format −10, R17 no error paths −5 |
| 88 | skills/shot/SKILL.md | skill | R05 449 lines (400–500 range) −5, R07 no scope note −3, vague ×2 −4 |
| 90 | commands/pua.md | command | R16 output format delegated to skill −10 |
| 90 | skills/pua-loop/SKILL.md | skill | R07 no scope note −3, vague ×2 −4, minor structural issues −3 |
| 91 | codex/pua-en/SKILL.md | skill | R07 no scope note −3, vague ×3 −6 |
| 91 | codebuddy/pua-en/SKILL.md | skill | R07 no scope note −3, vague ×3 −6 |
| 91 | hermes/pua-en/SKILL.md | skill | R07 no scope note −3, vague ×3 −6 |
| 91 | kimi/pua-en/SKILL.md | skill | R07 no scope note −3, vague ×3 −6 |
| 91 | skills/pua-en/SKILL.md | skill | R07 no scope note −3, vague ×3 −6 |
| 93 | codex/pua/SKILL.md | skill | R07 no scope note −3, vague ×2 −4 |
| 93 | codebuddy/pua/SKILL.md | skill | R07 no scope note −3, vague ×2 −4 |
| 93 | hermes/pua/SKILL.md | skill | R07 no scope note −3, vague ×2 −4 |
| 93 | kimi/pua/SKILL.md | skill | R07 no scope note −3, vague ×2 −4 |
| 93 | skills/mama/SKILL.md | skill | R06 shell snippets not runnable −5, vague ×1 −2 |
| 93 | skills/pua/SKILL.md | skill | R07 no scope note −3, vague ×2 −4 |
| 95 | codex/pua-ja/SKILL.md | skill | R07 no scope note −3, vague ×1 −2 |
| 95 | codebuddy/pua-ja/SKILL.md | skill | R07 no scope note −3, vague ×1 −2 |
| 95 | hermes/pua-ja/SKILL.md | skill | R07 no scope note −3, vague ×1 −2 |
| 95 | kimi/pua-ja/SKILL.md | skill | R07 no scope note −3, vague ×1 −2 |
| 95 | skills/pua-ja/SKILL.md | skill | R07 no scope note −3, vague ×1 −2 |
| 95 | skills/yes/SKILL.md | skill | R07 no formal scope note −3, vague ×1 −2 |
| 95 | commands/off.md | command | R17 no error paths for failed config write −5 |
| 95 | commands/on.md | command | R17 no error paths for failed config write −5 |
| 100 | commands/cancel-pua-loop.md | command | — |
| 100 | commands/reap-orphans.md | command | — |
| 100 | commands/team-status.md | command | — |
| 100 | commands/teardown-all.md | command | — |
| 100 | hooks/hooks.json | hooks config | — |
| 100 | plugin.json | plugin manifest | — |
| 100 | skills/pro/SKILL.md | skill | — |

**Weighted Average: 90/100** (Excellent)

---

## Security Scan

Scanned: `hooks/*.sh` (8 files), `scripts/setup-pua-loop.sh`, `hooks/hooks.json`.

### Findings

| Severity | File | Line | Pattern | Notes |
|----------|------|------|---------|-------|
| MEDIUM | hooks/stop-feedback.sh | 105 | `bash "$(cat /tmp/pua-plugin-root)/hooks/sanitize-session.sh"` | `/tmp/pua-plugin-root` is attacker-controlled: if a local user controls `/tmp/`, they can redirect to an arbitrary script. Race condition between file write and exec. |
| MEDIUM | hooks/stop-feedback.sh | 87–112 | `curl -s -X POST https://pua-skill.pages.dev/api/feedback` + session upload | Sanitized session JSONL uploaded to third-party domain. Consent gate present but: (1) upload domain is not user-controlled, (2) sanitization happens client-side before sending. Medium risk given explicit opt-in UX. |
| MEDIUM | skills/pro/SKILL.md | 102–104 | `curl … -d '{"action":"register","email":"USER_EMAIL","phone":"USER_PHONE"}'` | Email and phone sent to `pua-skill.pages.dev` during leaderboard registration. PII leaves the machine to a third-party endpoint. No on-machine retention verification. |
| LOW | hooks/failure-detector.sh | 10 | `python3 -c "import json; print(json.load(open('$PUA_CONFIG'))..."` | `$PUA_CONFIG` interpolated into Python source string. A config path containing `'` or special chars would break the expression. |
| LOW | hooks/frustration-trigger.sh | 8 | same `python3 -c "...open('$PUA_CONFIG')..."` pattern | Same path-interpolation in shell string. |
| LOW | hooks/session-restore.sh | 28 | same `python3 -c "...open(os.path.expanduser('~/.pua/config.json'))..."` pattern | Uses `os.path.expanduser` (safe) but also has string-interpolated `$PUA_CONFIG` variants elsewhere in the file. |
| LOW | hooks/flavor-helper.sh | 15–16 | `python3 -c "import os,json; print(json.load(open(os.path.expanduser('~/.pua/config.json'))).get('flavor','alibaba'))"` | Uses hardcoded path in this call (safe), but the same helper is sourced by hooks that use `$PUA_CONFIG` interpolation. |
| LOW | hooks/pua-loop-hook.sh | 212 | `timeout 120 bash -c "$VERIFY_CMD"` | `$VERIFY_CMD` is user-provided at loop setup time (`/pua-loop --verify '...'`) and written to a local state file. Intentional design (user sets own verify command) but constitutes code execution from file-system state. |

**Summary**: 0 Critical · 0 High · 3 Medium · 5 Low → **CLEAR**

The Medium findings are dataflow concerns rather than intrusion vectors. The session upload is consent-gated with a clear opt-in UI. The `/tmp/pua-plugin-root` race is exploitable only by a local attacker with filesystem access, which is already game-over for most threat models. The leaderboard PII collection is the most substantive concern because email/phone leave the machine without user visibility into retention policy.

---

## Bugs

No functional correctness bugs in the command or hook logic. One structural issue:

| File | Issue |
|------|-------|
| agents/tech-lead-p9.md | Instructs Claude to `cat 同目录下的 references/p9-protocol.md`. Agents live in `agents/`; the protocol file is at `skills/pua/references/p9-protocol.md`. The relative-path reference will silently fail unless Claude resolves it by convention. |
| agents/cto-p10.md | Same: `cat 同目录下的 references/p10-protocol.md` — file is at `skills/pua/references/p10-protocol.md`. |
| agents/senior-engineer-p7.md | `cat 同目录下的 references/p7-protocol.md` — same mismatch. Note: this agent also uses `Glob **/pua/skills/pua/SKILL.md` for the skill (correct), but uses the broken relative path for the protocol file. |

---

## Security Fixes

Ranked by impact:

| Priority | File | Fix |
|----------|------|-----|
| P1 | hooks/stop-feedback.sh | Replace `/tmp/pua-plugin-root` temp-file path lookup with direct `${CLAUDE_PLUGIN_ROOT}` env var, same as hooks.json already uses. Eliminate the race window entirely. |
| P2 | skills/pro/SKILL.md | Add explicit in-UI disclosure of PII retention policy before collecting email/phone. Link to a privacy statement at `openpua.ai`. Collect phone only if user explicitly opts in to SMS notifications (currently collected together with email in one prompt). |
| P3 | hooks/failure-detector.sh, frustration-trigger.sh | Replace `python3 -c "...open('$PUA_CONFIG')..."` with `python3 -c "import os,json; c=json.load(open(os.path.expanduser('~/.pua/config.json')))"` using hardcoded expanduser path, removing the interpolation. |

---

## Quality Issues

Issues that reduce NL score but don't affect correctness.

| Rule | Files | Issue | Fix |
|------|-------|-------|-----|
| R09 | agents/tech-lead-p9.md, agents/senior-engineer-p7.md, agents/cto-p10.md | Zero `<example>` blocks (−15 each). Reliable agent triggering requires at least 2 examples per R09. | Add 2 `<example>` blocks per agent: one for the canonical use case (P9: "拆解这个需求并协调团队"), one edge case. |
| R10 | agents/tech-lead-p9.md, agents/senior-engineer-p7.md | `model` not declared (−5 each). P9 orchestration requires sonnet+ reasoning; P7 execution likely haiku-capable. | Add `model: sonnet` to tech-lead-p9.md; `model: haiku` is reasonable for senior-engineer-p7 (execution tasks) but `model: sonnet` is safer. |
| R12 | agents/tech-lead-p9.md, agents/cto-p10.md | No output format defined (−10 each). tech-lead-p9 has narrative tags but no template. cto-p10 has narrative tags but no structured output. | Add a "## Output Format" section with a concrete template for Sprint summary and team status report. |
| R06 | skills/p7/SKILL.md, skills/p9/SKILL.md, skills/p10/SKILL.md | Stub files (3–5 lines) with no examples (−10 each). Current pattern: "see references/p7-protocol.md". | Either inline key protocol content or add at least one worked example in the stub. The delegation pattern is fine for detail but not for orientation. |
| R12 | skills/p7/SKILL.md, skills/p9/SKILL.md, skills/p10/SKILL.md | No output format defined in stubs (−10 each). | Add a one-paragraph output format note pointing to the format defined in the protocol reference file. |
| R14 | commands/survey.md | Multi-step workflow (read file → ask questions → write JSON → upload) written in flat prose with no numbered steps (−10). | Break into 4 numbered steps matching the actual flow. |
| R16 | commands/survey.md | No output format defined (−10). What does the user see after completing the survey? | Add "## Output" section showing the confirmation message template. |
| R05 | skills/shot/SKILL.md | 449 lines — in the 400–500 range penalty band (−5). | Consider splitting the "shot" (concentrated) variant into a core + supplementary reference file at ~300 lines. |
| R07 | All pua/pua-en/pua-ja SKILL.md variants (×17) | No scope note directing users to related skills (−3 each). | Add a one-line scope note: "Covers PUA behavioral enforcement. For flavor switching see `/pua:flavor`. For team management see `pua:p9`." |

---

## Cross-Component

### Agent → Protocol File References (Broken Relative Paths)

`agents/tech-lead-p9.md`, `agents/cto-p10.md`, and `agents/senior-engineer-p7.md` all contain instructions like:
```
cat 同目录下的 references/p9-protocol.md
```

These files do not exist in `agents/`. The actual protocol files are at:
```
skills/pua/references/p9-protocol.md
skills/pua/references/p10-protocol.md
skills/pua/references/p7-protocol.md
```

The senior-engineer-p7 agent demonstrates the correct pattern for skill loading (`Glob **/pua/skills/pua/SKILL.md`) but reverts to relative path for the protocol file. All three agents should use the same glob pattern:
```
Glob **/pua/skills/pua/references/p9-protocol.md
```

### Stub Skills → Protocol References (Verified Present)

`skills/p7/SKILL.md`, `skills/p9/SKILL.md`, `skills/p10/SKILL.md` reference `../pua/references/p{7,9,10}-protocol.md`. These resolve to `skills/pua/references/` which **exists** and contains the referenced files. These references are valid.

### Cross-Platform Skill Duplication (Intentional)

The 12 cross-platform SKILL.md files (`codex/`, `kimi/`, `hermes/`, `codebuddy/`) are exact copies of `skills/pua/`, `skills/pua-en/`, and `skills/pua-ja/`. This is an intentional multi-platform compatibility pattern, not a maintenance issue. No action required.

### Commands → Skills (Verified)

All delegator commands (`/pua:kpi`, `/pua:mama`, etc.) reference `pua:pro`, `pua:mama`, etc. These all exist as `skills/{name}/SKILL.md`. References are valid.

---

## Recommendation

**Contribute: YES**

This is a high-quality, actively maintained plugin with excellent NL artifact structure. The score of 90/100 reflects genuine production readiness. The security findings are dataflow concerns with explicit consent gates already in place, not intrusion vectors.

**Prioritized fixes for contribution PR:**

1. **(Medium security)** Replace `/tmp/pua-plugin-root` with `${CLAUDE_PLUGIN_ROOT}` in `hooks/stop-feedback.sh`. Two-line change.
2. **(Bug × 3)** Fix agent protocol file paths from `同目录下的 references/` to glob pattern `Glob **/pua/skills/pua/references/`. Six-word change per agent.
3. **(R09 × 3)** Add `<example>` blocks to all three agents. Highest ROI quality fix — improves triggering reliability.
4. **(R10 × 2)** Add `model:` declarations to tech-lead-p9 and senior-engineer-p7.
5. **(R14)** Rewrite commands/survey.md body with numbered steps.

Fixes 1–2 are mechanical and verifiable. Fixes 3–5 require judgment calls appropriate for a community PR.
