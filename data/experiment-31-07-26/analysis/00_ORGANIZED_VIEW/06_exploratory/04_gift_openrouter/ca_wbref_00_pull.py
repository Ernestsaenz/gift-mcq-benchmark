"""ca_wbref_00: independent read-only pull for the who-benefits refutation.
  (1) verify the pooled/per-model GIFT-vs-OR 2x2 from cross_arm_A.json against
      the DB directly (explicit experiment names, no LIKE);
  (2) get condition-A OpenRouter strict_correct for ALL 474 dataset-A items so
      the coverage-bias question can be attacked using the items GIFT missed.
"""
import sqlite3, json, os

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(BASE), "experiment.sqlite")

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
con.row_factory = sqlite3.Row

items = {}
for i, r in enumerate(con.execute("""
    SELECT q.question_id qid, q.region, q.year, q.exam_part, q.correct_letter
    FROM questions q JOIN datasets d ON d.id=q.dataset_id
    WHERE d.name='balanced_a_310726' ORDER BY q.id""")):
    items[r["qid"]] = dict(r) | {"order": i}

cells = []
for r in con.execute("""
    SELECT e.name exp, lc.model model, q.question_id qid,
           s.strict_correct sc, pa.parse_status ps, pa.selected_letter sel
    FROM scores s
    JOIN parsed_answers pa ON pa.id = s.parsed_answer_id
    JOIN logical_calls  lc ON lc.id = s.logical_call_id
    JOIN experiments    e  ON e.id  = lc.experiment_id
    JOIN questions      q  ON q.id  = lc.question_id
    WHERE e.name IN ('expA_or_310726','expA_gift_310726')"""):
    cells.append(dict(r))

n = {}
for c in cells:
    n[(c["exp"], c["model"])] = n.get((c["exp"], c["model"]), 0) + 1
for k in sorted(n):
    print("  %-18s %-26s scored=%d" % (k[0], k[1], n[k]))

json.dump({"items": items, "cells": cells},
          open(os.path.join(BASE, "ca_wbref_pull.json"), "w"))
print("dataset A items:", len(items), "scored cells:", len(cells))
