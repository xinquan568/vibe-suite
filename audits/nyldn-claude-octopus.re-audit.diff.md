# Re-Audit: nyldn/claude-octopus

**Date**: 2026-04-24  |  **Before**: `unknown` (79/100)  |  **After**: `14e8ee4` (82/100)

## Summary

| Outcome | Count |
|---------|------:|
| fixed — applied separately | 4 |
| fixed — upstream, not via our PR | 19 |
| newly introduced (regressions) | 12 |

## Original findings — verification

| # | File | Line | Rule | Pattern | Outcome | PR |
|---|------|------|------|---------|---------|----|
| 1 | `code-reviewer.md` | — | BUG-read-only-write | `write-edit-on-readonly` | fixed — upstream, not via our PR |  |
| 2 | `performance-engineer.md` | — | BUG-read-only-write | `write-edit-on-readonly` | fixed — upstream, not via our PR |  |
| 3 | `cloud-architect.md` | — | BUG-read-only-write | `write-edit-on-readonly` | fixed — upstream, not via our PR |  |
| 4 | `.github/agents/` | — | BUG-read-only-write | `write-edit-on-readonly` | fixed — upstream, not via our PR |  |
| 5 | `agents/droids/` | — | BUG-unclassified | `none-of-the-droid-agents-declare-a-tools` | fixed — applied separately | #293 |
| 6 | `agents/personas/python-pro.md` | — | BUG-unclassified | `the-python-pro-persona-body-describes-us` | fixed — applied separately | #294 |
| 7 | `skills/skill-extract/SKILL.md` | — | BUG-unclassified | `multiple-sections-are-explicitly-marked` | fixed — applied separately | #295 |
| 8 | `hooks/user-prompt-submit.sh` | — | BUG-unclassified | `the-hook-uses-python3-for-json-parsing-w` | fixed — applied separately | #296 |
| 9 | `agents/personas/openclaw-admin.md` | — | SEC-curl-pipe-sh | `curl-pipe-sh` | fixed — upstream, not via our PR |  |
| 10 | ``.github/agents/` are minimal stubs (score: ~63/100)` | — | UNCLASSIFIED | `github-agents-are-minimal-stubs-score-63` | fixed — upstream, not via our PR |  |
| 11 | ``.claude/commands/` missing `allowed-tools` in ~65% of files` | — | BUG-undeclared-tool | `missing-allowed-tools` | fixed — upstream, not via our PR |  |
| 12 | `Vague quantifiers in skill descriptions` | — | R01 | `vague-quantifiers` | fixed — upstream, not via our PR |  |
| 13 | ``agents/personas/devops-troubleshooter.md` missing `tools` declaration` | — | BUG-undeclared-tool | `missing-tools-declaration` | fixed — upstream, not via our PR |  |
| 14 | ``agents/personas/incident-responder.md` missing `tools` declaration` | — | BUG-undeclared-tool | `missing-tools-declaration` | fixed — upstream, not via our PR |  |
| 15 | ``agents/personas/test-automator.md` missing `tools` declaration` | — | BUG-undeclared-tool | `missing-tools-declaration` | fixed — upstream, not via our PR |  |
| 16 | ``agents/personas/cloud-architect.md` missing `tools` declaration (but has hooks)` | — | BUG-undeclared-tool | `missing-tools-declaration` | fixed — upstream, not via our PR |  |
| 17 | ``agents/personas/mermaid-expert.md` uses haiku with no tools` | — | UNCLASSIFIED | `agents-personas-mermaid-expert-md-uses-h` | fixed — upstream, not via our PR |  |
| 18 | ``agents/personas/context-manager.md` missing `when_to_use` / `avoid_if` / examples` | — | UNCLASSIFIED | `agents-personas-context-manager-md-missi` | fixed — upstream, not via our PR |  |
| 19 | ``agents/personas/ai-engineer.md` missing `when_to_use` / `avoid_if` / examples` | — | UNCLASSIFIED | `agents-personas-ai-engineer-md-missing-w` | fixed — upstream, not via our PR |  |
| 20 | ``agents/personas/academic-writer.md`, `agents/personas/graphql-architect.md` missing `tools`` | — | UNCLASSIFIED | `agents-personas-academic-writer-md-agent` | fixed — upstream, not via our PR |  |
| 21 | ``config/providers/` and `config/workflows/` files lack NLPM frontmatter schema` | — | UNCLASSIFIED | `config-providers-and-config-workflows-fi` | fixed — upstream, not via our PR |  |
| 22 | `Personas `business-analyst.md` and `exec-communicator.md` no `tools` declared vs `finance-analyst.md` which does` | — | UNCLASSIFIED | `personas-business-analyst-md-and-exec-co` | fixed — upstream, not via our PR |  |
| 23 | ``skill-extract/SKILL.md` skeleton implementation not gated by capability check` | — | UNCLASSIFIED | `skill-extract-skill-md-skeleton-implemen` | fixed — upstream, not via our PR |  |

