# Grouping tests — open vs closed weights; big vs small

**Owner:** Agent 3 (groupings). **Script:** `../scripts/03_groupings.py`.
**Raw output:** `groupings_open_closed_primary.csv`, `groupings_open_closed_secondary.csv`,
`groupings_summary.json`. **Taxonomy / audit trail:** `MODEL_TAXONOMY.md`.
Written 2026-08-07.

**Read this before the numbers below:** both requested groupings are
methodologically fragile by design (see `MODEL_TAXONOMY.md`). Big-vs-small
was declined outright. Open-vs-closed was computed, but every number in this
file describing it is a comparison of **one model against three**, not a
comparison of two populations. That fact is repeated on every result below,
not just here, because it changes what each number can be used for.

---

## 1. Big vs small — INFEASIBLE, not computed

No statistical test was run for this grouping. Two of the four models
(`z-ai/glm-5.2`, `google/gemini-3.6-flash`) have no defensible parameter
count established anywhere in this repo, and restricting to the two MoE
models with published counts does not rescue a binary label: gemma is
bigger by active parameters (4B vs 3B) while qwen is bigger by total
parameters (35B vs 26B) — the ordering inverts depending on which size
metric is used. Full reasoning in `MODEL_TAXONOMY.md`. **No results table
follows for this grouping.**

---

## 2. Open vs closed weights

**Groups, per `MODEL_TAXONOMY.md`:**
- closed: `google/gemini-3.6-flash` — **n_models_closed = 1**
- open: `google/gemma-4-26b-a4b-it`, `qwen/qwen3.6-35b-a3b`, `z-ai/glm-5.2` — **n_models_open = 3**

> **The confound, stated once in full so it doesn't need re-deriving at
> every row below:** with n_models_closed = 1, there is exactly one
> model's worth of information in the closed group. Cluster-robust
> standard errors (clustered on question) correct for the fact that a
> question contributes multiple correlated cells; they do **not**, and
> cannot, correct for the fact that "closed" and "gemini" are the same
> partition of the data. Every effect size and p-value below is
> mathematically a **gemini-vs-the-other-three comparison**. A significant
> result is evidence about gemini specifically. It is not evidence that
> open-weight models as a class perform differently from closed-weight
> models as a class — that claim would need multiple models per group,
> which this dataset does not have.

### 2.1 Primary outcome — run-1 `strict_correct`, 6000 cells (clean, uncontaminated by the Vertex deviation)

Method: cluster-robust logistic regression (GEE, exchangeable working
correlation, cluster = `question_id`, 500 clusters; pooled model additionally
adjusts for `arm` as a fixed effect since arm is not exchangeable per
STATS_SPEC). Risk difference = open − closed with a question-level cluster
bootstrap 95% CI (5000 resamples). Odds ratio from the GEE coefficient.
Cross-check: question-level Monte Carlo sign-flip permutation test (20,000
resamples) on the per-question (open mean − closed) difference — this is
model-free and doesn't rely on GEE's asymptotics, included because
n_models_closed = 1 makes it worth confirming the GEE result isn't an
artifact of the working-correlation assumption.

**Holm family:** {pooled (arm-adjusted), openrouter_A, openrouter_B, tailscale_A, condition_A_all_arms} — 5 tests, strict_correct outcome only. `condition_A_all_arms` (openrouter_A + tailscale_A, arm-adjusted) is added at the team lead's request so condition can be read off directly; it mixes provider with condition (see note under the table) and is reported for descriptive completeness — the clean, provider-fixed condition contrast is the `openrouter_A` vs `openrouter_B` row pair, which is why section 2.3 below restricts to those two rows for the condition-gap figure.

