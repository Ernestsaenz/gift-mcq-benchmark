# Independent statistical review — requested model-group comparisons

**Workflow:** fixed-model group comparisons  
**Canonical input:** `../paired_clean.json`, export v3  
**Input SHA-256:** `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187`  
**Analysis population:** the same 317 questions answered by all four models, comprising 1,268 model–item cells in 200 clinical clusters  
**Primary multiplicity family:** six requested group contrasts  
**Canonical report or analysis code changed:** none

## Executive verdict

Using the group labels supplied for this analysis:

- **Declared large models:** Gemini 3.6 Flash and GLM-5.2
- **Declared small models:** Qwen 3.6 35B-A3B and Gemma 4 26B-A4B-IT
- **Declared open-model group:** GLM-5.2, Qwen 3.6 35B-A3B, and Gemma 4 26B-A4B-IT
- **Proprietary endpoint:** Gemini 3.6 Flash

the large pair had higher mean keyed-answer accuracy than the small pair in both Experiment A (**95.43% vs 83.75%; +11.67 percentage points**) and Experiment B (**82.02% vs 66.09%; +15.93 points**). Both contrasts remained significant after Holm correction. The large pair lost 13.41 points from A to B and the small pair lost 17.67 points. Their **4.26-point difference in loss was not statistically resolved**: whole-cluster bootstrap 95% CI −0.38 to +8.56 points, exact cluster sign-flip p = .0925, Holm p = .0925.

Gemini had higher keyed-answer accuracy than the arithmetic mean of the three declared open models in A (**97.79% vs 86.86%; +10.94 points**) and B (**89.27% vs 68.98%; +20.29 points**). Gemini lost 8.52 points from A to B, compared with 17.88 points for the open-model average. The corresponding **difference in loss was +9.36 points in Gemini's favour**, 95% CI +4.91 to +13.66, exact cluster sign-flip p = .000161, Holm p = .000321.

These are valid conditional comparisons of the **four named deployed configurations over the sampled clinical-question clusters**. They are not estimates for populations of large, small, open, or proprietary models. In particular, the proprietary group contains one endpoint, so “proprietary versus open” is mathematically **Gemini versus the mean of GLM, Qwen, and Gemma**; model ownership is fully confounded with Gemini's individual identity.

## Design and estimands

The canonical included table contains 318 questions, but GLM has no recovered result for `b320`. Every group comparison therefore uses the common 317-question panel and excludes `b320` from all four models. No missing result is imputed or scored as wrong. Every question contributes equally, and every named model receives equal weight within its declared group.

For each question, condition, and group, group accuracy is the arithmetic mean of the member models' binary correctness indicators. The reported difference is:

`mean accuracy of first group − mean accuracy of second group`.

The A→B interaction is:

`(B − A change in first group) − (B − A change in second group)`.

A positive interaction therefore means that the first group lost fewer percentage points from A to B. This difference-in-differences preserves the same item, condition, and model structure; it is not obtained by comparing whether two separate p-values are significant.

## Member-model results on the common panel

| Model | Supplied size group | Supplied access group | A correct / 317 | A accuracy | B correct / 317 | B accuracy | Change, B−A |
|---|---|---|---:|---:|---:|---:|---:|
| Gemini 3.6 Flash | large | proprietary | 310 | 97.79% | 283 | 89.27% | −8.52 pp |
| GLM-5.2 | large | open model | 295 | 93.06% | 237 | 74.76% | −18.30 pp |
| Qwen 3.6 35B-A3B | small | open model | 280 | 88.33% | 230 | 72.56% | −15.77 pp |
| Gemma 4 26B-A4B-IT | small | open model | 251 | 79.18% | 189 | 59.62% | −19.56 pp |

“Large,” “small,” and “open model” are treated here as supplied analytical labels, not as independently audited parameter-count or software-licensing determinations.

## Comparison 1 — declared large versus small models

Whole-cluster percentile intervals use 100,000 bootstrap replicates and retain all related items, models, and conditions whenever a clinical cluster is drawn.

| Estimand | Declared large models | Declared small models | Difference, large−small | Unadjusted 95% CI for difference | Exact cluster sign-flip p | Holm p across primary six |
|---|---:|---:|---:|---:|---:|---:|
| Experiment A accuracy | 95.43% (93.37–97.12) | 83.75% (79.72–87.08) | **+11.67 pp** | +8.81 to +14.98 | 1.66×10⁻¹³ | **6.65×10⁻¹³** |
| Experiment B accuracy | 82.02% (78.06–85.28) | 66.09% (61.07–70.58) | **+15.93 pp** | +11.80 to +20.18 | 1.88×10⁻¹⁰ | **5.65×10⁻¹⁰** |
| A→B change | −13.41 pp (−17.05 to −10.19) | −17.67 pp (−21.98 to −13.30) | **+4.26 pp** | −0.38 to +8.56 | .0925 | **.0925** |

