---
description: "Root-cause analysis: cheap in-session recon shortlists suspect files, one read-only Codex dispatch analyses them per-file, and the report promotes only recon-supported findings."
argument-hint: "<bug description> [--background|--wait]"
---

# /vibe-suite:bug-analyze — recon-first root-cause analysis

Two stages: **recon in-session** (cheap, no engine cost), then **one read-only engine dispatch**
whose prompt carries a per-file section for every shortlisted file. The report never promotes a
claim the recon evidence does not support.

## 1. Recon — shortlist the suspects

Derive fixed-string search terms from the bug description (symbols, function names, error
fragments — not prose). Terms are **data**: the sweep is fixed-string (`-F`), option-terminated
(`--`), and capped, so regex metacharacters, shell syntax, or leading dashes in a description can
neither break nor broaden it. Use the session's Grep/Glob tools interactively, or the canonical
sweep (`BUGA_TERMS` = newline-separated terms):

<!-- canonical-recon -->
```bash
set -euo pipefail
printf '%s\n' "$BUGA_TERMS" | while IFS= read -r term; do
  [ -n "$term" ] || continue
  grep -rIlF --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.vibe-suite-state \
    -e "$term" -- . || true
done | sed 's|^\./||' | sort -u | head -n "${BUGA_CAP:-5}"
```

### When recon comes up empty

Never dispatch an empty shortlist, and never pretend the shortlist is complete. First **widen**:
split the description into more and looser fixed strings (identifiers without namespaces, error
substrings, file suffixes). If the sweep still finds nothing, ask the operator for a symptom
location (a file, a stack frame, a failing test) and re-run recon from there.

## 2. One dispatch — per-file analysis inside it

Compose the prompt with the Write tool **outside the workspace** (a temp path — a prompt file
inside the repo would match its own recon terms and contaminate any later sweep), and **save the
shortlist beside it** at dispatch time: the shortlist that built this prompt is part of the job's
inputs, not something to re-derive later. One section per shortlisted file — `FILE: <path>`
followed by the recon evidence lines. One job, bounded by the shortlist cap; analysis never
writes, so the sandbox is a constant:

<!-- canonical-dispatch -->
```bash
set -euo pipefail
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-runner.mjs" --kind bug-analyze --sandbox read-only ${BUGA_BACKGROUND:+--background} -- "$(cat "$BUGA_PROMPT_FILE")"
```

Branch on the four-key result's `status` — analysis output is used **only for `completed`**.
`failed` and `timed_out` route to §4; `cancelled` is the operator's own stop — report
it and stop. With `BUGA_BACKGROUND=1` the line above returns a `running` **launch receipt** (a
receipt, not an outcome): manage the job with `/vibe-suite:jobs`, and assemble the report at
retrieval time — after `/vibe-suite:jobs result <id>`, apply the same status branching and
assemble with the **shortlist saved at dispatch time**. Only if that file is lost re-run §1, and
then exclude generated artifacts (the prompt file, prior reports) from the sweep.

## 3. The report — findings are recon-supported or they are not findings

Assemble with the canonical block (`REPORT_SHORTLIST_FILE` = recon output,
`REPORT_RESULT_FILE` = the completed job's analysis text). The `## Root-cause findings` section
contains **only shortlist files the engine analysis actually addresses**; an engine claim naming a
file outside the shortlist is **not promoted** — it stays visible solely inside the fenced engine
text, as data:

<!-- canonical-report -->
```bash
set -euo pipefail
echo "## Root-cause findings (shortlist files the analysis addresses)"
while IFS= read -r f; do
  [ -n "$f" ] || continue
  if grep -qF -- "$f" "$REPORT_RESULT_FILE"; then echo "- $f"; fi
done < "$REPORT_SHORTLIST_FILE"
echo
echo "## Engine analysis (external text, shown as data)"
# The fence must be strictly longer than every tilde run in the content (an embedded ~~~ would
# close a fixed fence), and terminal controls are stripped — external text renders, never acts.
run=$({ grep -o '~~~*' "$REPORT_RESULT_FILE" || true; } | awk '{ if (length($0) > m) m = length($0) } END { print m + 0 }')
[ "$run" -lt 3 ] && run=3
fence=$(printf '~%.0s' $(seq 1 $((run + 1))))
echo "$fence"
head -c 4000 "$REPORT_RESULT_FILE" | LC_ALL=C tr -d '\000-\010\013-\037\177'
echo
echo "$fence"
```

Around that skeleton, state the root cause, quote the recon evidence, and suggest a fix direction
— checked against the evidence, never transcribed from the engine on trust.

## 4. When codex is unreachable — the fallback

Per `commands/shared/fallback.md`: spawn failure, timeout, `turn.failed`, or no terminal event →
the diagnostic header (actionable remedy; `/vibe-suite:preflight` is the diagnostic supplement),
then the **manual fallback** — natural here: the recon shortlist is already in-session, so perform
the per-file analysis yourself and say so. A `completed` job with empty or unusable output falls
back the same way **without** the header.
