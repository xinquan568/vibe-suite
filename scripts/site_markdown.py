#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Escape corpus strings for the VitePress site (vibe-196 / M23).

The five `bin/vibe-build-*` builders interpolate corpus strings — repo names, finding titles,
article and rule titles, vocabulary terms — into Markdown that VitePress compiles as a Vue
template. Three things in such a string are live there, and each is closed by a different
mechanism:

* HTML (`<script>`): markdown-it renders it as markup while `html: true` (VitePress's default).
  `site/.vitepress/config.ts` turns that off (`markdown.html: false`); `md_escape` also encodes
  `&`, `<` and `>` as entities so the string is inert even where that setting is not in force.
* A Vue mustache (`{{ 1+1 }}`): the Vue compiler evaluates it wherever it appears in template text,
  inline code included. `md_escape` encodes the opening pair as `&#123;&#123;` — VitePress's
  `restoreEntities` rule emits an entity by its source markup, so the compiler sees no delimiter and
  the page shows the literal braces. Plain markdown-it would decode the entity back; this escape is
  therefore specific to VitePress, which is the site's renderer by design (F10.3).
* A table pipe (`|`): inside a GFM table cell it ends the cell. `md_escape` writes it as `\\|`,
  which markdown-it keeps inside a cell and renders as `|` everywhere else. A backslash is doubled
  first so that an input backslash can never turn the escape back into a bare pipe.

Declared boundary: this is a text escape for scalar values placed in Markdown *text* positions
(headings, table cells, list items, link text, emphasis). It is inert inside a code span — code
spans render their content literally and entities are not decoded there — so a builder must not
place an escaped value inside backticks; and it does not neutralise Markdown syntax characters
(`]`, `*`, `_`, `#`, backtick), which can still alter layout but never execute. Blocks of corpus
*prose* that must keep their Markdown (a rule body) are wrapped with `v_pre` instead: VitePress's
`::: v-pre` container renders `<div v-pre>` from tokens, survives `html: false`, and stops the Vue
compiler for everything inside it.

The container fence is length-hardened. markdown-it-container closes on the first body line that is
a run of colons at least as long as the opening run, so a body carrying a bare `:::` line would
close a three-colon wrapper early and re-expose a following `{{ }}` to the Vue compiler (a real
breakout, measured). `v_pre` therefore opens and closes with a colon run strictly longer than the
longest all-colon line in the body, which no line in the body can match — so corpus content cannot
terminate the wrapper.
"""

import re

__all__ = ["md_escape", "v_pre"]

#: A body line that is nothing but colons (optionally spaced) — a candidate container closer.
_COLON_LINE = re.compile(r"^[ \t]*(:+)[ \t]*$")

_STEPS = (
    ("\\", "\\\\"),            # first: an input backslash may not join our own escapes
    ("&", "&amp;"),            # second: before any entity we emit
    ("<", "&lt;"),
    (">", "&gt;"),
    ("{{", "&#123;&#123;"),    # the Vue interpolation opener; a lone `{` is inert
    ("|", "\\|"),              # GFM table-cell separator
)


def md_escape(value):
    """Return `value` (any scalar; None → "") as inert Markdown text for a VitePress page."""
    text = "" if value is None else str(value)
    for raw, escaped in _STEPS:
        text = text.replace(raw, escaped)
    return text


def v_pre(block):
    """Wrap a Markdown prose block in a length-hardened VitePress `v-pre` container.

    The colon run is one longer than the longest all-colon line in the body (min 3), so no line in
    the body can close the container early. The Vue compiler evaluates nothing inside a `v-pre`
    element; the body keeps its own Markdown, and raw HTML in it is text under `markdown.html=false`.
    """
    body = ("" if block is None else str(block)).strip("\n")
    longest = max((len(m.group(1)) for m in map(_COLON_LINE.match, body.splitlines()) if m),
                  default=0)
    fence = ":" * max(3, longest + 1)
    return f"{fence} v-pre\n{body}\n{fence}"
