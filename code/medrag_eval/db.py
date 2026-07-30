from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import DEFAULT_DB_PATH
from .migrations import apply_migrations


COMPLETE_PARSE_STATUSES = frozenset({"ok", "ok_conflict"})

SUMMARY_COLUMNS = [
    "experiment_name",
    "dataset_name",
    "question_id",
    "region",
    "year",
    "specialty",
    "exam_part",
    "question_number",
    "provider",
    "model",
    "run_index",
    "prompt_version",
    "selected_letter",
    "selected_option_text",
    "correct_letter",
    "correct_option_text",
    "letter_correct",
    "text_correct",
    "strict_correct",
    "lenient_correct",
    "letter_text_conflict",
    "parse_status",
    "parse_method",
    "api_status_code",
    "latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "created_at",
]


RAW_COLUMNS = [
    "provider_call_id",
    "logical_call_id",
    "experiment_name",
    "question_id",
    "provider",
    "model",
    "run_index",
    "attempt_index",
    "request_json",
    "request_headers_json",
    "prompt_id",
    "top_k",
    "response_body",
    "status_code",
    "latency_ms",
    "error_type",
    "error_message",
    "created_at",
]


PROVIDER_ALIASES = {
    "tailscale": "tailscale_medical_rag",
    "tailscale_medical_rag": "tailscale_medical_rag",
    "openrouter": "openrouter",
}


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    is_memory = str(db_path) == ":memory:"
    if not is_memory:
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        path if not is_memory else ":memory:",
        timeout=30,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if not is_memory:
        conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA wal_autocheckpoint = 1000")
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        apply_migrations(conn)


def upsert_dataset(
    conn: sqlite3.Connection,
    name: str,
    source_xlsx_path: str,
    row_count: int,
) -> sqlite3.Row:
    now = utc_now()
    conn.execute(
        """
        INSERT INTO datasets(name, source_xlsx_path, row_count, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
          source_xlsx_path = excluded.source_xlsx_path,
          row_count = excluded.row_count
        """,
        (name, source_xlsx_path, int(row_count), now),
    )
    conn.commit()
    row = get_dataset(conn, name)
    if row is None:
        raise RuntimeError(f"Dataset upsert failed: {name}")
    return row


