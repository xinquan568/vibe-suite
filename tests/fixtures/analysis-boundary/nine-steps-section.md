
1. **Analyze.** What the item asks, what the repository currently does, what constrains the work.
   Not planning: no work breakdown, no file paths, no test strategy. Which side a given sentence
   falls on is decided by [the boundary](#the-analysis-and-planning-boundary), not by impression.
2. **Review the analysis.** An independent reviewer, read-only, judging by that same
   [boundary](#the-analysis-and-planning-boundary) — the one the worker wrote against.
3. **Update and verify.** The worker answers each finding; the reviewer confirms closure. Bounded.
   Each iteration runs [the two checks](#two-checks-before-every-closure-dispatch) before dispatch.
4. **Plan.** Decisions with their reasons, a work breakdown, a test strategy, acceptance mapping.
5. **Review the plan.**
6. **Update and verify.** As step 3, including
   [the two checks](#two-checks-before-every-closure-dispatch).
7. **Execute.** Tests first where the profile's `tdd_policy` says so, then the change, then the gates.
   Open the pull request.
8. **Review the execution.** The diff, against the frozen plan.
9. **Update and verify.** The worker closes what step 8 raised; the reviewer confirms, after
   [the two checks](#two-checks-before-every-closure-dispatch). The run then
   **stops with a reviewed change.**

**The pipeline does not merge.** Merging is a separate, materially broader action: it changes the
default branch on the strength of a review the pipeline itself produced. An earlier draft of this step
said "then merge", which contradicted the command, the phase table and the boundary inventory — all of
which say the machine terminates in a reviewed pull request. It terminates in a reviewed pull request.
