---
slug: karpathy-autoresearch
repo: karpathy/autoresearch
audited: 2026-05-28
commit_sha: 228791fb499afffb54b46200aca536f79142f117
score: 90
exemplifies:
  - R03
  - R14
  - R15
  - R16
  - R17
  - R33
---

# Exemplar: karpathy/autoresearch — `program.md`

**Score**: ~90/100  |  **Date**: 2026-05-28  |  **Commit**: `228791fb499afffb54b46200aca536f79142f117`

A research codebase by Andrej Karpathy in which a single Markdown file (`program.md`) is the *program* — instructions for an autonomous LLM agent that iterates on a 5-minute training loop overnight. The README states it plainly: "you are programming the `program.md` Markdown files that provide context to the AI agents and set up your autonomous research org." This is nlpm's own thesis ("NL artifacts are programs that can be linted") articulated from outside the Claude Code ecosystem entirely.

The audited artifact is the single 115-line `program.md` at the repo root. There is no `.claude/`, no `plugin.json`, no SKILL.md collection — `program.md` is the entire NL surface, and it stands alone.

## Why this exemplar

`program.md` is a **new artifact type** for nlpm: an *agent workflow program* — imperative instructions that drive an autonomous loop, sitting between a memory file (AGENTS.md-shaped context) and a command (numbered workflow with output format). It doesn't fit nlpm's existing taxonomy cleanly, but it satisfies the spirit of R03 + R14–R17 + R33 with notable craft. Worth studying as both an artifact and an external validation of the NL-programming framing.

## Per-rule evidence

### R03 — Positive framing (every prohibition paired with an alternative)

The strongest pattern in the document. The "What you CAN do / CANNOT do" contract is the most visible instance, but the pattern recurs at every prohibition:

> `program.md:25-31`:
>
> ```
> **What you CAN do:**
> - Modify `train.py` — this is the only file you edit. Everything is fair game...
>
> **What you CANNOT do:**
> - Modify `prepare.py`. It is read-only...
> - Install new packages or add dependencies...
> - Modify the evaluation harness...
> ```

> `program.md:99`:
>
> ```
> Run the experiment: `uv run train.py > run.log 2>&1` (redirect everything — do NOT use tee or let output flood your context)
> ```

> `program.md:112` (the "NEVER STOP" instruction):
>
> ```
> Do NOT pause to ask the human if you should continue... If you run out of
> ideas, think harder — read papers referenced in the code, re-read the
> in-scope files for new angles, try combining previous near-misses, try
> more radical architectural changes.
> ```

What makes these strong: every `NEVER` / `do NOT` is immediately followed by what to do instead (`redirect everything` after the tee prohibition; the four concrete fallbacks after "do NOT pause to ask"). Compare to a weaker pattern: "Do NOT stop without checking" alone — Karpathy's version names the failure mode (running out of ideas) and gives four specific recovery moves.

---

### R14 — Numbered steps in multi-phase workflow

Two numbered blocks, each on a distinct phase:

> `program.md:7-19` (Setup, 6 steps):
>
> ```
> 1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar5`)...
> 2. **Create the branch**: `git checkout -b autoresearch/<tag>` from current master.
> 3. **Read the in-scope files**: ...
> 4. **Verify data exists**: ...
> 5. **Initialize results.tsv**: ...
> 6. **Confirm and go**: ...
> ```

> `program.md:94-104` (the experiment loop, 9 steps prefixed `LOOP FOREVER:`):
>
> ```
> LOOP FOREVER:
>
> 1. Look at the git state: the current branch/commit we're on
> 2. Tune `train.py` with an experimental idea by directly hacking the code.
> 3. git commit
> 4. Run the experiment: `uv run train.py > run.log 2>&1`...
> ...
> 8. If val_bpb improved (lower), you "advance" the branch, keeping the git commit
> 9. If val_bpb is equal or worse, you git reset back to where you started
> ```

What makes these strong: each step is short, imperative, and verifiable — most include a runnable command. The `LOOP FOREVER:` prefix is unusual but cleanly conveys "this whole block is a body to repeat" without inventing pseudocode syntax.

---

### R15 — Empty-input / failure handling

Most workflows skip the "what if nothing came back" case. Karpathy spells it out:

> `program.md:100-101`:
>
> ```
> 5. Read out the results: `grep "^val_bpb:\|^peak_vram_mb:" run.log`
> 6. If the grep output is empty, the run crashed. Run `tail -n 50 run.log`
>    to read the Python stack trace and attempt a fix...
> ```

What makes this strong: empty grep output is the silent failure mode of "scrape a value from a log." Naming it explicitly + giving the recovery command (`tail -n 50 run.log`) means the agent never wonders "is no output good or bad?"

---

### R16 — Output format definition with concrete example

Two dedicated sections specify exactly what to produce:

> `program.md:43-56` (training script output, with literal example):
>
> ```
> ---
> val_bpb:          0.997900
> training_seconds: 300.1
> peak_vram_mb:     45060.2
> ...
> ```

> `program.md:68-88` (TSV log schema + 4-row example covering keep / discard / crash):
>
> ```
> commit	val_bpb	memory_gb	status	description
> a1b2c3d	0.997900	44.0	keep	baseline
> b2c3d4e	0.993200	44.2	keep	increase LR to 0.04
> c3d4e5f	1.005000	44.0	discard	switch to GeLU activation
> d4e5f6g	0.000000	0.0	crash	double model width (OOM)
> ```

What makes these strong: the TSV example shows all three terminal states (keep / discard / crash) plus the crash convention (`0.000000` for val_bpb, `0.0` for memory). The agent doesn't have to guess the schema — every column gets a worked example.

---

### R17 — Error paths

Three distinct failure modes addressed:

- **Crashes** (line 110): "If it's something dumb and easy to fix (e.g. a typo, a missing import), fix it and re-run. If the idea itself is fundamentally broken, just skip it, log 'crash' as the status in the tsv, and move on."
- **Timeouts** (line 108): "If a run exceeds 10 minutes, kill it and treat it as a failure (discard and revert)."
- **Stuck / out of ideas** (line 112): four specific recovery moves (read papers, re-read files, combine near-misses, try radical changes).

What makes these strong: each failure has a *bound* (10 minute timeout, "a few attempts" then give up) and a recovery *action*, not just a description.

---

### R33 — Build/run command

> `program.md:23`:
>
> ```
> You launch it simply as: `uv run train.py`.
> ```

> `program.md:15`:
>
> ```
> If not, tell the human to run `uv run prepare.py`.
> ```

Both runnable, exact, no ambiguity.

---

## Standout patterns not yet in nlpm's rulebook

Three patterns this artifact demonstrates that nlpm's writing-* skills don't currently teach:

### Pattern A — Numeric anchoring of subjective principles

> `program.md:37` (the "Simplicity criterion"):
>
> ```
> A 0.001 val_bpb improvement that adds 20 lines of hacky code? Probably
> not worth it. A 0.001 val_bpb improvement from deleting code? Definitely
> keep. An improvement of ~0 but much simpler code? Keep.
> ```

The principle ("simpler is better") is subjective. The anchors (`0.001 val_bpb`, `20 lines`) make it actionable. Three contrasting examples cover the trade-space corners. Weaker writers state the principle and stop; Karpathy state-and-anchors.

### Pattern B — Autonomy instruction with rationale + concrete fallbacks

> `program.md:112` ("NEVER STOP"):
>
> ```
> Once the experiment loop has begun (after the initial setup), do NOT
> pause to ask the human if you should continue. Do NOT ask "should I keep
> going?" or "is this a good stopping point?". The human might be asleep,
> or gone from a computer and expects you to continue working
> *indefinitely* until you are manually stopped. You are autonomous.
> If you run out of ideas, think harder — read papers referenced in the
> code, re-read the in-scope files for new angles, try combining previous
> near-misses, try more radical architectural changes.
> ```

This is one of the cleanest agent-autonomy instructions in the corpus. The structure: (1) state the rule with example forbidden questions, (2) explain *why* in concrete terms ("human might be asleep"), (3) name the most likely failure mode ("run out of ideas") and give four specific recovery moves. Compare to a typical "be autonomous" instruction that just says "don't stop."

### Pattern C — Worked use-case at the close

> `program.md:114`:
>
> ```
> As an example use case, a user might leave you running while they sleep.
> If each experiment takes you ~5 minutes then you can run approx 12/hour,
> for a total of about 100 over the duration of the average human sleep.
> The user then wakes up to experimental results, all completed by you
> while they slept!
> ```

Closes the doc with a concrete scenario that makes the abstract loop tangible. The agent now has a vivid mental model of the duty cycle. nlpm's writing-prompts skill doesn't currently teach the "close with a vivid use-case" technique; this exemplifies it.

---

## Worth adopting

**Pattern: paired CAN / CANNOT contract.** When constraining agent behavior, present capabilities and prohibitions as a paired list rather than a stream of `do not`s. Each prohibition gains a positive complement; the agent reads both halves of the boundary in one pass. Evidence: `program.md:25-31`. Why a useful rule: prohibitions without alternatives are R03's "Pink Elephant" failure mode; the paired pattern structurally avoids it.

**Pattern: numeric anchoring for subjective principles.** When a principle is subjective ("simpler is better", "small change", "meaningful improvement"), follow it immediately with one or more *numeric* examples that cover the trade-space corners (best case, worst case, neutral case). Evidence: `program.md:37`. Why a useful rule: subjective principles fail R22 enforceability without anchors; the anchored form makes the same principle testable.

**Pattern: autonomy instruction + rationale + fallback ladder.** When telling an agent to act autonomously, name the failure mode it's most likely to hit (running out of ideas, hitting an error, finishing a phase) and give a numbered list of recovery moves *before* it encounters them. Evidence: `program.md:112`. Why a useful rule: bare "be autonomous" instructions produce timid agents that ask for permission; the rationale + fallback ladder produces agents that stay in the loop with bounded recovery.

**Pattern: vivid closing use-case.** End an agent workflow doc with a one-paragraph concrete scenario (named persona, named time of day, calculated quantity) that makes the loop's duty cycle tangible. Evidence: `program.md:114`. Why a useful rule: agents follow workflows more reliably when they have a mental model of what success looks like in the wild, not just the per-step instructions.