def get_dataset(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM datasets WHERE name = ?", (name,)).fetchone()


def insert_question(conn: sqlite3.Connection, dataset_id: int | sqlite3.Row, question: Any) -> sqlite3.Row:
    values = _coerce_question(question)
    dataset_pk = _row_id(dataset_id)
    conn.execute(
        """
        INSERT INTO questions(
          dataset_id, question_id, region, year, specialty, exam_part,
          question_number, question_text, option_a, option_b, option_c, option_d,
          correct_letter, correct_option_text, source_row_json, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            dataset_pk,
            values["question_id"],
            values.get("region"),
            values.get("year"),
            values.get("specialty"),
            values.get("exam_part"),
            values.get("question_number"),
            values["question_text"],
            values["option_a"],
            values["option_b"],
            values["option_c"],
            values["option_d"],
            values["correct_letter"],
            values["correct_option_text"],
            values["source_row_json"],
            utc_now(),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM questions WHERE dataset_id = ? AND question_id = ?",
        (dataset_pk, values["question_id"]),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"Question insert failed: {values['question_id']}")
    return row


def replace_questions(conn: sqlite3.Connection, dataset_id: int | sqlite3.Row, questions: list[Any]) -> list[sqlite3.Row]:
    dataset_pk = _row_id(dataset_id)
    conn.execute("DELETE FROM questions WHERE dataset_id = ?", (dataset_pk,))
    conn.commit()
    return [insert_question(conn, dataset_pk, question) for question in questions]


def list_questions(
    conn: sqlite3.Connection,
    dataset_id: int | sqlite3.Row,
    *,
    limit: int | None = None,
    offset: int = 0,
    question_id: str | None = None,
) -> list[sqlite3.Row]:
    params: list[Any] = [_row_id(dataset_id)]
    sql = "SELECT * FROM questions WHERE dataset_id = ?"
    if question_id is not None:
        sql += " AND question_id = ?"
        params.append(question_id)
    sql += " ORDER BY question_number, id"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([int(limit), int(offset)])
    elif offset:
        sql += " LIMIT -1 OFFSET ?"
        params.append(int(offset))
    return list(conn.execute(sql, params))


def get_question_by_pk(conn: sqlite3.Connection, question_pk: int | sqlite3.Row) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (_row_id(question_pk),)).fetchone()
    if row is None:
        raise KeyError(f"Question not found: {_row_id(question_pk)}")
    return row


def question_options(question: sqlite3.Row | dict[str, Any]) -> dict[str, str]:
    return {
        "a": question["option_a"],
        "b": question["option_b"],
        "c": question["option_c"],
        "d": question["option_d"],
    }


def create_experiment(
    conn: sqlite3.Connection,
    *,
    name: str,
    dataset_id: int | sqlite3.Row,
    prompt_version: str,
    config_json: dict[str, Any] | str,
) -> sqlite3.Row:
    conn.execute(
        """
        INSERT INTO experiments(name, dataset_id, prompt_version, config_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, _row_id(dataset_id), prompt_version, _json_text(config_json), utc_now()),
    )
    conn.commit()
    row = get_experiment(conn, name)
    if row is None:
        raise RuntimeError(f"Experiment insert failed: {name}")
    return row


def get_experiment(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM experiments WHERE name = ?", (name,)).fetchone()


def get_or_create_experiment(
    conn: sqlite3.Connection,
    *,
    name: str,
    dataset_id: int | sqlite3.Row,
    prompt_version: str,
    config_json: dict[str, Any] | str,
) -> sqlite3.Row:
    existing = get_experiment(conn, name)
    if existing is not None:
        return existing
    return create_experiment(
        conn,
        name=name,
        dataset_id=dataset_id,
        prompt_version=prompt_version,
        config_json=config_json,
    )


def create_logical_call(
    conn: sqlite3.Connection,
    *,
    experiment_id: int | sqlite3.Row,
    question_id: int | sqlite3.Row,
    provider: str,
    model: str,
    run_index: int,
    prompt_version: str,
    system_prompt_sha256: str = "",
    user_prompt_sha256: str = "",
) -> sqlite3.Row:
    experiment_pk = _row_id(experiment_id)
    question_pk = _row_id(question_id)
    provider_name = normalize_provider(provider)
    conn.execute(
        """
        INSERT INTO logical_calls(
          experiment_id, question_id, provider, model, run_index, prompt_version,
          system_prompt_sha256, user_prompt_sha256, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(experiment_id, question_id, provider, model, run_index, prompt_version)
        DO UPDATE SET
          system_prompt_sha256 = COALESCE(NULLIF(excluded.system_prompt_sha256, ''), logical_calls.system_prompt_sha256),
          user_prompt_sha256 = COALESCE(NULLIF(excluded.user_prompt_sha256, ''), logical_calls.user_prompt_sha256)
        """,
        (
            experiment_pk,
            question_pk,
            provider_name,
            model,
            int(run_index),
            prompt_version,
            system_prompt_sha256,
            user_prompt_sha256,
            utc_now(),
        ),
    )
    conn.commit()
    row = _find_logical_call(
        conn,
        experiment_id=experiment_pk,
        question_id=question_pk,
        provider=provider_name,
        model=model,
        run_index=run_index,
        prompt_version=prompt_version,
    )
    if row is None:
        raise RuntimeError("Logical call upsert failed")
    return row


def get_or_create_logical_call(
    conn: sqlite3.Connection,
    *,
    experiment_id: int | sqlite3.Row,
    question_pk: int | sqlite3.Row,
    provider: str,
    model: str,
    run_index: int,
    prompt_version: str,
    system_prompt_sha256: str = "",
    user_prompt_sha256: str = "",
) -> sqlite3.Row:
    return create_logical_call(
        conn,
        experiment_id=experiment_id,
        question_id=question_pk,
        provider=provider,
        model=model,
        run_index=run_index,
        prompt_version=prompt_version,
        system_prompt_sha256=system_prompt_sha256,
        user_prompt_sha256=user_prompt_sha256,
    )


def insert_provider_attempt(
    conn: sqlite3.Connection,
    *,
    logical_call_id: int | sqlite3.Row,
    request_sha256: str | None = None,
    request_json: Any = None,
    request_headers_json: Any = None,
    prompt_id: int | None = None,
    top_k: int | None = None,
    status_code: int | None = None,
    response_body: str | None = None,
    response_json: Any = None,
    latency_ms: int | None = None,
    finish_reason: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    prompt_version: str | None = None,
    system_prompt_sha256: str | None = None,
    user_prompt_sha256: str | None = None,
) -> sqlite3.Row:
    request_text = _json_text({} if request_json is None else request_json)
    request_digest = request_sha256 or hashlib.sha256(request_text.encode("utf-8")).hexdigest()
    headers_text = (
        _json_text(request_headers_json) if request_headers_json is not None else None
    )
    logical_call_pk = _row_id(logical_call_id)
    cur = conn.execute(
        """
        INSERT INTO provider_attempts(
          logical_call_id, attempt_index, prompt_version, system_prompt_sha256,
          user_prompt_sha256, request_sha256, request_json, request_headers_json,
          prompt_id, top_k, status_code,
          response_body, response_json, latency_ms, finish_reason,
          prompt_tokens, completion_tokens, total_tokens, error_type,
          error_message, created_at
        )
        SELECT
          ?,
          COALESCE(MAX(attempt_index), 0) + 1,
          ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        FROM provider_attempts
        WHERE logical_call_id = ?
        """,
        (
            logical_call_pk,
            prompt_version,
            system_prompt_sha256,
            user_prompt_sha256,
            request_digest,
            request_text,
            headers_text,
            int(prompt_id) if prompt_id is not None else None,
            int(top_k) if top_k is not None else None,
            status_code,
            response_body,
            _json_text(response_json) if response_json is not None else None,
            latency_ms,
            finish_reason,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            error_type,
            error_message,
            utc_now(),
            logical_call_pk,
        ),
    )
    new_id = cur.lastrowid
    conn.commit()
    if new_id is None:
        raise RuntimeError("Provider attempt insert failed")
    row = conn.execute(
        """
        SELECT * FROM provider_attempts
        WHERE id = ?
        """,
        (new_id,),
    ).fetchone()
    if row is None:
        raise RuntimeError("Provider attempt insert failed")
    return row


def list_provider_attempts(conn: sqlite3.Connection, logical_call_id: int | sqlite3.Row) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM provider_attempts WHERE logical_call_id = ? ORDER BY attempt_index, id",
            (_row_id(logical_call_id),),
        )
    )


