// SPDX-License-Identifier: ISC
// Theme entry for the vibe-suite site (E8.4 / vibe-61). VitePress resolves
// .vitepress/theme/index once a theme directory exists, so this file is required
// rather than optional: without it the build fails resolving the theme.
import DefaultTheme from "vitepress/theme";
import type { Theme } from "vitepress";
import "./custom.css";

export default {
  extends: DefaultTheme,
} satisfies Theme;
