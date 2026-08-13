# NLPM Audit: HKUDS/CLI-Anything
**Date**: 2026-05-21  |  **Artifacts**: 105  |  **Strategy**: progressive
**NL Score**: 75/100
**Security**: CLEAR
**Bugs**: 5  |  **Quality Issues**: 36  |  **Security Findings**: 0

## NL Score Summary

| File | Type | Score | Notes |
|------|------|-------|-------|
| `cli-anything-plugin/commands/cli-anything.md` | command | 45 | Missing YAML frontmatter (name, description); no allowed-tools |
| `cli-anything-plugin/commands/refine.md` | command | 45 | Missing YAML frontmatter (name, description); no allowed-tools |
| `cli-anything-plugin/commands/validate.md` | command | 45 | Missing YAML frontmatter (name, description); no allowed-tools |
| `cli-anything-plugin/commands/test.md` | command | 45 | Missing YAML frontmatter (name, description); no allowed-tools |
| `cli-anything-plugin/commands/list.md` | command | 45 | Missing YAML frontmatter (name, description); no allowed-tools |
| `codex-skill/SKILL.md` | skill | 82 | Frontmatter name is `cli-anything` (not `cli-anything-codex`); no output format section |
| `skills/cli-hub-meta-skill/SKILL.md` | skill | 88 | Good; live catalog URL; clear examples |
| `skills/cli-anything-exa/SKILL.md` | skill | 88 | Good; clear command reference; JSON output documented |
| `skills/cli-anything-mermaid/SKILL.md` | skill | 88 | Good; examples across use cases; output format documented |
| `skills/cli-anything-mubu/SKILL.md` | skill | 78 | Truncated description ("..."); good safety rules and workflow |
| `skills/cli-anything-eth2-quickstart/SKILL.md` | skill | 85 | Compact but complete; safety rules documented |
| `skills/cli-anything-openscreen/SKILL.md` | skill | 90 | Comprehensive; editor settings table; preview workflow |
| `skills/cli-anything-browser/SKILL.md` | skill | 90 | Security section; URL validation documented; daemon mode explained |
| `skills/cli-anything-shotcut/SKILL.md` | skill | 88 | Truncated description; comprehensive command groups; good examples |
| `skills/cli-anything-firefly-iii/SKILL.md` | skill | 92 | Excellent; full API coverage; agent guidelines; troubleshooting |
| `skills/cli-anything-safari/SKILL.md` | skill | 95 | Exceptional; security section; tool selection strategy; 84-tool coverage |
| `skills/cli-anything-cloudcompare/SKILL.md` | skill | 95 | Exceptional; 41 commands with per-command examples; 4 workflow examples |
| `skills/cli-anything-cloudanalyzer/SKILL.md` | skill | 92 | Comprehensive; 27 commands; 4 workflow examples |
| `skills/cli-anything-rekordbox/SKILL.md` | skill | 85 | Architecture diagram; JSON output examples |
| `skills/cli-anything-zotero/SKILL.md` | skill | 62 | All command descriptions say "Execute `command`" — vague cap applied; -20 |
| `skills/cli-anything-novita/SKILL.md` | skill | 83 | Good; model table; examples |
| `skills/cli-anything-wiremock/SKILL.md` | skill | 87 | Error handling documented; workflow pattern |
| `skills/cli-anything-lldb/SKILL.md` | skill | 92 | DAP documented; structured errors; comprehensive agent notes |
| `skills/cli-anything-qgis/SKILL.md` | skill | 87 | Concise but complete; REPL example flow |
| `skills/cli-anything-obsidian/SKILL.md` | skill | 85 | Multiple examples; API key config docs |
| `skills/cli-anything-freecad/SKILL.md` | skill | 93 | 258 commands; all workbenches; preview integration documented |
| `skills/cli-anything-minimax/SKILL.md` | skill | 85 | TTS and chat covered; model tables |
| `skills/cli-anything-musescore/SKILL.md` | skill | 88 | Frontmatter name is `musescore` not `cli-anything-musescore` — mismatch |
| `skills/cli-anything-renderdoc/SKILL.md` | skill | 90 | Extra frontmatter; comprehensive capabilities |
| `skills/cli-anything-adguardhome/SKILL.md` | skill | 85 | Good; multiple examples |
| `skills/cli-anything-sbox/SKILL.md` | skill | 92 | 79+ commands; component presets table; agent workflow |
| `skills/cli-anything-kdenlive/SKILL.md` | skill | 78 | Truncated description; otherwise structured |
| `skills/cli-anything-slay-the-spire-ii/SKILL.md` | skill | 88 | Decision states table; installation instructions |
| `skills/cli-anything-unrealinsights/SKILL.md` | skill | 90 | JSON output fields documented; PowerShell examples |
| `skills/cli-anything-intelwatch/SKILL.md` | skill | 65 | Minimal; only 2 examples; no JSON output format |
| `skills/cli-anything-dify-workflow/SKILL.md` | skill | 65 | Minimal; few examples; no JSON output format |
| `skills/cli-anything-notebooklm/SKILL.md` | skill | 70 | Marked experimental; minimal examples |
| `skills/cli-anything-nslogger/SKILL.md` | skill | 92 | Extra frontmatter; JSON shapes documented |
| `skills/cli-anything-iterm2/SKILL.md` | skill | 90 | Comprehensive; name matches frontmatter |
| `skills/cli-anything-iterm2-ctl/SKILL.md` | skill | 83 | Frontmatter name `cli-anything-iterm2-ctl` but body heading says `cli-anything-iterm2` — mismatch |
| `skills/cli-anything-nsight-graphics/SKILL.md` | skill | 90 | Extra metadata; comprehensive agent notes |
| `skills/cli-anything-threemf/SKILL.md` | skill | 72 | Minimal examples; no JSON output schema |
| `skills/cli-anything-kdenlive/SKILL.md` | skill | 78 | Truncated description |
| `skills/cli-anything-obsidian/SKILL.md` | skill | 85 | Good; complete examples |
| `skills/cli-anything-unimol-tools/SKILL.md` | skill | 75 | Module-path examples instead of installed binary |
| `skills/cli-anything-videocaptioner/SKILL.md` | skill | 88 | Multiple examples; backend notes |
| `skills/cli-anything-novita/SKILL.md` | skill | 83 | Good; model table |
| `skills/cli-anything-audacity/SKILL.md` | skill | 70 | Truncated description; minimal examples |
| `skills/cli-anything-adguardhome/SKILL.md` | skill | 85 | Good; multiple examples |
| `skills/cli-anything-seaclip/SKILL.md` | skill | 68 | Minimal examples; no output format schema |
| `skills/cli-anything-gimp/SKILL.md` | skill | 80 | Truncated description |
| `skills/cli-anything-libreoffice/SKILL.md` | skill | 70 | Truncated description; minimal examples |
| `skills/cli-anything-blender/SKILL.md` | skill | 80 | Truncated description |
| `skills/cli-anything-pm2/SKILL.md` | skill | 72 | Minimal examples; no JSON schema |
| `skills/cli-anything-obs-studio/SKILL.md` | skill | 68 | Truncated description; minimal examples |
| `skills/cli-anything-rekordbox/SKILL.md` | skill | 85 | Architecture diagram; JSON output |
| `skills/cli-anything-zoom/SKILL.md` | skill | 68 | Truncated description; minimal examples |
| `skills/cli-anything-godot/SKILL.md` | skill | 83 | Good; JSON mode documented |
| `skills/cli-anything-anygen/SKILL.md` | skill | 68 | Truncated description; minimal examples |
| `skills/cli-anything-chromadb/SKILL.md` | skill | 70 | Minimal; no JSON output schema |
| `skills/cli-anything-n8n/SKILL.md` | skill | 68 | Table-only; no workflow examples |
| `skills/cli-anything-macrocli/SKILL.md` | skill | 87 | Output format documented; agent rules |
| `skills/cli-anything-comfyui/SKILL.md` | skill | 82 | Good; multiple examples |
| `skills/cli-anything-drawio/SKILL.md` | skill | 68 | Truncated description; minimal examples |
| `skills/cli-anything-ollama/SKILL.md` | skill | 83 | Multiple examples across commands |
| `skills/cli-anything-mailchimp/SKILL.md` | skill | 92 | 303 commands; JSON envelope shapes; agent patterns |
| `skills/cli-anything-rms/SKILL.md` | skill | 75 | Comprehensive listing; minimal workflow examples |
| `skills/cli-anything-krita/SKILL.md` | skill | 85 | Complete command reference; workflow example |
| `skills/cli-anything-safari/SKILL.md` | skill | 95 | Best-in-class; full agent guidance |
| `skills/cli-anything-calibre/SKILL.md` | skill | 82 | Truncated description; field table |
| `skills/cli-anything-inkscape/SKILL.md` | skill | 80 | Truncated description |
| `skills/cli-anything-quietshrink/SKILL.md` | skill | 80 | Name inconsistency (quietshrink vs cli-anything-quietshrink) |
| `skills/cli-anything-cloudcompare/SKILL.md` | skill | 95 | Exceptional; 41 commands detailed |
| `skills/cli-anything-mubu/SKILL.md` | skill | 80 | Truncated description |
| `skills/cli-anything-firefly-iii/SKILL.md` | skill | 92 | Excellent coverage |
| `skills/cli-anything-eth2-quickstart/SKILL.md` | skill | 85 | Compact; safety rules |
| `skills/cli-anything-mermaid/SKILL.md` | skill | 88 | Good examples |
| `skills/cli-anything-exa/SKILL.md` | skill | 88 | Clear command reference |
| `skills/cli-anything-openscreen/SKILL.md` | skill | 90 | Comprehensive |
| `skills/cli-anything-shotcut/SKILL.md` | skill | 88 | Truncated description |
| `skills/cli-anything-browser/SKILL.md` | skill | 90 | Security documented |
| `harness-level SKILL.md files (duplicates of skills/ versions)` | skill | varies | See skills/ scores above |

