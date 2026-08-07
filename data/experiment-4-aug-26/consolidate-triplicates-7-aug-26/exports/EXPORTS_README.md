# Exports — ab520 triplicate consolidation

Generated: **2026-08-07T08:22:39Z** (true filesystem mtime of the three CSVs
at first generation, confirmed with `stat`). Reproducibility was verified on
**2026-08-07T08:36:34Z** by re-running `build_exports.py` in place and
diffing SHA256 before/after — see "Byte-identity check" under Generation
below. Content is byte-identical between the two runs; only the mtime
advanced.

Owner: Agent 1 (data-export). Scope: `exports/` only, per
`../SPEC.md` file-ownership table. Nothing outside this directory was
modified. The SQLite database was opened read-only
(`file:<path>?mode=ro`) and never written to.

## Sources (all read-only, never modified)

| Role | Path | SHA256 |
| --- | --- | --- |
| Run-1 results, 6000 cells | `data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv` | `ce91b3f3eb90cd0b125a170a6f0a0a967c02d63da17cfa97161e62f739c4b721` (independently recomputed with `shasum -a 256`; matches `preparation-summary.json`) |
| Frozen replicate ledger | `data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/manifests/frozen-replicate-cell-ledger.csv` | `026bab787956cbe421fe1b380a5250beea0951f226e834a550b2b8cf153b3530` (independently recomputed; matches `preparation-summary.json`) |
| Runs 2-3 database (current, post-execution) | `data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite` | `6f72be10cdeb00a132ac1ab166527783af64cdbc177f254bac5fff22422a3359` (independently recomputed with `shasum -a 256`) |

**Correction:** an earlier version of this table listed the DB hash as
`823f92e01d9526e51204eb0fe082d69d8aa4e216830bd6b32d0cef0881ca3d6f`, copied
uncritically from `preparation-summary.json`'s `database_sha256` field. That
field was recorded *before* runs 2/3 executed and is identical to
`pre_execution_snapshot_sha256` in the same file — both point at
`manifests/ab520-incorrect-cell-triplicates.pre-execution.sqlite` (verified:
that file hashes to exactly `823f92e0...`). The live `runs/*.sqlite` file we
actually queried has since been populated with 1788 scores and 1856
provider attempts, so its hash has legitimately changed to `6f72be10...`.
The row above now reports the hash of the file we actually opened.

Join key between the run-1 CSV, the ledger, and the DB: `(arm, question_id,
model)` for the 898 cells, extended with `run_index` (`2`/`3`) for the 1796
logical calls. All three sources joined with **zero unresolved keys** — see
Verification below.

## 1. `consolidated-triplicates-898.csv` — 898 rows

One row per run-1-incorrect cell (arm, question, model). Derived by grouping
the 1796 ledger rows by `(arm, question_id, model)` and pulling run-1 truth
from the run-1 CSV and run-2/run-3 outcomes from the database.

| Column | Meaning | Allowed values | Raw/Derived |
| --- | --- | --- | --- |
| `arm` | Study arm | `openrouter_A`, `openrouter_B`, `tailscale_A` | raw (ledger) |
| `condition` | Question-set condition | `A`, `B` | derived (arm→condition map; `tailscale_A`→`A`) |
| `source_key` | Question source key (region\|year\|exam\|number) | free text | raw (run-1 CSV) |
| `question_id` | DB/CSV question id (e.g. `b101`, `n012`) | free text | raw |
| `model` | Model slug | 4 models, see SPEC.md | raw |
| `correct_letter` | Ground-truth answer letter | `a`-`d` | raw (run-1 CSV; cross-checked against ledger `run1_correct_letter`, 0 mismatches) |
| `run1_selected_letter` | Model's run-1 answer | `a`-`d` | raw (run-1 CSV) |
| `run1_strict_correct` | Run-1 strict correctness | `FALSE` always in this file (by construction — only strict-incorrect run-1 cells are included) | derived from raw `strict_correct` |
| `run2_selected_letter` | Model's run-2 answer | `a`-`d` or empty if not scored | raw (DB `parsed_answers.selected_letter` of the scoring attempt) |
| `run2_strict_correct` | Run-2 strict correctness | `TRUE`/`FALSE`, empty if not scored | raw (DB `scores.strict_correct`) |
| `run2_status` | Run-2 call outcome | `scored`, `exhausted` | derived (has a `scores` row vs. hit the 5-attempt ceiling with none) |
| `run3_selected_letter` | Model's run-3 answer | `a`-`d` or empty | raw |
| `run3_strict_correct` | Run-3 strict correctness | `TRUE`/`FALSE`, empty if not scored | raw |
| `run3_status` | Run-3 call outcome | `scored`, `exhausted` | derived |
| `n_runs_scored` | How many of run2/run3 produced a score | `0`, `1`, `2` | derived |
| `run2_upstream` | Upstream that served the run-2 scoring attempt | `google-ai-studio`, `google-vertex`, or empty | derived — **see "upstream scope" note below**; empty for every non-`google/gemini-3.6-flash` cell and for `tailscale_A` |
| `run3_upstream` | Upstream that served the run-3 scoring attempt | same as above | derived, same scope note |
| `temperature_honoured` | Whether the declared `temperature=0` was actually honoured for this cell | `TRUE`/`FALSE` | derived — `FALSE` iff either replicate's `upstream` is `google-vertex`; `TRUE` otherwise, per the PROTOCOL DEVIATION in `../SPEC.md` |
| `flipped_to_correct` | Did any replicate come back correct? | `TRUE`/`FALSE` | derived (`n_correct_across_replicates > 0`) |
| `n_correct_across_replicates` | Count of replicates (of the scored ones) that were strict-correct | `0`, `1`, `2` | derived |

