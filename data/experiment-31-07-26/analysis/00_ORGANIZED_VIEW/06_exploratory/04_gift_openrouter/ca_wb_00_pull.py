"""ca_wb_00: read-only pull of condition-A OpenRouter scores for ALL 474 items
of balanced_a_310726, so the who-benefits analysis can see the difficulty of
the items GIFT never reached. Own copy, own prefix -- does not depend on any
other agent's intermediate file.
"""
import sqlite3, json, os

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(BASE), "experiment.sqlite")
OUT = os.path.join(BASE, "ca_wb_or_full.json")

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row

items = {}
for r in con.execute("""
    SELECT q.question_id qid, q.region, q.year, q.exam_part, q.correct_letter,
           LENGTH(q.question_text) qlen, q.question_number
    FROM questions q JOIN datasets d ON d.id=q.dataset_id
    WHERE d.name='balanced_a_310726' ORDER BY q.id"""):
    items[r["qid"]] = dict(r)
for i, qid in enumerate(items):
    items[qid]["order"] = i
print("dataset A items:", len(items))

# LEFT JOIN parsed_answers so a scored-but-unparsed row is still visible; and
# also count logical_calls that produced no score at all (the GIFT shortfall).
cells = {}
for r in con.execute("""
    SELECT e.name exp, lc.model model, q.question_id qid,
           s.strict_correct, s.letter_correct, pa.parse_status
    FROM logical_calls lc
    JOIN experiments e ON e.id=lc.experiment_id
    JOIN questions   q ON q.id=lc.question_id
    LEFT JOIN scores s ON s.logical_call_id=lc.id
    LEFT JOIN parsed_answers pa ON pa.id=s.parsed_answer_id
    WHERE e.name IN ('expA_or_310726','expA_gift_310726')"""):
    cells[(r["exp"], r["model"], r["qid"])] = dict(
        strict_correct=r["strict_correct"], parse_status=r["parse_status"])

byexp = {}
for (e, m, q), v in cells.items():
    byexp.setdefault(e, {}).setdefault(m, []).append(v)
for e in sorted(byexp):
    for m in sorted(byexp[e]):
        v = byexp[e][m]
        ok = sum(1 for x in v if x["parse_status"] == "ok")
        print("  %-18s %-26s calls=%3d parsed_ok=%3d" % (e, m, len(v), ok))

json.dump({"items": items,
           "cells": [{"exp": k[0], "model": k[1], "qid": k[2], **v}
                     for k, v in cells.items()]}, open(OUT, "w"))
print("written", OUT)
