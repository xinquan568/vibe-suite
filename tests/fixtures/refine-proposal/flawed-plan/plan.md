# Plan — migrate the ingest pipeline to the new queue

## Goal

Move ingest off the legacy queue and onto the new one, with no loss of throughput.

## Approach

We will run both queues in parallel for a period, then cut over. The parallel period lets us compare
outputs and build confidence before anything irreversible happens.

Writes go to both queues. Reads come from the legacy queue until cutover, then from the new one.

## Rollout

1. Deploy the dual-write path behind a flag.
2. Enable the flag in staging and let it soak.
3. Enable in production and let it soak.
4. Compare outputs across the soak window.
5. Flip reads to the new queue.
6. Remove the legacy queue and the dual-write path.

## Rollback

If the new queue misbehaves after cutover, flip reads back to the legacy queue.

## Success criteria

Throughput stays within normal bounds and error rates do not increase.
