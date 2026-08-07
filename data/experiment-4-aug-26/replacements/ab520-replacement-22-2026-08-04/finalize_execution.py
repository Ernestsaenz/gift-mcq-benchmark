#!/usr/bin/env python3
"""Finalize the QA-approved replacement cohort and adjusted 6,000-cell result set."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import unicodedata
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CANONICAL = REPO / "data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04"
CANONICAL_EXPORTS = CANONICAL / "exports"
EXPORTS = HERE / "exports"
MANIFESTS = HERE / "manifests"
PRESENTATION = HERE / "presentation"
RUNS = HERE / "runs"
DB = RUNS / "ab520-replacement22-2026-08-05.sqlite"
POST_DB = MANIFESTS / "ab520-replacement22.post-execution.sqlite"
LEDGER = MANIFESTS / "frozen-replacement-cell-ledger.csv"
INVOCATIONS = MANIFESTS / "invocations"
CANONICAL_CELLS = CANONICAL_EXPORTS / "benchmark-6000-cell-results.csv"
CANONICAL_CATALOG = CANONICAL_EXPORTS / "benchmark-520-question-catalog.csv"
CELLS_OUT = EXPORTS / "benchmark-6000-cell-results-adjusted.csv"
CATALOG_OUT = EXPORTS / "benchmark-514-active-question-catalog-adjusted.csv"
PRIMARY_CATALOG_OUT = EXPORTS / "benchmark-500-question-catalog-adjusted.csv"
RESERVE_STATUS_OUT = EXPORTS / "reserve-20-historical-status-adjusted.csv"
PROVIDER_OUT = EXPORTS / "provider-condition-summary-adjusted.csv"
MODEL_OUT = EXPORTS / "model-condition-summary-adjusted.csv"
PAIRED_OUT = EXPORTS / "openrouter-paired-ab-results-adjusted.csv"
UNRESOLVED_OUT = EXPORTS / "unresolved-cells-adjusted.csv"
MAP_OUT = EXPORTS / "replacement-question-map.csv"
RECOVERED_OUT = EXPORTS / "recovered-first-attempt-failures.csv"
FINAL_MANIFEST = MANIFESTS / "execution-manifest-final.json"
OUTPUT_CHECKSUMS = MANIFESTS / "output-checksums.sha256"
ALL_CHECKSUMS = MANIFESTS / "all-files.sha256"
ROOT_CHECKSUMS = HERE / "checksums.sha256"
FINAL_REPORT = HERE / "FINAL_EXECUTION_REPORT.md"

RAW_FIELDS = (
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_letter",
    "correct_option_text",
)
MODELS = (
    "google/gemini-3.6-flash",
    "google/gemma-4-26b-a4b-it",
    "qwen/qwen3.6-35b-a3b",
    "z-ai/glm-5.2",
)
LINEAGE_FIELDS = (
    "replacement_id",
    "replaces_question_id",
    "candidate_id",
    "failure_group",
    "record_role",
    "replacement_manifest_sha256",
    "replacement_cell_ledger_sha256",
)
ARMS = ("openrouter_A", "openrouter_B", "tailscale_A")
EXPERIMENT_BY_ARM = {
    "openrouter_A": "ab520_replacement22_or_A_20260804",
    "openrouter_B": "ab520_replacement22_or_B_20260804",
    "tailscale_A": "ab520_replacement22_ts_A_20260804",
}
DATASET_BY_CONDITION = {
    "A": "aug26_replacement22_A",
    "B": "aug26_replacement22_B",
}
INPUT_BY_CONDITION = {
    "A": HERE / "replacement-22-A.csv",
    "B": HERE / "replacement-22-B.csv",
}
WORKBOOK_BY_CONDITION = {
    "A": HERE / "inputs/replacement-22-A.xlsx",
    "B": HERE / "inputs/replacement-22-B.xlsx",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def csv_fields(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle).fieldnames or [])


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    fields: list[str] | None = None,
) -> None:
    if fields is None:
        if not rows:
            raise AssertionError(f"Fields are required for an empty CSV: {path}")
        fields = list(rows[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str | None) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def lp_hash(values: list[Any]) -> str:
    payload = bytearray()
    for value in values:
        raw = ("" if value is None else str(value)).encode("utf-8")
        payload.extend(len(raw).to_bytes(8, "big"))
        payload.extend(raw)
    return hashlib.sha256(payload).hexdigest()


def raw_hash(row: dict[str, Any]) -> str:
    return lp_hash([row[field] for field in RAW_FIELDS])


def normalized_stem(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    normalized = re.sub(r"\s+", " ", normalized)
    return re.sub(r"[\s\.:;,]+$", "", normalized)


def relative(path: Path) -> str:
    return str(path.relative_to(REPO))


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_effective_model(response_json: str | None, response_body: str | None) -> str:
    for candidate in (response_json, response_body):
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if isinstance(payload.get("model"), str):
            return payload["model"]
        nested = payload.get("data")
        if isinstance(nested, dict) and isinstance(nested.get("model"), str):
            return nested["model"]
    return ""


def user_content_length(request_json: str | None) -> int | str:
    if not request_json:
        return ""
    try:
        payload = json.loads(request_json)
    except json.JSONDecodeError:
        return ""
    messages = payload.get("messages") if isinstance(payload, dict) else None
    if not isinstance(messages, list):
        return ""
    content = [
        message.get("content")
        for message in messages
        if isinstance(message, dict)
        and message.get("role") == "user"
        and isinstance(message.get("content"), str)
    ]
    return sum(len(value) for value in content) if content else ""


def one(rows: list[sqlite3.Row], label: str) -> sqlite3.Row:
    if len(rows) != 1:
        raise AssertionError(f"Expected one {label}; found {len(rows)}")
    return rows[0]


def validate_source_pair(a: dict[str, str], b: dict[str, str]) -> None:
    letter = a["correct_letter"].lower()
    assert b["correct_letter"].lower() == letter
    changed = [field for field in RAW_FIELDS if a[field] != b[field]]
    assert changed == [f"option_{letter}", "correct_option_text"], changed
    assert b[f"option_{letter}"] == "Ninguna de las respuestas anteriores es correcta."
    assert b["correct_option_text"] == "Ninguna de las respuestas anteriores es correcta."


def fetch_replacement_result(
    connection: sqlite3.Connection,
    ledger_row: dict[str, str],
    source: dict[str, str],
) -> dict[str, Any]:
    logical = one(
        connection.execute(
            """
            SELECT lc.*, e.name AS experiment_name, d.name AS dataset_name,
                   q.question_id AS replacement_id, q.question_text, q.option_a,
                   q.option_b, q.option_c, q.option_d, q.correct_letter,
                   q.correct_option_text
            FROM logical_calls lc
            JOIN experiments e ON e.id = lc.experiment_id
            JOIN datasets d ON d.id = e.dataset_id
            JOIN questions q ON q.id = lc.question_id
            WHERE e.name = ? AND q.question_id = ? AND lc.provider = ?
              AND lc.model = ? AND lc.run_index = ?
            """,
            (
                ledger_row["experiment"],
                ledger_row["replacement_id"],
                ledger_row["provider"],
                ledger_row["model"],
                int(ledger_row["run_index"]),
            ),
        ).fetchall(),
        f"logical call for {ledger_row['cell_key']}",
    )
    assert logical["experiment_name"] == EXPERIMENT_BY_ARM[ledger_row["arm"]]
    assert logical["dataset_name"] == DATASET_BY_CONDITION[ledger_row["condition"]]
    assert logical["prompt_version"] == ledger_row["prompt_version"] == "mcq_es_v4"
    assert logical["system_prompt_sha256"] == ledger_row["system_prompt_sha256"]
    assert logical["user_prompt_sha256"] == ledger_row["user_prompt_sha256"]
    for field in RAW_FIELDS:
        assert str(logical[field]) == str(source[field]), (
            ledger_row["cell_key"],
            field,
        )
    assert raw_hash(source) == ledger_row["input_fields_sha256"]

    attempts = connection.execute(
        "SELECT * FROM provider_attempts WHERE logical_call_id = ? ORDER BY id",
        (logical["id"],),
    ).fetchall()
    assert attempts
    assert len({attempt["request_sha256"] for attempt in attempts}) == 1
    for attempt in attempts:
        assert attempt["system_prompt_sha256"] == ledger_row["system_prompt_sha256"]
        assert attempt["user_prompt_sha256"] == ledger_row["user_prompt_sha256"]
        if ledger_row["provider"] == "tailscale_medical_rag":
            assert attempt["prompt_id"] == 13
        else:
            assert attempt["prompt_id"] is None

    parsed_rows = connection.execute(
        "SELECT * FROM parsed_answers WHERE logical_call_id = ? ORDER BY id",
        (logical["id"],),
    ).fetchall()
    parsed_by_attempt = {
        int(row["provider_attempt_id"]): row
        for row in parsed_rows
        if row["provider_attempt_id"] is not None
    }
    score = one(
        connection.execute(
            """
            SELECT s.*, p.parse_status, p.parse_method, p.selected_letter,
                   p.selected_option_text, p.provider_attempt_id
            FROM scores s
            JOIN parsed_answers p ON p.id = s.parsed_answer_id
            WHERE s.logical_call_id = ?
            """,
            (logical["id"],),
        ).fetchall(),
        f"score for {ledger_row['cell_key']}",
    )
    score_attempt = one(
        [attempt for attempt in attempts if attempt["id"] == score["provider_attempt_id"]],
        f"score attempt for {ledger_row['cell_key']}",
    )
    history = []
    for attempt in attempts:
        parsed = parsed_by_attempt.get(int(attempt["id"]))
        history.append(
            {
                "attempt_index": attempt["attempt_index"],
                "status_code": attempt["status_code"],
                "latency_ms": attempt["latency_ms"],
                "finish_reason": attempt["finish_reason"],
                "error_type": attempt["error_type"],
                "parse_status": parsed["parse_status"] if parsed else None,
                "selected_letter": parsed["selected_letter"] if parsed else None,
            }
        )
    assert score["parse_status"] == "ok"
    return {
        "logical_call_id": logical["id"],
        "prompt_version": logical["prompt_version"],
        "attempt_count": len(attempts),
        "attempt_history_json": json.dumps(
            history, ensure_ascii=False, separators=(",", ":")
        ),
        "exact_input_match_db": "TRUE",
        "final_execution_status": "scored",
        "selected_letter": score["selected_letter"],
        "selected_option_text": score["selected_option_text"],
        "parse_status": score["parse_status"],
        "parse_method": score["parse_method"],
        "strict_correct": score["strict_correct"],
        "lenient_correct": score["lenient_correct"],
        "letter_correct": score["letter_correct"],
        "text_correct": score["text_correct"],
        "answer_text_matches_provided": score["answer_text_matches_provided"],
        "latest_attempt_index": score_attempt["attempt_index"],
        "latest_status_code": score_attempt["status_code"],
        "latest_latency_ms": score_attempt["latency_ms"],
        "latest_finish_reason": score_attempt["finish_reason"],
        "latest_error_type": score_attempt["error_type"] or "",
        "request_sha256": score_attempt["request_sha256"],
        "response_sha256": sha256_text(score_attempt["response_body"]),
        "effective_model": extract_effective_model(
            score_attempt["response_json"], score_attempt["response_body"]
        ),
        "prompt_tokens": score_attempt["prompt_tokens"] or "",
        "completion_tokens": score_attempt["completion_tokens"] or "",
        "total_tokens": score_attempt["total_tokens"] or "",
        "request_user_content_char_count": user_content_length(
            score_attempt["request_json"]
        ),
        "failure_class": "",
        "history": history,
    }


def build_adjusted_cells(
    generated_at: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, str]],
]:
    del generated_at
    canonical_rows = read_csv(CANONICAL_CELLS)
    canonical_fields = csv_fields(CANONICAL_CELLS)
    assert len(canonical_rows) == len({row["cell_key"] for row in canonical_rows}) == 6000

    replacement_manifest = read_json(HERE / "replacement-manifest.json")
    replacements = replacement_manifest["replacements"]
    assert len(replacements) == 22
    old_to_new = {
        row["replaces_question_id"]: row["replacement_id"] for row in replacements
    }
    replacement_by_id = {row["replacement_id"]: row for row in replacements}
    assert len(old_to_new) == len(replacement_by_id) == 22

    removed = [row for row in canonical_rows if row["question_id"] in old_to_new]
    retained = [row for row in canonical_rows if row["question_id"] not in old_to_new]
    assert len(removed) == 264
    assert Counter(row["question_id"] for row in removed) == Counter(
        {question_id: 12 for question_id in old_to_new}
    )
    assert len(retained) == 5736
    assert all(row["final_execution_status"] == "scored" for row in retained)
    assert all(row["exact_input_match_db"] == "TRUE" for row in retained)

    inputs = {
        condition: {row["question_id"]: row for row in read_csv(path)}
        for condition, path in INPUT_BY_CONDITION.items()
    }
    assert all(len(rows) == 22 for rows in inputs.values())
    for replacement_id in replacement_by_id:
        validate_source_pair(inputs["A"][replacement_id], inputs["B"][replacement_id])

    ledger_rows = read_csv(LEDGER)
    assert len(ledger_rows) == len({row["cell_key"] for row in ledger_rows}) == 264
    assert Counter(row["arm"] for row in ledger_rows) == Counter(
        {"openrouter_A": 88, "openrouter_B": 88, "tailscale_A": 88}
    )
    assert {row["status"] for row in ledger_rows} <= {"READY_NOT_RUN", "SCORED"}

    connection = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    replacement_results: dict[tuple[str, str, str], dict[str, Any]] = {}
    ledger_by_key = {row["cell_key"]: row for row in ledger_rows}
    for ledger_row in ledger_rows:
        source = inputs[ledger_row["condition"]][ledger_row["replacement_id"]]
        assert source["candidate_id"] == ledger_row["candidate_id"]
        assert source["source_key"] == ledger_row["source_key"]
        result = fetch_replacement_result(connection, ledger_row, source)
        key = (ledger_row["arm"], ledger_row["replacement_id"], ledger_row["model"])
        assert key not in replacement_results
        replacement_results[key] = result
    connection.close()
    assert len(replacement_results) == 264

    row_number = {
        condition: {
            row["question_id"]: index
            for index, row in enumerate(read_csv(INPUT_BY_CONDITION[condition]), start=2)
        }
        for condition in ("A", "B")
    }
    workbook_hash = {
        condition: sha256_file(path) for condition, path in WORKBOOK_BY_CONDITION.items()
    }
    adjusted: list[dict[str, Any]] = []
    recovered: list[dict[str, Any]] = []
    replacement_manifest_sha256 = sha256_file(HERE / "replacement-manifest.json")
    replacement_ledger_sha256 = sha256_file(LEDGER)
    for canonical in canonical_rows:
        old_id = canonical["question_id"]
        if old_id not in old_to_new:
            adjusted.append(
                {
                    **canonical,
                    "replacement_id": "",
                    "replaces_question_id": "",
                    "candidate_id": "",
                    "failure_group": "",
                    "record_role": "retained",
                    "replacement_manifest_sha256": "",
                    "replacement_cell_ledger_sha256": "",
                }
            )
            continue
        replacement_id = old_to_new[old_id]
        key = (canonical["arm"], replacement_id, canonical["model"])
        result = replacement_results[key]
        manifest_row = replacement_by_id[replacement_id]
        condition = canonical["condition"]
        source = inputs[condition][replacement_id]
        ledger_key = (
            f"{canonical['provider']}|{condition}|{replacement_id}|"
            f"{source['source_key']}|{canonical['model']}|1"
        )
        ledger_row = ledger_by_key[ledger_key]
        assert ledger_row["arm"] == canonical["arm"]
        updated = dict(canonical)
        updated.update(
            {
                "cell_key": ledger_key,
                "question_id": replacement_id,
                "source_key": source["source_key"],
                "origin": "replacement22_2026-08-04",
                "score_status": "replacement_scored",
                "status_reason": "protocol_qa_pass_then_scored",
                "source_workbook": relative(WORKBOOK_BY_CONDITION[condition]),
                "source_workbook_sha256": workbook_hash[condition],
                "source_excel_row": row_number[condition][replacement_id],
                "content_sha256": source["content_sha256"],
                "raw_form_sha256": raw_hash(source),
                "prior_experiment": "",
                "prior_database": "",
                "source_csv": relative(INPUT_BY_CONDITION[condition]),
                "region": source["region"],
                "year": source["year"],
                "specialty": source["specialty"],
                "exam_part": source["exam_part"],
                "question_number": source["question_number"],
                "question_text": source["question_text"],
                "option_a": source["option_a"],
                "option_b": source["option_b"],
                "option_c": source["option_c"],
                "option_d": source["option_d"],
                "correct_letter": source["correct_letter"],
                "correct_option_text": source["correct_option_text"],
                "flags": source["flags"],
                "page_in_exam_pdf": source["page_in_exam_pdf"],
                "source_exam_pdf": source["source_exam_pdf"],
                "source_answer_key_pdf": source["source_answer_key_pdf"],
                "selection_score": source["selection_score"],
                "context_ids": source["context_ids"],
                "negated_stem": source["negated_stem"],
                "source_form_input_char_count": sum(
                    len(source[field]) for field in RAW_FIELDS[:5]
                ),
                "score_origin": "2026-08-05_replacement22",
                "result_database": relative(DB),
                "result_experiment": ledger_row["experiment"],
                "replacement_id": replacement_id,
                "replaces_question_id": old_id,
                "candidate_id": manifest_row["candidate_id"],
                "failure_group": manifest_row["failure_group"],
                "record_role": "replacement",
                "replacement_manifest_sha256": replacement_manifest_sha256,
                "replacement_cell_ledger_sha256": replacement_ledger_sha256,
                **{name: value for name, value in result.items() if name != "history"},
            }
        )
        assert set(updated) == set(canonical_fields) | set(LINEAGE_FIELDS)
        assert manifest_row["replaces_question_id"] == old_id
        adjusted.append(updated)
        if result["attempt_count"] > 1:
            failed = result["history"][:-1]
            assert failed
            recovered.append(
                {
                    "replacement_id": replacement_id,
                    "replaces_question_id": old_id,
                    "arm": canonical["arm"],
                    "provider": canonical["provider"],
                    "condition": condition,
                    "model": canonical["model"],
                    "cell_key": ledger_key,
                    "rejected_attempt_count": len(failed),
                    "rejected_attempt_status_code": failed[-1]["status_code"],
                    "rejected_attempt_finish_reason": failed[-1]["finish_reason"],
                    "rejected_attempt_parse_status": failed[-1]["parse_status"],
                    "rejected_attempt_latency_ms": failed[-1]["latency_ms"],
                    "recovery_attempt_status_code": result["latest_status_code"],
                    "recovery_attempt_finish_reason": result["latest_finish_reason"],
                    "recovery_attempt_parse_status": result["parse_status"],
                    "recovery_attempt_latency_ms": result["latest_latency_ms"],
                    "final_score_count": 1,
                    "final_status": "RECOVERED_SCORED",
                }
            )

    assert len(adjusted) == len({row["cell_key"] for row in adjusted}) == 6000
    assert len(recovered) == 2
    assert Counter(row["arm"] for row in adjusted) == Counter(
        {"openrouter_A": 2000, "openrouter_B": 2000, "tailscale_A": 2000}
    )
    assert all(row["final_execution_status"] == "scored" for row in adjusted)
    assert all(str(row["strict_correct"]) in {"0", "1"} for row in adjusted)
    assert len({row["question_id"] for row in adjusted}) == 500
    assert len({row["source_key"] for row in adjusted}) == 500
    assert len({normalized_stem(row["question_text"]) for row in adjusted}) == 500
    assert sum(row["origin"] == "replacement22_2026-08-04" for row in adjusted) == 264

    representative: dict[tuple[str, str], dict[str, Any]] = {}
    for row in adjusted:
        representative.setdefault((row["condition"], row["source_key"]), row)
    for source_key in {row["source_key"] for row in adjusted}:
        a = representative[("A", source_key)]
        b = representative[("B", source_key)]
        validate_source_pair(a, b)

    return adjusted, recovered, replacement_by_id, old_to_new


def arm_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for arm in ARMS:
        subset = [row for row in rows if row["arm"] == arm]
        correct = sum(int(row["strict_correct"]) for row in subset)
        output.append(
            {
                "arm": arm,
                "required_cells": len(subset),
                "scored_cells": len(subset),
                "unresolved_cells": 0,
                "july_reused_scored": sum(
                    row["score_origin"] == "2026-07-31_reused" for row in subset
                ),
                "august_gapfill_scored": sum(
                    row["score_origin"] == "2026-08-04_gapfill" for row in subset
                ),
                "replacement22_scored": sum(
                    row["score_origin"] == "2026-08-05_replacement22" for row in subset
                ),
                "strict_correct": correct,
                "strict_accuracy_scored": f"{correct / len(subset):.8f}",
                "coverage_fraction": "1.00000000",
            }
        )
    return output


def model_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for arm in ARMS:
        for model in MODELS:
            subset = [
                row for row in rows if row["arm"] == arm and row["model"] == model
            ]
            assert len(subset) == 500
            correct = sum(int(row["strict_correct"]) for row in subset)
            output.append(
                {
                    "arm": arm,
                    "model": model,
                    "required_cells": 500,
                    "scored_cells": 500,
                    "unresolved_cells": 0,
                    "strict_correct": correct,
                    "strict_accuracy_scored": f"{correct / 500:.8f}",
                    "coverage_fraction": "1.00000000",
                }
            )
    return output


def paired_openrouter(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indexed = {
        (row["condition"], row["source_key"], row["model"]): row
        for row in rows
        if row["provider"] == "openrouter"
    }
    ordered_questions: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if row["arm"] != "openrouter_A" or row["source_key"] in seen:
            continue
        seen.add(row["source_key"])
        ordered_questions.append((row["question_id"], row["source_key"]))
    assert len(ordered_questions) == 500
    output = []
    for question_id, source_key in ordered_questions:
        for model in MODELS:
            a = indexed[("A", source_key, model)]
            b = indexed[("B", source_key, model)]
            output.append(
                {
                    "question_id": question_id,
                    "source_key": source_key,
                    "origin": a["origin"],
                    "model": model,
                    "run_index": 1,
                    "paired_score_available": "TRUE",
                    "A_status": "scored",
                    "B_status": "scored",
                    "A_selected_letter": a["selected_letter"],
                    "B_selected_letter": b["selected_letter"],
                    "correct_letter": a["correct_letter"],
                    "A_strict_correct": a["strict_correct"],
                    "B_strict_correct": b["strict_correct"],
                    "B_minus_A_strict": int(b["strict_correct"])
                    - int(a["strict_correct"]),
                    "A_score_origin": a["score_origin"],
                    "B_score_origin": b["score_origin"],
                    "A_failure_class": "",
                    "B_failure_class": "",
                }
            )
    assert len(output) == 2000
    both_correct = sum(
        int(row["A_strict_correct"]) == int(row["B_strict_correct"]) == 1
        for row in output
    )
    a_only = sum(
        int(row["A_strict_correct"]) == 1 and int(row["B_strict_correct"]) == 0
        for row in output
    )
    b_only = sum(
        int(row["A_strict_correct"]) == 0 and int(row["B_strict_correct"]) == 1
        for row in output
    )
    both_wrong = 2000 - both_correct - a_only - b_only
    a_correct = sum(int(row["A_strict_correct"]) for row in output)
    b_correct = sum(int(row["B_strict_correct"]) for row in output)
    summary = {
        "required_pairs": 2000,
        "paired_scored": 2000,
        "unpaired": 0,
        "A_strict_correct": a_correct,
        "B_strict_correct": b_correct,
        "A_accuracy_paired": a_correct / 2000,
        "B_accuracy_paired": b_correct / 2000,
        "B_minus_A_accuracy": (b_correct - a_correct) / 2000,
        "both_correct": both_correct,
        "A_only_correct": a_only,
        "B_only_correct": b_only,
        "both_incorrect": both_wrong,
    }
    return output, summary


def select_reserve_backfills(
    catalog: list[dict[str, str]],
    cells: list[dict[str, Any]],
    replacement_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    dossier = Path("/private/tmp/ab182-q5i3oBTb")
    required = (
        dossier / "fully-passing-pool.jsonl",
        dossier / "sourcing-reviews.jsonl",
        dossier / "qa-reviews-initial.jsonl",
        dossier / "qa-reviews-expansion.jsonl",
        dossier / "negstem-labels.json",
    )
    if not all(path.exists() for path in required):
        raise AssertionError("Pinned AB182 reserve-reconstruction dossier is unavailable")

    replacement_candidates = {
        row["candidate_id"] for row in replacement_by_id.values()
    }
    reserve_rows = [row for row in catalog if row["is_reserve"] == "TRUE"]
    promoted = sorted(
        [row for row in reserve_rows if row["candidate_id"] in replacement_candidates],
        key=lambda row: int(row["reserve_rank"]),
    )
    surviving = [row for row in reserve_rows if row not in promoted]
    assert len(promoted) == 7 and len(surviving) == 13

    active_candidate_ids = {
        row["candidate_id"] for row in catalog if row.get("candidate_id")
    } | replacement_candidates
    active_source_keys = {row["source_key"] for row in surviving}
    active_stems = {normalized_stem(row["question_text"]) for row in surviving}
    seen_primary: set[str] = set()
    for row in cells:
        if row["source_key"] in seen_primary:
            continue
        seen_primary.add(row["source_key"])
        active_source_keys.add(row["source_key"])
        active_stems.add(normalized_stem(row["question_text"]))
    assert len(seen_primary) == 500

    sourcing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    qa_reviews: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for review in read_jsonl(dossier / "sourcing-reviews.jsonl"):
        if review.get("verdict") == "PASS":
            sourcing[review["candidate_id"]].append(review)
    for review_path in (
        dossier / "qa-reviews-initial.jsonl",
        dossier / "qa-reviews-expansion.jsonl",
    ):
        for review in read_jsonl(review_path):
            if review.get("verdict") == "PASS":
                qa_reviews[review["candidate_id"]].append(review)
    negated = read_json(dossier / "negstem-labels.json")

    def is_nonnegated(candidate_id: str) -> bool:
        label = negated.get(candidate_id)
        if isinstance(label, dict):
            return label.get("negated") is False
        return label is False

    selected: list[dict[str, Any]] = []
    review_records: list[dict[str, Any]] = []
    excluded_duplicate_repairs = {"c2772", "c0225", "c1152"}
    pool = sorted(
        read_jsonl(dossier / "fully-passing-pool.jsonl"),
        key=lambda packet: (packet["frozen_rank"], packet["candidate_id"]),
    )
    for packet in pool:
        candidate_id = packet["candidate_id"]
        stem = normalized_stem(packet["raw_fields"]["question_text"])
        if (
            candidate_id in active_candidate_ids
            or candidate_id in excluded_duplicate_repairs
            or packet["source_key"] in active_source_keys
            or stem in active_stems
            or not is_nonnegated(candidate_id)
            or not sourcing[candidate_id]
            or not qa_reviews[candidate_id]
        ):
            continue
        source_review = sourcing[candidate_id][0]
        qa_review = qa_reviews[candidate_id][0]
        assert source_review["raw_fields_hash"] == packet["raw_fields_hash"]
        assert qa_review["raw_fields_hash"] == packet["raw_fields_hash"]
        selected.append(packet)
        review_records.append(
            {
                "candidate_id": candidate_id,
                "source_key": packet["source_key"],
                "sourcing_review": source_review,
                "blinded_qa_review": qa_review,
            }
        )
        active_candidate_ids.add(candidate_id)
        active_source_keys.add(packet["source_key"])
        active_stems.add(stem)
    assert [row["candidate_id"] for row in selected] == ["c0989"], [
        row["candidate_id"] for row in selected
    ]

    packet_path = MANIFESTS / "reserve-backfill-source-packets.jsonl"
    review_path = MANIFESTS / "reserve-backfill-reviews.jsonl"
    packet_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected),
        encoding="utf-8",
    )
    review_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in review_records),
        encoding="utf-8",
    )

    selected_by_candidate = {row["candidate_id"]: row for row in selected}
    reviews_by_candidate = {row["candidate_id"]: row for row in review_records}
    mapping: dict[str, dict[str, Any]] = {}
    reconstruction: list[dict[str, Any]] = []
    for index, template in enumerate(promoted):
        if index < len(selected):
            packet = selected[index]
            record = reviews_by_candidate[packet["candidate_id"]]
            mapping[template["question_id"]] = {
                "template": template,
                "packet": selected_by_candidate[packet["candidate_id"]],
                "sourcing_review": record["sourcing_review"],
                "qa_review": record["blinded_qa_review"],
            }
            reconstruction.append(
                {
                    "reserve_rank": int(template["reserve_rank"]),
                    "promoted_candidate_id": template["candidate_id"],
                    "promoted_source_key": template["source_key"],
                    "backfill_candidate_id": packet["candidate_id"],
                    "backfill_source_key": packet["source_key"],
                    "backfill_frozen_rank": packet["frozen_rank"],
                    "sourcing_reviewer": record["sourcing_review"]["reviewer_id"],
                    "qa_reviewer": record["blinded_qa_review"]["reviewer_id"],
                    "status": "BACKFILLED_ACTIVE_RESERVE_NOT_EXECUTED",
                }
            )
        else:
            reconstruction.append(
                {
                    "reserve_rank": int(template["reserve_rank"]),
                    "promoted_candidate_id": template["candidate_id"],
                    "promoted_source_key": template["source_key"],
                    "backfill_candidate_id": "",
                    "backfill_source_key": "",
                    "backfill_frozen_rank": "",
                    "sourcing_reviewer": "",
                    "qa_reviewer": "",
                    "status": "VACANT_PENDING_NEW_QA_APPROVED_RESERVE",
                }
            )
    assert len(mapping) == 1 and len(reconstruction) == 7
    return mapping, reconstruction


def reserve_backfill_row(
    template: dict[str, str],
    packet: dict[str, Any],
    sourcing_review: dict[str, Any],
    qa_review: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    raw = packet["raw_fields"]
    letter = raw["correct_letter"].lower()
    options_b = {name: raw[f"option_{name}"] for name in "abcd"}
    options_b[letter] = "Ninguna de las respuestas anteriores es correcta."
    provenance = packet["provenance"]
    context_chunks = packet.get("context_chunks", [])
    evidence = [
        item
        for item in sourcing_review.get("evidence", [])
        if item.get("kind") == "medical_guidance"
    ]
    if not evidence:
        evidence = [
            item
            for item in qa_review.get("evidence", [])
            if item.get("kind") == "medical_guidance"
        ]
    pair_values = [
        raw["question_text"],
        raw["option_a"],
        raw["option_b"],
        raw["option_c"],
        raw["option_d"],
        letter,
        raw["correct_option_text"],
        options_b["a"],
        options_b["b"],
        options_b["c"],
        options_b["d"],
        "Ninguna de las respuestas anteriores es correcta.",
    ]
    current = dict(template)
    current.update(
        {
            "question_id": packet["candidate_id"],
            "cohort": "reserve_20",
            "target_test_role": "reviewed_reserve",
            "in_primary_500": "FALSE",
            "is_reserve": "TRUE",
            "cohort_rank": template["reserve_rank"],
            "legacy_item_number": "",
            "selection_rank": "",
            "already_run_in_ab_comparison": "FALSE",
            "ab_evaluation_status": "NOT_RUN_RESERVE",
            "ab_evaluation_missing": "TRUE",
            "ab_evaluation_missing_reason": "Reserve outside the authorized 500-question execution",
            "recommended_run_scope": "RESERVE_NOT_IN_PRIMARY_SCOPE",
            "prior_run_snapshot_date": "",
            "prior_ab_provider": "",
            "prior_ab_experiment_a": "",
            "prior_ab_experiment_b": "",
            "prior_ab_paired_model_count": 0,
            "prior_ab_expected_model_count": 4,
            "prior_ab_paired_models": "",
            "prior_a_correct_count": "",
            "prior_b_correct_count": "",
            "prior_a_selected_letters_by_model": "",
            "prior_b_selected_letters_by_model": "",
            "prior_a_backends": "",
            "prior_b_backends": "",
            "region": packet["region"],
            "region_source_label": packet["region"],
            "year": packet["year"],
            "specialty": "aparato-digestivo",
            "source_pair": packet["pair"],
            "exam_part": packet["exam_part"],
            "formal_type": packet["formal_type"],
            "formal_type_source_label": packet["formal_type"],
            "source_question_number": packet["question_number"],
            "question_text": raw["question_text"],
            "question_stem_raw": raw["question_text"],
            "option_a_A": raw["option_a"],
            "option_b_A": raw["option_b"],
            "option_c_A": raw["option_c"],
            "option_d_A": raw["option_d"],
            "correct_letter": letter,
            "correct_option_text_A": raw["correct_option_text"],
            "option_a_B": options_b["a"],
            "option_b_B": options_b["b"],
            "option_c_B": options_b["c"],
            "option_d_B": options_b["d"],
            "correct_option_text_B": "Ninguna de las respuestas anteriores es correcta.",
            "b_replacement_text": "Ninguna de las respuestas anteriores es correcta.",
            "b_changed_fields": f"option_{letter},correct_option_text",
            "b_diff_verified": "TRUE",
            "flags": "",
            "needs_attention": "",
            "case_id": "",
            "visual_id": "",
            "source_key": packet["source_key"],
            "source_sheet": packet["sheet"],
            "source_row": packet["source_row"],
            "source_corpus_path": (
                "/Users/ernestsaenz/Programming/gift-project-compile/second-project/"
                "workbook-repairs-2026-07-30/outputs/"
                "all-regions-aparato-digestivo.corrected.xlsx"
            ),
            "source_corpus_sha256": packet["corpus_sha256"],
            "a_row_source_path": relative(
                MANIFESTS / "reserve-backfill-source-packets.jsonl"
            ),
            "b_row_source_path": "mechanical_two_field_simulation_not_executed",
            "source_exam_pdf_reference": provenance["workbook_exam_name"],
            "source_exam_pdf_path": provenance["exam_pdf_path"],
            "source_exam_pdf_sha256": provenance["exam_pdf_sha256"],
            "page_in_exam_pdf": provenance["exam_page"],
            "source_answer_key_pdf_reference": provenance["workbook_key_name"],
            "source_answer_key_pdf_path": provenance["key_pdf_path"],
            "source_answer_key_pdf_sha256": provenance["key_pdf_sha256"],
            "legacy_content_sha256": packet["raw_fields_hash"],
            "raw_fields_hash": packet["raw_fields_hash"],
            "assembled_question_text_sha256": packet[
                "assembled_context_and_stem_sha256"
            ],
            "master_question_pair_sha256": lp_hash(pair_values),
            "normalized_content_signature": packet["normalized_content_signature"],
            "semantic_signature": packet["semantic_signature"],
            "context_ids": "|".join(
                chunk.get("context_id", "") for chunk in context_chunks
            ),
            "context_hashes": "|".join(
                f"{chunk.get('context_id', '')}:"
                f"{chunk.get('raw_sha256') or chunk.get('sha256') or ''}"
                for chunk in context_chunks
            ),
            "context_chunk_count": len(context_chunks),
            "review_protocol": sourcing_review.get(
                "protocol_version", "ab182-readonly-v1"
            ),
            "review_as_of_date": "2026-08-05",
            "sourcing_reviewer": sourcing_review["reviewer_id"],
            "sourcing_verdict": "PASS",
            "qa1_reviewer": qa_review["reviewer_id"],
            "qa1_verdict": "PASS",
            "qa2_reviewer": "",
            "qa2_verdict": "",
            "review_record_count": 2,
            "medical_guidance_evidence": json.dumps(
                evidence, ensure_ascii=False, separators=(",", ":")
            ),
            "selection_frozen_rank": packet["frozen_rank"],
            "balance_stratum": f"correct_letter_{letter}",
            "traceability_note": (
                "Deterministic reserve backfill after a prior reserve was promoted "
                "into the executed replacement cohort."
            ),
            "candidate_id": packet["candidate_id"],
            "reserve_selection_note": (
                "Deterministic frozen-rank backfill after seven reserve promotions; "
                "sourcing PASS plus one blinded QA PASS; not executed."
            ),
            "current_execution_snapshot_utc": generated_at,
            "current_execution_scope": "RESERVE_NOT_IN_PRIMARY_SCOPE",
            "current_in_scope_required_cells": 0,
            "current_in_scope_scored_cells": 0,
            "current_in_scope_unresolved_cells": 0,
            "current_openrouter_A_scored_models": 0,
            "current_openrouter_B_scored_models": 0,
            "current_tailscale_A_scored_models": 0,
            "current_openrouter_A_missing_models": "",
            "current_openrouter_B_missing_models": "",
            "current_tailscale_A_missing_models": "",
            "current_openrouter_ab_paired_models": 0,
            "current_openrouter_ab_status": "RESERVE_NOT_IN_PRIMARY_SCOPE",
            "current_all_requested_arms_status": "RESERVE_NOT_IN_PRIMARY_SCOPE",
            "current_august_gapfill_scored_cells": 0,
            "current_strict_correct_openrouter_A": "",
            "current_strict_correct_openrouter_B": "",
            "current_strict_correct_tailscale_A": "",
            "current_selected_letters_openrouter_A_by_model": "{}",
            "current_selected_letters_openrouter_B_by_model": "{}",
            "current_selected_letters_tailscale_A_by_model": "{}",
            "current_strict_correct_openrouter_A_by_model": "{}",
            "current_strict_correct_openrouter_B_by_model": "{}",
            "current_strict_correct_tailscale_A_by_model": "{}",
            "current_score_origin_by_arm_model": "{}",
            "current_execution_status_by_arm_model": "{}",
            "current_unresolved_details": "",
        }
    )
    return current


def build_catalog(
    rows: list[dict[str, Any]],
    replacement_by_id: dict[str, dict[str, Any]],
    old_to_new: dict[str, str],
    generated_at: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    catalog = read_csv(CANONICAL_CATALOG)
    fields = csv_fields(CANONICAL_CATALOG)
    assert len(catalog) == 520
    packets = {
        row["candidate_id"]: row
        for row in read_jsonl(HERE / "selected-source-packets.jsonl")
    }
    qa = {
        row["replacement_id"]: row
        for row in read_csv(HERE / "protocol-qa/qa-coverage.csv")
    }
    inputs = {
        condition: {row["question_id"]: row for row in read_csv(path)}
        for condition, path in INPUT_BY_CONDITION.items()
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["question_id"]].append(row)
    reserve_mapping, reserve_reconstruction = select_reserve_backfills(
        catalog, rows, replacement_by_id
    )
    promoted_reserve_candidates = {
        row["promoted_candidate_id"] for row in reserve_reconstruction
    }

    output: list[dict[str, Any]] = []
    map_rows: list[dict[str, Any]] = []
    for original in catalog:
        old_id = original["question_id"]
        if old_id in reserve_mapping:
            backfill = reserve_mapping[old_id]
            current = reserve_backfill_row(
                original,
                backfill["packet"],
                backfill["sourcing_review"],
                backfill["qa_review"],
                generated_at,
            )
            assert set(current) == set(fields)
            output.append(current)
            continue
        if (
            original["is_reserve"] == "TRUE"
            and original["candidate_id"] in promoted_reserve_candidates
        ):
            continue
        if old_id not in old_to_new:
            current = dict(original)
            if current["in_primary_500"] == "TRUE":
                assert current["current_all_requested_arms_status"] == "COMPLETE_12_OF_12_CELLS"
                current["current_execution_snapshot_utc"] = generated_at
            output.append(current)
            continue

        replacement_id = old_to_new[old_id]
        manifest = replacement_by_id[replacement_id]
        packet = packets[manifest["candidate_id"]]
        coverage = qa[replacement_id]
        a = inputs["A"][replacement_id]
        b = inputs["B"][replacement_id]
        validate_source_pair(a, b)
        cell_rows = grouped[replacement_id]
        assert len(cell_rows) == 12

        def arm_rows(arm: str) -> list[dict[str, Any]]:
            return [row for row in cell_rows if row["arm"] == arm]

        def model_values(arm: str, field: str) -> str:
            by_model = {row["model"]: row for row in arm_rows(arm)}
            value = {
                model: (
                    int(by_model[model][field])
                    if field == "strict_correct"
                    else by_model[model][field]
                )
                for model in MODELS
            }
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

        score_origins = {
            arm: {model: "2026-08-05_replacement22" for model in MODELS}
            for arm in ARMS
        }
        execution_statuses = {
            arm: {model: "scored" for model in MODELS} for arm in ARMS
        }
        evidence = []
        prior = manifest.get("prior_sourcing_review")
        manual = manifest.get("manual_research_adjudication")
        if isinstance(prior, dict):
            evidence = [
                item
                for item in prior.get("evidence", [])
                if item.get("kind") == "medical_guidance"
            ]
        if not evidence and isinstance(manual, dict):
            evidence = manual.get("evidence", [])
        official = manifest["official_source"]
        context_chunks = packet.get("context_chunks", [])
        pair_values = [
            a["question_text"],
            a["option_a"],
            a["option_b"],
            a["option_c"],
            a["option_d"],
            a["correct_letter"],
            a["correct_option_text"],
            b["option_a"],
            b["option_b"],
            b["option_c"],
            b["option_d"],
            b["correct_option_text"],
        ]
        current = dict(original)
        current.update(
            {
                "question_id": replacement_id,
                "cohort": "replacement22_2026-08-04",
                "target_test_role": "qa_approved_replacement_primary",
                "cohort_rank": int(replacement_id[1:]),
                "legacy_item_number": old_id,
                "selection_rank": int(replacement_id[1:]),
                "already_run_in_ab_comparison": "TRUE",
                "ab_evaluation_status": "COMPLETE_REPLACEMENT_4_OF_4_MODELS",
                "ab_evaluation_missing": "FALSE",
                "ab_evaluation_missing_reason": "",
                "recommended_run_scope": "COMPLETE_ADJUSTED_BENCHMARK",
                "prior_run_snapshot_date": "",
                "prior_ab_provider": "",
                "prior_ab_experiment_a": "",
                "prior_ab_experiment_b": "",
                "prior_ab_paired_model_count": 0,
                "prior_ab_expected_model_count": 4,
                "prior_ab_paired_models": "",
                "prior_a_correct_count": "",
                "prior_b_correct_count": "",
                "prior_a_selected_letters_by_model": "",
                "prior_b_selected_letters_by_model": "",
                "prior_a_backends": "",
                "prior_b_backends": "",
                "region": a["region"],
                "region_source_label": a["region"],
                "year": a["year"],
                "specialty": a["specialty"],
                "source_pair": packet["pair"],
                "exam_part": a["exam_part"],
                "formal_type": packet["formal_type"],
                "formal_type_source_label": packet["formal_type"],
                "source_question_number": a["question_number"],
                "question_text": a["question_text"],
                "question_stem_raw": packet["raw_fields"]["question_text"],
                "option_a_A": a["option_a"],
                "option_b_A": a["option_b"],
                "option_c_A": a["option_c"],
                "option_d_A": a["option_d"],
                "correct_letter": a["correct_letter"],
                "correct_option_text_A": a["correct_option_text"],
                "option_a_B": b["option_a"],
                "option_b_B": b["option_b"],
                "option_c_B": b["option_c"],
                "option_d_B": b["option_d"],
                "correct_option_text_B": b["correct_option_text"],
                "b_replacement_text": "Ninguna de las respuestas anteriores es correcta.",
                "b_changed_fields": f"option_{a['correct_letter']},correct_option_text",
                "b_diff_verified": "TRUE",
                "flags": a["flags"],
                "needs_attention": "",
                "case_id": "",
                "visual_id": "",
                "source_key": a["source_key"],
                "source_sheet": packet["sheet"],
                "source_row": packet["source_row"],
                "source_corpus_path": (
                    "/Users/ernestsaenz/Programming/gift-project-compile/second-project/"
                    "workbook-repairs-2026-07-30/outputs/"
                    "all-regions-aparato-digestivo.corrected.xlsx"
                ),
                "source_corpus_sha256": packet["corpus_sha256"],
                "a_row_source_path": relative(INPUT_BY_CONDITION["A"]),
                "b_row_source_path": relative(INPUT_BY_CONDITION["B"]),
                "source_exam_pdf_reference": official["workbook_exam_name"],
                "source_exam_pdf_path": official["exam_pdf_path"],
                "source_exam_pdf_sha256": official["exam_pdf_sha256"],
                "page_in_exam_pdf": official["exam_page"],
                "source_answer_key_pdf_reference": official["workbook_key_name"],
                "source_answer_key_pdf_path": official["key_pdf_path"],
                "source_answer_key_pdf_sha256": official["key_pdf_sha256"],
                "legacy_content_sha256": a["content_sha256"],
                "raw_fields_hash": packet["raw_fields_hash"],
                "assembled_question_text_sha256": packet[
                    "assembled_context_and_stem_sha256"
                ],
                "master_question_pair_sha256": lp_hash(pair_values),
                "normalized_content_signature": packet[
                    "normalized_content_signature"
                ],
                "semantic_signature": packet["semantic_signature"],
                "context_ids": "|".join(
                    chunk.get("context_id", "") for chunk in context_chunks
                ),
                "context_hashes": "|".join(
                    f"{chunk.get('context_id', '')}:"
                    f"{chunk.get('raw_sha256') or chunk.get('sha256') or ''}"
                    for chunk in context_chunks
                ),
                "context_chunk_count": len(context_chunks),
                "review_protocol": "ab520-replacement22-formal-qa-v1",
                "review_as_of_date": "2026-08-05",
                "sourcing_reviewer": coverage["sourcing_reviewer"],
                "sourcing_verdict": "PASS",
                "qa1_reviewer": coverage["qa1_reviewer"],
                "qa1_verdict": "PASS",
                "qa2_reviewer": coverage["qa2_reviewer"],
                "qa2_verdict": "PASS",
                "review_record_count": 3,
                "medical_guidance_evidence": json.dumps(
                    evidence, ensure_ascii=False, separators=(",", ":")
                ),
                "selection_frozen_rank": packet["frozen_rank"],
                "balance_stratum": f"correct_letter_{a['correct_letter']}",
                "traceability_note": (
                    f"QA-approved replacement for {old_id}; original item and all of "
                    "its prior cells are excluded from the adjusted analysis."
                ),
                "candidate_id": manifest["candidate_id"],
                "reserve_selection_note": "",
                "current_execution_snapshot_utc": generated_at,
                "current_execution_scope": (
                    "OpenRouter A, OpenRouter B, GIFT/TailScale A; four models; "
                    "TailScale B excluded"
                ),
                "current_in_scope_required_cells": 12,
                "current_in_scope_scored_cells": 12,
                "current_in_scope_unresolved_cells": 0,
                "current_openrouter_A_scored_models": 4,
                "current_openrouter_B_scored_models": 4,
                "current_tailscale_A_scored_models": 4,
                "current_openrouter_A_missing_models": "",
                "current_openrouter_B_missing_models": "",
                "current_tailscale_A_missing_models": "",
                "current_openrouter_ab_paired_models": 4,
                "current_openrouter_ab_status": "COMPLETE_4_OF_4_MODELS",
                "current_all_requested_arms_status": "COMPLETE_12_OF_12_CELLS",
                "current_august_gapfill_scored_cells": 0,
                "current_strict_correct_openrouter_A": sum(
                    int(row["strict_correct"]) for row in arm_rows("openrouter_A")
                ),
                "current_strict_correct_openrouter_B": sum(
                    int(row["strict_correct"]) for row in arm_rows("openrouter_B")
                ),
                "current_strict_correct_tailscale_A": sum(
                    int(row["strict_correct"]) for row in arm_rows("tailscale_A")
                ),
                "current_selected_letters_openrouter_A_by_model": model_values(
                    "openrouter_A", "selected_letter"
                ),
                "current_selected_letters_openrouter_B_by_model": model_values(
                    "openrouter_B", "selected_letter"
                ),
                "current_selected_letters_tailscale_A_by_model": model_values(
                    "tailscale_A", "selected_letter"
                ),
                "current_strict_correct_openrouter_A_by_model": model_values(
                    "openrouter_A", "strict_correct"
                ),
                "current_strict_correct_openrouter_B_by_model": model_values(
                    "openrouter_B", "strict_correct"
                ),
                "current_strict_correct_tailscale_A_by_model": model_values(
                    "tailscale_A", "strict_correct"
                ),
                "current_score_origin_by_arm_model": json.dumps(
                    score_origins, ensure_ascii=False, separators=(",", ":")
                ),
                "current_execution_status_by_arm_model": json.dumps(
                    execution_statuses, ensure_ascii=False, separators=(",", ":")
                ),
                "current_unresolved_details": "",
            }
        )
        assert set(current) == set(fields)
        output.append(current)
        map_rows.append(
            {
                "replacement_id": replacement_id,
                "replaces_question_id": old_id,
                "candidate_id": manifest["candidate_id"],
                "failure_group": manifest["failure_group"],
                "source_key": manifest["source_key"],
                "old_correct_letter": manifest["old_correct_letter"],
                "new_correct_letter": manifest["new_correct_letter"],
                "sourcing_reviewer": coverage["sourcing_reviewer"],
                "qa1_reviewer": coverage["qa1_reviewer"],
                "qa2_reviewer": coverage["qa2_reviewer"],
                "protocol_gate": coverage["protocol_gate"],
                "openrouter_A_scored": len(arm_rows("openrouter_A")),
                "openrouter_B_scored": len(arm_rows("openrouter_B")),
                "tailscale_A_scored": len(arm_rows("tailscale_A")),
                "total_scored": len(cell_rows),
                "execution_status": "COMPLETE_12_OF_12_CELLS",
            }
        )

    assert len(output) == 514
    assert len({row["question_id"] for row in output}) == 514
    assert len({row["source_key"] for row in output}) == 514
    primary = [row for row in output if row["in_primary_500"] == "TRUE"]
    reserves = [row for row in output if row["is_reserve"] == "TRUE"]
    assert len(primary) == 500 and len(reserves) == 14
    assert all(
        row["current_all_requested_arms_status"] == "COMPLETE_12_OF_12_CELLS"
        for row in primary
    )
    assert len(map_rows) == 22
    assert len(reserve_reconstruction) == 7
    reconstruction_by_candidate = {
        row["promoted_candidate_id"]: row for row in reserve_reconstruction
    }
    reserve_status: list[dict[str, Any]] = []
    for historical in [row for row in catalog if row["is_reserve"] == "TRUE"]:
        reconstruction = reconstruction_by_candidate.get(historical["candidate_id"])
        if reconstruction is None:
            reserve_status.append(
                {
                    "historical_reserve_rank": historical["reserve_rank"],
                    "historical_master_position": historical["master_520_position"],
                    "historical_candidate_id": historical["candidate_id"],
                    "historical_source_key": historical["source_key"],
                    "adjusted_status": "ACTIVE_RESERVE_NOT_EXECUTED",
                    "promoted_to_replacement_id": "",
                    "active_backfill_candidate_id": historical["candidate_id"],
                    "active_backfill_source_key": historical["source_key"],
                    "note": "Unchanged active reserve.",
                }
            )
            continue
        promoted_to = next(
            replacement_id
            for replacement_id, manifest in replacement_by_id.items()
            if manifest["candidate_id"] == historical["candidate_id"]
        )
        reserve_status.append(
            {
                "historical_reserve_rank": historical["reserve_rank"],
                "historical_master_position": historical["master_520_position"],
                "historical_candidate_id": historical["candidate_id"],
                "historical_source_key": historical["source_key"],
                "adjusted_status": reconstruction["status"],
                "promoted_to_replacement_id": promoted_to,
                "active_backfill_candidate_id": reconstruction[
                    "backfill_candidate_id"
                ],
                "active_backfill_source_key": reconstruction["backfill_source_key"],
                "note": (
                    "Historical reserve was promoted into the executed primary cohort; "
                    "a blank backfill means the reserve slot remains vacant pending QA."
                ),
            }
        )
    assert len(reserve_status) == 20
    assert Counter(row["adjusted_status"] for row in reserve_status) == Counter(
        {
            "ACTIVE_RESERVE_NOT_EXECUTED": 13,
            "BACKFILLED_ACTIVE_RESERVE_NOT_EXECUTED": 1,
            "VACANT_PENDING_NEW_QA_APPROVED_RESERVE": 6,
        }
    )
    return output, map_rows, reserve_status


def write_run_ledger() -> tuple[list[dict[str, Any]], str, str]:
    invocations = [read_json(path) for path in sorted(INVOCATIONS.glob("*.json"))]
    assert len(invocations) == 16
    invocations.sort(key=lambda row: row["start_time_utc"])
    fields = [
        "invocation_id",
        "arm",
        "condition",
        "model",
        "dataset",
        "experiment_id",
        "target_count",
        "concurrency",
        "start_time_utc",
        "end_time_utc",
        "status",
        "scored_count",
        "failure_count",
        "redacted_command",
        "log_path",
        "notes",
    ]
    rows = []
    for invocation in invocations:
        rows.append(
            {
                **{field: invocation.get(field, "") for field in fields[:-1]},
                "notes": (
                    f"skipped_already_scored={invocation.get('skipped_already_scored', 0)}; "
                    f"not_started_after_abort={invocation.get('not_started_after_abort', 0)}; "
                    f"stop_reason={invocation.get('stop_reason') or 'none'}"
                ),
            }
        )
    assert sum(int(row["scored_count"]) for row in rows) == 264
    assert sum(int(row["failure_count"]) for row in rows) == 2
    write_csv(HERE / "RUN_LEDGER.csv", rows, fields)
    return rows, rows[0]["start_time_utc"], rows[-1]["end_time_utc"]


def update_run_matrix() -> None:
    matrix_path = HERE / "run-matrix-264.csv"
    rows = read_csv(matrix_path)
    assert len(rows) == 264
    for row in rows:
        row["status"] = "SCORED"
    write_csv(matrix_path, rows, csv_fields(matrix_path))


def backup_database() -> dict[str, Any]:
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix="post-execution-", suffix=".sqlite", dir=MANIFESTS
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        source = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        destination = sqlite3.connect(temp_path)
        source.backup(destination)
        destination.close()
        source.close()
        check = sqlite3.connect(f"file:{temp_path}?mode=ro", uri=True)
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {
            "datasets": check.execute("SELECT COUNT(*) FROM datasets").fetchone()[0],
            "questions": check.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
            "experiments": check.execute("SELECT COUNT(*) FROM experiments").fetchone()[0],
            "logical_calls": check.execute("SELECT COUNT(*) FROM logical_calls").fetchone()[0],
            "provider_attempts": check.execute(
                "SELECT COUNT(*) FROM provider_attempts"
            ).fetchone()[0],
            "scores": check.execute("SELECT COUNT(*) FROM scores").fetchone()[0],
        }
        check.close()
        assert integrity == "ok"
        assert counts == {
            "datasets": 2,
            "questions": 44,
            "experiments": 3,
            "logical_calls": 264,
            "provider_attempts": 266,
            "scores": 264,
        }
        temp_path.replace(POST_DB)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    digest = sha256_file(POST_DB)
    (MANIFESTS / "ab520-replacement22.post-execution.sqlite.sha256").write_text(
        f"{digest}  {POST_DB.name}\n", encoding="utf-8"
    )
    return {"path": relative(POST_DB), "sha256": digest, "integrity": integrity, **counts}


def replace_exact(text: str, old: str, new: str) -> str:
    if old not in text:
        raise AssertionError(f"Presentation template text not found: {old[:80]!r}")
    return text.replace(old, new)


def build_presentation() -> None:
    PRESENTATION.mkdir(parents=True, exist_ok=True)
    source_builder = CANONICAL / "presentation/build_results_presentation.py"
    source_template = CANONICAL / "presentation/results_presentation_template.html"
    builder = source_builder.read_text(encoding="utf-8")
    builder = replace_exact(
        builder,
        '"analysis_date": "2026-08-04"',
        '"analysis_date": "2026-08-05"',
    )
    builder = replace_exact(
        builder,
        '"benchmark-6000-cell-results.csv"',
        '"benchmark-6000-cell-results-adjusted.csv"',
    )
    (PRESENTATION / "build_results_presentation.py").write_text(
        builder, encoding="utf-8"
    )
    template = source_template.read_text(encoding="utf-8")
    replacements = [
        (
            "The paired reduction appeared in all four models and remained under distribution-free testing.",
            "The paired effect is reported with model-specific estimates and distribution-free testing.",
        ),
        (
            "<td><i>W</i>=0.581–0.883; all <i>p</i>≤5.60e−19</td>",
            "<td>See the regenerated <code>statistics.json</code> for each arm.</td>",
        ),
        (
            "Model bars are paired complete-case estimates; GLM has {{ result.per_model_ab[3].n_pairs }} pairs and the other models have 500. Exact model-level <i>p</i> values were all ≤4.46e−10.",
            "Model bars use 500 paired questions for every model. Exact model-level <i>p</i> values are reported in the regenerated statistics record.",
        ),
        (
            "GIFT/RAG showed a nominal {{ \"%.1f\"|format(result.openrouter_a_vs_gift_a.risk_difference * 100) }}-point advantage—with coverage-sensitive inference",
            "GIFT/RAG versus OpenRouter A, with complete scored coverage in both arms",
        ),
        (
            "If every unresolved response is assigned the most unfavorable or favorable outcome, the arm difference crosses zero.",
            "No unresolved cells remain; both extreme missing-data bounds therefore equal the observed complete-data difference.",
        ),
        (
            "There were {{ result.coverage_context.gift_a_unresolved }} unresolved GIFT/RAG A cells, including {{ result.coverage_context.overlength_failures }} correlated failures from {{ result.coverage_context.overlength_questions }} linked-context questions. TailScale/GIFT B was not run. The comparison therefore cannot isolate a causal RAG effect from orchestration, provider route, run timing, or non-random missingness.",
            "All authorized condition-A cells were scored after replacing the protocol-rejected questions. TailScale/GIFT B was not run, so the comparison still cannot isolate a causal RAG effect from orchestration, provider route, or run timing.",
        ),
        (
            "Model ordering was stable; the size of the B penalty was not",
            "Strict accuracy by model and authorized benchmark arm",
        ),
        (
            "Within-arm model differences were strong: Cochran’s Q={{ \"%.1f\"|format(result.model_summaries[0].cochran_q) }}, {{ \"%.1f\"|format(result.model_summaries[4].cochran_q) }}, and {{ \"%.1f\"|format(result.model_summaries[8].cochran_q) }} for OpenRouter A, OpenRouter B, and GIFT/RAG A, respectively (df=3; all <i>p</i>&lt;1.3e−19).",
            "Within-arm omnibus results are Cochran’s Q={{ \"%.1f\"|format(result.model_summaries[0].cochran_q) }}, {{ \"%.1f\"|format(result.model_summaries[4].cochran_q) }}, and {{ \"%.1f\"|format(result.model_summaries[8].cochran_q) }} for OpenRouter A, OpenRouter B, and GIFT/RAG A; exact <i>p</i> values are in the statistics record.",
        ),
        (
            "GIFT/RAG A was {{ \"%.1f\"|format(result.openrouter_a_vs_gift_a.risk_difference * 100) }} points higher on matched scored cells, but the extreme missing-data bounds crossed zero and no GIFT/RAG B arm exists.",
            "GIFT/RAG A differed by {{ \"%.1f\"|format(result.openrouter_a_vs_gift_a.risk_difference * 100) }} points on 2,000 matched scored cells; no GIFT/RAG B arm exists.",
        ),
        (
            "treat cross-platform and model-taxonomy rankings as exploratory, coverage-sensitive associations.",
            "treat cross-platform and model-taxonomy rankings as exploratory associations.",
        ),
        (
            "500 questions = 318 retained + 182 new · 20 reserves not run",
            "500 questions = 478 original items + 22 QA replacements · 14 active reserves not run",
        ),
    ]
    for old, new in replacements:
        template = replace_exact(template, old, new)
    (PRESENTATION / "results_presentation_template.html").write_text(
        template, encoding="utf-8"
    )
    subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "jinja2",
            "python",
            str(PRESENTATION / "build_results_presentation.py"),
        ],
        cwd=REPO,
        check=True,
    )


def update_package_status() -> None:
    for path in (
        HERE / "replacement-manifest.json",
        HERE / "selection-spec.json",
        HERE / "benchmark-500-with-provisional-replacements.json",
    ):
        data = read_json(path)
        data["status"] = "EXECUTION_COMPLETE_6000_OF_6000_SCORED"
        if isinstance(data.get("execution_status"), dict):
            data["execution_status"].update(
                {
                    "status": "COMPLETE",
                    "replacement_cells_scored": 264,
                    "adjusted_cells_scored": 6000,
                    "adjusted_unresolved_cells": 0,
                    "completed_at_utc": "2026-08-05",
                }
            )
        write_json(path, data)


def write_docs(
    generated_at: str,
    started_at: str,
    ended_at: str,
    provider_rows: list[dict[str, Any]],
    paired_summary: dict[str, Any],
) -> None:
    production = read_json(MANIFESTS / "production-evidence-2026-08-05.json")
    status = f"""# Replacement execution status

