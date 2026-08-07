<!-- ported from the nlpm auditor at capability parity -->
# vibe-suite auditor — data contracts (SCHEMAS)

Every record the auditor pipeline reads or writes is specified here. Design goal: every
record is self-interpretable from this contract alone.

All durable pipeline data lives on the **`auditor-data` branch** of `xinquan568/vibe-suite`,
never beside the code on `main`:

| Contract | Path (auditor-data branch) |
|---|---|
| Registry (mutable state) | `registry/repos.json` |
| Findings ledger | `ledgers/findings.jsonl` |
| Disagreements ledger | `ledgers/disagreements.jsonl` |
| Event log | `ledgers/events.jsonl` |
| Vocab advisories ledger | `ledgers/vocab-advisories.jsonl` |
| Reports / audits / articles / exemplars | `reports/` `audits/` `articles/` `exemplars/` |
| Rule-health feedback log | `feedback/log.json` |
| Published suppressions observed | `feedback/suppressions.jsonl` |

`feedback/log.json` is REBUILT wholesale by `rule-health.py` on every run — it is derived
state, not a log, so it carries no history and is safe to delete and regenerate.
`feedback/suppressions.jsonl` is APPEND-ONLY like the ledgers: each record is one
observation of a published config at a given blob sha, deduplicated on
`(repo, sha, path)`. A config that disappears from a repository is never deleted here —
that it once existed is the fact worth keeping, and an edit appends a new record rather
than replacing the old one.

Workflows use a dual checkout: code from `main` at the job workspace root, the data branch
into `_data/`.

## 1. Registry — `registry/repos.json`

Mutable state, not a log. Mutated in place through the atomic validate-then-rename writer;
it is the only file in this document that is rewritten rather than appended.

Top level: a single `repos` map keyed by `owner/name`.

### Empty-registry bootstrap shape

The empty, freshly bootstrapped registry is exactly:

```json
{"repos": {}}
```

The registry is bootstrapped **once, by a human**, on the `auditor-data` branch. No stage
ever creates it: any stage that needs the registry and cannot find
`registry/repos.json` on the data branch REFUSES with `registry-missing`
(printed as `REFUSE:registry-missing`, non-zero exit) rather than auto-creating an empty
one — a silently self-created registry would erase all pipeline memory. By the same
design, registry state is **excluded from E8.5's migration**: the bootstrap above is the
only supported way an empty registry comes into existence.

### Repo record

| Field | Meaning | Writer stage |
|---|---|---|
| status | pipeline state enum: `discovered` / `audited` / `contributed` / `tracked` / `complete` / `policy_denied` / `policy_cla_required` / `orphaned` | each stage |
| audit_issue | tracking issue number | discover |
| stars | star count at discovery | discover |
| pipeline_prs | PR numbers opened on the target | contribute |
| prs | per-PR state snapshots (see PR record) | track |
| case_study_candidate | any PR merged or applied separately | track |
| rule_adopted | maintainer signaled rule adoption | track |
| policy_no_external_prs | owner on the deny list | contribute |
| policy_cla_required | CLA unsigned for a CLA-gated owner | contribute |
| terminal_reason | why orphaned (currently `prs_disabled`; room for deleted/archived) | manual/future |
| retired_at | date moved to orphaned | manual/future |
| retired_note | human explanation | manual/future |
| exemplar_published / exemplar_path | exemplar side-effects | exemplar workflow |

### Status invariants

- `policy_denied` and `policy_cla_required` are terminal-but-recoverable: they never
  auto-advance and are excluded from in-flight counts. Recovery is a human act
  (deny-list edit, or CLA variables set + re-label).
- `orphaned` is terminal for repos where PRs existed but became untrackable. The original
  PR list is preserved as an audit trail; no synthetic terminal outcome event is emitted,
  because no maintainer ever adjudicated those PRs.

### PR record (inside `prs`)

`number`, `state` (raw `OPEN`/`CLOSED`/`MERGED`), `mergedAt`, `closedAt`, `title`,
`createdAt`, `updatedAt` (drives stale detection), `outcome` (pipeline enum: `merged` /
`applied_separately` / `rejected` / `open` / `cla_blocked`), `fingerprints[]` (from the
PR-metadata block; empty for legacy PRs), `rule_ids[]` (parallel array; empty for legacy),
`stale_90d_emitted` (sticky once-only flag).

