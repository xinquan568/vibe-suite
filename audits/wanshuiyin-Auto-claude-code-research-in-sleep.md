# NLPM Audit: wanshuiyin/Auto-claude-code-research-in-sleep
**Date**: 2026-04-17  |  **Artifacts**: 100  |  **Strategy**: progressive
**NL Score**: 81/100
**Security**: BLOCKED
**Bugs**: 4  |  **Quality Issues**: 18  |  **Security Findings**: 11

## NL Score Summary

Skills are organized into four groups: main `skills/` (complete frontmatter), `skills-codex/` (missing allowed-tools), `skills-codex-claude-review/` (missing allowed-tools), and `skills-codex-gemini-review/` (missing allowed-tools). Scores reflect: -25 per missing required frontmatter field, -5 for missing allowed-tools, -2 per vague quantifier (cap -20), -10 for missing output format or missing numbered steps.

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/skills-codex/idea-discovery-robot/SKILL.md | skill | 74 | Missing allowed-tools; 5 vague words (appropriate, suitable, relevant, various, ensure) |
| skills/skills-codex/grant-proposal/SKILL.md | skill | 74 | Missing allowed-tools; 5 vague words (appropriate, effectively, ensure, various, suitable) |
| skills/skills-codex/paper-plan/SKILL.md | skill | 75 | Missing allowed-tools; 4 vague words (appropriate, suitable, ensure, relevant) |
| skills/skills-codex/paper-write/SKILL.md | skill | 76 | Missing allowed-tools; 4 vague words (appropriate, ensure, effectively, specific) |
| skills/skills-codex/paper-illustration/SKILL.md | skill | 76 | Missing allowed-tools; 4 vague words (appropriate, suitable, various, ensure) |
| skills/skills-codex-claude-review/research-refine/SKILL.md | skill | 76 | Missing allowed-tools; multiple vague quantifiers inherited from parent |
| skills/skills-codex-gemini-review/research-refine/SKILL.md | skill | 76 | Missing allowed-tools; multiple vague quantifiers |
| skills/skills-codex/auto-review-loop-llm/SKILL.md | skill | 77 | Missing allowed-tools; "appropriate", "comprehensive" |
| skills/skills-codex/novelty-check/SKILL.md | skill | 77 | Missing allowed-tools; "appropriate", "relevant" |
| skills/skills-codex/experiment-bridge/SKILL.md | skill | 77 | Missing allowed-tools; "appropriate", "proper" (multiple) |
| skills/skills-codex/auto-review-loop/SKILL.md | skill | 77 | Missing allowed-tools; "appropriate", "ensure", "comprehensive" |
| skills/skills-codex/research-review/SKILL.md | skill | 77 | Missing allowed-tools; "appropriate", "specifically", "specific" |
| skills/skills-codex/paper-figure/SKILL.md | skill | 77 | Missing allowed-tools; "appropriate", "various", "suitable" |
| skills/skills-codex/research-pipeline/SKILL.md | skill | 78 | Missing allowed-tools; "various", "appropriate" |
| skills/skills-codex-claude-review/auto-paper-improvement-loop/SKILL.md | skill | 78 | Missing allowed-tools; vague words from parent |
| skills/skills-codex-claude-review/research-review/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers |
| skills/skills-codex-claude-review/auto-review-loop/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers |
| skills/skills-codex-claude-review/paper-plan/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers |
| skills/skills-codex-claude-review/paper-write/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers |
| skills/skills-codex-claude-review/novelty-check/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers |
| skills/skills-codex-claude-review/paper-figure/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers |
| skills/skills-codex-gemini-review/paper-poster/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers from parent |
| skills/skills-codex-gemini-review/auto-paper-improvement-loop/SKILL.md | skill | 78 | Missing allowed-tools; vague quantifiers |
| skills/skills-codex/paper-compile/SKILL.md | skill | 79 | Missing allowed-tools; "appropriate", "reasonable" |
| skills/skills-codex/research-lit/SKILL.md | skill | 79 | Missing allowed-tools; "relevant", "appropriate" |
| skills/skills-codex/comm-lit-review/SKILL.md | skill | 79 | Missing allowed-tools; "relevant", "broader", "foundational" |
| skills/skills-codex/idea-discovery/SKILL.md | skill | 79 | Missing allowed-tools; "complete", "validated", "top" |
| skills/skills-codex/paper-writing/SKILL.md | skill | 79 | Missing allowed-tools; "polished", "automated" |
| skills/skills-codex/experiment-plan/SKILL.md | skill | 79 | Missing allowed-tools; "compact", "elegant", "strong" |
| skills/skills-codex/auto-paper-improvement-loop/SKILL.md | skill | 80 | Missing allowed-tools; minimal vague words |
| skills/skills-codex/deepxiv/SKILL.md | skill | 80 | Missing allowed-tools; "appropriate" |
| skills/skills-codex/monitor-experiment/SKILL.md | skill | 80 | Missing allowed-tools; "appropriate" |
| skills/skills-codex/paper-slides/SKILL.md | skill | 80 | Has allowed-tools; "modern" (contextual) |
| skills/skills-codex/arxiv/SKILL.md | skill | 80 | Missing allowed-tools; "relevant" |
| skills/skills-codex/rebuttal/SKILL.md | skill | 81 | Missing allowed-tools; "safe", "full" |
| skills/skills-codex/dse-loop/SKILL.md | skill | 81 | Missing allowed-tools; "reasonable", "typical" |
| skills/skills-codex/feishu-notify/SKILL.md | skill | 81 | Missing allowed-tools; "interactive", "rich" |
| skills/skills-codex/idea-creator/SKILL.md | skill | 81 | Missing allowed-tools; descriptive vague terms |
| skills/skills-codex/pixel-art/SKILL.md | skill | 81 | Missing allowed-tools; no numbered workflow steps (-10); "simple", "typically" |
| skills/skills-codex/training-check/SKILL.md | skill | 82 | Has allowed-tools; "ambiguous", "clearly" (judgment terms) |
| skills/skills-codex/ablation-planner/SKILL.md | skill | 82 | Has allowed-tools; "rigorous", "systematic" |
| skills/skills-codex/result-to-claim/SKILL.md | skill | 82 | Has allowed-tools; "appropriate", "specific", "objectively" |
| skills/skills-codex/proof-writer/SKILL.md | skill | 82 | Missing allowed-tools; "nontrivial", "honest" |
| skills/skills-codex/analyze-results/SKILL.md | skill | 83 | Missing allowed-tools; minimal vague words |
| skills/skills-codex/run-experiment/SKILL.md | skill | 83 | Missing allowed-tools; "necessary" |
| skills/skills-codex/formula-derivation/SKILL.md | skill | 83 | Missing allowed-tools; minimal vague words |
| skills/skills-codex/mermaid-diagram/SKILL.md | skill | 84 | Missing allowed-tools; clean structure |
| skills/skills-codex/research-refine-pipeline/SKILL.md | skill | 84 | Missing allowed-tools; clear phases |
| skills/skills-codex/auto-review-loop-minimax/SKILL.md | skill | 84 | Missing allowed-tools; few vague words |
| skills/skills-codex/paper-poster/SKILL.md | skill | 84 | Has allowed-tools; comprehensive but dense |
| skills/skills-codex/research-refine/SKILL.md | skill | 85 | Missing allowed-tools; excellent structure, minimal vague |
| skills/run-experiment/SKILL.md | skill | 78 | "necessary"; minor vague words |
| skills/analyze-results/SKILL.md | skill | 78 | Minimal vague words; short output section |
| skills/paper-poster/SKILL.md | skill | 78 | "appropriate" (layout); dense content |
| skills/auto-review-loop-minimax/SKILL.md | skill | 78 | Few vague words; curl with API key in examples |
| skills/pixel-art/SKILL.md | skill | 80 | Numbered steps present; minor vague ("simple", "typically") |
| skills/patent-review/SKILL.md | skill | 80 | Numbered steps; good output format |
| skills/prior-art-search/SKILL.md | skill | 80 | Numbered steps; good output format |
| skills/figure-spec/SKILL.md | skill | 80 | Numbered steps; clear output contract |
| skills/research-refine-pipeline/SKILL.md | skill | 80 | Clear phases; good output format |
| skills/mermaid-diagram/SKILL.md | skill | 82 | Comprehensive; minor vague ("appropriate" in academic style guide) |
| skills/research-refine/SKILL.md | skill | 83 | Excellent numbered phases; detailed output structure |
| skills/formula-derivation/SKILL.md | skill | 83 | Clean structure; minimal vague; clear output modes |
| skills/experiment-queue/SKILL.md | skill | 79 | Some vague quantifiers |
| skills/qzcli/SKILL.md | skill | 79 | Vague usage in context |
| skills/research-wiki/SKILL.md | skill | 79 | Some vague quantifiers |
| skills/training-check/SKILL.md | skill | 80 | Complete frontmatter; "clearly" used as judgment |
| skills/idea-creator/SKILL.md | skill | 79 | Vague descriptors ("concrete", "publishable", "genuine") |
| skills/paper-slides/SKILL.md | skill | 80 | Complete; "modern" (contextual) |
| skills/experiment-audit/SKILL.md | skill | 79 | Some vague words |
| skills/semantic-scholar/SKILL.md | skill | 79 | Minor vague usage |
| skills/embodiment-description/SKILL.md | skill | 79 | Some vague quantifiers |
| skills/alphaxiv/SKILL.md | skill | 79 | Minor vague usage |
| skills/feishu-notify/SKILL.md | skill | 80 | Clean structure; "interactive", "rich" |
| skills/system-profile/SKILL.md | skill | 75 | Missing allowed-tools; "appropriate", "sufficient", "necessary" |
| skills/proof-checker/SKILL.md | skill | 79 | Minor vague usage |
| skills/patent-pipeline/SKILL.md | skill | 79 | Minor vague usage |
| skills/invention-structuring/SKILL.md | skill | 79 | Minor vague usage |
| skills/writing-systems-papers/SKILL.md | skill | 80 | Complete frontmatter; clean structure |
| skills/exa-search/SKILL.md | skill | 79 | Minor vague usage |
| skills/experiment-plan/SKILL.md | skill | 79 | "compact", "elegant", "strong" |
| skills/paper-writing/SKILL.md | skill | 79 | "polished", "automated" |
| skills/idea-discovery/SKILL.md | skill | 79 | "complete", "validated" |
| skills/figure-description/SKILL.md | skill | 79 | Minor vague usage |
| skills/comm-lit-review/SKILL.md | skill | 79 | "relevant", "broader", "foundational" |
| skills/paper-claim-audit/SKILL.md | skill | 79 | Minor vague usage |
| skills/research-pipeline/SKILL.md | skill | 79 | "various", "appropriate" |
| skills/arxiv/SKILL.md | skill | 79 | "relevant" |
| skills/research-review/SKILL.md | skill | 79 | "appropriate" |
| skills/claims-drafting/SKILL.md | skill | 79 | Minor vague usage |
| skills/idea-discovery-robot/SKILL.md | skill | 76 | 4-5 vague words (appropriate, suitable, relevant, ensure) |
| skills/patent-novelty-check/SKILL.md | skill | 80 | Complete frontmatter; "appropriate", "rigorous" |
| skills/result-to-claim/SKILL.md | skill | 80 | Complete frontmatter; good structure |
| skills/serverless-modal/SKILL.md | skill | 80 | Complete frontmatter; numbered steps |
| skills/proof-writer/SKILL.md | skill | 82 | Good structure; "nontrivial", "honest" |
| skills/meta-optimize/SKILL.md | skill | 79 | Minor vague usage |
| skills/rebuttal/SKILL.md | skill | 80 | Numbered phases; "safe", "full" (contextual) |
| skills/dse-loop/SKILL.md | skill | 80 | Numbered phases; "reasonable", "typical" |
| skills/ablation-planner/SKILL.md | skill | 80 | Complete frontmatter; good structure |
| skills/auto-paper-improvement-loop/SKILL.md | skill | 80 | Numbered rounds; few vague words |

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 1 |
| High | 1 |
| Medium | 7 |
| Low | 2 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Shell scripts | `tools/save_trace.sh`, `tools/smart_update.sh`, `tools/meta_opt/check_ready.sh`, `tools/meta_opt/log_event.sh`, `mcp-servers/claude-review/run_with_claude_aws.sh` |
| Python scripts | `tools/experiment_queue/queue_manager.py`, `tools/experiment_queue/build_manifest.py`, `tools/figure_renderer.py`, `tools/arxiv_fetch.py`, `tools/deepxiv_fetch.py`, `tools/exa_search.py`, `tools/semantic_scholar_fetch.py`, `tools/research_wiki.py`, `tools/watchdog.py`, `tools/convert_skills_to_llm_chat.py`, `tools/generate_codex_claude_review_overrides.py`, `mcp-servers/claude-review/server.py`, `mcp-servers/feishu-bridge/server.py`, `mcp-servers/gemini-review/server.py`, `mcp-servers/llm-chat/server.py`, `mcp-servers/minimax-chat/server.py`, and test files |
| MCP configs | None found |
| Package manifests | `mcp-servers/llm-chat/requirements.txt`, `mcp-servers/minimax-chat/requirements.txt`, `mcp-servers/feishu-bridge/requirements.txt` |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | CRITICAL | `tools/save_trace.sh` | 104–133 | Shell vars interpolated into inline Python | `python3 -c "... 'purpose': '${PURPOSE}' ..."` — `--purpose`, `--model`, `--skill` CLI args interpolated directly into Python string literals; attacker-controlled value like `', ); __import__('os').system('id'); x=('` injects arbitrary Python. Reproduced pattern found in three separate `python3 -c` blocks in the same file (lines 104, 121, 137). |
| 2 | HIGH | `tools/experiment_queue/queue_manager.py` | 102 | `subprocess.run(cmd, shell=True, ...)` | General `run()` helper passes `cmd` to shell; downstream callers build `cmd` from manifest JSON values (e.g. `screen_name` in lines 123, 128) — manifest-controlled strings can inject shell commands. |
| 3 | MEDIUM | `mcp-servers/feishu-bridge/server.py` | 38–41 | `os.environ.get("FEISHU_APP_SECRET", "")` | FEISHU_APP_SECRET loaded from env; ensure it is never logged at DEBUG level and not exposed in HTTP error responses. |
| 4 | MEDIUM | `mcp-servers/claude-review/server.py` | 26–34 | `os.environ.get(...)` | CLAUDE_REVIEW_MODEL and related API config read from env; same log-exposure risk. |
| 5 | MEDIUM | `mcp-servers/gemini-review/server.py` | 34–41 | `os.environ.get(...)` | GEMINI_REVIEW_MODEL and API keys read from env; verify no key values appear in exception tracebacks or MCP response payloads. |
| 6 | MEDIUM | `mcp-servers/llm-chat/server.py` | — | `os.environ.get("LLM_API_KEY", ...)` | API key from env; same log-exposure concern. |
| 7 | MEDIUM | `mcp-servers/minimax-chat/server.py` | — | `os.environ.get("MINIMAX_API_KEY", ...)` | API key from env; same log-exposure concern. |
| 8 | MEDIUM | `tools/exa_search.py` | 77 | `os.getenv("EXA_API_KEY")` | API key from env; ensure not included in verbose logging or error messages sent back to Claude. |
| 9 | MEDIUM | `tools/semantic_scholar_fetch.py` | 80 | `os.environ.get("SEMANTIC_SCHOLAR_API_KEY")` | API key from env; same concern. |
| 10 | LOW | `mcp-servers/claude-review/run_with_claude_aws.sh` | 17 | `export PATH="$HOME/.local/bin:$HOME/bin:$PATH"` | Standard PATH prepend; low risk but documents a controlled PATH modification. |
| 11 | LOW | `tools/experiment_queue/queue_manager.py` | 110, 136 | Hardcoded nvidia-smi and tail commands | These specific calls use hardcoded strings and are safe; noted for completeness alongside finding #2. |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | `skills/skills-codex/*/SKILL.md` (40 files) | Missing `allowed-tools` field in frontmatter | Claude Code cannot enforce tool restriction when loading these skills; any tool may be called |
| 2 | `skills/skills-codex-claude-review/*/SKILL.md` (8 files) | Missing `allowed-tools` field in frontmatter | Same impact as #1 |
| 3 | `skills/skills-codex-gemini-review/*/SKILL.md` (3 files) | Missing `allowed-tools` field in frontmatter | Same impact as #1 |
| 4 | `skills/system-profile/SKILL.md` | Missing `allowed-tools` field in frontmatter | Skill can use any tool without restriction |

