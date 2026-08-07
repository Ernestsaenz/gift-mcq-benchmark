"""Execute frozen incorrect-cell replicates with resume and fail-fast guards."""

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


DEFAULT_DB = HERE / "runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite"
DEFAULT_LEDGER = HERE / "manifests/frozen-replicate-cell-ledger.csv"
INVOCATIONS = HERE / "invocations"
LOGS = HERE / "logs"
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
    attempts_before: int
    call: PlannedCall


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fields_hash(question: Any) -> str:
    payload = bytearray()
    for field in RAW_FIELDS:
        raw = str(question[field]).encode("utf-8")
        payload.extend(len(raw).to_bytes(8, "big"))
        payload.extend(raw)
    return hashlib.sha256(payload).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arm",
        required=True,
        choices=("openrouter_A", "openrouter_B", "tailscale_A"),
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--run-index", action="append", type=int, default=[])
    parser.add_argument("--question-id", action="append", default=[])
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--max-provider-attempts", type=int, default=5)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--invocation-id")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    # PROTOCOL DEVIATION SWITCH. Named so the deviation is legible in the recorded
    # command line of any invocation that used it.
    #
    # The frozen request pins temperature=0 and top_p=1 and relies on
    # provider.require_parameters=true to guarantee the serving provider honours
    # them. google/gemini-3.6-flash is closed-weights: only Google AI Studio
    # supports those parameters, and its shared pool has been returning 429 since
    # 2026-08-05T16:33Z. Routing to google-vertex reaches the model but SILENTLY
    # DROPS temperature and top_p, so the model samples at its default
    # temperature and is not deterministic (measured: one question returned
    # ['b','c','b'] across three repeats).
    #
    # Cells collected with this flag are therefore NOT comparable to cells
    # collected without it. See STATUS.md.
    parser.add_argument(
        "--deviation-route-upstream",
        default=None,
        help=(
            "Protocol deviation. Pin the OpenRouter upstream provider (e.g. "
            "'google-vertex') and relax require_parameters, allowing the provider "
            "to ignore temperature/top_p. Omit for normal frozen behaviour."
        ),
    )
    return parser.parse_args()


def _redacted_command() -> str:
    """Reconstruct the invoking command from the real argv, redacting paths.

    Anything that looks like a filesystem path is replaced, so the record stays
    reproducible without leaking the local layout. Every other flag is preserved
    verbatim, including --deviation-route-upstream: an invocation that departed
    from the frozen request must say so in its own record.
    """
    parts = ["uv run python execute_replicates.py"]
    redact_next = False
    for token in sys.argv[1:]:
        if redact_next:
            parts.append("[REDACTED_PATH]")
            redact_next = False
            continue
        if token in ("--db", "--ledger"):
            parts.append(token)
            redact_next = True
            continue
        # Only filesystem-looking tokens are redacted. Model ids such as
        # "google/gemini-3.6-flash" contain a slash but are NOT paths and must
        # survive verbatim, or the record stops identifying what was run.
        looks_like_path = token.startswith(("/", "~", "./", "../"))
        parts.append("[REDACTED_PATH]" if looks_like_path else token)
    return " ".join(parts)


def read_ledger(path: Path, args: argparse.Namespace) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    selected = [
        row
        for row in rows
        if row["arm"] == args.arm
        and row["model"] == args.model
        and (not args.run_index or int(row["run_index"]) in set(args.run_index))
        and (not args.question_id or row["question_id"] in set(args.question_id))
    ]
    if not selected:
        raise SystemExit("No frozen replicate targets matched the requested filters")
    if len({row["target_key"] for row in selected}) != len(selected):
        raise SystemExit("Frozen ledger contains duplicate selected target keys")
    if {int(row["run_index"]) for row in selected} - {2, 3}:
        raise SystemExit("Frozen ledger includes a run index outside 2 and 3")
    if {row["status"] for row in selected} != {"READY_NOT_RUN"}:
        raise SystemExit("Selected ledger rows are not frozen READY_NOT_RUN targets")
    if args.question_id and {row["question_id"] for row in selected} != set(args.question_id):
        raise SystemExit("One or more requested question IDs are absent from the selected ledger slice")
    return selected


