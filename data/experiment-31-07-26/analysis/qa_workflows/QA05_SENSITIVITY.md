# QA05 — OpenRouter A/B sensitivity analysis on the v2 analytical population

**Audit date:** 2026-07-31 (Europe/Madrid)  
**Scope:** OpenRouter condition B versus condition A, including the 2×2 exclusion grid,
the option-(a) NOTA construction artifact, leave-one-out influence, the advertised
160-specification curve, and multiplicity.  
**Mutation policy:** the SQLite database and canonical analysis files were opened read-only or
hashed only. All recomputations ran in memory; temporary specification-curve results went to
`/tmp`. This report is the only file created by QA05.

## Verdict

**PASS for the substantive robustness conclusion; FAIL for the current report/result-artifact
bundle.**

The v2 analytical population supports a large negative OpenRouter B−A effect under every one of
the four exclusion sets and every model. All 20 model-by-set point estimates are negative, and
all 20 independently recomputed clinical-cluster bootstrap 95% intervals exclude zero. On the
reported set the pooled risk difference is **−15.499607 percentage points** on **318 items / 1,271
cells / 201 clinical clusters**.

The delivery bundle nevertheless fails QA because `REPORT.md` §3 and multiple cached sensitivity
outputs still contain v1 denominators and estimates (325 / 1,299 / 208). The descriptive sign of
the 160-specification curve reproduces on v2, but its claim that 160/160 specifications are
“significant” is not a defensible evidential count: the grid repeats only 28 distinct point
estimates, combines dependent model tests with Fisher's method, includes non-clustered McNemar
tests, uses uncentered bootstrap tails as p-values, and treats four models with a parametric
`t(3)` approximation. Multiplicity arithmetic for the four primary model tests does reproduce
with exact clinical-cluster sign flips, but it should not be conflated with the specification
curve or with model-population generalisation.

### Component disposition

| component | verdict | basis |
|---|---|---|
| Database → paired JSON lineage | **PASS** | zero key, outcome, selected-letter, flag, or cluster mismatches |
| Four-set exclusion sensitivity | **PASS** | all 20 RDs negative; all 20 cluster-bootstrap CIs below zero |
| Position-(a) construction defect | **CONDITIONAL** | logical defect is certain; empirical excess drop is modest and inference is specification-sensitive |
| Cluster/item/model influence | **PASS** | 201/318/4 deletions; no sign reversal |
| Specification-curve sign | **PASS** | 160/160 negative on v2 |
| Specification-curve p-value percentage | **FAIL as inference** | mechanically reproducible, methodologically non-comparable and heavily duplicated |
| Four primary tests under multiplicity | **PASS, conditional on the declared family** | all survive Holm-4 and even Bonferroni-160 using exact cluster sign flips |
| Current `REPORT.md` and cached outputs | **FAIL** | mixed v2 inputs with v1 sensitivity results |

## 1. Pinned input and lineage verification

The analysis is pinned to content, not file modification time:

| input | MD5 | SHA-256 |
|---|---|---|
| `experiment.sqlite` | `1c5fcbb79c93f1a0554c3e8cea0be552` | `dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748` |
| `paired_clean.json` | `0b25b95d082cf00900443d262c84427e` | `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187` |

During this audit another workflow regenerated the metadata bundle as export v3. Its note says
that v3 preserves the v2 analytical population while fixing provenance/build mechanics. The
`paired_clean.json` bytes and hashes did not change, so all numbers below remain the requested v2
population results.

Independent read-only SQLite reconstruction used the authoritative scored chain:

```sql
scores
  JOIN parsed_answers
    ON parsed_answers.id = scores.parsed_answer_id
   AND parsed_answers.logical_call_id = scores.logical_call_id
  JOIN provider_attempts
    ON provider_attempts.id = parsed_answers.provider_attempt_id
   AND provider_attempts.logical_call_id = scores.logical_call_id
```

Checks:

- `PRAGMA integrity_check = ok`; zero foreign-key violations.
- Scored cells: A = 1,895; B = 1,692; scored A/B intersection = **1,691**.
- The database intersection and JSON have the identical 1,691 `(question_id, model)` keys.
- JSON versus authoritative DB: zero A/B correctness mismatches and zero selected-letter
  mismatches.
- Rebuilding clusters from the dataset-A question text (shared prepended vignette, otherwise a
  singleton) produced zero cluster mismatches.
- Exclusion flags exactly equal the declared item list and `correct_letter == "a"`; zero flag or
  `analysis_include` mismatches.
