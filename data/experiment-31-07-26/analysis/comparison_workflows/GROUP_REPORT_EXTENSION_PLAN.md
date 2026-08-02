# Minimal safe extension plan — model-group comparisons in the portable report

**Scope:** design and regression audit only; no canonical report, analysis, result, database, or
release file was modified by this workflow.  
**Primary artifact audited:** `../REPORT.html`, backed by `../REPORT.md`,
`../final_analysis.py`, `../final_analysis_results.json`, `../build_report_artifact.py`,
`../report_artifact.json`, and `../report_source.sqlite`  
**Current release baseline:** `v3.1-final`, 5 charts, 11 native tables, 12 QA workflows  
**Recommended next release:** `v3.2-final` while retaining metadata/data-export version `v3`

## Bottom line

The report currently compares the four named models within Experiment A and within Experiment B,
then compares each model with itself between A and B. It does **not** yet define or test the two
requested model-group contrasts:

1. requester-defined larger pair (Gemini + GLM) versus requester-defined smaller pair
   (Qwen + Gemma); and
2. proprietary endpoint (Gemini) versus requester-defined open-model group
   (GLM + Qwen + Gemma).

The safest extension is to add fixed, equal-model-weighted group contrasts to the existing common
317-item / 200-clinical-cluster panel. It should show group levels in A, group levels in B, and a
paired difference-in-differences for the A-to-B change. Whole-clinical-cluster bootstrap intervals
and exact whole-cluster sign-flip p-values fit the already approved analysis. Holm adjustment should
cover the six requested hypotheses together.

The report must not describe these as general effects of size, openness, licensing, or ownership.
There are four selected model endpoints, only one proprietary endpoint, and no smaller proprietary
model. Questions provide replication over the item bank; they do not create additional independent
models. The honest inferential target is the four named deployed configurations over the sampled
clinical-question clusters.

## 1. Current omissions

The current report has a strong model-specific spine but lacks the following requested evidence:

- no four-row membership table defining the user-supplied size and availability labels;
- no explicit display of the empty smaller-proprietary cell in the implied 2 × 2 design;
- no equal-weighted larger-versus-smaller contrast in A or B;
- no Gemini-versus-open-model-average contrast in A or B;
- no group-level A-to-B difference-in-differences;
- no multiplicity family for the newly requested post-hoc contrasts;
- no decomposition showing whether a size signal repeats within the open-model subset;
- no clinician-facing explanation of why a fixed comparison of named systems is not a class effect;
- no chart-map/table-omission note explaining why overlapping derived groups should not be drawn as
  if they were four disjoint populations; and
- no new independent statistical and rendered-release QA for the grouped extension.

Everything already present should remain: individual model estimates, pairwise model tables,
cluster-aware A/B results, sensitivity, GIFT limitations, clinical guardrails, source affordances,
and folder-preserving navigation.

## 2. Group definitions and identifiability

Add a visible membership table in the study/population section, immediately after the model list.
Use qualified labels because the report artifacts do not independently audit parameter counts,
active MoE parameters, inference compute, or software licenses.

| named endpoint | requester-defined size group | requester-defined availability group |
|---|---|---|
| Gemini 3.6 Flash | larger | proprietary endpoint |
| GLM-5.2 | larger | open-model group |
| Qwen 3.6 35B-A3B | smaller | open-model group |
| Gemma 4 26B-A4B-IT | smaller | open-model group |

Add this note directly below the table:

> These are requester-supplied analytical labels. The study did not independently audit a common
> model-size measure or the exact licensing/source-availability status of every deployed version.
> There is one proprietary endpoint and no smaller proprietary endpoint, so size, availability,
> and individual model identity cannot be separated as factorial effects.

The missing cell should be stated plainly:

| | requester-defined larger | requester-defined smaller |
|---|---|---|
| proprietary | Gemini | **none** |
| open-model group | GLM | Qwen, Gemma |

This is the central construct-validity limit. Do not fit or describe a 2 × 2 size-by-openness model
as though the factor cells were populated and models were sampled replicates.

## 3. Estimands and statistical method

### Common population and weighting

