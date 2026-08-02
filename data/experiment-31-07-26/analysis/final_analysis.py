"""Recompute the compact, version-pinned results used by the final report.

This script intentionally ignores the many superseded exploratory outputs in this
directory. It reads only the v3 canonical exports and the immutable run database.

Run from the repository root:

    uv run python data/experiment-31-07-26/analysis/final_analysis.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sqlite3
import tempfile
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
DB = HERE.parent / "experiment.sqlite"
PAIRED = HERE / "paired_clean.json"
CROSS = HERE / "cross_arm_A.json"
META = HERE / "dataset_meta.json"
AUDITED = HERE / "audited_secondary_results.json"
OUT = HERE / "final_analysis_results.json"
SEED = 20260731
N_BOOT = 100_000

SHORT = {
    "google/gemini-3.6-flash": "gemini-3.6-flash",
    "z-ai/glm-5.2": "glm-5.2",
    "qwen/qwen3.6-35b-a3b": "qwen3.6-35b-a3b",
    "google/gemma-4-26b-a4b-it": "gemma-4-26b-a4b-it",
}
MODEL_ORDER = [
    "google/gemini-3.6-flash",
    "z-ai/glm-5.2",
    "qwen/qwen3.6-35b-a3b",
    "google/gemma-4-26b-a4b-it",
]
GROUP_COMPARISON_SPECS = {
    "size": {
        "label": "Requested size grouping",
        "first_group": "large",
        "second_group": "small",
        "groups": {
            "large": [MODEL_ORDER[0], MODEL_ORDER[1]],
            "small": [MODEL_ORDER[2], MODEL_ORDER[3]],
        },
        "contrast_label": "large minus small",
    },
    "openness": {
        "label": "Requested model-access grouping",
        "first_group": "open_model",
        "second_group": "proprietary",
        "groups": {
            "open_model": [MODEL_ORDER[1], MODEL_ORDER[2], MODEL_ORDER[3]],
            "proprietary": [MODEL_ORDER[0]],
        },
        "contrast_label": "open-model minus proprietary",
    },
}
SECONDARY_COMPARISON_SPECS = {
    "openness_within_large": {
        "label": "Within-large triangulation",
        "first_group": "proprietary_large",
        "second_group": "open_large",
        "groups": {
            "proprietary_large": [MODEL_ORDER[0]],
            "open_large": [MODEL_ORDER[1]],
        },
        "contrast_label": "gemini minus glm",
    },
    "size_within_open": {
        "label": "Within-open triangulation",
        "first_group": "large_open",
        "second_group": "small_open",
        "groups": {
            "large_open": [MODEL_ORDER[1]],
            "small_open": [MODEL_ORDER[2], MODEL_ORDER[3]],
        },
        "contrast_label": "glm minus mean(qwen, gemma)",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json_write(path: Path, value: dict) -> None:
    """Publish one JSON document without exposing a partially written file."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def immutable_connection(path: Path) -> sqlite3.Connection:
    """Open a WAL-free frozen SQLite snapshot without creating sidecar files."""
    wal = Path(f"{path}-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError(f"refusing a database with a non-empty WAL: {wal}")
    connection = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    return connection


def load_audited_secondary(current_hashes: dict[str, str]) -> dict:
    """Load independently audited constants only after their evidence hashes match."""
    audited = json.loads(AUDITED.read_text(encoding="utf-8"))
    if audited.get("schema_version") != 1:
        raise RuntimeError("unsupported audited_secondary_results.json schema")
    for name, expected in audited.get("input_sha256", {}).items():
        if current_hashes.get(name) != expected:
            raise RuntimeError(f"audited secondary input hash mismatch: {name}")
    for relative, expected in audited.get("source_sha256", {}).items():
        source = HERE / relative
        if not source.is_file() or sha256(source) != expected:
            raise RuntimeError(f"audited secondary source hash mismatch: {relative}")
    return audited


def exact_mcnemar(n10: int, n01: int) -> float:
    """Two-sided exact binomial McNemar p for independent paired rows."""
    n = n10 + n01
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(n10, n01) + 1))
    return float(min(Fraction(2 * tail, 1 << n), Fraction(1)))


def holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=p_values.get)
    adjusted: dict[str, float] = {}
    running = 0.0
    m = len(ordered)
    for rank, key in enumerate(ordered):
        running = max(running, min(1.0, (m - rank) * p_values[key]))
        adjusted[key] = running
    return adjusted


def paired_summary(rows: list[dict], left: str, right: str) -> dict:
    n = len(rows)
    left_correct = sum(int(r[left]) for r in rows)
    right_correct = sum(int(r[right]) for r in rows)
    n10 = sum(r[left] == 1 and r[right] == 0 for r in rows)
    n01 = sum(r[left] == 0 and r[right] == 1 for r in rows)
    return {
        "n": n,
        "left_correct": left_correct,
        "right_correct": right_correct,
        "left_accuracy": left_correct / n,
        "right_accuracy": right_correct / n,
        "risk_difference_right_minus_left": (right_correct - left_correct) / n,
        "left_only": n10,
        "right_only": n01,
        "exact_mcnemar_p_iid_pairs": exact_mcnemar(n10, n01),
    }


def signflip_exact(rows: list[dict], left: str, right: str) -> dict:
    """Exact two-sided sign flip of whole clinical-cluster net differences."""
    by_cluster: dict[int, int] = defaultdict(int)
    for row in rows:
        by_cluster[int(row["cluster"])] += int(row[right]) - int(row[left])
    contributions = [value for value in by_cluster.values() if value]
    observed = sum(contributions)
    distribution = Counter({0: 1})
    for value in contributions:
        next_distribution: Counter[int] = Counter()
        for total, count in distribution.items():
            next_distribution[total + value] += count
            next_distribution[total - value] += count
        distribution = next_distribution
    denominator = 1 << len(contributions)
    extreme = sum(
        count for total, count in distribution.items() if abs(total) >= abs(observed)
    )
    discordant = sum(row[left] != row[right] for row in rows)
    null_variance = sum(value * value for value in contributions)
    return {
        "observed_net_right_minus_left": observed,
        "clusters_total": len(by_cluster),
        "clusters_nonzero": len(contributions),
        "p_two_sided": float(Fraction(extreme, denominator)),
        "null_variance": null_variance,
        "independent_pair_variance": discordant,
        "design_effect_vs_iid_discordances": null_variance / discordant
        if discordant
        else None,
    }


