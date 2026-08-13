---
slug: Xquik-dev-x-twitter-scraper
repo: Xquik-dev/x-twitter-scraper
audited: 2026-05-13
commit_sha: c9945b1061a0bc14f88cff48402442392f495ac0
score: 97
exemplifies:
  - R01
  - R04
  - R05
  - R06
  - R07
  - R08
---

# Exemplar: Xquik-dev/x-twitter-scraper

**Score**: 97/100  |  **Date**: 2026-05-13  |  **Commit**: `c9945b1061a0bc14f88cff48402442392f495ac0`

A 42-skill plugin wrapping a 111-endpoint X (Twitter) API — notable for trigger-engineered descriptions, disciplined per-workflow scoping, ASCII decision trees, and a security posture documented entirely in structured frontmatter.

## Per-rule evidence

### R04 — Description as trigger

The master skill's description is written as a dispatch surface, not a label. It covers 12 distinct action categories, handles the Twitter/X naming ambiguity explicitly, and anticipates users who phrase requests in terms of outcomes rather than API operations.

> From `skills/x-twitter-scraper/SKILL.md:3`:
>
> ```
> description: "Use when the user needs to interact with X (Twitter) - searching tweets, looking up
> users/followers, posting tweets/replies, liking, retweeting, following/unfollowing, sending DMs,
> downloading media, monitoring accounts in real time, or extracting bulk data. Provides 111 REST API
> endpoints, 2 MCP tools, and HMAC webhooks. The skill authenticates only with a Xquik API key
> (xq_...) and NEVER asks for, transmits, stores, or logs any X account login material - X account
> connection is done by the user in the Xquik dashboard. Use even if the user says 'Twitter' instead
> of 'X', or asks about social media automation, tweet analytics, or follower analysis."
> ```

The "Use even if the user says 'Twitter' instead of 'X'" clause preemptively defeats the most likely retrieval failure mode. Sibling skills follow the same discipline — `find-bangers` targets the colloquial term directly:

> From `skills/find-bangers/SKILL.md:3-4`:
>
> ```
> description: "Use when the user asks for 'bangers' on X (Twitter) - breakout tweets with
> exceptional engagement relative to the author's usual performance."
> ```

### R05 — Body length

The 42 sibling skills are scoped to a single workflow each and stay well under the 500-line limit by delegating bulk reference to the master skill. `find-bangers/SKILL.md` covers a complete workflow in 57 lines; `export-tweets-csv/SKILL.md` covers format selection, flow, and security in 66 lines; `monitor-accounts/SKILL.md` covers creation, polling, and teardown in 77 lines. The master skill (`x-twitter-scraper/SKILL.md`) carries the full API surface and lands at 434 lines — just inside the cap.

Sibling skills delegate explicitly rather than duplicating:

> From `skills/search-tweets/SKILL.md:119`:
>
> ```
> For posting tweets, reading user timelines, extracting replies, or monitoring accounts, see the
> sibling skills in this repo. For the full reference, see [x-twitter-scraper](../x-twitter-scraper/SKILL.md).
> ```

### R06 — Code examples must be runnable

Every skill includes literal HTTP examples with exact endpoint paths, real parameter names, and representative response shapes. No pseudocode. `search-tweets/SKILL.md` shows the live search call with the exact `queryType` enum values and loop termination condition:

> From `skills/search-tweets/SKILL.md:65-71`:
>
> ```
> GET /x/tweets/search?q=<url-encoded query>&queryType=Latest&cursor=<optional>
>
> Supported query parameters: `q` (URL-encoded), `queryType` (`Latest` or `Top`), `cursor`,
> `sinceTime`, `untilTime`, `limit`.
>
> Response: `{ tweets: [...], nextCursor: "..." }`. Loop until `nextCursor` is empty or you
> hit the number you need.
> ```

`monitor-accounts/SKILL.md` shows the full create-monitor JSON body inline rather than referencing a schema file:

> From `skills/monitor-accounts/SKILL.md:42-51`:
>
> ```
> POST /monitors
> {
>   "type": "account",
>   "target": "@elonmusk",
>   "filters": { "include_replies": false, "include_retweets": false },
>   "webhook_url": "https://example.com/webhook"  // optional
> }
> -> { monitor_id }
> ```

The `// optional` annotation and `-> { monitor_id }` response arrow are runnable signal, not decoration — they tell Claude exactly what fields to carry forward.

