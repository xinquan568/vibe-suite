# NLPM Audit: evo-hq/evo
**Date**: 2026-05-05  |  **Artifacts**: 4  |  **Strategy**: single
**NL Score**: 98/100
**Security**: CLEAR
**Bugs**: 0  |  **Quality Issues**: 4  |  **Security Findings**: 7

## NL Score Summary
| File | Type | Score | Top Issue |
|------|------|-------|-----------|
| plugins/evo/skills/discover/SKILL.md | skill | 96/100 | Vague quantifiers: "handful" (L71), "few lines" (L208) |
| plugins/evo/skills/optimize/SKILL.md | skill | 98/100 | Vague quantifier: "meaningfully different" (L147) |
| plugins/evo/skills/subagent/SKILL.md | skill | 98/100 | Vague quantifier: "meaningfully different idea" (L153) |
| plugins/evo/.claude-plugin/plugin.json | manifest | 100/100 | None |

Weighted average: (96 + 98 + 98 + 100) / 4 = **98/100**. Penalty breakdown: discover −4 (two R01 hits), optimize −2 (one R01 hit), subagent −2 (one R01 hit). No missing frontmatter, broken references, or structural bugs across any artifact.

## Security Scan
| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 0 |
| Medium | 6 |
| Low | 1 |

### Execution Surface Inventory
| Surface | Files |
|---------|-------|
| Hooks | 0 |
| Shell scripts | plugins/evo/bin/evo, plugins/evo/bin/evo-version-check |
| Python scripts | scripts/evo, scripts/dashboard.py, scripts/graph.py, scripts/scratchpad.py, scripts/check_versions.py, scripts/rlm_eval/generate_fixture.py, scripts/rlm_eval/rlm_eval.py, scripts/rlm_eval/score.py, scripts/rlm_eval/score_llm.py, plugins/evo/skills/discover/scripts/validate_result.py, plugins/evo/skills/discover/references/inline_instrumentation.py, plugins/evo/skills/discover/references/sdk_python.py |
| JS reference files | plugins/evo/skills/discover/references/inline_instrumentation.js, plugins/evo/skills/discover/references/sdk_node.js |
| MCP configs | 0 |
| Package manifests | plugins/evo/pyproject.toml, sdk/node/package.json |

Note: `plugins/evo/bin/evo` contains a heredoc that prints `curl -LsSf https://astral.sh/uv/install.sh | sh` as user-facing installation guidance (stderr output only) — the script never executes this curl command. Pre-scan correctly rated this CLEAR; confirmed false positive.

### Security Findings
| # | Severity | File | Line | Pattern | Description |
|---|----------|------|------|---------|-------------|
| 1 | Medium | scripts/rlm_eval/generate_fixture.py | 315 | subprocess-external-process | `subprocess.run([claude, "-p", ...])` calls the claude CLI (network call to Anthropic API) with an internally-constructed prompt. No `shell=True`; prompt is built from hardcoded CASES data, not external input. Eval-tooling context only. |
| 2 | Medium | scripts/rlm_eval/rlm_eval.py | 172 | subprocess-external-process | `subprocess.run([claude, "-p", ...])` calls claude CLI for trial execution. No `shell=True`; prompt is built from `textwrap.dedent(...)` literal. Eval-tooling context only. |
| 3 | Medium | scripts/rlm_eval/score_llm.py | 153 | subprocess-external-process | `subprocess.run([claude, "-p", ...])` calls claude CLI as LLM judge. No `shell=True`; prompt assembled from ground truth + model output JSON. Eval-tooling context only. |
| 4 | Medium | scripts/rlm_eval/generate_fixture.py | 234 | file-write-outside-repo | Writes raw LLM debug output to `/tmp/rlm_narr_{case_id}_raw.txt` on JSON parse failure. Path is constructed with `case_id` drawn from the hardcoded CASES dict (no traversal risk). |
| 5 | Medium | scripts/rlm_eval/rlm_eval.py | 154 | file-write-outside-repo | Creates isolated trial directory in `tempfile.gettempdir()` for each trial run. Intentional test-isolation pattern; `uuid4().hex[:8]` suffix prevents collisions. |
| 6 | Medium | plugins/evo/skills/discover/references/inline_instrumentation.py | 19 | env-var-file-path | `EVO_TRACES_DIR` and `EVO_RESULT_PATH` env vars determine where trace files and result JSON are written. This is the documented evo wire protocol; the caller (`evo run`) controls these vars. By design, but worth noting for users who copy this template into untrusted contexts. |
| 7 | Low | plugins/evo/pyproject.toml | 9 | unpinned-semver | Runtime dependencies `flask>=3.0.0`, `portalocker>=2.8.0`, `pyyaml>=6.0.0` use open `>=` specifiers, allowing future breaking major versions. `uv.lock` pins exact resolved versions for installs via this plugin, which mitigates the risk in practice. |