Invariant: PR-record fields are additive — readers must default-read fields that may
predate a given record.

## 2. Finding record — `ledgers/findings.jsonl`

Append-only JSONL; one finding per line.

| Field | Meaning | Required |
|---|---|---|
| event | constant discriminator `"finding"` | yes |
| timestamp | ISO-8601 UTC, set by the post-step, never by the model | yes |
| audit_run_id | CI run id or `"local"` | yes |
| repo | target `owner/name` | yes |
| commit_sha | target HEAD at audit; `"unknown"` fallback | yes |
| fingerprint | `sha256:`-prefixed join key (see §3) | yes |
| category | enum: `nl_quality` / `security` / `bug` / `cross_component` | yes |
| rule_id | namespaced rule identifier | yes |
| file | path relative to the target root | yes |
| line | int, or null for file-level / cross-component findings | yes |
| severity | enum: `critical` / `high` / `medium` / `low` / `info` | yes |
| confidence | enum `high` / `medium` / `low`; only `high` ever reaches contribute; `high` requires actively reproduced breakage | yes |
| evidence | one-line concrete observation when `high`; empty otherwise | yes |
| penalty | negative int for `nl_quality`; null otherwise | yes |
| pattern | short machine-friendly id | yes |
| description | one-line summary, no newlines | yes |
| false_positive | auditor self-invalidated flag | yes |
| suggested_fix | one-line hint or empty | yes |
| fp_reason | why the finding is invalid | only when `false_positive` is true |
| rule_gap | what the rule missed | only when `false_positive` is true |

Invariants:

- A missing `confidence` on a legacy record MUST be read as `medium` — this blocks
  accidental PR eligibility.
- External corrections never flip `false_positive` on an existing line; they land as
  separate disagreement events (append-only discipline, §11).
- A self-invalidated finding auto-emits a `self_false_positive` disagreement event.

Rule-id namespaces: `R01`–`R51` (NL rules; R51 opt-in), `SEC-*`, `BUG-*`, `CC-*`,
`VOCAB-*` (advisory ledger only — never findings), and `UNCLASSIFIED` (sparingly; a
rule-gap signal). New ids need no schema change.

## 3. Fingerprint spec (findings)

The fingerprint is the join key across findings, PR outcomes, and disagreements.

Computed over exactly five components — `repo`, `file`, `rule_id`, `pattern`, `line` —
pipe-joined, **with a mandatory trailing newline folded into the digest**, then hashed
with sha256 and prefixed `sha256:`:

```
fingerprint = "sha256:" + sha256( repo + "|" + file + "|" + rule_id + "|" + pattern + "|" + line + "\n" )
```

Invariants:

- Reimplementations MUST reproduce the trailing newline or digests silently diverge; a
  self-test cross-checks the Python and shell implementations.
- Stable across re-audits; a line shift changes the fingerprint **by design**.
- Consumers needing line-tolerant matching fall back to the loose key
  `(repo, file, rule_id, pattern)` and distinguish identical vs line-shifted persistence.

## 4. Per-audit findings sidecar — `audits/<slug>.findings.jsonl`

The scoring pass emits a machine sidecar next to the human report: strict JSONL, one
finding per line, fields `category` / `rule_id` / `file` / `line` / `severity` /
`confidence` / `evidence` / `penalty` / `pattern` / `description` / `false_positive` /
`suggested_fix` (plus `fp_reason` / `rule_gap` when self-invalidated). The sidecar
carries **no** timestamp, run id, repo, commit SHA, or fingerprint — the aggregation
post-step enriches each line with those before appending to `ledgers/findings.jsonl`.

Contract points:

- The sidecar is rewritten per audit run (not append-only); the ledger append is the
  durable record.
- Malformed sidecar lines are dropped and counted, never fatal; the count is reported via
  the `findings_aggregated` event (§7) — sustained nonzero `invalid_lines` is an
  emission-drift alarm.
- Sidecar completeness telemetry specifically watches for the `confidence` field going
  missing (a past silent drop).

## 5. Disagreement records — `ledgers/disagreements.jsonl`

Append-only JSONL; four event types share the one file. Every record carries `event`,
`timestamp`, and a join handle (a fingerprint, a fingerprint array, or a PR reference).

