# SPDX-License-Identifier: ISC
"""Seeds D1 Redundant & Low-Value Code."""

import hashlib          # unused
import json


def _unused_helper(rows):
    """Unreachable: nothing calls this."""
    return [r for r in rows if r]


# def old_render(rows):
#     return "\n".join(str(r) for r in rows)


def render(rows):
    return json.dumps(rows)
