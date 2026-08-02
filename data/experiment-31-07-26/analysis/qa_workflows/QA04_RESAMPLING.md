# QA04 — resampling and exact inference

**Independent QA date:** 2026-07-31  
**Input:** `paired_clean.json`, MD5 `0b25b95d082cf00900443d262c84427e`, SHA-256 `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187`  
**Scope:** canonical v2 OpenRouter A/B data; whole-clinical-cluster bootstrap, exact McNemar, exact clinical-cluster sign-flip, Clopper–Pearson, design effects, and Kish effective cluster count. Canonical scripts/results were not edited.

## Verdict

**Core resampling/exact algorithms: mostly PASS. Current result artifacts and `REPORT.md`: FAIL for v2 provenance and test labelling.**

The whole-cluster bootstrap code preserves repeated draws correctly, the Clopper–Pearson primitive is numerically correct, and independent v2 recomputation confirms all substantive A-to-B accuracy losses. However, `prim_cluster_bootstrap_results.json` is a v1 artifact (1,299 cells / 325 items / 208 clusters), created before the v2 export (1,271 / 318 / 201), and its intervals are the ones still shown in `REPORT.md`. The pooled table cell labelled “exact McNemar” is instead a stale exact clinical-cluster sign-flip p-value. Those are distinct tests with very different null distributions.

| claim/check | verdict | evidence |
|---|---|---|
| Bootstrap resamples whole clinical clusters with replacement and retains duplicate draws | **PASS** | `prim_01_cluster_bootstrap.py:92-105` loops over every element returned by `random.choices`; a repeated vector is added repeatedly. This is algebraically identical to expanding rows under a unique `(draw_index, cluster)` occurrence key. |
| Persisted bootstrap results and report CIs are v2 | **FAIL** | `prim_cluster_bootstrap_results.json` says 1,299/325/208 and was written 10:21:04; v2 `paired_clean.json` was written 10:47:46 and contains 1,271/318/201. |
| Corrected v2 percentile CIs are reproducible/stable | **PASS** | Independent multinomial whole-cluster bootstrap, 100,000 replicates, seed 20260731; five 20,000-replicate seeds changed any endpoint by at most 0.207 pp, and 100,000→200,000 changed any endpoint by at most 0.029 pp. |
| `P(delta* >= 0) = 0/B` is stable evidence or a p-value | **FAIL** | Gemini produced counts 1,0,0,0,0 across five 20,000-replicate seeds; across ten 100,000-replicate seeds it occurred 3 times in 1,000,000 draws. A zero count is a Monte Carlo floor, not probability zero, and the ordinary pairs bootstrap is not a null randomization test. |
| Exact McNemar implementation | **PASS (calculation); secondary inferential status** | Direct integer-binomial sums equal `scipy.stats.binomtest`. It conditions on discordant cells and assumes their directions are independent; clinical clustering, and pooled reuse of items across models, violate that iid interpretation. |
| Pooled value in the report is “exact McNemar” | **FAIL** | v2 stacked-cell McNemar is `8.679921e-34`; v2 exact clinical-cluster sign-flip is `1.947151e-15`. The report displays stale v1 sign-flip `4.5e-16` under the McNemar heading. |
| Exact clinical-cluster sign-flip implementation | **PASS (method); report value stale** | Exact integer convolution over 114 nonzero cluster totals gives `1.9471510525e-15`; no Monte Carlo approximation was used. |
| Clopper–Pearson implementation | **PASS (primitive); FAIL (current workflow)** | Current `stats_lib.binom_exact_ci` matched beta-quantile references over 505 edge/grid/study cases, maximum absolute error `4.55e-13`. `prim_mcnemar_exact.py` nevertheless aborts on v2 because line 162 asserts `N == 1299`; its validator also retains v1 pooled counts. |
| Reported DEFF 3.75 and Kish 53/208 are v2 | **FAIL** | Correct v2 sign-flip null-variance ratio is `1083/287 = 3.773519`; Kish effective clinical clusters are `1271^2 / sum(n_g^2) = 50.9009` of 201. |

## Correct canonical v2 numbers