def cluster_bootstrap(
    rows: list[dict],
    left: str,
    right: str,
    models: list[str] | None,
    seed: int,
    n_boot: int = N_BOOT,
) -> dict:
    """Percentile ratio-estimator CIs from whole-cluster resampling.

    One draw samples a clinical cluster and carries every item/model row in that
    cluster. Repeated draws remain separate through their multiplicity in the sampled
    index matrix; they are never re-grouped by question ID.
    """
    clusters = sorted({int(row["cluster"]) for row in rows})
    labels = list(models or []) + ["pooled"]
    features = np.zeros((len(clusters), len(labels), 2), dtype=np.int64)
    cluster_index = {cluster: idx for idx, cluster in enumerate(clusters)}
    model_index = {model: idx for idx, model in enumerate(models or [])}
    pooled_index = len(labels) - 1
    for row in rows:
        ci = cluster_index[int(row["cluster"])]
        difference = int(row[right]) - int(row[left])
        if models is not None:
            mi = model_index[row["model"]]
            features[ci, mi, 0] += difference
            features[ci, mi, 1] += 1
        features[ci, pooled_index, 0] += difference
        features[ci, pooled_index, 1] += 1

    rng = np.random.default_rng(seed)
    draws = {label: np.empty(n_boot, dtype=np.float64) for label in labels}
    batch_size = 5_000
    for start in range(0, n_boot, batch_size):
        stop = min(start + batch_size, n_boot)
        sampled = rng.integers(0, len(clusters), size=(stop - start, len(clusters)))
        totals = features[sampled].sum(axis=1)
        for idx, label in enumerate(labels):
            draws[label][start:stop] = totals[:, idx, 0] / totals[:, idx, 1]

    output = {
        "method": "whole-clinical-cluster percentile bootstrap of the ratio estimator",
        "seed": seed,
        "replicates": n_boot,
        "clusters": len(clusters),
        "estimates": {},
    }
    for label, values in draws.items():
        output["estimates"][SHORT.get(label, label)] = {
            "ci95": [
                float(np.quantile(values, 0.025)),
                float(np.quantile(values, 0.975)),
            ],
            "bootstrap_boxplot": bootstrap_boxplot_summary(values),
            "bootstrap_se": float(values.std(ddof=1)),
            "nonnegative_replicates": int(np.count_nonzero(values >= 0)),
        }
    return output


def bootstrap_boxplot_summary(values: np.ndarray) -> dict:
    """Deterministic five-number summary of a bootstrap sampling distribution."""
    minimum, q1, median, q3, maximum = np.quantile(values, [0.0, 0.25, 0.5, 0.75, 1.0])
    summary = {
        "minimum": float(minimum),
        "q1": float(q1),
        "median": float(median),
        "q3": float(q3),
        "maximum": float(maximum),
    }
    ordered = list(summary.values())
    if not all(math.isfinite(value) for value in ordered) or ordered != sorted(ordered):
        raise RuntimeError("invalid bootstrap boxplot summary")
    return summary


def kish_effective_clusters(rows: list[dict]) -> dict:
    sizes = Counter(int(row["cluster"]) for row in rows)
    total = sum(sizes.values())
    effective = total * total / sum(size * size for size in sizes.values())
    return {
        "nominal_clusters": len(sizes),
        "effective_clusters": effective,
        "largest_cluster_cells": max(sizes.values()),
    }


def leave_one_out(rows: list[dict]) -> dict:
    def delta(selected: list[dict]) -> float:
        return sum(r["B_correct"] - r["A_correct"] for r in selected) / len(selected)

    output = {}
    for field in ("cluster", "question_id", "model"):
        values = sorted({row[field] for row in rows}, key=str)
        estimates = [
            delta([row for row in rows if row[field] != value]) for value in values
        ]
        output[field] = {
            "refits": len(estimates),
            "minimum": min(estimates),
            "maximum": max(estimates),
        }
    return output


def cluster_accuracy_bootstrap(
    rows: list[dict], outcome: str, seed: int, n_boot: int = N_BOOT
) -> dict:
    """Whole-clinical-cluster percentile intervals for each model's accuracy."""
    clusters = sorted({int(row["cluster"]) for row in rows})
    cluster_index = {cluster: idx for idx, cluster in enumerate(clusters)}
    model_index = {model: idx for idx, model in enumerate(MODEL_ORDER)}
    features = np.zeros((len(clusters), len(MODEL_ORDER), 2), dtype=np.int64)
    for row in rows:
        ci = cluster_index[int(row["cluster"])]
        mi = model_index[row["model"]]
        features[ci, mi, 0] += int(row[outcome])
        features[ci, mi, 1] += 1

    rng = np.random.default_rng(seed)
    draws = np.empty((n_boot, len(MODEL_ORDER)), dtype=np.float64)
    batch_size = 5_000
    for start in range(0, n_boot, batch_size):
        stop = min(start + batch_size, n_boot)
        sampled = rng.integers(0, len(clusters), size=(stop - start, len(clusters)))
        totals = features[sampled].sum(axis=1)
        draws[start:stop] = totals[:, :, 0] / totals[:, :, 1]
    return {
        SHORT[model]: {
            "ci95": [
                float(np.quantile(draws[:, idx], 0.025)),
                float(np.quantile(draws[:, idx], 0.975)),
            ],
            "bootstrap_boxplot": bootstrap_boxplot_summary(draws[:, idx]),
            "bootstrap_se": float(draws[:, idx].std(ddof=1)),
        }
        for idx, model in enumerate(MODEL_ORDER)
    }


