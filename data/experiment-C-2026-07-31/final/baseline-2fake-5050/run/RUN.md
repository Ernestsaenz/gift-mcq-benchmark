# Experiment C — 2-Fake/50-50 Baseline — medrag-eval run recipe

Builder C's deliverable: 4 run-ready workbooks derived from
`../baseline.json` (built by `../build_baseline.py`, itself derived from the locked
mechanical-130 workbooks and `balanced-flat-A.xlsx`; none of those inputs were
touched), plus the exact `medrag-eval` recipe to benchmark them and compute the
primary outcome — the CTRL→ALT answer-**flip rate**, not accuracy — per model x arm,
with cluster-robust statistics.

Builder C made **no network calls and no model/API calls**. Steps 0–2 and 4–5 below
were actually executed against a throwaway sqlite (deleted afterward) to validate the
workbooks and the analysis script; step 3 (the only step needing credentials and a
live GIFT/OpenRouter endpoint) is written out exactly but was **not** run.

## What's here

| file | rows | question_text | contents |
|---|---:|---|---|
| `expC-bm-control.xlsx` | 100 | control | biomarker arm, no fabrication |
| `expC-bm-altered.xlsx` | 100 | altered | biomarker arm, 1 of 2 kept fakes inserted |
| `expC-an-control.xlsx` | 100 | control | anatomy arm, no fabrication |
| `expC-an-altered.xlsx` | 100 | altered | anatomy arm, 1 of 2 kept fakes inserted |
| `analyze_flip_rate.py` | — | — | CTRL vs ALT pairing → cluster-robust flip rate |
| `../build_run_workbooks.py` | — | — | builds the 4 workbooks from `../baseline.json` |

Each workbook is a single-sheet (`questions`) file whose active sheet has exactly the
17 columns `code/medrag_eval/excel_io.py` (`REQUIRED_COLUMNS`) requires, in order:

```
question_id, region, year, specialty, exam_part, question_number, question_text,
option_a, option_b, option_c, option_d, correct_letter, correct_option_text,
flags, page_in_exam_pdf, source_exam_pdf, source_answer_key_pdf
```

...plus 3 extra columns appended after those 17: `cluster`, `fabricated_entity`,
`variant_id`. The importer only reads `REQUIRED_COLUMNS` by header name
(`_required_column_indexes` in `excel_io.py`) and ignores anything else in the header
row, so the extras are inert for import purposes. They exist so step 5 can recover
`cluster` per `question_id` without re-deriving it from `baseline.json` — the
`medrag_eval` sqlite schema (`code/medrag_eval/migrations.py`) has no cluster column,
so this is the only place that field survives past import. `question_id` =
`base_question_id`; both are unique within every file. Only PRIMARY rows are
included — the 30 RESERVE rows/arm are intentionally excluded (per the task's "just a
reserve for later" framing).

## Validation performed (Builder C)

1. **Direct importer check** — `medrag_eval.excel_io.import_questions_from_workbook`
   against all 4 files: 100 questions each, **0 warnings**, no duplicate
   `question_id`, `correct_option_text == option_[correct_letter]` for all 400 rows.
2. **Full harness check** — `init-db` + `import-questions` (the actual CLI) into a
   throwaway `run/_tmp.sqlite`: `Imported 100 scoreable questions into dataset
   <name>` x4, row_count == actual imported row count for all 4 datasets, 0
   correctness mismatches, 0 blank `question_text`, 0 invalid `correct_letter`, 100
   distinct `question_id` per dataset. Control/altered question-id sets are identical
   within each arm, and every one of the 100 paired rows has a *different*
   `question_text` between control and altered (i.e. the insertion always changed the
   text). `run/_tmp.sqlite` (+ `-wal`/`-shm`) was deleted after.
3. **Provenance spot check (all 400 rows, not a sample)** — recomputed
   `sha256(question_text)` for every row of all 4 workbooks and compared against
   `control_text_sha256` / `altered_text_sha256` in `../baseline.json` for the
   matching `base_question_id`: **0 mismatches**, text and hash both exact.
4. **50/50 split** — `../baseline.json` `arms.{BM,AN}.primary_counts`: BM =
   `{colangiomirina-8: 50, fibroquelina-X3: 50}`, AN = `{saco orfalónico: 50, órgano
   liradónico: 50}`. Exact 50/50 for both arms, confirming `../assignment_report.md`'s
   `exact_5050_achieved: True`.
5. **`analyze_flip_rate.py` smoke test** — seeded synthetic `logical_calls` /
   `provider_attempts` / `parsed_answers` / `scores` rows (2 fake provider/model
   pairs, a designed-in ~20% flip rate, 2 forced-unparsed rows) into a throwaway
   sqlite already carrying the real `expC-bm-control` / `expC-bm-altered` imported
   datasets, then ran the script against it: it correctly reported `n_paired=100`,
   `n_scored=98` (2 excluded as unparsed), `flip_rate≈0.2041` (matching the injected
   design exactly: 20 flips / 98 scored), sane cluster-robust CIs, `n_clusters=32`
   (one of BM's 33 clusters was a singleton that happened to land on an excluded
   row). **This confirms the script runs correctly end-to-end; it is not, and must
   not be read as, a real result** — no real benchmark calls exist yet. The
   throwaway db and the synthetic seeding script (not a deliverable) were discarded.

## Step-by-step recipe

### 0. Environment

- Python: `/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/.venv/bin/python`
  — has `openpyxl` and the project's `analysis` extras (`numpy`, `pandas`, `scipy`,
  `statsmodels`) already installed; `analyze_flip_rate.py` needs the last one.
