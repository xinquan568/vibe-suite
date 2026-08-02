
Steps 3, 6 and 9 run these before the worker's update is dispatched for verification. They are
**procedure, not advice**: each ends with its output **pasted** into the iteration's record under the
heading named here, and a record missing either heading is treated by the reviewer as an unaddressed
finding rather than assumed to have passed.

Both were written down as techniques first and failed anyway — one of them inside the very document
that recorded it. **Documenting a technique does not cause it to run**, which is the whole reason
these are steps with visible output rather than guidance.

**`## Direct read of enumerated lists`** — open every enumerated list in the artifact and read **each
entry**, rather than querying it. The failure mode being looked for is an entry that lists artifacts
instead of stating a rule; it has no subject and no verb, so no sweep selects it. Table cells are read
individually. Paste the entries examined and the verdict on each.

**`## Decision↔consequence sweep`** — for **every claim the iteration changed**, search that claim's
subject across the whole artifact and confirm no other section still carries the superseded reading.
Paste the terms searched and what each turned up. This exists because the same defect recurred across
runs — a risk still describing the withdrawn reading after the decision moved — and once because the
sweep already existed and was skipped. Having a check and not running it is worse than lacking one:
the remedy was available and the defect shipped anyway.