def cluster_ratio_bootstrap(
    features_by_cluster: dict[int, tuple[int, int] | list[int]],
    seed: int,
    n_boot: int = N_BOOT,
) -> dict:
    """Whole-clinical-cluster interval for one numerator/denominator estimand."""
    clusters = sorted(features_by_cluster)
    features = np.asarray(
        [features_by_cluster[cluster] for cluster in clusters], dtype=np.int64
    )
    if not len(features) or np.any(features[:, 1] <= 0):
        raise RuntimeError("cluster ratio bootstrap requires positive denominators")
    observed = float(features[:, 0].sum() / features[:, 1].sum())
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot, dtype=np.float64)
    batch_size = 5_000
    for start in range(0, n_boot, batch_size):
        stop = min(start + batch_size, n_boot)
        sampled = rng.integers(0, len(clusters), size=(stop - start, len(clusters)))
        totals = features[sampled].sum(axis=1)
        draws[start:stop] = totals[:, 0] / totals[:, 1]
    return {
        "method": "whole-clinical-cluster percentile bootstrap of the ratio estimator",
        "estimate": observed,
        "ci95": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
        "bootstrap_boxplot": bootstrap_boxplot_summary(draws),
        "bootstrap_se": float(draws.std(ddof=1)),
        "nonnegative_replicates": int(np.count_nonzero(draws >= 0)),
        "clusters": len(clusters),
        "seed": seed,
        "replicates": n_boot,
    }


def exact_cluster_signflip_contributions(
    contributions_by_cluster: dict[int, int],
) -> dict:
    """Exact two-sided sign flip for integer-scaled whole-cluster contributions."""
    contributions = [
        int(value)
        for _, value in sorted(contributions_by_cluster.items())
        if int(value)
    ]
    observed = sum(contributions)
    distribution = Counter({0: 1})
    for value in contributions:
        next_distribution: Counter[int] = Counter()
        for total, count in distribution.items():
            next_distribution[total + value] += count
            next_distribution[total - value] += count
        distribution = next_distribution
    denominator = 1 << len(contributions)
    extreme = sum(
        count for total, count in distribution.items() if abs(total) >= abs(observed)
    )
    return {
        "method": "exact two-sided sign flip of integer-scaled clinical-cluster contributions",
        "observed_scaled_net": observed,
        "clusters_total": len(contributions_by_cluster),
        "clusters_nonzero": len(contributions),
        "p_two_sided": float(Fraction(extreme, denominator)),
        "null_variance_scaled": sum(value * value for value in contributions),
    }


def complete_case_model_population(
    paired: list[dict],
) -> tuple[list[str], list[dict], dict[str, dict[str, dict]]]:
    """Return the identical item set observed for all four models."""
    included = [row for row in paired if row["analysis_include"]]
    item_models: dict[str, set[str]] = defaultdict(set)
    for row in included:
        item_models[row["question_id"]].add(row["model"])
    complete_items = sorted(
        question_id
        for question_id, models in item_models.items()
        if models == set(MODEL_ORDER)
    )
    complete_item_set = set(complete_items)
    rows = [row for row in included if row["question_id"] in complete_item_set]
    pivot: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        pivot[row["question_id"]][row["model"]] = row
    if len(rows) != len(complete_items) * len(MODEL_ORDER):
        raise RuntimeError("unexpected complete-case model-comparison grain")
    return complete_items, rows, pivot


def _group_accuracy_summary(
    items: list[str],
    pivot: dict[str, dict[str, dict]],
    models: list[str],
    condition: str,
    seed: int,
) -> dict:
    features: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    outcome = f"{condition}_correct"
    for question_id in items:
        cluster = int(pivot[question_id][models[0]]["cluster"])
        for model in models:
            features[cluster][0] += int(pivot[question_id][model][outcome])
            features[cluster][1] += 1
    bootstrap = cluster_ratio_bootstrap(features, seed)
    correct = sum(value[0] for value in features.values())
    cells = sum(value[1] for value in features.values())
    return {
        "models": [SHORT[model] for model in models],
        "model_count": len(models),
        "items": len(items),
        "model_item_cells": cells,
        "correct": correct,
        "accuracy": correct / cells,
        "cluster_bootstrap_ci95": bootstrap["ci95"],
        "bootstrap_boxplot": bootstrap["bootstrap_boxplot"],
        "bootstrap_seed": bootstrap["seed"],
        "bootstrap_replicates": bootstrap["replicates"],
    }


