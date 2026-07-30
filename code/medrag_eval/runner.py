from __future__ import annotations

import json
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from . import db
from .config import Settings
from .parser import parse_openai_response, parse_with_fallback
from .prompting import SHARED_PROMPT_VERSION, render_shared_prompt
from .providers import GIFT_MCQ_PROMPT_ID, get_provider
from .providers.base import ProviderRequest, ProviderResponse
from .scoring import ScoreResult, score_answer


TAILSCALE_PROVIDER = "tailscale_medical_rag"
OPENROUTER_PROVIDER = "openrouter"

_thread_local = threading.local()
_thread_conns: list = []
_thread_conns_lock = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def _log_progress(
    *,
    position: int,
    total: int,
    call: "PlannedCall",
    wall_ms: int | None,
    parse_status: str,
    selected_letter: str | None,
    correct_letter: str,
    strict_correct: bool | None,
    api_error: str | None = None,
) -> None:
    """Print one progress line per executed call.

    Goes to stdout with flush=True so it appears live in `tail -f` even when
    the runner is launched under nohup (where stdout is block-buffered to a
    file by default).
    """
    pct = (position / total * 100) if total else 0.0
    wall_s = (wall_ms or 0) / 1000
    if api_error is not None:
        body = f"API_ERROR={api_error}"
    else:
        if strict_correct is True:
            marker = "✓"
        elif strict_correct is False:
            marker = "✗"
        else:
            marker = "?"
        letter = selected_letter or "-"
        body = f"parse={parse_status} letter={letter}/{correct_letter} {marker}"
    print(
        f"[{_now()}] [{position}/{total} ({pct:.0f}%)] "
        f"{call.provider}/{call.model} q={call.question_id} r={call.run_index}  "
        f"{body}  {wall_s:.1f}s",
        flush=True,
    )


class _ProgressTracker:
    def __init__(self, *, skipped_count: int, total: int) -> None:
        self._completed = 0
        self._skipped_count = skipped_count
        self._total = total
        self._lock = threading.Lock()

    @property
    def completed(self) -> int:
        with self._lock:
            return self._completed

    def tick_and_log(
        self,
        *,
        call: "PlannedCall",
        wall_ms: int | None,
        parse_status: str,
        selected_letter: str | None,
        correct_letter: str,
        strict_correct: bool | None,
        api_error: str | None = None,
    ) -> None:
        with self._lock:
            self._completed += 1
            _log_progress(
                position=self._skipped_count + self._completed,
                total=self._total,
                call=call,
                wall_ms=wall_ms,
                parse_status=parse_status,
                selected_letter=selected_letter,
                correct_letter=correct_letter,
                strict_correct=strict_correct,
                api_error=api_error,
            )


@dataclass(frozen=True)
class ProviderModel:
    provider: str
    model: str


@dataclass(frozen=True)
class PlannedCall:
    question_pk: int
    question_id: str
    provider: str
    model: str
    run_index: int
    prompt_version: str
    skipped: bool = False


@dataclass(frozen=True)
class RunSummary:
    experiment_name: str
    planned_calls: int
    executed_calls: int
    skipped_calls: int
    dry_run: bool


def parse_provider_models(providers: str | None, models: str | None, provider_model: tuple[str, ...]) -> list[ProviderModel]:
    pairs: list[ProviderModel] = []
    for item in provider_model:
        if ":" not in item:
            raise ValueError(f"--provider-model must be provider:model, got {item!r}")
        provider, model = item.split(":", 1)
        pairs.append(ProviderModel(provider=provider.strip(), model=model.strip()))

    if providers or models:
        if not providers or not models:
            raise ValueError("--providers and --models must be supplied together")
        provider_values = [value.strip() for value in providers.split(",") if value.strip()]
        model_values = [value.strip() for value in models.split(",") if value.strip()]
        if len(provider_values) != len(model_values):
            raise ValueError("--providers and --models must contain the same number of comma-separated items")
        pairs.extend(ProviderModel(provider=provider, model=model) for provider, model in zip(provider_values, model_values))

    if not pairs:
        raise ValueError("No provider/model pairs supplied")
    return pairs


