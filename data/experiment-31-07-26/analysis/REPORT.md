# Correct-option substitution benchmark: verified final analysis

**Analysis date:** 2026-07-31  
**Release:** v3.3.1 presentation repair on the approved v3.3 analysis; OpenRouter B complete; OpenRouter A missing one cell; GIFT A partial; GIFT B not run  
**Primary endpoint:** paired binary correctness  
**Direction:** all differences are condition B minus condition A unless stated otherwise

## Executive conclusion

The model comparisons are presented in the requested order: Experiment A, Experiment B, and then
the paired A-versus-B contrast. For the fair within-experiment comparisons, all four models are
evaluated on the same 317 items and 200 clinical clusters. In A, accuracy ranged from **97.79% for
gemini to 79.18% for gemma**, and all six pairwise model differences survived Holm correction. In
B, accuracy ranged from **89.27% for gemini to 59.62% for gemma**; glm and qwen were the only pair
the data did not separate after correction.

Using the requester-defined groups, the two large models averaged **95.43% versus 83.75%** for the
two small models in A and **82.02% versus 66.09%** in B. Both level contrasts survived Holm
correction. Their A-to-B losses differed by **4.26 points**, but that interaction was not resolved
(95% CI **−0.38 to +8.57**, Holm p = **0.0925**). The three-model open group averaged **86.86% in
A and 68.98% in B**, while the sole proprietary endpoint, gemini, scored **97.79% and 89.27%**.
Gemini's smaller decline produced a **9.36-point** difference in changes (Holm p = **0.000321**),
but one proprietary model cannot establish a proprietary-model class advantage.

Across all available paired OpenRouter cells, keyed-answer accuracy was **89.54% in A and 74.04%
in B**, a paired difference of **−15.50 percentage points**. In B, the substantive keyed option is
replaced by the same position-dependent preceding-options meta-answer on every item. A
100,000-replicate whole-clinical-cluster bootstrap gave a 95% interval of approximately **−18.8 to
−12.4 points**; an exact clinical-cluster sign-flip test gave **p = 1.95 × 10⁻¹⁵**. Every model
moved in the same negative direction.

The negative observed contrast is stable across the reported cleaning choices,
clinical-cluster analyses, four named model endpoints, and leave-one-unit checks. It does **not**
isolate memorisation or recognition of a familiar answer string: condition B also removes the
substantive key, changes answer semantics and genre, makes one recurring meta-answer correct on
every B item, and may change decision strategy. Because the arms were run at different times and
physical provider routing was not pinned, attributing the entire contrast to the text bundle also
requires a no-time/no-routing-confounding assumption.

The partial cross-pipeline result is model-specific. On 306 cleaned items completed by all four
GIFT-served models, GIFT-served minus OpenRouter-served accuracy was **+5.56 points** for gemma,
**+3.27** for glm, **−0.33** for qwen, and **−0.98** for gemini. GIFT A produced scores for only
**1,384 of 1,896 planned cells
(73.0%)**, its covered prefix was easier than the unobserved remainder, and GIFT B never ran.
These are observed differences between two deployed pipelines on the condition-A complete-case
subset, not isolated retrieval effects or a full-target estimate.

## 1. Study and analysis population

The source contains 500 Spanish multiple-choice items assembled for a digestive-system benchmark
from regional public-health exams; later QA identified a small law/administration subset. The
flattening step produced:

| dataset | items | construction |
|---|---:|---|
| condition A | 474 | 500 source items minus 17 three-option items and 9 source-level defects; keyed text retained |
| condition B | 423 | A minus 51 items where the swap was invalid or ambiguous; keyed text replaced by the position-dependent phrase `Ninguna de las respuestas anteriores es correcta.`; keyed letter unchanged |

Four models were run once per cell at temperature 0 with prompt `mcq_es_v4`:

- `google/gemini-3.6-flash`
- `z-ai/glm-5.2`
- `qwen/qwen3.6-35b-a3b`
- `google/gemma-4-26b-a4b-it`

The requested model groups for this post-hoc report analysis are defined as follows:

| model | requested size group | requested access group |
|---|---|---|
| gemini-3.6-flash | large | proprietary |
| glm-5.2 | large | open-model |
| qwen3.6-35b-a3b | small | open-model |
| gemma-4-26b-a4b-it | small | open-model |

“Open-model” is used as neutral shorthand for the requested open-source grouping; this analysis
does not adjudicate license terms. “Large” and “small” are also requested analytical labels, not a
parameter-count-matched taxonomy. There is no small proprietary model, so the design is not a
complete `size × access` factorial and cannot separate those attributes as general model-class
effects.

The reported OpenRouter A/B population is **318 items, 1,271 paired model×item cells, and 201
clinical clusters**. The expected 1,272 cells are reduced by the unrecovered
`b320 × glm-5.2` condition-A cell.