def insert_parsed_answer(
    conn: sqlite3.Connection,
    *,
    logical_call_id: int | sqlite3.Row,
    provider_attempt_id: int | sqlite3.Row | None = None,
    parser_version: str = "parser_v1",
    parse_status: str | None = None,
    parse_method: str | None = None,
    selected_letter_raw: str | None = None,
    selected_option_text_raw: str | None = None,
    selected_letter: str | None = None,
    selected_option_text: str | None = None,
    exact_text_match: bool | int = False,
    letter_text_conflict: bool | int = False,
    notes: str | None = None,
    parse_result: Any = None,
) -> sqlite3.Row:
    if parse_result is not None:
        parser_version = getattr(parse_result, "parser_version", parser_version)
        parse_status = getattr(parse_result, "parse_status", parse_status)
        parse_method = getattr(parse_result, "parse_method", parse_method)
        selected_letter_raw = getattr(parse_result, "selected_letter_raw", selected_letter_raw)
        selected_option_text_raw = getattr(parse_result, "selected_option_text_raw", selected_option_text_raw)
        selected_letter = getattr(parse_result, "selected_letter", selected_letter)
        selected_option_text = getattr(parse_result, "selected_option_text", selected_option_text)
        exact_text_match = getattr(parse_result, "exact_text_match", exact_text_match)
        letter_text_conflict = getattr(parse_result, "letter_text_conflict", letter_text_conflict)
        notes = getattr(parse_result, "notes", notes)
    if parse_status is None:
        raise ValueError("parse_status is required")
    conn.execute(
        """
        INSERT INTO parsed_answers(
          logical_call_id, provider_attempt_id, parser_version, parse_status,
          parse_method, selected_letter_raw, selected_option_text_raw,
          selected_letter, selected_option_text, exact_text_match,
          letter_text_conflict, notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _row_id(logical_call_id),
            _row_id(provider_attempt_id) if provider_attempt_id is not None else None,
            parser_version,
            parse_status,
            parse_method,
            selected_letter_raw,
            selected_option_text_raw,
            selected_letter,
            selected_option_text,
            _bool_int(exact_text_match),
            _bool_int(letter_text_conflict),
            notes,
            utc_now(),
        ),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return _get_by_id(conn, "parsed_answers", row_id)


def insert_score(
    conn: sqlite3.Connection,
    *,
    parsed_answer_id: int | sqlite3.Row,
    correct_letter: str | None = None,
    correct_option_text: str | None = None,
    letter_correct: bool | int | None = None,
    text_correct: bool | int | None = None,
    strict_correct: bool | int | None = None,
    lenient_correct: bool | int | None = None,
    answer_text_matches_provided: bool | int | None = None,
    score: Any = None,
) -> sqlite3.Row:
    if score is not None:
        correct_letter = getattr(score, "correct_letter", correct_letter)
        correct_option_text = getattr(score, "correct_option_text", correct_option_text)
        letter_correct = getattr(score, "letter_correct", letter_correct)
        text_correct = getattr(score, "text_correct", text_correct)
        strict_correct = getattr(score, "strict_correct", strict_correct)
        lenient_correct = getattr(score, "lenient_correct", lenient_correct)
        answer_text_matches_provided = getattr(
            score,
            "answer_text_matches_provided",
            answer_text_matches_provided,
        )
    required = {
        "correct_letter": correct_letter,
        "correct_option_text": correct_option_text,
        "letter_correct": letter_correct,
        "text_correct": text_correct,
        "strict_correct": strict_correct,
        "lenient_correct": lenient_correct,
        "answer_text_matches_provided": answer_text_matches_provided,
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        raise ValueError(f"Missing score fields: {', '.join(missing)}")
    parsed = _get_by_id(conn, "parsed_answers", _row_id(parsed_answer_id))
    conn.execute(
        """
        INSERT INTO scores(
          logical_call_id, parsed_answer_id, correct_letter, correct_option_text,
          letter_correct, text_correct, strict_correct, lenient_correct,
          answer_text_matches_provided, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parsed["logical_call_id"],
            parsed["id"],
            correct_letter,
            correct_option_text,
            _bool_int(letter_correct),
            _bool_int(text_correct),
            _bool_int(strict_correct),
            _bool_int(lenient_correct),
            _bool_int(answer_text_matches_provided),
            utc_now(),
        ),
    )
    conn.commit()
    row_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return _get_by_id(conn, "scores", row_id)


