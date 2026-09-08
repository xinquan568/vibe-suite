# SPDX-License-Identifier: ISC
"""runs-stats — HTML rendering from the two shells under `templates/runs-stats/` (H12 / vibe-216).

The dashboard and index shells used to live in this file as raw strings; they are now
`templates/runs-stats/dashboard.html` and `index.html`, each carrying the placeholders
`__CHART_BUNDLE__`, `__TITLE__` and `__DATA__` exactly once. The vendored Chart.js sits beside them
(`templates/runs-stats/vendor/`, see its VENDORED.md) and is inlined into every page so dashboards render
from file:// with no network (F8.5(c)). Library module: stdlib only, read-only.
"""

import html
import json
from pathlib import Path

#: Where the shells live; tests point this at sentinel templates.
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates" / "runs-stats"
#: The vendored Chart.js beside them (`templates/runs-stats/vendor/VENDORED.md` records its provenance).
VENDOR_BUNDLE = Path(__file__).resolve().parents[2] / "templates" / "runs-stats" / "vendor" / "chart.umd.min.js"

_CACHE = {}


def reset_caches():
    """Forget every template and bundle read so far (tests swap `TEMPLATE_DIR`)."""
    _CACHE.clear()


def _read(path):
    key = str(path)
    if key not in _CACHE:
        _CACHE[key] = Path(path).read_text(encoding="utf-8")
    return _CACHE[key]


def chart_bundle():
    """The vendored Chart.js source, read once. Inlined into every page (F8.5(c)):
    a static report under a consumer's runs/_reports/ cannot portably reference a
    plugin-install path, and file:// rendering must need no network."""
    return _read(VENDOR_BUNDLE)


def _fill(shell, title, payload):
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (shell.replace("__CHART_BUNDLE__", chart_bundle())
            .replace("__TITLE__", html.escape(title)).replace("__DATA__", data_json))


def render_html(report):
    return _fill(_read(TEMPLATE_DIR / "dashboard.html"), "Issue2PR Runs — Statistics Report", report)


def render_index(history, reports_dir):
    return _fill(_read(TEMPLATE_DIR / "index.html"), "Issue2PR Runs — Report Index", history)
