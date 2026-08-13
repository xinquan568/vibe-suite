# NLPM Audit: OpenRaiser/NanoResearch
**Date**: 2026-04-20  |  **Artifacts**: 26  |  **Strategy**: batched
**NL Score**: 73/100
**Security**: BLOCKED
**Bugs**: 9  |  **Quality Issues**: 27  |  **Security Findings**: 6

---

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| .claude/commands/ideation.md | command | 37 | Missing frontmatter (name+description) −50 |
| .claude/commands/planning.md | command | 37 | Missing frontmatter (name+description) −50 |
| .claude/commands/experiment.md | command | 39 | Missing frontmatter (name+description) −50 |
| .claude/commands/research.md | command | 39 | Missing frontmatter (name+description) −50 |
| .claude/commands/review.md | command | 39 | Missing frontmatter (name+description) −50 |
| .claude/commands/writing.md | command | 39 | Missing frontmatter (name+description) −50 |
| .claude/commands/analysis.md | command | 41 | Missing frontmatter (name+description) −50 |
| .claude/commands/resume.md | command | 45 | Missing frontmatter (name+description) −50 |
| .claude/commands/status.md | command | 45 | Missing frontmatter (name+description) −50 |
| skills/vendor-ai-research/unsloth/SKILL.md | skill | 77 | Sparse/placeholder content, no examples −15, vague template lang −8 |
| skills/nanoresearch-ideation/SKILL.md | skill | 79 | No example blocks −15, vague quantifiers −6 |
| skills/nanoresearch-planning/SKILL.md | skill | 79 | No example blocks −15, vague quantifiers −6 |
| skills/nanoresearch-experiment/SKILL.md | skill | 81 | No example blocks −15, vague quantifiers −4 |
| skills/nanoresearch-writing/SKILL.md | skill | 81 | No example blocks −15, vague quantifiers −4 |
| skills/vendor-ai-research/0-autoresearch-skill/SKILL.md | skill | 90 | Vague quantifiers (meaningful, appropriate, sufficient) −10 |
| skills/vendor-ai-research/ml-paper-writing/SKILL.md | skill | 92 | Vague quantifiers (well-written, appropriate, clear) −8 |
| skills/vendor-ai-research/academic-plotting/SKILL.md | skill | 94 | Vague quantifiers (publication-quality, appropriate) −6 |
| CLAUDE.md | config | 94 | Minor vague language −6 |
| skills/vendor-ai-research/creative-thinking-for-research/SKILL.md | skill | 96 | Vague quantifiers (appropriate) −4 |
| skills/vendor-ai-research/accelerate/SKILL.md | skill | 96 | Vague quantifiers (simplest, easy) −4 |
| skills/vendor-ai-research/peft/SKILL.md | skill | 96 | Vague quantifiers (appropriate, significant) −4 |
| skills/vendor-ai-research/lm-evaluation-harness/SKILL.md | skill | 96 | Vague quantifiers (appropriate) −4 |
| skills/vendor-ai-research/brainstorming-research-ideas/SKILL.md | skill | 96 | Vague quantifiers (appropriate, relevant) −4 |
| skills/vendor-ai-research/ml-training-recipes/SKILL.md | skill | 96 | Vague quantifiers (appropriate, suitable) −4 |
| skills/vendor-ai-research/skypilot/SKILL.md | skill | 96 | Vague quantifiers (appropriate, suitable) −4 |
| skills/vendor-ai-research/ray-data/SKILL.md | skill | 98 | Minor vague language −2 |

**Score distribution**: Commands cluster at 37–45 due to the consistent missing-frontmatter penalty (−50). Vendor skills score 90–98. Core nanoresearch skills score 77–81.

---

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 (1 pre-scan false positive — see note) |
| High | 1 |
| Medium | 3 |
| Low | 1 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Shell scripts (.sh) | 0 |
| Python scripts (.py) | 175 (under `nanoresearch/` and `mcp_server/`) |
| MCP configs | 0 |
| Package manifests | requirements.txt (12 dependencies) |