def _group_contrast_features(
    items: list[str],
    pivot: dict[str, dict[str, dict]],
    first_models: list[str],
    second_models: list[str],
    value_fields: tuple[str, ...],
) -> tuple[dict[int, list[int]], int]:
    """Build integer-scaled group-mean contrast features at the clinical-cluster level."""
    scale = math.lcm(len(first_models), len(second_models))
    features: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for question_id in items:
        cluster = int(pivot[question_id][first_models[0]]["cluster"])

        def value(model: str) -> int:
            if len(value_fields) == 1:
                return int(pivot[question_id][model][value_fields[0]])
            return int(pivot[question_id][model][value_fields[0]]) - int(
                pivot[question_id][model][value_fields[1]]
            )

        scaled_contrast = sum(value(model) for model in first_models) * (
            scale // len(first_models)
        ) - sum(value(model) for model in second_models) * (scale // len(second_models))
        features[cluster][0] += scaled_contrast
        features[cluster][1] += scale
    return features, scale


def _group_contrast_summary(
    items: list[str],
    pivot: dict[str, dict[str, dict]],
    spec: dict,
    value_fields: tuple[str, ...],
    seed: int,
) -> dict:
    first_group = spec["first_group"]
    second_group = spec["second_group"]
    features, scale = _group_contrast_features(
        items,
        pivot,
        spec["groups"][first_group],
        spec["groups"][second_group],
        value_fields,
    )
    bootstrap = cluster_ratio_bootstrap(features, seed)
    signflip = exact_cluster_signflip_contributions(
        {cluster: value[0] for cluster, value in features.items()}
    )
    return {
        "first_group": first_group,
        "second_group": second_group,
        "contrast_direction": spec["contrast_label"],
        "risk_difference_first_minus_second": bootstrap["estimate"],
        "cluster_bootstrap_ci95": bootstrap["ci95"],
        "bootstrap_boxplot": bootstrap["bootstrap_boxplot"],
        "exact_cluster_signflip_p": signflip["p_two_sided"],
        "clinical_clusters": signflip["clusters_total"],
        "nonzero_clinical_clusters": signflip["clusters_nonzero"],
        "integer_scale": scale,
        "bootstrap_seed": bootstrap["seed"],
        "bootstrap_replicates": bootstrap["replicates"],
    }


def _group_change_summary(
    items: list[str],
    pivot: dict[str, dict[str, dict]],
    models: list[str],
    seed: int,
) -> dict:
    features: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for question_id in items:
        cluster = int(pivot[question_id][models[0]]["cluster"])
        for model in models:
            row = pivot[question_id][model]
            features[cluster][0] += int(row["B_correct"]) - int(row["A_correct"])
            features[cluster][1] += 1
    bootstrap = cluster_ratio_bootstrap(features, seed)
    signflip = exact_cluster_signflip_contributions(
        {cluster: value[0] for cluster, value in features.items()}
    )
    return {
        "models": [SHORT[model] for model in models],
        "model_count": len(models),
        "items": len(items),
        "model_item_cells": sum(value[1] for value in features.values()),
        "risk_difference_b_minus_a": bootstrap["estimate"],
        "cluster_bootstrap_ci95": bootstrap["ci95"],
        "bootstrap_boxplot": bootstrap["bootstrap_boxplot"],
        "exact_cluster_signflip_p": signflip["p_two_sided"],
        "clinical_clusters": signflip["clusters_total"],
        "nonzero_clinical_clusters": signflip["clusters_nonzero"],
        "bootstrap_seed": bootstrap["seed"],
        "bootstrap_replicates": bootstrap["replicates"],
    }


def grouped_model_analysis(paired: list[dict], seed: int) -> dict:
    """Compare the two requested fixed-model groupings within and across A/B."""
    items, rows, pivot = complete_case_model_population(paired)
    definitions = {}
    group_models: dict[str, list[str]] = {}
    for dimension, spec in GROUP_COMPARISON_SPECS.items():
        members = [model for models in spec["groups"].values() for model in models]
        if len(members) != len(set(members)) or set(members) != set(MODEL_ORDER):
            raise RuntimeError(f"{dimension} groups must partition the four models")
        definitions[dimension] = {
            "label": spec["label"],
            "first_group": spec["first_group"],
            "second_group": spec["second_group"],
            "contrast_direction": spec["contrast_label"],
            "groups": {
                key: [SHORT[model] for model in models]
                for key, models in spec["groups"].items()
            },
        }
        group_models.update(spec["groups"])

    within_condition = {}
    primary_test_objects: dict[str, dict] = {}
    decline_test_objects: dict[str, dict] = {}
    seed_offset = 0
    for condition in ("A", "B"):
        accuracies = {}
        for group, models in group_models.items():
            accuracies[group] = _group_accuracy_summary(
                items, pivot, models, condition, seed + seed_offset
            )
            seed_offset += 1
        contrasts = {}
        for dimension, spec in GROUP_COMPARISON_SPECS.items():
            contrast = _group_contrast_summary(
                items,
                pivot,
                spec,
                (f"{condition}_correct",),
                seed + seed_offset,
            )
            seed_offset += 1
            contrast["test_id"] = f"{condition.lower()}_{dimension}_contrast"
            contrasts[dimension] = contrast
            primary_test_objects[contrast["test_id"]] = contrast
        within_condition[condition] = {
            "group_accuracies": accuracies,
            "contrasts": contrasts,
        }

    changes = {}
    for group, models in group_models.items():
        change = _group_change_summary(items, pivot, models, seed + seed_offset)
        seed_offset += 1
        change["test_id"] = f"a_vs_b_{group}"
        changes[group] = change
        decline_test_objects[change["test_id"]] = change

    interactions = {}
    for dimension, spec in GROUP_COMPARISON_SPECS.items():
        interaction = _group_contrast_summary(
            items,
            pivot,
            spec,
            ("B_correct", "A_correct"),
            seed + seed_offset,
        )
        seed_offset += 1
        interaction["test_id"] = f"condition_by_{dimension}_interaction"
        interaction["difference_in_b_minus_a_changes"] = interaction.pop(
            "risk_difference_first_minus_second"
        )
        interactions[dimension] = interaction
        primary_test_objects[interaction["test_id"]] = interaction

    primary_raw_p = {
        test_id: test["exact_cluster_signflip_p"]
        for test_id, test in primary_test_objects.items()
    }
    primary_adjusted = holm(primary_raw_p)
    for test_id, test in primary_test_objects.items():
        test["holm_adjusted_p_across_six_primary_group_tests"] = primary_adjusted[
            test_id
        ]

    decline_raw_p = {
        test_id: test["exact_cluster_signflip_p"]
        for test_id, test in decline_test_objects.items()
    }
    decline_adjusted = holm(decline_raw_p)
    for test_id, test in decline_test_objects.items():
        test["holm_adjusted_p_across_four_group_declines"] = decline_adjusted[test_id]

    secondary = {}
    secondary_test_objects: dict[str, dict] = {}
    for dimension, spec in SECONDARY_COMPARISON_SPECS.items():
        condition_results = {}
        for condition in ("A", "B"):
            first_group = spec["first_group"]
            second_group = spec["second_group"]
            contrast = _group_contrast_summary(
                items,
                pivot,
                spec,
                (f"{condition}_correct",),
                seed + seed_offset,
            )
            seed_offset += 1
            contrast["test_id"] = f"secondary_{condition.lower()}_{dimension}"
            secondary_test_objects[contrast["test_id"]] = contrast
            condition_results[condition] = {
                "first_group_accuracy": _group_accuracy_summary(
                    items,
                    pivot,
                    spec["groups"][first_group],
                    condition,
                    seed + seed_offset,
                ),
                "second_group_accuracy": _group_accuracy_summary(
                    items,
                    pivot,
                    spec["groups"][second_group],
                    condition,
                    seed + seed_offset + 1,
                ),
                "contrast": contrast,
            }
            seed_offset += 2
        interaction = _group_contrast_summary(
            items,
            pivot,
            spec,
            ("B_correct", "A_correct"),
            seed + seed_offset,
        )
        seed_offset += 1
        interaction["test_id"] = f"secondary_condition_by_{dimension}"
        interaction["difference_in_b_minus_a_changes"] = interaction.pop(
            "risk_difference_first_minus_second"
        )
        secondary_test_objects[interaction["test_id"]] = interaction
        secondary[dimension] = {
            "label": spec["label"],
            "first_group": spec["first_group"],
            "second_group": spec["second_group"],
            "contrast_direction": spec["contrast_label"],
            "groups": {
                key: [SHORT[model] for model in models]
                for key, models in spec["groups"].items()
            },
            "within_condition": condition_results,
            "condition_interaction": interaction,
        }

    secondary_raw_p = {
        test_id: test["exact_cluster_signflip_p"]
        for test_id, test in secondary_test_objects.items()
    }
    secondary_adjusted = holm(secondary_raw_p)
    for test_id, test in secondary_test_objects.items():
        test["holm_adjusted_p_across_six_secondary_tests"] = secondary_adjusted[test_id]

    for test in [
        *primary_test_objects.values(),
        *decline_test_objects.values(),
        *secondary_test_objects.values(),
    ]:
        p_value = test["exact_cluster_signflip_p"]
        lower, upper = test["cluster_bootstrap_ci95"]
        if not (math.isfinite(lower) and math.isfinite(upper) and lower <= upper):
            raise RuntimeError("invalid grouped-comparison bootstrap interval")
        if not (math.isfinite(p_value) and 0.0 <= p_value <= 1.0):
            raise RuntimeError("invalid grouped-comparison p-value")

    classification = []
    for model in MODEL_ORDER:
        classification.append(
            {
                "model": SHORT[model],
                "size_group": next(
                    group
                    for group, models in GROUP_COMPARISON_SPECS["size"][
                        "groups"
                    ].items()
                    if model in models
                ),
                "access_group": next(
                    group
                    for group, models in GROUP_COMPARISON_SPECS["openness"][
                        "groups"
                    ].items()
                    if model in models
                ),
            }
        )

    return {
        "population": {
            "items": len(items),
            "cells": len(rows),
            "clinical_clusters": len({int(row["cluster"]) for row in rows}),
            "excluded_for_complete_case": sorted(
                {
                    row["question_id"]
                    for row in paired
                    if row["analysis_include"] and row["question_id"] not in set(items)
                }
            ),
        },
        "estimand": "equal-weight mean keyed-answer accuracy across the named fixed models and common complete-case items",
        "model_classification": classification,
        "definitions": definitions,
        "within_condition": within_condition,
        "a_vs_b_within_group": changes,
        "condition_by_group_interactions": interactions,
        "secondary_triangulation": secondary,
        "primary_multiplicity": {
            "method": "Holm family-wise adjustment",
            "family_size": len(primary_test_objects),
            "family": sorted(primary_test_objects),
            "raw_p_values": primary_raw_p,
            "adjusted_p_values": primary_adjusted,
        },
        "decline_multiplicity": {
            "method": "Holm family-wise adjustment",
            "family_size": len(decline_test_objects),
            "family": sorted(decline_test_objects),
            "raw_p_values": decline_raw_p,
            "adjusted_p_values": decline_adjusted,
        },
        "secondary_multiplicity": {
            "method": "Holm family-wise adjustment",
            "family_size": len(secondary_test_objects),
            "family": sorted(secondary_test_objects),
            "raw_p_values": secondary_raw_p,
            "adjusted_p_values": secondary_adjusted,
        },
        "normality": "Not applicable: the source outcomes are binary; whole-cluster bootstrap intervals and exact cluster sign-flip tests do not require normally distributed 0/1 observations.",
        "interpretation_boundaries": [
            "The labels were requester-specified for this post-hoc report update and describe these four fixed models; the model group itself was not randomly sampled.",
            "The group p-values quantify benchmark-question evidence for these exact models, not a population-level large-versus-small or open-versus-proprietary model-class effect.",
            "No small proprietary model was tested, so size and model access are not a complete factorial design and cannot be separated as general causal attributes.",
            "Open-model is an analytical grouping label, not an adjudication of software-license terms.",
        ],
    }


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Continued fraction used by the regularized incomplete beta function."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / max(abs(d), 1e-30) * (1.0 if d >= 0 else -1.0)
    value = d
    for iteration in range(1, 301):
        doubled = 2 * iteration
        coefficient = (
            iteration * (b - iteration) * x / ((qam + doubled) * (a + doubled))
        )
        d = 1.0 + coefficient * d
        d = d if abs(d) >= 1e-30 else 1e-30
        c = 1.0 + coefficient / c
        c = c if abs(c) >= 1e-30 else 1e-30
        d = 1.0 / d
        value *= d * c
        coefficient = -(
            (a + iteration) * (qab + iteration) * x / ((a + doubled) * (qap + doubled))
        )
        d = 1.0 + coefficient * d
        d = d if abs(d) >= 1e-30 else 1e-30
        c = 1.0 + coefficient / c
        c = c if abs(c) >= 1e-30 else 1e-30
        d = 1.0 / d
        increment = d * c
        value *= increment
        if abs(increment - 1.0) < 1e-14:
            break
    return value


def regularized_beta(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a,b), without a SciPy dependency."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_beta_inverse = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    if x < (a + 1.0) / (a + b + 2.0):
        front = math.exp(a * math.log(x) + b * math.log1p(-x) + log_beta_inverse) / a
        return front * _beta_continued_fraction(a, b, x)
    front = math.exp(b * math.log1p(-x) + a * math.log(x) + log_beta_inverse) / b
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x)


