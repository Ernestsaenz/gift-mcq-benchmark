"""ca_00: READ-ONLY pull of OpenRouter condition-A scores for the FULL dataset
(balanced_a_310726, 474 items x 4 models) plus item metadata, so we can compare
GIFT-covered vs GIFT-uncovered items on the same footing.

Scoring convention matches the analysis files: a cell counts only if it parsed;
unparsed cells are dropped (never scored incorrect).
"""
import sqlite3, json

DB = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
      "experiment-31-07-26/experiment.sqlite")
BASE = ("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/"
        "experiment-31-07-26/analysis/")
OUT = BASE + "ca_cov_or_full.json"

MODELS = ["google/gemini-3.6-flash", "google/gemma-4-26b-a4b-it",
          "qwen/qwen3.6-35b-a3b", "z-ai/glm-5.2"]

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

# ---- item metadata for dataset A -------------------------------------------
items = {}
for r in con.execute("""
    SELECT q.question_id AS qid, q.region, q.year, q.exam_part,
           q.correct_letter, LENGTH(q.question_text) AS qlen,
           q.question_number
    FROM questions q JOIN datasets d ON d.id = q.dataset_id
    WHERE d.name='balanced_a_310726'
    ORDER BY q.id"""):
    items[r["qid"]] = dict(r)
print("dataset A items:", len(items))

# dataset order == runner order; record the rank so we can see the prefix effect
order = {qid: i for i, qid in enumerate(items.keys())}
for qid, i in order.items():
    items[qid]["order"] = i

# ---- scored cells, both arms, condition A ----------------------------------
cells = {}   # (exp, model, qid) -> dict
q = """
SELECT e.name AS exp, lc.model AS model, q.question_id AS qid,
       s.letter_correct, s.strict_correct, pa2.parse_status, s.id AS sid
FROM scores s
JOIN logical_calls lc ON lc.id = s.logical_call_id
JOIN experiments  e  ON e.id  = lc.experiment_id
JOIN questions    q  ON q.id  = lc.question_id
JOIN parsed_answers pa2 ON pa2.id = s.parsed_answer_id
WHERE e.name IN ('expA_or_310726','expA_gift_310726')
"""
n = 0
for r in con.execute(q):
    n += 1
    k = (r["exp"], r["model"], r["qid"])
    if k in cells:
        # keep the last one; note duplicates
        cells[k]["dupes"] = cells[k].get("dupes", 1) + 1
    cells[k] = {"letter_correct": r["letter_correct"],
                "strict_correct": r["strict_correct"],
                "parse_status": r["parse_status"]}
print("score rows:", n, "distinct cells:", len(cells))

dupes = sum(1 for v in cells.values() if v.get("dupes"))
print("cells with >1 score row:", dupes)

by_exp = {}
for (exp, model, qid), v in cells.items():
    by_exp.setdefault(exp, {}).setdefault(model, {})[qid] = v
for exp in by_exp:
    print(exp, {m: len(d) for m, d in by_exp[exp].items()})

json.dump({"items": items,
           "cells": [{"exp": k[0], "model": k[1], "qid": k[2], **v}
                     for k, v in cells.items()]},
          open(OUT, "w"))
print("written:", OUT)