For the model-versus-model comparisons in Experiments A and B, `b320` is removed for all four
models. This creates one identical complete-case set of **317 items, 1,268 model×item cells, and
200 clinical clusters**. No missing result is counted as wrong or imputed. The later paired A/B
section retains all available pairs—318 for gemini, qwen, and gemma and 317 for glm—because that
section compares each model with itself rather than comparing models with unequal denominators.

### Analysis exclusions

The eligible A/B universe contains 423 items. The requested cleaning removes 19 declared item
defects present in that universe and 91 items whose keyed letter is `a`; five items satisfy both
rules. Thus `423 − 19 − 91 + 5 = 318` items.

| rule | declared globally | present in A/B universe | basis |
|---|---:|---:|---|
| out-of-domain law/administration | 19 | 16 | employment, privacy, health-administration, and service-catalogue content outside digestive medicine |
| user-adjudicated key defect | 3 | 3 | `b178`, `b197`, `b496`; source-key adjudication supplied during the analysis |
| preceding-options phrase in option `a` | — | 91 | “respuestas anteriores” appears in the first position and has no antecedent |

Three globally declared out-of-domain items were already absent from B, so only 19 of the 22
declared defects enter the paired-universe arithmetic. The 19 law/administration classifications
are evident from their stems. The detailed medical adjudication and citations for the three key
defects were not preserved in the supplied artifacts; those three exclusions are therefore
treated as a user-directed rule and tested through the exclusion sensitivity grid, not as a newly
verified medical judgment.

The remaining analysed phrase positions are `b=111`, `c=122`, and `d=85`. Excluding slot `a`
removes the no-antecedent case but does not make the phrase position-neutral: in `b` and `c` it
literally refers only to choices printed before it. The exact phrase is keyed in all 423 B-eligible
items and in none of their matched A versions; key-letter frequencies themselves do not change.

## 2. Experiment A: comparison among models

Experiment A retains the original substantive keyed answer. To compare models fairly, this section
uses only the **317 questions answered by all four models**: 1,268 binary outcomes in 200 clinical
clusters. The one incomplete item, `b320`, is excluded for every model in this section only.

| model | correct / 317 | accuracy | whole-cluster bootstrap 95% CI |
|---|---:|---:|---:|
| gemini-3.6-flash | 310 / 317 | **97.79%** | [95.93%, 99.26%] |
| glm-5.2 | 295 / 317 | **93.06%** | [89.89%, 95.78%] |
| qwen3.6-35b-a3b | 280 / 317 | **88.33%** | [84.36%, 91.72%] |
| gemma-4-26b-a4b-it | 251 / 317 | **79.18%** | [73.81%, 83.60%] |

The corresponding omnibus test is a saturated linear probability model with CR1 sandwich
covariance over clinical clusters. It rejects equal marginal accuracy across the four models:
**cluster-robust Wald F(3, 199) = 22.75, p = 1.05 × 10⁻¹²**. This test uses the risk scale, so its
coefficients are the observed accuracy differences in percentage points.

Pairwise magnitudes use 100,000 whole-cluster bootstrap replicates. P-values use exact
clinical-cluster sign flips and are Holm-adjusted across the six comparisons within Experiment A.

| comparison | accuracy difference | cluster-bootstrap 95% CI | exact cluster p | Holm p |
|---|---:|---:|---:|---:|
| gemini − glm | **+4.73 pp** | [+1.91, +7.82] | 0.00332 | **0.00664** |
| gemini − qwen | **+9.46 pp** | [+6.39, +13.00] | 5.40 × 10⁻⁸ | **2.16 × 10⁻⁷** |
| gemini − gemma | **+18.61 pp** | [+14.25, +23.81] | 5.77 × 10⁻¹⁵ | **3.46 × 10⁻¹⁴** |
| glm − qwen | **+4.73 pp** | [+1.15, +8.54] | 0.0193 | **0.0193** |
| glm − gemma | **+13.88 pp** | [+9.61, +18.66] | 3.59 × 10⁻⁹ | **1.79 × 10⁻⁸** |
| qwen − gemma | **+9.15 pp** | [+4.82, +13.93] | 7.87 × 10⁻⁵ | **0.000236** |

All six pairwise differences remain statistically detectable after multiplicity correction. The
ordering in this benchmark is therefore gemini, glm, qwen, then gemma. It is a comparison of the
four deployed configurations on this item bank, not proof of a universal ranking.

### Requested group contrasts in Experiment A

Group accuracy is the equal-weight mean over the named models and 317 common items. The group
contrast uses a whole-clinical-cluster bootstrap interval and an exact clinical-cluster sign-flip
test. These are exploratory fixed contrasts requested after the main model analysis. Holm p-values
cover the six primary grouped hypotheses: large versus small and open-model
versus proprietary within each condition, plus the two group-by-condition interactions.

