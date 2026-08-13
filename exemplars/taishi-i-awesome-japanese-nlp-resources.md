---
slug: taishi-i-awesome-japanese-nlp-resources
repo: taishi-i/awesome-japanese-nlp-resources
audited: 2026-05-18
commit_sha: c3029cbaf68245df4db1251706fda9becd3fddf9
score: 98
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
  - R15
  - R16
---

# Exemplar: taishi-i/awesome-japanese-nlp-resources

**Score**: 98/100  |  **Date**: 2026-05-18  |  **Commit**: `c3029cbaf68245df4db1251706fda9becd3fddf9`

A four-skill Claude Code plugin wrapping a 2,200-entry Japanese NLP resource database, notable for concise trigger descriptions, in-body runnable search code, bilingual output templates, and explicit empty-input handling in every skill.

## Per-rule evidence

### R04 — Description as trigger

Each skill packs multiple action verbs and domain-specific constraints into its description, making skills self-disambiguating without shared routing logic.

> Real quote from `plugins/awesome-japanese-nlp-resources/skills/find-new-resources/SKILL.md:2`:
>
> ```
> description: Find Japanese NLP GitHub repositories that are NOT yet in awesome-japanese-nlp-resources. Suggests candidates to add for a given topic using WebSearch + WebFetch, then outputs contribution-ready markdown.
> ```

"NOT yet in", "contribution-ready markdown", and "using WebSearch + WebFetch" are concrete constraints that separate this skill from the `search` skill. The `search` description — "Search all Japanese NLP resources (libraries, models, datasets, tutorials, dictionaries, Hugging Face). Accepts keywords or natural language questions in any language." — covers the lookup case, leaving no overlap. Two skills with adjacent domains are fully disambiguated by description alone.

### R05 — Body length

All four skills fit under 500 lines: `search` runs 257 lines, `find-new-resources` 279, `research-issues` 279, `research-trends` 269. Each packs multi-step workflows — numbered steps, domain tables, Python scoring blocks, and output templates — without padding.

The `search` skill's six numbered steps (validate → interpret → locate data → search-and-score → re-rank → format) fill 257 lines because each step is executable instructions, not narrative. There is no "Background" section, no introductory theory, no limitations list.

### R06 — Code examples must be runnable

The `search` body embeds a 93-line Python scoring block as a literal bash heredoc. Field names (`u`, `n`, `d`, `c`, `s`, `st`, `ns`, `nd`, `sc`) are documented in the prose immediately above, placeholders are ALL_CAPS and called out explicitly, and the print output format is shown exactly.

> Real quote from `plugins/awesome-japanese-nlp-resources/skills/search/SKILL.md:94-122` (excerpt):
>
> ```python
> python3 << 'EOF'
> import json
>
> with open("PATH_FROM_STEP2") as f:
>     data = json.load(f)
>
> keywords = ["keyword1", "keyword2", "keyword3"]  # from Step 1
>
> results = []
> for item in data:
>     n = item.get("n", "").lower()
>     d = item.get("d", "").lower()
>     s = item.get("s", "").lower()
>     c = item.get("c", "").lower()
>
>     text_score = 0
>     for kw in keywords:
>         kw = kw.lower()
>         if n == kw:       text_score += 20
>         elif kw in n:     text_score += 10
>         if kw in d:       text_score += 5
>         if kw in s:       text_score += 3
>         if kw in c:       text_score += 2
>
>     if text_score < 8:
>         continue
> ...
> EOF
> ```

Scoring weights are written into code, not described in prose. This means every invocation gets the same scoring function with the same thresholds. Pseudocode or a prose description of "weight by field importance" would produce inconsistent thresholds across runs.

### R07 — Scope note when related skills exist

Cross-references flow both directions. The `find-new-resources` empty-result template routes to `search`:

> Real quote from `plugins/awesome-japanese-nlp-resources/skills/find-new-resources/SKILL.md:262-263`:
>
> ```
> - Check existing similar resources with `/awesome-japanese-nlp-resources:search "$ARGUMENTS"`
> ```

And `research-trends` routes the other direction — after surfacing web items not in the dataset, it notes:

> Real quote from `plugins/awesome-japanese-nlp-resources/skills/research-trends/SKILL.md:155`:
>
> ```
> these are candidates the user could also surface via `/awesome-japanese-nlp-resources:find-new-resources "$ARGUMENTS"`
> ```