Use `paired_clean.json` rows with `analysis_include == true`, pivot by exact `(question_id, model)`,
and retain only questions with all four exact model IDs. This excludes only `b320` and gives:

- 317 questions;
- 1,268 model-item cells; and
- 200 top-level clinical clusters.

Use this same common set for **all** grouped A, B, and A/B-change calculations. Every question has
equal weight and every named model has equal weight inside its supplied group. Do not use the
1,271-cell all-available-pair set for these group contrasts, because GLM's missing cell would make
the group weights and denominators unequal.

### Requested fixed contrasts

For each item and condition, calculate:

- size contrast:
  `0.5 × (Gemini + GLM) − 0.5 × (Qwen + Gemma)`;
- availability contrast:
  `Gemini − (GLM + Qwen + Gemma) / 3`; and
- paired change contrast:
  apply the same weights to each model's `(B − A)` outcome.

Define the A/B interaction as:

`(B − A change in first group) − (B − A change in second group)`.

A positive interaction therefore means the first named group lost fewer percentage points. It is a
direct difference-in-differences, not a comparison of whether two separate p-values cross 0.05.

### Inference

For every contrast:

1. Sum item-level contributions within the 200 clinical clusters.
2. Compute a two-sided exact sign-flip distribution over the non-zero whole-cluster contributions.
3. Scale fractional contrasts to integers before convolution: multiply the size contrast by 2 and
   the availability contrast by 3. Never round group means or cluster contributions.
4. Compute unadjusted 95% percentile intervals from 100,000 whole-clinical-cluster bootstrap draws.
   Every sampled cluster must carry all of its items, models, and conditions; a repeated cluster
   draw must retain its multiplicity.
5. Apply Holm correction across the six requested tests: size and availability in A, in B, and on
   the A/B difference-in-differences.

State the assumptions next to the results: independent top-level clusters and sign-exchangeability
of whole-cluster contributions under the null. The models were not randomized to categories; these
are sampling-model tests over item clusters, conditional on the four selected endpoints.

### Recommended triangulation

Add two explicitly exploratory restricted decompositions, with a **separate** six-test Holm family:

- within the requester-defined larger pair, Gemini versus GLM; and
- within the requester-defined open-model group, GLM versus the equal-weighted Qwen/Gemma mean.

The second is the most important additional comparison. It holds the supplied availability label
constant and shows whether the size pattern repeats inside the open group. The first is already
partly visible in the existing pairwise A/B tables, but its A-to-B interaction is useful for showing
that the proprietary-average pattern is not generated only by including the two smaller models.
Neither restricted comparison creates model-level replication or identifies a causal attribute.

## 4. Expected numerical acceptance values

The point estimates and exact p-values below were independently reconstructed from
`paired_clean.json` and agree with `GROUP_COMPARISONS_STATS.md`. Bootstrap limits below use that
workflow's planned 100,000-draw canonical seed (`20260801`); ordinary Monte Carlo seed changes may
move a displayed endpoint by a few hundredths of a percentage point but must not change a decision.

### Requested primary six

| context | comparison | first group | second group | contrast | unadjusted 95% CI | exact cluster p | Holm p across six |
|---|---|---:|---:|---:|---:|---:|---:|
| A | larger pair − smaller pair | 95.43% | 83.75% | **+11.67 pp** | +8.81 to +14.98 | 1.66×10⁻¹³ | **6.65×10⁻¹³** |
| B | larger pair − smaller pair | 82.02% | 66.09% | **+15.93 pp** | +11.80 to +20.18 | 1.88×10⁻¹⁰ | **5.65×10⁻¹⁰** |
| A→B | larger change − smaller change | −13.41 pp | −17.67 pp | **+4.26 pp** | −0.38 to +8.56 | .0925 | **.0925** |
| A | Gemini − open-model mean | 97.79% | 86.86% | **+10.94 pp** | +8.36 to +14.03 | 1.37×10⁻¹⁴ | **6.83×10⁻¹⁴** |
| B | Gemini − open-model mean | 89.27% | 68.98% | **+20.29 pp** | +16.16 to +24.47 | 2.85×10⁻¹⁷ | **1.71×10⁻¹⁶** |
| A→B | Gemini change − open-model mean change | −8.52 pp | −17.88 pp | **+9.36 pp** | +4.91 to +13.66 | .000161 | **.000321** |

