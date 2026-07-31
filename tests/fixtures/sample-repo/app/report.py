# SPDX-License-Identifier: ISC
"""Seeds D3 Code Correctness & Reliability."""


def last_n(rows, n):
    return rows[len(rows) - n - 1:]


def load(path):
    handle = open(path)
    try:
        return handle.read()
    except OSError:
        pass
