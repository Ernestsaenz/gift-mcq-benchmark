#!/usr/bin/env python3
"""
01_normality.py — Genuine normality diagnostics + distributional description
of the binary primary outcomes, for the ab520 500-question MCQ benchmark.

Owner: Agent 1 (normality / distributional diagnostics). Writes only:
  results/normality_*.json|csv
  figures/qq_*.svg
  results/NORMALITY_REPORT.md
All data sources below are opened read-only.

WHY THIS SCRIPT DOES NOT SHAPIRO-TEST strict_correct OR flip DIRECTLY:
strict_correct and flip are Bernoulli (0/1) indicators. Normality of a
Bernoulli variable is not a meaningful question — a Bernoulli distribution
is never normal for any p strictly between 0 and 1 except in the trivial,
uninformative sense of "not this", and Shapiro-Wilk / Anderson-Darling on
raw 0/1 data will simply reject in a way that carries no information about
which downstream test is valid. Per STATS_SPEC.md, the tests run here are
restricted to quantities that are genuinely continuous (or a proportion
over many trials that can behave close to continuous): per-question
difficulty, and attempt latency. The binary outcomes get a distributional
description instead (base rates, per-cluster counts, boundary counts) —
see section 3 below and NORMALITY_REPORT.md for what that does and does
not license downstream.

Run with: python3 statistical-analysis-7-aug-26/scripts/01_normality.py
(paths are resolved relative to this file, so it also runs from any cwd).
"""

import csv
import json
import math
import warnings
from pathlib import Path
from collections import Counter, defaultdict

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BASE = SCRIPT_DIR.parent  # statistical-analysis-7-aug-26/
DATA_ROOT = BASE.parent  # experiment-4-aug-26/

RUN1_CSV = DATA_ROOT / "consolidate-triplicates-7-aug-26/exports/run1-6000-with-replicate-status.csv"
REPLICATE_CSV = DATA_ROOT / "consolidate-triplicates-7-aug-26/exports/replicate-cell-level-1796.csv"
ATTEMPT_CSV = DATA_ROOT / "consolidate-triplicates-7-aug-26/ledger/ATTEMPT_TIMELINE.csv"

RESULTS_DIR = BASE / "results"
FIGURES_DIR = BASE / "figures"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

ARMS = ["openrouter_A", "openrouter_B", "tailscale_A"]

# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------

def se_skew(n):
    return math.sqrt(6 * n * (n - 1) / ((n - 2) * (n + 1) * (n + 3)))


def se_kurt(n):
    s = se_skew(n)
    return 2 * s * math.sqrt((n ** 2 - 1) / ((n - 3) * (n + 5)))


def ad_pvalue_approx(a2, n):
    """
    Cross-check for scipy's interpolated Anderson-Darling p-value: an
    independent closed-form approximation using the finite-sample
    correction and polynomial approximation of Stephens (1974) /
    D'Agostino & Stephens (1986), Table 4.7 (case 3, "mean and variance
    unknown"). Reported alongside scipy's own `method="interpolate"`
    p-value (the primary figure) purely so the two can be compared; if
    they diverge materially that is flagged rather than silently reported.
    """
    a2s = a2 * (1 + 0.75 / n + 2.25 / n ** 2)
    if a2s < 0.2:
        p = 1 - math.exp(-13.436 + 101.14 * a2s - 223.73 * a2s ** 2)
    elif a2s < 0.34:
        p = 1 - math.exp(-8.318 + 42.796 * a2s - 59.938 * a2s ** 2)
    elif a2s < 0.6:
        p = math.exp(0.9177 - 4.279 * a2s - 1.38 * a2s ** 2)
    else:
        p = math.exp(1.2937 - 5.709 * a2s + 0.0186 * a2s ** 2)
    return float(min(max(p, 0.0), 1.0))


