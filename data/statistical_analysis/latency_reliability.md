# Latency and Reliability Analysis: bench_315_v2

## Scope

- Repository: `/Users/ernestsaenz/Programming/gift-testing-api/test-system-1`
- Database: `runs/medrag_eval.sqlite`
- Experiment: `bench_315_v2` (`experiments.id = 1`, created `2026-05-25T12:28:28+00:00`)
- Logical calls: 2,520 = 315 questions x 2 providers x 4 models
- Provider attempts in history: 6,515
- Parsed-answer rows in history: 3,074

Accuracy is intentionally out of scope here. This report describes latency and operational reliability only.

## Methodology

- Final latency uses the latest successful provider attempt per logical call. In this database, that exactly matched the provider attempt referenced by the latest parse row for all 2,520 logical calls.
- Final completion follows the harness rule in `src/medrag_eval/db.py`: the latest parse must be `ok` or `ok_conflict`, and its provider attempt must have no `error_type`.
- Reliability uses all historical attempts and parse rows, including failed API attempts and parse failures that were later recovered.
- Latency is right-skewed, so the primary summaries are median, p90, and p95. Mean and max are included to show tail weight.
- Provider latency comparisons are paired by the same question and model. Inference uses paired log-latency ratios, matching the aggregate reproducible analysis script. Ratios are more interpretable for skewed latency than raw millisecond differences.
- Error messages and raw response bodies were not inspected for this report, to avoid exposing secrets or sensitive text.

## Final Completion

All planned logical calls completed successfully at the final state.

| Metric | Value |
|---|---:|
| Planned logical calls | 2,520 |
| Final completed calls | 2,520 |
| Final completion rate | 100.0% |
| Latest final parse status | 2,520 `ok` |
| Final latency nulls | 0 |

There was one historical `ok_conflict` parse row, but the latest parse for every logical call is `ok`.

## Final Latency By Provider

| Provider | Final calls | Median | p90 | p95 | Mean | Max |
|---|---:|---:|---:|---:|---:|---:|
| OpenRouter | 1,260 | 8.52s | 41.71s | 57.40s | 17.04s | 308.13s |
| TailScale medical RAG | 1,260 | 22.73s | 42.25s | 49.04s | 26.01s | 112.58s |

OpenRouter has the lower overall median, but its upper tail is heavier because of very long Qwen 3.6 and Gemini outliers. TailScale has a higher median but a lower observed max.

## Final Latency By Provider And Model

| Provider | Model | n | Median | p90 | p95 | Mean | Max |
|---|---|---:|---:|---:|---:|---:|---:|
| OpenRouter | google/gemini-3.5-flash | 315 | 4.95s | 7.97s | 9.93s | 6.88s | 240.18s |
| OpenRouter | google/gemma-4-26b-a4b-it | 315 | 1.69s | 3.30s | 4.56s | 2.56s | 61.88s |
| OpenRouter | qwen/qwen3.6-35b-a3b | 315 | 35.07s | 65.17s | 79.83s | 38.44s | 308.13s |
| OpenRouter | qwen/qwen3.7-max | 315 | 16.50s | 33.73s | 44.79s | 20.25s | 105.22s |
| TailScale medical RAG | google/gemini-3.5-flash | 315 | 25.39s | 45.39s | 48.75s | 28.39s | 109.33s |
| TailScale medical RAG | google/gemma-4-26b-a4b-it | 315 | 14.36s | 25.62s | 30.68s | 17.10s | 73.06s |
| TailScale medical RAG | qwen/qwen3.6-35b-a3b | 315 | 23.66s | 43.71s | 52.31s | 27.48s | 94.67s |
| TailScale medical RAG | qwen/qwen3.7-max | 315 | 27.78s | 43.86s | 58.94s | 31.09s | 112.58s |

## Paired Provider Latency Comparisons

Ratios are TailScale over OpenRouter for the same question and model. Values above 1 mean TailScale was slower.

| Model | Pairs | OpenRouter median | TailScale median | Median ratio | Geomean ratio, 95% CI | TailScale slower pairs | Paired log-latency p |
|---|---:|---:|---:|---:|---:|---:|---:|
| google/gemini-3.5-flash | 315 | 4.95s | 25.39s | 4.98x | 4.97x [4.69, 5.26] | 98.7% | 1.76e-163 |
| google/gemma-4-26b-a4b-it | 315 | 1.69s | 14.36s | 8.90x | 8.55x [8.00, 9.14] | 99.0% | 5.28e-180 |
| qwen/qwen3.6-35b-a3b | 315 | 35.07s | 23.66s | 0.70x | 0.78x [0.73, 0.84] | 29.8% | 6.18e-11 |
| qwen/qwen3.7-max | 315 | 16.50s | 27.78s | 1.78x | 1.71x [1.63, 1.78] | 94.3% | 2.38e-73 |

TailScale was slower for Gemini, Gemma, and Qwen 3.7 Max. TailScale was faster for Qwen 3.6, with a median paired ratio of 0.70x.