def is_logical_call_complete(conn: sqlite3.Connection, logical_call_id: int | sqlite3.Row) -> bool:
    parsed = conn.execute(
        """
        SELECT * FROM parsed_answers
        WHERE logical_call_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (_row_id(logical_call_id),),
    ).fetchone()
    if parsed is None or parsed["parse_status"] not in COMPLETE_PARSE_STATUSES:
        return False
    attempt_id = parsed["provider_attempt_id"]
    if attempt_id is None:
        return False
    attempt = conn.execute("SELECT * FROM provider_attempts WHERE id = ?", (attempt_id,)).fetchone()
    return attempt is not None and attempt["error_type"] is None


def get_completed_logical_call(
    conn: sqlite3.Connection,
    *,
    experiment_id: int | sqlite3.Row,
    question_id: int | sqlite3.Row,
    provider: str,
    model: str,
    run_index: int,
    prompt_version: str,
) -> sqlite3.Row | None:
    logical_call = _find_logical_call(
        conn,
        experiment_id=_row_id(experiment_id),
        question_id=_row_id(question_id),
        provider=normalize_provider(provider),
        model=model,
        run_index=run_index,
        prompt_version=prompt_version,
    )
    if logical_call is None:
        return None
    return logical_call if is_logical_call_complete(conn, logical_call["id"]) else None


def has_completed_logical_call(
    conn: sqlite3.Connection,
    *,
    experiment_id: int | sqlite3.Row,
    question_pk: int | sqlite3.Row,
    provider: str,
    model: str,
    run_index: int,
    prompt_version: str,
) -> bool:
    return (
        get_completed_logical_call(
            conn,
            experiment_id=experiment_id,
            question_id=question_pk,
            provider=provider,
            model=model,
            run_index=run_index,
            prompt_version=prompt_version,
        )
        is not None
    )


def normalize_provider(provider: str) -> str:
    return PROVIDER_ALIASES.get(provider, provider)


def summary_rows(conn: sqlite3.Connection, experiment_name: str) -> list[sqlite3.Row]:
    return list(conn.execute(_SUMMARY_SQL, (experiment_name,)))


def raw_attempt_rows(conn: sqlite3.Connection, experiment_name: str) -> list[sqlite3.Row]:
    return list(conn.execute(_RAW_SQL, (experiment_name,)))


def status_rows(conn: sqlite3.Connection, experiment_name: str) -> list[sqlite3.Row]:
    return list(conn.execute(_STATUS_ROWS_SQL, (experiment_name,)))


def status_totals(conn: sqlite3.Connection, experiment_name: str) -> sqlite3.Row:
    row = conn.execute(_STATUS_TOTALS_SQL, (experiment_name,)).fetchone()
    if row is None:
        return _dict_row(conn, {"planned": 0, "completed": 0, "api_failed": 0, "parse_failed": 0, "skipped_by_resume": 0})
    return row


def inspect_logical_call(conn: sqlite3.Connection, call_id: int | sqlite3.Row) -> dict[str, Any]:
    logical_call = _get_by_id(conn, "logical_calls", _row_id(call_id))
    attempts = [dict(row) for row in list_provider_attempts(conn, logical_call["id"])]
    parsed_answers = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM parsed_answers WHERE logical_call_id = ? ORDER BY id",
            (logical_call["id"],),
        )
    ]
    scores = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM scores WHERE logical_call_id = ? ORDER BY id",
            (logical_call["id"],),
        )
    ]
    return {
        "logical_call": dict(logical_call),
        "attempts": attempts,
        "parsed_answers": parsed_answers,
        "scores": scores,
    }


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _find_logical_call(
    conn: sqlite3.Connection,
    *,
    experiment_id: int,
    question_id: int,
    provider: str,
    model: str,
    run_index: int,
    prompt_version: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM logical_calls
        WHERE experiment_id = ?
          AND question_id = ?
          AND provider = ?
          AND model = ?
          AND run_index = ?
          AND prompt_version = ?
        """,
        (experiment_id, question_id, provider, model, int(run_index), prompt_version),
    ).fetchone()