Updated: {generated_at}

QA gate: **PASS — 22/22 sourcing, 22/22 QA1, 22/22 QA2**.

| Arm | Original cells retained | Replacement cells scored | Final scored | Queued | Unresolved |
|---|---:|---:|---:|---:|---:|
| OpenRouter A | 1,912 | 88 | 2,000 | 0 | 0 |
| OpenRouter B | 1,912 | 88 | 2,000 | 0 | 0 |
| GIFT/TailScale A | 1,912 | 88 | 2,000 | 0 | 0 |

Execution window: `{started_at}` to `{ended_at}`. Active concurrency: **0**.

Production gate: **PASS**. Required SHA `{production['required_commit']}` was the latest successful main deployment; deployment run `{production['deployment']['run_id']}` and the live health/authentication checks passed before GIFT traffic.

Final recovery: **264/264 replacement cells scored**. Two rejected first attempts were recovered by isolated exact-input retries: one OpenRouter GLM length-terminated response and one GIFT Qwen non-answer response. Residual replacement failures: **0**.

Adjusted analysis: **6,000/6,000 scored**, comprising 5,736 retained canonical scores and 264 QA-approved replacement scores. The 22 rejected original questions and all 264 of their former cells are excluded; no result was inferred or reassigned.

Reserve status: seven historical reserves were promoted into the primary replacement cohort. Thirteen prior reserves remain active and the frozen reviewed pool supplied one collision-free backfill (`c0989`), leaving **14 active reserves and six explicitly vacant reserve slots pending new QA**.

