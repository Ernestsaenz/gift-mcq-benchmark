"""Experiment C (2-fake/50-50 baseline) — OpenRouter CTRL vs ALT answer-flip analysis.

ANALYST 2 driver. Primary outcome = per-question ANSWER FLIP: for each
(model, base_question_id, arm) did the selected letter change between the CONTROL
and ALTERED version of the same base question?

This driver REUSES the QA-validated flip-rate code in
  data/experiment-C-2026-07-31/final/baseline-2fake-5050/run/analyze_flip_rate.py
(imported as `qa`) for every statistic it already produces — the pairing/exclusion
logic, the analytic CR1 cluster-sandwich CI (statsmodels OLS, cov_type="cluster",
df = n_clusters - 1) and the whole-cluster percentile bootstrap CI
(seed=20260731, n_boot=10000). It adds only two things that script does not
compute: (1) the flip DIRECTION breakdown (correct->wrong, wrong->correct,
wrong->wrong, plus a correct->correct-but-flipped residual that must be 0 when the
correct_letter is answer-key-preserved) and (2) a pooled-across-models per-arm
flip rate clustered on the cluster id (each cluster's observations across all four
models treated as one group — the conservative choice, since the same base
question answered by four models is nested inside one cluster).

Deps verified present in .venv (numpy 2.5.1, statsmodels 0.14.6, openpyxl 3.1.5),
so the QA-validated script is reused rather than re-implemented in stdlib.

READ-ONLY over the committed DB. Writes only flip_rate.csv / flip_rate.md in this
directory. No secrets are read or emitted.

Run:
  PYTHONPATH=code .venv/bin/python \
    data/experiment-C-2026-07-31/final/baseline-2fake-5050/openrouter-results/analyze_flip_rate_openrouter.py
"""
from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RUN_DIR = HERE.parent / "run"
REPO_ROOT = HERE.parents[4]  # .../tier1_mcq

# Make the harness package importable (the QA script's own parents[4] fallback
# points at a nonexistent data/code, so add the real code dir explicitly), then
# import the QA-validated module by file location and reuse its functions.
sys.path.insert(0, str(REPO_ROOT / "code"))
sys.path.insert(0, str(RUN_DIR))
import analyze_flip_rate as qa  # noqa: E402  (the QA-validated script)
from medrag_eval import db  # noqa: E402

DB_PATH = REPO_ROOT / "runs" / "expC-openrouter" / "expC_2fake_5050.sqlite"

ARMS = {
    "BM": {
        "control": "expC_2f_bm_control",
        "altered": "expC_2f_bm_altered",
        "cluster_workbook": RUN_DIR / "expC-bm-control.xlsx",
        "label": "biomarker",
    },
    "AN": {
        "control": "expC_2f_an_control",
        "altered": "expC_2f_an_altered",
        "cluster_workbook": RUN_DIR / "expC-an-control.xlsx",
        "label": "anatomy",
    },
}

# Task-requested model presentation order (exact OpenRouter IDs).
MODEL_ORDER = [
    "google/gemini-3.5-flash",
    "qwen/qwen3.7-max",
    "qwen/qwen3.6-35b-a3b",
    "google/gemma-4-26b-a4b-it",
]


def direction_and_pairs(control_answers, altered_answers, cluster_map):
    """Per (provider, model): direction counts + the paired (flip, cluster) vectors.

    Uses EXACTLY the QA script's exclusion rule (both sides must parse to a usable
    letter via qa.COMPLETE_PARSE_STATUSES, and the question must carry a cluster).
    Direction is defined by strict_correct on each side of a flip:
      correct(1)->wrong(0), wrong(0)->correct(1), wrong(0)->wrong(0).
    A correct(1)->correct(1) pair whose letter changed is impossible when the
    correct_letter is preserved; it is counted separately as a residual guard so
    nothing is ever silently dropped.
    """
    provider_models = sorted(set(control_answers) & set(altered_answers))
    per_model = {}
    for provider, model in provider_models:
        ctrl_by_q = control_answers[(provider, model)]
        alt_by_q = altered_answers[(provider, model)]
        qids = sorted(set(ctrl_by_q) & set(alt_by_q))

        flips, clusters = [], []
        c2w = w2c = w2w = cc_flip = 0
        excluded_unparsed = excluded_no_cluster = 0
        for qid in qids:
            c = ctrl_by_q[qid]
            a = alt_by_q[qid]
            if (
                c["parse_status"] not in qa.COMPLETE_PARSE_STATUSES
                or a["parse_status"] not in qa.COMPLETE_PARSE_STATUSES
            ):
                excluded_unparsed += 1
                continue
            cluster = cluster_map.get(qid)
            if cluster is None:
                excluded_no_cluster += 1
                continue
            flipped = c["selected_letter"] != a["selected_letter"]
            flips.append(1 if flipped else 0)
            clusters.append(cluster)
            if flipped:
                cc, ac = int(c["strict_correct"]), int(a["strict_correct"])
                if cc == 1 and ac == 0:
                    c2w += 1
                elif cc == 0 and ac == 1:
                    w2c += 1
                elif cc == 0 and ac == 0:
                    w2w += 1
                else:  # cc == 1 and ac == 1
                    cc_flip += 1
        per_model[(provider, model)] = {
            "flips": np.array(flips, dtype=float),
            "clusters": np.array(clusters),
            "n_paired": len(qids),
            "n_scored": len(flips),
            "excluded_unparsed": excluded_unparsed,
            "excluded_no_cluster": excluded_no_cluster,
            "c2w": c2w,
            "w2c": w2c,
            "w2w": w2w,
            "cc_flip": cc_flip,
        }
    return per_model


