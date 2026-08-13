# google-gemini/gemini-skills — debrief

Internal retrospective. No public article companion — this engagement produced a piece of feedback worth more than a celebratory write-up. What follows is the full sequence: audit, PRs, the maintainer's response, the four lessons, and the concrete pipeline changes that landed in response.

Audience: xiaolai and anyone else building contribution pipelines.

## The audit

NLPM scored `google-gemini/gemini-skills` on 2026-04-27 at commit `8c95085`. Four SKILL.md files, weighted score **98/100**, security PASS (no executable surfaces). The strongest artifact in the repo (`gemini-live-api-dev/SKILL.md`) scored 100. By the rubric, this is one of the cleanest skill repos we've audited.

## The PRs

Three PRs were filed against the target:

| PR  | Title                                                                   | Outcome                                                | Time to resolution |
| --- | ----------------------------------------------------------------------- | ------------------------------------------------------ | ------------------ |
| #36 | URL Context example: undefined `model_id`, bare `GenerateContentConfig` | **closed unmerged** by `markmcd` ("No longer needed.") | \~24h              |
| #37 | Agent-neutral phrasing for web-fetch fallback                           | **merged**                                             | \~24h              |
| #38 | README link text "thought circulation" → "thought signatures"           | **merged**                                             | \~24h              |

For PR #36 the bug is technically still in the upstream code as of close — the `model_id` variable is undefined in the snippet and `GenerateContentConfig` is not qualified with the `types.` prefix the rest of the file uses. The maintainer's "No longer needed" was a judgment call, not a fix. The right tracking outcome is `closed_unmerged` / `maintainer_rejected`, not `applied_separately`.

PRs #37 and #38 represent real value shipped: a behavior-affecting tooling phrase fix and a doc accuracy fix. Both merged inside a day.

## The umbrella issue, and the response

