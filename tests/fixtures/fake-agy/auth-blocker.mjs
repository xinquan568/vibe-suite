#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake agy reproducing the REAL unauthenticated behaviour observed on 1.1.2 (E1.7 / vibe-17): it
// prints an OAuth URL, ignores SIGTERM, and never exits — stdin at /dev/null does not save you.
// Only an external group kill bounds it, which is exactly the property under test.

import { writeProbe } from "./record.mjs";

writeProbe({ fixture: "auth-blocker" });
process.on("SIGTERM", () => { /* deliberately ignored, as observed */ });
process.stdout.write("Authentication required. Please visit the URL to log in:\n");
process.stdout.write("  https://accounts.google.com/o/oauth2/auth?client_id=REDACTED\n");
process.stdout.write("Waiting for authentication (timeout 60s)...\n");
setInterval(() => {}, 1000);
