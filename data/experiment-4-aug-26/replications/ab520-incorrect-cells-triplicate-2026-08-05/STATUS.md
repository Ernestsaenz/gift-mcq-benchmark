# Replication status

Updated: 2026-08-06T14:05:00Z

Status: **PARTIALLY_EXECUTED — 1,697 / 1,796 scored (94.5%)**

The frozen queue contains 1,796 run-2/run-3 calls derived from 898 strict-incorrect
run-1 cells. 99 cells remain outstanding, 8 of which are unrecoverable.

## Progress by arm

| Arm | Scored | Total | Outstanding |
| --- | --- | --- | --- |
| openrouter_A | 406 | 406 | 0 |
| openrouter_B | 966 | 1064 | 98 |
| tailscale_A | 325 | 326 | 1 |
| **Total** | **1697** | **1796** | **99** |

openrouter_B: gemma 458/458, qwen 284/284, glm 222/222, gemini 2/100.
tailscale_A: gemini 26/26, gemma 162/162, qwen 98/98, glm 39/40.

## Exhausted cells — unrecoverable under the frozen protocol

Eight logical calls have reached the five-attempt ceiling without a score. They cannot
be retried without raising `--max-provider-attempts`, which is a protocol change.

| Arm | Model | Question | Runs | Failure |
| --- | --- | --- | --- | --- |
| openrouter_B | google/gemini-3.6-flash | n012 | 2, 3 | all 429 rate_limited |
| openrouter_B | google/gemini-3.6-flash | n036 | 2, 3 | all 429 rate_limited |
| openrouter_B | google/gemini-3.6-flash | b326 | 2, 3 | all 429 rate_limited |
| openrouter_B | google/gemini-3.6-flash | b373 | 2 | all 429 rate_limited |
| tailscale_A | z-ai/glm-5.2 | b264 | 2 | all 500, four hanging exactly 150.1-150.2s |

**Maximum achievable under the current protocol is 1,788 / 1,796.**

## Failed resume attempt, 2026-08-06 ~14:00Z — read before retrying again

A bounded loop re-invoked the executor 6 times against openrouter_B gemini. Result:

```
round 1: +2  total 2/100  exhausted 2
round 2: +0  total 2/100  exhausted 3
round 3: +0  total 2/100  exhausted 4
round 4: +0  total 2/100  exhausted 5
round 5: +0  total 2/100  exhausted 6
round 6: +0  total 2/100  exhausted 7
```

It banked 2 scores and destroyed 5 more cells. Net negative. Do not repeat this
design.

The cause is structural, not bad luck. The executor selects targets in a fixed order
and aborts the entire run on a single 429 (`execute_replicates.py:309`). Previously
attempted cells sort to the head of the queue, so every round re-attacked the same
head cell, burned 2 of its attempts, and aborted before reaching anything new. Each
round therefore cost almost exactly one cell pushed to the ceiling, and the run never
advanced. Confirmed by the budget distribution afterwards: the 88 never-attempted
cells are still at 0 attempts and were never reached.

Current gemini_B budget:

| Attempts used | Cells |
| --- | --- |
| 0 | 88 |
| 2 | 1 |
| 4 | 2 |
| 5 (exhausted) | 7 |

The 88 untouched cells are the recoverable asset and are still intact.

### If a further attempt is made, change the design

1. Gate on the **frozen payload**, not on a trivial request. A bare 1-token call to
   this model returned 200 on 10 of 10 probes at a moment when the schema-constrained
   frozen payload was only succeeding about half the time. The trivial probe is not a
   valid readiness signal.
2. Require sustained health before spending any budget — e.g. 10 of 10 frozen-payload
   replays serving, not a single sample.
3. Sweep, do not loop: issue at most one invocation per distinct cell per sweep using
   `--question-id` / `--run-index`, and never re-attack a cell that just failed within
   the same sweep. This spreads exposure across cells instead of concentrating it on
   the queue head.

## OpenRouter B gemini — shared upstream pool, intermittent

The 429 body identifies the cause:

```
"limit_source": "upstream_provider_shared_pool"
"provider_name": "Google AI Studio",  "is_byok": false
```

The account has no BYOK key, so this model draws on OpenRouter's shared Google AI
Studio pool. Arm A completed 18/18 only because it ran first, at 16:17-16:33Z on
2026-08-05, before the pool was drained.

Two earlier hypotheses recorded here were wrong and are retracted: the condition is
**not** arm-specific, and it is **not** caused by the B payload or by
`provider.require_parameters` narrowing provider routing.

Pool availability measured against the frozen payload, all on 2026-08-06:

| Time | Serving |
| --- | --- |
| ~10:30Z | 2 of 4 |
| ~13:55Z | 2 of 4 |
| ~14:05Z, after the resume loop | 1 of 6 |

Availability degrades as our own traffic consumes the shared pool, so sustained
batches make their own conditions worse.

### Recommended remedy

Add a Google AI Studio key to the OpenRouter account at
`https://openrouter.ai/settings/integrations`. This moves the model onto the account's
own rate limits. It is a credentials change, not a request change, so the frozen
payload stays byte-identical and gemini_B remains comparable to gemini_A.

Rejected alternative: setting a provider-routing preference or dropping
`provider.require_parameters` would alter the frozen request and break comparability
with the A-condition results already collected.

## Concurrency finding

The TailScale backend fails under request rate, not on particular questions. The
2026-08-05 gemma batch at concurrency 5 halted on
`three_consecutive_transport_failures` and abandoned 52 cells; the same cells at
concurrency 2 completed 58/58 with zero failures and cleared all 6 cells previously
stuck on timeouts. Recommended bound for this backend: 2-3.

Lowering concurrency does **not** help the OpenRouter shared-pool limit: batches at
concurrency 2 and single-cell probes at concurrency 1 were refused just as fast as the
original concurrency-10 batch.

## Integrity

Verified 2026-08-06. All five immutable artifacts recompute to the SHA-256 values
recorded in `manifests/preparation-summary.json`. The `database_sha256` entry no longer
matches `runs/` by design, because execution writes to that database.

The 1,796 ledger rows collapse to exactly the 898 unique (arm, source_key, model)
triples that carry `strict_correct == "0"` in the source CSV, with zero mismatches
against `run1_selected_letter` / `run1_correct_letter`.

Of the 1,697 scored results, 1,696 parsed `ok` and 1 `ok_conflict`. No score exists
without a provider attempt. No logical call exceeds the five-attempt ceiling.

## Caveat for analysis

The 99 outstanding cells are not randomly distributed. 98 of them are the
openrouter_B/gemini slice, which has only 2 of 100 cells scored. Any variance analysis
run against the current data has effectively no run-2/run-3 estimate for that model on
the B condition, while having complete coverage for the same model on the A condition —
an asymmetry that would bias any A-vs-B comparison involving gemini.
