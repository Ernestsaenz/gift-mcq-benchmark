# Independent model comparison within Experiment B

**Workflow:** B-only model comparison  
**Date:** 2026-07-31  
**Scope:** condition B on the canonical v3 paired analysis population; no canonical report, code, or results file was edited  
**Canonical input:** `paired_clean.json`, SHA-256 `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187`

## Verdict

The four models do not have the same accuracy in condition B. A cluster-robust logistic GEE omnibus test on the 317 items observed for all four models gives **Wald chi-square(3) = 77.44, p = 1.08e-16**. Pairwise, Gemini is higher than all three other models; GLM and Qwen are not distinguishable; and both GLM and Qwen are higher than Gemma after Holm correction.

This is a comparison of benchmark accuracy under condition B. It is not evidence that any model is safe for autonomous clinical use, nor does it establish a universal model ranking outside this item bank and deployment configuration.

## 1. Population and denominators

The canonical v3 A/B table contains **1,271 analysed item-model pairs, 318 unique items, and 201 clinical-case clusters**. It deliberately retains the same analysis population used in the approved A-versus-B result.

One A-side response, `b320 x glm-5.2`, is absent. Consequently the canonical paired table contains 317 B observations for GLM and 318 for each other model. This workflow does not add the B-only `b320` result from outside the canonical paired export. The strict four-model omnibus analysis therefore uses the **317 items with all four model outcomes (1,268 observations, 200 clinical clusters)**. Pairwise analyses use every item shared by the two models being compared: 317 for comparisons involving GLM and 318 otherwise.

| model | B correct / analysed | B accuracy | descriptive rank |
|---|---:|---:|---:|
| Gemini 3.6 Flash | 284 / 318 | **89.31%** | 1 |
| GLM-5.2 | 237 / 317 | **74.76%** | 2 |
| Qwen 3.6 35B-A3B | 231 / 318 | **72.64%** | 3 |
| Gemma 4 26B-A4B-IT | 189 / 318 | **59.43%** | 4 |

The ranking in this table is descriptive. The tests below determine which observed gaps are distinguishable from sampling variation under the stated cluster assumptions.

## 2. Statistical test

### Primary omnibus test

I fit a population-averaged logistic generalized estimating equation,

`B_correct ~ model`,

to the 317 complete items. The working correlation was independence and the sandwich covariance was clustered by the 200 top-level clinical-case groups. Model was a four-level categorical predictor, with Gemini as the reference. The joint null hypothesis was that all three model coefficients equal zero.

- **Wald chi-square(3) = 77.4436**
- **p = 1.0846e-16**
- Conclusion: reject equal B accuracy across all four models.

The independence working correlation is not an assertion that scores within a clinical case are independent: the robust sandwich covariance allows arbitrary dependence within each clinical cluster. The inferential assumption is independence between top-level clinical clusters and adequate cluster-level asymptotics. There are 200 clusters in the complete-case analysis, although their sizes are unequal.

As cross-checks, the conventional item-paired Cochran Q test gives `Q(3) = 95.16, p = 1.71e-20`, but that p-value is not primary because it ignores higher-level clinical clustering. A 500,000-replicate clinical-cluster block permutation, applying one randomly selected four-model label permutation to every item within each cluster, produced zero statistics as large as observed (add-one Monte Carlo `p < 2.0e-06`). The latter supports the omnibus decision under a model-label-exchangeability null without relying on normal 0/1 outcomes.

### Pairwise estimands and tests

For each of the six model pairs I report:

1. the paired risk difference in percentage points, first model minus second;
2. a 95% percentile interval from 100,000 whole-clinical-cluster bootstrap replicates;
3. a marginal odds ratio and robust 95% CI from a two-model logistic GEE; and
4. a two-sided exact clinical-cluster sign-flip p-value, adjusted over all six pairwise tests by Holm's family-wise-error procedure.

The sign-flip test aggregates paired correctness differences within each clinical cluster and flips the sign of each nonzero cluster total. It therefore preserves all items inside a clinical case as a unit. Its null additionally requires cluster-level difference distributions to be sign-exchangeable. Dedicated pairwise GEE p-values, also Holm-adjusted, are given as a sensitivity check below the main table.

| comparison (first minus second) | paired n / clusters | accuracy difference, pp [cluster-bootstrap 95% CI] | marginal OR [robust 95% CI] | Holm p, exact cluster sign-flip |
|---|---:|---:|---:|---:|
| Gemini - GLM | 317 / 200 | **+14.51** [+10.00, +19.31] | 2.81 [1.99, 3.97] | 9.77e-08 |
| Gemini - Qwen | 318 / 201 | **+16.67** [+11.84, +21.67] | 3.15 [2.19, 4.52] | 2.59e-08 |
| Gemini - Gemma | 318 / 201 | **+29.87** [+23.60, +36.26] | 5.70 [3.87, 8.40] | 3.90e-14 |
| GLM - Qwen | 317 / 200 | **+2.21** [-3.09, +7.32] | 1.12 [0.86, 1.46] | **0.477** |
| GLM - Gemma | 317 / 200 | **+15.14** [+9.03, +21.23] | 2.01 [1.53, 2.63] | 7.30e-05 |
| Qwen - Gemma | 318 / 201 | **+13.21** [+7.21, +19.37] | 1.81 [1.39, 2.36] | 2.07e-04 |