- Run everything from the repo root
  (`/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq`):
  `Settings.from_env()` reads `Path.cwd()/.env`, and every default path (`runs/`,
  `DEFAULT_DB_PATH`) is relative to cwd.
- `PYTHONPATH=code` for every `medrag_eval.cli` invocation and for
  `analyze_flip_rate.py` (it imports `medrag_eval.db` directly so its summary query
  can never drift from what `medrag-eval export` produces).
- Step 3 needs `.env` with `GIFT_API` / `GIFT_EMAIL` / `GIFT_PASSWORD` and/or
  `OPENROUTER_API_KEY` (see `code/harness_README.md`). Nothing else here needs
  credentials or network.

### 1. `init-db` into `runs/` (never `data/`)

Use a **new, distinctly-named** db so this baseline never collides with the existing
`runs/medrag_eval.sqlite` (the committed 2026-07-31 balanced-mcq experiment's db):

```bash
cd /Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq
DB=runs/expC_2fake_5050.sqlite
PYTHONPATH=code .venv/bin/python -m medrag_eval.cli init-db --db "$DB"
```

### 2. Import each of the 4 workbooks as its own dataset

```bash
RUN=data/experiment-C-2026-07-31/final/baseline-2fake-5050/run
for pair in \
  "expC-bm-control:$RUN/expC-bm-control.xlsx" \
  "expC-bm-altered:$RUN/expC-bm-altered.xlsx" \
  "expC-an-control:$RUN/expC-an-control.xlsx" \
  "expC-an-altered:$RUN/expC-an-altered.xlsx" ; do
  name="${pair%%:*}"; path="${pair#*:}"
  PYTHONPATH=code .venv/bin/python -m medrag_eval.cli import-questions \
    --dataset "$name" --xlsx "$path" --db "$DB"
done
```

Expect `Imported 100 scoreable questions into dataset <name>` x4 with no `warning:`
lines — exactly what Builder C observed running this against the throwaway db (see
Validation above).

### 3. Run each dataset as its own experiment, single-shot, per model — NOT EXECUTED

This needs network + live credentials, which this task forbids, so it is written out
but not run. It mirrors the exact 4-model roster and provider handling already used
for the 2026-07-31 balanced-mcq A/B experiment this baseline descends from
(`data/experiment-31-07-26/run_lib.sh`, `run_gift.sh`, `run_openrouter.sh`) and the
"typical workflow" dry-run-first convention in `code/harness_README.md`.

Models (same 4 on both providers so the two arms stay directly comparable):

```
google/gemini-3.6-flash
z-ai/glm-5.2
qwen/qwen3.6-35b-a3b
google/gemma-4-26b-a4b-it
```

`--prompt-version` defaults to `BENCHMARK_PROMPT_VERSION = "mcq_es_v4"`
(`code/medrag_eval/prompting.py`) — already this project's shared Spanish
instruction set per this branch's most recent commit, so no flag is needed.
`--tailscale-prompt-id` defaults to the required `GIFT_MCQ_PROMPT_ID = 13`
(`code/medrag_eval/providers/tailscale_medical_rag.py`); any other value is rejected
by the CLI, so again no flag is needed unless you want to be explicit.

Optional smoke pass first (no full run commitment), per `code/harness_README.md`:

```bash
PYTHONPATH=code .venv/bin/python -m medrag_eval.cli run \
  --dataset expC-bm-control --experiment-name expC-bm-control \
  --provider-model tailscale_medical_rag:google/gemini-3.6-flash \
  --runs 1 --limit 2 --dry-run --db "$DB"
```

Full run, one `run` invocation per (dataset, provider) — kept separate because GIFT
and OpenRouter need different `--*-concurrency` settings and GIFT is known to
load-shed under concurrency on this harness:

```bash
DB=runs/expC_2fake_5050.sqlite
MODELS=(google/gemini-3.6-flash z-ai/glm-5.2 qwen/qwen3.6-35b-a3b google/gemma-4-26b-a4b-it)
GIFT_ARGS=(); for m in "${MODELS[@]}"; do GIFT_ARGS+=(--provider-model "tailscale_medical_rag:$m"); done
OR_ARGS=();   for m in "${MODELS[@]}"; do OR_ARGS+=(--provider-model "openrouter:$m"); done

for dataset in expC-bm-control expC-bm-altered expC-an-control expC-an-altered; do
  # GIFT arm: MUST be serialized. Concurrency > 1 makes GIFT shed load and return
  # errors as HTTP 200 bodies (~63% rate, per data/experiment-31-07-26/run_gift.sh).
  PYTHONPATH=code .venv/bin/python -m medrag_eval.cli run \
    --dataset "$dataset" --experiment-name "$dataset" --runs 1 \
    "${GIFT_ARGS[@]}" --tailscale-concurrency 1 --db "$DB"

  # OpenRouter arm: same experiment name — provider+model columns distinguish rows,
  # so both arms of one dataset live in a single experiment.
  PYTHONPATH=code .venv/bin/python -m medrag_eval.cli run \
    --dataset "$dataset" --experiment-name "$dataset" --runs 1 \
    "${OR_ARGS[@]}" --db "$DB"
done
```

A single pass will very likely **not** fully complete the GIFT arm (known
load-shedding). Gate completion on `status`, not on one pass's exit code — re-invoke
the same `run` command (it resumes: already-complete logical calls are skipped) until
converged, exactly like `data/experiment-31-07-26/run_lib.sh`'s `converge()` helper:

```bash
PYTHONPATH=code .venv/bin/python -m medrag_eval.cli status \
  --experiment-name "$dataset" --db "$DB"
# repeat `run` until: planned == completed, api_failed == 0, parse_failed == 0
```

### 4. Export

```bash
for dataset in expC-bm-control expC-bm-altered expC-an-control expC-an-altered; do
  PYTHONPATH=code .venv/bin/python -m medrag_eval.cli export \
    --experiment-name "$dataset" --format csv --db "$DB" \
    --out "$RUN/${dataset}_summary.csv"
done
```

### 5. Pair CTRL vs ALT by `question_id` → flip rate, cluster-robust

`flip rate is the primary outcome, not accuracy.` For each (provider, model),
`analyze_flip_rate.py` pairs every `question_id`'s control-condition
`selected_letter` with its altered-condition `selected_letter` and flags a flip when
they differ — but only when **both** sides parsed to a usable letter
(`parse_status` in `{"ok", "ok_conflict"}`); anything else is excluded and reported
separately (`n_excluded_unparsed`), never silently dropped. It re-joins `cluster` per
`question_id` from one of the arm's two run-ready workbooks (control or altered —
either has the same map) since that field never reaches the sqlite DB. It reports two
cluster-robust estimates, matching the convention already used for the sibling
2026-07-31 analysis
(`data/experiment-31-07-26/analysis/00_ORGANIZED_VIEW/06_exploratory/03_statistical_foundations/`):
an analytic CR1 sandwich SE + t-interval (`statsmodels.OLS(..., cov_type="cluster")`),
and a nonparametric whole-cluster percentile bootstrap 95% CI (10,000 resamples,
clusters resampled with replacement, carrying every item in a sampled cluster along).
It also reports `accuracy_control` / `accuracy_altered` as secondary context.