**Aggregate score (mean across 80+ files):** ~80/100
**Command files mean:** 45/100 (dragged down by universal missing-frontmatter bug)
**Skill files mean:** ~82/100

## Security Scan

**Result: PASS — no CRITICAL or HIGH patterns blocking contribution.**

### Scanned Surfaces

| Surface | Found |
|---------|-------|
| Hook scripts | None (`hooks.json` not present) |
| `.mcp.json` | Not present |
| `package.json` | Not present |
| `requirements.txt` | Not present |
| Shell scripts (`.sh`) | 3 files |
| Python scripts (`.py`) | 1,100+ files |
| JavaScript (`.js`) | 2 files |

### Pattern Results

| Severity | Pattern | Verdict |
|----------|---------|---------|
| CRITICAL | curl-pipe-sh (executed) | **NONE** — occurrences are in: (a) string literals in error messages / doc strings showing install commands, (b) test fixtures that mock the command but do not execute it |
| CRITICAL | eval with variables | NONE |
| CRITICAL | base64-decode-exec | NONE |
| CRITICAL | reverse shell | NONE |
| CRITICAL | credential exfiltration | NONE |
| HIGH | subprocess shell=True | LOW RISK — one call in `cli-hub/cli_hub/installer.py:61`. Used only when the command string from the registry contains shell metacharacters (pipes, `&&`). The source is the registry JSON fetched from `hkuds.github.io`, not user input. Comment confirms intent. |
| HIGH | os.system() | LOW RISK — one call in `firefly-iii/agent-harness/cli_anything/firefly_iii/utils/repl_skin.py:63`. Pattern is `os.system('')` (empty string) used to enable ANSI colour output on Windows — not user input. |
| HIGH | sudo | NONE in Python subprocess calls; not present in `.sh` scripts |
| HIGH | PATH modification | NONE |
| HIGH | postinstall scripts | NONE |
| MEDIUM | Network calls | 99+ `requests`/`urllib` calls — expected for REST API harnesses; all use well-known HTTPS endpoints |
| MEDIUM | Runtime installs | `cli-hub/cli_hub/installer.py` calls pip/npm to install CLIs on demand — by design, documented |
| LOW | Unpinned deps | All `setup.py` files use `>=` version pins (e.g. `click>=8.0`) — standard Python practice, not pinned to exact SHAs |