## Findings introduced since audit

These findings appear in the re-audit but were not in the original audit. They may be true regressions (new commits introduced them) or artifacts of scoring drift.

| # | File | Line | Rule | Pattern | Description |
|---|------|------|------|---------|-------------|
| 1 | `.github/agents/code-reviewer.agent.md` | — | UNCLASSIFIED | `` | All 10 GitHub Actions agent files declare tools using lowercase names not recognized by Claude Code: 'read', 'search', 'execute', 'edit'. Claude Code tool resolution is case-sensitive. Valid names are Read, Glob, Grep, Bash, Edit, Write. These agents will instantiate with no functional tools, making all tool-dependent workflows non-executable. |
| 2 | `agents/personas/openclaw-admin.md` | — | UNCLASSIFIED | `` | The openclaw-admin persona body contains 'curl -fsSL https://openclaw.ai/install.sh | bash'. The wrong-domain issue (gogcli.sh) from the prior audit was fixed. The curl-pipe-sh execution pattern remains. Claude Code renders this as an agent prompt body; the agent may follow the installation instruction and execute arbitrary remote code without content inspection. |
| 3 | `skills/skill-claw/SKILL.md` | — | UNCLASSIFIED | `` | Three instances of 'curl -fsSL https://openclaw.ai/install.sh | bash' appear in the installation table and code block. This skill is invokable via any command that loads it. When Claude executes the installation workflow, it will run this pattern directly on the user's machine without content verification or user inspection gate. |
| 4 | `agents/personas/product-writer.md` | — | UNCLASSIFIED | `` | The longest persona file in the repository (394 lines) has neither an 'examples:' array in frontmatter (-15 per R09) nor an Output Format section in the body (-10 per R12). This is the outlier in a persona category where 20/32 files have YAML examples. Score: 65/100. |
| 5 | `agents/personas/` | — | UNCLASSIFIED | `` | 16 persona files have no 'tools:' field in frontmatter. Claude Code defaults to empty tool lists for subagents without explicit declarations, silently preventing tool-dependent workflows. Affected: docs-architect.md, business-analyst.md, product-writer.md, graphql-architect.md, exec-communicator.md, academic-writer.md, ai-engineer.md, mermaid-expert.md, incident-responder.md, deployment-engineer.md, cloud-architect.md, context-manager.md, devops-troubleshooter.md, ux-researcher.md, typescript-pro.md, test-automator.md |
| 6 | `.claude/commands/` | — | UNCLASSIFIED | `` | Only 5 commands declare allowed-tools: setup.md, retro.md, costs.md, history.md, doctor.md. The prior audit found 2/49; 3 were added. 43/48 remain uncovered. Complex orchestration commands like embrace.md, factory.md, parallel.md, multi.md have unrestricted tool access despite narrow intended scope. |
| 7 | `.claude/commands/` | — | UNCLASSIFIED | `` | Only 6 commands define an output format section: costs.md, discover.md, embrace.md, meta-prompt.md, extract.md, prd-score.md. The remaining 42 commands including plan.md (563L), brainstorm.md (249L), multi.md (231L) have no output template. This creates unpredictable response formats when commands are used programmatically or chained. |
| 8 | `agents/personas/` | — | UNCLASSIFIED | `` | 24 persona files contain vague quantifiers: 'appropriate', 'relevant', 'various', 'several', 'reasonable'. Most files absorb -2 to -6. No file reaches the -20 cap. Worst affected: devops-troubleshooter.md, incident-responder.md, legal-compliance-advisor.md, research-synthesizer.md. Clean files: backend-architect, tdd-orchestrator, code-reviewer, debugger, security-auditor, frontend-developer, database-architect, python-pro. |
| 9 | `agents/droids/` | — | UNCLASSIFIED | `` | The BUG-002 fix added tools to all droids, but used 'All tools' for every droid regardless of operational scope. The Output Contract sections in these droids suggest some should be read-only (e.g. octo-code-reviewer should not write files). Declaring 'All tools' violates R11 least-privilege and creates unnecessary risk surface. |
| 10 | `.github/agents/` | — | UNCLASSIFIED | `` | No GitHub Actions agent file contains an <example> block in the description field or an examples: array in frontmatter. Combined with no model declaration (-5 each) and no output format (-10 each), each agent scores ~65/100. These agents are used in CI/CD workflows where behavioral grounding is critical for consistent output. |
| 11 | `agents/droids/` | — | UNCLASSIFIED | `` | All 10 droid agents now declare 'tools: ["All tools"]'. This resolves the original BUG-002 where droids had no tools field and could only perform text generation. Category average improved from 78 to 85. |
| 12 | `agents/personas/openclaw-admin.md` | — | UNCLASSIFIED | `` | The 'gogcli.sh' domain in the installation curl command was corrected to 'openclaw.ai', matching the rest of the codebase. The broader curl-pipe-sh security concern (SEC-001) remains open as a separate finding. |