def resolve_targets(
    path: Path,
    rows: list[dict[str, str]],
    *,
    max_provider_attempts: int,
) -> tuple[list[Target], int, list[dict[str, Any]]]:
    targets: list[Target] = []
    skipped_scored = 0
    exhausted: list[dict[str, Any]] = []
    with db.connect(path) as conn:
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise SystemExit(f"Database integrity gate failed: {integrity}")
        for row in rows:
            dataset = db.get_dataset(conn, row["dataset"])
            if dataset is None:
                raise SystemExit(f"Dataset absent: {row['dataset']}")
            experiment = db.get_experiment(conn, row["experiment"])
            if experiment is None:
                raise SystemExit(f"Experiment absent: {row['experiment']}")
            if int(experiment["dataset_id"]) != int(dataset["id"]):
                raise SystemExit(f"Experiment/dataset mismatch: {row['target_key']}")
            if experiment["prompt_version"] != row["prompt_version"]:
                raise SystemExit(f"Experiment prompt mismatch: {row['target_key']}")

            question = conn.execute(
                "SELECT * FROM questions WHERE dataset_id = ? AND question_id = ?",
                (dataset["id"], row["question_id"]),
            ).fetchone()
            if question is None:
                raise SystemExit(f"Question absent: {row['target_key']}")
            if fields_hash(question) != row["input_fields_sha256"]:
                raise SystemExit(f"Input fields changed: {row['target_key']}")
            prompt = render_benchmark_prompt(
                question,
                provider=row["provider"],
                prompt_version=row["prompt_version"],
            )
            hashes = (prompt.system_sha256, prompt.user_sha256)
            if hashes != (row["system_prompt_sha256"], row["user_prompt_sha256"]):
                raise SystemExit(f"Rendered prompt changed: {row['target_key']}")

            logical = conn.execute(
                """
                SELECT * FROM logical_calls
                WHERE experiment_id = ? AND question_id = ? AND provider = ?
                  AND model = ? AND run_index = ? AND prompt_version = ?
                """,
                (
                    experiment["id"],
                    question["id"],
                    row["provider"],
                    row["model"],
                    int(row["run_index"]),
                    row["prompt_version"],
                ),
            ).fetchone()
            if logical is None:
                raise SystemExit(f"Frozen logical call absent: {row['target_key']}")
            if (logical["system_prompt_sha256"], logical["user_prompt_sha256"]) != hashes:
                raise SystemExit(f"Stored prompt hashes changed: {row['target_key']}")
            score_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM scores WHERE logical_call_id = ?",
                    (logical["id"],),
                ).fetchone()[0]
            )
            attempt_count = int(
                conn.execute(
                    "SELECT COUNT(*) FROM provider_attempts WHERE logical_call_id = ?",
                    (logical["id"],),
                ).fetchone()[0]
            )
            if score_count > 1:
                raise SystemExit(f"Multiple scores exist: {row['target_key']}")
            if score_count == 1:
                skipped_scored += 1
                continue
            if attempt_count >= max_provider_attempts:
                exhausted.append(
                    {
                        "target_key": row["target_key"],
                        "attempt_count": attempt_count,
                        "reason": "max_provider_attempts_reached_without_score",
                    }
                )
                continue
            targets.append(
                Target(
                    ledger=row,
                    experiment_id=int(experiment["id"]),
                    logical_call_id=int(logical["id"]),
                    prompt_hashes=hashes,
                    attempts_before=attempt_count,
                    call=PlannedCall(
                        question_pk=int(question["id"]),
                        question_id=row["question_id"],
                        provider=row["provider"],
                        model=row["model"],
                        run_index=int(row["run_index"]),
                        prompt_version=row["prompt_version"],
                    ),
                )
            )
    return targets, skipped_scored, exhausted


