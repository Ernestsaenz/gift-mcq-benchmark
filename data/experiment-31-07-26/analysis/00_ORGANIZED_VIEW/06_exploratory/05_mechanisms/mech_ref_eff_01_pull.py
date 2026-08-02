"""REFUTATION pull, independent of mech_00b/mech_merge.

Difference from the original pull: the original keyed on MAX(attempt_index) per
(experiment, model, question_id) with no status filter.  Here I take the
provider_attempt that actually produced the SCORED parsed answer
(scores -> parsed_answers -> provider_attempt_id), which is the attempt the
accuracy analysis used.  Any divergence between the two selections is itself a
finding.
"""
import sqlite3, json, os

DB = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
      "experiment-31-07-26/experiment.sqlite")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "mech_ref_eff_cells.json")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

# ---- 1. everything, via the scored attempt ------------------------------
q_scored = """
SELECT e.name AS exp, lc.model AS model, q.question_id AS qid,
       lc.id AS lcid,
       pa.id AS paid, pa.attempt_index, pa.status_code,
       pa.completion_tokens, pa.prompt_tokens, pa.total_tokens,
       pa.latency_ms, pa.finish_reason, pa.created_at, pa.response_json,
       ans.parse_status, ans.selected_letter,
       s.letter_correct, s.strict_correct
FROM scores s
JOIN parsed_answers ans ON ans.id = s.parsed_answer_id
JOIN provider_attempts pa ON pa.id = ans.provider_attempt_id
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN experiments  e  ON e.id  = lc.experiment_id
JOIN questions    q  ON q.id  = lc.question_id
WHERE e.name IN ('expA_or_310726','expB_or_310726')
"""

# ---- 2. max-attempt_index selection, to reproduce the original ----------
q_all = """
SELECT e.name AS exp, lc.model AS model, q.question_id AS qid,
       pa.id AS paid, pa.attempt_index, pa.status_code, pa.completion_tokens,
       pa.finish_reason, pa.created_at, pa.response_json
FROM provider_attempts pa
JOIN logical_calls lc ON lc.id = pa.logical_call_id
JOIN experiments  e  ON e.id  = lc.experiment_id
JOIN questions    q  ON q.id  = lc.question_id
WHERE e.name IN ('expA_or_310726','expB_or_310726')
ORDER BY e.name, lc.model, q.question_id, pa.attempt_index
"""


def parse_row(r):
    rt = None
    content = reasoning = ""
    ntoks_detail = None
    try:
        j = json.loads(r["response_json"])
        u = j.get("usage") or {}
        d = u.get("completion_tokens_details") or {}
        rt = d.get("reasoning_tokens")
        ntoks_detail = u.get("completion_tokens")
        msg = j["choices"][0]["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning") or ""
    except Exception:
        pass
    sel = ""
    try:
        sel = json.loads(content).get("selected_option_text") or ""
    except Exception:
        pass
    return {"reasoning_tokens": rt,
            "usage_completion_tokens": ntoks_detail,
            "content_chars": len(content),
            "reasoning_chars": len(reasoning),
            "sel_text": sel,
            "sel_text_chars": len(sel)}


scored = {}
dupes = 0
for r in con.execute(q_scored):
    k = (r["exp"], r["model"], r["qid"])
    rec = {"paid": r["paid"], "attempt_index": r["attempt_index"],
           "status_code": r["status_code"],
           "completion_tokens": r["completion_tokens"],
           "prompt_tokens": r["prompt_tokens"],
           "latency_ms": r["latency_ms"],
           "finish_reason": r["finish_reason"],
           "created_at": r["created_at"],
           "parse_status": r["parse_status"],
           "selected_letter": r["selected_letter"],
           "letter_correct": r["letter_correct"],
           **parse_row(r)}
    if k in scored:
        dupes += 1
        # keep the later attempt if genuinely duplicated
        if rec["attempt_index"] <= scored[k]["attempt_index"]:
            continue
    scored[k] = rec

maxatt = {}
for r in con.execute(q_all):
    k = (r["exp"], r["model"], r["qid"])
    if k in maxatt and maxatt[k]["attempt_index"] >= r["attempt_index"]:
        continue
    maxatt[k] = {"paid": r["paid"], "attempt_index": r["attempt_index"],
                 "status_code": r["status_code"],
                 "completion_tokens": r["completion_tokens"],
                 "finish_reason": r["finish_reason"],
                 "created_at": r["created_at"], **parse_row(r)}

print("scored cells:", len(scored), " duplicate score rows:", dupes)
print("max-attempt cells:", len(maxatt))
diff = [k for k in scored if k in maxatt and scored[k]["paid"] != maxatt[k]["paid"]]
print("cells where scored attempt != max-attempt_index attempt:", len(diff))
print("scored cells missing reasoning_tokens:",
      sum(1 for v in scored.values() if v["reasoning_tokens"] is None))
print("status codes (scored):",
      sorted({v["status_code"] for v in scored.values()}))
from collections import Counter
print("finish_reason (scored):", Counter(v["finish_reason"] for v in scored.values()))

json.dump({"scored": [{"key": list(k), **v} for k, v in scored.items()],
           "maxatt": [{"key": list(k), **v} for k, v in maxatt.items()]},
          open(OUT, "w"))
print("->", OUT)
