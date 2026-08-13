---
slug: ChromeDevTools-chrome-devtools-mcp
repo: ChromeDevTools/chrome-devtools-mcp
audited: 2026-05-24
commit_sha: 57f32b0cd4afe1775b96ba35c27f25d6f0770331
score: 94
exemplifies:
  - R01
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: ChromeDevTools/chrome-devtools-mcp

**Score**: 94/100  |  **Date**: 2026-05-24  |  **Commit**: `57f32b0cd4afe1775b96ba35c27f25d6f0770331`

A six-skill Chrome DevTools MCP plugin where every skill is trigger-phrase-dense, under 200 lines, and built around executable workflow patterns rather than conceptual overviews.

## Per-rule evidence

### R04 — Description as trigger

`debug-optimize-lcp/SKILL.md` packs eight distinct user-query phrases into a single description block, covering keyword variants ("LCP", "largest contentful paint", "CWV"), symptom descriptions ("slow page loads", "why their page's main content takes too long"), and concrete goal phrasing ("hero image or main content renders").

> Real quote from `skills/debug-optimize-lcp/SKILL.md:3`:
>
> ```
> description: Guides debugging and optimizing Largest Contentful Paint (LCP) using Chrome DevTools MCP tools. Use this skill whenever the user asks about LCP performance, slow page loads, Core Web Vitals optimization, or wants to understand why their page's main content takes too long to appear. Also use when the user mentions "largest contentful paint", "page load speed", "CWV", or wants to improve how fast their hero image or main content renders.
> ```

What makes this exemplary rather than adequate: it covers both the technical acronym ("LCP", "CWV") and the lay description ("why their page's main content takes too long to appear"), which means it triggers on both expert and beginner phrasing. Most skill descriptions cover one vocabulary register, not both.

The `troubleshooting/SKILL.md` description takes a different approach: it triggers on specific tool-call failure events rather than user intents.

> Real quote from `skills/troubleshooting/SKILL.md:3`:
>
> ```
> description: Uses Chrome DevTools MCP and documentation to troubleshoot connection and target issues. Trigger this skill when list_pages, new_page, or navigate_page fail, or when the server initialization fails.
> ```

Naming the exact failing tool calls (`list_pages`, `new_page`, `navigate_page`) makes the trigger deterministic: when Claude sees one of those tool errors, the match is unambiguous.

### R01 — No vague quantifiers

`debug-optimize-lcp/SKILL.md` replaces all performance thresholds with concrete numbers rather than qualitative labels. The LCP breakpoints are explicit millisecond ranges, and the target percentages for each subpart are numeric.

> Real quote from `skills/debug-optimize-lcp/SKILL.md:9-14`:
>
> ```
> - **Good**: 2.5 seconds or less
> - **Needs improvement**: 2.5–4.0 seconds
> - **Poor**: greater than 4.0 seconds
>
> LCP is a Core Web Vital that directly affects user experience and search ranking. On 73% of mobile pages, the LCP element is an image.
> ```

And the subpart targets:

> Real quote from `skills/debug-optimize-lcp/SKILL.md:23-27`:
>
> ```
> | **Time to First Byte (TTFB)** | ~40%           | Navigation start → first byte of HTML received |
> | **Resource load delay**       | <10%           | TTFB → browser starts loading the LCP resource |
> | **Resource load duration**    | ~40%           | Time to download the LCP resource              |
> | **Element render delay**      | <10%           | LCP resource downloaded → LCP element rendered |
> ```

`a11y-debugging/SKILL.md` does the same for tap targets: "tap targets should be at least 48x48 pixels with sufficient spacing" (line 68). Every constraint that could have been "appropriate size" has a number instead.

### R05 — Body length

All six skills stay well under 500 lines. The most detailed skill, `debug-optimize-lcp/SKILL.md`, is 122 lines. The CLI reference, `chrome-devtools-cli/SKILL.md`, is 154 lines despite covering every command category. Neither pads with prose where a table or code block suffices.

> Real quote from `skills/chrome-devtools-cli/SKILL.md:1` (total file length: 154 lines):
>
> ```
> ---
> name: chrome-devtools-cli
> description: Use this skill to write shell scripts or run shell commands to automate tasks in the browser or otherwise use Chrome DevTools via CLI.
> ---
> ```

The CLI skill achieves complete coverage of 40+ commands in 154 lines because it uses a code-block-per-category structure with zero explanatory prose between examples. The `debug-optimize-lcp` skill achieves depth (subpart breakdowns, fix prioritization, emulation instructions) in 122 lines by using tables instead of paragraphs for structured data.

### R06 — Runnable examples

`chrome-devtools-cli/SKILL.md` is entirely composed of runnable shell commands organized by category. Every example is copy-pasteable with no placeholders beyond semantically obvious ones (`"id"`, `"https://example.com"`).