def normality_diagnostics(data, name, note=""):
    x = np.asarray(data, dtype=float)
    n = len(x)
    result = {
        "name": name,
        "note": note,
        "n": int(n),
        "mean": float(np.mean(x)),
        "std": float(np.std(x, ddof=1)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
    }

    W, p_sw = stats.shapiro(x)
    result["shapiro_W"] = float(W)
    result["shapiro_p"] = float(p_sw)

    # Legacy-style call: gives the critical-value table (statistic vs. fixed
    # significance levels). scipy 1.17+ emits a FutureWarning nudging callers
    # to opt into a p-value method instead; we deliberately still want the
    # critical-value table here (as a second, independent decision rule), so
    # the warning is expected and suppressed rather than acted on.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        ad_legacy = stats.anderson(x, dist="norm")
    crit = dict(zip([float(s) for s in ad_legacy.significance_level], [float(c) for c in ad_legacy.critical_values]))
    # New-style call: scipy's own interpolated p-value (primary figure).
    ad = stats.anderson(x, dist="norm", method="interpolate")
    result["anderson_darling_statistic"] = float(ad.statistic)
    result["anderson_darling_p_interpolated_scipy"] = float(ad.pvalue)
    result["anderson_darling_p_approx_stephens1974"] = ad_pvalue_approx(float(ad.statistic), n)
    result["anderson_darling_critical_values_pct"] = crit
    result["anderson_darling_reject_5pct"] = bool(ad.statistic > crit[5.0])

    skew = float(stats.skew(x))
    kurt = float(stats.kurtosis(x))  # Fisher (excess) kurtosis; normal = 0
    result["skewness"] = skew
    result["skewness_se"] = se_skew(n) if n > 3 else None
    result["skewness_z"] = (skew / se_skew(n)) if n > 3 else None
    result["kurtosis_excess"] = kurt
    result["kurtosis_se"] = se_kurt(n) if n > 5 else None
    result["kurtosis_z"] = (kurt / se_kurt(n)) if n > 5 else None

    return result


# ---------------------------------------------------------------------------
# Hand-written inline SVG QQ plot (no matplotlib available)
# ---------------------------------------------------------------------------

def make_qq_svg(data, title, out_path, subtitle=""):
    x = np.sort(np.asarray(data, dtype=float))
    n = len(x)
    mean = float(np.mean(x))
    std = float(np.std(x, ddof=1)) or 1.0

    # Plotting positions (Hazen / (i-0.5)/n), theoretical normal quantiles
    probs = (np.arange(1, n + 1) - 0.5) / n
    theo = stats.norm.ppf(probs)
    z = (x - mean) / std  # standardized sample quantiles

    W, H = 480, 480
    margin_l, margin_r, margin_t, margin_b = 65, 25, 45, 55
    plot_w = W - margin_l - margin_r
    plot_h = H - margin_t - margin_b

    all_vals = np.concatenate([theo, z])
    vmin, vmax = float(np.min(all_vals)), float(np.max(all_vals))
    pad = (vmax - vmin) * 0.08 if vmax > vmin else 1.0
    vmin, vmax = vmin - pad, vmax + pad

    def sx(v):
        return margin_l + (v - vmin) / (vmax - vmin) * plot_w

    def sy(v):
        return H - margin_b - (v - vmin) / (vmax - vmin) * plot_h

    ticks = np.linspace(vmin + pad * 0.6, vmax - pad * 0.6, 5)

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Helvetica,Arial,sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="white"/>')
    parts.append(
        f'<text x="{W/2:.1f}" y="22" text-anchor="middle" font-size="14" '
        f'font-weight="bold" fill="black">{title}</text>'
    )
    if subtitle:
        parts.append(
            f'<text x="{W/2:.1f}" y="38" text-anchor="middle" font-size="10" '
            f'fill="#555">{subtitle}</text>'
        )

    # axes
    parts.append(
        f'<line x1="{margin_l}" y1="{H-margin_b}" x2="{W-margin_r}" y2="{H-margin_b}" '
        f'stroke="black" stroke-width="1"/>'
    )
    parts.append(
        f'<line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{H-margin_b}" '
        f'stroke="black" stroke-width="1"/>'
    )
    # y = x reference line (both axes standardized, so reference is the identity line)
    parts.append(
        f'<line x1="{sx(vmin):.1f}" y1="{sy(vmin):.1f}" x2="{sx(vmax):.1f}" y2="{sy(vmax):.1f}" '
        f'stroke="#d33" stroke-width="1" stroke-dasharray="4,3"/>'
    )
    # ticks + labels
    for t in ticks:
        xt, yt = sx(t), sy(t)
        parts.append(
            f'<line x1="{xt:.1f}" y1="{H-margin_b}" x2="{xt:.1f}" y2="{H-margin_b+5}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{xt:.1f}" y="{H-margin_b+18:.1f}" text-anchor="middle" '
            f'font-size="9" fill="black">{t:.2f}</text>'
        )
        parts.append(
            f'<line x1="{margin_l-5}" y1="{yt:.1f}" x2="{margin_l}" y2="{yt:.1f}" stroke="black"/>'
        )
        parts.append(
            f'<text x="{margin_l-8}" y="{yt+3:.1f}" text-anchor="end" '
            f'font-size="9" fill="black">{t:.2f}</text>'
        )
    parts.append(
        f'<text x="{W/2:.1f}" y="{H-14}" text-anchor="middle" font-size="11" '
        f'fill="black">Theoretical quantiles (standard normal)</text>'
    )
    parts.append(
        f'<text x="14" y="{H/2:.1f}" text-anchor="middle" font-size="11" fill="black" '
        f'transform="rotate(-90 14 {H/2:.1f})">Standardized sample quantiles</text>'
    )

    idx = np.arange(n)
    if n > 1500:
        idx = np.unique(np.linspace(0, n - 1, 1500).astype(int))
    for i in idx:
        cx, cy = sx(theo[i]), sy(z[i])
        parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="1.7" fill="#2563eb" fill-opacity="0.55"/>')

    parts.append(
        f'<text x="{W-margin_r}" y="{margin_t-10}" text-anchor="end" font-size="9" '
        f'fill="black">n={n}</text>'
    )
    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

run1_rows = load_csv(RUN1_CSV)
assert len(run1_rows) == 6000, f"expected 6000 run-1 rows, got {len(run1_rows)}"

replicate_rows = load_csv(REPLICATE_CSV)
assert len(replicate_rows) == 1796, f"expected 1796 replicate rows, got {len(replicate_rows)}"

attempt_rows = load_csv(ATTEMPT_CSV)
assert len(attempt_rows) == 1856, f"expected 1856 attempt rows, got {len(attempt_rows)}"


def provider_of_arm(arm):
    return "tailscale" if arm.startswith("tailscale") else "openrouter"


# ---------------------------------------------------------------------------
# 2a. Per-question difficulty (proportion of 12 run-1 cells strict_correct)
# ---------------------------------------------------------------------------

by_question = defaultdict(list)
by_question_arm = defaultdict(list)  # (question_id, arm) -> list of 0/1
for row in run1_rows:
    sc = int(row["strict_correct"])
    qid = row["question_id"]
    arm = row["arm"]
    by_question[qid].append(sc)
    by_question_arm[(qid, arm)].append(sc)

question_ids = sorted(by_question.keys())
assert len(question_ids) == 500, f"expected 500 questions, got {len(question_ids)}"
for qid in question_ids:
    assert len(by_question[qid]) == 12, f"question {qid} has {len(by_question[qid])} cells, expected 12"
    for arm in ARMS:
        assert len(by_question_arm[(qid, arm)]) == 4, (
            f"question {qid} arm {arm} has {len(by_question_arm[(qid, arm)])} cells, expected 4"
        )

difficulty_overall = {qid: sum(by_question[qid]) / 12.0 for qid in question_ids}
difficulty_by_arm = {
    arm: {qid: sum(by_question_arm[(qid, arm)]) / 4.0 for qid in question_ids} for arm in ARMS
}

# CSV export: per-question difficulty table
with open(RESULTS_DIR / "normality_per_question_difficulty.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(
        ["question_id", "n_correct_of_12", "difficulty_overall"]
        + [f"n_correct_of_4_{arm}" for arm in ARMS]
        + [f"difficulty_{arm}" for arm in ARMS]
    )
    for qid in question_ids:
        row = [qid, sum(by_question[qid]), difficulty_overall[qid]]
        row += [sum(by_question_arm[(qid, arm)]) for arm in ARMS]
        row += [difficulty_by_arm[arm][qid] for arm in ARMS]
        w.writerow(row)

# ---------------------------------------------------------------------------
# 2b. Attempt latency (overall, by provider, log-transformed)
# ---------------------------------------------------------------------------

latency_all = []
latency_by_provider = defaultdict(list)
latency_all_scored_only = []
latency_by_provider_scored_only = defaultdict(list)
for row in attempt_rows:
    if row["latency_ms"] == "":
        continue
    lat = float(row["latency_ms"])
    prov = provider_of_arm(row["arm"])
    latency_all.append(lat)
    latency_by_provider[prov].append(lat)
    if row["scored"] == "TRUE":
        latency_all_scored_only.append(lat)
        latency_by_provider_scored_only[prov].append(lat)

n_latency_missing = sum(1 for row in attempt_rows if row["latency_ms"] == "")

# ---------------------------------------------------------------------------
# 3. Run normality diagnostics
# ---------------------------------------------------------------------------

diag_results = []

diag_results.append(
    normality_diagnostics(
        list(difficulty_overall.values()),
        "per_question_difficulty_overall",
        note="Proportion of the 12 run-1 cells (3 arms x 4 models) strict_correct, "
        "per question. n=500. Bounded [0,1]; only 13 distinct support points "
        "(k/12, k=0..12) — a discrete proportion, not a continuous measurement.",
    )
)
make_qq_svg(
    list(difficulty_overall.values()),
    "QQ: per-question difficulty (overall, n=500)",
    FIGURES_DIR / "qq_per_question_difficulty_overall.svg",
    subtitle="proportion of 12 run-1 cells strict_correct, per question",
)

for arm in ARMS:
    vals = list(difficulty_by_arm[arm].values())
    diag_results.append(
        normality_diagnostics(
            vals,
            f"per_question_difficulty_{arm}",
            note=f"Proportion of the 4 models strict_correct within arm {arm}, per question. "
            "n=500. Bounded [0,1]; only 5 distinct support points (k/4, k=0..4).",
        )
    )
    make_qq_svg(
        vals,
        f"QQ: per-question difficulty, {arm} (n=500)",
        FIGURES_DIR / f"qq_per_question_difficulty_{arm}.svg",
        subtitle="proportion of 4 models strict_correct, per question, within arm",
    )

diag_results.append(
    normality_diagnostics(
        latency_all, "latency_ms_all_attempts_overall",
        note=f"All provider attempts with a recorded latency_ms (successes and retries/errors); "
        f"{n_latency_missing} of {len(attempt_rows)} attempt rows have no latency recorded.",
    )
)
make_qq_svg(
    latency_all, f"QQ: latency_ms, all attempts (n={len(latency_all)})",
    FIGURES_DIR / "qq_latency_ms_all_attempts_overall.svg",
)

log_latency_all = list(np.log(latency_all))
diag_results.append(
    normality_diagnostics(
        log_latency_all, "log_latency_ms_all_attempts_overall",
        note="Natural log of latency_ms, all attempts. Latencies are typically log-normal, "
        "so this is the theoretically expected transform to test.",
    )
)
make_qq_svg(
    log_latency_all, f"QQ: log(latency_ms), all attempts (n={len(log_latency_all)})",
    FIGURES_DIR / "qq_log_latency_ms_all_attempts_overall.svg",
)

for prov in ["openrouter", "tailscale"]:
    vals = latency_by_provider[prov]
    diag_results.append(
        normality_diagnostics(
            vals, f"latency_ms_all_attempts_{prov}",
            note=f"All {prov} provider attempts with a recorded latency_ms.",
        )
    )
    make_qq_svg(
        vals, f"QQ: latency_ms, {prov} (n={len(vals)})",
        FIGURES_DIR / f"qq_latency_ms_all_attempts_{prov}.svg",
    )

    log_vals = list(np.log(vals))
    diag_results.append(
        normality_diagnostics(
            log_vals, f"log_latency_ms_all_attempts_{prov}",
            note=f"Natural log of latency_ms, {prov} provider attempts.",
        )
    )
    make_qq_svg(
        log_vals, f"QQ: log(latency_ms), {prov} (n={len(log_vals)})",
        FIGURES_DIR / f"qq_log_latency_ms_all_attempts_{prov}.svg",
    )

# Scored-only sensitivity check (not separately plotted; summarized in JSON only)
scored_only_summary = {
    "latency_all_scored_only": {
        "n": len(latency_all_scored_only),
        "mean": float(np.mean(latency_all_scored_only)),
        "median": float(np.median(latency_all_scored_only)),
        "std": float(np.std(latency_all_scored_only, ddof=1)),
        "shapiro_W": float(stats.shapiro(latency_all_scored_only)[0]),
        "shapiro_p": float(stats.shapiro(latency_all_scored_only)[1]),
    },
    "latency_all_attempts_including_retries_errors": {
        "n": len(latency_all),
        "mean": float(np.mean(latency_all)),
        "median": float(np.median(latency_all)),
        "std": float(np.std(latency_all, ddof=1)),
        "shapiro_W": float(stats.shapiro(latency_all)[0]),
        "shapiro_p": float(stats.shapiro(latency_all)[1]),
    },
}

# ---------------------------------------------------------------------------
# 4. Distributional description of the BINARY outcomes (no normality test)
# ---------------------------------------------------------------------------

# 4a. strict_correct base rates
n_total = len(run1_rows)
n_correct_total = sum(int(row["strict_correct"]) for row in run1_rows)

rate_by_arm = {}
for arm in ARMS:
    rows_arm = [row for row in run1_rows if row["arm"] == arm]
    n_c = sum(int(row["strict_correct"]) for row in rows_arm)
    rate_by_arm[arm] = {"n": len(rows_arm), "n_correct": n_c, "rate": n_c / len(rows_arm)}

models = sorted(set(row["model"] for row in run1_rows))
rate_by_model = {}
for m in models:
    rows_m = [row for row in run1_rows if row["model"] == m]
    n_c = sum(int(row["strict_correct"]) for row in rows_m)
    rate_by_model[m] = {"n": len(rows_m), "n_correct": n_c, "rate": n_c / len(rows_m)}

# 4b. per-cluster (per-question) count distribution: how many of the 12 cells
# were correct, for each of the 500 questions -> histogram over 0..12
cluster_hist = Counter(sum(by_question[qid]) for qid in question_ids)
cluster_hist_full = {k: cluster_hist.get(k, 0) for k in range(0, 13)}

# per-arm cluster (per-question-within-arm) count distribution: 0..4
cluster_hist_by_arm = {}
for arm in ARMS:
    h = Counter(sum(by_question_arm[(qid, arm)]) for qid in question_ids)
    cluster_hist_by_arm[arm] = {k: h.get(k, 0) for k in range(0, 5)}

# 4c. boundary counts: questions at ceiling (12/12 correct) or floor (0/12 correct)
n_ceiling = cluster_hist_full[12]
n_floor = cluster_hist_full[0]
n_boundary = n_ceiling + n_floor
n_interior = 500 - n_boundary

boundary_by_arm = {}
for arm in ARMS:
    h = cluster_hist_by_arm[arm]
    boundary_by_arm[arm] = {
        "n_ceiling_4of4": h[4],
        "n_floor_0of4": h[0],
        "n_boundary": h[4] + h[0],
        "n_interior": 500 - (h[4] + h[0]),
    }

# 4d. flip rate (secondary outcome): among the 1788 SCORED replicates
#     (conditioned on the parent cell having failed run 1), how many flip
#     to strict_correct.
scored_replicates = [row for row in replicate_rows if row["status"] == "scored"]
assert len(scored_replicates) == 1788, f"expected 1788 scored replicates, got {len(scored_replicates)}"
n_flip = sum(1 for row in scored_replicates if row["strict_correct"] == "TRUE")
flip_rate_overall = n_flip / len(scored_replicates)

flip_by_arm = {}
for arm in ARMS:
    rows_arm = [row for row in scored_replicates if row["arm"] == arm]
    if not rows_arm:
        continue
    n_f = sum(1 for row in rows_arm if row["strict_correct"] == "TRUE")
    flip_by_arm[arm] = {"n": len(rows_arm), "n_flip": n_f, "rate": n_f / len(rows_arm)}

# per-cell flip count distribution (0, 1, or 2 replicates flipped, among cells
# with at least one scored replicate)
cell_flip_counts = defaultdict(lambda: [0, 0])  # cell -> [n_scored, n_flip]
for row in scored_replicates:
    key = (row["arm"], row["question_id"], row["model"])
    cell_flip_counts[key][0] += 1
    if row["strict_correct"] == "TRUE":
        cell_flip_counts[key][1] += 1
n_cells_with_scored_replicate = len(cell_flip_counts)
cell_flip_hist = Counter(v[1] for v in cell_flip_counts.values())  # 0, 1, or 2 flips per cell
cell_flip_hist_full = {k: cell_flip_hist.get(k, 0) for k in range(0, 3)}

binary_outcome_summary = {
    "strict_correct": {
        "overall": {"n": n_total, "n_correct": n_correct_total, "rate": n_correct_total / n_total},
        "by_arm": rate_by_arm,
        "by_model": rate_by_model,
        "per_question_cluster_histogram_0to12_correct_of_12": cluster_hist_full,
        "per_question_cluster_histogram_by_arm_0to4_correct_of_4": cluster_hist_by_arm,
        "boundary_counts": {
            "n_questions_ceiling_12of12": n_ceiling,
            "n_questions_floor_0of12": n_floor,
            "n_questions_at_boundary": n_boundary,
            "n_questions_interior": n_interior,
            "pct_at_boundary": n_boundary / 500,
        },
        "boundary_counts_by_arm_0to4": boundary_by_arm,
    },
    "flip": {
        "definition": "strict_correct==TRUE on a scored replicate (run 2 or 3), conditioned on "
        "the parent run-1 cell having been strict-incorrect. Unconditional flip rate over "
        "all 6000 run-1 cells is NOT estimable: the 5102 run-1-correct cells were never "
        "replicated (see STATS_SPEC.md).",
        "overall": {"n_scored_replicates": len(scored_replicates), "n_flip": n_flip, "rate": flip_rate_overall},
        "by_arm": flip_by_arm,
        "per_cell_flip_count_histogram_0to2": {
            "n_cells_with_at_least_one_scored_replicate": n_cells_with_scored_replicate,
            "histogram": cell_flip_hist_full,
        },
        "caveat": "openrouter_B / gemini carries the Vertex protocol deviation for 91 of its "
        "scored replicates; see STATS_SPEC.md and agent 2/3 sensitivity analyses. This summary "
        "does not exclude those cells — it is a description of the raw replicate data, not an "
        "adjusted estimate.",
    },
}

# ---------------------------------------------------------------------------
# 5. Write JSON / CSV outputs
# ---------------------------------------------------------------------------

with open(RESULTS_DIR / "normality_continuous_diagnostics.json", "w", encoding="utf-8") as f:
    json.dump(
        {
            "diagnostics": diag_results,
            "latency_scored_vs_all_attempts_sensitivity": scored_only_summary,
        },
        f,
        indent=2,
    )

with open(RESULTS_DIR / "normality_continuous_diagnostics_summary.csv", "w", newline="", encoding="utf-8") as f:
    fieldnames = [
        "name", "n", "mean", "std", "min", "max",
        "shapiro_W", "shapiro_p",
        "anderson_darling_statistic", "anderson_darling_reject_5pct",
        "anderson_darling_p_interpolated_scipy", "anderson_darling_p_approx_stephens1974",
        "skewness", "skewness_se", "skewness_z",
        "kurtosis_excess", "kurtosis_se", "kurtosis_z",
        "note",
    ]
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for d in diag_results:
        w.writerow({k: d.get(k) for k in fieldnames})

with open(RESULTS_DIR / "normality_binary_outcome_summary.json", "w", encoding="utf-8") as f:
    json.dump(binary_outcome_summary, f, indent=2)

# Flat CSV mirror of the strict_correct cluster histograms, for quick plotting downstream.
# Two separate tables (0..12 overall, 0..4 per-arm) — different denominators, kept apart
# rather than forced into one misleading row alignment.
with open(RESULTS_DIR / "normality_binary_outcome_cluster_histogram.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["table", "n_correct", "n_of", "n_questions"])
    for k in range(0, 13):
        w.writerow(["overall", k, 12, cluster_hist_full[k]])
    for arm in ARMS:
        for k in range(0, 5):
            w.writerow([arm, k, 4, cluster_hist_by_arm[arm][k]])

print("Wrote:")
for p in sorted(RESULTS_DIR.glob("normality_*")):
    print(" ", p)
for p in sorted(FIGURES_DIR.glob("qq_*.svg")):
    print(" ", p)
