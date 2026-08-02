#!/usr/bin/env python
"""Pull reasoning_tokens + usage detail per (model, question_id, condition) from the read-only DB,
join to paired_clean.json, write mech_cells.json. Stdlib only."""
import sqlite3, json, os, collections

DB = "file:/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite?mode=ro"
HERE = os.path.dirname(os.path.abspath(__file__))

con = sqlite3.connect(DB, uri=True)
con.row_factory = sqlite3.Row

# Which experiments hold the paired A/B (OpenRouter) runs
EXP = {"expA_or_310726": "A", "expB_or_310726": "B"}

q = """
select e.name as exp, lc.id as lcid, lc.model as model, q.question_id as qid,
       pa.id as paid, pa.attempt_index, pa.status_code, pa.latency_ms, pa.finish_reason,
       pa.prompt_tokens, pa.completion_tokens, pa.total_tokens, pa.response_json,
       s.id as score_id, s.letter_correct, s.strict_correct,
       p.selected_letter, p.parse_status, p.id as parsed_id, p.provider_attempt_id
from logical_calls lc
join experiments e on e.id = lc.experiment_id
join questions q on q.id = lc.question_id
join provider_attempts pa on pa.logical_call_id = lc.id
left join parsed_answers p on p.logical_call_id = lc.id
left join scores s on s.logical_call_id = lc.id
where e.name in ('expA_or_310726','expB_or_310726')
"""
rows = [dict(r) for r in con.execute(q)]
print("raw joined rows:", len(rows))

# Attempts per logical call
per_lc = collections.defaultdict(list)
for r in rows:
    per_lc[r["lcid"]].append(r)
mult = sum(1 for v in per_lc.values() if len({x["paid"] for x in v}) > 1)
print("logical calls:", len(per_lc), " with >1 attempt:", mult)

def parse_usage(rj):
    if not rj:
        return None
    try:
        j = json.loads(rj)
    except Exception:
        return None
    u = j.get("usage") or {}
    ctd = u.get("completion_tokens_details") or {}
    prov = j.get("provider")
    fin = None
    ch = j.get("choices") or []
    msg_len = None
    reason_text_len = None
    if ch:
        fin = ch[0].get("finish_reason")
        m = ch[0].get("message") or {}
        c = m.get("content")
        if isinstance(c, str):
            msg_len = len(c)
        rt = m.get("reasoning")
        if isinstance(rt, str):
            reason_text_len = len(rt)
    return {
        "completion_tokens": u.get("completion_tokens"),
        "prompt_tokens": u.get("prompt_tokens"),
        "reasoning_tokens": ctd.get("reasoning_tokens"),
        "ctd_keys": sorted(ctd.keys()),
        "provider": prov,
        "finish_reason_json": fin,
        "content_chars": msg_len,
        "reasoning_chars": reason_text_len,
    }

cells = {}
for r in rows:
    cond = EXP[r["exp"]]
    # pick the attempt that the parsed answer / score points at, else the successful one
    key = (r["model"], r["qid"], cond)
    u = parse_usage(r["response_json"])
    rec = {
        "model": r["model"], "qid": r["qid"], "cond": cond,
        "paid": r["paid"], "attempt_index": r["attempt_index"],
        "status_code": r["status_code"], "latency_ms": r["latency_ms"],
        "finish_reason": r["finish_reason"],
        "completion_tokens_col": r["completion_tokens"],
        "linked": (r["provider_attempt_id"] == r["paid"]),
        "selected_letter": r["selected_letter"],
        "letter_correct": r["letter_correct"],
    }
    if u:
        rec.update(u)
    prev = cells.get(key)
    if prev is None:
        cells[key] = rec
    else:
        # prefer the attempt referenced by parsed_answers, then status 200, then higher attempt_index
        def rank(x):
            return (1 if x.get("linked") else 0, 1 if x["status_code"] == 200 else 0, x["attempt_index"])
        if rank(rec) > rank(prev):
            cells[key] = rec

print("unique (model,qid,cond) cells:", len(cells))

# reasoning_tokens availability
avail = collections.Counter()
for k, v in cells.items():
    avail[(k[0], k[2], v.get("reasoning_tokens") is None)] += 1
for k in sorted(avail):
    print("model=%s cond=%s reasoning_None=%s n=%d" % (k[0], k[1], k[2], avail[k]))

json.dump({"%s|%s|%s" % k: v for k, v in cells.items()},
          open(os.path.join(HERE, "mech_cells.json"), "w"))
print("wrote mech_cells.json")
