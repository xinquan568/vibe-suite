#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake agy that fails with the unauthenticated signature and EXITS 0 (E1.7 / vibe-17) — the
// observed behaviour of `agy models` when signed out. The exit code is not a success signal.

import { writeProbe } from "./record.mjs";

writeProbe({ fixture: "auth-error" });
process.stderr.write("Error: Please sign in to view available models.\n");
process.exit(0);
