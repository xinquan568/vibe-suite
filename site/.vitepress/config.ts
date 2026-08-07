// SPDX-License-Identifier: ISC
// VitePress configuration for the vibe-suite public site (E8.4 / vibe-61).
// Generated content (data/, reports/, dashboard.md, featured-audits.md) is produced by
// site/build.sh before this config is evaluated; it is gitignored and never committed.
import { defineConfig } from "vitepress";

export default defineConfig({
  title: "vibe-suite",
  description:
    "A Claude Code plugin that audits natural-language programming artifacts, and an " +
    "automated pipeline that contributes the fixes upstream.",
  lang: "en-GB",
  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: false,
  head: [["meta", { name: "theme-color", content: "#5319e7" }]],
  themeConfig: {
    siteTitle: "vibe-suite",
    nav: [
      { text: "Why", link: "/why" },
      { text: "Install", link: "/install" },
      { text: "How it works", link: "/how-it-works" },
      { text: "Audits", link: "/dashboard" },
    ],
    sidebar: [
      {
        text: "Start here",
        items: [
          { text: "Why it exists", link: "/why" },
          { text: "Install", link: "/install" },
          { text: "How to use it", link: "/how-to-use-it" },
        ],
      },
      {
        text: "The pipeline",
        items: [
          { text: "How it works", link: "/how-it-works" },
          { text: "How it evolves", link: "/how-it-evolves" },
        ],
      },
      {
        text: "Findings",
        items: [
          { text: "Dashboard", link: "/dashboard" },
          { text: "Featured audits", link: "/featured-audits" },
        ],
      },
    ],
    socialLinks: [
      { icon: "github", link: "https://github.com/xinquan568/vibe-suite" },
    ],
    footer: {
      message: "Released under the ISC licence.",
      copyright: "Copyright © 2026 Eric Y. Liu",
    },
    search: { provider: "local" },
  },
});
