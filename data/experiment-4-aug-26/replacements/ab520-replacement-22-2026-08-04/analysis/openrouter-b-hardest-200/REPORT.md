# OpenRouter B: the 200 operationally hardest questions

Generated: 2026-08-05T10:58:17.352561+00:00

Verdict: **complete descriptive sub-analysis; source validation passed**.

## Definition and the rank-200 tie

Difficulty is the number of the four OpenRouter B models that answered a question incorrectly. All models are weighted equally. Questions are ordered by wrong-model count descending. Exact ties use the SHA-256 of `openrouter_B-hard200-v1|<source_key>` ascending.

This produces a **150-question invariant hard core** (at least two models wrong) and a deterministic 50-question sample from the 146 questions tied with exactly one model wrong. Those 50 are not uniquely harder than the 96 equally scored exclusions.

| Wrong models | Correct models | Questions | Difficulty-rank interval |
|---:|---:|---:|---:|
| 4 | 0 | 19 | 1–19 |
| 3 | 1 | 48 | 20–67 |
| 2 | 2 | 83 | 68–150 |
| 1 | 3 | 146 | 151–296 |
| 0 | 4 | 204 | 297–500 |

Rank 200 is `n046` (`comunidad-de-madrid|2021|main|61`); rank 201 is `b471` (`comunidad-de-madrid|2021|main|37`).

## Model performance

These figures are descriptive and selection-conditioned. The same B outcomes define the hard set and are summarized below.

| Model | Full B | Core 150 B | Hard 200 B | Same 200 in A | Any valid tie-set B range |
|---|---:|---:|---:|---:|---:|
| Gemini 3.6 Flash | 450/500 (90.0%) | 102/150 (68.0%) | 152/200 (76.0%) | 193/200 (96.5%) | 75.0%–76.0% |
| GLM 5.2 | 389/500 (77.8%) | 56/150 (37.3%) | 101/200 (50.5%) | 176/200 (88.0%) | 44.5%–53.0% |
| Qwen 3.6 35B | 358/500 (71.6%) | 31/150 (20.7%) | 74/200 (37.0%) | 156/200 (78.0%) | 29.0%–40.5% |
| Gemma 4 26B | 271/500 (54.2%) | 25/150 (16.7%) | 37/200 (18.5%) | 135/200 (67.5%) | 12.5%–33.5% |
| **All model–question cells** | **1,468/2,000 (73.4%)** | **214/600 (35.7%)** | **364/800 (45.5%)** | **660/800 (82.5%)** | **45.5% invariant** |

On these selected cells, B is 37.0 percentage points below A. This is not an unbiased estimate of the condition effect because the questions were selected for B errors. The full pre-specified 500-question A–B difference remains the primary estimate.

## Error structure

- 19 questions were missed by all four models.
- 48 were missed by three models: Gemini alone was correct on 32, Gemma on 7, Qwen on 5, and GLM on 4.
- 83 were missed by two models. The largest paired pattern was Gemma + Qwen (43 questions), followed by Gemma + GLM (18).
- In the full one-error boundary, Gemma alone missed 104, Qwen 23, GLM 17, and Gemini 2.
- Ten of the 19 all-model failures converged on the same wrong option; the other nine split across two wrong options.

| Model pair | Shared-error questions | Jaccard | Phi |
|---|---:|---:|---:|
| Gemini 3.6 Flash + GLM 5.2 | 35 | 0.278 | 0.383 |
| Gemini 3.6 Flash + Qwen 3.6 35B | 35 | 0.223 | 0.308 |
| Gemini 3.6 Flash + Gemma 4 26B | 32 | 0.130 | 0.122 |
| GLM 5.2 + Qwen 3.6 35B | 67 | 0.360 | 0.379 |
| GLM 5.2 + Gemma 4 26B | 74 | 0.278 | 0.224 |
| Qwen 3.6 35B + Gemma 4 26B | 98 | 0.359 | 0.293 |

Every pairwise shared error lies in the invariant 150-question core.

## Selected-set composition

Origins: new182=72, replacement22_2026-08-04=9, retained318=119. Negated stems: 40/200. Correct-key letters: B=78, C=78, D=44.

| Region | Hard-200 questions | All benchmark questions |
|---|---:|---:|
| Andalucía | 35 | 64 |
| Illes Balears | 31 | 90 |
| Galicia | 30 | 70 |
| La Rioja | 24 | 51 |
| Comunidad de Madrid | 15 | 39 |
| Navarra | 15 | 34 |
| Aragón | 13 | 32 |
| Comunitat Valenciana | 13 | 23 |
| Castilla-La Mancha | 12 | 48 |
| Castilla y León | 7 | 27 |
| Región de Murcia | 5 | 22 |

These subgroup counts are unadjusted composition summaries. For source comparisons, the tie-free core rate in `subgroup-summary.csv` is safer than treating administrative hard-200 membership as a clinical effect.

## Nineteen questions missed by all four models

