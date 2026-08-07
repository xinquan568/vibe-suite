# Install

vibe-suite is a Claude Code plugin. Install it from the marketplace entry:

```
/plugin marketplace add xinquan568/vibe-suite
/plugin install vibe-suite
```

Then confirm the installation is healthy:

```
/vibe-suite:doctor
```

`doctor` reports what it found rather than what it expected — missing optional components are
listed as absent, not as failures, so a partial install is legible.

## What you get

| Surface | Command |
|---|---|
| Score an artifact set | `/vibe-suite:score` |
| Cross-component consistency | `/vibe-suite:check` |
| Run natural-language specs | `/vibe-suite:test` |
| Full nine-dimension audit | `/vibe-suite:nl-audit` |
| Repair what an audit found | `/vibe-suite:fix` |

## Requirements

Claude Code, plus Python 3 and Node for the local gates. Nothing else is required for the plugin
itself; the audit pipeline's deployment has its own prerequisites, documented in the repository's
`auditor/README.md`.