def f_survival(value: float, numerator_df: int, denominator_df: int) -> float:
    """Upper-tail probability for an F statistic."""
    x = denominator_df / (denominator_df + numerator_df * value)
    return regularized_beta(denominator_df / 2.0, numerator_df / 2.0, x)


def cluster_robust_model_wald(rows: list[dict], outcome: str) -> dict:
    """CR1 linear-probability Wald F test of equal marginal model accuracies."""
    design = []
    response = []
    groups = []
    for row in rows:
        design.append(
            [1.0, *[float(row["model"] == model) for model in MODEL_ORDER[1:]]]
        )
        response.append(float(row[outcome]))
        groups.append(int(row["cluster"]))
    x = np.asarray(design)
    y = np.asarray(response)
    group = np.asarray(groups)
    inverse = np.linalg.inv(x.T @ x)
    beta = inverse @ x.T @ y
    residual = y - x @ beta
    meat = np.zeros((x.shape[1], x.shape[1]), dtype=np.float64)
    unique_groups = np.unique(group)
    for cluster in unique_groups:
        score = x[group == cluster].T @ residual[group == cluster]
        meat += np.outer(score, score)
    n, k = x.shape
    g = len(unique_groups)
    correction = (g / (g - 1)) * ((n - 1) / (n - k))
    covariance = correction * inverse @ meat @ inverse
    contrast = np.eye(k)[1:]
    difference = contrast @ beta
    contrast_covariance = contrast @ covariance @ contrast.T
    wald_statistic = float(difference @ np.linalg.inv(contrast_covariance) @ difference)
    numerator_df = 3
    denominator_df = g - 1
    f_statistic = wald_statistic / numerator_df
    return {
        "method": "CR1 clinical-cluster-robust linear-probability Wald F test",
        "null_hypothesis": "equal marginal keyed-answer accuracy across the four models",
        "f_statistic": f_statistic,
        "numerator_df": numerator_df,
        "denominator_df": denominator_df,
        "wald_chi_square": wald_statistic,
        "p_value": f_survival(f_statistic, numerator_df, denominator_df),
        "cells": n,
        "clinical_clusters": g,
        "reference_model": SHORT[MODEL_ORDER[0]],
        "coefficients_vs_reference": {
            SHORT[model]: float(beta[idx])
            for idx, model in enumerate(MODEL_ORDER[1:], start=1)
        },
    }


