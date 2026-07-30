# Reproduction — Tier 1 MCQ Benchmark (GIFT)

This file lets a reviewer reproduce every Tier 1 number from the raw database with
no access to anything outside this folder. All commands are run from the
`tier1_mcq/` directory. All outputs shown below are **real** — copied verbatim from
runs performed while assembling this dossier (macOS, SQLite 3, `uv` 0.10.9,
statsmodels 0.14.x under Python 3.13).

Prerequisites: `sqlite3` on PATH; `uv` on PATH (for the statsmodels steps —
`uv` fetches the pinned dependencies declared inline in the analysis script, so no
manual `pip install` is needed).

---

## A. Reproduce the 86.9% headline directly from the DB

The harness scores the **latest attempt** per logical call. This single query
replicates that (latest provider attempt + latest parsed answer, joined to scores),
filtered to experiment `bench_315_v2` and the GIFT (`tailscale_medical_rag`) arm.

```bash
sqlite3 -box data/medrag_eval.sqlite "
WITH latest_attempt AS (
  SELECT a.*, ROW_NUMBER() OVER (PARTITION BY a.logical_call_id ORDER BY a.attempt_index DESC, a.id DESC) rn
  FROM provider_attempts a
), latest_answer AS (
  SELECT p.*, ROW_NUMBER() OVER (PARTITION BY p.logical_call_id ORDER BY p.id DESC) rn
  FROM parsed_answers p
), final AS (
  SELECT lc.provider, lc.model, la.error_type, pa.parse_status, s.strict_correct
  FROM logical_calls lc
  JOIN experiments e ON e.id = lc.experiment_id
  JOIN questions q ON q.id = lc.question_id
  LEFT JOIN latest_attempt la ON la.logical_call_id = lc.id AND la.rn = 1
  LEFT JOIN latest_answer pa ON pa.logical_call_id = lc.id AND pa.rn = 1
  LEFT JOIN scores s ON s.parsed_answer_id = pa.id
  WHERE e.name = 'bench_315_v2'
)
SELECT COUNT(*) AS calls, SUM(strict_correct) AS correct,
       ROUND(100.0*SUM(strict_correct)/COUNT(*),4) AS accuracy_pct,
       SUM(error_type IS NOT NULL) AS latest_api_failures,
       SUM(parse_status NOT IN ('ok','ok_conflict')) AS latest_parse_failures,
       SUM(strict_correct IS NULL) AS null_scores
FROM final WHERE provider='tailscale_medical_rag';
"
```

**Actual output:**

```
┌───────┬─────────┬──────────────┬─────────────────────┬───────────────────────┬─────────────┐
│ calls │ correct │ accuracy_pct │ latest_api_failures │ latest_parse_failures │ null_scores │
├───────┼─────────┼──────────────┼─────────────────────┼───────────────────────┼─────────────┤
│ 1260  │ 1095    │ 86.9048      │ 0                   │ 0                     │ 0           │
└───────┴─────────┴──────────────┴─────────────────────┴───────────────────────┴─────────────┘
```

This is the headline: **1,095 / 1,260 = 86.9048% ≈ 86.9%**, with **100% completion**
(0 latest-attempt API failures, 0 parse failures, 0 unscored calls).

---

## B. Per-model breakdown (GIFT arm) and the OpenRouter control

Replace the final `SELECT` in the query above with a grouped form
(`final` CTE unchanged):

```bash
sqlite3 -box data/medrag_eval.sqlite "
WITH latest_attempt AS (
  SELECT a.*, ROW_NUMBER() OVER (PARTITION BY a.logical_call_id ORDER BY a.attempt_index DESC, a.id DESC) rn FROM provider_attempts a
), latest_answer AS (
  SELECT p.*, ROW_NUMBER() OVER (PARTITION BY p.logical_call_id ORDER BY p.id DESC) rn FROM parsed_answers p
), final AS (
  SELECT lc.provider, lc.model, s.strict_correct
  FROM logical_calls lc JOIN experiments e ON e.id=lc.experiment_id
  LEFT JOIN latest_attempt la ON la.logical_call_id=lc.id AND la.rn=1
  LEFT JOIN latest_answer pa ON pa.logical_call_id=lc.id AND pa.rn=1
  LEFT JOIN scores s ON s.parsed_answer_id=pa.id
  WHERE e.name='bench_315_v2'
)
SELECT provider, model, COUNT(*) calls, SUM(strict_correct) correct,
       ROUND(100.0*SUM(strict_correct)/COUNT(*),4) accuracy_pct
FROM final WHERE provider='tailscale_medical_rag'
GROUP BY provider, model ORDER BY correct DESC;
"
```

