#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""The one place the plugin's Python puts its library on `sys.path` (P4 / vibe-215).

There is no installed package: `scripts/lib/` is a directory of modules imported by bare name
(`import bridge`, `import config`, …) and several programs import sibling top-level scripts the same
way (`import ls_counts`, `from site_markdown import …`). Before this module, every program prepended
those directories itself — 33 `sys.path.insert` lines in 30 files — and each new CLI copied the idiom.

**Who runs this.** Every *program*: a top-level `scripts/*.py`, a `bin/*` executable, a Python heredoc
in `scripts/migrate/*.sh`, and the three library modules that are also run as programs (`store.py`,
`init_bridge.py`, `unbridge.py`). A program that imports only the standard library needs nothing.
Pure library modules (`advisors`, `bridge`, `config`, `mcp_pin`, …) never run this — they are imported
after some program already did.

**How.** One line, relative to the caller's own file, so it holds whether the file is run as a script,
executed from `bin/`, or loaded by file location into a process whose path holds nothing:

    import runpy, pathlib
    runpy.run_path(str(pathlib.Path(__file__).resolve().parent / "_bootstrap.py"))            # scripts/*.py
    runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "scripts" / "_bootstrap.py"))  # bin/*
    runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "_bootstrap.py"))        # scripts/lib programs

A `python3 -c` one-liner run from the repository root uses the relative path:
`runpy.run_path('scripts/_bootstrap.py')`. `tests/test_bootstrap.py` enforces all of this.

Idempotent: a directory already on `sys.path` is not inserted again, and an existing entry is never
removed or moved. On a path holding neither, the result is the prefix `[scripts/lib, scripts]`.
"""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent

# Inserted at index 0 in turn, so the LAST entry ends up first: scripts/ goes in, then scripts/lib ahead of it.
for _entry in (str(_SCRIPTS), str(_SCRIPTS / "lib")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)
