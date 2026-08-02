# QA03 — primary OpenRouter A/B statistics

**Independent QA date:** 2026-07-31  
**Canonical input audited:** `paired_clean.json`, MD5 `0b25b95d082cf00900443d262c84427e`  
**Source cross-check:** `experiment.sqlite`, MD5 `1c5fcbb79c93f1a0554c3e8cea0be552`  
**Scope:** canonical v2 OpenRouter condition A versus B only. No canonical files were edited.

## Verdict

**Core scientific result: PASS. Final report as currently written: FAIL / major corrections required before delivery.**

The canonical v2 data show a large, consistently negative A-to-B accuracy change under every model and every cluster-aware check used here. That conclusion is secure. However, §2 of `REPORT.md` mixes the v2 sample declaration (318 items, 1,271 cells, 201 clusters) with several superseded v1 results (325 items, 1,299 cells, 208 clusters). Its pooled rates, four of five reported p-values, all bootstrap intervals, both logistic odds ratios, and the log-odds interaction p-value are not the canonical v2 values. The pooled table cell is also labelled “exact McNemar” even though the displayed value is a cluster-level sign-flip p-value, a different test.

The sentence “Models do not differ in robustness” is too strong. Evidence for model heterogeneity depends on the estimand and model: it is clear on the risk-difference scale, borderline in a marginal logistic model, and not detected by conditional logistic regression. Failure to reject an interaction is not evidence of equality. Use “heterogeneity is scale- and model-dependent” unless an equivalence margin is specified and tested.

## 1. Data integrity and denominators

I rebuilt the scored A/B intersection directly from the read-only SQLite database through the scored attempt (`scores -> parsed_answers -> provider_attempts`), applied the 22 declared item exclusions and the key-`a` exclusion, and compared every included outcome and selected letter to the JSON export.

- Database scored cells: A = 1,895; B = 1,692; A/B intersection = 1,691.
- Canonical analysis: **1,271 item×model pairs, 318 items, 201 clinical clusters**.
- The `(question_id, model)` key is unique; the database and JSON key sets are identical.
- Outcome/selected-letter mismatches between SQLite and JSON: **0**.
- Model denominators are 318, 318, 318, and **317 for glm-5.2**, because `b320 × glm-5.2` is absent.

The exact canonical v2 tables are:

| model | n | A correct | B correct | both right | A-only (`n10`) | B-only (`n01`) | both wrong |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 318 | 311 | 284 | 280 | 31 | 4 | 3 |
| glm-5.2 | 317 | 295 | 237 | 229 | 66 | 8 | 14 |
| qwen3.6-35b-a3b | 318 | 281 | 231 | 216 | 65 | 15 | 22 |
| gemma-4-26b-a4b-it | 318 | 251 | 189 | 171 | 80 | 18 | 49 |
| **cell-weighted pooled** | **1,271** | **1,138** | **941** | **896** | **242** | **45** | **88** |

## 2. Correct v2 descriptive and paired inference results

The risk difference is `B − A`; negative values mean condition B is worse. “Exact paired OR” is `n01/n10`, so values below 1 favour A. Its interval is the Clopper–Pearson interval for the discordant-direction probability transformed to odds. These exact p-values and OR intervals treat pairs as independent and therefore are secondary when multi-item clinical clusters are present.

| model | A | B | RD, B−A | 100k whole-cluster bootstrap 95% CI | exact McNemar p | exact paired OR B/A [95% CI] | exact clinical-cluster sign-flip p |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 97.799% | 89.308% | **−8.491 pp** | [−12.281, −5.018] | 3.46545e-06 | 0.1290 [0.0331, 0.3650] | 1.51005e-05 |
| glm-5.2 | 93.060% | 74.763% | **−18.297 pp** | [−23.333, −13.738] | 1.80774e-12 | 0.1212 [0.0502, 0.2531] | 5.27680e-11 |
| qwen3.6-35b-a3b | 88.365% | 72.642% | **−15.723 pp** | [−20.703, −10.756] | 1.41147e-08 | 0.2308 [0.1222, 0.4091] | 1.79581e-07 |
| gemma-4-26b-a4b-it | 78.931% | 59.434% | **−19.497 pp** | [−26.099, −12.813] | 1.66067e-10 | 0.2250 [0.1269, 0.3787] | 3.13718e-07 |
| **cell-weighted pooled** | **89.536%** | **74.036%** | **−15.500 pp** | **[−18.769, −12.372]** | 8.67992e-34* | 0.1860 [0.1321, 0.2565]* | **1.94715e-15** |

`*` The pooled ordinary McNemar calculation stacks four responses to the same item and ignores both item reuse across models and clinical clustering. It is a diagnostic, not the study-level primary p-value or CI.

