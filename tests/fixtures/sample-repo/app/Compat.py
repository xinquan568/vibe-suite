# SPDX-License-Identifier: ISC
"""Seeds D4 Compliance & Standards."""

import imp          # deprecated since 3.4, removed in 3.12


def LoadModule(Name, Path):
    return imp.load_source(Name, Path)
