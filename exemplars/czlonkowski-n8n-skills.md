---
slug: czlonkowski-n8n-skills
repo: czlonkowski/n8n-skills
audited: 2026-05-13
commit_sha: 27e9d0ab92cccfc46db4f147497b173f214b69c5
score: 93
exemplifies:
  - R04
  - R06
  - R07
  - R08
---

# Exemplar: czlonkowski/n8n-skills

**Score**: 93/100  |  **Date**: 2026-05-13  |  **Commit**: `27e9d0ab92cccfc46db4f147497b173f214b69c5`

A 7-skill plugin teaching Claude how to build n8n workflows via an MCP server; notable for using trigger-escalation in descriptions, ✅/❌ code contrasts throughout, and explicit cross-skill dispatch maps in every file.

## Per-rule evidence

### R04 — Description as trigger

Every SKILL.md description is a list of action phrases, not a summary of content. Two techniques stand out: `n8n-workflow-patterns` stacks 9 trigger phrases and then adds a "catch-all" sentence to prevent misses when the user's language doesn't match any phrase; `n8n-mcp-tools-expert` escalates to an IMPORTANT sentinel that tells Claude to consult the skill first, before any tool call.

> `skills/n8n-workflow-patterns/SKILL.md:3`:
>
> ```
> description: Proven workflow architectural patterns from real n8n workflows. Use when
> building new workflows, designing workflow structure, choosing workflow patterns,
> planning workflow architecture, or asking about webhook processing, HTTP API integration,
> database operations, AI agent workflows, batch processing, or scheduled tasks. Always
> consult this skill when the user asks to create, build, or design an n8n workflow,
> automate a process, or connect services — even if they don't explicitly mention
> 'patterns'. Covers webhook, API, database, AI, batch processing, and scheduled
> automation architectures.
> ```

The "even if they don't explicitly mention 'patterns'" clause is the key differentiator. Without it, a user asking "connect my Slack to a database" might miss the trigger. With it, Claude is instructed to load the skill for any workflow-construction intent, narrowing the gap between user language and skill vocabulary.

> `skills/n8n-mcp-tools-expert/SKILL.md:3`:
>
> ```
> description: Expert guide for using n8n-mcp MCP tools effectively. Use when searching
> for nodes, validating configurations, accessing templates, managing workflows, managing
> credentials, auditing instance security, or using any n8n-mcp tool. Provides tool
> selection guidance, parameter formats, and common patterns. IMPORTANT — Always consult
> this skill before calling any n8n-mcp tool — it prevents common mistakes like wrong
> nodeType formats, incorrect parameter structures, and inefficient tool usage. If the
> user mentions n8n, workflows, nodes, or automation and you have n8n MCP tools
> available, use this skill first.
> ```

The all-caps IMPORTANT signals that this isn't just a trigger phrase — it's a load-order instruction. Claude is told to consult this skill *before* acting, which prevents errors that would only surface after a tool call fails.

### R06 — Code examples must be runnable

Two techniques appear across all 7 skills. First, `n8n-expression-syntax` uses ✅/❌ pairs to show the exact wrong syntax alongside the correct form — no prose description, just the token difference:

> `skills/n8n-expression-syntax/SKILL.md:20-27`:
>
> ```
> **Examples**:
> ```
> ✅ {{$json.email}}
> ✅ {{$json.body.name}}
> ✅ {{$node["HTTP Request"].json.data}}
> ❌ $json.email  (no braces - treated as literal text)
> ❌ {$json.email}  (single braces - invalid)
> ```

Second, `n8n-mcp-tools-expert` distinguishes two nodeType formats — a common source of errors — by showing the actual string values that differ between tool groups:

> `skills/n8n-mcp-tools-expert/SKILL.md:107-133`:
>
> ```
> ### Format 1: Search/Validate Tools
> ```javascript
> // Use SHORT prefix
> "nodes-base.slack"
> "nodes-base.httpRequest"
> ```
>
> **Tools that use this**:
> - search_nodes (returns this format)
> - get_node
> - validate_node
>
> ### Format 2: Workflow Tools
> ```javascript
> // Use FULL prefix
> "n8n-nodes-base.slack"
> "n8n-nodes-base.httpRequest"
> "@n8n/n8n-nodes-langchain.agent"
> ```
>
> **Tools that use this**:
> - n8n_create_workflow
> - n8n_update_partial_workflow
> ```

Each example is immediately actionable: copy the string, use it in the named tool. There's no "the format varies by tool" summary that leaves Claude to guess which format applies where.

### R07 — Scope note when related skills exist

Every SKILL.md closes with an explicit section that names sibling skills and states *what each one adds* — not just a list of names. `n8n-workflow-patterns` goes further and explains the handoff: use this skill to choose structure, then use MCP Tools Expert to instantiate nodes, then Expression Syntax to wire data:

> `skills/n8n-workflow-patterns/SKILL.md:322-347`:
>
> ```
> ## Integration with Other Skills
>
> These skills work together with Workflow Patterns:
>
> **n8n MCP Tools Expert** - Use to:
> - Find nodes for your pattern (search_nodes)
> - Understand node operations (get_node)
> - Create workflows (n8n_create_workflow)
>
> **n8n Expression Syntax** - Use to:
> - Write expressions in transformation nodes
> - Access webhook data correctly ({{$json.body.field}})
> - Reference previous nodes ({{$node["Node Name"].json.field}})
>
> **n8n Node Configuration** - Use to:
> - Configure specific operations for pattern nodes
> - Understand node-specific requirements
>
> **n8n Validation Expert** - Use to:
> - Validate workflow structure
> - Fix validation errors
> - Ensure workflow correctness before deployment
> ```

And `n8n-expression-syntax` ends with a minimal version that covers the same ground in 3 lines:

> `skills/n8n-expression-syntax/SKILL.md:496-500`:
>
> ```
> ## Related Skills
>
> - **n8n MCP Tools Expert**: Learn how to validate expressions using MCP tools
> - **n8n Workflow Patterns**: See expressions in real workflow examples
> - **n8n Node Configuration**: Understand when expressions are needed
> ```

The "Use to:" lists in the longer version make the scope notes load-bearing, not decorative. Claude knows it should load n8n Expression Syntax when it needs to write `{{$json.body.field}}` — not when it needs to select a webhook node.

### R08 — Patterns over theory

`n8n-workflow-patterns` is structured entirely as a decision table: pick a pattern, get a template, see a concrete example. The Pattern Selection Guide names when each applies, then closes with a one-line example of the kind of workflow it fits:

> `skills/n8n-workflow-patterns/SKILL.md:44-79`:
>
> ```
> ### When to use each pattern:
>
> **Webhook Processing** - Use when:
> - Receiving data from external systems
> - Building integrations (Slack commands, form submissions, GitHub webhooks)
> - Need instant response to events
> - Example: "Receive Stripe payment webhook → Update database → Send confirmation"
>
> **HTTP API Integration** - Use when:
> - Fetching data from external APIs
> - Synchronizing with third-party services
> - Building data pipelines
> - Example: "Fetch GitHub issues → Transform → Create Jira tickets"
>
> **Database Operations** - Use when:
> - Syncing between databases
> - Running database queries on schedule
> - ETL workflows
> - Example: "Read Postgres records → Transform → Write to MySQL"
>
> **AI Agent Workflow** - Use when:
> - Building conversational AI
> - Need AI with tool access
> - Multi-step reasoning tasks
> - Example: "Chat with AI that can search docs, query database, send emails"
> ```

The example lines are the anchor. Without them, the "use when" bullets are abstract criteria. With them, Claude can match "my use case sounds like the Stripe example" even if the user's language doesn't match any bullet.

`n8n-validation-expert` applies the same technique to a process: the Validation Loop section cites telemetry counts ("7,841 occurrences") to show that this pattern isn't speculative — it describes observed real-world behavior:

> `skills/n8n-validation-expert/SKILL.md:76-86`:
>
> ```
> ### Pattern from Telemetry
> **7,841 occurrences** of this pattern:
>
> ```
> 1. Configure node
> 2. validate_node → fix errors
> 3. validate_node again (confirm fix)
> 4. Repeat 2-3 until no errors
> 5. validate_workflow when all nodes clean
> ```
>
> **Average**: 23s thinking about errors, 58s fixing them
> ```

The timing data grounds the pattern in observed cost. A skill that says "validation is iterative" is theory. A skill that says "expect 2-3 cycles, 23s thinking + 58s fixing per cycle" tells Claude what to communicate to the user about time.

## Worth adopting

**Pattern: Reference-file decomposition.** Every SKILL.md in this repo links to auxiliary `.md` files for bulk reference material (`COMMON_MISTAKES.md`, `DATA_ACCESS.md`, `EXAMPLES.md`, `BUILTIN_FUNCTIONS.md`, etc.), keeping the SKILL.md body as a quick-reference hub while deferring detail to on-demand reads. Evidence: `skills/n8n-expression-syntax/SKILL.md:519-521` (`For more details, see: [COMMON_MISTAKES.md](COMMON_MISTAKES.md) — Complete error catalog / [EXAMPLES.md](EXAMPLES.md) — Real workflow examples`); pattern repeated across all 7 skills. Why it would be a useful rule: R05 says "split into scoped sub-skills" for over-500-line skills, but domain cohesion sometimes makes multiple SKILL.md files unnatural. A complementary rule — "defer bulk lookup tables and example catalogs to linked auxiliary files; keep SKILL.md to quick-lookup patterns only" — would formalize a practice that already reduces effective context load even when the SKILL.md line count exceeds 500.