| grouping and direction | first group accuracy | second group accuracy | difference | cluster-bootstrap 95% CI | exact cluster p | Holm p |
|---|---:|---:|---:|---:|---:|---:|
| large − small | 95.43% | 83.75% | **+11.67 pp** | [+8.79, +14.95] | 1.66 × 10⁻¹³ | **6.65 × 10⁻¹³** |
| open-model − proprietary | 86.86% | 97.79% | **−10.94 pp** | [−14.00, −8.36] | 1.37 × 10⁻¹⁴ | **6.83 × 10⁻¹⁴** |

These p-values use the 200 clinical-question clusters as the sampling units while keeping the four
deployments fixed. They do not turn 317 questions into 317 independent model replicates: the size
contrast still contains only two named models per group, and the access contrast compares three
named open-model endpoints with gemini alone.

### How to read the annotated boxplots

The model and requested-group boxplots below summarize the **sampling distributions** from the
same 100,000 whole-clinical-cluster bootstrap used for the intervals—not the distribution of raw
0/1 answers. Each label gives the observed accuracy. The whisker caps mark the bootstrap minimum
and maximum, the outlined box runs from Q1 to Q3, and the dark line inside the box marks the
median. Hover repeats all five values. The adjacent tables remain the authoritative source for
95% intervals and Holm-adjusted tests.

### Clinical interpretation for physicians

On the same original-format questions, gemini matched the exam key on about 98 of every 100 items,
glm on 93, qwen on 88, and gemma on 79. Even the two smallest observed gaps—gemini versus glm and
glm versus qwen—were about five additional key-matched answers per 100 questions and remained
detectable after accounting for all six pairwise comparisons. Averaged over the requested groups,
the large pair produced about 12 more key-matched answers per 100 questions than the small pair;
gemini produced about 11 more than the mean of the three-model open group. Those group summaries
describe these systems only and should not be read as evidence that size or proprietary access
caused the difference. These are examination-key results, not estimates of diagnostic sensitivity,
patient benefit, or bedside safety. Each cell was run once, and any answer used clinically still
requires independent clinical verification.

## 3. Experiment B: comparison among models

Experiment B replaces the substantive keyed option with
`Ninguna de las respuestas anteriores es correcta.` while leaving the keyed letter unchanged. The
same complete-case population as Experiment A is used here: **317 questions, 1,268 outcomes, and
200 clinical clusters**.

| model | correct / 317 | accuracy | whole-cluster bootstrap 95% CI |
|---|---:|---:|---:|
| gemini-3.6-flash | 283 / 317 | **89.27%** | [85.47%, 92.57%] |
| glm-5.2 | 237 / 317 | **74.76%** | [69.47%, 79.27%] |
| qwen3.6-35b-a3b | 230 / 317 | **72.56%** | [67.49%, 77.17%] |
| gemma-4-26b-a4b-it | 189 / 317 | **59.62%** | [53.02%, 65.72%] |

The same risk-scale omnibus method rejects equal marginal accuracy:
**cluster-robust Wald F(3, 199) = 31.84, p = 7.42 × 10⁻¹⁷**.

Pairwise magnitudes again use 100,000 whole-cluster bootstrap replicates. P-values use exact
clinical-cluster sign flips with Holm adjustment across the six Experiment-B comparisons.

| comparison | accuracy difference | cluster-bootstrap 95% CI | exact cluster p | Holm p |
|---|---:|---:|---:|---:|
| gemini − glm | **+14.51 pp** | [+10.00, +19.27] | 2.44 × 10⁻⁸ | **9.77 × 10⁻⁸** |
| gemini − qwen | **+16.72 pp** | [+11.88, +21.71] | 5.17 × 10⁻⁹ | **2.59 × 10⁻⁸** |
| gemini − gemma | **+29.65 pp** | [+23.38, +36.05] | 1.14 × 10⁻¹⁴ | **6.86 × 10⁻¹⁴** |
| glm − qwen | **+2.21 pp** | [−3.14, +7.28] | 0.477 | **0.477** |
| glm − gemma | **+15.14 pp** | [+9.02, +21.19] | 2.43 × 10⁻⁵ | **7.30 × 10⁻⁵** |
| qwen − gemma | **+12.93 pp** | [+6.93, +19.06] | 0.000145 | **0.000290** |

Gemini is higher than each alternative, and both glm and qwen are higher than gemma after Holm
correction. The study does **not** resolve glm versus qwen: the observed +2.21-point difference has
a confidence interval spanning zero and an adjusted p-value of 0.477.

### Requested group contrasts in Experiment B

The same equal-model weighting, 317-item complete-case population, whole-cluster intervals, exact
cluster sign flips, and six-test Holm family are used here.

