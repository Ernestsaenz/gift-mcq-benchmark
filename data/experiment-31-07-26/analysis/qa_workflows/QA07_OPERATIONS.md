# QA07 — operational status, latency, tokens, throughput, and cost claims

**Audit date:** 2026-07-31 (Europe/Madrid)  
**Mode:** read-only inspection of `experiment.sqlite`, the four run logs, launch scripts,
provider/runner code, the v3 exports, and the report. No canonical input, export, script, result,
or report was edited. This QA file is the only artifact created by QA07.  
**Canonical populations:** v3 lineage with the unchanged v2 analytical populations:
OpenRouter A/B = **318 items / 1,271 paired cells / 201 clusters**; condition-A cross-arm =
**306 items / 1,224 cells / 178 clusters**.

## Verdict: FAIL for the original operational claims; PASS for omitting them from the current v3 report

The database supports exact run accounting and configuration-specific descriptive timings. It does
**not** support an intrinsic `15.6×` latency penalty, a causal `12 s retrieval tax`, or `20 minutes / 8
failures per additional correct answer`. Those claims combine different concurrency, separate time
windows and providers, a heuristic OpenRouter “busy-time” denominator, v1 accuracy counts, and a
projection of failures from unscored calls onto the selected scored subset.

The current v3 `REPORT.md` (SHA-256
`164cb1698599f770903e8a5470734bd30756e7b08a965281ba03b6d4335a4218` at audit time) correctly
excludes the intrinsic-latency and minutes/failures claims. Its statement that 196/1,582 = 12.39%
is an **attempt-row** non-2xx rate is correct, but a complete operational ledger should additionally
show the 17 recovered 401 rows, 179 latest 429/500 outcomes, two HTTP-200 parse failures, and one
logical call that never reached the provider.

Database integrity passed: `PRAGMA integrity_check` returned `ok` and
`PRAGMA foreign_key_check` returned no rows.

## Claim-by-claim disposition