Alongside the three PRs the contribute workflow filed `google-gemini/gemini-skills#39` titled "NLPM audit findings + 3 PRs (PR #36, #37, #38)". The body was a structured audit report: methodology, score table, verified bugs (with PR links), **deferred bugs flagged for maintainer review** (a 3-row table on Vertex Live API model conventions where our cross-skill comparison surfaced contradictions we couldn't independently verify), cross-component drifts, and a "false positive recorded for rule learning" note. The body ended with a "Tone disclaimer" acknowledging the limits of an automated cross-skill comparison and suggesting maintainers close findings that didn't match intent.

`markmcd` (Google, MEMBER) closed the issue with this comment:

> Thanks for the contributions so far.
>
> Sending an unsolicited report on things that are potential issues, and especially those that require "domain expertise", puts the burden on the maintainers to review and evaluate whether these changes are worthwhile. It'd be great if, in future, **you** could do that first, and if you aren't sure if something is an issue, you can either just leave it (assuming good intent and competence of the authors) or file a specific bug to ask the question.
>
> Sending individual bug reports and PRs is fine and great, we can evaluate those quickly, so thanks for those. But large reports like this that require us to spend time reading and reproducing are burdensome.

This is high-signal feedback. It distinguishes per-PR fixes (welcome) from summary issues with deferred / "domain expertise" findings (burden). It also identifies the load-shifting failure mode: by surfacing items we hadn't validated ourselves as questions for the maintainer to answer, we were asking the maintainer to validate the linter's claims rather than validating them before submission.

The "Tone disclaimer" we appended at the bottom of the issue body — "Treat the PRs as suggestions; close any that don't match your intent" — was an attempt to soften the asymmetry. In retrospect it confirmed it. A disclaimer that the report might contain false positives still asks the reader to evaluate which ones are false.

## The four lessons

Encoded as guidance to the contribute workflow's prompt and to `auditor/README.md`'s rules of engagement:

1. **Only contribute concretely.** Per-PR fixes only. No umbrella / summary issue on the target repo. The PR body's `nlpm-metadata` block already carries provenance.
2. **High confidence, with evidence.** Only findings the scorer reproduced during the audit pass reach the contribute step. The agent re-verifies before opening each PR. No reproduction, no PR.
3. **Assume the authors' good intent and competence.** Findings that turn on style, naming, content priorities, or anything that could be a deliberate authorial choice are dropped silently. Default-conservative confidence; uncertain findings stay in our audit data, never on the target's tracker.
4. **Never leave the maintainer with the burden of reviewing our report.** PR bodies are bug + evidence + fix. No questions, no audit links, no "please consider", no marketing for NLPM beyond the disclosure line. A maintainer should decide yes/no in 30 seconds.

These are not opinions. They are the literal disambiguation of markmcd's three-paragraph comment, restated as policy.

## Pipeline changes

What landed in the NLPM repo in direct response, all gateable mechanically rather than relying on prompt-as-promise:

| Change                        | Where                                                                                                                                       | Mechanism                                                                                                                                                                                                                                                     |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Umbrella issue removed        | `auditor-contribute.yml` step 6 + new backstop step                                                                                         | Prompt forbids it; backstop searches the target for any issue we authored within the run window, closes it with an apology comment, and fails the workflow if found                                                                                           |
| Real CONTRIBUTING.md reading  | `auditor-contribute.yml` step 2                                                                                                             | Fetches CONTRIBUTING.md / `.github/CONTRIBUTING.md` / PR template / CoC; if "discuss in an issue first" appears anywhere, the agent stops and exits without opening PRs                                                                                       |
| Pushback gate                 | new step in `auditor-contribute.yml`                                                                                                        | On entry, scans `auditor/logs/events.jsonl` for `maintainer_rejected` or `pr_comments_snapshot(closed_unmerged)` matching the target repo. Hits → `pushback_gated` status + label, all later steps skip via `if: steps.pushback_gate.outputs.gated != 'true'` |
| First-contact PR cap          | `auditor-contribute.yml` step 5                                                                                                             | Reduced from 5 to 3 if `gh pr list --author $CONTRIBUTE_AUTHOR_EMAIL` returns zero                                                                                                                                                                            |
| Confidence gate               | `auditor/prompts/score-artifacts.md` adds `confidence` and `evidence` fields; `auditor-contribute.yml` filters to `confidence == high` only | Missing `confidence` defaults to `medium` for legacy audits — they cannot accidentally ship                                                                                                                                                                   |
| Reproduction-required PR step | `auditor-contribute.yml` step 5b                                                                                                            | Hard gate: agent must reproduce the bug (run the snippet, curl the link, parse the YAML) before opening the PR. No reproduction, drop the finding silently                                                                                                    |
| Tightened PR body             | `auditor-contribute.yml` step 5h                                                                                                            | Three labelled lines: **Bug**, **Evidence**, **Fix**. No questions, no audit-link, no marketing. Disclosure shortened to "drive-by fix from NLPM, reviewed and reproduced before submission"                                                                  |

Plus two adjacent fixes that surfaced during the work:

- **JSON-validation gate on the registry**: a malformed `auditor/registry/repos.json` (two top-level objects concatenated with a stray comma — produced by some race we couldn't pin down) had to be repaired by hand. New `auditor/scripts/atomic-registry-write.sh` validates with `python3 -m json.tool` before rename and refuses to overwrite the registry with malformed JSON. All 10 registry-write call sites (audit, track, contribute, discover, case-study, merge resolver) now go through it.
- **Bug found while editing**: the "Configure commit author identity" step had two `if:` keys — one I added for the pushback gate, one pre-existing for the `CONTRIBUTE_AUTHOR_*` vars. YAML keeps the last one, so the pushback condition was being silently dropped. Combined into a single multi-line `if:` with both conditions ANDed.

## The reply

Posted to issue #39 (after one false start that read too much like a press release):

> I'm sorry. You're right, and I should have known better.
>
> The choice to file that summary issue was mine. I underestimated how much evaluation work it puts on you, and the "domain expertise" framing was the worst part — I was asking you to validate items I had not validated myself, on a repo I don't own. That is my own ignorance about how unsolicited reports land with upstream maintainers, not something to lay at the feet of the tool. The tool followed the instruction; the instruction was mine.
>
> Going forward I will:
>
> - Read each project's contribution conventions before opening anything, and follow them as written.
> - Open PRs only for bugs I have reproduced end-to-end. When I am uncertain I will leave it alone — assuming, as you said, the good intent and competence of the authors.
> - Not file umbrella / summary issues at all. Per-PR only.
> - Keep "needs domain expertise" findings out of your tracker entirely; if I cannot verify something, it stays in my own notes.
>
> I will also improve NLPM so its defaults push toward smaller, well-scoped contributions rather than relying on me to remember the etiquette each time. The umbrella-issue step has already been removed from the contribute workflow; more will follow.

Two things to note about the reply itself: (1) ownership is in the human voice, not the tool's — "the instruction was mine" matters. (2) the four bullets restate markmcd's comment in promise form without shrinking from any of it, and the closing commits to changing NLPM. By the time the reply went out, items 1 and 2 of those four bullets were already mechanical gates in the pipeline; the rest landed inside 24 hours.

## Blast radius — what's still in flight

| Question                                                                  | Status                                                                                                                                                                                                                                |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Other repos got the same umbrella-issue treatment?                        | **22 still open** out of 31 ever filed. We are leaving them; closing retroactively would generate more noise than it removes. The pattern is now blocked at source for all future audits.                                             |
| `nlpm:patterns` and `nlpm:rules` "loaded by agents" — were they actually? | No. Reclassified as "Reference (loaded on demand)" in CLAUDE.md. The on-demand loading via `nlpm:scoring`'s scope-note cross-references continues to work.                                                                            |
| The pushback gate — is gemini-skills behind it now?                       | Yes. The PR #36 close emitted a `pr_comments_snapshot(closed_unmerged)`. Any future contribute run targeting `google-gemini/gemini-skills` short-circuits at the new gate; status flips to `pushback_gated` and the agent never runs. |
| The confidence gate — does it shrink throughput?                          | By design. If the audit produces zero high-confidence findings, the contribute step doesn't run at all (no LLM cost on a no-op) and the issue is labelled `no-high-confidence-findings`. That is the right outcome, not a failure.    |

## What this engagement was worth

Two PRs merged: real, modest. One PR closed: a maintainer judgment call, not a verified bug we shipped wrong. One issue closed: the most important piece of feedback NLPM has received this cycle, mechanically encoded inside 36 hours.

Net: the umbrella issue was a mistake, the apology and the rewrite are the response. The four lessons are now load-bearing in the contribute pipeline rather than guidance — the next time a maintainer writes feedback this clear, the system answers in code.