**Upstream scope note (important):** the two-value `google-ai-studio` /
`google-vertex` coding exists to carry the specific, *verified* protocol
deviation documented in `../SPEC.md` (OpenRouter's `openrouter_B` /
`google/gemini-3.6-flash` cells were silently routed to Google Vertex, which
drops `temperature`). We populate `run{2,3}_upstream` **only** for
`google/gemini-3.6-flash` cells (both `openrouter_A` and `openrouter_B`),
based on the actual `response_json.provider` field of the scoring attempt
(`"Google"` → `google-vertex`, `"Google AI Studio"` → `google-ai-studio`).
For every other model, the OpenRouter request never set `provider.order` and
the true resolved upstream is a *different* provider (DeepInfra, Parasail,
AkashML, CoreWeave, SiliconFlow, Decart, Baidu, Venice, NextBit, Phala, or —
in 5 cases — literally `"Google"` for `google/gemma-4-26b-a4b-it`; see
"Anomaly investigated and ruled out" below — confirmed compliant, not a
deviation). We deliberately leave `upstream` empty for all of these rather
than labeling them with the Gemini-specific vocabulary, since that
vocabulary encodes a parameter-support gap that only exists for
`google/gemini-3.6-flash`, not for Gemma. `tailscale_A` cells always have
`upstream` empty and `temperature_honoured=TRUE` per SPEC.md.

## 2. `replicate-cell-level-1796.csv` — 1796 rows

One row per logical call (the 898 cells × run 2 and run 3).

| Column | Meaning | Allowed values | Raw/Derived |
| --- | --- | --- | --- |
| `arm` | Study arm | `openrouter_A`, `openrouter_B`, `tailscale_A` | raw (ledger) |
| `source_key` | Question source key | free text | raw (ledger) |
| `question_id` | Question id | free text | raw (ledger) |
| `model` | Model slug | 4 models | raw (ledger) |
| `run_index` | Replicate index | `2`, `3` | raw (ledger) |
| `status` | Call outcome | `scored`, `exhausted` | derived (presence of a `scores` row for this `logical_call_id`) |
| `selected_letter` | Model's answer on this replicate | `a`-`d`, empty if exhausted | raw (DB `parsed_answers.selected_letter` of the scoring attempt) |
| `correct_letter` | Ground-truth answer letter | `a`-`d` | raw (ledger `run1_correct_letter`, verified against `questions.correct_letter` and `scores.correct_letter` where present) |
| `strict_correct` | Strict correctness of this replicate | `TRUE`/`FALSE`, empty if exhausted | raw (DB `scores.strict_correct`) |
| `upstream` | Upstream that served the scoring attempt | `google-ai-studio`/`google-vertex` (gemini only) or empty | derived; see the upstream scope note above |
| `temperature_honoured` | Whether temp=0 was honoured for this specific call | `TRUE`/`FALSE` | derived — `FALSE` iff `upstream == google-vertex` |
| `n_attempts` | Provider attempts made for this logical call (retry ceiling is 5) | `1`-`5` | raw (`COUNT(*)` from `provider_attempts` for this `logical_call_id`) |
| `latency_ms` | Latency of the scoring attempt | integer ms, empty if exhausted | raw (DB `provider_attempts.latency_ms`) |
| `request_sha256` | Hash of the scoring attempt's request | hex string, empty if exhausted | raw (DB `provider_attempts.request_sha256`) |
| `parse_status` | Parser outcome for the scoring attempt | `ok`, `ok_conflict`, empty if exhausted | raw (DB `parsed_answers.parse_status`) |

