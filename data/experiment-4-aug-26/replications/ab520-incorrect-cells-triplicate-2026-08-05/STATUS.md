# Replication status

Updated: 2026-08-06T10:40:00Z

Status: **PARTIALLY_EXECUTED — 1,695 / 1,796 scored (94.4%)**

The frozen queue contains 1,796 run-2/run-3 calls derived from 898 strict-incorrect
run-1 cells. Execution ran 2026-08-05T16:17:38Z to 17:11:14Z, resumed
2026-08-06T09:21Z to 10:35Z, and is currently stopped. 101 cells remain outstanding,
3 of which are now unrecoverable.

## Progress by arm

| Arm | Scored | Total | Outstanding |
| --- | --- | --- | --- |
| openrouter_A | 406 | 406 | 0 |
| openrouter_B | 964 | 1064 | 100 |
| tailscale_A | 325 | 326 | 1 |
| **Total** | **1695** | **1796** | **101** |

TailScale A: gemini 26/26, gemma 162/162, qwen 98/98, glm 39/40.

## Exhausted cells — unrecoverable under the frozen protocol

Three logical calls have reached the five-attempt ceiling without a score. They cannot
be retried without raising `--max-provider-attempts`, which is a protocol change.

| Arm | Model | Question | Run | Attempts | Failure |
| --- | --- | --- | --- | --- | --- |
| openrouter_B | google/gemini-3.6-flash | n012 | 2 | 5 | all 429 rate_limited |
| openrouter_B | google/gemini-3.6-flash | n012 | 3 | 5 | all 429 rate_limited |
| tailscale_A | z-ai/glm-5.2 | b264 | 2 | 5 | all 500 server_error, four hanging exactly 150.1-150.2s |

Maximum achievable under the current protocol is therefore **1,793 / 1,796**.

## OpenRouter B gemini — shared upstream pool, intermittent

Corrected diagnosis. Two earlier hypotheses recorded here were wrong and are retracted:
it is **not** arm-specific, and it is **not** caused by the B-condition payload or by
`provider.require_parameters` narrowing provider routing.

The 429 body identifies the cause directly:

```
"limit_source": "upstream_provider_shared_pool"
"provider_name": "Google AI Studio",  "is_byok": false
"google/gemini-3.6-flash is temporarily rate-limited upstream"
```

The account has no BYOK key, so this model draws on OpenRouter's shared Google AI
Studio pool. Arm A completed 18/18 only because it ran first, at 16:17-16:33Z on
2026-08-05, before the pool was drained; arm B began at 16:33Z and has been walled off
since.

The pool flaps on a seconds timescale rather than being cleanly down. On 2026-08-06 a
direct replay of the exact frozen payload returned 200 at ~10:30Z, while the batch
using the identical payload returned 429 in 0.1s at 10:32:01Z. Because the executor
fails fast on any rate limit, and because each failed logical call consumes 2 of its 5
attempts, retrying into a flapping pool destroys attempt budget without producing
scores. That is exactly what happened on 2026-08-06: three retry rounds produced zero
new scores and pushed n012 runs 2 and 3 past the ceiling.

**Retrying further is counterproductive.** 88 of the 100 gemini_B cells still have a
full untouched budget; a fourth blind retry round would start consuming those too.

Attempt budget currently spent across the 100 gemini_B cells:

| Attempts used | Cells |
| --- | --- |
| 0 | 88 |
| 2 | 9 |
| 4 | 1 |
| 5 (exhausted) | 2 |

### Recommended remedy

Add a Google AI Studio key to the OpenRouter account at
`https://openrouter.ai/settings/integrations`. This moves the model off the shared
pool and onto the account's own rate limits. It is a credentials change, not a request
change, so the frozen request shape, prompt, temperature, top-p, and JSON schema all
stay byte-identical and gemini_B results remain comparable to gemini_A.

Rejected alternative: setting an explicit provider-routing preference or dropping
`provider.require_parameters` would alter the frozen request and make the B-condition
results non-comparable to the A-condition results already collected.

## Concurrency finding

The TailScale backend fails under request rate, not on particular questions. The
2026-08-05 gemma batch at concurrency 5 halted on
`three_consecutive_transport_failures` and abandoned 52 cells; the same cells at
concurrency 2 on 2026-08-06 completed 58/58 with zero failures and also cleared all 6
cells previously stuck on timeouts. Recommended bound for this backend: 2-3.

Lowering concurrency does **not** help the OpenRouter shared-pool limit: the
2026-08-06 batch at concurrency 2 and single-cell probes at concurrency 1 were refused
just as fast as the original concurrency-10 batch.

## Integrity

Verified 2026-08-06. All five immutable artifacts recompute to the SHA-256 values
recorded in `manifests/preparation-summary.json`: the source CSV, the frozen ledger,
the pre-execution snapshot, and both condition inputs. The `database_sha256` entry no
longer matches `runs/` by design, because execution writes to that database.

The 1,796 ledger rows collapse to exactly the 898 unique (arm, source_key, model)
triples that carry `strict_correct == "0"` in the source CSV, with zero mismatches
against `run1_selected_letter` / `run1_correct_letter`. No cell correct in run 1 is
present in the queue.

Of the 1,695 scored results, 1,694 parsed `ok` and 1 `ok_conflict`. No score exists
without a provider attempt. Maximum attempts on any single logical call is 5, and no
call exceeds the ceiling.

## Caveat for analysis

The 101 outstanding cells are not randomly distributed. 100 of them are the entire
openrouter_B/gemini slice, which has no data at all. Any variance analysis run against
the current data would therefore have no run-2/run-3 estimate for that model on the B
condition, while having complete coverage for the same model on the A condition — an
asymmetry that would bias any A-vs-B comparison involving gemini. The remaining single
cell (tailscale_A/glm, b264 run 2) is immaterial at 1/326.