### Notes

- `cli-hub/tests/test_cli_hub.py` contains a `jimeng` test fixture with `"install_cmd": "curl -s https://jimeng.jianying.com/cli | bash"`. This is test data, not executed code. The test mocks `_run_command` and never actually runs the curl command.
- `adguardhome` backend has a curl-pipe-sh in an error message string directing users to the official AdGuard install script — not executed by the harness.
- `iterm2` backend has a curl-pipe-sh in a documentation string — not executed.
- `quietshrink` has a curl-pipe-sh in a usage hint string — not executed.
- `cli-hub/cli_hub/registry.py` fetches registry JSON from `hkuds.github.io` over HTTPS — acceptable for a package manager pattern, but implies trust in that CDN.

## Bugs

| # | Rule | File | Severity | Description |
|---|------|------|----------|-------------|
| B1 | BUG-missing-frontmatter | `cli-anything-plugin/commands/cli-anything.md` | HIGH | Missing YAML frontmatter `name` and `description` fields |
| B2 | BUG-missing-frontmatter | `cli-anything-plugin/commands/refine.md` | HIGH | Missing YAML frontmatter `name` and `description` fields |
| B3 | BUG-missing-frontmatter | `cli-anything-plugin/commands/validate.md` | HIGH | Missing YAML frontmatter `name` and `description` fields |
| B4 | BUG-missing-frontmatter | `cli-anything-plugin/commands/test.md` | HIGH | Missing YAML frontmatter `name` and `description` fields |
| B5 | BUG-missing-frontmatter | `cli-anything-plugin/commands/list.md` | HIGH | Missing YAML frontmatter `name` and `description` fields |