| claim | verdict | exact audit result |
|---|---|---|
| GIFT A was “83% complete” | **FAIL if “complete” means scored** | The runner created 1,566/1,896 logical rows (**82.59%**) and started 1,565/1,896 provider calls (**82.54%**), but only 1,384/1,896 were scored (**73.00%**). “Reached about 83% of the plan” is safe; “83% complete” is not. |
| GIFT had a 12.4% attempt-failure rate | **PASS, narrowly defined** | 196/1,582 stored provider-attempt rows had `error_type IS NOT NULL` and non-2xx status (**12.389%**). Seventeen were intermediate 401s recovered immediately to 200. The latest-attempt API-error rate was 179/1,565 provider-started calls (**11.438%**). |
| GIFT had 179 transient failed attempts at stop | **PARTIAL / FAIL as worded** | There were **179 provider-started logical calls whose latest attempt was 429 or 500**, not 179 total failed attempt rows. They were eligible for a later outer pass, but recovery was not observed and is not guaranteed. |
| GIFT “must run serialised” | **FAIL as a general claim** | `run_gift.sh` configured `--tailscale-concurrency 1`; OpenRouter used the CLI default of 18. The database contains no controlled concurrency comparison. The evidence supports “this launch was serialised,” not “GIFT intrinsically must be serialised.” |
| GIFT is intrinsically 15.6× slower / 15.6× more wall-clock per cell | **FAIL** | The 15.643 ratio is reproducible only as `(31,584/1,386) / (2,762/1,896)`. The 2,762-second OpenRouter denominator is a >5-minute-gap “burst” heuristic computed from completion timestamps; singleton retry bursts contribute zero time, and the denominators count HTTP-200 calls rather than scores. Depending on defensible log boundaries, the configuration-specific ratio ranges from 3.12× to 17.67×. It is not intrinsic latency. |
| GIFT charges a ~12 s retrieval tax | **FAIL causally; PASS as a descriptive paired duration difference** | On the v3/v2 cross-arm population, median `GIFT latency_ms − OpenRouter latency_ms` is **11.9255 s**. Model medians range from **4.6435 to 13.4410 s**. The field is client-observed end-to-end call duration across separately run provider paths, not an isolated retrieval component. |
| A/B serving throughput changed | **PASS only as “implied completion-token rate changed”** | Median paired `(completion_tokens/s)_B / (completion_tokens/s)_A` is 1.068 gemini, 0.590 gemma, 0.810 qwen, and 1.010 glm on v3/v2. Because `completion_tokens` include reasoning and answer echo and routing/time changed, this is not a clean decoder-throughput or effort measure. |
| Throughput accounts for 128% of gemma's latency increase | **FAIL** | Repeating the exploratory log decomposition on v3 gives **134.5%**, not 128%. More importantly, it is an algebraic decomposition using a contaminated token-rate proxy, not causal attribution. Medians of the component logs are not additive either. |
| Gemma used about 12% fewer B completion tokens, hence less effort | **FAIL** | The v3 median paired B/A completion-token ratio is **0.881** (about −11.9%); sum tokens fall 13.52%. Gemma reports exactly zero reasoning tokens in all 636 v3 paired responses, while the required echoed output becomes shorter. The raw token decline cannot measure deliberation. |
| Pooled gain costs 20 minutes and 8 failed attempts per added correct | **FAIL** | The published values use the superseded v1 1,244-cell / +22-correct population plus the invalid busy-time allocation. Plugging v3's 1,224 cells / +23 into the same method gives **18.92 min and 7.53 raw error rows**, proving version dependence without repairing the method. The directly summed paired call-duration difference is 599.32 s (9.99 min) per net correct, but that too is not actual cross-provider wall-clock cost. |
| GIFT is “dominated outright” by direct Gemini | **FAIL as a general/product claim; descriptive ordering only** | On the selected 306-item overlap, OpenRouter Gemini scored 301/306 with median duration 3.4465 s; GIFT Gemini scored 298/306 with median 15.703 s. OpenRouter Gemini's point accuracy also exceeds the other three GIFT model configurations. The same-model accuracy interval includes zero, coverage is selected, timing is configuration-specific, and GIFT monetary cost is absent. |
| OpenRouter A has one unrecovered cell caused by five capped runaways | **PASS for the missing cell; FAIL for “five”** | The missing cell is `b320 × z-ai/glm-5.2`. It has **10** HTTP-200 attempts: nine `finish_reason=length` at 65,536 completion tokens and one `finish_reason=error` at 44,624; all ten parses failed. |

## 1. Exact run reconciliation

Definitions used throughout:

- **planned**: dataset rows selected by the experiment config × the four-model launch roster × one
  run. For the main experiments this is 474 or 423 per model. The empty GIFT-B roster is recovered
  from `run_gift.sh`, because an experiment with zero logical rows cannot encode intended models in
  SQLite.
- **logical created**: rows in `logical_calls`.
- **distinct attempted**: distinct logical calls with at least one `provider_attempts` row.
- **scored**: distinct logical calls with a `scores` row.
- **provider attempts**: all physical `provider_attempts` rows, including retries.

### Main experiments, per model

| experiment | model | planned | logical created | distinct attempted | scored | provider attempts |
|---|---|---:|---:|---:|---:|---:|
| OpenRouter A | gemini | 474 | 474 | 474 | 474 | 474 |
| OpenRouter A | gemma | 474 | 474 | 474 | 474 | 474 |
| OpenRouter A | qwen | 474 | 474 | 474 | 474 | 478 |
| OpenRouter A | glm | 474 | 474 | 474 | **473** | **504** |
| **OpenRouter A total** | | **1,896** | **1,896** | **1,896** | **1,895** | **1,930** |
| OpenRouter B | gemini | 423 | 423 | 423 | 423 | 423 |
| OpenRouter B | gemma | 423 | 423 | 423 | 423 | 423 |
| OpenRouter B | qwen | 423 | 423 | 423 | 423 | 424 |
| OpenRouter B | glm | 423 | 423 | 423 | 423 | 475 |
| **OpenRouter B total** | | **1,692** | **1,692** | **1,692** | **1,692** | **1,745** |
| GIFT A | gemini | 474 | 392 | 392 | 355 | 397 |
| GIFT A | gemma | 474 | 391 | 391 | 355 | 395 |
| GIFT A | qwen | 474 | 391 | 391 | 351 | 397 |
| GIFT A | glm | 474 | 392 | **391** | **323** | 393 |
| **GIFT A total** | | **1,896** | **1,566** | **1,565** | **1,384** | **1,582** |
| GIFT B | gemini | 423 | 0 | 0 | 0 | 0 |
| GIFT B | gemma | 423 | 0 | 0 | 0 | 0 |
| GIFT B | qwen | 423 | 0 | 0 | 0 | 0 |
| GIFT B | glm | 423 | 0 | 0 | 0 | 0 |
| **GIFT B total** | | **1,692** | **0** | **0** | **0** | **0** |

