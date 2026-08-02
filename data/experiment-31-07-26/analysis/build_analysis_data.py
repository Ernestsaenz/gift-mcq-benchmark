"""Deterministically rebuild the analysis tables from the run database.

    uv run python data/experiment-31-07-26/analysis/build_analysis_data.py

Reads  : data/experiment-31-07-26/experiment.sqlite  (read-only)
Writes : paired_clean.json   OpenRouter, condition A vs condition B, one row per (item, model)
         cross_arm_A.json    GIFT vs OpenRouter, condition A only
         gift_coverage.json  the items GIFT completed on all four models
         dataset_meta.json   every exclusion rule, with counts

Written because the first version of these tables was produced by an ad-hoc script that was never
committed, so no third party could regenerate them. Every exclusion is declared here as data.

Two traps this file avoids deliberately:
  * NEVER select experiments with `name LIKE 'expA%'` -- that silently merges the OpenRouter and
    GIFT arms into one number.
  * Reach the scored attempt via scores -> parsed_answers.provider_attempt_id -> provider_attempts.
    Joining provider_attempts straight to logical_calls also picks up superseded retry attempts,
    which would overweight exactly the items that needed retrying.
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "experiment.sqlite"

EXP = {
    "or_a": "expA_or_310726",
    "or_b": "expB_or_310726",
    "gift_a": "expA_gift_310726",
    "gift_b": "expB_gift_310726",
}
DS_A = "balanced_a_310726"
DS_B = "balanced_b_310726"

# --------------------------------------------------------------------------- exclusions
# Out-of-domain: administrative, employment and data-protection law. Correct Spanish, correct
# answer keys -- simply not digestive-system medicine, so they measure something the benchmark
# does not claim to measure.
OUT_OF_DOMAIN = [
    "b205",
    "b213",
    "b238",
    "b293",
    "b331",
    "b341",
    "b343",
    "b361",
    "b378",
    "b385",
    "b391",
    "b396",
    "b401",
    "b407",
    "b420",
    "b430",
    "b433",
    "b445",
    "b451",
]
# Adjudicated wrong or unanswerable source answer keys (defects in the original exams).
KEY_DEFECT = ["b178", "b197", "b496"]

ITEM_DEFECT = sorted(set(OUT_OF_DOMAIN) | set(KEY_DEFECT), key=lambda s: int(s[1:]))

# Construction defect in condition B: the inserted string reads "Ninguna de las respuestas
# ANTERIORES es correcta." Where the key is option (a) it is the FIRST option and has no
# antecedent. Excluded from the A-vs-B contrast only; the items are fine in condition A.
NOTA_POSITION_RULE = "correct_letter == 'a'"

NEGATED = re.compile(
    r"(\bfalsa\b|\bfalso\b|incorrect|\bexcepto\b|\bsalvo\b|err[oó]nea"
    r"|no es (cierta|correcta|verdadera))",
    re.I,
)


def connect() -> sqlite3.Connection:
    wal = Path(f"{DB}-wal")
    if wal.exists() and wal.stat().st_size:
        raise RuntimeError(f"refusing a database with a non-empty WAL: {wal}")
    conn = sqlite3.connect(f"{DB.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("BEGIN")
    return conn


def validate_db_integrity(conn: sqlite3.Connection) -> None:
    if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("SQLite integrity_check failed")
    foreign_key_errors = list(conn.execute("PRAGMA foreign_key_check"))
    if foreign_key_errors:
        raise RuntimeError(f"SQLite foreign-key violations: {foreign_key_errors[:5]}")
    duplicate_scores = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT logical_call_id FROM scores GROUP BY logical_call_id HAVING COUNT(*) != 1
        )
        """
    ).fetchone()[0]
    if duplicate_scores:
        raise RuntimeError(f"logical calls with duplicate scores: {duplicate_scores}")
    lineage_errors = conn.execute(
        """
        SELECT COUNT(*)
        FROM scores s
        LEFT JOIN parsed_answers p ON p.id=s.parsed_answer_id
        LEFT JOIN provider_attempts a ON a.id=p.provider_attempt_id
        WHERE p.id IS NULL OR a.id IS NULL
           OR p.logical_call_id != s.logical_call_id
           OR a.logical_call_id != p.logical_call_id
        """
    ).fetchone()[0]
    if lineage_errors:
        raise RuntimeError(f"score/parse/attempt lineage violations: {lineage_errors}")


