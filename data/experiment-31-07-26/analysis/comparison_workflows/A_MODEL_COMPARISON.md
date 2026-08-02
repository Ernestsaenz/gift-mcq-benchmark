# Independent model comparison within Experiment A

**Workflow:** A-model comparison  
**Scope:** OpenRouter condition/Experiment A only  
**Canonical input:** `../paired_clean.json`, export v3  
**Input SHA-256:** `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187`  
**Analysis population:** rows with `analysis_include == true`  
**Canonical population before complete-case restriction:** 318 items, 1,271 model–item cells, 201 clinical clusters

## Verdict

The four deployed model configurations did not perform equally in Experiment A. On the 317 questions answered by every model, a saturated risk-difference model with CR1 covariance at the clinical-cluster level gave **F(3, 199) = 22.746, p = 1.053×10⁻¹²**. The complete-case ranking was Gemini 3.6 Flash (97.79%), GLM-5.2 (93.06%), Qwen 3.6 35B-A3B (88.33%), then Gemma 4 26B-A4B-IT (79.18%). All six pairwise differences remained significant after Holm correction within the six-comparison family. An independent exact whole-cluster sign-flip sensitivity analysis reached the same six decisions.

This is a comparison of the **deployed configurations on this benchmark**, not proof that one underlying model architecture is universally superior. There was one run per model–item cell, and provider routing was not pinned.

## Population and missingness

The approved v3 A/B table contains one A-side missing response: `b320 × z-ai/glm-5.2`. The run status records repeated length termination for that cell; it was dropped, not counted as wrong. The other three A responses on `b320` are present: Gemini and Qwen were correct, while Gemma was incorrect.

| Model | Available A cells | Correct | All-available accuracy |
|---|---:|---:|---:|
| Gemini 3.6 Flash | 318 | 311 | 97.80% |
| GLM-5.2 | 317 | 295 | 93.06% |
| Qwen 3.6 35B-A3B | 318 | 281 | 88.36% |
| Gemma 4 26B-A4B-IT | 318 | 251 | 78.93% |

For the four-model hypothesis test and all pairwise contrasts, `b320` was removed from every model. The common comparison set therefore contains **317 items × 4 models = 1,268 observations in 200 clinical clusters**. No response was imputed. This restriction changes no rank and moves any displayed accuracy by at most 0.25 percentage point.

## Complete-case descriptive comparison

Whole-cluster percentile intervals below use 200,000 bootstrap replicates with seed `20260731`. They describe uncertainty from resampling clinical clusters and are not multiplicity-adjusted.

| Rank | Model | Correct / 317 | Accuracy | Cluster-bootstrap 95% CI |
|---:|---|---:|---:|---:|
| 1 | Gemini 3.6 Flash | 310 / 317 | **97.79%** | 95.93% to 99.26% |
| 2 | GLM-5.2 | 295 / 317 | **93.06%** | 89.90% to 95.77% |
| 3 | Qwen 3.6 35B-A3B | 280 / 317 | **88.33%** | 84.35% to 91.72% |
| 4 | Gemma 4 26B-A4B-IT | 251 / 317 | **79.18%** | 73.87% to 83.61% |

The maximum observed separation was 18.61 percentage points, between Gemini and Gemma.

## Omnibus statistical test

### Primary test

I fitted a saturated linear probability mean model to the 1,268 binary correctness outcomes:

`correct ~ 0 + model`

The four coefficients are exactly the four model accuracies. Covariance was estimated with the finite-sample-corrected **CR1 sandwich**, clustering every model response and every related item at the top-level clinical-cluster identifier. Equality of the four coefficients was tested jointly with three linear restrictions and an F reference distribution using the 200 clusters:

**Cluster-robust omnibus Wald F(3, 199) = 22.746, p = 1.053×10⁻¹².**

This directly tests whether the four A accuracies are equal on the clinically interpretable risk scale. It respects both the same-item pairing and dependence among questions belonging to the same clinical case because both are contained inside the same sandwich cluster.

### Why this test, rather than ANOVA or ordinary Cochran's Q?

- Correctness is Bernoulli (0/1), so normality of the raw endpoint is neither plausible nor required. A Shapiro–Wilk test on 0/1 values would merely rediscover that discreteness.
- Ordinary ANOVA assumes a continuous outcome with an unsuitable error structure.
- Cochran's Q is the conventional omnibus test for four matched binary measurements, but its ordinary form treats different item blocks as independent. Here, multiple questions can share one clinical case; using it naively would understate or otherwise misstate uncertainty.
- The saturated risk model makes no constant-variance assumption: CR1 covariance allows heteroskedastic Bernoulli outcomes and arbitrary dependence inside each of the 200 clinical clusters. Its inferential approximation instead requires independent top-level clusters and enough non-dominant clusters.

## Pairwise model comparisons

