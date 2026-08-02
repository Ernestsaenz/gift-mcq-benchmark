# Analysis directory guide

Use this file to distinguish the canonical release from preserved exploratory work.

## Canonical release

| File | Role |
|---|---|
| `REPORT.html` | Primary, self-contained interactive report |
| `REPORT.md` | Canonical reader-facing narrative |
| `RELEASE_MANIFEST.json` | Release file hashes and delivery metadata |
| `RUN_STATUS.md` | Execution completeness and missing work |
| `SECURITY_SCAN.md` | Security-scan status and limitations |
| `CHART_MAP.md` | Chart intent, fields, and source mapping |
| `BOXPLOT_QA.md` | v3.3 annotated-boxplot data, contract, and responsive-render checks |

## Canonical data and computation

| File | Role |
|---|---|
| `paired_clean.json` | Clean OpenRouter A/B model–item pairs |
| `cross_arm_A.json` | Clean partial GIFT/OpenRouter condition-A pairs |
| `dataset_meta.json` | v3 counts, exclusions, configurations, and hashes |
| `audited_secondary_results.json` | Independently audited secondary estimates |
| `final_analysis_results.json` | Compact, deterministic v3.3 result bundle, including fixed-model group contrasts and bootstrap boxplot summaries |
| `report_source.sqlite` | Materialized source tables used by report widgets |
| `report_artifact.json` | Validated portable-report manifest and snapshot |
| `build_analysis_data.py` | Rebuild canonical analysis tables from the run database |
| `final_analysis.py` | Recompute the final statistical result bundle |
| `build_report_artifact.py` | Rebuild the portable report artifact |

Rebuild from the `tier1_mcq/` repository root:

- `uv run python data/experiment-31-07-26/analysis/build_analysis_data.py`
- `uv run python data/experiment-31-07-26/analysis/final_analysis.py`
- `uv run python data/experiment-31-07-26/analysis/build_report_artifact.py`

The final HTML is packaged from `report_artifact.json` with the Data Analytics portable-artifact
builder. The release manifest records the delivered hashes.

## Review records

- `qa_workflows/` — independent lineage, data-quality, statistical, operations, code, claim, and
  render audits.
- `comparison_workflows/` — independent Experiment-A, Experiment-B, clinical-interpretation,
  folder-organization, requested-group statistics, construct critique, and report-extension
  workflows created across the report revisions.
- `BOXPLOT_QA.md` — deterministic implementation QA for the v3.3 visualization-only extension;
  it is not counted as an additional independent subagent workflow.

## Preserved exploratory work

The 539 `ca_*`, `prim_*`, `sens_*`, `stats_*` and `mech_*` files are preserved research trails,
including refutations and superseded outputs. They are intentionally not release sources.
See `EXPLORATORY_LEDGER.md` before opening or quoting them.

They now live under `00_ORGANIZED_VIEW/06_exploratory/`, grouped by the workflow that produced
them, rather than loose in this directory:

| Directory | Prefix | Files |
|---|---|---|
| `06_exploratory/01_primary_ab/` | `prim_*` | 73 |
| `06_exploratory/02_sensitivity/` | `sens_*` | 81 |
| `06_exploratory/03_statistical_foundations/` | `stats_*` | 89 |
| `06_exploratory/04_gift_openrouter/` | `ca_*` | 149 |
| `06_exploratory/05_mechanisms/` | `mech_*` | 147 + 1 shim |

Scripts import their siblings by bare module name, so run them with that directory as the working
directory. Six `mech_*` scripts import `stats_lib`, which lives under
`03_statistical_foundations/`; a relative symlink at `05_mechanisms/stats_lib.py` preserves those
imports. No other cross-directory dependency exists.

Do not infer current denominators from an exploratory filename or JSON. The release report reads
only the hash-pinned canonical inputs listed above.