Workbook note: the adjusted CSV, JSON, and HTML artifacts are complete. A new adjusted `.xlsx` was not authored because the required `load_workspace_dependencies`/`@oai/artifact-tool` runtime is unavailable in this environment.
"""
    (HERE / "STATUS.md").write_text(status, encoding="utf-8")

    readme = """# QA-approved 22-question replacement and adjusted August benchmark

This directory is the auditable replacement workspace for the August 26 experiment. Formal sourcing and two distinct blinded QA passes approved all 22 questions. The cohort was then run across four models in OpenRouter condition A, OpenRouter condition B, and GIFT/TailScale condition A. TailScale condition B remains outside the authorized design.

The adjusted benchmark is complete: **2,000/2,000 scored cells per arm and 6,000/6,000 overall**. It retains 478 original benchmark questions (5,736 scored cells), removes the 22 rejected originals and all their prior cells, and inserts 22 newly identified replacement questions (264 scored cells). The replacements are new questions, not retroactive answers to the rejected originals.

## Models and conditions

- `google/gemini-3.6-flash`
- `google/gemma-4-26b-a4b-it`
- `qwen/qwen3.6-35b-a3b`
- `z-ai/glm-5.2`
- Condition A preserves the official answer option.
- Condition B performs the verified two-field substitution at the keyed option and `correct_option_text`.

