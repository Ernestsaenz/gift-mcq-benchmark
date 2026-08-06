"""Freeze and initialize the run-2/run-3 incorrect-cell replication package."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "code"))

from medrag_eval import db  # noqa: E402
from medrag_eval.prompting import BENCHMARK_PROMPT_VERSION, render_benchmark_prompt  # noqa: E402


SOURCE = (
    REPO
    / "data/experiment-4-aug-26/replacements/ab520-replacement-22-2026-08-04"
    / "exports/benchmark-6000-cell-results-adjusted.csv"
)
DB_PATH = HERE / "runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite"
PRE_SNAPSHOT = HERE / "manifests/ab520-incorrect-cell-triplicates.pre-execution.sqlite"
LEDGER = HERE / "manifests/frozen-replicate-cell-ledger.csv"
PREPARED = HERE / "manifests/preparation-summary.json"
PROMPT_VERSION = BENCHMARK_PROMPT_VERSION
EXPECTED_SOURCE_SHA256 = "ce91b3f3eb90cd0b125a170a6f0a0a967c02d63da17cfa97161e62f739c4b721"

MODELS = (
    "google/gemini-3.6-flash",
    "google/gemma-4-26b-a4b-it",
    "qwen/qwen3.6-35b-a3b",
    "z-ai/glm-5.2",
)
ARM_SPECS = {
    "openrouter_A": {
        "provider": "openrouter",
        "condition": "A",
        "dataset": "ab520_adjusted_A_replication",
        "experiment": "ab520_incorrect_triplicates_or_A_20260805",
        "expected_wrong": 203,
    },
    "openrouter_B": {
        "provider": "openrouter",
        "condition": "B",
        "dataset": "ab520_adjusted_B_replication",
        "experiment": "ab520_incorrect_triplicates_or_B_20260805",
        "expected_wrong": 532,
    },
    "tailscale_A": {
        "provider": "tailscale_medical_rag",
        "condition": "A",
        "dataset": "ab520_adjusted_A_replication",
        "experiment": "ab520_incorrect_triplicates_ts_A_20260805",
        "expected_wrong": 163,
    },
}
RAW_FIELDS = (
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_letter",
    "correct_option_text",
)
QUESTION_FIELDS = (
    "question_id",
    "source_key",
    "region",
    "year",
    "specialty",
    "exam_part",
    "question_number",
    *RAW_FIELDS,
    "flags",
    "page_in_exam_pdf",
    "source_exam_pdf",
    "source_answer_key_pdf",
    "origin",
    "content_sha256",
    "raw_form_sha256",
)
LEDGER_FIELDS = (
    "target_key",
    "arm",
    "provider",
    "condition",
    "dataset",
    "experiment",
    "question_id",
    "source_key",
    "model",
    "run_index",
    "prompt_version",
    "run1_cell_key",
    "run1_selected_letter",
    "run1_correct_letter",
    "run1_request_sha256",
    "run1_response_sha256",
    "run1_result_database",
    "run1_result_experiment",
    "input_fields_sha256",
    "system_prompt_sha256",
    "user_prompt_sha256",
    "source_content_sha256",
    "source_raw_form_sha256",
    "status",
)


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fields_hash(row: Any) -> str:
    payload = bytearray()
    for field in RAW_FIELDS:
        raw = str(row[field]).encode("utf-8")
        payload.extend(len(raw).to_bytes(8, "big"))
        payload.extend(raw)
    return hashlib.sha256(payload).hexdigest()


def load_source() -> list[dict[str, str]]:
    source_sha = sha256_file(SOURCE)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise SystemExit(f"Source SHA-256 changed: {source_sha}")
    with SOURCE.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 6000:
        raise SystemExit(f"Expected 6,000 source cells, found {len(rows)}")
    if {row["arm"] for row in rows} != set(ARM_SPECS):
        raise SystemExit("Source arms differ from the authorized three-arm design")
    if {row["model"] for row in rows} != set(MODELS):
        raise SystemExit("Source models differ from the frozen four-model design")
    if {row["run_index"] for row in rows} != {"1"}:
        raise SystemExit("Source must contain run index 1 only")
    for row in rows:
        if row["final_execution_status"] != "scored":
            raise SystemExit(f"Unscored source cell: {row['cell_key']}")
        if row["parse_status"] not in {"ok", "ok_conflict"}:
            raise SystemExit(f"Invalid source parse: {row['cell_key']}")
        if row["strict_correct"] not in {"0", "1"}:
            raise SystemExit(f"Invalid source score: {row['cell_key']}")
        if row["prompt_version"] != PROMPT_VERSION:
            raise SystemExit(f"Prompt-version drift: {row['cell_key']}")
        if row["exact_input_match_db"].upper() != "TRUE":
            raise SystemExit(f"Source input was not exact-matched: {row['cell_key']}")
    return rows


def canonical_questions(rows: list[dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["arm"], row["source_key"])].append(row)

    result: dict[str, dict[str, dict[str, str]]] = {arm: {} for arm in ARM_SPECS}
    for (arm, source_key), group in grouped.items():
        if len(group) != 4 or {row["model"] for row in group} != set(MODELS):
            raise SystemExit(f"Incomplete four-model source group: {arm} {source_key}")
        for field in QUESTION_FIELDS:
            if len({row[field] for row in group}) != 1:
                raise SystemExit(f"Question field differs across models: {arm} {source_key} {field}")
        result[arm][source_key] = group[0]

    for arm, questions in result.items():
        if len(questions) != 500:
            raise SystemExit(f"Expected 500 questions in {arm}, found {len(questions)}")
        if len({row["question_id"] for row in questions.values()}) != 500:
            raise SystemExit(f"Question IDs are not unique in {arm}")

    a_keys = set(result["openrouter_A"])
    if set(result["tailscale_A"]) != a_keys:
        raise SystemExit("OpenRouter A and TailScale A question sets differ")
    for source_key in a_keys:
        left = result["openrouter_A"][source_key]
        right = result["tailscale_A"][source_key]
        if any(left[field] != right[field] for field in QUESTION_FIELDS):
            raise SystemExit(f"Condition-A forms differ by provider: {source_key}")
    return result


def question_record(row: dict[str, str]) -> dict[str, Any]:
    source_metadata = {field: row[field] for field in QUESTION_FIELDS}
    source_metadata["source_results_path"] = str(SOURCE.relative_to(REPO))
    source_metadata["source_run1_cell_key"] = row["cell_key"]
    return {
        "question_id": row["question_id"],
        "region": row["region"] or None,
        "year": int(row["year"]),
        "specialty": row["specialty"] or None,
        "exam_part": row["exam_part"] or None,
        "question_number": int(row["question_number"]),
        "question_text": row["question_text"],
        "option_a": row["option_a"],
        "option_b": row["option_b"],
        "option_c": row["option_c"],
        "option_d": row["option_d"],
        "correct_letter": row["correct_letter"],
        "correct_option_text": row["correct_option_text"],
        "source_row_json": source_metadata,
    }


def write_question_inputs(questions: dict[str, dict[str, dict[str, str]]]) -> dict[str, Path]:
    (HERE / "inputs").mkdir(parents=True, exist_ok=True)
    paths = {
        "A": HERE / "inputs/adjusted-500-condition-A.csv",
        "B": HERE / "inputs/adjusted-500-condition-B.csv",
    }
    for condition, arm in (("A", "openrouter_A"), ("B", "openrouter_B")):
        rows = sorted(questions[arm].values(), key=lambda row: (int(row["source_excel_row"]), row["source_key"]))
        with paths[condition].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=QUESTION_FIELDS)
            writer.writeheader()
            writer.writerows({field: row[field] for field in QUESTION_FIELDS} for row in rows)
    return paths


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    if DB_PATH.exists() or PRE_SNAPSHOT.exists() or LEDGER.exists():
        raise SystemExit("Replication package is already initialized; refusing to overwrite it")

    rows = load_source()
    questions = canonical_questions(rows)
    input_paths = write_question_inputs(questions)
    wrong_rows = [row for row in rows if row["strict_correct"] == "0"]
    wrong_counts = Counter(row["arm"] for row in wrong_rows)
    for arm, spec in ARM_SPECS.items():
        if wrong_counts[arm] != spec["expected_wrong"]:
            raise SystemExit(
                f"Wrong-cell count changed for {arm}: {wrong_counts[arm]} != {spec['expected_wrong']}"
            )
    if len(wrong_rows) != 898:
        raise SystemExit(f"Expected 898 wrong run-1 cells, found {len(wrong_rows)}")

    (HERE / "runs").mkdir(parents=True, exist_ok=True)
    (HERE / "manifests").mkdir(parents=True, exist_ok=True)
    (HERE / "logs").mkdir(parents=True, exist_ok=True)
    (HERE / "invocations").mkdir(parents=True, exist_ok=True)
    (HERE / "exports").mkdir(parents=True, exist_ok=True)
    temp_db = DB_PATH.with_suffix(".sqlite.preparing")
    if temp_db.exists():
        temp_db.unlink()
    db.init_db(temp_db)

    ledger_rows: list[dict[str, str]] = []
    with db.connect(temp_db) as conn:
        datasets: dict[str, Any] = {}
        for condition, arm in (("A", "openrouter_A"), ("B", "openrouter_B")):
            name = ARM_SPECS[arm]["dataset"]
            source_path = input_paths[condition]
            dataset = db.upsert_dataset(
                conn,
                name=name,
                source_xlsx_path=str(source_path.relative_to(REPO)),
                row_count=500,
            )
            records = [
                question_record(row)
                for row in sorted(
                    questions[arm].values(),
                    key=lambda item: (int(item["source_excel_row"]), item["source_key"]),
                )
            ]
            db.replace_questions(conn, dataset, records)
            datasets[name] = dataset

        experiments: dict[str, Any] = {}
        for arm, spec in ARM_SPECS.items():
            config = {
                "scope": "strict_incorrect_run1_cells_only",
                "source_results_sha256": EXPECTED_SOURCE_SHA256,
                "source_run_index": 1,
                "replicate_run_indices": [2, 3],
                "condition": spec["condition"],
                "tailscale_prompt_id": 13 if arm == "tailscale_A" else None,
                "tailscale_top_k": None,
            }
            experiments[arm] = db.create_experiment(
                conn,
                name=spec["experiment"],
                dataset_id=datasets[spec["dataset"]],
                prompt_version=PROMPT_VERSION,
                config_json=config,
            )

        for source in sorted(
            wrong_rows,
            key=lambda row: (row["arm"], row["model"], row["source_key"]),
        ):
            arm = source["arm"]
            spec = ARM_SPECS[arm]
            dataset = datasets[spec["dataset"]]
            question = conn.execute(
                "SELECT * FROM questions WHERE dataset_id = ? AND question_id = ?",
                (dataset["id"], source["question_id"]),
            ).fetchone()
            if question is None:
                raise SystemExit(f"Prepared question missing: {source['cell_key']}")
            if fields_hash(question) != fields_hash(source):
                raise SystemExit(f"Prepared input hash mismatch: {source['cell_key']}")
            prompt = render_benchmark_prompt(
                question,
                provider=spec["provider"],
                prompt_version=PROMPT_VERSION,
            )
            if len(prompt.user_prompt) != int(source["request_user_content_char_count"]):
                raise SystemExit(f"Rendered prompt length drift: {source['cell_key']}")
            for run_index in (2, 3):
                db.get_or_create_logical_call(
                    conn,
                    experiment_id=experiments[arm],
                    question_pk=question,
                    provider=spec["provider"],
                    model=source["model"],
                    run_index=run_index,
                    prompt_version=PROMPT_VERSION,
                    system_prompt_sha256=prompt.system_sha256,
                    user_prompt_sha256=prompt.user_sha256,
                )
                target_key = "|".join(
                    (arm, source["source_key"], source["model"], str(run_index))
                )
                ledger_rows.append(
                    {
                        "target_key": target_key,
                        "arm": arm,
                        "provider": spec["provider"],
                        "condition": spec["condition"],
                        "dataset": spec["dataset"],
                        "experiment": spec["experiment"],
                        "question_id": source["question_id"],
                        "source_key": source["source_key"],
                        "model": source["model"],
                        "run_index": str(run_index),
                        "prompt_version": PROMPT_VERSION,
                        "run1_cell_key": source["cell_key"],
                        "run1_selected_letter": source["selected_letter"],
                        "run1_correct_letter": source["correct_letter"],
                        "run1_request_sha256": source["request_sha256"],
                        "run1_response_sha256": source["response_sha256"],
                        "run1_result_database": source["result_database"],
                        "run1_result_experiment": source["result_experiment"],
                        "input_fields_sha256": fields_hash(question),
                        "system_prompt_sha256": prompt.system_sha256,
                        "user_prompt_sha256": prompt.user_sha256,
                        "source_content_sha256": source["content_sha256"],
                        "source_raw_form_sha256": source["raw_form_sha256"],
                        "status": "READY_NOT_RUN",
                    }
                )

        logical_count = int(conn.execute("SELECT COUNT(*) FROM logical_calls").fetchone()[0])
        attempt_count = int(conn.execute("SELECT COUNT(*) FROM provider_attempts").fetchone()[0])
        score_count = int(conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0])
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    if (logical_count, attempt_count, score_count, integrity) != (1796, 0, 0, "ok"):
        raise SystemExit(
            f"Invalid prepared database: logical={logical_count}, attempts={attempt_count}, "
            f"scores={score_count}, integrity={integrity}"
        )
    if len(ledger_rows) != 1796 or len({row["target_key"] for row in ledger_rows}) != 1796:
        raise SystemExit("Prepared ledger is not exactly 1,796 unique targets")

    with LEDGER.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(ledger_rows)

    temp_db.replace(DB_PATH)
    shutil.copy2(DB_PATH, PRE_SNAPSHOT)
    prepared = {
        "status": "READY_NOT_RUN",
        "prepared_at_utc": now_iso(),
        "scope": "two new independent runs for every strict-incorrect run-1 cell",
        "source_results": str(SOURCE.relative_to(REPO)),
        "source_results_sha256": EXPECTED_SOURCE_SHA256,
        "repository_commit": git_commit(),
        "prompt_version": PROMPT_VERSION,
        "temperature": 0,
        "top_p": 1,
        "tailscale_prompt_id": 13,
        "wrong_run1_cells": len(wrong_rows),
        "target_replicate_calls": len(ledger_rows),
        "target_counts_by_arm": dict(sorted(Counter(row["arm"] for row in ledger_rows).items())),
        "target_counts_by_arm_model": {
            f"{arm}|{model}": count
            for (arm, model), count in sorted(
                Counter((row["arm"], row["model"]) for row in ledger_rows).items()
            )
        },
        "database": str(DB_PATH.relative_to(REPO)),
        "database_sha256": sha256_file(DB_PATH),
        "pre_execution_snapshot": str(PRE_SNAPSHOT.relative_to(REPO)),
        "pre_execution_snapshot_sha256": sha256_file(PRE_SNAPSHOT),
        "ledger": str(LEDGER.relative_to(REPO)),
        "ledger_sha256": sha256_file(LEDGER),
        "input_files": {
            condition: {
                "path": str(path.relative_to(REPO)),
                "sha256": sha256_file(path),
            }
            for condition, path in input_paths.items()
        },
        "production_gate": {
            "required_commit": "29af9a4f1581f6ffc1921a44d96a2a2cbe36a84e",
            "deployment_run": 30629235833,
            "latest_main_deployment_verified": True,
            "authenticated_openrouter_check": "passed",
            "authenticated_tailscale_check": "passed",
        },
    }
    PREPARED.write_text(
        json.dumps(prepared, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (HERE / "STATUS.md").write_text(
        "# Replication status\n\n"
        f"Updated: {prepared['prepared_at_utc']}\n\n"
        "Status: **READY_NOT_RUN**\n\n"
        "The frozen queue contains 1,796 run-2/run-3 calls derived from 898 "
        "strict-incorrect run-1 cells. No provider call has been issued from this workspace.\n",
        encoding="utf-8",
    )
    print(json.dumps(prepared, indent=2))


if __name__ == "__main__":
    main()
