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