def _coerce_question(question: Any) -> dict[str, Any]:
    if isinstance(question, sqlite3.Row):
        return dict(question)
    if isinstance(question, dict):
        values = dict(question)
    else:
        values = {
            "question_id": getattr(question, "question_id"),
            "region": getattr(question, "region", None),
            "year": getattr(question, "year", None),
            "specialty": getattr(question, "specialty", None),
            "exam_part": getattr(question, "exam_part", None),
            "question_number": getattr(question, "question_number", None),
            "question_text": getattr(question, "question_text"),
            "correct_letter": getattr(question, "correct_letter"),
            "correct_option_text": getattr(question, "correct_option_text"),
            "source_row_json": getattr(question, "source_row_json", None),
        }
        options = getattr(question, "options", None)
        if options is not None:
            values.update({f"option_{letter}": options[letter] for letter in "abcd"})
        else:
            values.update({f"option_{letter}": getattr(question, f"option_{letter}") for letter in "abcd"})
    if "source_row_json" not in values or values["source_row_json"] is None:
        values["source_row_json"] = _json_text(values)
    elif not isinstance(values["source_row_json"], str):
        values["source_row_json"] = _json_text(values["source_row_json"])
    values["correct_letter"] = values["correct_letter"].lower()
    return values


def _json_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row_id(value: int | sqlite3.Row | None) -> int:
    if isinstance(value, sqlite3.Row):
        return int(value["id"])
    if value is None:
        raise ValueError("Expected row id, got None")
    return int(value)


