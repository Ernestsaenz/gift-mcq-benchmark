#!/usr/bin/env python3
"""Build the reproducible OpenRouter-B hardest-200 sub-analysis."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
SOURCE_CELLS = PACKAGE / "exports/benchmark-6000-cell-results-adjusted.csv"
SOURCE_CATALOG = PACKAGE / "exports/benchmark-500-question-catalog-adjusted.csv"
TIE_NAMESPACE = "openrouter_B-hard200-v1|"
TOP_N = 200

MODEL_SPECS = [
    ("gemini", "Gemini 3.6 Flash", "google/gemini-3.6-flash"),
    ("glm", "GLM 5.2", "z-ai/glm-5.2"),
    ("qwen", "Qwen 3.6 35B", "qwen/qwen3.6-35b-a3b"),
    ("gemma", "Gemma 4 26B", "google/gemma-4-26b-a4b-it"),
]
MODEL_IDS = [model for _, _, model in MODEL_SPECS]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise AssertionError(f"Cannot infer CSV fields for empty output: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def fraction(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values[order[end]] == values[order[index]]:
            end += 1
        average = ((index + 1) + end) / 2
        for ordered_index in order[index:end]:
            ranks[ordered_index] = average
        index = end
    return ranks


def pearson(x: list[float], y: list[float]) -> float:
    x_mean = mean(x)
    y_mean = mean(y)
    numerator = sum((a - x_mean) * (b - y_mean) for a, b in zip(x, y))
    x_ss = sum((a - x_mean) ** 2 for a in x)
    y_ss = sum((b - y_mean) ** 2 for b in y)
    return numerator / math.sqrt(x_ss * y_ss) if x_ss and y_ss else 0.0


def spearman(x: list[float], y: list[float]) -> float:
    return pearson(average_ranks(x), average_ranks(y))


def phi(x: list[int], y: list[int]) -> float:
    n11 = sum(a == 1 and b == 1 for a, b in zip(x, y))
    n10 = sum(a == 1 and b == 0 for a, b in zip(x, y))
    n01 = sum(a == 0 and b == 1 for a, b in zip(x, y))
    n00 = sum(a == 0 and b == 0 for a, b in zip(x, y))
    denominator = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    return ((n11 * n00) - (n10 * n01)) / denominator if denominator else 0.0


def validate_source(
    all_cells: list[dict[str, str]],
    catalog: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    b_cells = [row for row in all_cells if row["arm"] == "openrouter_B"]
    a_cells = [row for row in all_cells if row["arm"] == "openrouter_A"]
    assert len(all_cells) == 6000
    assert len(b_cells) == len(a_cells) == 2000
    assert len(catalog) == 500
    assert {row["model"] for row in b_cells} == set(MODEL_IDS)
    assert len({row["source_key"] for row in b_cells}) == 500
    assert len({row["question_id"] for row in b_cells}) == 500
    assert len({row["cell_key"] for row in b_cells}) == 2000
    assert len({row["logical_call_id"] for row in b_cells}) == 2000
    assert all(row["condition"] == "B" for row in b_cells)
    assert all(row["parse_status"] == "ok" for row in b_cells)
    assert all(row["final_execution_status"] == "scored" for row in b_cells)
    assert all(row["exact_input_match_db"] == "TRUE" for row in b_cells)
    assert all(row["failure_class"] == "" for row in b_cells)
    assert all(row["effective_model"] == row["model"] for row in b_cells)
    assert sum(int(row["strict_correct"]) for row in b_cells) == 1468
    for row in b_cells:
        values = {
            row["strict_correct"],
            row["lenient_correct"],
            row["letter_correct"],
            row["text_correct"],
            row["answer_text_matches_provided"],
        }
        assert len(values) == 1
    return a_cells, b_cells


def assemble_questions(
    a_cells: list[dict[str, str]],
    b_cells: list[dict[str, str]],
    catalog: list[dict[str, str]],
) -> list[dict[str, Any]]:
    catalog_by_source = {row["source_key"]: row for row in catalog}
    a_by_cell = {(row["source_key"], row["model"]): row for row in a_cells}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in b_cells:
        grouped[row["source_key"]].append(row)

    invariant_fields = [
        "question_id",
        "source_key",
        "question_text",
        "option_a",
        "option_b",
        "option_c",
        "option_d",
        "correct_letter",
        "correct_option_text",
        "content_sha256",
        "raw_form_sha256",
        "origin",
        "region",
        "year",
        "specialty",
        "exam_part",
        "question_number",
        "negated_stem",
        "replacement_id",
        "replaces_question_id",
        "candidate_id",
    ]
    questions: list[dict[str, Any]] = []
    for source_key, rows in grouped.items():
        assert len(rows) == 4
        assert {row["model"] for row in rows} == set(MODEL_IDS)
        for field in invariant_fields:
            assert len({row[field] for row in rows}) == 1, (source_key, field)
        by_model = {row["model"]: row for row in rows}
        incorrect_count = sum(1 - int(row["strict_correct"]) for row in rows)
        correct_count = 4 - incorrect_count
        tie_hash = sha256_text(TIE_NAMESPACE + source_key)
        base = rows[0]
        catalog_row = catalog_by_source[source_key]
        question: dict[str, Any] = {
            "deterministic_rank": 0,
            "difficulty_rank_min": 0,
            "difficulty_rank_max": 0,
            "difficulty_tier_wrong_models": incorrect_count,
            "correct_models_B": correct_count,
            "difficulty_fraction": f"{incorrect_count / 4:.8f}",
            "selection_status": "",
            "cutoff_tie": incorrect_count == 1,
            "tie_break_namespace": TIE_NAMESPACE,
            "tie_break_sha256": tie_hash,
            "primary_500_position": int(catalog_row["primary_500_position"]),
            "question_id": base["question_id"],
            "source_key": source_key,
            "origin": base["origin"],
            "replacement_id": base["replacement_id"],
            "replaces_question_id": base["replaces_question_id"],
            "candidate_id": base["candidate_id"],
            "region": base["region"],
            "year": base["year"],
            "specialty": base["specialty"],
            "exam_part": base["exam_part"],
            "question_number": base["question_number"],
            "negated_stem": base["negated_stem"],
            "correct_letter": base["correct_letter"],
            "correct_option_text": base["correct_option_text"],
            "question_text": base["question_text"],
            "option_a": base["option_a"],
            "option_b": base["option_b"],
            "option_c": base["option_c"],
            "option_d": base["option_d"],
            "content_sha256": base["content_sha256"],
            "raw_form_sha256": base["raw_form_sha256"],
            "source_form_input_char_count": base["source_form_input_char_count"],
            "wrong_models_B": ";".join(
                label
                for slug, label, model in MODEL_SPECS
                if not int(by_model[model]["strict_correct"])
            ),
            "selected_letters_B": ";".join(
                f"{label}={by_model[model]['selected_letter']}"
                for _, label, model in MODEL_SPECS
            ),
            "correct_models_A": sum(
                int(a_by_cell[(source_key, model)]["strict_correct"])
                for model in MODEL_IDS
            ),
        }
        for slug, _, model in MODEL_SPECS:
            b_row = by_model[model]
            a_row = a_by_cell[(source_key, model)]
            question[f"{slug}_selected_letter_B"] = b_row["selected_letter"]
            question[f"{slug}_strict_correct_B"] = int(b_row["strict_correct"])
            question[f"{slug}_strict_correct_A"] = int(a_row["strict_correct"])
        questions.append(question)

    tier_counts = Counter(row["difficulty_tier_wrong_models"] for row in questions)
    questions.sort(
        key=lambda row: (
            -row["difficulty_tier_wrong_models"],
            row["tie_break_sha256"],
            row["source_key"],
            row["question_id"],
        )
    )
    for index, row in enumerate(questions, start=1):
        tier = row["difficulty_tier_wrong_models"]
        above = sum(count for wrong, count in tier_counts.items() if wrong > tier)
        row["deterministic_rank"] = index
        row["difficulty_rank_min"] = above + 1
        row["difficulty_rank_max"] = above + tier_counts[tier]
        if tier >= 2:
            row["selection_status"] = "INVARIANT_HARD_CORE"
        elif tier == 1 and index <= TOP_N:
            row["selection_status"] = "SELECTED_BOUNDARY_TIE"
        elif tier == 1:
            row["selection_status"] = "UNSELECTED_BOUNDARY_TIE"
        else:
            row["selection_status"] = "ALL_MODELS_CORRECT"
    return questions


def model_performance(
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    core = [row for row in questions if row["difficulty_tier_wrong_models"] >= 2]
    boundary = [row for row in questions if row["difficulty_tier_wrong_models"] == 1]
    selected = questions[:TOP_N]
    results: list[dict[str, Any]] = []
    for slug, label, model in MODEL_SPECS:
        full_correct = sum(row[f"{slug}_strict_correct_B"] for row in questions)
        core_correct = sum(row[f"{slug}_strict_correct_B"] for row in core)
        selected_correct = sum(row[f"{slug}_strict_correct_B"] for row in selected)
        selected_a_correct = sum(row[f"{slug}_strict_correct_A"] for row in selected)
        core_errors = len(core) - core_correct
        boundary_errors = sum(1 - row[f"{slug}_strict_correct_B"] for row in boundary)
        minimum_boundary_errors = max(0, 50 - (len(boundary) - boundary_errors))
        maximum_boundary_errors = min(50, boundary_errors)
        minimum_accuracy = fraction(
            TOP_N - core_errors - maximum_boundary_errors,
            TOP_N,
        )
        maximum_accuracy = fraction(
            TOP_N - core_errors - minimum_boundary_errors,
            TOP_N,
        )
        results.append(
            {
                "model_slug": slug,
                "model_label": label,
                "model": model,
                "full_B_correct": full_correct,
                "full_B_total": 500,
                "full_B_accuracy": f"{fraction(full_correct, 500):.8f}",
                "core150_B_correct": core_correct,
                "core150_B_total": len(core),
                "core150_B_accuracy": f"{fraction(core_correct, len(core)):.8f}",
                "hard200_B_correct": selected_correct,
                "hard200_B_incorrect": TOP_N - selected_correct,
                "hard200_B_accuracy": f"{fraction(selected_correct, TOP_N):.8f}",
                "hard200_A_correct": selected_a_correct,
                "hard200_A_accuracy": f"{fraction(selected_a_correct, TOP_N):.8f}",
                "B_minus_A_percentage_points": f"{(selected_correct - selected_a_correct) / 2:.2f}",
                "boundary_pool_model_errors": boundary_errors,
                "selected_boundary_model_errors": sum(
                    1 - row[f"{slug}_strict_correct_B"]
                    for row in selected
                    if row["difficulty_tier_wrong_models"] == 1
                ),
                "any_valid_tie_selection_accuracy_min": f"{minimum_accuracy:.8f}",
                "any_valid_tie_selection_accuracy_max": f"{maximum_accuracy:.8f}",
            }
        )
    return results


def difficulty_summary(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(row["difficulty_tier_wrong_models"] for row in questions)
    output = []
    cumulative = 0
    for wrong in range(4, -1, -1):
        count = counts[wrong]
        start = cumulative + 1
        cumulative += count
        output.append(
            {
                "wrong_models": wrong,
                "correct_models": 4 - wrong,
                "question_count": count,
                "question_fraction": f"{fraction(count, 500):.8f}",
                "difficulty_rank_min": start,
                "difficulty_rank_max": cumulative,
                "cumulative_hardest_questions": cumulative,
                "strict_incorrect_cells": wrong * count,
            }
        )
    return output


def error_patterns(
    questions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scopes = {
        "all_500": questions,
        "invariant_core_150": [
            row for row in questions if row["difficulty_tier_wrong_models"] >= 2
        ],
        "operational_hard_200": questions[:TOP_N],
    }
    output = []
    for scope, rows in scopes.items():
        counter = Counter(row["wrong_models_B"] or "NONE" for row in rows)
        for pattern, count in sorted(
            counter.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            output.append(
                {
                    "scope": scope,
                    "wrong_models": pattern,
                    "wrong_model_count": 0 if pattern == "NONE" else pattern.count(";") + 1,
                    "question_count": count,
                    "scope_question_count": len(rows),
                    "scope_fraction": f"{fraction(count, len(rows)):.8f}",
                }
            )
    return output


def pairwise_overlap(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for index, (slug_a, label_a, _) in enumerate(MODEL_SPECS):
        errors_a = [1 - row[f"{slug_a}_strict_correct_B"] for row in questions]
        set_a = {
            row["source_key"]
            for row in questions
            if not row[f"{slug_a}_strict_correct_B"]
        }
        for slug_b, label_b, _ in MODEL_SPECS[index + 1 :]:
            errors_b = [1 - row[f"{slug_b}_strict_correct_B"] for row in questions]
            set_b = {
                row["source_key"]
                for row in questions
                if not row[f"{slug_b}_strict_correct_B"]
            }
            intersection = len(set_a & set_b)
            union = len(set_a | set_b)
            output.append(
                {
                    "model_a": label_a,
                    "model_b": label_b,
                    "model_a_error_questions": len(set_a),
                    "model_b_error_questions": len(set_b),
                    "shared_error_questions": intersection,
                    "union_error_questions": union,
                    "jaccard": f"{fraction(intersection, union):.8f}",
                    "phi": f"{phi(errors_a, errors_b):.8f}",
                    "all_shared_errors_in_core150": all(
                        row["difficulty_tier_wrong_models"] >= 2
                        for row in questions
                        if row["source_key"] in set_a & set_b
                    ),
                }
            )
    return output


def subgroup_summary(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected_keys = {row["source_key"] for row in questions[:TOP_N]}
    core_keys = {
        row["source_key"]
        for row in questions
        if row["difficulty_tier_wrong_models"] >= 2
    }
    output = []
    for field in ["origin", "region", "year", "negated_stem", "correct_letter"]:
        levels = sorted({str(row[field]) for row in questions})
        for level in levels:
            rows = [row for row in questions if str(row[field]) == level]
            selected = sum(row["source_key"] in selected_keys for row in rows)
            core = sum(row["source_key"] in core_keys for row in rows)
            wrong_cells = sum(row["difficulty_tier_wrong_models"] for row in rows)
            output.append(
                {
                    "dimension": field,
                    "level": level,
                    "all_questions": len(rows),
                    "all_B_cells": len(rows) * 4,
                    "all_B_incorrect_cells": wrong_cells,
                    "all_B_accuracy": f"{1 - fraction(wrong_cells, len(rows) * 4):.8f}",
                    "core150_questions": core,
                    "core150_rate_within_level": f"{fraction(core, len(rows)):.8f}",
                    "hard200_questions": selected,
                    "hard200_rate_within_level": f"{fraction(selected, len(rows)):.8f}",
                }
            )
    return output


def strength_adjusted_sensitivity(
    questions: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    accuracy_by_slug = {
        row["model_slug"]: float(row["full_B_accuracy"]) for row in model_rows
    }
    adjusted = sorted(
        questions,
        key=lambda row: (
            -row["difficulty_tier_wrong_models"],
            -sum(
                accuracy_by_slug[slug]
                for slug, _, _ in MODEL_SPECS
                if not row[f"{slug}_strict_correct_B"]
            ),
            row["tie_break_sha256"],
            row["source_key"],
        ),
    )[:TOP_N]
    primary_keys = {row["source_key"] for row in questions[:TOP_N]}
    adjusted_keys = {row["source_key"] for row in adjusted}
    model_accuracy = {
        slug: fraction(
            sum(row[f"{slug}_strict_correct_B"] for row in adjusted),
            TOP_N,
        )
        for slug, _, _ in MODEL_SPECS
    }
    return {
        "definition": (
            "Within equal wrong-model tiers, sort by the sum of full-B accuracies "
            "of the models that erred, descending; then use the neutral hash."
        ),
        "intersection_questions": len(primary_keys & adjusted_keys),
        "union_questions": len(primary_keys | adjusted_keys),
        "jaccard": fraction(
            len(primary_keys & adjusted_keys),
            len(primary_keys | adjusted_keys),
        ),
        "model_B_accuracy": model_accuracy,
        "aggregate_B_accuracy": fraction(
            sum(
                row[f"{slug}_strict_correct_B"]
                for row in adjusted
                for slug, _, _ in MODEL_SPECS
            ),
            TOP_N * 4,
        ),
    }


def build_report(
    questions: list[dict[str, Any]],
    tiers: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
    overlaps: list[dict[str, Any]],
    subgroups: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    selected = questions[:TOP_N]
    unanimous = [row for row in selected if row["difficulty_tier_wrong_models"] == 4]
    region_rows = [row for row in subgroups if row["dimension"] == "region"]
    region_rows.sort(key=lambda row: (-row["hard200_questions"], row["level"]))
    lines = [
        "# OpenRouter B: the 200 operationally hardest questions",
        "",
        f"Generated: {summary['generated_at_utc']}",
        "",
        "Verdict: **complete descriptive sub-analysis; source validation passed**.",
        "",
        "## Definition and the rank-200 tie",
        "",
        "Difficulty is the number of the four OpenRouter B models that answered a "
        "question incorrectly. All models are weighted equally. Questions are ordered "
        "by wrong-model count descending. Exact ties use the SHA-256 of "
        f"`{TIE_NAMESPACE}<source_key>` ascending.",
        "",
        "This produces a **150-question invariant hard core** (at least two models "
        "wrong) and a deterministic 50-question sample from the 146 questions tied "
        "with exactly one model wrong. Those 50 are not uniquely harder than the 96 "
        "equally scored exclusions.",
        "",
        "| Wrong models | Correct models | Questions | Difficulty-rank interval |",
        "|---:|---:|---:|---:|",
    ]
    for row in tiers:
        lines.append(
            f"| {row['wrong_models']} | {row['correct_models']} | "
            f"{row['question_count']} | {row['difficulty_rank_min']}–"
            f"{row['difficulty_rank_max']} |"
        )
    lines.extend(
        [
            "",
            f"Rank 200 is `{summary['selection']['rank_200_question_id']}` "
            f"(`{summary['selection']['rank_200_source_key']}`); rank 201 is "
            f"`{summary['selection']['rank_201_question_id']}` "
            f"(`{summary['selection']['rank_201_source_key']}`).",
            "",
            "## Model performance",
            "",
            "These figures are descriptive and selection-conditioned. The same B "
            "outcomes define the hard set and are summarized below.",
            "",
            "| Model | Full B | Core 150 B | Hard 200 B | Same 200 in A | "
            "Any valid tie-set B range |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in model_rows:
        lines.append(
            f"| {row['model_label']} | {row['full_B_correct']}/500 "
            f"({pct(float(row['full_B_accuracy']))}) | "
            f"{row['core150_B_correct']}/150 "
            f"({pct(float(row['core150_B_accuracy']))}) | "
            f"{row['hard200_B_correct']}/200 "
            f"({pct(float(row['hard200_B_accuracy']))}) | "
            f"{row['hard200_A_correct']}/200 "
            f"({pct(float(row['hard200_A_accuracy']))}) | "
            f"{pct(float(row['any_valid_tie_selection_accuracy_min']))}–"
            f"{pct(float(row['any_valid_tie_selection_accuracy_max']))} |"
        )
    lines.extend(
        [
            "| **All model–question cells** | **1,468/2,000 (73.4%)** | "
            "**214/600 (35.7%)** | **364/800 (45.5%)** | "
            "**660/800 (82.5%)** | **45.5% invariant** |",
            "",
            "On these selected cells, B is 37.0 percentage points below A. This is "
            "not an unbiased estimate of the condition effect because the questions "
            "were selected for B errors. The full pre-specified 500-question A–B "
            "difference remains the primary estimate.",
            "",
            "## Error structure",
            "",
            "- 19 questions were missed by all four models.",
            "- 48 were missed by three models: Gemini alone was correct on 32, Gemma "
            "on 7, Qwen on 5, and GLM on 4.",
            "- 83 were missed by two models. The largest paired pattern was "
            "Gemma + Qwen (43 questions), followed by Gemma + GLM (18).",
            "- In the full one-error boundary, Gemma alone missed 104, Qwen 23, "
            "GLM 17, and Gemini 2.",
            "- Ten of the 19 all-model failures converged on the same wrong option; "
            "the other nine split across two wrong options.",
            "",
            "| Model pair | Shared-error questions | Jaccard | Phi |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in overlaps:
        lines.append(
            f"| {row['model_a']} + {row['model_b']} | "
            f"{row['shared_error_questions']} | {float(row['jaccard']):.3f} | "
            f"{float(row['phi']):.3f} |"
        )
    lines.extend(
        [
            "",
            "Every pairwise shared error lies in the invariant 150-question core.",
            "",
            "## Selected-set composition",
            "",
            f"Origins: {summary['composition']['origin_text']}. Negated stems: "
            f"{summary['composition']['negated_count']}/200. Correct-key letters: "
            f"{summary['composition']['correct_letter_text']}.",
            "",
            "| Region | Hard-200 questions | All benchmark questions |",
            "|---|---:|---:|",
        ]
    )
    for row in region_rows:
        lines.append(
            f"| {row['level']} | {row['hard200_questions']} | "
            f"{row['all_questions']} |"
        )
    lines.extend(
        [
            "",
            "These subgroup counts are unadjusted composition summaries. For source "
            "comparisons, the tie-free core rate in `subgroup-summary.csv` is safer "
            "than treating administrative hard-200 membership as a clinical effect.",
            "",
            "## Nineteen questions missed by all four models",
            "",
            "| Question | Source key | Key | B selected letters by model |",
            "|---|---|---:|---|",
        ]
    )
    for row in unanimous:
        lines.append(
            f"| {row['question_id']} | `{row['source_key']}` | "
            f"{row['correct_letter'].upper()} | {row['selected_letters_B']} |"
        )
    lines.extend(
        [
            "",
            "Full stems, options, source metadata, and per-model results are retained "
            "in the CSV outputs rather than repeated in this report.",
            "",
            "## Sensitivity and limitations",
            "",
            f"- A strength-adjusted B-only tie-break changes "
            f"{TOP_N - summary['strength_adjusted_sensitivity']['intersection_questions']} "
            "of the 200 members. Its intersection and Jaccard similarity with the "
            f"primary set are {summary['strength_adjusted_sensitivity']['intersection_questions']} "
            f"and {summary['strength_adjusted_sensitivity']['jaccard']:.3f}. Aggregate "
            "accuracy remains 45.5%, but the model-specific allocation changes.",
            "- Difficulty is based on one binary outcome per model, not repeated-run "
            "probabilities or an item-response model.",
            "- Within-tier order is administrative; it does not establish fine-grained "
            "clinical difficulty.",
            "- Condition B changes the keyed answer text, so content difficulty and "
            "answer-form sensitivity are inseparable in this subset.",
            "- No technical failure was counted as an incorrect answer. All 2,000 B "
            "cells were scored, parsed, and exact-input matched.",
            "- No inferential p-values are reported: this is an exploratory description "
            "of the complete fixed benchmark, and the hard set is outcome-selected.",
            "",
            "## Reproducibility",
            "",
            f"- Source cell CSV SHA-256: `{summary['source']['cell_csv_sha256']}`.",
            f"- Ordered selected-key SHA-256: "
            f"`{summary['selection']['ordered_source_keys_sha256']}`.",
            f"- Sorted selected-key-set SHA-256: "
            f"`{summary['selection']['sorted_source_keys_sha256']}`.",
            f"- Tie namespace: `{TIE_NAMESPACE}`.",
            "- Rebuild with `python3 build_analysis.py` from this directory.",
            "",
            "## Files",
            "",
            "- `difficulty-ranking-all-500.csv`: all questions, tiers, tie hashes, and "
            "per-model A/B outcomes.",
            "- `hardest-200-questions.csv`: the exact operational panel.",
            "- `hardest-200-model-cells.csv`: the 800 underlying OpenRouter B cells.",
            "- `boundary-tie-146.csv`: all equally scored rank-151–296 candidates.",
            "- `unanimously-wrong-19.csv`: the invariant all-model failures.",
            "- `model-performance.csv`, `difficulty-tier-summary.csv`, "
            "`error-pattern-summary.csv`, `model-error-overlap.csv`, and "
            "`subgroup-summary.csv`: supporting tables.",
            "- `summary.json`: machine-readable methods, validations, and results.",
            "- `INDEPENDENT_QA.md`: independent source-level recomputation and verdict.",
            "- `checksums.sha256`: hashes for this analysis package.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    all_cells = read_csv(SOURCE_CELLS)
    catalog = read_csv(SOURCE_CATALOG)
    a_cells, b_cells = validate_source(all_cells, catalog)
    questions = assemble_questions(a_cells, b_cells, catalog)
    assert len(questions) == 500

    selected = questions[:TOP_N]
    core = [row for row in questions if row["difficulty_tier_wrong_models"] >= 2]
    boundary = [row for row in questions if row["difficulty_tier_wrong_models"] == 1]
    assert len(selected) == 200
    assert len(core) == 150
    assert len(boundary) == 146
    assert Counter(row["difficulty_tier_wrong_models"] for row in selected) == {
        4: 19,
        3: 48,
        2: 83,
        1: 50,
    }

    selected_keys = {row["source_key"] for row in selected}
    b_by_source_model = {
        (row["source_key"], row["model"]): row for row in b_cells
    }
    selected_cells: list[dict[str, Any]] = []
    for question in selected:
        for slug, label, model in MODEL_SPECS:
            source = b_by_source_model[(question["source_key"], model)]
            selected_cells.append(
                {
                    "deterministic_question_rank": question["deterministic_rank"],
                    "selection_status": question["selection_status"],
                    "difficulty_tier_wrong_models": question[
                        "difficulty_tier_wrong_models"
                    ],
                    "cutoff_tie": question["cutoff_tie"],
                    "model_slug": slug,
                    "model_label": label,
                    "cell_key": source["cell_key"],
                    "question_id": source["question_id"],
                    "source_key": source["source_key"],
                    "model": source["model"],
                    "selected_letter": source["selected_letter"],
                    "selected_option_text": source["selected_option_text"],
                    "correct_letter": source["correct_letter"],
                    "correct_option_text": source["correct_option_text"],
                    "strict_correct": source["strict_correct"],
                    "parse_status": source["parse_status"],
                    "parse_method": source["parse_method"],
                    "attempt_count": source["attempt_count"],
                    "logical_call_id": source["logical_call_id"],
                    "result_database": source["result_database"],
                    "result_experiment": source["result_experiment"],
                    "score_origin": source["score_origin"],
                    "request_sha256": source["request_sha256"],
                    "response_sha256": source["response_sha256"],
                    "content_sha256": source["content_sha256"],
                    "raw_form_sha256": source["raw_form_sha256"],
                    "prompt_version": source["prompt_version"],
                    "exact_input_match_db": source["exact_input_match_db"],
                    "final_execution_status": source["final_execution_status"],
                }
            )
    assert len(selected_cells) == 800
    assert len({row["cell_key"] for row in selected_cells}) == 800

    tiers = difficulty_summary(questions)
    model_rows = model_performance(questions)
    patterns = error_patterns(questions)
    overlaps = pairwise_overlap(questions)
    subgroups = subgroup_summary(questions)
    sensitivity = strength_adjusted_sensitivity(questions, model_rows)

    ordered_key_text = "".join(f"{row['source_key']}\n" for row in selected)
    sorted_key_text = "".join(f"{key}\n" for key in sorted(selected_keys))
    transition_counts = Counter(
        (
            row[f"{slug}_strict_correct_A"],
            row[f"{slug}_strict_correct_B"],
        )
        for row in selected
        for slug, _, _ in MODEL_SPECS
    )
    unanimous = [row for row in selected if row["difficulty_tier_wrong_models"] == 4]
    unanimous_wrong_letter_diversity = Counter(
        len(
            {
                row[f"{slug}_selected_letter_B"]
                for slug, _, _ in MODEL_SPECS
            }
        )
        for row in unanimous
    )
    origin_counts = Counter(row["origin"] for row in selected)
    letter_counts = Counter(row["correct_letter"] for row in selected)
    input_lengths = [float(row["source_form_input_char_count"]) for row in questions]
    stem_lengths = [float(len(row["question_text"])) for row in questions]
    difficulty = [float(row["difficulty_tier_wrong_models"]) for row in questions]

    summary: dict[str, Any] = {
        "artifact_version": "openrouter-b-hardest-200-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "cell_csv": str(SOURCE_CELLS.relative_to(PACKAGE.parents[3])),
            "cell_csv_sha256": sha256_file(SOURCE_CELLS),
            "catalog_csv": str(SOURCE_CATALOG.relative_to(PACKAGE.parents[3])),
            "catalog_csv_sha256": sha256_file(SOURCE_CATALOG),
            "arm_filter": "openrouter_B",
        },
        "definition": {
            "primary": "4 - sum(strict_correct) across the four OpenRouter B models",
            "model_weighting": "equal",
            "sort": [
                "difficulty_tier_wrong_models descending",
                "sha256(tie namespace + source_key) ascending",
                "source_key ascending",
                "question_id ascending",
            ],
            "tie_namespace": TIE_NAMESPACE,
            "interpretation": (
                "The first 150 are invariant. The final 50 form a deterministic "
                "sample of a 146-question one-error tie."
            ),
        },
        "validation": {
            "source_rows": 6000,
            "openrouter_B_cells": len(b_cells),
            "openrouter_B_questions": len(questions),
            "models": MODEL_IDS,
            "cells_per_question": 4,
            "unique_B_cell_keys": len({row["cell_key"] for row in b_cells}),
            "unique_B_logical_call_ids": len(
                {row["logical_call_id"] for row in b_cells}
            ),
            "strict_correct_cells": sum(
                int(row["strict_correct"]) for row in b_cells
            ),
            "strict_incorrect_cells": sum(
                1 - int(row["strict_correct"]) for row in b_cells
            ),
            "all_scored": True,
            "all_parse_ok": True,
            "all_exact_input_match": True,
            "technical_failures_counted_incorrect": 0,
        },
        "difficulty_distribution": tiers,
        "selection": {
            "top_n": TOP_N,
            "invariant_core_questions": len(core),
            "boundary_tie_questions": len(boundary),
            "boundary_selected": 50,
            "boundary_not_selected": 96,
            "ordered_source_keys_sha256": sha256_text(ordered_key_text),
            "sorted_source_keys_sha256": sha256_text(sorted_key_text),
            "rank_200_question_id": selected[-1]["question_id"],
            "rank_200_source_key": selected[-1]["source_key"],
            "rank_201_question_id": questions[TOP_N]["question_id"],
            "rank_201_source_key": questions[TOP_N]["source_key"],
        },
        "model_performance": model_rows,
        "aggregate": {
            "full_B_correct": 1468,
            "full_B_total": 2000,
            "full_B_accuracy": 1468 / 2000,
            "core150_B_correct": sum(
                row[f"{slug}_strict_correct_B"]
                for row in core
                for slug, _, _ in MODEL_SPECS
            ),
            "core150_B_total": 600,
            "hard200_B_correct": sum(
                row[f"{slug}_strict_correct_B"]
                for row in selected
                for slug, _, _ in MODEL_SPECS
            ),
            "hard200_B_total": 800,
            "hard200_A_correct": sum(
                row[f"{slug}_strict_correct_A"]
                for row in selected
                for slug, _, _ in MODEL_SPECS
            ),
            "hard200_A_total": 800,
            "paired_transitions": {
                "both_correct": transition_counts[(1, 1)],
                "A_correct_B_wrong": transition_counts[(1, 0)],
                "A_wrong_B_correct": transition_counts[(0, 1)],
                "both_wrong": transition_counts[(0, 0)],
            },
        },
        "unanimously_wrong": {
            "questions": len(unanimous),
            "same_wrong_letter_all_models": unanimous_wrong_letter_diversity[1],
            "two_distinct_wrong_letters": unanimous_wrong_letter_diversity[2],
            "question_ids": [row["question_id"] for row in unanimous],
        },
        "composition": {
            "origin_counts": dict(origin_counts),
            "origin_text": ", ".join(
                f"{key}={value}" for key, value in sorted(origin_counts.items())
            ),
            "negated_count": sum(row["negated_stem"] == "True" for row in selected),
            "correct_letter_counts": dict(letter_counts),
            "correct_letter_text": ", ".join(
                f"{key.upper()}={value}" for key, value in sorted(letter_counts.items())
            ),
        },
        "length_exploration": {
            "spearman_input_chars_vs_wrong_model_count": spearman(
                input_lengths,
                difficulty,
            ),
            "spearman_stem_chars_vs_wrong_model_count": spearman(
                stem_lengths,
                difficulty,
            ),
        },
        "strength_adjusted_sensitivity": sensitivity,
        "limitations": [
            "One observed binary response per model and question.",
            "Outcome-selected descriptive subset; not an unbiased condition comparison.",
            "Ranks 151-296 are tied on the primary equal-model difficulty measure.",
            "Metadata comparisons are unadjusted and exploratory.",
            "Condition-B answer-form sensitivity and content difficulty are inseparable.",
        ],
    }

    assert summary["selection"]["ordered_source_keys_sha256"] == (
        "9035f0e99364460f0036f5c210e35d59c3e2786bb409d2dbeb9fd9325dab1128"
    )
    assert summary["selection"]["sorted_source_keys_sha256"] == (
        "ee9484af0041f05cad216f1e6368e30d88970765ccaff03a84314105f325d13e"
    )
    assert summary["aggregate"]["hard200_B_correct"] == 364
    assert summary["aggregate"]["hard200_A_correct"] == 660

    write_csv(HERE / "difficulty-ranking-all-500.csv", questions)
    write_csv(HERE / "hardest-200-questions.csv", selected)
    write_csv(HERE / "hardest-200-model-cells.csv", selected_cells)
    write_csv(HERE / "boundary-tie-146.csv", boundary)
    write_csv(HERE / "unanimously-wrong-19.csv", unanimous)
    write_csv(HERE / "model-performance.csv", model_rows)
    write_csv(HERE / "difficulty-tier-summary.csv", tiers)
    write_csv(HERE / "error-pattern-summary.csv", patterns)
    write_csv(HERE / "model-error-overlap.csv", overlaps)
    write_csv(HERE / "subgroup-summary.csv", subgroups)
    write_json(HERE / "summary.json", summary)
    report = build_report(
        questions,
        tiers,
        model_rows,
        overlaps,
        subgroups,
        summary,
    )
    (HERE / "REPORT.md").write_text(report, encoding="utf-8")

    checksum_paths = [
        HERE / "build_analysis.py",
        HERE / "REPORT.md",
        HERE / "summary.json",
        HERE / "difficulty-ranking-all-500.csv",
        HERE / "hardest-200-questions.csv",
        HERE / "hardest-200-model-cells.csv",
        HERE / "boundary-tie-146.csv",
        HERE / "unanimously-wrong-19.csv",
        HERE / "model-performance.csv",
        HERE / "difficulty-tier-summary.csv",
        HERE / "error-pattern-summary.csv",
        HERE / "model-error-overlap.csv",
        HERE / "subgroup-summary.csv",
    ]
    independent_qa = HERE / "INDEPENDENT_QA.md"
    if independent_qa.exists():
        checksum_paths.append(independent_qa)
    checksum_text = "".join(
        f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths
    )
    (HERE / "checksums.sha256").write_text(checksum_text, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "source_sha256": summary["source"]["cell_csv_sha256"],
                "selected_questions": len(selected),
                "selected_cells": len(selected_cells),
                "core_questions": len(core),
                "boundary_pool": len(boundary),
                "hard200_B_correct": summary["aggregate"]["hard200_B_correct"],
                "hard200_A_correct": summary["aggregate"]["hard200_A_correct"],
                "selected_set_sha256": summary["selection"][
                    "sorted_source_keys_sha256"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
