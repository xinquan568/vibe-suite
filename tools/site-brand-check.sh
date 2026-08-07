#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
#
# site-brand-check (vibe-61 / E8.4, D-A) — the rendered-surface brand gate.
#
# tools/legacy-string-sweep.sh catches the retired NAMESPACES over the TRACKED tree. Two gaps
# it structurally cannot see: the bare brand word (no namespace colon) and generated output
# (never tracked). This check closes both as a separate, additive tool — it takes a DIRECTORY
# argument, recurses, matches case-insensitively, and admits no exception for anything that
# renders. A fenced code block renders. A visible provenance line renders. Quoting history is
# not a licence to display the retired brand; provenance belongs in a comment that the reader
# never sees.
#
# Allowed, because they never reach the page:
#   * an HTML comment (<!-- ... -->) in markdown/HTML, including a multi-line one
#   * a source comment (// ... , /* ... */ , # ...) in a config, theme or script file,
#     by the comment syntax of that file type
#
# Usage: bash tools/site-brand-check.sh <directory>
# Exit:  0 clean · 1 the retired brand renders somewhere · 2 usage or bad argument

set -euo pipefail

readonly BRAND='nlpm'

usage() {
  echo "usage: site-brand-check.sh <directory>" >&2
  echo "  scans <directory> recursively for the retired brand on rendered surfaces" >&2
}

if [ "$#" -ne 1 ]; then
  echo "site-brand-check: exactly one directory argument is required" >&2
  usage
  exit 2
fi

target="$1"

if [ ! -d "$target" ]; then
  echo "site-brand-check: not a directory: $target" >&2
  exit 2
fi

# Binary and vendored surfaces carry no rendered prose; scanning them is noise, not coverage.
files=()
while IFS= read -r -d '' file; do
  case "$file" in
    *.png|*.jpg|*.jpeg|*.gif|*.ico|*.webp|*.avif|*.pdf|*.zip|*.gz|*.tgz|*.bz2|*.xz) continue ;;
    *.woff|*.woff2|*.ttf|*.otf|*.eot|*.mp4|*.webm|*.mp3|*.wav|*.lock) continue ;;
    *.pyc|*.pyo|*.so|*.dylib|*.dll|*.class|*.wasm|*.db|*.sqlite|*.sqlite3) continue ;;
  esac
  # Anything else that is not text: a byte blob has no rendered surface, and feeding one to
  # awk is noise at best. An empty file fails this test too, and has nothing to hide.
  grep -Iq . "$file" 2>/dev/null || continue
  files+=("$file")
done < <(find "$target" \
  \( -name node_modules -o -name .git -o -name .pnpm-store -o -name __pycache__ \) -prune -o \
  -type f -print0)

if [ "${#files[@]}" -eq 0 ]; then
  echo "site-brand-check: clean — no files to scan under $target"
  exit 0
fi

# One awk pass over every file. Comment stripping is per file type and preserves line
# numbers, so what remains on a line is exactly what a reader would see.
# shellcheck disable=SC2016  # awk program: $0/$1 are awk fields, not shell expansions.
scan='
function strip_html(s,   i, out) {
  out = ""
  while (length(s) > 0) {
    if (in_html) {
      i = index(s, "-->")
      if (i == 0) { s = ""; break }
      s = substr(s, i + 3); in_html = 0
    } else {
      i = index(s, "<!--")
      if (i == 0) { out = out s; s = ""; break }
      out = out substr(s, 1, i - 1)
      s = substr(s, i + 4); in_html = 1
    }
  }
  return out
}
# A brand string inside a QUOTED LITERAL renders — CSS `content: "/* nlpm */"` paints it on the
# page, and a JS string `"// nlpm"` reaches the DOM — so comment stripping must never exempt it.
# Quoted spans are protected before any comment token is considered.
# Inside a quoted span the brand text must survive for matching while every comment INTRODUCER is
# destroyed — otherwise `content: "/* nlpm */"` is stripped as a block comment even though it paints
# on the page. Only the introducer characters are substituted; letters are untouched.
function neutralise(s) {
  gsub(/\//, "\002", s)
  gsub(/#/,  "\003", s)
  gsub(/</,  "\004", s)
  gsub(/!/,  "\005", s)
  return s
}
function protect_quoted(s,   out, i, q, j) {
  out = ""
  while (length(s) > 0) {
    i = match(s, /["\047]/)
    if (i == 0) { out = out s; break }
    out = out substr(s, 1, i - 1)
    q = substr(s, i, 1)
    s = substr(s, i + 1)
    j = index(s, q)
    if (j == 0) { out = out "\001" neutralise(s); break }   # unterminated: keep it scannable
    out = out "\001" neutralise(substr(s, 1, j - 1)) "\001"
    s = substr(s, j + 1)
  }
  return out
}
function strip_block(s,   i, out) {
  out = ""
  while (length(s) > 0) {
    if (in_block) {
      i = index(s, "*/")
      if (i == 0) { s = ""; break }
      s = substr(s, i + 2); in_block = 0
    } else {
      i = index(s, "/*")
      if (i == 0) { out = out s; s = ""; break }
      out = out substr(s, 1, i - 1)
      s = substr(s, i + 2); in_block = 1
    }
  }
  return out
}
function strip_line(s, marker,   i, at, prev, start) {
  start = 1
  while (1) {
    i = index(substr(s, start), marker)
    if (i == 0) return s
    at = i + start - 1
    if (at == 1) return ""
    prev = substr(s, at - 1, 1)
    if (prev == " " || prev == "\t") return substr(s, 1, at - 1)
    start = at + length(marker)
  }
}
FNR == 1 {
  in_html = 0; in_block = 0
  html = 0; slash = 0; hash = 0
  n = split(FILENAME, seg, "/")
  base = seg[n]
  m = split(base, dot, ".")
  ext = (m > 1) ? tolower(dot[m]) : ""
  if (ext == "vue") { html = 1; slash = 1 }
  else if (ext ~ /^(md|markdown|mdx|html|htm|svg|xml)$/) html = 1
  else if (ext ~ /^(ts|tsx|mts|cts|js|jsx|mjs|cjs|css|scss|less|json5)$/) slash = 1
  else if (ext ~ /^(sh|bash|zsh|py|rb|yml|yaml|toml|ini|cfg|conf|env)$/) hash = 1
}
{
  line = $0
  # Protect quoted literals FIRST: a brand string inside one renders, so no comment rule may
  # exempt it. \001 stands in for the quote marks and cannot be mistaken for a comment token.
  if (html || slash || hash) line = protect_quoted(line)
  if (html) line = strip_html(line)
  if (slash) { line = strip_block(line); line = strip_line(line, "//") }
  if (hash) line = strip_line(line, "#")
  if (tolower(line) ~ brand) {
    printf "%s:%d: %s\n", FILENAME, FNR, $0
    found = 1
  }
}
END { if (found) exit 1 }
'

# LC_ALL=C: the brand is ASCII, and a stray byte in one file must not abort the whole scan.
status=0
LC_ALL=C awk -v brand="$BRAND" "$scan" "${files[@]}" || status=$?

if [ "$status" -ne 0 ]; then
  echo "site-brand-check: the retired brand renders in the listing above (${#files[@]} files scanned under $target)" >&2
  echo "site-brand-check: move provenance into a non-rendered comment, or rename the reference" >&2
  exit 1
fi

echo "site-brand-check: clean — ${#files[@]} files scanned under $target"
