# Experiment C — OpenRouter results (fabricated-entity robustness, 2-fake / 50-50 baseline)

**Self-contained traceability report.** Assembled from Analyst 1 (accuracy) and
Analyst 2 (answer-flip) outputs, plus harness raw + summary exports of every
experiment. All figures below trace to the committed run DB and the two analyst
CSV/MD deliverables; nothing here is estimated or hand-entered beyond copying
those verified numbers.

---

## 1. What Experiment C tests

Experiment C measures **fabricated-entity robustness**: does inserting one
**fabricated clinical finding** into an otherwise-unchanged Spanish
gastroenterology MCQ change the model's selected answer?

- **Design.** Each *base* question appears in two versions:
  - **CONTROL** — the unaltered question.
  - **ALTERED** — the identical CONTROL question **plus one fabricated finding**
    inserted into the stem. The four answer options and the answer key are left
    untouched by construction.
- **Two arms**, each over the same 100 base questions:
  - **BM = biomarker** — the fabricated entity is an invented biomarker
    (`fibroquelina-X3`, `colangiomirina-8`; 50/50 split).
  - **AN = anatomy** — the fabricated entity is an invented anatomical structure
    (`saco orfalónico`, `órgano liradónico`; 50/50 split).
- **This baseline** is the *2-fake / 50-50* condition: exactly two distinct
  fabricated entities per arm, split 50/50 across the 100 primary questions.

**Primary outcome = per-question ANSWER FLIP:** for a given
(model, base_question_id, arm), did the selected letter change between CONTROL
and ALTERED? **Accuracy is secondary/supporting** — the altered set is *not*
clinically certified answer-key-preserving, so accuracy deltas are directional
support, not proof (see Limitations).

---

## 2. Provenance (what was run)

| Field | Value |
|---|---|
| Date | **2026-08-05** (call timestamps 02:24:24Z -> 02:48:06Z, from the DB) |
| Provider | **OpenRouter only** |
| Temperature | **0** (`temperature=0.0` verified in the stored `request_json`) |
| Sampling | **single-shot** (`runs=1`) — no run-to-run replication |
| Prompt version | **`mcq_es_v4`** (harness default `BENCHMARK_PROMPT_VERSION`) |
| Models (4, exact IDs) | `google/gemini-3.5-flash`, `qwen/qwen3.7-max`, `qwen/qwen3.6-35b-a3b`, `google/gemma-4-26b-a4b-it` |
| Experiments (4) | `expC_2f_bm_control`, `expC_2f_bm_altered`, `expC_2f_an_control`, `expC_2f_an_altered` (100 primary questions each) |
| Result health | Every experiment **planned=400 completed=400 api_failed=0 parse_failed=0**; **1600/1600** logical calls; **100% parse success**; 0 unparsed, 0 missing (re-derived from the DB; harness `status` reproduced per experiment) |
| OpenRouter spend | **~$7.79** |

**Data anchors (sha256):**

| Artifact | Path | sha256 |
|---|---|---|
| Run DB (READ-ONLY, gitignored) | `runs/expC-openrouter/expC_2fake_5050.sqlite` | `dc77c3ca46b08afe212b45f2cae4fe68520bf11a44ba79185c02ca8fdad4362d` |
| Dataset baseline | `.../baseline-2fake-5050/baseline.json` | `e941e25b7d4bcecd1e26173c1e1340c9ac30935f06ad5c7bd2be93eebe60d15f` (from `manifest.json`; independently recomputed — matches) |

Both arms derive from the locked mechanical-130 workbooks + `balanced-flat-A.xlsx`
(BM/AN input-workbook and source-workbook sha256s recorded in `manifest.json`).
The 50/50 split was achieved exactly for both arms (`exact_5050_achieved: true`).

---

## 3. Results

### 3.1 Accuracy — per model, both arms (Analyst 1)

Strict accuracy in % (n_correct out of 100). **Delta = altered - control**
(percentage points). Every cell re-derived from the DB and cross-checked by two
independent query paths that agree exactly; all 16 cells have `n_scored=100`,
`n_parsed_ok=100`.

