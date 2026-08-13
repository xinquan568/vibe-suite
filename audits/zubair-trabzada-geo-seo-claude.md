# NLPM Audit: zubair-trabzada/geo-seo-claude
**Date**: 2026-04-06  |  **Artifacts**: 20  |  **Strategy**: single
**NL Score**: 88/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 15  |  **Security Findings**: 5

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| agents/geo-content.md | agent | 74 | No model declared; no examples |
| agents/geo-technical.md | agent | 74 | No model declared; no examples |
| agents/geo-ai-visibility.md | agent | 76 | No model declared; no examples |
| agents/geo-platform-analysis.md | agent | 76 | No model declared; no examples |
| agents/geo-schema.md | agent | 76 | No model declared; no examples |
| skills/geo-brand-mentions/SKILL.md | skill | 88 | High vague-quantifier density (6+) |
| skills/geo-report/SKILL.md | skill | 90 | Broken skill reference + vague density |
| skills/geo-content/SKILL.md | skill | 90 | Vague quantifiers (5) |
| skills/geo-audit/SKILL.md | skill | 92 | Vague quantifiers (4) |
| skills/geo-crawlers/SKILL.md | skill | 92 | Vague quantifiers (4) |
| skills/geo-llmstxt/SKILL.md | skill | 92 | Vague quantifiers (4) |
| skills/geo-schema/SKILL.md | skill | 90 | Vague quantifiers (5) |
| skills/geo-technical/SKILL.md | skill | 94 | Vague quantifiers (3) |
| skills/geo-platform-optimizer/SKILL.md | skill | 94 | Vague quantifiers (3) |
| skills/geo-proposal/SKILL.md | skill | 96 | Minor vague language |
| skills/geo-citability/SKILL.md | skill | 96 | Minor vague language |
| skills/geo-compare/SKILL.md | skill | 96 | Minor vague language |
| skills/geo-report-pdf/SKILL.md | skill | 96 | Minor vague language |
| geo/SKILL.md | skill | 94 | Minor vague language |
| skills/geo-prospect/SKILL.md | skill | 98 | Negligible |

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 3 |
| Low | 2 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (Python) | scripts/brand_scanner.py, scripts/citability_scorer.py, scripts/crm_dashboard.py, scripts/fetch_page.py, scripts/generate_pdf_report.py, scripts/llmstxt_generator.py, scripts/webapp/app.py |
| MCP configs | 0 |
| Package manifests | requirements.txt |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | scripts/webapp/app.py | 214 | Flask debug=True | `app.run(debug=True, port=5050)` — Werkzeug interactive debugger enabled; if port is exposed, allows arbitrary Python code execution via browser PIN bypass or direct access |
| 2 | Medium | scripts/fetch_page.py | 61 | Network request to user-supplied URL | `requests.get(url, ...)` — no URL scheme/host validation; if wrapped in an API or automation pipeline, enables SSRF against internal network resources |
| 3 | Medium | scripts/llmstxt_generator.py | 247 | Network crawl without origin validation | Discovers URLs from crawled pages and fetches each one without validating that they belong to the original domain; could be steered to SSRF targets via redirect chains on a malicious site |
| 4 | Low | requirements.txt | 10 | Dependency spans major version boundary | `rich>=13.0.0,<15.0.0` permits installation of rich 14.x (a different major version); breaking API changes across major boundaries could cause unexpected runtime errors |
| 5 | Low | scripts/generate_pdf_report.py | 919-921 | Stdin read without size limit | `json.loads(sys.stdin.read())` — no maximum read size; a very large JSON payload piped to this script could exhaust memory on resource-constrained systems |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/geo-report/SKILL.md:23 | References skill as `geo-llms-txt` (hyphenated) but the installed skill name is `geo-llmstxt` (no internal hyphen) | Workflow step 1 of the report skill will fail to load the llms.txt assessment when constructing the client report; silently omits llms.txt data from output |

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/webapp/app.py:214 | Flask `debug=True` in production entrypoint | Change to `app.run(debug=False, port=5050)` or better: read from env var `os.environ.get("FLASK_DEBUG", "false").lower() == "true"` |
| 2 | scripts/fetch_page.py:61 | No URL scheme validation before `requests.get()` | Add `if urlparse(url).scheme not in ("http", "https"): raise ValueError(...)` before the request call; reject `file://`, `ftp://`, etc. |
| 3 | scripts/llmstxt_generator.py:247 | Crawled sub-URLs fetched without domain check | Validate that `page["url"]` shares the same netloc as `parsed.netloc` before fetching; skip cross-origin entries |
| 4 | requirements.txt:10 | `rich` spans major version boundary | Pin to `rich>=13.0.0,<14.0.0` to stay within a single stable major version |
| 5 | scripts/generate_pdf_report.py:919-921 | Stdin read without size guard | Wrap in a streaming reader with a max-bytes cap, e.g. `sys.stdin.buffer.read(10_000_000)`, and raise an error if the limit is exceeded |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | agents/geo-ai-visibility.md | `model` not declared in frontmatter | -5 |
| 2 | agents/geo-content.md | `model` not declared in frontmatter | -5 |
| 3 | agents/geo-platform-analysis.md | `model` not declared in frontmatter | -5 |
| 4 | agents/geo-schema.md | `model` not declared in frontmatter | -5 |
| 5 | agents/geo-technical.md | `model` not declared in frontmatter | -5 |
| 6 | agents/geo-ai-visibility.md | Zero example blocks (inputs + expected behavior) | -15 |
| 7 | agents/geo-content.md | Zero example blocks | -15 |
| 8 | agents/geo-platform-analysis.md | Zero example blocks | -15 |
| 9 | agents/geo-schema.md | Zero example blocks | -15 |
| 10 | agents/geo-technical.md | Zero example blocks | -15 |
| 11 | skills/geo-brand-mentions/SKILL.md | Vague quantifiers: "relevant" ×4, "appropriate" ×2 throughout analysis procedure | -12 |
| 12 | skills/geo-content/SKILL.md | Vague quantifiers: "appropriate" ×2, "relevant" ×3 | -10 |
| 13 | skills/geo-schema/SKILL.md | Vague quantifiers: "relevant" ×3, "appropriate" ×2 | -10 |
| 14 | skills/geo-audit/SKILL.md | Vague quantifiers: "relevant" ×2, "appropriate", "comprehensive" | -8 |
| 15 | skills/geo-report/SKILL.md | Vague quantifiers: "appropriate" ×2, "relevant" ×3 (separate from the broken-ref bug) | -10 |

