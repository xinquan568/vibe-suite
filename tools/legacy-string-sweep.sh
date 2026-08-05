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
set -u

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

status=0
unclassified=0
while IFS= read -r top; do
  case " $SWEPT $EXEMPT " in
    *" $top "*) ;;
    *) echo "legacy-string-sweep: unclassified top-level entry '$top' — add it to SWEPT or \
EXEMPT in tools/legacy-string-sweep.sh" >&2
       unclassified=1 ;;
  esac
done < <(git ls-files | cut -d/ -f1 | sort -u)
[ "$unclassified" -eq 1 ] && exit 2

for area in $SWEPT; do
  [ -e "$area" ] || continue
  while IFS= read -r hit; do
    file=${hit%%:*}
    skip=0
    for exc in $EXCEPTED_FILES; do
      [ "$file" = "$exc" ] && skip=1
    done
    [ "$skip" -eq 1 ] && continue
    echo "$hit"
    status=1
  done < <(git ls-files -z -- "$area" | xargs -0 grep -HInE "$PATTERNS" -- 2>/dev/null || true)
done

if [ "$status" -eq 0 ]; then
  echo "legacy-string-sweep: clean — no retired namespace in the shipped surface"
fi
exit "$status"
