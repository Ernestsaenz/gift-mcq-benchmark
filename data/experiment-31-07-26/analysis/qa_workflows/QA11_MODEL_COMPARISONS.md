# QA11 — adversarial audit of the A, B, and paired A/B model comparisons

**Reviewer role:** independent statistical and provenance QA  
**Canonical data:** `paired_clean.json` v3  
**Reader-facing files audited:** `REPORT.md`, `report_source.sqlite`, and
`report_artifact.json`  
**Computation audited:** `final_analysis.py` and `final_analysis_results.json`  
**Verdict:** **PASS**

## Bottom line

I independently reconstructed the Experiment-A comparison among models, the Experiment-B
comparison among models, and the paired A-versus-B comparison directly from the 1,691 canonical
rows in `paired_clean.json`. I did not use the displayed report tables as calculation inputs.

Every reported denominator, correct count, point estimate, CR1 omnibus F statistic, exact
whole-clinical-cluster sign-flip p-value, Holm-adjusted p-value, and 100,000-replicate
whole-cluster bootstrap interval reproduced. The SQLite report source and the portable report
artifact contained the same numeric rows as the hash-pinned result bundle. No statistical claim
in the three new sections needs correction.

The report now also states the important inferential limits that an adversarial reading requires:
binary outcomes do not call for a normality test; CR1 tests rely on cluster-level asymptotics;
exact sign-flip tests require cluster-level sign exchangeability; the models were not randomized;
and this item bank is not a probability sample of clinical practice.

## 1. Lineage and population reconstruction

I retained only rows where `analysis_include == true`.

| quantity | independent reconstruction | report/result bundle |
|---|---:|---:|
| analysed A/B cells | 1,271 | 1,271 |
| analysed items | 318 | 318 |
| analysed clinical clusters | 201 | 201 |
| gemini rows | 318 | 318 |
| glm rows | 317 | 317 |
| qwen rows | 318 | 318 |
| gemma rows | 318 | 318 |

The sole incomplete item is `b320`: its glm A result was not recovered. Intersecting the item sets
of all four models removes only `b320` and produces the correct fair model-comparison population:

- 317 identical items for every model;
- 1,268 binary model-item outcomes; and
- 200 top-level clinical clusters.

The report correctly uses that strict common set in both the A-only and B-only sections. It then
restores all valid matched pairs in the within-model A/B section: 318 pairs for gemini, qwen, and
gemma; 317 for glm; and 1,271 cell-weighted pairs pooled. This denominator change is explicit and
cannot be mistaken for an inconsistency.

### Hash and materialization checks

- `paired_clean.json` SHA-256 independently matched
  `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187`.
- The `final_analysis.py` SHA-256 embedded in `final_analysis_results.json` matched the file
  byte-for-byte at audit time.
- Every input hash embedded in `final_analysis_results.json` matched its current file, including
  `experiment.sqlite`, `dataset_meta.json`, `cross_arm_A.json`, and
  `audited_secondary_results.json`.
- The `reportSourceSha256` and `builderSha256` values in `report_artifact.json` matched the
  materialized SQLite source and builder.
- All datasets in the artifact snapshot exactly matched `SELECT *` from the corresponding SQLite
  tables. There were no duplicate source, card, chart, table, or block IDs.

## 2. Experiment A — independent recomputation

### Descriptive values

| model | correct / 317 | accuracy | independently reproduced 100k cluster-bootstrap 95% CI |
|---|---:|---:|---:|
| gemini-3.6-flash | 310 / 317 | 97.79% | [95.93%, 99.26%] |
| glm-5.2 | 295 / 317 | 93.06% | [89.89%, 95.78%] |
| qwen3.6-35b-a3b | 280 / 317 | 88.33% | [84.36%, 91.72%] |
| gemma-4-26b-a4b-it | 251 / 317 | 79.18% | [73.81%, 83.60%] |

I independently fit the saturated linear probability model and formed the CR1 sandwich from
cluster score outer products, including the correction
`G/(G-1) * (N-1)/(N-K)`. A separate `statsmodels` implementation returned the same result:

**F(3, 199) = 22.7458366956, p = 1.0527351541e-12.**