**Actual output (GIFT per-model):**

```
┌───────────────────────┬───────────────────────────┬───────┬─────────┬──────────────┐
│       provider        │           model           │ calls │ correct │ accuracy_pct │
├───────────────────────┼───────────────────────────┼───────┼─────────┼──────────────┤
│ tailscale_medical_rag │ google/gemini-3.5-flash   │ 315   │ 301     │ 95.5556      │
│ tailscale_medical_rag │ qwen/qwen3.7-max          │ 315   │ 297     │ 94.2857      │
│ tailscale_medical_rag │ qwen/qwen3.6-35b-a3b      │ 315   │ 265     │ 84.127       │
│ tailscale_medical_rag │ google/gemma-4-26b-a4b-it │ 315   │ 232     │ 73.6508      │
└───────────────────────┴───────────────────────────┴───────┴─────────┴──────────────┘
```

Provider-level control (swap the final `SELECT` for a `GROUP BY provider` + a
combined `UNION ALL` total):

**Actual output (both arms + combined):**

```
┌───────────────────────┬───────┬─────────┬──────────────┐
│       provider        │ calls │ correct │ accuracy_pct │
├───────────────────────┼───────┼─────────┼──────────────┤
│ openrouter            │ 1260  │ 1108    │ 87.9365      │
│ tailscale_medical_rag │ 1260  │ 1095    │ 86.9048      │
│ ALL COMBINED          │ 2520  │ 2203    │ 87.4206      │
└───────────────────────┴───────┴─────────┴──────────────┘
```

The GIFT arm (86.90%) and the OpenRouter control (87.94%) agree closely — the
headline is not a provider artifact.

---

## C. Recompute the two headline statistics (Cochran's Q + McNemar/Holm)

`statsmodels` is the reference implementation. The snippet below (dependencies
declared inline via PEP 723, run with `uv run`) recomputes, for the GIFT arm:
the aggregate accuracy, Cochran's Q, and the Gemini-vs-Qwen-3.7-Max exact-McNemar
raw and Holm-adjusted p-values.

```python
# save as verify_stats.py, then: uv run verify_stats.py
# /// script
# dependencies = ["numpy","pandas","scipy","statsmodels"]
# ///
import sqlite3; from pathlib import Path; import pandas as pd
from statsmodels.stats.contingency_tables import cochrans_q, mcnemar
from statsmodels.stats.multitest import multipletests
DB = Path("data/medrag_eval.sqlite"); TS = "tailscale_medical_rag"
Q = """
WITH latest_attempt AS (SELECT a.*, ROW_NUMBER() OVER (PARTITION BY a.logical_call_id ORDER BY a.attempt_index DESC, a.id DESC) rn FROM provider_attempts a),
     latest_answer  AS (SELECT p.*, ROW_NUMBER() OVER (PARTITION BY p.logical_call_id ORDER BY p.id DESC) rn FROM parsed_answers p)
SELECT q.question_id, lc.provider, lc.model, s.strict_correct
FROM logical_calls lc JOIN experiments e ON e.id=lc.experiment_id JOIN questions q ON q.id=lc.question_id
LEFT JOIN latest_attempt la ON la.logical_call_id=lc.id AND la.rn=1
LEFT JOIN latest_answer  pa ON pa.logical_call_id=lc.id AND pa.rn=1
LEFT JOIN scores s ON s.parsed_answer_id=pa.id
WHERE e.name='bench_315_v2'"""
df = pd.read_sql_query(Q, sqlite3.connect(DB)); df["strict_correct"]=df["strict_correct"].astype(int)
g = df[df.provider==TS]; print(f"GIFT aggregate: {g.strict_correct.sum()}/{len(g)} = {100*g.strict_correct.mean():.4f}%")
wide = g.pivot(index="question_id", columns="model", values="strict_correct")
q = cochrans_q(wide); print(f"Cochran's Q: Q={q.statistic:.3f}, df={len(wide.columns)-1}, p={q.pvalue:.3e}")
models=list(wide.columns); pvals=[]; pairs=[]
for i,a in enumerate(models):
    for b in models[i+1:]:
        nb=int(((wide[a]==1)&(wide[b]==0)).sum()); nc=int(((wide[a]==0)&(wide[b]==1)).sum())
        pvals.append(float(mcnemar([[0,nb],[nc,0]],exact=True).pvalue)); pairs.append((a,b,nb,nc))
holm = multipletests(pvals, method="holm")[1]
for (a,b,nb,nc),raw,hp in zip(pairs,pvals,holm):
    if {a,b}=={"google/gemini-3.5-flash","qwen/qwen3.7-max"}:
        print(f"McNemar Gemini vs Qwen 3.7 Max: b={nb}, c={nc}, raw p={raw:.10f}, Holm p={hp:.10f}")
```