## Main outputs

- `exports/benchmark-6000-cell-results-adjusted.csv`: all 6,000 scored cells with exact inputs, selected answers, correctness, attempts, hashes, and score origin.
- `exports/benchmark-500-question-catalog-adjusted.csv`: the complete adjusted primary benchmark.
- `exports/benchmark-514-active-question-catalog-adjusted.csv`: 500 primary questions plus the 14 currently active, collision-free reserves.
- `exports/reserve-20-historical-status-adjusted.csv`: all 20 historical reserve slots, showing seven promotions, one reviewed backfill, and six explicit vacancies pending QA.
- `exports/replacement-question-map.csv`: old ID → replacement ID → source/QA/execution mapping.
- `exports/recovered-first-attempt-failures.csv`: the two fail-closed first attempts and their successful isolated retries, without raw response text.
- `presentation/benchmark-results-presentation.html` and `presentation/statistics.json`: regenerated adjusted analysis.
- `manifests/execution-manifest-final.json`: final validation, provenance, counts, and hashes.
- `RUN_LEDGER.csv` and `STATUS.md`: one row per invocation and the final operational state.

The original result set remains unchanged at `data/experiment-4-aug-26/results/ab520-gapfill-2026-08-04/`. The benchmark source corpus is `/Users/ernestsaenz/Programming/gift-project-compile/second-project/workbook-repairs-2026-07-30/outputs/all-regions-aparato-digestivo.corrected.xlsx` (SHA-256 `18f6becd4e51f1b9ef6a5a8ab68421e905cfe2584ec32a0e303b76f3cacf1e46`). The execution harness is `code/medrag_eval/`.

