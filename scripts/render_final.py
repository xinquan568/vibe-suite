#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Render a finalized proposal to a self-contained document (E5.2 / vibe-41).

    render_final.py --root <dir> <source.md> [--out <dir>]

**Why this is Python and not the shell script it was ported from.** The source skill rendered through
`render_final.sh`, which wrote its output with `> "$target"`. This repository settled that question
already: `tests/test_write_discipline.py` keeps an allowlist of shell scripts permitted to redirect
into a real path, and that allowlist is **empty** — every write goes through `bridge.write_atomic`,
because a redirection follows a destination symlink and an AST lint cannot see it. Carrying the shell
version across would have re-opened a closed rule; **P6** says a port fixes an inherited defect rather
than inheriting it.

**Pandoc is optional and its absence is not a failure.** Without it the renderer writes a markdown
pointer and warns. Finalize degrades; it does not fail. A renderer that could fail the whole finalize
would make an optional feature load-bearing, which is the opposite of what an optional feature is for.

`VIBE_SUITE_PANDOC_BIN` overrides which pandoc is used, mirroring `VIBE_SUITE_CODEX_BIN` in
`codex-runner.mjs`. It exists for the same reason: the absent-tool branch is the one that matters, and
testing it by emptying `PATH` removes the interpreter too.
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

import bridge  # noqa: E402

EXIT_OK, EXIT_BAD_INPUT, EXIT_BAD_ROOT, EXIT_WRITE_FAILED = 0, 2, 3, 4

FALLBACK_MARKER = "pandoc unavailable"


def _lexical(path):
    """Absolute and lexically normalised — `..` collapsed, symlinks untouched.

    `.resolve()` is wrong here: it follows a caller-supplied final symlink and hands `bridge` the
    target rather than the thing it was asked to refuse. But `.absolute()` alone leaves `..` in place,
    so a root spelled `sub/..` and a destination spelled from the real parent do not share a prefix and
    `relative_to` raises instead of refusing. `normpath` collapses the traversal without resolving
    anything, which is the only operation that serves both.
    """
    return Path(os.path.normpath(os.path.join(os.getcwd(), str(path))))


def _write(root, dest, content):
    """One write path, and a containment failure that refuses rather than crashing.

    `bridge` raises `ValueError` from `relative_to` when a destination shares no prefix with the root —
    an alias the lexical pass cannot see, for instance. That is a refusal in every sense except the
    exception type, and an uncaught traceback is a worse way to say it.
    """
    try:
        bridge.write_atomic(root, dest, content)
    except (bridge.BridgeError, ValueError) as exc:
        print("render_final: refusing to write %s: %s" % (dest, exc), file=sys.stderr)
        return False
    return True


def banner(source_text):
    """Counted from the *source*, not the render.

    A word count taken after rendering would include markup and measure the renderer instead of the
    writing.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "Generated %s · %d words · %d characters" % (
        stamp, len(source_text.split()), len(source_text))


def pandoc_binary():
    override = os.environ.get("VIBE_SUITE_PANDOC_BIN")
    if override:
        return override if (os.path.isfile(override) and os.access(override, os.X_OK)) else None
    return shutil.which("pandoc")


def render_html(pandoc, document):
    """Render through pandoc over a pipe, so this process writes nothing.

    An earlier version staged the document to a temp file and let pandoc write a temp output. Both are
    filesystem mutations outside the audited primitive, and `tests/test_write_discipline.py` keeps an
    empty allowlist for exactly that — the rule is not "write somewhere harmless", it is "do not write
    outside `bridge`". Passing markdown on stdin and taking HTML from stdout removes the question
    instead of arguing it: the only write left is `bridge.write_atomic`.

    Returns the rendered HTML, or `None`. A pandoc that exists but cannot **embed** is, from
    finalize's point of view, the same as one that is absent — either way the reader gets markdown,
    which is honest, rather than an HTML file that quietly needs the network.
    """
    # Only the two embedding spellings. `--standalone` alone produces a document that references
    # external resources, and `FINAL.html` is contracted to be self-contained — publishing a
    # non-embedded file under that name would be worse than falling back to markdown, because the
    # failure would be invisible until someone opened it offline.
    for flags in (["--embed-resources", "--standalone"],
                  ["--self-contained", "--standalone"]):
        try:
            result = subprocess.run(
                [pandoc, *flags, "-f", "markdown", "-t", "html"],
                input=document, capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render a finalized proposal.")
    parser.add_argument("source", help="the assembled markdown finalize produced")
    parser.add_argument("--root", required=True, help="containment root for every write")
    parser.add_argument("--out", help="output directory (default: the source's directory)")
    args = parser.parse_args(argv)

    # `Path.resolve()` on the root would follow a caller-supplied final symlink and hand `bridge` the
    # target instead of the thing it was asked to check — which is precisely the refusal
    # `assert_root` exists to make. Absolute, not resolved: `absolute()` prefixes the cwd and leaves
    # the identity alone.
    root = _lexical(Path(args.root))
    try:
        bridge.assert_root(root)
        bridge.pin_root(root)
    except bridge.BridgeError as exc:
        print("render_final: %s" % exc, file=sys.stderr)
        return EXIT_BAD_ROOT

    # Every path handed onward must be absolute in the same frame as the root, because `bridge`
    # computes containment with `relative_to`. A relative `--out` against an absolute root raises
    # `ValueError` rather than refusing — an ordinary invocation like `--root . docs/run/plan.md`
    # crashed before this.
    source = _lexical(Path(args.source))
    if not source.is_file():
        print("render_final: no readable source markdown (%s)" % args.source, file=sys.stderr)
        return EXIT_BAD_INPUT

    text = source.read_text(encoding="utf-8")
    head = banner(text)
    print("render_final: %s" % head)

    outdir = _lexical(Path(args.out)) if args.out else source.parent
    document = "*%s*\n\n---\n\n%s" % (head, text)

    pandoc = pandoc_binary()
    if pandoc:
        html = render_html(pandoc, document)
        if html is not None:
            if not _write(root, outdir / "FINAL.html", html):
                return EXIT_WRITE_FAILED
            print("render_final: wrote %s" % (outdir / "FINAL.html"))
            return EXIT_OK
        print("render_final: WARNING pandoc failed; falling back to a markdown pointer",
              file=sys.stderr)
    else:
        print("render_final: WARNING pandoc not found; writing a markdown pointer instead of HTML",
              file=sys.stderr)

    pointer = (
        "<!-- rendered by render_final.py — %s -->\n\n"
        "*%s*\n\n"
        "> HTML rendering was skipped because pandoc is not available. The full document follows.\n\n"
        "---\n\n%s" % (FALLBACK_MARKER, head, text))

    # `FINAL.md` and a source named `final.md` are THE SAME FILE on a case-insensitive filesystem
    # (macOS by default). The shell version read the source while redirecting into it and wrote into
    # itself until the process was killed. Reading the source fully before writing — which happened
    # above — is what makes the collision harmless here.
    if not _write(root, outdir / "FINAL.md", pointer):
        return EXIT_WRITE_FAILED

    print("render_final: wrote %s (markdown pointer)" % (outdir / "FINAL.md"))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