Risk differences are oriented as the earlier-listed model minus the later-listed model; positive values favour the earlier-listed model. The confidence intervals are unadjusted CR1 95% intervals. Raw p-values come from cluster-robust t tests with 199 denominator degrees of freedom; **Holm p** controls family-wise error across all six pairwise comparisons.

| Pair | Accuracy difference | CR1 95% CI | t(199) | Raw p | Holm p |
|---|---:|---:|---:|---:|---:|
| Gemini − GLM | **+4.73 pp** | +1.78 to +7.68 pp | 3.162 | 0.00181 | **0.00363** |
| Gemini − Qwen | **+9.46 pp** | +6.18 to +12.75 pp | 5.685 | 4.61×10⁻⁸ | **1.84×10⁻⁷** |
| Gemini − Gemma | **+18.61 pp** | +13.88 to +23.35 pp | 7.748 | 4.68×10⁻¹³ | **2.81×10⁻¹²** |
| GLM − Qwen | **+4.73 pp** | +1.01 to +8.45 pp | 2.509 | 0.01290 | **0.01290** |
| GLM − Gemma | **+13.88 pp** | +9.36 to +18.40 pp | 6.059 | 6.74×10⁻⁹ | **3.37×10⁻⁸** |
| Qwen − Gemma | **+9.15 pp** | +4.58 to +13.72 pp | 3.945 | 0.000110 | **0.000331** |

The smallest difference is about 4.7 percentage points. The widest uncertainty among those two closest comparisons is GLM versus Qwen (+1.01 to +8.45 pp), but its Holm-adjusted p-value remains below 0.05. These tests establish a difference on this item set; they do not establish clinical equivalence, general superiority outside this benchmark, or within-model reproducibility.

## Exact whole-cluster sensitivity analysis

For each pair, I independently aggregated the paired correctness difference inside each clinical cluster,

`D_g = sum_items(correct_model_1 − correct_model_2)`,

and convolved the exact distribution obtained by jointly changing `D_g` to `+D_g` or `−D_g` for every nonzero cluster. This retains all within-cluster dependence. It is exact conditional on independent clusters and whole-cluster model-label exchangeability under the sharp null; it is a sensitivity test, not a claim that the models were randomized.

| Pair | Exact cluster sign-flip p | Holm p across six |
|---|---:|---:|
| Gemini − GLM | 0.003319 | **0.006638** |
| Gemini − Qwen | 5.40×10⁻⁸ | **2.16×10⁻⁷** |
| Gemini − Gemma | 5.77×10⁻¹⁵ | **3.46×10⁻¹⁴** |
| GLM − Qwen | 0.01930 | **0.01930** |
| GLM − Gemma | 3.59×10⁻⁹ | **1.79×10⁻⁸** |
| Qwen − Gemma | 7.87×10⁻⁵ | **0.000236** |

All six conclusions agree with the CR1 analysis. The sign-flip check is useful here because it avoids relying on a normal model for individual 0/1 outcomes.

## Clinician-facing explanation

> **What this means for a clinical doctor.** On the same 317 original-format questions, Gemini answered about 98 in 100 correctly, GLM about 93, Qwen about 88, and Gemma about 79. The observed gaps were larger than we would reasonably attribute to which clinical cases happened to be sampled: even the two closest gaps were about five additional correct answers per 100 questions and remained statistically detectable after correcting for all six model comparisons. This is benchmark evidence, not a clinical-safety certification. Each question was run only once, the systems were not provider-pinned, and an apparently correct answer still requires clinical verification before use in patient care.

## Reproducible method

1. Load `paired_clean.json` and verify its SHA-256 above.
2. Keep only rows where `analysis_include` is true.
3. Pivot by `(question_id, model)` and retain questions containing all four model IDs. This drops only `b320`, leaving 317 questions and 200 clusters.
4. Build a four-column one-hot design matrix with no intercept and fit OLS to `A_correct`. The coefficients equal the four raw accuracies.
5. Apply CR1 covariance with `cluster` as the grouping variable and small-sample correction `G/(G−1) × (N−1)/(N−K)`.
6. Test equality of the four coefficients with three restrictions and report an F test with `(3, G−1) = (3, 199)` degrees of freedom.
7. For every pair, contrast the corresponding coefficients, calculate t inference with 199 degrees of freedom, and apply Holm's step-down correction to the six raw p-values.
8. For descriptive intervals, resample the 200 clinical clusters with replacement 200,000 times (seed `20260731`), preserving every item and model inside each sampled cluster and keeping repeated draws distinct.
9. For the exact sensitivity analysis, form integer `D_g` values as above and use integer convolution of every `±D_g` assignment; count `|sum D_g*| ≥ |sum D_g observed|`, then apply Holm across six tests.

Software used for the independent computation: Python 3.14.4, NumPy 2.5.1, SciPy 1.18.0, and statsmodels 0.14.6. No stale exploratory JSON was read.