def within_condition_model_analysis(
    paired: list[dict], condition: str, seed: int
) -> dict:
    """Compare all four models on one identical complete-case item set."""
    included = [row for row in paired if row["analysis_include"]]
    item_models: dict[str, set[str]] = defaultdict(set)
    for row in included:
        item_models[row["question_id"]].add(row["model"])
    complete_items = {
        question_id
        for question_id, models in item_models.items()
        if models == set(MODEL_ORDER)
    }
    outcome = f"{condition}_correct"
    rows = [row for row in included if row["question_id"] in complete_items]
    if len(rows) != len(complete_items) * len(MODEL_ORDER):
        raise RuntimeError(
            f"unexpected {condition} complete-case model-comparison grain"
        )

    accuracy_intervals = cluster_accuracy_bootstrap(rows, outcome, seed)
    by_model = {}
    for model in MODEL_ORDER:
        selected = [row for row in rows if row["model"] == model]
        correct = sum(int(row[outcome]) for row in selected)
        by_model[SHORT[model]] = {
            "n": len(selected),
            "correct": correct,
            "accuracy": correct / len(selected),
            "cluster_bootstrap_ci95": accuracy_intervals[SHORT[model]]["ci95"],
            "bootstrap_boxplot": accuracy_intervals[SHORT[model]]["bootstrap_boxplot"],
        }

    pivot: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        pivot[row["question_id"]][row["model"]] = row
    pairwise = []
    pair_p_values = {}
    pair_index = 0
    for first_index, first in enumerate(MODEL_ORDER):
        for second in MODEL_ORDER[first_index + 1 :]:
            paired_rows = [
                {
                    "cluster": pivot[question_id][first]["cluster"],
                    "first_correct": int(pivot[question_id][first][outcome]),
                    "second_correct": int(pivot[question_id][second][outcome]),
                }
                for question_id in sorted(complete_items)
            ]
            summary = paired_summary(paired_rows, "second_correct", "first_correct")
            signflip = signflip_exact(paired_rows, "second_correct", "first_correct")
            bootstrap = cluster_bootstrap(
                paired_rows,
                "second_correct",
                "first_correct",
                None,
                seed + 100 + pair_index,
            )["estimates"]["pooled"]
            contrast_id = f"{SHORT[first]}_minus_{SHORT[second]}"
            pair_p_values[contrast_id] = signflip["p_two_sided"]
            pairwise.append(
                {
                    "contrast_id": contrast_id,
                    "first_model": SHORT[first],
                    "second_model": SHORT[second],
                    "paired_n": summary["n"],
                    "first_correct": summary["right_correct"],
                    "second_correct": summary["left_correct"],
                    "risk_difference_first_minus_second": summary[
                        "risk_difference_right_minus_left"
                    ],
                    "cluster_bootstrap_ci95": bootstrap["ci95"],
                    "exact_cluster_signflip_p": signflip["p_two_sided"],
                    "discordant_items": summary["left_only"] + summary["right_only"],
                }
            )
            pair_index += 1
    adjusted = holm(pair_p_values)
    for row in pairwise:
        row["holm_adjusted_cluster_signflip_p"] = adjusted[row["contrast_id"]]

    return {
        "population": {
            "items": len(complete_items),
            "cells": len(rows),
            "clinical_clusters": len({int(row["cluster"]) for row in rows}),
            "excluded_for_complete_case": sorted(
                {row["question_id"] for row in included} - complete_items
            ),
        },
        "outcome": "binary keyed-answer correctness",
        "by_model": by_model,
        "omnibus": cluster_robust_model_wald(rows, outcome),
        "pairwise": pairwise,
        "pairwise_multiplicity": "Holm adjustment across six model contrasts within condition",
        "normality": "Not applicable: correctness is binary; the tests do not assume normal 0/1 outcomes.",
    }