The two size groups differ clearly in their **accuracy levels** within A and within B. The data do not establish that the declared large group is more resistant to the A→B manipulation: the observed 4.26-point advantage in retained accuracy is compatible with zero after clinical-cluster uncertainty is propagated.

### Explanation for a clinical doctor

> On these same 317 benchmark questions, the two declared large systems averaged about 95 correct answers per 100 in A, compared with 84 per 100 for the two declared small systems. In B, the corresponding averages were about 82 versus 66 per 100. Those level differences are unlikely to be explained only by which clinical question clusters happened to be sampled. However, both groups deteriorated in B, and the study does **not** show a reliable difference in the amount of deterioration: roughly 13 fewer correct answers per 100 for the large pair versus 18 fewer for the small pair, with an uncertain between-group difference. This is keyed-answer agreement on an MCQ benchmark, not patient-level diagnostic performance or proof that larger models are safer.

## Comparison 2 — proprietary Gemini versus the declared open-model group

| Estimand | Proprietary endpoint: Gemini | Mean of GLM, Qwen, and Gemma | Difference, proprietary−open mean | Unadjusted 95% CI for difference | Exact cluster sign-flip p | Holm p across primary six |
|---|---:|---:|---:|---:|---:|---:|
| Experiment A accuracy | 97.79% (95.93–99.27) | 86.86% (83.51–89.59) | **+10.94 pp** | +8.36 to +14.03 | 1.37×10⁻¹⁴ | **6.83×10⁻¹⁴** |
| Experiment B accuracy | 89.27% (85.41–92.57) | 68.98% (64.48–72.94) | **+20.29 pp** | +16.16 to +24.47 | 2.85×10⁻¹⁷ | **1.71×10⁻¹⁶** |
| A→B change | −8.52 pp (−12.33 to −5.05) | −17.88 pp (−21.69 to −14.19) | **+9.36 pp** | +4.91 to +13.66 | .000161 | **.000321** |

The observed proprietary–open-average gap nearly doubled from A to B, and the A→B interaction remains statistically detectable after correction across all six requested group tests. This statement must not be shortened to “proprietary models outperform open models”: the analysis contains one proprietary endpoint and three heterogeneous open endpoints, with no model-level replication inside the proprietary category.

### Explanation for a clinical doctor

> Gemini produced about 98 keyed-correct answers per 100 in A and 89 per 100 in B. Averaged equally, the three declared open models produced about 87 per 100 in A and 69 per 100 in B. Gemini therefore lost about 9 points while the open-model average lost about 18; the estimated 9-point difference in deterioration remained after accounting for related clinical question clusters and multiple testing. The result describes these four named systems only. It does not demonstrate that proprietary development causes better performance, just as a comparison of one proprietary drug with three different generics would not by itself identify “proprietary status” as the causal ingredient.

## Additional comparisons worth reporting

The requested grouping contrasts ownership, size, and individual model identity at the same time. Two exploratory restricted comparisons partially decompose those factors. They are useful context, but they still do not create model-level replication. Holm correction below is applied separately across these six exploratory contrasts.

### Ownership contrast within the declared large group: Gemini versus GLM

| Estimand | Gemini−GLM difference | Unadjusted whole-cluster 95% CI | Exact cluster sign-flip p | Holm p across exploratory six |
|---|---:|---:|---:|---:|
| Experiment A | **+4.73 pp** | +1.91 to +7.82 | .00332 | **.00664** |
| Experiment B | **+14.51 pp** | +10.03 to +19.27 | 2.44×10⁻⁸ | **1.47×10⁻⁷** |
| Difference in A→B change | **+9.78 pp** | +4.81 to +14.97 | .000375 | **.00150** |

This comparison holds the supplied size category approximately constant, but it remains a comparison of exactly two models. It shows that the proprietary–open-average interaction is not produced only by including the two declared small models in the open group: Gemini also lost 9.78 points less than GLM.

### Size contrast within the declared open-model group: GLM versus mean of Qwen and Gemma

