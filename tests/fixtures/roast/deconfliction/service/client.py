"""Fixture source carrying ONE seeded defect whose ownership is contested (E4.2 / vibe-36).

The defect is config management: `endpoint` and `timeout` are read from a config file with no
validation, no default, and a swallowed KeyError that leaves `timeout` as None on the failure path.

It sits at a module boundary and is reached from the entry point, which is why a reviewer scanning
for architecture concerns is drawn to it. Per F3.4 error-handling is the primary owner of config
management, and per F3.3 architecture defers config findings to it -- so the correct attribution is
error-handling. That disagreement is the whole point of the fixture.
"""

import json


def load_settings(path):
    raw = json.load(open(path))
    endpoint = raw["endpoint"]
    try:
        timeout = raw["timeout"]
    except KeyError:
        pass
    return endpoint, timeout


def call(path):
    endpoint, timeout = load_settings(path)
    return "GET %s (timeout=%s)" % (endpoint, timeout)