| grouping and direction | first group accuracy | second group accuracy | difference | cluster-bootstrap 95% CI | exact cluster p | Holm p |
|---|---:|---:|---:|---:|---:|---:|
| large − small | 82.02% | 66.09% | **+15.93 pp** | [+11.81, +20.14] | 1.88 × 10⁻¹⁰ | **5.65 × 10⁻¹⁰** |
| open-model − proprietary | 68.98% | 89.27% | **−20.29 pp** | [−24.51, −16.16] | 2.85 × 10⁻¹⁷ | **1.71 × 10⁻¹⁶** |

The group gaps are larger in percentage points than in A, but that observation alone does not show
greater group “robustness”: the models start from different baselines, gemini is near the A ceiling,
and risk-difference interactions can disagree with log-odds interactions.

### How to read the annotated boxplots

The two boxplots below use 100,000 whole-clinical-cluster bootstrap estimates on the common
317-item set. Labels report observed accuracy. Whisker caps mark the bootstrap minimum and
maximum, the outlined box shows the middle 50% from Q1 to Q3, and its dark internal line marks the
median. Hover repeats all five values. These are uncertainty displays, not raw-score boxplots;
exact 95% intervals and corrected p-values remain in the tables.

### Clinical interpretation for physicians

Under this engineered answer format, gemini matched the key on about 89 of every 100 questions,
glm on 75, qwen on 73, and gemma on 60. The analysis supports a difference between gemini and each
other model and between gemma and both middle models. It cannot reliably rank glm above qwen; the
plausible range includes a modest advantage in either direction. For the requested groups, the
large pair averaged about 16 more key matches per 100 than the small pair, while gemini averaged
about 20 more than the three open-model endpoints. The second comparison is gemini versus a group,
not a replicated proprietary-versus-open experiment. This is an artificial position-dependent
meta-answer task, so the values must not be interpreted as bedside diagnostic accuracy or evidence
about general handling of a standard none-of-the-above option.

## 4. Paired comparison between Experiments A and B

This section compares each model with itself on every available A/B pair. It therefore restores
the three valid `b320` pairs and uses **318 pairs** for gemini, qwen, and gemma and **317 pairs** for
glm. The pooled descriptive row contains 1,271 model×item pairs in 201 clinical clusters.

| model | paired n | A accuracy | B accuracy | B − A | cluster-bootstrap 95% CI | exact cluster p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 318 | 97.80% | 89.31% | **−8.49 pp** | [−12.26, −5.01] | 1.51 × 10⁻⁵ | **1.51 × 10⁻⁵** |
| glm-5.2 | 317 | 93.06% | 74.76% | **−18.30 pp** | [−23.33, −13.74] | 5.28 × 10⁻¹¹ | **2.11 × 10⁻¹⁰** |
| qwen3.6-35b-a3b | 318 | 88.36% | 72.64% | **−15.72 pp** | [−20.69, −10.75] | 1.80 × 10⁻⁷ | **5.39 × 10⁻⁷** |
| gemma-4-26b-a4b-it | 318 | 78.93% | 59.43% | **−19.50 pp** | [−26.06, −12.81] | 3.14 × 10⁻⁷ | **6.27 × 10⁻⁷** |
| **cell-weighted pooled** | **1,271** | **89.54%** | **74.04%** | **−15.50 pp** | **[−18.8, −12.4]** | **1.95 × 10⁻¹⁵** | — |

The primary corresponding test is an exact two-sided sign flip of each whole clinical cluster's
net A/B difference. Holm adjustment is applied across the four named model endpoints. All four
models remain lower in B after correction. The pooled sign-flip test retains all four responses
and related questions inside each clinical cluster; its null-variance design effect is **3.774**
relative to treating discordant cells as independent. Ordinary exact McNemar tests are retained in
the machine-readable result bundle as iid-pair sensitivity checks, but they are not the primary
cluster-aware inference.

A model-adjusted logistic regression with CR1 covariance over the 201 clinical clusters estimated
an odds ratio of **0.314** (95% CI **0.247–0.399**, p = **3.36 × 10⁻²¹**). In words, condition B
was associated with about a **68.6% reduction in the odds** of a correct response after adjusting
for model. An item-stratified conditional logistic sensitivity model gave a within-item common odds
ratio of **0.209** (95% CI **0.150–0.290**).

### Model heterogeneity is scale-dependent

The percentage-point changes differ (cluster-covariance Wald p = **0.000293**), largely because the
models begin at different baselines and gemini is near the ceiling. Log-odds interaction tests are
less conclusive: the conditional-logit interaction LRT gives p = **0.201**, its cluster-robust Wald
test p = **0.123**, while a marginal-logit robust Wald test gives p = **0.0438**. These do not
establish equal robustness. The accurate conclusion is that heterogeneity depends on the estimand
and model; the direction is uniformly negative.

### A-to-B change within each requested model group