def primary_analysis(paired: list[dict], audited: dict) -> dict:
    rows = [row for row in paired if row["analysis_include"]]
    summaries = {}
    exact_p = {}
    signflips = {}
    for model in MODEL_ORDER:
        selected = [row for row in rows if row["model"] == model]
        label = SHORT[model]
        summaries[label] = paired_summary(selected, "A_correct", "B_correct")
        exact_p[label] = summaries[label]["exact_mcnemar_p_iid_pairs"]
        signflips[label] = signflip_exact(selected, "A_correct", "B_correct")
    summaries["pooled"] = paired_summary(rows, "A_correct", "B_correct")
    signflips["pooled"] = signflip_exact(rows, "A_correct", "B_correct")
    cluster_holm = holm(
        {
            key: value["p_two_sided"]
            for key, value in signflips.items()
            if key != "pooled"
        }
    )
    return {
        "population": {
            "cells": len(rows),
            "items": len({row["question_id"] for row in rows}),
            "clusters": len({row["cluster"] for row in rows}),
        },
        "by_model_and_pooled": summaries,
        "holm_adjusted_exact_mcnemar_p": holm(exact_p),
        "exact_cluster_signflip": signflips,
        "holm_adjusted_exact_cluster_signflip_p": cluster_holm,
        "cluster_bootstrap": cluster_bootstrap(
            rows, "A_correct", "B_correct", MODEL_ORDER, SEED
        ),
        "kish_cluster_count": kish_effective_clusters(rows),
        "audited_secondary_models": {
            key: value
            for key, value in audited["primary_openrouter_a_vs_b"].items()
            if key != "heterogeneity"
        },
        "audited_heterogeneity": audited["primary_openrouter_a_vs_b"]["heterogeneity"],
    }


def sensitivity_analysis(paired: list[dict], audited: dict) -> dict:
    sets = {
        "none": paired,
        "item_defects_only": [r for r in paired if not r["excl_item_defect"]],
        "nota_position_a_only": [r for r in paired if not r["excl_nota_position_a"]],
        "both_reported": [r for r in paired if r["analysis_include"]],
    }
    grid = {}
    for idx, (label, rows) in enumerate(sets.items()):
        summary = paired_summary(rows, "A_correct", "B_correct")
        bootstrap = cluster_bootstrap(
            rows, "A_correct", "B_correct", None, SEED + 100 + idx
        )
        grid[label] = {
            "cells": len(rows),
            "items": len({r["question_id"] for r in rows}),
            "clusters": len({r["cluster"] for r in rows}),
            "risk_difference_B_minus_A": summary["risk_difference_right_minus_left"],
            "ci95": bootstrap["estimates"]["pooled"]["ci95"],
        }
    no_defects = sets["item_defects_only"]
    position_a = [r for r in no_defects if r["excl_nota_position_a"]]
    other_positions = [r for r in no_defects if not r["excl_nota_position_a"]]
    return {
        "exclusion_grid": grid,
        "position_a_descriptive": {
            "position_a": paired_summary(position_a, "A_correct", "B_correct"),
            "other_positions": paired_summary(
                other_positions, "A_correct", "B_correct"
            ),
            "difference_in_risk_differences": (
                paired_summary(position_a, "A_correct", "B_correct")[
                    "risk_difference_right_minus_left"
                ]
                - paired_summary(other_positions, "A_correct", "B_correct")[
                    "risk_difference_right_minus_left"
                ]
            ),
            "audited_cleaned_interaction": audited["sensitivity"][
                "position_a_cleaned_interaction"
            ],
        },
        "leave_one_out_reported_set": leave_one_out(sets["both_reported"]),
    }


def cross_arm_analysis(cross: list[dict], audited: dict) -> dict:
    rows = [row for row in cross if row["analysis_include"]]
    summaries = {}
    p_values = {}
    signflips = {}
    for model in MODEL_ORDER:
        selected = [row for row in rows if row["model"] == model]
        label = SHORT[model]
        summaries[label] = paired_summary(selected, "or_correct", "gift_correct")
        p_values[label] = summaries[label]["exact_mcnemar_p_iid_pairs"]
        signflips[label] = signflip_exact(selected, "or_correct", "gift_correct")
    summaries["pooled"] = paired_summary(rows, "or_correct", "gift_correct")
    signflips["pooled"] = signflip_exact(rows, "or_correct", "gift_correct")
    cluster_holm = holm(
        {
            key: value["p_two_sided"]
            for key, value in signflips.items()
            if key != "pooled"
        }
    )
    return {
        "estimand": "GIFT minus OpenRouter accuracy on the all-four-model completed condition-A subset",
        "population": {
            "cells": len(rows),
            "items": len({row["question_id"] for row in rows}),
            "clusters": len({row["cluster"] for row in rows}),
        },
        "by_model_and_pooled": summaries,
        "holm_adjusted_exact_mcnemar_p": holm(p_values),
        "exact_cluster_signflip": signflips,
        "holm_adjusted_exact_cluster_signflip_p": cluster_holm,
        "cluster_bootstrap": cluster_bootstrap(
            rows, "or_correct", "gift_correct", MODEL_ORDER, SEED + 1_000
        ),
        "audited_partial_coverage": audited["cross_arm_gift_vs_openrouter_a"],
    }


