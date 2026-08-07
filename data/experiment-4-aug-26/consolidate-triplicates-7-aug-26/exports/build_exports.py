#!/usr/bin/env python3
"""
Consolidate the ab520 triplicate replication into three CSV exports.

Reads (read-only; the SQLite DB is opened via the file:...?mode=ro URI):
  - run1 CSV: benchmark-6000-cell-results-adjusted.csv (6000 rows, run_index=1)
  - frozen ledger: frozen-replicate-cell-ledger.csv (1796 rows, run_index 2/3)
  - sqlite DB: ab520-incorrect-cell-triplicates-2026-08-05.sqlite

Writes (this directory only):
  - consolidated-triplicates-898.csv
  - replicate-cell-level-1796.csv
  - run1-6000-with-replicate-status.csv

Does NOT write EXPORTS_README.md — that file is maintained by hand.

stdlib only (csv, json via sqlite3's json1 extension, sqlite3). No third
party dependencies. Run with: python3 build_exports.py
"""
import csv
import sqlite3
from collections import Counter, defaultdict

ROOT = "/Users/ernestsaenz/Programming/gift-project-compile/tier1_mcq"
BASE = ROOT + "/data/experiment-4-aug-26/consolidate-triplicates-7-aug-26"
RUN1_CSV = ROOT + "/data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04/exports/benchmark-6000-cell-results-adjusted.csv"
LEDGER_CSV = ROOT + "/data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/manifests/frozen-replicate-cell-ledger.csv"
DB_PATH = ROOT + "/data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite"
OUT_DIR = BASE + "/exports"

EXPERIMENT_TO_ARM = {
    "ab520_incorrect_triplicates_or_A_20260805": "openrouter_A",
    "ab520_incorrect_triplicates_or_B_20260805": "openrouter_B",
    "ab520_incorrect_triplicates_ts_A_20260805": "tailscale_A",
}
ARM_TO_CONDITION = {"openrouter_A": "A", "openrouter_B": "B", "tailscale_A": "A"}


