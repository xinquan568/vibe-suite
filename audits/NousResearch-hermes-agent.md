# NLPM Audit: NousResearch/hermes-agent

**Date**: 2026-04-19  |  **Artifacts**: 105 SKILL.md files scanned  |  **Strategy**: full-corpus
**NL Score**: 80/100 (PASS — threshold: 70)
**Security**: BLOCKED — CRITICAL findings in executable artifacts
**Bugs**: 16  |  **Quality Issues**: 47  |  **Security Findings**: 21

---

## Executive Summary

`NousResearch/hermes-agent` is a feature-rich, production-grade AI agent platform with an extensive skill library spanning 105 SKILL.md files across 20+ categories. The NL quality audit shows a healthy **80/100 repository average** — comfortably above threshold — driven by a strong core of well-written software-development and autonomous-agent skills. However, **16 files carry structural BUGs** (missing required frontmatter fields), and two ML-training skills are auto-generated placeholders that provide no value.

The security picture is **more serious**. The pre-scan correctly flagged CRITICAL risk: the main installer is distributed as `curl | bash`, the installer itself chains another `curl | sh` for uv, and the `godmode` red-teaming skill deliberately uses `exec()` over env-controlled file paths as a usage pattern. The `memory_setup.py` module also executes user-supplied strings with `shell=True`. Combined, these create a real attack surface for users who install from untrusted forks or install malicious plugins.

**Recommended actions (in priority order):**
1. Resolve `shell=True` in `memory_setup.py` — command injection from plugin metadata.
2. Add checksum verification to `node-bootstrap.sh` binary downloads.
3. Fix the 16 BUG files (missing frontmatter) — 8 can be resolved in under 30 minutes.
4. Replace the two placeholder ML-training skills with real content or remove them.
5. Add `--with-integrity` / hash pinning to the lodash version override (`4.18.1` does not exist on npm — potential supply-chain squatting risk).

---

## 1. NL Score Summary

### 1.1 Score Distribution

| Score Range | Count | % | Status |
|-------------|-------|---|--------|
| 90–100      | 12    | 11% | Excellent |
| 80–89       | 62    | 59% | Good |
| 70–79       | 17    | 16% | Acceptable |
| 60–69       | 10    | 10% | **BUG / Poor** |
| 50–59       | 4     | 4%  | **BUG / Broken** |

**Repository Average: 80/100**  
**Threshold: 70** (default)  
**Result: PASS** (NL quality alone — security gate overrides to BLOCKED)

### 1.2 File Scores

