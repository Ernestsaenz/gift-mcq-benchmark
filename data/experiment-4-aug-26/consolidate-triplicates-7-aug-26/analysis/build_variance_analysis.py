#!/usr/bin/env python3
"""
Flip-rate / determinism analysis for the ab520 incorrect-cell triplicate
replication (runs 2 and 3 of the 898 questions each model got strictly wrong
on run 1).

Reads the frozen replicate DB READ-ONLY (mode=ro URI) and writes three CSVs
plus a written report into this folder's own `analysis/` directory. Writes
nothing outside `analysis/`. Uses only the Python standard library.

Ground truth for all counts and the Vertex protocol deviation: see
../SPEC.md. Every number this script produces is checked against SPEC.md's
authoritative figures before being trusted (see the assertions in main()).
"""
import csv
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]  # .../tier1_mcq
DB_PATH = (
    REPO_ROOT
    / "data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05"
    / "runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite"
)
OUT_DIR = Path(__file__).resolve().parent

ARM_BY_EXPERIMENT_ID = {
    1: "openrouter_A",
    2: "openrouter_B",
    3: "tailscale_A",
}

MODEL_SHORT = {
    "google/gemini-3.6-flash": "gemini",
    "google/gemma-4-26b-a4b-it": "gemma",
    "qwen/qwen3.6-35b-a3b": "qwen",
    "z-ai/glm-5.2": "glm",
}

Z_95 = 1.959963984540054  # 97.5th percentile of the standard normal


def wilson_interval(successes, n, z=Z_95):
    """95% Wilson score interval for a binomial proportion.

    Chosen over the normal (Wald) approximation because several of our
    denominators are small (single digits to low tens for some model x arm
    cells, e.g. openrouter_A gemini n=18) and several flip counts are near 0,
    where Wald intervals can extend below 0 or above 1 and are known to
    under-cover. Wilson stays inside [0,1] and has good coverage even at
    small n and proportions near the boundary.
    """
    if n == 0:
        return (None, None)
    phat = successes / n
    denom = 1 + z * z / n
    center = phat + z * z / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    lower = (center - half) / denom
    upper = (center + half) / denom
    return (max(0.0, lower), min(1.0, upper))


def load_rows(conn):
    """One row per logical call (arm, model, qid, run_index) with scoring
    outcome and, for scored rows, the upstream that served the SCORING
    attempt (per SPEC.md's attribution rule -- via the parsed_answer that
    the score actually points to, not attempt history)."""
    query = """
    SELECT
        lc.experiment_id,
        lc.model,
        q.question_id AS qid,
        lc.run_index,
        s.id AS score_id,
        s.strict_correct,
        pab.selected_letter,
        COALESCE(json_extract(pa.request_json, '$.provider.order[0]'), 'google-ai-studio') AS upstream
    FROM logical_calls lc
    JOIN questions q ON q.id = lc.question_id
    LEFT JOIN scores s ON s.logical_call_id = lc.id
    LEFT JOIN parsed_answers pab ON pab.id = s.parsed_answer_id
    LEFT JOIN provider_attempts pa ON pa.id = pab.provider_attempt_id
    """
    return conn.execute(query).fetchall()


def build_cells(rows):
    """cells[(arm, model, qid)] = {2: {...} or None, 3: {...} or None}"""
    cells = defaultdict(lambda: {2: None, 3: None})
    for exp_id, model, qid, run_index, score_id, strict_correct, letter, upstream in rows:
        arm = ARM_BY_EXPERIMENT_ID[exp_id]
        key = (arm, model, qid)
        scored = score_id is not None
        cells[key][run_index] = {
            "scored": scored,
            "strict_correct": bool(strict_correct) if scored else None,
            "letter": letter if scored else None,
            "upstream": upstream if scored else None,
        }
    return cells


def temperature_regime_for(arm, model, upstreams_seen):
    """upstreams_seen: set of upstream strings observed among SCORED runs
    for this arm x model slice. Only openrouter_B / gemini ever contains a
    non-temperature_0 upstream (google-vertex); every other cell in the
    study declared and received temperature=0 (verified against
    provider_attempts.request_json)."""
    if arm != "openrouter_B" or model != "google/gemini-3.6-flash":
        return "temperature_0"
    non_vertex = upstreams_seen - {"google-vertex"}
    vertex = "google-vertex" in upstreams_seen
    if vertex and non_vertex:
        return "mixed"
    if vertex:
        return "vertex_default"
    return "temperature_0"