**Pre-scan critical match note**: The pre-scan flagged `nanoresearch/agents/experiment_tools.py:46` as Critical (curl-pipe-sh). This is a **false positive** — the pattern appears inside a Python regex *block list* (`_BLOCKED_COMMANDS`) that the runtime uses to **refuse** dangerous shell commands. The code actively prevents curl-pipe-sh, it does not execute it.

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH | nanoresearch/agents/debug.py | 148 | subprocess with shell=True | `subprocess.run(cmd, shell=True, ...)` in `_probe_env_sync`. `cmd` is constructed from a workspace path (derived from user-supplied research topic string). If topic slug generation does not strip shell metacharacters, an adversarial topic string could achieve command injection. |
| 2 | MEDIUM | nanoresearch/config.py | 140–143 | Runtime package install | `runtime_auto_install_enabled: bool = True` with `runtime_auto_install_allowlist: list[str] = []` (empty default). Allows AI-generated experiment code to trigger arbitrary pip installs up to 50 packages during execution. Supply-chain risk if LLM is induced to generate malicious requirements. |
| 3 | MEDIUM | mcp_server/tools/ | various | Network calls | MCP server makes external API calls to Semantic Scholar, OpenAlex, GitHub, arXiv, and DuckDuckGo. API keys for S2 and OpenAlex are read from environment variables and forwarded in HTTP headers — correct pattern, but the broad external call surface warrants disclosure. |
| 4 | MEDIUM | nanoresearch/agents/experiment/react_mode.py | 166 | PATH in script template | `export PATH=/usr/local/bin:/usr/bin:$PATH` is written into an Apptainer/Singularity container definition template. Risk is limited to the container environment, not the host; flagged because it matches the HIGH pattern signature. Actual severity is LOW. |
| 5 | LOW | requirements.txt | 1–12 | Unpinned dependency versions | All 12 dependencies use `>=` lower bounds with `<` major-version caps (e.g., `openai>=1.14.0,<2.0.0`). No exact pins; minor/patch version changes could introduce regressions. Low immediate risk; no known active exploits. |
| 6 | LOW | nanoresearch/agents/experiment_tools.py | 46 | curl-pipe-sh (false positive) | Pattern found inside `_BLOCKED_COMMANDS` regex block list. Code prevents this pattern from executing. Reported for completeness; no action required. |

---

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | .claude/commands/research.md | Missing `allowed-tools` frontmatter declaration | Command can invoke any Claude Code tool without restriction; unintended tool use possible |
| 2 | .claude/commands/analysis.md | Missing `allowed-tools` frontmatter declaration | Same as above |
| 3 | .claude/commands/ideation.md | Missing `allowed-tools` frontmatter declaration | Same as above |
| 4 | .claude/commands/review.md | Missing `allowed-tools` frontmatter declaration | Same as above |
| 5 | .claude/commands/resume.md | Missing `allowed-tools` frontmatter declaration | Same as above |
| 6 | .claude/commands/status.md | Missing `allowed-tools` frontmatter declaration | Same as above |
| 7 | .claude/commands/experiment.md | Missing `allowed-tools` frontmatter declaration | Same as above |
| 8 | .claude/commands/planning.md | Missing `allowed-tools` frontmatter declaration | Same as above |
| 9 | .claude/commands/writing.md | Missing `allowed-tools` frontmatter declaration | Same as above |

---

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | requirements.txt | Unpinned minor versions | Pin exact versions (e.g., `openai==1.14.0`) or add a lock file (`pip-compile requirements.txt`) |
| 2 | nanoresearch/config.py | Empty `runtime_auto_install_allowlist` with auto-install enabled | Populate a default allowlist of known-safe packages (numpy, torch, scikit-learn, etc.) or flip the logic so an empty allowlist means deny-all |
| 3 | nanoresearch/agents/experiment/react_mode.py | PATH modification written into container definition | Not a real risk in container context; add a comment clarifying this is container-only if the pattern triggers internal scanners |

