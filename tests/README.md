# `tests/` — Tests and fixtures

Test suites and their fixtures. Run the full suite locally (CI runs the same modules across its four `test shard` jobs, fanned in to the required `test` context):

    python3 -m unittest discover -s tests

The Node suite (hooks, job store, …) runs separately:

    node --test tests/node/*.test.mjs

CI runs the Python suite **sharded four ways** (`ci.yml`'s `test shard N` jobs, fanned in to
the required `test` context); locally `tests/run-parallel.sh` runs the modules in parallel.
The auditor workflow-YAML gate needs **`ruby`** on `PATH` (it parses with `ruby -ryaml`); without it those YAML-validity assertions green-skip.

Per TDD/P6 a failing test is written before the behaviour it covers.

## Fast inner loop (skip the auditor contract tier)

The 20 `tests/test_auditor_*.py` modules are the repo's strictest, slowest tier — an oracle
plus a no-op and a wrong-behaviour mutant per helper. **CI always runs the full suite**; for a
quick local loop you can run everything except that tier from the repo root:

    python3 -m unittest $(cd tests && ls test_*.py | grep -v '^test_auditor_' | sed 's/\.py$//' | sed 's/^/tests./')

The exclusion keys on the `test_auditor_` filename prefix; `tests/test_doc_accuracy.py` pins the
auditor tier against a reviewed manifest (`FastTestTier.AUDITOR_TIER`) and requires the on-disk
`test_auditor_*.py` set to equal it, so a non-auditor module cannot silently acquire the prefix
(and be skipped) and a new auditor module cannot be added without a deliberate manifest update.

## The real-codex contract probe (opt in; one call)

Every other test drives a **fake** codex, which is why the suite is fast and free — and why the real event vocabulary
is otherwise unverified. `tests/test_codex_contract.py` runs the installed binary **once** and asserts that the stream
still carries what `scripts/lib/events.mjs` extracts from it, **through that module** rather than through a second
parser:

    VIBE_SUITE_REAL_CODEX=1 python3 -m unittest tests.test_codex_contract.RealCodexContract -v

Without that variable it skips immediately, so an ordinary `unittest discover` — and every CI shard — spends nothing.
`VIBE_SUITE_CODEX_BIN` points at another binary; `VIBE_SUITE_PROBE_TIMEOUT_MS` moves the deadline (120000 by default).
The weekly `codex-contract` job in `.github/workflows/self-check.yml` runs the same command, with each step guarded by
the `OPENAI_API_KEY` secret: a repository without it sees a green, visibly-skipped job.

**A failure means the contract drifted; only a named cause skips.**

| Outcome | Verdict |
|---|---|
| the opt-in is unset, or the binary is absent | skip |
| the deadline passes and the process group is confirmed gone | skip |
| a `turn.failed` the repository's own classifier calls a quota | skip |
| the turn did not complete **and** the failure or stderr says it was refused for authentication | skip |
| a completed turn missing any mandatory observation, or output that explains nothing | **fail** |
| the process group outlives `SIGKILL` | **fail** ("cleanup unconfirmed") |

The mandatory observations are a terminal `turn.completed`, a thread id, an agent message, and the three usage fields
`billableTokens` subtracts. `reasoning_output_tokens` and the tool events (`item.started`, `command_execution`) are
**optional**: absent they prove nothing, present they are checked through `scripts/runs_stats/discover.py`, the
consumer that reads them. A renamed *optional* event is indistinguishable from an absent one; what catches a real
vocabulary change is the mandatory set. An upstream outage will turn the weekly job red — the safe direction, since a
red job is investigated and a silent green is not.

## The reproducibility gates, and the census that reports them (opt in)

Two gates check that a vendored manifest still describes the tree it stands for, and **both need a root that
lives outside this repository**:

| Variable | Points at | Gate |
|---|---|---|
| `VIBE_SUITE_PINNED_TREES` | the directory holding the `cc-suite` / `grill-for-claude` / `nlpm` checkouts | `TestManifestsAreReproducible` |
| `VIBE_SUITE_WORKSPACE_SKILLS` | the live `.claude/skills` directory | `TestWorkspaceManifestIsReproducible` |

Each obeys the same three-way contract, and **key membership decides, not the value**:

| State | Outcome |
|---|---|
| unset | **skip**, with a reason that names the variable and what to point it at |
| set to a path that works | the gate runs |
| set and empty, or set to something that is not a checkout / directory | **fail** — never a skip |

That last row is the load-bearing one. CI's shard job sets `VIBE_SUITE_PINNED_TREES` (`ci.yml`), so CI can never
green-skip the pinned-tree gate; if the fetch step did not run, the gate goes red rather than quietly passing.

**Neither root is guessed.** Until vibe-228 the pinned-tree root fell back to layout defaults — the directory beside
the checkout, then a four-parent climb — and the workspace root was a hard-coded four-parent path to `.claude/skills`.
That made whether a gate ran depend on what happened to sit next to your checkout, silently enrolled anything named
like a pinned clone as the tree the manifests were verified against, and left the workspace gate executable on exactly
one machine, where everywhere else it green-skipped. A local run now reads nothing outside the repository.

Because a skip is the honest answer on a machine with no roots, the skip has to be **visible**:

    python3 tests/reproducibility_census.py

It runs both gates and prints every skip by test id and reason, with a count derived from `unittest`'s result object
rather than from its printed output. Under GitHub Actions it appends the same table to `$GITHUB_STEP_SUMMARY`. Exit
status is 0 unless a gate **failed or errored** — a counted skip is not a failure. The weekly `reproducibility` job in
`.github/workflows/self-check.yml` runs exactly this command and sets neither variable, so the run summary states each
week which reproducibility gates did not execute and why.

## Behaviour-only inner loop (the contract tier)

A separate axis: about a quarter of the Python tests execute nothing — they read markdown, JSON or source text and
assert on it (the **contract** tier). The rest run a process or call repository code (the **behaviour** tier). To run
one tier from the repo root:

    python3 tests/tiers.py behaviour     # or: contract, all; add -v / -f as for unittest
    python3 tests/tiers.py list          # every test class and its tier (--json for tools, --why for the reason)

The tier is **computed from the test source, not tagged**, and the rule is an **allowlist**: a class is contract only
when everything it references resolves to something known not to execute — a listed builtin, a listed standard-library
module (`os`, `sys` and `unittest` judged per attribute, so `os.path` is fine and `os.system` is not), a test helper
imported from the module that defines it, a method of its own class, or a listed method of a value. Anything the rule
cannot resolve — an unlisted name, a wildcard import, reflection, a computed `getattr`, a string-driven load, a
`mock.patch` of a string target — makes the class behaviour. A class may set `tier = "behaviour"` to force the safe
side; there is no way to force *contract*, because an allowlist a class can opt out of is not one. To widen the rule,
extend the lists at the top of `tests/tiers.py`: an omission only costs inner-loop speed, never a skipped test.

The contract tier runs **under a guard**, so a class the rule gets wrong fails loudly instead of being skipped quietly:
while `contract` runs, an audit hook refuses every process start and records every load of repository code, and on
Python 3.12+ `sys.monitoring` records every call into repository code outside `tests/`. Installing a profiler, a tracer,
another monitoring tool or an audit hook during that run is itself a violation, because each one suspends the guard's
view. Any violation prints a table and the command exits 1. On Python 3.11 there is no `sys.monitoring`, so calls into
already-loaded repository code are not detected and the command says so. `behaviour` and `all` run unguarded, which is
where a test that must profile or trace belongs.

The module set is exactly CI's (every top-level `tests/test_*.py`), and `tests/test_tiers.py` holds that the two tiers
partition it. **CI still runs both tiers** — everything.
