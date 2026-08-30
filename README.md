# vibe-suite

A Claude Code plugin for vibe coding — NL-artifact quality tooling, cross-model review, and workflow
loops, bridged to Codex CLI.

Commands are namespaced `/vibe-suite:*`, which follows from `name` in
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json).

> **Status:** the suite installs and runs. The `auditor/` unit — workflows, helper scripts
> and rulebook (see [`auditor/README.md`](auditor/README.md)) — is **implemented and tested**
> under the repo's strictest test contract (an oracle plus a no-op and a wrong-behaviour
> mutant per helper): working code, not a docs stub. What remains is wiring it into
> `.github/workflows/` for deployment, tracked separately. The catalog below is what ships today.

## Platform support

**POSIX only, Python 3.11+** — bash, `python3` (3.11 or newer), `node`, `git`, and symlinks are
assumed throughout. `/vibe-suite:preflight` reports all three runtimes, and
`VIBE_SUITE_CLAIM_BUDGET_MS` raises or lowers the worker claim-handshake budget (default 5000 ms,
maximum 300000; an invalid value falls back to the default with a notice). macOS and Linux are
supported; **Windows is not**, including via cmd/PowerShell. WSL works because it is POSIX. This is a
deliberate v1 constraint inherited from all three projects this one references, stated explicitly
rather than left to be discovered.

**Node ≥ 18.** The shipped `.mjs` modules stay inside that floor and use **no top-level await**, so
they load under any runtime meeting it. The floor is declared here rather than in
`.claude-plugin/plugin.json`, whose schema has no `engines` field, and there is no `package.json` —
the suite ships no Node dependencies. `tests/node/no-top-level-await.mjs` enforces the rule with
Node's own parser; `node --check` does **not**, because it accepts top-level await in `.mjs`.

Process control assumes POSIX signals: the job engine enforces deadlines by escalating
SIGTERM→SIGKILL, and background jobs run detached in their own process group.

## Repository layout

| Path | Holds |
|---|---|
| `.claude-plugin/` | `plugin.json` (component manifest) + `marketplace.json` (installation pointer) |
| `commands/` | `/vibe-suite:*` slash commands, plus shared partials — see note below |
| `agents/` | subagent definitions — see note below |
| `skills/` | knowledge and workflow skills |
| `hooks/` | plugin hook registrations |
| `scripts/` | shared Bash/Python libraries |
| `bin/` | entry-point executables |
| `templates/` | scaffolding templates |
| `auditor/` | the deployable audit pipeline unit |
| `codex/` | generated Codex CLI mirror — never hand-edited |
| `tests/` | test suites and fixtures |
| `tools/` | developer utilities |
| `schemas/` | JSON Schemas for machine-readable contracts (e.g. audit output) |
| `docs/` | ADRs, contributor docs, and historical planning records |

> **`commands/` and `agents/` carry inert `.gitkeep` markers, not READMEs.** Claude Code scans those
> two directories for flat component files, so a bare `.md` in either is parsed as a command or agent
> and fails `claude plugin validate --strict` for want of frontmatter. Their descriptions live in the
> table above instead. Every other skeleton directory carries an explanatory `README.md`.

## Development

```bash
python3 -m unittest discover -s tests               # run the suite
jq empty .claude-plugin/plugin.json                 # validate a manifest
python3 scripts/validate_audit_output.py <report>   # validate an audit report
python3 tools/model-pin-lint.py                     # scan for pinned model identifiers (P9)
```

`model-pin-lint` enforces P9: shipped artifacts never name a versioned model ID. It scans **tracked
files only**, so a newly created file is invisible to it until `git add` — run the lint after
staging, not before. Scope is an explicit allowlist of top-level entries in the tool itself;
`docs/`, `tests/`, `tools/` and `.github/` are outside it, and an entry in neither list is an error
rather than a silent pass, so adding a directory fails the suite until it is classified.

Validate the plugin manifests — note these are two separate targets:

```bash
claude plugin validate . --strict                          # marketplace.json
claude plugin validate .claude-plugin/plugin.json --strict # plugin.json + component scan
```

CI runs manifest validation, Python/Node lint, a pinned-model-identifier scan, and the test suite on
every pull request.

## Install

**From the marketplace** (in Claude Code):

```
/plugin marketplace add xinquan568/vibe-suite
/plugin install vibe-suite@vibe-suite
```

The marketplace entry and the plugin resolve from the same repository and the same commit, so
what you install always matches the listing you installed it from.

**From a clone**, if you would rather read the source first:

```bash
git clone https://github.com/xinquan568/vibe-suite.git
```

then, in Claude Code, `/plugin marketplace add /path/to/vibe-suite` followed by the same
`/plugin install` line.

**Then initialize and verify.** Installing populates Claude Code's plugin cache; it does not
touch your project. Run these in the project you want the suite to work on, in this order:

```
/vibe-suite:init      # writes the config, bridges, and sentinels this project needs
/vibe-suite:doctor    # reports health — run it after init, not before
```

`doctor` reports `not-initialised` on a project where `init` has not run yet, which is
expected rather than a fault.

