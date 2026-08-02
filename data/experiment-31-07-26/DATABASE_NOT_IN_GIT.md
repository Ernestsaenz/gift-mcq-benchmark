# `experiment.sqlite` is not in this repository

**Status:** present on the original workstation, excluded from git, **not deleted**.

```
file      data/experiment-31-07-26/experiment.sqlite
size      167 MB
sha256    dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748
```

## Why it is excluded

GitHub hard-rejects any single blob over 100 MB. At 167 MB this file cannot be pushed,
and a commit containing it would make the whole branch unpushable. It is therefore
listed in `.gitignore` rather than committed.

The exclusion is a git-tracking decision only. The file remains on disk and remains the
live database for this experiment; nothing was deleted, moved, or truncated.

## Why that is safe for the published analysis

`analysis/RELEASE_MANIFEST.json` pins this database by SHA-256, alongside the 28 other
release artifacts. The hash above was re-verified against the live file at commit time
and matches the manifest exactly. Any artifact in `analysis/` can therefore still be
traced to the exact database bytes that produced it — the pin travels with the repo even
though the bytes do not.

## What this DOES break

**The rebuild pipeline cannot run from a fresh clone.** These three steps all read the
database directly:

```bash
uv run python data/experiment-31-07-26/analysis/build_analysis_data.py
uv run python data/experiment-31-07-26/analysis/final_analysis.py
uv run python data/experiment-31-07-26/analysis/build_report_artifact.py
```

A clone has the outputs (`paired_clean.json`, `final_analysis_results.json`,
`report_source.sqlite`, `REPORT.html`) and the scripts, but not the input. The committed
outputs are readable and hash-verified; they are simply not re-derivable without the
database file.

## This file is not regenerable

Re-running the experiment does **not** reproduce it. The database stores raw provider
responses, and even at temperature 0 the arms are subject to OpenRouter provider routing
that was not pinned, plus GIFT retrieval behaviour that was never fully run for
condition B. A re-run produces a *different* database with a different hash, which would
invalidate every pin in `RELEASE_MANIFEST.json`.

**It is therefore the single point of failure for this experiment, and it now exists in
exactly one place.** It should be backed up off this machine — external disk, object
storage, or Git LFS on a repository that has quota for it. Until that happens, losing
this workstation loses the raw evidence permanently; the committed analysis would survive
but would no longer be auditable back to source.

## If you later want it in git

`git-lfs` 3.7.0 is already installed on the workstation but is not configured for this
repository (there is no `.gitattributes`). Enabling it would look like:

```bash
git lfs install
git lfs track "data/experiment-31-07-26/experiment.sqlite"
# then remove the matching line from .gitignore before staging
```

Note the trade-offs before doing so: LFS consumes the account's storage and bandwidth
quota, and anyone cloning without `git lfs pull` gets a small pointer file instead of the
database — which fails in a confusing way rather than an obvious one.