| model | BM control | BM altered | Delta BM | AN control | AN altered | Delta AN |
|---|---:|---:|---:|---:|---:|---:|
| `google/gemini-3.5-flash` | 97 | 97 | 0 | 96 | 96 | 0 |
| `qwen/qwen3.7-max` | 92 | 92 | 0 | 92 | 92 | 0 |
| `qwen/qwen3.6-35b-a3b` | 84 | 87 | +3 | 91 | 87 | -4 |
| `google/gemma-4-26b-a4b-it` | 88 | 84 | -4 | 88 | 81 | -7 |

**Control accuracy over the union of distinct base questions** (BM and AN control
sets share base questions; shared questions counted once, as the mean of their two
byte-identical control observations):

| model | unique-control accuracy | n unique | n shared | shared-control letter agreement |
|---|---:|---:|---:|---:|
| `google/gemini-3.5-flash` | 97.1% | 140 | 60 | 60/60 |
| `qwen/qwen3.7-max` | 92.9% | 140 | 60 | 60/60 |
| `qwen/qwen3.6-35b-a3b` | 87.9% | 140 | 60 | **54/60** |
| `google/gemma-4-26b-a4b-it` | 86.4% | 140 | 60 | 60/60 |

> **Correction carried forward: the BM-intersect-AN source overlap is 60, not 58.**
> Every definition checked agrees on 60 shared base questions (union = 140
> distinct): identical `source_key`, identical `control_question_text`, identical
> `control_text_sha256`, identical `correct_letter`, and byte-identical prompts
> across the two arms. Do **not** carry "58" forward.

### 3.2 Answer-flip — primary outcome, per model per arm (Analyst 2)

Flip = the selected letter differs between CONTROL and ALTERED for the same base
question. `n=100` questions per model per arm; clustered on the **cluster id**
(the independence unit): BM = 33 clusters, AN = 34 clusters. Two 95% CIs are
reported for every cell: **CR1** = analytic cluster-robust sandwich (statsmodels
OLS, `cov_type="cluster"`, t-interval, df = clusters - 1); **bootstrap** =
whole-cluster percentile bootstrap (10,000 resamples, seed 20260731). Direction
is among flips only: **C->W** correct->wrong, **W->C** wrong->correct, **W->W**
wrong->wrong (a correct->correct flip is impossible — the key is identical across
CONTROL/ALTERED — and 0 were observed). Exclusions for unparsed/no-cluster = **0**
everywhere.

**Arm BM (biomarker)**

| model | flips/n | flip rate | 95% CI (CR1) | 95% CI (bootstrap) | clusters | C->W | W->C | W->W |
|---|---:|---:|---|---|---:|---:|---:|---:|
| `google/gemini-3.5-flash` | 0/100 | **0.00%** | [0.00%, 0.00%] | [0.00%, 0.00%] | 33 | 0 | 0 | 0 |
| `qwen/qwen3.7-max` | 6/100 | **6.00%** | [1.84%, 10.16%] | [2.11%, 10.81%] | 33 | 3 | 3 | 0 |
| `qwen/qwen3.6-35b-a3b` | 7/100 | **7.00%** | [2.36%, 11.64%] | [2.82%, 13.10%] | 33 | 2 | 5 | 0 |
| `google/gemma-4-26b-a4b-it` | 9/100 | **9.00%** | [3.32%, 14.68%] | [4.17%, 16.67%] | 33 | 5 | 1 | 3 |
| **POOLED (4 models)** | 22/400 | **5.50%** | [2.84%, 8.16%] | [3.19%, 9.00%] | 33 | 10 | 9 | 3 |

**Arm AN (anatomy)**

| model | flips/n | flip rate | 95% CI (CR1) | 95% CI (bootstrap) | clusters | C->W | W->C | W->W |
|---|---:|---:|---|---|---:|---:|---:|---:|
| `google/gemini-3.5-flash` | 0/100 | **0.00%** | [0.00%, 0.00%] | [0.00%, 0.00%] | 34 | 0 | 0 | 0 |
| `qwen/qwen3.7-max` | 2/100 | **2.00%** | [-0.54%, 4.54%] | [0.00%, 5.26%] | 34 | 1 | 1 | 0 |
| `qwen/qwen3.6-35b-a3b` | 8/100 | **8.00%** | [2.79%, 13.21%] | [3.01%, 14.06%] | 34 | 5 | 1 | 2 |
| `google/gemma-4-26b-a4b-it` | 10/100 | **10.00%** | [3.15%, 16.85%] | [4.67%, 20.55%] | 34 | 8 | 1 | 1 |
| **POOLED (4 models)** | 20/400 | **5.00%** | [2.36%, 7.64%] | [2.81%, 8.47%] | 34 | 14 | 3 | 3 |