These summaries return to the 317-item common set so that every group is evaluated on identical
questions. Each group-specific p-value tests its own A-to-B change; Holm adjustment is across the
four overlapping group summaries.

| requested group | model count | A accuracy | B accuracy | B − A | cluster-bootstrap 95% CI | exact cluster p | Holm p |
|---|---:|---:|---:|---:|---:|---:|---:|
| large | 2 | 95.43% | 82.02% | **−13.41 pp** | [−17.05, −10.18] | 4.84 × 10⁻¹² | **1.45 × 10⁻¹¹** |
| small | 2 | 83.75% | 66.09% | **−17.67 pp** | [−21.95, −13.26] | 5.67 × 10⁻¹¹ | **1.13 × 10⁻¹⁰** |
| open-model | 3 | 86.86% | 68.98% | **−17.88 pp** | [−21.67, −14.16] | 1.10 × 10⁻¹⁴ | **4.41 × 10⁻¹⁴** |
| proprietary (gemini) | 1 | 97.79% | 89.27% | **−8.52 pp** | [−12.31, −5.07] | 1.51 × 10⁻⁵ | **1.51 × 10⁻⁵** |

The inferential group question is whether those declines differ—not whether each decline alone is
nonzero:

| interaction and direction | difference between B − A changes | cluster-bootstrap 95% CI | exact cluster p | Holm p across six primary group tests | conclusion |
|---|---:|---:|---:|---:|---|
| large change − small change | **+4.26 pp** | [−0.38, +8.57] | 0.0925 | **0.0925** | difference not resolved |
| open-model change − proprietary change | **−9.36 pp** | [−13.64, −4.94] | 0.000161 | **0.000321** | open-model mean lost more |

The size-group interaction is therefore inconclusive on the percentage-point scale. The access-group
interaction is statistically detectable for this panel, but it is inseparable from gemini's model
identity and its higher baseline: the “proprietary” group has one endpoint and there is no small
proprietary comparator. It must not be presented as a general proprietary-model robustness effect.

### Triangulation inside the incomplete size × access design

Two secondary contrasts partially hold one requested attribute fixed. They use the same cluster
methods and Holm adjustment across six secondary tests (A level, B level, and change interaction
for each perspective).

| perspective | Experiment-A gap | Experiment-B gap | difference in B − A changes | interaction 95% CI | Holm interaction p |
|---|---:|---:|---:|---:|---:|
| within large: gemini − glm | +4.73 pp | +14.51 pp | **+9.78 pp** | [+4.85, +14.96] | **0.00150** |
| within open-model: glm − mean(qwen, gemma) | +9.31 pp | +8.68 pp | **−0.63 pp** | [−6.18, +4.39] | **0.859** |

This triangulation shows why the aggregate labels are not interchangeable with mechanisms. Within
the open-model subset, glm had higher level accuracy than the two small open endpoints in both
conditions, but its A-to-B loss was not detectably different. Within the large pair, gemini's loss
was smaller than glm's. That pattern points to endpoint-specific behavior and baseline scale—not a
cleanly identified size effect.

### How to read the annotated boxplots

The three annotated boxplots below show bootstrap distributions for each model's A-to-B change,
each requested group's change, and the primary plus secondary differences in changes. Labels show
the observed percentage-point estimate. Whisker caps mark the bootstrap minimum and maximum, the
outlined box spans Q1 to Q3, and the dark internal line marks the median. Hover repeats all five
values. A box crossing zero is descriptive only—the exact cluster test, its Holm adjustment, and
the 95% interval in the adjacent tables determine the stated inference.

### Clinical interpretation for physicians

For every model, changing from the original keyed answer in A to the engineered meta-answer in B
reduced agreement with the exam key. The observed loss ranged from roughly 8 fewer correct answers
per 100 for gemini to about 20 fewer for gemma, and all four declines remained detectable after
accounting for clinical-case clustering and four model-specific tests. This demonstrates
sensitivity to the complete B configuration; it does not prove memorisation, because B changes the
answer's content, semantics, genre, repetition pattern, and decision structure at the same time.
The requested large and small groups both declined, and the data did not establish that their
declines differ. The apparent proprietary/open-model difference is chiefly a comparison of gemini
with three other endpoints and should not guide a clinical procurement decision as a class effect.
It also does not estimate a change in patient outcomes.

## 5. Statistical method and normality

Correctness is binary and the paired change takes only `−1`, `0`, or `+1`. A Shapiro–Wilk test or
Q–Q plot on those values would test an impossible continuous-normal model and is not relevant.
The analyses used here do not assume normally distributed outcomes:

1. Within A and within B, a saturated risk-scale model with CR1 covariance tests whether all four
   marginal accuracies are equal; the finite-cluster reference is F(3, 199).
2. Within-experiment pairwise differences use 100,000 whole-cluster bootstrap intervals and exact
   clinical-cluster sign-flip p-values, with Holm adjustment across six comparisons per condition.
