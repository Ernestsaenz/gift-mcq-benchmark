# Run status — corrected v3 record

**Snapshot date:** 2026-07-31  
**Purpose:** reconcile what was planned, created, attempted, scored, analysed, and not run.  
**Authority:** `../experiment.sqlite`, joined at logical-call and score grain.

## Dataset construction

`../flatten.py` reads `../balanced-clinical-questionnaire-500-no-image.xlsx` and produces the two
import workbooks without modifying the source.

| dataset | items | derivation |
|---|---:|---|
| `balanced_a_310726` | 474 | 500 source − 17 three-option − 9 source-level defects |
| `balanced_b_310726` | 423 | A − 30 aggregator-broken − 5 existing-NOTA distractors − 16 swap-specific QA defects |

Condition B replaces only the keyed option's text with
`Ninguna de las respuestas anteriores es correcta.`; the keyed letter is unchanged. All reported
runs use four models, run index 1, temperature 0, and prompt `mcq_es_v4`.

## Exact execution status

| experiment | planned | logical calls created | distinct calls attempted | scores | provider attempts | status |
|---|---:|---:|---:|---:|---:|---|
| `expA_or_310726` | 1,896 | 1,896 | 1,896 | **1,895** | 1,930 | one unrecovered cell |
| `expB_or_310726` | 1,692 | 1,692 | 1,692 | **1,692** | 1,745 | complete |
| `expA_gift_310726` | 1,896 | 1,566 | 1,565 | **1,384** | 1,582 | stopped by operator |
| `expB_gift_310726` | 1,692 | 0 | 0 | **0** | 0 | never started |

The previous phrase “GIFT 83% complete” conflated two denominators. Logical-call creation reached
**1,566/1,896 = 82.59%**; score completion was **1,384/1,896 = 73.00%**. One created glm call was
never started.

### GIFT A by model

| model | logical calls | attempted | scored | attempted, unscored | never attempted |
|---|---:|---:|---:|---:|---:|
| gemini-3.6-flash | 392 | 392 | 355 | 37 | 82 |
| gemma-4-26b-a4b-it | 391 | 391 | 355 | 36 | 83 |
| qwen3.6-35b-a3b | 391 | 391 | 351 | 40 | 83 |
| glm-5.2 | 392 | 391 | 323 | 68 | 83 |

Exactly **319/474 items (67.30%)** have GIFT scores from all four models before analysis
exclusions.

### GIFT attempt reconciliation

Of 1,582 GIFT provider attempts, **196 (12.389%)** returned non-200 status codes. Seventeen HTTP
401 attempts were recovered on retry. On each attempted logical call's latest attempt, **179/1,565
(11.438%)** remained non-200: 96 HTTP 429 and 83 HTTP 500. Two additional logical calls received
HTTP 200 but failed answer parsing. These are run-state counts, not model-answer error rates.

## Known unrecovered OpenRouter cell

`b320 × z-ai/glm-5.2`, condition A, has no score after ten HTTP-200 attempts: nine ended
`finish_reason=length` at 65,536 completion tokens and one ended `finish_reason=error` at 44,624
tokens. It is absent from the paired A/B export rather than counted wrong.

## GIFT coverage is not random

The stopped runner covered a sequential prefix with gaps. On the raw A population, OpenRouter
accuracy was **91.07%** on the 319 all-four-model GIFT-covered items and **82.88%** on the 155
other items. The observed cross-arm subset is therefore easier than the unobserved remainder.

The cleaned cross-arm analysis uses 306 items, 1,224 cells, and 178 clusters completed by every
GIFT model. This makes the observed-subset pairing valid, but it does not identify the missing-item
GIFT effect. GIFT B has no calls, so no retrieval-arm A/B contrast exists.

## Canonical v3 analytical exports

v3 preserves the v2 analytical population and fixes two reproducibility defects: the builder now
joins the exact scored parse through `scores.parsed_answer_id`, and it regenerates complete
provenance metadata instead of stripping manual fields.

| set | cells | items | clusters |
|---|---:|---:|---:|
| OpenRouter A/B, all paired | 1,691 | 423 | 281 |
| OpenRouter A/B, reported | **1,271** | **318** | **201** |
| GIFT/OpenRouter A, reported | **1,224** | **306** | **178** |

The requested A/B analysis removes 19 declared defect items present in the paired universe and 91
key-`a` items, with five overlapping. The globally declared defect list has 22 IDs because three
out-of-domain items were already absent from B. The three medical-key exclusions (`b178`, `b197`,
`b496`) are user-adjudicated; their detailed clinical citations were not preserved.

## Measurement caveats

- **Completion tokens:** the emitted JSON echoes the selected option text; A/B answer-text length
  differs by construction. Raw completion tokens are not a clean deliberation measure.
- **Latency/throughput:** GIFT was serialised and OpenRouter used different infrastructure and
  concurrency. The observed median paired duration difference is not an intrinsic retrieval tax.
- **Backend routing:** OpenRouter providers were not pinned across A and B. Same-backend sensitivity
  remains negative but does not recreate random provider assignment.
- **Runs:** one run per cell; item-level stability is not estimable.
- **Bootstrap:** repeated clinical-cluster draws must retain draw multiplicity and must not be
  regrouped only by question ID.

Consequently, the final report does not claim an intrinsic 15.6× latency ratio, deliberation from
completion tokens, or projected minutes/failures per added correct answer.

## Reproduction

From the repository root:

```bash
uv run python data/experiment-31-07-26/analysis/build_analysis_data.py
uv run python data/experiment-31-07-26/analysis/final_analysis.py
uv run python data/experiment-31-07-26/analysis/build_report_artifact.py
```

`dataset_meta.json` pins the source inputs, database, builder, and core exports with SHA-256.
`final_analysis_results.json` is the only compact numerical result bundle used by the final report;
older exploratory outputs in this folder may contain superseded v1 counts.