- The declaration contains 22 defect IDs, but only **19 are present in dataset B/the paired
  intersection**. The absent IDs are `b343`, `b420`, and `b430`. This is why dropping item defects
  yields 404, not 401, observed paired items.

## 2. Methods independently applied

The effect estimand is the cell-weighted paired risk difference

`RD = 100 × (sum(B_correct) − sum(A_correct)) / n`,

so negative values mean worse accuracy in condition B.

For every exclusion-set/model cell, QA05 used a nonparametric clinical-cluster bootstrap:

- resampling unit: the observed clinical cluster;
- every draw carries all items and models in that cluster;
- 200,000 resamples, NumPy 2.4.4 `Generator(PCG64)`, seed 20260731 reset for each exclusion set;
- the numerator and denominator were recomputed in every draw;
- 95% percentile interval with linear quantile interpolation.

Representing repeated draws by multinomial cluster weights preserves duplicate draws and avoids
the known error of merging duplicate questions after resampling. Bootstrap endpoints are Monte
Carlo quantities; exact integer counts and point estimates are also shown. No bootstrap draw was
non-negative for any of the 20 estimates.

As an independent inferential cross-check, exact two-sided whole-cluster sign-flip distributions
were obtained by integer convolution of cluster net differences. Those p-values are used in the
multiplicity section, not ordinary stacked-cell McNemar p-values.

## 3. Corrected four-set exclusion grid

### Composition

| set | rule | items | cells | clusters |
|---|---|---:|---:|---:|
| none | retain every scored A/B pair | **423** | **1,691** | **281** |
| drop item defects | remove the 19 declared defects present in B | **404** | **1,615** | **263** |
| drop position-(a) | remove the 91 items whose key/NOTA is in slot a | **332** | **1,327** | **214** |
| drop both / reported | apply both rules | **318** | **1,271** | **201** |

`glm-5.2` has one fewer cell in every set because `b320 × glm-5.2` has no scored A response.

### Exact counts, rates, risk differences, and cluster-bootstrap intervals

| set | model | n | A correct (%) | B correct (%) | RD B−A, pp | 95% cluster-bootstrap CI, pp |
|---|---|---:|---:|---:|---:|---:|
| none | pooled | 1,691 | 1,511 (89.355%) | 1,218 (72.028%) | **−17.327** | **[−20.378, −14.413]** |
| none | gemini | 423 | 411 (97.163%) | 374 (88.416%) | **−8.747** | **[−12.032, −5.603]** |
| none | gemma | 423 | 339 (80.142%) | 244 (57.683%) | **−22.459** | **[−28.571, −16.364]** |
| none | qwen | 423 | 369 (87.234%) | 287 (67.849%) | **−19.385** | **[−23.752, −15.291]** |
| none | glm | 422 | 392 (92.891%) | 313 (74.171%) | **−18.720** | **[−23.266, −14.538]** |
| drop defects | pooled | 1,615 | 1,451 (89.845%) | 1,178 (72.941%) | **−16.904** | **[−20.022, −13.926]** |
| drop defects | gemini | 404 | 395 (97.772%) | 359 (88.861%) | **−8.911** | **[−12.329, −5.685]** |
| drop defects | gemma | 404 | 324 (80.198%) | 237 (58.663%) | **−21.535** | **[−27.861, −15.263]** |
| drop defects | qwen | 404 | 356 (88.119%) | 279 (69.059%) | **−19.059** | **[−23.418, −14.921]** |
| drop defects | glm | 403 | 376 (93.300%) | 303 (75.186%) | **−18.114** | **[−22.705, −13.921]** |
| drop position-(a) | pooled | 1,327 | 1,181 (88.998%) | 972 (73.248%) | **−15.750** | **[−18.930, −12.671]** |
| drop position-(a) | gemini | 332 | 322 (96.988%) | 295 (88.855%) | **−8.133** | **[−11.744, −4.796]** |
| drop position-(a) | gemma | 332 | 262 (78.916%) | 194 (58.434%) | **−20.482** | **[−26.884, −14.000]** |
| drop position-(a) | qwen | 332 | 291 (87.651%) | 237 (71.386%) | **−16.265** | **[−21.131, −11.420]** |
| drop position-(a) | glm | 331 | 306 (92.447%) | 246 (74.320%) | **−18.127** | **[−23.028, −13.636]** |
| drop both | pooled | 1,271 | 1,138 (89.536%) | 941 (74.036%) | **−15.500** | **[−18.765, −12.364]** |
| drop both | gemini | 318 | 311 (97.799%) | 284 (89.308%) | **−8.491** | **[−12.252, −5.023]** |
| drop both | gemma | 318 | 251 (78.931%) | 189 (59.434%) | **−19.497** | **[−26.087, −12.794]** |
| drop both | qwen | 318 | 281 (88.365%) | 231 (72.642%) | **−15.723** | **[−20.690, −10.769]** |
| drop both | glm | 317 | 295 (93.060%) | 237 (74.763%) | **−18.297** | **[−23.355, −13.750]** |

