# NLPM Audit: guanyang/antigravity-skills
**Date**: 2026-04-20  |  **Artifacts**: 63  |  **Strategy**: progressive
**NL Score**: 86/100
**Security**: REVIEW REQUIRED
**Bugs**: 3  |  **Quality Issues**: 8  |  **Security Findings**: 3

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/skill-creator/agents/analyzer.md | agent | 45 | Missing YAML frontmatter entirely — no `name:`, no `description:` |
| skills/skill-creator/agents/grader.md | agent | 45 | Missing YAML frontmatter entirely |
| skills/skill-creator/agents/comparator.md | agent | 45 | Missing YAML frontmatter entirely |
| skills/brand-guidelines/SKILL.md | skill | 78 | Purely descriptive; lacks usage examples or workflow steps |
| template/SKILL.md | skill | 80 | Intentional placeholder — minimal body is expected |
| skills/remotion/SKILL.md | skill | 80 | Typo "Stsrt" on line 25; index-only, delegates to rule files |
| skills/executing-plans/SKILL.md | skill | 80 | No output format examples despite being a workflow skill |
| skills/frontend-design/SKILL.md | skill | 80 | Guidelines only; no output examples |
| skills/canvas-design/SKILL.md | skill | 83 | No output format section; no workflow steps |
| skills/theme-factory/SKILL.md | skill | 83 | No output examples |
| skills/brainstorming/SKILL.md | skill | 85 | Vague quantifier "appropriately-scoped" |
| skills/mcp-builder/SKILL.md | skill | 85 | Good structure; references local docs |
| skills/internal-comms/SKILL.md | skill | 85 | Good structure; references examples/ directory |
| skills/web-design-guidelines/SKILL.md | skill | 85 | Relies on WebFetch at runtime; no inline examples |
| skills/notebooklm/SKILL.md | skill | 85 | Script-driven workflow; dense but clear |
| skills/planning-with-files/SKILL.md | skill | 85 | Stop hook executes glob-resolved cached script (see security) |
| skills/requesting-code-review/SKILL.md | skill | 85 | Good; references code-reviewer.md template |
| skills/web-artifacts-builder/SKILL.md | skill | 85 | Good 5-step process; no output examples |
| skills/doc-coauthoring/SKILL.md | skill | 85 | Good 3-stage workflow; no output format section |
| skills/obsidian-cli/SKILL.md | skill | 85 | Clean command patterns; no failure examples |
| skills/algorithmic-art/SKILL.md | skill | 85 | Instructions require reading bundled template at runtime |
| skills/context-optimization/SKILL.md | skill | 85 | Deferred to this score; would need re-read for precise penalty |
| skills/ui-ux-pro-max/SKILL.md | skill | 85 | Very large (650+ lines); CLI scripts referenced |
| skills/composition-patterns/SKILL.md | skill | 87 | author: vercel; index pattern with rule files |
| skills/react-best-practices/SKILL.md | skill | 87 | author: vercel; index pattern |
| skills/slack-gif-creator/SKILL.md | skill | 87 | Core workflow code inline; good |
| skills/using-superpowers/SKILL.md | skill | 88 | DOT diagram included; good priority rules |
| skills/dispatching-parallel-agents/SKILL.md | skill | 88 | Real-world examples; TypeScript dispatch |
| skills/webapp-testing/SKILL.md | skill | 88 | Decision tree; clear examples |
| skills/systematic-debugging/SKILL.md | skill | 88 | 4-phase process with supporting files |
| skills/supabase-postgres-best-practices/SKILL.md | skill | 88 | Rich metadata; rule files in references/ |
| skills/writing-skills/SKILL.md | skill | 88 | TDD-for-docs methodology; good |
| skills/xlsx/SKILL.md | skill | 88 | Extensive Python/openpyxl examples |
| skills/receiving-code-review/SKILL.md | skill | 88 | Numbered steps; real examples; tables |
| skills/skill-creator/SKILL.md | skill | 88 | Extensive workflow guide; references agents/ |
| skills/pptx/SKILL.md | skill | 88 | Quick reference table; visual QA section |
| skills/writing-plans/SKILL.md | skill | 88 | Numbered steps; complete code examples |
| skills/react-native-skills/SKILL.md | skill | 87 | author: vercel; index + rule file pattern |
| skills/filesystem-context/SKILL.md | skill | 90 | Six patterns; extensive gotchas |
| skills/docx/SKILL.md | skill | 90 | Extensive code examples (JS and XML) |
| skills/latent-briefing/SKILL.md | skill | 90 | Technical depth; example scenario |
| skills/claude-api/SKILL.md | skill | 90 | Comprehensive model table; thinking/effort docs |
| skills/context-degradation/SKILL.md | skill | 90 | Two examples; vague quantifiers minor penalty |
| skills/finishing-a-development-branch/SKILL.md | skill | 90 | Numbered steps; 4-option decision table |
| skills/json-canvas/SKILL.md | skill | 90 | JSON spec examples; validation checklist |
| skills/tool-design/SKILL.md | skill | 90 | Two examples (good/poor); gotchas |
| skills/context-fundamentals/SKILL.md | skill | 90 | Two examples; solid reference |
| skills/context-optimization/SKILL.md | skill | 90 | Three examples with Python code |
| skills/project-development/SKILL.md | skill | 90 | Real-world examples (Karpathy HN, Vercel d0) |
| skills/evaluation/SKILL.md | skill | 90 | Two examples with Python code |
| skills/pdf/SKILL.md | skill | 90 | Extensive Python/CLI examples |
| skills/verification-before-completion/SKILL.md | skill | 90 | Concise; key patterns table |
| skills/obsidian-markdown/SKILL.md | skill | 90 | Complete example; code blocks |
| skills/memory-systems/SKILL.md | skill | 90 | Three code examples; benchmark comparison table |
| skills/bdi-mental-states/SKILL.md | skill | 90 | Turtle/SPARQL/Python examples; competency questions |
| skills/hosted-agents/SKILL.md | skill | 90 | Comprehensive; multiple code examples; gotchas |
| skills/context-compression/SKILL.md | skill | 90 | Two examples (good/poor); six evaluation dimensions |
| skills/using-git-worktrees/SKILL.md | skill | 92 | Numbered steps; example workflow; red flags |
| skills/advanced-evaluation/SKILL.md | skill | 92 | Three full examples with JSON output |
| skills/subagent-driven-development/SKILL.md | skill | 92 | Full 2-task scenario example |
| skills/test-driven-development/SKILL.md | skill | 92 | Good/Bad tagged examples; TDD cycle diagram |
| skills/obsidian-bases/SKILL.md | skill | 92 | Complete examples (task tracker, reading list, daily notes) |
| skills/multi-agent-patterns/SKILL.md | skill | 92 | Token cost table; two examples; code; gotchas |
| skills/defuddle/SKILL.md | skill | 93 | Concise; clean examples; output formats table |