**Read of the results.**
- Flip rates are **low across the board** (0-10% per model per arm; pooled
  5.0-5.5%), consistent with the fabricated finding rarely moving the selected
  letter under this 2-fake / 50-50 baseline.
- `google/gemini-3.5-flash` is **completely stable** (0 flips in both arms).
  `google/gemma-4-26b-a4b-it` is the least stable (9-10% flips) and its flips skew
  **correct->wrong** (BM 5:1, AN 8:1).
- In the pooled AN arm, flips skew **correct->wrong** (14 C->W vs 3 W->C); pooled
  BM is roughly balanced (10 C->W vs 9 W->C).

---

## 4. Interpretation and LIMITATIONS

**Interpretation.** Under this 2-fake / 50-50 baseline, three of four models keep
selected-answer behavior stable (flip rates <= 8%), and the top model
(`gemini-3.5-flash`) does not flip at all. Accuracy stays flat or drops modestly
(Delta from 0 to -7 pp). Both signals point the same way — the single fabricated
finding usually does *not* dislodge the answer — with `gemma-4-26b-a4b-it` the
clearest exception and its flips concentrated in the harmful correct->wrong
direction.

**Limitations (read every result through these):**

1. **The altered set is MECHANICAL, not clinically certified
   answer-key-preserving.** The fabricated finding was inserted programmatically;
   no clinician has certified that the CONTROL answer key remains the single best
   answer once the fake finding is present. Therefore an **altered - control
   accuracy delta conflates** (a) genuine robustness loss with (b) any case where
   the fabricated finding legitimately changes the best answer. **Accuracy is
   supporting only; the per-question flip rate is primary.**

2. **Clusters are the independence unit — n = questions/clusters, not rows.** BM
   has 33 clusters over 100 questions, AN has 34 over 100; **some clusters hold
   many questions**. All inferential statistics cluster on the cluster id (CR1
   analytic sandwich + whole-cluster bootstrap). Do not treat the 100 rows as 100
   independent observations.

3. **Single-shot (runs=1): no run-to-run variance is captured, and provider
   nondeterminism at temperature=0 is real.** On the 60 **byte-identical** shared
   control prompts, three models return the same letter 60/60, but
   **`qwen/qwen3.6-35b-a3b` agrees only 54/60** — 6 prompts get a different letter
   across two separate API calls despite identical input and `temperature=0`. So
   part of that model's single-run flip signal is **provider/model noise**, not
   fabricated-finding sensitivity; its BM-control (84) vs AN-control (91) gap is
   likewise partly noise on the shared subset. A single shot cannot separate the
   two; the other three models are deterministic on that subset.

4. **Accuracy-stability != answer-stability.** A model can hold accuracy constant
   while still flipping letters. `qwen/qwen3.7-max` shows Delta-accuracy = 0 in
   **both** arms yet flips 6 letters in BM and 2 in AN — the flips offset (equal
   C->W and W->C), so accuracy hides them. This is exactly why flip is the primary
   outcome.

5. **The fabricated finding never alters the option text or the answer key, by
   construction.** ALTERED = CONTROL + one fabricated finding **in the stem only**;
   `correct_letter` is identical CONTROL vs ALTERED for all 100 questions in both
   arms. A correct->correct "flip" is therefore impossible (0 observed). The test
   is purely whether the extra stem finding perturbs the model's choice.

6. **CR1 analytic intervals can dip below 0% for the rarest flip cells** (normal
   approximation on a rare 0/1 proportion with few clusters — see AN
   `qwen3.7-max`: CR1 lower bound -0.54%). The whole-cluster bootstrap stays within
   [0%, 100%] and is the more trustworthy bound there. Both are reported; neither
   is clamped.