## Bugs (PR-worthy)
| # | File | Issue | Impact |
|---|------|-------|--------|
| — | — | No bugs found. All required frontmatter present; all cross-references resolve; no broken tool declarations. | — |

## Security Fixes (PR-worthy, Medium/Low only)
| # | File | Issue | Suggested Fix |
|---|------|-------|---------------|
| 1 | scripts/rlm_eval/generate_fixture.py | /tmp debug writes on JSON parse failure (L234, L244) | Use `tempfile.NamedTemporaryFile(prefix='rlm_narr_', suffix='.txt', delete=False)` instead of hardcoding `/tmp/`; more portable on Windows/WSL2. |
| 2 | plugins/evo/pyproject.toml | Unpinned semver (`>=`) for flask, portalocker, pyyaml | Pin to minor-compatible ranges (`flask>=3.0.0,<4`, etc.) so future majors don't silently pull in breaking changes for installs without `uv.lock` (e.g., pipx users). |

Findings #1–3 (subprocess calls to claude CLI) and #5 (tempfile trial dir) are intentional eval-framework behavior and do not warrant PRs. Finding #6 (env-var file path in inline_instrumentation.py) is the documented evo protocol; no fix needed, but worth a comment in the template for security-sensitive environments.

## Quality Issues (informational)
| # | File | Issue | Penalty |
|---|------|-------|---------|
| 1 | plugins/evo/skills/discover/SKILL.md:71 | "A handful of dimensions" — "handful" is a vague quantifier (R01 list: comparable to "several"). No measurable criterion given. | −2 |
| 2 | plugins/evo/skills/discover/SKILL.md:208 | "a few lines: parse the threshold flag" — "few" is vague (comparable to R01 "some/several"). | −2 |
| 3 | plugins/evo/skills/optimize/SKILL.md:147 | "without meaningfully different framings" — "meaningfully" is vague (similar to R01 pattern; cf. calibration example "well-organized"). No operationalized criterion for when framings are "meaningfully" distinct. | −2 |
| 4 | plugins/evo/skills/subagent/SKILL.md:153 | "a meaningfully different idea" — same vague modifier as #3. Subagents can't determine what "meaningful" means without a threshold. | −2 |

## Cross-Component
All internal references verified clean:
- discover/SKILL.md references `references/proposing-dimensions.md`, `references/constructing-benchmark.md`, `references/inline_instrumentation.{py,js}`, `references/sdk_{python.py,node.js}`, `scripts/validate_result.py` — all exist on disk at the expected relative paths.
- optimize/SKILL.md cross-references `skills/subagent/SKILL.md` (line 54) — path resolves correctly within the plugin directory tree.
- subagent/SKILL.md's `disable-model-invocation: true` frontmatter key is non-standard but benign; the description "Not user-invocable" is the human-readable equivalent. Hosts that don't recognize the key ignore it safely.
- plugin.json does not enumerate skills; skill discovery relies on directory convention rather than a manifest `skills:` list. This matches the `.codex-plugin/plugin.json` structure (same minimal schema), suggesting this is intentional for this plugin family. No inconsistency.
- No orphaned components, no stale cross-references, no terminology drift between the three skills.

## Recommendation
CLEAR — submit PRs for all bugs and medium/low security fixes.

No bugs were found, so there are no NL-fix PRs to open. The two security fix candidates (debug /tmp path portability in `generate_fixture.py` and minor-capped semver bounds in `pyproject.toml`) are genuinely low-risk improvements worth a PR if the maintainer is receptive. The six Medium security findings are expected patterns for an LLM evaluation framework and do not represent vulnerabilities. No private disclosure required.