Model labels above abbreviate the four full model IDs in `paired_clean.json`.

The corrected pooled span is **1.827 pp**, from −17.327 to −15.500, not the stale 1.78 pp.
Using the same 281-cluster draw for both members of each contrast gave:

| paired filter contrast | observed shift, pp | 95% paired cluster-bootstrap CI, pp |
|---|---:|---:|
| drop both − none | +1.827 | [ +0.282, +3.441 ] |
| drop defects − none | +0.423 | [ −0.147, +1.092 ] |
| drop position-(a) − none | +1.577 | [ +0.120, +3.089 ] |
| drop both − drop position-(a) | +0.250 | [ −0.245, +0.859 ] |
| drop both − drop defects | +1.404 | [ −0.058, +2.905 ] |

Thus both exclusions attenuate the pooled magnitude, but only the position-(a) component clearly
separates from zero in this paired bootstrap. “Both exclusions are conservative” is acceptable
for the pooled point estimate, not as a claim that every model-specific shift is in the same
direction.

## 4. NOTA position-(a) artifact

The construction defect itself is not statistical: “respuestas anteriores” has no antecedent
when placed first. The empirical question is how much additional degradation is associated with
that position.

### Unfiltered paired data

| stratum | items | cells | A correct (%) | B correct (%) | RD B−A, pp |
|---|---:|---:|---:|---:|---:|
| key = a | 91 | 364 | 330 (90.659%) | 246 (67.582%) | **−23.077** |
| key ∈ {b,c,d} | 332 | 1,327 | 1,181 (88.998%) | 972 (73.248%) | **−15.750** |

The crude artifact contrast is
`RD(a) − RD(b,c,d) = −7.327111 pp`, with a 200,000-replicate cluster-bootstrap
95% CI of **[−14.038, −0.564] pp**.

- Exact item-label randomisation, conditioning on 91 of 423 items labelled a:
  **p = 0.0340145720**.
- Exact randomisation within the nine clinical clusters containing both a and non-a items
  (137 items), conditioning on each cluster's observed a count: **p = 0.0374208737**.
- Direct standardisation over `has_context × question-length-tertile` gives **−7.399 pp**,
  cluster-bootstrap 95% CI **[−15.304, −0.423]**.
- A model-specific counterfactual replacing each a-cell difference with that model's non-a mean
  changes the raw pooled RD from −17.327025 to **−15.750197 pp**. The attributable component is
  **−1.576829 pp**, or **9.100%** of the raw pooled drop.

The full-set artifact is heterogeneous by model: gemini −2.856 pp, gemma −9.188 pp, qwen
−14.504 pp, and glm −2.752 pp.

### After dropping item defects

| stratum | items | cells | A correct (%) | B correct (%) | RD B−A, pp |
|---|---:|---:|---:|---:|---:|
| key = a | 86 | 344 | 313 (90.988%) | 237 (68.895%) | **−22.093** |
| key ∈ {b,c,d} | 318 | 1,271 | 1,138 (89.536%) | 941 (74.036%) | **−15.500** |

The artifact becomes **−6.593417 pp**, with cluster-bootstrap 95% CI
**[−13.380, +0.263]**. The exact global item-label randomisation is
**p = 0.0630784983**; the conditional within-mixed-cluster value remains 0.0374208737.

Conclusion: the report's −7.3 pp / ~9.1% descriptive claim reproduces for the unfiltered data,
but an unqualified “artifact is significant” claim is too strong. Correct-letter position was not
randomised, the a/non-a sets differ in composition, the global permutation relies on exchangeable
item labels, and defect-clean inference straddles 0.05. State this as a plausible, modest
construction-associated component, not a settled causal decomposition.

## 5. Corrected influence analysis

All calculations below use the reported v2 set: 1,271 cells, 318 items, 201 clusters, pooled
RD = **−15.499607 pp**.