## Security Fixes (PR-worthy, Medium/Low only)

> **Critical and High findings (#1, #2) require private disclosure — do NOT open public PRs for these.**

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | `mcp-servers/feishu-bridge/server.py` | APP_SECRET may appear in logs/tracebacks | Mask secret in logging config; catch exceptions before they serialize env context |
| 2 | `mcp-servers/claude-review/server.py` | API key in env may appear in tracebacks | Add `logging.addFilter` to redact key patterns; wrap startup in try/except that doesn't print env |
| 3 | `mcp-servers/gemini-review/server.py` | API key env var log exposure | Same as #2 |
| 4 | `mcp-servers/llm-chat/server.py` | API key env var | Same as #2 |
| 5 | `mcp-servers/minimax-chat/server.py` | API key env var | Same as #2 |
| 6 | `tools/exa_search.py` | EXA_API_KEY log exposure | Redact key in any error output before returning to Claude |
| 7 | `tools/semantic_scholar_fetch.py` | API key log exposure | Same as #6 |
| 8 | `mcp-servers/claude-review/run_with_claude_aws.sh` | PATH modification | Document reason in comment; consider using `hash -r` after |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills-codex/idea-discovery-robot | "appropriate", "suitable", "relevant", "various", "ensure" | -10 |
| 2 | skills-codex/grant-proposal | "appropriate", "effectively", "ensure", "various", "suitable" | -10 |
| 3 | skills-codex/paper-plan | "appropriate", "suitable", "ensure", "relevant" | -8 |
| 4 | skills-codex/paper-write | "appropriate", "ensure", "effectively", "specific" | -8 |
| 5 | skills-codex/paper-illustration | "appropriate", "suitable", "various", "ensure" | -8 |
| 6 | skills-codex/experiment-bridge | "appropriate", "proper" (multiple) | -8 |
| 7 | skills/idea-discovery-robot | "appropriate", "suitable", "relevant", "ensure" | -8 |
| 8 | skills-codex/auto-review-loop | "appropriate", "ensure", "comprehensive" | -6 |
| 9 | skills-codex/research-review | "appropriate", "specifically" | -6 |
| 10 | skills-codex/paper-figure | "appropriate", "various", "suitable" | -6 |
| 11 | skills-codex/pixel-art | No numbered workflow steps (design-principle format) | -10 |
| 12 | skills/system-profile | "appropriate", "sufficient", "necessary" (without precise definitions) | -6 |
| 13 | Multiple skills (all) | "relevant" used without threshold definition (what counts as relevant?) | -2 per occurrence |
| 14 | Multiple skills (all) | "appropriate" used as instruction without specifying criteria | -2 per occurrence |
| 15 | skills-codex variants | skills-codex files reference `../../shared-references/` paths that may not exist in codex distribution | Broken references (quality, not security) |
| 16 | skills-codex/comm-lit-review | "broader", "foundational", "recent" without operational definitions | -6 |
| 17 | skills-codex/idea-discovery | "complete", "validated", "top" as vague success criteria | -6 |
| 18 | skills/auto-review-loop-minimax | curl with `$MINIMAX_API_KEY` in documented example; key visible in command history if run in shell | Informational — key is in header not URL, but shell history concern |

## Cross-Component

**Duplication**: The repository contains four near-parallel skill hierarchies:
- `skills/*/SKILL.md` — primary (used with Claude)
- `skills/skills-codex/*/SKILL.md` — Codex variants (≈38 files, stripped frontmatter)
- `skills/skills-codex-claude-review/*/SKILL.md` — Claude-review subset (8 files)
- `skills/skills-codex-gemini-review/*/SKILL.md` — Gemini-review subset (3 files)

Any improvement to a primary skill must be mirrored to up to three additional files. The `tools/smart_update.sh` script partially automates this but requires manual merge when local customizations exist.

**Broken references**: `skills-codex/` files contain relative paths like `../shared-references/output-versioning.md` and `../research-refine/SKILL.md`. These paths are valid within the repository layout but may break if a subset of codex skills is distributed independently.

**Consistency**: Skills that compose workflows (e.g. `research-refine-pipeline`) correctly reference sibling skills but do not version-pin them. If a referenced skill changes its interface, the pipeline skill fails silently.

**Tool coverage**: The `experiment-queue` skill relies on `tools/experiment_queue/queue_manager.py` which has the HIGH shell-injection finding (#2). Users invoking `/experiment-queue` would exercise the vulnerable code path.

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

Finding #1 (`tools/save_trace.sh` Python code injection via shell variable interpolation) is a confirmed CRITICAL pattern: attacker-controlled CLI argument values can escape the Python string literal and execute arbitrary Python code. This must be fixed privately before any public contribution activity.

Finding #2 (`queue_manager.py` `shell=True` with manifest-controlled command strings) is HIGH: an attacker who can write a malicious `manifest.json` can execute arbitrary shell commands on the experiment server.

**After private disclosure and fixes:**
- Re-run security scan to confirm both findings are resolved
- Submit NL fix PRs for the 51 files missing `allowed-tools` (bugs #1–4)
- Submit quality PRs reducing vague quantifier density in high-offender files
- Consider adding a CI check that validates `allowed-tools` presence in all SKILL.md frontmatter
