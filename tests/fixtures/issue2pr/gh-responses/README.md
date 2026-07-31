# Spike fixtures — the evidence the protocol refinements rest on

Each file records **the invocation that produces it**, **where its shape is documented**, and **the
observation it should produce**. That header is not decoration: a fixture nobody can reproduce is a
guess with a filename, and the whole point of this set is that it decides protocol questions the
previous plan draft was answering by preference.

A scenario whose shape could not be established is marked `unresolved`, and an unresolved scenario
**blocks** the refinement that depended on it.

**The `since` question is about a request, not a response.** Whether the driver filters at the source
or fetches and filters is decided by whether the recorded invocation accepts a time parameter — so it
is answered by the `invocation` line, not by the payload.