def _get_by_id(conn: sqlite3.Connection, table_name: str, row_id: int) -> sqlite3.Row:
    if table_name not in {"parsed_answers", "scores", "logical_calls", "provider_attempts"}:
        raise ValueError(f"Unsupported table lookup: {table_name}")
    row = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise KeyError(f"{table_name} row not found: {row_id}")
    return row


def _bool_int(value: bool | int | None) -> int:
    return 1 if bool(value) else 0


def _dict_row(conn: sqlite3.Connection, values: dict[str, Any]) -> sqlite3.Row:
    # Column names are interpolated into SQL via f-string, so they must be
    # safe identifiers. Current callers pass hardcoded keys; this guard
    # protects future callers from accidentally enabling column-name injection.
    for key in values:
        if not isinstance(key, str) or not key.isidentifier():
            raise ValueError(f"Unsafe column name in _dict_row: {key!r}")
    columns = ", ".join(f"? AS {key}" for key in values)
    return conn.execute(f"SELECT {columns}", tuple(values.values())).fetchone()


_SUMMARY_SQL = """
WITH latest_attempt AS (
  SELECT a.*
  FROM provider_attempts a
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM provider_attempts
    GROUP BY logical_call_id
  ) latest ON latest.id = a.id
),
latest_parse AS (
  SELECT p.*
  FROM parsed_answers p
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM parsed_answers
    GROUP BY logical_call_id
  ) latest ON latest.id = p.id
),
latest_score AS (
  SELECT s.*
  FROM scores s
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM scores
    GROUP BY logical_call_id
  ) latest ON latest.id = s.id
)
SELECT
  e.name AS experiment_name,
  d.name AS dataset_name,
  q.question_id,
  q.region,
  q.year,
  q.specialty,
  q.exam_part,
  q.question_number,
  lc.provider,
  lc.model,
  lc.run_index,
  lc.prompt_version,
  p.selected_letter,
  p.selected_option_text,
  q.correct_letter,
  q.correct_option_text,
  s.letter_correct,
  s.text_correct,
  s.strict_correct,
  s.lenient_correct,
  p.letter_text_conflict,
  p.parse_status,
  p.parse_method,
  a.status_code AS api_status_code,
  a.latency_ms,
  a.prompt_tokens,
  a.completion_tokens,
  a.total_tokens,
  COALESCE(p.created_at, a.created_at, lc.created_at) AS created_at
FROM logical_calls lc
JOIN experiments e ON e.id = lc.experiment_id
JOIN datasets d ON d.id = e.dataset_id
JOIN questions q ON q.id = lc.question_id
LEFT JOIN latest_attempt a ON a.logical_call_id = lc.id
LEFT JOIN latest_parse p ON p.logical_call_id = lc.id
LEFT JOIN latest_score s ON s.logical_call_id = lc.id
WHERE e.name = ?
ORDER BY q.question_number, lc.provider, lc.model, lc.run_index
"""