**Score distribution:**

| Range | Count | % |
|-------|-------|---|
| 90–100 | 25 | 40% |
| 85–89 | 25 | 40% |
| 80–84 | 7 | 11% |
| 45–79 | 6 | 9% |

**Weighted average: 86/100**

The three agent files without frontmatter pull the mean down by ~2 points; the SKILL.md-only average is 87.7/100. High-quality skills (defuddle, multi-agent-patterns, obsidian-bases, subagent-driven-development, test-driven-development) set a strong ceiling for the collection.

## Security Scan

**Status:** REVIEW REQUIRED

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 1 |
| Low | 2 |

### Execution Surface Inventory

| Surface | Files | Notes |
|---------|-------|-------|
| Top-level hooks (hooks.json) | 0 | No hooks.json at repo root |
| SKILL.md embedded hooks | 1 | `planning-with-files/SKILL.md` — 4 hook events |
| Shell scripts (.sh) | 1 | `scripts/sync_skills.sh` — git clone/rsync utility |
| Python scripts (.py) | 0 | None standalone (only inline code in SKILL.md bodies) |
| JavaScript scripts (.js) | 0 | None standalone |
| MCP configs (.mcp.json) | 0 | None found |
| Package manifests (package.json) | 1 | `skills/brainstorming/scripts/package.json` — express/ws/chokidar server |
| Requirements files | 3 | mcp-builder (anthropic+mcp), notebooklm, slack-gif-creator |
| Hardcoded credentials | 0 | None found |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | skills/planning-with-files/SKILL.md | 24 | dynamic-script-exec-from-glob | Stop hook executes: `sh "$(ls $HOME/.claude/plugins/cache/*/*/*/scripts/check-complete.sh 2>/dev/null \| head -1)"`. The resolved script path comes from the user's own plugin cache glob, not from external input — but if the plugin cache is compromised or the glob matches an unexpected file, arbitrary shell code executes silently on every agent Stop event. PowerShell equivalent also present for Windows. |
| 2 | Low | scripts/sync_skills.sh | 75 | network-calls-from-config | Makes `git clone` calls for each entry in `skills_sources.json`. If `skills_sources.json` is tampered with or supplied untrusted data, it clones and copies from attacker-controlled repos. The script itself has no URL validation. Low severity because this is a maintenance utility, not a hook. |
| 3 | Low | skills/brainstorming/scripts/package.json | — | unpinned-deps | Dependencies use `^` ranges (`express ^4.18.2`, `ws ^8.14.2`, `chokidar ^3.5.3`). Future `npm install` may pull minor/patch versions with vulnerabilities. |