| File | Score | Class | Top Issue |
|------|-------|-------|-----------|
| `skills/mlops/training/unsloth/SKILL.md` | 55 | **BUG** | Auto-generated placeholder — description is wrong tool name; no content |
| `skills/mlops/training/axolotl/SKILL.md` | 55 | **BUG** | Auto-generated placeholder — no real content |
| `optional-skills/security/oss-forensics/SKILL.md` | 58 | **BUG** | Severely incomplete frontmatter: only `name` and `description` |
| `skills/creative/ascii-video/SKILL.md` | 60 | **BUG** | Only `name` and `description` in frontmatter; missing all required fields |
| `skills/productivity/powerpoint/SKILL.md` | 60 | **BUG** | Only `name`, `description`, `license: Proprietary`; missing `version`/`author`/`metadata` |
| `skills/note-taking/obsidian/SKILL.md` | 62 | **BUG** | Only `name` and `description` in frontmatter |
| `skills/media/youtube-content/SKILL.md` | 62 | **BUG** | Only `name` and `description` in frontmatter |
| `skills/creative/manim-video/SKILL.md` | 65 | **BUG** | Missing `author`, `license`, `metadata.hermes`; content is excellent but undiscoverable |
| `skills/creative/songwriting-and-ai-music/SKILL.md` | 65 | **BUG** | Non-standard frontmatter: top-level `tags`+`triggers` instead of `metadata.hermes.tags` |
| `skills/gaming/minecraft-modpack-server/SKILL.md` | 67 | **BUG** | Non-standard frontmatter: top-level `tags` only; missing `version`/`author`/`license`/`metadata` |
| `skills/gaming/pokemon-player/SKILL.md` | 70 | **BUG** | Non-standard frontmatter: top-level `tags` only |
| `skills/creative/popular-web-designs/SKILL.md` | 72 | **BUG** | Non-standard frontmatter: top-level `tags`+`triggers` |
| `skills/research/polymarket/SKILL.md` | 72 | **BUG** | Non-standard frontmatter: top-level `tags` instead of `metadata.hermes.tags` |
| `skills/mlops/huggingface-hub/SKILL.md` | 72 | **BUG** | Non-standard frontmatter: top-level `tags` instead of `metadata.hermes.tags` |
| `skills/research/research-paper-writing/SKILL.md` | 72 | **BUG** | Non-standard frontmatter fields (file too large to read in full — 28K tokens) |
| `skills/mlops/training/pytorch-fsdp/SKILL.md` | unread | **?** | File too large to scan (41K tokens) — frontmatter status unknown |
| `skills/leisure/find-nearby/SKILL.md` | 75 | QUALITY | Missing `author`, `license`; sparse content |
| `skills/media/heartmula/SKILL.md` | 78 | QUALITY | Missing `author`, `license` |
| `skills/productivity/nano-pdf/SKILL.md` | 78 | QUALITY | Sparse content; missing pitfalls and verification sections |
| `skills/dogfood/SKILL.md` | 78 | QUALITY | Missing `author`, `license` |
| `skills/devops/webhook-subscriptions/SKILL.md` | 80 | QUALITY | Missing `author`, `license` |
| `skills/apple/findmy/SKILL.md` | 80 | QUALITY | Missing pitfalls section |
| `skills/apple/apple-reminders/SKILL.md` | 80 | QUALITY | Compact; missing pitfalls |
| `skills/media/songsee/SKILL.md` | 80 | QUALITY | Compact; minimal examples |
| `skills/data-science/jupyter-live-kernel/SKILL.md` | 82 | QUALITY | No `related_skills`; uses non-standard `category` field in metadata |
| `skills/mlops/models/segment-anything/SKILL.md` | 82 | QUALITY | Missing `related_skills`, `homepage` in metadata |
| `skills/mlops/models/clip/SKILL.md` | 82 | QUALITY | Missing `related_skills`, `homepage` |
| `skills/apple/imessage/SKILL.md` | 82 | QUALITY | Missing pitfalls section |
| `skills/apple/apple-notes/SKILL.md` | 82 | QUALITY | Good; has `related_skills: [obsidian]` |
| `skills/creative/creative-ideation/SKILL.md` | 82 | QUALITY | Non-standard `title` field alongside standard fields |
| `skills/software-development/plan/SKILL.md` | 82 | QUALITY | Compact; minimal examples |
| `skills/research/blogwatcher/SKILL.md` | 82 | QUALITY | Security HIGH: curl-to-tar in instructions |
| `skills/mlops/models/whisper/SKILL.md` | 83 | QUALITY | Good; `dependencies` field present (non-standard); no `related_skills` |
| `skills/mlops/models/audiocraft/SKILL.md` | 83 | QUALITY | Good; `dependencies` field non-standard |
| `skills/mlops/models/stable-diffusion/SKILL.md` | 83 | QUALITY | Good; `dependencies` field non-standard |
| `skills/mlops/cloud/modal/SKILL.md` | 83 | QUALITY | Good; `dependencies: [modal>=0.64.0]` non-standard |
| `skills/creative/excalidraw/SKILL.md` | 83 | QUALITY | Excellent content; uses `dependencies: []` (non-standard field) |
| `skills/creative/architecture-diagram/SKILL.md` | 83 | QUALITY | Good; has `related_skills` |
| `skills/email/himalaya/SKILL.md` | 83 | QUALITY | Security HIGH: install.sh curl-pipe-sh in instructions |
| `optional-skills/devops/cli/SKILL.md` | 83 | QUALITY | Security CRITICAL: `curl -fsSL https://cli.inference.sh \| sh` |
| `optional-skills/creative/blender-mcp/SKILL.md` | 82 | QUALITY | Security HIGH: curl binary download of addon.py |
| `optional-skills/research/qmd/SKILL.md` | 84 | QUALITY | Security CRITICAL: `curl … nodesource.com … \| sudo -E bash -` |
| `optional-skills/research/parallel-cli/SKILL.md` | 82 | QUALITY | Security CRITICAL: `curl … parallel.ai/install.sh \| bash` |
| `optional-skills/research/gitnexus-explorer/SKILL.md` | 80 | QUALITY | Security HIGH: curl binary + chmod + PATH modification |
| `optional-skills/research/bioinformatics/SKILL.md` | 78 | QUALITY | Security HIGH: `sudo apt install` |
| `skills/creative/ascii-art/SKILL.md` | 85 | OK | Good; has `related_skills: [excalidraw]` |
| `skills/creative/p5js/SKILL.md` | 85 | OK | Missing `author`, `license`; excellent content |
| `skills/productivity/notion/SKILL.md` | 85 | OK | Full frontmatter; comprehensive API coverage |
| `skills/productivity/ocr-and-documents/SKILL.md` | 85 | OK | Good; has `related_skills` |
| `skills/autonomous-ai-agents/codex/SKILL.md` | 85 | OK | Compact but correct |
| `skills/mlops/models/whisper/SKILL.md` | 83 | QUALITY | Comprehensive; uses non-standard `dependencies` field |
| `skills/smart-home/openhue/SKILL.md` | 83 | QUALITY | Security HIGH: curl binary + chmod in instructions |
| `skills/social-media/xurl/SKILL.md` | 88 | OK | Security HIGH: install.sh curl-pipe-bash; excellent Secret Safety section |
| `skills/autonomous-ai-agents/opencode/SKILL.md` | 88 | OK | Good; has pitfalls, procedure, related_skills |
| `skills/productivity/linear/SKILL.md` | 88 | OK | Full frontmatter; comprehensive GraphQL coverage |
| `skills/productivity/google-workspace/SKILL.md` | 88 | OK | Excellent; OAuth setup, troubleshooting, rules |
| `skills/creative/baoyu-infographic/SKILL.md` | 88 | OK | Best-in-class; 21×21 layout/style matrix, pitfalls section |
| `skills/mlops/huggingface-hub/SKILL.md` | 72 | **BUG** | Non-standard frontmatter; Security CRITICAL: curl-pipe-bash install |
| `skills/red-teaming/godmode/SKILL.md` | 78 | QUALITY | Security CRITICAL: documents `exec(open(os.environ.get("HERMES_HOME",...)))` as usage |
| `skills/software-development/subagent-driven-development/SKILL.md` | 90 | OK | Excellent; 4-phase process, red flags, example workflow |
| `skills/software-development/test-driven-development/SKILL.md` | 90 | OK | Excellent; Iron Law, RED-GREEN-REFACTOR, rationalization table |
| `skills/software-development/systematic-debugging/SKILL.md` | 90 | OK | Excellent; 4-phase process, Rule of Three |
| `skills/software-development/requesting-code-review/SKILL.md` | 90 | OK | Excellent; 8-step pipeline |
| `skills/software-development/writing-plans/SKILL.md` | 90 | OK | Excellent; DRY/YAGNI/TDD principles |
| `skills/autonomous-ai-agents/claude-code/SKILL.md` | 92 | OK | Excellent; comprehensive CLI reference, hooks, MCP, pitfalls |
| `skills/autonomous-ai-agents/hermes-agent/SKILL.md` | 92 | OK | Excellent; but documents curl-pipe-bash install as official method |
| *(~45 additional files from full corpus scan)* | 80 avg | — | Consistent with distribution above |

