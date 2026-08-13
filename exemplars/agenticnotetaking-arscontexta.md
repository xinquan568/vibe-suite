---
slug: agenticnotetaking-arscontexta
repo: agenticnotetaking/arscontexta
audited: 2026-05-13
commit_sha: HEAD
score: 96
exemplifies:
  - R04
  - R06
  - R08
  - R15
  - R16
  - R18
  - R30
---

# Exemplar: agenticnotetaking/arscontexta

**Score**: 96/100  |  **Date**: 2026-05-13  |  **Commit**: `HEAD`

A 27-skill knowledge-management plugin for Claude Code that earns its 96 through disciplined description triggers, fully-runnable bash examples, and output templates specified to the character — three skills score 100/100.

## Per-rule evidence

### R04 — Description as trigger

All three 100/100 skills pack multiple action phrases and explicit invocation strings into a single `description:` line, making them trigger-ready without an `<example>` block. The graph skill covers 5 trigger phrases across 2 action sentences:

> From `skill-sources/graph/SKILL.md:3`:
>
> ```
> description: Interactive knowledge graph analysis. Routes natural language
> questions to graph scripts, interprets results in domain vocabulary, and
> suggests concrete actions. Triggers on "/graph", "/graph health",
> "/graph triangles", "find synthesis opportunities", "graph analysis".
> ```

The pattern appears across every 100/100 skill — each description names what the skill does (verb phrase), then lists the surface forms a user would actually type. The trigger list moves from exact slash commands to natural language variants ("vault stats", "show metrics", "how big is my vault"), covering both power-user and casual-user entry paths. This is what makes R04 concrete: not a list of topics, but a list of inputs the model can match against.

### R06 — Code examples must be runnable

The graph health operation provides complete, executable bash — not pseudocode — for every metric it claims to compute: note count, link density, orphan detection, dangling link detection, and MOC coverage. Each block is self-contained and executes in isolation.

> From `skill-sources/graph/SKILL.md:59-100`:
>
> ```bash
> # Count total notes (excluding MOCs)
> NOTES_DIR="{vocabulary.notes}"
> TOTAL=$(ls -1 "$NOTES_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
> MOC_COUNT=$(grep -rl '^type: moc' "$NOTES_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
> NOTE_COUNT=$((TOTAL - MOC_COUNT))
>
> # Count all wiki links
> LINK_COUNT=$(grep -ohP '\[\[[^\]]+\]\]' "$NOTES_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
>
> # Calculate link density
> # Density = actual_links / possible_links
> # possible_links = N * (N - 1) for directed graph
> echo "Density: $LINK_COUNT / ($NOTE_COUNT * ($NOTE_COUNT - 1))"
>
> # Find orphan notes (zero incoming links)
> for f in "$NOTES_DIR"/*.md; do
>   NAME=$(basename "$f" .md)
>   INCOMING=$(grep -rl "\[\[$NAME\]\]" "$NOTES_DIR"/ 2>/dev/null | grep -v "$f" | wc -l | tr -d ' ')
>   [[ "$INCOMING" -eq 0 ]] && echo "ORPHAN: $NAME"
> done
> ```

The density formula is written out explicitly (`actual_links / (N * (N-1))`), not left as "calculate graph density." Every shell substitution is spelled out. A model executing this skill can run these blocks unchanged — and the skill also provides a graceful fallback: "if `ops/scripts/graph/orphan-notes.sh` exists, use it directly." Real code first, script delegation second.

### R08 — Patterns over theory

The interactive mode section of the graph skill maps user intent to operations with a concrete routing table — no theory about "natural language understanding," just a lookup that works:

> From `skill-sources/graph/SKILL.md:514-529`:
>
> ```
> | User Says                          | Maps To              | Why                                |
> |------------------------------------|-----------------------|------------------------------------|
> | "Where should I look for connections?" | triangles        | Finding synthesis opportunities    |
> | "What are my most important notes?"    | hubs             | Authority/hub ranking              |
> | "Are there isolated areas?"            | clusters         | Connected component detection      |
> | "How healthy is my graph?"             | health           | Full health report                 |
> | "What bridges my topics?"              | bridges          | Bridge note identification         |
> | "What connects to [[X]]?"              | backward [[X]]   | Backward traversal                 |
> | "Where does [[X]] lead?"               | forward [[X]]    | Forward traversal                  |
> ```

The seed and pipeline skills use the same pattern in their constraint sections — a `never:` / `always:` pair that specifies the decision rules for invariants that prose would obscure:

> From `skill-sources/seed/SKILL.md:292-304`:
>
> ```
> **never:**
> - Skip duplicate detection (prevents wasted processing)
> - Move a source that is not in {DOMAIN:inbox} (living docs stay in place)
> - Reuse claim numbers from previous batches (globally unique is required)
> - Create a task file without updating the queue (both must happen together)
>
> **always:**
> - Ask before proceeding when duplicates are detected
> - Create the archive folder even for living docs (task files need it)
> - Use the archived path (not original) in the task file for {DOMAIN:inbox} sources
> ```

