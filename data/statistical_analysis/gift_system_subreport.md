# GIFT System Sub-Report: Accuracy and Performance

## Executive Summary

This sub-report evaluates the GIFT medical question-answering system on the completed `bench_315_v2` benchmark. The analysis uses the final validated database state after all retries were completed.

GIFT completed all planned evaluations successfully:

- Final completed calls: 1,260 / 1,260
- Final API failures: 0
- Final parse failures: 0
- Aggregate strict accuracy: 86.9%
- Best model accuracy: 95.6%
- Second-best model accuracy: 94.3%

The strongest GIFT configurations were Gemini and Qwen 3.7 Max. Their accuracies were statistically indistinguishable in the paired model comparison, forming the leading performance tier within the GIFT system.

## Benchmark Design

The GIFT system was evaluated on 315 Spanish gastroenterology multiple-choice questions. Each question was answered once by each of four model configurations served through GIFT:

- Gemini
- Gemma
- Qwen 3.6
- Qwen 3.7 Max

This produced:

- 315 questions
- 4 GIFT model configurations
- 1,260 final GIFT logical calls

The primary accuracy endpoint was `strict_correct`, a binary measure indicating whether the selected answer matched the benchmark answer under the strict scoring rule.

The performance endpoints were:

- final completion rate
- final parse success
- final latest-attempt latency
- historical retry/recovery behavior

## Methodology

### Accuracy

Accuracy was evaluated using the latest successful result for each question/model pair. Because the same 315 questions were answered by all four GIFT model configurations, model comparisons were treated as paired binary repeated-measures data.

The statistical workflow was:

- Descriptive strict accuracy by model.
- Cochran's Q test for the omnibus question: whether accuracy differs across the four GIFT model configurations.
- Pairwise exact McNemar tests between GIFT model configurations.
- Holm correction for multiple pairwise comparisons within the GIFT model family.

This design treats the question as the independent unit. That is appropriate because each model answered the same questions, and question difficulty is shared across model configurations.

### Latency

Latency was summarized from the latest successful attempt for each completed GIFT logical call. Latency is right-skewed, so medians and upper percentiles are emphasized over means.

Reported latency summaries:

- median
- p90
- p95
- mean
- maximum observed latest-attempt latency

### Reliability

Reliability was analyzed separately from final accuracy. Final accuracy uses only the latest completed result, while reliability uses the full append-only attempt history.

This distinction matters because GIFT achieved complete final coverage after retry/recovery, but the historical attempt log still shows operational friction such as request errors, timeouts, authentication errors, server errors, and parse failures that were later recovered.

## Final Completion and Parse Quality

GIFT reached full final completion:

| Metric | Result |
|---|---:|
| Planned GIFT logical calls | 1,260 |
| Final completed calls | 1,260 |
| Final completion rate | 100.0% |
| Final API failures | 0 |
| Final parse failures | 0 |
| Final scored calls | 1,260 |

Every final GIFT result was available for scoring. Historical parse failures were fully recovered by subsequent attempts, so the final benchmark table is complete.

## Accuracy Results

| GIFT model | Questions | Correct | Strict accuracy |
|---|---:|---:|---:|
| Gemini | 315 | 301 | 95.6% |
| Qwen 3.7 Max | 315 | 297 | 94.3% |
| Qwen 3.6 | 315 | 265 | 84.1% |
| Gemma | 315 | 232 | 73.7% |
| **All GIFT configurations** | **1,260** | **1,095** | **86.9%** |

### Interpretation

The GIFT system showed a clear top-performing tier:

- Gemini: 95.6%
- Qwen 3.7 Max: 94.3%

These two configurations were very close. The paired model comparison did not find a significant difference between them after correction.

The smaller model configurations were lower:

- Qwen 3.6: 84.1%
- Gemma: 73.7%

This means GIFT performance is strongly model-dependent. When paired with the strongest model configurations, GIFT delivered high final strict accuracy on this benchmark.

## Model Comparison Within GIFT

Cochran's Q test found strong evidence that accuracy differed across GIFT model configurations:

| Test | Statistic | df | p-value |
|---|---:|---:|---:|
| Cochran's Q | 117.454 | 3 | 2.73e-25 |

Pairwise exact McNemar tests with Holm correction showed:

| Model comparison | Accuracy A | Accuracy B | Difference | Holm-adjusted p | Interpretation |
|---|---:|---:|---:|---:|---|
| Gemini vs Gemma | 95.6% | 73.7% | 21.9 pp | 1.04e-14 | Significant |
| Gemini vs Qwen 3.6 | 95.6% | 84.1% | 11.4 pp | 8.39e-07 | Significant |
| Gemini vs Qwen 3.7 Max | 95.6% | 94.3% | 1.3 pp | 0.523 | Not significant |
| Gemma vs Qwen 3.6 | 73.7% | 84.1% | 10.5 pp | 1.74e-05 | Significant |
| Gemma vs Qwen 3.7 Max | 73.7% | 94.3% | 20.6 pp | 2.53e-16 | Significant |
| Qwen 3.6 vs Qwen 3.7 Max | 84.1% | 94.3% | 10.2 pp | 5.49e-06 | Significant |