**Actual output:**

```
GIFT aggregate: 1095/1260 = 86.9048%
Cochran's Q: Q=117.454, df=3, p=2.727e-25
McNemar Gemini vs Qwen 3.7 Max: b=13, c=9, raw p=0.5234670639, Holm p=0.5234670639
```

Cochran's Q rejects the null that all four GIFT models are equal
(p = 2.73e-25). The Gemini-vs-Qwen-3.7-Max comparison does **not** reject
(Holm p = 0.523) — the two top configurations are indistinguishable, matching the
abstract.

---

## D. Regenerate ALL committed statistics from the DB

The committed outputs in `data/statistical_analysis/` were produced by
`run_statistical_analysis.py`. That script uses **repo-relative hardcoded paths**:
it sets `ROOT = Path(__file__).resolve().parents[2]`, then reads
`ROOT/runs/medrag_eval.sqlite` and writes `ROOT/reports/statistical_analysis/`
(`run_statistical_analysis.py:26-28`). In this dossier the script sits at
`data/statistical_analysis/`, so `parents[2]` resolves to `tier1_mcq/`. To run it
here, stage the layout it expects (both paths are inside `tier1_mcq/`):

```bash
# from tier1_mcq/
mkdir -p runs reports/statistical_analysis
cp data/medrag_eval.sqlite runs/medrag_eval.sqlite     # script reads runs/medrag_eval.sqlite
cd data/statistical_analysis && uv run run_statistical_analysis.py
# -> writes regenerated CSVs + statistical_report.md into tier1_mcq/reports/statistical_analysis/
```

`uv` resolves the inline dependencies (`numpy, pandas, scipy, statsmodels,
tabulate`) automatically. The run prints one harmless
`FutureWarning: wald_test ...` from statsmodels and exits 0.

**Verification performed for this dossier.** The regenerated files were diffed
against the committed ones and are **byte-identical**:

```
IDENTICAL: final_accuracy_by_arm.csv
IDENTICAL: model_cochran_q.csv
IDENTICAL: model_pairwise_mcnemar.csv
IDENTICAL: analysis_summary.json
```

(The temporary `runs/` and `reports/` staging directories were removed afterward,
so the delivered folder contains only `code/`, `data/`, the Markdown documents, and this file.
Re-running the commands above recreates them.)

---

## E. Expected key values (quick-reference)

| Quantity | Expected value | Where |
|---|---|---|
| GIFT arm logical calls | 1,260 | §A |
| GIFT aggregate strict accuracy | 1,095 / 1,260 = 86.9048% | §A, §C |
| GIFT final completion | 100% (0 API / 0 parse / 0 null) | §A |
| Gemini | 301/315 = 95.5556% | §B |
| Qwen 3.7 Max | 297/315 = 94.2857% | §B |
| Qwen 3.6 | 265/315 = 84.1270% | §B |
| Gemma | 232/315 = 73.6508% | §B |
| OpenRouter control aggregate | 1,108 / 1,260 = 87.9365% | §B |
| Cochran's Q (GIFT arm) | Q = 117.454, df = 3, p = 2.727e-25 | §C |
| Gemini vs Qwen 3.7 Max | b=13, c=9, raw p = Holm p = 0.5234670639 | §C |

---

## F. Provenance note

The reproduction anchor is **`data/medrag_eval.sqlite`** (experiment
`bench_315_v2`, created 2026-05-25), not a git commit. The dossier folder is not a
git repository, and — per the harness data policy (`code/harness_README.md:15-16`) —
the database, dataset workbook, and statistical outputs are intentionally never
committed. The upstream harness code lives in `idara-paper-gift`
(`ope-questions/test-system-1/src/medrag_eval`, last commit `428a130`, 2026-04-27),
but the harness snapshot bundled here post-dates that commit (it adds the
`X-Prompt-ID`/`X-Top-K` retrieval controls and concurrency locks the committed
version lacks). Ground truth is therefore the database, which reproduces every
figure above deterministically.