Model labels above map to `google/gemini-3.6-flash`, `google/gemma-4-26b-a4b-it`,
`qwen/qwen3.6-35b-a3b`, and `z-ai/glm-5.2`.

### Smoke run

`smoke_gift_310726` planned two questions × four models = eight cells. It created seven logical
rows, started six, scored six, and stored six attempts. Gemma's second cell was never created;
qwen's second logical row (`b2`) was created but never reached the provider. Smoke rows are not in
any reported analysis.

### Complete GIFT-A disposition by model

This partition sums exactly to 474 planned cells for each model and corrects the stale
“attempted-unfinished / never attempted” wording in `RUN_STATUS.md`.

| model | scored | latest 429/500 | HTTP-200 parse failure | logical created, no provider attempt | never created | total |
|---|---:|---:|---:|---:|---:|---:|
| gemini | 355 | 37 | 0 | 0 | 82 | 474 |
| gemma | 355 | 36 | 0 | 0 | 83 | 474 |
| qwen | 351 | 40 | 0 | 0 | 83 | 474 |
| glm | 323 | 66 | 2 | **1** | 82 | 474 |
| **total** | **1,384** | **179** | **2** | **1** | **330** | **1,896** |

The unstarted GIFT-A logical row is `b417 × glm`, created at
`2026-07-31T08:26:58+00:00`. Therefore glm has 68 genuinely attempted-but-unscored calls and 83
cells that never reached the provider; the old 69/82 split uses logical creation rather than
provider initiation.

## 2. GIFT status codes, error types, and retries

### All stored provider-attempt rows

| model | all attempts | HTTP 200 | HTTP 401 `auth_error` | HTTP 429 `rate_limited` | HTTP 500 `server_error` | latest API-error calls | scored |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemini | 397 | 355 | 5 | 24 | 13 | 37 | 355 |
| gemma | 395 | 355 | 4 | 24 | 12 | 36 | 355 |
| qwen | 397 | 351 | 6 | 24 | 16 | 40 | 351 |
| glm | 393 | 325 | 2 | 24 | 42 | 66 | 323 |
| **total** | **1,582** | **1,386** | **17** | **96** | **83** | **179** | **1,384** |

All 17 401 responses were the first physical attempt for a logical call and were followed inside
the same adapter call by HTTP 200; the per-model recovered-retry counts are 5, 4, 6, and 2. No
logical call has more than two GIFT attempt rows. Thus:

- raw non-2xx attempt-row rate: `196 / 1,582 = 12.389%`;
- latest API-error outcomes among calls that reached the provider:
  `179 / 1,565 = 11.438%`;
- unscored outcomes after reaching the provider, including two parse failures:
  `181 / 1,565 = 11.565%`;
- scored share of the full plan: `1,384 / 1,896 = 72.996%`.

The 429/500 responses were not retried inside the GIFT adapter. A later outer convergence pass
would have selected those calls again, but the operator stopped during pass 1. It is safe to call
them **pending retry at stop**, not permanently failed and not proven recoverable.

### Log reconciliation

