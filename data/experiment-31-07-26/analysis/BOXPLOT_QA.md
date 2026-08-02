# Annotated-boxplot implementation and QA record

**Release extension:** v3.3.1-final (presentation repair; approved v3.3 analysis unchanged)  
**Scope:** descriptive visualization only; approved point estimates and inferential tests unchanged  
**Verdict:** PASS

## Chart contract

Eight native portable-artifact boxplots were added:

1. Experiment-A model accuracy
2. Experiment-A requested-group accuracy
3. Experiment-B model accuracy
4. Experiment-B requested-group accuracy
5. Model-specific A-to-B change
6. Requested-group A-to-B change
7. Primary and secondary differences in A-to-B changes
8. Partial GIFT-minus-OpenRouter change by model

Each chart uses the same deterministic 100,000 whole-clinical-cluster bootstrap distribution as
its corresponding analysis. The visible label gives the observed estimate; whisker caps mark the
minimum and maximum; the outlined box spans Q1–Q3; and a dark internal divider marks the median.
The native tooltip repeats all five values. The adjacent tables remain
authoritative for 95% intervals and exact/cluster-aware tests. The plots do not present raw binary
answers as continuous data.

## Data checks

- Eight chart datasets contain four annotated rows each: 32 rows total.
- All 32 five-number summaries satisfy `minimum ≤ Q1 ≤ median ≤ Q3 ≤ maximum`.
- Every observed estimate and 95% interval lies inside its saved bootstrap range.
- Every row records 100,000 bootstrap replicates and the relevant clinical-cluster count.
- All eight SQLite tables exactly equal their `report_artifact.json` snapshot datasets.
- `report_source.sqlite` returns `PRAGMA integrity_check = ok`.
- The approved pooled A-to-B estimate and requested-group interaction results are unchanged.

## Rendering checks

The canonical portable builder completed validation, packaging, and Chromium verification:

- 13 charts total: five existing bars plus eight native boxplots
- 17 native tables and 50 report blocks
- desktop width: 1440 px
- mobile width: 390 px
- source dialog and keyboard-semantic source action: pass
- external requests, browser errors, chart geometry, and overflow checks: pass

Each comparison section contains an adjacent explanation of the bootstrap-boxplot semantics and
retains its physician-facing interpretation. Long model/group labels include the observed estimate
and passed the narrow-width verifier.

The v3.3.1 visual regression check also verifies, for every one of the 32 plotted rows:

- one minimum-to-maximum whisker line;
- two visible end caps;
- one outlined Q1-to-Q3 rectangle;
- explicit Q1 and Q3 boundary strokes; and
- one high-contrast median divider.

## Local code and security checks

- Ruff: pass on `final_analysis.py` and `build_report_artifact.py`
- Repository tests: 60/60 pass
- Snyk Code: not completed; the installed CLI returned `SNYK-0005` / HTTP 401 because the local
  credentials were not recognized. This is not a Snyk pass.

## Final assessment

PASS. The boxplots are source-backed uncertainty displays aligned with the report's cluster-aware
estimands. They add no new causal or model-class claim and preserve the report's fixed-model,
singleton-proprietary, partial-coverage, and clinical-use caveats.