Required interpretation:

- The named larger pair has higher accuracy in both A and B.
- The data do **not** resolve a smaller A-to-B decline for the larger pair; its interaction interval
  includes zero and Holm p is .0925. Do not write “larger models are more robust.”
- Gemini is higher than the equal-weighted three-model open-group mean in A and B and has a smaller
  percentage-point decline. Because proprietary status has one endpoint, this must be written as
  “Gemini versus these three named alternatives,” not a general ownership effect.
- The percentage-point interaction is baseline- and scale-dependent. Existing log-odds
  heterogeneity cautions must remain visible.

### Exploratory restricted decompositions

| context | restricted contrast | contrast | unadjusted 95% CI | exact cluster p | Holm p across exploratory six |
|---|---|---:|---:|---:|---:|
| A | Gemini − GLM, within supplied larger pair | +4.73 pp | +1.91 to +7.82 | .00332 | .00664 |
| B | Gemini − GLM, within supplied larger pair | +14.51 pp | +10.03 to +19.27 | 2.44×10⁻⁸ | 1.47×10⁻⁷ |
| A→B | Gemini change − GLM change | +9.78 pp | +4.81 to +14.97 | .000375 | .00150 |
| A | GLM − Qwen/Gemma mean, within supplied open group | +9.31 pp | +6.01 to +12.90 | 2.11×10⁻⁷ | 1.06×10⁻⁶ |
| B | GLM − Qwen/Gemma mean, within supplied open group | +8.68 pp | +3.86 to +13.41 | .00140 | .00419 |
| A→B | GLM change − Qwen/Gemma mean change | −0.63 pp | −6.20 to +4.40 | .859 | .859 |

The within-open result is particularly useful: GLM has a higher **level** in A and B, but no
detectable advantage in A-to-B percentage-point retention. That prevents category composition from
being mistaken for a general size-resilience effect.

## 5. Canonical result schema

Add a new top-level object to `final_analysis_results.json` rather than scattering group values
across existing model objects:

```text
model_group_comparisons
├── definitions
│   ├── label_source: requester_supplied
│   ├── size: {larger: [...], smaller: [...]}
│   ├── availability: {proprietary: [...], open_model: [...]}
│   └── identifiability_note
├── population
│   ├── items: 317
│   ├── cells: 1268
│   ├── clinical_clusters: 200
│   └── excluded_for_complete_case: [b320]
├── weighting
├── primary_family
│   ├── multiplicity: Holm across six requested contrasts
│   ├── size
│   │   ├── A
│   │   ├── B
│   │   └── change_difference
│   └── availability
│       ├── A
│       ├── B
│       └── change_difference
└── exploratory_restricted_family
    ├── multiplicity: Holm across six restricted contrasts
    ├── within_larger_gemini_minus_glm
    └── within_open_glm_minus_small_open_mean
```

Every leaf result should carry explicit labels, member model IDs, member counts, group estimates,
contrast direction, point estimate, bootstrap CI, raw exact p, adjusted p, non-zero cluster count,
seed, and replicate count. Add assertions that weights sum to zero, group weights average to one,
all 317 items have four models, all result values are finite, and all p-values/intervals fall in
valid ranges.

Recommended analysis version change:

- `analysis_version`: `v3.1-final` → `v3.2-final`;
- metadata/data-export version remains `v3` because canonical input rows and exclusions do not
  change; and
- record the updated `final_analysis.py` hash in the output bundle.

## 6. Report placement and prose

Preserve the current A → B → paired A/B order and all existing model-specific evidence.

### Study/population section

After the four-model list:

- add the four-row membership table;
- add the incomplete 2 × 2 membership matrix or an equally explicit sentence;
- define equal model weighting and the common 317-item panel; and
- call the labels requester-defined.

### Experiment A section

After the existing four-model chart, accuracy table, and six-pair table, insert:

