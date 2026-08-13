# NLPM Audit: MiniMax-AI/skills
**Date**: 2026-04-27  |  **Artifacts**: 30  |  **Strategy**: batched
**NL Score**: 89/100
**Security**: BLOCKED
**Bugs**: 1  |  **Quality Issues**: 16  |  **Security Findings**: 6

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| skills/minimax-multimodal-toolkit/SKILL.md | skill | 68 | BUG: `name: mmx-cli` ≠ directory `minimax-multimodal-toolkit` |
| plugins/pptx-plugin/agents/cover-page-generator.md | agent | 76 | No model declared, no examples |
| plugins/pptx-plugin/agents/content-page-generator.md | agent | 76 | No model declared, no examples |
| plugins/pptx-plugin/agents/section-divider-generator.md | agent | 76 | No model declared, no examples |
| plugins/pptx-plugin/agents/summary-page-generator.md | agent | 78 | No model declared, no examples |
| plugins/pptx-plugin/agents/table-of-contents-generator.md | agent | 78 | No model declared, no examples |
| plugins/pptx-plugin/skills/color-font-skill/SKILL.md | skill | 88 | Missing license field; mixed Chinese/English without language label |
| plugins/pptx-plugin/skills/design-style-skill/SKILL.md | skill | 90 | Missing license field; predominantly Chinese content |
| skills/frontend-dev/SKILL.md | skill | 91 | Vague quantifiers: "premium", "striking", "compelling" |
| skills/minimax-docx/SKILL.md | skill | 91 | Dense format; trigger field not a standard SKILL.md field |
| skills/minimax-pdf/SKILL.md | skill | 92 | Minor vague language in description |
| skills/shader-dev/SKILL.md | skill | 92 | No explicit output format statement |
| skills/vision-analysis/SKILL.md | skill | 92 | Clean |
| plugins/pptx-plugin/.claude-plugin/plugin.json | manifest | 92 | Missing `author` field |
| skills/gif-sticker-maker/SKILL.md | skill | 93 | Clean |
| skills/android-native-dev/SKILL.md | skill | 93 | Clean |
| skills/buddy-sings/SKILL.md | skill | 93 | Clean |
| skills/minimax-music-gen/SKILL.md | skill | 93 | Clean |
| skills/fullstack-dev/SKILL.md | skill | 93 | Clean |
| plugins/pptx-plugin/skills/ppt-orchestra-skill/SKILL.md | skill | 94 | Clean |
| plugins/pptx-plugin/skills/ppt-editing-skill/SKILL.md | skill | 94 | Clean |
| plugins/pptx-plugin/skills/slide-making-skill/SKILL.md | skill | 94 | Clean |
| skills/minimax-xlsx/SKILL.md | skill | 94 | Clean |
| skills/react-native-dev/SKILL.md | skill | 94 | Clean |
| skills/ios-application-dev/SKILL.md | skill | 94 | Clean |
| skills/flutter-dev/SKILL.md | skill | 94 | Clean |
| skills/pptx-generator/SKILL.md | skill | 94 | Clean |
| .claude/skills/pr-review/SKILL.md | skill | 94 | Clean |
| skills/minimax-music-playlist/SKILL.md | skill | 95 | Clean |
| .claude-plugin/plugin.json | manifest | 97 | Clean |

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 3 |
| Medium | 2 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Scripts (.sh) | 4 (`skills/minimax-docx/scripts/{setup.sh,env_check.sh,doc_to_docx.sh,docx_preview.sh}`, `skills/minimax-pdf/scripts/make.sh`) |
| Scripts (.py) | 22 across `skills/{minimax-pdf,minimax-xlsx,gif-sticker-maker,frontend-dev}` and `.claude/skills/pr-review` |
| Scripts (.js) | 2 (`skills/minimax-pdf/scripts/render_cover.js`, `skills/frontend-dev/templates/generator_template.js`) |
| MCP configs | 0 |
| Package manifests | 0 (no package.json or requirements.txt at repo root; `skills/gif-sticker-maker/references/requirements.txt` is a reference doc) |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | High | skills/minimax-docx/scripts/setup.sh | 136–139 | SEC-curl-pipe-sh | Downloads `https://dot.net/v1/dotnet-install.sh` to `/tmp/`, `chmod +x`, then executes it — download-and-execute equivalent to curl-pipe-sh |
| 2 | High | skills/minimax-docx/scripts/setup.sh | 107–123 | SEC-sudo-usage | `sudo apt-get`, `sudo dnf`, `sudo pacman`, `sudo zypper` for system package installation |
| 3 | High | skills/minimax-docx/scripts/setup.sh | 140–141 | SEC-path-modification | Permanently appends `$HOME/.dotnet` to `PATH` in `~/.bashrc` |
| 4 | Medium | skills/minimax-pdf/scripts/make.sh | 109–111 | SEC-runtime-install | `python3 -m pip install ... reportlab pypdf matplotlib` runs at `fix` subcommand — installs unverified packages at runtime |
| 5 | Medium | skills/minimax-pdf/scripts/render_cover.js | 1 | SEC-headless-browser | Playwright/Chromium headless execution for HTML→PDF rendering; Chromium is a significant attack surface |
| 6 | Low | skills/gif-sticker-maker/references/requirements.txt | 1 | SEC-unpinned-semver | `requests>=2.28` — unpinned semver allows unexpected major version upgrades |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | skills/minimax-multimodal-toolkit/SKILL.md | `name: mmx-cli` does not match directory name `minimax-multimodal-toolkit` | Fails `validate_skills.py` hard check; skill cannot be registered or discovered by directory name |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | skills/minimax-pdf/scripts/make.sh | Runtime pip install with no version pins or hash verification | Pin all packages to exact versions with `--require-hashes`; document in a `requirements.txt` |
| 2 | skills/gif-sticker-maker/references/requirements.txt | `requests>=2.28` unpinned | Pin to `requests==2.32.3` or current stable with a hash |

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | plugins/pptx-plugin/agents/cover-page-generator.md | Model not declared | -5 |
| 2 | plugins/pptx-plugin/agents/cover-page-generator.md | Zero examples | -15 |
| 3 | plugins/pptx-plugin/agents/content-page-generator.md | Model not declared | -5 |
| 4 | plugins/pptx-plugin/agents/content-page-generator.md | Zero examples | -15 |
| 5 | plugins/pptx-plugin/agents/section-divider-generator.md | Model not declared | -5 |
| 6 | plugins/pptx-plugin/agents/section-divider-generator.md | Zero examples | -15 |
| 7 | plugins/pptx-plugin/agents/summary-page-generator.md | Model not declared | -5 |
| 8 | plugins/pptx-plugin/agents/summary-page-generator.md | Zero examples | -15 |
| 9 | plugins/pptx-plugin/agents/table-of-contents-generator.md | Model not declared | -5 |
| 10 | plugins/pptx-plugin/agents/table-of-contents-generator.md | Zero examples | -15 |
| 11 | plugins/pptx-plugin/skills/color-font-skill/SKILL.md | Missing `license` field | -3 |
| 12 | plugins/pptx-plugin/skills/design-style-skill/SKILL.md | Missing `license` field | -3 |
| 13 | skills/minimax-multimodal-toolkit/SKILL.md | Missing `license` and `metadata` fields | -5 |
| 14 | plugins/pptx-plugin/agents/cover-page-generator.md | Vague quantifiers: "appropriate layout", "optimal layout" | -4 |
| 15 | plugins/pptx-plugin/agents/section-divider-generator.md | Vague quantifiers: "appropriate layout", "effective professional layouts" | -4 |
| 16 | plugins/pptx-plugin/agents/content-page-generator.md | Vague quantifiers: "best subtype", "clean, well-structured code" | -4 |

