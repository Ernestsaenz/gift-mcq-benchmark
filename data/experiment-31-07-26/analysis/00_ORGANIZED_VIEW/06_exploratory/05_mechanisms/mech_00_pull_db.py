"""Pull per-cell provider metadata (READ-ONLY) for the effort analysis.

For each (experiment, model, question_id) in the openrouter arm we take the
LAST provider_attempt (highest attempt_index) -- that is the attempt that
produced the scored answer -- and record completion_tokens, latency_ms,
finish_reason, created_at, prompt_tokens, and the raw response text length.

Writes a JSON cache next to this script so downstream mech_ scripts do not
re-hit the DB.
"""
import sqlite3, json, os

DB = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
      "experiment-31-07-26/experiment.sqlite")
OUT = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
       "experiment-31-07-26/analysis/mech_db_cells.json")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

q = """
SELECT e.name AS exp, lc.model AS model, q.question_id AS qid,
       pa.attempt_index, pa.completion_tokens, pa.prompt_tokens,
       pa.latency_ms, pa.finish_reason, pa.created_at, pa.status_code,
       LENGTH(pa.response_body) AS body_len,
       pas.parse_status, pas.selected_letter, pas.selected_option_text
FROM provider_attempts pa
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN experiments  e  ON e.id  = lc.experiment_id
JOIN questions    q  ON q.id  = lc.question_id
LEFT JOIN parsed_answers pas ON pas.provider_attempt_id = pa.id
WHERE e.name IN ('expA_or_310726','expB_or_310726')
ORDER BY e.name, lc.model, q.question_id, pa.attempt_index
"""
best = {}
n_attempts = 0
for r in con.execute(q):
    n_attempts += 1
    k = (r["exp"], r["model"], r["qid"])
    prev = best.get(k)
    if prev is None or r["attempt_index"] > prev["attempt_index"]:
        best[k] = dict(r)

# also pull option/question text for both datasets
texts = {}
for r in con.execute("""
    SELECT d.name AS ds, q.question_id AS qid, q.question_text, q.option_a,
           q.option_b, q.option_c, q.option_d, q.correct_letter,
           q.correct_option_text
    FROM questions q JOIN datasets d ON d.id = q.dataset_id
    WHERE d.name IN ('balanced_a_310726','balanced_b_310726')"""):
    texts[(r["ds"], r["qid"])] = dict(r)

json.dump({"cells": [{"key": list(k), **v} for k, v in best.items()],
           "texts": [{"key": list(k), **v} for k, v in texts.items()]},
          open(OUT, "w"))
print("attempts scanned:", n_attempts, " final-attempt cells:", len(best),
      " question texts:", len(texts))
print("written:", OUT)
