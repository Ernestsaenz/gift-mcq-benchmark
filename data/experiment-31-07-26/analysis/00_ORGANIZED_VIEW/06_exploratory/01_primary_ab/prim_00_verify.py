import json, collections
P="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows=json.load(open(P))
print("total rows in file:", len(rows))
keep=[r for r in rows if r.get("analysis_include") is True]
print("analysis_include==true:", len(keep))
print("items:", len(set(r["question_id"] for r in keep)))
print("clusters:", len(set(r["cluster"] for r in keep)))
models=sorted(set(r["model"] for r in keep))
print("models:", models)
# cells per model
cm=collections.Counter(r["model"] for r in keep)
for m in models: print("  ",m,cm[m])
# item x model completeness
byitem=collections.Counter(r["question_id"] for r in keep)
inc=[q for q,c in byitem.items() if c!=4]
print("items without all 4 models:", inc, [byitem[q] for q in inc])
# which model missing
for q in inc:
    have=set(r["model"] for r in keep if r["question_id"]==q)
    print("   ",q,"missing:",sorted(set(models)-have))
# cluster sizes (items per cluster)
cl=collections.defaultdict(set)
for r in keep: cl[r["cluster"]].add(r["question_id"])
sizes=sorted(len(v) for v in cl.values())
print("cluster item-count: min",sizes[0],"med",sizes[len(sizes)//2],"max",sizes[-1],"sum",sum(sizes))
print("cluster size distribution:", collections.Counter(sizes))
# is item nested in exactly one cluster?
q2c=collections.defaultdict(set)
for r in keep: q2c[r["question_id"]].add(r["cluster"])
print("items in >1 cluster:", sum(1 for v in q2c.values() if len(v)>1))
# observed rates
for m in models:
    sub=[r for r in keep if r["model"]==m]
    n=len(sub); a=sum(r["A_correct"] for r in sub); b=sum(r["B_correct"] for r in sub)
    print(f"{m:28s} n={n} A={a/n*100:.2f}% B={b/n*100:.2f}% delta={(b-a)/n*100:+.2f}pp")
n=len(keep); a=sum(r["A_correct"] for r in keep); b=sum(r["B_correct"] for r in keep)
print(f"{'POOLED(cell)':28s} n={n} A={a/n*100:.2f}% B={b/n*100:.2f}% delta={(b-a)/n*100:+.2f}pp")
# check binary
print("A_correct values:", set(r["A_correct"] for r in keep), "B:", set(r["B_correct"] for r in keep))