1. `### Requested model-group contrasts in A`;
2. a native two-row primary group-contrast table;
3. an adjacent interpretation paragraph; and
4. then the physician-facing explanation, updated to translate the group levels without making a
   class or clinical claim.

Suggested physician language:

> On these 317 examination questions, the two deployments labelled larger by the requester
> averaged about 95 key-matched answers per 100, versus 84 for the two labelled smaller. Gemini
> scored about 98 per 100, versus 87 for the equal-weighted average of the three deployments placed
> in the open-model group. These are comparisons of selected systems on an exam bank, not evidence
> that size or ownership caused the difference and not estimates of patient-level diagnostic
> performance.

### Experiment B section

Use the same placement and schema, with B values. Keep the existing individual-model result that
GLM and Qwen are unresolved; the open-group average must not hide member heterogeneity.

Suggested physician language:

> Under the engineered B format, the requester-defined larger pair averaged about 82 key-matched
> answers per 100, versus 66 for the smaller pair. Gemini scored about 89 per 100, versus 69 for the
> named open-model average. The group averages summarize these four deployments only; they do not
> establish a general advantage of size, licensing, or proprietary development, and they are not
> bedside diagnostic-accuracy estimates.

### Paired A/B section

After the existing model-specific A/B table and scale-dependent heterogeneity paragraph, insert:

1. `### Do the supplied model groups change differently from A to B?`;
2. the two-row requested difference-in-differences table;
3. a compact restricted-decomposition table or paragraph, clearly labelled exploratory; and
4. then the updated physician-facing explanation.

Suggested physician language:

> Both supplied size groups performed worse in B. The larger pair lost about 13 answers per 100
> and the smaller pair about 18, but the 4-point difference in decline was uncertain and did not
> meet the corrected statistical threshold. Gemini lost about 9 points versus about 18 for the
> average of the three named open models; that is a Gemini-versus-three-model finding, not proof
> that proprietary status protects performance. None of these benchmark contrasts estimates a
> change in patient outcomes.

### Methods, limitations, and recommendations

Update the statistical-method section with the fixed contrast formulas, integer-scaled exact sign
flips, equal model weighting, common panel, bootstrap seed, two Holm families, and model-level
generalization limit. Add to “Not supported”:

- general effects of model size, openness, licensing, or ownership;
- a causal “robustness” effect from a risk-scale difference-in-differences; and
- a factorial size × availability conclusion.

Add one recommendation: repeat the comparison with several independently selected models in every
size/availability cell, including smaller proprietary models, and predefine a common size measure.

## 7. Portable artifact and table schema

Add these replayable SQLite/artifact datasets:

| dataset/table | rows | essential fields |
|---|---:|---|
| `model_group_membership` | 4 | model, size_group, availability_group, label_source |
| `condition_a_group_contrasts` | 2 | grouping, first_group, first_accuracy, second_group, second_accuracy, difference, ci95, exact_cluster_p, holm_p |
| `condition_b_group_contrasts` | 2 | same as A |
| `group_change_contrasts` | 2 | grouping, first_change, second_change, difference_in_changes, ci95, exact_cluster_p, holm_p |
| `group_restricted_decompositions` | 6 | restriction, context, first_estimate, second_estimate, difference, ci95, exact_cluster_p, holm_p |

Materialize each table in `report_source.sqlite`, add a canonical manifest/evidence source with an
exact `SELECT * FROM ...` query, add it to the bounded artifact snapshot, and expose a native table
in the appropriate section. Keep p-values as labelled strings via `p_value_text`; the portable
renderer previously coerced small numeric p-values to `0`.

Recommended native table titles:

- `Requester-defined model groups`
- `Experiment A fixed group contrasts`
- `Experiment B fixed group contrasts`
- `Difference in A-to-B change between supplied groups`
- `Exploratory restricted decompositions`

Use `movement: true` only on signed contrast columns, not on current accuracy levels.

### Chart decision

