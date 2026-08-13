# NLPM Vocab Drift Advisory

Repo: tinyhumansai/openhuman
Artifacts scanned: 42
Drift candidates: 10 (high: 2, medium: 8, low: 0)

──────────────────────────────────────────────────────────────────

CANDIDATE 1 — confidence: high
  Disposition: co-occurrence drift
  Terms:
    "sub-agent" — 6 occurrences across 2 files
    "worker" — 8 occurrences across 3 files
  Likely identity: The entity that receives delegated work from the orchestrator (a spawned agent)
  Evidence:
    src/openhuman/agent/agents/orchestrator/prompt.md: "Spawn specialised sub-agents only for tasks that require specialised capabilities"
    src/openhuman/agent/agents/orchestrator/prompt.md: "Use `spawn_worker_thread` for genuinely long or complex delegated tasks"
    docs/DELEGATION_POLICY.md: "Tier 3 — Spawn a sub-agent (inline)" / "Tier 4 — Spawn a dedicated worker thread"
  Suggested canonical: sub-agent
  Action options:
    a) Declare "sub-agent" canonical in registry.yaml; mark "worker" as deprecated except in "worker thread" compound
    b) Document the distinction if "worker" is intentionally reserved for long-running durable tasks and "sub-agent" for inline tasks
    c) Add "worker" to deprecated:[] under the canonical "sub-agent" entry

──────────────────────────────────────────────────────────────────

CANDIDATE 2 — confidence: high
  Disposition: drift
  Terms:
    "summariser" — 4 occurrences across 3 files
    "summarizer" — 3 occurrences across 1 file
  Likely identity: The component or agent responsible for compressing/summarizing content
  Evidence:
    src/openhuman/agent/agents/summarizer/prompt.md: "# Summarizer Agent" (American spelling)
    docs/AGENT_SELF_LEARNING.md: "the same `tree_source::summariser` that already runs over Slack/Gmail/Notion" (British spelling)
    src/openhuman/agent/agents/orchestrator/prompt.md: "summarise results clearly and concisely" (British verb form)
  Suggested canonical: summarizer
  Action options:
    a) Standardize on "summarizer" (American) across all agent names, module names, and prose
    b) Standardize on "summariser" (British) to match the Rust module convention already in tree_source
    c) Document that the two are intentionally different entities (content-compressor agent vs. memory-tree summarization module) and pick one spelling per scope

──────────────────────────────────────────────────────────────────

CANDIDATE 3 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "audit" — 5 occurrences across 3 files
    "review" — 22 occurrences across 5 files
  Likely identity: The operation of inspecting code or a PR for quality issues
  Evidence:
    .claude/agents/pr-reviewer.md: "do a coderabbit-style review of PR #N" / "audit this PR" (both in same description)
    .claude/agents/qualityqueen.md: "Accessibility Auditor" in working style, yet the agent description says "QA Review"
    .claude/agents/designguru.md: "Accessibility and usability auditing" as a capability
  Suggested canonical: review
  Action options:
    a) Use "review" as the canonical term for code inspection workflows; restrict "audit" to formal compliance/accessibility checks
    b) Declare "audit" canonical for systematic quality passes (broader than a PR review) and "review" for collaborative human feedback
    c) Add "audit" to deprecated:[] under "review" in registry.yaml if the distinction is not intentional

──────────────────────────────────────────────────────────────────

CANDIDATE 4 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "delegate" — 12 occurrences across 3 files
    "spawn" — 10 occurrences across 3 files
  Likely identity: The act of handing a task off to another agent
  Evidence:
    docs/DELEGATION_POLICY.md: title is "When to delegate vs. act directly" yet body uses "Spawn a sub-agent"
    src/openhuman/agent/agents/orchestrator/prompt.md: "Delegate only when needed" and "Spawn specialised sub-agents" in adjacent bullets
    src/openhuman/agent/agents/planner/prompt.md: "Never delegate to another reasoning agent" / "spawn hierarchy (hard rule)"
  Suggested canonical: delegate
  Action options:
    a) Use "delegate" for the semantic action (handing responsibility) and "spawn" only for the implementation mechanism (creating an agent process); document the distinction
    b) Standardize on "spawn" throughout since the technical mechanism is process creation
    c) Add "spawn" to deprecated:[] under "delegate" if spawn is considered implementation jargon

──────────────────────────────────────────────────────────────────

CANDIDATE 5 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "address" — 7 occurrences across 4 files
    "apply" — 9 occurrences across 4 files
  Likely identity: The act of implementing reviewer feedback on a pull request
  Evidence:
    .claude/agents/pr-manager.md: "apply every actionable fix" (section heading) and "address each actionable item" in adjacent prose
    .claude/commands/ship-and-babysit.md: "address actionable review comments" and "apply the smallest correct fix" in the same phase
    .codex/skills/ship-and-babysit/SKILL.md: "apply the smallest correct fix" mirroring the command
  Suggested canonical: apply
  Action options:
    a) Use "apply" for code changes (apply a fix, apply a suggestion) and "address" for the broader category (address a concern, address a comment); document this split
    b) Standardize on "apply" throughout PR-manager and ship-and-babysit workflows
    c) Standardize on "address" if the intent is always about responding to reviewer concerns, not just patching code

──────────────────────────────────────────────────────────────────

