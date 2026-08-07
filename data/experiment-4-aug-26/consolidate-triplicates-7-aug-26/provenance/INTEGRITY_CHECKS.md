# Integrity checks — ab520 incorrect-cell triplicate (runs 2–3)

All checks below were executed on 2026-08-07 against the live run DB, opened
read-only per SPEC.md's instruction (`sqlite3 -readonly` is broken on this
machine; `sqlite3 "file:<abs-path>?mode=ro"` was used instead):

```text
data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite
```

`PRAGMA integrity_check` returned `ok` before any of the checks below were
run.

## 1. 1,796 frozen logical calls, run indices only {2, 3}, 898 each

```sql
SELECT COUNT(*) FROM logical_calls;
SELECT DISTINCT run_index FROM logical_calls ORDER BY 1;
SELECT run_index, COUNT(*) FROM logical_calls GROUP BY run_index;
```

Output:

```
1796
2
3
2|898
3|898
```

**PASS.** 1,796 total, run indices are exactly {2, 3}, 898 rows each.

Arm breakdown (via `experiments.name`), for cross-reference against
SPEC.md's per-arm table:

```sql
SELECT e.name, COUNT(*) FROM logical_calls lc
JOIN experiments e ON e.id = lc.experiment_id GROUP BY e.name;
```

```
ab520_incorrect_triplicates_or_A_20260805 | 406
ab520_incorrect_triplicates_or_B_20260805 | 1064
ab520_incorrect_triplicates_ts_A_20260805 | 326
```

406 + 1064 + 326 = 1796. **Matches** SPEC.md's `target_counts_by_arm` and
`preparation-summary.json`'s `target_counts_by_arm` exactly.

## 2. Ledger rows collapse to the 898 run-1 `strict_correct=='0'` triples, zero mismatches

Method: read both CSVs with `csv.DictReader` (Python, `uv run python3`, no
external deps) and compare `(arm, source_key, model)` triple sets.

```python
wrong_triples = {(row['arm'], row['source_key'], row['model'])
                  for row in run1_csv if row['strict_correct'] == '0'}
ledger_triples = {(row['arm'], row['source_key'], row['model'])
                   for row in ledger_csv}
```

Output:

```
total run-1 rows: 6000
distinct (arm, source_key, model) with strict_correct==0: 898
ledger rows: 1796
distinct (arm, source_key, model) triples in ledger: 898
mismatches (in ledger not in wrong_triples): 0
mismatches (in wrong_triples not in ledger): 0
```

**PASS.** The 1,796 ledger rows collapse to exactly the 898 run-1-incorrect
`(arm, source_key, model)` triples (2 run rows per triple, run_index 2 and
3), with zero set-symmetric-difference mismatches in either direction.

## 3. No score without a provider attempt

```sql
SELECT COUNT(*) FROM scores s
JOIN parsed_answers pa ON pa.id = s.parsed_answer_id
LEFT JOIN provider_attempts att ON att.id = pa.provider_attempt_id
WHERE att.id IS NULL;
```

Output: `0`.

**PASS.**

## 4. No logical call above 5 attempts; max reported

```sql
SELECT MAX(cnt) FROM (
  SELECT logical_call_id, COUNT(*) cnt FROM provider_attempts GROUP BY logical_call_id
);
SELECT logical_call_id, COUNT(*) cnt FROM provider_attempts
GROUP BY logical_call_id HAVING cnt > 5;
```

Output: max attempts per logical call = `5`; the `HAVING cnt > 5` query
returned zero rows.

**PASS.** Ceiling is exactly 5, never exceeded.

## 5. Parse status distribution

```sql
SELECT parse_status, COUNT(*) FROM parsed_answers GROUP BY parse_status;
```

Output:

```
ok           | 1787
ok_conflict  | 1
```

Total parsed answers: 1,788. Total scores: 1,788 (`SELECT COUNT(*) FROM
scores;`). Total provider attempts: 1,856 (`SELECT COUNT(*) FROM
provider_attempts;`).

**MATCHES** SPEC.md: "1787 parses `ok`, 1 `ok_conflict`" and the headline
"Total scored: 1788 / 1796 (99.6%)."

## 6. Logical calls holding attempts with MORE THAN ONE distinct `request_sha256`

```sql
SELECT logical_call_id, COUNT(DISTINCT request_sha256) AS distinct_hashes
FROM provider_attempts GROUP BY logical_call_id HAVING distinct_hashes > 1;
```

Output — **3 logical calls**:

| logical_call_id | question_id | run_index | arm/provider | model | attempts | distinct hashes |
| --- | --- | --- | --- | --- | --- | --- |
| 416 | b373 | 3 | openrouter_B | google/gemini-3.6-flash | 5 | 2 |
| 417 | b323 | 2 | openrouter_B | google/gemini-3.6-flash | 3 | 2 |
| 485 | b101 | 2 | openrouter_B | google/gemini-3.6-flash | 5 | 2 |

