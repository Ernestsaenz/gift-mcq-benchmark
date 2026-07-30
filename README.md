# GIFT MCQ Benchmark — Tier 1

[![CI](https://github.com/Ernestsaenz/gift-mcq-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/Ernestsaenz/gift-mcq-benchmark/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A **315-item Spanish gastroenterology/hepatology multiple-choice benchmark** across
four LLMs served two ways — through the GIFT retrieval-augmented system and directly
via OpenRouter — together with the complete raw results, the harness that produced
them, and scripts that let you re-derive every published number yourself.

This repository is an **evidence package, not just code**. The 53 MB SQLite database
of raw per-call logs is committed, so `git clone` gives you everything needed to
reproduce the results offline, with no API keys and no network access.

> **Headline:** aggregate strict accuracy 86.90% (1,095/1,260) on the GIFT arm, with
> 100% completion; the two strongest models are statistically indistinguishable
> (Gemini 95.56% vs Qwen 3.7 Max 94.29%, exact McNemar, Holm p = 0.523).
>
> ⚠️ A post-publication audit found two answer-extraction defects. Both are fixed
> and regression-tested. Corrected: Gemini **96.19%**, aggregate **87.06%**,
> Holm p **0.263** — still non-significant, so the conclusion is unchanged. The
> published figures are retained throughout `EVIDENCE.md` for consistency with the
> abstract; corrected figures live in `data/statistical_analysis_corrected/`.
> Full details: **[CORRECTION_NOTE.md](CORRECTION_NOTE.md)**.

---

## Quickstart — verify the results offline

No credentials, no network, no third-party packages. Two commands:

```bash
git clone https://github.com/Ernestsaenz/gift-mcq-benchmark.git
cd gift-mcq-benchmark

# 1. Re-derive every statistic from the raw database and assert the audit's findings
python3 rescore_with_fixed_parser.py --check

# 2. Run the regression suite (needs pytest)
pip install -e ".[dev]" && pytest
```

Expected output from step 1:

```
score changes: 2  (method-only: 313)
GIFT aggregate : 1095/1260 = 86.9048%  ->  1097/1260 = 87.0635%
GIFT gemini    : 301/315 = 95.56%  ->  303/315 = 96.19%
Cochran's Q    : 117.454 (p=2.727e-25)  ->  124.042 (p=1.040e-26)
Gemini vs Qwen3.7 Holm p: 0.523467  ->  0.263176  (still NOT significant)
OpenRouter arm : unchanged at 1108/1260

CHECK PASSED: exactly the two audited corrections, control arm untouched.
```

`rescore_with_fixed_parser.py` is **standard-library only** — Cochran's Q, the exact
binomial McNemar test and the Holm step-down correction are implemented in it, so it
runs on a bare `python3` with nothing installed. It opens the database read-only and
never writes to it.

Or use the Makefile:

```bash
make verify    # rescoring + integrity check
make test      # regression suite
make check     # both
```

## Reproduce the headline straight from SQL

If you trust nothing but the raw rows:

```bash
sqlite3 -box data/medrag_eval.sqlite "
WITH latest_answer AS (
  SELECT p.*, ROW_NUMBER() OVER (PARTITION BY p.logical_call_id ORDER BY p.id DESC) rn
  FROM parsed_answers p
)
SELECT lc.provider, COUNT(*) calls, SUM(s.strict_correct) correct,
       ROUND(100.0*SUM(s.strict_correct)/COUNT(*), 4) accuracy_pct
FROM logical_calls lc
JOIN experiments e ON e.id = lc.experiment_id
LEFT JOIN latest_answer pa ON pa.logical_call_id = lc.id AND pa.rn = 1
LEFT JOIN scores s ON s.parsed_answer_id = pa.id
WHERE e.name = 'bench_315_v2'
GROUP BY lc.provider;"
```

More reproduction paths — per-model breakdowns, the full statistics regeneration —
are in **[reproduction.md](reproduction.md)**.

## Repository layout

```
├── README.md                       ← you are here
├── EVIDENCE.md                     the evidence document: every figure with provenance
├── CORRECTION_NOTE.md              the post-publication audit, its fixes, and the delta
├── reproduction.md                 step-by-step reproduction with real expected output
├── rescore_with_fixed_parser.py    stdlib-only re-scoring + corrected statistics
├── pyproject.toml
├── Makefile
├── code/
│   ├── medrag_eval/                the benchmark harness and packaged live prompts
│   ├── tests/                      regression tests
│   ├── harness_README.md           harness operating notes
│   └── mcq_shared_v2_user_template.txt   historical prompt used by the committed run
└── data/
    ├── README.md                   data provenance, privacy audit, licensing
    ├── medrag_eval.sqlite          raw per-call logs (2,520 calls) — the ground truth
    ├── questions-ope-300-clean.xlsx  the 315-item evaluation set
    ├── statistical_analysis/           originally published outputs (unchanged)
    └── statistical_analysis_corrected/ regenerated after the parser correction
```

## What was measured

| | |
|---|---|
| **Dataset** | 315 Spanish MCQs, Galicia (SERGAS) OPE 2016/2019/2022, specialty *aparato digestivo* |
| **Models** | `google/gemini-3.5-flash`, `qwen/qwen3.7-max`, `qwen/qwen3.6-35b-a3b`, `google/gemma-4-26b-a4b-it` |
| **Arms** | GIFT (retrieval-augmented) and OpenRouter (same base models, direct) |
| **Calls** | 2,520 = 315 × 4 × 2, single-shot (`run_index = 1` throughout) |
| **Prompt (as run)** | one shared user-only message, byte-identical across arms; **no `X-Prompt-ID` was sent**, so GIFT used its backend default (`Conciso`), *not* prompt 13 — see [EVIDENCE.md §5](EVIDENCE.md) |
| **Outcome** | `strict_correct` — see the caveat in [EVIDENCE.md §5](EVIDENCE.md) |
| **Tests** | Cochran's Q (omnibus), exact McNemar (pairwise), Holm correction |

The independent unit for inference is the **question (n = 315)**, not the 1,260 rows.

## Advanced — running the benchmark live

The offline path above is what most people want. Re-running the benchmark against
live models additionally requires credentials and will incur API costs.

```bash
cp .env.example .env      # then fill in your credentials
pip install -e .

medrag-eval init-db --db runs/medrag_eval.sqlite
medrag-eval import-questions --dataset galicia_digestivo_315 \
    --xlsx data/questions-ope-300-clean.xlsx --db runs/medrag_eval.sqlite
medrag-eval check-auth --provider openrouter
medrag-eval run --dataset galicia_digestivo_315 --experiment my_run \
    --provider-model openrouter:google/gemini-3.5-flash --db runs/medrag_eval.sqlite
medrag-eval status --experiment my_run --db runs/medrag_eval.sqlite
```

Notes:

- Write new runs to `runs/` (gitignored). **Do not** point `--db` at
  `data/medrag_eval.sqlite` — that is the committed ground truth.
- The GIFT (`tailscale_medical_rag`) provider needs a reachable GIFT deployment;
  without one, only the `openrouter` arm can be reproduced live.
- Every GIFT benchmark call sends `X-Prompt-ID: 13`, the stored multiple-choice
  prompt. The harness applies it automatically and rejects any other prompt ID
  so the backend cannot silently fall back to its default `Conciso` prompt.
- Under the live `mcq_provider_v3` regime, GIFT receives only the question and
  four options because prompt 13 already contains the MCQ instructions.
  OpenRouter receives the equivalent instructions in-message.
- Results will not match the committed database exactly. These are non-deterministic
  models and the served model versions have moved on. The committed database is the
  reproducible artifact; a live re-run is a *new experiment*.

See [`code/harness_README.md`](code/harness_README.md) for full harness documentation.

## Requirements

- Python **3.11+**
- `sqlite3` on PATH (optional — only for the raw-SQL path)
- Nothing else for verification. `pip install -e ".[dev]"` adds pytest;
  `".[analysis]"` adds numpy/pandas/scipy/statsmodels for regenerating the full
  statistical outputs.

## Citing

If you use this benchmark or its data, please cite it — see
[`CITATION.cff`](CITATION.cff), or use GitHub's "Cite this repository" button.

## License

Code is MIT (see [LICENSE](LICENSE)). **The 315 exam items in `data/` are
third-party content and are not covered by that license** — they are reproduced
from published Galicia SERGAS public examinations solely to make the results
reproducible. See [`data/README.md`](data/README.md).