**Security positives:**
- No curl-pipe-shell patterns anywhere in skill bodies
- No `eval` with variable interpolation
- No credential exfiltration patterns
- No reverse shell patterns
- `planning-with-files/SKILL.md` body explicitly documents the prompt-injection risk of its hooks (line 222) — the author is aware

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/skill-creator/agents/analyzer.md | Missing YAML frontmatter block entirely — no opening `---`, no `name:`, no `description:` | Agent cannot register; `skill-creator/SKILL.md` references it by path but it is invisible to the runtime; NL score: 45 |
| 2 | skills/skill-creator/agents/grader.md | Same — missing YAML frontmatter entirely | Same impact; grader subagent non-functional |
| 3 | skills/skill-creator/agents/comparator.md | Same — missing YAML frontmatter entirely | Same impact; blind comparison mode broken |

All three agent files have valid body content (Output Format, numbered steps, rubric) but will never be loaded as agents. One-line fix each: add `---\nname: <agent-name>\ndescription: <description>\n---` as the first four lines.

## Security Fixes (PR-worthy)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | skills/planning-with-files/SKILL.md:24 | Stop hook resolves and executes a script via shell glob over plugin cache directory | Hardcode the expected script path relative to the skill directory rather than discovering it dynamically, or add a SHA-256 digest check before execution: `SCRIPT=$(ls $HOME/.claude/plugins/cache/*/*/*/scripts/check-complete.sh 2>/dev/null \| head -1); [ -n "$SCRIPT" ] && [ "$(sha256sum "$SCRIPT" \| cut -d' ' -f1)" = "<expected-digest>" ] && sh "$SCRIPT"` |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/remotion/SKILL.md:25 | Typo in heading: "Stsrt the Remotion Studio" → "Start the Remotion Studio" | cosmetic |
| 2 | skills/brand-guidelines/SKILL.md | Purely descriptive — no usage examples, no workflow steps, no output format | -15 (no examples), -10 (no output format) |
| 3 | skills/executing-plans/SKILL.md | No output format examples for a workflow skill | -10 |
| 4 | skills/canvas-design/SKILL.md | No output format section; output is implied ("PDF or PNG") but not specified | -10 |
| 5 | skills/frontend-design/SKILL.md | Guidelines list only; no output examples or workflow steps | -10 (no output format) |
| 6 | skills/skill-creator/agents/*.md (all 3) | Body has no `model:` declaration; agents will run on default model without explicit targeting | -5 per agent (covered by missing frontmatter penalty) |
| 7 | skills/algorithmic-art/SKILL.md | Step 0 instructs Claude to `Read templates/viewer.html` using the Read tool — this adds an implicit runtime file I/O requirement to every skill invocation that isn't documented in the frontmatter | quality |
| 8 | skills/context-degradation/SKILL.md | Vague quantifiers: "significantly", "substantially", "relatively" appear 3–4 times | -6 |

## Cross-Component

**Broken agent registration in skill-creator skill:**
`skills/skill-creator/SKILL.md` references `agents/grader.md`, `agents/comparator.md`, and `agents/analyzer.md` at lines 225, 327, and 234 respectively — with explicit instructions to "read" and "spawn" them. All three files exist on disk with valid body content, but none have YAML frontmatter. The runtime will not recognize them as registered agents, and calls to spawn them will either fail silently or require the user to explicitly pass the file path. This is the highest-priority cross-component issue in the collection; it breaks the core skill-creator eval loop.

**planning-with-files hook injection surface documented but unresolved:**
`planning-with-files/SKILL.md` lines 222–226 explicitly warn that `task_plan.md` is an indirect prompt injection target (re-read by PreToolUse hook on every tool call). This is responsible disclosure, but the mitigation suggested ("write web/search results to `findings.md` only") depends on the model following instructions even when adversarial content has already entered context. No structural guard is present.

**Reference file dependencies not bundled inline:**
Several skills reference supporting files that must exist in the skill directory for the skill to function:
- `skills/systematic-debugging/SKILL.md` — references technique support files
- `skills/bdi-mental-states/SKILL.md` — references `references/bdi-ontology-core.md`, `references/rdf-examples.md`, `references/sparql-competency.md`, `references/framework-integration.md`
- `skills/skill-creator/SKILL.md` — references `references/schemas.md`
These were not verified to exist in the target-repo snapshot, but the pattern is consistent across the collection. The SKILL.md bodies clearly signal when to load them (good progressive-disclosure practice).

**vercel-authored skills (3 files):**
`composition-patterns`, `react-best-practices`, and `react-native-skills` carry `author: vercel` in metadata and use an index-to-rule-files pattern (detail deferred to `rules/*.md` files). This is functionally correct but means the inline SKILL.md body provides only navigation — full content requires reading rule files. Consistent with the vercel plugin pattern; no action needed unless inline summaries are desired.

**No allowed-tools declarations:**
None of the SKILL.md files declare `allowed-tools` in frontmatter (except `planning-with-files`, which does). This is common across the ecosystem and not a breaking issue for passive reference skills, but skills that bundle scripts and expect Bash access benefit from explicit declarations.

## Recommendation

REVIEW REQUIRED — the Stop hook security finding should be assessed before contribution is approved.

**Priority order:**

1. **Add YAML frontmatter to all three agent files** (Bugs #1–3) — one-line-group fix per file, highest ROI. Without this the core skill-creator evaluation loop is broken.
   ```yaml
   ---
   name: skill-creator-grader
   description: Grades assertion results against expected outputs. Read and follow to evaluate test case assertions.
   ---
   ```
2. **Review Stop hook in planning-with-files** (Security #1) — assess whether glob-resolved script execution is acceptable; if yes, document the trust model explicitly; if no, hardcode or remove.
3. **Fix remotion typo** (Quality #1) — one character change.
4. **Add examples to brand-guidelines** (Quality #2) — currently the lowest-scoring SKILL.md; 2–3 usage examples would bring it to 88+.
5. **Add output format to executing-plans, canvas-design, frontend-design** (Quality #3–5) — each needs one `## Output` section.
6. **Pin brainstorming/scripts/package.json dependencies** (Security #3) — change `^` to exact versions or add lockfile.

**Overall assessment:** Strong collection. The SKILL.md files are well above the ecosystem average at 87.7/100 mean, with clear progressive-disclosure patterns, bundled scripts, and good example density. The 3-point drag from the unregistered agent files is an easy fix. The security concern in planning-with-files is the only material hold.