The "scoring attempt" for a logical call is identified by following
`scores.logical_call_id → parsed_answers.id (via scores.parsed_answer_id) →
provider_attempts.id (via parsed_answers.provider_attempt_id)` — i.e. the
exact attempt that produced the recorded score, not simply the latest
attempt. This correctly avoids double-counting the 3 Vertex cells that also
carry an earlier failed AI Studio attempt (per SPEC.md's attribution rule).

## 3. `run1-6000-with-replicate-status.csv` — 6000 rows

All original columns of `benchmark-6000-cell-results-adjusted.csv`
(unchanged, raw), plus two derived columns appended at the end:

| Column | Meaning | Allowed values | Raw/Derived |
| --- | --- | --- | --- |
| `was_replicated` | Whether this run-1 cell was one of the 898 strict-incorrect cells selected for replication | `TRUE`/`FALSE` | derived |
| `replicate_outcome` | Replication result for this cell | `both_runs` (run2 & run3 both scored), `one_run` (exactly one scored), `no_runs` (neither scored — exhausted), `not_eligible` (run-1 was correct; never replicated) | derived |

All other columns are untouched pass-through from the source CSV (raw).

## Generation

Built by [`build_exports.py`](./build_exports.py), which lives in this
`exports/` directory (stdlib-only: `csv`, `sqlite3`; no third-party
dependencies) in a single deterministic pass:
1. Load run-1 CSV (6000 rows), filter `strict_correct == "0"` → 898 cells.
2. Load the frozen ledger (1796 rows, `run_index` 2/3).
3. Query the SQLite DB read-only (`file:...?mode=ro`) for every
   `logical_calls` row (1796), joined to `experiments` (→ arm) and
   `questions`; separately join `scores → parsed_answers →
   provider_attempts` to get the scoring attempt's `selected_letter`,
   `strict_correct`, `parse_status`, `request_sha256`, `latency_ms`, and
   upstream (`response_json.provider`).
4. Join ledger rows to DB results on `(arm, question_id, model, run_index)`.
5. Group by `(arm, question_id, model)` to build the 898-row export; use the
   1796 joined rows directly for the cell-level export; left-join the
   898-cell outcomes back onto the full 6000-row run-1 CSV for the third
   export.

Run with: `python3 exports/build_exports.py` from the repo root (paths
inside the script are absolute, so it also runs from any cwd).

### Byte-identity check

First generated 2026-08-07T08:22:39Z. Re-run 2026-08-07T08:36:34Z to confirm
the script actually reproduces the checked-in CSVs (not just "should" —
verified):

| File | SHA256 before re-run | SHA256 after re-run |
| --- | --- | --- |
| `consolidated-triplicates-898.csv` | `eff8716d0e0f5ac1fd6c4c1af1d31b207f5ebb41bba1ccccf44c96f53de3d401` | `eff8716d0e0f5ac1fd6c4c1af1d31b207f5ebb41bba1ccccf44c96f53de3d401` |
| `replicate-cell-level-1796.csv` | `8e3f62b3d437d0a64fcd9f60385d247cd914a374f18364d570cd93e55566d602` | `8e3f62b3d437d0a64fcd9f60385d247cd914a374f18364d570cd93e55566d602` |
| `run1-6000-with-replicate-status.csv` | `970a43c70137b1a02672dd14a29384f9840e27286ab672d2020a5fdcabeb8668` | `970a43c70137b1a02672dd14a29384f9840e27286ab672d2020a5fdcabeb8668` |

**Result: identical on all three files.** Only the on-disk mtime advanced
(08:22:39Z → 08:36:34Z); byte content did not change.

## Verification (all passed against `../SPEC.md`'s authoritative figures)

- Row counts: 898 / 1796 / 6000 — exact.
- Join: 0 ledger rows failed to resolve against the DB; 0 strict-incorrect
  run-1 cells failed to resolve against the ledger; 0 ledger cells outside
  the strict-incorrect set.
- `correct_letter` cross-check between the run-1 CSV and the ledger's
  `run1_correct_letter`: 0 mismatches across all 1796 ledger rows.
- Total scored: **1788 / 1796** — exact match.
- Scored per arm: `openrouter_A` 406, `openrouter_B` 1057, `tailscale_A`
  325 — exact match.
- Replicate completeness across the 898 cells: **893 both runs scored, 2
  exactly one run scored, 3 neither run scored** — exact match.
- The 8 unscored (exhausted) logical calls match SPEC.md's list exactly:
  `openrouter_B`/gemini `n012` r2+r3, `n036` r2+r3, `b326` r2+r3, `b373` r2;
  `tailscale_A`/glm `b264` r2 — all confirmed at `n_attempts=5` (the retry
  ceiling), and confirmed **no other** logical call exceeds 5 attempts.
- `gemini_B` scored cells: 93 total, split **91 `google-vertex` / 2
  `google-ai-studio`** — exact match to SPEC.md.
- Parse status across all 1788 scored replicates: 1787 `ok`, 1
  `ok_conflict` — exact match to SPEC.md's integrity note.

No figure in this file was adjusted to match SPEC.md; every number above was
independently re-derived from the primary sources and happened to agree.

## Anomaly investigated and ruled out

**What we observed:** beyond the documented Gemini deviation, 5 additional
scored cells (`google/gemma-4-26b-a4b-it`: 2 in `openrouter_A`, 3 in
`openrouter_B` — the `b326`/r2, `n113`/r2, `n039`/r2, `b432`/r2, `b304`/r3
logical calls) show `response_json.provider == "Google"`. Every other Gemma
call in the dataset is served by a third-party provider (DeepInfra,
Parasail, AkashML, CoreWeave, SiliconFlow, NextBit), so a Gemma call landing
on Google's own infrastructure initially looked like it might be a second,
undocumented instance of the Gemini/Vertex temperature-drop pattern.

**Why it turned out not to be a deviation** (confirmed by the team lead,
verified against the OpenRouter endpoints API and the DB):

1. Endpoint capability differs by model. For `google/gemma-4-26b-a4b-it`,
   the Google endpoint (tag `google-vertex/global`) **does** support
   `temperature`/`top_p`. For `google/gemini-3.6-flash`, all three
   Google/Vertex endpoints (`global`, `flex`, `priority`) do **not** —
   that gap is exactly what causes the documented Gemini deviation.
2. All 5 Gemma calls were issued with the same frozen provider block as
   every other call in the study: `require_parameters=1`, no `order`
   override, `temperature=0`, `top_p=1.0`. Verified per cell (`b326` r2,
   `n113` r2, `n039` r2, `b432` r2, `b304` r3).

Because `require_parameters=1` forces OpenRouter to only route to an
endpoint that can honour the declared parameters, and Google's Gemma
endpoint can honour `temperature=0`, OpenRouter routing these 5 calls to
Google is the integrity guarantee **working as designed** — not a lapse in
it. `temperature=0` was honoured for all 5.

**General principle** (this is what makes the Gemini deviation legible by
contrast): a `Google`/`Vertex` response is only a deviation for models where
the Vertex endpoint lacks `temperature`/`top_p` support. **Provider identity
alone does not indicate a deviation — parameter compatibility does.**
`google/gemini-3.6-flash` fails that compatibility check on Vertex;
`google/gemma-4-26b-a4b-it` passes it.

**Conclusion / data impact:** none. These 5 cells are fully compliant with
the frozen protocol. Our export's default of `upstream` empty and
`temperature_honoured=TRUE` for these rows was already correct and is
unchanged — only this documentation was updated. To re-check independently:

```sql
SELECT lc.id, e.name, q.question_id, lc.model, lc.run_index,
       json_extract(pa.request_json,'$.provider.require_parameters') as require_params,
       json_extract(pa.request_json,'$.provider.order') as order_override,
       json_extract(pa.request_json,'$.temperature') as temperature,
       json_extract(pa.request_json,'$.top_p') as top_p,
       json_extract(pa.response_json,'$.provider') as resp_provider
FROM logical_calls lc
JOIN experiments e ON lc.experiment_id = e.id
JOIN questions q ON lc.question_id = q.id
JOIN provider_attempts pa ON pa.logical_call_id = lc.id
JOIN scores sc ON sc.logical_call_id = lc.id
JOIN parsed_answers p ON sc.parsed_answer_id = p.id AND p.provider_attempt_id = pa.id
WHERE lc.model = 'google/gemma-4-26b-a4b-it'
  AND json_extract(pa.response_json,'$.provider') = 'Google';
```
