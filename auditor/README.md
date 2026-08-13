# `auditor/` — Audit pipeline unit

The deployable audit unit — workflows, rulebook and runbook. Its operational
secrets live only in the GitHub Actions environment, never in this directory.

## Provisioning runbook (E8.1)

The Category-10 deployment prerequisites for `xinquan568/vibe-suite` (decisions D4 and D9), as
provisioned on 2026-08-06. Every row below is checkable by the command given with it; E8.7's
`auditor-integration-test` preflight re-checks the required rows mechanically before the first
external audit.

### Lifecycle labels (the F10.1 state machine)

Seven labels drive the labeled-issue pipeline, one per state, with a human approval gate between
every automated stage:

| # | Label | Pipeline state it marks |
|---|---|---|
| 1 | `audit-candidate` | repo discovered, awaiting triage |
| 2 | `audit-ready` | approved for audit |
| 3 | `audit-complete` | audit done, report filed |
| 4 | `contribute-approved` | human-approved for contribution PRs |
| 5 | `prs-submitted` | contribution PRs open upstream |
| 6 | `case-study-ready` | outcomes merged, case study pending |
| 7 | `complete` | lifecycle finished |

All seven share color `#5319e7` (distinct from the `area:*`/`stage:*`/`size:*` families). Only the
*names* are normative; colors and descriptions are house style.

- Verify: `gh label list --repo xinquan568/vibe-suite --limit 100 --json name` — the seven names
  above must all be present (set membership, not a count: the repo carries ~30 other labels).
- Re-provision: `gh label create <name> --repo xinquan568/vibe-suite --color 5319e7
  --description "<state role>"` for exactly the missing names. Creation is idempotent this way; an
  existing label is never recolored or deleted by provisioning.

### Repository settings

| Setting | Required state | Verify |
|---|---|---|
| Issues | enabled | `gh api repos/xinquan568/vibe-suite --jq .has_issues` → `true` |
| Actions | enabled | `gh api repos/xinquan568/vibe-suite/actions/permissions --jq .enabled` → `true` |
| Pages | enabled, `workflow` build type | `gh api repos/xinquan568/vibe-suite/pages --jq .build_type` → `workflow` |

- Restore paths: issues — `gh api -X PATCH repos/xinquan568/vibe-suite -F has_issues=true`;
  Actions — `gh api -X PUT repos/xinquan568/vibe-suite/actions/permissions -F enabled=true`;
  Pages — `gh api -X POST repos/xinquan568/vibe-suite/pages -f build_type=workflow` (a 409 means
  already enabled). Pages was enabled 2026-08-06 with the `workflow` build type before any site
  deployment exists; the site itself (`https://xinquan568.github.io/vibe-suite/`) stays empty until
  E8.4's `deploy-site` workflow publishes it.
- **Actions minutes** are an account-level resource no repo API reports; the checklist row is
  satisfied operationally (workflows run) and re-proven by every CI run. E8.7's preflight is the
  mechanical check.

### The `auditor-data` branch (D9)

Ops data lives on the orphan branch `auditor-data` — no shared history with `main` — so plugin
installs stay lean (merge proposal §7A row 9). Seeded 2026-08-06 with a single root `README.md`
(commit `e0cd207`); the data categories (`reports/`, `exemplars/`, `audits/`, `ledgers/`,
`articles/`) and the reserved provenance prefix `.vibe-suite-migration/` are managed by
`tools/migrate-auditor-data.sh`, which arrives at them only through its own provenance checks and
refuses non-regular files on managed paths. Ops data arrives via E8.5's migration run
(count+hash-verified, idempotent).

- Verify: `git ls-remote origin auditor-data` → one ref.
- Re-provision (only if the ref is absent): create an orphan branch whose root commit carries the
  sentinel `README.md` only, and push **without force**. An existing ref is never rewritten by
  provisioning; `tools/migrate-auditor-data.sh` also creates the branch itself on a first run if it
  is missing, so either path is safe.