*(Finding #1 HIGH — `debug.py:148` `shell=True` — must be disclosed privately, not fixed via public PR.)*

---

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | All 9 commands | Missing YAML frontmatter block (name, description fields) | −50 each |
| 2 | skills/nanoresearch-experiment/SKILL.md | No example blocks showing how to invoke or use the skill | −15 |
| 3 | skills/nanoresearch-ideation/SKILL.md | No example blocks | −15 |
| 4 | skills/nanoresearch-writing/SKILL.md | No example blocks | −15 |
| 5 | skills/nanoresearch-planning/SKILL.md | No example blocks | −15 |
| 6 | skills/vendor-ai-research/unsloth/SKILL.md | Body is largely boilerplate placeholder ("Quick reference patterns will be added as you use the skill"); no actual code examples; all content deferred to `references/` subdirectory without inline summary | −23 |
| 7 | .claude/commands/ideation.md | Vague quantifiers: "appropriate" (×1), "novel" (×1), "suitable" (×1), "diverse" (×1) | −8 |
| 8 | .claude/commands/planning.md | Vague quantifiers: "appropriate" (×1), "suitable" (×1), "sufficient" (×1), "relevant" (×1) | −8 |
| 9 | .claude/commands/research.md | Vague quantifiers: "appropriate" (×1), "most promising" (×1), "suitable" (×1) | −6 |
| 10 | .claude/commands/review.md | Vague quantifiers: "well-written" (×1), "appropriate" (×1), "well-organized" (×1) | −6 |
| 11 | .claude/commands/experiment.md | Vague quantifiers: "appropriate" (×1), "relevant" (×1), "sufficient" (×1) | −6 |
| 12 | .claude/commands/writing.md | Vague quantifiers: "publication-quality" (×1), "appropriate" (×1), "sufficient" (×1) | −6 |
| 13 | .claude/commands/analysis.md | Vague quantifiers: "relevant" (×1), "sufficient" (×1) | −4 |
| 14 | skills/nanoresearch-ideation/SKILL.md | Vague quantifiers: "relevant" (×1), "appropriate" (×1), "novel" (×1) | −6 |
| 15 | skills/nanoresearch-planning/SKILL.md | Vague quantifiers: "appropriate" (×1), "suitable" (×1), "relevant" (×1) | −6 |
| 16 | skills/vendor-ai-research/0-autoresearch-skill/SKILL.md | Vague quantifiers: "meaningful" (×1), "appropriate" (×1), "relevant" (×1), "sufficient" (×1) | −10 |
| 17 | skills/vendor-ai-research/ml-paper-writing/SKILL.md | Vague quantifiers: "well-written" (×1), "appropriate" (×1), "sufficient" (×1), "clear" (×1) | −8 |
| 18 | skills/nanoresearch-experiment/SKILL.md | Vague quantifiers: "appropriate" (×1), implicit "suitable" context | −4 |
| 19 | skills/nanoresearch-writing/SKILL.md | Vague quantifiers: "publication-quality" (×1), "appropriate" (×1) | −4 |
| 20 | skills/vendor-ai-research/academic-plotting/SKILL.md | Vague quantifiers: "publication-quality" (×1), "appropriate" (×1), "clear" (×1) | −6 |
| 21 | skills/vendor-ai-research/creative-thinking-for-research/SKILL.md | Vague quantifiers: "appropriate" (×1), "genuinely novel" (×1) | −4 |
| 22 | skills/vendor-ai-research/accelerate/SKILL.md | Vague quantifiers: "simplest" (×1), "easy" (×1) | −4 |
| 23 | skills/vendor-ai-research/peft/SKILL.md | Vague quantifiers: "appropriate" (×1), "significant" (×1) | −4 |
| 24 | skills/vendor-ai-research/lm-evaluation-harness/SKILL.md | Vague quantifiers: "appropriate" (×1) | −4 |
| 25 | skills/vendor-ai-research/brainstorming-research-ideas/SKILL.md | Vague quantifiers: "appropriate" (×1), "relevant" (×1) | −4 |
| 26 | skills/vendor-ai-research/ml-training-recipes/SKILL.md | Vague quantifiers: "appropriate" (×1), "suitable" (×1) | −4 |
| 27 | skills/vendor-ai-research/skypilot/SKILL.md | Vague quantifiers: "appropriate" (×1), "suitable" (×1) | −4 |

---

## Cross-Component

**Consistent**: All 9 commands cross-reference each other via `/project:X` slash commands, and every referenced command exists. CLAUDE.md lists all 9 commands accurately. The 9-stage pipeline (ideation → planning → setup → coding → execution → analysis → figure_gen → writing → review) is described identically in CLAUDE.md, `research.md`, and the MCP-facing pipeline code.

**MCP tool naming**: The core nanoresearch skills (`nanoresearch-ideation`, `nanoresearch-writing`) declare tool names like `search_arxiv`, `generate_latex`, `compile_pdf`, `generate_figure` that match the MCP server tools in `mcp_server/tools/`. This dependency is not mentioned in CLAUDE.md — users who install only the NL commands without the MCP server will see opaque tool-not-found failures. CLAUDE.md should document the MCP server as a dependency.

**Schema dual-compatibility**: `resume.md` and `status.md` document two manifest schemas (old Python CLI v1.1, new Claude Code lowercase). This cross-compatibility layer is correct and intentional, but is not mentioned in CLAUDE.md. If the Python CLI is deprecated, this normalization code will become dead weight.

**Orphaned**: `skills/vendor-ai-research/unsloth/SKILL.md` references a `references/llms-txt.md` file. No `references/` subdirectory is present in the target repo (not cloned into the audit workspace). If the skill ships without reference files, agents loading this skill will get placeholder text and a broken reference.

**`autoresearch` skill**: This vendor skill invokes `/loop 20m` (Claude Code only) and `cron.add` (OpenClaw only). These are platform-specific and will silently fail outside those environments. No fallback or warning is documented in the skill.

---

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

Reason: A confirmed HIGH-severity finding exists in `nanoresearch/agents/debug.py:148` (`subprocess.run(cmd, shell=True, ...)`). The `cmd` string is constructed from a workspace path derived from the user-supplied research topic. If the topic-to-slug conversion does not sanitize shell metacharacters, an adversarial topic string can achieve command injection. This must be reported to the maintainers privately before any public contribution.

**For the maintainers** (private disclosure): Replace `shell=True` with a list-form invocation: `subprocess.run([python_cmd, "--version"], capture_output=True, text=True, ...)`. This eliminates the shell interpretation layer entirely and is sufficient to close the injection vector.

**After the security finding is resolved**, the NL artifacts have 9 PR-worthy bugs (missing `allowed-tools` on all commands) and several quality improvements worth contributing, particularly:
- Add YAML frontmatter to all 9 commands (name, description, allowed-tools)
- Add concrete usage examples to the 4 core nanoresearch skills
- Flesh out `unsloth/SKILL.md` with actual content instead of placeholder text
- Document the MCP server dependency in CLAUDE.md
