# Experiment C -- 2-Fake / 50-50 Rebalanced Baseline -- Assignment Report

Protocol: `expc-2fake-5050-baseline-v1`

Built by `build_baseline.py` from the locked mechanical-130 workbooks and
`balanced-flat-A.xlsx` (ultimate ground truth). No input files were modified.

## Overall: exact 50/50 achieved for both arms: **True**

## Arm BM

- Kept fake A: `fibroquelina-X3`
- Kept fake B: `colangiomirina-8`

### PRIMARY (100 rows)

| entity | count |
|---|---|
| colangiomirina-8 | 50 |
| fibroquelina-X3 | 50 |

- exact_5050_achieved: **True**

### RESERVE (30 rows)

| entity | count |
|---|---|
| colangiomirina-8 | 15 |
| fibroquelina-X3 | 15 |

### Churn

- rows reassigned (fabricated_entity changed): **48**
- rows moved PRIMARY<->RESERVE: **0**

### Camouflage-forced rows

- forced to A only (root of B is present in control text): **1** -- ['b240']
- forced to B only (root of A is present in control text): **1** -- ['b424']

### Assignment diagnostics

PRIMARY:

```json
{
  "forcedA": 1,
  "forcedB": 1,
  "keepA": 44,
  "keepB": 20,
  "fresh": 34,
  "flipped_a_to_b": 0,
  "flipped_b_to_a": 0,
  "fresh_a_need": 5,
  "fresh_b_need": 29
}
```

RESERVE:

```json
{
  "forcedA": 0,
  "forcedB": 0,
  "keepA": 9,
  "keepB": 7,
  "fresh": 14,
  "fresh_a_need": 6,
  "fresh_b_need": 8
}
```

## Arm AN

- Kept fake A: `saco orfalónico`
- Kept fake B: `órgano liradónico`

### PRIMARY (100 rows)

| entity | count |
|---|---|
| saco orfalónico | 50 |
| órgano liradónico | 50 |

- exact_5050_achieved: **True**

### RESERVE (30 rows)

| entity | count |
|---|---|
| saco orfalónico | 14 |
| órgano liradónico | 16 |

### Churn

- rows reassigned (fabricated_entity changed): **14**
- rows moved PRIMARY<->RESERVE: **0**

### Camouflage-forced rows

- forced to A only (root of B is present in control text): **0** -- []
- forced to B only (root of A is present in control text): **0** -- []

### Assignment diagnostics

PRIMARY:

```json
{
  "forcedA": 0,
  "forcedB": 0,
  "keepA": 64,
  "keepB": 36,
  "fresh": 0,
  "flipped_a_to_b": 14,
  "flipped_b_to_a": 0,
  "fresh_a_need": 0,
  "fresh_b_need": 0
}
```

RESERVE:

```json
{
  "forcedA": 0,
  "forcedB": 0,
  "keepA": 14,
  "keepB": 16,
  "fresh": 0,
  "fresh_a_need": 0,
  "fresh_b_need": 0
}
```

## Methodology

- **Churn minimization**: the current PRIMARY/RESERVE partition is kept untouched unless a forced-single-legal-fake side would exceed 50 rows within the current PRIMARY set (not the case for either arm here -- 0 rows moved). Within PRIMARY, a row keeps its current fake whenever that fake is one of the two kept fakes and is still camouflage-legal for it; only rows using a dropped fake, or the minimum number needed to correct an over-50 side, change.
- **Deterministic tie-breaks**: (currently-PRIMARY first, then pool_rank ascending, then base_question_id) throughout.
- **Spread**: whenever a row's fake assignment is genuinely free (no current-fake preference, or forced by an overflow flip), the choice is made by a deterministic greedy that prefers the cluster/region with the fewest rows already carrying that fake, so each fake's 50 are not clumped in a handful of clusters.