Prerequisites are the ones in [Platform support](#platform-support) above: POSIX, Python
3.11+, Node ≥ 18.

**Trying it without touching your setup.** `CLAUDE_CONFIG_DIR` points Claude Code at a
throwaway profile, so an install can be exercised and discarded:

```bash
export CLAUDE_CONFIG_DIR=$(mktemp -d)
claude plugin marketplace add /path/to/vibe-suite
claude plugin install vibe-suite@vibe-suite
claude plugin list        # Status: enabled
```

## Command catalog

The manifest registers **29 commands, 14 agents, 24 skills** (the exact lists live in
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json); `tests/test_doc_accuracy.py`
holds these counts equal to the manifest and the files on disk). By group:

- **Audit & quality** — `nl-audit`, `score`, `check`, `fix`, `test`, `trend`, `report`,
  `security-scan`, `vocab`, `spec-sync`, `roast` (code interrogation), `bug-analyze`.
- **Lifecycle & bridge** — `init`, `doctor`, `repair`, `update`, `config`, `bridge`,
  `unbridge`, `preflight`, `advisor`.
- **Cross-model & jobs** — `delegate`, `continue`, `jobs`, `refresh-knowledge`.
- **Workflow loops** — `issue2pr`, `refine-proposal`, `runs-stats`, `ls`.

## Migrating from cc-suite / nlpm / grill

Old commands map to their vibe-suite successors as follows (derived from
[`docs/disposition.yaml`](docs/disposition.yaml)):

| Old | New | Notes |
|---|---|---|
| `/cc-suite:init` | `/vibe-suite:init` | merged with nlpm's init |
| `/cc-suite:update` | `/vibe-suite:update` | |
| `/cc-suite:repair` | `/vibe-suite:repair` | |
| `/cc-suite:diagnose` | `/vibe-suite:doctor` | renamed |
| `/cc-suite:setup` | `/vibe-suite:config` | renamed |
| `/cc-suite:preflight` | `/vibe-suite:preflight` | |
| `/cc-suite:unbridge` | `/vibe-suite:unbridge` | |
| `/cc-suite:bridge-hooks` | `/vibe-suite:bridge` | one command, `hooks` subcommand |
| `/cc-suite:bridge-mcp` | `/vibe-suite:bridge` | `mcp` subcommand |
| `/cc-suite:bridge-skills` | `/vibe-suite:bridge` | `skills` subcommand |
| `/cc-suite:add-agent` | `/vibe-suite:advisor` | `add` subcommand |
| `/cc-suite:list-agents` | `/vibe-suite:advisor` | `list` subcommand |
| `/cc-suite:remove-agent` | `/vibe-suite:advisor` | `remove` subcommand |
| `/cc-suite:audit` | `/vibe-suite:roast` | `--engine codex`; nine dimensions preserved |
| `/cc-suite:audit-fix` | `/vibe-suite:fix` | merged with nlpm's fix |
| `/cc-suite:verify` | `/vibe-suite:fix` | verification folded into the fix loop |
| `/cc-suite:audit-agent` | `/vibe-suite:nl-audit` | `--type agent` |
| `/cc-suite:audit-command` | `/vibe-suite:nl-audit` | `--type command` |
| `/cc-suite:audit-nlp` | `/vibe-suite:nl-audit` | `--type repo` |
| `/cc-suite:audit-plugin` | `/vibe-suite:nl-audit` | `--type plugin` |
| `/cc-suite:audit-rules` | `/vibe-suite:nl-audit` | `--type rules` |
| `/cc-suite:audit-skill` | `/vibe-suite:nl-audit` | `--type skill` |
| `/cc-suite:implement` | `/vibe-suite:delegate` | renamed |
| `/cc-suite:review-plan` | the `refine-proposal` skill | `--review-mode single` |
| `/cc-suite:bug-analyze` | `/vibe-suite:bug-analyze` | |
| `/cc-suite:continue` | `/vibe-suite:continue` | |
| `/cc-suite:cancel` | `/vibe-suite:jobs` | `cancel` subcommand |
| `/cc-suite:result` | `/vibe-suite:jobs` | `result` subcommand |
| `/cc-suite:status` | `/vibe-suite:jobs` | `status` subcommand |
| `/cc-suite:refresh-knowledge` | `/vibe-suite:refresh-knowledge` | |
| `/grill:roast` | `/vibe-suite:roast` | styles and add-ons preserved |
| `/nlpm:ls` | `/vibe-suite:ls` | |
| `/nlpm:score` | `/vibe-suite:score` | |
| `/nlpm:fix` | `/vibe-suite:fix` | |
| `/nlpm:check` | `/vibe-suite:check` | |
| `/nlpm:test` | `/vibe-suite:test` | |
| `/nlpm:vocab-drift` | `/vibe-suite:vocab` | `drift` subcommand |
| `/nlpm:vocab-init` | `/vibe-suite:vocab` | `init` subcommand |
| `/nlpm:security-scan` | `/vibe-suite:security-scan` | |
| `/nlpm:trend` | `/vibe-suite:trend` | |
| `/nlpm:report` | `/vibe-suite:report` | |
| `/nlpm:init` | `/vibe-suite:init` | merged with cc-suite's init |
| `/nlpm:spec-sync` | `/vibe-suite:spec-sync` | |

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
