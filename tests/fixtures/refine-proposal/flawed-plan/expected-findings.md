# Expected findings — AC-3 flawed-plan fixture

Three flaws are seeded in `plan.md`. This file records what a competent review should raise, so the
fixture asserts something rather than merely existing.

**This is a specification, not a CI assertion about a reviewer.** CI checks that this file is
well-formed and that each category below is a dimension the rubric can express. Whether a review
actually raises them is the operator check that discharges the AC-3 acceptance clause.

| id | category | severity | line | what is wrong |
|---|---|---|---|---|
| F1 | measurability | major | 30 | "Throughput stays within normal bounds and error rates do not increase" names no measurable criterion — no baseline, no window, no threshold. Nothing here can be evaluated after the fact, so the plan cannot be said to have succeeded or failed. |
| F2 | risk coverage | major | 26 | The rollback flips reads back to the legacy queue, but step 6 removes it. After step 6 the stated rollback does not exist, and the plan never says the rollback expires or what replaces it. |
| F3 | sequencing | minor | 20 | Step 4 compares outputs "across the soak window", after step 3 has already enabled the flag in production. The comparison that would justify the production soak happens after it. |

## Why these three

Each is a different failure class, so a review that finds only one kind still misses two. F1 is an
absent criterion, F2 is an internal contradiction between two sections, and F3 is an ordering error
within one list — a reviewer reading top-to-bottom without holding the whole plan will pass over F2 and
F3 while catching F1.
