#!/usr/bin/env python3
"""Regenerate ledger/RUN_LEDGER.csv and ledger/ATTEMPT_TIMELINE.csv.

Sources (read-only, never modified):
  - .../replications/ab520-incorrect-cells-triplicate-2026-08-05/invocations/*.json
    (34 files) -> RUN_LEDGER.csv
  - .../replications/ab520-incorrect-cells-triplicate-2026-08-05/runs/
    ab520-incorrect-cell-triplicates-2026-08-05.sqlite (opened read-only via the
    file:...?mode=ro URI, per SPEC.md's note that `sqlite3 -readonly` fails on this
    machine) -> ATTEMPT_TIMELINE.csv

Run with: python3 build_ledger.py
Writes both CSVs into this script's own directory (ledger/), overwriting them.

Stdlib only: json, csv, sqlite3, pathlib.

NOTES column honesty note (see LEDGER_README.md section "Notes column
provenance" for the full explanation): the `notes` column in RUN_LEDGER.csv is
hand-authored narrative written after reading each invocation's log file and
comparing it against STATUS.md and the DB. It cannot be derived from the JSON/DB
alone -- no script can look at an aborted batch and know to write "queue-head
cell already exhausted, see STATUS.md's failed-resume-attempt section". Rather
than fake a derivation, this script stores that narrative as an explicit
literal dict (NOTES, below), keyed by invocation_id. That makes the mapping
itself reproducible and diffable even though the prose inside it was written by
a person (an LLM agent) reading the sources, not computed from them.
"""
import csv
import json
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (all resolved relative to this script, so it works regardless of cwd)
# ---------------------------------------------------------------------------
LEDGER_DIR = Path(__file__).resolve().parent
REPO_ROOT = LEDGER_DIR.parents[3]  # .../tier1_mcq

REPL_DIR = (
    REPO_ROOT
    / "data/experiment-4-aug-26/replications/ab520-incorrect-cells-triplicate-2026-08-05"
)
INV_DIR = REPL_DIR / "invocations"
DB_PATH = REPL_DIR / "runs/ab520-incorrect-cell-triplicates-2026-08-05.sqlite"

RUN_LEDGER_OUT = LEDGER_DIR / "RUN_LEDGER.csv"
ATTEMPT_TIMELINE_OUT = LEDGER_DIR / "ATTEMPT_TIMELINE.csv"

# ---------------------------------------------------------------------------
# RUN_LEDGER.csv
# ---------------------------------------------------------------------------

# Invocations confirmed -- via DB request_json inspection, not via the recorded
# command string, which is silent on this -- to have actually routed through
# Google Vertex. See LEDGER_README.md section 4 for the full discrepancy writeup.
DEVIATION_INVOCATIONS = {"or-b-gemini-vertex-run1", "or-b-gemini-vertex-TEST-4cells"}

