import json, collections
P="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows=json.load(open(P))
print("total rows:",len(rows))
inc=[r for r in rows if r.get("analysis_include") is True]
print("analysis_include==true:",len(inc))
print("distinct question_id:",len({r["question_id"] for r in inc}))
print("distinct cluster:",len({r["cluster"] for r in inc}))
print("distinct model:",len({r["model"] for r in inc}))
c=collections.Counter(r["model"] for r in inc)
for m,n in sorted(c.items()): print(f"  {m:32s} n={n}")
# duplicate check
k=collections.Counter((r["question_id"],r["model"]) for r in inc)
print("dup (qid,model) keys:",sum(1 for v in k.values() if v>1))
# runs=1 sanity: values of A_correct/B_correct
print("A_correct vals:",sorted({r["A_correct"] for r in inc}),"B_correct vals:",sorted({r["B_correct"] for r in inc}))
# items per model
for m in sorted(c):
    qs={r["question_id"] for r in inc if r["model"]==m}
    print(f"  {m:32s} items={len(qs)}")
