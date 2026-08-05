#!/usr/bin/env python3
"""Retry only unresolved logical calls named in the frozen retry manifest."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from medrag_eval import db
from medrag_eval.config import Settings
from medrag_eval.prompting import render_benchmark_prompt
from medrag_eval.providers import GIFT_MCQ_PROMPT_ID, get_provider
from medrag_eval.runner import PlannedCall, _ProgressTracker, _close_all_thread_conns, _execute_call


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "runs" / "ab520-gapfill-2026-08-04.sqlite"
DEFAULT_MANIFEST = ROOT / "manifests" / "retry-targets-pre-retry.csv"


@dataclass(frozen=True)
class Target:
    cell_key: str
    failure_class: str
    experiment_id: int
    logical_call_id: int
    prompt_hashes: tuple[str, str]
    call: PlannedCall


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--failure-class", action="append", default=[])
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--exclude-question-id", action="append", default=[])
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def manifest_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    with args.manifest.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    provider = db.normalize_provider(args.provider)
    selected = [
        row
        for row in rows
        if db.normalize_provider(row["provider"]) == provider
        and row["model"] == args.model
        and (not args.failure_class or row["failure_class"] in args.failure_class)
        and (not args.question_id or row["question_id"] in args.question_id)
        and row["question_id"] not in args.exclude_question_id
    ]
    if not selected:
        raise SystemExit("No retry targets matched the requested filters")
    keys = [row["cell_key"] for row in selected]
    if len(keys) != len(set(keys)):
        raise SystemExit("Retry manifest contains duplicate selected cell keys")
    return selected


def resolve_targets(path: Path, rows: list[dict[str, str]]) -> tuple[list[Target], int]:
    targets: list[Target] = []
    skipped_scored = 0
    with db.connect(path) as conn:
        for row in rows:
            provider = db.normalize_provider(row["provider"])
            record = conn.execute(
                """
                SELECT e.id AS experiment_id, q.id AS question_pk,
                       lc.id AS logical_call_id, lc.prompt_version,
                       lc.system_prompt_sha256, lc.user_prompt_sha256,
                       (SELECT COUNT(*) FROM scores s WHERE s.logical_call_id = lc.id) AS score_count
                FROM experiments e
                JOIN questions q ON q.dataset_id = e.dataset_id
                JOIN logical_calls lc
                  ON lc.experiment_id = e.id AND lc.question_id = q.id
                WHERE e.name = ? AND q.question_id = ? AND lc.provider = ?
                  AND lc.model = ? AND lc.run_index = ?
                """,
                (
                    row["result_experiment"],
                    row["question_id"],
                    provider,
                    row["model"],
                    int(row["run_index"]),
                ),
            ).fetchone()
            if record is None:
                raise SystemExit(f"Logical call not found: {row['cell_key']}")
            if int(record["score_count"]):
                skipped_scored += 1
                continue
            question = db.get_question_by_pk(conn, int(record["question_pk"]))
            prompt = render_benchmark_prompt(
                question,
                provider=provider,
                prompt_version=str(record["prompt_version"]),
            )
            hashes = (prompt.system_sha256, prompt.user_sha256)
            stored = (
                str(record["system_prompt_sha256"]),
                str(record["user_prompt_sha256"]),
            )
            if hashes != stored:
                raise SystemExit(f"Prompt hash mismatch before retry: {row['cell_key']}")
            targets.append(
                Target(
                    cell_key=row["cell_key"],
                    failure_class=row["failure_class"],
                    experiment_id=int(record["experiment_id"]),
                    logical_call_id=int(record["logical_call_id"]),
                    prompt_hashes=hashes,
                    call=PlannedCall(
                        question_pk=int(record["question_pk"]),
                        question_id=row["question_id"],
                        provider=provider,
                        model=row["model"],
                        run_index=int(row["run_index"]),
                        prompt_version=str(record["prompt_version"]),
                    ),
                )
            )
    return targets, skipped_scored


def inspect_outcome(path: Path, target: Target, attempts_before: int) -> dict[str, Any]:
    with db.connect(path) as conn:
        logical = conn.execute(
            "SELECT system_prompt_sha256, user_prompt_sha256 FROM logical_calls WHERE id = ?",
            (target.logical_call_id,),
        ).fetchone()
        if logical is None or tuple(logical) != target.prompt_hashes:
            raise RuntimeError(f"Prompt hash changed during retry: {target.cell_key}")
        latest = conn.execute(
            """
            SELECT status_code, latency_ms, finish_reason, error_type, error_message
            FROM provider_attempts WHERE logical_call_id = ?
            ORDER BY attempt_index DESC LIMIT 1
            """,
            (target.logical_call_id,),
        ).fetchone()
        attempt_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM provider_attempts WHERE logical_call_id = ?",
                (target.logical_call_id,),
            ).fetchone()[0]
        )
        score_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM scores WHERE logical_call_id = ?",
                (target.logical_call_id,),
            ).fetchone()[0]
        )
        integrity = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    if attempt_count <= attempts_before:
        raise RuntimeError(f"Retry stored no provider attempt: {target.cell_key}")
    if score_count > 1:
        raise RuntimeError(f"Recovered cell has multiple scores: {target.cell_key}")
    return {
        "cell_key": target.cell_key,
        "failure_class": target.failure_class,
        "attempt_delta": attempt_count - attempts_before,
        "score_count": score_count,
        "recovered": score_count == 1,
        "status_code": latest["status_code"] if latest else None,
        "latency_ms": latest["latency_ms"] if latest else None,
        "finish_reason": latest["finish_reason"] if latest else None,
        "error_type": latest["error_type"] if latest else None,
        "error_message": latest["error_message"] if latest else None,
        "integrity": integrity,
    }


def abort_reason(outcome: dict[str, Any], unexpected_5xx: int) -> tuple[str | None, int]:
    status = outcome["status_code"]
    error = str(outcome["error_type"] or "").lower()
    message = str(outcome["error_message"] or "").lower()
    if outcome["integrity"] != "ok":
        return "database_integrity_failure", unexpected_5xx
    if status in {401, 403} or error == "auth_error":
        return "authentication_failure", unexpected_5xx
    if status == 200 and not outcome["recovered"]:
        return "partial_or_unparseable_response", unexpected_5xx
    if status == 429 or "circuit" in error or "circuit" in message:
        return "rate_limit_or_circuit_open", unexpected_5xx
    expected_5xx = status == 500 and outcome["failure_class"] in {
        "tailscale_http500_correlated_overlength_exact_input",
        "tailscale_glm_server_error_150s_after_retries",
    }
    unexpected_5xx = unexpected_5xx + 1 if status and 500 <= status < 600 and not expected_5xx else 0
    if unexpected_5xx >= 2:
        return "sustained_unexpected_5xx", unexpected_5xx
    return None, unexpected_5xx


def main() -> None:
    args = parse_args()
    if not 1 <= args.max_concurrency <= 10:
        raise SystemExit("--max-concurrency must be between 1 and 10")
    rows = manifest_rows(args)
    targets, skipped_scored = resolve_targets(args.db, rows)
    plan = {
        "selected": len(rows),
        "queued": len(targets),
        "skipped_already_scored": skipped_scored,
        "provider": db.normalize_provider(args.provider),
        "model": args.model,
        "max_concurrency": args.max_concurrency,
        "execute": args.execute,
    }
    print(json.dumps({"plan": plan}, sort_keys=True), flush=True)
    if not args.execute or not targets:
        return

    adapter = get_provider(args.provider, settings=Settings.from_env())
    auth = adapter.check_auth()
    if auth.error_type is not None or auth.status_code not in {200}:
        adapter.close()
        raise SystemExit("Provider authentication/health check failed; no calls issued")

    attempts_before: dict[int, int] = {}
    with db.connect(args.db) as conn:
        for target in targets:
            attempts_before[target.logical_call_id] = int(
                conn.execute(
                    "SELECT COUNT(*) FROM provider_attempts WHERE logical_call_id = ?",
                    (target.logical_call_id,),
                ).fetchone()[0]
            )

    tracker = _ProgressTracker(skipped_count=0, total=len(targets))
    pending = iter(targets)
    futures: dict[Future[None], Target] = {}
    outcomes: list[dict[str, Any]] = []
    stop_reason: str | None = None
    unexpected_5xx = 0

    def submit(pool: ThreadPoolExecutor) -> bool:
        if stop_reason is not None:
            return False
        try:
            target = next(pending)
        except StopIteration:
            return False
        future = pool.submit(
            _execute_call,
            db_path=args.db,
            experiment_id=target.experiment_id,
            call=target.call,
            adapter=adapter,
            tracker=tracker,
            temperature=0,
            no_retry=False,
            tailscale_prompt_id=(
                GIFT_MCQ_PROMPT_ID
                if target.call.provider == "tailscale_medical_rag"
                else None
            ),
            tailscale_top_k=None,
        )
        futures[future] = target
        return True

    try:
        with ThreadPoolExecutor(max_workers=args.max_concurrency) as pool:
            for _ in range(args.max_concurrency):
                if not submit(pool):
                    break
            while futures:
                done, _ = wait(set(futures), return_when=FIRST_COMPLETED)
                for future in done:
                    target = futures.pop(future)
                    future.result()
                    outcome = inspect_outcome(
                        args.db, target, attempts_before[target.logical_call_id]
                    )
                    outcomes.append(outcome)
                    print(json.dumps({"outcome": outcome}, sort_keys=True), flush=True)
                    reason, unexpected_5xx = abort_reason(outcome, unexpected_5xx)
                    if reason and stop_reason is None:
                        stop_reason = reason
                if stop_reason is None:
                    for _ in done:
                        submit(pool)
        print(
            json.dumps(
                {
                    "summary": {
                        "executed": len(outcomes),
                        "recovered": sum(item["recovered"] for item in outcomes),
                        "residual": sum(not item["recovered"] for item in outcomes),
                        "not_started_after_abort": len(targets) - len(outcomes),
                        "stop_reason": stop_reason,
                    }
                },
                sort_keys=True,
            )
        )
    finally:
        _close_all_thread_conns()
        adapter.close()


if __name__ == "__main__":
    main()