| deletion unit | refits | RD range after one deletion, pp | maximum absolute shift | sign reversals |
|---|---:|---:|---:|---:|
| clinical cluster | **201** | **[−16.055420, −14.995990]** | **0.555813 pp** | 0 |
| item | **318** | **[−15.864246, −15.232833]** | **0.364640 pp** | 0 |
| model | **4** | **[−17.838405, −14.165792]** | **2.338798 pp** | 0 |

For leave-one-cluster-out, two clusters move the estimate by more than 0.5 pp and none by more
than 1 pp:

- remove cluster 3 (11 items / 44 cells; item IDs `b2,b4,b5,b6,b7,b9,b11,b12,b13,b21,b22`):
  RD −16.055420, shift −0.555813 pp;
- remove cluster 0 (6 items / 24 cells; `b166,b167,b168,b170,b171,b184`):
  RD −14.995990, shift +0.503616 pp.

For leave-one-item-out, nine items move the estimate by more than 0.25 pp and none by more than
0.5 pp. The largest shift is deletion of `b248`: RD −15.864246, shift −0.364640 pp.

| model removed | remaining n | RD without model, pp | shift from full, pp |
|---|---:|---:|---:|
| gemini | 953 | **−17.838405** | −2.338798 |
| gemma | 953 | **−14.165792** | +1.333814 |
| qwen | 953 | **−15.424974** | +0.074633 |
| glm | 954 | **−14.570231** | +0.929376 |

The point estimate is not driven by one cluster or item. Model choice matters materially, but all
four individual model effects and every leave-one-model-out pooled effect remain negative.

## 6. Specification-curve claim

I reconstructed the declared grid without reading the cached result file:

- four exclusion rules;
- lenient paired-complete-case outcome versus a strict sensitivity that scores the sole missing
  A response (`b320 × glm`) as incorrect while B is DB-verified correct;
- the code-listed cell/item/cluster/model weightings and inference labels;
- 20 rows per exclusion/outcome combination, 160 rows total.

The strict cell is independently supported by the DB: A has ten failed parses (nine length, one
error), while B parsed `d`, the correct key.

### Descriptive part: reproducible on v2

- negative estimates: **160/160**;
- median: **−16.469501 pp**;
- range: **−17.841547 to −15.408805 pp**;
- only **28 distinct point estimates** among the 160 rows;
- primary/lenient cell RD: −15.499607 pp;
- primary/strict cell RD: −15.408805 pp.

The current report's median −16.55 and upper endpoint −15.46 are v1 values.

### P-value count: mechanically reproducible, not defensible as “160 confirmations”

For audit only, I reran the original code-listed p-value definitions with the independent
refutation primitives, 10,000 bootstrap/permutation replicates, base seed 777333111, and
`PYTHONHASHSEED=0`. The mechanical counts are:

- p < 0.05: **160/160**;
- p < 0.01: **158/160**;
- p < 0.001: **152/160**;
- median p: **9.047194995×10⁻13**;
- maximum p: **0.0100867663**;
- **93/160** p-values were pinned to a 10,000-replicate resolution floor or a Fisher combination
  of such floors.

These counts should not be presented as a robust inferential frequency:

1. Fifty-six rows use Fisher combination across four model p-values even though the models share
   the same items/clusters; Fisher's independence condition is violated.
2. Sixteen McNemar rows treat paired cells as independent and ignore clinical clustering.
3. The nonparametric bootstrap distributions are centred on the observed effect, not a null
   distribution; their sign-tail proportions are not calibrated null-bootstrap p-values.
4. Eight rows use a one-sample `t(3)` over four selected model effects. An exact model-level
   sign/sign-flip test has minimum attainable two-sided p = 2/16 = **0.125**.
5. The 152/160 count is structurally 19 of 20 grid templates × eight datasets; the eight failures
   are exactly the `t(3)` rows. It is primarily a property of grid construction.
6. Repeating inferential engines and weights over 28 distinct estimates does not create 160
   independent pieces of evidence.

Only the all-negative descriptive curve should survive into a final report. The cluster-aware
exclusion table in §3 is the interpretable inferential sensitivity analysis.

## 7. Multiplicity

There are two unrelated quantities both labelled “160” in the current files:

1. the 160-row specification curve above; and
2. a separate post-hoc inventory consisting of 4 primary tests, 100 per-model subgroup tests,
   25 pooled subgroup tests, 20 per-model moderator tests, 5 pooled moderator tests, and 6
   between-model contrasts.

