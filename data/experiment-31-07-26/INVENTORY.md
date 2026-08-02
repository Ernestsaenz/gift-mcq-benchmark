# Experiment 31-07-26 inventory

This is the navigation entry point for the experiment snapshot. The directory is organized
**without moving or deleting existing files** because canonical hashes, reproducibility commands,
exploratory imports, and QA citations depend on their current paths.

## Start here

| Need | File or directory |
|---|---|
| Read the final interactive report | `analysis/REPORT.html` |
| Read the report as Markdown | `analysis/REPORT.md` |
| Understand what ran and what is missing | `analysis/RUN_STATUS.md` |
| Reproduce the canonical data and statistics | `analysis/README.md` |
| Review independent QA | `analysis/qa_workflows/` |
| Review this update's independent workflows | `analysis/comparison_workflows/` |
| Navigate superseded exploratory work | `analysis/EXPLORATORY_LEDGER.md` |

## Directory map

### Source and derived datasets

- `balanced-clinical-questionnaire-500-no-image.xlsx` — source workbook.
- `balanced-flat-A.xlsx` — flattened Experiment-A workbook.
- `balanced-flat-B.xlsx` — flattened Experiment-B workbook.
- `flatten.py` and `flatten_report.json` — flattening code and its audit output.

### Run database

- `experiment.sqlite` — authoritative run database.
- `experiment.sqlite-wal` and `experiment.sqlite-shm` — SQLite sidecars. Keep them beside the
  database; do not move them independently.

### Execution scripts and logs

- `run_lib.sh`, `run_openrouter.sh`, `run_openrouter_b.sh`, `run_gift.sh`, and `retry_a_or.sh` —
  run orchestration.
- `openrouter_run.log`, `openrouter_b.log`, `gift_run.log`, and `retry_a_or.log` — preserved run
  logs.

### Analysis

All release outputs, canonical analysis data, reproducible code, QA records, and preserved
exploratory work are under `analysis/`. Its detailed navigation file is `analysis/README.md`.

## Preservation policy

No existing file was eliminated or relocated during this organization pass. This additive index
is intentional: more than 500 exploratory scripts and outputs use sibling imports or relative
paths, and several reviewed artifacts pin exact file hashes. System-generated `.DS_Store` and
`__pycache__` entries are also left untouched so the instruction to retain all content is literal.
