# NLPM Audit: RKiding/Awesome-finance-skills
**Date**: 2026-04-06  |  **Artifacts**: 10  |  **Strategy**: single
**NL Score**: 92/100
**Security**: CLEAR
**Bugs**: 1  |  **Quality Issues**: 17  |  **Security Findings**: 6

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/alphaear-predictor/SKILL.md | skill | 88 | Missing output format; "subjectively adjust" vague |
| skills/alphaear-signal-tracker/SKILL.md | skill | 88 | Missing output format; "necessary data" vague |
| skills/alphaear-deepear-lite/SKILL.md | skill | 90 | Missing output format |
| skills/alphaear-logic-visualizer/SKILL.md | skill | 90 | Missing output format |
| skills/alphaear-news/SKILL.md | skill | 90 | Missing output format |
| skills/alphaear-reporter/SKILL.md | skill | 90 | Missing output format |
| skills/alphaear-search/SKILL.md | skill | 95 | Partially missing output format |
| skills/skill-creator/SKILL.md | skill | 96 | "Appropriate", "simple" vague quantifiers |
| skills/alphaear-sentiment/SKILL.md | skill | 98 | "insufficient" vague quantifier |
| skills/alphaear-stock/SKILL.md | skill | 100 | None |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 5 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Python scripts (.py) | ~139 across 9 skills |
| Shell scripts (.sh) | 0 |
| MCP configs | 0 |
| Package manifests (requirements.txt / package.json) | 0 found at repo root |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | skills/alphaear-predictor/scripts/utils/predictor/evaluation.py | 39 | unsafe-pickle-load | `torch.load` called without `weights_only=True`; loads model checkpoint via pickle, allowing arbitrary code execution if a malicious .pt file is placed in the models directory |
| 2 | Medium | skills/alphaear-signal-tracker/scripts/utils/predictor/evaluation.py | 39 | unsafe-pickle-load | Same pattern as #1 — identical file copied into signal-tracker skill |
| 3 | Medium | skills/alphaear-reporter/scripts/utils/predictor/evaluation.py | 39 | unsafe-pickle-load | Same pattern as #1 — identical file copied into reporter skill |
| 4 | Medium | skills/alphaear-predictor/scripts/kronos_predictor.py | 83 | unsafe-pickle-load | Fallback path drops `weights_only=True` when it raises `TypeError/RuntimeError`; the safe guard is silently bypassed on incompatible torch versions |
| 5 | Medium | skills/alphaear-news/scripts/news_tools.py | 61 | unvetted-network-host | Outbound HTTP request to `https://newsnow.busiyi.world` — a third-party Chinese aggregation service with no pinned hostname or certificate validation; compromise of this host can inject arbitrary content into the agent's context |
| 6 | Low | skills/alphaear-predictor/scripts/utils/json_utils.py | 174 | untrusted-eval-input | `ast.literal_eval` applied to JSON-like strings extracted from external API responses; safer than `eval` but still parses untrusted input — could raise exceptions or process unexpected Python literals from a compromised upstream |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/alphaear-predictor/SKILL.md | Import path `from scripts.utils.kronos_predictor import KronosPredictorUtility` is wrong; the file lives at `scripts/kronos_predictor.py` (not `scripts/utils/`), so the example code raises `ModuleNotFoundError` | Any user following the code example verbatim cannot import `KronosPredictorUtility` |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | skills/alphaear-predictor/scripts/utils/predictor/evaluation.py | `torch.load` without `weights_only=True` | Change line 39 to `torch.load(path, map_location=self.device, weights_only=True)`; add a comment noting this requires PyTorch ≥ 1.13 |
| 2 | skills/alphaear-signal-tracker/scripts/utils/predictor/evaluation.py | Same as #1 | Same fix |
| 3 | skills/alphaear-reporter/scripts/utils/predictor/evaluation.py | Same as #1 | Same fix |
| 4 | skills/alphaear-predictor/scripts/kronos_predictor.py | Fallback silently drops `weights_only=True` | Remove the broad `except (TypeError, RuntimeError, AttributeError)` fallback or narrow it to only `TypeError` for old torch versions, keeping `weights_only=True` on the fallback where possible |
| 5 | skills/alphaear-news/scripts/news_tools.py | Requests to `newsnow.busiyi.world` without hostname validation | Document the third-party dependency in the skill README; add `requests.exceptions.SSLError` handling so a MitM certificate does not silently fall back |
| 6 | skills/alphaear-predictor/scripts/utils/json_utils.py | `ast.literal_eval` on API-sourced strings | Wrap in `try/except (ValueError, SyntaxError, MemoryError)` only (already done) — ensure the caller never passes content larger than a configurable size limit to prevent MemoryError DoS |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/alphaear-deepear-lite/SKILL.md | Missing output format: `fetch_latest_signals` returns a "formatted report" but no structure (fields, types, section headings) is defined | -10 |
| 2 | skills/alphaear-logic-visualizer/SKILL.md | Missing output format: `render_drawio_to_html` produces "a viewable HTML file" but the structure of the XML/HTML content is not specified | -10 |
| 3 | skills/alphaear-logic-visualizer/SKILL.md | Duplicate section heading "### 1. Generate Draw.io Diagrams" appears twice in sequence (lines 14 and 17) | 0 (informational) |
| 4 | skills/alphaear-news/SKILL.md | Missing output format: `get_market_summary` returns a "formatted report" without specifying fields or Markdown structure | -10 |
| 5 | skills/alphaear-predictor/SKILL.md | Missing output format: `get_base_forecast` returns `List[KLinePoint]` but `KLinePoint` fields are not defined in the SKILL.md body | -10 |
| 6 | skills/alphaear-predictor/SKILL.md | Vague quantifier: "subjectively adjust the numbers based on latest news/logic" — "subjectively" gives no criteria for how to adjust (R01) | -2 |
| 7 | skills/alphaear-predictor/SKILL.md | Duplicate section heading "### 1. Forecast Market Trends" appears twice (lines 14 and 16) | 0 (informational) |
| 8 | skills/alphaear-reporter/SKILL.md | Missing output format: generates "professional financial reports" but no Markdown template or section structure is defined | -10 |
| 9 | skills/alphaear-reporter/SKILL.md | Duplicate top-level heading "## Capabilities" appears twice (lines 13 and 15) | 0 (informational) |
| 10 | skills/alphaear-search/SKILL.md | Partially missing output format: `search()` returns "JSON string or List[Dict]" (defined) but `aggregate_search()` has no return type | -5 |
| 11 | skills/alphaear-sentiment/SKILL.md | Vague quantifier: "if the local tool is insufficient" — no threshold defined for what counts as insufficient accuracy (R01) | -2 |
| 12 | skills/alphaear-sentiment/SKILL.md | Duplicate top-level heading "## Capabilities" appears twice (lines 13 and 15) | 0 (informational) |
| 13 | skills/alphaear-signal-tracker/SKILL.md | Missing output format: result described only as "Updated Signal" with no schema for the updated state | -10 |
| 14 | skills/alphaear-signal-tracker/SKILL.md | Vague quantifier: "gather the necessary data" — "necessary" is undefined without a list of required data points (R01) | -2 |
| 15 | skills/alphaear-signal-tracker/SKILL.md | Duplicate section heading "### 1. Track Signal Evolution" appears twice (lines 14 and 17) | 0 (informational) |
| 16 | skills/skill-creator/SKILL.md | Vague quantifier: "Set Appropriate Degrees of Freedom" — "Appropriate" gives no measurable criteria for degree of freedom selection (R01) | -2 |
| 17 | skills/skill-creator/SKILL.md | Vague quantifier: "For simple edits, modify the XML directly" — "simple" is undefined (R01) | -2 |

## Cross-Component
- **Undeclared inter-skill dependency**: `alphaear-signal-tracker/SKILL.md` instructs the agent to "Use `alphaear-search` and `alphaear-stock` skills to gather the necessary data" but lists neither as a prerequisite in its frontmatter or a Dependencies section. If either skill is absent the workflow silently degrades.
- **Three-way code duplication**: `evaluation.py`, `training.py`, `json_utils.py`, `database_manager.py`, and supporting utilities are physically copied into `alphaear-predictor`, `alphaear-signal-tracker`, and `alphaear-reporter` rather than shared. The torch.load security fix (Finding #1) must be applied to three independent copies.
- **No broken references** beyond the `KronosPredictorUtility` import path already listed in Bugs. Referenced scripts (`deepear_lite.py`, `visualizer.py`, `news_tools.py`, `fin_agent.py`, `kronos_predictor.py`) all exist at the declared locations.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

Priority order: (1) Fix the `KronosPredictorUtility` import path — it breaks the advertised code example. (2) Add `weights_only=True` to the three `evaluation.py` copies and narrow the fallback in `kronos_predictor.py`. (3) Address vague-quantifier quality issues for the five skills scoring below 93; adding concrete output schemas would also lift most of those scores by 10 points each.
