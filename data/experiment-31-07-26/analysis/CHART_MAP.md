# Report chart map

The report combines native portable-artifact bars for observed magnitudes with annotated native
boxplots for uncertainty. Every boxplot summarizes 100,000 whole-clinical-cluster bootstrap ratio
estimates: the label gives the observed estimate, whisker caps mark the minimum and maximum, the
outlined box spans Q1–Q3, and the dark internal divider marks the median. The tooltip repeats all
five values. These are sampling distributions, not raw binary-answer
distributions. Exact denominators, 95% intervals, and tests remain in the adjacent tables.

| Chart | Analytical question | Fields | Canonical source | Why this form |
|---|---|---|---|---|
| Experiment A model accuracy | How do the four models compare on the original-answer condition? | `model`, `accuracy` | `condition_a_models` in `report_source.sqlite` | A common-zero bar chart makes four discrete accuracy levels easy to compare; the table supplies intervals and pairwise tests. |
| Experiment B model accuracy | How do the same models compare under the engineered meta-answer? | `model`, `accuracy` | `condition_b_models` | The same encoding supports direct visual comparison with A; the table identifies the unresolved glm–qwen contrast. |
| Paired A versus B accuracy | How does each model move from A to B? | `model`, `condition`, `accuracy` | `primary_accuracy` | Grouped bars show the within-model direction while preserving model baselines. |
| Cleaning sensitivity | Does the pooled A/B contrast depend on exclusions? | `exclusions`, `change` | `sensitivity` | Signed bars show that every specification remains below zero. |
| Partial cross-pipeline comparison | Does GIFT-served minus OpenRouter-served accuracy have the same direction for every model? | `model`, `change` | `cross_arm_chart` | Signed bars expose the model-specific sign reversal that a pooled summary hides. |
| Experiment A model bootstrap boxplot | How much sampling uncertainty surrounds each Experiment-A model accuracy? | `display_label`, `minimum`, `q1`, `median`, `q3`, `maximum` | `condition_a_model_boxplot` | Four aligned bootstrap distributions complement the omnibus and pairwise table. |
| Experiment A group bootstrap boxplot | How do uncertainty distributions compare for the requested fixed-model groups? | same five-number fields plus observed estimate and test annotation | `condition_a_group_boxplot` | Separate annotated rows expose uncertainty while the subtitle warns that size and access groups overlap. |
| Experiment B model bootstrap boxplot | How much sampling uncertainty surrounds each Experiment-B model accuracy? | same five-number fields | `condition_b_model_boxplot` | The same scale and grain support direct comparison with Experiment A. |
| Experiment B group bootstrap boxplot | How do the requested group accuracies vary under whole-cluster resampling? | same five-number fields | `condition_b_group_boxplot` | The chart complements, rather than replaces, the fixed-model group tests. |
| Model A-to-B change boxplot | How much uncertainty surrounds each model-specific B-minus-A change? | same five-number fields; signed observed estimate | `primary_model_change_boxplot` | Signed bootstrap distributions show that all four model changes remain below zero. |
| Group A-to-B change boxplot | How much uncertainty surrounds each requested group's B-minus-A change? | same five-number fields; signed observed estimate | `group_change_boxplot` | Four annotated rows show the overlapping group summaries without implying independent model samples. |
| Interaction boxplot | Which primary and secondary differences in A-to-B changes are resolved? | same five-number fields; signed interaction estimate | `group_interaction_boxplot` | A shared signed scale with zero in view makes unresolved versus resolved interactions visually legible; tables govern inference. |
| Partial GIFT/OpenRouter boxplot | How much uncertainty surrounds each observed-subset pipeline difference? | same five-number fields; signed observed estimate | `cross_arm_boxplot` | Model-specific distributions preserve the sign reversal and the adjacent text preserves the missing-coverage caveat. |

Accuracy charts use percent formatting and a zero baseline. Signed difference charts place zero at
the reference line. None of the charts substitutes for the cluster-aware statistical tables.

## Group-comparison display decision

The v3.3.1 boxplot presentation repair adds visible five-number geometry without treating the four
displayed group means as four disjoint categories. The same models reappear under two overlapping classifications, and the
proprietary row contains gemini alone. The group plots therefore use neutral, individually labeled
rows and repeat the overlap/singleton caveat; they do not use stacked or compositional encodings.
The tables still preserve the contrast direction, model count, confidence interval,
multiplicity-adjusted p-value, and fixed-model boundary.
