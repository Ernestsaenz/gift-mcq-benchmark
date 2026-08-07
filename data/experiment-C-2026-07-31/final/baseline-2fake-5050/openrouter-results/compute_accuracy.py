#!/usr/bin/env python
"""Experiment C (2-fake/50-50 baseline) -- OpenRouter strict-accuracy analysis (Analyst 1).

Re-derives strict accuracy PER (model, experiment) straight from the raw run DB,
using the harness's OWN "latest attempt/parse/score per logical call" query
(medrag_eval.db.summary_rows) so these numbers match exactly what
`medrag-eval export --format csv` / the harness `status` command would score.
Nothing here trusts the harness stdout; every count is recomputed from the DB.

strict accuracy for a cell = sum(strict_correct) / 100   (per task spec: /100).
All four cells are additionally reported with their parsed/scored denominators so
the /100 denominator is auditable (here every cell is 100/100 parsed ok).

DB (READ-ONLY input):
  runs/expC-openrouter/expC_2fake_5050.sqlite
Experiments: expC_2f_bm_control, expC_2f_bm_altered, expC_2f_an_control, expC_2f_an_altered.

Outputs (written ONLY under .../baseline-2fake-5050/openrouter-results/):
  accuracy.csv   -- per-model x arm CONTROL/ALTERED accuracy + delta + unique-control.
  accuracy_long.csv -- one row per (model, experiment) cell, with denominators.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path("/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq")
DB_PATH = REPO / "runs/expC-openrouter/expC_2fake_5050.sqlite"
BASELINE_JSON = REPO / "data/experiment-C-2026-07-31/final/baseline-2fake-5050/baseline.json"
OUT_DIR = REPO / "data/experiment-C-2026-07-31/final/baseline-2fake-5050/openrouter-results"

sys.path.insert(0, str(REPO / "code"))
from medrag_eval import db  # noqa: E402

COMPLETE_PARSE_STATUSES = {"ok", "ok_conflict"}

EXPERIMENTS = {
    ("BM", "control"): "expC_2f_bm_control",
    ("BM", "altered"): "expC_2f_bm_altered",
    ("AN", "control"): "expC_2f_an_control",
    ("AN", "altered"): "expC_2f_an_altered",
}

MODELS = [
    "google/gemini-3.5-flash",
    "qwen/qwen3.7-max",
    "qwen/qwen3.6-35b-a3b",
    "google/gemma-4-26b-a4b-it",
]


def load_cell(conn, experiment_name):
    """(model) -> {question_id: {selected_letter, parse_status, strict_correct}} for one experiment."""
    out = defaultdict(dict)
    for row in db.summary_rows(conn, experiment_name):
        r = dict(row)
        out[r["model"]][r["question_id"]] = {
            "selected_letter": r["selected_letter"],
            "parse_status": r["parse_status"],
            "strict_correct": r["strict_correct"],
        }
    return out


def cell_accuracy(by_model, model):
    """Return dict with n_scored, n_parsed_ok, n_correct, accuracy(/100)."""
    rows = by_model.get(model, {})
    n_scored = len(rows)
    n_parsed_ok = sum(1 for v in rows.values() if v["parse_status"] in COMPLETE_PARSE_STATUSES)
    n_correct = sum(int(v["strict_correct"]) for v in rows.values() if v["strict_correct"] is not None)
    accuracy = n_correct / 100.0  # task spec: strict_correct / 100
    return {
        "n_scored": n_scored,
        "n_parsed_ok": n_parsed_ok,
        "n_correct": n_correct,
        "accuracy": accuracy,
    }


def main():
    conn = db.connect(DB_PATH)
    try:
        cells = {key: load_cell(conn, name) for key, name in EXPERIMENTS.items()}
    finally:
        conn.close()

    # ---- Per (model, experiment) long table + per-model wide table --------------
    long_rows = []
    wide_rows = []
    per_model_struct = {}

    for model in MODELS:
        rec = {}
        for arm in ("BM", "AN"):
            for cond in ("control", "altered"):
                c = cell_accuracy(cells[(arm, cond)], model)
                rec[(arm, cond)] = c
                long_rows.append({
                    "model": model,
                    "experiment": EXPERIMENTS[(arm, cond)],
                    "arm": arm,
                    "condition": cond,
                    "n_scored": c["n_scored"],
                    "n_parsed_ok": c["n_parsed_ok"],
                    "n_correct": c["n_correct"],
                    "strict_accuracy": round(c["accuracy"], 4),
                })
        bm_delta = rec[("BM", "altered")]["accuracy"] - rec[("BM", "control")]["accuracy"]
        an_delta = rec[("AN", "altered")]["accuracy"] - rec[("AN", "control")]["accuracy"]

        # ---- unique-control accuracy over the union of BM+AN control questions ----
        bm_ctrl = cells[("BM", "control")].get(model, {})
        an_ctrl = cells[("AN", "control")].get(model, {})
        bm_ids = set(bm_ctrl)
        an_ids = set(an_ctrl)
        shared = bm_ids & an_ids
        union = bm_ids | an_ids
        # agreement diagnostic on shared control questions (byte-identical prompts)
        shared_agree_letter = sum(
            1 for q in shared if bm_ctrl[q]["selected_letter"] == an_ctrl[q]["selected_letter"]
        )
        shared_agree_correct = sum(
            1 for q in shared if int(bm_ctrl[q]["strict_correct"]) == int(an_ctrl[q]["strict_correct"])
        )
        # unique-control correctness: each unique question counted once; shared
        # questions contribute the mean of their two (near-deterministic) observations.
        total = 0.0
        for q in union:
            if q in shared:
                total += (int(bm_ctrl[q]["strict_correct"]) + int(an_ctrl[q]["strict_correct"])) / 2.0
            elif q in bm_ids:
                total += int(bm_ctrl[q]["strict_correct"])
            else:
                total += int(an_ctrl[q]["strict_correct"])
        unique_control_acc = total / len(union)

        per_model_struct[model] = {
            "bm_control_accuracy": round(rec[("BM", "control")]["accuracy"], 4),
            "bm_altered_accuracy": round(rec[("BM", "altered")]["accuracy"], 4),
            "an_control_accuracy": round(rec[("AN", "control")]["accuracy"], 4),
            "an_altered_accuracy": round(rec[("AN", "altered")]["accuracy"], 4),
            "bm_altered_minus_control": round(bm_delta, 4),
            "an_altered_minus_control": round(an_delta, 4),
            "unique_control_accuracy": round(unique_control_acc, 4),
            "n_unique_control_questions": len(union),
            "n_shared_control_questions": len(shared),
            "shared_control_letter_agreement": f"{shared_agree_letter}/{len(shared)}",
            "shared_control_correctness_agreement": f"{shared_agree_correct}/{len(shared)}",
            "bm_control_n_correct": rec[("BM", "control")]["n_correct"],
            "bm_altered_n_correct": rec[("BM", "altered")]["n_correct"],
            "an_control_n_correct": rec[("AN", "control")]["n_correct"],
            "an_altered_n_correct": rec[("AN", "altered")]["n_correct"],
        }

        wide_rows.append({
            "model": model,
            "bm_control_accuracy": round(rec[("BM", "control")]["accuracy"], 4),
            "bm_altered_accuracy": round(rec[("BM", "altered")]["accuracy"], 4),
            "bm_altered_minus_control_delta": round(bm_delta, 4),
            "an_control_accuracy": round(rec[("AN", "control")]["accuracy"], 4),
            "an_altered_accuracy": round(rec[("AN", "altered")]["accuracy"], 4),
            "an_altered_minus_control_delta": round(an_delta, 4),
            "unique_control_accuracy": round(unique_control_acc, 4),
            "n_unique_control_questions": len(union),
            "n_shared_control_questions": len(shared),
            "shared_control_letter_agreement": f"{shared_agree_letter}/{len(shared)}",
        })

    # ---- write CSVs -------------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wide_fields = [
        "model",
        "bm_control_accuracy", "bm_altered_accuracy", "bm_altered_minus_control_delta",
        "an_control_accuracy", "an_altered_accuracy", "an_altered_minus_control_delta",
        "unique_control_accuracy", "n_unique_control_questions",
        "n_shared_control_questions", "shared_control_letter_agreement",
    ]
    with (OUT_DIR / "accuracy.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=wide_fields)
        w.writeheader()
        w.writerows(wide_rows)

    long_fields = ["model", "experiment", "arm", "condition",
                   "n_scored", "n_parsed_ok", "n_correct", "strict_accuracy"]
    with (OUT_DIR / "accuracy_long.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=long_fields)
        w.writeheader()
        w.writerows(long_rows)

    # ---- console diagnostics ----------------------------------------------------
    print("DB:", DB_PATH)
    print("Total scored logical calls across 16 cells:",
          sum(r["n_scored"] for r in long_rows))
    print("Total parsed_ok across 16 cells:",
          sum(r["n_parsed_ok"] for r in long_rows))
    print()
    hdr = f"{'model':26} {'BMc':>5} {'BMa':>5} {'dBM':>6} {'ANc':>5} {'ANa':>5} {'dAN':>6} {'uniqC':>6} {'nUniq':>5} {'shrAgr':>7}"
    print(hdr)
    for r in wide_rows:
        print(f"{r['model']:26} "
              f"{r['bm_control_accuracy']*100:5.0f} {r['bm_altered_accuracy']*100:5.0f} "
              f"{r['bm_altered_minus_control_delta']*100:+6.0f} "
              f"{r['an_control_accuracy']*100:5.0f} {r['an_altered_accuracy']*100:5.0f} "
              f"{r['an_altered_minus_control_delta']*100:+6.0f} "
              f"{r['unique_control_accuracy']*100:6.1f} {r['n_unique_control_questions']:5} "
              f"{r['shared_control_letter_agreement']:>7}")

    # overlap check straight from baseline.json (source of truth for question sets)
    import json
    b = json.load(open(BASELINE_JSON))
    bm_bids = {x["base_question_id"] for x in b["arms"]["BM"]["primary"]}
    an_bids = {x["base_question_id"] for x in b["arms"]["AN"]["primary"]}
    print()
    print(f"baseline.json PRIMARY overlap (BM ∩ AN base_question_id): {len(bm_bids & an_bids)}")
    print(f"baseline.json PRIMARY union  (unique base questions):     {len(bm_bids | an_bids)}")

    return per_model_struct


if __name__ == "__main__":
    main()
