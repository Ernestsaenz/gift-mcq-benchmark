#!/usr/bin/env python3
"""stats_structure5.py -- concrete over-dispersion check: do the 4 models flip
the SAME items? Monte-Carlo null preserves each model's own marginal flip rate
but shuffles WHICH items it flips (10000 draws). Stdlib only."""
import json, random, statistics
from collections import defaultdict, Counter
DATA=("/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/"
      "data/experiment-31-07-26/analysis/paired_clean.json")
random.seed(7)
rows=[r for r in json.load(open(DATA)) if r.get("analysis_include") is True]
models=sorted({r["model"] for r in rows})
byq=defaultdict(dict)
for r in rows: byq[r["question_id"]][r["model"]]=r["B_correct"]-r["A_correct"]
obs=Counter()
for q,v in byq.items(): obs[sum(v.values())]+=1
print("observed distribution of per-item SUM of delta over models:",dict(sorted(obs.items())))
obs_down3=sum(c for s,c in obs.items() if s<=-3); obs_zero=obs[0]
per_model=defaultdict(list)
for r in rows: per_model[r["model"]].append(r["B_correct"]-r["A_correct"])
NS=10000; d3=[]; z0=[]; var_sum=[]
qs=sorted(byq); qidx={q:i for i,q in enumerate(qs)}
memb={m:[q for q in qs if m in byq[q]] for m in models}
for _ in range(NS):
    tot=[0]*len(qs)
    for m in models:
        vv=per_model[m][:]; random.shuffle(vv)
        for q,v in zip(memb[m],vv): tot[qidx[q]]+=v
    c=Counter(tot); d3.append(sum(n for s,n in c.items() if s<=-3)); z0.append(c[0])
    var_sum.append(statistics.pvariance(tot))
print(f"items with sum(delta) <= -3 (>=3 of 4 models broke): observed={obs_down3}  "
      f"null mean={statistics.mean(d3):.2f} sd={statistics.pstdev(d3):.2f}  "
      f"p={(sum(1 for x in d3 if x>=obs_down3)+1)/(NS+1):.4f}")
print(f"items with sum(delta) == 0 (no model changed):        observed={obs_zero}  "
      f"null mean={statistics.mean(z0):.2f} sd={statistics.pstdev(z0):.2f}  "
      f"p={(sum(1 for x in z0 if x>=obs_zero)+1)/(NS+1):.4f}")
ov=statistics.pvariance([sum(v.values()) for v in byq.values()])
print(f"variance of per-item sum(delta): observed={ov:.4f}  null mean={statistics.mean(var_sum):.4f}"
      f"  over-dispersion ratio={ov/statistics.mean(var_sum):.4f}"
      f"  p={(sum(1 for x in var_sum if x>=ov)+1)/(NS+1):.4f}")
