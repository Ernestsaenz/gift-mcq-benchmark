"""Pull, for every scored A/B cell, the exact token decomposition and emitted text.

Writes mech_tokens.json: one row per (question_id, model) with A_* and B_* fields:
  ct        completion_tokens (== paired_clean A_tokens/B_tokens, verified)
  rt        completion_tokens_details.reasoning_tokens (provider-reported)
  vis       ct - rt  ("visible" tokens: the emitted answer JSON, the only part
                      that can carry the echoed-option-text confound)
  content   the emitted assistant content string
  reason    the reasoning string (chars)
  echo      the selected_option_text as parsed
Read-only on the DB.
"""
import json, sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = HERE.parent / "experiment.sqlite"
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

Q = """
SELECT q.question_id qid, lc.model model, s.strict_correct correct,
       p.selected_letter sel, p.selected_option_text echo,
       a.completion_tokens ct, a.response_json rj, a.latency_ms lat
FROM scores s
JOIN logical_calls lc    ON lc.id = s.logical_call_id
JOIN questions q         ON q.id  = lc.question_id
JOIN parsed_answers p    ON p.logical_call_id = lc.id
JOIN provider_attempts a ON a.id  = p.provider_attempt_id
JOIN experiments e       ON e.id  = lc.experiment_id
WHERE e.name = ?
"""

def pull(exp):
    out = {}
    for r in conn.execute(Q, (exp,)):
        if r["correct"] is None:
            continue
        rj = json.loads(r["rj"]) if r["rj"] else {}
        usage = rj.get("usage") or {}
        det = usage.get("completion_tokens_details") or {}
        msg = (rj.get("choices") or [{}])[0].get("message") or {}
        content = msg.get("content") or ""
        reason = msg.get("reasoning") or ""
        out[(r["qid"], r["model"])] = {
            "correct": int(r["correct"]), "sel": r["sel"], "echo": r["echo"] or "",
            "ct": r["ct"], "rt": det.get("reasoning_tokens"), "lat": r["lat"],
            "content": content, "reason_chars": len(reason),
            "usage_ct": usage.get("completion_tokens"),
        }
    return out

A, B = pull("expA_or_310726"), pull("expB_or_310726")

# item metadata straight from paired_clean so exclusions match exactly
paired = json.loads((HERE / "paired_clean.json").read_text(encoding="utf-8"))
meta = {(r["question_id"], r["model"]): r for r in paired}

rows = []
for key, m in meta.items():
    if key not in A or key not in B:
        continue
    a, b = A[key], B[key]
    rows.append({
        "qid": key[0], "model": key[1],
        "analysis_include": m["analysis_include"],
        "correct_letter": m["correct_letter"],
        "A_correct": m["A_correct"], "B_correct": m["B_correct"],
        "A_selected": m["A_selected"], "B_selected": m["B_selected"],
        "A_tokens_json": m["A_tokens"], "B_tokens_json": m["B_tokens"],
        "A_ct": a["ct"], "B_ct": b["ct"],
        "A_rt": a["rt"], "B_rt": b["rt"],
        "A_content": a["content"], "B_content": b["content"],
        "A_echo": a["echo"], "B_echo": b["echo"],
        "A_reason_chars": a["reason_chars"], "B_reason_chars": b["reason_chars"],
        "A_lat": a["lat"], "B_lat": b["lat"],
    })

(HERE / "mech_tokens.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

mis = sum(1 for r in rows if r["A_ct"] != r["A_tokens_json"] or r["B_ct"] != r["B_tokens_json"])
print(f"rows={len(rows)}  include={sum(r['analysis_include'] for r in rows)}")
print(f"completion_tokens vs paired_clean tokens mismatches: {mis}")
nort = sum(1 for r in rows if r["A_rt"] is None or r["B_rt"] is None)
print(f"rows missing reasoning_tokens: {nort}")