_RAW_SQL = """
SELECT
  a.id AS provider_call_id,
  lc.id AS logical_call_id,
  e.name AS experiment_name,
  q.question_id,
  lc.provider,
  lc.model,
  lc.run_index,
  a.attempt_index,
  a.prompt_version,
  a.request_json,
  a.request_headers_json,
  a.prompt_id,
  a.top_k,
  a.response_body,
  a.status_code,
  a.latency_ms,
  a.error_type,
  a.error_message,
  a.created_at
FROM provider_attempts a
JOIN logical_calls lc ON lc.id = a.logical_call_id
JOIN experiments e ON e.id = lc.experiment_id
JOIN questions q ON q.id = lc.question_id
WHERE e.name = ?
ORDER BY q.question_number, lc.provider, lc.model, lc.run_index, a.attempt_index
"""


_STATUS_ROWS_SQL = """
WITH latest_attempt AS (
  SELECT a.*
  FROM provider_attempts a
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM provider_attempts
    GROUP BY logical_call_id
  ) latest ON latest.id = a.id
),
latest_parse AS (
  SELECT p.*
  FROM parsed_answers p
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM parsed_answers
    GROUP BY logical_call_id
  ) latest ON latest.id = p.id
),
latest_score AS (
  SELECT s.*
  FROM scores s
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM scores
    GROUP BY logical_call_id
  ) latest ON latest.id = s.id
)
SELECT
  lc.provider,
  lc.model,
  COUNT(*) AS calls,
  AVG(CASE WHEN p.parse_status IN ('ok', 'ok_conflict') THEN 1.0 ELSE 0.0 END) AS parse_success_rate,
  AVG(CASE WHEN p.parse_status IN ('ok', 'ok_conflict') THEN s.strict_correct ELSE NULL END) AS strict_accuracy,
  AVG(a.latency_ms) AS mean_latency_ms
FROM logical_calls lc
JOIN experiments e ON e.id = lc.experiment_id
LEFT JOIN latest_attempt a ON a.logical_call_id = lc.id
LEFT JOIN latest_parse p ON p.logical_call_id = lc.id
LEFT JOIN latest_score s ON s.logical_call_id = lc.id
WHERE e.name = ?
GROUP BY lc.provider, lc.model
ORDER BY lc.provider, lc.model
"""


_STATUS_TOTALS_SQL = """
WITH latest_attempt AS (
  SELECT a.*
  FROM provider_attempts a
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM provider_attempts
    GROUP BY logical_call_id
  ) latest ON latest.id = a.id
),
latest_parse AS (
  SELECT p.*
  FROM parsed_answers p
  JOIN (
    SELECT logical_call_id, MAX(id) AS id
    FROM parsed_answers
    GROUP BY logical_call_id
  ) latest ON latest.id = p.id
)
SELECT
  COUNT(*) AS planned,
  SUM(CASE WHEN p.parse_status IN ('ok', 'ok_conflict') AND a.error_type IS NULL THEN 1 ELSE 0 END) AS completed,
  SUM(CASE WHEN a.error_type IS NOT NULL THEN 1 ELSE 0 END) AS api_failed,
  SUM(CASE WHEN p.parse_status IS NOT NULL AND p.parse_status NOT IN ('ok', 'ok_conflict') THEN 1 ELSE 0 END) AS parse_failed,
  0 AS skipped_by_resume
FROM logical_calls lc
JOIN experiments e ON e.id = lc.experiment_id
LEFT JOIN latest_attempt a ON a.logical_call_id = lc.id
LEFT JOIN latest_parse p ON p.logical_call_id = lc.id
WHERE e.name = ?
"""