### R07 — Scope note when related skills exist

Every sibling skill ends with a "Related" section that names neighbors and disambiguates by use case, not just proximity. `find-bangers` does this with a dedicated section:

> From `skills/find-bangers/SKILL.md:45-50`:
>
> ```
> ## Why not just `find-viral-tweets`
>
> `find-viral-tweets` uses absolute thresholds. `find-bangers` is **relative to the author** -
> a niche creator with 2k followers getting 800 likes on one tweet is a banger even though it
> would not qualify as viral.
> ```

Then the Related section confirms the disambiguation in one line:

> From `skills/find-bangers/SKILL.md:55-57`:
>
> ```
> Absolute-threshold viral search: `find-viral-tweets`. Style analysis of the creator:
> `tweet-style`. Full API: [x-twitter-scraper](../x-twitter-scraper/SKILL.md).
> ```

Without "absolute-threshold vs. relative-to-author" Claude cannot choose between the two skills at retrieval time. The disambiguation is made in two places — in the body where the algorithm is explained, and in the Related line where it's compressed to a phrase.

### R08 — Patterns over theory

The master skill teaches the API exclusively through decision trees structured as "given this need → use this endpoint". No abstract description of the API's capabilities — only branching paths to concrete tool calls. Five trees cover read, bulk extraction, write, monitoring, and AI composition:

> From `skills/x-twitter-scraper/SKILL.md:138-159` (first two trees):
>
> ```
> ### "I need X data"
>
> Need X data?
> ├─ Single tweet by ID or URL → GET /x/tweets/{id}
> ├─ Full X Article by tweet ID → GET /x/articles/{id}
> ├─ Search tweets by keyword → GET /x/tweets/search
> ├─ User profile by username → GET /x/users/{username}
> ├─ User's recent tweets → GET /x/users/{id}/tweets
> ...
> └─ DM conversation history → GET /x/dm/{userId}/history
>
> ### "I need bulk extraction"
>
> Need bulk data?
> ├─ Replies to a tweet → reply_extractor
> ├─ Retweets of a tweet → repost_extractor
> ├─ Quotes of a tweet → quote_extractor
> ...
> └─ Tweet search (bulk, up to 1K) → tweet_search_extractor
> ```

The entire 111-endpoint API surface is navigated through intent-keyed branching — Claude reads the branch condition matching the user's request, not a full endpoint catalog.

### R01 — No vague quantifiers without criteria

The error handling section replaces "handle errors appropriately" with an exact retry policy that specifies which status codes, a numeric cap, and the backoff strategy:

> From `skills/x-twitter-scraper/SKILL.md:243`:
>
> ```
> All errors return `{ "error": "error_code" }`. Retry only `429` and `5xx` (max 3 retries,
> exponential backoff). Never retry other `4xx`.
> ```

`find-bangers` applies the same discipline to the banger threshold — a falsifiable ratio rather than "unusually high engagement":

> From `skills/find-bangers/SKILL.md:44-46`:
>
> ```
> 4. Compute engagement rate per tweet = (likes + RTs + replies) / followers.
> 5. Surface tweets with engagement rate more than 3-5x the median for that author. Those are bangers.
> ```

## Worth adopting

**Pattern: Security posture frontmatter.** Every skill in this repo declares its security characteristics in a structured `metadata.security` block — `contentTrust`, `promptInjectionDefense`, `writeConfirmation`, `paymentConfirmation`, `executionModel`, `codeExecution`, `credentialProxy`. The master skill expands this into a full machine-readable block (lines 15–88) covering credential handling, content isolation, 9 specific prompt injection mitigations, payment model, and external dependencies. Evidence: `skills/x-twitter-scraper/SKILL.md:15-88`. Why it would be a useful rule: skills wrapping external APIs with write access or sensitive data need a declared security contract; a structured frontmatter block lets automated tools audit the posture and lets Claude surface relevant warnings without parsing the full security prose section.

**Pattern: ASCII decision tree as primary navigation.** Rather than a prose description of what an API supports, the master skill opens with 5 decision trees that map user intents directly to endpoints. Evidence: `skills/x-twitter-scraper/SKILL.md:138-231`. Why it would be a useful rule: for skills wrapping APIs with 10+ endpoints, decision trees cut the per-invocation token cost of endpoint selection — Claude reads only the matching branch — and prevent hallucinated endpoint names by exhaustively enumerating what exists.