def questions(conn, dataset: str) -> dict:
    return {
        q["question_id"]: q
        for q in conn.execute(
            "SELECT * FROM questions WHERE dataset_id=(SELECT id FROM datasets WHERE name=?)",
            (dataset,),
        )
    }


def scored_cells(conn, experiment: str) -> dict:
    """One row per (question_id, model) for the attempt that was actually scored."""
    rows = conn.execute(
        """
        SELECT q.question_id AS qid, lc.model AS model, s.strict_correct AS correct,
               p.selected_letter AS selected, a.latency_ms AS latency_ms,
               a.completion_tokens AS tokens, a.response_body AS body
        FROM scores s
        JOIN logical_calls lc      ON lc.id = s.logical_call_id
        JOIN questions q           ON q.id  = lc.question_id
        JOIN parsed_answers p      ON p.id  = s.parsed_answer_id
                                  AND p.logical_call_id = s.logical_call_id
        JOIN provider_attempts a   ON a.id  = p.provider_attempt_id
                                  AND a.logical_call_id = p.logical_call_id
        JOIN experiments e         ON e.id  = lc.experiment_id
        WHERE e.name = ?
        ORDER BY q.question_id, lc.model
        """,
        (experiment,),
    )
    out = {}
    for r in rows:
        if r["correct"] is None:  # unparsed -> excluded, never scored as incorrect
            continue
        try:
            backend = (json.loads(r["body"]) or {}).get("provider")
        except Exception:
            backend = None
        key = (r["qid"], r["model"])
        if key in out:
            raise RuntimeError(f"duplicate scored cell in {experiment}: {key}")
        out[key] = {
            "correct": int(r["correct"]),
            "selected": r["selected"],
            "latency_ms": r["latency_ms"],
            "tokens": r["tokens"],
            "backend": backend,
        }
    return out


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_run_configuration(conn: sqlite3.Connection) -> dict:
    names = tuple(EXP.values())
    placeholders = ",".join("?" for _ in names)
    prompt_versions = {
        row[0]
        for row in conn.execute(
            f"SELECT DISTINCT lc.prompt_version FROM logical_calls lc "
            f"JOIN experiments e ON e.id=lc.experiment_id WHERE e.name IN ({placeholders})",
            names,
        )
    }
    run_indices = {
        row[0]
        for row in conn.execute(
            f"SELECT DISTINCT lc.run_index FROM logical_calls lc "
            f"JOIN experiments e ON e.id=lc.experiment_id WHERE e.name IN ({placeholders})",
            names,
        )
    }
    temperatures = {
        row[0]
        for row in conn.execute(
            f"SELECT DISTINCT json_extract(a.request_json, '$.temperature') "
            f"FROM provider_attempts a JOIN logical_calls lc ON lc.id=a.logical_call_id "
            f"JOIN experiments e ON e.id=lc.experiment_id WHERE e.name IN ({placeholders})",
            names,
        )
    }
    models = sorted(
        {
            row[0]
            for row in conn.execute(
                f"SELECT DISTINCT lc.model FROM logical_calls lc "
                f"JOIN experiments e ON e.id=lc.experiment_id WHERE e.name IN ({placeholders})",
                names,
            )
        }
    )
    if prompt_versions != {"mcq_es_v4"}:
        raise RuntimeError(f"unexpected prompt versions: {sorted(prompt_versions)}")
    if run_indices != {1}:
        raise RuntimeError(f"unexpected run indices: {sorted(run_indices)}")
    if temperatures != {0}:
        raise RuntimeError(f"unexpected temperatures: {sorted(temperatures, key=str)}")
    if len(models) != 4:
        raise RuntimeError(f"expected four models, found {models}")
    return {
        "runs_per_cell": 1,
        "temperature": 0,
        "prompt_version": "mcq_es_v4",
        "models": models,
    }