def plan_calls(
    conn,
    *,
    dataset: str,
    experiment_name: str,
    provider_models: Iterable[ProviderModel],
    runs: int,
    limit: int | None,
    offset: int,
    question_id: str | None,
    prompt_version: str,
    force: bool,
    tailscale_prompt_id: int | None = None,
    tailscale_top_k: int | None = None,
) -> tuple[int, list[PlannedCall]]:
    dataset_row = db.get_dataset(conn, dataset)
    if dataset_row is None:
        raise ValueError(f"Dataset not found: {dataset}")
    provider_pairs = list(provider_models)
    tailscale_prompt_id = _resolve_gift_prompt_id(provider_pairs, tailscale_prompt_id)
    # `runs` is intentionally NOT stored in the experiment config — it is a
    # planning parameter, not part of the experiment identity. This lets the
    # operator extend an existing experiment with additional runs by re-launching
    # with a higher --runs value; already-completed (question, provider, model,
    # run_index, prompt_version) tuples are skipped via has_completed_logical_call,
    # while the new run_indices are queued. The actual count of completed runs
    # at any time is derivable from MAX(run_index) in logical_calls.
    config = {
        "limit": limit,
        "offset": offset,
        "question_id": question_id,
        "tailscale_prompt_id": tailscale_prompt_id,
        "tailscale_top_k": tailscale_top_k,
    }
    experiment = db.get_or_create_experiment(
        conn,
        name=experiment_name,
        dataset_id=dataset_row["id"],
        prompt_version=prompt_version,
        config_json=config,
    )
    _validate_experiment_reuse(experiment, dataset_row["id"], prompt_version, config)
    questions = db.list_questions(conn, dataset_row["id"], limit=limit, offset=offset, question_id=question_id)
    planned: list[PlannedCall] = []
    for run_index in range(1, runs + 1):
        for question in questions:
            for pair in provider_pairs:
                provider_name = db.normalize_provider(pair.provider)
                # Both providers receive the same user prompt regime. GIFT also
                # receives its mandatory stored MCQ wrapper via X-Prompt-ID.
                skipped = False if force else db.has_completed_logical_call(
                    conn,
                    experiment_id=experiment["id"],
                    question_pk=question["id"],
                    provider=provider_name,
                    model=pair.model,
                    run_index=run_index,
                    prompt_version=prompt_version,
                )
                planned.append(
                    PlannedCall(
                        question_pk=question["id"],
                        question_id=question["question_id"],
                        provider=provider_name,
                        model=pair.model,
                        run_index=run_index,
                        prompt_version=prompt_version,
                        skipped=skipped,
                    )
                )
    return experiment["id"], planned


def run_benchmark(
    *,
    db_path,
    dataset: str,
    experiment_name: str,
    provider_models: list[ProviderModel],
    runs: int,
    limit: int | None,
    offset: int = 0,
    question_id: str | None = None,
    temperature: float = 0,
    prompt_version: str = SHARED_PROMPT_VERSION,
    force: bool = False,
    dry_run: bool = False,
    no_retry: bool = False,
    tailscale_prompt_id: int | None = None,
    tailscale_top_k: int | None = None,
    openrouter_concurrency: int = 18,
    tailscale_concurrency: int = 5,
) -> RunSummary:
    tailscale_prompt_id = _resolve_gift_prompt_id(
        provider_models, tailscale_prompt_id
    )
    with db.connect(db_path) as conn:
        experiment_id, planned = plan_calls(
            conn,
            dataset=dataset,
            experiment_name=experiment_name,
            provider_models=provider_models,
            runs=runs,
            limit=limit,
            offset=offset,
            question_id=question_id,
            prompt_version=prompt_version,
            force=force,
            tailscale_prompt_id=tailscale_prompt_id,
            tailscale_top_k=tailscale_top_k,
        )
        if dry_run:
            return RunSummary(experiment_name, len(planned), 0, sum(call.skipped for call in planned), True)

        calls_to_run = [call for call in planned if not call.skipped]
        skipped_count = sum(1 for c in planned if c.skipped)
        total_planned = len(planned)
        tracker = _ProgressTracker(skipped_count=skipped_count, total=total_planned)
        settings = Settings.from_env()
        adapters: dict[str, object] = {}
        try:
            adapters = _build_provider_adapters(calls_to_run, settings=settings)
            if calls_to_run:
                print("[note] Progress counter reflects completion order, not plan order.", flush=True)
            _run_calls_parallel(
                db_path=db_path,
                experiment_id=experiment_id,
                calls=calls_to_run,
                adapters=adapters,
                tracker=tracker,
                temperature=temperature,
                no_retry=no_retry,
                tailscale_prompt_id=tailscale_prompt_id,
                tailscale_top_k=tailscale_top_k,
                openrouter_concurrency=openrouter_concurrency,
                tailscale_concurrency=tailscale_concurrency,
            )
        finally:
            _close_all_thread_conns()
            _close_adapters(adapters)

        return RunSummary(experiment_name, len(planned), tracker.completed, sum(call.skipped for call in planned), False)