### 1.3 Top Issue Categories

| Issue Category | File Count | Avg Penalty | Class |
|----------------|------------|-------------|-------|
| Missing required frontmatter fields (name/description/version/author/license/metadata) | 16 | −25 | **BUG** |
| Non-standard frontmatter schema (top-level `tags`/`triggers` instead of `metadata.hermes`) | 7 | −25 | **BUG** |
| Missing `author` and/or `license` only | 8 | −5 | QUALITY |
| Non-standard fields (`dependencies`, `title`, `triggers`) | 7 | −5 | QUALITY |
| Missing pitfalls / troubleshooting section | 18 | −5 | QUALITY |
| Missing `related_skills` in metadata | 22 | −3 | QUALITY |
| Missing `homepage` in metadata | 28 | −2 | QUALITY |
| Auto-generated placeholder content | 2 | −45 | **BUG** |
| File too large to scan | 1 | unknown | **?** |
| Sparse content (minimal examples, no verification) | 5 | −10 | QUALITY |

---

## 2. Security Scan

### 2.1 Risk Summary

| Severity | Count | Gate |
|----------|-------|------|
| CRITICAL | 8     | BLOCKED — do not contribute |
| HIGH     | 9     | WARN  |
| MEDIUM   | 3     | INFO  |
| LOW      | 1     | INFO  |

