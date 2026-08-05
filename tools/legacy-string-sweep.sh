#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# AC-6 legacy-string sweep (E7.3 / vibe-55).
#
# No retired command namespace may appear in any shipped runtime-reachable string. The
# patterns are scripts/lib/retired_names.py's five literals (cross-pinned by
# tests/test_legacy_sweep.py — edit both together); the scope is a TOTAL partition over
# tracked top-level entries, modeled on tools/model-pin-lint.py: every entry is SWEPT or
# EXEMPT, and an entry in neither is an error, never a silent pass.
#
# Exit: 0 clean · 1 hits (file:line: pattern) · 2 usage/environment error.
set -u -o pipefail

if [ "$#" -gt 0 ]; then
  echo "legacy-string-sweep: unknown argument '$1' (the sweep takes none)" >&2
  exit 2
fi

command -v git >/dev/null 2>&1 || { echo "legacy-string-sweep: git required" >&2; exit 2; }
git rev-parse --git-dir >/dev/null 2>&1 || {
  echo "legacy-string-sweep: run inside the repository" >&2; exit 2; }

# The five retired namespaces (retired_names.RETIRED): /cc-suite: /nlpm: /grill:
# /codex-toolkit: /vibe:
PATTERNS='/cc-suite:|/nlpm:|/grill:|/codex-toolkit:|/vibe:'

# Shipped runtime-reachable surface — the model-pin SCANNED list, plus `site` pre-classified
# for the S8 tree docs/disposition.yaml expects (classified before it exists, so the sweep
# covers it the moment it lands).
SWEPT=".claude-plugin .vibe-suite.md .vibe-test agents auditor bin codex codex-src commands \
hooks schemas scripts site skills templates"

# EXEMPT, each with its reason:
#   docs               — documentation, incl. historical planning records
#   tests              — the test corpus deliberately contains the patterns
#   tools              — developer utilities, incl. this script's own pattern list
#   .github            — CI infrastructure, not runtime text
#   README.md CLAUDE.md PRIVACY.md LICENSE — root documentation (the migration table NAMES
#                        the old commands by design)
#   .gitignore .gitattributes — git configuration
EXEMPT="docs tests tools .github README.md CLAUDE.md PRIVACY.md LICENSE .gitignore \
.gitattributes"

# Per-FILE exception: the predicate module IS the enforcement data — the five literals are
# its RETIRED tuple, not runtime output.
EXCEPTED_FILES="scripts/lib/retired_names.py"

# Enumeration must not fail silently (F1): capture ls-files output first, with its status.
if ! toplist=$(git ls-files | cut -d/ -f1 | sort -u); then
  echo "legacy-string-sweep: git ls-files failed" >&2
  exit 2
fi
status=0
unclassified=0
while IFS= read -r top; do
  case " $SWEPT $EXEMPT " in
    *" $top "*) ;;
    *) echo "legacy-string-sweep: unclassified top-level entry '$top' — add it to SWEPT or \
EXEMPT in tools/legacy-string-sweep.sh" >&2
       unclassified=1 ;;
  esac
done <<< "$toplist"
[ "$unclassified" -eq 1 ] && exit 2

for area in $SWEPT; do
  [ -e "$area" ] || continue
  if ! files=$(git ls-files -- "$area"); then
    echo "legacy-string-sweep: git ls-files failed for '$area'" >&2
    exit 2
  fi
  [ -n "$files" ] || continue
  # Per-FILE grep, no xargs: GNU xargs folds grep's ordinary no-match (1) into its own 123,
  # which is indistinguishable from a real error — the exact ambiguity that failed CI while
  # macOS passed. Per file, the status is unambiguous: 0 = matches, 1 = none, >1 = a
  # read/usage error and a loud exit 2 (never a silent clean).
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    skip=0
    for exc in $EXCEPTED_FILES; do
      [ "$f" = "$exc" ] && skip=1
    done
    [ "$skip" -eq 1 ] && continue
    hits=$(grep -HInE "$PATTERNS" -- "$f")
    rc=$?
    if [ "$rc" -gt 1 ]; then
      echo "legacy-string-sweep: grep failed (status $rc) reading '$f'" >&2
      exit 2
    fi
    [ "$rc" -eq 0 ] || continue
    printf '%s\n' "$hits"
    status=1
  done <<< "$files"
done

if [ "$status" -eq 0 ]; then
  echo "legacy-string-sweep: clean — no retired namespace in the shipped surface"
fi
exit "$status"
