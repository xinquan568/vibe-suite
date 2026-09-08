# SPDX-License-Identifier: ISC
"""`scripts/lib` — the plugin's Python library, as a package (P4 / vibe-215).

The modules here import one another by bare name (`import bridge`) and are imported that way by every
program; `scripts/_bootstrap.py` puts this directory on `sys.path`, so nothing imports `lib.<module>`
yet. This marker exists so later refactors (the bridge split and its siblings) can adopt
package-qualified imports without another bootstrap change.
"""