def run_status(planned: dict[str, int]) -> dict:
    connection = immutable_connection(DB)
    names = ["expA_or_310726", "expB_or_310726", "expA_gift_310726", "expB_gift_310726"]
    output = {}
    for name in names:
        row = connection.execute(
            """
            WITH selected_calls AS (
                SELECT lc.id
                FROM experiments e
                JOIN logical_calls lc ON lc.experiment_id=e.id
                WHERE e.name=?
            ), attempt_counts AS (
                SELECT COUNT(DISTINCT a.logical_call_id) AS attempted_calls,
                       COUNT(*) AS attempts,
                       SUM(CASE WHEN COALESCE(a.status_code,0) != 200 THEN 1 ELSE 0 END)
                           AS failed_attempts
                FROM provider_attempts a
                JOIN selected_calls c ON c.id=a.logical_call_id
            ), score_counts AS (
                SELECT COUNT(DISTINCT s.logical_call_id) AS scored_calls
                FROM scores s
                JOIN selected_calls c ON c.id=s.logical_call_id
            )
            SELECT (SELECT COUNT(*) FROM selected_calls) AS logical_calls,
                   attempt_counts.attempted_calls,
                   score_counts.scored_calls,
                   attempt_counts.attempts,
                   attempt_counts.failed_attempts
            FROM attempt_counts CROSS JOIN score_counts
            """,
            (name,),
        ).fetchone()
        output[name] = {
            "planned_cells": planned[name],
            "logical_calls_created": row["logical_calls"],
            "distinct_calls_attempted": row["attempted_calls"],
            "scored_cells": row["scored_calls"],
            "attempts": row["attempts"],
            "failed_attempts": row["failed_attempts"] or 0,
            "scored_fraction_of_planned": row["scored_calls"] / planned[name],
        }
    connection.close()
    return output


def main() -> None:
    paired = json.loads(PAIRED.read_text(encoding="utf-8"))
    cross = json.loads(CROSS.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    if meta.get("export_version") != "v3":
        raise RuntimeError("final analysis requires the v3 canonical export")
    expected_hashes = meta.get("output_sha256", {})
    for path in (PAIRED, CROSS):
        if expected_hashes.get(path.name) != sha256(path):
            raise RuntimeError(
                f"input hash does not match dataset_meta.json: {path.name}"
            )
    expected_db_hash = meta.get("input_sha256", {}).get("experiment_database")
    actual_db_hash = sha256(DB)
    if not expected_db_hash or actual_db_hash != expected_db_hash:
        raise RuntimeError("experiment.sqlite does not match the v3 metadata snapshot")
    current_hashes = {
        "paired_clean.json": sha256(PAIRED),
        "cross_arm_A.json": sha256(CROSS),
    }
    audited = load_audited_secondary(current_hashes)
    within_conditions = {
        "A": within_condition_model_analysis(paired, "A", SEED + 2_000),
        "B": within_condition_model_analysis(paired, "B", SEED + 3_000),
    }
    grouped_comparisons = grouped_model_analysis(paired, SEED + 4_000)
    result = {
        "analysis_version": "v3.3-final",
        "bootstrap_replicates": N_BOOT,
        "input_sha256": {
            **current_hashes,
            "dataset_meta.json": sha256(META),
            "experiment.sqlite": actual_db_hash,
            "audited_secondary_results.json": sha256(AUDITED),
        },
        "code_sha256": {"final_analysis.py": sha256(Path(__file__).resolve())},
        "execution_environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "sqlite": sqlite3.sqlite_version,
            "quantile_method": "numpy default linear",
            "bootstrap_seed": SEED,
        },
        "audited_source_sha256": audited["source_sha256"],
        "within_condition_model_comparisons": within_conditions,
        "grouped_model_comparisons": grouped_comparisons,
        "primary_openrouter_a_vs_b": primary_analysis(paired, audited),
        "sensitivity": sensitivity_analysis(paired, audited),
        "cross_arm_gift_vs_openrouter_a": cross_arm_analysis(cross, audited),
        "run_status": run_status(
            {
                name: status["planned_cells"]
                for name, status in meta["experiment_status"].items()
            }
        ),
        "interpretation_boundaries": [
            "The observed A/B contrast bundles answer removal, semantics, genre, phrase repetition, position, run time, and unpinned routing; it does not isolate memorisation.",
            "GIFT condition B was never run, so no GIFT-pipeline A/B substitution contrast exists.",
            "GIFT condition A coverage is a sequential partial subset; the full-target pipeline difference is not identified without assumptions.",
            "Binary correctness is Bernoulli; normality tests on the raw endpoint are inapplicable.",
            "Requested size and model-access group contrasts describe four fixed deployments and do not identify population-level model-class effects.",
        ],
    }
    primary_population = result["primary_openrouter_a_vs_b"]["population"]
    expected_counts = meta["counts"]
    if primary_population != {
        "cells": expected_counts["ab_cells_analysis"],
        "items": expected_counts["ab_items_analysis"],
        "clusters": expected_counts["ab_clusters_analysis"],
    }:
        raise RuntimeError("primary population does not match dataset_meta.json")
    cross_population = result["cross_arm_gift_vs_openrouter_a"]["population"]
    if cross_population != {
        "cells": expected_counts["cross_cells_analysis"],
        "items": expected_counts["cross_items_analysis"],
        "clusters": expected_counts["cross_clusters_analysis"],
    }:
        raise RuntimeError("cross-arm population does not match dataset_meta.json")
    for condition, comparison in within_conditions.items():
        if comparison["population"] != {
            "items": 317,
            "cells": 1268,
            "clinical_clusters": 200,
            "excluded_for_complete_case": ["b320"],
        }:
            raise RuntimeError(
                f"unexpected within-condition population for {condition}"
            )
    if grouped_comparisons["population"] != {
        "items": 317,
        "cells": 1268,
        "clinical_clusters": 200,
        "excluded_for_complete_case": ["b320"],
    }:
        raise RuntimeError("unexpected grouped-model-comparison population")
    if grouped_comparisons["primary_multiplicity"]["family_size"] != 6:
        raise RuntimeError("unexpected primary grouped-comparison multiplicity family")
    if grouped_comparisons["decline_multiplicity"]["family_size"] != 4:
        raise RuntimeError("unexpected grouped-decline multiplicity family")
    if grouped_comparisons["secondary_multiplicity"]["family_size"] != 6:
        raise RuntimeError(
            "unexpected secondary grouped-comparison multiplicity family"
        )
    atomic_json_write(OUT, result)
    print(
        json.dumps(
            {
                "output": str(OUT),
                "primary": result["primary_openrouter_a_vs_b"]["by_model_and_pooled"][
                    "pooled"
                ],
                "cross_arm": result["cross_arm_gift_vs_openrouter_a"][
                    "by_model_and_pooled"
                ]["pooled"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