| Scope | n cells (open / closed) | n models (open / closed) | Open accuracy | Closed (gemini) accuracy | Risk diff. (open−closed) | 95% CI | Odds ratio | 95% CI | GEE Wald p | **Holm p** | Sign-flip p |
|---|---|---|---|---|---:|---|---:|---|---:|---:|---:|
| Pooled (arm-adjusted) | 4500 / 1500 | 3 / 1 | 81.6% | 95.2% | −13.6 pp | [−15.4, −11.8] | 0.212 | [0.161, 0.278] | 1.08×10⁻²⁸ | **5.42×10⁻²⁸** | 0.00005 |
| openrouter_A | 1500 / 500 | 3 / 1 | 87.1% | 98.2% | −11.1 pp | [−13.3, −9.0] | 0.123 | [0.065, 0.234] | 1.57×10⁻¹⁰ | **3.14×10⁻¹⁰** | 0.00005 |
| openrouter_B | 1500 / 500 | 3 / 1 | 67.9% | 90.0% | −22.1 pp | [−25.3, −19.0] | 0.235 | [0.178, 0.309] | 3.41×10⁻²⁵ | **1.37×10⁻²⁴** | 0.00005 |
| tailscale_A | 1500 / 500 | 3 / 1 | 90.0% | 97.4% | −7.4 pp | [−9.3, −5.6] | 0.240 | [0.144, 0.400] | 4.09×10⁻⁸ | **4.09×10⁻⁸** | 0.00005 |
| condition_A_all_arms ⁽ᵖʳᵒᵛ⁾ | 3000 / 1000 | 3 / 1 | 88.5% | 97.8% | −9.3 pp | [−11.1, −7.5] | 0.173 | [0.102, 0.292] | 6.22×10⁻¹¹ | **1.86×10⁻¹⁰** | 0.00005 |

⁽ᵖʳᵒᵛ⁾ Pools `openrouter_A` and `tailscale_A` — i.e. condition A across **both** providers, mixing provider with condition. Reported for completeness at the team lead's request; do not read this row as a clean condition-A estimate — see section 2.3 for the provider-fixed version.

**Reading this table correctly:** gemini scores higher than the pooled
open-model average in every arm, by a wide and consistent margin, and the
sign-flip permutation test (which makes no distributional assumption and
would not "know" about the GEE model) agrees at p ≈ 0.00005 in all four
rows — so this is not a fragile result driven by a modeling choice. **What
it does not show:** it does not show that closed-weight licensing causes
better performance, or that open-weight models in general trail closed
ones. It shows that this specific proprietary model outperformed this
specific set of three open models on this specific 500-question set, across
all three arms, by margins from 7 to 22 percentage points depending on arm.
The gap is largest in `openrouter_B` (−22.1 pp). Per STATS_SPEC.md, condition
B is not a generic "harder" condition — it is a **none-of-the-above (NOTA)
manipulation**: the substantive correct option is replaced by "Ninguna de
las respuestas anteriores es correcta" in the same letter slot, so scoring
correct in B requires rejecting every plausible-sounding distractor rather
than recognising a plausible correct statement. Gemini's relative advantage
over the pooled open group roughly doubles under this NOTA manipulation
(−11.1 pp in A → −22.1 pp in B), i.e. the three open models lose
disproportionately more accuracy than gemini specifically when the task
switches from "pick the right answer" to "recognise that none of the listed
answers is right." That is a substantive, gemini-vs-open-three finding worth
flagging for the primary per-model analysis (agent 2 / stats-primary), but
it remains a statement about these four named models' NOTA-handling, not
about open-weight models as a class.

### 2.2 Secondary outcome — flip rate on replicate cells (stability, conditioned on failing run 1)

This uses the 1788 scored replicate attempts (of 1796 logical calls; 8
exhausted the retry ceiling and are excluded, per STATS_SPEC). By
construction every row here is conditioned on the model having gotten the
question wrong on run 1, so regression to the mean applies and these are
**not** general accuracy estimates — a cell can only "flip" from wrong to
right, never the reverse, because correct run-1 cells were never
replicated (STATS_SPEC, 5102 correct cells unmeasured for this direction).
Per STATS_SPEC, the run-1-incorrect (replicated) cells are also not evenly
split across conditions — `openrouter_B` (the NOTA condition, section 2.1)
contributes far more of the 898 replicated cells (532) than `openrouter_A`
(203), consistent with the `n_cells` column below (`openrouter_B` main row
has roughly 2.5x the replicate volume of `openrouter_A`). Any pooled
statement in this table is therefore weighted toward NOTA items, on top of
everything else caveated here.

