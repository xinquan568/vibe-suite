---
slug: htdt-godogen
repo: htdt/godogen
audited: 2026-05-13
commit_sha: c5047e90d11a9b85db4024d73b10395585eba145
score: 91
exemplifies:
  - R05
  - R07
  - R08
  - R44
  - R46
---

# Exemplar: htdt/godogen

**Score**: 91/100  |  **Date**: 2026-05-13  |  **Commit**: `c5047e90`

A source repo for AI game-generation skills (Godot + Bevy), structured as a set of orchestrator SKILL.md files that lazy-load stage sub-skills. The SKILL.md files stay under 110 lines each by delegating every non-trivial behavior to named stage files, and every quality decision is grounded in observable output — screenshots, compiled binary, video frames.

## Per-rule evidence

### R05 — Body length

The orchestrator SKILL.md for godogen (107 lines) stays lean by externalizing every complex sub-stage into a named file that is read on demand. The Capabilities table makes the delegation explicit: each row names a file, its purpose, and the exact trigger condition for loading it.

> `godot/skills/godogen/SKILL.md:16-31`:
>
> ```
> Read each stage file from `${GODOGEN_SKILL_DIR}/` only when you reach that stage.
>
> | File | Purpose | When to read |
> |------|---------|--------------|
> | `visual-target.md` | Generate reference image | Pipeline start |
> | `decomposer.md` | Decompose into task plan | After visual target |
> | `scaffold.md` | Architecture + skeleton | After decomposition |
> | `asset-planner.md` | Budget and plan assets | If budget provided |
> | `asset-gen.md` | Asset generation CLI ref | When generating assets |
> | `rembg.md` | Background removal | Only when an asset needs transparency removed |
> | `task-execution.md` | Task workflow + commands | Before first task |
> | `quirks.md` | Godot gotchas | Before writing code |
> | `scene-generation.md` | Scene builders | Targets include `.tscn` |
> | `test-harness.md` | SceneTree verification scripts | Before writing capture/test scripts |
> | `capture.md` | Screenshot/video capture + final result bundle | Before automated screenshots or video |
> | `android-build.md` | APK export | User requests Android |
> | *(godot-api skill)* | C# Godot syntax ref | When unsure about Godot API details |
> ```

What makes this better than a plain list: the "When to read" column gives the LLM an unambiguous load trigger. Without it, the agent would either load everything upfront (context bloat) or guess when to load each file.

### R07 — Scope note when related skills exist

Both engine orchestrators explicitly route API lookup to a companion skill rather than inlining it, and they explain the routing rationale in one sentence.

> `godot/skills/godogen/SKILL.md:78-82`:
>
> ```
> When you need to look up a Godot class API or C# Godot pattern, use the `godot-api` skill with a
> targeted query. It keeps large API docs out of the main pipeline.
>
> Use the skill inline when you already know what class or symbol to inspect and can answer by
> searching `_common.md` / `_other.md` plus reading a small number of specific docs. Use a
> dedicated helper agent when you need to discover candidate classes, compare several classes, or
> read multiple or large docs and reduce them to a compact answer.
> ```

The scope note includes routing criteria ("inline when you already know … dedicated helper when you need to discover"), not just a pointer. This eliminates the ambiguity of when to delegate — a common failure mode in multi-skill pipelines.

> `bevy/skills/bevy-help/SKILL.md:11-13`:
>
> ```
> Use this skill for any Bevy-related question, not just exact symbol lookup. It should be the
> default tool for Bevy API questions, feature design, architecture, and implementation-pattern
> questions such as "how do I add snow particles?"
> ```

This uses a concrete user query ("how do I add snow particles?") to widen the trigger surface beyond narrow API lookups — a clean way to prevent under-invocation without vague language.

### R08 — Patterns over theory

`bevy/skills/bevy-help/SKILL.md` replaces a generic "check the docs" instruction with a decision table that maps question shape to lookup source.

