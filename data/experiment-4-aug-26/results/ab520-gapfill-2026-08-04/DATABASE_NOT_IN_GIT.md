# The ab520 gapfill databases are not in this repository

**Status:** present on the original workstation, excluded from git, **not deleted**.

```
file      runs/ab520-gapfill-2026-08-04.sqlite
size      56 MB
sha256    c3dee485f8de1a6f28f2e38c7416ba412f0ebf30bc751c250af79b006a180888

file      manifests/ab520-gapfill-2026-08-04.pre-retry.sqlite
size      55 MB
sha256    c2ea94788b6a743c67584f5afbecaf5321c8109afa89b3cd4a1a4c0a3f5a57bb
```

Both hashes were recomputed from the live files at commit time. The first matches the
value recorded in `STATUS.md`; the second matches its committed sidecar
`manifests/ab520-gapfill-2026-08-04.pre-retry.sqlite.sha256` exactly.

## Why they are excluded

Together they are 111 MB. Neither exceeds GitHub's 100 MB per-blob hard limit on its own,
so unlike `data/experiment-31-07-26/experiment.sqlite` this is a size *policy* decision
rather than a hard rejection: committing them would add 111 MB permanently to a public
repository for two files that are inputs to already-committed outputs.

The exclusion is a git-tracking decision only. Both files remain on disk and remain the
live databases for this experiment; nothing was deleted, moved, or truncated.

## What this DOES break

**A clone gets a checksum for a file it does not have.**
`manifests/ab520-gapfill-2026-08-04.pre-retry.sqlite.sha256` is committed while the file
it pins is not. That sidecar is now verifiable only on the original workstation. This
note exists so the gap is explicit rather than discovered.

**The documented rebuild cannot run from a fresh clone.**
`tools/build_final_exports.py` reads `runs/ab520-gapfill-2026-08-04.sqlite`, and also
reads `data/experiment-31-07-26/experiment.sqlite`, which is excluded for the separate
reason documented in that folder. A clone therefore has the exports, the manifests and
the scripts, but not either input.

What a clone *does* have is the full fail-closed cell ledger
(`exports/benchmark-6000-cell-results.csv`, 6,000 rows) and every summary derived from
it. Those are readable and internally consistent without the database.

## These files are not regenerable

Re-running the gapfill does not reproduce them. They store raw provider responses, and
even at `temperature=0` the OpenRouter arm is subject to provider routing that was not
pinned and the GIFT arm to backend behaviour that varied across the run — the retry
timeline in `STATUS.md` records HTTP 500s that were reproducible at the time and may not
be later. A re-run produces a *different* database with a different hash.

**They now exist in exactly one place** and should be backed up off this machine —
external disk, object storage, or Git LFS on a repository with quota. Until then, losing
this workstation loses the raw evidence for the gapfill round permanently; the committed
exports survive but stop being auditable back to source.

## Superseded scope — read before relying on this round

These databases back the **5,930 / 70** gapfill result. That result was subsequently
superseded: 22 of the 500 questions were withdrawn and replaced, and the current result
is 6,000 / 6,000 over an adjusted 500. See
`../../replacements/ab520-replacement-22-2026-08-04/`.

The 22 withdrawn questions are exactly the 22 that carried the 70 unresolved cells, so
the adjusted total was reached by changing benchmark membership, not by recovering the
missing answers. Anything derived from the databases described here belongs to the
pre-replacement population.

## If you later want them in git

`git-lfs` is installed on the workstation but is not configured for this repository
(there is no `.gitattributes`):

```bash
git lfs install
git lfs track "data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04/runs/*.sqlite"
git lfs track "data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04/manifests/*.sqlite"
# then remove the matching lines from .gitignore before staging
```

LFS consumes the account's storage and bandwidth quota, and anyone cloning without
`git lfs pull` gets a small pointer file instead of a database — which fails in a
confusing way rather than an obvious one.