def inspect_outcome(path: Path, target: Target) -> dict[str, Any]:
    with db.connect(path) as conn:
        logical = conn.execute(
            "SELECT system_prompt_sha256, user_prompt_sha256 FROM logical_calls WHERE id = ?",
            (target.logical_call_id,),
        ).fetchone()
        if logical is None or tuple(logical) != target.prompt_hashes:
            raise RuntimeError(f"Prompt hash changed during execution: {target.ledger['target_key']}")
        attempts = conn.execute(
            """
            SELECT status_code, latency_ms, finish_reason, error_type, error_message,
                   request_sha256, prompt_id, top_k
            FROM provider_attempts WHERE logical_call_id = ?
            ORDER BY attempt_index
            """,
            (target.logical_call_id,),
        ).fetchall()
        scores = conn.execute(
            """
            SELECT s.strict_correct, s.letter_correct, s.text_correct,
                   p.parse_status, p.parse_method, p.selected_letter,
                   p.selected_option_text
            FROM scores s JOIN parsed_answers p ON p.id = s.parsed_answer_id
            WHERE s.logical_call_id = ? ORDER BY s.id
            """,
            (target.logical_call_id,),
        ).fetchall()
        integrity = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    if len(attempts) <= target.attempts_before:
        raise RuntimeError(f"No new provider attempt stored: {target.ledger['target_key']}")
    if len(scores) > 1:
        raise RuntimeError(f"Multiple scores stored: {target.ledger['target_key']}")
    latest = attempts[-1]
    score = scores[0] if scores else None
    return {
        "target_key": target.ledger["target_key"],
        "arm": target.ledger["arm"],
        "model": target.ledger["model"],
        "question_id": target.ledger["question_id"],
        "source_key": target.ledger["source_key"],
        "run_index": int(target.ledger["run_index"]),
        "attempts_before": target.attempts_before,
        "attempts_after": len(attempts),
        "attempt_delta": len(attempts) - target.attempts_before,
        "scored": score is not None,
        "selected_letter": score["selected_letter"] if score else None,
        "selected_option_text": score["selected_option_text"] if score else None,
        "strict_correct": int(score["strict_correct"]) if score else None,
        "letter_correct": int(score["letter_correct"]) if score else None,
        "text_correct": int(score["text_correct"]) if score else None,
        "parse_status": score["parse_status"] if score else None,
        "parse_method": score["parse_method"] if score else None,
        "status_code": latest["status_code"],
        "latency_ms": latest["latency_ms"],
        "finish_reason": latest["finish_reason"],
        "error_type": latest["error_type"],
        "error_message": latest["error_message"],
        "request_sha256": latest["request_sha256"],
        "prompt_id": latest["prompt_id"],
        "top_k": latest["top_k"],
        "database_integrity": integrity,
    }


def update_failure_state(
    outcome: dict[str, Any],
    *,
    consecutive_5xx: int,
    consecutive_transport: int,
    consecutive_unscored_200: int,
) -> tuple[str | None, int, int, int]:
    status = outcome["status_code"]
    error = str(outcome["error_type"] or "").casefold()
    message = str(outcome["error_message"] or "").casefold()
    if outcome["database_integrity"] != "ok":
        return "database_integrity_failure", consecutive_5xx, consecutive_transport, consecutive_unscored_200
    if status in {401, 403} or error in {"auth_error", "forbidden"}:
        return "authentication_failure", consecutive_5xx, consecutive_transport, consecutive_unscored_200
    if status == 402 or error == "payment_required":
        return "payment_or_credit_failure", consecutive_5xx, consecutive_transport, consecutive_unscored_200
    if status == 429 or error == "rate_limited" or "circuit" in error or "circuit" in message:
        return "rate_limit_or_circuit_open", consecutive_5xx, consecutive_transport, consecutive_unscored_200

    is_5xx = status is not None and 500 <= int(status) < 600
    is_transport = error in {"timeout", "request_error"}
    is_unscored_200 = status == 200 and not outcome["scored"]
    consecutive_5xx = consecutive_5xx + 1 if is_5xx else 0
    consecutive_transport = consecutive_transport + 1 if is_transport else 0
    consecutive_unscored_200 = consecutive_unscored_200 + 1 if is_unscored_200 else 0
    if consecutive_5xx >= 3:
        return "three_consecutive_5xx", consecutive_5xx, consecutive_transport, consecutive_unscored_200
    if consecutive_transport >= 3:
        return "three_consecutive_transport_failures", consecutive_5xx, consecutive_transport, consecutive_unscored_200
    if consecutive_unscored_200 >= 3:
        return "three_consecutive_unscored_200_responses", consecutive_5xx, consecutive_transport, consecutive_unscored_200
    return None, consecutive_5xx, consecutive_transport, consecutive_unscored_200