### Independently re-verified after a correction from the team lead

This query was first run by this agent on 2026-08-07 and returned these same
3 rows. At that point SPEC.md and the `7ef8436` commit message both stated
"exactly 2 (b373 r3, b323 r2)," so this was flagged below as a disagreement
with SPEC.md, with the third call (`logical_call_id 485`, question `b101`,
run_index 2) identified as the omission — visible independently in the
`invocations/` directory (`or-b-gemini-probe-b101-r2-20260806.json`,
`or-b-gemini-probe-b101-r2-retry2.json`, committed in `0bf6537`/`10a8fa3`,
predating the `7ef8436` commit that stated the count as 2).

The team lead subsequently corrected SPEC.md to state 3 (naming all of
b101 r2, b323 r2, b373 r3, with attempt counts 5/3/5) and asked this agent to
re-run the check independently rather than take either figure on trust. Doing
so now (fresh query, same live DB, same read-only connection method) reproduces
**the identical 3 rows with the identical attempt counts (5, 3, 5)** shown in
the table above — this agent's original finding, this agent's fresh
re-verification, and SPEC.md's corrected figure are now all in agreement.
This section is kept as a "disagreement" writeup below because the analysis
of *why* the mismatch exists is unchanged and still useful, but the bottom
line is: **SPEC.md is now correct; there is no outstanding disagreement.**

Per-attempt detail for all three logical calls (`request_sha256` truncated
to 12 hex chars for legibility; full values available via the query above):

```sql
SELECT att.id, att.logical_call_id, att.attempt_index, att.status_code,
  json_extract(att.request_json,'$.provider.order[0]') AS routed_upstream,
  json_extract(att.response_json,'$.provider') AS resp_provider,
  substr(att.request_sha256,1,12) AS req_sha_prefix, att.error_type,
  att.created_at
FROM provider_attempts att WHERE att.logical_call_id IN (416,417,485)
ORDER BY att.logical_call_id, att.attempt_index;
```

```
id    lc_id  idx  status  routed_upstream  resp_provider  req_sha(12)   error_type     created_at
425   416    1    429     (null)           (null)         794eef333a21  rate_limited   2026-08-05T16:33:49Z
426   416    2    429     (null)           (null)         794eef333a21  rate_limited   2026-08-05T16:33:49Z
1764  416    3    429     (null)           (null)         794eef333a21  rate_limited   2026-08-06T15:52:00Z
1765  416    4    429     (null)           (null)         794eef333a21  rate_limited   2026-08-06T15:52:00Z
1773  416    5    200     google-vertex    Google         e11096bbcfa2  (null)         2026-08-06T21:13:16Z
427   417    1    429     (null)           (null)         6a0456b598ed  rate_limited   2026-08-05T16:35:05Z
428   417    2    429     (null)           (null)         6a0456b598ed  rate_limited   2026-08-05T16:35:05Z
1771  417    3    200     google-vertex    Google         f53c2b247c21  (null)         2026-08-06T21:13:10Z
1534  485    1    429     (null)           (null)         c25e8f97199b  rate_limited   2026-08-06T09:21:09Z
1535  485    2    429     (null)           (null)         c25e8f97199b  rate_limited   2026-08-06T09:21:09Z
1742  485    3    429     (null)           (null)         c25e8f97199b  rate_limited   2026-08-06T10:29:03Z
1743  485    4    429     (null)           (null)         c25e8f97199b  rate_limited   2026-08-06T10:29:03Z
1834  485    5    200     google-vertex    Google         c2479060ae0f  (null)         2026-08-06T21:15:24Z
```

**Explanation — the same explanation SPEC.md gives for the other two, and it
holds equally for the third.** In every one of the 3 cases, all failed
attempts (`status_code=429`, `error_type=rate_limited`) share **one**
`request_sha256` — they are exact-input retries against the original
AI-Studio-eligible routing (no `provider.order` override,
`provider_routing=None`, i.e. the frozen default), which was rate-limited
from `2026-08-05T16:33Z` onward per `ef04b53`/STATUS.md. Only the final,
scoring attempt (`status_code=200`) carries a **different** hash, because it
was reissued with `--deviation-route-upstream google-vertex` (see
`execute_replicates.py`'s `--deviation-route-upstream` flag, added in
`7ef8436` — full diff in `CODE_AND_DATABASE_PROVENANCE.md` §3), which changes
`provider.order`/`require_parameters` inside the request body and therefore
its hash. `response_json.provider` confirms this: `"Google"` (Vertex) on the
scoring attempt vs. `null`/absent on the failed 429s (no response body was
returned for a 429).