All 5 command files in `cli-anything-plugin/commands/` are missing the required YAML frontmatter block. Claude Code requires `name` and `description` in frontmatter for slash commands to be discoverable and self-describing. Without these fields, tools like `/nlpm:ls` cannot catalogue them and model context lacks the structured description.

## Security Fixes

No CRITICAL or HIGH security fixes required. The two LOW RISK findings (subprocess shell=True from registry data; os.system('') for ANSI) are acceptable and do not require changes.

**Optional hardening:**
- Consider pinning the registry URL to a content-hash or using a signed manifest to prevent CDN-level tampering with `install_cmd` strings.
- The `cli-hub` installer's `shell=True` code path could validate commands against an allowlist of safe shell operators before routing to shell execution.

## Quality Issues

| # | Rule | File | Penalty | Description |
|---|------|------|---------|-------------|
| Q1 | R14-vague-quantifiers | `skills/cli-anything-zotero/SKILL.md` | -20 (cap) | All 40+ command descriptions use "Execute `command`" — provides no agent-useful information |
| Q2 | R09-minimal-examples | `skills/cli-anything-n8n/SKILL.md` | -5 | Only a command-group table; no workflow examples |
| Q3 | R09-minimal-examples | `skills/cli-anything-intelwatch/SKILL.md` | -5 | Only 2 example scenarios |
| Q4 | R09-minimal-examples | `skills/cli-anything-dify-workflow/SKILL.md` | -5 | Minimal examples; no JSON output format |
| Q5 | R09-minimal-examples | `skills/cli-anything-seaclip/SKILL.md` | -5 | Only 3 example commands |
| Q6 | R09-minimal-examples | `skills/cli-anything-obs-studio/SKILL.md` | -5 | Only 2 basic examples |
| Q7 | R09-minimal-examples | `skills/cli-anything-zoom/SKILL.md` | -5 | Only 2 basic examples |
| Q8 | R09-minimal-examples | `skills/cli-anything-anygen/SKILL.md` | -5 | Minimal examples |
| Q9 | R09-minimal-examples | `skills/cli-anything-chromadb/SKILL.md` | -5 | Very few examples |
| Q10 | R09-minimal-examples | `skills/cli-anything-drawio/SKILL.md` | -5 | Minimal examples |
| Q11 | R10-missing-output-format | `skills/cli-anything-n8n/SKILL.md` | -10 | No JSON output schema documented |
| Q12 | R10-missing-output-format | `skills/cli-anything-seaclip/SKILL.md` | -10 | No JSON output schema |
| Q13 | R10-missing-output-format | `skills/cli-anything-obs-studio/SKILL.md` | -10 | No JSON output schema |
| Q14 | R10-missing-output-format | `skills/cli-anything-zoom/SKILL.md` | -10 | No JSON output schema |
| Q15 | R10-missing-output-format | `skills/cli-anything-chromadb/SKILL.md` | -10 | No JSON output schema |
| Q16 | R10-missing-output-format | `skills/cli-anything-drawio/SKILL.md` | -10 | No JSON output schema |
| Q17 | R10-missing-output-format | `skills/cli-anything-pm2/SKILL.md` | -10 | No JSON schema; basic examples only |
| Q18 | R10-missing-output-format | `skills/cli-anything-anygen/SKILL.md` | -10 | No JSON output schema |
| Q19 | R22-naming | `skills/cli-anything-musescore/SKILL.md` | -5 | Frontmatter `name: musescore` should be `cli-anything-musescore` |
| Q20 | R22-naming | `skills/cli-anything-iterm2-ctl/SKILL.md` | -5 | Heading says `cli-anything-iterm2` but frontmatter says `cli-anything-iterm2-ctl` |
| Q21 | R22-naming | `skills/cli-anything-quietshrink/SKILL.md` | -5 | Frontmatter `name: quietshrink` should be `cli-anything-quietshrink` |
| Q22 | R18-truncated-description | `skills/cli-anything-shotcut/SKILL.md` | -2 | Description truncated with "..." |
| Q23 | R18-truncated-description | `skills/cli-anything-kdenlive/SKILL.md` | -2 | Description truncated with "..." |
| Q24 | R18-truncated-description | `skills/cli-anything-mubu/SKILL.md` | -2 | Description truncated with "..." |
| Q25 | R18-truncated-description | `skills/cli-anything-audacity/SKILL.md` | -2 | Description truncated with "..." |
| Q26 | R18-truncated-description | `skills/cli-anything-inkscape/SKILL.md` | -2 | Description truncated with "..." |
| Q27 | R18-truncated-description | `skills/cli-anything-gimp/SKILL.md` | -2 | Description truncated with "..." |
| Q28 | R18-truncated-description | `skills/cli-anything-libreoffice/SKILL.md` | -2 | Description truncated with "..." |
| Q29 | R18-truncated-description | `skills/cli-anything-blender/SKILL.md` | -2 | Description truncated with "..." |
| Q30 | R18-truncated-description | `skills/cli-anything-anygen/SKILL.md` | -2 | Description truncated with "..." |
| Q31 | R18-truncated-description | `skills/cli-anything-obs-studio/SKILL.md` | -2 | Description truncated with "..." |
| Q32 | R18-truncated-description | `skills/cli-anything-zoom/SKILL.md` | -2 | Description truncated with "..." |
| Q33 | R18-truncated-description | `skills/cli-anything-calibre/SKILL.md` | -2 | Description truncated with "..." |
| Q34 | R18-truncated-description | `skills/cli-anything-drawio/SKILL.md` | -2 | Description truncated with "..." |
| Q35 | R07-allowed-tools | `cli-anything-plugin/commands/*.md` | -5 (each) | Missing `allowed-tools` in all 5 command files |
| Q36 | R25-example-count | `skills/cli-anything-unimol-tools/SKILL.md` | -5 | Examples use `python3 -m cli_anything.unimol_tools` not the installed `cli-anything-unimol-tools` binary |

