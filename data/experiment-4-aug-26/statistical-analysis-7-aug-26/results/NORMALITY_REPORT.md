# Normality and distributional diagnostics

Agent 1 of 4. Owns: `scripts/01_normality.py`, `results/normality_*.json|csv`,
`figures/qq_*.svg`, this report. All data sources read-only. Design constraints
below are as verified in `../STATS_SPEC.md`; this report does not relitigate them.

## 0. What this report is, and is not

The user asked to "check normality first, then choose tests accordingly." The
study's primary outcomes — `strict_correct` (6000 run-1 cells) and `flip`
(1788 scored replicates) — are **Bernoulli (0/1) indicators**. A Bernoulli
variable is not drawn from a normal distribution for any p strictly between 0
and 1; running Shapiro-Wilk on raw 0/1 data will reject every time, for a
reason that carries zero information about which downstream test is valid.
That is a ritual, not a diagnostic, so it is not done here.

What *is* done here:
1. Genuine normality diagnostics (Shapiro-Wilk, Anderson-Darling, skewness,
   kurtosis, QQ plot) on the quantities that are actually continuous, or
   close enough to be worth checking: per-question difficulty (a proportion)
   and attempt latency.
2. A distributional description of the binary outcomes that does not treat
   them as continuous: base rates, per-cluster counts, and boundary counts.
3. An explicit statement of which tests follow from data type and clustering
   structure for the binary outcomes, since normality is not the gate there.

## 1. Continuous quantities: normality diagnostics

Full numbers: `results/normality_continuous_diagnostics.json` and
`results/normality_continuous_diagnostics_summary.csv`. QQ plots:
`figures/qq_*.svg` (10 plots, one per row below plus the two log-latency
provider splits).

Two p-values are reported for Anderson-Darling: scipy's own
`method="interpolate"` value (`anderson_darling_p_interpolated_scipy`,
floored at 0.01 — the pre-computed table scipy interpolates from does not
resolve p below that), and an independent closed-form approximation
(`anderson_darling_p_approx_stephens1974`, Stephens 1974 / D'Agostino &
Stephens 1986, Table 4.7) reported purely as a cross-check. For every
quantity below the two agree qualitatively: both are pinned at their
respective floors (0.01 and ~0), i.e. both say "far below any conventional
alpha," which is the only claim resting on them.

| Quantity | n | Shapiro W | Shapiro p | AD statistic | AD p (scipy / Stephens) | skew | excess kurtosis |
|---|---|---|---|---|---|---|---|
| Per-question difficulty, overall | 500 | 0.806 | 4.8e-24 | 29.95 | 0.01 / ~0 | -1.54 | 2.53 |
| Per-question difficulty, openrouter_A | 500 | 0.588 | 1.0e-32 | 91.47 | 0.01 / ~0 | -2.03 | 3.77 |
| Per-question difficulty, openrouter_B | 500 | 0.826 | 6.6e-23 | 32.22 | 0.01 / ~0 | -0.88 | -0.13 |
| Per-question difficulty, tailscale_A | 500 | 0.519 | 1.1e-34 | 101.14 | 0.01 / ~0 | -2.74 | 8.53 |
| latency_ms, all attempts, overall | 1835 | 0.627 | 8.0e-53 | 187.25 | 0.01 / ~0 | 3.25 | 13.59 |
| log(latency_ms), overall | 1835 | 0.916 | 1.0e-30 | 63.52 | 0.01 / ~0 | 0.11 | -1.38 |
| latency_ms, openrouter attempts | 1491 | 0.552 | 6.6e-52 | 213.48 | 0.01 / ~0 | 3.70 | 17.99 |
| log(latency_ms), openrouter | 1491 | 0.909 | 5.9e-29 | 55.32 | 0.01 / ~0 | 0.51 | -1.00 |
| latency_ms, tailscale attempts | 344 | 0.601 | 2.1e-27 | 44.46 | 0.01 / ~0 | 2.92 | 8.35 |
| log(latency_ms), tailscale | 344 | 0.887 | 3.1e-15 | 9.69 | 0.01 / ~0 | 1.32 | 1.72 |

