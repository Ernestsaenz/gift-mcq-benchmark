import json, math, random, statistics as st
from collections import defaultdict
BASE='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis'
D=[r for r in json.load(open(f'{BASE}/paired_clean.json')) if r['analysis_include']]
bc=defaultdict(list)
for r in D: bc[r['cluster']].append(r)
cl=sorted(bc); K=len(cl)
cn=[len(bc[c]) for c in cl]
cd=[sum(r['B_correct']-r['A_correct'] for r in bc[c]) for c in cl]
N=sum(cn); obs=sum(cd)/N; Z=1.959963984540054
def rob(bn,bd):
    Nn=sum(bn); th=sum(bd)/Nn
    u=[(bd[i]-th*bn[i])/Nn for i in range(K)]
    return th, math.sqrt((K/(K-1.0))*sum(x*x for x in u))
rng=random.Random(31337); OUT=40000; cz=0
for _ in range(OUT):
    bn=[];bd=[]
    for _ in range(K):
        j=rng.randrange(K); bn.append(cn[j]); bd.append(cd[j])
    th,se=rob(bn,bd)
    if th-Z*se<=obs<=th+Z*se: cz+=1
mc=math.sqrt(.95*.05/OUT)
print(f'high-precision calibration, OUT={OUT}')
print(f'  normal-theory + cluster-robust SE coverage = {cz/OUT:.4f}  (MC SE {mc:.4f}) '
      f'-> {(0.95-cz/OUT)/mc:+.1f} MC SEs from nominal')
# per-model deltas + item-level structure
mods=sorted(set(r['model'] for r in D))
print('\nper-model deltas:')
for m in mods:
    s=[r for r in D if r['model']==m]
    print(f'  {m:>28} n={len(s):5d} deltaB-A={sum(r["B_correct"]-r["A_correct"] for r in s)/len(s):+.5f}')
# item-level bootstrap (325 items) for contrast with cluster-level
bi=defaultdict(list)
for r in D: bi[r['question_id']].append(r)
it=sorted(bi); I=len(it)
inn=[len(bi[q]) for q in it]; ind=[sum(r['B_correct']-r['A_correct'] for r in bi[q]) for q in it]
rng=random.Random(4); b=[]
for _ in range(20000):
    s=0;c=0
    for _ in range(I):
        j=rng.randrange(I); s+=ind[j]; c+=inn[j]
    b.append(s/c)
print(f'\nitem-level bootstrap SE ({I} items) = {st.stdev(b):.6f}')
rng=random.Random(5); b2=[]
for _ in range(20000):
    s=0;c=0
    for _ in range(K):
        j=rng.randrange(K); s+=cd[j]; c+=cn[j]
    b2.append(s/c)
print(f'cluster-level bootstrap SE ({K} clusters) = {st.stdev(b2):.6f}  '
      f'ratio cluster/item = {st.stdev(b2)/st.stdev(b):.3f}')