| Estimand | GLM−small-open mean difference | Unadjusted whole-cluster 95% CI | Exact cluster sign-flip p | Holm p across exploratory six |
|---|---:|---:|---:|---:|
| Experiment A | **+9.31 pp** | +6.01 to +12.90 | 2.11×10⁻⁷ | **1.06×10⁻⁶** |
| Experiment B | **+8.68 pp** | +3.86 to +13.41 | .00140 | **.00419** |
| Difference in A→B change | **−0.63 pp** | −6.20 to +4.40 | .859 | **.859** |

Within the three declared open models, the declared large model GLM has higher accuracy than the two-model small-open average in both conditions. There is no evidence here that it loses less accuracy from A to B. This decomposition reinforces the distinction between **overall accuracy level** and **resistance to the manipulation**.

## Statistical tests and assumptions

### Primary inference

For each contrast, an item-level paired difference was computed first. It was then summed inside each of the 200 top-level clinical clusters. The primary p-value is the exact two-sided distribution obtained by jointly changing every nonzero whole-cluster contribution from `D_g` to `+D_g` or `−D_g` and counting assignments with an absolute total at least as large as observed. Fractions were multiplied by two for large-versus-small contrasts and by three for proprietary-versus-open contrasts so the exact convolution used integers without rounding.

This procedure:

- keeps every model response to the same question paired;
- keeps A and B paired for the interaction tests;
- permits arbitrary dependence among questions inside a clinical case cluster; and
- does not assume normally distributed 0/1 outcomes.

Its inferential assumptions are independent top-level clinical clusters and sign-exchangeability of whole-cluster contrast contributions under the null. The models were not randomized to labels, so the test is conditional on these deployed systems and sampled clusters rather than a causal model-category experiment.

The confidence intervals are percentile intervals from **100,000 whole-clinical-cluster bootstrap draws**, seed `20260801`. Repeated draws remain distinct and carry every item, model, and condition in the selected cluster. Intervals are not multiplicity-adjusted; the p-values use Holm's step-down correction across the six primary tests.

### Independent CR1 sensitivity check

An intercept-only linear probability analysis of each item-level contrast with CR1 covariance clustered by the same 200 clinical clusters reached identical 0.05 decisions:

| Contrast | CR1 t(199) | Two-sided p |
|---|---:|---:|
| Large−small, A | 7.493 | 2.16×10⁻¹² |
| Large−small, B | 7.516 | 1.88×10⁻¹² |
| Difference in large−small A→B change | 1.879 | .0618 |
| Gemini−open mean, A | 7.707 | 5.98×10⁻¹³ |
| Gemini−open mean, B | 9.542 | 5.23×10⁻¹⁸ |
| Difference in proprietary−open A→B change | 4.221 | 3.69×10⁻⁵ |

The exact sign-flip test is retained as primary for consistency with the report's approved paired A/B analysis; CR1 provides an asymptotic sensitivity analysis.

## Reporting guardrails

1. Call these **declared groups of the four named endpoints**, not populations of model types.
2. Do not write “open source causes lower accuracy” or “large models are more robust.” Neither causal claim is identified.
3. State explicitly that only one proprietary endpoint was tested. The ownership label is aliased with Gemini.
4. Separate level effects from A→B interactions. Large versus small differs in A and B accuracy but not convincingly in the amount of degradation.
5. Keep “correct” tied to the benchmark key. This is not diagnostic accuracy, patient outcome, clinical safety, or evidence of within-model repeatability; `runs=1`.
6. Label the two restricted decompositions exploratory and keep their multiplicity family separate from the six requested tests.

## Reproducible calculation recipe

1. Verify the `paired_clean.json` SHA-256 above.
2. Keep rows with `analysis_include == true`.
3. Pivot by `(question_id, model)` and retain items with all four exact model IDs. This removes only `b320`, leaving 317 items, 1,268 cells, and 200 clinical clusters.
4. For every item and condition, compute equal-model-weight group means using the membership definitions at the top of this document.
5. Form the within-condition group differences and paired difference-in-differences defined in “Design and estimands.”
6. Sum each item-level contrast within `cluster`, perform exact whole-cluster sign enumeration by integer convolution, and apply Holm correction across the six primary p-values.
7. Resample the 200 clinical clusters with replacement 100,000 times using NumPy `default_rng(20260801)`. Carry all rows of each sampled cluster; calculate the ratio estimator in each draw; report its 2.5th and 97.5th percentiles.
8. Repeat steps 4–7 for the six exploratory restricted contrasts and apply a separate Holm correction to that family.

Independent computation environment: Python 3.13.5, NumPy 2.4.4, and SciPy 1.18.0. No superseded exploratory result file was used.
