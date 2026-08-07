"""Builder C — run-ready importer sheets for the Experiment C 2-fake/50-50 baseline.

Reads baseline.json (built by build_baseline.py, NOT modified here) and emits 4
single-sheet workbooks under run/ whose ACTIVE sheet satisfies the harness importer
contract (code/medrag_eval/excel_io.py REQUIRED_COLUMNS):

  question_id, region, year, specialty, exam_part, question_number, question_text,
  option_a, option_b, option_c, option_d, correct_letter, correct_option_text,
  flags, page_in_exam_pdf, source_exam_pdf, source_answer_key_pdf

One row per PRIMARY question (100 rows), question_id = base_question_id.

Three extra columns are appended AFTER the required set: `cluster`, `fabricated_entity`,
`variant_id`. The importer only reads columns it needs (code/medrag_eval/excel_io.py
_required_column_indexes keys off REQUIRED_COLUMNS and ignores anything else in the
header row), so these are inert for import purposes but let the flip-rate /
cluster-robust analysis step (RUN.md) read `cluster` straight off the workbook instead
of re-deriving it — the medrag_eval DB schema has no cluster column, and question_id is
the only bridge back to baseline.json.

Output: run/expC-bm-control.xlsx, run/expC-bm-altered.xlsx, run/expC-an-control.xlsx,
run/expC-an-altered.xlsx.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).resolve().parent
BASELINE_JSON = HERE / "baseline.json"
RUN_DIR = HERE / "run"

REQUIRED_COLUMNS = [
    "question_id",
    "region",
    "year",
    "specialty",
    "exam_part",
    "question_number",
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_letter",
    "correct_option_text",
    "flags",
    "page_in_exam_pdf",
    "source_exam_pdf",
    "source_answer_key_pdf",
]
EXTRA_COLUMNS = ["cluster", "fabricated_entity", "variant_id"]
HEADER = REQUIRED_COLUMNS + EXTRA_COLUMNS

ARM_FILE_PREFIX = {"BM": "expC-bm", "AN": "expC-an"}
CONDITION_TEXT_FIELD = {"control": "control_question_text", "altered": "altered_question_text"}


def build_row(record: dict, condition: str) -> list:
    question_text = record[CONDITION_TEXT_FIELD[condition]]
    row = {
        "question_id": record["base_question_id"],
        "region": record["region"],
        "year": record["year"],
        "specialty": record["specialty"],
        "exam_part": record["exam_part"],
        "question_number": record["question_number"],
        "question_text": question_text,
        "option_a": record["option_a"],
        "option_b": record["option_b"],
        "option_c": record["option_c"],
        "option_d": record["option_d"],
        "correct_letter": record["correct_letter"],
        "correct_option_text": record["correct_option_text"],
        "flags": record["flags"],
        "page_in_exam_pdf": record["page_in_exam_pdf"],
        "source_exam_pdf": record["source_exam_pdf"],
        "source_answer_key_pdf": record["source_answer_key_pdf"],
        "cluster": record["cluster"],
        "fabricated_entity": record["fabricated_entity"],
        "variant_id": record["variant_id"],
    }
    assert row["correct_option_text"] == row[f"option_{row['correct_letter']}"], (
        f"correct_option_text mismatch for {row['question_id']}"
    )
    return [row[col] for col in HEADER]


def write_workbook(records: list[dict], condition: str, out_path: Path) -> int:
    wb = Workbook()
    sheet = wb.active
    sheet.title = "questions"
    sheet.append(HEADER)
    seen_ids: set[str] = set()
    n = 0
    for record in records:
        assert record["pool_role"] == "PRIMARY", f"non-PRIMARY row leaked in: {record['base_question_id']}"
        qid = record["base_question_id"]
        assert qid not in seen_ids, f"duplicate question_id in output: {qid}"
        seen_ids.add(qid)
        sheet.append(build_row(record, condition))
        n += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return n


def main() -> int:
    with BASELINE_JSON.open(encoding="utf-8") as fh:
        baseline = json.load(fh)

    total_written = {}
    for arm, prefix in ARM_FILE_PREFIX.items():
        primary = baseline["arms"][arm]["primary"]
        if len(primary) != 100:
            raise SystemExit(f"{arm}: expected 100 PRIMARY rows, found {len(primary)}")
        for condition in ("control", "altered"):
            out_path = RUN_DIR / f"{prefix}-{condition}.xlsx"
            count = write_workbook(primary, condition, out_path)
            total_written[out_path.name] = count
            print(f"wrote {out_path} rows={count}")

    print(json.dumps(total_written, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
