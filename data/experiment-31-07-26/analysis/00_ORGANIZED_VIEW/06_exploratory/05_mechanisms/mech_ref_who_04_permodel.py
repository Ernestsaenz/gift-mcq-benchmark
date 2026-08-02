import json, math, random
from collections import defaultdict
P='/Users/ernestsaenz/Programming/GIFT-abstract-dossier/tier1_mcq/data/experiment-31-07-26/analysis/paired_clean.json'
rows=[r for r in json.load(open(P)) if r.get('analysis_include')]
def logC(n,k): return math.lgamma(n+1)-math.lgamma(k+1)-math.lgamma(n-k+1)
def exact_binom(k,n):
    if n==0: return 1.0
    lp=[logC(n,i)-n*math.log(2) for i in range(n+1)]
    thr=lp[k]+1e-9
    return min(1.0,sum(math.exp(x) for x in lp if x<=thr))
bym=defaultdict(list)
for r in rows: bym[r['model']].append(r)
print("per-model exact McNemar (two-sided exact binomial on discordant cells) + cluster-robust z")
for m in sorted(bym):
    sub=bym[m]; n=len(sub)
    L=sum(1 for r in sub if r['A_correct']==1 and r['B_correct']==0)
    G=sum(1 for r in sub if r['A_correct']==0 and r['B_correct']==1)
    mean=(G-L)/n
    byc=defaultdict(int)
    for r in sub: byc[r['cluster']]+=r['B_correct']-r['A_correct']
    cnt=defaultdict(int)
    for r in sub: cnt[r['cluster']]+=1
    var=sum((byc[c]-mean*cnt[c])**2 for c in byc)/n**2
    se=math.sqrt(var)
    z=mean/se
    p=2*0.5*math.erfc(abs(z)/math.sqrt(2))
    print("  %-30s L=%3d G=%2d net=%+.4f  McNemar p=%.3g | cluster-robust z=%.2f p=%.3g"%(m,L,G,mean,exact_binom(G,L+G),z,p))

# counterfactual: same transition matrix, different A base rate
p_lost=247/1166; p_gain=45/133
print("\nCOUNTERFACTUAL with the SAME transition probabilities (p_lost=%.4f, p_gain=%.4f):"%(p_lost,p_gain))
for base in [0.90,0.75,0.60,0.5,0.40]:
    L=base*p_lost; G=(1-base)*p_gain
    print("  if A acc were %.2f -> expected L:G = %.2f:1, net = %+.4f"%(base, L/G, G-L))
