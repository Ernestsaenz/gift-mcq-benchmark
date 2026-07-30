# Exploratory group analysis: `bench_315_v2`

Statistical Agent 4 analyzed exploratory groupings in `runs/medrag_eval.sqlite` for experiment `bench_315_v2`.

## Data used

- Dataset: `galicia_digestivo_315`
- Questions: 315
- Latest scored model-provider observations: 2,520
- Providers: `openrouter`, `tailscale_medical_rag`
- Models per provider: `google/gemini-3.5-flash`, `google/gemma-4-26b-a4b-it`, `qwen/qwen3.6-35b-a3b`, `qwen/qwen3.7-max`
- Outcome: `strict_correct`. In the latest scored calls, `letter_correct`, `strict_correct`, and `lenient_correct` were identical.
- Latest parse status: all 2,520 latest parsed answers were `ok`.

## Group definitions

Source type:

- Closed-source Gemini: `google/gemini-3.5-flash`
- Selected open-source/open-weight models: `google/gemma-4-26b-a4b-it`, `qwen/qwen3.6-35b-a3b`, `qwen/qwen3.7-max`

Size class:

- Big: `google/gemini-3.5-flash`, `qwen/qwen3.7-max`
- Small: `google/gemma-4-26b-a4b-it`, `qwen/qwen3.6-35b-a3b`

## Methods

The primary focused inference here uses the requested fallback:

- For each question, preserve all eight provider-model observations as one cluster.
- Compute paired question-level group contrasts.
- Estimate uncertainty with a question-cluster bootstrap resampling the 315 questions with replacement, 50,000 replicates, seed `20260526`.
- Estimate odds ratio CIs from the same cluster bootstrap.
- Report exploratory two-sided p-values from an exact paired sign-flip test over question-level contrasts. These p-values are only descriptive because the grouping labels were not randomized.

I also checked the repository's companion GEE outputs in `reports/statistical_analysis/exploratory_source_gee.csv` and `reports/statistical_analysis/exploratory_size_gee.csv`. Those provider-adjusted binomial GEE results use question-level clustering and agree with the bootstrap conclusions.

## Descriptive accuracy by model and provider

| Provider | Model | Source group | Size group | Correct / N | Accuracy |
|---|---|---|---|---:|---:|
| `openrouter` | `google/gemini-3.5-flash` | Closed-source Gemini | Big | 303 / 315 | 96.2% |
| `openrouter` | `google/gemma-4-26b-a4b-it` | Selected open-source | Small | 232 / 315 | 73.7% |
| `openrouter` | `qwen/qwen3.6-35b-a3b` | Selected open-source | Small | 275 / 315 | 87.3% |
| `openrouter` | `qwen/qwen3.7-max` | Selected open-source | Big | 298 / 315 | 94.6% |
| `tailscale_medical_rag` | `google/gemini-3.5-flash` | Closed-source Gemini | Big | 301 / 315 | 95.6% |
| `tailscale_medical_rag` | `google/gemma-4-26b-a4b-it` | Selected open-source | Small | 232 / 315 | 73.7% |
| `tailscale_medical_rag` | `qwen/qwen3.6-35b-a3b` | Selected open-source | Small | 265 / 315 | 84.1% |
| `tailscale_medical_rag` | `qwen/qwen3.7-max` | Selected open-source | Big | 297 / 315 | 94.3% |

## Primary grouped estimates

| Contrast | Group A accuracy | Group B accuracy | Difference, A - B | Bootstrap 95% CI | Odds ratio | Bootstrap 95% CI | Sign-flip p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Closed-source Gemini vs selected open-source | 604 / 630 = 95.9% | 1,599 / 1,890 = 84.6% | +11.3 pp | +8.5 to +14.1 pp | 4.23 | 2.77 to 7.81 | 1.36e-15 |
| Big vs small | 1,199 / 1,260 = 95.2% | 1,004 / 1,260 = 79.7% | +15.5 pp | +12.4 to +18.7 pp | 5.01 | 3.64 to 7.45 | 4.82e-22 |

Provider-adjusted GEE cross-check:

| GEE contrast term | Odds ratio | Cluster-robust 95% CI | Wald p |
|---|---:|---:|---:|
| `source_c[T.closed_source]` | 4.23 | 2.58 to 6.93 | 1.09e-08 |
| `size_c[T.big]` | 5.03 | 3.37 to 7.50 | 2.33e-15 |
| `size_c[T.big]:provider_c[T.tailscale_medical_rag]` | 0.99 | 0.72 to 1.37 | 0.974 |

Question-level paired contrast distribution:

| Contrast | Questions where A > B | A = B | A < B | Median question contrast |
|---|---:|---:|---:|---:|
| Closed-source Gemini vs selected open-source | 100 | 203 | 12 | 0.0 pp |
| Big vs small | 99 | 206 | 10 | 0.0 pp |

The median paired contrast is 0 because many questions were answered correctly by all or nearly all compared observations. The mean contrast is positive because when the grouped models differ, the higher-performing group more often has the advantage.

## Provider-stratified descriptives

| Provider | Contrast | Group A accuracy | Group B accuracy | Difference |
|---|---|---:|---:|---:|
| `openrouter` | Closed-source Gemini vs selected open-source | 303 / 315 = 96.2% | 805 / 945 = 85.2% | +11.0 pp |
| `tailscale_medical_rag` | Closed-source Gemini vs selected open-source | 301 / 315 = 95.6% | 794 / 945 = 84.0% | +11.5 pp |
| `openrouter` | Big vs small | 601 / 630 = 95.4% | 507 / 630 = 80.5% | +14.9 pp |
| `tailscale_medical_rag` | Big vs small | 598 / 630 = 94.9% | 497 / 630 = 78.9% | +16.0 pp |

## Sensitivity checks

These are not replacements for the requested groupings, but they show how strongly the source-type result depends on which open models are included.

| Contrast | Group A accuracy | Group B accuracy | Difference | Bootstrap 95% CI | Sign-flip p |
|---|---:|---:|---:|---:|---:|
| Gemini vs Qwen 3.7 Max only | 604 / 630 = 95.9% | 595 / 630 = 94.4% | +1.4 pp | -1.1 to +4.0 pp | 0.324 |
| Gemini vs Qwen-only models | 604 / 630 = 95.9% | 1,135 / 1,260 = 90.1% | +5.8 pp | +3.3 to +8.3 pp | 8.41e-06 |
| Qwen 3.7 Max vs Qwen 3.6/35B | 595 / 630 = 94.4% | 540 / 630 = 85.7% | +8.7 pp | +5.6 to +12.1 pp | 2.04e-07 |

## Interpretation and caveats

The requested grouped contrasts favor closed-source Gemini over the selected open-source mix and favor the big size class over the small size class. The estimated differences are large on this question set, and the question-clustered uncertainty intervals do not overlap zero for the primary grouped contrasts.

However, these are exploratory associations, not causal estimates:

- The source-type comparison is a single closed-source model family, Gemini, versus a selected mix of Gemma and Qwen models. It cannot isolate source availability from model family, training data, serving stack, or model generation.
- The selected open-source group is heterogeneous. Qwen 3.7 Max was close to Gemini, while Gemma and Qwen 3.6/35B were lower. The Gemini-vs-Qwen 3.7 Max sensitivity contrast was only +1.4 pp with a CI crossing zero.
- The size-class comparison is also confounded by family and model identity. The only same-family size-style sensitivity here is Qwen 3.7 Max versus Qwen 3.6/35B, which still favored the larger Qwen model by +8.7 pp.
- Provider observations are balanced and provider-stratified descriptives point in the same direction, but the analysis treats provider-model outputs as repeated observations within question clusters. It does not model model-family random effects.
- P-values are descriptive and conditional on treating the 315 questions as the sampled clusters. They do not license broad claims such as "closed-source models outperform open-source models" beyond this benchmark configuration.

Practical summary: in `bench_315_v2`, the top-performing models were Gemini and Qwen 3.7 Max, while Gemma and Qwen 3.6/35B drove most of the grouped gaps.
