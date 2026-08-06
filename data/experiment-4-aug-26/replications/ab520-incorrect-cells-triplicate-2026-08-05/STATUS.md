# Replication status

Updated: 2026-08-06T09:15:00Z

Status: **PARTIALLY_EXECUTED — 1,500 / 1,796 scored (83.5%)**

The frozen queue contains 1,796 run-2/run-3 calls derived from 898 strict-incorrect
run-1 cells. Execution ran from 2026-08-05T16:17:38Z to 2026-08-05T17:11:14Z and is
currently stopped. 296 cells remain outstanding.

## Progress by arm

| Arm | Scored | Total | Outstanding |
| --- | --- | --- | --- |
| openrouter_A | 406 | 406 | 0 |
| openrouter_B | 964 | 1064 | 100 |
| tailscale_A | 130 | 326 | 196 |
| **Total** | **1500** | **1796** | **296** |

## Outstanding work

| Arm | Model | Scored | Total | Blocker |
| --- | --- | --- | --- | --- |
| openrouter_B | google/gemini-3.6-flash | 0 | 100 | Upstream 429. 11 cells attempted (26 attempts, all rate_limited), 89 never started. Retries at concurrency 2 and 1 also returned 429. |
| tailscale_A | google/gemma-4-26b-a4b-it | 104 | 162 | Transport timeouts. 6 cells unresolved across 3 questions (b101, b77, b88), 52 never started. Batch halted on `three_consecutive_transport_failures`. One isolated retry (b61 run 3) succeeded on its second attempt. |
| tailscale_A | qwen/qwen3.6-35b-a3b | 0 | 98 | Never started — no invocation issued. |
| tailscale_A | z-ai/glm-5.2 | 0 | 40 | Never started — no invocation issued. |

## Integrity

Verified 2026-08-06. All five immutable artifacts recompute to the SHA-256 values
recorded in `manifests/preparation-summary.json`: the source CSV, the frozen ledger,
the pre-execution snapshot, and both condition inputs. The `database_sha256` entry no
longer matches `runs/` by design, because execution writes to that database.

The 1,796 ledger rows collapse to exactly the 898 unique (arm, source_key, model)
triples that carry `strict_correct == "0"` in the source CSV, with zero mismatches
against `run1_selected_letter` / `run1_correct_letter`. No cell correct in run 1 is
present in the queue.

Of the 1,500 scored results, 1,499 parsed `ok` and 1 `ok_conflict`. No score exists
without a provider attempt. Maximum attempts on any single logical call is 4, below
the frozen five-attempt ceiling.

## Caveat for analysis

The 296 outstanding cells are not randomly distributed — they are concentrated in
three arm/model slices, two of which have no data at all. Any variance analysis run
against the current partial data would systematically under-represent
openrouter_B/gemini and tailscale_A/qwen and tailscale_A/glm.
