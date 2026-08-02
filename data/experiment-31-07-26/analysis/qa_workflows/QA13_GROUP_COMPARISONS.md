# QA13 — adversarial audit of fixed-model group comparisons

**Reviewer role:** independent statistical and provenance QA  
**Canonical data:** `paired_clean.json` v3  
**Artifacts audited:** `REPORT.md`, `final_analysis_results.json`, and
`report_source.sqlite`  
**Analysis release audited:** `v3.2-final`  
**Verdict:** **PASS**

## Bottom line

I independently reconstructed every requested size-group, model-access-group, and secondary
triangulation result directly from `paired_clean.json`. I did not import `final_analysis.py` and
did not use the displayed report tables as calculation inputs.

The independently derived complete-case population, eight condition-specific group accuracies,
six primary grouped contrasts, four group-specific A-to-B declines, and six secondary tests all
match `final_analysis_results.json`. All 100,000-replicate whole-clinical-cluster percentile
intervals reproduce exactly from the pinned seeds and NumPy linear quantiles. Independent integer
convolution reproduces every exact clinical-cluster sign-flip p-value, and independent Holm
calculation reproduces all adjusted p-values. There are **zero numeric discrepancies**.

`REPORT.md` displays the same results at the stated precision. The six new SQLite tables have the
expected row counts and their numeric fields agree with the result bundle; SQLite
`PRAGMA integrity_check` returns `ok`. No statistical or narrative correction is required.

## 1. Population and estimand

Filtering the 1,691 canonical rows to `analysis_include == true` gives 1,271 cells across 318
items and 201 clinical clusters. Exactly one item is incomplete:

- `b320` contains gemini, qwen, and gemma results but no glm result;
- no included `(question_id, model)` pair is duplicated;
- all retained A and B outcomes are observed binary values; and
- each item has the same clinical-cluster identifier for every model.

Removing `b320` for all models yields the fair grouped-comparison population: **317 identical
items × 4 fixed models = 1,268 cells in 200 clinical clusters**. Every model contributes 317
items. Consequently, pooling cells within a requested group is algebraically identical to giving
each named model equal weight. No missing response is imputed or counted as wrong.

The audited estimand is the equal-weight mean keyed-answer accuracy across the named fixed models
and common items. It is not a population mean over randomly sampled models.

## 2. Independently reproduced group accuracies

| condition | requested group | correct / cells | accuracy | 100k whole-cluster bootstrap 95% CI |
|---|---|---:|---:|---:|
| A | large: gemini + glm | 605 / 634 | 95.43% | [93.38%, 97.13%] |
| A | small: qwen + gemma | 531 / 634 | 83.75% | [79.74%, 87.07%] |
| A | open-model: glm + qwen + gemma | 826 / 951 | 86.86% | [83.52%, 89.59%] |
| A | proprietary: gemini | 310 / 317 | 97.79% | [95.95%, 99.26%] |
| B | large: gemini + glm | 520 / 634 | 82.02% | [78.10%, 85.28%] |
| B | small: qwen + gemma | 419 / 634 | 66.09% | [61.11%, 70.62%] |
| B | open-model: glm + qwen + gemma | 656 / 951 | 68.98% | [64.51%, 72.92%] |
| B | proprietary: gemini | 283 / 317 | 89.27% | [85.47%, 92.56%] |

The slight difference between these group-specific singleton bootstrap limits and the earlier
model table's independently seeded limits is expected Monte Carlo variation; the point estimates
are identical. The group-specific limits exactly match the v3.2 result bundle.

## 3. Contrast construction and direction

I rebuilt each contrast from per-item binary outcomes before aggregating by clinical cluster.
Integer scaling preserves exact group means:

- size, scale 2: `(gemini + glm) − (qwen + gemma)`, divided by 2;
- model access, scale 3: `(glm + qwen + gemma) − 3 × gemini`, divided by 3;
- within-large, scale 1: `gemini − glm`;
- within-open, scale 2: `2 × glm − (qwen + gemma)`, divided by 2; and
- interaction tests apply the same contrast to each model's `B_correct − A_correct` change.

