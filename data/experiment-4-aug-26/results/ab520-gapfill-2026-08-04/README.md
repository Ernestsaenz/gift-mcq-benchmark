# August 26 benchmark results

This is the canonical result directory for experiment `ab520-gapfill-2026-08-04`.
The final fail-closed ledger contains **5,930 scored cells and 70 unresolved cells out of
6,000 required cells**.

## Experiment

The benchmark evaluates 500 primary Spanish digestive-medicine MCQs across four models:

- `google/gemini-3.6-flash`
- `google/gemma-4-26b-a4b-it`
- `qwen/qwen3.6-35b-a3b`
- `z-ai/glm-5.2`

OpenRouter ran Condition A and Condition B. GIFT/TailScale Medical RAG ran Condition A;
GIFT Condition B was outside this experiment. Condition B replaces the keyed option text
with `Ninguna de las respuestas anteriores es correcta.` without changing the keyed letter.

The 500 primary questions comprise 318 retained questions and 182 replacements. The
companion catalog documents 20 reserves, but reserves were not executed. Dataset files live
at `data/experiment-4-aug-26/`; the full forms are `flat-A.xlsx` and `flat-B.xlsx`.

## Final coverage

| Arm | Required | Scored | Unresolved |
|---|---:|---:|---:|
| OpenRouter A | 2,000 | 1,998 | 2 |
| OpenRouter B | 2,000 | 2,000 | 0 |
| GIFT/TailScale A | 2,000 | 1,932 | 68 |
| **Total** | **6,000** | **5,930** | **70** |

No answer was inferred from reasoning text or an unsuccessful response. See `STATUS.md` for
the retry timeline, recovered cells, residual causes, deployment gate, and concurrency.

## Directory map

- `runs/`: canonical SQLite database and WAL sidecars.
- `logs/`: redacted retry logs.
- `inputs/`: sparse execution workbooks used by the original gapfill.
- `exports/`: 6,000-cell CSV, 520-question catalog, summaries, unresolved ledger, paired
  OpenRouter results, and the traceability workbook.
- `manifests/`: frozen cell ledger, pre-retry 72-cell target list, pre-retry database
  snapshot, deployment evidence, provenance hashes, and checksums.
- `tools/`: export builder and manifest-constrained retry driver.
- `presentation/`: reproducible statistical analysis, standalone HTML deck, and rendered QA
  images.

`RUN_LEDGER.csv` records every retry invocation that issued provider traffic. Commands are
redacted and logs contain no credentials.

## Harness and provenance

The companion harness is `code/medrag_eval/` at repository commit
`9660b9a503cf68c45b9a808f38ba597b41769c16`. Runs used prompt version `mcq_es_v4`,
temperature 0, one run per cell, the original provider/model identifiers, and GIFT stored
prompt ID 13. Relevant hashes are in `manifests/code-provenance.sha256`; dataset and input
hashes are in `manifests/execution-manifest-final.json` and `manifests/run-manifest.json`.

GIFT retries were gated on the latest successful deployment workflow at backend commit
`29af9a4f1581f6ffc1921a44d96a2a2cbe36a84e` plus a fresh healthy production response.
The health endpoint does not expose a SHA, so the evidence combines the latest deployment
job and the live health result; see `manifests/production-evidence.json`.

## Rebuild

From the repository root:

```bash
uv run python data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04/tools/build_final_exports.py
python3 data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04/presentation/build_results_presentation.py
```

The export builder reads the canonical result database, the July reuse database at
`data/experiment-31-07-26/experiment.sqlite`, the August dataset, and the still-resolving
upstream selection dossier at `/private/tmp/ab182-q5i3oBTb/`. Those are documented dataset
provenance references; no benchmark dataset is duplicated here.

The pre-retry snapshot is
`manifests/ab520-gapfill-2026-08-04.pre-retry.sqlite`, SHA-256
`c2ea94788b6a743c67584f5afbecaf5321c8109afa89b3cd4a1a4c0a3f5a57bb`.

