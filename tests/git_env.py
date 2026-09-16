# SPDX-License-Identifier: ISC
"""One environment for every git the Python test suite spawns (vibe-318).

Every `git commit` spawns `git maintenance run --auto`; on git >= 2.47 that process DETACHES by
default (`maintenance.autoDetach`), and on git >= 2.55 the default strategy repacks a repository
with more than 256 loose objects — after `commit` has returned. A test that commits a copy of
this repository and then removes its `TemporaryDirectory` races that detached repack, and lost
once on CI: `OSError: Directory not empty: '.git'` (issue #318).

The fix is not in cleanup: it is to keep git from spawning maintenance in test repositories at
all. `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` is the channel, because git reads
it in every process it starts (the detached child included), nothing in this tree scrubs it
(`scripts/stop-review-gate-hook.mjs` scrubs `GIT_CONFIG_PARAMETERS`), and it composes with a
caller's own entries by appending. Repository config would need every `git init` site to remember
it; this needs one import per module, which `tests/test_git_maintenance.py` pins.

Import this module in any test module that spawns git; the import installs the keys into
`os.environ` once. A call that hands git an explicit `env=` dictionary must merge
`GIT_NO_AUTO_MAINTENANCE` into it (or build it from `os.environ`); the same test pins that.
"""
import os

__all__ = ["GIT_NO_AUTO_MAINTENANCE", "quiet_git_env", "install"]

#: The settings, in order. `maintenance.auto=false` stops the spawn on every git that has the
#: `maintenance` command (2.29+); `gc.autoDetach=false` keeps any remaining `gc --auto` in the
#: foreground on a git that still calls it directly.
SETTINGS = (("maintenance.auto", "false"), ("gc.autoDetach", "false"))

#: The keys as they read with no pre-existing GIT_CONFIG_COUNT — for merging into explicit dicts.
GIT_NO_AUTO_MAINTENANCE = {"GIT_CONFIG_COUNT": str(len(SETTINGS))}
for _i, (_k, _v) in enumerate(SETTINGS):
    GIT_NO_AUTO_MAINTENANCE[f"GIT_CONFIG_KEY_{_i}"] = _k
    GIT_NO_AUTO_MAINTENANCE[f"GIT_CONFIG_VALUE_{_i}"] = _v


def quiet_git_env(base):
    """`base` plus the settings, appended after any GIT_CONFIG_* entries `base` already carries.

    git requires the indices 0..COUNT-1 to be contiguous, so existing entries keep their numbers
    and ours follow. A `base` whose GIT_CONFIG_COUNT is not a non-negative integer is returned
    unchanged: git would ignore the block anyway, and a helper must never raise at import.
    Idempotent: settings already present (by key) are not appended twice.
    """
    env = dict(base)
    raw = env.get("GIT_CONFIG_COUNT", "0")
    if not raw.isdigit():
        return env
    count = int(raw)
    present = {env.get(f"GIT_CONFIG_KEY_{i}") for i in range(count)}
    for key, value in SETTINGS:
        if key in present:
            continue
        env[f"GIT_CONFIG_KEY_{count}"] = key
        env[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    env["GIT_CONFIG_COUNT"] = str(count)
    return env


def install():
    """Apply the settings to this process's environment (and so to every child that inherits it)."""
    os.environ.update(quiet_git_env(os.environ))


install()