Thus all displayed directions and signs are correct. Resampling takes whole clinical clusters and
keeps repeated draws at their sampled multiplicity. The sign-flip calculation changes the sign of
the complete integer-scaled contribution of each nonzero clinical cluster; it never treats the
individual model-item rows inside a cluster as independent.

## 4. Six primary grouped tests

The primary family contains the two level contrasts in A, the two level contrasts in B, and the
two group-by-condition interactions. Holm correction is valid under dependence and is applied to
all six together as declared.

| test and direction | estimate | bootstrap 95% CI | nonzero clusters / scale | exact sign-flip p | Holm p |
|---|---:|---:|---:|---:|---:|
| A: large − small | +11.67 pp | [+8.79, +14.95] | 57 / 2 | 1.663530424522719e-13 | 6.654121698090876e-13 |
| A: open-model − proprietary | −10.94 pp | [−14.00, −8.36] | 63 / 3 | 1.365314111767546e-14 | 6.826570558837730e-14 |
| B: large − small | +15.93 pp | [+11.81, +20.14] | 104 / 2 | 1.884095680006461e-10 | 5.652287040019382e-10 |
| B: open-model − proprietary | −20.29 pp | [−24.51, −16.16] | 121 / 3 | 2.852824831561761e-17 | 1.711694898937057e-16 |
| `(large B−A) − (small B−A)` | +4.26 pp | [−0.38, +8.57] | 98 / 2 | 0.0924796432254102 | 0.0924796432254102 |
| `(open B−A) − (proprietary B−A)` | −9.36 pp | [−13.64, −4.94] | 110 / 3 | 0.0001606927767157373 | 0.0003213855534314745 |

The report's inference is correct: both requested groups differ at the A and B levels for these
fixed endpoints; the size-group difference in declines is unresolved; and the observed
model-access interaction is statistically detectable for this panel but cannot identify a
general access-class effect.

## 5. Four group-specific A-to-B declines

These four overlapping summaries form their own declared four-test Holm family.

| requested group | B − A | bootstrap 95% CI | nonzero clusters | exact sign-flip p | Holm p |
|---|---:|---:|---:|---:|---:|
| large | −13.41 pp | [−17.05, −10.18] | 67 | 4.837504718633798e-12 | 1.451251415590139e-11 |
| small | −17.67 pp | [−21.95, −13.26] | 101 | 5.665381451737212e-11 | 1.133076290347442e-10 |
| open-model | −17.88 pp | [−21.67, −14.16] | 110 | 1.101319896242292e-14 | 4.405279584969169e-14 |
| proprietary: gemini | −8.52 pp | [−12.31, −5.07] | 32 | 1.510046422481537e-05 | 1.510046422481537e-05 |

All four observed groups decline after their family-wise correction. The report correctly treats
the interaction contrasts—not the separate significance of each decline—as the relevant evidence
about differences in decline.

## 6. Six secondary triangulation tests

The secondary family holds one requested label partly fixed: gemini versus glm within the large
pair, and glm versus the qwen/gemma mean within the open-model subset. Holm correction is applied
across the six declared level and interaction tests.

| test and direction | estimate | bootstrap 95% CI | nonzero clusters / scale | exact sign-flip p | Holm p |
|---|---:|---:|---:|---:|---:|
| A: gemini − glm | +4.73 pp | [+1.92, +7.82] | 19 / 1 | 0.00331878662109375 | 0.0066375732421875 |
| B: gemini − glm | +14.51 pp | [+10.00, +19.32] | 49 / 1 | 2.443054469836170e-08 | 1.465832681901702e-07 |
| change interaction: gemini − glm | +9.78 pp | [+4.85, +14.96] | 49 / 1 | 0.0003751345676477058 | 0.001500538270590823 |
| A: glm − mean(qwen, gemma) | +9.31 pp | [+5.99, +12.90] | 55 / 2 | 2.110497600016359e-07 | 1.055248800008179e-06 |
| B: glm − mean(qwen, gemma) | +8.68 pp | [+3.80, +13.41] | 111 / 2 | 0.001398281778339018 | 0.004194845335017054 |
| change interaction: glm − mean(qwen, gemma) | −0.63 pp | [−6.18, +4.39] | 103 / 2 | 0.8587508675144084 | 0.8587508675144084 |