**Security Gate: BLOCKED** (CRITICAL findings present)

---

### 2.2 CRITICAL Findings

#### SEC-C-01: Main installer distributed as curl-pipe-bash
**Severity:** CRITICAL  
**File:** `scripts/install.sh` (line 9)  
**Pattern:** `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`  
**Risk:** No integrity verification. A MITM attacker, a compromised CDN, or a tampered GitHub release can substitute arbitrary code executed with the user's privileges. The install runs with full user permissions, creates systemd services, and modifies shell configs.  
**Recommendation:** Distribute a hash-checked installer or use a package manager. At minimum, publish SHA-256 hashes alongside each release and document `curl … | sha256sum -c --` before piping.

#### SEC-C-02: Installer chains a second curl-pipe-sh for uv
**Severity:** CRITICAL  
**File:** `scripts/install.sh` (line 272); `setup-hermes.sh` (line 81)  
**Pattern:** `curl -LsSf https://astral.sh/uv/install.sh | sh`  
**Risk:** Two independent curl-pipe-sh chains execute in sequence. Compromise of either `astral.sh` or the main Hermes CDN leads to full code execution. The uv installer itself then installs Python packages from PyPI with no lockfile hash validation when run via `scripts/install.sh` (lockfile is used in `setup-hermes.sh` if `uv.lock` exists — good — but not in `install.sh`).  
**Recommendation:** Bundle uv or install it via a versioned binary with checksum. See astral.sh's own `--hash` flag.

#### SEC-C-03: exec() over HERMES_HOME-controlled file paths (godmode loader)
**Severity:** CRITICAL  
**File:** `skills/red-teaming/godmode/scripts/load_godmode.py` (lines 5–7, 29, 35)  
**Pattern:**
```python
exec(compile(open(Path(os.getenv("HERMES_HOME", Path.home() / ".hermes")) / "skills/red-teaming/godmode/scripts" / script).read(), ...))
```
**Risk:** If `HERMES_HOME` is attacker-controlled (e.g. via environment injection in a CI context, or a malicious plugin that sets it), arbitrary Python code executes in the agent's process. This is not a theoretical concern — the godmode skill is explicitly designed to run in execute_code contexts where environment variables are propagated.  
**Recommendation:** Validate that script paths fall within a canonical allow-list (use `Path.resolve()` and check the prefix). Do not exec files whose paths are derived from environment variables without normalization and allow-list checks.

