# Non-destructive folder-organization review

**Scope:** `data/experiment-31-07-26/`  
**Review rule:** preserve every byte; do not move a path that is consumed by the canonical rebuild, report, release manifest, or QA record.  
**Snapshot:** 628 files, 218,218,596 bytes (about 208 MiB).

## Recommendation

Use an additive `INVENTORY.md` as the navigation layer and leave the existing experiment paths in
place. This is the only low-risk first pass. The apparent clutter is mostly an immutable historical
analysis ledger: 539 flat `analysis/` files are exploratory scripts or their outputs, and many have
sibling imports, relative-file reads, or exact-path citations in the QA reports. Moving them into
pretty subdirectories would make older analyses and their audit trail non-reproducible.

The root inventory should distinguish four surfaces:

1. **Inputs and construction** — source workbook, `flatten.py`, the two generated workbooks, and
   `flatten_report.json`.
2. **Run record** — `experiment.sqlite` plus its sidecars, runner shell scripts, and the four logs.
3. **Canonical release** — the compact report/rebuild files named below.
4. **Historical exploratory ledger** — the `ca_*`, `mech_*`, `prim_*`, `sens_*`, and `stats_*`
   families. These remain available but are explicitly marked non-canonical unless a QA document
   cites them.

This makes the folder understandable without changing any referenced path or duplicating results.

## Inventory by surface

| surface | files | bytes | disposition |
|---|---:|---:|---|
| Experiment root / run record | 18 | 175,751,679 | Keep paths fixed |
| Canonical analysis/release files | 16 | 2,356,764 | Keep paths fixed |
| Independent QA (`qa_workflows/`) | 12 | 192,498 | Keep paths fixed; some hashes are pinned |
| New comparison reviews (`comparison_workflows/`) | 3 | 31,746 | Keep together in existing directory |
| Flat exploratory ledger | 539 | 39,255,684 | Keep flat and label historical |
| Python bytecode caches | 39 | 602,569 | Optional archive-only move; no analytical value |

The flat exploratory ledger is already consistently prefix-namespaced:

| prefix | topic | files | bytes |
|---|---|---:|---:|
| `ca_*` | GIFT/OpenRouter cross-arm analyses | 149 | 8,346,894 |
| `mech_*` | exploratory mechanism analyses | 147 | 29,042,942 |
| `prim_*` | primary-inference exploratory analyses | 73 | 501,257 |
| `sens_*` | sensitivity analyses | 81 | 769,426 |
| `stats_*` | statistical foundations/checks | 89 | 595,165 |

## Canonical release paths that must not move

The following files are the supported release surface and should be linked prominently from the
inventory:

- `analysis/REPORT.html` — primary reader-facing deliverable.
- `analysis/REPORT.md` — report narrative source.
- `analysis/RUN_STATUS.md` — run-state authority.
- `analysis/RELEASE_MANIFEST.json` and `analysis/SECURITY_SCAN.md` — release record.
- `analysis/build_analysis_data.py`, `analysis/final_analysis.py`, and
  `analysis/build_report_artifact.py` — canonical rebuild chain.
- `analysis/paired_clean.json`, `analysis/cross_arm_A.json`,
  `analysis/gift_coverage.json`, and `analysis/dataset_meta.json` — canonical analytical exports.
- `analysis/audited_secondary_results.json` and `analysis/final_analysis_results.json` — compact,
  approved numerical inputs/results.
- `analysis/report_source.sqlite` and `analysis/report_artifact.json` — portable-report data and
  artifact specification.
- `analysis/qa_workflows/` — independent QA evidence. In particular,
  `audited_secondary_results.json` verifies exact hashes for `QA03_PRIMARY_STATS.md`,
  `QA05_SENSITIVITY.md`, and `QA06_CROSS_ARM.md`; moving or editing those files invalidates the
  canonical analysis.

## Root paths that must not move

- `balanced-clinical-questionnaire-500-no-image.xlsx`, `flatten.py`,
  `balanced-flat-A.xlsx`, `balanced-flat-B.xlsx`, and `flatten_report.json` are joined by exact
  sibling paths inside `flatten.py`.
- `experiment.sqlite` must remain one directory above the canonical analysis scripts. Both rebuild
  scripts resolve it as `analysis/../experiment.sqlite`.
- `experiment.sqlite-shm` and `experiment.sqlite-wal` must remain adjacent to the database until a
  deliberate SQLite snapshot/close procedure is used. The WAL is currently empty, but the
  canonical code explicitly inspects that exact sidecar path.