def load_run1():
    with open(RUN1_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_key = {}
    for row in rows:
        assert row["run_index"] == "1"
        key = (row["arm"], row["question_id"], row["model"])
        assert key not in by_key, f"duplicate run1 key {key}"
        by_key[key] = row
    return rows, by_key


def load_ledger():
    with open(LEDGER_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows


def load_db_calls():
    """Return dict (arm, question_id, model, run_index[str]) -> info dict,
    covering all 1796 logical_calls (scored or exhausted)."""
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # All logical calls with question_id/model/run_index/arm
    cur.execute(
        """
        SELECT lc.id as lc_id, e.name as exp_name, q.question_id as question_id,
               q.correct_letter as db_correct_letter, lc.model as model,
               lc.run_index as run_index
        FROM logical_calls lc
        JOIN experiments e ON lc.experiment_id = e.id
        JOIN questions q ON lc.question_id = q.id
        """
    )
    calls = {r["lc_id"]: dict(r) for r in cur.fetchall()}

    # attempt counts per logical_call
    cur.execute(
        "SELECT logical_call_id, COUNT(*) as n FROM provider_attempts GROUP BY logical_call_id"
    )
    attempt_counts = {r["logical_call_id"]: r["n"] for r in cur.fetchall()}

    # scoring attempt details: scores -> parsed_answers -> provider_attempts
    # (the exact attempt that produced the recorded score, not simply the
    # latest attempt -- this avoids double-counting the 3 Vertex cells that
    # also carry an earlier failed AI Studio attempt).
    cur.execute(
        """
        SELECT sc.logical_call_id as lc_id,
               sc.correct_letter as correct_letter,
               sc.strict_correct as strict_correct,
               p.selected_letter as selected_letter,
               p.parse_status as parse_status,
               pa.request_sha256 as request_sha256,
               pa.latency_ms as latency_ms,
               pa.attempt_index as attempt_index,
               pa.status_code as status_code,
               COALESCE(json_extract(pa.request_json,'$.provider.order[0]'), '') as req_order,
               json_extract(pa.response_json,'$.provider') as resp_provider
        FROM scores sc
        JOIN parsed_answers p ON sc.parsed_answer_id = p.id
        JOIN provider_attempts pa ON p.provider_attempt_id = pa.id
        """
    )
    scoring = {r["lc_id"]: dict(r) for r in cur.fetchall()}
    con.close()

    result = {}
    for lc_id, c in calls.items():
        arm = EXPERIMENT_TO_ARM[c["exp_name"]]
        key = (arm, c["question_id"], c["model"], str(c["run_index"]))
        n_attempts = attempt_counts.get(lc_id, 0)
        sc = scoring.get(lc_id)
        if sc is not None:
            status = "scored"
            selected_letter = sc["selected_letter"]
            strict_correct = bool(sc["strict_correct"])
            parse_status = sc["parse_status"]
            request_sha256 = sc["request_sha256"]
            latency_ms = sc["latency_ms"]
            db_correct_letter = sc["correct_letter"]
            # Upstream: only meaningful/verified for the google/gemini-3.6-flash
            # model served through openrouter (see PROTOCOL DEVIATION in SPEC.md).
            # For all other models/arms the OpenRouter request never set
            # provider.order, and the resolved upstream (DeepInfra, Parasail,
            # AkashML, CoreWeave, SiliconFlow, Decart, Baidu, Venice, NextBit,
            # Phala, or occasionally "Google" for gemma -- see EXPORTS_README's
            # "Anomaly investigated and ruled out": Gemma's Google endpoint
            # supports temperature/top_p, unlike Gemini's, so that routing is
            # NOT a deviation) is a different kind of fact than the documented
            # Gemini AI-Studio-vs-Vertex split, so we leave upstream/
            # temperature_honoured at their defaults for those rows rather
            # than mislabeling them "google-ai-studio".
            upstream = None
            if arm == "openrouter_B" and c["model"] == "google/gemini-3.6-flash":
                if sc["resp_provider"] == "Google":
                    upstream = "google-vertex"
                elif sc["resp_provider"] == "Google AI Studio":
                    upstream = "google-ai-studio"
            elif arm == "openrouter_A" and c["model"] == "google/gemini-3.6-flash":
                if sc["resp_provider"] == "Google AI Studio":
                    upstream = "google-ai-studio"
                elif sc["resp_provider"] == "Google":
                    upstream = "google-vertex"
            temperature_honoured = not (upstream == "google-vertex")
        else:
            status = "exhausted"
            selected_letter = None
            strict_correct = None
            parse_status = None
            request_sha256 = None
            latency_ms = None
            db_correct_letter = c["db_correct_letter"]
            upstream = None
            temperature_honoured = True  # no evidence otherwise; protocol declared temp=0

        result[key] = dict(
            lc_id=lc_id,
            status=status,
            selected_letter=selected_letter,
            strict_correct=strict_correct,
            parse_status=parse_status,
            request_sha256=request_sha256,
            latency_ms=latency_ms,
            n_attempts=n_attempts,
            db_correct_letter=db_correct_letter,
            upstream=upstream,
            temperature_honoured=temperature_honoured,
        )
    return result


def tf(v):
    if v is None:
        return ""
    return "TRUE" if v else "FALSE"


def main():
    run1_rows, run1_by_key = load_run1()
    ledger_rows = load_ledger()
    db_calls = load_db_calls()

    # sanity: ledger keys should all resolve in db_calls
    join_failures = []
    for lr in ledger_rows:
        key = (lr["arm"], lr["question_id"], lr["model"], lr["run_index"])
        if key not in db_calls:
            join_failures.append(key)

    # sanity: run1 strict_correct==0 count should equal 898, and every such
    # cell should have a (arm,qid,model) matching a ledger group of 2 rows.
    strict_incorrect_keys = {
        (row["arm"], row["question_id"], row["model"])
        for row in run1_rows
        if row["strict_correct"] == "0"
    }

    # group ledger rows by cell (arm, question_id, model)
    ledger_by_cell = defaultdict(list)
    for lr in ledger_rows:
        cell_key = (lr["arm"], lr["question_id"], lr["model"])
        ledger_by_cell[cell_key].append(lr)

    cell_join_failures = [k for k in strict_incorrect_keys if k not in ledger_by_cell]
    extra_ledger_cells = [k for k in ledger_by_cell if k not in strict_incorrect_keys]

    # ---------- Export 2: replicate-cell-level-1796.csv ----------
    rep_fields = [
        "arm", "source_key", "question_id", "model", "run_index", "status",
        "selected_letter", "correct_letter", "strict_correct", "upstream",
        "temperature_honoured", "n_attempts", "latency_ms", "request_sha256",
        "parse_status",
    ]
    rep_out_rows = []
    for lr in ledger_rows:
        key = (lr["arm"], lr["question_id"], lr["model"], lr["run_index"])
        d = db_calls.get(key)
        if d is None:
            # should not happen; recorded in join_failures above
            continue
        rep_out_rows.append({
            "arm": lr["arm"],
            "source_key": lr["source_key"],
            "question_id": lr["question_id"],
            "model": lr["model"],
            "run_index": lr["run_index"],
            "status": d["status"],
            "selected_letter": d["selected_letter"] or "",
            "correct_letter": lr["run1_correct_letter"],
            "strict_correct": tf(d["strict_correct"]),
            "upstream": d["upstream"] or "",
            "temperature_honoured": tf(d["temperature_honoured"]),
            "n_attempts": d["n_attempts"],
            "latency_ms": d["latency_ms"] if d["latency_ms"] is not None else "",
            "request_sha256": d["request_sha256"] or "",
            "parse_status": d["parse_status"] or "",
        })

    # ---------- Export 1: consolidated-triplicates-898.csv ----------
    cons_fields = [
        "arm", "condition", "source_key", "question_id", "model",
        "correct_letter",
        "run1_selected_letter", "run1_strict_correct",
        "run2_selected_letter", "run2_strict_correct", "run2_status",
        "run3_selected_letter", "run3_strict_correct", "run3_status",
        "n_runs_scored",
        "run2_upstream", "run3_upstream",
        "temperature_honoured",
        "flipped_to_correct",
        "n_correct_across_replicates",
    ]
    cons_out_rows = []
    for cell_key in sorted(strict_incorrect_keys):
        arm, qid, model = cell_key
        run1_row = run1_by_key[cell_key]
        lrows = sorted(ledger_by_cell.get(cell_key, []), key=lambda r: r["run_index"])
        by_run = {r["run_index"]: r for r in lrows}
        r2_ledger = by_run.get("2")
        r3_ledger = by_run.get("3")

        def cell_for(run_ledger, run_index):
            if run_ledger is None:
                return dict(status="missing", selected_letter="", strict_correct=None,
                            upstream=None, temperature_honoured=None)
            key2 = (arm, qid, model, run_index)
            d = db_calls.get(key2)
            if d is None:
                return dict(status="missing", selected_letter="", strict_correct=None,
                            upstream=None, temperature_honoured=None)
            return d

        d2 = cell_for(r2_ledger, "2")
        d3 = cell_for(r3_ledger, "3")

        n_runs_scored = sum(1 for d in (d2, d3) if d["status"] == "scored")
        n_correct = sum(
            1 for d in (d2, d3) if d["status"] == "scored" and d["strict_correct"]
        )
        flipped = n_correct > 0

        # temperature_honoured at the cell level: FALSE if EITHER replicate
        # was served by google-vertex (i.e. any replicate's temp was dropped)
        cell_temp_honoured = True
        for d in (d2, d3):
            if d.get("upstream") == "google-vertex":
                cell_temp_honoured = False

        cons_out_rows.append({
            "arm": arm,
            "condition": ARM_TO_CONDITION[arm],
            "source_key": run1_row["source_key"],
            "question_id": qid,
            "model": model,
            "correct_letter": run1_row["correct_letter"],
            "run1_selected_letter": run1_row["selected_letter"],
            "run1_strict_correct": tf(run1_row["strict_correct"] == "1"),
            "run2_selected_letter": d2["selected_letter"] or "",
            "run2_strict_correct": tf(d2["strict_correct"]) if d2["status"] == "scored" else "",
            "run2_status": d2["status"],
            "run3_selected_letter": d3["selected_letter"] or "",
            "run3_strict_correct": tf(d3["strict_correct"]) if d3["status"] == "scored" else "",
            "run3_status": d3["status"],
            "n_runs_scored": n_runs_scored,
            "run2_upstream": d2.get("upstream") or "",
            "run3_upstream": d3.get("upstream") or "",
            "temperature_honoured": tf(cell_temp_honoured),
            "flipped_to_correct": tf(flipped),
            "n_correct_across_replicates": n_correct,
        })

    # ---------- Export 3: run1-6000-with-replicate-status.csv ----------
    run1_out_fields = list(run1_rows[0].keys()) + ["was_replicated", "replicate_outcome"]
    run1_out_rows = []
    cons_by_cell = {(r["arm"], r["question_id"], r["model"]): r for r in cons_out_rows}
    for row in run1_rows:
        key = (row["arm"], row["question_id"], row["model"])
        out = dict(row)
        if key in cons_by_cell:
            c = cons_by_cell[key]
            out["was_replicated"] = "TRUE"
            if c["run2_status"] == "scored" and c["run3_status"] == "scored":
                outcome = "both_runs"
            elif c["run2_status"] == "scored" or c["run3_status"] == "scored":
                outcome = "one_run"
            else:
                outcome = "no_runs"
            out["replicate_outcome"] = outcome
        else:
            out["was_replicated"] = "FALSE"
            out["replicate_outcome"] = "not_eligible"
        run1_out_rows.append(out)

    # ---------- Write CSVs ----------
    def write_csv(path, fieldnames, rows):
        with open(path, "w", newline="\n", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow(r)

    write_csv(f"{OUT_DIR}/consolidated-triplicates-898.csv", cons_fields, cons_out_rows)
    write_csv(f"{OUT_DIR}/replicate-cell-level-1796.csv", rep_fields, rep_out_rows)
    write_csv(f"{OUT_DIR}/run1-6000-with-replicate-status.csv", run1_out_fields, run1_out_rows)

    # ---------- Verification ----------
    print("=== VERIFICATION ===")
    print("consolidated rows:", len(cons_out_rows), "(expect 898)")
    print("replicate rows:", len(rep_out_rows), "(expect 1796)")
    print("run1 rows:", len(run1_out_rows), "(expect 6000)")
    print("join_failures (ledger key not in db_calls):", len(join_failures), join_failures[:10])
    print("cell_join_failures (strict-incorrect run1 cell w/o ledger group):", len(cell_join_failures), cell_join_failures[:10])
    print("extra_ledger_cells (ledger cell not in strict-incorrect set):", len(extra_ledger_cells), extra_ledger_cells[:10])

    total_scored = sum(1 for r in rep_out_rows if r["status"] == "scored")
    print("total scored (replicate rows):", total_scored, "(expect 1788)")

    scored_by_arm = Counter(r["arm"] for r in rep_out_rows if r["status"] == "scored")
    print("scored per arm:", dict(scored_by_arm), "(expect or_A 406, or_B 1057, ts_A 325)")

    both_runs = sum(1 for r in cons_out_rows if r["n_runs_scored"] == 2)
    one_run = sum(1 for r in cons_out_rows if r["n_runs_scored"] == 1)
    no_runs = sum(1 for r in cons_out_rows if r["n_runs_scored"] == 0)
    print(f"completeness: both={both_runs} one={one_run} none={no_runs} (expect 893/2/3)")

    gemini_b_scored = [r for r in rep_out_rows if r["arm"] == "openrouter_B" and r["model"] == "google/gemini-3.6-flash" and r["status"] == "scored"]
    vertex_ct = sum(1 for r in gemini_b_scored if r["upstream"] == "google-vertex")
    aistudio_ct = sum(1 for r in gemini_b_scored if r["upstream"] == "google-ai-studio")
    print(f"gemini_B scored: {len(gemini_b_scored)} vertex={vertex_ct} ai-studio={aistudio_ct} (expect 93 total, 91 vertex, 2 ai-studio)")

    was_repl_true = sum(1 for r in run1_out_rows if r["was_replicated"] == "TRUE")
    print("run1 rows marked was_replicated=TRUE:", was_repl_true, "(expect 898)")

    outcome_counts = Counter(r["replicate_outcome"] for r in run1_out_rows)
    print("replicate_outcome counts:", dict(outcome_counts))

    # correct_letter cross-check: ledger run1_correct_letter vs run1 csv correct_letter
    mismatches = 0
    for lr in ledger_rows:
        key = (lr["arm"], lr["question_id"], lr["model"])
        r1 = run1_by_key.get(key)
        if r1 and r1["correct_letter"] != lr["run1_correct_letter"]:
            mismatches += 1
    print("ledger vs run1-csv correct_letter mismatches:", mismatches)

    # parse_status anomaly check
    parse_statuses = Counter(r["parse_status"] for r in rep_out_rows if r["status"] == "scored")
    print("parse_status distribution (scored rows):", dict(parse_statuses))

    return {
        "join_failures": join_failures,
        "cell_join_failures": cell_join_failures,
        "extra_ledger_cells": extra_ledger_cells,
        "mismatches": mismatches,
    }


if __name__ == "__main__":
    main()
