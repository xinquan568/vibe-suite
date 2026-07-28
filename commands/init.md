---
description: "Set up vibe-suite in this project: asks four questions, migrates any legacy cc-suite/nlpm stores per §7A without touching them, then installs the cross-tool bridge (AGENTS.md and imports, .codex/, .mcp.json, gitignore block, baseline history). Idempotent — a second run is a no-op. No arguments."
argument-hint: ""
---

# /vibe-suite:init — interactive project setup

One command sets up the bridge **and** the quality baseline **and** migrates whatever cc-suite or
nlpm left behind. It never deletes or rewrites a legacy store: it copies or derives, leaves the
original untouched, and where both stores exist the new one wins. Rollback is deleting the new store.

## What to do

### 1. Ask the five questions

Use **AskUserQuestion**, one call, five questions:

| Question | Options | Becomes |
|---|---|---|
| What Codex effort should commands default to? | `low` · `medium` · `high` | `--effort` |
| What sandbox should Codex run under? | `read-only` · `workspace-write` · `danger-full-access` | `--sandbox` |
| How deep should audits run by default? | `mini` (fast) · `full` | `--audit-depth` |
| How strict is the score gate? | `relaxed` (60) · `standard` (70) · `strict` (80) | `--strictness` |
| Any paths to skip? | free text, optional | `--skip` |

**No question here names a model.** F1.1 asks for Codex *effort* and *sandbox*, and both are enums in
`.vibe-suite.md`'s schema. Per P9/D6 a model question would ask which **tier** to trust and never
offer a versioned id — but the suite stores no model key at all, so the honest thing is not to ask.
The engines run on their own configured defaults.

### 2. Run it

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/init.sh" \
  --effort <low|medium|high> [--sandbox <sandbox>] \
  --audit-depth <mini|full> --strictness <relaxed|standard|strict> [--skip "a/**,b/**"]
```

### 3. If it exits 3, a decision is required

Exit 3 means a §7A helper found something only the user can settle, and **nothing was written**. A
report is in `.vibe-suite-state/`. Read it, ask **one** AskUserQuestion, and re-run with the answer
appended — the flags accumulate, and init re-runs from the start relying on each helper's own
idempotence.

| Report | Ask | Accept | Decline |
|---|---|---|---|
| `migration-conflicts.json` | which source wins, **per key** | `--resolve-config '{"<key>":"cc-suite"\|"nlpm"}'` | `--decline-config` |
| row 5 disagreement | which `stopReviewGate` value | `--resolve-state true\|false` | `--decline-state` |
| row 6 sentinels | migrate cc-suite registrations? | `--confirm-sentinels yes` | `--confirm-sentinels no` |

**A resolution must cover every key the report lists** — a partial mapping is an error, because "ask
once" bounds how often the user is interrupted, not how many keys one answer covers.

**Declining is not failing.** A declined row is skipped, its legacy store stays exactly as it was, and
the rest of the install proceeds. `/vibe-suite:doctor` reports what remains.

`--resolve-state false` means *the user chose `false`*. `--decline-state` means *the user was asked
and declined*. They are different states and the flags keep them apart.

### 4. Report what happened

Name the artefacts written, any row skipped and why, and any warning the survey emitted (leftover
`nlpm-reports/`, legacy `.nlpm-test/` specs, source plugins still installed).

## Notes

- **Non-interactive** (`--non-interactive`) surfaces exit 3 rather than asking. A conflict without a
  human is not resolvable and §7A forbids guessing.
- **Idempotent.** A second run changes nothing — same content, modes and mtimes.
- **Provenance** is written once, before the first mutation, and holds the pre-image of every target
  so `/vibe-suite:unbridge` can restore it. A re-run never overwrites it.
