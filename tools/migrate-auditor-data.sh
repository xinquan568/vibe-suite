#!/usr/bin/env bash
# SPDX-License-Identifier: ISC
# §7A row 9 — publish accumulated auditor data to a branch of another repository (E0.8 / vibe-10).
#
# Usage: migrate-auditor-data.sh <dest-repo> [--branch auditor-data] [--source DIR]
#   exit 0  published, or already complete
#   exit 3  a decision is required (destination conflict, or unproven ownership of the tool prefix)
#   exit 1  error
#
# Why this goes through a clone rather than copying into the destination:
# `cp -r` into a bare repository SUCCEEDS. It leaves files on disk that are in no tree and no
# commit, so a tool that copies and then checks its own output directory passes its own
# verification over a branch that gained nothing. Everything here is staged in a clone and every
# check reads `git ls-tree` on the destination — the branch, never the filesystem.

set -euo pipefail

readonly TOOL_PREFIX=".vibe-suite-migration"
readonly TOOL_NAME="vibe-suite/migrate-auditor-data"

log()    { printf '%s\n' "$*" >&2; }
die()    { printf 'error: %s\n' "$*" >&2; exit 1; }
redact() { printf '%s' "$1" | sed -E 's#(://)[^/@[:space:]]+@#\1***@#g'; }

dest="" branch="auditor-data" source_dir="."
while [ $# -gt 0 ]; do
    case "$1" in
        --branch) branch="${2:?--branch needs a name}"; shift 2 ;;
        --source) source_dir="${2:?--source needs a directory}"; shift 2 ;;
        -h|--help) sed -n '3,16p' "$0"; exit 0 ;;
        -*) die "unknown option: $1" ;;
        *)  [ -z "$dest" ] || die "only one destination may be given"; dest="$1"; shift ;;
    esac
done
[ -n "$dest" ] || die "usage: migrate-auditor-data.sh <dest-repo> [--branch NAME] [--source DIR]"
[ -d "$source_dir" ] || die "not a directory: $source_dir"

# Every message about the destination goes through redact(): a clone URL can embed a token, and a
# leak into stdout is a leak into CI logs.
safe_dest="$(redact "$dest")"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

log "cloning $safe_dest (branch $branch)"
clone="$work/clone"
if git clone --quiet --branch "$branch" "$dest" "$clone" 2>/dev/null; then
    :
else
    # A missing branch is normal on a first run: create it as an orphan so the destination's
    # default branch never carries ops data.
    git clone --quiet "$dest" "$clone" 2>/dev/null || die "cannot clone $safe_dest"
    git -C "$clone" checkout --quiet --orphan "$branch"
    git -C "$clone" rm -rq --cached . 2>/dev/null || true
    find "$clone" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
    log "branch $branch did not exist — created as an orphan branch"
fi

python3 - "$source_dir" "$clone" "$branch" "$TOOL_PREFIX" "$TOOL_NAME" "$safe_dest" <<'PY'
import hashlib, json, os, subprocess, sys
from pathlib import Path

source, clone, branch, prefix, tool, safe_dest = (Path(sys.argv[1]), Path(sys.argv[2]),
                                                  sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])

# --- the corpus -------------------------------------------------------------------------------
# §7A names five categories. Four are subtrees; "ledgers" is the merge proposal's word for the four
# files `auditor/SCHEMAS.md` marks append-only, which sit at differing depths and so are flattened
# by name. `registry/repos.json` ("mutated in place") and `feedback/log.json` ("rebuilt") are state
# rather than record and are deliberately out of scope, as are `scripts/`, `prompts/` and — this one
# matters — `disclosures-pending/`, which holds unpublished security disclosures. The destination is
# a public branch; those must never be copied.
SUBTREES = {
    "reports": "auditor/reports",
    "exemplars": "auditor/exemplars",
    "audits": "auditor/audits",
    "articles": "case-studies",
}
LEDGERS = {
    "ledgers/findings.jsonl": "auditor/findings.jsonl",
    "ledgers/disagreements.jsonl": "auditor/disagreements.jsonl",
    "ledgers/vocab-advisories.jsonl": "auditor/vocab-advisories.jsonl",
    "ledgers/events.jsonl": "auditor/logs/events.jsonl",
}

corpus = {}                                    # destination path -> source path
for dest_root, src_root in SUBTREES.items():
    base = source / src_root
    if not base.is_dir():
        continue
    for path in sorted(base.rglob("*")):
        if path.is_file() and not path.is_symlink():
            corpus[f"{dest_root}/{path.relative_to(base).as_posix()}"] = path
for dest_path, src_path in LEDGERS.items():
    candidate = source / src_path
    if candidate.is_file():
        corpus[dest_path] = candidate

