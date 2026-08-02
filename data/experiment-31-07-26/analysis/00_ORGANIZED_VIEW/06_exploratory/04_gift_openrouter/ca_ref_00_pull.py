"""Independent read-only pull. No reuse of ca_cov_* outputs."""
import sqlite3, json, collections
DB="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/experiment.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro",uri=True); con.row_factory=sqlite3.Row

print("--- experiments ---")
for r in con.execute("select e.id,e.name,d.name dn,d.row_count from experiments e join datasets d on d.id=e.dataset_id"):
    print(dict(r))

items={}
for r in con.execute("""select q.id rid,q.question_id qid,q.region,q.year,q.exam_part,q.correct_letter,
  q.question_number, length(q.question_text) qlen
  from questions q join datasets d on d.id=q.dataset_id where d.name='balanced_a_310726' order by q.id"""):
    items[r["qid"]]=dict(r)
print("dataset A items:",len(items))
for i,(qid,v) in enumerate(items.items()): v["ord_qid"]=i
print("first5",list(items)[:5],"last5",list(items)[-5:])

# score rows joined the documented way
rows=list(con.execute("""
 select e.name exp, lc.model model, q.question_id qid, lc.run_index,
        s.letter_correct lc_, s.strict_correct sc_, pa.parse_status ps
 from scores s
 join logical_calls lc on lc.id=s.logical_call_id
 join experiments e on e.id=lc.experiment_id
 join questions q on q.id=lc.question_id
 join parsed_answers pa on pa.id=s.parsed_answer_id
 where e.name in ('expA_or_310726','expA_gift_310726')"""))
print("score rows:",len(rows))
seen=collections.Counter((r["exp"],r["model"],r["qid"]) for r in rows)
print("dup cells:",sum(1 for v in seen.values() if v>1))
print("parse_status values:",collections.Counter(r["ps"] for r in rows))
print("letter!=strict:",sum(1 for r in rows if r["lc_"]!=r["sc_"]))
per=collections.Counter((r["exp"],r["model"]) for r in rows)
for k in sorted(per): print(k,per[k])
json.dump({"items":items,"rows":[dict(r) for r in rows]},open("ca_ref_pull.json","w"))