def write_event(path: Path, event: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_invocation(
    *,
    args: argparse.Namespace,
    selected: list[dict[str, str]],
    start: str,
    end: str,
    outcomes: list[dict[str, Any]],
    skipped_scored: int,
    exhausted: list[dict[str, Any]],
    not_started: int,
    stop_reason: str | None,
    log_path: Path,
) -> Path:
    scored = sum(item["scored"] for item in outcomes)
    unresolved = len(outcomes) - scored
    status = "completed"
    if stop_reason:
        status = f"aborted_{stop_reason}"
    elif unresolved or exhausted:
        status = "completed_with_unresolved"
    payload = {
        "invocation_id": args.invocation_id,
        "arm": args.arm,
        "condition": selected[0]["condition"],
        "provider": selected[0]["provider"],
        "model": args.model,
        "run_indices": sorted({int(row["run_index"]) for row in selected}),
        "dataset": selected[0]["dataset"],
        "experiment": selected[0]["experiment"],
        "target_count": len(selected),
        "concurrency": args.max_concurrency,
        "max_provider_attempts": args.max_provider_attempts,
        "start_time_utc": start,
        "end_time_utc": end,
        "status": status,
        "executed_count": len(outcomes),
        "scored_count": scored,
        "failure_count": unresolved,
        "skipped_already_scored": skipped_scored,
        "exhausted_before_invocation": exhausted,
        "not_started_after_abort": not_started,
        "stop_reason": stop_reason,
        # Derived from the real argv, not a template. The previous hand-built
        # string listed a fixed five arguments, so any invocation using
        # --question-id, --run-index or --deviation-route-upstream recorded a
        # command that would NOT reproduce it. Records written before 2026-08-07
        # carry that templated form; see the consolidation folder's ledger notes.
        "redacted_command": _redacted_command(),
        # Explicit, machine-readable statement of whether this invocation departed
        # from the frozen request. Recorded even when false, so silence in the
        # record is never ambiguous.
        "protocol_deviation": (
            {
                "upstream_override": args.deviation_route_upstream,
                "require_parameters": False,
                "allow_fallbacks": False,
                "consequence": (
                    "temperature and top_p may be ignored by the pinned upstream"
                ),
            }
            if args.deviation_route_upstream
            else None
        ),
        "log_path": str(log_path.relative_to(HERE)),
        "ledger_sha256": sha256_file(args.ledger),
        "outcomes": outcomes,
    }
    path = INVOCATIONS / f"{args.invocation_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> None:
    args = parse_args()
    if not 1 <= args.max_concurrency <= 10:
        raise SystemExit("--max-concurrency must be between 1 and 10")
    if not 1 <= args.max_provider_attempts <= 5:
        raise SystemExit("--max-provider-attempts must be between 1 and 5")
    if args.run_index and set(args.run_index) - {2, 3}:
        raise SystemExit("--run-index may only be 2 or 3")
    if args.execute and not args.invocation_id:
        raise SystemExit("--invocation-id is required with --execute")

    selected = read_ledger(args.ledger, args)
    if len({(row["provider"], row["dataset"], row["experiment"]) for row in selected}) != 1:
        raise SystemExit("Selected targets span multiple provider/dataset/experiment tuples")
    targets, skipped_scored, exhausted = resolve_targets(
        args.db,
        selected,
        max_provider_attempts=args.max_provider_attempts,
    )
    plan = {
        "selected": len(selected),
        "queued": len(targets),
        "skipped_already_scored": skipped_scored,
        "exhausted": len(exhausted),
        "arm": args.arm,
        "provider": selected[0]["provider"],
        "model": args.model,
        "run_indices": sorted({int(row["run_index"]) for row in selected}),
        "max_concurrency": args.max_concurrency,
        "execute": args.execute,
    }
    print(json.dumps({"plan": plan}, sort_keys=True), flush=True)
    if not args.execute or not targets:
        if args.execute and exhausted:
            raise SystemExit(2)
        return

    INVOCATIONS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    invocation_path = INVOCATIONS / f"{args.invocation_id}.json"
    log_path = LOGS / f"{args.invocation_id}.jsonl"
    if invocation_path.exists() or log_path.exists():
        raise SystemExit(f"Invocation ID already exists: {args.invocation_id}")
    log_path.touch(exist_ok=False)

    start = now_iso()
    write_event(log_path, {"event": "start", "at_utc": start, "plan": plan})
    adapter = get_provider(selected[0]["provider"], settings=Settings.from_env())
    auth = adapter.check_auth()
    if auth.status_code != 200 or auth.error_type is not None:
        end = now_iso()
        write_event(
            log_path,
            {
                "event": "auth_failure",
                "at_utc": end,
                "status_code": auth.status_code,
                "error_type": auth.error_type,
            },
        )
        write_invocation(
            args=args,
            selected=selected,
            start=start,
            end=end,
            outcomes=[],
            skipped_scored=skipped_scored,
            exhausted=exhausted,
            not_started=len(targets),
            stop_reason="authentication_failure",
            log_path=log_path,
        )
        adapter.close()
        raise SystemExit("Provider authentication/health gate failed; no benchmark calls issued")

    tracker = _ProgressTracker(
        skipped_count=skipped_scored + len(exhausted),
        total=len(selected),
    )
    # allow_fallbacks=False keeps the deviation honest: if the pinned upstream is
    # unavailable the call fails rather than quietly reverting to a different
    # provider, which would mix two sampling regimes inside one slice.
    provider_routing: dict[str, Any] | None = None
    if args.deviation_route_upstream:
        provider_routing = {
            "order": [args.deviation_route_upstream],
            "allow_fallbacks": False,
            "require_parameters": False,
        }
        print(
            json.dumps(
                {
                    "protocol_deviation": {
                        "upstream": args.deviation_route_upstream,
                        "require_parameters": False,
                        "consequence": (
                            "temperature and top_p may be ignored by the upstream; "
                            "results are not comparable to cells collected without "
                            "this flag"
                        ),
                    }
                }
            ),
            flush=True,
        )

    pending = iter(targets)
    futures: dict[Future[None], Target] = {}
    outcomes: list[dict[str, Any]] = []
    stop_reason: str | None = None
    consecutive_5xx = 0
    consecutive_transport = 0
    consecutive_unscored_200 = 0

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
            # Provider adapters may issue two wire attempts. Disable that
            # internal retry when only one attempt remains under the frozen
            # five-attempt ceiling, so a logical replicate never exceeds it.
            no_retry=target.attempts_before >= args.max_provider_attempts - 1,
            tailscale_prompt_id=(
                GIFT_MCQ_PROMPT_ID
                if target.call.provider == "tailscale_medical_rag"
                else None
            ),
            tailscale_top_k=None,
            provider_routing=provider_routing,
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
                    try:
                        future.result()
                        outcome = inspect_outcome(args.db, target)
                    except Exception as exc:  # noqa: BLE001
                        stop_reason = "executor_or_database_exception"
                        write_event(
                            log_path,
                            {
                                "event": "executor_exception",
                                "at_utc": now_iso(),
                                "target_key": target.ledger["target_key"],
                                "exception_type": type(exc).__name__,
                                "message": str(exc)[:500],
                            },
                        )
                        continue
                    outcomes.append(outcome)
                    write_event(log_path, {"event": "outcome", "at_utc": now_iso(), **outcome})
                    (
                        reason,
                        consecutive_5xx,
                        consecutive_transport,
                        consecutive_unscored_200,
                    ) = update_failure_state(
                        outcome,
                        consecutive_5xx=consecutive_5xx,
                        consecutive_transport=consecutive_transport,
                        consecutive_unscored_200=consecutive_unscored_200,
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
        not_started = len(selected) - skipped_scored - len(exhausted) - len(outcomes)
        invocation_file = write_invocation(
            args=args,
            selected=selected,
            start=start,
            end=end,
            outcomes=outcomes,
            skipped_scored=skipped_scored,
            exhausted=exhausted,
            not_started=not_started,
            stop_reason=stop_reason,
            log_path=log_path,
        )
        summary = {
            "executed": len(outcomes),
            "scored": sum(item["scored"] for item in outcomes),
            "unresolved": sum(not item["scored"] for item in outcomes),
            "skipped_already_scored": skipped_scored,
            "exhausted": len(exhausted),
            "not_started": not_started,
            "stop_reason": stop_reason,
            "invocation": str(invocation_file.relative_to(HERE)),
        }
        write_event(log_path, {"event": "end", "at_utc": end, "summary": summary})
        print(json.dumps({"summary": summary}, sort_keys=True), flush=True)
        if stop_reason or summary["unresolved"] or summary["exhausted"] or summary["not_started"]:
            raise SystemExit(2)
    finally:
        _close_all_thread_conns()
        adapter.close()


if __name__ == "__main__":
    main()
