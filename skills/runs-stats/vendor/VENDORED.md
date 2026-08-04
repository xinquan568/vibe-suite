# Vendored: Chart.js 4.4.1 (UMD build)

- Origin: npm registry tarball `chart.js-4.4.1.tgz`
  (https://registry.npmjs.org/chart.js/-/chart.js-4.4.1.tgz)
- Tarball sha256: 9ee0a0470ab0888f95f2cd380b219c9e31a0a64a8356cea970f49bbfa829fd83
- File: `package/dist/chart.umd.js` from that tarball, stored here as
  `chart.umd.min.js` — npm 4.4.1 ships the UMD build already minified; jsDelivr's
  `chart.umd.min.js` alias (the URL the pre-port pages loaded) serves this same content.
- File sha256: 74401d738dd3e03ee5dfb3b6841210fe2c4ead8a960c4011ca4ba0b78a9fd8f3
- License: MIT (see LICENSE, copied verbatim from `package/LICENSE.md`)
- Why vendored: F8.5(c) — generated dashboards must render from file:// with no network;
  the generator inlines this bundle into every page it writes.