- `gift_run.log` starts at `Fri Jul 31 01:40:19 CEST` and its final progress line is
  `[08:26:58]` UTC, i.e. 10:26:58 CEST: **8 h 46 min 39 s** launch-to-last-progress.
- The database's first and last stored GIFT attempt timestamps span **31,584 s**; summed recorded
  attempt duration is **31,594.746 s**. Their near equality is consistent with the configured
  concurrency of one.
- The log was piped through `tail -25`, so it contains only positions 1,541–1,565 plus the start
  lines. It has no normal completion trailer. SQLite, not the truncated log, is authoritative for
  the full error ledger.
- The final visible score is gemini `b417`; the runner then created glm `b417` but no attempt row
  was stored before stopping.

## 3. OpenRouter retries and the missing A cell

OpenRouter recorded no provider-level `error_type`: all 3,675 A/B attempt rows are HTTP 200.
That does **not** mean every attempt completed analytically. OpenRouter A contains 35
`failed_no_answer_found` parses and 1,895 successful parses; B contains 53 failed parses and 1,692
successful parses. Resume passes recovered every B call and every A call except one.

For `expA_or_310726 / b320 / z-ai/glm-5.2`:

- 10 stored provider attempts, all HTTP 200;
- nine `finish_reason=length` at exactly 65,536 completion tokens;
- one `finish_reason=error` at 44,624 completion tokens;
- 634,448 completion tokens and 8,626.014 seconds of summed call duration across the ten attempts;
- ten `failed_no_answer_found` parses and zero scores.

`openrouter_run.log` shows attempts 1–7 before ending at a pass-8 header;
`retry_a_or.log` records attempts 8–10. Therefore the historical “five consecutive runaways” and
“abandoned after eight passes” descriptions are stale. The correct concise wording is:

> OpenRouter A scored 1,895/1,896 planned cells. The sole missing cell, `b320 × glm`, remained
> unparseable after ten HTTP-200 attempts; nine hit the 65,536-token length cap.

## 4. Observed serialized wall-clock versus intrinsic latency

### What is directly observed

The GIFT launch used concurrency 1. From the shell start line to the last progress line it produced
1,384 scores in 31,599 seconds: **157.68 scored cells/hour**, or **22.83 observed run seconds per
score**. This includes the time consumed by the errors encountered while advancing through the
sequential prefix. It is a valid description of this launch configuration.

It is not an intrinsic per-call latency:

- OpenRouter used concurrency 18 and GIFT used concurrency 1.
- The arms traversed different provider infrastructure and were not simultaneous paired calls.
- retry sessions, idle gaps, and the pathological OpenRouter `b320` calls make the chosen run
  boundary consequential.
- OpenRouter completion timestamps do not encode individual request start times; a burst's first
  completion minus last completion is not its true active wall-clock.

### Why 15.6× fails

The exploratory calculation is exactly:

```text
GIFT: 31,584 s “busy” / 1,386 HTTP-200 logical calls = 22.7879 s/call
OR-A:  2,762 s “busy” / 1,896 HTTP-200 logical calls =  1.4568 s/call
ratio = 15.6429×
```

The OpenRouter “busy” value groups completion timestamps separated by no more than five minutes.
A singleton retry burst has `last_timestamp − first_timestamp = 0`, even when that one request
took 10–30 minutes. The denominators also count the two GIFT parse failures and the unscored
OpenRouter `b320` call as completed. Therefore the calculation is not a valid wall-clock-per-score
metric.

Reasonable log boundaries show its instability:

| OpenRouter A boundary | OR seconds per score | GIFT/OR ratio using GIFT's 22.83 s/score |
|---|---:|---:|
| initial continuous pass: 2,422 s / 1,874 scores | 1.292 | 17.67× |
| launch through the 1,895th and last recovered score: 4,123 s / 1,895 | 2.176 | 10.49× |
| launch through the final retry stop: 13,882 s / 1,895 | 7.326 | 3.12× |

These are all configuration-specific operational summaries, not intrinsic provider ratios. The
study did not run equal-concurrency, provider-pinned, contemporaneous timing trials.

