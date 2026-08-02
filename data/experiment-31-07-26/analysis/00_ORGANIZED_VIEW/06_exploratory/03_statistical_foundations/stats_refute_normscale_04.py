import json, math, random, statistics as st
from collections import defaultdict
BASE='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis'
D=[r for r in json.load(open(f'{BASE}/paired_clean.json')) if r['analysis_include']]
bc=defaultdict(list)
for r in D: bc[r['cluster']].append(r)
cl=sorted(bc); K=len(cl)
cn=[len(bc[c]) for c in cl]; cd=[sum(r['B_correct']-r['A_correct'] for r in bc[c]) for c in cl]
N=sum(cn); obs=sum(cd)/N; Z=1.959963984540054; T=1.9715
def rob(bn,bd):
    Nn=sum(bn); th=sum(bd)/Nn
    u=[(bd[i]-th*bn[i])/Nn for i in range(K)]
    return th, math.sqrt((K/(K-1.0))*sum(x*x for x in u))
# pooled over 3 independent seeds, OUT=40000 each, for z and t(K-1)
tot=OUTs=0; cz=ct=0
for seed in (11,22,33):
    rng=random.Random(seed)
    for _ in range(40000):
        bn=[];bd=[]
        for _ in range(K):
            j=rng.randrange(K); bn.append(cn[j]); bd.append(cd[j])
        th,se=rob(bn,bd); OUTs+=1
        if th-Z*se<=obs<=th+Z*se: cz+=1
        if th-T*se<=obs<=th+T*se: ct+=1
mc=math.sqrt(.95*.05/OUTs)
print(f'pooled OUT={OUTs}  MC SE={mc:.5f}')
print(f'  z=1.960 x cluster-robust SE : coverage {cz/OUTs:.4f}  deficit {100*(0.95-cz/OUTs):+.2f} pp  ({(0.95-cz/OUTs)/mc:+.1f} MC SE)')
print(f'  t=1.9715 x same SE          : coverage {ct/OUTs:.4f}  deficit {100*(0.95-ct/OUTs):+.2f} pp  ({(0.95-ct/OUTs)/mc:+.1f} MC SE)')
