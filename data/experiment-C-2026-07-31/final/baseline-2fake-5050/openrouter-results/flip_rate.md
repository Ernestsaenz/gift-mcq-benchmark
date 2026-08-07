# Experiment C (2-fake / 50-50 baseline) — OpenRouter answer-flip analysis (Analyst 2)

**Primary outcome: per-question answer FLIP** (did the selected letter change between the
CONTROL and ALTERED version of the same base question). Accuracy columns are secondary/supporting
(the altered set is *not* clinically certified answer-key-preserving).

## Provenance (cite verbatim)

- Date **2026-08-05**. Provider: **OpenRouter only**. temperature=0, single-shot (runs=1),
  prompt_version = harness default `BENCHMARK_PROMPT_VERSION` (`mcq_es_v4`).
- 4 models: `google/gemini-3.5-flash`, `qwen/qwen3.7-max`, `qwen/qwen3.6-35b-a3b`,
  `google/gemma-4-26b-a4b-it`.
- 4 experiments, 100 PRIMARY questions each: `expC_2f_bm_control`, `expC_2f_bm_altered`,
  `expC_2f_an_control`, `expC_2f_an_altered`. Arms: **BM** (biomarker), **AN** (anatomy); each
  pairs a CONTROL (unchanged) and an ALTERED (control + one fabricated finding) version of the
  SAME 100 base questions.
- Result health (harness status): every experiment planned=400 completed=400 api_failed=0
  parse_failed=0; 100% parse; 1600/1600 calls. OpenRouter spend ~$7.79.
- Read-only DB: `/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/runs/expC-openrouter/expC_2fake_5050.sqlite`
- Cluster ids (independence unit) from the run-ready workbooks:
  `.../baseline-2fake-5050/run/expC-bm-control.xlsx` (BM, 33 clusters) and
  `.../baseline-2fake-5050/run/expC-an-control.xlsx` (AN, 34 clusters).

## Method

- Reused the QA-validated `run/analyze_flip_rate.py` (imported as a module) for the pairing,
  the exclusion rule, and BOTH cluster-robust 95% CIs. Deps verified present in `.venv`
  (numpy 2.5.1, statsmodels 0.14.6, openpyxl 3.1.5), so it was reused rather than
  re-implemented in stdlib.
- **Pairing**: by `base_question_id` (the DB `question_id`, e.g. `b1`), which is identical
  across CONTROL and ALTERED within an arm (BM 100/100, AN 100/100 intersect). Flip = 1 when
  `selected_letter` differs CONTROL vs ALTERED.
- **Exclusions**: a pair is dropped only if either side failed to parse to a usable letter
  (`parse_status` not in {ok, ok_conflict}) or the question lacks a cluster. Observed
  exclusions = **0** everywhere (parse was 100%).
- **Analytic CI (CR1)**: statsmodels OLS of the 0/1 flip vector on an intercept,
  `cov_type="cluster"` on the cluster id, t-interval with df = n_clusters - 1.
- **Bootstrap CI**: whole-cluster percentile bootstrap (resample clusters with replacement,
  carrying every question in a sampled cluster), n_boot=10000, seed=20260731.
- **Flip DIRECTION** (added here; among flips only, by `strict_correct` each side):
  correct->wrong, wrong->correct, wrong->wrong. `correct_letter` is identical CONTROL vs
  ALTERED for all 100 questions in both arms, so a correct->correct flip is impossible;
  the residual guard counted **0** such cases (expected 0).
- **Pooled per arm**: all four models stacked, clustered on the cluster id (each cluster's
  observations across all models = one group; the conservative choice because the same base
  question answered by four models is nested in one cluster). Pooling mixes heterogeneous
  models, so treat the pooled number as a descriptive summary, not a per-model estimate.

## Results

### Arm BM (biomarker) — per model

