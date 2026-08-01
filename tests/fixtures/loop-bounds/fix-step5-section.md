`--max-rounds` 1–5, **default 3**. A round is: fix the issues still open → verify → keep going while
any remain `NOT FIXED` or `PARTIAL`. `FIXED` issues leave the loop; a `REGRESSED` issue stops the loop
and is reported for a human, because re-running the change that caused it is the wrong move.

The loop also stops when the cap is reached, when nothing remains open, or per step 4's outage rule.
**The harness proving the bound holds is E5.6 (#45)**, which the acceptance assigns there; this
command specifies the cap and does not claim that coverage.
