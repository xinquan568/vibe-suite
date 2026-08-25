#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# tests/run-parallel.sh (vibe-199 / M34) — run the Python test suite in parallel locally.
#
# `python3 -m unittest` has no parallel runner, but the modules are temp-dir isolated (vibe-198),
# so each `tests/test_*.py` module can run as its own process. This runs them with `xargs -P`
# (default: one job per CPU) and exits non-zero if ANY module fails — a fast local mirror of what
# CI's four shards do in parallel.
#
#   tests/run-parallel.sh [-j N] [-- <extra unittest args>]
#
# -j N : max parallel jobs (default: CPU count). Env NODE, CI, VIBE_SUITE_PINNED_TREES pass through.
set -euo pipefail

JOBS="$( { command -v nproc >/dev/null 2>&1 && nproc; } || sysctl -n hw.ncpu 2>/dev/null || echo 4 )"
EXTRA=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    -j) JOBS="$2"; shift 2 ;;
    --) shift; EXTRA=("$@"); break ;;
    *) echo "run-parallel.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd -- "$REPO_ROOT"

# The module set, one dotted name per line, sorted (same source the CI shards partition).
# Discovery must never fail open: redirect find to a file inside an `if` so its exit status
# propagates (a partial list would silently drop modules), then sort the null-delimited names.
tmp="$(mktemp)"
if ! find tests -maxdepth 1 -name 'test_*.py' -print0 > "$tmp"; then
  echo "run-parallel.sh: test discovery failed" >&2; rm -f "$tmp"; exit 1
fi
mapfile -d '' -t FILES < <(sort -z < "$tmp"); rm -f "$tmp"
MODULES=()
for f in "${FILES[@]}"; do
  m="${f#tests/}"; m="${m%.py}"; MODULES+=("tests.$m")
done
if [ "${#MODULES[@]}" -eq 0 ]; then
  echo "run-parallel.sh: no tests found under tests/" >&2
  exit 1
fi
printf 'run-parallel.sh: %d module(s), -P %s\n' "${#MODULES[@]}" "$JOBS" >&2

# Each module is one `python3 -m unittest` process. xargs returns 123 if any invocation exits
# non-zero, which we normalise to 1. A failing module's output is preserved (xargs interleaves
# per-process; each process's block is contiguous enough to read).
if printf '%s\n' "${MODULES[@]}" \
    | xargs -P "$JOBS" -I '{}' python3 -m unittest "${EXTRA[@]}" '{}'; then
  echo "run-parallel.sh: all ${#MODULES[@]} modules passed" >&2
else
  echo "run-parallel.sh: at least one module failed" >&2
  exit 1
fi
