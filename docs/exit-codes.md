# Exit codes

Every program this plugin ships, and what each of its exit codes means. **This page is the registry.**
Each program also states its codes in one marker line in its own header, in its own comment syntax:

    Exit codes: 0 <meaning> · 1 <meaning> · …

`tests/test_exit_codes.py` holds the two together.

## Rules every table assumes

- **A Python program that raises an uncaught exception exits 1**: the interpreter's traceback exit. The
  tables list only the codes a program chooses.
- **A Node program exits 1 on an error it does not handle.** The three CLIs (`codex-runner.mjs`,
  `jobs-cli.mjs`, `preflight-cli.mjs`) run `main` through `scripts/lib/cli.mjs`'s `runMain`, which prints the
  error to stderr and sets exit 1; elsewhere it is Node's own default. The two hooks catch the faults of their
  main flow and exit 0 for those, as their tables say. An error outside those handlers (at module load, or an
  asynchronous stream error such as a closed pipe) follows Node's default.
- **A program built on `argparse` exits 2 on a usage error**, unless its table lists usage under
  another code (`scripts/watch_pr.py` uses 1).
- **A help option prints the program's help and exits 0.** This holds for the 33 programs built on
  `argparse`, and for the seven shell helpers with a `--help` branch (`init.sh`, `unbridge.sh` and the five
  `migrate/*.sh`). The tables list only the other outcomes. The other programs have no help option: they treat
  `--help` as any other argument, with the codes their tables list.
- **The codes are per-program vocabularies, not one global scheme.** `2` is "usage" to
  `scripts/jobs-cli.mjs`, "closed without merge" to `scripts/watch_pr.py`, and "refusal" to
  `scripts/issue2pr_mode_driver.py`. Each is a contract its callers already rely on, so none was
  renumbered to make them agree (vibe-231). A caller reads the table of the program it runs.

## What the test proves, and what it does not

`tests/test_exit_codes.py` proves five things:

1. **Every candidate is classified.** Every file under `bin/`, and every `.py`, `.mjs` and `.sh` file
   under `scripts/`, is either a program in the tables below or a file listed under
   [Not a program](#not-a-program), with the reason. A new file fails the test until it is classified,
   and a table cannot be removed while its file remains.
2. **Each program's header marker equals its table**, code for code and meaning for meaning.
3. **Every `EXIT_*` constant a Python program defines at module level has its value in the table.**
4. **The marker is the header's only statement of an exit number.** No other line of a program's header
   (its module docstring or leading comment block, and the block holding the marker) has a standalone
   integer within the three words after a word beginning with "exit". Two lines are allowed by exact
   text: one describes another program's exit status, and one shows a JSON line the program prints.
5. **No marker replaces text a program prints about itself**: no docstring line a program prints or
   passes to `argparse` is its marker.

It does **not** prove that a literal `return 3` or `sys.exit(3)` matches the table, or that a constant
whose meaning changed was re-described. Those are covered by each program's own behaviour tests where
they exist, and are otherwise a reviewed statement.

## Programs

### `bin/vibe-badge`

| Code | Meaning |
| --- | --- |
| 0 | emitted: the badge (the no-data badge included), or with --attestation the attestation payload |
| 2 | refused: an empty --scope, an unreadable or malformed history, or nothing to attest |

### `bin/vibe-build-case-studies-index`

| Code | Meaning |
| --- | --- |
| 0 | built (an absent corpus builds empty) |
| 2 | refused |

### `bin/vibe-build-docs`

| Code | Meaning |
| --- | --- |
| 0 | built (an absent corpus builds empty) |
| 2 | refused |

### `bin/vibe-build-reference-md`

| Code | Meaning |
| --- | --- |
| 0 | built (an absent corpus builds empty) |
| 2 | refused |

### `bin/vibe-build-site-report-pages`

| Code | Meaning |
| --- | --- |
| 0 | built (an absent corpus builds empty) |
| 2 | refused |

### `bin/vibe-build-vocab-data`

| Code | Meaning |
| --- | --- |
| 0 | built (an absent corpus builds empty) |
| 2 | refused |

### `bin/vibe-check`

| Code | Meaning |
| --- | --- |
| 0 | every requested check ran, zero findings |
| 1 | findings |
| 2 | a requested check could not run, or usage |

### `bin/vibe-report`

| Code | Meaning |
| --- | --- |
| 0 | rendered |
| 2 | refused |

### `scripts/advisor_cli.py`

| Code | Meaning |
| --- | --- |
| 0 | success |
| 2 | refusal: an advisor or bridge error, or usage |

### `scripts/bridge_cli.py`

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | failure: any step (skills, hooks, mcp, mirrors) raised, or the mirror generator is missing, timed out or failed |

### `scripts/check-artifact.sh`

| Code | Meaning |
| --- | --- |
| 0 | nothing to report, or a fault (fail-open) |
| 1 | an advisory note the harness shows the operator; never blocks |

### `scripts/check_engine.py`

| Code | Meaning |
| --- | --- |
| 0 | checked (issues are in the output, not the exit code) |
| 2 | refusal, or usage |

### `scripts/codex-runner.mjs`

| Code | Meaning |
| --- | --- |
| 0 | foreground: the run completed; background: the launch was acknowledged; worker: the job ran (its outcome is in its record) |
| 1 | the run failed, or a launch, claim or finalisation failed |
| 2 | usage, or a refused dispatch: the resolved sandbox or effort (from flags, .vibe-suite.md or the resumed job) is not allowed, or a resume target has no thread id |

### `scripts/config_cli.py`

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | the config was refused, or a set or view failed |
| 2 | an engine outside the schema, or usage |

### `scripts/detect_profile.py`

| Code | Meaning |
| --- | --- |
| 0 | detected |
| 1 | preconditions missing |
| 2 | bad input, or usage |

### `scripts/doctor.py`

| Code | Meaning |
| --- | --- |
| 0 | every finding is [GOOD] |
| 1 | at least one other finding |

### `scripts/gh_boundary_lint.py`

| Code | Meaning |
| --- | --- |
| 0 | clean |
| 1 | a violation |

### `scripts/init.sh`

| Code | Meaning |
| --- | --- |
| 0 | done, or a listing (--list-owned, --list-checkpoints) |
| 1 | error |
| 3 | a helper needs a decision |

### `scripts/issue2pr_mode_driver.py`

| Code | Meaning |
| --- | --- |
| 0 | done |
| 2 | refusal: precondition, containment, illegal transition, bad input, or usage |
| 4 | declaration gap |

### `scripts/issue2pr_slug.py`

| Code | Meaning |
| --- | --- |
| 0 | the slug conforms, or was made |
| 2 | no slug can be made, or it does not conform, or usage |
| 4 | declaration gap |

### `scripts/jobs-cli.mjs`

| Code | Meaning |
| --- | --- |
| 0 | done, including "already finished" cancels |
| 1 | a true answer that is not success (result not finished, nothing to cancel, ambiguous target, invalid or missing record, group outlived escalation, or prune left a job or file it could not vouch for or remove) |
| 2 | usage |

### `scripts/lib/boot_probe.mjs`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | the server could not be spawned, exited, returned an MCP error, timed out, or reported a name or version other than the pinned one, or usage |

### `scripts/lib/bridge.py`

| Code | Meaning |
| --- | --- |
| 0 | written, published or listed |
| 1 | error |
| 2 | usage |
| 3 | publish: the destination already existed |

### `scripts/lib/config.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | a config error |

### `scripts/lib/init_bridge.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | error |
| 2 | unknown subcommand |

### `scripts/lib/scope_tag.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 2 | refused |

### `scripts/lib/store.py`

| Code | Meaning |
| --- | --- |
| 0 | success, including an unparseable or unreadable project file |
| 1 | a state file too damaged to read, or holding a key or value outside the shadowable set |
| 2 | usage |

### `scripts/lib/unbridge.py`

| Code | Meaning |
| --- | --- |
| 0 | removed, or nothing to remove |
| 1 | error |
| 3 | dry run: --confirm is needed |

### `scripts/ls_counts.py`

| Code | Meaning |
| --- | --- |
| 0 | counted |
| 2 | refused |

### `scripts/manifest_entry.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | the manifest is unreadable |
| 2 | schema failure, or usage |
| 3 | profile mismatch, or the profile declares no repo_id or base_branch |

### `scripts/mechanical_fix.py`

| Code | Meaning |
| --- | --- |
| 0 | ran: changes applied, none needed, or reported by --dry-run without writing |
| 2 | the root is not a directory or was refused as a containment root (for example a symlink), or usage |
| 3 | a write was refused by the atomic primitive |

### `scripts/migrate/migrate-config.sh`

| Code | Meaning |
| --- | --- |
| 0 | written, or nothing to do |
| 1 | error |
| 3 | conflicts: the report .vibe-suite-state/migration-conflicts.json is written, and nothing else |

### `scripts/migrate/migrate-history.sh`

| Code | Meaning |
| --- | --- |
| 0 | done, or nothing to do |
| 1 | error |

### `scripts/migrate/migrate-sentinels.sh`

| Code | Meaning |
| --- | --- |
| 0 | done, or nothing to do |
| 1 | error |
| 3 | a decision is required: without --confirm it writes a report and changes nothing else |

### `scripts/migrate/migrate-state.sh`

| Code | Meaning |
| --- | --- |
| 0 | done, or nothing to do |
| 1 | error |
| 3 | a decision is required: the legacy stores disagree |

### `scripts/migrate/survey.sh`

| Code | Meaning |
| --- | --- |
| 0 | surveyed |
| 1 | error: an unknown argument, a missing --workspace value, or not a directory |

### `scripts/mirror-sync.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | a mirror error |

### `scripts/preflight-cli.mjs`

| Code | Meaning |
| --- | --- |
| 0 | every probed engine and runtime available and no probe degraded to `unknown` |
| 1 | a probed engine or runtime (python3, node, git) unavailable, below its floor, or degraded |
| 2 | usage |

### `scripts/profile_lint.py`

| Code | Meaning |
| --- | --- |
| 0 | valid |
| 1 | invalid |
| 2 | unreadable, or usage |

### `scripts/profile_manifest.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | bad input |
| 2 | usage |
| 3 | the write failed |

### `scripts/render_final.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 2 | bad input, or usage |
| 3 | bad root |
| 4 | the write failed |

### `scripts/repair.py`

| Code | Meaning |
| --- | --- |
| 0 | every step fine |
| 1 | at least one step failed |
| 2 | nothing is installed here, or usage |

### `scripts/runs_stats/main.py`

| Code | Meaning |
| --- | --- |
| 0 | done |
| 1 | runs root not found, bad timezone, or config key mismatch |
| 2 | refusal |

### `scripts/score_engine.py`

| Code | Meaning |
| --- | --- |
| 0 | scored |
| 1 | the history append failed |
| 2 | contract refusal, or usage |

### `scripts/session-lifecycle-hook.mjs`

| Code | Meaning |
| --- | --- |
| 0 | success, and any fault its handler catches (fail-open) |
| 2 | usage: an unknown or missing --event |

### `scripts/stop-review-gate-hook.mjs`

| Code | Meaning |
| --- | --- |
| 0 | every decision, and any fault its handler catches: the decision is the output, never the exit code |

### `scripts/trend_engine.py`

| Code | Meaning |
| --- | --- |
| 0 | computed (all three history states) |
| 2 | contract refusal: bad stdin, bad args, or a history path outside the root |

### `scripts/unbridge.sh`

| Code | Meaning |
| --- | --- |
| 0 | removed, or nothing to remove |
| 1 | error, or an unknown argument |
| 3 | dry run: --confirm is needed |

### `scripts/update.py`

| Code | Meaning |
| --- | --- |
| 0 | every stage passed |
| 1 | a stage failed, or retired names leaked |

### `scripts/validate_audit_output.py`

| Code | Meaning |
| --- | --- |
| 0 | valid |
| 1 | invalid, or an unsupported schema |
| 2 | usage |

### `scripts/vocab_extract.py`

| Code | Meaning |
| --- | --- |
| 0 | extracted |
| 2 | not a directory, or usage |

### `scripts/watch_pr.py`

| Code | Meaning |
| --- | --- |
| 0 | merged |
| 1 | usage error, or interrupted |
| 2 | closed without merge |
| 3 | activity newer than the cursor |
| 4 | a completed check failed |
| 5 | timeout |
| 6 | ten consecutive state-probe failures |
| 7 | green and unarmed (--merge-when-green only) |

### `scripts/write_profile.py`

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | bad input |
| 2 | guard refused, or usage |
| 3 | invalid |
| 4 | the write failed |

## Not a program

These files match the candidate rule above but are not run as programs.

| File | Why it is not a program |
| --- | --- |
| `bin/README.md` | documentation |
| `scripts/_bootstrap.py` | a library: imported by the programs, never run itself |
| `scripts/lib/__init__.py` | package marker |
| `scripts/lib/advisors.py` | a library: imported by the programs, never run itself |
| `scripts/lib/claim-budget.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/cli.mjs` | library: defines runMain for the Node CLIs |
| `scripts/lib/config-bridge.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/engine_resolution.py` | a library: imported by the programs, never run itself |
| `scripts/lib/eventlog.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/events.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/fsafe.py` | a library: imported by the programs, never run itself |
| `scripts/lib/gate-toggle.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/jobs.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/mcp_pin.py` | a library: imported by the programs, never run itself |
| `scripts/lib/mirror_tables.py` | a library: imported by the programs, never run itself |
| `scripts/lib/octopus_install.py` | a library: imported by the programs, never run itself |
| `scripts/lib/preflight.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/process.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/reason-frame.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/render.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/resolve.mjs` | a library: imported by the programs, never run itself |
| `scripts/lib/retired_names.py` | a library: imported by the programs, never run itself |
| `scripts/lib/write.mjs` | library: the audited write primitive |
| `scripts/migrate/common.sh` | sourced by the migrate helpers; its exit contract is theirs |
| `scripts/runs_stats/__init__.py` | package marker |
| `scripts/runs_stats/aggregate.py` | a library: imported by the programs, never run itself |
| `scripts/runs_stats/discover.py` | a library: imported by the programs, never run itself |
| `scripts/runs_stats/render.py` | a library: imported by the programs, never run itself |
| `scripts/site_markdown.py` | a library: imported by the programs, never run itself |
