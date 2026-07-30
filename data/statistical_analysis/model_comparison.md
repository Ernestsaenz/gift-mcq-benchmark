# bench_315_v2 Model Comparison

## Scope and Assumptions

Experiment: `bench_315_v2` in `runs/medrag_eval.sqlite`.

Outcome: `strict_correct`, treated as a binary paired outcome for each model on each question.

Pairing unit: question. Each within-provider comparison uses the same 315 questions as paired independent clusters.

Providers analyzed separately:

- `openrouter`
- `tailscale_medical_rag`

No cross-provider hypothesis tests are reported here.

One logical cell had two scored versions: TailScale `google/gemini-3.5-flash` on source question `g241`. The canonical value used here is the latest scored result by `scores.created_at, scores.id` (`strict_correct = 1`, score id `2521`). All other provider/model/question cells had one scored value.

## Methods

- Omnibus within-provider test: Cochran's Q across the four paired model outcomes.
- Pairwise within-provider tests: exact two-sided McNemar tests using discordant pairs only.
- Multiple comparisons: Holm correction applied separately to the six pairwise tests within each provider family.
- Significance reference: alpha = 0.05 after Holm correction.

Model order in pairwise tables is `A vs B`; `A only` means A correct and B incorrect, while `B only` means B correct and A incorrect.

## Per-Model Accuracy

| Provider | Model | Correct / N | Accuracy |
|---|---:|---:|---:|
| OpenRouter | `google/gemini-3.5-flash` | 303 / 315 | 96.19% |
| OpenRouter | `google/gemma-4-26b-a4b-it` | 232 / 315 | 73.65% |
| OpenRouter | `qwen/qwen3.6-35b-a3b` | 275 / 315 | 87.30% |
| OpenRouter | `qwen/qwen3.7-max` | 298 / 315 | 94.60% |
| TailScale | `google/gemini-3.5-flash` | 301 / 315 | 95.56% |
| TailScale | `google/gemma-4-26b-a4b-it` | 232 / 315 | 73.65% |
| TailScale | `qwen/qwen3.6-35b-a3b` | 265 / 315 | 84.13% |
| TailScale | `qwen/qwen3.7-max` | 297 / 315 | 94.29% |

## Omnibus Tests

| Provider | Cochran's Q | df | p-value | Interpretation |
|---|---:|---:|---:|---|
| OpenRouter | 121.0000 | 3 | 4.70e-26 | Strong evidence that accuracy differs among the four models. |
| TailScale | 117.4543 | 3 | 2.73e-25 | Strong evidence that accuracy differs among the four models. |

## OpenRouter Pairwise McNemar Tests

| A | B | A only | B only | Discordant | Exact p | Holm p | Interpretation |
|---|---|---:|---:|---:|---:|---:|---|
| `google/gemini-3.5-flash` | `google/gemma-4-26b-a4b-it` | 75 | 4 | 79 | 5.24e-18 | 3.15e-17 | Gemini 3.5 Flash is significantly higher. |
| `google/gemini-3.5-flash` | `qwen/qwen3.6-35b-a3b` | 32 | 4 | 36 | 1.94e-06 | 5.82e-06 | Gemini 3.5 Flash is significantly higher. |
| `google/gemini-3.5-flash` | `qwen/qwen3.7-max` | 12 | 7 | 19 | 0.3593 | 0.3593 | No statistically significant difference. |
| `google/gemma-4-26b-a4b-it` | `qwen/qwen3.6-35b-a3b` | 11 | 54 | 65 | 6.03e-08 | 2.41e-07 | Qwen 3.6 is significantly higher. |
| `google/gemma-4-26b-a4b-it` | `qwen/qwen3.7-max` | 5 | 71 | 76 | 5.25e-16 | 2.62e-15 | Qwen 3.7 Max is significantly higher. |
| `qwen/qwen3.6-35b-a3b` | `qwen/qwen3.7-max` | 7 | 30 | 37 | 0.000191 | 0.000382 | Qwen 3.7 Max is significantly higher. |

## TailScale Pairwise McNemar Tests

| A | B | A only | B only | Discordant | Exact p | Holm p | Interpretation |
|---|---|---:|---:|---:|---:|---:|---|
| `google/gemini-3.5-flash` | `google/gemma-4-26b-a4b-it` | 71 | 2 | 73 | 5.72e-19 | 3.43e-18 | Gemini 3.5 Flash is significantly higher. |
| `google/gemini-3.5-flash` | `qwen/qwen3.6-35b-a3b` | 43 | 7 | 50 | 2.10e-07 | 8.39e-07 | Gemini 3.5 Flash is significantly higher. |
| `google/gemini-3.5-flash` | `qwen/qwen3.7-max` | 13 | 9 | 22 | 0.5235 | 0.5235 | No statistically significant difference. |
| `google/gemma-4-26b-a4b-it` | `qwen/qwen3.6-35b-a3b` | 11 | 44 | 55 | 8.70e-06 | 1.74e-05 | Qwen 3.6 is significantly higher. |
| `google/gemma-4-26b-a4b-it` | `qwen/qwen3.7-max` | 3 | 68 | 71 | 5.06e-17 | 2.53e-16 | Qwen 3.7 Max is significantly higher. |
| `qwen/qwen3.6-35b-a3b` | `qwen/qwen3.7-max` | 7 | 39 | 46 | 1.83e-06 | 5.49e-06 | Qwen 3.7 Max is significantly higher. |

## Interpretation

Within both providers, Cochran's Q rejects equal model accuracy across the four paired model outcomes.

After Holm correction, the same pairwise pattern appears for OpenRouter and TailScale:

- `google/gemini-3.5-flash` and `qwen/qwen3.7-max` are the top two models by accuracy, but their paired difference is not statistically significant within either provider.
- Both top models significantly outperform `qwen/qwen3.6-35b-a3b` and `google/gemma-4-26b-a4b-it`.
- `qwen/qwen3.6-35b-a3b` significantly outperforms `google/gemma-4-26b-a4b-it`.
- `google/gemma-4-26b-a4b-it` is the lowest-performing model in both providers.

These conclusions are based only on within-provider paired binary tests over the 315 shared questions.