Bootstrap details: 100,000 multinomial resamples of all 201 clinical clusters, seed 20260731; every resample carried all items and models within the selected cluster and recomputed the ratio estimator. No bootstrap RD was non-negative. Monte Carlo endpoints may move by a few hundredths of a percentage point under a different seed or 20,000 rather than 100,000 replicates.

The exact pooled cluster sign-flip distribution uses the 114 clusters with nonzero net discordance. Its null variance inflation relative to independent discordant cells is **3.774**, not the stale 3.75/4.47e-16 result. This test is exact conditional on independent clusters and joint A/B-label exchangeability within each cluster; it is not an “exact McNemar” test.

## 3. Logistic claims

I independently refit the long-format binary outcome (2,542 rows) by Fisher scoring and recomputed CR1 sandwich covariance over the 201 clinical clusters.

### Model-adjusted marginal logistic model

For `correct ~ condition_B + model`:

- `beta_B = −1.159341`, CR1 SE = 0.122669.
- **OR = 0.31369**, 95% CI **[0.24665, 0.39895]**, z = −9.451, p = **3.356e-21**.
- This is a **68.6% reduction in the odds**, which supports the rounded “about 69%” wording.

Thus the report's OR 0.309, CI 0.243–0.393, and p = 7.6e-22 are stale v1 values. Also call this a *model-adjusted logistic OR*; “marginal OR” alone is ambiguous because odds ratios are non-collapsible.

### Exact conditional logistic model stratified by item

Conditioning out the item intercept and including model main effects gave 193 informative item strata in 139 clinical clusters:

- `beta_B = −1.567113`, cluster-robust SE = 0.167684.
- **Within-item common OR = 0.20865**, 95% CI **[0.15020, 0.28983]**, p = **9.135e-21**.

The report's within-item OR 0.204 is stale v1. This common-effect estimate is a useful sensitivity analysis, not a replacement for per-model risk differences.

## 4. Model heterogeneity: current report overstates homogeneity

Canonical v2 results do not support the categorical header “Models do not differ in robustness.” They support the narrower statement that conclusions depend on scale/model:

- Risk-difference scale: cluster-bootstrap covariance Wald chi-square = 18.86, df = 3, **p = 0.000293**. The original within-item model-label permutation also remains significant after v2 cleaning, but its value is **p = 0.00270**, not 0.0011; that permutation does not preserve the higher clinical-cluster dependence.
- Conditional log-odds scale: interaction LRT **p = 0.2009**; clinical-cluster robust Wald **p = 0.1227**.
- Marginal log-odds scale: model-based LRT **p = 0.1485**, but clinical-cluster robust Wald **p = 0.0438**.

These are not contradictory: risk differences and odds ratios encode different effect homogeneity, and marginal and conditional ORs differ. They do mean the “no differences” conclusion is not stable enough to state as a finding.

For six v2 pairwise risk-difference contrasts, exact cluster sign-flips with Holm correction found:

- gemini vs glm: adjusted p = 0.00225;
- gemini vs gemma: adjusted p = 0.03394;
- gemini vs qwen: adjusted p = 0.07892;
- all three contrasts among glm/qwen/gemma: adjusted p = 1.0.

So even the pairwise sentence needs qualification: gemini differs from glm and gemma, but not qwen after Holm in v2. Non-significant interaction or pairwise tests do **not** establish equivalence.

## 5. Normality and defensible test selection

No raw-outcome normality test is applicable to the primary endpoint:

- `A_correct` and `B_correct` are Bernoulli variables; the paired change is supported only on `{-1, 0, +1}`. Shapiro–Wilk or a Q–Q plot on these values tests an impossible continuous-normal model and will mainly rediscover discreteness and the success rate.
- Exact McNemar, conditional logistic regression, cluster sign-flips, GEE/sandwich inference, and whole-cluster bootstrap CIs do **not** assume normally distributed outcomes.
- Logistic CR1 inference relies on asymptotic behaviour of cluster-level scores and independent top-level clusters, not normality of 0/1 observations. There are 201 nominal clusters but strong size imbalance; the v2 Kish effective cluster count is **50.9**, so leverage/whole-cluster sensitivity matters.
- A bootstrap percentile interval does not require a normal data distribution, but it does require the resampled clusters to be plausible independent sampling units.
- Normality becomes decision-relevant only for genuinely continuous secondary variables or a proposed t-test. Here completion tokens and latency are additionally measurement-confounded across arms, so they should not be promoted to inferential outcomes merely after a normality transform.

### Recommended primary analysis