No input question, prompt, model identifier, answer key, or provider condition was edited during execution. GIFT calls used prompt ID 13, temperature 0, and the production SHA gate recorded in `manifests/production-evidence-2026-08-05.json`.

The adjusted CSV/JSON/HTML deliverables are complete. A new adjusted `.xlsx` could not be authored because the workspace-required `load_workspace_dependencies`/`@oai/artifact-tool` runtime was not available; the canonical pre-replacement workbook is therefore not presented as an adjusted output.
"""
    (HERE / "README.md").write_text(readme, encoding="utf-8")

    qa_report = f"""# Final QA and execution report

Generated: {generated_at}

Verdict: **PASS — QA complete and adjusted benchmark complete**.

## QA gates

- Formal sourcing: 22/22 PASS.
- Blinded QA1: 22/22 PASS.
- Blinded QA2: 22/22 PASS, with a distinct reviewer for every candidate.
- Condition B mechanical transformation: 22/22 exact two-field swaps.
- Official workbook, exam PDF, and definitive-key bindings: 22/22 verified.
- Duplicate adjudication for c0369: PASS; the historical three-option variant is absent from the active benchmark and is not a full-content collision.

## Execution integrity

- Frozen replacement ledger: 264 unique cells, 88 per arm.
- Replacement database: 264 logical calls, 266 provider attempts, 264 scores, integrity check `ok`.
- Every replacement cell has exactly one score and an unchanged question, prompt, model, condition, and input hash.
- All GIFT attempts use prompt ID 13; no TailScale B calls exist.
- No `--force`, reasoning-disable, answer inference, input truncation, or score reassignment was used.
- Two rejected first attempts were retained as diagnostic evidence and did not create scores; isolated exact-input retries recovered both.

