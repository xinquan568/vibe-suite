# NLPM Re-Audit: kubesphere/kubesphere

**Date**: 2026-05-07  |  **Artifacts**: 26  |  **Strategy**: batched
**NL Score**: 99.7/100
**Bugs**: 0  |  **Quality Issues**: 2

## NL Score Summary

| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/kubesphere-volcano/SKILL.md | skill | 94 | 3× vague quantifier "appropriate" (-6) |
| skills/kubesphere-devops-pipeline/SKILL.md | skill | 98 | 1× vague quantifier "properly" (-2) |
| skills/kubesphere-devops-argocd/SKILL.md | skill | 100 | — |
| skills/nodegroup/SKILL.md | skill | 100 | — |
| skills/kubesphere-core/SKILL.md | skill | 100 | — |
| skills/whizard-events/SKILL.md | skill | 100 | — |
| skills/opensearch/SKILL.md | skill | 100 | — |
| skills/whizard-telemetry-ruler/SKILL.md | skill | 100 | — |
| skills/kubesphere-devops-overview/SKILL.md | skill | 100 | — |
| skills/kubesphere-cluster-management/SKILL.md | skill | 100 | — |
| skills/kubesphere-network-extension-operations/SKILL.md | skill | 100 | — |
| skills/kubesphere-openkruise/SKILL.md | skill | 100 | — |
| skills/vector/SKILL.md | skill | 100 | — |
| skills/kubesphere-multi-tenant-management/SKILL.md | skill | 100 | — |
| skills/frontend-integration-yaml/SKILL.md | skill | 100 | — |
| skills/whizard-telemetry/SKILL.md | skill | 100 | — |
| skills/kubesphere-devops-credentials/SKILL.md | skill | 100 | — |
| skills/wiztelemetry-tracing/SKILL.md | skill | 100 | — |
| skills/whizard-logging/SKILL.md | skill | 100 | — |
| skills/frontend-forge-fi-operations/SKILL.md | skill | 100 | — |
| skills/kubesphere-devops-tenant/SKILL.md | skill | 100 | — |
| skills/whizard-auditing/SKILL.md | skill | 100 | — |
| skills/kubesphere-fluid/SKILL.md | skill | 100 | — |
| skills/whizard-notification/SKILL.md | skill | 100 | — |
| skills/kubesphere-extension-management/SKILL.md | skill | 100 | — |
| skills/kubesphere-devops-jenkins/SKILL.md | skill | 100 | — |

## Bugs (PR-worthy)

| # | File | Issue | Confidence | Evidence | Impact |
|---|------|-------|------------|----------|--------|

No high-confidence bugs found.

## Quality Issues (informational)

| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | skills/kubesphere-volcano/SKILL.md | 3× vague quantifier "appropriate": "Use appropriate queue" (line 715), "Use appropriate restart policy" (line 733), "appropriate modifications" (line 790) | -6 |
| 2 | skills/kubesphere-devops-pipeline/SKILL.md | 1× vague quantifier "properly": "to properly track ownership" (line 185) | -2 |

## Cross-Component

`skills/kubesphere-devops-tenant/SKILL.md` lines 49 and 75 reference `../../core/kubesphere-core/SKILL.md`. From the skill's location at `skills/kubesphere-devops-tenant/`, this path resolves to `core/kubesphere-core/SKILL.md` at repo root — a directory that does not appear in the scored artifact set. The kubesphere-core skill exists at `skills/kubesphere-core/SKILL.md`; the correct relative path would be `../kubesphere-core/SKILL.md`. Medium confidence: a `core/` directory may exist in the full repo.

## Recommendation

25 of 26 skills score 100/100; the collection is exceptionally high-quality reference material. The two quality findings are cosmetic: replace three instances of "appropriate" in kubesphere-volcano and one "properly" in kubesphere-devops-pipeline with concrete, prescriptive language.