Risk difference is `B - A`; negative values favour condition A. CIs below are type-7/linear 2.5th and 97.5th percentiles from 100,000 multinomial resamples of all 201 clinical-cluster occurrences, seed 20260731. Each draw carries every available item/model row in that cluster and recomputes the ratio estimator.

| model | n | RD (pp) | cluster-bootstrap SE (pp) | 95% percentile CI (pp) | exact McNemar p | exact cluster sign-flip p |
|---|---:|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 318 | −8.4906 | 1.8495 | [−12.2807, −5.0179] | 3.465451e-06 | 1.510046e-05 |
| glm-5.2 | 317 | −18.2965 | 2.4515 | [−23.3333, −13.7380] | 1.807741e-12 | 5.276803e-11 |
| qwen3.6-35b-a3b | 318 | −15.7233 | 2.5188 | [−20.7031, −10.7558] | 1.411467e-08 | 1.795807e-07 |
| gemma-4-26b-a4b-it | 318 | −19.4969 | 3.3877 | [−26.0989, −12.8125] | 1.660670e-10 | 3.137179e-07 |
| **cell-weighted pooled** | **1,271** | **−15.4996** | **1.6319** | **[−18.7686, −12.3720]** | **8.679921e-34*** | **1.947151e-15** |

`*` The pooled McNemar number treats 287 discordant item×model cells as iid. It is a computational check, not the cluster-aware study-level p-value.

For an exact paired odds ratio oriented consistently as **B/A** (`B-only / A-only`), the Clopper–Pearson results are:

| model | A-only / B-only | exact paired OR B/A [95% CI] |
|---|---:|---:|
| gemini | 31 / 4 | 0.12903 [0.03309, 0.36496] |
| glm | 66 / 8 | 0.12121 [0.05025, 0.25305] |
| qwen | 65 / 15 | 0.23077 [0.12223, 0.40910] |
| gemma | 80 / 18 | 0.22500 [0.12694, 0.37866] |
| pooled | 242 / 45 | 0.18595 [0.13215, 0.25647] |

Some scripts orient this reciprocal as A/B. That is not a numerical error if the label is explicit. These exact intervals inherit the iid-discordant-direction assumption and are not cluster-robust.

## Duplicate-draw audit

The canonical vector accumulator does not materialize row identities, so it does not literally need a `draw_index`; it is nevertheless multiplicity-preserving. In the first diagnostic draw using `random.Random(20260731).choices(sorted_clusters, k=201)`:

- 201 cluster occurrences contained only 132 distinct cluster labels; 69 were duplicate occurrences and the maximum multiplicity was 4.
- Explicit expansion keyed by `(draw_index, cluster)` produced 1,251 cells, net difference −188, RD −15.02798 pp.
- Multiplicity-weighted sufficient-statistic accumulation produced exactly the same 1,251, −188, and −15.02798 pp.
- Incorrectly joining/deduplicating on `cluster` alone would have produced only 847 cells and RD −15.11216 pp.

Thus the current summation algorithm passes. Any future dataframe/SQL implementation must attach the draw occurrence before joining, e.g. `(replicate, draw_index, cluster)`, because `cluster` alone collapses repeated selections.

## Exact tests are not interchangeable

Ordinary exact McNemar conditions on `n_disc = b + c` and uses `Binomial(n_disc, 0.5)` for independent discordant directions. The pooled v2 table has A-only `b=242`, B-only `c=45`, so its exact p is `8.679921e-34`.

The clinical-cluster sign-flip first forms `D_g = sum(B_correct - A_correct)` inside each cluster, then flips each nonzero `D_g` jointly. Integer convolution over the 114 nonzero clusters gives `P(|sum(s_g D_g)| >= 197) = 1.9471510525e-15`. It is exact under independent clusters and joint within-cluster A/B-label exchangeability. It is not McNemar, and “exact” does not remove this exchangeability assumption.

The associated null variances clarify the dependence levels:

| flip unit | null variance of pooled numerator | ratio to iid-cell variance 287 | exact p |
|---|---:|---:|---:|
| discordant cell (McNemar) | 287 | 1.0000 | 8.679921e-34 |
| item (four models jointly) | 525 | 1.8293 | 1.340652e-21 |
| clinical cluster | 1,083 | **3.7735** | **1.947151e-15** |

This `3.7735` is a **null sign-flip variance ratio**, not the sampling-variance design effect of the RD estimator. The v2 pooled RD's CR1 sampling design effect is `1.64735` (`SE_iid=1.26049 pp`, `SE_CR1=1.61783 pp`), implying about `1271/1.64735 = 771.5` iid-equivalent cells. Those quantities answer different questions and should not share an unqualified “DEFF” label.

## Kish count and leverage

Clinical-cluster sizes range from 3 to 80 cells (1 to 20 items); 190 of 201 clusters are singleton items, while the largest five contain 26.1% of all cells. Therefore:

- size-weighted mean cluster size `sum(n_g^2)/sum(n_g) = 24.9701` cells;
- Kish effective cluster count `(sum n_g)^2/sum(n_g^2) = 50.9009` of 201;
- item-size version `318^2/sum(m_g^2) = 50.9698` of 201.

`stats_structure4.py` reads v2 rows but hard-codes 1,299/325/208 at lines 61–63, 103, 109, 119, and 135–136. Its dynamic empirical DEFF happens to remain usable, but displayed means and effective sample sizes are hybrid v1/v2 outputs and must not be cited.

## Reproduction and stability checks

Read-only commands executed from `tier1_mcq/`:

```bash
md5 data/experiment-31-07-26/analysis/paired_clean.json
shasum -a 256 data/experiment-31-07-26/analysis/paired_clean.json
jq '[.[] | select(.analysis_include == true)] | length' \
  data/experiment-31-07-26/analysis/paired_clean.json
python data/experiment-31-07-26/analysis/prim_mcnemar_exact.py
python data/experiment-31-07-26/analysis/prim_mcnemar_validate.py
python data/experiment-31-07-26/analysis/stats_structure4.py
python data/experiment-31-07-26/analysis/stats_04_gee.py
```

The first three yield the pinned hash and 1,271 included rows. `prim_mcnemar_exact.py` exits 1 with `AssertionError: 1271`; the validator reports live `sum b=242` against hard-coded v1 `247`; `stats_04_gee.py` dynamically returns Kish `50.9 (nominal 201)`.

Independent recomputation used cluster sufficient statistics `(n_g, sum_g(B-A))`. Bootstrap multiplicities were drawn as `Multinomial(K=201; 1/K, ..., 1/K)`, which is exactly the count representation of K draws with replacement. Exact sign-flips used an integer `Counter` convolution, and exact McNemar used integer combinations / `scipy.stats.binomtest`. Clopper–Pearson was checked against

```text
lo = Beta.ppf(.025, k, n-k+1)   (0 when k=0)
hi = Beta.ppf(.975, k+1, n-k)   (1 when k=n)
```

Five independent 20,000-replicate seeds (`1,2,3,777,20260731`) gave maximum endpoint ranges of 0.115 pp (gemini), 0.103 pp (glm), 0.184 pp (qwen), 0.207 pp (gemma), and 0.137 pp (pooled). All intervals excluded zero by wide margins.

## Limitations

- Percentile-bootstrap stability is not a coverage proof. It assumes the 201 labelled clinical clusters are the independent sampling units and representative of a relevant population.
- Size imbalance is severe (Kish 50.9 despite nominal K=201), so the few large case clusters have material leverage; cluster leave-one-out checks remain important.
- The glm model is missing one item/cell and appears in 200 observed clusters. The joint whole-corpus bootstrap samples all 201 top-level clusters, with an empty glm contribution where that cell is absent; this preserves cross-model resamples but assumes the missing cell is ignorable.
- Exact McNemar/Clopper–Pearson calculations are mathematically exact only for their conditional iid-binomial model. Clinical clustering invalidates that model as primary inference.
- The exact cluster sign-flip requires joint A/B exchangeability within each cluster under the sharp null. It should be described as a randomization/sign-flip sensitivity analysis, not relabelled McNemar.
