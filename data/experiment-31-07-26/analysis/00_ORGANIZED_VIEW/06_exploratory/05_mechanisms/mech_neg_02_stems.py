#!/usr/bin/env python
"""Dump the A-wrong item stems so polarity can be classified independently."""
from __future__ import annotations
import json, sqlite3, re
from pathlib import Path

HERE = Path("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis")
DB = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite"
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

qs = {r["question_id"]: dict(r) for r in conn.execute(
    "SELECT * FROM questions WHERE dataset_id=(SELECT id FROM datasets WHERE name='balanced_a_310726')")}

rows = json.load(open(HERE / "paired_clean.json"))
inc = [r for r in rows if r["analysis_include"]]
items = {}
for r in inc:
    items.setdefault(r["question_id"], r)

out = []
for qid, r in sorted(items.items(), key=lambda kv: int(kv[0][1:])):
    q = qs[qid]
    stem = q["question_text"].split("\n\n")[-1].strip()
    nA = sum(1 for x in inc if x["question_id"] == qid and x["A_correct"] == 0)
    out.append({"qid": qid, "flag": r["negated_stem"], "n_Awrong": nA, "stem": stem})

json.dump(out, open(HERE / "mech_neg_stems.json", "w"), ensure_ascii=False, indent=1)
print("items", len(out), "flagged negated", sum(o["flag"] for o in out))
print("items with >=1 A-wrong cell", sum(1 for o in out if o["n_Awrong"]))
