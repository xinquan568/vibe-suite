# NLPM Audit: xiaolai/nlpm-for-claude

Score: 100/100
Security: CLEAR
Files audited: 36
Strategy: self_audit

## Summary

This is NLPM's audit of itself. The same scorer + checker + security pipeline that runs against external Claude Code plugins is applied here. The result represents how the project ranks against its own published rule set.

| Dimension | Result |
|-----------|--------|
| Quality score | 100/100 (zero penalties applied) |
| Security scan | CLEAR (no critical or high patterns; one MCP server reference, allowed; hooks fail-open) |
| Cross-component | Clean (`/nlpm:check` reports zero broken references, zero orphans, zero contradictions) |
| Vocabulary discipline (R51) | Enabled, zero drift findings — NLPM dogfoods its own canonical registry |
| Unit tests | 23/23 pass (`python3 -m unittest tests.test_nlpm_check`) |
| Standalone validator | `bin/nlpm-check` clean |

## Methodology

The score is computed by `nlpm:scorer` (the same agent applied to every external repo in the auditor pipeline). Penalties enumerated in `skills/nlpm/scoring/SKILL.md` are deterministic; ties are broken by the calibration examples in that same skill.

The cross-component check is the deterministic `bin/nlpm-check` plus `nlpm:checker` for behavioral consistency. The security scan follows `agents/security-scanner.md` against the four signature classes (eval, curl|sh, credential exfil, postinstall hooks).

## R51 — vocabulary discipline

NLPM ships its own vocabulary skill at `skills/nlpm/vocabulary/` and opts itself in via `.claude/nlpm.local.md`:

```yaml
rule_overrides:
  R51:
    enabled: true
    vocabulary_skill: skills/nlpm/vocabulary/
```

Drift findings: 0 across all 36 artifacts.

## What's audited

| Category | Count |
|----------|-------|
| Commands | 11 |
| Agents | 7 |
| Skills | 14 (incl. writing-*, conventions, scoring, rules, vocabulary, patterns) |
| Manifests + config (plugin.json, hooks.json) | 2 |
| CLAUDE.md / README.md / standalone surfaces | 2 |

Total: 36 NL programming artifacts.

## What's NOT included in this score

- `auditor/` directory (workflow definitions, schemas, scripts) — operational tooling, not user-facing NL artifacts
- `analysis/` directory (design rationale, principles) — internal docs
- `templates/` directory (site templates, pre-commit hook scaffolds) — author-facing scaffolding
- `bin/` Python binaries — not NL artifacts (they're code that processes NL artifacts)

The rule set defines NL artifacts as the markdown files Claude Code consumes — commands, agents, skills, rules, hooks, CLAUDE.md. Code that NL artifacts dispatch is out of scope by design.

## Findings

Zero findings. The full breakdown (per-file scores at 100, penalties: none) lives in the per-audit sidecar at `auditor/audits/xiaolai-nlpm-for-claude.findings.jsonl` (empty).

## Provenance

- Commit SHA: `f9535b41631884de027886a3dc8aa4f027a46abc`
- Audited at: see the `discovered` field in `auditor/registry/repos.json`
- Method: self-audit (the project audits itself with the same pipeline it audits others)
- Discovery: `self` (not pulled from the standard discovery cron)

The "100/100" claim is checkable: clone the repo at the commit SHA, run `python3 bin/nlpm-check` and `python3 -m unittest tests.test_nlpm_check`. The deterministic surface is fully reproducible. The judgment-heavy surface (the scorer agent) is reproducible by anyone with Claude Code who runs `/nlpm:score ./` against the same tree.