## Adjusted benchmark reconciliation

- Canonical source: 6,000 cells, 5,930 scored and 70 unresolved.
- Removed with the 22 rejected originals: 264 cells, including all 70 unresolved cells.
- Retained: 5,736/5,736 scored cells from 478 questions.
- Added: 264/264 scored cells from the 22 QA-approved replacements.
- Final: **6,000/6,000 scored, 2,000/2,000 per arm, zero unresolved**.
- OpenRouter paired A/B coverage: {paired_summary['paired_scored']:,}/{paired_summary['required_pairs']:,}.
- Reserve catalog: 14 active collision-free reserves; six of the 20 historical slots remain vacant pending new QA after seven reserve promotions and one reviewed backfill.

## Arm results

| Arm | Scored | Strict correct | Strict accuracy |
|---|---:|---:|---:|
""" + "\n".join(
        f"| {row['arm']} | {row['scored_cells']:,} | {row['strict_correct']:,} | {float(row['strict_accuracy_scored']):.2%} |"
        for row in provider_rows
    ) + """

The complete per-cell audit trail, QA coverage, production evidence, invocations, database snapshots, and checksums remain in this directory. A Snyk Code scan was attempted separately; the installed CLI rejected its credentials with HTTP 401, so no successful Snyk result is claimed.

