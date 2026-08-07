# Code and database provenance for the adjusted A–B experiment

This note identifies the exact local code state and databases behind the completed adjusted August A–B benchmark. The final adjusted result contains **500 questions × 4 models × 3 authorized arms = 6,000 scored cells**.

## Short answer

The repository is:

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq
```

The core execution harness is:

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/code/medrag_eval/
```

The SQLite database that received the final 264 replacement calls is:

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/runs/ab520-replacement22-2026-08-05.sqlite
```

The immutable post-execution database snapshot to use for audit is:

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/manifests/ab520-replacement22.post-execution.sqlite
```

The authoritative final 6,000-cell adjusted result is:

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv
```

There is intentionally **no single SQLite database containing all 6,000 adjusted cells**. The final export is a traceable merge of 5,736 retained scores from the canonical experiment and 264 newly executed replacement scores.

## Exact code state

### Core harness

- Repository HEAD during final replacement execution: `c7f96131485671a406485d4d73987c0b0481fca5`.
- Commit subject: `Add ExpC mechanical-130 addendum and the aug-26 ab520 500-item experiment`.
- Harness path: `code/medrag_eval/`.
- The harness directory was clean against that commit; there were no tracked modifications under `code/medrag_eval/`.
- Prompt version: `mcq_es_v4`.
- Temperature: `0`.
- Runs per cell: `1`, with isolated exact-input retries only after a rejected response.
- GIFT/TailScale stored prompt ID: `13`.
- `--force` was not used and reasoning was not disabled.

The exact SHA-256 for every harness Python file is recorded in:

```text
data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/manifests/code-provenance.sha256
```

### Replacement orchestration code

The replacement workflow also used package-local orchestration scripts. These were workspace files rather than files contained in commit `c7f9613`, so the commit alone is not the complete executable state. Their exact paths and hashes are:

| Role | Repository-relative path | SHA-256 |
|---|---|---|
| Prepare frozen execution inputs | `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/prepare_execution.py` | `855ff3264546fdf54b6263c8f63222582444df941c4bf28f8a847b508b2381d2` |
| Issue and record replacement calls | `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/execute_replacement_cells.py` | `4dfccd3e8939a63a0986bcc9af4e9384aa823d9d59d7a12aa2cc05ea47c63d7f` |
| Reconcile and build adjusted outputs | `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/finalize_execution.py` | `b316318eb42beba127e167fb975a3e83c8b9288c678175f0d52b15595359320c` |

The authoritative machine-readable record of the combined commit, code hashes, inputs, database, and outputs is:

```text
data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/manifests/execution-manifest-final.json
```

### Earlier canonical A–B code state

The pre-replacement canonical August result documents its original harness at commit:

```text
9660b9a503cf68c45b9a808f38ba597b41769c16
```

That earlier state produced the canonical 5,930-scored/70-unresolved result from which the 22 rejected questions were removed. The final replacement calls were executed under the later `c7f9613` repository state plus the exact package-local scripts listed above.

### GIFT production backend

The GIFT/TailScale calls also depended on the separately deployed production backend:

- Repository recorded by deployment evidence: `carneiran/handmade-gift`.
- Required and deployed backend commit: `29af9a4f1581f6ffc1921a44d96a2a2cbe36a84e`.
- Deployment workflow run: `30629235833`, successful.
- Fresh production health and authenticated provider checks passed before GIFT traffic.

Evidence is stored in:

```text
data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/manifests/production-evidence-2026-08-05.json
```

## Database lineage

### 1. Earlier reused-score database

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-31-07-26/experiment.sqlite
```

SHA-256: `dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748`.

This database supplied the previously completed cells reused by the canonical August result.

### 2. Canonical August gapfill database

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04/runs/ab520-gapfill-2026-08-04.sqlite
```

SHA-256: `c3dee485f8de1a6f28f2e38c7416ba412f0ebf30bc751c250af79b006a180888`.

This database contains the August gapfill calls. Together with the reused-score database, it produced the canonical 6,000-cell ledger with 5,930 scores and 70 unresolved cells. The adjusted workflow removed all 264 cells belonging to the 22 rejected questions, leaving 5,736 retained scored cells.

### 3. Replacement execution database

Live path:

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/runs/ab520-replacement22-2026-08-05.sqlite
```

SHA-256 at finalization: `cd53aacc5ed4cb524998dbd40fc409f6d1b4d7aaefa4144921830b1cbd6254fc`.

Contents:

| Experiment ID | Arm | Condition | Provider | Logical cells |
|---|---|---|---|---:|
| `ab520_replacement22_or_A_20260804` | OpenRouter A | A | `openrouter` | 88 |
| `ab520_replacement22_or_B_20260804` | OpenRouter B | B | `openrouter` | 88 |
| `ab520_replacement22_ts_A_20260804` | GIFT/TailScale A | A | `tailscale_medical_rag` | 88 |

Database totals:

- 264 logical calls.
- 266 provider attempts.
- 264 accepted scores.
- Two rejected first attempts, both recovered by isolated exact-input retries.
- SQLite `PRAGMA integrity_check`: `ok`.

### 4. Immutable post-execution snapshot

```text
/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/manifests/ab520-replacement22.post-execution.sqlite
```

SHA-256: `c0112fd5f32d5e7291bfd3f8b352aa411f75866f89eb86adedc25134e0f3113e`.

Use this snapshot for audit or archival inspection. Its companion checksum file is `manifests/ab520-replacement22.post-execution.sqlite.sha256`.

## How the final adjusted result is assembled

```text
canonical 6,000-cell ledger
  − 264 cells from 22 rejected original questions
  = 5,736 retained scored cells

replacement database
  + 264 scored cells from 22 QA-approved replacements
  = 6,000 final scored cells
```

The final adjusted export has:

- 6,000 unique logical cell keys;
- 500 unique primary questions;
- 2,000 scores in OpenRouter A;
- 2,000 scores in OpenRouter B;
- 2,000 scores in GIFT/TailScale A;
- 500 scores for each arm/model combination;
- zero unresolved cells.

The per-cell export preserves the originating database, experiment, logical-call ID, attempt history, request/response hashes, score origin, replacement mapping, and exact-input-match status.

## Verification commands

Run these from the repository root:

```bash
cd /Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq

git rev-parse HEAD

shasum -a 256 -c \
  data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/manifests/code-provenance.sha256

shasum -a 256 -c \
  data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/checksums.sha256

sqlite3 \
  data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/manifests/ab520-replacement22.post-execution.sqlite \
  'PRAGMA integrity_check; SELECT COUNT(*) AS logical_calls FROM logical_calls; SELECT COUNT(*) AS scores FROM scores;'
```

Expected database output includes `ok`, `264`, and `264`.

## Related audit files

- `RUN_LEDGER.csv`: one row per provider invocation.
- `STATUS.md`: final arm coverage and recovery state.
- `QA_REPORT.md`: formal sourcing, blinded QA, and execution-integrity verdict.
- `exports/recovered-first-attempt-failures.csv`: both rejected first attempts and their successful retries.
- `manifests/frozen-replacement-cell-ledger.csv`: the exact 264 authorized replacement cells.
- `manifests/execution-manifest-final.json`: machine-readable final provenance and hashes.
