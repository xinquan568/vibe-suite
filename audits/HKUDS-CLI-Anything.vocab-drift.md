# NLPM Vocab Drift Advisory

Repo: HKUDS/CLI-Anything
Artifacts scanned: 73
Drift candidates: 7 (high: 0, medium: 6, low: 1)

──────────────────────────────────────────────────────────────────

CANDIDATE 1 — confidence: medium
  Disposition: likely drift
  Terms:
    "build" — 34 occurrences across 5 files
    "generate" — 46 occurrences across 5 files
  Likely identity: the act of creating a CLI harness from a software codebase
  Evidence:
    cli-anything-plugin/commands/cli-anything.md:3: "Build a complete, stateful CLI harness for any GUI application"
    README.md:230: "1. 🔍 **Analyze** ... 7. 📦 **Publish** — full CLI generation pipeline"
    cli-anything-plugin/README.md:11: "every generated CLI now ships with an AI-discoverable skill"
  Suggested canonical: build
  Action options:
    a) Declare "build" canonical and mark "generate" deprecated for the harness-creation concept
    b) Document the distinction: "build" = full pipeline invocation, "generate" = producing a specific artifact (SKILL.md, intermediate file)
    c) Add "generate" to the deprecated list for the harness-creation verb in a future registry

──────────────────────────────────────────────────────────────────

CANDIDATE 2 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "phase" — 35 occurrences across 4 files
    "step" — 16 occurrences across 2 files
  Likely identity: a numbered sequential stage in the CLI-building pipeline
  Evidence:
    cli-anything-plugin/commands/cli-anything.md:29: "### Phase 0: Source Acquisition"
    cli-anything-plugin/commands/cli-anything.md:34: "### Phase 1: Codebase Analysis"
    cli-anything-plugin/commands/refine.md:38: "### Step 1: Inventory Current Coverage"
    cli-anything-plugin/commands/refine.md:44: "### Step 2: Analyze Software Capabilities"
  Suggested canonical: phase
  Action options:
    a) Standardize on "phase" across all command documents including refine.md
    b) Document the distinction: "phase" = build pipeline stage, "step" = refine sub-step (intentional split)
    c) Rename refine.md sections to "Phase" headings to match cli-anything.md and HARNESS.md

──────────────────────────────────────────────────────────────────

CANDIDATE 3 — confidence: medium
  Disposition: likely drift
  Terms:
    "validate" — 25 occurrences across 5 files
    "verify" — 11 occurrences across 3 files
  Likely identity: confirming correctness of a CLI harness or its outputs
  Evidence:
    cli-anything-plugin/commands/validate.md:3: "Validate a CLI harness against HARNESS.md standards and best practices"
    cli-anything-plugin/HARNESS.md:151: "verify the output"
    cli-anything-plugin/commands/cli-anything.md:63: "Adds output verification (pixel analysis, format validation, etc.)"
  Suggested canonical: validate
  Action options:
    a) Declare "validate" canonical for standards conformance checks; reserve "verify" for output file checks
    b) Align all harness-conformance language to "validate"; keep "verify" only in test-code contexts
    c) Document the distinction: "validate" = check against declared standards, "verify" = confirm output properties

──────────────────────────────────────────────────────────────────

CANDIDATE 4 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "analyze" — 8 occurrences across 3 files
    "scan" — 7 occurrences across 3 files
  Likely identity: examining the target software source code to understand its capabilities
  Evidence:
    cli-anything-plugin/commands/refine.md:44: "### Step 2: Analyze Software Capabilities"
    cli-anything-plugin/commands/refine.md:45: "- Re-scan the software source at `<software-path>`"
    cli-anything-plugin/commands/cli-anything.md:34: "### Phase 1: Codebase Analysis"
  Suggested canonical: analyze
  Action options:
    a) Standardize on "analyze" for the source examination concept; retire "scan" in that context
    b) Document the distinction: "analyze" = deep understanding of source, "scan" = mechanical discovery pass
    c) Keep "scan" for mechanical listing (list.md "Scan installed CLIs") and use "analyze" for source comprehension

──────────────────────────────────────────────────────────────────

CANDIDATE 5 — confidence: medium
  Disposition: likely drift
  Terms:
    "expand" — 6 occurrences across 3 files
    "improve" — 4 occurrences across 2 files
  Likely identity: the outcome of running the refine command — growing CLI coverage
  Evidence:
    opencode-commands/cli-anything-refine.md:2: "description: Refine an existing CLI harness to expand coverage and add missing capabilities"
    cli-anything-plugin/commands/refine.md:3: "Refine an existing CLI harness to improve coverage of the software's functions"
    cli-anything-plugin/commands/refine.md:36: "it analyzes gaps...then iteratively expands coverage"
  Suggested canonical: expand
  Action options:
    a) Align all refine descriptions to "expand coverage"; retire "improve" for this concept
    b) Document the distinction: "expand" = add new commands, "improve" = quality improvements
    c) Use a consistent phrase like "expand and improve coverage" throughout

──────────────────────────────────────────────────────────────────

CANDIDATE 6 — confidence: medium
  Disposition: likely drift
  Terms:
    "capability" — 8 occurrences across 3 files
    "functionality" — 4 occurrences across 2 files
  Likely identity: the feature-set or abilities of the target software being wrapped
  Evidence:
    cli-anything-plugin/commands/refine.md:36: "analyzes gaps between the software's full capabilities and what the current CLI covers"
    cli-anything-plugin/commands/refine.md:36: "narrows its analysis and implementation to that specific functionality area"
    opencode-commands/cli-anything-refine.md:22: "A natural-language description of the functionality area to focus on"
  Suggested canonical: capability
  Action options:
    a) Standardize on "capability" for describing what the target software can do
    b) Use "functionality area" as a compound noun for a scoped sub-domain, distinct from "capabilities" as the full set
    c) Declare "functionality" deprecated in favor of "capability" in a vocabulary registry

──────────────────────────────────────────────────────────────────

CANDIDATE 7 — confidence: low
  Disposition: ambiguous
  Terms:
    "harness" — 350 occurrences across 8+ files
    "wrapper" — 35 occurrences across 4 files
  Likely identity: the generated CLI package that makes a software application agent-accessible
  Evidence:
    skills/cli-anything-dify-workflow/SKILL.md:54: "The harness itself is a wrapper. Real workflow logic is provided by the upstream project."
    README.md:992: "NotebookLM CLI wrapper (experimental)"
    cli-hub-meta-skill/SKILL.md:57: "`cli-hub` is a lightweight wrapper around `pip`"
  Suggested canonical: harness
  Action options:
    a) Reserve "wrapper" for CLIs that explicitly delegate to an existing CLI tool; use "harness" for all others
    b) Document the distinction in HARNESS.md: "harness" = full CLI package, "wrapper" = thin delegation layer
    c) Accept the distinction as intentional and add a note in CONTRIBUTING.md

──────────────────────────────────────────────────────────────────

Summary
  Most-drifted concept: CLI creation verb ("build" vs "generate" — 80 combined occurrences across 5 files)
  Files with the most drift: cli-anything-plugin/commands/refine.md (candidates 4, 5, 6), cli-anything-plugin/HARNESS.md (candidates 1, 3, 4), opencode-commands/cli-anything-refine.md (candidates 2, 5, 6)
  Suggested next step: Bootstrap a vocabulary skill via /nlpm:vocab-init — this corpus has no registry yet and would benefit from declaring canonical terms for at least the high-frequency pairs (build/generate, phase/step, validate/verify).
