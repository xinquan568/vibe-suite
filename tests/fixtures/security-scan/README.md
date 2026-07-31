# vibe-34 worksheet — hand-derived expectations for `/vibe-suite:security-scan`

Authored before the artifacts, from `skills/security/SKILL.md`, F5.1, F9.1, F9.2 and F9.7.

## The four capping rules, one worked example each

| Rule | Seed | Outcome |
|---|---|---|
| `.md` cap | `commands/notes.md:5` carries a Critical pipe-to-shell signature | **reported at Low** — capped, NOT dropped |
| echo drop | `scripts/install.sh:6` — the signature inside `echo "…"` | dropped |
| heredoc drop | `scripts/install.sh:10` — the signature inside a quoted heredoc | dropped |
| lockfile suppression | `package.json:3` `"left-pad": "*"` with `package-lock.json` present | suppressed entirely |

Echo and heredoc are separate rules with separate seeds: a scanner that dropped quoted
strings but not heredoc bodies would pass a test that seeded only one.

**The pinning distinction is half-seeded, and only half.** An unpinned `package.json`
dependency is advisory and is suppressed outright once a lockfile exists; the fixture seeds
that half at `package.json:3`, and it is not reported. The counterpart — an unpinned
`.mcp.json` server IS PR-worthy — is **not** seeded, because the MCP family's six named
checks contain no unpinned-server name, so such a finding could carry no permitted
`Pattern`. Seeding it would force the oracle to record an unnameable finding.

## The banner ladder, over four severity mixtures

Applied first-match-wins, because the bands overlap otherwise:

| Findings present | Recommendation | Banner |
|---|---|---|
| Low only | PASS | `SECURITY GATE: PASSED` |
| Medium only | REVIEW | `SECURITY GATE: REVIEW NEEDED` |
| Medium + Low | REVIEW | `SECURITY GATE: REVIEW NEEDED` |
| any Critical or High | BLOCK | `SECURITY GATE: BLOCKED` |

A Medium-only report satisfies both "no Critical or High" and "only Medium", which is why
the ladder is ordered rather than a set of independent conditions.

## The composite report — seven parts

1. `## [Agent: vibe-suite:security-scanner] Findings` — six fields plus an Exploit scenario;
2. severity counts; 3. the 6-column `### Findings` summary; 4. surface inventory;
5. `Risk level`; 6. exactly one `Recommendation:`; 7. the zero form below.

**Rendering consistency.** Parts 1 and 3 render one finding set, so `Observation` is written
`<Pattern name> — <prose>`: `File`/`Line` split `File path:line`, `Pattern` is the text
before the em-dash, `Description` the text after. `Evidence`, `Proposed change`, `Tradeoff`
and `Exploit scenario` appear only in part 1 — the table is a summary and drops them.

**The `[GOOD]` sentinel row** is exempt from those derivations, because a `[GOOD]` entry has
no location and no pattern:

```
| 1 | [GOOD] | — | — | — | <what was checked and found clean> |
```

Only a `[GOOD]` row may carry `—` there. Zero counts, `Risk level: CLEAR`,
`Recommendation: PASS`. Zero-surfaces and surfaces-but-no-findings differ only in part 4.

**Risk level** grades the highest severity present; the gate is coarser:

| Highest severity | Risk level | Recommendation |
|---|---|---|
| none | CLEAR | PASS |
| Low | LOW | PASS |
| Medium | MEDIUM | REVIEW |
| High | HIGH | BLOCK |
| Critical | CRITICAL | BLOCK |

## The permitted pattern names — 39, parsed from the skill

18 pattern-database rows + 6 MCP rows + 5 hook-safety + 7 dependency + 3 prompt-injection.
The last fifteen were unnamed prose bullets; this item names them **in the skill**, so the
set stays derivable from the single pattern DB rather than restated here. The tests parse
the skill and compare; this worksheet records the count, not the list.

## The hook's classification boundary — 24 representatives

One path per F9.3 A/B/F pattern class, plus C and E controls and one source-only case. The
source's eight patterns and F9.3's categories **overlap — neither contains the other**, and
exactness is claimed only over these 24 rows.

*Matched (13):* `.claude-plugin/plugin.json`, `commands/x.md`, `commands/shared/x.md`,
`agents/a.md`, `skills/s/SKILL.md`, `hooks/hooks.json`, `.mcp.json`, `CLAUDE.md`,
`.claude/CLAUDE.md`, `pkg/CLAUDE.md`, `.claude/rules/r.md`, `.claude/commands/u.md`,
`vendor/thirdparty/commands/x.md`.

*Unmatched (11):* `.claude-plugin/marketplace.json`, `.lsp.json`, `settings.json`,
`.claude/settings.json`, `.claude/settings.local.json`, `.claude/x.local.md`,
`~/.claude/projects/p/memory/topic.md`, `~/.claude/projects/p/memory/MEMORY.md`,
`prompts/x.md`, `docs/x.md`, `README.md`.

`vendor/thirdparty/commands/x.md` matches because shell case-pattern `*` spans `/` — the
same property that makes `*/commands/*.md` cover nested paths and made the source's old
`**` alternatives unreachable. Eight A/B/F classes are unmatched; that is a recorded
decision, not an oversight.

## Fixture and oracle

`seeded-plugin/` seeds each severity band and each capping rule.
`expected-findings.md` is the hand-authored oracle; `recorded-scan.md` is a manual run under
a provenance header. The tests compare them one-to-one — every expected finding present with
its post-capping severity, no extras, and the three suppressions asserted absent. Live
scanning is the agent's judgment lane: CI makes no model call.
