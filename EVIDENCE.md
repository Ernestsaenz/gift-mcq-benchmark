# Tier 1 — MCQ Benchmark Evidence (GIFT)

Evidence backing the Tier 1 sentence of the GIFT abstract:

> "315-item Spanish gastroenterology-hepatology MCQ benchmark across four LLMs
> (gemini 3.5, qwen 3.7 max, qwen 3.6, gemma 4); 1,260 paired calls analyzed by
> Cochran's Q and exact McNemar with Holm correction. RESULTS: aggregate accuracy
> 86.9% with 100% completion; gemini 95.6% and qwen 3.7 max 94.3% indistinguishable
> (Holm p=0.523)."

Every number in that sentence is reproduced below directly from the raw results
database (`data/medrag_eval.sqlite`, experiment `bench_315_v2`) and cross-checked
against the committed statistical outputs. The reproduction commands and their real
output are in [`reproduction.md`](reproduction.md).

> ⚠️ **Post-audit correction — read [`CORRECTION_NOTE.md`](CORRECTION_NOTE.md).**
> A code audit of `code/medrag_eval/` found two answer-extraction defects. Both are
> fixed and covered by regression tests. Net effect: **two GIFT-arm gemini answers
> were scored wrong in the model's disfavour** (g134, g261). Corrected figures are
> gemini **96.19%** (was 95.56%) and aggregate **87.0635%** (was 86.9048%); the
> OpenRouter control arm is unchanged, and the "top two models are
> indistinguishable" conclusion still holds (Holm p = 0.263). The numbers quoted
> throughout this README remain the **as-published** ones so the abstract and the
> committed statistics stay internally consistent; the corrected set lives in
> `data/statistical_analysis_corrected/`. Whether to restate the abstract is an
> open decision — see `CORRECTION_NOTE.md` §5.

---

## 1. Purpose

This folder is the primary-source packet for the multiple-choice-question (MCQ)
accuracy claim. It lets a reviewer independently confirm, from raw per-call logs,
that:

1. The GIFT system answered a 315-question Spanish digestive-medicine board-exam
   benchmark with four served LLM configurations.
2. Across those four configurations the GIFT aggregate strict accuracy was **86.9%**
   with **100% final completion** (no dropped or unscoreable calls).
3. The two strongest configurations (Gemini 95.6%, Qwen 3.7 Max 94.3%) were
   **statistically indistinguishable** after multiplicity correction (Holm-adjusted
   exact-McNemar p = 0.523).

---

## 2. What "GIFT" is in this benchmark

GIFT is evaluated here as the **`tailscale_medical_rag` provider arm** of the
harness. This is not a relabelling convenience — the provider client literally
authenticates against the GIFT medical-RAG API using `GIFT_API` / `GIFT_EMAIL` /
`GIFT_PASSWORD` credentials and forwards retrieval-depth controls as `X-Top-K`
headers (`code/medrag_eval/providers/tailscale_medical_rag.py:46-49`, `:399-405`).
In the statistical reports the same arm is displayed under the label **"TailScale"**.

