# AC-3 acceptance runbook — `/vibe-suite:nl-audit`

The seeded-defect fixtures in this directory are the AC-3 corpus for E4.1 (vibe-35). This file is how
an operator turns them into a verdict.

**What CI already checks, so you do not have to.** `tests/test_nl_audit_fixtures.py` verifies the
corpus itself — that all six fixtures exist with exactly the class sets merge-proposal line 627
enumerates, that every class is attributed to the dimension an independent oracle assigns it, that
each artifact-type fixture seeds both a mini-member and a full-only class, and that every declared
floor equals `ceil(0.75 × N)`. `tests/test_nl_audit_acceptance.py` verifies the **gate** —
`tools/nl-audit-acceptance.py` — by proving each of its clauses can fail.

**What CI cannot check.** A live judgment engine's output. CI dispatches no engine, so the detection
rate itself is measured here, by you, once per release or whenever the auditing skill changes.

## The two steps

### 1. In a Claude Code session, on a live lane

```
/vibe-suite:nl-audit --type skill tests/fixtures/nl-audit/defective-skill --full
```

Then ask the session to write the run's findings to a file **with the Write tool** — not by shell
redirection, which cannot capture a slash command's output — in this shape:

```json
{
  "run":      { "type": "skill", "depth": "full", "engine": "codex" },
  "findings": [ { "class": "missing name", "dimension": "D0" } ]
}
```

- `class` matches a seeded class id from that fixture's `seeded-defects.json`. Matching ignores case
  and punctuation, so `>500-line body` and `over 500 line body` are the same class.
- `dimension` is the dimension the finding was attributed to — `D0`–`D6`, or an `A1`–`E3` check-set id
  for `--type repo`.
- `run.engine` is recorded for provenance. No clause reads it, but line 627 requires the outcome
  contract to hold on **each** engine lane, and a verdict with no lane recorded cannot be attributed
  to one.
- A class the fixture never seeded is **rejected**, not ignored: an invented finding would otherwise
  inflate the detection rate.

### 2. In a shell

```bash
python3 tools/nl-audit-acceptance.py tests/fixtures/nl-audit/defective-skill \
  --full --findings /tmp/nl-audit-skill-full.json
```

Exit `0` passes, `1` names the clause that failed, `2` means the record could not be graded at all.
Add `--json` for a machine-readable verdict.

## The twelve runs

Six fixtures × two depths. Run all twelve; a release claim of AC-3 rests on the full set.

| Fixture | `--type` | Classes | `--full` floor | `--mini` checks |
|---|---|---|---|---|
| `defective-skill` | `skill` | 10 | 8 | only D0–D3 reported |
| `defective-command` | `command` | 7 | 6 | only D0–D3 reported |
| `defective-agent` | `agent` | 7 | 6 | only D0–D3 reported |
| `defective-rules` | `rules` | 7 | 6 | only D0–D3 reported |
| `defective-plugin` | `plugin` | 7 | 6 | only D0, D1, D3, D6 reported |
| `mixed-repo` | `repo` | 8 | 6 | no exclusion defined for this type |

`defective-plugin`'s mini set is **irregular** — D2 Security Posture is full-only and D6
Maintainability is mini+full. A mini run of that fixture reporting D2 is a failure, not thoroughness.

`--type plugin` dispatches no engine at all (local analysis, F4.9), so its two runs exercise the
in-session path regardless of which lane is configured.

## Which clause applies at which depth

- `--full`: **detection rate** (≥ floor) and **attribution** (every reported class under its seeded
  dimension).
- `--mini`: **attribution** and **mini-membership exclusion**. The detection floor deliberately does
  **not** apply — a mini audit covers fewer dimensions by design, so grading it against the full-run
  floor would fail every correct mini run.

## `defective-skill` is jointly owned

That fixture is also the score-golden oracle for E3.3: `tests/test_score_goldens.py` compares its
`expected.json` to a hand-derived worksheet for exact equality, and line 627 assigns it both duties in
one sentence. **Do not edit any pre-existing file in it.** `seeded-defects.json` was the only
permitted addition, and `tests/test_nl_audit_fixtures.py` asserts that the rest is byte-identical to
its committed content, so a well-meaning edit fails loudly here rather than silently in the other
suite.