## Cross-Component

**Broken reference:**
`skills/geo-report/SKILL.md` line 23 lists `geo-llms-txt` as an optional input skill. The actual installed skill directory is `skills/geo-llmstxt/` and its `name` field is `geo-llmstxt`. The hyphenated variant does not exist and will silently produce no output when the report skill tries to incorporate llms.txt findings.

**Consistent model tier omission:**
All five agent definitions (`geo-ai-visibility`, `geo-content`, `geo-platform-analysis`, `geo-schema`, `geo-technical`) omit the `model` frontmatter field. The orchestrator in `geo/SKILL.md` and `skills/geo-audit/SKILL.md` states these agents run in parallel as subagents, so the routing engine will pick model by default. Adding `model: claude-sonnet-4-6` (or haiku for lighter agents) aligns each agent's cost/capability expectations with the plugin documentation.

**Unused `version`/`author`/`tags` in agents:**
Skills carry optional `version`, `author`, and `tags` fields (e.g., `geo-content/SKILL.md`, `geo-platform-optimizer/SKILL.md`), but the five agent files have none of these, making them harder to track in changelogs. Not a functional issue, but reduces metadata consistency.

**External script dependency declared in skills but not agents:**
`skills/geo-schema/SKILL.md` and the `agents/geo-schema.md` agent both reference `~/.claude/skills/geo/scripts/fetch_page.py`. The agent relies on the script existing at install-time but does not state this prerequisite in its frontmatter or a `## Prerequisites` section. If the plugin is partially installed, the agent will silently fail the schema detection step.

**No orphaned agents or skills detected.** Every agent is referenced from `geo/SKILL.md` or `skills/geo-audit/SKILL.md`, and every skill listed in `geo/SKILL.md`'s sub-skills table has a corresponding directory.

## Recommendation

CLEAR — submit PRs for all bugs and medium/low security fixes.

**Priority order:**
1. **Bug fix (immediate):** Rename `geo-llms-txt` → `geo-llmstxt` in `skills/geo-report/SKILL.md:23`. One-line change, zero risk.
2. **Security fix (medium):** Change `debug=True` → `debug=False` in `scripts/webapp/app.py:214`. Trivial change, prevents debugger exposure.
3. **Security fix (medium):** Add URL scheme validation to `scripts/fetch_page.py` and domain-origin check to `scripts/llmstxt_generator.py`.
4. **Quality (batch PR):** Add `model: claude-sonnet-4-6` to all five agent frontmatter blocks and add at least one example block per agent. These are the largest quality-score depressors and straightforward to add.
5. **Security fix (low):** Pin `rich` to `<14.0.0` in `requirements.txt` and add stdin size guard to `generate_pdf_report.py`.