> `bevy/skills/bevy-help/SKILL.md:52-62`:
>
> ```
> Problem-shape heuristics:
>
> - Pattern or architecture question -> examples first
> - Warning, propagation, auto-inserted behavior, or hierarchy/debug question -> crate source first
> - Exact symbol, trait bound, or signature question -> rustdoc first
>
> Bevy-specific source traps:
>
> - If behavior seems automatic, inspect component attributes such as `#[require(...)]` and
>   `#[component(on_insert = ...)]` in crate source.
> - Rustdoc is best for public names and signatures, but it often hides the internal reason a
>   behavior occurs.
> ```

Each bullet is an actionable dispatch rule. The "source traps" section names specific Bevy internals that reliably fool a lookup-by-rustdoc approach.

`godot/skills/godogen/quirks.md` applies the same principle to Godot engine quirks — every entry is a named failure mode with a concrete code fix, not a concept description.

> `godot/skills/godogen/quirks.md:5-16`:
>
> ```
> - **`SetScript()` disposes the C# wrapper** — calling `SetScript()` on a node in a scene builder
>   invalidates the C# managed wrapper. Any subsequent use of that variable throws
>   `ObjectDisposedException`. Build the full node hierarchy first, call `SetScript()` last.
>   For the root node, use a temp parent to re-obtain the reference after `SetScript()`:
>   ```csharp
>   var temp = new Node();
>   var root = new Node2D();
>   root.Name = "Main";
>   temp.AddChild(root);
>   // ... build entire hierarchy ...
>   root.SetScript(GD.Load("res://scripts/GameManager.cs"));  // wrapper dies here
>   var rootNode = temp.GetChild(0);  // re-obtain via temp parent
>   temp.RemoveChild(rootNode);
>   // now use rootNode for packing
>   ```
> ```

The pattern names the exact exception thrown, the exact trigger condition, and the exact fix in compilable C#. No hedging, no "you may see issues with."

### R44 — QC gate between AI and output

Both godogen orchestrators make visual verification a mandatory step rather than an advisory one. The framing is adversarial by design.

> `godot/skills/godogen/SKILL.md:101-106`:
>
> ```
> **Do not trust code alone — verify on screenshots, captured frames, and video.** Code that
> looks correct often still ships broken placement, wrong scale, clipped geometry, missing
> elements, or bad motion timing.
>
> When code and media disagree, trust the media. Be skeptical: the job is to find what is still
> broken, not to argue that it is probably fine. If a requirement is not clearly visible, treat
> it as not done.
> ```

"Not to argue that it is probably fine" is the key phrase — it pre-empts the model's tendency to rationalize ambiguous screenshots as acceptable. The gate is applied on every task iteration, not just at delivery.

`godot/skills/godogen/task-execution.md` encodes the same gate into the implementation loop at step 8, making it structurally impossible to skip:

> `godot/skills/godogen/task-execution.md:43-50`:
>
> ```
> 8. Run a runtime smoke test:
>    - local desktop: `godot --path .`
>    - headless workstation or CI: use the capture wrapper from `capture.md`
>    - screenshots or video needed: switch to the deterministic capture path in `capture.md`
> 9. Read runtime logs, not just the exit code. Missing resources, import failures, camera
>    warnings, and script errors are real failures.
> ```

### R46 — State file for resumability

The pipeline explicitly checks for a `PLAN.md` sentinel before deciding whether to start fresh or resume mid-task.

> `godot/skills/godogen/SKILL.md:38-44`:
>
> ```
> +- Check if PLAN.md exists (resume check)
> |   +- If yes: read PLAN.md, STRUCTURE.md, MEMORY.md, ASSETS.md if present -> skip to task execution
> |   +- If no: continue with fresh pipeline below
> ```

The state files are named, scoped to distinct concerns, and enumerated:

> `godot/skills/godogen/SKILL.md:90-98`:
>
> ```
> Keep important state in files so the pipeline can resume cleanly after long threads or compaction:
>
> - **PLAN.md** — task statuses and verification criteria
> - **STRUCTURE.md** — architecture reference
> - **MEMORY.md** — discoveries, quirks, workarounds, what worked or failed
> - **ASSETS.md** — asset manifest with paths and generation details
>
> After completing each task: update `PLAN.md`, write discoveries to `MEMORY.md`, and commit. If
> the thread becomes noisy, summarize the important state into those files and continue from the
> artifacts instead of relying on conversational memory.
> ```

One file per concern (plan / structure / memory / assets) means a resumed session loads only what it needs rather than a monolithic state blob. The "commit after each task" instruction makes the state durable across crashes.

## Worth adopting

**Pattern: On-demand stage loading via a "When to read" table.** Evidence: `godot/skills/godogen/SKILL.md:16-31` and `bevy/skills/godogen/SKILL.md:16-30`. A Capabilities table with columns `File | Purpose | When to read` tells the model exactly which sub-skill to load at each pipeline stage, preventing both eager loading (context bloat) and missed loads (skipped steps). Why it would be a useful rule: large-context skills can stay under the R05 limit by externalizing stages to sub-files — but only if the orchestrator specifies load triggers, not just file names. A rule would be: "In multi-stage skills, enumerate sub-skill files with an explicit load condition. 'When to read' or equivalent — not just a list of files."

**Pattern: Invocation scope with concrete query examples.** Evidence: `bevy/skills/bevy-help/SKILL.md:11-13` and `godot/skills/godogen/SKILL.md:82-85`. Both skills include a short example query to illustrate invocation scope — "how do I add snow particles?" (bevy-help) and `"CharacterBody3D: what method applies velocity and slides along collisions?"` (godogen). This widens trigger recognition beyond exact-match cases. Why it would be a useful rule: R04 requires 3+ action phrases, but a single concrete user query example often does more work than a phrase list for skills with broad, hard-to-enumerate scopes.