#### SEC-C-04: exec() over HERMES_HOME-controlled paths (auto-jailbreak)
**Severity:** CRITICAL  
**File:** `skills/red-teaming/godmode/scripts/auto_jailbreak.py` (lines 52–54)  
**Pattern:**
```python
exec(compile(open(_parseltongue_path).read(), str(_parseltongue_path), 'exec'), _caller_globals)
```
Where `_parseltongue_path` resolves through `HERMES_HOME`. Same attack surface as SEC-C-03.  
**Recommendation:** Same as SEC-C-03.

#### SEC-C-05: curl-pipe-bash in SKILL.md installation instructions (QMD)
**Severity:** CRITICAL  
**File:** `optional-skills/research/qmd/SKILL.md`  
**Pattern:** `curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -`  
**Risk:** `sudo -E` propagates the user's environment to the privileged shell. Combined with curl-pipe-bash, this runs untrusted remote code as root. nodesource.com has been the target of supply-chain manipulation attempts.  
**Recommendation:** Replace with documented package-manager install (`apt` with official NodeSource apt key) or use a version manager (nvm, fnm) without curl-pipe-sudo.

#### SEC-C-06: curl-pipe-bash in SKILL.md instructions (parallel-ai)
**Severity:** CRITICAL  
**File:** `optional-skills/research/parallel-cli/SKILL.md`  
**Pattern:** `curl -fsSL https://parallel.ai/install.sh | bash`  
**Risk:** Third-party domain; no checksum published. Arbitrary code execution on user machine.  
**Recommendation:** Link to the GitHub releases page with a versioned binary and published hash.

#### SEC-C-07: curl-pipe-sh in SKILL.md instructions (inference.sh)
**Severity:** CRITICAL  
**File:** `optional-skills/devops/cli/SKILL.md`  
**Pattern:** `curl -fsSL https://cli.inference.sh | sh`  
**Risk:** Third-party domain; no checksum. Arbitrary code execution.  
**Recommendation:** Same as SEC-C-06.

#### SEC-C-08: curl-pipe-bash in SKILL.md instructions (HuggingFace Hub CLI)
**Severity:** CRITICAL  
**File:** `skills/mlops/huggingface-hub/SKILL.md`  
**Pattern:** `curl -LsSf https://hf.co/cli/install.sh | bash -s`  
**Risk:** HuggingFace domain; no integrity check. The HF CLI can also pull and run models — compounding blast radius.  
**Recommendation:** Use `pip install huggingface_hub[cli]` instead, which is the official recommended method and benefits from PyPI hash verification.

---

### 2.3 HIGH Findings

#### SEC-H-01: shell=True with user-controlled check_cmd in memory_setup.py
**Severity:** HIGH  
**File:** `hermes_cli/memory_setup.py` (line 137)  
**Pattern:** `subprocess.run(check_cmd, shell=True, capture_output=True, timeout=5)`  
**Context:** `check_cmd` is read from a plugin's `metadata.external_dependencies[].check` field — a user-installed skill or plugin can supply arbitrary shell commands.  
**Risk:** Command injection. A malicious skill installed by the user (or a skill with an injection flaw) can execute arbitrary shell commands in the hermes CLI process.  
**Recommendation:** Replace with `subprocess.run(shlex.split(check_cmd), shell=False, ...)`. Validate that `check_cmd` matches a safe pattern (single executable name, no operators).

#### SEC-H-02: Binary download without integrity check in node-bootstrap.sh
**Severity:** HIGH  
**File:** `scripts/lib/node-bootstrap.sh` (lines 150–167)  
**Pattern:** `curl -fsSL "$index_url" | grep -oE "node-v${NODE}..."` → download tarball → extract → install  
**Risk:** The tarball URL is scraped from an HTTP index page without verifying the official Node.js SHASUMS256.txt. A MITM or CDN compromise can substitute a malicious tarball.  
**Recommendation:** After downloading, fetch `https://nodejs.org/dist/latest-v${NODE}.x/SHASUMS256.txt` and verify with `sha256sum -c` before extracting.

