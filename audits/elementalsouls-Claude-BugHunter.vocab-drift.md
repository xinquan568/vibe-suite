# NLPM Vocab Drift Advisory

Repo: elementalsouls/Claude-BugHunter
Artifacts scanned: 115
Drift candidates: 8 (high: 0, medium: 8, low: 0)

──────────────────────────────────────────────────────────────────

CANDIDATE 1 — confidence: medium
  Disposition: likely drift
  Terms:
    "validate" — 22 occurrences across 5 files
    "triage" — 16 occurrences across 5 files
  Likely identity: The gate-before-reporting step where a potential finding is checked against the 7-Question Gate before a report is drafted
  Evidence:
    commands/triage.md:1: "Quick 7-Question Gate triage on a finding before writing a report. Kills N/A submissions before they happen. Faster than /validate"
    commands/autopilot.md:57: "5. VALIDATE     7-Question Gate on findings"
    skills/triage-validation/SKILL.md:3: "Finding validation before writing any report — 7-Question Gate (all 7 questions), 4 pre-submission gates"
    commands/validate.md:1: "Validate a finding — runs 7-Question Gate + 4-gate checklist. Kills weak findings before report writing."
    commands/hunt.md:75: "before any report    →  /validate  (7-Question Gate)"
  Suggested canonical: validate
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

CANDIDATE 2 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "recon" — 24 occurrences across 5 files
    "osint" — 14 occurrences across 5 files
  Likely identity: The target data-gathering phase — subdomain enumeration, asset discovery, identity mapping, and intelligence collection
  Evidence:
    docs/architecture.md:1: "Phase 2 — RECON (discovery) Use when: asset enumeration, subdomain discovery, secret hunting, identity-fabric mapping"
    skills/osint-methodology/SKILL.md:3: "5-stage recon pipeline · 29-type asset graph · severity rubric · time budgeting"
    README.md:34: "Recon + OSINT — subdomain enum, identity-fabric mapping, certificate transparency, JS analysis, secret scanning"
    skills/offensive-osint/SKILL.md:1: "15-reference probe arsenal — subdomain enum, identity fabric, secret patterns, sector recon"
    skills/bug-bounty/SKILL.md:267: "## Phase 1: RECON — Standard Recon Pipeline"
  Suggested canonical: recon
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

CANDIDATE 3 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "bug bounty" — 12 occurrences across 5 files
    "wapt" — 8 occurrences across 3 files
    "pentest" — 6 occurrences across 3 files
  Likely identity: The non-red-team engagement mode — web application security testing for a program or client
  Evidence:
    commands/hunt.md:27: "options: 1. Red Team Assessment — critical/high impact ... 2. WAPT / BugHunting — full OWASP coverage, platform/program report"
    commands/hunt.md:66: "mode: wapt / {blackbox|greybox}"
    skills/bb-methodology/SKILL.md:20: "| Pentest (signed SoW / WAPT) | Depends on SoW..."
    skills/hunt-dispatch/SKILL.md:3: "hunt-dispatch mode=wapt box=blackbox|greybox"
    README.md:14: "Bug bounty hunting — web apps, APIs, SaaS..."
  Suggested canonical: wapt
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

CANDIDATE 4 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "hunt" — 30 occurrences across 5 files
    "test" — 15 occurrences across 5 files
  Likely identity: The active vulnerability-testing activity performed against a target in Phase 3
  Evidence:
    docs/architecture.md:30: "Phase 3 — HUNT (active testing) Use when: testing for specific vulnerability classes"
    commands/autopilot.md:52: "4. HUNT     Test P1 endpoints systematically"
    commands/hunt.md:1: "description: Active vulnerability hunting."
    docs/architecture.md:55: "How auto-triggering works: just describe what you're testing"
    skills/bug-bounty/SKILL.md:1: "vulnerability hunting (IDOR, SSRF, XSS, auth bypass...)"
  Suggested canonical: hunt
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

