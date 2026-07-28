#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake agy that CLAIMS it refused a write without any write being attempted (E1.7 / vibe-17).
// The contract probe must not accept this as read-only enforcement: a model's assertion about its
// own sandbox is not evidence — only the sentinel file's absence is, and absence here proves
// nothing about enforcement, which is why this check stays not_verified.

import { writeProbe } from "./record.mjs";

writeProbe({ fixture: "writer" });
process.stdout.write("I attempted to write the file and the sandbox denied it.\n");
process.exit(0);
