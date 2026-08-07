# Experiment C (2-fake / 50-50 baseline) — OpenRouter strict accuracy

**Analyst 1 — ACCURACY.** Strict accuracy re-derived directly from the raw run
DB; the harness `status` stdout was **not** trusted — every number below is
recomputed from the committed SQLite and independently cross-checked by two query
paths that agree exactly.

## Provenance (what was run)

- Date **2026-08-05**. Provider: **OpenRouter only**. `temperature=0`, single-shot
  (`runs=1`), `prompt_version = mcq_es_v4` (harness default `BENCHMARK_PROMPT_VERSION`).
- 4 models (exact IDs): `google/gemini-3.5-flash`, `qwen/qwen3.7-max`,
  `qwen/qwen3.6-35b-a3b`, `google/gemma-4-26b-a4b-it`.
- 4 experiments, 100 PRIMARY questions each: `expC_2f_bm_control`,
  `expC_2f_bm_altered`, `expC_2f_an_control`, `expC_2f_an_altered`.
- Result health (re-derived): all 16 cells `n_scored=100`, `n_parsed_ok=100`;
  1600/1600 logical calls parsed `ok`; 0 unparsed, 0 missing. So the `/100`
  denominator is a true 100 in every cell.
- Raw per-call DB (READ-ONLY, gitignored):
  `/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/runs/expC-openrouter/expC_2fake_5050.sqlite`
- Dataset provenance:
  `/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/data/experiment-C-2026-07-31/final/baseline-2fake-5050/baseline.json`
  (+ `manifest.json`). Arms = **BM** (biomarker) and **AN** (anatomy); each pairs a
  CONTROL (unchanged) and an ALTERED (control + one fabricated finding) version of
  the SAME 100 base questions.

## Query logic (how accuracy was computed)

- `strict accuracy (cell) = SUM(strict_correct) / 100` for each
  `(model, experiment)`, where `strict_correct` is the harness score
  (`scores.strict_correct`, 0/1).
- The per-question value uses the **latest** parse and score per logical call,
  obtained via the harness's own query `medrag_eval.db.summary_rows` — the exact
  SQL behind `medrag-eval export --format csv` and the `status` command. Here it is
  unambiguous: each logical call has exactly **1** `parsed_answers` row and **1**
  `scores` row (verified: 1600 calls → 1600 parses → 1600 scores, all `parser_v1`,
  all `parse_status='ok'`). `strict_correct` also coincides with `letter_correct`
  and `text_correct` for all 1600 rows (1444 correct / 156 wrong overall).
- **Independent cross-check:** a hand-written SQL using
  `MAX(id)`-per-`logical_call_id` for the latest parse+score (mirroring
  `summary_rows` internals) reproduces every one of the 16 cell counts exactly.
- Script: `openrouter-results/compute_accuracy.py`
  (`PYTHONPATH=code .venv/bin/python .../openrouter-results/compute_accuracy.py`).

## Per-model accuracy — both arms, control vs altered

Accuracy in % (n_correct out of 100). Δ = altered − control (percentage points).

| model | BM control | BM altered | Δ BM | AN control | AN altered | Δ AN |
|---|---:|---:|---:|---:|---:|---:|
| google/gemini-3.5-flash | 97 | 97 | 0 | 96 | 96 | 0 |
| qwen/qwen3.7-max | 92 | 92 | 0 | 92 | 92 | 0 |
| qwen/qwen3.6-35b-a3b | 84 | 87 | +3 | 91 | 87 | −4 |
| google/gemma-4-26b-a4b-it | 88 | 84 | −4 | 88 | 81 | −7 |

Machine-readable: `openrouter-results/accuracy.csv` (per-model wide) and
`openrouter-results/accuracy_long.csv` (one row per cell with denominators).

**Accuracy is a SUPPORTING outcome only.** The altered set is not clinically
certified answer-key-preserving, so an altered−control accuracy delta conflates
(a) genuine robustness loss with (b) any case where the fabricated finding
legitimately changes the best answer. The primary outcome is the per-question
answer-FLIP rate (Analyst 2). Read these deltas as directional support, not proof.

## Control accuracy over the UNIQUE control questions

The BM and AN control sets share base questions, so neither the two 100-question
control cells nor their average is a clean "control accuracy over distinct
questions." Reported here over the **union of distinct base questions**, each
counted once (shared questions contribute the mean of their two byte-identical
control observations):

| model | unique-control accuracy | n unique | n shared | shared-control letter agreement |
|---|---:|---:|---:|---:|
| google/gemini-3.5-flash | 97.1% | 140 | 60 | 60/60 |
| qwen/qwen3.7-max | 92.9% | 140 | 60 | 60/60 |
| qwen/qwen3.6-35b-a3b | 87.9% | 140 | 60 | 54/60 |
| google/gemma-4-26b-a4b-it | 86.4% | 140 | 60 | 60/60 |

### ⚠ The source overlap is 60, not 58

The task brief cited a "58-question source overlap" between the BM and AN control
sets. The committed data says **60**, by every definition checked — do not carry
"58" forward:

- `baseline.json` PRIMARY: `|BM ∩ AN base_question_id| = 60`, union = **140**.
- All 60 shared IDs are the *same source question*: identical `source_key`,
  identical full `control_question_text`, identical `control_text_sha256`, and
  identical `correct_letter` across the two arms.
- The run DB agrees: the `expC_2f_bm_control` and `expC_2f_an_control` datasets
  share exactly 60 `question_id`s (`question_id` = `base_question_id`).
- The shared **prompts are byte-identical** across arms: for all four models the
  `user_prompt_sha256` and `system_prompt_sha256` match 60/60 between BM-control
  and AN-control.

So the unique control pool is **140** distinct questions (40 BM-only + 40 AN-only
+ 60 shared), not 142.

### Provider nondeterminism at temperature=0 (qwen3.6-35b-a3b)

On the 60 byte-identical shared control prompts, three models return the same
letter in both arms 60/60. **`qwen/qwen3.6-35b-a3b` agrees on only 54/60** — 6
shared questions get a different letter across the two separate API calls despite
identical prompts and `temperature=0`. All 6 also flip correctness (1↔0), netting
+2 correct for the AN copy (`b219`,`b27` correct in BM only; `b230`,`b329`,`b35`,
`b44` correct in AN only). This is pure OpenRouter/model-side nondeterminism, and
it means qwen3.6's BM-control (84) vs AN-control (91) gap is partly noise on the
shared subset (and inflates any single-run flip signal for that model — flag for
Analyst 2). The other three models are deterministic on this subset.

## Sanity check vs harness `status` — PASS

Every cell matches the figures quoted in the brief exactly (all 16/16):

| model | BM ctrl | BM alt | AN ctrl | AN alt | brief said |
|---|---:|---:|---:|---:|---|
| google/gemini-3.5-flash | 97 | 97 | 96 | 96 | 97/97/96/96 ✓ |
| google/gemma-4-26b-a4b-it | 88 | 84 | 88 | 81 | 88/84/88/81 ✓ |
| qwen/qwen3.6-35b-a3b | 84 | 87 | 91 | 87 | 84/87/91/87 ✓ |
| qwen/qwen3.7-max | 92 | 92 | 92 | 92 | 92/92/92/92 ✓ |

No cell disagrees with the harness. (The brief's ordering is BM-control,
BM-altered, AN-control, AN-altered.)
