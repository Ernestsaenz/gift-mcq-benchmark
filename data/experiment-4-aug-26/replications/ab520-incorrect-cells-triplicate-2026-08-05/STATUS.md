# Replication status

Updated: 2026-08-06T10:25:00Z

Status: **PARTIALLY_EXECUTED — 1,695 / 1,796 scored (94.4%)**

The frozen queue contains 1,796 run-2/run-3 calls derived from 898 strict-incorrect
run-1 cells. Execution ran 2026-08-05T16:17:38Z to 17:11:14Z, resumed
2026-08-06T09:21Z to 10:25Z, and is currently stopped. 101 cells remain outstanding.

## Progress by arm

| Arm | Scored | Total | Outstanding |
| --- | --- | --- | --- |
| openrouter_A | 406 | 406 | 0 |
| openrouter_B | 964 | 1064 | 100 |
| tailscale_A | 325 | 326 | 1 |
| **Total** | **1695** | **1796** | **101** |

TailScale A is complete except for one cell: gemini 26/26, gemma 162/162,
qwen 98/98, glm 39/40.

## Outstanding work

| Arm | Model | Scored | Total | Blocker |
| --- | --- | --- | --- | --- |
| openrouter_B | google/gemini-3.6-flash | 0 | 100 | Upstream 429. 12 cells attempted (28 attempts, all rate_limited), 88 never started. Retried at concurrency 2 and 1 on 2026-08-05, and probed again on 2026-08-06 after ~18h: still an immediate 429 at 0.3s with no Retry-After. Not cooldown-shaped. See "OpenRouter B gemini" below. |
| tailscale_A | z-ai/glm-5.2 | 39 | 40 | Question b264 run 2 only. Four attempts, all HTTP 500 `server_error`, three of them hanging for exactly 150.2s — consistent with a client-side 150s timeout on a stalled backend, not a rejection. Run 3 of the same question succeeded in 45s. One attempt remains in budget, deliberately unspent. |

## OpenRouter B gemini — arm-specific, not account-wide

`google/gemini-3.6-flash` completed 18/18 on **openrouter_A** with every attempt
HTTP 200, while **openrouter_B** returns immediate 429s for the same model, the same
API key, and the same day. The difference is arm-specific, which points at the
B-condition request payload routing to a different or restricted upstream provider
pool rather than at an account rate limit.

This has NOT been diagnosed further. Any fix that sets an OpenRouter provider-routing
preference would change the frozen request shape and must be treated as a protocol
decision, not a retry.

## Concurrency finding

The TailScale backend fails under request rate, not on particular questions. The
2026-08-05 gemma batch at concurrency 5 halted on
`three_consecutive_transport_failures` and abandoned 52 cells; the same cells at
concurrency 2 on 2026-08-06 completed 58/58 with zero failures and also cleared all 6
cells previously stuck on timeouts. Recommended bound for this backend: 2–3.

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
without a provider attempt. Maximum attempts on any single logical call is 4, below
the frozen five-attempt ceiling; no cell exceeds it.

## Caveat for analysis

The 101 outstanding cells are not randomly distributed. 100 of them are the entire
openrouter_B/gemini slice, which has no data at all. Any variance analysis run against
the current data would therefore have no run-2/run-3 estimate for that model on the B
condition, while having complete coverage for the same model on the A condition — an
asymmetry that would bias any A-vs-B comparison involving gemini. The remaining single
cell (tailscale_A/glm, b264 run 2) is immaterial at 1/326.