## 5. Paired latency and completion-token ledger on v3/v2

The v3 builder follows the scored attempt exactly:
`scores.parsed_answer_id → parsed_answers.id → provider_attempts.id`. All 1,224 cross-arm rows have
non-null paired `latency_ms`, prompt-token, completion-token, and total-token values.

### Condition A, GIFT versus OpenRouter

`latency_ms` is the harness's end-to-end client duration around `adapter.chat_completion`. It is
comparable as a recorded field, but its provider difference bundles retrieval, prompt/prefill,
queueing, network, backend, generation, and run-time load.

| model | n | median latency GIFT / OR (s) | median paired difference (s) | median paired latency ratio G/O | median completion tokens GIFT / OR | median paired completion-rate ratio G/O* |
|---|---:|---:|---:|---:|---:|---:|
| gemini | 306 | 15.703 / 3.4465 | **11.9675** | 4.517 | 534.5 / 507.5 | 0.233 |
| gemma | 306 | 14.6845 / 1.119 | **13.4410** | 13.024 | 50 / 50 | 0.078 |
| qwen | 306 | 23.812 / 20.0095 | **4.6435** | 1.241 | 1,334.5 / 1,944 | 0.534 |
| glm | 306 | 20.7155 / 8.3885 | **12.6320** | 2.652 | 372 / 438 | 0.341 |
| **pooled** | **1,224** | **17.6645 / 4.8435** | **11.9255** | **3.713** | **461.5 / 469.5** | **0.266** |

\* Per-cell `(completion_tokens / latency_seconds)_GIFT / (...)_OpenRouter`, then median. This is
an **implied completion-token rate**, not a decoder-only throughput measurement.

For the 1,224 successful pairs, summed recorded call durations are 25,705.740 seconds for GIFT and
11,921.352 seconds for OpenRouter, a difference of 13,784.388 seconds. Those sums are serial
request-time totals; they are not the actual elapsed OpenRouter wall-clock because its calls
overlapped.

Prompt-token medians are **5,112 GIFT versus 917 OpenRouter**. The median paired prompt-token ratio
is 5.095. This is expected to include GIFT's server-side prompt/retrieved context, but it prevents
the latency difference from isolating retrieval time: longer prefill and the provider path change
at the same time.

### OpenRouter condition A versus B

The v3/v2 A/B population shows that recorded latency and the constructed completion-token rate
move differently by model:

| model | n | median latency A / B (s) | median paired B/A latency | median completion A / B | median paired `(completion/s)` B/A |
|---|---:|---:|---:|---:|---:|
| gemini | 318 | 3.5515 / 4.9555 | 1.377 | 522.5 / 812.5 | 1.068 |
| gemma | 318 | 1.1755 / 1.7890 | 1.481 | 52 / 46 | 0.590 |
| qwen | 318 | 19.9405 / 29.4665 | 1.357 | 1,990 / 2,185.5 | 0.810 |
| glm | 317 | 9.348 / 13.643 | 1.498 | 465 / 736 | 1.010 |

This is useful evidence **against** treating latency as an effort proxy. It does not identify a
serving-throughput mechanism: A and B ran at different times; OpenRouter routing was unpinned; and
the A/B backend total-variation distances are 0.000 gemini, 0.814 gemma, 0.236 qwen, and 0.303 glm.

The exploratory log identity

```text
log(latency_B / latency_A)
  = log(completion_tokens_B / completion_tokens_A)
  + log(implied_rate_A / implied_rate_B)
```

is arithmetic. On v3, the ratio of the median “rate term” to median log-latency change is 134.5%
for gemma. That number cannot be interpreted as the percentage of latency causally attributable to
throughput: the token count is contaminated, the rate includes every pre-generation stage, the
provider routes changed, and medians of components do not generally sum to the median total.

## 6. Completion tokens, reasoning tokens, and answer echo

`paired_clean.json` fields `A_tokens`/`B_tokens` and `cross_arm_A.json` fields
`gift_tokens`/`or_tokens` exactly equal the scored attempt's `provider_attempts.completion_tokens`.
They are not prompt tokens and not pure reasoning tokens.

