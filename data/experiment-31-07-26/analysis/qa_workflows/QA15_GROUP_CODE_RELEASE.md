# QA15 — adversarial code, lineage, and release audit for v3.2 group comparisons

**Reviewer role:** independent code and release QA  
**Code audited:** `final_analysis.py` and `build_report_artifact.py`  
**Release candidate audited:** `final_analysis_results.json`, `REPORT.md`,
`report_source.sqlite`, `report_artifact.json`, `REPORT.html`, and `00_ORGANIZED_VIEW/`  
**Verdict:** **PASS**

## Bottom line

The v3.2 group-comparison implementation is internally consistent, deterministic in the pinned
project environment, and traceable to the v3 canonical paired rows. An independent implementation
reconstructed the 317-item complete-case population, every requested group accuracy, all primary
and secondary group contrasts, every A-to-B group change, and every exact clinical-cluster
sign-flip p-value. The values matched the result bundle without using the report tables as
calculation inputs.

The release builder materializes the same 20 datasets into SQLite and the portable artifact, all
widget fields resolve, all cards/charts/tables are reachable from a unique block, all source hashes
match, and the organized view remains an additive symlink index with no broken targets. No unsafe
recursive operation, source-data mutation, or deletion path was introduced.

Two release-hardening issues identified during this audit were repaired before this verdict:

1. QA readiness originally checked only for a `PENDING` initial verdict. Every QA row now has a
   machine-readable `final_status`, and the artifact is `ready` only when all final statuses are
   `PASS`.
2. The report now explicitly labels the requested model groups as a post-hoc analysis, and the
   result bundle records each group-bootstrap seed and replicate count.

The integrated v3.2 HTML and release manifest subsequently passed the final read-only seal: all 28
pinned paths matched, all 15 QA rows had final status `PASS`, both SQLite databases passed
integrity checks, all 20 materialized report tables matched the portable artifact, and all 562
organized-view symlinks resolved.

## 1. Data lineage and estimands

Independent reconstruction began from `paired_clean.json`, retaining only
`analysis_include == true`. The strict all-model intersection is:

| quantity | independently reconstructed | v3.2 bundle |
|---|---:|---:|
| common items | 317 | 317 |
| model×item cells | 1,268 | 1,268 |
| clinical clusters | 200 | 200 |
| item excluded only for complete-case comparison | `b320` | `b320` |

Each item has exactly four model rows, and every model row for an item has the same clinical-cluster
identifier. The code's grain assertion would reject duplicate or missing model rows. The input
files and run database remain hash-pinned before analysis starts, and the database is opened as a
read-only immutable SQLite snapshot after refusing a non-empty WAL.

The requested estimand is implemented as an equal-weight mean over the named fixed models and the
317 common items. Because every model is observed on the same items, the cell aggregation gives
each named model equal weight. Integer least-common-multiple scaling preserves exact group means
for both 2-versus-2 and 3-versus-1 contrasts.

## 2. Independent numerical reconstruction

### Group accuracies

| requested group | Experiment A | Experiment B | B − A |
|---|---:|---:|---:|
| large: gemini + glm | 95.43% | 82.02% | −13.41 pp |
| small: qwen + gemma | 83.75% | 66.09% | −17.67 pp |
| open-model: glm + qwen + gemma | 86.86% | 68.98% | −17.88 pp |
| proprietary endpoint: gemini | 97.79% | 89.27% | −8.52 pp |

### Primary group contrasts

An independent integer-convolution sign-flip implementation reproduced the exact p-values:

| contrast | point estimate | exact cluster p | bundle match |
|---|---:|---:|---:|
| A: large − small | +11.67 pp | 1.6635304e-13 | pass |
| A: open-model − proprietary | −10.94 pp | 1.3653141e-14 | pass |
| B: large − small | +15.93 pp | 1.8840957e-10 | pass |
| B: open-model − proprietary | −20.29 pp | 2.8528248e-17 | pass |
| change: large − small | +4.26 pp | 0.0924796 | pass |
| change: open-model − proprietary | −9.36 pp | 0.000160693 | pass |

Holm adjustment is correctly applied across those six prespecified report-update hypotheses. The
four overlapping within-group A-to-B declines use a separate four-test Holm family.

### Secondary triangulation

The two partial-matching perspectives also reproduced:

- within the large pair, gemini minus glm changes by +9.78 pp from A to B
  (raw exact p = 0.000375135; six-test secondary Holm p = 0.00150054);
- within the requested open-model subset, glm minus the qwen/gemma mean changes by −0.63 pp
  (raw and Holm p = 0.858751).

These checks support the report's restrained conclusion: the aggregate labels describe four fixed
deployments, not randomly sampled model classes. The missing small-proprietary cell prevents a
factorial separation of size from model access.