7. **Pooled rows mix heterogeneous models.** The pooled arm stacks all four models
   and clusters so that the same base question across four models nests in one
   cluster (the conservative choice). Treat pooled numbers as a **descriptive
   summary**, not a per-model estimate.

---

## 5. Traceability — inputs and exports

### 5.1 Analyst deliverables consumed

| File | Author | Content |
|---|---|---|
| `openrouter-results/accuracy.md` / `.csv` / `accuracy_long.csv` | Analyst 1 | Strict accuracy per (model, experiment); unique-control accuracy; 58->60 overlap correction; qwen3.6 nondeterminism finding |
| `openrouter-results/flip_rate.md` / `.csv` | Analyst 2 | Per-question flip rate + two cluster-robust 95% CIs + direction breakdown, per model per arm and pooled |
| `openrouter-results/compute_accuracy.py`, `analyze_flip_rate_openrouter.py` | Analysts 1 & 2 | Reproducible scripts behind the two tables above |

### 5.2 Raw + summary exports (produced by this step)

Written to `openrouter-results/exports/`, one **summary CSV** and one **raw JSONL**
per experiment, via the harness `medrag-eval export`
(`db.summary_rows` / `db.raw_attempt_rows`).

- **Summary CSV** — 400 data rows each (100 questions x 4 models; header +400 =
  401 lines), 29 columns incl. `selected_letter`, `correct_letter`,
  `strict_correct`, `parse_status`, tokens, latency.
- **Raw JSONL** — 400 attempts each (1600 total), 19 columns incl. `request_json`,
  `response_body`, `status_code`. **`request_headers_json` is `null` for all 1600
  attempts** (no Authorization header was ever stored); a secret scan of the
  written files returns **0** matches for API-key / Bearer / authorization /
  api_key patterns.

| Export file | sha256 |
|---|---|
| `exports/expC_2f_bm_control_summary.csv` | `116e1af81ffb128027f3045f74c9964f81e7fb3fe08759c8fe80ede408c59f56` |
| `exports/expC_2f_bm_control_raw.jsonl` | `76a9dac52070f9008e120197176568b31c95fe69ac1b3e7d28c77c310f83d9a2` |
| `exports/expC_2f_bm_altered_summary.csv` | `9e792f4bca462892ed6fb14f7538f3062c3d5fbef8cf6ae2e155ac7d13510563` |
| `exports/expC_2f_bm_altered_raw.jsonl` | `9e7472e50b6c262684aeb09a8e7230769c1f10c2b4eb5104e11dccb84fc093ca` |
| `exports/expC_2f_an_control_summary.csv` | `d9bc19778f1d20f1bc7527cb059b76c1d47365865e3356f0393b2f139740aa49` |
| `exports/expC_2f_an_control_raw.jsonl` | `43da3776f0de2f09fe30a4f746efb0d4916b7c4d6eaaf78ae2ac4cfa9aec85ea` |
| `exports/expC_2f_an_altered_summary.csv` | `ab82473c7b0ea8f171aa65f041c486b482be1a06302ecd707821b1cd8ec5efef` |
| `exports/expC_2f_an_altered_raw.jsonl` | `44c7252310fc1bda71c36423462b41e2f7d6552d15974078523fb3c60061e2d0` |

### 5.3 Read-only handling of the committed DB

`db.connect` forces `PRAGMA journal_mode = WAL` (a write that also creates
`-wal`/`-shm` sidecars). To keep the committed DB **byte-for-byte unmodified**, the
harness export was run against a **throwaway copy** in a scratch directory. The
copy was verified byte-identical to the original before export
(`sha256 = dc77c3ca...` on both), and the original's sha256 was **re-verified
unchanged after** all exports, with **no `-wal`/`-shm` sidecars** left beside it.
No secret files were read; no network or model-API calls were made; nothing was
staged or committed to git.

---

*Generated 2026-08-05 as the Experiment C OpenRouter traceability report. All
numbers trace to `expC_2fake_5050.sqlite` (`dc77c3ca...`) and the Analyst 1 / 2
deliverables. No secrets are present in this report or any export.*
