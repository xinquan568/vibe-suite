# NLPM Audit: qwibitai/nanoclaw
**Date**: 2026-04-25  |  **Artifacts**: 56  |  **Strategy**: batched
**NL Score**: 81/100
**Security**: CRITICAL
**Bugs**: 3  |  **Quality Issues**: 8  |  **Security Findings**: 6

---

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| `.claude/skills/add-parallel/SKILL.md` | Skill | 50 | **Missing frontmatter entirely** — no `name`, no `description` |
| `.claude/skills/customize/SKILL.md` | Skill | 62 | References v1 file paths (`src/ipc.ts`, `src/router.ts`, `src/db.ts`) that don't exist in v2 |
| `groups/main/CLAUDE.md` | Project memory | 65 | Mixed v1/v2 content — WhatsApp JID management, IPC paths, registered_groups.json, sender-allowlist at v1 host path |
| `.claude/skills/x-integration/SKILL.md` | Skill | 72 | Declares "Compatibility: NanoClaw v1.0.0" — outdated version label |
| `.claude/skills/init-onecli/SKILL.md` | Skill | 78 | Instructs `curl -fsSL onecli.sh/install \| sh` (security — see below); no output-format |
| `.claude/skills/debug/SKILL.md` | Skill | 79 | Multiple vague quantifiers (`appropriate`, `relevant`, `some`) |
| `.claude/skills/add-discord/SKILL.md` | Skill | 80 | No output-format; single-step sections |
| `.claude/skills/add-slack/SKILL.md` | Skill | 80 | No output-format; single-step sections |
| `.claude/skills/add-telegram/SKILL.md` | Skill | 80 | No output-format; single-step sections |
| `.claude/skills/add-whatsapp/SKILL.md` | Skill | 80 | No output-format; single-step sections |
| `.claude/skills/add-whatsapp-cloud/SKILL.md` | Skill | 80 | No output-format |
| `.claude/skills/add-opencode/SKILL.md` | Skill | 80 | No output-format |
| `.claude/skills/manage-channels/SKILL.md` | Skill | 81 | Vague quantifiers (`various`, `appropriate`) |
| `.claude/skills/setup/SKILL.md` | Skill | 82 | Vague (`appropriate`, `some`) |
| `.claude/skills/convert-to-apple-container/SKILL.md` | Skill | 82 | Sudo in examples (security); no output-format |
| `.claude/skills/migrate-from-openclaw/SKILL.md` | Skill | 82 | No output-format |
| `.claude/skills/migrate-nanoclaw/SKILL.md` | Skill | 82 | No output-format |
| `.claude/skills/update-nanoclaw/SKILL.md` | Skill | 83 | Minor vagueness |
| `.claude/skills/update-skills/SKILL.md` | Skill | 83 | No output-format |
| `.claude/skills/add-wechat/SKILL.md` | Skill | 83 | No output-format |
| `.claude/skills/add-signal/SKILL.md` | Skill | 83 | No output-format |
| `.claude/skills/add-teams/SKILL.md` | Skill | 83 | No output-format |
| `.claude/skills/add-matrix/SKILL.md` | Skill | 83 | No output-format |
| `.claude/skills/add-linear/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-github/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-gchat/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-resend/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-imessage/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-webex/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-codex/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-emacs/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-vercel/SKILL.md` | Skill | 84 | No output-format |
| `.claude/skills/add-vercel/container-skills/vercel-cli/SKILL.md` | Skill | 85 | Minor |
| `.claude/skills/add-gcal-tool/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-gmail-tool/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-ollama-provider/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-ollama-tool/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-dashboard/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-atomic-chat-tool/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-macos-statusbar/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-karpathy-llm-wiki/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/claw/SKILL.md` | Skill | 86 | Minor |
| `.claude/skills/use-native-credential-proxy/SKILL.md` | Skill | 86 | Minor |
| `.claude/skills/manage-mounts/SKILL.md` | Skill | 86 | Minor |
| `.claude/skills/init-first-agent/SKILL.md` | Skill | 87 | Minor |
| `.claude/skills/qodo-pr-resolver/SKILL.md` | Skill | 87 | Minor |
| `container/skills/self-customize/SKILL.md` | Container skill | 88 | Minor |
| `container/skills/agent-browser/SKILL.md` | Container skill | 92 | Clean |
| `container/skills/slack-formatting/SKILL.md` | Container skill | 90 | Minor |
| `container/skills/welcome/SKILL.md` | Container skill | 88 | Minor |
| `container/CLAUDE.md` | Project memory | 88 | Minor vagueness |
| `groups/global/CLAUDE.md` | Project memory | 82 | v1-era sections in global instructions |
| `CLAUDE.md` | Project memory | 92 | Excellent — comprehensive, well-structured, clear supply-chain rules |
| `.claude/skills/get-qodo-rules/SKILL.md` | Skill | 92 | Best-scored skill — has version, allowed-tools, triggers |
| `.claude/skills/add-ollama-tool/SKILL.md` | Skill | 85 | No output-format |
| `.claude/skills/add-ollama-provider/SKILL.md` | Skill | 85 | No output-format |

