"""Independent pull: every scored cell in expA_gift_310726 and expA_or_310726,
regardless of whether the item is in the 319 'complete on all four' set.

Purpose: measure whether GIFT's own coverage is correlated with GIFT's own
accuracy, which the OR-side difficulty skew in RUN_STATUS.md cannot detect.
"""
import json, sqlite3, os

DB = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite"
OUT = "/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/ca_ref_wb_00_cells.json"

con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
cur = con.cursor()

Q = """
SELECT e.name, q.question_id, lc.model, s.strict_correct, pa.selected_letter,
       q.correct_letter, q.region, q.year, q.exam_part, q.question_number,
       length(q.question_text)
FROM scores s
JOIN parsed_answers pa      ON pa.id = s.parsed_answer_id
JOIN logical_calls  lc      ON lc.id = s.logical_call_id
JOIN experiments    e       ON e.id  = lc.experiment_id
JOIN questions      q       ON q.id  = lc.question_id
WHERE e.name IN ('expA_gift_310726','expA_or_310726')
  AND q.dataset_id = 1
"""
rows = []
for r in cur.execute(Q):
    rows.append(dict(exp=r[0], question_id=r[1], model=r[2], correct=r[3],
                     selected=r[4], correct_letter=r[5], region=r[6], year=r[7],
                     exam_part=r[8], qnum=r[9], qlen=r[10]))
con.close()

print("scored cells pulled:", len(rows))
for e in sorted({r["exp"] for r in rows}):
    sub = [r for r in rows if r["exp"] == e]
    print("  %-18s cells=%4d items=%3d" % (e, len(sub), len({r["question_id"] for r in sub})))

json.dump(rows, open(OUT, "w"))
print("written", OUT)
