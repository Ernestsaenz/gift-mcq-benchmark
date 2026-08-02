# Independent synthesis — Experiment A versus Experiment B

**Scope:** report architecture, the within-model paired A↔B section, denominator policy, and
physician-facing interpretation.  
**Evidence used:** the canonical v3 `final_analysis_results.json` and the accepted findings in
`QA03_PRIMARY_STATS.md`, `QA04_RESAMPLING.md`, `QA05_SENSITIVITY.md`,
`QA08_CONSTRUCT_VALIDITY.md`, and `QA10_RELEASE_CANDIDATE.md`.  
**Canonical artifacts changed:** none.

## Recommendation

The report should put the model comparisons in this order:

1. **Experiment A: comparison between models.** This answers which of the four fixed model
   endpoints most often agreed with the benchmark key under the original MCQ format.
2. **Experiment B: comparison between models.** This repeats the same comparison after the
   substantive keyed option was replaced by the fixed, position-dependent preceding-options
   meta-answer.
3. **Experiment A versus B: paired change within each model.** This is the principal experimental
   contrast. Each item/model result in A is paired with that same item/model result in B.

This order separates two different questions. Sections 1 and 2 compare models *within one
condition*; section 3 compares conditions *within a model*. A reader should not infer the third
question merely by comparing two rankings or by inspecting whether two separate confidence
intervals overlap.

## Denominator policy for the three sections

Use the cleaned, B-eligible analytical population throughout. Do not use all 474 A items in the
first section and the 318 paired items later: that would make the apparent A→B movement partly a
change in item composition.

| section | recommended inferential population | reason |
|---|---:|---|
| A, between models | 317 items × 4 models = 1,268 outputs; 200 clinical clusters | The one item lacking an A result for glm (`b320`) is removed from all four models, so every model is compared on exactly the same questions. |
| B, between models | the same 317 items × 4 models = 1,268 outputs; the same 200 clusters | Keeps the B ranking directly comparable to the A ranking and to its inferential test. |
| A↔B, within model | 318 pairs for gemini, qwen, and gemma; 317 for glm; 1,271 pairs pooled; 201 clusters pooled | Uses every observed matched A/B pair for effect estimation. The glm denominator is one smaller because its A response for `b320` was never recovered. |

On the common 317-item set, the descriptive counts that should underpin the first two sections are:

| model | A correct / 317 | A accuracy | B correct / 317 | B accuracy |
|---|---:|---:|---:|---:|
| gemini-3.6-flash | 310 | 97.79% | 283 | 89.27% |
| glm-5.2 | 295 | 93.06% | 237 | 74.76% |
| qwen3.6-35b-a3b | 280 | 88.33% | 230 | 72.56% |
| gemma-4-26b-a4b-it | 251 | 79.18% | 189 | 59.62% |

These common-set values are for fair four-model comparisons. The third section should retain the
canonical pair-specific denominators and values below. The one-item difference must be stated so
readers do not mistake a denominator change for an inconsistency.

For the A-only and B-only omnibus comparisons, use a binary-outcome model with a model factor and
clinical-cluster-robust covariance. Pairwise model contrasts should compare models on shared items,
retain clinical clustering, and use Holm correction across the six model pairs. A conventional
one-way ANOVA is inappropriate; an ordinary chi-square test would incorrectly treat correlated
model responses to the same items as independent. Cochran's Q or pairwise McNemar can be shown as
secondary item-paired checks only if their failure to represent the higher clinical clusters is
made explicit.

## Draft report section 3 — Experiment A versus Experiment B

### Experiment A versus B: paired change within each model

This comparison asks whether each model's benchmark-key agreement changed when the *same eligible
question* moved from A to B. Risk difference is defined as `B minus A`, so a negative number means
lower accuracy in B. Confidence intervals were obtained by resampling whole clinical clusters
100,000 times. The primary p-values are exact clinical-cluster sign-flip tests; the four
model-specific p-values are Holm-adjusted as one family.

| model | paired n | A correct | B correct | A accuracy | B accuracy | change, B−A | whole-cluster bootstrap 95% CI | exact cluster sign-flip p | Holm p across 4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 318 | 311 | 284 | 97.80% | 89.31% | **−8.49 pp** | [−12.26, −5.01] | 1.51 × 10⁻⁵ | 1.51 × 10⁻⁵ |
| glm-5.2 | 317 | 295 | 237 | 93.06% | 74.76% | **−18.30 pp** | [−23.33, −13.74] | 5.28 × 10⁻¹¹ | 2.11 × 10⁻¹⁰ |
| qwen3.6-35b-a3b | 318 | 281 | 231 | 88.36% | 72.64% | **−15.72 pp** | [−20.69, −10.75] | 1.80 × 10⁻⁷ | 5.39 × 10⁻⁷ |
| gemma-4-26b-a4b-it | 318 | 251 | 189 | 78.93% | 59.43% | **−19.50 pp** | [−26.06, −12.81] | 3.14 × 10⁻⁷ | 6.27 × 10⁻⁷ |
| **cell-weighted pooled** | **1,271** | **1,138** | **941** | **89.54%** | **74.04%** | **−15.50 pp** | **[−18.78, −12.39]** | **1.95 × 10⁻¹⁵** | — |

All four model-specific contrasts are negative, their cluster-bootstrap intervals exclude zero,
and all four exact cluster sign-flip tests remain significant after Holm correction. The pooled
estimate is a descriptive, cell-weighted summary of these four named model endpoints rather than
an estimate for a population of future models.