**Second, arm-specific confound on top of the group confound (2.1):**
gemini is simultaneously (a) the entire closed group and (b) the only model
touched by the Vertex protocol deviation, and the deviation is concentrated
almost entirely in `openrouter_B` (91 of gemini's 93 scored `openrouter_B`
replicate cells were served via `google-vertex`, which silently drops
`temperature=0`). That means in the replicate data, the open/closed
contrast in `openrouter_B` and the Vertex-deviation contrast are **the same
split of the data** — excluding the 91 Vertex cells doesn't just clean the
data, it removes 91 of the closed group's 93 `openrouter_B` cells, leaving
n_cells_closed = 2. Both variants are reported below; neither should be
read as a clean estimate.

**Holm family (main variant only, n=5):** {pooled (arm-adjusted), openrouter_A, openrouter_B, tailscale_A, condition_A_all_arms}, strict_correct-of-replicate outcome. The Vertex-exclusion variant is a **robustness check on the same hypotheses**, not an added family member, and is not separately Holm-corrected — reported alongside for comparison per the mandatory sensitivity requirement. `condition_A_all_arms` carries the same provider-mixing caveat as in 2.1.

| Scope | Sensitivity | n cells (open/closed) | Open flip rate | Closed (gemini) flip rate | Risk diff. | 95% CI | Odds ratio | GEE Wald p | **Holm p** | Sign-flip p |
|---|---|---|---:|---:|---:|---|---:|---:|---:|---:|
| Pooled (arm-adj.) | main | 1651 / 137 | 13.6% | 11.7% | +1.9 pp | [−5.7, +8.5] | 1.01 | 0.987 | **0.987** | 0.947 |
| Pooled (arm-adj.) | excl. 91 Vertex | 1651 / 46 | 13.6% | 8.7% | +4.9 pp | [−7.3, +13.9] | 1.84 | 0.371 | not corrected¹ | 0.943 |
| openrouter_A | main | 388 / 18 | 19.8% | **0.0%** | +19.8 pp | [+14.8, +25.3] | undefined² | undefined² | undefined² | 0.062 |
| openrouter_A | excl. Vertex (no change: A has none) | 388 / 18 | 19.8% | 0.0% | +19.8 pp | [+14.8, +25.3] | undefined² | undefined² | not corrected¹ | 0.062 |
| openrouter_B | main | 964 / 93 | 11.0% | 15.1% | −4.1 pp | [−14.2, +4.8] | 0.63 | 0.200 | **0.599** | 0.333 |
| openrouter_B | **excl. 91 Vertex** | 964 / **2** | 11.0% | **100.0%** | −89.0 pp | [−91.4, −86.4] | undefined² | undefined² | not corrected¹ | 1.000 |
| tailscale_A | main | 299 / 26 | 13.7% | 7.7% | +6.0 pp | [−6.4, +16.3] | 1.74 | 0.428 | **0.856** | 0.622 |
| tailscale_A | excl. Vertex (no change: tailscale has none) | 299 / 26 | 13.7% | 7.7% | +6.0 pp | [−6.4, +16.3] | 1.74 | 0.428 | not corrected¹ | 0.622 |
| condition_A_all_arms ⁽ᵖʳᵒᵛ⁾ | main | 687 / 44 | 17.2% | 4.5% | +12.6 pp | [+3.8, +19.4] | 4.69 | 0.075 | **0.301** | 0.097 |
| condition_A_all_arms ⁽ᵖʳᵒᵛ⁾ | excl. Vertex (no change: condition A has none) | 687 / 44 | 17.2% | 4.5% | +12.6 pp | [+3.8, +19.4] | 4.69 | 0.075 | not corrected¹ | 0.097 |