CANDIDATE 5 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "finding" — 20 occurrences across 5 files
    "lead" — 5 occurrences across 2 files
  Likely identity: A potential security issue identified during a hunt, at any stage of confirmation
  Evidence:
    skills/bug-bounty/SKILL.md:441: "## Interesting Leads (not confirmed bugs yet)"
    README.md:202: "KILL returns to Hunt, not to 'end of engagement.' A killed lead doesn't mean..."
    commands/triage.md:1: "Quick 7-Question Gate triage on a finding before writing a report"
    commands/remember.md:1: "Log current finding or successful pattern to hunt memory"
    commands/autopilot.md:57: "5. VALIDATE     7-Question Gate on findings"
  Suggested canonical: finding
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

CANDIDATE 6 — confidence: medium
  Disposition: likely drift
  Terms:
    "confirm" — 12 occurrences across 4 files
    "verify" — 3 occurrences across 1 file
  Likely identity: The act of asserting that a finding is real by producing a real HTTP request that demonstrates it
  Evidence:
    skills/bug-bounty/SKILL.md:79: "1. CONFIRM A     Verify bug A is real with an HTTP request"
    commands/chain.md:111: "Rules Before Pursuing B: 1. Confirm A is REAL first (exact HTTP request + response)"
    skills/triage-validation/SKILL.md:104: "Gate 0: Reality Check: Bug is REAL — confirmed with actual HTTP requests, not code reading alone"
    commands/validate.md:93: "[ ] Confirmed with real HTTP requests (not just code reading)"
  Suggested canonical: confirm
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

CANDIDATE 7 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "remember" — 10 occurrences across 4 files
    "log" — 7 occurrences across 3 files
  Likely identity: Persisting a finding or successful technique to the hunt-memory store for future recall
  Evidence:
    commands/remember.md:1: "description: Log current finding or successful pattern to hunt memory."
    README.md:449: "/remember     Log finding or pattern to hunt memory"
    commands/autopilot.md:79: "Run /remember to log successful patterns to hunt memory"
    commands/hunt.md:99: "session end              →  /remember  (silent)"
    commands/remember.md:10: "## What This Does ... 4. Writes to journal.jsonl (always)"
  Suggested canonical: log
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

CANDIDATE 8 — confidence: medium
  Disposition: co-occurrence drift
  Terms:
    "pattern" — 14 occurrences across 4 files
    "technique" — 7 occurrences across 3 files
  Likely identity: The method or approach by which a vulnerability was discovered — the how-it-was-found for a confirmed finding
  Evidence:
    commands/remember.md:37: "Technique:  numeric_id_swap_with_put_method"
    commands/remember.md:42: "Writes to journal.jsonl (always) + patterns.jsonl (if confirmed + payout > 0)"
    commands/pickup.md:43: "Suggests techniques based on tech stack + pattern DB"
    skills/bug-bounty/SKILL.md:492: "V1: Direct | Change object ID in URL path ... V8: Method swap"
    commands/autopilot.md:81: "Run /remember to log successful patterns to hunt memory"
  Suggested canonical: pattern
  Action options:
    a) Declare canonical in registry.yaml and mark the other as deprecated
    b) Document the distinction if the terms are actually different concepts
    c) Refine an existing canonical's deprecated:[] list to include this synonym

──────────────────────────────────────────────────────────────────

Summary
  Most-drifted concept: The gate-before-reporting step (triage / validate) — highest frequency, most files affected, and blurred by the combined skill name triage-validation
  Files with the most drift: skills/bug-bounty/SKILL.md (candidates 2, 3, 4, 5, 6, 8), commands/hunt.md (candidates 1, 3, 4, 7), docs/architecture.md (candidates 1, 2, 4)
  Suggested next step: Bootstrap a vocabulary skill via /nlpm:vocab-init to establish canonical terms before the corpus grows further