The corresponding ordinary exact McNemar p-values are 3.47 × 10⁻⁶ (gemini),
1.81 × 10⁻¹² (glm), 1.41 × 10⁻⁸ (qwen), and 1.66 × 10⁻¹⁰ (gemma).
They are useful secondary checks of discordant pairs, but they treat item/model pairs as
independent and therefore should not replace the clinical-cluster sign-flip tests. The stacked
pooled McNemar value, 8.68 × 10⁻³⁴, is diagnostic only because it additionally reuses each item
across four models.

A model-adjusted logistic sensitivity analysis estimated an odds ratio of **0.314** for B versus A
(cluster-robust 95% CI **0.247–0.399**, p = **3.36 × 10⁻²¹**). This corresponds to 68.6% lower
odds of a keyed-correct response under the observed B configuration, after adjustment for the four
model indicators. It is a secondary odds-scale summary; the percentage-point changes above remain
the clinically clearest estimands.

The sizes of the percentage-point changes differ across models (clinical-cluster covariance Wald
p = **0.000293**). This is not a scale-independent robustness ranking. Interaction evidence is
weaker on conditional log-odds scales (LRT p = **0.201**; cluster-robust Wald p = **0.123**) and is
borderline in a marginal-logit robust test (p = **0.0438**). State that heterogeneity depends on
the estimand and model, not that robustness is equal or that one model is definitively most robust.

#### Explanation for a clinical doctor

Think of each question as its own matched case. A model answers that same case once in the original
format and once after the keyed option has been replaced. This is analogous to a paired study:
within-question comparison removes differences caused simply by one model receiving an easier set
of cases than another.

The most direct result is the absolute change in correct answers. Across the four systems, B was
about **15.5 fewer keyed-correct answers per 100 attempts** than A; the model-specific losses ranged
from about **8.5 to 19.5 per 100**. The pooled 95% interval, approximately **12.4 to 18.8 fewer per
100**, expresses the uncertainty produced by sampling clinical question clusters. The very small
p-value says that a contrast this one-sided would be extremely unusual under the sign-exchangeable
no-difference model; it does not measure clinical importance, bias, or bedside safety.

This endpoint is **agreement with the benchmark key**, not diagnostic accuracy in real patients.
It also does not prove that the models memorised the original answers. B changes several things at
once: it removes the substantive keyed answer, inserts a repeated and position-dependent
meta-answer, changes the answer's semantics and genre, and was run at a different time without
pinned physical provider routing. The defensible conclusion is that observed keyed-answer
performance was lower under this bundled B configuration for all four fixed model endpoints.

#### Why no normality test is needed

Each response is binary—keyed-correct or not—and each paired change can only be `−1`, `0`, or `+1`.
Those values cannot follow a continuous normal distribution. Shapiro–Wilk testing or a normal Q–Q
plot would therefore answer the wrong question. The selected methods are designed for paired
binary data and do not assume normal 0/1 outcomes: whole-cluster bootstrap intervals, exact
clinical-cluster sign flips, McNemar checks, and logistic regression with cluster-robust
covariance. Their important assumptions concern the independence and exchangeability of the
top-level clinical clusters, not normality of individual answers.

## Physician explanations below sections 1 and 2

The report can keep these short, leaving the fuller causal boundary to section 3.

### Below Experiment A

> **For a clinical reader:** Experiment A is the conventional exam-format benchmark. The
> percentages show how often each fixed model endpoint selected the supplied answer key on the
> same 317-question comparison set. This ranks benchmark performance under this prompt and run; it
> is not a patient-level sensitivity, specificity, calibration measure, or proof that every source
> key is current clinical truth. The omnibus test asks whether the observed model differences are
> larger than expected under equal model performance while accounting for related clinical
> question clusters.

### Below Experiment B

> **For a clinical reader:** Experiment B uses the same comparison cases but replaces the
> substantive keyed answer with a recurring, position-dependent meta-answer. The percentages rank
> benchmark-key agreement under that artificial answer format. They should not be read as general
> diagnostic competence or ordinary none-of-the-above performance. The omnibus test again asks
> whether models differ within this condition; it does not explain why their performance changed
> from A.

## Reporting guardrails

- Call the outcome **benchmark-key agreement** or **keyed-answer accuracy**; the medical truth of
  every retained source key was not independently re-adjudicated.
- Show correct counts as well as percentages and name the denominator immediately above each table.
- Keep each inferential label beside its estimate: whole-cluster bootstrap for intervals; exact
  clinical-cluster sign flip for paired A↔B p-values; cluster-robust binary regression or an
  equivalent cluster-aware procedure for within-condition model comparisons.
- Do not use overlapping or non-overlapping marginal confidence intervals as a model-comparison
  test.
- Keep Holm adjustment explicit: six pairwise model comparisons within A, six within B, and four
  predeclared within-model A↔B tests are separate families unless a broader family is deliberately
  defined.
- Do not call the A↔B result proof of memorisation, lexical recognition, increased reasoning
  burden, general NOTA ability, or a pure causal text effect.
- Do not mix the partial GIFT-served comparison into these three OpenRouter sections. It is a
  separate condition-A, selected-complete-case pipeline comparison, and GIFT B was never run.

## Independent synthesis verdict

The approved data support a strong and clinically understandable paired A↔B finding. The best
main table should replace ordinary McNemar with the cluster-aware sign-flip p-values while retaining
McNemar as a labelled sensitivity check. The A-only and B-only sections must use the same
317-item/200-cluster complete-case set for fair between-model tests; the A↔B section should use all
1,271 available matched pairs. Normality testing is neither required nor meaningful for this binary
endpoint.