# Hand-authored narrative, one entry per invocation_id. See module docstring.
NOTES = {
    "or-a-gemini-r2-r3-initial": "Zero provider calls issued; aborted immediately on OpenRouter authentication failure before any call was sent. All 18 target cells left not-started; retried successfully in or-a-gemini-r2-r3-run1 sixteen seconds later.",
    "or-a-gemini-r2-r3-run1": "Full run-1 retry after the authentication-failure abort; completed all 18 openrouter_A gemini cells.",
    "or-a-gemma-r2-r3-run1": "openrouter_A gemma, completed in one pass.",
    "or-a-glm-r2-r3-run1": "openrouter_A glm, completed in one pass.",
    "or-a-qwen-r2-r3-run1": "openrouter_A qwen, completed in one pass.",
    "or-b-gemini-probe-b323-r2": "Single-cell diagnostic probe against the shared OpenRouter/Google AI Studio pool for gemini_B; aborted on rate_limit_or_circuit_open. Not a scoring attempt for the batch.",
    "or-b-gemini-r2-r3-run1": "First full-batch attempt at openrouter_B gemini (concurrency 10); aborted after 10 calls, all rate-limited, on rate_limit_or_circuit_open. 90 cells left not-started.",
    "or-b-gemini-r2-r3-resume1": "Resume attempt at reduced concurrency 2; aborted after 2 calls, both rate-limited. 98 cells left not-started.",
    "or-b-gemini-probe-b101-r2-20260806": "Single-cell pool-availability probe next day (2026-08-06); aborted on rate_limit_or_circuit_open.",
    "or-b-gemini-r2-r3-resume2": "Second resume attempt at concurrency 2; aborted after 2 calls, both rate-limited. 98 cells left not-started.",
    "or-b-gemini-probe-b101-r2-retry2": "Repeat single-cell pool-availability probe; aborted on rate_limit_or_circuit_open.",
    "or-b-gemini-resume3-r1": "Round 1 of 6 in the bounded resume loop against openrouter_B gemini (see STATUS.md 'Failed resume attempt'). Banked 2 scores; queue-head cell (andalucia|2021|cuestionario-practico|117, r2+r3) exhausted at 5 attempts before this round started, meaning it was already unrecoverable entering the loop.",
    "or-b-gemini-resume3-r2": "Round 2 of 6; the executor's fixed queue order re-attacked the same head cell each round, aborting before reaching new cells. +0 scores; one additional cell pushed toward exhaustion.",
    "or-b-gemini-resume3-r3": "Round 3 of 6; same structural failure as rounds 2/4-6. +0 scores; a third cell (andalucia|2021|cuestionario-teorico|31) newly exhausted.",
    "or-b-gemini-resume3-r4": "Round 4 of 6; +0 scores; cuestionario-practico|140 run 3 newly exhausted.",
    "or-b-gemini-resume3-r5": "Round 5 of 6; +0 scores; cuestionario-teorico|31 run 2 newly exhausted.",
    "or-b-gemini-resume3-r6": "Round 6 of 6, loop abandoned after this round per STATUS.md. +0 scores; cuestionario-teorico|31 run 3 newly exhausted. Net effect of the 6-round loop: +2 scores banked, 5 additional cells pushed to the 5-attempt ceiling. Do not repeat this design (fixed queue order re-attacks the head cell every round).",
    "or-b-gemini-vertex-TEST-4cells": "PROTOCOL DEVIATION test batch (4 cells) confirming Google Vertex routing behavior before authorizing the full run. DB request_json shows provider.order[0]=google-vertex, require_parameters=false, allow_fallbacks=false, though this is not visible in the recorded redacted_command or log start-event plan (verified discrepancy — see LEDGER_README.md).",
    "or-b-gemini-vertex-run1": "PROTOCOL DEVIATION full run: openrouter_B gemini routed to Google Vertex at default temperature (temperature=0/top_p=1.0 silently dropped), authorized by the PI. Scored 87 of 87 executed; skipped 6 already-scored (2 real-temperature AI Studio cells collected 2026-08-05, plus cells banked by the resume loop); 7 cells entered already exhausted at the 5-attempt ceiling from prior rounds. Same discrepancy as vertex-TEST-4cells: the deviation flag does not appear in the recorded command string, but DB request_json confirms google-vertex routing with require_parameters=false.",
    "or-b-gemma-r2-r3-run1": "openrouter_B gemma, completed in one pass.",
    "or-b-glm-r2-r3-run1": "openrouter_B glm, completed in one pass.",
    "or-b-qwen-r2-r3-run1": "openrouter_B qwen, completed in one pass.",
    "ts-a-gemini-probe-b22-r2": "Single-cell probe/warm-up before the tailscale_A gemini batch; completed.",
    "ts-a-gemini-r2-r3-run1": "tailscale_A gemini, completed; 1 cell skipped as already scored by the preceding probe.",
    "ts-a-gemma-r2-r3-run1": "tailscale_A gemma at concurrency 5; aborted after three_consecutive_transport_failures having scored 103/162. Confirms concurrency finding: TailScale backend fails under request rate, not on particular questions. Remainder resumed in ts-a-gemma-r2-r3-run2 at concurrency 2.",
    "ts-a-gemma-r2-r3-run2": "Resume of the aborted gemma batch at reduced concurrency 2; completed all remaining 58 cells with zero failures, confirming concurrency 2-3 as the recommended bound for the TailScale backend.",
    "ts-a-glm-r2-r3-run1": "tailscale_A glm at concurrency 3; completed with 6 unresolved failures out of 40 executed (status completed_with_unresolved).",
    "ts-a-glm-r2-r3-retry1": "Retry pass over the 6 unresolved glm cells at concurrency 2; recovered 4 of 6, 2 still failing (status completed_with_unresolved).",
    "ts-a-glm-probe-b264-retry2": "Single-cell probe/retry pair targeting the last 2 unresolved glm cells; 1 of 2 scored, question b264 run 2 failed (status completed_with_unresolved).",
    "ts-a-glm-probe-b264-retry3": "Further retry of b264 run 2 alone; failed again (status completed_with_unresolved, 0 scored).",
    "ts-a-glm-probe-b264-retry4": "Further retry of b264 run 2 alone; failed again with 500 errors, four hanging ~150.1-150.2s per STATUS.md. This cell (tailscale_A/glm/b264/r2) is the one tailscale_A cell left unrecoverable at the 5-attempt ceiling.",
    "ts-a-qwen-r2-r3-run1": "tailscale_A qwen at concurrency 3; completed_with_unresolved, 97/98 scored, 1 failure.",
    "ts-a-qwen-r2-r3-retry1": "Retry of the single unresolved qwen cell; recovered successfully (1/1 scored). 97 cells skipped as already scored.",
    "ts-a-gemma-probe-b61-r3-retry1": "Single-cell retry of a previously-failed tailscale_A gemma cell (b61, run 3); completed.",
}