## 3. Statistical implementation review

- Whole clinical clusters, not rows, are resampled. Repeated cluster draws retain multiplicity in
  the sampled index array and are not collapsed back by question ID.
- Bootstrap ratio denominators are positive on the complete-case population. Seeds and 100,000
  replicate counts are deterministic and now recorded in each group result.
- Exact sign flips operate on integer-scaled whole-cluster contributions; zero-contribution
  clusters are correctly omitted from the random-sign denominator but retained in the reported
  total-cluster count.
- Holm adjustment is monotone and bounded for the six primary, four decline, and six secondary
  families.
- The report states the sign-exchangeability assumption, uneven cluster sizes, fixed-model scope,
  post-hoc status, and absence of model-level random sampling.
- Binary correctness does not require normally distributed observations; the report does not run
  a meaningless normality test on 0/1 outcomes.

No average-of-averages, denominator-shift, duplicate-cluster, or model-level pseudoreplication bug
was found in the code. The report explicitly warns that question-level evidence cannot establish a
population-level large-versus-small or open-versus-proprietary model-class effect.

## 4. Determinism and reproducibility

Running `final_analysis.py` through the repository's `uv` environment into a temporary output
produced a byte-identical `final_analysis_results.json`. A temporary run of
`build_report_artifact.py` produced byte-identical `report_source.sqlite` and
`report_artifact.json`. The analysis output records Python, NumPy, SQLite, quantile method,
bootstrap seed, input hashes, and code hash.

Running with an unrelated system Python reproduced the analytical values but changed the recorded
Python/NumPy environment strings, and therefore the file hash. The supported rebuild instructions
now use `uv run python` so byte-identical release output is obtained from the project environment.

## 5. Artifact and source-contract checks

The following checks passed on the rebuilt candidate:

- SQLite `PRAGMA integrity_check`: `ok`;
- 20/20 artifact datasets exactly equal the corresponding `SELECT *` SQLite rows;
- all source paths exist and every artifact source SHA-256 matches;
- no duplicate source, card, chart, table, or block identifiers;
- every table column and chart/card encoding refers to an existing dataset field;
- all three cards, five charts, and seventeen tables are reachable from report blocks;
- no orphaned native widget;
- the new group tables occur in A, B, and paired A/B sections without removing the prior primary,
  sensitivity, cross-pipeline, run-status, limitation, provenance, or recommendation sections.

The explicit `final_status` QA field now makes readiness machine-checkable. Historical initial
FAIL findings can remain visible while their repaired release status is independently represented.

## 6. Safety and local verification

| check | result |
|---|---|
| Python compilation of both modified files | pass |
| Ruff on both modified files | pass |
| repository test suite | 60/60 pass |
| deterministic result rebuild under `uv` | byte-identical |
| deterministic source/artifact rebuild | byte-identical |
| Snyk Code | not completed: `SNYK-0005`, HTTP 401 authentication failure |

The Snyk failure is an external authentication limitation, not a scan pass, and is correctly
disclosed in `SECURITY_SCAN.md`. No Snyk-clean claim is made.

File-writing code uses explicit known targets, same-directory temporary files, `fsync`, and atomic
replacement. The SQLite materializer quotes internal table and column identifiers. Its only unlink
operation targets the temporary file it just created. No deletion, broad glob, recursive mutation,
or movement of experiment evidence was introduced.

## 7. Organized-view preservation

`00_ORGANIZED_VIEW/` contains 562 relative symbolic links. All 562 resolve; none is broken. The
canonical release and rebuild links resolve to the live root-level files, so report updates appear
in the organized view without copying or moving evidence. The three documented Markdown navigation
links also resolve.

## Final release seal

At the start of this audit, `RELEASE_MANIFEST.json` was the previous v3.1 seal and therefore did not
match the newly rebuilt v3.2 files. The release owner then integrated QA13–QA15, rebuilt the full
chain, packaged the final HTML, and generated `v3.2-final` with 28 pinned paths.

The final read-only audit found **28/28 hashes matching**, release and analysis version
`v3.2-final`, artifact status `ready`, **15/15 QA final statuses PASS**, SQLite integrity `ok` for
both the run database and report source, exact equality across all 20 artifact/SQLite datasets,
complete reachability of three cards, five charts, and seventeen tables, and **562/562 organized
symlinks resolving**. Updating this memo from integration PASS to final PASS changes only its own
hash; the release owner can refresh that single manifest entry without rebuilding any analytical
artifact.

## Final verdict

**PASS.** The new group comparisons are arithmetically correct, use the
intended common population and cluster-aware methods, preserve prior report content, expose their
post-hoc and fixed-model limitations, and rebuild deterministically under the project environment.
No code, statistical, lineage, source-contract, preservation, or release remediation remains.
