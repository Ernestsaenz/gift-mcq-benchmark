# QA06 — GIFT versus OpenRouter condition-A and partial-coverage audit

**Independent QA date:** 2026-07-31  
**Scope:** GIFT versus OpenRouter on condition A; canonical v2 exclusions; execution coverage,
complete-case paired accuracy, clinical-cluster inference, model heterogeneity, coverage selection,
post-stratification sensitivity, and Manski bounds. GIFT condition B did not run. Canonical data,
scripts, and result files were not edited.

Pinned inputs:

- `../experiment.sqlite`: SHA-256
  `dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748`
- `cross_arm_A.json`: SHA-256
  `987c632976260d4614056afcc9210fcd4902d322fcfe28b480ebc2e6216c8120`
- `gift_coverage.json`: SHA-256
  `3291caae151082f7be97c7a256e81e63da74052c5ce1b0d5b636e21dbbc942c9`
- `dataset_meta.json`: SHA-256
  `2ff9970b0b3a5362eabe829a9f95dc4dc5fa7d1b9be576eea48f523982beecba`

## Verdict

**Observed common-subset result: PASS. Current cross-arm report section: FAIL / major v2 and
estimand corrections required.**

The database and canonical v2 JSON agree cell for cell. On the 306 analysis-eligible items for
which GIFT produced a score under all four models, GIFT has an equal-weight, fixed-four-model
accuracy advantage of **+1.8791 percentage points**. A whole-clinical-cluster bootstrap gives a
95% percentile interval of **[+0.4448, +3.3514] pp**; an exact whole-cluster sign-flip gives
**p=0.020564**. Thus the observed-subset average is not an iid-cell artifact.

That average is not a generic “retrieval effect.” Effects reverse sign across models and are
strongly heterogeneous on the risk-difference scale (clinical-cluster CR1 Wald
**F(3,177)=7.0757, p=0.0001616**). It is defensible only as a secondary descriptive average over
these four fixed models and this selected item subset. Per-model results must remain primary.

The final-report table combines a 306-item v2 label with several 311-item v1 rates and counts.
The “83% complete” statement also conflates run progress with scored completion: GIFT A reached
82.5% of planned cells, scored only 73.0%, and had all-four-model scores for only 67.3% of items.
The full 452-item v2 target is not identified. Using every available partial GIFT result, its
strict binary-outcome Manski bound is **[-21.4602, +5.4204] pp**, so no full-target sign claim is
assumption-free.

| component | verdict | audit result |
|---|---|---|
| SQLite-to-JSON correctness and v2 filtering | **PASS** | 1,224/1,224 included cells and every binary outcome agree |
| Per-model denominators/rates in `REPORT.md` | **FAIL** | report mixes v1 results with the v2 `n=306` declaration |
| Ordinary exact McNemar and Holm conclusions | **PASS with corrected values** | gemma and glm survive; qwen's v2 exact p is 1.0 |
| Clinical-cluster inference | **PASS** | bootstrap CI, exact sign-flip, and CR1 inference support the selected-subset average |
| Universal/common provider effect | **FAIL** | effects are sign-reversing and heterogeneous; models are fixed, not exchangeable draws |
| Execution/completion description | **FAIL** | 82.54% attempted, 73.00% scored, 67.30% all-four; not “83% complete” |
| Sequential-prefix warning | **PASS** | directly verified from call creation order and score coverage |
| Full-target reweighting | **Sensitivity only** | estimates depend on an untestable transport assumption and analysis choice |
| Manski bound | **PASS after v2 correction** | report's `[-21.8,+5.2]` is v1; canonical strict bound is `[-21.46,+5.42]` pp |
| GIFT condition B | **PASS (absence correctly stated)** | 1,692 planned; 0 logical calls, attempts, parses, or scores |

## 1. Source reconciliation and canonical population

I rebuilt scored cells from the read-only database using explicit experiment names and the
authoritative scored-parse link:

```text
scores -> parsed_answers.id = scores.parsed_answer_id
       -> provider_attempts.id = parsed_answers.provider_attempt_id
       -> logical_calls -> questions -> experiments
```

The four models are gemini-3.6-flash, gemma-4-26b-a4b-it, qwen3.6-35b-a3b, and glm-5.2.
Independent database reconstruction found **319** items scored by GIFT for all four models,
identical to `gift_coverage.json`. `cross_arm_A.json` contains exactly those 319 items × four
models = 1,276 rows.

Canonical v2 has 22 post-ingestion analysis exclusions. Thirteen occur in the GIFT all-four set:

`b205 b213 b238 b293 b331 b341 b343 b361 b378 b391 b396 b401 b407`

Removing their 52 rows leaves **306 items, 1,224 item×model cells, and 178 clinical clusters**.
The included item set is identical under every model; `(question_id, model)` is unique; all
correctness fields are binary. Direct comparison of the 1,224 JSON pairs with GIFT-A and
OpenRouter-A scores in SQLite found **zero key differences and zero outcome differences**.

## 2. Estimands must remain separate

The data support several different quantities, none interchangeable:

1. **Model-specific complete-case RD:** for a named model, mean
   `GIFT_correct - OpenRouter_correct` on the same 306 v2-eligible all-four-covered items.
2. **Fixed-four-model complete-case average:** the equal-weight mean of those four RDs. Because
   each model has `n=306`, this equals the stacked cell-weighted RD. It describes these four
   named models only.
3. **Per-model available-case RD:** uses every scored GIFT cell for that model. Denominators and
   item sets differ by model, so these values cannot be used for a clean heterogeneity comparison.
4. **Full v2 condition-A target:** 452 eligible items × four fixed models. GIFT outcomes are
   missing for many target cells, so this finite-population RD is only bounded without an
   extrapolation assumption.
5. **GIFT condition-A versus condition-B effect:** nonexistent in these data because GIFT B never
   ran. Nothing in the OpenRouter A/B result identifies it.

All comparisons are between the deployed GIFT and OpenRouter pipelines. They do not isolate
retrieval from provider stack, routing/model snapshot, serving-time, or other pipeline differences.
With one temperature-zero run per cell, uncertainty is over items/clusters, not repeated model
generation or deployment time.

## 3. Correct canonical v2 paired results

Here `b` is GIFT correct/OpenRouter wrong and `c` is GIFT wrong/OpenRouter correct. Ordinary exact
p-values are two-sided `Binomial(b+c, 0.5)` tests. Holm adjustment is across the four per-model
tests. The cluster p-value instead jointly flips the arm labels for every item and model within a
clinical cluster, then uses exact integer convolution; its Holm column adjusts the four
per-model cluster tests.

| model | n | GIFT correct | OpenRouter correct | GIFT | OpenRouter | RD (pp) | b/c | exact p | Holm p | exact cluster p | cluster-Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 306 | 298 | 301 | 97.3856% | 98.3660% | **-0.9804** | 0/3 | 0.250000 | 0.500000 | 0.250000 | 0.500000 |
| gemma-4-26b-a4b-it | 306 | 270 | 253 | 88.2353% | 82.6797% | **+5.5556** | 24/7 | 0.00332689 | 0.0133076 | 0.00699854 | 0.0279942 |
| qwen3.6-35b-a3b | 306 | 281 | 282 | 91.8301% | 92.1569% | **-0.3268** | 11/12 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| glm-5.2 | 306 | 295 | 285 | 96.4052% | 93.1373% | **+3.2680** | 11/1 | 0.00634766 | 0.0190430 | 0.0107422 | 0.0322266 |
| **fixed-four pooled** | **1,224** | **1,144** | **1,121** | **93.4641%** | **91.5850%** | **+1.8791** | **46/23** | **0.00762052*** | — | **0.0205639** | — |

`*` The pooled ordinary exact test treats 69 discordant item×model cells as independent. It
ignores both reuse of each item across four models and multi-item clinical vignettes, so it is a
calculation check, not the preferred pooled inference. Its uncorrected and continuity-corrected
McNemar statistics are respectively 7.6667 (`p=0.0056250`) and 7.0145 (`p=0.0080853`).

The current report's Holm decisions remain directionally correct: gemma and glm survive either
the ordinary exact or whole-cluster family. Numerically, however, its gemma/glm/qwen rates and
qwen `11/13` discordance are v1. Canonical qwen is `11/12` and has exact `p=1.0`.

## 4. Clinical-cluster uncertainty and leverage

I drew 100,000 multinomial whole-cluster resamples of all 178 clusters, seed 20260731. A draw
retained every item and all four model rows in the selected cluster; repeated cluster draws were
counted repeatedly. Each replicate recomputed the ratio estimator. Intervals are linear/type-7
2.5th and 97.5th percentiles.