So throughout this dossier: **GIFT arm = `tailscale_medical_rag` provider = the
"TailScale" rows in the reports.** The benchmark also ran the *identical* prompts
and questions through a second provider (**OpenRouter**, the same base models called
directly, without GIFT's retrieval layer). That second arm is used only as a
robustness control (see §7, note 1), never as the headline.

---

## 3. Dataset (honest scope)

| Property | Value | Source |
|---|---|---|
| Dataset name | `galicia_digestivo_315` | `datasets` table |
| Source workbook | `questions-ope-300-clean.xlsx` (315 rows) | `data/questions-ope-300-clean.xlsx` |
| Region | Galicia (Spain) public-health specialist exams (OPE) | `questions.region` (all `galicia`) |
| Specialty label | `aparato-digestivo` (Spanish for the combined **digestive-system** specialty = gastroenterology + hepatology) | `questions.specialty` (all rows) |
| Exam years | 2016 (105 items), 2019 (104), 2022 (106) = **315** | `questions.year` / `exam_part` |
| Format | 4-option single-best-answer MCQ (letters a–d) | `questions.option_a…d`, `correct_letter` |
| Language | Spanish (stems and options preserve Spanish orthography) | `question_text`, `mcq_shared_v2` template |

**Scope honesty.** The specialty is the Spanish *aparato digestivo* board specialty,
which encompasses both gastroenterology and hepatology; it is not a purely
hepatology exam. A conservative keyword scan of the **question stems**
(`hepat*`, `cirros*`, `colangi*`, `biliar*`, `varices`, `ascit*`) matches
**58 / 315 = 18.4%** of items as explicitly hepatobiliary; including option-level
mentions raises this to 88/315 (≈28%). The abstract's "gastroenterology-hepatology"
label is therefore defensible as a description of the specialty, with the honest
caveat that hepatology is a substantial minority (~one in five stems), not half, of
the benchmark. Results should not be generalized beyond this exam domain
(stated in `data/statistical_analysis/gift_system_subreport.md:228`).

---

## 4. Models (four GIFT configurations)

Each question was answered **exactly once** per model per provider (`run_index = 1`
for all 2,520 logical calls), so accuracy is a single-shot measurement, not a
best-of-N.

| Abstract label | Served model ID | GIFT strict accuracy |
|---|---|---|
| gemini 3.5 | `google/gemini-3.5-flash` | 95.6% (301/315) |
| qwen 3.7 max | `qwen/qwen3.7-max` | 94.3% (297/315) |
| qwen 3.6 | `qwen/qwen3.6-35b-a3b` | 84.1% (265/315) |
| gemma 4 | `google/gemma-4-26b-a4b-it` | 73.7% (232/315) |

Source: `data/statistical_analysis/final_accuracy_by_arm.csv:6-9`;
mirrored in `gift_system_subreport.md:92-98`.

---

## 5. Methods

**Scoring — strict (with an honest caveat added post-audit).** The primary outcome
`strict_correct` requires **both** the correct letter **and** a character-for-character
match of the chosen option text (`code/medrag_eval/scoring.py:23-25`).

⚠️ **Correction (see `CORRECTION_NOTE.md` §4).** An earlier version of this section
claimed the strict rule makes 86.9% "a floor, not an inflated lenient score."
**That claim is not supported by the data.** Across all 2,520 scored rows,
`strict_correct`, `letter_correct`, `text_correct` and `lenient_correct` are
**identical** — strict scoring separates nothing in this dataset. The reason is
structural: the parser backfills `selected_option_text` from the letter when the
model supplies only a letter, and treats a paraphrased option text as a *parse
failure* rather than a wrong answer. So `text_correct` can only diverge from
`letter_correct` on `ok_conflict` rows — of which there is exactly one in the DB,
and it is not in the final scored set. The 86.9% figure itself is correct and
unaffected; only this justification for it was wrong. Read 86.9% as
**letter-level accuracy**.

**Prompt.** A single shared prompt (`mcq_shared_v2`) casts the model as a
"board-certified specialist in gastroenterology and hepatology" and forces a strict
JSON output (`selected_letter`, `selected_option_text`)
(`code/mcq_shared_v2_user_template.txt:1,14-20`). The *same* prompt is used for both
providers, so the GIFT-vs-OpenRouter contrast is apples-to-apples **at the prompt
level**.

⚠️ **Extraction asymmetry (added post-audit; see `CORRECTION_NOTE.md` §3).** The
prompt is identical, but the *extraction path* was not. In the published run the
GIFT arm resolved **31.5% of answers via regex fallback (397/1260)** versus **0.5%
on OpenRouter (6/1260)**, because gemma wraps every GIFT-arm response in a
` ```json ` fence that the parser did not strip. This is now fixed: fenced JSON
parses structurally, moving 313 rows onto the structured path **without changing
any answer**. Post-fix the asymmetry is 84/1260 vs 6/1260. Of those 90 residual
rows, **82 still carry a verbatim `"selected_letter"` key** and are extracted
exactly; only **8** (all tailscale/gemini) depend on the prose heuristics at all,
and exactly one of those relies on the weakest tier. Full breakdown in
`CORRECTION_NOTE.md` §3.

**Answer selection.** Accuracy uses the **latest attempt** per logical call (the
final validated answer after any retries). This mirrors the harness query
(`run_statistical_analysis.py:54-103`) and is what the SQLite reproduction in
`reproduction.md` replicates.

**Statistical tests and why.** The same 315 questions are answered by all four
model configurations, so the outcomes are **paired/blocked on the question**. That
dictates the test choice:

- **Cochran's Q** — omnibus test for whether the four models' accuracies differ,
  treating each question as a block of four paired binary outcomes
  (`run_statistical_analysis.py:194`, `statsmodels.stats.contingency_tables.cochrans_q`).
- **Exact McNemar** — pairwise follow-up between two models on the same questions,
  using only the discordant pairs; exact (binomial) because some discordant counts
  are small (`run_statistical_analysis.py:162,209`, `mcnemar(..., exact=True)`).
- **Holm correction** — controls the family-wise error rate across the six
  within-provider pairwise comparisons; less conservative than Bonferroni, no
  independence assumption (`run_statistical_analysis.py:183,231`,
  `statsmodels.stats.multitest.multipletests(method="holm")`).

The independent unit for inference is the **question (n = 315)**, not the 1,260
rows — stated explicitly in the report caveats
(`data/statistical_analysis/statistical_report.md:133-134`).

---

## 6. Results (every figure with provenance)

All figures below are for the **GIFT / `tailscale_medical_rag`** arm unless noted.
"Reproduced" = independently recomputed in `reproduction.md` from the raw DB.

| Claim | Value | Primary source (file:line) | Reproduced? |
|---|---|---|---|
| Logical calls, GIFT arm | 1,260 (= 315 × 4 models × 1 run) | `gift_system_subreport.md:31-32`; DB count | ✅ |
| Aggregate strict accuracy | **1,095 / 1,260 = 86.9048% ≈ 86.9%** | `gift_system_subreport.md:98`; `final_accuracy_by_arm.csv:6-9` | ✅ 86.9048% |
| Final completion | **1,260 / 1,260 = 100%** (0 API failures, 0 parse failures, 0 null scores) | `gift_system_subreport.md:9-11,83-87`; `statistical_report.md:7` | ✅ 0/0/0 |
| Gemini accuracy | 95.6% (301/315) | `final_accuracy_by_arm.csv:6`; `statistical_report.md:16` | ✅ |
| Qwen 3.7 Max accuracy | 94.3% (297/315) | `final_accuracy_by_arm.csv:9`; `statistical_report.md:19` | ✅ |
| Qwen 3.6 accuracy | 84.1% (265/315) | `final_accuracy_by_arm.csv:8` | ✅ |
| Gemma accuracy | 73.7% (232/315) | `final_accuracy_by_arm.csv:7` | ✅ |
| Cochran's Q (GIFT arm) | Q = 117.454, df = 3, **p = 2.73e-25** (models differ overall) | `model_cochran_q.csv:3`; `statistical_report.md:35` | ✅ Q=117.454 |
| Gemini vs Qwen 3.7 Max | discordant b=13, c=9; raw p = 0.5235; **Holm p = 0.523 → not significant / indistinguishable** | `model_pairwise_mcnemar.csv:10`; `statistical_report.md:47` | ✅ Holm p=0.5234670639 |
| OpenRouter arm aggregate (control) | 1,108 / 1,260 = 87.94% | `statistical_report.md:12-15` (sum of arm rows) | ✅ 87.9365% |

Why Holm leaves the Gemini/Qwen p unchanged: 0.523 is the **largest** of the six
within-provider raw p-values, and Holm multiplies the largest by 1, so
adjusted = raw. The conclusion (no detectable difference between the top two
configurations) is robust to the correction.

---

## 7. Framing notes handled openly

These are the points a scrupulous reviewer will probe. Each is stated here rather
than buried.

**Note 1 — "aggregate 86.9%" is the GIFT (TailScale) arm specifically.** It is the
mean strict accuracy over the four GIFT-served configurations on 315 questions
(1,095/1,260). The identical benchmark run through OpenRouter (same base models,
no GIFT retrieval layer) gave 87.94% aggregate, and the within-model
GIFT-vs-OpenRouter provider comparison was **non-significant for every model**
(Holm p = 1.0 for Gemini, Gemma, Qwen 3.7 Max; 0.349 for Qwen 3.6;
`data/statistical_analysis/provider_mcnemar.csv:2-5`). So 86.9% is not a
provider-specific artifact — the two arms agree — and we report it transparently as
the GIFT arm, with OpenRouter as corroboration.

**Note 2 — 86.9% is a blended, model-heterogeneous figure.** It averages a strong
tier (Gemini 95.6%, Qwen 3.7 Max 94.3%) with two weaker configurations
(Qwen 3.6 84.1%, Gemma 73.7%). GIFT performance is strongly model-dependent
(`gift_system_subreport.md:100-114`); the aggregate should be read as "average over
four heterogeneous configs," and the per-model numbers (esp. 95.6% best) tell the
sharper story. We present both, never the aggregate alone.

**Note 3 — "1,260 paired calls."** 1,260 = 315 questions × 4 models × 1 run for the
GIFT arm. "Paired" refers to the analysis structure, not to duplicate calls: the
1,260 outcomes are arranged as **315 within-question blocks of 4** for Cochran's Q,
and each McNemar comparison pairs two models cell-by-cell across the same 315
questions. The effective independent sample size for inference is the question
(n = 315), which we state in the caveats rather than claiming n = 1,260.

**Note 4 — this is NOT the EASL autoimmune-liver study.** A separate study
("Is Bigger Always Better", easl-andreas-small-LLM) is a **117-question
autoimmune-liver** evaluation and is unrelated to this benchmark. The Tier 1 claim
rests solely on the 315-item Galicia OPE `aparato-digestivo` dataset described here.
The two must not be conflated.

---

## 8. Why this is defensible

The claim is anchored to raw, append-only per-call logs, not to a summary
spreadsheet: every attempt, its latency, its parse status, and its score are in
`medrag_eval.sqlite`, and the headline reproduces from those rows with a single
SQL query (see `reproduction.md`). The scoring rule is nominally strict (letter +
exact option text), though in this dataset strict, letter, text and lenient scoring
coincide on all 2,520 rows — see the correction in §5; read 86.9% as **letter-level
accuracy**, neither inflated nor a floor. The 100%
completion figure is verified three ways (0 latest-attempt API failures, 0 parse
failures, 0 null scores). The "indistinguishable" claim is a **correctly
non-significant** result presented as such — we are not over-claiming a difference;
we are declining to claim one, backed by an exact test and multiplicity control.
And the whole finding replicates across a second, independent provider arm
(OpenRouter, 87.94%). The main honest limitations — single-domain dataset,
single-shot per model, and heavy retry dependence in the *attempt history* despite a
clean *final* table (`gift_system_subreport.md:171-202`) — are documented, not
hidden.

---

## 9. Provenance & exact source files

**Ground-truth artifact (authoritative):**
- `data/medrag_eval.sqlite` — raw results DB. Experiment `bench_315_v2`, created
  2026-05-25; dataset `galicia_digestivo_315`; 2,520 logical calls
  (315 × 2 providers × 4 models). Tables: `experiments`, `datasets`, `questions`,
  `logical_calls`, `provider_attempts`, `parsed_answers`, `scores`.
- `data/questions-ope-300-clean.xlsx` — the 315-item benchmark workbook.

**Statistical outputs (committed, regenerable from the DB):**
- `data/statistical_analysis/run_statistical_analysis.py` — the analysis script
  (statsmodels: `cochrans_q` L194; `mcnemar(exact=True)` L162/L209;
  `multipletests(method="holm")` L183/L231/L358).
- `data/statistical_analysis/final_accuracy_by_arm.csv` — accuracy per arm.
- `data/statistical_analysis/model_cochran_q.csv` — Cochran's Q per provider.
- `data/statistical_analysis/model_pairwise_mcnemar.csv` — pairwise McNemar + Holm.
- `data/statistical_analysis/provider_mcnemar.csv` — GIFT vs OpenRouter per model.
- `data/statistical_analysis/statistical_report.md` — full 8-arm report.
- `data/statistical_analysis/gift_system_subreport.md` — GIFT-arm-only report.
- `data/statistical_analysis/analysis_summary.json` — run metadata (2520 rows,
  315 questions, 8 arms).

**Harness (generation code):**
- `code/medrag_eval/` — the CLI harness (providers, prompting, parser, scoring, DB).
- `code/mcq_shared_v2_user_template.txt` — the shared MCQ prompt.
- `code/harness_README.md`, `code/pyproject.toml`.

**Version-control provenance (stated honestly).** The dossier folder is not itself
a git repository, and the benchmark artifacts (the SQLite DB, the dataset workbook,
and the statistical outputs) are **intentionally not version-controlled** — the
harness data policy forbids committing databases, raw responses, and exports
(`code/harness_README.md:15-16`). The upstream harness lives in the
`idara-paper-gift` repository (`ope-questions/test-system-1/src/medrag_eval`), but
the code snapshot bundled here **post-dates** that repo's last commit (`428a130`,
2026-04-27) — the bundled provider adds concurrency locks and the `X-Prompt-ID`/
`X-Top-K` retrieval controls the earlier commit lacks. We therefore anchor
provenance to **the committed database itself** (the reproducible ground truth),
not to a single git SHA. This is called out so the mismatch is disclosed rather
than discovered.