#### E8.5 execution record (2026-08-13)

§7A row 9 executed for real (vibe-62), operator-approved, from the nlpm source corpus:

- **Invocation**: `tools/migrate-auditor-data.sh <auditor-repo-remote> --source <nlpm-source-tree>`
  (branch defaulted to `auditor-data`).
- **Corpus**: `corpus: 1287 file(s) across 5 categories` — 642 `reports/`, 96 `exemplars/`,
  496 `audits/`, 49 `articles/`, 4 `ledgers/` files (the merge proposal's "exemplars (95)"
  was a dated snapshot; the tool's own enumeration is the binding count).
  `disclosures-pending/` was excluded by the tool's corpus definition and is absent from the
  pushed tree (verified: zero matches in `git ls-tree -r`).
- **Complete copy**: `published 1287 new file(s)` … `verified 1287 file(s) against
  auditor-data by content address` — every published blob compared against the SHA-256
  manifest (`.vibe-suite-migration/manifest.sha256`; provenance in
  `.vibe-suite-migration/provenance.json`). Exit 0.
- **Tips**: before `8d8d85a` (sentinel + `registry/repos.json`) → after `72ab8f0`. The two
  pre-existing blobs are byte-identical before and after (`README.md` `68903f1`,
  `registry/repos.json` `03be823`).
- **Idempotent re-run**: second invocation → `already complete — no commit`, exit 0, tip
  unchanged at `72ab8f0`.
- **Originals untouched**: whole-source digest (1,531 files, per-file SHA-256, digest of
  digests `f8631b5…`) identical before and after both runs.
- **Rollback discipline**: the tool's nothing-was-changed guarantee applies to its `exit 3`
  refusals only (they fire before staging). After any OTHER failure, whether a push
  happened is unknown until checked — so every recovery, without exception, first stops
  for the operator, then fetches and compares the remote tip against the recorded
  baseline. Three outcomes: (1) tip unchanged — nothing landed; fix and re-run (safe by
  idempotence); (2) the migration commit is the tip — the baseline tip may be restored,
  only with `--force-with-lease` (the lease fails if anything has since landed); (3) any
  commit landed after the migration (e.g. a registry write) — never move the tip; revert
  the migration commit so intervening state survives. Branch deletion is a
  first-run/missing-branch remedy only — the live branch carries pipeline state the
  pipeline owns.

### Actions secrets

Secret *values* live only in the GitHub Actions environment — never in this repository, its
branches, or this runbook (anti-pattern rule 6).

| Secret | Used by | Required? | Absent ⇒ |
|---|---|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | every model-judged stage (audit, case-study, refine-rules) | required | those stages fail preflight naming the secret — no silent skip |
| `PAT_TOKEN` | contribute (fork/branch/PR), track | required for contribution | audit-only mode: the pipeline stops at `audit-complete`; doctor/README state why |
| `OPENAI_API_KEY` | case-study cover generation | optional | cover degrades to a templated SVG; the article still publishes (AC-8 tests this path) |

- Verify presence: `gh secret list --repo xinquan568/vibe-suite` (both required names present;
  installed 2026-08-06). Presence proves neither validity nor scope — E8.7's preflight exercises
  both.
- Install/rotate: `gh secret set <NAME> --repo xinquan568/vibe-suite` (value prompted or piped —
  never written to disk or shell history).

#### `PAT_TOKEN` rotation

- **Scope:** classic PAT with `public_repo` only (or a fine-grained token limited to public-repo
  contents+PR write). Nothing wider: the contribution surface is fork/branch/PR on public repos.
- **Cadence:** rotate every 90 days, and immediately on any suspected exposure or when a holder
  leaves.
- **Steps:** (1) create the replacement token with the same scope; (2) `gh secret set PAT_TOKEN
  --repo xinquan568/vibe-suite`; (3) prove the replacement works — re-run the E8.7 preflight (or,
  until it exists, a `track` dry run); (4) only after that check succeeds, revoke the old token in
  the issuing account's settings — until then it remains the rollback credential; (5) note the
  rotation date in the ops log on `auditor-data` (`ledgers/`), not here. A rotation that revoked
  first would have no fallback if the replacement turned out invalid or mis-scoped.
- A wrong-scope token is indistinguishable from a valid one by presence checks; only the preflight
  catches it.

### AC-8 preflight checklist map

What E8.7's preflight must find, and the command that proves each row today:

| Checklist row | Proven by |
|---|---|
| Seven lifecycle labels | label-list set membership (above) |
| Issues enabled | repo `has_issues` |
| Actions enabled (+minutes) | actions permissions endpoint; minutes prove themselves on any run |
| Pages enabled | pages endpoint, `build_type: workflow` |
| `auditor-data` branch | `ls-remote` ref |
| `CLAUDE_CODE_OAUTH_TOKEN` present | secret list |
| `PAT_TOKEN` present (+`public_repo` scope) | secret list; scope only via preflight exercise |
| `OPENAI_API_KEY` | optional — absence engages the documented SVG fallback; the full tier executes the fallback with the key unbound and REQUIRES it to pass |
| F10.1 security checklist signed | `auditor/SECURITY-CHECKLIST.md` — every row checked and a dated `Signed-off-by:` line; the unit tier refuses by name until the operator signs |

The sign-off is an operator act: the pipeline scaffolds `auditor/SECURITY-CHECKLIST.md`
unchecked and can only verify the durable record — AC-8 cannot go green before the
operator has attested the rows (PAT scope, rotation doc, injection separation, audit
token scope, no secret egress) and signed with a name and an ISO date.

### Re-provisioning notes

Every step above is idempotent as written: label creation targets only the missing set; the
settings PATCH/PUT/POST calls are no-ops (or 409) when already enabled; the branch push is skipped
when the ref exists and never forced. A full re-provision is therefore safe to run end to end, and
partial state is always advanced, never rewound.

## Pipeline operation (E8.2)

The audit-and-contribute pipeline (F10.1): eighteen workflows staged under `auditor/workflows/`,
**inert by design** — GitHub runs workflows only from `.github/workflows/`, and activation is a
deliberate later act. E8.7 activated `auditor-integration-test` (2026-08-13): a live COPY at
`.github/workflows/auditor-integration-test.yml`, held byte-identical to the staged source by
`tests/test_auditor_fixture.py` (the codex-mirror discipline — the staged file stays the edited,
lint-covered source; edit it and re-copy). Its tiers audit the in-repo defect fixture at
`auditor/test-fixture/` (planted defects pinned by `census.json`). The other seventeen remain
staged-only.
Eleven of the eighteen carry cron triggers and twelve react to issue events; none may go live
before the helper scripts (E8.3), the migrated ops data (E8.5) and the AC-8 preflight (E8.7) exist.

### The state machine

`audit-candidate` → `audit-ready` → `audit-complete` → `contribute-approved` → `prs-submitted` →
`case-study-ready` → `complete`, with a **human approval gate between every automated stage**:
`discover` files candidates; a human adds `audit-ready`; `audit` scores and exits
`audit-complete`; a human adds `contribute-approved` after reading the report; `contribute`
submits capped, gated PRs and exits `prs-submitted`; `track` (cron) records outcomes and promotes
to `case-study-ready`; `case-study` writes (or worthiness-skips) the article and closes at
`complete`. `daily-report` (cron) is a pure observer.

### Code/data topology (D9)

Every data-writing workflow uses a dual checkout: code from `main` at the workspace root, the
`auditor-data` branch at `_data/`. Data categories live flattened on the data branch —
`reports/ audits/ ledgers/ articles/ exemplars/` plus `registry/repos.json` — with the four
append-only ledgers under `ledgers/` (`findings.jsonl`, `disagreements.jsonl`, `events.jsonl`,
`vocab-advisories.jsonl`). Contracts: `auditor/SCHEMAS.md`.

### Registry bootstrap (performed 2026-08-06)

`registry/repos.json` is pipeline *state*, deliberately excluded from E8.5's migration; stages
**refuse with `REFUSE:registry-missing`** when it is absent and never create it silently. The
bootstrap (empty shape per SCHEMAS.md, `{"repos": {}}`) was committed to `auditor-data` by this
item — idempotent: an existing file is never rewritten by re-provisioning. Re-run shape: check
`git ls-remote origin auditor-data`, fetch the branch, add the file only if absent, push without
force.

### Helper scripts

`auditor/scripts/` holds exactly thirty helpers: twenty-one Python at mode `100644` and nine
shell at `100755`. The set is CLOSED — `tests/test_auditor_workflows.py` asserts the names on
disk equal the declared names in both directions, so an extra file fails as loudly as a missing
one, and a workflow referencing a name outside the set fails the lint.

Workflows call them directly. There is no existence check: a guard that can be false skips the
helper silently, which is how `build-exemplar-gallery.sh` was invoked for months against a
helper that is actually `.py`, and how every `[ -x ]` guard on a Python helper stayed false
forever because Python helpers are not executable by contract. The lint enforces that a
reference names a declared helper, that its predicate can be true for its mode, and that its
interpreter matches its extension.

Python helpers are run with `python3`, shell helpers with `bash`; neither relies on the
executable bit.

### Orphaned forks — manual cleanup (E8.2b)

The contribution engine creates a fork under the bot account before opening a PR, then
re-confirms four things: the fork resolves, it *is* a fork, its owner is the PAT's own login,
and its parent is the audited repository. If any check fails the run **refuses** — and
deliberately **does not delete the fork**.

Deleting a repository under a third-party account is not an action this pipeline takes on its
own judgement (operator decision, 2026-08-07). An automated delete that misfires is
unrecoverable and is visible to the account owner; a fork left in place is neither. So the
engine records the failure and hands it to a human.

**Finding them.** Each failure appends an `orphaned_fork` event to `ledgers/events.jsonl` on
the `auditor-data` branch (contract: `auditor/SCHEMAS.md` §7):

```bash
git fetch origin auditor-data:auditor-data
git show auditor-data:ledgers/events.jsonl \
  | jq -c 'select(.event == "orphaned_fork") | .data'
```

Each record carries `repo`, `fork_slug`, `owner`, `created_at` and `invariant_failed` — the
last naming which of the four checks failed (`resolves`, `is_fork`, `owner_matches`,
`parent_matches`).

**Deciding what to do.** `invariant_failed` tells you what to expect:

| `invariant_failed` | Most likely cause | Usual action |
|---|---|---|
| `resolves` | creation raced, or the API returned before the fork was queryable | re-check by hand; often nothing to clean up |
| `is_fork` | a repository of that name already existed under the bot account | rename or remove **that** repo, not a fork |
| `owner_matches` | `PAT_TOKEN` belongs to a different account than expected | fix the token or the expectation first — a fork may not exist at all |
| `parent_matches` | the fork points at a different upstream | inspect before deleting; it may be someone's legitimate work |

**Cleaning up.** Only after deciding the fork is genuinely the pipeline's own stray:

```bash
gh repo view  <fork_slug>          # confirm what it is, and that it holds no unique work
gh repo delete <fork_slug>          # interactive confirmation; never scripted in bulk
```

Do not script this across many records. The whole reason the engine refuses to delete is that
"this looks like ours" is a judgement, and it is one a human makes per fork.

### Secrets behavior (recap; provisioning above)

`PAT_TOKEN` absent → audit-only mode (the pipeline stops at `audit-complete`). `OPENAI_API_KEY`
absent → the case-study cover degrades to a templated SVG and the article still publishes.
`CLAUDE_CODE_OAUTH_TOKEN` absent → every model-judged stage fails preflight naming the secret.
The contribute workflow separates the model job from the PAT-bearing job; no job holds both.
