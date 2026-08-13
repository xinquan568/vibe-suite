---
slug: timescale-pg-aiguide
repo: timescale/pg-aiguide
audited: 2026-05-13
commit_sha: c61d613e7842096e9aaa7d9b8b6fddbdaa9ec5be
score: 94
exemplifies:
  - R04
  - R06
  - R07
  - R08
---

# Exemplar: timescale/pg-aiguide

**Score**: 94/100  |  **Date**: 2026-05-13  |  **Commit**: `c61d613e7842096e9aaa7d9b8b6fddbdaa9ec5be`

A seven-skill PostgreSQL skills collection (pgvector, TimescaleDB, hybrid search, table design, PostGIS, hypertable migration and candidate analysis) that demonstrates trigger-first descriptions, copy-paste-ready SQL examples, tight cross-skill scope handoffs, and named-pattern decision tables across every file.

## Per-rule evidence

### R04 — Description as trigger

Every skill uses a two-block description structure: an explicit `**Trigger when user asks to:**` list of action phrases followed by a `**Keywords:**` line. This makes the description function as a dispatch rule rather than a summary.

> Real quote from `skills/pgvector-semantic-search/SKILL.md:3-16`:
>
> ```
> description: |
>   Use this skill for setting up vector similarity search with pgvector for AI/ML
>   embeddings, RAG applications, or semantic search.
>
>   **Trigger when user asks to:**
>   - Store or search vector embeddings in PostgreSQL
>   - Set up semantic search, similarity search, or nearest neighbor search
>   - Create HNSW or IVFFlat indexes for vectors
>   - Implement RAG (Retrieval Augmented Generation) with PostgreSQL
>   - Optimize pgvector performance, recall, or memory usage
>   - Use binary quantization for large vector datasets
>
>   **Keywords:** pgvector, embeddings, semantic search, vector similarity, HNSW,
>   IVFFlat, halfvec, cosine distance, nearest neighbor, RAG, LLM, AI search
> ```

Six user-intent phrases cover six concrete task types; the keyword list covers noun-only queries ("pgvector halfvec") that the verb-phrased triggers might miss. All seven skills follow this pattern identically — including the orchestration `postgres/SKILL.md`, which adds a third block listing which sub-skill to load for each task domain.

### R06 — Code examples must be runnable

SQL examples throughout the collection use real table definitions, real operator syntax, and real parameter names. The binary quantization block in the pgvector skill is the strongest instance: it includes a `CREATE TABLE` with a generated column, an HNSW index with explicit op class, a `SET` statement, and a two-stage CTE query with explicit casts — none of it pseudocode.

> Real quote from `skills/pgvector-semantic-search/SKILL.md:175-203`:
>
> ```sql
> CREATE TABLE items (
>   id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
>   contents TEXT NOT NULL,
>   embedding halfvec(1536) NOT NULL,
>   embedding_bq bit(1536) GENERATED ALWAYS AS (binary_quantize(embedding)::bit(1536)) STORED
> );
>
> CREATE INDEX ON items USING hnsw (embedding_bq bit_hamming_ops);
>
> -- Query with re-ranking for better recall
> -- ef_search must be >= inner LIMIT to retrieve enough candidates
> SET hnsw.ef_search = 800;
> WITH q AS (
>   SELECT binary_quantize($1::halfvec(1536))::bit(1536) AS qb
> )
> SELECT *
> FROM (
>   SELECT i.id, i.contents, i.embedding
>   FROM items i, q
>   ORDER BY i.embedding_bq <~> q.qb
>   LIMIT 800
> ) candidates
> ORDER BY candidates.embedding <=> $1::halfvec(1536)
> LIMIT 10;
> ```

What makes this exemplary rather than adequate: the inline comments explain the 80× oversampling ratio ("binary quantization loses precision, so more candidates are needed") and the `ef_search` constraint ("must be >= inner LIMIT"), so the example carries enough context to be adapted without guesswork. The `find-hypertable-candidates` skill sustains this standard by providing runnable `pg_stat_user_tables` queries with explicit column aliases and filter conditions throughout Step 1.

### R07 — Scope note when related skills exist

Two skills explicitly scope themselves and hand off to named siblings in the first paragraph of the body — before any content that requires the scope. `postgres-hybrid-text-search` covers RRF fusion and BM25 setup but routes advanced pgvector tuning to its sibling. `find-hypertable-candidates` opens by naming the migration skill as its follow-on.

