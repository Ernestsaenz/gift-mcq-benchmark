"""Build the proposed 22-question replacement cohort without provider calls.

This script reads the canonical benchmark and pinned ab182 selection dossier,
then writes only inside this replacement subfolder. It intentionally emits CSV
and JSON rather than modifying the canonical benchmark or results database.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DOSSIER = Path("/private/tmp/ab182-q5i3oBTb")
CANONICAL_BENCHMARK = REPO / "data/experiment-4-aug-26/benchmark-500.json"
SOURCE_WORKBOOK = Path(
    "/Users/ernestsaenz/Programming/gift-project-compile/second-project/"
    "workbook-repairs-2026-07-30/outputs/all-regions-aparato-digestivo.corrected.xlsx"
)
EXPECTED_CORPUS_SHA256 = "18f6becd4e51f1b9ef6a5a8ab68421e905cfe2584ec32a0e303b76f3cacf1e46"
SWAP = "Ninguna de las respuestas anteriores es correcta."
SPECIALTY = "aparato-digestivo"
GIFT_LIMIT = 5000
GIFT_TARGET = 4500

MODELS = [
    "google/gemini-3.6-flash",
    "google/gemma-4-26b-a4b-it",
    "qwen/qwen3.6-35b-a3b",
    "z-ai/glm-5.2",
]
ARMS = [
    {
        "arm": "openrouter_A",
        "provider": "openrouter",
        "condition": "A",
        "dataset_name": "aug26_replacement22_A",
        "planned_experiment_id": "ab520_replacement22_or_A_20260804",
        "tailscale_prompt_id": "",
    },
    {
        "arm": "openrouter_B",
        "provider": "openrouter",
        "condition": "B",
        "dataset_name": "aug26_replacement22_B",
        "planned_experiment_id": "ab520_replacement22_or_B_20260804",
        "tailscale_prompt_id": "",
    },
    {
        "arm": "tailscale_A",
        "provider": "tailscale_medical_rag",
        "condition": "A",
        "dataset_name": "aug26_replacement22_A",
        "planned_experiment_id": "ab520_replacement22_ts_A_20260804",
        "tailscale_prompt_id": 13,
    },
]

REGION_DISPLAY = {
    "andalucia": "Andalucía",
    "aragon": "Aragón",
    "castilla-la-mancha": "Castilla-La Mancha",
    "castilla-y-leon": "Castilla y León",
    "comunidad-de-madrid": "Comunidad de Madrid",
    "comunitat-valenciana": "Comunitat Valenciana",
    "galicia": "Galicia",
    "illes-balears": "Illes Balears",
    "la-rioja": "La Rioja",
    "navarra": "Navarra",
    "region-de-murcia": "Región de Murcia",
}

FLAT_COLUMNS = [
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
    "content_sha256",
    "source_key",
    "selection_score",
    "context_ids",
    "origin",
    "negated_stem",
    "candidate_id",
    "replaces_question_id",
    "failure_group",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value).casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip(" .:;,¿?¡!\t\n")


STOPWORDS = {
    "ante", "con", "cual", "cuál", "de", "del", "el", "en", "entre", "es",
    "esta", "este", "la", "las", "lo", "los", "mas", "más", "para", "por",
    "que", "se", "senala", "señala", "senale", "señale", "sobre", "una", "uno",
}


def token_set(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_text(value))
        if len(token) > 2 and token not in STOPWORDS
    }


def jaccard(left: str, right: str) -> float:
    a, b = token_set(left), token_set(right)
    return len(a & b) / len(a | b) if a or b else 0.0


def packet_text(packet: dict) -> str:
    raw = packet["raw_fields"]
    return " ".join([raw["question_text"], *(raw[f"option_{letter}"] for letter in "abcd")])


def benchmark_text(question: dict) -> str:
    return " ".join([question["stem"], *(question["A"]["options"].values())])


def gift_user_message(question_id: str, stem: str, options: dict[str, str]) -> str:
    return (
        f"question_id: {question_id}\n\n{stem}\n\n"
        f"a) {options['a']}\n"
        f"b) {options['b']}\n"
        f"c) {options['c']}\n"
        f"d) {options['d']}"
    ).strip()


def flat_row(packet: dict, mapping: dict, condition: str) -> dict:
    raw = packet["raw_fields"]
    provenance = packet["provenance"]
    letter = raw["correct_letter"].lower()
    options = {key: raw[f"option_{key}"] for key in "abcd"}
    correct_text = raw["correct_option_text"]
    if condition == "B":
        options[letter] = SWAP
        correct_text = SWAP
    row = {
        "question_id": mapping["replacement_id"],
        "region": REGION_DISPLAY.get(packet["region"], packet["region"]),
        "year": packet["year"],
        "specialty": SPECIALTY,
        "exam_part": packet["exam_part"],
        "question_number": packet["question_number"],
        "question_text": raw["question_text"],
        **{f"option_{key}": options[key] for key in "abcd"},
        "correct_letter": letter,
        "correct_option_text": correct_text,
        "flags": "",
        "page_in_exam_pdf": provenance.get("exam_page", ""),
        "source_exam_pdf": provenance.get("workbook_exam_name", ""),
        "source_answer_key_pdf": provenance.get("workbook_key_name", ""),
        "content_sha256": packet["raw_fields_hash"],
        "source_key": packet["source_key"],
        "selection_score": "",
        "context_ids": "",
        "origin": "replacement22_2026-08-04",
        "negated_stem": False,
        "candidate_id": packet["candidate_id"],
        "replaces_question_id": mapping["replaces_question_id"],
        "failure_group": mapping["failure_group"],
    }
    return {column: row.get(column, "") for column in FLAT_COLUMNS}


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    spec = json.loads((HERE / "selection-spec.json").read_text(encoding="utf-8"))
    manual = json.loads((HERE / "manual-adjudications.json").read_text(encoding="utf-8"))
    mappings = spec["mappings"]
    candidate_ids = [item["candidate_id"] for item in mappings]
    old_ids = [item["replaces_question_id"] for item in mappings]

    packets = {item["candidate_id"]: item for item in read_jsonl(DOSSIER / "candidate-packets.jsonl")}
    sourcing = {item["candidate_id"]: item for item in read_jsonl(DOSSIER / "sourcing-reviews.jsonl")}
    qa_records = read_jsonl(DOSSIER / "qa-reviews-initial.jsonl") + read_jsonl(
        DOSSIER / "qa-reviews-expansion.jsonl"
    )
    selected_qa = [item for item in qa_records if item.get("candidate_id") in candidate_ids]
    adverse_qa = [item for item in selected_qa if item.get("verdict") != "PASS"]
    assert not adverse_qa, [(item.get("candidate_id"), item.get("verdict")) for item in adverse_qa]

    negation_labels = json.loads((DOSSIER / "negstem-labels.json").read_text(encoding="utf-8"))
    canonical = json.loads(CANONICAL_BENCHMARK.read_text(encoding="utf-8"))
    canonical_by_id = {item["question_id"]: item for item in canonical}
    assert len(canonical) == 500 and all(item in canonical_by_id for item in old_ids)
    assert len(mappings) == len(set(candidate_ids)) == len(set(old_ids)) == 22

    corpus_sha = sha256_file(SOURCE_WORKBOOK)
    assert corpus_sha == EXPECTED_CORPUS_SHA256
    canonical_source_keys = {item["source_key"] for item in canonical}
    selected_source_keys: list[str] = []
    selected_packets: list[dict] = []
    rows_a: list[dict] = []
    rows_b: list[dict] = []
    replacements: list[dict] = []
    pdf_hashes: dict[str, str] = {}

    reserve_ids = {item["candidate_id"] for item in read_jsonl(DOSSIER / "reserve-packets.jsonl")}
    fully_passing_ids = {item["candidate_id"] for item in read_jsonl(DOSSIER / "fully-passing-pool.jsonl")}

    for mapping in mappings:
        packet = packets[mapping["candidate_id"]]
        selected_packets.append(packet)
        raw = packet["raw_fields"]
        letter = raw["correct_letter"].lower()
        original = canonical_by_id[mapping["replaces_question_id"]]
        assert letter == original["correct_letter"], (mapping, letter, original["correct_letter"])
        assert packet["corpus_sha256"] == corpus_sha
        assert not packet.get("context_chunks")
        assert raw["correct_option_text"] == raw[f"option_{letter}"]
        normalized_options = [normalized_text(raw[f"option_{key}"]) for key in "abcd"]
        assert len(set(normalized_options)) == 4
        assert not any(
            re.search(r"\b(ningun[ao]?|todas? las anteriores|todos? los anteriores)\b", option)
            for option in normalized_options
        )
        label = negation_labels.get(packet["candidate_id"])
        manual_record = manual["candidates"].get(packet["candidate_id"])
        assert label is False or (manual_record and manual_record["non_negated"] is True)
        source_review = sourcing.get(packet["candidate_id"])
        if source_review is None:
            assert manual_record and manual_record["a_validity"] == manual_record["b_validity"] == "PASS"
        else:
            assert source_review["verdict"] == "PASS"
            assert source_review["a_validity"] == source_review["b_validity"] == "PASS"

        provenance = packet["provenance"]
        for path_key, hash_key in (("exam_pdf_path", "exam_pdf_sha256"), ("key_pdf_path", "key_pdf_sha256")):
            pdf_path = Path(provenance[path_key])
            assert pdf_path.is_file(), pdf_path
            actual_hash = pdf_hashes.setdefault(str(pdf_path), sha256_file(pdf_path))
            assert actual_hash == provenance[hash_key], (pdf_path, actual_hash, provenance[hash_key])

        assert packet["source_key"] not in canonical_source_keys
        selected_source_keys.append(packet["source_key"])
        row_a = flat_row(packet, mapping, "A")
        row_b = flat_row(packet, mapping, "B")
        rows_a.append(row_a)
        rows_b.append(row_b)

        changed = [
            column
            for column in ("question_text", "option_a", "option_b", "option_c", "option_d", "correct_letter", "correct_option_text")
            if row_a[column] != row_b[column]
        ]
        assert changed == [f"option_{letter}", "correct_option_text"], (mapping, changed)

        options_a = {key: row_a[f"option_{key}"] for key in "abcd"}
        options_b = {key: row_b[f"option_{key}"] for key in "abcd"}
        gift_a = gift_user_message(mapping["replacement_id"], row_a["question_text"], options_a)
        gift_b = gift_user_message(mapping["replacement_id"], row_b["question_text"], options_b)
        assert len(gift_a) <= GIFT_TARGET and len(gift_b) <= GIFT_TARGET

        prior_passes = [item for item in selected_qa if item.get("candidate_id") == packet["candidate_id"]]
        if packet["candidate_id"] in reserve_ids:
            provenance_class = "unrun_reserve_promotion"
        elif packet["candidate_id"] in fully_passing_ids:
            provenance_class = "unrun_fully_passing_backfill"
        else:
            provenance_class = "newly_screened_unused_candidate"

        replacements.append(
            {
                **mapping,
                "old_correct_letter": original["correct_letter"],
                "new_correct_letter": letter,
                "source_key": packet["source_key"],
                "source_row": packet["source_row"],
                "region": REGION_DISPLAY.get(packet["region"], packet["region"]),
                "year": packet["year"],
                "exam_part": packet["exam_part"],
                "question_number": packet["question_number"],
                "provenance_class": provenance_class,
                "question": {
                    "stem": raw["question_text"],
                    "A": {"options": options_a, "correct_option_text": row_a["correct_option_text"]},
                    "B": {"options": options_b, "correct_option_text": row_b["correct_option_text"]},
                },
                "hashes": {
                    "raw_fields_sha256": packet["raw_fields_hash"],
                    "question_text_sha256": packet["raw_field_hashes"]["question_text"],
                    "condition_A_gift_user_sha256": sha256_text(gift_a),
                    "condition_B_gift_user_sha256": sha256_text(gift_b),
                },
                "gift_user_lengths": {
                    "condition_A_characters": len(gift_a),
                    "condition_A_utf8_bytes": len(gift_a.encode("utf-8")),
                    "condition_B_characters": len(gift_b),
                    "condition_B_utf8_bytes": len(gift_b.encode("utf-8")),
                },
                "official_source": provenance,
                "prior_sourcing_review": source_review,
                "prior_blinded_qa_pass_count": len(prior_passes),
                "manual_research_adjudication": manual_record,
            }
        )

    assert len(set(selected_source_keys)) == 22
    letter_distribution = Counter(row["correct_letter"] for row in rows_a)
    assert letter_distribution == Counter({"b": 7, "c": 7, "d": 8})

    normalized_stems = [normalized_text(row["question_text"]) for row in rows_a]
    assert len(set(normalized_stems)) == 22
    retained = [item for item in canonical if item["question_id"] not in set(old_ids)]
    retained_stems = {normalized_text(item["stem"]): item["question_id"] for item in retained}
    assert not (set(normalized_stems) & set(retained_stems))

    similarity_rows = []
    for mapping, packet in zip(mappings, selected_packets):
        matches = sorted(
            (
                (jaccard(packet_text(packet), benchmark_text(question)), question["question_id"], question["source_key"])
                for question in retained
            ),
            reverse=True,
        )
        score, question_id, source_key = matches[0]
        similarity_rows.append(
            {
                "replacement_id": mapping["replacement_id"],
                "candidate_id": packet["candidate_id"],
                "max_token_jaccard": round(score, 6),
                "nearest_retained_question_id": question_id,
                "nearest_retained_source_key": source_key,
            }
        )
    assert max(item["max_token_jaccard"] for item in similarity_rows) < 0.30

    replacement_by_old = {item["replaces_question_id"]: item for item in replacements}
    proposed_benchmark = []
    for question in canonical:
        replacement = replacement_by_old.get(question["question_id"])
        if not replacement:
            proposed_benchmark.append(question)
            continue
        proposed_benchmark.append(
            {
                "question_id": replacement["replacement_id"],
                "candidate_id": replacement["candidate_id"],
                "replaces_question_id": replacement["replaces_question_id"],
                "replacement_status": "PROVISIONAL_PENDING_PROTOCOL_QA",
                "origin": "replacement22_2026-08-04",
                "negated_stem": False,
                "region": replacement["region"],
                "year": replacement["year"],
                "exam_part": replacement["exam_part"],
                "source_key": replacement["source_key"],
                "correct_letter": replacement["new_correct_letter"],
                "stem": replacement["question"]["stem"],
                "A": replacement["question"]["A"],
                "B": replacement["question"]["B"],
            }
        )
    assert len(proposed_benchmark) == 500
    assert all(item not in {question["question_id"] for question in proposed_benchmark} for item in old_ids)

    run_matrix = []
    for mapping in mappings:
        for arm in ARMS:
            for model in MODELS:
                run_matrix.append(
                    {
                        "replacement_id": mapping["replacement_id"],
                        "replaces_question_id": mapping["replaces_question_id"],
                        "candidate_id": mapping["candidate_id"],
                        **arm,
                        "model": model,
                        "prompt_version": "mcq_es_v4",
                        "temperature": 0,
                        "runs": 1,
                        "status": "NOT_RUN_REQUIRES_FINAL_PROTOCOL_QA",
                    }
                )
    assert len(run_matrix) == 264

    try:
        repository_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        repository_commit = "unavailable"

    source_files = {
        str(SOURCE_WORKBOOK): corpus_sha,
        str(CANONICAL_BENCHMARK.relative_to(REPO)): sha256_file(CANONICAL_BENCHMARK),
        str((DOSSIER / "candidate-packets.jsonl")): sha256_file(DOSSIER / "candidate-packets.jsonl"),
        str((DOSSIER / "sourcing-reviews.jsonl")): sha256_file(DOSSIER / "sourcing-reviews.jsonl"),
        str((DOSSIER / "qa-reviews-initial.jsonl")): sha256_file(DOSSIER / "qa-reviews-initial.jsonl"),
        str((DOSSIER / "qa-reviews-expansion.jsonl")): sha256_file(DOSSIER / "qa-reviews-expansion.jsonl"),
        str((DOSSIER / "negstem-labels.json")): sha256_file(DOSSIER / "negstem-labels.json"),
        "code/medrag_eval/prompting.py": sha256_file(REPO / "code/medrag_eval/prompting.py"),
    }

    manifest = {
        "artifact_version": "ab520-replacement-22-package-v1",
        "selection_date": "2026-08-04",
        "status": "PROVISIONAL_PENDING_PROTOCOL_QA",
        "execution_status": "NOT_RUN",
        "interpretation": (
            "This is a new matched replacement cohort. It does not recover or overwrite the original "
            "22 questions or any original unresolved cell."
        ),
        "scope": {
            "replacement_questions": 22,
            "ambiguous_or_model_sensitive_questions": 6,
            "overlength_questions": 16,
            "historical_overlength_failures": 64,
            "planned_arms": [item["arm"] for item in ARMS],
            "models": MODELS,
            "planned_cells": len(run_matrix),
            "excluded_arm": "tailscale_B",
        },
        "condition_B_contract": {
            "replacement_text": SWAP,
            "changed_fields_per_question": ["option_{correct_letter}", "correct_option_text"],
            "correct_letter_unchanged": True,
        },
        "repository_commit": repository_commit,
        "source_files_sha256": source_files,
        "replacements": replacements,
        "validation": {
            "candidate_count": len(replacements),
            "letter_distribution": dict(sorted(letter_distribution.items())),
            "context_free_count": sum(not packet.get("context_chunks") for packet in selected_packets),
            "source_key_collisions_with_canonical_500": 0,
            "exact_stem_collisions_with_retained_478": 0,
            "known_adverse_qa_records": len(adverse_qa),
            "gift_target_characters": GIFT_TARGET,
            "gift_hard_limit_characters": GIFT_LIMIT,
            "max_gift_A_characters": max(item["gift_user_lengths"]["condition_A_characters"] for item in replacements),
            "max_gift_B_characters": max(item["gift_user_lengths"]["condition_B_characters"] for item in replacements),
            "max_retained_token_jaccard": max(item["max_token_jaccard"] for item in similarity_rows),
            "all_machine_assertions_passed": True,
        },
    }

    write_csv(HERE / "replacement-22-A.csv", rows_a, FLAT_COLUMNS)
    write_csv(HERE / "replacement-22-B.csv", rows_b, FLAT_COLUMNS)
    write_csv(HERE / "run-matrix-264.csv", run_matrix, list(run_matrix[0]))
    (HERE / "replacement-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "benchmark-500-with-provisional-replacements.json").write_text(
        json.dumps(proposed_benchmark, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "similarity-audit.json").write_text(
        json.dumps(similarity_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (HERE / "selected-source-packets.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in selected_packets),
        encoding="utf-8",
    )
    selected_sourcing = [sourcing[item] for item in candidate_ids if item in sourcing]
    (HERE / "selected-sourcing-reviews.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in selected_sourcing),
        encoding="utf-8",
    )
    (HERE / "selected-prior-qa-reviews.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in selected_qa),
        encoding="utf-8",
    )

    generated = sorted(
        path
        for path in HERE.iterdir()
        if path.is_file() and path.name != "checksums.sha256"
    )
    (HERE / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in generated), encoding="utf-8"
    )
    print(json.dumps(manifest["validation"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