def main() -> int:
    conn = db.connect(DB_PATH)
    try:
        rows_out = []
        pooled_out = []
        md_sections = []
        residual_total = 0

        for arm in ("BM", "AN"):
            cfg = ARMS[arm]
            cluster_map = qa.load_cluster_map(cfg["cluster_workbook"])
            control_answers = qa.load_answers(conn, cfg["control"])
            altered_answers = qa.load_answers(conn, cfg["altered"])

            # Authoritative flip-rate + CIs straight from the QA-validated code.
            qa_rows = {
                (r["provider"], r["model"]): r
                for r in qa.compute_flip_table(control_answers, altered_answers, cluster_map)
            }
            # Direction counts + raw paired vectors (added here).
            dirs = direction_and_pairs(control_answers, altered_answers, cluster_map)

            models_present = [(p, m) for (p, m) in dirs]
            ordered = sorted(
                models_present,
                key=lambda pm: (MODEL_ORDER.index(pm[1]) if pm[1] in MODEL_ORDER else 99, pm[1]),
            )

            pooled_flips, pooled_clusters = [], []
            arm_c2w = arm_w2c = arm_w2w = 0
            for provider, model in ordered:
                d = dirs[(provider, model)]
                qa_r = qa_rows[(provider, model)]

                # Consistency guard: our independent flip count must match the QA code.
                qa_flip_count = round(qa_r["flip_rate"] * qa_r["n_scored"])
                my_flip_count = int(d["flips"].sum())
                assert qa_flip_count == my_flip_count, (
                    f"flip-count mismatch {arm} {model}: qa={qa_flip_count} mine={my_flip_count}"
                )
                # Direction categories must partition the flips (no residual expected).
                assert d["c2w"] + d["w2c"] + d["w2w"] + d["cc_flip"] == my_flip_count
                residual_total += d["cc_flip"]

                pooled_flips.extend(d["flips"].tolist())
                pooled_clusters.extend(d["clusters"].tolist())
                arm_c2w += d["c2w"]
                arm_w2c += d["w2c"]
                arm_w2w += d["w2w"]

                rows_out.append(
                    {
                        "arm": arm,
                        "arm_label": cfg["label"],
                        "provider": provider,
                        "model": model,
                        "scope": "per_model",
                        "n_paired": qa_r["n_paired"],
                        "n_scored": qa_r["n_scored"],
                        "n_excluded_unparsed": qa_r["n_excluded_unparsed"],
                        "n_excluded_no_cluster": qa_r["n_excluded_no_cluster"],
                        "n_clusters": qa_r["n_clusters"],
                        "n_flips": my_flip_count,
                        "flip_rate": qa_r["flip_rate"],
                        "cluster_robust_se": qa_r["cluster_robust_se"],
                        "ci95_lo_analytic": qa_r["ci95_lo_analytic"],
                        "ci95_hi_analytic": qa_r["ci95_hi_analytic"],
                        "ci95_lo_bootstrap": qa_r["ci95_lo_bootstrap"],
                        "ci95_hi_bootstrap": qa_r["ci95_hi_bootstrap"],
                        "dir_correct_to_wrong": d["c2w"],
                        "dir_wrong_to_correct": d["w2c"],
                        "dir_wrong_to_wrong": d["w2w"],
                        "dir_correct_to_correct_flip": d["cc_flip"],
                        "accuracy_control": qa_r["accuracy_control"],
                        "accuracy_altered": qa_r["accuracy_altered"],
                        "note": qa_r["note"],
                    }
                )

            # Pooled across the four models, clustered on cluster id (conservative:
            # every model-question observation in a cluster is one group).
            y = np.array(pooled_flips, dtype=float)
            g = np.array(pooled_clusters)
            an = qa.cluster_robust_mean(y, g)
            blo, bhi = qa.cluster_bootstrap_ci(y, g)
            pooled_out.append(
                {
                    "arm": arm,
                    "arm_label": cfg["label"],
                    "provider": "openrouter",
                    "model": "POOLED (4 models)",
                    "scope": "pooled_arm",
                    "n_paired": len(y),
                    "n_scored": len(y),
                    "n_excluded_unparsed": 0,
                    "n_excluded_no_cluster": 0,
                    "n_clusters": an["n_clusters"],
                    "n_flips": int(y.sum()),
                    "flip_rate": an["mean"],
                    "cluster_robust_se": an["se"],
                    "ci95_lo_analytic": an["ci_lo"],
                    "ci95_hi_analytic": an["ci_hi"],
                    "ci95_lo_bootstrap": blo,
                    "ci95_hi_bootstrap": bhi,
                    "dir_correct_to_wrong": arm_c2w,
                    "dir_wrong_to_correct": arm_w2c,
                    "dir_wrong_to_wrong": arm_w2w,
                    "dir_correct_to_correct_flip": 0,
                    "accuracy_control": float("nan"),
                    "accuracy_altered": float("nan"),
                    "note": "pooled across 4 models; clustered on cluster id",
                }
            )

        all_rows = rows_out + pooled_out

        fieldnames = [
            "arm", "arm_label", "provider", "model", "scope",
            "n_paired", "n_scored", "n_excluded_unparsed", "n_excluded_no_cluster",
            "n_clusters", "n_flips", "flip_rate", "cluster_robust_se",
            "ci95_lo_analytic", "ci95_hi_analytic", "ci95_lo_bootstrap", "ci95_hi_bootstrap",
            "dir_correct_to_wrong", "dir_wrong_to_correct", "dir_wrong_to_wrong",
            "dir_correct_to_correct_flip", "accuracy_control", "accuracy_altered", "note",
        ]
        csv_path = HERE / "flip_rate.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(all_rows)

        write_md(HERE / "flip_rate.md", rows_out, pooled_out, residual_total)

        # Echo a compact table for the console / log.
        print(f"residual correct->correct-but-flipped across all cells: {residual_total}")
        for r in all_rows:
            print(
                f"{r['arm']:2} {r['model']:26} flip={r['flip_rate']*100:5.2f}% "
                f"CI[{r['ci95_lo_analytic']*100:6.2f},{r['ci95_hi_analytic']*100:6.2f}] "
                f"boot[{r['ci95_lo_bootstrap']*100:5.2f},{r['ci95_hi_bootstrap']*100:5.2f}] "
                f"nflip={r['n_flips']:2} C2W={r['dir_correct_to_wrong']} "
                f"W2C={r['dir_wrong_to_correct']} W2W={r['dir_wrong_to_wrong']} "
                f"ncl={r['n_clusters']}"
            )
        print(f"\nWrote {csv_path}")
        print(f"Wrote {HERE / 'flip_rate.md'}")
    finally:
        conn.close()
    return 0


