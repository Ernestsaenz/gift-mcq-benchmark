"""Build the canonical portable-report artifact from verified v3.3 outputs.

The v3.3.1 presentation repair makes every native boxplot's five-number geometry visible; it does
not change the approved v3.3 observations, bootstrap summaries, or inferential results.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPORT = HERE / "REPORT.md"
RESULTS = HERE / "final_analysis_results.json"
META = HERE / "dataset_meta.json"
QA_SUMMARY = HERE / "qa_workflows" / "qa_summary.json"
OUT = HERE / "report_artifact.json"
SOURCE_DB = HERE / "report_source.sqlite"
# A deterministic release timestamp keeps clean builds byte-identical. It identifies the reviewed
# snapshot, not the time at which an invented query supposedly ran.
GENERATED_AT = "2026-07-31T15:00:00+02:00"

MODEL_LABELS = {
    "gemini-3.6-flash": "Gemini 3.6 Flash",
    "glm-5.2": "GLM 5.2",
    "qwen3.6-35b-a3b": "Qwen 3.6 35B",
    "gemma-4-26b-a4b-it": "Gemma 4 26B",
}


def pct_interval(values: list[float]) -> str:
    return f"[{100 * values[0]:+.2f}, {100 * values[1]:+.2f}] pp"


def percent_range(values: list[float]) -> str:
    return f"[{100 * values[0]:.2f}%, {100 * values[1]:.2f}%]"


def scientific_text(value: float) -> str:
    """Reader-facing scientific notation that table renderers cannot coerce to zero."""
    mantissa, exponent = f"{value:.2e}".split("e")
    superscript = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return f"{mantissa} × 10{str(int(exponent)).translate(superscript)}"


def p_value_text(value: float) -> str:
    value_text = f"{value:.4g}" if value >= 0.001 else scientific_text(value)
    return f"p = {value_text}"


def boxplot_row(
    label: str,
    estimate: float,
    summary: dict,
    ci95: list[float],
    *,
    clinical_clusters: int,
    bootstrap_replicates: int,
    test_annotation: str,
    signed: bool,
) -> dict:
    """Create one annotated native-boxplot row from a bootstrap distribution."""
    estimate_text = f"{100 * estimate:+.2f} pp" if signed else f"{100 * estimate:.2f}%"
    row = {
        "display_label": f"{label} · {estimate_text}",
        "comparison": label,
        "observed_estimate": estimate,
        "ci95_low": ci95[0],
        "ci95_high": ci95[1],
        "minimum": summary["minimum"],
        "q1": summary["q1"],
        "median": summary["median"],
        "q3": summary["q3"],
        "maximum": summary["maximum"],
        "clinical_clusters": clinical_clusters,
        "bootstrap_replicates": bootstrap_replicates,
        "test_annotation": test_annotation,
    }
    five_number = [
        row["minimum"],
        row["q1"],
        row["median"],
        row["q3"],
        row["maximum"],
    ]
    if five_number != sorted(five_number):
        raise RuntimeError(f"invalid bootstrap boxplot row: {label}")
    return row


def boxplot_chart(
    chart_id: str,
    title: str,
    subtitle: str,
    dataset: str,
    header_markdown: str,
    x_axis_title: str,
    question: str,
) -> dict:
    """Return one source-backed native boxplot using the shared artifact contract."""
    return {
        "id": chart_id,
        "title": title,
        "subtitle": subtitle,
        "headerMarkdown": header_markdown,
        "intent": "distribution",
        "question": question,
        "rationale": (
            "A box plot compactly compares deterministic whole-clinical-cluster "
            "bootstrap sampling distributions while the adjacent table preserves exact "
            "confidence intervals and multiplicity-adjusted tests."
        ),
        "comparisonContext": {
            "denominator": "Common cleaned item population stated in the section",
            "grain": "100,000 whole-clinical-cluster bootstrap ratio estimates",
            "normalization": "Cell-weighted ratio estimator with clusters resampled intact",
            "unit": "Accuracy or accuracy difference",
        },
        "type": "boxPlot",
        "dataset": dataset,
        "sourceId": dataset,
        "encodings": {
            "x": {
                "field": "display_label",
                "type": "nominal",
                "label": "Comparison and observed estimate",
            },
            "y": {
                "fields": ["minimum", "q1", "median", "q3", "maximum"],
                "type": "quantitative",
                "label": "Bootstrap estimate",
                "format": "percent",
            },
        },
        "xAxisTitle": x_axis_title,
        "valueFormat": "percent",
        "maxRows": 8,
        "layout": "full",
    }


def split_markdown(markdown: str) -> list[tuple[str, str]]:
    """Return stable block IDs and one H1/H2 section per Markdown block."""
    parts = re.split(r"(?m)^## ", markdown.rstrip())
    output = [("title", parts[0].strip())]
    for part in parts[1:]:
        heading = part.splitlines()[0].strip()
        block_id = re.sub(r"[^a-z0-9]+", "_", heading.casefold()).strip("_")
        output.append((block_id, f"## {part.strip()}"))
    return output


def strip_pipe_tables(markdown: str) -> str:
    """Remove only syntactically complete GFM pipe tables from narrative blocks.

    The same rows are rendered as native report tables. Restricting removal to a header followed
    by a separator avoids hiding ordinary prose that merely contains a pipe character.
    """
    lines = markdown.splitlines()
    separator = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$")
    output: list[str] = []
    index = 0
    while index < len(lines):
        current = lines[index].strip()
        is_header = current.startswith("|") and current.endswith("|")
        if index + 1 < len(lines) and is_header and separator.match(lines[index + 1]):
            index += 2
            while index < len(lines):
                row = lines[index].strip()
                if not (row.startswith("|") and row.endswith("|")):
                    break
                index += 1
            if output and output[-1] != "":
                output.append("")
            continue
        output.append(lines[index])
        index += 1
    return "\n".join(output)


def split_clinical_interpretation(markdown: str) -> tuple[str, str | None]:
    """Keep each physician-facing explanation below its section's native result widgets."""
    marker = "\n### Clinical interpretation for physicians\n"
    if marker not in markdown:
        return markdown, None
    evidence, clinical = markdown.split(marker, 1)
    return (
        evidence.rstrip(),
        f"### Clinical interpretation for physicians\n\n{clinical.strip()}",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json_write(path: Path, value: dict) -> None:
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


def source_entry(
    source_id: str,
    label: str,
    path: str,
    description: str,
    *,
    query: str | None = None,
    table: str | None = None,
) -> tuple[dict, dict]:
    absolute = HERE.parents[2] / path
    source = {
        "id": source_id,
        "label": label,
        "path": path,
        "sha256": sha256(absolute),
        "description": description,
    }
    evidence = dict(source)
    if query and table:
        evidence["query"] = {
            "engine": "sqlite",
            "description": description,
            "sql": query,
            "tables_used": [table],
            "executed_at": GENERATED_AT,
        }
    return source, evidence


def materialize_report_source(datasets: dict[str, list[dict]]) -> None:
    """Create the exact replayable SQLite relations used by native report widgets."""
    with tempfile.NamedTemporaryFile(
        dir=HERE, prefix=".report-source.", suffix=".sqlite", delete=False
    ) as handle:
        temporary = Path(handle.name)
    try:
        connection = sqlite3.connect(temporary)
        for table, rows in datasets.items():
            if not rows:
                continue
            columns = list(rows[0])
            if any(list(row) != columns for row in rows):
                raise RuntimeError(f"inconsistent row shape in report dataset: {table}")
            declarations = []
            for column in columns:
                values = [row[column] for row in rows if row[column] is not None]
                kind = (
                    "REAL"
                    if any(isinstance(value, float) for value in values)
                    else "INTEGER"
                )
                if any(isinstance(value, str) for value in values):
                    kind = "TEXT"
                declarations.append(f'"{column}" {kind}')
            connection.execute(f'CREATE TABLE "{table}" ({", ".join(declarations)})')
            placeholders = ",".join("?" for _ in columns)
            quoted = ",".join(f'"{column}"' for column in columns)
            connection.executemany(
                f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
                [[row[column] for column in columns] for row in rows],
            )
        connection.commit()
        connection.execute("VACUUM")
        connection.close()
        os.replace(temporary, SOURCE_DB)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    report_text = REPORT.read_text(encoding="utf-8")
    result = json.loads(RESULTS.read_text(encoding="utf-8"))
    meta = json.loads(META.read_text(encoding="utf-8"))
    if not QA_SUMMARY.is_file():
        raise RuntimeError(
            "qa_workflows/qa_summary.json is required for the release artifact"
        )
    qa_rows = json.loads(QA_SUMMARY.read_text(encoding="utf-8"))
    if len(qa_rows) < 10 or len({row.get("workflow") for row in qa_rows}) != len(
        qa_rows
    ):
        raise RuntimeError(
            "QA summary must contain at least ten uniquely named workflows"
        )
    required_qa_fields = {
        "workflow",
        "scope",
        "verdict",
        "resolution",
        "final_status",
    }
    if any(set(row) != required_qa_fields for row in qa_rows):
        raise RuntimeError(
            f"every QA row must contain exactly {sorted(required_qa_fields)}"
        )
    qa_not_passed = [
        row["workflow"] for row in qa_rows if row["final_status"].upper() != "PASS"
    ]

    dataset_rows = [
        {
            "dataset": "Condition A",
            "items": 474,
            "construction": "500 source items minus 17 three-option items and 9 source-level defects; keyed text retained",
        },
        {
            "dataset": "Condition B",
            "items": 423,
            "construction": "A minus 51 manipulation-incompatible items; keyed text replaced by the position-dependent preceding-options phrase; key letter unchanged",
        },
    ]
    exclusion_rows = [
        {
            "rule": "Out-of-domain law/administration",
            "declared_globally": "19",
            "present_in_ab": "16",
            "basis": "Employment, privacy, health-administration, and service-catalogue content outside digestive medicine",
        },
        {
            "rule": "User-adjudicated key defect",
            "declared_globally": "3",
            "present_in_ab": "3",
            "basis": "b178, b197, b496; detailed clinical citation ledger was not preserved",
        },
        {
            "rule": "Preceding-options phrase in option a",
            "declared_globally": "—",
            "present_in_ab": "91",
            "basis": "The phrase has no antecedent when printed first",
        },
    ]

    within = result["within_condition_model_comparisons"]
    condition_model_rows: dict[str, list[dict]] = {}
    condition_model_box_rows: dict[str, list[dict]] = {}
    condition_pair_rows: dict[str, list[dict]] = {}
    for condition in ("A", "B"):
        comparison = within[condition]
        condition_model_rows[condition] = [
            {
                "model": model,
                "correct": stats["correct"],
                "n": stats["n"],
                "accuracy": stats["accuracy"],
                "ci95": percent_range(stats["cluster_bootstrap_ci95"]),
            }
            for model, stats in comparison["by_model"].items()
        ]
        condition_model_box_rows[condition] = [
            boxplot_row(
                MODEL_LABELS.get(model, model),
                stats["accuracy"],
                stats["bootstrap_boxplot"],
                stats["cluster_bootstrap_ci95"],
                clinical_clusters=comparison["population"]["clinical_clusters"],
                bootstrap_replicates=result["bootstrap_replicates"],
                test_annotation=(
                    "Four-model omnibus "
                    f"{p_value_text(comparison['omnibus']['p_value'])}; "
                    "pairwise Holm tests are in the adjacent table"
                ),
                signed=False,
            )
            for model, stats in comparison["by_model"].items()
        ]
        condition_pair_rows[condition] = [
            {
                "comparison": f"{row['first_model']} − {row['second_model']}",
                "paired_n": row["paired_n"],
                "difference": row["risk_difference_first_minus_second"],
                "ci95": pct_interval(row["cluster_bootstrap_ci95"]),
                "exact_cluster_p": p_value_text(row["exact_cluster_signflip_p"]),
                "holm_p": p_value_text(row["holm_adjusted_cluster_signflip_p"]),
            }
            for row in comparison["pairwise"]
        ]

    grouped = result["grouped_model_comparisons"]
    group_labels = {
        "large": "Large",
        "small": "Small",
        "open_model": "Open-model",
        "proprietary": "Proprietary (gemini)",
    }
    dimension_labels = {"size": "Size", "openness": "Model access"}
    classification_rows = [
        {
            "model": row["model"],
            "size_group": group_labels[row["size_group"]],
            "access_group": group_labels[row["access_group"]],
        }
        for row in grouped["model_classification"]
    ]
    condition_group_rows: dict[str, list[dict]] = {}
    condition_group_box_rows: dict[str, list[dict]] = {}
    for condition in ("A", "B"):
        condition_result = grouped["within_condition"][condition]
        condition_group_rows[condition] = []
        condition_group_box_rows[condition] = []
        for dimension in ("size", "openness"):
            contrast = condition_result["contrasts"][dimension]
            first = condition_result["group_accuracies"][contrast["first_group"]]
            second = condition_result["group_accuracies"][contrast["second_group"]]
            condition_group_rows[condition].append(
                {
                    "grouping": dimension_labels[dimension],
                    "comparison": (
                        f"{group_labels[contrast['first_group']]} − "
                        f"{group_labels[contrast['second_group']]}"
                    ),
                    "first_accuracy": first["accuracy"],
                    "second_accuracy": second["accuracy"],
                    "difference": contrast["risk_difference_first_minus_second"],
                    "ci95": pct_interval(contrast["cluster_bootstrap_ci95"]),
                    "exact_cluster_p": p_value_text(
                        contrast["exact_cluster_signflip_p"]
                    ),
                    "holm_p": p_value_text(
                        contrast["holm_adjusted_p_across_six_primary_group_tests"]
                    ),
                }
            )
            comparison_label = (
                f"{group_labels[contrast['first_group']]} − "
                f"{group_labels[contrast['second_group']]}"
            )
            test_annotation = (
                f"{comparison_label}: Holm "
                f"{p_value_text(contrast['holm_adjusted_p_across_six_primary_group_tests'])}"
            )
            for group, accuracy in (
                (contrast["first_group"], first),
                (contrast["second_group"], second),
            ):
                condition_group_box_rows[condition].append(
                    boxplot_row(
                        group_labels[group],
                        accuracy["accuracy"],
                        accuracy["bootstrap_boxplot"],
                        accuracy["cluster_bootstrap_ci95"],
                        clinical_clusters=grouped["population"]["clinical_clusters"],
                        bootstrap_replicates=accuracy["bootstrap_replicates"],
                        test_annotation=test_annotation,
                        signed=False,
                    )
                )

    group_change_rows = []
    group_change_box_rows = []
    for group in ("large", "small", "open_model", "proprietary"):
        change = grouped["a_vs_b_within_group"][group]
        group_change_rows.append(
            {
                "grouping": "Size" if group in {"large", "small"} else "Model access",
                "group": group_labels[group],
                "models": ", ".join(change["models"]),
                "model_count": change["model_count"],
                "a_accuracy": grouped["within_condition"]["A"]["group_accuracies"][
                    group
                ]["accuracy"],
                "b_accuracy": grouped["within_condition"]["B"]["group_accuracies"][
                    group
                ]["accuracy"],
                "change": change["risk_difference_b_minus_a"],
                "ci95": pct_interval(change["cluster_bootstrap_ci95"]),
                "exact_cluster_p": p_value_text(change["exact_cluster_signflip_p"]),
                "holm_p": p_value_text(
                    change["holm_adjusted_p_across_four_group_declines"]
                ),
            }
        )
        group_change_box_rows.append(
            boxplot_row(
                group_labels[group],
                change["risk_difference_b_minus_a"],
                change["bootstrap_boxplot"],
                change["cluster_bootstrap_ci95"],
                clinical_clusters=change["clinical_clusters"],
                bootstrap_replicates=change["bootstrap_replicates"],
                test_annotation=(
                    "A-to-B change: Holm "
                    f"{p_value_text(change['holm_adjusted_p_across_four_group_declines'])}"
                ),
                signed=True,
            )
        )

    group_interaction_rows = []
    group_interaction_box_rows = []
    for dimension in ("size", "openness"):
        interaction = grouped["condition_by_group_interactions"][dimension]
        group_interaction_rows.append(
            {
                "grouping": dimension_labels[dimension],
                "comparison": (
                    f"{group_labels[interaction['first_group']]} change − "
                    f"{group_labels[interaction['second_group']]} change"
                ),
                "difference_in_changes": interaction["difference_in_b_minus_a_changes"],
                "ci95": pct_interval(interaction["cluster_bootstrap_ci95"]),
                "exact_cluster_p": p_value_text(
                    interaction["exact_cluster_signflip_p"]
                ),
                "holm_p": p_value_text(
                    interaction["holm_adjusted_p_across_six_primary_group_tests"]
                ),
                "conclusion": (
                    "Difference not resolved"
                    if dimension == "size"
                    else "Open-model mean lost more; singleton-proprietary caveat"
                ),
            }
        )
        group_interaction_box_rows.append(
            boxplot_row(
                ("Large−small change" if dimension == "size" else "Open−gemini change"),
                interaction["difference_in_b_minus_a_changes"],
                interaction["bootstrap_boxplot"],
                interaction["cluster_bootstrap_ci95"],
                clinical_clusters=interaction["clinical_clusters"],
                bootstrap_replicates=interaction["bootstrap_replicates"],
                test_annotation=(
                    "Primary interaction: Holm "
                    f"{p_value_text(interaction['holm_adjusted_p_across_six_primary_group_tests'])}"
                ),
                signed=True,
            )
        )

    secondary_group_rows = []
    secondary_labels = {
        "openness_within_large": "Within large: gemini − glm",
        "size_within_open": "Within open-model: glm − mean(qwen, gemma)",
    }
    for dimension in ("openness_within_large", "size_within_open"):
        secondary = grouped["secondary_triangulation"][dimension]
        a_contrast = secondary["within_condition"]["A"]["contrast"]
        b_contrast = secondary["within_condition"]["B"]["contrast"]
        interaction = secondary["condition_interaction"]
        secondary_group_rows.append(
            {
                "perspective": secondary_labels[dimension],
                "a_difference": a_contrast["risk_difference_first_minus_second"],
                "a_holm_p": p_value_text(
                    a_contrast["holm_adjusted_p_across_six_secondary_tests"]
                ),
                "b_difference": b_contrast["risk_difference_first_minus_second"],
                "b_holm_p": p_value_text(
                    b_contrast["holm_adjusted_p_across_six_secondary_tests"]
                ),
                "difference_in_changes": interaction["difference_in_b_minus_a_changes"],
                "interaction_ci95": pct_interval(interaction["cluster_bootstrap_ci95"]),
                "interaction_holm_p": p_value_text(
                    interaction["holm_adjusted_p_across_six_secondary_tests"]
                ),
            }
        )
        interaction_label = (
            "Gemini−GLM change"
            if dimension == "openness_within_large"
            else "GLM−small-open change"
        )
        group_interaction_box_rows.append(
            boxplot_row(
                interaction_label,
                interaction["difference_in_b_minus_a_changes"],
                interaction["bootstrap_boxplot"],
                interaction["cluster_bootstrap_ci95"],
                clinical_clusters=interaction["clinical_clusters"],
                bootstrap_replicates=interaction["bootstrap_replicates"],
                test_annotation=(
                    "Secondary interaction: Holm "
                    f"{p_value_text(interaction['holm_adjusted_p_across_six_secondary_tests'])}"
                ),
                signed=True,
            )
        )

    primary = result["primary_openrouter_a_vs_b"]
    primary_rows = []
    accuracy_rows = []
    primary_change_box_rows = []
    for model, stats in primary["by_model_and_pooled"].items():
        ci = primary["cluster_bootstrap"]["estimates"][model]["ci95"]
        primary_rows.append(
            {
                "model": "Cell-weighted pooled" if model == "pooled" else model,
                "n": stats["n"],
                "a_accuracy": stats["left_accuracy"],
                "b_accuracy": stats["right_accuracy"],
                "change": stats["risk_difference_right_minus_left"],
                "ci95": pct_interval(ci),
                "exact_cluster_p": p_value_text(
                    primary["exact_cluster_signflip"][model]["p_two_sided"]
                ),
                "holm_cluster_p": (
                    "—"
                    if model == "pooled"
                    else p_value_text(
                        primary["holm_adjusted_exact_cluster_signflip_p"][model]
                    )
                ),
            }
        )
        if model == "pooled":
            continue
        bootstrap = primary["cluster_bootstrap"]["estimates"][model]
        primary_change_box_rows.append(
            boxplot_row(
                MODEL_LABELS.get(model, model),
                stats["risk_difference_right_minus_left"],
                bootstrap["bootstrap_boxplot"],
                bootstrap["ci95"],
                clinical_clusters=primary["cluster_bootstrap"]["clusters"],
                bootstrap_replicates=primary["cluster_bootstrap"]["replicates"],
                test_annotation=(
                    "A-to-B change: Holm "
                    f"{p_value_text(primary['holm_adjusted_exact_cluster_signflip_p'][model])}"
                ),
                signed=True,
            )
        )
        accuracy_rows.extend(
            [
                {
                    "model": model,
                    "condition": "A · original key text",
                    "accuracy": stats["left_accuracy"],
                },
                {
                    "model": model,
                    "condition": "B · preceding-options meta-answer",
                    "accuracy": stats["right_accuracy"],
                },
            ]
        )

    pooled = primary["by_model_and_pooled"]["pooled"]
    pooled_ci = primary["cluster_bootstrap"]["estimates"]["pooled"]["ci95"]
    summary_rows = [
        {
            "a_accuracy": pooled["left_accuracy"],
            "b_accuracy": pooled["right_accuracy"],
            "change": pooled["risk_difference_right_minus_left"],
            "model_adjusted_or": primary["audited_secondary_models"][
                "model_adjusted_logistic_or"
            ]["estimate"],
            "effective_clusters": primary["kish_cluster_count"]["effective_clusters"],
            "gift_scored_fraction": result["run_status"]["expA_gift_310726"][
                "scored_fraction_of_planned"
            ],
        }
    ]

    sensitivity_rows = []
    sensitivity_labels = {
        "none": "None",
        "item_defects_only": "Item defects only",
        "nota_position_a_only": "Position-a only",
        "both_reported": "Both · reported set",
    }
    for key, row in result["sensitivity"]["exclusion_grid"].items():
        sensitivity_rows.append(
            {
                "exclusions": sensitivity_labels[key],
                "items": row["items"],
                "cells": row["cells"],
                "change": row["risk_difference_B_minus_A"],
                "ci95": pct_interval(row["ci95"]),
            }
        )

    cross = result["cross_arm_gift_vs_openrouter_a"]
    cross_rows = []
    cross_chart_rows = []
    cross_box_rows = []
    for model, stats in cross["by_model_and_pooled"].items():
        ci = cross["cluster_bootstrap"]["estimates"][model]["ci95"]
        row = {
            "model": "Cell-weighted pooled" if model == "pooled" else model,
            "openrouter_accuracy": stats["left_accuracy"],
            "gift_accuracy": stats["right_accuracy"],
            "change": stats["risk_difference_right_minus_left"],
            "ci95": pct_interval(ci),
            "or_only": stats["left_only"],
            "gift_only": stats["right_only"],
        }
        cross_rows.append(row)
        if model != "pooled":
            cross_chart_rows.append(row)
            bootstrap = cross["cluster_bootstrap"]["estimates"][model]
            cross_box_rows.append(
                boxplot_row(
                    MODEL_LABELS.get(model, model),
                    stats["risk_difference_right_minus_left"],
                    bootstrap["bootstrap_boxplot"],
                    bootstrap["ci95"],
                    clinical_clusters=cross["cluster_bootstrap"]["clusters"],
                    bootstrap_replicates=cross["cluster_bootstrap"]["replicates"],
                    test_annotation=(
                        "GIFT−OpenRouter change: Holm "
                        f"{p_value_text(cross['holm_adjusted_exact_cluster_signflip_p'][model])}"
                    ),
                    signed=True,
                )
            )

    run_labels = {
        "expA_or_310726": "OpenRouter A",
        "expB_or_310726": "OpenRouter B",
        "expA_gift_310726": "GIFT A",
        "expB_gift_310726": "GIFT B",
    }
    run_rows = []
    for key, row in result["run_status"].items():
        run_rows.append(
            {
                "experiment": run_labels[key],
                "planned": row["planned_cells"],
                "logical_calls": row["logical_calls_created"],
                "attempted_calls": row["distinct_calls_attempted"],
                "scored": row["scored_cells"],
                "scored_fraction": row["scored_fraction_of_planned"],
            }
        )

    datasets = {
        "dataset_construction": dataset_rows,
        "analysis_exclusions": exclusion_rows,
        "model_group_classification": classification_rows,
        "summary": summary_rows,
        "condition_a_models": condition_model_rows["A"],
        "condition_a_model_boxplot": condition_model_box_rows["A"],
        "condition_a_pairwise": condition_pair_rows["A"],
        "condition_a_group_contrasts": condition_group_rows["A"],
        "condition_a_group_boxplot": condition_group_box_rows["A"],
        "condition_b_models": condition_model_rows["B"],
        "condition_b_model_boxplot": condition_model_box_rows["B"],
        "condition_b_pairwise": condition_pair_rows["B"],
        "condition_b_group_contrasts": condition_group_rows["B"],
        "condition_b_group_boxplot": condition_group_box_rows["B"],
        "primary_accuracy": accuracy_rows,
        "primary_results": primary_rows,
        "primary_model_change_boxplot": primary_change_box_rows,
        "group_a_vs_b_changes": group_change_rows,
        "group_change_boxplot": group_change_box_rows,
        "group_interactions": group_interaction_rows,
        "group_interaction_boxplot": group_interaction_box_rows,
        "secondary_group_triangulation": secondary_group_rows,
        "sensitivity": sensitivity_rows,
        "cross_arm_chart": cross_chart_rows,
        "cross_arm_boxplot": cross_box_rows,
        "cross_arm": cross_rows,
        "run_status": run_rows,
        "qa_results": qa_rows,
    }
    materialize_report_source(datasets)

    manifest_sources = []
    evidence_sources = []
    source_path = "data/experiment-31-07-26/analysis/report_source.sqlite"
    for args, kwargs in [
        (
            (
                "dataset_construction",
                "Reviewed dataset-construction snapshot",
                source_path,
                "Dataset counts and construction rules reconciled to v3 metadata and the source workbooks.",
            ),
            {
                "query": "SELECT * FROM dataset_construction",
                "table": "dataset_construction",
            },
        ),
        (
            (
                "analysis_exclusions",
                "Reviewed exclusion snapshot",
                source_path,
                "Declared exclusions and their presence in the paired A/B universe.",
            ),
            {
                "query": "SELECT * FROM analysis_exclusions",
                "table": "analysis_exclusions",
            },
        ),
        (
            (
                "model_group_classification",
                "Requested model-group classification",
                source_path,
                "Requester-defined size and model-access labels for the four fixed deployments.",
            ),
            {
                "query": "SELECT * FROM model_group_classification",
                "table": "model_group_classification",
            },
        ),
        (
            (
                "summary",
                "Reviewed headline snapshot",
                source_path,
                "Materialized exactly from the hash-pinned final result bundle.",
            ),
            {"query": "SELECT * FROM summary", "table": "summary"},
        ),
        (
            (
                "condition_a_models",
                "Reviewed Experiment-A model snapshot",
                source_path,
                "Complete-case Experiment-A accuracies and whole-cluster intervals materialized from final_analysis_results.json.",
            ),
            {
                "query": "SELECT * FROM condition_a_models",
                "table": "condition_a_models",
            },
        ),
        (
            (
                "condition_a_model_boxplot",
                "Experiment-A model bootstrap distributions",
                source_path,
                "Five-number summaries of 100,000 whole-clinical-cluster bootstrap accuracy estimates for each model in Experiment A.",
            ),
            {
                "query": "SELECT * FROM condition_a_model_boxplot",
                "table": "condition_a_model_boxplot",
            },
        ),
        (
            (
                "condition_a_pairwise",
                "Reviewed Experiment-A pairwise snapshot",
                source_path,
                "Six Experiment-A cluster-aware pairwise model contrasts and Holm-adjusted p-values.",
            ),
            {
                "query": "SELECT * FROM condition_a_pairwise",
                "table": "condition_a_pairwise",
            },
        ),
        (
            (
                "condition_a_group_contrasts",
                "Reviewed Experiment-A group contrasts",
                source_path,
                "Two requested fixed-model group contrasts on the common Experiment-A population.",
            ),
            {
                "query": "SELECT * FROM condition_a_group_contrasts",
                "table": "condition_a_group_contrasts",
            },
        ),
        (
            (
                "condition_a_group_boxplot",
                "Experiment-A group bootstrap distributions",
                source_path,
                "Five-number summaries of 100,000 whole-clinical-cluster bootstrap accuracy estimates for the requested fixed-model groups in Experiment A.",
            ),
            {
                "query": "SELECT * FROM condition_a_group_boxplot",
                "table": "condition_a_group_boxplot",
            },
        ),
        (
            (
                "condition_b_models",
                "Reviewed Experiment-B model snapshot",
                source_path,
                "Complete-case Experiment-B accuracies and whole-cluster intervals materialized from final_analysis_results.json.",
            ),
            {
                "query": "SELECT * FROM condition_b_models",
                "table": "condition_b_models",
            },
        ),
        (
            (
                "condition_b_model_boxplot",
                "Experiment-B model bootstrap distributions",
                source_path,
                "Five-number summaries of 100,000 whole-clinical-cluster bootstrap accuracy estimates for each model in Experiment B.",
            ),
            {
                "query": "SELECT * FROM condition_b_model_boxplot",
                "table": "condition_b_model_boxplot",
            },
        ),
        (
            (
                "condition_b_pairwise",
                "Reviewed Experiment-B pairwise snapshot",
                source_path,
                "Six Experiment-B cluster-aware pairwise model contrasts and Holm-adjusted p-values.",
            ),
            {
                "query": "SELECT * FROM condition_b_pairwise",
                "table": "condition_b_pairwise",
            },
        ),
        (
            (
                "condition_b_group_contrasts",
                "Reviewed Experiment-B group contrasts",
                source_path,
                "Two requested fixed-model group contrasts on the common Experiment-B population.",
            ),
            {
                "query": "SELECT * FROM condition_b_group_contrasts",
                "table": "condition_b_group_contrasts",
            },
        ),
        (
            (
                "condition_b_group_boxplot",
                "Experiment-B group bootstrap distributions",
                source_path,
                "Five-number summaries of 100,000 whole-clinical-cluster bootstrap accuracy estimates for the requested fixed-model groups in Experiment B.",
            ),
            {
                "query": "SELECT * FROM condition_b_group_boxplot",
                "table": "condition_b_group_boxplot",
            },
        ),
        (
            (
                "primary_accuracy",
                "Reviewed model accuracy snapshot",
                source_path,
                "Model-condition accuracy rows materialized from final_analysis_results.json.",
            ),
            {"query": "SELECT * FROM primary_accuracy", "table": "primary_accuracy"},
        ),
        (
            (
                "primary_results",
                "Reviewed primary results snapshot",
                source_path,
                "Primary paired results and cluster intervals materialized from final_analysis_results.json.",
            ),
            {"query": "SELECT * FROM primary_results", "table": "primary_results"},
        ),
        (
            (
                "primary_model_change_boxplot",
                "Model-specific A-to-B bootstrap distributions",
                source_path,
                "Five-number summaries of 100,000 whole-clinical-cluster bootstrap B-minus-A estimates for each model.",
            ),
            {
                "query": "SELECT * FROM primary_model_change_boxplot",
                "table": "primary_model_change_boxplot",
            },
        ),
        (
            (
                "group_a_vs_b_changes",
                "Reviewed group-specific A/B changes",
                source_path,
                "Four overlapping requested group summaries with whole-cluster intervals and four-test Holm correction.",
            ),
            {
                "query": "SELECT * FROM group_a_vs_b_changes",
                "table": "group_a_vs_b_changes",
            },
        ),
        (
            (
                "group_change_boxplot",
                "Requested-group A-to-B bootstrap distributions",
                source_path,
                "Five-number summaries of 100,000 whole-clinical-cluster bootstrap B-minus-A estimates for the four overlapping requested groups.",
            ),
            {
                "query": "SELECT * FROM group_change_boxplot",
                "table": "group_change_boxplot",
            },
        ),
        (
            (
                "group_interactions",
                "Reviewed group-by-condition interactions",
                source_path,
                "Primary risk-difference interactions for requested size and model-access groupings.",
            ),
            {
                "query": "SELECT * FROM group_interactions",
                "table": "group_interactions",
            },
        ),
        (
            (
                "group_interaction_boxplot",
                "Group-interaction bootstrap distributions",
                source_path,
                "Five-number summaries of primary and secondary whole-clinical-cluster bootstrap difference-in-change estimates.",
            ),
            {
                "query": "SELECT * FROM group_interaction_boxplot",
                "table": "group_interaction_boxplot",
            },
        ),
        (
            (
                "secondary_group_triangulation",
                "Reviewed partial-matching triangulation",
                source_path,
                "Within-large and within-open fixed-model contrasts used to expose group-label confounding.",
            ),
            {
                "query": "SELECT * FROM secondary_group_triangulation",
                "table": "secondary_group_triangulation",
            },
        ),
        (
            (
                "sensitivity",
                "Reviewed sensitivity snapshot",
                source_path,
                "Cleaning sensitivity rows materialized from final_analysis_results.json.",
            ),
            {"query": "SELECT * FROM sensitivity", "table": "sensitivity"},
        ),
        (
            (
                "cross_arm_chart",
                "Reviewed model-level cross-pipeline snapshot",
                source_path,
                "Four model-level partial condition-A pipeline comparisons materialized from final_analysis_results.json.",
            ),
            {"query": "SELECT * FROM cross_arm_chart", "table": "cross_arm_chart"},
        ),
        (
            (
                "cross_arm_boxplot",
                "Partial GIFT/OpenRouter bootstrap distributions",
                source_path,
                "Five-number summaries of 100,000 whole-clinical-cluster bootstrap GIFT-minus-OpenRouter estimates for each model on the observed subset.",
            ),
            {
                "query": "SELECT * FROM cross_arm_boxplot",
                "table": "cross_arm_boxplot",
            },
        ),
        (
            (
                "cross_arm",
                "Reviewed cross-pipeline snapshot",
                source_path,
                "Partial condition-A pipeline comparison materialized from final_analysis_results.json.",
            ),
            {"query": "SELECT * FROM cross_arm", "table": "cross_arm"},
        ),
        (
            (
                "run_status",
                "Reviewed execution-status snapshot",
                source_path,
                "Execution counts materialized from the DB-hash-verified final result bundle.",
            ),
            {"query": "SELECT * FROM run_status", "table": "run_status"},
        ),
        (
            (
                "qa",
                "Independent-QA snapshot",
                source_path,
                f"{len(qa_rows)} unique QA workflow verdicts and their final resolutions.",
            ),
            {"query": "SELECT * FROM qa_results", "table": "qa_results"},
        ),
        (
            (
                "final_results_file",
                "Verified v3.3 result bundle",
                "data/experiment-31-07-26/analysis/final_analysis_results.json",
                "Deterministic model, requested-group, primary, sensitivity, cross-arm, and status results.",
            ),
            {},
        ),
        (
            (
                "audited_secondary_file",
                "Pinned audited secondary results",
                "data/experiment-31-07-26/analysis/audited_secondary_results.json",
                "Machine-readable QA03, QA05, and QA06 secondary estimates with source hashes.",
            ),
            {},
        ),
        (
            (
                "paired_file",
                "Canonical OpenRouter A/B pairs",
                "data/experiment-31-07-26/analysis/paired_clean.json",
                "Scored A/B intersection with model, cluster, and exclusion fields.",
            ),
            {},
        ),
        (
            (
                "cross_file",
                "Canonical partial cross-arm pairs",
                "data/experiment-31-07-26/analysis/cross_arm_A.json",
                "Condition-A GIFT/OpenRouter pairs on all-model completed items.",
            ),
            {},
        ),
        (
            (
                "metadata_file",
                "v3 provenance and exclusions",
                "data/experiment-31-07-26/analysis/dataset_meta.json",
                "Counts, configuration checks, run status, caveats, and SHA-256 hashes.",
            ),
            {},
        ),
        (
            (
                "database_file",
                "Frozen run database",
                "data/experiment-31-07-26/experiment.sqlite",
                "Authoritative experiments, logical calls, attempts, parses, and scores; identity verified against v3 metadata.",
            ),
            {},
        ),
        (
            (
                "qa_file",
                "Independent-QA record",
                "data/experiment-31-07-26/analysis/qa_workflows/qa_summary.json",
                "Machine-readable lineage, quality, statistics, code, claim, and render audit summary.",
            ),
            {},
        ),
        (
            (
                "qa_summary_file",
                "QA resolution narrative",
                "data/experiment-31-07-26/analysis/qa_workflows/QA_SUMMARY.md",
                f"Human-readable summary of all {len(qa_rows)} independent QA workflows and their resolutions.",
            ),
            {},
        ),
        (
            (
                "boxplot_qa_file",
                "Annotated-boxplot QA record",
                "data/experiment-31-07-26/analysis/BOXPLOT_QA.md",
                "v3.3.1 five-number-mark visibility, estimand, data-contract, SQLite, responsive-render, and local verification checks.",
            ),
            {},
        ),
        (
            (
                "report_markdown_file",
                "Canonical report narrative",
                "data/experiment-31-07-26/analysis/REPORT.md",
                "Reader-facing Markdown report from which narrative blocks are built.",
            ),
            {},
        ),
        (
            (
                "security_scan_file",
                "Security-scan status",
                "data/experiment-31-07-26/analysis/SECURITY_SCAN.md",
                "Snyk authentication failure and completed local security-adjacent checks.",
            ),
            {},
        ),
    ]:
        manifest_source, evidence_source = source_entry(*args, **kwargs)
        manifest_sources.append(manifest_source)
        evidence_sources.append(evidence_source)

    cards = [
        {
            "id": "primary_outcome",
            "description": "Cell-weighted paired accuracy on 1,271 verified OpenRouter cells.",
            "dataset": "summary",
            "sourceId": "summary",
            "metrics": [
                {
                    "label": "Condition A accuracy",
                    "field": "a_accuracy",
                    "format": "percent",
                },
                {
                    "label": "Condition B accuracy",
                    "field": "b_accuracy",
                    "format": "percent",
                },
                {
                    "label": "B − A change",
                    "field": "change",
                    "format": "percent",
                    "signed": True,
                },
            ],
        },
        {
            "id": "inference",
            "description": f"Pooled 95% cluster-bootstrap interval {pct_interval(pooled_ci)}.",
            "dataset": "summary",
            "sourceId": "summary",
            "metrics": [
                {
                    "label": "Model-adjusted odds ratio",
                    "field": "model_adjusted_or",
                    "format": "number",
                },
                {
                    "label": "Kish effective clusters",
                    "field": "effective_clusters",
                    "format": "number",
                },
            ],
        },
        {
            "id": "gift_coverage",
            "description": "GIFT A scored coverage; logical-run progress was higher and must not be substituted.",
            "dataset": "summary",
            "sourceId": "summary",
            "metrics": [
                {
                    "label": "GIFT A scored share",
                    "field": "gift_scored_fraction",
                    "format": "percent",
                },
            ],
        },
    ]

    boxplot_key = (
        "Labels show observed estimates. Whisker caps mark the bootstrap minimum and maximum; "
        "the outlined box runs from Q1 to Q3, and its dark divider marks the median. "
        "Hover repeats all five values; 95% intervals and adjusted tests "
        "remain in the adjacent tables."
    )
    charts = [
        {
            "id": "condition_a_accuracy",
            "title": "Experiment A: original-answer accuracy by model",
            "subtitle": "Same 317 items and 200 clinical clusters for every model.",
            "headerMarkdown": "All six pairwise differences survive Holm correction.",
            "type": "bar",
            "dataset": "condition_a_models",
            "sourceId": "condition_a_models",
            "encodings": {
                "x": {"field": "model", "type": "nominal", "label": "Model"},
                "y": {
                    "field": "accuracy",
                    "type": "quantitative",
                    "label": "Accuracy",
                    "format": "percent",
                },
            },
            "yAxisTitle": "Accuracy",
            "valueFormat": "percent",
            "layout": "full",
        },
        {
            "id": "condition_b_accuracy",
            "title": "Experiment B: engineered-meta-answer accuracy by model",
            "subtitle": "Same 317 items and 200 clinical clusters for every model.",
            "headerMarkdown": "GLM versus qwen is the only statistically unresolved pair.",
            "type": "bar",
            "dataset": "condition_b_models",
            "sourceId": "condition_b_models",
            "encodings": {
                "x": {"field": "model", "type": "nominal", "label": "Model"},
                "y": {
                    "field": "accuracy",
                    "type": "quantitative",
                    "label": "Accuracy",
                    "format": "percent",
                },
            },
            "yAxisTitle": "Accuracy",
            "valueFormat": "percent",
            "layout": "full",
        },
        {
            "id": "primary_accuracy",
            "title": "Observed accuracy is lower in condition B for every model",
            "subtitle": "Verified v3 analysis set; exact values are in the adjacent table.",
            "headerMarkdown": "The paired change ranges from **−8.49 to −19.50 percentage points**.",
            "type": "bar",
            "dataset": "primary_accuracy",
            "sourceId": "primary_accuracy",
            "encodings": {
                "x": {"field": "model", "type": "nominal", "label": "Model"},
                "y": {
                    "field": "accuracy",
                    "type": "quantitative",
                    "label": "Accuracy",
                    "format": "percent",
                },
                "color": {
                    "field": "condition",
                    "type": "nominal",
                    "label": "Condition",
                },
            },
            "yAxisTitle": "Accuracy",
            "valueFormat": "percent",
            "layout": "full",
        },
        {
            "id": "sensitivity_change",
            "title": "Every main cleaning specification remains negative",
            "subtitle": "B minus A; requested exclusions make the observed contrast smaller.",
            "type": "bar",
            "dataset": "sensitivity",
            "sourceId": "sensitivity",
            "encodings": {
                "x": {"field": "exclusions", "type": "nominal", "label": "Exclusions"},
                "y": {
                    "field": "change",
                    "type": "quantitative",
                    "label": "B − A",
                    "format": "percent",
                },
            },
            "yAxisTitle": "Accuracy change",
            "valueFormat": "percent",
            "layout": "full",
        },
        {
            "id": "cross_arm_change",
            "title": "The partial cross-pipeline difference reverses sign by model",
            "subtitle": "GIFT minus OpenRouter on 306 cleaned, all-model-completed condition-A items.",
            "headerMarkdown": "Positive for **gemma and glm**; near zero or negative for **qwen and gemini**.",
            "type": "bar",
            "dataset": "cross_arm_chart",
            "sourceId": "cross_arm_chart",
            "encodings": {
                "x": {"field": "model", "type": "nominal", "label": "Model"},
                "y": {
                    "field": "change",
                    "type": "quantitative",
                    "label": "GIFT − OpenRouter",
                    "format": "percent",
                },
            },
            "yAxisTitle": "Accuracy change",
            "valueFormat": "percent",
            "layout": "full",
        },
        boxplot_chart(
            "condition_a_model_boxplot",
            "Experiment A model accuracy: bootstrap distributions",
            "100,000 whole-clinical-cluster resamples of the 317-item common set.",
            "condition_a_model_boxplot",
            (
                f"{boxplot_key} Four-model omnibus "
                f"{p_value_text(within['A']['omnibus']['p_value'])}."
            ),
            "Bootstrap accuracy",
            "How much uncertainty surrounds each model's Experiment-A accuracy?",
        ),
        boxplot_chart(
            "condition_a_group_boxplot",
            "Experiment A requested groups: bootstrap distributions",
            "Equal-model group means on 317 common items; groups overlap across definitions.",
            "condition_a_group_boxplot",
            (
                f"{boxplot_key} Large–small Holm "
                f"{p_value_text(grouped['within_condition']['A']['contrasts']['size']['holm_adjusted_p_across_six_primary_group_tests'])}; "
                "open-model–gemini Holm "
                f"{p_value_text(grouped['within_condition']['A']['contrasts']['openness']['holm_adjusted_p_across_six_primary_group_tests'])}."
            ),
            "Bootstrap accuracy",
            "How do the requested fixed-model groups compare in Experiment A?",
        ),
        boxplot_chart(
            "condition_b_model_boxplot",
            "Experiment B model accuracy: bootstrap distributions",
            "100,000 whole-clinical-cluster resamples of the 317-item common set.",
            "condition_b_model_boxplot",
            (
                f"{boxplot_key} Four-model omnibus "
                f"{p_value_text(within['B']['omnibus']['p_value'])}."
            ),
            "Bootstrap accuracy",
            "How much uncertainty surrounds each model's Experiment-B accuracy?",
        ),
        boxplot_chart(
            "condition_b_group_boxplot",
            "Experiment B requested groups: bootstrap distributions",
            "Equal-model group means on 317 common items; groups overlap across definitions.",
            "condition_b_group_boxplot",
            (
                f"{boxplot_key} Large–small Holm "
                f"{p_value_text(grouped['within_condition']['B']['contrasts']['size']['holm_adjusted_p_across_six_primary_group_tests'])}; "
                "open-model–gemini Holm "
                f"{p_value_text(grouped['within_condition']['B']['contrasts']['openness']['holm_adjusted_p_across_six_primary_group_tests'])}."
            ),
            "Bootstrap accuracy",
            "How do the requested fixed-model groups compare in Experiment B?",
        ),
        boxplot_chart(
            "primary_model_change_boxplot",
            "A-to-B accuracy change by model: bootstrap distributions",
            "B minus A on all available cleaned pairs for each model.",
            "primary_model_change_boxplot",
            f"{boxplot_key} Every model-specific change remains negative after Holm correction.",
            "Bootstrap B − A change",
            "How much uncertainty surrounds each model's paired A-to-B change?",
        ),
        boxplot_chart(
            "group_change_boxplot",
            "A-to-B accuracy change by requested group",
            "Equal-model group means on the 317-item common set.",
            "group_change_boxplot",
            f"{boxplot_key} All four group-specific declines survive their four-test Holm family.",
            "Bootstrap B − A change",
            "How much uncertainty surrounds each requested group's A-to-B change?",
        ),
        boxplot_chart(
            "group_interaction_boxplot",
            "Differences in A-to-B changes: primary and secondary contrasts",
            "Positive values mean the first named side lost less accuracy from A to B.",
            "group_interaction_boxplot",
            (
                f"{boxplot_key} The large–small interaction spans zero; the open–gemini "
                "contrast remains a fixed-panel, singleton-proprietary comparison."
            ),
            "Bootstrap difference in changes",
            "Which requested group-change contrasts are resolved on the risk-difference scale?",
        ),
        boxplot_chart(
            "cross_arm_boxplot",
            "Partial GIFT versus OpenRouter change by model",
            "GIFT minus OpenRouter on 306 cleaned condition-A items in 178 clinical clusters.",
            "cross_arm_boxplot",
            (
                f"{boxplot_key} Signs reverse by model, so the pooled pipeline estimate is not "
                "a sufficient product conclusion."
            ),
            "Bootstrap GIFT − OpenRouter change",
            "How much uncertainty surrounds each observed-subset pipeline difference?",
        ),
    ]

    tables = [
        {
            "id": "dataset_construction",
            "title": "Dataset construction",
            "dataset": "dataset_construction",
            "sourceId": "dataset_construction",
            "columns": [
                {"field": "dataset", "label": "Dataset", "type": "text"},
                {"field": "items", "label": "Items", "format": "number"},
                {"field": "construction", "label": "Construction", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "analysis_exclusions",
            "title": "Analysis exclusions",
            "dataset": "analysis_exclusions",
            "sourceId": "analysis_exclusions",
            "columns": [
                {"field": "rule", "label": "Rule", "type": "text"},
                {
                    "field": "declared_globally",
                    "label": "Declared globally",
                    "type": "text",
                },
                {"field": "present_in_ab", "label": "Present in A/B", "type": "text"},
                {"field": "basis", "label": "Basis", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "model_group_classification",
            "title": "Requester-defined model groups",
            "subtitle": "Four fixed deployments; the design has no small proprietary endpoint.",
            "dataset": "model_group_classification",
            "sourceId": "model_group_classification",
            "columns": [
                {"field": "model", "label": "Model", "type": "text"},
                {
                    "field": "size_group",
                    "label": "Requested size group",
                    "type": "text",
                },
                {
                    "field": "access_group",
                    "label": "Requested access group",
                    "type": "text",
                },
            ],
            "layout": "full",
        },
        {
            "id": "condition_a_models",
            "title": "Experiment A model accuracy",
            "subtitle": "Complete-case comparison; intervals resample whole clinical clusters.",
            "dataset": "condition_a_models",
            "sourceId": "condition_a_models",
            "columns": [
                {"field": "model", "label": "Model", "type": "text"},
                {"field": "correct", "label": "Correct", "format": "number"},
                {"field": "n", "label": "n", "format": "number"},
                {"field": "accuracy", "label": "Accuracy", "format": "percent"},
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "condition_a_pairwise",
            "title": "Experiment A pairwise model tests",
            "subtitle": "First model minus second; exact whole-cluster sign flips with Holm correction across six tests.",
            "dataset": "condition_a_pairwise",
            "sourceId": "condition_a_pairwise",
            "columns": [
                {"field": "comparison", "label": "Comparison", "type": "text"},
                {"field": "paired_n", "label": "Paired n", "format": "number"},
                {
                    "field": "difference",
                    "label": "Accuracy difference",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
                {
                    "field": "exact_cluster_p",
                    "label": "Exact cluster p",
                    "type": "text",
                },
                {"field": "holm_p", "label": "Holm p", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "condition_a_group_contrasts",
            "title": "Experiment A requested group contrasts",
            "subtitle": "Equal model weighting on 317 common items; Holm correction spans six primary group tests.",
            "dataset": "condition_a_group_contrasts",
            "sourceId": "condition_a_group_contrasts",
            "columns": [
                {"field": "grouping", "label": "Grouping", "type": "text"},
                {"field": "comparison", "label": "Direction", "type": "text"},
                {
                    "field": "first_accuracy",
                    "label": "First group",
                    "format": "percent",
                },
                {
                    "field": "second_accuracy",
                    "label": "Second group",
                    "format": "percent",
                },
                {
                    "field": "difference",
                    "label": "Accuracy difference",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
                {
                    "field": "exact_cluster_p",
                    "label": "Exact cluster p",
                    "type": "text",
                },
                {"field": "holm_p", "label": "Holm p", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "condition_b_models",
            "title": "Experiment B model accuracy",
            "subtitle": "Complete-case comparison; intervals resample whole clinical clusters.",
            "dataset": "condition_b_models",
            "sourceId": "condition_b_models",
            "columns": [
                {"field": "model", "label": "Model", "type": "text"},
                {"field": "correct", "label": "Correct", "format": "number"},
                {"field": "n", "label": "n", "format": "number"},
                {"field": "accuracy", "label": "Accuracy", "format": "percent"},
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "condition_b_pairwise",
            "title": "Experiment B pairwise model tests",
            "subtitle": "First model minus second; exact whole-cluster sign flips with Holm correction across six tests.",
            "dataset": "condition_b_pairwise",
            "sourceId": "condition_b_pairwise",
            "columns": [
                {"field": "comparison", "label": "Comparison", "type": "text"},
                {"field": "paired_n", "label": "Paired n", "format": "number"},
                {
                    "field": "difference",
                    "label": "Accuracy difference",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
                {
                    "field": "exact_cluster_p",
                    "label": "Exact cluster p",
                    "type": "text",
                },
                {"field": "holm_p", "label": "Holm p", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "condition_b_group_contrasts",
            "title": "Experiment B requested group contrasts",
            "subtitle": "Equal model weighting on 317 common items; Holm correction spans six primary group tests.",
            "dataset": "condition_b_group_contrasts",
            "sourceId": "condition_b_group_contrasts",
            "columns": [
                {"field": "grouping", "label": "Grouping", "type": "text"},
                {"field": "comparison", "label": "Direction", "type": "text"},
                {
                    "field": "first_accuracy",
                    "label": "First group",
                    "format": "percent",
                },
                {
                    "field": "second_accuracy",
                    "label": "Second group",
                    "format": "percent",
                },
                {
                    "field": "difference",
                    "label": "Accuracy difference",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
                {
                    "field": "exact_cluster_p",
                    "label": "Exact cluster p",
                    "type": "text",
                },
                {"field": "holm_p", "label": "Holm p", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "primary_results",
            "title": "Paired Experiment-A versus Experiment-B results",
            "subtitle": "Risk differences use B minus A; CIs resample whole clinical clusters.",
            "dataset": "primary_results",
            "sourceId": "primary_results",
            "columns": [
                {"field": "model", "label": "Model", "type": "text"},
                {"field": "n", "label": "Paired n", "format": "number"},
                {"field": "a_accuracy", "label": "A accuracy", "format": "percent"},
                {"field": "b_accuracy", "label": "B accuracy", "format": "percent"},
                {
                    "field": "change",
                    "label": "B − A",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
                {
                    "field": "exact_cluster_p",
                    "label": "Exact cluster p",
                    "type": "text",
                },
                {"field": "holm_cluster_p", "label": "Holm p", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "group_a_vs_b_changes",
            "title": "A-to-B change within requested model groups",
            "subtitle": "Overlapping fixed-model summaries on 317 common items; Holm correction spans four group declines.",
            "dataset": "group_a_vs_b_changes",
            "sourceId": "group_a_vs_b_changes",
            "columns": [
                {"field": "grouping", "label": "Grouping", "type": "text"},
                {"field": "group", "label": "Group", "type": "text"},
                {"field": "model_count", "label": "Models", "format": "number"},
                {"field": "a_accuracy", "label": "A accuracy", "format": "percent"},
                {"field": "b_accuracy", "label": "B accuracy", "format": "percent"},
                {
                    "field": "change",
                    "label": "B − A",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
                {
                    "field": "exact_cluster_p",
                    "label": "Exact cluster p",
                    "type": "text",
                },
                {"field": "holm_p", "label": "Holm p", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "group_interactions",
            "title": "Do the requested groups change differently from A to B?",
            "subtitle": "Difference-in-differences on the percentage-point scale; Holm correction spans six primary group tests.",
            "dataset": "group_interactions",
            "sourceId": "group_interactions",
            "columns": [
                {"field": "grouping", "label": "Grouping", "type": "text"},
                {
                    "field": "comparison",
                    "label": "Interaction direction",
                    "type": "text",
                },
                {
                    "field": "difference_in_changes",
                    "label": "Difference in B − A changes",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "Cluster-bootstrap 95% CI", "type": "text"},
                {
                    "field": "exact_cluster_p",
                    "label": "Exact cluster p",
                    "type": "text",
                },
                {"field": "holm_p", "label": "Holm p", "type": "text"},
                {"field": "conclusion", "label": "Conclusion", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "secondary_group_triangulation",
            "title": "Triangulation inside the incomplete size × access design",
            "subtitle": "Within-large and within-open contrasts; Holm correction spans six secondary tests.",
            "dataset": "secondary_group_triangulation",
            "sourceId": "secondary_group_triangulation",
            "columns": [
                {"field": "perspective", "label": "Perspective", "type": "text"},
                {
                    "field": "a_difference",
                    "label": "Experiment-A gap",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "a_holm_p", "label": "A Holm p", "type": "text"},
                {
                    "field": "b_difference",
                    "label": "Experiment-B gap",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "b_holm_p", "label": "B Holm p", "type": "text"},
                {
                    "field": "difference_in_changes",
                    "label": "Difference in changes",
                    "format": "percent",
                    "movement": True,
                },
                {
                    "field": "interaction_ci95",
                    "label": "Interaction 95% CI",
                    "type": "text",
                },
                {
                    "field": "interaction_holm_p",
                    "label": "Interaction Holm p",
                    "type": "text",
                },
            ],
            "layout": "full",
        },
        {
            "id": "sensitivity_results",
            "title": "Cleaning sensitivity",
            "dataset": "sensitivity",
            "sourceId": "sensitivity",
            "columns": [
                {"field": "exclusions", "label": "Exclusions", "type": "text"},
                {"field": "items", "label": "Items", "format": "number"},
                {"field": "cells", "label": "Cells", "format": "number"},
                {
                    "field": "change",
                    "label": "B − A",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "95% CI", "type": "text"},
            ],
            "layout": "full",
        },
        {
            "id": "cross_results",
            "title": "Partial condition-A cross-pipeline detail",
            "subtitle": "Not a full-target pipeline estimate; GIFT B was never run.",
            "dataset": "cross_arm",
            "sourceId": "cross_arm",
            "columns": [
                {"field": "model", "label": "Model", "type": "text"},
                {
                    "field": "openrouter_accuracy",
                    "label": "OpenRouter",
                    "format": "percent",
                },
                {"field": "gift_accuracy", "label": "GIFT", "format": "percent"},
                {
                    "field": "change",
                    "label": "GIFT − OR",
                    "format": "percent",
                    "movement": True,
                },
                {"field": "ci95", "label": "95% CI", "type": "text"},
                {"field": "or_only", "label": "OR only", "format": "number"},
                {"field": "gift_only", "label": "GIFT only", "format": "number"},
            ],
            "layout": "full",
        },
        {
            "id": "run_status",
            "title": "Execution status",
            "dataset": "run_status",
            "sourceId": "run_status",
            "columns": [
                {"field": "experiment", "label": "Experiment", "type": "text"},
                {"field": "planned", "label": "Planned", "format": "number"},
                {
                    "field": "logical_calls",
                    "label": "Logical calls",
                    "format": "number",
                },
                {
                    "field": "attempted_calls",
                    "label": "Attempted calls",
                    "format": "number",
                },
                {"field": "scored", "label": "Scored", "format": "number"},
                {
                    "field": "scored_fraction",
                    "label": "Scored share",
                    "format": "percent",
                },
            ],
            "layout": "full",
        },
    ]
    if qa_rows:
        tables.append(
            {
                "id": "qa_results",
                "title": f"{len(qa_rows)} independent QA workflows",
                "dataset": "qa_results",
                "sourceId": "qa",
                "columns": [
                    {"field": "workflow", "label": "Workflow", "type": "text"},
                    {"field": "scope", "label": "Scope", "type": "text"},
                    {"field": "verdict", "label": "Initial verdict", "type": "text"},
                    {
                        "field": "final_status",
                        "label": "Final status",
                        "type": "text",
                    },
                    {"field": "resolution", "label": "Resolution", "type": "text"},
                ],
                "layout": "full",
            }
        )

    evidence_source_by_id = {source["id"]: source for source in evidence_sources}
    for widget in [*cards, *charts, *tables]:
        source_id = widget.pop("sourceId")
        widget["source"] = dict(evidence_source_by_id[source_id])

    insertions = {
        "1": [
            {
                "id": "model_group_classification_block",
                "type": "table",
                "tableId": "model_group_classification",
                "layout": "full",
            },
            {
                "id": "dataset_table_block",
                "type": "table",
                "tableId": "dataset_construction",
                "layout": "full",
            },
            {
                "id": "exclusion_table_block",
                "type": "table",
                "tableId": "analysis_exclusions",
                "layout": "full",
            },
        ],
        "2": [
            {
                "id": "condition_a_chart",
                "type": "chart",
                "chartId": "condition_a_accuracy",
                "layout": "full",
            },
            {
                "id": "condition_a_model_boxplot_block",
                "type": "chart",
                "chartId": "condition_a_model_boxplot",
                "layout": "full",
            },
            {
                "id": "condition_a_model_table",
                "type": "table",
                "tableId": "condition_a_models",
                "layout": "full",
            },
            {
                "id": "condition_a_pairwise_table",
                "type": "table",
                "tableId": "condition_a_pairwise",
                "layout": "full",
            },
            {
                "id": "condition_a_group_boxplot_block",
                "type": "chart",
                "chartId": "condition_a_group_boxplot",
                "layout": "full",
            },
            {
                "id": "condition_a_group_table",
                "type": "table",
                "tableId": "condition_a_group_contrasts",
                "layout": "full",
            },
        ],
        "3": [
            {
                "id": "condition_b_chart",
                "type": "chart",
                "chartId": "condition_b_accuracy",
                "layout": "full",
            },
            {
                "id": "condition_b_model_boxplot_block",
                "type": "chart",
                "chartId": "condition_b_model_boxplot",
                "layout": "full",
            },
            {
                "id": "condition_b_model_table",
                "type": "table",
                "tableId": "condition_b_models",
                "layout": "full",
            },
            {
                "id": "condition_b_pairwise_table",
                "type": "table",
                "tableId": "condition_b_pairwise",
                "layout": "full",
            },
            {
                "id": "condition_b_group_boxplot_block",
                "type": "chart",
                "chartId": "condition_b_group_boxplot",
                "layout": "full",
            },
            {
                "id": "condition_b_group_table",
                "type": "table",
                "tableId": "condition_b_group_contrasts",
                "layout": "full",
            },
        ],
        "4": [
            {
                "id": "primary_chart",
                "type": "chart",
                "chartId": "primary_accuracy",
                "layout": "full",
            },
            {
                "id": "primary_model_change_boxplot_block",
                "type": "chart",
                "chartId": "primary_model_change_boxplot",
                "layout": "full",
            },
            {
                "id": "primary_table",
                "type": "table",
                "tableId": "primary_results",
                "layout": "full",
            },
            {
                "id": "group_change_boxplot_block",
                "type": "chart",
                "chartId": "group_change_boxplot",
                "layout": "full",
            },
            {
                "id": "group_change_table",
                "type": "table",
                "tableId": "group_a_vs_b_changes",
                "layout": "full",
            },
            {
                "id": "group_interaction_boxplot_block",
                "type": "chart",
                "chartId": "group_interaction_boxplot",
                "layout": "full",
            },
            {
                "id": "group_interaction_table",
                "type": "table",
                "tableId": "group_interactions",
                "layout": "full",
            },
            {
                "id": "secondary_group_table",
                "type": "table",
                "tableId": "secondary_group_triangulation",
                "layout": "full",
            },
        ],
        "6": [
            {
                "id": "sensitivity_chart_block",
                "type": "chart",
                "chartId": "sensitivity_change",
                "layout": "full",
            },
            {
                "id": "sensitivity_table_block",
                "type": "table",
                "tableId": "sensitivity_results",
                "layout": "full",
            },
        ],
        "8": [
            {
                "id": "cross_chart_block",
                "type": "chart",
                "chartId": "cross_arm_change",
                "layout": "full",
            },
            {
                "id": "cross_boxplot_block",
                "type": "chart",
                "chartId": "cross_arm_boxplot",
                "layout": "full",
            },
            {
                "id": "cross_table_block",
                "type": "table",
                "tableId": "cross_results",
                "layout": "full",
            },
        ],
        "9": [
            {
                "id": "run_table_block",
                "type": "table",
                "tableId": "run_status",
                "layout": "full",
            },
        ],
    }
    blocks = []
    found_insertions = set()
    for block_id, body in split_markdown(strip_pipe_tables(report_text)):
        evidence_body, clinical_body = split_clinical_interpretation(body)
        blocks.append(
            {"id": f"text_{block_id}", "type": "markdown", "body": evidence_body}
        )
        if block_id == "executive_conclusion":
            blocks.append(
                {
                    "id": "metrics",
                    "type": "metric-strip",
                    "cardIds": ["primary_outcome", "inference", "gift_coverage"],
                }
            )
        section_number = block_id.split("_", 1)[0]
        if section_number in insertions:
            blocks.extend(insertions[section_number])
            found_insertions.add(section_number)
        if clinical_body is not None:
            blocks.append(
                {
                    "id": f"text_{block_id}_clinical",
                    "type": "markdown",
                    "body": clinical_body,
                }
            )
    missing_insertions = set(insertions) - found_insertions
    if missing_insertions:
        raise RuntimeError(
            f"required report sections not found: {sorted(missing_insertions)}"
        )
    blocks.append(
        {
            "id": "qa_table_block",
            "type": "table",
            "tableId": "qa_results",
            "layout": "full",
        }
    )

    reachable_cards = {
        card_id
        for block in blocks
        if block["type"] == "metric-strip"
        for card_id in block["cardIds"]
    }
    reachable_charts = {
        block["chartId"] for block in blocks if block["type"] == "chart"
    }
    reachable_tables = {
        block["tableId"] for block in blocks if block["type"] == "table"
    }
    if reachable_cards != {card["id"] for card in cards}:
        raise RuntimeError("one or more metric cards are orphaned")
    if reachable_charts != {chart["id"] for chart in charts}:
        raise RuntimeError("one or more charts are orphaned")
    if reachable_tables != {table["id"] for table in tables}:
        raise RuntimeError("one or more tables are orphaned")

    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": "Correct-option substitution benchmark: verified final analysis",
            "description": f"v3.3.1 presentation repair on the approved v3.3 fixed-model analysis, with fully marked bootstrap boxplots, OpenRouter A/B analysis, partial GIFT condition-A evidence, and {len(qa_rows)}-workflow QA.",
            "generatedAt": GENERATED_AT,
            "cards": cards,
            "charts": charts,
            "tables": tables,
            "sources": manifest_sources,
            "blocks": blocks,
        },
        "snapshot": {
            "version": 1,
            "generatedAt": GENERATED_AT,
            "status": "partial" if qa_not_passed else "ready",
            "datasets": datasets,
        },
        "sources": evidence_sources,
        "package_info": {
            "originUrl": "artifact://gift-correct-option-substitution-v3-3",
            "controls": {"edit": False, "refresh": False},
            "analysisVersion": result["analysis_version"],
            "metadataVersion": meta["export_version"],
            "reportSourceSha256": sha256(SOURCE_DB),
            "builderSha256": sha256(Path(__file__).resolve()),
        },
    }
    atomic_json_write(OUT, artifact)
    print(OUT)


if __name__ == "__main__":
    main()
