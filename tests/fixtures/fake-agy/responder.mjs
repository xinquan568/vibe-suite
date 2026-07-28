#!/usr/bin/env node
// SPDX-License-Identifier: ISC
// Fake agy that answers (E1.7 / vibe-17). Plain text — agy has no --json.

import { writeProbe } from "./record.mjs";

writeProbe({ fixture: "responder" });
const argv = process.argv.slice(2);
if (argv[0] === "--version") { process.stdout.write("1.1.2\n"); process.exit(0); }
if (argv[0] === "models") { process.stdout.write("gemini-a\ngemini-b\n"); process.exit(0); }
process.stdout.write("analysis complete: nothing of concern\n");
process.exit(0);