def experiment_status(
    conn: sqlite3.Connection, qa_count: int, qb_count: int, n_models: int
) -> dict:
    expected = {
        EXP["or_a"]: qa_count * n_models,
        EXP["or_b"]: qb_count * n_models,
        EXP["gift_a"]: qa_count * n_models,
        EXP["gift_b"]: qb_count * n_models,
    }
    result = {}
    for name, planned in expected.items():
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT lc.id) AS logical_calls,
                   COUNT(DISTINCT s.logical_call_id) AS scored_calls
            FROM experiments e
            LEFT JOIN logical_calls lc ON lc.experiment_id=e.id
            LEFT JOIN scores s ON s.logical_call_id=lc.id
            WHERE e.name=?
            """,
            (name,),
        ).fetchone()
        result[name] = {
            "planned_cells": planned,
            "logical_calls_created": row["logical_calls"],
            "scored_cells": row["scored_calls"],
            "logical_progress_fraction": row["logical_calls"] / planned,
            "scored_fraction": row["scored_calls"] / planned,
        }
    return result


def total_variation(a_values: list[str | None], b_values: list[str | None]) -> float:
    if not a_values or not b_values:
        return 0.0
    keys = set(a_values) | set(b_values)
    return 0.5 * sum(
        abs(a_values.count(key) / len(a_values) - b_values.count(key) / len(b_values))
        for key in keys
    )


def cluster_ids(qa: dict) -> dict:
    """Items sharing a prepended clinical narrative form one cluster; others are singletons."""
    key = {}
    for qid, q in qa.items():
        parts = q["question_text"].split("\n\n")
        key[qid] = parts[0][:120] if len(parts) > 1 else f"__solo__{qid}"
    index = {k: i for i, k in enumerate(sorted(set(key.values())))}
    return {qid: index[k] for qid, k in key.items()}


def item_fields(q, cluster) -> dict:
    return {
        "cluster": cluster,
        "region": q["region"],
        "year": q["year"],
        "exam_part": q["exam_part"],
        "correct_letter": q["correct_letter"],
        "qlen": len(q["question_text"]),
        "negated_stem": bool(NEGATED.search(q["question_text"].split("\n\n")[-1])),
        "has_context": "\n\n" in q["question_text"],
    }


def main() -> None:
    db_hash_before = file_hash(DB)
    conn = connect()
    validate_db_integrity(conn)
    qa = questions(conn, DS_A)
    qb = questions(conn, DS_B)
    if len(qa) != 474 or len(qb) != 423:
        raise RuntimeError(f"unexpected dataset sizes: A={len(qa)}, B={len(qb)}")
    config = validate_run_configuration(conn)
    clusters = cluster_ids(qa)

    or_a = scored_cells(conn, EXP["or_a"])
    or_b = scored_cells(conn, EXP["or_b"])
    gift_a = scored_cells(conn, EXP["gift_a"])

    # ---------------------------------------------------------------- A vs B (OpenRouter)
    paired = []
    for key in sorted(set(or_a) & set(or_b), key=lambda k: (int(k[0][1:]), k[1])):
        qid, model = key
        q = qa[qid]
        a, b = or_a[key], or_b[key]
        rec = {
            "question_id": qid,
            "model": model,
            **item_fields(q, clusters[qid]),
            "A_correct": a["correct"],
            "B_correct": b["correct"],
            "A_selected": a["selected"],
            "B_selected": b["selected"],
            "A_tokens": a["tokens"],
            "B_tokens": b["tokens"],
            "A_latency_ms": a["latency_ms"],
            "B_latency_ms": b["latency_ms"],
            "A_backend": a["backend"],
            "B_backend": b["backend"],
            "same_backend": bool(a["backend"] and a["backend"] == b["backend"]),
            "excl_item_defect": qid in ITEM_DEFECT,
            "excl_nota_position_a": q["correct_letter"] == "a",
        }
        rec["analysis_include"] = (
            not rec["excl_item_defect"] and not rec["excl_nota_position_a"]
        )
        paired.append(rec)
    # ---------------------------------------------------------------- GIFT coverage
    done = defaultdict(set)
    for qid, model in gift_a:
        done[model].add(qid)
    models = sorted(done)
    if models != config["models"]:
        raise RuntimeError(f"GIFT model coverage is incomplete: {models}")
    complete = set.intersection(*[done[m] for m in models]) if models else set()
    coverage = {
        "complete_all_models": sorted(complete, key=lambda s: int(s[1:])),
        "n_complete": len(complete),
        "per_model_completed": {m: len(done[m]) for m in models},
    }

    # ---------------------------------------------------------------- GIFT vs OpenRouter, cond. A
    cross = []
    for key in sorted(set(gift_a) & set(or_a), key=lambda k: (int(k[0][1:]), k[1])):
        qid, model = key
        if qid not in complete:  # keep only items every GIFT model finished
            continue
        q = qa[qid]
        g, o = gift_a[key], or_a[key]
        rec = {
            "question_id": qid,
            "model": model,
            **item_fields(q, clusters[qid]),
            "gift_correct": g["correct"],
            "or_correct": o["correct"],
            "gift_selected": g["selected"],
            "or_selected": o["selected"],
            "gift_latency_ms": g["latency_ms"],
            "or_latency_ms": o["latency_ms"],
            "gift_tokens": g["tokens"],
            "or_tokens": o["tokens"],
            "excl_item_defect": qid in ITEM_DEFECT,
        }
        rec["analysis_include"] = not rec["excl_item_defect"]
        cross.append(rec)
    inc_p = [r for r in paired if r["analysis_include"]]
    inc_c = [r for r in cross if r["analysis_include"]]
    covered_cells = [cell for key, cell in or_a.items() if key[0] in complete]
    uncovered_cells = [cell for key, cell in or_a.items() if key[0] not in complete]
    coverage_accuracy = {
        "openrouter_a_covered": sum(r["correct"] for r in covered_cells)
        / len(covered_cells),
        "openrouter_a_uncovered": sum(r["correct"] for r in uncovered_cells)
        / len(uncovered_cells),
    }
    backend_tv = {}
    for model in config["models"]:
        model_rows = [r for r in inc_p if r["model"] == model]
        backend_tv[model] = total_variation(
            [r["A_backend"] for r in model_rows],
            [r["B_backend"] for r in model_rows],
        )

    status = experiment_status(conn, len(qa), len(qb), len(config["models"]))
    conn.commit()
    conn.close()
    if file_hash(DB) != db_hash_before:
        raise RuntimeError(
            "experiment.sqlite changed while the analytical snapshot was read"
        )
    paired_text = json.dumps(paired, ensure_ascii=False)
    cross_text = json.dumps(cross, ensure_ascii=False)
    coverage_text = json.dumps(coverage, indent=1)

    source_files = {
        "source_workbook": DB.parent
        / "balanced-clinical-questionnaire-500-no-image.xlsx",
        "flat_a_workbook": DB.parent / "balanced-flat-A.xlsx",
        "flat_b_workbook": DB.parent / "balanced-flat-B.xlsx",
        "flatten_script": DB.parent / "flatten.py",
        "flatten_report": DB.parent / "flatten_report.json",
        "experiment_database": DB,
        "analysis_builder": Path(__file__).resolve(),
    }
    meta = {
        "export_version": "v3",
        "export_note": (
            "v3 preserves the v2 analytical population and fixes the scored-parse join and "
            "deterministic metadata generation. It supersedes all v1 result artifacts."
        ),
        "source_db": str(DB.name),
        "arm_ab": "openrouter",
        "runs_per_cell": config["runs_per_cell"],
        "temperature": config["temperature"],
        "prompt_version": config["prompt_version"],
        "experiments": EXP,
        "datasets": {"A": DS_A, "B": DS_B},
        "swap_string": "Ninguna de las respuestas anteriores es correcta.",
        "exclusions": {
            "out_of_domain_law": OUT_OF_DOMAIN,
            "adjudicated_key_defect": KEY_DEFECT,
            "nota_position_a": {
                "rule": NOTA_POSITION_RULE,
                "why": "inserted string says 'respuestas ANTERIORES' but occupies the FIRST slot",
                "scope": "A-vs-B contrast only",
            },
            "unparsed_cells": "dropped; never scored as incorrect",
        },
        "counts": {
            "ab_cells_all": len(paired),
            "ab_cells_analysis": len(inc_p),
            "ab_items_analysis": len({r["question_id"] for r in inc_p}),
            "ab_clusters_analysis": len({r["cluster"] for r in inc_p}),
            "declared_item_defects": len(ITEM_DEFECT),
            "item_defects_present_in_ab": len(
                {r["question_id"] for r in paired if r["excl_item_defect"]}
            ),
            "nota_position_a_items_in_ab": len(
                {r["question_id"] for r in paired if r["excl_nota_position_a"]}
            ),
            "cross_cells_analysis": len(inc_c),
            "cross_items_analysis": len({r["question_id"] for r in inc_c}),
            "cross_clusters_analysis": len({r["cluster"] for r in inc_c}),
            "gift_items_complete_all_models": len(complete),
            "models": config["models"],
        },
        "experiment_status": status,
        "coverage_diagnostics": {
            **coverage_accuracy,
            "difference_covered_minus_uncovered": (
                coverage_accuracy["openrouter_a_covered"]
                - coverage_accuracy["openrouter_a_uncovered"]
            ),
        },
        "backend_total_variation_a_vs_b": backend_tv,
        "caveats": [
            "GIFT experiment A is partial: logical-call creation reached 82.6% of planned cells, "
            "but only 73.0% produced scores. Coverage is a sequential prefix, not a random sample.",
            "GIFT experiment B was never run; there is no retrieval-arm A/B contrast.",
            "OpenRouter backend routing was not pinned and differed between arms. Use "
            "same_backend and backend_total_variation_a_vs_b to assess this confound.",
            "runs=1: no within-item variance, so per-item claims are unsupportable.",
            "Completion-token counts include the emitted answer text and are not a clean measure "
            "of deliberation across conditions.",
            "Latency is not directly comparable across asynchronous provider runs because serving "
            "throughput and routing changed.",
            "A cluster drawn repeatedly in a bootstrap must retain a draw index; regrouping only by "
            "question_id merges duplicate draws.",
        ],
        "superseded_v1_counts": {
            "ab_items": 325,
            "ab_cells": 1299,
            "ab_clusters": 208,
            "cross_items": 311,
            "cross_cells": 1244,
            "cross_clusters": 183,
        },
        "input_sha256": {
            label: file_hash(path) for label, path in source_files.items()
        },
    }

    with tempfile.TemporaryDirectory(prefix="analysis-build-", dir=HERE) as stage_name:
        stage = Path(stage_name)
        staged = {
            "paired_clean.json": paired_text,
            "cross_arm_A.json": cross_text,
            "gift_coverage.json": coverage_text,
        }
        for name, text in staged.items():
            (stage / name).write_text(text, encoding="utf-8")
        meta["output_sha256"] = {name: file_hash(stage / name) for name in staged}
        meta["output_md5"] = {name: file_hash(stage / name, "md5") for name in staged}
        (stage / "dataset_meta.json").write_text(
            json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        for name in (*staged, "dataset_meta.json"):
            os.replace(stage / name, HERE / name)

    print(json.dumps(meta["counts"], indent=1))
    for m in sorted({r["model"] for r in inc_p}):
        s = [r for r in inc_p if r["model"] == m]
        a = sum(r["A_correct"] for r in s)
        b = sum(r["B_correct"] for r in s)
        print(
            f"  {m:28} n={len(s):4} A={100 * a / len(s):5.1f}% B={100 * b / len(s):5.1f}% "
            f"delta={100 * (b - a) / len(s):+6.1f}pp"
        )


if __name__ == "__main__":
    main()