The practical conclusion is straightforward: GIFT performs best with Gemini or Qwen 3.7 Max. Qwen 3.7 Max reached near-Gemini performance, while Qwen 3.6 and Gemma were materially less accurate in this benchmark.

## Model Class Summary

Grouping the GIFT configurations into larger and smaller model classes gives a useful descriptive view:

| GIFT model class | Models | Calls | Correct | Strict accuracy |
|---|---|---:|---:|---:|
| Larger configurations | Gemini, Qwen 3.7 Max | 630 | 598 | 94.9% |
| Smaller configurations | Gemma, Qwen 3.6 | 630 | 497 | 78.9% |

This grouping is descriptive rather than causal, because model size is confounded with architecture and model family. Still, it is operationally useful: the larger GIFT configurations delivered substantially stronger benchmark accuracy.

## Latency Results

Latency below uses the latest successful attempt for each final completed call.

| GIFT model | Calls | Median latency | p90 | p95 | Mean | Max |
|---|---:|---:|---:|---:|---:|---:|
| Gemma | 315 | 14.36s | 25.62s | 30.68s | 17.10s | 73.06s |
| Qwen 3.6 | 315 | 23.66s | 43.71s | 52.31s | 27.48s | 94.67s |
| Gemini | 315 | 25.39s | 45.39s | 48.75s | 28.39s | 109.33s |
| Qwen 3.7 Max | 315 | 27.78s | 43.86s | 58.94s | 31.09s | 112.58s |
| **All GIFT configurations** | **1,260** | **22.73s** | **42.25s** | **49.04s** | **26.01s** | **112.58s** |

### Interpretation

GIFT's final successful responses generally landed in the tens-of-seconds range:

- Fastest median latency: Gemma at 14.36s
- Highest-accuracy tier median latency: Gemini at 25.39s and Qwen 3.7 Max at 27.78s
- Overall GIFT median latency: 22.73s
- Overall p95 latency: 49.04s

The strongest accuracy configurations therefore carried a latency cost, but remained within a consistent operational range for final successful attempts.

## Reliability and Recovery

The final GIFT table is fully complete, but the attempt history shows that retries and recovery were important.

| GIFT model | Logical calls | Total attempts | Mean attempts | Max attempts | Calls needing retry | Final completed |
|---|---:|---:|---:|---:|---:|---:|
| Gemini | 315 | 758 | 2.41 | 4 | 280 | 315 |
| Gemma | 315 | 679 | 2.16 | 6 | 280 | 315 |
| Qwen 3.6 | 315 | 751 | 2.38 | 4 | 281 | 315 |
| Qwen 3.7 Max | 315 | 778 | 2.47 | 5 | 284 | 315 |
| **All GIFT configurations** | **1,260** | **2,966** | **2.35** | **6** | **1,125** | **1,260** |

Historical parse failures occurred during earlier attempts, but every such case was recovered:

| GIFT model | Historical failed parse rows | Unique affected calls | Final recovered |
|---|---:|---:|---:|
| Gemini | 155 | 155 | 155 |
| Gemma | 77 | 77 | 77 |
| Qwen 3.6 | 149 | 149 | 149 |
| Qwen 3.7 Max | 172 | 172 | 172 |
| **Total** | **553** | **553** | **553** |

### Interpretation

GIFT's reliability profile is best described as strong final recoverability with meaningful retry dependence:

- Final success was complete: 1,260 / 1,260.
- All historical parse failures were recovered.
- Most calls required more than one attempt.
- The retry system was essential to reaching the final clean result table.

This is an important operational finding: GIFT can produce a complete, high-quality final benchmark table, but production use should preserve robust retry, timeout handling, and parse validation.

## Overall Assessment

GIFT performed strongly as a medical multiple-choice answering system when paired with its best model configurations.

The headline result is that GIFT reached:

- 100.0% final completion
- 100.0% final parse/scoring availability
- 95.6% strict accuracy with Gemini
- 94.3% strict accuracy with Qwen 3.7 Max
- 94.9% strict accuracy across the larger-model GIFT configurations

The main weakness is operational rather than final-result quality: the attempt history shows substantial retry and parse-recovery activity. That does not affect the final benchmark completeness, but it should shape deployment expectations.

## Practical Recommendations

1. Use Gemini or Qwen 3.7 Max when final answer quality is the priority.
2. Use Gemma when lower latency is more important and reduced accuracy is acceptable.
3. Keep serial or carefully rate-limited execution for GIFT-style runs if parse stability matters.
4. Keep response validation and retry recovery enabled; they are central to the observed 100% final completion.
5. Report final accuracy and operational reliability separately, because GIFT's final results are clean while its attempt history contains recoverable failures.

## Methodological Caveats

- The benchmark contains 315 questions from a specific medical exam domain, so results should not be generalized without additional datasets.
- Each model/question cell uses the final latest successful answer; this is appropriate for final benchmark reporting but does not estimate stochastic model variability.
- Model-class summaries are descriptive. They should not be interpreted as pure causal effects of model size.
- Latency reflects the latest successful attempt, not full wall-clock time including failed attempts, retry delays, or orchestration overhead.
- Reliability metrics use the full append-only history and therefore describe operational recovery behavior, not final answer quality.
