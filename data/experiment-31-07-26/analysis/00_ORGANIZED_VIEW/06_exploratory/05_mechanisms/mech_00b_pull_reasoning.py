"""Re-pull per-cell metadata, this time splitting completion_tokens into
reasoning tokens and answer tokens.

Why this matters: the answer format is a JSON object that ECHOES the chosen
option's text --
    {"question_id": "...", "selected_letter": "c",
     "selected_option_text": "<full text of the chosen option>"}
so raw completion_tokens confounds deliberation with the character length of
whatever option the model picked.  OpenRouter reports
usage.completion_tokens_details.reasoning_tokens, which isolates the thinking
trace.  answer_tokens = completion_tokens - reasoning_tokens.
"""
import sqlite3, json

DB = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
      "experiment-31-07-26/experiment.sqlite")
OUT = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
       "experiment-31-07-26/analysis/mech_db_reasoning.json")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

q = """
SELECT e.name AS exp, lc.model AS model, q.question_id AS qid,
       pa.attempt_index, pa.completion_tokens, pa.latency_ms,
       pa.finish_reason, pa.created_at, pa.response_json
FROM provider_attempts pa
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN experiments  e  ON e.id  = lc.experiment_id
JOIN questions    q  ON q.id  = lc.question_id
WHERE e.name IN ('expA_or_310726','expB_or_310726')
ORDER BY e.name, lc.model, q.question_id, pa.attempt_index
"""
best = {}
for r in con.execute(q):
    k = (r["exp"], r["model"], r["qid"])
    if k in best and best[k]["attempt_index"] >= r["attempt_index"]:
        continue
    rt = None
    content = reasoning = ""
    try:
        j = json.loads(r["response_json"])
        u = j.get("usage") or {}
        d = u.get("completion_tokens_details") or {}
        rt = d.get("reasoning_tokens")
        msg = j["choices"][0]["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning") or ""
    except Exception:
        pass
    sel_text = ""
    try:
        sel_text = json.loads(content).get("selected_option_text") or ""
    except Exception:
        pass
    best[k] = {"attempt_index": r["attempt_index"],
               "completion_tokens": r["completion_tokens"],
               "reasoning_tokens": rt,
               "latency_ms": r["latency_ms"],
               "finish_reason": r["finish_reason"],
               "created_at": r["created_at"],
               "content_chars": len(content),
               "reasoning_chars": len(reasoning),
               "sel_text": sel_text,
               "sel_text_chars": len(sel_text)}

json.dump([{"key": list(k), **v} for k, v in best.items()], open(OUT, "w"))
print("cells:", len(best), "-> ", OUT)
miss = sum(1 for v in best.values() if v["reasoning_tokens"] is None)
print("cells missing reasoning_tokens:", miss)