| Event | Fields | Notes |
|---|---|---|
| `self_false_positive` | repo, fingerprint, rule_id, reason, rule_gap | `rule_gap` is the learning payload |
| `pr_comments_snapshot` | pr, pr_state, comments_hash, fingerprints[], rule_ids[], comments[] | raw thread captured at rejection; each comment body capped at 4000 chars; `comments_hash` = digest of the serialized (capped) comments — the classifier dedupe key |
| `maintainer_rejected` | pr, fingerprints[], rule_ids[], dissent_type, quote, commenter_role, classifier_model, classifier_confidence | `dissent_type` ∈ {intentional_pattern, out_of_scope, style_disagreement, context_missed, rule_disputed}; `commenter_role` ∈ {maintainer, contributor, bot, unknown} — only maintainer weighs high; `classifier_confidence` ∈ {high, medium, low} — low is logged but down-weighted; `quote` capped at 200 chars |
| `maintainer_pushback` | same shape as `maintainer_rejected` | for open or merged-despite-objection PRs; `fingerprints` is an array because bundled PRs need per-finding attribution |
| `downstream_suppression` | repo, commit_sha, rule_id, suppression_type, reason_given (optional), path | `suppression_type` ∈ {suppress, max_penalty, threshold_adjustment, rule_override} |

## 6. Vocab advisory record — `ledgers/vocab-advisories.jsonl`

Append-only JSONL.

| Field | Meaning | Required |
|---|---|---|
| event | constant `"vocab_advisory"` | yes |
| timestamp / audit_run_id / repo / commit_sha | as in findings (§2) | yes |
| fingerprint | vocab-specific digest (below) | yes |
| disposition | enum: `drift` / `likely_drift` / `co_occurrence_drift` / `ambiguous` | yes |
| confidence | `high` / `medium` / `low` cluster confidence | yes |
| terms | alphabetically sorted, length ≥ 2 | yes |
| term_freq | per-term int count | yes |
| term_files | per-term paths, max 5 each | yes |
| files_affected | distinct-file count of the union | yes |
| suggested_canonical | must be a member of `terms` | yes |
| evidence | one-line clustering rationale | yes |
| rule_id | a `VOCAB-*` variant | yes |

Vocab fingerprint — computed over `repo`, the literal string `VOCAB`, the sorted
comma-joined `terms`, and `disposition`, pipe-joined with the same **mandatory trailing
newline** folded into the sha256 digest, result prefixed `sha256:`:

```
fingerprint = "sha256:" + sha256( repo + "|VOCAB|" + sorted_terms_csv + "|" + disposition + "\n" )
```

Stable while the term set is unchanged; a changed cluster is deliberately a new advisory.

Structural invariant: this ledger is **never read by the contribute stage**, so advisories
can never become PRs. Lifecycle events: a scan-skipped event (fewer than 5 NL artifacts)
and a per-scan aggregation event with counts.

## 7. Event-log records — `ledgers/events.jsonl`

Append-only JSONL. Envelope on every record: `timestamp`, `workflow`, `event`, `run_id`,
`run_number`, `data`.

| Event | Data fields | Contract points |
|---|---|---|
| `finding_outcome` | pr, pr_state, fingerprints[], rule_ids[] | `pr_state` ∈ {merged, closed_unmerged, open, stale_90d, cla_blocked}; `stale_90d` is emitted once at 90 days of inactivity and never for cla_blocked PRs |
| `findings_aggregated` | repo, findings, invalid_lines | sustained nonzero `invalid_lines` = emission-drift alarm |
| `finding_verified` | repo, fingerprint, rule_id, file, pattern, outcome, commit_sha_before, commit_sha_after, pr_number | `outcome` ∈ {fixed_and_merged, fixed_applied_separately, fixed_upstream_not_merged, persists_identically, persists_line_shifted}; `pr_number` is normalized to integer-or-null (strings, `#N`, malformed shapes coerced or dropped) so consumers may skip type branching |
| `finding_introduced` | repo, fingerprint, rule_id, file, pattern, severity, commit_sha | NOT appended to `ledgers/findings.jsonl` — avoids double-counting rule reach |
| `finding_amended` | references a prior fingerprint | reserved; no emitter yet |
| `exemplar_published` | repo, exemplar_path, score | emitted after a successful exemplar commit |

