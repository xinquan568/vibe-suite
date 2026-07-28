#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake agy returning a quota-class failure (E1.7 / vibe-17): an unreachable-class outcome that
// must hand off to codex rather than stop, once the gate has passed.

import { writeProbe } from "./record.mjs";

writeProbe({ fixture: "quota" });
process.stderr.write("Error: resource exhausted — quota exceeded for this project.\n");
process.exit(0);
