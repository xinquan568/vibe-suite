# `codex-src/` — reverse-delegation skill sources (hand-authored)

The seven Codex-side skills of F9.6 source set (d): instructions the Codex CLI follows to
delegate work back to Claude Code through the pinned `claude-octopus` MCP server, registered as
`vibe-claude-mcp` (E2.6). They are **source artifacts**: the E7.2 mirror-sync generator consumes
this directory and emits the installable mirror into `codex/`, stamping versions and recording
content hashes. Hand-edit HERE, never in `codex/`.

Contracts these sources honor (frozen in `tests/test_codex_src_contracts.py`):

- every call names the `vibe-claude-mcp` server and only tools/arguments the pinned server
  actually serves (`tests/fixtures/claude-octopus-tools-1.2.0.json`);
- read-only delegations (review, plan, audit, verify's fresh session) set
  `permissionMode: plan`; implementation and debugging run with write access;
- no call form ever sets the `model` argument — the delegated Claude session runs on its own
  default (P9);
- delegated content carries a provenance note: the task originates from the outer Codex agent,
  and Claude applies independent judgment.

Re-implemented at functional parity with cc-suite's reverse-delegation skill set (D7:
independently written; the originals are consulted as read-only behavioral references).

## `vibe-roast/SKILL.md.tmpl` — the roast variant's template (M13)

Not an eighth skill: the prose of the generated `codex/skills/vibe-roast/SKILL.md` (the sequential
rendering of `commands/roast.md`), moved out of the generator so that its bytes are a hashed source.
The generator renders it with `str.format` over exactly six plain named placeholders —
`{version}`, `{banner}`, `{criteria}`, `{specialists}`, `{edge}`, `{recon_line}` — computed from the
production tables (roster, criteria link, recon and edge-cases lines); no conversions (`!r`), no format
specs (`:>3`), no positional `{}`; a literal brace is written `{{`/`}}`. Anything else is a generation
error, never a silently changed mirror. The template is **consumed, not mirrored**: the manifest's
`vibe-roast` record keeps `commands/roast.md` as its source and lists the template under `inputs`
with its SHA-256, and `bin/vibe-check --mirrors` fails on any edit to it until the mirror is
regenerated. Its scope grammar is held equal to `commands/shared/scope-parse.md`'s by
`tests/test_mirror_sync.py::ScopeGrammar` (form → resolution; the Codex-native "review" wording is the
one declared difference).
