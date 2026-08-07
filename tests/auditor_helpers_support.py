# SPDX-License-Identifier: ISC
"""Shared scaffolding for the E8.3 helper test files.

The specification splits helper coverage across ten files by concern. Every one of them
needs the same few primitives, so they live here instead of being duplicated ten times --
duplicated harnesses drift, and a drifted no-op table silently stops proving anything.

The mutation contract these primitives exist to serve:

The issue's acceptance is "all smoke tests green", so these tests ARE the evidence. A test that
passes when its helper is replaced by a no-op establishes nothing, and existence checks,
`--help`, `bash -n`, import success and unasserted invocation all survive that substitution.

Every helper therefore carries, per the E8.3 specification:

  * a **behavioural oracle** — a postcondition of the contract, not a banner or incidental
    output;
  * a **no-op mutant** — the interpreter-correct do-nothing replacement, which the oracle must
    reject. (`exit 0` is a SyntaxError in Python, so a shell no-op would make every Python
    helper's oracle "fail" for the wrong reason and prove nothing. The replacement is chosen
    per helper class.)
  * a **wrong-behaviour mutant** — a plausible mis-implementation, which the oracle must also
    reject. This is what proves the oracle is attached to the contract's meaning rather than to
    some accident of the real helper's output.

One class per helper, named `Test_<helper stem>`, so the mutation harness can address a single
helper's oracle.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "auditor" / "scripts"

#: Interpreter-correct no-ops. A shell `exit 0` does not parse as Python.
NOOP = {
    ".sh": "#!/usr/bin/env bash\n# SPDX-License-Identifier: ISC\nexit 0\n",
    ".py": "#!/usr/bin/env python3\n# SPDX-License-Identifier: ISC\nraise SystemExit(0)\n",
}


def source_and_call(script_text, snippet):
    """Run `snippet` in a bash shell that has sourced `script_text`.

    Sourceable helpers have no CLI, so mutation must go through the same caller shell the real
    oracle uses — otherwise the mutant is exercised differently from the original and the
    comparison proves nothing.
    """
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "helper.sh"
        path.write_text(script_text, encoding="utf-8")
        return subprocess.run(["bash", "-c", f". '{path}'\n{snippet}"],
                              capture_output=True, text=True)