> Real quote from `skills/chrome-devtools-cli/SKILL.md:34-54`:
>
> ```
> ## Input Automation (<uid> from snapshot)
>
> ```bash
> chrome-devtools take_snapshot --help # Help message for commands, works for any command.
> chrome-devtools take_snapshot # Take a text snapshot of the page to get UIDs for elements
> chrome-devtools click "id" # Clicks on the provided element
> chrome-devtools click "id" --dblClick true --includeSnapshot true # Double clicks and returns a snapshot
> chrome-devtools drag "src" "dst" # Drag an element onto another element
> chrome-devtools drag "src" "dst" --includeSnapshot true # Drag an element and return a snapshot
> chrome-devtools fill "id" "text" # Type text into an input or select an option
> chrome-devtools fill "id" "text" --includeSnapshot true # Fill an element and return a snapshot
> ```
> ```

`a11y-debugging/SKILL.md` includes a runnable Node.js one-liner for extracting Lighthouse failures — not pseudocode, not "run a script", but the literal command:

> Real quote from `skills/a11y-debugging/SKILL.md:27-29`:
>
> ```
> node -e "const r=require('./report.json'); Object.values(r.audits).filter(a=>a.score!==null && a.score<1).forEach(a=>console.log(JSON.stringify({id:a.id, title:a.title, items:a.details?.items})))"
> ```

Inline comments on each command (e.g., `# Double clicks and returns a snapshot`) eliminate the need for surrounding prose, keeping the skill dense without being cryptic.

### R07 — Scope note when related skills exist

`chrome-devtools/SKILL.md` includes a negative scope note in its description line: "This skill does not apply to `--slim` mode (MCP configuration)." This directly prevents the skill from being selected for slim-mode users where its tool references would be invalid.

> Real quote from `skills/chrome-devtools/SKILL.md:3`:
>
> ```
> description: Uses Chrome DevTools via MCP for efficient debugging, troubleshooting and browser automation. Use when debugging web pages, automating browser interactions, analyzing performance, or inspecting network requests. This skill does not apply to `--slim` mode (MCP configuration).
> ```

`chrome-devtools-cli/SKILL.md` scopes away from its own setup section with a forward reference:

> Real quote from `skills/chrome-devtools-cli/SKILL.md:10-11`:
>
> ```
> _Note: If this is your very first time using the CLI, see [references/installation.md](references/installation.md) for setup. Installation is a one-time prerequisite and is **not** part of the regular AI workflow._
> ```

The phrase "is **not** part of the regular AI workflow" is load-bearing: it prevents the skill from repeatedly triggering setup steps in a already-configured environment.

### R08 — Patterns over theory

`debug-optimize-lcp/SKILL.md` is structured entirely as bottleneck-specific action patterns. The "Debugging Workflow" section is five numbered steps, each naming the exact MCP tool to call. The "Optimization Strategies" section maps bottleneck type → root cause → fix, with no abstract discussion of LCP theory.

> Real quote from `skills/debug-optimize-lcp/SKILL.md:81-89`:
>
> ```
> ### 1. Eliminate Resource Load Delay (target: <10%)
>
> The most common bottleneck. The LCP resource should start loading immediately.
>
> - **Root Cause**: LCP image loaded via JS/CSS, `data-src` usage, or `loading="lazy"`.
> - **Fix**: Use standard `<img>` with `src`. **Never** lazy-load the LCP image.
> - **Fix**: Add `<link rel="preload" fetchpriority="high">` if the image isn't discoverable in HTML.
> - **Fix**: Add `fetchpriority="high"` to the LCP `<img>` tag.
> ```

`troubleshooting/SKILL.md` structures diagnosis as a six-step escalation ladder with exact error strings to match against at each tier.

> Real quote from `skills/troubleshooting/SKILL.md:25-34`:
>
> ```
> #### Error: `Could not find DevToolsActivePort`
>
> This error is highly specific to the `--autoConnect` feature. It means the MCP server cannot find the file created by a running, debuggable Chrome instance. This is not a generic connection failure.
>
> Your primary goal is to guide the user to ensure Chrome is running and properly configured. Do not immediately suggest switching to `--browserUrl`. Follow this exact sequence:
>
> 1. **Ask the user to confirm that the correct Chrome version** (e.g., "Chrome Canary" if the error mentions it) is currently running.
> 2. **If the user confirms it is running, instruct them to enable remote debugging.**
> ```

Naming the error string verbatim means Claude can match the exact failure without inference. The "do not immediately suggest switching to `--browserUrl`" guard prevents the most common premature escalation.

## Worth adopting

Pattern: **URL suffix trick for fetching clean documentation.** Evidence: `skills/a11y-debugging/SKILL.md:10` — "you can append `.md.txt` to the URL (e.g., `https://web.dev/articles/accessible-tap-targets.md.txt`) to fetch the clean, raw markdown version." Why it would be a useful rule: when a skill references external documentation, it should provide a machine-readable fetch path alongside the human URL, since HTML fetches waste tokens on nav/footer/script noise. Could be codified as: "When citing external docs, provide a raw-markdown fetch URL alongside the human URL. Use the host's documented plain-text suffix (`.md.txt` on web.dev, `/raw/` on GitHub) where available."