| model | RD (pp) | cluster-bootstrap SE (pp) | 95% percentile CI (pp) |
|---|---:|---:|---:|
| gemini | -0.9804 | 0.6133 | [-2.4291, 0.0000] |
| gemma | +5.5556 | 1.8470 | [+1.9663, +9.2664] |
| qwen | -0.3268 | 1.5475 | [-3.4146, +2.7027] |
| glm | +3.2680 | 1.1836 | [+1.1407, +5.7851] |
| **fixed-four pooled** | **+1.8791** | **0.7362** | **[+0.4448, +3.3514]** |

The ordinary empirical bootstrap is an interval estimator, not a null randomization test. In
particular, gemini has no GIFT-favouring discordance, so its bootstrap cannot generate a positive
RD; the endpoint at zero must not be converted into a tiny p-value. Its valid exact paired and
whole-cluster sign-flip p-values are both 0.25.

As an asymptotic cross-check, an intercept-only RD model with CR1 covariance over 178 clinical
clusters gives pooled SE **0.7150 pp**, `t(177)=2.6279`, **p=0.009345**, and 95% CI
**[+0.4680,+3.2902] pp**. The exact cluster sign-flip (`p=0.020564`) is the more conservative
reported null sensitivity. The methods differ: CR1 is sampling-asymptotic, while sign-flipping
requires joint within-cluster arm-label exchangeability under the sharp null.

Cluster leverage is severe. Of 178 nominal clusters, 171 are singleton items and seven contain
6–23 items each. Those seven contain **135/306 = 44.12%** of analysed items; the item-size Kish
effective cluster count is only **31.13**. Dropping all seven is a deliberately severe, post-hoc
leverage diagnostic, not a recommended exclusion. It leaves 171 items/684 cells and a similar RD
of **+2.0468 pp**, but its 100,000-resample CI is **[-0.1462,+4.2398]**, exact cluster sign-flip
`p=0.09258`, and CR1 `p=0.07058`. Thus point magnitude is stable while conventional significance
is sensitive to the large case clusters. The report's “43%, p=0.105” values are stale v1 values.

## 5. Heterogeneity and whether pooling is defensible

The complete-case RDs span **6.5359 pp**, from gemini -0.9804 to gemma +5.5556. A model-indicator
RD regression with the full cross-model clinical-cluster sandwich covariance rejects equality:

```text
CR1 Wald chi-square = 21.2270
F(3,177) = 7.07568
p = 0.00016156
```

The gemma-minus-qwen RD contrast is **+5.8824 pp**, CR1 95% CI
**[+1.6831,+10.0816]**, `p=0.006306`.

For comparison with the report's older conditional-discordance calculation, canonical v2 has
common discordant-direction estimate `46/69 = 0.6667` and Pearson
**Q=14.6618**. Its asymptotic chi-square(3) p is **0.0021297**; exact enumeration under independent
`Binomial(n_i,46/69)` plug-in samples gives **p=0.0039580**. The report's `Q=15.43, p=0.0027`
comes from v1. This conditional test also ignores clinical and cross-model dependence, so the CR1
RD-scale test is the primary heterogeneity check.

Pooling is therefore defensible only if labelled as the **equal-weight mean over these four fixed
models on the 306-item common subset**. It is not a common-effect estimate, a random-model
meta-analytic effect, or evidence that a future/unsampled model benefits. Because two models have
positive and two negative point estimates, the pooled value must not replace the per-model table.

## 6. Planned, reached, attempted, parsed, scored, and all-four coverage

Counts below are distinct planned item×model cells. “Logical created” is scheduler progress;
“provider attempted” means at least one provider-attempt row; “parsed” means any parse row exists;
and “scored” means an authoritative score exists.

| GIFT-A model | planned | logical created | provider attempted | any parse row | scored |
|---|---:|---:|---:|---:|---:|
| gemini | 474 | 392 | 392 | 355 | 355 |
| gemma | 474 | 391 | 391 | 355 | 355 |
| qwen | 474 | 391 | 391 | 351 | 351 |
| glm | 474 | 392 | 391 | 325 | 323 |
| **total** | **1,896** | **1,566 (82.595%)** | **1,565 (82.542%)** | **1,386 (73.101%)** | **1,384 (72.996%)** |

The 1,565 attempted cells generated 1,582 attempt records because of retries. The 1,896 planned
cells partition into 1,384 scored, 181 attempted-but-unscored, one logical cell with no provider
attempt, and 330 never-created cells. Terminal unscored states are 96 rate-limited, 83 server
errors, two parsed-but-unscored responses, and one no-attempt cell.

Raw item coverage by number of scored GIFT models is:

| scored models on item | 0 | 1 | 2 | 3 | 4 |
|---|---:|---:|---:|---:|---:|
| all 474 A items | 118 | 1 | 1 | 35 | **319** |
| 452 v2-eligible items | 112 | 1 | 1 | 32 | **306** |

Thus all-four coverage is **319/474 = 67.300%** before v2 analysis exclusions and
**306/452 = 67.699%** afterward. The all-four raw cells are 1,276, of which 1,224 are v2
eligible. Calling the arm “83% complete” is incorrect: approximately 83% describes scheduler or
attempt reach, 73.0% describes scored-cell completion, and 67.3% is the balanced all-four item
coverage used for cross-arm analysis.

For comparison, OpenRouter A has 1,896 created/attempted cells and 1,895 scores (99.947%); only
`b320 × glm` is unscored. GIFT B has **0/1,692** cells at every execution stage.

## 7. Sequential-prefix selection and observed difficulty

Call creation is exactly sequential in dataset order. Every model has logical calls for the first
391 dataset rows, through `b416`; gemini and glm alone also have a logical call for position 392,
`b417`. The last all-four-scored item is `b416` at position 391. Among positions 1–391, 319 items
are all-four scored and 72 are incomplete gaps; the remaining 83 dataset positions occur after
the last all-four-scored item. This directly verifies a prefix-with-gaps mechanism, not random
coverage.

OpenRouter accuracy provides an observed difficulty diagnostic:

| item universe | covered items/cells | OR correct | covered OR accuracy | uncovered items/cells | OR correct | uncovered OR accuracy | gap |
|---|---:|---:|---:|---:|---:|---:|---:|
| all dataset-A items | 319 / 1,276 | 1,162 | 91.0658% | 155 / 619 | 513 | 82.8756% | **+8.1902 pp** |
| canonical v2 eligible | 306 / 1,224 | 1,121 | 91.5850% | 146 / 583 | 486 | 83.3619% | **+8.2230 pp** |

The uncovered v2 denominator is 583 rather than 584 because `b320 × glm` lacks an OpenRouter
score. Region coverage is also skewed: before v2 analysis exclusions, Illes Balears contributes
129 covered versus 30 uncovered items, while Navarra contributes 14 versus 20.

This **proves selection on observed item difficulty**, but does not by itself quantify bias in a
within-item provider RD. Bias requires the provider RD to vary with difficulty/order. That effect
modification is only partly observable on the covered portion, and the deterministic tail leaves
no design-based positivity for the unobserved outcomes.

## 8. Partial observations, reweighting, and Manski bounds

The full canonical condition-A target contains 452 eligible items × four models = 1,808 cells.
OpenRouter is observed on 1,807 of them. Conditional on those 1,807 cells:

- balanced all-four paired cells: **1,224**, net GIFT-minus-OpenRouter correct = **+23**;
- additional partial GIFT cells outside the balanced set: **99**, net difference = **+5**
  (**+5.0505 pp**);
- all observed GIFT cells: **1,323**, net difference = **+28** (**+2.1164 pp** available-case);
- GIFT-unobserved cells: **484**.

The available-case estimate is not a substitute for the complete-case estimand: model
denominators are gemini 339, gemma 339, qwen 335, and glm 310, with different item sets. Their RDs
are respectively -0.2950, +4.7198, +0.8955, and +3.2258 pp.

### Reweighting sensitivity

I reproduced post-stratification directly from SQLite, defining leave-one-model-out OpenRouter
difficulty `k` as the number of the other three OpenRouter models correct on the item. This avoids
putting a model's own OpenRouter outcome into its own difficulty stratum. “Hard/easy” means
`k<=2` versus `k=3`.

| transport calculation over the 1,807 OR-observed target cells | RD |
|---|---:|
| complete-case RD, no extrapolation | +1.8791 pp |
| impute all non-complete cells from complete cases, pooled hard/easy | +2.0622 pp |
| same, model × hard/easy | +2.1088 pp |
| retain the 99 partial observations; impute 484 missing from complete cases, pooled hard/easy | **+2.1665 pp** |
| same, model × hard/easy | **+2.2308 pp** |
| model × four-level `k` (sparse), complete-case training / all-observed training | +2.2744 / +2.3383 pp |

The report's `+2.06 pp` is an underspecified v1 result. A number rounding to +2.06 can also be
obtained from the canonical complete-case-only pooled hard/easy variant, but the direct canonical
analogue that retains the 99 observed partial cells is +2.1665 pp. Reasonable transparent variants
span roughly **+2.05 to +2.34 pp**. The model×`k` version has training strata as small as two
cells; pooled variants conflict with the observed model heterogeneity.