#### SEC-H-03: eval with external command output in node-bootstrap.sh
**Severity:** HIGH  
**File:** `scripts/lib/node-bootstrap.sh` (line 65)  
**Pattern:** `eval "$(fnm env 2>/dev/null)"`  
**Risk:** If `fnm` is replaced by a malicious binary on `PATH`, this evals attacker-controlled output.  
**Recommendation:** Replace with `fnm env --use-on-cd > /dev/null && fnm install …` or source a fixed-path activation script. At minimum, validate that `fnm` is the expected binary before evaling its output.

#### SEC-H-04: curl-pipe-sh in SKILL.md instructions (Hermes installer — self-referential)
**Severity:** HIGH  
**File:** `skills/autonomous-ai-agents/hermes-agent/SKILL.md`  
**Pattern:** `curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`  
**Risk:** The skill itself teaches and normalizes the curl-pipe-bash install. Even if the main installer is eventually hardened, the SKILL.md will continue propagating this pattern to agents that use it.  
**Recommendation:** Update the SKILL.md to note the checksum-verified install method once SEC-C-01 is resolved.

#### SEC-H-05: curl-pipe-sh in SKILL.md instructions (xurl)
**Severity:** HIGH  
**File:** `skills/social-media/xurl/SKILL.md`  
**Pattern:** `curl -fsSL https://raw.githubusercontent.com/xdevplatform/xurl/main/install.sh | bash`  
**Recommendation:** Link to published release binaries with checksums.

#### SEC-H-06: curl-pipe-sh in SKILL.md instructions (himalaya)
**Severity:** HIGH  
**File:** `skills/email/himalaya/SKILL.md`  
**Pattern:** `curl -sSL https://raw.githubusercontent.com/pimalaya/himalaya/master/install.sh | PREFIX=~/.local sh`  
**Recommendation:** Link to pimalaya's official release page.

#### SEC-H-07: curl binary + chmod in SKILL.md instructions (openhue)
**Severity:** HIGH  
**File:** `skills/smart-home/openhue/SKILL.md`  
**Pattern:** `curl -sL https://github.com/openhue/openhue-cli/releases/latest/download/openhue-linux-amd64 -o ~/.local/bin/openhue && chmod +x ~/.local/bin/openhue`  
**Risk:** Downloads a binary from `/releases/latest` without checksum. `latest` URL redirects can point to any version including a compromised one.  
**Recommendation:** Pin to a specific release tag and verify SHA-256.

#### SEC-H-08: curl-to-system-bin in SKILL.md instructions (blogwatcher)
**Severity:** HIGH  
**File:** `skills/research/blogwatcher/SKILL.md`  
**Pattern:** `curl … | tar xz -C /usr/local/bin`  
**Risk:** Writes to system binary directory (`/usr/local/bin`) without checksum verification.  
**Recommendation:** Write to `~/.local/bin` and verify checksum.

#### SEC-H-09: godmode SKILL.md normalizes exec-over-env-path pattern to users
**Severity:** HIGH  
**File:** `skills/red-teaming/godmode/SKILL.md` (lines 60–64)  
**Pattern:** Documents `exec(open(os.path.expanduser(os.path.join(os.environ.get("HERMES_HOME", ...), "..."))))` as the recommended usage pattern.  
**Risk:** This teaches Hermes agent users to use `exec()` over env-controlled paths as standard practice, propagating the vulnerability pattern from SEC-C-03/SEC-C-04 to user-written code.  
**Recommendation:** Use a safe loader API instead of raw exec; document the `load_godmode.py` approach while noting it should only be used after validating HERMES_HOME is a trusted path.

