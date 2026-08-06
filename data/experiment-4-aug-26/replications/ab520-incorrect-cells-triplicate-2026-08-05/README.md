# Incorrect-cell triplicates for the adjusted AB520 benchmark

This workspace adds independent run indices 2 and 3 for every arm/model/question
cell that was strictly incorrect in run 1 of the adjusted 500-question benchmark.
The canonical 6,000-cell result is an immutable input and is not edited.

Authorized arms are OpenRouter A, OpenRouter B, and TailScale/GIFT A. The scope is
cell-level: only the model that missed a question in a given arm is repeated. The
frozen target is 898 run-1 incorrect cells and 1,796 new logical calls.

All calls retain the original question form, model identifier, `mcq_es_v4` prompt,
temperature 0, top-p 1, OpenRouter JSON-schema behavior, and GIFT prompt ID 13.
Technical retries remain attempts inside one logical replicate; they are never
counted as additional independent runs.

The source result is:

`../../replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv`

Run artifacts are written under `runs/`, `logs/`, `manifests/`, `invocations/`,
and `exports/`. `STATUS.md`, `RUN_LEDGER.csv`, and `FINAL_REPORT.md` are generated
as the execution progresses and is finalized.