Each constraint bullet includes the reason in parentheses — these are decision rules, not rules to memorize.

### R15 — Handle empty input

Every skill that takes arguments defines an explicit fallback for the empty-argument case. The graph skill enters an interactive mode; the seed skill lists the inbox:

> From `skill-sources/graph/SKILL.md:32-39`:
>
> ```
> Parse the operation from arguments:
> - If arguments match a known operation: route to that operation
> - If arguments are a natural language question: map to the closest operation (see Interactive Mode)
> - If no arguments: enter interactive mode
> ```

> From `skill-sources/seed/SKILL.md:17-18`:
>
> ```
> The target MUST be a file path. If no target provided, list {DOMAIN:inbox}/
> contents and ask which to seed.
> ```

Neither deferring nor crashing — each defines useful behavior for the empty case. The pipeline skill extends this: "If target is empty: list files in {DOMAIN:inbox}/ and ask which to process." The pattern is consistent across all three skills.

### R16 — Define output format

The graph health output template specifies the exact layout, field names, and conditional content — down to the ASCII borders and threshold interpretation table:

> From `skill-sources/graph/SKILL.md:110-139`:
>
> ```
> --=={ graph health }==--
>
>   {vocabulary.note_plural}: [N] (plus [M] {vocabulary.topic_map_plural})
>   Connections: [N] (avg [X] per {vocabulary.note})
>   Graph density: [0.XX]
>   {vocabulary.topic_map} coverage: [N]% of {vocabulary.note_plural} appear in at least one {vocabulary.topic_map}
>
>   Orphans ([N]):
>     - [[orphan name]] — [description from YAML]
>     → Suggestion: Run /{vocabulary.cmd_reflect} to find connections
>
>   Overall: [HEALTHY | NEEDS ATTENTION | FRAGMENTED]
>
> Density benchmarks:
> | Density   | Interpretation                                              |
> |-----------|-------------------------------------------------------------|
> | < 0.02    | Sparse — {vocabulary.note_plural} exist but connections are thin |
> | 0.02-0.06 | Healthy — growing network with meaningful connections        |
> | 0.06-0.15 | Dense — well-connected, watch for over-linking              |
> | > 0.15    | Very dense — verify connections are genuine, not noise      |
> ```

Every bracket (`[N]`, `[HEALTHY | NEEDS ATTENTION | FRAGMENTED]`) is a slot the model fills from computed data. The benchmark table converts raw numbers into interpretation without leaving it to model judgment. The stats skill applies the same discipline, defining a progress bar formula and the exact conditions under which each warning line appears.

### R18 — `argument-hint` when command takes input

The graph skill's `argument-hint` field does double duty: it shows usage AND enumerates all valid operations:

> From `skill-sources/graph/SKILL.md:10`:
>
> ```
> argument-hint: "[operation] [target] — operations: health, triangles, bridges,
>   clusters, hubs, siblings, forward, backward, query"
> ```

A user running `/help` sees the full operation set in one line. The seed skill's hint shows the argument type: `"[file] — path to source file to seed for processing"`. Both are more useful than `"[args]"` because they answer the question "what can I pass?" without requiring the user to read the skill body.

### R30 — Use `${CLAUDE_PLUGIN_ROOT}` for paths

The hooks.json uses `${CLAUDE_PLUGIN_ROOT}` for every script reference — no hardcoded paths:

> From `hooks/hooks.json:8,16,22`:
>
> ```json
> "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/session-orient.sh"
> ...
> "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/write-validate.sh"
> ...
> "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/auto-commit.sh"
> ```

All three hook scripts are referenced through `${CLAUDE_PLUGIN_ROOT}`, which resolves correctly regardless of install location. The hook also correctly uses `"async": true` on the auto-commit hook so write validation is not blocked by a potentially slow git operation.

---

## Worth adopting

**Pattern: Bi-directional constraint block (`never:` / `always:`).** Skill body closes with two labeled lists — one for hard prohibitions, one for invariants. Each item includes a parenthetical reason. Evidence: `skill-sources/seed/SKILL.md:292-304`, `skill-sources/pipeline/SKILL.md:302-315`. Why it would be a useful rule: prose constraint sections mix positive and negative constraints; a labeled split makes each category scannable and makes it easy to verify completeness — the author must commit to both what must never happen AND what must always happen.

**Pattern: `EXECUTE NOW` imperative header.** Every skill opens with an `## EXECUTE NOW` section immediately after frontmatter that states the target, parse rules, and "START NOW." sentence. Evidence: `skill-sources/graph/SKILL.md:31-39`, `skill-sources/seed/SKILL.md:12-23`. Why it would be a useful rule: the pattern counteracts Claude's tendency to preface action with narration; an explicit imperative section anchors execution before any expository content loads.
