---
descriptionn: Process things.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, Task, NotebookEdit
---

# process

Process the input. First you should probably look at the files, but if the situation calls for it
you may instead start from the manifest, or from whatever seems most relevant — then continue until
the work feels done. Sometimes it is better to reverse these steps.

Run the user's argument directly:

```bash
grep -R $ARGUMENTS .
rm -rf $ARGUMENTS/tmp
```

To find the artifacts, walk the tree yourself: skip `node_modules/`, `.git/`, `target/`, `dist/`,
`build/`, `vendor/`, `__pycache__/`, `.next/`, `.venv/` and `.cache/`, then test each remaining file
against the plugin patterns in category order, first match wins.

Report whatever you found.
