# vibe-31 worksheet — hand-derived expectations for `/vibe-suite:test`

Authored BEFORE the specs, the command, and the agent (T0 of the frozen plan). Every
determination cites its governing decision (D1–D9) or text (F4.5, §5.0,
skills/testing/SKILL.md, the disposition map).

## The frozen 14-agent table (§5.0; min_score per D4 = the project Strict threshold)

| Spec file | Artifact | Exists @ befb954 | Source spec | min_score |
|---|---|---|---|---|
| recon.spec.md | agents/recon.md | no (RED) | F3.x recon | 80 |
| architecture.spec.md | agents/architecture.md | no (RED) | F3.x architecture | 80 |
| error-handling.spec.md | agents/error-handling.md | no (RED) | F3.x error-handling | 80 |
| security.spec.md | agents/security.md | no (RED) | F3.x security | 80 |
| testing.spec.md | agents/testing.md | no (RED) | F3.x testing | 80 |
| edge-cases.spec.md | agents/edge-cases.md | no (RED) | F3.x edge-cases | 80 |
| scanner.spec.md | agents/scanner.md | yes | shipped text (F4.1) | 80 |
| scorer.spec.md | agents/scorer.md | yes | shipped text (F4.2) | 80 |
| vague-scanner.spec.md | agents/vague-scanner.md | yes | shipped text (F4.2) | 80 |
| checker.spec.md | agents/checker.md | yes | shipped text (F4.3) | 80 |
| tester.spec.md | agents/tester.md | no at T2a, yes at T2b | F4.5 (spec-before-artifact) | 80 |
| vocab-drift-scanner.spec.md | agents/vocab-drift-scanner.md | no (RED) | F4.6 | 80 |
| security-scanner.spec.md | agents/security-scanner.md | no (RED) | F5.1/E3.9 | 80 |
| spec-researcher.spec.md | agents/spec-researcher.md | no (RED) | F4.7/E3.8 | 80 |

Current-state run expectation (worksheet-only, NOT a test assertion — D9): the suite's
own `.vibe-test/` run reports NINE RED specs (the six F3 review agents,
vocab-drift-scanner, security-scanner, spec-researcher) — the F4.5 TDD start state.
The five stage-delivered artifacts (scanner, scorer, vague-scanner, checker, tester)
resolve by name.

## Fixtures

- `missing-artifact/.vibe-test/ghost.spec.md` — the DURABLE missing-artifact contract:
  `artifact: agents/ghost.md` is absent by construction and never to be created.
  Expected runtime role (D7): per-spec FAIL, detail `artifact missing (RED)`, RED-items
  entry naming agents/ghost.md.
- `legacy/` — SELF-CONTAINED legacy root: `.nlpm-test/legacy-sample.spec.md` (current
  3-field schema) + `agents/local.md` (minimal agent, description present). With
  `legacy/` as the runner root: legacy read-compat discovers the spec, the artifact
  resolves, the spec is evaluated; the spec is never renamed (D2).

## Contract-assertion inventory (pinned by tests/test_vibe_test_specs.py)

Command (D1, D2, D3, D6, D7): report header `Vibe Suite Test Report`; table columns
Spec|Artifact|Result|Details; `N/M checks`; overall percent line; `RED items (fix
these):`; batches of ≤3 in sorted order; the legacy read-compat sentence + collision
rule (new dir wins, legacy reported skipped); missing→RED rule; the D3 line formats —
canonical trigger line (both polarities), separate indented `confidence:` line,
canonical score line, frontmatter missing/style lines, output line, both rule-direction
lines, `artifact missing (RED)` line; provenance line naming skills/testing/SKILL.md.
Agent (D5): five lanes named; trigger checks PREDICTED, never executed; artifact
existence checked BEFORE delegation; engine invocation exactly `agent\x1f<rel>\x00` on
stdin to `"${CLAUDE_PLUGIN_ROOT}/scripts/score_engine.py" --root <root>` (no positional
form); parse `files[0].score`; IGNORE `files[0].verdict`; compare raw score to the
spec's `min_score`; engine exit 2 fails that spec alone, batch continues.