**Why the resulting score still has unambiguous provenance, for all 3
cases.** The failed attempts scored nothing — there is no `parsed_answers`
or `scores` row referencing attempt ids 425/426/1764/1765 (logical_call 416),
427/428 (417), or 1534/1535/1742/1743 (485). Each logical call's single
`scores` row references exactly one `parsed_answer`, which references
exactly one `provider_attempt` (the id-200 row), which carries exactly one
`request_sha256`. There is one scoring lineage per call; the extra hash
belongs entirely to attempts that failed before scoring.

```sql
-- confirms: for each of the 3 calls, the score's parsed_answer points at the
-- single 200-status attempt, not at any of the 429 attempts
SELECT s.logical_call_id, s.id AS score_id, pa.provider_attempt_id
FROM scores s JOIN parsed_answers pa ON pa.id = s.parsed_answer_id
WHERE s.logical_call_id IN (416,417,485);
-- -> (416, 1705, 1773), (417, 1703, 1771), (485, 1766, 1834) — all point at
--    the id-200 attempt for that call.
```

**Consequence for the sibling experiment's assertion.** SPEC.md and the
`7ef8436` commit both flag that `finalize_execution.py:284` in the sibling
`ab520-replacement-22-2026-08-04` package asserts one `request_sha256` per
logical call, and would trip on this replication's data. That is confirmed
correct: all 3 of the calls found above (not the 2 the `7ef8436` commit
message originally named) would trip a naive uniform-hash assertion. The
recommendation stands unchanged and is reaffirmed here: **the assertion
should be scoped to the `request_sha256` of the attempt that produced the
score** (i.e. join through
`scores → parsed_answers → provider_attempts` and assert uniqueness only
over that joined set), not to the full `provider_attempts` history of a
logical call, since retries-before-recovery are expected and, in this
replication, are the norm for every rate-limited gemini_B cell regardless of
whether the final routing changed.

## 7. gemini_B upstream attribution — cross-check of SPEC.md's 91/2 split

```sql
SELECT COALESCE(json_extract(pa.request_json,'$.provider.order[0]'),'google-ai-studio') AS upstream,
       COUNT(*)
FROM provider_attempts pa
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN experiments e ON e.id = lc.experiment_id
WHERE pa.status_code = 200
  AND e.name = 'ab520_incorrect_triplicates_or_B_20260805'
  AND lc.model = 'google/gemini-3.6-flash'
GROUP BY upstream;
```

Output:

```
google-ai-studio | 2
google-vertex     | 91
```

**MATCHES** SPEC.md's protocol-deviation section (91 Vertex + 2 AI Studio =
93 scored gemini_B cells) exactly, using the same attribution rule SPEC.md
specifies (attribute by the upstream of the `status_code = 200` attempt).

## 8. Housekeeping note — invocation/log file counts (resolved)

Actual counts on disk, verified 2026-08-07 and unchanged since:

```text
$ ls invocations/ | wc -l
34
$ ls logs/ | wc -l
34
```

**History, kept for the audit trail:** SPEC.md's source table originally
listed "Invocation records (20 files)" and "Per-invocation logs (20 files)."
That was stale — consistent with the git history in
`CODE_AND_DATABASE_PROVENANCE.md` §2, the initial `7571ab7` checkpoint added
the first ~17 invocation/log pairs, and five further commits (`0bf6537`,
`10a8fa3`, `7617826`, plus the probe files) each added more as the run was
resumed, retried, and probed through `2026-08-06` — so "20" described an
earlier state of the directory, not the final one. This was flagged as a
disagreement with SPEC.md when first found; SPEC.md's source table now
reads "34 files" in both rows, so **the two are in agreement and there is no
outstanding disagreement.** This never affected any of the scored-cell
counts above, which were all independently recomputed from the DB rather
than from file counts.

## Summary

| Check | Result |
| --- | --- |
| 1,796 logical calls, run_index ∈ {2,3}, 898 each | PASS |
| Ledger 1,796 → 898 run-1-incorrect triples, 0 mismatches | PASS |
| No score without a provider attempt | PASS |
| No logical call > 5 attempts (max = 5) | PASS |
| Parse status: 1787 ok / 1 ok_conflict | PASS, matches SPEC.md |
| Logical calls with >1 distinct request_sha256 | PASS, count is 3 (b101/run 2 [id 485], b323/run 2 [id 417], b373/run 3 [id 416]) — matches SPEC.md as corrected 2026-08-07. Originally found as a disagreement with an earlier SPEC.md draft that said 2; resolved, see §6. |
| gemini_B upstream attribution 91 Vertex / 2 AI Studio | PASS, matches SPEC.md |
| Invocation/log file counts | PASS, 34/34 — matches SPEC.md as corrected 2026-08-07. Originally found as a disagreement with an earlier SPEC.md draft that said 20/20; resolved, see §8. |