1. Pre-specify each model's paired risk difference `B−A` as the most interpretable estimand. Report whole-clinical-cluster bootstrap CIs and a cluster-level sign-flip or wild-cluster p-value.
2. Use the model-adjusted logistic OR with cluster-robust covariance as a pooled/common-effect secondary summary; state the weighting and common-effect assumption.
3. Keep ordinary exact McNemar p-values and exact discordant-pair OR intervals as secondary checks only, because their iid-pair assumption ignores multi-item clusters. Apply Holm across the four per-model tests if they are treated as a family.
4. Test model heterogeneity with a pre-specified `condition × model` interaction and cluster-robust covariance. Report the estimand/scale. Do not convert a non-significant interaction into a claim of equality; equivalence requires a defensible margin and TOST or interval-based equivalence assessment.
5. Do not run or report a normality test on binary correctness.

## 6. Material discrepancies to correct in `REPORT.md`

| severity | current claim | canonical v2 correction |
|---|---|---|
| **Major** | Pooled 89.8%, 74.2%, −15.6 pp | 89.536%, 74.036%, −15.500 pp (round to 89.5%, 74.0%, −15.5 pp) |
| **Major** | Table CIs are over 201 clusters | Displayed CIs are v1/208-cluster outputs; replace with the v2 intervals in §2 |
| **Major** | Pooled “exact McNemar p = 4.5e-16” | 4.47e-16 is the stale v1 cluster sign-flip result, not McNemar. v2 cluster sign-flip p = 1.947e-15; ordinary stacked McNemar p = 8.680e-34 and is not primary |
| **Major** | OR 0.309 [0.243, 0.393], p 7.6e-22; within-item OR 0.204 | OR 0.31369 [0.24665, 0.39895], p 3.356e-21; within-item OR 0.20865 [0.15020, 0.28983] |
| **Major** | “Models do not differ”; conditional LRT p = 0.225 | v2 conditional LRT p = 0.2009 / cluster Wald p = 0.1227, while marginal cluster Wald p = 0.0438 and RD test p < 0.001; describe scale/model dependence |
| **Moderate** | Per-model exact p-values 1.0e-12, 5.3e-09, 6.1e-11 | glm 1.8077e-12; qwen 1.4115e-08; gemma 1.6607e-10 (gemini unchanged) |
| **Moderate** | Naive pooled exact p 6.3e-35 and DEFF 3.75 | v2 8.6799e-34 and DEFF 3.7735 |
| **Moderate** | Global RD permutation p = 0.0011 and gemini separates from all three | v2 item permutation p = 0.00270; Holm cluster contrast vs qwen p = 0.0789 |
| **Moderate** | Kish effective clusters 53 of 208 | v2 50.9 of 201 |

## 7. Reproduction commands and formulas used

Read-only artifact checks:

```bash
md5 data/experiment-31-07-26/analysis/paired_clean.json \
    data/experiment-31-07-26/experiment.sqlite
jq '[.[] | select(.analysis_include == true)] | length' \
    data/experiment-31-07-26/analysis/paired_clean.json
```

Direct count and McNemar recomputation used this core (executed from `tier1_mcq/`):

```python
import json
from collections import Counter
from scipy.stats import binomtest

rows = [r for r in json.load(open("data/experiment-31-07-26/analysis/paired_clean.json"))
        if r["analysis_include"]]
for model in sorted({r["model"] for r in rows}) + [None]:
    x = rows if model is None else [r for r in rows if r["model"] == model]
    tab = Counter((r["A_correct"], r["B_correct"]) for r in x)
    n10, n01 = tab[(1, 0)], tab[(0, 1)]
    print(model, len(x), sum(r["A_correct"] for r in x),
          sum(r["B_correct"] for r in x), n10, n01,
          binomtest(n01, n10 + n01, 0.5).pvalue)
```

The exact cluster sign-flip distribution was obtained by integer convolution of the clinical-cluster totals
`D_g = sum(A_correct − B_correct)`: starting at mass `{0:1}`, replace every mass at `s` by equal counts at `s−|D_g|` and `s+|D_g|`, then sum exact counts with `|S| >= |S_observed|`. The bootstrap resampled the 201 cluster sufficient-statistic vectors with replacement and recomputed each ratio in every replicate.

Secondary implementation cross-checks (their top observed sections read the live v2 file; embedded v1 “CLAIM” constants should be ignored):

```bash
python data/experiment-31-07-26/analysis/prim_refute_mcnemar_indep.py
python data/experiment-31-07-26/analysis/prim_ref_marginal_irls.py
```

All substantive signs and the main practical conclusion survived. The corrections are versioning, test-labelling, exact numerical reporting, and restraint about between-model homogeneity—not a reversal of the A/B finding.
