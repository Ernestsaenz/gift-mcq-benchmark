# Consolidated triplicate replication — AB520, run-1-incorrect cells

**Status: 1,788 / 1,796 scored (99.6%).** Before trusting any number pooled across
`openrouter_B` / `google/gemini-3.6-flash`, read **[DEVIATIONS.md](DEVIATIONS.md)** —
91 of those 93 scored cells were collected off-protocol and are not directly
comparable to the rest of the study.

## What this is

This folder consolidates a replication study run on top of the adjusted 500-question
AB520 MCQ benchmark (3 arms x 4 models = 6,000 cells, all answered once in run 1).
The 898 cells that were strictly incorrect in run 1 were each given two further
independent runs (run indices 2 and 3), for 1,796 new logical calls. This folder
gathers those results into one place: cleaned exports, a unified ledger, provenance
records, and analysis, plus the documentation you're reading now.

## What question it answers

**Of the answers a model got wrong on its first try, how often does it get the
same question right (or wrong the same way) on a second and third independent
attempt?** This is a study of run-to-run consistency conditioned on initial
failure — see [METHODS.md](METHODS.md) for why that conditioning matters and what
it does and doesn't let you conclude.

## Folder map

| Path | Owner | Contents |
| --- | --- | --- |
| `README.md` | docs | This file — entry point and folder map |
| `METHODS.md` | docs | Full method: benchmark, arms/models, design rationale, protocol parameters |
| `DEVIATIONS.md` | docs | The honest record of everything that departed from protocol |
| `SPEC.md` | coordinator | Shared ground-truth figures every agent in this folder was required to use |
| `exports/` | data-export | Cleaned/derived result exports |
| `ledger/` | ledger | Unified cell-level ledger for the 1,796 logical calls. See `ledger/LEDGER_README.md` for the `redacted_command` record-keeping defect (34 historical invocation records don't reproduce their actual arguments; also noted in DEVIATIONS.md) |
| `provenance/` | provenance | Source hashes, query records, and audit trail |
| `analysis/` | analysis | Computed flip-rate / consistency analysis |
| `checksums.sha256` | coordinator | Generated last, after all other outputs exist |

Each subdirectory owner is responsible for its own contents; this document does not
restate their figures beyond what's already fixed in `SPEC.md`. Where you need a
number owned by another subdirectory, go to the file itself rather than trusting a
paraphrase here.

## Headline status

| Arm | Scored | Total |
| --- | --- | --- |
| openrouter_A | 406 | 406 |
| openrouter_B | 1057 | 1064 |
| tailscale_A | 325 | 326 |
| **Total** | **1788** | **1796** |

The 8 unscored cells are all exhausted at the five-attempt technical-retry ceiling
(not missing data in the ordinary sense — see METHODS.md and DEVIATIONS.md for the
full list and cause). 11 of the 12 arm x model slices are clean and ran entirely at
the frozen `temperature=0` protocol. One slice — `openrouter_B` / gemini — is not:
see DEVIATIONS.md before using it.

## Start here (reading order)

1. **This file** — orientation.
2. **[DEVIATIONS.md](DEVIATIONS.md)** — read this before touching any number
   involving `openrouter_B` / gemini. It is the single most important file in this
   folder.
3. **[METHODS.md](METHODS.md)** — the full method, if you need to judge what the
   numbers mean or reproduce the design.
4. `provenance/` — if you need to verify a figure against its source rather than
   take this documentation's word for it.
5. `ledger/` and `exports/` — the cell-level and derived data.
6. `analysis/` — the computed results.

## Primary sources this folder is built from

- Run 1 (6,000 cells): `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv`
- Runs 2-3 (this replication): `data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/`
  - Database: `runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite`
  - Frozen target ledger: `manifests/frozen-replicate-cell-ledger.csv`
  - Narrative execution record: `STATUS.md`

These are read-only inputs to this consolidation and are never modified here.