def _resolve_gift_prompt_id(
    provider_models: Iterable[ProviderModel],
    tailscale_prompt_id: int | None,
) -> int | None:
    """Apply the required MCQ prompt whenever the benchmark includes GIFT."""
    includes_gift = any(
        db.normalize_provider(pair.provider) == TAILSCALE_PROVIDER
        for pair in provider_models
    )
    if not includes_gift:
        return tailscale_prompt_id
    if tailscale_prompt_id is None:
        return GIFT_MCQ_PROMPT_ID
    if tailscale_prompt_id != GIFT_MCQ_PROMPT_ID:
        raise ValueError(
            "GIFT benchmark runs must use "
            f"--tailscale-prompt-id {GIFT_MCQ_PROMPT_ID}; "
            f"received {tailscale_prompt_id}"
        )
    return tailscale_prompt_id


_RUN_EXTENSIBLE_KEYS = {"runs"}


def _stripped_config(cfg: dict | None) -> dict | None:
    """Return a copy of `cfg` with run-extensible keys removed.

    `runs` is not part of an experiment's identity (see plan_calls). We strip
    it from both sides of the comparison so:
      * Old experiments stored before this change (which DID include `runs`)
        still validate against fresh requests that no longer include it.
      * Re-launching with a different --runs value never triggers the reuse
        guard — it's an intentional resume / extend operation.
    """
    if not isinstance(cfg, dict):
        return cfg
    return {k: v for k, v in cfg.items() if k not in _RUN_EXTENSIBLE_KEYS}


def _validate_experiment_reuse(experiment, dataset_id: int, prompt_version: str, config: dict) -> None:
    if experiment["dataset_id"] != dataset_id:
        raise ValueError(
            f"Experiment {experiment['name']!r} already belongs to a different dataset"
        )
    if experiment["prompt_version"] != prompt_version:
        raise ValueError(
            f"Experiment {experiment['name']!r} already uses prompt version {experiment['prompt_version']!r}"
        )
    try:
        existing_config = json.loads(experiment["config_json"])
    except (TypeError, json.JSONDecodeError):
        existing_config = None
    if _stripped_config(existing_config) != _stripped_config(config):
        raise ValueError(f"Experiment {experiment['name']!r} already exists with different run config")


def _build_provider_adapters(calls: list[PlannedCall], *, settings: Settings) -> dict[str, object]:
    adapters: dict[str, object] = {}
    try:
        for provider in sorted({call.provider for call in calls}):
            adapter = get_provider(provider, settings=settings)
            adapters[provider] = adapter
            if provider == TAILSCALE_PROVIDER:
                ensure_token = getattr(adapter, "_ensure_token", None)
                if callable(ensure_token):
                    auth_response = ensure_token()
                    if auth_response is not None:
                        raise RuntimeError(auth_response.error or f"TailScale auth failed: {auth_response.status.value}")
        return adapters
    except Exception:
        _close_adapters(adapters)
        raise