Do **not** add a required chart for the group extension. The four group labels overlap: Gemini and
GLM contribute to the size summary, and Gemini/GLM/Qwen/Gemma reappear in the availability
summary. Drawing all four bars together would visually imply four disjoint populations, while the
meaningful evidence is the exact fixed contrast and interval. The existing A, B, and A/B model
charts already display the underlying values. Native tables are the more honest form for exact
derived contrasts.

Record this omitted-chart rationale in `CHART_MAP.md`. If a visual is nevertheless desired, use two
clearly separated panels (size classification and availability classification) with identical
zero-based scales and explicit “overlapping classifications” language; never use a single four-bar
ranking.

Expected baseline after the table-only extension: 5 charts and 16 native tables (11 existing + 5
new). All existing chart IDs, table IDs, block IDs, sources, and prose must remain unless a directly
dependent update is required.

## 8. Source lineage and build order

The only analytical source should remain the hash-pinned canonical `paired_clean.json`; do not
promote exploratory JSON files into report sources.

Build in this order:

1. Patch `final_analysis.py` with deterministic group-contrast computation and assertions.
2. Rebuild `final_analysis_results.json`; verify its input and code hashes.
3. Patch `REPORT.md` and `CHART_MAP.md`; preserve current section numbering and model-specific text.
4. Patch `build_report_artifact.py` with the five datasets, five source/query entries, five native
   tables, and section insertions.
5. Rebuild `report_source.sqlite` and `report_artifact.json`.
6. Compare old/new artifact structures: additions should be limited to the grouped evidence,
   directly dependent narrative, analysis version, generated timestamp, sources, and QA rows.
7. Run the Data Analytics portable packaging command once to regenerate `REPORT.html` and require
   `validation`, `package`, and `verification` to pass.
8. Run independent grouped-statistics QA and independent adversarial rendered/clinical QA.
9. Only after all QA rows are final, rebuild the QA summary, report artifact/HTML if needed, and
   `RELEASE_MANIFEST.json`.
10. Perform a final read-only hash replay of every manifest-pinned file.

Keep the organized view additive and path-stable. Its release, canonical-data, rebuild-pipeline,
and QA entries are symlinks to canonical paths, so updating the target files is sufficient. Do not
move, delete, duplicate, or replace historical exploratory files.

## 9. Release versioning and QA integration

Recommended release bookkeeping:

- release: `v3.2-final`;
- `qa_workflows`: 14 after two new independent workflows;
- retain all 12 prior QA records;
- add `QA13_GROUP_COMPARISONS.md` for independent recomputation and inferential audit;
- add `QA14_GROUP_REPORT_RELEASE.md` for construct, clinical, source-replay, render, and folder QA;
- update `qa_summary.json` and `QA_SUMMARY.md` only after both verdicts are final;
- update hashes for all changed canonical files and add the new QA records to
  `RELEASE_MANIFEST.json`; and
- keep `status: ready` only when there is no pending QA row.

Any generated/modified Python is first-party code. Invoke the required Snyk Code scan after the
code change, attempt to remediate findings, and rescan. If authentication again returns
`SNYK-0005`/HTTP 401, record the limitation in `SECURITY_SCAN.md` and do not claim a pass. Also run
Ruff and the repository test suite.

## 10. Statistical regression risks

1. **Unequal denominators.** Group inference must use the 317-item common panel. Keep the existing
   individual A/B table on all 1,271 valid pairs.
2. **Wrong unit of replication.** P-values quantify variation over item clusters for fixed named
   endpoints, not variation over populations of models.
3. **Fraction rounding.** Exact sign flips must use integer-scaled rational weights, never rounded
   group means.
4. **Bootstrap duplicate collapse.** A cluster drawn twice must remain twice in the sampled totals.
5. **Sign reversal.** Within-condition tables use first minus second; A/B uses B minus A; the
   interaction uses first-group change minus second-group change.
6. **Average-of-averages drift.** Equal model weights are intentional. Recalculate from model
   numerators on the common panel and assert group member counts.
7. **Multiplicity leakage.** Do not reuse the current six-model-pair Holm values. The requested six
   group hypotheses and the exploratory restricted six are separate declared families.
8. **Scale overclaim.** A percentage-point difference in decline is not a universal robustness
   ranking; preserve the existing log-odds caveat.