| model | n | flips | flip rate | 95% CI (CR1) | 95% CI (bootstrap) | clusters | C->W | W->C | W->W | acc ctrl | acc alt |
|---|--:|--:|--:|---|---|--:|--:|--:|--:|--:|--:|
| `google/gemini-3.5-flash` | 100 | 0 | 0.00% | [0.00%, 0.00%] | [0.00%, 0.00%] | 33 | 0 | 0 | 0 | 97.00% | 97.00% |
| `qwen/qwen3.7-max` | 100 | 6 | 6.00% | [1.84%, 10.16%] | [2.11%, 10.81%] | 33 | 3 | 3 | 0 | 92.00% | 92.00% |
| `qwen/qwen3.6-35b-a3b` | 100 | 7 | 7.00% | [2.36%, 11.64%] | [2.82%, 13.10%] | 33 | 2 | 5 | 0 | 84.00% | 87.00% |
| `google/gemma-4-26b-a4b-it` | 100 | 9 | 9.00% | [3.32%, 14.68%] | [4.17%, 16.67%] | 33 | 5 | 1 | 3 | 88.00% | 84.00% |

### Arm BM (biomarker) — pooled across 4 models

| model | n | flips | flip rate | 95% CI (CR1) | 95% CI (bootstrap) | clusters | C->W | W->C | W->W | acc ctrl | acc alt |
|---|--:|--:|--:|---|---|--:|--:|--:|--:|--:|--:|
| `POOLED (4 models)` | 400 | 22 | 5.50% | [2.84%, 8.16%] | [3.19%, 9.00%] | 33 | 10 | 9 | 3 | n/a | n/a |

### Arm AN (anatomy) — per model

| model | n | flips | flip rate | 95% CI (CR1) | 95% CI (bootstrap) | clusters | C->W | W->C | W->W | acc ctrl | acc alt |
|---|--:|--:|--:|---|---|--:|--:|--:|--:|--:|--:|
| `google/gemini-3.5-flash` | 100 | 0 | 0.00% | [0.00%, 0.00%] | [0.00%, 0.00%] | 34 | 0 | 0 | 0 | 96.00% | 96.00% |
| `qwen/qwen3.7-max` | 100 | 2 | 2.00% | [-0.54%, 4.54%] | [0.00%, 5.26%] | 34 | 1 | 1 | 0 | 92.00% | 92.00% |
| `qwen/qwen3.6-35b-a3b` | 100 | 8 | 8.00% | [2.79%, 13.21%] | [3.01%, 14.06%] | 34 | 5 | 1 | 2 | 91.00% | 87.00% |
| `google/gemma-4-26b-a4b-it` | 100 | 10 | 10.00% | [3.15%, 16.85%] | [4.67%, 20.55%] | 34 | 8 | 1 | 1 | 88.00% | 81.00% |

### Arm AN (anatomy) — pooled across 4 models

| model | n | flips | flip rate | 95% CI (CR1) | 95% CI (bootstrap) | clusters | C->W | W->C | W->W | acc ctrl | acc alt |
|---|--:|--:|--:|---|---|--:|--:|--:|--:|--:|--:|
| `POOLED (4 models)` | 400 | 20 | 5.00% | [2.36%, 7.64%] | [2.81%, 8.47%] | 34 | 14 | 3 | 3 | n/a | n/a |

## Notes

- The analytic CR1 Wald interval can dip below 0% for the lowest flip rates (normal
  approximation on a rare 0/1 proportion with few clusters); the whole-cluster bootstrap
  interval stays within [0%, 100%] and is the more trustworthy bound in those cells. Both
  are reported; neither is clamped.
- Flip rates are low across the board, consistent with the fabricated finding rarely moving
  the selected letter under this 2-fake / 50-50 baseline.
- Accuracy deltas are supporting only; the altered answer key is not clinically certified.

## Reproduce

```
PYTHONPATH=code .venv/bin/python \
  data/experiment-C-2026-07-31/final/baseline-2fake-5050/openrouter-results/analyze_flip_rate_openrouter.py
```
