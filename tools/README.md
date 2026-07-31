# `tools/` — Developer utilities

Helper scripts for working on vibe-suite itself. Not shipped as plugin
functionality and not registered in the manifest.

That exclusion is also why `model-pin-lint.py` does not scan this directory: it lists `tools` in its
own `EXCLUDED` set. A script here that needs a P9 check gets one in its test module rather than
inheriting the repo-wide scan.

| Script | Gate | Invoked by |
|---|---|---|
| `coverage-check.py` | AC-1 — every source artifact is claimed by `docs/disposition.yaml` | the `coverage (AC-1)` CI job |
| `model-pin-lint.py` | AC-9(a) — no pinned model identifiers in shipped artifacts | the `lint` CI job |
| `nl-audit-acceptance.py` | AC-3 — an `/vibe-suite:nl-audit` run met its fixture's detection floor, attribution and mini-membership clauses | an operator, per `tests/fixtures/nl-audit/ACCEPTANCE.md` |
| `gen-source-manifest.py` | — regenerates the vendored source path manifests | by hand, when a source tree is re-pinned |
| `migrate-auditor-data.sh` | — one-shot data migration | by hand |

`nl-audit-acceptance.py` is the one gate here that CI does not invoke, and deliberately so: grading a
run is arithmetic over two files, but *producing* the run needs a live judgment engine, which CI has
no credentials for. Its own correctness is covered by `tests/test_nl_audit_acceptance.py`, which
proves each of its clauses can fail.
