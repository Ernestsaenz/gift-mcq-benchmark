# Data dictionary — ab520 incorrect-cell triplicate run DB

Covers the live run DB (schema extracted via `sqlite3 "file:<path>?mode=ro"
".schema"` on 2026-08-07, read-only per SPEC.md):

```text
data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite
```

Six tables, in dependency order (each references the one above it via
`REFERENCES ... ON DELETE CASCADE`, except `scores.parsed_answer_id` and
`parsed_answers.provider_attempt_id` which are described per-row below).

## `datasets`

The two flattened input CSVs, loaded once at prep time (`prepare_replicates.py`).

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PK | Surrogate key. |
| `name` | TEXT, unique | e.g. `ab520_adjusted_A_replication`, `ab520_adjusted_B_replication` — one row per condition (A, B). |
| `source_xlsx_path` | TEXT | Despite the column name (a holdover from the harness's original Excel-only ingestion path), this holds the path actually loaded — here the condition CSVs: `inputs/adjusted-500-condition-{A,B}.csv`. |
| `created_at` | TEXT | ISO-8601 UTC timestamp of ingestion, `2026-08-05T16:16:4{8,9}Z` for both rows — consistent with `preparation-summary.json`'s `prepared_at_utc`. |
| `row_count` | INTEGER | 500 for both — the 500-question item bank, not the 898/1796 replicate-cell counts (those are downstream, per logical call). |

Two rows: `id=1` → condition A (500 rows), `id=2` → condition B (500 rows).
`tailscale_A` reuses `dataset_id=1` (condition A) — TailScale/GIFT's arm
runs against the same question set as `openrouter_A` (see `experiments`
below); it is a different **provider/route**, not a different **condition**.

## `questions`

One row per (dataset, question) — the flattened MCQ item, carrying full exam
provenance.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PK | Surrogate key, referenced by `logical_calls.question_id`. |
| `dataset_id` | INTEGER FK → `datasets.id` | Which condition (A/B) this question row belongs to. |
| `question_id` | TEXT | The stable item identifier used throughout this study, e.g. `b101`, `b323`, `b373`, `n012`, `n036`. Matches the run-1 CSV's `question_id` column and the ledger's `question_id`/`source_key`-adjacent identity. |
| `region`, `year`, `specialty`, `exam_part`, `question_number` | TEXT/INTEGER | Original exam metadata (Spanish regional MIR-style exam bank): e.g. region `Andalucía`, year `2021`, `exam_part='cuestionario-teorico'`, `question_number=373`. Together with `source_key` in the CSVs, this triple (region\|year\|exam_part\|question_number) is the exam-provenance identity. |
| `question_text`, `option_a..d`, `correct_letter`, `correct_option_text` | TEXT | The MCQ stem, four options, and keyed answer — the actual content sent to the model and used for scoring. |
| `source_row_json` | TEXT (JSON) | Full original flattened-CSV row for this question, verbatim, including fields not otherwise broken out as columns here (`content_sha256`, `raw_form_sha256`, `flags`, `page_in_exam_pdf`, `source_exam_pdf`, `source_answer_key_pdf`, `source_results_path`, `source_run1_cell_key`, etc.) — this is how the run-1 provenance chain (which database/CSV each question came from) survives into this DB without a dedicated column per field. |
| `created_at` | TEXT | Ingestion timestamp, matches `datasets.created_at` for the parent dataset. |

Unique constraint: `(dataset_id, question_id)` — a question appears at most
once per condition.

## `experiments`

One row per **arm** (not per condition) — the harness's unit of "a run of a
prompt/model/provider configuration over a dataset."

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PK | Surrogate key. |
| `name` | TEXT, unique | `ab520_incorrect_triplicates_or_A_20260805`, `..._or_B_20260805`, `..._ts_A_20260805` — maps 1:1 to SPEC.md's arms `openrouter_A`, `openrouter_B`, `tailscale_A`. |
| `dataset_id` | INTEGER FK → `datasets.id` | `or_A`→1(A), `or_B`→2(B), `ts_A`→1(A) — confirms `tailscale_A` runs condition A content over the GIFT/TailScale route, as SPEC.md's arm table states. |
| `prompt_version` | TEXT | `mcq_es_v4` for all three arms (shared instruction set per commit `bcf362a`). |
| `config_json` | TEXT (JSON) | Run configuration, e.g. `{"condition":"A","replicate_run_indices":[2,3],"scope":"strict_incorrect_run1_cells_only","source_results_sha256":"ce91b3f3...","source_run_index":1,"tailscale_prompt_id":null,"tailscale_top_k":null}` — records the scoping decision (only run-1-incorrect cells), the frozen run indices, and a hash-pinned link back to the exact run-1 source CSV. `tailscale_prompt_id`/`tailscale_top_k` are non-null only for the `ts_A` experiment row. |
| `created_at` | TEXT | `2026-08-05T16:16:49Z` for all three — created together at prep time, before any calls were issued. |

## `logical_calls`

The unit SPEC.md calls a "logical call": one (question, provider, model,
run_index) cell that may be attempted more than once.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PK | Surrogate key. This is the id used throughout `INTEGRITY_CHECKS.md` (e.g. `logical_call_id 485`). |
| `experiment_id` | INTEGER FK → `experiments.id` | Which arm. |
| `question_id` | INTEGER FK → `questions.id` | Which item (note: this is the DB surrogate key, distinct from `questions.question_id` the text identifier like `b101`). |
| `provider` | TEXT | `openrouter` or `tailscale_medical_rag`. Per SPEC.md's note, Vertex is an upstream *inside* `openrouter`, not a distinct value here — grouping by this column is correct even for the 91 Vertex-routed cells. |
| `model` | TEXT | One of `google/gemini-3.6-flash`, `google/gemma-4-26b-a4b-it`, `qwen/qwen3.6-35b-a3b`, `z-ai/glm-5.2`. |
| `run_index` | INTEGER | `2` or `3` only in this DB (run 1 lives in the separate replacement-22 database/export; this DB only ever holds the replicate runs). |
| `prompt_version` | TEXT | `mcq_es_v4`, echoed from the experiment. |
| `system_prompt_sha256`, `user_prompt_sha256` | TEXT | Hash of the rendered system/user prompt actually sent — lets an auditor confirm the exact prompt text without storing it redundantly per attempt. |
| `created_at` | TEXT | When this logical call was first created (i.e., first attempted), not when the experiment was created. |

Unique constraint: `(experiment_id, question_id, provider, model, run_index,
prompt_version)` — this is the "logical call identity"; a second attempt at
the same cell reuses the same `logical_calls` row and adds a new
`provider_attempts` row instead.

## `provider_attempts`

One row per actual HTTP call issued for a logical call — the raw record of
what was sent and what came back, including failures.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PK | Surrogate key. |
| `logical_call_id` | INTEGER FK → `logical_calls.id` | Which cell this attempt belongs to. |
| `attempt_index` | INTEGER | 1-based sequence within the logical call; the 5-attempt ceiling (INTEGRITY_CHECKS.md §4) is `MAX(attempt_index)` per `logical_call_id`. |
| `prompt_version`, `system_prompt_sha256`, `user_prompt_sha256` | TEXT (nullable) | Per-attempt copies of the prompt identity fields (allows detecting prompt drift across attempts of the same call, though none is expected). |
| `request_sha256` | TEXT | Hash of the exact outbound request. Central to INTEGRITY_CHECKS.md §6: two attempts of the same logical call with different `request_sha256` values mean the request itself changed (e.g. a `provider_routing` override), not merely a retry of an identical request. |
| `request_json` | TEXT (JSON) | The full outbound payload. For OpenRouter, `$.provider.order[0]` reveals a pinned upstream (e.g. `google-vertex`) when the protocol-deviation flag was used; absent/null for the frozen default (`require_parameters: true`, any upstream). |
| `request_headers_json` | TEXT (JSON, nullable) | Outbound HTTP headers (e.g. TailScale's `X-Prompt-ID`/`X-Top-K`). |
| `prompt_id`, `top_k` | INTEGER (nullable) | TailScale-only routing controls (see `code/medrag_eval/providers/base.py`'s `ProviderRequest.prompt_id`/`top_k`); null for OpenRouter attempts. |
| `status_code` | INTEGER | HTTP status. `200` = accepted; `429` throughout this DB = rate-limited (the dominant failure mode driving the multi-hash cells in INTEGRITY_CHECKS.md §6). |
| `response_body` | TEXT | Raw response body, if any. |
| `response_json` | TEXT (JSON, nullable) | Parsed response. `$.provider` distinguishes `"Google AI Studio"` from `"Google"` (Vertex) for the affected gemini_B cells — the machine-detectable signature SPEC.md and `STATUS.md` rely on. |
| `latency_ms` | INTEGER | Wall-clock latency for the call. |
| `finish_reason` | TEXT | e.g. `stop`. |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | INTEGER | Token accounting from the provider response. |
| `error_type`, `error_message` | TEXT (nullable) | Populated on failed attempts, e.g. `error_type='rate_limited'` for every 429 in this DB. |
| `created_at` | TEXT | Attempt timestamp — the field used to reconstruct the attempt timeline in INTEGRITY_CHECKS.md §6 (e.g. distinguishing the 2026-08-05 initial rate-limited attempts from the 2026-08-06 Vertex-routed recovery attempt). |

Unique constraint: `(logical_call_id, attempt_index)`.

## `parsed_answers`

One row per attempt that was parsed for an answer (i.e., attempts that
produced a response worth parsing; failed/errored attempts typically have no
corresponding row here, or the parser recorded a null/attempted state — the
only guarantee enforced by schema is `parsed_answers.provider_attempt_id` is
nullable via `ON DELETE SET NULL`).

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PK | Surrogate key. |
| `logical_call_id` | INTEGER FK → `logical_calls.id` | Convenience denormalization; also reachable via `provider_attempt_id`. |
| `provider_attempt_id` | INTEGER FK → `provider_attempts.id`, nullable, `ON DELETE SET NULL` | Which raw attempt this parse came from. |
| `parser_version` | TEXT | Parser implementation version. |
| `parse_status` | TEXT | `ok` (1,787 rows) or `ok_conflict` (1 row) in this DB — see INTEGRITY_CHECKS.md §5. `ok_conflict` means the parser found a usable answer but flagged an internal inconsistency (see `letter_text_conflict` below), not that parsing failed outright. |
| `parse_method` | TEXT | How the answer was extracted (e.g. structured JSON schema field vs. free-text regex fallback). |
| `selected_letter_raw`, `selected_option_text_raw` | TEXT | Raw extracted values before normalization. |
| `selected_letter`, `selected_option_text` | TEXT | Normalized answer letter/text used for scoring. |
| `exact_text_match` | INTEGER (0/1) | Whether the model's stated option text exactly matched one of the four provided options verbatim. |
| `letter_text_conflict` | INTEGER (0/1) | Whether the selected letter and the selected option text disagree (i.e., the model said "b" but wrote out option c's text) — this is what produces `parse_status='ok_conflict'` when set. |
| `notes` | TEXT (nullable) | Free-text parser notes. |
| `created_at` | TEXT | Parse timestamp. |

## `scores`

One row per parsed answer that was scored against the keyed correct answer —
the final, authoritative correctness record for a logical call.

| Column | Type | Meaning |
| --- | --- | --- |
| `id` | INTEGER PK | Surrogate key. |
| `logical_call_id` | INTEGER FK → `logical_calls.id` | Which cell. A logical call has at most one `scores` row in this DB (1,788 scores / 1,796 logical calls — 8 unscored, all exhausted at the 5-attempt ceiling per SPEC.md). |
| `parsed_answer_id` | INTEGER FK → `parsed_answers.id` | Which parse produced this score — the join used in INTEGRITY_CHECKS.md §6 to prove each score's request-hash provenance is unambiguous even for the 3 multi-hash logical calls. |
| `correct_letter`, `correct_option_text` | TEXT | Copied from the source question at scoring time (redundant with `questions.correct_letter`/`correct_option_text`, kept here so a score row is self-describing). |
| `letter_correct`, `text_correct` | INTEGER (0/1) | Whether the selected letter matches, and separately whether the selected text matches, the keyed answer. |
| `strict_correct` | INTEGER (0/1) | The primary correctness metric used throughout this study (e.g. the run-1 CSV's `strict_correct` column that defines the 898-cell selection). Requires letter and text to agree with each other and with the key (exact semantics defined in the harness's scoring code, not reproduced here). |
| `lenient_correct` | INTEGER (0/1) | A looser correctness metric (e.g. accepting a letter match alone). |
| `answer_text_matches_provided` | INTEGER (0/1) | Whether the model's stated option text matches one of the four options it was actually given (sanity check independent of correctness). |
| `created_at` | TEXT | Scoring timestamp. |

## Indexes

`idx_questions_dataset_number`, `idx_logical_calls_identity`,
`idx_provider_attempts_logical`, `idx_parsed_answers_logical`,
`idx_scores_logical` — all support the natural join paths above
(`dataset→question`, the logical-call identity tuple, and the
attempt/parse/score chains keyed by `logical_call_id`). No additional
semantics beyond what the referenced columns already describe.

---

## Run-1 CSV → this schema: column mapping

The run-1 source is a **different** database's flattened export (the
replacement-22 6,000-cell result), not a dump of this DB — it predates this
DB by design (this DB only holds runs 2–3 for the 898 cells run-1 marked
incorrect). Its 78 columns are a denormalized, single-row-per-cell view that
mixes: (a) fields with a direct equivalent in the schema above, (b) fields
that are exam/workbook provenance carried from *before* any DB ingestion
(and, in this DB, would live inside `questions.source_row_json` rather than
as a dedicated column), and (c) fields specific to the replacement-22
package's own reconciliation logic that have no equivalent object in this
schema at all. Grouped below; run-1 CSV header read from
`exports/benchmark-6000-cell-results-adjusted.csv`.

### (a) Direct equivalents

| Run-1 CSV column | This schema |
| --- | --- |
| `arm` | `experiments.name` (suffix) / SPEC.md arm label — `openrouter_A`/`openrouter_B`/`tailscale_A` |
| `provider` | `logical_calls.provider` |
| `model` | `logical_calls.model` |
| `run_index` | `logical_calls.run_index` (run-1 CSV rows are all `run_index=1`; this DB only ever has 2 or 3) |
| `question_id` | `questions.question_id` |
| `question_text`, `option_a..d`, `correct_letter`, `correct_option_text` | `questions.question_text`, `questions.option_a..d`, `questions.correct_letter`, `questions.correct_option_text` |
| `region`, `year`, `specialty`, `exam_part`, `question_number` | `questions.region`, `.year`, `.specialty`, `.exam_part`, `.question_number` |
| `prompt_version` | `logical_calls.prompt_version` / `experiments.prompt_version` |
| `selected_letter`, `selected_option_text` | `parsed_answers.selected_letter`, `.selected_option_text` |
| `parse_status`, `parse_method` | `parsed_answers.parse_status`, `.parse_method` |
| `strict_correct`, `lenient_correct`, `letter_correct`, `text_correct`, `answer_text_matches_provided` | `scores.strict_correct`, `.lenient_correct`, `.letter_correct`, `.text_correct`, `.answer_text_matches_provided` |
| `attempt_count` | `COUNT(*)` from `provider_attempts` grouped by `logical_call_id` |
| `latest_attempt_index`, `latest_status_code`, `latest_latency_ms`, `latest_finish_reason`, `latest_error_type` | The `provider_attempts` row with `MAX(attempt_index)` for that logical call — `.attempt_index`, `.status_code`, `.latency_ms`, `.finish_reason`, `.error_type` |
| `request_sha256`, `response_sha256` | `provider_attempts.request_sha256` (and a hash of `response_body`/`response_json` for `response_sha256`, which this schema does not pre-compute as a column) |
| `prompt_tokens`, `completion_tokens`, `total_tokens` | `provider_attempts.prompt_tokens`, `.completion_tokens`, `.total_tokens` |
| `logical_call_id` | `logical_calls.id` (values are **not** comparable across the two databases — surrogate keys are per-DB) |
| `result_database`, `result_experiment` | `experiments.name`, and the DB file path itself (this schema has no self-referential "which DB am I" column; that provenance is carried externally, e.g. in `preparation-summary.json`) |

### (b) Exam/workbook provenance — carried in `questions.source_row_json`, not dedicated columns

`source_key`, `origin`, `source_workbook`, `source_workbook_sha256`,
`source_excel_row`, `content_sha256`, `raw_form_sha256`,
`source_form_input_char_count`, `flags`, `page_in_exam_pdf`,
`source_exam_pdf`, `source_answer_key_pdf`, `negated_stem`,
`context_ids`, `selection_score`. These describe where the question came
from *before* ingestion into any harness DB. This schema stores the
equivalent information verbatim inside `questions.source_row_json` (the
full original CSV row as JSON) rather than as first-class columns — see the
sample keys observed in this DB's `source_row_json` (§`questions` above):
`content_sha256`, `raw_form_sha256`, `flags`, `page_in_exam_pdf`,
`source_exam_pdf`, `source_answer_key_pdf` are present there verbatim,
confirming the mapping.

### (c) Replacement-22-specific fields with no equivalent in this schema

`cell_key`, `condition`, `score_status`, `status_reason`, `prior_experiment`,
`prior_database`, `source_csv`, `score_origin`, `attempt_history_json`,
`exact_input_match_db`, `final_execution_status`, `effective_model`,
`request_user_content_char_count`, `failure_class`, `replacement_id`,
`replaces_question_id`, `candidate_id`, `failure_group`, `record_role`,
`replacement_manifest_sha256`, `replacement_cell_ledger_sha256`. These
belong to the replacement-22 package's specific reconciliation problem (merging
5,736 retained cells with 264 replacement cells, tracking which of the 22
rejected-then-replaced questions each row concerns) and have no
corresponding table/column in this triplicate-run schema, which was never
part of that reconciliation. Recorded here as **not mappable**, per
SPEC.md's "never invent a number" standard, rather than guessing an
equivalent.

### New in the frozen replicate ledger (not in the run-1 CSV at all)

`manifests/frozen-replicate-cell-ledger.csv`'s columns
`run1_cell_key`, `run1_selected_letter`, `run1_correct_letter`,
`run1_request_sha256`, `run1_response_sha256`, `run1_result_database`,
`run1_result_experiment`, `input_fields_sha256`, `target_key`, `status` are
the ledger's own bridging columns between the two databases — they carry a
snapshot of the run-1 cell's identity/hashes forward into this DB's prep
step, and are the mechanism `execute_replicates.py`/`prepare_replicates.py`
use to guarantee the 898×2=1,796 frozen selection matches run-1 exactly
(verified in INTEGRITY_CHECKS.md §2). They do not correspond to columns in
this DB's schema either; they are ledger-only, input-side provenance.
