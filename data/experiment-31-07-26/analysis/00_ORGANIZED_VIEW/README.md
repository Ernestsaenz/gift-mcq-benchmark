# Organized analysis view

This numbered directory is the clean entry point for the experiment analysis. Start with the
[interactive final report](01_release/REPORT.html).

## Directory map

| Directory | Contents | Status |
|---|---|---|
| `01_release/` | Final HTML and Markdown reports, run status, release manifest, security note, and chart map | Canonical release |
| `02_canonical_data/` | Clean paired datasets, metadata, audited secondary estimates, final results, and report database | Canonical analytical inputs and outputs |
| `03_rebuild_pipeline/` | The three supported rebuild steps and portable report artifact | Canonical reproducibility path |
| `04_quality_assurance/` | Fifteen independent QA workflows and the model-comparison review workflows | Review evidence |
| `05_guides/` | Analysis guide and exploratory-work ledger | Documentation |
| `06_exploratory/01_primary_ab/` | Earlier primary A/B inference work (`prim_*`) | Preserved research trail |
| `06_exploratory/02_sensitivity/` | Exclusion, influence, and specification analyses (`sens_*`) | Preserved research trail |
| `06_exploratory/03_statistical_foundations/` | Distribution, interval, power, and test-selection work (`stats_*`) | Preserved research trail |
| `06_exploratory/04_gift_openrouter/` | Partial GIFT/OpenRouter comparisons (`ca_*`) | Preserved research trail |
| `06_exploratory/05_mechanisms/` | Mechanism, effort, negation, and error-destination work (`mech_*`) | Preserved research trail |
| `99_preserved_system/` | Existing Finder metadata and Python bytecode cache | Preserved system content |

## Preservation design

**Updated 2026-08-02.** `06_exploratory/` no longer symlinks — it now **holds the 539 exploratory
files directly**, so the analysis root went from 563 entries to 24. Nothing was copied, renamed or
deleted; the files were moved into the directories that previously pointed at them, and the
grouping is unchanged.

The canonical directories (`01_release/`, `02_canonical_data/`, `03_rebuild_pipeline/`,
`04_quality_assurance/`, `05_guides/`, `99_preserved_system/`) are still symlinks, deliberately:
`RELEASE_MANIFEST.json` pins the release artifacts at their original paths, and moving them would
invalidate it. All 29 manifest hashes verify after the reorganisation.

One dependency needed preserving: six `mech_*` scripts import `stats_lib`, which sits in
`06_exploratory/03_statistical_foundations/`. A relative symlink at
`06_exploratory/05_mechanisms/stats_lib.py` keeps those imports working. Scripts resolve siblings
by bare module name, so run them from their own directory.

The remaining entries in this view are **relative symbolic links** to the original analysis paths. This gives
the directory a usable hierarchy without moving, copying, renaming, or deleting evidence.

That distinction matters because the canonical rebuild uses exact relative paths, the exploratory
scripts use sibling imports and sibling data files, and the release and QA records pin paths and
SHA-256 hashes. Run scripts from the original `analysis/` directory; use this view for navigation.

Coverage at creation:

- 559 original top-level files represented;
- 539 exploratory files separated into five topic families;
- all three original subdirectories represented (`qa_workflows`, `comparison_workflows`, and
  `__pycache__`);
- zero original files moved or removed;
- zero broken links after validation.

For the authoritative distinction between current and superseded results, read
[the analysis guide](05_guides/ANALYSIS_GUIDE.md) and
[the exploratory ledger](05_guides/EXPLORATORY_LEDGER.md).
