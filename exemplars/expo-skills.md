---
slug: expo-skills
repo: expo/skills
audited: 2026-05-13
commit_sha: 93751dadf0494110893a9f7a2091ca14833d8212
score: 92
exemplifies:
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: expo/skills

**Score**: 92/100  |  **Date**: 2026-05-13  |  **Commit**: `93751dadf0494110893a9f7a2091ca14833d8212`

An Expo-authored collection of 13 skills for app development, deployment, and monitoring — notable for descriptions that read like natural user queries and a `references/` discipline that keeps every skill under 250 lines.

## Per-rule evidence

### R04 — Description as trigger

`eas-update-insights` packs 6 natural user query phrases plus 3 trigger conditions into its description field, making it unambiguous about which user messages should load this skill.

> `plugins/expo/skills/eas-update-insights/SKILL.md:3`:
>
> ```
> description: "Check the health of published EAS Updates: crash rates, install/launch counts,
> unique users, payload size, and the split between embedded and OTA users per channel. Use when
> the user asks how an update is performing, whether a rollout is healthy, how many users are on
> the embedded build vs OTA, or wants to gate CI on update health."
> ```

The description names concrete metrics (crash rates, payload size, unique users), specifies the delivery axis (embedded vs OTA split), and adds a non-obvious trigger ("gate CI on update health") that a summary-style description would miss entirely. A skill description written as "Use for EAS update monitoring" would fire on one trigger phrase; this one fires on six.

`expo-module` follows the same construction — action phrase first, then scope expansion:

> `plugins/expo/skills/expo-module/SKILL.md:3`:
>
> ```
> description: Guide for writing Expo native modules and views using the Expo Modules API
> (Swift, Kotlin, TypeScript). Covers module definition DSL, native views, shared objects,
> config plugins, lifecycle hooks, autolinking, and type system. Use when building or modifying
> native modules for Expo.
> ```

### R05 — Body length

Every skill in the collection stays under 250 lines. The heavier skills — `building-native-ui` and `expo-api-routes` — stay lean by delegating detail to `references/` subdirectories. `building-native-ui` ships 13 named reference files:

> `plugins/expo/skills/building-native-ui/references/` (directory listing):
>
> ```
> tabs.md             toolbar-and-headers.md   form-sheet.md
> webgpu-three.md     search.md                visual-effects.md
> icons.md            controls.md              animations.md
> storage.md          gradients.md             route-structure.md
> media.md            zoom-transitions.md
> ```

`expo-module` routes reference detail through an annotated index at the top of the file, so Claude can load only the needed sub-document:

> `plugins/expo/skills/expo-module/SKILL.md:28-34`:
>
> ```
> references/
>   native-module.md      Module definition DSL: Name, Function, AsyncFunction, Property,
>                         Constant, Events, type system, shared objects
>   native-view.md        Native view components: View, Prop, EventDispatcher, view lifecycle,
>                         ref-based functions
>   lifecycle.md          Lifecycle hooks: module, iOS app/AppDelegate, Android activity/application
>   config-plugin.md      Config plugins: modifying Info.plist, AndroidManifest.xml
>   module-config.md      expo-module.config.json fields and autolinking configuration
> ```

Each entry carries a one-line summary so Claude can pick the right sub-file without reading all five.

### R06 — Code examples must be runnable

`eas-update-insights` "Common workflows" gives complete copy-pasteable bash — real group IDs, real jq expressions, real flag combinations. Nothing is pseudocode.

> `plugins/expo/skills/eas-update-insights/SKILL.md:175-182`:
>
> ```bash
> # 1. Grab the latest publish on production
> GROUP_ID=$(eas update:list --branch production --json --non-interactive \
>   | jq -r '.currentPage[0].group')
>
> # 2. Give it some adoption time (minutes to hours), then check crash rate
> eas update:insights "$GROUP_ID" --json --non-interactive \
>   | jq '.platforms[] | {platform, installs: .totals.installs, crashRate: .totals.crashRatePercent}'
> ```

