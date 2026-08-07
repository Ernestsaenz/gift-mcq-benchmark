# Independent QA of the OpenRouter B hardest-200 analysis

Date: 2026-08-05

Verdict: **PASS — ready to share**.

The reviewer recomputed the analysis directly from the authoritative adjusted 6,000-cell CSV without importing or running `build_analysis.py`. No numerical, ranking, lineage, or checksum discrepancy was found.

## Independently reproduced

- Source cell CSV SHA-256: `ce91b3f3eb90cd0b125a170a6f0a0a967c02d63da17cfa97161e62f739c4b721`.
- Source catalog SHA-256: `351f5044854c285f3546ae49d65a041a5dacec3ff6c6de98177dd3b058c3c2ba`.
- OpenRouter B: 2,000 cells, 500 questions, and exactly four distinct model outcomes per question.
- Difficulty tiers for 4/3/2/1/0 wrong models: 19/48/83/146/204 questions.
- Invariant hard core: 150 questions with at least two models wrong.
- Deterministic boundary: 50 selected from the 146-question one-error tie using `openrouter_B-hard200-v1|<source_key>`.
- Rank 200: `n046`; rank 201: `b471`.
- Ordered selected-key SHA-256: `9035f0e99364460f0036f5c210e35d59c3e2786bb409d2dbeb9fd9325dab1128`.
- Sorted selected-key-set SHA-256: `ee9484af0041f05cad216f1e6368e30d88970765ccaff03a84314105f325d13e`.
- Output cardinalities: 500 ranked questions, 200 selected questions, 800 selected model cells, 146 cutoff-tie questions, and 19 all-model failures.

## Model totals reproduced

| Model | Full B correct | Core-150 B correct | Hard-200 B correct | Same-200 A correct |
|---|---:|---:|---:|---:|
| Gemini 3.6 Flash | 450 | 102 | 152 | 193 |
| GLM 5.2 | 389 | 56 | 101 | 176 |
| Qwen 3.6 35B | 358 | 31 | 74 | 156 |
| Gemma 4 26B | 271 | 25 | 37 | 135 |

The reviewer also reproduced the 343 both-correct, 317 A-only-correct, 21 B-only-correct, and 119 both-wrong paired cell transitions. All error patterns, pairwise overlap/Jaccard/phi values, subgroup rows, unanimous wrong-letter patterns, length correlations, and tie-break sensitivity results matched.

## Leakage and failure audit

- Primary selection uses only OpenRouter B strict-correctness outcomes and the declared hash tie-break.
- Condition A is joined only after selection for a clearly labeled descriptive comparison.
- Thirty-seven OpenRouter B logical cells had earlier unparseable HTTP-200 attempts, but every one ended with a scored, parse-valid, exact-input-matched result.
- No failed attempt was counted as an incorrect answer.
- The report correctly states that only the first 150 questions are uniquely hard under the primary measure; the final 50 are an administrative sample from an unresolved tie.

## Maintenance note

`build_analysis.py` contains several assertions and narrative totals fixed to this frozen benchmark version. They match the source exactly and protect the current artifact, but a future analysis against a changed source should review those constants rather than assuming the script is version-agnostic.

