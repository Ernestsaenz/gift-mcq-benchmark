# Retry and failure-traceability policy

This policy applies to any future execution needed to complete the adjusted August benchmark.

## Retry rule

- Never rerun a logical cell that already has exactly one accepted score.
- If a cell has no accepted score because of a timeout, rate limit, transient HTTP error, empty or partial response, or parse failure, retry the **same frozen input** up to five times after the initial failed attempt.
- Stop retrying a cell as soon as one response passes parsing and scoring.
- Use bounded concurrency and backoff between attempts. Do not use `--force`, disable reasoning, truncate the input, change the prompt, change the model, change the provider condition, or infer an answer from incomplete reasoning text.
- Stop the affected batch rather than repeatedly calling it if authentication fails, the production health/SHA gate fails, a circuit opens, database integrity fails, or failures indicate a deterministic protocol or context-limit rejection. Preserve that evidence and require operator review before resuming.

## Traceability requirements

Every attempt, successful or unsuccessful, must retain:

- logical cell identity, arm, condition, model, dataset, experiment, and attempt index;
- unchanged question, raw-input, system-prompt, user-prompt, and request hashes;
- start/end timestamps, HTTP status, latency, finish reason, error class, and redacted log path;
- response hash and parse outcome, without treating an invalid response as a score;
- invocation-level concurrency and status in `RUN_LEDGER.csv`;
- final recovery or terminal unresolved reason in `STATUS.md` and the unresolved-cell export.

If all five retries fail, the cell remains explicitly unresolved. It must not be imputed, reassigned, or silently omitted.

## Current execution state

As of 2026-08-05, the adjusted benchmark has **6,000/6,000 scored cells and zero unresolved cells**. Two cells had rejected first attempts; each succeeded on its first exact-input isolated retry. Their failed and successful attempts remain recorded in the SQLite database and `exports/recovered-first-attempt-failures.csv`. No additional retry is warranted for either cell.