The output contract requires the model to emit JSON containing `selected_option_text`. Therefore
every completion contains an answer echo. On the 318 v3 A/B items:

- condition-A keyed option text: mean **74.085** characters, median **65**;
- condition-B keyed text: exactly **49** characters in every item;
- median visible response length is about 143–147 characters in A versus 132 in B, depending on
  model.

OpenRouter exposes `usage.completion_tokens_details.reasoning_tokens`, but it does not make a
general effort analysis clean:

| model | v3 A/B responses with field | median reasoning A / B | notable limitation |
|---|---:|---:|---|
| gemini | 636/636 | 470.5 / 767.5 | backend stable, but separate run time/load remains |
| gemma | 636/636 | 0 / 0 | no measured reasoning signal at all |
| qwen | 636/636 | 1,890.5 / 2,112 | reasoning exceeds `completion_tokens` in 139/636 cells |
| glm | 634/634 | 418 / 688 | reasoning exceeds completion in one cell |

GIFT exposes no reasoning-token field in any of the 1,224 v3 cross-arm scored responses, whereas
OpenRouter exposes it in all 1,224. Thus no cross-provider reasoning-effort comparison is possible.
The qwen inconsistencies also show that subtracting `reasoning_tokens` from `completion_tokens` is
not a provider-agnostic “answer token” estimator.

Safe conclusion:

> Completion-token counts are provider usage fields that mix hidden reasoning and required visible
> output, including the selected-option echo. Provider-reported reasoning-token details are absent
> on GIFT and are not consistently accounted across routed OpenRouter backends. Neither field
> supports a cross-provider or general causal effort claim in this experiment.

## 7. “20 minutes / 8 failures per added correct”

The original values can be reverse engineered exactly:

```text
v1 net correct = 22 over 1,244 cells
projected wall difference
  = [(31,584/1,386) - (2,762/1,896)] × 1,244
  = 26,536 seconds
26,536 / 22 = 1,206 seconds = 20.10 minutes per net correct

projected raw GIFT error rows
  = (196/1,386) × 1,244 = 175.9
175.9 / 22 = 8.00 per net correct
```

This fails for four independent reasons:

1. It uses the superseded v1 cross-arm population. The unchanged v2/v3 population has 1,224 cells
   and +23 net correct; mechanical substitution yields 18.92 minutes and 7.53, not 20 and 8.
2. The OpenRouter time rate uses the invalid completion-timestamp burst heuristic described above.
3. The error projection allocates all 196 run-wide error rows—including 17 recovered 401s and 179
   errors on calls with no score—proportionally onto a subset selected to have GIFT scores. The
   actual 1,224 selected GIFT calls contain 1,224 HTTP-200 attempts plus only 15 recovered 401
   intermediates.
4. The +23 pooled answers combine heterogeneous model effects: gemma +17, glm +10, qwen −1, and
   gemini −3. A single pooled “price” hides the decision-relevant sign reversals and has an unstable
   denominator under resampling.

One can mechanically divide the v3 summed paired call-duration difference by +23:
`13,784.388 / 23 = 599.32 s = 9.99 min`. This is **not** a wall-clock cost: OpenRouter calls were
concurrent, failed/unscored GIFT calls are excluded, the arms were not contemporaneous, and no
monetary or compute-resource cost is attached. It should not be promoted as a result.

SQLite has OpenRouter `response_json.usage.cost` values but no GIFT cost values. There is no common
currency/price, GPU-time, energy, or operator-time ledger. A cross-provider monetary cost or
cost-effectiveness statement is therefore unavailable.

## 8. Dominance audit

On the observed 306-item cross-arm subset, direct OpenRouter gemini has the following descriptive
ordering:

| configuration | correct / 306 | accuracy | median recorded duration |
|---|---:|---:|---:|
| OpenRouter gemini | **301** | **98.37%** | **3.4465 s** |
| GIFT gemini | 298 | 97.39% | 15.703 s |
| GIFT glm | 295 | 96.41% | 20.7155 s |
| GIFT qwen | 281 | 91.83% | 23.812 s |
| GIFT gemma | 270 | 88.24% | 14.6845 s |

