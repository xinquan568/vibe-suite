# vibe-30 worksheet — hand-derived oracle for `bin/vibe-check`

Authored BEFORE any engine code (the S3 oracle-first discipline). Every fixture is
otherwise-clean so its expected findings are EXACTLY its seeds; every determination cites
the frozen plan's design decisions (D2–D6) and their governing texts (F4.4, ADR-0001,
plugin-discover.md, conventions-claude §6–§7).

## Finding line format and class order

Text findings render `<class>: <path>: <detail>`. Deterministic class order (D5):
manifest-vs-disk, unregistered-skill, frontmatter, name-dir, hook-case, monorepo,
version, mirrors, report; within a class: path, then detail.

## Exit codes per case (D6)

0 = every requested check ran, zero findings. 1 = ≥1 finding (all structural classes;
--report ValidationError on a PARSED document). 2 = a requested check could not run:
bad dir; root neither plugin nor monorepo; unparsable plugin.json; structurally unusable
parsed manifest (non-object; commands/agents/skills not lists of strings; hooks neither
string nor object); unparsable configured hooks file or marketplace.json; unreadable OR
non-JSON report file; UnsupportedSchemaError; --mirrors without its manifest; usage.

## Mode matrix (D4)

| Invocation | Behavior | Root requirement |
|---|---|---|
| (none) | structural checks on CWD | yes |
| `dir` | structural checks on dir | yes |
| `--report P` | REPORT-ONLY: no structural checks | none — any CWD |
| `dir --report P` | both; findings merge | yes |
| `--mirrors [dir]` | directory mode always engaged; pre-E7.2 → refusal exit 2 | yes |
| `--report P --mirrors` | directory mode (default CWD) + report; pre-E7.2 the mirrors refusal (2) governs | yes |

`--json` report-only: `"root": null`; structural classes false in `checked`.

## Fixtures (10 artifacts, 9 classes; hook class carries two)

| Fixture | Seeds | Expected findings (exact) | Exit |
|---|---|---|---|
| `manifest-vs-disk/` | manifest registers `./commands/ghost.md` (absent); disk carries unregistered `agents/stray.md`; `commands/real.md` registered+clean | `manifest-vs-disk: agents/stray.md: on disk but not registered in plugin.json` · `manifest-vs-disk: commands/ghost.md: registered in plugin.json but absent on disk` | 1 |
| `unregistered-skill/` | `skills/orphan/SKILL.md` present; manifest `skills` omits it | `unregistered-skill: skills/orphan: SKILL.md present but not in plugin.json skills[]` | 1 |
| `frontmatter/` | `commands/noblock.md` no block; `agents/nodesc.md` block missing description; `commands/shared/nodesc.md` has `user-invocable: false` but no description; `commands/shared/invocable-true.md` has description but `user-invocable: true` (the value must be exactly false) | `frontmatter: agents/nodesc.md: missing required key 'description'` · `frontmatter: commands/noblock.md: missing frontmatter block` · `frontmatter: commands/shared/invocable-true.md: key 'user-invocable' must be false` · `frontmatter: commands/shared/nodesc.md: missing required key 'description'` | 1 |
| `name-dir/` | `skills/alpha/SKILL.md` carries `name: beta` (registered) | `name-dir: skills/alpha/SKILL.md: name 'beta' does not match directory 'alpha'` | 1 |
| `hook-case/` | manifest `hooks: ./hooks/hooks.json`; config `{"hooks": {"postToolUse": [], "TotallyNewEvent": []}}` — the unknown exact name is the §6 open-world ANTI-seed | `hook-case: hooks/hooks.json: event 'postToolUse' should be 'PostToolUse'` (exactly one) | 1 |
| `hook-case-configured/` | manifest `hooks: ./config/custom-hooks.json`; that file `{"hooks": {"sessionstart": []}}` | `hook-case: config/custom-hooks.json: event 'sessionstart' should be 'SessionStart'` | 1 |
| `monorepo/` | NO root `.claude-plugin/`; `sub-a/`, `sub-b/` each a plugin | `monorepo: sub-a: sub-plugin root (run vibe-check per sub-plugin)` · same for `sub-b` | 1 |
| `version/` | plugin.json `name: fixture-version`, `version: 0.0.1`; marketplace entry same name `version: 9.9.9` | `version: .claude-plugin/marketplace.json: plugin 'fixture-version' version '9.9.9' != plugin.json version '0.0.1'` | 1 |
| `mirrors-missing/` | minimal valid plugin; run WITH `--mirrors` | (stderr) `vibe-check: mirror hash manifest not found; ships with E7.2/F9.6` — the deferred class's CURRENT failing case | 2 |
| `report-invalid.json` | severity `"[WRONG]"` in an otherwise-conforming report | one `report:` finding carrying the validator's ValidationError text | 1 |

Anti-seeds: every fixture's non-seeded surfaces are clean (verified by hand against D3);
`hook-case`'s unknown event yields NO finding; `version/`'s marketplace parse is valid;
the suite itself (repo root) seeds nothing — expected `vibe-check: clean`, exit 0 (rung 3).

`schema-unsupported.json` (module-seam input, not a CLI fixture): the canonical schema
plus a `pattern` keyword — `validate()` must raise UnsupportedSchemaError; vibe-check's
boundary maps it to exit 2.

## Module-seam expectations (hand-derived, not CLI cases)

- Inline-object hooks: `check_hook_case(root, {"name": "x", "hooks": {"hooks":
  {"postToolUse": []}}})` yields exactly one finding whose detail names
  `'PostToolUse'` — the inline branch shares the event-map reader with the path branch.
- `validate_report(sample, schema=schema-unsupported.json)` → `(2, [])`.

## --report per-case table (hand-derived)

| Input | Exit | Rationale (D6) |
|---|---|---|
| `tests/fixtures/sample-report.json` | 0 | conforms (mandated passing case); also from a non-plugin CWD |
| `report-invalid.json` | 1 | PARSED document the canonical schema rejects (finding carries the validator's message) |
| a non-JSON file | 2 | no instance exists — the check could not run |
| an absent/unreadable path | 2 | I/O — the check could not run |
| invalid UTF-8 bytes | 2 | the stream never decodes — the check could not run |

## Containment and registration expectations (hand-derived)

- Manifest entries that are absolute or escape the root (`../…`) are findings
  ("escapes the plugin root") and are never read or registered — including a `hooks`
  path, whose target file must never be opened.
- Registration is PER COMPONENT CLASS: `commands/x.md` listed only under `agents[]` is
  an unregistered command; a `skills[]` entry may name the directory OR its SKILL.md.
- Invalid UTF-8 in plugin.json → exit 2 (could-not-run), matching the report row above.

## --json golden (`expected-manifest-vs-disk.json`)

Invocation fixed at repo root: `bin/vibe-check tests/fixtures/vibe-check/manifest-vs-disk --json`.
`root` is the dir AS GIVEN; findings sorted per D5; `checked`: all structural classes
true, `mirrors` false (not requested), `report` false (not requested). Verdict
`"2 findings"`.
