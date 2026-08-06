# Replication status

Updated: 2026-08-06T21:20:00Z

Status: **COMPLETE TO PROTOCOL CEILING — 1,788 / 1,796 scored (99.6%)**

The frozen queue contains 1,796 run-2/run-3 calls derived from 898 strict-incorrect
run-1 cells. Execution ran 2026-08-05T16:17Z to 17:11Z and 2026-08-06T09:21Z to 21:16Z.
No runnable work remains: the 8 outstanding cells are all exhausted at the five-attempt
ceiling, so 1,788 is the maximum achievable without a further protocol change.

**Read the PROTOCOL DEVIATION section before analysing.** 91 of the 93 scored gemini_B
cells were collected through Google Vertex at default temperature, not the frozen
`temperature=0`. They are not comparable to the rest of the study without stratifying.

## Progress by arm

| Arm | Scored | Total | Outstanding |
| --- | --- | --- | --- |
| openrouter_A | 406 | 406 | 0 |
| openrouter_B | 1057 | 1064 | 7 |
| tailscale_A | 325 | 326 | 1 |
| **Total** | **1788** | **1796** | **8** |

openrouter_B: gemma 458/458, qwen 284/284, glm 222/222, gemini 93/100.
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

### No alternative provider exists — checked 2026-08-06

The OpenRouter catalogue was queried directly for every endpoint of each model in
this study. `require_parameters: true` in the harness demands a provider supporting
`temperature` and `top_p`, so only compatible providers can serve a frozen request.

| Model | Providers | Compatible with temperature + top_p |
| --- | --- | --- |
| google/gemini-3.6-flash | 2 | **1** — Google AI Studio only |
| google/gemma-4-26b-a4b-it | 9 | 9 |
| qwen/qwen3.6-35b-a3b | 9 | 9 |
| z-ai/glm-5.2 | 27 | 27 |

gemini is closed-weights, so only Google serves it: AI Studio (supports temperature,
rate-limited) or Vertex (does not support temperature). The `:batch` variant is
Vertex-only. No third party can offer this model, so provider substitution is not
available. The other three models never stalled precisely because OpenRouter could
fall back across 9-27 interchangeable providers.

Vertex was measured as a fallback: it served 5/5, but with `temperature` and `top_p`
dropped it is not deterministic. Repeating one frozen request three times per question
gave `['c','c','c']`, `['d','d','d']`, `['b','c','b']` — the third question returned
two different answers. Since this study measures run-to-run variance at temperature 0,
routing gemini_B through Vertex would fold provider sampling noise into the very
quantity being measured, and its variance would not be comparable to gemini_A or to
run 1.

Note that `require_parameters: true`
(`code/medrag_eval/providers/openrouter.py:176`) is what forces this to fail loudly
rather than silently serving a request stripped of `temperature=0`. It is an integrity
guarantee, not a routing preference, and it is shared by every experiment in this
repository.

## PROTOCOL DEVIATION — gemini_B routed to Google Vertex, 2026-08-06

Authorised by the principal investigator after the evidence below was presented.
Recorded here because the affected cells are **not comparable** to the rest of the
study and must not be pooled with them without stratifying.

**What changed.** `openrouter_B` / `google/gemini-3.6-flash` cells are now issued with

```json
"provider": {"order": ["google-vertex"], "allow_fallbacks": false, "require_parameters": false}
```

instead of the frozen `{"require_parameters": true}`. Everything else in the request is
unchanged: same prompt, same `mcq_es_v4` version, same JSON schema, and `temperature: 0`
and `top_p: 1.0` are still transmitted.

**What it costs.** Vertex does not support `temperature` or `top_p`. Per OpenRouter's
documentation, with `require_parameters: false` a provider "can still receive the
request, but will ignore unknown parameters". So the declared `temperature=0` is
**silently discarded** and the model samples at its default temperature of 1.0.
Measured before authorising: three repeats of one frozen request returned
`['b','c','b']`. Vertex without a seed is not deterministic.

Because this study measures run-to-run variance at temperature 0, the variance observed
in these cells includes provider sampling noise that no other cell in the study carries.

**Seed was considered and rejected.** Fixing a seed does restore stability (measured:
`['b','b','b','b']`), but it does not restore `temperature=0` — it only makes a
temperature-1.0 draw repeatable. A shared seed across runs 2 and 3 would force their
variance to zero by construction; distinct seeds would measure injected sampling noise.
Neither is the quantity this study is estimating, and neither arm A nor run 1 sent a
seed.

### How to identify affected cells

The deviation is machine-detectable from the audit record; it does not rely on reading
this document:

```sql
SELECT ... FROM provider_attempts
WHERE json_extract(request_json, '$.provider.order[0]') = 'google-vertex';
```

Affected attempts also record `"provider": "Google"` in `response_json` (Vertex) rather
than `"Google AI Studio"`, and carry a different `request_sha256` from the frozen shape.

### The gemini_B slice is stratified, not uniform

| Cells | Regime |
| --- | --- |
| 2 | Google AI Studio, real `temperature=0`, collected 2026-08-05 before the pool blocked |
| 91 | Google Vertex, default temperature, collected 2026-08-06 |
| 7 | Exhausted at the five-attempt ceiling, no data |

Attributed by the upstream that served the scoring attempt, not by attempt history:
three of the 91 Vertex cells also carry earlier failed AI Studio attempts.

Those 2 AI Studio cells cannot be re-collected under the new route: they are already
scored and the executor skips scored cells, which is the guard that prevents
overwriting data. Treat them as a separate stratum — they are the only two gemini_B
cells whose expected variance is structurally lower than the rest.

### Harness change backing this

`ProviderRequest` gained an optional `provider_routing` field
(`code/medrag_eval/providers/base.py`), consumed by `_chat_payload`
(`code/medrag_eval/providers/openrouter.py`) and threaded through `_execute_call` /
`_execute_call_with_conn` (`code/medrag_eval/runner.py`). It defaults to `None`
everywhere, which reproduces the previous payload byte for byte — verified by
constructing both payloads and diffing them. No other experiment is affected.

The executor exposes it as `--deviation-route-upstream`, named so the deviation is
legible in the recorded command line of any invocation that used it, and it prints a
`protocol_deviation` banner to the log before issuing any call. `allow_fallbacks:false`
is deliberate: if Vertex is unavailable the call fails rather than quietly reverting to
AI Studio, which would mix two sampling regimes inside one slice.

## Recommended remedy

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

Of the 1,788 scored results, 1,787 parsed `ok` and 1 `ok_conflict`. No score exists
without a provider attempt. No logical call exceeds the five-attempt ceiling.

## Caveat for analysis

Coverage is now effectively complete: 8 missing cells out of 1,796 (0.4%), spread
across 4 questions of gemini_B and 1 of tailscale_A/glm. That level of missingness is
immaterial to any aggregate.

The live hazard is no longer coverage but **heterogeneity**. 91 of the 93 scored
gemini_B cells were collected through Google Vertex at default temperature rather than
the frozen `temperature=0`, while gemini_A's 18 cells and every other slice ran at
`temperature=0`. A gemini A-vs-B comparison therefore contrasts two sampling regimes,
not two prompt conditions. Stratify on the upstream provider (see the deviation section
above for the SQL) before pooling, and treat the 2 AI Studio gemini_B cells as a third
stratum.