The regression detection workflow takes the same approach — a two-liner that someone can paste into a CI script unchanged:

> `plugins/expo/skills/eas-update-insights/SKILL.md:203-205`:
>
> ```bash
> eas update:insights "$GROUP_ID" --days 1 --json --non-interactive \
>   | jq '.platforms[] | select(.totals.crashRatePercent > 1)'
> ```

`expo-dev-client` specifies the exact output artifact per platform — not "a build file":

> `plugins/expo/skills/expo-dev-client/SKILL.md:81-84`:
>
> ```
> Local builds output:
> - iOS: `.ipa` file
> - Android: `.apk` or `.aab` file
> ```

### R07 — Scope note when related skills exist

`eas-update-insights` closes its "When to use" section with an explicit negative boundary — the one sentence that prevents Claude from stretching this skill into per-device reporting:

> `plugins/expo/skills/eas-update-insights/SKILL.md:28`:
>
> ```
> Don't use when the user needs per-user crash detail or device-level reporting;
> this skill only exposes aggregate EAS metrics.
> ```

This scope note names the adjacent use case (per-user crash detail), names the related category it belongs to (device-level reporting), and states the invariant (aggregate only). A skill without this line would silently hallucinate per-user capabilities when the user asks "which specific users crashed?"

`expo-dev-client` applies the same technique to prevent the common over-reach of creating dev clients for Expo Go apps:

> `plugins/expo/skills/expo-dev-client/SKILL.md:13-20`:
>
> ```
> Only create development clients when your app requires custom native code. Most apps
> work fine in Expo Go.
>
> You need a dev client ONLY when using:
> - Local Expo modules (custom native code)
> - Apple targets (widgets, app clips, extensions)
> - Third-party native modules not in Expo Go
>
> Try Expo Go first with `npx expo start`. If everything works, you don't need a dev client.
> ```

### R08 — Patterns over theory

`eas-update-insights` "Common workflows" is organized by user situation, not by CLI surface area:

> `plugins/expo/skills/eas-update-insights/SKILL.md:172-213` (section headings):
>
> ```
> ### Verify the update I just published is healthy
> ### Compare adoption between two channels
> ### Detect a rollout regression in the last 24 hours
> ### Summarize group metrics for release notes
> ```

The file could have been organized by command (`eas update:insights`, `eas channel:insights`) — the structure of the CLI. Instead, each section names what the user is trying to accomplish. That means Claude picks the right command for the situation rather than picking a command and guessing the situation.

`expo-api-routes` leads with two decision matrices before any implementation detail:

> `plugins/expo/skills/expo-api-routes/SKILL.md:8-28` (structure):
>
> ```
> ## When to Use API Routes
>
> Use API routes when you need:
> - Server-side secrets — API keys, database credentials, or tokens that must never reach the client
> - Database operations — Direct database queries that shouldn't be exposed
> - Third-party API proxies — Hide API keys when calling external services (OpenAI, Stripe, etc.)
> ...
>
> ## When NOT to Use API Routes
>
> Avoid API routes when:
> - Data is already public — Use direct fetch to public APIs instead
> - Real-time updates needed — Use WebSockets or services like Supabase Realtime
> ...
> ```

The decision matrices appear before any code — the skill teaches when to apply the pattern before teaching the pattern itself.

## Worth adopting

**Pattern: Verbatim error message registry.** Evidence: `eas-update-insights/SKILL.md:115-117` and `eas-update-insights/SKILL.md:166-168` each document CLI error messages verbatim with trigger condition and fix in one block, e.g., `` `Could not find any updates with group ID: "<id>"` — group doesn't exist or you lack access. `` Why it would be a useful rule: when Claude encounters an actual terminal error and the exact error string is quoted in the loaded skill, it can route to the fix in a single inference step rather than re-reading docs or hallucinating a fix. Proposed rule: "Quote terminal error messages verbatim when recovery is non-obvious. One line per error: the literal message, the trigger condition, and the fix."