def aggregate(cells, group_key_fn):
    """group_key_fn(arm, model) -> grouping key (e.g. (arm, model) or (arm,))
    Returns dict[group_key] -> stats dict."""
    groups = defaultdict(lambda: {
        "n_cells": 0,
        "n_run2_scored": 0,
        "n_run3_scored": 0,
        "flips_run2": 0,
        "flips_run3": 0,
        "n_with_both_runs": 0,
        "cells_flipped_at_least_once": 0,
        "cells_flipped_both": 0,
        "upstreams_seen": set(),
    })

    for (arm, model, qid), runs in cells.items():
        gkey = group_key_fn(arm, model)
        g = groups[gkey]
        g["n_cells"] += 1

        r2 = runs[2]
        r3 = runs[3]

        r2_scored = r2 is not None and r2["scored"]
        r3_scored = r3 is not None and r3["scored"]
        r2_flip = r2_scored and r2["strict_correct"]
        r3_flip = r3_scored and r3["strict_correct"]

        if r2_scored:
            g["n_run2_scored"] += 1
            if r2_flip:
                g["flips_run2"] += 1
            g["upstreams_seen"].add(r2["upstream"])
        if r3_scored:
            g["n_run3_scored"] += 1
            if r3_flip:
                g["flips_run3"] += 1
            g["upstreams_seen"].add(r3["upstream"])
        if r2_scored and r3_scored:
            g["n_with_both_runs"] += 1
            if r2_flip and r3_flip:
                g["cells_flipped_both"] += 1
        if r2_flip or r3_flip:
            g["cells_flipped_at_least_once"] += 1

    return groups


def rows_from_groups(groups, key_names):
    out = []
    for gkey, g in sorted(groups.items()):
        denom = g["n_run2_scored"] + g["n_run3_scored"]
        flips = g["flips_run2"] + g["flips_run3"]
        rate = (flips / denom) if denom else None
        lo, hi = wilson_interval(flips, denom)
        arm = gkey[0]
        model = gkey[1] if len(gkey) > 1 else None
        # Arm-level (model is None) rows get their temperature_regime filled
        # in by the caller, which can see all models within the arm.
        regime = temperature_regime_for(arm, model, g["upstreams_seen"]) if model else None
        row = dict(zip(key_names, gkey))
        row.update({
            "n_cells": g["n_cells"],
            "n_with_both_runs": g["n_with_both_runs"],
            "n_run2_scored": g["n_run2_scored"],
            "n_run3_scored": g["n_run3_scored"],
            "flips_run2": g["flips_run2"],
            "flips_run3": g["flips_run3"],
            "cells_flipped_at_least_once": g["cells_flipped_at_least_once"],
            "cells_flipped_both": g["cells_flipped_both"],
            "flip_denominator_runs": denom,
            "flip_rate_per_run": f"{rate:.6f}" if rate is not None else "",
            "flip_rate_wilson_lower": f"{lo:.6f}" if lo is not None else "",
            "flip_rate_wilson_upper": f"{hi:.6f}" if hi is not None else "",
        })
        row["temperature_regime"] = regime
        out.append(row)
    return out


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def build_agreement(cells):
    """Per arm x model, and for openrouter_B/gemini also per upstream
    subgroup, agreement rate between run2 and run3 selected letters among
    cells where BOTH runs were scored."""
    groups = defaultdict(lambda: {"n_both": 0, "n_agree": 0})

    for (arm, model, qid), runs in cells.items():
        r2, r3 = runs[2], runs[3]
        if not (r2 and r2["scored"] and r3 and r3["scored"]):
            continue
        agree = r2["letter"] == r3["letter"]

        key_all = (arm, model, "all")
        groups[key_all]["n_both"] += 1
        groups[key_all]["n_agree"] += int(agree)

        if arm == "openrouter_B" and model == "google/gemini-3.6-flash":
            up2, up3 = r2["upstream"], r3["upstream"]
            sub = up2 if up2 == up3 else "cross_upstream"
            sub_label = {
                "google-vertex": "vertex_only",
                "google-ai-studio": "ai_studio_only",
            }.get(sub, sub)
            key_sub = (arm, model, sub_label)
            groups[key_sub]["n_both"] += 1
            groups[key_sub]["n_agree"] += int(agree)

    rows = []
    for (arm, model, subgroup), g in sorted(groups.items()):
        n, agree = g["n_both"], g["n_agree"]
        rate = (agree / n) if n else None
        lo, hi = wilson_interval(agree, n)
        regime_upstreams = set()
        if subgroup == "vertex_only":
            regime_upstreams = {"google-vertex"}
        elif subgroup == "ai_studio_only":
            regime_upstreams = {"google-ai-studio"}
        elif subgroup == "cross_upstream":
            regime_upstreams = {"google-vertex", "google-ai-studio"}
        else:
            regime_upstreams = {"google-vertex", "google-ai-studio"} if (
                arm == "openrouter_B" and model == "google/gemini-3.6-flash"
            ) else set()
        regime = temperature_regime_for(arm, model, regime_upstreams) if regime_upstreams else temperature_regime_for(arm, model, set())
        rows.append({
            "arm": arm,
            "model": model,
            "upstream_subgroup": subgroup,
            "n_cells_both_runs": n,
            "n_agree": agree,
            "agreement_rate": f"{rate:.6f}" if rate is not None else "",
            "agreement_rate_wilson_lower": f"{lo:.6f}" if lo is not None else "",
            "agreement_rate_wilson_upper": f"{hi:.6f}" if hi is not None else "",
            "temperature_regime": regime,
        })
    return rows


