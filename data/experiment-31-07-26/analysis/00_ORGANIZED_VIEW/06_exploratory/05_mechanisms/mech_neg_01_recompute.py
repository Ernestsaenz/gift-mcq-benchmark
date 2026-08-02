import json, math
from collections import defaultdict, Counter

P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
rows=[r for r in json.load(open(P)) if r.get('analysis_include')]
print("cells",len(rows),"items",len(set(r['question_id'] for r in rows)),
      "clusters",len(set(r['cluster'] for r in rows)),"models",len(set(r['model'] for r in rows)))

# sanity: per-model cell counts
print(Counter(r['model'] for r in rows))

# A-wrong stratum
aw=[r for r in rows if r['A_correct']==0]
print("A-wrong cells",len(aw),"items",len(set(r['question_id'] for r in aw)))
neg=[r for r in aw if r['negated_stem']]
non=[r for r in aw if not r['negated_stem']]
def rate(x): 
    k=sum(r['B_correct'] for r in x); return k,len(x), k/len(x) if x else float('nan')
print("neg",rate(neg),"items",len(set(r['question_id'] for r in neg)))
print("non",rate(non),"items",len(set(r['question_id'] for r in non)))

for m in sorted(set(r['model'] for r in rows)):
    n=[r for r in aw if r['model']==m and r['negated_stem']]
    o=[r for r in aw if r['model']==m and not r['negated_stem']]
    print(m, rate(n), rate(o))

# overall marginals: A and B accuracy by negation (full sample)
for lab,sub in [('neg',[r for r in rows if r['negated_stem']]),('non',[r for r in rows if not r['negated_stem']])]:
    a=sum(r['A_correct'] for r in sub)/len(sub); b=sum(r['B_correct'] for r in sub)/len(sub)
    print(lab,"n",len(sub),"A_acc %.3f"%a,"B_acc %.3f"%b,"drop %.3f"%(a-b))
