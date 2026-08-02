#!/usr/bin/env python3
"""Cross-check: rebuild A_correct/B_correct from (selected letter == correct_letter)
instead of trusting the stored flags, then recompute the marginals from scratch."""
import json
from collections import defaultdict, Counter
PATH="/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json"
rows=json.load(open(PATH))
inc=[r for r in rows if r.get("analysis_include") is True]

def norm(x):
    return None if x is None else str(x).strip().lower()

mA=mB=0
selA=Counter(); selB=Counter()
for r in inc:
    cl=norm(r["correct_letter"])
    a_der=int(norm(r["A_selected"])==cl)
    b_der=int(norm(r["B_selected"])==cl)
    selA[norm(r["A_selected"])]+=1
    selB[norm(r["B_selected"])]+=1
    if a_der!=int(r["A_correct"]): mA+=1
    if b_der!=int(r["B_correct"]): mB+=1
print("cells:",len(inc))
print("A_correct disagreements with (A_selected==correct_letter):",mA)
print("B_correct disagreements with (B_selected==correct_letter):",mB)
print("A_selected value counts:",dict(selA))
print("B_selected value counts:",dict(selB))
print("correct_letter value counts:",dict(Counter(norm(r['correct_letter']) for r in inc)))

# recompute marginals purely from derived correctness
pm=defaultdict(lambda:[0,0,0])
for r in inc:
    cl=norm(r["correct_letter"])
    e=pm[r["model"]]
    e[0]+=1
    e[1]+=int(norm(r["A_selected"])==cl)
    e[2]+=int(norm(r["B_selected"])==cl)
tot=[0,0,0]
print("\nmarginals rebuilt from letters:")
for m in sorted(pm):
    n,a,b=pm[m]
    tot[0]+=n; tot[1]+=a; tot[2]+=b
    print("  %-28s n=%d A=%d (%.4f%%) B=%d (%.4f%%) d=%.4fpp"%(m,n,a,100*a/n,b,100*b/n,100*b/n-100*a/n))
n,a,b=tot
print("  %-28s n=%d A=%d (%.4f%%) B=%d (%.4f%%) d=%.4fpp"%("POOLED",n,a,100*a/n,b,100*b/n,100*b/n-100*a/n))

# 4 x 325 grid completeness
items=sorted({r["question_id"] for r in inc})
models=sorted({r["model"] for r in inc})
grid={(r["model"],r["question_id"]) for r in inc}
missing=[(m,i) for m in models for i in items if (m,i) not in grid]
print("\nfull grid would be %d x %d = %d ; observed %d ; missing %d: %s"
      %(len(models),len(items),len(models)*len(items),len(grid),len(missing),missing))
print("long rows = 2 * %d = %d"%(len(inc),2*len(inc)))