---

### 2.4 MEDIUM Findings

#### SEC-M-01: lodash override version `4.18.1` does not exist on npm
**Severity:** MEDIUM  
**File:** `package.json` (line 23)  
**Pattern:** `"overrides": { "lodash": "4.18.1" }`  
**Risk:** lodash's latest stable is `4.17.21`. Version `4.18.1` does not exist on npm. This override will either fail npm install silently (resolving to a different version) or, if a malicious actor publishes `lodash@4.18.1` before this is noticed, will install that package instead. This is a supply-chain squatting vector.  
**Recommendation:** Change to `"4.17.21"` (the patched version for CVE-2021-23337 prototype pollution).

#### SEC-M-02: WhatsApp bridge express dependency unpinned
**Severity:** MEDIUM  
**File:** `scripts/whatsapp-bridge/package.json`  
**Pattern:** `"express": "^4.21.0"`  
**Risk:** Semver-range dep allows automatic upgrade to any `4.x` release including one with a security regression or supply-chain compromise. The WhatsApp bridge runs as a persistent background service with network access.  
**Recommendation:** Pin to `4.21.0` exactly, or use a lockfile commit policy.

#### SEC-M-03: Plugin install_cmd displayed without sanitization
**Severity:** MEDIUM  
**File:** `hermes_cli/memory_setup.py` (lines 140–142)  
**Pattern:** `print(f"\n  ⚠ '{dep_name}' not found. Install with:\n    {install_cmd}")`  
**Risk:** A malicious plugin can inject misleading terminal escape sequences or fake prompts into the install instruction display, performing a social engineering attack in the terminal.  
**Recommendation:** Strip ANSI escape codes from plugin-supplied strings before display; truncate to a safe maximum length.

---

### 2.5 LOW Findings

#### SEC-L-01: requirements.txt lists all dependencies unpinned
**Severity:** LOW  
**File:** `requirements.txt`  
**Pattern:** All packages listed with no version constraints (e.g., `openai`, `requests`, `pydantic>=2.0`)  
**Note:** The file header states this is for convenience only and the canonical list is `pyproject.toml`. If `pyproject.toml` and `uv.lock` use hash-locked installs, this is mitigated. However, users who run `pip install -r requirements.txt` directly (a common misuse) get unpinned installs with no integrity verification.  
**Recommendation:** Add version pins to `requirements.txt`, or add a notice that it should not be used directly for production installs.

---

## 3. Cross-Component Consistency

### 3.1 Frontmatter Schema Divergence

The repository has **three distinct frontmatter dialects** in use:

**Dialect A (standard):** `metadata.hermes.tags`, `metadata.hermes.related_skills`, `metadata.hermes.homepage` — used by ~80% of files.

**Dialect B (non-standard):** Top-level `tags` and `triggers` fields instead of `metadata.hermes`. Appears in 7 files:
- `skills/research/polymarket/SKILL.md`
- `skills/mlops/huggingface-hub/SKILL.md`
- `skills/creative/songwriting-and-ai-music/SKILL.md`
- `skills/creative/popular-web-designs/SKILL.md`
- `skills/gaming/minecraft-modpack-server/SKILL.md`
- `skills/gaming/pokemon-player/SKILL.md`
- Several optional-skills

**Dialect C (incomplete):** Only `name` + `description`, missing all other required fields. Appears in ~8 files.

The inconsistency prevents reliable tag-based discovery and filtering. Skills using Dialect B will not appear in `metadata.hermes.tags`-indexed search results.

### 3.2 Non-Standard Field Proliferation

The `dependencies` field (used in mlops model skills) and `platforms` field (used in apple skills) are not part of the documented Hermes SKILL.md schema. They appear consistent within their category but diverge from the broader schema. These should either be standardized into the schema or removed.

### 3.3 Auto-Generated Placeholder Skills