Run once per arm:

```bash
PYTHONPATH=code .venv/bin/python "$RUN/analyze_flip_rate.py" \
  --db "$DB" --arm BM \
  --control-experiment expC-bm-control --altered-experiment expC-bm-altered \
  --cluster-workbook "$RUN/expC-bm-control.xlsx" \
  --out "$RUN/flip_rate_BM.csv"

PYTHONPATH=code .venv/bin/python "$RUN/analyze_flip_rate.py" \
  --db "$DB" --arm AN \
  --control-experiment expC-an-control --altered-experiment expC-an-altered \
  --cluster-workbook "$RUN/expC-an-control.xlsx" \
  --out "$RUN/flip_rate_AN.csv"
```

Output columns: `arm, provider, model, n_paired, n_scored, n_excluded_unparsed,
n_excluded_no_cluster, n_missing_one_side, flip_rate, cluster_robust_se,
ci95_lo_analytic, ci95_hi_analytic, ci95_lo_bootstrap, ci95_hi_bootstrap,
n_clusters, accuracy_control, accuracy_altered, note`.

For reference, the cluster structure of the 100 PRIMARY rows (from
`../baseline.json`, `cluster` field — one cluster is one exam paper/case grouping):
BM has 33 distinct clusters (max size 20, 25 singletons); AN has 34 (max size 22, 27
singletons). Both are well within range for CR1/bootstrap cluster-robust inference,
same regime the sibling experiment already uses successfully.

## Notes / caveats

- The locked input workbooks and `balanced-flat-A.xlsx` were only read, never
  written, at every step of this task (Builder A/B's `build_baseline.py`, and
  Builder C's `build_run_workbooks.py` / `analyze_flip_rate.py` here).
- `runs/expC_2fake_5050.sqlite` does not exist yet — step 1 creates it. Never point
  `--db` at anything under `data/`; that tree is committed ground truth (same
  convention already stated in the repo root `README.md`).
- Extra columns `cluster`, `fabricated_entity`, `variant_id` in the 4 workbooks are
  ignored by the importer (confirmed in Validation above) and exist purely for
  downstream analysis; they do not change the 17-column import contract.
- Builder C ran no network calls and no model/API calls, per this task's SAFETY
  constraint. Step 3 is the only step that needs them and was left unexecuted by
  design — everything else in this document was actually run (against throwaway,
  now-deleted sqlite state) to validate the recipe end-to-end before handoff.