This supports the report's caution: the large/small labels do not behave like an identified
mechanism. Within the open-model subset, glm has higher level accuracy, but its decline is not
resolved from the small-open mean. Within the large pair, gemini has the smaller decline.

## 7. Statistical assumption and pseudoreplication audit

### Whole-cluster bootstrap

The percentile intervals correctly target cell/item-weighted risk differences while resampling
the top-level clinical clusters. All models are present on every common item, so group summaries
also give models equal weight. Unequal cluster sizes are retained through the ratio estimator.

### Exact sign flips

The p-values are exact only conditional on the report's stated cluster-level sign-exchangeability
null. They are not randomized-treatment p-values because model identity and group membership were
not randomized. `REPORT.md` states this explicitly in the statistical-method section.

### Fixed-model boundary

The report repeatedly and correctly prevents question-level replication from becoming model-class
replication:

- the four deployments are fixed rather than sampled from model classes;
- the size contrast has only two named endpoints per group;
- the proprietary category is gemini alone;
- there is no small proprietary endpoint, so size and access are not factorially separable;
- “open-model” is an analytical label rather than a license adjudication; and
- recommendations state that model, not question, is the replication unit needed for a general
  model-class claim.

Accordingly, the p-values quantify evidence over the analysed clinical-question clusters for these
exact endpoint bundles. The report does not claim a population-level large-model or
open/proprietary causal effect.

## 8. Artifact consistency

At audit time:

- `paired_clean.json` SHA-256:
  `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187`;
- `final_analysis.py` SHA-256:
  `af8908a2b3f057f63a1ea6ff2d3ffcd95b26ab787893ffe05aae6af9982c52fa`;
- both hashes match those embedded in `final_analysis_results.json`;
- `report_source.sqlite` integrity check is `ok`;
- SQLite row counts are 4 classifications, 2 A contrasts, 2 B contrasts, 4 declines, 2
  interactions, and 2 secondary summary rows; and
- every numeric SQLite field agrees with `final_analysis_results.json`; formatted intervals and
  p-values agree with `REPORT.md` at displayed precision.

The current report's grouping definitions, tables, physician-facing text, statistical-method
description, supported/not-supported claims, and follow-up recommendation are internally
consistent with the independently recomputed evidence.

## 9. Machine-checkable summary

All values below are proportions, not percentage points. Contrast directions are encoded in the
keys. `raw_p` is the exact two-sided whole-clinical-cluster sign-flip p-value.

