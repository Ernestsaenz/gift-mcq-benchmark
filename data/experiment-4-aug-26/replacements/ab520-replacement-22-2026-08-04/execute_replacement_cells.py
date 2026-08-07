"""Execute only cells in the frozen replacement ledger with fail-fast guards."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "code"))

from medrag_eval import db  # noqa: E402
from medrag_eval.config import Settings  # noqa: E402
from medrag_eval.prompting import render_benchmark_prompt  # noqa: E402
from medrag_eval.providers import GIFT_MCQ_PROMPT_ID, get_provider  # noqa: E402
from medrag_eval.runner import (  # noqa: E402
    PlannedCall,
    _ProgressTracker,
    _close_all_thread_conns,
    _execute_call,
)


DEFAULT_DB = HERE / "runs/ab520-replacement22-2026-08-05.sqlite"
DEFAULT_LEDGER = HERE / "manifests/frozen-replacement-cell-ledger.csv"
INVOCATIONS = HERE / "manifests/invocations"
RAW_FIELDS = (
    "question_text",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_letter",
    "correct_option_text",
)


@dataclass(frozen=True)
class Target:
    ledger: dict[str, str]
    experiment_id: int
    logical_call_id: int
    prompt_hashes: tuple[str, str]
    call: PlannedCall


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def input_fields_hash(question: Any) -> str:
    payload = bytearray()
    for field in RAW_FIELDS:
        raw = str(question[field]).encode("utf-8")
        payload.extend(len(raw).to_bytes(8, "big"))
        payload.extend(raw)
    return hashlib.sha256(payload).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", required=True, choices=("openrouter_A", "openrouter_B", "tailscale_A"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--abort-on-first-5xx", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--invocation-id")
    parser.add_argument("--log-path", default="")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    return parser.parse_args()


def read_ledger(path: Path, args: argparse.Namespace) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    selected = [
        row
        for row in rows
        if row["arm"] == args.arm
        and row["model"] == args.model
        and (not args.question_id or row["replacement_id"] in args.question_id)
    ]
    if not selected:
        raise SystemExit("No frozen replacement cells matched the requested filters")
    if len({row["cell_key"] for row in selected}) != len(selected):
        raise SystemExit("Frozen ledger contains duplicate selected cell keys")
    if args.question_id and {row["replacement_id"] for row in selected} != set(args.question_id):
        raise SystemExit("One or more requested question IDs are absent from the frozen ledger")
    if {row["status"] for row in selected} - {"READY_NOT_RUN", "RUNNING", "SCORED"}:
        raise SystemExit("Selected ledger rows are not execution-authorized")
    return selected


def expected_config(provider: str) -> dict[str, Any]:
    return {
        "limit": None,
        "offset": 0,
        "question_id": None,
        "tailscale_prompt_id": GIFT_MCQ_PROMPT_ID if provider == "tailscale_medical_rag" else None,
        "tailscale_top_k": None,
    }


def resolve_targets(
    path: Path, rows: list[dict[str, str]], *, create_logical_calls: bool
) -> tuple[list[Target], int]:
    targets: list[Target] = []
    skipped_scored = 0
    with db.connect(path) as conn:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise SystemExit(f"Database integrity gate failed: {integrity}")
        for row in rows:
            dataset = db.get_dataset(conn, row["dataset"])
            if dataset is None:
                raise SystemExit(f"Dataset not imported: {row['dataset']}")
            experiment = db.get_experiment(conn, row["experiment"])
            if experiment is None:
                raise SystemExit(
                    f"Experiment dry-run is missing: {row['experiment']}; run the frozen dry-run first"
                )
            if int(experiment["dataset_id"]) != int(dataset["id"]):
                raise SystemExit(f"Experiment/dataset mismatch: {row['experiment']}")
            if experiment["prompt_version"] != row["prompt_version"]:
                raise SystemExit(f"Prompt-version mismatch: {row['experiment']}")
            if json.loads(experiment["config_json"]) != expected_config(row["provider"]):
                raise SystemExit(f"Experiment-config mismatch: {row['experiment']}")
            question = conn.execute(
                "SELECT * FROM questions WHERE dataset_id = ? AND question_id = ?",
                (dataset["id"], row["replacement_id"]),
            ).fetchone()
            if question is None:
                raise SystemExit(f"Question absent from imported dataset: {row['replacement_id']}")
            if input_fields_hash(question) != row["input_fields_sha256"]:
                raise SystemExit(f"Input hash mismatch: {row['cell_key']}")
            prompt = render_benchmark_prompt(
                question,
                provider=row["provider"],
                prompt_version=row["prompt_version"],
            )
            hashes = (prompt.system_sha256, prompt.user_sha256)
            if hashes != (row["system_prompt_sha256"], row["user_prompt_sha256"]):
                raise SystemExit(f"Prompt hash mismatch: {row['cell_key']}")

            logical = conn.execute(
                """
                SELECT lc.* FROM logical_calls lc
                WHERE lc.experiment_id = ? AND lc.question_id = ? AND lc.provider = ?
                  AND lc.model = ? AND lc.run_index = 1 AND lc.prompt_version = ?
                """,
                (
                    experiment["id"],
                    question["id"],
                    row["provider"],
                    row["model"],
                    row["prompt_version"],
                ),
            ).fetchone()
            if logical is None and create_logical_calls:
                logical = db.get_or_create_logical_call(
                    conn,
                    experiment_id=experiment["id"],
                    question_pk=question["id"],
                    provider=row["provider"],
                    model=row["model"],
                    run_index=1,
                    prompt_version=row["prompt_version"],
                    system_prompt_sha256=prompt.system_sha256,
                    user_prompt_sha256=prompt.user_sha256,
                )
            if logical is not None:
                stored_hashes = (
                    str(logical["system_prompt_sha256"]),
                    str(logical["user_prompt_sha256"]),
                )
                if stored_hashes != hashes:
                    raise SystemExit(f"Stored prompt hash mismatch: {row['cell_key']}")
                score_count = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM scores WHERE logical_call_id = ?",
                        (logical["id"],),
                    ).fetchone()[0]
                )
                if score_count > 1:
                    raise SystemExit(f"Multiple scores already exist: {row['cell_key']}")
                if score_count == 1:
                    skipped_scored += 1
                    continue
            if not create_logical_calls:
                continue
            assert logical is not None
            targets.append(
                Target(
                    ledger=row,
                    experiment_id=int(experiment["id"]),
                    logical_call_id=int(logical["id"]),
                    prompt_hashes=hashes,
                    call=PlannedCall(
                        question_pk=int(question["id"]),
                        question_id=row["replacement_id"],
                        provider=row["provider"],
                        model=row["model"],
                        run_index=1,
                        prompt_version=row["prompt_version"],
                    ),
                )
            )
    return targets, skipped_scored


def attempt_count(path: Path, logical_call_id: int) -> int:
    with db.connect(path) as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM provider_attempts WHERE logical_call_id = ?",
                (logical_call_id,),
            ).fetchone()[0]
        )


def inspect_outcome(path: Path, target: Target, attempts_before: int) -> dict[str, Any]:
    with db.connect(path) as conn:
        logical = conn.execute(
            "SELECT system_prompt_sha256, user_prompt_sha256 FROM logical_calls WHERE id = ?",
            (target.logical_call_id,),
        ).fetchone()
        assert logical is not None
        if tuple(logical) != target.prompt_hashes:
            raise RuntimeError(f"Prompt hash changed during execution: {target.ledger['cell_key']}")
        latest = conn.execute(
            """
            SELECT status_code, latency_ms, finish_reason, error_type, error_message
            FROM provider_attempts WHERE logical_call_id = ?
            ORDER BY attempt_index DESC LIMIT 1
            """,
            (target.logical_call_id,),
        ).fetchone()
        attempts_after = int(
            conn.execute(
                "SELECT COUNT(*) FROM provider_attempts WHERE logical_call_id = ?",
                (target.logical_call_id,),
            ).fetchone()[0]
        )
        scores = conn.execute(
            """
            SELECT s.strict_correct, p.parse_status, p.selected_letter
            FROM scores s JOIN parsed_answers p ON p.id = s.parsed_answer_id
            WHERE s.logical_call_id = ? ORDER BY s.id
            """,
            (target.logical_call_id,),
        ).fetchall()
        integrity = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    if attempts_after <= attempts_before:
        raise RuntimeError(f"No provider attempt stored: {target.ledger['cell_key']}")
    if len(scores) > 1:
        raise RuntimeError(f"Multiple scores stored: {target.ledger['cell_key']}")
    score = scores[0] if scores else None
    return {
        "cell_key": target.ledger["cell_key"],
        "replacement_id": target.ledger["replacement_id"],
        "attempt_delta": attempts_after - attempts_before,
        "score_count": len(scores),
        "scored": score is not None,
        "selected_letter": score["selected_letter"] if score else None,
        "strict_correct": int(score["strict_correct"]) if score else None,
        "parse_status": score["parse_status"] if score else None,
        "status_code": latest["status_code"] if latest else None,
        "latency_ms": latest["latency_ms"] if latest else None,
        "finish_reason": latest["finish_reason"] if latest else None,
        "error_type": latest["error_type"] if latest else None,
        "error_message": latest["error_message"] if latest else None,
        "integrity": integrity,
    }


def abort_reason(
    outcome: dict[str, Any],
    *,
    unexpected_5xx: int,
    transport_errors: int,
    abort_on_first_5xx: bool,
) -> tuple[str | None, int, int]:
    status = outcome["status_code"]
    error = str(outcome["error_type"] or "").casefold()
    message = str(outcome["error_message"] or "").casefold()
    if outcome["integrity"] != "ok":
        return "database_integrity_failure", unexpected_5xx, transport_errors
    if status in {401, 403} or error in {"auth_error", "forbidden"}:
        return "authentication_failure", unexpected_5xx, transport_errors
    if status == 402 or error == "payment_required":
        return "payment_or_credit_failure", unexpected_5xx, transport_errors
    if status == 200 and not outcome["scored"]:
        return "partial_or_unparseable_response", unexpected_5xx, transport_errors
    if status == 429 or error == "rate_limited" or "circuit" in error or "circuit" in message:
        return "rate_limit_or_circuit_open", unexpected_5xx, transport_errors
    if status is not None and 500 <= int(status) < 600:
        unexpected_5xx += 1
        if abort_on_first_5xx or unexpected_5xx >= 2:
            return "unexpected_5xx", unexpected_5xx, transport_errors
    if error in {"timeout", "request_error"}:
        transport_errors += 1
        if transport_errors >= 2:
            return "sustained_transport_failure", unexpected_5xx, transport_errors
    return None, unexpected_5xx, transport_errors


def write_invocation(
    *,
    args: argparse.Namespace,
    selected: list[dict[str, str]],
    start: str,
    end: str,
    outcomes: list[dict[str, Any]],
    skipped_scored: int,
    stop_reason: str | None,
) -> None:
    INVOCATIONS.mkdir(parents=True, exist_ok=True)
    invocation_id = args.invocation_id or (
        f"{args.arm}-{args.model.replace('/', '-').replace('.', '-')}-{start.replace(':', '')}"
    )
    path = INVOCATIONS / f"{invocation_id}.json"
    if path.exists():
        raise RuntimeError(f"Invocation ID already exists: {invocation_id}")
    scored = sum(item["scored"] for item in outcomes)
    residual = len(outcomes) - scored
    status = "completed"
    if stop_reason:
        status = f"aborted_{stop_reason}"
    elif residual:
        status = "completed_with_unresolved"
    payload = {
        "invocation_id": invocation_id,
        "arm": args.arm,
        "condition": selected[0]["condition"],
        "provider": selected[0]["provider"],
        "model": args.model,
        "dataset": selected[0]["dataset"],
        "experiment_id": selected[0]["experiment"],
        "target_count": len(selected),
        "concurrency": args.max_concurrency,
        "start_time_utc": start,
        "end_time_utc": end,
        "status": status,
        "scored_count": scored,
        "failure_count": residual,
        "skipped_already_scored": skipped_scored,
        "not_started_after_abort": len(selected) - skipped_scored - len(outcomes),
        "stop_reason": stop_reason,
        "redacted_command": (
            "uv run python execute_replacement_cells.py "
            f"--arm {args.arm} --model {args.model} --max-concurrency {args.max_concurrency} "
            "--db [REDACTED_PATH] --execute"
        ),
        "log_path": args.log_path,
        "ledger_sha256": sha256_file(args.ledger),
        "outcomes": outcomes,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if not 1 <= args.max_concurrency <= 10:
        raise SystemExit("--max-concurrency must be between 1 and 10")
    if args.execute and not args.invocation_id:
        raise SystemExit("--invocation-id is required with --execute")
    rows = read_ledger(args.ledger, args)
    if len({(row["provider"], row["dataset"], row["experiment"]) for row in rows}) != 1:
        raise SystemExit("Selected cells span more than one provider/dataset/experiment")
    targets, skipped_scored = resolve_targets(
        args.db, rows, create_logical_calls=args.execute
    )
    plan = {
        "selected": len(rows),
        "queued": len(targets) if args.execute else len(rows) - skipped_scored,
        "skipped_already_scored": skipped_scored,
        "arm": args.arm,
        "provider": rows[0]["provider"],
        "model": args.model,
        "max_concurrency": args.max_concurrency,
        "execute": args.execute,
    }
    print(json.dumps({"plan": plan}, sort_keys=True), flush=True)
    if not args.execute or not targets:
        return

    adapter = get_provider(rows[0]["provider"], settings=Settings.from_env())
    auth = adapter.check_auth()
    if auth.status_code != 200 or auth.error_type is not None:
        adapter.close()
        raise SystemExit("Provider authentication/health gate failed; no benchmark calls issued")

    attempts_before = {
        target.logical_call_id: attempt_count(args.db, target.logical_call_id)
        for target in targets
    }
    start = now_iso()
    tracker = _ProgressTracker(skipped_count=skipped_scored, total=len(rows))
    pending = iter(targets)
    futures: dict[Future[None], Target] = {}
    outcomes: list[dict[str, Any]] = []
    stop_reason: str | None = None
    unexpected_5xx = 0
    transport_errors = 0

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
                        args.db,
                        target,
                        attempts_before[target.logical_call_id],
                    )
                    outcomes.append(outcome)
                    print(json.dumps({"outcome": outcome}, sort_keys=True), flush=True)
                    reason, unexpected_5xx, transport_errors = abort_reason(
                        outcome,
                        unexpected_5xx=unexpected_5xx,
                        transport_errors=transport_errors,
                        abort_on_first_5xx=args.abort_on_first_5xx,
                    )
                    if reason and stop_reason is None:
                        stop_reason = reason
                if stop_reason is None:
                    for _ in done:
                        submit(pool)
                else:
                    for future in futures:
                        future.cancel()
        end = now_iso()
        write_invocation(
            args=args,
            selected=rows,
            start=start,
            end=end,
            outcomes=outcomes,
            skipped_scored=skipped_scored,
            stop_reason=stop_reason,
        )
        summary = {
            "executed": len(outcomes),
            "scored": sum(item["scored"] for item in outcomes),
            "unresolved": sum(not item["scored"] for item in outcomes),
            "skipped_already_scored": skipped_scored,
            "not_started": len(rows) - skipped_scored - len(outcomes),
            "stop_reason": stop_reason,
        }
        print(json.dumps({"summary": summary}, sort_keys=True), flush=True)
        if stop_reason or summary["unresolved"] or summary["not_started"]:
            raise SystemExit(2)
    finally:
        _close_all_thread_conns()
        adapter.close()


if __name__ == "__main__":
    main()
