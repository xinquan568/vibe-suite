---
slug: google-skills
repo: google/skills
audited: 2026-05-25
commit_sha: f0253cb4d1cabac751622153cb93be907b2eca88
score: 98
exemplifies:
  - R04
  - R05
  - R06
  - R08
---

# Exemplar: google/skills

**Score**: 97.7/100 average across 19 SKILL.md files (median 98, 12 of 19 at 100/100)  |  **Date**: 2026-05-25  |  **Commit**: `f0253cb4d1cabac751622153cb93be907b2eca88`

Google's first-party Agent Skills corpus, launched at Cloud Next 2026 under Apache 2.0. Nineteen skills covering Google Cloud products (AlloyDB, BigQuery, Cloud Run, Cloud SQL, Firebase, Gemini API, GKE), Well-Architected Framework pillars (Security, Reliability, Cost, Performance, Sustainability, Operational Excellence), and recipe skills (Onboarding, Auth, Network Observability). Distributed via the cross-tool `npx skills` installer maintained by Vercel Labs, designed to work in Claude Code, Codex CLI, Gemini CLI, Antigravity, Cursor, and others on the agentskills.io open spec.

What makes this corpus an exemplar: it is the first major vendor-published reference for the open Agent Skills spec, written by authors who designed for cross-tool retrieval rather than for a single agent's UI. Several patterns here are not yet codified in nlpm's rulebook but are visibly load-bearing for retrieval quality.

## Per-rule evidence

### R04 — Description as trigger

Every product skill closes its description with an explicit `WHEN:` clause that enumerates the user phrases the skill should match. This is a stricter version of the "Use when..." convention rewarded by R04: instead of one prose trigger sentence, the WHEN clause is a comma-separated list of 8–13 trigger phrases optimized for substring matching.

> `skills/cloud/gke-basics/SKILL.md:7`:
>
> ```
> description: "Plan, create, and configure production-ready Google Kubernetes Engine (GKE) clusters using the golden path Autopilot configuration. Covers Day-0 checklist, Autopilot vs Standard, networking (private clusters, VPC-native, Gateway API), security (Workload Identity, Secret Manager, RBAC hardening), observability, scaling, cost optimization, and AI/ML inference. WHEN: create GKE cluster, provision GKE environment, design GKE networking, secure GKE, optimize GKE cost, GKE autoscaling, GKE inference, GKE upgrade, GKE observability, GKE multi-tenancy, GKE batch, GKE HPC, GKE compute class."
> ```

> `skills/cloud/gemini-api/SKILL.md:3`:
>
> ```
> description: Guides the usage of the Gemini API on Agent Platform with the Google Gen AI SDK. Use when the user asks about using Gemini in an enterprise environment or explicitly mentions Vertex AI, Google Cloud, or Agent Platform. Covers SDK usage (Python, JS/TS, Go, Java, C#), capabilities like Live API, tools, multimedia generation, caching, and batch prediction.
> ```

What makes these strong: the WHEN clause separates the *prose summary* (for humans reading the catalog) from the *retrieval surface* (for the agent matching a user query). A weaker description would conflate the two — either burying triggers inside a marketing sentence or padding with generic terms like "comprehensive guide." The GKE description sacrifices ~5 R04 length points to gain a retrieval surface that catches 13 distinct user phrasings; on a corpus where every skill competes for context budget at retrieval time, that trade is worth it.

---

### R05 — Body length

All seven product skills use a thin-index + deep-references architecture identical in spirit to antfu/skills but more rigorous in scale. The SKILL.md holds a `## Quick Start` runnable block plus a `## Reference Directory` table; depth lives in `references/*.md` sub-files.

| Skill | SKILL.md lines | references/ files |
|-------|---------------:|------------------:|
| `cloud/gemini-api` | 116 | 9 |
| `cloud/cloud-sql-basics` | ~120 | 11 |
| `cloud/gke-basics` | ~220 | 21 |
| `cloud/google-cloud-networking-observability` | ~140 | 8 |
| `cloud/agent-platform-skill-registry` | ~160 | 6 |

The novel piece is the routing table itself — every row has a third column, **Trigger Keywords**, that lists the user phrases routing to that reference. This is not in nlpm's rulebook today; it should be.

> `skills/cloud/gke-basics/SKILL.md:32-41` (excerpt):
>
> ```
> | Scenario        | Trigger Keywords                                           | Reference                                  |
> | Core Concepts   | Autopilot vs Standard, architecture, pricing, what is GKE  | core-concepts.md                           |
> | Cluster Creation| create cluster, new cluster, provision GKE                 | gke-cluster-creation.md                    |
> | Networking      | private cluster, VPC, subnet, Gateway API, DNS, ingress    | gke-networking.md                          |
> | Security & IAM  | Workload Identity, Secret Manager, RBAC, Binary Auth, gVisor | gke-security.md                          |
> ```

The pattern lets the SKILL.md serve as an O(1) routing layer (~220 lines for a 21-reference skill) while preserving full depth on demand. Compare to antfu's `turborepo` skill (912 lines, R05 penalty -10) which inlined everything — the same content shape, the routing-table pattern would have kept it under budget.

---

### R06 — Runnable code examples

Quick-start blocks in product skills are minimal but complete: every line is copy-pasteable and the sequence ends in observable state.