```json
{
  "verdict": "PASS",
  "discrepancies": 0,
  "population": {
    "items": 317,
    "cells": 1268,
    "clinical_clusters": 200,
    "complete_case_exclusion": ["b320"]
  },
  "group_accuracy": {
    "A": {
      "large": {"correct": 605, "n": 634, "estimate": 0.9542586750788643, "ci95": [0.9338461538461539, 0.9713375796178344]},
      "small": {"correct": 531, "n": 634, "estimate": 0.8375394321766562, "ci95": [0.7973856209150327, 0.8706896551724138]},
      "open_model": {"correct": 826, "n": 951, "estimate": 0.868559411146162, "ci95": [0.8352197724542435, 0.895935062523214]},
      "proprietary": {"correct": 310, "n": 317, "estimate": 0.9779179810725552, "ci95": [0.9594594594594594, 0.9926470588235294]}
    },
    "B": {
      "large": {"correct": 520, "n": 634, "estimate": 0.8201892744479495, "ci95": [0.7810344827586206, 0.8527510572398594]},
      "small": {"correct": 419, "n": 634, "estimate": 0.6608832807570978, "ci95": [0.6111111111111112, 0.7062315429555465]},
      "open_model": {"correct": 656, "n": 951, "estimate": 0.6898002103049422, "ci95": [0.6450836901329139, 0.7292341805007897]},
      "proprietary": {"correct": 283, "n": 317, "estimate": 0.8927444794952681, "ci95": [0.8546712802768166, 0.9256198347107438]}
    }
  },
  "primary_family": {
    "a_size_large_minus_small": {"estimate": 0.1167192429022082, "ci95": [0.08789625360230548, 0.14948496420865148], "raw_p": 1.663530424522719e-13, "holm_p": 6.654121698090876e-13},
    "a_open_minus_proprietary": {"estimate": -0.10935856992639327, "ci95": [-0.13997636480272943, -0.08357341861184321], "raw_p": 1.365314111767546e-14, "holm_p": 6.82657055883773e-14},
    "b_size_large_minus_small": {"estimate": 0.15930599369085174, "ci95": [0.11807580174927114, 0.2013888888888889], "raw_p": 1.8840956800064606e-10, "holm_p": 5.652287040019382e-10},
    "b_open_minus_proprietary": {"estimate": -0.20294426919032596, "ci95": [-0.24509872194002946, -0.16161616161616163], "raw_p": 2.8528248315617606e-17, "holm_p": 1.7116948989370565e-16},
    "interaction_large_change_minus_small_change": {"estimate": 0.04258675078864353, "ci95": [-0.003787878787878788, 0.08567424710480184], "raw_p": 0.0924796432254102, "holm_p": 0.0924796432254102},
    "interaction_open_change_minus_proprietary_change": {"estimate": -0.0935856992639327, "ci95": [-0.13636363636363635, -0.049418539355189216], "raw_p": 0.00016069277671573726, "holm_p": 0.0003213855534314745}
  },
  "decline_family": {
    "large": {"estimate": -0.13406940063091483, "ci95": [-0.17054263565891473, -0.10176991150442478], "raw_p": 4.837504718633798e-12, "holm_p": 1.4512514155901393e-11},
    "small": {"estimate": -0.17665615141955837, "ci95": [-0.21954674220963172, -0.13262599469496023], "raw_p": 5.665381451737212e-11, "holm_p": 1.1330762903474424e-10},
    "open_model": {"estimate": -0.17875920084121977, "ci95": [-0.21671525753158405, -0.14163582531458185], "raw_p": 1.1013198962422923e-14, "holm_p": 4.4052795849691693e-14},
    "proprietary": {"estimate": -0.08517350157728706, "ci95": [-0.12307692307692308, -0.05067567567567568], "raw_p": 1.5100464224815369e-05, "holm_p": 1.5100464224815369e-05}
  },
  "secondary_family": {
    "a_gemini_minus_glm": {"estimate": 0.0473186119873817, "ci95": [0.019169329073482427, 0.07818987516380427], "raw_p": 0.00331878662109375, "holm_p": 0.0066375732421875},
    "b_gemini_minus_glm": {"estimate": 0.14511041009463724, "ci95": [0.1, 0.19318181818181818], "raw_p": 2.44305446983617e-08, "holm_p": 1.465832681901702e-07},
    "interaction_gemini_minus_glm": {"estimate": 0.09779179810725552, "ci95": [0.048517268777406766, 0.14963503649635038], "raw_p": 0.0003751345676477058, "holm_p": 0.0015005382705908232},
    "a_glm_minus_small_open_mean": {"estimate": 0.09305993690851735, "ci95": [0.059870550161812294, 0.12896842924448929], "raw_p": 2.110497600016359e-07, "holm_p": 1.0552488000081794e-06},
    "b_glm_minus_small_open_mean": {"estimate": 0.08675078864353312, "ci95": [0.03804347826086957, 0.13414634146341464], "raw_p": 0.001398281778339018, "holm_p": 0.004194845335017054},
    "interaction_glm_minus_small_open_mean": {"estimate": -0.006309148264984227, "ci95": [-0.061837455830388695, 0.043882978723404256], "raw_p": 0.8587508675144084, "holm_p": 0.8587508675144084}
  }
}
```

## Final verdict

**PASS.** The v3.2 grouped comparisons are numerically correct, use a coherent common population
and equal-model estimand, preserve cluster structure in intervals and tests, apply the declared
Holm families correctly, and state the sign-exchangeability and fixed-model limitations needed to
prevent pseudoreplication or model-class overclaim. No canonical code or report was modified by
this audit. This QA record should be added to the QA summary, rebuilt report artifact/HTML, and
final release manifest during release integration.
