# `tests/` — Tests and fixtures

Test suites and their fixtures. Run the full suite — exactly what CI's `test` job runs:

    python3 -m unittest discover -s tests

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