## Cross-Component
**Terminology drift**: `skills/minimax-multimodal-toolkit/SKILL.md` uses `name: mmx-cli` while the directory is `minimax-multimodal-toolkit`. Every other skill uses a name that matches its directory. This file is the sole outlier.

**Functional overlap**: `skills/pptx-generator/SKILL.md` and the `plugins/pptx-plugin/` subtree serve the same PowerPoint generation use case. The standalone skill appears to be a unified wrapper over the plugin's modular agents. This is intentional and documented, but users loading both could see ambiguous trigger matching on "PPT/PPTX/PowerPoint" phrases.

**Internal references are intact**: `pr-review/SKILL.md` references `references/structure-rules.md` and `references/quality-guidelines.md` — both exist. All `pptx-plugin` agent cross-references to `slide-making-skill` and `design-style-skill` resolve within the plugin subtree.

## Recommendation
BLOCKED — do not submit PRs. File private security report.

Three HIGH security findings are present in `skills/minimax-docx/scripts/setup.sh`: download-and-execute of an external shell script, broad sudo usage, and permanent `~/.bashrc` modification. While all three are standard patterns for a .NET SDK installer and represent intended behavior rather than malicious code, they match HIGH-severity signatures that require human security review before any PR workflow is initiated.

Once the security review clears `setup.sh` (or the findings are formally accepted as expected behavior), the single NL bug (`mmx-cli` name mismatch) is a clean one-line fix and the medium/low security items in `make.sh` and `requirements.txt` are suitable for public PRs.