Holm-adjusted pairwise GEE p-values, in the same row order, are `1.77e-08`, `3.00e-09`, `7.14e-18`, `0.399`, `1.38e-06`, and `2.03e-05`. Thus the substantive decision is identical under the sandwich-Wald and exact cluster sign-flip approaches: **only GLM versus Qwen remains unresolved**.

The odds ratios compare the odds of a correct answer, not probabilities. Because odds ratios can look large at high or low baseline accuracy, the percentage-point differences and their intervals are the primary magnitude summaries.

## 3. Clinician-facing explanation for insertion below the B section

> **For a clinical reader.** On this same set of digestive-system exam questions under Experiment B, Gemini answered about 89 of every 100 questions correctly, GLM about 75, Qwen about 73, and Gemma about 59. The statistical analysis accounts for the fact that some questions belong to the same clinical case. It supports Gemini outperforming each of the other models and supports both GLM and Qwen outperforming Gemma. The 2.2-point gap between GLM and Qwen is too uncertain to call a real difference: its plausible range runs from GLM being about 3 points worse to about 7 points better. These are examination results under one engineered answer format—not estimates of bedside safety, diagnostic accuracy, or patient benefit.

## 4. Normality and assumptions

No Shapiro-Wilk or other raw-score normality test is appropriate. Correctness is binary, so each observation is Bernoulli rather than normally distributed. Logistic GEE, exact cluster sign flips, and whole-cluster bootstrap intervals do not require normal 0/1 outcomes.

The relevant assumptions are instead:

- the top-level clinical clusters are independent sampling units;
- within-cluster dependence is retained by sandwich covariance and whole-cluster resampling;
- the logistic mean model is saturated for the four model-specific marginal accuracies;
- robust Wald inference relies on cluster-level asymptotics; and
- exact sign-flip inference relies on sign exchangeability of cluster-level paired differences.

The item bank is not a random sample of all clinical practice. Statistical uncertainty therefore quantifies variation under the analysed cluster structure, not external clinical generalisability.

## 5. Reproduction method

Run from `tier1_mcq/` with the locked analysis dependencies:

```bash
uv run --extra analysis python <reproduction-script>
```

The calculation used only rows satisfying `analysis_include == true` in `paired_clean.json`. The essential long-format construction was:

```python
rows = [r for r in json.load(open(
    "data/experiment-31-07-26/analysis/paired_clean.json"
)) if r["analysis_include"]]

df = pandas.DataFrame({
    "item": [r["question_id"] for r in rows],
    "cluster": [r["cluster"] for r in rows],
    "model": [model_labels[r["model"]] for r in rows],
    "correct": [r["B_correct"] for r in rows],
})
```

For the omnibus test, items with four model rows were retained and the model was fit as:

```python
fit = statsmodels.api.GEE.from_formula(
    "correct ~ C(model)",
    groups="cluster",
    data=complete_case_df,
    family=statsmodels.api.families.Binomial(),
    cov_struct=statsmodels.genmod.cov_struct.Independence(),
).fit()

R = numpy.zeros((3, 4))
R[:, 1:] = numpy.eye(3)
omnibus = fit.wald_test(R, scalar=True)
```

For each pair, item-level differences `d_i = correct_first - correct_second` were summed within clinical cluster. The observed risk difference was `sum_g D_g / sum_g n_g`. The bootstrap sampled all observed clinical clusters with replacement and recomputed that ratio; 100,000 replicates were used with deterministic pair-specific seeds derived from base seed `20260731`. The exact sign-flip distribution was calculated by integer convolution of `+abs(D_g)` and `-abs(D_g)` over nonzero cluster totals. Holm adjustment was applied monotonically to the six raw p-values.

## 6. Report-ready concise block

**Experiment B — comparison among models.** Accuracy differed across the four models in the strict common set of 317 items and 200 clinical clusters (cluster-robust logistic GEE Wald chi-square(3) = 77.44, p = 1.08e-16). In the canonical paired analysis population, accuracy was 89.31% for Gemini (284/318), 74.76% for GLM (237/317), 72.64% for Qwen (231/318), and 59.43% for Gemma (189/318). Holm-adjusted exact cluster comparisons supported Gemini over each other model and both GLM and Qwen over Gemma. GLM versus Qwen was unresolved: +2.21 percentage points, cluster-bootstrap 95% CI [-3.09, +7.32], adjusted p = 0.477.

> **For a clinical reader.** Gemini performed best on this examination task, while Gemma performed worst. GLM and Qwen were close enough that this study cannot reliably separate them. The test accounts for questions grouped within the same clinical case, but it does not translate directly into diagnostic safety or patient outcomes.
