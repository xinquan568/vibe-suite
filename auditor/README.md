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
  --repo xinquan568/vibe-suite`; (3) revoke the old token in the issuing account's settings;
  (4) re-run the E8.7 preflight (or, until it exists, a `track` dry run) to prove the new token
  works; (5) note the rotation date in the ops log on `auditor-data` (`ledgers/`), not here.
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
| `OPENAI_API_KEY` | optional — absence engages the documented SVG fallback |

### Re-provisioning notes

Every step above is idempotent as written: label creation targets only the missing set; the
settings PATCH/PUT/POST calls are no-ops (or 409) when already enabled; the branch push is skipped
when the ref exists and never forced. A full re-provision is therefore safe to run end to end, and
partial state is always advanced, never rewound.
