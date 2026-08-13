# 69,816 Stars, Four Hidden Skills

![Cover](images/2026-05-11-mattpocock-skills-cover.webp)

> **Disclosure**: Written from NLPM audit data on 2026-05-11 and re-verified against the live state of `mattpocock/skills` the same day. The repository's plugin manifest and the affected `SKILL.md` files were inspected directly via `git ls-tree` and `gh api`; star and fork counts come from `GET /repos/mattpocock/skills` at audit time. Cover image generated with OpenAI `gpt-image-1` (gpt-image-2 was requested but requires org verification not enabled on this account).

---

## The Project

[`mattpocock/skills`](https://github.com/mattpocock/skills) is Matt Pocock's personal Claude Code skill kit, published 2026-02-03 with the tagline _"Skills for Real Engineers. Straight from my .claude directory."_ Three months later it carries **69,816 stars and 6,039 forks** — by raw popularity the most prominent skill kit on GitHub outside Anthropic's own examples. Matt is one of the most-followed TypeScript educators in the ecosystem; the repository's reach is amplified by his Twitter/YouTube footprint.

The repository's purpose is to package his daily TS/engineering workflow as installable Claude Code skills covering TDD, code review, refactoring, prototyping, triage, and writing. Users discover it through Matt's social channels and run `claude plugin install` against it.

---

## The Audit

**Date**: 2026-05-11 | **Artifacts scored**: 30 | **NL Score**: **98/100** | **Security**: CLEAR

The skill kit is, in nearly every respect, exemplary. Twenty-six of the thirty scored artifacts landed between 96 and 100. The two scripts in `skills/misc/git-guardrails-claude-code/scripts/` and `skills/engineering/diagnose/scripts/` passed security scrutiny — no eval, no curl-pipe-sh, no credential exfil. The bundled scripts include a guard against creating symlinks into the repo (`scripts/link-skills.sh`), which is good defensive design. The CLAUDE.md is terse and accurate. The frontmatter on every `SKILL.md` is valid.

If the score were the only signal, the audit would close with "well-built; minor `relevant` vague-quantifier hits on 14 lines." That's not the audit's interesting finding.

The interesting finding is that **four of the skills users see on the README are not in the manifest**.

---

## The Bug

The repository's `.claude-plugin/plugin.json` enumerates skills via an explicit `skills:` array (not the directory-wildcard form). At audit time it listed 26 skills. The disk had 30 `SKILL.md` files. The diff:

| Disk path | Featured in README? | In `plugin.json`? |
|---|---|---|
| `skills/misc/git-guardrails-claude-code/SKILL.md` | Yes (line 172) | **No** |
| `skills/misc/setup-pre-commit/SKILL.md` | Yes (line 173) | **No** |
| `skills/misc/migrate-to-shoehorn/SKILL.md` | Yes (line 174) | **No** |
| `skills/misc/scaffold-exercises/SKILL.md` | Yes (line 175) | **No** |

All four files are present on disk with valid `name:` and `description:` frontmatter. All four are listed and described in the top-level `README.md` and again in `skills/misc/README.md`. They are intended to be public, active skills. They are simply absent from the manifest array.

When a user runs `claude plugin install mattpocock-skills`, the runtime reads the manifest, sees 26 skill paths, and registers those. The four `misc/` skills exist on disk but are invisible to the loader. The user, looking at the README that advertised them, has no signal that anything is missing — `claude plugin install` succeeds, no warning emitted.

The audit's other 16 findings are mechanical: vague-quantifier hits on the word "relevant" across 14 sub-agent prompts, plus two truncated `## Output` sections. None are user-visible runtime bugs. The four missing manifest entries are.

---

## The Self-Mandate

The audit's most striking finding sits not in the score but in the cross-component check.

`CLAUDE.md` in the same repository contains this rule, verbatim:

> _"Every skill in `engineering/`, `productivity/`, or `misc/` must have…an entry in `.claude-plugin/plugin.json`."_

The maintainer's own contributing guide mandates the exact check the manifest fails. The other category prefixes — `skills/in-progress/`, `skills/personal/`, `skills/deprecated/` — are correctly absent from the manifest, consistent with their names. Only the `misc/` group violates the self-imposed rule.

The bug is not philosophical disagreement with the rule. It's that the rule isn't automated. The author wrote it, then drifted from it as the kit grew.

---

## Why The Other Validators Don't Catch It

Eight other validators are in active development for Claude Code plugins, including Anthropic's own [`plugin-validator`](https://github.com/anthropics/claude-code/blob/main/plugins/plugin-dev/agents/plugin-validator.md) agent and the [Linux Foundation's `skills-ref`](https://github.com/agentskills/agentskills) reference library. Running any of them against `mattpocock/skills` produces a clean report.

| Validator | What it checks | Catches this bug? |
|---|---|---|
| `claude plugin validate` (Anthropic CLI) | Manifest JSON syntax | No |
| `plugin-validator` (Anthropic agent) | Per-component frontmatter; manifest field shapes; MCP security | **No** — explicitly outside its documented scope |
| `agentskills` / `skills-ref` (Linux Foundation) | Per-`SKILL.md` frontmatter and naming | No — operates at the skill boundary, not the plugin boundary |
| Six third-party linters | Various per-file checks | No |
| **NLPM `/nlpm:check` and `bin/nlpm-check`** | Manifest array vs. disk enumeration | **Yes** — the diff is mechanical |

The full ecosystem comparison and reasoning is in [`analysis/ecosystem-gap.md`](../analysis/ecosystem-gap.md). The short version: every validator concentrates at the single-artifact boundary because per-file linters are easier to ship; the cross-artifact diff requires reading two enumerations at once. The bug class survives because the gate doesn't exist in any tool the maintainer has reached for.

---

## The Submission Problem

The audit reproduced the finding locally and prepared a fork + branch + push to `xiaolai/skills-1` for a pull request. GitHub returned the GraphQL response:

```
xiaolai does not have the correct permissions to execute CreatePullRequest
```

The fork existed, the branch was pushed, the token had the right scopes. The repository's collaboration policy simply does not permit external PRs. Running `gh pr list --repo mattpocock/skills` confirms it:

| State | Count |
|---|---:|
| Merged | **1** (PR #90, authored by `mattpocock` himself, 2026-04-28) |
| Closed unmerged | **41** |
| Open | **0** |

No external pull request has ever merged in the repository's three-month history. Forty-one have been opened and closed without merging. The single merged PR is the owner's own — a self-PR to rename the `setup-matt-pocock-skills` skill and migrate others to "vague prose."

The repository accepts issues, however. External contributor `vltansky` filed issue #163 the day before this audit (2026-05-10) and Matt has historically engaged with issues. The audit's findings were filed as **[issue #164](https://github.com/mattpocock/skills/issues/164)** instead, following the maintainer's evident preference. The issue body included the exact `diff` invocation that reproduces the four missing entries.

```bash
diff <(jq -r '.skills[]' .claude-plugin/plugin.json | sort) \
     <(find skills -path 'skills/*/*/SKILL.md' -type f | sed 's|/SKILL.md||;s|^|./|' | sort)
```

As of the audit date, the issue is open with no maintainer response.

---

## The Tension

The repository contains, in this order:

1. A `CLAUDE.md` mandating that every `misc/` skill be registered in the manifest.
2. A `README.md` featuring four `misc/` skills as live, supported entries.
3. A `plugin.json` that omits all four.
4. A history of 41 closed external PRs, no merges.

The user-visible effect: someone reads Matt's README, runs `claude plugin install mattpocock-skills`, and gets a kit missing four of the skills they came for. They will not know which four. The kit's `claude plugin install` exit code is zero. The official Anthropic validator's exit code is also zero. The README they came in through still advertises the missing skills as installed.

For the audit pipeline, the case is a sharp instance of the ecosystem gap NLPM has documented across five high-profile repos (`graphify`, `kubesphere`, `tanweai`, `agent-sh`, and now `mattpocock`): authors with deep domain knowledge ship manifest-vs-disk inconsistencies because no tool in their toolchain checks for them, and the bug class is invisible to the developer-time loop ("works on my machine, because my `.claude/` walks the filesystem").

The case for the manifest-vs-disk check existing in canonical form is not theoretical. The most-starred skill kit on GitHub demonstrates it directly.

---

## What NLPM Did, And Didn't

NLPM produced the finding. The audit report and per-finding sidecar are committed at [`auditor/audits/mattpocock-skills.md`](../auditor/audits/mattpocock-skills.md). The finding was filed as [issue #164](https://github.com/mattpocock/skills/issues/164). The issue's outcome depends on Matt; the audit pipeline tracks it for downstream learning.

NLPM did **not** open a pull request. The earlier memory entry implied "0 PRs in history" — imprecise. The actual count is 1 self-merge and 41 closed external PRs. Either way, the implicit policy is unambiguous: no external code lands.

NLPM also did not add `mattpocock/*` to the `DENY_OWNERS` list. The pattern is a per-repository policy, not org-wide. If a second mattpocock repository surfaces in the discovery pipeline and exhibits the same shape, the evidence will be re-evaluated. Until then, the gate is "verify external-merge history before attempting a PR" — encoded as a one-line `gh pr list` check in the contributing memory.

The case study you are reading is the third place this finding will surface: the per-repo audit report (private, in `auditor/audits/`), the upstream issue (public, awaiting maintainer response), and this article (public, evidence for the rule's existence).

---

## The Broader Argument

`mattpocock/skills` is a near-perfect skill kit by every test except one. The author is an experienced TypeScript educator, the security surface is clean, the frontmatter is valid, the descriptions are well-written. The bug that survives is not a quality problem. It is an ecosystem problem: the layer at which the bug sits has no validator in canonical form, and the layer the validators do cover — per-file frontmatter, per-script security — was passed cleanly.

The 69,816 stars are evidence of the author's craft and reach. They are not evidence that the kit installs as advertised. The single check that would have surfaced the discrepancy — comparing the manifest's `skills:` array against `find skills -name SKILL.md` — exists in no validator the author has reason to reach for. NLPM ships it. After v0.8.0, ships it as a standalone Python script with no Claude Code dependency, designed for the pre-commit and CI loops the author has but hasn't yet wired up.

The bug, in a repository this prominent, is not embarrassing for the author. It is informative for the ecosystem.

---

## Links

- Audit report: [`auditor/audits/mattpocock-skills.md`](../auditor/audits/mattpocock-skills.md)
- Upstream issue: [mattpocock/skills#164](https://github.com/mattpocock/skills/issues/164)
- Ecosystem-gap research: [`analysis/ecosystem-gap.md`](../analysis/ecosystem-gap.md)
- Standalone validator that catches this class: [`bin/nlpm-check`](../bin/nlpm-check) (shipped in NLPM v0.8.0)