The corresponding Wald chi-square is 68.2375100867; dividing by the three restrictions gives the
reported F statistic. The report correctly displays the finite-cluster F reference rather than
mislabeling the chi-square statistic.

### Pairwise checks

Each exact p-value was independently rebuilt by summing the paired model difference inside each
clinical cluster and convolving all `+|D_g|`/`-|D_g|` assignments. Holm adjustment was recomputed
from the six raw p-values.

| contrast | risk difference | bootstrap 95% CI | exact cluster p | Holm p | QA |
|---|---:|---:|---:|---:|---:|
| gemini - glm | +4.73 pp | [+1.91, +7.82] | 0.003319 | 0.006638 | pass |
| gemini - qwen | +9.46 pp | [+6.39, +13.00] | 5.40e-08 | 2.16e-07 | pass |
| gemini - gemma | +18.61 pp | [+14.25, +23.81] | 5.77e-15 | 3.46e-14 | pass |
| glm - qwen | +4.73 pp | [+1.15, +8.54] | 0.01930 | 0.01930 | pass |
| glm - gemma | +13.88 pp | [+9.61, +18.66] | 3.59e-09 | 1.79e-08 | pass |
| qwen - gemma | +9.15 pp | [+4.82, +13.93] | 7.87e-05 | 0.000236 | pass |

As an adversarial sensitivity check, I also formed all six CR1 t contrasts from the omnibus risk
model and applied Holm. All six remained below 0.05, including glm versus qwen (Holm p = 0.0129).
The report's statement that every A pair is separated is therefore not an artifact of choosing the
sign-flip test.

## 3. Experiment B — independent recomputation

### Descriptive values

| model | correct / 317 | accuracy | independently reproduced 100k cluster-bootstrap 95% CI |
|---|---:|---:|---:|
| gemini-3.6-flash | 283 / 317 | 89.27% | [85.47%, 92.57%] |
| glm-5.2 | 237 / 317 | 74.76% | [69.47%, 79.27%] |
| qwen3.6-35b-a3b | 230 / 317 | 72.56% | [67.49%, 77.17%] |
| gemma-4-26b-a4b-it | 189 / 317 | 59.62% | [53.02%, 65.72%] |

The independently reconstructed CR1 omnibus test is:

**F(3, 199) = 31.8433079589, p = 7.4206099493e-17.**

The equivalent Wald chi-square is 95.5299238768. An independent `statsmodels` CR1 calculation
matched the custom implementation to numerical precision.

### Pairwise checks

| contrast | risk difference | bootstrap 95% CI | exact cluster p | Holm p | QA |
|---|---:|---:|---:|---:|---:|
| gemini - glm | +14.51 pp | [+10.00, +19.27] | 2.44e-08 | 9.77e-08 | pass |
| gemini - qwen | +16.72 pp | [+11.88, +21.71] | 5.17e-09 | 2.59e-08 | pass |
| gemini - gemma | +29.65 pp | [+23.38, +36.05] | 1.14e-14 | 6.86e-14 | pass |
| glm - qwen | +2.21 pp | [-3.14, +7.28] | 0.4774 | 0.4774 | pass |
| glm - gemma | +15.14 pp | [+9.02, +21.19] | 2.43e-05 | 7.30e-05 | pass |
| qwen - gemma | +12.93 pp | [+6.93, +19.06] | 0.000145 | 0.000290 | pass |

The sole unresolved pair is glm versus qwen. A separate CR1 t-contrast family reached the same
decision (Holm p = 0.401 for glm versus qwen; all other adjusted p-values below 0.001). The report
does not infer equivalence from the non-significant result and correctly describes the interval as
allowing a modest difference in either direction.

## 4. Paired A versus B — independent recomputation

| model | paired n | A correct | B correct | B - A | bootstrap 95% CI | exact cluster p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 318 | 311 | 284 | -8.49 pp | [-12.26, -5.01] | 1.51e-05 | 1.51e-05 |
| glm-5.2 | 317 | 295 | 237 | -18.30 pp | [-23.33, -13.74] | 5.28e-11 | 2.11e-10 |
| qwen3.6-35b-a3b | 318 | 281 | 231 | -15.72 pp | [-20.69, -10.75] | 1.80e-07 | 5.39e-07 |
| gemma-4-26b-a4b-it | 318 | 251 | 189 | -19.50 pp | [-26.06, -12.81] | 3.14e-07 | 6.27e-07 |
| cell-weighted pooled | 1,271 | 1,138 | 941 | -15.50 pp | [-18.78, -12.39] | 1.95e-15 | — |