Additional lifecycle events (discovery, drift check, aggregation, completion, disclosure
filed/pending, report-generated, proposals_prepared, published / no-narrative, skip
variants) use the same envelope; their `data` payloads are additive per §13.

## 8. Re-audit summary (caller-specified location)

Fields: `repo`; `date`; `original_score` / `reaudit_score` (int or null, parsed from the
reports' labelled score lines); `commit_sha_before` (`"unknown"` fallback) /
`commit_sha_after`; `original_findings_count` / `reaudit_findings_count`;
`original_malformed_count` / `reaudit_malformed_count` (nonzero means the
fixed/introduced tallies may under-count); `verified.<outcome>` (one count per
verified-outcome enum key from §7); `introduced_count`; `fixed_total` (sum of the three
fixed outcomes); `persists_total` (sum of both persists outcomes).

**Skip variant**: only `skipped` + `reason` are present. Consumers MUST omit the re-audit
section entirely — never fabricate it from absent data.

## 9. PR-metadata block

Sentinel-bounded JSON inside an HTML comment, parsed by a defined regex, and it MUST be
the **last** element of the PR body — the tail position protects the closing sentinel from
maintainer edits above it.

Top-level keys (exact set):

- `version` — int, currently `1`.
- `findings` — array of `{ "rule_id": ..., "fingerprint": ... }`; `rule_id` is a
  denormalized convenience, `fingerprint` is the authoritative join to
  `ledgers/findings.jsonl`.

The block is emitted even when `findings` is empty, sentinels verbatim. Rationale
contract: invisible to humans, sentinel-disambiguated, JSON-versioned.

## 10. Exemplar frontmatter — `exemplars/<slug>.md`

| Field | Meaning | Required |
|---|---|---|
| slug | hyphen-substituted repo key | yes |
| repo | `owner/name` | yes |
| audited | audit date | yes |
| commit_sha | audited HEAD from the registry | yes |
| score | numeric audit score | yes |
| exemplifies | list of `R##` rule ids the body evidences | yes |

`exemplifies` is the join key consumed by rule-health (per-rule exemplar counts + slugs;
high-hits-zero-exemplar rules get surfaced). Threshold contract: exemplar promotion at
score ≥ 90 (default, configurable) and security not blocked.

The exemplar gallery README is deterministic machine output — **never hand-edit it**; the
generator overwrites it wholesale. Citation blocks in the rules catalog are
marker-anchored for idempotent in-place update/removal; hand edits inside the markers are
overwritten.

## 11. Append-only designations

Append-only — a correction is a **superseding event appended later, never an edit** of an
existing line:

- `ledgers/findings.jsonl`
- `ledgers/disagreements.jsonl`
- `ledgers/events.jsonl`
- `ledgers/vocab-advisories.jsonl`

Rewritten/mutated (not append-only): the per-audit report + findings sidecar, the
re-audit report/sidecar/diff table, the vocab-drift report + sidecar, the rebuilt
feedback summary, `registry/repos.json` (mutated in place via the atomic writer), and
exemplar files + the auto-generated gallery.

## 12. Learning query + derived metrics

Join: findings ⋈ outcome events ⋈ verified events ⋈ disagreements — all on
`fingerprint`, grouped by `rule_id`.

Per-rule metrics:

- `hits / repos_audited` — reach
- `merged / contributed` — intent precision
- `verified_fixed / verified_total` — effect precision; the stricter, more load-bearing
  signal, weighted above merged
- `self_fp / hits`
- `maintainer_rejected / contributed`
- `downstream_suppression / deployments`
- median `dissent_type`

Rule states: `healthy` / `noisy` / `dormant` / `disputed`.

## 13. Versioning invariants

- **Additive** changes (a new optional field, event type, or enum variant): document here,
  no version bump.
- **Breaking** changes: bump the PR-metadata-block `version`; JSONL ledgers get a one-shot
  migration rewrite — mixed schemas in one file are forbidden.
- **Deprecated** fields keep being emitted for ≥ 30 days after consumers stop reading
  them.
- Registry state is excluded from E8.5's migration by design (§1): the human-performed
  bootstrap is the sole origin of an empty registry.
