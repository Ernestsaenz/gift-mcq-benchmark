# Full adjusted model for `strict_correct`

Experiment: `bench_315_v2`  
Database: `runs/medrag_eval.sqlite`  
Generated: 2026-05-26

## Analysis dataset

The unit of analysis is one scored logical call per provider/model/question condition.
The raw `scores` table contains one duplicated logical call:

| logical_call_id | question_id | provider | model | score_ids | strict_values | score_created |
| --- | --- | --- | --- | --- | --- | --- |
| 451 | g241 | tailscale_medical_rag | google/gemini-3.5-flash | 1631,2521 | 0,1 | 2026-05-25T17:07:18+00:00,2026-05-26T00:15:41+00:00 |

To avoid overweighting that logical call, the analysis uses the latest score row per
`logical_call_id` (`MAX(scores.id)`). This yields 2,520 observations across 315 question
clusters, with exactly 8 observations per question.

Cell counts after this de-duplication:

| provider | model | n | correct | accuracy |
| --- | --- | --- | --- | --- |
| openrouter | google/gemini-3.5-flash | 315 | 303 | 0.961905 |
| openrouter | google/gemma-4-26b-a4b-it | 315 | 232 | 0.736508 |
| openrouter | qwen/qwen3.6-35b-a3b | 315 | 275 | 0.873016 |
| openrouter | qwen/qwen3.7-max | 315 | 298 | 0.946032 |
| tailscale_medical_rag | google/gemini-3.5-flash | 315 | 301 | 0.955556 |
| tailscale_medical_rag | google/gemma-4-26b-a4b-it | 315 | 232 | 0.736508 |
| tailscale_medical_rag | qwen/qwen3.6-35b-a3b | 315 | 265 | 0.841270 |
| tailscale_medical_rag | qwen/qwen3.7-max | 315 | 297 | 0.942857 |

## Model

The canonical aggregate analysis now fits this model with `statsmodels` via the
inline `uv` dependencies declared in `run_statistical_analysis.py`. This focused
report originally cross-checked the same independence-working GEE/logistic
estimating equation directly; the numeric results align:

```text
strict_correct ~ provider * model
cluster = question_id
family = binomial
link = logit
working correlation = independence
covariance = question-cluster robust sandwich
```

This gives the same coefficient estimates as logistic regression with the listed fixed
effects and uses question-cluster robust standard errors to account for repeated
questions.

Reference levels:

| factor | reference |
| --- | --- |
| provider | openrouter |
| model | google/gemini-3.5-flash |

The fit converged in 8 Newton iterations. The full-model log likelihood was -864.442.

## Coefficients

Wald p-values use the cluster-robust standard errors and a large-sample normal
approximation.

| term | coef | robust_se | z | p | OR | OR_95_CI |
| --- | --- | --- | --- | --- | --- | --- |
| Intercept | 3.229 | 0.294 | 10.970 | <0.001 | 25.250 | 14.181 to 44.958 |
| provider[tailscale_medical_rag] | -0.161 | 0.161 | -1.001 | 0.317 | 0.851 | 0.621 to 1.167 |
| model[google/gemma-4-26b-a4b-it] | -2.201 | 0.299 | -7.366 | <0.001 | 0.111 | 0.062 to 0.199 |
| model[qwen/qwen3.6-35b-a3b] | -1.301 | 0.288 | -4.512 | <0.001 | 0.272 | 0.155 to 0.479 |
| model[qwen/qwen3.7-max] | -0.365 | 0.319 | -1.143 | 0.253 | 0.694 | 0.371 to 1.298 |
| provider[tailscale_medical_rag]:model[google/gemma-4-26b-a4b-it] | 0.161 | 0.186 | 0.866 | 0.387 | 1.174 | 0.816 to 1.690 |
| provider[tailscale_medical_rag]:model[qwen/qwen3.6-35b-a3b] | -0.099 | 0.218 | -0.456 | 0.648 | 0.905 | 0.591 to 1.388 |
| provider[tailscale_medical_rag]:model[qwen/qwen3.7-max] | 0.100 | 0.270 | 0.371 | 0.711 | 1.105 | 0.651 to 1.878 |

Interpretation notes:

- The intercept is the log odds for `openrouter` with `google/gemini-3.5-flash`.
- The provider main effect is the tailscale versus openrouter contrast for the reference model.
- Model main effects are model contrasts versus `google/gemini-3.5-flash` within `openrouter`.
- Interaction terms are additional tailscale versus openrouter deviations for each non-reference model.

## Predicted accuracies

Because the model includes the full `provider * model` interaction, fitted probabilities
match the de-duplicated cell accuracies. Confidence intervals are delta-method intervals
using the question-cluster robust covariance.

| provider | model | n | correct | predicted_accuracy | robust_se | 95_CI |
| --- | --- | --- | --- | --- | --- | --- |
| openrouter | google/gemini-3.5-flash | 315 | 303 | 0.962 | 0.011 | 0.941 to 0.983 |
| openrouter | google/gemma-4-26b-a4b-it | 315 | 232 | 0.737 | 0.025 | 0.688 to 0.785 |
| openrouter | qwen/qwen3.6-35b-a3b | 315 | 275 | 0.873 | 0.019 | 0.836 to 0.910 |
| openrouter | qwen/qwen3.7-max | 315 | 298 | 0.946 | 0.013 | 0.921 to 0.971 |
| tailscale_medical_rag | google/gemini-3.5-flash | 315 | 301 | 0.956 | 0.012 | 0.933 to 0.978 |
| tailscale_medical_rag | google/gemma-4-26b-a4b-it | 315 | 232 | 0.737 | 0.025 | 0.688 to 0.785 |
| tailscale_medical_rag | qwen/qwen3.6-35b-a3b | 315 | 265 | 0.841 | 0.021 | 0.801 to 0.882 |
| tailscale_medical_rag | qwen/qwen3.7-max | 315 | 297 | 0.943 | 0.013 | 0.917 to 0.968 |

## Provider contrasts by model

Risk differences are `tailscale_medical_rag - openrouter` on the probability scale.
P-values use delta-method cluster-robust standard errors.

| model | openrouter | tailscale | risk_diff | rd_se | rd_p | OR_ts_vs_or | or_p |
| --- | --- | --- | --- | --- | --- | --- | --- |
| google/gemini-3.5-flash | 0.962 | 0.956 | -0.006 | 0.006 | 0.317 | 0.851 | 0.317 |
| google/gemma-4-26b-a4b-it | 0.737 | 0.737 | 0.000 | 0.017 | 1.000 | 1.000 | 1.000 |
| qwen/qwen3.6-35b-a3b | 0.873 | 0.841 | -0.032 | 0.017 | 0.057 | 0.771 | 0.058 |
| qwen/qwen3.7-max | 0.946 | 0.943 | -0.003 | 0.011 | 0.781 | 0.941 | 0.782 |

The balanced average provider risk difference across the four model levels is -0.010
(SE 0.0068, z = -1.527, p = 0.127).

## Provider by model interaction

The joint cluster-robust Wald test of the three interaction terms gives:

```text
chi-square(3) = 2.854
p = 0.415
```

There is no statistical support in this fitted model for a provider-by-model interaction.
The largest provider contrast is for `qwen/qwen3.6-35b-a3b` (-3.2 percentage points for
tailscale versus openrouter), but it is not conventionally significant after accounting
for question clustering (risk-difference p = 0.057; odds-ratio p = 0.058), and the joint
interaction test is clearly non-significant.

As a descriptive check only, the ordinary unclustered likelihood-ratio comparison of
the interaction model versus an additive provider-plus-model model gives
`chi-square(3) = 0.833`, `p = 0.842`.

## Assumptions and limitations

- The model treats the 315 questions as independent clusters and allows arbitrary
  within-question correlation across the 8 provider/model outcomes.
- The robust inference is asymptotic in the number of clusters. With 315 question
  clusters this is reasonable, but p-values are still Wald approximations.
- No random-intercept mixed-effects logistic model was fit because no stable local GLMM
  implementation was available (`statsmodels`/`scipy` absent). A custom mixed model would
  be less defensible than the requested clustered GEE/logistic approach.
- The analysis is observational with respect to provider/model conditions and does not
  establish causal effects.
- One conflicting duplicate score existed for `logical_call_id=451`; using the latest
  score is consistent with one scored outcome per logical call, but results involving
  `tailscale_medical_rag` plus `google/gemini-3.5-flash` move slightly if the older score
  is used instead.