So OpenRouter gemini has the highest observed point accuracy and lowest median duration in this
selected sample. “Dominated outright” still overreaches because:

- the only same-base-model provider comparison is gemini, where the accuracy difference is only
  3/306 and its cluster-bootstrap interval includes zero;
- comparisons to GIFT glm/qwen/gemma change model and provider together;
- the 306-item set is the easier, sequentially covered prefix after cleaning;
- timings reflect concurrency/provider/run settings, not equal-resource service levels;
- GIFT monetary cost and non-MCQ product attributes were not measured.

Safe wording:

> On the 306-item observed overlap, OpenRouter gemini had the highest point accuracy (301/306) and
> the lowest median recorded call duration (3.45 s) among the five configurations shown. This is a
> descriptive model/provider/configuration comparison, not a general dominance or cost claim.

## 9. Reproducible SQL and calculations

### Count each grain without retry join multiplication

```sql
WITH lc AS (
  SELECT e.id, e.name, lc.model, COUNT(*) logical_created
  FROM experiments e JOIN logical_calls lc ON lc.experiment_id=e.id
  GROUP BY e.id,e.name,lc.model
), att AS (
  SELECT e.id, lc.model,
         COUNT(DISTINCT pa.logical_call_id) distinct_attempted,
         COUNT(*) provider_attempts
  FROM experiments e
  JOIN logical_calls lc ON lc.experiment_id=e.id
  JOIN provider_attempts pa ON pa.logical_call_id=lc.id
  GROUP BY e.id,lc.model
), sc AS (
  SELECT e.id, lc.model, COUNT(DISTINCT s.logical_call_id) scored
  FROM experiments e
  JOIN logical_calls lc ON lc.experiment_id=e.id
  JOIN scores s ON s.logical_call_id=lc.id
  GROUP BY e.id,lc.model
)
SELECT lc.name,lc.model,lc.logical_created,
       COALESCE(att.distinct_attempted,0),COALESCE(sc.scored,0),
       COALESCE(att.provider_attempts,0)
FROM lc LEFT JOIN att USING(id,model) LEFT JOIN sc USING(id,model)
ORDER BY lc.id,lc.model;
```

Planned per-model counts were added from dataset row count/config limit and the four-model launch
roster. Separate CTEs are required; directly joining attempts and scores multiplies retry rows.

### Latest GIFT outcome and internal retries

```sql
WITH ranked AS (
  SELECT pa.*,
         ROW_NUMBER() OVER (
           PARTITION BY pa.logical_call_id
           ORDER BY pa.attempt_index DESC,pa.id DESC
         ) rn,
         COUNT(*) OVER (PARTITION BY pa.logical_call_id) attempts_for_call
  FROM provider_attempts pa
)
SELECT lc.model,r.status_code,r.error_type,
       COUNT(*) latest_calls,
       SUM(r.attempts_for_call>1) internally_retried_calls
FROM ranked r
JOIN logical_calls lc ON lc.id=r.logical_call_id
JOIN experiments e ON e.id=lc.experiment_id
WHERE e.name='expA_gift_310726' AND r.rn=1
GROUP BY lc.model,r.status_code,r.error_type;
```

All-attempt status counts use the same joins without `rn=1`. The 17 multi-attempt GIFT calls have
status sequences `401 → 200`.

### Follow the attempt that was actually scored

```sql
SELECT e.name,q.question_id,lc.model,
       pa.latency_ms,pa.prompt_tokens,pa.completion_tokens,pa.total_tokens,
       json_extract(
         pa.response_json,
         '$.usage.completion_tokens_details.reasoning_tokens'
       ) AS reasoning_tokens
FROM scores s
JOIN parsed_answers p ON p.id=s.parsed_answer_id
JOIN provider_attempts pa ON pa.id=p.provider_attempt_id
JOIN logical_calls lc ON lc.id=s.logical_call_id
JOIN experiments e ON e.id=lc.experiment_id
JOIN questions q ON q.id=lc.question_id
WHERE e.name IN ('expA_or_310726','expB_or_310726','expA_gift_310726');
```