These are outcome-model transport sensitivities, not design-based corrections. They require the
unobserved GIFT RD to be transportable from covered to uncovered cells conditional on the chosen
difficulty/model strata. A sequential stop can still depend on order, load, region, or latent
difficulty within strata. No reweighted point estimate identifies the full target without that
assumption.

### Assumption-free binary-outcome bounds

Over the 1,807 cells with an OpenRouter score, OpenRouter has 1,607 correct and GIFT has 1,220
correct among its observed cells. Setting every one of the 484 missing GIFT outcomes first to
wrong and then to correct gives:

```text
OR-observed target Manski RD = [-21.4167, +5.3680] pp
```

For the strict 1,808-cell target, the one cell missing from both providers can contribute anywhere
from -1 to +1. The bound is therefore:

```text
strict 452-item × four-model Manski RD = [-21.4602, +5.4204] pp
```

These bounds use all 99 partial GIFT observations and only binary-outcome support; they are
reproducible and sign-indeterminate. The current report's `[-21.8,+5.2] pp` is the v1
460-item/1,839-OR-cell calculation. After the +28 observed net advantage, the remaining 484
unseen cells would need an average RD of **-5.7851 pp** to make the OR-observed full-target RD
exactly zero; this tipping value is a sensitivity statement, not a probability.

## 9. Required claim boundaries and report corrections

1. Replace “GIFT completed 83%” with all three quantities: **82.54% attempted cells, 73.00%
   scored cells, 67.30% all-four item coverage**.
2. Replace the cross-arm table with the canonical values in section 3. In particular, correct
   gemma, glm, and qwen rates and qwen `b/c=11/12`, exact `p=1.0`.
3. Label `p=0.0076205` as a stacked-cell exact McNemar diagnostic. Use the exact clinical-cluster
   sign-flip `p=0.0205639` and cluster-bootstrap CI for pooled dependence-aware inference.
4. Replace stale heterogeneity `Q=15.43, p=0.0027` with a named method. The preferred RD-scale
   result is **F(3,177)=7.0757, p=0.0001616**; the analogous independent-discordant calculation is
   **Q=14.6618**, plug-in exact-enumeration `p=0.0039580`.
5. Keep the pooled value secondary and explicitly define it as an equal-weight average over four
   fixed models. Do not state a universal GIFT advantage or replace sign-reversing per-model RDs.
6. Keep the raw 91.1% versus 82.9% difficulty warning; add the canonical v2 comparison of 91.585%
   versus 83.362%. Do not say the 8.2 pp gap itself equals RD bias.
7. Treat all reweighting as model-dependent sensitivity. If a point is retained, state the exact
   strata, whether partial observations were used, target denominator, and transport assumption.
8. Replace the v1 Manski bound with **[-21.46,+5.42] pp** for the strict canonical target. Any
   full-target point claim is extrapolation.
9. State that GIFT B never ran and that this analysis cannot estimate a provider-by-condition
   interaction or GIFT's A-to-B robustness.
10. Describe results as differences between the two deployed pipelines on one run per cell, not
    as the isolated causal effect of retrieval or as evidence about arbitrary future models.

## 10. Reproduction notes

- Experiment names were matched exactly: `expA_gift_310726` and `expA_or_310726`; no `LIKE`
  wildcard was used.
- The v2 exclusion set was read from `dataset_meta.json`; only the 13 covered defect IDs remove
  cross-arm rows.
- Exact McNemar values were independently checked with integer binomial sums and
  `scipy.stats.binomtest`.
- Holm adjusted values use the monotone step-down rule over the four named models.
- Exact clinical-cluster sign-flips convolved integer cluster totals
  `D_g=sum(GIFT_correct-OpenRouter_correct)` and summed both tails at least as extreme as the
  observed absolute total.
- Bootstrap multiplicities were represented as
  `Multinomial(K;1/K,...,1/K)`, algebraically identical to drawing K labelled clusters with
  replacement; no duplicate draw was collapsed.
- The heterogeneity model used four model indicators and CR1 covariance over the same 178
  clinical clusters, including cross-model score covariance within cluster.
- Manski calculations were direct finite-population arithmetic and used every observed partial
  GIFT cell. No missing-at-random assumption enters the bounds.

Latency, token cost, rescue/breakage decomposition, and operational wall-clock claims were not
re-audited here; they require separate measurement and causal definitions and should not be
treated as validated by this accuracy/coverage audit.