def _close_adapters(adapters: dict[str, object]) -> None:
    for adapter in adapters.values():
        close = getattr(adapter, "close", None)
        if callable(close):
            close()


def _get_thread_conn(db_path) -> object:
    conn = getattr(_thread_local, "conn", None)
    conn_path = getattr(_thread_local, "db_path", None)
    if conn is None or conn_path != str(db_path):
        conn = db.connect(db_path)
        _thread_local.conn = conn
        _thread_local.db_path = str(db_path)
        with _thread_conns_lock:
            _thread_conns.append(conn)
    return conn


def _close_all_thread_conns() -> None:
    with _thread_conns_lock:
        conns = list(_thread_conns)
        _thread_conns.clear()
    for conn in conns:
        try:
            conn.close()
        except Exception:
            pass
    _thread_local.conn = None
    _thread_local.db_path = None


def _run_calls_parallel(
    *,
    db_path,
    experiment_id: int,
    calls: list[PlannedCall],
    adapters: dict[str, object],
    tracker: _ProgressTracker,
    temperature: float,
    no_retry: bool,
    tailscale_prompt_id: int | None,
    tailscale_top_k: int | None,
    openrouter_concurrency: int,
    tailscale_concurrency: int,
) -> None:
    openrouter_calls = [call for call in calls if call.provider == OPENROUTER_PROVIDER]
    tailscale_calls = [call for call in calls if call.provider == TAILSCALE_PROVIDER]
    other_calls = [
        call for call in calls if call.provider not in {OPENROUTER_PROVIDER, TAILSCALE_PROVIDER}
    ]
    if other_calls:
        providers = ", ".join(sorted({call.provider for call in other_calls}))
        raise ValueError(f"No concurrency policy configured for provider(s): {providers}")

    stop_event = threading.Event()
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="provider-dispatch") as dispatcher:
        futures = [
            dispatcher.submit(
                _run_provider_calls,
                calls=openrouter_calls,
                max_workers=max(1, openrouter_concurrency),
                thread_name_prefix="openrouter",
                db_path=db_path,
                experiment_id=experiment_id,
                adapter=adapters.get(OPENROUTER_PROVIDER),
                tracker=tracker,
                temperature=temperature,
                no_retry=no_retry,
                tailscale_prompt_id=tailscale_prompt_id,
                tailscale_top_k=tailscale_top_k,
                stop_event=stop_event,
            ),
            dispatcher.submit(
                _run_provider_calls,
                calls=tailscale_calls,
                max_workers=max(1, tailscale_concurrency),
                thread_name_prefix="tailscale",
                db_path=db_path,
                experiment_id=experiment_id,
                adapter=adapters.get(TAILSCALE_PROVIDER),
                tracker=tracker,
                temperature=temperature,
                no_retry=no_retry,
                tailscale_prompt_id=tailscale_prompt_id,
                tailscale_top_k=tailscale_top_k,
                stop_event=stop_event,
            ),
        ]
        done, pending = wait(set(futures), return_when=FIRST_COMPLETED)
        while pending:
            try:
                for future in done:
                    future.result()
            except Exception:
                stop_event.set()
                for future in pending:
                    future.cancel()
                raise
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
        for future in done:
            future.result()


def _run_provider_calls(
    *,
    calls: list[PlannedCall],
    max_workers: int,
    thread_name_prefix: str,
    db_path,
    experiment_id: int,
    adapter,
    tracker: _ProgressTracker,
    temperature: float,
    no_retry: bool,
    tailscale_prompt_id: int | None,
    tailscale_top_k: int | None,
    stop_event: threading.Event,
) -> None:
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=thread_name_prefix) as pool:
        _drain_provider_pool(
            pool=pool,
            calls=calls,
            max_in_flight=max_workers,
            db_path=db_path,
            experiment_id=experiment_id,
            adapter=adapter,
            tracker=tracker,
            temperature=temperature,
            no_retry=no_retry,
            tailscale_prompt_id=tailscale_prompt_id,
            tailscale_top_k=tailscale_top_k,
            stop_event=stop_event,
        )


