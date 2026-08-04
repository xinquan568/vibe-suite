# Vendored: AntV G6 5.1.1

- **Package**: `@antv/g6` 5.1.1 (MIT — see the adjacent LICENSE, the package's own)
- **Upstream artifact**: https://registry.npmjs.org/@antv/g6/-/g6-5.1.1.tgz
- **npm-published shasum (SHA-1, tarball)**: `e3ebcb6f1b3ca79563d3a461b28a36a7feb8b55e` — verified at vendoring
- **sha256 (this g6.min.js)**: `3e091a94fd08994a383ff34bfba256bb8e382e4be4042197a206d2ecc0957331`
- **Delivered file**: `package/dist/g6.min.js` → `templates/report/vendor/g6.min.js`, byte-identical

The report renderer (`bin/vibe-report`) inlines these bytes into every emitted HTML so reports
are single self-contained files that open over `file://` with no network. The integrity test
(`tests/test_report.py`) recomputes the sha256 against the value above.

## Update procedure

1. Pick the new exact version; fetch its registry tarball; verify the npm-published shasum.
2. Replace `g6.min.js` and `LICENSE` from the tarball's `package/`; update every field above.
3. Run the integrity test and the report suite; regenerate a report and repeat the file:// browser check.