def main():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        rows = load_rows(conn)
    finally:
        conn.close()

    cells = build_cells(rows)

    # --- Sanity checks against SPEC.md's authoritative figures ---
    assert len(cells) == 898, f"expected 898 distinct cells, got {len(cells)}"
    n_logical_calls = sum(1 for c in cells.values() for r in (2, 3) if c[r] is not None)
    assert n_logical_calls == 1796, n_logical_calls
    n_scored = sum(1 for c in cells.values() for r in (2, 3) if c[r] and c[r]["scored"])
    assert n_scored == 1788, n_scored
    n_both = sum(1 for c in cells.values() if c[2] and c[2]["scored"] and c[3] and c[3]["scored"])
    assert n_both == 893, n_both
    n_one = sum(
        1 for c in cells.values()
        if (bool(c[2] and c[2]["scored"]) != bool(c[3] and c[3]["scored"]))
    )
    assert n_one == 2, n_one
    n_neither = sum(
        1 for c in cells.values()
        if not (c[2] and c[2]["scored"]) and not (c[3] and c[3]["scored"])
    )
    assert n_neither == 3, n_neither
    print(f"Sanity checks OK: {len(cells)} cells, {n_logical_calls} logical calls, "
          f"{n_scored} scored, {n_both} both / {n_one} one / {n_neither} neither replicate.")

    # --- Deliverable 1: by arm x model ---
    groups_am = aggregate(cells, lambda arm, model: (arm, model))
    rows_am = rows_from_groups(groups_am, ["arm", "model"])
    fieldnames_am = [
        "arm", "model", "n_cells", "n_with_both_runs", "n_run2_scored", "n_run3_scored",
        "flips_run2", "flips_run3", "cells_flipped_at_least_once", "cells_flipped_both",
        "flip_denominator_runs", "flip_rate_per_run", "flip_rate_wilson_lower",
        "flip_rate_wilson_upper", "temperature_regime",
    ]
    write_csv(OUT_DIR / "flip-rates-by-arm-model.csv", rows_am, fieldnames_am)

    # --- Deliverable 2: by arm ---
    groups_a = aggregate(cells, lambda arm, model: (arm,))
    rows_a = rows_from_groups(groups_a, ["arm"])
    # arm-level temperature_regime: mixed if the arm contains any mixed model slice
    mixed_arms = {
        arm for (arm, model), g in groups_am.items()
        if temperature_regime_for(arm, model, g["upstreams_seen"]) == "mixed"
    }
    for row in rows_a:
        row["temperature_regime"] = "mixed" if row["arm"] in mixed_arms else "temperature_0"
    fieldnames_a = [
        "arm", "n_cells", "n_with_both_runs", "n_run2_scored", "n_run3_scored",
        "flips_run2", "flips_run3", "cells_flipped_at_least_once", "cells_flipped_both",
        "flip_denominator_runs", "flip_rate_per_run", "flip_rate_wilson_lower",
        "flip_rate_wilson_upper", "temperature_regime",
    ]
    write_csv(OUT_DIR / "flip-rates-by-arm.csv", rows_a, fieldnames_a)

    # --- Deliverable 3: run2 vs run3 agreement ---
    agreement_rows = build_agreement(cells)
    fieldnames_agree = [
        "arm", "model", "upstream_subgroup", "n_cells_both_runs", "n_agree",
        "agreement_rate", "agreement_rate_wilson_lower", "agreement_rate_wilson_upper",
        "temperature_regime",
    ]
    write_csv(OUT_DIR / "run2-vs-run3-agreement.csv", agreement_rows, fieldnames_agree)

    print("Wrote flip-rates-by-arm-model.csv, flip-rates-by-arm.csv, run2-vs-run3-agreement.csv")

    # Dump a small JSON of headline numbers for use while writing the report.
    headline = {"by_arm_model": rows_am, "by_arm": rows_a, "agreement": agreement_rows}
    with open(OUT_DIR / "_headline_numbers.json", "w", encoding="utf-8") as f:
        json.dump(headline, f, indent=2)


if __name__ == "__main__":
    main()
