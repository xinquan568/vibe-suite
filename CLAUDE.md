# CLAUDE.md — working in the vibe-suite repository

Project memory for Claude Code sessions developing THIS plugin. User-facing documentation is
`README.md`; privacy posture is `PRIVACY.md`.

## Layout, short form

`commands/` `/vibe-suite:*` slash commands (+ `commands/shared/` partials) · `agents/`
subagents · `skills/` knowledge + workflow skills · `codex-src/` hand-authored Codex-side
skill sources · `codex/` the GENERATED Codex mirror — never hand-edit; change sources and run
`python3 scripts/mirror-sync.py generate` · `scripts/` shared libraries (`scripts/lib/`) ·
`bin/` executables · `hooks/` plugin hooks · `schemas/` JSON contracts · `templates/`
scaffolding · `auditor/` the S8 audit unit · `tests/` the suite · `tools/` dev utilities.

## The gate battery (run before any commit)

```bash
python3 -m unittest discover -s tests    # the whole suite (CI runs it sharded 4-way; see below)
node --test tests/node/*.test.mjs        # the Node suite (hooks, job store, events, …)
python3 tools/model-pin-lint.py          # P9: no pinned model ids in shipped artifacts
bash tools/legacy-string-sweep.sh        # AC-6: no retired namespace in shipped text
bin/vibe-check .                         # structural checks
bin/vibe-check . --mirrors               # codex/ staleness (both hash directions)
```

> **Prerequisites for the full local run:** `node` (the Node suite) and `ruby` (the auditor
> workflow-YAML gate in `tests/test_auditor_workflows.py` parses with `ruby -ryaml`; without
> ruby those YAML-validity assertions green-skip rather than run). `tests/run-parallel.sh`
> runs the Python modules in parallel locally (the same modules CI shards four ways).

## Load-bearing invariants

- **`codex/` is generated.** `MIRROR-MANIFEST.json` binds every file to its source bytes;
  hand-edits fail `--mirrors`. Sources: the 21 knowledge skills, `commands/roast.md`, the
  six roast agents, `codex-src/`, the copied dependencies
  (`schemas/audit-output.schema.json`, `commands/shared/{classify,discover}.md`), and
  `.claude-plugin/plugin.json` (the version stamp + README record).
- **The pin pair.** `scripts/lib/claude-octopus-pin.txt` (exact semver) is the shipped
  state; exactly one of {pin, pending marker} may exist. Boot-verify compares the server's
  self-report to the pin — name AND version.
- **Skills must be registered.** Every `skills/*/SKILL.md` appears in
  `.claude-plugin/plugin.json`; `bin/vibe-check` flags strays.
- **Write discipline.** PYTHON (and embedded-shell-Python) mutation under `scripts/`
  routes through `scripts/lib/bridge.py`'s audited primitives —
  `tests/test_write_discipline.py` enforces this by AST for that surface; the Node surface
  uses `scripts/lib/write.mjs` and is explicitly outside that test's scope (its own
  discipline is tracked separately).
- **Cross-pinned pairs.** Two separate pin pairs exist: the MIRROR inventory (generator
  tables ↔ vibe-check `MIRROR_EXPECTED`, held identical by `test_mirror_sync.py`) and the
  RETIRED patterns (`retired_names.RETIRED` ↔ the sweep's list, held by
  `test_legacy_sweep.py`). Extend each pair together; they are not one table.

## Conventions

Conventional Commits (`<type>(<scope>): <subject>`); every change traces to a `vibe-<N>`
issue — branch `<user>/ai/vibe-<N>-<slug>`, PR title ends `(vibe-<N>)`, body `Closes #<N>`.
Tests first (TDD/P6); stdlib only — no new dependencies; new `.sh`/`.py`/`.js`/`.ts` files
carry `SPDX-License-Identifier: ISC` in their first three lines. Never pass `--no-verify`.
Documentation counts are held to disk by `tests/test_doc_accuracy.py` — update the docs and
the manifest together.
