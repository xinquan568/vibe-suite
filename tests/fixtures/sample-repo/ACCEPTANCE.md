# AC-3 acceptance runbook — `/vibe-suite:roast`

This tree is the AC-3 structural fixture for E4.3 (vibe-37): a small application carrying **one
seeded issue per cc-suite audit dimension**, nine in total. `seeded-issues.json` records each issue's
id, dimension, file and line.

**What CI already checks.** `tests/test_roast_acceptance.py` proves the gate —
`tools/roast-acceptance.py` — works, by driving it with synthetic reports and confirming each
assertion can fail: a missing dimension, a missing executive summary, an unphased fixing-plan item, an
item citing a finding the report never raised, four agent sections where styles 5–6 need five, and an
unqualified agent name. `tests/test_roast.py` pins the command's own content contract.

**What CI cannot check.** A real roast report, because producing one needs a live engine and CI
dispatches none. That is this runbook's job.

## The two steps

### 1. In a Claude Code session, on a live lane

```
/vibe-suite:roast tests/fixtures/sample-repo --engine codex --style 6 \
    --output /tmp/roast-sample-codex.md
```

`--output` is given explicitly so the report lands outside the fixture. Without it the report would be
written **into** `tests/fixtures/sample-repo/`, and a committed report would then be an input to the
next run — the exact recursion `agents/recon.md`'s `vibe-report-*.md` exclusion exists to prevent.

### 2. In a shell

```bash
python3 tools/roast-acceptance.py tests/fixtures/sample-repo \
  --report /tmp/roast-sample-codex.md --lane codex --style 6
```

Exit `0` passes; `1` names the assertion that failed; `2` means the report could not be graded at all.
Add `--json` for a machine-readable verdict.

## The runs that make up an acceptance pass

| Lane | Command | Asserts |
|---|---|---|
| `claude`, style 2 | `--engine claude --style 2` | four `## [Agent: vibe-suite:…] Findings` sections |
| `claude`, style 6 | `--engine claude --style 6` | five sections — styles 5–6 add `edge-cases` |
| `codex`, style 6 | `--engine codex --style 6` | all nine `## Dimension:` sections |
| `agy`, style 6 | — | **skipped**: the E1.7 contract gate reads `not_passed`, so `--engine agy` errors with a pointer rather than running. Re-run this row after the gate flips. |

Every lane additionally asserts the frontmatter keys, the executive summary, and a phased fixing plan
whose every item cites a finding the report actually raised.

## Recording the result

**Paste the command and its output into the PR.** "The operator step was performed" is a claim; the
exit code and the check list are evidence. A PR that asserts AC-3 without them is asserting a gate
nobody watched run.

## Why the report is graded rather than diffed

Merge-proposal line 628 is explicit that the assertions are **structural, not byte-golden**. A
judgement engine's prose differs run to run; what must not differ is that every dimension is
represented, that the plan is phased, and that every planned action traces to a finding. Grading those
properties is stable across runs and across engines, which is what makes the same fixture usable on
the codex lane today and the agy lane after the flip — line 628 calls that the "engine-independent
outcome contract".

## Do not commit a report into this tree

The fixture is an input. A `vibe-report-*.md` committed here would be surveyed by `recon` on the next
run despite its exclusion rule being about the *target* scan, and would drift from whatever the
current command produces. Write reports to a scratch path, as step 1 does.