---

## Bug Findings

### BUG-01 — Missing Frontmatter: `add-parallel/SKILL.md`
**Severity**: high | **Penalty**: -50  
**File**: `.claude/skills/add-parallel/SKILL.md`

The file has no YAML frontmatter at all — it opens directly with `# Add Parallel AI Integration`. The `name` and `description` fields required for skill registration are absent. This skill cannot be installed or referenced by name until the frontmatter is added.

**Fix**: Add at minimum:
```yaml
---
name: add-parallel
description: Install the Parallel AI provider integration for NanoClaw
---
```

---

### BUG-02 — Broken v1 File References: `customize/SKILL.md`
**Severity**: high | **Penalty**: -15  
**File**: `.claude/skills/customize/SKILL.md`

The skill references source files that existed in v1 but were removed or relocated in v2:
- `src/ipc.ts` (removed — v2 uses session DBs, not IPC)
- `src/channels/whatsapp.ts` (moved to `channels` branch, installed via `/add-whatsapp`)
- `src/router.ts` (exists in v2 but different API)
- `src/db.ts` (removed — replaced by `src/db/` directory)
- `src/whatsapp-auth.ts` (removed)
- `groups/CLAUDE.md` (path changed — now per-group folders)

These stale references will cause Claude to try editing nonexistent files, wasting tokens and confusing operators.

**Fix**: Update the skill to reference v2 paths. The v2 equivalents are documented in `CLAUDE.md §Key Files`.

---

### BUG-03 — v1/v2 Mixed Content: `groups/main/CLAUDE.md`
**Severity**: medium | **Penalty**: -20  
**File**: `groups/main/CLAUDE.md`

