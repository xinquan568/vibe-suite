# NLPM Audit: timescale/pg-aiguide
**Date**: 2026-04-16  |  **Artifacts**: 9  |  **Strategy**: single
**NL Score**: 94/100
**Security**: REVIEW
**Bugs**: 1  |  **Quality Issues**: 10  |  **Security Findings**: 3

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/postgres/SKILL.md | skill (orchestration) | 85 | Broken references — 7 links to non-existent `references/` subdir |
| CLAUDE.md | project instructions | 88 | "gpt-5 compatibility" references a non-existent model |
| skills/design-postgis-tables/SKILL.md | skill | 94 | "appropriate" used 3× as vague qualifier (−6) |
| skills/pgvector-semantic-search/SKILL.md | skill | 96 | "significantly" + "roughly" vague (−4) |
| skills/postgres-hybrid-text-search/SKILL.md | skill | 96 | "slightly" + "significantly" vague (−4) |
| skills/migrate-postgres-tables-to-hypertables/SKILL.md | skill | 97 | No significant issues |
| skills/setup-timescaledb-hypertables/SKILL.md | skill | 97 | Body approaching 500-line recommended limit |
| skills/design-postgres-tables/SKILL.md | skill | 98 | "usually optimal" vague (−2) |
| skills/find-hypertable-candidates/SKILL.md | skill | 98 | "mostly insert-heavy" vague (−2) |

## Security Scan

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 2 |
| Low | 1 |

### Execution Surface Inventory

| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (TypeScript) | scripts/validate-skills.ts, src/index.ts, src/httpServer.ts, src/migrate.ts, src/config.ts, src/types.ts, src/serverInfo.ts, src/apis/index.ts, src/apis/searchDocs.ts, src/prompts/index.ts, src/stdio.ts, src/util/featureFlags.ts, src/util/featureFlags.test.ts, generate-server.json.ts, release.ts |
| MCP configs | 0 |
| Package manifests | package.json |

### Security Findings

| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | src/migrate.ts | 37, 41, 51 | SQL identifier from env var | `${schema}` (sourced from `process.env.DB_SCHEMA`) interpolated directly into SQL template literals as an unquoted identifier in CREATE SCHEMA and SELECT queries. If DB_SCHEMA contains SQL metacharacters, this can break queries. Should use `quote_ident()` or validate the schema name against an allowlist. |
| 2 | Medium | src/apis/searchDocs.ts | 143–151 | SQL template with unquoted identifiers | `${schema}` and `${entityPrefix}` are interpolated into SQL table/index name positions. `entityPrefix` is derived from a strict Zod enum (`tiger`, `postgres`, `postgis`) so injection risk is low, but `schema` is not quoted. Use `quote_ident()` for both identifiers. |
| 3 | Low | package.json | 33–40 | Unpinned dependency versions | Six of eight production dependencies use `^` caret ranges (`ai`, `dotenv`, `gray-matter`, `migrate`, `pg`, `zod`). Minor/patch auto-upgrades can introduce unexpected breaking changes. `@tigerdata/mcp-boilerplate` is correctly pinned at `1.3.2`. |

## Bugs (PR-worthy)

| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/postgres/SKILL.md | 7 reference links point to `references/design-postgres-tables.md`, `references/pgvector-semantic-search.md`, etc. — the `references/` subdirectory does not exist under `skills/postgres/`. Claude cannot load these files. | Skill is effectively non-functional as an orchestration layer; agents loading it cannot follow its "Load the reference file" instructions. |

## Security Fixes (PR-worthy, Medium/Low only)

| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | src/migrate.ts:37,41,51 | `${schema}` used as unquoted SQL identifier | Replace with `${pgPool.escapeIdentifier(schema)}` (node-postgres) or add a regex allowlist check: `if (!/^[a-z_][a-z0-9_]*$/.test(schema)) throw new Error(...)` before use. |
| 2 | src/apis/searchDocs.ts:143,150 | `${schema}` interpolated in SQL template | Same fix as above; also consider extracting a `safeIdentifier()` helper used in both files. `entityPrefix` is already enum-constrained but would benefit from the same treatment for consistency. |
| 3 | package.json:33–40 | `^`-pinned production dependencies | Pin to exact versions (`=X.Y.Z`) or use a lock-file-only strategy with automated Renovate/Dependabot PRs to control upgrade timing. |

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | CLAUDE.md:15 | "required for gpt-5 compatibility" — GPT-5 does not exist; likely means GPT-4 or is an internal model identifier. Misleading for contributors. | −0 (not a scored artifact type) |
| 2 | skills/design-postgis-tables/SKILL.md:26 | "appropriate local projections for regional data" — "appropriate" is a vague quantifier | −2 |
| 3 | skills/design-postgis-tables/SKILL.md:171 | "Use appropriate local CRS for area/distance calculations" — "appropriate" again | −2 |
| 4 | skills/design-postgis-tables/SKILL.md (section header) | "Use Appropriate Precision" section title — third instance of "appropriate" | −2 |
| 5 | skills/design-postgres-tables/SKILL.md:47 | "Default `EXTENDED` usually optimal" — "usually" is a vague quantifier | −2 |
| 6 | skills/find-hypertable-candidates/SKILL.md:80 | "mostly insert-heavy patterns" — "mostly" is a vague quantifier | −2 |
| 7 | skills/pgvector-semantic-search/SKILL.md:243 | "can significantly increase latency" — "significantly" is vague | −2 |
| 8 | skills/pgvector-semantic-search/SKILL.md:149 | "roughly doubles HNSW link/graph overhead" — "roughly" is vague | −2 |
| 9 | skills/postgres-hybrid-text-search/SKILL.md:32 | "at the cost of slightly more complexity" — "slightly" is vague | −2 |
| 10 | skills/postgres-hybrid-text-search/SKILL.md:219 | "hybrid RRF alone significantly improves over single-method search" — "significantly" is vague | −2 |

## Cross-Component

**Broken reference chain in postgres/SKILL.md:** The orchestration skill instructs Claude to "Load the reference file" and provides 7 markdown links (e.g., `[design-postgres-tables](references/design-postgres-tables.md)`), but there is no `references/` directory under `skills/postgres/`. The referenced content exists as sibling SKILL.md files (`../design-postgres-tables/SKILL.md`, etc.) but at different paths. Two resolution options: (a) create symlinks or copies at `skills/postgres/references/`, or (b) change the links to relative paths pointing at the correct SKILL.md files.

**No contradictions found** between skills. The TimescaleDB trilogy (`find-hypertable-candidates` → `migrate-postgres-tables-to-hypertables` → `setup-timescaledb-hypertables`) cross-references each other correctly and consistently. The `postgres-hybrid-text-search` skill correctly defers to `pgvector-semantic-search` for advanced tuning.

**API deprecation coverage:** `setup-timescaledb-hypertables` includes a dedicated API deprecation table (old → new function names). The other TimescaleDB skills use the new API consistently. No stale API usage detected.

## Recommendation

**REVIEW** — submit NL fix PRs, flag security findings in issue.

The collection is high quality (94/100 average). One actionable PR covers the main bug: restore the `references/` directory under `skills/postgres/` so the orchestration skill's links resolve. The two medium security findings (`quote_ident` for schema identifiers in migrate.ts and searchDocs.ts) should be filed as a private security issue or addressed in a separate PR with a note in the PR body about the low exploitability (server-operator-controlled env var). Vague-quantifier cleanup across the skill files is optional polish.