9. **Singleton proprietary endpoint.** Do not use plural “proprietary models” in findings.
10. **Incomplete 2 × 2 design.** Do not estimate or imply a size × availability factorial effect.
11. **Unaudited labels.** Use “requester-defined open-model group,” not an unsupported legal claim
    that exact deployed versions are fully open source.
12. **Heterogeneity hidden by an average.** Keep the individual model tables adjacent; GLM, Qwen,
    and Gemma are not interchangeable.

## 11. Browser and rendered-release QA assertions

The current portable report passed local Chromium with 5 non-empty charts, 11 native tables,
working source dialogs, no console errors, no external network calls, and no horizontal overflow at
1440×1000 and 390×844. The updated release should preserve that baseline and add these assertions.

### Reading order and semantic content

- Experiment A remains before Experiment B, which remains before paired A/B.
- The membership table appears in the population section before any grouped claim.
- Each A and B group table appears after the existing model/pairwise evidence and before that
  section's `Clinical interpretation for physicians` heading.
- The A/B group-change and restricted-decomposition evidence appears before the A/B clinician
  block.
- Searchable rendered text includes `requester-defined`, `one proprietary endpoint`, and the
  inability to separate size, availability, and model identity.
- Rendered text does not contain “large models are more robust,” “proprietary models outperform,”
  or a causal ownership/size statement.
- The size interaction shows `+4.26 pp`, an interval spanning zero, and corrected `p = 0.0925`.
- The availability interaction shows `+9.36 pp`, a positive interval, and corrected
  `p = 0.000321` (formatting tolerance only in the last displayed digit).
- No primary p-value renders as bare `0`, and no raw Markdown markers leak.

### Dataset, table, and source replay

- `model_group_membership` has exactly 4 rows.
- A and B requested group tables have exactly 2 rows each.
- The group-change table has exactly 2 rows.
- The restricted-decomposition table has exactly 6 rows if the recommended triangulation is used.
- `report_source.sqlite` passes `PRAGMA integrity_check`.
- Every artifact snapshot dataset matches `SELECT *` from its corresponding SQLite table in row
  count, column order, values, and nulls.
- The source drawer for a grouped table shows Overview, Data preview, and SQL; the query is the
  exact expected `SELECT * FROM ...`, the preview row count is correct, and Copy query is available.
- All source, dataset, card, chart, table, and block IDs are unique and every widget is reachable.

### Desktop/mobile rendering

- page-level horizontal overflow is zero at both 1440×1000 and 390×844;
- all 5 retained charts have non-zero dimensions at both widths;
- all 16 native tables are visible, and dense tables remain inside horizontal scroll containers;
- group and confidence-interval labels do not clip;
- clinical headings remain below their final corresponding table;
- the semantic/no-script representation contains the new tables;
- source controls remain keyboard reachable;
- browser console is clean; and
- the network log contains only the local `file://.../REPORT.html` load.

### Release seal

- QA source table, artifact dataset, HTML table, manifest count, and filesystem QA files all agree
  on 14 unique workflows;
- `RELEASE_MANIFEST.json` reports `v3.2-final`, `status: ready`, and no pending QA;
- every manifest-pinned path exists and matches its SHA-256;
- organized-view symlinks resolve and no previously inventoried file is missing; and
- the final browser/hash check is read-only and does not stale the manifest after it passes.

## 12. Acceptance decision

Ship the grouped extension only if it is framed as a fixed comparison of named deployments,
retains individual-model heterogeneity, uses the common 317-item panel and whole-cluster inference,
declares both multiplicity families, and exposes the incomplete design. The requested findings are
decision-useful, but their correct conclusion is narrower than a class ranking:

- higher grouped accuracy levels are observed in A and B;
- the larger-pair A-to-B retention advantage is unresolved;
- the Gemini-versus-open-average A-to-B difference is detectable but confounded with Gemini
  identity; and
- the open-only sensitivity does not reproduce a size advantage in A-to-B retention.

That framing adds the requested perspectives without converting four selected model endpoints into
unsupported population-level claims.
