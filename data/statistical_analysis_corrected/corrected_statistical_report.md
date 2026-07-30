# Tier 1 — Corrected Statistics (fixed parser)

Re-derived from the SAME raw responses in `data/medrag_eval.sqlite`
(opened read-only) using the corrected `medrag_eval.parser`.
See `CORRECTION_NOTE.md` for the defects and their provenance.

## Extraction changes vs. the published run

- Answers whose score changed: **2**
- Rows that merely moved to structured parsing (answer unchanged): **313**

| provider | model | question | gold | published | corrected | strict |
|---|---|---|---|---|---|---|
| tailscale_medical_rag | Gemini | g134 | d | `a` | `d` | 0 → 1 |
| tailscale_medical_rag | Gemini | g261 | c | `a` | `c` | 0 → 1 |

## GIFT / TailScale

| model | published | corrected | accuracy |
|---|---|---|---|
| Gemini | 301/315 | 303/315 **(+2)** | 96.19% |
| Gemma | 232/315 | 232/315 | 73.65% |
| Qwen 3.6 | 265/315 | 265/315 | 84.13% |
| Qwen 3.7 Max | 297/315 | 297/315 | 94.29% |
| **Aggregate** | **1095/1260** | **1097/1260** | **87.0635%** |

Cochran's Q = 124.042, df = 3, p = 1.040e-26

| model A | model B | b | c | raw p | Holm p | reject@0.05 |
|---|---|---|---|---|---|---|
| Gemini | Gemma | 71 | 0 | 0.000000 | 0.000000 | True |
| Gemini | Qwen 3.6 | 43 | 5 | 0.000000 | 0.000000 | True |
| Gemini | Qwen 3.7 Max | 13 | 7 | 0.263176 | 0.263176 | False |
| Gemma | Qwen 3.6 | 11 | 44 | 0.000009 | 0.000017 | True |
| Gemma | Qwen 3.7 Max | 3 | 68 | 0.000000 | 0.000000 | True |
| Qwen 3.6 | Qwen 3.7 Max | 7 | 39 | 0.000002 | 0.000005 | True |

## OpenRouter (control)

| model | published | corrected | accuracy |
|---|---|---|---|
| Gemini | 303/315 | 303/315 | 96.19% |
| Gemma | 232/315 | 232/315 | 73.65% |
| Qwen 3.6 | 275/315 | 275/315 | 87.30% |
| Qwen 3.7 Max | 298/315 | 298/315 | 94.60% |
| **Aggregate** | **1108/1260** | **1108/1260** | **87.9365%** |

Cochran's Q = 121.000, df = 3, p = 4.700e-26

| model A | model B | b | c | raw p | Holm p | reject@0.05 |
|---|---|---|---|---|---|---|
| Gemini | Gemma | 75 | 4 | 0.000000 | 0.000000 | True |
| Gemini | Qwen 3.6 | 32 | 4 | 0.000002 | 0.000006 | True |
| Gemini | Qwen 3.7 Max | 12 | 7 | 0.359283 | 0.359283 | False |
| Gemma | Qwen 3.6 | 11 | 54 | 0.000000 | 0.000000 | True |
| Gemma | Qwen 3.7 Max | 5 | 71 | 0.000000 | 0.000000 | True |
| Qwen 3.6 | Qwen 3.7 Max | 7 | 30 | 0.000191 | 0.000382 | True |

## Cross-arm: GIFT / TailScale vs OpenRouter (paired by question)

Supersedes `data/statistical_analysis/provider_mcnemar.csv`, which was
computed from the pre-fix scores. Holm is across the four model comparisons.

| model | OpenRouter | TailScale | diff (OR−TS) | b | c | raw p | Holm p |
|---|---|---|---|---|---|---|---|
| Gemini | 96.19% | 96.19% | +0.00 pp | 1 | 1 | 1.000000 | 1.000000 |
| Gemma | 73.65% | 73.65% | +0.00 pp | 14 | 14 | 1.000000 | 1.000000 |
| Qwen 3.6 | 87.30% | 84.13% | +3.17 pp | 19 | 9 | 0.087159 | 0.348634 |
| Qwen 3.7 Max | 94.60% | 94.29% | +0.32 pp | 7 | 6 | 1.000000 | 1.000000 |

No model shows a significant provider effect after correction.