RUN_LEDGER_FIELDS = [
    "invocation_id", "arm", "condition", "model", "dataset", "experiment_id",
    "target_count", "concurrency", "start_time_utc", "end_time_utc", "status",
    "scored_count", "failure_count", "stop_reason", "not_started",
    "skipped_already_scored", "upstream_override", "deviation",
    "redacted_command", "log_path", "notes",
]


def build_run_ledger() -> int:
    rows = []
    for path in sorted(INV_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        inv_id = d["invocation_id"]
        deviation = inv_id in DEVIATION_INVOCATIONS
        if inv_id not in NOTES:
            raise ValueError(f"no NOTES entry for invocation_id={inv_id!r}; add one")
        rows.append({
            "invocation_id": inv_id,
            "arm": d["arm"],
            "condition": d["condition"],
            "model": d["model"],
            "dataset": d["dataset"],
            "experiment_id": d["experiment"],
            "target_count": d["target_count"],
            "concurrency": d["concurrency"],
            "start_time_utc": d["start_time_utc"],
            "end_time_utc": d["end_time_utc"],
            "status": d["status"],
            "scored_count": d["scored_count"],
            "failure_count": d["failure_count"],
            "stop_reason": d.get("stop_reason") or "",
            "not_started": d.get("not_started_after_abort", 0),
            "skipped_already_scored": d.get("skipped_already_scored", 0),
            "upstream_override": "google-vertex" if deviation else "",
            "deviation": "TRUE" if deviation else "FALSE",
            "redacted_command": d["redacted_command"],
            "log_path": d["log_path"],
            "notes": NOTES[inv_id],
        })

    rows.sort(key=lambda r: (r["start_time_utc"], r["invocation_id"]))

    with RUN_LEDGER_OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RUN_LEDGER_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    return len(rows)


# ---------------------------------------------------------------------------
# ATTEMPT_TIMELINE.csv
# ---------------------------------------------------------------------------

ATTEMPT_TIMELINE_SQL = """
SELECT
  pa.created_at AS created_at,
  CASE
    WHEN ex.name LIKE '%\\_or\\_A%' ESCAPE '\\' THEN 'openrouter_A'
    WHEN ex.name LIKE '%\\_or\\_B%' ESCAPE '\\' THEN 'openrouter_B'
    WHEN ex.name LIKE '%\\_ts\\_A%' ESCAPE '\\' THEN 'tailscale_A'
    ELSE 'UNKNOWN'
  END AS arm,
  lc.model AS model,
  q.question_id AS question_id,
  lc.run_index AS run_index,
  pa.attempt_index AS attempt_index,
  pa.status_code AS status_code,
  COALESCE(pa.error_type,'') AS error_type,
  pa.latency_ms AS latency_ms,
  CASE
    WHEN json_extract(pa.request_json,'$.provider.order[0]') IS NOT NULL
      THEN json_extract(pa.request_json,'$.provider.order[0]')
    WHEN lc.provider='openrouter' THEN 'google-ai-studio'
    ELSE ''
  END AS upstream,
  CASE WHEN EXISTS (
    SELECT 1 FROM parsed_answers paw JOIN scores s ON s.parsed_answer_id = paw.id
    WHERE paw.provider_attempt_id = pa.id
  ) THEN 'TRUE' ELSE 'FALSE' END AS scored
FROM provider_attempts pa
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN experiments ex ON ex.id = lc.experiment_id
JOIN questions q ON q.id = lc.question_id
ORDER BY pa.created_at, pa.id
"""

ATTEMPT_TIMELINE_FIELDS = [
    "created_at", "arm", "model", "question_id", "run_index", "attempt_index",
    "status_code", "error_type", "latency_ms", "upstream", "scored",
]


def _sqlite_csv_field(value) -> str:
    """Render one field the way `sqlite3 <db>` in `.mode csv` does.

    SQL NULL -> empty, unquoted (distinguishes it from an empty string).
    Empty string -> quoted `""` (distinguishes it from NULL).
    Anything containing a comma, quote, or newline -> quoted, with embedded
    quotes doubled. Everything else -> printed as-is, unquoted.
    This is not the Python csv module's default QUOTE_MINIMAL behaviour --
    QUOTE_MINIMAL leaves empty strings unquoted, so a plain csv.writer would
    not reproduce the SQLite CLI's output for the empty-string columns
    (error_type, upstream) in this table. Reproduced by hand here instead of
    faking it with a stdlib option that doesn't have this mode.
    """
    if value is None:
        return ""
    s = str(value)
    if s == "" or any(ch in s for ch in (",", '"', "\n", "\r")):
        return '"' + s.replace('"', '""') + '"'
    return s


def build_attempt_timeline() -> int:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cur = con.execute(ATTEMPT_TIMELINE_SQL)
        rows = cur.fetchall()
    finally:
        con.close()

    # SQLite CLI's .mode csv uses RFC4180 CRLF line endings; the original
    # ATTEMPT_TIMELINE.csv (generated via the sqlite3 CLI) has them too.
    with ATTEMPT_TIMELINE_OUT.open("w", newline="") as f:
        f.write(",".join(ATTEMPT_TIMELINE_FIELDS) + "\r\n")
        for row in rows:
            f.write(",".join(_sqlite_csv_field(v) for v in row) + "\r\n")

    return len(rows)


if __name__ == "__main__":
    n_ledger = build_run_ledger()
    n_timeline = build_attempt_timeline()
    print(f"RUN_LEDGER.csv: {n_ledger} rows -> {RUN_LEDGER_OUT}")
    print(f"ATTEMPT_TIMELINE.csv: {n_timeline} rows -> {ATTEMPT_TIMELINE_OUT}")
