---
description: "Fixture command: runs the go flow using the helper agent and shared steps."
argument-hint: ""
---

# /fixture-broken:go

Follow the shared steps in [missing-partial](shared/missing-partial.md), then dispatch the
[helper](../agents/helper.md) agent to utilize the results.

Always run the checks before committing. Triage the leftovers, then file the outcome in
the audit report.