## Attempt Reliability

| Metric | Value |
|---|---:|
| Total provider attempts | 6,515 |
| Attempts per logical call, mean | 2.59 |
| Attempts per logical call, median | 3 |
| Attempts per logical call, p90 | 3 |
| Attempts per logical call, p95 | 3 |
| Max attempts for one logical call | 6 |
| Calls needing retry or rerun | 2,247 / 2,520 (89.2%) |
| Initial API failures | 2,246 / 2,520 (89.1%) |
| Initial parse failures | 1 / 2,520 (0.04%) |
| Initial successes | 273 / 2,520 (10.8%) |
| Recovery after initial failure | 2,247 / 2,247 (100.0%) |

Attempt-count distribution:

| Attempts for logical call | Logical calls |
|---:|---:|
| 1 | 273 |
| 2 | 564 |
| 3 | 1,636 |
| 4 | 30 |
| 5 | 16 |
| 6 | 1 |

The final successful attempt index has the same distribution, meaning every logical call's latest stored attempt is also its final successful attempt.

## Attempt Status Counts

| Attempt status | Attempts |
|---|---:|
| no provider error | 3,074 |
| request_error | 3,371 |
| timeout | 44 |
| auth_error | 15 |
| server_error | 10 |
| malformed_json | 1 |

Initial API failures were almost entirely `request_error`: 2,241 `request_error`, 4 `server_error`, and 1 `timeout`.

## Reliability By Provider And Model

| Provider | Model | Calls | Attempts | Mean attempts | Calls needing retry | Initial API failures | Parse-failure calls | request_error | timeout | auth_error | server_error | malformed_json | Final completed |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| OpenRouter | google/gemini-3.5-flash | 315 | 878 | 2.79 | 280 | 280 | 0 | 560 | 3 | 0 | 0 | 0 | 315 |
| OpenRouter | google/gemma-4-26b-a4b-it | 315 | 879 | 2.79 | 280 | 280 | 0 | 561 | 3 | 0 | 0 | 0 | 315 |
| OpenRouter | qwen/qwen3.6-35b-a3b | 315 | 903 | 2.87 | 281 | 281 | 0 | 566 | 21 | 0 | 0 | 1 | 315 |
| OpenRouter | qwen/qwen3.7-max | 315 | 889 | 2.82 | 281 | 281 | 0 | 564 | 10 | 0 | 0 | 0 | 315 |
| TailScale medical RAG | google/gemini-3.5-flash | 315 | 758 | 2.41 | 280 | 280 | 155 | 280 | 1 | 5 | 1 | 0 | 315 |
| TailScale medical RAG | google/gemma-4-26b-a4b-it | 315 | 679 | 2.16 | 280 | 280 | 77 | 280 | 4 | 3 | 0 | 0 | 315 |
| TailScale medical RAG | qwen/qwen3.6-35b-a3b | 315 | 751 | 2.38 | 281 | 281 | 149 | 280 | 1 | 3 | 3 | 0 | 315 |
| TailScale medical RAG | qwen/qwen3.7-max | 315 | 778 | 2.47 | 284 | 283 | 172 | 280 | 1 | 4 | 6 | 0 | 315 |

OpenRouter required more attempts per logical call on average, driven by repeated `request_error` attempts. TailScale had fewer provider attempts overall, but it produced 553 parse failures that required recovery.

## Parse Reliability

All historical parse rows:

| Parse status | Parse rows |
|---|---:|
| ok | 2,520 |
| failed_no_answer_found | 553 |
| ok_conflict | 1 |

`failed_no_answer_found` occurred only for TailScale medical RAG:

| Model | Failed parse rows | Unique logical calls | Final recovered |
|---|---:|---:|---:|
| google/gemini-3.5-flash | 155 | 155 | 155 |
| google/gemma-4-26b-a4b-it | 77 | 77 | 77 |
| qwen/qwen3.6-35b-a3b | 149 | 149 | 149 |
| qwen/qwen3.7-max | 172 | 172 | 172 |
| Total | 553 | 553 | 553 |

Every call with a historical parse failure was eventually recovered to a final `ok` parse.

## Caveats

- Final latency is not full user-perceived elapsed time for retry-heavy calls. It excludes earlier failed API attempts, parse-failed attempts, retry sleeps, and any orchestration delay. Many `request_error` rows have null latency, so reconstructing a complete end-to-end wall-clock latency from this database would be unreliable.
- The very high initial API failure rate means reliability should not be judged from final completion alone. Final completion was perfect, but only after substantial retry/recovery behavior.
- The latency p-values are secondary to the effect sizes because latency is highly skewed. The paired ratio estimates and medians are the main interpretation targets.
- Error counts are based on persisted `error_type` values. This report did not classify raw `error_message` text.
- The database was read as the current SQLite snapshot. If the benchmark was still being modified elsewhere, later reads could differ.
