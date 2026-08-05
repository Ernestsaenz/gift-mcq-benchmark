"""Prepare redacted, deterministic assignments for replacement-cohort QA.

The emitted packets deliberately exclude ranks, prior verdicts, manual
adjudications, and reviewer identities from earlier phases. Reviewers receive
only the pinned question, official-source provenance, and exact A/B simulation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
DOSSIER = Path("/private/tmp/ab182-q5i3oBTb")
QA_ROOT = HERE / "protocol-qa"
INPUTS = QA_ROOT / "inputs"
PROTOCOL_VERSION = "ab182-readonly-v1"
QA_DATE = "2026-08-05"
REVIEWERS = {
    "sourcing": "RSRC22",
    "qa1": "RQA22A",
    "qa2": "RQA22B",
}
MAX_BATCH = 10

PACKET_FIELDS = (
    "as_of_date",
    "assembled_context_and_stem_sha256",
    "b_simulation",
    "candidate_id",
    "context_chunks",
    "context_separator",
    "corpus_sha256",
    "exam_part",
    "formal_type",
    "protocol_version",
    "provenance",
    "question_number",
    "raw_field_hashes",
    "raw_fields",
    "raw_fields_hash",
    "region",
    "sheet",
    "source_key",
    "source_row",
    "year",
)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def redact(packet: dict) -> dict:
    redacted = {field: packet[field] for field in PACKET_FIELDS}
    assert set(redacted) == set(PACKET_FIELDS)
    assert "frozen_rank" not in redacted
    assert "review_instructions" not in redacted
    return redacted


def batches(rows: list[dict]) -> list[list[dict]]:
    return [rows[index : index + MAX_BATCH] for index in range(0, len(rows), MAX_BATCH)]


def main() -> None:
    INPUTS.mkdir(parents=True, exist_ok=True)
    for phase in ("calibration", "sourcing", "qa1", "qa2"):
        (QA_ROOT / "reviews" / phase).mkdir(parents=True, exist_ok=True)

    selected = read_jsonl(HERE / "selected-source-packets.jsonl")
    manifest = json.loads((HERE / "replacement-manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "PROVISIONAL_PENDING_PROTOCOL_QA"
    assert len(selected) == len({row["candidate_id"] for row in selected}) == 22
    selected_by_id = {row["candidate_id"]: row for row in selected}
    assert set(selected_by_id) == {row["candidate_id"] for row in manifest["replacements"]}

    ordered = sorted(
        (redact(row) for row in selected),
        key=lambda row: (
            row["region"],
            row["year"],
            row["exam_part"],
            row["question_number"],
            row["candidate_id"],
        ),
    )
    formal_sourcing_ids = {
        row["candidate_id"]
        for row in manifest["replacements"]
        if row["prior_sourcing_review"] is not None
    }
    sourcing_rows = [row for row in ordered if row["candidate_id"] not in formal_sourcing_ids]
    assert len(formal_sourcing_ids) == 12
    assert len(sourcing_rows) == 10

    calibration = [redact(row) for row in read_jsonl(DOSSIER / "calibration-packets.jsonl")]
    assert len(calibration) == 8
    write_jsonl(INPUTS / "calibration.jsonl", calibration)

    outputs: dict[str, list[dict]] = {}
    for role, rows in (("sourcing", sourcing_rows), ("qa1", ordered), ("qa2", ordered)):
        outputs[role] = []
        for index, batch in enumerate(batches(rows), start=1):
            path = INPUTS / f"{role}-batch-{index:02d}.jsonl"
            write_jsonl(path, batch)
            outputs[role].append(
                {
                    "batch": index,
                    "path": str(path.relative_to(HERE)),
                    "count": len(batch),
                    "candidate_ids": [row["candidate_id"] for row in batch],
                    "sha256": sha256_file(path),
                }
            )

    assignment_manifest = {
        "protocol_version": PROTOCOL_VERSION,
        "qa_date": QA_DATE,
        "selection_status_at_assignment": manifest["status"],
        "reviewers": REVIEWERS,
        "reviewer_independence": {
            "qa1_ne_qa2": REVIEWERS["qa1"] != REVIEWERS["qa2"],
            "prior_reviews_excluded_from_inputs": True,
            "manual_adjudications_excluded_from_inputs": True,
            "ranks_excluded_from_inputs": True,
        },
        "calibration": {
            "path": str((INPUTS / "calibration.jsonl").relative_to(HERE)),
            "count": len(calibration),
            "sha256": sha256_file(INPUTS / "calibration.jsonl"),
        },
        "assignments": outputs,
    }
    (INPUTS / "assignment-manifest.json").write_text(
        json.dumps(assignment_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "calibration_fixtures": len(calibration),
        "formal_sourcing_assignments": len(sourcing_rows),
        "qa1_assignments": len(ordered),
        "qa2_assignments": len(ordered),
        "max_batch_size": max(
            entry["count"]
            for role in outputs.values()
            for entry in role
        ),
        "reviewers": REVIEWERS,
    }, indent=2))


if __name__ == "__main__":
    main()