CANDIDATE 6 — confidence: medium
  Disposition: likely drift
  Terms:
    "architect" — 7 occurrences across 2 files
    "architectobot" — 8 occurrences across 2 files
  Likely identity: The planning agent responsible for architectural design and task decomposition
  Evidence:
    .claude/agents/taskmaster.md: "Architect Role: ArchitectoBot, custom planning agents" (same sentence)
    .claude/agents/taskmaster.md: "Route between Architect ↔ Developer" (bare role name)
    .claude/agents/taskmaster.md: "ArchitectoBot analyzing requirements and designing implementation plan" (branded name)
  Suggested canonical: architectobot
  Action options:
    a) Use "architectobot" consistently as the agent name in all pipeline references; use "architect" only for the abstract role concept when describing role responsibilities
    b) Rename the agent to "architect" for consistency with "developer", "designer", "tester" role naming in the same pipeline
    c) Add a note in taskmaster.md that "Architect" == "ArchitectoBot" to clarify the alias

──────────────────────────────────────────────────────────────────

CANDIDATE 7 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "critic" — 6 occurrences across 3 files
    "qualityqueen" — 8 occurrences across 2 files
  Likely identity: The QA/code-review specialist agent that identifies problems in code
  Evidence:
    src/openhuman/agent/agents/critic/prompt.md: "Adversarial QA Reviewer — find problems before they reach production"
    .claude/agents/qualityqueen.md: "Quality Assurance & Code Standards Specialist — ensures code meets project standards"
    src/openhuman/agent/agents/planner/prompt.md: "`critic` — Reviews code quality and security. Use after code changes."
  Suggested canonical: critic
  Action options:
    a) Document that "critic" (in-product orchestration system) and "qualityqueen" (Claude Code dev workflow) are distinct agents serving parallel roles across two systems
    b) Align the two systems' QA agent names for cross-system readability
    c) Add a cross-reference in each agent's description pointing to its counterpart in the other system

──────────────────────────────────────────────────────────────────

CANDIDATE 8 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "validate" — 7 occurrences across 4 files
    "verify" — 6 occurrences across 4 files
  Likely identity: The action of confirming code or process output meets expected quality
  Evidence:
    .claude/commands/ship-and-babysit.md: "rerun targeted validation" and "Do not claim validation passed if a command was not run"
    .agents/agents/pr-manager.md: "rerun targeted validation" and "Verify that the checked-out branch"
    .claude/agents/codecrusher.md: "Test-First Mindset: Validate implementation with builds and runtime checks" / "Verify functionality works"
  Suggested canonical: validate
  Action options:
    a) Use "validate" for format/spec conformance checks and "verify" for behavioral correctness checks; document the distinction
    b) Standardize on "validate" across all quality workflows (highest file spread: 6 files)
    c) Standardize on "verify" if the codebase prefers a term that implies correctness rather than conformance

──────────────────────────────────────────────────────────────────

CANDIDATE 9 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "coordinate" — 5 occurrences across 1 file
    "orchestrate" — 4 occurrences across 2 files
  Likely identity: The act of managing multi-agent workflows
  Evidence:
    .claude/agents/taskmaster.md: "manages entire development workflows by coordinating specialist agents through configurable pipelines" (description) and "Pipeline Orchestrator" (heading in same file)
    src/openhuman/agent/agents/orchestrator/prompt.md: "Orchestrator" as canonical agent name throughout
    .claude/agents/taskmaster.md: "Agent Coordination Protocol" (section heading)
  Suggested canonical: orchestrate
  Action options:
    a) Use "orchestrate" for the top-level workflow management role and "coordinate" for inter-agent communication at a lower level
    b) Standardize on "orchestrate" to align with the canonical "Orchestrator" agent name
    c) Standardize on "coordinate" if the project prefers to reserve "orchestrate" as a proper noun for the Orchestrator agent only

──────────────────────────────────────────────────────────────────

CANDIDATE 10 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "break down" — 4 occurrences across 2 files
    "decompose" — 4 occurrences across 2 files
  Likely identity: The operation of splitting a complex task into smaller sub-tasks
  Evidence:
    src/openhuman/agent/agents/planner/prompt.md: "decompose a complex user goal into a directed acyclic graph (DAG)"
    .claude/agents/architectobot.md: "Task Decomposer: Break complex features into manageable development chunks"
    .claude/agents/architectobot.md: "Break down even the gnarliest tasks into bite-sized, actionable steps"
  Suggested canonical: decompose
  Action options:
    a) Use "decompose" as the canonical technical verb; use "break down" only in informal/user-facing prose
    b) Add "break down" to deprecated:[] under "decompose" in registry.yaml
    c) Align architectobot's body text with the planner's "decompose" vocabulary since both describe the same operation

──────────────────────────────────────────────────────────────────

Summary
  Most-drifted concept: agent-handoff action ("delegate" vs "spawn", 22 combined occurrences across 3 files)
  Files with the most drift: .claude/agents/taskmaster.md (candidates 6, 9, 10), .claude/agents/pr-manager.md (candidates 3, 4, 5), src/openhuman/agent/agents/orchestrator/prompt.md (candidates 1, 4)
  Suggested next step: Bootstrap a vocabulary skill via /nlpm:vocab-init — 10 candidates across both agent-role nouns and workflow-action verbs suggest the corpus would benefit from a declared registry before drift compounds further.
