# vibe-suite

A Claude Code plugin for vibe coding — NL-artifact quality tooling, cross-model review, and workflow
loops, bridged to Codex CLI.

Commands are namespaced `/vibe-suite:*`, which follows from `name` in
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json).

> **Status:** scaffold. The manifest pair, directory skeleton and CI are in place; commands, agents
> and skills land issue by issue and register themselves in the manifest as they do.

## Platform support

**POSIX only** — bash, `python3`, `node`, and symlinks are assumed throughout. macOS and Linux are
supported; **Windows is not**, including via cmd/PowerShell. WSL works because it is POSIX. This is a
deliberate v1 constraint inherited from all three projects this one references, stated explicitly
rather than left to be discovered.

## Repository layout

| Path | Holds |
|---|---|
| `.claude-plugin/` | `plugin.json` (component manifest) + `marketplace.json` (installation pointer) |
| `commands/` | `/vibe-suite:*` slash commands, plus shared partials |
| `agents/` | subagent definitions |
| `skills/` | knowledge and workflow skills |
| `hooks/` | plugin hook registrations |
| `scripts/` | shared Bash/Python libraries |
| `bin/` | entry-point executables |
| `templates/` | scaffolding templates |
| `auditor/` | the deployable audit pipeline unit |
| `codex/` | generated Codex CLI mirror — never hand-edited |
| `tests/` | test suites and fixtures |
| `tools/` | developer utilities |
| `docs/` | ADRs, contributor docs, and historical planning records |

## Development

```bash
python3 -m unittest discover -s tests    # run the suite
jq empty .claude-plugin/plugin.json      # validate a manifest
```

CI runs manifest validation, Python/Node lint, and the test suite on every pull request.

## Acknowledgements

This project references the following open-source projects for functionality:

- [cc-suite](https://github.com/xiaolai/cc-suite)
- [nlpm](https://github.com/xiaolai/nlpm)
- [grill-for-claude](https://github.com/xiaolai/grill-for-claude)

Their capabilities are **reimplemented in vibe-suite's own code at functional parity**. This
acknowledgement is collective and deliberate: no per-file or per-function source attribution ships in
this repository, because no source was carried over. Our thanks to their authors for the ideas.

## License

[ISC](LICENSE) © 2026 Eric Y. Liu
