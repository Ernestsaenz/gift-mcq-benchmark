from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Literal

from openpyxl import Workbook

from . import db


def _validate_experiment_name(name: str) -> None:
    # Reject anything that would let f"{name}_summary.csv" escape the runs/ directory.
    # Caller-supplied --out is intentionally not validated; that is the operator's choice.
    if not name or "/" in name or "\\" in name or "\x00" in name or ".." in name:
        raise ValueError(
            f"Invalid experiment_name {name!r}: must not contain '/', '\\', NUL, or '..'"
        )


def default_export_path(experiment_name: str, fmt: str, raw: bool = False) -> Path:
    _validate_experiment_name(experiment_name)
    suffix = "raw" if raw else "summary"
    return Path("runs") / f"{experiment_name}_{suffix}.{fmt}"


def export_summary(db_path, *, experiment_name: str, fmt: Literal["csv", "xlsx"], out: str | Path | None = None) -> Path:
    output = Path(out) if out else default_export_path(experiment_name, fmt)
    output.parent.mkdir(parents=True, exist_ok=True)
    with db.connect(db_path) as conn:
        rows = db.summary_rows(conn, experiment_name)
    if fmt == "csv":
        _write_csv(output, rows)
    elif fmt == "xlsx":
        _write_xlsx(output, rows)
    else:
        raise ValueError(f"Unsupported summary export format: {fmt}")
    return output


def export_raw(db_path, *, experiment_name: str, out: str | Path | None = None) -> Path:
    output = Path(out) if out else default_export_path(experiment_name, "jsonl", raw=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with db.connect(db_path) as conn:
        rows = db.raw_attempt_rows(conn, experiment_name)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
    return output


def _write_csv(path: Path, rows) -> None:
    fieldnames = list(rows[0].keys()) if rows else db.SUMMARY_COLUMNS
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _write_xlsx(path: Path, rows) -> None:
    fieldnames = list(rows[0].keys()) if rows else db.SUMMARY_COLUMNS
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "summary"
    sheet.append(fieldnames)
    for row in rows:
        values = dict(row)
        sheet.append([values.get(field) for field in fieldnames])
    workbook.save(path)