¹ Sensitivity variant is a robustness check on the same row's hypothesis, not Holm-corrected as an added test — see note above.
² GEE odds ratio is degenerate (undefined/unstable) when the 2×2 group×outcome table has an empty cell — one group scored 0% or 100% on that row. Reported as "undefined" rather than the raw ±∞ the model returns, because that number is not usable. The risk difference (with cluster-bootstrap CI, which stays finite) and the sign-flip permutation p-value are the only usable statistics on those rows.
⁽ᵖʳᵒᵛ⁾ Pools `openrouter_A` and `tailscale_A` replicate cells — condition A across both providers. The +12.6pp row here is arithmetically dominated by the same `openrouter_A` 0/18-flip degeneracy already discussed below (`openrouter_A` supplies 18 of this row's 44 closed-group cells), so it is not an independent confirmation — flagged rather than presented as a second finding.

**Reading this table correctly, row by row:**

- **None of the four "main" rows reach significance** (Holm p ranges
  0.60–0.99), unlike the primary-outcome table above where every row was
  significant at p < 10⁻⁷. That contrast is itself informative: gemini's
  large run-1 accuracy advantage does not translate into a detectable
  difference in how "fixable" each group's remaining errors are on
  replication. Take this as a null result, not as absence of a difference
  worth investigating further — the closed-group cell counts (n=18 to
  n=137) are small enough that only large effects would be detectable.
- **`openrouter_A`, main:** gemini's 18 run-1 errors in this arm never
  flipped correct on either replicate (0/18), while the open models' errors
  flipped 19.8% of the time. This is a real, complete-separation result
  (not a modeling artifact — the raw counts are 0 of 18), but n=18 is small
  and the sign-flip p (0.062) does not clear a conventional threshold. It
  is consistent with a plausible story — gemini's rare errors in the
  easier A condition are more likely to be "hard" (consistently
  wrong) rather than noise — but that story is not established by n=18
  cells, and again describes gemini specifically, not closed models as a
  class.
- **`openrouter_B`, excluding the 91 Vertex cells:** this row is not
  interpretable. It reduces the closed group to 2 cells, both of which
  happened to flip correct (100%), producing a −89 pp "risk difference"
  that is an artifact of n=2, not a finding. It is reported only because
  the sensitivity analysis is mandatory, not because it supports any
  conclusion. The **main** `openrouter_B` row (n_closed=93, all upstreams
  included) is the more informative one, and even that is not significant.

### 2.3 Condition-stratified view — does the open/closed gap widen under NOTA?

Added at the team lead's request after STATS_SPEC.md was updated to
establish that **condition B is a none-of-the-above (NOTA) manipulation**,
not a generically "harder" condition (see 2.1). This section asks a
narrower, honest question: within the open-vs-closed contrast already
computed above, is the gap bigger under B (NOTA) than under A (ordinary
items)?

**Method — deliberately not a formal test.** This is a **descriptive effect
size only**: point estimate + question-cluster bootstrap 95% CI, no p-value,
not part of any Holm family. Restricted to `openrouter_A` vs `openrouter_B`
so provider is held fixed — STATS_SPEC.md calls this pairing "the cleanest
contrast in the study" for exactly this reason, and mixing in `tailscale_A`
(which has no B counterpart) would confound condition with provider. The
statistic is `gap = RD_condition_B − RD_condition_A`, where `RD = open
accuracy − closed accuracy`; a negative gap means the open group loses more
ground relative to gemini under the NOTA manipulation.

| Outcome | RD, condition A | RD, condition B | Gap (B − A) | 95% CI | Reading |
|---|---:|---:|---:|---|---|
| strict_correct (run-1, 6000 cells) | −11.1 pp | −22.1 pp | **−11.0 pp** | [−14.2, −7.7] | CI excludes 0. The open group's deficit relative to gemini roughly doubles under the NOTA manipulation. This is the clearest, best-powered result in this file and is consistent with the arm-level numbers in 2.1. |
| flip rate (replicates, OpenRouter only) | +19.8 pp | −4.1 pp | **−23.9 pp** | [−35.1, −14.0] | CI excludes 0, but **do not read this as an independent confirmation of the row above.** The condition-A term (+19.8pp) is exactly the `openrouter_A` 0/18-flip degeneracy already flagged in 2.2 — n=18 closed-group cells, one arm's worth of data, already noted as too small to support a conclusion on its own. This gap statistic inherits that fragility; it is reported for transparency, not as a second, independently-powered finding. |

**Bottom line for this subsection:** the strict_correct row is a genuine,
well-powered descriptive finding — gemini's advantage over the pooled open
group is not uniform across conditions, it concentrates under the NOTA
manipulation. The flip-rate row points the same direction but is built from
a small, already-flagged degenerate cell and should not be cited on its own
as confirming the pattern. Neither row is a claim about open-vs-closed
weight licensing (the n_models_closed=1 confound from the top of section 2
still applies in full) or a formal interaction test — both are descriptive,
per the team lead's explicit instruction not to overclaim a formal
interaction without a model that supports one.

---

## 3. Multiplicity — families as tested

| Family | Members | Correction |
|---|---|---|
| open_vs_closed × strict_correct_run1 | pooled(arm-adj.), openrouter_A, openrouter_B, tailscale_A, condition_A_all_arms | Holm-Bonferroni, n=5 |
| open_vs_closed × flip_rate_replicates (main) | pooled(arm-adj.), openrouter_A, openrouter_B, tailscale_A, condition_A_all_arms | Holm-Bonferroni, n=5 |
| open_vs_closed × flip_rate_replicates (Vertex-excluded) | same 5 rows | **not corrected** — robustness check on the family above, not an additional hypothesis family |
| open_vs_closed × condition-gap (section 2.3) | strict_correct gap, flip-rate gap | **not corrected, no p-value** — descriptive effect sizes only, not a hypothesis family |
| big_vs_small | — | not applicable; no test run |

Raw and Holm-adjusted p appear together in `groupings_open_closed_primary.csv`
and `groupings_open_closed_secondary.csv` (columns `p_gee_wald`,
`p_gee_wald_holm`).

## 4. Reproducing this

```
./.venv/bin/python3 data/experiment-4-aug-26/statistical-analysis-7-aug-26/scripts/03_groupings.py
```
Deterministic given the fixed random seed (`20260807`) used for both the
cluster bootstrap (5000 resamples) and the sign-flip permutation (20,000
resamples). Reads only from `../consolidate-triplicates-7-aug-26/exports/`
(read-only per file-ownership scope); writes only the three files in
`results/` named at the top of this document.

## 5. Bottom line

- **Big vs small: not computed.** Declared infeasible — two of four models
  lack a defensible parameter count, and the two that have one disagree
  about which model is "big" depending on the metric. See `MODEL_TAXONOMY.md`.
- **Open vs closed, primary outcome: gemini (the sole closed model) beats
  the pooled three open models by 7–22 points of accuracy depending on arm,
  consistently and with very small p-values, confirmed by a model-free
  permutation test.** This is a real, robust, well-powered finding — about
  gemini. It is not evidence about weight licensing as a factor, because
  n_models_closed = 1 makes the two impossible to separate. Do not shorten
  this to "closed models outperform open models."
- **Open vs closed, secondary outcome (flip rate): no significant
  difference in any arm**, and the one row with a suggestive pattern
  (`openrouter_A`, gemini 0/18 flips vs open models 19.8%) is too small
  (n=18) to support a conclusion. The Vertex-exclusion sensitivity variant
  for `openrouter_B` is uninterpretable (n_closed drops to 2) because the
  Vertex deviation and the closed-group definition are the same subset of
  cells in that arm — a second, arm-specific confound layered on top of the
  n_models_closed=1 problem.
- **Condition-stratified (section 2.3): the open/closed accuracy gap
  roughly doubles under the NOTA manipulation** — descriptive effect size
  −11.0pp [−14.2, −7.7] (CI excludes 0), OpenRouter-only so provider is held
  fixed. This is the most interesting single result added in this revision:
  it says gemini's advantage over the pooled open group is not a flat
  accuracy offset, it concentrates specifically on recognising that no
  listed answer is correct. The parallel flip-rate gap (−23.9pp [−35.1,
  −14.0]) points the same way but is built from the same small `openrouter_A`
  degenerate cell (n=18) already flagged above, so treat it as consistent
  with the accuracy-gap finding, not as separate confirmation of it. Both
  are descriptive effect sizes with bootstrap CIs, not formal interaction
  tests — no p-value is reported and neither is Holm-corrected, per the
  team lead's explicit instruction.
