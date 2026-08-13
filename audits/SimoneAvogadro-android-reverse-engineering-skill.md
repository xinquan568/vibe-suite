# NLPM Audit: SimoneAvogadro/android-reverse-engineering-skill
**Date**: 2026-04-06  |  **Artifacts**: 3  |  **Strategy**: single
**NL Score**: 92/100
**Security**: BLOCKED
**Bugs**: 1  |  **Quality Issues**: 8  |  **Security Findings**: 5

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/android-reverse-engineering/commands/decompile.md | command | 83/100 | Unused Write+Edit in allowed-tools; missing output format section |
| plugins/android-reverse-engineering/skills/android-reverse-engineering/SKILL.md | skill | 92/100 | Four vague comparators ("better results", "broad sweep") |
| plugins/android-reverse-engineering/.claude-plugin/plugin.json | manifest | 100/100 | None |

### Score detail

**plugin.json** — 100/100  
No penalties. All required fields present (name, version, description, author). Valid semver `1.1.0`. Paths `./skills/` and `./commands/` verified to exist.

**commands/decompile.md** — 83/100  
Penalties: missing output format section (−5), unused `Write` tool (−3), unused `Edit` tool (−3), "better results" line 40 (−2), "better Java output" line 53 (−2), "best quality" line 62 (−2). Empty-input handling: ✓ Step 1 asks the user if no argument given. Numbered steps: ✓ Steps 1–5.

**SKILL.md** — 92/100  
Penalties: "best results" line 64 (−2), "better Java output" table ~line 97 (−2), "better code" line 104 (−2), "broad sweep" line 159 (−2). Prerequisites, phased workflow, output section, and references are all present and well-structured.

---

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 2 |
| Medium | 2 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Scripts | 4 — `scripts/check-deps.sh`, `scripts/decompile.sh`, `scripts/find-api-calls.sh`, `scripts/install-dep.sh` |
| Hooks | 0 |
| MCP configs | 0 |
| Package manifests | 0 |

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | HIGH | plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/install-dep.sh | 92, 99, 105 | SEC-sudo | `pkg_install()` invokes `sudo apt-get`, `sudo dnf`, `sudo pacman`; package names are hardcoded so no injection risk, but sudo elevation is unconditional if available |
| 2 | HIGH | plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/install-dep.sh | 144–163, 244, 309, 385 | SEC-path-modification | `add_to_profile()` appends `export PATH=...` and `export FERNFLOWER_JAR_PATH=...` to `~/.zshrc`, `~/.bashrc`, or `~/.profile` — persistent file writes outside the repo and permanent PATH modification |
| 3 | MEDIUM | plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/install-dep.sh | 230, 297, 347 | SEC-unverified-binary | `install_jadx`, `install_vineflower`, `install_dex2jar` each download a zip/JAR from GitHub releases via `download()` with no SHA-256 or signature check before execution |
| 4 | MEDIUM | plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/install-dep.sh | 122–141 | SEC-network-fetch | `download()` (curl/wget) and `gh_latest_tag()` make outbound network calls to GitHub at install time; no pinned version or integrity check on the API response |
| 5 | LOW | plugins/android-reverse-engineering/skills/android-reverse-engineering/scripts/decompile.sh | 110 | SEC-user-content-display | `cat "$XAPK_EXTRACTED_DIR/manifest.json"` prints raw JSON from a user-supplied archive to stdout; display-only, no code execution, but content is unsanitised |

---

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| 1 | plugins/android-reverse-engineering/commands/decompile.md | `Write` and `Edit` declared in `allowed-tools` but never used in any of the 5 command steps; decompilation and output are handled by Bash scripts and Read/Glob/Grep respectively | Unnecessary permission prompts for Write/Edit; signals broader tool scope than needed |

---

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/install-dep.sh | Binary downloads from GitHub without checksum verification | After each `download` call, verify the file's SHA-256 against the checksum published on the GitHub release page before extracting or executing |
| 2 | scripts/install-dep.sh | `add_to_profile` permanently modifies shell profiles without user consent | Add a `--no-profile-modify` flag (or default to requiring explicit `--modify-profile`) and print the export lines for the user to add manually when the flag is absent |
| 3 | scripts/decompile.sh | `cat` on unsanitised manifest.json from user-supplied archive | Pipe through `jq .` (if available) or at minimum validate the file is valid JSON before display; reject non-JSON content |

---

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | commands/decompile.md | No formal `## Output` section; format guidance is embedded in step prose ("Report a summary to the user") rather than a structured template | −5 |
| 2 | commands/decompile.md | "better results" (line 40) — undefined comparator | −2 |
| 3 | commands/decompile.md | "better Java output" (line 53) — undefined comparator | −2 |
| 4 | commands/decompile.md | "best quality" (line 62) — undefined comparator | −2 |
| 5 | skills/android-reverse-engineering/SKILL.md | "best results" (line 64) — undefined comparator | −2 |
| 6 | skills/android-reverse-engineering/SKILL.md | "better Java output" (engine-selection table, ~line 97) — undefined comparator | −2 |
| 7 | skills/android-reverse-engineering/SKILL.md | "better code" (line 104) — undefined comparator | −2 |
| 8 | skills/android-reverse-engineering/SKILL.md | "broad sweep" (line 159) — vague scope quantifier | −2 |

---

## Cross-Component

**Functional defect in find-api-calls.sh (lines 112, 114):** The `run_grep()` function signature is `run_grep() { local pattern="$1"; … }`. Two calls in the `--auth` block pass `-i` as `$1` (making `pattern="-i"`) and the actual regex as `$2`, which is silently discarded. The auth-credential and base-URL searches therefore grep for the literal string `-i` instead of the intended case-insensitive patterns. The `--auth` flag is functionally broken.

**Reference consistency:** All five `references/` files cited by SKILL.md (`setup-guide.md`, `jadx-usage.md`, `fernflower-usage.md`, `api-extraction-patterns.md`, `call-flow-analysis.md`) are present on disk. ✓

**Script path consistency:** `${CLAUDE_PLUGIN_ROOT}/skills/android-reverse-engineering/scripts/` is used identically in both `commands/decompile.md` and `SKILL.md`. ✓

**plugin.json path resolution:** `"skills": "./skills/"` and `"commands": "./commands/"` both resolve to existing directories within the plugin root. ✓

---

## Recommendation

**BLOCKED — do not submit PRs. File private security report.**

Two HIGH findings block contribution: `sudo` invocation in `install-dep.sh` and persistent shell-profile writes with PATH modification. Both are standard install-script patterns with no injection risk given the hardcoded package names, but they require explicit maintainer acknowledgement before a PR is appropriate. File a private security advisory on the target repo describing findings #1 and #2, and request the maintainer confirm the behaviour is intentional or add consent prompts.

Once the maintainer acknowledges the HIGH findings, the NL bug (unused Write/Edit in `decompile.md`) and the medium/low security fixes (checksum verification, `--no-profile-modify` flag, JSON validation) are clean PR candidates. The `run_grep -i` functional defect in `find-api-calls.sh` is also a strong PR candidate independent of the security gate.
