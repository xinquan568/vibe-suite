---
name: conventions-fixturetool
description: Fixture overlay for /vibe-suite:spec-sync tests — a deliberately stale Claude-shaped overlay carrying one seeded instance per tag. Not a real tool overlay.
---

# Fixture tool conventions overlay

**Spec freshness:** verified 2026-01-01 against the fixture docs map (fixture.example/docs)

## 1. Skill layout

Skills live at `.tool/skills/<name>/SKILL.md`. (SEED 5 — CONFIRM: the source states
this same path.)

## 2. Directory placement

STATUS — advisory only: the workspace directory layout is unsettled and two research
passes disagreed on `.tool/` versus `.tools/`; treat placement checks as advisory until
a verification pass lands. (SEED 1 — RESOLVED: the source now settles this as `.tool/`.)

## 3. Legacy switches

The manifest accepts a `legacy_mode` boolean that restores pre-2.0 path resolution.
(SEED 2 — REMOVE: the source documents this flag as withdrawn, with no replacement.)

## 4. Hook events

Event names are lowercase — `pretooluse`, `posttooluse`. (SEED 3 — FIX: the source
states PascalCase, `PreToolUse`/`PostToolUse`, which is the replacement fact.)

The overlay documents no batch event. (SEED 4 — ADD: the source documents
`PostToolBatch`, which falls inside this overlay's declared scope.)

## 5. Telemetry

The manifest carries a `telemetry_endpoint` field. (SEED 6 — UNCLASSIFIED/source-silent:
no first-party page mentions it.)

## 6. Config precedence

Workspace config overrides user config. (SEED 7 — UNCLASSIFIED/source-conflict: the
configuration page and the migration page state opposite precedence.)