## Cross-Component Consistency

**Duplicate SKILL.md files:** Many skills appear in both `skills/cli-anything-<name>/SKILL.md` and `<name>/agent-harness/cli_anything/<name>/skills/SKILL.md`. In most cases the content is identical or nearly identical, which is acceptable. However, two cases show version discrepancies:

- `firefly-iii`: `skills/cli-anything-firefly-iii/SKILL.md` is version `2.0.0` while `firefly-iii/agent-harness/cli_anything/firefly_iii/skills/SKILL.md` appears to be an earlier version — the newer content should propagate to the harness-level copy.
- Naming conventions are inconsistent across `musescore` (frontmatter `name: musescore`), `quietshrink` (frontmatter `name: quietshrink`), and `iterm2-ctl` (heading/frontmatter mismatch). The dominant pattern in the repo is `name: "cli-anything-<software>"`.

**Command files vs skill files:** The 5 command files in `cli-anything-plugin/commands/` are Claude Code slash commands (not skills) and have a different format requirement (YAML frontmatter with name/description, allowed-tools). The skills are well-formed by comparison. The bug class is isolated to commands.

**No broken cross-references found** between the command files and the agent documentation they reference (HARNESS.md, TEST.md, README.md).

## Recommendation

**Approved for contribution with priority fix on command frontmatter.**

The repository demonstrates high-quality skill authorship with best-in-class examples (Safari, CloudCompare, FreeCAD, Firefly III, LLDB). The security posture is clean — no critical patterns, and the two LOW findings are by design and documented.

**Priority fixes (bugs):**

1. Add YAML frontmatter to all 5 command files in `cli-anything-plugin/commands/`:
   ```yaml
   ---
   name: "cli-anything"
   description: "Build a CLI-Anything harness for a GUI application or source repository."
   allowed-tools: ["Read", "Write", "Edit", "Bash", "mcp__github__search_code"]
   ---
   ```
   This fix would raise each command from 45 → ~90.

**Recommended quality improvements:**

2. Fix frontmatter `name` inconsistencies in `musescore`, `quietshrink`, `iterm2-ctl` SKILL.md files.
3. Expand Zotero SKILL.md command descriptions from "Execute `command`" to meaningful one-liners.
4. Add JSON output schema examples to `n8n`, `seaclip`, `obs-studio`, `zoom`, `chromadb`, `drawio`, `pm2`, `anygen`.
5. Fix truncated descriptions (11 files with "...") — these appear to be YAML `>-` block-scalar truncations that should be complete sentences.
6. Synchronize the `firefly-iii` skill versions between `skills/` and the harness-level copy.