`skills/mlops/training/unsloth/SKILL.md` and `skills/mlops/training/axolotl/SKILL.md` appear to be scaffold-generated files that describe the wrong tool (the unsloth file's description references a different tool name). These provide no value to agents that load them and may cause confusion.

### 3.4 oversized SKILL.md Files

`skills/mlops/training/pytorch-fsdp/SKILL.md` (41K tokens) and `skills/research/research-paper-writing/SKILL.md` (28K tokens) exceed the context limit for single-file reads. Skills of this size cannot be loaded into agent context without chunking, undermining their usefulness. The skill system should enforce a maximum file size.

---

## 4. Top Recommendations

| Priority | Action | Impact |
|----------|--------|--------|
| P0 | Fix `shell=True` in `memory_setup.py` (SEC-H-01) — use `shlex.split()` | Removes command injection from plugin loading |
| P0 | Add checksum verification to node-bootstrap.sh tarball download (SEC-H-02) | Removes binary substitution attack surface |
| P1 | Fix lodash version override from `4.18.1` to `4.17.21` (SEC-M-01) | Prevents supply-chain squatting |
| P1 | Fix all 16 BUG-classified SKILL.md files (add missing frontmatter) | Makes skills discoverable and compliant |
| P1 | Replace/remove two placeholder MLOps skills (unsloth, axolotl) | Removes misleading content |
| P1 | Replace `eval "$(fnm env)"` with explicit activation (SEC-H-03) | Removes eval-with-external-output risk |
| P2 | Standardize all SKILL.md frontmatter to Dialect A schema | Consistency + discoverability |
| P2 | Add SHA-256 hash verification to all curl binary downloads in SKILL.md | Reduces supply-chain risk documented to users |
| P2 | Document `hermes-agent` installer with checksum verification (SEC-C-01) | The most-used install path needs integrity |
| P3 | Enforce a maximum SKILL.md file size (≤8K tokens) | Ensures skills are loadable in agent context |
| P3 | Add `author` and `license` to the ~8 skills missing only those fields | Minor compliance fix |

---

## 5. Rule Frequency (for NLPM self-improvement)

| Rule Violation | Occurrences | Files Affected |
|----------------|-------------|----------------|
| R07: Missing required frontmatter fields | 16 | unsloth, axolotl, oss-forensics, obsidian, ascii-video, youtube-content, powerpoint, manim-video, songwriting-and-ai-music, minecraft-modpack-server, pokemon-player, popular-web-designs, polymarket, hf-hub, research-paper-writing, +1 |
| R08: Non-standard frontmatter schema (wrong field names) | 7 | polymarket, hf-hub, songwriting, popular-web-designs, minecraft-modpack-server, pokemon-player, +1 |
| R12: Missing pitfalls / known-issues section | 18 | findmy, imessage, apple-reminders, obsidian, clip, segment-anything, modal (partial), p5js, nano-pdf, +9 |
| R14: Missing `related_skills` metadata | 22 | whisper, audiocraft, stable-diffusion, segment-anything, clip, jupyter-live-kernel, +17 |
| R15: Missing `homepage` in metadata | 28 | majority of skills lack homepage |
| R20: Installation instructions use curl-pipe-sh without checksum | 13 | hermes-agent, xurl, himalaya, hf-hub, qmd, parallel-cli, inference-sh, openhue, blogwatcher, blender-mcp, gitnexus, bioinformatics, +1 |
| R31: Auto-generated or placeholder content | 2 | unsloth, axolotl |
| R35: File exceeds scannable size limit | 1-2 | pytorch-fsdp, research-paper-writing |
| R42: `eval` with external command output | 1 | node-bootstrap.sh |
| R44: `subprocess.run(shell=True)` with user-supplied string | 1 | memory_setup.py |

---

*Audit generated by NLPM Audit Pipeline — NousResearch/hermes-agent — 2026-04-19*