3. The paired A/B section uses per-model risk differences, 100,000 whole-cluster bootstrap
   intervals, and exact clinical-cluster sign flips with Holm adjustment across four models.
4. Requested group accuracies give each named model equal weight on the 317 common items. Group
   contrasts and group-by-condition interactions use whole-cluster bootstrap intervals and exact
   sign flips of integer-scaled clinical-cluster contributions. Holm correction is applied to six
   primary group contrasts, four group-specific declines, and—separately—six secondary
   triangulation tests.
5. Exact McNemar tests remain secondary iid-pair checks, and cluster-robust logistic regression is
   a secondary A/B common-effect summary.

The top-level clusters are assumed independent and exchangeable enough for resampling. Cluster
sizes are uneven: the Kish effective count is **50.9** rather than the nominal 201. This is why the
report emphasizes whole-cluster intervals and leave-one-unit checks. In the bootstrap, repeated
cluster draws retain their multiplicity; they are never regrouped only by question ID.

The CR1 Wald F tests rely on having enough independent top-level clusters. Exact sign-flip tests
add the sharper null assumption that cluster-level paired differences are sign-exchangeable; the
models were not randomized, so these are sampling-model tests over the analysed item clusters, not
randomized-treatment tests. The item bank is not a probability sample of clinical practice, and
none of these p-values establishes external clinical generalisability.

Normality would matter for a proposed parametric comparison of a genuinely continuous secondary
outcome. It does not rescue completion-token or latency comparisons here, because those measures
have additional construction and serving confounds described below.

## 6. Sensitivity to cleaning and influential units

The observed contrast remains negative under every main exclusion choice. These four rows are independently
recomputed on v3; intervals are whole-cluster percentile bootstraps.

| exclusions | items | cells | pooled change | 95% CI |
|---|---:|---:|---:|---:|
| none | 423 | 1,691 | −17.33 pp | [−20.39, −14.44] |
| item defects only | 404 | 1,615 | −16.90 pp | [−20.02, −13.96] |
| position-`a` only | 332 | 1,327 | −15.75 pp | [−18.91, −12.68] |
| both, reported set | 318 | 1,271 | −15.50 pp | [−18.75, −12.35] |

Both requested exclusion classes make the measured contrast smaller. On the reported set, the pooled
change ranges only from **−16.06 to −15.00 points** across 201 leave-one-cluster-out refits and
from **−15.86 to −15.23** across 318 leave-one-item-out refits. Dropping one model at a time gives
**−17.84 to −14.17**.

After removing declared item defects, key-`a` cells show a descriptive change of **−22.09 points**,
compared with **−15.50** for other positions, a **−6.59-point** gap. This supports excluding the
positionally incoherent construction on logical-design grounds, but the cleaned interaction is not
conclusive (cluster 95% CI **−13.38 to +0.26 points**; exact item-label p = **0.063**). The core
contrast is not dependent on those cells.

## 7. What the A/B result can and cannot support

### Supported

- Across the observed runs, condition-B keyed-answer accuracy is materially lower than condition A
  for all four named model endpoints.
- The negative contrast survives clinical clustering, the requested cleaning rules, and
  leave-one-unit checks.
- The contrast is not explained by the one unrecovered OpenRouter cell.

### Not supported

- **The pure causal effect of text replacement.** Run time and physical provider routing were not
  pinned or randomized across arms.
- **Memorisation, lexical familiarity, or reasoning burden as isolated mechanisms.** The
  intervention removes the substantive key, changes semantics and genre, perfectly couples one
  repeated phrase with keyed status, and may change decision strategy; burden was not measured.
- **General none-of-the-above handling.** The phrase refers to preceding options and is always
  keyed in B; it was not tested as a position-neutral or unkeyed meta-option.
- **Equal robustness across models.** Interaction evidence varies by scale; no equivalence margin
  was specified or tested.
- **General large-versus-small or open-versus-proprietary effects.** The four deployments were
  fixed, only one proprietary model was observed, and the size-by-access table lacks a small
  proprietary cell. Question-level replication does not supply model-level replication.
- **Item-level stability.** There was one run per item/model/condition.
- **Unconfounded latency or token effort.** The serving and response formats differ in ways that
  contaminate those measures.

The highest-value follow-up uses multiple clinician-validated, length/style-matched paraphrases,
including keyed-only and all-options paraphrase controls. A position-neutral meta-option should be
tested both keyed and unkeyed, with position balanced and the substantive answer held present or
absent by design. To isolate retrieval, randomize and interleave a
`substitution (A/B) × retrieval (off/on)` design within the same provider stack while pinning the
model snapshot, prompt, corpus/index, `top_k`, response schema, and backend.

## 8. Partial GIFT-served versus OpenRouter-served result: condition A only