- `run_lib.sh`, `run_gift.sh`, `run_openrouter.sh`, `run_openrouter_b.sh`, and `retry_a_or.sh`
  source each other with sibling-relative paths.
- `gift_run.log`, `openrouter_run.log`, `openrouter_b.log`, and `retry_a_or.log` are primary
  operational evidence cited by exact basename and SHA-256 in `QA07_OPERATIONS.md`.

## Why the exploratory files should not be moved now

The 539 flat historical files are not used by the three-file canonical rebuild chain, but they are
not independent loose files either:

- scripts import sibling modules such as `stats_lib`, `prim_linalg`, `ca_lib`, `mech_*_lib`, and
  `sens_*_lib` by bare module name;
- scripts read and write sibling JSON/TXT/PKL files by relative path;
- QA documents cite exact historical filenames and use them to explain which v1 results are stale;
- the ledger is evidence of the adversarial workflow, including failed and superseded paths, not
  merely a set of current outputs.

Therefore a bulk move into `analysis/exploratory/{cross_arm,mechanism,primary,sensitivity,stats}`
would require import rewrites, data-path rewrites, documentation updates, hash regeneration, and a
full replay. That is a migration project, not safe folder tidying.

## Safe additive organization to perform now

Create one root file, `data/experiment-31-07-26/INVENTORY.md`, containing:

- a “Start here” link to `analysis/REPORT.html`;
- the canonical rebuild commands from `analysis/RUN_STATUS.md`;
- the four-surface map above;
- a warning that prefixed exploratory outputs may contain superseded v1 counts and are not inputs
  to the final report;
- file counts and a generated SHA-256 inventory (or a link to `analysis/RELEASE_MANIFEST.json`).

Optionally add `analysis/EXPLORATORY_LEDGER.md` with the five prefix families and links to the QA
reports that adjudicated them. This is also additive and leaves every historical path intact.

For **future** work only, direct new non-canonical outputs into:

```text
analysis/exploratory/
  cross_arm/
  mechanism/
  primary/
  sensitivity/
  statistical_foundations/
```

Do not retroactively move the 539-file ledger into these directories.

## Exact optional moves verified as unreferenced analytical content

Only operating-system metadata and Python bytecode are safe to relocate without affecting the
analysis. These are ignored by Git and no analysis/report/QA file refers to their paths:

```text
data/experiment-31-07-26/.DS_Store
  -> data/experiment-31-07-26/archive/system_generated/root.DS_Store

data/experiment-31-07-26/analysis/.DS_Store
  -> data/experiment-31-07-26/archive/system_generated/analysis.DS_Store

data/experiment-31-07-26/__pycache__/
  -> data/experiment-31-07-26/archive/system_generated/python_bytecode/root/

data/experiment-31-07-26/analysis/__pycache__/
  -> data/experiment-31-07-26/archive/system_generated/python_bytecode/analysis/
```

These moves preserve content literally, but Python/Finder may recreate the cache/metadata files in
their original locations. They are optional and low-value; the inventory is the material
organization improvement.

## Proposed target view (without relocating current evidence)

```text
experiment-31-07-26/
├── INVENTORY.md                    # new navigation layer
├── balanced-clinical-questionnaire-500-no-image.xlsx
├── balanced-flat-A.xlsx
├── balanced-flat-B.xlsx
├── flatten.py / flatten_report.json
├── experiment.sqlite[-shm|-wal]
├── run_*.sh / retry_a_or.sh / *.log
├── archive/system_generated/       # optional metadata/bytecode preservation only
└── analysis/
    ├── REPORT.html                 # start here
    ├── REPORT.md / RUN_STATUS.md
    ├── RELEASE_MANIFEST.json / SECURITY_SCAN.md
    ├── build_analysis_data.py / final_analysis.py / build_report_artifact.py
    ├── canonical JSON/SQLite outputs
    ├── qa_workflows/
    ├── comparison_workflows/
    ├── EXPLORATORY_LEDGER.md        # optional additive index
    └── ca_* / mech_* / prim_* / sens_* / stats_*  # historical, paths preserved
```

## Bottom line

Add indices; do not rearrange analytical evidence. The only confidently movable current content is
ignored OS metadata and bytecode, and archiving it offers little benefit. The report, database,
source workbooks, run scripts/logs, canonical exports, QA evidence, and flat exploratory ledger all
have path-level provenance or dependency reasons to remain where they are.