All 15 displayed limits in the A, B, and paired A/B sections reproduced exactly from the advertised
deterministic seeds and NumPy linear quantiles. I sampled whole clinical clusters, retained every
item/model row in a sampled cluster, and kept repeated draws as repeated draws. This specifically
tests the earlier duplicate-cluster bootstrap failure mode; it is not present in the current code.

The model-specific Holm family correctly contains four tests and excludes the pooled descriptive
summary. The pooled sign-flip uses 201 clusters, 114 nonzero cluster contributions, observed net
change -197, null variance 1,083, and iid-discordance variance 287, giving the reported design
effect 3.7735. Ordinary McNemar p-values remain secondary and are not substituted for the
cluster-aware tests.

## 5. Assumptions, normality, and clinical wording

### Statistical language

- Correctness is Bernoulli, and paired changes lie in `{-1, 0, +1}`. The report correctly rejects
  Shapiro-Wilk and raw-score Q-Q testing as answering the wrong question.
- The report distinguishes the CR1 large-cluster approximation from exact sign-flip inference.
- It explicitly states that exact sign-flip inference adds cluster-level sign exchangeability.
- It does not describe these as randomized-treatment tests, and it names the lack of a probability
  sample and resulting limit on external generalisability.
- Holm families are correctly separated: six A model contrasts, six B model contrasts, and four
  model-specific A/B contrasts.

### Clinician-facing language

Each of the three requested result sections places a physician explanation after its statistical
evidence. The explanations translate risk differences into additional or fewer key-matched answers
per 100 while preserving the following guardrails:

- the endpoint is agreement with an examination key, not patient-level diagnostic accuracy;
- results do not establish sensitivity, specificity, patient benefit, or bedside safety;
- the B comparison is an engineered, position-dependent meta-answer task;
- the A/B contrast does not prove memorisation or isolate a pure text effect; and
- one deterministic run per cell cannot establish within-model stability.

I found no clinical overclaim in these blocks.

## 6. Adversarial failure-mode checks

| attempted falsification | outcome |
|---|---|
| Count the unrecovered glm cell as wrong | Current pipeline does not; it is dropped and declared. |
| Compare models on unequal 317/318 denominators | Current A and B model sections use the strict common 317-item set. |
| Hide the common-set/all-pairs denominator change | The change and `b320` are explained before the tables. |
| Recompute CR1 covariance in `statsmodels` | Matches custom covariance and both F tests to numerical precision. |
| Recompute exact sign flips with independent integer convolution | All 17 raw p-values match. |
| Recompute Holm families from unsorted raw p-values | All 16 model-specific adjusted p-values match. |
| Recreate all bootstrap intervals from canonical rows and seeds | All limits match exactly. |
| Replace sign-flip conclusions with CR1 pairwise contrasts | Same six A decisions and same five-versus-one B decisions. |
| Treat non-significance as model equivalence | Report explicitly avoids this error. |
| Infer bedside performance or a memorisation mechanism | Physician and construct-validity wording explicitly forbids both. |
| Compare artifact snapshot with SQLite source | Every dataset and row matches. |

## 7. Release integration note

`RELEASE_MANIFEST.json` was still the pre-update ten-QA manifest at the time of this audit and
contained hashes from before the new model-comparison code and report build. That does not change
the statistical verdict, but it **must be regenerated after QA11 and QA12 and after the final HTML
build**. The final release manifest should record the final QA count and hashes rather than preserve
the stale values.

## Final verdict

**PASS.** The three requested comparison sections are numerically correct, use coherent
denominators and cluster-aware inferential procedures, state the assumptions needed for those
procedures, and translate the evidence for physicians without converting benchmark performance
into a clinical claim. No remediation is required in the statistical tables or narrative. The
only outstanding action is release packaging: rebuild the QA summary, report artifact/HTML, and
release manifest after both new adversarial QA workflows finish.
