---
slug: RKiding-Awesome-finance-skills
repo: RKiding/Awesome-finance-skills
audited: 2026-05-13
commit_sha: 853f09b4d0baae747759ed31e21ed5c5b2316a5f
score: 92
exemplifies:
  - R04
  - R05
  - R06
  - R08
---

# Exemplar: RKiding/Awesome-finance-skills

**Score**: 92/100  |  **Date**: 2026-05-13  |  **Commit**: `853f09b4d0baae747759ed31e21ed5c5b2316a5f`

A 10-skill finance agent toolkit (A-Share/HK/US markets) where the best-scoring skills (alphaear-stock at 100/100, alphaear-sentiment at 98/100) demonstrate tight description triggers, compact bodies, and concrete output schemas.

## Per-rule evidence

### R04 — Description as trigger

The skills consistently pack 2–3 specific trigger phrases into the `description` field — matching real user query patterns rather than summarizing what the skill does.

> From `skills/alphaear-stock/SKILL.md:3`:
>
> ```
> description: Search A-Share/HK/US finance stock tickers and retrieve finance stock price history. Use when user asks about finance stock codes, recent price changes, or specific company finance stock info.
> ```

> From `skills/alphaear-search/SKILL.md:3`:
>
> ```
> description: Perform finance web searches and local context searches. Use when the user needs general finance info from the web (Jina/DDG/Baidu) or needs to retrieve finance information from a local document store (RAG).
> ```

> From `skills/alphaear-sentiment/SKILL.md:3`:
>
> ```
> description: Analyze finance text sentiment using FinBERT or LLM. Use when the user needs to determine the sentiment (positive/negative/neutral) and score of financial text markets.
> ```

Each description names the concrete implementation (FinBERT, Jina/DDG/Baidu, A-Share/HK/US) so the agent can distinguish between skills without loading their bodies — the specificity is what makes these triggers rather than summaries.

### R05 — Under 500 lines

All nine domain-specific skills are dramatically under budget. alphaear-stock is 41 lines; alphaear-search is 37 lines; alphaear-sentiment is 58 lines. Even the longest skill in the repo, `skill-creator/SKILL.md` at 372 lines, stays well within the 500-line ceiling.

> From `skills/alphaear-stock/SKILL.md:1-41` (complete file):
>
> ```
> ---
> name: alphaear-stock
> description: Search A-Share/HK/US finance stock tickers and retrieve finance stock
>   price history. Use when user asks about finance stock codes, recent price
>   changes, or specific company finance stock info.
> ---
>
> # AlphaEar Stock Skill
>
> ## Overview
>
> Search A-Share/HK/US stock tickers and retrieve historical price data (OHLCV).
>
> ## Capabilities
>
> ### 1. Stock Search & Data
>
> Use `scripts/stock_tools.py` via `StockTools`.
>
> -   **Search**: `search_ticker(query)`
>     -   Fuzzy search by code or name (e.g., "Moutai", "600519").
>     -   Returns: List of `{code, name}`.
> -   **Get Price**: `get_stock_price(ticker, start_date, end_date)`
>     -   Returns DataFrame with OHLCV data.
>     -   Dates format: "YYYY-MM-DD".
> -   **Get Fundamentals**: `get_stock_fundamentals(ticker)`
>     -   Returns dict with sector, industry, market cap, PE ratio, and summary.
>     -   Supports A-Share/HK/US stocks.
>
> ## Dependencies
>
> -   `pandas`, `requests`, `akshare`, `yfinance`
> -   `scripts/database_manager.py` (stock tables)
>
> ## Notes
>
> -   **Proxy**: For US stock data (via `yfinance`), you may need to set environment
>     variables if your network cannot reach Yahoo Finance directly:
>     ```bash
>     export HTTP_PROXY="http://<proxy_ip>:<port>"
>     export HTTPS_PROXY="http://<proxy_ip>:<port>"
>     ```
> -   **A-Share/HK**: Data is primarily fetched via `akshare` (EastMoney), which
>     usually works best with a direct connection in China.
> ```

This is not just technically under budget — the skill covers 3 methods with typed return values, dependencies, and a network-configuration note in 41 lines because every section earns its presence.

### R06 — Code examples must be runnable

`skill-creator/SKILL.md` provides executable bash commands at lines 278–284, not generic templates with angle-bracket placeholders:

> From `skills/skill-creator/SKILL.md:278-284`:
>
> ```
> Examples:
>
> ```bash
> scripts/init_skill.py my-skill --path skills/public
> scripts/init_skill.py my-skill --path skills/public --resources scripts,references
> scripts/init_skill.py my-skill --path skills/public --resources scripts --examples
> ```
> ```

`alphaear-sentiment/SKILL.md` goes further: rather than describing what a sentiment prompt should contain, it embeds the complete prompt text the agent uses verbatim, with only the substitution variable `{text}` remaining:

> From `skills/alphaear-sentiment/SKILL.md:35-41`:
>
> ```markdown
> 请分析以下金融/新闻文本的情绪极性。
> 返回严格的 JSON 格式:
> {"score": <float: -1.0到1.0>, "label": "<positive/negative/neutral>", "reason": "<简短理由>"}
>
> 文本: {text}
> ```

Both examples can be used as-is — the bash commands run without editing; the prompt text pastes directly into an LLM call.

### R08 — Patterns over theory

`skill-creator/SKILL.md` teaches skill design through three named "Progressive Disclosure Patterns", each showing when and how to split content across files with concrete directory trees and markdown examples — not abstract advice about "keeping context lean":

> From `skills/skill-creator/SKILL.md:127-144`:
>
> ```
> **Pattern 1: High-level guide with references**
>
> ```markdown
> # PDF Processing
>
> ## Quick start
>
> Extract text with pdfplumber:
> [code example]
>
> ## Advanced features
>
> - **Form filling**: See [FORMS.md](FORMS.md) for complete guide
> - **API reference**: See [REFERENCE.md](REFERENCE.md) for all methods
> - **Examples**: See [EXAMPLES.md](EXAMPLES.md) for common patterns
> ```
>
> Codex loads FORMS.md, REFERENCE.md, or EXAMPLES.md only when needed.
> ```

`alphaear-sentiment/SKILL.md` applies the same principle for mode selection — it doesn't explain that FinBERT and LLM modes have different accuracy trade-offs in prose; it provides a numeric **Scoring Guide** that defines exactly which sentiment label maps to which numeric range:

> From `skills/alphaear-sentiment/SKILL.md:43-47`:
>
> ```
> **Scoring Guide:**
> - **Positive (0.1 to 1.0)**: Optimistic news, profit growth, policy support, etc.
> - **Negative (-1.0 to -0.1)**: Losses, sanctions, price drops, pessimism.
> - **Neutral (-0.1 to 0.1)**: Factual reporting, sideways movement, ambiguous impact.
> ```

The bins make classification deterministic — the agent applies the table rather than exercising judgment about what counts as "positive."

## Worth adopting

Pattern: **Embed ready-to-use prompts inline for agentic execution paths.** Evidence: `skills/alphaear-sentiment/SKILL.md:31-41`. When a skill exposes an LLM-direct-call path alongside a code-tool path, providing the complete prompt text as a code block (with only substitution variables remaining) eliminates a generation step where the agent might improvise its own prompt and introduce hallucination. Why it would be a useful rule: current R06 and R08 don't cover the case where the artifact Claude executes is *another prompt* — an imperative rule like "If a skill offers an LLM-agentic path, embed the literal prompt text with variable placeholders, never describe the prompt's intent and let the agent generate it" would prevent agents from inventing their own prompts instead of using a validated one.