The inventory arithmetic remains 160 on v2 because the five factors still contain 25 levels in
total (`correct_letter` 3, negated stem 2, context 2, region 11, year 7). That does not establish
that this family was preregistered, and it must not be used interchangeably with the curve.

For the four primary per-model tests, exact whole-clinical-cluster sign-flip p-values and
adjustments are:

| model | exact cluster sign-flip p | Holm adjusted within 4 | Bonferroni adjusted as 160 |
|---|---:|---:|---:|
| gemini | 1.51004642248e−05 | 1.51004642248e−05 | **0.002416074276** |
| gemma | 3.13717898009e−07 | 6.27435796018e−07 | **5.01948636814e−05** |
| qwen | 1.79580711433e−07 | 5.38742134300e−07 | **2.87329138293e−05** |
| glm | 5.27680295292e−11 | 2.11072118117e−10 | **8.44288472468e−09** |

All four therefore survive even the deliberately broad Bonferroni-160 arithmetic. The limiting
gemini p is 20.695 times smaller than `0.05/160`. The report's “~90× margin” comes from ordinary
pair-level McNemar (`p = 3.4654513e−06`), which ignores clinical clustering; the appropriate
cluster-aware margin is about **20.7×**.

This supports within-model A/B effects. It does not establish a population-of-models effect:
with only four selected models, an assumption-light exact two-sided model-level test cannot attain
p < 0.05.

## 8. Additional diagnostic and limitations

Backend routing was not pinned. Restricting the reported set to cells served by the same backend
in A and B remains directionally consistent: gemini n=318, RD −8.491 pp; gemma n=30, RD −23.333
pp; qwen n=80, RD −18.750 pp; glm n=219, RD −18.721 pp. This is a selected-subset diagnostic, not
a randomised provider adjustment, and the gemma denominator is especially small.

Other limitations:

- Clinical-cluster bootstrap validity requires independence between the constructed top-level
  clusters. Non-context questions are treated as singleton clusters even when they share an exam.
- Cluster sizes are highly imbalanced: 201 nominal clusters but Kish effective count **50.901**;
  the largest cluster contains 80 cells. The leave-one-cluster results are therefore important.
- `runs=1` gives no within-item/model repeatability estimate.
- Exclusion/adjudication rules are post-hoc. This audit checks their mechanics and sensitivity,
  not the medical merits of every exclusion.
- Position-artifact randomisation assumes correct-letter labels are exchangeable across items (or
  within the nine mixed clusters), which was not imposed by experimental randomisation.
- Bootstrap endpoints can move by a few hundredths of a percentage point with RNG and replicate
  count; exact point counts and exact sign-flip p-values do not.

## 9. Stale v1 scripts and outputs

Do not cite or aggregate the following without a hash-pinned v2/v3-population rerun:

- `REPORT.md` §3: 412/1,647 and 325/1,299/208, −15.55 pp, the 1.78-pp span, and
  208/325 leave-one-out counts are v1.
- `sens_exclusion_grid_results.json`: records S2 = 412/1,647/271 and
  S4 = 325/1,299/208.
- `sens_speccurve_results.json` and `sens_speccurve_table.txt`: primary rows use
  325/1,299/208 and defect-only rows use 412/1,647/271.
- `sens_refute_curvep_out.json` and `sens_refute_mcfloor_01_out.json`: cached v1 curve/inference.
- `sens_refute_posartifact_02_out.json`: its defect-clean artifact is −7.1507 pp; current v2 is
  −6.5934 pp.
- `sens_refute_gridflip_exact_out.json`: none and position-only rows remain applicable, but its
  defect and both-exclusion rows are v1. In particular it gives S4 −15.5504 and
  p=4.4745e−16; v2 is −15.4996 and exact cluster sign-flip p=1.94715105249e−15.
- `stats_multiplicity_ceiling_output.txt` and `stats_mde_sensitivity*`: contain 325/1,299/208.

Several executable scripts read the current JSON dynamically and would numerically use v2 if run,
but their prose and output handling are stale:

- `sens_exclusion_grid.py` still says “published 325-item analysis,” “11 defective items,” and
  writes an unversioned result file in place.
- `sens_leave_one_out.py` and `sens_position_artifact.py` still describe “14” or “11” defect
  items in labels/comments.
- specification/refutation scripts write unversioned filenames without recording the input hash,
  allowing a v1 result to sit beside a v2/v3-population input with no machine-enforced warning.

Before delivery, version sensitivity outputs, embed the input SHA-256 and analytical-population
counts in every result file, and make report generation refuse artifacts whose manifest does not
match the current paired-data hash.