**Every quantity rejects normality overwhelmingly** (Shapiro W between 0.52
and 0.92, all p ≪ 1e-14). That is expected, not a bug, for two distinct
reasons per quantity:

- **Per-question difficulty** is a proportion over only 4 or 12 Bernoulli
  trials. Its support is discrete (13 points `k/12`, k=0..12 for the overall
  version; 5 points `k/4` for the per-arm version), it is bounded on [0,1],
  and — as section 2 shows — a large fraction of questions sit exactly at
  the boundary. A discrete, bounded, boundary-heavy variable cannot be
  normal, and the very negative skew (-0.88 to -2.74: left tail, i.e. mass
  piled near 1.0 with a spread-out low tail) and large excess kurtosis
  (heavy central peak, mostly from the mass at `difficulty=1`) are visible
  directly in `figures/qq_per_question_difficulty_*.svg`: the QQ points
  bend sharply at the top (a stack of near-identical high values) while the
  bottom tail lags behind the reference line.

- **Attempt latency** is a positive-only, right-skewed duration (skew 2.9 to
  3.7 raw), consistent with the log-normal-ish shape latencies typically
  have. Log-transforming reduces skew substantially (raw skew ~3 → log skew
  0.1-1.3) and moves Shapiro W from ~0.55-0.63 up to ~0.89-0.92, but **does
  not** achieve normality — p-values stay far below 1e-14. Restricting to
  the 1788 scored (non-retry, non-error) attempts instead of all 1835
  recorded attempts changes the picture negligibly (Shapiro W 0.675 vs
  0.627 on raw latency; see
  `latency_scored_vs_all_attempts_sensitivity` in the JSON) — the
  non-normality is not an artefact of mixing in retries/errors, it is
  latency's actual shape (heavy right tail from slow calls and rare
  timeouts). `latency_ms` split by provider also differs sharply in scale
  (tailscale mean ≈37.3s vs openrouter ≈11.3s) — a descriptive fact, not a
  normality-test output, and consistent with STATS_SPEC's note that the
  provider contrast is a provider **and** prompt-delivery contrast, not a
  pure transport one.

**What this does and does not rule out downstream:**
- It rules out treating per-question difficulty or latency as inputs to a
  method whose validity depends on approximate normality of that specific
  variable — e.g. a paired t-test on question-level mean-difficulty scores,
  or a standard OLS confidence interval built from latency's raw or
  log-scale sample mean assuming normal errors.
- It does **not** rule out: (a) non-parametric alternatives on the same
  quantities (Wilcoxon signed-rank on paired question-level differences,
  permutation tests, bootstrap CIs — none of which assume normality); (b)
  modeling latency's central tendency via the log scale with robust/
  cluster-adjusted standard errors, which is a distinct claim from "log-
  latency is normal" and doesn't require it; (c) using per-question
  difficulty descriptively (e.g., as a stratification variable, or for the
  boundary-count argument in section 2) rather than as a normal-theory test
  input; (d) — most importantly — modeling the underlying binary cell data
  directly (logistic regression / GEE), which sidesteps this problem
  entirely because it never assumes the aggregated proportion is normal in
  the first place. That last option is the recommended path; see section 3.

## 2. Binary outcomes: distributional description, not a normality test

Full numbers: `results/normality_binary_outcome_summary.json` (and, for the
per-question histogram, the flatter `results/normality_binary_outcome_cluster_histogram.csv`).

### 2.1 Base rates

`strict_correct`, run-1, n=6000: **85.03%** correct (5102/6000) overall.

By arm: `openrouter_A` 89.85% (1797/2000), `openrouter_B` 73.40%
(1468/2000), `tailscale_A` 91.85% (1837/2000).