The paired cross-arm table uses only items for which all four GIFT models produced a score, then
applies the declared item-defect exclusions: **306 items, 1,224 model×item pairs, 178 clinical
clusters**.

This compares whole deployed pipelines, not retrieval alone. OpenRouter received the in-message
`mcq_es_v4` template. GIFT calls carried server-side prompt ID 13 and used the server-default
retrieval depth (`top_k` was not pinned); the deployed prompt text, retrieved passages, and
corpus/index version were not independently archived.

| model | OpenRouter | GIFT | GIFT − OpenRouter | discordance OR-only / GIFT-only | cluster-bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 98.37% | 97.39% | **−0.98 pp** | 3 / 0 | [−2.42, 0.00] |
| glm-5.2 | 93.14% | 96.41% | **+3.27 pp** | 1 / 11 | [+1.12, +5.80] |
| qwen3.6-35b-a3b | 92.16% | 91.83% | **−0.33 pp** | 12 / 11 | [−3.43, +2.68] |
| gemma-4-26b-a4b-it | 82.68% | 88.24% | **+5.56 pp** | 7 / 24 | [+1.97, +9.27] |
| **cell-weighted pooled** | **91.58%** | **93.46%** | **+1.88 pp** | **23 / 46** | **[+0.44, +3.35]** |

The exact cluster sign-flip p-values are 0.250 (gemini), 0.0107 (glm), 1.000 (qwen), 0.0070
(gemma), and 0.0206 pooled. Risk-difference heterogeneity is strong
(F(3,177) = **7.08**, p = **0.000162**). The model effects reverse sign, so the pooled
+1.88-point estimate is
not an adequate product conclusion. The two positive model results survive Holm adjustment of the
four cluster sign-flip tests; gemini and qwen do not.

### Coverage limitation

GIFT A produced scores for **1,384/1,896 planned cells (73.0%)**. The runner created 1,566 logical
calls (82.6% of plan) and attempted 1,565 distinct calls; “83% complete” therefore describes where
the sequential runner reached, not scored completion. Only **319 items** had scores from all four
GIFT models before analysis exclusions.

Coverage was a sequential prefix with gaps, not a random sample. OpenRouter accuracy was **91.07%**
on the 319 all-model-covered items and **82.88%** on the 155 other A items, an **8.19-point**
difference. Pairing makes the observed-subset comparison internally coherent but does not identify
the GIFT-served minus OpenRouter-served pipeline difference on the missing items. On the cleaned
full condition-A target, a strict
assumption-free missing-outcome bound for GIFT minus OpenRouter is **−21.46 to +5.42 points**;
post-stratified estimates near +2 points require untestable extrapolation. No full-target pipeline
difference is reported.

### How to read the annotated boxplot

The boxplot below summarizes 100,000 whole-clinical-cluster bootstrap estimates of GIFT minus
OpenRouter for each model on the observed subset. Labels show the observed change. Whisker caps
mark the bootstrap minimum and maximum, the outlined box spans Q1 to Q3, and the dark internal
line marks the median. Hover repeats all five values. It visualizes uncertainty on the covered
subset only; it does not repair the sequential missing coverage or identify retrieval.

## 9. Run status and measurement caveats

| experiment | planned cells | logical calls created | scored cells | scored share | status |
|---|---:|---:|---:|---:|---|
| OpenRouter A | 1,896 | 1,896 | 1,895 | 99.95% | one unrecovered cell |
| OpenRouter B | 1,692 | 1,692 | 1,692 | 100.0% | complete |
| GIFT A | 1,896 | 1,566 | 1,384 | 73.0% | stopped by operator |
| GIFT B | 1,692 | 0 | 0 | 0% | never started |

The GIFT A run recorded **1,582 provider attempts**, of which **196 (12.39%)** returned non-200
status codes. Seventeen HTTP 401 attempts were recovered on retry. At stop time, **179 of 1,565
attempted logical cells (11.44%)** ended on a non-200 latest attempt (96 HTTP 429 and 83 HTTP 500),
two more ended in an HTTP-200 parse failure, and one created logical call was never started. These
are operational attempt/call rates, not permanent model error rates; retries and unattempted cells
must be shown separately.

Cross-arm latency and cost claims require restraint:

- GIFT was deliberately serialised while OpenRouter used different serving infrastructure and
  concurrency. Observed wall-clock throughput is a property of those run settings, not an intrinsic
  model latency ratio.
- `completion_tokens` include the emitted JSON and selected option text. Condition B replaces a
  variable-length keyed answer with a fixed string, so raw completion-token differences partly
  measure answer echo, not deliberation.
- OpenRouter provider routing was not pinned. The A/B backend total-variation distance is 0 for
  gemini, 0.815 for gemma, 0.236 for qwen, and 0.303 for glm. Same-backend subsets remain negative
  for all models, but are selected and small for gemma and qwen; they reduce concern without fully
  removing the confound.