Every "I didn't find what I wanted" exit path names the adjacent skill by full invocation path. The audit confirms no orphaned cross-references.

### R08 — Patterns over theory

The `search` skill replaces a prose explanation of query translation with a 21-row domain-to-keyword table:

> Real quote from `plugins/awesome-japanese-nlp-resources/skills/search/SKILL.md:38-57` (excerpt):
>
> ```
> | Domain (Japanese query hint) | Stem keywords | Tool names to add |
> |---|---|---|
> | 形態素解析 / morphological analysis | `morpholog`, `segment` | `mecab`, `janome`, `sudachi`, `kytea`, `kuromoji`, `jumanpp`, `nagisa` |
> | 固有表現認識 / NER | `named entit`, `NER`, `recogni` | `ginza`, `spacy`, `knp` |
> | 係り受け解析 / dependency parsing | `depend`, `parse`, `syntax` | `cabocha`, `knp`, `ginza`, `spacy` |
> | 感情分析 / sentiment analysis | `sentiment`, `emotion`, `opinion` | `oseti`, `wrime` |
> | 埋め込み / word vectors / embeddings | `embed`, `vector`, `represent` | `word2vec`, `fasttext`, `bert`, `sbert` |
> ```

Each row encodes exactly which stems and tool names correspond to a domain — no inference required. An equivalent prose instruction ("translate the user's morphological analysis query to English, including well-known tool names") would take 3× more tokens and produce inconsistent keyword sets across invocations.

### R15 — Handle empty input

All four skills have an explicit Step 0 defining behavior when `$ARGUMENTS` is blank — not an error state, but a detailed default workflow. The `find-new-resources` Step 0 specifies default topic label, keyword set, four ready-to-run WebSearch queries, and output heading variant:

> Real quote from `plugins/awesome-japanese-nlp-resources/skills/find-new-resources/SKILL.md:13-20`:
>
> ```
> - **Topic label** for output headings: "Latest Japanese NLP Resources"
> - **Keywords for Step 1**: `japanese nlp`, `日本語 nlp`, `japanese language processing`, `japanese machine learning`
> - **WebSearch queries for Step 4**: focus on recency — add "2025 2026" to every query, and include:
>   - `japanese NLP new library github 2026`
>   - `日本語 NLP 新しい ライブラリ github 2026`
>   - `awesome japanese nlp 2025 2026 new`
>   - `japanese natural language processing tool released 2025 2026`
> ```

The pattern: a blank argument is a mode switch, not a failure. The default path is specified with the same level of detail as the non-empty path.

### R16 — Define output format

Every skill ends with a literal markdown template. The `search` skill provides two variants (English/Japanese) keyed by query language and appends a mandatory use-case selection guide with column names and cell-level fill rules:

> Real quote from `plugins/awesome-japanese-nlp-resources/skills/search/SKILL.md:218-231`:
>
> ```
> ## Search results for "$ARGUMENTS"
>
> *(Searched for: keyword1, keyword2, ...)*
>
> Found N result(s).
>
> ### 1. [repository-name](url)
> **Category:** category > subcategory
> **Popularity:** ⭐ {st} stars  (or  📥 {dl} downloads for HF)
> Description text here.
> ```

The template is literal markdown with named fill-in slots (`{st}`, `N`), not a description of the desired output. A separate template for Japanese output uses the same slot names, making explicit what to translate (headings, prose) versus keep as-is (URLs, numbers, star counts).

## Worth adopting

**Pattern: Bilingual mode-switch via character-class detection.** Evidence: `skills/search/SKILL.md:210-214`, `skills/research-trends/SKILL.md:165-168`, `skills/research-issues/SKILL.md:164-168`. All three skills apply the identical two-line rule: "If `$ARGUMENTS` contains Japanese characters (hiragana / katakana / kanji) → **Japanese**, otherwise → **English** (default)." Each provides two complete output templates per language with identical slot names. Why it would be a useful rule: for domain plugins serving bilingual users, a single query-language detection rule applied uniformly across all skills produces more consistent output than leaving language selection to per-invocation judgment. Candidate rule: "**Use character-class detection for bilingual output.** Define a single language-detection rule (e.g. presence of hiragana/katakana/kanji → target language) and apply it identically in every skill in the plugin. Provide a full output template per language; do not attempt to translate a single template at inference time."