This file appears to be a v1-era CLAUDE.md that was never fully migrated to the v2 entity model. It instructs the agent to:
- Read `/workspace/project/data/registered_groups.json` (v1 — v2 uses central SQLite DB)
- Manage WhatsApp JIDs directly (`120363336345536173@g.us`)
- Use `/workspace/ipc/` file paths for group management (removed in v2)
- Reference `~/.config/nanoclaw/sender-allowlist.json` on the host (v1 path)
- Use the `register_group` MCP tool (not part of v2's `mcp__nanoclaw__*` surface)

Meanwhile it also contains v2 concepts (`messaging_group_agents`, `agent_group_members`). The result is an internally inconsistent document that will cause the main-channel agent to attempt v1-style operations against a v2 system.

**Fix**: Replace with a v2-native CLAUDE.md for the main channel that references the SQLite DB (`data/v2.db`), v2 entity model concepts, and correct MCP tools. Keep the admin context section (correct) and remove all JID/IPC/registered_groups.json content.

---

## Quality Findings

### QUAL-01 — Systematic Missing `output-format` Across Channel Install Skills
**Severity**: low | **Penalty**: -10 each  
**Files**: All `add-<channel>/SKILL.md` files (≈20 skills)

None of the channel install skills declare an `output-format` in their frontmatter. For operational skills that produce observable state changes (channel added, pnpm install run, imports wired), documenting the expected output helps Claude confirm success and helps operators debug failures.

**Fix**: Add `output-format: "confirmation with changed files and next steps"` to each install skill's frontmatter, or add a `## Expected Output` section to the body.

---

### QUAL-02 — Vague Quantifiers Across Multiple Skills
**Severity**: low | **Penalty**: -2 each  
**Files**: `debug/SKILL.md`, `manage-channels/SKILL.md`, `setup/SKILL.md`, others

Recurring vague quantifiers found: `appropriate`, `relevant`, `some`, `various`, `sufficient`. Each is scored -2 under R29. The `debug` skill alone has ≥6 instances.

---

### QUAL-03 — v1 Compatibility Caveat: `x-integration/SKILL.md`
**Severity**: low | **Penalty**: -10  
**File**: `.claude/skills/x-integration/SKILL.md`

The skill contains: _"Compatibility: NanoClaw v1.0.0. Directory structure may change in future versions."_ This is misleading in a v2 repo — it signals to Claude that the skill may not apply to the current version, creating unnecessary uncertainty.

**Fix**: Update or remove the compatibility note. If the skill has been updated for v2, state that. If not, gate the skill with a `## Prerequisites` section noting v2 compatibility status.

---

## Security Findings

### SEC-CRITICAL: curl-pipe-to-shell in `init-onecli/SKILL.md`
**Severity**: critical  
**File**: `.claude/skills/init-onecli/SKILL.md`, lines ~62–63  
**Pattern**: `SEC-curl-pipe-sh`

The skill instructs Claude to execute:
```bash
curl -fsSL onecli.sh/install | sh
curl -fsSL onecli.sh/cli/install | sh
```

Curl-pipe-to-shell fetches and executes arbitrary code from a remote URL without verification. This is NLPM's highest-severity security pattern. If `onecli.sh` is compromised, typosquatted, or redirected (DNS hijacking, CDN compromise), every NanoClaw operator who runs `/init-onecli` executes the attacker's code with user privileges.

**Risk factors**:
- Domain `onecli.sh` uses a short TLD — higher squatting/expiry risk than `.com`/`.io`
- No checksum verification in the install steps
- No fallback to manual download

**Fix**: Replace with a pinned, checksum-verified install:
```bash
# Download, verify, then execute
curl -fsSL https://onecli.sh/install -o /tmp/onecli-install.sh
echo "<expected-sha256>  /tmp/onecli-install.sh" | sha256sum -c
sh /tmp/onecli-install.sh
```
Or document the checksum separately and instruct Claude to verify before execution. At minimum, add a warning comment in the skill noting the trust assumption.

---

### SEC-HIGH-01: sudo Usage in `convert-to-apple-container/SKILL.md`
**Severity**: high  
**File**: `.claude/skills/convert-to-apple-container/SKILL.md`  
**Pattern**: `SEC-sudo-usage`

Phase 3 of the skill instructs Claude to run `sudo pfctl` and `sudo tee` to configure packet filtering rules. These commands require elevated privileges and modify system networking.

**Risk**: Claude executing `sudo` commands in a skill context lacks the interactive verification a human would apply before entering their password. Errors in the pfctl rules can break network connectivity system-wide.

**Fix**: Add an explicit `## Requires sudo` section that explains what requires privilege and why, and prompt the operator to review the commands before Claude executes them. Consider adding `-- Requires human confirmation before running sudo commands --` as a pre-step.

---

### SEC-HIGH-02: User Input in sed Substitution in `add-parallel/SKILL.md`
**Severity**: high  
**File**: `.claude/skills/add-parallel/SKILL.md`  
**Pattern**: `SEC-shell-injection-sed`

The skill uses the pattern:
```bash
sed -i.bak "s/^PARALLEL_API_KEY=.*/PARALLEL_API_KEY=${API_KEY_FROM_USER}/"
```

If `API_KEY_FROM_USER` contains sed metacharacters (`/`, `&`, `\`) or shell metacharacters, this command can produce unexpected behavior or execute unintended code. API keys are long random strings but users can enter anything.

**Fix**: Use a safer `.env` writing approach that doesn't interpolate user input into a regex replacement:
```bash
grep -v '^PARALLEL_API_KEY=' .env > .env.tmp
echo "PARALLEL_API_KEY=${API_KEY_FROM_USER}" >> .env.tmp
mv .env.tmp .env
```

---

### SEC-MED-01: postinstall Execution Hook in `package.json`
**Severity**: medium  
**File**: `package.json`  
**Pattern**: `SEC-postinstall-script`

`"prepare": "husky"` runs on `pnpm install`. While husky is well-known, the `prepare` hook is a common vector for supply-chain attacks — any package that compromises the build environment could alter this hook.

The repo already uses `pnpm minimumReleaseAge: 4320` (documented in `CLAUDE.md`) which mitigates the primary risk. The `onlyBuiltDependencies` policy in `pnpm-workspace.yaml` limits build-script execution to approved packages.

**Risk**: Low-medium given existing mitigations, but worth noting.

---

### SEC-MED-02: Browser Session Storage in `x-integration/scripts/setup.ts`
**Severity**: medium  
**File**: `.claude/skills/x-integration/scripts/setup.ts`  
**Pattern**: `SEC-browser-session-storage`

The setup script persists a full Chrome browser session (including cookies and localStorage) to disk after logging into `x.com`. This session can be replayed to authenticate as the user without credentials.

**Risk**: The session file at `config.browserDataDir` should be treated like a credential — it grants full X account access. If the host machine is compromised or the session path is readable by other processes, account takeover is trivial.

**Fix**: Document that `config.browserDataDir` must be protected (chmod 700 equivalent). The skill's SKILL.md should warn operators about the security implications of stored browser sessions.

---

### SEC-MED-03: execFileSync with argv-Provided Path in `scripts/run-migrations.ts`
**Severity**: medium  
**File**: `scripts/run-migrations.ts`, line 86  
**Pattern**: `SEC-argv-path-exec`

`execFileSync(tsxBin, [migrationIndex, projectRoot], ...)` runs TypeScript files whose paths derive from `process.argv[4]` (`newCorePath`). A malicious `newCorePath` could point to an attacker-controlled `.ts` file that executes arbitrary code.

**Risk**: This is a developer/CI script, not agent-facing, so exploitation requires the attacker to already control the CI environment or developer machine. **Assessed low-medium in practice**.

---

## Consistency Notes

### CC-01: `groups/main/CLAUDE.md` references IPC paths removed in v2
The file references `/workspace/ipc/available_groups.json` and `/workspace/ipc/tasks/`. These paths were part of the v1 file-based IPC system. In v2, group management goes through SQLite and MCP tools. The main agent will not find these files and may emit errors or fall back incorrectly.

### CC-02: `customize/SKILL.md` expects v1 channel modules at trunk
The skill tells Claude to edit `src/channels/whatsapp.ts` and related files directly. In v2, channel adapters are installed from the `channels` branch via `/add-<channel>` skills — they are not present on trunk by default. This creates a false expectation that editing the channel module is a manual in-repo operation.

---

## Recommendations

**P0 (Blocking)**
1. Fix `add-parallel/SKILL.md` — add frontmatter. Currently uninstallable by name.
2. Review `init-onecli/SKILL.md` curl-pipe install steps — add checksum verification or a warning.

**P1 (High Priority)**
3. Rewrite `groups/main/CLAUDE.md` for v2 — the v1 content will cause the main agent to attempt incorrect operations.
4. Update `customize/SKILL.md` to reference v2 file paths.

**P2 (Cleanup)**
5. Update or remove the "Compatibility: NanoClaw v1.0.0" line from `x-integration/SKILL.md`.
6. Add `output-format` declarations to channel install skills (batch fix: sed across all `add-*/SKILL.md`).
7. Document `browserDataDir` security implications in `x-integration/SKILL.md`.
8. Add human-confirmation prompt before sudo steps in `convert-to-apple-container/SKILL.md`.

---

## Score Methodology

100-point scale per artifact. Start at 100, subtract:
- Missing `name` or `description` frontmatter: -25 each
- Missing `output-format`: -10
- Broken/stale file references: -15
- Explicit version mismatch / obsolete caveat: -10
- Vague quantifiers: -2 each (capped -20)
- v1/v2 content mixing in CLAUDE.md: -20

Weighted average across 56 artifacts: **81/100**  
Threshold: 70/100 (default). Repository **passes** the threshold despite the three outliers.  
Outliers drag the average: without `add-parallel` (50), `customize` (62), `groups/main` (65), the average is **84/100**.
