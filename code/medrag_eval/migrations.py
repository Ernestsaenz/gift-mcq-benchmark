from __future__ import annotations

import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS datasets (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  source_xlsx_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  row_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY,
  dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  question_id TEXT NOT NULL,
  region TEXT,
  year INTEGER,
  specialty TEXT,
  exam_part TEXT,
  question_number INTEGER,
  question_text TEXT NOT NULL,
  option_a TEXT NOT NULL,
  option_b TEXT NOT NULL,
  option_c TEXT NOT NULL,
  option_d TEXT NOT NULL,
  correct_letter TEXT NOT NULL,
  correct_option_text TEXT NOT NULL,
  source_row_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(dataset_id, question_id)
);

CREATE TABLE IF NOT EXISTS experiments (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  prompt_version TEXT NOT NULL,
  config_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logical_calls (
  id INTEGER PRIMARY KEY,
  experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
  question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  run_index INTEGER NOT NULL,
  prompt_version TEXT NOT NULL,
  system_prompt_sha256 TEXT NOT NULL DEFAULT '',
  user_prompt_sha256 TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  UNIQUE(experiment_id, question_id, provider, model, run_index, prompt_version)
);

CREATE TABLE IF NOT EXISTS provider_attempts (
  id INTEGER PRIMARY KEY,
  logical_call_id INTEGER NOT NULL REFERENCES logical_calls(id) ON DELETE CASCADE,
  attempt_index INTEGER NOT NULL,
  prompt_version TEXT,
  system_prompt_sha256 TEXT,
  user_prompt_sha256 TEXT,
  request_sha256 TEXT NOT NULL,
  request_json TEXT NOT NULL,
  request_headers_json TEXT,
  prompt_id INTEGER,
  top_k INTEGER,
  status_code INTEGER,
  response_body TEXT,
  response_json TEXT,
  latency_ms INTEGER,
  finish_reason TEXT,
  prompt_tokens INTEGER,
  completion_tokens INTEGER,
  total_tokens INTEGER,
  error_type TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL,
  UNIQUE(logical_call_id, attempt_index)
);

CREATE TABLE IF NOT EXISTS parsed_answers (
  id INTEGER PRIMARY KEY,
  logical_call_id INTEGER NOT NULL REFERENCES logical_calls(id) ON DELETE CASCADE,
  provider_attempt_id INTEGER REFERENCES provider_attempts(id) ON DELETE SET NULL,
  parser_version TEXT NOT NULL,
  parse_status TEXT NOT NULL,
  parse_method TEXT,
  selected_letter_raw TEXT,
  selected_option_text_raw TEXT,
  selected_letter TEXT,
  selected_option_text TEXT,
  exact_text_match INTEGER NOT NULL DEFAULT 0,
  letter_text_conflict INTEGER NOT NULL DEFAULT 0,
  notes TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scores (
  id INTEGER PRIMARY KEY,
  logical_call_id INTEGER NOT NULL REFERENCES logical_calls(id) ON DELETE CASCADE,
  parsed_answer_id INTEGER NOT NULL REFERENCES parsed_answers(id) ON DELETE CASCADE,
  correct_letter TEXT NOT NULL,
  correct_option_text TEXT NOT NULL,
  letter_correct INTEGER NOT NULL,
  text_correct INTEGER NOT NULL,
  strict_correct INTEGER NOT NULL,
  lenient_correct INTEGER NOT NULL,
  answer_text_matches_provided INTEGER NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_dataset_number
ON questions(dataset_id, question_number, id);

CREATE INDEX IF NOT EXISTS idx_logical_calls_identity
ON logical_calls(experiment_id, question_id, provider, model, run_index, prompt_version);

CREATE INDEX IF NOT EXISTS idx_provider_attempts_logical
ON provider_attempts(logical_call_id, attempt_index);

CREATE INDEX IF NOT EXISTS idx_parsed_answers_logical
ON parsed_answers(logical_call_id, id);

CREATE INDEX IF NOT EXISTS idx_scores_logical
ON scores(logical_call_id, parsed_answer_id);
"""


def apply_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    _ensure_column(conn, "provider_attempts", "prompt_version", "TEXT")
    _ensure_column(conn, "provider_attempts", "system_prompt_sha256", "TEXT")
    _ensure_column(conn, "provider_attempts", "user_prompt_sha256", "TEXT")
    _ensure_column(conn, "provider_attempts", "request_headers_json", "TEXT")
    _ensure_column(conn, "provider_attempts", "prompt_id", "INTEGER")
    _ensure_column(conn, "provider_attempts", "top_k", "INTEGER")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, declaration: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
