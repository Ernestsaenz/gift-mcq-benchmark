# QA-approved 22-question replacement and adjusted August benchmark

This directory is the auditable replacement workspace for the August 26 experiment. Formal sourcing and two distinct blinded QA passes approved all 22 questions. The cohort was then run across four models in OpenRouter condition A, OpenRouter condition B, and GIFT/TailScale condition A. TailScale condition B remains outside the authorized design.

The adjusted benchmark is complete: **2,000/2,000 scored cells per arm and 6,000/6,000 overall**. It retains 478 original benchmark questions (5,736 scored cells), removes the 22 rejected originals and all their prior cells, and inserts 22 newly identified replacement questions (264 scored cells). The replacements are new questions, not retroactive answers to the rejected originals.

## Models and conditions

- `google/gemini-3.6-flash`
- `google/gemma-4-26b-a4b-it`
- `qwen/qwen3.6-35b-a3b`
- `z-ai/glm-5.2`
- Condition A preserves the official answer option.
- Condition B performs the verified two-field substitution at the keyed option and `correct_option_text`.

## Main outputs

- `exports/benchmark-6000-cell-results-adjusted.csv`: all 6,000 scored cells with exact inputs, selected answers, correctness, attempts, hashes, and score origin.
- `exports/benchmark-500-question-catalog-adjusted.csv`: the complete adjusted primary benchmark.
- `exports/benchmark-514-active-question-catalog-adjusted.csv`: 500 primary questions plus the 14 currently active, collision-free reserves.
- `exports/reserve-20-historical-status-adjusted.csv`: all 20 historical reserve slots, showing seven promotions, one reviewed backfill, and six explicit vacancies pending QA.
- `exports/replacement-question-map.csv`: old ID → replacement ID → source/QA/execution mapping.
- `exports/recovered-first-attempt-failures.csv`: the two fail-closed first attempts and their successful isolated retries, without raw response text.
- `presentation/benchmark-results-presentation.html` and `presentation/statistics.json`: regenerated adjusted analysis.
- `manifests/execution-manifest-final.json`: final validation, provenance, counts, and hashes.
- `RUN_LEDGER.csv` and `STATUS.md`: one row per invocation and the final operational state.

The original result set remains unchanged at `data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04/`. The benchmark source corpus is `/Users/ernestsaenz/Programming/gift-project-compile/second-project/workbook-repairs-2026-07-30/outputs/all-regions-aparato-digestivo.corrected.xlsx` (SHA-256 `18f6becd4e51f1b9ef6a5a8ab68421e905cfe2584ec32a0e303b76f3cacf1e46`). The execution harness is `code/medrag_eval/`.

No input question, prompt, model identifier, answer key, or provider condition was edited during execution. GIFT calls used prompt ID 13, temperature 0, and the production SHA gate recorded in `manifests/production-evidence-2026-08-05.json`.

The adjusted CSV/JSON/HTML deliverables are complete. A new adjusted `.xlsx` could not be authored because the workspace-required `load_workspace_dependencies`/`@oai/artifact-tool` runtime was not available; the canonical pre-replacement workbook is therefore not presented as an adjusted output.