Accordingly, the final findings do not include “deliberated longer,” an intrinsic 15.6× latency
penalty, or minutes/failures per additional correct answer unless a separately pinned operational
benchmark is run.

## 10. Missing work and scope boundaries

The following evidence does not exist and is absent from the conclusions:

- GIFT condition B and therefore any retrieval-arm A/B contrast.
- The remaining 512 planned GIFT A scores.
- The paraphrase and format-control arms needed for a memorisation mechanism claim.
- Replicate runs for within-item/model stability.
- Provider-pinned A/B serving measurements.
- Archived medical rationale and citations for the three user-adjudicated key exclusions.

Two earlier exploratory workflows—“Data structure, distributional assumptions, and principled
test selection” and “What drives the A-to-B behaviour”—were stopped before their verification
phases completed. Their mechanism, error-destination, effort, and subgroup outputs are not treated
as findings. The report retains only results rebuilt from v3 and accepted by the final QA process.

## 11. Reproducibility and provenance

The v3 builder fixes the earlier nondeterministic parse join by following the scored parse exactly:
`scores.parsed_answer_id → parsed_answers.id → provider_attempts.id`. A reverse-order SQLite test
reproduces the three canonical data exports and metadata byte-for-byte. v3 preserves the v2
analytical population; it changes lineage code and metadata, not the accuracy observations.

Rebuild from the repository root:

- `uv run python data/experiment-31-07-26/analysis/build_analysis_data.py`
- `uv run python data/experiment-31-07-26/analysis/final_analysis.py`
- `uv run python data/experiment-31-07-26/analysis/build_report_artifact.py`

`dataset_meta.json` records SHA-256 hashes for the source workbook, flattened workbooks, run
database, builder, and canonical data exports. `final_analysis_results.json` pins the inputs used by
the report. Analysis v3.3 retains the v3.2 fixed-model group contrasts and adds deterministic
five-number summaries of their 100,000 whole-cluster bootstrap distributions without changing the
v3 population or canonical pairs. Superseded exploratory JSON files in the same directory may contain
v1 counts; they are not report sources.

Primary source artifacts:

- `experiment.sqlite` — run database and scored-attempt lineage
- `paired_clean.json` — canonical OpenRouter A/B pairs and exclusion flags
- `cross_arm_A.json` — canonical partial condition-A cross-arm pairs
- `dataset_meta.json` — v3 counts, exclusions, run status, and hashes
- `final_analysis_results.json` — compact recomputation used for this report
- `qa_workflows/` — independent audit records
- `../INVENTORY.md` — path-stable navigation across source data, execution records, release files,
  QA, and preserved exploratory work

Fifteen independently scoped QA workflows were completed. Their initial verdicts, corrective
actions, and final resolutions are summarized in `qa_workflows/QA_SUMMARY.md`. QA11 independently
recomputed the Experiment-A, Experiment-B, and paired A/B model comparisons. QA13 independently
recomputed every new requested-group estimate, interval, exact cluster test, and Holm family with
zero discrepancies. QA14 passed the grouped clinical-language, source-replay, and desktop/mobile
render checks after rejecting a stale interim HTML. QA15 passed the implementation,
deterministic-rebuild, fail-closed QA-state, preservation, and release-seal checks.
The v3.3.1 boxplot presentation repair is separately documented in `BOXPLOT_QA.md`: all 32 plotted
five-number summaries, eight SQLite/artifact datasets, visible whiskers/quartile boundaries/median
lines, native chart contracts, and desktop/mobile rendering passed. This implementation check is
not relabelled as a sixteenth independent workflow.

The required Snyk Code invocation could not authenticate (`SNYK-0005`, HTTP 401), so no Snyk pass
is claimed. `SECURITY_SCAN.md` records that limitation; Ruff and all 60 local tests passed.

## 12. Recommendations

1. Use the narrow conclusion: the observed B configuration has lower keyed-answer accuracy than A
   for these runs; pure text causation requires a no-time/no-routing-confounding assumption.
2. Run multiple validated paraphrase and keyed/unkeyed neutral-format controls before making a
   memorisation or general meta-option claim.
3. Replace `anteriores` with position-neutral wording and balance position if the meta-answer arm
   is repeated.
4. Pin OpenRouter providers and serving settings across arms.
5. For a retrieval claim, use a randomized same-stack retrieval-off/on factorial; merely completing
   GIFT A and B would estimate another pipeline-specific substitution contrast.
6. Use at least three independent runs per cell for stability claims.
7. Preserve a cited adjudication ledger for every medical-key exclusion.
8. For claims about size or model access, expand to a balanced `large/small × open/proprietary`
   panel with multiple independently selected models in every cell, preregister the classification,
   and treat model—not question—as the replication unit for model-class generalisation.
