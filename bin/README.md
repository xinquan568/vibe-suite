# `bin/` — Entry-point executables

Deterministic tools invoked directly or by CI. These are programs, not prompts — they
ship with tests. A `bin/` executable that imports a repository module reaches it through
`scripts/_bootstrap.py` (`runpy.run_path(str(REPO_ROOT / "scripts" / "_bootstrap.py"))`, the one place
the library path is set); a stdlib-only one, like `vibe-report`, needs nothing.

- `vibe-check` — the deterministic CI validator (F4.4, ADR-0001): structural plugin
  checks, `--report` audit-report schema validation, exit 0/1/2. Run it on a plugin
  root: `python3 bin/vibe-check .` — see `templates/` for the pre-commit and CI wiring.