def _drain_provider_pool(
    *,
    pool: ThreadPoolExecutor,
    calls: list[PlannedCall],
    max_in_flight: int,
    db_path,
    experiment_id: int,
    adapter,
    tracker: _ProgressTracker,
    temperature: float,
    no_retry: bool,
    tailscale_prompt_id: int | None,
    tailscale_top_k: int | None,
    stop_event: threading.Event,
) -> None:
    if not calls:
        return
    if adapter is None:
        raise ValueError(f"Missing provider adapter for {calls[0].provider}")
    pending_calls = iter(calls)
    futures: set[Future[None]] = set()

    def submit_next() -> bool:
        if stop_event.is_set():
            return False
        try:
            call = next(pending_calls)
        except StopIteration:
            return False
        futures.add(
            pool.submit(
                _execute_call,
                db_path=db_path,
                experiment_id=experiment_id,
                call=call,
                adapter=adapter,
                tracker=tracker,
                temperature=temperature,
                no_retry=no_retry,
                tailscale_prompt_id=tailscale_prompt_id,
                tailscale_top_k=tailscale_top_k,
            )
        )
        return True

    for _ in range(max_in_flight):
        if not submit_next():
            break

    while futures:
        done, futures = wait(futures, return_when=FIRST_COMPLETED)
        try:
            for future in done:
                future.result()
        except Exception:
            stop_event.set()
            for future in futures:
                future.cancel()
            raise
        if stop_event.is_set():
            for future in futures:
                future.cancel()
            return
        for _ in done:
            submit_next()


def _execute_call(
    *,
    db_path,
    experiment_id: int,
    call: PlannedCall,
    adapter,
    tracker: _ProgressTracker,
    temperature: float,
    no_retry: bool,
    tailscale_prompt_id: int | None,
    tailscale_top_k: int | None,
) -> None:
    conn = _get_thread_conn(db_path)
    try:
        _execute_call_with_conn(
            conn=conn,
            experiment_id=experiment_id,
            call=call,
            adapter=adapter,
            tracker=tracker,
            temperature=temperature,
            no_retry=no_retry,
            tailscale_prompt_id=tailscale_prompt_id,
            tailscale_top_k=tailscale_top_k,
        )
    except Exception:
        conn.rollback()
        raise


def _execute_call_with_conn(
    *,
    conn,
    experiment_id: int,
    call: PlannedCall,
    adapter,
    tracker: _ProgressTracker,
    temperature: float,
    no_retry: bool,
    tailscale_prompt_id: int | None,
    tailscale_top_k: int | None,
) -> None:
    question = db.get_question_by_pk(conn, call.question_pk)
    is_tailscale = call.provider == TAILSCALE_PROVIDER

    # Shared prompt regime: a single user message with English instructions,
    # the JSON output contract, and the Spanish question content. No system
    # role on either provider. TailScale ignores systems anyway; OpenRouter
    # carries the instruction in-message for symmetry.
    prompt = render_shared_prompt(question, prompt_version=call.prompt_version)
    messages = [{"role": "user", "content": prompt.user_prompt}]

    logical_call = db.get_or_create_logical_call(
        conn,
        experiment_id=experiment_id,
        question_pk=call.question_pk,
        provider=call.provider,
        model=call.model,
        run_index=call.run_index,
        prompt_version=prompt.version,
        system_prompt_sha256=prompt.system_sha256,
        user_prompt_sha256=prompt.user_sha256,
    )
    # Both providers get top_p=1 for symmetry. OpenRouter retains its
    # response_format: json_schema enforcement (TailScale does not honor
    # it per the API characterization). This is the one remaining
    # asymmetry between arms and is documented as such.
    request = ProviderRequest(
        provider=call.provider,
        model=call.model,
        messages=messages,
        temperature=temperature,
        top_p=1.0,
        stream=False,
        response_schema=(
            adapter.answer_schema()
            if getattr(adapter, "supports_response_schema", False)
            else None
        ),
        prompt_id=tailscale_prompt_id if is_tailscale else None,
        top_k=tailscale_top_k if is_tailscale else None,
    )
    # Wall-clock timer using monotonic_ns so laptop-sleep doesn't corrupt the
    # latency. Populates response.latency_ms IF the adapter didn't already set it.
    wall_t0 = time.monotonic_ns()
    response = adapter.chat_completion(request, retry=not no_retry)
    wall_ms = (time.monotonic_ns() - wall_t0) // 1_000_000
    if response.latency_ms is None:
        response.latency_ms = int(wall_ms)
    attempt_id = _store_provider_response_attempts(
        conn,
        logical_call_id=logical_call["id"],
        prompt=prompt,
        response=response,
    )
    if response.error_type is not None:
        tracker.tick_and_log(
            call=call,
            wall_ms=response.latency_ms,
            parse_status="—",
            selected_letter=None,
            correct_letter=str(question["correct_letter"]),
            strict_correct=None,
            api_error=response.error_type,
        )
        return

    parse_result = parse_openai_response(response.response_json, question)

    if parse_result.repair_needed:
        # With user-only prompts on both providers there is no system role
        # to inject a "fix your JSON" instruction into, so the model-side
        # repair call cannot improve behavior. Always fall through to the
        # deterministic regex fallback on the primary response text.
        parse_result = parse_with_fallback(
            response.response_json or response.response_body or "",
            question,
            repair_response=None,
        )

    score = _store_parse_and_score(conn, logical_call["id"], attempt_id, parse_result, question)
    tracker.tick_and_log(
        call=call,
        wall_ms=response.latency_ms,
        parse_status=parse_result.parse_status,
        selected_letter=parse_result.selected_letter,
        correct_letter=str(question["correct_letter"]),
        strict_correct=bool(score.strict_correct) if score is not None else None,
    )