> `skills/cloud/gke-basics/SKILL.md:18-24`:
>
> ```bash
> gcloud services enable container.googleapis.com --quiet
> gcloud container clusters create-auto my-cluster --region=us-central1 --quiet
> gcloud container clusters get-credentials my-cluster --region=us-central1 --quiet
> kubectl create deployment hello-server \
>   --image=us-docker.pkg.dev/google-samples/containers/gke/hello-app:1.0
> ```

What makes this strong: each command produces a verifiable side effect (API enabled → cluster created → kubeconfig populated → deployment running), so the agent can verify success at each step without consulting the references. The sequence also models the "golden path" mentioned in the description — the same defaults that the rest of the skill explains, run in five commands.

The recipe skills (`google-cloud-recipe-auth`, `google-cloud-recipe-onboarding`) go further and embed full Python and Terraform snippets for the most common cases (Workload Identity Federation, project enablement, OAuth client setup) inside the SKILL.md itself rather than deferring to references.

---

### R08 — Patterns over theory

The Well-Architected Framework skills are organized around concrete decision points rather than abstract principles. The Reliability skill leads with measurable SLOs and named GCP services:

> `skills/cloud/google-cloud-waf-reliability/SKILL.md` (preferences section):
>
> ```
> - Define explicit Service Level Indicators (SLIs) and Service Level Objectives (SLOs) before discussing reliability
> - Prefer Active-Active multi-region for Tier-1 workloads; document the failover RTO
> - Use Cloud Load Balancing health checks tied to the SLI, not pod liveness alone
> - For data, prefer dual-write + verify over async replication when RPO < 60s
> ```

Each line names what to do AND the narrower case where it applies ("when RPO < 60s", "for Tier-1 workloads"). The contrast with theory-first prose is sharp: a weaker WAF skill would read "Reliability is about minimizing service disruption through architectural redundancy" — true but untriggerable.

The pattern repeats across all six WAF pillars: the prose layer is decision-oriented, the references layer is theory.

---

## What this corpus exposed about the rulebook

The audit also surfaced gaps in nlpm's own scoring. Documenting them here so future authors and the auditor pipeline see the same evidence:

1. **Tier-1/Tier-2 path classification is too coarse.** `nlpm:scoring` distinguishes Tier 1 (tool-namespaced paths like `.codex/skills/`) from Tier 2 (Claude Code paths like `.claude/skills/` and `skills/**/SKILL.md`). Google's corpus lives at `skills/cloud/*/SKILL.md` — literal Tier 2 — but it is a tool-agnostic open-spec repo (no `.claude/`, no `plugin.json`). A naive scorer would penalize the corpus for missing `## Output`, missing `model:`, missing `version:` — all Claude-Code overlays that don't apply. The audit applied Tier 1 manually; the rulebook should add a Tier-1.5 detector ("`skills/**/SKILL.md` matches AND no Claude-Code markers present → score as Tier 1").
2. **"name MUST match parent directory" has no penalty row.** `nlpm:conventions §5` states the rule; `nlpm:scoring` has no penalty for violations. `gemini-agents-api/SKILL.md` declares `name: gemini-managed-agents-api` — a deterministic high-confidence spec MUST violation that the audit had to calibrate ad-hoc. This deserves an explicit row in the rubric.
3. **R01 over-flags "relevant" in `## Relevant X` headers** and `relevant to <scope>` phrasings. The six WAF skills contain ~12 occurrences that are legitimate semantic usage ("pertinent to"), not vague-quantifier hedges. R01 should carve out markdown headers and the `relevant to <named-scope>` pattern.
4. **R04 length budget should exclude `WHEN:` blocks.** GKE's description loses points for length, but a large fraction of that length is the WHEN clause — a retrieval-surface investment that nlpm's rulebook doesn't yet recognize as separate from prose length.

---

## Worth adopting

**Pattern: `WHEN:` clause as explicit retrieval surface.** Append `WHEN: <phrase>, <phrase>, …` to the description, listing the user queries that should trigger the skill. Treat this as separate from the prose summary that humans read. Evidence: `skills/cloud/gke-basics/SKILL.md:7` (13 WHEN triggers, plus a prose summary; substring-matchable for retrieval). Why a useful rule: descriptions written for human catalog browsing under-perform on retrieval; descriptions written purely for retrieval read poorly for humans. The two-clause split lets one description serve both audiences and makes the retrieval surface auditable.

**Pattern: Trigger-keyword column in the reference routing table.** When a SKILL.md uses a routing table to dispatch to `references/*.md`, add a `Trigger Keywords` column between Scenario and Reference. Evidence: `skills/cloud/gke-basics/SKILL.md:30-50`. Why a useful rule: the rule R05 incentivizes the thin-index pattern, but the routing-table format isn't specified, so authors invent their own. Without trigger keywords in the table, the index can't fulfill its routing role at retrieval time — the agent has to load the reference file to find out whether it matches.

**Pattern: Recipe / Pillar / Product skill taxonomy at scale.** When publishing >10 skills, split them into product skills (one per technology), pillar skills (one per cross-cutting concern), and recipe skills (one per common multi-product workflow). Evidence: google/skills splits 19 files as 7 products + 6 WAF pillars + 3 recipes + 3 platform skills. Why a useful rule: flat skill collections force every skill to redundantly cover concerns that pillar skills could centralize; large flat collections also produce description-trigger collisions at retrieval time.