| Question | Source key | Key | B selected letters by model |
|---|---|---:|---|
| b370 | `castilla-la-mancha|2017|main|84` | B | Gemini 3.6 Flash=d;GLM 5.2=d;Qwen 3.6 35B=a;Gemma 4 26B=d |
| b455 | `aragon|2017|main|79` | D | Gemini 3.6 Flash=b;GLM 5.2=b;Qwen 3.6 35B=b;Gemma 4 26B=b |
| n088 | `castilla-y-leon|2019|main|43` | B | Gemini 3.6 Flash=d;GLM 5.2=d;Qwen 3.6 35B=d;Gemma 4 26B=d |
| b170 | `navarra|2022|caso-clinico-1|95` | D | Gemini 3.6 Flash=b;GLM 5.2=b;Qwen 3.6 35B=b;Gemma 4 26B=c |
| b470 | `aragon|2017|reserva-especifica|108` | B | Gemini 3.6 Flash=d;GLM 5.2=d;Qwen 3.6 35B=d;Gemma 4 26B=d |
| b322 | `comunidad-de-madrid|2021|main|42` | B | Gemini 3.6 Flash=c;GLM 5.2=c;Qwen 3.6 35B=c;Gemma 4 26B=c |
| b425 | `aragon|2017|reserva-especifica|102` | C | Gemini 3.6 Flash=a;GLM 5.2=a;Qwen 3.6 35B=a;Gemma 4 26B=d |
| n147 | `castilla-la-mancha|2022|main|20` | D | Gemini 3.6 Flash=c;GLM 5.2=c;Qwen 3.6 35B=c;Gemma 4 26B=c |
| b374 | `castilla-la-mancha|2017|main|71` | D | Gemini 3.6 Flash=a;GLM 5.2=a;Qwen 3.6 35B=a;Gemma 4 26B=a |
| b168 | `navarra|2022|caso-clinico-1|93` | B | Gemini 3.6 Flash=c;GLM 5.2=c;Qwen 3.6 35B=c;Gemma 4 26B=a |
| n112 | `andalucia|2022|cuestionario-teorico|46` | C | Gemini 3.6 Flash=a;GLM 5.2=a;Qwen 3.6 35B=a;Gemma 4 26B=a |
| b355 | `la-rioja|2021|main|37` | D | Gemini 3.6 Flash=c;GLM 5.2=c;Qwen 3.6 35B=c;Gemma 4 26B=a |
| b196 | `comunidad-de-madrid|2021|main|135` | B | Gemini 3.6 Flash=d;GLM 5.2=d;Qwen 3.6 35B=d;Gemma 4 26B=d |
| n130 | `castilla-y-leon|2019|main|116` | C | Gemini 3.6 Flash=b;GLM 5.2=b;Qwen 3.6 35B=b;Gemma 4 26B=d |
| b211 | `galicia|2016|reserva-especifica|108` | B | Gemini 3.6 Flash=c;GLM 5.2=c;Qwen 3.6 35B=c;Gemma 4 26B=a |
| b326 | `andalucia|2021|cuestionario-teorico|31` | C | Gemini 3.6 Flash=b;GLM 5.2=b;Qwen 3.6 35B=b;Gemma 4 26B=b |
| n176 | `galicia|2022|main|52` | B | Gemini 3.6 Flash=a;GLM 5.2=a;Qwen 3.6 35B=c;Gemma 4 26B=c |
| b123 | `illes-balears|2022|caso-6|126` | B | Gemini 3.6 Flash=d;GLM 5.2=d;Qwen 3.6 35B=a;Gemma 4 26B=d |
| b134 | `illes-balears|2022|caso-6|137` | B | Gemini 3.6 Flash=d;GLM 5.2=d;Qwen 3.6 35B=d;Gemma 4 26B=d |

Full stems, options, source metadata, and per-model results are retained in the CSV outputs rather than repeated in this report.

## Sensitivity and limitations

- A strength-adjusted B-only tie-break changes 30 of the 200 members. Its intersection and Jaccard similarity with the primary set are 170 and 0.739. Aggregate accuracy remains 45.5%, but the model-specific allocation changes.
- Difficulty is based on one binary outcome per model, not repeated-run probabilities or an item-response model.
- Within-tier order is administrative; it does not establish fine-grained clinical difficulty.
- Condition B changes the keyed answer text, so content difficulty and answer-form sensitivity are inseparable in this subset.
- No technical failure was counted as an incorrect answer. All 2,000 B cells were scored, parsed, and exact-input matched.
- No inferential p-values are reported: this is an exploratory description of the complete fixed benchmark, and the hard set is outcome-selected.

## Reproducibility

- Source cell CSV SHA-256: `ce91b3f3eb90cd0b125a170a6f0a0a967c02d63da17cfa97161e62f739c4b721`.
- Ordered selected-key SHA-256: `9035f0e99364460f0036f5c210e35d59c3e2786bb409d2dbeb9fd9325dab1128`.
- Sorted selected-key-set SHA-256: `ee9484af0041f05cad216f1e6368e30d88970765ccaff03a84314105f325d13e`.
- Tie namespace: `openrouter_B-hard200-v1|`.
- Rebuild with `python3 build_analysis.py` from this directory.

## Files

- `difficulty-ranking-all-500.csv`: all questions, tiers, tie hashes, and per-model A/B outcomes.
- `hardest-200-questions.csv`: the exact operational panel.
- `hardest-200-model-cells.csv`: the 800 underlying OpenRouter B cells.
- `boundary-tie-146.csv`: all equally scored rank-151–296 candidates.
- `unanimously-wrong-19.csv`: the invariant all-model failures.
- `model-performance.csv`, `difficulty-tier-summary.csv`, `error-pattern-summary.csv`, `model-error-overlap.csv`, and `subgroup-summary.csv`: supporting tables.
- `summary.json`: machine-readable methods, validations, and results.
- `INDEPENDENT_QA.md`: independent source-level recomputation and verdict.
- `checksums.sha256`: hashes for this analysis package.