Spreadsheet limitation: the adjusted `.xlsx` remains blocked because the mandated artifact-tool dependency loader is unavailable. CSV outputs and the standalone statistical HTML presentation were regenerated and verified.
"""
    (HERE / "QA_REPORT.md").write_text(qa_report, encoding="utf-8")

    report = f"""# Final adjusted execution report

Generated: {generated_at}

The replacement workflow completed with **6,000/6,000 scored cells** and no unresolved cells. Each authorized arm contains exactly 2,000 scores. The result combines 5,736 unchanged retained scores with 264 scores from 22 fully QA-approved replacement questions.

The 22 rejected original questions were removed as questions, so none of their scored or failed cells contributes to the adjusted analysis. This is a replacement-cohort result, not a retry-based recovery of the rejected items.

OpenRouter A/B has {paired_summary['paired_scored']:,}/{paired_summary['required_pairs']:,} exact matched pairs. Condition A strict accuracy is {paired_summary['A_accuracy_paired']:.2%}; condition B is {paired_summary['B_accuracy_paired']:.2%}; B minus A is {paired_summary['B_minus_A_accuracy']:.2%}.

Two provider responses failed closed on their first attempt: OpenRouter GLM r018 ended by length without a parseable answer, and GIFT Qwen r004 returned a non-answer message. Both exact-input isolated retries succeeded, while the rejected responses remain recorded as attempts and never received inferred scores.

See `exports/`, `presentation/`, `RUN_LEDGER.csv`, `STATUS.md`, and `manifests/execution-manifest-final.json` for the reproducible outputs and provenance.

