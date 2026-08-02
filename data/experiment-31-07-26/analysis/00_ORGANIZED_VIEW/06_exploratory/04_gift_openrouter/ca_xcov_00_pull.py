"""ca_xcov_00: independent read-only pull of dataset A cells for both arms.

Deliberately does NOT reuse ca_lib / ca_cov_or_full.json. Goes to the DB, follows
scores -> parsed_answers.provider_attempt_id -> provider_attempts (per RUN_STATUS
hazard #2), names experiments explicitly, and records dataset order.
"""
import json, os, sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(BASE), "experiment.sqlite")
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row

# ---- dataset A items, in dataset order (questions.id ordering = insert order)
items = {}
order = 0
for r in con.execute("""
    select q.id, q.question_id, q.region, q.year, q.exam_part, q.question_number,
           q.correct_letter, length(q.question_text) as qlen
    from questions q join datasets d on d.id=q.dataset_id
    where d.name='balanced_a_310726'
    order by q.id"""):
    items[r["question_id"]] = dict(rowid=r["id"], order=order, region=r["region"],
                                   year=r["year"], exam_part=r["exam_part"],
                                   qnum=r["question_number"],
                                   correct_letter=r["correct_letter"], qlen=r["qlen"])
    order += 1

# ---- scored cells, explicit experiment names, via the scored attempt
cells = []
for r in con.execute("""
    select e.name as exp, lc.model as model, q.question_id as qid,
           s.letter_correct as lc_, s.strict_correct as sc_,
           pa.parse_status as pstatus,
           at.latency_ms as latency_ms, at.completion_tokens as ctok,
           at.finish_reason as finish
    from scores s
    join logical_calls lc on lc.id = s.logical_call_id
    join experiments e    on e.id = lc.experiment_id
    join questions q      on q.id = lc.question_id
    join parsed_answers pa on pa.id = s.parsed_answer_id
    left join provider_attempts at on at.id = pa.provider_attempt_id
    where e.name in ('expA_or_310726','expA_gift_310726')"""):
    cells.append(dict(r))

json.dump({"items": items, "cells": cells},
          open(os.path.join(BASE, "ca_xcov_pull.json"), "w"))

# sanity
from collections import Counter
c = Counter((x["exp"], x["model"]) for x in cells)
print("dataset A items:", len(items))
print("score rows pulled:", len(cells))
for k in sorted(c):
    print("   ", k, c[k])
dup = Counter((x["exp"], x["model"], x["qid"]) for x in cells)
print("duplicate (exp,model,qid) cells:", sum(1 for v in dup.values() if v > 1))
print("parse_status values:", Counter(x["pstatus"] for x in cells))
