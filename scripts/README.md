# `scripts/` — Shared libraries

Bash and Python helpers used by commands, hooks and CI. New `.sh`/`.py` files
carry an ISC SPDX header in the first 3 lines.

`runs_stats/` is a package: `main.py` is the program (`python3 scripts/runs_stats/main.py`),
the other modules are libraries that never touch `sys.path` — programs bootstrap, libraries do not.