> Real quote from `skills/postgres-hybrid-text-search/SKILL.md:27-28`:
>
> ```
> This guide covers combining pg_textsearch (BM25) with pgvector. Requires both
> extensions. For high-volume setups, filtering, or advanced pgvector tuning
> (binary quantization, HNSW parameters), see the **pgvector-semantic-search** skill.
> ```

> Real quote from `skills/find-hypertable-candidates/SKILL.md:25-26`:
>
> ```
> Identify tables that would benefit from TimescaleDB hypertable conversion. After
> identification, use the companion "migrate-postgres-tables-to-hypertables" skill
> for configuration and migration.
> ```

Both notes appear in the opening paragraph so a reader who loaded the wrong skill discovers the right one before reading further. The hybrid-search note is also specific about *which* topics belong to the other skill (binary quantization, HNSW parameters, filtering), not just that one exists.

### R08 — Patterns over theory

The collection structures knowledge as situation-specific decision rules, not concept explanations. Each skill opens with a "Golden Path (Default Setup)" section that gives a single, concrete working configuration, then follows with explicit "choose X if Y" deviation sections. This ensures Claude produces a concrete answer in the common case and only consults decision tables when a deviation condition is met.

> Real quote from `skills/pgvector-semantic-search/SKILL.md:29-39`:
>
> ```
> ## Golden Path (Default Setup)
>
> Use this configuration unless you have a specific reason not to.
> - Embedding column data type: `halfvec(N)` where `N` is your embedding dimension
> - Distance: cosine (`<=>`)
> - Index: HNSW (`m = 16`, `ef_construction = 64`). Use `halfvec_cosine_ops` and
>   query with `<=>`.
> - Query-time recall: `SET hnsw.ef_search = 100`
> - Query pattern: `ORDER BY embedding <=> $1::halfvec(N) LIMIT k`
>
> This setup provides a strong speed–recall tradeoff for most text-embedding workloads.
> ```

The IVFFlat section continues the pattern: it opens with "Default to HNSW" and lists four specific conditions under which IVFFlat is appropriate, rather than presenting both indexes neutrally and leaving the choice to judgment.

The `find-hypertable-candidates` skill takes patterns over theory furthest with an explicit numeric scoring rubric: tables scoring 8+ points on a weighted checklist are candidates; below 8 they are not. No vague judgment calls.

> Real quote from `skills/find-hypertable-candidates/SKILL.md:197-213`:
>
> ```
> ## Step 2: Candidacy Scoring (8+ points = good candidate)
>
> ### Time-Series Characteristics (5+ points needed)
>
> - Has timestamp/timestamptz column: **3 points**
> - Data inserted chronologically: **2 points**
> - Queries filter by time: **2 points**
> - Time aggregations common: **2 points**
>
> ### Scale & Performance (3+ points recommended)
>
> - Large table (1M+ rows or 100MB+): **2 points**
> - High insert volume: **1 point**
> - Infrequent updates to historical: **1 point**
> - Range queries common: **1 point**
> - Aggregation queries: **2 points**
> ```

## Worth adopting

**Pattern: Deprecation table (old → new API mapping).** Evidence: `skills/setup-timescaledb-hypertables/SKILL.md:454-480`. The skill includes a full table mapping deprecated TimescaleDB identifiers (`timescaledb.compress`, `add_compression_policy()`, `compress_chunk()`) to their current replacements. This prevents Claude from generating stale API calls when its training data contains both the old and new forms. Why it would be a useful rule: *When a skill covers a library with a deprecation history, include an old→new API table so Claude emits current syntax even when training data skews toward the deprecated form.*

**Pattern: Symptom → Cause → Fix troubleshooting table.** Evidence: `skills/pgvector-semantic-search/SKILL.md:334-345`. A three-column table covers eight failure modes (e.g., "Query does not use ANN index", "Fewer results than expected") with a likely cause and a concrete fix for each. This is more actionable than a prose "Common Issues" section because Claude can pattern-match the user's described symptom directly to a fix without inference. Why it would be a useful rule: *Skill files covering configuration-sensitive or operationally complex topics should include a Symptom → Cause → Fix table for the most common failure modes.*