def fmt_pct(x):
    return "n/a" if x != x else f"{x*100:.2f}%"


def fmt_ci(lo, hi):
    if lo != lo or hi != hi:
        return "n/a"
    return f"[{lo*100:.2f}%, {hi*100:.2f}%]"


def write_md(path: Path, rows_out, pooled_out, residual_total):
    lines = []
    A = lines.append
    A("# Experiment C (2-fake / 50-50 baseline) — OpenRouter answer-flip analysis (Analyst 2)")
    A("")
    A("**Primary outcome: per-question answer FLIP** (did the selected letter change between the")
    A("CONTROL and ALTERED version of the same base question). Accuracy columns are secondary/supporting")
    A("(the altered set is *not* clinically certified answer-key-preserving).")
    A("")
    A("## Provenance (cite verbatim)")
    A("")
    A("- Date **2026-08-05**. Provider: **OpenRouter only**. temperature=0, single-shot (runs=1),")
    A("  prompt_version = harness default `BENCHMARK_PROMPT_VERSION` (`mcq_es_v4`).")
    A("- 4 models: `google/gemini-3.5-flash`, `qwen/qwen3.7-max`, `qwen/qwen3.6-35b-a3b`,")
    A("  `google/gemma-4-26b-a4b-it`.")
    A("- 4 experiments, 100 PRIMARY questions each: `expC_2f_bm_control`, `expC_2f_bm_altered`,")
    A("  `expC_2f_an_control`, `expC_2f_an_altered`. Arms: **BM** (biomarker), **AN** (anatomy); each")
    A("  pairs a CONTROL (unchanged) and an ALTERED (control + one fabricated finding) version of the")
    A("  SAME 100 base questions.")
    A("- Result health (harness status): every experiment planned=400 completed=400 api_failed=0")
    A("  parse_failed=0; 100% parse; 1600/1600 calls. OpenRouter spend ~$7.79.")
    A("- Read-only DB: `/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq/runs/expC-openrouter/expC_2fake_5050.sqlite`")
    A("- Cluster ids (independence unit) from the run-ready workbooks:")
    A("  `.../baseline-2fake-5050/run/expC-bm-control.xlsx` (BM, 33 clusters) and")
    A("  `.../baseline-2fake-5050/run/expC-an-control.xlsx` (AN, 34 clusters).")
    A("")
    A("## Method")
    A("")
    A("- Reused the QA-validated `run/analyze_flip_rate.py` (imported as a module) for the pairing,")
    A("  the exclusion rule, and BOTH cluster-robust 95% CIs. Deps verified present in `.venv`")
    A("  (numpy 2.5.1, statsmodels 0.14.6, openpyxl 3.1.5), so it was reused rather than")
    A("  re-implemented in stdlib.")
    A("- **Pairing**: by `base_question_id` (the DB `question_id`, e.g. `b1`), which is identical")
    A("  across CONTROL and ALTERED within an arm (BM 100/100, AN 100/100 intersect). Flip = 1 when")
    A("  `selected_letter` differs CONTROL vs ALTERED.")
    A("- **Exclusions**: a pair is dropped only if either side failed to parse to a usable letter")
    A("  (`parse_status` not in {ok, ok_conflict}) or the question lacks a cluster. Observed")
    A("  exclusions = **0** everywhere (parse was 100%).")
    A("- **Analytic CI (CR1)**: statsmodels OLS of the 0/1 flip vector on an intercept,")
    A("  `cov_type=\"cluster\"` on the cluster id, t-interval with df = n_clusters - 1.")
    A("- **Bootstrap CI**: whole-cluster percentile bootstrap (resample clusters with replacement,")
    A("  carrying every question in a sampled cluster), n_boot=10000, seed=20260731.")
    A("- **Flip DIRECTION** (added here; among flips only, by `strict_correct` each side):")
    A("  correct->wrong, wrong->correct, wrong->wrong. `correct_letter` is identical CONTROL vs")
    A(f"  ALTERED for all 100 questions in both arms, so a correct->correct flip is impossible;")
    A(f"  the residual guard counted **{residual_total}** such cases (expected 0).")
    A("- **Pooled per arm**: all four models stacked, clustered on the cluster id (each cluster's")
    A("  observations across all models = one group; the conservative choice because the same base")
    A("  question answered by four models is nested in one cluster). Pooling mixes heterogeneous")
    A("  models, so treat the pooled number as a descriptive summary, not a per-model estimate.")
    A("")

    def table(rows, header):
        A(f"### {header}")
        A("")
        A("| model | n | flips | flip rate | 95% CI (CR1) | 95% CI (bootstrap) | clusters | C->W | W->C | W->W | acc ctrl | acc alt |")
        A("|---|--:|--:|--:|---|---|--:|--:|--:|--:|--:|--:|")
        for r in rows:
            A(
                f"| `{r['model']}` | {r['n_scored']} | {r['n_flips']} | {fmt_pct(r['flip_rate'])} | "
                f"{fmt_ci(r['ci95_lo_analytic'], r['ci95_hi_analytic'])} | "
                f"{fmt_ci(r['ci95_lo_bootstrap'], r['ci95_hi_bootstrap'])} | {r['n_clusters']} | "
                f"{r['dir_correct_to_wrong']} | {r['dir_wrong_to_correct']} | {r['dir_wrong_to_wrong']} | "
                f"{fmt_pct(r['accuracy_control'])} | {fmt_pct(r['accuracy_altered'])} |"
            )
        A("")

    A("## Results")
    A("")
    for arm, label in (("BM", "biomarker"), ("AN", "anatomy")):
        per = [r for r in rows_out if r["arm"] == arm]
        pool = [r for r in pooled_out if r["arm"] == arm]
        table(per, f"Arm {arm} ({label}) — per model")
        table(pool, f"Arm {arm} ({label}) — pooled across 4 models")

    A("## Notes")
    A("")
    A("- The analytic CR1 Wald interval can dip below 0% for the lowest flip rates (normal")
    A("  approximation on a rare 0/1 proportion with few clusters); the whole-cluster bootstrap")
    A("  interval stays within [0%, 100%] and is the more trustworthy bound in those cells. Both")
    A("  are reported; neither is clamped.")
    A("- Flip rates are low across the board, consistent with the fabricated finding rarely moving")
    A("  the selected letter under this 2-fake / 50-50 baseline.")
    A("- Accuracy deltas are supporting only; the altered answer key is not clinically certified.")
    A("")
    A("## Reproduce")
    A("")
    A("```")
    A("PYTHONPATH=code .venv/bin/python \\")
    A("  data/experiment-C-2026-07-31/final/baseline-2fake-5050/openrouter-results/analyze_flip_rate_openrouter.py")
    A("```")
    A("")
    path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