if not corpus:
    sys.stderr.write("error: no auditor data found under the source directory\n")
    raise SystemExit(1)
sys.stderr.write(f"corpus: {len(corpus)} file(s) across "
                 f"{len({p.split('/')[0] for p in corpus})} categories\n")

def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()

def git(*args, check=True):
    return subprocess.run(["git", "-C", str(clone), *args], capture_output=True, text=True,
                          check=check)

# --- ownership of the tool prefix must be proved, not assumed -----------------------------------
# A declared prefix is only a declaration, and a filename is not a provenance claim. The tool
# rewrites what is under this prefix, so it first checks a record it wrote itself.
prov_path = clone / prefix / "provenance.json"
prefix_dir = clone / prefix
if prefix_dir.exists():
    owned = False
    if prov_path.is_file():
        try:
            owned = json.loads(prov_path.read_text(encoding="utf-8")).get("tool") == tool
        except (UnicodeDecodeError, json.JSONDecodeError):
            owned = False               # unparseable is unproven, and unproven means hands off
    if not owned:
        sys.stderr.write(
            f"decision required: {prefix}/ exists on {branch} but no valid provenance.json names\n"
            f"this tool, so its contents cannot be shown to be ours. Nothing was changed. Move or\n"
            f"remove {prefix}/ if it is not from a previous run of this tool.\n")
        raise SystemExit(3)

# --- D-F: refuse to overwrite differing destination content -------------------------------------
conflicts, to_write = [], []
for dest_path, src_path in sorted(corpus.items()):
    existing = clone / dest_path
    if not existing.exists():
        to_write.append((dest_path, src_path))
    elif sha256_of(existing) != sha256_of(src_path):
        conflicts.append(dest_path)
if conflicts:
    sys.stderr.write(f"decision required: {len(conflicts)} destination file(s) differ from the "
                     "source. Nothing was staged.\n")
    for path in conflicts[:20]:
        sys.stderr.write(f"  {path}\n")
    if len(conflicts) > 20:
        sys.stderr.write(f"  ... and {len(conflicts) - 20} more\n")
    raise SystemExit(3)

# --- the manifest: real SHA-256 of contents, sorted, excluding itself ---------------------------
manifest_body = "".join(f"{sha256_of(src)}  {dest}\n" for dest, src in sorted(corpus.items()))
manifest_path = clone / prefix / "manifest.sha256"
manifest_current = manifest_path.read_text(encoding="utf-8") if manifest_path.is_file() else None

if not to_write and manifest_current == manifest_body:
    # Idempotence is a property of the WHOLE corpus, not of individual files: no commit only when
    # every path is present and identical and the manifest already matches.
    sys.stderr.write("already complete — no commit\n")
    print(git("rev-parse", "HEAD").stdout.strip())
    raise SystemExit(0)

for dest_path, src_path in to_write:
    target = clone / dest_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(src_path.read_bytes())

manifest_path.parent.mkdir(parents=True, exist_ok=True)
manifest_path.write_text(manifest_body, encoding="utf-8")
prov_path.write_text(json.dumps({
    "tool": tool, "schema": 1, "branch": branch,
    "files": len(corpus),
    "categories": sorted({p.split("/")[0] for p in corpus}),
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

git("add", "--", *sorted(corpus), f"{prefix}/manifest.sha256", f"{prefix}/provenance.json")
if not git("diff", "--cached", "--quiet", check=False).returncode:
    sys.stderr.write("nothing staged — no commit\n")
    print(git("rev-parse", "HEAD").stdout.strip())
    raise SystemExit(0)

git("-c", "user.name=vibe-suite migration",
    "-c", "user.email=migration@vibe-suite.invalid",
    "commit", "--quiet", "-m",
    f"data: publish auditor corpus ({len(corpus)} files)\n\nGenerated by {tool}.")
git("push", "--quiet", "origin", f"HEAD:{branch}")
sys.stderr.write(f"published {len(to_write)} new file(s) to {branch} on {safe_dest}\n")
print(git("rev-parse", "HEAD").stdout.strip())
PY
status=$?
[ "$status" -eq 0 ] || exit "$status"

# --- verification reads the BRANCH, never the working tree --------------------------------------
log "verifying against $branch on $safe_dest"
git -C "$clone" fetch --quiet origin "$branch"
tree_count="$(git -C "$clone" ls-tree -r --name-only "origin/$branch" | grep -vc "^$TOOL_PREFIX/" || true)"
log "branch carries $tree_count corpus file(s) plus the $TOOL_PREFIX/ namespace"
[ "$tree_count" -gt 0 ] || die "the branch tree is empty — nothing was published"
exit 0
