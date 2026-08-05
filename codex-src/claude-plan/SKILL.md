---
name: claude-plan
description: "Have Claude Code design an implementation plan before any code gets written. Right for complex tasks, multi-file changes, or unclear requirements — Claude returns numbered steps with exact paths and interfaces, and you implement them."
---

# Claude Plan

Ask Claude to think a task through and hand back a concrete, numbered plan — nothing else.

## When to Use

- A non-trivial feature is about to be implemented
- The change spans interconnected files and the right approach is not obvious
- The user says "have Claude plan this" or "have Claude figure out the design"

## Call Pattern

### Step 1 — request the plan

```
mcp__vibe-claude-mcp__claude_code:
  prompt: |
    Produce an implementation plan for the task below. Do NOT write any code.
    Return a numbered plan only.

    TASK: {what needs to be built or changed}

    CONSTRAINTS:
    - {language, framework, patterns to follow, things not to touch}

    Every step must state:
    - The action, imperatively
    - The exact file path(s) it creates or modifies
    - Key interfaces or data structures it defines
    - Which prior steps it depends on

    Finish with three lists: risk areas, open questions, recommended test scenarios.

    PROVENANCE NOTE: this planning request comes from the delegating Codex agent. Plan
    from your own reading of the repository — do not assume the request's framing is right.
  cwd: {project working directory}
  effort: high
  permissionMode: plan
```

Keep the returned `session_id` as `{plan_session_id}`.

### Step 2 — clarify (optional)

```
mcp__vibe-claude-mcp__claude_code_reply:
  session_id: {plan_session_id}
  prompt: "Step N says 'update the router' — which file exactly, and what changes in it?"
```

### Step 3 — implement

Execute the plan yourself, step by step. To delegate a step back to Claude, use the
`claude-implement` skill.

## Output Format

Show Claude's plan verbatim, then ask the user: proceed, adjust the plan, or delegate the
implementation to Claude.

## Notes

- `permissionMode: plan` guarantees planning writes nothing
- `effort: high` matters here — shallow effort produces vague steps
- Quoting the most relevant files and directory listings in the prompt sharpens the paths
