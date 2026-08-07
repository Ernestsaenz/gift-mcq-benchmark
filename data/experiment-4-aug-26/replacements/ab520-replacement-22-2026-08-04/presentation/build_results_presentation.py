#!/usr/bin/env python3
"""Reproduce the statistics and build the standalone benchmark results deck."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from scipy import stats


HERE = Path(__file__).resolve().parent
AB_ROOT = HERE.parent
INPUT_CSV = AB_ROOT / "exports" / "benchmark-6000-cell-results-adjusted.csv"
TEMPLATE = HERE / "results_presentation_template.html"
OUTPUT_HTML = HERE / "benchmark-results-presentation.html"
OUTPUT_JSON = HERE / "statistics.json"
OUTPUT_CSV = HERE / "analysis-summary.csv"

BOOTSTRAP_REPS = 100_000
BOOTSTRAP_SEED = 20_260_804
ALPHA = 0.05

MODEL_IDS = {
    "Gemini": "google/gemini-3.6-flash",
    "Gemma": "google/gemma-4-26b-a4b-it",
    "Qwen": "qwen/qwen3.6-35b-a3b",
    "GLM": "z-ai/glm-5.2",
}

ARM_SPECS = [
    ("OpenRouter A", "openrouter", "A"),
    ("OpenRouter B", "openrouter", "B"),
    ("GIFT / RAG A", "tailscale_medical_rag", "A"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def wilson_interval(successes: int, n: int, alpha: float = ALPHA) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    z = float(stats.norm.ppf(1 - alpha / 2))
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (center - half, center + half)


def stable_seed(label: str) -> int:
    offset = int(hashlib.sha256(label.encode("utf-8")).hexdigest()[:8], 16)
    return BOOTSTRAP_SEED + offset


def bootstrap_mean_ci(values: np.ndarray, label: str) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(stable_seed(label))
    output = np.empty(BOOTSTRAP_REPS, dtype=float)
    chunk = 2_000
    for start in range(0, BOOTSTRAP_REPS, chunk):
        stop = min(start + chunk, BOOTSTRAP_REPS)
        indexes = rng.integers(0, len(values), size=(stop - start, len(values)))
        output[start:stop] = values[indexes].mean(axis=1)
    return tuple(np.quantile(output, [ALPHA / 2, 1 - ALPHA / 2]))


def bootstrap_clustered_pair_ci(pairs: pd.DataFrame, label: str) -> tuple[float, float]:
    grouped = pairs.groupby("source_key", sort=True)["delta"].agg(["sum", "count"])
    sums = grouped["sum"].to_numpy(dtype=float)
    counts = grouped["count"].to_numpy(dtype=float)
    rng = np.random.default_rng(stable_seed(label))
    output = np.empty(BOOTSTRAP_REPS, dtype=float)
    chunk = 2_000
    for start in range(0, BOOTSTRAP_REPS, chunk):
        stop = min(start + chunk, BOOTSTRAP_REPS)
        indexes = rng.integers(0, len(grouped), size=(stop - start, len(grouped)))
        output[start:stop] = sums[indexes].sum(axis=1) / counts[indexes].sum(axis=1)
    return tuple(np.quantile(output, [ALPHA / 2, 1 - ALPHA / 2]))


def matched_odds_ratio(comparator_only: int, baseline_only: int) -> tuple[float, float, float]:
    # A continuity correction is only needed if a discordance cell is zero.
    c = comparator_only + (0.5 if comparator_only == 0 else 0.0)
    b = baseline_only + (0.5 if baseline_only == 0 else 0.0)
    estimate = c / b
    se = math.sqrt(1 / c + 1 / b)
    lower = math.exp(math.log(estimate) - 1.96 * se)
    upper = math.exp(math.log(estimate) + 1.96 * se)
    return estimate, lower, upper


def paired_contrast(
    data: pd.DataFrame,
    baseline_filter: pd.Series,
    comparator_filter: pd.Series,
    baseline_name: str,
    comparator_name: str,
    label: str,
) -> dict:
    keys = ["source_key", "model"]
    baseline = data.loc[baseline_filter, keys + ["strict_correct"]].rename(
        columns={"strict_correct": "baseline"}
    )
    comparator = data.loc[comparator_filter, keys + ["strict_correct"]].rename(
        columns={"strict_correct": "comparator"}
    )
    pairs = baseline.merge(comparator, on=keys, how="inner", validate="one_to_one").dropna()
    pairs["delta"] = pairs["comparator"] - pairs["baseline"]

    both_wrong = int(((pairs.baseline == 0) & (pairs.comparator == 0)).sum())
    baseline_only = int(((pairs.baseline == 1) & (pairs.comparator == 0)).sum())
    comparator_only = int(((pairs.baseline == 0) & (pairs.comparator == 1)).sum())
    both_correct = int(((pairs.baseline == 1) & (pairs.comparator == 1)).sum())
    discordant = baseline_only + comparator_only
    mcnemar_p = float(stats.binomtest(comparator_only, discordant, 0.5).pvalue)

    question_differences = pairs.groupby("source_key", sort=True)["delta"].mean()
    shapiro = stats.shapiro(question_differences)
    wilcoxon = stats.wilcoxon(
        question_differences,
        zero_method="pratt",
        correction=False,
        alternative="two-sided",
        method="approx",
    )
    ci_low, ci_high = bootstrap_clustered_pair_ci(pairs, label)
    matched_or, matched_or_low, matched_or_high = matched_odds_ratio(
        comparator_only, baseline_only
    )

    return {
        "label": label,
        "baseline_name": baseline_name,
        "comparator_name": comparator_name,
        "n_pairs": int(len(pairs)),
        "n_questions": int(pairs.source_key.nunique()),
        "baseline_correct": int(pairs.baseline.sum()),
        "comparator_correct": int(pairs.comparator.sum()),
        "baseline_accuracy": float(pairs.baseline.mean()),
        "comparator_accuracy": float(pairs.comparator.mean()),
        "risk_difference": float(pairs.delta.mean()),
        "risk_difference_ci": [float(ci_low), float(ci_high)],
        "both_wrong": both_wrong,
        "baseline_only": baseline_only,
        "comparator_only": comparator_only,
        "both_correct": both_correct,
        "mcnemar_exact_p": mcnemar_p,
        "matched_odds_ratio": matched_or,
        "matched_odds_ratio_ci": [matched_or_low, matched_or_high],
        "shapiro_w": float(shapiro.statistic),
        "shapiro_p": float(shapiro.pvalue),
        "wilcoxon_w": float(wilcoxon.statistic),
        "wilcoxon_p": float(wilcoxon.pvalue),
    }


def cochran_q(matrix: np.ndarray) -> tuple[float, int, float]:
    matrix = np.asarray(matrix, dtype=float)
    n, k = matrix.shape
    del n
    column_totals = matrix.sum(axis=0)
    row_totals = matrix.sum(axis=1)
    total = matrix.sum()
    denominator = k * total - np.square(row_totals).sum()
    statistic = (k - 1) * (k * np.square(column_totals).sum() - total * total) / denominator
    degrees_freedom = k - 1
    return float(statistic), degrees_freedom, float(stats.chi2.sf(statistic, degrees_freedom))


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(m, dtype=float)
    running = 0.0
    for rank, original_index in enumerate(order):
        candidate = (m - rank) * p_values[original_index]
        running = max(running, candidate)
        adjusted[original_index] = min(1.0, running)
    return adjusted.tolist()


def taxonomy_contrasts(data: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    gemini = MODEL_IDS["Gemini"]
    gemma = MODEL_IDS["Gemma"]
    qwen = MODEL_IDS["Qwen"]
    glm = MODEL_IDS["GLM"]
    closed_open: list[dict] = []
    capacity: list[dict] = []

    for arm_name, provider, condition in ARM_SPECS:
        subset = data[(data.provider == provider) & (data.condition == condition)]
        wide = subset.pivot(index="source_key", columns="model", values="strict_correct")
        complete = wide[[gemini, gemma, qwen, glm]].dropna()

        closed = complete[gemini]
        open_weight = complete[[gemma, qwen, glm]].mean(axis=1)
        high_capacity = complete[[gemini, glm]].mean(axis=1)
        low_active = complete[[gemma, qwen]].mean(axis=1)

        for collection, contrast_name, left_name, right_name, left, right in [
            (
                closed_open,
                "proprietary_vs_open_weight",
                "Gemini (proprietary)",
                "Open-weight set",
                closed,
                open_weight,
            ),
            (
                capacity,
                "high_vs_low_active",
                "High-capacity set",
                "Low-active-parameter set",
                high_capacity,
                low_active,
            ),
        ]:
            difference = left - right
            ci_low, ci_high = bootstrap_mean_ci(
                difference.to_numpy(), f"{arm_name}-{contrast_name}"
            )
            shapiro = stats.shapiro(difference)
            wilcoxon = stats.wilcoxon(
                difference,
                zero_method="pratt",
                correction=False,
                alternative="two-sided",
                method="approx",
            )
            collection.append(
                {
                    "arm": arm_name,
                    "n_questions": int(len(complete)),
                    "left_name": left_name,
                    "right_name": right_name,
                    "left_accuracy": float(left.mean()),
                    "right_accuracy": float(right.mean()),
                    "difference": float(difference.mean()),
                    "difference_ci": [float(ci_low), float(ci_high)],
                    "shapiro_w": float(shapiro.statistic),
                    "shapiro_p": float(shapiro.pvalue),
                    "wilcoxon_w": float(wilcoxon.statistic),
                    "p_raw": float(wilcoxon.pvalue),
                }
            )

    combined = closed_open + capacity
    adjusted = holm_adjust([row["p_raw"] for row in combined])
    for row, p_adjusted in zip(combined, adjusted, strict=True):
        row["p_holm"] = p_adjusted
    return closed_open, capacity


def arm_and_model_summaries(data: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    arms: list[dict] = []
    model_rows: list[dict] = []
    for arm_name, provider, condition in ARM_SPECS:
        subset = data[(data.provider == provider) & (data.condition == condition)]
        scored = subset.strict_correct.notna()
        successes = int(subset.loc[scored, "strict_correct"].sum())
        n_scored = int(scored.sum())
        ci_low, ci_high = wilson_interval(successes, n_scored)
        arms.append(
            {
                "arm": arm_name,
                "provider": provider,
                "condition": condition,
                "required": int(len(subset)),
                "scored": n_scored,
                "correct": successes,
                "missing": int(len(subset) - n_scored),
                "accuracy": successes / n_scored,
                "wilson_ci": [ci_low, ci_high],
                "coverage": n_scored / len(subset),
            }
        )

        wide_complete = subset.pivot(
            index="source_key", columns="model", values="strict_correct"
        )[list(MODEL_IDS.values())].dropna()
        q_stat, q_df, q_p = cochran_q(wide_complete.to_numpy())
        for short_name, model_id in MODEL_IDS.items():
            model_subset = subset[subset.model == model_id]
            model_scored = model_subset.strict_correct.notna()
            model_successes = int(model_subset.loc[model_scored, "strict_correct"].sum())
            model_n = int(model_scored.sum())
            model_ci_low, model_ci_high = wilson_interval(model_successes, model_n)
            model_rows.append(
                {
                    "arm": arm_name,
                    "model": short_name,
                    "model_id": model_id,
                    "correct": model_successes,
                    "scored": model_n,
                    "missing": int(len(model_subset) - model_n),
                    "accuracy": model_successes / model_n,
                    "wilson_ci": [model_ci_low, model_ci_high],
                    "complete_question_n_for_omnibus": int(len(wide_complete)),
                    "cochran_q": q_stat,
                    "cochran_q_df": q_df,
                    "cochran_q_p": q_p,
                }
            )
    return arms, model_rows


def per_model_ab(data: pd.DataFrame) -> list[dict]:
    output = []
    for short_name, model_id in MODEL_IDS.items():
        subset = data[(data.provider == "openrouter") & (data.model == model_id)]
        wide = subset.pivot(index="source_key", columns="condition", values="strict_correct").dropna()
        a_only = int(((wide.A == 1) & (wide.B == 0)).sum())
        b_only = int(((wide.A == 0) & (wide.B == 1)).sum())
        p_value = float(stats.binomtest(b_only, a_only + b_only, 0.5).pvalue)
        delta = wide.B - wide.A
        ci_low, ci_high = bootstrap_mean_ci(delta.to_numpy(), f"model-ab-{short_name}")
        output.append(
            {
                "model": short_name,
                "n_pairs": int(len(wide)),
                "a_accuracy": float(wide.A.mean()),
                "b_accuracy": float(wide.B.mean()),
                "difference": float(delta.mean()),
                "difference_ci": [float(ci_low), float(ci_high)],
                "a_only": a_only,
                "b_only": b_only,
                "mcnemar_exact_p": p_value,
            }
        )
    return output


def make_flat_summary(result: dict) -> pd.DataFrame:
    rows = []
    for arm in result["arm_summaries"]:
        rows.append(
            {
                "section": "arm",
                "contrast": arm["arm"],
                "direction": "accuracy",
                "left_group": arm["arm"],
                "right_group": "",
                "n": arm["scored"],
                "estimate": arm["accuracy"],
                "ci_low": arm["wilson_ci"][0],
                "ci_high": arm["wilson_ci"][1],
                "p_value": math.nan,
                "p_holm": math.nan,
            }
        )
    for key in ["openrouter_a_vs_b", "openrouter_a_vs_gift_a"]:
        row = result[key]
        rows.append(
            {
                "section": "paired",
                "contrast": row["label"],
                "direction": f"{row['comparator_name']} minus {row['baseline_name']}",
                "left_group": row["comparator_name"],
                "right_group": row["baseline_name"],
                "n": row["n_pairs"],
                "estimate": row["risk_difference"],
                "ci_low": row["risk_difference_ci"][0],
                "ci_high": row["risk_difference_ci"][1],
                "p_value": row["mcnemar_exact_p"],
                "p_holm": math.nan,
            }
        )
    for section, key in [("taxonomy", "closed_open"), ("capacity", "capacity")]:
        for row in result[key]:
            rows.append(
                {
                    "section": section,
                    "contrast": row["arm"],
                    "direction": f"{row['left_name']} minus {row['right_name']}",
                    "left_group": row["left_name"],
                    "right_group": row["right_name"],
                    "n": row["n_questions"],
                    "estimate": row["difference"],
                    "ci_low": row["difference_ci"][0],
                    "ci_high": row["difference_ci"][1],
                    "p_value": row["p_raw"],
                    "p_holm": row["p_holm"],
                }
            )
    return pd.DataFrame(rows)


def json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    raise TypeError(f"Cannot serialize {type(value)!r}")


def validate_input(data: pd.DataFrame) -> None:
    required = {
        "source_key",
        "question_id",
        "provider",
        "condition",
        "model",
        "strict_correct",
        "final_execution_status",
        "failure_class",
    }
    missing_columns = required - set(data.columns)
    if missing_columns:
        raise RuntimeError(f"Missing required columns: {sorted(missing_columns)}")
    if len(data) != 6_000 or data.source_key.nunique() != 500:
        raise RuntimeError("Expected 6,000 cells from exactly 500 source questions")
    if data.model.nunique() != 4:
        raise RuntimeError("Expected four model identifiers")
    if set(data.strict_correct.dropna().unique()) != {0.0, 1.0}:
        raise RuntimeError("strict_correct must be binary when present")
    scored = int(data.strict_correct.notna().sum())
    unresolved = int(data.strict_correct.isna().sum())
    if scored + unresolved != 6_000:
        raise RuntimeError(
            f"Coverage invariant failed: {scored} scored + {unresolved} unresolved != 6,000"
        )
    status_scored = data.final_execution_status.eq("scored")
    if not status_scored.equals(data.strict_correct.notna()):
        raise RuntimeError("Score presence does not match final_execution_status")


def main() -> None:
    data = pd.read_csv(INPUT_CSV)
    validate_input(data)

    arm_summaries, model_summaries = arm_and_model_summaries(data)
    ab = paired_contrast(
        data,
        (data.provider == "openrouter") & (data.condition == "A"),
        (data.provider == "openrouter") & (data.condition == "B"),
        "OpenRouter A",
        "OpenRouter B",
        "OpenRouter B minus A",
    )
    platform = paired_contrast(
        data,
        (data.provider == "openrouter") & (data.condition == "A"),
        (data.provider == "tailscale_medical_rag") & (data.condition == "A"),
        "OpenRouter A",
        "GIFT / RAG A",
        "GIFT / RAG A minus OpenRouter A",
    )
    closed_open, capacity = taxonomy_contrasts(data)

    missing_counts = (
        data.loc[data.strict_correct.isna(), "failure_class"].value_counts().sort_values(ascending=False)
    )
    openrouter_a = data[(data.provider == "openrouter") & (data.condition == "A")]
    gift_a = data[
        (data.provider == "tailscale_medical_rag") & (data.condition == "A")
    ]
    openrouter_a_correct = int(openrouter_a.strict_correct.sum(skipna=True))
    gift_a_correct = int(gift_a.strict_correct.sum(skipna=True))
    openrouter_a_missing = int(openrouter_a.strict_correct.isna().sum())
    gift_a_missing = int(gift_a.strict_correct.isna().sum())
    openrouter_a_required = int(len(openrouter_a))
    gift_a_required = int(len(gift_a))
    result = {
        "protocol": {
            "analysis_date": "2026-08-05",
            "input_csv": str(INPUT_CSV.relative_to(AB_ROOT.parent)),
            "input_sha256": sha256(INPUT_CSV),
            "bootstrap_repetitions": BOOTSTRAP_REPS,
            "bootstrap_base_seed": BOOTSTRAP_SEED,
            "bootstrap_seed_derivation": "base seed + integer from first 8 hex digits of SHA-256(contrast label)",
            "alpha": ALPHA,
            "outcome": "strict_correct",
            "pairing_key": ["source_key", "model"],
            "cluster_key": "source_key",
            "multiplicity": "Holm correction across six user-requested exploratory taxonomy contrasts",
        },
        "dataset": {
            "required_cells": int(len(data)),
            "scored_cells": int(data.strict_correct.notna().sum()),
            "unresolved_cells": int(data.strict_correct.isna().sum()),
            "questions": int(data.source_key.nunique()),
            "models": int(data.model.nunique()),
            "failure_classes": {str(k): int(v) for k, v in missing_counts.items()},
        },
        "arm_summaries": arm_summaries,
        "model_summaries": model_summaries,
        "per_model_ab": per_model_ab(data),
        "openrouter_a_vs_b": ab,
        "openrouter_a_vs_gift_a": platform,
        "closed_open": closed_open,
        "capacity": capacity,
        "missing_data_sensitivity": {
            "gift_a_accuracy_if_all_missing_wrong": gift_a_correct / gift_a_required,
            "gift_a_accuracy_if_all_missing_correct": (gift_a_correct + gift_a_missing) / gift_a_required,
            "openrouter_a_accuracy_if_all_missing_wrong": openrouter_a_correct / openrouter_a_required,
            "openrouter_a_accuracy_if_all_missing_correct": (openrouter_a_correct + openrouter_a_missing) / openrouter_a_required,
            "gift_minus_openrouter_extreme_bounds": [
                gift_a_correct / gift_a_required
                - (openrouter_a_correct + openrouter_a_missing) / openrouter_a_required,
                (gift_a_correct + gift_a_missing) / gift_a_required
                - openrouter_a_correct / openrouter_a_required,
            ],
        },
        "coverage_context": {
            "gift_a_unresolved": gift_a_missing,
            "openrouter_a_unresolved": openrouter_a_missing,
            "overlength_failures": int(
                missing_counts.get(
                    "tailscale_http500_correlated_overlength_exact_input", 0
                )
            ),
            "overlength_questions": int(
                data.loc[
                    data.failure_class.eq(
                        "tailscale_http500_correlated_overlength_exact_input"
                    ),
                    "source_key",
                ].nunique()
            ),
        },
        "taxonomy": {
            "access": {
                "proprietary_api": ["Gemini"],
                "open_weight": ["Gemma", "Qwen", "GLM"],
            },
            "capacity_user_defined_exploratory": {
                "high_capacity": ["Gemini", "GLM"],
                "low_active_parameter": ["Gemma", "Qwen"],
            },
        },
    }

    OUTPUT_JSON.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=json_default) + "\n",
        encoding="utf-8",
    )
    make_flat_summary(result).to_csv(OUTPUT_CSV, index=False)

    environment = Environment(
        loader=FileSystemLoader(str(HERE)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.globals["comma"] = lambda value: f"{int(value):,}"
    template = environment.get_template(TEMPLATE.name)
    html = template.render(
        result=result,
        stats_json=json.dumps(result, ensure_ascii=False, default=json_default),
    )
    OUTPUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_HTML}")
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
