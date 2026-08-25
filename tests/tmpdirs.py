# SPDX-License-Identifier: ISC
"""Throwaway-directory helpers for the Python test suite (vibe-198 / M32).

Seven test modules called `tempfile.mkdtemp()` with no matching cleanup, leaking ~600 dirs into
$TMPDIR per full run. Two shapes replace them:

* `TempDirMixin.mkdtemp(**kw)` — for a `TestCase` method: it registers `shutil.rmtree` via
  `addCleanup`, so the dir is removed when the test ends (pass or fail). A class using it lists
  `TempDirMixin` before `unittest.TestCase` in its bases.
* `scratch_dir(**kw)` — for a module-level helper with no `self`: the dir is removed at process
  exit (mirroring the Node `_tmp.mjs` exit hook). Idempotent; a dir already gone is skipped.
"""
import atexit
import shutil
import tempfile

__all__ = ["TempDirMixin", "scratch_dir"]


class TempDirMixin:
    """Mixin giving a TestCase a `mkdtemp` that cleans itself up when the test finishes."""

    def mkdtemp(self, **kw):
        d = tempfile.mkdtemp(**kw)
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d


_EXIT_DIRS = []


@atexit.register
def _remove_exit_dirs():
    for d in _EXIT_DIRS:
        shutil.rmtree(d, ignore_errors=True)


def scratch_dir(**kw):
    """A temp dir removed at process exit — for module-level helpers that have no `self`."""
    d = tempfile.mkdtemp(**kw)
    _EXIT_DIRS.append(d)
    return d
