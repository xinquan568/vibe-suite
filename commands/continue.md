---
description: "Resume a prior engine job's thread with a follow-up prompt. Takes the job id from /vibe-suite:jobs; kind, sandbox, effort and model are inherited from the prior record by contract."
argument-hint: "<job-id> <follow-up>"
---

# /vibe-suite:continue — resume a prior engine thread

Resumes the conversation a prior job holds in the engine. The surface is the **job id** (from
`/vibe-suite:jobs status --all`) — the runner reads the record, requires its thread id, and
**inherits kind, sandbox, effort and model from the prior record by construction**. That is why
the dispatch passes none of those flags: inheriting is the contract, and re-specifying would
either be ignored or fight it. (F2.4's planning prose says "threadId"; the implemented, honest
surface is the job id — the record carries the thread.)

## 1. Usage errors are answers, not fallbacks

Check these before dispatching; each has a remedy and **none of them is an engine failure**:

- **Job id not found** → the remedy is `/vibe-suite:jobs status --all` to find the right id.
- **The record has `no thread id`** (a failed spawn or never-claimed job) → not resumable; the
  remedy is a fresh dispatch of the original command instead.
- **The prior sandbox is `danger-full-access`** → inheriting a confirmed sandbox is not inheriting
  the confirmation. Confirm in-session with AskUserQuestion (state what full access means), and
  only after an explicit yes set `CONTINUE_CONFIRM_DANGER=1`. Declined or ambiguous → stop; do not
  downgrade silently (a resumed thread cannot change sandbox).

## 2. Dispatch

Compose the follow-up with the Write tool (`CONTINUE_PROMPT_FILE`); values travel as env data:

<!-- canonical-dispatch -->
```bash
set -euo pipefail
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-runner.mjs" --resume "$CONTINUE_JOB_ID" ${CONTINUE_CONFIRM_DANGER:+--confirm-danger} -- "$(cat "$CONTINUE_PROMPT_FILE")"
```

Branch on the four-key result's `status`: use the output **only for `completed`**; `failed` and
`timed_out` route to §3; `cancelled` is the operator's own stop — report it and stop.

## 3. When the engine is unreachable — the honest fallback

**Only true engine unavailability** (spawn failure, timeout, `turn.failed`, no terminal event)
falls back — never the §1 usage errors. And the fallback discloses its gap plainly: **the original
thread's conversation history lives in the engine and is not recoverable from here.** Work from
what exists — the prior job's recorded `rawOutput`, the current session's context, and the
operator's follow-up — state that limitation in the disclosure header (per
`commands/shared/fallback.md`; `/vibe-suite:preflight` is the diagnostic supplement), and ask the
operator for any context the follow-up needs rather than pretending the thread was resumed.
