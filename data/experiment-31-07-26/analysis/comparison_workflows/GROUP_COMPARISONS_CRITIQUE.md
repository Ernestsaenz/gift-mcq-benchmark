# Adversarial critique: model-size and openness group comparisons

**Scope.** This review concerns the requested comparisons of (1) gemini + glm versus qwen +
gemma and (2) glm + qwen + gemma versus gemini. It inspects the canonical v3.1 complete-case
results and focuses on what the data can and cannot support. It does not modify the report or
analysis code.

## Bottom line

The proposed group averages are useful **descriptive contrasts among these four deployed model
configurations**. They are not estimates of a general effect of model size or licensing/openness.
The attributes live at the model level, where there are only four non-randomly selected endpoints;
317 repeated questions do not create 317 independent examples of a “large,” “small,” “open,” or
“proprietary” model.

The report may test fixed contrasts over the sampled clinical-question clusters, provided it says
exactly that. It should not interpret the resulting p-values as evidence that increasing size or
changing licensing status caused the performance difference.

## 1. Requested grouping is an incomplete 2 × 2 design

Use a membership table prominently:

| requester-defined size group | requester-defined open-model group | proprietary endpoint |
|---|---|---|
| larger | glm | gemini |
| smaller | qwen, gemma | **none** |

Consequences:

1. There is no smaller proprietary model, so a size × openness factorial interaction cannot be
   estimated.
2. “Larger versus smaller” is a contrast of two named pairs, not a size effect. It is entangled
   with model family, training, architecture, post-training, routing, and other configuration
   differences.
3. “Open versus proprietary” is literally one named endpoint (gemini) versus the mean of three
   different endpoints. It is inseparable from gemini's model identity and partly entangled with
   the requested size grouping.
4. A two-factor regression on all item-level rows would give spuriously impressive category-level
   precision. The repeated questions help estimate these exact deployments over this item bank;
   they do not increase the number of independently sampled models beyond four.

No causal wording such as “larger models perform better,” “open models are worse,” or “proprietary
models are more robust” is justified.

## 2. Terminology must be qualified

Use **“requester-defined larger-model pair”** and **“requester-defined smaller-model pair.”** The
artifacts do not contain a validated, common size measure. Total parameters, active parameters in
mixture-of-experts models, inference compute, and an undisclosed proprietary parameter count are
not interchangeable.

Use **“requester-defined open-model group”**, not “open-source models,” unless every exact version's
license, source availability, weight availability, and redistribution terms are separately sourced
and audited. Weight availability is not the same construct as OSI-style open source, and model
ownership is not the same as distribution/licensing status. Define the grouping explicitly:

> For this exploratory analysis only, the requester classified glm, qwen, and gemma as the
> open-model group and gemini as the proprietary endpoint; this study did not independently audit
> model licenses or training-source openness.

This language honors the requested grouping without turning it into an unsupported licensing fact.

## 3. Independent descriptive spot-check

The values below are equal-weighted means of the named models on the canonical common set of 317
items and 200 clinical clusters. Equal model weighting is essential; do not let a missing cell or a
model with more rows change group weights.

| condition | larger-pair mean | smaller-pair mean | larger − smaller | open-model mean | gemini | open − gemini |
|---|---:|---:|---:|---:|---:|---:|
| A | 95.43% | 83.75% | +11.67 pp | 86.86% | 97.79% | −10.94 pp |
| B | 82.02% | 66.09% | +15.93 pp | 68.98% | 89.27% | −20.29 pp |

These arithmetic checks reproduce the group means implied by
`final_analysis_results.json`. They should be labelled exploratory fixed-configuration summaries.

On the percentage-point scale, the B − A loss is about −13.41 points for the larger pair and
−17.67 for the smaller pair, a +4.26-point difference-in-differences. The open-model mean loses
about −17.88 points versus −8.52 for gemini, a −9.36-point difference-in-differences. Those
differences must **not** be called group “robustness” effects: gemini begins at a 97.8% ceiling, and
the previously approved analysis already shows model heterogeneity is estimand-dependent.

Indeed, the individual B-versus-A log odds changes run in the opposite descriptive direction from
the naive percentage-point robustness story: approximately −1.67 for gemini, −1.51 for glm,
−1.05 for qwen, and −0.94 for gemma. Thus the apparently smaller percentage-point loss for gemini
or the larger pair does not establish less proportional degradation.

## 4. Defensible statistical target and tests

If added, state the estimand as:

> the equal-model-weighted accuracy contrast among these prespecified deployed configurations over
> the analysed clinical-question clusters.

Use the identical 317-item complete-case set for all group comparisons. Suitable calculations are:

1. **Within A and within B:** for each item, form
   `0.5(gemini + glm) − 0.5(qwen + gemma)` and
   `(glm + qwen + gemma)/3 − gemini`.
2. **Differential A/B change:** form those same contrasts on each model's paired `B − A` outcome.
3. Estimate percentage-point magnitudes with 100,000 whole-clinical-cluster bootstrap intervals,
   preserving cluster multiplicity.
4. Use either an explicitly specified CR1 cluster-robust linear contrast or the report's exact
   whole-cluster sign-flip test. State the sign-exchangeability assumption if sign flips are used.
5. Adjust for the newly introduced exploratory contrasts. At minimum, Holm-adjust the size and
   openness contrasts together within A, within B, and within the A/B-change family. If the
   within-open sensitivity below receives a p-value, include it in the relevant family rather than
   treating it as an uncorrected extra test.

Report the sampling units correctly:

- size summary: **2 named models versus 2 named models**, evaluated on 317 items in 200 clusters;
- openness summary: **3 named models versus 1 named model**, evaluated on the same items/clusters.

Do not report `n = 634 versus 634` or `n = 951 versus 317` as if those were independent model-level
sample sizes. A hierarchical “random model” analysis is not credible with four selected models,
one proprietary model, and an empty smaller-proprietary cell.

## 5. The most useful additional comparison

Add one clearly labelled triangulation, preferably descriptive:

**Within the requested open-model group, compare glm with the equal-weighted qwen/gemma mean.**
This holds the requested openness label constant, although it still compares one named model with
two others and therefore does not identify a causal size effect.

The canonical arithmetic is:

- A: glm exceeds the qwen/gemma mean by **9.31 points**;
- B: glm exceeds the qwen/gemma mean by **8.68 points**;
- difference in B − A change: approximately **−0.63 points**.

This is substantively important because it shows that the apparent larger-pair advantage in
percentage-point A/B resilience is driven by the category composition, especially gemini, rather
than reproduced within the open-model subset.

Also retain the individual-model results adjacent to any group table. The open-model group is
heterogeneous: all three members separate in A; in B, glm and qwen are unresolved while both
exceed gemma. A single open-group mean otherwise hides a clinically meaningful performance range.

Avoid adding latency, token, GIFT-B, or broad subgroup comparisons here. Latency/tokens have known
measurement and serving confounds, GIFT B was never run, and more post-hoc contrasts would invite
fishing without answering the user's group question.

## 6. Clinician-facing wording

Recommended language under each group section:

> On this examination benchmark, the two deployments classified by the requester as larger had a
> higher equal-weighted average key-agreement rate than the two classified as smaller. This is a
> comparison of four selected systems across the same questions, not evidence that model size
> itself caused the difference. The study contains too few independently sampled models—and no
> smaller proprietary model—to separate size, licensing/access, and model-family effects.

For openness:

> Gemini scored above the average of the three deployments placed in the requester-defined
> open-model group. Because the proprietary group contains only gemini, this is best read as
> “gemini versus these three named alternatives,” not as a general proprietary-versus-open result.

For the A/B group change:

> Percentage-point losses differed between the named groups, but the conclusion changes with the
> statistical scale because models started at very different baseline accuracies. The result does
> not show that either size or openness protects a model from the engineered answer-format change.

Every paragraph should reiterate that keyed-answer agreement is not diagnostic accuracy, patient
benefit, or bedside safety.

## 7. Release acceptance criteria

The group section passes adversarial review only if all of the following are true:

- the membership table exposes the empty smaller-proprietary cell;
- the labels are explicitly requester-defined and “open-model,” not an unaudited “open-source”
  licensing claim;
- equal model weighting and the 317-item/200-cluster common set are stated;
- CIs/p-values resample or robustly cluster whole clinical cases;
- new post-hoc tests receive an explicit multiplicity correction;
- the inferential target is the four named deployments, not all large/small/open/proprietary models;
- percentage-point difference-in-differences is not called robustness without the scale-dependence
  warning;
- individual models remain visible, especially the heterogeneity within the open-model group;
- clinician text distinguishes exam-key agreement from clinical performance.

**Adversarial verdict:** include the requested comparisons as exploratory, fixed-configuration
contrasts with the limitations above. Reject any causal or class-general claim about size or
openness.