By model: `gemini-3.6-flash` 95.20% (1428/1500), `gemma-4-26b-a4b-it` 72.33%
(1085/1500), `qwen3.6-35b-a3b` 83.40% (1251/1500), `glm-5.2` 89.20%
(1338/1500). (Descriptive only — no significance claims belong here; that's
agents 2/3's contrasts.)

`flip` (secondary, conditioned on run-1 failure), n=1788 scored replicates:
**13.42%** flip to strict-correct overall (240/1788). By arm: `openrouter_A`
18.97% (77/406), `openrouter_B` 11.35% (120/1057), `tailscale_A` 13.23%
(43/325). Per-cell flip counts, among the 895 run-1-incorrect cells that had
at least one scored replicate: 725 cells flip on 0 of their scored
replicates, 100 flip on exactly 1, 70 flip on both (of the cells with 2
scored replicates). As STATS_SPEC notes, this is unconditionally silent
about the 5102 run-1-correct cells (never replicated) and is a raw
description of the replicate data — it is not adjusted for the 91 Vertex-
served `openrouter_B`/gemini cells; that adjustment is agents 2/3's
sensitivity analysis to run, per STATS_SPEC's "Sensitivity" requirement.

### 2.2 Per-cluster counts (question = cluster)

Histogram of `n_correct_of_12` across the 500 questions (run-1,
`strict_correct`, all 3 arms × 4 models pooled per question):

| n_correct / 12 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| n questions | 1 | 0 | 3 | 4 | 4 | 11 | 9 | 24 | 34 | 53 | 71 | 100 | 186 |

Same histogram split by arm (`n_correct_of_4`, since each arm has 4 models
per question) is in the JSON/CSV; headline: `openrouter_B` has the flattest,
least boundary-heavy distribution of the three arms (204 at ceiling, 19 at
floor, 277 interior), consistent with it being the hardest arm at the model
level (73.4% base rate above) — `openrouter_A` and `tailscale_A` are both
heavily ceiling-loaded (365/500 and 385/500 questions respectively answered
correctly by all 4 models).

### 2.3 Boundary counts — why this matters downstream

**186 of 500 questions (37.2%) have all 12 cells strict_correct; 1 question
(0.2%) has all 12 cells strict_incorrect.** That's **187/500 = 37.4% of
questions at a boundary** with zero within-question variance in the primary
outcome. The remaining 313 questions (62.6%) show some mix of correct/
incorrect across their 12 cells.

This is the fact that gates question-level aggregation. A method that
aggregates each question down to a single continuous "proportion correct"
and then runs a normal-theory test on those 500 numbers (e.g., a paired
t-test on per-question A-vs-B differences) is throwing away exactly the
cells that make up over a third of the dataset, because a question stuck at
12/12 or 0/12 contributes a fixed, uninformative value to that aggregate
regardless of which arm or model produced it — there is no within-question
signal left for a difference-of-conditions test to detect on those rows. It
also explains why per-question difficulty is so far from normal in section
1: nearly 2 in 5 questions are piled at one of two single points.

Cluster-robust methods that operate on the individual binary cells (GEE
clustered on question, or a question-level permutation test that permutes
whole questions' cell-vectors) do not have this problem — a ceiling/floor
question still contributes correctly to those estimators' handling of
within-cluster correlation, it just correctly contributes "no evidence of a
condition effect" rather than being silently dropped or degenerately
averaged. This is one more concrete reason (on top of the pairing/clustering
argument in STATS_SPEC) to prefer those methods over t-tests on
question-level aggregates.

## 3. Recommendation to agents 2 and 3

**The test choice for `strict_correct` and `flip` follows from data type
(binary) and the pairing/clustering structure documented in STATS_SPEC.md —
not from any normality result, and not from the boundary-count finding
above either (that finding is a power/viability argument about
*aggregation*, not a normality argument).** Concretely:

| Contrast | Structure | Recommended test | Why |
|---|---|---|---|
| Condition A vs B (paired, OpenRouter only, same 500 questions × 4 models) | Within-question paired binary | **McNemar's exact test** on the discordant pairs (per model, and/or pooled); for the pooled/multi-model version, **cluster-robust logistic regression (GEE, exchangeable correlation, clusters = question)** with a condition indicator, since 4 models are stacked per question and McNemar alone doesn't absorb that extra clustering layer | Cleanest contrast in the study (STATS_SPEC). Two-sample proportion tests are wrong here because they ignore that both conditions hit the identical questions — that inflates the SE. |
| Provider (openrouter_A vs tailscale_A, condition fixed at A) | Also within-question paired (same 500 questions, both conditions = A) | Same as above: **McNemar** per model or **cluster-robust GEE clustered on question** | Same pairing logic applies since both arms answer the same question set. Report as a provider **+ prompt-delivery** contrast per STATS_SPEC (TailScale doesn't honour JSON-schema enforcement), not a pure transport contrast. |
| Model-level / grouped contrasts (open-vs-closed, big-vs-small, model main effects) | Not paired — the grouping variable is (partly) what defines the cluster | **Cluster-robust logistic regression (GEE, clusters = question)** or a **question-level permutation test** (permute whole questions' outcome vectors across group labels) | McNemar doesn't apply (no natural 1:1 pairing across the grouping). Naive pooled-proportion tests (e.g. chi-square on flattened cells) ignore the question cluster and will overstate significance. |
| Flip rate contrasts (secondary, conditioned on run-1 failure) | Binary, clustered on cell/question, fewer and unbalanced clusters (898 cells, ≤2 replicates each) | **Cluster-robust logistic regression clustered on question (or cell)**, with attention to small-sample cluster-count corrections; treat as descriptive/exploratory given the conditioning | Same binary+clustering logic, but n is smaller and the conditioning-on-failure structure means results describe stability of already-wrong answers, not general accuracy (regression to the mean applies, per STATS_SPEC) — this is not a normality consideration either. |

**Effect sizes:** every one of the above needs risk difference and odds
ratio with CIs alongside the p-value (STATS_SPEC's "Effect sizes are
mandatory" requirement) — normality diagnostics don't bear on that
requirement, it's independent.

**Multiplicity:** apply Holm-Bonferroni within whatever families agents 2/3
define (e.g. "all pairwise model contrasts" as one family, "A vs B per
model" as another) — again independent of anything in this report.

**One thing this report specifically rules out for agents 2/3:** do not
justify McNemar, GEE, or permutation test choice by citing a Shapiro-Wilk or
Anderson-Darling result on `strict_correct`/`flip` — those tests were
deliberately not run on the binary outcomes (section 0), so there is no such
result to cite. The choice rests entirely on data type + design structure,
as tabulated above.

## 4. Files produced

- `scripts/01_normality.py` — reproducible (stdlib csv/json + numpy/scipy
  only; re-run verified byte-identical output on the committed CSVs).
- `results/normality_continuous_diagnostics.json` — full Shapiro-Wilk,
  Anderson-Darling (both p variants + critical-value table), skewness,
  kurtosis (with SE and z) for all 10 continuous quantities, plus the
  scored-vs-all-attempts latency sensitivity check.
- `results/normality_continuous_diagnostics_summary.csv` — flat version of
  the same, one row per quantity.
- `results/normality_per_question_difficulty.csv` — 500 rows: per-question
  `n_correct_of_12` / `difficulty_overall`, and the same split by arm
  (`n_correct_of_4_<arm>` / `difficulty_<arm>`).
- `results/normality_binary_outcome_summary.json` — base rates (overall,
  by arm, by model), per-question cluster histograms (overall 0-12, by-arm
  0-4), boundary counts (overall and by arm), and the flip-rate
  distributional description.
- `results/normality_binary_outcome_cluster_histogram.csv` — flat mirror of
  the two cluster histograms (`overall`/0-12 and per-arm/0-4 kept in
  separate row blocks, tagged by a `table` column, since they have
  different denominators).
- `figures/qq_*.svg` — 10 hand-written inline-SVG QQ plots (no matplotlib
  dependency): standardized sample quantiles vs. theoretical standard-normal
  quantiles, with a dashed y=x reference line, for per-question difficulty
  (overall + 3 arms) and latency_ms / log(latency_ms) (overall + 2
  providers).
