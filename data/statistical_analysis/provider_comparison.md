# Primary Provider Comparison: bench_315_v2

Experiment: `bench_315_v2`  
Database: `runs/medrag_eval.sqlite`  
Primary outcome: latest `strict_correct` score per logical call  
Comparison direction: OpenRouter minus TailScale, within the same model and the same 315 questions

## Data Checks

- The experiment contains four model-level provider comparisons.
- Each comparison has 315 matched question pairs: one latest OpenRouter answer and one latest TailScale answer for the same model and question.
- All latest parsed answers used here have `parse_status = 'ok'`.
- Historical retry rows were not counted directly; the analysis used the latest parsed answer and latest score per `logical_call_id`.
- `strict_correct` was used because it is the benchmark's reported strict accuracy metric.

## Method

For each model, I built a paired 2x2 correctness table:

- Both correct
- OpenRouter only correct (`b`)
- TailScale only correct (`c`)
- Both wrong

The provider comparison uses McNemar's paired binary test. Because discordant counts are small to modest across all four comparisons (`b + c` ranges from 4 to 28), I report exact two-sided McNemar p-values for every model. Holm correction is applied across the four model-level provider comparisons.

The 95% confidence interval is for the paired accuracy difference, OpenRouter minus TailScale. It uses a question-level paired bootstrap, matching the aggregate reproducible analysis script. Values are reported in percentage points.

## Results

| Model | n pairs | OpenRouter accuracy | TailScale accuracy | Both correct | OpenRouter only correct b | TailScale only correct c | Both wrong | Diff OR-TS | 95% CI | Exact McNemar p | Holm p | Holm significant at 0.05 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `google/gemini-3.5-flash` | 315 | 96.19% (303/315) | 95.56% (301/315) | 300 | 3 | 1 | 11 | +0.63 pp | [-0.63, +1.90] pp | 0.6250 | 1.0000 | No |
| `google/gemma-4-26b-a4b-it` | 315 | 73.65% (232/315) | 73.65% (232/315) | 218 | 14 | 14 | 69 | +0.00 pp | [-3.17, +3.17] pp | 1.0000 | 1.0000 | No |
| `qwen/qwen3.6-35b-a3b` | 315 | 87.30% (275/315) | 84.13% (265/315) | 256 | 19 | 9 | 31 | +3.17 pp | [+0.00, +6.67] pp | 0.0872 | 0.3486 | No |
| `qwen/qwen3.7-max` | 315 | 94.60% (298/315) | 94.29% (297/315) | 291 | 7 | 6 | 11 | +0.32 pp | [-1.90, +2.54] pp | 1.0000 | 1.0000 | No |

## Interpretation

No model-level OpenRouter vs TailScale comparison is statistically significant after Holm correction at alpha = 0.05.

The largest observed paired difference is for `qwen/qwen3.6-35b-a3b`: OpenRouter answers 10 more questions correctly than TailScale among the discordant pairs, for a paired accuracy difference of +3.17 percentage points. The exact McNemar p-value is 0.0872 before correction and 0.3486 after Holm correction, so this is not statistically significant in this experiment.

The Gemini and Qwen 3.7 Max comparisons have very few net discordants. Gemma has exactly balanced discordants, so there is no observed paired accuracy difference.

## Limitations

- The independent unit is assumed to be the question. If questions are correlated by source, topic, or exam structure, these p-values may be optimistic.
- This is a single run per provider-model-question cell. The analysis does not estimate model stochasticity or provider retry variability beyond the final latest scored answer.
- Exact McNemar tests condition on the number of discordant pairs and test equality of paired marginal accuracies. They do not estimate causal provider effects outside this benchmark setup.
- Holm correction covers only the four primary model-level provider comparisons requested here.
- Confidence intervals are paired question-bootstrap intervals, not exact unconditional intervals.