Reserve lineage is kept separate from the scored result: 13 prior reserves remain active, `c0989` is the sole eligible reviewed backfill in the frozen pool, and six historical reserve slots remain vacant pending new QA. No duplicate reserve was silently retained.
"""
    FINAL_REPORT.write_text(report, encoding="utf-8")


def write_code_provenance() -> dict[str, str]:
    paths = sorted((REPO / "code/medrag_eval").rglob("*.py")) + [
        HERE / "build_replacement_package.py",
        HERE / "prepare_protocol_qa.py",
        HERE / "finalize_protocol_qa.py",
        HERE / "prepare_execution.py",
        HERE / "execute_replacement_cells.py",
        HERE / "finalize_execution.py",
        PRESENTATION / "build_results_presentation.py",
    ]
    hashes = {relative(path): sha256_file(path) for path in paths}
    (MANIFESTS / "code-provenance.sha256").write_text(
        "".join(f"{digest}  {path}\n" for path, digest in hashes.items()),
        encoding="utf-8",
    )
    return hashes


def write_checksums(paths: list[Path], destination: Path) -> None:
    unique = sorted({path.resolve() for path in paths})
    destination.write_text(
        "".join(
            f"{sha256_file(path)}  {relative(path)}\n"
            for path in unique
            if path.exists() and path.is_file()
        ),
        encoding="utf-8",
    )


def main() -> None:
    generated_at = utc_now()
    for directory in (EXPORTS, MANIFESTS, PRESENTATION, RUNS):
        directory.mkdir(parents=True, exist_ok=True)

    qa_summary = read_json(HERE / "protocol-qa/final-review-summary.json")
    assert qa_summary["status"] == "PASS_QA_COMPLETE_READY_FOR_EXECUTION"
    assert qa_summary["candidate_count"] == 22
    assert qa_summary["formal_sourcing_passes"] == 22
    assert qa_summary["blinded_qa1_passes"] == qa_summary["blinded_qa2_passes"] == 22

    cells, recovered, replacement_by_id, old_to_new = build_adjusted_cells(generated_at)
    provider_rows = arm_summary(cells)
    model_rows = model_summary(cells)
    paired_rows, paired_summary = paired_openrouter(cells)
    catalog_rows, map_rows, reserve_status_rows = build_catalog(
        cells, replacement_by_id, old_to_new, generated_at
    )
    primary_rows = [row for row in catalog_rows if row["in_primary_500"] == "TRUE"]

    write_csv(
        CELLS_OUT,
        cells,
        csv_fields(CANONICAL_CELLS) + list(LINEAGE_FIELDS),
    )
    write_csv(CATALOG_OUT, catalog_rows, csv_fields(CANONICAL_CATALOG))
    write_csv(PRIMARY_CATALOG_OUT, primary_rows, csv_fields(CANONICAL_CATALOG))
    write_csv(RESERVE_STATUS_OUT, reserve_status_rows)
    write_csv(PROVIDER_OUT, provider_rows)
    write_csv(MODEL_OUT, model_rows)
    write_csv(PAIRED_OUT, paired_rows)
    write_csv(MAP_OUT, map_rows)
    write_csv(RECOVERED_OUT, recovered)
    unresolved_fields = csv_fields(CANONICAL_EXPORTS / "unresolved-cells.csv")
    write_csv(UNRESOLVED_OUT, [], unresolved_fields)

    ledger_rows, started_at, ended_at = write_run_ledger()
    update_run_matrix()
    post_db = backup_database()
    build_presentation()
    write_docs(generated_at, started_at, ended_at, provider_rows, paired_summary)
    code_hashes = write_code_provenance()

    tracked_changes = subprocess.check_output(
        ["git", "diff", "--name-only"], cwd=REPO, text=True
    ).splitlines()
    allowed_prefix = relative(HERE) + "/"
    assert all(path.startswith(allowed_prefix) for path in tracked_changes), tracked_changes
    repository_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
    ).strip()

    output_paths = [
        CELLS_OUT,
        CATALOG_OUT,
        PRIMARY_CATALOG_OUT,
        RESERVE_STATUS_OUT,
        PROVIDER_OUT,
        MODEL_OUT,
        PAIRED_OUT,
        UNRESOLVED_OUT,
        MAP_OUT,
        RECOVERED_OUT,
        PRESENTATION / "benchmark-results-presentation.html",
        PRESENTATION / "statistics.json",
        PRESENTATION / "analysis-summary.csv",
        HERE / "RUN_LEDGER.csv",
        HERE / "STATUS.md",
        HERE / "README.md",
        HERE / "QA_REPORT.md",
        FINAL_REPORT,
        POST_DB,
        MANIFESTS / "reserve-backfill-source-packets.jsonl",
        MANIFESTS / "reserve-backfill-reviews.jsonl",
    ]
    input_paths = [
        CANONICAL_CELLS,
        CANONICAL_CATALOG,
        HERE / "replacement-manifest.json",
        HERE / "protocol-qa/final-review-summary.json",
        HERE / "protocol-qa/qa-coverage.csv",
        LEDGER,
        INPUT_BY_CONDITION["A"],
        INPUT_BY_CONDITION["B"],
        WORKBOOK_BY_CONDITION["A"],
        WORKBOOK_BY_CONDITION["B"],
        DB,
        MANIFESTS / "production-evidence-2026-08-05.json",
        MANIFESTS / "ab520-replacement22.pre-execution.sqlite",
    ]
    pre_db_expected = (
        MANIFESTS / "ab520-replacement22.pre-execution.sqlite.sha256"
    ).read_text(encoding="utf-8").split()[0]
    assert sha256_file(MANIFESTS / "ab520-replacement22.pre-execution.sqlite") == pre_db_expected

    manifest = {
        "artifact_version": "ab520-adjusted-replacement22-final-v1",
        "generated_at_utc": generated_at,
        "status": "COMPLETE_6000_OF_6000_SCORED",
        "scope": {
            "primary_questions": 500,
            "original_questions_retained": 478,
            "qa_approved_replacement_questions": 22,
            "reserve_questions_documented_not_run": 20,
            "active_reserve_questions": 14,
            "vacant_reserve_slots_pending_qa": 6,
            "arms": list(ARMS),
            "excluded_arm": "tailscale_B",
            "models": list(MODELS),
            "required_cells": 6000,
            "scored_cells": 6000,
            "unresolved_cells": 0,
        },
        "reconciliation": {
            "canonical_required_cells": 6000,
            "canonical_scored_cells": 5930,
            "canonical_unresolved_cells": 70,
            "removed_original_questions": 22,
            "removed_original_cells": 264,
            "retained_original_cells": 5736,
            "retained_original_scored_cells": 5736,
            "replacement_cells_added": 264,
            "replacement_cells_scored": 264,
            "final_scored_cells": 6000,
            "final_unresolved_cells": 0,
        },
        "protocol_qa": {
            "formal_sourcing_passes": 22,
            "blinded_qa1_passes": 22,
            "blinded_qa2_passes": 22,
            "distinct_reviewers_per_candidate": True,
            "adverse_or_uncertain_findings": 0,
        },
        "execution": {
            "window_start_utc": started_at,
            "window_end_utc": ended_at,
            "invocations": len(ledger_rows),
            "logical_cells": 264,
            "provider_attempts": 266,
            "scores": 264,
            "rejected_first_attempts_recovered": 2,
            "residual_failures": 0,
            "temperature": 0,
            "prompt_version": "mcq_es_v4",
            "tailscale_prompt_id": 13,
            "force_used": False,
            "reasoning_disabled": False,
        },
        "provider_condition_summary": provider_rows,
        "model_condition_summary": model_rows,
        "openrouter_paired_ab": paired_summary,
        "reserve_reconstruction": {
            "historical_slots": 20,
            "surviving_active_reserves": 13,
            "deterministic_reviewed_backfills": 1,
            "vacant_slots_pending_new_qa": 6,
            "slot_status": reserve_status_rows,
            "note": (
                "Seven historical reserves were promoted into the executed primary "
                "replacement cohort. The frozen reviewed pool supplied only c0989 as "
                "a collision-free reviewed backfill; six slots remain explicitly vacant."
            ),
        },
        "database": {
            "live_path": relative(DB),
            "live_sha256_at_finalization": sha256_file(DB),
            "pre_execution_snapshot_sha256": pre_db_expected,
            "post_execution_snapshot": post_db,
        },
        "production_gate": read_json(
            MANIFESTS / "production-evidence-2026-08-05.json"
        ),
        "input_hashes": {relative(path): sha256_file(path) for path in input_paths},
        "outputs": {
            relative(path): {
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in output_paths
        },
        "code": {
            "repository": str(REPO),
            "repository_commit": repository_head,
            "harness_path": "code/medrag_eval/",
            "hashes": code_hashes,
        },
        "validation": {
            "frozen_ledger_rows": 264,
            "unique_frozen_cell_keys": 264,
            "adjusted_rows": 6000,
            "unique_adjusted_cell_keys": 6000,
            "adjusted_questions": 500,
            "unique_adjusted_source_keys": 500,
            "unique_normalized_stems": 500,
            "active_catalog_questions_primary_plus_reserve": 514,
            "active_reserve_questions": 14,
            "historical_reserve_slots": 20,
            "vacant_reserve_slots_pending_qa": 6,
            "exact_database_input_matches": 6000,
            "scores_per_logical_cell": 1,
            "condition_b_exact_two_field_swaps": 500,
            "database_integrity": "ok",
            "tracked_changes_outside_replacement_workspace": [],
            "spreadsheet_workbook": {
                "status": "BLOCKED_REQUIRED_ARTIFACT_TOOL_RUNTIME_UNAVAILABLE",
                "note": (
                    "No adjusted XLSX was authored. The canonical pre-replacement "
                    "workbook is not represented as an adjusted output."
                ),
            },
            "secrets_written": False,
        },
        "methodology_notes": [
            "The adjusted result replaces 22 questions; it does not reinterpret or recover their old cells.",
            "All 264 replacement cells use frozen QA-approved inputs and the original provider protocol.",
            "Rejected first attempts remain attempts only; no response without a parsed answer was scored.",
            "TailScale B was outside the authorized design and was not called.",
        ],
    }
    write_json(FINAL_MANIFEST, manifest)

    write_checksums(output_paths + [FINAL_MANIFEST], OUTPUT_CHECKSUMS)
    package_files = [
        path
        for path in HERE.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and not path.name.endswith(("-wal", "-shm"))
        and path not in {ROOT_CHECKSUMS, ALL_CHECKSUMS}
    ]
    write_checksums(package_files, ALL_CHECKSUMS)
    write_checksums(package_files + [ALL_CHECKSUMS], ROOT_CHECKSUMS)

    print(
        json.dumps(
            {
                "status": manifest["status"],
                "scope": manifest["scope"],
                "replacement_attempts": 266,
                "recovered_first_attempts": 2,
                "paired_openrouter": paired_summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