This join is essential for latency/token work. Selecting the latest or an arbitrary parsed attempt
can choose a superseded retry.

### Missing OpenRouter-A cell

```sql
SELECT pa.attempt_index,pa.status_code,pa.finish_reason,
       pa.completion_tokens,pa.latency_ms,p.parse_status
FROM logical_calls lc
JOIN experiments e ON e.id=lc.experiment_id
JOIN questions q ON q.id=lc.question_id
JOIN provider_attempts pa ON pa.logical_call_id=lc.id
LEFT JOIN parsed_answers p ON p.provider_attempt_id=pa.id
WHERE e.name='expA_or_310726'
  AND q.question_id='b320'
  AND lc.model='z-ai/glm-5.2'
ORDER BY pa.attempt_index;
```

### Descriptive paired calculations

For current `cross_arm_A.json`, filter `analysis_include == true` and compute within each
`(question_id, model)` pair:

```text
latency difference seconds = (gift_latency_ms - or_latency_ms) / 1000
latency ratio              = gift_latency_ms / or_latency_ms
completion-rate ratio      = (gift_tokens / gift_latency_seconds)
                             / (or_tokens / or_latency_seconds)
```

Reported table values are ordinary sample medians. No causal interpretation or cross-provider
price conversion was applied.

## 10. Release-safe operational wording

The following paragraph is fully supported by the audit:

> GIFT A was stopped after the sequential runner had created 1,566 of 1,896 planned logical calls
> (82.6%); 1,565 reached the provider and 1,384 produced scores (73.0%). The database contains
> 1,582 physical GIFT attempts: 196 (12.39%) are non-2xx rows, including 17 intermediate 401s that
> were retried successfully. At stop, 179 provider-started calls ended on 429/500 and two HTTP-200
> responses were unparseable. The launch was configured at concurrency one and yielded 1,384
> scores over about 8 h 47 min, or roughly 158 scored cells/hour under those specific run settings.
> On the cleaned 306-item overlap, the median recorded GIFT-minus-OpenRouter call-duration
> difference was 11.93 s, with model medians from 4.64 to 13.44 s. Because provider path,
> concurrency, prompt length, routing, and run time were not controlled, this is not an intrinsic
> latency or retrieval-tax estimate. Completion tokens include required answer echo, GIFT exposes
> no reasoning-token field, and no common provider-cost ledger exists; no effort, monetary-cost,
> minutes-per-correct, failures-per-correct, or general dominance claim is supported.

## Audit snapshot hashes

| artifact | SHA-256 |
|---|---|
| `experiment.sqlite` | `dec53a3d8ed452676672820a758b4571d061c3fe994c45981095d30216744748` |
| `cross_arm_A.json` | `987c632976260d4614056afcc9210fcd4902d322fcfe28b480ebc2e6216c8120` |
| `paired_clean.json` | `76b9059cd67a1024cde1655dd3f32083bbfbbb40609728dc65173b25b8835187` |
| `dataset_meta.json` | `fc4b4d5aa217dcce743f9269583ff8002f4d77360d4668d108ad7a143d7e1148` |
| `final_analysis_results.json` | `e420cd5a0e5505ab1c725d2c8ae59fbc722567f12e879b837278bd6b37364f3e` |
| `gift_run.log` | `ca967f9788578b336c43fcc8b9dfa982c008e6690b6ab59005752ec4a4a37b45` |
| `openrouter_run.log` | `deef4b72024825aa87047e048b95d5468f4c4b73e481f898dc87f7b5a083a49b` |
| `openrouter_b.log` | `4283df7508215aaa78d12092dbfdc965e16f5b44e5f2372208bf60ec89a5a1d1` |
| `retry_a_or.log` | `f589d27dd881f74e213289dee251863108df8043c36d2a800f07be4e8e37581e` |