def _store_provider_response_attempts(
    conn,
    *,
    logical_call_id: int,
    prompt,
    response: ProviderResponse,
) -> int:
    for intermediate in response.attempt_responses:
        _store_attempt(
            conn,
            logical_call_id=logical_call_id,
            prompt=prompt,
            response=intermediate,
        )
    return _store_attempt(
        conn,
        logical_call_id=logical_call_id,
        prompt=prompt,
        response=response,
    )


def _store_attempt(conn, *, logical_call_id: int, prompt, response: ProviderResponse) -> int:
    row = db.insert_provider_attempt(
        conn,
        logical_call_id=logical_call_id,
        prompt_version=prompt.version,
        system_prompt_sha256=prompt.system_sha256,
        user_prompt_sha256=prompt.user_sha256,
        request_json=response.request_json,
        request_headers_json=response.request_headers,
        prompt_id=response.prompt_id,
        top_k=response.top_k,
        status_code=response.status_code,
        response_body=response.response_body,
        response_json=response.response_json,
        latency_ms=response.latency_ms,
        finish_reason=response.finish_reason,
        prompt_tokens=response.prompt_tokens,
        completion_tokens=response.completion_tokens,
        total_tokens=response.total_tokens,
        error_type=response.error_type,
        error_message=response.error_message,
    )
    return row["id"]


def _store_parse_and_score(
    conn, logical_call_id: int, attempt_id: int, parse_result: ParseResult, question
) -> ScoreResult | None:
    parsed_id = db.insert_parsed_answer(
        conn,
        logical_call_id=logical_call_id,
        provider_attempt_id=attempt_id,
        parse_result=parse_result,
    )
    # Only score parses that resolved to a letter; otherwise scoring would be
    # meaningless (no letter to compare). Returning None lets the caller emit
    # a parse-failed progress line without claiming strict_correct=False.
    if parse_result.selected_letter is None:
        return None
    score = score_answer(parse_result, question)
    db.insert_score(
        conn,
        parsed_answer_id=parsed_id,
        correct_letter=question["correct_letter"],
        correct_option_text=question["correct_option_text"],
        letter_correct=score.letter_correct,
        text_correct=score.text_correct,
        strict_correct=score.strict_correct,
        lenient_correct=score.lenient_correct,
        answer_text_matches_provided=score.answer_text_matches_provided,
    )
    return score
